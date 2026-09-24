# -*- coding: utf-8 -*-
"""Photométrie de l'empilement — zéro-point instrumental PAR BANDE (jalon 56,
étape 4).

Apparie les étoiles DÉTECTÉES dans l'empilement aux étoiles du catalogue Gaia
de Siril (positions + magnitude G) grâce au WCS résolu puis PROPAGÉ (étapes
2-3 du jalon), et mesure un zéro-point instrumental par bande :

    m_G(catalogue) + 2,5·log10(flux_image) = ZP(bande)

L'écart de zéro-point ENTRE BANDES est exactement le déséquilibre de
sensibilité à corriger (étape 5 : application aux gains du stacker) — c'est la
version RELATIVE et VÉRIFIABLE de la SPCC, mesurable sur une image synthétique.
La SPCC « absolue » (spectres Gaia `xp_sampled` × transmissions filtre/capteur
de la base Siril) viendra ensuite : elle exige la base SPCC de Siril, alors
qu'ICI aucun spectre n'est nécessaire.

Règles de CLAUDE.md appliquées :
  • appariement MUTUEL (le plus proche des DEUX côtés) : un appariement non
    mutuel injecte des correspondances fantômes qui faussent la mesure — et ici
    l'appariement sert d'ANCRE pour toute la photométrie ;
  • rejet 3σ ROBUSTE (MAD) sur les résidus, jamais une moyenne brute ;
  • flux par OUVERTURE moins fond local (jamais le pixel du pic : le cœur d'une
    PSF sature bien avant le reste) ;
  • étoiles saturées ÉCARTÉES (proches de la plus brillante détectée) ;
  • aucune panne silencieuse : chaque refus est expliqué, jamais une valeur
    inventée. Convention du projet : (résultat, message), jamais d'exception.

Ce module vit dans `processing` (glue) : la fondation `catalogues` ne doit
jamais dépendre du processing (cycle d'import), l'inverse est permis.
"""

import math

import numpy as np

from ..catalogues import CatalogueSiril, dossier_catalogues
from ..catalogues.telechargeur import etat_local
from ..processing import stars as _stars

# --- Réglages (surchargeables par les bancs) ---------------------------------
RAYON_APPARIEMENT_PX = 2.5   # tolérance d'appariement (px) : le WCS est bon à
                             # quelques dixièmes de px ; 2,5 px couvre la
                             # distorsion résiduelle sans apparier à tort
MIN_ETOILES = 8              # en dessous : aucun facteur (mesure non fiable)
MAG_MARGE_SATURATION = 0.5   # étoiles à moins de 0,5 mag de la plus brillante
                             # détectée : écartées (cœur de PSF non linéaire)
GAIN_MIN, GAIN_MAX = 0.25, 4.0   # mêmes bornes que l'équilibrage/Linear Fit
SIGMA_REJET = 3.0            # rejet robuste des résidus (MAD)
PLANCHER_SIGMA_MAG = 0.05    # plancher du seuil de rejet (mag) : sur des
                             # mesures parfaites le MAD vaut 0 et plus aucune
                             # aberration ne serait retirée
BORD_MARGE_PX = 12.0         # étoiles trop près du bord : flux tronqué
RAYON_FLUX_PX = 3.0          # rayon d'ouverture du flux (px)
ANNEAU_FOND = (5.0, 8.0)     # anneau de mesure du fond local (px)
MAX_ETOILES_PHOTO = 300      # étoiles les plus brillantes analysées
MAX_ESSAIS = 4               # tentatives de mesure par session (réessais
                             # espacés : un empilement plus profond aide)
DELAI_ESSAI_S = 20.0         # délai minimal entre deux tentatives


def canal_photometrique(img):
    """Canal utilisé pour DÉTECTER les étoiles : vert si couleur (même
    convention que l'alignement et le solveur), tel quel en mono. → (H, W)
    float32."""
    a = np.asarray(img)
    if a.ndim == 2:
        return a.astype(np.float32, copy=False)
    if a.ndim == 3:
        if a.shape[0] <= 4 and a.shape[-1] > 4:      # canaux-en-tête (C, H, W)
            a = np.transpose(a, (1, 2, 0))
        return np.ascontiguousarray(a[..., 1], dtype=np.float32)
    raise ValueError(f"image de rang inattendu : {a.shape}")


