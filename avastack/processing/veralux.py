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
  - l'image d'entrée n'est JAMAIS modifiée (copie défensive + clip [0, 1] :
    le `normalize_input` du moteur divise par 65 535 tout float dont le max
    dépasse 1.1, et une donnée recalée peut être légèrement négative) ;
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

    img     : (H, W) mono ou (H, W, 3) RGB, float, valeurs linéaires
              attendues dans [0, 1] (clippées défensivement).
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

    # Copie défensive (astype copie) + nettoyage + clip [0, 1] :
    # - piége normalize_input (max > 1.1 → division par 65 535) ;
    # - une donnée passée par recalage géométrique peut être < 0.
    img = np.asarray(img, dtype=np.float32)
    img = np.nan_to_num(img, nan=0.0, posinf=1.0, neginf=0.0)
    np.clip(img, 0.0, 1.0, out=img)

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