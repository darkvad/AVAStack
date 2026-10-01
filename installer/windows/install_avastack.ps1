# install_avastack.ps1 - installateur WINDOWS "paquet ZIP" pour AVAStack.
#
# POURQUOI CE SCRIPT EXISTE (constat reel du 01/10/2026) : l'installateur
# avastack-setup-<version>.exe (Inno Setup) est un EXECUTABLE NON SIGNE. Sur un
# Windows 11 neuf, le Controle intelligent des applications (Smart App Control)
# bloque l'execution d'un fichier temporaire d'Inno Setup et l'installation
# s'arrete sur :
#     "Impossible d'executer un fichier depuis le dossier temporaire.
#      Abandon de l'installation. Erreur 4551 : une strategie de controle
#      d'application a bloque ce fichier."
# Ce paquet-ci ne contient AUCUN executable a nous : l'installation se fait par
# CE script (lance par le double-clic sur installer\install_avastack.bat).
#
# REGLE DU PYTHON (consigne d'Alain, 01/10/2026) : ce script n'utilise JAMAIS le
# Python du Microsoft Store, MEME s'il est present. Deux raisons mesurees :
#   1. avec ce Python, la creation d'un venv avec pip echoue de facon connue :
#      a cause de la REDIRECTION DE CHEMINS, le venv atterrit dans
#      %LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.xx_...\LocalCache\
#      et pip ne trouve plus pyvenv.cfg -> code retour 1 (echec "Creation du venv
#      AVAStack" deja vu sur le poste d'un testeur en v2.45.0) ;
#   2. il est aussi deja arrive que "python3" designe ce Python hors venv
#      (piege consigne dans CLAUDE.md).
# Donc : le script CHERCHE un Python de python.org (>= 3.10, AVEC Tkinter) ; s'il
# n'en trouve pas, il TELECHARGE ET INSTALLE Python depuis python.org.
#
# Il fait ensuite, exactement comme l'installateur Inno Setup : copie de
# l'application dans %LOCALAPPDATA%\AVAStack, copie des SDK cameras presents,
# creation du venv + dependances, lanceur lancer_avastack.bat, raccourcis
# Bureau + Menu Demarrer, puis un TEST DE DEMARRAGE REEL (import de
# avastack.ui.app dans le venv, aucune fenetre) qui AFFICHE l'erreur exacte.
#
# Usage (terminal, ou par install_avastack.bat pour le double-clic) :
#   powershell -NoProfile -ExecutionPolicy Bypass -File install_avastack.ps1
#   ... -Prefix D:\AVAStack        dossier d'installation
#   ... -Python C:\Python312\python.exe   imposer un interpreteur precis
#   ... -SansRaccourci             n'ecrit ni raccourci Bureau ni Menu Demarrer
#   ... -Simulation                montre ce qui serait fait, NE TOUCHE A RIEN
#   ... -Forcer                    passe outre un garde-fou (Tkinter absent,
#                                  desinstallation sans VERSION.txt)
#   ... -Desinstaller [-Purge]     desinstalle (GARDE les reglages, sauf -Purge)
#   ... -Aide                      affiche l'aide
#
# NB : script volontairement sans caracteres accentues (encodage PS 5.1), meme
# regle que build_avastack.ps1.

[CmdletBinding()]
param(
    [string] $Prefix = (Join-Path $env:LOCALAPPDATA 'AVAStack'),
    [string] $Python = '',
    [switch] $SansRaccourci,
    [switch] $Forcer,
    [switch] $Purge,
    [switch] $Desinstaller,
    [switch] $Simulation,
    [switch] $Aide
)

$ErrorActionPreference = 'Stop'

$NOM_APP = 'AVAStack'
$VERSION_MIN_MAJEUR = 3
$VERSION_MIN_MINEUR = 10
# Python de python.org installe par ce script si aucun Python utilisable n'est
# trouve. MEME version et meme adresse que l'installateur Inno Setup
# (avastack.iss : PythonInstallerUrl) - un banc verifie que les deux fichiers
# s'accordent, pour que les deux chemins d'installation ne divergent jamais.
$PY_VERSION = '3.12.7'
$PY_URL = "https://www.python.org/ftp/python/$PY_VERSION/python-$PY_VERSION-amd64.exe"
# Empreinte SHA-256 du fichier ci-dessus, VERIFIEE avant de l'executer (v2.48.2) :
# un telechargement interrompu ne doit jamais partir a l'execution (fichier
# tronque = signature invalide = message incomprehensible chez l'utilisateur).
# Valeur relevee d'un telechargement dont la signature Authenticode a ete
# verifiee comme Valide (signataire : Python Software Foundation).
# MEME valeur que installer/windows/avastack.iss (define PythonSha256) : un banc
# verifie que les deux fichiers s'accordent, sinon ils divergeraient en silence.
$PY_SHA256 = '1206721601A62C925D4E4A0DCFC371E88F2DDBE8C0C07962EBB2BE9B5BDE4570'