def flux_ouverture(mono, positions, rayon=RAYON_FLUX_PX,
                   anneau=ANNEAU_FOND):
    """Flux de chaque étoile par OUVERTURE, en unités de l'image.

    Somme du disque `rayon` MOINS le fond local : médiane de l'anneau
    (rayon…rayon+anneau) × aire du disque. Le fond local — et non un fond
    global — parce qu'un gradient (pollution lumineuse) rend un fond global
    faux ; la médiane est insensible aux étoiles voisines qui tomberaient dans
    l'anneau. → (flux (N,) float64 — NaN si l'ouverture sort de l'image)."""
    p = np.asarray(positions, dtype=np.float64).reshape(-1, 2)
    img = np.asarray(mono, dtype=np.float64)
    h, w = img.shape
    r_in = float(rayon)
    r_out = float(rayon) + float(anneau[1])
    r_bas = float(rayon) + float(anneau[0])
    out = np.full(len(p), np.nan, dtype=np.float64)
    for i, (x, y) in enumerate(p):
        ix, iy = int(round(x)), int(round(y))
        if (ix - r_out < 0 or iy - r_out < 0
                or ix + r_out > w - 1 or iy + r_out > h - 1):
            continue                              # bord : flux tronqué
        x0, x1 = int(math.floor(x - r_out)), int(math.ceil(x + r_out)) + 1
        y0, y1 = int(math.floor(y - r_out)), int(math.ceil(y + r_out)) + 1
        # PIÈGE (vérifié en réel le 24/09/2026 sur un crop 1024×1024 d'une
        # couche M31) : à cause de l'arrondi du centre (± 0,5 px), ces bornes
        # peuvent SORTIR de l'image alors que le contrôle ci-dessus est passé
        # (x = 24,49 avec r_out = 23,5 → x0 = 0 mais y = 23,49 → y0 = -1).
        # numpy TRONQUE alors silencieusement la zone (`img[-1:y1]`,
        # `img[:h+1]`) pendant que `np.mgrid` garde la taille THÉORIQUE : le
        # masque du disque ne correspond plus à la zone (IndexError). On
        # ramène donc les bornes DANS l'image — le disque reste entier, la
        # marge d'anneau (r_out - r_in) couvrant l'arrondi du centre.
        x0, x1 = max(0, x0), min(w, x1)
        y0, y1 = max(0, y0), min(h, y1)
        if x1 - x0 < 1 or y1 - y0 < 1:
            continue
        zone = img[y0:y1, x0:x1]
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d = np.hypot(xx - x, yy - y)
        disque = d <= r_in
        fond = (d >= r_bas) & (d <= r_out)
        if not disque.any() or int(fond.sum()) < 8:
            continue
        out[i] = (float(zone[disque].sum())
                  - float(np.median(zone[fond])) * int(disque.sum()))
    return out


def etoiles_image(img, max_etoiles=MAX_ETOILES_PHOTO):
    """Étoiles de l'image : positions (N, 2) et FLUX par ouverture.
    → (positions, flux, message) ; listes vides + raison si rien d'exploitable.
    Réutilise `processing.stars.detecter_positions` (le détecteur du projet,
    celui de l'alignement) : aucune seconde détection à maintenir."""
    try:
        mono = canal_photometrique(img)
    except Exception as exc:
        return np.zeros((0, 2)), np.zeros(0), f"image inexploitable ({exc})"
    h, w = mono.shape
    if min(h, w) < 32:
        return np.zeros((0, 2)), np.zeros(0), f"image trop petite ({w}×{h})"
    pos, msg = _stars.detecter_positions(mono, max_etoiles=max_etoiles)
    if pos is None or len(pos) == 0:
        return np.zeros((0, 2)), np.zeros(0), (msg or "aucune étoile détectée")
    flux = flux_ouverture(mono, pos)
    garde = np.isfinite(flux) & (flux > 0.0)
    garde &= ((pos[:, 0] > BORD_MARGE_PX) & (pos[:, 0] < w - 1 - BORD_MARGE_PX)
              & (pos[:, 1] > BORD_MARGE_PX)
              & (pos[:, 1] < h - 1 - BORD_MARGE_PX))
    pos, flux = pos[garde], flux[garde]
    if len(pos) == 0:
        return (np.zeros((0, 2)), np.zeros(0),
                f"aucune étoile exploitable ({msg or 'bords'} )")
    return pos, flux, ""


