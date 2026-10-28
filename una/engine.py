"""Proračun profila brzine (V85) prema srpskim smjernicama + teška vozila."""
from .i18n import _T, _TF, TrDict, tr_obj
import math, copy
import numpy as np
from .parse import Axis

def ft_diag(m, CdA, rho=1.225, g=9.81, frl0=0.01, frl_v=44.73):
    """Kriva sile vuče Ft(v) merodavnog teretnog vozila iz slike 3-10 Priloga 2: u ravnoteži je Ft jednaka zbiru otpora,
    a ravnotežne brzine na usponima 2…7 % su 68, 55, 43, 33, 24 i 15 km/h."""
    pts = []
    for gr, vk in ((2, 68), (3, 55), (4, 43), (5, 33), (6, 24), (7, 15)):
        v = vk / 3.6; W = m * g
        pts.append([float(vk), round(frl0 * (1 + v / frl_v) * W + 0.5 * rho * CdA * v * v + W * gr / 100, 0)])
    return sorted(pts)


def ft_of(veh, v, W):
    """Sila vuče [N] pri brzini v [m/s]: kriva iz dijagrama (ako je zadana), inače konstantna snaga η·P/v; ograničeno prianjanjem μ·W."""
    k = veh.get("Ft_kriva")
    if k:
        vk = v * 3.6; X = [p[0] for p in k]; Y = [p[1] for p in k]
        if vk <= X[0]: F = Y[0]
        elif vk >= X[-1]: F = Y[-1] * X[-1] / max(vk, 1e-9)       # iznad posljednje tačke – konstantna snaga
        else: F = float(np.interp(vk, X, Y))
        return min(F, veh["mu"] * W)
    return min(veh["eta"] * veh["P"] * 1000 / max(v, 3.0), veh["mu"] * W)


DEFAULTS = dict(
    projekat="Glavni projekat – dionica", Vr=100.0, dodatak_maxVr=20.0, korak=5.0, a=0.8, d=0.8,
    ulazna_brzina=None, g=9.81, rho=1.225, b=0.24, prazan_hod=2.0, frl0=0.01, frl_v=44.73,
    Vr_tab=[40, 50, 60, 70, 80, 90, 100, 110, 120, 130],
    Rmin_tab=[43.4, 75.7, 118.1, 175.4, 252.0, 335.7, 437.4, 560.5, 667.0, 782.8],   # slika 3-07: minR = Vri² / (127·(fR + ipk,max)), ipk,max = 7 %, fR iz tabele 3-05
    fT=[0.44, 0.41, 0.38, 0.36, 0.34, 0.32, 0.30, 0.29, 0.28, 0.27],
    fR=[0.22, 0.19, 0.17, 0.15, 0.13, 0.12, 0.11, 0.10, 0.10, 0.10],
    iN_tab=[-10, -8, -7, -5, 4, 4.1, 6, 8, 10],          # slika 3-08 (očitano s grafikona, tačnost ≈ ±5 km/h)
    ViN_tab=[70, 90, 100, 130, 130, 120, 100, 75, 50],
    maxVr_tab=None, obrazac_puta=True,
    max_nagib=5.0,
    vozila=[dict(naziv="merodavno teretno vozilo prema Pravilniku (slika 3-10 Priloga 2)", kratko="Tegljač (Pravilnik)", m=40000, P=None, CdA=5.2, eta=0.90, vlim=80, gam=1.06, mu=0.5, Ft_kriva=ft_diag(40000, 5.2)),
            dict(naziv="teško teretno vozilo – tegljač s poluprikolicom (savremeno vozilo)", kratko="Tegljač (savremeni)", m=40000, P=350, CdA=5.2, eta=0.90, vlim=80, gam=1.06, mu=0.5),
            dict(naziv="autovoz (vučno vozilo s prikolicom)", kratko="Autovoz", m=36000, P=320, CdA=7.0, eta=0.90, vlim=80, gam=1.06, mu=0.5),
            dict(naziv="putničko vozilo (srednja klasa)", kratko="Putničko vozilo", m=1500, P=90, CdA=0.66, eta=0.90, vlim=None, gam=1.10, mu=0.6, b=0.28, prazan_hod=0.8)],
)

TIPOVI = TrDict({"razdvojene": "dvije odvojene osovine (desna i lijeva)", "centralna": "centralna osovina (oba smjera)",
          "jedna_naprijed": "jedna osovina – smjer stacionaže", "jedna_nazad": "jedna osovina – suprotno smjeru stacionaže"})


