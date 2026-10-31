"""Slike za elaborat (generičke – za proizvoljan broj sekcija)."""
from .i18n import _T, _TF
import math, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import logging
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
from matplotlib import font_manager as _fm
_av = {f.name for f in _fm.fontManager.ttflist}
_FONT = next((n for n in ("Arial", "Liberation Sans", "DejaVu Sans") if n in _av), "DejaVu Sans")
plt.rcParams.update({"font.family": _FONT, "font.size": 9, "axes.grid": True, "grid.alpha": 0.3, "figure.dpi": 150})
COLS = ["C0", "C3", "C2", "C1", "C4", "C5", "C6", "C7", "C8", "C9"]


def kap(c):
    out = []
    for s, i in zip(c.S, c.IDX):
        e = c.axis.elems[i]
        k0 = 0 if math.isinf(e["R0"]) else 1 / e["R0"]; k1 = 0 if math.isinf(e["R1"]) else 1 / e["R1"]
        out.append((k0 + (k1 - k0) * (s - e["s0"]) / max(e["L"], 1e-9)) * 1000 if e["L"] > 0 else 0)
    return np.array(out)


def color_of(c, cases):
    return COLS[cases.index(c) % len(COLS)]


def run_label(ch):
    return " + ".join(c.shortname for c in ch)