def etoiles_catalogue(wcs, forme, dossier=None, limmag=None):
    """Étoiles Gaia du CHAMP décrit par `wcs` → (dict {"ra","dec","g"}, message).

    Le rayon d'extraction est DÉDUIT du WCS (coins de l'image projetés au ciel) :
    aucune supposition sur l'orientation ni sur l'échelle — c'est le WCS qui
    dit la vérité du champ. Catalogue absent → ({}, raison) : la photométrie ne
    se lance pas, elle ne devine pas."""
    if wcs is None:
        return {}, "WCS absent (astrométrie non résolue)"
    try:
        h, w = (tuple(int(v) for v in forme) if forme
                else tuple(getattr(wcs, "forme", ()) or ()))
    except (TypeError, ValueError):
        return {}, f"forme inutilisable ({forme})"
    if not h or not w:
        return {}, "forme (h, w) requise pour délimiter le champ"
    coins = np.array([[0.0, 0.0], [w - 1.0, 0.0], [0.0, h - 1.0],
                      [w - 1.0, h - 1.0], [(w - 1) / 2.0, (h - 1) / 2.0]])
    try:
        ra_c, dec_c = wcs.vers_radec(coins)
        # PIÈGE : `float(tableau)` ne marche que pour UNE valeur — le WCS rend
        # ici 5 positions (les 4 coins + le centre) : ravel PUIS indexation.
        ra_c = np.asarray(ra_c, dtype=np.float64).ravel()
        dec_c = np.asarray(dec_c, dtype=np.float64).ravel()
    except Exception as exc:
        return {}, f"WCS inexploitable ({exc})"
    ra0, dec0 = ra_c[4], dec_c[4]
    cosd = math.cos(math.radians(dec0))
    # np.hypot (PAS math.hypot) : ra_c/dec_c sont des TABLEAUX (5 positions).
    dist = np.hypot((ra_c - ra0) * cosd, dec_c - dec0)
    rayon = float(dist.max()) + 0.1          # marge : bords de détection
    d = dossier or dossier_catalogues()
    etat = etat_local(d)
    if not etat.get("astro"):
        return {}, (f"catalogue Gaia astrométrique de Siril introuvable dans "
                    f"{d} (téléchargeur, jalon 56 étape 1)")
    try:
        cat = CatalogueSiril(etat["astro"])
        et = cat.extraire(ra0, dec0, rayon, limmag=limmag)
    except Exception as exc:
        return {}, f"lecture du catalogue impossible ({exc})"
    if len(et.get("ra", ())) == 0:
        return {}, f"aucune étoile de catalogue dans le champ (r={rayon:.3f}°)"
    return ({"ra": np.asarray(et["ra"]), "dec": np.asarray(et["dec"]),
             "g": np.asarray(et["g"])},
            f"{len(et['ra'])} étoiles de catalogue (r={rayon:.3f}°)")


