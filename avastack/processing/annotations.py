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

import math

import cv2
import numpy as np
from typing import List, Tuple, Optional

from ..catalogues import ObjetCelebre


# ──────────────────────────────────────────────────────────────────────────
# Configuration visuelle par défaut
# ──────────────────────────────────────────────────────────────────────────
# PIÈGE DES CANAUX (constat Alain sur M31, 04/10/2026) : le buffer d'affichage
# est RGB (app.py : cv2.cvtColor GRAY2RGB, PNG compagnon écrit tel quel) —
# les couleurs sont donc définies en RGB, PAS à la mode OpenCV BGR. Le
# premier jet définissait le « jaune » en BGR : il s'affichait CYAN (et le
# « cyan » des étoiles s'affichait jaune).
JAUNE = (255, 255, 0)                     # RGB — demandé par Alain pour TOUT
COULEUR_DEFAUT_OBJET = JAUNE              # objets célèbres
COULEUR_DEFAUT_ETOILE = JAUNE             # étoiles brillantes
EPAISSEUR_TRAIT = 1
EPAISSEUR_CERCLE = 1
RAYON_CERCLE = 4                          # repli : taille angulaire inconnue
TAILLE_POLICE_BASE = 0.4
EPaisseUR_POLICE = 1
MARGE_BORD = 10  # pixels
# Entourage « selon la forme » (demande d'Alain, 04/10/2026) :
RAYON_ENTOURAGE_MIN_PX = 6.0   # sous ce rayon l'entourage est invisible
PLAFOND_DEMI_AXE = 0.5         # demi-axe ≤ 50 % de la plus grande dimension
                               # (M31 fait 190′ : sans plafond, l'entourage
                               # déborde de l'écran dès qu'on zoome)
RAYON_MESURE_MIN_PX = 12.0     # en dessous, la mesure de forme n'est pas fiable
PLAFOND_MESURE_PX = 300.0      # le crop de mesure est borné (coût maîtrisé)
# Finesse MAXIMALE du ratio d'axes pour un objet DÉBORDANT de l'entourage
# (taille réelle > plafond 50 %) : la mesure ne voit qu'une PARTIE de
# l'objet — le bulbe rond d'une galaxie fausse le ratio vers rond (constat
# Alain sur M31, 05/10/2026 : « l'ellipse devrait être plus fine »). Clamps
# par type, appliqués SEULEMENT aux objets plus grands que l'entourage.
TYPE_RATIO_MAX = {
    "galaxie": 0.45,
    "nebuleuse_diffuse": 0.55,
    "region_HII": 0.55,
    "nebuleuse_obscure": 0.70,
    "amas_ouvert": 0.85,
}

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


def _pixel_depuis_ciel(wcs, ra, dec):
    """(ra, dec) en degrés → (x, y) pixel du buffer, via le WCS du projet.

    Le WCS du projet (WcsTan / WcsCompose, cf. catalogues.solveur et
    catalogues.propagation) expose `vers_pixels(ra, dec)` → tableau (N, 2) en
    coordonnées tableau 0-based — il N'A PAS de méthode `world_to_pixel`
    (piège de branchement : le module d'origine l'appelait et ne dessinait
    donc JAMAIS rien, chaque étiquette tombant sur une exception)."""
    p = np.asarray(wcs.vers_pixels(float(ra), float(dec)),
                   dtype=np.float64).reshape(-1, 2)
    return float(p[0, 0]), float(p[0, 1])


class WcsEchelle:
    """WCS d'un buffer RÉDUIT : `vers_pixels` rendu à l'échelle du buffer.

    L'image affichée est souvent un APERÇU réduit (facteur `echelle` < 1) de
    la grille décrite par le WCS (pleine résolution). La réduction est
    uniforme (`cv2.resize`, fx = fy) : multiplier les coordonnées pixel par
    `echelle` suffit — aucune hypothèse sur la projection, aucun re-solve."""

    def __init__(self, wcs, echelle=1.0):
        self.wcs = wcs
        try:
            e = float(echelle)
        except (TypeError, ValueError):
            e = 1.0
        self.echelle = e if e > 0.0 else 1.0
        self.forme = getattr(wcs, "forme", None)

    def vers_pixels(self, ra, dec):
        """Ciel (deg) → pixels du buffer (array (N, 2), 0-based)."""
        p = np.asarray(self.wcs.vers_pixels(ra, dec),
                       dtype=np.float64).reshape(-1, 2)
        return p * self.echelle

    def vers_radec(self, xy):
        """Pixels du buffer (0-based) → (ra, dec) en degrés."""
        xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2) / self.echelle
        return self.wcs.vers_radec(xy)


