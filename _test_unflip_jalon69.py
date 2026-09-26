# -*- coding: utf-8 -*-
"""Banc v2.38.2 — `auto_unflip` REDRESSE-T-IL VRAIMENT LE RÉSULTAT DU ⚡ ?

DÉFAUT MESURÉ (27/09/2026, fichiers réels d'Alain) : le résultat de la chaîne
EXTERNE (GraXpert + BXT) était enregistré ET affiché **en miroir vertical**
(v2.373, v2.38.0, v2.38.1), parce que la mesure de comparaison d'`auto_unflip`
— une corrélation de Pearson sur les images LINÉAIRES brutes, sous-échantillonnées
« 1 pixel sur N » — était écrasée par les quelques pixels du cœur : les deux
orientations donnaient +0,1085 (droite) contre +0,1212 (miroir), écart +0,0127,
SOUS la marge de 0,05 → aucun redressement.

Vérifie :
  [1] sur une scène qui reproduit le MÉCANISME du défaut (galaxie asymétrique à
      fort écart dynamique + gradient de pollution lumineuse + grain, « sortie
      d'outil » = gradient retiré + débruitée + accentuée + échelle ≠, puis
      RETOURNÉE) : la fonction REDRESSE, avec le TÉMOIN de l'ancienne formule
      ré-écrite qui, lui, ne voit rien ;
  [2] AUCUN faux positif : image déjà droite, miroir HORIZONTAL (on ne corrige
      que le vertical), images sans structure, formes différentes ;
  [3] sur les VRAIS fichiers linéaires du ⚡ (section sautée s'ils sont absents) :
      l'ancienne formule ne corrigeait pas, la nouvelle corrige.

Exécution : python _test_unflip_jalon69.py
"""
import os
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

