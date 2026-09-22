# -*- coding: utf-8 -*-
"""Solveur astrométrique INTERNE (jalon 56, étape 2) — WCS TAN en numpy pur.

Objectif (accord d'Alain, 22/09/2026) : résoudre l'astrométrie d'un
empilement SANS outil externe, à partir des INDICES connus (centre + taille
du champ fournis par la cible/monture), le catalogue Gaia DR3 astrométrique
de Siril servant de vérité terrain. ASTAP (cf. `astap.py`) reste la
RÉFÉRENCE INDÉPENDANTE et le repli.

Méthode, esprit astrometry.net / Siril :
  1. détection des étoiles de l'image (même mécanique que
     `processing/stars.py` : luminance → fond/bruit médiane-MAD → seuil 8σ →
     composantes 8-connexes → centroïdes pondérés, tri par éclat) ;
  2. extraction du catalogue dans le cône couvert par le champ, projection
     TAN (gnomonique) autour du centre INDICué ;
  3. appariement GLOBAL par TRIANGLES CANONIQUES (jalon 15, même
     canonisation que `processing/alignment.py` : invariants = rapports de
     côtés, aveugles à la translation, rotation, échelle ET parité — le
     bon appariement survit, les miroirs sont rejetés au score) ; la
     meilleure paire de triangles donne une affinité exacte 3 points
     (plan tangent → pixels) ;
  4. correspondances MUTUELLES à ±2 px (règle « ancre fiable », jalon 13),
     puis ajustement TAN complet par Gauss-Newton (8 paramètres : CRVAL,
     CRPIX, matrice CD) avec réjection 3σ itérative.

Convention de retour du projet : (résultat, "") en succès, (None, message
explicite) sinon — JAMAIS d'exception propagée, jamais de panne silencieuse.

Détection recopiée (adaptée) plutôt qu'importée de `processing.stars` :
la FONDATION catalogues ne doit pas dépendre du package processing, qui
importera catalogues à partir de l'étape 3 (propagation WCS) — un import
croisé ferait un cycle.
"""

import itertools
import math

import numpy as np
import cv2

from .siril_cat import CatalogueSiril

# --- Garde-fous généraux ----------------------------------------------------
CHAMP_DEG_MIN, CHAMP_DEG_MAX = 0.05, 5.0     # champ indicé plausible (deg)
ECHELLE_ARCSEC_MIN, ECHELLE_ARCSEC_MAX = 0.05, 30.0
# L'échelle résolue doit rester proche de l'indice (le champ indicé divise
# la largeur en pixels) : un appariement faux dévie nettement plus.
ECHELLE_TOL_RELATIVE = 0.5
RMS_PX_MAX = 2.0                             # résidu moyen admissible

# --- Détection --------------------------------------------------------------
SEUIL_SIGMA = 8.0
MAX_ETOILES_DETECTION = 120
AIRE_MIN, AIRE_MAX = 2, 400                  # pixels au-dessus du seuil

# --- Appariement par triangles (mêmes constantes que le jalon 15) -----------
TRI_N_MAX = 12          # triangles construits sur les N plus brillantes
TRI_N_MAX_CAT = 20      # côté catalogue : plus de triangles, car les deux
                        # listes ne coïncident pas aussi bien que dans le
                        # jalon 15 (image↔image) — les plus brillantes du
                        # catalogue ne sont pas forcément toutes détectées
                        # (limmag, saturation, hors champ indicé)
TRI_TOL = 0.02          # tolérance sur les rapports de côtés
TRI_PAIRS_MAX = 3000    # plafond de paires candidates évaluées
TRI_INLIERS_MIN = 6     # correspondances mutuelles requises
TRI_RAYON = 3.0         # rayon de score d'une étoile après affinité (px)
MUTUEL_RAYON = 2.0      # rayon des correspondances mutuelles finales (px)

N_CAT_MAX = 400         # étoiles de catalogue gardées (les plus brillantes)
MARGE_INDICES = 0.5     # marge fixe du rayon d'extraction (deg) — couvre
                        # l'erreur d'indication de la monture/cible
