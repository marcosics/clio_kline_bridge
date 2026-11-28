#!/usr/bin/env python3
"""
clio_web.py - Web local de diagnostico del Clio por linea K y unico tester en la linea.
Pestanas: Tablero, Fallos, Configuracion (varias centralitas + base DDT4ALL) y Aprendizaje.
Claude usa lo mismo via tools/clio_mcp.py (cliente HTTP de esta web).
Backends: sim (sin hardware), elm (ELM327/OBDLink/vLinker por COM) y bridge (firmware/ por COMx o tcp:IP:23).
SOLO LECTURA en el coche: lista blanca de CLAUDE.md sec. 6. Escrituras de configuracion: DDT4ALL/Renolink a mano.

  pip install pyserial
  python tools/clio_web.py            -> http://localhost:8080
"""
import argparse, json, shutil, socket, subprocess, sys, threading, time
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent))
import ddt_db
import clio_drive
from clio_kline import diff

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
LOG = LOGS / f"web_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
REPORTS = ROOT / "informes"
REPORTS.mkdir(exist_ok=True)
DECODE = Path(__file__).parent / "ddcr_decode.json"
ECUS = {"7A": "Inyeccion (DDCR)", "28": "ABS", "26": "UCH", "2C": "Airbag", "51": "Cuadro"}
BRIDGE_CMDS = ("PING", "STATUS", "SNIFF", "KEEPALIVE", "SIM", "VERSION", "STATS", "TEST", "LOGDUMP", "CONFIG", "SET ",
               "SAVE", "WIFI", "NET", "SCAN", "TIMING", "LOG", "BAUD", "ECU ", "INIT", "HELP", "REBOOT", "FACTORY")


def safe(h):
    """Lista blanca de servicios KWP2000. Devuelve el hex normalizado o lanza ValueError."""
    h = h.replace(" ", "").upper()
    if len(h) < 2 or len(h) % 2 or any(c not in "0123456789ABCDEF" for c in h):
        raise ValueError("hex invalido")
    if h == "10C0" or h[:2] in ("3E", "21", "17", "18", "1A"):
        return h
    raise ValueError(f"servicio {h[:2]} bloqueado (solo lectura)")


def checksum(b):
    return sum(b) & 0xFF


def frame_data(b):
    """Quita cabecera y checksum de una trama KWP2000 completa."""
    hdr = 3 if b[0] & 0x80 else 1
    n = b[0] & 0x3F
    if n == 0:
        n = b[hdr]
        hdr += 1
    return b[hdr:hdr + n]


def sim_drive(t):
    """Ciclo de conducción simulado (60 s): rpm, velocidad, temperatura, freno."""
    ph = t % 60
    v = 0 if ph < 8 else min(90, (ph - 8) * 3) if ph < 40 else max(0, 90 - (ph - 40) * 5)
    gear = 1 if v < 15 else 2 if v < 30 else 3 if v < 50 else 4 if v < 70 else 5
    rpm = 820 if v == 0 else int(v * (130, 75, 50, 38, 31)[gear - 1] + 900)
    temp = min(88, 20 + (t - SIM_T0) / 4)
    brake = 1 if 40 <= ph < 52 else 0
    return rpm, v, temp, brake


SIM_T0 = time.time()


def sim_answer(q, ecu="7A"):
    """Misma UCE simulada que firmware/src/main.cpp simAnswer(), con un ciclo de conducción para probar el modo coche."""
    s = q[0]
    if s == 0x81: return bytes([0xC1, 0xEF, 0x8F])
    if s == 0x10: return bytes([0x50, q[1]])
    if s == 0x3E: return b"\x7E"
    if s in (0x17, 0x18): return bytes([s + 0x40, 1, 0x01, 0x23, 0xA0])
    rpm, v, temp, brake = sim_drive(time.time())
    if ecu == "28" and s == 0x21 and q[1] == 0xA0:   # ABS: velocidad de las 4 ruedas, km/h x 100, little endian
        return bytes([0x61, 0xA0]) + b"".join(int(v * 100 + i * 7).to_bytes(2, "little") for i in range(4))
    if s == 0x21 and q[1] in (0x80, 0xA0, 0xA1, 0xA2) and ecu != "28":
        r = bytearray([0x61, q[1]] + [(q[1] * 7 + i * 13) & 0xFF for i in range(2, 26)])
        if q[1] == 0xA1:
            r[2:4] = rpm.to_bytes(2, "little")
            r[6] = int(temp + 40)
        if q[1] == 0xA2:
            r[5] = int(v)
            r[7] = 0x10 | brake
        if q[1] == 0x80: r[2:15] = b"SIM8200212348"
        return bytes(r)
    return bytes([0x7F, s, 0x12 if s == 0x21 else 0x11])


class SimBackend:
    def __init__(self, address, baud): self.ecu = "7A"
    def connect(self, ecu, init="fast"):
        ok = ecu in ("7A", "26", "28")  # el simulador "tiene" inyección, UCH y ABS
        self.ecu = ecu
        return ok, {"init": "OK (simulado)" if ok else "sin respuesta (simulado)", "10C0": self.req("10C0") if ok else ""}
    def req(self, h): return sim_answer(bytes.fromhex(h), self.ecu).hex().upper()
    def close(self): pass


