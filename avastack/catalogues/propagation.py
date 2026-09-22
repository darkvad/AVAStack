# -*- coding: utf-8 -*-
"""Propagation du WCS par COMPOSITION de transformations (jalon 56, étape 3).

Décision d'Alain (22/09/2026) : PAS de re-solve à chaque réempilement — le
WCS est résolu UNE fois sur la référence (solveur interne de l'étape 2,
ASTAP en repli/référence indépendante), puis PROPAGÉ par composition le
long des transformations d'alignement.

La composition est ici EXACTE, sans aucun ajustement : une transformation
warpAffine est exacte sur le plan image, `WcsTan.vers_radec` l'est sur le
plan tangent, et les deux exactitudes se composent :

    ciel(p_frame) = wcs_ref.vers_radec(M @ [p_frame, 1])

L'ajustement TAN n'intervient QUE dans `WcsCompose.vers_tan()`, pour
l'interopérabilité FITS (écrire un en-tête TAN standard consommable par
Siril/astropy) — le banc le confronte à astropy.wcs (règle de CLAUDE.md :
toute implémentation est confrontée à une référence indépendante).

Sens des matrices = convention warpAffine du projet (processing/alignment) :

    p_cible = M @ [p_source, 1]

L'aligneur renvoie M tel que `cv2.warpAffine(frame, M)` se superpose à la
référence ; `propager(wcs_ref, M)` donne donc le WCS de la frame.

Cas « réempilement » (jalon 18) : la grille ne change que quand la
référence change. W0 est le WCS de l'ancien empilement (grille G0). Le
re-stack aligne chaque frame archivée sur la nouvelle référence R1, et
l'ancienne grille est reliée à la nouvelle par UNE SEULE matrice M10,
obtenue en alignant R1 sur l'ancien empilement (un seul alignement,
aucune détection de plus, aucun appariement de catalogue) :

    W1 = propager(W0, M10)          # M10 : pixels R1 → pixels G0
    Wf = propager(W0, compose_M(M10, Mf1))   # WCS d'une frame f

(Les chaînes passent par `compose_M` AVANT `propager` : les matrices se
composent exactement, alors qu'un WcsCompose n'a pas de CRVAL/CRPIX/CD à
exposer à un second `propager`.)

Numpy pur — la FONDATION catalogues ne dépend pas de processing (le
processing, lui, importe catalogues à partir de cette étape 3 ; un import
croisé ferait un cycle, cf. solveur.py).
"""

import math

import numpy as np

from .solveur import WcsTan, _ajuster_tan

# Garde-fous de SANITATION seulement : la politique d'alignement (échelle
# [0.9, 1.1], |angle| ≤ 10°) est appliquée EN AMONT par
# processing/alignment sur chaque matrice — la composition de deux matrices
# valides peut dépasser ces bornes (1,1 × 1,1 = 1,21) sans être fausse.
# Ici on refuse uniquement le mathématiquement inexploitable.
ECHELLE_SAN_MIN, ECHELLE_SAN_MAX = 0.5, 2.0
ANGLE_SAN_DEG = 45.0


def compose_M(M2, M1):
    """Composition warpAffine : p3 = M2(M1(p)) → matrice (2, 3)."""
    M1 = np.asarray(M1, dtype=np.float64).reshape(2, 3)
    M2 = np.asarray(M2, dtype=np.float64).reshape(2, 3)
    A = M2[:2, :2] @ M1[:2, :2]
    t = M2[:2, :2] @ M1[:2, 2] + M2[:2, 2]
    return np.column_stack([A, t])


def inverse_M(M):
    """Inverse d'une warpAffine : p0 = inverse_M(M)(p1) → matrice (2, 3)."""
    M = np.asarray(M, dtype=np.float64).reshape(2, 3)
    Ai = np.linalg.inv(M[:2, :2])
    return np.column_stack([Ai, -(Ai @ M[:2, 2])])


def infos_M(M):
    """→ (angle °, échelle, dx, dy) d'une matrice 2×3 (warpAffine) —
    recopié de processing/alignment (cycle d'import interdit, cf. haut)."""
    a, b = float(M[0, 0]), float(M[1, 0])
    return (float(np.degrees(np.arctan2(b, a))), float(np.hypot(a, b)),
            float(M[0, 2]), float(M[1, 2]))


def propager(wcs_ref, M, forme=None):
    """WCS d'un repère transformé par composition — JAMAIS de re-solve.

    `wcs_ref` : WcsTan du repère cible (référence d'alignement, empilement) ;
    `M` : warpAffine (2, 3) allant du repère à décrire VERS le repère de
    `wcs_ref` (convention du projet : warpAffine(frame, M) ≈ référence).
    → (WcsCompose, "") en succès ; (None, message explicite) sinon —
    convention du projet : jamais d'exception, jamais de panne silencieuse."""
    if wcs_ref is None:
        return None, "WCS de référence absent — rien à propager"
    if not isinstance(wcs_ref, WcsTan):
        return None, (f"WCS de référence attendu WcsTan, reçu "
                      f"{type(wcs_ref).__name__}")
    M = np.asarray(M, dtype=np.float64)
    if M.shape != (2, 3):
        return None, f"matrice d'alignement attendue (2, 3), reçu {M.shape}"
    if not np.isfinite(M).all():
        return None, "matrice d'alignement non finie (NaN/Inf)"
    A = M[:2, :2]
    if abs(float(np.linalg.det(A))) < 1e-12:
        return None, "matrice d'alignement dégénérée (déterminant nul)"
    ang, ech, _dx, _dy = infos_M(M)
    if not (ECHELLE_SAN_MIN <= ech <= ECHELLE_SAN_MAX):
        return None, f"échelle d'alignement aberrante : {ech:.3f}"
    if abs(ang) > ANGLE_SAN_DEG:
        return None, f"angle d'alignement aberrant : {ang:.1f}°"
    return WcsCompose(wcs_ref, M, forme=forme), ""


