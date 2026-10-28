"""IFC 4.3 (IFC4X3_ADD2) izvoz osovina: IfcAlignment (horizontala + vertikala + 3D linija). Ručno pisan STEP (bez vanjskih biblioteka)."""
import math, uuid, datetime
from .i18n import _T

_B64 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"


def _g():
    """IFC GUID: 128 bita → 22 znaka (prvi znak 2 bita)."""
    n = uuid.uuid4().int; out = []
    for i in range(22):
        out.append(_B64[n % 64]); n //= 64
    return "".join(reversed(out))[:22]


def _s(x): return "'" + _esc(str(x)) + "'"


def _esc(t):
    out = []
    for ch in t.replace("\\", "\\\\").replace("'", "''"):
        out.append(ch if ord(ch) < 128 else "\\X2\\%04X\\X0\\" % ord(ch))
    return "".join(out)


def _f(x): return ("%.10g" % x) if ("%.10g" % x).count(".") or "e" in ("%.10g" % x) else "%.10g." % x


class _W:
    def __init__(self): self.lines = []; self.n = 0
    def add(self, txt): self.n += 1; self.lines.append(f"#{self.n}={txt};"); return f"#{self.n}"


def _horizontal(ax):
    """Segmenti horizontale: (tip, start Y, X, smjer [rad, IFC], R0, R1, L)."""
    segs = []
    for e in ax.elems:
        if e["L"] < 1e-6: continue
        th = math.pi / 2 - math.radians(e["nu0"])                 # azimut (od X, u smjeru Y) → IFC ugao od E ose suprotno kazaljci
        r0 = None if math.isinf(e["R0"]) else -e["R0"]            # R>0 = desno → IFC negativno
        r1 = None if math.isinf(e["R1"]) else -e["R1"]
        if e["typ"] == "PRAVAC": tp = "LINE"
        elif e["typ"] == "KRUZNI_LUK": tp = "CIRCULARARC"
        else: tp = "CLOTHOID"
        segs.append((tp, e["Y0"], e["X0"], th, r0, r1, e["L"]))
    return segs


def _vertical(ax, s_ref):
    """Segmenti vertikale iz prelomnih tačaka: (tip, start dist, dužina, z, g0, g1, R)."""
    P = ax.pis; segs = []
    s, z, g = P[0][0], P[0][1], P[0][3] / 100.0
    for i in range(1, len(P)):
        s_pi, z_pi, Rv, g_out, TZ, TK = P[i]; g_prev = P[i - 1][3] / 100.0
        curved = Rv and TK > TZ
        end_t = TZ if curved else s_pi
        if end_t - s > 1e-6:
            segs.append(("CONSTANTGRADIENT", s - s_ref, end_t - s, z, g_prev, g_prev, None)); z += g_prev * (end_t - s); s = end_t
        if curved:
            go = g_out / 100.0; sign = 1.0 if go > g_prev else -1.0
            segs.append(("PARABOLICARC", s - s_ref, TK - TZ, z, g_prev, go, sign * abs(Rv)))
            z = segs[-1][3] + (g_prev + go) / 2 * (TK - TZ); s = TK
    return segs


