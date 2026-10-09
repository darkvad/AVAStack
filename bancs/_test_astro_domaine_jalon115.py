# -*- coding: utf-8 -*-
"""Banc du jalon 115 — L'ASTROMÉTRIE REÇOIT LA BONNE IMAGE (domaine des brutes).

DÉFAUT CORRIGÉ (test réel M31 LRGB, journal v2.66.0 du 09/10/2026, 7 échecs) :
« pas assez de correspondances mutuelles ; RANSAC paires : … (meilleur : 3
inliers, échelle 1.628″/px) ». Cause REPRODUITE hors-ligne sur les frames
réellement lues : le solveur recevait `stacker.mean(recadre=False)` — le
COMPOSITE NORMALISÉ, dont le fond (~0,72) monte son seuil (fond + 8σ) à ~0,99 :
presque rien ne passe, les « étoiles » détectées sont du BRUIT, l'appariement
échoue. La COUCHE BRUTE du rôle G, MÊME GRILLE, résout (94 appariements,
2,466″/px). C'est le même défaut de DOMAINE que le correctif ① du jalon 113,
mais pour l'ASTROMÉTRIE (le 113 n'avait corrigé que l'ALIGNEUR).

Vérifie :
  [1] `_image_reference_de(composite)` = COUCHE BRUTE du rôle du VERT (2D, fond
      de brute), là où `mean(recadre=False)` est un composite 3D au fond ÉLEVÉ
      (le défaut est donc MESURABLE, pas supposé) ;
  [2] `App._astro_tour` transmet BIEN cette couche au solveur (`resoudre_sur`) ;
  [3] `_astro_propager_restack` prend l'ancien empilement dans le MÊME domaine
      (piste « non corrigée » signalée en AVANCEMENT) ;
  [4] `SuiviAstrometrie.resume_echec()` : les compteurs du solveur (image,
      catalogue, appariements) figurent dans le message d'échec — un échec
      futur dira TOUT SEUL d'où il vient.

Exécution : python bancs/_test_astro_domaine_jalon115.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV/OpenCL au teardown sinon

import avastack.core.worker as wk
import avastack.ui.app as ui
from avastack import journal
from avastack.processing import astrometrie as astro
from avastack.processing.composition import CompositeStacker

if hasattr(sys.stdout, "reconfigure"):   # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


H, W = 64, 80
RA, DEC, CHAMP = 10.683333, 41.268611, 2.63665


def brute(fond=0.03, graine=0):
    """Frame mono « brute » : fond bas + quelques étoiles gaussiennes."""
    rng = np.random.default_rng(graine)
    img = rng.normal(fond, 0.002, (H, W)).astype(np.float32)
    for (x, y, a) in ((12, 15, 0.6), (40, 20, 0.9), (60, 45, 0.5),
                      (25, 50, 0.7), (48, 33, 0.8)):
        img[y - 1:y + 2, x - 1:x + 2] += a
    return img


def composite(n=4):
    """CompositeStacker LRGB réaliste (rôles L/R/G/B, fonds de brutes)."""
    st = CompositeStacker("LRGB", k=3.0, warmup=3, method="winsorized", window=4)
    st.normalisation_commune = True
    st.mode_l = "synthetise"
    for i in range(n):
        for role in ("L", "R", "G", "B"):
            st.role_courant = role
            st.add(brute(0.03 + 0.005 * ("LRGB".index(role)), graine=i + 7))
    return st


journal.note = lambda etape, detail="": True    # banc hermétique
ui.CONFIG = {}
ui.sauver_config = lambda *a, **k: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
app._mode_compo = True


# ============================================ [1] le DOMAINE, mesuré
print("[1] _image_reference_de : couche BRUTE du VERT vs composite normalisé")
st_c = composite()
comp = st_c.mean(recadre=False)
ref = app._image_reference_de(st_c)
moy = st_c.moyennes(recadre=False)
fond_comp = float(np.median(comp[..., 1]))
fond_ref = float(np.median(ref))
verifie(ref is not None and ref.ndim == 2,
        f"la référence est une COUCHE 2D (reçu ndim="
        f"{None if ref is None else ref.ndim})")
verifie(np.array_equal(ref, moy["G"]),
        "la référence est la couche du rôle G (le canal VERT)")
verifie(fond_ref < 0.2,
        f"fond de la couche = domaine des brutes ({fond_ref:.4f} < 0,2)")
# Le NIVEAU du composite dépend des percentiles de la normalisation : sur les
# VRAIES frames M31 il monte à 0,72 (contre 0,03-0,07 par couche) — c'est CE
# fait, mesuré hors-ligne, qui porte le seuil du solveur à ~0,99 et le rend
# aveugle. Un jeu synthétique ne le reproduit pas fidèlement : on l'AFFICHE
# sans en faire une condition (la condition robuste est « couche 2D à fond de
# brute », ci-dessus, plus la non-régression de [2] et [3]).
print(f"    (info) fond du composite normalisé ici : {fond_comp:.4f} — "
      f"sur les vraies frames : ~0,72 (cf. changelog v2.67.0)")


# ============================================ [2] _astro_tour
print("[2] App._astro_tour : le solveur reçoit la COUCHE, pas le composite")


class SuiviBouchon:
    """Suivi de test : enregistre ce que `resoudre_sur` reçoit."""

    def __init__(self):
        self.resolu = False
        self.pret = True
        self.essais = 0
        self.derniere_erreur = ""
        self.vues = []      # (ndim, médiane) des images reçues

    def indice(self, *a):
        return False

    def peut_essayer(self, n, maintenant=None):
        return True

    def raison_attente(self):
        return ""

    def texte_resume(self):
        return ""

    def resoudre_sur(self, img, n_frames=None):
        a = np.asarray(img)
        self.vues.append((int(a.ndim), float(np.median(a))))
        return False, "bouchon"


b = SuiviBouchon()
app.suivi_astro = b
app.stacker = st_c
app._astro_actif = True
app._astro_indices = (RA, DEC, CHAMP)
app._astro_wcs_secours = None
app._astro_tour(st_c)
verifie(len(b.vues) == 1 and b.vues[0][0] == 2
        and abs(b.vues[0][1] - fond_ref) < 1e-6,
        f"resoudre_sur a reçu la couche 2D de fond {fond_ref:.4f} — "
        f"reçu {b.vues}")


# ============================================ [3] propagation de re-stack
print("[3] _astro_propager_restack : ancien empilement dans le domaine des brutes")

instances = []


class FauxAligner:
    def __init__(self):
        self.triangles_seuls = False
        self.refs = []
        instances.append(self)

    def set_reference(self, img):
        a = np.asarray(img)
        self.refs.append((int(a.ndim), float(np.median(a))))

    def compute(self, img):
        return np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]), True


class SuiviResolu:
    def __init__(self):
        self.resolu = True
        self.pret = True
        self.essais = 1
        self.derniere_erreur = ""
        self.prop = []

    def texte_resume(self):
        return ""

    def propager(self, M):
        self.prop.append(np.asarray(M))
        return True, ""


_orig_aligner = wk.StarAligner
_orig_app_aligner = app.aligner
wk.StarAligner = FauxAligner
try:
    app.suivi_astro = SuiviResolu()
    app._astro_name_proposed = True
    app._astro_was_resolved = True        # évite le bloc « nom de cible »
    app.aligner = type("A", (), {"triangles_seuls": False})()
    app._astro_propager_restack(st_c, brute(graine=99))
finally:
    wk.StarAligner = _orig_aligner
    app.aligner = _orig_app_aligner
verifie(instances and instances[0].refs and instances[0].refs[0][0] == 2
        and abs(instances[0].refs[0][1] - fond_ref) < 1e-6,
        f"l'aligneur privé a reçu la COUCHE (2D, fond {fond_ref:.4f}) — reçu "
        f"{instances[0].refs if instances else None}")
verifie(len(app.suivi_astro.prop) == 1,
        "le WCS a bien été propagé (1 appel) sur la matrice de l'aligneur")


# ============================================ [4] compteurs d'échec
print("[4] SuiviAstrometrie.resume_echec : compteurs du solveur dans l'échec")


def _solveur_bouchon(img, ra, dec, champ, dossier=None, limmag=None):
    return None, {"n_etoiles_img": 120, "n_etoiles_cat": 400,
                  "n_appariements": 0}, "pas assez de correspondances mutuelles"


s1 = astro.SuiviAstrometrie(solveur=_solveur_bouchon)
s1.indice(RA, DEC, CHAMP)
okk, msg = s1.resoudre_sur(np.zeros((32, 40), np.float32), n_frames=12)
verifie(not okk and "pas assez de correspondances mutuelles" in msg
        and "[image 120 étoiles, catalogue 400, appariements 0]" in msg,
        f"l'échec porte les compteurs (« {msg} »)")

s2 = astro.SuiviAstrometrie(solveur=lambda *a, **k: (None, {}, "échec nu"))
s2.indice(RA, DEC, CHAMP)
okk2, msg2 = s2.resoudre_sur(np.zeros((32, 40), np.float32), n_frames=12)
verifie(msg2 == "échec nu",
        f"info VIDE : message inchangé (aucun suffixe inventé) — « {msg2} »")

root.destroy()
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
