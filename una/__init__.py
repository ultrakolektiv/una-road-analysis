"""UNA - ROAD ENGINEERING ANALYSIS."""
import os as _os


def _ver():
    try:
        from ._version import VERSION          # upisuje build (build_ci.ps1) iz fajla VERSION
        return VERSION
    except Exception:
        p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "VERSION")
        try: return open(p, encoding="utf-8").read().strip()
        except Exception: return "dev"


__version__ = _ver()
