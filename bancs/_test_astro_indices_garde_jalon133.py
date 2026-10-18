# -*- coding: utf-8 -*-
"""Banc du jalon 133 — GARDE D'INTERFACE DES INDICES D'ASTROMÉTRIE.

DÉFAUT CORRIGÉ (mesuré le 18/10/2026) : les AD/Dec d'astrométrie sont
PERSISTÉES dans `config.json` et restaurées au démarrage ; à l'ouverture
`_source_fichiers_obsolete()` rend False (aucune caméra), donc elles servent à
la NOUVELLE cible sans que rien ne le dise. Cas réel : AD/Dec de M31
(10,683333 / +41,268611) sur des brutes M33 (23,4625 / +30,66) → « aucune
affinité convaincante (5 étoiles) ; RANSAC paires : 4 inliers, 1,615″/px »,
message MUET sur les indices ; avec les indices de l'en-tête : 115
appariements, 2,469″/px. Le champ (2,637°) ne distinguait PAS les deux cibles.

La garde vit dans le WORKER (`_astro_indices_garde`, appelée par `_astro_tour`
juste avant la pose des indices) : l'interface ne décide rien.

Vérifie :
  [1] M31 SAISI sur une brute M33 ⇒ l'EN-TÊTE est retenu (indices remplacés,
      `ra0` du suivi reposé), la ligne d'état ET le journal DISENT les deux
      valeurs et laquelle est retenue ; le solveur reçoit les BONS indices ;
  [2] même cible à 0,05° (< 0,25 × champ) ⇒ la SAISIE est conservée, et
      l'en-tête n'est lu qu'UNE fois (aucun coût par frame) ;
  [3] brute SANS coordonnées (ni OBJCTRA ni RA/DEC) ⇒ saisie conservée ;
  [4] `_astro_source` déjà « en-tête … » ⇒ aucun message et AUCUNE lecture ;
  [5] le WCS résolu reste PROPAGÉ (WCS de la grille courante + `propager`) ;
  [6] champ de l'en-tête utilisé quand il est DÉDUCTIBLE, champ SAISI conservé
      sinon (même optique : `indices_entete_fits` rend alors `champ=None`).

Exécution : python bancs/_test_astro_indices_garde_jalon133.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (et non plus à côté de l'application).
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import os
import shutil
import sys
import tempfile
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV/OpenCL au teardown sinon

import avastack.core.worker as wk
import avastack.ui.app as ui
from avastack import journal
from avastack.catalogues import WcsTan
from avastack.images import save_image
from avastack.processing import astrometrie as astro
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):   # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)



# --------------------------------------------------------------- constantes
H, W = 120, 200
FORME = (H, W)
# Indices SAISIS de la VEILLE : M31, champ réel du setup (2,637°) — ceux-là
# mêmes qui ont fait échouer la résolution des brutes M33 le 18/10/2026.
RA_M31, DEC_M31, CHAMP = 10.683333, 41.268611, 2.63665
# Brute M33 (en-tête N.I.N.A. : OBJCTRA en HEURES).
RA_M33, DEC_M33 = 23.4625, 30.66
ECH = 2.465 / 3600.0                     # 2,465 ″/px (échelle du jeu réel)
CRVAL = (RA_M33, DEC_M33)
W_VRAI = WcsTan(CRVAL, ((W - 1) / 2.0, (H - 1) / 2.0),
                [[-ECH, 0.0], [0.0, ECH]], forme=FORME)


# ------------------------------------------------------------- environnement
journal_ecrit = []


def _journal(etape, detail=""):
    journal_ecrit.append((etape, detail))
    return True


journal.note = _journal
ui.CONFIG = {}
ui.sauver_config = lambda *a, **k: None

tmp = tempfile.mkdtemp(prefix="avastack_garde133_")
brute = np.full((H, W), 0.03, np.float32)
brute[40:44, 50:54] = 0.9

P_M33 = os.path.join(tmp, "m33.fit")
save_image(P_M33, brute, entete={"OBJCTRA": "01 33 51",
                                "OBJCTDEC": "+30 39 36",
                                "OBJECT": "M33"})
# MÊME cible à 0,05° (Dec +30°42'36" au lieu de +30°39'36")
P_PROCHE = os.path.join(tmp, "m33_proche.fit")
save_image(P_PROCHE, brute, entete={"OBJCTRA": "01 33 51",
                                    "OBJCTDEC": "+30 42 36",
                                    "OBJECT": "M33"})
# Brute SANS coordonnées (caméra SDK, PNG/TIFF, FITS sans mots-clés)
P_SANS = os.path.join(tmp, "sans_coordonnees.fit")
save_image(P_SANS, brute, entete={"EXPTIME": 60.0})
# Brute M33 AVEC optique : le champ de l'en-tête est déductible
P_CHAMP = os.path.join(tmp, "m33_optique.fit")
save_image(P_CHAMP, brute, entete={"OBJCTRA": "01 33 51",
                                   "OBJCTDEC": "+30 39 36",
                                   "OBJECT": "M33",
                                   "FOCALLEN": 243.0, "XPIXSZ": 2.9011})


class CameraBouchon:
    """Source FICHIERS minimale : la garde ne lit que la brute courante."""

    def __init__(self, chemin=""):
        self.last_file = chemin

    def stats(self):
        return {}


def empilement(n=4):
    """Empilement MONO de `n` frames (au-delà de ASTRO_MIN_FRAMES = 3)."""
    st = LiveStacker(FORME, k=None, method="kappa", window=8)
    for _ in range(n):
        st.add(brute)
    st.note_alignement(np.eye(2, 3))
    return st


def faux_solveur(wcs, appels=None):
    """Solveur FACTICE (mêmes arguments/retour que `catalogues.resoudre`) ;
    `appels` enregistre les INDICES reçus — c'est la preuve du correctif."""
    def solve(img, ra0, dec0, champ, dossier=None, limmag=None):
        if appels is not None:
            appels.append((float(ra0), float(dec0), float(champ)))
        if wcs is None:
            return None, {"n_etoiles_img": 9}, "échec simulé"
        return wcs, {"n_etoiles_img": 86, "n_etoiles_cat": 201,
                     "n_appariements": 53, "rms_px": 0.59,
                     "echelle_arcsec_px": 2.465, "methode": "triangles"}, ""
    return solve


