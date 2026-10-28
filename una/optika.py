"""Elaborat 4 – optičke analize: zahtijevana, raspoloživa (rezultujuća) i preticajna preglednost, sadržaj grafičkih priloga."""
import math, os, re, shutil, tempfile
import numpy as np
from . import preglednost as pg
from .texts import SYM

APP_NAME = "UNA - ROAD ENGINEERING ANALYSIS"
fm = lambda x, n=0: f"{float(x):.{n}f}".replace(".", ",")
TRAG = {"F": "smjer rastuće stacionaže", "B": "smjer opadajuće stacionaže"}

OPT_DEF = dict(ukljuci=False, Pp_faktor=6.0, Pp_po="Vr", Pp_tablica=None, h_predmeta_preticanje=None, min_proc=25.0, grupa="A", tip_puta="auto",
               korak_tabela=50.0, norma="BiH Smjernice (jpcfbih.ba, 4.2.5, Tabela 8) i Pravilnik RS (Sl. glasnik RS 50/2011, Prilog 1, tč. 6.1.3 i Prilog 2)")


PP_BIH = {"50": 330, "60": 380, "70": 450, "80": 520, "90": 600, "100": 680}        # BiH Smjernice, Tabela 30
PP_RS = {"40": 260, "50": 320, "60": 370, "70": 430, "80": 480, "90": 540, "100": 600}   # Pravilnik RS, Prilog 2, tabela 4-02
MIN_RS = 20.0                                                                          # Pravilnik RS, Prilog 2, tabela 4-03 (Vr 40–100 km/h)


def opt_par(cfg):
    o = dict(OPT_DEF); o.update({k: v for k, v in (cfg.get("optika") or {}).items() if k in OPT_DEF})
    if "min_proc" not in (cfg.get("optika") or {}): o["min_proc"] = 25.0 if str(o.get("grupa", "A")).upper() == "A" else 15.0
    t_ = str(o.get("tip_puta", "auto")).lower(); o["tip_puta"] = "razdvojeni" if t_.startswith("razd") else ("dvosmjerni" if t_.startswith("dvo") else "auto")
    if o.get("h_predmeta_preticanje") in ("", 0, "0"): o["h_predmeta_preticanje"] = None
    for k in ("Pp_faktor", "min_proc", "korak_tabela") + (("h_predmeta_preticanje",) if o.get("h_predmeta_preticanje") is not None else ()): o[k] = float(str(o[k]).replace(",", "."))
    if o.get("Pp_tablica"):
        o["Pp_tablica"] = sorted((float(k), float(v)) for k, v in dict(o["Pp_tablica"]).items())
    else: o["Pp_tablica"] = None
    return o


def Pp_of(V, o):
    """Potrebna preticajna preglednost Pp [m] za brzinu V [km/h]: tablica (interpolacija) ili Pp = faktor·V."""
    t = o["Pp_tablica"]
    if t: return float(np.interp(V, [a for a, _ in t], [b for _, b in t]))
    return o["Pp_faktor"] * V


def AV(out, k):
    return (out.get("zaht") or {}).get(k) or out["vp"][k]


def xd_rows(out, k, dv_min=2.0):
    """Zone usporenja u profilu Vp (u smjeru vožnje) i dužina puta usporenja Xd = 0,1·Vsr·ΔV (slika 3-09 Priloga 2).
    Pr (Pzp) ≥ Xd: preglednost na početku usporenja (tačka gdje Vp počinje opadati) mora biti najmanje jednaka putu usporenja."""
    rows = sorted(AV(out, k)["avail"]["rows"], key=lambda r: r["s"])
    if k.startswith("B"): rows = rows[::-1]                      # smjer vožnje suprotan rastućoj stacionaži
    res = []; i = 0; n = len(rows)
    while i < n - 1:
        if rows[i + 1]["V"] < rows[i]["V"] - 1e-6:
            j = i
            while j < n - 1 and rows[j + 1]["V"] < rows[j]["V"] - 1e-6: j += 1
            V1, V2 = rows[i]["V"], rows[j]["V"]
            if V1 - V2 >= dv_min:
                Xd = 0.1 * (V1 + V2) / 2 * (V1 - V2); r0 = rows[i]
                res.append(dict(s0=r0["s"], s1=rows[j]["s"], V1=V1, V2=V2, Xd=Xd, Pzp=r0["Lz"], Pr=r0["D"], trunc=bool(r0.get("trunc")),
                                ok_pzp=r0["Lz"] >= Xd, ok_pr=r0["D"] >= Xd))
            i = j
        else: i += 1
    return res