class Params:
    def __init__(self, cfg):
        c = copy.deepcopy(DEFAULTS); c.update({k: v for k, v in cfg.items() if k in DEFAULTS and v is not None})
        self.__dict__.update(c)
        self.maxVr = self.Vr + self.dodatak_maxVr
        if self.maxVr_tab not in (None, "", 0): self.maxVr = min(self.maxVr, float(self.maxVr_tab))      # tabela 3-04 Priloga 2
        self.a_nom, self.d_nom = self.a, self.d
        if self.obrazac_puta: self.a = self.d = 1 / (0.1 * 3.6 ** 2)      # slika 3-09: L = 0,1·Vsr·ΔV  ⇔  V2² − V1² = 20·L [km/h]  ⇒  a = d = 0,7716 m/s²
        for v in self.vozila:
            if v.get("Ft_kriva") and v.get("P") in (None, "", 0):
                v["P"] = round(max(F * vk / 3.6 for vk, F in v["Ft_kriva"]) / (v["eta"] * 1000), 0)      # najveća snaga na krivoj (informativno)
        self.vozila = [dict(v, naziv=_T(v["naziv"]), kratko=_T(v["kratko"]), vlim=(self.maxVr if v.get("vlim") in (None, "", 0) else v["vlim"]),
                            b=(self.b if v.get("b") in (None, "") else v["b"]), prazan_hod=(self.prazan_hod if v.get("prazan_hod") in (None, "") else v["prazan_hod"])) for v in self.vozila]
        if self.ulazna_brzina is None: self.ulazna_brzina = self.maxVr

    def vpR(self, R):
        return min(self.maxVr, float(np.interp(R, self.Rmin_tab, self.Vr_tab)))

    def vpG(self, g):
        return float(np.interp(g, self.iN_tab, self.ViN_tab))

    def fRv(self, V):
        return float(np.interp(V, self.Vr_tab, self.fR))

    def RminVr(self):
        return float(np.interp(self.Vr, self.Vr_tab, self.Rmin_tab))


class Case:
    pass


def build_cases(cfg, P, log=print):
    """Iz konfiguracije pravi osovine, sekcije i slučajeve (smjerove vožnje)."""
    axes = {}; sections = []
    def axis(spec, name):
        key = (spec["h"], spec["v"], spec["x"])
        if key not in axes:
            axes[key] = Axis(name, *key, cs_col=spec.get("cs_col")); log(axes[key].info())
        return axes[key]
    cases = []
    for si, sec in enumerate(sorted(cfg["sekcije"], key=lambda s: s["od"]), 1):
        sec = dict(sec); sec["no"] = si; tip = sec["tip"]; sections.append(sec)
        sa, sb = float(sec["od"]), float(sec["do"])
        if tip == "razdvojene":
            specs = [("D", +1, "desna", _TF('desna osovina (D{0})', si), _T('desni kolovoz')), ("L", -1, "lijeva", _TF('lijeva osovina (L{0})', si), _T('lijevi kolovoz'))]
        elif tip == "centralna":
            specs = [("F", +1, "centralna", _TF('centralna osovina (sekcija {0})', si), _T("centralna →")), ("B", -1, "centralna", _TF('centralna osovina (sekcija {0})', si), _T("centralna ←"))]
        elif tip == "jedna_naprijed":
            specs = [("F", +1, 'osovina', _TF('osovina (sekcija {0})', si), _T('osovina →'))]
        elif tip == "jedna_nazad":
            specs = [("B", -1, 'osovina', _TF('osovina (sekcija {0})', si), _T('osovina ←'))]
        else:
            raise ValueError(f"Nepoznat tip sekcije: {tip}")
        for tag, sg, role, aname, short in specs:
            c = Case(); c.sec = sec; c.no = si; c.tag = tag; c.sg = sg; c.role = role
            c.key = f"{tag}{si}"; c.axis = axis(sec[role], aname)
            c.short = f"{short} [{sa:.0f}–{sb:.0f}]"; c.shortname = short
            c.SA, c.SB = sa, sb
            c.caps = [(float(z["od"]), float(z["do"]), float(z["v"])) for z in sec.get("ogranicenja", [])]
            c.label = f"{_T('Desni kolovoz') if tag=='D' and tip=='razdvojene' else _T('Lijevi kolovoz') if tag=='L' and tip=='razdvojene' else _T('Centralna osovina') if tip=='centralna' else _T('Osovina')}, " \
                      f"{_T('smjer stacionaže') if sg==1 else _T('suprotno smjeru stacionaže')}, st. {sa:.0f} – {sb:.0f}" 
            cases.append(c)
    return sections, cases, list(axes.values())


