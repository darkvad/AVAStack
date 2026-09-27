# -*- coding: utf-8 -*-
"""Outils de traitement externes (GraXpert, RC-Astro CLI…).

Détection automatique des exécutables + commandes par défaut. Une fois
détectées ou choisies via le bouton « … » de l'interface, les commandes
complètes sont persistées dans config.json (cf. avastack/config.py).
"""

import glob
import os
import re
import shutil

from .. import siril_ini
from .. import travail
from ..compat import IS_WINDOWS, IS_MACOS
from ..config import CONFIG


def _racines():
    """Racines d'installation à sonder, par OS (liste ordonnée, sans trou).

    v2.38.11 : les racines situées sur un **montage RÉSEAU (NAS)** sont
    ÉCARTÉES. POURQUOI (constat RÉEL d'Alain, 27/09/2026) : cette détection
    tournait à l'IMPORT de l'interface, et `os.path.isfile`/`glob` font des
    `stat` — sur un NAS injoignable (pare-feu `nftables`, autofs sans délai) ils
    ATTENDENT INDÉFINIMENT : l'application ne s'ouvrait plus, sans un mot. Un
    outil installé sur un NAS se désigne à la main (bouton « … »), ce qui est de
    toute façon le geste prévu."""
    if IS_WINDOWS:
        noms = ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
                "PROGRAMW6432")
        racines = [os.environ.get(n, "") for n in noms]
    elif IS_MACOS:
        racines = [os.path.expanduser("~/Applications"), "/Applications"]
    else:
        # Linux : dossier utilisateur (extraction d'un archive), `bin` utilisateur,
        # puis les emplacements système. `~` est sondé EN DERNIER et seulement par
        # nom d'outil/filtre : aucune exploration récursive du dossier personnel.
        racines = [os.path.expanduser("~/.local"), "/usr/local", "/opt",
                   os.path.expanduser("~/Applications"),
                   os.path.expanduser("~")]
    return [r for r in racines if r and not travail.sur_montage_reseau(r)]


def _path_local():
    """Le PATH privé de ses dossiers situés sur un MONTAGE RÉSEAU (NAS).

    `shutil.which` teste CHAQUE dossier du PATH : un dossier sur un NAS
    injoignable fait donc attendre la recherche indéfiniment (constat du
    27/09/2026). → None si aucun dossier local ne reste : `shutil.which`
    utilisera alors le PATH tel quel (cas dégénéré, mieux vaut essayer)."""
    morceaux = [d for d in (os.environ.get("PATH") or "").split(os.pathsep)
                if d and not travail.sur_montage_reseau(d)]
    return os.pathsep.join(morceaux) or None


def _noms_graxpert():
    """Noms du binaire GraXpert, par OS.

    PIÈGE MESURÉ (constat d'Alain, 27/09/2026, installateur Linux) : sous
    LINUX le binaire officiel s'appelle **`GraXpert-linux`** — l'archive
    `graxpert-linux-amd64.zip` (Releases Steffenhir/GraXpert) se décompresse
    en `GraXpert-linux`, à rendre exécutable par `chmod u+x ./GraXpert-linux`
    (README officiel : « Linux: Replace GraXpert-win64.exe by
    GraXpert-linux »). L'ancienne liste ne contenait que `graxpert`/`GraXpert`
    et, la comparaison étant SENSIBLE À LA CASSE sous Linux, la détection ne
    pouvait RIEN trouver — l'application retombait sur la commande nue
    « graxpert … » (le shell répondait « command not found » bien plus tard).
    Sous macOS, l'exécutable vit dans le bundle (`GraXpert.app/Contents/
    MacOS/GraXpert`), ce que `_sous_graxpert()` traduit."""
    if IS_WINDOWS:
        return ("graxpert.exe",)
    if IS_MACOS:
        return ("GraXpert", "graxpert")
    return ("GraXpert-linux", "GraXpert-linux-amd64", "graxpert-linux",
            "graxpert", "GraXpert")


def _sous_graxpert():
    """Sous-chemins d'installation de GraXpert (relatifs à `_racines()`)."""
    if IS_WINDOWS:
        # `...\\AppData\\Local\\Programs\\GraXpert\\GraXpert.exe` (obs. 27/09/2026)
        return ("", os.path.join("Programs", "GraXpert"), "GraXpert")
    if IS_MACOS:
        return (os.path.join("GraXpert.app", "Contents", "MacOS"),
                "GraXpert", "")
    return ("GraXpert", "GraXpert-linux-amd64", "bin", "")


def _noms_rc_astro():
    """Noms du CLI rc-astro (BlurXTerminator) — même nom partout hors Windows."""
    return ("rc-astro.exe",) if IS_WINDOWS else ("rc-astro",)


def _sous_rc_astro():
    """Sous-chemins d'installation de rc-astro."""
    return (os.path.join("RC-Astro", "CLI"), "", "bin")


