"""LandXML 1.2 izvoz osovina i nivelete (Civil 3D, OpenRoads, Trimble, …): Import → LandXML → Alignments + Profiles."""
import math, datetime
from xml.sax.saxutils import escape, quoteattr
from .i18n import _TF


def _k(R): return 0.0 if (R is None or math.isinf(R)) else 1.0 / R


def _elem_pts(e):
    """Početak, kraj, tangente (azimut od sjevera, u smjeru kazaljke, rad) jednog elementa; Y istok, X sjever."""
    Y, X = e["Y0"], e["X0"]; nu = math.radians(e["nu0"]); k0, k1 = _k(e["R0"]), _k(e["R1"])
    n = max(2, int(math.ceil(e["L"] / 0.25))); d = e["L"] / n
    for j in range(n):
        kk = k0 + (k1 - k0) * (j + 0.5) / n; mid = nu + 0.5 * kk * d
        X += d * math.cos(mid); Y += d * math.sin(mid); nu += kk * d
    return (e["Y0"], e["X0"]), (Y, X), math.radians(e["nu0"]), nu


def _pi(p0, nu0, p1, nu1):
    """Presjek tangenti (Y, X)."""
    a = (math.sin(nu0), math.cos(nu0)); b = (math.sin(nu1), math.cos(nu1))
    det = a[0] * (-b[1]) - a[1] * (-b[0])
    if abs(det) < 1e-9: return ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    dy, dx = p1[0] - p0[0], p1[1] - p0[1]
    t = (dy * (-b[1]) - dx * (-b[0])) / det
    return (p0[0] + a[0] * t, p0[1] + a[1] * t)


def _pt(p): return f"{p[1]:.4f} {p[0]:.4f}"           # LandXML: northing easting


def _coordgeom(ax):
    out = []; chain = 0.0
    for e in ax.elems:
        if e["L"] < 1e-6: continue
        p0, p1, n0, n1 = _elem_pts(e); sta = e["s0"]
        if e["typ"] == "PRAVAC":
            out.append(f'<Line dir="{math.degrees(n0) % 360:.6f}" length="{e["L"]:.4f}" staStart="{sta:.4f}"><Start>{_pt(p0)}</Start><End>{_pt(p1)}</End></Line>')
        elif e["typ"] == "KRUZNI_LUK":
            R = abs(e["R0"]); rot = "cw" if e["R0"] > 0 else "ccw"; sgn = 1 if e["R0"] > 0 else -1
            c = (p0[0] + R * math.sin(n0 + sgn * math.pi / 2), p0[1] + R * math.cos(n0 + sgn * math.pi / 2))
            pi = _pi(p0, n0, p1, n1); delta = abs(n1 - n0)
            ch = 2 * R * math.sin(delta / 2)
            out.append(f'<Curve rot="{rot}" chord="{ch:.4f}" crvType="arc" delta="{math.degrees(delta):.6f}" dirStart="{math.degrees(n0) % 360:.6f}" dirEnd="{math.degrees(n1) % 360:.6f}" length="{e["L"]:.4f}" radius="{R:.4f}" staStart="{sta:.4f}">'
                       f'<Start>{_pt(p0)}</Start><Center>{_pt(c)}</Center><End>{_pt(p1)}</End><PI>{_pt(pi)}</PI></Curve>')
        else:   # PRIJELAZNICA (klotoida)
            Rs, Re = e["R0"], e["R1"]; rot = "cw" if (n1 - n0) > 0 else "ccw"
            if (Rs is not None and math.isinf(Rs)) and not math.isinf(Re): rot = "cw" if Re > 0 else "ccw"
            elif not math.isinf(Rs): rot = "cw" if Rs > 0 else "ccw"
            pi = _pi(p0, n0, p1, n1); A = e.get("A")
            const = f' constant="{A:.4f}"' if A else ""
            rs = "INF" if math.isinf(Rs) else f"{abs(Rs):.4f}"; re_ = "INF" if math.isinf(Re) else f"{abs(Re):.4f}"
            out.append(f'<Spiral length="{e["L"]:.4f}" radiusEnd="{re_}" radiusStart="{rs}" rot="{rot}" spiType="clothoid" theta="{math.degrees(abs(n1 - n0)):.6f}"{const} dirStart="{math.degrees(n0) % 360:.6f}" dirEnd="{math.degrees(n1) % 360:.6f}" staStart="{sta:.4f}">'
                       f'<Start>{_pt(p0)}</Start><PI>{_pt(pi)}</PI><End>{_pt(p1)}</End></Spiral>')
    return "\n        ".join(out)


def _profile(ax):
    items = []
    for i, (s_pi, z_pi, Rv, g_out, TZ, TK) in enumerate(ax.pis):
        L = TK - TZ
        if 0 < i < len(ax.pis) - 1 and L > 0.01: items.append(f'<ParaCurve length="{L:.4f}">{s_pi:.4f} {z_pi:.4f}</ParaCurve>')
        else: items.append(f"<PVI>{s_pi:.4f} {z_pi:.4f}</PVI>")
    return "\n          ".join(items)


def write_landxml(path, project, axes, log=print):
    now = datetime.datetime.now(); seen = set(); body = []
    for ax in axes:
        key = tuple(ax.files)
        if key in seen: continue
        seen.add(key)
        nm = quoteattr(ax.name)
        body.append(f'      <Alignment name={nm} length="{ax.length:.4f}" staStart="{ax.elems[0]["s0"]:.4f}" desc="UNA">\n        <CoordGeom>\n        {_coordgeom(ax)}\n        </CoordGeom>\n'
                    f'        <Profile name={nm}>\n          <ProfAlign name={nm}>\n          {_profile(ax)}\n          </ProfAlign>\n        </Profile>\n      </Alignment>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" version="1.2" date="%s" time="%s" language="English">\n'
           '  <Units><Metric areaUnit="squareMeter" linearUnit="meter" volumeUnit="cubicMeter" temperatureUnit="celsius" pressureUnit="HPA" angularUnit="decimal degrees" directionUnit="decimal degrees"/></Units>\n'
           '  <Project name=%s/>\n  <Application name="UNA Road Engineering Analysis" desc="UNA" manufacturer="UNA" version="1.3"/>\n  <Alignments>\n%s\n  </Alignments>\n</LandXML>\n') % (now.date().isoformat(), now.strftime("%H:%M:%S"), quoteattr(project), "\n".join(body))
    open(path, "w", encoding="utf-8").write(xml)
    log(_TF("LandXML (Civil 3D): {0} ({1} osovina)", path, len(seen)))
    return path
