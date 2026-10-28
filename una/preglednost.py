"""Preglednost: zrake po osovinama vozne trake (sa ofsetom od osovine puta, na OBJE strane osovine).

Tri proračuna / crteža:
  1. 'Vp'          – potrebna Lz = f(Vp (V85), nagib u smjeru vožnje), 'Skraćena zaustavna preglednost' (Crtež 52, fT50 %, Smjernice BiH);
  2. 'zahtijevana' – zraka zadane dužine L_zahtijevano (unosi korisnik), isti proračun omotača;
  3. 'očekivana'   – raspoloživa preglednost: korisnik za svaki element trase (pravac, prijelaznica, kružni luk) unosi ofset prepreke
                     od krajnje ivice kolovoza; prepreka je linija na toj udaljenosti, a rezultat je najduža zraka koju prepreka (i niveleta) dopušta.
Zraka = tetiva od oka vozača (osovina vozne trake) do tačke ispred, mjereno duž osovine trake; oko h_oka, predmet h_prepreke iznad nivelete.
Ofset osovine trake zadaje se u smjeru vožnje: ofset_desno (traka desno od osovine) i ofset_lijevo (traka lijevo od osovine).
Trake/ivice se zadaju u smjeru rastuće stacionaže: trake_desno / trake_lijevo = širine traka od osovine prema van.
"""
import math
import numpy as np

S_TAB = [-12, -10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10, 12]
V_TAB = [40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140]
# Očitano iz dijagrama (Crtež 52: Skraćena zaustavna preglednost, fT50 %) – digitalizacija slike, odstupanje ≈ 0,1 m
LZ_TAB = {
    40: [30.2, 29.7, 29.1, 28.6, 28.2, 27.7, 27.3, 27.0, 26.7, 26.4, 26.2, 26.0, 25.9],
    50: [42.2, 41.4, 40.6, 39.9, 39.2, 38.5, 37.9, 37.3, 36.8, 36.3, 35.8, 35.4, 35.0],
    60: [55.8, 54.6, 53.4, 52.4, 51.3, 50.4, 49.5, 48.6, 47.8, 47.1, 46.4, 45.8, 45.2],
    70: [74.0, 72.0, 70.1, 68.4, 66.7, 65.2, 63.8, 62.4, 61.3, 60.2, 59.2, 58.4, 57.7],
    80: [89.7, 87.3, 85.1, 83.0, 81.0, 79.2, 77.5, 75.9, 74.5, 73.1, 71.9, 70.8, 69.9],
    90: [108.9, 105.8, 102.9, 100.2, 97.6, 95.2, 93.1, 91.0, 89.2, 87.5, 86.0, 84.7, 83.5],
    100: [133.6, 129.5, 125.7, 122.1, 118.7, 115.5, 112.6, 109.9, 107.5, 105.3, 103.3, 101.6, 100.0],
    110: [156.7, 151.8, 147.2, 142.8, 138.8, 135.0, 131.4, 128.2, 125.2, 122.6, 120.2, 118.1, 116.3],
    120: [182.9, 177.1, 171.5, 166.4, 161.5, 156.9, 152.7, 148.7, 145.1, 141.8, 138.9, 136.2, 133.9],
    130: [209.2, 202.3, 195.8, 189.7, 184.0, 178.7, 173.8, 169.2, 165.1, 161.3, 157.9, 154.9, 152.3],
    140: [241.8, 233.5, 225.7, 218.3, 211.5, 205.1, 199.2, 193.7, 188.8, 184.3, 180.3, 176.8, 173.7],
}
_LZ = np.array([LZ_TAB[v] for v in V_TAB])


def lz(V, g):
    """Skraćena zaustavna preglednost [m] za brzinu V [km/h] i nagib g [%] u smjeru vožnje (+ uzbrdo)."""
    g = min(12.0, max(-12.0, g))
    col = np.array([np.interp(g, S_TAB, _LZ[i]) for i in range(len(V_TAB))])
    return float(np.interp(V, V_TAB, col))          # van raspona 40–140 km/h: najbliža granica


# Pravilnik RS (Sl. glasnik RS 50/2011), Prilog 2, tabela 4-01: zaustavna preglednost Pz u funkciji računske brzine (nagib 0 %, R = ∞)
PZ_RS_V = [40, 50, 60, 70, 80, 90, 100, 110, 120, 130]
PZ_RS = [40, 55, 70, 90, 115, 145, 180, 215, 255, 300]


def lzn(V, g, par):
    """Potrebna preglednost prema usvojenoj normi: BiH – Crtež 52 (skraćena zaustavna, zavisi od nagiba); RS – Tabela 4-01 Pravilnika (nagib 0 %)."""
    return lz(V, g)          # uvijek BiH Crtež 52 (skraćena zaustavna preglednost, zavisi od nagiba)


DEFAULTS = dict(norma="BiH", ofset=1.75, h_oka=None, h_prepreke="auto", h2_varijanta="nize", korak_proracun=5.0, korak_crtez=20.0, mjerilo=1000, scenarij=1,
                L_zahtijevano=None, dodatak_L=0.0, Lmax=500.0, ivice=True, ivica_debljina=0.3)
SIDES = {"desno": "D", "lijevo": "L", "D": "D", "L": "L"}
SIDE_NAME = {"D": "desna traka (desno od osovine kolovoza)", "L": "lijeva traka (lijevo od osovine kolovoza)"}
TIP_ZNAK = {"PRAVAC": "pravac", "KRUZNI_LUK": "kružni luk", "PRIJELAZNICA": "prijelaznica"}


# ------------------------------------------------------------------ geometrija osovine (gušća integracija)
_DENSE = {}