def make_all(P, sections, cases, axes, fw, bw, has_caps, outdir, log=print):
    os.makedirs(outdir, exist_ok=True)
    F = {}
    for c in cases: c.KAP = kap(c)
    Vr = P.Vr
    s_lo = min(c.SA for c in cases); s_hi = max(c.SB for c in cases)
    chains = [(ch, _T('Smjer rastuće stacionaže')) for ch in (fw,) if ch] + [(ch, _T('Suprotno smjeru stacionaže')) for ch in (bw,) if ch]
    def sbound(ax):
        for sec in sections[1:]:
            ax.axvline(sec["od"], color="k", lw=.6, ls="-.")

    # 1 plan
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    seen = set()
    for c in cases:
        key = (id(c.axis), c.SA, c.SB)
        if key in seen: continue
        seen.add(key); pl = c.axis.plan
        m = (pl[:, 0] >= c.SA - 0.1) & (pl[:, 0] <= c.SB + 0.1)
        ax.plot(pl[m, 1], pl[m, 2], color=color_of(c, cases), lw=1.5, label=f"{c.axis.name}, st. {c.SA:.0f}–{c.SB:.0f}")
        for s0 in np.arange(math.ceil(c.SA / 1000) * 1000, c.SB + 1e-6, 1000):
            i = np.argmin(abs(pl[:, 0] - s0)); ax.plot(pl[i, 1], pl[i, 2], "o", color=color_of(c, cases), ms=3)
            ax.annotate(f"{s0:.0f}", (pl[i, 1], pl[i, 2]), textcoords="offset points", xytext=(4, 4), fontsize=7)
    ax.set_aspect("equal"); ax.ticklabel_format(useOffset=False, style="plain"); plt.setp(ax.get_xticklabels(), rotation=30); ax.set_xlabel("Y [m]"); ax.set_ylabel("X [m]"); ax.legend(fontsize=7); ax.set_title(_T('Situacioni plan osovina (oznake stacionaže)'))
    plt.tight_layout(); p = f"{outdir}/f_plan.png"; plt.savefig(p); plt.close(); F["plan"] = p

    # 2 uzduzni
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 5.2), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    seen = set()
    for c in cases:
        key = (id(c.axis), c.SA, c.SB)
        if key in seen: continue
        seen.add(key)
        a1.plot(c.S, c.Z, color=color_of(c, cases), lw=1.3, label=f"{c.axis.name}, {c.SA:.0f}–{c.SB:.0f}"); a2.plot(c.S, c.G, color=color_of(c, cases), lw=1)
    a1.set_ylabel("Kota nivelete [m n.m.]"); a1.set_title(_T('Uzdužni profil')); a1.legend(fontsize=7); a2.axhline(0, color="k", lw=.6)
    a2.set_ylabel(_T('Nagib [%]')); a2.set_xlabel(_T('Stacionaža [m]'))
    plt.tight_layout(); p = f"{outdir}/f_uzduzni.png"; plt.savefig(p); plt.close(); F["uzduzni"] = p

    # 3 krivina + poprecni
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 4.9), sharex=True)
    seen = set()
    for c in cases:
        key = (id(c.axis), c.SA, c.SB)
        if key in seen: continue
        seen.add(key)
        a1.plot(c.S, c.KAP, color=color_of(c, cases), lw=1, label=f"{c.axis.name}, {c.SA:.0f}–{c.SB:.0f}"); a2.plot(c.S, c.CL, color=color_of(c, cases), lw=1)
    a1.axhline(0, color="k", lw=.6); a1.set_ylabel(_T('Krivina 1000/R [1/km]')); a1.set_title(_T('Dijagram krivine (+ desno, − lijevo) i poprečnog nagiba lijeve strane kolovoza')); a1.legend(ncol=3, fontsize=7)
    a2.axhline(0, color="k", lw=.6); a2.set_ylabel(_T('Poprečni nagib lijeve\nstrane [%]')); a2.set_xlabel(_T('Stacionaža [m]'))
    plt.tight_layout(); p = f"{outdir}/f_krivina.png"; plt.savefig(p); plt.close(); F['krivina'] = p

    # 4 putnicko
    n = len(chains)
    fig, axs = plt.subplots(n, 1, figsize=(7.2, 3.3 * n + 0.6), sharex=True, squeeze=False); axs = axs[:, 0]
    lo = max(40, min(c.V.min() for c in cases) - 8)

    for ax, (ch, lab) in zip(axs, chains):
        for j, c in enumerate(ch):
            ax.plot(c.S, c.T, "--", color="grey", lw=1, label=_T('Ciljna brzina T') if j == 0 else None)
            ax.plot(c.S, c.V, color=color_of(c, cases), lw=1.8, label=_TF('Rezultirajući profil Vp – {0}', c.shortname))
        sbound(ax)
        for j, c in enumerate(ch): ax.plot(c.S, c.VRS, color="C3", lw=1, ls=":", drawstyle="steps-post")
        ax.text(s_lo + 20, Vr + 0.4, f"Vr = {Vr:.0f} km/h", color="C3", fontsize=8)
        ax.set_ylim(lo, max(c.VMX.max() for c in cases) + 5); ax.set_ylabel(_T('Brzina [km/h]')); ax.set_title(f"{lab} ({run_label(ch)})", fontsize=9); ax.legend(loc="lower left", fontsize=7, ncol=2)
    axs[-1].set_xlabel(_T('Stacionaža [m]')); plt.tight_layout(); p = f"{outdir}/f_putnicko.png"; plt.savefig(p); plt.close(); F["putnicko"] = p

    # 5 teska
    fig, axs = plt.subplots(n, 1, figsize=(7.2, 3.3 * n + 0.8), sharex=True, squeeze=False); axs = axs[:, 0]
    allv = np.concatenate([t["v"] for c in cases for t in c.trk]); 
    for ax, (ch, lab) in zip(axs, chains):
        for j, c in enumerate(ch):
            ax.plot(c.S, c.V, color="grey", lw=1, label=_T('Putničko') if j == 0 else None)
            for q, t in enumerate(c.trk):
                ax.plot(c.S, t["v"], color=color_of(c, cases), ls=["-", "--", ":", "-."][q % 4], lw=1.6, label=f"{P.vozila[q]['kratko']} – {c.shortname}")
        sbound(ax); ax.set_ylabel(_T('Brzina [km/h]')); ax.set_title(f"{lab} ({run_label(ch)})", fontsize=9); ax.legend(loc="lower left", fontsize=7, ncol=2)
        ax.set_ylim(max(0, allv.min() - 8), max(c.VMX.max() for c in cases) + 5)
    axs[-1].set_xlabel(_T('Stacionaža [m]')); plt.tight_layout(); p = f"{outdir}/f_teska.png"; plt.savefig(p); plt.close(); F["teska"] = p

    # 6 kumulativno
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.5))
    for ci, (ch, lab) in enumerate(chains):
        for q, v in enumerate(P.vozila):
            dist = []; tm = []; fu = []; od = ot = of = 0
            for c in ch:
                r = c.trk[q]; S = c.S; d = (S - S[0]) if c.sg == 1 else (S[-1] - S); o = np.argsort(d)
                dist += list(d[o] + od); tm += list(r["time"][o] + ot); fu += list(r["fuel"][o] + of)
                od += abs(S[-1] - S[0]); ot += r["T"]; of += r["Fu"]
            l = f"{v['kratko']} – {_T('smjer stacionaže') if ci == 0 and ch[0].sg == 1 else 'suprotno'}"
            col = ["C0", "C3"][0 if ch[0].sg == 1 else 1]; ls = ["-", "--", ":", "-."][q % 4]
            a1.plot(dist, np.array(tm) / 60, color=col, ls=ls, label=l); a2.plot(dist, fu, color=col, ls=ls, label=l)
    a1.set_xlabel(_T('Pređeni put [m]')); a1.set_ylabel("Vrijeme [min]"); a1.legend(fontsize=6); a2.set_xlabel(_T('Pređeni put [m]')); a2.set_ylabel(_T('Potrošnja goriva [l]')); a2.legend(fontsize=6)
    fig.suptitle(_TF('Kumulativno vrijeme putovanja i potrošnja goriva teških vozila (st. {0:.0f} – {1:.0f})', s_lo, s_hi)); plt.tight_layout()
    p = f"{outdir}/f_vrijeme_gorivo.png"; plt.savefig(p); plt.close(); F["vrijeme"] = p

    # grafički prilozi – trake
    seg = 1330.0; nseg = max(1, math.ceil((s_hi - s_lo) / seg)); seg = (s_hi - s_lo) / nseg
    F["strips"] = []
    for k in range(nseg):
        a = s_lo + k * seg; b = s_lo + (k + 1) * seg
        panels = [(_T('Krivina'), None)] + [("Kota", None)]
        chs = [(ch, lab) for ch, lab in chains if any(c.SB > a and c.SA < b for c in ch)]
        fig, axs = plt.subplots(2 + len(chs), 1, figsize=(7.2, 4.0 + 2.4 * len(chs)), sharex=True,
                                gridspec_kw={"height_ratios": [1, 1.3] + [1.8] * len(chs)}, squeeze=False); axs = axs[:, 0]
        seen = set()
        for c in cases:
            if not (c.SB > a and c.SA < b): continue
            key = (id(c.axis), c.SA, c.SB)
            if key in seen: continue
            seen.add(key); m = (c.S >= a) & (c.S <= b)
            axs[0].plot(c.S[m], c.KAP[m], color=color_of(c, cases), label=f"{c.axis.name}"); axs[1].plot(c.S[m], c.Z[m], color=color_of(c, cases))
        axs[0].axhline(0, color="k", lw=.6); axs[0].set_ylabel("1000/R [1/km]"); axs[0].legend(ncol=3, fontsize=7, loc="upper right")
        axs[0].set_title(_TF('Grafički prilog {0}: st. {1:.0f} – {2:.0f} (plan, uzdužni profil, brzine)', k + 1, a, b)); axs[1].set_ylabel("Kota [m]")
        for ax, (ch, lab) in zip(axs[2:], chs):
            first = True
            for c in ch:
                if not (c.SB > a and c.SA < b): continue
                m = (c.S >= a) & (c.S <= b)
                ax.plot(c.S[m], c.V[m], "k", lw=1.6, label=_T('Putničko') if first else None)
                for q, t in enumerate(c.trk): ax.plot(c.S[m], t["v"][m], color=["C0", "C2", "C4", "C5"][q % 4], ls=["-", "--", ":", "-."][q % 4], label=P.vozila[q]["kratko"] if first else None)
                ax.plot(c.S[m], c.VRS[m], color="C3", ls=":", lw=1, drawstyle="steps-post")
                first = False
            ax.axhline(Vr, color="C3", ls=":", lw=0.6, alpha=0.0); ax.set_ylim(max(0, allv.min() - 8), max(c.VMX.max() for c in cases) + 5); ax.set_ylabel(_T('Brzina [km/h]')); ax.set_title(lab, fontsize=8); ax.legend(ncol=4, fontsize=7, loc="lower center")
        axs[-1].set_xlabel(_T('Stacionaža [m]')); axs[-1].set_xlim(a, b)
        t0 = int(math.ceil(a / 100) * 100); axs[-1].set_xticks(range(t0, int(b) + 1, 100)); plt.setp(axs[-1].get_xticklabels(), rotation=60, fontsize=7)
        plt.tight_layout(); p = f"{outdir}/s{k + 1}.png"; plt.savefig(p); plt.close(); F["strips"].append(p)
    log(_TF('Slike: {0}', len(F['strips']) + 6 + 0))
    return F
