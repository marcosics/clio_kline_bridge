#!/usr/bin/env python3
"""
clio_kline.py - Escaner/logger KWP2000 por K-Line para Clio II 1.5 dCi (K9K 702, UCE Delphi)
Interfaz: cable ELM327 (USB tipo Renolink o Bluetooth emparejado como puerto COM).
SOLO LECTURA: usa 10 C0 (sesion), 3E (tester present), 21 xx (lectura por LID). Nunca escribe.

Uso:
  pip install pyserial
  python clio_kline.py --port COM5 probe                # identifica el cable (ATI/STI, baudios); no toca la UCE
  python clio_kline.py --port COM5 info
  python clio_kline.py --port COM5 scan                 # barre LIDs 21 01..FF -> scan_*.json
  python clio_kline.py --port COM5 log 01 02 03         # registra LIDs en bucle -> log_*.csv
  python clio_kline.py --port COM5 learn 01 02 03       # detecta que bytes cambian con una accion
  python clio_kline.py --port COM5 raw                  # consola manual
Opciones: --baud 38400 (USB) | --ecu 7A (inyeccion) | --secs 8 (duracion de cada fase en learn)
Sube los .json/.csv al chat para analizarlos.
"""
import argparse, csv, json, sys, time
from datetime import datetime
import serial

ECU_NAMES = {"7A": "Inyeccion", "28": "ABS", "26": "UCH", "2C": "Airbag", "51": "Cuadro"}


class Elm:
    def __init__(self, port, baud):
        self.s = serial.Serial(port, baud, timeout=0.1)

    def cmd(self, c, timeout=3.0):
        self.s.reset_input_buffer()
        self.s.write((c + "\r").encode())
        buf, t0 = b"", time.time()
        while time.time() - t0 < timeout:
            buf += self.s.read(256)
            if buf.endswith(b">"):
                break
        txt = buf.decode(errors="ignore").replace(">", "").strip()
        return [l.strip() for l in txt.splitlines() if l.strip() and l.strip() != c]

    def init(self, ecu):
        print("ELM:", self.cmd("ATZ", 5))
        for c in ["ATE0", "ATL0", "ATS1", "ATH0", "ATAT1", "ATSP5",
                  f"ATSH81{ecu}F1", f"ATWM81{ecu}F13E", "ATST96"]:
            self.cmd(c)
        r = self.cmd("ATFI", 6)
        print("Fast init:", r)
        r = self.cmd("10C0", 4)
        print("Sesion 10C0:", r)
        if not any(l.replace(" ", "").startswith("50") for l in r):
            print("AVISO: la UCE no acepto 10C0; prueba contacto ON, motor parado, o --ecu distinto.")
        return r

    def read_lid(self, lid):
        r = self.cmd(f"21{lid}", 2)
        data = "".join(l.replace(" ", "") for l in r)
        if data.startswith("61" + lid.upper()):
            return bytes.fromhex(data[4:])
        return None, " ".join(r)


def ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def do_scan(e):
    out = {}
    for i in range(1, 256):
        lid = f"{i:02X}"
        r = e.read_lid(lid)
        if isinstance(r, bytes):
            out[lid] = r.hex(" ").upper()
            print(f"21{lid} -> {len(r)} bytes: {out[lid]}")
        if i % 20 == 0:
            e.cmd("3E")
    fn = f"scan_{ts()}.json"
    json.dump(out, open(fn, "w"), indent=1)
    print(f"\n{len(out)} LIDs con respuesta -> {fn}")


def poll(e, lids, secs, writer=None):
    samples, t0 = {l: [] for l in lids}, time.time()
    while time.time() - t0 < secs:
        for l in lids:
            r = e.read_lid(l)
            if isinstance(r, bytes):
                samples[l].append(r)
                if writer:
                    writer.writerow([f"{time.time()-t0:.2f}", l, r.hex(" ").upper()])
    return samples


def do_log(e, lids):
    fn = f"log_{ts()}.csv"
    with open(fn, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "lid", "bytes"])
        print(f"Registrando {lids} en {fn}. Ctrl+C para parar.")
        try:
            while True:
                poll(e, lids, 5, w)
                f.flush()
        except KeyboardInterrupt:
            print("Parado.")