def grid(SA, SB, step):
    S = list(np.arange(SA, SB - 1e-9, step))
    if abs(S[-1] - SB) > 1e-9: S.append(SB)
    return np.array(S)


def prepare(c, P):
    ax = c.axis; S = grid(c.SA, c.SB, P.korak); c.S = S; c.N = len(S); c.DSA = np.diff(S)
    if S[0] < ax.s_min - 1e-6 or S[-1] > ax.s_max + 1e-6:
        raise ValueError(_TF('Raspon {0}–{1} ({2}) izlazi iz osovine {3} (st. {4:.1f}–{5:.1f})', c.SA, c.SB, c.label, ax.name, ax.s_min, ax.s_max))
    c.IDX = np.array([ax.elem_index(s) for s in S])
    zg = [ax.vert(s) for s in S]; c.Z = np.array([a for a, b in zg]); c.G = np.array([b for a, b in zg])
    c.RR = np.array([abs(ax.elems[i]["R0"]) if ax.elems[i]["typ"] == "KRUZNI_LUK" else 0.0 for i in c.IDX])
    c.ENO = np.array([ax.elems[i]["no"] for i in c.IDX])
    vpR_el = [P.vpR(abs(e["R0"])) if e["typ"] == "KRUZNI_LUK" else P.maxVr for e in ax.elems]
    c.VPR = np.array([vpR_el[i] for i in c.IDX])
    c.VPG = np.array([P.vpG(c.sg * g) for g in c.G])
    c.CL = np.array([ax.cross(s) for s in S])
    c.L = c.SB - c.SA
    # uzastopni elementi → jedinice (krivine / pravci)
    units = []
    for e in ax.elems:
        if not (e["s1"] > c.SA and e["s0"] < c.SB and e["L"] > 0.5): continue
        if e["typ"] == "PRAVAC":
            units.append(dict(kind="P", s0=e["s0"], s1=e["s1"], R=math.inf, has_arc=False)); continue
        u = units[-1] if units and units[-1]["kind"] == "K" else None
        newu = u is None or (e["typ"] == "KRUZNI_LUK" and u["has_arc"]) or (e["typ"] == "PRIJELAZNICA" and math.isinf(e["R0"]) and u["has_arc"])
        if newu:
            u = dict(kind="K", s0=e["s0"], s1=e["s1"], R=math.inf, has_arc=False); units.append(u)
        else:
            u["s1"] = e["s1"]
        if e["typ"] == "KRUZNI_LUK":
            u["has_arc"] = True; u["R"] = abs(e["R0"]); u["dir"] = "desna" if e["R0"] > 0 else "lijeva"
    c.units = units


def capval(c, s, scen):
    if scen != 2: return 1e9
    v = [z[2] for z in c.caps if z[0] <= s <= z[1]]
    return min(v) if v else 1e9


def target(c, P, scen):
    return np.array([min(c.VPR[i], c.VPG[i], capval(c, c.S[i], scen)) for i in range(c.N)])


def car_chain(chain, P, scen):
    """Prolaz ubrzanja naprijed i usporenja nazad kroz cijeli lanac slučajeva (u smjeru vožnje)."""
    trav = []
    for c in chain:
        T = target(c, P, scen); c.T = T
        order = np.arange(c.N) if c.sg == 1 else np.arange(c.N - 1, -1, -1)
        ds = np.abs(np.diff(c.S[order]))
        trav.append((c, order, T[order] / 3.6, ds))
    J = []; prev = P.ulazna_brzina / 3.6
    for c, order, T, ds in trav:
        j = T.copy(); j[0] = min(j[0], prev)
        for i in range(1, len(j)): j[i] = min(j[i], math.sqrt(j[i - 1] ** 2 + 2 * P.a * ds[i - 1]))
        J.append(j); prev = j[-1]
    K = [None] * len(trav); nxt = None
    for q in range(len(trav) - 1, -1, -1):
        c, order, T, ds = trav[q]; j = J[q]; k = j.copy()
        if nxt is not None: k[-1] = min(k[-1], nxt)
        for i in range(len(k) - 2, -1, -1): k[i] = min(k[i], math.sqrt(k[i + 1] ** 2 + 2 * P.d * ds[i]))
        K[q] = k; nxt = k[0]
    for q, (c, order, T, ds) in enumerate(trav):
        v = np.zeros(c.N); v[order] = K[q] * 3.6; c.V = v
        a = np.zeros(c.N); a[order] = J[q] * 3.6; c.Vacc = a


