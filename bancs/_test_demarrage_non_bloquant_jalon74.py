# -*- coding: utf-8 -*-
"""Banc du jalon 74 : LE DÉMARRAGE NE PEUT PLUS SE BLOQUER (NAS, montage réseau).

Constat déclencheur (Alain, 27/09/2026, v2.38.10 sur Linux) :
    « cette version ne se lance pas (ni depuis application, ni depuis ligne de
    commande) — pas d'enregistrement dans le journal. En ligne de commande ça
    affiche juste la version. »

CAUSE MESURÉE : ses dossiers de couches R/G/B sont sur un **NAS** (dans
config.json) et `nftables` filtre ce NAS ; un `stat`/`listdir` sur un montage
réseau injoignable **attend le montage indéfiniment**. L'inspection ayant lieu
AVANT l'affichage, l'application ne s'ouvrait jamais — et comme la première
ligne du journal était écrite APRÈS la mesure de l'environnement, il n'y avait
même pas de trace. Contre-épreuve d'Alain : nftables arrêté → la même version
démarre.

Ce banc vérifie, SANS aucun réseau ni NAS :
  [1] `delais.borne` : résultat rapide, DÉFAUT quand ça bloque (chronométré),
      jamais d'exception ;
  [2] `journal.etape` : la « miette de pain » qui NOMME l'étape bloquée ;
  [3] le point d'entrée : la PREMIÈRE ligne de journal est écrite SANS accès
      disque, la mesure d'environnement est bornée, et l'application continue
      (avec un message « NON MESURÉ ») — plus jamais de journal vide ;
  [4] l'interface : `App(root)` se construit MALGRÉ des sondes qui dorment
      30 s (dossier de travail, détection d'outils, catalogues), et la ligne
      l'annonce honnêtement ;
  [5] montages RÉSEAU : recensés, écartés des balayages de détection (racines et
      PATH) — c'est ce qui évite de réveiller le NAS ;
  [6] la détection des outils ne tourne PLUS à l'import : elle est disponible et
      fonctionnelle quand on l'appelle (après l'affichage).

Exécution : python bancs/_test_demarrage_non_bloquant_jalon74.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent sous bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time

import avastack
from avastack import config as config_mod
from avastack import delais
from avastack import journal
from avastack import travail
from avastack.external import detection
from avastack.external import live as gx_live

if hasattr(sys.stdout, "reconfigure"):      # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


TMP = tempfile.mkdtemp(prefix="banc74_")
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL = os.path.join(TMP, "journal.txt")

# Bac à sable : journal, configuration et écran de départ DANS le temporaire.
_CONFIG_PREVU = config_mod.CONFIG
_DOSSIER_CONFIG = config_mod.dossier_config
config_mod.dossier_config = lambda: TMP
config_mod.CONFIG = {}
_DOSSIER_JOURNAL = journal.dossier_journal
journal.dossier_journal = lambda: TMP


def lire_journal():
    try:
        with open(JOURNAL, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def dormir(secondes):
    """Mouchard : simule une sonde disque BLOQUÉE (NAS injoignable)."""
    time.sleep(secondes)
    return "jamais atteint"


# ==================================================== [1] delais.borne
print("[1] delais.borne : rendre la main, toujours")
t0 = time.time()
valeur, abouti = delais.borne(lambda: 42, "défaut", 1.0)
verifie(valeur == 42 and abouti, "résultat rendu dès qu'il est prêt")

t0 = time.time()
valeur, abouti = delais.borne(lambda: dormir(30), "défaut", 0.5)
duree = time.time() - t0
verifie(valeur == "défaut" and abouti is False and duree < 3.0,
        "sonde BLOQUÉE : abandonnée après %.2f s (bornée à 0,5 s)" % duree)


def _boom():
    raise ValueError("sonde en échec")


valeur, abouti = delais.borne(_boom, "défaut", 1.0)
verifie(valeur == "défaut" and abouti is True,
        "sonde en ÉCHEC : aucune exception ne remonte, le défaut est rendu")


# ==================================================== [2] journal.etape
print("[2] journal.etape : nommer l'étape pour qu'un blocage laisse une trace")
journal.ecrire("")           # fichier créé
journal.etape("détection des outils", "accès disque possible")
verifie("étape — détection des outils — accès disque possible" in lire_journal(),
        "la miette de pain est écrite AVANT l'étape (c'est elle qui nomme le blocage)")


# ================================ [3] point d'entrée : journal AVANT mesure
print("[3] AVAStack._demarrer : 1re ligne écrite AVANT toute mesure")
_spec = importlib.util.spec_from_file_location(
    "avastack_entree_banc74", os.path.join(RACINE, "AVAStack.py"))
entree = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(entree)
from avastack.ui import app as ui            # noqa: E402

_trace_prevu = journal.trace_env
_delai_prevu = delais.DELAI_DEFAUT
_main_prevu = ui.main
journal.trace_env = lambda: dormir(30)        # mesure d'environnement BLOQUÉE
delais.DELAI_DEFAUT = 0.5                     # borne réduite (banc rapide)
appels = []
ui.main = lambda: appels.append("main")
try:
    t0 = time.time()
    entree._demarrer()
    duree = time.time() - t0
finally:
    ui.main = _main_prevu
    journal.trace_env = _trace_prevu
    delais.DELAI_DEFAUT = _delai_prevu
contenu = lire_journal()
verifie("AVAStack " + avastack.AVASTACK_VERSION in contenu
        and "argv=" in contenu,
        "1re ligne écrite SANS accès disque (version, python, argv)")
verifie("environnement NON MESURÉ" in contenu,
        "mesure bloquée : l'application CONTINUE et le DIT")
verifie(appels == ["main"] and duree < 5.0,
        "_demarrer rend la main en %.2f s malgré la sonde bloquée" % duree)


# ============ [4] l'interface s'ouvre MALGRÉ des sondes qui dorment 30 s
print("[4] App(root) malgré trois sondes disque BLOQUÉES (30 s)")
import tkinter as tk                          # noqa: E402

_travail_prevu = travail.dossier_travail
_outil_prevu = gx_live.outil_manquant
_cat_prevu = ui.cat_mod.dossier_catalogues
_sauve_conf = ui.sauver_config
_sauve_cfg = ui.CONFIG
travail.dossier_travail = lambda: dormir(30)
gx_live.outil_manquant = lambda *a, **k: dormir(30)
ui.cat_mod.dossier_catalogues = lambda *a, **k: dormir(30)
delais.DELAI_DEFAUT = 0.5
ui.CONFIG = {}
ui.sauver_config = lambda *a, **k: None
root = tk.Tk()
root.withdraw()
try:
    t0 = time.time()
    application = ui.App(root)
    duree = time.time() - t0
    root.update()
finally:
    ui.sauver_config = _sauve_conf
verifie(duree < 8.0 and root.winfo_exists(),
        "App(root) construit en %.2f s MALGRÉ trois sondes bloquées" % duree)
_fin = time.time() + 15.0
_ligne = ""
while time.time() < _fin:
    application._tick()
    root.update()
    _ligne = application.lbl_travail.cget("text")
    if "non mesuré" in _ligne.lower() or "ILLISIBLE" in _ligne:
        break
    time.sleep(0.05)
verifie("non mesuré" in _ligne.lower() or "ILLISIBLE" in _ligne,
        "la ligne de travail DIT que la mesure n'a pas abouti : « %s »"
        % _ligne[:64])
_etat_grav = application.lbl_etat_graxpert.cget("text")
verifie("mesure en cours" in _etat_grav or "⚠" in _etat_grav,
        "l'état des outils reste HONNÊTE (pas d'ancien texte trompeur) : « %s »"
        % _etat_grav[:52])
travail.dossier_travail = _travail_prevu
gx_live.outil_manquant = _outil_prevu
ui.cat_mod.dossier_catalogues = _cat_prevu
ui.CONFIG = _sauve_cfg
delais.DELAI_DEFAUT = _delai_prevu
root.destroy()


# ==================== [5] montages RÉSEAU : recensés et écartés des balayages
print("[5] montages réseau (NAS) : recensés, jamais balayés")
verifie({"nfs", "nfs4", "cifs", "sshfs", "autofs"} <= set(travail.TYPES_RESEAU),
        "les types réseau courants sont connus")
_montages_prevus = travail.points_de_montage
_win_prevu, _mac_prevu = travail.IS_WINDOWS, travail.IS_MACOS
travail.points_de_montage = lambda: [("/", "ext4"), ("/mnt/nas", "nfs4"),
                                     ("/tmp", "tmpfs")]
# `type_systeme` interroge le type de montage SOUS LINUX seulement : pour
# éprouver sa logique depuis n'importe quel OS, on simule Linux (les constantes
# sont lues à l'appel, donc patchables) — c'est la même méthode que les bancs de
# détection d'outils.
travail.IS_WINDOWS = travail.IS_MACOS = False
try:
    _nas = travail.sur_montage_reseau("/mnt/nas/brutes/R")
    _local = travail.sur_montage_reseau("/home/alain/brutes")
    _type = travail.type_systeme("/mnt/nas/brutes/R")
    _tmp = travail.est_tmpfs("/tmp/x")
    _tmp_nas = travail.est_tmpfs("/mnt/nas/x")
finally:
    travail.IS_WINDOWS, travail.IS_MACOS = _win_prevu, _mac_prevu
verifie(_nas and not _local and _type == "nfs4",
        "sur_montage_reseau : dossier du NAS reconnu (point de montage le plus long)")
verifie(_tmp and not _tmp_nas,
        "est_tmpfs continue de fonctionner (même logique de point de montage)")
_reseau_prevu = travail.sur_montage_reseau
travail.sur_montage_reseau = lambda p: "nas" in str(p).lower()
_lap_prevu = os.environ.get("LOCALAPPDATA")
_path_prevu = os.environ.get("PATH")
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "nas-local")
os.environ["PATH"] = os.pathsep.join([os.path.join(TMP, "local-bin"),
                                      os.path.join(TMP, "nas-bin")])
try:
    racines = detection._racines()
    chemin_sain = detection._path_local()
finally:
    travail.sur_montage_reseau = _reseau_prevu
    travail.points_de_montage = _montages_prevus
    if _lap_prevu is None:
        os.environ.pop("LOCALAPPDATA", None)
    else:
        os.environ["LOCALAPPDATA"] = _lap_prevu
    if _path_prevu is None:
        os.environ.pop("PATH", None)
    else:
        os.environ["PATH"] = _path_prevu
verifie(all("nas" not in str(r).lower() for r in racines),
        "aucune racine RÉSEAU dans les racines de détection : %s"
        % (racines[:3],))
verifie(chemin_sain is not None and "nas" not in chemin_sain.lower()
        and "local-bin" in chemin_sain,
        "le PATH de recherche d'exécutable est privé de ses dossiers réseau")


# ============ [6] la détection ne tourne plus à l'import (mesuré en enfant)
print("[6] détection des outils : RIEN à l'import, tout à l'appel (sous-processus)")
_code = "\n".join([
    "import sys",
    "sys.path.insert(0, %r)" % RACINE,
    "import shutil, glob",
    "appels = []",
    "shutil.which = lambda *a, **k: (appels.append('which'), None)[1]",
    "glob.glob = lambda *a, **k: (appels.append('glob'), [])[1]",
    "from avastack.external import detection",
    "print('appels_import', len(appels))",
    "detection.detecter_outils()",
    "print('appels_appel', len(appels) > 0)",
])
enfant = subprocess.run([sys.executable, "-c", _code], capture_output=True,
                        encoding="utf-8", errors="replace", timeout=120)
_sortie = (enfant.stdout or "") + (enfant.stderr or "")
verifie("appels_import 0" in _sortie,
        "import de la détection : AUCUN `which`/`glob` (zéro accès disque)")
verifie("appels_appel True" in _sortie,
        "appelée explicitement, la détection retrouve ses sondes (which/glob)")


# --- fin du banc : tout est remis en place
journal.dossier_journal = _DOSSIER_JOURNAL
config_mod.CONFIG = _CONFIG_PREVU
config_mod.dossier_config = _DOSSIER_CONFIG
shutil.rmtree(TMP, ignore_errors=True)

print("\nBANC JALON 74 (démarrage non bloquant) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)
