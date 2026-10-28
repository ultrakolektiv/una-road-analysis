"""Prepisuje una/*.py: srpski tekstovi → _T("...") / _TF("...", args). Modulski nivo se ne dira (rješava se na mjestu upotrebe).
Pokretanje: python tools/i18n_apply.py [--dry]"""
import ast, glob, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from i18n_common import *
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"licenca.py", "_pubkey.py", "__init__.py", "i18n.py", "gui.py", "paths.py"}
cat = json.load(open(os.path.join(ROOT, "una", "data", "en.json"), encoding="utf-8"))
dry = "--dry" in sys.argv
tot = 0
for f in sorted(glob.glob(os.path.join(ROOT, "una", "*.py"))):
    if os.path.basename(f) in SKIP: continue
    src = open(f, encoding="utf-8").read(); tree = ast.parse(src); par = parents_of(tree)
    lines = src.encode("utf-8").split(b"\n"); starts = [0]
    for l in lines: starts.append(starts[-1] + len(l) + 1)
    off = lambda ln, col: starts[ln - 1] + col
    b = src.encode("utf-8")
    edits = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.Constant, ast.JoinedStr)) and is_candidate(n, par):
            if at_module_level(n, par): continue
            tmpl, args = tmpl_of(n)
            if tmpl not in cat: continue
            a, e = off(n.lineno, n.col_offset), off(n.end_lineno, n.end_col_offset)
            if args:
                segs = [ast.get_source_segment(src, x) for x in args]
                if any(s is None for s in segs): print("SKIP args", f, n.lineno); continue
                new = "_TF(" + repr(tmpl) + ", " + ", ".join(segs) + ")"
            else:
                new = "_T(" + repr(tmpl) + ")"
            edits.append((a, e, new, n.lineno))
    edits.sort()
    keep, last = [], -1                        # ugniježđeni: vanjski pobjeđuje
    for ed in edits:
        if ed[0] >= last: keep.append(ed); last = ed[1]
        else: print("NESTED skip", os.path.basename(f), ed[3])
    for a, e, new, ln in reversed(keep):
        b = b[:a] + new.encode("utf-8") + b[e:]
    if keep:
        s = b.decode("utf-8")
        imp = "from .i18n import _T, _TF\n"
        if imp not in s:
            t2 = ast.parse(s); idx = 0
            for st in t2.body:
                if isinstance(st, (ast.Import, ast.ImportFrom)) and not (isinstance(st, ast.ImportFrom) and st.module == "__future__"):
                    idx = st.lineno; break
            ls = s.split("\n"); ls.insert(max(idx - 1, 0), imp.rstrip("\n")); s = "\n".join(ls)
        ast.parse(s)
        if not dry: open(f, "w", encoding="utf-8").write(s)
    print(os.path.basename(f), len(keep)); tot += len(keep)
print("ukupno", tot, "(dry)" if dry else "")
