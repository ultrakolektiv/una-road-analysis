"""Lokalni HTTP poslužitelj + prozor aplikacije (Edge/Chrome u 'app' režimu). Samo 127.0.0.1, sa jednokratnim tokenom."""
import json, os, sys, threading, time, traceback, secrets, subprocess, shutil, mimetypes, copy, webbrowser, queue
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from .. import pipeline, engine
from ..parse import Axis, detect_kind
from . import dialogs

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")
LAST = os.path.join(os.path.expanduser("~"), ".una_zadnji_projekat.txt")
UI_CFG = os.path.join(os.path.expanduser("~"), ".una_ui.json")

ROLES = {"razdvojene": ["desna", "lijeva"], "centralna": ["centralna"], "jedna_naprijed": ["osovina"], "jedna_nazad": ["osovina"]}


def _version():
    try:
        from .. import _version as v
        return v.VERSION
    except Exception:
        try: return open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "VERSION")).read().strip()
        except Exception: return "dev"


class State:
    def __init__(self):
        self.token = secrets.token_urlsafe(16)
        self.lock = threading.Lock()
        self.run = None                       # {"lines": [], "done": bool, "outs": [], "error": None}
        self.last_ping = time.time(); self.pinged = False
        self.ui = self.load_ui()

    @staticmethod
    def load_ui():
        try: return json.load(open(UI_CFG, encoding="utf-8"))
        except Exception: return {}

    def save_ui(self):
        try: json.dump(self.ui, open(UI_CFG, "w", encoding="utf-8"))
        except Exception: pass


S = State()


# ------------------------------------------------------------------ API
def api_state(b):
    from .. import licenca, i18n
    i18n.set_lang((b or {}).get('lang'))
    lic = {"ok": False, "text": "", "id": ""}
    try:
        lic["id"] = licenca.machine_id()
        l = licenca.current(); lic.update(ok=True, text=licenca.describe(l))
    except licenca.LicencaError as e:
        lic["text"] = str(e)
    except Exception as e:
        lic["text"] = str(e)
    last = None
    try:
        p = open(LAST, encoding="utf-8").read().strip()
        if p and os.path.isfile(p): last = p
    except Exception: pass
    D = {k: v for k, v in engine.DEFAULTS.items()}
    return {"version": _version(), "license": lic, "last": last, "ui": S.ui, "defaults": json.loads(json.dumps(D, default=lambda o: None)),
            "pid": os.getpid()}


def api_ui(b):
    S.ui.update(b or {}); S.save_ui(); return {"ok": True}


def api_pick(b):
    try:
        r = dialogs.pick(b.get("mode", "open"), b.get("title", ""), [tuple(x) for x in b.get("filters", [])], bool(b.get("multiple")), b.get("initial", ""), b.get("name", ""))
        return {"paths": r}
    except Exception as e:
        return {"paths": [], "error": str(e)}


def api_detect(b):
    out, errs = {}, {}
    for p in b.get("paths", []):
        try: out[p] = detect_kind(p)
        except Exception as e: errs[p] = str(e)
    return {"kinds": out, "errors": errs}


def _axis(sp):
    return Axis("tmp", sp["h"], sp["v"], sp["x"], cs_col=sp.get("cs_col"))


def api_axisrange(b):
    lo = hi = None
    try:
        for sp in b.get("specs", []):
            if not all(os.path.isfile(sp.get(k, "")) for k in ("h", "v", "x")): raise ValueError("files")
            ax = _axis(sp)
            a, c = max(ax.s_min, float(ax.cs_s.min())), min(ax.s_max, float(ax.cs_s.max()))
            lo = a if lo is None else max(lo, a); hi = c if hi is None else min(hi, c)
        return {"lo": lo, "hi": hi}
    except Exception as e:
        return {"error": str(e)}


