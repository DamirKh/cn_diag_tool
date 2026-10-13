#requires -Version 5.1
# Build the Windows one-dir bundle (PyInstaller) and the Inno Setup installer.
# Usage:  .\build_win.ps1
# Requires: Python 3.12 in PATH and Inno Setup 6 installed.

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

Write-Host '== ControlNet Diagnostic Tool: Windows build =='

# --- version from the nearest tag, with ver.py as fallback ---
$ver = $null
try {
    $desc = (git describe --tags --always --dirty 2>$null)
    if ($desc -match '^v?([0-9]+\.[0-9]+)') { $ver = $Matches[1] }
} catch { }
if (-not $ver -and (Test-Path 'ver.py')) {
    $maj = (Select-String -Path 'ver.py' -Pattern '^major\s*=\s*(\d+)' | Select-Object -First 1)
    $min = (Select-String -Path 'ver.py' -Pattern '^minor\s*=\s*(\d+)' | Select-Object -First 1)
    if ($maj -and $min) { $ver = "$($maj.Matches[0].Groups[1].Value).$($min.Matches[0].Groups[1].Value)" }
}
if (-not $ver) { $ver = '0.0' }
$verFile = if ($ver -match '^\d+\.\d+$') { "$ver.0" } else { $ver }
Write-Host "Version: $ver (file version: $verFile)"

# --- venv + deps ---
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'python not found in PATH' }
if (-not (Test-Path '.venv-build')) { python -m venv .venv-build }
$vpy = Join-Path $PWD '.venv-build\Scripts\python.exe'
if (-not (Test-Path $vpy)) { $vpy = Join-Path $PWD '.venv-build\bin\python' }
& $vpy -m pip install --upgrade pip
& $vpy -m pip install -r requirements.txt -r requirements-build.txt

# --- PyInstaller (one-dir: dist\cn_tool\) ---
& $vpy -m PyInstaller --noconfirm --clean cn_diag_tool.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }

# --- Inno Setup ---
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $iscc) {
    $iscc = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) { throw 'ISCC.exe not found. Install Inno Setup 6 (https://jrsoftware.org/isinfo.php).' }
Write-Host "Using ISCC: $iscc"
& $iscc "/DMyAppVersion=$ver" "/DMyAppVerFile=$verFile" 'installer\cn_tool.iss'
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }

Write-Host "Done: installer\Output\cn_tool-$ver-setup.exe"
