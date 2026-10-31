"""Grafički prozor (tkinter) – čarobnjak za unos sekcija i pokretanje proračuna."""
import os, re, json, threading, queue, traceback, copy
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from . import pipeline, engine
from .parse import Axis, detect_kind

TIP_OPIS = [
    ("razdvojene", "Dvije odvojene osovine (desni i lijevi kolovoz)"),
    ("centralna", "Centralna osovina (jedan ispis, oba smjera vožnje)"),
    ("jedna_naprijed", "Jedna osovina – samo smjer rastuće stacionaže"),
    ("jedna_nazad", "Jedna osovina – samo smjer opadajuće stacionaže"),
]
ROLES = {"razdvojene": [("desna", "DESNA osovina (desni kolovoz, vožnja u smjeru stacionaže)"), ("lijeva", "LIJEVA osovina (lijevi kolovoz, vožnja suprotno stacionaži)")],
         "centralna": [("centralna", "CENTRALNA osovina")],
         "jedna_naprijed": [("osovina", "Osovina")], "jedna_nazad": [("osovina", "Osovina")]}
TIP_KR = {"PRAVAC": "pravac", "KRUZNI_LUK": "kružni luk", "PRIJELAZNICA": "prijelaznica"}
FILE_LABEL = {"h": "Horizontalna osovina (elementi)", "v": "Uzdužni profil (prelomne tačke)", "x": "Poprečni nagibi"}


def fnum(s, default=None):
    s = str(s).strip().replace(",", ".")
    if s == "": return default
    return float(s)


def parse_list(txt):
    """'3.5, 3.5' / '3,5; 3,5' / '3.5 3.5' → [3.5, 3.5] (zarez uz razmak ili ';' razdvaja, zarez bez razmaka je decimalni)."""
    t = str(txt).replace(";", " ").replace(", ", " ").strip()
    return [float(x.replace(",", ".")) for x in t.split() if x]


def sec_summary(s):
    roles = ROLES[s["tip"]]
    fl = []
    for r, _ in roles:
        sp = s.get(r) or {}
        fl.append(os.path.basename(sp.get("h", "?")))
    cap = "; ".join(f"Vr {z['v']:.0f} km/h na {z['od']}–{z['do']}" for z in s.get("zone_Vr", []))
    return fl, cap


class AxisPicker(ttk.LabelFrame):
    def __init__(self, master, title, spec=None):
        super().__init__(master, text=title, padding=6)
        self.vars = {k: tk.StringVar(value=(spec or {}).get(k, "")) for k in ("h", "v", "x")}
        self.cs = tk.StringVar(value="" if not spec or spec.get("cs_col") is None else str(spec["cs_col"] + 1))
        sp_ = spec or {}
        def _sv(k):
            v = sp_.get(k)
            return tk.StringVar(value="" if v is None else (", ".join(f"{x:g}" for x in v) if isinstance(v, (list, tuple)) else str(v)))
        self.pf = {"trake_desno": _sv("trake_desno"), "trake_lijevo": _sv("trake_lijevo"), "razdjelni_pola": _sv("razdjelni_pola"), "ofset_desno": _sv("ofset_desno" if sp_.get("ofset_desno") is not None else "ofset"), "ofset_lijevo": _sv("ofset_lijevo")}
        for i, k in enumerate(("h", "v", "x")):
            ttk.Label(self, text=FILE_LABEL[k]).grid(row=i, column=0, sticky="w")
            ttk.Entry(self, textvariable=self.vars[k], width=70).grid(row=i, column=1, padx=4, pady=1)
            ttk.Button(self, text="…", width=3, command=lambda k=k: self.pick(k)).grid(row=i, column=2)
        ttk.Button(self, text="Odaberi sva 3 fajla odjednom (automatsko prepoznavanje)", command=self.pick3).grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))
        f = ttk.Frame(self); f.grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Label(f, text="Kolona poprečnog nagiba LIJEVE strane (redni broj trake, prazno = automatski):").pack(side="left")
        ttk.Entry(f, textvariable=self.cs, width=4).pack(side="left", padx=4)
        f2 = ttk.LabelFrame(self, text="Preglednost – poprečni profil i ofset osovine vozne trake (prazno = podrazumijevano)", padding=4); f2.grid(row=5, column=0, columnspan=3, sticky="we", pady=(4, 0))
        for i, (k, lab) in enumerate((("razdjelni_pola", "Centralna osovina: POLA širine razdjelnog pojasa [m] (osovina puta → unutrašnja ivica kolovoza; 0 ili prazno ako nema):"),
                                      ("trake_desno", "Širine traka DESNO od osovine puta [m] (centralna: desni kolovoz, od unutrašnje ivice; npr. 3.5, 3.5):"),
                                      ("trake_lijevo", "Širine traka LIJEVO od osovine puta [m] (centralna: lijevi kolovoz, od unutrašnje ivice; npr. 3.5, 3.5):"),
                                      ("ofset_desno", "Osovina oka vozača DESNO od osovine kolovoza [m] (prazno = pola prve trake):"),
                                      ("ofset_lijevo", "Osovina oka vozača LIJEVO od osovine kolovoza [m] (prazno = pola prve trake):"))):
            ttk.Label(f2, text=lab).grid(row=i, column=0, sticky="w"); ttk.Entry(f2, textvariable=self.pf[k], width=14).grid(row=i, column=1, padx=4, pady=1)

    def pick(self, k):
        p = filedialog.askopenfilename(title=FILE_LABEL[k], filetypes=[("Ispisi", "*.txt *.TXT *.dat *.lst *.*")])
        if p: self.vars[k].set(p)

    def pick3(self):
        ps = filedialog.askopenfilenames(title="Odaberite 3 datoteke osovine (horizontala, uzdužni, poprečni)")
        if not ps: return
        found = {}
        for p in ps:
            try: found.setdefault(detect_kind(p), p)
            except Exception as e: messagebox.showerror("Greška", f"{p}\n{e}")
        for k, p in found.items(): self.vars[k].set(p)
        if len(found) < 3: messagebox.showwarning("Upozorenje", "Nisu prepoznate sve tri vrste datoteka – dopunite ručno.")

    def get(self):
        d = {k: v.get().strip() for k, v in self.vars.items()}
        c = self.cs.get().strip()
        if c: d["cs_col"] = int(c) - 1
        for k in ("trake_desno", "trake_lijevo"):
            t = parse_list(self.pf[k].get())
            if t: d[k] = t
        for k in ("razdjelni_pola", "ofset_desno", "ofset_lijevo"):
            o = self.pf[k].get().strip().replace(",", ".")
            if o: d[k] = float(o)
        return d

    def axis_range(self):
        d = self.get()
        if not all(os.path.isfile(d[k]) for k in ("h", "v", "x")): return None
        ax = Axis("tmp", d["h"], d["v"], d["x"], cs_col=d.get("cs_col"))
        return ax


