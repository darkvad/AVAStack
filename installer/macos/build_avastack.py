#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_avastack.py — paquet d'installation macOS pour AVAStack.

Construit `installer/macos/output/avastack-setup-<version>-macos.tar.gz` à
partir de `AVASTACK_VERSION` (`avastack/__init__.py`, source unique de vérité —
même règle que les installateurs Windows et Linux, cf. CLAUDE.md) : le nom de
l'artéfact PORTE la version, jamais un nom figé.

C'est le frère du packer LINUX (`installer/linux/build_avastack.py`) : MÊMES
règles de contenu et de fins de ligne, à trois différences près —
  ① l'installateur embarqué est `installer/macos/install_avastack.sh` (placé
     dans l'archive sous `installer/install_avastack.sh`) et le lisez-moi est
     `installer/macos/LISEZMOI.txt` ;
  ② le nom porte `-macos` (racine `avastack-<version>-macos/`) ;
  ③ rien d'autre : ni Python ni venv ni SDK dans l'archive (mêmes décisions de
     projet : les seuls bancs embarqués sont les OUTILS DE DIAGNOSTIC caméra,
     `bancs/cameras/_diag_*.py`).

Usage (Windows, Linux ou macOS — stdlib seulement) :
    python3 installer/macos/build_avastack.py
    python  installer\\macos\\build_avastack.py

L'archive contient un unique dossier racine `avastack-<version>-macos/` :
    tar xzf avastack-setup-<version>-macos.tar.gz
    cd avastack-<version>-macos
    bash installer/install_avastack.sh
"""

import hashlib
import io
import os
import re
import tarfile

MOTIF_VERSION = re.compile(r'^AVASTACK_VERSION\s*=\s*"([^"]+)"', re.M)
FICHIERS_RACINE = ("AVAStack.py", "requirements.txt", "veralux_core_headless.py")
DOSSIER_CAMERAS = os.path.join("bancs", "cameras")
MOTIF_DIAG = "_diag_"
EXTENSIONS_INTERDITES = (".so", ".dll", ".dylib", ".rules")
# Fichiers dont les fins de ligne DOIVENT être UNIX dans le paquet : un script
# shell en CRLF ne s'exécute pas (le dépôt vit sur Windows, core.autocrlf=true).
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
    """[(chemin source, nom dans l'archive, mode)] — même contenu que Linux."""
    entrees = []

    def ajouter(source, arcname):
        extension = os.path.splitext(arcname)[1].lower()
        if extension in EXTENSIONS_INTERDITES:
            raise SystemExit("ERREUR : %s est un binaire constructeur, "
                             "jamais embarqué." % arcname)
        entrees.append((source, arcname, MODES.get(extension, 0o644)))

    for nom in FICHIERS_RACINE:
        ajouter(os.path.join(racine, nom), nom)
    dossier_cameras = os.path.join(racine, DOSSIER_CAMERAS)
    if os.path.isdir(dossier_cameras):
        for nom in sorted(os.listdir(dossier_cameras)):
            if not nom.endswith(".py") or MOTIF_DIAG not in nom:
                continue
            ajouter(os.path.join(dossier_cameras, nom), "bancs/cameras/" + nom)
    for dossier, sous, noms in os.walk(os.path.join(racine, "avastack")):
        sous[:] = [s for s in sous if s != "__pycache__"]
        for nom in sorted(noms):
            if nom.endswith(".py"):
                chemin = os.path.join(dossier, nom)
                ajouter(chemin, os.path.relpath(chemin, racine))
    ajouter(os.path.join(racine, "installer", "macos", "install_avastack.sh"),
            "installer/install_avastack.sh")
    ajouter(os.path.join(racine, "installer", "common", "avastack_setup.py"),
            "installer/common/avastack_setup.py")
    ajouter(os.path.join(racine, "installer", "macos", "LISEZMOI.txt"),
            "LISEZMOI.txt")
    return entrees


def lire_octets(source, arcname):
    """(octets à archiver, converti en fins de ligne UNIX ?).

    Les scripts shell et les lisez-moi sont convertis : le dépôt Windows les
    écrit en CRLF, macOS/Linux ne savent pas exécuter un .sh en CRLF."""
    with open(source, "rb") as f:
        donnees = f.read()
    if arcname.endswith(EXTENSIONS_UNIX) and b"\r\n" in donnees:
        return donnees.replace(b"\r\n", b"\n"), True
    return donnees, False


def construire(racine, version, dossier_sortie):
    """Écrit l'archive et renvoie (chemin, entrées, fichiers convertis)."""
    nom_archive = "avastack-setup-%s-macos.tar.gz" % version
    chemin = os.path.join(dossier_sortie, nom_archive)
    prefixe = "avastack-%s-macos" % version
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
    dossier_sortie = os.path.join(racine, "installer", "macos", "output")
    chemin, entrees, convertis = construire(racine, version, dossier_sortie)
    print("Version lue : AVASTACK_VERSION = %s" % version)
    print("Fichiers embarques : %d" % len(entrees))
    if convertis:
        print("Fins de ligne converties en UNIX : %s" % ", ".join(convertis))
    print("Artefact : %s" % chemin)
    print("Taille : %.0f Kio" % (os.path.getsize(chemin) / 1024.0))
    print("SHA-256 : %s" % empreinte(chemin))
    print("")
    print("Installation cote macOS :")
    print("    tar xzf %s" % os.path.basename(chemin))
    print("    cd avastack-%s-macos" % version)
    print("    bash installer/install_avastack.sh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

