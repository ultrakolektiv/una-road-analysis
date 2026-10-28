"""Minimalni pisac DXF (R12, ASCII) bez vanjskih biblioteka – otvara se u AutoCAD-u, BricsCAD-u, DraftSight-u, LibreCAD-u…
Kodna strana ANSI_1250 (č ć š ž đ). Jedinica crteža: metar."""
import math

LTYPES = {
    "CONTINUOUS": ("Solid line", []),
    "DASHED": ("Dashed", [6.0, -3.0]),            # relativne dužine (puta ltscale)
    "DASHDOT": ("Dash dot", [8.0, -2.0, 0.5, -2.0]),
    "DOT": ("Dot", [0.5, -2.5]),
}


class Dxf:
    def __init__(self, ltscale=1.0):
        self.layers = {}; self.ents = []; self.ltscale = ltscale
        self.ext = [1e18, 1e18, -1e18, -1e18]
        self.layer("0", 7); self.items = []

    def layer(self, name, color=7, ltype="CONTINUOUS"):
        self.layers[name] = (color, ltype)

    def _e(self, x, y):
        self.ext[0] = min(self.ext[0], x); self.ext[1] = min(self.ext[1], y); self.ext[2] = max(self.ext[2], x); self.ext[3] = max(self.ext[3], y)

    @staticmethod
    def _f(v): return f"{v:.4f}"

    def _head(self, kind, layer, color=None, ltype=None):
        s = ["0", kind, "8", layer]
        if ltype: s += ["6", ltype]
        if color is not None: s += ["62", str(color)]
        return s

    def line(self, layer, x1, y1, x2, y2, color=None, ltype=None):
        self._e(x1, y1); self._e(x2, y2); self.items.append(("L", layer, color, ltype, [(x1, y1), (x2, y2)], None))
        self.ents += self._head("LINE", layer, color, ltype) + ["10", self._f(x1), "20", self._f(y1), "30", "0.0", "11", self._f(x2), "21", self._f(y2), "31", "0.0"]

    def poly(self, layer, pts, closed=False, color=None, ltype=None, width=None):
        if len(pts) < 2: return
        self.items.append(("P", layer, color, ltype, list(pts), width))
        s = self._head("POLYLINE", layer, color, ltype) + ["66", "1", "10", "0.0", "20", "0.0", "30", "0.0", "70", "1" if closed else "0"]
        if width: s += ["40", self._f(width), "41", self._f(width)]
        for x, y in pts:
            self._e(x, y); s += ["0", "VERTEX", "8", layer, "10", self._f(x), "20", self._f(y), "30", "0.0"]
        s += ["0", "SEQEND", "8", layer]
        self.ents += s

    def circle(self, layer, x, y, r, color=None):
        self._e(x - r, y - r); self._e(x + r, y + r)
        self.ents += self._head("CIRCLE", layer, color) + ["10", self._f(x), "20", self._f(y), "30", "0.0", "40", self._f(r)]

    def text(self, layer, x, y, h, txt, rot=0.0, align="l", color=None):
        self.items.append(("T", layer, color, None, (x, y, h, txt, rot, align), None))
        """align: l (lijevo), c (sredina), r (desno) – vertikalno: osnovna linija."""
        self._e(x, y); self._e(x + h * len(txt) * 0.6 * math.cos(math.radians(rot)), y + h * len(txt) * 0.6 * math.sin(math.radians(rot)))
        s = self._head("TEXT", layer, color) + ["10", self._f(x), "20", self._f(y), "30", "0.0", "40", self._f(h), "1", txt, "50", self._f(rot), "7", "STANDARD"]
        if align in ("c", "r"):
            s += ["72", "1" if align == "c" else "2", "11", self._f(x), "21", self._f(y), "31", "0.0"]
        self.ents += s

    def save(self, path):
        o = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$DWGCODEPAGE", "3", "ANSI_1250",
             "9", "$LTSCALE", "40", self._f(self.ltscale),              "9", "$EXTMIN", "10", self._f(self.ext[0] if self.ext[0] < 1e17 else 0), "20", self._f(self.ext[1] if self.ext[1] < 1e17 else 0),
             "9", "$EXTMAX", "10", self._f(self.ext[2] if self.ext[2] > -1e17 else 1), "20", self._f(self.ext[3] if self.ext[3] > -1e17 else 1),
             "0", "ENDSEC", "0", "SECTION", "2", "TABLES"]
        o += ["0", "TABLE", "2", "LTYPE", "70", str(len(LTYPES))]
        for n, (d, pat) in LTYPES.items():
            tot = sum(abs(p) for p in pat)
            o += ["0", "LTYPE", "2", n, "70", "64", "3", d, "72", "65", "73", str(len(pat)), "40", self._f(tot)] + sum([["49", self._f(p)] for p in pat], [])
        o += ["0", "ENDTAB", "0", "TABLE", "2", "LAYER", "70", str(len(self.layers))]
        for n, (c, lt) in self.layers.items(): o += ["0", "LAYER", "2", n, "70", "0", "62", str(c), "6", lt]
        o += ["0", "ENDTAB", "0", "TABLE", "2", "STYLE", "70", "1", "0", "STYLE", "2", "STANDARD", "70", "0", "40", "0.0", "41", "1.0", "50", "0.0", "71", "0", "42", "2.5", "3", "arial.ttf", "4", "",
              "0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "BLOCKS", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
        o += self.ents + ["0", "ENDSEC", "0", "EOF"]
        with open(path, "w", encoding="cp1250", errors="replace", newline="") as f:
            f.write("\r\n".join(o) + "\r\n")


ACI = {1: "#e41a1c", 2: "#d4b000", 3: "#2ca02c", 4: "#00a0c0", 5: "#1f3fd0", 6: "#c020c0", 7: "#000000", 8: "#808080", 30: "#ff7f00", 202: "#a0409a", 140: "#4060a0", 253: "#c0c0c0", 150: "#3060a0", 40: "#ffa060", 82: "#60a060", 74: "#40a0a0", 200: "#c060c0", 210: "#d080d0", 240: "#c0105a", 12: "#990000", 52: "#8b5a2b", 53: "#a0702b"}


def preview(d, path, box=None, figsize=(16, 9), dpi=130):
    """Slika crteža (matplotlib) iz zabilježenih entiteta – za kontrolu prije otvaranja u CADu."""
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=figsize)
    for kind, layer, color, lt, data, wd in d.items:
        c = color if color is not None else d.layers.get(layer, (7, "CONTINUOUS"))[0]
        lt = lt or d.layers.get(layer, (7, "CONTINUOUS"))[1]
        col = ACI.get(c, "#000000"); ls = {"DASHED": (0, (4, 2)), "DASHDOT": (0, (5, 2, 1, 2)), "DOT": (0, (1, 2))}.get(lt, "-")
        if kind in ("L", "P"):
            xs = [p[0] for p in data]; ys = [p[1] for p in data]
            if box and (max(xs) < box[0] or min(xs) > box[2] or max(ys) < box[1] or min(ys) > box[3]): continue
            ax.plot(xs, ys, color=col, lw=(1.4 if wd else 0.6), ls=ls)
        elif kind == "T":
            x, y, h, txt, rot, al = data
            if box and not (box[0] <= x <= box[2] and box[1] <= y <= box[3]): continue
            ax.text(x, y, txt, rotation=rot, rotation_mode="anchor", ha={"l": "left", "c": "center", "r": "right"}[al], va="baseline", fontsize=max(2.0, h * 1.1 * (figsize[0] * 72 / ((box[2] - box[0]) if box else (d.ext[2] - d.ext[0])))), color=col)
    ax.set_aspect("equal"); ax.ticklabel_format(useOffset=False, style="plain")
    if box: ax.set_xlim(box[0], box[2]); ax.set_ylim(box[1], box[3])
    ax.tick_params(labelsize=6); plt.tight_layout(); plt.savefig(path, dpi=dpi); plt.close()
