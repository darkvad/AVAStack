# -*- coding: utf-8 -*-
"""Câblage du moteur d'étirement VeraLux (code TIERS) dans AVAStack.

`veralux_core_headless.py` (racine du dépôt) est du code TIERS sous licence
GPL-3.0-or-later (extrait de VeraLux_HyperMetric_Stretch.py v1.5.2,
Riccardo Paterniti). Ce module l'IMPORTE sans jamais le modifier ; il
n'apporte que l'adaptation des formats :
  - le moteur renvoie le RGB en (canaux, H, W), AVAStack travaille en
    (H, W, canaux) ;
  - les caméras live livrent du (H, W) mono ou (H, W, 3) RGB.

Règles de sécurité (leçons des tentatives précédentes, cf. AVANCEMENT.md) :
  - l'image d'entrée n'est JAMAIS modifiée (copie défensive RÉELLE) et elle est
    ramenée dans [0, 1] par UN SEUL facteur GLOBAL (`normaliser_lin`) : le
    `normalize_input` du moteur divise par 65 535 tout float dont le max dépasse
    1.1, et une donnée recalée peut être légèrement négative. v2.37.2 : c'était
    un CLIP à 1,0 — l'empilement vivant à une échelle arbitraire (facteur global
    13 à 18, cf. AVASCALE des fichiers d'Alain), tout ce qui dépassait 1,0 (le
    CŒUR de M31 entier) était écrasé sur une valeur unique : rendu PLAT, sans
    dégradé, alors que le fichier sauvegardé, lui, garde son dégradé ;
  - VeraLux n'écrit jamais dans les réglages de l'afficheur
    (black/white/gamma restent la propriété du STF / du mode manuel).
"""

import os
import sys

import numpy as np

# --- Import du moteur tiers -------------------------------------------------
# La racine du projet (parent du package avastack) est déduite de __file__,
# PAS du répertoire courant : l'appli doit trouver le moteur même lancée via
# l'installateur depuis un autre dossier.
_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _RACINE not in sys.path:
    sys.path.insert(0, _RACINE)

try:
    from veralux_core_headless import SENSOR_PROFILES, solve_and_stretch
    MOTEUR_DISPONIBLE = True
    _ERREUR_IMPORT = ""
except ImportError as exc:            # moteur absent/corrompu : l'appli doit
    SENSOR_PROFILES = {}              # continuer à fonctionner en STF
    MOTEUR_DISPONIBLE = False
    _ERREUR_IMPORT = str(exc)

PROFIL_PAR_DEFAUT = "Rec.709 (Recommended)"

MODE_TARGET_BG = "target_bg"   # résolution automatique du logD pour amener
                               # le fond du ciel à target_bg
MODE_LOG_D = "log_d"           # logD imposé : déterministe, réactif, sans
                               # résolution itérative

TARGET_BG_PAR_DEFAUT = 0.20
LOG_D_PAR_DEFAUT = 2.0
PROTECT_B_PAR_DEFAUT = 6.0
CONVERGENCE_POWER_PAR_DEFAUT = 3.5


def normaliser_lin(img):
    """Ramène une image LINÉAIRE dans [0, 1] par UN SEUL facteur global.

    v2.37.2 — CORRECTIF DU CŒUR « CRAMÉ ». L'empilement vit en mémoire à une
    échelle arbitraire (le facteur global retiré à l'écriture des fichiers
    linéaires, `images.borner_lineaire`, valait 13 à 18 sur les empilements
    M31 d'Alain). Le chemin d'étirement COUPAIT jusqu'ici à 1,0 AVANT
    l'étirement : tout ce qui dépassait — c'est-à-dire TOUT le cœur de M31
    (0,4 à 0,8 % de l'image) — devenait une valeur UNIQUE, donc un disque
    blanc PLAT sans aucun dégradé, alors que le MÊME étirement appliqué au
    fichier sauvegardé (borné, lui, par un facteur global) restituait un cœur
    finement dégradé. Mesuré sur son empilement M31 (anneaux du cœur, % du
    canal vert) : 86,0 → 86,0 → 86,0 → 86,0 APRÈS la coupe, contre
    85,8 → 78,7 → 73,1 → 67,4 → 62,6 AVEC la mise à l'échelle.

    Règle (identique à celle des sauvegardes linéaires) : UN SEUL facteur
    GLOBAL, jamais par canal — linéarité, équilibre des couleurs et dégradé du
    cœur préservés ; le rendu ne dépend plus de l'échelle arbitraire de
    l'empilement.

    - valeurs non finies neutralisées, négatives ramenées à 0 (un recalage
      géométrique peut en produire) ;
    - max ≤ 1 : image renvoyée telle quelle (cas inchangé, aucun facteur) ;
    - max > 1 : division par le max ;
    - l'ENTRÉE n'est jamais modifiée : copie RÉELLE (l'ancien `np.clip` avec
      `out=img` écrivait, lui, dans le tableau de l'appelant).
    """
    img = np.array(img, dtype=np.float32)          # copie défensive RÉELLE
    img = np.nan_to_num(img, nan=0.0, posinf=1.0, neginf=0.0)
    np.maximum(img, 0.0, out=img)
    mx = float(img.max()) if img.size else 0.0
    if mx > 1.0:
        img /= mx
    return img


