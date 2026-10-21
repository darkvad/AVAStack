# -*- coding: utf-8 -*-
"""Banc — PERSISTANCE DES MAÎTRES DARK/FLAT (v2.98.7, 21/10/2026).

POURQUOI CE BANC. `_load_dark` / `_load_flat` chargeaient l'image en mémoire
sans RIEN écrire dans `config.json` : les maîtres étaient donc à re-sélectionner
à CHAQUE session (défaut trouvé pendant l'audit mémoire du 21/10/2026). Le
correctif persiste les CHEMINS et les restaure au démarrage — et la
restauration doit se faire HORS du fil d'interface (leçon v2.98.4 : un maître
peut vivre sur un partage réseau ; une lecture pendant la construction de la
fenêtre empêcherait l'application de s'ouvrir).

CE QUE CE BANC VERROUILLE
  [1] Fonctions PURES : `cles_persistees` (unique + par rôle, un maître absent
      ne produit AUCUNE clé) et `lire_cles_persistees` (aller-retour exact,
      ordre stable, entrées douteuses IGNORÉES) ;
  [2] `Calibrator.poser_dark`/`poser_flat` : poser un maître DÉJÀ lu ne fait
      AUCUNE I/O, l'état et l'image calibrée sont IDENTIQUES AU BIT à ceux d'un
      chargement par fichier ;
  [3] Interface RÉELLE (Tk, config vierge simulée) : chaque geste PERSISTE les
      chemins (dark unique, flat par rôle) ; « Effacer la calibration » les
      RETIRE ; les clés SURVIVENT à la fermeture (le « sauver » de fin réécrit
      la config entière) ;
  [4] RESTAURATION : une SECONDE session relit la config écrite par la première
      et retrouve ses maîtres — images identiques AU BIT, sources et libellés
      justes, ligne d'état qui le dit ;
  [5] Maître INTROUVABLE : aucun échec, les autres se chargent quand même, et
      l'échec est DIT (ligne d'état + journal) ;
  [6] I/O HORS du fil d'interface : pendant `_restaurer_calib_differe()`
      (fil principal) **0 lecture de fichier** ; toutes les lectures ont lieu
      dans un fil DÉMON.

Exécution : python bancs/_test_calib_persistance.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import os
import shutil
import sys
import tempfile
import threading
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
from avastack.processing import calibration as calib_mod
from avastack.processing.calibration import Calibrator
from avastack.images import save_image

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CFA_MODE_AVANT = images.CFA_MODE
images.CFA_MODE = "Non"                  # brutes mono dans ce test

H, W = 40, 52
ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK  " if cond else "  ÉCHEC ") + msg)


rac = tempfile.mkdtemp(prefix="banc_calib_persistance_")

# Maîtres de test : un jeu « unique » et un jeu par RÔLE (Ha).
P_DU = os.path.join(rac, "dark_unique.fit")
P_FU = os.path.join(rac, "flat_unique.fit")
P_DH = os.path.join(rac, "dark_Ha.fit")
P_FH = os.path.join(rac, "flat_Ha.fit")
P_ABSENT = os.path.join(rac, "n_existe_pas.fit")
IMG_DU = np.full((H, W), 0.02, np.float32)
IMG_FU = np.full((H, W), 0.9, np.float32)
IMG_DH = np.full((H, W), 0.05, np.float32)
IMG_FH = np.full((H, W), 1.1, np.float32)
for _p, _a in ((P_DU, IMG_DU), (P_FU, IMG_FU), (P_DH, IMG_DH), (P_FH, IMG_FH)):
    save_image(_p, _a)
FRAME = np.full((H, W), 0.5, np.float32)

# ============================================================================
# [1] FONCTIONS PURES
# ============================================================================
print("=" * 78)
print("[1] Fonctions PURES : cles_persistees / lire_cles_persistees")
print("=" * 78)

cal = Calibrator()
verifie(calib_mod.cles_persistees(cal) == {},
        "calibrateur vide : aucune clé (un maître ABSENT n'en produit pas — "
        "l'appelant doit donc retirer les anciennes)")
cal.load_dark(P_DU)
cal.load_flat(P_FU)
cal.load_dark(P_DH, role="Ha")
cal.load_flat(P_FH, role="Ha")
cles = calib_mod.cles_persistees(cal)
verifie(cles == {"calib_dark_unique": P_DU, "calib_flat_unique": P_FU,
                 "calib_dark_Ha": P_DH, "calib_flat_Ha": P_FH},
        f"unique ET par rôle : 4 clés exactes — {sorted(cles)}")
lues = calib_mod.lire_cles_persistees(cles)
verifie(sorted(lues) == sorted([("dark", "unique", P_DU),
                                ("flat", "unique", P_FU),
                                ("dark", "Ha", P_DH),
                                ("flat", "Ha", P_FH)]),
        "aller-retour : la lecture rend EXACTEMENT les 4 (famille, cible, chemin)")
verifie(calib_mod.lire_cles_persistees(cles) == lues,
        "ordre STABLE : deux lectures donnent la même liste")
# Tolérance : rien de tout cela ne doit lever, ni produire de faux maître.
bordel = {"calib_dark_unique": "", "calib_flat_unique": None,
          "calib_dark_": P_DU, "calib_dark": P_DU, "calib_darkX": P_DU,
          "calib_dark_Ha": 42, "calib_dark_L": P_DU, "calib_flat_R": P_FU,
          "dossier": "C:/un/chemin", "compo_role_0": "R"}
lues_b = calib_mod.lire_cles_persistees(bordel)
verifie(lues_b == [("dark", "L", P_DU), ("flat", "R", P_FU)],
        "entrées douteuses IGNORÉES (vide, None, 42, sans cible, hors préfixe) "
        f"— restent {lues_b}")
verifie(calib_mod.lire_cles_persistees({}) == [],
        "config sans maître : liste vide (aucune restauration lancée)")


# ============================================================================
# [2] CALIBRATOR : POSER UN MAÎTRE DÉJÀ LU
# ============================================================================
print("=" * 78)
print("[2] Calibrator : poser un maître DÉJÀ lu (zéro I/O) et apply() inchangé")
print("=" * 78)

_espion_lectures = []
_vrai_load_calib = calib_mod.load_image


def _espion_load_calib(chemin):
    _espion_lectures.append(chemin)
    return _vrai_load_calib(chemin)


calib_mod.load_image = _espion_load_calib
c_pose = Calibrator()
c_pose.poser_dark(IMG_DU, P_DU)
c_pose.poser_flat(IMG_FU, P_FU)
c_pose.poser_dark(IMG_DH, P_DH, role="Ha")
c_pose.poser_flat(IMG_FH, P_FH, role="Ha")
calib_mod.load_image = _vrai_load_calib
verifie(not _espion_lectures,
        "poser_dark/poser_flat : AUCUNE lecture de fichier (0 appel espionné)")

c_charge = Calibrator()
c_charge.load_dark(P_DU)
c_charge.load_flat(P_FU)
c_charge.load_dark(P_DH, role="Ha")
c_charge.load_flat(P_FH, role="Ha")
verifie(np.array_equal(c_pose.dark, c_charge.dark)
        and np.array_equal(c_pose.flat, c_charge.flat)
        and np.array_equal(c_pose.darks["Ha"], c_charge.darks["Ha"])
        and np.array_equal(c_pose.flats["Ha"], c_charge.flats["Ha"]),
        "état posé IDENTIQUE AU BIT à l'état chargé par fichier")
verifie(c_pose.dark_source == P_DU and c_pose.flat_source == P_FU
        and c_pose.darks_sources == {"Ha": P_DH}
        and c_pose.flats_sources == {"Ha": P_FH},
        "sources notées comme au chargement (libellés de l'interface)")
verifie(np.array_equal(c_pose.apply(FRAME), c_charge.apply(FRAME))
        and np.array_equal(c_pose.apply(FRAME, role="Ha"),
                           c_charge.apply(FRAME, role="Ha")),
        "apply() : image calibrée identique AU BIT (unique ET par rôle)")


# ============================================================================
# [3] INTERFACE RÉELLE — CHAQUE GESTE PERSISTE
# ============================================================================
print("=" * 78)
print("[3] Interface réelle : les gestes PERSISTENT les chemins (config simulée)")
print("=" * 78)

import avastack.ui.app as ui

root1 = tk.Tk()
root1.withdraw()
# Test HERMÉTIQUE (piège config.json) : config vierge SIMULÉE et sauvegarde
# interceptée — le vrai fichier n'est jamais lu ni écrit.
ui.CONFIG = {}
_ecrit = {}


def _faux_sauver(d):
    _ecrit.clear()
    _ecrit.update(dict(d))


ui.sauver_config = _faux_sauver
app1 = ui.App(root1)

# --- dark UNIQUE (hors composition : aucune boîte de dialogue)
ui.filedialog.askopenfilename = lambda **k: P_DU
app1._load_dark()
verifie(ui.CONFIG.get("calib_dark_unique") == P_DU
        and _ecrit.get("calib_dark_unique") == P_DU,
        "dark unique chargé → chemin PERSISTÉ (CONFIG + config.json écrit)")
verifie(app1.calib.dark is not None,
        "…et le maître est bien en mémoire (comportement d'avant inchangé)")

# --- flat PAR RÔLE (composition : la couche se choisit au clic)
app1.var_source.set("Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
app1._maj_visibilite_cadres()
root1.update_idletasks()


def _repond(valeur):
    def _go():
        app1._dlg_var.set(valeur)
        app1._dlg_ok()
    return _go


ui.filedialog.askopenfilename = lambda **k: P_FH
root1.after(200, _repond("Ha"))
app1._load_flat()
verifie(ui.CONFIG.get("calib_flat_Ha") == P_FH
        and ui.CONFIG.get("calib_dark_unique") == P_DU,
        "flat « Ha » → clé PAR RÔLE persistée, le dark unique reste")
verifie(app1.calib.flats_sources == {"Ha": P_FH},
        "…et rangé dans la couche choisie")

# --- « Effacer la calibration » : les clés partent AUSSI de la config
app1._clear_calib()
_reste = [k for k in ui.CONFIG if k.startswith(("calib_dark", "calib_flat"))]
verifie(not _reste, f"« Effacer la calibration » → plus AUCUNE clé ({_reste})")
verifie(not [k for k in _ecrit if k.startswith(("calib_dark", "calib_flat"))],
        "…et la config ÉCRITE n'en contient plus (un maître effacé ne revient pas)")

# --- rechargement (comme une vraie session), puis FERMETURE
# Retour hors composition : le rechargement ne doit pas ouvrir la boîte de
# choix de couche (elle attendrait une réponse qui ne vient pas dans un banc).
app1.var_source.set("Dossier surveillé (brutes FITS/PNG/TIFF…)")
app1._maj_visibilite_cadres()
root1.update_idletasks()
ui.filedialog.askopenfilename = lambda **k: P_DU
app1._load_dark()
ui.filedialog.askopenfilename = lambda **k: P_FU
app1._load_flat()
REF_DARK = app1.calib.dark
REF_FLAT = app1.calib.flat
REF_APPLY = app1.calib.apply(FRAME)
app1._on_close()          # sauver + arrêt propre (config interceptée)
verifie(_ecrit.get("calib_dark_unique") == P_DU
        and _ecrit.get("calib_flat_unique") == P_FU,
        "les clés SURVIVENT à la fermeture (le « sauver » de fin réécrit tout)")
CONFIG_SESSION_1 = dict(_ecrit)     # ce que lira la session suivante

# ============================================================================
# [4] RESTAURATION — SECONDE SESSION (et [6] : I/O hors du fil d'interface)
# ============================================================================
print("=" * 78)
print("[4] Restauration : une SECONDE session retrouve ses maîtres")
print("=" * 78)

# [6] est mesuré ICI : espion sur la lecture des images, posé AVANT la
# construction de la fenêtre — c'est le moment où la restauration part.
# L'espion note le fil APPELANT : la preuve cherchée est « le fil d'interface ne
# lit JAMAIS », et c'est une propriété, pas un délai (une assertion sur « rien
# n'a encore été lu » serait FLAKY : le fil démon peut finir avant la fin de la
# construction).
_fils = []
_vrai_ui_load = ui.load_image


def _espion_ui_load(chemin):
    _fils.append(threading.current_thread().name)
    return _vrai_ui_load(chemin)


ui.load_image = _espion_ui_load
# Maître INTROUVABLE ajouté à la config relue : la restauration doit le DIRE
# sans échouer, et charger les autres quand même.
CONFIG_SESSION_1["calib_dark_R"] = P_ABSENT
ui.CONFIG = CONFIG_SESSION_1
_notes = []
_vrai_note = ui.journal.note
ui.journal.note = lambda cat, txt, *a, **k: _notes.append((cat, str(txt)))

root2 = tk.Tk()
root2.withdraw()
app2 = ui.App(root2)
verifie(app2.calib.dark is None and app2.calib.flat is None,
        "après la construction : rien n'est encore posé (le fil d'interface "
        "n'applique rien tout seul — c'est `_tick` qui applique)")
verifie("MainThread" not in _fils,
        "le fil d'interface n'a lu AUCUN fichier pendant la construction "
        f"(fils lecteurs : {sorted(set(_fils)) or 'aucun'})")


def _pomper(jusqua, timeout=15.0):
    """Fait tourner la boucle Tk jusqu'à `jusqua()` (ou expiration)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        root2.update()
        if jusqua():
            return True
        time.sleep(0.02)
    return False


