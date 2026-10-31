"""Osnovni testovi: proračun na primjeru, DXF izlaz, prepoznavanje ispisa. Pokretanje:  pytest -q"""
import os, shutil, sys, json
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from una import engine, parse, pipeline, licenca, preglednost as pg   # noqa: E402


@pytest.fixture(autouse=True)
def _bez_licence(monkeypatch):
    monkeypatch.setattr(licenca, "require", lambda *a, **k: {})
    monkeypatch.setattr(licenca, "describe", lambda *a, **k: "test")
    monkeypatch.setattr(licenca, "stamp", lambda *a, **k: {"id": "TEST"})


def _cfg(tmp):
    cfg = pipeline.load_cfg(os.path.join(ROOT, "primjer", "primjer_projekat.json"))
    cfg["izlaz"] = str(tmp); cfg["optika"] = {"ukljuci": False}
    return cfg


def test_prepoznavanje_ispisa():
    kinds = {f: parse.detect_kind(os.path.join(ROOT, "primjer", f)) for f in os.listdir(os.path.join(ROOT, "primjer")) if f.endswith(".TXT")}
    assert kinds["DESNA.TXT"] == "h" and kinds["DESNAUZDUZNI.TXT"] == "v" and kinds["DESNAPOPRECNINAGIBI.TXT"] == "x"


def test_vp_tabele():
    P = engine.Params({})
    assert abs(P.a - 0.7716) < 1e-3
    assert round(P.vpR(437.4)) == 100 and round(P.vpG(0)) == 130 and round(P.vpG(8)) == 75


def test_kriva_vuce_tegljaca():
    P = engine.Params({}); v = P.vozila[0]; W = v["m"] * P.g
    for gr, vk in ((2, 68), (7, 15)):
        vm = vk / 3.6
        otpor = P.frl0 * (1 + vm / P.frl_v) * W + 0.5 * P.rho * v["CdA"] * vm * vm + W * gr / 100
        assert abs(engine.ft_of(v, vm, W) - otpor) < 5


def test_proracun_i_preglednost(tmp_path):
    outs, _ = pipeline.generate(_cfg(tmp_path), str(tmp_path), log=lambda s: None, word=False, excel=True, sight=True)
    names = [os.path.basename(o) for o in outs]
    assert any(n.endswith(".xlsx") for n in names) and any(n.endswith(".dxf") for n in names)


def test_zone_racunske_brzine(tmp_path):
    cfg = _cfg(tmp_path); P0, sec0, c0, *_ = engine.run(cfg, log=lambda *a: None)
    s0, s1 = c0[0].SA, c0[0].SB; za, zb = s0 + (s1 - s0) * 0.4, s0 + (s1 - s0) * 0.6
    cfg2 = pipeline.load_cfg(os.path.join(ROOT, "primjer", "primjer_projekat.json")); cfg2["izlaz"] = str(tmp_path); cfg2["optika"] = {"ukljuci": False}
    cfg2["sekcije"][0]["zone_Vr"] = [{"od": za, "do": zb, "v": 60.0}]
    P, sec, cs, ax, fw, bw, hc = engine.run(cfg2, log=lambda *a: None)
    c = cs[0]; m = (c.S >= za) & (c.S <= zb)
    assert hc is False and abs(c.VRS[m].max() - 60) < 1e-9 and abs(c.VRS[~m].min() - P.Vr) < 1e-9
    assert c.VMX[m].max() <= 60 + P.dodatak_maxVr + 1e-9 and c.V[m].max() <= 80 + 1e-6      # u zoni Vp ≤ Vr_zone + dodatak
    outs, _ = pipeline.generate(cfg2, str(tmp_path), log=lambda s: None, word=False, excel=True, sight=True)
    assert any(o.endswith(".xlsx") for o in outs)


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc nije instaliran")
def test_word_elaborat(tmp_path):
    outs, _ = pipeline.generate(_cfg(tmp_path), str(tmp_path), log=lambda s: None, word=True, excel=False, sight=False)
    assert any(o.endswith(".docx") for o in outs)


def test_engleski_katalog_placeholderi():
    """Svaki prevod mora zadržati iste {n} / <<x>> oznake kao izvorni tekst."""
    import re
    cat = json.load(open(os.path.join(ROOT, "una", "data", "en.json"), encoding="utf-8"))
    sig = lambda s: (sorted(re.findall(r"\{\d*(?:![rsa])?(?::[^{}]*)?\}", s)), sorted(re.findall(r"<<\w+>>", s)))
    lose = [k[:60] for k, v in cat.items() if sig(k) != sig(v) and "{pk}" not in k]
    assert not lose, lose


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc nije instaliran")
def test_engleski_elaborat(tmp_path):
    from una import i18n
    cfg = _cfg(tmp_path); cfg["jezik"] = "en"
    try:
        outs, _ = pipeline.generate(cfg, str(tmp_path), log=lambda s: None, word=True, excel=True, sight=False)
    finally:
        i18n.set_lang("sr")
    names = [os.path.basename(o) for o in outs]
    assert any(n.startswith("Study_3") and n.endswith(".docx") for n in names)
    assert any(n.startswith("Calculation_") and n.endswith(".xlsx") for n in names)


