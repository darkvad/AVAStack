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
modèle est dans `processing/spcc.py`). Il lit la base SANS la modifier.

OÙ EST LA BASE (jalon 77 — « AVAStack sans Siril »). Trois emplacements, dans
cet ordre :
  1. la clé de config `chemin_spcc` (choix EXPLICITE de l'utilisateur, champ
     « 📂 Dossier SPCC » de l'interface) ;
  2. la copie d'AVAStack (`spcc-database` du dossier de configuration de
     l'application) — c'est là que le bouton « ⬇ Base SPCC » écrit : le dépôt
     `siril-spcc-database` de GitLab (GPLv3) est téléchargeable sans compte,
     donc la SPCC ne demande plus d'avoir installé Siril ;
  3. les emplacements de Siril, par OS (comportement d'origine, inchangé :
     `%LOCALAPPDATA%\\siril-spcc-database` puis `%LOCALAPPDATA%\\Siril\\
     spcc-database` sous Windows, `~/.local/share/siril-spcc-database` sous
     Linux, `~/Library/Application Support/...` sous macOS).
Un dossier n'est retenu que s'il contient VRAIMENT des profils (`_a_des_profils`)
— un dossier vide ne doit pas masquer une base utilisable ailleurs.

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

from ..compat import IS_MACOS

# Clé de configuration du dossier choisi par l'utilisateur (interface).
CLE_CONFIG = "chemin_spcc"

# Dossiers de la base, dans l'ordre d'essai (mêmes emplacements que Siril).
SOUS_DOSSIERS = {
    "mono_sensors": ("MONO_SENSOR",),
    "mono_filters": ("MONO_FILTER",),
    "osc_sensors": ("OSC_SENSOR",),
    "osc_filters": ("OSC_FILTER", "OSC_LPF"),
    "wb_refs": ("WB_REF",),
}


def _candidats_siril():
    """Emplacements de la base installée par Siril, par OS (ordre d'essai).

    Les constantes d'OS sont lues à l'APPEL (convention des modules de
    détection : un banc peut simuler un autre OS sans recharger le module)."""
    out = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        out.append(os.path.join(local, "siril-spcc-database"))
        out.append(os.path.join(local, "Siril", "spcc-database"))
    if IS_MACOS:
        out.append(os.path.expanduser(
            "~/Library/Application Support/siril-spcc-database"))
    data = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    out.append(os.path.join(data, "siril-spcc-database"))
    out.append(os.path.join(os.path.expanduser("~"), ".local", "share",
                            "siril-spcc-database"))
    return out


def dossier_avastack():
    """Dossier où AVAStack garde SA copie de la base (config de l'APPLICATION,
    donc multiplateforme) : `spcc-database` à côté de config.json."""
    from ..config import dossier_config
    return os.path.join(dossier_config(), "spcc-database")


def _a_des_profils(dossier):
    """`dossier` contient-il au moins UN profil lisible (n'importe quelle
    catégorie) ? Ne lève jamais : un dossier absent ou illisible rend False."""
    if not dossier or not os.path.isdir(dossier):
        return False
    for categorie in SOUS_DOSSIERS:
        d = os.path.join(dossier, categorie)
        try:
            if any(n.lower().endswith(".json") for n in os.listdir(d)):
                return True
        except OSError:
            continue
    return False


def base_complete(dossier):
    """Les CINQ catégories sont-elles présentes ET non vides ? C'est le critère
    d'une base TÉLÉCHARGÉE (le téléchargeur ne retélécharge rien si oui)."""
    if not dossier or not os.path.isdir(dossier):
        return False
    for categorie in SOUS_DOSSIERS:
        try:
            if not any(n.lower().endswith(".json")
                       for n in os.listdir(os.path.join(dossier, categorie))):
                return False
        except OSError:
            return False
    return True


def dossier_ecriture():
    """Dossier où ÉCRIRE la base : celui choisi par l'utilisateur s'il peut être
    créé, sinon la copie d'AVAStack. → "" si aucun n'est utilisable."""
    from ..config import CONFIG
    surcharge = (CONFIG.get(CLE_CONFIG) or "").strip()
    for c in ([surcharge] if surcharge else []) + [dossier_avastack()]:
        try:
            os.makedirs(c, exist_ok=True)
            return c
        except OSError:
            continue
    return ""


def dossier_base():
    """Dossier de la base SPCC retenu, ou None si aucune base n'est installée
    (l'appli doit alors le DIRE, jamais deviner des courbes).

    Ordre : `chemin_spcc` de la config → copie d'AVAStack → emplacements de
    Siril. Seul un dossier qui contient RÉELLEMENT des profils est retenu."""
    from ..config import CONFIG
    surcharge = (CONFIG.get(CLE_CONFIG) or "").strip()
    candidats = ([surcharge] if surcharge else []) + [dossier_avastack()] \
        + _candidats_siril()
    for c in candidats:
        if _a_des_profils(c):
            return c
    return None


def resume_base(dossier=None):
    """{catégorie: nombre de fichiers .json} de la base retenue (ou de
    `dossier`) — pour l'affichage. Dict vide si aucune base."""
    base = dossier or dossier_base()
    out = {}
    if not base:
        return out
    for categorie in SOUS_DOSSIERS:
        try:
            out[categorie] = sum(
                1 for n in os.listdir(os.path.join(base, categorie))
                if n.lower().endswith(".json"))
        except OSError:
            out[categorie] = 0
    return out


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