function Info   ($m) { Write-Host "[AVAStack] $m" }
function Avis   ($m) { Write-Host "[AVAStack] ATTENTION : $m" -ForegroundColor Yellow }
function Erreur ($m) { Write-Host "[AVAStack] ERREUR : $m" -ForegroundColor Red }

function Show-Usage {
    @"
Installateur Windows AVAStack (paquet ZIP) - usage :

  install_avastack.bat [options]                (double-clic recommande)
  powershell -NoProfile -ExecutionPolicy Bypass -File install_avastack.ps1 [options]

OPTIONS
  -Prefix DIR         dossier d'installation (defaut : %LOCALAPPDATA%\AVAStack)
  -Python EXE         impose un interpreteur precis (de preference un Python
                      de python.org). Utilise-le si tu veux choisir TOI-MEME le
                      Python ; le Python du Microsoft Store n'est JAMAIS
                      choisi tout seul.
  -SansRaccourci      n'ecrit ni raccourci Bureau ni raccourci Menu Demarrer
  -Simulation         montre ce qui serait fait, sans rien modifier (utile pour
                      verifier QUELLE version de Python serait choisie)
  -Forcer             passe outre un garde-fou : Python sans Tkinter, ou
                      desinstallation d'un dossier sans VERSION.txt
  -Desinstaller       desinstalle (GARDE les reglages)
  -Purge              avec -Desinstaller : supprime AUSSI les reglages
  -Aide               affiche cette aide

Le script utilise un Python de python.org (>= 3.10, avec Tkinter). S'il n'en
trouve pas, il telecharge et installe Python $PY_VERSION depuis python.org.
Le Python du Microsoft Store est IGNORE (voir l'en-tete du script).
"@
}

# --- emplacements -----------------------------------------------------------

# Dossier du script, capture UNE fois a la portee du SCRIPT. Piege mesure
# (02/10/2026) : dans une FONCTION, $MyInvocation.MyCommand.Path est VIDE (il ne
# designe le script qu'a sa propre portee), d'ou un « Split-Path -Parent $null »
# des qu'une fonction voulait retrouver le dossier du script.
$SCRIPT_DIR = $PSScriptRoot
if (-not $SCRIPT_DIR) { $SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $SCRIPT_DIR) { $SCRIPT_DIR = (Get-Location).Path }

function Get-ScriptDir {
    return $SCRIPT_DIR
}

# Racine du paquet = dossier qui contient AVAStack.py ET avastack\. Le script
# vit dans installer\ dans le paquet et installer\windows\ dans le depot : on
# remonte jusqu'a 4 niveaux.
function Find-Root {
    $d = Get-ScriptDir
    for ($i = 0; $i -lt 4; $i++) {
        if ((Test-Path (Join-Path $d 'AVAStack.py')) -and
            (Test-Path (Join-Path $d 'avastack'))) {
            return $d
        }
        $parent = Split-Path -Parent $d
        if (-not $parent -or $parent -eq $d) { break }
        $d = $parent
    }
    return $null
}

function Read-Version {
    param([string]$Racine)
    $f = Join-Path $Racine 'avastack\__init__.py'
    if (Test-Path $f) {
        $m = Select-String -Path $f -Pattern '^AVASTACK_VERSION\s*=\s*"([^"]+)"'
        if ($m) { return $m.Matches[0].Groups[1].Value }
    }
    return 'inconnue'
}

function Resolve-Chemin {
    param([string]$Chemin)
    try { return [System.IO.Path]::GetFullPath($Chemin) } catch { return $Chemin }
}

# --- Python : detection, en EXCLUANT le Python du Microsoft Store -----------

function Test-PythonStore {
    <# Vrai si le chemin designe le Python du Microsoft Store : l'alias
       ...\AppData\Local\Microsoft\WindowsApps\python.exe ou l'installation
       reelle sous ...\AppData\Local\Packages\PythonSoftwareFoundation.* #>
    param([string]$Chemin)
    if ([string]::IsNullOrWhiteSpace($Chemin)) { return $false }
    $c = $Chemin.ToLowerInvariant()
    return (($c -like '*\windowsapps\*') -or
            ($c -like '*\packages\pythonsoftwarefoundation.*'))
}

function Get-PythonVersion {
    param([string]$Chemin)
    if (-not (Test-Path -LiteralPath $Chemin -PathType Leaf)) { return $null }
    # ErrorActionPreference localement a 'Continue' : une commande NATIVE qui
    # ecrit sur stderr devient une erreur TERMINANTE sous 'Stop' (piege mesure
    # le 02/10/2026) - un Python parfaitement valide serait alors rejete.
    $ancien = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $texte = (& $Chemin --version 2>&1 | Out-String).Trim()
    } catch {
        return $null
    } finally {
        $ErrorActionPreference = $ancien
    }
    if ($texte -match '^Python\s+(\d+)\.(\d+)\.(\d+)') {
        return [pscustomobject]@{
            Texte     = "Python $($Matches[1]).$($Matches[2]).$($Matches[3])"
            Majeur    = [int]$Matches[1]
            Mineur    = [int]$Matches[2]
            Correctif = [int]$Matches[3]
        }
    }
    return $null
}

