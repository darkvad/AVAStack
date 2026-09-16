# -*- coding: utf-8 -*-
"""Netteté live (jalon 11) — déconvolution de Richardson-Lucy, MODULE SEUL.

Décision d'Alain (16/09/2026, banc d'essai chiffré) : la netteté live passe
par **Richardson-Lucy** — Unsharp Mask et Wiener sont ÉCARTÉS (l'UM sature :
il n'accentue que les AILES de la PSF, jamais son cœur ; Wiener DIVISE par
le spectre de la PSF et s'effondre dès que la PSF estimée est fausse —
halo sombre mesuré à −0,102 du pic pour une PSF fausse de 35 %). Banc
d'essai d'origine (étoile synthétique FWHM 3,06 px, bruit σ = 0,006 ;
« bruit × » en LINÉAIRE, coût sur 1,6 Mpx) :

    | RL  3 it | FWHM 2,47 px | « bruit » ×1,14 |  44 ms |
    | RL  5 it | FWHM 2,24 px | « bruit » ×1,22 |  74 ms |
    | RL 10 it | FWHM 2,00 px | « bruit » ×1,39 | 142 ms |

MESURES DU MODULE (jalon 11, 16/09/2026 ; 40 étoiles FWHM VRAIE 3,00 px,
bruit σ = 0,006, 800×1200 px) — FWHM mesurée 2,91 px puis, à 3 / 5 / 10 it :
**2,38 / 1,84 / 1,48 px** (63 / 75 / 105 ms ; au-delà de 10 it plus rien ne
bouge) ; pic d'une étoile isolée ×2,35 avec un **flux conservé à ×1,000** ;
tolérance à une PSF fausse de ±35 % confirmée (2,46 et 2,16 px, creux de
fond +0,00000). Deux points de méthode :
  - ⚠️ **le « bruit × » du banc d'origine n'est PAS du bruit de fond** :
    mesuré sur le fond (MAD) et en hautes fréquences (starlet), RL ne
    DÉGRADE rien — ×0,95 / ×0,92 / ×0,86 aux mêmes itérations. Ce qui monte
    (écart-type GLOBAL ×1,22 / ×1,32 / ×1,51), c'est le CONTRASTE gagné sur
    les pics d'étoiles : c'est l'AMPLITUDE des étoiles qu'il faut surveiller
    (halos), pas le fond. Le tableau ci-dessus est conservé pour mémoire.
  - le module est VALIDÉ CONTRE UNE RL DE RÉFÉRENCE écrite en numpy pur
    (convolution 2D explicite, `_test_rl_jalon11.py`) : écart relatif
    < 1e-5 à 1, 3, 5 et 10 it — c'est cette comparaison qui garantit que
    c'est bien LA formule de Richardson-Lucy qui est appliquée.


Ce module est le **jalon 11** : il n'a AUCUNE interface (le câblage live —
case à cocher, curseur, cache du solveur, « tel que vu », config — est le
jalon 12) et AUCUNE dépendance nouvelle (numpy + OpenCV, comme
`denoise.py` et `stars.py`).

Ce qu'il fait :
  - la PSF est une gaussienne ISOTROPE dont le σ est DÉDUIT de la FWHM
    mesurée par `stars.mesurer_seeing` (jalon 10) via
    `stars.sigma_depuis_fwhm` : la netteté suit donc le seeing réel de la
    nuit, sans réglage à trouver ;
  - 3 à 5 itérations sont le réglage utile ; `ITERATIONS_MAX` (10) est un
    plafond DUR (au-delà le gain devient invisible alors que le bruit
    continue de monter) ;
  - **luminance seule** pour une image couleur (comme SharpCap) : la
    luminance est déconvoluée, puis le gain obtenu est ré-appliqué aux
    canaux d'origine — la chromatidité est conservée, aucun artefact
    couleur n'apparaît ;
  - **pas de no-op silencieux** : moins de `stars.MIN_ETOILES` étoiles
    mesurables, paramètres invalides ou PSF hors bornes → l'image est
    renvoyée INCHANGÉE avec un message explicite, et JAMAIS une exception
    (même convention que `denoise.denoiser` et `stars.mesurer_seeing`).

⚠️ À ne pas redécouvrir (mesures du 16/09/2026) :
  - la netteté change l'AMPLITUDE, pas la texture : à l'écran le bruit
    affiché bouge à peine (le point noir auto vaut médiane − k·σ et σ est
    mesuré sur l'image COURANTE → il redescend de lui-même, ×0,99-1,01
    pour TOUTES les méthodes). MAIS la sauvegarde « tel que vu » emporte le
    bruit réellement amplifié, et en mode manuel (black/white figés) il se
    voit ;
  - ordre de la chaîne (précisé par Alain) : **recadrage → gradient →
    débruitage → NETTETÉ → étirement** — on lisse d'abord, on restaure
    ensuite : déconvoluer une image déjà lissée par NLM accentue les
    plaques du fond « léopard » ;
  - sur un capteur à petit échantillonnage (aperçu réduit, étoiles ~1 px)
    la déconvolution n'a plus rien à mordre et fabrique du ringing : d'où
    le refus explicite d'une σ de PSF hors bornes (`stars.SIGMA_MIN` /
    `stars.SIGMA_MAX`) ;
  - RL est conservatif en flux (photométrie : le pic monte, la largeur
    diminue, l'éclat TOTAL de l'étoile est préservé) et tolère une PSF
    fausse de ±35 % (creux du halo −0,021 à PSF 1,70 px) — c'est ce qui le
    rend utilisable en live, contrairement à Wiener.
"""

