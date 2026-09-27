# -*- coding: utf-8 -*-
"""_diag_veralux_resolution_jalon66.py — POURQUOI le même étirement VeraLux,
appliqué à l'APERÇU (1600 px, ce qu'Alain voit) et au FICHIER (3839 px), donne
des étoiles rouges très différentes (mesuré : R/G cœur 1,28 à l'écran contre
3,13 dans le fichier, pour une entrée linéaire identique à R/G 1,20).

Le moteur « Ready-to-Use » de VeraLux (code TIERS, jamais modifié) contient
TROIS constantes calculées SUR L'IMAGE :
  ① `calculate_anchor_adaptive` : ancre = pied du pic d'histogramme de la
     luminance (fenêtre de 50 bins), donc sensible à la LARGEUR DU BRUIT — le
     grain de l'aperçu est moyenné par la réduction, celui du fichier non ;
  ② `global_floor = median_L − 2,7·σ_L` (σ_L dominé par le bruit) ;
  ③ `soft_ceil` = 99ᵉ percentile par canal.
Ces trois constantes pilotent la dérive des couleurs SOMBRES : une ancre ou un
plancher plus bas laisse le résidu de ciel dans le rapport (C−ancre)/(L−ancre)
que le moteur utilise comme couleur, et l'amplifie donc au-delà du rapport
réel. Ce banc REJOUE la chaîne du moteur (en appelant SES méthodes, copie de
`process_veralux_ready_to_use` pour la mesure seulement) et compare :
  (a) le fichier pleine résolution tel quel ;
  (b) le fichier avec l'ANCRE de l'aperçu ;
  (c) le fichier avec l'ancre ET les constantes de sortie de l'aperçu.

Usage : python bancs/_diag_veralux_resolution_jalon66.py [dossier]
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

import numpy as np
import cv2
from astropy.io import fits

RACINE = sys.argv[1] if len(sys.argv) > 1 else r"C:\Astro\test"

try:                          # sortie console : jamais de plantage d'encodage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from avastack.processing import veralux as _veralux          # noqa: E402
import veralux_core_headless as VC                           # noqa: E402

PROFIL = "Sony IMX585 (ASI585) - STARVIS 2"
TARGET_BG = 0.16
LARGEUR_APERCU = 1600.0
PEDESTAL = 0.001
SOFT_CEIL_PCT = 99.0

LIGNE = "M31_traite_lineaire_2.37.3.fits"       # vue « empilement » (pile)
ETOILES = [(194, 105), (658, 371), (1150, 737), (1276, 167)]   # px d'aperçu


def _poids():
    return VC.SENSOR_PROFILES[PROFIL]["weights"]


def _pct99(ch):
    stride = max(1, ch.size // 500000)
    return float(np.percentile(ch.flatten()[::stride], SOFT_CEIL_PCT))


def chaine(img, logd, anchor=None, constantes=None, b=6.0, n_pow=3.5):
    """COPIE de `process_veralux_ready_to_use` (moteur tiers) pour la MESURE :
    mêmes appels aux mêmes méthodes, mais l'ancre et les constantes de sortie
    peuvent être SUBSTITUÉES pour tester leur rôle.

    → (image finale [0,1], infos) ; `infos` porte les constantes réellement
    utilisées et les valeurs intermédiaires au pixel le plus brillant.
    """
    rw, gw, bw = _poids()
    x = VC.VeraLuxCore.normalize_input(img)
    if x.ndim == 3 and x.shape[0] != 3 and x.shape[2] == 3:
        x = x.transpose(2, 0, 1)
    ancre = (float(anchor) if anchor is not None
             else VC.VeraLuxCore.calculate_anchor_adaptive(x, weights=(rw, gw, bw)))
    La, xa = VC.VeraLuxCore.extract_luminance(x, ancre, (rw, gw, bw))
    L_safe = La + 1e-9
    Ls = np.clip(VC.VeraLuxCore.hyperbolic_stretch(La, 10.0 ** logd, b), 0.0, 1.0)
    k = np.power(Ls, n_pow)
    final = np.empty_like(x)
    for i in range(3):
        ratio = xa[i] / L_safe
        final[i] = Ls * (ratio * (1.0 - k) + 1.0 * k)
    final = (final * (1.0 - 0.005) + 0.005).astype(np.float32)
    final = np.clip(final, 0.0, 1.0)
    # --- constantes de adaptive_output_scaling (mêmes formules que le moteur)
    L_raw = rw * final[0] + gw * final[1] + bw * final[2]
    med_L, std_L, min_L = (float(np.median(L_raw)), float(np.std(L_raw)),
                           float(np.min(L_raw)))
    plancher = max(min_L, med_L - 2.7 * std_L)
    abs_max = float(np.max(L_raw))
    valide_max = True
    if abs_max > 0.001:
        y, xx = np.unravel_index(int(np.argmax(L_raw)), L_raw.shape)
        fen = L_raw[max(0, y - 1):y + 2, max(0, xx - 1):xx + 2]
        voisins = fen[fen < abs_max]
        if voisins.size and float(np.max(voisins)) < abs_max * 0.20:
            valide_max = False
    plafond = max(_pct99(final[0]), _pct99(final[1]), _pct99(final[2]))
    if plafond <= plancher:
        plafond = plancher + 1e-6
    if abs_max <= plafond:
        abs_max = plafond + 1e-6
    ech_contraste = (0.98 - PEDESTAL) / (plafond - plancher + 1e-9)
    ech_limite = (1.0 - PEDESTAL) / (abs_max - plancher + 1e-9)
    echelle = min(ech_contraste, ech_limite) if valide_max else ech_contraste
    if constantes is not None:                  # substitution (test)
        plancher = constantes["plancher"]
        echelle = constantes["echelle"]
    for i in range(3):
        final[i] = np.clip((final[i] - plancher) * echelle + PEDESTAL, 0.0, 1.0)
    L = rw * final[0] + gw * final[1] + bw * final[2]
    bg = float(np.median(L))
    m = float("nan")
    if 0.0 < bg < 1.0 and abs(bg - TARGET_BG) > 1e-3:
        m = (bg * (TARGET_BG - 1.0)) / (bg * (2.0 * TARGET_BG - 1.0) - TARGET_BG)
        if constantes is not None and "m" in constantes:
            m = float(constantes["m"])
        for i in range(3):
            final[i] = VC.VeraLuxCore.apply_mtf(final[i], m)
    # `apply_ready_to_use_soft_clip`
    for i in range(3):
        c = final[i]
        masque = c > 0.98
        if np.any(masque):
            t = np.clip((c[masque] - 0.98) / (1.0 - 0.98 + 1e-9), 0.0, 1.0)
            c[masque] = 0.98 + 0.02 * (1.0 - np.power(1.0 - t, 2.0))
            final[i] = np.clip(c, 0.0, 1.0)
    infos = {"ancre": ancre, "plancher": plancher, "echelle": echelle,
             "plafond": plafond, "med_L": med_L, "std_L": std_L,
             "min_L": min_L, "max_valide": valide_max, "bg": bg, "m": m}
    return np.transpose(final, (1, 2, 0)), infos


def reduire(img):
    h, w = img.shape[:2]
    ech = min(1.0, LARGEUR_APERCU / float(max(h, w)))
    if ech >= 1.0:
        return np.ascontiguousarray(img), 1.0
    return cv2.resize(img, None, fx=ech, fy=ech,
                      interpolation=cv2.INTER_AREA), ech


def bruit_ciel(lum, marge=60):
    """σ du fond (MAD robuste) sur les BORDS de l'image (ciel sans galaxie)."""
    bord = np.concatenate((lum[:marge].ravel(), lum[-marge:].ravel(),
                           lum[:, :marge].ravel(), lum[:, -marge:].ravel()))
    med = float(np.median(bord))
    return med, float(np.median(np.abs(bord - med)) * 1.4826)


