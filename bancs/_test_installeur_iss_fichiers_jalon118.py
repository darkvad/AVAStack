# -*- coding: utf-8 -*-
"""Banc du jalon 118 : CONTENU DE L'INSTALLATEUR WINDOWS (Inno Setup) — garde-fou
contre l'omission des SOUS-PAQUETS.

POURQUOI CE BANC (defaut REEL du 10/10/2026) : l'installateur
`avastack-setup-<version>.exe` listait ses sources DOSSIER PAR DOSSIER
(`avastack\\ui\\*.py`, `avastack\\processing\\*.py`, ...). Le refactoring a cree des
SOUS-PAQUETS (`avastack/core/`, `avastack/ui/widgets/`, `avastack/ui/panels/`, a
partir du 07/10/2026) que cette liste ne connaissait pas : le paquet installe
plantait au demarrage sur
`ModuleNotFoundError: No module named 'avastack.ui.widgets'` (versions v2.58.1 a
v2.71.0). Ce banc rend la panne IMPOSSIBLE EN SILENCE : il verifie que TOUT
fichier du package `avastack/` — y compris chaque sous-paquet, present OU FUTUR —
est couvert par la section [Files] d'`avastack.iss`.

Le banc simule la selection de fichiers d'Inno Setup : expansion des motifs
`Source` (jokers), drapeau `recursesubdirs`, et parametre `Excludes` (motif sans
antislash initial = comparaison en FIN de chemin, cf. doc Inno Setup). Cette
simulation a ete CONFRONTEE a un essai reel (mini-paquet compile et installe :
arborescence preservee, `__pycache__`/`.pyc`/`.pyi` exclus). Il ne remplace pas un
essai sur machine vierge : il ne le pretend pas fait.

  [1] COUVERTURE : tout `.py` de `avastack/` (dont core/, ui/widgets/,
      ui/panels/) est selectionne par [Files] ;
  [2] PROPRETE : aucun `__pycache__`, `.pyc` ni `.pyi` n'est embarque ;
  [3] DONNEES : le catalogue embarque (`catalogues/data/*.bz2`) est selectionne ;
  [4] COMPILATION (si ISCC est present) : `avastack.iss` compile sans erreur.

Execution : python bancs/_test_installeur_iss_fichiers_jalon118.py
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import fnmatch
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


RACINE = str(_pl_banc.Path(__file__).resolve().parents[1])
ISS = os.path.join(RACINE, "installer", "windows", "avastack.iss")
def _entrees_files(chemin):
    """→ lignes Source de la section [Files] (continuations de ligne resolues)."""
    with open(chemin, encoding="utf-8", errors="replace") as f:
        brut = f.read().splitlines()
    fusionnees, tampon = [], ""
    for ligne in brut:
        if tampon:
            ligne = tampon + ligne.lstrip()
            tampon = ""
        if ligne.rstrip().endswith("\\"):
            tampon = ligne.rstrip()[:-1]
            continue
        fusionnees.append(ligne)
    en_files, entrees = False, []
    for ligne in fusionnees:
        s = ligne.strip()
        if s.startswith("[") and s.endswith("]"):
            en_files = (s == "[Files]")
            continue
        if not en_files or not s or s.startswith(";"):
            continue
        if s.lower().startswith("source:"):
            entrees.append(s)
    return entrees


def _champ(texte, nom):
    m = re.search(nom + r':\s*"([^"]*)"', texte)
    return m.group(1) if m else ""


def _exclus(texte):
    m = re.search(r'Excludes:\s*"([^"]*)"', texte)
    return [p.strip() for p in m.group(1).split(",") if p.strip()] if m else []


def _exclu(rel, motifs):
    """Inno : motif sans antislash initial -> comparaison en FIN de chemin."""
    for motif in motifs:
        if motif.startswith("\\"):
            if fnmatch.fnmatch(rel, motif[1:]):
                return True
        elif fnmatch.fnmatch(rel, "*" + motif):
            return True
    return False


def selectionnes(racine, iss):
    """→ fichiers du depot selectionnes par [Files] (chemins relatifs a la racine)."""
    installes = set()
    for entree in _entrees_files(iss):
        src = _champ(entree, "Source")
        if "{#RepoRoot}" not in src:                # entrees locales : hors sujet
            continue
        motif = src.replace("{#RepoRoot}", racine)
        if not motif.startswith(racine + os.sep):
            continue
        base = os.path.dirname(motif)
        if not os.path.isdir(base):
            continue
        trouves = set()
        if "recursesubdirs" in entree.lower():
            for rac, _d, fichiers in os.walk(base):
                for nom in fichiers:
                    trouves.add(os.path.join(rac, nom))
        else:
            for chemin in glob.glob(motif):
                if os.path.isfile(chemin):
                    trouves.add(chemin)
        exclus = _exclus(entree)
        for chemin in trouves:
            if _exclu(os.path.relpath(chemin, base), exclus):
                continue
            installes.add(os.path.relpath(chemin, racine))
    return installes


# ======================================================= lecture
if not os.path.isfile(ISS):
    print("ÉCHEC : avastack.iss introuvable :", ISS)
    sys.exit(1)

installes = selectionnes(RACINE, ISS)

attendus = set()                                   # package avastack/, sans dev
for rac, dossiers, fichiers in os.walk(os.path.join(RACINE, "avastack")):
    dossiers[:] = [d for d in dossiers if d != "__pycache__"]
    for nom in fichiers:
        if not nom.endswith((".pyc", ".pyi")):
            attendus.add(os.path.relpath(os.path.join(rac, nom), RACINE))

# ======================================================= [1] couverture
print("[1] couverture : tout le package avastack/ est selectionne par [Files]")
manquants = sorted(attendus - installes)
verifie(not manquants,
        "aucun fichier du package n'est oublie (%d attendus)" % len(attendus))
for m in manquants[:12]:
    print("        manquant : " + m)

for sous in ("core", "ui/widgets", "ui/panels"):
    attendu = os.path.join("avastack", *sous.split("/"), "__init__.py")
    verifie(attendu in installes, "sous-paquet selectionne : " + sous)

# ======================================================= [2] proprete
print("[2] proprete : ni __pycache__, ni .pyc, ni .pyi")
pollues = sorted(a for a in installes
                 if "__pycache__" in a or a.endswith((".pyc", ".pyi")))
verifie(not pollues,
        "aucun fichier de DEV embarque (%d fichiers selectionnes)"
        % len(installes))

# ======================================================= [3] donnees
print("[3] donnees : catalogue embarque selectionne")
bz2 = [a for a in installes if a.endswith(".bz2")]
verifie(any(a.startswith(os.path.join("avastack", "catalogues", "data"))
            for a in bz2),
        "le catalogue embarque (*.bz2) est selectionne : %s" % (bz2 or "AUCUN"))

# ======================================================= [4] compilation Inno
print("[4] compilation d'avastack.iss (si ISCC est present)")
issc = None
for cand in (os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                          "Inno Setup 6", "ISCC.exe"),
             r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
             r"C:\Program Files\Inno Setup 6\ISCC.exe"):
    if cand and os.path.isfile(cand):
        issc = cand
        break
if issc is None:
    print("  (ISCC introuvable : section [4] non verifiee ici)")
else:
    with open(os.path.join(RACINE, "avastack", "__init__.py"),
              encoding="utf-8") as f:
        m = re.search(r'^AVASTACK_VERSION\s*=\s*"([^"]+)"', f.read(), re.M)
    version = m.group(1) if m else "0"
    sortie = tempfile.mkdtemp(prefix="banc118_")
    r = subprocess.run([issc, "/DAppVersion=" + version, "/O" + sortie, ISS],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=os.path.dirname(ISS))
    verifie(r.returncode == 0, "avastack.iss compile (code 0)")
    if r.returncode != 0:
        print(((r.stdout or "") + (r.stderr or ""))[-900:])
    else:
        exe = os.path.join(sortie, "avastack-setup-%s.exe" % version)
        verifie(os.path.isfile(exe),
                "l'artefact est produit : %s" % os.path.basename(exe))
    shutil.rmtree(sortie, ignore_errors=True)

print("\nBANC JALON 118 (contenu installateur Inno) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)


