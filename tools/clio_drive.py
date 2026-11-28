"""
clio_drive.py - Modo coche: registro continuo, anomalías, autodescubrimiento y paneles que diseña la IA.
Lo usa clio_web.py (único tester de la línea K). Todo es SOLO LECTURA: usa web.request(), que pasa la lista blanca.

- Registro: lee sin parar los LIDs de la UCE principal; cada `other_every_s` visita las otras UCE del plan
  y vuelve; averías cada `dtc_every_s`. Si se cae la línea (contacto quitado), reintenta solo.
  Guarda logs/drive_*.jsonl (una línea por lectura, con los valores decodificados).
- Anomalías: estadística en línea por canal (byte, u16 little endian y variable decodificada):
  salto fuera de rango aprendido, avería nueva, fallos de comunicación seguidos y bytes "dormidos" que despiertan.
  Van a logs/events.jsonl y a la web; la IA los lee con el MCP.
- Descubrimiento: analiza un registro: qué canales varían, contadores, bits que conmutan y grupos de canales que
  se mueven juntos (correlación), para que la IA proponga qué es cada cosa.
- Paneles: tools/ui_layout.json (páginas y widgets). La IA lo reescribe con el MCP y la web lo pinta al momento.
"""
import json, math, threading, time
from collections import deque
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
UI_FILE = HERE / "ui_layout.json"
MEMORY_FILE = HERE / "ia_memoria.md"
DEFAULT_PLAN = {"main_ecu": "7A", "main_lids": ["A0", "A1", "A2"], "period_ms": 250,
                "others": [], "other_every_s": 60, "dtc_every_s": 60, "init": "fast"}
WIDGETS = ("value", "gauge", "chart", "bits", "table", "text", "dtc", "events", "request", "raw")


# ---------------------------------------------------------------- estadística en línea
class Stat:
    __slots__ = ("n", "mean", "m2", "lo", "hi", "last", "changes", "quiet_since")

    def __init__(self):
        self.n, self.mean, self.m2, self.lo, self.hi, self.last, self.changes = 0, 0.0, 0.0, None, None, None, 0
        self.quiet_since = None

    def add(self, x, t):
        self.n += 1
        d = x - self.mean
        self.mean += d / self.n
        self.m2 += d * (x - self.mean)
        self.lo = x if self.lo is None else min(self.lo, x)
        self.hi = x if self.hi is None else max(self.hi, x)
        if self.last is not None and x != self.last:
            self.changes += 1
        self.last = x

    @property
    def sd(self):
        return math.sqrt(self.m2 / (self.n - 1)) if self.n > 1 else 0.0

    def to(self):
        return {"n": self.n, "media": round(self.mean, 3), "sd": round(self.sd, 3), "min": self.lo, "max": self.hi,
                "ultimo": self.last, "cambios": self.changes}


def channels(data, decoded):
    """Canales de una respuesta: b<i> (byte), u<i> (u16 little endian i,i+1) y las variables decodificadas."""
    out = {f"b{i}": v for i, v in enumerate(data)}
    out.update({f"u{i}": data[i] | data[i + 1] << 8 for i in range(len(data) - 1)})
    for d in decoded:
        try:
            out["v:" + d["name"]] = float(d["value"])
        except (TypeError, ValueError):
            pass
    return out


