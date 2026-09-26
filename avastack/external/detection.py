# -*- coding: utf-8 -*-
"""Outils de traitement externes (GraXpert, RC-Astro CLI…).

Détection automatique des exécutables + commandes par défaut. Une fois
détectées ou choisies via le bouton « … » de l'interface, les commandes
complètes sont persistées dans config.json (cf. avastack/config.py).
"""

import os
import re
import shutil

from ..compat import IS_WINDOWS, IS_MACOS
from ..config import CONFIG


def trouver_exe(noms, env_var, sous_chemins):
    """Cherche un exécutable : 1) variable d'environnement dédiée,
    2) dans le PATH (shutil.which), 3) emplacements d'installation courants
    selon l'OS. → chemin complet ou None."""
    env = os.environ.get(env_var)
    if env and os.path.isfile(env):
        return env
    for nom in noms:
        trouve = shutil.which(nom)
        if trouve:
            return trouve
    racines = ([os.environ.get("LOCALAPPDATA", ""), os.environ.get("PROGRAMFILES", ""),
                os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("PROGRAMW6432", "")]
               if IS_WINDOWS else
               [os.path.expanduser("~/Applications"), "/Applications"]
               if IS_MACOS else
               [os.path.expanduser("~/.local"), "/usr/local", "/opt"])
    for racine in racines:
        if not racine:
            continue
        for sous in sous_chemins:
            for nom in noms:
                c = os.path.join(racine, sous, nom)
                if os.path.isfile(c):
                    return c
    return None


# Noms de binaires par OS (Windows : .exe ; Linux/macOS : sans extension)
_NOM_GRAXPERT = ("graxpert.exe",) if IS_WINDOWS else ("graxpert", "GraXpert")
_NOM_RC_ASTRO = ("rc-astro.exe",) if IS_WINDOWS else ("rc-astro",)
# Emplacements d'installation connus (relatifs aux racines de trouver_exe)
_SOUS_GRAXPERT = ("" if IS_WINDOWS else "GraXpert",)
_SOUS_RC_ASTRO = (os.path.join("RC-Astro", "CLI"), "")

# Placeholders des commandes :
#   {input}    fichier d'entrée (FITS temporaire, instantané de l'empilement)
#   {output}   fichier de sortie complet (…\\xxx.fits)
#   {outbase}  chemin de sortie SANS extension (GraXpert : -output)
_GX_OPTIONS = ('"{input}" -cli -cmd background-extraction '
               '-correction Subtraction -smoothing 0.5 -output "{outbase}"')
# Débruitage (jalon 7, remis le 16/09/2026) : la doc officielle GraXpert
# (README du dépôt Steffenhir/GraXpert) impose le flag -strength (0.0 à 1.0,
# défaut 0.5) pour le débruitage ; -smoothing ne concerne QUE le retrait de
# gradient (le confondre échoue silencieusement). Traitement LONG (IA tuile
# par tuile, plusieurs minutes) : volontairement cantonné au traitement
# manuel sur instantané, jamais au live.
_GX_DN_OPTIONS = ('"{input}" -cli -cmd denoising '
                  '-strength 0.5 -output "{outbase}"')


def commande_par_defaut_graxpert():
    """Commande GraXpert : chemin détecté si trouvé, sinon binaire nu (PATH)."""
    exe = trouver_exe(_NOM_GRAXPERT, "AVASTACK_GRAXPERT", _SOUS_GRAXPERT)
    if exe is None:
        return 'graxpert ' + _GX_OPTIONS
    return f'"{exe}" ' + _GX_OPTIONS


def commande_par_defaut_graxpert_dn():
    """Commande GraXpert DÉBRUITAGE : même exécutable, -cmd denoising."""
    exe = trouver_exe(_NOM_GRAXPERT, "AVASTACK_GRAXPERT", _SOUS_GRAXPERT)
    if exe is None:
        return 'graxpert ' + _GX_DN_OPTIONS
    return f'"{exe}" ' + _GX_DN_OPTIONS


# Options BXT ÉCRITES EXPLICITEMENT (v2.38.3, décision d'Alain, 27/09/2026).
# POURQUOI : le CLI rc-astro a des DÉFAUTS qui agissent tant qu'on ne passe rien
# — `--help` du CLI installé (v2.6.9) : `--ss/--sharpen-stars` défaut 0,50,
# `--ash/--adjust-star-halos` défaut 0,00, **`--sn/--sharpen-nonstellar` défaut
# 0,50**. La commande d'origine ne passait que `--ash` : le volet « objets »
# tournait donc à 0,50 sans que rien ne l'écrive, et c'est lui qui ajoutait le
# moucheté chromatique 2-8 px MESURÉ sur l'empilement d'Alain (×1,28 contre la
# vue live ; ×0,48 avec `--sn 0.3`, σ/MAD du bleu 2,95 → 1,49). Réglage retenu :
# étoiles 0,5 (défaut), halos −0,3 (halos réels constatés), objets 0,3.
_BXT_OPTIONS = ('bxt "{input}" -o "{output}" --overwrite '
                '--ss 0.5 --ash -0.3 --sn 0.3')


def commande_par_defaut_bxt():
    """Commande BlurXTerminator (rc-astro) : chemin détecté sinon binaire nu.

    Les paramètres sont EXPLICITES (cf. `_BXT_OPTIONS`) : « ne rien passer »
    n'est PAS neutre — le CLI applique alors ses propres défauts."""
    exe = trouver_exe(_NOM_RC_ASTRO, "AVASTACK_RC_ASTRO", _SOUS_RC_ASTRO)
    if exe is None:
        return "rc-astro " + _BXT_OPTIONS
    return f'"{exe}" ' + _BXT_OPTIONS


# Commandes effectives au lancement : persistance d'abord, détection ensuite.
# (Charge UNE fois à l'import, comme l'ancien module unique.)
DEFAULT_CMD_GRAXPERT = CONFIG.get("cmd_graxpert") or commande_par_defaut_graxpert()
DEFAULT_CMD_GRAXPERT_DN = (CONFIG.get("cmd_graxpert_dn")
                           or commande_par_defaut_graxpert_dn())
DEFAULT_CMD_BXT = CONFIG.get("cmd_bxt") or commande_par_defaut_bxt()


def commande_avec_strength(cmd, val):
    """Renvoie la commande de DÉBRUITAGE avec -strength fixé à val (0..1).

    La valeur réglée dans l'interface est la source de vérité : si la
    commande contient déjà un -strength (saisi à la main ou d'une session
    précédente), il est REMPLACÉ (première occurrence, insensible à la
    casse) ; sinon il est ajouté en fin de commande. Une valeur hors
    bornes est ramenée dans [0, 1] (jamais de crash, jamais d'argument
    invalide transmis à GraXpert)."""
    v = min(1.0, max(0.0, float(val)))
    s = f"{v:.2f}".rstrip("0").rstrip(".") or "0"
    if re.search(r"(?i)-strength\s+\S+", cmd):
        return re.sub(r"(?i)-strength\s+\S+", f"-strength {s}", cmd, count=1)
    return cmd.rstrip() + f" -strength {s}"