function Test-PythonModule {
    param([string]$Chemin, [string]$Module)
    $ancien = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Chemin -c ("import " + $Module) 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $ancien
    }
}

function Get-PythonCandidats {
    <# Candidats dans l'ordre de preference : python.org d'abord (par utilisateur
       puis machine), le lanceur py, puis le PATH. Le PATH est teste EN DERNIER :
       c'est la que se cache l'alias du Microsoft Store. #>
    $liste = New-Object System.Collections.Generic.List[string]
    if ($Python) { $liste.Add($Python) }
    $motifs = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python3*\python.exe'),
        (Join-Path $env:ProgramFiles 'Python3*\python.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Python3*\python.exe'),
        'C:\Python3*\python.exe',
        'C:\Python*\python.exe'
    )
    foreach ($motif in $motifs) {
        Get-ChildItem -Path $motif -ErrorAction SilentlyContinue |
            ForEach-Object { $liste.Add($_.FullName) }
    }
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        try {
            $cible = (& py.exe -c "import sys; print(sys.executable)" 2>$null |
                      Select-Object -First 1)
            if ($cible) { $liste.Add(("$cible").Trim()) }
        } catch { }
    }
    foreach ($nom in @('python.exe', 'python3.exe')) {
        $cmd = Get-Command $nom -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source) { $liste.Add($cmd.Source) }
    }
    return ($liste | Select-Object -Unique)
}

function Find-PythonUtilisable {
    <# -> objet @{Chemin;Version;Tkinter} du meilleur Python utilisable, ou $null.
       Un Python est retenu s'il est >= 3.10, s'il a venv (et ensurepip) et --
       sauf -Forcer -- Tkinter. Le Python du Microsoft Store est ECARTE. #>
    $rejetes = @()
    $bons = @()
    foreach ($c in Get-PythonCandidats) {
        if (Test-PythonStore $c) {
            $rejetes += "Python du Microsoft Store IGNORE : $c"
            continue
        }
        $v = Get-PythonVersion $c
        if (-not $v) { continue }
        if ($v.Majeur -lt $VERSION_MIN_MAJEUR -or
            ($v.Majeur -eq $VERSION_MIN_MAJEUR -and
             $v.Mineur -lt $VERSION_MIN_MINEUR)) {
            $rejetes += "trop ancien ($($v.Texte)) : $c"
            continue
        }
        if (-not (Test-PythonModule $c 'venv')) {
            $rejetes += "module venv incomplet : $c"
            continue
        }
        $tk = Test-PythonModule $c 'tkinter'
        if (-not $tk -and -not $Forcer) {
            $rejetes += "Tkinter absent : $c"
            continue
        }
        $bons += [pscustomobject]@{ Chemin = $c; Version = $v; Tkinter = $tk }
    }
    foreach ($r in $rejetes) { Avis $r }
    if ($bons.Count -eq 0) { return $null }
    return ($bons |
        Sort-Object -Property @{Expression = { $_.Version.Majeur }},
                              @{Expression = { $_.Version.Mineur }},
                              @{Expression = { $_.Version.Correctif }} -Descending |
        Select-Object -First 1)
}

# --- Python : telechargement + installation silencieuse depuis python.org ---