class WcsCompose:
    """WCS EXACT d'un repère transformé (référence ∘ alignement).

    pixels `p` → ciel : `wcs_ref.vers_radec(M @ [p, 1])` — composition
    exacte, aucun ajustement, aucune perte (l'aller-retour retombe au
    bruit machine, vérifié par le banc). `vers_tan()` seul ré-ajuste un
    WcsTan équivalent, pour écrire un en-tête FITS TAN standard."""

    def __init__(self, wcs_ref, M, forme=None):
        M = np.asarray(M, dtype=np.float64).reshape(2, 3)
        self.wcs_ref = wcs_ref
        self.M = M
        self.A = M[:2, :2].copy()
        self.t = M[:2, 2].copy()
        self.A_inv = np.linalg.inv(self.A)
        self.forme = None if forme is None else tuple(int(v) for v in forme)

    # -- conversions exactes --------------------------------------------------
    def vers_radec(self, xy):
        """Pixels (tableau, 0-based) → (ra, dec) en degrés (arrays).
        Le pixel `p` de ce repère montre le contenu arrivé de M(p) dans le
        repère de référence (sens warpAffine) — c'est LÀ que le ciel est lu."""
        xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
        return self.wcs_ref.vers_radec(xy @ self.A.T + self.t)

    def vers_pixels(self, ra, dec):
        """Ciel (deg) → pixels (tableau, 0-based), array (N, 2) — exact.
        Un point du ciel posé en `p_ref` dans la référence se retrouve en
        M⁻¹(p_ref) dans ce repère (le contenu a été ramené par l'alignement)."""
        p_ref = self.wcs_ref.vers_pixels(ra, dec)
        return (p_ref - self.t) @ self.A_inv.T

    # -- grandeurs dérivées ---------------------------------------------------
    @property
    def echelle_arcsec(self):
        """Échelle moyenne (″/px) du repère transformé."""
        return (self.wcs_ref.echelle_arcsec
                * float(math.sqrt(abs(np.linalg.det(self.A)))))

    @property
    def angle_deg(self):
        """Orientation (deg) de l'axe X pixel — partie linéaire composée
        cd_ref @ A (la même formule que WcsTan.angle_deg)."""
        cd_c = np.asarray(self.wcs_ref.cd, dtype=np.float64) @ self.A
        return float(math.degrees(math.atan2(cd_c[1, 0], cd_c[0, 0])))

    # -- interopérabilité FITS ------------------------------------------------
    def vers_tan(self, forme=None, n=7, iterations=30):
        """Ré-ajuste un WcsTan ÉQUIVALENT (pour un en-tête FITS TAN standard,
        consommable par Siril/astropy) sur une grille `n`×`n` couvrant la
        forme. → (WcsTan, rms_px).

        Initialisation ANALYTIQUE (cd₀ = cd_ref @ A, crpix₀ =
        A⁻¹(crpix_ref − t), CRVAL inchangé). Constat du banc (22/09/2026) :
        l'aligneur du projet n'estime que des SIMILITUDES (rotation +
        translation + échelle uniforme, `estimateAffinePartial2D`), et la
        composition d'un TAN avec une similitude est EXACTEMENT un autre TAN
        (la similitude du plan tangent correspond à une rotation 3D exacte de
        la sphère) — le rms mesuré est alors au bruit machine (~1e-11 px).
        Gauss-Newton ne corrige donc en pratique que rien ; il reste pour
        blinder le cas d'une matrice non-similitude (futur ré-échelonnement).
        La DÉVATION exacte est dans le rms retourné, jamais cachée (jamais
        de panne silencieuse)."""
        forme = self.forme if forme is None else tuple(int(v) for v in forme)
        if not forme or forme[0] <= 0 or forme[1] <= 0:
            raise ValueError("forme (h, w) requise pour vers_tan()")
        h, w = int(forme[0]), int(forme[1])
        n = max(2, int(n))
        xs = np.linspace(0.0, w - 1.0, n)
        ys = np.linspace(0.0, h - 1.0, n)
        XX, YY = np.meshgrid(xs, ys)
        pts = np.column_stack([XX.ravel(), YY.ravel()])
        ra, dec = self.vers_radec(pts)
        cd0 = (np.asarray(self.wcs_ref.cd, dtype=np.float64) @ self.A)
        crpix0 = self.A_inv @ (np.asarray(self.wcs_ref.crpix,
                                          dtype=np.float64) - self.t)
        wcs0 = WcsTan(self.wcs_ref.crval, crpix0, cd0)
        wcs, rms = _ajuster_tan(pts, ra, dec, wcs0, iterations=iterations)
        wcs.forme = (h, w)
        return wcs, float(rms)

    def __repr__(self):
        ang, ech, dx, dy = infos_M(self.M)
        return (f"WcsCompose({self.wcs_ref!r} ∘ M(dx={dx:+.2f}, "
                f"dy={dy:+.2f}, angle={ang:+.3f}°, échelle={ech:.4f}))")
