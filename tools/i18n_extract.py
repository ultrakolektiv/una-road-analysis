"""Izdvaja sve srpske tekstove iz una/*.py u tools/i18n_strings.json (šablon → lokacije). Pokretanje: python tools/i18n_extract.py"""
import ast, glob, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from i18n_common import *

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {"licenca.py", "_pubkey.py", "__init__.py", "i18n.py", "gui.py", "paths.py"}
out = {}
for f in sorted(glob.glob(os.path.join(ROOT, "una", "*.py"))):
    if os.path.basename(f) in SKIP: continue
    src = open(f, encoding="utf-8").read(); tree = ast.parse(src); par = parents_of(tree)
    for n in ast.walk(tree):
        if isinstance(n, (ast.Constant, ast.JoinedStr)) and is_candidate(n, par):
            t = tmpl_of(n)[0]
            out.setdefault(t, []).append(f"{os.path.basename(f)}:{n.lineno}" + (":MODUL" if at_module_level(n, par) else ""))
json.dump(out, open(os.path.join(ROOT, "tools", "i18n_strings.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(len(out), "jedinstvenih šablona;", sum(len(v) for v in out.values()), "mjesta;", sum(len(k) for k in out), "znakova")
