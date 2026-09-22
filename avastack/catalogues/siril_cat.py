# -*- coding: utf-8 -*-
"""Lecture des catalogues Siril (format « Siril HEALpixel Catalog » v1.0.0).

Spécification : Zenodo DOI 10.5281/zenodo.14697486 (CC-BY 4.0) ; les deux
catalogues utilisés par le projet sont des extraits de Gaia DR3 :
  • astrométrique        — siril_cat_healpix8_astro.dat (fichier unique,
    16 o/étoile) ;
  • spectrophotométrique — siril_cat1_healpix8_xpsamp_<N>.dat (48 chunks,
    un par pixel HEALpix de niveau 1, 701 o/étoile, spectres xp_sampled
    336–1020 nm par pas de 2 nm, float16 + exposant partagé).

Structure d'un fichier : EN-TÊTE (128 o fixe) + INDEX (uint32 cumulatifs :
786 432 entrées pour un monolithique niveau 8 ; 16 384 pour un chunk
niveau 1 — l'index du chunk ne couvre QUE sa plage de pixels) + DONNÉES
(enregistrements de taille fixe, groupés par pixel HEALpix croissant,
little-endian). Recherche : pixels du champ (healpix.py) → plages
continues → lecture directe via l'index cumulatif (seek) → filtrage
final par distance angulaire réelle.

Un fichier .bz2 de Zenodo ne se consulte pas par seeks : à la première
extraction il est décompressé UNE fois vers un cache .dat à côté (les
chunks d'Alain sont déjà en .dat, jamais concernés).
"""

import bz2
import os

import numpy as np

from . import healpix

TAILLE_ENTETE = 128
TYPE_ASTRO = 1
TYPE_XPSAMP = 2

# dtype numpy des enregistrements (little-endian, SANS alignement numpy :
# itemsize exact 16 et 701 octets, cf. spécification).
DTYPE_ASTRO = np.dtype([
    ("ra_s", "<i4"), ("dec_s", "<i4"),
    ("dra", "<i2"), ("ddec", "<i2"),
    ("teff", "<u2"), ("g", "<i2"),
])
DTYPE_XPSAMP = np.dtype([
    ("ra_s", "<i4"), ("dec_s", "<i4"),
    ("dra", "<i2"), ("ddec", "<i2"),
    ("g", "<i2"), ("fexpo", "i1"), ("flux", "<u2", (343,)),
])
ECHELLE_ANGLE = 360.0 / (2 ** 31 - 1)   # RA/Dec stockés : deg × (2³¹−1)/360
ECHELLE_MAG = 1000.0                    # G en millimag


def lire_entete(chemin):
    """→ dict(titre, release, niveau, type, chunked, chunk_level, chunk,
    pixel_debut, pixel_fin) — lève ValueError si l'en-tête est absurde."""
    with open(chemin, "rb") as f:
        ent = f.read(TAILLE_ENTETE)
    if len(ent) != TAILLE_ENTETE:
        raise ValueError(f"en-tête tronqué ({len(ent)} o) : {chemin}")
    titre = ent[:48].split(b"\x00")[0].decode("ascii", errors="replace").strip()
    release, niveau, ctype, chunked, chunk_level = ent[48:53]
    chunk, p_debut, p_fin = np.frombuffer(ent[53:65], dtype="<u4")
    if not (1 <= niveau <= 12) or ctype not in (1, 2, 3):
        raise ValueError(f"en-tête non Siril (niveau={niveau}, type={ctype})"
                         f" : {chemin}")
    return {"titre": titre, "release": int(release), "niveau": int(niveau),
            "type": int(ctype), "chunked": bool(chunked),
            "chunk_level": int(chunk_level), "chunk": int(chunk),
            "pixel_debut": int(p_debut), "pixel_fin": int(p_fin)}


def _assurer_decompresse(chemin):
    """Fichier .bz2 → cache .dat décompressé à côté (une seule fois).
    → chemin du fichier consultable par seeks."""
    if not chemin.endswith(".bz2"):
        return chemin
    cache = chemin[:-4]
    if os.path.isfile(cache) and os.path.getsize(cache) > TAILLE_ENTETE:
        return cache
    tmp = cache + ".part"
    with bz2.open(chemin, "rb") as src, open(tmp, "wb") as dst:
        while True:
            bloc = src.read(1 << 20)
            if not bloc:
                break
            dst.write(bloc)
    os.replace(tmp, cache)          # atomique : pas de cache à moitié écrit
    return cache


