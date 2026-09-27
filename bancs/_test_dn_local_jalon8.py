# -*- coding: utf-8 -*-
"""Test du jalon 8 — module de débruitage LOCAL (ondelettes à trous +
Non-local means, numpy/OpenCV).

Vérifie (HEADLESS, sans fenêtre) :
  - la transformée à trous reconstruit EXACTEMENT l'image (somme des
    couches + couche résiduelle = entrée) ;
  - les deux algorithmes réduisent réellement le bruit du fond tout en
    PRÉSERVANT les étoiles (test numérique sur image synthétique) ;
  - l'API denoiser() : mono/RGB, méthode inconnue, force hors bornes,
    image d'entrée jamais modifiée.

Le câblage UI du débruitage externe (combobox de méthode, force, 8-tuple,
chaîne gradient → local → BXT, persistance) est vérifié par
_test_dn_jalon7.py ; le câblage LIVE (solveur, cache, vue « traitée »,
« tel que vu », persistance) par _test_denoise_live_jalon9.py. Ce test
reste focalisé sur le module, indépendant de l'organisation de l'interface.

Exécution : python bancs/_test_dn_local_jalon8.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import time

import numpy as np

from avastack.processing import denoise as dn

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# Outil externe SIMULÉ (comme jalon 7) : copie l'entrée sur la sortie et
# journalise son étiquette (argv[4]) pour vérifier l'ORDRE des étapes.
FAKE_TOOL = r"""
import sys
import numpy as np
from astropy.io import fits
d = fits.getdata(sys.argv[1])
fits.PrimaryHDU(np.asarray(d, dtype=np.float32)).writeto(sys.argv[2],
                                                         overwrite=True)
if len(sys.argv) > 4:
    with open(sys.argv[3], "a", encoding="utf-8") as f:
        f.write(sys.argv[4] + "\n")
"""

print("[1] Transformée à trous : reconstruction exacte")
img = np.random.default_rng(0).random((128, 96), dtype=np.float32)
c_prev = img
somme_w = np.zeros_like(img)
for n in range(dn._NIVEAUX):
    c = dn._etage(c_prev, n)
    somme_w += c_prev - c
    c_prev = c
verifie(float(np.abs(c_prev + somme_w - img).max()) < 1e-5,
        "c_N + Σw_i = image initiale (reconstruction exacte, à 1e-5 près)")

print("[2] Efficacité : image synthétique (étoiles + fond + bruit)")
rng = np.random.default_rng(1)
img = np.full((1000, 1600), 0.01, dtype=np.float32)
yy, xx = np.mgrid[0:1000, 0:1600]
for _ in range(60):
    y, x = int(rng.integers(30, 970)), int(rng.integers(30, 1570))
    a = rng.uniform(0.05, 0.5)
    s2 = rng.uniform(1.0, 2.2)
    img += (a * np.exp(-((xx - x) ** 2 + (yy - y) ** 2)
                       / (2 * s2 * s2))).astype(np.float32)
img += rng.normal(0, 0.008, img.shape).astype(np.float32)
mq = img < 0.02                       # zones du fond sans étoile
for methode in ("ondelettes", "nlm"):
    t0 = time.time()
    out, err = dn.denoiser(img, methode, 0.5)
    dt = time.time() - t0
    b_av = img[mq].std()
    b_ap = out[mq].std()
    verifie(err == "", f"{methode} : aucun erreur (t = {dt:.2f} s)")
    verifie(b_ap < 0.8 * b_av,
            f"{methode} : bruit du fond réduit de ≥ 20 % "
            f"({b_av:.5f} → {b_ap:.5f})")
    if methode == "ondelettes":
        verifie(abs(out.max() - img.max()) < 0.05 * img.max(),
                f"ondelettes : étoiles épargnées (pic {img.max():.4f} → "
                f"{out.max():.4f})")

print("[3] API denoiser : RGB, erreurs, non-mutation")
rgb = np.stack([img, img * 0.9, img * 0.5], axis=-1)
for methode in ("ondelettes", "nlm"):
    out, err = dn.denoiser(rgb, methode, 0.5)
    verifie(err == "" and out.shape == rgb.shape
            and out.dtype == np.float32,
            f"{methode} : RGB {rgb.shape} → {out.shape} float32")
img_avant = img.copy()
dn.denoiser(img, "ondelettes", 0.5)
verifie(np.array_equal(img, img_avant), "image d'entrée jamais modifiée")
out, err = dn.denoiser(img, "zzz", 0.5)
verifie(err != "" and np.array_equal(out, img),
        "méthode inconnue → message d'erreur + image intacte")
out, err = dn.denoiser(img, "ondelettes", 7.0)
verifie(err == "", "force hors bornes → clampée, pas de crash")

print("[3bis] Entrée avec pixels invalides (NaN/Inf) — retour réel v2.9.0")
import warnings
piege = img.copy()
piege[10, 10] = np.nan
piege[20, 20] = np.inf
piege[30, 30] = -np.inf
for methode in ("ondelettes", "nlm"):
    with warnings.catch_warnings():
        warnings.simplefilter("error")   # tout RuntimeWarning = échec
        out, err = dn.denoiser(piege, methode, 0.5)
    verifie(err == "" and np.isfinite(out).all(),
            f"{methode} : NaN/Inf sanitisés, sortie finie, sans warning "
            f"(err={err!r})")

# NB : le cÂBLAGE UI du débruitage externe (combobox de méthode, force,
# 8-tuple, chaîne gradient → local → BXT, persistance) est vérifié par
# _test_dn_jalon7.py ; le câblage LIVE (solveur, cache, vue « traitée »,
# « tel que vu », persistance) par _test_denoise_live_jalon9.py. Ce test
# reste focalisé sur le module, indépendant de l'organisation de l'interface.

print()
print("MODULE DÉBRUITAGE : " + ("TOUS LES TESTS PASSENT" if ok
                                else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