def profils_disponibles():
    """Clés de SENSOR_PROFILES (liste des profils capteur du moteur)."""
    return tuple(SENSOR_PROFILES.keys()) if MOTEUR_DISPONIBLE else ()


def profil_existe(nom):
    return MOTEUR_DISPONIBLE and nom in SENSOR_PROFILES


def moteur_disponible():
    return MOTEUR_DISPONIBLE


def etirer(img, mode=MODE_TARGET_BG, target_bg=TARGET_BG_PAR_DEFAUT,
           log_d=LOG_D_PAR_DEFAUT, profil=PROFIL_PAR_DEFAUT,
           protect_b=PROTECT_B_PAR_DEFAUT,
           convergence_power=CONVERGENCE_POWER_PAR_DEFAUT,
           use_adaptive_anchor=True, color_grip=1.0, shadow_convergence=0.0):
    """Applique l'étirement hyperbolique VeraLux à une image linéaire.

    img     : (H, W) mono ou (H, W, 3) RGB, float, valeurs linéaires à une
              échelle QUELCONQUE (mise à l'échelle globale défensive, jamais de
              coupe : cf. `normaliser_lin`).
    mode    : MODE_TARGET_BG — le logD est résolu pour amener le fond à
              `target_bg` (résolution itérative du moteur, avec pression
              d'étoiles) ;
              MODE_LOG_D — logD imposé (`log_d`) : pas de résolution,
              résultat déterministe et rapide.
    profil  : clé de SENSOR_PROFILES (pondérations de luminance).

    Retourne (image_étirée float32 de MÊME forme que l'entrée ([H, W] ou
    [H, W, 3]), valeurs [0, 1] ; log_d utilisé ; dict de diagnostics).

    Lève RuntimeError si le moteur tiers est indisponible.
    """
    if not MOTEUR_DISPONIBLE:
        raise RuntimeError("Moteur VeraLux indisponible "
                           "(veralux_core_headless.py) : "
                           + (_ERREUR_IMPORT or "fichier absent"))

    profil = profil if profil_existe(profil) else PROFIL_PAR_DEFAUT

    # Ramenée dans [0, 1] par UN SEUL facteur GLOBAL (v2.37.2 : plus de coupe à
    # 1,0 — elle écrasait le cœur de M31 sur une valeur unique, donc un disque
    # plat ; l'entrée n'est jamais modifiée, cf. normaliser_lin) :
    # - piège normalize_input (max > 1.1 → division par 65 535) ;
    # - une donnée passée par recalage géométrique peut être < 0.
    img = normaliser_lin(img)

    mode = MODE_LOG_D if mode == MODE_LOG_D else MODE_TARGET_BG
    log_d_override = float(log_d) if mode == MODE_LOG_D else None

    result, log_d_utilise, diagnostics = solve_and_stretch(
        img, working_space=profil, target_bg=float(target_bg),
        protect_b=float(protect_b),
        convergence_power=float(convergence_power),
        use_adaptive_anchor=use_adaptive_anchor,
        log_d_override=log_d_override, color_grip=float(color_grip),
        shadow_convergence=float(shadow_convergence))

    # Le moteur renvoie le RGB en (3, H, W) → repasse en (H, W, 3).
    if result.ndim == 3 and result.shape[0] == 3 and img.ndim == 3 \
            and img.shape[2] == 3:
        result = result.transpose(1, 2, 0)

    return result, float(log_d_utilise), diagnostics