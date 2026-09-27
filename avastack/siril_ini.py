# -*- coding: utf-8 -*-
"""Lecture de l'ini de Siril — le « carnet d'adresses » des outils voisins.

POURQUOI CE MODULE (constat d'Alain, 27/09/2026) : Siril range dans son
fichier de configuration le chemin de GraXpert ET ceux de ses catalogues Gaia.
C'est donc une source EXPLICITE, déjà renseignée par l'utilisateur, pour deux
détections qu'AVAStack faisait jusqu'ici à l'aveugle (dossier de catalogues,
exécutable GraXpert) :

    %LOCALAPPDATA%\\siril\\config.1.4.ini       (Windows, machine d'Alain)
        graxpert_path=C:\\\\Users\\\\alain\\\\AppData\\\\Local\\\\Programs\\\\GraXpert\\\\GraXpert.exe
        catalogue_gaia_astro=C:\\\\Users\\\\alain\\\\AppData\\\\Local\\\\siril\\\\siril_cat_healpix8_astro.dat
        catalogue_gaia_photo=C:\\\\Users\\\\alain\\\\AppData\\\\Local\\\\siril\\\\siril_cat1_healpix8_xpsamp

Emplacements VÉRIFIÉS dans la documentation Siril 1.4.4 (« Preferences ») et
dans `src/core/initfile.c` (le fichier s'appelle `config<MAJ>.<MIN>.ini`) :

    Linux    ~/.config/siril/configX.Y.ini              (XDG_CONFIG_HOME honoré)
    Windows  %LOCALAPPDATA%\\siril\\configX.Y.ini
    macOS    ~/Library/Application Support/org.free-astro.Siril/siril/configX.Y.ini

PIÈGE (mesuré dans l'ini réel) : les valeurs sont écrites par GKeyFile, qui
ÉCHAPPE les antislashs (`C:\\\\Users\\\\...`). Ne pas déséchaîner donne un chemin
inexistant — donc une détection muette de plus. Toutes les lectures passent
par `_desescapage()`.

Convention des modules de détection : les constantes d'OS sont lues à
l'APPEL (`IS_WINDOWS`/`IS_MACOS` du module), pour que les bancs puissent
simuler un autre OS sans recharger le module.
"""

import glob
import os

from .compat import IS_MACOS, IS_WINDOWS

# Clés utiles de l'ini (clé brute, sans groupe : les noms sont uniques).
CLE_GRAXPERT = "graxpert_path"
CLE_CATALOGUE_ASTRO = "catalogue_gaia_astro"
CLE_CATALOGUE_PHOTO = "catalogue_gaia_photo"


def dossiers_config_siril():
    """Dossiers de configuration de Siril, par OS (ordre d'essai).

    Doc Siril 1.4.4 « Preferences » : `~/.config/siril` (Linux, XDG respecté),
    `%LOCALAPPDATA%\\siril` (Windows), `~/Library/Application Support/
    org.free-astro.Siril/siril` (macOS)."""
    out = []
    if IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA")
        if local:
            out.append(os.path.join(local, "siril"))
    elif IS_MACOS:
        out.append(os.path.expanduser(
            "~/Library/Application Support/org.free-astro.Siril/siril"))
    conf = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    out.append(os.path.join(conf, "siril"))
    return out


def fichiers_ini():
    """Fichiers `config*.ini` existants, du plus RÉCENT au plus ancien.

    Siril nomme le sien `config<MAJ>.<MIN>.ini` (ex. `config.1.4.ini`) : le
    tri décroissant fait gagner la version la plus récente quand plusieurs
    cohabitent (mise à jour de Siril)."""
    trouves = []
    for d in dossiers_config_siril():
        try:
            trouves += glob.glob(os.path.join(d, "config*.ini"))
        except OSError:                       # jamais d'exception (convention)
            continue
    return sorted(set(trouves), reverse=True)


def _desescapage(valeur):
    """Déséchaîne une valeur GKeyFile (`\\\\` → `\\`, `\\n`, `\\t`, `\\r`, `\\s`)."""
    out = []
    i = 0
    while i < len(valeur):
        c = valeur[i]
        if c == "\\" and i + 1 < len(valeur):
            out.append({"n": "\n", "t": "\t", "r": "\r", "s": " "}.get(
                valeur[i + 1], valeur[i + 1]))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def lire_cle(cle):
    """Valeur de `cle` trouvée dans le premier ini qui la porte, ou None.

    Recherche SANS tenir compte du groupe (`[core]`…) : les clés qui nous
    intéressent (`graxpert_path`, `catalogue_gaia_*`) ont des noms uniques.
    Lecture tolérante : fichier illisible, ligne sans `=` ou clé absente →
    on passe au suivant, jamais d'exception."""
    for chemin in fichiers_ini():
        try:
            with open(chemin, encoding="utf-8", errors="replace") as f:
                lignes = f.read().splitlines()
        except OSError:
            continue
        for ligne in lignes:
            ligne = ligne.strip()
            if not ligne or ligne.startswith(("#", ";", "[")):
                continue
            if "=" not in ligne:
                continue
            nom, _, valeur = ligne.partition("=")
            if nom.strip() != cle:
                continue
            valeur = _desescapage(valeur.strip())
            if valeur:
                return valeur
    return None


def lire_chemin(cle):
    """Chemin cité par `cle` (déséchaîné, `~` développé) ou None.

    Ne teste PAS l'existence : l'appelant décide (une valeur peut désigner un
    dossier — cf. `catalogue_gaia_photo`, qui n'a pas d'extension)."""
    valeur = lire_cle(cle)
    if not valeur:
        return None
    return os.path.expanduser(valeur)


def chemin_fichier(cle):
    """Chemin cité par `cle` s'il existe VRAIMENT comme fichier, sinon None.

    C'est ce qu'attend une détection d'exécutable : une valeur figée dans
    l'ini après un désinstallateur ne doit pas faire croire que l'outil est
    là."""
    p = lire_chemin(cle)
    return p if p and os.path.isfile(p) else None