import math

import numpy as np
import cv2

from . import stars

# Itérations : 3-5 = réglage utile (cf. banc d'essai), 10 = plafond DUR.
ITERATIONS_DEFAUT = 5
ITERATIONS_MAX = 10
# Rayon du noyau gaussien, en σ (4 σ ≈ 99,99 % du flux).
_RAYON_SIGMA = 4.0
# Garde-fou de la division de Richardson-Lucy : le rapport observation /
# estimation peut s'emballer sur un pixel isolé ; 1e3 ne bride aucun cas
# réel (un pixel 1000× plus fort que son estimation reste astronomique).
_RATIO_MAX = 1.0e3
# Gain maximal ré-appliqué aux canaux couleur. Le gain utile mesuré est
# ×2,4 à 5 it (réglage recommandé) et ~×4 à 10 it sur une étoile brillante :
# 8 ne bride donc AUCUN réglage utile, il protège seulement le fond d'un
# pixel aberrant (division par une luminance quasi nulle).
_GAIN_MAX = 8.0
# Sous ce niveau de luminance, la couleur locale n'est pas définie
# (pixel noir, masque) : le gain reste NEUTRE (1).
_LUMA_MIN = 1e-6


def _luminance(img):
    """Luminance float32 d'une image mono (H,W) ou couleur (H,W,3).

    Même pondération Rec.601 que `stars._luminance` (recopiée ici : les
    deux modules restent indépendants). PIÈGE connu du projet : l'axe des
    canaux est le DERNIER en couleur et ABSENT en mono — les deux cas sont
    traités, une disposition inattendue lève plutôt que de rendre une
    image noire en silence."""
    a = np.asarray(img, dtype=np.float32)
    if a.ndim == 2:
        return a
    if a.ndim == 3 and a.shape[2] >= 3:
        return (0.299 * a[..., 0] + 0.587 * a[..., 1]
                + 0.114 * a[..., 2]).astype(np.float32)
    raise ValueError(f"image de dimensions inattendues : {a.shape}")


def _noyau_gaussien(sigma_px):
    """Noyau 1D gaussien NORMALISÉ (somme = 1 → RL conserve le flux)."""
    s = max(float(sigma_px), 1e-3)
    demi = max(1, int(math.ceil(_RAYON_SIGMA * s)))
    t = np.arange(-demi, demi + 1, dtype=np.float32)
    k = np.exp(-0.5 * (t / s) ** 2).astype(np.float32)
    return k / k.sum()


def _convoluer(x, noyau):
    """Convolution SÉPARABLE (lignes puis colonnes) : cv2.sepFilter2D est
    natif et multithread — c'est ce qui met RL 5 it à 74 ms sur 1,6 Mpx.
    Bordures réfléchies (aucune marche artificielle au bord de l'aperçu)."""
    return cv2.sepFilter2D(x, cv2.CV_32F, noyau, noyau,
                           borderType=cv2.BORDER_REFLECT)


def _rl_luminance(luma, sigma_px, iterations):
    """Richardson-Lucy sur une luminance 2D, non négative.

    u ← u · [(d / (u ⊛ P)) ⊛ P] : P étant gaussienne (donc SYMÉTRIQUE), sa
    version « miroir » est P elle-même — une seule convolution par passe.
    L'observation est bornée à ≥ 0 (un empilement recalé peut contenir de
    légères valeurs négatives, cf. denoise.py) : RL n'a de sens que sur des
    données non négatives, et le résultat l'est par construction."""
    noyau = _noyau_gaussien(sigma_px)
    obs = np.maximum(np.asarray(luma, dtype=np.float32), np.float32(0.0))
    est = obs.copy()
    for _ in range(int(iterations)):
        conv = _convoluer(est, noyau)
        ratio = obs / np.maximum(conv, np.float32(1e-12))
        np.clip(ratio, 0.0, _RATIO_MAX, out=ratio)
        est *= _convoluer(ratio, noyau)
        np.maximum(est, 0.0, out=est)
    return est