def apparier(pos_px, wcs, cat, rayon_px=RAYON_APPARIEMENT_PX):
    """Appariement MUTUEL étoiles-image ↔ étoiles-catalogue via le WCS.

    MUTUEL = la même paire est la plus proche des DEUX côtés (règle de
    CLAUDE.md : un appariement qui sert d'ANCRE — et la photométrie en est une
    — doit être mutuel, sinon des correspondances fantômes faussent la mesure).
    Distance évaluée en PIXELS (via l'échelle du WCS) : c'est le repère où la
    tolérance a un sens physique (largeur de PSF).

    → (dict ia, ic, d_px, ra, dec, mag, message) ; listes vides + raison."""
    if wcs is None:
        return {"ia": np.zeros(0, int), "ic": np.zeros(0, int)}, "WCS absent"
    if len(pos_px) == 0 or len(cat.get("ra", ())) == 0:
        return {"ia": np.zeros(0, int), "ic": np.zeros(0, int)}, \
            "rien à apparier (image ou catalogue vide)"
    try:
        ra_i, dec_i = wcs.vers_radec(np.asarray(pos_px, dtype=np.float64))
        ra_i, dec_i = np.ravel(ra_i), np.ravel(dec_i)
        ech = float(wcs.echelle_arcsec)          # ″/px local
    except Exception as exc:
        return {"ia": np.zeros(0, int), "ic": np.zeros(0, int)}, \
            f"projection impossible ({exc})"
    if not np.isfinite(ech) or ech <= 0.0:
        return {"ia": np.zeros(0, int), "ic": np.zeros(0, int)}, \
            f"échelle inutilisable ({ech})"
    cosd = math.cos(math.radians(float(np.median(dec_i))))
    dra = (ra_i[:, None] - cat["ra"][None, :]) * cosd
    ddec = dec_i[:, None] - cat["dec"][None, :]
    d_px = np.hypot(dra, ddec) * 3600.0 / ech        # (N_img, N_cat)
    vers_cat = np.argmin(d_px, axis=1)               # meilleur cat. par image
    vers_img = np.argmin(d_px, axis=0)               # meilleure image par cat.
    ia, ic = [], []
    for i, j in enumerate(vers_cat):
        if int(vers_img[j]) == i and d_px[i, j] <= rayon_px:
            ia.append(i)
            ic.append(int(j))                        # MUTUEL + dans la tolérance
    out = {"ia": np.asarray(ia, dtype=int), "ic": np.asarray(ic, dtype=int)}
    if len(ia) == 0:
        return out, (f"aucun appariement mutuel (tolérance {rayon_px} px, "
                     f"{d_px.min():.2f} px au plus près)")
    out["d_px"] = d_px[out["ia"], out["ic"]]
    out["ra"] = ra_i[out["ia"]]
    out["dec"] = dec_i[out["ia"]]
    out["mag"] = cat["g"][out["ic"]]
    return out, (f"{len(ia)} appariements mutuels "
                 f"(médiane {float(np.median(out['d_px'])):.2f} px)")


def zero_point(mag, flux, sigma=SIGMA_REJET):
    """Zéro-point instrumental d'une bande : ZP = mag_catalogue +
    2,5·log10(flux_image), estimé par MÉDIANE avec rejet robuste (MAD).

    Pourquoi la médiane et pas la moyenne : une seule étoile mal appariée ou
    variable décalerait une moyenne ; la médiane ignore les traînantes — et le
    rejet 3σ (sur les résidus au sens robuste) retire les vraies aberrations du
    lot gardé. → (zp, rms_mag, n_gardés, message)."""
    mag = np.asarray(mag, dtype=np.float64)
    flux = np.asarray(flux, dtype=np.float64)
    ok = np.isfinite(mag) & np.isfinite(flux) & (flux > 0.0)
    mag, flux = mag[ok], flux[ok]
    if len(mag) < MIN_ETOILES:
        return None, None, int(len(mag)), (f"trop peu d'étoiles appariées "
                                           f"({len(mag)} < {MIN_ETOILES})")
    z = mag + 2.5 * np.log10(flux)
    med = float(np.median(z))
    mad = float(np.median(np.abs(z - med)))
    sig = 1.4826 * mad
    # PLANCHER de rejet (0,05 mag) : sur des mesures PARFAITES (banc, image
    # idéale) le MAD vaut 0 et aucune aberration ne serait retirée — le
    # plancher garde le rejet opérant sans jamais éliminer un lot sain.
    seuil = max(sigma * sig, PLANCHER_SIGMA_MAG)
    garde = np.abs(z - med) <= seuil
    if int(garde.sum()) >= MIN_ETOILES:
        z = z[garde]
        mag = mag[garde]
        flux = flux[garde]
        med = float(np.median(z))
    res = mag + 2.5 * np.log10(flux) - med
    rms = float(np.sqrt(np.mean(res * res)))
    return med, rms, int(len(z)), ""


