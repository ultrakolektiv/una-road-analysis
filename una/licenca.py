"""Licenciranje: potpisana licenca (Ed25519), vezana za računar, sa rokom važenja.

Datoteka licence (licenca.lic) = JSON { "podaci": {...}, "potpis": base64 }.
Aplikacija sadrži samo javni ključ; licence može izdati samo vlasnik privatnog ključa.
"""
import os, sys, json, base64, hashlib, datetime, subprocess, shutil
from .i18n import _T, _TF

APP = "UNA"; _HASH_ID = "Elaborat3"            # _HASH_ID se ne mijenja (ID računara ostaje isti kao u ranijim verzijama)


class LicencaError(Exception):
    pass


# ---------------------------------------------------------------- identifikacija računara
def _raw_machine():
    try:
        if os.name == "nt":
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            return winreg.QueryValueEx(k, "MachineGuid")[0]
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            if os.path.isfile(p): return open(p).read().strip()
        if sys.platform == "darwin":
            out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], capture_output=True, text=True).stdout
            for ln in out.splitlines():
                if "IOPlatformUUID" in ln: return ln.split('"')[-2]
    except Exception:
        pass
    import uuid
    return str(uuid.getnode())


def machine_id():
    """Kratak ID računara oblika XXXX-XXXX-XXXX-XXXX (hash; ne otkriva ništa o računaru)."""
    h = hashlib.sha256((_HASH_ID + "|" + _raw_machine()).encode()).hexdigest().upper()[:16]
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


# ---------------------------------------------------------------- lokacije
def user_dir():
    base = os.environ.get("APPDATA") if os.name == "nt" else os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base or os.path.expanduser("~"), APP); os.makedirs(d, exist_ok=True); return d


def license_paths():
    from .paths import app_dir
    ps = [os.path.join(user_dir(), "licenca.lic"), os.path.join(app_dir(), "licenca.lic")]
    pd = os.environ.get("PROGRAMDATA")
    if pd: ps.append(os.path.join(pd, APP, "licenca.lic"))
    return ps


# ---------------------------------------------------------------- provjera
def _pubkey():
    from . import _pubkey as pk
    key = pk.PUBLIC_KEY_B64
    if not key:                          # rezervno: javni_kljuc.txt pored aplikacije (preživi zamjenu foldera una novom verzijom)
        from . import paths
        for d in (paths.app_dir(), user_dir()):
            f = os.path.join(d, "javni_kljuc.txt")
            if os.path.isfile(f):
                key = open(f, encoding="utf-8").read().strip(); break
    if not key: raise LicencaError("Javni ključ nije ugrađen u ovu verziju. U Izdavac_licenci pokrenite dugme \"Ključevi / upiši javni ključ u aplikaciju\" (upisuje i datoteku javni_kljuc.txt).")
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(key))


def canon(podaci):
    return json.dumps(podaci, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def verify_file(path, pub=None, today=None):
    """Vraća rječnik licence ili baca LicencaError."""
    try:
        d = json.load(open(path, encoding="utf-8")); podaci, sig = d["podaci"], base64.b64decode(d["potpis"])
    except Exception:
        raise LicencaError("Datoteka licence je oštećena ili nije licenca.")
    try:
        (pub or _pubkey()).verify(sig, canon(podaci))
    except LicencaError:
        raise
    except Exception:
        raise LicencaError("Licenca nije valjana (potpis se ne poklapa).")
    mid = podaci.get("racunar", "*")
    if mid != "*" and mid != machine_id():
        raise LicencaError(f"Licenca je izdata za drugi računar (vaš ID računara: {machine_id()}).")
    today = today or datetime.date.today()
    if podaci.get("istice"):
        if today > datetime.date.fromisoformat(podaci["istice"]):
            raise LicencaError(f"Licenca je istekla {podaci['istice']}.")
    _clock_check(today)
    return podaci


def _clock_check(today):
    """Prosta zaštita od vraćanja sata: pamti zadnji datum korištenja."""
    p = os.path.join(user_dir(), ".last")
    try:
        last = datetime.date.fromisoformat(open(p).read().strip())
        if today < last - datetime.timedelta(days=1):
            raise LicencaError("Sat računara je vraćen unazad. Postavite ispravan datum.")
        if today > last: open(p, "w").write(today.isoformat())
    except FileNotFoundError:
        open(p, "w").write(today.isoformat())
    except ValueError:
        open(p, "w").write(today.isoformat())


_CACHE = {}


def current(pub=None):
    """Prva valjana licenca sa poznatih lokacija. Baca LicencaError ako je nema."""
    if _CACHE.get("lic") and pub is None: return _CACHE["lic"]
    last = None
    for p in license_paths():
        if os.path.isfile(p):
            try:
                lic = verify_file(p, pub); _CACHE["lic"] = lic; return lic
            except LicencaError as e:
                last = e
    raise last or LicencaError("Licenca nije pronađena. Pošaljite ID računara da dobijete licencu.")


def require():
    return current()


def install(src):
    """Provjeri datoteku licence i kopiraj je u korisnički folder."""
    lic = verify_file(src)
    shutil.copyfile(src, os.path.join(user_dir(), "licenca.lic")); _CACHE.clear()
    return lic


def describe(lic):
    ist = lic.get("istice") or _T("bez isteka")
    return _TF("Licenca: {0} | ID {1} | važi do: {2}", lic.get("kupac", "?"), lic.get("id", "?"), ist)


def stamp(lic):
    """Tihi potpis u izlaznim dokumentima (svojstva Word/Excel fajla) – za praćenje curenja kopija."""
    return {"kupac": lic.get("kupac", ""), "id": lic.get("id", "")}
