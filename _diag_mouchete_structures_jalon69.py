# -*- coding: utf-8 -*-
"""_diag_mouchete_structures_jalon69.py — OÙ est le moucheté bleu, et à quelle
échelle ? (question d'Alain, 27/09/2026 : « BXT a des paramètres pour les
étoiles, les halos ET les objets — peut-être faut-il voir le défaut pour les
structures si on ne passe rien ? »)

On classe les pixels par LUMINOSITÉ LISSÉE (donc par « nature de fond ») : ciel
pur → halo de la galaxie → cœur — et, dans chaque classe, on mesure le moucheté
CHROMATIQUE à trois échelles :
   • 1-2 px  = le GRAIN ;
   • 2-8 px  = la TEXTURE (ce que fabrique une déconvolution/IA) ;
   • 8-30 px = les plaques larges.
Si le moucheté du fichier traité est concentré sur les STRUCTURES (classes
claires), c'est la déconvolution des objets (BXT, volet « non-stellar ») qu'il
faut regarder ; s'il est uniforme, c'est plutôt le débruitage IA.

Usage : python _diag_mouchete_structures_jalon69.py
"""
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

from avastack.images import load_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STACK = r"C:\Astro\test\m31_stack_etire-telquevu_traite-v2.38.1.fits"
EXTERNE = r"C:\Astro\test\m31_traite_externe_etire-v2.38.1.fits"
CLASSES = 6


def bande(x, f1, f2):
    """Passe-bande (f1 < f2) : contenu entre les deux échelles."""
    return (cv2.GaussianBlur(x, (0, 0), sigmaX=f2)
            - cv2.GaussianBlur(x, (0, 0), sigmaX=f1))


def mad(v):
    v = np.asarray(v, np.float64).ravel()
    return 1.4826 * float(np.median(np.abs(v - np.median(v))))


a = np.asarray(load_image(STACK), np.float32)
b = np.asarray(load_image(EXTERNE), np.float32)
if a.shape != b.shape:
    print("formes différentes :", a.shape, b.shape)
    raise SystemExit(2)
h, w = a.shape[:2]
# contrôle de géométrie : le fichier du ⚡ est en miroir (v2.38.1) → on redresse
if (cv2.minMaxLoc(cv2.matchTemplate(cv2.cvtColor(b, cv2.COLOR_RGB2GRAY),
                                    cv2.cvtColor(a, cv2.COLOR_RGB2GRAY),
                                    cv2.TM_CCOEFF_NORMED))[1]
        < cv2.minMaxLoc(cv2.matchTemplate(
            np.ascontiguousarray(cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)[::-1]),
            cv2.cvtColor(a, cv2.COLOR_RGB2GRAY),
            cv2.TM_CCOEFF_NORMED))[1]):
    b = np.ascontiguousarray(b[::-1])
    print("  (fichier du ⚡ redressé : miroir vertical de la v2.38.1)")

lum_a = cv2.GaussianBlur(a.mean(axis=2), (0, 0), sigmaX=8.0)
bords = np.percentile(lum_a, np.linspace(0, 100, CLASSES + 1))
print("=" * 78)
print("MOUCHETÉ CHROMATIQUE par CLASSE DE FOND (échelles en px)")
print("=" * 78)
print(f"{'classe (niveau lissé)':<28} {'n px':>9} "
      f"{'1-2 px':>9} {'2-8 px':>9} {'8-30 px':>9}   {'ratio 2-8':>9}")
for i in range(CLASSES):
    bas = bords[i] if i > 0 else -1e9
    haut = bords[i + 1] if i < CLASSES - 1 else 1e9
    m = (lum_a >= bas) & (lum_a < haut)
    n = int(m.sum())
    if n < 1000:
        continue
    ligne = []
    for img in (a, b):
        d = img[..., 2] - img[..., 1]                 # B−G (le bleu)
        ligne.append((mad(bande(d, 0.7, 2.0)[m]),
                      mad(bande(d, 2.0, 8.0)[m]),
                      mad(bande(d, 8.0, 30.0)[m])))
    (f_a, t_a, l_a), (f_b, t_b, l_b) = ligne
    nom = f"{0.5 * (bas + haut):.4f} (±{0.5 * (haut - bas):.4f})"
    print(f"{nom:<28} {n:>9} "
          f"{f_a:>9.6f} {t_a:>9.6f} {l_a:>9.6f}   "
          f"×{t_b / t_a:>5.3f}   (grain ×{f_b / f_a:.3f} · plaques ×{l_b / l_a:.3f})")
print()
print("  Lecture : la colonne « ratio 2-8 » dit où le fichier traité ajoute de")
print("  la texture 2-8 px. Si elle GRANDIT avec le niveau (structures), c'est")
print("  la déconvolution des OBJETS (BXT « non-stellar ») ; si elle est")
print("  uniforme, c'est le débruitage/IA global.")
