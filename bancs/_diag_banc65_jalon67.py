# -*- coding: utf-8 -*-
"""_diag_banc65_jalon67.py — les DEUX points du banc jalon 65 qui bougent avec le
poids de structure (v2.37.5), mesurés côte à côte :

  ① le résidu sur le canal Y (le banc exige < 2e-05, mesuré 5,95e-05) — d'où
     vient-il exactement ?
  ② le grain chromatique du fond : σ contre MAD (le banc mesure un σ, sensible
     aux ~0,2 % de pixels que le masque PROTÈGE par construction).

Reproduit la scène du banc (ciel bleuté + étoiles de Moffat). Lecture seule.

Usage : python bancs/_diag_banc65_jalon67.py
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

from avastack.processing import couleurs as C

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

N = 600
yy, xx = np.mgrid[0:N, 0:N].astype(np.float64)
RNG = np.random.default_rng(20260926)
CIEL = (0.00120, 0.00140, 0.00170)
GRAIN = 0.0004
ROUGE, BLEUE, PALE = (1.00, 0.72, 0.42), (0.42, 0.70, 1.00), (0.85, 0.90, 1.00)
FORCE = 0.9


def moffat(cx, cy, fwhm, amp, beta=2.5):
    alpha = fwhm / (2.0 * np.sqrt(2.0 ** (1.0 / beta) - 1.0))
    r2 = (xx - cx) ** 2 + (yy - cy) ** 2
    return amp / (1.0 + r2 / alpha ** 2) ** beta


s = CIEL[0] * np.ones((N, N, 3), np.float32)
s[..., 0] += moffat(200, 200, 3.0, 2.6) * ROUGE[0]
s[..., 1] += moffat(200, 200, 3.0, 2.6) * ROUGE[1]
s[..., 2] += moffat(200, 200, 3.0, 2.6) * ROUGE[2]
s += moffat(420, 380, 3.0, 2.6)[..., None] * np.array(BLEUE, np.float32).reshape(1, 1, 3)
s += moffat(300, 480, 3.0, 0.10)[..., None] * np.array(PALE, np.float32).reshape(1, 1, 3)
s += RNG.normal(0.0, GRAIN, (N, N, 3)).astype(np.float32)
IMAGE = np.clip(s, 0.0, 1.0).astype(np.float32)
ZONE = (slice(30, 150), slice(450, 570))


def v2374(img, force=FORCE, rayon=3.0):
    """La formule de la v2.37.4 (sans masque) — pour comparer."""
    a = np.asarray(img, np.float32)
    ycc = cv2.cvtColor(a, cv2.COLOR_RGB2YCrCb)
    y = ycc[..., 0]
    den = np.maximum(np.minimum(y, cv2.GaussianBlur(y, (0, 0), sigmaX=rayon)),
                     np.float32(max(C.PLANCHER_CHROMA * float(np.median(y)), 1e-7)))
    for i in (1, 2):
        cn = (ycc[..., i] - 0.5) / den
        ycc[..., i] = 0.5 + den * (cn + np.float32(force)
                                   * (cv2.GaussianBlur(cn, (0, 0), sigmaX=rayon) - cn))
    return np.maximum(cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB),
                      np.float32(0.0)).astype(np.float32)


def chroma_absolue(img, force=FORCE, rayon=3.0):
    a = np.asarray(img, np.float32)
    ycc = cv2.cvtColor(a, cv2.COLOR_RGB2YCrCb)
    for i in (1, 2):
        c = ycc[..., i]
        ycc[..., i] = c + np.float32(force) * (
            cv2.GaussianBlur(c, (0, 0), sigmaX=rayon) - c)
    return np.maximum(cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB),
                      np.float32(0.0)).astype(np.float32)


def chroma_hf(img, zone=ZONE):
    z = np.asarray(img, np.float32)[zone]
    hf = z - cv2.GaussianBlur(z, (0, 0), sigmaX=2.0)
    d = hf[..., 0] - hf[..., 1]
    return float(d.std()), float(np.median(np.abs(d))) * 1.4826


y0 = cv2.cvtColor(IMAGE, cv2.COLOR_RGB2YCrCb)[..., 0]
print("① résidu sur le canal Y (max, et son emplacement)")
for nom, img in (("sans chroma", IMAGE),
                 ("v2.37.5 (masque)", C.reduire_bruit_chroma(IMAGE, force=FORCE)),
                 ("v2.37.4 (sans masque)", v2374(IMAGE)),
                 ("avant v2.37.3 (absolue)", chroma_absolue(IMAGE))):
    dy = np.abs(cv2.cvtColor(img, cv2.COLOR_RGB2YCrCb)[..., 0] - y0)
    iy, ix = np.unravel_index(int(np.argmax(dy)), dy.shape)
    print(f"    {nom:24s} max {float(dy.max()):.2e} en ({ix},{iy}) · "
          f"valeurs locales R {IMAGE[iy, ix, 0]:.4f} V {IMAGE[iy, ix, 1]:.4f} "
          f"B {IMAGE[iy, ix, 2]:.4f}")
print("② grain chromatique du fond (zone de ciel) : σ contre MAD")
for nom, img in (("sans chroma", IMAGE),
                 ("v2.37.4 (sans masque)", v2374(IMAGE)),
                 ("v2.37.5 (masque)", C.reduire_bruit_chroma(IMAGE, force=FORCE))):
    sg, md = chroma_hf(img)
    print(f"    {nom:24s} σ {sg:.6f} · MAD {md:.6f}")