def dense_plan(ax, ds=1.0):
    """Gusta polilinija osovine: stacionaža, Y (istok), X (sjever), azimut nu [rad]."""
    if id(ax) in _DENSE: return _DENSE[id(ax)]
    el = ax.elems; Y, X = el[0]["Y0"], el[0]["X0"]; nu = math.radians(el[0]["nu0"])
    S = [el[0]["s0"]]; YY = [Y]; XX = [X]; NU = [nu]
    for e in el:
        k0 = 0.0 if math.isinf(e["R0"]) else 1 / e["R0"]; k1 = 0.0 if math.isinf(e["R1"]) else 1 / e["R1"]
        n = max(2, int(math.ceil(e["L"] / ds))); d = e["L"] / n
        for j in range(n):
            kk = k0 + (k1 - k0) * (j + 0.5) / n; mid = nu + 0.5 * kk * d
            X += d * math.cos(mid); Y += d * math.sin(mid); nu += kk * d
            S.append(e["s0"] + (j + 1) * d); YY.append(Y); XX.append(X); NU.append(nu)
    out = tuple(np.array(a) for a in (S, YY, XX, NU)); _DENSE[id(ax)] = out; return out


# ------------------------------------------------------------------ poprečni profil, ofseti, prepreke
def _lanes(v, default):
    if v is None or v == "": return list(default)
    if isinstance(v, str): v = [t for t in v.replace(";", ",").replace(" ", ",").split(",") if t]
    if isinstance(v, (int, float)): v = [v]
    out = [float(str(t).replace(",", ".")) for t in v]
    return out if out else list(default)


def case_prof(c, par):
    """Poprečni profil slučaja (u smjeru stacionaže). gR/gL = udaljenost osovine puta do UNUTRAŠNJE ivice kolovoza desno/lijevo (pola razdjelnog pojasa kod centralne osovine);
    eR/eL = udaljenost KRAJNJE (vanjske) ivice kolovoza = g + zbir širina traka. dDR/dDL = udaljenost osovine vozne trake od osovine puta desno/lijevo u SMJERU VOŽNJE
    (podrazumijevano sredina kolovoza tog smjera: g + zbir traka / 2)."""
    sp = c.sec.get(c.role) or {}
    def num(*keys):
        for k in keys:
            v = sp.get(k)
            if v is None: v = c.sec.get(k)
            if v not in (None, ""): return abs(float(str(v).replace(",", ".")))
        return None
    base = [2 * float(par["ofset"])]
    tR = _lanes(sp.get("trake_desno"), base); tL = _lanes(sp.get("trake_lijevo"), base)
    gp = num("razdjelni_pola") or 0.0
    gR = num("unutra_desno"); gL = num("unutra_lijevo")
    gR = gp if gR is None else gR; gL = gp if gL is None else gL
    # osovina kolovoza vozača: centralna osovina → sredina kolovoza smjera (desno: g+suma/2; lijevo isto sa lijeve strane); ostale osovine su same osovina kolovoza
    if c.role == "centralna": hC = (gR + sum(tR) / 2) if c.sg == 1 else (gL + sum(tL) / 2)
    else: hC = 0.0
    lane0 = (tR[0] if c.sg == 1 else tL[0]) / 2
    o_ = num("ofset"); dr = num("ofset_desno"); dl = num("ofset_lijevo")
    dr = (lane0 if o_ is None else o_) if dr is None else dr; dl = (lane0 if o_ is None else o_) if dl is None else dl
    # osovina oka vozača = osovina kolovoza ± ofset (u smjeru vožnje): desna traka hC + dr, lijeva traka hC - dl
    return dict(tR=tR, tL=tL, gR=gR, gL=gL, eR=gR + sum(tR), eL=gL + sum(tL), hC=hC, dDR=dr, dDL=dl, pD=hC + dr, pL=hC - dl)


def element_rows(c):
    """Elementi horizontale osovine u rasponu slučaja: (br, vrsta, s0, s1, R0, R1)."""
    out = []
    for e in c.axis.elems:
        s0, s1 = e["s0"], e["s0"] + e["L"]
        if s1 < c.SA - 1e-6 or s0 > c.SB + 1e-6 or e["L"] < 0.5: continue
        out.append(dict(no=e["no"], typ=e["typ"], s0=s0, s1=s1, R0=e["R0"], R1=e["R1"], k=(0.0 if math.isinf(e["R0"]) else 1 / e["R0"]) + (0.0 if math.isinf(e["R1"]) else 1 / e["R1"])))
    return out


def _match(en, c, e=None):
    if en.get("sekcija") not in (None, "", c.sec["no"]): return False
    if en.get("osovina") not in (None, "", c.role): return False
    return True