def test_web_sucelje_api():
    """Lokalni poslužitelj web sučelja: statika, token i osnovni API pozivi."""
    import threading, urllib.request, urllib.error
    from http.server import ThreadingHTTPServer
    from una.webui import server
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.H); port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{port}"
        html = urllib.request.urlopen(base + "/").read().decode()
        assert "UNA" in html and "__TOKEN__" not in html
        req = urllib.request.Request(base + "/api/state", data=b"{}", method="POST", headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError) as ei: urllib.request.urlopen(req)       # bez tokena → 403
        assert ei.value.code == 403
        req = urllib.request.Request(base + "/api/validate", data=json.dumps({"cfg": {"sekcije": []}, "lang": "en"}).encode(), method="POST", headers={"X-UNA-Token": server.S.token})
        r = json.loads(urllib.request.urlopen(req).read())
        assert r["errors"] and "segment" in r["errors"][0].lower()
    finally:
        srv.shutdown()


def test_ifc_export():
    import os, re, tempfile
    from una import pipeline, licenca
    licenca.require = lambda *a, **k: {}; licenca.describe = lambda *a, **k: "test"; licenca.stamp = lambda *a, **k: {"id": "TEST"}
    cfg = pipeline.load_cfg(os.path.join(os.path.dirname(__file__), "..", "primjer", "primjer_projekat.json"))
    d = tempfile.mkdtemp(); cfg["ifc"] = True; cfg["jezik"] = "en"
    outs, _ = pipeline.generate(cfg, d, log=lambda *a: None, word=False, excel=False, sight=False)
    f = [o for o in outs if o.endswith(".ifc")]
    assert f, outs
    t = open(f[0], encoding="utf-8").read()
    assert "IFC4X3_ADD2" in t and t.count("IFCALIGNMENT(") == 3
    ids = set(re.findall(r"^#(\d+)=", t, re.M)); refs = set(re.findall(r"#(\d+)", t))
    assert refs <= ids


def test_npp_vizura_landxml():
    import os, json, tempfile, xml.etree.ElementTree as ET
    from una import pipeline, licenca, npp
    licenca.require = lambda *a, **k: {}; licenca.describe = lambda *a, **k: "test"; licenca.stamp = lambda *a, **k: {"id": "TEST"}
    cfg = pipeline.load_cfg(os.path.join(os.path.dirname(__file__), "..", "primjer", "primjer_projekat.json"))
    cfg["npp"] = {"zadani": "nasip", "dionice": [{"od": 1500, "do": 2300, "osovina": "desna", "profil": "tunel"}, {"od": 3000, "do": 3600, "osovina": "desna", "profil": "most"}]}
    cfg["vizura"] = True; cfg["landxml"] = True; cfg["jezik"] = "en"
    d = tempfile.mkdtemp()
    outs, _ = pipeline.generate(cfg, d, log=lambda *a: None, word=False, excel=False, sight=True)
    h = [o for o in outs if o.endswith(".html")]; x = [o for o in outs if o.endswith(".xml")]
    assert h and x, outs
    t = open(h[0], encoding="utf-8").read()
    assert "const DATA={" in t and '"tunel"' in t and '"most"' in t
    data = json.loads(t.split("const DATA=")[1].split(";\nconst L=")[0])
    assert data["routes"] and all(len(r["s"]) == r["n"] for r in data["routes"].values())
    root = ET.parse(x[0]).getroot(); ns = {"l": "http://www.landxml.org/schema/LandXML-1.2"}
    assert len(root.findall(".//l:Alignment", ns)) == 3 and root.findall(".//l:Spiral", ns)
    N = npp.resolve(cfg); assert npp.profile_at(N, "desna", 1800)[0] == "tunel" and npp.profile_at(N, "desna", 100)[0] == "nasip"