def gains_depuis_zp(zp_par_bande):
    """Gain RELATIF par bande depuis les zéro-points → ({bande: gain}, message).

    Physique : une étoile de magnitude m donne flux_b = 10^(0,4·(ZP_b − m)) ;
    ramener la bande b sur le zéro-point de référence demande donc le facteur
    gain_b = 10^(0,4·(ZP_ref − ZP_b)) — exactement le genre de facteur que
    l'étape 5 posera sur les gains du stacker.

    La RÉFÉRENCE est la bande MÉDIANE des zéro-points mesurés : les corrections
    se répartissent des deux côtés, plutôt qu'une bande arbitrairement
    intouchée (choix explicite, réversible en changeant la référence)."""
    paires = [(b, zp) for b, zp in (zp_par_bande or {}).items()
              if zp is not None and np.isfinite(zp)]
    if not paires:
        return {}, "aucun zéro-point mesuré"
    zp_ref = float(np.median([zp for _b, zp in paires]))
    gains, bornes = {}, []
    for b, zp in paires:
        g = float(10.0 ** (0.4 * (zp_ref - float(zp))))
        if not (GAIN_MIN <= g <= GAIN_MAX):
            bornes.append(f"{b} ({g:.3f})")
            continue
        gains[b] = g
    msg = f"référence : ZP médian {zp_ref:.3f}"
    if bornes:
        msg += f" — gain(s) hors bornes, ignoré(s) : {', '.join(bornes)}"
    return gains, msg


