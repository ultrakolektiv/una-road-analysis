"""Teren (TIN) iz LandXML <Surface>: rasterizacija u mrežu za brzo očitavanje visina (preglednost u usjecima, vožnja kroz koridor)."""
import os, hashlib
import numpy as np
from .i18n import _T, _TF


def _parse_surface(path, name=None):
    """Tačke i trouglovi prve (ili imenovane) površine. LandXML: <P id="..">N E Z</P>, <F>i j k</F>."""
    import xml.etree.ElementTree as ET
    ids, pts, faces = {}, [], []
    want = None; cur = None; depth_ok = False
    for ev, el in ET.iterparse(path, events=("start", "end")):
        tag = el.tag.rsplit("}", 1)[-1]
        if ev == "start":
            if tag == "Surface":
                nm = el.get("name", "")
                if want is None and (name is None or nm == name): want = nm; depth_ok = True
                else: depth_ok = False
            continue
        if not depth_ok:
            if tag != "Surface": el.clear()
            continue
        if tag == "P":
            v = el.text.split(); ids[el.get("id")] = len(pts); pts.append((float(v[0]), float(v[1]), float(v[2])))
        elif tag == "F":
            if el.get("i") == "1": el.clear(); continue          # nevidljivi trougao
            v = el.text.split()
            try: faces.append((ids[v[0]], ids[v[1]], ids[v[2]]))
            except KeyError: pass
        elif tag == "Surface":
            depth_ok = False; break
        if tag not in ("Pnts", "Faces", "Definition"): el.clear()
    return want, np.array(pts, float), np.array(faces, int)


class Teren:
    """Raster terena: z(E, N) bilinearno; NaN izvan TIN-a."""
    def __init__(self, path, cell=1.0, name=None, log=print):
        st = os.stat(path); key = hashlib.md5(f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime}|{cell}|{name}".encode()).hexdigest()[:16]
        cache = os.path.join(os.path.dirname(os.path.abspath(path)), f".una_teren_{key}.npz")
        if os.path.isfile(cache):
            d = np.load(cache); self.e0, self.n0, self.c = float(d["e0"]), float(d["n0"]), float(d["c"]); self.Z = d["Z"]; self.name = str(d["name"])
        else:
            import matplotlib.tri as mtri
            nm, P, F = _parse_surface(path, name)
            if len(P) < 3 or len(F) < 1: raise ValueError(_TF("Teren: u datoteci {0} nema TIN površine.", os.path.basename(path)))
            N, E, Zp = P[:, 0], P[:, 1], P[:, 2]                    # LandXML: sjever, istok, visina
            self.c = float(cell); self.e0 = float(E.min()); self.n0 = float(N.min())
            ne = int((E.max() - self.e0) / cell) + 2; nn = int((N.max() - self.n0) / cell) + 2
            tri = mtri.Triangulation(E, N, F); fi = mtri.LinearTriInterpolator(tri, Zp)
            Z = np.full((nn, ne), np.nan, np.float32); ee = self.e0 + np.arange(ne) * cell
            for r0 in range(0, nn, 256):
                r1 = min(nn, r0 + 256); NN, EE = np.meshgrid(self.n0 + np.arange(r0, r1) * cell, ee, indexing="ij")
                Z[r0:r1] = np.ma.filled(fi(EE, NN), np.nan)
            self.Z = Z; self.name = nm or ""
            try: np.savez_compressed(cache, e0=self.e0, n0=self.n0, c=self.c, Z=Z, name=self.name)
            except OSError: pass
        log(_TF("Teren: površina '{0}', raster {1} × {2} ćelija po {3} m.", self.name, self.Z.shape[1], self.Z.shape[0], self.c))

    def z(self, E, N):
        E = np.asarray(E, float); N = np.asarray(N, float)
        fx = (E - self.e0) / self.c; fy = (N - self.n0) / self.c
        ix = np.floor(fx).astype(int); iy = np.floor(fy).astype(int)
        ok = (ix >= 0) & (iy >= 0) & (ix < self.Z.shape[1] - 1) & (iy < self.Z.shape[0] - 1)
        ix = np.where(ok, ix, 0); iy = np.where(ok, iy, 0); tx = fx - ix; ty = fy - iy
        Z = self.Z
        v = (Z[iy, ix] * (1 - tx) * (1 - ty) + Z[iy, ix + 1] * tx * (1 - ty) + Z[iy + 1, ix] * (1 - tx) * ty + Z[iy + 1, ix + 1] * tx * ty)
        return np.where(ok, v, np.nan)
