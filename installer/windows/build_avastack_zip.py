#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_avastack_zip.py — paquet d'installation WINDOWS « ZIP » pour AVAStack.

Construit `installer/windows/output/avastack-setup-<version>-windows.zip` à
partir de `AVASTACK_VERSION` (`avastack/__init__.py`, source unique de vérité —
même règle que les autres packers, cf. CLAUDE.md) : le nom de l'artéfact PORTE
la version, jamais un nom figé.

POURQUOI CE PAQUET EXISTE (constat réel du 01/10/2026) : l'installateur
`avastack-setup-<version>.exe` (Inno Setup) est un EXÉCUTABLE NON SIGNÉ.
Sur un Windows 11 neuf, le **Contrôle intelligent des applications** (Smart App
Control) bloque un fichier temporaire d'Inno Setup et l'installation s'arrête sur
« Erreur 4551 : une stratégie de contrôle d'application a bloqué ce fichier ».
Ce paquet-ci ne contient AUCUN exécutable à nous : l'installation se fait par un
script PowerShell (`installer/install_avastack.ps1`), lancé par le double-clic
sur `installer/install_avastack.bat`. Rien à signer, rien à compiler.

Contenu du paquet : l'application (`AVAStack.py` + package `avastack/`), les
OUTILS DE DIAGNOSTIC MATÉRIEL caméra (`bancs/cameras/_diag_*.py` — les SEULS
bancs embarqués, même règle que `avastack.iss` et que le packer Linux),
`requirements.txt`, `veralux_core_headless.py`, les SDK binaires constructeurs
présents à la racine (`*.dll` : ASICamera2, PlayerOneCamera, ToupCam,
SVBCameraSDK — exactement la liste NOMMÉE d'`avastack.iss`, jamais un joker), et
l'installateur (`installer/install_avastack.ps1`, `installer/install_avastack.bat`,
`installer/common/avastack_setup.py`, `LISEZMOI.txt`).

DIFFÉRENCE ASSUMÉE AVEC LES PACKERS LINUX/macOS : ceux-ci REFUSENT d'embarquer le
moindre binaire constructeur (l'utilisateur y dépose lui-même ses `*.so`). Sous
Windows, l'installateur Inno Setup les embarque DÉJÀ (décision de projet du
19/09/2026) : ce packer-ci fait pareil, sans quoi la distribution ZIP offrirait
moins de caméras que le `.exe`. Les DLL sont ajoutées par NOM (liste explicite),
et leur présence/absence est ANNONCÉE en fin de construction.

FINS DE LIGNE : le dépôt vit sur Windows mais peut contenir des LF ; un `.bat` en
LF se comporte mal sous `cmd.exe`. Tous les `.py`, `.ps1`, `.bat` et `.txt` du
paquet sont donc NORMALISÉS en CRLF (symétrique du packer Linux, qui normalise en
LF les `.sh`/`.txt`).

Usage (Windows, Linux ou macOS — stdlib seulement) :
    python installer/windows/build_avastack_zip.py

Contenu de l'archive :
    avastack-<version>-windows/
        AVAStack.py, requirements.txt, veralux_core_headless.py, ...
        installer/install_avastack.ps1, installer/install_avastack.bat
        installer/common/avastack_setup.py
        LISEZMOI.txt
