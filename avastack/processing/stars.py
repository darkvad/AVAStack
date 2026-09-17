# -*- coding: utf-8 -*-
"""Détection d'étoiles et mesure de la PSF / du seeing (jalon 10).

Prérequis de la NETTETÉ live (déconvolution de Richardson-Lucy, à venir) :
il faut la PSF de l'image — et l'ORB de `StarAligner` n'est PAS un
détecteur photométrique (aucune PSF, aucune liste d'étoiles exploitable,
vérifié le 16/09/2026). Ce module fournit ce prérequis, et livré SEUL il a
déjà un usage : l'**affichage du seeing en direct** (FWHM médiane + nombre
d'étoiles), très utile en EAA et validable sur une nuit réelle avant même
que la netteté n'existe.

Méthode (numpy + OpenCV, AUCUNE dépendance nouvelle — comme denoise.py) :
  1. luminance (moyenne pondérée Rec.601 pour une image couleur) ;
  2. fond et bruit par MÉDIANE / MAD (robustes : les étoiles sont
     minoritaires dans l'image) ;
  3. seuil = fond + k·σ (k = 8 par défaut) puis composantes 8-connexes ;
  4. rejet des objets trop petits (pixels chauds, résidus de bruit), trop
     gros (nébulosités, amas), trop allongés (étoiles filées, tilt/coma)
     et de ceux qui touchent un bord (mesure forcément incomplète) ;
  5. autour de chaque étoile retenue : centroïde pondéré par l'intensité
     puis moments d'ordre 2 → σx, σy en pixels ;
  6. FWHM = 2·√(2·ln2)·√(σx·σy) ; MÉDIANE des FWHM (robuste aux étoiles
     atypiques — saturées, doubles, à pic chaud).
Les valeurs sont en PIXELS DE L'IMAGE FOURNIE : c'est exactement la
résolution sur laquelle la netteté live travaillera (aperçu ≤ 1600 px),
la mesure est donc directement exploitable comme PSF.

Convention de retour (identique à `denoise.denoiser` et
`external.live.appliquer`) : (résultat, "") en succès, (résultat partiel,
message explicite) sinon — JAMAIS d'exception propagée, jamais de panne
silencieuse (règle « pas de no-op silencieux » : SharpCap n'applique rien
sans le dire quand aucune étoile n'est détectée ; ici le message est
toujours renvoyé à l'affichage).
"""

import math

import numpy as np
import cv2

# Seuil de détection, en σ au-dessus du fond (k). 8σ : les étoiles d'un
# empilement le dépassent largement, le bruit non.
SEUIL_SIGMA = 8.0
# En dessous de ce nombre d'étoiles exploitables, la mesure est signalée
# comme PEU FIABLE (message renvoyé) — pour la netteté ce sera le seuil
# sous lequel elle ne s'applique pas.
MIN_ETOILES = 3
# Plafond d'étoiles conservées (tri par éclat DÉCROISSANT : les plus
# brillantes d'abord). Borne le coût sur un champ très riche.
MAX_ETOILES = 200
# Filtres de forme, en pixels de l'image.
AIRE_MIN = 2          # < 2 px au-dessus de 8σ : pixel chaud ou bruit
AIRE_MAX = 400        # > 400 px : nébulosité / amas, pas une étoile
SIGMA_MIN = 0.4       # plus étroit que ça : échantillonnage impossible
SIGMA_MAX = 8.0       # plus large : l'objet n'est pas une étoile isolée
# Ellipticité max : |σx − σy| / σ. Au-delà : étoile filée (suivi), tilt…
ELLIPTICITE_MAX = 0.35
# Fenêtre de mesure : elle SUIT la taille apparente de l'étoile. Fenêtre
# FIXE = piège constaté au 1er essai (test du jalon 10 : ÉCHEC) : une fenêtre
# de ±9 px autour d'une étoile de σ ≈ 1,2 px surestimait la FWHM de 170 %,
# le bruit du fond (±9 px = 361 pixels !) pesant alors autant que les ailes
# de l'étoile dans les moments.
_DEMI_MIN = 5         # demi-fenêtre minimale (px)
_DEMI_MAX = 24        # demi-fenêtre maximale (px)
_PROFIL_DR = 0.25     # pas du profil radial (px)
# 2·√(2·ln 2) : passage σ gaussien ↔ FWHM.
FWHM_PAR_SIGMA = 2.3548200450309493
# Sous-échantillonnage du calcul de fond : la médiane d'un quart de million
# de pixels suffit largement et la mesure reste ≪ 1 ms.
MAX_PX_FOND = 262144