function Get-PythonFraichementInstalle {
    <# Retrouve le python.exe de l'installation python.org par utilisateur
       (%LOCALAPPDATA%\Programs\Python\Python3xx). Necessaire car PrependPath
       ne modifie PAS le PATH de la session en cours. #>
    $dossier = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (-not (Test-Path $dossier)) { return $null }
    $trouves = Get-ChildItem -Path (Join-Path $dossier 'Python3*') -Directory `
                             -ErrorAction SilentlyContinue |
               Sort-Object Name -Descending
    foreach ($d in $trouves) {
        $exe = Join-Path $d.FullName 'python.exe'
        if (Test-Path $exe) { return $exe }
    }
    return $null
}

function Install-PythonPythonOrg {
    <# Telecharge l'installateur python.org et l'installe silencieusement
       (par utilisateur, Tkinter INCLUS). Renvoie le chemin du python.exe
       installe, ou $null en cas d'echec (cause AFFICHEE, jamais muette). #>
    $dest = Join-Path $env:TEMP ("python-{0}-amd64.exe" -f $PY_VERSION)
    Info "aucun Python 3.10+ utilisable : telechargement de Python $PY_VERSION (python.org)"
    # Empreinte VERIFIEE avant execution (v2.48.2) : un telechargement interrompu
    # ne doit jamais partir a l'execution (fichier tronque = signature invalide =
    # message incomprehensible chez l'utilisateur). DEUX tentatives, comme
    # l'installateur Inno Setup, avec la MEME empreinte des deux cotes.
    $fichierBon = $false
    for ($essai = 1; $essai -le 2 -and -not $fichierBon; $essai++) {
        try {
            [Net.ServicePointManager]::SecurityProtocol = `
                [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $PY_URL -OutFile $dest -UseBasicParsing
        } catch {
            Avis "telechargement impossible (tentative $essai/2) : $($_.Exception.Message)"
            continue
        }
        $obtenue = ''
        if (Test-Path -LiteralPath $dest) {
            try {
                $obtenue = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash
            } catch {
                $obtenue = ''
            }
        }
        if ($obtenue.ToUpperInvariant() -eq $PY_SHA256) {
            $fichierBon = $true
        } else {
            Avis "fichier INCOMPLET ou altere (tentative $essai/2) : empreinte $obtenue"
            Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue
        }
    }
    if (-not $fichierBon) {
        Erreur "le telechargement de Python a echoue, ou le fichier recu est INCOMPLET."
        Erreur "Empreinte attendue : $PY_SHA256"
        Erreur "Verifie la connexion Internet (ou un proxy / antivirus qui filtre les"
        Erreur "telechargements), puis relance. Sinon, installe Python 3.10+"
        Erreur "MANUELLEMENT depuis python.org (coche 'Add python.exe to PATH'), puis"
        Erreur "relance ce script."
        return $null
    }
    Info "fichier telecharge et VERIFIE (SHA-256) : $dest"
    Info "installation silencieuse de Python (par utilisateur, Tkinter inclus)..."
    $arguments = @(
        '/quiet',
        'InstallAllUsers=0',
        'PrependPath=1',
        'Include_test=0',
        'Include_launcher=1',
        'Include_tcltk=1',
        'Include_pip=1'
    )
    try {
        $proc = Start-Process -FilePath $dest -ArgumentList $arguments `
                              -Wait -PassThru
        $code = $proc.ExitCode
    } catch {
        Erreur "lancement de l'installateur Python impossible : $($_.Exception.Message)"
        $code = -1
    }
    if ($code -ne 0 -and $code -ne 3010) {
        Erreur "l'installation de Python a echoue (code retour $code)."
        Erreur "Vraisemblables : un ANTIVIRUS, ou le Controle intelligent des"
        Erreur "applications qui bloque un executable non signe. Pour ce dernier"
        Erreur "(Windows 11) : Securite Windows > Controle des applications et du"
        Erreur "navigateur > Controle intelligent des applications > Arrete."
        return $null
    }
    Remove-Item -LiteralPath $dest -Force -ErrorAction SilentlyContinue
    $exe = Get-PythonFraichementInstalle
    if (-not $exe) {
        Erreur "Python a semble s'installer, mais python.exe reste introuvable."
        Erreur "Cherche-le dans %LOCALAPPDATA%\Programs\Python et relance ce script"
        Erreur "avec -Python <chemin complet>."
        return $null
    }
    return $exe
}

# --- copie de l'application -------------------------------------------------

function Copy-Application {
    param([string]$Src, [string]$Dst)
    Info "copie de l'application vers $Dst"
    New-Item -ItemType Directory -Force -Path $Dst | Out-Null
    foreach ($f in @('AVAStack.py', 'veralux_core_headless.py',
                     'requirements.txt')) {
        Copy-Item -LiteralPath (Join-Path $Src $f) (Join-Path $Dst $f) -Force
    }
    # Package avastack/ (recopie franche, __pycache__ jete)
    $dstPkg = Join-Path $Dst 'avastack'
    if (Test-Path $dstPkg) { Remove-Item $dstPkg -Recurse -Force }
    Copy-Item -LiteralPath (Join-Path $Src 'avastack') $dstPkg -Recurse -Force
    Get-ChildItem -Path $dstPkg -Recurse -Directory -Filter '__pycache__' `
        -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force `
        -ErrorAction SilentlyContinue
    # Bancs installes : les OUTILS DE DIAGNOSTIC MATERIEL camera seulement
    # (bancs/cameras/_diag_*.py) - meme regle que l'installateur Inno Setup.
    $srcBancs = Join-Path $Src 'bancs\cameras'
    if (Test-Path $srcBancs) {
        $dstBancs = Join-Path $Dst 'bancs\cameras'
        New-Item -ItemType Directory -Force -Path $dstBancs | Out-Null
        Get-ChildItem -Path $srcBancs -Filter '_diag_*.py' -File |
            Copy-Item -Destination $dstBancs -Force
    }
    # Lisez-moi utilisateur : racine du paquet, ou installer\windows\ quand le
    # script est lance depuis le depot.
    foreach ($f in @((Join-Path $Src 'LISEZMOI.txt'),
                     (Join-Path $Src 'installer\windows\LISEZMOI.txt'))) {
        if (Test-Path $f) {
            Copy-Item -LiteralPath $f (Join-Path $Dst 'LISEZMOI.txt') -Force
            break
        }
    }
    # Outil de creation du venv (stdlib seulement) : copie avec l'application
    # pour que l'installation reste auto-suffisante (mise a jour, reparation).
    foreach ($f in @((Join-Path $Src 'installer\common\avastack_setup.py'),
                     (Join-Path $Src 'installer\avastack_setup.py'))) {
        if (Test-Path $f) {
            $cible = Join-Path $Dst 'installer\common'
            New-Item -ItemType Directory -Force -Path $cible | Out-Null
            Copy-Item -LiteralPath $f (Join-Path $cible 'avastack_setup.py') -Force
            break
        }
    }
    # SDK binaires constructeurs presents a la racine du paquet (ZWO, Player
    # One, Touptek/Altair, SVBONY) : copies a cote de l'application, comme le
    # fait l'installateur Inno Setup.
    $dlls = Get-ChildItem -Path $Src -Filter '*.dll' -File `
                          -ErrorAction SilentlyContinue
    foreach ($d in $dlls) {
        Copy-Item -LiteralPath $d.FullName (Join-Path $Dst $d.Name) -Force
        Info "SDK camera copie : $($d.Name)"
    }
}

