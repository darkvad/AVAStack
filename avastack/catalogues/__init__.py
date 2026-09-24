# -*- coding: utf-8 -*-
"""Catalogues d'étoiles locaux (jalon 56, étape 1 — fondations SPCC).

Sous-module `healpix`      — HEALPix NESTED en numpy pur (index↔coordonnées,
                             pixels d'un champ, chunks niveau 1) ;
sous-module `siril_cat`    — lecture du format « Siril HEALpixel Catalog »
                             (Gaia DR3 astrométrique + spectrophotométrique) ;
sous-module `telechargeur` — téléchargement Zenodo à froid (reprise,
                             sha256, en-têtes navigateur).

Dossier par défaut des catalogues : le dossier des catalogues Siril si
présent, sinon un dossier `catalogues` dans la configuration AVAStack.
Surchargeable par la clé de config `chemin_catalogues`.
"""

import os

from ..compat import IS_WINDOWS
from . import astap, healpix, siril_cat, solveur, telechargeur
from .healpix import (NIVEAU_CATALOGUE, NPIX_NIVEAU8, ang2pix_nest,
                      chunk_vers_plage_pixels, entrelacer, depaqueter,
                      pixel_vers_chunk, pix2ang_nest, pixels_cone)
from .siril_cat import (CatalogueSiril, DTYPE_ASTRO, DTYPE_XPSAMP,
                        TAILLE_ENTETE, TYPE_ASTRO, TYPE_XPSAMP, lire_entete)
from .solveur import WcsTan, projection_tan, projection_tan_inverse, resoudre
from .propagation import (WcsCompose, compose_M, infos_M, inverse_M,
                          propager)
from .astap import trouver_astap, resoudre_avec_astap
from .astap import balayage_possible, bases_installees
from .telechargeur import (RECORD_ASTRO, RECORD_XPSAMP, etat_local,
                           sommaire_zenodo, telecharger,
                           telecharger_catalogue_astro,
                           telecharger_chunk_xpsamp)

__all__ = [
    "healpix", "siril_cat", "telechargeur", "solveur", "astap",
    "NIVEAU_CATALOGUE", "NPIX_NIVEAU8", "ang2pix_nest", "pix2ang_nest",
    "entrelacer", "depaqueter", "pixel_vers_chunk", "chunk_vers_plage_pixels",
    "pixels_cone", "CatalogueSiril", "lire_entete", "TAILLE_ENTETE",
    "TYPE_ASTRO", "TYPE_XPSAMP", "DTYPE_ASTRO", "DTYPE_XPSAMP",
    "RECORD_ASTRO", "RECORD_XPSAMP", "telecharger", "etat_local",
    "sommaire_zenodo", "telecharger_catalogue_astro",
    "telecharger_chunk_xpsamp", "dossier_catalogues",
    "WcsTan", "projection_tan", "projection_tan_inverse", "resoudre",
    "WcsCompose", "propager", "compose_M", "inverse_M", "infos_M",
    "trouver_astap", "resoudre_avec_astap", "balayage_possible",
    "bases_installees",
]


def dossier_catalogues():
    """Dossier par défaut des catalogues : celui de Siril s'il existe
    (les chunks d'Alain y sont déjà), sinon dans la config AVAStack."""
    candidats = []
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidats.append(os.path.join(local, "Siril"))
    candidats.append(os.path.join(os.path.expanduser("~"),
                                  ".local", "share", "kstars"))
    for c in candidats:
        if os.path.isdir(c) and any(
                n.startswith("siril_cat") for n in os.listdir(c)):
            return c
    from ..config import dossier_config
    d = os.path.join(dossier_config(), "catalogues")
    os.makedirs(d, exist_ok=True)
    return d