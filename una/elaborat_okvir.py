"""Formalni okvir elaborata (Word): naslovna strana sa šifrom knjige, obrazac sa podacima o projektu i potpisima,
sadržaj knjige, zaglavlje sa logotipom i potpisni blok na kraju. Uključuje se postavkom cfg["elaborat"] (ne mijenja analizu)."""
import os, re
from .i18n import _T, _TF

POLJA = ("investitor", "projektant", "objekat", "dionica", "lokacija", "faza", "autor_projekta", "odgovorno_lice", "vodeci_projektant",
         "odgovorni_projektant", "saradnici", "mjesto", "datum", "sifra", "sifra_vozna", "sifra_optika", "logo_investitor", "logo_projektant", "adresa_projektanta", "revident")
VRSTE = {"vozna": dict(naslov="ELABORAT VOZNO-DINAMIČKIH ANALIZA", dio="Elaborat vozno-dinamičkih analiza", zag="VOZNO-DINAMIČKE ANALIZE"),
         "optika": dict(naslov="ELABORAT OPTIČKIH ANALIZA TRASE", dio="Elaborat optičkih analiza trase", zag="OPTIČKE ANALIZE")}


def aktivan(cfg):
    e = cfg.get("elaborat")
    return isinstance(e, dict) and e.get("ukljuci", True) is not False and any(str(e.get(k, "")).strip() for k in POLJA)


def _v(e, k, d=""):
    x = e.get(k, d)
    if isinstance(x, (list, tuple)): return "\n".join(str(i) for i in x if str(i).strip())
    return str(x if x is not None else d).strip()


def _sadrzaj(vrsta, n_prilog):
    if vrsta == "vozna":
        return [(_T("TEKSTUALNA DOKUMENTACIJA"), [_T("Tehnički opis (poglavlja 1–7)"), _T("Uslovi obrade i pretpostavke")]),
                (_T("NUMERIČKA DOKUMENTACIJA"), [_TF("Numerički proračun profila brzina, vremena putovanja i potrošnje goriva (prilozi A1–A{0})", max(1, n_prilog))]),
                (_T("GRAFIČKA DOKUMENTACIJA"), [_T("Dijagrami brzina, krivine i nagiba (prilog B)")])]
    return [(_T("TEKSTUALNA DOKUMENTACIJA"), [_T("Tehnički opis"), _T("Zaključak")]),
            (_T("NUMERIČKA DOKUMENTACIJA"), [_T("Zaustavna, zahtijevana i raspoloživa preglednost po stacionaži")]),
            (_T("GRAFIČKA DOKUMENTACIJA"), [_T("Dijagrami preglednosti"), _T("Situacioni prikaz raspoložive preglednosti")])]


def _put(base, p):
    if not p: return None
    p = os.path.expanduser(str(p))
    for c in (p, os.path.join(base or "", p)):
        if os.path.isfile(c): return c
    return None


