"""Placa pequeña (6 x 17, serigrafía 01-06 / A-Q) con el LM339N y sus componentes. El ESP-01 va aparte con cables.
La colocación sale de una búsqueda automática (pequena_layout.json); aquí se rutea, se comprueba y se dibuja.
python docs/img/gen_pequena.py -> pequena_arriba.svg, pequena_abajo.svg
"""
import json, os, sys
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_esquemas import Svg, COL, BANDS, RES, OUT
from gen_perfboard import res_body, NETCOL

NC, NR, P = 6, 17, 36
LAYOUT = json.load(open(os.path.join(OUT, "pequena_layout.json")))
PARTS = {"R1": ("res", "68k", "K", "KD"), "R2": ("res", "10k", "KD", "GND"), "R3": ("res", "47k", "3V3", "REFRX"),
         "R4": ("res", "10k", "RX", "3V3"), "R5": ("res", "10k", "3V3", "REFTX"), "R6": ("res", "10k", "REFTX", "GND"),
         "R7": ("res", "10k", "TX", "TXN"), "R8": ("res", "10k", "G2", "3V3"), "R10": ("res", "1k", "V12", "K"),
         "R11": ("res", "10k", "REFRX", "GND"), "D2": ("diodo", "1N4148", "G2", "TXN"), "C3": ("cer", "100nF", "3V3", "GND")}
PADTXT = {"V12": ("+12 V (OBD 16, tras F1 y D1)", COL["12V"]), "K": ("OBD 7 (línea K)", COL["K"]),
          "GND": ("masa (OBD 4-5 y buck −)", COL["GND"]), "3V3": ("+3,3 V del buck", COL["3V3"]),
          "TX": ("ESP TX (GPIO1)", COL["TX"]), "RX": ("ESP RX (GPIO3)", COL["RX"]), "G2": ("ESP GPIO2", COL["G2"])}
NETCOL = dict(NETCOL, **{"V12": COL["12V"], "GND": COL["GND"], "3V3": COL["3V3"]})


def lab(c, r):
    return f"{chr(65 + r)}{c + 1:02d}"


def ic_cells():
    A = ["K", "K", "3V3", "REFTX", "TXN", "REFTX", "TXN"]                              # pines 1..7
    B = (["REFRX", "KD", "GND", "GND", "GND", None, "RX"] if LAYOUT["rx"] == 3        # pines 8..14
         else ["GND", "GND", "REFRX", "KD", "GND", "RX", None])
    cells, pins = {}, {}
    for i in range(7):
        r = LAYOUT["r0"] + i
        if LAYOUT["rot"] == 0:   # muesca arriba: izquierda 1..7 hacia abajo, derecha 14..8
            pins[(1, r)], pins[(4, r)] = i + 1, 14 - i
            cells[(1, r)], cells[(4, r)] = A[i], B[6 - i]
        else:                    # muesca abajo: izquierda 8..14, derecha 7..1
            pins[(1, r)], pins[(4, r)] = 8 + i, 7 - i
            cells[(1, r)], cells[(4, r)] = B[i], A[6 - i]
    return cells, pins


def fixed_cells():
    f, holes = {}, {}
    cells, pins = ic_cells()
    for c, n in cells.items():
        f[c] = n or f"nc{pins[c]}"; holes[c] = f"LM339 pin {pins[c]}"
    for ref, cs in LAYOUT["parts"].items():
        cs = [tuple(x) for x in cs]
        if ref.startswith("pad_"):
            f[cs[0]] = ref[4:]; holes[cs[0]] = "cable " + ref[4:]
        else:
            _, _, a, b = PARTS[ref]
            f[cs[0]], f[cs[1]] = a, b; holes[cs[0]] = holes[cs[1]] = ref
    return f, holes


def route_all(f):
    """Rutea por la cara de abajo (vecinos ortogonales). Devuelve pistas y cables aislados."""
    keep = {(c, LAYOUT["r0"] + i) for c in (2, 3) for i in range(7)}  # bajo el chip: solo pistas
    best = None
    import random
    nets = sorted(set(f.values()))
    for t in range(3000):
        order = nets if t == 0 else random.Random(t).sample(nets, len(nets))
        used, traces, wires = dict(f), {}, []
        for net in order:
            pads = [c for c, n in f.items() if n == net]
            if len(pads) < 2:
                continue
            tree, rest, edges = {pads[0]}, set(pads[1:]), []
            while rest:
                prev, q, hit = {c: None for c in tree}, deque(tree), None
                while q:
                    c = q.popleft()
                    if c in rest:
                        hit = c; break
                    for d in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
                        if d in prev or not (0 <= d[0] < NC and 0 <= d[1] < NR) or used.get(d, net) != net:
                            continue
                        prev[d] = c; q.append(d)
                if hit is None:
                    a = min(rest, key=lambda r: min(abs(r[0] - s[0]) + abs(r[1] - s[1]) for s in tree))
                    b = min(tree, key=lambda s: abs(a[0] - s[0]) + abs(a[1] - s[1]))
                    wires.append((net, a, b)); tree.add(a); rest.discard(a); continue
                c = hit
                while prev[c] is not None:
                    edges.append((prev[c], c)); used[c] = net; tree.add(c); c = prev[c]
                rest.discard(hit)
            traces[net] = edges
        sc = (len(wires), sum(len(e) for e in traces.values()))
        if best is None or sc < best[0]:
            best = (sc, traces, wires, used)
    return best[1], best[2], best[3]


