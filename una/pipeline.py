"""Cijeli tok: konfiguracija → proračun → slike → Word + Excel."""
from .i18n import _T, _TF, tr_obj
import os, json, time, traceback
from . import engine, figs, report, xlsx
from .texts import SYM


def validate(cfg):
    errs = []
    if not cfg.get("sekcije"): errs.append("Nije unesena nijedna sekcija.")
    for i, s in enumerate(cfg.get("sekcije", []), 1):
        t = s.get("tip")
        if t not in engine.TIPOVI: errs.append(f"Sekcija {i}: nepoznat tip '{t}'."); continue
        try:
            if float(s["do"]) <= float(s["od"]): errs.append(_TF("Sekcija {0}: 'do' mora biti veće od 'od'.", i))
        except Exception: errs.append(_TF('Sekcija {0}: stacionaže nisu brojevi.', i))
        roles = {"razdvojene": ["desna", "lijeva"], "centralna": ["centralna"], "jedna_naprijed": ['osovina'], "jedna_nazad": ['osovina']}[t]
        for r in roles:
            sp = s.get(r) or {}
            for k in ("h", "v", "x"):
                p = sp.get(k)
                if not p or not os.path.isfile(p): errs.append(_TF("Sekcija {0} ({1}): datoteka '{2}' ne postoji: {3}", i, r, k, p))
    pc = cfg.get("preglednost")
    if pc:
        try:
            from . import preglednost as pgm
            par = pgm.make_par(cfg)
            for j, e in enumerate(par["prepreke"], 1):
                if e.get("tip") not in (None, ""):
                    if e["tip"] not in par["tipovi_prepreka"]: errs.append(_TF("Preglednost, prepreka {0}: tip '{1}' nema upisan ofset (tipovi prepreka).", j, e['tip']))
                elif e.get("ofset") in (None, "") or float(e["ofset"]) < 0: errs.append(_TF('Preglednost, prepreka {0}: zadajte tip prepreke ili ofset od ivice kolovoza (broj ≥ 0).', j))
                if e.get("element") in (None, "") and (e.get("od") in (None, "") or e.get("do") in (None, "")): errs.append(_TF("Preglednost, prepreka {0}: zadajte 'element' ili 'od' i 'do'.", j))
                if e.get("strana", "unutra") not in ("unutra", "vani", "izvana", "desno", "lijevo", "D", "L"): errs.append(_TF('Preglednost, prepreka {0}: strana mora biti unutra / vani / desno / lijevo.', j))
            if not par["strane"]: errs.append(_T('Preglednost: nije odabrana nijedna strana osovine.'))
        except Exception as ex: errs.append(_TF('Preglednost: neispravan unos ({0}).', ex))
        for i, s in enumerate(cfg.get("sekcije", []), 1):
            for r in ("desna", "lijeva", "centralna", 'osovina'):
                sp = s.get(r)
                if not isinstance(sp, dict): continue
                for k in ("trake_desno", "trake_lijevo"):
                    v = sp.get(k)
                    try:
                        if v not in (None, "") and any(float(x) <= 0 for x in (v if isinstance(v, (list, tuple)) else [v])): errs.append(_TF('Sekcija {0} ({1}): širine traka moraju biti > 0.', i, r))
                    except Exception: errs.append(f"Sekcija {i} ({r}): '{k}' mora biti lista brojeva.")
    tp = cfg.get("template") or {}
    if tp.get("file") and not os.path.isfile(tp["file"]): errs.append(f"Word template ne postoji: {tp['file']}")
    secs = sorted(cfg.get("sekcije", []), key=lambda s: float(s.get("od", 0)))
    for a, b in zip(secs, secs[1:]):
        try:
            if float(b["od"]) < float(a["do"]) - 1e-6: errs.append(f"Sekcije se preklapaju: {a['od']}–{a['do']} i {b['od']}–{b['do']}.")
        except Exception: pass
    return errs


def _stamp_docx(path, lic):
    """Upisuje ID licence u svojstva dokumenta (ne vidi se u tekstu)."""
    from . import licenca
    from docx import Document
    s = licenca.stamp(lic); d = Document(path); cp = d.core_properties
    cp.comments = ((cp.comments or "") + _TF(' [UNA licenca {0}]', s['id'])).strip(); cp.keywords = (cp.keywords or "") + f" lic:{s['id']}"
    d.save(path)


