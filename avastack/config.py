# -*- coding: utf-8 -*-
"""Persistance de la configuration (config.json).

Emplacement selon les conventions de l'OS :
  %APPDATA%\\AVAStack (Windows), ~/Library/Application Support/AVAStack
  (macOS), ~/.config/AVAStack (Linux, respecte XDG_CONFIG_HOME).

Le dict CONFIG est charge UNE fois a l'import du module (comportement
identique a l'ancien fichier unique) ; l'application le relit/complète
via charger_config() / sauver_config().
"""

import os
import json

from .compat import IS_WINDOWS, IS_MACOS


def dossier_config():
    """Dossier de configuration persistante, selon les conventions de l'OS.
    Cree si absent."""
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif IS_MACOS:
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, "AVAStack")
    os.makedirs(d, exist_ok=True)
    return d


CHEMIN_CONFIG = os.path.join(dossier_config(), "config.json")


def charger_config():
    """Lit config.json → dict ({} si absent/corrompu)."""
    try:
        with open(CHEMIN_CONFIG, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def sauver_config(d):
    """Écrit config.json (tolérant aux échecs : réglages non vitaux)."""
    try:
        with open(CHEMIN_CONFIG, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


# Chargé une fois au démarrage — les commandes d'outils externes (module
# external.detection) s'appuient dessus avant de lancer leur détection.
CONFIG = charger_config()

# ──────────────────────────────────────────────────────────────────────────
# Clés de configuration par défaut (utilisées via CONFIG.get(cle, defaut))
# ──────────────────────────────────────────────────────────────────────────
DEFAUT_CONFIG = {
    # Nom de cible automatique pour les boîtes d'enregistrement
    "nom_cible_auto": True,
    # Annotations temps-réel sur l'image affichée
    "annoter_objets": False,
    "annoter_etoiles": False,
    # N'entourer que les objets RÉELLEMENT détectés dans l'image (v2.56.0)
    "annoter_visibles": True,
    "seuil_mag_etoiles": 8.0,
    # Sauvegarde PNG annotée à côté du FITS
    "annoter_sauvegarde": True,
}