class ElmBackend:
    def __init__(self, address, baud):
        from clio_kline import Elm
        self.e = Elm(address, baud or 38400)
        self.adapter = None

    def connect(self, ecu, init="fast"):
        if init == "slow":  # ISO 14230 con init a 5 baudios
            for c in ("ATZ", "ATE0", "ATL0", "ATS1", "ATH0", "ATAT1", "ATSP4", f"ATSH81{ecu}F1", f"ATIIA{ecu}",
                      f"ATWM81{ecu}F13E"):
                self.e.cmd(c, 5)
            out = {"ATSI": self.e.cmd("ATSI", 10), "10C0": self.e.cmd("10C0", 4)}
        else:
            out = {"10C0": self.e.init(ecu)}
        if self.adapter is None:
            self.adapter = {c: self.e.cmd(c, 3) for c in ("ATI", "STI", "AT@1", "ATRV", "ATDP")}
        out["adapter"] = self.adapter
        return any(l.replace(" ", "").startswith("50") for l in out["10C0"]), out

    def req(self, h): return "".join(l.replace(" ", "") for l in self.e.cmd(h, 4)).upper()
    def at(self, c): return self.e.cmd(c, 5)
    def close(self): self.e.s.close()


def discover_bridge(timeout=2.0):
    """Busca el puente ESP: mDNS clio-kline.local, difusión UDP 'CLIO?' al puerto 4210 y por último su AP 192.168.4.1."""
    try:
        return socket.gethostbyname("clio-kline.local")
    except OSError:
        pass
    try:
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        u.settimeout(timeout)
        u.sendto(b"CLIO?", ("255.255.255.255", 4210))
        data, addr = u.recvfrom(128)
        if data.startswith(b"CLIO"):
            return addr[0]
    except OSError:
        pass
    return "192.168.4.1"


class BridgeBackend:
    """Firmware propio. address: COM5 o tcp:192.168.4.1:23"""
    def __init__(self, address, baud):
        self.lines, self._buf = [], b""
        if address.lower() in ("", "auto"):
            address = "tcp:" + discover_bridge() + ":23"
        if address.lower().startswith("tcp:"):
            host, port = address[4:].rsplit(":", 1)
            self.sock, self.ser = socket.create_connection((host, int(port)), 5), None
            self.sock.settimeout(0.1)
        else:
            import serial
            self.ser, self.sock = serial.Serial(address, baud or 115200, timeout=0.1), None

    def _write(self, line):
        data = (line + "\n").encode()
        self.sock.sendall(data) if self.sock else self.ser.write(data)

    def _readline(self):
        while b"\n" not in self._buf:
            try:
                chunk = self.sock.recv(512) if self.sock else self.ser.read(512)
            except socket.timeout:
                chunk = b""
            if not chunk:
                return None
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line.decode(errors="ignore").strip()

    def cmd(self, line, timeout=8.0):
        """Envia una linea y recoge hasta OK/ERR. Devuelve todas las lineas."""
        self._write(line)
        out, t0 = [], time.time()
        while time.time() - t0 < timeout:
            l = self._readline()
            if l is None:
                continue
            out.append(l)
            self.lines = (self.lines + [l])[-500:]
            if l.startswith(("OK", "ERR")):
                break
        return out

    def connect(self, ecu, init="fast"):
        out = {"PING": self.cmd("PING"),
               "INIT": self.cmd(f"INIT {'SLOW' if init == 'slow' else 'FAST'} {ecu}", 12)}
        out["10C0"] = self.req("10C0")
        out["KEEPALIVE"] = self.cmd("KEEPALIVE ON 1500")
        return bool(out["INIT"]) and out["INIT"][-1].startswith("OK") and out["10C0"].startswith("50"), out

    def req(self, h):
        rx = [l for l in self.cmd("SEND " + h) if l.startswith(("RX", "ERR"))]
        if not rx or rx[-1].startswith("ERR"):
            return " ".join(rx) or "ERR TIMEOUT"
        return frame_data(bytes.fromhex("".join(rx[-1].split()[2:]))).hex().upper()

    def close(self):
        self.sock.close() if self.sock else self.ser.close()


BACKENDS = {"sim": SimBackend, "elm": ElmBackend, "bridge": BridgeBackend}
state = {"b": None, "ecu": "7A", "kind": None, "lock": threading.Lock(), "db": None,
         "rec": {"stop": None, "file": None, "label": "", "lids": [], "n": 0},
         "job": {"name": None, "running": False, "progress": "", "file": None, "stop": threading.Event()},
         "ai": {"proc": None, "log": [], "file": None, "ask": None, "answer": None, "answered": threading.Event(),
                "session": None},
         "ai_auto": {"enabled": False, "interval_min": 30, "max_runs_day": 12, "max_usd_day": 3.0, "last": 0.0,
                     "day": "", "runs": 0, "cost": 0.0}}


