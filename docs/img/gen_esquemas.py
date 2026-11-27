"""Genera los dibujos estilo Fritzing del puente ESP-01 + LM339N (docs/img/*.svg).
python docs/img/gen_esquemas.py  (después: node docs/img/render.js para PNG y PDF)
"""
import math, os

OUT = os.path.dirname(os.path.abspath(__file__))
P = 20  # paso de la protoboard (0,1")

COL = {"12V": "#d62828", "3V3": "#f77f00", "GND": "#222222", "K": "#e9c46a", "KD": "#2a9d8f",
       "RX": "#2a9d8f", "TX": "#1d4ed8", "G2": "#7b2cbf", "REF": "#8d99ae", "PU": "#f4a261", "TXN": "#60a5fa"}
BANDS = {"0": "#000", "1": "#7a4a1d", "2": "#d00", "3": "#f80", "4": "#ee0", "5": "#0a0", "6": "#05c",
         "7": "#90c", "8": "#888", "9": "#fff"}
RES = {"1k": "102", "10k": "103", "47k": "473", "68k": "683"}  # 2 cifras + multiplicador


class Svg:
    def __init__(s, w, h, title):
        s.w, s.h, s.o = w, h, []
        s.o.append(f'<rect width="{w}" height="{h}" fill="#fff"/>')
        s.text(w / 2, 32, title, 22, anchor="middle", weight="bold")

    def add(s, x):
        s.o.append(x)

    def text(s, x, y, t, size=12, color="#222", anchor="start", weight="normal", rot=0):
        tr = f' transform="rotate({rot} {x} {y})"' if rot else ""
        t = t.replace("&", "&amp;").replace("<", "&lt;")
        s.o.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" '
                   f'fill="{color}" text-anchor="{anchor}" font-weight="{weight}"{tr}>{t}</text>')

    def save(s, name):
        body = "\n".join(s.o)
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(f'<svg xmlns="http://www.w3.org/2000/svg" width="{s.w}" height="{s.h}" '
                    f'viewBox="0 0 {s.w} {s.h}">\n{body}\n</svg>\n')


def wire(s, pts, color, w=5, arc=0):
    """Cable: lista de puntos; arc>0 curva un tramo de 2 puntos (puente)."""
    if len(pts) == 2 and arc:
        (x1, y1), (x2, y2) = pts
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        d = math.hypot(x2 - x1, y2 - y1)
        nx, ny = -(y2 - y1) / d, (x2 - x1) / d
        if ny > 0:
            nx, ny = -nx, -ny
        c = (mx + nx * arc, my + ny * arc)
        path = f"M{x1},{y1} Q{c[0]:.1f},{c[1]:.1f} {x2},{y2}"
    else:
        path = "M" + " L".join(f"{x},{y}" for x, y in pts)
    s.add(f'<path d="{path}" fill="none" stroke="#000" stroke-opacity=".35" stroke-width="{w + 2}" '
          f'stroke-linecap="round" stroke-linejoin="round"/>')
    s.add(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linecap="round" '
          f'stroke-linejoin="round"/>')
    for x, y in (pts[0], pts[-1]):
        s.add(f'<rect x="{x - 4}" y="{y - 4}" width="8" height="8" rx="1.5" fill="#555" stroke="#222"/>')