def check(f, traces, wires, used):
    """Comprobación independiente: cada red conectada y ninguna unida a otra."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for net, es in traces.items():
        for a, b in es:
            assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
            assert used[a] == net and used[b] == net, f"pista de {net} pisa otra red"
            parent[find(a)] = find(b)
    for net, a, b in wires:
        parent[find(a)] = find(b)
    groups = {}
    for c, n in used.items():
        groups.setdefault(n, set()).add(find(c))
    for n, g in groups.items():
        if not n.startswith("nc") and len(g) != 1:
            raise SystemExit(f"red {n} cortada")
    roots = {}
    for n, g in groups.items():
        for r in g:
            if r in roots:
                raise SystemExit(f"CORTO {roots[r]} - {n}")
            roots[r] = n
    print(f"Conectividad OK: {len(groups)} redes, {sum(len(e) for e in traces.values())} puentes, {len(wires)} cables aislados")


def board(s, x0, y0, mirror):
    def xy(c, r):
        cc = NC - 1 - c if mirror else c
        return x0 + 30 + cc * P, y0 + 30 + r * P
    w, h = 60 + (NC - 1) * P, 60 + (NR - 1) * P
    s.add(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="6" fill="{"#1f6b45" if mirror else "#1e7a4c"}" stroke="#0f3d26" stroke-width="2"/>')
    for r in range(NR):
        for c in range(NC):
            px, py = xy(c, r)
            s.add(f'<circle cx="{px}" cy="{py}" r="10" fill="#cfd3d6" stroke="#8d9096"/>')
            s.add(f'<circle cx="{px}" cy="{py}" r="4" fill="#20302a"/>')
        s.text(x0 - 8, xy(0, r)[1] + 4, chr(65 + r), 11, "#1f3d2c", "end", "bold")
        s.text(x0 + w + 8, xy(0, r)[1] + 4, chr(65 + r), 11, "#1f3d2c", "start", "bold")
    for c in range(NC):
        s.text(xy(c, 0)[0], y0 + 13, f"{c + 1:02d}", 10, "#e8f5ec", "middle", "bold")
        s.text(xy(c, 0)[0], y0 + h - 3, f"{c + 1:02d}", 10, "#e8f5ec", "middle", "bold")
    return xy


def draw(f, traces, wires):
    cells, pins = ic_cells()
    s = Svg(1100, 1000, "Placa pequeña 6 × 17 (01-06 / A-Q): LM339N y componentes")
    # ---------------- arriba
    xy = board(s, 90, 90, False)
    s.text(90 + 120, 78, "Por ARRIBA (componentes)", 14, "#111", "middle", "bold")
    r0 = LAYOUT["r0"]
    (x1, y1), (x2, y2) = xy(1, r0), xy(4, r0 + 6)
    s.add(f'<rect x="{x1 + 10}" y="{y1 - 14}" width="{x2 - x1 - 20}" height="{y2 - y1 + 28}" rx="4" fill="#262626"/>')
    ny = y1 - 14 if LAYOUT["rot"] == 0 else y2 + 14
    s.add(f'<path d="M{(x1 + x2) / 2 - 10},{ny} A10,10 0 0 {0 if LAYOUT["rot"] == 0 else 1} {(x1 + x2) / 2 + 10},{ny}" fill="#666"/>')
    s.text((x1 + x2) / 2, (y1 + y2) / 2, "LM339N", 14, "#eee", "middle", "bold", rot=90)
    for c, n in pins.items():
        x, y = xy(*c)
        s.add(f'<rect x="{x - 7}" y="{y - 6}" width="14" height="12" fill="#c0c0c0" stroke="#777"/>')
        s.text(x + (18 if c[0] == 1 else -18), y + 4, str(n), 10, "#ddd", "middle", "bold")
    for ref, (kind, val, a, b) in PARTS.items():
        pa, pb = [xy(*tuple(c)) for c in LAYOUT["parts"][ref]]
        if kind == "res":
            res_body(s, pa, pb, val, ref, True, color="#fff")
        else:
            s.add(f'<line x1="{pa[0]}" y1="{pa[1]}" x2="{pb[0]}" y2="{pb[1]}" stroke="#a3a3a3" stroke-width="3"/>')
            cx, cy = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
            if kind == "cer":
                s.add(f'<ellipse cx="{cx}" cy="{cy}" rx="10" ry="10" fill="#e9b949" stroke="#9c7a1e"/>')
            else:
                vert = abs(pb[1] - pa[1]) > abs(pb[0] - pa[0])
                w_, h_ = (12, 24) if vert else (24, 12)
                s.add(f'<rect x="{cx - w_ / 2}" y="{cy - h_ / 2}" width="{w_}" height="{h_}" rx="4" fill="#f4a261" stroke="#333"/>')
                bx = cx + (pb[0] - pa[0]) * 0.18 - (2 if not vert else w_ / 2)
                by = cy + (pb[1] - pa[1]) * 0.18 - (2 if vert else h_ / 2)
                s.add(f'<rect x="{bx}" y="{by}" width="{w_ if vert else 4}" height="{4 if vert else h_}" fill="#111"/>')
            vert = abs(pb[1] - pa[1]) > abs(pb[0] - pa[0])
            s.text(cx + (20 if vert else 0), cy + (4 if vert else -14), ref, 11, "#fff", "start" if vert else "middle", "bold")
    pads = sorted(((k[4:], tuple(v[0])) for k, v in LAYOUT["parts"].items() if k.startswith("pad_")), key=lambda t: (t[1][1], t[1][0]))
    for i, (n, c) in enumerate(pads):
        x, y = xy(*c)
        t, col = PADTXT[n]
        s.add(f'<circle cx="{x}" cy="{y}" r="13" fill="{col}" stroke="#fff" stroke-width="2"/>')
        s.text(x, y + 5, str(i + 1), 13, "#111" if n in ("K", "3V3") else "#fff", "middle", "bold")
    for i, (net, a, b) in enumerate(wires):
        pa, pb = xy(*a), xy(*b)
        mx, my = (pa[0] + pb[0]) / 2 + 40, (pa[1] + pb[1]) / 2
        path = f"M{pa[0]},{pa[1]} Q{mx},{my} {pb[0]},{pb[1]}"
        s.add(f'<path d="{path}" fill="none" stroke="#000" stroke-opacity=".3" stroke-width="8" stroke-linecap="round"/>')
        s.add(f'<path d="{path}" fill="none" stroke="{NETCOL.get(net, "#999")}" stroke-width="6" stroke-linecap="round"/>')
        s.text(mx + 6, my, f"W{i + 1}", 12, "#fff", "start", "bold")
    # ---------------- abajo
    xy = board(s, 560, 90, True)
    s.text(560 + 120, 78, "Por ABAJO (soldaduras, en espejo)", 14, "#111", "middle", "bold")
    for net, es in traces.items():
        for a, b in es:
            (xa, ya), (xb, yb) = xy(*a), xy(*b)
            s.add(f'<line x1="{xa}" y1="{ya}" x2="{xb}" y2="{yb}" stroke="#b9bcc2" stroke-width="12" stroke-linecap="round"/>')
            s.add(f'<line x1="{xa}" y1="{ya}" x2="{xb}" y2="{yb}" stroke="{NETCOL.get(net, "#999")}" stroke-width="4" stroke-linecap="round"/>')
    for c in f:
        x, y = xy(*c)
        s.add(f'<circle cx="{x}" cy="{y}" r="8" fill="#e5e7ea" stroke="#8d9096"/>')
    for c, n in pins.items():
        x, y = xy(*c)
        s.text(x + (-18 if c[0] == 1 else 18), y + 4, str(n), 10, "#fff", "middle", "bold")
    for i, (net, a, b) in enumerate(wires):
        pa, pb = xy(*a), xy(*b)
        s.add(f'<line x1="{pa[0]}" y1="{pa[1]}" x2="{pb[0]}" y2="{pb[1]}" stroke="#fff" stroke-width="2" stroke-dasharray="4 4"/>')
    # ---------------- leyenda
    y = 775
    for i, (n, c) in enumerate(pads):
        t, col = PADTXT[n]
        x, yy = 60 + (i % 2) * 520, y + (i // 2) * 24
        s.add(f'<line x1="{x}" y1="{yy - 4}" x2="{x + 26}" y2="{yy - 4}" stroke="{col}" stroke-width="6" stroke-linecap="round"/>')
        s.text(x + 34, yy, f"{i + 1}  {lab(*c)}: {t}", 13, "#111", weight="bold")
    yy = y + ((len(pads) + 1) // 2) * 24 + 12
    notes = ["Valores: " + ", ".join(f"{r} {v[1]}" for r, v in PARTS.items()) + ".",
             "Todo de pie. Por abajo, cada raya = unir dos agujeros vecinos con estaño o hilo desnudo.",
             (f"{len(wires)} cable(s) aislado(s) por arriba: " + ", ".join(f"W{i + 1} {lab(*a)}-{lab(*b)} ({n})" for i, (n, a, b) in enumerate(wires)))
             if wires else "Sin cables aislados.",
             "Fuera de la placa: F1 1 A y D1 1N4007 en el cable del OBD 16; C1 470 µF junto al ESP-01.",
             "ESP-01 por cables Dupont: VCC, EN, RST y GPIO0 al +3,3 V del buck; GND a masa; TX, RX y GPIO2 a esta placa.",
             "Comprobar con el polímetro, sin alimentar: entre +12 V, +3,3 V, K y masa no debe pitar nada."]
    for i, t in enumerate(notes):
        s.text(60, yy + i * 20, "• " + t, 12, "#333")
    s.save("pequena_lm339.svg")


if __name__ == "__main__":
    f, holes = fixed_cells()
    traces, wires, used = route_all(f)
    check(f, traces, wires, used)
    draw(f, traces, wires)
