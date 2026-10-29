"""Uvoz koridora iz Civil 3D-a (LandXML 1.2) i priprema podataka za vožnju kroz koridor.

Čita strujno (datoteka može imati stotine MB): osovine (CoordGeom), nivelete (ProfAlign), poprečne presjeke koridora (CrossSect → DesignCrossSectSurf)
i teren (Surface/TIN). Izlaz je kompaktna struktura za una/data/koridor.html (vidi build_scene).

Konvencije LandXML-a: koordinate 'sjever istok', azimut u stepenima od sjevera u smjeru kazaljke, ofset presjeka + = desno u smjeru stacionaže,
visine presjeka su relativne u odnosu na niveletu osovine."""
import math, os, pickle, hashlib, tempfile
import xml.etree.ElementTree as ET
import numpy as np
from .i18n import _T, _TF

NS = "{http://www.landxml.org/schema/LandXML-1.2}"


def _tag(el): return el.tag.rsplit("}", 1)[-1]


def _f(s, d=0.0):
    try: return float(s)
    except (TypeError, ValueError): return d


# ----------------------------------------------------------------------------------------------- osovina
class Align:
    """Osovina iz LandXML-a: plan (integracija elemenata) i niveleta (PVI + parabole)."""

    def __init__(self, name, sta0, elems):
        self.name = name; self.sta0 = sta0; self.elems = elems
        self._build(); self.pvi = []

    def _build(self):
        S, N, E, NU = [], [], [], []; sta = self.sta0; nu = None
        for e in self.elems:
            n0, e0 = e["start"]; L = e["length"]
            if e["type"] == "Line":
                if "end" in e: nu = math.atan2(e["end"][1] - n0 + 0.0 * e0, 0.0) if False else math.atan2(e["end"][1] - e0, e["end"][0] - n0)
                else: nu = math.radians(e["dir"])
                k0 = k1 = 0.0
            elif e["type"] == "Curve":
                sg = 1.0 if e["rot"] == "cw" else -1.0; k0 = k1 = sg / e["radius"]
                if nu is None: nu = math.radians(e["dirStart"])
            else:
                sg = 1.0 if e["rot"] == "cw" else -1.0
                k0 = 0.0 if e["rs"] == math.inf else sg / e["rs"]; k1 = 0.0 if e["re"] == math.inf else sg / e["re"]
                if nu is None: nu = math.radians(e["dirStart"])
            n = max(2, int(math.ceil(L / 0.5))); d = L / n; X, Y = n0, e0
            S.append(sta); N.append(X); E.append(Y); NU.append(nu)
            for j in range(n):
                kk = k0 + (k1 - k0) * (j + 0.5) / n; mid = nu + 0.5 * kk * d
                X += d * math.cos(mid); Y += d * math.sin(mid); nu += kk * d
                S.append(sta + (j + 1) * d); N.append(X); E.append(Y); NU.append(nu)
            # sljedeći element počinje od vlastite Start tačke (bez driftanja); azimut se prenosi
            sta += L
        self.S = np.array(S); self.N = np.array(N); self.E = np.array(E); self.NU = np.array(NU)
        self.s_end = sta

    def pos(self, s):
        s = np.asarray(s, float)
        return np.interp(s, self.S, self.N), np.interp(s, self.S, self.E)

    def heading(self, s):
        s = np.asarray(s, float); h = np.unwrap(self.NU)
        return np.interp(s, self.S, h)

    def curvature(self, s):
        s = np.asarray(s, float); h = np.unwrap(self.NU)
        ds = np.diff(self.S); m = ds > 1e-9
        k = np.diff(h)[m] / ds[m]; mid = (self.S[:-1] + self.S[1:])[m] / 2
        return np.interp(s, mid, k)                                              # + = desno (azimut raste)

    def z(self, s):
        """Nivelete: PVI (s, z) i ParaCurve (s_pvi, z_pvi, L)."""
        s = np.atleast_1d(np.asarray(s, float)); P = self.pvi
        if not P: return np.zeros_like(s)
        ps = np.array([p[0] for p in P]); pz = np.array([p[1] for p in P]); pl = np.array([p[2] for p in P])
        g = np.diff(pz) / np.diff(ps)
        out = np.interp(s, ps, pz)                                               # pravci između PVI
        for i in range(1, len(P) - 1):
            L = pl[i]
            if L <= 0: continue
            gi, go = g[i - 1], g[i]; b = ps[i] - L / 2; m = (s >= b) & (s <= ps[i] + L / 2)
            x = s[m] - b; out[m] = pz[i] - gi * L / 2 + gi * x + (go - gi) * x * x / (2 * L)
        return out