def _luminance(img):
    """Luminance float32 d'une image mono (H,W) ou couleur (H,W,3).

    PIÈGE (leçon du projet) : toute fonction image doit être vérifiée sur
    les DEUX dispositions — ici l'axe des canaux est le DERNIER pour le
    couleur et ABSENT pour le mono ; les deux cas sont traités, et une
    disposition inattendue lève une erreur plutôt que de rendre une image
    noire en silence."""
    a = np.asarray(img, dtype=np.float32)
    if a.ndim == 2:
        return a
    if a.ndim == 3 and a.shape[2] >= 3:
        return (0.299 * a[..., 0] + 0.587 * a[..., 1]
                + 0.114 * a[..., 2]).astype(np.float32)
    raise ValueError(f"image de dimensions inattendues : {a.shape}")


def _fond_bruit(luma):
    """(fond, bruit) d'une luminance, par médiane / 1,4826·MAD — robustes
    aux étoiles et structures (qui restent minoritaires). Sous-échantillonné
    pour rester instantané même en pleine résolution."""
    h, w = luma.shape
    pas = max(1, int(math.sqrt(max(1, h * w) / float(MAX_PX_FOND))))
    s = luma[::pas, ::pas]
    med = float(np.median(s))
    return med, 1.4826 * float(np.median(np.abs(s - med)))


def _mesure_etoile(luma, x, y, bw, bh, fond, bruit):
    """Mesure d'UNE étoile : (σ, FWHM, ellipticité) en px, ou None si
    l'objet ne ressemble pas à une étoile mesurable/isolée.

    `x, y, bw, bh` : boîte de l'objet au-dessus du seuil de détection.
    La taille apparente de la boîte FIXE la fenêtre de mesure (1,2σ à 2,8σ
    de rayon selon l'éclat de l'étoile) — cf. le piège de la fenêtre fixe
    ci-dessus.

    FWHM par PROFIL RADIAL : fond retiré (médiane d'un anneau
    périphérique, donc hors de l'étoile) SANS clip, pixels moyennés par
    anneau de 0,25 px — dans chaque moyenne le bruit s'annule, il n'y a donc
    PAS de biais de fond — puis FWHM = 2 × rayon où le profil retombe à la
    moitié de son pic (interpolation linéaire). L'ellipticité vient de
    moments d'ordre 2 pondérés et seuillés sur le seul cœur (rejet des
    étoiles filées, tilt/coma)."""
    h, w = luma.shape
    taille = 0.25 * max(bw, bh)                # rayon au seuil ≈ 1,2-2,8 σ
    sigma_g = min(max(taille, SIGMA_MIN), SIGMA_MAX)
    demi = int(min(_DEMI_MAX, max(_DEMI_MIN, round(4.0 * sigma_g) + 2)))
    y0, y1 = max(0, y - demi), min(h, y + bh + demi)
    x0, x1 = max(0, x - demi), min(w, x + bw + demi)
    sub = luma[y0:y1, x0:x1].astype(np.float64)
    ys, xs = np.mgrid[y0:y1, x0:x1]

    # --- centroïde pondéré, sur une fenêtre plus SERRÉE : une étoile
    # voisine présente dans la fenêtre large ne doit pas tirer le centre.
    demi_c = int(min(demi, max(4, round(2.0 * sigma_g) + 2)))
    proche = ((np.abs(xs - (x + bw / 2.0)) <= demi_c)
              & (np.abs(ys - (y + bh / 2.0)) <= demi_c))
    poids = np.where(proche, sub - (fond + 1.0 * bruit), 0.0)
    np.clip(poids, 0.0, None, out=poids)
    tot = float(poids.sum())
    if tot <= 0.0:
        return None
    cy = float((poids * ys).sum()) / tot
    cx = float((poids * xs).sum()) / tot
    r = np.hypot(xs - cx, ys - cy)

    # --- ellipticité : moments d'ordre 2 sur le CŒUR seulement (r ≤ 3 σ) —
    # au-delà le bruit du fond domine et masquerait l'allongement réel.
    noyau = r <= max(4.0, 3.0 * sigma_g)
    poids = np.where(noyau, poids, 0.0)
    tot = float(poids.sum())
    if tot <= 0.0:
        return None
    vx = float((poids * (xs - cx) ** 2).sum()) / tot
    vy = float((poids * (ys - cy) ** 2).sum()) / tot
    ex, ey = math.sqrt(max(vx, 0.0)), math.sqrt(max(vy, 0.0))
    if ex <= 0.0 or ey <= 0.0:
        return None
    ellipticite = abs(ex - ey) / math.sqrt(ex * ey)

    # --- profil radial (fond retiré, bruit non clipé : il s'annule) ------
    anneau = r >= 0.75 * demi                  # fond local, hors étoile
    if int(anneau.sum()) < 12:
        return None
    base = float(np.median(sub[anneau]))
    val = (sub - base).ravel()
    nb_max = int(np.floor(demi / _PROFIL_DR)) + 1
    idx = np.minimum((r.ravel() / _PROFIL_DR).astype(np.int32), nb_max - 1)
    compte = np.bincount(idx, minlength=nb_max)
    somme = np.bincount(idx, weights=val, minlength=nb_max)
    profil = np.divide(somme, compte,
                       out=np.full(nb_max, np.nan), where=compte > 0)
    rayons = (np.arange(nb_max) + 0.5) * _PROFIL_DR
    coeur = np.isfinite(profil) & (rayons <= 1.5)
    if not coeur.any():
        return None
    pic = float(np.nanmax(profil[coeur]))
    if pic <= 0.0:
        return None
    i_pic = int(np.argmax(np.where(coeur, profil, -np.inf)))
    demi_pic = 0.5 * pic
    # PIÈGE (constaté au 1er essai du jalon 10) : tous les anneaux ne
    # contiennent pas de pixel (grille entière) → certains bins sont NaN.
    # Il faut donc suivre le dernier anneau FINI au-dessus de la
    # mi-hauteur et interpoler vers le premier FINI en dessous, même s'ils
    # ne sont pas voisins — sinon 45 % des étoiles étaient perdues
    # (« pas de retombée ») alors que leur profil était parfaitement net.
    precedent = None
    for i in range(i_pic, nb_max):
        if not np.isfinite(profil[i]):
            continue
        if profil[i] >= demi_pic:
            precedent = i
        elif precedent is not None:
            frac = ((profil[precedent] - demi_pic)
                    / max(profil[precedent] - profil[i], 1e-12))
            r_half = (rayons[precedent] + float(np.clip(frac, 0.0, 1.0))
                      * (rayons[i] - rayons[precedent]))
            fwhm = 2.0 * r_half
            return fwhm / FWHM_PAR_SIGMA, fwhm, ellipticite
    return None                                # pas de retombée : trop large


