"""DXF → DWG pretvorba pomoću besplatnog ODA File Converter-a (Open Design Alliance) – ako je instaliran.
DWG je zatvoren format; UNA ga ne može pisati sama, pa koristi službeni besplatni konverter (https://www.opendesign.com/guestfiles/oda_file_converter)."""
import os, glob, shutil, subprocess, tempfile
from .i18n import _T, _TF


def find_converter():
    p = os.environ.get("UNA_ODA") or shutil.which("ODAFileConverter")
    if p and os.path.isfile(p): return p
    cands = []
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
        if base: cands += glob.glob(os.path.join(base, "ODA", "ODAFileConverter*", "ODAFileConverter.exe")) + glob.glob(os.path.join(base, "ODA", "*", "ODAFileConverter.exe"))
    cands += glob.glob("/usr/bin/ODAFileConverter*") + glob.glob("/opt/ODAFileConverter*/ODAFileConverter")
    return cands[0] if cands else None


def convert(dxf_files, log=print, version="ACAD2018"):
    """Vraća listu napravljenih .dwg datoteka (pored .dxf). Ako konverter nije instaliran, upisuje uputu u log i vraća []."""
    exe = find_converter()
    if not exe:
        log(_T("DWG: nije pronađen ODA File Converter. Instalirajte besplatni ODA File Converter (opendesign.com) i ponovo pokrenite izradu – DWG se tada pravi automatski. Do tada otvorite DXF u AutoCAD-u i Save As → DWG."))
        return []
    dxf_files = [f for f in dxf_files if f.lower().endswith(".dxf")]
    if not dxf_files: return []
    out = []
    with tempfile.TemporaryDirectory() as tin, tempfile.TemporaryDirectory() as tout:
        for f in dxf_files: shutil.copy(f, os.path.join(tin, os.path.basename(f)))
        r = subprocess.run([exe, tin, tout, version, "DWG", "0", "1", "*.DXF"], capture_output=True, text=True, timeout=600,
                           creationflags=0x08000000 if os.name == "nt" else 0)
        for f in dxf_files:
            d = os.path.join(tout, os.path.splitext(os.path.basename(f))[0] + ".dwg")
            if os.path.isfile(d):
                dst = os.path.splitext(f)[0] + ".dwg"; shutil.copy(d, dst); out.append(dst)
    log(_TF("DWG: napravljeno {0} od {1} crteža.", len(out), len(dxf_files)))
    return out
