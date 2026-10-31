"""Izvoz elaborata u korisnički Word template (naslovna strana, sadržaj, stilovi, zaglavlja/podnožja iz templata)."""
from .i18n import _T, _TF
import copy, io, re
import docx
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"



PPR_ORDER = ["pStyle","keepNext","keepLines","pageBreakBefore","framePr","widowControl","numPr","suppressLineNumbers","pBdr","shd","tabs","suppressAutoHyphens","kinsoku","wordWrap","overflowPunct","topLinePunct","autoSpaceDE","autoSpaceDN","bidi","adjustRightInd","snapToGrid","spacing","ind","contextualSpacing","mirrorIndents","suppressOverlap","jc","textDirection","textAlignment","textboxTightWrap","outlineLvl","divId","cnfStyle","rPr","sectPr","pPrChange"]
RPR_ORDER = ["rStyle","rFonts","b","bCs","i","iCs","caps","smallCaps","strike","dstrike","outline","shadow","emboss","imprint","noProof","snapToGrid","vanish","webHidden","color","spacing","w","kern","position","sz","szCs","highlight","u","effect","bdr","shd","fitText","vertAlign","rtl","cs","em","lang","eastAsianLayout","specVanish","oMath"]


TBLPR_ORDER = ["tblStyle","tblpPr","tblOverlap","bidiVisual","tblStyleRowBandSize","tblStyleColBandSize","tblW","jc","tblCellSpacing","tblInd","tblBorders","shd","tblLayout","tblCellMar","tblLook","tblCaption","tblDescription"]
TCPR_ORDER = ["cnfStyle","tcW","gridSpan","hMerge","vMerge","tcBorders","shd","noWrap","tcMar","textDirection","tcFitText","vAlign","hideMark"]
TRPR_ORDER = ["cnfStyle","divId","gridBefore","gridAfter","wBefore","wAfter","cantSplit","trHeight","tblHeader","tblCellSpacing","jc","hidden"]


def oins(parent, el, order):
    """Umeće dijete u redoslijed propisan OOXML šemom (zamjenjuje postojeći element iste vrste)."""
    name = el.tag.split("}")[1]
    for old in parent.findall(el.tag): parent.remove(old)
    idx = order.index(name) if name in order else len(order)
    for ch in list(parent):
        n = ch.tag.split("}")[1]
        if (order.index(n) if n in order else len(order)) > idx:
            ch.addprevious(el); return el
    parent.append(el); return el


def get_ppr(p):
    ppr = p.find(qn("w:pPr"))
    if ppr is None: ppr = OxmlElement("w:pPr"); p.insert(0, ppr)
    return ppr

def normalize_order(root):
    """Sortira djecu w:pPr i w:rPr prema redoslijedu iz OOXML šeme (Word je osjetljiv na redoslijed)."""
    for tag, order in (("w:pPr", PPR_ORDER), ("w:rPr", RPR_ORDER), ("w:tblPr", TBLPR_ORDER), ("w:tcPr", TCPR_ORDER), ("w:trPr", TRPR_ORDER)):
        for el in root.iter(qn(tag)):
            kids = list(el)
            key = lambda c: order.index(c.tag.split("}")[1]) if c.tag.split("}")[1] in order else len(order)
            srt = sorted(kids, key=key)
            if srt != kids:
                for c in kids: el.remove(c)
                for c in srt: el.append(c)


TEXT_W = 9300


