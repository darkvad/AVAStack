# -*- coding: utf-8 -*-
"""Annotations d'objets célestes sur l'image affichée (overlay OpenCV).

Ce module fournit l'affichage temps-réel des noms d'objets célèbres et d'étoiles
brillantes sur le buffer d'affichage, SANS modifier les données brutes ni les FITS
sauvegardés (linéarité photométrique préservée).

Deux fonctions principales :
  - overlay_objets_celebres(img_disp, wcs, objets, config_couleurs)
  - overlay_etoiles_brillantes(img_disp, wcs, catalogue_gaia, mag_limite, config_couleurs)

Appelé depuis `ui/app.py` dans la boucle d'affichage (_refresh_image) quand les
cases correspondantes sont cochées.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional

from ..catalogues import ObjetCelebre


# ──────────────────────────────────────────────────────────────────────────
# Configuration visuelle par défaut
# ──────────────────────────────────────────────────────────────────────────
COULEUR_DEFAUT_OBJET = (0, 255, 255)      # jaune (BGR)
COULEUR_DEFAUT_ETOILE = (255, 255, 0)     # cyan (BGR)
COULEUR_DEFAUT_TRAIT = (255, 255, 255)    # blanc
EPAISSEUR_TRAIT = 1
EPAISSEUR_CERCLE = 1
RAYON_CERCLE = 4
TAILLE_POLICE_BASE = 0.4
EPaisseUR_POLICE = 1
MARGE_BORD = 10  # pixels

# Codes de type objet → icône 1 lettre
TYPE_ICON = {
    "galaxie": "Gx",
    "nebuleuse_diffuse": "Nb",
    "nebuleuse_planetaire": "Pn",
    "amas_ouvert": "Oc",
    "amas_globulaire": "Gc",
    "nebuleuse_obscure": "Dk",
    "region_HII": "H2",
}
def _sanitize_texte(txt: str) -> str:
    """Nettoie le texte pour l'affichage OpenCV (ASCII seul)."""
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in txt)


def _position_etiquette(x: float, y: float, w_img: int, h_img: int,
                         taille_texte: Tuple[int, int], positions_prises: List[Tuple[int, int, int, int]],
                         decalage_x: int = 8, decalage_y: int = -8) -> Tuple[int, int]:
    """Trouve une position pour l'étiquette qui ne chevauche pas les bords ni les autres.
    Retourne (x_texte, y_texte) en coordonnées pixel (origine haut-gauche)."""
    tw, th = taille_texte
    # Position préférée : à droite-au-dessus de l'objet
    tx = int(x) + decalage_x
    ty = int(y) + decalage_y

    # Contraintes bords
    if tx < MARGE_BORD:
        tx = MARGE_BORD
    if tx + tw > w_img - MARGE_BORD:
        tx = w_img - tw - MARGE_BORD
    if ty < MARGE_BORD + th:
        ty = MARGE_BORD + th
    if ty > h_img - MARGE_BORD:
        ty = h_img - MARGE_BORD

    # Éviter chevauchement avec étiquettes déjà placées
    rect = (tx, ty - th, tw, th)
    essais = 0
    while any(_rects_chevauchent(rect, r) for r in positions_prises) and essais < 8:
        # Décale en quinconce
        tx += 12 if essais % 2 == 0 else -12
        ty += 8 if essais % 2 == 0 else -8
        # Re-contraintes bords
        tx = max(MARGE_BORD, min(tx, w_img - tw - MARGE_BORD))
        ty = max(MARGE_BORD + th, min(ty, h_img - MARGE_BORD))
        rect = (tx, ty - th, tw, th)
        essais += 1

    return tx, ty


def _rects_chevauchent(r1: Tuple[int, int, int, int],
                        r2: Tuple[int, int, int, int]) -> bool:
    """Test de chevauchement de deux rectangles (x, y, w, h)."""
    return not (r1[0] + r1[2] <= r2[0] or r2[0] + r2[2] <= r1[0] or
                r1[1] + r1[3] <= r2[1] or r2[1] + r2[3] <= r1[1])