def obstacle_offsets(c, par, s):
    """Ofset prepreke od krajnje ivice kolovoza za stacionaže s: (oR, oL) – desna/lijeva strana u smjeru STACIONAŽE; NaN = nema prepreke.
    Redoslijed prioriteta: zadano po vrsti elementa < unos po elementu (br.) < unos po rasponu stacionaža."""
    s = np.asarray(s, float); oR = np.full(len(s), np.nan); oL = np.full(len(s), np.nan)
    pre = par.get("prepreke") or []; dflt = par.get("prepreke_zadano") or {}; tipovi = par.get("tipovi_prepreka") or {}; ztip = par.get("zadani_tip") or ""
    if not pre and not dflt and not ztip: return oR, oL
    def val(en):
        if en.get("tip") not in (None, ""):
            v = tipovi.get(en["tip"]); return None if v in (None, "") else float(v)
        return None if en.get("ofset") in (None, "") else float(en["ofset"])
    els = element_rows(c)
    def put(mask, off, side, k):
        if side in ("desno", "D", "desna"): oR[mask] = off
        elif side in ("lijevo", "L", "lijeva"): oL[mask] = off
        else:                                            # 'unutra' / 'vani' prema zakrivljenosti (k>0: desna krivina, unutra = desno)
            if abs(k) < 1e-12: return
            inside_right = k > 0
            if side in ("vani", "izvana"): inside_right = not inside_right
            (oR if inside_right else oL)[mask] = off
    for e in els:
        m = (s >= e["s0"] - 1e-9) & (s <= e["s1"] + 1e-9)
        if not m.any(): continue
        key = {"PRAVAC": "pravac", "KRUZNI_LUK": "kruzni", "PRIJELAZNICA": "prijelaznica"}[e["typ"]]
        if dflt.get(key) not in (None, ""): put(m, float(dflt[key]), "unutra", e["k"])
        if ztip and e["typ"] != "PRAVAC" and tipovi.get(ztip) not in (None, ""): put(m, float(tipovi[ztip]), "unutra", e["k"])
        for en in pre:
            if not _match(en, c): continue
            if en.get("element") not in (None, "") and int(en["element"]) == e["no"] and val(en) is not None:
                put(m, val(en), en.get("strana", "unutra"), e["k"])
    for en in pre:                                        # rasponi stacionaža
        if not _match(en, c) or en.get("od") in (None, "") or val(en) is None: continue
        for e in els:
            m = (s >= max(e["s0"], float(en["od"])) - 1e-9) & (s <= min(e["s1"], float(en["do"])) + 1e-9)
            if m.any(): put(m, val(en), en.get("strana", "unutra"), e["k"])
    return oR, oL


def case_frame(c, par, s):
    """Tačke osovine puta i desne normale (stacionaža rastuća) za stacionaže s."""
    S, Y, X, NU = dense_plan(c.axis)
    y0 = np.interp(s, S, Y); x0 = np.interp(s, S, X)
    cx = np.interp(s, S, np.cos(NU)); cy = np.interp(s, S, np.sin(NU)); nn = np.hypot(cx, cy); cx /= nn; cy /= nn
    return x0, y0, -cy, cx            # desna normala (X sjever, Y istok) = (-sin nu, cos nu)


def build_chain(ch, P, par, scen=1, side="D"):
    """Lanac slučajeva u smjeru vožnje → čvorovi (korak 1 m) po osovini vozne trake na strani side ('D' desno / 'L' lijevo od osovine)."""
    cols = {k: [] for k in ("x", "y", "s", "ci", "z", "v", "g")}
    ob = {k: [] for k in ("rx", "ry", "lx", "ly")}            # prepreke u smjeru vožnje (desno/lijevo od vozača), CAD koordinate
    for ci, c in enumerate(ch):
        pr = case_prof(c, par)
        d = pr["pD"] if side == "D" else pr["pL"]              # udaljenost osovine oka od osovine puta, + desno u smjeru vožnje
        a, b = c.SA, c.SB; n = max(2, int(round((b - a) / 1.0)) + 1)
        s = np.linspace(a, b, n)
        if c.sg == -1: s = s[::-1]
        x0, y0, nx, ny = case_frame(c, par, s)
        xl = x0 + c.sg * d * nx; yl = y0 + c.sg * d * ny
        cols["x"] += list(yl); cols["y"] += list(xl)            # CAD: x = istok (Y), y = sjever (X)
        cols["s"] += list(s); cols["ci"] += [ci] * len(s)
        oR, oL = obstacle_offsets(c, par, s)                    # smjer stacionaže
        for nm, o, sign in (("R", oR, +1), ("L", oL, -1)):       # položaj prepreke u smjeru stacionaže: desno +(eR+o), lijevo -(eL+o)
            lat = sign * ((pr["eR"] if sign > 0 else pr["eL"]) + o)
            px = np.where(np.isnan(o), np.nan, y0 + lat * ny); py = np.where(np.isnan(o), np.nan, x0 + lat * nx)
            ob[("r" if (nm == "R") == (c.sg == 1) else "l") + "x"] += list(px); ob[("r" if (nm == "R") == (c.sg == 1) else "l") + "y"] += list(py)
        zc = np.interp(s, c.S, c.Z)
        if cols["z"]: zc = zc + (cols["z"][-1] - zc[0])
        cols["z"] += list(zc)
        V = c.V2 if (scen == 2 and hasattr(c, "V2")) else c.V
        cols["v"] += list(np.interp(s, c.S, V)); cols["g"] += list(c.sg * np.interp(s, c.S, c.G))
    A = {k: np.array(v) for k, v in cols.items()}
    for k, v in ob.items(): A["ob" + k] = np.array(v)
    xa = A["x"].copy(); ya = A["y"].copy(); ci = A["ci"]
    for k in np.where(np.diff(ci) != 0)[0]:
        dx = xa[k] - xa[k + 1]; dy = ya[k] - ya[k + 1]
        xa[k + 1:] += dx; ya[k + 1:] += dy
    A["xa"] = xa; A["ya"] = ya
    sx = xa - A["x"]; sy = ya - A["y"]
    A["obrxa"] = A["obrx"] + sx; A["obrya"] = A["obry"] + sy; A["oblxa"] = A["oblx"] + sx; A["oblya"] = A["obly"] + sy
    A["has_ob"] = bool(np.isfinite(A["obrx"]).any() or np.isfinite(A["oblx"]).any())
    dq = np.hypot(np.diff(xa), np.diff(ya)); dq = np.maximum(dq, 0.01); A["q"] = np.concatenate([[0.0], np.cumsum(dq)])
    tx = np.gradient(xa); ty = np.gradient(ya); tn = np.hypot(tx, ty) + 1e-12
    A["tx"] = tx / tn; A["ty"] = ty / tn          # tangenta puta vožnje; desna normala = (ty, -tx)
    return A


