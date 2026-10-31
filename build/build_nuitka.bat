@echo off
rem ============================================================
rem  Pravi UNA kao pravi Windows program (bez Pythona kod korisnika)
rem  Preduslovi (jednom): Python 3.11/3.12 64-bit, Visual Studio Build Tools (C++) ILI dozvolite Nuitki da preuzme MinGW,
rem                       Inno Setup 6, i pandoc.exe u build\vendor\pandoc\ (vidi README_BUILD.txt)
rem ============================================================
setlocal
cd /d "%~dp0\.."
if not exist build\vendor\pandoc\pandoc.exe ( echo FALI build\vendor\pandoc\pandoc.exe - vidi README_BUILD.txt & exit /b 1 )
findstr /C:"PUBLIC_KEY_B64 = \"\"" una\_pubkey.py >nul && ( echo Javni kljuc nije upisan - prvo pokrenite izdavac.py init & exit /b 1 )
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt nuitka ordered-set zstandard
if exist dist rmdir /s /q dist
python -m nuitka --standalone --assume-yes-for-downloads ^
  --enable-plugin=tk-inter ^
  --windows-console-mode=disable --windows-icon-from-ico=build\assets\una.ico ^
  --include-package=una --include-data-dir=una\data=una\data ^
  --include-package=docx --include-package-data=docx ^
  --nofollow-import-to=pytest,IPython,scipy.tests,numpy.tests ^
  --product-name="UNA - ROAD ENGINEERING ANALYSIS" --company-name="VAŠA FIRMA" --product-version=1.0.0.0 --file-version=1.0.0.0 ^
  --output-dir=dist --output-filename=UNA.exe UNA.py
if errorlevel 1 ( echo Nuitka build nije uspio & exit /b 1 )
xcopy /E /I /Y build\vendor\pandoc dist\UNA.dist\pandoc >nul
copy /Y build\EULA.txt dist\UNA.dist\ >nul
copy /Y build\TRECE_STRANE.txt dist\UNA.dist\ >nul 2>nul
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" build\installer.iss
echo.
echo Gotovo: dist\UNA_Setup.exe