def _position_etiquette(x: float, y: float, w_img: int, h_img: int,
                         taille_texte: Tuple[int, int], positions_prises: List[Tuple[int, int, int, int]],
                         decalage_x: int = 8, decalage_y: int = -8,
                         echelle_police: float = 1.0) -> Tuple[int, int]:
    """Trouve une position pour l'étiquette qui ne chevauche pas les bords ni
    les autres. Position préférée : à droite-au-dessus de l'objet ; en cas de
    collision, EMPILEMENT VERTICAL sous l'étiquette en collision (les objets
    réellement voisins — M31/M32/M110 — forment une pile lisible). Le zigzag
    horizontal du premier jet saturait au bout de 8 essais et laissait les
    textes se chevaucher (constat Alain sur M31, 04/10/2026).
    Retourne (x_texte, y_texte), origine du texte = BAS-GAUCHE (putText)."""
    tw, th = taille_texte
    marge = max(2, int(MARGE_BORD * max(1.0, echelle_police)))
    tx = int(x) + decalage_x
    ty = int(y) + decalage_y

    # Contraintes bords
    tx = max(marge, min(tx, w_img - tw - marge))
    ty = max(marge + th, min(ty, h_img - marge))

    rect = (tx, ty - th, tw, th)
    for _essai in range(24):
        collisions = [r for r in positions_prises
                      if _rects_chevauchent(rect, r)]
        if not collisions:
            break
        # Se placer SOUS la collision la plus basse (pile verticale) :
        # l'origine du texte est son BAS (putText) → il faut th + écart.
        ty = max(r[1] + r[3] for r in collisions) + th + 3
        if ty > h_img - marge:
            # En bas d'image : colonne suivante à droite, on repart en haut
            tx += tw + 8
            ty = int(y) + decalage_y
        tx = max(marge, min(tx, w_img - tw - marge))
        ty = max(marge + th, min(ty, h_img - marge))
        rect = (tx, ty - th, tw, th)

    return tx, ty


def _rects_chevauchent(r1: Tuple[int, int, int, int],
                        r2: Tuple[int, int, int, int]) -> bool:
    """Test de chevauchement de deux rectangles (x, y, w, h)."""
    return not (r1[0] + r1[2] <= r2[0] or r2[0] + r2[2] <= r1[0] or
                r1[1] + r1[3] <= r2[1] or r2[1] + r2[3] <= r1[1])


def _demi_axe_pixels(wcs, ra, dec, taille_arcmin) -> float:
    """Demi-grand axe EN PIXELS d'un objet de taille angulaire donnée : la
    distance est mesurée dans le buffer en projetant DEUX points séparés
    d'un demi-diamètre — robuste à l'échelle et à la rotation, y compris à
    travers `WcsEchelle` (aperçu réduit). 0.0 si la taille est inconnue ou
    le WCS muet (jamais d'exception)."""
    try:
        taille = float(taille_arcmin)
    except (TypeError, ValueError):
        return 0.0
    if not (taille > 0.0):
        return 0.0
    try:
        dec_c = max(-89.0, min(89.0, float(dec)))
        # taille_arcmin → deg : ×1/60 ; DEMI-diamètre : ÷2 ; le décalage AD
        # sous-tendu est d_ra·cos(dec) = demi-taille → d_ra = .../cos(dec).
        d_ra = (taille / 120.0) / math.cos(math.radians(dec_c))
        p = np.asarray(wcs.vers_pixels(
            np.array([float(ra), float(ra) + d_ra], dtype=np.float64),
            np.array([float(dec), float(dec)], dtype=np.float64)),
            dtype=np.float64).reshape(-1, 2)
        return float(math.hypot(*(p[1] - p[0])))
    except Exception:
        return 0.0


def _rayon_entourage(wcs, obj: ObjetCelebre, h: int, w: int,
                     echelle_police: float = 1.0) -> float:
    """Rayon/demi-grand axe de l'entourage (px) : taille angulaire du
    catalogue convertie par le WCS, bornée — plancher lisible, plafond
    50 % de la plus grande dimension (une cible géante ne doit pas remplir
    l'écran quand on zoome). Taille inconnue → petit cercle par défaut.
    `echelle_police` suit la TAILLE À L'ÉCRAN (v2.55.3) : à pleine
    résolution le plancher est agrandi de même, sinon il resterait
    invisible après réduction à l'écran."""
    e = max(1.0, float(echelle_police))
    r = _demi_axe_pixels(wcs, obj.ra_deg, obj.dec_deg, obj.size_arcmin)
    if r <= 0.0:
        return float(RAYON_CERCLE * e)
    plafond = PLAFOND_DEMI_AXE * max(h, w)
    return float(min(max(r, RAYON_ENTOURAGE_MIN_PX * e), plafond))