def appli(root, chemin, saisie=None, wcs=None, appels=None):
    """App réelle sur `root` : `saisie` = indices SAISIS (None = aucun)."""
    app = ui.App(root)
    app._dire = lambda *a, **k: None      # boîte MODALE : jamais dans un banc
    app._astro_actif = True
    app._astro_wcs_secours = None
    app._astro_aveugles = 0
    app.camera = CameraBouchon(chemin)
    app.suivi_astro = astro.SuiviAstrometrie(solveur=faux_solveur(wcs, appels))
    if saisie is None:
        app._astro_indices = None
        app._astro_source = ""
    else:
        app._astro_indices = tuple(saisie)
        app._astro_source = "saisie"
        app.suivi_astro.indice(*saisie)   # comme le fait `_on_astro` (UI)
    app._astro_garde_pour = None
    app._astro_name_proposed = True       # pas de dialogue de nom de cible
    app._astro_was_resolved = False
    return app


def lignes_garde():
    """Lignes de journal écrites par la GARDE (toutes causes confondues)."""
    return [d for (_e, d) in journal_ecrit if "≠ en-tête" in str(d)]



# =================================================== [0] la mesure d'écart
print("[0] astrometrie.separation_deg : grand cercle, stable aux petits écarts")
sep_m31_m33 = astro.separation_deg(RA_M31, DEC_M31, RA_M33, DEC_M33)
verifie(sep_m31_m33 is not None and 10.0 < sep_m31_m33 < 20.0,
        f"M31 ↔ M33 = {sep_m31_m33:.2f}° (deux cibles distinctes)")
verifie(abs(astro.separation_deg(RA_M33, DEC_M33, RA_M33, DEC_M33)) < 1e-9,
        "même position → 0,00°")