def leads(s, p1, p2):
    s.add(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="#9a9a9a" stroke-width="2.5"/>')
    for x, y in (p1, p2):
        s.add(f'<circle cx="{x}" cy="{y}" r="3" fill="#777"/>')


def body(s, p1, p2, inner, length=40, thick=13):
    (x1, y1), (x2, y2) = p1, p2
    ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    s.add(f'<g transform="translate({cx:.1f} {cy:.1f}) rotate({ang:.1f})">{inner(length, thick)}</g>')
    return cx, cy, ang


def resistor(s, p1, p2, val, label, lpos=(0, 0)):
    leads(s, p1, p2)
    code = RES[val]
    cols = [BANDS[code[0]], BANDS[code[1]], BANDS[code[2]], "#c9a227"]

    def inner(L, T):
        g = f'<rect x="{-L / 2}" y="{-T / 2}" width="{L}" height="{T}" rx="6" fill="#d9bf8c" stroke="#8a7350"/>'
        for i, c in enumerate(cols):
            x = -L / 2 + 8 + i * 7 + (4 if i == 3 else 0)
            g += f'<rect x="{x}" y="{-T / 2}" width="4" height="{T}" fill="{c}"/>'
        return g

    cx, cy, _ = body(s, p1, p2, inner)
    s.text(cx + lpos[0], cy + lpos[1], f"{label} {val}", 11, "#111", "middle", "bold")


def diode(s, pa, pk, kind, label, lpos=(0, 0)):
    leads(s, pa, pk)
    glass = kind == "1N4148"

    def inner(L, T):
        L, T = (30, 9) if glass else (36, 13)
        fill = "#f4a261" if glass else "#1b1b1b"
        band = "#111" if glass else "#cfcfcf"
        return (f'<rect x="{-L / 2}" y="{-T / 2}" width="{L}" height="{T}" rx="4" fill="{fill}" '
                f'fill-opacity="{0.85 if glass else 1}" stroke="#333"/>'
                f'<rect x="{L / 2 - 8}" y="{-T / 2}" width="4" height="{T}" fill="{band}"/>')

    cx, cy, _ = body(s, pa, pk, inner)
    s.text(cx + lpos[0], cy + lpos[1], f"{label} {kind}", 11, "#111", "middle", "bold")


def ceramic(s, p1, p2, label, lpos=(0, 0)):
    leads(s, p1, p2)
    cx, cy = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    s.add(f'<ellipse cx="{cx}" cy="{cy}" rx="9" ry="8" fill="#e9b949" stroke="#9c7a1e"/>')
    s.text(cx + lpos[0], cy + lpos[1], label, 11, "#111", "middle", "bold")


def electro(s, pplus, pminus, label, lpos=(0, 0)):
    leads(s, pplus, pminus)
    cx, cy = (pplus[0] + pminus[0]) / 2, (pplus[1] + pminus[1]) / 2
    s.add(f'<circle cx="{cx}" cy="{cy}" r="15" fill="#2b4c9b" stroke="#16295a" stroke-width="2"/>')
    # franja del negativo hacia el pin -
    ang = math.atan2(pminus[1] - pplus[1], pminus[0] - pplus[0])
    s.add(f'<path d="M{cx},{cy} L{cx + 15 * math.cos(ang - .7):.1f},{cy + 15 * math.sin(ang - .7):.1f} '
          f'A15,15 0 0 1 {cx + 15 * math.cos(ang + .7):.1f},{cy + 15 * math.sin(ang + .7):.1f} Z" fill="#cfd8ea"/>')
    s.text(cx, cy + 4, "+", 13, "#fff", "middle", "bold")
    s.text(cx + lpos[0], cy + lpos[1], label, 11, "#111", "middle", "bold")


# ---------------------------------------------------------------- protoboard
class Board:
    ROWS = {"T1": 20, "T2": 40, "a": 75, "b": 95, "c": 115, "d": 135, "e": 155,
            "f": 195, "g": 215, "h": 235, "i": 255, "j": 275, "B1": 310, "B2": 330}

    def __init__(s, svg, x, y, ncol=34):
        s.svg, s.x, s.y, s.n = svg, x, y, ncol
        w, h = 40 + (ncol - 1) * P + 30, 350
        svg.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#f1f1ee" stroke="#bdbdb5" '
                f'stroke-width="2"/>')
        svg.add(f'<rect x="{x + 6}" y="{y + 170}" width="{w - 12}" height="10" fill="#e2e2dc"/>')
        for r, yy, c in (("T1", 10, "#d62828"), ("T2", 50, "#1d4ed8"), ("B1", 300, "#1d4ed8"), ("B2", 340, "#d62828")):
            svg.add(f'<line x1="{x + 20}" y1="{y + yy}" x2="{x + w - 20}" y2="{y + yy}" stroke="{c}" stroke-width="2"/>')
        svg.text(x + 8, y + s.ROWS["T1"] + 4, "+", 14, "#d62828", weight="bold")
        svg.text(x + 8, y + s.ROWS["T2"] + 4, "−", 14, "#1d4ed8", weight="bold")
        svg.text(x + 8, y + s.ROWS["B1"] + 4, "−", 14, "#1d4ed8", weight="bold")
        svg.text(x + 8, y + s.ROWS["B2"] + 4, "+", 14, "#d62828", weight="bold")
        for r, yy in s.ROWS.items():
            for c in range(1, ncol + 1):
                if r in ("T1", "T2", "B1", "B2") and (c - 1) % 6 == 5:
                    continue
                hx, hy = s.p(c, r)
                svg.add(f'<rect x="{hx - 3}" y="{hy - 3}" width="6" height="6" rx="1" fill="#3a3a3a"/>')
            if len(r) == 1:
                svg.text(x + 14, y + yy + 4, r, 10, "#888", "middle")
        for c in range(1, ncol + 1):
            if c == 1 or c % 5 == 0:
                svg.text(s.p(c, "a")[0], y + 64, str(c), 9, "#888", "middle")
                svg.text(s.p(c, "j")[0], y + 292, str(c), 9, "#888", "middle")

    def p(s, c, r):
        return (s.x + 30 + (c - 1) * P, s.y + s.ROWS[r])