def _mesure_forme(img_disp: np.ndarray, x: float, y: float,
                  rayon: float) -> Optional[Tuple[float, float]]:
    """Forme RÉELLE de l'objet dans l'image affichée (demande d'Alain,
    option A validée) : moments d'inertie du crop centré sur l'objet →
    (angle_deg, ratio d'axes) de l'ellipse équivalente. None si la mesure
    n'est pas fiable — objet trop faible, trop petit, ou ROND (ratio ≥ 0,92)
    — auquel cas un CERCLE est dessiné.

    Le crop couvre l'ÉTENDUE de l'objet (réduit par INTER_AREA au-delà de
    PLAFOND_MESURE_PX) : mesurer un objet géant sur un petit crop ne voyait
    que son cœur rond — ellipse de M31 trop épaisse, constat Alain 05/10.
    Les poids sont CLIPPÉS au 99e percentile : une étoile brillante du champ
    ou un cœur saturé ne dominent plus les moments.

    L'orientation mesurée est celle de l'IMAGE (rotation de champ incluse) :
    le catalogue ne dispose pas d'angle de position, et l'option B
    (l'ajouter au format .dat + régénérer Zenodo) a été écartée."""
    h, w = img_disp.shape[:2]
    demi = int(round(min(float(rayon), 0.5 * max(h, w))))
    if demi < 8:
        return None
    x0, y0 = max(0, int(x) - demi), max(0, int(y) - demi)
    x1, y1 = min(w, int(x) + demi + 1), min(h, int(y) + demi + 1)
    if (x1 - x0) < 16 or (y1 - y0) < 16:
        return None                      # crop vraiment trop petit
    crop = img_disp[y0:y1, x0:x1]
    if crop.ndim == 3:
        g = crop.astype(np.float32).mean(axis=2)
    else:
        g = crop.astype(np.float32)
    f = max(1.0, demi / PLAFOND_MESURE_PX)   # réduction si rayon > plafond
    if f > 1.0:
        nh = max(8, int(round(g.shape[0] / f)))
        nw = max(8, int(round(g.shape[1] / f)))
        g = cv2.resize(g, (nw, nh), interpolation=cv2.INTER_AREA)
    # Fond : 25e percentile du crop (robuste même si l'objet remplit le crop).
    fond = float(np.percentile(g, 25.0))
    poids = np.clip(g - fond, 0.0, None)
    plafond_poids = float(np.percentile(poids, 99.0))
    if plafond_poids > 0.0:
        poids = np.minimum(poids, plafond_poids)
    if int((poids > max(1.0, 0.02 * plafond_poids)).sum()) < 30:
        return None                      # trop peu de signal mesurable
    total = float(poids.sum())
    if total <= 0.0:
        return None
    ys, xs = np.mgrid[0:g.shape[0], 0:g.shape[1]].astype(np.float32)
    dx = xs - float((poids * xs).sum() / total)
    dy = ys - float((poids * ys).sum() / total)
    mu20 = float((poids * dx * dx).sum() / total)
    mu02 = float((poids * dy * dy).sum() / total)
    mu11 = float((poids * dx * dy).sum() / total)
    dis = math.hypot(mu20 - mu02, 2.0 * mu11)
    lam_max = 0.5 * (mu20 + mu02 + dis)
    lam_min = 0.5 * (mu20 + mu02 - dis)
    if lam_max <= 0.0 or lam_min < 0.0:
        return None
    ratio = math.sqrt(lam_min / lam_max)
    if not (0.30 <= ratio <= 0.92):
        return None                      # rond ou dégénéré → cercle
    angle = 0.5 * math.degrees(math.atan2(2.0 * mu11, mu20 - mu02))
    return angle, ratio


def _dessine_entourage(img_disp: np.ndarray, x: float, y: float,
                       rayon: float, forme, couleur: Tuple[int, int, int],
                       echelle_police: float = 1.0):
    """Entourage d'un objet : ELLIPSE orientée si la forme mesurée est
    allongée (angle + ratio RÉELS mesurés sur l'image), CERCLE sinon
    (objet rond, mesure non fiable, ou taille angulaire inconnue)."""
    e = max(1.0, float(echelle_police))
    ep = max(1, int(round(EPAISSEUR_CERCLE * e)))
    if forme is None:
        cv2.circle(img_disp, (int(x), int(y)), max(2, int(round(rayon))),
                   couleur, ep, cv2.LINE_AA)
        return
    angle, ratio = forme
    a = max(2.0, float(rayon))
    b = max(2.0, a * float(ratio))
    cv2.ellipse(img_disp, (int(round(x)), int(round(y))),
                (int(round(a)), int(round(b))), float(angle),
                0.0, 360.0, couleur, ep, cv2.LINE_AA)