verifie(abs(astro.separation_deg(RA_M33, DEC_M33, RA_M33, DEC_M33 + 1.0) - 1.0)
        < 1e-6, "1° d'écart en Dec → 1,000000°")
verifie(astro.separation_deg("illisible", 1.0, 2.0, 3.0) is None,
        "valeur illisible → None (jamais d'exception)")
verifie(astro.GARDE_INDICES_FRACTION == 0.25,
        "le seuil de la garde vaut 0,25 × champ (une seule source)")

root = tk.Tk()
root.withdraw()

# ================================ [1] M31 saisi sur une brute M33 → en-tête
print("[1] M31 SAISI sur une brute M33 : l'EN-TÊTE est retenu et le DIT")
ORIG_NOM_PROCH = wk._nom_cible_proche
# Le catalogue d'objets célèbres n'est pas une dépendance des bancs : on rend
# le nom de la cible SAISIE déterministe (« M31 »), l'en-tête donnant « M33 ».
wk._nom_cible_proche = lambda ra, dec: "M31"

journal_ecrit.clear()
app1 = appli(root, P_M33, saisie=(RA_M31, DEC_M31, CHAMP), wcs=None)
change = app1._astro_indices_garde()
verifie(change is True, "décision : les indices SAISIS sont REMPLACÉS")
ind1 = app1._astro_indices or (0.0, 0.0, 0.0)
verifie(abs(ind1[0] - RA_M33) < 1e-4 and abs(ind1[1] - DEC_M33) < 1e-4,
        f"AD/Dec de l'EN-TÊTE retenues ({ind1[0]:.5f}° / {ind1[1]:+.5f}°)")
verifie(abs(ind1[2] - CHAMP) < 1e-9,
        f"champ SAISI conservé faute d'optique dans l'en-tête "
        f"({ind1[2]:.5f}°)")
verifie(app1._astro_source.startswith("en-tête m33.fit"),
        f"provenance annoncée : « {app1._astro_source} »")
verifie(app1.suivi_astro.pret and abs(app1.suivi_astro.ra0 - RA_M33) < 1e-4,
        "le SUIVI porte les indices de l'en-tête (WCS et essais remis à zéro)")
msg1 = str(app1.astro_info)
verifie("AD/Dec saisies M31" in msg1 and "en-tête M33" in msg1
        and "en-tête utilisé" in msg1,
        f"ligne d'état : « {msg1} »")
verifie(len(lignes_garde()) == 1,
        "le message est aussi parti au JOURNAL (une ligne)")

# Intégration : c'est bien le SOLVEUR qui reçoit les indices de l'en-tête.
journal_ecrit.clear()
appels1 = []
app1b = appli(root, P_M33, saisie=(RA_M31, DEC_M31, CHAMP), wcs=W_VRAI,
              appels=appels1)
app1b._astro_tour(empilement())
verifie(len(appels1) == 1 and abs(appels1[0][0] - RA_M33) < 1e-4
        and abs(appels1[0][1] - DEC_M33) < 1e-4,
        f"`_astro_tour` → le solveur reçoit les indices de l'en-tête "
        f"({appels1})")
verifie(any("AD/Dec saisies M31" in d for d in lignes_garde()),
        "la ligne du journal est écrite par le WORKER (pas par l'interface)")
verifie(app1b.suivi_astro.resolu,
        "la résolution aboutit avec les indices de l'en-tête")






# =================== [2] même cible à 0,05° → la saisie reste, UNE lecture
print("[2] Même cible à 0,05° : la SAISIE reste, l'en-tête n'est lu qu'UNE fois")
wk._nom_cible_proche = ORIG_NOM_PROCH      # plus de nom simulé
compte = {"n": 0}
ORIG_ENTETE = astro.indices_entete_fits


def _entete_compte(chemin):
    compte["n"] += 1
    return ORIG_ENTETE(chemin)


