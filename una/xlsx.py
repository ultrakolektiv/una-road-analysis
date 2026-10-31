"""Excel radna knjiga sa formulama i dijagramima (za proizvoljan broj sekcija i osovina)."""
from .i18n import _T, _TF, cell as _cell
import math
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as CL
from openpyxl.chart import ScatterChart, Reference, Series
from .engine import chains, TIPOVI

Fn = lambda **k: Font(name="Arial", size=k.pop("size", 10), **k)
BLUE = Fn(color="0000FF"); BLK = Fn(); BOLD = Fn(bold=True); GREEN = Fn(color="008000")
HFILL = PatternFill("solid", fgColor="D9E2F3")
thin = Side(style="thin", color="999999"); BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
R0 = 6
PAL = ["1F77B4", "D62728", "2CA02C", "FF7F0E", "9467BD", "8C564B", "E377C2", "7F7F7F", "BCBD22", "17BECF"]


def hdr(ws, row, vals, col=1):
    for i, v in enumerate(vals):
        c = ws.cell(row, col + i, _cell(v)); c.font = BOLD; c.fill = HFILL
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center"); c.border = BOX


def put(ws, ref, v, font=BLK, fmt=None):
    c = ws[ref]; c.value = _cell(v); c.font = font
    if fmt: c.number_format = fmt
    return c


