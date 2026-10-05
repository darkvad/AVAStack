# build_avastack_frozen.ps1 - paquet AVAStack GELE (PyInstaller) pour Windows
#
# POURQUOI CE PAQUET (chantier « Microsoft Store », jalon 91, 02/10/2026) : la
# voie Store exige un MSIX, et un MSIX est IMMUABLE (fichiers en lecture seule) :
# le venv ne peut plus etre cree a l'installation -> l'application doit etre
# GELEE au prealable. Ce script produit ce gel.
#
# Il lit AVASTACK_VERSION dans avastack/__init__.py (source unique de verite) et
# le nom de l'artefact PORTE la version, comme les autres packers.
#
# LES 4 DLL CONSTRUCTEURS SONT EMBARQUEES (decision d'Alain, 02/10/2026 : on les
# garde dans TOUS les installateurs ; la certification 10.2.4 ne vise que les
# PILOTES noyau, pas les DLL utilisateur). Elles sont ajoutees par NOM (liste
# explicite, jamais un joker) a la racine du bundle, la ou sdk_loader les
# cherche DEJA (mesure du jalon 90 : RACINE_PROJET == sys._MEIPASS).
# Une DLL absente de la machine de build est ANNONCEE, jamais inventee.
#
# Usage (depuis n'importe ou) :
#   powershell -NoProfile -ExecutionPolicy Bypass -File build_avastack_frozen.ps1
# Prerequis : PyInstaller >= 6.16 dans le venv de build (Python 3.14).
# NB : script volontairement sans caracteres accentues (encodage PS 5.1).

$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

# --- Python portant PyInstaller ---------------------------------------------
$Candidats = @((Join-Path $Root 'venv\Scripts\python.exe'), 'python')
$Python = $null
foreach ($c in $Candidats) {
    try {
        & $c -c "import PyInstaller" 2>$null
        if ($LASTEXITCODE -eq 0) { $Python = $c; break }
    } catch { }
}
if (-not $Python) {
    Write-Host "ERREUR : PyInstaller introuvable." -ForegroundColor Red
    Write-Host "  Installez-le dans le venv de build :" -ForegroundColor Red
    Write-Host "  & '$Root\venv\Scripts\python.exe' -m pip install 'pyinstaller>=6.16'" -ForegroundColor Red
    exit 1
}

# --- Version : AVASTACK_VERSION dans avastack/__init__.py -------------------
$InitPy = Join-Path $Root 'avastack\__init__.py'
$Corresp = Select-String -Path $InitPy -Pattern '^AVASTACK_VERSION\s*=\s*"([^"]+)"'
if (-not $Corresp) {
    Write-Host "ERREUR : AVASTACK_VERSION introuvable dans $InitPy" -ForegroundColor Red
    exit 1
}
$Version = $Corresp.Matches[0].Groups[1].Value

$Sortie  = Join-Path $PSScriptRoot 'output'
$Paquet  = Join-Path $Sortie ("avastack-frozen-$Version-windows")
$Archive = Join-Path $Sortie ("avastack-frozen-$Version-windows.zip")
$Travail = Join-Path $Sortie 'build_frozen'
New-Item -ItemType Directory -Force -Path $Sortie | Out-Null

# SDK binaires constructeurs : LISTE NOMMEE, recopiee d'avastack.iss
$Dlls = @('ASICamera2.dll', 'PlayerOneCamera.dll', 'ToupCam.dll', 'SVBCameraSDK.dll')

Write-Host "Version lue : AVASTACK_VERSION = $Version"
Write-Host "Python      : $Python"

# --- PyInstaller -------------------------------------------------------------
$PyArgs = @(
    '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
    '--name', 'AVAStack',
    '--paths', $Root,
    '--distpath', $Sortie,
    '--workpath', $Travail,
    '--specpath', $Travail,
    (Join-Path $Root 'AVAStack.py')
)
# Icone de l'application (barre des taches / Explorateur) + ressources : le
# .ico choisit l'icone de l'EXE ; assets\ est EMBARQUE pour que le code pose
# aussi l'icone de la FENETRE au demarrage (avastack/ressources.py).
$Icone = Join-Path $Root 'assets\avastack.ico'
$DossierAssets = Join-Path $Root 'assets'
if (Test-Path $Icone) { $PyArgs += @('--icon', $Icone) }
if (Test-Path $DossierAssets) { $PyArgs += @('--add-data', "$DossierAssets;assets") }
# Catalogue d'objets celebres EMBARQUE (v2.56.0) : telecharger_catalogue_celebres
# le copie depuis le paquet gele vers le dossier des catalogues.
$CatData = Join-Path $Root 'avastack\catalogues\data\celebres_healpix8.dat.bz2'
if (Test-Path $CatData) {
    $PyArgs += @('--add-data', "$CatData;avastack/catalogues/data")
}
$Embarquees = @()
$Manquantes = @()
foreach ($d in $Dlls) {
    $p = Join-Path $Root $d
    if (Test-Path $p) {
        $PyArgs += @('--add-binary', "$p;.")
        $Embarquees += $d
    } else {
        $Manquantes += $d
    }
}
Write-Host ("SDK cameras embarques : " + $(if ($Embarquees) { $Embarquees -join ', ' } else { 'AUCUN' }))

if (Test-Path $Paquet) { Remove-Item -Recurse -Force $Paquet }

Push-Location $PSScriptRoot
try {
    & $Python @PyArgs
    $Code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($Code -ne 0) {
    Write-Host "ERREUR : PyInstaller a echoue (code retour $Code)." -ForegroundColor Red
    exit $Code
}

# --- Mise a l'ecart du dossier produit sous le nom QUI PORTE LA VERSION ------
if (Test-Path $Paquet) { Remove-Item -Recurse -Force $Paquet }
Move-Item -LiteralPath (Join-Path $Sortie 'AVAStack') -Destination $Paquet

if ($Manquantes) {
    Write-Host ""
    Write-Host "SDK cameras ABSENTS de la machine de build (non embarques) :" -ForegroundColor Yellow
    foreach ($nom in $Manquantes) { Write-Host "    - $nom" -ForegroundColor Yellow }
    Write-Host "  -> ces cameras seront ABSENTES du paquet (detectees absentes a" -ForegroundColor Yellow
    Write-Host "     l'ouverture d'une source camera). Placez la DLL a la racine du" -ForegroundColor Yellow
    Write-Host "     depot puis relancez pour un paquet complet." -ForegroundColor Yellow
}

# --- Archive transferable + empreinte ---------------------------------------
if (Test-Path $Archive) { Remove-Item -Force $Archive }
Compress-Archive -Path $Paquet -DestinationPath $Archive -CompressionLevel Optimal
$Empreinte = (Get-FileHash -Algorithm SHA256 -Path $Archive).Hash
$TailleMo = [math]::Round((Get-Item $Archive).Length / 1MB, 1)
$DossierMo = [math]::Round(((Get-ChildItem -Recurse $Paquet | Measure-Object -Property Length -Sum).Sum) / 1MB, 1)

Write-Host ""
Write-Host "OK - paquet   : $Paquet" -ForegroundColor Green
Write-Host ("     taille    : {0} Mo (dossier)" -f $DossierMo)
Write-Host "OK - archive  : $Archive" -ForegroundColor Green
Write-Host ("     taille    : {0} Mo" -f $TailleMo)
Write-Host ("     SHA-256   : {0}" -f $Empreinte)
Write-Host ""
Write-Host "Essai : double-cliquer sur"
Write-Host "  $Paquet\AVAStack.exe"
exit 0