def generate(cfg, outdir, log=print, word=True, excel=True, sight=None):
    t0 = time.time()
    from . import licenca, i18n
    i18n.set_lang(cfg.get("jezik", "sr"))
    lic = licenca.require(); log(licenca.describe(lic))
    errs = validate(cfg)
    if errs: raise ValueError("\n".join(errs))
    os.makedirs(outdir, exist_ok=True)
    log(_T('1/4 Učitavanje ispisa i proračun profila brzine …'))
    P, sections, cases, axes, fw, bw, has_caps = engine.run(cfg, log=log)
    secs = sorted(sections, key=lambda s: s["od"])
    for a, b in zip(secs, secs[1:]):
        if abs(b["od"] - a["do"]) > 0.01: log(_TF('UPOZORENJE: sekcije nisu povezane (kraj {0} ≠ početak {1}); brzina se prenosi preko praznine.', a['do'], b['od']))
    for c in cases:
        log(f"  {c.key}: {c.label}: Vp {c.stc['vmin']:.1f}–{c.stc['vmax']:.1f} km/h, Dh = {c.stc['Dh']:.2f} %, vrijeme {c.stc['time']:.1f} s")
    outs = []
    tr = str.maketrans({"č": "c", "ć": "c", "ž": "z", "š": "s", "đ": "dj", "Č": "C", "Ć": "C", "Ž": "Z", "Š": "S", "Đ": "Dj"})
    import re as _re
    name = _re.sub(r"_+", "_", "".join(ch if (ch.isascii() and ch.isalnum()) or ch in "-_" else "_" for ch in cfg.get("projekat", "Projekat").translate(tr)))[:40].strip("_") or "Projekat"
    if word:
        log(_T('2/4 Izrada slika …'))
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            F = figs.make_all(P, sections, cases, axes, fw, bw, has_caps, td, log=log)
            log("3/4 Izrada Word elaborata …")
            p = os.path.join(outdir, _TF("Elaborat_3_Vozno-dinamicke_analize_{0}.docx", name))
            report.write_docx(P, sections, cases, axes, fw, bw, has_caps, F, cfg, p, log=log); _stamp_docx(p, lic); outs.append(p)
            tp = cfg.get("template") or {}
            if tp.get("file"):
                log("3b/4 Izrada Word elaborata prema templatu …")
                p2 = os.path.join(outdir, _TF("Elaborat_3_Vozno-dinamicke_analize_{0}_po_templateu.docx", name))
                report.write_docx_template(P, sections, cases, axes, fw, bw, has_caps, F, cfg, p2, log=log); _stamp_docx(p2, lic); outs.append(p2)
    else:
        report.LAST_REG = []
    if excel:
        log(_T('4/4 Izrada Excel radne knjige sa formulama i dijagramima (može potrajati) …'))
        p = os.path.join(outdir, _TF("Proracun_vozno-dinamicke_analize_{0}.xlsx", name))
        xlsx.build_xlsx(p, P, sections, cases, axes, tr_obj(SYM), report.LAST_REG, has_caps, log=log, stamp=licenca.stamp(lic)); outs.append(p)
    sg_on = sight if sight is not None else bool((cfg.get("preglednost") or {}).get("ukljuci") or (cfg.get("optika") or {}).get("ukljuci"))
    if sg_on:
        log(_T('5/5 Preglednost: zrake, omotač i DXF crtež …'))
        from . import preglednost as pgm, preglednost_crtez as pgc
        par, out_ = pgm.run(P, cases, fw, bw, cfg, log=log)
        png = bool((cfg.get("preglednost") or {}).get("png"))
        for mode, key in (("vp", "vp"), ("vr", "vr"), ("zaht", "zaht"), ("ocek", "ocek")):
            if not out_.get(key): continue
            pd = os.path.join(outdir, f"{pgc.FILES[mode]}_{name}.dxf")
            pgc.draw(P, cases, par, out_[key], cfg, pd, mode=mode, log=log, preview_png=os.path.join(outdir, f"{pgc.FILES[mode]}_{name}_pregled.png") if png else None)
            outs.append(pd)
        from . import preglednost_dijagram as pgd
        for tg in ("F", "B"):
            kk = [k for k, R in out_["vp"].items() if R["tag"] == tg]
            if not kk: continue
            R0 = out_["vp"][kk[0]]
            outs.append(pgd.make_profil_dxf(P, par, [({kk[0]: dict(rows=R0["avail"]["rows"], A=R0["A"])}, _T('VERTIKALNA PREGLEDNOST – raspoloživa, ') + (_T('smjer stacionaže') if tg == "F" else _T('suprotno smjeru stacionaže')), None if par["h_auto"] else par["h_prepreke"])],
                                            os.path.join(outdir, _TF('Preglednost_vertikalna_{0}_{1}.dxf', tg, name)), log=log))
        outs += pgd.make(P, par, out_, outdir, name, log=log)
        outs += pgd.make_vr(P, par, out_, outdir, name, log=log)
        px = os.path.join(outdir, _TF('Preglednost_rezultati_{0}.xlsx', name)); pgm.write_xlsx(px, P, par, out_, cases); log(_TF('Excel (preglednost): {0}', px)); outs.append(px)
        if (cfg.get("optika") or {}).get("ukljuci"):
            log(_T('6/6 Elaborat optičkih analiza (preticajna preglednost, sadržaj grafičkih priloga) …'))
            from . import optika
            o2, _pp = optika.make(P, cases, par, out_, cfg, outdir, name, list(outs), log=log); outs += o2
    log(_TF('Gotovo za {0:.0f} s.', time.time() - t0))
    return outs, (P, sections, cases, axes, fw, bw, has_caps)


def load_cfg(path):
    """Učitava projekat; relativne putanje datoteka računaju se u odnosu na folder JSON-a."""
    cfg = json.load(open(path, encoding="utf-8")); base = os.path.dirname(os.path.abspath(path))
    for s in cfg.get("sekcije", []):
        for r in ("desna", "lijeva", "centralna", 'osovina'):
            sp = s.get(r)
            if isinstance(sp, dict):
                for k in ("h", "v", "x"):
                    if sp.get(k) and not os.path.isabs(sp[k]): sp[k] = os.path.normpath(os.path.join(base, sp[k]))
    tp = cfg.get("template")
    if isinstance(tp, dict) and tp.get("file") and not os.path.isabs(tp["file"]): tp["file"] = os.path.normpath(os.path.join(base, tp["file"]))
    if cfg.get("izlaz") and not os.path.isabs(cfg["izlaz"]): cfg["izlaz"] = os.path.normpath(os.path.join(base, cfg["izlaz"]))
    return cfg