def _parse_align(el):
    elems = []; cg = next((c for c in el if _tag(c) == "CoordGeom"), None)
    if cg is None: return None
    for g in cg:
        t = _tag(g)
        if t not in ("Line", "Curve", "Spiral"): continue
        st = next((c for c in g if _tag(c) == "Start"), None)
        if st is None: continue
        p = st.text.split(); d = dict(type=t, length=_f(g.get("length")), start=(float(p[0]), float(p[1])))
        en = next((c for c in g if _tag(c) == "End"), None)
        if en is not None: q = en.text.split(); d["end"] = (float(q[0]), float(q[1]))
        if t == "Line": d["dir"] = _f(g.get("dir"))
        elif t == "Curve": d.update(rot=g.get("rot", "cw"), radius=_f(g.get("radius"), 1e9), dirStart=_f(g.get("dirStart")))
        else:
            rs, re_ = g.get("radiusStart", "INF"), g.get("radiusEnd", "INF")
            d.update(rot=g.get("rot", "cw"), rs=math.inf if rs == "INF" else _f(rs), re=math.inf if re_ == "INF" else _f(re_), dirStart=_f(g.get("dirStart")))
        elems.append(d)
    return elems


def _parse_profile(pr):
    out = []
    for pa in pr:
        if _tag(pa) != "ProfAlign": continue
        for k in pa:
            t = _tag(k); a = (k.text or "").split()
            if t in ("PVI", "ParaCurve") and len(a) >= 2: out.append((float(a[0]), float(a[1]), _f(k.get("length")) if t == "ParaCurve" else 0.0))
        break
    return out


