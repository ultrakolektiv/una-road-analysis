"use strict";
/* UNA – Road Engineering Analysis · web UI (vanilla JS, no build step) */
const TOKEN = document.querySelector('meta[name="una-token"]').content;
const $ = (s, r = document) => r.querySelector(s);
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") e.className = v; else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "value") e.value = v; else if (k === "checked") e.checked = !!v; else e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) e.append(c.nodeType ? c : document.createTextNode(c));
  return e;
}
async function api(name, body) {
  const r = await fetch("/api/" + name, { method: "POST", headers: { "X-UNA-Token": TOKEN, "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
  const j = await r.json(); if (!r.ok) throw new Error(j.error || r.status); return j;
}

/* ---------------------------------------------------------------- i18n */
const L = {
sr: {
 nav_project:"Projekat", nav_sections:"Sekcije trase", nav_params:"Parametri", nav_sight:"Preglednost", nav_run:"Izrada",
 new:"Novi", open:"Otvori…", save:"Spremi", save_as:"Spremi kao…", untitled:"Novi projekat", unsaved:"nije spremljeno",
 p_title:"Projekat", p_sub:"Osnovni podaci o dionici i izlazu.", p_name:"Naziv dionice", p_vr:"Računska brzina Vr [km/h]", p_out:"Izlazni folder", p_browse:"Odaberi…",
 p_lang:"Jezik dokumenata", p_lang_h:"Jezik (bosanski ili engleski) u kome se prave Word/Excel/DXF izlazi.", p_notes:"Tekst za elaborat", p_notes_h:"Naslovna strana i dodatni opisi koji ulaze u elaborat.",
 p_date:"Datum / verzija (naslovna strana)", p_desc:"Dodatni opis trase (Uvod)", p_remarks:"Dodatne napomene / pretpostavke (jedna po redu, Prilog C)",
 p_settings:"Postavke za sljedeći projekat", p_settings_h:"Spremite napredne parametre (bez sekcija i ispisa) i učitajte ih u novom projektu.", p_save_set:"Spremi postavke…", p_load_set:"Učitaj postavke…",
 s_title:"Sekcije trase", s_sub:"Redom po stacionaži. Svaka sekcija ima svoj tip: razdvojene osovine, centralna ili jedna osovina.", s_add:"Dodaj sekciju", s_edit:"Uredi", s_del:"Ukloni", s_up:"Gore", s_down:"Dolje",
 s_empty:"Još nema sekcija. Dodajte prvu sekciju i odaberite ispise osovine (horizontala, uzdužni profil, poprečni nagibi).", s_confirm_del:"Ukloniti sekciju {0}?",
 t_razdvojene:"Dvije odvojene osovine (desni i lijevi kolovoz)", t_centralna:"Centralna osovina (jedan ispis, oba smjera)", t_jedna_naprijed:"Jedna osovina – smjer rastuće stacionaže", t_jedna_nazad:"Jedna osovina – smjer opadajuće stacionaže",
 r_desna:"DESNA osovina (desni kolovoz, vožnja u smjeru stacionaže)", r_lijeva:"LIJEVA osovina (lijevi kolovoz, vožnja suprotno stacionaži)", r_centralna:"CENTRALNA osovina", r_osovina:"Osovina",
 f_h:"Horizontalna osovina (elementi)", f_v:"Uzdužni profil (prelomne tačke)", f_x:"Poprečni nagibi", f_pick3:"Odaberi sva 3 fajla odjednom (automatsko prepoznavanje)", f_none:"nije odabrano",
 d_title_new:"Nova sekcija", d_title_edit:"Sekcija trase", d_type:"Vrsta sekcije", d_from:"Stacionaža OD [m]", d_to:"DO [m]", d_auto:"Postavi OD/DO prema ispisima",
 d_caps:"Zone računske brzine Vr (opciono)", d_caps_h:"Jedan red: OD; DO; Vr km/h. Unutar zone proračun (Vp, Rmin, zrake preglednosti) koristi tu računsku brzinu.", d_caps_why:"Napomena uz zone (ne ulazi u proračun)",
 d_cs:"Kolona poprečnog nagiba LIJEVE strane (redni broj trake, prazno = automatski)", d_cross:"Poprečni profil i ofset osovine vozne trake (prazno = podrazumijevano)",
 d_half:"Centralna osovina: POLA širine razdjelnog pojasa [m]", d_wr:"Širine traka DESNO od osovine puta [m] (npr. 3.5, 3.5)", d_wl:"Širine traka LIJEVO od osovine puta [m] (npr. 3.5, 3.5)",
 d_or:"Osovina oka vozača DESNO od osovine kolovoza [m]", d_ol:"Osovina oka vozača LIJEVO od osovine kolovoza [m]", d_range:"Zajednički raspon ispisa: {0} – {1} m. Prilagodite OD/DO prema stvarnoj sekciji.",
 ok:"U redu", cancel:"Otkaži", close:"Zatvori", yes:"Da", no:"Ne",
 e_range:"Stacionaže OD / DO nisu ispravne (DO mora biti veće od OD).", e_file:"Datoteka ne postoji: {0}", e_cap:"Zona Vr: neispravan red '{0}' (OD; DO; Vr).", e_num:"Neispravan broj: {0}",
 e_unrec:"Nisu prepoznate sve tri vrste datoteka – dopunite ručno.", dlg_pick_one:"Odaberite datoteku.", s_lx:"Uvezi osovine iz LandXML-a", s_lx_wait:"Čitam LandXML (velike datoteke traju nekoliko minuta)…", s_lx_replace:"Zamijeniti postojeće sekcije osovinama iz LandXML-a?", s_lx_ok:"Uvezene osovine:", dlg_opening:"Otvaram dijalog za odabir datoteke …", e_nodlg:"Prozor za odabir datoteka nije dostupan – upišite putanju ručno.",
 pa_title:"Napredni parametri", pa_sub:"Model vožnje, tablice iz Priloga 2 pravilnika i vozila za dinamički proračun (poglavlje 5).", pa_reset:"Vrati podrazumijevano",
 pa_model:"Model vožnje", pa_tables:"Tablice", pa_tables_h:"Vrijednosti odvojene zarezom ili razmakom. Vp–R koristi Vr i Rmin tablicu.", pa_veh:"Vozila", pa_veh_h:"vlim prazno = max Vr; b i prazan hod prazno = opšte vrijednosti; P prazno = kriva sile vuče iz Pravilnika.",
 pa_addveh:"Dodaj vozilo", pa_delveh:"Ukloni zadnje", pa_tpl:"Word template", pa_tpl_h:"Ako je odabran, pored izvornog elaborata pravi se i elaborat u templatu. Prazna polja ostaju kakva su u templatu.", pa_tpl_file:"Template (.docx)", pa_tpl_clear:"Ukloni template",
 sc_korak:"Korak proračuna Δs [m]", sc_a:"Ubrzanje a [m/s²]", sc_d:"Usporenje d [m/s²]", sc_ulazna_brzina:"Ulazna brzina na početku trase [km/h] (prazno = Vr + dodatak)", sc_dodatak_maxVr:"max Vr = Vr + [km/h]",
 sc_maxVr_tab:"max Vr prema tabeli 3-04 [km/h] (prazno = bez ograničenja)", sc_obrazac_puta:"Put promjene brzine po obrascu 0,1·Vsr·ΔV: 1 = da, 0 = kinematika s a i d", sc_max_nagib:"Referentni najveći podužni nagib [%]",
 sc_rho:"Gustina vazduha ρ [kg/m³]", sc_b:"Specifična potrošnja b [l/kWh]", sc_prazan_hod:"Prazan hod [l/h]",
 tb_Vr_tab:"Vr [km/h]", tb_Rmin_tab:"Rmin [m]", tb_fT:"fT", tb_fR:"fR", tb_iN_tab:"Vp–iN: nagib iN [%]", tb_ViN_tab:"Vp–iN: brzina [km/h]",
 v_naziv:"Naziv", v_kratko:"Kratko", e_tables:"Tablice Vr, Rmin, fT i fR moraju imati isti broj vrijednosti.", e_tab2:"Tablica Vp–iN: broj nagiba i brzina mora biti isti.", e_tab3:"Vrijednosti Rmin i iN moraju biti rastuće.",
 g_title:"Preglednost", g_sub:"Zrake preglednosti, zahtijevana i očekivana preglednost, preticanje.", g_on:"Uključi preglednost (DXF crteži + Excel)", g_on_h:"Izlaz: DXF crteži (otvaraju se u AutoCAD-u; Save As → DWG) + Excel sa rezultatima.",
 g_params:"Parametri zraka", g_sides:"Zrake crtati iz osovine oka vozača na strani osovine kolovoza", g_right:"desna traka", g_left:"lijeva traka", g_edges:"Crtaj ivice kolovoza (crvene linije)", g_png:"Dodatno napravi PNG pregled crteža",
 g_obst:"Očekivana preglednost – prepreke", g_obst_h:"Ofset prepreke od krajnje ivice kolovoza.", g_types:"Tipovi prepreke i ofset [m]", g_type_name:"Naziv", g_type_off:"Ofset [m]", g_default:"Tip koji važi za SVE krivine (radijusi i prijelaznice)",
 g_exc:"Izuzeci po stacionaži", g_exc_h:"Npr. most ili tunel koji zahvata samo dio elementa.", g_exc_add:"Dodaj izuzetak", g_exc_sec:"Sek.", g_exc_axis:"Osovina", g_exc_obst:"Prepreka", g_exc_side:"Strana",
 g_elems:"Elementi trase", g_elems_h:"Označite jedan ili više redova pa „Uredi odabrane“ da im odjednom zadate tip prepreke ili ofset.", g_load:"Učitaj elemente iz ispisa", g_edit_sel:"Uredi odabrane…", g_clear_sel:"Obriši unos za odabrane",
 g_kind:"Vrsta", g_el:"El.", g_from:"Od [m]", g_to:"Do [m]", g_all_curves:"za sve krivine", g_side:"strana", g_no_elems:"Nema učitanih elemenata – prvo odaberite datoteke osovina u sekcijama.",
 g_side_in:"unutra (prema centru krivine)", g_side_out:"vani", g_side_r:"desno (smjer stacionaže)", g_side_l:"lijevo (smjer stacionaže)", g_type:"Tip prepreke", g_or_off:"ILI ofset od ivice kolovoza [m]", g_all:"sve",
 g_selected:"Odabrano elemenata: {0}", e_type_off:"Zadajte tip prepreke ili ofset.", e_one_side:"Odaberite bar jednu stranu osovine.", e_def_type:"Tip '{0}' nema upisan ofset u tabeli tipova.",
 k_ofset:"Podrazumijevana širina trake / 2 – ofset osovine vozne trake [m]", k_h_oka:"Visina oka vozača iznad nivelete [m]", k_h_prepreke:"Visina predmeta [m] (prazno = automatski, Tabela 29)", k_dodatak_L:"Dodatak na zaustavnu dužinu Lz [m]",
 k_L_zahtijevano:"ZAHTIJEVANA dužina zrake L [m] (prazno = bez tog crteža)", k_Lmax:"Najveća dužina zrake u proračunu očekivane preglednosti [m]", k_korak_crtez:"Razmak zraka na crtežu [m]", k_korak_proracun:"Korak proračuna zraka i omotača [m]",
 k_mjerilo:"Mjerilo crteža (1:N)", k_ivica_debljina:"Debljina crvene linije ivice kolovoza [mm na papiru]",
 o_title:"Elaborat optičkih analiza (preticanje)", o_on:"Napravi optičke analize (Word)", o_tip:"Tip puta", o_tip_a:"auto (prema sekcijama)", o_tip_d:"dvosmjerni (Tabela 30, min. 25 %)", o_tip_r:"razdvojeni (kriterij Pzp)",
 o_grupa:"Tehnička grupa puta", o_Pp_po:"Brzina za Pp", o_min_proc:"Minimalni % preticajne preglednosti", o_h:"Visina predmeta pri preticanju [m]", o_korak:"Korak tabele u Wordu [m]",
 r_title:"Izrada elaborata", r_sub:"Odaberite izlaze i pokrenite proračun.", r_word:"Vozno-dinamičke analize (Word)", r_word_h:"Vozno-dinamičke analize", r_excel:"Excel radna knjiga", r_excel_h:"Formule, tablice i dijagrami",
 r_sight:"Preglednost (DXF + Excel)", r_sight_h:"Zrake, zahtijevana i očekivana preglednost", r_optika:"Optičke analize (Word)", r_optika_h:"Optičke analize i preticanje", r_ifc:"IFC 4.3 osovine", r_ifc_h:"IfcAlignment: horizontala, niveleta, 3D linija", r_dwg:"DWG crteži", r_dwg_h:"Iz DXF-a, preko besplatnog ODA File Converter-a", r_lx:"LandXML (Civil 3D)", r_lx_h:"Osovine i nivelete za Civil 3D corridor", r_kor:"Vožnja kroz Civil 3D koridor (HTML)", r_kor_h:"Uvoz LandXML koridora, ograde, teren, tunel i most", k_file:"LandXML koridora (Civil 3D)", k_pick:"Odaberi …", k_from:"Stacionaža od [m]", k_to:"Stacionaža do [m]", k_off:"Prepreka (čelična ograda) od ivice kolovoza [m]", k_rails:"Uskladi proračun preglednosti s koridorom (širina trake, prepreke, most/tunel)", k_h:"Koridor se čita iz Civil 3D LandXML-a (osovine, nivelete, poprečni presjeci, teren). Slika prati proračun: oko, prepreke i zrake su iz UNA proračuna, a uskladivanje preuzima širinu trake i vrstu prepreke iz koridora.", e_kor:"Koridor: odaberite LandXML datoteku.",
 r_run:"Napravi elaborat", r_running:"Računam…", r_done:"Gotovo", r_files:"Napravljene datoteke", r_open:"Otvori", r_folder:"Folder", r_log:"Tok proračuna", r_errors:"Provjera unosa", r_nothing:"Odaberite bar jedan izlaz.", r_noout:"Odaberite izlazni folder (korak Projekat).", r_fail:"Greška pri izradi",
 r_open_folder:"Otvori izlazni folder", r_ready:"Spremno", r_summary:"Rezime",
 lic_ok:"Licenca aktivna", lic_bad:"Licenca nije aktivirana", lic_act:"Aktiviraj…", lic_title:"Aktivacija licence", lic_id:"Pošaljite ovaj ID računara dobavljaču da dobijete licencu:", lic_copy:"Kopiraj ID", lic_load:"Učitaj licencu (.lic)…", lic_done:"Licenca je aktivirana.", copied:"Kopirano",
 last_q:"Učitati posljednji projekat?", saved:"Projekat spremljen", loaded:"Projekat učitan", settings_saved:"Postavke su spremljene.", settings_loaded:"Postavke su učitane; sekcije, naziv i izlazni folder ostali su kakvi jesu.",
 dirty_q:"Postoje nespremljene izmjene. Nastaviti bez spremanja?", theme:"Tema", browse_hint:"…", files_sel:"{0} datoteka", rows:"redova", err_generic:"Greška",
 flt_proj:"Projekat", flt_all:"Sve datoteke", flt_prn:"Ispisi", flt_lic:"Licenca", flt_word:"Word", flt_set:"Postavke",
 dlg_out:"Izlazni folder", dlg_open:"Otvori projekat", dlg_save:"Spremi projekat", dlg_files3:"Odaberite 3 datoteke osovine (horizontala, uzdužni, poprečni)", dlg_file:"Odaberite datoteku", dlg_set_save:"Spremi postavke", dlg_set_load:"Učitaj postavke", dlg_tpl:"Word template", dlg_lic:"Datoteka licence",
},
en: {
 nav_project:"Project", nav_sections:"Alignment segments", nav_params:"Parameters", nav_sight:"Sight distance", nav_run:"Generate",
 new:"New", open:"Open…", save:"Save", save_as:"Save as…", untitled:"New project", unsaved:"not saved",
 p_title:"Project", p_sub:"Basic data about the road section and the output.", p_name:"Section name", p_vr:"Design speed Vr [km/h]", p_out:"Output folder", p_browse:"Browse…",
 p_lang:"Document language", p_lang_h:"Language of the Word/Excel/DXF outputs.", p_notes:"Text for the study", p_notes_h:"Title page and additional descriptions included in the study.",
 p_date:"Date / version (title page)", p_desc:"Additional alignment description (Introduction)", p_remarks:"Additional remarks / assumptions (one per line, Appendix C)",
 p_settings:"Settings for the next project", p_settings_h:"Save the advanced parameters (without segments and printouts) and load them in a new project.", p_save_set:"Save settings…", p_load_set:"Load settings…",
 s_title:"Alignment segments", s_sub:"In order of chainage. Each segment has its own type: separate carriageway axes, central axis, or a single axis.", s_add:"Add segment", s_edit:"Edit", s_del:"Remove", s_up:"Up", s_down:"Down",
 s_empty:"No segments yet. Add the first segment and choose the axis printouts (horizontal, longitudinal profile, cross-slopes).", s_confirm_del:"Remove segment {0}?",
 t_razdvojene:"Two separate axes (right and left carriageway)", t_centralna:"Central axis (one printout, both directions)", t_jedna_naprijed:"Single axis – direction of increasing chainage", t_jedna_nazad:"Single axis – direction of decreasing chainage",
 r_desna:"RIGHT axis (right carriageway, driving in the direction of chainage)", r_lijeva:"LEFT axis (left carriageway, driving against chainage)", r_centralna:"CENTRAL axis", r_osovina:"Axis",
 f_h:"Horizontal axis (elements)", f_v:"Longitudinal profile (break points)", f_x:"Cross-slopes", f_pick3:"Choose all 3 files at once (automatic recognition)", f_none:"not selected",
 d_title_new:"New segment", d_title_edit:"Alignment segment", d_type:"Segment type", d_from:"Chainage FROM [m]", d_to:"TO [m]", d_auto:"Set FROM/TO from the printouts",
 d_caps:"Design-speed zones Vr (optional)", d_caps_h:"One row: FROM; TO; Vr km/h. Inside a zone the calculation (Vp, Rmin, sight-distance rays) uses that design speed.", d_caps_why:"Note on the zones (not used in calculation)",
 d_cs:"Cross-slope column of the LEFT side (lane number, empty = automatic)", d_cross:"Cross-section and offset of the driving-lane axis (empty = default)",
 d_half:"Central axis: HALF width of the median [m]", d_wr:"Lane widths RIGHT of the road axis [m] (e.g. 3.5, 3.5)", d_wl:"Lane widths LEFT of the road axis [m] (e.g. 3.5, 3.5)",
 d_or:"Driver's eye axis RIGHT of the carriageway axis [m]", d_ol:"Driver's eye axis LEFT of the carriageway axis [m]", d_range:"Common range of the printouts: {0} – {1} m. Adjust FROM/TO to the actual segment.",
 ok:"OK", cancel:"Cancel", close:"Close", yes:"Yes", no:"No",
 e_range:"Chainages FROM / TO are not valid (TO must be greater than FROM).", e_file:"File does not exist: {0}", e_cap:"Vr zone: invalid row '{0}' (FROM; TO; Vr).", e_num:"Invalid number: {0}",
 e_unrec:"Not all three file kinds were recognised – complete them manually.", dlg_pick_one:"Select a file.", s_lx:"Import alignments from LandXML", s_lx_wait:"Reading LandXML (large files take a few minutes)…", s_lx_replace:"Replace the existing segments with the alignments from LandXML?", s_lx_ok:"Imported alignments:", dlg_opening:"Opening the file dialog …", e_nodlg:"The file dialog is not available – type the path manually.",
 pa_title:"Advanced parameters", pa_sub:"Driving model, tables from Annex 2 of the Rulebook and vehicles for the dynamic calculation (chapter 5).", pa_reset:"Restore defaults",
 pa_model:"Driving model", pa_tables:"Tables", pa_tables_h:"Values separated by comma or space. Vp–R uses the Vr and Rmin tables.", pa_veh:"Vehicles", pa_veh_h:"vlim empty = max Vr; b and idle empty = general values; P empty = traction curve from the Rulebook.",
 pa_addveh:"Add vehicle", pa_delveh:"Remove last", pa_tpl:"Word template", pa_tpl_h:"If selected, a study in the template is produced in addition to the original one. Empty fields stay as in the template.", pa_tpl_file:"Template (.docx)", pa_tpl_clear:"Remove template",
 sc_korak:"Calculation step Δs [m]", sc_a:"Acceleration a [m/s²]", sc_d:"Deceleration d [m/s²]", sc_ulazna_brzina:"Entry speed at the start of the alignment [km/h] (empty = Vr + increment)", sc_dodatak_maxVr:"max Vr = Vr + [km/h]",
 sc_maxVr_tab:"max Vr per Table 3-04 [km/h] (empty = no limit)", sc_obrazac_puta:"Speed-change distance by formula 0.1·Vavg·ΔV: 1 = yes, 0 = kinematics with a and d", sc_max_nagib:"Reference maximum longitudinal grade [%]",
 sc_rho:"Air density ρ [kg/m³]", sc_b:"Specific consumption b [l/kWh]", sc_prazan_hod:"Idle [l/h]",
 tb_Vr_tab:"Vr [km/h]", tb_Rmin_tab:"Rmin [m]", tb_fT:"fT", tb_fR:"fR", tb_iN_tab:"Vp–iN: grade iN [%]", tb_ViN_tab:"Vp–iN: speed [km/h]",
 v_naziv:"Name", v_kratko:"Short", e_tables:"Tables Vr, Rmin, fT and fR must have the same number of values.", e_tab2:"Vp–iN table: the number of grades and speeds must be equal.", e_tab3:"Rmin and iN values must be increasing.",
 g_title:"Sight distance", g_sub:"Sight rays, required and expected sight distance, passing.", g_on:"Include sight distance (DXF drawings + Excel)", g_on_h:"Output: DXF drawings (open in AutoCAD; Save As → DWG) + Excel with results.",
 g_params:"Ray parameters", g_sides:"Draw rays from the driver's eye axis on the side of the carriageway axis", g_right:"right lane", g_left:"left lane", g_edges:"Draw carriageway edges (red lines)", g_png:"Also produce a PNG preview of the drawing",
 g_obst:"Expected sight distance – obstacles", g_obst_h:"Obstacle offset from the outer carriageway edge.", g_types:"Obstacle types and offset [m]", g_type_name:"Name", g_type_off:"Offset [m]", g_default:"Type that applies to ALL curves (radii and transition curves)",
 g_exc:"Exceptions by chainage", g_exc_h:"E.g. a bridge or tunnel covering only part of an element.", g_exc_add:"Add exception", g_exc_sec:"Seg.", g_exc_axis:"Axis", g_exc_obst:"Obstacle", g_exc_side:"Side",
 g_elems:"Alignment elements", g_elems_h:"Select one or more rows, then \"Edit selected\" to set the obstacle type or offset at once.", g_load:"Load elements from printouts", g_edit_sel:"Edit selected…", g_clear_sel:"Clear entry for selected",
 g_kind:"Kind", g_el:"El.", g_from:"From [m]", g_to:"To [m]", g_all_curves:"for all curves", g_side:"side", g_no_elems:"No elements loaded – first choose the axis files in the segments.",
 g_side_in:"inside (towards the curve centre)", g_side_out:"outside", g_side_r:"right (chainage direction)", g_side_l:"left (chainage direction)", g_type:"Obstacle type", g_or_off:"OR offset from the carriageway edge [m]", g_all:"all",
 g_selected:"Selected elements: {0}", e_type_off:"Specify the obstacle type or an offset.", e_one_side:"Select at least one side of the axis.", e_def_type:"Type '{0}' has no offset in the type table.",
 k_ofset:"Default lane width / 2 – offset of the driving-lane axis [m]", k_h_oka:"Driver's eye height above the grade line [m]", k_h_prepreke:"Object height [m] (empty = automatic, Table 29)", k_dodatak_L:"Allowance on stopping distance Lz [m]",
 k_L_zahtijevano:"REQUIRED ray length L [m] (empty = no such drawing)", k_Lmax:"Maximum ray length in the expected-sight-distance calculation [m]", k_korak_crtez:"Ray spacing on the drawing [m]", k_korak_proracun:"Ray and envelope calculation step [m]",
 k_mjerilo:"Drawing scale (1:N)", k_ivica_debljina:"Thickness of the red carriageway-edge line [mm on paper]",
 o_title:"Optical analyses study (passing)", o_on:"Produce optical analyses (Word)", o_tip:"Road type", o_tip_a:"auto (from segments)", o_tip_d:"two-way (Table 30, min. 25 %)", o_tip_r:"divided (Pzp criterion)",
 o_grupa:"Technical group of the road", o_Pp_po:"Speed for Pp", o_min_proc:"Minimum % of passing sight distance", o_h:"Object height for passing [m]", o_korak:"Table step in Word [m]",
 r_title:"Generate study", r_sub:"Choose the outputs and start the calculation.", r_word:"Driving-dynamics analysis (Word)", r_word_h:"Driving-dynamics analyses", r_excel:"Excel workbook", r_excel_h:"Formulas, tables and charts",
 r_sight:"Sight distance (DXF + Excel)", r_sight_h:"Rays, required and expected sight distance", r_optika:"Optical analyses (Word)", r_optika_h:"Optical analyses and passing", r_ifc:"IFC 4.3 alignments", r_ifc_h:"IfcAlignment: horizontal, vertical, 3D curve", r_dwg:"DWG drawings", r_dwg_h:"From DXF, via the free ODA File Converter", r_lx:"LandXML (Civil 3D)", r_lx_h:"Alignments and profiles for a Civil 3D corridor", r_kor:"Civil 3D corridor drive-through (HTML)", r_kor_h:"Import a LandXML corridor: barriers, terrain, tunnel and bridge", k_file:"Corridor LandXML (Civil 3D)", k_pick:"Browse …", k_from:"Chainage from [m]", k_to:"Chainage to [m]", k_off:"Obstacle (steel barrier) offset from carriageway edge [m]", k_rails:"Align the sight-distance calculation with the corridor (lane width, obstacles, bridge/tunnel)", k_h:"The corridor is read from a Civil 3D LandXML (alignments, profiles, cross-sections, terrain). The picture follows the calculation: eye, obstacles and rays come from the UNA calculation; alignment takes lane width and obstacle type from the corridor.", e_kor:"Corridor: select a LandXML file.",
 r_run:"Generate study", r_running:"Calculating…", r_done:"Done", r_files:"Generated files", r_open:"Open", r_folder:"Folder", r_log:"Calculation log", r_errors:"Input check", r_nothing:"Select at least one output.", r_noout:"Choose the output folder (Project step).", r_fail:"Error during generation",
 r_open_folder:"Open output folder", r_ready:"Ready", r_summary:"Summary",
 lic_ok:"Licence active", lic_bad:"Licence not activated", lic_act:"Activate…", lic_title:"Licence activation", lic_id:"Send this computer ID to the supplier to obtain a licence:", lic_copy:"Copy ID", lic_load:"Load licence (.lic)…", lic_done:"The licence has been activated.", copied:"Copied",
 last_q:"Load the last project?", saved:"Project saved", loaded:"Project loaded", settings_saved:"Settings saved.", settings_loaded:"Settings loaded; segments, name and output folder were left as they are.",
 dirty_q:"There are unsaved changes. Continue without saving?", theme:"Theme", browse_hint:"…", files_sel:"{0} files", rows:"rows", err_generic:"Error",
 flt_proj:"Project", flt_all:"All files", flt_prn:"Printouts", flt_lic:"Licence", flt_word:"Word", flt_set:"Settings",
 dlg_out:"Output folder", dlg_open:"Open project", dlg_save:"Save project", dlg_files3:"Select the 3 axis files (horizontal, longitudinal, cross-slopes)", dlg_file:"Select a file", dlg_set_save:"Save settings", dlg_set_load:"Load settings", dlg_tpl:"Word template", dlg_lic:"Licence file",
}};
let LANG = "sr";
const t = (k, ...a) => { let s = (L[LANG][k] ?? L.sr[k] ?? k); a.forEach((v, i) => s = s.replace("{" + i + "}", v)); return s; };

/* ---------------------------------------------------------------- state */
const S = { cfg: { projekat: "", Vr: 100, sekcije: [] }, path: null, dirty: false, page: "project", defaults: {}, lic: {}, ui: {}, tab: "model",
            run: { running: false, lines: [], outs: [], error: null, done: false }, elrows: [], elset: {}, exc: [], sel: new Set(), seen: new Set(["project"]) };
const ROLES = { razdvojene: ["desna", "lijeva"], centralna: ["centralna"], jedna_naprijed: ["osovina"], jedna_nazad: ["osovina"] };
const TYPES = ["razdvojene", "centralna", "jedna_naprijed", "jedna_nazad"];
const num = (s, d = null) => { s = String(s ?? "").trim().replace(",", "."); if (s === "") return d; const x = Number(s); if (!isFinite(x)) throw new Error(t("e_num", s)); return x; };
const fmtn = (x, n = 3) => (x == null ? "" : String(+(+x).toFixed(n)));
const base = p => String(p || "").split(/[\\/]/).pop();
const dirty = () => { S.dirty = true; renderTop(); };
function toast(msg, err) { const e = h("div", { class: "toast" + (err ? " err" : "") }, msg); $("#toast-root").append(e); setTimeout(() => e.remove(), err ? 6000 : 2800); }

/* ---------------------------------------------------------------- native dialogs */
const FLT = () => ({ proj: [[t("flt_proj"), "*.json"], [t("flt_all"), "*.*"]], prn: [[t("flt_prn"), "*.txt;*.dat;*.lst"], [t("flt_all"), "*.*"]], lic: [[t("flt_lic"), "*.lic"], [t("flt_all"), "*.*"]], word: [[t("flt_word"), "*.docx;*.dotx"]], set: [[t("flt_proj"), "*.json"]] });
async function pick(mode, title, filters, extra = {}) {
  if (S.stubPick) { const r = await api("pick", { mode, title, filters, ...extra }); return r.paths || []; }   // testovi
  return browseDialog(mode, title, filters || [], extra);
}
/* Ugrađeni odabir datoteka/foldera (radi bez Windows dijaloga) */
function browseDialog(mode, title, filters, extra) {
  const multiple = !!extra.multiple; let cur = extra.initial || ""; let sel = new Set(); let fi = 0;
  const exts = () => { const pat = (filters[fi] && filters[fi][1]) || "*.*"; if (pat.includes("*.*")) return null; return pat.split(/[;,\s]+/).map(x => x.replace(/^\*/, "").toLowerCase()).filter(Boolean); };
  const pathIn = txt("", { class: "mono", style: "width:100%" }); const nameIn = txt(extra.name || "", { style: "width:100%" });
  const list = h("div", { style: "border:1px solid var(--line,#8884);border-radius:8px;height:340px;overflow:auto;padding:4px" }); const side = h("div", { style: "display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px" });
  const fsel = filters.length > 1 ? h("select", { onchange: e => { fi = +e.target.value; go(pathIn.value); } }, filters.map((f, i) => h("option", { value: i }, f[0]))) : null;
  const sz = n => n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : n > 1024 ? Math.round(n / 1024) + " KB" : n + " B";
  async function go(p) {
    const r = await api("ls", { path: p }); cur = r.path; pathIn.value = cur; sel.clear(); side.replaceChildren(...r.roots.map(x => h("button", { class: "btn sm", onclick: () => go(x.p) }, x.n)));
    const ex = exts(); const rows = [];
    if (r.parent) rows.push(h("div", { class: "file", style: "cursor:pointer;padding:5px 8px", onclick: () => go(r.parent) }, "📁 .."));
    if (r.error) rows.push(h("div", { class: "hint", style: "padding:8px" }, r.error));
    for (const e of r.entries) {
      const full = cur.replace(/[\\/]+$/, "") + (cur.includes("\\") ? "\\" : "/") + e.n;
      if (e.d) rows.push(h("div", { class: "file", style: "cursor:pointer;padding:5px 8px", onclick: () => go(full) }, "📁 " + e.n));
      else if (mode !== "folder" && (!ex || ex.some(x => e.n.toLowerCase().endsWith(x)))) {
        const row = h("div", { class: "file", style: "cursor:pointer;padding:5px 8px;display:flex;gap:8px;border-radius:6px", onclick: () => { if (!multiple) { sel.clear(); [...list.children].forEach(c => c.style.background = ""); } if (sel.has(full)) { sel.delete(full); row.style.background = ""; } else { sel.add(full); row.style.background = "rgba(56,130,246,.25)"; } if (mode === "save") nameIn.value = e.n; } }, h("span", { class: "grow" }, "📄 " + e.n), h("span", { class: "hint" }, sz(e.s)));
        rows.push(row);
      }
    }
    list.replaceChildren(...rows);
  }
  const body = h("div", {}, side, h("div", { class: "row", style: "margin-bottom:8px;gap:8px" }, h("div", { class: "grow" }, pathIn), h("button", { class: "btn sm", onclick: () => go(pathIn.value) }, "↵")), list,
    mode === "save" ? h("div", { style: "margin-top:8px" }, nameIn) : null, fsel ? h("div", { style: "margin-top:8px" }, fsel) : null);
  pathIn.addEventListener("keydown", e => { if (e.key === "Enter") go(pathIn.value); });
  go(cur);
  return modal({ title, body, wide: true, okText: mode === "folder" ? "OK" : null,
    onOk: () => {
      const sep = cur.includes("\\") ? "\\" : "/";
      if (mode === "folder") return [cur];
      if (mode === "save") { const n = nameIn.value.trim(); if (!n) throw new Error(t("e_nodlg")); return [cur.replace(/[\\/]+$/, "") + sep + n]; }
      if (!sel.size) throw new Error(t("dlg_pick_one")); return [...sel];
    } }).then(v => v || []);
}
async function pathField(input, mode, title, filters) {
  const p = await pick(mode, title, filters, { initial: input.value }); if (p[0]) { input.value = p[0]; input.dispatchEvent(new Event("input", { bubbles: true })); input.dispatchEvent(new Event("change", { bubbles: true })); }
}

/* ---------------------------------------------------------------- modal */
function modal({ title, body, onOk, okText, wide, small, extra }) {
  return new Promise(res => {
    const close = v => { bg.remove(); document.removeEventListener("keydown", key); res(v); };
    const errBox = h("div", { class: "alert err", style: "display:none;margin-bottom:12px" });
    const ok = h("button", { class: "btn primary", onclick: async () => { try { const v = onOk ? await onOk() : true; if (v !== false) close(v ?? true); } catch (e) { errBox.textContent = e.message; errBox.style.display = ""; errBox.scrollIntoView({ block: "nearest" }); } } }, okText || t("ok"));
    const cancel = h("button", { class: "btn", onclick: () => close(null) }, t("cancel"));
    const bg = h("div", { class: "modal-bg", onmousedown: e => { if (e.target === bg) { /* ne zatvaraj klikom pored */ } } },
      h("div", { class: "modal" + (small ? " sm" : ""), role: "dialog", "aria-modal": "true", style: wide ? "width:min(1000px,100%)" : "" },
        h("header", {}, h("h2", {}, title), h("button", { class: "btn ghost sm", onclick: () => close(null), "aria-label": t("close") }, "✕")),
        h("div", { class: "body" }, errBox, body), h("footer", {}, extra || [], cancel, ok)));
    const key = e => { if (e.key === "Escape") close(null); };
    document.addEventListener("keydown", key); $("#modal-root").append(bg);
    const f = bg.querySelector("input,select,textarea"); if (f) f.focus();
  });
}
const confirmBox = (msg, okText) => modal({ title: t("close") === "Zatvori" ? "Potvrda" : "Confirm", small: true, body: h("p", {}, msg), okText: okText || t("yes") });
const infoBox = msg => modal({ title: "UNA", small: true, body: h("p", {}, msg), okText: t("ok") });

/* ---------------------------------------------------------------- shell */
const PAGES = ["project", "sections", "params", "sight", "run"];
function renderNav() {
  const nav = $("#nav"); nav.replaceChildren();
  PAGES.forEach((p, i) => {
    const done = (p === "project" && S.cfg.projekat && S.cfg.izlaz) || (p === "sections" && S.cfg.sekcije.length) ;
    nav.append(h("button", { class: (S.page === p ? "on " : "") + (done && S.page !== p ? "done" : ""), onclick: () => go(p) }, h("span", { class: "n" }, done && S.page !== p ? "✓" : i + 1), t("nav_" + p)));
  });
  $("#ver").textContent = "v" + (S.version || "");
  document.querySelectorAll("#langseg button").forEach(b => b.classList.toggle("on", b.dataset.l === LANG));
  const lb = $("#licbox"); lb.className = "lic" + (S.lic.ok ? "" : " bad"); lb.replaceChildren(...[h("b", {}, S.lic.ok ? "● " + t("lic_ok") : "● " + t("lic_bad")), h("div", { style: "opacity:.8" }, S.lic.text || ""),
    S.lic.ok ? null : h("button", { class: "btn sm", onclick: licenseDialog }, t("lic_act"))].filter(Boolean));
}
function renderTop() {
  const top = $("#top"); top.replaceChildren(
    h("div", { class: "ttl" }, h("b", {}, S.cfg.projekat || t("untitled")), h("span", {}, (S.path || t("unsaved")) + (S.dirty ? "  •" : ""))),
    h("button", { class: "btn sm", onclick: newProject }, t("new")), h("button", { class: "btn sm", onclick: openProject }, t("open")),
    h("button", { class: "btn sm primary", onclick: () => saveProject(false) }, t("save")), h("button", { class: "btn sm", onclick: () => saveProject(true) }, t("save_as")));
}
function go(p) { collectPage(); S.page = p; S.seen.add(p); render(); }
function render() { renderNav(); renderTop(); const pg = $("#page"); pg.replaceChildren(PAGE_FN[S.page]()); pg.scrollTop = 0; }
let collectFn = null; function collectPage() { if (collectFn) { try { collectFn(); } catch (e) { } } collectFn = null; }

/* ---------------------------------------------------------------- project file ops */
async function newProject() { if (S.dirty && !(await confirmBox(t("dirty_q")))) return; S.cfg = { projekat: "", Vr: 100, sekcije: [], jezik: LANG }; S.path = null; S.dirty = false; S.elrows = []; S.elset = {}; S.exc = []; loadSightState(); S.page = "project"; render(); }
async function openProject() {
  if (S.dirty && !(await confirmBox(t("dirty_q")))) return;
  const p = (await pick("open", t("dlg_open"), FLT().proj))[0]; if (p) await loadProject(p);
}
async function loadProject(p) {
  const r = await api("load", { path: p }); if (r.error) return toast(r.error, true);
  S.cfg = r.cfg; S.cfg.sekcije = S.cfg.sekcije || []; S.path = p; S.dirty = false; loadSightState(); S.page = "project"; render(); toast(t("loaded"));
}
async function saveProject(as) {
  collectPage(); let p = S.path;
  if (as || !p) { p = (await pick("save", t("dlg_save"), FLT().proj, { name: base(S.path) || "projekat.json" }))[0]; if (!p) return; if (!/\.json$/i.test(p)) p += ".json"; }
  const cfg = buildCfg(); const r = await api("save", { path: p, cfg }); if (r.error) return toast(r.error, true);
  S.path = p; S.dirty = false; renderTop(); toast(t("saved"));
}
function buildCfg() { const c = JSON.parse(JSON.stringify(S.cfg)); c.jezik = c.jezik || LANG; if (c.preglednost !== undefined || S.sightTouched) { /* već u cfg */ } return c; }
async function licenseDialog() {
  const idIn = h("input", { type: "text", class: "mono", readonly: true, value: S.lic.id || "" });
  await modal({ title: t("lic_title"), okText: t("close"), body: h("div", { class: "grid" },
    S.lic.ok ? null : h("div", { class: "alert err" }, S.lic.text), h("p", {}, t("lic_id")), idIn,
    h("div", { class: "row" }, h("button", { class: "btn", onclick: async () => { try { await navigator.clipboard.writeText(idIn.value); } catch (e) { idIn.select(); document.execCommand("copy"); } toast(t("copied")); } }, t("lic_copy")),
      h("button", { class: "btn primary", onclick: async () => { const p = (await pick("open", t("dlg_lic"), FLT().lic))[0]; if (!p) return; const r = await api("license", { path: p }); if (r.error) return toast(r.error, true); toast(t("lic_done")); await refreshState(); } }, t("lic_load")))) });
}
async function refreshState() { const st = await api("state", { lang: LANG }); S.lic = st.license; S.defaults = st.defaults; S.version = st.version; S.stubPick = !!st.stub_pick; renderNav(); }

/* ---------------------------------------------------------------- UI helpers */
const field = (label, input, help) => h("div", { class: "field" }, h("label", {}, label), input, help ? h("div", { class: "help" }, help) : null);
const txt = (v, a = {}) => h("input", { type: "text", value: v ?? "", ...a });
function pathRow(inp, mode, title, filters) { return h("div", { class: "row" }, h("div", { class: "grow" }, inp), h("button", { class: "btn", onclick: () => pathField(inp, mode, title, filters) }, t("p_browse"))); }
const sw = (label, checked, onchange, id) => { const i = h("input", { type: "checkbox", checked, onchange: e => onchange(e.target.checked) }); return h("label", { class: "sw" }, i, h("span", {}, label)); };

/* ================================================================ PAGE 1 – PROJECT */
function pageProject() {
  const c = S.cfg;
  const name = txt(c.projekat, { oninput: e => { c.projekat = e.target.value; dirty(); } });
  const vr = txt(c.Vr, { inputmode: "decimal", oninput: e => { const v = num(e.target.value, 100); c.Vr = v; dirty(); } });
  const out = txt(c.izlaz || "", { oninput: e => { c.izlaz = e.target.value.trim(); dirty(); }, placeholder: "C:\\…\\izlaz" });
  const lang = h("select", { onchange: e => { c.jezik = e.target.value; dirty(); } }, h("option", { value: "sr" }, "Bosanski"), h("option", { value: "en" }, "English"));
  lang.value = c.jezik || LANG;
  const ta = (k, rows = 3) => { const e = h("textarea", { rows, oninput: ev => { c[k] = ev.target.value; dirty(); } }); e.value = c[k] || ""; return e; };
  const rem = h("textarea", { rows: 4, oninput: ev => { c.napomene = ev.target.value.split("\n").map(x => x.trim()).filter(Boolean); dirty(); } });
  rem.value = [].concat(c.napomene || []).join("\n");
  return h("div", { class: "wrap" },
    h("div", {}, h("h1", {}, t("p_title")), h("p", { class: "sub" }, t("p_sub"))),
    h("div", { class: "card" }, h("div", { class: "grid g2" },
      field(t("p_name"), name), field(t("p_vr"), vr),
      field(t("p_out"), pathRow(out, "folder", t("dlg_out"))), field(t("p_lang"), lang, t("p_lang_h")))),
    h("div", { class: "card" }, h("h3", {}, t("p_notes")), h("p", { class: "hint" }, t("p_notes_h")),
      h("div", { class: "grid" }, field(t("p_date"), txt(c.datum || "", { oninput: e => { c.datum = e.target.value; dirty(); } })),
        field(t("p_desc"), ta("opis_sekcija")), field(t("p_remarks"), rem))),
    h("div", { class: "card" }, h("h3", {}, t("p_settings")), h("p", { class: "hint" }, t("p_settings_h")),
      h("div", { class: "row" }, h("button", { class: "btn", onclick: saveSettings }, t("p_save_set")), h("button", { class: "btn", onclick: loadSettings }, t("p_load_set")))),
    navButtons(null, "sections"));
}
function navButtons(prev, next) {
  return h("div", { class: "row", style: "justify-content:space-between" }, prev ? h("button", { class: "btn", onclick: () => go(prev) }, "← " + t("nav_" + prev)) : h("span"),
    next ? h("button", { class: "btn primary", onclick: () => go(next) }, t("nav_" + next) + " →") : null);
}
async function saveSettings() {
  const p = (await pick("save", t("dlg_set_save"), FLT().set, { name: "postavke.json" }))[0]; if (!p) return;
  const c = buildCfg(); ["sekcije", "projekat", "izlaz"].forEach(k => delete c[k]);
  const r = await api("save", { path: /\.json$/i.test(p) ? p : p + ".json", cfg: c }); if (r.error) return toast(r.error, true); toast(t("settings_saved"));
}
async function loadSettings() {
  const p = (await pick("open", t("dlg_set_load"), FLT().set))[0]; if (!p) return;
  const r = await api("readjson", { path: p }); if (r.error) return toast(r.error, true);
  const keep = { sekcije: S.cfg.sekcije, projekat: S.cfg.projekat, izlaz: S.cfg.izlaz }; const d = r.data; ["sekcije", "projekat", "izlaz"].forEach(k => delete d[k]);
  S.cfg = Object.assign({}, S.cfg, d, keep); loadSightState(); dirty(); render(); toast(t("settings_loaded"));
}

/* ================================================================ PAGE 2 – SECTIONS */
function secOf(s) { return ROLES[s.tip].map(r => base((s[r] || {}).h)).join(", "); }
function pageSections() {
  const secs = S.cfg.sekcije; const lo = Math.min(...secs.map(s => +s.od), 0), hi = Math.max(...secs.map(s => +s.do), 1), span = (hi - lo) || 1;
  const list = secs.length ? h("div", { class: "secs" }, secs.map((s, i) => h("div", { class: "sec" },
      h("div", { class: "no" }, i + 1),
      h("div", {}, h("div", { class: "t" }, t("t_" + s.tip)), h("div", { class: "m" }, h("span", { class: "range" }, `${fmtn(s.od)} – ${fmtn(s.do)} m`), "  ·  ", secOf(s),
        (s.zone_Vr || []).length ? h("span", { class: "chip warn", style: "margin-left:8px" }, s.zone_Vr.map(z => `Vr ${z.v}`).join(", ")) : null),
        h("div", { class: "bar" }, h("i", { style: `left:${(s.od - lo) / span * 100}%;width:${Math.max(1, (s.do - s.od) / span * 100)}%` }))),
      h("div", { class: "row" }, h("button", { class: "btn sm", disabled: i === 0, title: t("s_up"), onclick: () => moveSec(i, -1) }, "↑"), h("button", { class: "btn sm", disabled: i === secs.length - 1, title: t("s_down"), onclick: () => moveSec(i, 1) }, "↓"),
        h("button", { class: "btn sm", onclick: () => editSec(i) }, t("s_edit")), h("button", { class: "btn sm danger", onclick: () => delSec(i) }, t("s_del"))))))
    : h("div", { class: "empty" }, t("s_empty"));
  return h("div", { class: "wrap" }, h("div", { class: "row" }, h("div", { class: "grow" }, h("h1", {}, t("s_title")), h("p", { class: "sub" }, t("s_sub"))), h("button", { class: "btn", onclick: importLX, style: "margin-right:8px" }, t("s_lx")), h("button", { class: "btn primary", onclick: () => editSec(-1) }, "+ " + t("s_add"))),
    list, navButtons("project", "params"));
}
async function importLX() {
  const p = (await pick("open", t("s_lx"), [["LandXML", "*.xml"], [t("flt_all"), "*.*"]], {}))[0]; if (!p) return;
  toast(t("s_lx_wait"));
  let r; try { r = await api("lx_import", { path: p }); } catch (e) { return toast(String(e.message || e), true); }
  if (r.error) return toast(r.error, true);
  if (S.cfg.sekcije.length && !(await confirmBox(t("s_lx_replace")))) return;
  S.cfg.sekcije = r.sekcije; dirty(); render(); toast(t("s_lx_ok") + " " + r.alignments.map(a => a.name).join(", "));
}
function moveSec(i, d) { const L = S.cfg.sekcije; [L[i], L[i + d]] = [L[i + d], L[i]]; dirty(); render(); }
async function delSec(i) { if (await confirmBox(t("s_confirm_del", i + 1))) { S.cfg.sekcije.splice(i, 1); dirty(); render(); } }
async function editSec(i) {
  const cur = i >= 0 ? JSON.parse(JSON.stringify(S.cfg.sekcije[i])) : { tip: "razdvojene", od: "", do: "" };
  const ax = {}; // po ulozi: {h,v,x,cs,pf:{...}} kao stringovi
  const tipSel = h("select", {}, TYPES.map(k => h("option", { value: k }, t("t_" + k)))); tipSel.value = cur.tip;
  const od = txt(cur.od, { inputmode: "decimal" }), dO = txt(cur.do, { inputmode: "decimal" });
  const roleBox = h("div"); const stash = {};
  const toStr = v => v == null ? "" : (Array.isArray(v) ? v.map(x => fmtn(x, 4)).join(", ") : String(v));
  function build() {
    roleBox.replaceChildren(); for (const k of Object.keys(ax)) delete ax[k];
    for (const r of ROLES[tipSel.value]) {
      const sp = stash[r] || cur[r] || {}; const a = ax[r] = {};
      const files = ["h", "v", "x"].map(k => { a[k] = txt(sp[k] || "", { class: "mono" }); return h("div", { class: "kv" }, h("div", { class: "k" }, t("f_" + k)), a[k], h("button", { class: "btn sm", onclick: () => pathField(a[k], "open", t("dlg_file"), FLT().prn) }, "…")); });
      a.cs = txt(sp.cs_col == null ? "" : sp.cs_col + 1, { style: "width:70px" });
      const pf = {}; [["razdjelni_pola", "d_half"], ["trake_desno", "d_wr"], ["trake_lijevo", "d_wl"], ["ofset_desno", "d_or"], ["ofset_lijevo", "d_ol"]].forEach(([k, l]) => pf[k] = field(t(l), txt(toStr(sp[k]))));
      a.pf = pf;
      roleBox.append(h("div", { class: "axis-box" }, h("h4", {}, t("r_" + r)), files,
        h("button", { class: "btn sm", style: "margin:4px 0 8px", onclick: async () => {
            const ps = await pick("open", t("dlg_files3"), FLT().prn, { multiple: true }); if (!ps.length) return;
            const d = await api("detect", { paths: ps }); const found = {};
            for (const p of ps) { const kd = d.kinds[p]; if (kd && !found[kd]) found[kd] = p; }
            for (const [k, p] of Object.entries(found)) a[k].value = p;
            if (Object.keys(found).length < 3) toast(t("e_unrec"), true);
          } }, t("f_pick3")),
        h("details", {}, h("summary", {}, t("d_cross")), h("div", { class: "grid g2", style: "margin-top:10px" }, Object.values(pf), field(t("d_cs"), a.cs)))));
    }
  }
  tipSel.addEventListener("change", () => { for (const [r, a] of Object.entries(ax)) stash[r] = specOf(a, false); build(); });
  function specOf(a, strict) {
    const d = {}; ["h", "v", "x"].forEach(k => d[k] = a[k].value.trim());
    const c = a.cs.value.trim(); if (c) d.cs_col = parseInt(c) - 1;
    for (const k of ["trake_desno", "trake_lijevo"]) { const s = a.pf[k].querySelector("input").value.replace(/;/g, " ").replace(/, /g, " ").trim(); if (s) d[k] = s.split(/\s+/).map(x => num(x)); }
    for (const k of ["razdjelni_pola", "ofset_desno", "ofset_lijevo"]) { const v = num(a.pf[k].querySelector("input").value); if (v != null) d[k] = v; }
    return d;
  }
  const caps = h("textarea", { rows: 3, class: "mono" }); caps.value = (cur.zone_Vr || []).map(z => `${z.od}; ${z.do}; ${z.v}`).join("\n");
  const why = txt(cur.zone_Vr_opis || "");
  const auto = h("button", { class: "btn sm", onclick: async () => {
      const specs = Object.values(ax).map(a => specOf(a, false)); const r = await api("axisrange", { specs });
      if (r.error || r.lo == null) return toast(t("e_file", "") + " " + (r.error || ""), true);
      od.value = fmtn(r.lo); dO.value = fmtn(r.hi); toast(t("d_range", fmtn(r.lo), fmtn(r.hi)));
    } }, t("d_auto"));
  build();
  const body = h("div", {}, h("div", { class: "grid g3", style: "margin-bottom:14px" }, h("div", { style: "grid-column:span 3" }, field(t("d_type"), tipSel)),
      field(t("d_from"), od), field(t("d_to"), dO), h("div", { style: "align-self:end" }, auto)), roleBox,
    h("div", { class: "card", style: "box-shadow:none;margin-top:6px" }, h("h3", {}, t("d_caps")), h("p", { class: "hint" }, t("d_caps_h")), caps, h("div", { style: "height:10px" }), field(t("d_caps_why"), why)));
  const res = await modal({ title: i >= 0 ? t("d_title_edit") : t("d_title_new"), body, wide: true, onOk: () => {
    const s = { tip: tipSel.value, od: num(od.value), do: num(dO.value) };
    if (s.od == null || s.do == null || s.do <= s.od) throw new Error(t("e_range"));
    for (const [r, a] of Object.entries(ax)) { s[r] = specOf(a, true); }
    const cp = []; for (const ln of caps.value.split("\n")) { const l = ln.trim(); if (!l) continue; const p = l.replace(/;/g, " ").split(/\s+/).map(x => num(x)); if (p.length !== 3 || p.includes(null)) throw new Error(t("e_cap", l)); cp.push({ od: p[0], do: p[1], v: p[2] }); }
    if (cp.length) s.zone_Vr = cp; if (why.value.trim()) s.zone_Vr_opis = why.value.trim();
    return s;
  } });
  if (!res || res === true) return;
  if (i >= 0) S.cfg.sekcije[i] = res; else S.cfg.sekcije.push(res);
  S.cfg.sekcije.sort((a, b) => a.od - b.od); dirty(); render();
}

/* ================================================================ PAGE 3 – PARAMETERS */
const SCAL = ["korak", "a", "d", "ulazna_brzina", "dodatak_maxVr", "maxVr_tab", "obrazac_puta", "max_nagib", "rho", "b", "prazan_hod"];
const TABS = ["Vr_tab", "Rmin_tab", "fT", "fR", "iN_tab", "ViN_tab"];
const VEH = [["naziv", 190], ["kratko", 110], ["m", 70], ["P", 60], ["CdA", 60], ["eta", 55], ["vlim", 55], ["gam", 55], ["mu", 55], ["b", 60], ["prazan_hod", 70]];
const VLAB = { naziv: "v_naziv", kratko: "v_kratko" };
const VHEAD = { m: "m [kg]", P: "P [kW]", CdA: "CdA [m²]", eta: "η", vlim: "vlim [km/h]", gam: "γm", mu: "μ", b: "b [l/kWh]", prazan_hod: "idle [l/h]" };
function dflt(k) { return S.cfg[k] !== undefined ? S.cfg[k] : S.defaults[k]; }
function pageParams() {
  const c = S.cfg; const tabs = [["model", t("pa_model")], ["tables", t("pa_tables")], ["veh", t("pa_veh")], ["tpl", t("pa_tpl")]];
  let inner;
  if (S.tab === "model") {
    inner = h("div", { class: "grid g2" }, SCAL.map(k => { let v = dflt(k); if (typeof v === "boolean") v = +v;
      return field(t("sc_" + k), txt(v == null ? "" : v, { inputmode: "decimal", oninput: e => { const s = e.target.value.trim(); if (s === "") { if (k === "ulazna_brzina" || k === "maxVr_tab") c[k] = null; else delete c[k]; } else { try { c[k] = num(s); } catch (_) { return; } } dirty(); } })); }));
  } else if (S.tab === "tables") {
    inner = h("div", {}, h("p", { class: "hint" }, t("pa_tables_h")), h("div", { class: "grid" }, TABS.map(k => field(t("tb_" + k), txt((dflt(k) || []).join(", "), { class: "mono", oninput: e => { const arr = e.target.value.replace(/[,;]/g, " ").split(/\s+/).filter(Boolean).map(Number); if (arr.every(isFinite)) { c[k] = arr; dirty(); } } })))));
  } else if (S.tab === "veh") {
    const veh = () => { if (!c.vozila) c.vozila = JSON.parse(JSON.stringify(S.defaults.vozila)); return c.vozila; };
    const vs = c.vozila || S.defaults.vozila || [];
    const tbl = h("table", { class: "tb" }, h("thead", {}, h("tr", {}, VEH.map(([k]) => h("th", {}, VLAB[k] ? t(VLAB[k]) : (VHEAD[k] || k))))), h("tbody", {}, vs.map((v, i) => h("tr", {}, VEH.map(([k, w]) => h("td", {}, h("input", { type: "text", style: `width:${w}px`, value: v[k] ?? "", oninput: e => { const L = veh(); const s = e.target.value.trim().replace(",", "."); L[i][k] = (k === "naziv" || k === "kratko") ? e.target.value : (s === "" ? null : Number(s)); dirty(); } })))))));
    inner = h("div", {}, h("p", { class: "hint" }, t("pa_veh_h")), h("div", { class: "scroll", style: "max-height:none;overflow-x:auto" }, tbl),
      h("div", { class: "row", style: "margin-top:10px" }, h("button", { class: "btn", onclick: () => { veh().push({ naziv: "novo vozilo", kratko: "Vozilo", m: 30000, P: 300, CdA: 5.0, eta: 0.9, vlim: 80, gam: 1.06, mu: 0.5 }); dirty(); render(); } }, "+ " + t("pa_addveh")),
        h("button", { class: "btn", onclick: () => { const L = veh(); if (L.length > 1) { L.pop(); dirty(); render(); } } }, t("pa_delveh"))));
  } else {
    const tp = c.template || {}; const set = (k, v) => { c.template = c.template || {}; if (v) c.template[k] = v; else delete c.template[k]; if (!Object.keys(c.template).length) delete c.template; dirty(); };
    const F = [["folder_sr", "Folder – naziv (SR)"], ["folder_en", "Folder – naziv (ENG)"], ["datum", "Datum / Date"], ["vodeci", "Vodeći projektant / Lead designer"], ["odgovorni", "Odgovorni projektant / Responsible designer"], ["saradnici", "Saradnici / Associates"], ["saradnici_en", "Associates (ENG)"], ["naslov_izvjestaj", "Naslov – tekstualna dokumentacija (SR / ENG)"], ["naslov_numericki", "Naslov – numerička dokumentacija (SR / ENG)"], ["naslov_graficki", "Naslov – grafička dokumentacija (SR / ENG)"]];
    const tf = txt(tp.file || "", { class: "mono", oninput: e => set("file", e.target.value.trim()) });
    inner = h("div", {}, h("p", { class: "hint" }, t("pa_tpl_h")), field(t("pa_tpl_file"), pathRow(tf, "open", t("dlg_tpl"), FLT().word)), h("div", { class: "grid g2", style: "margin-top:12px" }, F.map(([k, l]) => field(l, txt(tp[k] || "", { oninput: e => set(k, e.target.value.trim()) })))),
      h("div", { style: "margin-top:10px" }, h("button", { class: "btn danger sm", onclick: () => { delete c.template; dirty(); render(); } }, t("pa_tpl_clear"))));
  }
  return h("div", { class: "wrap" }, h("div", { class: "row" }, h("div", { class: "grow" }, h("h1", {}, t("pa_title")), h("p", { class: "sub" }, t("pa_sub"))),
      h("button", { class: "btn", onclick: () => { [...SCAL, ...TABS, "vozila"].forEach(k => delete c[k]); dirty(); render(); } }, t("pa_reset"))),
    h("div", { class: "card" }, h("div", { class: "tabs" }, tabs.map(([k, l]) => h("button", { class: S.tab === k ? "on" : "", onclick: () => { S.tab = k; render(); } }, l))), inner),
    navButtons("sections", "sight"));
}

/* ================================================================ PAGE 4 – SIGHT DISTANCE */
const PFIELDS = [["ofset", 1.75, false], ["h_oka", 1.0, false], ["h_prepreke", "", true], ["dodatak_L", 0.0, false], ["Lmax", 500.0, false], ["korak_crtez", 20.0, false], ["korak_proracun", 5.0, false], ["mjerilo", 1000, false], ["ivica_debljina", 0.3, false]];
function loadSightState() {
  const p = S.cfg.preglednost || {}; S.sightTouched = false;
  S.pre = { f: {}, sd: (p.strane || ["desno", "lijevo"]).includes("desno"), sl: (p.strane || ["desno", "lijevo"]).includes("lijevo"), ivice: p.ivice !== false, png: !!p.png,
            tipovi: Object.entries(p.tipovi_prepreka || { "otvorena trasa": "", "most": 1.17, "tunel": "" }).map(([k, v]) => [k, v === "" ? "" : String(v)]), zadani: p.zadani_tip || "" };
  PFIELDS.forEach(([k, d]) => S.pre.f[k] = p[k] != null ? String(p[k]) : String(d));
  S.exc = (p.prepreke || []).filter(e => e.element == null || e.element === "").map(e => ({ ...e }));
  S.elset = {}; (p.prepreke || []).filter(e => e.element != null && e.element !== "").forEach(e => S.elset[[e.sekcija || "", e.osovina || "", e.element].join("|")] = [e.tip || "", e.ofset ?? "", e.strana || "unutra"]);
}
function composePre() {
  const P = S.pre, d = {};
  for (const [k, , opt] of PFIELDS) { const x = num(P.f[k]); if (x == null && !opt) throw new Error(t("k_" + k) + ": ?"); if (x != null) d[k] = x; }
  d.strane = [P.sd ? "desno" : null, P.sl ? "lijevo" : null].filter(Boolean); if (!d.strane.length) throw new Error(t("e_one_side"));
  d.ivice = P.ivice; d.ukljuci = true; d.png = P.png;
  const tv = {}; P.tipovi.forEach(([k, v]) => { if (k.trim() && String(v).trim() !== "") tv[k.trim()] = num(v); }); d.tipovi_prepreka = tv; d.zadani_tip = P.zadani.trim();
  if (d.zadani_tip && !(d.zadani_tip in tv)) throw new Error(t("e_def_type", d.zadani_tip));
  const pre = S.exc.map(e => ({ ...e }));
  for (const [key, [tip, of, st]] of Object.entries(S.elset)) { const [sek, os, no] = key.split("|"); const e = { element: +no, strana: st }; if (sek) e.sekcija = +sek; if (os) e.osovina = os; if (tip) e.tip = tip; else e.ofset = num(of); pre.push(e); }
  d.prepreke = pre; return d;
}
function syncSight() { if (S.sightTouched || S.cfg.preglednost) { S.cfg.preglednost = composePre(); } }
const optOn = k => (S.cfg.gui_opcije || {})[k];
function setOpt(k, v) { S.cfg.gui_opcije = Object.assign({ word: true, excel: true, preglednost: false, optika: false }, S.cfg.gui_opcije || {}); S.cfg.gui_opcije[k] = v; dirty(); }
const OPT_DEF = { tip_puta: "auto", grupa: "A", Pp_po: "Vr", min_proc: 25.0, h_predmeta_preticanje: "", korak_tabela: 50.0 };

const nz = s => { try { return num(s); } catch (e) { return null; } };

function pageSight() {
  S.sightTouched = true; const P = S.pre; const c = S.cfg;
  const upd = () => { dirty(); };
  const inputs = PFIELDS.map(([k]) => field(t("k_" + k), txt(P.f[k], { inputmode: "decimal", oninput: e => { P.f[k] = e.target.value; upd(); } })));
  const o = c.optika || {}; const ov = k => String(o[k] ?? OPT_DEF[k]); const setO = (k, v) => { c.optika = c.optika || {}; c.optika[k] = v; dirty(); };
  const sel = (k, opts, lab) => { const s = h("select", { onchange: e => setO(k, e.target.value) }, opts.map(([v, l]) => h("option", { value: v }, l))); s.value = ov(k); return field(lab, s); };
  // tipovi prepreka
  const typeRows = h("tbody"); const drawTypes = () => { typeRows.replaceChildren(...P.tipovi.map((r, i) => h("tr", {}, h("td", {}, txt(r[0], { oninput: e => { r[0] = e.target.value; upd(); } })), h("td", {}, txt(r[1], { style: "width:100px", oninput: e => { r[1] = e.target.value; upd(); } })), h("td", {}, h("button", { class: "btn sm ghost", onclick: () => { P.tipovi.splice(i, 1); drawTypes(); upd(); } }, "✕"))))); };
  drawTypes();
  const defSel = txt(P.zadani, { oninput: e => { P.zadani = e.target.value; upd(); }, list: "tipl" });
  const excBody = h("tbody"); const drawExc = () => { excBody.replaceChildren(...S.exc.map((e, i) => h("tr", {}, h("td", {}, e.sekcija || "*"), h("td", {}, e.osovina || "*"), h("td", { class: "mono" }, `${e.od} – ${e.do}`), h("td", {}, e.tip || `${e.ofset} m`), h("td", {}, e.strana || "unutra"),
      h("td", {}, h("button", { class: "btn sm", onclick: async () => { const r = await excDialog(e); if (r) { S.exc[i] = r; drawExc(); upd(); } } }, t("s_edit")), " ", h("button", { class: "btn sm ghost", onclick: () => { S.exc.splice(i, 1); drawExc(); upd(); } }, "✕"))))); };
  drawExc();
  const elBox = h("div", { class: "scroll" }); const drawEl = () => elBox.replaceChildren(elTable(drawEl));
  if (!S.elrows.length) loadElems(true).then(drawEl); else drawEl();
  return h("div", { class: "wrap" },
    h("div", {}, h("h1", {}, t("g_title")), h("p", { class: "sub" }, t("g_sub"))),
    h("div", { class: "card" }, sw(t("g_on"), !!optOn("preglednost"), v => setOpt("preglednost", v)), h("p", { class: "hint", style: "margin:6px 0 0 48px" }, t("g_on_h"))),
    h("div", { class: "card" }, h("h3", {}, t("g_params")), h("div", { class: "grid g2", style: "margin-top:10px" }, inputs),
      h("div", { class: "row", style: "margin-top:14px;flex-wrap:wrap;gap:20px" }, h("span", { class: "lbl" }, t("g_sides")), sw(t("g_right"), P.sd, v => { P.sd = v; upd(); }), sw(t("g_left"), P.sl, v => { P.sl = v; upd(); })),
      h("div", { class: "row", style: "margin-top:10px;gap:24px;flex-wrap:wrap" }, sw(t("g_edges"), P.ivice, v => { P.ivice = v; upd(); }), sw(t("g_png"), P.png, v => { P.png = v; upd(); }))),
    h("div", { class: "card" }, h("h3", {}, t("g_obst")), h("p", { class: "hint" }, t("g_obst_h")),
      h("div", { class: "grid g2" }, h("div", {}, h("div", { class: "lbl", style: "margin-bottom:6px" }, t("g_types")), h("table", { class: "tb" }, h("thead", {}, h("tr", {}, h("th", {}, t("g_type_name")), h("th", {}, t("g_type_off")), h("th"))), typeRows),
          h("button", { class: "btn sm", style: "margin-top:8px", onclick: () => { P.tipovi.push(["", ""]); drawTypes(); } }, "+")
          ), h("div", {}, field(t("g_default"), defSel), h("datalist", { id: "tipl" }, P.tipovi.map(r => h("option", { value: r[0] }))))),
      h("div", { style: "margin-top:16px" }, h("h3", {}, t("g_exc")), h("p", { class: "hint" }, t("g_exc_h")),
        h("table", { class: "tb" }, h("thead", {}, h("tr", {}, [t("g_exc_sec"), t("g_exc_axis"), t("g_from") + " – " + t("g_to"), t("g_exc_obst"), t("g_exc_side"), ""].map(x => h("th", {}, x)))), excBody),
        h("button", { class: "btn sm", style: "margin-top:8px", onclick: async () => { const r = await excDialog(); if (r) { S.exc.push(r); drawExc(); upd(); } } }, "+ " + t("g_exc_add"))),
      h("div", { style: "margin-top:16px" }, h("h3", {}, t("g_elems")), h("p", { class: "hint" }, t("g_elems_h")),
        h("div", { class: "row", style: "margin-bottom:8px" }, h("button", { class: "btn sm", onclick: async () => { await loadElems(false); drawEl(); } }, t("g_load")), h("button", { class: "btn sm primary", onclick: () => editEls(drawEl) }, t("g_edit_sel")), h("button", { class: "btn sm", onclick: () => { S.sel.forEach(i => { const r = S.elrows[i]; delete S.elset[[r.sek, r.os, r.no].join("|")]; }); upd(); drawEl(); } }, t("g_clear_sel"))),
        elBox)),
    h("div", { class: "card" }, h("h3", {}, t("o_title")), h("div", { style: "margin:8px 0 12px" }, sw(t("o_on"), !!optOn("optika"), v => setOpt("optika", v))),
      h("div", { class: "grid g3" }, sel("tip_puta", [["auto", t("o_tip_a")], ["dvosmjerni", t("o_tip_d")], ["razdvojeni", t("o_tip_r")]], t("o_tip")), sel("grupa", [["A", "A"], ["B", "B"], ["C", "C"]], t("o_grupa")), sel("Pp_po", [["Vr", "Vr"], ["Vp", "Vp"]], t("o_Pp_po")),
        field(t("o_min_proc"), txt(ov("min_proc"), { oninput: e => setO("min_proc", num(e.target.value, 25)) })), field(t("o_h"), txt(o.h_predmeta_preticanje ?? "", { oninput: e => setO("h_predmeta_preticanje", num(e.target.value)) })), field(t("o_korak"), txt(ov("korak_tabela"), { oninput: e => setO("korak_tabela", num(e.target.value, 50)) })))),
    navButtons("sight", "run"));
}
async function loadElems(silent) {
  const r = await api("elements", { cfg: S.cfg }); S.elrows = r.rows || []; S.sel.clear();
  if (r.error && !silent) toast(r.error, true); if (!S.elrows.length && !silent) toast(t("g_no_elems"), true);
}
let lastClick = null;
function elTable(redraw) {
  const P = S.pre; const tv = Object.fromEntries(P.tipovi.map(r => [r[0], r[1]]));
  const rows = S.elrows.map((r, i) => {
    const u = S.elset[[r.sek, r.os, r.no].join("|")] || S.elset[[r.sek, "", r.no].join("|")]; let txtc = "";
    if (u) txtc = (u[0] ? `${u[0]} (${tv[u[0]] ?? "?"} m)` : `${u[1]} m`) + `, ${t("g_side")}: ${u[2]}`; else if (r.typ !== "PRAVAC" && P.zadani && P.zadani in tv) txtc = `(${t("g_all_curves")}: ${P.zadani}, ${tv[P.zadani]} m)`;
    return h("tr", { class: "pick" + (S.sel.has(i) ? " sel" : ""), onclick: ev => { if (ev.shiftKey && lastClick != null) { const [a, b] = [Math.min(lastClick, i), Math.max(lastClick, i)]; for (let k = a; k <= b; k++) S.sel.add(k); } else if (ev.ctrlKey || ev.metaKey) { S.sel.has(i) ? S.sel.delete(i) : S.sel.add(i); } else { S.sel.clear(); S.sel.add(i); } lastClick = i; redraw(); }, ondblclick: () => editEls(redraw) },
      h("td", {}, r.sek), h("td", {}, r.os), h("td", {}, r.no), h("td", {}, r.typ === "PRAVAC" ? (LANG === "en" ? "tangent" : "pravac") : r.typ === "KRUZNI_LUK" ? (LANG === "en" ? "circular curve" : "kružni luk") : (LANG === "en" ? "transition" : "prijelaznica")),
      h("td", { class: "mono" }, r.s0.toFixed(2)), h("td", { class: "mono" }, r.s1.toFixed(2)), h("td", { class: "mono" }, r.R == null ? "∞" : r.R.toFixed(1)), h("td", {}, txtc));
  });
  if (!rows.length) return h("div", { class: "empty", style: "border:0" }, t("g_no_elems"));
  return h("table", { class: "tb" }, h("thead", {}, h("tr", {}, [t("g_exc_sec"), t("g_exc_axis"), t("g_el"), t("g_kind"), t("g_from"), t("g_to"), "R [m]", t("g_exc_obst")].map(x => h("th", {}, x)))), h("tbody", {}, rows));
}
async function editEls(redraw) {
  if (!S.sel.size) return; const P = S.pre; const rs = [...S.sel].sort((a, b) => a - b).map(i => S.elrows[i]); const r0 = rs[0]; const cur = S.elset[[r0.sek, r0.os, r0.no].join("|")] || ["", "", "unutra"];
  const tip = h("select", {}, h("option", { value: "" }, "—"), P.tipovi.filter(r => r[0]).map(r => h("option", { value: r[0] }, r[0]))); tip.value = cur[0];
  const of = txt(cur[1], { style: "width:120px" }); const st = h("select", {}, [["unutra", "g_side_in"], ["vani", "g_side_out"], ["desno", "g_side_r"], ["lijevo", "g_side_l"]].map(([v, k]) => h("option", { value: v }, t(k)))); st.value = cur[2];
  const res = await modal({ title: rs.length === 1 ? `${t("g_el")} ${r0.no} (${r0.os}, ${t("g_exc_sec")} ${r0.sek})` : t("g_selected", rs.length), small: true, body: h("div", { class: "grid" }, field(t("g_type"), tip), field(t("g_or_off"), of), field(t("g_exc_side"), st)),
    onOk: () => { const o = (of.value || "").trim().replace(",", "."); if (o && !isFinite(Number(o))) throw new Error(t("e_num", o)); rs.forEach(r => { const k = [r.sek, r.os, r.no].join("|"); if (tip.value || o) S.elset[k] = [tip.value, o, st.value]; else delete S.elset[k]; }); return true; } });
  if (res) { dirty(); redraw(); }
}
async function excDialog(cur) {
  cur = cur || {}; const P = S.pre; const od = txt(cur.od ?? ""), dO = txt(cur.do ?? "");
  const tip = h("select", {}, h("option", { value: "" }, "—"), P.tipovi.filter(r => r[0]).map(r => h("option", { value: r[0] }, r[0]))); tip.value = cur.tip || "";
  const of = txt(cur.ofset ?? "", { style: "width:120px" }); const st = h("select", {}, [["unutra", "g_side_in"], ["vani", "g_side_out"], ["desno", "g_side_r"], ["lijevo", "g_side_l"]].map(([v, k]) => h("option", { value: v }, t(k)))); st.value = cur.strana || "unutra";
  const sek = txt(cur.sekcija ?? "", { style: "width:80px" }); const os = h("select", {}, ["", "desna", "lijeva", "centralna"].map(v => h("option", { value: v }, v || t("g_all")))); os.value = cur.osovina || "";
  return modal({ title: t("g_exc"), small: true, body: h("div", { class: "grid g2" }, field(t("d_from"), od), field(t("d_to"), dO), field(t("g_type"), tip), field(t("g_or_off"), of), field(t("g_exc_side"), st), field(t("g_exc_sec"), sek), field(t("g_exc_axis"), os)),
    onOk: () => { const a = num(od.value), b = num(dO.value); if (a == null || b == null || b <= a) throw new Error(t("e_range")); const e = { od: a, do: b, strana: st.value }; const o = num(of.value); if (tip.value) e.tip = tip.value; else if (o != null) e.ofset = o; else throw new Error(t("e_type_off")); if (sek.value.trim()) e.sekcija = parseInt(sek.value); if (os.value) e.osovina = os.value; return e; } }).then(r => (r && r !== true) ? r : null);
}

/* ================================================================ PAGE 5 – RUN */
function pageRun() {
  const o = Object.assign({ word: true, excel: true, preglednost: false, optika: false, ifc: false, dwg: false, landxml: false, koridor: false }, S.cfg.gui_opcije || {});
  const R = S.run; const cards = [["word", "r_word", "r_word_h", "DOCX"], ["excel", "r_excel", "r_excel_h", "XLSX"], ["preglednost", "r_sight", "r_sight_h", "DXF"], ["optika", "r_optika", "r_optika_h", "DOCX"], ["ifc", "r_ifc", "r_ifc_h", "IFC"], ["landxml", "r_lx", "r_lx_h", "XML"], ["koridor", "r_kor", "r_kor_h", "HTML"], ["dwg", "r_dwg", "r_dwg_h", "DWG"]];
  const grid = h("div", { class: "outs" }, cards.map(([k, a, b, ext]) => { const on = h("input", { type: "checkbox", checked: o[k], onchange: e => { setOpt(k, e.target.checked); render(); } }); return h("label", { class: "opt" + (o[k] ? " on" : ""), style: "cursor:pointer" }, h("span", { class: "sw" }, on), h("div", {}, h("b", {}, t(a)), h("small", {}, t(b)))); }));
  const secs = S.cfg.sekcije;
  const sum = h("div", { class: "row", style: "flex-wrap:wrap;gap:8px" }, h("span", { class: "chip" }, `${S.cfg.projekat || t("untitled")}`), h("span", { class: "chip" }, `Vr ${S.cfg.Vr} km/h`), h("span", { class: "chip" }, `${secs.length} ${t("nav_sections").toLowerCase()}`), h("span", { class: "chip" }, (S.cfg.jezik || LANG).toUpperCase()), h("span", { class: "chip" + (S.cfg.izlaz ? " ok" : " err") }, S.cfg.izlaz || "—"));
  const log = h("div", { class: "log", id: "logbox" }, R.lines.join("\n"));
  const btn = h("button", { class: "btn primary big", id: "runbtn", disabled: R.running, onclick: startRun }, R.running ? t("r_running") : "▶  " + t("r_run"));
  const files = R.done && R.outs.length ? h("div", { class: "card" }, h("div", { class: "row" }, h("h3", { class: "grow" }, t("r_files") + ` (${R.outs.length})`), h("button", { class: "btn sm", onclick: () => api("open", { path: R.outs[0], folder: true }) }, t("r_open_folder"))),
      h("div", { class: "files", style: "margin-top:10px" }, R.outs.filter(p => !/\.(png|pdf)$/i.test(p) || R.outs.length < 14).map(p => h("div", { class: "file" }, h("div", { class: "ic" }, (p.split(".").pop() || "").toUpperCase().slice(0, 4)), h("div", { class: "nm", title: p }, base(p)), h("button", { class: "btn sm", onclick: () => api("open", { path: p }) }, t("r_open")))))) : null;
  return h("div", { class: "wrap" }, h("div", {}, h("h1", {}, t("r_title")), h("p", { class: "sub" }, t("r_sub"))),
    h("div", { class: "card" }, sum), h("div", { class: "card" }, grid), o.koridor ? korCard() : null,
    h("div", { class: "row" }, btn, R.running ? h("div", { class: "prog grow" }, h("i")) : R.done ? h("span", { class: "chip " + (R.error ? "err" : "ok") }, R.error ? t("r_fail") : "✓ " + t("r_done")) : null),
    R.errs && R.errs.length ? h("div", { class: "alert err" }, h("b", {}, t("r_errors")), h("ul", { style: "margin:6px 0 0 18px;padding:0" }, R.errs.map(e => h("li", {}, e)))) : null,
    h("div", { class: "card" }, h("h3", {}, t("r_log")), log), files, navButtons("sight", null));
}
function korCard() {
  const k = S.cfg.koridor = Object.assign({ datoteka: "", od: "", do: "", ograda_ofset: 0.78, uskladi: true }, S.cfg.koridor || {});
  const f = txt(k.datoteka || "", { class: "mono", oninput: e => { k.datoteka = e.target.value; dirty(); } });
  const nIn = (key, w) => txt(String(k[key]), { style: "width:" + w + "px", inputmode: "decimal", placeholder: "auto", oninput: e => { const v = nz(e.target.value); if (e.target.value.trim() === "") { k[key] = ""; dirty(); } else if (v != null) { k[key] = v; dirty(); } } });
  return h("div", { class: "card" }, h("h3", {}, t("r_kor")), h("p", { class: "hint" }, t("k_h")),
    h("div", { class: "grid g2" }, field(t("k_file"), h("div", { class: "row" }, h("div", { class: "grow" }, f), h("button", { class: "btn sm", onclick: () => pathField(f, "open", t("k_file"), [["LandXML", "*.xml"], [t("flt_all"), "*.*"]]) }, t("k_pick")))),
      field(t("k_from"), nIn("od", 120)), field(t("k_to"), nIn("do", 120)), field(t("k_off"), nIn("ograda_ofset", 120))),
    sw(t("k_rails"), !!k.uskladi, v => { k.uskladi = v; dirty(); }));
}
async function startRun() {
  try { await startRun_(); } catch (e) { const R = S.run; R.running = false; R.errs = [String(e && e.message || e)]; toast(R.errs[0], true); render(); }
}
async function startRun_() {
  collectPage(); const R = S.run; R.errs = [];
  try { syncSight(); } catch (e) { R.errs = [e.message]; return render(); }
  const o = Object.assign({ word: true, excel: true, preglednost: false, optika: false }, S.cfg.gui_opcije || {});
  if (!S.cfg.izlaz) { R.errs = [t("r_noout")]; return render(); }
  if (o.koridor && !(S.cfg.koridor && S.cfg.koridor.datoteka)) { R.errs = [t("e_kor")]; return render(); }
  if (!o.word && !o.excel && !o.preglednost && !o.optika && !o.ifc && !o.dwg && !o.landxml && !o.koridor) { R.errs = [t("r_nothing")]; return render(); }
  const cfg = buildCfg(); cfg.jezik = cfg.jezik || LANG;
  const v = await api("validate", { cfg, lang: LANG }); if (v.errors && v.errors.length) { R.errs = v.errors; return render(); }
  Object.assign(R, { running: true, done: false, lines: [], outs: [], error: null });
  const r = await api("run", { cfg, options: o }); if (r.error) { R.running = false; R.errs = [r.error]; return render(); }
  render(); let since = 0;
  const tick = async () => {
    let j; try { j = await api("log", { since }); } catch (e) { setTimeout(tick, 1500); return; } since = j.next; if (j.lines.length) { R.lines.push(...j.lines); const lb = $("#logbox"); if (lb) { lb.textContent = R.lines.join("\n"); lb.scrollTop = lb.scrollHeight; } }
    if (j.done) { R.running = false; R.done = true; R.outs = j.outs; R.error = j.error; if (S.page === "run") render(); return; }
    setTimeout(tick, 500);
  };
  tick();
}

const PAGE_FN = { project: pageProject, sections: pageSections, params: pageParams, sight: pageSight, run: pageRun };
// buildCfg uključuje sinhronizaciju prepreka
const _buildCfg = buildCfg; buildCfg = function () { try { syncSight(); } catch (e) { if (S.page === "sight") toast(e.message, true); } return _buildCfg(); };

/* ================================================================ init */
function applyTheme(th) { document.documentElement.dataset.theme = th; $("#themebtn").textContent = th === "dark" ? "☀" : "☾"; S.ui.theme = th; api("ui", { theme: th }); }
function setLang(l) { collectPage(); LANG = l; refreshState(); document.documentElement.lang = l; S.ui.lang = l; api("ui", { lang: l }); render(); }
async function init() {
  const st = await api("state"); S.lic = st.license; S.defaults = st.defaults; S.version = st.version; S.ui = st.ui || {};
  LANG = S.ui.lang || ((navigator.language || "").toLowerCase().startsWith("en") ? "en" : "sr"); document.documentElement.lang = LANG;
  const th = S.ui.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"); document.documentElement.dataset.theme = th; $("#themebtn").textContent = th === "dark" ? "☀" : "☾";
  $("#themebtn").addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
  document.querySelectorAll("#langseg button").forEach(b => b.addEventListener("click", () => setLang(b.dataset.l)));
  loadSightState(); refreshState(); render(); setInterval(() => api("ping").catch(() => { }), 4000); api("ping");
  window.addEventListener("beforeunload", e => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });
  document.addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveProject(false); } });
  if (!S.lic.ok) setTimeout(licenseDialog, 300);
  else if (st.last && !new URLSearchParams(location.search).has("nolast")) setTimeout(async () => { if (await confirmBox(t("last_q") + "\n" + st.last)) loadProject(st.last); }, 500);
}
init();