def trouver_exe(noms, env_var, sous_chemins, chemins_directs=(),
                motifs=()):
    """Cherche un exécutable, du plus EXPLICITE au plus deviné :

    1) `chemins_directs` : pistes nommées par un autre outil (ini de Siril,
       dossier `GraXpert.app` de macOS) — l'utilisateur les a déjà désignées ;
    2) `env_var` : variable d'environnement dédiée (`AVASTACK_GRAXPERT`…) ;
    3) le PATH (`shutil.which`, insensible à la casse sous Windows seulement) ;
    4) `racine/sous_chemin/nom` pour chaque racine de l'OS ;
    5) `motifs` : dossiers ou fichiers commençant par le motif (ex.
       `GraXpert*` — archive décompressée dans `~/GraXpert-linux-amd64/`,
       ou AppImage posée dans `~/Applications/`) ; un fichier EXÉCUTABLE
       trouvé par motif est accepté tel quel.
    → chemin complet NORMALISÉ (`os.path.normpath` : jamais de « C:\\a/b » dans
      une commande persistée ni dans la ligne d'état de l'interface), ou None
      (aucune exception remontée ici)."""
    for c in chemins_directs:
        if c and os.path.isfile(c):
            return os.path.normpath(c)
    env = os.environ.get(env_var)
    if env and os.path.isfile(env):
        return os.path.normpath(env)
    for nom in noms:
        trouve = shutil.which(nom, path=_path_local())
        if trouve:
            return os.path.normpath(trouve)
    racines = [r for r in _racines() if r]
    for racine in racines:
        for sous in sous_chemins:
            for nom in noms:
                c = os.path.join(racine, sous, nom)
                if os.path.isfile(c):
                    return os.path.normpath(c)
    for motif in motifs:
        for racine in racines:
            try:
                candidats = sorted(glob.glob(os.path.join(racine, motif)))
            except (OSError, re.error):       # motif invalide : jamais bloquant
                continue
            for p in candidats:
                for nom in noms:
                    c = os.path.join(p, nom)
                    if os.path.isfile(c):
                        return os.path.normpath(c)
                if os.path.isfile(p) and os.access(p, os.X_OK):
                    return os.path.normpath(p)      # AppImage / binaire nu
    return None

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


def chemin_graxpert():
    """Chemin de l'exécutable GraXpert réellement installé, ou None.

    Ordre de recherche (v2.38.5) : la clé `graxpert_path` de l'INI DE SIRIL
    (l'utilisateur l'a déjà désignée là, et c'est elle qui a permis de
    comprendre le cas Linux) → variable `AVASTACK_GRAXPERT` → PATH → noms et
    emplacements de l'OS → dossiers/fichiers `GraXpert*` (archive
    décompressée, AppImage)."""
    return trouver_exe(_noms_graxpert(), "AVASTACK_GRAXPERT", _sous_graxpert(),
                       chemins_directs=(siril_ini.chemin_fichier(
                           siril_ini.CLE_GRAXPERT),),
                       motifs=("GraXpert*",))


def commande_par_defaut_graxpert():
    """Commande GraXpert : chemin détecté si trouvé, sinon binaire nu (PATH)."""
    exe = chemin_graxpert()
    if exe is None:
        return 'graxpert ' + _GX_OPTIONS
    return f'"{exe}" ' + _GX_OPTIONS


def commande_par_defaut_graxpert_dn():
    """Commande GraXpert DÉBRUITAGE : même exécutable, -cmd denoising."""
    exe = chemin_graxpert()
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
    exe = trouver_exe(_noms_rc_astro(), "AVASTACK_RC_ASTRO", _sous_rc_astro())
    if exe is None:
        return "rc-astro " + _BXT_OPTIONS
    return f'"{exe}" ' + _BXT_OPTIONS


# Commandes effectives AU DÉMARRAGE (v2.38.11) : la valeur PERSISTÉE si elle
# existe, sinon le REPLI SANS AUCUN ACCÈS DISQUE (binaire nu, que le shell
# résoudra au lancement).
#
# POURQUOI PLUS DE DÉTECTION ICI : cette détection tournait à l'IMPORT de
# l'interface et balaie le PATH et des dossiers de l'OS (`which`, `glob`,
# `isfile`) — sur un NAS injoignable, ces `stat` attendent indéfiniment et
# l'application ne s'ouvrait plus (constat RÉEL d'Alain, 27/09/2026, dossiers de
# couches R/G/B sur son NAS, `nftables` filtrant ce NAS). La détection se fait
# désormais APRÈS l'affichage, bornée (cf. `detecter_outils` et `delais.borne`
# côté interface).
DEFAULT_CMD_GRAXPERT = CONFIG.get("cmd_graxpert") or ("graxpert " + _GX_OPTIONS)
DEFAULT_CMD_GRAXPERT_DN = (CONFIG.get("cmd_graxpert_dn")
                           or ("graxpert " + _GX_DN_OPTIONS))
DEFAULT_CMD_BXT = CONFIG.get("cmd_bxt") or ("rc-astro " + _BXT_OPTIONS)


def detecter_outils():
    """DÉTECTION RÉELLE des trois outils (accès disque : PATH + dossiers de l'OS).

    À APPELER APRÈS l'affichage, et avec un délai (`delais.borne`) : c'est le
    seul endroit qui touche le disque pour les outils. → dict `{clé: commande}`
    (commande détectée, ou repli binaire nu si l'outil n'est pas trouvé)."""
    return {"cmd_graxpert": commande_par_defaut_graxpert(),
            "cmd_graxpert_dn": commande_par_defaut_graxpert_dn(),
            "cmd_bxt": commande_par_defaut_bxt()}


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
