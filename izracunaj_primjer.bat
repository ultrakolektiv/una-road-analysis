@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call pokreni_priprema.bat
".venv\Scripts\python.exe" -m una primjer\primjer_projekat.json
echo.
echo Rezultat je u folderu primjer\izlaz_primjer
pause
