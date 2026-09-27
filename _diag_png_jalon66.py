# -*- coding: utf-8 -*-
"""_diag_png_jalon66.py — qualification du « petit défaut sur les étoiles »
signalé par Alain (26/09/2026) dans la SAUVEGARDE PNG : « les étoiles moyennes
rouges sont bien plus rouges et ont presque un halo. Cela se produit aussi bien
dans le tel que vu stack que dans le tel que vu traité alors que l'affichage est
correct ».

Méthode (celle du jalon 62 qui avait attrapé la permutation R-B de v2.36.1) :
comparer PIXEL À PIXEL le PNG et le FITS du MÊME rendu, puis mesurer sur les
ÉTOILES ce que l'œil voit (profil radial de couleur autour des étoiles rouges).

Usage :  python _diag_png_jalon66.py [dossier]
Sortie : mesures chiffrées à l'écran (aucun fichier écrit, lecture seule).
"""

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

# Paire (libellé, base du nom) — mêmes noms que ceux donnés par Alain.
CAS = [
    ("tel que vu PILE  (stack traité)",
     "m31_stack_etire-telquevu_traite-v2.37.3"),
    ("tel que vu EXTERNE (traité)",
     "m31_traite_externe_etire-v2.373."),
]


def charger_fits(p):
    """FITS (3,H,W) ou (H,W,3) float → RGB flottant HWC, [] si absent."""
    if not os.path.isfile(p):
        return None
    d = np.asarray(fits.getdata(p), dtype=np.float32)
    if d.ndim == 3 and d.shape[0] == 3:
        d = np.transpose(d, (1, 2, 0))
    return d


def charger_png(p):
    """PNG → RGB flottant HWC [0..1] (uint16 conservé), None si absent."""
    if not os.path.isfile(p):
        return None
    u = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if u is None:
        return None
    brut = u
    if u.ndim == 3 and u.shape[2] == 3:
        u = cv2.cvtColor(u, cv2.COLOR_BGR2RGB)      # OpenCV rend du BGR
    prof = 65535.0 if u.dtype == np.uint16 else 255.0
    return np.asarray(u, np.float32) / prof, brut


def stats_titre(t):
    print("\n" + "=" * 74 + f"\n{t}\n" + "=" * 74)


def ecarts(a, b):
    """Écart absolu max et moyenne, en niveaux de 16 bits."""
    d = np.abs(a - b)
    return float(d.max()) * 65535.0, float(d.mean()) * 65535.0


def analyser_etoiles(rgb, etiq, n_max=8):
    """Trouve les étoiles ROUGES de luminosité MOYENNE et mesure le profil
    radial de couleur (R/G normalisé par le fond local, en anneaux).

    « Luminosité moyenne » = pic de luminance entre 1 % et 25 % du pic le plus
    fort de l'image : ce sont celles dont Alain dit qu'elles sont « bien plus
    rouges et ont presque un halo » (les étoiles saturées ne montrent rien).
    """
    if rgb is None:
        return []
    lum = rgb.mean(axis=2)
    seuil = float(np.percentile(lum, 99.93))
    mx = float(lum.max())
    dil = cv2.dilate(lum, np.ones((7, 7), np.float32))
    pics = (lum >= dil - 1e-9) & (lum > seuil)
    ys, xs = np.nonzero(pics)
    # tri par luminosité décroissante, on ne garde que la fenêtre « moyenne »
    ordre = np.argsort(-lum[ys, xs])
    h, w = lum.shape
    trouvees = []
    for i in ordre:
        y, x = int(ys[i]), int(xs[i])
        if not (30 <= y < h - 30 and 30 <= x < w - 30):
            continue
        if any(abs(y - t[0]) < 12 and abs(x - t[1]) < 12 for t in trouvees):
            continue                                  # déjà trouvée à côté
        p = float(lum[y, x])
        if not (0.01 * mx <= p <= 0.25 * mx):
            continue
        trouvees.append((y, x))
        if len(trouvees) >= n_max * 4:
            break
    lignes = []
    for (y, x) in trouvees:
        prof = couleur_radiale(rgb, y, x)
        if prof is None:
            continue
        rouge = prof[-1]
        lignes.append((rouge, y, x, prof))
    lignes.sort(reverse=True)                        # les plus ROUGES d'abord
    print(f"\n  {etiq} : {len(lignes)} étoiles rouges de luminosité moyenne "
          f"(pic 1-25 % du max {mx:.3f})")
    print("    (R/G = rapport au fond local, en multiples ; colonnes = rayons "
          "1-2, 3-4, 5-7, 8-11, 12-16 px)")
    for k, (rouge, y, x, prof) in enumerate(lignes[:n_max], 1):
        print(f"    #{k} (x={x:5d}, y={y:5d})  " +
              "  ".join(f"{v:5.2f}" for v in prof) +
              f"   ← halo R/G ×{rouge:.2f} à 12-16 px")
    return lignes