def _mini_landxml(path, cfg):
    """Najmanji mogući Civil 3D koridor sastavljen nad stvarnim osovinama projekta: Line elementi svakih 5 m, presjeci svakih 5 m, TIN."""
    import numpy as np
    from una import engine, preglednost as pg
    P, sections, cases, axes, fw, bw, hc = engine.run(cfg, log=lambda *a: None)
    ns = 'xmlns="http://www.landxml.org/schema/LandXML-1.2"'
    def al(name, c):
        st = np.arange(0, 101, 5.0); x0, y0, nx, ny = pg.case_frame(c, {}, st)           # x0 sjever, y0 istok
        el = "".join(f'<Line dir="0" length="5"><Start>{x0[i]} {y0[i]}</Start><End>{x0[i + 1]} {y0[i + 1]}</End></Line>' for i in range(len(st) - 1))
        cs = "".join(f'<CrossSect name="{name}" sta="{s}"><DesignCrossSectSurf name="Pave1" side="both"><CrossSectPnt>-3.85 0.1</CrossSectPnt><CrossSectPnt>3.85 0.1</CrossSectPnt></DesignCrossSectSurf>'
                     f'<DesignCrossSectSurf name="Top" side="both"><CrossSectPnt>-3.85 0.1</CrossSectPnt><CrossSectPnt>3.85 0.1</CrossSectPnt></DesignCrossSectSurf>'
                     f'<DesignCrossSectSurf name="Bankina" side="both"><CrossSectPnt>3.85 0.1</CrossSectPnt><CrossSectPnt>5.4 0.0</CrossSectPnt></DesignCrossSectSurf></CrossSect>' for s in range(0, 101, 5))
        return (f'<Alignment name="{name}" staStart="0" length="100"><CoordGeom>{el}</CoordGeom>'
                f'<Profile name="p"><ProfAlign name="p"><PVI>0 262</PVI><PVI>100 261</PVI></ProfAlign></Profile><CrossSects>{cs}</CrossSects></Alignment>')
    d1 = next(c for c in cases if c.key == "D1"); l1 = next(c for c in cases if c.key == "L1")
    x0, y0, _, _ = pg.case_frame(d1, {}, np.array([0.0, 50.0]))
    pts = "".join(f'<P id="{i + 1}">{n} {e} 100</P>' for i, (n, e) in enumerate([(x0[0] - 900, y0[0] - 900), (x0[0] - 900, y0[0] + 900), (x0[0] + 900, y0[0] + 900), (x0[0] + 900, y0[0] - 900)]))
    x = (f'<?xml version="1.0"?><LandXML {ns} version="1.2"><Surfaces><Surface name="T"><Definition surfType="TIN"><Pnts>{pts}</Pnts><Faces><F>1 2 3</F><F>1 3 4</F></Faces></Definition></Surface></Surfaces>'
         f'<Alignments>{al("DESNA", d1)}{al("LIJEVA", l1)}</Alignments></LandXML>')
    open(path, "w", encoding="utf-8").write(x)


def test_koridor_vizura():
    import os, json, tempfile
    from una import pipeline, licenca, corridor
    licenca.require = lambda *a, **k: {}; licenca.describe = lambda *a, **k: "test"; licenca.stamp = lambda *a, **k: {"id": "TEST"}
    d = tempfile.mkdtemp(); xp = os.path.join(d, "k.xml")
    cfg = pipeline.load_cfg(os.path.join(os.path.dirname(__file__), "..", "primjer", "primjer_projekat.json")); _mini_landxml(xp, cfg)
    cfg["koridor"] = {"datoteka": xp, "od": 10, "do": 90, "ograda_ofset": 0.78}; cfg["jezik"] = "en"
    outs, _ = pipeline.generate(cfg, d, log=lambda *a: None, word=False, excel=False, sight=True)
    h = [o for o in outs if os.path.basename(o).startswith("Corridor_drive")]
    assert h, outs
    t = open(h[0], encoding="utf-8").read()
    data = json.loads(t.split("const DATA=")[1].split(";\nconst L=")[0])
    assert set(data["routes"]) == {"F", "B"}
    F = data["routes"]["F"]; assert len(F["q"]) >= 10 and F["kind"][0] == "otvorena" and F["ray"][0][0] > 0
    assert abs(F["ob"][3][0] - (3.85 + 0.78)) < 0.02                   # prepreka iz UNA proračuna: 0,78 m od ivice kolovoza (širina trake iz koridora)
    assert abs(abs(F["latD"][3]) - 3.85 / 2) < 0.02                    # oko u sredini trake (UNA)
    assert data["routes"]["B"]["q"][0] == 0 and data["routes"]["B"]["s"][0] > data["routes"]["B"]["s"][-1]
    assert F["ray"][3][3] != 0 and F["lim"][3] != ""


def test_osovine_iz_landxml(tmp_path):
    """Osovine (horizontala, niveleta, poprečni nagib) čitaju se iz LandXML-a umjesto iz ispisa projektanta."""
    from una import parse, lx_axis
    cfg = _cfg(tmp_path); xp = str(tmp_path / "k.xml"); _mini_landxml(xp, cfg)
    info = lx_axis.alignments_info(xp, log=lambda *a: None)
    assert {a["name"] for a in info} == {"DESNA", "LIJEVA"} and all(a["hi"] > 90 for a in info)
    ax = parse.make_axis("t", xp + "#DESNA", xp + "#DESNA", xp + "#DESNA")
    assert abs(ax.vert(50)[0] - 261.5) < 0.01 and abs(ax.cross(50)) < 0.01 and ax.elems and ax.plan.shape[1] == 3
    assert parse.file_ok(xp + "#DESNA") and not parse.file_ok(xp + "x#DESNA")
