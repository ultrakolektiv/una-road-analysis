IZGRADNJA INSTALATERA (radi se na Windowsu, jednom po verziji)
==============================================================
A. JEDNOKRATNA PRIPREMA
 1. Instalirajte: Python 3.12 (64-bit, sa tcl/tk), Inno Setup 6 (jrsoftware.org), a za Nuitku C kompajler
    (Visual Studio Build Tools "Desktop development with C++" – ili pustite Nuitku da sam preuzme MinGW64 kad pita).
 2. Skinite Pandoc (pandoc.org/installing) – "windows-x86_64.zip". Iz zip-a kopirajte pandoc.exe i COPYING.txt u
    build\vendor\pandoc\
 3. Napravite VLASTITI PAR KLJUČEVA (privatni ključ ostaje samo kod Vas):
      cd Izdavac_licenci
      python -m pip install cryptography
      python izdavac.py init
    Ovo upisuje javni ključ u UNA_aplikacija\una\_pubkey.py. private.key NE KOPIRAJTE u paket – napravite backup
    na dva sigurna mjesta (npr. šifrovani USB + password manager). Bez njega ne možete izdavati nove licence.
 4. U build\installer.iss, build_nuitka.bat i EULA.txt zamijenite "VAŠA FIRMA" i dopunite EULA uz pomoć pravnika.

B. PRAVLJENJE INSTALATERA
      build\build_nuitka.bat          (zaštićenija varijanta: kod se prevodi u C/mašinski kod; prvi build traje 10–30 min)
   ili build\build_pyinstaller.bat    (rezervna, brža; slabija zaštita koda)
   Rezultat: dist\UNA_Setup.exe  – to dajete kupcima.
   PRVI BUILD OBAVEZNO TESTIRAJTE na čistom računaru/VM bez Pythona: instalacija, aktivacija licence, "Izračunaj primjer"
   (primjer\primjer_projekat.json) i Word/Excel izlaz. Ako Nuitka javi da nešto fali (npr. matplotlib font/data), dodajte
   odgovarajući --include-package-data / --include-data-dir parametar.
   Preporuka: potpišite Setup.exe i UNA.exe kodnim certifikatom (Authenticode), inače Windows SmartScreen/antivirus
   često upozoravaju na nepotpisane programe.

C. IZDAVANJE LICENCI
 1. Kupac pokrene program → prozor "Aktivacija licence" prikaže ID računara (ili: UNA.exe --id) → pošalje Vam ga.
 2. Vi:  python izdavac.py issue --kupac "Firma d.o.o." --email kupac@firma.ba --racunar XXXX-XXXX-XXXX-XXXX --do 2027-12-31
    → nastaje licenca_Lyymmdd-XXXXXX.lic; pošaljete je kupcu. U programu UNA: "Učitaj licencu (.lic)…". (evidencija: izdate_licence.csv)
 3. Probna verzija: --racunar * --do <za 14 dana>   (radi na bilo kom računaru dok ne istekne).
 4. Produženje: izdajte novu .lic sa novim rokom. Prijenos na novi računar: nova licenca za novi ID.

D. ŠTA JE ZAŠTIĆENO, A ŠTA NIJE (iskreno)
 + Licenca je potpisana (Ed25519): kupac ne može sam napraviti ni izmijeniti licencu; vezana za računar i rok.
 + Nuitka onemogućava običan "dekompajl" nazad u Python kod. 
 + U svojstvima svakog Word/Excel izlaza je ID licence → ako kopija procuri, znate čija je licenca.
 - Odlučan napadač sa alatima za reverse engineering može zaobići provjeru u izvršnom fajlu. Pravna zaštita (EULA) i
   odnos s kupcima ostaju bitan dio zaštite. Ne stavljajte u program ništa što ne smije biti vidljivo (tajne, lozinke).
 - Provjera sata je osnovna (ne štiti od odlučnog vraćanja vremena).
