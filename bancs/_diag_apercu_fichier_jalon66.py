# -*- coding: utf-8 -*-
"""_diag_apercu_fichier_jalon66.py — « pourquoi les étoiles rouges sont bien
plus rouges et ont presque un halo DANS LES FICHIERS alors que l'affichage est
correct » (constat d'Alain, 26/09/2026).

HYPOTHÈSE MESURÉE ICI : l'écran n'applique PAS la même opération que le fichier.
L'aperçu est construit en RÉDUISANT l'empilement à 1600 px (cv2.INTER_AREA,
`app.py`), PUIS la chaîne non linéaire est appliquée (GraXpert/NLM/netteté/
chroma/étirement) ; le fichier reçoit la MÊME chaîne en PLEINE RÉSOLUTION.
Or la chaîne n'est pas linéaire : réduire ÷2,4 AVANT l'étirement dilue le cœur
des étoiles compactes (leur couleur relative change), et la couleur est portée
par le RAPPORT R/L que le moteur VeraLux calcule PIXEL PAR PIXEL. Réduire puis
étirer ≠ étirer puis réduire → « le fichier » (étiré pleine résolution) ne
correspond pas à l'écran.

Protocole, sur les fichiers RÉELS d'Alain (dossier « externe » : la chaîne
« tel que vu » se réduit à l'étirement + gamma/saturation, rien d'autre ne
diffère → l'écart mesuré est imputable à la RÉSOLUTION, pas à une case) :
  [A] FICHIER reproduit  = étirer(linéaire plein format, logD résolu) + gamma
      → comparé au fichier réellement enregistré (contrôle du protocole) ;
  [B] ÉCRAN reproduit    = étirer(réduction INTER_AREA à 1600 px) + gamma ;
  [C] FICHIER vu à la taille de l'écran = réduire le résultat de [A] ;
  [D] comparer [B] et [C] sur les étoiles ROUGES (profil radial de R/G).

Usage : python bancs/_diag_apercu_fichier_jalon66.py [dossier]
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

from avastack.processing import veralux as _veralux        # noqa: E402
from avastack.processing import couleurs as _couleurs      # noqa: E402

# Réglages de la session d'Alain (config.json, 26/09/2026)
PROFIL = "Sony IMX585 (ASI585) - STARVIS 2"
TARGET_BG = 0.16
GAMMA = 1.15
LARGEUR_APERCU = 1600.0

# (libellé, linéaire d'entrée, fichier « tel que vu » enregistré,
#  étapes PRÉ-ÉTIREMENT de la chaîne « tel que vu » de cette vue)
#   dossier « externe » : l'image a déjà subi le traitement externe et la vue
#   « traitée » ne rejoue AUCUNE étape live → étirement seul ;
#   vue « empilement » : neutralisation du fond PUIS réduction du bruit
#   chromatique (v2.36.1/v2.37.0), juste avant l'étirement.
CAS = [
    ("EXTERNE (vue traitée : étirement seul)",
     "m31_traite_externe_lineaire-v2.373..fits",
     "m31_traite_externe_etire-v2.373..fits",
     (False, 0.0, 3.0)),
    ("PILE (vue empilement : neutre → chroma → étirement)",
     "M31_traite_lineaire_2.37.3.fits",
     "m31_stack_etire-telquevu_traite-v2.37.3.fits",
     (True, 0.8471, 3.0)),
]

ANNEAUX = ((1, 2), (3, 4), (5, 7), (8, 11), (12, 16), (17, 24))
FOND = (28, 40)


def lire_fits(p):
    d = np.asarray(fits.getdata(p), dtype=np.float32)
    if d.ndim == 3 and d.shape[0] == 3:
        d = np.transpose(d, (1, 2, 0))
    return d


def reduire(img, largeur=LARGEUR_APERCU):
    """Réduction d'aperçu EXACTE de l'appli (INTER_AREA, plus grand côté)."""
    h, w = img.shape[:2]
    ech = min(1.0, largeur / float(max(h, w)))
    if ech >= 1.0:
        return np.ascontiguousarray(img), 1.0
    return cv2.resize(img, None, fx=ech, fy=ech,
                      interpolation=cv2.INTER_AREA), ech


def gamma(x):
    return np.clip(np.power(np.clip(x, 0.0, 1.0), 1.0 / max(GAMMA, 0.05)),
                   0.0, 1.0)


def ecarts(a, b):
    d = np.abs(np.asarray(a, np.float32) - np.asarray(b, np.float32))
    return float(d.max()), float(d.mean())


def etoiles_rouges(img, n_max=5):
    """Étoiles ÉTENDUELLES (le cœur de M31, lui, est une plage continue) :
    maxima locaux de luminance, triés par ROUGEUR (R/G au cœur).
    → liste de (x, y, luminosité, R/G)."""
    lum = img.mean(axis=2)
    mx = float(lum.max())
    dil = cv2.dilate(lum, np.ones((9, 9), np.float32))
    pics = (lum >= dil - 1e-9) & (lum > max(0.12, 0.06 * mx))
    ys, xs = np.nonzero(pics)
    h, w = lum.shape
    garde = []
    for k in np.argsort(-lum[ys, xs])[:4000]:
        y, x = int(ys[k]), int(xs[k])
        if not (24 <= y < h - 24 and 24 <= x < w - 24):
            continue
        if any(abs(y - b[0]) < 15 and abs(x - b[1]) < 15 for b in garde):
            continue
        garde.append((y, x))
        if len(garde) >= 300:
            break
    res = []
    for (y, x) in garde:
        c = img[y, x]
        if c[1] <= 1e-4:
            continue
        res.append((x, y, float(lum[y, x]), float(c[0] / c[1])))
    res.sort(key=lambda t: -t[3])
    return res[:n_max]


def profil_rg(img, x, y, echelle=1.0, anneaux=ANNEAUX, fond=FOND):
    """R/G par ANNEAU (rayons en px d'APERÇU × `echelle`), en multiples du R/G
    du fond local (couronne `fond`). `echelle` = 1/ech pour la pleine
    résolution : on mesure ainsi les MÊMES rayons PHYSIQUES partout."""
    h, w = img.shape[:2]
    xf, yf = x * echelle, y * echelle
    demi = int(round((fond[1] + 6) * echelle))
    y0, y1 = max(0, int(yf) - demi), min(h, int(yf) + demi + 1)
    x0, x1 = max(0, int(xf) - demi), min(w, int(xf) + demi + 1)
    sous = np.asarray(img[y0:y1, x0:x1], np.float64)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    r = np.sqrt((yy - yf) ** 2.0 + (xx - xf) ** 2.0) / echelle
    m = (r >= fond[0]) & (r <= fond[1])
    if int(m.sum()) < 40:
        return None
    f = sous[m].mean(axis=0)
    if f[1] <= 1e-9:
        return None
    ref = f[0] / f[1]
    out = []
    for (a, b) in anneaux:
        mm = (r >= a) & (r < b)
        if int(mm.sum()) < 8:
            out.append(np.nan)
            continue
        moy = sous[mm].mean(axis=0)
        out.append(float((moy[0] / max(moy[1], 1e-12)) / ref))
    return out


def main():
    print("Moteur VeraLux :", "disponible" if _veralux.moteur_disponible()
          else "ABSENT")
    for libelle, nom_lin, nom_eti, pre in CAS:
        neutre, f_chroma, r_chroma = pre
        p_lin = os.path.join(RACINE, nom_lin)
        p_eti = os.path.join(RACINE, nom_eti)
        if not (os.path.isfile(p_lin) and os.path.isfile(p_eti)):
            print(f"\n### {libelle} — fichier absent, ignoré")
            continue
        print("\n" + "=" * 78 + f"\n### {libelle}\n" + "=" * 78)
        lin = _veralux.normaliser_lin(lire_fits(p_lin))
        petit, ech = reduire(lin)
        # étapes pré-étirement EXACTES de la chaîne « tel que vu », chacune à SA
        # résolution (le rayon de chroma suit l'image, comme dans l'appli)
        lin_p = _avant_etirement(lin, neutre, f_chroma, r_chroma, 1.0)
        petit_p = _avant_etirement(petit, neutre, f_chroma, r_chroma, ech)
        print(f"  linéaire {lin.shape[1]}×{lin.shape[0]} (max {float(lin.max()):.3f})"
              f" → aperçu ×{ech:.4f} = {petit.shape[1]}×{petit.shape[0]} px ; "
              f"chroma rayon {_couleurs.rayon_chroma_apercu(1.0, r_chroma):.2f} px "
              f"pleine rés. / {_couleurs.rayon_chroma_apercu(ech, r_chroma):.2f} px "
              f"aperçu")

        # [B] ÉCRAN : l'appli étire l'APERÇU (image réduite) — et résout le logD
        ecran_p, logd, diag_p = _veralux.etirer(
            petit_p, mode=_veralux.MODE_TARGET_BG, target_bg=TARGET_BG,
            profil=PROFIL)
        ecran = gamma(ecran_p)
        # [A] FICHIER : même étirement en PLEINE résolution, avec LE logD résolu
        # sur l'aperçu (c'est exactement ce que fait rendu_pleine_resolution)
        fich_p, _, diag_f = _veralux.etirer(
            lin_p, mode=_veralux.MODE_LOG_D, log_d=logd, target_bg=TARGET_BG,
            profil=PROFIL)
        fichier = gamma(fich_p)
        print("  diagnostics du moteur d'étirement :")
        for nom, dg in (("APERÇU (écran)", diag_p), ("PLEINE RÉS. (fichier)", diag_f)):
            p = dg.get("luminance_percentiles", {})
            print(f"    {nom:22s} ancre {dg.get('anchor'):.6f} · logD "
                  f"{dg.get('log_d_resolu'):.4f} · pression étoiles "
                  f"{dg.get('star_pressure'):.4f} · médiane L "
                  f"{dg.get('median_luminance_finale'):.4f} · p0,1 {p.get('p0.1')}"
                  f" · p50 {p.get('p50_mediane')}")
        reel = lire_fits(p_eti)
        mac, moyc = ecarts(fichier, reel)
        print(f"  logD résolu sur l'APERÇU : {logd:.4f} → appliqué au fichier")
        print(f"  [A] reproduction du FICHIER vs fichier enregistré : écart max "
              f"{mac:.4f} / moyen {moyc:.4f}  (contrôle du protocole)")
        fich_reduit, _ = reduire(fichier)
        reel_reduit, _ = reduire(reel)
        dm, dmy = ecarts(reel_reduit, ecran)
        print(f"  [D] ÉCRAN vs FICHIER enregistré (mêmes 1600 px) : écart max "
              f"{dm:.4f} / moyen {dmy:.4f}  ← l'écart que voit Alain")

        # [C] Les étoiles rouges, vues quatre fois (MÊMES rayons physiques)
        print("\n  Profil R/G par anneaux (× le R/G du fond local) : "
              "1-2 / 3-4 / 5-7 / 8-11 / 12-16 / 17-24 px d'aperçu")
        for (x, y, p, rg) in etoiles_rouges(petit, n_max=4):
            print(f"\n   ÉTOILE ({x:4d},{y:4d})  R/G cœur {rg:.2f}  lum {p:.3f}")
            for nom, img, echl in (
                    ("linéaire APERÇU (avant étir.)", petit_p, 1.0),
                    ("linéaire PLEINE RÉS. (idem)", lin_p, 1.0 / ech),
                    ("ÉCRAN  étiré de l'aperçu", ecran, 1.0),
                    ("FICHIER étiré pleine rés.", fichier, 1.0 / ech),
                    ("FICHIER réduit à 1600 px", fich_reduit, 1.0)):
                pr = profil_rg(img, x, y, echelle=echl)
                if pr is None:
                    print(f"      {nom:29s} (mesure impossible)")
                    continue
                print(f"      {nom:29s} " +
                      "  ".join(f"{v:5.2f}" for v in pr))


def _avant_etirement(img, neutre, force_chroma, rayon_chroma, echelle):
    """Étapes PRÉ-ÉTIREMENT de la chaîne « tel que vu » : neutralisation du
    fond (v2.36.1) puis réduction du bruit chromatique (v2.37.0) — les MÊMES
    fonctions que le worker de l'appli, avec le rayon de chroma de la
    résolution REÇUE (v2.37.3 : le rayon suit la résolution)."""
    if neutre:
        img = _couleurs.neutraliser_fond(img)
    if force_chroma > 0.0:
        img = _couleurs.reduire_bruit_chroma(
            img, force=float(force_chroma),
            rayon=_couleurs.rayon_chroma_apercu(echelle, float(rayon_chroma)))
    return img


if __name__ == "__main__":
    main()
