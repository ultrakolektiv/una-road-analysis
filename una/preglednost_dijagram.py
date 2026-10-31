"""Dijagrami: brzina Vp (V85) i preglednost na istoj stacionaži (gore brzina, dolje potrebna i raspoloživa preglednost).
Izlaz: PNG + PDF po osovini vozne trake (smjer / strana) i jedan DXF sa svim dijagramima (jedinica: mm papira)."""
from .i18n import _T, _TF
import math
import numpy as np
from .dxf import Dxf
from . import preglednost as pg
from .preglednost_crtez import tname, kmfmt


def _series(out, key):
    vp = out["vp"][key]["rows"]
    s = np.array([r["s"] for r in vp]); V = np.array([r["V"] for r in vp]); Lz = np.array([r["Lz"] for r in vp])
    o = np.argsort(s)
    d = dict(s=s[o], V=V[o], Lz=Lz[o], Lfix=None, D=None, lim=None, ok=None, Dh=None, Dv=None)
    av = out["vp"][key].get("avail")
    if av:
        ra = av["rows"]; sa = np.array([r["s"] for r in ra]); oa = np.argsort(sa); tr = np.array([r["trunc"] for r in ra])[oa]
        d["sa"] = sa[oa]; d["Dv"] = np.where(tr, np.nan, np.array([r["Dv"] for r in ra])[oa])
        if out["vp"][key]["A"]["has_ob"]: d["Dh"] = np.where(tr, np.nan, np.array([r["Dh"] for r in ra])[oa])
    if out.get("zaht") and key in out["zaht"] and out.get("_fixL"): d["Lfix"] = float(out["zaht"][key]["rows"][0]["Lz"])
    if out.get("ocek") and key in out["ocek"]:
        e = out["ocek"][key]["rows"]; se = np.array([r["s"] for r in e]); oe = np.argsort(se)
        d["se"] = se[oe]; d["D"] = np.array([r["D"] for r in e])[oe]; d["Lreq"] = np.array([r["Lz"] for r in e])[oe]
        d["ok"] = np.array([r["ok"] for r in e])[oe]; d["trunc"] = np.array([r["trunc"] for r in e])[oe]
        d["D"] = np.where(d["trunc"], np.nan, d["D"])                     # zraka koja izlazi van kraja trase – nije mjerodavna
    return d


