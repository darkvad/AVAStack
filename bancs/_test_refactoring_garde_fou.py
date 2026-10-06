# -*- coding: utf-8 -*-
"""BANC GARDE-FOU du chantier de REFACTORING (jalon 100) — LA référence.

Chantier (décision d'architecture du 06/10/2026, roadmap des jalons 100→110
dans AVANCEMENT.md) : découper `avastack/ui/app.py` (objet monolithique) en
modules cohérents et poser un typage progressif — SANS AUCUN changement de
comportement (rendu identique AU BIT). Ce banc est REJOUÉ À CHAQUE JALON :
toute extraction qui casse l'API ou le rendu le fait passer au ROUGE.

Il verrouille quatre choses :
  [1] LA SYNTAXE de TOUS les `.py` du dépôt (compilation à blanc) ;
  [2] L'INVENTAIRE DES SYMBOLES PUBLICS de `app.py`. Surface publique =
      noms DÉFINIS au niveau module ∪ noms importés DU PAQUET `avastack`
      (les ré-exports). C'est STABLE sous « extraire puis ré-importer » (le
      symbole reste offert par `avastack.ui.app.X`) et ROUGE si une extraction
      fait DISPARAÎTRE un symbole public (vraie rupture d'API). Un jalon qui
      change légitimement cette surface met à jour la constante ci-dessous :
      cette mise à jour est VOLONTAIRE et relue, jamais subie ;
  [3] LE HASH SHA-256 d'un EMPILEMENT SIMULÉ déterministe (kappa, winsorized,
      kappa-RGB) : le rendu figé AU BIT — la garantie « zéro régression » ;
  [4] `pyright` 0 ERREUR sur la LISTE BLANCHE des fichiers typés (elle grandit
      à chaque jalon ; l'étape est IGNORÉE proprement tant que pyright n'est
      pas installé — pip install -r requirements-dev.txt).

Exécution (interpréteur du venv) :
    python bancs/_test_refactoring_garde_fou.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
RACINE = None
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        RACINE = _d_banc
        _sys_banc.path.insert(0, str(_d_banc))
        break

import ast
import hashlib
import os
import shutil
import subprocess
import sys

import numpy as np

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# ============================================================================
# CONSTANTES FIGÉES — mises à jour VOLONTAIREMENT, à chaque jalon qui le
# justifie (voir le mode d'emploi dans la docstring et AVANCEMENT.md).
# ============================================================================

# [2] Surface publique de `avastack/ui/app.py` (jalon 100). Union :
#   - les 13 noms DÉFINIS au niveau module : 10 constantes, la classe `App`
#     et les 2 fonctions `activer_fenetre`, `main` ;
#   - les noms importés DU PAQUET `avastack` (ré-exports) — l'API que le reste
#     du projet et les bancs consomment via `avastack.ui.app.<nom>`.
# NE figurent PAS les imports de la bibliothèque standard / tierce (os, np,
# cv2, tkinter, PIL…) : ce sont des détails d'implémentation dont le lieu
# d'import change librement pendant le refactoring.
SURFACE_PUBLIQUE = frozenset((
    "AVASTACK_VERSION", "App", "ArchiveFrames", "CAMERAS_PILOTEES", "CFA_MODE",
    "COMPOSITIONS", "CONFIG", "Calibrator", "CompositeStacker",
    "DEFAULT_CMD_BXT", "DEFAULT_CMD_GRAXPERT", "DEFAULT_CMD_GRAXPERT_DN",
    "DisplayProcessor", "FILTRES_ROUE", "FLU_MIN_REF", "FLU_NB_FRAC",
    "FWHM_ABS_MIN", "FWHM_MARGE", "FolderCamera", "IS_MACOS", "IS_WINDOWS",
    "LiveStacker", "MODES_L", "MultiFolderCamera", "OpenCVCamera",
    "PlayerOneCamera", "QHYCamera", "RESTACK_CADENCE", "RESTACK_HIST_MAX",
    "RESTACK_MARGE", "RESTACK_MIN_FRAMES", "ROLES", "SCORE_MAX_ETOILES",
    "SOURCES", "SVBonyCamera", "SimulatedCamera", "StarAligner",
    "TouptekCamera", "ZWOASICamera", "activer_fenetre", "align_mod",
    "annoter_mod", "astro_mod", "auto_unflip", "borner_lineaire", "cat_mod",
    "commande_avec_strength", "composition_mod", "composition_pour_roles",
    "couleurs_mod", "delais", "denoiser_local", "detecter_outils",
    "display_mod", "extraire_canal", "find_output", "gx_live", "journal",
    "lire_filtre_fits", "lister_via_sous_processus", "load_image", "main",
    "nettete_live", "photo_mod", "reactivite_mod", "ressources",
    "role_de_filtre", "roles_de", "sauver_config", "save_image",
    "seeing_live", "spcc_mod", "tracer_evt", "travail", "veralux_moteur",
))

# [2] Noms CONSOMMÉS par d'autres fichiers (`AVAStack.py`, les bancs) : on
# vérifie qu'ils sont RÉELLEMENT résolvables sur `avastack.ui.app` (pas
# seulement présents dans l'AST) — la preuve que l'API tient à l'exécution.
API_CONSOMMEE = ("App", "main", "CONFIG", "sauver_config", "ArchiveFrames",
                 "filedialog", "messagebox")

# [3] Empreintes SHA-256 du DERNIER octet d'un empilement SIMULÉ déterministe
# (graine fixée). Le rendu du cœur d'empilement est figé ici : tout changement
# de comportement au bit les fait diverger.
HASH_KAPPA = "d37b86241c4a7bc404a7aee98f6bbf23edba7d38366d6bf7ebdb8c7c36c04dc3"
HASH_WINSORIZED = "6b6d1bb7d884913a79db0023f43bb6759b17c52499247e9311ae75b86b0f9d8e"
HASH_KAPPA_RGB = "a4ece0a2eb47a24dfd603071a18e5b1a9f590e818a5022c369a2475a4565682e"

# [4] LISTE BLANCHE des fichiers typés (chemins RELATIFS à la racine). Elle
# grandit à chaque jalon de typage (101 : compat/config/delais/journal/
# ressources/travail/siril_ini ; puis les modules extraits…). Tant qu'elle est
# vide, l'étape pyright est un no-op documenté.
FICHIERS_TYPES = ()


# ============================================================================
# [1] SYNTAXE DE TOUS LES .py
# ============================================================================
print("[1] Syntaxe de tous les .py du dépôt")

# Dossiers ignorés : environnement virtuel, caches, sorties de build des
# installateurs, artefacts de diagnostics.
_EXCLUS = {"venv", ".git", "__pycache__", "node_modules", ".continue",
           "output", "build_frozen"}


def _a_ignorer(chemin_relatif):
    for partie in chemin_relatif.parts:
        if partie in _EXCLUS or partie.startswith(("avastack_", "astrolivestack_")):
            return True
    return False


_fichiers_py = []
for _p in RACINE.rglob("*.py"):
    _rel = _p.relative_to(RACINE)
    if not _a_ignorer(_rel):
        _fichiers_py.append(_p)
_fichiers_py.sort()

_echecs_syntaxe = []
for _p in _fichiers_py:
    try:
        # utf-8-sig : certains fichiers portent un BOM, que compile() refuse.
        compile(_p.read_text(encoding="utf-8-sig"), str(_p), "exec")
    except SyntaxError as _e:
        _echecs_syntaxe.append((_p.relative_to(RACINE), _e))
for _rel, _e in _echecs_syntaxe:
    print("   SYNTAXE KO  %s : %s" % (_rel, _e))
verifie(not _echecs_syntaxe,
        "syntaxe : %d fichier(s) .py compilé(s), %d erreur(s)"
        % (len(_fichiers_py), len(_echecs_syntaxe)))



# ============================================================================
# [2] INVENTAIRE DES SYMBOLES PUBLICS DE app.py
# ============================================================================
print("[2] Inventaire des symboles publics de avastack/ui/app.py")


def _surface_publique(chemin):
    """Surface publique d'un module : noms DÉFINIS au niveau module (classes,
    fonctions, affectations) ∪ noms importés DU PAQUET `avastack` — les noms
    privés (préfixe « _ ») et les imports stdlib/tiers sont écartés. On
    descend dans les blocs de contrôle (if/try) sans entrer dans les corps de
    fonction/classe."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8-sig"))
    definis, importes = set(), set()

    def parcourir(noeuds):
        for n in noeuds:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
                definis.add(n.name)
            elif isinstance(n, ast.Assign):
                for tg in n.targets:
                    for nn in ast.walk(tg):
                        if isinstance(nn, ast.Name):
                            definis.add(nn.id)
            elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                definis.add(n.target.id)
            elif isinstance(n, ast.ImportFrom):
                mod = n.module or ""
                if n.level > 0 or mod.startswith("avastack"):
                    for a in n.names:
                        importes.add(a.asname or a.name)
            elif isinstance(n, (ast.Try, ast.If)):
                parcourir(n.body)
                parcourir(getattr(n, "orelse", []))
                for h in getattr(n, "handlers", []):
                    parcourir(h.body)

    parcourir(arbre.body)
    return {x for x in (definis | importes) if not x.startswith("_")}