def rg_coeur(img, x, y, echelle=1.0, r=3.0, fond=(28, 40)):
    """R/G maximal dans un rayon `r` (px d'aperçu) autour de (x, y), normalisé
    par le R/G du fond local — la mesure « étoile rouge » du banc."""
    h, w = img.shape[:2]
    xf, yf = x * echelle, y * echelle
    demi = int(round((fond[1] + 4) * echelle))
    y0, y1 = max(0, int(yf) - demi), min(h, int(yf) + demi + 1)
    x0, x1 = max(0, int(xf) - demi), min(w, int(xf) + demi + 1)
    sous = np.asarray(img[y0:y1, x0:x1], np.float64)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    rr = np.sqrt((yy - yf) ** 2.0 + (xx - xf) ** 2.0) / echelle
    m_fond = (rr >= fond[0]) & (rr <= fond[1])
    if int(m_fond.sum()) < 40:
        return np.nan
    f = sous[m_fond].mean(axis=0)
    ref = f[0] / max(f[1], 1e-12)
    m_coeur = rr <= r
    if int(m_coeur.sum()) < 4:
        return np.nan
    c = sous[m_coeur].mean(axis=0)
    return float((c[0] / max(c[1], 1e-12)) / ref)


def main():
    lin = _veralux.normaliser_lin(np.asarray(
        fits.getdata(os.path.join(RACINE, LIGNE)), np.float32))
    if lin.ndim == 3 and lin.shape[0] == 3:
        lin = np.transpose(lin, (1, 2, 0))
    petit, ech = reduire(lin)
    lum_f = lin.mean(axis=2)
    lum_p = petit.mean(axis=2)
    med_f, sg_f = bruit_ciel(lum_f)
    med_p, sg_p = bruit_ciel(lum_p)
    print(f"ciel plein format : {med_f:.5f} + σ {sg_f:.5f}   |   "
          f"ciel de l'aperçu (×{ech:.3f}) : {med_p:.5f} + σ {sg_p:.5f}   "
          f"→ le grain de l'aperçu vaut {sg_p / sg_f:.2f} × celui du fichier")

    # logD : celui de l'appli (résolu sur l'aperçu, mode « fond cible »)
    _, logd, _ = _veralux.etirer(petit, mode=_veralux.MODE_TARGET_BG,
                                 target_bg=TARGET_BG, profil=PROFIL)
    print(f"\nlogD résolu sur l'aperçu : {logd:.4f} (utilisé pour les DEUX)")

    print("\n--- ÉCRAN : chaîne du moteur sur l'APERÇU ---")
    ecran, i_p = chaine(petit, logd)
    for k in ("ancre", "plancher", "echelle", "plafond", "std_L", "bg", "m"):
        print(f"    {k:9s} {i_p[k]:.6f}")
    print("\n--- FICHIER : chaîne du moteur sur la PLEINE RÉSOLUTION ---")
    fich, i_f = chaine(lin, logd)
    for k in ("ancre", "plancher", "echelle", "plafond", "std_L", "bg", "m"):
        print(f"    {k:9s} {i_f[k]:.6f}")
    print(f"    → ancre fichier / ancre écran = {i_f['ancre'] / max(i_p['ancre'], 1e-12):.3f}"
          f" ; plancher fichier / plancher écran = "
          f"{i_f['plancher'] / max(i_p['plancher'], 1e-12):.3f}")

    # variantes : qu'est-ce qui ramène le fichier sur l'écran ?
    v_b, _ = chaine(lin, logd, anchor=i_p["ancre"])
    v_c, _ = chaine(lin, logd,
                    constantes={"plancher": i_p["plancher"],
                                "echelle": i_p["echelle"], "m": i_p["m"]})
    v_d, _ = chaine(lin, logd, anchor=i_p["ancre"],
                    constantes={"plancher": i_p["plancher"],
                                "echelle": i_p["echelle"], "m": i_p["m"]})
    v_e, _ = chaine(petit, logd)         # rappel : l'écran lui-même

    print(f"\n  R/G au cœur (moyenne dans r ≤ 3 px d'aperçu, × le R/G du fond)")
    print(f"    {'étoile':>14} {'écran':>7} {'fichier':>8} "
          f"{'fich.+ancre':>12} {'fich.+const':>12} {'fich.+les 2':>12}")
    for (x, y) in ETOILES:
        print(f"    {f'({x},{y})':>14} "
              f"{rg_coeur(ecran, x, y):7.2f} {rg_coeur(fich, x, y, 1.0 / ech):8.2f} "
              f"{rg_coeur(v_b, x, y, 1.0 / ech):12.2f} "
              f"{rg_coeur(v_c, x, y, 1.0 / ech):12.2f} "
              f"{rg_coeur(v_d, x, y, 1.0 / ech):12.2f}")
    print("    (rappels : écran = appli ; fichier = ce que l'appli écrit ; "
          "fich.+ancre = fichier avec l'ANCRE de l'écran, etc.)")
    print(f"\n  écart global ÉCRAN vs FICHIER : moyenne "
          f"{float(np.mean(np.abs(ecran - _red(fich, ecran.shape)))):.4f}")


def _red(img, forme):
    return cv2.resize(img, (forme[1], forme[0]), interpolation=cv2.INTER_AREA)


if __name__ == "__main__":
    main()