def fix_widths(tbl, total):
    """Fiksne širine kolona proporcionalno dužini sadržaja (LibreOffice/Word ravnomjerno koriste punu širinu teksta)."""
    rows = tbl.findall(qn("w:tr"))
    if not rows: return
    n = max(len(r.findall(qn("w:tc"))) for r in rows)
    small = n >= 10
    if small:
        for r_ in tbl.iter(qn("w:r")):
            rp = r_.find(qn("w:rPr"))
            if rp is None: rp = OxmlElement("w:rPr"); r_.insert(0, rp)
            for tg in ("w:sz", "w:szCs"):
                x = OxmlElement(tg); x.set(qn("w:val"), "14"); oins(rp, x, RPR_ORDER)
    cw = 82 if small else 100
    base = [380] * n; ext = [0.0] * n
    for r in rows:
        for j, tc in enumerate(r.findall(qn("w:tc"))):
            tx = ptext(tc); words = tx.split(); L = max([len(w) for w in words] + [1])
            base[j] = max(base[j], L * cw + 120); ext[j] = max(ext[j], max(len(tx) - L, 0))
    tot = sum(base)
    if tot >= total: ws = [int(x * total / tot) for x in base]
    else:
        left = total - tot; se = sum(ext) or 1
        ws = [int(base[j] + left * ext[j] / se) if sum(ext) else int(base[j] + left / n) for j in range(n)]
    tp = tbl.find(qn("w:tblPr"))
    for e in tp.findall(qn("w:tblW")) + tp.findall(qn("w:tblLayout")): tp.remove(e)
    w_ = OxmlElement("w:tblW"); w_.set(qn("w:w"), str(sum(ws))); w_.set(qn("w:type"), "dxa"); tp.append(w_)
    lay = OxmlElement("w:tblLayout"); lay.set(qn("w:type"), "fixed"); tp.append(lay)
    grid = tbl.find(qn("w:tblGrid"))
    for gc, w in zip(grid.findall(qn("w:gridCol")), ws): gc.set(qn("w:w"), str(w))
    for r in rows:
        for j, tc in enumerate(r.findall(qn("w:tc"))):
            pr = tc.find(qn("w:tcPr"))
            if pr is None: pr = OxmlElement("w:tcPr"); tc.insert(0, pr)
            for e in pr.findall(qn("w:tcW")): pr.remove(e)
            x = OxmlElement("w:tcW"); x.set(qn("w:w"), str(ws[min(j, n - 1)])); x.set(qn("w:type"), "dxa"); pr.insert(0, x)


def ptext(p): return "".join(t.text or "" for t in p.iter(qn("w:t")))


def set_text(p, text, keep_highlight=False):
    """Upisuje tekst u prvi run paragrafa (zadržava njegovo formatiranje), ostale runove briše."""
    runs = [r for r in p.iter(qn("w:r")) if r.find(qn("w:t")) is not None]
    if not runs:
        r = OxmlElement("w:r"); t = OxmlElement("w:t"); r.append(t); p.append(r); runs = [r]
    first = runs[0]
    for r in runs[1:]: r.getparent().remove(r)
    ts = first.findall(qn("w:t"))
    for t in ts[1:]: first.remove(t)
    ts[0].text = text; ts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    if not keep_highlight:
        rpr = first.find(qn("w:rPr"))
        if rpr is not None:
            for h in rpr.findall(qn("w:highlight")) + rpr.findall(qn("w:color")): rpr.remove(h)


def fill_cover(body, t):
    """Popunjava naslovnu stranu: polja označena žutom bojom i redove sa nazivima uloga."""
    labels = {_T('VODEĆI PROJEKTANT'): t.get("vodeci"), "LEAD DESIGNER": t.get("vodeci"), _T('ODGOVORNI PROJEKTANT'): t.get("odgovorni"), "RESPONSIBLE DESIGNER": t.get("odgovorni"),
              _T('SARADNICI NA PROJEKTU'): t.get("saradnici"), "PROJECT TEAM MEMBERS": t.get("saradnici_en") or t.get("saradnici")}
    for tbl in body.iter(qn("w:tbl")):
        for tr in tbl.findall(qn("w:tr")):
            tcs = tr.findall(qn("w:tc"))
            if len(tcs) < 2: continue
            lab = ptext(tcs[0]).strip().rstrip(":").strip().upper()
            for k, v in labels.items():
                if lab.startswith(k) and v:
                    ps = tcs[1].findall(qn("w:p"))
                    if ps: set_text(ps[0], v)
    # folder (jedna ćelija, istaknut tekst)
    for p in body.iter(qn("w:p")):
        tx = ptext(p)
        if tx.strip().startswith("FOLDER XX"):
            if "ENG" in tx.upper():
                if t.get("folder_en"): set_text(p, t["folder_en"])
            elif t.get("folder_sr"): set_text(p, t["folder_sr"])
        elif re.match(r"^\s*Avgust/August 2026", tx) and t.get("datum"): set_text(p, t["datum"])


