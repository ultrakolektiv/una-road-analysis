"""DXF crteži preglednosti: osovina puta, ivice kolovoza (crvene, debljine 0,3 mm na papiru), osovine vozne trake (obje strane osovine),
zrake, omotač / prepreke, stacionaže i legenda. Tri crteža: Vp, zahtijevana (L zadaje korisnik) i očekivana (prepreke po elementima trase)."""
from .i18n import _T, _TF, TrDict, tr_obj
import math, datetime, textwrap
import numpy as np
from .dxf import Dxf
from . import preglednost as pg

# boje po tragu (smjer_strana): osovina trake, zrake, omotač
PAL = {"F_D": (5, 3, 30), "F_L": (150, 4, 40), "B_D": (6, 82, 202), "B_L": (200, 74, 210)}
TNAME = TrDict({"F": "smjer rastuće stacionaže", "B": "suprotno smjeru stacionaže", "D": "traka desno od osovine", "L": "traka lijevo od osovine"})
TITLES = TrDict({"vp": "ZAHTIJEVANA PREGLEDNOST Pzp NA OSNOVU PROJEKTNE BRZINE Vp (V85) I NAGIBA", "zaht": "ZAHTIJEVANA PREGLEDNOST (zadana dužina zrake)", "ocek": "OČEKIVANA (RASPOLOŽIVA) PREGLEDNOST", "vr": "PREGLEDNOST ZA RAČUNSKU BRZINU Vr"})
FILES = TrDict({"vp": "Preglednost_Vp", "zaht": "Preglednost_zahtijevana", "ocek": "Preglednost_ocekivana", "vr": "Preglednost_Vr"})


def A_has_ob(R): return bool(R["A"]["has_ob"])