H2_V = [40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140]
H2_NIZE = [0.00, 0.00, 0.05, 0.05, 0.05, 0.05, 0.05, 0.10, 0.15, 0.15, 0.15]     # Tabela 29 (BiH Smjernice) – minimalna visina vidljivog dijela prepreke h2
H2_VISE = [0.00, 0.05, 0.05, 0.05, 0.05, 0.05, 0.10, 0.10, 0.15, 0.15, 0.15]     # varijanta za 50 i 100 km/h (druga kolona iz tabele)


def h2_of(V, vis=False):
    """h2 [m] iz Tabele 29: stepenasto, vrijednost za najveću tabličnu brzinu ≤ V (povoljnije po sigurnost – manji predmet)."""
    t = H2_VISE if vis else H2_NIZE; j = max(0, int(np.searchsorted(H2_V, V + 1e-9, side="right")) - 1)
    return t[j]


def hpr_at(A, par, a):
    return h2_of(float(A["v"][a]), par.get("h2_vise", False)) if par.get("h_auto") else par["h_pr"]


def _vert(A, par, a, b):
    """Raspoloživa vertikalna preglednost [m] od čvora a do čvora b (oko h_oka, predmet h_pr)."""
    q = A["q"]; z = A["z"]; ze = z[a] + par["h_oka"]; j = np.arange(a + 1, b + 1); Dv = q[b] - q[a]
    if len(j):
        d = np.maximum(q[j] - q[a], 1e-6)
        road = (z[j] - ze) / d; cm = np.maximum.accumulate(road); prev = np.concatenate([[-1e9], cm[:-1]])
        vis = (z[j] + hpr_at(A, par, a) - ze) / d >= prev - 1e-12
        bad = np.where(~vis)[0]
        if len(bad): Dv = float(d[bad[0] - 1]) if bad[0] > 0 else 0.0
    return min(Dv, q[b] - q[a])


def L_vp(A, par, a): return lzn(A["v"][a], A["g"][a], par) + par["dodatak_L"]      # + dodatak (npr. 7 m za puteve A kategorije – unosi korisnik)
def L_fix(A, par, a): return float(par["L_zahtijevano"])
def L_vr(A, par, a): return lzn(par["Vr"], A["g"][a], par) + par["dodatak_L"]      # preglednost za računsku brzinu Vr (nagib iz nivelete)
def L_zaht(A, par, a): return L_fix(A, par, a) if par["L_zahtijevano"] else L_vp(A, par, a)      # zahtijevana preglednost Pzp = preglednost na osnovu projektne brzine Vp i nagiba


def analyse(A, par, Lfun=L_vp):
    """Zrake, vertikalna provjera i omotač za sve čvorove sa korakom korak_proracun (dužina zrake = Lfun)."""
    n = len(A["q"]); st = max(1, int(round(par["korak_proracun"]))); idx = list(range(0, n, st))
    q = A["q"]; x = A["xa"]; y = A["ya"]
    mR = np.zeros(n); mL = np.zeros(n); rows = []
    for a in idx:
        L = Lfun(A, par, a)
        b = int(np.searchsorted(q, q[a] + L)); trunc = False
        if b >= n: b = n - 1; trunc = (q[b] - q[a]) < L - 1e-6
        Lx = q[b] - q[a]; Dv = _vert(A, par, a, b) if b > a else Lx
        if b > a + 1:
            ux, uy = x[b] - x[a], y[b] - y[a]; un = math.hypot(ux, uy) + 1e-12
            k = np.arange(a + 1, b); cr = (ux * (y[k] - y[a]) - uy * (x[k] - x[a])) / un        # >0: čvor lijevo od tetive → tetiva desno od puta
            mR[k] = np.maximum(mR[k], np.where(cr > 0, cr, 0.0)); mL[k] = np.maximum(mL[k], np.where(cr < 0, -cr, 0.0))
        rows.append(dict(i=a, s=float(A["s"][a]), q=float(q[a]), V=float(A["v"][a]), g=float(A["g"][a]), Lz=L, Lx=float(Lx), Dv=float(min(Dv, Lx)), trunc=trunc,
                         ok=(min(Dv, Lx) >= Lx - 1e-6), b=b))
    return dict(rows=rows, mR=mR, mL=mL)


def _first_blocked(A, a, cand):
    """Prvi (po redu) kandidat b čija tetiva a→b presijeca prepreku; None ako nijedan."""
    if len(cand) == 0: return None
    x = A["xa"]; y = A["ya"]; ux = x[cand] - x[a]; uy = y[cand] - y[a]
    ks = np.arange(a + 1, cand[-1]); 
    if len(ks) == 0: return None
    mk = ks[None, :] < cand[:, None]; blk = np.zeros(len(cand), bool)
    for ox, oy, sgn in ((A["obrxa"], A["obrya"], +1), (A["oblxa"], A["oblya"], -1)):
        px = ox[ks]; py = oy[ks]; fin = np.isfinite(px)
        if not fin.any(): continue
        cr = ux[:, None] * (np.where(fin, py, 0) - y[a]) - uy[:, None] * (np.where(fin, px, 0) - x[a])      # >0: prepreka lijevo od tetive
        blk |= ((sgn * cr > 0) & mk & fin[None, :]).any(1)           # desna prepreka lijevo od tetive (ili lijeva desno) = tetiva je presjekla prepreku
    w = np.where(blk)[0]
    return int(cand[w[0]]) if len(w) else None