def count_list_info(raw):
    """numId -> ('bullet'|'decimal')"""
    out = {}
    try:
        num = raw.part.numbering_part.element
    except Exception:
        return out
    absfmt = {}
    for a in num.findall(qn("w:abstractNum")):
        lvl = a.find(qn("w:lvl")); f = lvl.find(qn("w:numFmt")).get(qn("w:val")) if lvl is not None and lvl.find(qn("w:numFmt")) is not None else "decimal"
        absfmt[a.get(qn("w:abstractNumId"))] = f
    for n in num.findall(qn("w:num")):
        a = n.find(qn("w:abstractNumId")).get(qn("w:val")); out[n.get(qn("w:numId"))] = absfmt.get(a, "decimal")
    return out


def pstyle(p):
    ppr = p.find(qn("w:pPr")); 
    if ppr is None: return None
    s = ppr.find(qn("w:pStyle")); return s.get(qn("w:val")) if s is not None else None


def set_pstyle(p, sid, numoff=False):
    ppr = get_ppr(p)
    for st in ppr.findall(qn("w:pStyle")): ppr.remove(st)
    if sid is not None:
        st = OxmlElement("w:pStyle"); st.set(qn("w:val"), sid); oins(ppr, st, PPR_ORDER)
    if numoff:
        n = OxmlElement("w:numPr"); i = OxmlElement("w:ilvl"); i.set(qn("w:val"), "0"); d = OxmlElement("w:numId"); d.set(qn("w:val"), "0"); n.append(i); n.append(d)
        oins(ppr, n, PPR_ORDER)


def set_rpr_all(p, bold=None, italic=None, size=None):
    for r in p.iter(qn("w:r")):
        rpr = r.find(qn("w:rPr"))
        if rpr is None: rpr = OxmlElement("w:rPr"); r.insert(0, rpr)
        if bold: oins(rpr, OxmlElement("w:b"), RPR_ORDER)
        if italic: oins(rpr, OxmlElement("w:i"), RPR_ORDER)
        if size:
            sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(size)); oins(rpr, sz, RPR_ORDER)


def make_caption(proto, kind, title, num=1):
    p = copy.deepcopy(proto)
    for b in list(p):
        if b.tag in (qn("w:bookmarkStart"), qn("w:bookmarkEnd")): p.remove(b)
    runs = p.findall(qn("w:r"))
    base_rpr = copy.deepcopy(runs[0].find(qn("w:rPr")))
    for r in runs: p.remove(r)
    for e in list(p):
        if e.tag != qn("w:pPr"): p.remove(e)
    ppr = get_ppr(p)
    if kind == "T": oins(ppr, OxmlElement("w:keepNext"), PPR_ORDER)
    def run(text=None, fld=None, instr=None):
        r = OxmlElement("w:r"); r.append(copy.deepcopy(base_rpr))
        if text is not None:
            t = OxmlElement("w:t"); t.text = text; t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve"); r.append(t)
        if fld: f = OxmlElement("w:fldChar"); f.set(qn("w:fldCharType"), fld); r.append(f)
        if instr: i = OxmlElement("w:instrText"); i.set("{http://www.w3.org/XML/1998/namespace}space", "preserve"); i.text = instr; r.append(i)
        return r
    label, seq = (_T('Tabela/Table '), " SEQ Tabela_/_Table \\* ARABIC ") if kind == "T" else (_T('Slika / Figure  '), " SEQ Slika_/_Figure_ \\* ARABIC ")
    for r in (run(label), run(fld="begin"), run(instr=seq), run(fld="separate"), run(str(num)), run(fld="end"), run(". " + title)): p.append(r)
    if kind == "F":
        jc = OxmlElement("w:jc"); jc.set(qn("w:val"), "center"); oins(ppr, jc, PPR_ORDER)
    return p


