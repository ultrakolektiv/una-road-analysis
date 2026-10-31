# Gradi UNA_Setup.exe (Windows, PowerShell). Koristi ga GitHub Actions; može i lokalno:  powershell -ExecutionPolicy Bypass -File build\build_ci.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$ver = (Get-Content VERSION -Raw).Trim()
Write-Host "UNA verzija $ver"
Set-Content -Path una\_version.py -Value "VERSION = `"$ver`"" -Encoding UTF8

# 1) javni ključ za licence mora biti upisan (izdavac.py init)
if (Select-String -Path una\_pubkey.py -Pattern 'PUBLIC_KEY_B64 = ""' -Quiet) { throw "Javni ključ nije upisan u una\_pubkey.py (pokrenite izdavac.py init i commit-ujte rezultat)." }

# 2) pandoc
$pd = "build\vendor\pandoc"
if (-not (Test-Path "$pd\pandoc.exe")) {
  $pv = "3.1.11.1"; $zip = "$env:TEMP\pandoc.zip"
  Invoke-WebRequest "https://github.com/jgm/pandoc/releases/download/$pv/pandoc-$pv-windows-x86_64.zip" -OutFile $zip
  Expand-Archive $zip -DestinationPath "$env:TEMP\pandoc_x" -Force
  $src = Get-ChildItem "$env:TEMP\pandoc_x" -Directory | Select-Object -First 1
  New-Item -ItemType Directory -Force $pd | Out-Null
  Copy-Item "$($src.FullName)\pandoc.exe" $pd -Force
  if (Test-Path "$($src.FullName)\COPYING.txt") { Copy-Item "$($src.FullName)\COPYING.txt" $pd -Force }
}

# 3) Python paketi i Nuitka
python -m pip install --upgrade pip
pip install -r requirements.txt nuitka ordered-set zstandard
$fv = ($ver + ".0")
if (Test-Path dist) { Remove-Item dist -Recurse -Force }
python -m nuitka --standalone --assume-yes-for-downloads --msvc=latest `
  --enable-plugin=tk-inter --windows-console-mode=disable `
  --include-package=una --include-data-dir=una\data=una\data --include-data-dir=una\webui\static=una\webui\static --include-package=docx --include-package-data=docx `
  --nofollow-import-to=pytest,IPython,scipy.tests,numpy.tests `
  --product-name="UNA - ROAD ENGINEERING ANALYSIS" --company-name="VAŠA FIRMA" --product-version=$fv --file-version=$fv `
  --windows-icon-from-ico=build\assets\una.ico --output-dir=dist --output-filename=UNA.exe UNA.py
if ($LASTEXITCODE -ne 0) { throw "Nuitka build nije uspio" }

Copy-Item $pd dist\UNA.dist\pandoc -Recurse -Force
Copy-Item build\EULA.txt dist\UNA.dist\ -Force
if (Test-Path build\TRECE_STRANE.txt) { Copy-Item build\TRECE_STRANE.txt dist\UNA.dist\ -Force }

# 4) instalater
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { $iscc = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe" }
& $iscc "/DAppVer=$ver" build\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup nije uspio" }
Write-Host "Gotovo: dist\UNA_Setup.exe"