CLIP_MARGE = 1.6        # rectangle indicatif × marge : le catalogue est
                        # CLIPPÉ à la zone plausible de l'image AVANT la
                        # sélection des plus brillantes (sinon le top-N du
                        # cône d'extraction n'est pas le top-N de l'image
                        # et les triangles corrects n'existent plus —
                        # constat du banc étape 2, échec « mutuelles (3) »)

# ============================================================ projection TAN
def projection_tan(ra, dec, ra0, dec0):
    """Ciel → plan tangent (ξ, η) en DEGRÉS (gnomonique de point tangent
    (ra0, dec0)) : ξ vers l'est, η vers le nord. Vectorisé, numpy pur.
    Validé contre astropy.wcs (banc jalon 56 étape 2, règle « toute
    implémentation est confrontée à une référence indépendante »)."""
    r = np.radians(np.asarray(ra, dtype=np.float64))
    d = np.radians(np.asarray(dec, dtype=np.float64))
    r0 = np.radians(float(ra0))
    d0 = np.radians(float(dec0))
    cosc = (np.sin(d0) * np.sin(d)
            + np.cos(d0) * np.cos(d) * np.cos(r - r0))
    cosc = np.where(np.abs(cosc) < 1e-12, np.nan, cosc)
    xi = np.cos(d) * np.sin(r - r0) / cosc
    eta = (np.cos(d0) * np.sin(d) - np.sin(d0) * np.cos(d)
           * np.cos(r - r0)) / cosc
    return np.degrees(xi), np.degrees(eta)


def projection_tan_inverse(xi, eta, ra0, dec0):
    """Plan tangent (ξ, η) en DEGRÉS → ciel (ra normalisé [0, 360), dec).
    Inverse exact de `projection_tan` (formules gnomoniques standard)."""
    x = np.radians(np.asarray(xi, dtype=np.float64))
    y = np.radians(np.asarray(eta, dtype=np.float64))
    r0 = np.radians(float(ra0))
    d0 = np.radians(float(dec0))
    g = np.sqrt(1.0 + x * x + y * y)
    dec = np.arcsin((np.sin(d0) + y * np.cos(d0)) / g)
    dra = np.arctan2(x, np.cos(d0) - y * np.sin(d0))
    return np.degrees(r0 + dra) % 360.0, np.degrees(dec)


