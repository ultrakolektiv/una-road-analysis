"""Vožnja kroz koridor BEZ LandXML-a: scena se gradi iz UNA proračuna i ručno unesenih dionica (otvorena trasa / most / tunel).

Geometrija (osovina, niveleta, širina kolovoza, razdjelni pojas, položaj oka, zrake, prepreke) dolazi iz UNA proračuna. Poprečni presjek, ograde, tunel i teren
su parametarski (širina prepreke po vrsti dionice iz tabele 'tipovi prepreka'; ograda na otvorenoj trasi: čelična ili New Jersey, na mostu New Jersey,
u tunelu revizione staze). Izlaz ima istu strukturu kao corridor.build_scene, pa se koristi isti prikaz (una/data/koridor.html)."""
import math
import numpy as np
from .i18n import _T, _TF
from . import preglednost as pg
from .corridor import ST, _interp_s, pg_hpr

DEF_OFF = {"otvorena": 0.78, "most": 1.17, "tunel": 1.70}          # zadani ofset prepreke od ivice kolovoza [m] kad korisnik nije upisao
NJ_X = (0.0, 0.12, 0.18, 0.24, 0.48); NJ_Z = (0.0, 0.167, 0.298, 0.71, 0.71)
DS = 3.0                                                              # razmak presjeka u sceni [m]


def _kind_of(tip):
    t = str(tip or "").lower()
    if "tunel" in t or "galer" in t: return 2
    if "most" in t or "vijadukt" in t: return 1
    return 0


def kind_profile(c, par, s):
    """Vrsta dionice po stacionaži: 0 otvorena trasa, 1 most, 2 tunel – iz unosa 'prepreke' (tip + element ili raspon od–do) iste osovine/sekcije."""
    s = np.asarray(s, float); k = np.zeros(len(s), int)
    pre = [e for e in (par.get("prepreke") or []) if pg._match(e, c) and e.get("tip") not in (None, "")]
    els = pg.element_rows(c)
    for en in pre:
        if en.get("element") in (None, ""): continue
        for e in els:
            if int(en["element"]) == e["no"]: k[(s >= e["s0"] - 1e-9) & (s <= e["s1"] + 1e-9)] = _kind_of(en["tip"])
    for en in pre:
        if en.get("od") in (None, "") or en.get("do") in (None, ""): continue
        k[(s >= float(en["od"]) - 1e-9) & (s <= float(en["do"]) + 1e-9)] = _kind_of(en["tip"])
    return k


def _off_defaults(par):
    tv = {str(k).lower(): v for k, v in (par.get("tipovi_prepreka") or {}).items()}; res = {}
    for kind, keys in (("otvorena", ("otvorena trasa", "otvorena")), ("most", ("most", "vijadukt")), ("tunel", ("tunel",))):
        v = next((tv[k] for k in keys if k in tv), None)
        if isinstance(v, dict): vo, vi = v.get("vani"), v.get("razdjelni", v.get("vani"))
        else: vo = vi = v
        res[kind] = (float(vo) if vo not in (None, "") else DEF_OFF[kind], float(vi) if vi not in (None, "") else DEF_OFF[kind])
    return res


def _ss(x0, x1, v):
    u = min(1.0, max(0.0, (v - x0) / (x1 - x0))); return u * u * (3 - 2 * u)


def _runs(q, mask):
    r = []; i = 0; n = len(q)
    while i < n:
        if mask[i]:
            j = i
            while j + 1 < n and mask[j + 1]: j += 1
            r.append((float(q[i]), float(q[j]))); i = j + 1
        else: i += 1
    return r


def _signed(q, runs):
    """Za svaku tačku: dubina unutar najbliže dionice (+) ili udaljenost do nje (−)."""
    out = np.full(len(q), -1e9)
    for a, b in runs:
        inside = (q >= a) & (q <= b); d = np.where(inside, np.minimum(q - a, b - q), -np.minimum(np.abs(q - a), np.abs(q - b)))
        out = np.maximum(out, d)
    return out