class SectionDialog(tk.Toplevel):
    def __init__(self, master, sec=None):
        super().__init__(master)
        self.title("Sekcija trase"); self.result = None; self.transient(master); self.grab_set()
        sec = sec or {"tip": "razdvojene", "od": 0, "do": 0}
        top = ttk.Frame(self, padding=8); top.pack(fill="both", expand=True)
        ttk.Label(top, text="Vrsta sekcije:").grid(row=0, column=0, sticky="w")
        self.tip = tk.StringVar(value=dict(TIP_OPIS)[sec["tip"]])
        cb = ttk.Combobox(top, textvariable=self.tip, values=[t[1] for t in TIP_OPIS], state="readonly", width=60); cb.grid(row=0, column=1, columnspan=3, sticky="w", pady=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self.rebuild())
        ttk.Label(top, text="Stacionaža OD [m]:").grid(row=1, column=0, sticky="w"); self.od = tk.StringVar(value=str(sec["od"])); ttk.Entry(top, textvariable=self.od, width=14).grid(row=1, column=1, sticky="w")
        ttk.Label(top, text="DO [m]:").grid(row=1, column=2, sticky="e"); self.do = tk.StringVar(value=str(sec["do"])); ttk.Entry(top, textvariable=self.do, width=14).grid(row=1, column=3, sticky="w")
        ttk.Button(top, text="Postavi OD/DO prema ispisima", command=self.autorange).grid(row=1, column=4, padx=6)
        self.body = ttk.Frame(top); self.body.grid(row=2, column=0, columnspan=5, sticky="we", pady=6)
        self.sec0 = sec; self.pickers = {}
        cf = ttk.LabelFrame(top, text="Zone računske brzine Vr (opciono) – jedan red: OD; DO; Vr km/h", padding=6); cf.grid(row=3, column=0, columnspan=5, sticky="we")
        self.caps = tk.Text(cf, width=70, height=3); self.caps.pack()
        self.caps.insert("1.0", "\n".join(f"{z['od']}; {z['do']}; {z['v']}" for z in sec.get("zone_Vr", [])))
        ttk.Label(cf, text="Unutar zone proračun (Vp, Rmin, zrake preglednosti) koristi računsku brzinu zone.").pack(anchor="w")
        bf = ttk.Frame(top); bf.grid(row=4, column=0, columnspan=5, sticky="e", pady=6)
        ttk.Button(bf, text="U redu", command=self.ok).pack(side="left", padx=4); ttk.Button(bf, text="Otkaži", command=self.destroy).pack(side="left")
        self.rebuild()

    def cur_tip(self):
        inv = {v: k for k, v in TIP_OPIS}; return inv[self.tip.get()]

    def rebuild(self):
        old = {r: p.get() for r, p in self.pickers.items()}
        for w in self.body.winfo_children(): w.destroy()
        self.pickers = {}
        for r, title in ROLES[self.cur_tip()]:
            spec = old.get(r) or self.sec0.get(r)
            p = AxisPicker(self.body, title, spec); p.pack(fill="x", pady=3); self.pickers[r] = p

    def autorange(self):
        lo, hi = None, None
        try:
            for r, p in self.pickers.items():
                ax = p.axis_range()
                if ax is None: raise ValueError("Najprije odaberite sve tri datoteke za svaku osovinu.")
                a, b = max(ax.s_min, float(ax.cs_s.min())), min(ax.s_max, float(ax.cs_s.max()))
                lo = a if lo is None else max(lo, a); hi = b if hi is None else min(hi, b)
            self.od.set(f"{max(lo, 0) if lo < 0 else lo:.3f}".rstrip("0").rstrip(".")); self.do.set(f"{hi:.3f}".rstrip("0").rstrip("."))
            messagebox.showinfo("Raspon", f"Zajednički raspon ispisa: {lo:.3f} – {hi:.3f} m. Prilagodite OD/DO prema stvarnoj sekciji.")
        except Exception as e:
            messagebox.showerror("Greška", str(e))

    def ok(self):
        try:
            s = {"tip": self.cur_tip(), "od": fnum(self.od.get()), "do": fnum(self.do.get())}
            if s["od"] is None or s["do"] is None or s["do"] <= s["od"]: raise ValueError("Stacionaže OD / DO nisu ispravne (DO mora biti veće od OD).")
            for r, p in self.pickers.items():
                d = p.get()
                for k in ("h", "v", "x"):
                    if not os.path.isfile(d[k]): raise ValueError(f"Datoteka ne postoji: {d[k] or '(prazno)'}")
                s[r] = d
            caps = []
            for ln in self.caps.get("1.0", "end").splitlines():
                ln = ln.strip()
                if not ln: continue
                a = [fnum(x) for x in ln.replace(";", " ").replace("\t", " ").split()]
                if len(a) != 3 or None in a: raise ValueError(f"Zona Vr: neispravan red '{ln}' (OD; DO; Vr).")
                caps.append({"od": a[0], "do": a[1], "v": a[2]})
            if caps: s["zone_Vr"] = caps
            self.result = s; self.destroy()
        except Exception as e:
            messagebox.showerror("Greška", str(e), parent=self)


