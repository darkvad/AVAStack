# -*- coding: utf-8 -*-
"""Chargement des bibliothèques natives (SDK constructeurs).

Les SDK binaires (PlayerOneCamera.dll, toupcam.dll, SVBCameraSDK.dll…) sont
du code PROPRIÉTAIRE : ils ne sont JAMAIS dans le dépôt git. Chaque
utilisateur les obtient sur le site du constructeur et les place :
  1. dans le dossier du script (avastack/cameras/) ou du projet,
  2. ou n'importe où, en indiquant le chemin via la variable d'environnement
     dédiée (AVASTACK_PLAYERONE_DIR, AVASTACK_TOUPTEK_DIR, AVASTACK_SVBONY_DIR…).

Ordre de recherche (premier trouvé gagne) :
  variable d'environnement dédiée → dossier du projet → sous-dossiers système.
"""

import os
import ctypes

# Racine du projet (dossier parent du package avastack)
RACINE_PROJET = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def charger_dll(nom_fichier, env_var, sous_dossiers=("sdk", "")):
    """Charge une bibliothèque native en la cherchant aux emplacements
    conventionnels. → handle ctypes, ou lève RuntimeError avec un message
    d'installation clair.

    nom_fichier : ex 'PlayerOneCamera.dll' (le nom dépend déjà de l'OS)
    env_var     : ex 'AVASTACK_PLAYERONE_DIR' (dossier contenant la DLL)
    sous_dossiers : sous-dossiers du projet à scanner (ex 'sdk/')
    """
    candidats = []
    # 1) variable d'environnement dédiée (dossier OU chemin complet du fichier)
    env = os.environ.get(env_var)
    if env:
        candidats.append(env if os.path.isfile(env)
                         else os.path.join(env, nom_fichier))
    # 2) dossier du module cameras + racine du projet (+ sous-dossiers)
    ici = os.path.dirname(os.path.abspath(__file__))
    for base in (ici, RACINE_PROJET):
        for sous in sous_dossiers:
            candidats.append(os.path.join(base, sous, nom_fichier))
    # 3) PATH système (DLL déjà installée au niveau OS)
    for c in candidats:
        if os.path.isfile(c):
            return ctypes.CDLL(c)
    raise RuntimeError(
        f"Bibliothèque '{nom_fichier}' introuvable.\n"
        f"Télécharge le SDK du constructeur et place {nom_fichier} dans le "
        f"dossier du projet, ou définis {env_var}=chemin_du_dossier.")


def nom_bibliotheque(base, is_windows, is_macos):
    """Nom de fichier de bibliothèque selon l'OS (base = 'PlayerOneCamera')."""
    if is_windows:
        return base + ".dll"
    if is_macos:
        return "lib" + base + ".dylib"
    return "lib" + base + ".so"
