# -*- coding: utf-8 -*-
"""Test du jalon 11 — netteté live : module Richardson-Lucy
(`avastack/processing/sharpness.py`), module SEUL (le câblage live est le
jalon 12 : aucune fenêtre requise ici, le test est HEADLESS).

Vérifie :
  [1] API : cas dégénérés (1D, image constante, itérations/FWHM invalides),
      formes et types de sortie, NON-MUTATION de l'entrée, plafond
      d'itérations — JAMAIS d'exception, message explicite ;
  [2] CONFORMITÉ : le résultat doit coïncider avec une RL de référence
      écrite en numpy pur (convolution 2D explicite, bords réfléchis) —
      écart relatif < 1e-5. C'est la garantie que le module implémente bien
      LA formule de Richardson-Lucy (et non une variante approximative) ;
  [3] banc d'essai synthétique du plan (étoile FWHM 3,00 px + bruit) :
      resserrement croissant et plafonné, bruit de FOND non dégradé, coût ;
  [4] photométrie : le pic monte, le FLUX TOTAL de l'étoile est conservé ;
  [5] robustesse à une PSF FAUSSE de ±35 % (pas de creux sombre de fond —
      c'est le mode d'échec de Wiener, mesuré à −0,102 du pic au banc du
      16/09, qui a fait écarter Wiener) ;
  [6] couleur (H,W,3) : même resserrement que le mono, chromaticité INTACTE
      (luminance seule, comme SharpCap : aucun artéfact couleur) ;
  [7] repli explicite « pas de no-op silencieux » : sans étoiles, l'image est
      renvoyée INCHANGÉE avec la RAISON ; une mesure fournie évite une 2e
      mesure du seeing.

Exécution : python _test_rl_jalon11.py
"""
import sys
import time

import numpy as np

from avastack.processing import denoise as dn
from avastack.processing import sharpness as sh
from avastack.processing import stars as st

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def mad(x):
    """σ robuste (1,4826 × MAD) : mesure du bruit hors étoiles."""
    return 1.4826 * float(np.median(np.abs(x - np.median(x))))


def champ(shape, sigma_px, nb=40, bruit=0.006, fond=0.002,
          amp=(0.05, 0.6), graine=1, marge=25):
    """Champ synthétique : nb étoiles gaussiennes de σ connu + bruit."""
    rng = np.random.default_rng(graine)
    h, w = shape
    img = np.full((h, w), fond, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(nb):
        y = int(rng.integers(marge, h - marge))
        x = int(rng.integers(marge, w - marge))
        a = float(rng.uniform(*amp))
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * sigma_px ** 2))).astype(np.float32)
    img += rng.normal(0.0, bruit, img.shape).astype(np.float32)
    return img


def rl_reference(data, sigma_px, iterations):
    """RL de référence : convolution 2D EXPLICITE en numpy pur (aucune
    bibliothèque), bords réfléchis. Sert de juge au module (cf. [2])."""
    r = int(np.ceil(4 * sigma_px))
    t = np.arange(-r, r + 1, dtype=np.float64)
    k1 = np.exp(-0.5 * (t / sigma_px) ** 2)
    k1 /= k1.sum()
    noyau = np.outer(k1, k1)
    h, w = data.shape

    def conv2(x):
        p = np.pad(x, r, mode="reflect")
        out = np.zeros((h, w), dtype=np.float64)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                out += noyau[dy + r, dx + r] * p[r + dy:r + dy + h,
                                                 r + dx:r + dx + w]
        return out

    est = np.maximum(data.astype(np.float64), 0.0).copy()
    for _ in range(int(iterations)):
        est *= conv2(data / np.maximum(conv2(est), 1e-12))
    return est


print("[1] API : cas dégénérés, formes, non-mutation, plafond d'itérations")
sig3 = 3.0 / st.FWHM_PAR_SIGMA
img = champ((800, 1200), sig3)
ref_img = img.copy()
rgb = np.stack([img, img * 0.9, img * 0.6], axis=-1)
ref_rgb = rgb.copy()