def make_png(P, par, out, base, log=print):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    files = []
    for key in out["vp"]:
        d = _series(out, key)
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(15, 8.5), sharex=True, gridspec_kw=dict(height_ratios=[1, 1.25], hspace=0.08))
        a1.plot(d["s"], d["V"], color="#1f3fd0", lw=1.6, label=(_T('Računska brzina Vr (projektni zadatak)') if par.get("_vr") else _T('Projektna brzina Vp (V85)')))
        a1.axhline(P.Vr, color="#888", ls="--", lw=1, label=_TF('Računska brzina Vr = {0:g} km/h', P.Vr))
        a1.set_ylabel(_T('Brzina [km/h]')); a1.grid(alpha=0.3); a1.legend(loc="lower right", fontsize=8)
        a1.set_title(_TF('{0} – brzina i preglednost – {1}', P.projekat, tname(key)), fontsize=11)
        a1.set_ylim(0, max(P.Vr * 1.1, float(d["V"].max()) * 1.05))
        a2.plot(d["s"], d["Lz"], color="#2ca02c", lw=1.4, label=(_T('Potrebna preglednost Pz za Vr, nagib') if par.get("_vr") else _T('Potrebna preglednost Lz (Vp, nagib')) + (f", +{par['dodatak_L']:g} m" if par["dodatak_L"] else "") + ")")
        if d["Lfix"]: a2.axhline(d["Lfix"], color="#ff7f00", ls="-.", lw=1.2, label=_TF('Zahtijevana preglednost L = {0:g} m', d['Lfix']))
        cap = float(par["Lmax"])
        if d["Dv"] is not None: a2.plot(d["sa"], np.minimum(d["Dv"], cap), color="#1f77b4", lw=1.0, ls="--", label=_T('Vertikalna raspoloživa preglednost (niveleta)'))
        if d["Dh"] is not None: a2.plot(d["sa"], np.minimum(d["Dh"], cap), color="#8c564b", lw=1.0, ls=":", label=_T('Horizontalna raspoloživa preglednost (prepreke)'))
        if d["D"] is not None:
            a2.plot(d["se"], d["D"], color="#c0105a", lw=1.2, label=_T('Očekivana (raspoloživa) preglednost – manja od horizontalne i vertikalne'))
            bad = (~d["ok"]); a2.fill_between(d["se"], d["D"], d["Lreq"], where=bad, color="#e41a1c", alpha=0.35, label=_T('Preglednost nedovoljna'))
            a2.set_ylim(0, min(float(par["Lmax"]) * 1.05, max(float(d["Lz"].max()) * 2.5, float(np.nanpercentile(d["D"], 90)) * 1.1)))
        else:
            top = float(d["Lz"].max()) * 1.3
            if d["Dv"] is not None: top = max(top, min(cap, float(np.nanpercentile(d["Dv"], 90))) * 1.1)
            a2.set_ylim(0, min(cap * 1.05, top))
        a2.set_ylabel(_T('Preglednost [m]')); a2.set_xlabel(_T('Stacionaža [m]')); a2.grid(alpha=0.3); a2.legend(loc="upper right", fontsize=8)
        a2.ticklabel_format(useOffset=False, style="plain")
        fig.tight_layout()
        for ext in ("png", "pdf"):
            p = f"{base}_{key}.{ext}"; fig.savefig(p, dpi=140); files.append(p)
        plt.close(fig)
    log(_T('Dijagrami brzine i preglednosti: ') + ", ".join(f.rsplit("/", 1)[-1] for f in files if f.endswith("png")))
    return files