_fini = _pomper(lambda: app2.calib.dark is not None and app2.calib.flat is not None)
verifie(_fini, "maîtres persistés RESTAURÉS (fil démon → file → `_tick`)")
verifie(_fils and all(n != "MainThread" for n in _fils),
        f"lectures faites HORS du fil d'interface : {sorted(set(_fils))}")
verifie(app2.calib.dark_source == P_DU and app2.calib.flat_source == P_FU,
        "chemins d'origine retrouvés (sources affichées)")
verifie(np.array_equal(app2.calib.dark, REF_DARK)
        and np.array_equal(app2.calib.flat, REF_FLAT),
        "images restaurées IDENTIQUES AU BIT à celles de la session 1")
verifie(np.array_equal(app2.calib.apply(FRAME), REF_APPLY),
        "image calibrée identique AU BIT : AUCUN pixel changé par le correctif")
_txt = app2.lbl_dark.cget("text").splitlines()[0]
verifie(_txt.startswith("Dark unique : ") and "—" not in _txt,
        f"libellé de calibration mis à jour : {_txt}")
verifie("Calibration restaurée" in app2.lbl_status.cget("text"),
        "ligne d'état : « " + app2.lbl_status.cget("text")[:64] + "… »")

# ============================================================================
# [5] MAÎTRE INTROUVABLE
# ============================================================================
print("=" * 78)
print("[5] Maître introuvable : aucun échec, l'échec est DIT")
print("=" * 78)

