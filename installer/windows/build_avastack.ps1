# build_avastack.ps1 - compilation de l'installateur AVAStack (Inno Setup 6)
#
# Lit AVASTACK_VERSION dans avastack/__init__.py (source unique de verite)
# et la passe a ISCC via /DAppVersion=... : le numero de version embarque
# dans l'installateur suit automatiquement le source, sans etre fige dans
# avastack.iss.
#
# Usage (depuis n'importe ou) :
#   powershell -NoProfile -ExecutionPolicy Bypass -File build_avastack.ps1
# NB : script volontairement sans caracteres accentues (encodage PS 5.1).

$ErrorActionPreference = 'Stop'

# --- Inno Setup 6 : premier chemin existant parmi les candidats -------------
$Iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    Write-Host "ERREUR : Inno Setup 6 introuvable - installez-le depuis" -ForegroundColor Red
    Write-Host "https://jrsoftware.org/isdl.php puis relancez ce script." -ForegroundColor Red
    exit 1
}

# --- Version : AVASTACK_VERSION dans avastack/__init__.py (racine du depot) --
$Root    = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$InitPy  = Join-Path $Root 'avastack\__init__.py'
$Corresp = Select-String -Path $InitPy -Pattern '^AVASTACK_VERSION\s*=\s*"([^"]+)"'
if (-not $Corresp) {
    Write-Host "ERREUR : AVASTACK_VERSION introuvable dans $InitPy" -ForegroundColor Red
    exit 1
}
$Version = $Corresp.Matches[0].Groups[1].Value
Write-Host "Version lue : AVASTACK_VERSION = $Version"
Write-Host "Compilateur : $Iscc"

# --- Compilation --------------------------------------------------------------
Push-Location $PSScriptRoot
try {
    & $Iscc "/DAppVersion=$Version" ".\avastack.iss"
    $Code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($Code -ne 0) {
    Write-Host "ERREUR : ISCC a echoue (code retour $Code)." -ForegroundColor Red
    exit $Code
}
Write-Host ""
Write-Host "OK - artefact : $PSScriptRoot\output\avastack-setup.exe" -ForegroundColor Green
exit 0