# ---------------------------------------------------------------- registro continuo
class Drive:
    def __init__(self, web):
        self.web = web                       # módulo clio_web (request, select, read_lid, state, LOGS)
        self.plan = dict(DEFAULT_PLAN)
        self.auto = None                     # {"backend","address","baud"} para reconectar solo
        self.stop_ev = threading.Event()
        self.thread = None
        self.file = None
        self.buf = deque(maxlen=6000)        # (t, ecu, lid, bytes, {canal: valor})
        self.latest = {}                     # "ECU:LID" -> {"t","bytes","decoded"}
        self.stats = {}                      # "ECU:LID:canal" -> Stat
        self.events = deque(maxlen=500)
        self.dtc_seen = {}
        self.err_streak = 0
        self.n = 0
        self.state = "parado"
        self.lock = threading.Lock()

    # --- eventos
    def event(self, kind, text, **extra):
        ev = dict(t=time.time(), kind=kind, text=text, **extra)
        self.events.append(ev)
        with open(self.web.LOGS / "events.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev

    # --- detección de anomalías por canal
    def check(self, key, ch, x, t):
        st = self.stats.get(key)
        if st is None:
            st = self.stats[key] = Stat()
        if st.n >= 200:
            if st.lo == st.hi and x != st.lo and ch.startswith("b"):
                self.event("descubrimiento", f"{key} estaba fijo en {st.lo} y ahora vale {x}", key=key, value=x)
            elif st.sd > 0 and abs(x - st.mean) > 6 * st.sd and not (st.lo <= x <= st.hi):
                if ch.startswith("v:"):
                    self.event("anomalia", f"{key} = {x} fuera de lo visto ({st.lo}..{st.hi}, media {st.mean:.1f})",
                               key=key, value=x)
        st.add(x, t)

    def sample(self, ecu, lid, r, t):
        if not r.startswith("61" + lid):
            self.err_streak += 1
            if self.err_streak == 10:
                self.event("comunicacion", f"10 lecturas seguidas sin respuesta ({ecu} 21{lid}: {r[:40]})")
            return None
        self.err_streak = 0
        data = bytes.fromhex(r[4:])
        decoded = self.web.decode_all(lid, data, r)
        chs = channels(data, decoded)
        with self.lock:
            self.latest[f"{ecu}:{lid}"] = {"t": t, "bytes": list(data), "decoded": decoded}
            self.buf.append((t, ecu, lid, data, chs))
            for ch, x in chs.items():
                self.check(f"{ecu}:{lid}:{ch}", ch, x, t)
        self.n += 1
        return {d["name"]: d["value"] for d in decoded}

    def read_dtc(self, ecu, f):
        for svc in ("17", "18"):
            try:
                d = self.web.parse_dtc(self.web.request(svc + "FF00", log_it=False))
            except Exception as e:
                d = {"error": str(e)}
            f.write(json.dumps({"t": time.time(), "ecu": ecu, "dtc": svc, "d": d}, ensure_ascii=False) + "\n")
            for x in d.get("dtc", []):
                k = f"{ecu}:{x['code']}"
                if k not in self.dtc_seen:
                    self.dtc_seen[k] = x
                    self.event("averia", f"Avería {x['code']} en {ecu} (estado {x['status']}) {x.get('name', '')}",
                               ecu=ecu, code=x["code"])

    # --- bucle
    def ensure_link(self):
        w = self.web
        if w.state["b"]:
            return True
        if not self.auto:
            self.state = "sin conexión (conecta desde la web o arranca con --auto)"
            return False
        try:
            self.state = f"conectando {self.auto['backend']} {self.auto.get('address', '')}"
            w.api("/api/connect", {}, dict(self.auto, ecu=self.plan["main_ecu"], init=self.plan["init"]))
            ok = w.state["b"] is not None
            if ok:
                self.event("conexion", f"conectado ({self.auto['backend']})")
            return ok
        except Exception as e:
            self.state = f"reintentando: {e}"
            w.state["b"] = None
            return False

    def run(self):
        w, p = self.web, self.plan
        self.file = w.LOGS / f"drive_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
        last_other = last_dtc = 0.0
        with open(self.file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.time(), "plan": p}) + "\n")
            while not self.stop_ev.is_set():
                if not self.ensure_link():
                    self.stop_ev.wait(5)
                    continue
                if w.state["ecu"] != p["main_ecu"]:
                    ok, _ = w.select(p["main_ecu"], p["init"])
                    if not ok:
                        self.state = f"la UCE {p['main_ecu']} no responde (¿contacto quitado?)"
                        self.err_streak += 1
                        if self.err_streak > 3:
                            w.state["b"].close() if w.state["b"] else None
                            w.state["b"] = None
                        self.stop_ev.wait(3)
                        continue
                self.state = "registrando"
                t0 = time.time()
                for lid in p["main_lids"]:
                    try:
                        r = w.request("21" + lid, log_it=False)
                    except Exception as e:
                        r = f"ERR {e}"
                    v = self.sample(p["main_ecu"], lid, r, time.time())
                    f.write(json.dumps({"t": time.time(), "ecu": p["main_ecu"], "lid": lid, "r": r, "v": v},
                                       ensure_ascii=False) + "\n")
                if self.err_streak >= 20:      # la UCE dejó de contestar: nuevo init en la siguiente vuelta
                    w.state["ecu"] = ""
                    self.stop_ev.wait(2)
                    continue
                if time.time() - last_dtc > p["dtc_every_s"]:
                    last_dtc = time.time()
                    self.read_dtc(p["main_ecu"], f)
                if p["others"] and time.time() - last_other > p["other_every_s"]:
                    last_other = time.time()
                    for o in p["others"]:
                        self.state = f"visitando {o['ecu']}"
                        ok, _ = w.select(o["ecu"], p["init"])
                        if ok:
                            for lid in o.get("lids", []):
                                try:
                                    r = w.request("21" + lid, log_it=False)
                                except Exception as e:
                                    r = f"ERR {e}"
                                v = self.sample(o["ecu"], lid, r, time.time())
                                f.write(json.dumps({"t": time.time(), "ecu": o["ecu"], "lid": lid, "r": r, "v": v},
                                                   ensure_ascii=False) + "\n")
                            if o.get("dtc"):
                                self.read_dtc(o["ecu"], f)
                    w.select(p["main_ecu"], p["init"])
                f.flush()
                self.stop_ev.wait(max(0.0, p["period_ms"] / 1000 - (time.time() - t0)))
        self.state = "parado"

    def start(self, plan=None, auto=None):
        if self.thread and self.thread.is_alive():
            raise RuntimeError("el registro ya está en marcha")
        if plan:
            self.plan.update({k: v for k, v in plan.items() if k in DEFAULT_PLAN})
            self.plan["main_lids"] = [l.upper() for l in self.plan["main_lids"]]
        if auto:
            self.auto = auto
        self.stop_ev.clear()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        return {"ok": True, "file": self.file.name if self.file else None, "plan": self.plan}

    def stop(self):
        self.stop_ev.set()
        return {"ok": True, "file": self.file.name if self.file else None, "samples": self.n}

    def status(self):
        return {"running": bool(self.thread and self.thread.is_alive()), "state": self.state, "samples": self.n,
                "file": self.file.name if self.file else None, "plan": self.plan, "auto": self.auto,
                "events": len(self.events), "channels": len(self.stats)}

    # --- consultas para la web y la IA
    def resolve(self, key):
        """'7A:A1:rpm' (variable), '7A:A1:b3', '7A:A1:u3' o '7A:A1:b5.2' (bit) -> valor actual."""
        ecu, lid, ch = key.split(":", 2)
        cur = self.latest.get(f"{ecu.upper()}:{lid.upper()}")
        if not cur:
            return None
        return value_of(ch, cur["bytes"], {d["name"]: d["value"] for d in cur["decoded"]})

    def series(self, key, n=300):
        ecu, lid, ch = key.split(":", 2)
        ecu, lid = ecu.upper(), lid.upper()
        out = []
        with self.lock:
            for t, e, l, data, chs in list(self.buf)[::-1]:
                if e == ecu and l == lid:
                    v = value_of(ch, list(data), {k[2:]: x for k, x in chs.items() if k.startswith("v:")})
                    if v is not None:
                        out.append([round(t, 2), v])
                    if len(out) >= n:
                        break
        return out[::-1]

    def summary(self, top=40):
        """Resumen para la IA: canales que varían, con estadística."""
        with self.lock:
            items = [(k, s) for k, s in self.stats.items() if s.lo != s.hi]
        items.sort(key=lambda ks: -ks[1].changes)
        return {"canales_que_varian": {k: s.to() for k, s in items[:top]}, "total_canales": len(self.stats),
                "ultimos": {k: {"bytes": v["bytes"], "decoded": v["decoded"]} for k, v in self.latest.items()}}


