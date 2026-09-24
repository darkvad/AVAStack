# -*- coding: utf-8 -*-
"""Calibration spectrophotométrique ABSOLUE « à la Siril » (jalon 58).

POURQUOI : la photométrie RELATIVE du jalon 56 (zéro-point par bande contre la
magnitude Gaia G) ne peut pas corriger la couleur d'une image multi-filtres —
G est une bande très large (330-1050 nm) et rien ne relie le flux d'une bande
instrumentale à celui d'une autre. Mesuré sur les couches réelles d'Alain
(24/09/2026) : dispersion des zéro-points croissante vers le bleu (R 0,162 /
G 0,233 / B 0,376 mag) et gains qui refroidissent l'image (R ×0,7665 /
B ×1,0426). La SPCC fait autrement : elle PRÉDIT le flux attendu dans CHAQUE
bande en multipliant le SPECTRE Gaia DR3 de chaque étoile (`xp_sampled`,
336-1020 nm par pas de 2 nm) par la RÉPONSE de la bande = QE du capteur ×
transmission du filtre, puis en intégrant. Les rapports prédits (R/G, B/G)
sont confrontés aux rapports MESURÉS, et une régression robuste donne les
coefficients — corrigés par une RÉFÉRENCE DE BLANC (couleur visée).

MODÈLE repris de Siril (src/algos/photometric_cc.c `get_spcc_white_balance_
coeffs` + src/algos/spcc.c, lu le 24/09/2026) :
  1. réponse du canal : R_c(λ) = QE(λ) · T_c(λ), interpolée sur la grille
     `xp_sampled` (interpolation LINÉAIRE : le projet n'a ni scipy ni GSL ;
     Siril interpole en Akima — écart négligeable sur les intégrales, cf.
     banc _diag_spcc) ; les courbes sont ramenées à ZÉRO hors de leur domaine
     mesuré (pas d'extrapolation numérique aux extrémités) ;
  2. flux Gaia → comptage de PHOTONS : Siril multiplie par λ puis normalise à
     500 nm (facteur PAR ÉTOILE, donc sans effet sur des ratios) ;
  3. flux attendu : F_c = ∫ R_c(λ)·S(λ) dλ (trapèzes) → ratios catalogue
     crg = F_R/F_G, cbg = F_B/F_G ;
  4. flux mesurés I_c (photométrie d'ouverture) → irg = I_R/I_G, ibg = I_B/I_G ;
  5. régression ROBUSTE par médianes répétées (Siegel) : irg = a + b·crg ;
  6. référence de BLANC (spectre de galaxie spirale moyenne par défaut),
     traitée comme un « spectre d'étoile » → wrg = W_R/W_G, wbg = W_B/W_G ;
  7. coefficients : k_R = 1/(a_RG + b_RG·wrg), k_G = 1,
     k_B = 1/(a_BG + b_BG·wbg), normalisés par le plus grand.

Aucune dépendance nouvelle : numpy seul (l'image et les catalogues sont lus
par les modules existants). Tout est PUR : ce module ne touche ni au disque
ni à l'UI, ce qui le rend directement testable au banc.
"""

import numpy as np

# Grille spectrale Gaia DR3 xp_sampled : 336 → 1020 nm par pas de 2 nm
# (343 points — identique à DTYPE_XPSAMP de catalogues/siril_cat.py).
GRILLE_WL = np.arange(336.0, 1021.0, 2.0)
XPSAMPLED_LEN = GRILLE_WL.size          # 343
# Indice de normalisation utilisé par Siril (xps->y[82] → 500 nm) : facteur
# PAR ÉTOILE, conservé pour la fidélité du modèle.
INDICE_NORM = 82


