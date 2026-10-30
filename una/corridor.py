"""Uvoz koridora iz Civil 3D-a (LandXML 1.2) i priprema podataka za vožnju kroz koridor.

Čita strujno (datoteka može imati stotine MB): osovine (CoordGeom), nivelete (ProfAlign), poprečne presjeke koridora (CrossSect → DesignCrossSectSurf)
i teren (Surface/TIN). Izlaz je kompaktna struktura za una/data/koridor.html (vidi build_scene).

Konvencije LandXML-a: koordinate 'sjever istok', azimut u stepenima od sjevera u smjeru kazaljke, ofset presjeka + = desno u smjeru stacionaže,
visine presjeka su relativne u odnosu na niveletu osovine."""
import math, os, pickle, hashlib, tempfile
import xml.etree.ElementTree as ET
import numpy as np


class _NN:
    """Najbliža tačka (brute force, bez scipy)."""
    def __init__(self, xy): self.xy = np.asarray(xy, float)

    def query(self, q):
        q = np.asarray(q, float)
        if q.ndim == 1:
            d = np.hypot(self.xy[:, 0] - q[0], self.xy[:, 1] - q[1]); j = int(np.argmin(d)); return float(d[j]), j
        dm = np.empty(len(q)); jm = np.empty(len(q), int)
        for a in range(0, len(q), 4000):
            c = q[a:a + 4000]; d = np.hypot(c[:, None, 0] - self.xy[None, :, 0], c[:, None, 1] - self.xy[None, :, 1]); jm[a:a + 4000] = d.argmin(1); dm[a:a + 4000] = d.min(1)
        return dm, jm
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
        d, _ = _NN(np.c_[cx, cy]).query(tin[:, :2]); keep = d < 320.0
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


def _interp_s(A, arr, sta, order=None):
    sA = A["s"]; o = np.argsort(sA, kind="stable") if order is None else order
    return float(np.interp(sta, sA[o], np.asarray(arr)[o]))