# --- dependances ------------------------------------------------------------

function New-RequirementsSansCameras {
    <# Copie de requirements.txt SANS les paquets cameras (qhyccd, zwoasi) :
       l'application demarre sans eux (leurs imports sont paresseux), et les
       tenter separement evite qu'un paquet camera en echec fasse echouer TOUTE
       l'installation - c'est exactement le "Code retour : 1" vu en v2.45.0. #>
    param([string]$Source, [string]$Destination)
    $lignes = Get-Content -LiteralPath $Source -Encoding UTF8
    $gardees = $lignes | Where-Object { $_ -notmatch '^\s*(qhyccd|zwoasi)\s*$' }
    Set-Content -LiteralPath $Destination -Value $gardees -Encoding ASCII
}

function New-Venv {
    param([string]$PythonExe, [string]$Venv, [string]$Requirements)
    $helper = Join-Path $Prefix 'installer\common\avastack_setup.py'
    # | Out-Host sur chaque commande native : leur sortie doit s'AFFICHER sans
    # entrer dans le pipeline (sinon elle serait capturee avec la valeur de
    # retour de la fonction -> $pythonVenv deviendrait un TABLEAU).
    if (Test-Path $helper) {
        & $PythonExe $helper create-venv --venv-dir $Venv `
            --requirements $Requirements | Out-Host
    } else {
        Info "creation du venv : $Venv"
        & $PythonExe -m venv $Venv | Out-Host
        $pyv = Join-Path $Venv 'Scripts\python.exe'
        & $pyv -m pip install --upgrade pip --quiet | Out-Host
        & $pyv -m pip install -r $Requirements --quiet | Out-Host
    }
    $py = Join-Path $Venv 'Scripts\python.exe'
    if (-not (Test-Path $py)) {
        Erreur "venv incomplet : $py absent."
        Erreur "Verifie que le Python utilise n'est pas celui du Microsoft Store"
        Erreur "($PythonExe), puis relance."
        exit 1
    }
    return $py
}

function Install-CamerasTolerant {
    <# Les paquets pip cameras sont tentes SEPAREMENT et SANS bloquer : leur
       absence ne doit jamais faire echouer l'installation (l'application ouvre
       alors les autres sources). #>
    param([string]$PythonVenv)
    Info "cameras : paquets pip optionnels tentes sans bloquer l'installation"
    foreach ($paquet in @('qhyccd', 'zwoasi')) {
        try {
            & $PythonVenv -m pip install $paquet --quiet | Out-Host
            if ($LASTEXITCODE -eq 0) {
                Info "  $paquet           OK"
            } else {
                Avis "  $paquet           NON installe (code $LASTEXITCODE)"
                Avis "  -> les cameras correspondantes seront indisponibles."
            }
        } catch {
            Avis "  $paquet           NON installe ($($_.Exception.Message))"
        }
    }
}

# --- lanceur et raccourcis --------------------------------------------------

function Write-Lanceur {
    param([string]$AppDir, [string]$Venv)
    $pythonw = Join-Path $Venv 'Scripts\pythonw.exe'
    $python  = Join-Path $Venv 'Scripts\python.exe'
    $contenu = @"
@echo off
rem Lanceur AVAStack - genere par install_avastack.ps1. Ne pas editer.
set PYTHONW=$pythonw
if exist "%PYTHONW%" (
    start "" "%PYTHONW%" "$AppDir\AVAStack.py"
) else (
    start "" "$python" "$AppDir\AVAStack.py"
)
"@
    $fichier = Join-Path $AppDir 'lancer_avastack.bat'
    Set-Content -LiteralPath $fichier -Value $contenu -Encoding ASCII
    Info "lanceur ecrit : $fichier"
    return $fichier
}

function New-Raccourci {
    param([string]$Cible, [string]$Lien, [string]$Description, [string]$Dossier)
    $shell = New-Object -ComObject WScript.Shell
    $raccourci = $shell.CreateShortcut($Lien)
    $raccourci.TargetPath = $Cible
    $raccourci.WorkingDirectory = $Dossier
    $raccourci.Description = $Description
    $raccourci.IconLocation = $Cible
    $raccourci.Save()
}

function Write-Raccourcis {
    param([string]$Lanceur, [string]$AppDir)
    $description = 'Live stacking AVAStack'
    $bureau = [Environment]::GetFolderPath('Desktop')
    if ($bureau) {
        New-Raccourci -Cible $Lanceur -Lien (Join-Path $bureau 'AVAStack.lnk') `
                      -Description $description -Dossier $AppDir
        Info "raccourci Bureau ecrit"
    } else {
        Avis "dossier Bureau introuvable : raccourci Bureau non ecrit."
    }
    $menu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AVAStack'
    try {
        New-Item -ItemType Directory -Force -Path $menu | Out-Null
        New-Raccourci -Cible $Lanceur -Lien (Join-Path $menu 'AVAStack.lnk') `
                      -Description $description -Dossier $AppDir
        New-Raccourci -Cible $AppDir -Lien (Join-Path $menu 'Dossier AVAStack.lnk') `
                      -Description 'Dossier d''installation AVAStack' -Dossier $AppDir
        Info "raccourcis Menu Demarrer ecrits : $menu"
    } catch {
        Avis "raccourcis Menu Demarrer non ecrits : $($_.Exception.Message)"
    }
}

