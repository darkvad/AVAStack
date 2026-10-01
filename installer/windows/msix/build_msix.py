#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_msix.py — paquet MSIX (Microsoft Store) pour AVAStack.

POURQUOI CE PAQUET (chantier « Microsoft Store », jalon 92, 02/10/2026) : le
Store distribue des MSIX, et un MSIX est IMMUABLE (fichiers en LECTURE SEULE) :
le venv ne peut donc plus être créé à l'installation — l'application doit être
GELÉE au préalable. Ce packer EMBALLE donc le paquet gelé produit par
`build_avastack_frozen.ps1` (application PyInstaller + les 4 DLL) dans un MSIX.

Ce script ne fait que la partie BUILD (déterministe, testable) : préparation du
dossier de staging, écriture de `AppxManifest.xml` (depuis le modèle .template),
génération des VIGNETTES, puis appel de `MakeAppx.exe` (Windows SDK). La
SIGNATURE (certificat auto-signé pour un essai local) vit dans
`signer_msix.ps1` : un `.msix` NON SIGNÉ se construit, mais NE S'INSTALLE PAS.

Identité : pour un ESSAI LOCAL, `Name`/`Publisher` peuvent être quelconques
(le `Publisher` doit être le SUJET EXACT du certificat qui signe). POUR LE
STORE, ils doivent être EXACTEMENT ceux de Partner Center → ils sont donc
passés en paramètres, jamais figés.

Usage (Windows) :
    python installer/windows/msix/build_msix.py
    python installer/windows/msix/build_msix.py --nom 1234MonCompte.AVAStack \
        --publisher "CN=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