def expected(A, par, Lfun=L_vp):
    """Očekivana (raspoloživa) preglednost: najduža zraka od oka vozača koju prepreka (ofset od ivice kolovoza) i niveleta dopuštaju."""
    n = len(A["q"]); st = max(1, int(round(par["korak_proracun"]))); q = A["q"]; rows = []
    Lmax = float(par["Lmax"])
    for a in range(0, n, st):
        Lr = Lfun(A, par, a); bmax = min(n - 1, int(np.searchsorted(q, q[a] + max(Lmax, Lr))))
        end = bmax == n - 1 and q[n - 1] - q[a] < max(Lmax, Lr) - 1e-6
        blocked = None
        if A["has_ob"] and bmax > a + 1:
            coarse = np.arange(a + 2, bmax + 1, 4); cb = _first_blocked(A, a, coarse)
            if cb is not None:
                fine = np.arange(max(a + 2, cb - 3), cb + 1); blocked = _first_blocked(A, a, fine)
        bh = bmax if blocked is None else max(a, blocked - 1)
        Dh = float(q[bh] - q[a])
        Dv = _vert(A, par, a, bmax) if bmax > a else 0.0           # vertikalna preglednost se računa nezavisno od prepreka (do najveće tražene dužine)
        D = min(Dh, Dv); b = int(np.searchsorted(q, q[a] + D)); b = min(b, bh)
        kc = None                                          # dodirna tačka zrake i linije prepreke (čvor prepreke najbliži tetivi)
        if A["has_ob"] and b > a + 1:
            ux, uy = A["xa"][b] - A["xa"][a], A["ya"][b] - A["ya"][a]; un = math.hypot(ux, uy) + 1e-12; ks = np.arange(a + 1, b); best = 1e18
            for ox, oy, sgn in ((A["obrxa"], A["obrya"], +1), (A["oblxa"], A["oblya"], -1)):
                px = ox[ks]; py = oy[ks]; fin = np.isfinite(px)
                if not fin.any(): continue
                cl = -sgn * (ux * (py - A["ya"][a]) - uy * (px - A["xa"][a])) / un           # udaljenost prepreke od tetive (>0: tetiva slobodna)
                cl = np.where(fin, cl, 1e18); j = int(np.argmin(cl))
                if cl[j] < best: best = float(cl[j]); kc = int(ks[j])
            if best > 1.5: kc = None                        # prepreka daleko od tetive – nije dodirna tačka
        lim = "prepreka" if (blocked is not None and Dh <= Dv + 1e-9) else ("niveleta" if Dv < Dh - 1e-9 else ("kraj trase" if end else "Lmax"))
        short_end = (lim == "kraj trase") and D < Lr - 1e-6
        okH = (Dh >= Lr - 1e-6) or (end and blocked is None); okV = (Dv >= Lr - 1e-6) or (end and Dv >= float(q[bmax] - q[a]) - 1e-6)
        rows.append(dict(i=a, s=float(A["s"][a]), q=float(q[a]), V=float(A["v"][a]), g=float(A["g"][a]), Lz=Lr, Dh=Dh, Dv=float(Dv), D=float(D), b=b, lim=lim,
                         trunc=short_end, ok=(D >= Lr - 1e-6) or short_end, kc=kc, okH=bool(okH), okV=bool(okV)))
    return dict(rows=rows)


def dminmax(rr):
    v = [r['D'] for r in rr if not r['trunc']] or [r['D'] for r in rr]
    return f"{min(v):.0f}–{max(v):.0f} m"


def intervals(rows, key="ok", bad=False, dkey="Dv"):
    """Spaja uzastopne stanice u raspone (po stacionaži)."""
    out = []; cur = None
    for r in rows:
        flag = (not r[key]) if bad else r[key]
        if flag:
            if cur is None: cur = dict(s0=r["s"], s1=r["s"], q0=r["q"], dmin=r[dkey], need=r["Lz"], V=r["V"])
            cur["s1"] = r["s"]; cur["dmin"] = min(cur["dmin"], r[dkey]); cur["need"] = max(cur["need"], r["Lz"])
        elif cur is not None: out.append(cur); cur = None
    if cur is not None: out.append(cur)
    return out


def make_par(cfg):
    par = dict(DEFAULTS)
    pc = cfg.get("preglednost") or {}
    par.update({k: v for k, v in pc.items() if k in DEFAULTS or k in ("grupa", "norma", "prepreke", "prepreke_zadano", "strane", "tipovi_prepreka", "zadani_tip")})
    on = (cfg.get("optika") or {}).get("norma") or pc.get("norma") or "BiH"; par["norma"] = "RS" if str(on).upper().startswith("RS") else "BiH"
    if par.get("h_oka") in (None, "", "auto"): par["h_oka"] = 1.10 if par["norma"] == "RS" else 1.0        # Pravilnik RS: h_oka = 1,10 m, nepokretna smetnja 0,10 m
    if par["norma"] == "RS" and str(par.get("h_prepreke")).strip().lower() in ("", "none", "auto", "tabela"): par["h_prepreke"] = 0.10
    par["h_auto"] = str(par.get("h_prepreke")).strip().lower() in ("", "none", "auto", "tabela", "0", "0.0")
    par["h2_vise"] = str(par.get("h2_varijanta", "nize")).lower().startswith("vi")
    if par["h_auto"]: par["h_prepreke"] = 0.10
    for k in ("dodatak_L", "ofset", "h_oka", "h_prepreke", "korak_proracun", "korak_crtez", "Lmax", "ivica_debljina"):
        par[k] = float(str(par[k]).replace(",", "."))
    L = par.get("L_zahtijevano")
    par["L_zahtijevano"] = None if L in (None, "", 0, "0") else float(str(L).replace(",", "."))
    st = par.get("strane") or ["desno", "lijevo"]
    par["strane"] = [SIDES[s] for s in (st if isinstance(st, (list, tuple)) else [st]) if s in SIDES]
    par["prepreke"] = [e for e in (par.get("prepreke") or []) if isinstance(e, dict)]
    par["prepreke_zadano"] = {k: v for k, v in (par.get("prepreke_zadano") or {}).items() if v not in (None, "")}
    par["h_pr"] = par["h_prepreke"]; par["ivice"] = bool(par["ivice"])
    par["tipovi_prepreka"] = {str(k): v for k, v in (par.get("tipovi_prepreka") or {}).items() if v not in (None, "")}
    par["zadani_tip"] = par.get("zadani_tip") or ""
    par["ima_prepreke"] = bool(par["prepreke"] or par["prepreke_zadano"] or (par["zadani_tip"] and par["zadani_tip"] in par["tipovi_prepreka"]))
    return par


