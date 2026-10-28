@echo off
rem Rezervna varijanta (brža za pravljenje, slabija zaštita koda): PyInstaller, onedir.
setlocal
cd /d "%~dp0\.."
if not exist build\vendor\pandoc\pandoc.exe ( echo FALI build\vendor\pandoc\pandoc.exe & exit /b 1 )
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt pyinstaller
if exist dist rmdir /s /q dist
pyinstaller --noconfirm --windowed --name UNA --distpath dist --collect-all docx --collect-all openpyxl ^
  --add-data "una\data;una\data" --hidden-import una.gui --hidden-import una.template_export UNA.py
rem PyInstaller pravi dist\UNA ; Inno skripta očekuje dist\UNA.dist
if exist dist\UNA.dist rmdir /s /q dist\UNA.dist
ren dist\UNA UNA.dist
xcopy /E /I /Y build\vendor\pandoc dist\UNA.dist\pandoc >nul
copy /Y build\EULA.txt dist\UNA.dist\ >nul
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" build\installer.iss
echo Gotovo: dist\UNA_Setup.exe