class ParamDialog(tk.Toplevel):
    SCAL = [("korak", "Korak proračuna Δs [m]"), ("a", "Ubrzanje a [m/s²]"), ("d", "Usporenje d [m/s²]"), ("ulazna_brzina", "Ulazna brzina na početku trase [km/h] (prazno = Vr + dodatak)"),
            ("dodatak_maxVr", "max Vr = Vr + [km/h]"), ("maxVr_tab", "max Vr prema tabeli 3-04 Priloga 2 [km/h] (prazno = bez ograničenja; max Vr = manje od Vr+dodatak i ove vrijednosti)"), ("obrazac_puta", "Put promjene brzine po obrascu 0,1·Vsr·ΔV (slika 3-09): 1 = da, 0 = kinematika s a i d"), ("max_nagib", "Referentni najveći podužni nagib [%]"), ("rho", "Gustina vazduha ρ [kg/m³]"), ("b", "Specifična potrošnja b [l/kWh]"), ("prazan_hod", "Prazan hod [l/h]")]
    TABS = [("Vr_tab", "Vr [km/h]"), ("Rmin_tab", "Rmin [m]"), ("fT", "fT"), ("fR", "fR"), ("iN_tab", "Vp–iN: nagib iN [%]"), ("ViN_tab", "Vp–iN: brzina [km/h]")]
    VEH = [("naziv", "Naziv", 34), ("kratko", "Kratko", 9), ("m", "m [kg]", 8), ("P", "P [kW]", 7), ("CdA", "CdA [m²]", 7), ("eta", "η", 5), ("vlim", "vlim", 6), ("gam", "γm", 5), ("mu", "μ", 5), ("b", "b l/kWh", 7), ("prazan_hod", "prazan hod l/h", 8)]

    def __init__(self, master, cfg):
        super().__init__(master); self.title("Napredni parametri"); self.transient(master); self.grab_set(); self.result = None
        D = engine.DEFAULTS; self.D = D
        f = ttk.Frame(self, padding=8); f.pack(fill="both", expand=True)
        self.sv = {}
        for i, (k, lab) in enumerate(self.SCAL):
            ttk.Label(f, text=lab).grid(row=i, column=0, sticky="w"); v = cfg.get(k, D.get(k)); v = int(v) if isinstance(v, bool) else v; self.sv[k] = tk.StringVar(value="" if v is None else str(v)); ttk.Entry(f, textvariable=self.sv[k], width=14).grid(row=i, column=1, sticky="w", pady=1)
        r0 = len(self.SCAL)
        ttk.Label(f, text="Tablice (vrijednosti odvojene zarezom ili razmakom; Vp–R koristi Vr i Rmin tablicu):").grid(row=r0, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.tv = {}
        for i, (k, lab) in enumerate(self.TABS):
            ttk.Label(f, text=lab).grid(row=r0 + 1 + i, column=0, sticky="w"); self.tv[k] = tk.StringVar(value=", ".join(str(x) for x in cfg.get(k, D[k]))); ttk.Entry(f, textvariable=self.tv[k], width=70).grid(row=r0 + 1 + i, column=1, columnspan=2, sticky="w")
        r1 = r0 + 1 + len(self.TABS)
        ttk.Label(f, text="Vozila za dinamički proračun (poglavlje 5; vlim prazno = max Vr, b i prazan hod prazno = opšte vrijednosti):").grid(row=r1, column=0, sticky="w", pady=(8, 0))
        vf = ttk.Frame(f); vf.grid(row=r1 + 1, column=0, columnspan=3, sticky="w")
        for j, (k, lab, w) in enumerate(self.VEH): ttk.Label(vf, text=lab).grid(row=0, column=j)
        self.vrows = []; self.vf = vf
        for v in cfg.get("vozila", D["vozila"]): self.add_veh(v)
        bf = ttk.Frame(f); bf.grid(row=r1 + 2, column=0, columnspan=3, sticky="we", pady=6)
        ttk.Button(bf, text="Dodaj vozilo", command=lambda: self.add_veh(dict(naziv="novo vozilo", kratko="Vozilo", m=30000, P=300, CdA=5.0, eta=0.9, vlim=80, gam=1.06, mu=0.5))).pack(side="left")
        ttk.Button(bf, text="Ukloni zadnje", command=self.del_veh).pack(side="left", padx=4)
        ttk.Button(bf, text="Vrati podrazumijevano", command=self.reset).pack(side="left", padx=4)
        ttk.Button(bf, text="U redu", command=self.ok).pack(side="right"); ttk.Button(bf, text="Otkaži", command=self.destroy).pack(side="right", padx=4)

    def add_veh(self, v):
        row = len(self.vrows) + 1; vs = {}
        for j, (k, lab, w) in enumerate(self.VEH):
            vs[k] = tk.StringVar(value="" if v.get(k) is None else str(v.get(k, ""))); ttk.Entry(self.vf, textvariable=vs[k], width=w).grid(row=row, column=j, padx=1, pady=1)
        vs["_extra"] = {k: x for k, x in v.items() if k not in [e[0] for e in self.VEH]}      # npr. kriva sile vuče Ft_kriva – čuva se nepromijenjena
        self.vrows.append(vs)

    def del_veh(self):
        if len(self.vrows) <= 1: return
        self.vrows.pop(); last = max(w.grid_info()["row"] for w in self.vf.winfo_children())
        for w in self.vf.winfo_children():
            if w.grid_info()["row"] == last: w.destroy()

    def reset(self):
        D = self.D
        for k, _ in self.SCAL: self.sv[k].set("" if D.get(k) is None else str(int(D.get(k)) if isinstance(D.get(k), bool) else D.get(k)))
        for k, _ in self.TABS: self.tv[k].set(", ".join(str(x) for x in D[k]))

    def ok(self):
        try:
            res = {}
            for k, _ in self.SCAL:
                x = fnum(self.sv[k].get()); 
                if x is not None: res[k] = x
                elif k in ("ulazna_brzina", "maxVr_tab"): res[k] = None
            for k, _ in self.TABS:
                arr = [float(x) for x in self.tv[k].get().replace(",", " ").replace(";", " ").split()]
                res[k] = arr
            if len(res["Vr_tab"]) != len(res["Rmin_tab"]) or len(res["Vr_tab"]) != len(res["fR"]) or len(res["Vr_tab"]) != len(res["fT"]): raise ValueError("Tablice Vr, Rmin, fT i fR moraju imati isti broj vrijednosti.")
            if len(res["iN_tab"]) != len(res["ViN_tab"]): raise ValueError("Tablica Vp–iN: broj nagiba i brzina mora biti isti.")
            if res["Rmin_tab"] != sorted(res["Rmin_tab"]) or res["iN_tab"] != sorted(res["iN_tab"]): raise ValueError("Vrijednosti Rmin i iN moraju biti rastuće.")
            vs = []
            for r in self.vrows:
                d = {}
                for k, lab, w in self.VEH:
                    t_ = r[k].get().strip().replace(",", ".")
                    d[k] = t_ if k in ("naziv", "kratko") else (None if (t_ == "" and k in ("vlim", "b", "prazan_hod", "P")) else float(t_))
                d.update(r.get("_extra", {})); vs.append(d)
            res["vozila"] = vs; self.result = res; self.destroy()
        except Exception as e:
            messagebox.showerror("Greška", str(e), parent=self)


class NotesDialog(tk.Toplevel):
    def __init__(self, master, cfg):
        super().__init__(master); self.title("Tekst za elaborat"); self.transient(master); self.grab_set(); self.result = None
        f = ttk.Frame(self, padding=8); f.pack(fill="both", expand=True)
        ttk.Label(f, text="Datum / verzija (na naslovnoj strani):").pack(anchor="w"); self.dat = tk.StringVar(value=cfg.get("datum", "")); ttk.Entry(f, textvariable=self.dat, width=70).pack(fill="x")
        ttk.Label(f, text="Dodatni opis trase (ubacuje se u Uvod):").pack(anchor="w", pady=(8, 0)); self.opis = tk.Text(f, width=80, height=4); self.opis.pack(); self.opis.insert("1.0", cfg.get("opis_sekcija", ""))
        ttk.Label(f, text="Dodatne napomene / pretpostavke (jedna po redu, idu u Prilog C):").pack(anchor="w", pady=(8, 0)); self.nap = tk.Text(f, width=80, height=5); self.nap.pack()
        nn = cfg.get("napomene", []); nn = nn if isinstance(nn, list) else [nn]; self.nap.insert("1.0", "\n".join(nn))
        bf = ttk.Frame(f); bf.pack(fill="x", pady=6); ttk.Button(bf, text="U redu", command=self.ok).pack(side="right"); ttk.Button(bf, text="Otkaži", command=self.destroy).pack(side="right", padx=4)

    def ok(self):
        self.result = {"datum": self.dat.get().strip(), "opis_sekcija": self.opis.get("1.0", "end").strip(),
                       "napomene": [x.strip() for x in self.nap.get("1.0", "end").splitlines() if x.strip()]}
        self.destroy()


class TemplateDialog(tk.Toplevel):
    FIELDS = [("folder_sr", "Folder – naziv (SR), upisuje se u polje 'FOLDER XX – NAZIV FOLDERA'"), ("folder_en", "Folder – naziv (ENG)"), ("datum", "Datum na naslovnoj strani (npr. Oktobar/October 2026)"),
              ("vodeci", "Vodeći projektant (isto za SR i ENG)"), ("odgovorni", "Odgovorni projektant"), ("saradnici", "Saradnici na projektu"), ("saradnici_en", "Saradnici (ENG; prazno = isto)"),
              ("naslov_izvjestaj", "Naslov poglavlja u tekstualnoj dokumentaciji (SR / ENG)"), ("naslov_numericki", "Naslov u numeričkoj dokumentaciji (SR / ENG)"), ("naslov_graficki", "Naslov u grafičkoj dokumentaciji (SR / ENG)")]

    def __init__(self, master, cfg):
        super().__init__(master); self.title("Word template (dodatni izlaz)"); self.transient(master); self.grab_set(); self.result = None
        t = cfg.get("template") or {}
        f = ttk.Frame(self, padding=8); f.pack(fill="both", expand=True)
        ttk.Label(f, text="Template (.docx) – ako je odabran, pored izvornog elaborata pravi se i elaborat u templatu:").grid(row=0, column=0, columnspan=3, sticky="w")
        self.file = tk.StringVar(value=t.get("file", "")); ttk.Entry(f, textvariable=self.file, width=70).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Button(f, text="…", width=3, command=self.pick).grid(row=1, column=2, sticky="w")
        self.v = {}
        for i, (k, lab) in enumerate(self.FIELDS):
            ttk.Label(f, text=lab).grid(row=2 + i, column=0, sticky="w", pady=1); self.v[k] = tk.StringVar(value=t.get(k, "")); ttk.Entry(f, textvariable=self.v[k], width=70).grid(row=2 + i, column=1, columnspan=2, sticky="w")
        ttk.Label(f, text="Prazna polja ostaju kakva su u templatu (žuto označena).").grid(row=2 + len(self.FIELDS), column=0, columnspan=3, sticky="w", pady=4)
        bf = ttk.Frame(f); bf.grid(row=3 + len(self.FIELDS), column=0, columnspan=3, sticky="e")
        ttk.Button(bf, text="Ukloni template", command=self.clear).pack(side="left", padx=4); ttk.Button(bf, text="U redu", command=self.ok).pack(side="left"); ttk.Button(bf, text="Otkaži", command=self.destroy).pack(side="left", padx=4)

    def pick(self):
        p = filedialog.askopenfilename(title="Word template", filetypes=[("Word", "*.docx *.dotx")])
        if p: self.file.set(p)

    def clear(self): self.result = {}; self.destroy()

    def ok(self):
        d = {k: v.get().strip() for k, v in self.v.items() if v.get().strip()}
        if self.file.get().strip(): d["file"] = self.file.get().strip()
        if d.get("file") and not os.path.isfile(d["file"]): messagebox.showerror("Greška", "Template ne postoji.", parent=self); return
        self.result = d; self.destroy()


class PregDialog(tk.Toplevel):
    FIELDS = [("ofset", "Podrazumijevana širina trake / 2 – ofset osovine vozne trake [m] (koristi se kad nije unesen u sekciji)", 1.75, False),
              ("h_oka", "Visina oka vozača iznad nivelete [m]", 1.0, False), ("h_prepreke", "Visina predmeta iznad nivelete [m] (prazno = automatski po Tabeli 29: h2 = f(Vp), 0–0,15 m)", "", True),
              ("dodatak_L", "Dodatak na zaustavnu dužinu Lz iz dijagrama [m] (npr. 7 za puteve A kategorije; 0 = bez dodatka)", 0.0, False),
              ("L_zahtijevano", "ZAHTIJEVANA dužina zrake L [m] – crta se poseban crtež (prazno = bez tog crteža)", "", True),
              ("Lmax", "Najveća dužina zrake koja se traži u proračunu očekivane preglednosti [m]", 500.0, False),
              ("korak_crtez", "Razmak zraka na crtežu [m]", 20.0, False), ("korak_proracun", "Korak proračuna zraka i omotača [m]", 5.0, False),
              ("mjerilo", "Mjerilo crteža (1:N; određuje veličinu teksta i debljinu linija)", 1000, False),
              ("ivica_debljina", "Debljina crvene linije ivice kolovoza [mm na papiru]", 0.3, False)]
    PRE_HELP = ("3) Izuzeci po stacionaži (npr. most, tunel) – po jedan red:  sekcija; osovina; od-do; tip (ili ofset u m); strana\n"
                "  osovina: desna / lijeva / centralna / osovina (ili * za sve);  od-do: stacionaže (npr. 7700-7800)\n"
                "  strana: unutra (prema centru krivine, podrazumijevano) / vani / desno / lijevo (smjer stacionaže)\n"
                "  primjer:  2; centralna; 7700-7800; most          (prepreke za pojedini element zadajte u tabeli ispod)")

    def __init__(self, master, cfg):
        super().__init__(master); self.title("Preglednost (zrake, zahtijevana i očekivana preglednost)"); self.transient(master); self.grab_set(); self.result = None; self.cfg = cfg
        t = cfg.get("preglednost") or {}
        f = ttk.Frame(self, padding=8); f.pack()
        self.v = {}; r = 0
        for k, lab, dv, opt in self.FIELDS:
            ttk.Label(f, text=lab).grid(row=r, column=0, sticky="w", pady=1); self.v[k] = tk.StringVar(value=str(t.get(k, dv) if t.get(k) is not None else dv)); ttk.Entry(f, textvariable=self.v[k], width=10).grid(row=r, column=1, sticky="w", padx=6); r += 1
        sd = t.get("strane") or ["desno", "lijevo"]
        self.sd = tk.BooleanVar(value="desno" in sd); self.sl = tk.BooleanVar(value="lijevo" in sd)
        sf = ttk.Frame(f); sf.grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
        ttk.Label(sf, text="Zrake crtati iz osovine oka vozača na strani osovine kolovoza:").pack(side="left")
        ttk.Checkbutton(sf, text="desna traka", variable=self.sd).pack(side="left", padx=6); ttk.Checkbutton(sf, text="lijeva traka", variable=self.sl).pack(side="left")
        self.iv = tk.BooleanVar(value=t.get("ivice", True)); ttk.Checkbutton(f, text="Crtaj ivice kolovoza (crvene linije) prema unesenim širinama traka", variable=self.iv).grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
        self.png = tk.BooleanVar(value=bool(t.get("png"))); ttk.Checkbutton(f, text="Dodatno napravi PNG pregled crteža", variable=self.png).grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
        pf = ttk.LabelFrame(f, text="Očekivana preglednost – prepreke (ofset od krajnje ivice kolovoza)", padding=6); pf.grid(row=r, column=0, columnspan=2, sticky="we", pady=6); r += 1
        ttk.Label(pf, text="1) Tipovi prepreke i njihov ofset od krajnje ivice kolovoza – po jedan red:  naziv; ofset [m]   (npr. most; 1.17)", foreground="#333").pack(anchor="w")
        self.tip = tk.Text(pf, width=100, height=4); self.tip.pack()
        tv = t.get("tipovi_prepreka") or {"otvorena trasa": "", "most": 1.17, "tunel": ""}
        self.tip.insert("1.0", "\n".join(f"{k}; {v}" for k, v in tv.items()))
        zf = ttk.Frame(pf); zf.pack(anchor="w", pady=3)
        ttk.Label(zf, text="2) Tip koji važi za SVE krivine (radijusi i prijelaznice), ako nije drugačije zadano:").pack(side="left")
        self.ztip = tk.StringVar(value=t.get("zadani_tip", "")); ttk.Entry(zf, textvariable=self.ztip, width=22).pack(side="left", padx=4)
        ttk.Label(pf, text="3) Izuzeci po stacionaži (npr. most, tunel koji zahvata samo dio elementa) – dodajte pomoću dugmeta, upisuje se od–do i ofset/tip prepreke:", foreground="#333").pack(anchor="w", pady=3)
        ef = ttk.Frame(pf); ef.pack(fill="x")
        self.exc = [dict(e) for e in (t.get("prepreke") or []) if e.get("element") in (None, "")]
        self.xt = ttk.Treeview(ef, columns=("sek", "os", "od", "do", "prep", "str"), show="headings", height=4)
        for c_, t_, w_ in (("sek", "Sek.", 50), ("os", "Osovina", 90), ("od", "Od [m]", 100), ("do", "Do [m]", 100), ("prep", "Prepreka (tip / ofset)", 260), ("str", "Strana", 90)):
            self.xt.heading(c_, text=t_); self.xt.column(c_, width=w_, anchor="w")
        self.xt.pack(side="left", fill="x", expand=True); self.xt.bind("<Double-1>", lambda e: self.edit_exc())
        xb = ttk.Frame(ef); xb.pack(side="left", padx=6)
        for tx, cm in (("Dodaj izuzetak…", self.add_exc), ("Izmijeni…", self.edit_exc), ("Obriši", self.del_exc)): ttk.Button(xb, text=tx, command=cm, width=16).pack(pady=1)
        self.refresh_exc()
        ttk.Label(pf, text="4) Elementi trase – označite jedan ili VIŠE redova (Ctrl/Shift) pa „Uredi odabrane…“ da im odjednom zadate tip prepreke (npr. most) ili ofset (prazno = važi tip za sve krivine):", foreground="#333").pack(anchor="w", pady=(6, 0))
        tf = ttk.Frame(pf); tf.pack(fill="both", expand=True)
        cols = ("sek", "os", "br", "vrsta", "od", "do", "R", "prep")
        self.et = ttk.Treeview(tf, columns=cols, show="headings", height=9)
        for c_, t_, w_ in (("sek", "Sek.", 40), ("os", "Osovina", 80), ("br", "El.", 40), ("vrsta", "Vrsta", 90), ("od", "Od [m]", 90), ("do", "Do [m]", 90), ("R", "R [m]", 80), ("prep", "Prepreka (tip / ofset od ivice, strana)", 330)):
            self.et.heading(c_, text=t_); self.et.column(c_, width=w_, anchor="w")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.et.yview); self.et.configure(yscrollcommand=sb.set)
        self.et.pack(side="left", fill="both", expand=True); sb.pack(side="left", fill="y")
        self.et.bind("<Double-1>", lambda e: self.edit_el()); self.et.configure(selectmode="extended")
        bb = ttk.Frame(pf); bb.pack(anchor="w", pady=3)
        ttk.Button(bb, text="Učitaj elemente iz ispisa", command=self.load_elems).pack(side="left")
        ttk.Button(bb, text="Uredi odabrane…", command=self.edit_el).pack(side="left", padx=6)
        ttk.Button(bb, text="Obriši unos za odabrane", command=self.clear_el).pack(side="left")
        self.elset = {}
        for e in (t.get("prepreke") or []):
            if e.get("element") not in (None, ""): self.elset[(e.get("sekcija"), e.get("osovina"), int(e["element"]))] = (e.get("tip", ""), e.get("ofset", ""), e.get("strana", "unutra"))
        self.elrows = []; self.after(100, lambda: self.load_elems(True))
        ttk.Label(f, text="Širine traka i ofset za svaku osovinu unose se u prozoru sekcije.\nIzlaz: DXF crteži (otvaraju se u AutoCAD-u; Save As → DWG) + Excel sa rezultatima.", foreground="#555").grid(row=r, column=0, columnspan=2, sticky="w", pady=4); r += 1
        bf = ttk.Frame(f); bf.grid(row=r, column=0, columnspan=2, sticky="e")
        ttk.Button(bf, text="U redu", command=self.ok).pack(side="left"); ttk.Button(bf, text="Otkaži", command=self.destroy).pack(side="left", padx=4)

    @staticmethod
    def _fmt(e):
        where = str(e["element"]) if e.get("element") not in (None, "") else f"{e.get('od')}-{e.get('do')}"
        return f"{e.get('sekcija') or '*'}; {e.get('osovina') or '*'}; {where}; {e.get('tip') or e.get('ofset')}; {e.get('strana', 'unutra')}"

    def parse_pre(self):
        out = []
        for n, line in enumerate(self.pre.get("1.0", "end").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"): continue
            p = [x.strip() for x in line.split(";")]
            if len(p) < 4: raise ValueError(f"Prepreke, red {n}: očekujem 'sekcija; osovina; element ili od-do; ofset; strana'.")
            e = {}
            if p[0] not in ("*", ""): e["sekcija"] = int(p[0])
            if p[1] not in ("*", ""): e["osovina"] = p[1]
            m = re.match(r"^\s*(-?[\d.,]+)\s*[-–]\s*(-?[\d.,]+)\s*$", p[2])
            if m: e["od"] = float(m.group(1).replace(",", ".")); e["do"] = float(m.group(2).replace(",", "."))
            else: e["element"] = int(p[2])
            try: e["ofset"] = float(p[3].replace(",", "."))
            except ValueError: e["tip"] = p[3]
            e["strana"] = p[4] if len(p) > 4 and p[4] else "unutra"
            out.append(e)
        return out

    def load_elems(self, silent=False):
        """Čita elemente horizontale svake osovine iz odabranih ispisa i puni tabelu."""
        self.elrows = []
        try:
            for si, sec in enumerate(sorted(self.cfg.get("sekcije", []), key=lambda s: s["od"]), 1):
                for role, _ in ROLES[sec["tip"]]:
                    sp = sec.get(role) or {}
                    if not all(os.path.isfile(sp.get(k, "")) for k in ("h", "v", "x")): continue
                    ax = Axis("tmp", sp["h"], sp["v"], sp["x"], cs_col=sp.get("cs_col"))
                    for e in ax.elems:
                        if e["s0"] + e["L"] < float(sec["od"]) or e["s0"] > float(sec["do"]) or e["L"] < 0.5: continue
                        R = e["R0"] if e["typ"] == "KRUZNI_LUK" else (e["R1"] if e["R0"] == float("inf") else e["R0"])
                        self.elrows.append(dict(sek=si, os=role, no=e["no"], typ=e["typ"], s0=e["s0"], s1=e["s0"] + e["L"], R=R))
        except Exception as ex:
            messagebox.showerror("Greška", f"Elementi se ne mogu učitati: {ex}", parent=self)
        self.refresh_el()
        if not self.elrows and not silent: messagebox.showinfo("Elementi trase", "Nema učitanih elemenata – prvo odaberite datoteke osovina u sekcijama.", parent=self)

    def _tipovi(self):
        out = {}
        for line in self.tip.get("1.0", "end").splitlines():
            p = [x.strip() for x in line.split(";")]
            if len(p) >= 2 and p[0] and p[1]:
                try: out[p[0]] = float(p[1].replace(",", "."))
                except ValueError: pass
        return out

    def refresh_el(self):
        self.et.delete(*self.et.get_children()); tv = self._tipovi(); zt = self.ztip.get().strip()
        for i, r in enumerate(self.elrows):
            k = (r["sek"], r["os"], r["no"]); k2 = (r["sek"], None, r["no"])
            u = self.elset.get(k) or self.elset.get(k2)
            if u:
                tip, of, st = u
                txt = (f"{tip} ({tv.get(tip, '?')} m)" if tip else f"{of} m") + f", strana: {st}"
            elif r["typ"] != "PRAVAC" and zt in tv: txt = f"(za sve krivine: {zt}, {tv[zt]} m)"
            else: txt = ""
            Rt = "∞" if r["R"] == float("inf") else f"{r['R']:.1f}"
            self.et.insert("", "end", iid=str(i), values=(r["sek"], r["os"], r["no"], TIP_KR.get(r["typ"], r["typ"]), f"{r['s0']:.2f}", f"{r['s1']:.2f}", Rt, txt))

    def edit_el(self):
        sel = self.et.selection()
        if not sel: return
        rs = [self.elrows[int(i)] for i in sel]; r = rs[0]; k = (r["sek"], r["os"], r["no"]); cur = self.elset.get(k, ("", "", "unutra"))
        w = tk.Toplevel(self); w.title(f"Element {r['no']} ({r['os']}, sekcija {r['sek']})" if len(rs) == 1 else f"Odabrano elemenata: {len(rs)}"); w.transient(self); w.grab_set()
        f = ttk.Frame(w, padding=10); f.pack()
        tv = self._tipovi()
        ttk.Label(f, text="Tip prepreke:").grid(row=0, column=0, sticky="w"); tip = tk.StringVar(value=cur[0])
        ttk.Combobox(f, textvariable=tip, values=[""] + list(tv), width=24, state="readonly").grid(row=0, column=1, pady=2)
        ttk.Label(f, text="ILI ofset od ivice kolovoza [m]:").grid(row=1, column=0, sticky="w"); of = tk.StringVar(value=str(cur[1]))
        ttk.Entry(f, textvariable=of, width=10).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(f, text="Strana:").grid(row=2, column=0, sticky="w"); st = tk.StringVar(value=cur[2])
        ttk.Combobox(f, textvariable=st, values=["unutra", "vani", "desno", "lijevo"], width=10, state="readonly").grid(row=2, column=1, sticky="w", pady=2)
        def ok():
            try:
                o = of.get().strip().replace(",", ".")
                if o: float(o)
                for r_ in rs:
                    k_ = (r_["sek"], r_["os"], r_["no"])
                    if tip.get() or o: self.elset[k_] = (tip.get(), o, st.get())
                    else: self.elset.pop(k_, None)
                self.refresh_el(); w.destroy()
            except ValueError: messagebox.showerror("Greška", "Ofset mora biti broj.", parent=w)
        ttk.Button(f, text="U redu", command=ok).grid(row=3, column=1, sticky="e", pady=6)

    def refresh_exc(self):
        self.xt.delete(*self.xt.get_children())
        for i, e in enumerate(self.exc):
            self.xt.insert("", "end", iid=str(i), values=(e.get("sekcija") or "*", e.get("osovina") or "*", e.get("od"), e.get("do"), e.get("tip") or f"{e.get('ofset')} m", e.get("strana", "unutra")))

    def _exc_dialog(self, cur=None):
        cur = cur or {}
        w = tk.Toplevel(self); w.title("Izuzetak po stacionaži"); w.transient(self); w.grab_set(); res = {}
        f = ttk.Frame(w, padding=10); f.pack()
        tv = self._tipovi()
        sv = {"od": tk.StringVar(value=str(cur.get("od", ""))), "do": tk.StringVar(value=str(cur.get("do", ""))), "ofset": tk.StringVar(value=str(cur.get("ofset", ""))),
              "tip": tk.StringVar(value=cur.get("tip", "")), "strana": tk.StringVar(value=cur.get("strana", "unutra")),
              "sek": tk.StringVar(value=str(cur.get("sekcija", "") or "")), "os": tk.StringVar(value=cur.get("osovina", "") or "")}
        rows = [("Stacionaža OD [m]:", ttk.Entry(f, textvariable=sv["od"], width=14)), ("Stacionaža DO [m]:", ttk.Entry(f, textvariable=sv["do"], width=14)),
                ("Tip prepreke:", ttk.Combobox(f, textvariable=sv["tip"], values=[""] + list(tv), width=22, state="readonly")),
                ("ILI ofset prepreke od ivice kolovoza [m]:", ttk.Entry(f, textvariable=sv["ofset"], width=14)),
                ("Strana:", ttk.Combobox(f, textvariable=sv["strana"], values=["unutra", "vani", "desno", "lijevo"], width=12, state="readonly")),
                ("Sekcija (prazno = sve):", ttk.Entry(f, textvariable=sv["sek"], width=6)),
                ("Osovina (desna / lijeva / centralna; prazno = sve):", ttk.Combobox(f, textvariable=sv["os"], values=["", "desna", "lijeva", "centralna"], width=12, state="readonly"))]
        for i, (lab, wd) in enumerate(rows): ttk.Label(f, text=lab).grid(row=i, column=0, sticky="w", pady=2); wd.grid(row=i, column=1, sticky="w", padx=6)
        def ok():
            try:
                a, b = fnum(sv["od"].get()), fnum(sv["do"].get())
                if a is None or b is None or b <= a: raise ValueError("Stacionaže OD / DO nisu ispravne (DO mora biti veće od OD).")
                e = {"od": a, "do": b, "strana": sv["strana"].get() or "unutra"}
                o = sv["ofset"].get().strip().replace(",", ".")
                if sv["tip"].get(): e["tip"] = sv["tip"].get()
                elif o: e["ofset"] = float(o)
                else: raise ValueError("Zadajte tip prepreke ili ofset.")
                if sv["sek"].get().strip(): e["sekcija"] = int(sv["sek"].get())
                if sv["os"].get(): e["osovina"] = sv["os"].get()
                res.update(e); w.destroy()
            except ValueError as ex: messagebox.showerror("Greška", str(ex), parent=w)
        ttk.Button(f, text="U redu", command=ok).grid(row=len(rows), column=1, sticky="e", pady=8)
        self.wait_window(w); return res or None

    def add_exc(self):
        e = self._exc_dialog()
        if e: self.exc.append(e); self.refresh_exc()

    def edit_exc(self):
        s_ = self.xt.selection()
        if not s_: return
        i = int(s_[0]); e = self._exc_dialog(self.exc[i])
        if e: self.exc[i] = e; self.refresh_exc()

    def del_exc(self):
        for i in sorted((int(x) for x in self.xt.selection()), reverse=True): del self.exc[i]
        self.refresh_exc()

    def clear_el(self):
        for i in self.et.selection():
            r = self.elrows[int(i)]; self.elset.pop((r["sek"], r["os"], r["no"]), None)
        self.refresh_el()

    def ok(self):
        try:
            d = {}
            for k, lab, dv, opt in self.FIELDS:
                x = fnum(self.v[k].get())
                if x is None and not opt: raise ValueError(f"Polje je prazno: {lab}")
                if x is not None: d[k] = x
            d["strane"] = [n for n, v in (("desno", self.sd.get()), ("lijevo", self.sl.get())) if v]
            if not d["strane"]: raise ValueError("Odaberite bar jednu stranu osovine.")
            d["ivice"] = self.iv.get(); d["ukljuci"] = True; d["png"] = self.png.get()
            tv = {}
            for n, line in enumerate(self.tip.get("1.0", "end").splitlines(), 1):
                if not line.strip(): continue
                p = [x.strip() for x in line.split(";")]
                if len(p) < 2 or not p[0]: raise ValueError(f"Tipovi prepreka, red {n}: očekujem 'naziv; ofset'.")
                if p[1]: tv[p[0]] = float(p[1].replace(",", "."))
            d["tipovi_prepreka"] = tv; d["zadani_tip"] = self.ztip.get().strip()
            if d["zadani_tip"] and d["zadani_tip"] not in tv: raise ValueError(f"Tip '{d['zadani_tip']}' nema upisan ofset u tabeli tipova.")
            pre = [dict(e) for e in self.exc]       # izuzeci po stacionaži iz tabele
            for (sek, os_, no), (tip, of, st) in self.elset.items():
                e = {"element": no, "strana": st}
                if sek: e["sekcija"] = sek
                if os_: e["osovina"] = os_
                if tip: e["tip"] = tip
                else: e["ofset"] = float(str(of).replace(",", "."))
                pre.append(e)
            d["prepreke"] = pre; self.result = d; self.destroy()
        except Exception as e:
            messagebox.showerror("Greška", str(e), parent=self)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("UNA - ROAD ENGINEERING ANALYSIS – vozno-dinamičke i optičke analize"); self.geometry("980x720")
        self.cfg = {"projekat": "", "Vr": 100, "sekcije": []}; self.path = None; self.q = queue.Queue(); self.busy = False
        try:
            self._ico = tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), "webui", "static", "logo_icon.png")); self.iconphoto(True, self._ico)      # ikona prozora (logo)
        except Exception: pass
        m = tk.Menu(self); fm_ = tk.Menu(m, tearoff=0)
        fm_.add_command(label="Novi projekat", command=self.new); fm_.add_command(label="Učitaj projekat…", command=self.load); fm_.add_command(label="Spremi projekat (Ctrl+S)", command=self.save_quick); fm_.add_command(label="Spremi projekat kao…", command=self.save); fm_.add_separator(); fm_.add_command(label="Spremi postavke (bez ispisa)…", command=self.save_settings); fm_.add_command(label="Učitaj postavke…", command=self.load_settings); fm_.add_separator(); fm_.add_command(label="Izlaz", command=self.destroy)
        m.add_cascade(label="Projekat", menu=fm_); self.config(menu=m)
        top = ttk.LabelFrame(self, text="1. Projekat", padding=8); top.pack(fill="x", padx=8, pady=4)
        self.name = tk.StringVar(); self.vr = tk.StringVar(value="100"); self.out = tk.StringVar()
        ttk.Label(top, text="Naziv dionice:").grid(row=0, column=0, sticky="w"); ttk.Entry(top, textvariable=self.name, width=60).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(top, text="Računska brzina Vr [km/h]:").grid(row=0, column=2, sticky="e"); ttk.Entry(top, textvariable=self.vr, width=6).grid(row=0, column=3, sticky="w", padx=4)
        ttk.Label(top, text="Izlazni folder:").grid(row=1, column=0, sticky="w"); ttk.Entry(top, textvariable=self.out, width=60).grid(row=1, column=1, sticky="w", padx=4)
        ttk.Button(top, text="…", width=3, command=self.pick_out).grid(row=1, column=2, sticky="w")
        mid = ttk.LabelFrame(self, text="2. Sekcije trase (redom po stacionaži; svaka ima svoj tip: razdvojene osovine / centralna / jedna osovina)", padding=8); mid.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("br", "tip", "od", "do", "fajlovi", "ogr")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", height=7)
        for c, t, w in (("br", "Br.", 40), ("tip", "Vrsta", 280), ("od", "Od [m]", 80), ("do", "Do [m]", 80), ("fajlovi", "Horizontale (datoteke)", 260), ("ogr", "Zone Vr", 180)):
            self.tree.heading(c, text=t); self.tree.column(c, width=w)
        self.tree.pack(side="left", fill="both", expand=True); self.tree.bind("<Double-1>", lambda e: self.edit())
        bf = ttk.Frame(mid); bf.pack(side="left", fill="y", padx=6)
        for t, c in (("Dodaj sekciju…", self.add), ("Uredi…", self.edit), ("Ukloni", self.remove), ("Gore", lambda: self.move(-1)), ("Dolje", lambda: self.move(1))): ttk.Button(bf, text=t, command=c, width=18).pack(pady=2)
        opt = ttk.LabelFrame(self, text="3. Izlaz i postavke", padding=8); opt.pack(fill="x", padx=8, pady=4)
        self.w = tk.BooleanVar(value=True); self.x = tk.BooleanVar(value=True); self.pg = tk.BooleanVar(value=False); self.op = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt, text="Word elaborat", variable=self.w).pack(side="left"); ttk.Checkbutton(opt, text="Excel radna knjiga (sa formulama i dijagramima)", variable=self.x).pack(side="left", padx=8)
        ttk.Button(opt, text="Napredni parametri…", command=self.params).pack(side="left", padx=8); ttk.Button(opt, text="Tekst za elaborat…", command=self.notes).pack(side="left", padx=4); ttk.Button(opt, text="Word template…", command=self.tpl).pack(side="left")
        ttk.Checkbutton(opt, text="Preglednost (DXF)", variable=self.pg).pack(side="left", padx=8); ttk.Button(opt, text="Preglednost…", command=self.pgdlg).pack(side="left")
        ttk.Checkbutton(opt, text="Elaborat optičkih analiza (Word)", variable=self.op).pack(side="left", padx=8); ttk.Button(opt, text="Preticanje…", command=self.opdlg).pack(side="left")
        self.run_b = ttk.Button(opt, text="▶  NAPRAVI ELABORAT", command=self.run); self.run_b.pack(side="right")
        self.logw = scrolledtext.ScrolledText(self, height=10, state="disabled"); self.logw.pack(fill="both", expand=False, padx=8, pady=4)
        self.bind('<Control-s>', lambda e: self.save_quick()); self.after(150, self.poll); self.refresh(); self.after(300, self.check_license); self.after(700, self.offer_last)

    # --- licenca
    def check_license(self):
        from . import licenca
        try:
            lic = licenca.current(); self.title(self.title() + "  –  " + licenca.describe(lic))
        except licenca.LicencaError as e:
            self.activate(str(e))

    def activate(self, msg=""):
        from . import licenca
        d = tk.Toplevel(self); d.title("Aktivacija licence"); d.transient(self); d.grab_set()
        f = ttk.Frame(d, padding=12); f.pack()
        if msg: ttk.Label(f, text=msg, foreground="#b00000", wraplength=480).pack(anchor="w", pady=(0, 8))
        ttk.Label(f, text="Pošaljite ovaj ID računara dobavljaču da dobijete licencu:").pack(anchor="w")
        mid = licenca.machine_id(); e = ttk.Entry(f, width=30, font=("Consolas", 12)); e.insert(0, mid); e.configure(state="readonly"); e.pack(anchor="w", pady=4)
        def cp(): self.clipboard_clear(); self.clipboard_append(mid)
        def load():
            p = filedialog.askopenfilename(parent=d, title="Datoteka licence", filetypes=[("Licenca", "*.lic"), ("Sve", "*.*")])
            if not p: return
            try: lic = licenca.install(p)
            except licenca.LicencaError as ex: messagebox.showerror("Licenca", str(ex), parent=d); return
            messagebox.showinfo("Licenca", "Licenca je aktivirana.\n" + licenca.describe(lic), parent=d); d.destroy()
        bf = ttk.Frame(f); bf.pack(anchor="w", pady=8)
        ttk.Button(bf, text="Kopiraj ID", command=cp).pack(side="left"); ttk.Button(bf, text="Učitaj licencu (.lic)…", command=load).pack(side="left", padx=6); ttk.Button(bf, text="Zatvori", command=d.destroy).pack(side="left")

    # --- stanje
    def offer_last(self):
        try:
            p = open(self.LAST, encoding="utf-8").read().strip()
            if p and os.path.isfile(p) and messagebox.askyesno("Posljednji projekat", f"Učitati posljednji projekat?\n{p}"):
                self.path = p; self.fill(pipeline.load_cfg(p))
        except Exception: pass

    def collect(self):
        c = dict(self.cfg); c["projekat"] = self.name.get().strip() or "Dionica"
        c["Vr"] = fnum(self.vr.get(), 100.0); c["izlaz"] = self.out.get().strip()
        c["gui_opcije"] = {"word": self.w.get(), "excel": self.x.get(), "preglednost": self.pg.get(), "optika": self.op.get()}; return c

    def fill(self, cfg):
        self.cfg = cfg; self.name.set(cfg.get("projekat", "")); self.vr.set(str(cfg.get("Vr", 100))); self.out.set(cfg.get("izlaz", ""))
        g = cfg.get("gui_opcije") or {}
        for var, k in ((self.w, "word"), (self.x, "excel"), (self.pg, "preglednost"), (self.op, "optika")):
            if k in g: var.set(bool(g[k]))
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, s in enumerate(self.cfg.get("sekcije", []), 1):
            fl, cap = sec_summary(s)
            self.tree.insert("", "end", iid=str(i - 1), values=(i, dict(TIP_OPIS)[s["tip"]], s["od"], s["do"], ", ".join(fl), cap))

    def sel(self):
        s = self.tree.selection(); return int(s[0]) if s else None

    def add(self):
        d = SectionDialog(self); self.wait_window(d)
        if d.result: self.cfg.setdefault("sekcije", []).append(d.result); self.cfg["sekcije"].sort(key=lambda s: s["od"]); self.refresh()

    def edit(self):
        i = self.sel()
        if i is None: return
        d = SectionDialog(self, self.cfg["sekcije"][i]); self.wait_window(d)
        if d.result: self.cfg["sekcije"][i] = d.result; self.cfg["sekcije"].sort(key=lambda s: s["od"]); self.refresh()

    def remove(self):
        i = self.sel()
        if i is not None and messagebox.askyesno("Ukloni", "Ukloniti odabranu sekciju?"): del self.cfg["sekcije"][i]; self.refresh()

    def move(self, d):
        i = self.sel(); L = self.cfg["sekcije"]
        if i is None or not (0 <= i + d < len(L)): return
        L[i], L[i + d] = L[i + d], L[i]; self.refresh(); self.tree.selection_set(str(i + d))

    def params(self):
        d = ParamDialog(self, self.cfg); self.wait_window(d)
        if d.result: self.cfg.update(d.result)

    def notes(self):
        d = NotesDialog(self, self.cfg); self.wait_window(d)
        if d.result: self.cfg.update(d.result)

    def tpl(self):
        d = TemplateDialog(self, self.cfg); self.wait_window(d)
        if d.result is not None:
            if d.result: self.cfg["template"] = d.result
            else: self.cfg.pop("template", None)

    def pgdlg(self):
        d = PregDialog(self, self.cfg); self.wait_window(d)
        if d.result is not None: self.cfg["preglednost"] = d.result; self.pg.set(True)

    def opdlg(self):
        o = dict(self.cfg.get("optika") or {})
        d = tk.Toplevel(self); d.title("Preticajna preglednost – parametri"); d.transient(self); d.grab_set()
        v = {k: tk.StringVar(value=str(o.get(k, dflt))) for k, dflt in (("tip_puta", "dvosmjerni"), ("grupa", "A"), ("Pp_po", "Vr"), ("min_proc", 25.0), ("h_predmeta_preticanje", ""), ("korak_tabela", 50.0))}
        lab = {"tip_puta": "Tip puta: dvosmjerni (Tabela 30, min. 25 %) ili razdvojeni (kriterij Pzp, bez minimuma)", "grupa": "Tehnička grupa puta (A: min 25 %, B/C: 15 %)", "Pp_po": "Brzina za Pp: Vr (računska, projektni zadatak) ili Vp (projektna)", "min_proc": "Minimalni % preticajne preglednosti", "h_predmeta_preticanje": "Visina predmeta pri preticanju [m] (prazno = ista kao u Preglednost… )", "korak_tabela": "Korak tabele u Wordu [m]"}
        for i, k in enumerate(v):
            ttk.Label(d, text=lab[k]).grid(row=i, column=0, sticky="w", padx=6, pady=3); ttk.Entry(d, textvariable=v[k], width=10).grid(row=i, column=1, padx=6)
        ttk.Label(d, text="Pp prema Tabeli 30 BiH Smjernica (4.2.5.3); zrake iz lijeve (preticajne) trake.", foreground="#333").grid(row=len(v), column=0, columnspan=2, padx=6, pady=4)
        def ok():
            o.update({k: (x.get().strip().replace(",", ".") if k == "Pp_po" else fnum(x.get(), 0.0)) for k, x in v.items()}); self.cfg["optika"] = o; self.op.set(True); d.destroy()
        ttk.Button(d, text="U redu", command=ok).grid(row=len(v) + 1, column=1, pady=6); self.wait_window(d)

    def pick_out(self):
        p = filedialog.askdirectory(title="Izlazni folder")
        if p: self.out.set(p)

    def new(self): self.path = None; self.fill({"projekat": "", "Vr": 100, "sekcije": []})

    def load(self):
        p = filedialog.askopenfilename(title="Učitaj projekat", filetypes=[("Projekat", "*.json")])
        if p:
            try: self.path = p; self.fill(pipeline.load_cfg(p)); self._remember(p)
            except Exception as e: messagebox.showerror("Greška", str(e))

    LAST = os.path.join(os.path.expanduser("~"), ".una_zadnji_projekat.txt")

    def _remember(self, p):
        try: open(self.LAST, "w", encoding="utf-8").write(p)
        except Exception: pass

    def save(self):
        p = filedialog.asksaveasfilename(title="Spremi projekat (ispisi + sve postavke)", defaultextension=".json", filetypes=[("Projekat", "*.json")], initialfile=os.path.basename(self.path or "projekat.json"))
        if p:
            json.dump(self.collect(), open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False); self.path = p; self._remember(p)

    def save_quick(self):
        if not self.path: return self.save()
        json.dump(self.collect(), open(self.path, "w", encoding="utf-8"), indent=1, ensure_ascii=False); self._remember(self.path)
        self.log(f"Projekat spremljen: {self.path}\n")

    def save_settings(self):
        p = filedialog.asksaveasfilename(title="Spremi postavke (bez sekcija i ispisa) – za sljedeći projekat", defaultextension=".json", filetypes=[("Postavke", "*.json")], initialfile="postavke.json")
        if p:
            c = self.collect(); c.pop("sekcije", None); c.pop("projekat", None); c.pop("izlaz", None)
            json.dump(c, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            messagebox.showinfo("Postavke", "Postavke su spremljene. Kod sljedećeg projekta: Projekat → Učitaj postavke…, zatim samo dodajte ispise (sekcije).")

    def load_settings(self):
        p = filedialog.askopenfilename(title="Učitaj postavke", filetypes=[("Postavke / projekat", "*.json")])
        if not p: return
        try:
            c = json.load(open(p, encoding="utf-8"))
            keep = {k: self.cfg.get(k) for k in ("sekcije",) if k in self.cfg}
            c.pop("sekcije", None); c.pop("projekat", None); c.pop("izlaz", None)
            new = dict(self.cfg); new.update(c); new.update(keep)
            new["projekat"] = self.name.get(); new["izlaz"] = self.out.get()
            self.fill(new)
            messagebox.showinfo("Postavke", "Postavke su učitane; sekcije, naziv i izlazni folder ostali su kakvi jesu.")
        except Exception as e: messagebox.showerror("Greška", str(e))

    # --- pokretanje
    def log(self, s):
        self.q.put(str(s))

    def poll(self):
        try:
            while True:
                s = self.q.get_nowait()
                if s == "\0DONE": self.busy = False; self.run_b.config(state="normal"); continue
                self.logw.config(state="normal"); self.logw.insert("end", s + "\n"); self.logw.see("end"); self.logw.config(state="disabled")
        except queue.Empty: pass
        self.after(150, self.poll)

    def run(self):
        if self.busy: return
        cfg = self.collect()
        if not cfg["izlaz"]: messagebox.showwarning("Izlazni folder", "Odaberite izlazni folder."); return
        errs = pipeline.validate(cfg)
        if errs: messagebox.showerror("Provjera unosa", "\n".join(errs)); return
        self.busy = True; self.run_b.config(state="disabled"); self.logw.config(state="normal"); self.logw.delete("1.0", "end"); self.logw.config(state="disabled")
        word, excel = self.w.get(), self.x.get(); sight = self.pg.get() or self.op.get()
        cfg["optika"] = dict(cfg.get("optika") or {}, ukljuci=bool(self.op.get()))
        if sight and not cfg.get("preglednost"): cfg["preglednost"] = {"ukljuci": True}
        def work():
            try:
                outs, _ = pipeline.generate(cfg, cfg["izlaz"], log=self.log, word=word, excel=excel, sight=sight)
                self.log("\nGOTOVO. Napravljene datoteke:\n" + "\n".join(outs))
            except Exception as e:
                self.log("\nGREŠKA: " + str(e) + "\n" + traceback.format_exc())
            finally:
                self.q.put("\0DONE")
        threading.Thread(target=work, daemon=True).start()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