def build_xlsx(path, P, sections, cases, axes, SYM, TABCOL, has_caps, log=print, stamp=None):
    wb = Workbook(); fw, bw = chains(cases)
    axid = {id(a): i + 1 for i, a in enumerate(axes)}
    nveh = len(P.vozila)
    # ------------------------------------------------------------ Pretpostavke
    ws = wb.active; ws.title = "Pretpostavke"
    lines = [_TF('VOZNO-DINAMIČKA ANALIZA – {0} – radna knjiga uz vozno-dinamičku analizu', P.projekat),
        "Sekcije: " + "; ".join(f"{s['no']}. {_T(TIPOVI[s['tip']])}, st. {s['od']}–{s['do']}" for s in sections) + _T('. Preglednost (optička analiza) NIJE obuhvaćena.'), "",
        "KAKO SE KORISTI:",
        _T(' 1. Na listovima Ulaz_* zamijenite plave podatke ispisima projektanta: elementi horizontalne osovine (A–H), prelomne tačke nivelete (O–U), poprečni nagibi (AC i dalje). Dodajete li redove, UMETNITE ih unutar tablice (iznad zadnjeg reda).'),
        _T(' 2. Na listovima Profil_* podesite početnu/krajnju stacionažu i korak (plava polja u redu 3).'),
        _T(' 3. Sve ostalo se računa formulama: Vp–R, Vp–iN, profil brzine, teška vozila, vrijeme, gorivo, statistika, provjere nagiba i dijagrami (list Dijagrami).'),
        _T(' 4. Skup susjednih elemenata (Provjere_*) i spisak lukova za provjeru su ulazni podaci (plavo).'), "",
        _T('BOJE: plavo = ulaz/pretpostavka; crno = formula; zeleno = veza na drugi list.'),
        _T("LANAC: brzina na granici sekcija prenosi se između listova (ulazna brzina, a usporenje 'gleda unaprijed' na početak sljedeće sekcije)."), "",
        _T('METODA: Prilog 2 pravilnika (Sl. glasnik RS 50/2011; naziv provjeriti) i Priručnik za projektovanje puteva u RS (4.0): Vp (=V85) je posljedica geometrije, Vri ≤ Vp ≤ maxVr; zakoni Vp–R i Vp–iN; a = d = 0,8 m/s².'), "",
        _T('PRETPOSTAVKE (provjeriti!): 1) Vp–R = interpolacija tablice Rmin(Vr) sastavljene na osnovu dijagrama (slika 3-07, Prilog 2 pravilnika); 2) Vp–iN = tablica sastavljena na osnovu dijagrama (slika 3-08, Prilog 2 pravilnika); 3) teška vozila: parametri pretpostavljeni (list Parametri); 4) mreža ') + _TF('{0:g} m, statistika ponderisana po dužini, vrijeme = ∫ds/v; 5) poprečni nagib luka = nagib odabrane trake (Ulaz_*), apsolutna vrijednost; 6) kriterij ΔV: ≤10 dobro, 10–20 zadovoljavajuće, >20 loše (Lamm); ocjena po ciljnim brzinama.', P.korak),
        _T('SCENARIJ: Parametri!B14 = 1 samo geometrija; 2 = dodatno ograničenje brzine iz tabele ograničenja (Parametri, red 59 i dalje).')]
    for i, l in enumerate(lines, 1):
        c = ws.cell(i, 1, l); c.font = BOLD if i in (1, 4) else BLK; c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 150
    # ------------------------------------------------------------ Oznake
    o = wb.create_sheet("Oznake"); put(o, "A1", _T('OZNAKE I SIMBOLI (isto kao Tabela O1 u elaboratu)'), BOLD)
    hdr(o, 3, ["Oznaka", _T('Značenje'), "Jedinica", "Izvor vrijednosti", "Gdje se koristi"])
    for i, r in enumerate(SYM):
        for j, v in enumerate(r): put(o, f"{CL(1 + j)}{4 + i}", v.replace("~", ""))
    r0 = 6 + len(SYM); hdr(o, r0, [_T('Tabela'), _T('Značenje kolona')])
    for i, r in enumerate(TABCOL): put(o, f"A{r0 + 1 + i}", r[0]); put(o, f"B{r0 + 1 + i}", r[1].replace("~", ""))
    for c, w in zip("ABCDE", (22, 70, 12, 34, 34)): o.column_dimensions[c].width = w
    # ------------------------------------------------------------ Parametri
    u = wb.create_sheet("Parametri"); put(u, "A1", "ULAZNI PARAMETRI I TABLICE", BOLD)
    rows = [(_T('Računska brzina Vr'), P.Vr, "km/h", _T('Projektni zadatak')), (_T('Najveća projektna brzina maxVr'), P.maxVr, "km/h", "Vr + dodatak (Prilog 2)"),
            ("Ubrzanje a", P.a, "m/s²", _T('ekvivalent obrasca 0,1·Vsr·ΔV (slika 3-09), nominalno 0,8')), ("Usporenje d", P.d, "m/s²", _T('ekvivalent obrasca 0,1·Vsr·ΔV (slika 3-09), nominalno 0,8')), (_T('Zadani korak mreže'), P.korak, "m", "koristi se u Profil_* (H3)"),
            ("g", P.g, "m/s²", ""), ("Gustina zraka ρ", P.rho, "kg/m³", ""), (_T('Specifična potrošnja goriva b'), P.b, "l/kWh", "pretpostavka"),
            (_T('Potrošnja u praznom hodu'), P.prazan_hod, "l/h", "pretpostavka"),
            (_T('Ulazna brzina putničkog na ulazu u lanac'), P.ulazna_brzina, "km/h", "slobodan tok"),
            (_T('Gornja granica Vp,R (najveći max Vr po zonama)'), None, "km/h", _T('računa se iz zona Vr (tabela dolje)')),
            ("f_rl0 (otpor kotrljanja)", P.frl0, "–", "f_rl = f_rl0·(1+V/44,73)"), (_T('Brzinski parametar f_rl'), P.frl_v, "m/s", ""),
            (_T('Dodatak max Vr = Vr + dodatak'), P.dodatak_maxVr, "km/h", "Prilog 2"), (_T('max Vr prema tabeli 3-04 (999 = bez ograničenja)'), float(P.maxVr_tab) if P.maxVr_tab not in (None, "", 0) else 999.0, "km/h", "Prilog 2")]
    for i, (a, b, c, d) in enumerate(rows):
        r = 4 + i; put(u, f"A{r}", a); put(u, f"B{r}", b, BLUE); put(u, f"C{r}", c); put(u, f"D{r}", d)
    # adrese: B4 Vr,B5 maxVr,B6 a,B7 d,B8 step,B9 g,B10 rho,B11 b,B12 idle,B13 vin,B14 max Vp,R gornja granica,B15 frl0,B16 frl_v,B17 dodatak,B18 tab 3-04
    hdr(u, 20, [_T('Parametar vozila')] + [v["kratko"] for v in P.vozila])
    vp = [("Masa m [kg]", "m"), ("Snaga motora P [kW]", "P"), ("CdA [m²]", "CdA"), (_T('Stepen iskorištenja η'), "eta"), (_T('Ograničenje brzine v_lim [km/h]'), "vlim"), (_T('Faktor rotirajućih masa γm'), "gam"), ("Koef. prianjanja μ", "mu"), (_T('Specifična potrošnja goriva b [l/kWh]'), "b"), (_T('Potrošnja u praznom hodu [l/h]'), "prazan_hod")]
    for i, (lab, k) in enumerate(vp):
        r = 21 + i; put(u, f"A{r}", lab)
        for q, v in enumerate(P.vozila): put(u, f"{CL(2 + q)}{r}", v[k], BLUE)
    for q, v in enumerate(P.vozila):          # kriva sile vuče iz dijagrama (slika 3-10), ako je zadana
        if v.get("Ft_kriva"):
            cx, cy = 6 + 2 * q, 7 + 2 * q
            hdr(u, 32, [f"v [km/h] – {v['kratko']}", "Ft [N]"], cx)
            for j, (vk, F) in enumerate(v["Ft_kriva"]): put(u, f"{CL(cx)}{33 + j}", vk, BLUE); put(u, f"{CL(cy)}{33 + j}", F, BLUE, "0")
            u.column_dimensions[CL(cx)].width = 22; u.column_dimensions[CL(cy)].width = 12
    nt = len(P.Vr_tab); T1 = 33
    hdr(u, T1 - 1, ["Vr [km/h]", "R_min [m]", "fT", "fR"])
    for i in range(nt):
        r = T1 + i; put(u, f"A{r}", P.Vr_tab[i], BLUE); put(u, f"B{r}", P.Rmin_tab[i], BLUE); put(u, f"C{r}", P.fT[i], BLUE); put(u, f"D{r}", P.fR[i], BLUE)
    T1e = T1 + nt - 1
    put(u, f"E{T1 - 1}", _T('Tabela 1 (Prilog 2 pravilnika)'))
    T2 = T1e + 5; ni = len(P.iN_tab)
    hdr(u, T2 - 1, [_T('Nagib iN [%]'), "Vp(iN) [km/h]"])
    for i in range(ni): put(u, f"A{T2 + i}", P.iN_tab[i], BLUE); put(u, f"B{T2 + i}", P.ViN_tab[i], BLUE)
    T2e = T2 + ni - 1; put(u, f"C{T2 - 1}", _T('Tabela 2: sastavljena na osnovu dijagrama (slika 3-08, Prilog 2 pravilnika)'))
    T3 = T2e + 5; NZ = 10
    hdr(u, T3 - 1, [_T('Zona Vr od st. [m]'), _T('do st. [m]'), _T('računska brzina Vr [km/h]')]); put(u, f"D{T3 - 1}", _T('Tabela zona računske brzine (izvan zona važi Vr iz B4), oba smjera'))
    zones = []
    for c in cases:
        for z in c.zvr:
            if z not in zones: zones.append(z)
    for i in range(NZ):
        r = T3 + i
        if i < len(zones):
            for j in range(3): put(u, f"{CL(1 + j)}{r}", zones[i][j], BLUE, "0.000")
        else:
            for j in range(3): put(u, f"{CL(1 + j)}{r}", None, BLUE)
    T3e = T3 + NZ - 1
    put(u, "B14", f"=MAX(B5,IF(COUNT(C{T3}:C{T3e})>0,MIN(MAX(C{T3}:C{T3e})+B17,B18),0))", BLK, "0.0")
    u.column_dimensions["A"].width = 56
    for c in "BCD": u.column_dimensions[c].width = 22
    Pm = "Parametri!"
    def vrow(q, k): return f"{Pm}${CL(2 + q)}${21 + k}"      # k: 0 m,1 P,2 CdA,3 eta,4 vlim,5 gam,6 mu
    # ------------------------------------------------------------ Ulaz_n
    ULAZ = {}
    for a in axes:
        i = axid[id(a)]; w = wb.create_sheet(f"Ulaz_{i}")
        put(w, "A1", f"ULAZNI PODACI GEOMETRIJE – {a.name} ({', '.join(f.replace(chr(92), '/').split('/')[-1] for f in a.files)})", BOLD)
        put(w, "A2", _T('Radijus: + desna krivina, − lijeva, 0 = beskonačno. Plave kolone su ulazni podaci.'), BLK)
        put(w, "A3", _T('TABELA – ELEMENTI HORIZONTALNE OSOVINE'), BOLD)
        hdr(w, 4, ["Br.", "Tip", _T('St. početka [m]'), "St. kraja [m]", "L [m]", _T('R početak [m]'), "R kraj [m]", "A [m]", "Vp,R [km/h]", "Kontrola A²=R·L [m]", "Smjer", _T('k početak [1/km]'), "k kraj [1/km]"]); w.row_dimensions[4].height = 42
        e0 = 5; e1 = 4 + len(a.elems)
        for q, e in enumerate(a.elems):
            r = 5 + q
            put(w, f"A{r}", e["no"], BLUE); put(w, f"B{r}", e["typ"], BLUE); put(w, f"C{r}", e["s0"], BLUE, "0.000"); put(w, f"D{r}", e["s1"], BLUE, "0.000"); put(w, f"E{r}", f"=D{r}-C{r}", BLK, "0.000")
            put(w, f"F{r}", 0 if math.isinf(e["R0"]) else e["R0"], BLUE, "0.00"); put(w, f"G{r}", 0 if math.isinf(e["R1"]) else e["R1"], BLUE, "0.00"); put(w, f"H{r}", e["A"] if e["A"] else None, BLUE, "0.000")
            m = f"MATCH(ABS(F{r}),{Pm}$B${T1}:$B${T1e},1)"
            put(w, f"I{r}", (f'=IF(B{r}="KRUZNI_LUK",MIN({Pm}$B$14,IF(ABS(F{r})<={Pm}$B${T1},{Pm}$A${T1},IF(ABS(F{r})>={Pm}$B${T1e},{Pm}$A${T1e},'
                f'INDEX({Pm}$A${T1}:$A${T1e},{m})+(ABS(F{r})-INDEX({Pm}$B${T1}:$B${T1e},{m}))*(INDEX({Pm}$A${T1}:$A${T1e},{m}+1)-INDEX({Pm}$A${T1}:$A${T1e},{m}))/(INDEX({Pm}$B${T1}:$B${T1e},{m}+1)-INDEX({Pm}$B${T1}:$B${T1e},{m}))))),{Pm}$B$14)'), BLK, "0.0")
            put(w, f"J{r}", _TF('=IF(B{0}="PRIJELAZNICA",SQRT(MAX(ABS(F{1}),ABS(G{2}))*E{3}),"")', r, r, r, r), BLK, "0.000")
            put(w, f"K{r}", f'=IF(B{r}="PRAVAC","",IF(IF(F{r}=0,G{r},F{r})>0,"desno","lijevo"))', BLK)
            put(w, f"L{r}", f"=IF(F{r}=0,0,1000/F{r})", BLK, "0.000"); put(w, f"M{r}", f"=IF(G{r}=0,0,1000/G{r})", BLK, "0.000")
        put(w, "O3", _T('TABELA – PRELOMNE TAČKE NIVELETE'), BOLD)
        hdr(w, 4, ["PT", "Stac. [m]", "Kota [m]", "Rv [m]", "i izl. [%]", "TZ [m]", "TK [m]", "Δi [%]", "Lvk [m]", "T [m]", "e [m]", "Tip", "i ul. [%]"], 15)
        p0 = 5; p1 = 4 + len(a.pis)
        for q, p in enumerate(a.pis):
            r = 5 + q
            put(w, f"O{r}", q, BLUE); put(w, f"P{r}", p[0], BLUE, "0.000"); put(w, f"Q{r}", p[1], BLUE, "0.000"); put(w, f"R{r}", p[2], BLUE, "0"); put(w, f"S{r}", p[3], BLUE, "0.000")
            put(w, f"T{r}", p[4], BLUE, "0.000"); put(w, f"U{r}", p[5], BLUE, "0.000")
            put(w, f"AA{r}", (f"=S{r - 1}" if q > 0 else f"=S{r}"), BLK, "0.000")
            put(w, f"V{r}", f"=ABS(S{r}-AA{r})", BLK, "0.000"); put(w, f"W{r}", f"=U{r}-T{r}", BLK, "0.0"); put(w, f"X{r}", f"=W{r}/2", BLK, "0.0")
            put(w, f"Y{r}", f"=IF(R{r}>0,X{r}^2/(2*R{r}),0)", BLK, "0.00"); put(w, f"Z{r}", _TF('=IF(W{0}>0,IF(S{1}>AA{2},"udubljena","ispupčena"),"–")', r, r, r), BLK)
        put(w, "AC3", _TF('POPREČNI NAGIBI (po trakama; za provjeru: lijeva {0}, desna {1})', a.cs_heads[a.cs_left], a.cs_heads[a.cs_right]), BOLD)
        hdr(w, 4, [_T('Stacionaža [m]')] + [h + " [%]" for h in a.cs_heads], 29)
        for q in range(len(a.cs_s)):
            r = 5 + q; put(w, f"AC{r}", float(a.cs_s[q]), BLUE, "0.000")
            for j in range(a.cs_val.shape[1]): put(w, f"{CL(30 + j)}{r}", float(a.cs_val[q, j]), BLUE, "0.000")
        nr = len(a.cs_s); lcol = CL(30 + a.cs_left); rcol = CL(30 + a.cs_right)
        put(w, f"AC{6 + nr}", "Provjera: zbir |lijeva + desna| (0 = desna strana zrcalna lijevoj)", BLK)
        put(w, f"AC{7 + nr}", f"=SUMPRODUCT(ABS({lcol}5:{lcol}{4 + nr}+{rcol}5:{rcol}{4 + nr}))", BLK, "0.000")
        for c, wd in zip("ABCDEFGHIJKLM", (6, 16, 14, 14, 11, 13, 13, 11, 11, 13, 9, 12, 12)): w.column_dimensions[c].width = wd
        for c in "OPQRSTUVWXYZ": w.column_dimensions[c].width = 11
        for cc in range(29, 37): w.column_dimensions[CL(cc)].width = 14
        w.freeze_panes = "A5"
        ULAZ[id(a)] = dict(sheet=f"Ulaz_{i}", e0=e0, e1=e1, p0=p0, p1=p1, c0=5, c1=4 + nr, lcol=lcol, rcol=rcol)
    # ------------------------------------------------------------ Profil_*
    def iNf(ref):
        A_ = f"{Pm}$A${T2}:$A${T2e}"; B_ = f"{Pm}$B${T2}:$B${T2e}"; m = f"MATCH({ref},{A_},1)"
        return (f"IF({ref}<={Pm}$A${T2},{Pm}$B${T2},IF({ref}>={Pm}$A${T2e},{Pm}$B${T2e},INDEX({B_},{m})+({ref}-INDEX({A_},{m}))*(INDEX({B_},{m}+1)-INDEX({B_},{m}))/(INDEX({A_},{m}+1)-INDEX({A_},{m}))))")
    PROF = {}
    def chain_pos(c):
        ch = fw if c.sg == 1 else bw; q = ch.index(c)
        return ch, q
    def trow(c, which):   # red prvog / zadnjeg po smjeru vožnje
        first = R0 if c.sg == 1 else R0 + c.N - 1; last = R0 + c.N - 1 if c.sg == 1 else R0
        return first if which == "first" else last
    for c in cases:
        U = ULAZ[id(c.axis)]; ug = U["sheet"]; N = c.N; sg = c.sg
        p = wb.create_sheet(f"Profil_{c.key}")
        put(p, "A1", _TF('REZULTIRAJUĆI PROFIL PROJEKTNE BRZINE – PUTNIČKO VOZILO – {0}', c.label), BOLD)
        put(p, "A2", _TF('Osovina: {0}. Cilj T = min(Vp,R ; Vp,iN u smjeru vožnje ; max Vr u zoni Vr). Prolaz 1: ubrzanje a; prolaz 2: usporenje d (v² = v₀² + 2·a·Δs). Kota i nagib iz prelomnih tačaka ({1}).', c.axis.name, ug), BLK)
        put(p, "A3", "Smjer (+1/−1)"); put(p, "B3", sg, BLUE, "0"); put(p, "C3", _T('SA [m]')); put(p, "D3", float(c.SA), BLUE, "0.000"); put(p, "E3", "SB [m]"); put(p, "F3", float(c.SB), BLUE, "0.000")
        put(p, "G3", "Korak [m]"); put(p, "H3", f"={Pm}B8", GREEN, "0.0"); put(p, "I3", _T('Ulazna brzina [km/h]'))
        ch, q = chain_pos(c)
        if q == 0: put(p, "J3", f"={Pm}B13", GREEN, "0.000")
        else:
            pc = ch[q - 1]; put(p, "J3", f"=Profil_{pc.key}!J{trow(pc, 'last')}", GREEN, "0.000")
        put(p, "K3", _T('Granični uslov na izlazu [km/h]'))
        if q == len(ch) - 1: put(p, "L3", 999, BLUE, "0")
        else:
            nc = ch[q + 1]; put(p, "L3", f"=Profil_{nc.key}!K{trow(nc, 'first')}", GREEN, "0.000")
        hdr(p, 5, ["Stac. s [m]", "Δs [m]", "Kota z [m]", _T('Nagib g [%]'), "R [m] (0=∞)", "El. indeks", "Vp,R [km/h]", _T('Vp,iN u smjeru vožnje [km/h]'), "Cilj T [km/h]", "Nakon ubrzanja [km/h]", _T('REZULTIRAJUĆA Vp [km/h]'), "dt [s]", _T('Krivina 1000/R [1/km]'), _T('Poprečni nagib lijeve strane [%]'), "Vr [km/h]", "Idx PT", _T('Poprečni nagib desne strane [%]')]); p.row_dimensions[5].height = 48
        E = lambda col: f"{ug}!${col}${U['e0']}:${col}${U['e1']}"
        Pp = lambda col: f"{ug}!${col}${U['p0']}:${col}${U['p1']}"
        Cc = lambda col: f"{ug}!${col}${U['c0']}:${col}${U['c1']}"
        sgn = "" if sg == 1 else "-"
        for i in range(N):
            r = R0 + i
            if i == 0: put(p, f"A{r}", "=$D$3", BLK, "0.000")
            else: put(p, f"A{r}", f"=MIN(A{r - 1}+$H$3,$F$3)", BLK, "0.000"); put(p, f"B{r}", f"=A{r}-A{r - 1}", BLK, "0.000")
            s = f"$A{r}"
            put(p, f"P{r}", f"=IFERROR(MATCH({s},{Pp('T')},1),0)", BLK, "0"); k = f"$P{r}"
            inc = f"AND({k}>1,INDEX({Pp('U')},{k})>INDEX({Pp('T')},{k}),{s}<=INDEX({Pp('U')},{k}))"
            put(p, f"C{r}", (f"=IF({k}=0,INDEX({Pp('Q')},1)+INDEX({Pp('S')},1)/100*({s}-INDEX({Pp('P')},1)),IF({inc},"
                f"INDEX({Pp('Q')},{k})+INDEX({Pp('S')},{k}-1)/100*({s}-INDEX({Pp('P')},{k}))+(INDEX({Pp('S')},{k})-INDEX({Pp('S')},{k}-1))/(200*(INDEX({Pp('U')},{k})-INDEX({Pp('T')},{k})))*({s}-INDEX({Pp('T')},{k}))^2,"
                f"INDEX({Pp('Q')},{k})+INDEX({Pp('S')},{k})/100*({s}-INDEX({Pp('P')},{k}))))"), BLK, "0.000")
            put(p, f"D{r}", (f"=IF({k}=0,INDEX({Pp('S')},1),IF({inc},INDEX({Pp('S')},{k}-1)+(INDEX({Pp('S')},{k})-INDEX({Pp('S')},{k}-1))*({s}-INDEX({Pp('T')},{k}))/(INDEX({Pp('U')},{k})-INDEX({Pp('T')},{k})),INDEX({Pp('S')},{k})))"), BLK, "0.000")
            put(p, f"F{r}", f"=MATCH({s},{E('C')},1)", BLK, "0")
            put(p, f"E{r}", f'=IF(INDEX({E("B")},F{r})="KRUZNI_LUK",ABS(INDEX({E("F")},F{r})),0)', BLK, "0.00")
            put(p, f"G{r}", f"=INDEX({E('I')},F{r})", GREEN, "0.0")
            put(p, f"H{r}", "=" + iNf(f"({sgn}D{r})"), BLK, "0.0")
            put(p, f"I{r}", f"=MIN(G{r},H{r},IF(COUNTIFS({Pm}$A${T3}:$A${T3e},\"<=\"&{s},{Pm}$B${T3}:$B${T3e},\">=\"&{s})>0,MIN(_xlfn.MAXIFS({Pm}$C${T3}:$C${T3e},{Pm}$A${T3}:$A${T3e},\"<=\"&{s},{Pm}$B${T3}:$B${T3e},\">=\"&{s})+{Pm}$B$17,{Pm}$B$18),{Pm}$B$5))", BLK, "0.0")
            put(p, f"M{r}", f"=INDEX({E('L')},F{r})+(INDEX({E('M')},F{r})-INDEX({E('L')},F{r}))*({s}-INDEX({E('C')},F{r}))/MAX(INDEX({E('E')},F{r}),0.000000001)", BLK, "0.000")
            for colx, tgt in ((U["lcol"], "N"), (U["rcol"], "Q")):
                mm = f"MATCH({s},{Cc('AC')},1)"
                put(p, f"{tgt}{r}", (f"=IF({s}<=INDEX({Cc('AC')},1),INDEX({Cc(colx)},1),IF({s}>=INDEX({Cc('AC')},ROWS({Cc('AC')})),INDEX({Cc(colx)},ROWS({Cc(colx)})),"
                    f"INDEX({Cc(colx)},{mm})+({s}-INDEX({Cc('AC')},{mm}))*(INDEX({Cc(colx)},{mm}+1)-INDEX({Cc(colx)},{mm}))/MAX(INDEX({Cc('AC')},{mm}+1)-INDEX({Cc('AC')},{mm}),0.000000001)))"), BLK, "0.00")
            put(p, f"O{r}", f"={Pm}$B$4", GREEN, "0")
            ac = lambda ref, rr: f"SQRT(({ref}/3.6)^2+2*{Pm}$B$6*{rr})*3.6"
            dc = lambda ref, rr: f"SQRT(({ref}/3.6)^2+2*{Pm}$B$7*{rr})*3.6"
            if sg == 1:
                put(p, f"J{r}", f"=MIN(I{r},$J$3)" if i == 0 else f"=MIN(I{r},{ac(f'J{r - 1}', f'B{r}')})", BLK, "0.0")
                put(p, f"K{r}", f"=MIN(J{r},$L$3)" if i == N - 1 else f"=MIN(J{r},{dc(f'K{r + 1}', f'B{r + 1}')})", BLK, "0.0")
            else:
                put(p, f"J{r}", f"=MIN(I{r},$J$3)" if i == N - 1 else f"=MIN(I{r},{ac(f'J{r + 1}', f'B{r + 1}')})", BLK, "0.0")
                put(p, f"K{r}", f"=MIN(J{r},$L$3)" if i == 0 else f"=MIN(J{r},{dc(f'K{r - 1}', f'B{r}')})", BLK, "0.0")
            if i > 0: put(p, f"L{r}", f"=B{r}*3.6*(1/K{r - 1}+1/K{r})/2", BLK, "0.000")
        for cc in "ABCDEFGHIJKLMNOPQ": p.column_dimensions[cc].width = 13
        p.freeze_panes = "B6"; PROF[c.key] = dict(N=N, R1=R0 + N - 1)
    # ------------------------------------------------------------ Voz*_*
    TRS = {}
    for c in cases:
        N = c.N; sg = c.sg; ch, q = chain_pos(c)
        for k, veh in enumerate(P.vozila):
            sn = f"Voz{k + 1}_{c.key}"; t = wb.create_sheet(sn)
            put(t, "A1", _TF('{0} – profil brzine, vrijeme i potrošnja goriva – {1}', veh['naziv'].upper(), c.label), BOLD)
            put(t, "A2", _T('Fr = f_rl·m·g + ½ρ·CdA·v² + m·g·G; Ft = min(η·P/v ; μ·m·g) – za vozilo s krivom vuče (slika 3-10): Ft(v) interpolirano iz tabele na listu Parametri; v² = v₀² + 2·(Ft−Fr)/(γm·m)·Δs; gorivo = b·(Fu·v/η)·dt (Fu=Fr pri v_lim; Fu=Ft pri punom opterećenju; prazan hod pri Fr≤0).'), BLK)
            put(t, "A3", _T('Početna brzina [km/h]'))
            if q == 0: put(t, "B3", f"={vrow(k, 4)}", GREEN, "0.000")
            else:
                pc = ch[q - 1]; put(t, "B3", f"=Voz{k + 1}_{pc.key}!O{trow(pc, 'last')}", GREEN, "0.000")
            m, Pw, CdA, eta, vl, gam, mu = (vrow(k, j) for j in range(7))
            hdr(t, 5, ["Stac. [m]", _T('Nagib [%]'), "Δs koraka [m]"]); hdr(t, 5, ["v [m/s]", "G", "Fr [N]", "Ft [N]", _T('v sljedeće [m/s]'), "Fu [N]", "v sr [m/s]", "dt [s]", "gorivo [l]", "Σt [s]", "Σgorivo [l]", "v [km/h]"], 4); t.row_dimensions[5].height = 40
            for i in range(N):
                r = R0 + i
                put(t, f"A{r}", f"=Profil_{c.key}!A{r}", GREEN, "0.000"); put(t, f"B{r}", f"=Profil_{c.key}!D{r}", GREEN, "0.000")
                v, Gc, Fr, Ft, vn, Fu, vav, dt, fu, Tc, Fc, vk = [CL(4 + z) for z in range(12)]
                first = (i == 0) if sg == 1 else (i == N - 1); last = (i == N - 1) if sg == 1 else (i == 0)
                prev = r - 1 if sg == 1 else r + 1; nxt = r + 1 if sg == 1 else r - 1
                if not last: put(t, f"C{r}", f"=Profil_{c.key}!B{r + 1}" if sg == 1 else f"=Profil_{c.key}!B{r}", GREEN, "0.000")
                if first: put(t, f"{v}{r}", "=$B$3/3.6", BLK, "0.000"); put(t, f"{Tc}{r}", 0, BLK, "0.0"); put(t, f"{Fc}{r}", 0, BLK, "0.000")
                else:
                    put(t, f"{v}{r}", f"={vn}{prev}", BLK, "0.000"); put(t, f"{Tc}{r}", f"={Tc}{prev}+{dt}{prev}", BLK, "0.0"); put(t, f"{Fc}{r}", f"={Fc}{prev}+{fu}{prev}", BLK, "0.000")
                put(t, f"{vk}{r}", f"={v}{r}*3.6", BLK, "0.0")
                if not last:
                    s_ = "" if sg == 1 else "-"
                    put(t, f"{Gc}{r}", f"={s_}(B{r}+B{nxt})/200", BLK, "0.0000")
                    put(t, f"{Fr}{r}", f"={Pm}$B$15*(1+{v}{r}/{Pm}$B$16)*{m}*{Pm}$B$9+0.5*{Pm}$B$10*{CdA}*{v}{r}^2+{m}*{Pm}$B$9*{Gc}{r}", BLK, "0")
                    if veh.get("Ft_kriva"):
                        n_ = len(veh["Ft_kriva"]); cX = f"{Pm}${CL(6 + 2 * k)}$33:${CL(6 + 2 * k)}${32 + n_}"; cY = f"{Pm}${CL(7 + 2 * k)}$33:${CL(7 + 2 * k)}${32 + n_}"
                        V_ = f"({v}{r}*3.6)"; mt = f"MATCH({V_},{cX},1)"
                        put(t, f"{Ft}{r}", f"=MIN({mu}*{m}*{Pm}$B$9,IF({V_}<=INDEX({cX},1),INDEX({cY},1),IF({V_}>=INDEX({cX},{n_}),INDEX({cY},{n_})*INDEX({cX},{n_})/{V_},INDEX({cY},{mt})+({V_}-INDEX({cX},{mt}))*(INDEX({cY},{mt}+1)-INDEX({cY},{mt}))/(INDEX({cX},{mt}+1)-INDEX({cX},{mt})))))", BLK, "0")
                    else: put(t, f"{Ft}{r}", f"=MIN({eta}*{Pw}*1000/MAX({v}{r},3),{mu}*{m}*{Pm}$B$9)", BLK, "0")
                    put(t, f"{vn}{r}", f"=IF(AND({v}{r}>={vl}/3.6-1E-9,{Ft}{r}>={Fr}{r}),{vl}/3.6,MIN({vl}/3.6,SQRT(MAX({v}{r}^2+2*({Ft}{r}-{Fr}{r})/({gam}*{m})*C{r},9))))", BLK, "0.000")
                    put(t, f"{Fu}{r}", f"=IF(AND({v}{r}>={vl}/3.6-1E-9,{Ft}{r}>={Fr}{r}),MAX({Fr}{r},0),IF({Fr}{r}>0,{Ft}{r},0))", BLK, "0")
                    put(t, f"{vav}{r}", f"=({v}{r}+{vn}{r})/2", BLK, "0.000"); put(t, f"{dt}{r}", f"=C{r}/{vav}{r}", BLK, "0.000")
                    put(t, f"{fu}{r}", f"=IF({Fr}{r}<=0,{Pm}${CL(2 + k)}$29*{dt}{r}/3600,{Pm}${CL(2 + k)}$28*({Fu}{r}*{vav}{r}/{eta}/1000)*{dt}{r}/3600)", BLK, "0.0000")
            for z in range(1, 16): t.column_dimensions[CL(z)].width = 12
            t.freeze_panes = "D6"
            TRS[(c.key, k)] = dict(sn=sn, end=trow(c, "last"), first=trow(c, "first"))
    # ------------------------------------------------------------ Provjere_*
    for c in cases:
        U = ULAZ[id(c.axis)]; ug = U["sheet"]; N = c.N; R1 = R0 + N - 1
        h = wb.create_sheet(f"Provjere_{c.key}")
        put(h, "A1", _TF('USKLAĐENOST SUSJEDNIH ELEMENATA I PROVJERA POPREČNIH NAGIBA – {0}', c.label), BOLD)
        put(h, "A2", _T('ΔVp između susjednih elemenata (krivine: najmanja brzina; pravci: najveća). Jedinice su ulazni podatak.'), BLK)
        hdr(h, 3, ["Br.", _T('Tip (P=pravac, K=krivina)'), _T('St. početka [m]'), "St. kraja [m]", "L [m]", _T('R kružnog luka [m]'), _T('Smjer krivine'), "Vp,i – cilj T [km/h]", "ΔVp,cilj [km/h]", _T('Ocjena (po ΔVp,cilj)'), _T('Vp,i – rezultirajuća [km/h]'), _T('ΔV rezultirajuća [km/h]')]); h.row_dimensions[3].height = 55
        rg = f"Profil_{c.key}!$K${R0}:$K${R1}"; tg = f"Profil_{c.key}!$I${R0}:$I${R1}"; ag = f"Profil_{c.key}!$A${R0}:$A${R1}"
        for i, un in enumerate(c.units):
            r = 4 + i; a_ = max(un["s0"], c.SA); b_ = min(un["s1"], c.SB)
            put(h, f"A{r}", i + 1, BLUE); put(h, f"B{r}", un["kind"], BLUE); put(h, f"C{r}", round(a_, 3), BLUE, "0.000"); put(h, f"D{r}", round(b_, 3), BLUE, "0.000"); put(h, f"E{r}", f"=D{r}-C{r}", BLK, "0.0")
            put(h, f"F{r}", 0 if math.isinf(un["R"]) else un["R"], BLUE, "0.00"); put(h, f"G{r}", un.get("dir", "–"), BLUE)
            for col, rng_ in (("H", tg), ("K", rg)):
                put(h, f"{col}{r}", f'=IF(B{r}="K",_xlfn.MINIFS({rng_},{ag},">="&C{r},{ag},"<="&D{r}),_xlfn.MAXIFS({rng_},{ag},">="&C{r},{ag},"<="&D{r}))', GREEN, "0.0")
            if i < len(c.units) - 1:
                put(h, f"I{r}", f"=ABS(H{r}-H{r + 1})", BLK, "0.0"); put(h, f"J{r}", _TF('=IF(I{0}<=10,"dobro",IF(I{1}<=20,"zadovoljavajuće","loše"))', r, r)); put(h, f"L{r}", f"=ABS(K{r}-K{r + 1})", BLK, "0.0")
        q0 = 4 + len(c.units) + 3
        put(h, f"A{q0 - 2}", _T('PROVJERA POPREČNOG NAGIBA NA KRUŽNIM LUKOVIMA'), BOLD)
        put(h, f"A{q0 - 1}", _T('ipk(Vr) = 7·(R_min(Vr)/R)^0,74 [%], 2,5 ≤ ipk ≤ 7; ip,potr = V²/(127R) − fR(V); f_pot = V²/(127R) − ip/100 ≤ fR(V). V = najmanja rezultirajuća brzina na luku (dio unutar granica).'), BLK)
        hdr(h, q0, ["El. br.", "R [m]", "Smjer", _T('St. početka [m]'), "St. kraja [m]", "Vp,R [km/h]", _T('V rezultirajuća (min) [km/h]'), "ipk(Vr) [%]", "ipk zaokr. 0,1 [%]", "Primijenjeni ip [%]", "Uslov ip ≥ ipk(Vr)", "fR(V)", _T('ip,potr za V [%]'), "f_pot pri ip primijenjenom", "Uslov f_pot ≤ fR", "R_min(Vr) [m]", "Uslov R ≥ R_min(Vr)"]); h.row_dimensions[q0].height = 55
        arcs = [e for e in c.axis.elems if e["typ"] == "KRUZNI_LUK" and min(e["s1"], c.SB) - max(e["s0"], c.SA) >= 20]
        for i, e in enumerate(arcs):
            r = q0 + 1 + i; a_ = max(e["s0"], c.SA); b_ = min(e["s1"], c.SB)
            put(h, f"A{r}", e["no"], BLUE); put(h, f"B{r}", abs(e["R0"]), BLUE, "0.00"); put(h, f"C{r}", "desna" if e["R0"] > 0 else "lijeva", BLUE)
            put(h, f"D{r}", round(a_, 3), BLUE, "0.000"); put(h, f"E{r}", round(b_, 3), BLUE, "0.000")
            put(h, f"F{r}", f"=INDEX({ug}!$I${U['e0']}:$I${U['e1']},MATCH(A{r},{ug}!$A${U['e0']}:$A${U['e1']},0))", GREEN, "0.0")
            put(h, f"G{r}", f'=_xlfn.MINIFS({rg},{ag},">="&D{r},{ag},"<="&E{r})', GREEN, "0.0")
            put(h, f"H{r}", f"=MIN(7,MAX(2.5,7*(INDEX({Pm}$B${T1}:$B${T1e},MATCH({Pm}$B$4,{Pm}$A${T1}:$A${T1e},0))/B{r})^0.74))", BLK, "0.000")
            put(h, f"I{r}", f"=ROUND(H{r},1)", BLK, "0.0")
            put(h, f"J{r}", f'=ABS(AVERAGEIFS(Profil_{c.key}!$N${R0}:$N${R1},{ag},">="&(D{r}+0.25*(E{r}-D{r})),{ag},"<="&(E{r}-0.25*(E{r}-D{r}))))', GREEN, "0.0")
            put(h, f"K{r}", f'=IF(ROUND(J{r},1)>=I{r}-1E-9,"zadovoljava","NE ZADOVOLJAVA")')
            mm = f"MATCH(G{r},{Pm}$A${T1}:$A${T1e},1)"
            put(h, f"L{r}", f"=IF(G{r}<={Pm}$A${T1},{Pm}$D${T1},IF(G{r}>={Pm}$A${T1e},{Pm}$D${T1e},INDEX({Pm}$D${T1}:$D${T1e},{mm})+(G{r}-INDEX({Pm}$A${T1}:$A${T1e},{mm}))*(INDEX({Pm}$D${T1}:$D${T1e},{mm}+1)-INDEX({Pm}$D${T1}:$D${T1e},{mm}))/(INDEX({Pm}$A${T1}:$A${T1e},{mm}+1)-INDEX({Pm}$A${T1}:$A${T1e},{mm}))))", BLK, "0.000")
            put(h, f"M{r}", f"=MAX(2.5,(G{r}^2/(127*B{r})-L{r})*100)", BLK, "0.00"); put(h, f"N{r}", f"=G{r}^2/(127*B{r})-J{r}/100", BLK, "0.000")
            put(h, f"O{r}", f'=IF(N{r}<=L{r}+1E-9,"zadovoljava","NE ZADOVOLJAVA")')
            put(h, f"P{r}", f"=INDEX({Pm}$B${T1}:$B${T1e},MATCH({Pm}$B$4,{Pm}$A${T1}:$A${T1e},0))", GREEN, "0"); put(h, f"Q{r}", f'=IF(B{r}>=P{r},"da","NE – R < R_min(Vr)")')
        for cc in "ABCDEFGHIJKLMNOPQ": h.column_dimensions[cc].width = 15
    # ------------------------------------------------------------ Statistika
    s = wb.create_sheet("Statistika"); put(s, "A1", _T('STATISTIKA REZULTIRAJUĆIH PROFILA BRZINE'), BOLD)
    hdr(s, 3, [_T('Dionica / vozilo'), "Vp,sr [km/h]", "σ [km/h]", "Dh = σ/Vp,sr [%]", "V_min [km/h]", "V_max [km/h]", "Vrijeme [s]", "Vrijeme [min]", "Gorivo [l]", "Gorivo [l/km]", "L [m]", "∫V ds", "∫V² ds"]); s.row_dimensions[3].height = 40
    vehlab = [_T('putničko')] + [v["kratko"].lower() for v in P.vozila]
    SROW = {}
    def statrow(r, label, sheet, col, key, timecell, fuelcell=None):
        N = PROF[key]["N"]; R1 = R0 + N - 1
        r1 = f"{sheet}!${col}${R0}:${col}${R1 - 1}"; r2 = f"{sheet}!${col}${R0 + 1}:${col}${R1}"; full = f"{sheet}!${col}${R0}:${col}${R1}"
        dsr = f"Profil_{key}!$B${R0 + 1}:$B${R1}"
        put(s, f"A{r}", label); put(s, f"K{r}", f"=Profil_{key}!$F$3-Profil_{key}!$D$3", GREEN, "0.000")
        put(s, f"L{r}", f"=SUMPRODUCT(({r1}+{r2})/2*{dsr})", GREEN, "0.0"); put(s, f"M{r}", f"=SUMPRODUCT(({r1}^2+{r2}^2)/2*{dsr})", GREEN, "0.0")
        put(s, f"B{r}", f"=L{r}/K{r}", BLK, "0.00"); put(s, f"C{r}", f"=SQRT(M{r}/K{r}-B{r}^2)", BLK, "0.000"); put(s, f"D{r}", f"=C{r}/B{r}*100", BLK, "0.00")
        put(s, f"E{r}", f"=MIN({full})", GREEN, "0.0"); put(s, f"F{r}", f"=MAX({full})", GREEN, "0.0"); put(s, f"G{r}", timecell, GREEN, "0.0"); put(s, f"H{r}", f"=G{r}/60", BLK, "0.00")
        if fuelcell: put(s, f"I{r}", fuelcell, GREEN, "0.00"); put(s, f"J{r}", f"=I{r}/(K{r}/1000)", BLK, "0.000")
    rr = 4
    for c in cases:
        N = PROF[c.key]["N"]; R1 = R0 + N - 1
        statrow(rr, _TF('{0} – putničko', c.label), f"Profil_{c.key}", "K", c.key, f"=SUM(Profil_{c.key}!L{R0 + 1}:L{R1})"); SROW[(c.key, 0)] = rr; rr += 1
        for k in range(nveh):
            t = TRS[(c.key, k)]
            statrow(rr, f"{c.label} – {vehlab[k + 1]}", t["sn"], "O", c.key, f"={t['sn']}!M{t['end']}", f"={t['sn']}!N{t['end']}"); SROW[(c.key, k + 1)] = rr; rr += 1
    rr += 1; put(s, f"A{rr}", _T('UKUPNO PO SMJERU VOŽNJE (lanac sekcija)'), BOLD); rr += 1
    hdr(s, rr, [_T('Smjer / vozilo'), "Vp,sr [km/h]", "σ [km/h]", "Dh [%]", "V_min [km/h]", "V_max [km/h]", "Vrijeme [s]", "Vrijeme [min]", "Gorivo [l]", "Gorivo [l/km]", "L [m]", "∫V ds", "∫V² ds"]); rr += 1
    RROW = {}
    for tag, lab, chn in (("F", _T('Smjer stacionaže'), fw), ("B", _T('Suprotno smjeru stacionaže'), bw)):
        if not chn: continue
        for v in range(nveh + 1):
            rws = [SROW[(c.key, v)] for c in chn]
            put(s, f"A{rr}", f"{lab} – {vehlab[v]}")
            put(s, f"K{rr}", "=" + "+".join(f"K{x}" for x in rws), BLK, "0.000"); put(s, f"L{rr}", "=" + "+".join(f"L{x}" for x in rws), BLK, "0.0"); put(s, f"M{rr}", "=" + "+".join(f"M{x}" for x in rws), BLK, "0.0")
            put(s, f"B{rr}", f"=L{rr}/K{rr}", BLK, "0.00"); put(s, f"C{rr}", f"=SQRT(M{rr}/K{rr}-B{rr}^2)", BLK, "0.000"); put(s, f"D{rr}", f"=C{rr}/B{rr}*100", BLK, "0.00")
            put(s, f"E{rr}", "=MIN(" + ",".join(f"E{x}" for x in rws) + ")", BLK, "0.0"); put(s, f"F{rr}", "=MAX(" + ",".join(f"F{x}" for x in rws) + ")", BLK, "0.0")
            put(s, f"G{rr}", "=" + "+".join(f"G{x}" for x in rws), BLK, "0.0"); put(s, f"H{rr}", f"=G{rr}/60", BLK, "0.00")
            if v > 0: put(s, f"I{rr}", "=" + "+".join(f"I{x}" for x in rws), BLK, "0.00"); put(s, f"J{rr}", f"=I{rr}/(K{rr}/1000)", BLK, "0.000")
            RROW[(tag, v)] = rr; rr += 1
    for cc in "ABCDEFGHIJKLM": s.column_dimensions[cc].width = 16
    s.column_dimensions["A"].width = 70
    put(s, f"A{rr + 1}", _T('σ = √(∫V²ds/L − Vp,sr²) (algebarski jednako ∫(V−Vp,sr)²ds/L za trapeznu integraciju). Vrijeme = Σ Δs/v.'), BLK)
    # ------------------------------------------------------------ Rezime
    z = wb.create_sheet("Rezime"); put(z, "A1", _T('REZIME REZULTATA (veze na list Statistika)'), BOLD)
    colsz = [(c.shortname + f" [{c.SA:.0f}–{c.SB:.0f}]", c.key) for c in cases]
    heads = [_T('Pokazatelj / vozilo')] + [x[0] for x in colsz] + ([_T('Cijela trasa →')] if fw else []) + ([_T('Cijela trasa ←')] if bw else [])
    hdr(z, 3, heads); z.row_dimensions[3].height = 40
    labs = [("Vp,sr [km/h]", "B", "0.0"), ("σ [km/h]", "C", "0.00"), ("Dh [%]", "D", "0.00"), ("V_min [km/h]", "E", "0.0"), ("V_max [km/h]", "F", "0.0"), ("Vrijeme [min]", "H", "0.00"), ("Gorivo [l]", "I", "0.00"), ("Gorivo [l/km]", "J", "0.000")]
    rz = 4
    for v in range(nveh + 1):
        put(z, f"A{rz}", vehlab[v].upper(), BOLD); rz += 1
        for lab, colx, fmt in labs:
            if v == 0 and colx in "IJ": continue
            put(z, f"A{rz}", lab)
            for j, (cn, key) in enumerate(colsz): put(z, f"{CL(2 + j)}{rz}", f"=Statistika!{colx}{SROW[(key, v)]}", GREEN, fmt)
            jj = 2 + len(colsz)
            if fw: put(z, f"{CL(jj)}{rz}", f"=Statistika!{colx}{RROW[('F', v)]}", GREEN, fmt); jj += 1
            if bw: put(z, f"{CL(jj)}{rz}", f"=Statistika!{colx}{RROW[('B', v)]}", GREEN, fmt)
            rz += 1
    z.column_dimensions["A"].width = 26
    for cc in range(2, 2 + len(heads)): z.column_dimensions[CL(cc)].width = 18
    # ------------------------------------------------------------ Prilozi_A
    pa = wb.create_sheet("Prilozi_A"); put(pa, "A1", _T('PRILOZI A – profili brzina na koraku od svaka 10 tačaka mreže (veze na Profil_* i Voz*_*)'), BOLD)
    rowp = 3
    for c in cases:
        N = c.N; put(pa, f"A{rowp}", c.label, BOLD); rowp += 1
        hdr(pa, rowp, ["s [m]", "z [m]", "i [%]", "R [m]", "Vp [km/h]"] + [f"V {v['kratko']} [km/h]" for v in P.vozila] + [f"t {P.vozila[0]['kratko']} [s]", f"B {P.vozila[0]['kratko']} [l]"]); rowp += 1
        for i in list(range(0, N, 10)) + [N - 1]:
            r = R0 + i; t0 = TRS[(c.key, 0)]["sn"]
            vals = [(f"=Profil_{c.key}!A{r}", "0"), (f"=Profil_{c.key}!C{r}", "0.00"), (f"=Profil_{c.key}!D{r}", "0.00"), (f"=Profil_{c.key}!E{r}", "0"), (f"=Profil_{c.key}!K{r}", "0.0")]
            vals += [(f"=Voz{k + 1}_{c.key}!O{r}", "0.0") for k in range(nveh)] + [(f"={t0}!M{r}", "0"), (f"={t0}!N{r}", "0.00")]
            for j, (f, fmt) in enumerate(vals): put(pa, f"{CL(1 + j)}{rowp}", f, GREEN, fmt)
            rowp += 1
        rowp += 2
    for cc in range(1, 12): pa.column_dimensions[CL(cc)].width = 16
    # ------------------------------------------------------------ Plan_podaci
    pl = wb.create_sheet("Plan_podaci"); put(pl, "A1", _T('SITUACIONI PLAN – koordinate osovina (Y, X) integrisane iz elemenata (vrijednosti, ≈10 m); služe za dijagram plana'), BOLD)
    col = 1; PLAN = {}
    for a in axes:
        lo = min(c.SA for c in cases if c.axis is a); hi = max(c.SB for c in cases if c.axis is a)
        arr = a.plan[::2]; arr = arr[(arr[:, 0] >= lo - 20) & (arr[:, 0] <= hi + 20)]
        hdr(pl, 3, [f"{a.name} s [m]", f"{a.name} Y [m]", f"{a.name} X [m]"], col)
        for i, (x1, y1, z1) in enumerate(arr):
            pl.cell(4 + i, col, float(x1)).font = BLK; pl.cell(4 + i, col + 1, float(y1)).font = BLK; pl.cell(4 + i, col + 2, float(z1)).font = BLK
        PLAN[id(a)] = (col, 4, 3 + len(arr)); col += 4
    for cc in range(1, col): pl.column_dimensions[CL(cc)].width = 14
    # ------------------------------------------------------------ Dijagrami
    dg = wb.create_sheet("Dijagrami"); put(dg, "A1", _T('DIJAGRAMI (isti kao slike u elaboratu) – ažuriraju se automatski'), BOLD)
    def mkchart(title, xt, yt, ymin=None, ymax=None, w=24, h=11):
        ch = ScatterChart(); ch.title = title; ch.style = 13; ch.x_axis.title = xt; ch.y_axis.title = yt
        ch.x_axis.delete = False; ch.y_axis.delete = False; ch.width = w; ch.height = h
        if ymin is not None: ch.y_axis.scaling.min = ymin
        if ymax is not None: ch.y_axis.scaling.max = ymax
        ch.x_axis.tickLblPos = "low"; ch.x_axis.number_format = "0"; ch.y_axis.number_format = "0"; ch.legend.position = "b"; return ch
    def addser(ch, sheet, xcol, ycol, name, key, color=None, dash=None, width=1.5):
        wsx = wb[sheet]; r2 = R0 + PROF[key]["N"] - 1
        x = Reference(wsx, min_col=xcol, min_row=R0, max_row=r2); y = Reference(wsx, min_col=ycol, min_row=R0, max_row=r2)
        se = Series(y, x, title=name); se.marker.symbol = "none"; se.smooth = False; se.graphicalProperties.line.width = int(width * 12700)
        if color: se.graphicalProperties.line.solidFill = color
        if dash: se.graphicalProperties.line.dashStyle = dash
        ch.series.append(se)
    pos = [3]
    def place(ch): dg.add_chart(ch, f"A{pos[0]}"); pos[0] += 24
    ch = mkchart(_T('Situacioni plan osovina'), "Y [m]", "X [m]", w=24, h=14)
    for i, a in enumerate(axes):
        c0, ra, rb = PLAN[id(a)]; x = Reference(pl, min_col=c0 + 1, min_row=ra, max_row=rb); y = Reference(pl, min_col=c0 + 2, min_row=ra, max_row=rb)
        se = Series(y, x, title=a.name); se.marker.symbol = "none"; se.graphicalProperties.line.solidFill = PAL[i % 10]; se.graphicalProperties.line.width = 19050; ch.series.append(se)
    place(ch)
    first_case = {}
    for c in cases:
        if (id(c.axis), c.SA) not in first_case: first_case[(id(c.axis), c.SA)] = c
    base = list(first_case.values())
    for title, ycol, yt in ((_T('Uzdužni profil nivelete'), 3, "Kota [m n.m.]"), (_T('Podužni nagib nivelete'), 4, _T('Nagib [%]')), (_T('Krivina 1000/R (+ desno, − lijevo)'), 13, "1000/R [1/km]")):
        ch = mkchart(title, _T('Stacionaža [m]'), yt)
        for i, c in enumerate(base): addser(ch, f"Profil_{c.key}", 1, ycol, f"{c.axis.name} [{c.SA:.0f}–{c.SB:.0f}]", c.key, PAL[i % 10], width=1.3)
        place(ch)
    ch = mkchart(_T('Poprečni nagib kolovoza (lijeva i desna strana)'), _T('Stacionaža [m]'), _T('Nagib [%]'))
    for i, c in enumerate(base):
        addser(ch, f"Profil_{c.key}", 1, 14, f"{c.axis.name} – lijeva", c.key, PAL[i % 10], width=1); addser(ch, f"Profil_{c.key}", 1, 17, f"{c.axis.name} – desna", c.key, PAL[i % 10], "dash", 1)
    place(ch)
    for tag, chn, lab in (("F", fw, _T('smjer stacionaže')), ("B", bw, _T('suprotno smjeru stacionaže'))):
        if not chn: continue
        ch = mkchart(_TF('Rezultirajući profil Vp – putničko vozilo – {0}', lab), _T('Stacionaža [m]'), _T('Brzina [km/h]'), ymin=40, ymax=P.maxVr + 5)
        for i, c in enumerate(chn):
            addser(ch, f"Profil_{c.key}", 1, 9, f"Cilj T – {c.key}", c.key, "999999", "dash", 1); addser(ch, f"Profil_{c.key}", 1, 11, f"Vp – {c.shortname} [{c.SA:.0f}–{c.SB:.0f}]", c.key, PAL[i % 10], width=1.8)
        addser(ch, f"Profil_{chn[0].key}", 1, 15, f"Vr = {P.Vr:g} km/h", chn[0].key, "FF0000", "sysDot", 1); place(ch)
        ch = mkchart(_TF('Brzine teških vozila – {0}', lab), _T('Stacionaža [m]'), _T('Brzina [km/h]'), ymin=30, ymax=P.maxVr + 5)
        for i, c in enumerate(chn):
            addser(ch, f"Profil_{c.key}", 1, 11, _TF('Putničko – {0}', c.key), c.key, "999999", width=1)
            for k in range(nveh): addser(ch, TRS[(c.key, k)]["sn"], 1, 15, f"{P.vozila[k]['kratko']} – {c.key}", c.key, PAL[i % 10], "dash" if k else None, 1.8 - 0.3 * k)
        place(ch)
    for k in range(nveh):
        for ycol, ttl, yt in ((13, "Kumulativno vrijeme putovanja", "Vrijeme [s]"), (14, _T('Kumulativna potrošnja goriva'), "Gorivo [l]")):
            ch = mkchart(_TF('{0} – {1} (po sekciji, od ulaza u sekciju)', ttl, P.vozila[k]['kratko']), _T('Stacionaža [m]'), yt)
            for i, c in enumerate(cases): addser(ch, TRS[(c.key, k)]["sn"], 1, ycol, c.key, c.key, PAL[i % 10])
            place(ch)
    for c in cases:
        p = wb[f"Profil_{c.key}"]; ch = mkchart(_TF('Profil brzina – {0}', c.label), _T('Stacionaža [m]'), _T('Brzina [km/h]'), ymin=30, ymax=P.maxVr + 5, w=26, h=12)
        addser(ch, f"Profil_{c.key}", 1, 11, _T('Putničko Vp'), c.key, "000000", width=1.8)
        for k in range(nveh): addser(ch, TRS[(c.key, k)]["sn"], 1, 15, P.vozila[k]["kratko"], c.key, PAL[k % 10], "dash" if k else None)
        addser(ch, f"Profil_{c.key}", 1, 15, "Vr", c.key, "FF0000", "sysDot", 1); p.add_chart(ch, "S3")
    order = ["Pretpostavke", "Oznake", "Parametri", "Rezime", "Statistika", "Dijagrami"] + [f"Ulaz_{axid[id(a)]}" for a in axes]
    for c in cases: order += [f"Profil_{c.key}"] + [f"Voz{k + 1}_{c.key}" for k in range(nveh)] + [f"Provjere_{c.key}"]
    order += ["Prilozi_A", "Plan_podaci"]
    wb._sheets = [wb[n] for n in order]
    wb.calculation.fullCalcOnLoad = True
    if stamp: wb.properties.description = _TF('UNA licenca {0}', stamp['id']); wb.properties.keywords = f"lic:{stamp['id']}"
    wb.save(path); log(_TF('Excel sačuvan: {0} ({1} listova)', path, len(order)))
    return dict(SROW=SROW, RROW=RROW, TRS=TRS, PROF=PROF)