def overlay_objets_celebres(img_disp: np.ndarray, wcs, objets: List[ObjetCelebre],
                            couleur: Tuple[int, int, int] = COULEUR_DEFAUT_OBJET) -> List[Tuple[int, int, int, int]]:
    """Dessine les noms des objets célèbres sur l'image d'affichage.
    Retourne la liste des rectangles occupés par les étiquettes (pour éviter chevauchements)."""
    if img_disp is None or img_disp.size == 0 or not objets:
        return []

    h, w = img_disp.shape[:2]
    positions_prises = []

    for obj in objets:
        try:
            # Conversion monde → pixel via WCS
            x, y = wcs.world_to_pixel(obj.ra_deg, obj.dec_deg)
        except Exception:
            continue

        # Hors champ affiché ?
        if x < -50 or x > w + 50 or y < -50 or y > h + 50:
            continue

        # Texte à afficher : designation + icône type
        icone = TYPE_ICON.get(obj.type_obj, "?")
        texte = f"{obj.designation} ({icone})"
        texte = _sanitize_texte(texte)

        # Taille du texte
        (tw, th), _ = cv2.getTextSize(texte, cv2.FONT_HERSHEY_SIMPLEX, TAILLE_POLICE_BASE, EPaisseUR_POLICE)

        # Position étiquette
        tx, ty = _position_etiquette(x, y, w, h, (tw, th), positions_prises)

        # Trait de liaison objet → étiquette
        cv2.line(img_disp, (int(x), int(y)), (tx, ty - th // 2), COULEUR_DEFAUT_TRAIT, EPAISSEUR_TRAIT, cv2.LINE_AA)

        # Fond semi-transparent pour lisibilité (optionnel, léger)
        overlay = img_disp.copy()
        cv2.rectangle(overlay, (tx - 2, ty - th - 2), (tx + tw + 2, ty + 2), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.3, img_disp, 0.7, 0, img_disp)

        # Texte
        cv2.putText(img_disp, texte, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                    TAILLE_POLICE_BASE, couleur, EPaisseUR_POLICE, cv2.LINE_AA)

        # Cercle sur l'objet
        cv2.circle(img_disp, (int(x), int(y)), RAYON_CERCLE, couleur, EPAISSEUR_CERCLE, cv2.LINE_AA)

        positions_prises.append((tx, ty - th, tw, th))

    return positions_prises
def overlay_etoiles_brillantes(img_disp: np.ndarray, wcs, etoiles: dict,
                               mag_limite: float = 8.0,
                               couleur: Tuple[int, int, int] = COULEUR_DEFAUT_ETOILE,
                               positions_prises: List[Tuple[int, int, int, int]] = None) -> List[Tuple[int, int, int, int]]:
    """Dessine les noms des étoiles brillantes (Gaia) sur l'image d'affichage.
    `etoiles` : dict retourné par CatalogueSiril.extraire() avec clés 'ra', 'dec', 'g'.
    Retourne la liste mise à jour des rectangles occupés."""
    if img_disp is None or img_disp.size == 0 or etoiles is None:
        return positions_prises or []

    if positions_prises is None:
        positions_prises = []

    h, w = img_disp.shape[:2]
    ra_arr = etoiles.get("ra")
    dec_arr = etoiles.get("dec")
    g_arr = etoiles.get("g")

    if ra_arr is None or dec_arr is None or g_arr is None:
        return positions_prises

    # Filtre magnitude
    mask = g_arr <= mag_limite
    if not np.any(mask):
        return positions_prises

    ra_f = ra_arr[mask]
    dec_f = dec_arr[mask]
    g_f = g_arr[mask]

    # Tri par magnitude (plus brillantes d'abord)
    idx = np.argsort(g_f)
    ra_f = ra_f[idx]
    dec_f = dec_f[idx]
    g_f = g_f[idx]

    # Limite du nombre d'étiquettes pour lisibilité (max 50)
    max_labels = 50
    for i in range(min(len(ra_f), max_labels)):
        try:
            x, y = wcs.world_to_pixel(float(ra_f[i]), float(dec_f[i]))
        except Exception:
            continue

        if x < -20 or x > w + 20 or y < -20 or y > h + 20:
            continue

        # Texte : magnitude (et nom Hipparcos/HD si dispo — pas dans extraire actuellement)
        texte = f"★ {g_f[i]:.1f}"
        texte = _sanitize_texte(texte)

        (tw, th), _ = cv2.getTextSize(texte, cv2.FONT_HERSHEY_SIMPLEX, TAILLE_POLICE_BASE * 0.8, EPaisseUR_POLICE)

        tx, ty = _position_etiquette(x, y, w, h, (tw, th), positions_prises, decalage_x=6, decalage_y=-6)

        cv2.line(img_disp, (int(x), int(y)), (tx, ty - th // 2), COULEUR_DEFAUT_TRAIT, EPAISSEUR_TRAIT, cv2.LINE_AA)

        overlay = img_disp.copy()
        cv2.rectangle(overlay, (tx - 2, ty - th - 2), (tx + tw + 2, ty + 2), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.3, img_disp, 0.7, 0, img_disp)

        cv2.putText(img_disp, texte, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                    TAILLE_POLICE_BASE * 0.8, couleur, EPaisseUR_POLICE, cv2.LINE_AA)

        cv2.circle(img_disp, (int(x), int(y)), 3, couleur, 1, cv2.LINE_AA)

        positions_prises.append((tx, ty - th, tw, th))

    return positions_prises


def generer_image_annotee(img_disp: np.ndarray, wcs, objets: List[ObjetCelebre],
                          etoiles: dict, mag_limite: float = 8.0,
                          annoter_objets: bool = True, annoter_etoiles: bool = True) -> np.ndarray:
    """Crée une COPIE de l'image d'affichage avec les annotations (pour sauvegarde PNG).
    Ne modifie PAS l'original."""
    if img_disp is None:
        return None
    img_ann = img_disp.copy()
    positions = []
    if annoter_objets and objets:
        positions = overlay_objets_celebres(img_ann, wcs, objets)
    if annoter_etoiles and etoiles is not None:
        positions = overlay_etoiles_brillantes(img_ann, wcs, etoiles, mag_limite, positions_prises=positions)
    return img_ann