def apply(d, cfg, vrsta, n_prilog=1, base=None):
    """Umeće naslovnu stranu, obrazac i sadržaj knjige na početak, a potpis na kraj dokumenta d (python-docx Document)."""
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH as AL
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    e = cfg.get("elaborat") or {}; V = VRSTE[vrsta]; body = d.element.body
    sect = body.find(qn("w:sectPr")); new = []
    base = base or cfg.get("_osnova")

    def keep(el): new.append(el); return el
    def para(text="", size=10, bold=False, al=None, after=4, before=0, italic=False, color=None):
        p = d.add_paragraph(); keep(p._p)
        if al is not None: p.alignment = al
        p.paragraph_format.space_after = Pt(after); p.paragraph_format.space_before = Pt(before)
        if text:
            r = p.add_run(text); r.font.size = Pt(size); r.font.name = "Arial"; r.bold = bold; r.italic = italic
            if color: r.font.color.rgb = RGBColor(*color)
        return p
    def pbreak():
        p = d.add_paragraph(); keep(p._p); p.add_run().add_break(__import__("docx").enum.text.WD_BREAK.PAGE); p.paragraph_format.space_after = Pt(0)
    def borders(t, sz=6):
        tblPr = t._tbl.tblPr; b = OxmlElement("w:tblBorders")
        for k in ("top", "left", "bottom", "right", "insideH", "insideV"):
            x = OxmlElement(f"w:{k}"); x.set(qn("w:val"), "single"); x.set(qn("w:sz"), str(sz)); x.set(qn("w:space"), "0"); x.set(qn("w:color"), "444444"); b.append(x)
        tblPr.append(b)
    def cell(c, text, size=9, bold=False, al=None, color=None):
        c.text = ""; p = c.paragraphs[0]; p.paragraph_format.space_after = Pt(1)
        if al is not None: p.alignment = al
        for i, line in enumerate(str(text).split("\n")):
            if i: p = c.add_paragraph(); p.paragraph_format.space_after = Pt(1)
            r = p.add_run(line); r.font.size = Pt(size); r.font.name = "Arial"; r.bold = bold
            if color: r.font.color.rgb = RGBColor(*color)
    def widths(t, ws):
        t.autofit = False
        for gc, w in zip(t._tbl.tblGrid.findall(qn("w:gridCol")), ws): gc.set(qn("w:w"), str(int(w * 567)))
        for r in t.rows:
            for c, w in zip(r.cells, ws): c.width = Cm(w)
    def logo(c, path, w=3.2):
        if path:
            try: c.paragraphs[0].add_run().add_picture(path, width=Cm(w))
            except Exception: pass

    sifra = _v(e, "sifra_" + vrsta) or _v(e, "sifra"); lg_i = _put(base, _v(e, "logo_investitor")); lg_p = _put(base, _v(e, "logo_projektant"))
    # ---------------------------------------------------------------- naslovna strana
    para("", after=40)
    t = d.add_table(rows=2, cols=3); keep(t._tbl); t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (lab, name, lg) in enumerate(((_T("INVESTITOR"), _v(e, "investitor"), lg_i), (_T("PROJEKTANT"), _v(e, "projektant"), lg_p))):
        cell(t.cell(i, 0), lab + ":", 10, True); logo(t.cell(i, 1), lg, 3.0); cell(t.cell(i, 2), name, 11, True)
        t.rows[i].height = Cm(2.4)
    widths(t, (4.0, 3.8, 8.6))
    para("", after=60)
    if sifra:
        parts = [x for x in re.split(r"[\s\-_/]+", sifra) if x]
        t = d.add_table(rows=1, cols=len(parts)); keep(t._tbl); t.alignment = WD_TABLE_ALIGNMENT.CENTER; borders(t, 8)
        for c, x in zip(t.rows[0].cells, parts): cell(c, x, 16, True, AL.CENTER)
    para(_v(e, "objekat").upper(), 16, True, AL.CENTER, 4, 18)
    if _v(e, "dionica"): para(_TF("DIONICA: {0}", _v(e, "dionica").upper()), 13, True, AL.CENTER, 4)
    if _v(e, "faza"): para(_v(e, "faza").upper(), 14, True, AL.CENTER, 4, 28)
    para(V["naslov"] if _T(V["naslov"]) == V["naslov"] else _T(V["naslov"]), 15, True, AL.CENTER, 4, 18)
    pbreak()
    # ---------------------------------------------------------------- obrazac sa podacima i potpisima
    para(_T("OBRAZAC 1"), 11, True, AL.RIGHT, 8)
    t = d.add_table(rows=2, cols=3); keep(t._tbl); borders(t, 4)
    for c, h in zip(t.rows[0].cells, (_T("Elektronski potpis projektanta"), _T("Elektronski potpis revidenta"), _T("Elektronski potpis nadležnog organa za izdavanje građevinske dozvole"))): cell(c, h, 8)
    for c, h in zip(t.rows[1].cells, ("", _v(e, "revident"), "")): cell(c, h, 9)
    t.rows[1].height = Cm(2.0); widths(t, (5.4, 5.4, 5.6))
    para("", after=10)
    redovi = [(_T("INVESTITOR"), _v(e, "investitor")), (_T("OBJEKAT"), _v(e, "objekat") + ((" – " + _TF("DIONICA {0}", _v(e, "dionica"))) if _v(e, "dionica") else "")),
              (_T("LOKACIJA"), _v(e, "lokacija")), (_T("DIO TEHNIČKE DOKUMENTACIJE"), _T(V["dio"])), (_T("AUTOR PROJEKTA"), _v(e, "autor_projekta")),
              (_T("PROJEKTANT"), _v(e, "projektant") + ("\n" + _v(e, "adresa_projektanta") if _v(e, "adresa_projektanta") else "")),
              (_T("ODGOVORNO LICE"), _v(e, "odgovorno_lice")), (_T("VODEĆI PROJEKTANT"), _v(e, "vodeci_projektant")),
              (_T("ODGOVORNI PROJEKTANT"), _v(e, "odgovorni_projektant")), (_T("SARADNICI NA PROJEKTU"), _v(e, "saradnici"))]
    redovi = [r for r in redovi if r[1]]
    t = d.add_table(rows=len(redovi), cols=2); keep(t._tbl)
    for i, (a, b) in enumerate(redovi):
        cell(t.cell(i, 0), a, 9, True); cell(t.cell(i, 1), b, 10)
        t.rows[i].height = Cm(1.0)
    widths(t, (5.6, 10.8))
    pbreak()
    # ---------------------------------------------------------------- sadržaj knjige
    para("", after=60)
    para(_TF("SADRŽAJ KNJIGE {0}", sifra.replace("-", " ")) if sifra else _T("SADRŽAJ KNJIGE"), 13, True, AL.CENTER, 24)
    for i, (h, stavke) in enumerate(_sadrzaj(vrsta, n_prilog), 1):
        para(f"{i}.  {h}", 11, True, None, 3, 14)
        for s in stavke: para("–  " + s, 10, False, None, 2)
    # ---------------------------------------------------------------- umetni na početak, ukloni stari naslov
    for p in list(d.paragraphs[:3]):
        if p.style.name in ("Title", "Subtitle", "Author") and p._p not in new: p._p.getparent().remove(p._p)
    first = next(ch for ch in body if ch not in new)
    for el in new: first.addprevious(el)
    # ---------------------------------------------------------------- zaglavlje sa logotipom i nazivom dijela
    for sec in d.sections:
        h = sec.header; h.is_linked_to_previous = False
        for p in list(h.paragraphs)[1:]: p._p.getparent().remove(p._p)
        p0 = h.paragraphs[0]; p0.text = ""
        tb = h.add_table(rows=1, cols=2, width=Cm(16.5)); tb.alignment = WD_TABLE_ALIGNMENT.CENTER
        logo(tb.cell(0, 0), lg_p, 2.6); cell(tb.cell(0, 1), _T(V["zag"]), 8, False, AL.RIGHT)
        if not lg_p: cell(tb.cell(0, 0), _v(e, "projektant"), 8, True)
        p0._p.addnext(tb._tbl)
    # ---------------------------------------------------------------- potpisni blok na kraju
    if _v(e, "mjesto") or _v(e, "datum") or _v(e, "odgovorni_projektant"):
        para("", after=18)
        para((_v(e, "mjesto") + (", " if _v(e, "mjesto") and _v(e, "datum") else "") + _v(e, "datum")), 10, False, None, 10)
        para(_T("Sastavio/la,"), 10, False, None, 22)
        who = _v(e, "odgovorni_projektant") or _v(e, "autor_projekta")
        if who: para(who, 10, True, None, 2)
        last = body[-1] if body[-1] is not sect else body[-2]
        # d.add_paragraph je već stavio elemente ispred sectPr – ostaju na kraju dokumenta
    return d