# --- verification -----------------------------------------------------------

function Test-ImportModules {
    <# Vrai si « import <Modules> » reussit DANS le venv.
       Le passage TEMPORAIRE en ErrorActionPreference='Continue' est
       indispensable : sous 'Stop', une ligne ecrite sur stderr par une
       commande native devient une erreur TERMINANTE (mesure du 02/10/2026 -
       l'installation s'arretait sur « import numpy, cv2, PIL » alors que ce
       controle doit seulement AVERTIR). #>
    param([string]$PythonVenv, [string]$Modules)
    $ancien = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $PythonVenv -c ("import " + $Modules) 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $ancien
    }
}

function Test-Application {
    param([string]$Dossier, [string]$PythonVenv)
    Info "verification de l'installation"
    if (Test-ImportModules $PythonVenv 'tkinter') {
        Info "  Tkinter (interface)       OK"
    } else {
        Avis "  Tkinter ABSENT du venv : l'interface ne peut pas s'ouvrir."
    }
    if (Test-ImportModules $PythonVenv 'numpy, cv2, PIL') {
        Info "  numpy / OpenCV / Pillow   OK"
    } else {
        Avis "  numpy / OpenCV / Pillow inutilisables."
    }
    if (Test-ImportModules $PythonVenv 'astropy') {
        Info "  astropy (FITS)            OK"
    } else {
        Avis "  astropy absent : lecture et ecriture FITS limitees."
    }
    # v2.38.7 : DEMARRAGE REEL de l'application - on IMPORTE l'interface dans le
    # venv, depuis le dossier d'installation (aucune fenetre ouverte). Un
    # installateur qui conclut "termine" sur une application incapable de
    # demarrer envoie l'utilisateur chercher au mauvais endroit.
    # Capture par REDIRECTION DE FICHIERS (Start-Process) : la trace d'erreur
    # Python ressort alors PROPREMENT (pas d'enrobage PowerShell) et une erreur
    # n'arrete jamais l'installation.
    $fSortie = Join-Path $env:TEMP ("avastack_demarrage_{0}.out" -f $PID)
    $fErreur = Join-Path $env:TEMP ("avastack_demarrage_{0}.err" -f $PID)
    $ancien = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $code = 1
    try {
        # -ArgumentList en CHAINE citee : un tableau ne protegerait PAS l'espace
        # de « import avastack.ui.app », et python recevrait « -c import » seul
        # (mesure du 02/10/2026 : SyntaxError « Expected one or more names »).
        $proc = Start-Process -FilePath $PythonVenv `
            -ArgumentList '-c "import avastack.ui.app"' `
            -WorkingDirectory $Dossier -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $fSortie -RedirectStandardError $fErreur
        $code = $proc.ExitCode
        $erreur = if (Test-Path $fErreur) { Get-Content $fErreur -Raw } else { "" }
    } catch {
        $erreur = "" + $_.Exception.Message
        $code = 1
    } finally {
        $ErrorActionPreference = $ancien
        Remove-Item -LiteralPath $fSortie, $fErreur -Force `
            -ErrorAction SilentlyContinue
    }
    if ($code -eq 0) {
        Info "  demarrage (imports)       OK"
    } else {
        Avis "  L'APPLICATION NE PEUT PAS DEMARRER - erreur exacte :"
        foreach ($l in (("" + $erreur) -split "`r?`n")) {
            if ($l -ne "") { Write-Host "      $l" }
        }
        Avis "  corrige la cause ci-dessus, puis relance ce script ; le"
        Avis "  journal de l'application gardera la trace des essais suivants :"
        Avis ("      " + (Join-Path $env:APPDATA 'AVAStack\journal.txt'))
    }
}

# --- desinstallation --------------------------------------------------------

function Uninstall-AvaStack {
    param([string]$Dossier, [switch]$PurgeReglages)
    $versionTxt = Join-Path $Dossier 'VERSION.txt'
    if (-not (Test-Path $versionTxt)) {
        Erreur "$Dossier ne ressemble pas a une installation AVAStack (VERSION.txt absent)."
        if (-not $Forcer) {
            Erreur "Verifie -Prefix ; ajoute -Forcer pour passer outre ce garde-fou."
            exit 2
        }
        Avis "garde-fou ignore (-Forcer) : poursuite de la suppression."
    }
    # Ne touche aux raccourcis QUE si l'installation les a CREES. Marque depuis la
    # v2.48.2 dans VERSION.txt : une installation d'essai faite en -SansRaccourci
    # ne doit pas effacer les raccourcis d'une AUTRE installation (defaut constate
    # le 02/10/2026). Les installations ANTERIEURES n'ont pas la marque : on garde
    # alors le comportement d'avant (raccourcis retires).
    $raccourcisCrees = $true
    if (Test-Path $versionTxt) {
        if (Select-String -Path $versionTxt -Pattern 'raccourcis : AUCUN' `
                -SimpleMatch -ErrorAction SilentlyContinue) {
            $raccourcisCrees = $false
        }
    }
    Info "desinstallation de $Dossier"
    Remove-Item -LiteralPath $Dossier -Recurse -Force
    if ($raccourcisCrees) {
        $bureau = [Environment]::GetFolderPath('Desktop')
        foreach ($lien in @((Join-Path $bureau 'AVAStack.lnk'),
                            (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AVAStack'))) {
            if (Test-Path -LiteralPath $lien) {
                Remove-Item -LiteralPath $lien -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    } else {
        Info "raccourcis non touches (installation faite avec -SansRaccourci)."
    }
    $config = Join-Path $env:APPDATA 'AVAStack'
    if ($PurgeReglages) {
        Remove-Item -LiteralPath $config -Recurse -Force -ErrorAction SilentlyContinue
        Info "reglages supprimes : $config"
    } else {
        Info "reglages conserves : $(Join-Path $config 'config.json')"
    }
}

# --- programme --------------------------------------------------------------

function Main {
    # Le code de sortie passe par une variable de PORTEE SCRIPT : ecrire
    # « exit (Main) » CAPTURERAIT la sortie de pipeline de Main (le texte de
    # l'aide, la sortie de pip) au lieu de la laisser s'afficher - mesure du
    # 02/10/2026 : -Aide n'affichait plus RIEN.
    $script:CODE_SORTIE = 0

    if ($Aide) { Show-Usage; return }

    # Garde-fou : ce script est l'installateur WINDOWS. PowerShell Core existe
    # aussi sous Linux/macOS : on refuse franchement, en renvoyant au bon paquet.
    if ($env:OS -ne 'Windows_NT') {
        Erreur "ce script est l'installateur Windows (systeme detecte : $($env:OS))."
        Erreur "Linux : avastack-setup-<version>-linux.tar.gz puis bash installer/install_avastack.sh"
        Erreur "macOS : avastack-setup-<version>-macos.tar.gz puis bash installer/install_avastack.sh"
        $script:CODE_SORTIE = 1
        return
    }

    $cible = Resolve-Chemin $Prefix
    $script:Prefix = $cible

    if ($Desinstaller) {
        Uninstall-AvaStack -Dossier $cible -PurgeReglages:$Purge
        return
    }

    $racine = Find-Root
    if (-not $racine) {
        Erreur "AVAStack.py introuvable autour de $(Get-ScriptDir)."
        Erreur "Extrais le ZIP EN ENTIER (clic droit sur le .zip > Extraire tout)"
        Erreur "puis relance install_avastack.bat depuis le dossier extrait."
        $script:CODE_SORTIE = 1
        return
    }
    if ($cible -eq $racine) {
        Erreur "le dossier d'installation est le dossier du paquet : choisis-en un autre (-Prefix)."
        $script:CODE_SORTIE = 2
        return
    }

    $version = Read-Version $racine
    $info = Find-PythonUtilisable

    Write-Host ""
    Info "AVAStack $version - installateur Windows (paquet ZIP)"
    Info "dossier d'installation : $cible"
    if ($info) {
        Info "Python retenu : $($info.Version.Texte) ($($info.Chemin))"
        if (-not $info.Tkinter) { Avis "Tkinter absent (accepte par -Forcer)." }
    } else {
        Avis "aucun Python python.org >= 3.10 utilisable trouve."
        Info "il sera telecharge et installe depuis python.org : $PY_URL"
    }
    Write-Host ""

    if ($Simulation) {
        Info "SIMULATION : rien n'a ete modifie."
        Info "seraient faits : copie de l'application, venv + dependances, lanceur,"
        Info "raccourcis Bureau/Menu Demarrer, puis TEST DE DEMARRAGE reel."
        return
    }

    if (-not $info) {
        $exe = Install-PythonPythonOrg
        if (-not $exe) { $script:CODE_SORTIE = 1; return }
        $info = Find-PythonUtilisable
        if (-not $info) {
            Erreur "Python vient d'etre installe mais reste introuvable : relance ce script."
            $script:CODE_SORTIE = 1
            return
        }
        Info "Python installe : $($info.Version.Texte) ($($info.Chemin))"
    }

    Copy-Application -Src $racine -Dst $cible
    # La marque "raccourcis" est RELUE a la desinstallation : une installation
    # d'essai en -SansRaccourci ne doit PAS effacer les raccourcis d'une AUTRE
    # installation (defaut constate le 02/10/2026).
    $marqueRaccourcis = if ($SansRaccourci) {
        'raccourcis : AUCUN (-SansRaccourci)'
    } else {
        'raccourcis : Bureau + Menu Demarrer'
    }
    Set-Content -LiteralPath (Join-Path $cible 'VERSION.txt') -Encoding ASCII `
        -Value @("AVAStack $version",
                 "installe le $(Get-Date -Format 'yyyy-MM-dd HH:mm') par installer\install_avastack.ps1",
                 $marqueRaccourcis)

    $requirements = Join-Path $cible 'requirements-installation.txt'
    New-RequirementsSansCameras -Source (Join-Path $cible 'requirements.txt') `
        -Destination $requirements
    $pythonVenv = New-Venv -PythonExe $info.Chemin -Venv (Join-Path $cible 'venv') `
        -Requirements $requirements
    Remove-Item -LiteralPath $requirements -Force -ErrorAction SilentlyContinue
    Install-CamerasTolerant -PythonVenv $pythonVenv

    $lanceur = Write-Lanceur -AppDir $cible -Venv (Join-Path $cible 'venv')
    if (-not $SansRaccourci) { Write-Raccourcis -Lanceur $lanceur -AppDir $cible }

    Test-Application -Dossier $cible -PythonVenv $pythonVenv

    Write-Host ""
    Info "installation terminee - AVAStack $version"
    Write-Host "  Dossier        : $cible"
    Write-Host "  Interpreteur   : $pythonVenv"
    if ($SansRaccourci) {
        Write-Host "  Lancement      : $lanceur"
    } else {
        Write-Host "  Lancement      : raccourci AVAStack (Bureau / Menu Demarrer)"
        Write-Host "                   ou : $lanceur"
    }
    Write-Host "  Reglages       : $(Join-Path $env:APPDATA 'AVAStack\config.json')"
    Write-Host "  Journal        : $(Join-Path $env:APPDATA 'AVAStack\journal.txt')"
    Write-Host "  Version notee  : $(Join-Path $cible 'VERSION.txt')"
    Write-Host "  Mise a jour    : fermer AVAStack, extraire le nouveau paquet, relancer"
    Write-Host "                   ce script (le venv et les reglages sont reutilises)."
    Write-Host "  Desinstaller   : install_avastack.bat -Desinstaller [-Purge]"
    Write-Host ""
}

# Appel de Main SANS capturer sa sortie : les messages (aide, sortie de pip)
# doivent s'afficher, et le code de sortie passe par $script:CODE_SORTIE.
Main
exit $script:CODE_SORTIE