def make_dxf(P, par, out, path, log=print, hs=10.0, vs=2.0, ds=5.0):
    """DXF dijagram (jedinica mm papira): 1 mm = hs m po stacionaži, vs km/h po brzini, ds m po preglednosti."""
    d = Dxf(ltscale=1.0)
    for n, c, lt in (("OKVIR", 7, "CONTINUOUS"), ("MREZA", 253, "CONTINUOUS"), ("TEKST", 7, "CONTINUOUS"), (_T('BRZINA_VP'), 5, "CONTINUOUS"), (_T('BRZINA_VR'), 8, "DASHED"),
                     (_T('PREGLEDNOST_POTREBNA'), 3, "CONTINUOUS"), (_T('PREGLEDNOST_ZAHTIJEVANA'), 30, "DASHDOT"), (_T('PREGLEDNOST_RASPOLOZIVA'), 6, "CONTINUOUS"), (_T('PREGLEDNOST_VERTIKALNA'), 5, "DASHED"), (_T('PREGLEDNOST_HORIZONTALNA'), 52, "DOT"), (_T('PREGLEDNOST_NEDOVOLJNA'), 1, "CONTINUOUS")):
        d.layer(n, c, lt)
    H = 2.5; y0 = 0.0
    for key in out["vp"]:
        s = _series(out, key); smin = math.floor(s["s"].min() / 500) * 500; smax = math.ceil(s["s"].max() / 500) * 500
        X = lambda v: (v - smin) / hs
        vmax = math.ceil(max(P.Vr * 1.1, s["V"].max() * 1.05) / 20) * 20
        dmax_src = max(float(s["Lz"].max()) * 1.3, float(s["Lfix"] or 0) * 1.3)
        if s["D"] is not None: dmax_src = max(dmax_src, min(float(par["Lmax"]), float(np.nanmax(s["D"]))) * 1.05)
        dmax = math.ceil(dmax_src / 50) * 50
        hV = vmax / vs; hD = dmax / ds; W = X(smax)
        yD0 = y0; yV0 = y0 + hD + 18                                    # dolje preglednost, gore brzina
        d.text("TEKST", 0, yV0 + hV + 10, 3.5, _TF('{0} – brzina i preglednost – {1}', P.projekat, tname(key)))
        for (yb, hh, mx, step, st, lab) in ((yV0, hV, vmax, 20, vs, _T('Brzina [km/h]')), (yD0, hD, dmax, 50, ds, _T('Preglednost [m]'))):
            d.poly("OKVIR", [(0, yb), (W, yb), (W, yb + hh), (0, yb + hh)], closed=True)
            for v in np.arange(0, mx + 1e-6, step):
                yy = yb + v / st; d.line("MREZA", 0, yy, W, yy); d.text("TEKST", -2, yy - 0.9, H * 0.8, f"{v:g}", align="r")
            d.text("TEKST", 0, yb + hh + 2, H, lab)
        for sx in np.arange(smin, smax + 1e-6, 500):
            for yb, hh in ((yV0, hV), (yD0, hD)): d.line("MREZA", X(sx), yb, X(sx), yb + hh)
            d.text("TEKST", X(sx), yD0 - 6, H * 0.8, kmfmt(sx), rot=90, align="r" if False else "l")
        d.poly(_T('BRZINA_VP'), [(X(a), yV0 + b / vs) for a, b in zip(s["s"], s["V"])])
        d.line(_T('BRZINA_VR'), 0, yV0 + P.Vr / vs, W, yV0 + P.Vr / vs)
        d.poly(_T('PREGLEDNOST_POTREBNA'), [(X(a), yD0 + min(b, dmax) / ds) for a, b in zip(s["s"], s["Lz"])])
        if s["Lfix"]: d.line(_T('PREGLEDNOST_ZAHTIJEVANA'), 0, yD0 + s["Lfix"] / ds, W, yD0 + s["Lfix"] / ds)
        from .preglednost_crtez import _runs
        for arr, xs_, lay in ((s["Dv"], s.get("sa"), _T('PREGLEDNOST_VERTIKALNA')), (s["Dh"], s.get("sa"), _T('PREGLEDNOST_HORIZONTALNA'))):
            if arr is None: continue
            xx = [X(a) if not math.isnan(b) else float("nan") for a, b in zip(xs_, arr)]; yy = [yD0 + min(b, dmax, par["Lmax"]) / ds if not math.isnan(b) else float("nan") for b in arr]
            for rn in _runs(xx, yy): d.poly(lay, rn)
        if s["D"] is not None:
            from .preglednost_crtez import _runs
            xs = [X(a) if not math.isnan(b) else float("nan") for a, b in zip(s["se"], s["D"])]; ys = [yD0 + min(b, dmax) / ds if not math.isnan(b) else float("nan") for b in s["D"]]
            for rn in _runs(xs, ys): d.poly(_T('PREGLEDNOST_RASPOLOZIVA'), rn)
            run = []
            for a, b, ok in zip(s["se"], s["D"], s["ok"]):
                if not ok: run.append((X(a), yD0 + min(b, dmax) / ds))
                else:
                    if len(run) > 1: d.poly(_T('PREGLEDNOST_NEDOVOLJNA'), run, width=0.6)
                    run = []
            if len(run) > 1: d.poly(_T('PREGLEDNOST_NEDOVOLJNA'), run, width=0.6)
        lx = W + 6; ly = yV0 + hV
        for lay, txt in ((_T('BRZINA_VP'), _T('Računska brzina Vr') if par.get("_vr") else _T('Projektna brzina Vp (V85)')), (_T('BRZINA_VR'), _TF('Računska brzina Vr = {0:g} km/h', P.Vr)), (_T('PREGLEDNOST_POTREBNA'), _T('Potrebna preglednost Pz za Vr i nagib') if par.get("_vr") else _T('Potrebna preglednost Lz (Vp i nagib)')),
                         (_T('PREGLEDNOST_ZAHTIJEVANA'), _T('Zahtijevana preglednost L (zadao projektant)')), (_T('PREGLEDNOST_VERTIKALNA'), _T('Vertikalna raspoloživa preglednost (niveleta)')), (_T('PREGLEDNOST_HORIZONTALNA'), _T('Horizontalna raspoloživa preglednost (prepreke)')), (_T('PREGLEDNOST_RASPOLOZIVA'), _T('Raspoloživa preglednost (manja od H i V)')), (_T('PREGLEDNOST_NEDOVOLJNA'), _T('Dio gdje je preglednost nedovoljna'))):
            if lay == _T('PREGLEDNOST_ZAHTIJEVANA') and not s["Lfix"]: continue
            if lay in (_T('PREGLEDNOST_RASPOLOZIVA'), _T('PREGLEDNOST_NEDOVOLJNA')) and s["D"] is None: continue
            if lay == _T('PREGLEDNOST_HORIZONTALNA') and s["Dh"] is None: continue
            d.line(lay, lx, ly, lx + 12, ly); d.text("TEKST", lx + 15, ly - 0.9, H * 0.9, txt); ly -= 6
        d.text("TEKST", 0, yD0 - 16, H * 0.9, _TF('Razmjera: 1 mm = {0:g} m (stacionaža), {1:g} km/h (brzina), {2:g} m (preglednost). Jedinica crteža: mm.', hs, vs, ds))
        y0 = yV0 + hV + 40
    d.save(path); log(_TF("DXF dijagram: {0}", path))
    return path


