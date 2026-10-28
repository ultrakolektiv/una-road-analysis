"""Pun proračun na primjeru u zadanom jeziku:  python tools/run_lang.py sr|en OUTDIR"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from una import pipeline, licenca, i18n
licenca.require = lambda *a, **k: {}; licenca.describe = lambda *a, **k: "test"; licenca.stamp = lambda *a, **k: {"id": "TEST"}
lang, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
cfg = pipeline.load_cfg(os.path.join(ROOT, "primjer", "primjer_projekat.json")); cfg["izlaz"] = out
cfg["jezik"] = lang
outs, _ = pipeline.generate(cfg, out, log=print, word=True, excel=True, sight=True)
print("\n".join(sorted(os.path.basename(o) for o in outs)))
