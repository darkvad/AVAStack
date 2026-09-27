# -*- coding: utf-8 -*-
"""Catalogues d'étoiles locaux (jalon 56, étape 1 — fondations SPCC).

Sous-module `healpix`      — HEALPix NESTED en numpy pur (index↔coordonnées,
                             pixels d'un champ, chunks niveau 1) ;
sous-module `siril_cat`    — lecture du format « Siril HEALpixel Catalog »
                             (Gaia DR3 astrométrique + spectrophotométrique) ;
sous-module `telechargeur` — téléchargement Zenodo à froid (reprise,
                             sha256, en-têtes navigateur).

Dossier par défaut des catalogues (jalon 70, constat Linux du 27/09/2026).
`dossiers_siril()` liste les dossiers de Siril/KStars PAR OS — sous Linux
`~/.local/share/siril` (vérifié dans la documentation Siril 1.4.4,
`core.catalogue_gaia_astro`) : c'est ce chemin qui MANQUAIT, l'application ne
regardait que le dossier KStars puis retombait sur un dossier AVAStack vide,
et l'astrométrie échouait sans que rien ne désigne les données manquantes.
La clé de config `chemin_catalogues` (champ « Catalogues » de l'interface, et
bouton de téléchargement) prime ; sinon le dossier `catalogues` de la
configuration AVAStack sert de repli.
"""

import os

from ..compat import IS_MACOS, IS_WINDOWS
from . import astap, healpix, siril_cat, solveur, telechargeur
from .healpix import (NIVEAU_CATALOGUE, NPIX_NIVEAU8, ang2pix_nest,
                      chunk_vers_plage_pixels, entrelacer, depaqueter,
                      pixel_vers_chunk, pix2ang_nest, pixels_cone)
from .siril_cat import (CatalogueSiril, DTYPE_ASTRO, DTYPE_XPSAMP,
                        TAILLE_ENTETE, TYPE_ASTRO, TYPE_XPSAMP, lire_entete)
from .solveur import (WcsTan, projection_tan, projection_tan_inverse, resoudre,
                      MSG_CATALOGUE_ABSENT)
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
    "dossiers_siril", "chemin_catalogue_astro", "MSG_CATALOGUE_ABSENT",
    "WcsTan", "projection_tan", "projection_tan_inverse", "resoudre",
    "WcsCompose", "propager", "compose_M", "inverse_M", "infos_M",
    "trouver_astap", "resoudre_avec_astap", "balayage_possible",
    "bases_installees",
]


def dossiers_siril():
    """Dossiers où chercher les catalogues, par OS (ordre d'essai).

    VÉRIFIÉ le 27/09/2026 dans la documentation Siril 1.4.4 (« Preferences
    (commands) ») : Siril range les siens sous Linux dans
    `~/.local/share/siril` (`core.catalogue_gaia_astro`), sous Windows dans
    `%LOCALAPPDATA%\\Siril` ; les catalogues KStars restent, eux, dans
    `~/.local/share/kstars` quel que soit l'OS. `XDG_DATA_HOME` est honoré.

    Le dossier KStars ne contient PAS les fichiers du projet (`siril_cat*`) :
    c'est `_nb_catalogues` qui décide, dossier par dossier, lequel est
    réellement utilisable.
    """
    racines = []
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA")
        if local:
            racines.append(os.path.join(local, "Siril"))
    elif IS_MACOS:
        racines.append(os.path.expanduser(
            "~/Library/Application Support/Siril"))
    data = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    for nom in ("siril", "kstars"):
        racines.append(os.path.join(data, nom))
        racines.append(os.path.join(os.path.expanduser("~"), ".local", "share",
                                    nom))
    return racines


def _nb_catalogues(dossier):
    """Nombre de fichiers de catalogue ATTENDUS par le projet dans `dossier`
    (`siril_cat*` : astro et/ou chunks spectro) — 0 si le dossier est absent
    ou illisible (jamais d'exception)."""
    try:
        return sum(1 for n in os.listdir(dossier) if n.startswith("siril_cat"))
    except OSError:
        return 0


def dossier_catalogues():
    """Dossier des catalogues, dans cet ordre :
      1. la surcharge `chemin_catalogues` de la config (choix explicite de
         l'utilisateur — champ « Catalogues » de l'interface), si elle existe ;
      2. le dossier DÉSIGNÉ par l'INI DE SIRIL (`catalogue_gaia_astro` /
         `catalogue_gaia_photo`, v2.38.5) : c'est là que Siril a réellement
         rangé ses catalogues Gaia, l'utilisateur l'a déjà renseigné (relevé
         dans `%LOCALAPPDATA%\\siril\\config.1.4.ini` le 27/09/2026) ;
      3. le premier dossier de Siril/KStars qui contient DÉJÀ des fichiers du
         projet (`siril_cat*`), par OS ;
      4. le dossier `catalogues` de la configuration AVAStack, créé au besoin —
         c'est là que le bouton de téléchargement de l'interface écrit."""
    from ..config import CONFIG
    from .. import siril_ini
    surcharge = (CONFIG.get("chemin_catalogues") or "").strip()
    if surcharge and os.path.isdir(surcharge):
        return surcharge
    for cle in (siril_ini.CLE_CATALOGUE_ASTRO, siril_ini.CLE_CATALOGUE_PHOTO):
        p = siril_ini.lire_chemin(cle)
        d = os.path.dirname(p) if p else ""
        if d and _nb_catalogues(d):
            return d
    for c in dossiers_siril():
        if _nb_catalogues(c):
            return c
    from ..config import dossier_config
    d = os.path.join(dossier_config(), "catalogues")
    os.makedirs(d, exist_ok=True)
    return d


def chemin_catalogue_astro(dossier=None):
    """Chemin du catalogue astrométrique PRÉSENT, ou None. `etat_local` fait
    foi : fichier `.dat` décompressé ou `.bz2` téléchargé."""
    from .telechargeur import etat_local
    return etat_local(dossier or dossier_catalogues()).get("astro")