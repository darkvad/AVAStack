# -*- coding: utf-8 -*-
"""HEALPix NESTED en numpy pur — schéma NESTED uniquement (celui des
catalogues Siril/Gaia DR3 et du schéma source_id de Gaia).

Pourquoi « maison » alors que des bibliothèques existent : le projet se
limite volontairement à numpy/OpenCV, et il ne nous faut que trois
opérations — index↔coordonnées et « pixels d'un champ » — fournies ici
vectorisées et SANS dépendance.

Implémentation calquée sur la numérotation standard, validée point à point
contre astropy-healpix (valeurs de référence codées en dur dans le banc du
jalon 56 — règle « toute implémentation est confrontée à une référence
indépendante » de CLAUDE.md).

Géométrie (déduite puis vérifiée numériquement) : les 12 faces se
répartissent en trois familles —
  • 0–3  : losanges « nord » (pôle nord au coin (nside-1, nside-1),
           sommet équatorial au coin (0, 0)) ;
  • 4–7  : losanges équatoriaux (centres à phi = 0, 90, 180, 270°) ;
  • 8–11 : losanges « sud » (pôle sud au coin (0, 0)).
Sur chaque face, le centre du pixel (ix, iy) vérifie EXACTEMENT
(S = ix+iy+1, D = ix-iy, z = sin(dec), n = nside) :
  famille nord       : z = 2S/(3n)                    si S ≤ n
                       z = 1 - ((2n-S)² - 1)/(3n²)    si S > n
                       phi = 90·face + 45 + 45·D/e
                       (e = n si S ≤ n, sinon √((2n-S)²-1) ; 0 au pôle)
  famille équatoriale: z = 2(S-n)/(3n)
                       phi = 90·(face-4) + 45·D/n
  famille sud        : z = -1 + (S²-1)/(3n²)          si S ≤ n
                       z = (2S-4n)/(3n)               si S > n
                       phi = 90·(face-8) + 45 + 45·D/e
                       (e = √(S²-1) si S ≤ n, sinon n ; 0 au pôle)
L'inverse (ang2pix) en découle : ix = ⌊((S-1)+D)/2⌋, iy = ⌊((S-1)-D)/2⌋,
la famille retenue étant celle dont les DEUX indices tombent dans
[0, nside).
"""

import numpy as np

NIVEAU_CATALOGUE = 8            # niveau d'indexation des catalogues Siril
_NSIDE = 1 << NIVEAU_CATALOGUE
NPIX_NIVEAU8 = 12 * _NSIDE * _NSIDE          # 786 432 pixels de niveau 8
_AIRE_PIXEL_DEG2 = 41252.96 / NPIX_NIVEAU8   # ~0,0524 deg² (~0,229° de côté)


def entrelacer(ix, iy, niveau):
    """(ix, iy) → index nested : ix sur les bits pairs, iy sur les impairs."""
    ix = np.asarray(ix, dtype=np.int64)
    iy = np.asarray(iy, dtype=np.int64)
    pix = np.zeros(np.broadcast(ix, iy).shape, dtype=np.int64)
    for b in range(niveau):
        pix |= ((ix >> b) & 1) << (2 * b)
        pix |= ((iy >> b) & 1) << (2 * b + 1)
    return pix


def depaqueter(pix, niveau):
    """Index nested → (ix, iy) (exact inverse de entrelacer)."""
    pix = np.asarray(pix, dtype=np.int64)
    ix = np.zeros(pix.shape, dtype=np.int64)
    iy = np.zeros(pix.shape, dtype=np.int64)
    for b in range(niveau):
        ix |= ((pix >> (2 * b)) & 1) << b
        iy |= ((pix >> (2 * b + 1)) & 1) << b
    return ix, iy