def export(raw_path, t, out_path, log=print):
    tpl = docx.Document(t["file"]); raw = docx.Document(raw_path)
    body = tpl.element.body; els = list(body)
    # --- prototipi i indeksi (pozicije iz templata: tražimo po stilu/tekstu radi robusnosti)
    def idx(pred, start=0):
        for i in range(start, len(els)):
            if pred(els[i]): return i
        return None
    i_nas1 = idx(lambda e: e.tag == qn("w:p") and pstyle(e) == "NASLOV" and "TEKSTUALNA" in ptext(e).upper())
    if i_nas1 is None: raise ValueError(_T("Template nema naslov 'TEKSTUALNA DOKUMENTACIJA' (stil NASLOV) – ne mogu odrediti mjesto za tekst elaborata."))
    i_tr = i_nas1 + 1                      # PODNASLOV 1 – Tehnički izvještaj
    i_sec1 = idx(lambda e: e.tag == qn("w:p") and e.find(".//" + qn("w:sectPr")) is not None, i_tr)   # kraj tekstualnog dijela
    i_nas2 = idx(lambda e: e.tag == qn("w:p") and pstyle(e) == "NASLOV" and "NUMERI" in ptext(e).upper(), i_sec1)
    i_nas3 = idx(lambda e: e.tag == qn("w:p") and pstyle(e) == "NASLOV" and "GRAFI" in ptext(e).upper(), i_nas2 or i_sec1)
    if None in (i_sec1, i_nas2, i_nas3): raise ValueError(_T('Template nema očekivane dijelove (NUMERIČKA / GRAFIČKA DOKUMENTACIJA).'))
    proto_cap = next((e for e in els if e.tag == qn("w:p") and pstyle(e) == "Caption" and _T('Tabela/Table') in ptext(e)), None)
    if proto_cap is None: raise ValueError(_T('Template nema primjer naslova tabele (stil Caption).'))
    fill_cover(body, t)
    # --- priprema sadržaja iz pandoc dokumenta
    listfmt = count_list_info(raw)
    relmap = {}
    def new_rid(old):
        if old not in relmap:
            blob = raw.part.related_parts[old].blob
            rid, _ = tpl.part.get_or_add_image(io.BytesIO(blob)); relmap[old] = rid
        return relmap[old]
    items = [e for e in raw.element.body if e.tag != qn("w:sectPr")]
    segs = {"M": [], "A": [], "B": [], "C": []}; cur = "M"; counters = {}; capn = {"T": 0, "F": 0}
    for e in items:
        tx = ptext(e).strip() if e.tag == qn("w:p") else None
        if tx in ("ZZSEGA", "ZZSEGB", "ZZSEGC"): cur = tx[-1]; continue
        if e.tag in (qn("w:bookmarkStart"), qn("w:bookmarkEnd")): continue
        e = copy.deepcopy(e)
        for bm in list(e.iter(qn("w:bookmarkStart"))) + list(e.iter(qn("w:bookmarkEnd"))): bm.getparent().remove(bm)
        for bl in e.iter("{%s}blip" % A_NS):
            bl.set("{%s}embed" % R_NS, new_rid(bl.get("{%s}embed" % R_NS)))
        segs[cur].append(e)
    def convert(e, in_table=False):
        if e.tag == qn("w:tbl"):
            for p in e.iter(qn("w:p")): convert(p, True)
            return e
        if e.tag != qn("w:p"): return e
        st = pstyle(e); txt = ptext(e).strip()
        if in_table:
            set_pstyle(e, None); ppr = get_ppr(e)
            ind = OxmlElement("w:ind"); ind.set(qn("w:left"), "0"); ind.set(qn("w:right"), "0"); ind.set(qn("w:firstLine"), "0"); oins(ppr, ind, PPR_ORDER)
            if ppr.find(qn("w:jc")) is None:
                jc = OxmlElement("w:jc"); jc.set(qn("w:val"), "left"); oins(ppr, jc, PPR_ORDER)
            sp = ppr.find(qn("w:spacing"))
            if sp is not None: sp.set(qn("w:line"), "240"); sp.set(qn("w:lineRule"), "auto")
            return e
        ppr = e.find(qn("w:pPr")); numpr = ppr.find(qn("w:numPr")) if ppr is not None else None
        if st in ("Heading1",):
            set_pstyle(e, "PODNASLOV2", numoff=True); set_rpr_all(e, size=24)
        elif st in ("Heading2",):
            set_pstyle(e, "PODNASLOV2", numoff=True)
        elif st in ("Heading3", "Heading4"):
            set_pstyle(e, "GLAVNITEKST"); set_rpr_all(e, bold=True, italic=True)
        else:
            m1 = re.match(_T('^Tabela (\\d+) – (.+)$'), txt); m2 = re.match(_T('^Slika (\\d+) – (.+)$'), txt)
            if m1: capn["T"] += 1; return make_caption(proto_cap, "T", m1.group(2), capn["T"])
            if m2: capn["F"] += 1; return make_caption(proto_cap, "F", m2.group(2), capn["F"])
            has_img = e.find(".//" + qn("w:drawing")) is not None
            set_pstyle(e, "GLAVNITEKST")
            if has_img:
                ppr = get_ppr(e); jc = OxmlElement("w:jc"); jc.set(qn("w:val"), "center"); oins(ppr, jc, PPR_ORDER)
            if numpr is not None:
                nid = numpr.find(qn("w:numId")).get(qn("w:val")); kind = listfmt.get(nid, "decimal")
                ppr = e.find(qn("w:pPr")); ppr.remove(numpr)
                if kind == "bullet": prefix = "•\t"
                else: counters[nid] = counters.get(nid, 0) + 1; prefix = f"{counters[nid]}.\t"
                ind = OxmlElement("w:ind"); ind.set(qn("w:left"), "425"); ind.set(qn("w:hanging"), "425"); oins(ppr, ind, PPR_ORDER)
                r = OxmlElement("w:r"); t_ = OxmlElement("w:t"); t_.text = prefix.replace("\t", ""); t_.set("{http://www.w3.org/XML/1998/namespace}space", "preserve"); r.append(t_)
                r.append(OxmlElement("w:tab")) if False else None
                first_r = e.find(qn("w:r"))
                if first_r is not None: first_r.addprevious(r)
                else: e.append(r)
                t_.text = prefix.replace("\t", " ")
        return e
    # tabele iz pandoca: obrub i font (isto kao u standardnom elaboratu)
    from .report import postprocess_tables
    tmp_tables = [e for k in segs for e in segs[k] if e.tag == qn("w:tbl")]
    postprocess_tables(tmp_tables)
    for tb in tmp_tables: fix_widths(tb, TEXT_W)
    for k in segs: segs[k] = [convert(e) for e in segs[k]]
    # ostali brojači listi: nova numeracija za svaku listu
    # --- ukloni primjere iz templata i ubaci sadržaj
    def retitle(p, text): set_text(p, text)
    def insert_after(anchor, nodes):
        for n in nodes: anchor.addnext(n); anchor = n
    # grafički dio (od kraja): brišemo sve između naslova GRAFIČKA i završnog sectPr, ostavljamo prvi PODNASLOV 1
    gi = i_nas3 + 1
    gfirst = els[gi]
    for e in els[gi + 1:]:
        if e.tag != qn("w:sectPr"): body.remove(e)
    retitle(gfirst, t.get("naslov_graficki", _T('Grafički prilozi – vozno-dinamičke analize / Graphical Appendices – Driving Dynamics Analysis')))
    insert_after(gfirst, segs["B"])
    # numerički dio: PODNASLOV 1 odmah iza NASLOV (i_nas2+1); do sectPr paragrafa uklanjamo ostale podnaslove, a paragraf sa sectPr čistimo
    nfirst = els[i_nas2 + 1]
    for e in els[i_nas2 + 2: i_nas3]:
        if e.tag == qn("w:p") and e.find(".//" + qn("w:sectPr")) is not None:
            for r in e.findall(qn("w:r")): e.remove(r)
            ppr = e.find(qn("w:pPr")); st = ppr.find(qn("w:pStyle"))
            if st is not None: ppr.remove(st)
            for n in ppr.findall(qn("w:numPr")): ppr.remove(n)
            sect_par = e
        else: body.remove(e)
    retitle(nfirst, t.get("naslov_numericki", _T('Numerički proračun profila brzina / Numerical Calculation of Speed Profiles')))
    insert_after(nfirst, segs["A"])
    # tekstualni dio
    tfirst = els[i_tr]
    for e in els[i_tr + 1: i_sec1]:
        body.remove(e)
    retitle(tfirst, t.get("naslov_izvjestaj", _T('Vozno-dinamičke analize / Driving Dynamics Analyses')))
    insert_after(tfirst, segs["M"] + segs["C"])
    # zadnji tekstualni element ne smije završiti tabelom neposredno ispred sectPr paragrafa – dodaj prazan paragraf
    # ažuriranje polja pri otvaranju
    st = tpl.settings.element
    if st.find(qn("w:updateFields")) is None:
        u = OxmlElement("w:updateFields"); u.set(qn("w:val"), "true"); st.append(u)
    normalize_order(tpl.element)
    tpl.save(out_path)
    log(_TF("Word (template): {0}", out_path))