def value_of(ch, data, named):
    try:
        if ch.startswith("b") and "." in ch:
            i, bit = ch[1:].split(".")
            return (data[int(i)] >> int(bit)) & 1
        if ch.startswith("b") and ch[1:].isdigit():
            return data[int(ch[1:])]
        if ch.startswith("u") and ch[1:].isdigit():
            i = int(ch[1:])
            return data[i] | data[i + 1] << 8
    except (IndexError, ValueError):
        return None
    return named.get(ch)


# ---------------------------------------------------------------- descubrimiento sobre un registro
def corr(a, b):
    n = len(a)
    if n < 10:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va == 0 or vb == 0:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def analyze_drive(fn, max_channels=60):
    """Canales que varían, contadores, bits que conmutan y grupos que se mueven juntos."""
    rows = {}
    for line in open(fn, encoding="utf-8"):
        d = json.loads(line)
        if "lid" in d and str(d.get("r", "")).startswith("61" + d["lid"]):
            rows.setdefault(f"{d['ecu']}:{d['lid']}", []).append((d["t"], bytes.fromhex(d["r"][4:]), d.get("v") or {}))
    if not rows:
        return {"error": "registro sin datos válidos"}
    out = {"archivo": Path(fn).name, "lids": {}, "parejas_correlacionadas": [], "bits": []}
    series = {}
    for key, rs in rows.items():
        n = min(len(b) for _, b, _ in rs)
        info = {"muestras": len(rs), "duracion_s": round(rs[-1][0] - rs[0][0], 1), "canales": {}}
        for i in range(n):
            vals = [b[i] for _, b, _ in rs]
            if len(set(vals)) == 1:
                continue
            steps = [(y - x) & 0xFF for x, y in zip(vals, vals[1:])]
            kind = "contador" if all(s in (0, 1) for s in steps) and sum(steps) > 0.7 * len(steps) else "variable"
            info["canales"][f"b{i}"] = {"tipo": kind, "min": min(vals), "max": max(vals), "distintos": len(set(vals))}
            if kind == "variable":
                series[f"{key}:b{i}"] = vals
            if len(set(vals)) == 2 or all(v in (0, 1, 2, 4, 8, 16, 32, 64, 128) for v in set(vals)):
                for bit in range(8):
                    bv = [(v >> bit) & 1 for v in vals]
                    flips = [rs[j][0] for j in range(1, len(bv)) if bv[j] != bv[j - 1]]
                    if 0 < len(flips) < len(bv) // 3:
                        out["bits"].append({"canal": f"{key}:b{i}.{bit}", "conmutaciones": len(flips),
                                            "primeros_cambios_t": [round(x, 1) for x in flips[:6]]})
        for i in range(n - 1):
            u = [b[i] | b[i + 1] << 8 for _, b, _ in rs]
            if len(set(u)) > 20 and f"b{i}" in info["canales"] and f"b{i + 1}" in info["canales"]:
                info["canales"][f"u{i}"] = {"tipo": "u16le", "min": min(u), "max": max(u)}
                series[f"{key}:u{i}"] = u
        for name in {k for _, _, v in rs for k in v}:
            vals = [v.get(name) for _, _, v in rs]
            if all(isinstance(x, (int, float)) for x in vals) and len(set(vals)) > 1:
                series[f"{key}:{name}"] = vals
                info["canales"][name] = {"tipo": "decodificada", "min": min(vals), "max": max(vals)}
        out["lids"][key] = info
    keys = sorted(series, key=lambda k: -len(set(series[k])))[:max_channels]
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if a.split(":")[:2] != b.split(":")[:2]:
                continue  # misma respuesta: mismas muestras alineadas
            if a.rsplit(":", 1)[1][1:].isdigit() and b.rsplit(":", 1)[1][1:].isdigit():
                ia, ib = int(a.rsplit(":", 1)[1][1:]), int(b.rsplit(":", 1)[1][1:])
                if abs(ia - ib) <= 1:
                    continue  # el u16 y sus propios bytes
            m = min(len(series[a]), len(series[b]))
            r = corr(series[a][:m], series[b][:m])
            if abs(r) > 0.85:
                out["parejas_correlacionadas"].append({"a": a, "b": b, "r": round(r, 3)})
    out["parejas_correlacionadas"].sort(key=lambda x: -abs(x["r"]))
    out["parejas_correlacionadas"] = out["parejas_correlacionadas"][:40]
    out["bits"] = out["bits"][:60]
    return out