def _appliquer_gain(img, luma, luma_dec):
    """Ré-applique le gain de luminance déconvoluée à l'image d'origine.

    Mono (H,W) : le produit rend directement la luminance déconvoluée.
    Couleur (H,W,3) : chaque canal est multiplié par le MÊME gain (d'où le
    `[..., None]` : la diffusion numpy aligne les DERNIÈRES dimensions —
    sans lui, (H,W,3) × (H,W) lève une erreur) → les rapports entre canaux,
    donc la couleur, sont inchangés : c'est exactement l'esprit « luminance
    seule » de SharpCap, sans artéfact couleur. Là où la luminance est
    nulle (pixel noir, masque), le gain reste neutre."""
    gain = np.ones_like(luma, dtype=np.float32)
    valide = luma > _LUMA_MIN
    gain[valide] = luma_dec[valide] / luma[valide]
    np.clip(gain, 0.0, _GAIN_MAX, out=gain)
    base = np.asarray(img, dtype=np.float32)
    if base.ndim == 3:
        gain = gain[..., None]
    return base * gain



def deconvoluer(img, fwhm=None, iterations=ITERATIONS_DEFAUT,
                seuil_sigma=stars.SEUIL_SIGMA, mesure=None):
    """Point d'entrée de la netteté : Richardson-Lucy sur `img` (LINÉAIRE).

    `fwhm`      : FWHM de la PSF en px. None → elle est MESURÉE sur l'image
                  (`stars.mesurer_seeing`, ~15 ms) — le cas normal en live :
                  la netteté suit alors le seeing réel de la nuit.
    `iterations`: 3-5 = réglage utile ; plafonné à ITERATIONS_MAX, ramené à
                  l'entier inférieur ; refusé s'il est < 1.
    `seuil_sigma`: seuil de détection des étoiles transmis à la mesure.
    `mesure`    : dict DÉJÀ renvoyé par `stars.mesurer_seeing` (évite une 2e
                  mesure quand l'appelant vient de la faire — cf. cache du
                  solveur, jalon 12). Un `fwhm` fourni reste prioritaire.

    Renvoie (image, "") en succès, (image d'ENTRÉE INCHANGÉE, message
    explicite) si la netteté ne s'applique pas — jamais d'exception, jamais
    de no-op silencieux. `img` n'est jamais modifiée."""
    source = np.asarray(img)
    try:
        data = np.asarray(img, dtype=np.float32)
        if data.ndim not in (2, 3) or (data.ndim == 3 and data.shape[2] < 3):
            return source, (f"image de dimensions inattendues : {data.shape} "
                            f"(attendu (H, W) ou (H, W, 3))")

        try:
            it = int(iterations)
        except (TypeError, ValueError):
            return source, (f"nombre d'itérations invalide : {iterations!r} "
                            f"(entier ≥ 1 attendu)")
        if it < 1:
            return source, (f"nombre d'itérations invalide : {it} "
                            f"(entier ≥ 1 attendu)")
        it = min(it, ITERATIONS_MAX)

        # --- PSF : mesure du seeing, ou FWHM fournie par l'appelant --------
        if fwhm is None:
            message_mesure = ""
            if mesure is None:
                mesure, message_mesure = stars.mesurer_seeing(
                    data, seuil_sigma=seuil_sigma)
            if not isinstance(mesure, dict):
                return source, ("mesure de seeing inutilisable : "
                                f"{type(mesure).__name__}")
            nb = int(mesure.get("nb", 0))
            if mesure.get("fwhm") is None or nb < stars.MIN_ETOILES:
                raison = message_mesure or (f"pas assez d'étoiles détectées "
                                            f"({nb})")
                return source, f"netteté inactive — {raison}"
            fwhm = mesure["fwhm"]

        try:
            fwhm_px = float(fwhm)
        except (TypeError, ValueError):
            return source, (f"FWHM invalide : {fwhm!r} "
                            "(nombre de pixels attendu)")

        # σ de la PSF : hors bornes = déconvolution sans objet (étoile trop
        # étroite pour l'échantillonnage, ou PSF démesurée → ringing).
        sigma = stars.sigma_depuis_fwhm(fwhm_px)
        if not (stars.SIGMA_MIN <= sigma <= stars.SIGMA_MAX):
            return source, ("netteté inactive — PSF hors bornes "
                            f"(FWHM {fwhm_px:.2f} px → σ {sigma:.2f} px, "
                            f"attendu σ dans [{stars.SIGMA_MIN:g}, "
                            f"{stars.SIGMA_MAX:g}] px)")

        luma = _luminance(data)
        resultat = _appliquer_gain(data, luma, _rl_luminance(luma, sigma, it))
        resultat = np.asarray(resultat, dtype=np.float32)
        if resultat.shape != source.shape:
            return source, (f"dimensions de sortie {resultat.shape} ≠ "
                            f"entrée {source.shape}")
        return resultat, ""
    except Exception as exc:                 # mémoire, OpenCV, PSF dégénérée…
        return source, str(exc)

