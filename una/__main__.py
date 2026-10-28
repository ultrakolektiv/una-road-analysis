from .i18n import _T, _TF
import sys, os, argparse
from . import pipeline

def main(argv=None):
    ap = argparse.ArgumentParser(prog="una", description="UNA - ROAD ENGINEERING ANALYSIS – elaborati 3 i 4 (Word + Excel + DXF)")
    ap.add_argument("config", nargs="?", help=_T('JSON datoteka projekta (ako se izostavi, otvara se prozor)'))
    ap.add_argument("-o", "--out", default=None, help=_T("izlazni folder (default: folder 'izlaz' pored projekta)"))
    ap.add_argument("--bez-worda", action="store_true"); ap.add_argument("--bez-excela", action="store_true")
    ap.add_argument("--preglednost", action="store_true", help=_T('dodatno: zrake preglednosti i DXF crtež'))
    ap.add_argument("--id", action="store_true", help=_T('ispiši ID ovog računara (za zahtjev licence)'))
    ap.add_argument("--licenca", metavar="FAJL.lic", help=_T('aktiviraj licencu iz datoteke'))
    ap.add_argument("--lang", choices=["sr", "en"], default=None, help="jezik izlaza / output language")
    a = ap.parse_args(argv)
    from . import licenca
    if a.id: print(licenca.machine_id()); return 0
    if a.licenca:
        try: print("Aktivirano.", licenca.describe(licenca.install(a.licenca))); return 0
        except licenca.LicencaError as e: print(_T('Greška:'), e); return 2
    if not a.config:
        from . import gui; gui.main(); return 0
    cfg = pipeline.load_cfg(a.config)
    if a.lang: cfg["jezik"] = a.lang
    out = a.out or cfg.get("izlaz") or os.path.join(os.path.dirname(os.path.abspath(a.config)), "izlaz")
    try: outs, _ = pipeline.generate(cfg, out, word=not a.bez_worda, excel=not a.bez_excela, sight=True if a.preglednost else None)
    except licenca.LicencaError as e: print(_T('LICENCA:'), e); return 2
    print("\n".join(outs)); return 0

if __name__ == "__main__":
    sys.exit(main())