"""
import argparse
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import zlib

# --- Création de référence : le nom de l'artéfact PORTE la version ------------
MOTIF_VERSION = re.compile(r'^AVASTACK_VERSION\s*=\s*"([^"]+)"', re.M)
# Identité par DÉFAUT = celle d'un ESSAI LOCAL (jamais le Store).
NOM_DEFAUT = "AVAStack"
PUBLISHER_DEFAUT = "CN=AVAStack Test"
AFFICHE_PUBLISHER_DEFAUT = "AVAStack"
DESCRIPTION_DEFAUT = ("Live stacking : empilement des brutes en temps réel "
                      "pendant l'acquisition.")
EXE_DEFAUT = "AVAStack.exe"

# --- Vignettes (placeholder d'essai ; à REMPLACER pour le Store) -------------
FOND = (0x1B, 0x2A, 0x4A)       # bleu nuit
BORD = (0x5C, 0x8A, 0xC8)       # bleu clair
MARQUE = (0xFF, 0xFF, 0xFF)     # blanc
VIGNETTES = (("StoreLogo.png", 50),
             ("Square44x44Logo.png", 44),
             ("Square150x150Logo.png", 150))


# ============================================================ outils externes
def racine_depot(depart):
    """Racine du dépôt (celle qui porte `AVAStack.py`), depuis un fichier."""
    chemin = os.path.abspath(depart)
    while True:
        if os.path.isfile(os.path.join(chemin, "AVAStack.py")):
            return chemin
        parent = os.path.dirname(chemin)
        if parent == chemin:
            raise SystemExit("Racine du depot introuvable (AVAStack.py).")
        chemin = parent


def lire_version(racine):
    """AVASTACK_VERSION depuis `avastack/__init__.py` (source unique)."""
    with open(os.path.join(racine, "avastack", "__init__.py"),
              encoding="utf-8") as f:
        corresp = MOTIF_VERSION.search(f.read())
    if not corresp:
        raise SystemExit("AVASTACK_VERSION introuvable.")
    return corresp.group(1)


def version_msix(version):
    """« 2.49.0 » → « 2.49.0.0 » (MSIX exige QUATRE nombres, chacun 0–65535)."""
    nombres = [int(n) for n in re.findall(r"\d+", version)][:4]
    while len(nombres) < 4:
        nombres.append(0)
    return ".".join(str(max(0, min(65535, n))) for n in nombres)


def trouver_outil(nom):
    """Chemin de `MakeAppx.exe`/`signtool.exe` : PATH, sinon Windows SDK.

    Le SDK range ses outils par version sous ...\\Windows Kits\\10\\bin\\<ver>\\
    x64\\ : on prend la version la PLUS RÉCENTE (le tri lexicographique ferait
    passer 10.0.9999 pour plus récent que 10.0.26100 → tri par NOMBRES)."""
    dans_path = shutil.which(nom)
    if dans_path:
        return dans_path
    trouves = []
    for racine in (r"C:\Program Files (x86)\Windows Kits\10\bin",
                   r"C:\Program Files\Windows Kits\10\bin"):
        if not os.path.isdir(racine):
            continue
        for version in os.listdir(racine):
            candidat = os.path.join(racine, version, "x64", nom)
            if os.path.isfile(candidat):
                nombres = [int(n) for n in re.findall(r"\d+", version)] or [0]
                trouves.append((nombres, candidat))
    if trouves:
        trouves.sort(key=lambda t: t[0])
        return trouves[-1][1]
    secours = os.path.join(r"C:\Program Files (x86)\Windows Kits\10",
                           "App Certification Kit", nom)
    return secours if os.path.isfile(secours) else None


# ============================================================ vignettes (PNG)
def _bloc_png(typ, donnees):
    return (struct.pack(">I", len(donnees)) + typ + donnees
            + struct.pack(">I", zlib.crc32(typ + donnees) & 0xFFFFFFFF))


def _png_carre(cote):
    """PNG RGBA carré, code SANS dépendance (zlib + struct de la stdlib).

    Motif d'essai : bordure claire + losange central (à remplacer au Store)."""
    centre = (cote - 1) / 2.0
    rayon = max(2.0, cote * 0.18)
    marge = max(1.0, cote * 0.06)
    lignes = []
    for y in range(cote):
        ligne = bytearray()
        for x in range(cote):
            if x < marge or y < marge or x >= cote - marge or y >= cote - marge:
                couleur = BORD
            else:
                couleur = FOND
            if abs(x - centre) + abs(y - centre) <= rayon:
                couleur = MARQUE
            ligne += bytes((couleur[0], couleur[1], couleur[2], 255))
        lignes.append(bytes(ligne))
    ihdr = struct.pack(">IIBBBBB", cote, cote, 8, 6, 0, 0, 0)
    brut = b"".join(b"\x00" + ligne for ligne in lignes)   # filtre 0 par ligne
    return (b"\x89PNG\r\n\x1a\n" + _bloc_png(b"IHDR", ihdr)
            + _bloc_png(b"IDAT", zlib.compress(brut, 9))
            + _bloc_png(b"IEND", b""))


def faire_vignettes(dossier):
    """Écrit les vignettes exigées par le manifeste dans `dossier`."""
    os.makedirs(dossier, exist_ok=True)
    for nom, cote in VIGNETTES:
        with open(os.path.join(dossier, nom), "wb") as f:
            f.write(_png_carre(cote))