def _ground(q, o, base_ph=0.0):
    """Valovit teren oko trase (relativno prema niveleti): ±3 m."""
    return 2.2 * math.sin(q / 83.0 + o / 57.0 + base_ph) + 1.3 * math.sin(q / 27.0 - o / 33.0) + 0.9 * math.sin(o / 19.0 + q / 140.0)


def _ring(e, hw_extra=1.8, cz=2.4, hv=4.65, n=26):
    hw = e + hw_extra; pts = [(-hw, cz)]
    for i in range(1, n):
        a = math.pi - math.pi * i / n; pts.append((hw * math.cos(a), cz + hv * math.sin(a)))
    pts.append((hw, cz)); return pts


def build_scene_manual(P, par, out, cfg, log=print):
    h_oka = float(par["h_oka"]); nj_open = str((cfg.get("koridor") or {}).get("ograda_otvorena") or par.get("ograda_otvorena", "celicna")).lower().startswith(("nj", "new"))
    offk = _off_defaults(par)
    scene = dict(routes={}, h=h_oka, range=[0, 0], projekat=cfg.get("projekat", ""), h_pr=float(par["h_prepreke"]), h_auto=bool(par.get("h_auto")))
    ROUTES = {}
    for tag in ("F", "B"):
        prep = {}
        for sd in ("D", "L"):
            Rr = out["vp"].get(f"{tag}_{sd}")
            if Rr is None: continue
            A = Rr["A"]; rows = Rr["avail"]["rows"]
            prep[sd] = dict(A=A, rows=rows, rs=np.array([r["s"] for r in rows]), o=np.argsort(A["s"], kind="stable"), ch=Rr["chain"])
        if prep: ROUTES[tag] = prep
    if not ROUTES: raise ValueError(_T("Koridor: nema proračuna preglednosti za ovu osovinu (uključite preglednost)."))
    axis_cache = {}
    for tag, prep in ROUTES.items():
        PD = prep.get("D") or prep["L"]; A = PD["A"]; ch = PD["ch"]; n = len(A["s"])
        # ---- čvorovi scene (razmak ~DS m po osovini), u smjeru vožnje
        sel = [0]; acc = 0.0
        for i in range(1, n):
            acc += math.hypot(A["x"][i] - A["x"][i - 1], A["y"][i] - A["y"][i - 1])
            if acc >= DS or i == n - 1: sel.append(i); acc = 0.0
        # osovina puta i okvir u svakom čvoru
        nod = []
        for i in sel:
            c = ch[int(A["ci"][i])]; s = float(A["s"][i])
            x0, y0, nx, ny = pg.case_frame(c, par, np.array([s]))
            nod.append(dict(i=i, c=c, s=s, E=float(y0[0]), N=float(x0[0]), sinN=-float(nx[0]), cosN=float(ny[0])))
        q = [0.0]
        for a, b in zip(nod, nod[1:]): q.append(q[-1] + math.hypot(b["E"] - a["E"], b["N"] - a["N"]))
        q = np.array(q)
        kinds = np.array([int(kind_profile(d["c"], par, [d["s"]])[0]) for d in nod])
        tun_runs = _runs(q, kinds == 2); br_runs = _runs(q, kinds == 1)
        dt = _signed(q, tun_runs) if tun_runs else np.full(len(q), -1e9); db = _signed(q, br_runs) if br_runs else np.full(len(q), -1e9)
        # krivina i element
        nu = np.unwrap(np.arctan2([d["sinN"] for d in nod], [d["cosN"] for d in nod]))
        kst = np.gradient(nu, q) if len(q) > 3 else np.zeros(len(q))
        kst = np.convolve(kst, np.ones(5) / 5, mode="same")
        names = {"PRAVAC": 0, "PRIJELAZNICA": 1, "KRUZNI_LUK": 2}
        lang_save = None
        from .i18n import get_lang, set_lang
        _lg = get_lang(); _nz = {}
        for _l in ("sr", "en"):
            set_lang(_l); _nz[_l] = _TF("{0} – {1}", _T("ručni unos"), _T("smjer stacionaže") if tag == "F" else _T("suprotno stacionaži"))
        set_lang(_lg)
        o_ = dict(naziv=_nz["en" if _lg == "en" else "sr"], naziv_en=_nz["en"], naziv_bs=_nz["sr"], q=[], s=[], x=[], y=[], z=[], tx=[], ty=[], k=[], el=[], v=[], g=[], D=[], Lz=[], ok=[],
                  kind=[], jn=[], pt=[], hl=[], vr=[], gr=[], F=[], e=[], box=[], ring=[], ln=[], latD=[], latL=[], zeD=[], zeL=[], ob=[], bf=[], ray=[], lim=[], hp=[])
        h_oka_ = h_oka
        for m, d in enumerate(nod):
            i = d["i"]; c = d["c"]; sg = int(c.sg); sta = d["s"]; kd = int(kinds[m]); kind = ("otvorena", "most", "tunel")[kd]
            pr = pg.case_prof(c, par)
            eR_s, eL_s, gR_s, gL_s = pr["eR"], pr["eL"], pr["gR"], pr["gL"]
            eR, eL, gR, gL = (eR_s, eL_s, gR_s, gL_s) if sg > 0 else (eL_s, eR_s, gL_s, gR_s)     # okvir vožnje: desno/lijevo u smjeru vožnje
            tx, ty = sg * d["sinN"], sg * d["cosN"]; nxs, nys = d["cosN"], -d["sinN"]; nxd, nyd = sg * nxs, sg * nys
            x, y = d["E"], d["N"]; z0 = float(A["z"][i])
            lat = {"D": float(pr["pD"]), "L": float(pr["pL"])}; ze = {}
            kk = sg * float(kst[m]) * (1 if sg > 0 else 1)
            kdrv = sg * float(kst[m]); lane = -1 if kdrv < -1 / 9000 else 1
            sdsel = "L" if (lane < 0 and "L" in prep) else ("D" if "D" in prep else "L")
            for sd, pp in prep.items(): ze[sd] = _interp_s(pp["A"], pp["A"]["z"], sta, pp["o"])
            for sd in ("D", "L"): ze.setdefault(sd, ze[sdsel])
            gap = (gR + gL) > 0.4 and c.role == "centralna"
            pvd = [[-eL, -gL], [gR, eR]] if gap else [[-eL, eR]]
            e_half = min(eR, eL) if not gap else min(eR - gR, eL - gL)
            ofo, ofi = offk[kind]
            # ---- poprečni nagib: dvostrešni krov 2,5 % (pravac) / jednostrani u krivini
            R_ = 1.0 / max(abs(kdrv), 1e-9); p = 0.025 if R_ > 2500 else min(0.07, 0.025 + (2500 - R_) / 2500 * 0.045)
            if abs(kdrv) < 1 / 2500.0: zf = lambda o: -0.025 * abs(o) if not gap else -0.025 * (abs(o) - (gR if o > 0 else gL)) * (1 if abs(o) > (gR if o > 0 else gL) else 0)
            else:
                sgn = 1.0 if kdrv > 0 else -1.0                     # desna krivina: vanjska (lijeva) ivica viša
                zf = lambda o, sgn=sgn: -sgn * p * o
            sw = 1.2                                              # bankina
            # ---- lica prepreka (ofset od ivice kolovoza; UNA vrijednost ako postoji, inače zadano po vrsti dionice)
            ob = []
            for kx, ky in (("obrx", "obry"), ("oblx", "obly")):
                j = int(np.argmin(np.abs(PD["A"]["s"] - sta)))
                ob.append(None if not np.isfinite(PD["A"][kx][j]) else round((PD["A"][kx][j] - x) * nxd + (PD["A"][ky][j] - y) * nyd, 3))
            fR = eR + ofo; fL = -(eL + ofo)
            if gap: fL = -(gL - ofi)                                 # lijeva strana vozača = razdjelni pojas
            bf = [round(fR, 3), round(fL, 3)]
            # ---- gornja ploha
            def zr(o): return zf(o)
            top = []
            xs_ = [-eL - sw, -eL, -gL, 0.0, gR, eR, eR + sw] if gap else [-eL - sw, -eL, 0.0, eR, eR + sw]
            for o in xs_:
                oo = o
                zz = zr(oo) if abs(oo) <= max(eL, eR) else zr(eR if oo > 0 else -eL) - 0.04 * (abs(oo) - (eR if oo > 0 else eL))
                top.append((round(oo, 3), round(zz, 3)))
            if gap: top = sorted(set(top))
            full = list(top); box = []; ring = []; hl = None; pt = None; tL = tR = None
            shL, shR = -(eL + sw), eR + sw
            # ---- teren
            gsz = _ground
            m_t = _ss(-60, 40, float(dt[m])) if tun_runs else 0.0            # planina iznad tunela (raste već ispred portala)
            v_b = _ss(-70, 20, float(db[m])) if br_runs else 0.0            # dolina ispod mosta
            def terr_z(o):
                zt = gsz(float(q[m]), o) * (1 - 0.6 * m_t)
                if tun_runs: zt += 38.0 * m_t * max(0.0, 1 - (abs(o) / 130.0) ** 1.6)
                if br_runs: zt -= 9.0 * v_b * max(0.0, 1 - (abs(o) / 110.0) ** 2)
                return zt
            if kind == "otvorena":
                for side, (oe, ze_) in ((1, (eR + sw, top[-1][1])), (-1, (-(eL + sw), top[0][1]))):
                    lst = []
                    for dd in (3, 6, 10, 15, 21, 28, 36, 46, 58, 72, 90, 110, 135, 165, 200, 250, 310):
                        oo = oe + side * dd; zt = terr_z(oo)
                        lim = dd / 1.6 if zt > ze_ else dd / 2.0                  # kosina useka 1:1,6, nasipa 1:2
                        zz = ze_ + min(max(zt - ze_, -lim), lim) if abs(zt - ze_) > lim else zt
                        lst.append((round(oo, 2), round(zz, 2)))
                    full = (lst[::-1] + full) if side < 0 else (full + lst)
                if nj_open:
                    for sdd, face in ((1, fR), (-1, fL)):
                        if gap and sdd < 0: continue
                        zb = zr(face) ; box.append([ST["parapet"], round(min(face, face + sdd * 0.46), 3), round(max(face, face + sdd * 0.46), 3), round(zb + 0.81, 3)])
                if gap and nj_open is False: pass
            elif kind == "most":
                tL = -(eL + 0.9 + max(0.0, ofo)); tR = eR + 0.9 + max(0.0, ofo)
                for side, oe in ((1, tR), (-1, tL)):
                    lst = [(round(oe, 2), round(terr_z(oe), 2))]
                    for dd in (6, 14, 26, 45, 70, 100, 150, 210, 290):
                        oo = oe + side * dd; lst.append((round(oo, 2), round(terr_z(oo), 2)))
                    full = (lst[::-1] + full) if side < 0 else (full + lst)
                for sdd, face in ((1, fR), (-1, fL)):
                    if gap and sdd < 0: continue
                    zb = zr(face)
                    lo, hi = (face, face + 0.48) if sdd > 0 else (face - 0.48, face)
                    prof = [(round(NJ_X[j], 3), round(zb + NJ_Z[j] + 0.08 * 0, 3)) for j in range(5)]
                    box.append([ST["parapet"], round(lo, 3), round(hi, 3), round(zb + 0.71, 3), prof])
                if gap:                                                  # betonska ograda u razdjelnom pojasu mosta
                    w = 0.45; zb = 0.0
                    prof = [(-w, zb), (-w + 0.12, zb + 0.167), (-w + 0.18, zb + 0.298), (-w + 0.24, zb + 0.71), (w - 0.24, zb + 0.71), (w - 0.18, zb + 0.298), (w - 0.12, zb + 0.167), (w, zb)]
                    box.append([ST["medblok"], -w, w, zb + 0.71, [(round(a_, 3), round(b_, 3)) for a_, b_ in prof]])
            else:                                                        # tunel
                ring = _ring(max(eL, eR) if not gap else max(eL, eR) )
                ring = [(round(a_, 3), round(b_, 3)) for a_, b_ in _ring(0.5 * (eL + eR))]
                for sdd, face in ((1, eR + ofo * 0.3), (-1, -(eL + ofo * 0.3))):
                    hi = face + sdd * 1.1; box.append([ST["walk"], round(min(face, hi), 3), round(max(face, hi), 3), 0.12])
                full = [(round(-(eL + 1.5), 3), zr(-eL) - 0.05)] + top + [(round(eR + 1.5, 3), zr(eR) - 0.05)]
                crown = lambda oo: float(np.interp(oo, [r_[0] for r_ in ring], [r_[1] for r_ in ring])) if ring[0][0] <= oo <= ring[-1][0] else None
                hl = []
                for oo in (-300, -220, -160, -115, -80, -55, -38, -26, -17, -11, -6, 0, 6, 11, 17, 26, 38, 55, 80, 115, 160, 220, 300):
                    zt = terr_z(oo); cr = crown(oo)
                    if cr is not None: zt = max(zt, cr + 1.6)
                    hl.append([oo, round(zt, 2)])
                prev_k = int(kinds[m - 1]) if m > 0 else 0; next_k = int(kinds[m + 1]) if m + 1 < len(kinds) else 0
                if prev_k != 2 or next_k != 2:
                    pt = []; offs = [-110, -80, -58, -42, -30, -22, -16, -12, -9, -7, -5.5, -4.5, -3.5, -2.5, -1.5, -.5]
                    for oo in offs + [-v for v in reversed(offs)]:
                        pt.append([oo, round(max(terr_z(oo), 6.0), 2)])
            zones = dict(ug=0, pv=[[round(a_, 3), round(b_, 3)] for a_, b_ in pvd], e=round(e_half, 3), shL=round(shL, 3), shR=round(shR, 3), oe=0, ot=0,
                         med=[round(-gL, 3), 0.0, round(gR, 3), 0.0] if gap else None, nj=1 if (nj_open and kind == "otvorena") else 0)
            if tL is not None: zones["tL"] = round(tL, 3); zones["tR"] = round(tR, 3)
            # ---- zraka iz UNA
            pp = prep[sdsel]; Ar = pp["A"]; sxs = Ar["xa"] - Ar["x"]; sys_ = Ar["ya"] - Ar["y"]; nA = len(Ar["q"])
            order_r = np.argsort(pp["rs"], kind="stable"); rsS = pp["rs"][order_r]
            jj = int(np.clip(np.searchsorted(rsS, sta), 1, len(rsS) - 1)) if len(rsS) > 1 else 0
            cand = [order_r[jj - 1], order_r[jj]] if len(rsS) > 1 else [order_r[0]]
            def _ray(r):
                a = int(r["i"]); hpr = pg_hpr(Ar, par, a); Lz_ = float(r["Lz"]); bD = int(min(r.get("b", a), nA - 1)); bL = int(min(nA - 1, np.searchsorted(Ar["q"], Ar["q"][a] + Lz_)))
                return a, hpr, [float(Ar["x"][a]), float(Ar["y"][a]), float(Ar["z"][a] + h_oka_), float(Ar["xa"][bD] - sxs[bD]), float(Ar["ya"][bD] - sys_[bD]), float(Ar["z"][bD] + hpr),
                                float(Ar["xa"][bL] - sxs[bL]), float(Ar["ya"][bL] - sys_[bL]), float(Ar["z"][bL] + hpr)], float(r["D"]), Lz_
            rr = [pp["rows"][cc] for cc in cand]; Rs = [_ray(r) for r in rr]
            f_ = float(np.clip((sta - rr[0]["s"]) / (rr[1]["s"] - rr[0]["s"]), 0, 1)) if (len(rr) == 2 and rr[1]["s"] != rr[0]["s"]) else 0.0
            lerp = lambda u, v: u + (v - u) * f_
            ray = [round(lerp(u, v), 2) for u, v in zip(Rs[0][2], Rs[-1][2])] + [None]
            D = lerp(Rs[0][3], Rs[-1][3]); Lz = lerp(Rs[0][4], Rs[-1][4]); hpr = Rs[0][1]
            r = rr[0] if f_ < 0.5 else rr[-1]; a_ = Rs[0][0] if f_ < 0.5 else Rs[-1][0]
            kc = r.get("kc")
            if kc is not None:
                kc = int(kc); cand2 = []
                for kx, ky in (("obrx", "obry"), ("oblx", "obly")):
                    if np.isfinite(Ar[kx][kc]): cand2.append((math.hypot(Ar[kx][kc] - Ar["x"][kc], Ar[ky][kc] - Ar["y"][kc]), float(Ar[kx][kc]), float(Ar[ky][kc])))
                if cand2: c0 = min(cand2); ray[9] = [round(c0[1], 2), round(c0[2], 2), round(float(Ar["z"][kc] + hpr), 3)]
            okc = 0 if (r.get("okH", True) and r.get("okV", True)) else (1 if not r.get("okH", True) else 2)
            v_ = float(_interp_s(Ar, Ar["v"], sta, pp["o"])); g_ = float(_interp_s(Ar, Ar["g"], sta, pp["o"]))
            els = pg.element_rows(c); el = 0
            for e_ in els:
                if e_["s0"] - 1e-6 <= sta <= e_["s1"] + 1e-6: el = names.get(e_["typ"], 0); break
            o_["q"].append(round(float(q[m]), 2)); o_["s"].append(round(sta, 2)); o_["x"].append(round(x, 3)); o_["y"].append(round(y, 3)); o_["z"].append(round(z0, 3))
            o_["tx"].append(round(tx, 5)); o_["ty"].append(round(ty, 5)); o_["k"].append(round(kdrv, 6)); o_["el"].append(el); o_["kind"].append(kind); o_["jn"].append(0)
            o_["pt"].append(pt); o_["hl"].append(hl); o_["vr"].append(round(float(_interp_s(Ar, Ar["vr"], sta, pp["o"])), 1) if "vr" in Ar else None); o_["gr"].append(1 if kind == "otvorena" else 0)
            o_["F"].append([[round(a2, 3), round(b2, 3)] for a2, b2 in full]); o_["e"].append(zones); o_["box"].append(box); o_["ring"].append(ring)
            o_["ln"].append(-1 if sdsel == "L" else 1); o_["latD"].append(round(lat["D"], 3)); o_["latL"].append(round(lat["L"], 3)); o_["zeD"].append(round(ze["D"], 3)); o_["zeL"].append(round(ze["L"], 3))
            o_["ob"].append(ob); o_["bf"].append(bf); o_["ray"].append(ray); o_["lim"].append(str(r.get("lim", ""))); o_["hp"].append(round(hpr, 2))
            o_["v"].append(round(v_, 1)); o_["g"].append(round(g_, 2)); o_["D"].append(round(D, 1)); o_["Lz"].append(round(Lz, 1)); o_["ok"].append(okc)
        for key in ("ob", "bf"):
            for kk in (0, 1):                                                   # ograda kao glatka linija
                v = [(r_[kk] if r_ and len(r_) > kk else None) for r_ in o_[key]]; n_ = len(v); i0_ = 0
                while i0_ < n_:
                    if v[i0_] is None: i0_ += 1; continue
                    i1_ = i0_
                    while i1_ + 1 < n_ and v[i1_ + 1] is not None and abs(v[i1_ + 1] - v[i1_]) < 0.35: i1_ += 1
                    seg = np.array(v[i0_:i1_ + 1], float)
                    if len(seg) > 5:
                        md = np.array([np.median(seg[max(0, j - 4):j + 5]) for j in range(len(seg))]); sm = np.array([md[max(0, j - 12):j + 13].mean() for j in range(len(seg))])
                        for j, val in enumerate(sm): o_[key][i0_ + j][kk] = round(float(val), 3)
                    i0_ = i1_ + 1
        scene["routes"][tag] = o_
    n_all = sum(len(r["q"]) for r in scene["routes"].values())
    log(_TF("Koridor (ručni unos): scena izrađena ({0} presjeka).", n_all))
    return scene
