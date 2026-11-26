"""
ddt_db.py - Lee la base de DDT4ALL (ecu.zip generado con `ddt4all -z` desde DDT2000, o JSON sueltos) y decodifica
respuestas igual que DDT4ALL (src/ddt4all/core/ecu/ecu_data.py, getHexValue/getDisplayValue).
Coloca ecu.zip o los *.json en <proyecto>/ddt/. La base no es publica: viene de tu instalacion de DDT2000/DDT4ALL.
"""
import json, math, zipfile
from pathlib import Path

DDT_DIR = Path(__file__).resolve().parent.parent / "ddt"


def _signed(v, nbytes):
    return -(v & 0x80) | (v & 0x7F) if nbytes == 1 else -(v & 0x8000) | (v & 0x7FFF) if nbytes == 2 else v


def hex_value(resp, ref, data, ecu_endian):
    """resp = respuesta completa en hex incluyendo el SID (61..). firstbyte es 1-based sobre esa respuesta."""
    le = ref.get("endian") == "Little" or (ecu_endian == "Little" and ref.get("endian") != "Big")
    bits, start_bit, sb = data.get("bitscount", 8), ref.get("bitoffset", 0), ref.get("firstbyte", 0) - 1
    nbytes, span = math.ceil(bits / 8), math.ceil((bits + start_bit) / 8)
    rb = bytes.fromhex(resp)
    if sb < 0 or sb + span > len(rb):
        return None
    chunk = rb[sb:sb + span]
    if le:
        v = (int.from_bytes(chunk, "big") >> start_bit) & ((1 << bits) - 1)
        return v.to_bytes(nbytes, "big")[::-1].hex().upper()
    binstr = "".join(f"{b:08b}" for b in chunk)
    return f"{int(binstr[start_bit:start_bit + bits], 2):0{nbytes * 2}X}"


def display_value(resp, ref, data, ecu_endian):
    h = hex_value(resp, ref, data, ecu_endian)
    if h is None:
        return None
    if data.get("bytesascii"):
        return bytes.fromhex(h).decode("utf-8", errors="ignore")
    v = int(h, 16)
    if data.get("signed"):
        v = _signed(v, data.get("bytescount", 1))
    if not data.get("scaled"):
        return data.get("lists", {}).get(str(v), h)
    div = float(data.get("divideby", 1))
    if div == 0:
        return None
    res = (v * float(data.get("step", 1)) + float(data.get("offset", 0))) / div
    fmt = data.get("format", "")
    if "." in fmt:
        return f"{res:.{len(fmt.split('.')[1])}f}"
    return str(int(res)) if int(res) == res else str(res)


def parse_ident(resp):
    """2180 -> campos que usa DDT4ALL para elegir el archivo de la UCE (ecu_scanner.check_ecu)."""
    r = bytes.fromhex(resp)
    if len(r) >= 20:
        return {"diagversion": str(r[7]), "supplier": r[8:12].decode(errors="ignore"),
                "soft": r[16:18].hex().upper(), "version": r[18:20].hex().upper()}
    if len(r) >= 15:
        return {"diagversion": str(r[2]), "supplier": r[3:7].decode(errors="ignore"),
                "soft": r[7:11].hex().upper(), "version": r[11:15].hex().upper()}
    return None


class Db:
    def __init__(self, folder=DDT_DIR):
        self.folder, self.zip, self.index, self.ecu, self.file, self.endian_override = folder, None, {}, None, None, ""
        z = folder / "ecu.zip"
        if z.exists():
            self.zip = zipfile.ZipFile(z)
            self.index = json.loads(self.zip.read("db.json"))
        for p in folder.glob("*.json"):
            self.index.setdefault(p.name, {"address": "", "ecuname": p.stem, "autoidents": []})

    def _read(self, name):
        p = self.folder / name
        return json.loads(p.read_text(encoding="utf-8") if p.exists() else self.zip.read(name))

    def candidates(self, addr, ident=None):
        """Archivos de la base para una direccion; con ident, ordenados como DDT4ALL (exacto, luego version cercana)."""
        out = []
        for f, e in self.index.items():
            if e.get("address", "").upper() not in (addr.upper(), ""):
                continue
            score = 0
            for a in e.get("autoidents", []) if ident else []:
                same = a.get("supplier", "").strip() == ident["supplier"].strip() and \
                       a.get("soft", "").strip() == ident["soft"].strip()
                if same and a.get("version", "").strip() == ident["version"].strip():
                    score = max(score, 100000)
                elif same:
                    try:
                        score = max(score, 50000 - abs(int(a["version"], 16) - int(ident["version"], 16)))
                    except ValueError:
                        score = max(score, 1)
            out.append({"file": f, "ecuname": e.get("ecuname", ""), "projects": e.get("projects", []), "score": score})
        return sorted(out, key=lambda c: -c["score"])

    def load(self, file, endian_override=""):
        self.ecu, self.file, self.endian_override = self._read(file), file, endian_override
        return self.status()

    def status(self):
        return {"folder": str(self.folder), "zip": bool(self.zip), "files": len(self.index), "loaded": self.file,
                "endian": self.endian(), "requests": len(self.requests()), "data": len((self.ecu or {}).get("data", {}))}

    def endian(self):
        return self.endian_override or (self.ecu or {}).get("endian", "Big")

    def requests(self):
        return self.ecu["requests"] if self.ecu else []

    def request(self, name):
        return next((r for r in self.requests() if r["name"] == name), None)

    def by_sent(self, sent):
        return next((r for r in self.requests() if r.get("sentbytes", "").upper() == sent.upper()), None)

    def search(self, text):
        t = text.lower()
        return {"requests": [{"name": r["name"], "sent": r.get("sentbytes")} for r in self.requests()
                             if t in r["name"].lower() or any(t in d.lower() for d in r.get("receivebyte_dataitems", {}))],
                "data": [{"name": k, **{x: v for x, v in d.items() if x in ("unit", "comment", "lists")}}
                         for k, d in (self.ecu or {}).get("data", {}).items() if t in k.lower()]}

    def decode_request(self, req, resp):
        out = []
        for name, ref in req.get("receivebyte_dataitems", {}).items():
            d = self.ecu["data"].get(name, {})
            r = dict(ref, endian=self.endian_override or ref.get("endian", ""))  # DDCR: forzar Little (CLAUDE.md sec. 5)
            out.append({"name": name, "value": display_value(resp, r, d, self.endian()), "unit": d.get("unit", ""),
                        "byte": ref.get("firstbyte", 0) - 3, "bit": ref.get("bitoffset", 0), "bits": d.get("bitscount", 8)})
        return out