# ============================================================ staging + pack
def ecrire_manifeste(staging, gabarit, remplacements):
    """Écrit `AppxManifest.xml` à la racine du staging (jetons remplacés)."""
    with open(gabarit, encoding="utf-8") as f:
        xml = f.read()
    for jeton, valeur in remplacements.items():
        if jeton not in xml:
            raise SystemExit("Jeton %s absent du modele de manifeste." % jeton)
        xml = xml.replace(jeton, valeur)
    sortie = os.path.join(staging, "AppxManifest.xml")
    with open(sortie, "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    return sortie


def preparer_staging(package, staging, gabarit, remplacements):
    """Staging = copie du paquet GELÉ + manifeste + vignettes."""
    if not os.path.isfile(os.path.join(package, EXE_DEFAUT)):
        raise SystemExit(
            "Paquet gele introuvable : %s\n"
            "-> construis-le d'abord : powershell -File "
            "installer/windows/build_avastack_frozen.ps1"
            % os.path.join(package, EXE_DEFAUT))
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    shutil.copytree(package, staging)
    faire_vignettes(os.path.join(staging, "Assets"))
    return ecrire_manifeste(staging, gabarit, remplacements)


def empaqueter(makeappx, staging, destination):
    """Appelle `MakeAppx.exe pack` → (code, sortie)."""
    cmd = [makeappx, "pack", "/d", staging, "/p", destination, "/o"]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def empreinte(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def principal():
    ici = os.path.dirname(os.path.abspath(__file__))
    racine = racine_depot(ici)
    version = lire_version(racine)
    dossier_sortie = os.path.join(racine, "installer", "windows", "output")
    defaut_paquet = os.path.join(
        dossier_sortie, "avastack-frozen-%s-windows" % version)

    p = argparse.ArgumentParser(description="Paquet MSIX AVAStack (build).")
    p.add_argument("--package", default=defaut_paquet,
                   help="dossier du paquet GELE (build_avastack_frozen.ps1)")
    p.add_argument("--sortie", default=None,
                   help="chemin du .msix "
                        "(defaut : output/avastack-<v>-windows.msix)")
    p.add_argument("--nom", default=NOM_DEFAUT, help="Identity Name")
    p.add_argument("--publisher", default=PUBLISHER_DEFAUT,
                   help="Identity Publisher (= sujet du certificat signataire)")
    p.add_argument("--publisher-display", default=AFFICHE_PUBLISHER_DEFAUT)
    p.add_argument("--affiche", default=NOM_DEFAUT, help="DisplayName")
    p.add_argument("--description", default=DESCRIPTION_DEFAUT)
    p.add_argument("--exe", default=EXE_DEFAUT)
    p.add_argument("--garder-staging", action="store_true",
                   help="conserve le dossier de staging (diagnostic)")
    args = p.parse_args()

    destination = args.sortie or os.path.join(
        dossier_sortie, "avastack-%s-windows.msix" % version)
    staging = os.path.join(dossier_sortie, "msix_staging")
    gabarit = os.path.join(ici, "AppxManifest.xml.template")

    makeappx = trouver_outil("makeappx.exe")
    if not makeappx:
        print("ERREUR : MakeAppx.exe introuvable.", file=sys.stderr)
        print("  Il vient du Windows SDK, composant « Windows SDK pour "
              "applications Windows » :", file=sys.stderr)
        print("  https://developer.microsoft.com/windows/downloads/windows-sdk/",
              file=sys.stderr)
        return 1

    remplacements = {
        "__NAME__": args.nom,
        "__PUBLISHER__": args.publisher,
        "__VERSION__": version_msix(version),
        "__DISPLAY_NAME__": args.affiche,
        "__PUBLISHER_DISPLAY__": args.publisher_display,
        "__DESCRIPTION__": args.description,
        "__EXE__": args.exe,
    }

    print("Version lue : AVASTACK_VERSION = %s  (MSIX %s)"
          % (version, version_msix(version)))
    print("MakeAppx    : %s" % makeappx)
    print("Paquet gele : %s" % args.package)
    print("Identite    : Name=%s  Publisher=%s" % (args.nom, args.publisher))

    os.makedirs(dossier_sortie, exist_ok=True)
    if os.path.exists(destination):
        os.remove(destination)
    manifeste = preparer_staging(args.package, staging, gabarit, remplacements)
    print("Manifeste   : %s" % manifeste)

    code, sortie = empaqueter(makeappx, staging, destination)
    if not args.garder_staging:
        shutil.rmtree(staging, ignore_errors=True)
    if code != 0 or not os.path.isfile(destination):
        print("ERREUR : MakeAppx a echoue (code %s)" % code, file=sys.stderr)
        print(sortie, file=sys.stderr)
        return code or 1

    print("")
    print("OK - MSIX (NON SIGNE) : %s" % destination)
    print("     taille  : %.1f Mo"
          % (os.path.getsize(destination) / 1048576.0))
    print("     SHA-256 : %s" % empreinte(destination))
    print("")
    print("Etape suivante - SIGNER (sans signature, Windows REFUSE "
          "l'installation) :")
    print("     powershell -NoProfile -ExecutionPolicy Bypass -File "
          "installer\\windows\\msix\\signer_msix.ps1 -Msix \"%s\""
          % destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())