def couleur_radiale(rgb, y, x, anneaux=((1, 2), (3, 4), (5, 7), (8, 11), (12, 16)),
                    fond=(25, 34)):
    """Rapport R/G (et B/G) moyen par ANNEAU de rayon autour de (y, x), en
    multiples du même rapport mesuré dans l'anneau de FOND le plus externe.

    Un halo de couleur = un rapport qui reste au-dessus de 1 loin du cœur.
    """
    h, w, _ = rgb.shape
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt((yy - y) ** 2.0 + (xx - x) ** 2.0)
    y0, y1 = max(0, y - 40), min(h, y + 41)
    x0, x1 = max(0, x - 40), min(w, x + 41)
    sous = rgb[y0:y1, x0:x1]
    rr = r[y0:y1, x0:x1]
    m_fond = (rr >= fond[0]) & (rr <= fond[1])
    if int(m_fond.sum()) < 50:
        return None
    f = sous[m_fond].mean(axis=0)
    if f[1] <= 1e-6:
        return None
    ref = float(f[0]) / float(f[1])
    if ref <= 1e-6:
        return None
    out = []
    for (a, b) in anneaux:
        m = (rr >= a) & (rr < b)
        if int(m.sum()) < 12:
            out.append(0.0)
            continue
        moy = sous[m].mean(axis=0)
        out.append(float(moy[0] / max(moy[1], 1e-6)) / ref)
    return out


def main():
    for libelle, base in CAS:
        stats_titre(f"{libelle}  ({base})")
        f_fits = os.path.join(RACINE, base + ".fits")
        f_png = os.path.join(RACINE, base + ".png")
        fits_img = charger_fits(f_fits)
        png_img, png_brut = (None, None) if not os.path.isfile(f_png) \
            else charger_png(f_png)
        if fits_img is None or png_img is None:
            print(f"  fichiers absents : {f_fits} / {f_png}")
            continue
        print(f"  FITS : {fits_img.shape} float32   min {fits_img.min():.4f} "
              f"max {fits_img.max():.4f}")
        print(f"  PNG  : {png_brut.shape} {png_brut.dtype}   "
              f"(16 bits = {png_brut.dtype == np.uint16})")

        # ---- [1] Le PNG est-il bien le MÊME rendu que le FITS ? -------------
        ecart_max, ecart_moy = ecarts(fits_img, png_img)
        print(f"\n  [1] PNG vs FITS : écart max {ecart_max:.1f} / moyenne "
              f"{ecart_moy:.3f} (niveaux 16 bits)")
        for nom, variante in (
                ("R-B permutés", png_img[..., ::-1]),
                ("transposé", np.transpose(png_img, (1, 0, 2))),
                ("miroir vertical", png_img[::-1]),
                ("miroir horizontal", png_img[:, ::-1]),
                ("R-B permutés + transposé",
                 np.transpose(png_img[..., ::-1], (1, 0, 2)))):
            if variante.shape != fits_img.shape:
                continue
            m, _ = ecarts(fits_img, variante)
            if m < ecart_max:
                print(f"      ⚠ l'hypothèse « {nom} » colle MIEUX "
                      f"({m:.1f} au lieu de {ecart_max:.1f})")
        # le rendu a-t-il perdu de la précision (déjà quantifié en 8 bits ?)
        q = fits_img * 65535.0
        residu = float(np.abs(q - np.round(q)).max())
        print(f"      FITS quantifié au 1/65535 ? résidu max {residu:.4f} "
              f"niveau(x) — 0 = rendu déjà en 16 bits, ~255 = rendu en 8 bits")
        # où sont les écarts ?
        d = np.abs(fits_img - png_img).max(axis=2)
        nets = (d * 65535.0) > 1
        chaud = fits_img.max(axis=2) > 0.9
        print(f"      pixels d'écart > 1 niveau : {100.0 * float(nets.mean()):.3f} %"
              + (f"  ; parmi les pixels > 0,9 : écart max "
                 f"{float((d * 65535.0)[chaud].max()):.1f} niveaux"
                 if bool(chaud.any()) else ""))

        # ---- [2] Notre mesure : les étoiles rouges ont-elles un halo ? ------
        analyser_etoiles(fits_img, "FITS", n_max=6)
        analyser_etoiles(png_img, "PNG ", n_max=6)

        # ---- [3] Et à l'échelle de l'APERÇU de l'appli (1600 px de large) --
        ech = 1600.0 / fits_img.shape[1]
        petit = cv2.resize(fits_img, None, fx=ech, fy=ech,
                           interpolation=cv2.INTER_AREA)
        print(f"\n  [3] le même FITS réduit à l'APERÇU de l'appli "
              f"(facteur {ech:.3f} → {petit.shape[1]} px de large)")
        analyser_etoiles(petit, "FITS aperçu", n_max=6)


if __name__ == "__main__":
    main()
