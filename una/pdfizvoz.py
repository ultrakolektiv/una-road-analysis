"""PDF iz Word elaborata preko LibreOffice-a. Formule (OMML) se za PDF zamjenjuju slikama (matplotlib mathtext), jer LibreOffice bez
modula Math formule izostavi. Word dokument ostaje nepromijenjen (izvorne, izmjenjive formule)."""
import os, re, shutil, subprocess, tempfile


def _latex_list(docx, pandoc):
    md = subprocess.run([pandoc, "-f", "docx", "-t", "markdown", "--wrap=none", docx], capture_output=True, text=True, check=True).stdout
    out = []
    for m in re.finditer(r"\$\$(.+?)\$\$|(?<![\\$])\$(?!\$)(.+?)(?<!\\)\$", md, re.S):
        out.append((m.group(1) if m.group(1) is not None else m.group(2), m.group(1) is not None))
    return out


def _mt(tex):
    t = tex.strip()
    t = re.sub(r"\\text\{([^}]*)\}", r"\\mathrm{\1}", t)
    t = t.replace(r"\lbrack", "[").replace(r"\rbrack", "]").replace(r"\left\lbrack", r"\left[").replace(r"\right\rbrack", r"\right]")
    t = t.replace(r"\quad\quad", r"\quad").replace("\n", " ")
    t = re.sub(r"\\t?frac(?=\{)", r"\\dfrac", t)                     # razlomci u punoj veličini (kao u Wordu)
    return t


def _png(tex, path, fs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, f"${_mt(tex)}$", fontsize=fs)
    fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(fig)


def docx_to_pdf(docx, pdf=None, log=print):
    from .paths import find_pandoc
    import docx as _dx
    from docx.shared import Pt
    from docx.oxml.ns import qn
    pdf = pdf or os.path.splitext(docx)[0] + ".pdf"
    td = tempfile.mkdtemp(prefix="una_pdf_")
    try:
        try: lst = _latex_list(docx, find_pandoc())
        except Exception: lst = []
        d = _dx.Document(docx); body = d.element.body
        M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
        els = [e for e in body.iter() if e.tag in (M + "oMathPara", M + "oMath") and not (e.tag == M + "oMath" and e.getparent().tag == M + "oMathPara")]
        if lst and len(lst) == len(els):
            for k, (el, (tex, disp)) in enumerate(zip(els, lst)):
                png = os.path.join(td, f"f{k}.png")
                try: _png(tex, png, 14 if disp else 11)
                except Exception: continue
                from PIL import Image
                w, h = Image.open(png).size
                p = el.getparent()
                while p is not None and p.tag != qn("w:p"): p = p.getparent()
                if p is None: continue
                from docx.text.paragraph import Paragraph
                par = Paragraph(p, d._body)
                r = par.add_run(); r.add_picture(png, height=Pt(h / 300 * 72))
                el.addprevious(r._r); el.getparent().remove(el)
        elif els:
            log(f"PDF: formule nisu zamijenjene slikama ({len(lst)} / {len(els)}).")
        tmp = os.path.join(td, os.path.basename(docx)); d.save(tmp)
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", td, tmp], capture_output=True, timeout=900)
        shutil.copy(os.path.splitext(tmp)[0] + ".pdf", pdf)
        return pdf
    finally:
        shutil.rmtree(td, ignore_errors=True)
