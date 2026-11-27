"""Placa perforada (de puntos) compacta del puente ESP-01 + LM339N: vista de componentes y vista de soldaduras.
Comprueba la conectividad antes de dibujar (si hay un corto o una red cortada, falla).
python docs/img/gen_perfboard.py  -> perfboard_arriba.svg, perfboard_abajo.svg
NOTA: en la placa se usan los comparadores 1 y 2 para TX y el 3 para RX (en la protoboard es al revés),
el circuito y el firmware son los mismos.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_esquemas import Svg, COL, BANDS, RES, OUT

NC, NR = 18, 12          # placa 5x7 cm (18 x 24): se usan las filas A-L; el diseño ocupa las columnas 01-15


def lab(c, r):
    """Nombre del agujero con la serigrafía de la placa: letra de fila + número de columna (p. ej. I01)."""
    return f"{chr(65 + r)}{c + 1:02d}"
P = 34                   # px por agujero en el dibujo

# ---------------------------------------------------------------- pistas por debajo (puentes de estaño / hilo desnudo)
TRACES = {
    "K":     [(3, 2), (3, 3), (3, 4), (3, 5), (3, 6), (3, 7), (3, 8), "|", (3, 2), (4, 2), "|", (3, 7), (4, 7), (5, 7),
              "|", (2, 7), (3, 7)],
    "V12IN": [(0, 8), (1, 8)],
    "V12":   [(2, 8), (2, 9), (3, 9)],
    "KD":    [(9, 2), (9, 3), (9, 4)],
    "GNDT":  [(6, 3), (6, 4), (7, 4), (8, 4), (8, 3), (8, 2), (8, 1), (9, 1), (10, 1), (10, 2), (11, 2)],
    "REFRX": [(11, 4), (10, 4), (10, 3)],
    "3V3":   [(11, 3), (12, 3), (12, 4), (13, 4), (13, 5), (13, 6), (13, 7), (13, 8), (12, 8), "|", (13, 7), (14, 7),
              "|", (12, 3), (12, 2), "|", (12, 4), (12, 5)],
    "RX":    [(4, 4), (4, 3), (5, 3), (5, 2), (5, 1), (5, 0)] + [(c, 0) for c in range(6, 15)] + [(14, r) for r in range(1, 7)],
    "REFTX": [(7, 8), (7, 7), (7, 6), (8, 6), (9, 6), (9, 7), "|", (7, 8), (7, 9)],
    "3V3B":  [(6, 7), (6, 8), (6, 9), (6, 10), "|", (6, 9), (5, 9)],
    "TXN":   [(8, 7), (8, 8), (9, 8), (10, 8), (11, 8), "|", (10, 8), (10, 7)],
    "TX":    [(9, 9), (10, 9), (11, 9), (12, 9), (13, 9)],
    "G2":    [(11, 7), (12, 7), (12, 6)],
    "GND":   [(c, 11) for c in range(0, 15)] + ["|", (0, 10), (0, 11), "|", (7, 10), (7, 11), "|", (5, 10), (5, 11), "|", (14, 9), (14, 10), (14, 11)],
}
# cables aislados (se pueden cruzar con las pistas): nombre, red, desde, hasta, cara
WIRES = [("W1", "G2", (14, 8), (12, 7), "abajo", "GPIO2: soldado a la patilla del zócalo"),
         ("W2", "3V3", (12, 8), (6, 9), "arriba", "+3,3 V al LM339"),
         ("W3", "GND", (6, 3), (0, 10), "arriba", "masa de arriba a la de abajo")]
SAME = [("3V3", "3V3B"), ("GND", "GNDT")]  # redes unidas por cables aislados

# ---------------------------------------------------------------- componentes (patillas -> red)
IC_TOP = ["RX", None, "GNDT", "GNDT", "GNDT", "KD", "REFRX"]   # pines 14..8
IC_BOT = ["K", "K", "3V3B", "REFTX", "TXN", "REFTX", "TXN"]    # pines 1..7
PARTS = [  # ref, tipo, valor, [(celda, red)], montaje
    ("D1", "diodo", "1N4007", [((1, 8), "V12IN"), ((2, 8), "V12")], "pie"),
    ("R10", "res", "1k", [((3, 9), "V12"), ((3, 8), "K")], "pie"),
    ("R1", "res", "68k", [((4, 2), "K"), ((9, 2), "KD")], "tumbada"),
    ("R2", "res", "10k", [((9, 3), "KD"), ((8, 3), "GNDT")], "pie"),
    ("R11", "res", "10k", [((10, 3), "REFRX"), ((10, 2), "GNDT")], "pie"),
    ("R3", "res", "47k", [((11, 4), "REFRX"), ((11, 3), "3V3")], "pie"),
    ("R4", "res", "10k", [((13, 4), "3V3"), ((14, 4), "RX")], "pie"),
    ("C1", "elec", "470µF", [((12, 2), "3V3"), ((11, 2), "GNDT")], "tumbado"),
    ("R5", "res", "10k", [((6, 8), "3V3B"), ((7, 8), "REFTX")], "pie"),
    ("R6", "res", "10k", [((7, 9), "REFTX"), ((7, 10), "GND")], "pie"),
    ("C3", "cer", "100nF", [((5, 9), "3V3B"), ((5, 10), "GND")], "pie"),
    ("D2", "diodo", "1N4148", [((11, 7), "G2"), ((11, 8), "TXN")], "pie"),
    ("R8", "res", "10k", [((12, 6), "G2"), ((12, 5), "3V3")], "pie"),
    ("R7", "res", "10k", [((9, 8), "TXN"), ((9, 9), "TX")], "pie"),
]
ESP = {"VCC": ((13, 6), "3V3"), "RST": ((13, 7), "3V3"), "EN": ((13, 8), "3V3"), "TX": ((13, 9), "TX"),
       "RX": ((14, 6), "RX"), "GPIO0": ((14, 7), "3V3"), "GPIO2": ((14, 8), "G2"), "GND": ((14, 9), "GND")}
EXT = [  # cables que salen de la placa: celda, red, texto, color
    ((0, 8), "V12IN", "OBD 16 (+12 V, con F1 1 A)", COL["12V"]),
    ((2, 7), "K", "OBD 7 (línea K)", COL["K"]),
    ((0, 11), "GND", "OBD 4 y 5 (masa)", COL["GND"]),
    ((2, 9), "V12", "al buck IN+", COL["12V"]),
    ((1, 11), "GND", "al buck IN− / OUT−", COL["GND"]),
    ((6, 10), "3V3B", "del buck OUT+ (3,3 V)", COL["3V3"]),
]


def check():
    net_of, holes = {}, {}

    def put(cell, net, what):
        c, r = cell
        assert 0 <= c < NC and 0 <= r < NR, f"{what} fuera de la placa {cell}"
        if cell in net_of and net_of[cell] != net:
            raise SystemExit(f"CORTO en {cell}: {net_of[cell]} y {net} ({what})")
        net_of[cell] = net

    def hole(cell, what):
        if cell in holes:
            raise SystemExit(f"Agujero {cell} ocupado dos veces: {holes[cell]} y {what}")
        holes[cell] = what

    edges = []
    for net, seq in TRACES.items():
        prev = None
        for it in seq:
            if it == "|":
                prev = None
                continue
            put(it, net, "pista")
            if prev:
                assert abs(prev[0] - it[0]) + abs(prev[1] - it[1]) == 1, f"pista no adyacente {prev}->{it} en {net}"
                edges.append((prev, it))
            prev = it
    for i, n in enumerate(IC_BOT):
        put((4 + i, 7), n or f"nc{i}", f"pin {i + 1}"); hole((4 + i, 7), "LM339")
    for i, n in enumerate(IC_TOP):
        put((4 + i, 4), n or f"nc{14 - i}", f"pin {14 - i}"); hole((4 + i, 4), "LM339")
    for ref, _, _, pins, _ in PARTS:
        for cell, net in pins:
            put(cell, net, ref); hole(cell, ref)
    for name, (cell, net) in ESP.items():
        put(cell, net, "ESP " + name); hole(cell, "zócalo ESP")
    for cell, net, t, _ in EXT:
        put(cell, net, t); hole(cell, t)
    for w, net, a, b, *_ in WIRES:
        if a not in holes or "zócalo" not in holes[a]:
            hole(a, w)
        hole(b, w) if b not in holes else None
    # conectividad
    parent = {}

    def f(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[f(a)] = f(b)
    for _, _, a, b, *_ in WIRES:
        parent[f(a)] = f(b)
    alias = {b: a for a, b in SAME}
    groups = {}
    for cell, net in net_of.items():
        groups.setdefault(alias.get(net, net), set()).add(f(cell))
    bad = {n: len(g) for n, g in groups.items() if len(g) > 1 and not n.startswith("nc")}
    if bad:
        raise SystemExit(f"Redes cortadas: {bad}")
    # ninguna pista toca dos redes distintas (ya lo garantiza put) y no hay dos redes unidas por error
    roots = {}
    for n, g in groups.items():
        for r in g:
            if r in roots and roots[r] != n:
                raise SystemExit(f"CORTO entre {roots[r]} y {n}")
            roots[r] = n
    print("Conectividad OK:", len(groups), "redes,", len(edges), "puentes de estaño")
    return net_of


NETCOL = {"K": COL["K"], "V12IN": COL["12V"], "V12": COL["12V"], "KD": COL["KD"], "GNDT": COL["GND"], "GND": COL["GND"],
          "REFRX": "#a855f7", "3V3": COL["3V3"], "3V3B": COL["3V3"], "RX": COL["RX"], "REFTX": COL["REF"],
          "TXN": COL["TXN"], "TX": COL["TX"], "G2": COL["G2"]}


def board(s, x0, y0, mirror):
    def xy(c, r):
        cc = NC - 1 - c if mirror else c
        return x0 + 30 + cc * P, y0 + 30 + r * P
    w, h = 60 + (NC - 1) * P, 60 + (NR - 1) * P
    s.add(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="6" fill="{"#c8a165" if mirror else "#d7b77a"}" stroke="#8a6a35" stroke-width="2"/>')
    for r in range(NR):
        for c in range(NC):
            px, py = xy(c, r)
            if mirror:
                s.add(f'<circle cx="{px}" cy="{py}" r="11" fill="#c9884b" stroke="#9b5f2a"/>')
            s.add(f'<circle cx="{px}" cy="{py}" r="4.5" fill="#3b2a14"/>')
    for c in range(NC):
        s.text(xy(c, 0)[0], y0 + 14, f"{c + 1:02d}", 10, "#5a4320", "middle", "bold")
        s.text(xy(c, 0)[0], y0 + h - 4, f"{c + 1:02d}", 10, "#5a4320", "middle", "bold")
    for r in range(NR):
        s.text(x0 - 10, xy(0, r)[1] + 4, chr(65 + r), 11, "#5a4320", "end", "bold")
        s.text(x0 + w + 10, xy(0, r)[1] + 4, chr(65 + r), 11, "#5a4320", "start", "bold")
    s.add(f'<line x1="{x0 - 20}" y1="{y0 + h + 6}" x2="{x0 + w + 20}" y2="{y0 + h + 6}" stroke="#c00" stroke-width="2" stroke-dasharray="8 5"/>')
    s.text(x0 + w / 2, y0 + h + 22, "✂ cortar aquí (entre las filas L y M): el trozo M-X (18 × 12) se guarda", 12, "#c00", "middle", "bold")
    return xy


def res_body(s, a, b, val, label, standing, tumbada=False):
    (x1, y1), (x2, y2) = a, b
    s.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#a3a3a3" stroke-width="3"/>')
    code = RES[val]
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    vert = abs(y2 - y1) > abs(x2 - x1)
    L, T = (44, 15) if tumbada else (26, 14)
    rot = 90 if vert else 0
    bands = "".join(f'<rect x="{-L / 2 + 5 + i * 5 + (2 if i == 3 else 0)}" y="{-T / 2}" width="3" height="{T}" fill="{c}"/>'
                    for i, c in enumerate([BANDS[code[0]], BANDS[code[1]], BANDS[code[2]], "#c9a227"]))
    s.add(f'<g transform="translate({cx} {cy}) rotate({rot})"><rect x="{-L / 2}" y="{-T / 2}" width="{L}" height="{T}" rx="6" '
          f'fill="#d9bf8c" stroke="#7a6545"/>{bands}</g>')
    if standing:  # de pie: el cuerpo se dibuja sobre una patilla y la otra vuelve doblada
        s.add(f'<circle cx="{x1}" cy="{y1}" r="5" fill="none" stroke="#666" stroke-width="1.5"/>')
    for x, y in (a, b):
        s.add(f'<circle cx="{x}" cy="{y}" r="3" fill="#888"/>')
    dx, dy = (22, 4) if vert else (0, -12)
    left = label.startswith("R6")
    s.text(cx - dx if left else cx + dx, cy + dy, label, 11, "#111", "end" if left else ("start" if vert else "middle"), "bold")


def top_view(net_of):
    s = Svg(1060, 790, "Placa 5×7 cm (filas A-L, se corta el resto) — vista de COMPONENTES (por arriba)")
    xy = board(s, 70, 80, False)
    # zócalo del ESP
    (ax, ay), (bx, by) = xy(13, 6), xy(14, 9)
    s.add(f'<rect x="{ax - 15}" y="{ay - 15}" width="{bx - ax + 30}" height="{by - ay + 30}" rx="3" fill="#111" fill-opacity=".85"/>')
    for n, (cell, _) in ESP.items():
        x, y = xy(*cell)
        s.add(f'<rect x="{x - 5}" y="{y - 5}" width="10" height="10" fill="#444"/>')
        if cell[0] == 14:
            s.text(x + 26, y + 4, n, 10, "#1f2f6b", "start", "bold")
    mx0 = bx + 18
    s.add(f'<rect x="{mx0}" y="{ay - 30}" width="250" height="{by - ay + 60}" rx="6" fill="#1f2f6b" fill-opacity=".18" '
          f'stroke="#1f2f6b" stroke-dasharray="6 4"/>')
    s.text(mx0 + 150, ay - 38, "ESP-01 enchufado (por encima de 16-18, sobresale)", 11, "#1f2f6b", "middle", "bold")
    s.text(mx0 + 150, by + 22, "chips arriba · antena hacia fuera", 11, "#1f2f6b", "middle")
    s.text((ax + bx) / 2, by + 30, "zócalo 2×4 hembra", 10, "#111", "middle")
    pinmap = ("Zócalo: " + " · ".join(f"{lab(*ESP[n][0])} {n}" for n in ("VCC", "RST", "EN", "TX", "RX", "GPIO0", "GPIO2", "GND")))
    # LM339
    (x1, y1), (x2, y2) = xy(4, 4), xy(10, 7)
    s.add(f'<rect x="{x1 - 14}" y="{y1 + 12}" width="{x2 - x1 + 28}" height="{y2 - y1 - 24}" rx="4" fill="#262626"/>')
    s.add(f'<path d="M{x1 - 14},{(y1 + y2) / 2 - 10} A10,10 0 0 1 {x1 - 14},{(y1 + y2) / 2 + 10}" fill="#666"/>')
    s.text((x1 + x2) / 2, (y1 + y2) / 2 + 6, "LM339N", 16, "#eee", "middle", "bold")
    for i in range(7):
        for r, num in ((7, i + 1), (4, 14 - i)):
            x, y = xy(4 + i, r)
            s.add(f'<rect x="{x - 6}" y="{y - 7}" width="12" height="14" fill="#c0c0c0" stroke="#777"/>')
            s.text(x, y + (-16 if r == 7 else 24), str(num), 10, "#ccc", "middle", "bold")
    # componentes
    for ref, kind, val, pins, mont in PARTS:
        a, b = xy(*pins[0][0]), xy(*pins[1][0])
        if kind == "res":
            res_body(s, a, b, val, f"{ref} {val}", mont == "pie", mont == "tumbada")
        elif kind == "diodo":
            glass = val == "1N4148"
            s.add(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="#a3a3a3" stroke-width="3"/>')
            cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            vert = abs(b[1] - a[1]) > abs(b[0] - a[0])
            sx = 0 if vert else (1 if b[0] > a[0] else -1)
            sy = (1 if b[1] > a[1] else -1) if vert else 0
            w, h = (12, 24) if vert else (24, 12)
            s.add(f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" rx="4" fill="{"#f4a261" if glass else "#1b1b1b"}" stroke="#333"/>')
            s.add(f'<rect x="{cx + sx * 6 - (2 if sx else w / 2)}" y="{cy + sy * 6 - (2 if sy else h / 2)}" width="{4 if sx else w}" height="{4 if sy else h}" fill="{"#111" if glass else "#ddd"}"/>')
            if glass:
                s.text(cx - 14, cy + 4, f"{ref} {val}", 11, "#111", "end", "bold")
                s.text(cx - 14, cy + 17, "franja = cátodo", 9, "#444", "end")
            else:
                s.text(cx, cy - 14, f"{ref} {val}", 11, "#111", "middle", "bold")
                s.text(cx, cy + 24, "franja = cátodo", 9, "#444", "middle")
        elif kind == "cer":
            s.add(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="#a3a3a3" stroke-width="3"/>')
            s.add(f'<ellipse cx="{(a[0] + b[0]) / 2}" cy="{(a[1] + b[1]) / 2}" rx="9" ry="12" fill="#e9b949" stroke="#9c7a1e"/>')
            s.text(a[0] - 16, (a[1] + b[1]) / 2 + 4, f"{ref} {val}", 11, "#111", "end", "bold")
        elif kind == "elec":
            # tumbado hacia arriba, sobre las filas 1-2 libres
            s.add(f'<line x1="{a[0]}" y1="{a[1]}" x2="{a[0]}" y2="{a[1] - 30}" stroke="#a3a3a3" stroke-width="3"/>')
            s.add(f'<line x1="{b[0]}" y1="{b[1]}" x2="{b[0]}" y2="{b[1] - 30}" stroke="#a3a3a3" stroke-width="3"/>')
            s.add(f'<rect x="{b[0] - 16}" y="{a[1] - 76}" width="{a[0] - b[0] + 32}" height="48" rx="8" fill="#2b4c9b" stroke="#16295a" stroke-width="2"/>')
            s.add(f'<rect x="{b[0] - 16}" y="{a[1] - 76}" width="12" height="48" fill="#cfd8ea"/>')
            s.text((a[0] + b[0]) / 2 + 4, a[1] - 48, "C1 470µF", 10, "#fff", "middle", "bold")
            s.text(a[0] + 18, a[1] + 4, "+", 14, "#111", "middle", "bold")
            s.text(b[0] - 18, b[1] + 4, "−", 14, "#111", "middle", "bold")
    # cables aislados por arriba
    for w, net, a, b, side, t in WIRES:
        if side != "arriba":
            continue
        pa, pb = xy(*a), xy(*b)
        mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2 + 60
        if w == "W3":
            ex = pb[0] - 34
            path = f"M{pa[0]},{pa[1]} L{pa[0]},{pa[1] - 30} L{ex},{pa[1] - 30} L{ex},{pb[1]} L{pb[0]},{pb[1]}"
        else:
            path = f"M{pa[0]},{pa[1]} Q{mx},{my} {pb[0]},{pb[1]}"
        s.add(f'<path d="{path}" fill="none" stroke="#000" stroke-opacity=".3" stroke-width="8" stroke-linecap="round"/>')
        s.add(f'<path d="{path}" fill="none" stroke="{NETCOL[net]}" stroke-width="6" stroke-linecap="round"/>')
        for p in (pa, pb):
            s.add(f'<circle cx="{p[0]}" cy="{p[1]}" r="5" fill="#555"/>')
        lx, lyy = ((pa[0] + pb[0]) / 2 - 30, pa[1] - 34) if w == "W3" else ((pa[0] + pb[0]) / 2 + 40, my + 34)
        s.add(f'<rect x="{lx - 62}" y="{lyy - 12}" width="124" height="16" rx="3" fill="#fff" fill-opacity=".85"/>')
        s.text(lx, lyy, f"{w} cable aislado", 11, "#111", "middle", "bold")
    # cables externos
    for cell, net, t, col in EXT:
        x, y = xy(*cell)
        ex = 70 - 20
        s.add(f'<path d="M{x},{y} L{ex - 10},{y}" stroke="{col}" stroke-width="6" stroke-linecap="round"/>' if cell[0] <= 2 and cell[1] != 10 else
              f'<path d="M{x},{y} Q{x - 10},{y + 20} {x - 30},{y + 58}" fill="none" stroke="{col}" stroke-width="6" stroke-linecap="round"/>')
    ly = 80
    for cell, net, t, col in EXT:
        pass
    notes = [(f"{t} → {lab(*cell)}", col) for cell, net, t, col in EXT]
    for i, (t, col) in enumerate(notes):
        x, y = 70 + (i % 3) * 300, 610 + (i // 3) * 24
        s.add(f'<line x1="{x}" y1="{y - 4}" x2="{x + 26}" y2="{y - 4}" stroke="{col}" stroke-width="6" stroke-linecap="round"/>')
        s.text(x + 34, y, t, 12)
    s.text(70, 664, pinmap, 12, "#111", weight="bold")
    s.text(70, 686, "Resistencias DE PIE (el círculo marca la patilla de abajo del cuerpo), salvo R1 tumbada. C1 tumbado hacia el borde de arriba.", 12, "#333")
    s.text(70, 706, "Letras = filas (A-L), números = columnas (01-18), como viene serigrafiado. W2 y W3: cable aislado por arriba; W1 por abajo.", 12, "#333")
    s.text(70, 726, "En la placa, el LM339 usa los comparadores 1-2 para TX y el 3 para RX: mismo circuito que la protoboard, otros pines.", 12, "#333")
    s.text(70, 746, "Muesca del LM339 a la izquierda. El ESP-01 se quita para grabarlo.", 12, "#333")
    s.save("perfboard_arriba.svg")


def bottom_view(net_of):
    s = Svg(1060, 790, "Placa 5×7 cm — vista de SOLDADURAS (por abajo, dada la vuelta: izquierda ↔ derecha)")
    xy = board(s, 70, 80, True)
    for net, seq in TRACES.items():
        prev = None
        for it in seq:
            if it == "|":
                prev = None
                continue
            if prev:
                (x1, y1), (x2, y2) = xy(*prev), xy(*it)
                s.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#b9bcc2" stroke-width="12" stroke-linecap="round"/>')
                s.add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{NETCOL[net]}" stroke-width="4" stroke-linecap="round"/>')
            prev = it
    for cell in net_of:
        x, y = xy(*cell)
        s.add(f'<circle cx="{x}" cy="{y}" r="8" fill="#d7d9de" stroke="#8d9096"/>')
    for w, net, a, b, side, t in WIRES:
        if side != "abajo":
            continue
        pa, pb = xy(*a), xy(*b)
        path = f"M{pa[0]},{pa[1]} Q{pa[0] + 50},{(pa[1] + pb[1]) / 2 + 40} {pb[0]},{pb[1]}"
        s.add(f'<path d="{path}" fill="none" stroke="#000" stroke-opacity=".3" stroke-width="8" stroke-linecap="round"/>')
        s.add(f'<path d="{path}" fill="none" stroke="{NETCOL[net]}" stroke-width="6" stroke-linecap="round"/>')
        s.text(pa[0] + 60, (pa[1] + pb[1]) / 2 + 40, f"{w} cable aislado (GPIO2)", 11, "#111", "start", "bold")
    # rótulos de patillas del IC y del zócalo vistos por abajo
    for i in range(7):
        x, y = xy(4 + i, 7)
        s.text(x, y - 15, str(i + 1), 10, "#111", "middle", "bold")
        x, y = xy(4 + i, 4)
        s.text(x, y + 22, str(14 - i), 10, "#111", "middle", "bold")
    for n, (cell, _) in ESP.items():
        x, y = xy(*cell)
        s.add(f'<rect x="{x - 9}" y="{y - 9}" width="18" height="18" fill="none" stroke="#111" stroke-width="1.5"/>')
    x, y = xy(14, 6)
    s.text(x - 18, y - 22, "zócalo ESP", 10, "#111", "middle", "bold")
    x, y = xy(4, 7)
    s.text(x + 14, y + 44, "pin 1 LM339", 10, "#111", "middle", "bold")
    items = [(COL["K"], "línea K"), (COL["12V"], "+12 V"), (COL["3V3"], "+3,3 V"), (COL["GND"], "masa"), (COL["RX"], "RX"),
             (COL["TX"], "TX"), (COL["TXN"], "nodo TX"), (COL["REF"], "ref. TX 1,65 V"), (COL["KD"], "K ÷ 7,8"),
             (COL["G2"], "GPIO2"), ("#a855f7", "ref. RX 0,58 V")]
    for i, (c, t) in enumerate(items):
        x, y = 70 + (i % 6) * 160, 610 + (i // 6) * 24
        s.add(f'<line x1="{x}" y1="{y - 4}" x2="{x + 26}" y2="{y - 4}" stroke="{c}" stroke-width="6" stroke-linecap="round"/>')
        s.text(x + 34, y, t, 12)
    s.text(70, 680, "Cada raya = unir dos agujeros vecinos con estaño o con hilo desnudo (el del cable rígido pelado). Nada más se toca.", 12, "#333")
    s.text(70, 700, "Al terminar: comprobar con el polímetro que NO hay continuidad entre +12 V, +3,3 V, K y masa.", 12, "#333")
    s.text(70, 720, "Esta vista está en espejo: la columna 01 queda a la DERECHA, igual que cuando le das la vuelta a la placa.", 12, "#333")
    s.save("perfboard_abajo.svg")


if __name__ == "__main__" and "--pequena" not in sys.argv:
    nets = check()
    top_view(nets)
    bottom_view(nets)
    print("SVG en", OUT)


# ---------------------------------------------------------------- placa pequeña (6 x 17): soporte del buck
def small_board():
    SC, SR, Q = 6, 17, 30
    s = Svg(1060, 760, "Placa pequeña 6 × 17 (01-06 / A-Q): alimentación con el buck MP1584")

    def draw(x0, y0, mirror, title):
        def xy(c, r):
            cc = SC - 1 - c if mirror else c
            return x0 + 28 + cc * Q, y0 + 28 + r * Q
        w, h = 56 + (SC - 1) * Q, 56 + (SR - 1) * Q
        s.add(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="6" fill="{"#c8a165" if mirror else "#d7b77a"}" stroke="#8a6a35" stroke-width="2"/>')
        s.text(x0 + w / 2, y0 - 12, title, 14, "#111", "middle", "bold")
        for r in range(SR):
            s.text(x0 - 8, xy(0, r)[1] + 4, chr(65 + r), 10, "#5a4320", "end", "bold")
            for c in range(SC):
                px, py = xy(c, r)
                if mirror:
                    s.add(f'<circle cx="{px}" cy="{py}" r="10" fill="#c9884b" stroke="#9b5f2a"/>')
                s.add(f'<circle cx="{px}" cy="{py}" r="4" fill="#3b2a14"/>')
        for c in range(SC):
            s.text(xy(c, 0)[0], y0 + 13, f"{c + 1:02d}", 9, "#5a4320", "middle", "bold")
        return xy

    # pistas: columna 01 = entrada/salida +, columna 06 = masa
    runs = [("12V", 0, 0, 2), ("GND", 5, 0, 2), ("3V3", 0, 11, 16), ("GND", 5, 11, 16)]
    legs = {"IN+": (0, 2), "IN−": (5, 2), "OUT+": (0, 11), "OUT−": (5, 11)}
    wires = [((0, 0), "12V", "+12 V ← J03"), ((5, 0), "GND", "masa ← L02"),
             ((0, 16), "3V3", "+3,3 V → K07"), ((5, 16), "GND", "masa (opcional)")]

    xy = draw(300, 90, False, "Por ARRIBA")
    (x1, y1), (x2, y2) = xy(0, 2), xy(5, 11)
    s.add(f'<rect x="{x1 - 22}" y="{y1 - 16}" width="{x2 - x1 + 44}" height="{y2 - y1 + 32}" rx="4" fill="#1e5aa8" stroke="#0f3463" stroke-width="2"/>')
    s.add(f'<rect x="{(x1 + x2) / 2 - 22}" y="{(y1 + y2) / 2 - 40}" width="44" height="44" fill="#6b7280"/>')
    s.add(f'<circle cx="{(x1 + x2) / 2}" cy="{(y1 + y2) / 2 + 40}" r="12" fill="#f2c14e" stroke="#444"/>')
    s.text((x1 + x2) / 2, (y1 + y2) / 2 + 70, "tornillo: 3,3 V", 10, "#fff", "middle", "bold")
    s.text((x1 + x2) / 2, y1 + 32, "MP1584", 13, "#fff", "middle", "bold")
    for n, cell in legs.items():
        x, y = xy(*cell)
        s.add(f'<rect x="{x - 6}" y="{y - 6}" width="12" height="12" fill="#d4af37" stroke="#7a5f12"/>')
        s.text(x + (12 if cell[0] == 0 else -12), y + (16 if cell[1] == 2 else -10), n, 10, "#fff", "start" if cell[0] == 0 else "end", "bold")
    for cell, net, t in wires:
        x, y = xy(*cell)
        right = cell[0] == 5
        ex = x + 70 if right else x - 70
        s.add(f'<path d="M{x},{y} L{ex},{y}" stroke="{COL[net]}" stroke-width="6" stroke-linecap="round"/>')
        s.text(ex + (8 if right else -8), y + 4, t, 12, "#111", "start" if right else "end", "bold")

    xy = draw(800, 90, True, "Por ABAJO (dada la vuelta)")
    for net, c, ra, rb in runs:
        for r in range(ra, rb):
            (xa, ya), (xb, yb) = xy(c, r), xy(c, r + 1)
            s.add(f'<line x1="{xa}" y1="{ya}" x2="{xb}" y2="{yb}" stroke="#b9bcc2" stroke-width="11" stroke-linecap="round"/>')
            s.add(f'<line x1="{xa}" y1="{ya}" x2="{xb}" y2="{yb}" stroke="{COL[net]}" stroke-width="4" stroke-linecap="round"/>')
        for r in range(ra, rb + 1):
            x, y = xy(c, r)
            s.add(f'<circle cx="{x}" cy="{y}" r="7" fill="#d7d9de" stroke="#8d9096"/>')
    notes = ["Las 4 esquinas del buck (IN+, IN−, OUT+, OUT−) van a la placa con 4 patas de resistencia cortadas, en 01/06 de C y L.",
             "Si las patas del buck no caen justo en C y L, usa la fila de al lado y alarga la pista de estaño.",
             "Por abajo solo 4 pistas rectas: 01 A-C (+12 V), 06 A-C y 06 L-Q (masa), 01 L-Q (+3,3 V).",
             "AJUSTA EL BUCK A 3,3 V con el polímetro ANTES de unirlo a la placa grande (gira el tornillo).",
             "Con este soporte, en la placa grande los cables del buck van a J03 (IN+), L02 (masa) y K07 (OUT+)."]
    for i, t in enumerate(notes):
        s.text(60, 660 + i * 20, "• " + t, 12, "#333")
    s.save("perfboard_pequena_buck.svg")


if __name__ == "__main__" and "--pequena" in sys.argv:
    small_board()