def truck_run(c, veh, P, v0):
    m = veh["m"]; W = m * P.g; vl = veh["vlim"] / 3.6
    idx = list(range(c.N)) if c.sg == 1 else list(range(c.N - 1, -1, -1))
    v = v0 if v0 is not None else vl
    vs = [v]; fs = [0.0]; ts = [0.0]; fuel = 0.0; tt = 0.0
    for a, b in zip(idx[:-1], idx[1:]):
        Gm = c.sg * (c.G[a] + c.G[b]) / 200; ds = abs(c.S[b] - c.S[a])
        frl = P.frl0 * (1 + v / P.frl_v); Fr = frl * W + 0.5 * P.rho * veh["CdA"] * v * v + W * Gm
        Ft = ft_of(veh, v, W)
        if v >= vl - 1e-9 and Ft >= Fr: vn = vl; Fu = max(Fr, 0)
        else:
            vn = min(vl, math.sqrt(max(v * v + 2 * (Ft - Fr) / (veh["gam"] * m) * ds, 9.0))); Fu = Ft if Fr > 0 else 0.0
        vav = (v + vn) / 2; dt = ds / vav
        fl = veh["prazan_hod"] * dt / 3600 if Fr <= 0 else veh["b"] * (Fu * vav / veh["eta"] / 1000) * dt / 3600
        fuel += fl; tt += dt; v = vn; vs.append(v); fs.append(fuel); ts.append(tt)
    arr = np.zeros(c.N); far = np.zeros(c.N); tar = np.zeros(c.N)
    arr[idx] = np.array(vs) * 3.6; far[idx] = fs; tar[idx] = ts
    return dict(v=arr, fuel=far, time=tar, T=tt, Fu=fuel, v0=v0 if v0 is not None else vl, vend=vs[-1])


def stat(c, V):
    L = c.L; ds = c.DSA
    m = float(np.sum((V[:-1] + V[1:]) / 2 * ds) / L)
    var = float(np.sum((((V[:-1] - m) ** 2 + (V[1:] - m) ** 2) / 2) * ds) / L)
    sd = math.sqrt(var)
    t = float(np.sum(ds * 3.6 * (1 / V[:-1] + 1 / V[1:]) / 2))
    return dict(mean=m, sd=sd, Dh=sd / m * 100, vmin=float(V.min()), vmax=float(V.max()), time=t, L=L)


def combine(items):
    """items: list of (stat dict, L) → statistika za spojene dionice."""
    Lt = sum(x["L"] for x in items); I1 = sum(x["mean"] * x["L"] for x in items)
    I2 = sum((x["sd"] ** 2 + x["mean"] ** 2) * x["L"] for x in items)
    m = I1 / Lt; sd = math.sqrt(max(I2 / Lt - m * m, 0))
    out = dict(mean=m, sd=sd, Dh=sd / m * 100, vmin=min(x["vmin"] for x in items), vmax=max(x["vmax"] for x in items), L=Lt,
               time=sum(x["time"] for x in items))
    if all("fuel" in x for x in items): out["fuel"] = sum(x["fuel"] for x in items)
    return out


def chains(cases):
    fw = sorted([c for c in cases if c.sg == 1], key=lambda c: c.SA)
    bw = sorted([c for c in cases if c.sg == -1], key=lambda c: -c.SB)
    return fw, bw


def run(cfg, log=print):
    P = Params(cfg)
    sections, cases, axes = build_cases(cfg, P, log)
    for c in cases: prepare(c, P)
    fw, bw = chains(cases)
    has_caps = any(c.caps for c in cases)
    res = {}
    for scen in ([1, 2] if has_caps else [1]):
        for ch in (fw, bw):
            if ch: car_chain(ch, P, scen)
        res[scen] = {c.key: (c.V.copy(), c.T.copy(), c.Vacc.copy()) for c in cases}
    # scenarij 1 postaje osnovni rezultat
    for c in cases: c.V, c.T, c.Vacc = res[1][c.key]
    for c in cases:
        c.stc = stat(c, c.V)
        if has_caps: c.V2, c.T2, _ = res[2][c.key]; c.stc2 = stat(c, c.V2)
    for ch in (fw, bw):
        prev = [None] * len(P.vozila)
        for c in ch:
            c.trk = []
            for k, veh in enumerate(P.vozila):
                r = truck_run(c, veh, P, prev[k]); c.trk.append(r); prev[k] = r["vend"]
            for k in range(len(P.vozila)):
                c.trk[k]["stat"] = stat(c, np.maximum(c.trk[k]["v"], 1))
                c.trk[k]["stat"]["fuel"] = c.trk[k]["Fu"]; c.trk[k]["stat"]["time"] = c.trk[k]["T"]
    return P, sections, cases, axes, fw, bw, has_caps
