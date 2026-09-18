# -*- coding: utf-8 -*-
"""Débruitage LOCAL (jalon 8) — algorithmes classiques, sans IA ni subprocess.

Demande d'Alain : le débruitage GraXpert (IA) est très long ; deux
algorithmes classiques rapides (quelques secondes) sont codés ici, en
numpy + OpenCV uniquement (aucune nouvelle dépendance) :

  - « ondelettes » : transformée à trous (starlet, noyau B3-spline) sur 5
    niveaux d'échelle, mais seuls les 2 niveaux FINS (échelles 1 et 2 px)
    sont seuillés (garrote non-négative k-sigma, bruit estimé par MAD,
    robuste aux étoiles) puis reconstruction — les niveaux plus grossiers
    contiennent de la structure, pas du bruit : les seuiller créait un
    fond « léopard » (cf. _ondelettes). Option DOUCE. Méthode astro de
    référence (PixInsight, Siril). Les étoiles et structures brillantes
    dépassent largement le seuil : elles sont épargnées.

  - « nlm » (DÉFAUT) : Non-local Means (cv2.fastNlMeansDenoising) — chaque
    pixel est moyenné avec les pixels semblables du voisinage. La force
    `h` est auto-adaptée au bruit RÉEL de l'image (estimation par MAD de
    la 1re couche d'ondelettes), h ≈ (0.3 + 1.0·force)·σ appliqué en 2
    passes faibles — volontairement proche de σ et à petite fenêtre : un
    h trop fort ou une grande fenêtre créent un fond « léopard »
    (cf. _nlm). OpenCV impose des entiers : l'image [0..1] est convertie
    en 16 bits (quantification 1/65535, négligeable) ; RGB accepté
    directement (mono-canal comme multi-canaux, cf. PIÈGE OpenCV 5 dans
    _nlm : la version 16 bits n'existe qu'avec la norme L1 et le h
    « tableau »).

Les deux opèrent sur l'image LINÉAIRE [0..1] (mono (H,W) ou RGB
(H,W,3)). L'entrée peut contenir de légères valeurs négatives (empilement
recalé) : l'ondelette les respecte, le NLM les clampe (conversion
entière). Renvoie toujours une copie float32 — l'image d'entrée n'est
jamais modifiée.
"""

import sys

import numpy as np
import cv2

# Niveaux d'échelle de la transformée à trous (5 = fino à ~32 px de large).
_NIVEAUX = 5
# Anti-léopard : seuls les N niveaux FINS (échelles 1, 2 px) sont
# seuillés — le bruit fin vit dans les petites échelles ; les niveaux
# plus grossiers (4 px et au-delà) contiennent déjà de la structure
# réelle sur des images astro (retour test réel d'Alain : le niveau
# 4 px suffit à créer un léger moutonnement). L'ondelette est donc
# l'option DOUCE ; le NLM est l'option « forte » (défaut).
_NIVEAUX_FINES = 2
# Noyau B3-spline 1D de la starlet (interpolant, reconstruction exacte).
_B3 = np.array([1.0, 4.0, 6.0, 4.0, 1.0], dtype=np.float64) / 16.0

METHODS = ("ondelettes", "nlm")


def _noyau_1d(niveau):
    """Noyau 1D B3-spline « dilaté » : coefficients espacés de 2^niveau
    (principe de l'algorithme à trous — aucune sous-échantillonnage)."""
    d = 2 ** int(niveau)
    k = np.zeros(4 * d + 1, dtype=np.float64)
    k[::d] = _B3
    return k


def _etage(c_prev, niveau):
    """Convolution séparable (lignes puis colonnes) au niveau donné.
    cv2.sepFilter2D est natif et multithread ; bordures réfléchies."""
    k = _noyau_1d(niveau)
    return cv2.sepFilter2D(c_prev, -1, k, k, borderType=cv2.BORDER_REFLECT)


def _mad_sigma(x):
    """Estimation robuste du bruit : 1,4826 × MAD (médiane de |x - médiane|).
    Robuste aux structures (étoiles, nébulosités) qui restent minoritaires."""
    m = np.median(x)
    return 1.4826 * float(np.median(np.abs(x - m)))


def estimer_sigma(img):
    """Estime le sigma du bruit d'une image [0..1] via la 1re couche de
    détail de la starlet (cette couche est dominée par le bruit fin)."""
    data = np.asarray(img, dtype=np.float32)
    w = data - _etage(data, 0)
    return min(max(_mad_sigma(w), 1e-9), 1.0)