def api_elements(b):
    rows = []
    try:
        for si, sec in enumerate(sorted(b["cfg"].get("sekcije", []), key=lambda s: s["od"]), 1):
            for role in ROLES[sec["tip"]]:
                sp = sec.get(role) or {}
                if not all(os.path.isfile(sp.get(k, "")) for k in ("h", "v", "x")): continue
                ax = _axis(sp)
                for e in ax.elems:
                    if e["s0"] + e["L"] < float(sec["od"]) or e["s0"] > float(sec["do"]) or e["L"] < 0.5: continue
                    R = e["R0"] if e["typ"] == "KRUZNI_LUK" else (e["R1"] if e["R0"] == float("inf") else e["R0"])
                    rows.append(dict(sek=si, os=role, no=e["no"], typ=e["typ"], s0=e["s0"], s1=e["s0"] + e["L"], R=None if R == float("inf") else R))
        return {"rows": rows}
    except Exception as e:
        return {"rows": rows, "error": str(e)}


def api_load(b):
    p = b["path"]
    try:
        cfg = pipeline.load_cfg(p)
        try: open(LAST, "w", encoding="utf-8").write(p)
        except Exception: pass
        return {"cfg": cfg, "path": p}
    except Exception as e:
        return {"error": str(e)}


def api_save(b):
    p = b["path"]
    try:
        json.dump(b["cfg"], open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        try: open(LAST, "w", encoding="utf-8").write(p)
        except Exception: pass
        return {"ok": True, "path": p}
    except Exception as e:
        return {"error": str(e)}


def api_readjson(b):
    try: return {"data": json.load(open(b["path"], encoding="utf-8"))}
    except Exception as e: return {"error": str(e)}


def api_validate(b):
    from .. import i18n
    i18n.set_lang(b.get('lang'))
    try: return {"errors": pipeline.validate(b["cfg"])}
    except Exception as e: return {"errors": [str(e)]}


def api_run(b):
    with S.lock:
        if S.run and not S.run["done"]: return {"error": "busy"}
        S.run = {"lines": [], "done": False, "outs": [], "error": None}
    run = S.run
    cfg = b["cfg"]; o = b.get("options", {})
    word, excel = bool(o.get("word", True)), bool(o.get("excel", True))
    sight = bool(o.get("preglednost")) or bool(o.get("optika"))
    cfg["optika"] = dict(cfg.get("optika") or {}, ukljuci=bool(o.get("optika")))
    if sight and not cfg.get("preglednost"): cfg["preglednost"] = {"ukljuci": True}
    def log(s): run["lines"].append(str(s))
    def work():
        try:
            outs, _ = pipeline.generate(cfg, cfg["izlaz"], log=log, word=word, excel=excel, sight=sight)
            run["outs"] = [os.path.abspath(x) for x in outs]
        except Exception as e:
            run["error"] = str(e); log("ERROR: " + str(e) + "\n" + traceback.format_exc())
        finally:
            run["done"] = True
    threading.Thread(target=work, daemon=True).start()
    return {"ok": True}


def api_log(b):
    r = S.run
    if not r: return {"lines": [], "done": True, "outs": [], "error": None, "next": 0}
    since = int(b.get("since", 0))
    return {"lines": r["lines"][since:], "next": len(r["lines"]), "done": r["done"], "outs": r["outs"] if r["done"] else [], "error": r["error"]}


def api_open(b):
    p = b["path"]
    try:
        if b.get("folder"): p = p if os.path.isdir(p) else os.path.dirname(p)
        if os.name == "nt": os.startfile(p)
        elif sys.platform == "darwin": subprocess.Popen(["open", p])
        else: subprocess.Popen(["xdg-open", p])
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def api_license(b):
    from .. import licenca
    try:
        lic = licenca.install(b["path"]); return {"ok": True, "text": licenca.describe(lic)}
    except licenca.LicencaError as e:
        return {"error": str(e)}


def api_ping(_):
    S.last_ping = time.time(); S.pinged = True; return {"ok": True}


def api_quit(_):
    threading.Timer(0.3, lambda: os._exit(0)).start(); return {"ok": True}


API = {"state": api_state, "ui": api_ui, "pick": api_pick, "detect": api_detect, "axisrange": api_axisrange, "elements": api_elements, "load": api_load, "save": api_save,
       "readjson": api_readjson, "validate": api_validate, "run": api_run, "log": api_log, "open": api_open, "license": api_license, "ping": api_ping, "quit": api_quit}


class H(BaseHTTPRequestHandler):
    server_version = "UNA"
    def log_message(self, *a): pass

    def _ok_host(self):
        h = (self.headers.get("Host") or "").split(":")[0]
        return h in ("127.0.0.1", "localhost")

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff"); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        if not self._ok_host(): return self._send(403, {"error": "host"})
        u = urlparse(self.path); path = u.path
        if path == "/": path = "/index.html"
        f = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not f.startswith(STATIC) or not os.path.isfile(f): return self._send(404, {"error": "not found"})
        data = open(f, "rb").read()
        if path == "/index.html": data = data.replace(b"__TOKEN__", S.token.encode())
        self._send(200, data, (mimetypes.guess_type(f)[0] or "application/octet-stream") + ("; charset=utf-8" if f.endswith((".html", ".js", ".css", ".svg")) else ""))

    def do_POST(self):
        if not self._ok_host(): return self._send(403, {"error": "host"})
        if self.headers.get("X-UNA-Token") != S.token: return self._send(403, {"error": "token"})
        name = urlparse(self.path).path.rstrip("/").split("/")[-1]
        fn = API.get(name)
        if not fn: return self._send(404, {"error": "unknown"})
        try:
            n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
            self._send(200, fn(body))
        except Exception as e:
            self._send(500, {"error": str(e), "trace": traceback.format_exc()})


# ------------------------------------------------------------------ prozor
def _browser_candidates():
    pf = [os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("LOCALAPPDATA", "")]
    c = []
    if os.name == "nt":
        for base in pf:
            if base: c += [os.path.join(base, r"Microsoft\Edge\Application\msedge.exe"), os.path.join(base, r"Google\Chrome\Application\chrome.exe"), os.path.join(base, r"BraveSoftware\Brave-Browser\Application\brave.exe")]
    for n in ("msedge", "microsoft-edge", "google-chrome", "chrome", "chromium", "chromium-browser", "brave-browser"):
        p = shutil.which(n)
        if p: c.append(p)
    return [p for p in c if p and os.path.isfile(p)]


def open_window(url, profile):
    for exe in _browser_candidates():
        try:
            args = [exe, f"--app={url}", f"--user-data-dir={profile}", "--window-size=1320,880", "--no-first-run", "--no-default-browser-check", "--disable-features=Translate"]
            return subprocess.Popen(args)
        except Exception:
            continue
    webbrowser.open(url)
    return None


def main(argv=None):
    argv = argv or sys.argv[1:]
    no_window = "--no-window" in argv
    port = 0
    for a in argv:
        if a.startswith("--port="): port = int(a.split("=")[1])
    srv = ThreadingHTTPServer(("127.0.0.1", port), H); port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    try: print("UNA UI:", url, flush=True)
    except Exception: pass                      # pakovana aplikacija bez konzole
    if no_window:
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt: return 0
    profile = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache"), "UNA", "window")
    os.makedirs(profile, exist_ok=True)
    proc = open_window(url, profile)
    # kraj: prozor zatvoren (proces završen) ili nema otkucaja (ping) >20 s nakon prvog
    while True:
        time.sleep(1.0)
        if S.pinged and time.time() - S.last_ping > 20: break
        if proc is not None and proc.poll() is not None and (not S.pinged or time.time() - S.last_ping > 6): break
        if proc is None and not S.pinged and time.time() - S.last_ping > 120: break
    return 0


def _log_dir():
    d = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache"), "UNA"); os.makedirs(d, exist_ok=True); return d


def run():
    """Ulazna tačka za pakovanu aplikaciju: greške idu u log i prikazuju se u poruci (nema konzole)."""
    try:
        return main()
    except Exception:
        tb = traceback.format_exc()
        try: open(os.path.join(_log_dir(), "error.log"), "a", encoding="utf-8").write(time.strftime("%Y-%m-%d %H:%M:%S ") + tb + "\n")
        except Exception: pass
        if os.name == "nt":
            try:
                import ctypes; ctypes.windll.user32.MessageBoxW(0, "UNA se nije mogla pokrenuti.\n\n" + tb[-600:] + "\n\nLog: " + os.path.join(_log_dir(), "error.log"), "UNA", 0x10)
            except Exception: pass
        return 1


if __name__ == "__main__":
    sys.exit(run())
