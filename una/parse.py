"""Čitanje ispisa projektanta: horizontalna osovina, uzdužni profil, poprečni nagibi."""
from .i18n import _T, _TF
import re, math
import numpy as np

_DMS = re.compile(r"(\d+)d(\d+)'(\d+)\"")
_ELEM = re.compile(r"^\s*\d+\s+(PRAVAC|KRUZNI_LUK|PRIJELAZNICA)\s+\d+")


def _read(path, encodings=("cp1250", "utf-8", "latin-1")):
    raw = open(path, "rb").read()
    for enc in encodings:
        try:
            return raw.decode(enc).replace("\x1a", "").splitlines()
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1").splitlines()


def _ang(s):
    m = _DMS.search(s)
    return int(m[1]) + int(m[2]) / 60 + int(m[3]) / 3600 if m else None


class Axis:
    """Jedna osovina: horizontalni elementi, niveleta i poprečni nagibi."""

    def __init__(self, name, hfile, vfile, xfile, cs_col=None):
        self.name = name
        self.files = (hfile, vfile, xfile)
        self._parse_h(hfile)
        self._parse_v(vfile)
        self._parse_x(xfile, cs_col)

    # ------------------------------------------------------------ horizontal
    def _parse_h(self, path):
        t = _read(path)
        elems = []
        for i, l in enumerate(t):
            if _ELEM.match(l):
                k = l.split(); l2 = t[i + 1].split(); l3 = t[i + 2].split()
                if l2[1] == "BESK" or (l2[2] != "BESK" and abs(float(l2[2])) > 1e5):
                    A = None; L = float(l2[0]); R1 = l2[1]
                else:
                    A = float(l2[0]); L = float(l2[1]); R1 = l2[2]
                rd = lambda x: math.inf if x == "BESK" else float(x)
                elems.append(dict(no=int(k[0]), typ=k[1], s0=float(k[3]), s1=float(l3[0]), L=L, A=A,
                                  R0=rd(k[4]), R1=rd(R1), Y0=float(k[5]), X0=float(k[6]), nu0=_ang(k[7]),
                                  dnu=(_ang(t[i + 1]) or 0.0) if k[1] != "PRAVAC" else 0.0))
        if not elems:
            raise ValueError(_TF('{0}: nije pronađen nijedan element (PRAVAC / KRUZNI_LUK / PRIJELAZNICA)', path))
        self.elems = elems
        Y, X = elems[0]["Y0"], elems[0]["X0"]; nu = math.radians(elems[0]["nu0"])
        plan = [(elems[0]["s0"], Y, X)]
        for e in elems:
            k0 = 0 if math.isinf(e["R0"]) else 1 / e["R0"]; k1 = 0 if math.isinf(e["R1"]) else 1 / e["R1"]
            n = max(2, int(e["L"] / 0.25)); ds = e["L"] / n
            for j in range(n):
                kk = k0 + (k1 - k0) * (j + 0.5) / n; mid = nu + 0.5 * kk * ds
                X += ds * math.cos(mid); Y += ds * math.sin(mid); nu += kk * ds
                if j % 20 == 19 or j == n - 1:
                    plan.append((e["s0"] + (j + 1) * ds, Y, X))
        self.plan = np.array(plan)
        ii = [i for i, l in enumerate(t) if _ELEM.match(l)][-1]
        tk = t[ii + 1].split(); o = -4 if "d" in tk[-2] else -3
        self.end_err = (Y - float(tk[o]), X - float(tk[o + 1]))
        self.length = sum(e["L"] for e in elems)
        self.K = sum(abs(e["dnu"]) for e in elems) * 10 / 9 / (self.length / 1000)
        self.K_file = None
        for l in t:
            m = re.search(r"Grad/Km\)\s*:\s*([\d.]+)", l)
            if m: self.K_file = float(m[1])
        self.s_min = elems[0]["s0"]; self.s_max = elems[-1]["s1"]
        self.s0 = np.array([e["s0"] for e in elems])

    # ------------------------------------------------------------ vertical
    def _parse_v(self, path):
        v = _read(path)
        pis = []; started = False
        for l in v:
            if l.strip() == "&":
                if pis: break
                continue
            p = l.split()
            if len(p) == 6 and not l.startswith("*"):
                try: pis.append([float(x) for x in p])
                except ValueError: pass
        if not pis:
            raise ValueError(_TF('{0}: nije pronađena tabela prelomnih tačaka nivelete', path))
        pis[0][5] = pis[0][4]; pis[-1][5] = pis[-1][4]
        self.pis = pis
        # kontrolne kote iz ispisa poprečnih profila (ako postoje)
        ctrl = []
        for l in v:
            m = re.match(r"^\s*(\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$", l)
            if m: ctrl.append((float(m[2]), float(m[4]))); continue
            p = l.split()
            if len(p) == 9 and not l.startswith("*"):
                try: ctrl.append((float(p[1]), float(p[5])))
                except ValueError: pass
        self.vdev = max((abs(self.vert(s)[0] - z) for s, z in ctrl if s >= pis[0][4]), default=None)

    def vert(self, s):
        pis = self.pis
        for idx, p in enumerate(pis):
            s_pi, z_pi, Rv, g_out, TZ, TK = p
            g_prev = pis[idx - 1][3] if idx > 0 else 0.0
            if TK > TZ and TZ <= s <= TK:
                gg = g_prev + (g_out - g_prev) * (s - TZ) / (TK - TZ)
                z = z_pi + g_prev / 100 * (s - s_pi) + (g_out - g_prev) / (200 * (TK - TZ)) * (s - TZ) ** 2
                return z, gg
        last = None
        for idx, p in enumerate(pis):
            if p[5] <= s: last = idx
        if last is None:
            return pis[0][1] + pis[0][3] / 100 * (s - pis[0][0]), pis[0][3]
        p = pis[last]
        return p[1] + p[3] / 100 * (s - p[0]), p[3]

    # ------------------------------------------------------------ cross slopes
    def _parse_x(self, path, cs_col):
        rows = []; heads = None
        for l in _read(path, ("utf-8", "cp1250", "latin-1")):
            if "TRAK_" in l and heads is None:
                heads = [h for h in l.split() if h.startswith("TRAK_")]
            p = l.split()
            if len(p) >= 4 and not l.startswith("*"):
                try: rows.append([float(x) for x in p])
                except ValueError: pass
        if not rows:
            raise ValueError(_TF('{0}: nisu pronađeni poprečni nagibi', path))
        n = len(rows[0]) - 2
        self.cs_heads = heads if heads and len(heads) == n else [f"TRAK_{i + 1}" for i in range(n)]
        self.cs_s = np.array([r[0] * 1000 + r[1] for r in rows])
        self.cs_val = np.array([r[2:] for r in rows])
        if cs_col is None:
            cs_col = {2: 0, 4: 0, 6: 1}.get(n, max(0, n // 2 - 2))
        self.cs_left = cs_col; self.cs_right = n - 1 - cs_col
        self.cs_l = self.cs_val[:, self.cs_left]; self.cs_d = self.cs_val[:, self.cs_right]
        self.cs_mirror = float(np.abs(self.cs_l + self.cs_d).max())

    # ------------------------------------------------------------ helpers
    def elem_index(self, s):
        i = int(np.searchsorted(self.s0, s, side="right")) - 1
        return min(max(i, 0), len(self.elems) - 1)

    def cross(self, s):
        return float(np.interp(s, self.cs_s, self.cs_l))

    def info(self):
        return (_TF('{0}: {1} elemenata, dužina {2:.3f} m (st. {3:.3f}–{4:.3f}), K = {5:.3f} gon/km', self.name, len(self.elems), self.length, self.s_min, self.s_max, self.K) + (_TF(' (ispis {0})', self.K_file) if self.K_file else "") +
                _TF(", odstupanje kraja {0:.0f} mm", max(abs(self.end_err[0]), abs(self.end_err[1])) * 1000) +
                (_TF(", odstupanje nivelete {0:.0f} mm", self.vdev * 1000) if self.vdev is not None else ""))


def detect_kind(path):
    """Prepoznaje vrstu ispisa po sadržaju: 'h' horizontala, 'x' poprečni nagibi, 'v' uzdužni profil."""
    txt = "\n".join(_read(path, ("utf-8", "cp1250", "latin-1")))
    if re.search(r"^\s*\d+\s+(PRAVAC|KRUZNI_LUK|PRIJELAZNICA)\s+\d+", txt, re.M): return "h"
    if re.search(r"UZD\.?\s*PAD|VIS\.?\s*T\.?|\bEKSTREM\b", txt, re.I): return "v"     # uzdužni ispis može sadržati i tabelu poprečnih (TRAK_), pa se prvo traže njegove oznake
    if "TRAK_" in txt: return "x"
    return "v"