plat = np.full((300, 400), 0.01, dtype=np.float32)
out, msg = sh.deconvoluer(plat, fwhm=3.0, iterations=5)
verifie(msg == "" and float(np.abs(out - plat).max()) == 0.0,
        "image constante + FWHM connue : rien n'est inventé (écart max 0), "
        f"msg={msg!r}")

out, msg = sh.deconvoluer(np.zeros(50, dtype=np.float32))
verifie(out.shape == (50,) and "dimensions inattendues" in msg,
        f"tableau 1D → message, pas d'exception (« {msg} »)")

plat_rgb = np.full((60, 80, 3), 0.01, dtype=np.float32)
out, msg = sh.deconvoluer(plat_rgb, fwhm=3.0)
verifie(out.shape == (60, 80, 3) and msg == "",
        f"couleur (H,W,3) conservée : {out.shape}")

out, msg = sh.deconvoluer(img, iterations=0)
verifie(np.array_equal(out, img) and "itérations invalide" in msg,
        f"itérations = 0 → image inchangée + « {msg} »")
out, msg = sh.deconvoluer(img, iterations="x")
verifie(np.array_equal(out, img) and "itérations invalide" in msg,
        f"itérations non numérique → image inchangée + « {msg} »")
out, msg = sh.deconvoluer(img, fwhm="x")
verifie(np.array_equal(out, img) and "FWHM invalide" in msg,
        f"FWHM non numérique → image inchangée + « {msg} »")
out, msg = sh.deconvoluer(img, fwhm=40.0)
verifie(np.array_equal(out, img) and "PSF hors bornes" in msg,
        f"FWHM démesurée → image inchangée + « {msg} »")
out, msg = sh.deconvoluer(img, fwhm=0.5)
verifie(np.array_equal(out, img) and "PSF hors bornes" in msg,
        f"FWHM trop étroite (étoile ~1 px, ringing) → « {msg} »")
out, msg = sh.deconvoluer(img, mesure=5)
verifie(np.array_equal(out, img) and "inutilisable" in msg,
        f"mesure de seeing d'un type inattendu → « {msg} »")
out, msg = sh.deconvoluer(np.full((20, 20), 0.01, dtype=np.float32))
verifie("petite" in msg and "inactive" in msg,
        f"image trop petite (mesure impossible) → « {msg} »")

o57, _ = sh.deconvoluer(img, iterations=5.7)
o5, _ = sh.deconvoluer(img, iterations=5)
o50, _ = sh.deconvoluer(img, iterations=50)
o10, _ = sh.deconvoluer(img, iterations=10)
verifie(np.array_equal(o57, o5), "itérations 5,7 → ramenées à 5 (entier)")
verifie(np.array_equal(o50, o10),
        f"PLAFOND dur respecté : 50 it == {sh.ITERATIONS_MAX} it");
verifie(np.array_equal(img, ref_img) and np.array_equal(rgb, ref_rgb),
        "images d'entrée jamais modifiées (mono et couleur)")
verifie(o5.dtype == np.float32 and o5.shape == img.shape,
        f"sortie float32 de même forme : {o5.dtype}, {o5.shape}")

print("[2] Conformité à une RL de référence (numpy pur, bords réfléchis)")
sig_small = 1.2
iso = np.full((121, 121), 0.002, dtype=np.float64)
yy, xx = np.mgrid[0:121, 0:121]
iso += 0.5 * np.exp(-((yy - 60) ** 2 + (xx - 60) ** 2)
                    / (2.0 * sig_small ** 2))
attendu = rl_reference(iso, sig_small, 5)
obtenu, msg = sh.deconvoluer(iso.astype(np.float32),
                             fwhm=sig_small * st.FWHM_PAR_SIGMA, iterations=5)
ecart_rel = float(np.abs(attendu - obtenu).max()) / float(attendu.max())
verifie(msg == "" and ecart_rel < 1e-5,
        f"5 it sur étoile isolée : écart relatif {ecart_rel:.2e} (< 1e-5) "
        f"avec la référence numpy")
verifie(float(attendu.max()) > 1.5 * float(iso.max()),
        f"la référence est bien LOIN de l'entrée (pic {iso.max():.4f} → "
        f"{attendu.max():.4f}) : le test discrimine")