def run_pp(P, par, out, o, log=print):
    """Preticajna preglednost po tragovima: oko 1,0 m, predmet 1,3 m; ostvareni % = dio dužine gdje je raspoloživa preglednost ≥ Pp."""
    par2 = dict(par); par2["Lmax"] = max(Pp_of(P.Vr, o), Pp_of(max(float(np.max(R["A"]["v"])) for R in out["vp"].values()), o)); 
    if o["h_predmeta_preticanje"] is not None: par2["h_prepreke"] = par2["h_pr"] = o["h_predmeta_preticanje"]; par2["h_auto"] = False
    res = {}
    for key, R in out["vp"].items():
        if R["side"] != "L": continue                      # preticanje se vrši iz lijeve (preticajne) trake
        A = R["A"]
        if o["Pp_po"] == "Vp": Lf = lambda A_, p_, a: Pp_of(A_["v"][a], o)
        else:
            Pv = Pp_of(P.Vr, o); Lf = lambda A_, p_, a, Pv=Pv: Pv
        E = pg.expected(A, par2, Lf)
        rows = E["rows"]; use = [r for r in rows if not r["trunc"]] or rows
        okn = sum(1 for r in use if r["ok"]); pr = 100.0 * okn / len(use)
        zones = pg.intervals(rows, key="ok", bad=False, dkey="D")
        st = float(par["korak_proracun"])
        zl = [(z["s1"] - z["s0"] + st) for z in zones]
        E["A"] = A; E["chain"] = R["chain"]; E["tag"] = R["tag"]; E["side"] = R["side"]; E["key"] = key
        E["deficits"] = pg.intervals(rows, bad=True, dkey="D"); E["defH"] = pg.intervals(rows, key="okH", bad=True, dkey="Dh"); E["defV"] = pg.intervals(rows, key="okV", bad=True, dkey="Dv")
        res[key] = dict(E=E, rows=rows, pct=pr, zones=zones, zlen=zl, Pp=Pf(rows), ok=pr >= o["min_proc"], tag=R["tag"], side=R["side"])
        log(f"Preticajna preglednost {key}: Pp = {res[key]['Pp']:.0f} m, ostvareno {pr:.1f} % (min. {o['min_proc']:.0f} %)")
    return res


def Pf(rows):
    v = [r["Lz"] for r in rows]; return float(max(v)) if v else 0.0


def make_png(P, par, out, pp, o, outdir, name, log=print):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    files = []
    for key, R in out["vp"].items():
        va = AV(out, key)["avail"]["rows"]; ra = pp[key]["rows"] if key in pp else None
        s1 = np.array([r["s"] for r in va]); o1 = np.argsort(s1); s1 = s1[o1]
        V = np.array([r["V"] for r in va])[o1]; Lz = np.array([r["Lz"] for r in va])[o1]
        tr = np.array([r["trunc"] for r in va])[o1]
        D = np.where(tr, np.nan, np.array([r["D"] for r in va])[o1])
        if ra is not None:
            s2 = np.array([r["s"] for r in ra]); o2 = np.argsort(s2); s2 = s2[o2]
            tr2 = np.array([r["trunc"] for r in ra])[o2]; D2 = np.where(tr2, np.nan, np.array([r["D"] for r in ra])[o2]); Lp = np.array([r["Lz"] for r in ra])[o2]
            ok2 = np.array([r["ok"] for r in ra])[o2]
        nrow = 3 if ra is not None else 2
        fig, axs = plt.subplots(nrow, 1, figsize=(15, 10.5 if nrow == 3 else 7.5), sharex=True, gridspec_kw=dict(height_ratios=[0.8, 1.1, 1.1][:nrow], hspace=0.1))
        a1, a2 = axs[0], axs[1]; a3 = axs[2] if nrow == 3 else None
        a1.plot(s1, V, color="#1f4e9c", lw=1.4, label="projektna brzina Vp (Elaborat 3)"); a1.axhline(P.Vr, color="k", ls="--", lw=0.8, label=f"Vr = {P.Vr:g} km/h")
        a1.set_ylabel("V [km/h]"); a1.legend(loc="lower right", fontsize=8); a1.grid(alpha=.3)
        a2.plot(s1, Lz, color="#2a8a3a", lw=1.2, label="zahtijevana preglednost Pzp = f(Vp, nagib)"); a2.plot(s1, D, color="#c0392b", lw=1.2, label="raspoloživa preglednost Pr")
        a2.fill_between(s1, D, Lz, where=np.nan_to_num(D, nan=1e9) < Lz, color="#c0392b", alpha=.25, label="nedovoljno (Pr < Pzp)")
        a2.set_ylabel("preglednost [m]"); a2.legend(loc="upper right", fontsize=8); a2.grid(alpha=.3)
        if a3 is not None:
            a3.plot(s2, Lp, color="#7d3c98", lw=1.2, label=f"potrebna preticajna Pp = {Lp.max():.0f} m"); a3.plot(s2, D2, color="#d68910", lw=1.2, label="raspoloživa preglednost za preticanje")
            a3.fill_between(s2, 0, np.nanmax(D2) if np.isfinite(D2).any() else 1, where=ok2, color="#27ae60", alpha=.18, label=f"preticanje moguće ({pp[key]['pct']:.1f} %, min. {o['min_proc']:.0f} %)")
            a3.set_ylabel("preglednost [m]"); a3.set_xlabel("stacionaža [m]"); a3.legend(loc="upper right", fontsize=8); a3.grid(alpha=.3)
        else: a2.set_xlabel("stacionaža [m]")
        fig.suptitle(f"Dijagram raspoložive preglednosti – {TRAG[R['tag']]}, {pg.SIDE_NAME[R['side']]}", fontsize=11)
        base = os.path.join(outdir, f"Optika_dijagram_{name}_{key}")
        fig.savefig(base + ".png", dpi=130, bbox_inches="tight"); fig.savefig(base + ".pdf", bbox_inches="tight"); plt.close(fig)
        files += [base + ".png", base + ".pdf"]
    return files