# ---------------------------------------------------------------- paneles (los diseña la IA)
DEFAULT_UI = {
    "_ayuda": ("Páginas y widgets que pinta la pestaña 'Panel'. Claves: '7A:A1:rpm' (variable aprendida o DDT), "
               "'7A:A1:b3' (byte), '7A:A1:u3' (u16 little endian), '7A:A1:b5.2' (bit). Tipos: " + ", ".join(WIDGETS) +
               ". 'request' = petición de la base DDT: si es de lectura se puede leer; si es de escritura solo se "
               "muestra cómo cambiarla a mano con DDT4ALL (nunca se escribe desde aquí)."),
    "pages": [
        {"id": "conduccion", "title": "Conducción", "widgets": [
            {"type": "text", "title": "Primeros pasos",
             "text": "Arranca el registro (Modo coche). La IA irá añadiendo aquí lo que descubra."},
            {"type": "chart", "title": "A1 byte 0-1 (u16)", "key": "7A:A1:u0"},
            {"type": "events", "title": "Eventos"},
            {"type": "dtc", "title": "Averías"}]},
        {"id": "bytes", "title": "Bytes", "widgets": [
            {"type": "raw", "title": "A0", "key": "7A:A0"}, {"type": "raw", "title": "A1", "key": "7A:A1"},
            {"type": "raw", "title": "A2", "key": "7A:A2"}]}]}


