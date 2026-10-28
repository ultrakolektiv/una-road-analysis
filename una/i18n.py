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


_T = _      # kratki nazivi za izvorni kod (izbjegavaju sudar sa promjenljivom '_')
_TF = _f
