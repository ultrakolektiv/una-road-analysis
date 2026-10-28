"""Putanje: resursi i pandoc, i u razvojnom i u pakovanom (Nuitka/PyInstaller) režimu."""
import os, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))


def app_dir():
    """Folder u kome je pokrenuta aplikacija (pored .exe kad je pakovana)."""
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.dirname(HERE)


def find_pandoc():
    """1) pandoc zapakovan uz aplikaciju (pandoc\\pandoc.exe)  2) PATH  3) pypandoc."""
    exe_name = "pandoc.exe" if os.name == "nt" else "pandoc"
    for base in (app_dir(), os.path.dirname(os.path.abspath(sys.argv[0])), HERE):
        for sub in ("pandoc", "vendor/pandoc", "."):
            p = os.path.join(base, sub, exe_name)
            if os.path.isfile(p): return p
    exe = shutil.which("pandoc")
    if exe: return exe
    try:
        import pypandoc
        return pypandoc.get_pandoc_path()
    except Exception:
        raise RuntimeError("Pandoc nije pronađen. Instalirajte aplikaciju ponovo (pandoc je u paketu) ili instalirajte Pandoc sa pandoc.org.")