def build_scene(R, s_from, s_to, out, par, cfg, log=print):
    """Scena vožnje. SVE što se tiče preglednosti (oko, ofset trake, prepreke, zrake, D, Lz, v, g) uzima se direktno iz UNA proračuna (out['vp'] / out['ocek']);
    iz koridora dolaze samo oblik presjeka, teren, most i tunel. 'F' = osovina D* u smjeru stacionaže, 'B' = druga osovina suprotno stacionaži."""
    dtm = _dtm_interp(R); A_ = R["aligns"]; names = [n for n in A_ if n in R["sect"]]
    nF = next((n for n in names if n.upper().startswith("D")), names[0]); nB = next((n for n in names if n != nF), None)
    plan = [("F", nF, nB, +1)] + ([("B", nB, nF, -1)] if nB else [])
    secs_by = {}
    for nm in names:
        keep = []; last = -1e9
        for sta, ss in R["sect"][nm]:
            if s_from - 1 <= sta <= s_to + 1 and sta - last >= 1.2: keep.append((sta, ss)); last = sta
        sta = np.array([r[0] for r in keep]); N, E = A_[nm].pos(sta); nu = A_[nm].heading(sta)
        secs_by[nm] = dict(sta=sta, N=N, E=E, nu=nu, z0=A_[nm].z(sta), G=[section_geom(ss, 0.78, False) for _, ss in keep], k=A_[nm].curvature(sta))
    trees = {nm: _NN(np.c_[v["E"], v["N"]]) for nm, v in secs_by.items()}
    h_oka = float(par["h_oka"]); scene = dict(routes={}, h=h_oka, range=[s_from, s_to], projekat=cfg.get("projekat", ""), h_pr=float(par["h_prepreke"]), h_auto=bool(par.get("h_auto")))
    for tag, nm, other, sg in plan:
        S = secs_by[nm]; n = len(S["sta"]); order = np.arange(n) if sg > 0 else np.arange(n)[::-1]
        prep = {}
        for sd in ("D", "L"):
            Rr = out["vp"].get(f"{tag}_{sd}")
            if Rr is None: continue
            A = Rr["A"]; rows = Rr["avail"]["rows"]            # zahtijevana preglednost = Pzp iz Vp i nagiba (L_vp), ne fiksna vrijednost
            prep[sd] = dict(A=A, rows=rows, rs=np.array([r["s"] for r in rows]), o=np.argsort(A["s"], kind="stable"))
        if not prep: raise ValueError(_T("Koridor: nema proračuna preglednosti za ovu osovinu (uključite preglednost)."))
        PD = prep.get("D") or prep["L"]
        q = 0.0; prev = None
        o_ = dict(naziv=_TF("{0} – {1}", nm, _T("smjer stacionaže") if sg > 0 else _T("suprotno stacionaži")), q=[], s=[], x=[], y=[], z=[], tx=[], ty=[], k=[], el=[], v=[], g=[], D=[], Lz=[], ok=[],
                  kind=[], gr=[], F=[], e=[], box=[], ring=[], ln=[], latD=[], latL=[], zeD=[], zeL=[], ob=[], ray=[], lim=[], hp=[])
        for ii in order:
            sta = float(S["sta"][ii]); x, y = float(S["E"][ii]), float(S["N"][ii])
            if prev is not None: q += math.hypot(x - prev[0], y - prev[1])
            prev = (x, y); nu = float(S["nu"][ii]); G = S["G"][ii]; z0c = float(S["z0"][ii])
            shift = _interp_s(PD["A"], PD["A"]["z"], sta, PD["o"]) - z0c            # UNA niveleta vs Civil niveleta (razlika se prikazuje, slika prati UNA)
            z0 = z0c + shift
            nxs, nys = math.cos(nu), -math.sin(nu); nxd, nyd = sg * nxs, sg * nys    # desna normala (stacionaža / smjer vožnje), (E,N)
            kd = sg * float(S["k"][ii]); lane = -1 if kd < -1 / 9000 else 1
            sdsel = "L" if (lane < 0 and "L" in prep) else ("D" if "D" in prep else "L")
            lat = {}; ze = {}
            for sd, pp in prep.items():
                Ax = _interp_s(pp["A"], pp["A"]["x"], sta, pp["o"]); Ay = _interp_s(pp["A"], pp["A"]["y"], sta, pp["o"])
                lat[sd] = (Ax - x) * nxd + (Ay - y) * nyd; ze[sd] = _interp_s(pp["A"], pp["A"]["z"], sta, pp["o"])
            for sd in ("D", "L"): lat.setdefault(sd, lat[sdsel]); ze.setdefault(sd, ze[sdsel])
            if abs(lat[sdsel]) > 25: raise ValueError(_TF("Koridor: osovina '{0}' na st. {1:.1f} je {2:.0f} m od osovine u UNA projektu – koordinate ili stacionaže se ne poklapaju.", nm, sta, abs(lat[sdsel])))
            # --- profil u stacionažnom okviru
            top = list(G["top"]); oth_top = None; oth_e = None
            if other and G["kind"] == "otvorena":
                d, j = trees[other].query([x, y])
                if d < 60:
                    Go = secs_by[other]["G"][int(j)]
                    if Go["kind"] == "otvorena":
                        t = (secs_by[other]["E"][j] - x) * nxs + (secs_by[other]["N"][j] - y) * nys
                        dz = float(secs_by[other]["z0"][j]) - z0
                        oth_top = [(o + t, zz + dz) for o, zz in Go["top"]]; oth_e = (Go["e"], t)
            drv = lambda tp: sorted([(sg * o, zz) for o, zz in tp])
            P1 = drv(top); P2 = drv(oth_top) if oth_top else None; pts = list(P1); med = None
            if P2:
                if P2[-1][0] < P1[0][0] + 0.2:
                    gap = P1[0][0] - P2[-1][0]
                    if 0.02 < gap < 45: med = (P2[-1][0], P2[-1][1], P1[0][0], P1[0][1])
                    pts = P2 + P1
                else: P2 = None; oth_e = None
            terr_R = []; terr_L = []
            if G["kind"] == "otvorena" and dtm is not None:
                for side, (o_end, z_end), lst in ((1, pts[-1], terr_R), (-1, pts[0], terr_L)):
                    for dd in (4, 10, 22, 40, 70, 110, 170, 260):
                        oo = o_end + side * dd; zt = dtm(x + nxd * oo, y + nyd * oo)
                        if np.ma.is_masked(zt) or zt is None: break
                        lst.append((oo, float(zt) - z0))
            full = list(reversed(terr_L)) + pts + terr_R
            zones = dict(e=round(G["e"], 3), shL=round(sg * (G["shL"] if sg > 0 else G["shR"]), 3), shR=round(sg * (G["shR"] if sg > 0 else G["shL"]), 3),
                         oe=round(oth_e[0], 3) if (oth_top and oth_e) else 0, ot=round(sg * oth_e[1], 3) if (oth_top and oth_e) else 0, med=[round(v, 3) for v in med] if med else None)
            # --- prepreke iz UNA proračuna (bočni ofset u okviru vožnje)
            ob = []
            for kx, ky in (("obrx", "obry"), ("oblx", "obly")):
                ox = _interp_s(PD["A"], PD["A"][kx], sta, PD["o"]) if np.isfinite(PD["A"][kx]).any() else float("nan")
                oy = _interp_s(PD["A"], PD["A"][ky], sta, PD["o"]) if np.isfinite(PD["A"][ky]).any() else float("nan")
                # np.interp s NaN daje NaN; provjeri najbliži čvor
                j = int(np.argmin(np.abs(PD["A"]["s"] - sta)))
                if not np.isfinite(PD["A"][kx][j]): ob.append(None)
                else: ob.append(round((PD["A"][kx][j] - x) * nxd + (PD["A"][ky][j] - y) * nyd, 3))
            # --- zraka iz UNA (red najbliži stacionaži; čvorovi lanca)
            pp = prep[sdsel]; A = pp["A"]; sxs = A["xa"] - A["x"]; sys_ = A["ya"] - A["y"]; nA = len(A["q"])
            order_r = np.argsort(pp["rs"], kind="stable"); rsS = pp["rs"][order_r]
            jj = int(np.clip(np.searchsorted(rsS, sta), 1, len(rsS) - 1)) if len(rsS) > 1 else 0
            cand = [order_r[jj - 1], order_r[jj]] if len(rsS) > 1 else [order_r[0]]
            def _ray(r):
                a = int(r["i"]); hpr = pg_hpr(A, par, a); Lz_ = float(r["Lz"]); bD = int(min(r.get("b", a), nA - 1)); bL = int(min(nA - 1, np.searchsorted(A["q"], A["q"][a] + Lz_)))
                return a, hpr, [float(A["x"][a]), float(A["y"][a]), float(A["z"][a] + h_oka), float(A["xa"][bD] - sxs[bD]), float(A["ya"][bD] - sys_[bD]), float(A["z"][bD] + hpr),
                                float(A["xa"][bL] - sxs[bL]), float(A["ya"][bL] - sys_[bL]), float(A["z"][bL] + hpr)], float(r["D"]), Lz_
            rr = [pp["rows"][c] for c in cand]; Rs = [_ray(r) for r in rr]
            if len(rr) == 2 and rr[1]["s"] != rr[0]["s"]: f_ = float(np.clip((sta - rr[0]["s"]) / (rr[1]["s"] - rr[0]["s"]), 0, 1))
            else: f_ = 0.0
            lerp = lambda u, v: u + (v - u) * f_
            ray = [round(lerp(u, v), 2) for u, v in zip(Rs[0][2], Rs[-1][2])] + [None]
            D = lerp(Rs[0][3], Rs[-1][3]); Lz = lerp(Rs[0][4], Rs[-1][4]); hpr = Rs[0][1]
            r = rr[0] if f_ < 0.5 else rr[-1]; a = Rs[0][0] if f_ < 0.5 else Rs[-1][0]
            kc = r.get("kc")
            if kc is not None:
                kc = int(kc); cand2 = []
                for kx, ky in (("obrx", "obry"), ("oblx", "obly")):
                    if np.isfinite(A[kx][kc]): cand2.append((math.hypot(A[kx][kc] - A["x"][kc], A[ky][kc] - A["y"][kc]), float(A[kx][kc]), float(A[ky][kc])))
                if cand2: c0 = min(cand2); ray[9] = [round(c0[1], 2), round(c0[2], 2), round(float(A["z"][kc] + hpr), 3)]
            okc = 0 if (r.get("okH", True) and r.get("okV", True)) else (1 if not r.get("okH", True) else 2)
            v_ = float(_interp_s(A, A["v"], sta, pp["o"])); g_ = float(_interp_s(A, A["g"], sta, pp["o"]))
            o_["q"].append(round(q, 2)); o_["s"].append(round(sta, 2)); o_["x"].append(round(x, 3)); o_["y"].append(round(y, 3)); o_["z"].append(round(z0, 3))
            o_["tx"].append(round(sg * math.sin(nu), 5)); o_["ty"].append(round(sg * math.cos(nu), 5)); o_["k"].append(round(kd, 6))
            o_["el"].append(_elem_at(A_[nm], sta)); o_["kind"].append(G["kind"]); o_["gr"].append(G["gr"]); o_["F"].append([[round(a_, 3), round(b_, 3)] for a_, b_ in full]); o_["e"].append(zones)
            bx = []
            for st_, a_, b_, h_ in G["box"]:
                lo, hi = sorted((sg * a_, sg * b_)); bx.append([st_, round(lo, 3), round(hi, 3), round(h_, 3)])
            o_["box"].append(bx); o_["ring"].append([[round(sg * a_, 3), round(b_, 3)] for a_, b_ in G["ring"]])
            o_["ln"].append(-1 if sdsel == "L" else 1); o_["latD"].append(round(lat["D"], 3)); o_["latL"].append(round(lat["L"], 3)); o_["zeD"].append(round(ze["D"], 3)); o_["zeL"].append(round(ze["L"], 3))
            o_["ob"].append(ob); o_["ray"].append(ray); o_["lim"].append(str(r.get("lim", ""))); o_["hp"].append(round(hpr, 2))
            o_["v"].append(round(v_, 1)); o_["g"].append(round(g_, 2)); o_["D"].append(round(D, 1)); o_["Lz"].append(round(Lz, 1)); o_["ok"].append(okc)
        zs = np.array(o_["z"]) - np.array([float(S["z0"][k]) for k in order])
        if len(zs) and abs(zs).max() > 0.01: log(_TF("Koridor: niveleta u UNA proračunu se razlikuje od Civil 3D niveleta za {0:.3f} m (osovina {1}); slika prati UNA.", float(np.median(zs)), nm))
        scene["routes"][tag] = o_
    log(_TF("Koridor: scena izrađena ({0} presjeka po smjeru).", len(order)))
    return scene


