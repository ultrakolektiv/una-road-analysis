"""Vizualizacija vožnje iz oka vozača (samostalna HTML datoteka, canvas 2D, bez vanjskih biblioteka).
Putanja, niveleta, brzina Vp i preglednost dolaze iz UNA proračuna; poprečni profili (otvorena trasa / most / tunel) iz NPP-a (una/npp.py)."""
import json, math, os
import numpy as np
from .i18n import _T, _TF, get_lang
from . import npp as _npp, preglednost as pg

STEP = 2.0          # razmak čvorova u HTML-u [m]


def _smooth(a, n):
    if n <= 1: return a
    k = np.ones(n) / n; pad = n // 2
    return np.convolve(np.pad(a, (pad, n - 1 - pad), mode="edge"), k, mode="valid")


def build_data(P, par, out, cfg, log=print):
    N = _npp.resolve(cfg)
    keys = list(N["profili"]); pf_list = []
    for k in keys:
        p = N["profili"][k]
        pf_list.append(dict(key=k, naziv=_T(p.get("naziv", k)), tip=p.get("tip", "otvorena"), iv=p.get("ivicna_traka", 0.5), w=p.get("sirina_trake", 3.5), bank=p.get("bankina", 0),
                            ofR=p["vani"]["ofset"], hR=p["vani"]["visina"], opR=_T(p["vani"].get("opis", "")), ofL=p["razdjelni"]["ofset"], hL=p["razdjelni"]["visina"], opL=_T(p["razdjelni"].get("opis", "")),
                            cr=p.get("razdjelni_pojas", 0.0), hs=p.get("visina_svoda", 5.0), sl=p.get("slobodna_visina", 4.7), dp=p.get("debljina_ploce", 1.9), teren=p.get("teren", "")))
    routes = {}
    for key, R in out["vp"].items():
        if key.split("_")[1] != "D" and not (cfg.get("vizura_opcije") or {}).get("obje_trake"): continue
        A = R["A"]; ch = R["chain"]; n = len(A["xa"])
        rows = R["avail"]["rows"]            # zahtijevana = Vp preglednost (L_vp)
        qq = A["q"]; idx = np.arange(0, n, max(1, int(round(STEP / max(np.median(np.diff(qq)), 0.01)))))
        if idx[-1] != n - 1: idx = np.append(idx, n - 1)
        th = np.unwrap(np.arctan2(A["ty"], A["tx"])); k = np.gradient(th, qq + np.arange(n) * 1e-9); k = _smooth(k, 21)
        rq = np.array([r["q"] for r in rows]); rD = np.array([r["D"] for r in rows]); rL = np.array([r["Lz"] for r in rows])
        rok = np.array([0 if (r.get("okH", True) and r.get("okV", True)) else (1 if not r.get("okH", True) else 2) for r in rows])
        ci = A["ci"]; sg = np.zeros(n); de = np.zeros(n); lr = np.zeros(n); rr = np.zeros(n); cl = np.zeros(n); cd = np.zeros(n); pf = np.zeros(n, int); el = np.zeros(n, int); Rm = np.zeros(n)
        pcache = {}
        for c_i, c in enumerate(ch):
            m = ci == c_i
            if not m.any(): continue
            pr = pg.case_prof(c, par); d = pr["pD"] if key.endswith("_D") else pr["pL"]
            g_t, e_t = (pr["gR"], pr["eR"]) if c.sg == 1 else (pr["gL"], pr["eL"]); e_o = pr["eL"] if c.sg == 1 else pr["eR"]
            left_abs = g_t if c.role == "centralna" else -e_o
            sg[m] = c.sg; de[m] = d; lr[m] = left_abs - d; rr[m] = e_t - d
            ss = A["s"][m]; ax = c.axis
            cl[m] = np.interp(ss, ax.cs_s, ax.cs_l); cd[m] = np.interp(ss, ax.cs_s, ax.cs_d)
            for j in np.where(m)[0]:
                pk, _ = _npp.profile_at(N, c.role, float(A["s"][j]), c.sec["no"]); pf[j] = keys.index(pk)
                e = ax.elems[ax.elem_index(float(A["s"][j]))]; el[j] = {"PRAVAC": 0, "PRIJELAZNICA": 1, "KRUZNI_LUK": 2}[e["typ"]]; Rm[j] = abs(e["R0"] if e["typ"] == "KRUZNI_LUK" else (e["R1"] if math.isinf(e["R0"]) else e["R0"])) if e["typ"] != "PRAVAC" else 0
        f = lambda a, d=2: [round(float(v), d) for v in a[idx]]
        routes[key] = dict(naziv=_TF("{0}, {1}", _T("smjer stacionaže") if R["tag"] == "F" else _T("suprotno stacionaži"), pg.SIDE_NAME[R["side"]]),
                           n=len(idx), s=f(A["s"], 1), q=f(qq, 1), x=f(A["xa"]), y=f(A["ya"]), z=f(A["z"], 3), v=f(A["v"], 1), g=f(A["g"], 2), k=[round(float(v), 6) for v in k[idx]],
                           cl=f(cl, 2), cd=f(cd, 2), sg=[int(v) for v in sg[idx]], de=f(de, 2), lr=f(lr, 2), rr=f(rr, 2), pf=[int(v) for v in pf[idx]], el=[int(v) for v in el[idx]], R=f(Rm, 0),
                           D=[round(float(np.interp(v, rq, rD)), 1) for v in qq[idx]], Lz=[round(float(np.interp(v, rq, rL)), 1) for v in qq[idx]],
                           ok=[int(rok[min(len(rok) - 1, int(np.searchsorted(rq, v)))]) for v in qq[idx]])
    return dict(routes=routes, profili=pf_list, h=float(par.get("h_oka", 1.0)), Vr=float(P.Vr), projekat=cfg.get("projekat", ""), lang=get_lang(), izvor=N.get("izvor", ""))


def write_html(path, P, par, out, cfg, log=print):
    data = build_data(P, par, out, cfg, log)
    tpl = open(os.path.join(os.path.dirname(__file__), "data", "vizura.html"), encoding="utf-8").read()
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(path, "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/null", js))
    log(_TF("Vizualizacija vožnje (HTML): {0}", path))
    return path