def diff(base, act):
    hits = []
    for lid in base:
        if not base[lid] or not act[lid]:
            continue
        n = min(len(base[lid][0]), len(act[lid][0]))
        for i in range(n):
            vb = {s[i] for s in base[lid] if len(s) > i}
            va = {s[i] for s in act[lid] if len(s) > i}
            if vb.isdisjoint(va):
                bits = [b for b in range(8) if all(((x >> b) & 1) != ((y >> b) & 1) for x in vb for y in va)]
                hits.append({"lid": lid, "byte": i, "reposo": sorted(f"{v:02X}" for v in vb),
                             "accion": sorted(f"{v:02X}" for v in va), "bits": bits})
    return hits


def do_learn(e, lids, secs):
    results = []
    while True:
        name = input("\nNombre de la entrada a aprender (ej. embrague, freno, marcha_atras) o Enter para salir: ").strip()
        if not name:
            break
        input(f"Deja '{name}' en REPOSO y pulsa Enter ({secs}s)...")
        b = poll(e, lids, secs)
        input(f"ACTIVA '{name}' (mantenlo) y pulsa Enter ({secs}s)...")
        a = poll(e, lids, secs)
        h = diff(b, a)
        print(f"  -> {len(h)} candidatos" + "".join(f"\n     21{x['lid']} byte {x['byte']}: {x['reposo']} -> {x['accion']} bits {x['bits']}" for x in h))
        if not h:
            print("     Sin cambios: la UCE probablemente no lee esta senal.")
        results.append({"entrada": name, "candidatos": h})
    fn = f"learn_{ts()}.json"
    json.dump(results, open(fn, "w"), indent=1)
    print(f"Guardado -> {fn}")


def do_raw(e):
    print("Consola. Escribe comandos (21xx, AT...). 'q' para salir. Bloqueados: servicios de escritura.")
    while True:
        c = input("> ").strip().replace(" ", "").upper()
        if c == "Q":
            break
        if c[:2] in ("2E", "3B", "31", "14", "27", "34", "36", "11") and not c.startswith("AT"):
            print("Bloqueado (escritura/borrado/reset).")
            continue
        print(e.cmd(c, 4))


def do_probe(port):
    """Identifica el cable: prueba baudios y pregunta ATI/STI (STN = OBDLink real)."""
    for baud in (38400, 115200, 9600, 230400, 500000):
        try:
            e = Elm(port, baud)
        except serial.SerialException as ex:
            print("No se pudo abrir", port, ex)
            return
        r = e.cmd("ATI", 2)
        if any("ELM" in l or "STN" in l or "OBD" in l for l in r):
            print(f"Responde a {baud} baudios: {r}")
            for c in ("ATZ", "ATI", "AT@1", "STI", "STDI", "ATRV", "ATDP"):
                print(f"  {c:5} -> {e.cmd(c, 5)}")
            print("STI con respuesta = chip STN (OBDLink real). '?' en STI = clon ELM327.")
            return
        e.s.close()
    print("Sin respuesta en ningun baudio. Revisa el puerto COM y el driver (FTDI/CH340).")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", required=True)
    p.add_argument("--baud", type=int, default=38400)
    p.add_argument("--ecu", default="7A")
    p.add_argument("--secs", type=float, default=8)
    p.add_argument("mode", choices=["probe", "info", "scan", "log", "learn", "raw"])
    p.add_argument("lids", nargs="*")
    a = p.parse_args()
    if a.mode == "probe":
        return do_probe(a.port)
    lids = [l.upper().zfill(2) for l in a.lids]
    e = Elm(a.port, a.baud)
    print(f"UCE {a.ecu} ({ECU_NAMES.get(a.ecu.upper(), '?')})")
    e.init(a.ecu)
    if a.mode == "scan":
        do_scan(e)
    elif a.mode == "log":
        do_log(e, lids or ["01"])
    elif a.mode == "learn":
        do_learn(e, lids or ["01"], a.secs)
    elif a.mode == "raw":
        do_raw(e)


if __name__ == "__main__":
    sys.exit(main())