def pix2ang_nest(pix, niveau=NIVEAU_CATALOGUE):
    """Index nested → (ra_deg, dec_deg) du centre du pixel (vectorisé)."""
    nside = 1 << niveau
    pix = np.asarray(pix, dtype=np.int64)
    face = pix >> (2 * niveau)
    ix, iy = depaqueter(pix, niveau)
    S = (ix + iy + 1).astype(float)
    D = (ix - iy).astype(float)
    q = (face % 4).astype(float)

    z = np.empty(pix.shape, dtype=float)
    phi = np.empty(pix.shape, dtype=float)

    nord = face < 4
    if nord.any():
        ixn, iyn = ix[nord].astype(float), iy[nord].astype(float)
        Sn = ixn + iyn + 1.0
        lin = Sn <= nside
        # région linéaire (bande équatoriale de la face) — exacte
        z_lin = 2.0 * Sn / (3 * nside)
        phi_lin = 90.0 * q[nord] + 45.0 + 45.0 * (ixn - iyn) / nside
        # région Collignon (calotte) — exacte : u, v mesurés depuis le
        # coin PÔLE de la face, z = 1 - (u+v)²/3, phi = 90(q+1-u/(u+v))
        u = (nside - ixn - 0.5) / nside
        v = (nside - iyn - 0.5) / nside
        w = u + v
        z_col = 1.0 - w * w / 3.0
        phi_col = 90.0 * (q[nord] + 1.0 - u / np.where(w == 0, 1.0, w))
        phi_col = np.where(w == 0, 90.0 * q[nord] + 45.0, phi_col)
        z[nord] = np.where(lin, z_lin, z_col)
        phi[nord] = np.where(lin, phi_lin, phi_col)

    equ = (face >= 4) & (face < 8)
    if equ.any():
        z[equ] = 2.0 * (S[equ] - nside) / (3 * nside)
        phi[equ] = 90.0 * (face[equ] - 4) + 45.0 * D[equ] / nside

    sud = face >= 8
    if sud.any():
        ixs, iys = ix[sud].astype(float), iy[sud].astype(float)
        Ss = ixs + iys + 1.0
        lin = Ss > nside
        # région linéaire — exacte
        z_lin = (2.0 * Ss - 4 * nside) / (3 * nside)
        phi_lin = 90.0 * (face[sud] - 8) + 45.0 + 45.0 * (ixs - iys) / nside
        # région Collignon (calotte sud) — exacte, pôle au coin (0, 0)
        u = (ixs + 0.5) / nside
        v = (iys + 0.5) / nside
        w = u + v
        z_col = -1.0 + w * w / 3.0
        phi_col = 90.0 * ((face[sud] - 8) + u / np.where(w == 0, 1.0, w))
        z[sud] = np.where(lin, z_lin, z_col)
        phi[sud] = np.where(lin, phi_lin, phi_col)

    dec = np.degrees(np.arcsin(np.clip(z, -1.0, 1.0)))
    return phi % 360.0, dec


def ang2pix_nest(ra, dec, niveau=NIVEAU_CATALOGUE):
    """(ra_deg, dec_deg) → index nested du pixel contenant la direction.

    Inversion analytique exacte des formules de pix2ang_nest, région par
    région : φ est d'abord ramené au CENTRE de la face (dphi ∈ [-45, 45)),
    puis la famille retenue est celle dont les deux indices continus
    tombent dans [0, nside). Une direction exactement sur une arête
    partagée appartient aux deux pixels qu'elle sépare (cas de mesure
    nulle, sans conséquence ici)."""
    nside = 1 << niveau
    ra = np.asarray(ra, dtype=float) % 360.0
    dec = np.asarray(dec, dtype=float)
    z = np.clip(np.sin(np.radians(dec)), -1.0 + 1e-12, 1.0 - 1e-12)
    phi = ra
    # φ relatif au centre de la face : les faces POLAIRES sont centrées à
    # 90q+45, les ÉQUATORIALES à 90q — deux décalages DISTINCTS.
    dphi_pol = (phi % 90.0) - 45.0                 # ∈ [-45, 45)
    dphi_equ = ((phi + 45.0) % 90.0) - 45.0        # ∈ [-45, 45)
    q_pol = np.floor(phi / 90.0).astype(np.int64) % 4
    q_equ = (np.floor((phi + 45.0) / 90.0).astype(np.int64)) % 4

    face = np.full(phi.shape, -1, dtype=np.int64)
    ixc = np.zeros(phi.shape, dtype=float)
    iyc = np.zeros(phi.shape, dtype=float)

    def pose(masque, num_face, a, b):
        ok = (a >= -1e-9) & (a < nside) & (b >= -1e-9) & (b < nside) \
            & (face < 0) & masque
        return np.where(ok, num_face, face), \
            np.where(ok, np.floor(a + 1e-9), ixc), \
            np.where(ok, np.floor(b + 1e-9), iyc)

    # --- famille nord (0–3) -------------------------------------------
    w_n = np.sqrt(3.0 * (1.0 - z))          # u+v continus (unités de face)
    lin = w_n >= 1.0                        # bande équatoriale : z ≤ 2/3
    # linéaire : S continu = 1.5·n·z ; le pixel ix est centré en (S+D)/2
    s1 = 1.5 * nside * z
    d = dphi_pol * nside / 45.0
    face, ixc, iyc = pose(lin, q_pol, (s1 + d) / 2.0, (s1 - d) / 2.0)
    # Collignon : u = w(1-φ_rel), v = w-u (depuis le coin pôle). Les
    # frontières des pixels sont aux ENTIERS de n·u / n·v (centres aux
    # demi-entiers) : floor(n·u), SANS décalage de demi-pixel.
    phi_rel = ((phi - 90.0 * q_pol) / 90.0) % 1.0
    u = w_n * (1.0 - phi_rel)
    v = w_n - u
    face, ixc, iyc = pose(~lin, q_pol, nside * (1.0 - u),
                          nside * (1.0 - v))

    # --- famille équatoriale (4–7) ------------------------------------
    s1 = 1.5 * nside * z + nside - 1.0
    d = dphi_equ * nside / 45.0
    face, ixc, iyc = pose(np.ones_like(z, dtype=bool), 4 + q_equ,
                          (s1 + d) / 2.0, (s1 - d) / 2.0)

    # --- famille sud (8–11) -------------------------------------------
    w_s = np.sqrt(3.0 * (z + 1.0))
    lin = w_s >= 1.0
    s1 = 1.5 * nside * z + 2 * nside - 1.0
    d = dphi_pol * nside / 45.0
    face, ixc, iyc = pose(lin, 8 + q_pol, (s1 + d) / 2.0, (s1 - d) / 2.0)
    phi_rel = ((phi - 90.0 * q_pol) / 90.0) % 1.0
    u = w_s * phi_rel
    v = w_s - u
    face, ixc, iyc = pose(~lin, 8 + q_pol, nside * u, nside * v)

    if not (face >= 0).all():
        raise ValueError("ang2pix_nest : direction non résolue sur la "
                         "sphère — coordonnées invalides ?")
    return (face.astype(np.int64) << (2 * niveau)) | \
        entrelacer(ixc.astype(np.int64), iyc.astype(np.int64), niveau)