def sur_grille(wl, val):
    """Courbe (nm, valeurs) → valeurs sur `GRILLE_WL`, interpolées
    linéairement et RAMENÉES À ZÉRO hors de son domaine mesuré.

    Pourquoi zéro hors domaine : Siril laisse GSL Akima EXTRAPOLER (pente des
    derniers points), ce qui peut fabriquer une réponse fantôme en dessous de
    380 nm (début des profils capteurs) ou au-delà de 1000 nm. Multipliée par
    la QE puis intégrée, elle faussait les ratios ; physiquement, aucune
    donnée = aucune réponse connue."""
    if wl is None or val is None or len(wl) < 2:
        return np.zeros(XPSAMPLED_LEN, dtype=np.float64)
    wl = np.asarray(wl, dtype=np.float64)
    val = np.asarray(val, dtype=np.float64)
    out = np.interp(GRILLE_WL, wl, val, left=0.0, right=0.0)
    return out


def reponse_canal(capteur, filtre):
    """Réponse d'un canal : QE du capteur × transmission du filtre, sur la
    grille xp_sampled. `capteur` et `filtre` sont des couples (wl, val) issus
    de `catalogues.spcc_db.courbe` (le filtre peut être None : mode
    narrowband ou canal sans filtre). → (343,) float64."""
    r = sur_grille(*capteur) if capteur else np.ones(XPSAMPLED_LEN)
    if filtre:
        r = r * sur_grille(*filtre)
    return r


def photons(spectres):
    """Flux Gaia (N, 343) — W·m⁻²·nm⁻¹ — → comptage de PHOTONS RELATIF.

    Siril (`flux_to_relcount`) multiplie par λ (un photon de grande longueur
    d'onde porte moins d'énergie) puis normalise à 500 nm. La normalisation
    est un facteur PAR ÉTOILE : elle ne change aucun ratio, mais elle est
    conservée ici pour que les nombres restent comparables à ceux de Siril."""
    s = np.asarray(spectres, dtype=np.float64)
    if s.ndim == 1:
        s = s[None, :]
    s = s * GRILLE_WL[None, :]
    return s / np.where(s[:, INDICE_NORM:INDICE_NORM + 1] == 0.0, 1.0,
                        s[:, INDICE_NORM:INDICE_NORM + 1])


def flux_par_canal(spectres, reponses):
    """Intégrale (trapèzes) de réponse × spectre par canal.
    → (N, 3) float64 : [R, G, B] ; NaN si une intégrale est nulle ou non
    finie (canal inexploitable — jamais une valeur inventée)."""
    s = np.asarray(spectres, dtype=np.float64)
    if s.ndim == 1:
        s = s[None, :]
    out = np.full((s.shape[0], 3), np.nan)
    for c in range(3):
        out[:, c] = np.trapz(s * reponses[c][None, :], GRILLE_WL, axis=1)
    mauvais = ~np.isfinite(out) | (out <= 0.0)
    if mauvais.any(axis=1).any():
        out[np.any(mauvais, axis=1)] = np.nan
    return out


def ratios(flux, canaux=(0, 2)):
    """Ratios d'un tableau (N, 3) par rapport au VERT → (N, 2) [R/G, B/G].
    Lignes inexploitables (NaN) → NaN."""
    f = np.asarray(flux, dtype=np.float64)
    g = f[:, 1]
    out = np.column_stack([f[:, canaux[0]] / g, f[:, canaux[1]] / g])
    return out