_chemin_app = RACINE / "avastack" / "ui" / "app.py"
_surface = _surface_publique(_chemin_app)
_manquants = sorted(SURFACE_PUBLIQUE - _surface)
_nouveaux = sorted(_surface - SURFACE_PUBLIQUE)
if _manquants:
    print("   DISPARUS (rupture d'API ?) : " + ", ".join(_manquants))
if _nouveaux:
    print("   APPARUS (à figer si voulu)  : " + ", ".join(_nouveaux))
verifie(not _manquants and not _nouveaux,
        "surface publique identique : %d symbole(s) figé(s), aucun écart"
        % len(SURFACE_PUBLIQUE))

# Preuve d'exécution : les noms consommés par le projet se RÉSOLVENT vraiment.
import avastack.ui.app as _app                                    # noqa: E402
_absents = [nom for nom in API_CONSOMMEE if not hasattr(_app, nom)]
verifie(not _absents,
        "API consommée résolvable sur avastack.ui.app (App, main, CONFIG, "
        "sauver_config, ArchiveFrames, filedialog, messagebox)"
        + (" — ABSENTS : " + ", ".join(_absents) if _absents else ""))



# ============================================================================
# [3] HASH D'UN EMPILEMENT SIMULÉ (rendu figé AU BIT)
# ============================================================================
print("[3] Hash d'un empilement simulé (kappa / winsorized / kappa-RGB)")
from avastack.processing.stacking import LiveStacker                # noqa: E402