journal_ecrit.clear()
astro.indices_entete_fits = _entete_compte
# SAISIE à 0,05° de l'en-tête : MÊME cible, petit écart (<< 0,25 × champ).
SAISIE_PROCHE = (RA_M33, DEC_M33 + 0.05, CHAMP)
try:
    app2 = appli(root, P_PROCHE, saisie=SAISIE_PROCHE, wcs=None)
    st2 = empilement()
    app2._astro_tour(st2)
    app2._astro_tour(st2)      # 2e tour : la comparaison ne doit PAS relire
finally:
    astro.indices_entete_fits = ORIG_ENTETE
verifie(compte["n"] == 1,
        f"en-tête lu UNE seule fois pour deux tours (reçu {compte['n']})")
verifie(app2._astro_indices == SAISIE_PROCHE
        and app2._astro_source == "saisie",
        "saisie CONSERVÉE (0,05° < 0,25 × 2,637° = 0,66°)")
verifie(not lignes_garde(), "aucun message de garde (même cible)")


# ==================== [3] brute sans coordonnées → la saisie reste, silence
print("[3] Brute SANS coordonnées : la saisie est conservée, sans comparaison")
journal_ecrit.clear()
app3 = appli(root, P_SANS, saisie=(RA_M31, DEC_M31, CHAMP), wcs=None)
app3._astro_tour(empilement())
verifie(app3._astro_indices == (RA_M31, DEC_M31, CHAMP)
        and app3._astro_source == "saisie",
        "saisie CONSERVÉE (ni OBJCTRA/OBJCTDEC ni RA/DEC dans l'en-tête)")
verifie(not lignes_garde(), "aucun message (le comportement d'avant ne bouge pas)")


# ================= [4] indices déjà de l'en-tête → aucun message, 0 lecture
print("[4] Indices déjà « en-tête … » : aucun message et AUCUNE lecture")
compte2 = {"n": 0}


def _entete_compte2(chemin):
    compte2["n"] += 1
    return ORIG_ENTETE(chemin)


journal_ecrit.clear()
astro.indices_entete_fits = _entete_compte2
try:
    app4 = appli(root, P_M33, saisie=None, wcs=None)
    app4._astro_indices = (RA_M33, DEC_M33, CHAMP)
    app4._astro_source = "en-tête m33.fit"
    app4.suivi_astro.indice(RA_M33, DEC_M33, CHAMP)
    app4._astro_tour(empilement())
finally:
    astro.indices_entete_fits = ORIG_ENTETE
verifie(compte2["n"] == 0, f"aucune lecture d'en-tête (reçu {compte2['n']})")
verifie(not lignes_garde(),
        "aucun message : les indices viennent DÉJÀ de l'en-tête")


# ============================ [5] le WCS résolu reste PROPAGÉ après la garde
print("[5] Le WCS résolu après la garde reste PROPAGÉ")
journal_ecrit.clear()
app5 = appli(root, P_M33, saisie=(RA_M31, DEC_M31, CHAMP), wcs=W_VRAI)
app5._astro_tour(empilement())
w5, m5 = app5.suivi_astro.wcs_grille(None, forme=FORME)
verifie(app5.suivi_astro.resolu and w5 is not None,
        f"WCS de la grille courante disponible (« {m5} »)")
okp, mp = app5.suivi_astro.propager(np.eye(2, 3))
verifie(okp, f"propagation acceptée (« {mp} »)")
verifie("AD 23.46250" in str(app5.astro_info),
        f"la ligne d'état montre les indices RETENUS : « {app5.astro_info} »")


# ============== [6] champ de l'en-tête adopté quand il est déductible
print("[6] Champ de l'en-tête adopté quand il est DÉDUCTIBLE")
journal_ecrit.clear()
app6 = appli(root, P_CHAMP, saisie=(RA_M31, DEC_M31, CHAMP), wcs=None)
app6._astro_indices_garde()
champ_entete = astro.champ_depuis_optique(243.0, 2.9011, W)
ind6 = app6._astro_indices or (0.0, 0.0, 0.0)
verifie(ind6[2] is not None and abs(ind6[2] - float(champ_entete)) < 1e-6,
        f"champ de l'en-tête adopté ({ind6[2]:.4f}° = FOCALLEN/XPIXSZ/NAXIS1, "
        f"au lieu de {CHAMP:.4f}° saisis)")