class WcsTan:
    """WCS TAN minimal : point tangent `crval` (deg), pixel de référence
    `crpix` (convention TABLEAU, indices 0-based — les mots-clés FITS sont
    en convention 1-based, d'où le ±1 dans les conversions ci-dessous),
    matrice `cd` (2×2, deg/px, convention FITS CD).

    PIÈGE 0/1-based (vérifié contre astropy, banc étape 2) : le CRPIX1 d'un
    en-tête FITS vaut crpix_tableau + 1. Sans ce décalage, toute la solution
    glisse d'un pixel (~1 à 3")."""

    def __init__(self, crval, crpix, cd, forme=None):
        self.crval = np.asarray(crval, dtype=np.float64).reshape(2)
        self.crpix = np.asarray(crpix, dtype=np.float64).reshape(2)
        self.cd = np.asarray(cd, dtype=np.float64).reshape(2, 2)
        self.forme = None if forme is None else tuple(int(v) for v in forme)

    # -- conversions ---------------------------------------------------------
    def vers_radec(self, xy):
        """Pixels (tableau, 0-based) → (ra, dec) en degrés (arrays)."""
        d = np.asarray(xy, dtype=np.float64).reshape(-1, 2) - self.crpix
        xi = self.cd[0, 0] * d[:, 0] + self.cd[0, 1] * d[:, 1]
        eta = self.cd[1, 0] * d[:, 0] + self.cd[1, 1] * d[:, 1]
        return projection_tan_inverse(xi, eta, self.crval[0], self.crval[1])

    def vers_pixels(self, ra, dec):
        """Ciel (deg) → pixels (tableau, 0-based), array (N, 2)."""
        xi, eta = projection_tan(ra, dec, self.crval[0], self.crval[1])
        a, b, c, dd = (self.cd[0, 0], self.cd[0, 1],
                       self.cd[1, 0], self.cd[1, 1])
        det = a * dd - b * c
        if abs(det) < 1e-18:
            raise ValueError("matrice CD singulière")
        u = (dd * xi - b * eta) / det
        v = (-c * xi + a * eta) / det
        return np.column_stack([u, v]) + self.crpix

    # -- mots-clés FITS ------------------------------------------------------
    def mots_cles_fits(self):
        """→ dict de mots-clés FITS (CRPIX en convention 1-based, cf. piège
        ci-dessus) — utilisable tel quel dans un en-tête astropy."""
        return {
            "CTYPE1": "RA---TAN", "CTYPE2": "DEC--TAN",
            "CUNIT1": "deg", "CUNIT2": "deg",
            "CRPIX1": float(self.crpix[0]) + 1.0,
            "CRPIX2": float(self.crpix[1]) + 1.0,
            "CRVAL1": float(self.crval[0] % 360.0),
            "CRVAL2": float(self.crval[1]),
            "CD1_1": float(self.cd[0, 0]), "CD1_2": float(self.cd[0, 1]),
            "CD2_1": float(self.cd[1, 0]), "CD2_2": float(self.cd[1, 1]),
            "RADESYS": "ICRS",
        }

    @classmethod
    def depuis_mots_cles(cls, entete, forme=None):
        """Construit depuis un mapping de mots-clés FITS (dict ou
        astropy.io.fits.Header). Exige la matrice CD (ASTAP l'écrit
        toujours, vérifié le 22/09/2026)."""
        def _val(nom):
            v = entete[nom]
            return float(v.value) if hasattr(v, "value") else float(v)
        try:
            crval = (_val("CRVAL1") % 360.0, _val("CRVAL2"))
            crpix = (_val("CRPIX1") - 1.0, _val("CRPIX2") - 1.0)  # 0-based
            cd = [[_val("CD1_1"), _val("CD1_2")],
                  [_val("CD2_1"), _val("CD2_2")]]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"mots-clés WCS TAN incomplets : {exc}") from exc
        return cls(crval, crpix, cd, forme=forme)

    # -- grandeurs dérivées --------------------------------------------------
    @property
    def echelle_arcsec(self):
        """Échelle moyenne (″/px) — norme géométrique de la matrice CD."""
        return float(3600.0 * math.sqrt(abs(np.linalg.det(self.cd))))

    @property
    def angle_deg(self):
        """Orientation (deg) de l'axe X pixel projeté, par rapport au sens
        des RA croissants (peut différer de CROTA2 selon la parité)."""
        return float(math.degrees(math.atan2(self.cd[1, 0], self.cd[0, 0])))

    def __repr__(self):
        return (f"WcsTan(crval=({self.crval[0]:.6f}, {self.crval[1]:.6f}), "
                f"crpix=({self.crpix[0]:.2f}, {self.crpix[1]:.2f}), "
                f"échelle={self.echelle_arcsec:.3f}\"/px)")

# ============================================================== détection
def _canonise_img(img):
    """Canal de détection : l'image telle quelle en mono, canal VERT pour
    une couleur (esprit Siril — même convention que
    processing/alignment.canal_alignement). → (H, W) float32."""
    a = np.asarray(img)
    if a.ndim == 2:
        return a.astype(np.float32, copy=False)
    if a.ndim == 3:
        if a.shape[0] <= 4 and a.shape[-1] > 4:   # canaux-en-tête
            a = np.transpose(a, (1, 2, 0))
        return np.ascontiguousarray(a[..., 1], dtype=np.float32)
    raise ValueError(f"image de rang inattendu : {a.shape}")


