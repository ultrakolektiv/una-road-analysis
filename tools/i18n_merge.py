"""Spaja tools/en/b*.py u una/data/en.json uz provjeru placeholdera."""
import json, re, sys, glob, os, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
keys = json.load(open(os.path.join(HERE, "i18n_keys.json"), encoding="utf-8"))
T = {}
for p in sorted(glob.glob(os.path.join(HERE, "en", "b*.py"))):
    spec = importlib.util.spec_from_file_location("m", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    T.update(m.T)

def sig(s):
    return (sorted(re.findall(r"\{\d*(?:![rsa])?(?::[^{}]*)?\}", s)),
            sorted(re.findall(r"<<\w+>>", s)),
            sorted(re.findall(r"%[-+0#]*\d*(?:\.\d+)?[sdfi]", s)),
            sorted(re.findall(r"\{[A-Za-z_]\w*\}", s)))
bad, cat = [], {}
for i, k in enumerate(keys):
    e = T.get(i)
    if e is None: continue
    a, b = sig(k), sig(e)
    # {n} u LaTeX/regex sigurno ostaju isti; poredi skupove
    if a != b: bad.append((i, a, b))
    cat[k] = e
for i, a, b in bad:
    print("MISMATCH", i, "\n  SR:", keys[i][:90].replace("\n", "⏎"), "\n  ", a, "\n  ", b)
print("keys", len(keys), "translated", len(cat), "mismatches", len(bad))
if "--write" in sys.argv:
    out = os.path.join(HERE, "..", "una", "data", "en.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(cat, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("written", out)