verifie(abs(ind6[0] - RA_M33) < 1e-4,
        "les AD/Dec restent celles de l'en-tête")


# ================================================================== verdict
shutil.rmtree(tmp, ignore_errors=True)
print("\nBANC 133 :", "VERT" if ok else "ROUGE")
sys.exit(0 if ok else 1)



journal_ecrit.clear()
astro.indices_entete_fits = _entete_compte2
try:
    app4 = appli(root, P_M33, saisie=None, wcs=None)
    app4._astro_indices = (RA_M33, DEC_M33, CHAMP)
    app4._astro_source = "en-tête m33.fit"
    app4.suivi_astro.indice(RA_M33, DEC_M33, CHAMP)
    app4._astro_tour(empilement())
finally:
    astro.indices_entete_fits = ORIG_ENTETE
verifie(compte2["n"] == 0, f"aucune lecture d'en-tête (reçu {compte2['n']})")
verifie(not lignes_garde(), "aucun message : les indices viennent DÉJÀ de l'en-tête")

# ================================ [1] M31 saisi sur une brute M33 → en-tête
print("[1] M31 SAISI sur une brute M33 : l'EN-TÊTE est retenu et le DIT")
ORIG_NOM_PROCH = wk._nom_cible_proche
# Le catalogue d'objets célèbres n'est pas une dépendance des bancs : on rend
# le nom de la cible SAISIE déterministe (« M31 »), l'en-tête donnant « M33 ».
wk._nom_cible_proche = lambda ra, dec: "M31"

journal_ecrit.clear()
app1 = appli(root, P_M33, saisie=(RA_M31, DEC_M31, CHAMP), wcs=None)
change = app1._astro_indices_garde()
verifie(change is True, "décision : les indices SAISIS sont REMPLACÉS")
ind1 = app1._astro_indices or (0.0, 0.0, 0.0)
verifie(abs(ind1[0] - RA_M33) < 1e-4 and abs(ind1[1] - DEC_M33) < 1e-4,
        f"AD/Dec de l'EN-TÊTE retenues ({ind1[0]:.5f}° / {ind1[1]:+.5f}°)")
verifie(abs(ind1[2] - CHAMP) < 1e-9,
        f"champ SAISI conservé faute d'optique dans l'en-tête "
        f"({ind1[2]:.5f}°)")
verifie(app1._astro_source.startswith("en-tête m33.fit"),
        f"provenance annoncée : « {app1._astro_source} »")
verifie(app1.suivi_astro.pret
        and abs(app1.suivi_astro.ra0 - RA_M33) < 1e-4,
        "le SUIVI porte les indices de l'en-tête (WCS et essais remis à zéro)")
msg1 = str(app1.astro_info)
verifie("AD/Dec saisies M31" in msg1 and "en-tête M33" in msg1
        and "en-tête utilisé" in msg1,
        f"ligne d'état : « {msg1} »")
verifie(len(lignes_garde()) == 1,
        "le message est aussi parti au JOURNAL (une ligne)")

# Intégration : c'est bien le SOLVEUR qui reçoit les indices de l'en-tête.
journal_ecrit.clear()
appels = []
app1b = appli(root, P_M33, saisie=(RA_M31, DEC_M31, CHAMP), wcs=W_VRAI,
              appels=appels)
app1b._astro_tour(empilement())
verifie(len(appels) == 1 and abs(appels[0][0] - RA_M33) < 1e-4
        and abs(appels[0][1] - DEC_M33) < 1e-4,
        f"`_astro_tour` → le solveur reçoit les indices de l'en-tête ({appels})")
verifie(any("AD/Dec saisies M31" in d for d in lignes_garde()),
        "la ligne du journal est écrite par le WORKER (pas par l'interface)")
verifie(app1b.suivi_astro.resolu,
        "la résolution aboutit avec les indices de l'en-tête")