for n in (1, 3, 10):
    a = rl_reference(iso, sig_small, n)
    b, _ = sh.deconvoluer(iso.astype(np.float32),
                          fwhm=sig_small * st.FWHM_PAR_SIGMA, iterations=n)
    e = float(np.abs(a - b).max()) / float(a.max())
    verifie(e < 1e-5, f"  {n:2d} it : écart relatif {e:.2e}")



print("[3] Banc d'essai synthétique : resserrement, bruit de fond, coût")
mes_av, err_av = st.mesurer_seeing(img)
fwhm_av = mes_av["fwhm"]
fond = img[0:20, :]                      # bandeau SANS étoile (marge = 25)
bruit_av, hf_av = mad(fond), dn.estimer_sigma(img)
verifie(err_av == "" and abs(fwhm_av - 3.0) / 3.0 < 0.05,
        f"FWHM mesurée avant netteté : {fwhm_av:.3f} px pour 3,000 px vrais "
        f"({mes_av['nb']} étoiles) — mesure du jalon 10")
fwhms = {}
for it in (3, 5, 10):
    t0 = time.perf_counter()
    out, msg = sh.deconvoluer(img, iterations=it)
    dt = time.perf_counter() - t0
    fwhms[it] = st.mesurer_seeing(out)[0].get("fwhm", 0.0)
    verifie(msg == "" and fwhms[it] < 0.9 * fwhm_av,
            f"{it:2d} it : FWHM {fwhm_av:.3f} → {fwhms[it]:.3f} px "
            f"({dt * 1000:.0f} ms sur 800×1200 px)")
verifie(fwhms[3] > fwhms[5] > fwhms[10],
        f"resserrement CROISSANT avec les itérations ({fwhms[3]:.2f} > "
        f"{fwhms[5]:.2f} > {fwhms[10]:.2f} px)")
verifie(1.6 < fwhms[5] < 2.1,
        f"réglage utile (5 it, défaut) : {fwhms[5]:.2f} px mesurés, "
        "conforme à la valeur documentée (≈1,8-1,9 px)")
out5, _ = sh.deconvoluer(img, iterations=5)
verifie(mad(out5[0:20, :]) <= 1.05 * bruit_av
        and dn.estimer_sigma(out5) <= 1.05 * hf_av,
        f"bruit de FOND non dégradé : MAD ×{mad(out5[0:20, :]) / bruit_av:.3f}, "
        f"hautes fréquences ×{dn.estimer_sigma(out5) / hf_av:.3f} "
        "(≤ 1,05 attendu)")
verifie(float(out5.std()) > 1.15 * float(img.std()),
        "⚠️ nuance consignée : l'écart-type GLOBAL, lui, monte ×"
        f"{float(out5.std()) / float(img.std()):.2f} — ce « bruit ×1,22 » du "
        "banc du 16/09 est le CONTRASTE gagné sur les pics d'étoiles, pas du "
        "bruit de fond")

print("[4] Photométrie : le pic monte, le FLUX TOTAL est conservé")
iso2 = np.full((200, 200), 0.002, dtype=np.float32)
yy, xx = np.mgrid[0:200, 0:200]
iso2 += (0.5 * np.exp(-((yy - 100) ** 2 + (xx - 100) ** 2)
                      / (2.0 * sig3 ** 2))).astype(np.float32)
iso2 += np.random.default_rng(7).normal(0.0, 0.006, iso2.shape).astype(np.float32)
out4, msg4 = sh.deconvoluer(iso2, fwhm=3.0, iterations=5)
fen = (slice(60, 140), slice(60, 140))
pic = float(out4[fen].max()) / float(iso2[fen].max())
flux = float(out4[fen].sum()) / float(iso2[fen].sum())
verifie(msg4 == "" and pic > 1.8,
        f"pic de l'étoile ×{pic:.2f} (résolution restaurée)")
verifie(abs(flux - 1.0) < 0.02,
        f"flux total conservé ×{flux:.3f} (±2 %) — photométrie préservée")

