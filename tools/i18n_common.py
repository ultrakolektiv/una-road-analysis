"""Zajednički dio alata za izdvajanje/primjenu prevoda (AST)."""
import ast, re

SR = re.compile(r"[čćžšđČĆŽŠĐ]|\b(je|su|za|na|od|do|po|sa|ili|kao|koji|koja|koje|preglednost\w*|brzin\w*|trase|trasa|dionic\w*|vozil\w*|proračun\w*|tabel\w*|slik\w*|nagib\w*|osovin\w*|odaberite|datotek\w*|greška|upozorenje|izlaz\w*|uspon\w*|krivin\w*|luk\w*|kolovoz\w*|prijelaznic\w*|stacionaž\w*|ispis\w*|licenc\w*|projekt\w*)\b", re.I)


def tmpl_of(node):
    """(šablon, [izrazi]) za Constant ili JoinedStr; None ako se ne može pretvoriti."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, []
    if isinstance(node, ast.JoinedStr):
        parts, args = [], []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(v.value.replace("{", "{{").replace("}", "}}"))
            elif isinstance(v, ast.FormattedValue):
                spec = ""
                if v.format_spec is not None:
                    if not all(isinstance(x, ast.Constant) for x in v.format_spec.values): return None
                    spec = ":" + "".join(x.value for x in v.format_spec.values)
                conv = {-1: "", 115: "!s", 114: "!r", 97: "!a"}[v.conversion]
                parts.append("{" + str(len(args)) + conv + spec + "}"); args.append(v.value)
            else: return None
        return "".join(parts), args
    return None


def is_candidate(node, parents):
    t = tmpl_of(node)
    if t is None: return False
    s = t[0]
    if len(s) < 6 or not SR.search(s): return False
    p = parents.get(node)
    # već prevedeno / docstring / import / nije tekst
    if isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id in ("_", "_f", "_T", "_TF"): return False
    if isinstance(p, ast.Expr): return False                      # docstringovi
    if isinstance(p, ast.JoinedStr) or isinstance(p, ast.FormattedValue): return False
    if isinstance(p, ast.Constant): return False
    return True


def parents_of(tree):
    d = {}
    for p in ast.walk(tree):
        for c in ast.iter_child_nodes(p): d[c] = p
    return d


def at_module_level(node, parents):
    n = node
    while n in parents:
        n = parents[n]
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)): return False
    return True