drive = clio_drive.Drive(sys.modules[__name__])


def db():
    if state["db"] is None:
        state["db"] = ddt_db.Db()
    return state["db"]


def log(kind, req, resp):
    with open(LOG, "a") as f:
        f.write(json.dumps({"t": time.time(), "k": kind, "ecu": state["ecu"], "req": req, "resp": resp}) + "\n")


def request(h, log_it=True):
    h = safe(h)
    if not state["b"]:
        raise RuntimeError("no conectado")
    with state["lock"]:
        r = state["b"].req(h)
    if log_it:
        log("req", h, r)
    return r


def select(ecu, init):
    with state["lock"]:
        ok, info = state["b"].connect(ecu, init)
    state["ecu"] = ecu
    log("select", {"ecu": ecu, "init": init}, info)
    return ok, info


def parse_dtc(r):
    """57/58 nn [hi lo estado]*n. Nombre del codigo: base DDT (devices) si esta cargada."""
    if r[:2] not in ("57", "58"):
        return {"raw": r, "error": "respuesta no valida"}
    b = bytes.fromhex(r)
    devs = {str(d.get("dtc", "")).upper(): d.get("name", "") for d in (db().ecu or {}).get("devices", [])}
    return {"raw": r, "count": b[1], "dtc": [{"code": f"{b[i]:02X}{b[i+1]:02X}", "status": f"{b[i+2]:02X}",
                                              "name": devs.get(f"{b[i]:02X}{b[i+1]:02X}", "")}
                                             for i in range(2, len(b) - 2, 3)]}