def write_xlsx(path, P, par, out, pp, o):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook(); ws = wb.active; ws.title = "Sažetak"
    ws.append([f"{APP_NAME} – optičke analize (preticanje)"]); ws["A1"].font = Font(bold=True)
    ws.append(["Pp = faktor · V" if not o["Pp_tablica"] else "Pp iz tablice", o["Pp_faktor"], "Pp_po", o["Pp_po"], "min % Pp", o["min_proc"], "predmet [m]", o["h_predmeta_preticanje"] if o["h_predmeta_preticanje"] is not None else "Tabela 29"])
    ws.append([]); ws.append(["Trag", "Pp [m]", "Ostvareno % Pp", "Minimum %", "Zadovoljava", "Broj zona", "Najduža zona [m]"])
    for k, r in pp.items(): ws.append([k, r["Pp"], round(r["pct"], 2), o["min_proc"], "DA" if r["ok"] else "NE", len(r["zones"]), max(r["zlen"]) if r["zlen"] else 0])
    for k, r in pp.items():
        w = wb.create_sheet(f"Pp_{k}"); w.append(["Stacionaža s", "V [km/h]", "Nagib [%]", "Zahtijevana Pzp (Vp) [m]", "Raspoloživa Pr [m]", "Potrebna Pp [m]", "Raspoloživa za preticanje [m]", "Dh", "Dv", "Preticanje moguće"])
        va = {x["i"]: x for x in AV(out, k)["avail"]["rows"]}
        for x in r["rows"]:
            v = va.get(x["i"], {})
            w.append([round(x["s"], 2), round(x["V"], 1), round(x["g"], 2), round(v.get("Lz", 0), 1), round(v.get("D", 0), 1), round(x["Lz"], 1), round(x["D"], 1), round(x["Dh"], 1), round(x["Dv"], 1), "DA" if x["ok"] else "NE"])
    wb.save(path)


def attachments(outdir, name, files):
    """Sadržaj grafičkih priloga: popis stvarno napravljenih datoteka."""
    L = []; n = 0
    def add(fn, naziv, mj="R 1:1000"):
        nonlocal n
        if fn and os.path.exists(fn): n += 1; L.append((n, naziv, mj, os.path.splitext(fn)[1][1:].upper(), os.path.basename(fn)))
    for f in files:
        b = os.path.basename(f)
        if b.startswith("Preglednost_Vr_") and f.endswith(".dxf"): add(f, "Situacija – zrake preglednosti za računsku brzinu Vr (horizontalna i vertikalna preglednost)")
        elif b.startswith("Preglednost_Vp_") and f.endswith(".dxf"): add(f, "Situacija – zrake zahtijevane preglednosti Pzp na osnovu projektne brzine Vp i nagiba, horizontalna i vertikalna preglednost")
        elif b.startswith("Preglednost_zahtijevana_") and f.endswith(".dxf"): add(f, "Situacija – zrake zahtijevane preglednosti i zone nedovoljne preglednosti")
        elif b.startswith("Preglednost_ocekivana_") and f.endswith(".dxf"): add(f, "Situacija – očekivana (raspoloživa) preglednost, linija prepreke i dodirne tačke")
        elif b.startswith("Preglednost_preticanje_") and f.endswith(".dxf"): add(f, "Situacija – preglednost pri preticanju: zrake Pp iz lijeve (preticajne) trake, oba smjera")
        elif b.startswith("Preglednost_vertikalna_") and f.endswith(".dxf"): add(f, "Vertikalna preglednost u uzdužnom profilu – " + ("smjer stacionaže" if "_F_" in b else "suprotno smjeru stacionaže") + ": niveleta, linija oka, linija predmeta i najduža moguća zraka", "R 1:1000/100")
        elif b.startswith("Preglednost_dijagram_Vr_") and f.endswith(".dxf"): add(f, "Dijagram horizontalne i vertikalne preglednosti za računsku brzinu Vr (svi tragovi)", "po stacionaži")
        elif b.startswith("Preglednost_dijagram_Vr_") and f.endswith(".pdf"): add(f, "Dijagram horizontalne i vertikalne preglednosti za računsku brzinu Vr, " + _trag(b), "po stacionaži")
        elif b.startswith("Preglednost_dijagram_") and f.endswith(".dxf"): add(f, "Dijagram brzina – preglednost (svi tragovi)", "po stacionaži")
        elif b.startswith("Preglednost_dijagram_") and f.endswith(".pdf"): add(f, "Dijagram brzina – preglednost, " + _trag(b), "po stacionaži")
        elif b.startswith("Optika_dijagram_") and f.endswith(".pdf"): add(f, "Dijagram raspoložive i preticajne preglednosti, " + _trag(b), "po stacionaži")
    return L