def _detecter(img, max_etoiles=MAX_ETOILES_DETECTION):
    """Positions des étoiles les plus brillantes — même mécanique que
    `processing/stars.detecter_positions` (jalon 10/13), recopiée ici pour
    éviter le cycle d'import processing↔catalogues (cf. docstring module).
    → (positions (N, 2) float64 (x, y) triées par éclat DÉCROISSANT,
    message) — convention (résultat, message) du projet."""
    try:
        luma = _canonise_img(img)
        h, w = luma.shape
        if min(h, w) < 8:
            return np.zeros((0, 2)), f"image trop petite ({w}×{h} px)"
        fond = float(np.median(luma))
        bruit = 1.4826 * float(np.median(np.abs(luma - fond)))
        if bruit <= 1e-9:
            return np.zeros((0, 2)), "image constante"
        masque = (luma > fond + SEUIL_SIGMA * bruit).astype(np.uint8)
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
            if s <= 0.0:
                pos.append((x + bw / 2.0, y + bh / 2.0))
                continue
            ys, xs = np.mgrid[y:y + bh, x:x + bw]
            pos.append((float((xs * sub).sum() / s),
                        float((ys * sub).sum() / s)))
        return np.array(pos, np.float64).reshape(-1, 2), ""
    except Exception as exc:                 # mémoire, image dégénérée…
        return np.zeros((0, 2)), str(exc)

# =================================================== triangles (jalon 15)
def _invariants_triangles(pts, n_max=TRI_N_MAX):
    """Triangles CANONIQUES des `n_max` plus brillantes de `pts` ((N, 2),
    trié par éclat décroissant) — MÊME canonisation que
    processing/alignment.py (jalon 15) : le plus grand côté relie deux
    sommets de base (ordonnés par distance à l'apex), invariants =
    d(apex→base proche)/grand côté et d(apex→base loin)/grand côté.
    → (inv (T, 2) float32, sommets (T, 3) int, longueurs (T,)) ou
    (None, None, None) si moins de 3 points."""
    n = min(int(n_max), len(pts))
    if n < 3:
        return None, None, None
    idx = np.array(list(itertools.combinations(range(n), 3)), np.int64)
    p = pts[idx].astype(np.float64)                # (T, 3, 2)
    d = p[:, :, None, :] - p[:, None, :, :]
    L = np.sqrt((d * d).sum(-1))                   # (T, 3, 3)
    iu = np.triu_indices(3, 1)
    c = L[:, iu[0], iu[1]]                         # (T, 3) côtés
    i_lon = c.argmax(1)                            # le plus grand côté
    base = np.array(iu, np.int64).T[i_lon]         # (T, 2) POSITIONS
    apex = 3 - base.sum(1)                         # la position restante
    t = np.arange(len(idx))
    d0 = L[t, apex, base[:, 0]]
    d1 = L[t, apex, base[:, 1]]
    proche = d0 <= d1
    b_proche = np.where(proche, base[:, 0], base[:, 1])
    b_loin = np.where(proche, base[:, 1], base[:, 0])
    grand = np.maximum(L[t, b_proche, b_loin], 1e-6)
    roles = np.stack([apex, b_proche, b_loin], 1)  # (T, 3) POSITIONS
    # → indices GLOBAUX (piège jalon 15 : positions 0..2 ≠ indices globaux)
    sommets = np.take_along_axis(idx, roles, 1).astype(np.int64)
    inv = np.stack([L[t, apex, b_proche] / grand,
                    L[t, apex, b_loin] / grand], 1).astype(np.float32)
    return inv, sommets, grand


def _appariements_mutuels(a, b, rayon):
    """Appariements MUTUELS (plus proche voisin des deux côtés, règle
    « ancre fiable » du jalon 13) entre deux nuages (N, 2) et (M, 2).
    → (ia, ib, dist) des paires retenues (ia/ib : indices dans a/b)."""
    if len(a) == 0 or len(b) == 0:
        return (np.zeros(0, np.int64), np.zeros(0, np.int64),
                np.zeros(0))
    d = np.hypot(a[:, None, 0] - b[None, :, 0],
                 a[:, None, 1] - b[None, :, 1])
    ja = d.argmin(1)
    da = d[np.arange(len(a)), ja]
    ib = d.argmin(0)
    sel = (da <= rayon) & (ib[ja] == np.arange(len(a)))
    ia = np.flatnonzero(sel)
    return ia, ja[ia], da[ia]