# ----------------------------------------------------------------------------------------------- čitanje datoteke
def load_landxml(path, s_from, s_to, log=print, margin=60.0):
    """Jedan prolaz kroz datoteku. Vraća dict: aligns{name: Align}, sect{name: [(sta, [(ime, strana, [(ofs, z, kod),…]),…]),…]}, tin (Nx3 sjever/istok/z), faces (Mx3)."""
    key = hashlib.md5(f"{os.path.abspath(path)}|{os.path.getsize(path)}|{os.path.getmtime(path)}|{s_from}|{s_to}".encode()).hexdigest()
    cache = os.path.join(tempfile.gettempdir(), f"una_koridor_{key}.pkl")
    if os.path.isfile(cache):
        try:
            R = pickle.load(open(cache, "rb")); log(_T("Koridor: učitano iz privremene memorije (cache).")); return R
        except Exception: pass
    log(_TF("Koridor: čitam {0} ({1:.0f} MB) – može potrajati nekoliko minuta …", os.path.basename(path), os.path.getsize(path) / 1e6))
    aligns = {}; sect = {}; al_name = None; stack = []; pts = []; ids = {}; faces = []; pcount = 0
    for ev, el in ET.iterparse(path, events=("start", "end")):
        t = _tag(el)
        if ev == "start":
            stack.append(t)
            if t == "Alignment": al_name = el.get("name"); aligns[al_name] = dict(sta0=_f(el.get("staStart")), elems=None, pvi=[])
            continue
        stack.pop()
        if t == "CoordGeom":
            aligns[al_name]["elems"] = _parse_align_cg(el)
        elif t == "Profile" and al_name in aligns:
            if not aligns[al_name]["pvi"]: aligns[al_name]["pvi"] = _parse_profile(el)
            el.clear()
        elif t == "CrossSect":
            sta = _f(el.get("sta"))
            if s_from - margin <= sta <= s_to + margin:
                secs = []
                for ch in el:
                    if _tag(ch) != "DesignCrossSectSurf": continue
                    pp = []
                    for g in ch:
                        a = (g.text or "").split()
                        if len(a) >= 2: pp.append((float(a[0]), float(a[1]), g.get("code")))
                    secs.append((ch.get("name"), ch.get("side"), pp))
                sect.setdefault(al_name, []).append((sta, secs))
            el.clear()
        elif t == "P" and stack[-1] == "Pnts":
            a = el.text.split(); ids[el.get("id")] = len(pts); pts.append((float(a[0]), float(a[1]), float(a[2]))); el.clear()
        elif t == "F" and stack[-1] == "Faces":
            if el.get("i") != "1" and el.text:
                a = el.text.split()
                if len(a) == 3: faces.append((a[0], a[1], a[2]))
            el.clear()
    for k, v in aligns.items():
        if not v["elems"]: raise ValueError(_TF("Koridor: osovina '{0}' nema geometriju (CoordGeom).", k))
    A = {}
    for k, v in aligns.items():
        a = Align(k, v["sta0"], v["elems"]); a.pvi = v["pvi"]; A[k] = a
    tin = np.array(pts, float) if pts else np.zeros((0, 3))
    fc = np.array([[ids[x] for x in f] for f in faces if all(x in ids for x in f)], int) if faces else np.zeros((0, 3), int)
    # zadrži samo teren oko koridora
    if len(tin) and sect:
        xs = np.concatenate([A[k].pos([s_from, (s_from + s_to) / 2, s_to])[0] for k in A]); ys = np.concatenate([A[k].pos([s_from, (s_from + s_to) / 2, s_to])[1] for k in A])
        # TIN pokriva i mnogo veće područje; filtriraj po koridoru (guste tačke osovine)
        ss = np.linspace(s_from, s_to, 200); cx = np.concatenate([A[k].pos(ss)[0] for k in A]); cy = np.concatenate([A[k].pos(ss)[1] for k in A])
        keep = np.zeros(len(tin), bool)
        from scipy.spatial import cKDTree
        d, _ = cKDTree(np.c_[cx, cy]).query(tin[:, :2]); keep = d < 320.0
        remap = -np.ones(len(tin), int); remap[keep] = np.arange(keep.sum())
        fm = keep[fc].all(axis=1) if len(fc) else np.zeros(0, bool)
        tin = tin[keep]; fc = remap[fc[fm]] if len(fc) else fc
    for k in sect: sect[k].sort(key=lambda r: r[0])
    R = dict(aligns=A, sect=sect, tin=tin, faces=fc)
    try: pickle.dump(R, open(cache, "wb"))
    except Exception: pass
    log(_TF("Koridor: {0} osovina, {1} presjeka u rasponu, teren {2} tačaka.", len(A), sum(len(v) for v in sect.values()), len(tin)))
    return R


def _parse_align_cg(cg):
    class _W:                       # omotač da _parse_align radi nad CoordGeom elementom
        def __iter__(self): return iter([cg])
    return _parse_align(_W())


# ----------------------------------------------------------------------------------------------- oblik presjeka
ENV_LAYERS = ("Top", "Bankina", "Humus_skarpa", "Curb", "Ivicnjak", "Ivicnjak_sa_procjepom", "Gutter", "Rigol", "Sloj1", "Sloj1_vrh")


def _segments(secs, names):
    out = []
    for nm, side, pp in secs:
        if nm in names:
            for a, b in zip(pp, pp[1:]): out.append((a[0], a[1], b[0], b[1]))
    return out


