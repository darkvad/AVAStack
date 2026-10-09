# -*- coding: utf-8 -*-
"""DIAGNOSTIC (jetable) — retournement au méridien en composition.

But : reproduire le scénario RÉEL d'Alain (2 nuits, R/G/B retournés à 180°,
L non retourné) et vérifier que l'aligneur les accepte MAINTENANT. On teste
aussi le chemin TRIANGLES SEUL (au cas où ORB échoue sur les vraies données).

Exécution : python bancs/_diag_meridien_flip_reel.py
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import numpy as np
import cv2

from avastack.processing import alignment as al_mod
from avastack.processing import composition as comp_mod

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def champ(shape, nb, graine, fond=0.02, sigma=1.4, bruit=0.004):
    rng = np.random.default_rng(graine)
    h, w = shape
    img = np.full((h, w), fond, np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(nb):
        y = float(rng.integers(20, h - 20))
        x = float(rng.integers(20, w - 20))
        a = float(rng.uniform(0.05, 0.8))
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * sigma ** 2))).astype(np.float32)
    img += rng.normal(0.0, bruit, img.shape).astype(np.float32)
    return img


print("Version du module alignment chargée :",
      al_mod.__file__)
print("MERIDIAN_FLIP_DEG =", getattr(al_mod, "MERIDIAN_FLIP_DEG", "ABSENT !"),
      "· TOL =", getattr(al_mod, "MERIDIAN_FLIP_TOL_DEG", "ABSENT !"))
print()

FORM = (400, 600)
# Nuit A (L, non retourné) : référence. Nuit B (R/G/B, retourné 180°).
L = champ(FORM, 80, graine=1)
Rb = champ(FORM, 80, graine=1)          # même champ (mêmes étoiles)…
Rb = np.clip(Rb * 0.6 + 0.01, 0, 1)     # …mais spectre rouge (fond plus bas)
Rb_180 = cv2.rotate(Rb, cv2.ROTATE_180)  # RETOURNEMENT AU MÉRIDIEN

print("[1] Référence = L (nuit A) ; frame = R retournée 180° (nuit B)")
al = al_mod.StarAligner()
al.set_reference(L)
M, ok = al.compute(Rb_180)
if M is None:
    print("    → REFUSÉ (aucune matrice)")
else:
    ang, ech, dx, dy = al_mod.infos_M(M)
    print(f"    → ok={ok} · angle={ang:+.2f}° · échelle={ech:.4f} · "
          f"Δ=({dx:+.1f},{dy:+.1f}) · méthode={al.dernier}")
print()

print("[2] Même chose, TRIANGLES SEULS (comme HOO/SHO, ORB écarté)")
al2 = al_mod.StarAligner()
al2.triangles_seuls = True
al2.set_reference(L)
M2, ok2 = al2.compute(Rb_180)
if M2 is None:
    print("    → REFUSÉ (aucune matrice)")
else:
    ang2, ech2, dx2, dy2 = al_mod.infos_M(M2)
    print(f"    → ok={ok2} · angle={ang2:+.2f}° · échelle={ech2:.4f} · "
          f"Δ=({dx2:+.1f},{dy2:+.1f}) · méthode={al2.dernier}")
print()

print("[3] Chaîne RÉELLE de composition (extraire_canal + canaux multi-rôles)")
# Image COULEUR (H, W, 3) type OSC : on simule un dossier R/G/B couleur.
rgbA = np.stack([L * 0.5, L * 0.3, L * 0.2], axis=-1).astype(np.float32)
canaux = {"L": L, "R": comp_mod.extraire_canal(rgbA, "R")}
al3 = al_mod.StarAligner()
al3.set_reference(canaux["L"])
img_travail = comp_mod.extraire_canal(np.rot90(rgbA * 0, 0) + rgbA, "R")
img_180 = cv2.rotate(img_travail, cv2.ROTATE_180)
M3, ok3 = al3.compute(img_180)
if M3 is None:
    print("    → REFUSÉ (aucune matrice)")
else:
    ang3, ech3, dx3, dy3 = al_mod.infos_M(M3)
    print(f"    → ok={ok3} · angle={ang3:+.2f}° · méthode={al3.dernier}")

print()
print("RAPPEL : si [1] et [2] affichent un angle ≈ 180°, le correctif FONCTIONNE")
print("dans le code source. Un résultat identique en appli signifierait alors")
print("que l'appli lancée n'utilise PAS ce code source (paquet installé/gelé).")