def pg_hpr(A, par, a):
    from . import preglednost as pg
    return pg.hpr_at(A, par, a)


def write_html(path, R_or_path, P, par, out, cfg, log=print):
    import json
    kc = cfg.get("koridor") or {}
    s_from = float(kc.get("od", 80)); s_to = float(kc.get("do", 1580))
    R = R_or_path if isinstance(R_or_path, dict) else load_landxml(R_or_path, s_from, s_to, log=log)
    scene = build_scene(R, s_from, s_to, out, par, cfg, log=log)
    from .i18n import get_lang
    scene["lang"] = get_lang(); scene["Vr"] = float(P.Vr)
    tpl = open(os.path.join(os.path.dirname(__file__), "data", "koridor.html"), encoding="utf-8").read()
    js = json.dumps(scene, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(path, "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/null", js))
    log(_TF("Vožnja kroz koridor (HTML): {0}", path))
    return path


# ----------------------------------------------------------------------------------------------- usklađivanje proračuna s koridorom
def kinds_by_axis(R, s_from, s_to):
    """Dionice (od, do, vrsta) po osovini iz poprečnih presjeka koridora."""
    res = {}
    for nm, lst in R["sect"].items():
        runs = []; cur = None
        for sta, ss in lst:
            if sta < s_from - 1 or sta > s_to + 1: continue
            names = {n for n, _, _ in ss}
            k = "tunel" if "Sekundarna_obloga" in names else ("most" if ("Ploca_mosta" in names or "Vijenac" in names) else "otvorena")
            if cur and cur[2] == k: cur[1] = sta
            else:
                cur = [sta, sta, k]; runs.append(cur)
        res[nm] = runs
    return res