def make_vr(P, par, out, outdir, name, log=print):
    """Dijagrami horizontalne i vertikalne preglednosti za računsku brzinu Vr (unesena u programu): potrebna Pz = Lz(Vr, nagib) + dodatak."""
    import os
    from .preglednost import lzn
    par2 = dict(par); par2["_vr"] = True
    o2 = dict(vp={}, zaht=None, ocek={})
    for key, R in out["vp"].items():
        def fix(r):
            vr_ = float(R["A"]["vr"][r["i"]]) if ("vr" in R["A"] and r.get("i") is not None) else float(P.Vr)      # Vr zone na tački
            L = lzn(vr_, r["g"], par) + par["dodatak_L"]
            r2 = dict(r, V=vr_, Lz=L)
            r2["okH"] = bool(r["Dh"] >= L - 1e-6 or r.get("trunc")); r2["okV"] = bool(r["Dv"] >= L - 1e-6 or r.get("trunc")); r2["ok"] = bool(r["D"] >= L - 1e-6 or r.get("trunc"))
            return r2
        av = [fix(r) for r in R["avail"]["rows"]]
        R2 = dict(R); R2["rows"] = [dict(fix(dict(r, Dh=r.get("Dh", 0), Dv=r.get("Dv", 0), D=r.get("Dv", 0))), ) for r in R["rows"]]
        R2["avail"] = dict(rows=av); o2["vp"][key] = R2
        o2["ocek"][key] = dict(rows=av, A=R["A"])
    base = os.path.join(outdir, _TF('Preglednost_dijagram_Vr_{0}', name))
    files = make_png(P, par2, o2, base, log)
    files.append(make_dxf(P, par2, o2, base + ".dxf", log))
    return files


def make(P, par, out, outdir, name, log=print):
    import os
    base = os.path.join(outdir, _TF('Preglednost_dijagram_{0}', name))
    files = make_png(P, par, out, base, log)
    files.append(make_dxf(P, par, out, base + ".dxf", log))
    return files