def _trag(b):
    m = re.search(r"_([FB])_([DL])\.", b)
    return f"{TRAG[m.group(1)]}, {pg.SIDE_NAME[m.group(2)]}" if m else ""


def build_md(P, par, out, pp, o, cfg, figs, att, name, template_mode=False):
    md = []; A = md.append; tn = [0]; fn = [0]
    def seg(c):
        if template_mode: md.append(f"ZZSEG{c}\n")
    def tab(t): tn[0] += 1; return f"**Tabela {tn[0]} – {t}**\n\n"
    def table(head, rows):
        s = "| " + " | ".join(head) + " |\n| " + " | ".join([":---:"] * len(head)) + " |\n"
        for r in rows: s += "| " + " | ".join(str(x) for x in r) + " |\n"
        return s + "\n"
    proj = cfg.get("projekat", "Dionica")
    if not template_mode: A(f"---\ntitle: \"ELABORAT OPTIČKIH ANALIZA\"\nsubtitle: \"{proj}\"\n---\n")
    A("# Uvod\n")
    A("Optičke analize sprovedene su za usvojeno rješenje trase. Vozač svoje manevre podešava prema sadržaju u vidnom polju, pa je za svaku traku i svaki smjer vožnje numerički modelom trase (plan, niveleta, poprečni profil, prepreke uz kolovoz) određena raspoloživa preglednost. "
      f"Proračun je urađen programom {APP_NAME}; ulazna projektna brzina Vp preuzeta je iz Elaborata 3 (vozno-dinamičke analize, rezultirajući profil projektne brzine).\n")
    A(f"Oko vozača je {fm(par['h_oka'],2)} m iznad nivelete, a visina predmeta {('h2 prema Tabeli 29 Smjernica (0–0,15 m, zavisi od brzine Vp)' if par['h_auto'] else fm(par['h_prepreke'],2) + ' m')} (za zaustavnu preglednost i preticanje{'; za preticanje zadato ' + fm(o['h_predmeta_preticanje'],2) + ' m' if o['h_predmeta_preticanje'] is not None else ''}). Zrake preglednosti polaze od ose oka vozača, na rastojanju od ose kolovoza prema usvojenom ofsetu.\n")
    A("# Zahtijevana preglednost, Pzp = f(Vp)\n")
    RS = False   # Pzp/Pz uvijek po Crtežu 52 BiH Smjernica
    A("Da bi se ostvarila brzina veća od računske, na svakom mjestu trase mora biti obezbijeđena preglednost koja zavisi od projektne brzine Vp i stvarnog podužnog nagiba (zahtijevana preglednost Pzp). Mora biti ispunjen uslov **Pzp ≥ Pz**, gdje je Pz zaustavna preglednost u funkciji računske brzine deonice. "
      + ("Pzp se određuje u svakom presjeku trase na osnovu projektne brzine Vp, interpolacijom tabele 4-01 Pravilnika (Prilog 2); dijagram Pzp = f(Vp, iN) (slika 4-01) nije ugrađen, pa se uticaj nagiba ne uzima u obzir. " if RS else f"Pzp se određuje u svakom presjeku trase na osnovu projektne brzine Vp i podužnog nagiba u smjeru vožnje, očitavanjem iz dijagrama Crtež 52 (skraćena zaustavna preglednost, fT50 %). ")
      + f"Dodatak na očitanu vrijednost: {fm(par['dodatak_L'],0)} m. Pzp se primjenjuje pri projektovanju saobraćajno-tehničke opreme, uređenju putnog pojasa i za provjeru elemenata plana i profila.\n")
    A(tab("Zahtijevana preglednost Pzp u funkciji projektne brzine Vp i podužnog nagiba"))
    gs = [-8, -4, 0, 4, 8]
    A(table(["Vp [km/h]"] + [f"i = {g:+d} %" for g in gs], [[fm(v)] + [fm(pg.lzn(v, g, par) + par["dodatak_L"]) for g in gs] for v in range(40, int(max(P.Vr, 100)) + 21, 10)]))
    if RS:
        A(tab("Zaustavna preglednost Pz u funkciji računske brzine deonice (Pravilnik, tabela 4-01)"))
        A(table(["Vri [km/h]"] + [str(v) for v in pg.PZ_RS_V], [["Pz [m]"] + [str(v) for v in pg.PZ_RS]]))
    A(f"Za računsku brzinu Vr = {fm(P.Vr)} km/h zaustavna preglednost je Pz = {fm(pg.lzn(P.Vr, 0, par) + par['dodatak_L'])} m" + (" (Pravilnik, tabela 4-01)." if RS else " (Crtež 52, nagib 0 %).") + "\n")
    A("# Raspoloživa i preticajna preglednost\n")
    A("## Raspoloživa preglednost Pr\n")
    A("Raspoloživa preglednost Pr određena je kao najduža tetiva od oka vozača koju dozvoljavaju prepreka uz kolovoz (horizontalna preglednost) i niveleta (vertikalna preglednost). Rezultati su dati po tragovima, za oba smjera vožnje, a kompletan proračun je u prilogu (Excel i Tabela 4).\n")
    rows = []
    for k, R in out["vp"].items():
        Z = AV(out, k); av = Z["avail"]; rr = [r for r in av["rows"] if not r["trunc"]] or av["rows"]
        vs = [r["V"] for r in R["rows"]]
        nb = sum(1 for r in rr if not r["ok"]); lenb = nb * float(par["korak_proracun"])
        rows.append([f"{TRAG[R['tag']]}, {pg.SIDE_NAME[R['side']]}", f"{min(vs):.0f}–{max(vs):.0f}", f"{min(r['Lz'] for r in rr):.0f}–{max(r['Lz'] for r in rr):.0f}",
                     f"{min(r['D'] for r in rr):.0f}–{max(r['D'] for r in rr):.0f}", len(Z["defV"]), len(Z["defH"]) if R["A"]["has_ob"] else "–", f"{lenb:.0f}", "DA" if nb == 0 else "NE"])
    A(tab("Sažetak raspoložive preglednosti u odnosu na zahtijevanu (projektna brzina Vp)"))
    A(table(["Trag", "Vp [km/h]", "Pzp [m]", "Pr [m]", "Vert. nedov. (br. zona)", "Hor. nedov. (br. zona)", "Dužina Pr<Pzp [m]", "Pr ≥ Pzp"], rows))
    A("## Uslov Pr (Pzp) ≥ X~d~ – put usporenja\n")
    A("Prema tački 3.4.2.1 Priloga 2 Pravilnika jedan od uslova bezbjednosti vožnje je da dužina raspoložive preglednosti Pr, odnosno zahtijevane preglednosti Pzp, bude veća ili jednaka dužini puta usporenja X~d~, tj. **Pr (Pzp) ≥ X~d~**. Dužina puta usporenja pri prelazu sa brzine V~1~ na V~2~ (slika 3-09, a = d = 0,8 m/s²) iznosi X~d~ = 0,1·V~sr~·ΔV, gdje je V~sr~ = (V~1~ + V~2~)/2, ΔV = V~1~ − V~2~ [km/h], X~d~ u [m]. Provjera se vrši na početku svake zone usporenja rezultirajućeg profila V~p~ (u smjeru vožnje), tj. na mjestu na kojem V~p~ počinje opadati.\n")
    xr = []; xbad = 0
    for k in out["vp"]:
        for z in xd_rows(out, k):
            xr.append([k, f"{z['s0']:.0f}–{z['s1']:.0f}", f"{z['V1']:.0f} → {z['V2']:.0f}", f"{z['Xd']:.0f}", f"{z['Pzp']:.0f}", ("≥ " if z["trunc"] else "") + f"{z['Pr']:.0f}", "DA" if z["ok_pzp"] else "NE", "DA" if z["ok_pr"] else "NE"])
            xbad += (not z["ok_pzp"]) + (not z["ok_pr"])
    if xr:
        A(tab("Provjera uslova Pr (Pzp) ≥ X~d~ na zonama usporenja"))
        A(table(["Trag", "Zona usporenja od–do [m]", "V~1~ → V~2~ [km/h]", "X~d~ [m]", "Pzp [m]", "Pr [m]", "Pzp ≥ X~d~", "Pr ≥ X~d~"], xr))
        A("Uslov je ispunjen na svim zonama usporenja.\n" if not xbad else f"Uslov nije ispunjen na {xbad} provjera; na tim mjestima treba povećati raspoloživu preglednost ili ublažiti prelaz brzine (npr. većim radijusom ili dužim elementom ispred krivine).\n")
    else:
        A("U profilu V~p~ nema zona usporenja (V~p~ se ne smanjuje za više od 2 km/h), pa uslov Pr (Pzp) ≥ X~d~ nije potrebno provjeravati.\n")
    seg("B")
    for k, R in out["vp"].items():
        if k in figs:
            fn[0] += 1; A(f"![]({os.path.basename(figs[k])}){{width=16cm}}\n\n*Slika {fn[0]} – Dijagram brzine, zahtijevane, raspoložive i preticajne preglednosti – {TRAG[R['tag']]}, {pg.SIDE_NAME[R['side']]}*\n")
    seg("C")
    A("Mjesta na kojima raspoloživa preglednost nije dovoljna:\n")
    dr = []
    for k, R in out["vp"].items():
        Z = AV(out, k)
        for lab, lst in (("vertikalna", Z["defV"]), ("horizontalna", Z["defH"] if R["A"]["has_ob"] else [])):
            for z in lst: dr.append([k, lab, f"{z['s0']:.0f}–{z['s1']:.0f}", f"{z['need']:.0f}", f"{z['dmin']:.0f}"])
    A(tab("Zone nedovoljne preglednosti"))
    A(table(["Trag", "Vrsta", "Stacionaža od–do [m]", "Potrebno [m]", "Min. raspoloživo [m]"], dr) if dr else "Nedovoljna preglednost nije utvrđena ni na jednom mjestu.\n")
    A("## Preticajna preglednost Pp\n")
    if o["tip_puta"] == "razdvojeni":
        A("Preticajna preglednost Pp i ostvareni procenat %Pp **nisu računati**, jer se na ovoj saobraćajnici ne primjenjuju. Dionica ima fizički razdvojene kolovoze, a svaki kolovoz ima voznu i preticajnu traku, pa preticanje ne zalazi u traku suprotnog toka. " +
          ("Tabela 4-02 i 4-03 Priloga 2 Pravilnika (Pp = 260–600 m, minimalni %Pp = 20 %) odnose se na dvotračne puteve; na dvotračnim putevima računska brzina se može postići samo uz dovoljno preticajne preglednosti (tačka 3.3.2). " if par["norma"] == "RS" else "Tačka 4.2.5.3 BiH Smjernica (Tabela 30 i minimalni procenat od > 25 % za tehničku grupu A) odnosi se na dvosmjerne puteve sa jednim kolovozom; ") + "i međunarodna praksa (npr. AASHTO/Caltrans HDM, tačka 201.2) preglednost pri preticanju razmatra samo na dvotračnim putevima, a višetračne dionice projektuje prema zaustavnoj preglednosti. "
          "Za ovu saobraćajnicu mjerodavna je zahtijevana (zaustavna) preglednost Pzp iz poglavlja 2, a njeno ispunjenje u oba smjera vožnje prikazano je dijagramima raspoložive preglednosti Pr i tabelama u prethodnom poglavlju.\n")
    else:
        if par["norma"] == "RS":
            A("### Preticajna preglednost prema Pravilniku (Prilog 2, tačke 4.3 i 4.4)\n")
            A("Potrebne dužine preticajne preglednosti date su u tabeli 4-02 (za dvotračne puteve), a minimalni procenat u tabeli 4-03 (po smjeru vožnje).\n")
            A(table(["Vri [km/h]"] + [str(int(k)) for k in sorted(map(int, PP_RS))], [["Pp [m]"] + [str(PP_RS[str(k)]) for k in sorted(map(int, PP_RS))]]))
            A(table(["Vr [km/h]", "40–100", "110, 120"], [["min %Pp", "20", "–"]]))
            A(f"Ostvareni procenat preticajne preglednosti određuje se po smjeru vožnje izrazom **%Pp = Σlpi / L · 100**, gdje je lpi dužina na kojoj je raspoloživa preglednost Pr ≥ Pp, a L ukupna dužina trase. Raspoloživa preglednost Pr određuje se sa mjesta oka vozača ho = {fm(par['h_oka'],2)} m. Zrake se crtaju **iz lijeve (preticajne) trake**, i za razdvojene osovine i za centralnu osovinu. Potrebna dužina Pp = {fm(Pp_of(P.Vr, o))} m za Vr = {fm(P.Vr)} km/h (tabela 4-02); minimum {fm(o['min_proc'],0)} % (tabela 4-03).\n")
        else:
            A("### Obezbjeđenje preglednosti pri preticanju (BiH Smjernice, tačka 4.2.5.3)\n")
            A("> Na dvosmjernim putevima sa jednim kolovozom iz tehničke grupe A, potrebno je obezbijediti preglednost pri preticanju na dužini kojom se postiže predviđena dovoljna propusnost puta pri određenoj brzini putovanja. Ukoliko saobraćajnim dimenzionisanjem nije određena potrebna dužina dionica za obezbjeđenje preglednosti pri preticanju, najmanjom dužinom smatra se: > 25 % dužine puta za puteve tehničke grupe A i > 15 % dužine puta za puteve tehničke grupe B i C. U posebno složenim uslovima reljefa moguće je izostaviti navedene najmanje dužine, što mora biti određeno projektnim zadatkom. Na dužim usponima sa dodatnom trakom za spora vozila preticanje nije dozvoljeno pri kretanju nizbrdo.\n")
            A("Minimalne daljine preglednosti pri preticanju (Tabela 30 Smjernica):\n")
            A(table(["V [km/h]", "40", "50", "60", "70", "80", "90", "100"], [["min Pp [m]", "–", "330", "380", "450", "520", "600", "680"]]))
            A(f"Zrake preglednosti pri preticanju crtaju se **iz lijeve (preticajne) trake**, i za razdvojene kolovoze (osovine) i za centralnu osovinu: oko vozača je {fm(par['h_oka'],2)} m iznad nivelete, visina predmeta {(fm(o['h_predmeta_preticanje'],2) + ' m (zadata)') if o['h_predmeta_preticanje'] is not None else ('h2 po Tabeli 29 (zavisi od Vp)' if par['h_auto'] else fm(par['h_prepreke'],2) + ' m')}, a zraka polazi od ose oka vozača u lijevoj traci. "
              f"Potrebna dužina Pp očitana je iz Tabele 30 za brzinu {'Vr' if o['Pp_po']=='Vr' else 'Vp'} (Vr = {fm(P.Vr)} km/h → Pp = {fm(Pp_of(P.Vr, o))} m); ostvareni %Pp je udio dužine trase na kojoj je raspoloživa preglednost ≥ Pp. Minimalni procenat za tehničku grupu {o['grupa']} iznosi {fm(o['min_proc'],0)} %. "
              "Za razdvojene kolovoze analiza je pokazatelj kvaliteta trase (preticanje se vrši u okviru istog kolovoza), a izostavljanje minimalne dužine u posebno složenim uslovima mora biti određeno projektnim zadatkom.\n")
    if pp:
        A(tab("Ostvareni procenat preticajne preglednosti %Pp"))
        A(table(["Trag", "Pp [m]", "Ostvareno %Pp", "Minimum [%]", "Uslov ispunjen", "Broj zona", "Najduža zona [m]"],
                [[f"{TRAG[r['tag']]}, {pg.SIDE_NAME[r['side']]}", fm(r["Pp"]), fm(r["pct"], 1), fm(o["min_proc"], 0), ("DA" if r["ok"] else "NE"), len(r["zones"]), fm(max(r["zlen"])) if r["zlen"] else "0"] for r in pp.values()]))
    seg("A")
    for k, R in out["vp"].items():
        A(f"### Tabela raspoložive preglednosti – {TRAG[R['tag']]}, {pg.SIDE_NAME[R['side']]}\n")
        va = AV(out, k)["avail"]["rows"]; step = max(1, int(round(o["korak_tabela"] / float(par["korak_proracun"]))))
        pr = {x["i"]: x for x in pp[k]["rows"]} if k in pp else {}
        head = ["s [m]", "Vp [km/h]", "Nagib [%]", "Pzp [m]", "Pr [m]", "Pr ≥ Pzp"] + (["Pp [m]", "Pr (preticanje) [m]", "Preticanje"] if pr else [])
        rr = []
        for v in va[::step]:
            row = [fm(v["s"]), fm(v["V"]), fm(v["g"], 2), fm(v["Lz"]), fm(v["D"]), "DA" if v["ok"] else "NE"]
            if pr and v["i"] in pr: x = pr[v["i"]]; row += [fm(x["Lz"]), fm(x["D"]), "DA" if x["ok"] else "NE"]
            elif pr: row += ["", "", ""]
            rr.append(row)
        A(tab(f"Numerički proračun ({TRAG[R['tag']]}, {pg.SIDE_NAME[R['side']]}) – korak {fm(o['korak_tabela'])} m"))
        A(table(head, rr))
    seg("C")
    A("# Model trase\n")
    A("Prostorni model projektovane trase u razmjeri R 1:1000 je ulazni podatak za optičke analize. Model čine osovine kolovoza, ivice kolovoza (crvene linije debljine 0,3 mm u razmjeri crteža), linije prepreka uz kolovoz i zrake preglednosti, u DXF formatu (otvara se u AutoCAD-u, snima kao DWG po potrebi). Grafički prilozi dati su u Sadržaju grafičkih priloga.\n")
    A("# Vizuelizacija\n")
    A("Rezultati se vizuelizuju numeričkim modelom: situacioni prikaz zraka preglednosti po tragovima i dijagrami po stacionaži koji prate profil brzina. Prednost numeričkog modela je brza provjera varijantnih rješenja uz ponovni proračun cijele dionice.\n")
    A("# Sadržaj i uslovi obrade projektne dokumentacije\n")
    A("Sadržaj elaborata definisan je regulativom i propisima navedenim u Opštem dijelu Projektnog zadatka (tačka 3.11) i ostalim pravilnicima i propisima iz ove oblasti. Pored grafičkih priloga u razmjeri R 1:1000 dat je kompletan numerički proračun u tabelarnoj formi (Word i Excel).\n")
    seg("B")
    A("## Sadržaj grafičkih priloga\n")
    A(tab("Sadržaj grafičkih priloga"))
    A(table(["Br.", "Naziv priloga", "Razmjera", "Format", "Datoteka"], [[a, b, c, d, e] for a, b, c, d, e in att]))
    seg("C")
    A("## Korištena regulativa\n")
    A("1. Smjernice za projektovanje, građenje, održavanje i nadzor na putevima u BiH – Geometrijski elementi (1-1-3), tačka 4.2.5 Preglednost pri preticanju, Tabela 8.\n2. Pravilnik o uslovima koje sa aspekta bezbjednosti saobraćaja moraju da ispunjavaju putni objekti i drugi elementi javnog puta (Sl. glasnik RS 50/2011), Prilog 1 tač. 6.1.3 i Prilog 2.\n3. Smjernice za projektovanje puteva u Republici Srbiji – Projektni elementi puta (JP Putevi Srbije), Tabela 4.2.4.\n")
    return "".join(x.rstrip("\n") + "\n\n" for x in md)


