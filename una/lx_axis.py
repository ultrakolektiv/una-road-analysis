"""Osovine iz Civil 3D LandXML-a kao ulaz proračuna (umjesto ispisa projektanta): horizontala, niveleta i poprečni nagibi iz presjeka."""
import os, math, hashlib, tempfile, pickle
import xml.etree.ElementTree as ET
import numpy as np
from .i18n import _T, _TF
from .parse import Axis
from . import corridor as C

SURF_PRIO = ("Pave1", "Sloj1_vrh", "Sloj1", "Ploca_mosta", "Top")      # površ kolovoza (redoslijed prioriteta)


def split_ref(ref):
    """'datoteka.xml#DESNA' → ('datoteka.xml', 'DESNA'); None ako nije LandXML referenca."""
    if isinstance(ref, str) and "#" in ref:
        p, n = ref.rsplit("#", 1)
        if p.lower().endswith(".xml"): return p, n
    return None


def _lane_slopes(secs, w):
    """Poprečni nagib lijeve/desne trake [%] iz presjeka: (z(∓w) − z(0)) / w · 100; z = gornja ivica površi kolovoza."""
    for nm in SURF_PRIO:
        segs = [(a[0], a[1], b[0], b[1]) for n, _, pp in secs if n == nm for a, b in zip(pp, pp[1:])]
        if not segs: continue
        top = C._envelope(segs, 0.05)
        if len(top) < 2: continue
        px = [abs(p[0]) for n, _, pp in secs if n == nm for p in pp]
        cross0 = any(a[0] * b[0] < 0 for n, _, pp in secs if n == nm for a, b in zip(pp, pp[1:]))
        g = 0.0 if (cross0 or not px or min(px) <= 0.3) else min(px)                      # unutrašnja ivica kolovoza (centralna osovina: pola razdjelnog pojasa)
        if min(p[0] for p in top) > -(g + w) + 0.05 or max(p[0] for p in top) < g + w - 0.05: continue
        zl0, zd0 = (C._zi(top, -g), C._zi(top, g)) if g else (C._zi(top, 0.0),) * 2
        return 100 * (C._zi(top, -(g + w)) - zl0) / w, 100 * (C._zi(top, g + w) - zd0) / w, g, max(px)
    return None


def load_axes(path, log=print, w=3.5):
    """Čita sve osovine iz LandXML-a: {ime: dict(sta0, elems, pvi, cs_s, cs_l, cs_d)}. Rezultat se kešira."""
    key = hashlib.md5(f"lxaxes2|{os.path.abspath(path)}|{os.path.getsize(path)}|{os.path.getmtime(path)}|{w}".encode()).hexdigest()
    cache = os.path.join(tempfile.gettempdir(), f"una_lxosa_{key}.pkl")
    if os.path.isfile(cache):
        try: return pickle.load(open(cache, "rb"))
        except Exception: pass
    log(_TF("LandXML osovine: čitam {0} ({1:.0f} MB) – može potrajati nekoliko minuta …", os.path.basename(path), os.path.getsize(path) / 1e6))
    al = {}; cur = None; stack = []
    for ev, el in ET.iterparse(path, events=("start", "end")):
        t = C._tag(el)
        if ev == "start":
            stack.append(t)
            if t == "Alignment": cur = el.get("name"); al[cur] = dict(sta0=C._f(el.get("staStart")), elems=None, pvi=[], cs=[])
            continue
        stack.pop()
        if t == "CoordGeom" and cur in al: al[cur]["elems"] = C._parse_align_cg(el)
        elif t == "Profile" and cur in al:
            if not al[cur]["pvi"]: al[cur]["pvi"] = C._parse_profile(el)
            el.clear()
        elif t == "CrossSect" and cur in al:
            secs = []
            for ch in el:
                if C._tag(ch) != "DesignCrossSectSurf" or ch.get("name") not in SURF_PRIO: continue
                pp = []
                for g in ch:
                    a = (g.text or "").split()
                    if len(a) >= 2: pp.append((float(a[0]), float(a[1]), g.get("code")))
                secs.append((ch.get("name"), ch.get("side"), pp))
            r = _lane_slopes(secs, w)
            if r: al[cur]["cs"].append((C._f(el.get("sta")), r[0], r[1])); al[cur].setdefault("geo", []).append((r[2], r[3]))
            el.clear()
        elif t in ("P", "F"): el.clear()
    for k, v in al.items():
        if not v["elems"]: raise ValueError(_TF("Koridor: osovina '{0}' nema geometriju (CoordGeom).", k))
        v["cs"].sort()
    try: pickle.dump(al, open(cache, "wb"))
    except Exception: pass
    return al


