#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_avastack.py — paquet d'installation LINUX pour AVAStack.

Construit `installer/linux/output/avastack-setup-<version>-linux.tar.gz` à
partir de `AVASTACK_VERSION` (`avastack/__init__.py`, source unique de vérité —
même règle que l'installateur Windows, cf. CLAUDE.md) : le nom de l'artéfact
PORTE la version, jamais un nom figé.

Contenu du paquet : l'application (`AVAStack.py` + package `avastack/`), les
OUTILS DE DIAGNOSTIC MATÉRIEL caméra (`bancs/cameras/_diag_*.py` — les SEULS
bancs embarqués, décision de projet du 27/09/2026 : « l'installation ne contient
que des outils réellement utilisables par l'utilisateur ; les bancs de RÉGRESSION
`_test_*.py`, à SDK factices, sont des outils de DEV et restent au dépôt),
`requirements.txt`, `veralux_core_headless.py`, et l'installateur
(`installer/install_avastack.sh`, `installer/common/avastack_setup.py`,
`LISEZMOI.txt`). Il ne contient AUCUN SDK constructeur
(`*.so`, `*.dll`, `*.dylib`, `*.rules`), ni venv, ni config : la version livrée
est SANS caméras et travaille en mode dossier / composition / OpenCV / simulé.

Usage (Windows, Linux ou macOS — stdlib seulement) :
    python3 installer/linux/build_avastack.py
    python  installer\\linux\\build_avastack.py

L'archive contient un unique dossier racine `avastack-<version>-linux/` :
    tar xzf avastack-setup-<version>-linux.tar.gz
    cd avastack-<version>-linux
    bash installer/install_avastack.sh
"""

import hashlib
import io
import os
import re
import tarfile

MOTIF_VERSION = re.compile(r'^AVASTACK_VERSION\s*=\s*"([^"]+)"', re.M)
FICHIERS_RACINE = ("AVAStack.py", "requirements.txt", "veralux_core_headless.py")
# Bancs embarqués : les OUTILS DE DIAGNOSTIC MATÉRIEL caméra seulement
# (motif `_diag_*.py`), exactement comme `avastack.iss` — décision de projet du
# 27/09/2026 : « l'installation ne contient que des outils réellement
# utilisables par moi » (les diagnostics parlent aux VRAIES DLL et à SES
# caméras). Les autres bancs — y compris les bancs de RÉGRESSION de la couche
# caméra (`_test_*.py` : SDK factices, aucun matériel requis) — sont des outils
# de DEV : ils vivent sous `bancs/` dans le dépôt et ne sont PAS embarqués.
DOSSIER_CAMERAS = os.path.join("bancs", "cameras")
MOTIF_DIAG = "_diag_"
EXTENSIONS_INTERDITES = (".so", ".dll", ".dylib", ".rules")
# Fichiers dont les fins de ligne DOIVENT être UNIX dans le paquet : un script
# shell en CRLF ne s'exécute pas sous Linux (« set -euo pipefail\r » = commande
# introuvable) alors que le dépôt vit sur Windows (core.autocrlf=true).
EXTENSIONS_UNIX = (".sh", ".txt")
MODES = {".sh": 0o755, ".py": 0o644, ".txt": 0o644}


def racine_depot(chemin_script):
    """Dossier du dépôt = celui qui contient AVAStack.py ET avastack/."""
    dossier = os.path.dirname(os.path.abspath(chemin_script))
    for _ in range(4):
        if (os.path.isfile(os.path.join(dossier, "AVAStack.py"))
                and os.path.isdir(os.path.join(dossier, "avastack"))):
            return dossier
        dossier = os.path.dirname(dossier)
    raise SystemExit("ERREUR : racine du dépôt introuvable (AVAStack.py absent).")


def lire_version(racine):
    """AVASTACK_VERSION lue dans le source (jamais recopiée à la main)."""
    chemin = os.path.join(racine, "avastack", "__init__.py")
    with open(chemin, encoding="utf-8") as f:
        trouve = MOTIF_VERSION.search(f.read())
    if not trouve:
        raise SystemExit("ERREUR : AVASTACK_VERSION introuvable dans " + chemin)
    return trouve.group(1)


def fichiers_a_embarquer(racine):
    """[(source absolu, chemin dans l'archive, mode)] — même esprit que
    avastack.iss : application + outils autonomes, jamais les SDK binaires."""
    entrees = []

    def ajouter(source, arcname=None):
        if arcname is None:
            arcname = os.path.basename(source)
        if arcname.lower().endswith(EXTENSIONS_INTERDITES):
            raise SystemExit("ERREUR : fichier interdit dans le paquet : " + arcname)
        mode = MODES.get(os.path.splitext(source)[1], 0o644)
        entrees.append((source, arcname.replace(os.sep, "/"), mode))

    for nom in FICHIERS_RACINE:
        ajouter(os.path.join(racine, nom))
    # Ressources : l'icone de l'application (assets/ a la racine du depot).
    dossier_assets = os.path.join(racine, "assets")
    if os.path.isdir(dossier_assets):
        for nom in sorted(os.listdir(dossier_assets)):
            chemin = os.path.join(dossier_assets, nom)
            if os.path.isfile(chemin):
                ajouter(chemin, "assets/" + nom)
    dossier_cameras = os.path.join(racine, DOSSIER_CAMERAS)
    for nom in sorted(os.listdir(dossier_cameras)):
        if nom.startswith(MOTIF_DIAG) and nom.endswith(".py"):
            ajouter(os.path.join(dossier_cameras, nom),
                    "bancs/cameras/" + nom)
    for dossier, sous, noms in os.walk(os.path.join(racine, "avastack")):
        sous[:] = [s for s in sous if s != "__pycache__"]
        for nom in sorted(noms):
            if nom.endswith(".py"):
                chemin = os.path.join(dossier, nom)
                ajouter(chemin, os.path.relpath(chemin, racine))
    ajouter(os.path.join(racine, "installer", "linux", "install_avastack.sh"),
            "installer/install_avastack.sh")
    ajouter(os.path.join(racine, "installer", "common", "avastack_setup.py"),
            "installer/common/avastack_setup.py")
    ajouter(os.path.join(racine, "installer", "linux", "LISEZMOI.txt"),
            "LISEZMOI.txt")
    return entrees


def lire_octets(source, arcname):
    """(octets à archiver, converti en fins de ligne UNIX ?).

    Les scripts shell et les lisez-moi sont convertis : le dépôt Windows les
    écrit en CRLF, Linux ne sait pas exécuter un .sh en CRLF.
    """
    with open(source, "rb") as f:
        donnees = f.read()
    if arcname.endswith(EXTENSIONS_UNIX) and b"\r\n" in donnees:
        return donnees.replace(b"\r\n", b"\n"), True
    return donnees, False


def construire(racine, version, dossier_sortie):
    """Écrit l'archive et renvoie (chemin, entrées, fichiers convertis)."""
    nom_archive = "avastack-setup-%s-linux.tar.gz" % version
    chemin = os.path.join(dossier_sortie, nom_archive)
    prefixe = "avastack-%s-linux" % version
    os.makedirs(dossier_sortie, exist_ok=True)
    entrees = fichiers_a_embarquer(racine)
    convertis = []
    with tarfile.open(chemin, "w:gz") as archive:
        for source, arcname, mode in entrees:
            info = archive.gettarinfo(source, arcname=prefixe + "/" + arcname)
            info.mode = mode
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            donnees, converti = lire_octets(source, arcname)
            if converti:
                convertis.append(arcname)
                # la conversion CRLF -> LF change la TAILLE : le tar doit
                # annoncer le nombre d'octets réellement écrits
                info.size = len(donnees)
            archive.addfile(info, io.BytesIO(donnees))
    return chemin, entrees, convertis


def empreinte(chemin):
    """SHA-256 de l'artéfact (pour vérifier une copie transférée)."""
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def main():
    racine = racine_depot(__file__)
    version = lire_version(racine)
    dossier_sortie = os.path.join(racine, "installer", "linux", "output")
    chemin, entrees, convertis = construire(racine, version, dossier_sortie)
    print("Version lue : AVASTACK_VERSION = %s" % version)
    print("Fichiers embarques : %d" % len(entrees))
    if convertis:
        print("Fins de ligne converties en UNIX : %s" % ", ".join(convertis))
    print("Artefact : %s" % chemin)
    print("Taille : %.0f Kio" % (os.path.getsize(chemin) / 1024.0))
    print("SHA-256 : %s" % empreinte(chemin))
    print("")
    print("Installation cote Linux :")
    print("    tar xzf %s" % os.path.basename(chemin))
    print("    cd avastack-%s-linux" % version)
    print("    bash installer/install_avastack.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