def _empreinte(a):
    """SHA-256 des octets bruts du tableau (C-contigu) — « identique AU BIT »
    se prouve, ne se suppose pas."""
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


_rng = np.random.default_rng(100)
_frames = [_rng.normal(0.2, 0.02, (48, 64)).astype(np.float32)
           for _ in range(12)]
_st = LiveStacker((48, 64), k=3.0, method="kappa", window=8)
for _f in _frames:
    _st.add(_f)
_h_kappa = _empreinte(_st.mean())
verifie(_h_kappa == HASH_KAPPA,
        "empilement kappa (mono) inchangé au bit"
        + ("" if _h_kappa == HASH_KAPPA else "  — obtenu " + _h_kappa))

_st = LiveStacker((48, 64), k=3.0, method="winsorized", window=8)
for _f in _frames:
    _st.add(_f)
_h_wins = _empreinte(_st.mean())
verifie(_h_wins == HASH_WINSORIZED,
        "empilement winsorized (mono) inchangé au bit"
        + ("" if _h_wins == HASH_WINSORIZED else "  — obtenu " + _h_wins))

_rng2 = np.random.default_rng(101)
_frames_rgb = [_rng2.normal(0.2, 0.02, (32, 40, 3)).astype(np.float32)
               for _ in range(10)]
_st = LiveStacker((32, 40, 3), k=3.0, method="kappa", window=8)
for _f in _frames_rgb:
    _st.add(_f)
_h_rgb = _empreinte(_st.mean())
verifie(_h_rgb == HASH_KAPPA_RGB,
        "empilement kappa (RGB) inchangé au bit"
        + ("" if _h_rgb == HASH_KAPPA_RGB else "  — obtenu " + _h_rgb))


# ============================================================================
# [4] PYRIGHT — 0 ERREUR SUR LA LISTE BLANCHE DES FICHIERS TYPÉS
# ============================================================================
print("[4] pyright — 0 erreur sur la liste blanche des fichiers typés")


def _trouver_pyright():
    """→ commande pyright (liste d'arguments), ou None s'il n'est pas installé.

    Ordre : script console à côté de l'interpréteur (venv/Scripts|bin), puis
    le PATH, puis le module Python `pyright`."""
    dossier = os.path.dirname(sys.executable)
    for nom in ("pyright.exe", "pyright.cmd", "pyright.bat", "pyright"):
        candidat = os.path.join(dossier, nom)
        if os.path.isfile(candidat):
            return [candidat]
    trouve = shutil.which("pyright")
    if trouve:
        return [trouve]
    try:
        import pyright                                            # noqa: F401
        return [sys.executable, "-m", "pyright"]
    except Exception:
        return None


_pyright = _trouver_pyright()
if _pyright is None:
    print("  IGNORÉ (pyright non installé — pip install -r requirements-dev.txt)")
elif not FICHIERS_TYPES:
    print("  IGNORÉ (liste blanche vide — aucun fichier typé à ce stade)")
else:
    _cmd = _pyright + ["--outputjson"] + list(FICHIERS_TYPES)
    _res = subprocess.run(_cmd, cwd=str(RACINE), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    _nb = None
    try:
        import json
        _nb = int(json.loads(_res.stdout)["summary"]["errorCount"])
    except Exception:
        _nb = None
    if _nb is None:                       # sortie non-JSON : repli sur le code
        verifie(_res.returncode == 0,
                "pyright : code de retour %d (sortie non interprétable)"
                % _res.returncode)
        if _res.returncode != 0:
            print(_res.stdout[-2000:])
            print(_res.stderr[-1000:])
    else:
        verifie(_nb == 0,
                "pyright : %d erreur(s) sur %d fichier(s) typé(s)"
                % (_nb, len(FICHIERS_TYPES)))


# ============================================================================
print()
print("GARDE-FOU REFACTORING (jalon 100) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS À CORRIGER ❌")
sys.exit(0 if ok else 1)

