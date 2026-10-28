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


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc nije instaliran")
def test_word_elaborat(tmp_path):
    outs, _ = pipeline.generate(_cfg(tmp_path), str(tmp_path), log=lambda s: None, word=True, excel=False, sight=False)
    assert any(o.endswith(".docx") for o in outs)
