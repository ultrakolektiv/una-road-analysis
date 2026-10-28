"""Normalni poprečni profili (NPP): otvorena trasa (nasip/usjek), most, tunel.
Zadane mjere su očitane iz crteža NPP_BC_Budva / NPP_Mostovi / NPP_Tuneli (una/data/npp_default.json); korisnik ih može mijenjati u cfg["npp"]."""
import json, os, copy
from .i18n import _T

_DEF = None


def defaults():
    global _DEF
    if _DEF is None:
        _DEF = json.load(open(os.path.join(os.path.dirname(__file__), "data", "npp_default.json"), encoding="utf-8"))
    return copy.deepcopy(_DEF)


def resolve(cfg):
    """Spaja zadane profile sa cfg['npp'] (profili se dopunjavaju po poljima)."""
    d = defaults(); u = (cfg or {}).get("npp") or {}
    for k, v in (u.get("profili") or {}).items():
        base = d["profili"].setdefault(k, {})
        for kk, vv in v.items():
            if isinstance(vv, dict) and isinstance(base.get(kk), dict): base[kk].update(vv)
            else: base[kk] = vv
    d["zadani"] = u.get("zadani") or d["zadani"]
    d["dionice"] = [e for e in (u.get("dionice") or []) if isinstance(e, dict) and e.get("profil") in d["profili"]]
    return d


def profile_at(N, role, s, sekcija=None):
    """Profil NPP za osovinu (role) i stacionažu s: posljednja podudarna dionica pobjeđuje, inače zadani."""
    pr = N["zadani"]
    for e in N["dionice"]:
        if e.get("osovina") not in (None, "", role): continue
        if e.get("sekcija") not in (None, "", sekcija): continue
        if float(e["od"]) - 1e-9 <= s <= float(e["do"]) + 1e-9: pr = e["profil"]
    return pr, N["profili"][pr]


def apply_to_sight(cfg):
    """Prenosi NPP u postavke preglednosti: tipovi prepreka (ofset po strani) i raspone (dionice). Poziva se prije preglednost.run."""
    N = resolve(cfg)
    if not (cfg.get("npp") and (cfg["npp"].get("dionice") or cfg["npp"].get("profili") or cfg["npp"].get("zadani"))): return N
    pg = cfg.setdefault("preglednost", {"ukljuci": True})
    tip = dict(pg.get("tipovi_prepreka") or {})
    for k, p in N["profili"].items():
        tip[k] = {"vani": float(p["vani"]["ofset"]), "razdjelni": float(p["razdjelni"]["ofset"])}
    pg["tipovi_prepreka"] = tip
    pg["zadani_tip"] = N["zadani"]
    pre = [e for e in (pg.get("prepreke") or []) if isinstance(e, dict) and not e.get("_npp")]
    for e in N["dionice"]:
        pre.append({k: e[k] for k in ("sekcija", "osovina", "od", "do") if e.get(k) not in (None, "")} | {"tip": e["profil"], "_npp": True})
    pg["prepreke"] = pre
    return N