def overlay_objets_celebres(img_disp: np.ndarray, wcs, objets: List[ObjetCelebre],
                            couleur: Tuple[int, int, int] = COULEUR_DEFAUT_OBJET,
                            echelle_police: float = 1.0) -> List[Tuple[int, int, int, int]]:
    """Dessine les objets célèbres sur l'image d'affichage : entourage CERCLE
    ou ELLIPSE selon la forme réelle (mesurée dans l'image — cf.
    `_mesure_forme`), dimensionné par la taille angulaire du catalogue, puis
    étiquette. La liste `objets` doit être DÉDUPLIQUÉE en amont
    (`catalogues.celebres.deduplique_celebres`) : une étiquette par objet.
    `echelle_police` (v2.55.3) met textes/traits/étiquettes à l'échelle pour
    garder une TAILLE À L'ÉCRAN constante sur un buffer pleine résolution.
    Retourne la liste des rectangles occupés par les étiquettes."""
    if img_disp is None or img_disp.size == 0 or not objets:
        return []

    h, w = img_disp.shape[:2]
    e = max(1.0, float(echelle_police))
    taille_police = TAILLE_POLICE_BASE * e
    ep_trait = max(1, int(round(EPAISSEUR_TRAIT * e)))
    pad = max(1, int(round(2 * e)))
    positions_prises = []
    attends = []        # (x, y, texte, tx, ty, tw, th, rayon, forme) — 2e passe

    for obj in objets:
        try:
            x, y = _pixel_depuis_ciel(wcs, obj.ra_deg, obj.dec_deg)
        except Exception:
            continue

        # Hors champ affiché ?
        if x < -50 * e or x > w + 50 * e or y < -50 * e or y > h + 50 * e:
            continue

        # Texte à afficher : designation + icône type
        icone = TYPE_ICON.get(obj.type_obj, "?")
        texte = f"{obj.designation} ({icone})"
        texte = _sanitize_texte(texte)

        # Taille du texte
        (tw, th), _ = cv2.getTextSize(texte, cv2.FONT_HERSHEY_SIMPLEX,
                                      taille_police, EPaisseUR_POLICE)

        # Position étiquette (décrochage proportionnel à l'échelle)
        tx, ty = _position_etiquette(x, y, w, h, (tw, th), positions_prises,
                                     decalage_x=max(1, int(round(8 * e))),
                                     decalage_y=-max(1, int(round(8 * e))),
                                     echelle_police=e)

        # Entourage : taille réelle (via le WCS) + forme mesurée AVANT tout
        # dessin — le crop de mesure doit voir l'image PROPRE, pas annotée.
        taille_px = _demi_axe_pixels(wcs, obj.ra_deg, obj.dec_deg,
                                     obj.size_arcmin)
        rayon = _rayon_entourage(wcs, obj, h, w, echelle_police=e)
        forme = (_mesure_forme(img_disp, x, y, rayon)
                 if rayon >= RAYON_MESURE_MIN_PX else None)
        if forme is not None and taille_px > rayon + 0.5:
            # Objet plus grand que l'entourage (plafond 50 % appliqué) : la
            # mesure ne voit qu'une partie de l'objet, le ratio est biaisé
            # rond → prior de finesse par type (constat Alain sur M31).
            ratio_max = TYPE_RATIO_MAX.get(obj.type_obj)
            if ratio_max is not None and forme[1] > ratio_max:
                forme = (forme[0], ratio_max)

        # DEUX PASSES (jalon 96, mesure du banc : 53,8 ms pour 10 étiquettes
        # à l'aperçu 1600×904) : le fond semi-transparent de TOUTES les
        # étiquettes est posé en UNE seule copie + addWeighted (la copie du
        # buffer ≈ 4,3 Mo payée par étiquette dominait tout le reste), puis
        # traits/textes/entourages. L'ordre reste respecté : le fond est sous
        # le texte.
        attends.append((x, y, texte, tx, ty, tw, th, rayon, forme))
        positions_prises.append((tx, ty - th, tw, th))

    if attends:
        overlay = img_disp.copy()
        for _x, _y, _texte, tx, ty, tw, th, _rayon, _forme in attends:
            cv2.rectangle(overlay, (tx - pad, ty - th - pad),
                          (tx + tw + pad, ty + pad), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.3, img_disp, 0.7, 0, img_disp)
        del overlay
        for x, y, texte, tx, ty, tw, th, rayon, forme in attends:
            cv2.line(img_disp, (int(x), int(y)), (tx, ty - th // 2),
                     couleur, ep_trait, cv2.LINE_AA)
            cv2.putText(img_disp, texte, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                        taille_police, couleur, EPaisseUR_POLICE,
                        cv2.LINE_AA)
            _dessine_entourage(img_disp, x, y, rayon, forme, couleur,
                               echelle_police=e)

    return positions_prises
def overlay_etoiles_brillantes(img_disp: np.ndarray, wcs, etoiles: dict,
                               mag_limite: float = 8.0,
                               couleur: Tuple[int, int, int] = COULEUR_DEFAUT_ETOILE,
                               positions_prises: List[Tuple[int, int, int, int]] = None,
                               echelle_police: float = 1.0) -> List[Tuple[int, int, int, int]]:
    """Dessine les noms des étoiles brillantes (Gaia) sur l'image d'affichage.
    `etoiles` : dict retourné par CatalogueSiril.extraire() avec clés 'ra', 'dec', 'g'.
    `echelle_police` : cf. `overlay_objets_celebres` (taille à l'écran constante).
    Retourne la liste mise à jour des rectangles occupés."""
    if img_disp is None or img_disp.size == 0 or etoiles is None:
        return positions_prises or []

    if positions_prises is None:
        positions_prises = []

    h, w = img_disp.shape[:2]
    e = max(1.0, float(echelle_police))
    taille_police = TAILLE_POLICE_BASE * 0.8 * e
    ep = max(1, int(round(EPAISSEUR_TRAIT * e)))
    pad = max(1, int(round(2 * e)))
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
            x, y = _pixel_depuis_ciel(wcs, float(ra_f[i]), float(dec_f[i]))
        except Exception:
            continue

        if x < -20 or x > w + 20 or y < -20 or y > h + 20:
            continue

        # Texte : magnitude (« ★ » n'existe pas dans la police Hershey
        # d'OpenCV : il sortait en « ? » après _sanitize_texte) — virgule
        # décimale française, comme le reste de l'interface.
        texte = f"mag {g_f[i]:.1f}".replace(".", ",")
        texte = _sanitize_texte(texte)

        (tw, th), _ = cv2.getTextSize(texte, cv2.FONT_HERSHEY_SIMPLEX,
                                      taille_police, EPaisseUR_POLICE)

        tx, ty = _position_etiquette(x, y, w, h, (tw, th), positions_prises,
                                     decalage_x=max(1, int(round(6 * e))),
                                     decalage_y=-max(1, int(round(6 * e))),
                                     echelle_police=e)

        cv2.line(img_disp, (int(x), int(y)), (tx, ty - th // 2), couleur,
                 ep, cv2.LINE_AA)

        overlay = img_disp.copy()
        cv2.rectangle(overlay, (tx - pad, ty - th - pad),
                      (tx + tw + pad, ty + pad), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.3, img_disp, 0.7, 0, img_disp)

        cv2.putText(img_disp, texte, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX,
                    taille_police, couleur, EPaisseUR_POLICE, cv2.LINE_AA)

        cv2.circle(img_disp, (int(x), int(y)), max(1, int(round(3 * e))),
                   couleur, ep, cv2.LINE_AA)

        positions_prises.append((tx, ty - th, tw, th))

    return positions_prises


def generer_image_annotee(img_disp: np.ndarray, wcs, objets: List[ObjetCelebre],
                          etoiles: dict, mag_limite: float = 8.0,
                          annoter_objets: bool = True, annoter_etoiles: bool = True,
                          echelle_police: float = 1.0) -> np.ndarray:
    """Crée une COPIE de l'image d'affichage avec les annotations (pour
    sauvegarde PNG). `echelle_police` : cf. `overlay_objets_celebres`.
    Ne modifie PAS l'original."""
    if img_disp is None:
        return None
    img_ann = img_disp.copy()
    positions = []
    if annoter_objets and objets:
        positions = overlay_objets_celebres(img_ann, wcs, objets,
                                            echelle_police=echelle_police)
    if annoter_etoiles and etoiles is not None:
        positions = overlay_etoiles_brillantes(img_ann, wcs, etoiles,
                                               mag_limite,
                                               positions_prises=positions,
                                               echelle_police=echelle_police)
    return img_ann