def _ondelettes(img, force):
    """Débruitage par seuillage k-sigma de la transformée à trous.

    ANTI-LÉOPARD (retour de test réel d'Alain, 15/09/2026 — la 1re version
    laissait un fond « léopard ») :
      1. seuls les niveaux FINS (échelles 1, 2 et 4 px) sont seuillés —
         c'est là que vit le bruit ; les niveaux grossiers (8 px et plus)
         contiennent de la STRUCTURE (nébulosités, gradients) et non du
         bruit : les seuiller créait du moutonnement à grande échelle ;
      2. seuillage GARROTE non-négative (shrinkage doux
         w·(1 − (t/w)²) au lieu du seuil DUR) : transition continue au
         voisinage du seuil — le seuil dur laissait des îlots de
         coefficients survécus, visibles en plaques ;
      3. k conservateur : k = 4.5 − 1.0·force (force 0.5 → 4σ) ;
         v2.6.2 : encore plus doux — 2 niveaux fins seulement (le niveau
         4 px laissait encore un léger moutonnement en test réel).

    Reconstruction EXACTE : c_N + Σ w_i = image initiale — on n'additionne
    donc que la différence (w_i − w_i nettoyé) pour ne pas stocker les
    couches."""
    data = np.asarray(img, dtype=np.float32)
    f = min(1.0, max(0.0, float(force)))
    k_seuil = 4.5 - 1.0 * f
    c_prev = data
    retires = np.zeros_like(data)
    for n in range(_NIVEAUX):
        c = _etage(c_prev, n)
        w = c_prev - c
        if n < _NIVEAUX_FINES:
            t = np.float32(k_seuil * _mad_sigma(w))
            aw = np.abs(w)
            # Garrote non-négative : shrinkage DOUX (transition continue),
            # grands coefficients quasi intacts (étoiles épargnées).
            w_nette = np.where(
                aw > t,
                w * (1.0 - (t / np.maximum(aw, np.float32(1e-12))) ** 2),
                np.float32(0.0)).astype(np.float32)
        else:
            w_nette = w                 # grandes échelles : structure, intacte
        retires += w - w_nette
        c_prev = c
    return data - retires


def _nlm(img, force):
    """Non-local Means. h TOTAL = (0.3 + 1.0·force) × sigma estimé (unités
    16 bits ; force 0.5 → h ≈ 0.8σ), appliqué en DEUX passes faibles
    (0.6·h puis 0.4·h).

    ANTI-LÉOPARD (retours de tests réels d'Alain, 15/09/2026) :
      - h ≈ 1σ est le réglage astro usuel — un h trop fort (l'ancien 3σ)
        moyenne des zones « similaires » lointaines → fond tacheté ;
      - searchWindowSize 21 → 15 et templateWindowSize 7 → 5 : la taille
        de la fenêtre de recherche FIXE l'échelle des plaques — la réduire
        les rend beaucoup plus fines et moins visibles ;
      - DEUX passes faibles au lieu d'une forte : le lissage itératif
        homogénéise le résultat (plus de plaques, même dose de lissage).
    À force 1 (h ≈ 1.3σ) le résultat reste homogène.

    PIÈGE OpenCV 5 (constat 15/09/2026) : la version 16 bits n'existe
    QU'avec la norme L1 et le h « tableau » — et dans CETTE surcharge h
    est le 2e argument positionnel (sinon « Unsupported depth! Only
    CV_8U »). Appel fait par mots-clés pour lever toute ambiguïté."""
    data = np.asarray(img, dtype=np.float32)
    sigma = estimer_sigma(data)
    if sigma <= 1e-8:                       # image constante : rien à faire
        return data.copy()
    h = (0.3 + 1.0 * min(1.0, max(0.0, float(force)))) * sigma * 65535.0
    u16 = np.clip(data, 0.0, 1.0)
    u16 = np.rint(u16 * 65535.0).astype(np.uint16)
    u16 = np.ascontiguousarray(u16)
    # Passe 1 (la plus forte) puis passe 2 (finition) — cf. docstring.
    d = cv2.fastNlMeansDenoising(
        u16, h=np.array([0.6 * h], dtype=np.float32),
        templateWindowSize=5, searchWindowSize=15, normType=cv2.NORM_L1)
    d = cv2.fastNlMeansDenoising(
        d, h=np.array([0.4 * h], dtype=np.float32),
        templateWindowSize=5, searchWindowSize=15, normType=cv2.NORM_L1)
    return d.astype(np.float32) / 65535.0


def denoiser(img, methode, force=0.5):
    """Point d'entrée unique : débruite img par la méthode demandée.

    methode : "ondelettes" ou "nlm" (cf. METHODS). force : 0..1.
    Renvoie (image débruitée, "") en succès, (image d'entrée, message)
    en échec — jamais d'exception propagée, jamais d'image perdue
    (même convention que external.live.appliquer)."""
    source = np.asarray(img)
    m = str(methode).strip().lower()
    if m not in METHODS:
        return source, (f"méthode de débruitage inconnue : {methode!r} "
                        f"(attendu : {' ou '.join(METHODS)})")
    try:
        data = np.asarray(source, dtype=np.float32)
        if not np.isfinite(data).all():
            # v2.9.1 : pixels invalides (NaN/Inf) — ils viennent de l'AMONT
            # (sortie d'outil externe, FITS douteux…). Sans correction, le
            # NLM les jette à 0 en conversion 16 bits avec un RuntimeWarning
            # (« invalid value encountered in cast ») et les ondelettes
            # propagent le NaN à TOUTE la reconstruction. Remis à 0 (resp.
            # 1 pour +Inf) AVANT tout traitement ; compteur affiché en
            # console pour diagnostiquer l'amont.
            n_bad = int(np.count_nonzero(~np.isfinite(data)))
            data = np.nan_to_num(data, nan=0.0, posinf=1.0,
                                 neginf=0.0).astype(np.float32)
            print(f"avastack.denoise : {n_bad} pixels invalides (NaN/Inf) "
                  f"corrigés avant débruitage ({m})")
        out = _ondelettes(data, force) if m == "ondelettes" \
            else _nlm(data, force)
        out = np.asarray(out, dtype=np.float32)
        if out.shape != source.shape:
            return source, (f"dimensions de sortie {out.shape} ≠ "
                            f"entrée {source.shape}")
        return out, ""
    except Exception as exc:                 # OpenCV, mémoire… : repli sûr
        return source, str(exc)

