"""Jezik (sr / en) i prevodni katalog. Srpski tekst je izvor; engleski se traži u una/data/en.json (ključ = srpski tekst)."""
import json, os

_LANG = "sr"
_CAT = None
HERE = os.path.dirname(os.path.abspath(__file__))
LANGS = ("sr", "en")


def set_lang(lang):
    global _LANG
    _LANG = "en" if str(lang or "").lower().startswith("en") else "sr"


def get_lang():
    return _LANG


def _catalog():
    global _CAT
    if _CAT is None:
        try:
            with open(os.path.join(HERE, "data", "en.json"), encoding="utf-8") as f:
                _CAT = json.load(f)
        except Exception:
            _CAT = {}
    return _CAT


def _(s):
    """Prevodi srpski tekst u aktivni jezik (nepoznato = ostaje srpski)."""
    if _LANG == "sr": return s
    return _catalog().get(s, s)


def _f(tmpl, *args):
    """Prevedeni šablon sa pozicionim argumentima ({0}, {1:.1f} …) – zamjena za f-string."""
    return _(tmpl).format(*args)


def dec(sep_text):
    """Decimalni separator za aktivni jezik: zarez (sr) / tačka (en)."""
    return sep_text if _LANG == "sr" else sep_text.replace(",", ".")


def dec(s):
    """Decimalni separator prema jeziku: zarez (sr) / tačka (en)."""
    return s.replace(".", ",") if _LANG == "sr" else s


def tr_obj(x):
    """Rekurzivno prevodi tekstove u strukturi (list/tuple/dict-vrijednosti) – za modulske konstante."""
    if isinstance(x, str): return _(x)
    if isinstance(x, list): return [tr_obj(i) for i in x]
    if isinstance(x, tuple): return tuple(tr_obj(i) for i in x)
    if isinstance(x, dict): return {k: tr_obj(v) for k, v in x.items()}
    return x


class TrDict(dict):
    """Rječnik čije se vrijednosti prevode pri čitanju (jezik se bira u trenutku upotrebe)."""
    def __getitem__(self, k): return tr_obj(dict.__getitem__(self, k))
    def get(self, k, d=None): return tr_obj(dict.get(self, k, d))
    def values(self): return [tr_obj(v) for v in dict.values(self)]
    def items(self): return [(k, tr_obj(v)) for k, v in dict.items(self)]


def cell(v):
    """Prevod vrijednosti ćelije/zaglavlja: tekst se traži u katalogu; u formulama se prevode navodnicima ograđeni literali."""
    if _LANG == "sr" or not isinstance(v, str): return v
    if v.startswith("="):
        import re
        return re.sub(r'"([^"]+)"', lambda m: '"' + _(m.group(1)) + '"' if m.group(1) in _catalog() else m.group(0), v)
    return _(v)


_T = _      # kratki nazivi za izvorni kod (izbjegavaju sudar sa promjenljivom '_')
_TF = _f