def lm339(s, b, c0):
    x1, x2 = b.p(c0, "e")[0] - 10, b.p(c0 + 6, "e")[0] + 10
    y1, y2 = b.p(c0, "e")[1] - 6, b.p(c0, "f")[1] + 6
    for i in range(7):
        for r in ("e", "f"):
            px, py = b.p(c0 + i, r)
            s.add(f'<rect x="{px - 4}" y="{py - 5}" width="8" height="10" fill="#c0c0c0" stroke="#777"/>')
    s.add(f'<rect x="{x1}" y="{y1 + 4}" width="{x2 - x1}" height="{y2 - y1 - 8}" rx="3" fill="#262626"/>')
    s.add(f'<path d="M{x1},{(y1 + y2) / 2 - 7} A7,7 0 0 1 {x1},{(y1 + y2) / 2 + 7}" fill="#555"/>')
    s.add(f'<circle cx="{x1 + 9}" cy="{y2 - 12}" r="2.5" fill="#777"/>')
    s.text((x1 + x2) / 2, (y1 + y2) / 2 + 5, "LM339N", 13, "#eee", "middle", "bold")
    for i in range(7):
        s.text(b.p(c0 + i, "f")[0], y2 - 7, str(i + 1), 8, "#bbb", "middle")
        s.text(b.p(c0 + i, "e")[0], y1 + 15, str(14 - i), 8, "#bbb", "middle")


def esp01(s, x, y, labels=True):
    """ESP-01 por el lado de los chips, antena a la DERECHA, tira 2x4 a la izquierda.
    Devuelve {pin: (x, y)}. Columna exterior (borde): VCC RST EN TX; interior: RX GPIO0 GPIO2 GND."""
    W, H = 190, 120
    s.add(f'<rect x="{x}" y="{y}" width="{W}" height="{H}" rx="5" fill="#1f2f6b" stroke="#0e1a44" stroke-width="2"/>')
    s.add(f'<path d="M{x + W - 12},{y + 22} h-26 v18 h18 v18 h-18 v18 h26" fill="none" stroke="#d4af37" stroke-width="4"/>')
    s.add(f'<rect x="{x + 88}" y="{y + 36}" width="46" height="46" fill="#9ca3af" stroke="#555"/>')
    s.text(x + 111, y + 63, "ESP8266", 9, "#222", "middle", "bold")
    s.add(f'<rect x="{x + 66}" y="{y + 44}" width="14" height="30" fill="#111"/>')
    if labels:
        s.text(x + W / 2, y - 10, "ESP-01 (lado de los chips, antena a la derecha)", 12, "#111", "middle", "bold")
    pins = {}
    rows = [("VCC", "RX"), ("RST", "GPIO0"), ("EN", "GPIO2"), ("TX", "GND")]
    for i, (o, n) in enumerate(rows):
        py = y + 18 + i * 28
        for name, px in ((o, x + 12), (n, x + 30)):
            s.add(f'<rect x="{px - 5}" y="{py - 5}" width="10" height="10" fill="#d4af37" stroke="#7a5f12"/>')
            pins[name] = (px, py)
        s.text(x + 40, py + 4, n, 10, "#fff", weight="bold")
        s.text(x + 4, py - 8, o, 9, "#ffd166", weight="bold")
    return pins