def mesurer_seeing(img, seuil_sigma=SEUIL_SIGMA, max_etoiles=MAX_ETOILES):
    """Détecte les étoiles de `img` et mesure la PSF (seeing).

    Renvoie (dict, message) :
      - succès (assez d'étoiles)  → (mesure, "") ;
      - échec / mesure douteuse   → (mesure partielle, message explicite).
    Clés de `mesure` : nb (étoiles exploitables), fwhm, sigma, ellipticite
    (médianes, en px), objets (objets détectés au-dessus du seuil), seuil,
    fond, bruit. `img` n'est JAMAIS modifiée."""
    try:
        luma = _luminance(img)
        h, w = luma.shape
        if min(h, w) < 4 * _DEMI_MIN + 8:
            return {}, ("image trop petite pour mesurer le seeing "
                        f"({w}×{h} px)")
        fond, bruit = _fond_bruit(luma)
        if bruit <= 1e-9:
            return {"nb": 0, "fond": fond, "bruit": bruit}, \
                "image constante : aucune étoile détectable"
        seuil = fond + float(seuil_sigma) * bruit

        masque = (luma > seuil).astype(np.uint8)
        nb_obj, _labels, stats, _ = cv2.connectedComponentsWithStats(
            masque, connectivity=8)

        # --- 1er tri (grossier, sans moments) : aire, bords, éclat -------
        cands = []
        for i in range(1, nb_obj):
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            bw = int(stats[i, cv2.CC_STAT_WIDTH])
            bh = int(stats[i, cv2.CC_STAT_HEIGHT])
            aire = int(stats[i, cv2.CC_STAT_AREA])
            if aire < AIRE_MIN or aire > AIRE_MAX:
                continue
            if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
                continue        # touche un bord : mesure incomplète
            pic = float(luma[y:y + bh, x:x + bw].max())
            cands.append((pic, x, y, bw, bh))
        cands.sort(key=lambda c: -c[0])

        # --- 2e tri (fin) : profil radial + ellipticité par étoile -------
        fwhms, sigmas, ellips = [], [], []
        for _pic, x, y, bw, bh in cands[:int(max_etoiles)]:
            mes = _mesure_etoile(luma, x, y, bw, bh, fond, bruit)
            if mes is None:
                continue
            sig, fwhm, el = mes
            if not (SIGMA_MIN <= sig <= SIGMA_MAX) or el > ELLIPTICITE_MAX:
                continue
            sigmas.append(sig)
            fwhms.append(fwhm)
            ellips.append(el)

        base = {"nb": len(fwhms), "objets": int(nb_obj - 1),
                "seuil": seuil, "fond": fond, "bruit": bruit}
        if not fwhms:
            return base, ("pas assez d'étoiles détectées (0 exploitable) : "
                          "seeing indisponible")
        mesure = dict(base, fwhm=float(np.median(fwhms)),
                      sigma=float(np.median(sigmas)),
                      ellipticite=float(np.median(ellips)))
        if len(fwhms) < MIN_ETOILES:
            return mesure, (f"pas assez d'étoiles détectées ({len(fwhms)}) : "
                            "mesure peu fiable")
        return mesure, ""
    except Exception as exc:                 # mémoire, image dégénérée…
        return {}, str(exc)