def write_ifc(path, project, axes, log=print):
    w = _W(); now = datetime.datetime.now().replace(microsecond=0).isoformat()
    head = ("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('ViewDefinition [Alignment-basedView]'),'2;1');\n"
            f"FILE_NAME('{_esc(path.split('/')[-1].split(chr(92))[-1])}','{now}',('UNA'),('UNA Road Engineering Analysis'),'UNA','UNA','');\n"
            "FILE_SCHEMA(('IFC4X3_ADD2'));\nENDSEC;\nDATA;\n")
    org = w.add(f"IFCORGANIZATION($,'UNA',$,$,$)")
    app = w.add(f"IFCAPPLICATION({org},'{_esc(__import__("una").__version__)}','UNA Road Engineering Analysis','UNA')")
    per = w.add("IFCPERSON($,'UNA',$,$,$,$,$,$)")
    pao = w.add(f"IFCPERSONANDORGANIZATION({per},{org},$)")
    oh = w.add(f"IFCOWNERHISTORY({pao},{app},$,.NOCHANGE.,$,$,$,{int(datetime.datetime.now().timestamp())})")
    o3 = w.add("IFCCARTESIANPOINT((0.,0.,0.))"); ax3 = w.add(f"IFCAXIS2PLACEMENT3D({o3},$,$)")
    ctx = w.add(f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,{ax3},$)")
    sub = w.add(f"IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Axis','Model',*,*,*,*,{ctx},$,.MODEL_VIEW.,$)")
    u1 = w.add("IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.)"); u2 = w.add("IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.)")
    ua = w.add(f"IFCUNITASSIGNMENT(({u1},{u2}))")
    prj = w.add(f"IFCPROJECT('{_g()}',{oh},{_s(project)},$,$,$,$,({ctx}),{ua})")
    pl = w.add(f"IFCLOCALPLACEMENT($,{ax3})")
    road = w.add(f"IFCROAD('{_g()}',{oh},{_s(project)},$,$,{pl},$,$,.ELEMENT.,$)")
    w.add(f"IFCRELAGGREGATES('{_g()}',{oh},$,$,{prj},({road}))")
    seen = set(); aligns = []
    for ax in axes:
        key = tuple(ax.files)
        if key in seen: continue
        seen.add(key)
        hs = _horizontal(ax); s_ref = ax.elems[0]["s0"]; vs = _vertical(ax, s_ref)
        # horizontalni segmenti
        hseg = []
        for tp, Y, X, th, r0, r1, L in hs:
            pt = w.add(f"IFCCARTESIANPOINT(({_f(Y)},{_f(X)}))")
            R0 = "$" if r0 is None else _f(r0); R1 = "$" if r1 is None else _f(r1)
            d = w.add(f"IFCALIGNMENTHORIZONTALSEGMENT($,$,{pt},{_f(th)},{R0},{R1},{_f(L)},$,.{tp}.)")
            hseg.append(w.add(f"IFCALIGNMENTSEGMENT('{_g()}',{oh},$,$,$,$,$,{d})"))
        last = ax.elems[-1]; ye, xe = ax.plan[-1][1], ax.plan[-1][2]
        pt = w.add(f"IFCCARTESIANPOINT(({_f(ye)},{_f(xe)}))")
        d = w.add(f"IFCALIGNMENTHORIZONTALSEGMENT($,$,{pt},{_f(math.pi / 2 - math.radians(last['nu0']))},$,$,0.,$,.LINE.)")
        hseg.append(w.add(f"IFCALIGNMENTSEGMENT('{_g()}',{oh},$,$,$,$,$,{d})"))
        hor = w.add(f"IFCALIGNMENTHORIZONTAL('{_g()}',{oh},$,$,$,$,$,0.)")
        w.add(f"IFCRELNESTS('{_g()}',{oh},$,$,{hor},({','.join(hseg)}))")
        # vertikalni segmenti
        vseg = []
        for tp, sd, L, z, g0, g1, R in vs:
            Rv = "$" if R is None else _f(R)
            d = w.add(f"IFCALIGNMENTVERTICALSEGMENT($,$,{_f(sd)},{_f(L)},{_f(z)},{_f(g0)},{_f(g1)},{Rv},.{tp}.)")
            vseg.append(w.add(f"IFCALIGNMENTSEGMENT('{_g()}',{oh},$,$,$,$,$,{d})"))
        if vs:
            tp, sd, L, z, g0, g1, R = vs[-1]; zend = z + (g0 + g1) / 2 * L
            d = w.add(f"IFCALIGNMENTVERTICALSEGMENT($,$,{_f(sd + L)},0.,{_f(zend)},{_f(g1)},{_f(g1)},$,.CONSTANTGRADIENT.)")
            vseg.append(w.add(f"IFCALIGNMENTSEGMENT('{_g()}',{oh},$,$,$,$,$,{d})"))
        ver = w.add(f"IFCALIGNMENTVERTICAL('{_g()}',{oh},$,$,$,$,$)") if vseg else None
        if ver: w.add(f"IFCRELNESTS('{_g()}',{oh},$,$,{ver},({','.join(vseg)}))")
        # 3D linija (prikaz u pregledačima)
        pts = [f"({_f(r[1])},{_f(r[2])},{_f(ax.vert(r[0])[0])})" for r in ax.plan]
        pl3 = w.add("IFCCARTESIANPOINTLIST3D((" + ",".join(pts) + "),$)")
        curve = w.add(f"IFCINDEXEDPOLYCURVE({pl3},$,.F.)")
        rep = w.add(f"IFCSHAPEREPRESENTATION({sub},'Axis','Curve3D',({curve}))")
        pds = w.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({rep}))")
        al = w.add(f"IFCALIGNMENT('{_g()}',{oh},{_s(ax.name)},$,$,{pl},{pds},.NOTDEFINED.)")
        nest = [x for x in (hor, ver) if x]
        w.add(f"IFCRELNESTS('{_g()}',{oh},$,$,{al},({','.join(nest)}))")
        aligns.append(al)
    if aligns: w.add(f"IFCRELAGGREGATES('{_g()}',{oh},$,$,{road},({','.join(aligns)}))")
    open(path, "w", encoding="ascii", newline="\n").write(head + "\n".join(w.lines) + "\nENDSEC;\nEND-ISO-10303-21;\n")
    log(f"IFC 4.3: {path} ({len(aligns)} IfcAlignment)")
    return path
