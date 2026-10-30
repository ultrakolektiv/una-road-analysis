"""Izvorni (nativni) dijalozi za odabir datoteka/foldera. Windows: PowerShell + WinForms; Linux/macOS: zenity / tkinter ako postoji."""
import os, subprocess, sys, shutil, json

_PS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form -Property @{TopMost = $true; ShowInTaskbar = $false; Opacity = 0; StartPosition = 'CenterScreen'}
$owner.Show(); $owner.Activate()
$mode = $env:UNA_MODE; $title = $env:UNA_TITLE; $flt = $env:UNA_FILTER; $init = $env:UNA_INIT; $name = $env:UNA_NAME
if ($mode -eq 'folder') {
  $d = New-Object System.Windows.Forms.FolderBrowserDialog
  $d.Description = $title; $d.ShowNewFolderButton = $true
  if ($init -and (Test-Path $init)) { $d.SelectedPath = $init }
  if ($d.ShowDialog($owner) -eq 'OK') { Write-Output $d.SelectedPath }
} elseif ($mode -eq 'save') {
  $d = New-Object System.Windows.Forms.SaveFileDialog
  $d.Title = $title; if ($flt) { $d.Filter = $flt }; $d.FileName = $name; $d.OverwritePrompt = $true
  if ($init -and (Test-Path $init)) { $d.InitialDirectory = $init }
  if ($d.ShowDialog($owner) -eq 'OK') { Write-Output $d.FileName }
} else {
  $d = New-Object System.Windows.Forms.OpenFileDialog
  $d.Title = $title; if ($flt) { $d.Filter = $flt }; $d.Multiselect = ($env:UNA_MULTI -eq '1')
  if ($init -and (Test-Path $init)) { $d.InitialDirectory = $init }
  if ($d.ShowDialog($owner) -eq 'OK') { $d.FileNames | ForEach-Object { Write-Output $_ } }
}
$owner.Close()
"""


def _flt_win(filters):
    """[("Projekat", "*.json"), ...] → 'Projekat|*.json|Sve|*.*'"""
    return "|".join(f"{n}|{p}" for n, p in (filters or [])) or "All|*.*"


def pick(mode="open", title="", filters=None, multiple=False, initial="", name=""):
    """Vraća listu odabranih putanja ([] = otkazano). Baca RuntimeError ako dijalog nije dostupan."""
    stub = os.environ.get("UNA_PICK_STUB")          # testovi: JSON lista odgovora (svaki odgovor = lista putanja)
    if stub:
        q = json.load(open(stub)); r = q.pop(0) if q else []; json.dump(q, open(stub, "w")); return r
    initial = initial if initial and os.path.isdir(initial) else (os.path.dirname(initial) if initial and os.path.isdir(os.path.dirname(initial)) else "")
    if os.name == "nt":
        err = ""
        try:
            env = dict(os.environ, UNA_MODE=mode, UNA_TITLE=title, UNA_FILTER=_flt_win(filters), UNA_INIT=initial, UNA_NAME=name, UNA_MULTI="1" if multiple else "0")
            ps = shutil.which("powershell") or "powershell"
            r = subprocess.run([ps, "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass", "-Command", _PS], env=env, capture_output=True, text=True, encoding="utf-8",
                               creationflags=0x08000000, timeout=1800)
            if r.returncode == 0: return [x.strip() for x in r.stdout.splitlines() if x.strip()]
            err = r.stderr.strip() or "PowerShell dialog failed"
        except Exception as e:
            err = str(e)
        try:                                                  # rezerva: tkinter (uključen u pakovanu aplikaciju)
            return _tk(mode, title, filters, multiple, name)
        except Exception as e2:
            raise RuntimeError("PowerShell: " + err[:300] + " | tkinter: " + str(e2)[:200])
    z = shutil.which("zenity")
    if z:
        cmd = [z, "--file-selection", "--title=" + title]
        if mode == "folder": cmd.append("--directory")
        if mode == "save": cmd += ["--save", "--confirm-overwrite"]
        if multiple: cmd += ["--multiple", "--separator=\n"]
        for n, p in (filters or []): cmd.append(f"--file-filter={n} | {p.replace(';', ' ')}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        return [x for x in r.stdout.splitlines() if x]
    try:
        return _tk(mode, title, filters, multiple, name)
    except Exception as e:
        raise RuntimeError("no-native-dialog: " + str(e))


def _tk(mode, title, filters, multiple, name):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    ft = [(n, p.replace(";", " ")) for n, p in (filters or [])] or [("All", "*.*")]
    try:
        if mode == "folder": r = filedialog.askdirectory(title=title, parent=root)
        elif mode == "save": r = filedialog.asksaveasfilename(title=title, filetypes=ft, initialfile=name, parent=root)
        elif multiple: r = list(filedialog.askopenfilenames(title=title, filetypes=ft, parent=root))
        else: r = filedialog.askopenfilename(title=title, filetypes=ft, parent=root)
    finally:
        root.destroy()
    return [r] if isinstance(r, str) and r else list(r or [])
