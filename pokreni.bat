@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
where py >nul 2>nul
if %errorlevel%==0 set "PY=py -3"
if not defined PY (
  where python >nul 2>nul
  if %errorlevel%==0 set "PY=python"
)
if not defined PY goto nopython
if not exist ".venv\Scripts\python.exe" goto make
".venv\Scripts\python.exe" -c "import numpy, matplotlib, openpyxl, docx, cryptography" >nul 2>nul
if not errorlevel 1 goto run
echo Okruzenje .venv je nepotpuno ili kopirano sa drugog mjesta - pravim ga ponovo ...
rmdir /s /q .venv
:make
echo Priprema okruzenja (potreban internet, traje 1-3 minute) ...
%PY% -m venv .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
:run
".venv\Scripts\python.exe" -m una
if errorlevel 1 pause
exit /b
:nopython
echo Python nije instaliran. Skinite ga sa https://www.python.org/downloads/ (Windows installer;
echo obavezno ukljucite "Add python.exe to PATH" i ostavite ukljucen "tcl/tk and IDLE"), pa ponovo pokrenite ovaj fajl.
start https://www.python.org/downloads/
pause
exit /b
:fail
echo Greska pri pripremi okruzenja. Provjerite internet vezu i pokusajte ponovo (obrisite folder .venv ako postoji).
pause