# ======================================================= ajustement TAN
def _ajuster_tan(xy, ra, dec, wcs0, iterations=30):
    """Ajuste un WcsTan aux paires (pixels mesurés ↔ ciel catalogue) par
    Gauss-Newton (8 paramètres : CRVAL, CRPIX, CD ; Jacobienne numérique).
    → (WcsTan, rms_px). Peut diverger si les paires sont fausses : le
    APPELANT vérifie le rms et le nombre de points."""
    p = np.concatenate([np.asarray(wcs0.crval, dtype=np.float64),
                        np.asarray(wcs0.crpix, dtype=np.float64),
                        np.asarray(wcs0.cd, dtype=np.float64).ravel()])
    xy = np.asarray(xy, dtype=np.float64)
    ra = np.asarray(ra, dtype=np.float64)
    dec = np.asarray(dec, dtype=np.float64)

    def residus(q):
        wcs = WcsTan(q[:2], q[2:4], q[4:].reshape(2, 2))
        return (wcs.vers_pixels(ra, dec) - xy).ravel()

    r = residus(p)
    cout = float(r @ r)
    for _ in range(iterations):
        J = np.empty((r.size, p.size))
        for k in range(p.size):
            h = 1e-6 * (abs(p[k]) + 1e-3)
            p2 = p.copy()
            p2[k] += h
            J[:, k] = (residus(p2) - r) / h
        delta = np.linalg.solve(J.T @ J + 1e-9 * np.eye(p.size),
                                -(J.T @ r))
        pas, accepte = 1.0, False
        for _t in range(20):                 # recherche linéaire simple
            q = p + pas * delta
            q[1] = np.clip(q[1], -89.9, 89.9)   # point tangent hors pôles
            r2 = residus(q)
            c2 = float(r2 @ r2)
            if c2 < cout:
                accepte = True
                break
            pas *= 0.5
        if not accepte:
            break
        p, r, cout = q, r2, c2
        if pas * float(np.abs(delta).max()) < 1e-9 or cout < 1e-18:
            break
    wcs = WcsTan(p[:2], p[2:4], p[4:].reshape(2, 2))
    return wcs, math.sqrt(cout / max(1, len(ra)))

# ============================================================== solveur
def _extraire_catalogue(ra0, dec0, champ_deg, forme, dossier=None,
                        limmag=None):
    """Étoiles Gaia couvrant le champ indicé, les plus brillantes d'abord.
    → (dict numpy du catalogue, message) — (None, message) si absent."""
    from . import dossier_catalogues
    from .telechargeur import etat_local
    d = dossier or dossier_catalogues()
    etat = etat_local(d)
    if not etat.get("astro"):
        return None, ("catalogue Gaia astrométrique de Siril introuvable "
                      f"dans {d} — lancez le téléchargeur (jalon 56, "
                      "étape 1)")
    h_img, w_img = forme
    rayon = 0.5 * math.hypot(w_img, h_img) * champ_deg / w_img \
        + MARGE_INDICES
    cat = CatalogueSiril(etat["astro"])
    et = cat.extraire(float(ra0), float(dec0), float(rayon), limmag=limmag)
    if len(et["ra"]) < 3:
        return None, (f"catalogue trop pauvre autour de "
                      f"({ra0:.4f}, {dec0:.4f}) ({len(et['ra'])} étoiles)")
    ordre = np.argsort(et["g"])[:N_CAT_MAX]   # les plus brillantes d'abord
    return {k: v[ordre] for k, v in et.items()}, ""