def _dp(pts, tol):
    if len(pts) < 3: return pts
    a = np.array(pts); keep = np.zeros(len(a), bool); keep[0] = keep[-1] = True; st = [(0, len(a) - 1)]
    while st:
        i, j = st.pop()
        if j <= i + 1: continue
        p0, p1 = a[i], a[j]; d = p1 - p0; n = math.hypot(*d) or 1e-9
        dist = np.abs(d[0] * (a[i + 1:j, 1] - p0[1]) - d[1] * (a[i + 1:j, 0] - p0[0])) / n
        k = int(np.argmax(dist))
        if dist[k] > tol: keep[i + 1 + k] = True; st += [(i, i + 1 + k), (i + 1 + k, j)]
    return [tuple(map(float, r)) for r in a[keep]]


def _envelope(segs, step=0.05):
    if not segs: return []
    S = np.array(segs); lo = min(S[:, 0].min(), S[:, 2].min()); hi = max(S[:, 0].max(), S[:, 2].max())
    g = np.arange(lo, hi + step, step); z = np.full(len(g), -np.inf)
    for x1, z1, x2, z2 in S:
        a, b = (x1, x2) if x1 <= x2 else (x2, x1); m = (g >= a - 1e-9) & (g <= b + 1e-9)
        if not m.any(): continue
        if abs(x2 - x1) < 1e-6: z[m] = np.maximum(z[m], max(z1, z2))
        else: z[m] = np.maximum(z[m], z1 + (z2 - z1) * (g[m] - x1) / (x2 - x1))
    ok = np.isfinite(z)
    if not ok.any(): return []
    z = np.interp(g, g[ok], z[ok])
    return _dp(list(zip(g, z)), 0.012)


def _ring(secs, cz=2.4):
    pts = [(p[0], p[1]) for nm, sd, pp in secs if nm == "Sekundarna_obloga" for p in pp if p[1] > 0.3]
    if not pts: return []
    bins = {}
    for x, z in pts:
        a = math.degrees(math.atan2(z - cz, x)); r = math.hypot(x, z - cz); b = int(round(a / 5.0))
        if b not in bins or r < bins[b][0]: bins[b] = (r, x, z)
    ks = sorted(bins); ring = []
    for b in range(1, 36):
        if b in bins: ring.append((bins[b][1], bins[b][2]))
        else:
            a = math.radians(b * 5.0); lo = [k for k in ks if k < b]; hi = [k for k in ks if k > b]
            if lo and hi:
                r = (bins[lo[-1]][0] + bins[hi[0]][0]) / 2; ring.append((r * math.cos(a), cz + r * math.sin(a)))
    return ring[::-1]            # od desnog zida preko tjemena do lijevog zida? (kut opada: ide od lijevo prema desno -> obrnuto)


def section_geom(secs, rail_off=0.78, add_rails=True):
    """Presjek u stacionažnom okviru (ofset + = desno u smjeru stacionaže, visina relativna na niveletu osovine)."""
    names = {n or "-" for n, _, _ in secs}
    bridge = "Ploca_mosta" in names or "Vijenac" in names; tunnel = "Sekundarna_obloga" in names
    kind = "tunel" if tunnel else ("most" if bridge else "otvorena")
    ref = [p[0] for n, _, pp in secs if n in ("Pave1", "Sloj1", "Sloj1_vrh") for p in pp]
    eL, eR = (min(ref), max(ref)) if ref else (-3.85, 3.85)
    e = max(2.5, min(abs(eL), eR, 3.85))
    top = _envelope(_segments(secs, ENV_LAYERS))
    G = dict(kind=kind, e=e, eL=eL, eR=eR, top=top, gr=int(("Humus_skarpa" in names) or ("Humus_dno" in names)), rails=[], box=[], ring=[])
    bk = [p[0] for n, _, pp in secs if n == "Bankina" for p in pp]
    G["shR"] = max(bk) if bk and max(bk) > 0 else e
    G["shL"] = min(bk) if bk and min(bk) < 0 else -e
    gt = [p[0] for n, _, pp in secs if n in ("Gutter", "Rigol") for p in pp]
    if gt:
        if min(gt) < 0: G["shL"] = min(G["shL"], min(gt))
        if max(gt) > 0: G["shR"] = max(G["shR"], max(gt))
    if kind == "most":
        for sd in (-1, 1):
            pts = [(p[0], p[1]) for n, _, pp in secs if n == "Vijenac" for p in pp if p[0] * sd > e + 0.05]
            if len(pts) >= 3:
                xs = [abs(x) for x, _ in pts]; G["box"].append([ST["parapet"], sd * min(xs), sd * max(xs), max(z for _, z in pts)])
    elif kind == "tunel":
        G["ring"] = [(round(x, 3), round(z, 3)) for x, z in _ring(secs)]
        for sd in (-1, 1):
            pts = [(p[0], p[1]) for n, _, pp in secs if n == "Ploca_staze" for p in pp if p[0] * sd > 0]
            if len(pts) >= 3:
                xs = [abs(x) for x, _ in pts]; G["box"].append([ST["walk"], sd * min(xs), sd * max(xs), max(z for _, z in pts)])
    elif add_rails:
        for sd in (-1, 1): G["rails"].append(sd * (e + rail_off))
    return G


