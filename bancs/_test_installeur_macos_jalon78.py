# -*- coding: utf-8 -*-
"""Banc du jalon 78 : INSTALLATEUR macOS — paquet, contenu et garde-fous.

Le portage macOS n'a pas de machine en test ici : ce banc vérifie donc TOUT ce
qui est vérifiable SANS macOS, et le DIT (règle du projet : une affirmation
d'état est DATÉE, jamais inventée).

  [1] le PACKER (`installer/macos/build_avastack.py`) : nom d'artéfact qui porte
      la version lue dans `avastack/__init__.py`, racine unique
      `avastack-<version>-macos/`, tous les `.py` de l'application,
      `installer/install_avastack.sh` en 0755, `LISEZMOI.txt`,
      `installer/common/avastack_setup.py` — et AUCUN binaire constructeur
      (`.so`/`.dll`/`.dylib`/`.rules`) ;
  [2] les FINS DE LIGNE : `.sh` et `.txt` en UNIX dans l'archive (un script en
      CRLF ne s'exécute pas — leçon du 27/09/2026), y compris la TAILLE annoncée
      par le tar (elle change à la conversion) ;
  [3] le SCRIPT d'installation, réellement exécuté ici avec le bash de Git Bash :
      `--aide` sort 0 et affiche l'usage ; SANS option il REFUSE de s'installer
      hors macOS (c'est le garde-fou qui empêche un utilisateur Windows/Linux
      d'aller au bout) ; `bash -n` valide sa syntaxe ;
  [4] les garde-fous PRÉSENTS DANS LE TEXTE : refus hors Darwin, prérequis
      Tkinter (python.org et `python-tk` de Homebrew), bundle `.app`, mention de
      la quarantaine (`xattr`), journal, `--desinstaller`/`--purger`, `--cameras`.

Exécution : python bancs/_test_installeur_macos_jalon78.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (et bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


RACINE = str(_pl_banc.Path(__file__).resolve().parents[1])
sys.path.insert(0, os.path.join(RACINE, "installer", "macos"))
import build_avastack as packer                                  # noqa: E402

TMP = tempfile.mkdtemp(prefix="banc78_")
VERSION = packer.lire_version(RACINE)
NOM_ARCHIVE = "avastack-setup-%s-macos.tar.gz" % VERSION
PREFIXE = "avastack-%s-macos" % VERSION

# ======================================================= [1] le paquet
print("[1] le packer macOS : contenu et nom d'artéfact")
chemin, entrees, convertis = packer.construire(RACINE, VERSION, TMP)
verifie(os.path.basename(chemin) == NOM_ARCHIVE,
        "l'artéfact PORTE la version lue dans le source (%s)" % NOM_ARCHIVE)
noms = []
with tarfile.open(chemin, "r:gz") as arch:
    membres = arch.getmembers()
    for m in membres:
        noms.append(m.name)
        with arch.extractfile(m) as f:
            donnees = f.read() if f is not None else b""
        if m.name.endswith((".sh", ".txt")):
            verifie(b"\r\n" not in donnees,
                    "fins de ligne UNIX : %s" % m.name.split("/", 1)[1])
    sh = [m for m in membres if m.name.endswith("installer/install_avastack.sh")]
    verifie(len(sh) == 1 and (sh[0].mode & 0o111) == 0o111,
            "installer/install_avastack.sh est EXÉCUTABLE (mode %o)"
            % (sh[0].mode if sh else 0))

racines = {n.split("/")[0] for n in noms}
verifie(racines == {PREFIXE}, "un SEUL dossier racine : %s" % sorted(racines))
relatifs = {n.split("/", 1)[1] for n in noms if "/" in n}
attendus = {"AVAStack.py", "requirements.txt", "veralux_core_headless.py",
            "LISEZMOI.txt", "installer/install_avastack.sh",
            "installer/common/avastack_setup.py"}
verifie(attendus <= relatifs,
        "fichiers indispensables présents (manquants : %s)"
        % sorted(attendus - relatifs))
n_py = sum(1 for n in relatifs if n.startswith("avastack/") and n.endswith(".py"))
n_reels = sum(1 for _d, _s, fs in os.walk(os.path.join(RACINE, "avastack"))
              for f in fs if f.endswith(".py"))
verifie(n_py == n_reels,
        "les %d modules de l'application sont embarqués" % n_reels)
binaires = [n for n in relatifs
            if n.lower().endswith((".so", ".dll", ".dylib", ".rules"))]
verifie(not binaires,
        "AUCUN binaire constructeur embarqué %s" % (binaires or "(0)"))
diag = [n for n in relatifs if n.startswith("bancs/cameras/")]
verifie(bool(diag) and all("_diag_" in n for n in diag),
        "seuls les diagnostics caméra sont embarqués (%d) — pas les bancs de dev"
        % len(diag))

# ======================================================= [2] les garde-fous
print("[2] garde-fous présents dans le script d'installation")
script = os.path.join(RACINE, "installer", "macos", "install_avastack.sh")
with open(script, encoding="utf-8", errors="replace") as f:
    texte = f.read()
for motif, quoi in (('"Darwin"', "refus d'installer hors macOS"),
                    ("python.org", "Python de python.org (Tk inclus)"),
                    ("python-tk", "python-tk de Homebrew"),
                    ("AVAStack.app", "bundle cliquable .app"),
                    ("xattr -dr com.apple.quarantine", "quarantaine (Gatekeeper)"),
                    ("journal.txt", "où lire le journal en cas d'échec"),
                    ("--desinstaller", "désinstallation"),
                    ("--purger", "purge des réglages"),
                    ("--cameras", "caméras (option)"),
                    ("import avastack.ui.app", "TEST DE DÉMARRAGE réel"),
                    ("VERSION.txt", "garde-fou de désinstallation")):
    verifie(motif in texte, "%s" % quoi)
verifie("pip install \"$paquet\"" in texte and "qhyccd" in texte,
        "les paquets pip caméras sont tentés SANS bloquer l'installation")


# ======================================================= [3] exécution réelle
print("[3] exécution réelle du script (bash de Git Bash, s'il est là)")
bash = None
for candidat in ("bash", r"C:\Program Files\Git\bin\bash.exe"):
    try:
        subprocess.run([candidat, "--version"], capture_output=True, timeout=20)
        bash = candidat
        break
    except Exception:
        continue
if bash is None:
    print("  (bash indisponible : sections [3] non vérifiées sur cette machine)")
else:
    extrait = os.path.join(TMP, "extrait")
    with tarfile.open(chemin, "r:gz") as arch:
        arch.extractall(extrait)
    dossier = os.path.join(extrait, PREFIXE)
    script_extrait = os.path.join(dossier, "installer", "install_avastack.sh")
    r = subprocess.run([bash, script_extrait, "--aide"], capture_output=True,
                       timeout=60, cwd=dossier)
    sortie = (r.stdout + r.stderr).decode("utf-8", "replace")
    verifie(r.returncode == 0 and "--prefix" in sortie and "--cameras" in sortie,
            "« --aide » sort 0 et affiche l'usage")
    r2 = subprocess.run([bash, script_extrait], capture_output=True, timeout=60,
                        cwd=dossier)
    sortie2 = (r2.stdout + r2.stderr).decode("utf-8", "replace")
    verifie(r2.returncode != 0 and "installateur macOS" in sortie2
            and "linux.tar.gz" in sortie2,
            "sans option : REFUS hors macOS, en renvoyant vers les bons paquets")
    r3 = subprocess.run([bash, "-n", script_extrait], capture_output=True,
                        timeout=60, cwd=dossier)
    verifie(r3.returncode == 0,
            "syntaxe du script embarqué validée (bash -n) — dans l'archive")

shutil.rmtree(TMP, ignore_errors=True)
print("\nBANC JALON 78 (installateur macOS) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)