def ui_get():
    try:
        return json.loads(UI_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return json.loads(json.dumps(DEFAULT_UI))


def ui_validate(ui):
    if not isinstance(ui, dict) or not isinstance(ui.get("pages"), list):
        raise ValueError("el panel necesita {'pages': [...]}")
    for p in ui["pages"]:
        if not p.get("id") or not isinstance(p.get("widgets", []), list):
            raise ValueError("cada página necesita id y widgets")
        for wd in p["widgets"]:
            if wd.get("type") not in WIDGETS:
                raise ValueError(f"tipo de widget desconocido: {wd.get('type')} (válidos: {', '.join(WIDGETS)})")
    return ui


def ui_save(ui):
    ui_validate(ui)
    old = UI_FILE.with_suffix(".prev.json")
    if UI_FILE.exists():
        old.write_text(UI_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    UI_FILE.write_text(json.dumps(ui, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "pages": [p["id"] for p in ui["pages"]]}


def ui_page(page):
    """Crea o sustituye una página entera."""
    ui = ui_get()
    ui["pages"] = [p for p in ui["pages"] if p["id"] != page["id"]] + [page]
    return ui_save(ui)


# ---------------------------------------------------------------- memoria de la IA
def memory_get():
    try:
        return MEMORY_FILE.read_text(encoding="utf-8")
    except OSError:
        return "# Memoria de la IA (Clio)\n\nAquí la IA apunta lo que va aprendiendo del coche entre sesiones.\n"


def memory_add(text, section="Notas"):
    mem = memory_get().rstrip() + f"\n\n## {section} · {datetime.now():%Y-%m-%d %H:%M}\n{text.strip()}\n"
    MEMORY_FILE.write_text(mem, encoding="utf-8")
    return {"ok": True, "bytes": len(mem)}