"""

import hashlib
import os
import re
import zipfile

MOTIF_VERSION = re.compile(r'^AVASTACK_VERSION\s*=\s*"([^"]+)"', re.M)
FICHIERS_RACINE = ("AVAStack.py", "requirements.txt", "veralux_core_headless.py")
# SDK binaires constructeurs embarqués sous Windows — LISTE NOMMÉE, recopiée
# d'`avastack.iss` (jamais un joker : un fichier inattendu ne part jamais).
SDK_DLLS = ("ASICamera2.dll", "PlayerOneCamera.dll", "ToupCam.dll",
            "SVBCameraSDK.dll")
# Bancs embarqués : les OUTILS DE DIAGNOSTIC MATÉRIEL caméra seulement
# (motif `_diag_*.py`), exactement comme `avastack.iss` et le packer Linux.
DOSSIER_CAMERAS = os.path.join("bancs", "cameras")
MOTIF_DIAG = "_diag_"
# Extensions interdites SAUF les DLL constructeurs nommées ci-dessus : les
# binaires Linux/macOS et les règles udev n'ont rien à faire dans un paquet
# Windows.
EXTENSIONS_INTERDITES = (".so", ".dylib", ".rules")
# Fichiers dont les fins de ligne doivent être CRLF dans le paquet Windows.
EXTENSIONS_CRLF = (".py", ".ps1", ".bat", ".txt")


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
    """→ [(chemin source, nom dans l'archive, présent ?)] dans l'ordre du paquet.

    Les DLL constructeurs sont retournées avec leur nom SEUL et peuvent être
    absentes de la machine de build (elles ne sont pas suivies par git) : le
    packer le DIT au lieu d'échouer, pour qu'un paquet sans caméras reste
    constructible — mais la liste des DLL réellement embarquées est annoncée.
    """
    entrees = []
    vus = set()

    def ajouter(source, arcname):
        if os.path.isfile(source) and arcname not in vus:
            vus.add(arcname)
            entrees.append((source, arcname, True))

    for nom in FICHIERS_RACINE:
        ajouter(os.path.join(racine, nom), nom)

    # Application : tous les .py du package, __pycache__ exclu.
    for dossier, sous, noms in os.walk(os.path.join(racine, "avastack")):
        sous[:] = [s for s in sous if s != "__pycache__"]
        for nom in sorted(noms):
            if nom.endswith(".py"):
                chemin = os.path.join(dossier, nom)
                ajouter(chemin, os.path.relpath(chemin, racine))

    # Bancs embarqués : les diagnostics matériel caméra (motif `_diag_`).
    dossier_cameras = os.path.join(racine, DOSSIER_CAMERAS)
    if os.path.isdir(dossier_cameras):
        for nom in sorted(os.listdir(dossier_cameras)):
            if nom.endswith(".py") and MOTIF_DIAG in nom:
                ajouter(os.path.join(dossier_cameras, nom),
                        "bancs/cameras/" + nom)

    # Installateur (script + lanceur double-clic + outil de venv + lisez-moi).
    ajouter(os.path.join(racine, "installer", "windows", "install_avastack.ps1"),
            "installer/install_avastack.ps1")
    ajouter(os.path.join(racine, "installer", "windows", "install_avastack.bat"),
            "installer/install_avastack.bat")
    ajouter(os.path.join(racine, "installer", "common", "avastack_setup.py"),
            "installer/common/avastack_setup.py")
    ajouter(os.path.join(racine, "installer", "windows", "LISEZMOI.txt"),
            "LISEZMOI.txt")

    # SDK binaires constructeurs : ajoutés par NOM, présents ou non.
    for nom in SDK_DLLS:
        source = os.path.join(racine, nom)
        entrees.append((source, nom, os.path.isfile(source)))

    return entrees


def lire_octets_crlf(source):
    """→ (octets normalisés en CRLF, converti ?) pour un fichier texte."""
    with open(source, "rb") as f:
        donnees = f.read()
    normalise = donnees.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    en_crlf = normalise.replace(b"\n", b"\r\n")
    return en_crlf, en_crlf != donnees


def construire(racine, version, dossier_sortie):
    """Écrit l'archive et renvoie (chemin, entrees, convertis, dlls, manquantes)."""
    nom_archive = "avastack-setup-%s-windows.zip" % version
    chemin = os.path.join(dossier_sortie, nom_archive)
    prefixe = "avastack-%s-windows" % version
    os.makedirs(dossier_sortie, exist_ok=True)
    entrees = fichiers_a_embarquer(racine)
    convertis = []
    embarquees = []
    manquantes = []
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as archive:
        for source, arcname, present in entrees:
            if not present:
                manquantes.append(arcname)
                continue
            bas = os.path.basename(arcname).lower()
            if any(bas.endswith(ext) for ext in EXTENSIONS_INTERDITES):
                raise SystemExit(
                    "ERREUR : binaire interdit dans le paquet Windows : " + arcname)
            donnees = None
            if arcname.lower().endswith(EXTENSIONS_CRLF):
                donnees, converti = lire_octets_crlf(source)
                if converti:
                    convertis.append(arcname)
            if donnees is None:
                with open(source, "rb") as f:
                    donnees = f.read()
            archive.writestr(prefixe + "/" + arcname, donnees)
            if bas.endswith(".dll"):
                embarquees.append(arcname)
    return chemin, entrees, convertis, embarquees, manquantes


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
    dossier_sortie = os.path.join(racine, "installer", "windows", "output")
    chemin, entrees, convertis, dlls, manquantes = construire(
        racine, version, dossier_sortie)
    total = sum(1 for _, _, present in entrees if present)
    print("Version lue : AVASTACK_VERSION = %s" % version)
    print("Fichiers embarques : %d" % total)
    print("SDK cameras embarques : %s" % (", ".join(dlls) if dlls else "AUCUN"))
    if manquantes:
        print("SDK cameras ABSENTS de la machine de build (non embarques) :")
        for nom in manquantes:
            print("    - %s" % nom)
        print("  -> le paquet ne contiendra PAS ces caméras : elles seront")
        print("     détectées absentes à l'ouverture d'une source caméra.")
        print("     Pour un paquet complet, place ces DLL à la racine du dépôt")
        print("     avant de relancer.")
    if convertis:
        print("Fins de ligne normalisees en CRLF : %s" % ", ".join(convertis))
    print("Artefact : %s" % chemin)
    print("Taille : %.0f Kio" % (os.path.getsize(chemin) / 1024.0))
    print("SHA-256 : %s" % empreinte(chemin))
    print("")
    print("Installation cote Windows :")
    print("    1. clic droit sur le .zip -> Extraire tout")
    print("    2. dans avastack-%s-windows, double-cliquer sur" % version)
    print("       installer\\install_avastack.bat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
