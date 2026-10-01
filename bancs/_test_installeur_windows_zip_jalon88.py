# -*- coding: utf-8 -*-
"""Banc du jalon 88 : INSTALLATEUR WINDOWS « paquet ZIP » — contenu, garde-fous
et DÉTECTION RÉELLE de l'interpréteur.

POURQUOI CE PAQUET : l'installateur `avastack-setup-<version>.exe` (Inno Setup)
est un exécutable NON SIGNÉ ; sur un Windows 11 neuf, le Contrôle intelligent
des applications (Smart App Control) bloque un fichier temporaire d'Inno Setup et
l'installation s'arrête sur « Erreur 4551 » (constat réel du 01/10/2026). Le
paquet ZIP n'exécute AUCUN binaire à nous : un script PowerShell fait le travail.

Ce banc vérifie TOUT ce qui est vérifiable SANS machine vierge, et le DIT (règle
du projet : une affirmation d'état est DATÉE, jamais inventée) :

  [1] le PACKER (`installer/windows/build_avastack_zip.py`) : nom d'artéfact qui
      porte la version lue dans `avastack/__init__.py`, racine unique
      `avastack-<version>-windows/`, application complète, script d'installation
      + lanceur `.bat` + outil de venv + `LISEZMOI.txt`, seuls les bancs
      `bancs/cameras/_diag_*.py`, AUCUN `.so`/`.dylib`/`.rules`, et les DLL
      constructeurs NOMMÉES embarquées (quand elles sont là) ;
  [2] les FINS DE LIGNE : `.py`, `.ps1`, `.bat`, `.txt` en CRLF dans l'archive
      (un `.bat` en LF se comporte mal sous `cmd.exe`) ;
  [3] les GARDE-FOUS présents dans le TEXTE du script : exclusion du Python du
      Microsoft Store, téléchargement python.org, Tkinter, refus « dossier
      d'installation = dossier du paquet », désinstallation, test de démarrage
      réel, et `ErrorActionPreference` ramené à `Continue` autour des commandes
      NATIVES (sinon stderr devient une erreur TERMINANTE) ;
  [4] l'ACCORD avec `avastack.iss` : le MÊME Python de python.org est déclaré
      des deux côtés (deux chaînes recopiées finissent toujours par diverger) ;
  [5] EXÉCUTION RÉELLE (si PowerShell est disponible) : `-Aide` sort 0 et
      affiche l'usage ; `-Simulation` sort 0, NE MODIFIE RIEN et n'annonce
      jamais un Python du Microsoft Store comme « retenu » ; `-Simulation` avec
      `-Prefix` = racine du paquet REFUSE (code 2).

Exécution : python bancs/_test_installeur_windows_zip_jalon88.py
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


RACINE = str(_pl_banc.Path(__file__).resolve().parents[1])
sys.path.insert(0, os.path.join(RACINE, "installer", "windows"))
import build_avastack_zip as packer                              # noqa: E402

TMP = tempfile.mkdtemp(prefix="banc88_")
VERSION = packer.lire_version(RACINE)
NOM_ARCHIVE = "avastack-setup-%s-windows.zip" % VERSION
PREFIXE = "avastack-%s-windows" % VERSION
SCRIPT = os.path.join(RACINE, "installer", "windows", "install_avastack.ps1")
ISS = os.path.join(RACINE, "installer", "windows", "avastack.iss")

# ======================================================= [1] le paquet
print("[1] le packer Windows ZIP : contenu et nom d'artéfact")
chemin, entrees, convertis, dlls, manquantes = packer.construire(
    RACINE, VERSION, TMP)
verifie(os.path.basename(chemin) == NOM_ARCHIVE,
        "l'artéfact PORTE la version lue dans le source (%s)" % NOM_ARCHIVE)
with zipfile.ZipFile(chemin, "r") as arch:
    noms = arch.namelist()
    donnees = {n: arch.read(n) for n in noms}
relatifs = [n[len(PREFIXE) + 1:] for n in noms]
verifie(all(n.startswith(PREFIXE + "/") for n in noms),
        "racine unique %s/ (%d fichiers)" % (PREFIXE, len(noms)))
for attendu in ("AVAStack.py", "requirements.txt", "veralux_core_headless.py",
                "installer/install_avastack.ps1",
                "installer/install_avastack.bat",
                "installer/common/avastack_setup.py", "LISEZMOI.txt"):
    verifie(attendu in relatifs, "embarqué : %s" % attendu)
n_reels = 0
for dossier, sous, fichiers in os.walk(os.path.join(RACINE, "avastack")):
    sous[:] = [s for s in sous if s != "__pycache__"]
    n_reels += sum(1 for f in fichiers if f.endswith(".py"))
n_py = len([n for n in relatifs if n.startswith("avastack/") and n.endswith(".py")])
verifie(n_py == n_reels,
        "les %d modules de l'application sont embarqués" % n_reels)
verifie(not [n for n in relatifs
             if n.lower().endswith((".so", ".dylib", ".rules"))],
        "AUCUN binaire Linux/macOS embarqué")
diag = [n for n in relatifs if n.startswith("bancs/cameras/")]
verifie(bool(diag) and all("_diag_" in n for n in diag),
        "seuls les diagnostics caméra sont embarqués (%d) — pas les bancs de dev"
        % len(diag))
attendues_dll = set(packer.SDK_DLLS)
if dlls:
    verifie(set(dlls) == attendues_dll,
            "les 4 DLL constructeurs NOMMÉES sont embarquées (%s)"
            % ", ".join(sorted(dlls)))
else:
    print("  (aucune DLL à la racine : paquet SANS caméras — cas admis)")

# ======================================================= [2] fins de ligne
print("[2] fins de ligne CRLF dans l'archive (.bat/.ps1/.py/.txt)")
mauvais = []
for n in relatifs:
    if n.lower().endswith(packer.EXTENSIONS_CRLF):
        donnees_n = donnees[PREFIXE + "/" + n]
        if b"\r\n" not in donnees_n or re.search(rb"[^\r]\n", donnees_n):
            mauvais.append(n)
verifie(not mauvais, "tous les .py/.ps1/.bat/.txt sont en CRLF %s"
        % (mauvais[:3] or "(0 défaut)"))

# ======================================================= [3] garde-fous
print("[3] garde-fous présents dans le script d'installation")
with open(SCRIPT, encoding="utf-8", errors="replace") as f:
    texte = f.read()
for motif, quoi in (
        ("\\windowsapps\\", "exclusion de l'alias du Microsoft Store"),
        ("pythonsoftwarefoundation", "exclusion de l'installation du Store"),
        ("python.org", "Python de python.org"),
        ("InstallAllUsers=0", "installation de Python PAR UTILISATEUR"),
        ("Include_tcltk=1", "Tkinter explicitement inclus"),
        ("PrependPath=1", "python.org ajouté au PATH"),
        ("3.10", "version minimale 3.10"),
        ("tkinter", "contrôle Tkinter"),
        ("-Simulation", "mode simulation (sans rien modifier)"),
        ("-Desinstaller", "désinstallation"),
        ("-Purge", "purge des réglages"),
        ("VERSION.txt", "garde-fou de désinstallation"),
        ("lancer_avastack.bat", "lanceur Windows"),
        ("import avastack.ui.app", "TEST DE DÉMARRAGE réel"),
        ("journal.txt", "où lire le journal en cas d'échec"),
        ("Controle intelligent des applications",
         "aide en cas de blocage Smart App Control"),
        ("ErrorActionPreference = 'Continue'",
         "protection contre stderr devenu erreur TERMINANTE"),
        ("dossier d'installation est le dossier du paquet",
         "refus d'installer dans le paquet")):
    verifie(motif.lower() in texte.lower(), "%s" % quoi)
verifie("qhyccd" in texte and "zwoasi" in texte,
        "paquets pip caméras tentés SANS bloquer l'installation")
verifie("Microsoft Store" in texte and "JAMAIS" in texte,
        "la règle « jamais le Python du Store » est écrite dans le script")

# ======================================================= [4] accord avec le .iss
print("[4] accord avec l'installateur Inno Setup (même Python de python.org)")
with open(ISS, encoding="utf-8", errors="replace") as f:
    iss = f.read()
url_iss = re.search(r'PythonInstallerUrl\s+"([^"]+)"', iss)
verif_ps = re.search(r"\$PY_VERSION\s*=\s*'([^']+)'", texte)
verifie(url_iss is not None and verif_ps is not None,
        "les deux fichiers déclarent un Python de python.org")
if url_iss and verif_ps:
    verifie(url_iss.group(1).endswith("python-%s-amd64.exe" % verif_ps.group(1)),
            "MÊME version des deux côtés (%s)" % verif_ps.group(1))

# ======================================================= [5] exécution réelle
print("[5] exécution réelle du script (PowerShell, s'il est là)")
powershell = None
if os.name == "nt":
    for candidat in ("powershell",
                     r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"):
        try:
            subprocess.run([candidat, "-NoProfile", "-Command", "exit 0"],
                           capture_output=True, timeout=30)
            powershell = candidat
            break
        except Exception:
            continue


def lancer(arguments):
    r = subprocess.run([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", SCRIPT] + arguments,
                       capture_output=True, timeout=300, cwd=RACINE)
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


if powershell is None:
    print("  (PowerShell indisponible : section [5] non vérifiée ici)")
else:
    code, sortie = lancer(["-Aide"])
    verifie(code == 0 and "-Prefix" in sortie and "-Simulation" in sortie,
            "« -Aide » sort 0 et affiche l'usage")
    cible = os.path.join(TMP, "cible_simulation")
    code, sortie = lancer(["-Simulation", "-Prefix", cible])
    verifie(code == 0, "« -Simulation » sort 0")
    verifie("SIMULATION" in sortie,
            "« -Simulation » annonce qu'elle ne modifie rien")
    lignes_retenu = [l for l in sortie.splitlines() if "Python retenu" in l]
    verifie(not [l for l in lignes_retenu
                 if "WindowsApps" in l or "PythonSoftwareFoundation" in l],
            "jamais le Python du Microsoft Store comme « retenu » %s"
            % (lignes_retenu or "(aucun Python trouvé)"))
    verifie(not os.path.exists(cible),
            "« -Simulation » n'a RIEN créé (%s)" % cible)
    code, sortie = lancer(["-Simulation", "-Prefix", RACINE])
    verifie(code == 2 and "dossier du paquet" in sortie,
            "« -Prefix <racine du paquet> » REFUSE (code 2)")

shutil.rmtree(TMP, ignore_errors=True)
print("\nBANC JALON 88 (installateur Windows ZIP) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)