def tunnel_wall_offset(R, s_from, s_to, e, z0=1.0):
    """Ofset unutrašnje ivice obloge tunela (kalota) od ivice kolovoza, na visini zrake (≈1 m iznad kolovoza) – medijana po presjecima i stranama. None ako nema tunela."""
    vals = []
    for nm, lst in R["sect"].items():
        for sta, ss in lst[::4]:
            if not (s_from <= sta <= s_to): continue
            if not any(n == "Sekundarna_obloga" for n, _, _ in ss): continue
            for sd in (-1, 1):
                xs = []
                for n, _, pp in ss:
                    if n != "Sekundarna_obloga": continue
                    for p1, p2 in zip(pp, pp[1:]):
                        if (p1[1] - z0) * (p2[1] - z0) <= 0 and p1[1] != p2[1]:
                            x = p1[0] + (p2[0] - p1[0]) * (z0 - p1[1]) / (p2[1] - p1[1])
                            if x * sd > 0: xs.append(abs(x))
                if xs: vals.append(min(xs) - e)
    if not vals: return None
    vals.sort(); return round(max(0.0, vals[len(vals) // 2]), 2)


def parapet_offset(R, s_from, s_to, e):
    """Ofset unutrašnje strane parapeta mosta (vijenac) od ivice kolovoza, očitan iz presjeka koridora – medijana. None ako nema mosta."""
    vals = []
    for nm, lst in R["sect"].items():
        for sta, ss in lst[::4]:
            if not (s_from <= sta <= s_to): continue
            for sd in (-1, 1):
                xs = [abs(p[0]) for n, _, pp in ss if n == "Vijenac" for p in pp if p[0] * sd > e + 0.05]
                if xs: vals.append(min(xs) - e)
    if not vals: return None
    vals.sort(); return round(max(0.0, vals[len(vals) // 2]), 2)


def harmonize(cfg, R, log=print):
    """Proračun preglednosti prati koridor: širina trake iz koridora, prepreka na otvorenoj trasi na zadanom ofsetu od ivice kolovoza (zadano 0,78 m),
    vrsta prepreke (most / tunel) po stacionaži iz koridora. Mijenja cfg (poziva se prije proračuna)."""
    kc = cfg.get("koridor") or {}
    if not kc.get("uskladi", True): return
    s_from = float(kc.get("od", 80)); s_to = float(kc.get("do", 1580)); off = float(kc.get("ograda_ofset", 0.78))
    es = []
    for nm, lst in R["sect"].items():
        for sta, ss in lst[::10]:
            if s_from <= sta <= s_to:
                G = section_geom(ss, off, False)
                if G["kind"] == "otvorena": es.append(round(G["e"], 2))
    if not es: return
    e = max(set(es), key=es.count)
    for sec in cfg.get("sekcije", []):
        if float(sec["do"]) < s_from or float(sec["od"]) > s_to: continue
        for r in ("desna", "lijeva", "centralna", "osovina"):
            sp = sec.get(r)
            if isinstance(sp, dict):
                old = (sp.get("trake_desno"), sp.get("trake_lijevo")); sp["trake_desno"] = [e]; sp["trake_lijevo"] = [e]
                log(_TF("Koridor → proračun: sekcija {0} ({1}): širina trake {2} → {3:.2f} m.", sec.get("od"), r, old[0], e))
    pc = cfg.setdefault("preglednost", {"ukljuci": True})
    tip = dict(pc.get("tipovi_prepreka") or {})
    if not cfg.get("npp"):
        tip["otvorena trasa"] = off; pc["zadani_tip"] = "otvorena trasa"
        log(_TF("Koridor → proračun: prepreka na otvorenoj trasi {0:.2f} m od ivice kolovoza.", off))
        tip.setdefault("most", 1.17); tip.setdefault("tunel", 0.5)
        pw = parapet_offset(R, s_from, s_to, e)
        if pw is not None:
            tip["most"] = pw
            log(_TF("Koridor → proračun: na mostu je prepreka unutrašnja strana parapeta na {0:.2f} m od ivice kolovoza (iz presjeka koridora).", pw))
        tw = tunnel_wall_offset(R, s_from, s_to, e)
        if tw is not None:
            tip["tunel"] = tw
            log(_TF("Koridor → proračun: u tunelu je prepreka unutrašnja ivica obloge (kalota) na {0:.2f} m od ivice kolovoza (ne ivičnjak).", tw))
        pc["tipovi_prepreka"] = tip
        pre = [en for en in (pc.get("prepreke") or []) if not (isinstance(en, dict) and en.get("_kor"))]
        for nm, runs in kinds_by_axis(R, s_from, s_to).items():
            role = "desna" if nm.upper().startswith("D") else "lijeva"
            for a, b, k in runs:
                if k != "otvorena":
                    for st_ in ("desno", "lijevo"):          # zid tunela / parapet mosta su s obje strane (i na pravcu)
                        pre.append({"osovina": role, "od": round(a, 2), "do": round(b, 2), "tip": k, "strana": st_, "_kor": True})
        pc["prepreke"] = pre
        log(_TF("Koridor → proračun: dionice mosta/tunela preuzete iz koridora ({0}).", len([e_ for e_ in pre if e_.get("_kor")])))
    else:
        log(_T("Koridor: NPP je uključen – prepreke u proračunu ostaju prema NPP-u (slika prati proračun)."))