def make(P, cases, par, out, cfg, outdir, name, files, log=print):
    from . import report
    o = opt_par(cfg); rs = par["norma"] == "RS"
    if not o["Pp_tablica"]: o["Pp_tablica"] = sorted((float(k), float(v)) for k, v in (PP_RS if rs else PP_BIH).items())
    if "min_proc" not in (cfg.get("optika") or {}) and rs: o["min_proc"] = MIN_RS
    if o["tip_puta"] == "auto": o["tip_puta"] = "dvosmjerni" if any(getattr(c, "role", "") == "osovina" for c in cases) else "razdvojeni"
    log(f"Tip puta za preticanje: {o['tip_puta']}" + (" – preticajna preglednost se ne računa (razdvojeni kolovozi: vozna i preticajna traka)" if o["tip_puta"] == "razdvojeni" else ""))
    pp = run_pp(P, par, out, o, log) if o["tip_puta"] == "dvosmjerni" else {}
    outs = make_png(P, par, out, pp, o, outdir, name, log)
    if pp:
        xp = os.path.join(outdir, f"Optika_preticanje_{name}.xlsx"); write_xlsx(xp, P, par, out, pp, o); outs.append(xp)
    figs = {k: os.path.join(outdir, f"Optika_dijagram_{name}_{k}.png") for k in out["vp"]}
    from . import preglednost_crtez as pgc
    dp = os.path.join(outdir, f"Preglednost_preticanje_{name}.dxf")
    from . import preglednost_dijagram as pgd
    if pp: pgc.draw(P, cases, par, {k: r["E"] for k, r in pp.items()}, cfg, dp, mode="ocek", log=log, title="PREGLEDNOST PRI PRETICANJU – zrake iz lijeve (preticajne) trake"); outs.append(dp)
    att = attachments(outdir, name, list(files) + outs)
    md = build_md(P, par, out, pp, o, cfg, figs, att, name)
    docx = os.path.join(outdir, f"Elaborat_4_Opticke_analize_{name}.docx")
    with tempfile.TemporaryDirectory() as td:
        fd = os.path.join(td, "fig"); os.makedirs(fd)
        for f in figs.values(): shutil.copy(f, fd)
        md = re.sub(r"\]\(([^)/]+\.png)\)", r"](fig/\1)", md)
        mdp = os.path.join(td, "doc.md"); open(mdp, "w", encoding="utf-8").write(md)
        raw = os.path.join(td, "raw.docx"); report.run_pandoc(mdp, raw, td, os.path.join(report.HERE, "data", "ref.docx"))
        report.postprocess(raw, docx, f"Elaborat 4 – Optičke analize | {cfg.get('projekat', '')}")
    log(f"Word: {docx}"); outs.append(docx)
    tp = cfg.get("template") or {}
    if tp.get("file"):
        from . import template_export
        md2 = build_md(P, par, out, pp, o, cfg, figs, att, name, template_mode=True)
        d2 = os.path.join(outdir, f"Elaborat_4_Opticke_analize_{name}_po_templateu.docx")
        with tempfile.TemporaryDirectory() as td:
            fd = os.path.join(td, "fig"); os.makedirs(fd)
            for f in figs.values(): shutil.copy(f, fd)
            md2 = re.sub(r"\]\(([^)/]+\.png)\)", r"](fig/\1)", md2)
            mdp = os.path.join(td, "doc.md"); open(mdp, "w", encoding="utf-8").write(md2)
            raw = os.path.join(td, "raw.docx")
            import subprocess
            from .paths import find_pandoc
            cmd = [find_pandoc(), mdp, "-f", "markdown+pipe_tables+tex_math_dollars+subscript+raw_attribute", "-o", raw, f"--reference-doc={os.path.join(report.HERE, 'data', 'ref.docx')}", "--number-sections", f"--resource-path={td}"]
            rr = subprocess.run(cmd, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if rr.returncode != 0: raise RuntimeError("Pandoc greška: " + rr.stderr[:2000])
            t2 = dict(tp); t2["naslov_izvjestaj"] = "Optičke analize (Elaborat 4) / Optical Analyses (Elaborate 4)"; t2["naslov_numericki"] = "Numerički proračun preglednosti / Numerical Calculation of Sight Distances"; t2["naslov_graficki"] = "Grafički prilozi – optičke analize / Graphical Appendices – Optical Analyses"
            if tp.get("folder_sr_optika"): t2["folder_sr"] = tp["folder_sr_optika"]
            if tp.get("folder_en_optika"): t2["folder_en"] = tp["folder_en_optika"]
            template_export.export(raw, t2, d2, log)
        outs.append(d2)
    return outs, pp
