@echo off
cd /d "%~dp0"
set "PY="
where py >nul 2>nul
if %errorlevel%==0 set "PY=py -3"
if not defined PY set "PY=python"
if exist .venv rmdir /s /q .venv
%PY% -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