class Photometrie:
    """Zéro-point instrumental PAR BANDE de l'empilement (jalon 56, étape 4).

    Cycle de vie dans le worker : `mesurer(canaux, wcs)` quand l'astrométrie
    est RÉSOLUE et l'empilement assez profond ; le résultat (zéro-points,
    gains relatifs, nombre d'appariements) est exposé à l'UI. L'APPLICATION de
    ces gains au stacker est l'étape 5 — ici on MESURE, on n'applique rien.

    `canaux` : {bande: image 2D} — {"L": accumulation} en mono, les cartes par
    rôle en composition (toutes sur la MÊME grille, celle du WCS fourni).
    `catalogue` est INJECTABLE (bancs : catalogue factice, aucun Gaia requis) ;
    par défaut `etoiles_catalogue` (catalogue Siril réel)."""

    def __init__(self, catalogue=None, dossier=None, limmag=None):
        self._catalogue = catalogue or etoiles_catalogue
        self.dossier = dossier
        self.limmag = limmag
        self.reset()

    def reset(self):
        """Session neuve : aucune mesure, aucun facteur."""
        self.zp = {}               # bande → zéro-point instrumental
        self.gains = {}            # bande → gain relatif (étape 5)
        self.bandes = {}           # bande → dict complet (n, rms, d_px…)
        self.n_paires = 0
        self.derniere_erreur = ""
        self.mesures = 0           # nombre de mesures réussies (session)
        self._motif = []           # bandes écartées et pourquoi (dernière mesure)

    @property
    def valide(self):
        """Une mesure exploitable est disponible ?"""
        return bool(self.gains)

    def mesurer(self, canaux, wcs, forme=None):
        """Mesure les zéro-points puis les gains relatifs. → (dict|None, message).

        `canaux` : {bande: image 2D}. La forme de référence est celle du PREMIER
        canal (toutes les bandes d'un même empilement partagent la grille) ;
        `forme` peut la forcer. Chaque bande est détectée et appariée
        INDÉPENDAMMENT (un filtre étroit ne montre pas les mêmes étoiles) — le
        catalogue, lui, est commun. Jamais d'exception."""
        if not canaux:
            self.derniere_erreur = "aucun canal à mesurer"
            return None, self.derniere_erreur
        if wcs is None:
            self.derniere_erreur = "astrométrie non résolue (WCS absent)"
            return None, self.derniere_erreur
        bandes = [b for b in canaux if canaux[b] is not None]
        if not bandes:
            self.derniere_erreur = "canaux vides"
            return None, self.derniere_erreur
        try:
            h, w = (tuple(int(v) for v in forme) if forme
                    else tuple(np.asarray(canaux[bandes[0]]).shape[:2]))
        except Exception as exc:
            self.derniere_erreur = f"forme inutilisable ({exc})"
            return None, self.derniere_erreur
        cat, msg_cat = self._catalogue(wcs, (h, w))
        if not cat:
            self.derniere_erreur = f"catalogue indisponible — {msg_cat}"
            return None, self.derniere_erreur

        detail, motif = {}, []
        for b in bandes:
            pos, flux, msg = etoiles_image(canaux[b])
            if len(pos) == 0:
                motif.append(f"{b} : {msg}")
                continue
            # Étoiles SATURÉES écartées : à moins de MAG_MARGE_SATURATION de
            # l'étoile la plus brillante de la bande, le cœur de PSF n'est plus
            # linéaire (flux sous-estimé → zéro-point biaisé).
            rel = -2.5 * np.log10(flux / float(np.nanmax(flux)))
            garde = rel > MAG_MARGE_SATURATION
            if int(garde.sum()) < MIN_ETOILES:
                motif.append(f"{b} : {int(garde.sum())} étoiles non saturées "
                             f"(< {MIN_ETOILES})")
                continue
            pos_b, flux_b = pos[garde], flux[garde]
            ap, msg_ap = apparier(pos_b, wcs, cat)
            ia, ic = ap["ia"], ap["ic"]
            if len(ia) == 0:
                motif.append(f"{b} : {msg_ap}")
                continue
            zp, rms, n, msg_zp = zero_point(ap["mag"], flux_b[ia])
            if zp is None:
                motif.append(f"{b} : {msg_zp}")
                continue
            detail[b] = {"zp": float(zp), "rms_mag": float(rms), "n": int(n),
                         "n_mutuels": int(len(ia)),
                         "d_px": float(np.median(ap["d_px"])),
                         "mag_min": float(np.min(ap["mag"])),
                         "mag_max": float(np.max(ap["mag"]))}
        if not detail:
            self.derniere_erreur = ("aucune bande mesurable — "
                                    + " ; ".join(motif))
            return None, self.derniere_erreur
        gains, msg_g = gains_depuis_zp({b: d["zp"] for b, d in detail.items()})
        self.bandes = detail
        self.zp = {b: d["zp"] for b, d in detail.items()}
        self.gains = dict(gains)
        self.n_paires = int(sum(d["n"] for d in detail.values()))
        self.mesures += 1
        self.derniere_erreur = ""
        self._motif = motif
        return {"bandes": dict(detail), "gains": dict(gains),
                "n_paires": self.n_paires, "motif": list(motif)}, msg_g

    def texte_resume(self):
        """Ligne d'état : zéro-points et gains mesurés par bande, en clair.
        "" si aucune mesure exploitable."""
        if not self.bandes:
            return ""
        morceaux = []
        for b in sorted(self.bandes):
            d = self.bandes[b]
            g = self.gains.get(b)
            morceaux.append(
                f"{b} ZP {d['zp']:.3f} (σ {d['rms_mag']:.3f}, {d['n']} ét.)"
                + (f" → ×{g:.4f}" if g is not None else ""))
        txt = ("Photométrie (Gaia G) : " + " · ".join(morceaux)
               + f" — {self.n_paires} appariements")
        if self._motif:
            txt += " · sans " + ", ".join(self._motif)
        return txt