def make_profil_dxf(P, par, sets, path, log=print, vexag=10.0):
    """Vertikalna preglednost u uzdužnom profilu: niveleta prati osovinu trake; zraka od oka vozača (h_oka iznad nivelete) do predmeta (h_pr iznad nivelete).
    res = {trag: R} sa R['rows'] (i, q, Lz, Dv, trunc) i R['A']. Crtež: X = dužina duž trase [m], Y = kota · vexag [m]."""
    from .dxf import Dxf
    from .preglednost import hpr_at
    from .preglednost_crtez import kmfmt, tname
    d = Dxf()
    for nm, col in (("NIVELETA", 7), ("LINIJA_OKA", 8), ("LINIJA_PREDMETA", 5), ("ZRAKA_V_DOVOLJNO", 3), ("ZRAKA_V_NEDOVOLJNO", 1), ("TEKST", 7), ("MREZA", 9), ("OKVIR", 7)): d.layer(nm, col)
    y0 = 0.0; sets = sets if isinstance(sets, list) else [sets]; step = max(1, int(round(par["korak_crtez"] / max(par["korak_proracun"], 1e-9))))
    for res, title, h_pr in [(s[0], s[1], s[2]) for s in sets]:
      for key, R in res.items():
          A = R["A"]; q = np.asarray(A["q"]); z = np.asarray(A["z"]); rows = R["rows"]
          zmin, zmax = float(z.min()), float(z.max()); base = y0 - zmin * vexag + 60
          d.poly("NIVELETA", [(float(a), float(base + b * vexag)) for a, b in zip(q, z)], width=0.6)
          d.poly("LINIJA_OKA", [(float(a), float(base + (b + par["h_oka"]) * vexag)) for a, b in zip(q, z)])
          hp = np.array([hpr_at(A, par, i) if h_pr is None else float(h_pr) for i in range(len(q))])
          d.poly("LINIJA_PREDMETA", [(float(a), float(base + (b + h) * vexag)) for a, b, h in zip(q, z, hp)])
          nbad = 0
          for r in rows[::step]:
              if r.get("trunc"): continue
              a = r["i"]; need = r["Lz"]; Dv = r["Dv"]; ok = Dv >= need - 1e-6
              b = min(len(q) - 1, int(np.searchsorted(q, q[a] + Dv)))      # najduža moguća zraka na nivelleti
              if b <= a: continue
              d.line("ZRAKA_V_DOVOLJNO" if ok else "ZRAKA_V_NEDOVOLJNO", float(q[a]), float(base + (z[a] + par["h_oka"]) * vexag), float(q[b]), float(base + (z[b] + hp[a]) * vexag))
              nbad += (not ok)
          x1 = float(q[-1]); H = 6.0
          d.text("TEKST", 0, base + (zmax + 12) * vexag, H * 1.6, f"{title} – {tname(key)}")
          for li, tx in enumerate((_TF('Vertikalna preglednost u uzdužnom profilu: oko vozača {0:.2f} m, predmet ', par['h_oka']) + ((_T('h2 = %.2f–%.2f m po Tabeli 29 (zavisi od Vp)') % (hp.min(), hp.max())) if h_pr is None else format(h_pr, '.2f') + ' m') + " iznad nivelete. Razmjera R 1:1000/100.",
                                   _T('Linija oka (siva) i linija predmeta (plava) prate nivelete; zraka ide od linije oka do linije predmeta i prikazuje NAJVEĆU moguću vertikalnu preglednost (do Lmax)'),
                                   _TF('u presjeku, na istim stacionažama kao zrake u situaciji. Zelena = ≥ potrebna Pzp(Vp), crvena = manja od potrebne ({0} zraka).', nbad))):
              d.text("TEKST", 0, base + (zmax + 12) * vexag - 14 - li * 9, H, tx)
          for sx in np.arange(0, x1 + 1e-6, 500):
              d.line("MREZA", float(sx), base + (zmin - 5) * vexag, float(sx), base + (zmax + 5) * vexag)
              j = int(np.searchsorted(q, sx)); j = min(j, len(q) - 1)
              d.text("TEKST", float(sx), base + (zmin - 5) * vexag - 8, H, kmfmt(float(A["s"][j])), rot=90, align="l")
          for zz in np.arange(np.floor(zmin / 10) * 10, zmax + 10, 10):
              d.line("MREZA", 0, float(base + zz * vexag), x1, float(base + zz * vexag)); d.text("TEKST", -4, float(base + zz * vexag) - 2, H, f"{zz:.0f}", align="r")
          y0 = base + (zmax + 40) * vexag
    d.save(path); log(_TF('DXF vertikalna preglednost (profil): {0}', path))
    return path
