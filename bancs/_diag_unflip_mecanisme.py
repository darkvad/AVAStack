# -*- coding: utf-8 -*-
"""_diag_unflip_mecanisme.py — QU'EST-CE QUI ÉCRASE la mesure d'`auto_unflip` ?

Sur les fichiers réels, la corrélation brute de la v2.38.1 valait +0,1085
(droite) contre +0,1212 (miroir) : écart minuscule, donc aucune décision. Sur
une scène de banc « propre », la même formule donne +0,89 contre +1,00 et
FONCTIONNE — la scène ne reproduit donc pas le mécanisme.

Hypothèses testées ici, sur la VRAIE paire (empilement linéaire / résultat du ⚡) :
  A) le GRADIENT de pollution lumineuse (présent dans l'empilement, retiré par
     l'outil) sature la corrélation et noie la structure ;
  B) le GRAIN (non corrélé entre les deux images) domine le signal ;
  C) l'écart dynamique (cœur) écrase tout.
Mesure : corrélation brute (formule v2.38.1) sur les deux orientations, puis la
même après retrait des basses fréquences (÷ flou très large) des deux images.

Usage : python bancs/_diag_unflip_mecanisme.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

from avastack.images import load_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EMP = r"C:\Astro\test\M31_traite_lineaire_2.38.0.fits"
EXT = r"C:\Astro\test\m31_traite_externe_lineaire-v2.38.0.fits"


def corr(x, y):
    x, y = x - x.mean(), y - y.mean()
    d = np.sqrt((x * x).sum() * (y * y).sum())
    return float((x * y).sum() / d) if d > 0 else 0.0


def echantillon(a):
    """Le sous-échantillonnage « 1 pixel sur N » de la v2.38.1."""
    return a[::max(1, a.shape[0] // 256),
             ::max(1, a.shape[1] // 256)].astype(np.float64)


def paire(nom, a, b):
    a, b = echantillon(a), echantillon(b)
    c1, c2 = corr(a, b), corr(a, b[::-1])
    print(f"    {nom:<34} droite {c1:+.4f} · miroir {c2:+.4f} · "
          f"écart {c2 - c1:+.4f}"
          f"{'   ← DÉCIDABLE' if abs(c2 - c1) > 0.05 else '   ← indécidable'}")


emp = np.asarray(load_image(EMP), np.float32).mean(axis=2)
ext = np.asarray(load_image(EXT), np.float32).mean(axis=2)
print("=" * 78)
print("A) la paire BRUTE (ce que voit la v2.38.1)")
print("=" * 78)
paire("brute", ext, emp)

print()
print("B) après retrait des BASSES fréquences (÷ flou σ=64 px)")
print("=" * 78)


def basses(x, sigma=64.0):
    f = cv2.GaussianBlur(x, (0, 0), sigmaX=sigma)
    return x / np.maximum(f, 1e-6)


paire("basses fréquences retirées", basses(ext), basses(emp))

print()
print("C) après ÉTREMENT doux + normalisation (ce que fait la v2.38.2)")
print("=" * 78)


def etire(x):
    bas, haut = (float(np.percentile(x, 0.5)), float(np.percentile(x, 99.5)))
    y = np.clip((x - bas) / max(1e-9, haut - bas), 0.0, 1.0)
    return np.sqrt(y)


paire("étirée (v2.38.2)", etire(ext), etire(emp))

print()
print("D) ampleur des composantes (qui « pèse » dans la corrélation ?)")
print("=" * 78)
for nom, x in (("empilement", emp), ("résultat du ⚡", ext)):
    bas = cv2.GaussianBlur(x, (0, 0), sigmaX=64.0)
    print(f"    {nom:<16} écart-type : total {x.std():.5f} · "
          f"basses fréquences {bas.std():.5f} · "
          f"hautes fréquences {(x - bas).std():.5f} · "
          f"rapport BF/HF {bas.std() / max(1e-9, (x - bas).std()):.2f}")
