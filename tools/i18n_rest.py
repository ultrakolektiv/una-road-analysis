"""Ispisuje preostale (nepreuzete) tekstualne konstante koje bi mogle biti prikazani tekst."""
import ast, glob, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from i18n_common import parents_of, tmpl_of
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"licenca.py", "_pubkey.py", "__init__.py", "i18n.py", "gui.py", "paths.py"}
for f in sorted(glob.glob(ROOT + "/una/*.py")):
    if os.path.basename(f) in SKIP: continue
    src = open(f, encoding="utf-8").read(); tree = ast.parse(src); par = parents_of(tree)
    for n in ast.walk(tree):
        if not isinstance(n, (ast.Constant, ast.JoinedStr)): continue
        t = tmpl_of(n)
        if not t: continue
        s = t[0]
        if not isinstance(s, str) or not re.search(r"[A-Za-zČĆŽŠĐčćžšđ]{2}", s): continue
        p = par.get(n)
        if isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id in ("_T", "_TF"): continue
        if isinstance(p, (ast.Expr, ast.JoinedStr, ast.FormattedValue, ast.Constant)): continue
        if isinstance(p, ast.Subscript) or isinstance(p, ast.Compare) or isinstance(p, ast.keyword): continue
        if isinstance(p, ast.Dict) and n in p.keys: continue
        if isinstance(p, ast.Call) and isinstance(p.func, ast.Attribute) and p.func.attr in ("get", "setdefault", "pop", "startswith", "endswith", "replace", "split", "join", "write", "open", "format", "index", "count", "append") and n in p.args[:1]:
            if p.func.attr not in ("append", "write"): continue
        print(f"{os.path.basename(f)}:{n.lineno}|{s[:110]!r}".replace("\n", "⏎"))