def pixel_vers_chunk(pix_niveau8):
    """Pixel de niveau 8 → numéro de chunk (HEALpix niveau 1, 0–47).

    Propriété NESTED : le pixel de niveau 1 est le pixel de niveau 8
    privé de ses 2·7 bits de bas poids."""
    return np.asarray(pix_niveau8, dtype=np.int64) >> (2 * (NIVEAU_CATALOGUE - 1))


def chunk_vers_plage_pixels(chunk):
    """Chunk (niveau 1) → (premier, dernier) pixel de niveau 8 couverts."""
    n = int(chunk) << (2 * (NIVEAU_CATALOGUE - 1))
    return n, n + (1 << (2 * (NIVEAU_CATALOGUE - 1))) - 1


def pixels_cone(ra, dec, rayon_deg, niveau=NIVEAU_CATALOGUE):
    """Pixels (nested, triés) touchant le disque (ra, dec, rayon_deg).

    Méthode : échantillonnage dense du carré circonscrit au disque
    majoré du diamètre d'un pixel (à ce pas, aucun pixel intersectant
    le disque ne peut être manqué), puis filtrage par distance angulaire
    du CENTRE du pixel au disque majoré du demi-diagonal du pixel.
    Sur-sélection assumée : les enregistrements seront de toute façon
    filtrés par leurs positions réelles."""
    # sqrt d'une aire en deg² est DÉJÀ en degrés — ne pas reconvertir !
    cote = float(np.sqrt(_AIRE_PIXEL_DEG2))        # ~0,229°
    pas = 0.3 * cote
    marge = cote
    n = max(2, int(np.ceil(2.0 * (rayon_deg + marge) / pas)) + 1)
    du = np.linspace(-rayon_deg - marge, rayon_deg + marge, n)
    cosd = max(np.cos(np.radians(dec)), 1e-3)
    decs = np.clip(dec + du, -89.9999, 89.9999)
    nra = (ra + du / cosd) % 360.0
    RR, DD = np.meshgrid(nra, decs, indexing="ij")
    pix = ang2pix_nest(RR.ravel(), DD.ravel(), niveau)
    pix = np.unique(pix)
    pra, pdec = pix2ang_nest(pix, niveau)
    sep = np.arccos(np.clip(
        np.sin(np.radians(dec)) * np.sin(np.radians(pdec))
        + np.cos(np.radians(dec)) * np.cos(np.radians(pdec))
        * np.cos(np.radians(pra - ra)), -1.0, 1.0))
    return pix[sep <= np.radians(rayon_deg + marge)]