from avastack.images import auto_unflip, load_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def auto_unflip_v2381(proc, ref):
    """TÉMOIN : la formule d'AVANT la v2.38.2, ré-écrite ici exprès —
    corrélation de Pearson sur les images LINÉAIRES brutes, sous-échantillonnage
    « 1 pixel sur N » (celle qui laissait passer le miroir)."""
    a = proc if proc.ndim == 2 else proc.mean(axis=2)
    b = ref if ref.ndim == 2 else ref.mean(axis=2)
    if a.shape != b.shape:
        return proc
    a = a[::max(1, a.shape[0] // 256), ::max(1, a.shape[1] // 256)]
    b = b[::max(1, b.shape[0] // 256), ::max(1, b.shape[1] // 256)]
    a, b = a.astype(np.float64), b.astype(np.float64)

    def corr(x, y):
        x, y = x - x.mean(), y - y.mean()
        d = np.sqrt((x * x).sum() * (y * y).sum())
        return float((x * y).sum() / d) if d > 0 else 0.0

    c_droite, c_miroir = corr(a, b), corr(a, b[::-1])
    print(f"      (témoin v2.38.1 : droite {c_droite:+.4f} · "
          f"miroir {c_miroir:+.4f} — écart {c_miroir - c_droite:+.4f})")
    return proc[::-1] if c_miroir > c_droite + 0.05 else proc


def scene_defaut(h=900, w=1400, graine=6901):
    """Scène de banc FRANCHEMENT ASYMÉTRIQUE en vertical (c'est ce qui permet de
    trancher un miroir haut-bas) : noyau de galaxie DÉCENTRÉ, bande de poussière
    oblique, deux satellites différents, champ d'étoiles, gradient de pollution
    lumineuse. L'« outil externe » rend une version modifiée (gradient retiré,
    débruitée, accentuée, autre échelle) : on la retourne, comme le fait le CLI
    rc-astro.

    NB : sur une scène AUSSI propre, l'ancienne formule tranche aussi — c'est le
    fichier RÉEL d'Alain (section [3]) qui reproduit le défaut, parce que le ⚡
    travaille sur un instantané DIFFÉRENT de l'empilement sauvegardé (grains et
    textures fines non superposés) : mesuré, la corrélation brute y tombe à
    +0,1085 / +0,1212 (indécidable). Le mécanisme est mesuré par
    `_diag_unflip_mecanisme.py`."""
    rng = np.random.default_rng(graine)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    # galaxie inclinée, noyau DÉCENTRÉ vers le haut (rien de symétrique)
    dy = (yy - 0.38 * h)
    dx = (xx - 0.45 * w)
    ang = np.deg2rad(28.0)
    u = dx * np.cos(ang) + dy * np.sin(ang)
    v = -dx * np.sin(ang) + dy * np.cos(ang)
    rr = np.sqrt((u / (0.30 * w)) ** 2 + (v / (0.10 * h)) ** 2)
    gal = 0.55 * np.exp(-rr ** 2 * 2.4) + 0.10 * np.exp(-rr ** 2 * 0.5)
    bande = np.abs(v - 0.02 * h) / (0.025 * h)
    gal *= (1.0 - 0.65 * np.exp(-bande ** 2))
    for (cx, cy, amp, sig) in ((0.62 * w, 0.20 * h, 0.20, 0.006 * h),
                               (0.28 * w, 0.66 * h, 0.05, 0.010 * h)):
        gal += amp * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / sig ** 2)
    for _ in range(120):                        # champ d'étoiles asymétrique
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        gal += rng.uniform(0.05, 0.35) * np.exp(
            -((xx - cx) ** 2 + (yy - cy) ** 2) / (1.8 ** 2))
    grad = 1.0 + 1.6 * (yy / h) + 0.4 * (xx / w)      # pollution lumineuse
    grain = 0.0015
    brut = (0.028 + gal) * grad + rng.normal(0.0, grain, (h, w))
    brut = np.clip(brut, 0.0, None).astype(np.float32)
    # « sortie d'outil » : gradient retiré (Division), débruitée, accentuée,
    # AUTRE échelle, et sa PROPRE texture fine (indépendante de la nôtre).
    out = brut / grad
    out = cv2.GaussianBlur(out, (0, 0), sigmaX=1.2)
    out = out + 1.5 * (out - cv2.GaussianBlur(out, (0, 0), sigmaX=2.5))
    out = out + rng.normal(0.0, grain, (h, w))
    return brut, (out * 0.85).astype(np.float32)




def correlations_v2382(proc, ref):
    """La mesure de la v2.38.2, répliquée ici pour l'AFFICHER (images étirées et
    normalisées, sous-échantillonnage par moyenne). → (droite, miroir)."""
    a = proc if proc.ndim == 2 else proc.mean(axis=2)
    b = ref if ref.ndim == 2 else ref.mean(axis=2)
    ech = max(1.0, max(a.shape) / 256.0)
    taille = (max(8, int(round(a.shape[1] / ech))),
              max(8, int(round(a.shape[0] / ech))))

    def prep(x):
        y = cv2.resize(np.asarray(x, np.float32), taille,
                       interpolation=cv2.INTER_AREA)
        bas, haut = (float(v) for v in np.percentile(y, (0.5, 99.5)))
        y = np.clip((y - bas) / max(1e-9, haut - bas), 0.0, 1.0)
        return np.sqrt(y).astype(np.float64)

    a, b = prep(a), prep(b)

    def corr(x, y):
        x, y = x - x.mean(), y - y.mean()
        d = np.sqrt((x * x).sum() * (y * y).sum())
        return float((x * y).sum() / d) if d > 0 else 0.0

    c1, c2 = corr(a, b), corr(a, b[::-1])
    print(f"      (mesure v2.38.2 : droite {c1:+.4f} · miroir {c2:+.4f} — "
          f"écart {c2 - c1:+.4f})")
    return c1, c2


print("=" * 78)
print("[1] scène qui reproduit le défaut : le miroir est-il redressé ?")
print("=" * 78)
brut, outil = scene_defaut()
rendu = auto_unflip(np.flipud(outil).copy(), brut)
verifie(np.allclose(rendu, outil, atol=1e-6),
        "la fonction REDRESSE la sortie retournée par l'outil")
# TÉMOIN de l'ancienne formule : sur une scène AUSSI propre, elle tranche aussi
# (l'information est imprimée) — c'est la section [3], sur ses VRAIS fichiers,
# qui démontre le défaut (le témoin y est aveugle).
auto_unflip_v2381(np.flipud(outil).copy(), brut)
correlations_v2382(np.flipud(outil).copy(), brut)

print()
print("=" * 78)
print("[2] aucun faux positif")
print("=" * 78)
verifie(np.allclose(auto_unflip(outil.copy(), brut), outil, atol=1e-6),
        "image déjà dans le bon sens : NON touchée (marge non atteinte)")
verifie(np.allclose(auto_unflip(outil[:, ::-1].copy(), brut),
                    outil[:, ::-1], atol=1e-6),
        "miroir HORIZONTAL : non touché (seul le vertical est corrigé)")
plat = np.full((400, 400), 0.03, np.float32)
plat += np.random.default_rng(1).normal(0.0, 0.001, plat.shape).astype(
    np.float32)
verifie(np.allclose(auto_unflip(plat.copy(), plat), plat, atol=1e-6),
        "image sans structure (bruit seul) dans le bon sens : non touchée")
verifie(np.allclose(auto_unflip(np.zeros((10, 20), np.float32),
                                np.zeros((30, 20), np.float32)),
                    np.zeros((10, 20), np.float32)),
        "formes différentes : renvoyée telle quelle (jamais de risque)")

print()
print("=" * 78)
print("[3] les VRAIS fichiers linéaires du ⚡ (sautée s'ils sont absents)")
print("=" * 78)
EMP = r"C:\Astro\test\M31_traite_lineaire_2.38.0.fits"
EXT = r"C:\Astro\test\m31_traite_externe_lineaire-v2.38.0.fits"


def orientation(img, ref, cote=160, ech=8):
    """Mesure INDÉPENDANTE de l'orientation : corrélation normalisée sur les
    images étirées. → [score « tel quel », score « miroir »]."""
    def prep(x):
        lum = x if x.ndim == 2 else x.mean(axis=2)
        bas, haut = (float(np.percentile(lum, 0.5)),
                     float(np.percentile(lum, 99.5)))
        y = np.sqrt(np.clip((lum - bas) / max(1e-9, haut - bas), 0.0, 1.0))
        s = cv2.resize(y, (y.shape[1] // ech, y.shape[0] // ech),
                       interpolation=cv2.INTER_AREA)
        m = float(np.median(s))
        return (s - m) / max(1e-6, 1.4826 * float(np.median(np.abs(s - m))))

    r, c = prep(np.asarray(ref, np.float32)), prep(np.asarray(img, np.float32))
    y0 = (r.shape[0] - cote) // 2
    x0 = (r.shape[1] - cote) // 2
    mot = np.ascontiguousarray(r[y0:y0 + cote, x0:x0 + cote], np.float32)
    sc = []
    for t in (c, c[::-1]):
        r_ = cv2.matchTemplate(np.ascontiguousarray(t, np.float32), mot,
                               cv2.TM_CCOEFF_NORMED)
        sc.append(float(cv2.minMaxLoc(r_)[1]))
    return sc


if os.path.isfile(EMP) and os.path.isfile(EXT):
    emp = np.asarray(load_image(EMP), np.float32)
    ext = np.asarray(load_image(EXT), np.float32)
    avant = orientation(ext, emp)
    print(f"    état livré (v2.38.1) : tel quel {avant[0]:+.3f} · "
          f"miroir {avant[1]:+.3f} → "
          f"{'DROIT' if avant[0] >= avant[1] else 'EN MIROIR'}")
    verifie(avant[1] > avant[0],
            "le fichier du ⚡ EST en miroir tel que livré (défaut reproduit)")
    corrige = np.asarray(auto_unflip(ext, emp), np.float32)
    apres = orientation(corrige, emp)
    print(f"    après `auto_unflip` : tel quel {apres[0]:+.3f} · "
          f"miroir {apres[1]:+.3f} → "
          f"{'DROIT' if apres[0] >= apres[1] else 'EN MIROIR'}")
    verifie(np.allclose(corrige, ext[::-1], atol=1e-6),
            "la fonction REDRESSE le vrai fichier du ⚡")
    verifie(not np.allclose(auto_unflip_v2381(ext.copy(), emp), ext[::-1],
                            atol=1e-6),
            "TÉMOIN sur les vrais fichiers : l'ancienne formule NE redresse PAS "
            "(c'est le défaut mesuré)")
else:
    print("    (fichiers de test absents — section ignorée)")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
