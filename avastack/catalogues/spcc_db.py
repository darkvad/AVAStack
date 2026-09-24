# -*- coding: utf-8 -*-
"""Base SPCC de Siril : profils de CAPTEURS et de FILTRES (jalon 58).

Siril calcule sa calibration spectrophotométrique avec deux bases :
  1. les SPECTRES Gaia DR3 `xp_sampled` (catalogue local, lu par
     `catalogues.siril_cat` — déjà en place pour l'astrométrie/photométrie) ;
  2. les PROFILS de réponse publiés dans le dépôt `siril-spcc-database`
     (JSON, un fichier par modèle, plusieurs objets par fichier), où sont
     décrites :
       • la réponse QUANTIQUE d'un capteur (mono ou par canal pour un OSC),
       • la TRANSMISSION d'un filtre (par canal : RED, GREEN, BLUE, LUM…) ;
       • les SPECTRES DE RÉFÉRENCE de blanc (`wb_refs/` : fond de galaxie
         spirale moyenne, étoiles types, elliptiques…), qui servent à fixer
         la couleur « réelle » visée.

Ce module ne fait QUE lire et exposer ces courbes : aucun calcul ici (le
modèle est dans `processing/spcc.py`). Il lit la base installée par Siril
(`%LOCALAPPDATA%\\siril-spcc-database` sous Windows), sans la modifier.

FORMAT d'un objet (schéma `spcc-database-schema.json`) : dictionnaire JSON
`model`, `name`, `type` (MONO_SENSOR / OSC_SENSOR / MONO_FILTER /
OSC_FILTER / OSC_LPF / WB_REF), `channel`, `wavelength.value` (nm) et
`values.value` (+ `range`). Les fichiers de la base contiennent un objet
SEUL (capteurs, références) OU une LISTE d'objets (jeux de filtres : un
objet par couleur) — les deux formes sont gérées.
"""

import json
import os

import numpy as np

# Dossiers de la base, dans l'ordre d'essai (mêmes emplacements que Siril).
SOUS_DOSSIERS = {
    "mono_sensors": ("MONO_SENSOR",),
    "mono_filters": ("MONO_FILTER",),
    "osc_sensors": ("OSC_SENSOR",),
    "osc_filters": ("OSC_FILTER", "OSC_LPF"),
    "wb_refs": ("WB_REF",),
}


def dossier_base():
    """Dossier de la base SPCC de Siril, ou None si elle n'est pas
    installée (l'appli doit alors le DIRE, jamais deviner des courbes)."""
    local = os.environ.get("LOCALAPPDATA")
    candidats = []
    if local:
        candidats.append(os.path.join(local, "siril-spcc-database"))
        candidats.append(os.path.join(local, "Siril", "spcc-database"))
    candidats.append(os.path.join(os.path.expanduser("~"), ".local", "share",
                                  "siril-spcc-database"))
    for c in candidats:
        if os.path.isdir(os.path.join(c, "mono_filters")):
            return c
    return None


def _objets(chemin):
    """Liste des objets d'un fichier JSON (objet seul OU liste)."""
    with open(chemin, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [o for o in data if isinstance(o, dict)]
    return []


def lister(categorie):
    """Entrées d'une catégorie (voir SOUS_DOSSIERS) → liste de dict
    {'nom', 'modele', 'canal', 'chemin', 'index', 'qualite', 'source'}.
    L'`index` est la position de l'objet DANS son fichier (les jeux de
    filtres en contiennent plusieurs : c'est la clé pour en choisir un)."""
    base = dossier_base()
    if base is None:
        return []
    d = os.path.join(base, categorie)
    if not os.path.isdir(d):
        return []
    out = []
    for nom_fichier in sorted(os.listdir(d)):
        if not nom_fichier.lower().endswith(".json"):
            continue
        chemin = os.path.join(d, nom_fichier)
        try:
            objets = _objets(chemin)
        except (OSError, ValueError):
            continue
        for i, o in enumerate(objets):
            out.append({
                "nom": str(o.get("name") or o.get("model") or nom_fichier),
                "modele": str(o.get("model") or ""),
                "canal": str(o.get("channel") or "").upper(),
                "type": str(o.get("type") or ""),
                "chemin": chemin,
                "index": i,
                "qualite": int(o.get("dataQualityMarker") or 0),
                "source": str(o.get("dataSource") or ""),
            })
    return out


def courbe(entree):
    """Courbe (longueurs d'onde en nm, valeurs) d'une entrée de `lister()`.
    Les valeurs sont rendues TELLES QUELLES (aucune normalisation : c'est le
    modèle de `processing/spcc.py` qui décide, Siril gardant les unités du
    fichier — QE du capteur et transmission du filtre dans la même unité
    pour tous les canaux, ce qui rend les RATIOS justes).
    → (wl (N,) float64, val (N,) float64) triés par longueur d'onde
    croissante, ou (None, None) si l'entrée est inexploitable."""
    try:
        objets = _objets(entree["chemin"])
    except (OSError, ValueError, KeyError):
        return None, None
    i = int(entree.get("index", 0))
    if not 0 <= i < len(objets):
        return None, None
    o = objets[i]
    try:
        wl = [float(v) for v in o["wavelength"]["value"]]
        val = [float(v) for v in o["values"]["value"]]
        unite = str(o["wavelength"].get("units") or "nm").strip().lower()
    except (KeyError, TypeError, ValueError):
        return None, None
    # PIÈGE (vérifié le 24/09/2026) : le schéma Siril autorise QUATRE unités
    # de longueur d'onde et les fichiers les utilisent vraiment — les
    # références de blanc sont en ANGSTRÖMS (1005…25050 Å pour la galaxie
    # spirale moyenne), les capteurs et filtres en nm. Sans conversion, la
    # référence tombait HORS de la grille spectrale (336-1020 nm) → intégrales
    # nulles → NaN silencieux. On normalise TOUT en nm ici, une fois.
    facteur = {"nm": 1.0, "nanometre": 1.0, "nanometer": 1.0,
               "angstrom": 0.1, "angstroms": 0.1, "a": 0.1,
               "micrometer": 1000.0, "micrometre": 1000.0, "um": 1000.0,
               "µm": 1000.0, "m": 1e9}.get(unite, None)
    if facteur is None:
        return None, None
    wl = [v * facteur for v in wl]
    if len(wl) < 5 or len(wl) != len(val):
        return None, None
    wl = np.asarray(wl, dtype=np.float64)
    val = np.asarray(val, dtype=np.float64)
    ordre = np.argsort(wl)
    return wl[ordre], val[ordre]