print("[5] Robustesse à une PSF FAUSSE de ±35 % (Wiener, lui, s'effondrait)")
for fac in (0.65, 1.35):
    out_w, msg_w = sh.deconvoluer(img, fwhm=3.0 * fac, iterations=5)
    f_w = st.mesurer_seeing(out_w)[0].get("fwhm", 0.0)
    creux = float(out_w[0:20, :].min()) - float(img[0:20, :].min())
    verifie(msg_w == "" and f_w < 0.9 * fwhm_av,
            f"PSF ×{fac:.2f} : FWHM {fwhm_av:.3f} → {f_w:.3f} px (pas "
            "d'effondrement)")
    verifie(creux > -0.01,
            f"PSF ×{fac:.2f} : creux du fond {creux:+.5f} — pas de halo "
            "sombre (Wiener mesurait −0,102 du pic)")



print("[6] Couleur (H,W,3) : luminance seule, chromaticité intacte")
out_c, msg_c = sh.deconvoluer(rgb, fwhm=3.0, iterations=5)
verifie(msg_c == "" and out_c.shape == rgb.shape and out_c.dtype == np.float32,
        f"sortie couleur de même forme : {out_c.shape}, {out_c.dtype}")
verifie(bool(np.isfinite(out_c).all()),
        "aucun NaN/Inf produit sur une image couleur")
f_c = st.mesurer_seeing(out_c)[0].get("fwhm", 0.0)
verifie(f_c < 0.9 * fwhm_av,
        f"luminance resserrée comme en mono : {fwhm_av:.3f} → {f_c:.3f} px")
zone = (slice(300, 400), slice(300, 400))
av = img[zone] / (img[zone] * 0.9)
ap = out_c[zone + (0,)] / out_c[zone + (1,)]
verifie(float(np.abs(av - ap).max()) < 1e-5,
        "rapport R/G inchangé (écart max "
        f"{float(np.abs(av - ap).max()):.2e}) : aucun artéfact couleur")
verifie(float(np.abs(out_c[..., 0] - out5).max()) / float(out5.max()) < 0.05,
        "mono (H,W) et couleur (H,W,3) donnent la MÊME netteté (écart relatif "
        f"{float(np.abs(out_c[..., 0] - out5).max()) / float(out5.max()):.2e})")
verifie(float(out_c[..., 1].max()) < float(out_c[..., 0].max())
        and float(out_c[..., 2].max()) < float(out_c[..., 1].max()),
        "l'ordre des canaux est préservé (0 > 1 > 2 en éclat)")

print("[7] Repli explicite « pas de no-op silencieux »")
sans = (0.01 + np.random.default_rng(3).normal(0, 0.006, (300, 400))
        ).astype(np.float32)
out, msg = sh.deconvoluer(sans)
verifie(np.array_equal(out, sans) and "inactive" in msg
        and "étoiles" in msg,
        f"champ sans étoile : image INCHANGÉE + raison affichée (« {msg} »)")
deux = (0.002 + np.random.default_rng(5).normal(0, 0.006, (300, 400))
        ).astype(np.float32)
yy, xx = np.mgrid[0:300, 0:400]
deux += (0.5 * np.exp(-((yy - 100) ** 2 + (xx - 100) ** 2)
                      / (2.0 * sig3 ** 2))).astype(np.float32)
deux += (0.3 * np.exp(-((yy - 200) ** 2 + (xx - 300) ** 2)
                      / (2.0 * sig3 ** 2))).astype(np.float32)
out, msg = sh.deconvoluer(deux)
verifie(np.array_equal(out, deux) and "inactive" in msg,
        f"2 étoiles (< {st.MIN_ETOILES}) : netteté REFUSÉE explicitement "
        f"(« {msg} »)")
out, msg = sh.deconvoluer(sans, mesure={"nb": 40, "fwhm": 2.5})
verifie(msg == "" and not np.array_equal(out, sans),
        "mesure de seeing FOURNIE (cache du solveur) : la netteté "
        "s'applique sans refaire la mesure, même sans étoile détectée ici")
out, msg = sh.deconvoluer(sans, fwhm=2.5)
verifie(msg == "" and not np.array_equal(out, sans),
        "FWHM explicite : la netteté s'applique sans aucune mesure")

print()
print("JALON 11 : " + ("TOUS LES TESTS PASSENT" if ok
                       else "ÉCHECS — à corriger"))
sys.exit(0 if ok else 1)