def regression_mediane(x, y):
    """Régression linéaire ROBUSTE par médianes répétées (Siegel 1982),
    celle de Siril (`repeated_median_fit`, src/algos/fitting.c, lu le
    24/09/2026) :
        b = médiane_i ( médiane_{j≠i} (y_j - y_i)/(x_j - x_i) )
        a = médiane_i ( y_i - b·x_i )
    Insensible aux étoiles aberrantes (variabilité, saturation, fusions
    apparentes) — indispensable ici : le nuage contient toujours quelques
    points aberrants que l'astrométrie n'exclut pas.
    → (a, b, ecart) : `ecart` = MAD des résidus (diagnostic affichable) ;
    (nan, nan, nan) si moins de 3 points exploitables (Siril exige ≥ 3)."""
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    bon = np.isfinite(x) & np.isfinite(y)
    x, y = x[bon], y[bon]
    n = x.size
    if n < 3:
        return float("nan"), float("nan"), float("nan")
    # pentes de chaque point vers tous les autres (vecteurisé)
    dx = x[None, :] - x[:, None]
    dy = y[None, :] - y[:, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        pentes = np.where(dx != 0.0, dy / dx, np.nan)
    med_i = np.nanmedian(pentes, axis=1)
    pente = float(np.median(med_i[np.isfinite(med_i)]))
    ordonnee = float(np.median(y - pente * x))
    residus = y - (ordonnee + pente * x)
    ecart = float(np.median(np.abs(residus - np.median(residus))) * 1.4826)
    return ordonnee, pente, ecart


def coefficients(crg, cbg, irg, ibg, wrg, wbg):
    """Coefficients SPCC (R, G, B) — formules de Siril :
        k_R = 1/(a_RG + b_RG·wrg) ; k_G = 1 ; k_B = 1/(a_BG + b_BG·wbg)
    puis division par le plus grand (le vert reste à 1, comme Siril).

    Entrées : ratios CATALOGUE par étoile (crg, cbg), ratios IMAGE par étoile
    (irg, ibg), ratios de la RÉFÉRENCE DE BLANC (wrg, wbg).
    → (k (3,) float64, diag dict) ; k vide (nan) si la régression échoue ou
    donne un coefficient négatif/nul (Siril : « kw contains negative values »
    → échec, jamais un gain négatif appliqué à l'image)."""
    a_rg, b_rg, s_rg = regression_mediane(crg, irg)
    a_bg, b_bg, s_bg = regression_mediane(cbg, ibg)
    if not all(np.isfinite(v) for v in (a_rg, b_rg, a_bg, b_bg)):
        return np.full(3, np.nan), {"erreur": "régression impossible "
                                             "(moins de 3 étoiles valides)"}
    k_r = 1.0 / (a_rg + b_rg * wrg)
    k_b = 1.0 / (a_bg + b_bg * wbg)
    k = np.array([k_r, 1.0, k_b], dtype=np.float64)
    if not np.all(np.isfinite(k)) or np.any(k <= 0.0):
        return np.full(3, np.nan), {
            "erreur": "coefficient négatif ou nul (vérifier capteur/filtres)",
            "a_rg": a_rg, "b_rg": b_rg, "a_bg": a_bg, "b_bg": b_bg}
    k = k / k.max()
    diag = {"a_rg": a_rg, "b_rg": b_rg, "sigma_rg": s_rg,
            "a_bg": a_bg, "b_bg": b_bg, "sigma_bg": s_bg,
            "wrg": float(wrg), "wbg": float(wbg)}
    return k, diag


def erreur_ratios(crg, cbg, irg, ibg):
    """Erreur résiduelle des ratios image vs catalogue, en MAGNITUDES
    équivalentes (log10) — c'est la mesure OBJECTIVE de la qualité de
    couleur, celle que la SPCC minimise. → (rms (2,), mediane (2,), n)."""
    import math
    crg = np.asarray(crg, np.float64)
    cbg = np.asarray(cbg, np.float64)
    irg = np.asarray(irg, np.float64)
    ibg = np.asarray(ibg, np.float64)
    bon = (np.isfinite(crg) & np.isfinite(irg) & (crg > 0) & (irg > 0)
           & np.isfinite(cbg) & np.isfinite(ibg) & (cbg > 0) & (ibg > 0))
    if not bon.any():
        return np.zeros(2), np.zeros(2), 0
    d_r = np.abs(2.5 * np.log10(irg[bon] / crg[bon]))
    d_b = np.abs(2.5 * np.log10(ibg[bon] / cbg[bon]))
    rms = np.array([math.sqrt(float((d_r ** 2).mean())),
                    math.sqrt(float((d_b ** 2).mean()))])
    med = np.array([float(np.median(d_r)), float(np.median(d_b))])
    return rms, med, int(bon.sum())