def resoudre(img, ra0, dec0, champ_deg, dossier=None, limmag=None):
    """Résout l'astrométrie de `img` avec les INDICES (ra0, dec0) du centre
    et `champ_deg` (largeur du champ en degrés, côté est-ouest).
    → (WcsTan, info dict, "") en succès ; (None, info, message) sinon —
    convention du projet : jamais d'exception, jamais de panne silencieuse.
    `info` : n_etoiles_img, n_etoiles_cat, n_appariements, rms_px,
    rms_arcsec, echelle_arcsec_px, angle_deg."""
    info = {"n_etoiles_img": 0, "n_etoiles_cat": 0, "n_appariements": 0,
            "rms_px": None, "rms_arcsec": None, "echelle_arcsec_px": None,
            "angle_deg": None}
    try:
        h_img, w_img = _canonise_img(img).shape
    except Exception as exc:
        return None, info, f"image inexploitable : {exc}"

    champ_deg = float(champ_deg)
    if not (CHAMP_DEG_MIN <= champ_deg <= CHAMP_DEG_MAX):
        return None, info, f"champ indicé hors bornes : {champ_deg}°"

    # 1) étoiles détectées ---------------------------------------------------
    pos, msg = _detecter(img, MAX_ETOILES_DETECTION)
    info["n_etoiles_img"] = int(len(pos))
    if len(pos) < TRI_INLIERS_MIN:
        return None, info, (f"pas assez d'étoiles détectées ({len(pos)})"
                            + (f" — {msg}" if msg else ""))

    # 2) catalogue projeté autour des indices --------------------------------
    et, msg = _extraire_catalogue(ra0, dec0, champ_deg, (h_img, w_img),
                                  dossier=dossier, limmag=limmag)
    if et is None:
        return None, info, msg
    info["n_etoiles_cat"] = int(len(et["ra"]))
    xi, eta = projection_tan(et["ra"], et["dec"], ra0, dec0)
    # CLIP au rectangle indicatif (× marge) AVANT la sélection des plus
    # brillantes : le top-N doit être celui de la ZONE DE L'IMAGE, pas celui
    # du cône d'extraction (sinon les triangles corrects n'existent plus —
    # constat du banc étape 2).
    demi_xi = 0.5 * champ_deg * CLIP_MARGE
    demi_eta = 0.5 * champ_deg * (h_img / w_img) * CLIP_MARGE
    dans = (np.abs(xi) <= demi_xi) & (np.abs(eta) <= demi_eta)
    if int(dans.sum()) < TRI_INLIERS_MIN:
        return None, info, (f"catalogue trop pauvre dans le champ indicé "
                            f"({int(dans.sum())} étoiles)")
    xi, eta = xi[dans], eta[dans]
    ra_clip, dec_clip = et["ra"][dans], et["dec"][dans]
    ordre = np.argsort(et["g"][dans])[:N_CAT_MAX]  # brillantes d'abord
    xi, eta = xi[ordre], eta[ordre]
    ra_clip, dec_clip = ra_clip[ordre], dec_clip[ordre]
    info["n_etoiles_cat"] = int(len(xi))
    cat_xy = np.column_stack([xi, eta])

    # 3) appariement global par triangles ------------------------------------
    inv_img, som_img, _ = _invariants_triangles(pos)
    inv_cat, som_cat, _ = _invariants_triangles(cat_xy, TRI_N_MAX_CAT)
    if inv_img is None or inv_cat is None:
        return None, info, "moins de 3 étoiles d'un côté de l'appariement"
    ecart = np.abs(inv_img[:, None, :] - inv_cat[None, :, :]).max(-1)
    paires = np.argwhere(ecart <= TRI_TOL)
    if not len(paires):
        return None, info, ("aucun triangle image ≈ triangle catalogue — "
                            "indices faux ou champ hors catalogue ?")
    if len(paires) > TRI_PAIRS_MAX:
        ordre = np.argsort(ecart[paires[:, 0], paires[:, 1]])[:TRI_PAIRS_MAX]
        paires = paires[ordre]

    ones_cat = np.column_stack([cat_xy, np.ones(len(cat_xy))])
    n_stop = min(len(pos), len(cat_xy))
    best_M, best_n = None, 0
    for ir, ic in paires:
        # affinité EXACTE 3 points : plan tangent (deg) → pixels
        A = np.column_stack([cat_xy[som_cat[ic]], np.ones(3)])
        try:
            M = np.linalg.solve(A, pos[som_img[ir]])
        except np.linalg.LinAlgError:
            continue
        if not np.isfinite(M).all():
            continue
        pred = ones_cat @ M
        d = np.hypot(pred[:, None, 0] - pos[None, :, 0],
                     pred[:, None, 1] - pos[None, :, 1])
        n = int((d.min(1) <= TRI_RAYON).sum())
        if n > best_n:
            best_n, best_M = n, M
            if best_n >= n_stop:
                break                    # impossible de mieux
    if best_M is None or best_n < TRI_INLIERS_MIN:
        return None, info, (f"aucune affinité convaincante "
                            f"(meilleur score : {best_n} étoiles)")

    # 4) correspondances mutuelles à ±2 px -----------------------------------
    pred = ones_cat @ best_M
    ia, ib, _d = _appariements_mutuels(pos, pred, MUTUEL_RAYON)
    if len(ia) < TRI_INLIERS_MIN:
        return None, info, (f"pas assez de correspondances mutuelles "
                            f"({len(ia)})")

    # 5) ajustement TAN (Gauss-Newton) + réjection 3σ itérative --------------
    xy_f, ra_f, dec_f = pos[ia], ra_clip[ib], dec_clip[ib]
    # initialisation : l'affinité (3, 2) vérifie x = ξ·M[0,0] + η·M[1,0] +
    # M[2,0] → partie linéaire = M[:2, :].T, d'où CD = inverse ; CRVAL =
    # point tangent des indices. (PIÈGE : M[:2,:] SANS transposée inverse la
    # rotation de départ — faux minimum constaté en 3c du banc.)
    try:
        cd0 = np.linalg.inv(best_M[:2, :].T)
    except np.linalg.LinAlgError:
        return None, info, "affinité dégénérée"
    wcs0 = WcsTan((ra0, dec0), best_M[2, :], cd0, forme=(h_img, w_img))
    wcs, rms = _ajuster_tan(xy_f, ra_f, dec_f, wcs0)
    for _ in range(2):
        res = np.hypot(*(wcs.vers_pixels(ra_f, dec_f) - xy_f).T)
        sigma = 1.4826 * float(np.median(np.abs(res - np.median(res))))
        garde = res <= max(3.0 * sigma, 1.5)
        if garde.all() or int(garde.sum()) < TRI_INLIERS_MIN:
            break
        xy_f, ra_f, dec_f = xy_f[garde], ra_f[garde], dec_f[garde]
        wcs, rms = _ajuster_tan(xy_f, ra_f, dec_f, wcs)

    # 6) garde-fous ------------------------------------------------------------
    echelle = wcs.echelle_arcsec
    echelle_indice = 3600.0 * champ_deg / w_img
    if not (ECHELLE_ARCSEC_MIN <= echelle <= ECHELLE_ARCSEC_MAX):
        return None, info, f"échelle résolue absurde : {echelle:.3f}\"/px"
    if not (1.0 - ECHELLE_TOL_RELATIVE <= echelle / echelle_indice
            <= 1.0 + ECHELLE_TOL_RELATIVE):
        return None, info, (f"échelle résolue ({echelle:.3f}\"/px) trop "
                            f"éloignée de l'indice "
                            f"({echelle_indice:.3f}\"/px)")
    if rms > RMS_PX_MAX or len(xy_f) < TRI_INLIERS_MIN:
        return None, info, (f"ajustement insuffisant : rms {rms:.2f} px "
                            f"sur {len(xy_f)} étoiles")

    info.update({"n_appariements": int(len(xy_f)), "rms_px": float(rms),
                 "rms_arcsec": float(rms * echelle),
                 "echelle_arcsec_px": float(echelle),
                 "angle_deg": float(wcs.angle_deg)})
    return wcs, info, ""