def alignments_info(path, log=print):
    al = load_axes(path, log)
    out = []
    for nm in al:
        ax = AxisLX(nm, path, al[nm])
        gg = al[nm].get("geo") or [(0.0, 3.85)]; g = float(np.median([a for a, _ in gg])); em = float(np.median([b for _, b in gg]))
        out.append(dict(name=nm, lo=float(ax.s_min), hi=float(ax.s_max), cs_lo=float(ax.cs_s.min()), cs_hi=float(ax.cs_s.max()), n=len(ax.elems), g=round(g, 2), lanes=max(1, int(round((em - g - 0.35) / 3.5)))))
    return out


class AxisLX(Axis):
    """Osovina u istom obliku kao Axis iz ispisa (elems, plan, pis, cs_*), ali iz LandXML-a."""

    def __init__(self, name, path, d):
        self.name = name; ref = f"{path}#{name}"; self.files = (ref, ref, ref)
        A = C.Align(name, d["sta0"], d["elems"]); A.pvi = d["pvi"]
        self._horizontal(A); self._vertical(d["pvi"])
        cs = d["cs"]
        if not cs: raise ValueError(_TF("LandXML osovina '{0}': u presjecima nema površi kolovoza za poprečne nagibe.", name))
        a = np.array(cs, float); self.cs_s = a[:, 0]; self.cs_val = a[:, 1:3]
        self.cs_heads = ["TRAK_L1", "TRAK_D1"]; self.cs_left = 0; self.cs_right = 1
        self.cs_l = self.cs_val[:, 0]; self.cs_d = self.cs_val[:, 1]; self.cs_mirror = float(np.abs(self.cs_l + self.cs_d).max())
        self.vdev = None

    def _horizontal(self, A):
        elems = []; sta = A.sta0; Y = X = None
        typ = {"Line": "PRAVAC", "Curve": "KRUZNI_LUK", "Spiral": "PRIJELAZNICA"}
        H = np.unwrap(A.NU)
        for i, e in enumerate(A.elems):
            L = float(e["length"]); n0, e0 = e["start"]
            nu0 = float(np.interp(sta, A.S, H)); k0 = k1 = 0.0
            if e["type"] == "Curve": sg = 1.0 if e["rot"] == "cw" else -1.0; R0 = R1 = sg * e["radius"]; Aa = None
            elif e["type"] == "Spiral":
                sg = 1.0 if e["rot"] == "cw" else -1.0
                R0 = math.inf if e["rs"] == math.inf else sg * e["rs"]; R1 = math.inf if e["re"] == math.inf else sg * e["re"]
                Rf = [abs(r) for r in (R0, R1) if not math.isinf(r)]; Aa = math.sqrt(Rf[0] * L) if Rf else None
            else: R0 = R1 = math.inf; Aa = None
            k0 = 0.0 if math.isinf(R0) else 1 / R0; k1 = 0.0 if math.isinf(R1) else 1 / R1
            dnu = math.degrees(abs((k0 + k1) / 2 * L))
            elems.append(dict(no=i + 1, typ=typ[e["type"]], s0=sta, s1=sta + L, L=L, A=Aa, R0=R0, R1=R1, Y0=e0, X0=n0,
                              nu0=math.degrees(nu0) % 360.0, dnu=dnu))
            sta += L
        self.elems = elems
        step = 5.0; ss = np.arange(A.sta0, A.s_end, step); ss = np.append(ss, A.s_end)
        N, E = A.pos(ss); self.plan = np.c_[ss, E, N]
        self.end_err = (0.0, 0.0); self.length = sum(e["L"] for e in elems)
        self.K = sum(e["dnu"] for e in elems) * 10 / 9 / (self.length / 1000); self.K_file = None
        self.s_min = elems[0]["s0"]; self.s_max = elems[-1]["s1"]; self.s0 = np.array([e["s0"] for e in elems])

    def _vertical(self, pvi):
        P = [p for p in pvi]
        if len(P) < 2: raise ValueError(_T("LandXML: niveleta nema prelomnih tačaka."))
        # P: (s, z, L parabole); prvi i posljednji su PVI bez parabole
        pis = []
        for i, (s, z, L) in enumerate(P):
            g_out = 0.0
            if i < len(P) - 1: g_out = (P[i + 1][1] - z) / (P[i + 1][0] - s) * 100
            elif i > 0: g_out = (z - P[i - 1][1]) / (s - P[i - 1][0]) * 100
            g_in = (z - P[i - 1][1]) / (s - P[i - 1][0]) * 100 if i > 0 else g_out
            Rv = (L * 100 / (g_out - g_in)) if (L > 0.01 and abs(g_out - g_in) > 1e-9) else 0.0
            TZ, TK = (s - L / 2, s + L / 2) if (0 < i < len(P) - 1 and L > 0.01) else (s, s)
            pis.append([s, z, Rv, g_out, TZ, TK])
        self.pis = pis