def decode_table():
    try:
        return json.loads(DECODE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def decode_local(lid, data):
    """tools/ddcr_decode.json: lo aprendido. 16 bits = little endian en la DDCR."""
    out = []
    for p in decode_table().get(lid, []):
        raw = data[p["byte"]:p["byte"] + p.get("len", 1)]
        if len(raw) != p.get("len", 1):
            continue
        v = int.from_bytes(raw, "little" if p.get("le", True) else "big")
        if p.get("bit", -1) >= 0:
            v = (v >> p["bit"]) & 1
        out.append({"name": p["name"], "value": round(v * p.get("scale", 1) + p.get("offset", 0), 3),
                    "unit": p.get("unit", ""), "byte": p["byte"], "src": "local"})
    return out


def decode_all(lid, d, r):
    """Variables de una respuesta 61xx: tabla aprendida (local) + base DDT4ALL si está cargada."""
    out = decode_local(lid, d)
    req = db().by_sent("21" + lid)
    if req:
        out += [dict(v, src="ddt") for v in db().decode_request(req, r)]
    return out


def read_lid(lid, log_it=True):
    r = request("21" + lid, log_it)
    if not r.startswith("61" + lid):
        return {"error": r}
    d = bytes.fromhex(r[4:])
    return {"bytes": list(d), "decoded": decode_all(lid, d, r)}


# ---------- aprendizaje: grabacion con marcas y analisis de diferencias ----------
def _record(lids, period, fn, stop):
    rec, last = state["rec"], None
    with open(fn, "a") as f:
        while not stop.is_set():
            t0 = time.time()
            if rec["label"] != last:
                last = rec["label"]
                f.write(json.dumps({"t": t0, "mark": last}) + "\n")
            for lid in lids:
                try:
                    r = request("21" + lid, log_it=False)
                except Exception as e:
                    r = f"ERR {e}"
                f.write(json.dumps({"t": time.time(), "label": last, "lid": lid, "r": r}) + "\n")
                rec["n"] += 1
            f.flush()
            stop.wait(max(0.0, period - (time.time() - t0)))


def analyze(fn):
    seg, order = {}, []
    for line in open(fn):
        d = json.loads(line)
        if "lid" not in d or not d["r"].startswith("61" + d["lid"]):
            continue
        if d["label"] not in seg:
            seg[d["label"]] = {}
            order.append(d["label"])
        seg[d["label"]].setdefault(d["lid"], []).append(bytes.fromhex(d["r"][4:]))
    if not order:
        return {"error": "grabacion sin datos validos"}
    lids = {l for s in seg.values() for l in s}
    base = seg[order[0]]
    changes = {lab: diff({l: base.get(l, []) for l in lids}, {l: seg[lab].get(l, []) for l in lids}) for lab in order[1:]}
    ranges = {}
    for lid in lids:
        allv = [b for s in seg.values() for b in s.get(lid, [])]
        n = min(len(b) for b in allv)
        byt = {i: [min(b[i] for b in allv), max(b[i] for b in allv)] for i in range(n)}
        u16 = {i: [min(b[i] | b[i + 1] << 8 for b in allv), max(b[i] | b[i + 1] << 8 for b in allv)] for i in range(n - 1)}
        ranges[lid] = {"samples": len(allv), "bytes_que_varian": {i: v for i, v in byt.items() if v[0] != v[1]},
                       "u16le_que_varian": {i: v for i, v in u16.items() if v[0] != v[1]}}
    return {"file": Path(fn).name, "marcas": order, "cambios_respecto_a_" + order[0]: changes, "rangos": ranges}


# ---------- exploracion automatica (sin IA): todas las UCE, todos los LIDs, clasificacion de bytes ----------
def classify(samples):
    """Tipo de cada byte en una serie de muestras: constante, contador o variable."""
    n, out, const = min(len(s) for s in samples), [], 0
    for i in range(n):
        vals = [s[i] for s in samples]
        if len(set(vals)) == 1:
            const += 1
            continue
        steps = [(b - a) & 0xFF for a, b in zip(vals, vals[1:])]
        kind = "contador" if all(x in (0, 1) for x in steps) and sum(steps) > 2 else "variable"
        out.append({"byte": i, "tipo": kind, "min": min(vals), "max": max(vals), "distintos": len(set(vals))})
    return {"muestras": len(samples), "bytes_constantes": const, "bytes_que_cambian": out}


def _try(h):
    try:
        return request(h)
    except Exception as e:
        return f"ERR {e}"


def explore(ecus, init, full_scan, sample_s, job):
    orig, res = state["ecu"], {}
    try:
        for e in ecus:
            if job["stop"].is_set():
                break
            job["progress"] = f"{e}: init"
            ok, _ = select(e, init)
            r = res[e] = {"nombre": ECUS.get(e, "?"), "responde": ok}
            if not ok:
                continue
            r["2180"] = _try("2180")
            r["ident"] = ddt_db.parse_ident(r["2180"]) if r["2180"].startswith("6180") else None
            r["averias"] = {s: parse_dtc(_try(s + "FF00")) for s in ("17", "18")}
            lids = range(1, 256) if full_scan else (0x80, 0x81, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5)
            found = {}
            for i in lids:
                if job["stop"].is_set():
                    break
                lid = f"{i:02X}"
                job["progress"] = f"{e}: 21{lid}"
                x = _try("21" + lid)
                if x.startswith("61" + lid):
                    found[lid] = x[4:]
                if i % 20 == 0:
                    _try("3E")
            r["lids"] = found
            samples, t0 = {l: [] for l in found}, time.time()
            while found and time.time() - t0 < sample_s and not job["stop"].is_set():
                for lid in found:
                    job["progress"] = f"{e}: muestreando 21{lid}"
                    x = _try("21" + lid)
                    if x.startswith("61" + lid):
                        samples[lid].append(bytes.fromhex(x[4:]))
            r["analisis"] = {l: classify(s) for l, s in samples.items() if s}
    finally:
        if state["b"]:
            select(orig, init)
        fn = LOGS / f"explore_{datetime.now():%Y%m%d_%H%M%S}.json"
        fn.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        job.update(running=False, file=fn.name, progress=f"terminado -> logs/{fn.name}")


def start_job(name, target, *args):
    job = state["job"]
    if job["running"]:
        raise RuntimeError(f"ya hay un trabajo en marcha: {job['name']}")
    job.update(name=name, running=True, progress="empezando", file=None)
    job["stop"].clear()
    threading.Thread(target=target, args=(*args, job), daemon=True).start()
    return {"ok": True}


# ---------- Claude en vivo: sesion autonoma de Claude Code con el MCP clio-kline ----------
AI_PROMPT = """Estás conectado EN VIVO al Renault Clio II 1.5 dCi del usuario a través del MCP clio-kline (la web clio_web.py).
Lee CLAUDE.md para el contexto. Trabaja tú solo, de forma ordenada, y explica cada paso en una línea en español.
Objetivo del usuario: {goal}

Pasos:
1. status. Si no está conectado, dilo y termina.
2. ident, read_dtc y ecu_scan: qué centralitas responden (inyección, ABS, UCH/llaves/luces, airbag, cuadro).
3. auto_explore (full_scan=true en la inyección si no hay escaneo previo en recordings) y luego lee el resultado del archivo logs/explore_*.json.
4. db_status/db_search si hay base DDT4ALL: relaciona LIDs y bytes con nombres oficiales.
5. Aprendizaje guiado: para freno, embrague, pedal del acelerador, A/C, luces, etc. usa learn_start, ask_user
   ("pisa el freno y pulsa Hecho"), learn_mark, learn_stop y learn_analyze. Guarda con decode_set SOLO lo que
   tenga evidencia clara, con la evidencia en note; las hipótesis, con el nombre empezando por "?".
6. Escribe el informe informes/informe_{fecha}.md con:
   - centralitas e identificación;
   - averías con su interpretación y posibles causas;
   - variables identificadas e hipótesis;
   - valores fuera de lo normal y posibles problemas;
   - recomendaciones de parámetros a revisar o cambiar (el usuario las aplicará a mano con DDT4ALL, con copia y cargador);
   - lo que falta y qué necesitas del usuario.
Reglas: nunca intentes escribir en una centralita ni borrar averías (está bloqueado y no se debe intentar).
Llaves/antiarranque: solo lectura de estado; el registro de llaves se hace con Renolink/CLIP y el código de seguridad del coche."""


def _ai_reader(proc, fn):
    ai = state["ai"]
    with open(fn, "a", encoding="utf-8") as f:
        for line in proc.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                ev = {"type": "raw", "text": line.strip()}
            out = []
            if ev.get("session_id"):
                ai["session"] = ev["session_id"]
            if ev.get("type") == "result":
                state["ai_auto"]["cost"] += float(ev.get("total_cost_usd") or 0)
            if ev.get("type") == "assistant":
                for c in ev["message"].get("content", []):
                    if c.get("type") == "text":
                        out.append("💬 " + c["text"])
                        for l in c["text"].splitlines():
                            if l.strip().startswith("ALERTA"):
                                drive.event("ia", l.strip())
                    elif c.get("type") == "tool_use":
                        out.append(f"🔧 {c['name'].replace('mcp__clio-kline__', '')} {json.dumps(c.get('input', {}), ensure_ascii=False)[:200]}")
            elif ev.get("type") == "user":
                for c in ev.get("message", {}).get("content", []):
                    if isinstance(c, dict) and c.get("type") == "tool_result":
                        txt = c.get("content")
                        txt = txt if isinstance(txt, str) else json.dumps(txt, ensure_ascii=False)
                        out.append("   ↳ " + txt[:300])
            elif ev.get("type") == "result":
                out.append(f"✅ fin ({ev.get('subtype')}) coste ${ev.get('total_cost_usd', 0):.2f}")
            elif ev.get("type") == "raw" and ev["text"]:
                out.append(ev["text"])
            for o in out:
                ai["log"].append(o)
                f.write(o + "\n")
    ai["proc"] = None


AUTO_PROMPT = """Modo coche, revisión automática ({motivo}). Estás conectado al Clio por el MCP clio-kline.
Contexto: CLAUDE.md. Empieza leyendo tu memoria con memory_get (lo que ya sabes del coche).
1. drive_status y events (desde hace {desde} min): ¿qué ha pasado? Interpreta averías y anomalías y di causas probables.
2. drive_summary y, si hay registro, analyze_drive: canales que varían, bits que conmutan y parejas correlacionadas.
   Relaciónalo con lo que ya sabes y con la base DDT (db_search) para identificar variables nuevas.
   Guarda con decode_set solo lo que tenga evidencia clara (con la evidencia en note); hipótesis con nombre "?...".
3. Mejora el panel con ui_page: lo importante arriba (lo que avisa de fallos), lo nuevo que descubras, y páginas de
   configuración con widgets 'request' de la base DDT para ver cada parámetro (cambiarlos es a mano con DDT4ALL).
4. Si necesitas un cálculo, escribe un script en analisis/ y ejecútalo con python (lee logs/, nunca abre el puerto).
5. memory_add con lo aprendido y lo pendiente, en pocas líneas.
6. Si hay algo urgente (avería nueva, temperatura alta, presión de rail anómala...), escribe una línea que empiece por ALERTA:.
No uses ask_user si drive_status dice que se está registrando (el usuario conduce).
Nunca intentes escribir en una centralita ni borrar averías: está bloqueado y no se debe intentar."""


def _claude_cmd(prompt, resume=None):
    exe = shutil.which("claude") or "claude"   # en Windows encuentra claude.cmd
    cmd = [exe, "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--mcp-config", str(ROOT / ".mcp.json"), "--strict-mcp-config",
           "--allowedTools", "mcp__clio-kline", "Read", "Grep", "Glob", "Write(informes/**)", "Write(analisis/**)",
           "Edit(analisis/**)", "Bash(python analisis/*)"]
    if resume:
        cmd += ["--resume", resume]
    return cmd


def ai_run(prompt, title, resume=None):
    ai = state["ai"]
    if ai["proc"]:
        raise RuntimeError("Claude ya está en marcha")
    (ROOT / "analisis").mkdir(exist_ok=True)
    fn = REPORTS / f"claude_{datetime.now():%Y%m%d_%H%M%S}.log"
    ai["log"].append(f"▶ {title}")
    ai["file"] = fn.name
    ai["proc"] = subprocess.Popen(_claude_cmd(prompt, resume), cwd=ROOT, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    threading.Thread(target=_ai_reader, args=(ai["proc"], fn), daemon=True).start()
    return {"ok": True, "log": fn.name}


def ai_start(goal):
    if not state["b"]:
        raise RuntimeError("conecta primero")
    prompt = AI_PROMPT.format(goal=goal or "entender todo el coche: datos, averías, centralitas, y recomendar",
                              fecha=datetime.now().strftime("%Y%m%d_%H%M"))
    return ai_run(prompt, f"Claude en vivo: {goal or 'exploración completa'}")


def ai_chat(text):
    """Pregunta libre a Claude; sigue la misma conversación (--resume) para que recuerde el contexto."""
    ai = state["ai"]
    prompt = text if ai.get("session") else (
        "Eres el asistente del Clio del usuario, conectado por el MCP clio-kline (lee CLAUDE.md y memory_get). "
        "Puedes leer datos, analizar registros, guardar variables (decode_set), rediseñar el panel (ui_page) y apuntar "
        "en tu memoria (memory_add). Nunca escribas en una centralita. Petición del usuario: " + text)
    return ai_run(prompt, "Tú: " + text, ai.get("session"))


def ai_supervisor():
    """IA automática en el coche: revisa cada N minutos o cuando hay averías/anomalías nuevas, con tope diario."""
    auto, last_ev = state["ai_auto"], 0
    while True:
        time.sleep(20)
        if not auto["enabled"] or state["ai"]["proc"]:
            continue
        today = datetime.now().strftime("%Y%m%d")
        if auto["day"] != today:
            auto.update(day=today, runs=0, cost=0.0)
        if auto["runs"] >= auto["max_runs_day"] or auto["cost"] >= auto["max_usd_day"]:
            continue
        now = time.time()
        new = [e for e in drive.events if e["t"] > last_ev and e["kind"] in ("averia", "anomalia", "descubrimiento")]
        due = now - auto["last"] > auto["interval_min"] * 60
        hot = new and now - auto["last"] > 300
        if not (due or hot) or not drive.status()["running"]:
            continue
        last_ev = max([e["t"] for e in new] + [last_ev])
        motivo = f"{len(new)} eventos nuevos" if hot else f"revisión cada {auto['interval_min']} min"
        desde = int((now - auto["last"]) / 60) if auto["last"] else 60
        auto.update(last=now, runs=auto["runs"] + 1)
        try:
            ai_run(AUTO_PROMPT.format(motivo=motivo, desde=desde), f"IA automática: {motivo}")
        except Exception as e:
            state["ai"]["log"].append(f"⚠ IA automática: {e}")


def ai_ask(text, timeout=300):
    """La IA pregunta al usuario (banner en la web) y espera la respuesta."""
    ai = state["ai"]
    ai["answered"].clear()
    ai.update(ask=text, answer=None)
    ok = ai["answered"].wait(timeout)
    ai["ask"] = None
    return {"answer": ai["answer"] if ok else "sin respuesta (tiempo agotado)"}


def api(path, q, body):
    rec = state["rec"]
    if path == "/api/connect":
        if state["b"]:
            state["b"].close()
            state["b"] = None
        b = BACKENDS[body["backend"]](body.get("address", ""), int(body.get("baud") or 0))
        state["b"], state["kind"] = b, body["backend"]
        ok, info = select(body.get("ecu", "7A").upper(), body.get("init", "fast"))
        return {"ok": ok, "info": info}
    if path == "/api/disconnect":
        if rec["stop"]:
            rec["stop"].set()
        if state["b"]:
            state["b"].close()
        state["b"] = None
        return {"ok": True}
    if path == "/api/status":
        return {"connected": bool(state["b"]), "backend": state["kind"], "ecu": state["ecu"], "ecus": list(ECUS.items()),
                "log": str(LOG.relative_to(ROOT)), "recording": bool(rec["stop"] and not rec["stop"].is_set()),
                "rec_file": rec["file"], "rec_label": rec["label"], "rec_samples": rec["n"], "db": db().status(),
                "job": {k: v for k, v in state["job"].items() if k != "stop"},
                "ai": {"running": bool(state["ai"]["proc"]), "ask": state["ai"]["ask"], "lines": len(state["ai"]["log"])}}
    if path == "/api/select_ecu":
        ok, info = select(body["ecu"].upper(), body.get("init", "fast"))
        return {"ok": ok, "info": info}
    if path == "/api/ecu_scan":
        orig, init, out = state["ecu"], body.get("init", "fast"), {}
        for e in [x.upper() for x in body.get("ecus") or ECUS]:
            ok, info = select(e, init)
            out[e] = {"name": ECUS.get(e, "?"), "ok": ok, "2180": request("2180") if ok else None}
        select(orig, init)
        return out
    if path == "/api/ident":
        r = request("2180")
        out = {"2180": r, "ascii": "".join(chr(c) if 31 < c < 127 else "." for c in bytes.fromhex(r)) if r.startswith("61") else ""}
        if r.startswith("6180"):
            out["ident"] = ddt_db.parse_ident(r)
            out["ddt_candidatos"] = db().candidates(state["ecu"], out["ident"])[:10]
        return out
    if path == "/api/dtc":
        return {"17": parse_dtc(request("17FF00")), "18": parse_dtc(request("18FF00"))}
    if path == "/api/live":
        return {"t": time.time(), "ecu": state["ecu"],
                "lids": {lid: read_lid(lid) for lid in q.get("lids", ["A0,A1,A2"])[0].upper().split(",") if lid}}
    if path == "/api/scan":
        found = {}
        for i in range(int(body.get("start", 1)), int(body.get("end", 255)) + 1):
            lid = f"{i:02X}"
            r = request("21" + lid)
            if r.startswith("61" + lid):
                found[lid] = r[4:]
            if i % 20 == 0:
                request("3E")
        fn = LOGS / f"scan_{state['ecu']}_{datetime.now():%Y%m%d_%H%M%S}.json"
        fn.write_text(json.dumps(found, indent=1))
        return {"found": found, "file": fn.name}
    if path == "/api/console":
        line, b = body["line"].strip(), state["b"]
        if line.upper().startswith("AT") and isinstance(b, ElmBackend):
            with state["lock"]:
                r = b.at(line.replace(" ", "").upper())
        elif line.upper().startswith(BRIDGE_CMDS) and isinstance(b, BridgeBackend):
            with state["lock"]:
                r = b.cmd(line.upper(), 3)
        else:
            r = request(line)
        log("console", line, r)
        return {"resp": r}
    if path == "/api/serial_log":
        b = state["b"]
        return {"lines": b.lines[-int(q.get("n", ["100"])[0]):] if isinstance(b, BridgeBackend) else []}
    if path == "/api/learn/start":
        if not state["b"]:
            raise RuntimeError("no conectado")
        if rec["stop"] and not rec["stop"].is_set():
            raise RuntimeError("ya hay una grabacion en marcha")
        lids = [l.strip().upper() for l in body.get("lids", "A0,A1,A2").split(",") if l.strip()]
        name = "".join(c for c in body.get("name", "rec") if c.isalnum() or c in "-_") or "rec"
        fn = LOGS / f"rec_{name}_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        rec.update(stop=threading.Event(), file=fn.name, label=body.get("label", "reposo"), lids=lids, n=0)
        threading.Thread(target=_record, args=(lids, int(body.get("period_ms", 200)) / 1000, fn, rec["stop"]),
                         daemon=True).start()
        return {"ok": True, "file": fn.name}
    if path == "/api/learn/mark":
        rec["label"] = body["label"]
        return {"ok": True, "label": rec["label"], "samples": rec["n"]}
    if path == "/api/learn/stop":
        if rec["stop"]:
            rec["stop"].set()
        return {"ok": True, "file": rec["file"], "samples": rec["n"]}
    if path == "/api/learn/analyze":
        name = body.get("file") or rec["file"]
        if not name:
            raise RuntimeError("no hay grabacion")
        return analyze(LOGS / Path(name).name)
    if path == "/api/recordings":
        return {"files": sorted((p.name for p in LOGS.glob("*") if p.name.startswith(("rec_", "scan_"))), reverse=True)}
    if path == "/api/decode":
        if not body:
            return decode_table()
        t = decode_table()
        lid = body.pop("lid").upper()
        if body.get("bit", -1) < 0:
            body.pop("bit", None)
        t[lid] = [p for p in t.get(lid, []) if p["name"] != body["name"]] + ([body] if not body.get("delete") else [])
        DECODE.write_text(json.dumps(t, indent=1, ensure_ascii=False), encoding="utf-8")
        return {"ok": True, lid: t[lid]}
    if path == "/api/db/status":
        return dict(db().status(), candidatos=db().candidates(state["ecu"])[:30])
    if path == "/api/db/load":
        return db().load(body["file"], body.get("endian", ""))
    if path == "/api/db/search":
        return db().search(body["text"])
    if path == "/api/db/requests":
        out = []
        for r in db().requests():
            try:
                safe(r.get("sentbytes", "")); ro = True
            except ValueError:
                ro = False
            out.append({"name": r["name"], "sent": r.get("sentbytes", ""), "lectura": ro,
                        "datos": list(r.get("receivebyte_dataitems", {}) if ro else r.get("sendbyte_dataitems", {}))})
        return {"requests": out}
    if path == "/api/db/read":
        req = db().request(body["name"])
        if not req:
            raise RuntimeError("peticion no encontrada en la base")
        r = request(req["sentbytes"])
        return {"sent": req["sentbytes"], "resp": r, "values": db().decode_request(req, r) if r[:2] != "7F" else []}
    if path == "/api/auto/explore":
        if not state["b"]:
            raise RuntimeError("no conectado")
        ecus = [e.upper() for e in body.get("ecus") or ECUS]
        return start_job("exploracion", explore, ecus, body.get("init", "fast"), bool(body.get("full_scan", True)),
                         float(body.get("sample_s", 5)))
    if path == "/api/job":
        return {k: v for k, v in state["job"].items() if k != "stop"}
    if path == "/api/job/stop":
        state["job"]["stop"].set()
        return {"ok": True}
    if path == "/api/ai/start":
        return ai_start(body.get("goal", ""))
    if path == "/api/ai/stop":
        p = state["ai"]["proc"]
        if p:
            p.terminate()
        state["ai"]["answered"].set()
        return {"ok": True}
    if path == "/api/ai/log":
        since = int(q.get("since", ["0"])[0])
        return {"lines": state["ai"]["log"][since:], "next": len(state["ai"]["log"]), "running": bool(state["ai"]["proc"]),
                "ask": state["ai"]["ask"]}
    if path == "/api/ai/ask":
        return ai_ask(body["text"], int(body.get("timeout", 300)))
    if path == "/api/ai/answer":
        state["ai"]["answer"] = body.get("answer", "hecho")
        state["ai"]["answered"].set()
        return {"ok": True}
    # ---------- modo coche: registro continuo, eventos, descubrimiento, panel y memoria ----------
    if path == "/api/drive/start":
        return drive.start(body.get("plan"), body.get("auto"))
    if path == "/api/drive/stop":
        return drive.stop()
    if path == "/api/drive/status":
        return drive.status()
    if path == "/api/drive/latest":
        return {k: v for k, v in drive.latest.items()}
    if path == "/api/drive/series":
        keys = q.get("key", [""])[0].split(",")
        n = int(q.get("n", ["300"])[0])
        return {k: drive.series(k, n) for k in keys if k.count(":") >= 2}
    if path == "/api/drive/values":
        return {k: drive.resolve(k) for k in q.get("keys", [""])[0].split(",") if k.count(":") >= 2}
    if path == "/api/drive/summary":
        return drive.summary(int(q.get("top", ["40"])[0]))
    if path == "/api/events":
        since = time.time() - float(q.get("minutes", ["60"])[0]) * 60
        kinds = [k for k in q.get("kinds", [""])[0].split(",") if k]
        return {"events": [e for e in drive.events if e["t"] >= since and (not kinds or e["kind"] in kinds)]}
    if path == "/api/drives":
        return {"files": sorted((p.name for p in LOGS.glob("drive_*.jsonl")), reverse=True)}
    if path == "/api/discover":
        name = body.get("file") or (drive.file.name if drive.file else "")
        if not name:
            raise RuntimeError("no hay registro: arranca el modo coche")
        return clio_drive.analyze_drive(LOGS / Path(name).name)
    if path == "/api/ui":
        return clio_drive.ui_save(body["ui"]) if body.get("ui") else clio_drive.ui_get()
    if path == "/api/ui/page":
        return clio_drive.ui_page(body["page"])
    if path == "/api/memory":
        return clio_drive.memory_add(body["text"], body.get("section", "Notas")) if body.get("text") else \
            {"text": clio_drive.memory_get()}
    if path == "/api/ai/auto":
        a = state["ai_auto"]
        for k in ("enabled", "interval_min", "max_runs_day", "max_usd_day"):
            if k in body:
                a[k] = type(a[k])(body[k])
        return {k: v for k, v in a.items()}
    if path == "/api/ai/chat":
        return ai_chat(body["text"])
    if path == "/api/reports":
        return {"files": sorted((p.name for p in REPORTS.glob("*") if p.suffix in (".md", ".log")), reverse=True)}
    if path == "/api/report":
        return {"text": (REPORTS / Path(q["name"][0]).name).read_text(encoding="utf-8", errors="replace")}
    return None


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, body):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(200, (Path(__file__).parent / "web" / "index.html").read_bytes(), "text/html; charset=utf-8")
        try:
            r = api(u.path, parse_qs(u.query), body)
            self._send(404, {"error": f"no existe {u.path}"}) if r is None else self._send(200, r)
        except Exception as e:  # el error se muestra en la web/MCP en vez de tumbar el servidor
            self._send(400, {"error": f"{type(e).__name__}: {e}"})

    def do_GET(self): self._handle({})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self._handle(json.loads(self.rfile.read(n) or b"{}"))

    def log_message(self, *a): pass


class Server(ThreadingHTTPServer):
    allow_reuse_address = False  # en Windows, True deja arrancar dos servidores en el mismo puerto


def main():
    ap = argparse.ArgumentParser(description="Web de diagnóstico del Clio (único tester de la línea K)")
    ap.add_argument("port", nargs="?", type=int, default=8080)
    ap.add_argument("--lan", action="store_true", help="abrir también a la red (ver el panel desde el móvil)")
    ap.add_argument("--auto", help="conectar solo y reconectar: bridge:auto · bridge:tcp:IP:23 · elm:COM5 · sim")
    ap.add_argument("--drive", action="store_true", help="arrancar el registro continuo (modo coche)")
    ap.add_argument("--lids", default="A0,A1,A2", help="LIDs de la UCE principal en el registro")
    ap.add_argument("--otras", default="", help="otras UCE a visitar, p. ej. 28:A0,A1;26:80")
    ap.add_argument("--ia-auto", type=int, default=0, metavar="MIN", help="IA automática cada MIN minutos (0 = no)")
    a = ap.parse_args()
    threading.Thread(target=ai_supervisor, daemon=True).start()
    if a.auto:
        backend, _, address = a.auto.partition(":")
        drive.auto = {"backend": backend, "address": address, "baud": 0}
    if a.drive or a.auto:
        others = [{"ecu": o.split(":")[0].upper(), "lids": [l for l in o.split(":")[1].split(",") if l] if ":" in o else [],
                   "dtc": True} for o in a.otras.split(";") if o.strip()]
        drive.start({"main_lids": [l for l in a.lids.upper().split(",") if l], "others": others})
    if a.ia_auto:
        state["ai_auto"].update(enabled=True, interval_min=a.ia_auto)
    host = "0.0.0.0" if a.lan else "127.0.0.1"
    print(f"http://localhost:{a.port}  (log: {LOG})" + ("  · abierta a la red" if a.lan else ""))
    Server((host, a.port), H).serve_forever()


if __name__ == "__main__":
    main()