def _zi(top, o):
    if not top: return 0.0
    xs = [p[0] for p in top]; zs = [p[1] for p in top]; return float(np.interp(o, xs, zs))


# stilovi (indeksi se koriste u JavaScript-u)
ST = dict(road=0, ground=1, curb=2, parapet=3, lining=4, walk=5, rail=6, median=7, terrain=8, deck=9)


# ----------------------------------------------------------------------------------------------- scena za HTML
def _dtm_interp(R):
    import matplotlib.tri as mtri
    t = R["tin"]
    if len(t) < 10: return None
    tri = mtri.Triangulation(t[:, 1], t[:, 0], R["faces"])        # x = istok, y = sjever
    return mtri.LinearTriInterpolator(tri, t[:, 2])


def _elem_at(al, s):
    st = al.sta0
    for e in al.elems:
        if s < st + e["length"] + 1e-6: return {"Line": 0, "Spiral": 1, "Curve": 2}[e["type"]]
        st += e["length"]
    return 0


def build_scene(R, s_from, s_to, sight, cfg, h_eye=1.0, log=print):
    """sight: {'F': route, 'B': route} iz vizura.build_data (s, v, g, D, Lz, ok). Vozi se: 'F' = osovina s indeksom 0 u smjeru stacionaže,
    'B' = druga osovina suprotno stacionaži (razdvojeni kolovozi)."""
    from scipy.spatial import cKDTree
    kc = cfg.get("koridor") or {}
    rail_off = float(kc.get("ograda_ofset", 0.78)); add_rails = bool(kc.get("ograde", True))
    dtm = _dtm_interp(R); A = R["aligns"]; names = [n for n in A if n in R["sect"]]
    # F = osovina čije ime počinje sa D (desna), B = ostala
    nF = next((n for n in names if n.upper().startswith("D")), names[0]); nB = next((n for n in names if n != nF), None)
    plan = [("F", nF, nB, +1)] + ([("B", nB, nF, -1)] if nB else [])
    secs_by = {}
    for nm in names:
        keep = []; last = -1e9
        for sta, ss in R["sect"][nm]:
            if s_from - 1 <= sta <= s_to + 1 and sta - last >= 1.2: keep.append((sta, ss)); last = sta
        sta = np.array([r[0] for r in keep]); N, E = A[nm].pos(sta); nu = A[nm].heading(sta)
        secs_by[nm] = dict(sta=sta, N=N, E=E, nu=nu, z0=A[nm].z(sta), G=[section_geom(ss, rail_off, add_rails) for _, ss in keep], k=A[nm].curvature(sta))
    trees = {nm: cKDTree(np.c_[v["E"], v["N"]]) for nm, v in secs_by.items()}
    scene = dict(routes={}, h=h_eye, range=[s_from, s_to], rail_off=rail_off, projekat=cfg.get("projekat", ""))
    for tag, nm, other, sg in plan:
        S = secs_by[nm]; n = len(S["sta"]); order = np.arange(n) if sg > 0 else np.arange(n)[::-1]
        srs = sight.get(tag) or {}; sr = srs.get("D") or srs.get("L")
        q = 0.0; prev = None; out = dict(naziv=_TF("{0} – {1}", nm, _T("smjer stacionaže") if sg > 0 else _T("suprotno stacionaži")), q=[], s=[], x=[], y=[], z=[], tx=[], ty=[], k=[], el=[], v=[], g=[], D=[], Lz=[], ok=[],
                                         kind=[], e=[], gr=[], F=[], rails=[], box=[], ring=[], cs=[])
        for ii in order:
            sta = float(S["sta"][ii]); x, y = float(S["E"][ii]), float(S["N"][ii])
            if prev is not None: q += math.hypot(x - prev[0], y - prev[1])
            prev = (x, y); nu = float(S["nu"][ii]); G = S["G"][ii]; z0 = float(S["z0"][ii])
            nxs, nys = math.cos(nu), -math.sin(nu)                       # desna normala u stacionažnom okviru (E,N)
            # profil u stacionažnom okviru: naš top + susjedni kolovoz (ako je otvorena trasa) + teren
            top = list(G["top"]); pieces = [(ST["road"], top)]
            oth_top = None
            if other and G["kind"] == "otvorena":
                d, j = trees[other].query([x, y])
                if d < 60:
                    Go = secs_by[other]["G"][int(j)]
                    if Go["kind"] == "otvorena":
                        t = (secs_by[other]["E"][j] - x) * nxs + (secs_by[other]["N"][j] - y) * nys
                        dz = float(secs_by[other]["z0"][j]) - z0
                        oth_top = [(o + t, zz + dz) for o, zz in Go["top"]]; oth_e = (Go["e"], t)
            # u okviru vožnje: lat = sg * o
            def drv(tp): return sorted([(sg * o, zz) for o, zz in tp])
            P1 = drv(top); P2 = drv(oth_top) if oth_top else None
            if sg < 0: pass
            pts = list(P1); med = None
            if P2:
                # drugi kolovoz mora biti s lijeve strane (lat manji); inače ignoriši
                if P2[-1][0] < P1[0][0] + 0.2:
                    gap = P1[0][0] - P2[-1][0]
                    if 0.02 < gap < 45: med = (P2[-1][0], P2[-1][1], P1[0][0], P1[0][1])
                    pts = P2 + P1
                else: P2 = None
            # teren izvan (desno od naših, lijevo od krajnjeg)
            terr_R = []; terr_L = []
            if G["kind"] != "tunel" and dtm is not None:
                nxd, nyd = sg * nxs, sg * nys                              # desna normala u okviru vožnje
                for side, (o_end, z_end), lst in ((1, pts[-1], terr_R), (-1, pts[0], terr_L)):
                    for dd in (4, 10, 22, 40, 70, 110, 170, 260):
                        o = o_end + side * dd; zt = dtm(x + nxd * o, y + nyd * o)
                        if np.ma.is_masked(zt) or zt is None: break
                        lst.append((o, float(zt) - z0))
                # preskoči teren ako je "ispod" (most) ili ako počinje iznad kosine ekstremno
                if G["kind"] == "most": terr_R = terr_R[:0]; terr_L = terr_L[:0]
            full = list(reversed(terr_L)) + pts + terr_R
            seg_road = [[round(a, 3), round(b, 3)] for a, b in full]
            # zone: kolovoz(i)
            zones = dict(e=round(G["e"], 3), shL=round(sg * (G["shL"] if sg > 0 else G["shR"]), 3), shR=round(sg * (G["shR"] if sg > 0 else G["shL"]), 3),
                         oe=round(oth_e[0], 3) if oth_top else 0, ot=round(sg * oth_e[1], 3) if oth_top else 0, tn=len(terr_L), tr=len(terr_R), med=[round(v, 3) for v in med] if med else None)
            out["q"].append(round(q, 2)); out["s"].append(round(sta, 2)); out["x"].append(round(x, 3)); out["y"].append(round(y, 3)); out["z"].append(round(z0, 3))
            out["tx"].append(round(sg * math.sin(nu), 5)); out["ty"].append(round(sg * math.cos(nu), 5)); out["k"].append(round(sg * float(S["k"][ii]), 6))
            out["el"].append(_elem_at(A[nm], sta)); out["kind"].append(G["kind"]); out["e"].append(zones); out["gr"].append(G["gr"]); out["F"].append(seg_road)
            out["rails"].append([round(sg * r, 3) for r in (G["rails"] if sg > 0 else G["rails"])] if G["rails"] else [])
            bx = []
            for st_, a_, b_, h_ in G["box"]:
                lo, hi = sorted((sg * a_, sg * b_)); bx.append([st_, round(lo, 3), round(hi, 3), round(h_, 3)])
            out["box"].append(bx); out["ring"].append([[round(sg * a, 3), round(b, 3)] for a, b in G["ring"]])
            # uzdužni nagib iz nivelete
            out["g"].append(0.0)
            kd = sg * float(S["k"][ii]); lane = -1 if kd < -1 / 9000 else 1         # unutrašnja strana krivine (lijevi zavoj → lijeva traka)
            out.setdefault("ln", []).append(lane)
            sr = srs.get("L" if lane < 0 else "D") or srs.get("D") or srs.get("L")
            if sr:
                ss = np.array(sr["s"]); o = np.argsort(ss)
                f = lambda arr: float(np.interp(sta, ss[o], np.array(arr)[o]))
                out["v"].append(round(f(sr["v"]), 1)); out["D"].append(round(f(sr["D"]), 1)); out["Lz"].append(round(f(sr["Lz"]), 1)); out["ok"].append(int(round(f(sr["ok"])))); out["g"][-1] = round(f(sr["g"]), 2)
            else:
                out["v"].append(0); out["D"].append(0); out["Lz"].append(0); out["ok"].append(0)
        # nagib iz nivelete (ako nema iz UNA)
        z = np.array(out["z"]); qq = np.array(out["q"])
        if not (srs.get("D") or srs.get("L")) and len(qq) > 2: out["g"] = [round(float(v) * 100, 2) for v in np.gradient(z, qq + np.arange(len(qq)) * 1e-9)]
        scene["routes"][tag] = out
    log(_TF("Koridor: scena izrađena ({0} presjeka po smjeru).", len(order)))
    return scene


def write_html(path, R_or_path, P, par, out, cfg, log=print):
    import json
    from . import vizura
    kc = cfg.get("koridor") or {}
    s_from = float(kc.get("od", 80)); s_to = float(kc.get("do", 1580))
    R = R_or_path if isinstance(R_or_path, dict) else load_landxml(R_or_path, s_from, s_to, log=log)
    d = vizura.build_data(P, par, out, dict(cfg, vizura_opcije={"obje_trake": True}), log)
    sight = {}
    for key, r in d["routes"].items():
        tag, side = key.split("_")[0], key.split("_")[1]
        sight.setdefault(tag, {})[side] = dict(s=r["s"], v=r["v"], g=r["g"], D=r["D"], Lz=r["Lz"], ok=r["ok"])
    scene = build_scene(R, s_from, s_to, sight, cfg, h_eye=d["h"], log=log)
    scene["lang"] = d["lang"]; scene["Vr"] = d["Vr"]
    tpl = open(os.path.join(os.path.dirname(__file__), "data", "koridor.html"), encoding="utf-8").read()
    js = json.dumps(scene, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(path, "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/null", js))
    log(_TF("Vožnja kroz koridor (HTML): {0}", path))
    return path