class CatalogueSiril:
    """Un ou plusieurs fichiers du format Siril (monolithique OU chunks
    du MÊME catalogue). `extraire()` renvoie un dict de tableaux numpy.
    Aucun état global ; l'index reste en RAM (~3 Mo par fichier)."""

    def __init__(self, chemins):
        if isinstance(chemins, (str, bytes)):
            chemins = [chemins]
        self.fichiers = []
        self.dtype = None
        for brut in chemins:
            chemin = _assurer_decompresse(brut)
            ent = lire_entete(chemin)
            taille = os.path.getsize(chemin)
            n_index = healpix.NPIX_NIVEAU8
            if ent["chunked"]:
                # un chunk de niveau L couvre 4^(8-L) pixels de niveau 8
                # (16 384 pour L=1) — c'est la taille de SON index local
                # (cf. loader Siril : n_healpixels /= 12·nside_chunk²)
                n_index = 1 << (2 * (healpix.NIVEAU_CATALOGUE
                                     - ent["chunk_level"]))
            dtype = DTYPE_ASTRO if ent["type"] == TYPE_ASTRO else DTYPE_XPSAMP
            attendu = TAILLE_ENTETE + 4 * n_index
            if taille < attendu:
                raise ValueError(f"{chemin} trop court ({taille} o)")
            data = taille - attendu
            if data % dtype.itemsize:
                raise ValueError(f"{chemin} : zone de données ({data} o) pas "
                                 f"multiple de {dtype.itemsize} o")
            with open(chemin, "rb") as f:
                f.seek(TAILLE_ENTETE)
                index = np.fromfile(f, dtype="<u4", count=n_index)
            if self.dtype is None:
                self.dtype = dtype
            elif self.dtype != dtype:
                raise ValueError("mélange de catalogues de types différents")
            self.fichiers.append({"chemin": chemin, "entete": ent,
                                  "index": index, "offset_data": attendu})

    # ------------------------------------------------------------------
    def _lire_plage(self, fich, p_debut, p_fin):
        """Enregistrements des pixels [p_debut, p_fin] (indices LOCAUX au
        chunk si chunké — l'appelant a déjà converti)."""
        index = fich["index"]
        i0 = 0 if p_debut == 0 else int(index[p_debut - 1])
        i1 = int(index[p_fin])
        if i1 <= i0:
            return None
        with open(fich["chemin"], "rb") as f:
            f.seek(fich["offset_data"] + i0 * self.dtype.itemsize)
            brut = f.read((i1 - i0) * self.dtype.itemsize)
        return np.frombuffer(brut, dtype=self.dtype)

    def _vide(self):
        out = {"ra": np.empty(0), "dec": np.empty(0), "g": np.empty(0),
               "dra": np.empty(0), "ddec": np.empty(0)}
        if self.dtype is DTYPE_ASTRO:
            out["teff"] = np.empty(0)
        else:
            out["flux"] = np.empty((0, 343))
            out["fexpo"] = np.empty(0)
        return out

    def extraire(self, ra, dec, rayon_deg, limmag=None):
        """Étoiles du disque (ra, dec, rayon en degrés), G ≤ limmag si
        fourni. → dict numpy : ra, dec (deg), dra, ddec (mas/an), g (mag)
        + teff (astro) ou flux (n, 343) et fexpo (xpsamp). Le filtrage
        spatial se fait sur les positions RÉELLES du catalogue (l'index
        n'est qu'un moyen de ne lire que les bons pixels)."""
        pix = healpix.pixels_cone(ra, dec, rayon_deg)
        if pix.size == 0:
            return self._vide()
        morceaux = []
        for fich in self.fichiers:
            ent = fich["entete"]
            if ent["chunked"]:
                p0, p1 = ent["pixel_debut"], ent["pixel_fin"]
                loc = pix[(pix >= p0) & (pix <= p1)] - p0
            else:
                loc = pix[pix < len(fich["index"])]
            if loc.size == 0:
                continue
            coup = np.flatnonzero(np.diff(loc) > 1)
            deb = np.concatenate(([0], coup + 1))
            fin = np.concatenate((coup, [loc.size - 1]))
            for a, b in zip(deb, fin):
                brut = self._lire_plage(fich, int(loc[a]), int(loc[b]))
                if brut is not None:
                    morceaux.append(brut)
        if not morceaux:
            return self._vide()
        rec = np.concatenate(morceaux)

        ra_cat = rec["ra_s"].astype(np.float64) * ECHELLE_ANGLE
        dec_cat = rec["dec_s"].astype(np.float64) * ECHELLE_ANGLE
        g = rec["g"].astype(np.float64) / ECHELLE_MAG

        dra_deg = (ra_cat - ra + 180.0) % 360.0 - 180.0
        cosd = np.cos(np.radians(dec))
        garde = ((dra_deg * cosd) ** 2 + (dec_cat - dec) ** 2
                 <= rayon_deg * rayon_deg)
        if limmag is not None:
            garde &= g <= float(limmag)
        if not garde.any():
            return self._vide()
        rec, ra_cat, dec_cat, g = (rec[garde], ra_cat[garde],
                                   dec_cat[garde], g[garde])
        out = {"ra": ra_cat % 360.0, "dec": dec_cat, "g": g,
               "dra": rec["dra"].astype(np.float64),
               "ddec": rec["ddec"].astype(np.float64)}
        if self.dtype is DTYPE_ASTRO:
            out["teff"] = rec["teff"].astype(np.float64)   # 0 = indisponible
        else:
            expo = rec["fexpo"].astype(np.float64)
            flux16 = rec["flux"].astype(np.float16).astype(np.float64)
            out["flux"] = flux16 * np.power(10.0, expo)[:, None]
            out["fexpo"] = expo
        return out