def sigma_depuis_fwhm(fwhm):
    """σ gaussien (px) correspondant à une FWHM (px) — PSF de la netteté."""
    return max(float(fwhm), 0.0) / FWHM_PAR_SIGMA


def fwhm_depuis_sigma(sigma):
    """FWHM (px) correspondant à un σ gaussien (px)."""
    return FWHM_PAR_SIGMA * max(float(sigma), 0.0)


def detecter_positions(img, max_etoiles=MAX_ETOILES, seuil_sigma=SEUIL_SIGMA):
    """Positions (centroïdes) des étoiles les plus brillantes — prérequis de
    l'ALIGNEMENT par étoiles (jalon 13) : sur un champ pauvre en étoiles et
    riche en nébulosité (C8 à 1280 mm, constat réel du 17/09/2026), les
    descripteurs ORB ne s'apparient plus (0-6 appariements sur 1000 points)
    alors que les CENTROÏDES, eux, se votent très bien (translation estimée
    par histogramme des paires). Même 1re étape de détection que
    `mesurer_seeing` (luminance, fond/bruit par médiane-MAD, seuil k·σ,
    composantes 8-connexes, rejet des surfaces), SANS la mesure de profil
    (inutile ici, et elle écarte des étoiles utilisables pour l'appariement) :
    centroïde pondéré par l'intensité, tri par éclat décroissant, plafonné à
    `max_etoiles`.

    Renvoie (positions, message) — convention du module : (résultat, "") en
    succès, (résultat partiel, message explicite) sinon. `positions` est un
    numpy (N, 2) float32 en (x, y) PIXELS DE L'IMAGE FOURNIE, éventuellement
    vide. `img` n'est JAMAIS modifiée."""
    try:
        luma = _luminance(img)
        h, w = luma.shape
        if min(h, w) < 8:
            return np.zeros((0, 2), np.float32), \
                f"image trop petite ({w}×{h} px)"
        fond, bruit = _fond_bruit(luma)
        if bruit <= 1e-9:
            return np.zeros((0, 2), np.float32), "image constante"
        masque = (luma > fond + float(seuil_sigma) * bruit).astype(np.uint8)
        nb_obj, _labels, stats, _ = cv2.connectedComponentsWithStats(
            masque, connectivity=8)
        cands = []
        for i in range(1, nb_obj):
            x = int(stats[i, cv2.CC_STAT_LEFT])
            y = int(stats[i, cv2.CC_STAT_TOP])
            bw = int(stats[i, cv2.CC_STAT_WIDTH])
            bh = int(stats[i, cv2.CC_STAT_HEIGHT])
            aire = int(stats[i, cv2.CC_STAT_AREA])
            if aire < AIRE_MIN or aire > AIRE_MAX:
                continue
            if x <= 1 or y <= 1 or x + bw >= w - 1 or y + bh >= h - 1:
                continue        # touche un bord : centroïde incomplet
            pic = float(luma[y:y + bh, x:x + bw].max())
            cands.append((pic, x, y, bw, bh))
        cands.sort(key=lambda c: -c[0])
        pos = []
        for _pic, x, y, bw, bh in cands[:int(max_etoiles)]:
            sub = np.clip(luma[y:y + bh, x:x + bw] - fond, 0.0, None)
            s = float(sub.sum())
            if s <= 0.0:        # composante au seuil mais sous le fond
                pos.append((x + bw / 2.0, y + bh / 2.0))
                continue
            ys, xs = np.mgrid[y:y + bh, x:x + bw]
            pos.append((float((xs * sub).sum() / s),
                        float((ys * sub).sum() / s)))
        return np.array(pos, np.float32).reshape(-1, 2), ""
    except Exception as exc:                 # mémoire, image dégénérée…
        return np.zeros((0, 2), np.float32), str(exc)