def protoboard():
    s = Svg(1300, 940, "Puente línea K: ESP-01 + LM339N en protoboard (vista estilo Fritzing)")
    b = Board(s, 300, 330, 36)
    lm339(s, b, 12)
    p = b.p

    def drop(pin, c, row, color, w=4, inner=False):
        """Cable desde un pin del ESP: sale a la izquierda, baja por un carril entre columnas y entra en (c, row)."""
        x0, y0 = pin
        pts = [pin]
        if inner:
            y0 += 13
            pts.append((x0, y0))
        lx = p(c, row)[0] + 10
        pts += [(lx, y0), (lx, p(c, row)[1]), p(c, row)]
        wire(s, pts, color, w)

    # carriles: arriba T1 = +3V3, T2 = GND ; abajo B1 = GND, B2 = +3V3
    wire(s, [p(1, "T1"), (p(1, "T1")[0] - 22, p(1, "T1")[1]), (p(1, "B2")[0] - 22, p(1, "B2")[1]), p(1, "B2")], COL["3V3"])
    wire(s, [p(2, "T2"), (p(2, "T2")[0] - 34, p(2, "T2")[1]), (p(2, "B1")[0] - 34, p(2, "B1")[1]), p(2, "B1")], COL["GND"])

    # +12P y pull-up de la K
    diode(s, p(2, "c"), p(5, "c"), "1N4007", "D1", (0, -12))
    resistor(s, p(5, "d"), p(9, "d"), "1k", "R10", (0, -10))
    # línea K: col 9 (arriba y abajo), salidas 14 (arriba) y 1 (abajo)
    wire(s, [p(9, "e"), p(9, "f")], COL["K"])
    wire(s, [p(12, "b"), p(9, "b")], COL["K"], arc=12)
    wire(s, [p(12, "i"), p(9, "i")], COL["K"], arc=12)
    # recepción
    resistor(s, p(9, "g"), p(16, "g"), "68k", "R1", (0, -10))
    resistor(s, p(16, "j"), p(16, "B1"), "10k", "R2", (24, 0))
    resistor(s, p(15, "j"), p(15, "B2"), "47k", "R3", (-4, 48))
    resistor(s, p(15, "h"), p(11, "h"), "10k", "R11", (-112, 4))
    wire(s, [p(11, "j"), p(11, "B1")], COL["GND"], w=4)
    resistor(s, p(13, "j"), p(13, "B2"), "10k", "R4", (-26, 48))
    wire(s, [p(14, "j"), p(14, "B2")], COL["3V3"], w=4)
    wire(s, [p(13, "i"), p(24, "i")], COL["RX"], w=4, arc=14)       # OUT1 -> columna RX
    wire(s, [p(24, "e"), p(24, "f")], COL["RX"], w=4)
    ceramic(s, p(26, "B1"), p(26, "B2"), "C3 100nF", (0, 32))
    # masa del chip y comparador 4
    wire(s, [p(14, "a"), p(14, "T2")], COL["GND"], w=4)
    wire(s, [p(15, "a"), p(15, "T2")], COL["GND"], w=4)
    # referencia TX 1,65 V: columna 19
    wire(s, [p(16, "b"), p(18, "b")], COL["REF"], w=4, arc=10)
    wire(s, [p(18, "c"), p(19, "c")], COL["REF"], w=4, arc=8)
    resistor(s, p(19, "b"), p(19, "T1"), "10k", "R5", (-26, 4))
    resistor(s, p(19, "d"), p(21, "d"), "10k", "R6", (-62, 4))
    wire(s, [p(21, "a"), p(21, "T2")], COL["GND"], w=4)
    wire(s, [p(19, "e"), p(19, "f")], COL["REF"], w=4)
    wire(s, [p(17, "h"), p(19, "h")], COL["REF"], w=4, arc=10)
    # nodo TX: columna 22
    wire(s, [p(17, "a"), p(22, "a")], COL["TXN"], w=4, arc=14)
    wire(s, [p(22, "e"), p(22, "f")], COL["TXN"], w=4)
    wire(s, [p(18, "j"), p(22, "j")], COL["TXN"], w=4, arc=12)
    resistor(s, p(30, "b"), p(22, "b"), "10k", "R7", (0, -10))
    diode(s, p(28, "d"), p(22, "d"), "1N4148", "D2", (0, -10))
    resistor(s, p(28, "c"), p(33, "c"), "10k", "R8", (8, 22))
    wire(s, [p(33, "a"), p(33, "T1")], COL["3V3"], w=4)
    electro(s, p(34, "T1"), p(35, "T2"), "C1 470µF", (0, -24))
    ceramic(s, p(36, "T1"), p(36, "T2"), "C2", (18, 4))

    # ESP-01: cada cable baja por su carril, sin cruzarse
    e = esp01(s, 1060, 110)
    drop(e["VCC"], 23, "T1", COL["3V3"])
    drop(e["RX"], 24, "a", COL["RX"], inner=True)
    drop(e["RST"], 25, "T1", COL["3V3"], 3)
    drop(e["GPIO0"], 26, "T1", COL["3V3"], 3, inner=True)
    drop(e["EN"], 27, "T1", COL["3V3"], 3)
    drop(e["GPIO2"], 28, "a", COL["G2"], inner=True)
    drop(e["TX"], 30, "a", COL["TX"])
    drop(e["GND"], 32, "T2", COL["GND"], inner=True)
    s.text(1155, 260, "RST, GPIO0 y EN van directos a +3,3 V", 11, "#444", "middle")

    # toma OBD y buck
    ox, oy = 40, 360
    s.add(f'<rect x="{ox}" y="{oy}" width="120" height="150" rx="10" fill="#333" stroke="#111" stroke-width="2"/>')
    s.text(ox + 60, oy - 10, "Toma OBD del coche", 12, "#111", "middle", "bold")
    obd = {}
    for i, (n, c, t) in enumerate((("16", COL["12V"], "+12 V"), ("7", COL["K"], "línea K"), ("5", COL["GND"], "masa"),
                                   ("4", COL["GND"], "masa"))):
        py = oy + 25 + i * 32
        s.add(f'<rect x="{ox + 96}" y="{py - 6}" width="22" height="12" fill="#d4af37"/>')
        s.text(ox + 14, py + 5, f"pin {n}", 13, "#fff", weight="bold")
        s.text(ox + 58, py + 5, t, 10, "#ddd")
        obd[n] = (ox + 118, py)
    fx = 190
    wire(s, [obd["16"], (fx, obd["16"][1])], COL["12V"])
    s.add(f'<rect x="{fx}" y="{obd["16"][1] - 9}" width="40" height="18" rx="4" fill="#f2c14e" stroke="#8a6d1a"/>')
    s.text(fx + 20, obd["16"][1] + 4, "F1 1A", 10, "#111", "middle", "bold")
    wire(s, [(fx + 40, obd["16"][1]), (250, obd["16"][1]), (250, p(2, "a")[1]), p(2, "a")], COL["12V"])
    wire(s, [obd["7"], (240, obd["7"][1]), (240, 290), (p(9, "a")[0], 290), p(9, "a")], COL["K"])
    wire(s, [obd["5"], (214, obd["5"][1]), (214, obd["4"][1])], COL["GND"])
    wire(s, [obd["4"], (214, obd["4"][1]), (214, p(3, "B1")[1]), p(3, "B1")], COL["GND"])
    bx, by = 40, 720
    s.add(f'<rect x="{bx}" y="{by}" width="170" height="80" rx="4" fill="#1e5aa8" stroke="#0f3463" stroke-width="2"/>')
    s.add(f'<rect x="{bx + 60}" y="{by + 20}" width="34" height="34" fill="#6b7280"/>')
    s.add(f'<circle cx="{bx + 125}" cy="{by + 38}" r="9" fill="#f2c14e" stroke="#444"/>')
    s.text(bx + 85, by - 8, "Buck MP1584 ajustado a 3,3 V", 12, "#111", "middle", "bold")
    bp = {"IN+": (bx + 10, by + 15), "IN-": (bx + 10, by + 65), "OUT+": (bx + 160, by + 15), "OUT-": (bx + 160, by + 65)}
    for n, (x, y) in bp.items():
        s.add(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="#d4af37"/>')
        s.text(x + (10 if n.startswith("IN") else -10), y + 4, n, 10, "#fff", "start" if n.startswith("IN") else "end", "bold")
    wire(s, [p(5, "a"), (p(5, "a")[0], 270), (24, 270), (24, bp["IN+"][1]), bp["IN+"]], COL["12V"])
    wire(s, [bp["IN-"], (bx + 10, by + 100), (p(4, "B1")[0], by + 100), p(4, "B1")], COL["GND"])
    wire(s, [bp["OUT+"], (bp["OUT+"][0] + 40, bp["OUT+"][1]), (bp["OUT+"][0] + 40, p(6, "B2")[1] + 40), (p(6, "B2")[0], p(6, "B2")[1] + 40), p(6, "B2")], COL["3V3"])
    wire(s, [bp["OUT-"], (p(8, "B1")[0], bp["OUT-"][1]), p(8, "B1")], COL["GND"])

    ly = 850
    items = [("12V", "+12 V (OBD 16, tras F1)"), ("3V3", "+3,3 V"), ("GND", "masa (OBD 4 y 5)"), ("K", "línea K (OBD 7)"),
             ("TX", "TX ESP (GPIO1)"), ("RX", "RX ESP (GPIO3)"), ("G2", "GPIO2 (puerta TX)"), ("REF", "ref. 1,65 V"),
             ("TXN", "nodo TX (pines 7 y 9)")]
    for i, (k, t) in enumerate(items):
        x = 40 + (i % 5) * 250
        y = ly + (i // 5) * 24
        s.add(f'<line x1="{x}" y1="{y}" x2="{x + 30}" y2="{y}" stroke="{COL[k]}" stroke-width="6" stroke-linecap="round"/>')
        s.text(x + 38, y + 4, t, 12)
    s.text(40, 912, "Cada columna: a-e unidas y f-j unidas. LM339 a caballo del canal, muesca a la izquierda, pin 1 en la columna 12 abajo. "
           "Los puentes curvos solo tocan en sus extremos.", 11, "#444")
    s.text(40, 928, "Carril de arriba: rojo +3,3 V, azul masa. Carril de abajo: azul masa, rojo +3,3 V. Los 12 V solo van por D1 → columna 5 → R10 y al buck.", 11, "#444")
    s.save("protoboard_esp01_lm339.svg")


# ---------------------------------------------------------------- toma OBD
def obd_face(s, cx, cy, mirror, title, sub):
    w1, w2, h = 420, 360, 150
    s.add(f'<path d="M{cx - w1 / 2},{cy - h / 2} L{cx + w1 / 2},{cy - h / 2} L{cx + w2 / 2},{cy + h / 2} '
          f'L{cx - w2 / 2},{cy + h / 2} Z" fill="#2b2b2b" stroke="#000" stroke-width="3" stroke-linejoin="round"/>')
    s.add(f'<rect x="{cx - 20}" y="{cy - h / 2 - 14}" width="40" height="14" rx="3" fill="#2b2b2b"/>')
    s.text(cx, cy - h / 2 - 24, title, 16, "#111", "middle", "bold")
    s.text(cx, cy + h / 2 + 26, sub, 12, "#444", "middle")
    hot = {4: ("GND", COL["GND"]), 5: ("GND", COL["GND"]), 7: ("K", COL["K"]), 16: ("+12V", COL["12V"])}
    for n in range(1, 17):
        row, k = (0, n - 1) if n <= 8 else (1, n - 9)
        x = cx - 168 + k * 48 if row == 0 else cx - 150 + k * 43
        if mirror:
            x = 2 * cx - x
        y = cy - 30 if row == 0 else cy + 32
        c = hot.get(n, (None, "#666"))[1]
        big = n in hot
        s.add(f'<rect x="{x - 9}" y="{y - 14}" width="18" height="28" rx="3" fill="{c if big else "#555"}" '
              f'stroke="{"#fff" if big else "#444"}" stroke-width="{3 if big else 1}"/>')
        s.text(x, y + (-22 if row == 0 else 32), str(n), 15 if big else 12, "#111" if big else "#999", "middle",
               "bold" if big else "normal")


def obd():
    s = Svg(1000, 860, "Toma OBD del Clio II: los 4 pines que usa el puente (dibujo)")
    obd_face(s, 260, 190, False, "Vista de FRENTE (por donde se enchufa)", "lado ancho arriba: pines 1-8 · abajo: 9-16")
    obd_face(s, 740, 190, True, "Vista por DETRÁS (lado de los cables)", "espejo de la vista de frente: el 1 queda a la derecha")
    rows = [("4", "Masa de chasis", "negro", COL["GND"]), ("5", "Masa de señal", "negro", COL["GND"]),
            ("7", "Línea K (UCE A-B4)", "amarillo", COL["K"]), ("16", "+12 V permanente", "rojo, con F1 1 A", COL["12V"])]
    y = 360
    s.text(60, y, "Pin", 14, weight="bold"); s.text(130, y, "Señal", 14, weight="bold"); s.text(360, y, "Cable al puente", 14, weight="bold")
    for i, (n, t, c, col) in enumerate(rows):
        yy = y + 30 + i * 28
        s.add(f'<rect x="58" y="{yy - 15}" width="40" height="22" rx="4" fill="{col}"/>')
        s.text(78, yy + 1, n, 14, "#fff" if n != "7" else "#111", "middle", "bold")
        s.text(130, yy, t, 14); s.text(360, yy, c, 14)
    s.text(60, 520, "Resto de pines: NO conectar. En el Clio II no hay CAN de diagnóstico (6/14) y la línea L (15) no hace falta.", 13, "#444")

    # pin de cable rigido
    s.text(60, 575, "Sin conector macho: pin hecho con cable rígido de 1,5 mm² (el de la instalación de casa)", 15, "#111", weight="bold")
    x0, y0 = 80, 640
    s.add(f'<rect x="{x0}" y="{y0 - 8}" width="60" height="16" fill="#c87533" stroke="#7a4317"/>')
    s.text(x0 + 30, y0 - 18, "1 cm pelado", 12, "#111", "middle")
    s.add(f'<rect x="{x0 + 60}" y="{y0 - 11}" width="50" height="22" rx="4" fill="#2b2b2b"/>')
    s.text(x0 + 85, y0 + 30, "termorretráctil", 12, "#111", "middle")
    s.add(f'<rect x="{x0 + 110}" y="{y0 - 6}" width="200" height="12" rx="6" fill="{COL["K"]}"/>')
    s.text(x0 + 210, y0 + 30, "soldado al cable del puente", 12, "#111", "middle")
    s.add(f'<rect x="{x0 + 330}" y="{y0 - 22}" width="140" height="44" rx="6" fill="#555"/>')
    s.text(x0 + 400, y0 + 4, "a la placa", 13, "#fff", "middle", "bold")
    s.add(f'<line x1="{x0 + 310}" y1="{y0}" x2="{x0 + 330}" y2="{y0}" stroke="{COL["K"]}" stroke-width="10"/>')
    tips = ["Hacer 4 pines (4, 5, 7, 16) y unirlos con cinta o un trozo de plástico para que no se crucen.",
            "Orden: masas 4 y 5 → K 7 → +12 V 16 el último. Si el 16 toca masa salta el fusible del coche.",
            "Los Dupont macho de 0,64 mm bailan en la toma: por delante no; por detrás (pinchando el cable) sí.",
            "En el Clio II la toma está en la consola central, delante de la palanca de cambios (detrás de la tapa).",
            "Comprobar antes con el polímetro: 16-4 = tensión de batería; 7-4 ≈ 10-12 V con el contacto puesto."]
    for i, t in enumerate(tips):
        s.text(60, 710 + i * 24, "• " + t, 13)
    s.save("obd_pines.svg")


# ---------------------------------------------------------------- patillajes
def pinouts():
    s = Svg(1300, 640, "Patillaje: LM339N y ESP-01, y qué va en cada pin")
    x, y = 420, 110
    s.add(f'<rect x="{x}" y="{y}" width="130" height="300" rx="6" fill="#262626"/>')
    s.add(f'<path d="M{x + 50},{y} A15,15 0 0 0 {x + 80},{y}" fill="#555"/>')
    s.add(f'<circle cx="{x + 18}" cy="{y + 20}" r="5" fill="#555"/>')
    s.text(x + 65, y + 290, "LM339N", 15, "#eee", "middle", "bold")
    left = [("1", "OUT2", "→ línea K (con OUT3)", "K"), ("2", "OUT1", "→ RX del ESP · R4 10k a +3,3 V", "RX"),
            ("3", "VCC", "+3,3 V · C3 100 nF a masa", "3V3"), ("4", "IN1−", "ref. RX 0,58 V (R3 47k / R11 10k)", "REF"),
            ("5", "IN1+", "K ÷ 7,8 (R1 68k desde K / R2 10k)", "KD"), ("6", "IN2−", "ref. TX 1,65 V (R5 / R6 10k)", "REF"),
            ("7", "IN2+", "nodo TX (R7 desde TX, D2 desde GPIO2)", "TXN")]
    right = [("14", "OUT3", "→ línea K (con OUT2)", "K"), ("13", "OUT4", "sin conectar", None), ("12", "GND", "masa", "GND"),
             ("11", "IN4+", "masa (comparador sin usar)", "GND"), ("10", "IN4−", "ref. TX 1,65 V", "REF"),
             ("9", "IN3+", "nodo TX", "TXN"), ("8", "IN3−", "ref. TX 1,65 V", "REF")]
    for i in range(7):
        py = y + 30 + i * 38
        for (n, nm, d, c), side in ((left[i], -1), (right[i], 1)):
            px = x - 18 if side < 0 else x + 130
            s.add(f'<rect x="{px}" y="{py - 6}" width="18" height="12" fill="#c0c0c0"/>')
            s.text(x + 65 + side * 38, py + 4, nm, 11, "#ddd", "middle")
            s.text(px + (-8 if side < 0 else 26), py + 5, n, 14, "#111", "end" if side < 0 else "start", "bold")
            lx = x - 60 if side < 0 else x + 190
            if c:
                s.add(f'<line x1="{lx + (-8 if side < 0 else 8) * 0}" y1="{py}" x2="{lx + (-24 if side < 0 else 24)}" y2="{py}" stroke="{COL[c]}" stroke-width="6" stroke-linecap="round"/>')
            s.text(lx + (-32 if side < 0 else 32), py + 4, d, 12, "#222", "end" if side < 0 else "start")
    s.text(x + 65, y + 330, "Muesca arriba (o punto junto al pin 1). Salidas en colector abierto: aguantan 36 V.", 12, "#444", "middle")

    e = esp01(s, 960, 130)
    desc = [("VCC", "+3,3 V (¡nunca 5 V!) · C1 470 µF + C2 100 nF", "3V3"), ("RX", "← OUT1 (pin 2 del LM339)", "RX"),
            ("RST", "directo a +3,3 V", "3V3"), ("GPIO0", "directo a +3,3 V (arranque normal)", "3V3"),
            ("EN", "directo a +3,3 V (CH_PD)", "3V3"), ("GPIO2", "R8 10k a +3,3 V · ánodo de D2", "G2"),
            ("TX", "→ R7 10k → nodo TX (pines 7 y 9)", "TX"), ("GND", "masa", "GND")]
    for i, (n, d, c) in enumerate(desc):
        yy = 300 + i * 26
        s.add(f'<line x1="900" y1="{yy - 4}" x2="926" y2="{yy - 4}" stroke="{COL[c]}" stroke-width="6" stroke-linecap="round"/>')
        s.text(936, yy, n, 13, "#111", weight="bold")
        s.text(996, yy, d, 12, "#222")
    s.text(900, 530, "Pines por parejas: VCC-RX, RST-GPIO0, EN-GPIO2, TX-GND.", 12, "#444")
    s.text(900, 548, "Comprueba GND con el polímetro: tiene continuidad con la tapa metálica.", 12, "#444")
    s.text(900, 566, "Si la tuya sale al revés, gira el dibujo: lo que cuenta son las parejas.", 12, "#444")
    s.save("pinout_lm339_esp01.svg")


if __name__ == "__main__":
    protoboard(); obd(); pinouts()
    print("SVG generados en", OUT)