def run(P, cases, fw, bw, cfg, log=print):
    """Vraća (par, out): out = dict(vp={trag: R}, zaht={..} ili None, ocek={..} ili None); trag = 'F_D', 'F_L', 'B_D', 'B_L'."""
    par = make_par(cfg); par["Vr"] = float(P.Vr); out = dict(vp={}, zaht=None, ocek=None, vr={})
    out["zaht"] = {} if par["L_zahtijevano"] else None; out["_fixL"] = bool(par["L_zahtijevano"])
    if par["ima_prepreke"]: out["ocek"] = {}
    for tag, ch in (("F", fw), ("B", bw)):
        if not ch: continue
        for sd in par["strane"]:
            A = build_chain(ch, P, par, par["scenarij"], sd); key = f"{tag}_{sd}"
            def meta(R):
                R["A"] = A; R["chain"] = ch; R["tag"] = tag; R["side"] = sd; R["key"] = key; return R
            R = meta(analyse(A, par, L_vp)); R["deficits"] = intervals(R["rows"], bad=True); out["vp"][key] = R
            R["avail"] = expected(A, par, L_vp); R["defH"] = intervals(R["avail"]["rows"], key="okH", bad=True, dkey="Dh"); R["defV"] = intervals(R["avail"]["rows"], key="okV", bad=True, dkey="Dv")
            nm = f"smjer {'stacionaže' if tag == 'F' else 'suprotno stacionaži'}, traka {SIDE_NAME[sd]}"
            log(f"Preglednost Vp, {nm}: Lz {min(r['Lz'] for r in R['rows']):.0f}–{max(r['Lz'] for r in R['rows']):.0f} m, slobodan prostor desno {R['mR'].max():.2f} m / lijevo {R['mL'].max():.2f} m, vertikalno nedovoljno na {len(R['defV'])}, horizontalno (prepreke) na {len(R['defH']) if A['has_ob'] else '-'} mjesta")
            Rv = meta(analyse(A, par, L_vr)); Rv["deficits"] = intervals(Rv["rows"], bad=True); out["vr"][key] = Rv
            Rv["avail"] = expected(A, par, L_vr); Rv["defH"] = intervals(Rv["avail"]["rows"], key="okH", bad=True, dkey="Dh"); Rv["defV"] = intervals(Rv["avail"]["rows"], key="okV", bad=True, dkey="Dv")
            log(f"Preglednost za Vr = {P.Vr:g} km/h, {nm}: Pz {min(r['Lz'] for r in Rv['rows']):.0f}–{max(r['Lz'] for r in Rv['rows']):.0f} m, vertikalno nedovoljno na {len(Rv['defV'])}, horizontalno (prepreke) na {len(Rv['defH']) if A['has_ob'] else '-'} mjesta")
            if out["zaht"] is not None:
                Z = meta(analyse(A, par, L_zaht)); Z["deficits"] = intervals(Z["rows"], bad=True); out["zaht"][key] = Z
                Z["avail"] = expected(A, par, L_zaht); Z["defH"] = intervals(Z["avail"]["rows"], key="okH", bad=True, dkey="Dh"); Z["defV"] = intervals(Z["avail"]["rows"], key="okV", bad=True, dkey="Dv")
                log(f"Zahtijevana preglednost {('L=%.0f m' % par['L_zahtijevano']) if par['L_zahtijevano'] else 'Pzp=f(Vp, nagib)'}, {nm}: slobodan prostor desno {Z['mR'].max():.2f} m / lijevo {Z['mL'].max():.2f} m, vertikalno nedovoljno na {len(Z['defV'])}, horizontalno (prepreke) na {len(Z['defH']) if A['has_ob'] else '-'} mjesta")
            if out["ocek"] is not None:
                Lf = L_zaht
                E = meta(expected(A, par, Lf)); E["deficits"] = intervals(E["rows"], bad=True, dkey="D"); out["ocek"][key] = E
                E["defH"] = intervals(E["rows"], key="okH", bad=True, dkey="Dh"); E["defV"] = intervals(E["rows"], key="okV", bad=True, dkey="Dv")
                rr = E["rows"]; log(f"Očekivana preglednost, {nm}: raspoloživo {dminmax(rr)}, nedovoljno na {len(E['deficits'])} mjesta")
    return par, out


