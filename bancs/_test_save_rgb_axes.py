# -*- coding: utf-8 -*-
"""Banc : convention d'axes FITS couleur (retour réel d'Alain, 22/09/2026).

Constat : « 💾 Enregistrer l'empilement (linéaire) » écrivait le RGB avec
les canaux sur NAXIS1 — ASIFitsView/Siril voyaient 2165 images de 3 px de
large → image « noire ». Fix : save_image écrit les canaux sur NAXIS3
(convention astro), load_image normalise en (H, W, C) pour l'appli.

[1] save_image couleur → NAXIS1 = largeur, NAXIS3 = 3 ;
[2] aller-retour save_image → load_image : (H, W, C) intact ;
[3] load_image lit un FITS « Siril » (canaux sur NAXIS3) → (H, W, C) ;
[4] mono 2D : NAXIS1 = largeur, load_image → 2D inchangé ;
[5] PNG 16 bits : inchangé (clip [0..1]).

Exécution : python bancs/_test_save_rgb_axes.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys
import tempfile

import numpy as np
from astropy.io import fits

from avastack.images import load_image, save_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


tmp = tempfile.mkdtemp(prefix="avastack_axes_")
rng = np.random.default_rng(9)
H, W = 200, 300
rgb = np.clip(rng.normal(0.05, 0.02, (H, W, 3)) + 0.05, 0, None).astype(
    np.float32)
rgb[:, :, 0] += 0.3                     # signature R identifiable

# ============================================ [1] axes du FITS écrit
print("[1] save_image couleur : canaux sur NAXIS3")
p = os.path.join(tmp, "rgb.fit")
save_image(p, rgb, entete={"FILTER": "R"})
h = fits.getheader(p)
verifie(int(h["NAXIS1"]) == W and int(h["NAXIS2"]) == H
        and int(h["NAXIS3"]) == 3,
        f"NAXIS=({h['NAXIS1']},{h['NAXIS2']},{h['NAXIS3']}) — canaux sur "
        "NAXIS3 (lut par Siril/ASIFitsView)")
verifie(str(h.get("FILTER", "")) == "R", "mot-clé FILTER conservé")

# ==================================== [2] aller-retour save → load
print("[2] Aller-retour save_image → load_image : (H, W, C) intact")
img = load_image(p)
verifie(img.ndim == 3 and img.shape == (H, W, 3),
        f"forme rechargée {img.shape} == (H, W, 3)")
if img.shape == rgb.shape:
    verifie(float(np.abs(img - rgb).max()) < 1e-6,
            f"contenu identique (écart max {float(np.abs(img - rgb).max()):.2e})")
    verifie(float(img[:, :, 0].mean() - img[:, :, 1].mean()) > 0.25,
            "le canal R reste le canal R (pas d'échange de canaux)")

# =========================== [3] lecture d'un FITS « Siril » (C, H, W)
print("[3] load_image : FITS canaux-sur-NAXIS3 (Siril) → (H, W, C)")
p2 = os.path.join(tmp, "siril.fit")
fits.PrimaryHDU(np.ascontiguousarray(
    np.transpose(rgb, (2, 0, 1)).astype(np.float32))).writeto(p2)
img2 = load_image(p2)
verifie(img2.shape == (H, W, 3) and
        float(np.abs(img2 - rgb).max()) < 1e-6,
        f"FITS (C, H, W) lu en {img2.shape}, contenu intact")

# ================================================ [4] mono : inchangé
print("[4] Mono 2D : NAXIS1 = largeur, lecture inchangée")
mono = rng.normal(0.05, 0.01, (H, W)).astype(np.float32) + 0.05
p3 = os.path.join(tmp, "mono.fit")
save_image(p3, mono)
h3 = fits.getheader(p3)
verifie(int(h3["NAXIS1"]) == W and int(h3["NAXIS2"]) == H
        and "NAXIS3" not in h3,
        f"NAXIS=({h3['NAXIS1']},{h3['NAXIS2']}) — mono 2D intact")
m2 = load_image(p3)
verifie(m2.ndim == 2 and m2.shape == (H, W)
        and float(np.abs(m2 - mono).max()) < 1e-6,
        "mono : forme 2D et contenu identiques")

# ================================================ [5] PNG : inchangé
print("[5] PNG 16 bits : clip [0..1] inchangé")
try:
    import cv2
    p4 = os.path.join(tmp, "rgb.png")
    save_image(p4, np.clip(rgb, 0, 1))
    u = cv2.imread(p4, cv2.IMREAD_UNCHANGED)      # BGR
    verifie(u is not None and u.dtype == np.uint16
            and int(u.max()) > 30000, "PNG 16 bits écrit et lisible")
except ImportError:
    print("  (cv2 absent — skippé)")

print()
print("BANC AXES FITS COULEUR : TOUT AU VERT" if ok
      else "BANC AXES FITS COULEUR : ÉCHECS")
sys.exit(0 if ok else 1)