verifie("R" not in app2.calib.darks, "le dark R introuvable n'a PAS été posé")
verifie(os.path.basename(P_ABSENT) in app2.lbl_status.cget("text"),
        "la ligne d'état NOMME le fichier manquant")
verifie(any("NON restauré" in t for _c, t in _notes),
        "le JOURNAL le dit aussi : "
        + "; ".join(t for _c, t in _notes if "NON" in t))
verifie(app2.calib.dark is not None and app2.calib.flat is not None,
        "les maîtres VALIDES se sont chargés quand même (pas de tout-ou-rien)")
verifie(CONFIG_SESSION_1.get("calib_dark_R") == P_ABSENT,
        "un maître illisible n'est PAS retiré de la config (un partage réseau "
        "absent ne doit pas faire perdre le réglage)")

# ============================================================================
# [6] SYNTHÈSE I/O
# ============================================================================
print("=" * 78)
print("[6] Synthèse : toutes les lectures sont hors du fil d'interface")
print("=" * 78)
verifie(len(_fils) == 3,
        f"3 maîtres demandés → 3 lectures, toutes en fil démon ({len(_fils)})")

# --- nettoyage
ui.journal.note = _vrai_note
ui.load_image = _vrai_ui_load
try:
    app2._on_close()
except Exception:
    pass
images.CFA_MODE = CFA_MODE_AVANT
shutil.rmtree(rac, ignore_errors=True)

print("=" * 78)
print("TOUS LES TESTS PASSENT" if ok else "DES TESTS ONT ÉCHOUÉ")
print("=" * 78)
sys.exit(0 if ok else 1)