def element_table(cases, par):
    """Tabela elemenata trase po osovini/sekciji sa primijenjenim ofsetom prepreke (za izvještaj i GUI)."""
    rows = []; seen = set()
    for c in cases:
        key = (id(c.axis), c.SA, c.SB, c.role, c.sec["no"])
        if key in seen: continue
        seen.add(key)
        for e in element_rows(c):
            s = np.array([(max(e["s0"], c.SA) + min(e["s1"], c.SB)) / 2]); oR, oL = obstacle_offsets(c, par, s)
            rows.append(dict(sek=c.sec["no"], osovina=c.role, no=e["no"], typ=TIP_ZNAK[e["typ"]], s0=e["s0"], s1=e["s1"], R=e["R0"] if e["typ"] == "KRUZNI_LUK" else (e["R1"] if math.isinf(e["R0"]) else e["R0"]),
                             oR=float(oR[0]), oL=float(oL[0])))
    return rows


def openpyxl_col(c):
    from openpyxl.utils import get_column_letter
    return get_column_letter(c)


def write_xlsx(path, P, par, out, cases=None):
    """Tabele rezultata (vrijednosti, ne formule)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook(); ws = wb.active; ws.title = "Sažetak"
    B = Font(name="Arial", bold=True); F = Font(name="Arial"); fill = PatternFill("solid", fgColor="D9E2F3")
    def w(ws, r, c, v, f=F, fmt=None):
        x = ws.cell(r, c, v); x.font = f
        if fmt: x.number_format = fmt
        return x
    nm = lambda R: f"{'smjer rastuće stacionaže' if R['tag'] == 'F' else 'suprotno smjeru stacionaže'}, traka {SIDE_NAME[R['side']]}"
    w(ws, 1, 1, f"PREGLEDNOST – {P.projekat}", B)
    w(ws, 2, 1, "Napomena: IZRAČUNATE VRIJEDNOSTI (nisu formule). Lz iz dijagrama 'Skraćena zaustavna preglednost (fT50 %)', očitanog iz slike (odstupanje ≈ 0,1 m).")
    r = 4; w(ws, r, 1, "Parametri", B); r += 1
    for k, v in (("Oko vozača iznad nivelete [m]", par["h_oka"]), ("Predmet iznad nivelete [m]", "po Tabeli 29 (h2 = f(Vp))" if par["h_auto"] else par["h_prepreke"]), ("Podrazumijevana širina trake/2 – ofset [m]", par["ofset"]),
                 ("Korak proračuna zraka [m]", par["korak_proracun"]), ("Dodatak na zaustavnu dužinu Lz [m] (unosi korisnik)", par["dodatak_L"]), ("Zahtijevana dužina zrake L [m] (unosi korisnik)", par["L_zahtijevano"] or "nije zadana"), ("Najveća tražena dužina zrake (očekivana) [m]", par["Lmax"]),
                 ("Strane osovine", ", ".join(SIDE_NAME[s] for s in par["strane"])),
                 ("Zadani tip prepreke (sve krivine)", par["zadani_tip"] or "-")) + tuple((f"Tip prepreke '{k}': ofset od ivice kolovoza [m]", v) for k, v in par["tipovi_prepreka"].items()):
        w(ws, r, 1, k); w(ws, r, 2, v); r += 1
    r += 1
    if cases:
        w(ws, r, 1, "Poprečni profil i ofsete po slučaju (ofset u smjeru vožnje; ivice u smjeru stacionaže)", B); r += 1
        for c in cases:
            pr = case_prof(c, par)
            w(ws, r, 1, f"{c.key}  {c.short}:  trake desno {pr['tR']} (ivica {pr['eR']:.2f} m), lijevo {pr['tL']} (ivica {pr['eL']:.2f} m);  osovina kolovoza {pr['hC']:.2f} m od osovine puta; ofset oka desno {pr['dDR']:.2f} m, lijevo {pr['dDL']:.2f} m" + (f"; razdjelni pojas: pola {pr['gR']:.2f} / {pr['gL']:.2f} m" if pr['gR'] or pr['gL'] else "")); r += 1
        r += 1
    def block(title, dd, expd=False):
        nonlocal r
        w(ws, r, 1, title, B); r += 1
        for R in dd.values():
            rows = R["rows"]; w(ws, r, 1, nm(R), B); r += 1
            if expd:
                items = (("Potrebna dužina min / max [m]", f"{min(x['Lz'] for x in rows):.0f} / {max(x['Lz'] for x in rows):.0f}"), ("Raspoloživa preglednost min / max [m] (bez zraka koje izlaze van trase)", dminmax(rows).replace("–", " / ").replace(" m", "")),
                         ("Mjesta sa nedovoljnom preglednošću", len(R["deficits"])))
            else:
                items = (("Lz min / max [m]", f"{min(x['Lz'] for x in rows):.0f} / {max(x['Lz'] for x in rows):.0f}"), ("Najveći potreban slobodni prostor desno od osovine trake [m]", round(float(R['mR'].max()), 2)),
                         ("Najveći potreban slobodni prostor lijevo od osovine trake [m]", round(float(R['mL'].max()), 2)), ("Mjesta sa nedovoljnom vertikalnom preglednošću", len(R["deficits"])))
            for k, v in items: w(ws, r, 1, k); w(ws, r, 2, v); r += 1
            hasob = R["A"]["has_ob"]
            for lab, key in (("HORIZONTALNA preglednost (prepreke)", "defH"), ("VERTIKALNA preglednost (niveleta)", "defV")):
                if key == "defH" and not hasob: w(ws, r, 1, "Horizontalna preglednost (prepreke): prepreke nisu zadane"); r += 1; continue
                w(ws, r, 1, f"{lab}: nedovoljno na {len(R[key])} mjesta" + (" – zadovoljava na cijeloj dužini" if not R[key] else ""), B); r += 1
                for b in R[key]:
                    w(ws, r, 1, f"   st. {b['s0']:.0f} – {b['s1']:.0f}: raspoloživo min {b['dmin']:.0f} m < potrebno {b['need']:.0f} m (Vp {b['V']:.0f} km/h)"); r += 1
            if not expd:
                w(ws, r, 1, "Lokalni maksimumi potrebnog slobodnog prostora (≥ 1,0 m, razmak ≥ 150 m)", B); r += 1
                for c, h in enumerate(["Stacionaža [m]", "Strana", "m od osovine trake [m]"], 1): w(ws, r, c, h, B).fill = fill
                r += 1; A = R["A"]
                for side, mm in (("desno", R["mR"]), ("lijevo", R["mL"])):
                    taken = []
                    for k in np.argsort(-mm):
                        if mm[k] < 1.0: break
                        if all(abs(A["q"][k] - A["q"][t]) > 150 for t in taken):
                            taken.append(k); w(ws, r, 1, round(float(A["s"][k]), 1)); w(ws, r, 2, side); w(ws, r, 3, round(float(mm[k]), 2)); r += 1
            r += 1
    block("1. PREGLEDNOST NA OSNOVU Vp (V85)", out["vp"])
    if out.get("zaht"): block(f"2. ZAHTIJEVANA PREGLEDNOST, " + (f"L = {par['L_zahtijevano']:.0f} m" if par["L_zahtijevano"] else "Pzp = f(Vp, nagib)"), out["zaht"])
    if out.get("ocek"): block("3. OČEKIVANA (RASPOLOŽIVA) PREGLEDNOST – prepreke prema unesenim ofsetima od ivice kolovoza", out["ocek"], True)
    ws.column_dimensions["A"].width = 100; ws.column_dimensions["B"].width = 18; ws.column_dimensions["C"].width = 24
    def sheet(name, R, kind):
        t = wb.create_sheet(name[:31]); A = R["A"]
        if kind == "e":
            hd = ["Stacionaža [m]", "Put trake q [m]", "Vp [km/h]", "Nagib [%]", "Potrebno [m]", "Raspoloživo – horizontalno [m]", "Raspoloživo – vertikalno [m]", "Raspoloživa preglednost [m]", "Ograničava", "Zadovoljava", "Horizontalno zadovoljava", "Vertikalno zadovoljava"]
        else:
            hd = ["Stacionaža [m]", "Put trake q [m]", "Vp [km/h]", "Nagib u smjeru vožnje [%]", "Potrebno L [m]", "Dužina zrake [m]", "Vertikalna raspoloživa [m]", "Vertikalno", "Slobodni prostor desno [m]", "Slobodni prostor lijevo [m]", "Zraka završava van trase",
                  "Horizontalno raspoloživo – prepreke [m]", "Vertikalno raspoloživo – niveleta [m]", "Raspoloživo ukupno [m]", "Ograničava", "Horizontalno zadovoljava", "Vertikalno zadovoljava"]
        for c, h in enumerate(hd, 1):
            x = w(t, 1, c, h, B); x.fill = fill; x.alignment = Alignment(wrap_text=True, horizontal="center")
        t.row_dimensions[1].height = 45
        for i, x in enumerate(R["rows"], 2):
            if kind == "e": vals = [x["s"], x["q"], x["V"], x["g"], x["Lz"], x["Dh"], x["Dv"], x["D"], x["lim"], "da" if x["ok"] else "NE", "da" if x["okH"] else "NE", "da" if x["okV"] else "NE"]; nf = (1, 2, 4, 5, 6, 7, 8)
            else:
                vals = [x["s"], x["q"], x["V"], x["g"], x["Lz"], x["Lx"], x["Dv"], "da" if x["ok"] else "NE", float(R["mR"][x["i"]]), float(R["mL"][x["i"]]), "da" if x["trunc"] else ""]; nf = (1, 2, 4, 5, 6, 7, 9, 10, 12, 13, 14)
                av = R["avail"]["rows"][i - 2] if R.get("avail") else None
                if av: vals += [av["Dh"] if R["A"]["has_ob"] else None, av["Dv"], av["D"], av["lim"], ("da" if av["okH"] else "NE") if R["A"]["has_ob"] else "-", "da" if av["okV"] else "NE"]
            for c, v in enumerate(vals, 1): w(t, i, c, v, F, "0.00" if c in nf else ("0.0" if c == 3 else None))
        for c in range(1, 18): t.column_dimensions[openpyxl_col(c)].width = 16
        t.freeze_panes = "A2"
    for key, R in out["vp"].items(): sheet(f"Vp_{key}", R, "z")
    for key, R in (out.get("zaht") or {}).items(): sheet(f"Zahtijevana_{key}", R, "z")
    for key, R in (out.get("ocek") or {}).items(): sheet(f"Ocekivana_{key}", R, "e")
    if cases and par["ima_prepreke"]:
        t = wb.create_sheet("Elementi_prepreke")
        for c, h in enumerate(["Sekcija", "Osovina", "Element br.", "Vrsta", "Od [m]", "Do [m]", "R [m]", "Ofset prepreke od ivice – desno [m]", "Ofset prepreke od ivice – lijevo [m]"], 1):
            x = w(t, 1, c, h, B); x.fill = fill; x.alignment = Alignment(wrap_text=True, horizontal="center")
        t.row_dimensions[1].height = 45
        for i, e in enumerate(element_table(cases, par), 2):
            for c, v in enumerate([e["sek"], e["osovina"], e["no"], e["typ"], e["s0"], e["s1"], None if math.isinf(e["R"]) else e["R"], None if math.isnan(e["oR"]) else e["oR"], None if math.isnan(e["oL"]) else e["oL"]], 1): w(t, i, c, v)
        for c in range(1, 10): t.column_dimensions[chr(64 + c)].width = 16
    wb.save(path)