def kmfmt(s):
    k = int(s // 1000); m = s - 1000 * k
    return f"{k}+{m:03.0f}"


def tname(k): return f"{TNAME[k[0]]}, {TNAME[k[2]]}"


def case_polys(ch, A):
    """Polilinije osovine vozne trake po slučaju (prekid na spoju sekcija)."""
    out = []; ci = A["ci"]; start = 0
    for k in list(np.where(np.diff(ci) != 0)[0] + 1) + [len(ci)]:
        out.append((ci[start], list(zip(A["x"][start:k], A["y"][start:k])))); start = k
    return out


def _runs(xs, ys):
    """Polilinije iz nizova sa NaN prekidima."""
    out = []; cur = []
    for a, b in zip(xs, ys):
        if math.isnan(a):
            if len(cur) > 1: out.append(cur)
            cur = []
        else: cur.append((a, b))
    if len(cur) > 1: out.append(cur)
    return out


def draw(P, cases, par, res, cfg, path, mode="vp", log=print, preview_png=None, title=None):
    u = par["mjerilo"] / 1000.0            # metara na crtežu po 1 mm papira
    d = Dxf(ltscale=u * 1.0)
    base = [(_T('OSOVINA_PUTA'), 8, "CONTINUOUS"), ("IVICA_KOLOVOZA", 1, "CONTINUOUS"), ("STACIONAZA", 7, "CONTINUOUS"), ("TEKST_ZRAKA", 8, "CONTINUOUS"),
            ("LEGENDA", 7, "CONTINUOUS"), ("OKVIR_LEGENDE", 7, "CONTINUOUS")]
    with_ob = par["ima_prepreke"]
    if with_ob or mode == "ocek": base += [("PREPREKA_DESNO", 52, "CONTINUOUS"), ("PREPREKA_LIJEVO", 53, "CONTINUOUS")]
    if mode == "ocek": base += [("ZRAKE_NEDOVOLJNO", 240, "CONTINUOUS"), ("OZNAKE_NEDOVOLJNO", 240, "CONTINUOUS"), ("DODIR_PREPREKA", 6, "CONTINUOUS")]
    else: base += [("ZRAKE_VERT_NEDOVOLJNO", 240, "CONTINUOUS"), ("ZRAKE_HOR_NEDOVOLJNO", 12, "CONTINUOUS"), ("OMOTAC_OZNAKE", 7, "CONTINUOUS")]
    LAY = list(base)
    for k in res:
        t, r, e = PAL[k]
        LAY += [(_TF('OSOVINA_TRAKE_{0}', k), t, "CONTINUOUS"), (f"ZRAKE_{k}", r, "CONTINUOUS")]
        if mode != "ocek": LAY.append((f"OMOTAC_{k}", e, "DASHED"))
    for n, c, lt in LAY: d.layer(n, c, lt)
    H = 2.5 * u
    # --- osovine puta + stacionaže; ivice kolovoza
    seen = set(); seen_e = set()
    for c in cases:
        key = (id(c.axis), c.SA, c.SB)
        if key not in seen:
            seen.add(key); S, Y, X, NU = pg.dense_plan(c.axis); m = (S >= c.SA - 1e-6) & (S <= c.SB + 1e-6)
            pts = list(zip(Y[m], X[m])); d.poly(_T('OSOVINA_PUTA'), pts[::2] if len(pts) > 4000 else pts)
            for s0 in np.arange(math.ceil(c.SA / 100) * 100, c.SB + 1e-6, 100):
                i = int(np.argmin(abs(S - s0))); x, y, nu = Y[i], X[i], NU[i]
                tx, ty = math.sin(nu), math.cos(nu); nx, ny = -ty, tx
                L = 5 * u if s0 % 500 else 9 * u
                d.line("STACIONAZA", x - nx * L, y - ny * L, x + nx * L, y + ny * L)
                if s0 % 500 == 0 or par["mjerilo"] <= 2000:
                    ang = math.degrees(math.atan2(ty, tx))
                    if ang > 90 or ang < -90: ang += 180
                    d.text("STACIONAZA", x + nx * (L + 1.0 * u), y + ny * (L + 1.0 * u), H, "km " + kmfmt(s0), rot=ang, align="c")
        ek = (id(c.axis), c.SA, c.SB, c.role, c.sec["no"])
        if par["ivice"] and ek not in seen_e:
            seen_e.add(ek); pr = pg.case_prof(c, par); n = max(2, int(round((c.SB - c.SA) / 2.0)) + 1); s = np.linspace(c.SA, c.SB, n)
            x0, y0, nx, ny = pg.case_frame(c, par, s)
            lats = [pr["eR"], -pr["eL"]] + ([pr["gR"]] if pr["gR"] > 0 else []) + ([-pr["gL"]] if pr["gL"] > 0 else [])      # vanjske + unutrašnje ivice (razdjelni pojas)
            for lat in lats:
                d.poly("IVICA_KOLOVOZA", list(zip(y0 + lat * ny, x0 + lat * nx)), width=par["ivica_debljina"] * u)
    if with_ob:
        seen_o = set()
        for c in cases:
            ok_ = (id(c.axis), c.SA, c.SB, c.role, c.sec["no"])
            if ok_ in seen_o: continue
            seen_o.add(ok_); pr = pg.case_prof(c, par); n = max(2, int(round((c.SB - c.SA) / 1.0)) + 1); s = np.linspace(c.SA, c.SB, n)
            x0, y0, nx, ny = pg.case_frame(c, par, s); oR, oL = pg.obstacle_offsets(c, par, s)
            for o, lat, lay in ((oR, pr["eR"] + oR, "PREPREKA_DESNO"), (oL, -(pr["eL"] + oL), "PREPREKA_LIJEVO")):
                xs = np.where(np.isnan(o), np.nan, y0 + lat * ny); ys = np.where(np.isnan(o), np.nan, x0 + lat * nx)
                for run in _runs(xs, ys): d.poly(lay, run, width=0.15 * u)
    # --- tragovi
    for ti, R in enumerate(res.values()):
        A = R["A"]; ch = R["chain"]; k = R["key"]
        for ci, pts in case_polys(ch, A): d.poly(_TF('OSOVINA_TRAKE_{0}', k), pts)
        nxt = 0.0; lab_next = 60.0 * ti; x, y, xa, ya = A["x"], A["y"], A["xa"], A["ya"]
        lay_bad = "ZRAKE_NEDOVOLJNO" if mode == "ocek" else "ZRAKE_VERT_NEDOVOLJNO"
        for ri, r in enumerate(R["rows"]):
            if r["q"] + 1e-6 < nxt: continue
            nxt = r["q"] + par["korak_crtez"]
            a, b = r["i"], r["b"]
            ex = x[a] + (xa[b] - xa[a]); ey = y[a] + (ya[b] - ya[a])
            lay_r = lay_bad if not r["ok"] else f"ZRAKE_{k}"
            if mode != "ocek" and R.get("avail"):
                av = R["avail"]["rows"][ri]
                if not av["okV"] or not r["ok"]: lay_r = "ZRAKE_VERT_NEDOVOLJNO"
                elif A["has_ob"] and not av["okH"]: lay_r = "ZRAKE_HOR_NEDOVOLJNO"
            d.line(lay_r, x[a], y[a], ex, ey)
            if mode == "ocek" and r.get("kc") is not None:                  # dodirna tačka zrake i prepreke
                kc = r["kc"]; cx_ = x[a] + (A["obrxa"][kc] - xa[a]) if np.isfinite(A["obrxa"][kc]) else x[a] + (A["oblxa"][kc] - xa[a])
                cy_ = y[a] + (A["obrya"][kc] - ya[a]) if np.isfinite(A["obrxa"][kc]) else y[a] + (A["oblya"][kc] - ya[a])
                d.circle("DODIR_PREPREKA", cx_, cy_, 0.8 * u)
            if r["q"] >= lab_next:
                lab_next = r["q"] + 240.0
                mx, my = (x[a] + ex) / 2, (y[a] + ey) / 2; ang = math.degrees(math.atan2(ey - y[a], ex - x[a]))
                if ang > 90 or ang < -90: ang += 180
                if mode == "vp": tx_ = f"Lz={r['Lz']:.0f} m (Vp={r['V']:.0f}, i={r['g']:+.1f}%)"
                elif mode == "vr": tx_ = f"Pz={r['Lz']:.0f} m (Vr={(r.get('vr') or par['Vr']):g}, i={r['g']:+.1f}%)"
                elif mode == "zaht": tx_ = f"Pzp={r['Lz']:.0f} m" + ("" if par["L_zahtijevano"] else f" (Vp={r['V']:.0f})")
                else: tx_ = _TF('raspoloživo {0:.0f} m (potrebno {1:.0f} m)', r['D'], r['Lz'])
                d.text("TEKST_ZRAKA", mx, my, 0.8 * H, tx_, rot=ang, align="c")
        if mode == "ocek":
            for b_ in R["deficits"][:60]:                      # oznaka na mjestu najmanje preglednosti u rasponu
                rr = [r for r in R["rows"] if b_["s0"] - 1e-6 <= r["s"] <= b_["s1"] + 1e-6 and not r["ok"]] or R["rows"][:1]
                r = min(rr, key=lambda t: t["D"]); a = r["i"]
                d.text("OZNAKE_NEDOVOLJNO", x[a], y[a] + 2.5 * u, 0.9 * H, f"km {kmfmt(r['s'])}: {r['D']:.0f} m < {r['Lz']:.0f} m ({r['lim']})", rot=0, align="c")
            continue
        # omotač (potreban slobodni prostor desno/lijevo od osovine trake)
        rn_x, rn_y = A["ty"], -A["tx"]
        for name, m, sgn in (("R", R["mR"], +1), ("L", R["mL"], -1)):
            run = []
            for q in range(len(m)):
                if m[q] > 0.05 and not (q > 0 and A["ci"][q] != A["ci"][q - 1] and run):
                    run.append((x[q] + sgn * m[q] * rn_x[q], y[q] + sgn * m[q] * rn_y[q]))
                else:
                    if len(run) > 1: d.poly(f"OMOTAC_{k}", run)
                    run = [(x[q] + sgn * m[q] * rn_x[q], y[q] + sgn * m[q] * rn_y[q])] if m[q] > 0.05 else []
            if len(run) > 1: d.poly(f"OMOTAC_{k}", run)
            taken = []
            for q in np.argsort(-m):
                if m[q] < 1.0: break
                if all(abs(A["q"][q] - A["q"][t]) > 150 for t in taken):
                    taken.append(q)
                    px, py = x[q] + sgn * m[q] * rn_x[q], y[q] + sgn * m[q] * rn_y[q]
                    d.line("OMOTAC_OZNAKE", x[q], y[q], px, py)
                    ang = math.degrees(math.atan2(A["ty"][q], A["tx"][q]))
                    if ang > 90 or ang < -90: ang += 180
                    d.text("OMOTAC_OZNAKE", px + sgn * 1.2 * u * rn_x[q], py + sgn * 1.2 * u * rn_y[q], H, f"m={m[q]:.2f} m (km {kmfmt(A['s'][q])})", rot=ang, align="c")
    # --- legenda
    x0, y0, x1, y1 = d.ext
    W = 200 * u; proj = cfg.get("projekat", "")
    ly = {n: (c, lt) for n, c, lt in LAY}
    items = []
    def T_(t, ind=4, h=H, gap=6.5):
        for q, w_ in enumerate(textwrap.wrap(t, max(20, int((W - (ind + 6) * u) / (0.75 * h))))): items.append(("t", w_, ind if q == 0 else ind + 3, h, gap))
    ttl = (title or TITLES[mode]) + ((f" – L = {par['L_zahtijevano']:.0f} m" if par["L_zahtijevano"] else " – Pzp") if mode == "zaht" else "")
    items.append(("t", "LEGENDA – " + ttl, 4, 3.5 * u, 8))
    T_(_TF('Dionica: {0}   |   Računska brzina Vr = {1:g} km/h; Vp = V85 iz Elaborata 3 (a = d = {2:g} m/s²)', proj, P.Vr, P.a), gap=7)
    items.append(("sep",))
    ent = [(_T('OSOVINA_PUTA'), _T('Osovina puta (stacionaže svakih 100 m, oznaka na 500 m)'))]
    if par["ivice"]: ent.append(("IVICA_KOLOVOZA", _TF('Ivica kolovoza (crvena linija debljine {0:g} mm na papiru; širine traka zadaje korisnik)', par['ivica_debljina'])))
    for k in res:
        ent.append((_TF('OSOVINA_TRAKE_{0}', k), _TF('Osovina oka vozača – {0}', tname(k))))
        ent.append((f"ZRAKE_{k}", f"Zrake – {tname(k)} (svakih {par['korak_crtez']:.0f} m)"))
        if mode != "ocek": ent.append((f"OMOTAC_{k}", f"Granica slobodnog prostora – {tname(k)}"))
    if with_ob and mode != "ocek": ent += [("PREPREKA_DESNO", _T('Prepreka desno od osovine puta (ofset od ivice kolovoza)')), ("PREPREKA_LIJEVO", _T('Prepreka lijevo od osovine puta (ofset od ivice kolovoza)'))]
    if mode == "ocek":
        ent += [("DODIR_PREPREKA", _T('Dodirna tačka zrake i linije prepreke (zraka je tu najduža moguća)')), ("PREPREKA_DESNO", _T('Prepreka desno od osovine puta (ofset od ivice kolovoza)')), ("PREPREKA_LIJEVO", _T('Prepreka lijevo od osovine puta (ofset od ivice kolovoza)')),
                ("ZRAKE_NEDOVOLJNO", _T('Zraka sa raspoloživom preglednošću manjom od potrebne (prepreka ili niveleta)'))]
    else:
        ent.append(("ZRAKE_VERT_NEDOVOLJNO", _T('Zraka sa nedovoljnom VERTIKALNOM preglednošću (zaklon nivelete)')))
        if with_ob: ent.append(("ZRAKE_HOR_NEDOVOLJNO", _T('Zraka sa nedovoljnom HORIZONTALNOM preglednošću (prepreka uz kolovoz)')))
    for lay, txt in ent: items.append(("e", lay, txt))
    items.append(("sep",))
    if mode in ("vp", "vr"):
        T_((_TF('Pz = skraćena zaustavna preglednost (Crtež 52, fT50 %) za računsku brzinu Vr = {0:g} km/h (projektni zadatak) i podužni nagib u smjeru vožnje.', par['Vr'])) if mode == "vr" else _T('Lz = skraćena zaustavna preglednost (Smjernice BiH, Crtež 52, fT50 %) u funkciji Vp (V85) i podužnog nagiba u smjeru vožnje; vrijednosti očitane iz dijagrama.') + (_TF(' Na očitanu vrijednost dodato je {0:g} m (dodatak zadao projektant).', par['dodatak_L']) if par["dodatak_L"] else ""))
    elif mode == "zaht":
        if par["L_zahtijevano"]: T_(_TF('Zahtijevana dužina zrake L = {0:.0f} m zadana je od strane projektanta (ne zavisi od Vp ni od nagiba).', par['L_zahtijevano']))
        else: T_(_T('Zahtijevana preglednost Pzp = Lz(Vp) očitana iz Crteža 52 (fT50 %) za projektnu brzinu Vp iz Elaborata 3 u tom presjeku i stvarni podužni nagib niveleta') + (f"; dodato {par['dodatak_L']:g} m." if par["dodatak_L"] else "."))
    else:
        Lt = _TF('zadana dužina L = {0:.0f} m', par['L_zahtijevano']) if par["L_zahtijevano"] else _T('Pzp = Lz(Vp, nagib) (Crtež 52, fT50 %)')
        T_(_TF('Očekivana preglednost = najduža zraka od oka vozača koju dopuštaju prepreka (linija na unesenom ofsetu od krajnje ivice kolovoza, po elementima trase: pravac, prijelaznica, kružni luk) i niveleta. Poređenje sa potrebnom dužinom: {0}.', Lt))
    T_(_TF('Zraka = tetiva od oka vozača (osovina vozne trake) do tačke ispred, mjereno duž osovine vozne trake. Oko {0:.2f} m i predmet {1} iznad nivelete (vertikalna provjera).', par['h_oka'], _T('h2 = 0–0,15 m po Tabeli 29 (zavisi od Vp)') if par.get('h_auto') else format(par['h_prepreke'], '.2f') + ' m'))
    if mode != "ocek": T_(_T('Prostor između osovine trake i granice (isprekidano) mora ostati slobodan od prepreka (usjek, ograda, zelenilo, objekti). m = potreban slobodni prostor od osovine vozne trake; oznake = lokalni maksimumi ≥ 1,0 m.'))
    T_(_T('Poprečni profil (u smjeru stacionaže: širine traka od osovine puta) i ofset osovine oka vozača od osovine kolovoza svog smjera (u smjeru vožnje):'))
    for c in cases:
        pr = pg.case_prof(c, par)
        T_(_TF('{0}  {1}: trake desno {2} m (ivica {3:.2f} m), lijevo {4} m (ivica {5:.2f} m); osovina kolovoza {6:.2f} m od osovine puta; ofset oka desno {7:.2f} m, lijevo {8:.2f} m', c.key, c.short, ', '.join(f'{v:g}' for v in pr['tR']), pr['eR'], ', '.join(f'{v:g}' for v in pr['tL']), pr['eL'], pr['hC'], pr['dDR'], pr['dDL']) + (f"; razdjelni pojas: pola {pr['gR']:.2f} / {pr['gL']:.2f} m" if pr['gR'] or pr['gL'] else ""), ind=8, h=0.9 * H, gap=6)
    for R in res.values():
        rr = R["rows"]; nb = len(R["deficits"]); lab = tname(R["key"])
        if mode == "ocek":
            T_(_TF('{0}: raspoloživo {1} (horizontalno nedovoljno na {2}, vertikalno na {3} mjesta). ', lab, pg.dminmax(rr), len(R['defH']), len(R['defV'])) + (_T('Zadovoljava na cijeloj dužini.') if nb == 0 else _T('NEDOVOLJNO na: ') + "; ".join(
                f"km {kmfmt(min(b['s0'], b['s1']))}–{kmfmt(max(b['s0'], b['s1']))} (min {b['dmin']:.0f} m < {b['need']:.0f} m)" for b in R["deficits"][:8])), ind=8)
        else:
            T_(f"{lab}: Lz {min(r['Lz'] for r in rr):.0f}–{max(r['Lz'] for r in rr):.0f} m; max m desno {R['mR'].max():.2f} m, lijevo {R['mL'].max():.2f} m. Vertikalno: " + ("zadovoljava." if not R["defV"] else _T('NEDOVOLJNO na: ') + "; ".join(
                f"km {kmfmt(min(b['s0'], b['s1']))}–{kmfmt(max(b['s0'], b['s1']))} (min {b['dmin']:.0f} m < {b['need']:.0f} m)" for b in R["defV"][:8])) + (" Horizontalno (prepreke): " + ("zadovoljava." if not R["defH"] else _T('NEDOVOLJNO na: ') + "; ".join(
                f"km {kmfmt(min(b['s0'], b['s1']))}–{kmfmt(max(b['s0'], b['s1']))} (min {b['dmin']:.0f} m < {b['need']:.0f} m)" for b in R["defH"][:8])) if A_has_ob(R) else ""), ind=8)
    items.append(("sep",))
    T_(_TF('Mjerilo crteža {0} (jedinica: m)  |  Koordinate: Y (istok), X (sjever) iz ispisa projektanta  |  Izrada: UNA - ROAD ENGINEERING ANALYSIS  |  {1}', '1:%d' % par['mjerilo'], datetime.date.today().strftime('%d.%m.%Y')), h=0.9 * H, gap=6)
    hh = 4 * u
    for it in items: hh += {"t": it[4] * u if it[0] == "t" else 0, "sep": 3 * u, "e": 7 * u}[it[0]]
    bx0 = x0; by1 = y0 - 40 * u; by0 = by1 - hh
    d.poly("OKVIR_LEGENDE", [(bx0, by0), (bx0 + W, by0), (bx0 + W, by1), (bx0, by1)], closed=True)
    cy = by1 - 3 * u
    for it in items:
        if it[0] == "t":
            _, t, ind, h, gap = it; cy -= gap * u; d.text("LEGENDA", bx0 + ind * u, cy + 1.5 * u, h, t)
        elif it[0] == "sep":
            cy -= 1.5 * u; d.line("OKVIR_LEGENDE", bx0, cy, bx0 + W, cy); cy -= 1.5 * u
        else:
            _, lay, txt = it; col, lt = ly[lay]; cy -= 7 * u
            if lay == "IVICA_KOLOVOZA": d.poly(lay, [(bx0 + 4 * u, cy + 2.5 * u), (bx0 + 24 * u, cy + 2.5 * u)], width=par["ivica_debljina"] * u)
            else: d.line(lay, bx0 + 4 * u, cy + 2.5 * u, bx0 + 24 * u, cy + 2.5 * u, ltype=lt)
            d.text("LEGENDA", bx0 + 28 * u, cy + 1.2 * u, H, txt)
    d.save(path); log(_TF("DXF: {0} ({1} entiteta)", path, len(d.items)))
    if preview_png:
        from .dxf import preview
        preview(d, preview_png)
    return d
