# -*- coding: utf-8 -*-
"""Téléchargeur des catalogues Siril sur Zenodo (à froid, hors session).

ZENODO BLOQUE LES CLIENTS NUS (403 anti-robot, constaté le 22/09/2026
avec Invoke-WebRequest sans en-tête navigateur) : toutes les requêtes
partent avec des en-têtes navigateur complets.

Garanties :
  • REPRISE : une coupure réseau ne repart pas de zéro (Range/206) ;
  • INTÉGRITÉ : sha256 vérifié contre le .sha256sum officiel de Zenodo ;
  • AUCUNE SURPRISE : écrit en .part puis renommé — jamais de catalogue
    à moitié téléchargé qui passerait pour complet ;
  • fichier déjà présent et conforme → PAS de re-téléchargement.
"""

import hashlib
import os
import re
import shutil
import urllib.error
import urllib.request
import zipfile

# Les cinq catégories de la base SPCC sont définies UNE seule fois (spcc_db).
from .spcc_db import SOUS_DOSSIERS as CATEGORIES_SPCC

# Enregistrements Zenodo (vérifiés le 22/09/2026) :
RECORD_ASTRO = "14692304"      # Siril Astrometry Catalogue from Gaia DR3
RECORD_XPSAMP = "14738271"     # Siril Spectrophotometric Catalog (48 chunks)
NOM_ASTRO = "siril_cat_healpix8_astro.dat.bz2"
TOTAL_CHUNKS = 48              # morceaux de niveau 1 (0-47) du catalogue spectro

# Hôtes des données (constantes de module : un banc les redirige vers un
# serveur http local, ce qui teste le VRAI code — reprise, sha256, extraction —
# sans dépendre du réseau).
URL_ZENODO = "https://zenodo.org/records"

# Base de profils SPCC (jalon 77) : dépôt GitLab `siril-spcc-database` (GPLv3),
# archive ZIP téléchargeable SANS compte. Elle porte les courbes de réponse des
# capteurs, les transmissions de filtres et les références de blanc — sans elle,
# la SPCC exige un Siril installé ET une calibration lancée une fois.
# PIÈGE VÉRIFIÉ (29/09/2026) : l'API GitLab veut l'identifiant de projet ENCODÉ
# (`free-astro%2Fsiril-spcc-database`) ; la requête SANS `sha` suit la branche
# PAR DÉFAUT du dépôt (mesuré : 200, application/zip) — et non un nom de branche
# figé dans le code, qui casserait au premier renommage.
URL_SPCC = ("https://gitlab.com/api/v4/projects/"
            "free-astro%2Fsiril-spcc-database/repository/archive.zip")
NOM_ZIP_SPCC = "siril-spcc-database.zip"
GARDE_ZIP_SPCC = 512 << 20     # 512 Mo décompressés : au-delà, on refuse

_EN_TETES = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": "*/*",
}


def url_fichier(record, nom):
    return f"{URL_ZENODO}/{record}/files/{nom}?download=1"


def _requete(url, timeout=60):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=_EN_TETES), timeout=timeout)


def _requete_texte(url, timeout=60):
    with _requete(url, timeout) as rep:
        return rep.read().decode("utf-8", errors="replace")


def sha256_fichier(chemin, progression=None):
    """sha256 hex d'un fichier (lecture par blocs de 4 Mo)."""
    h = hashlib.sha256()
    taille = os.path.getsize(chemin)
    fait = 0
    with open(chemin, "rb") as f:
        while True:
            bloc = f.read(1 << 22)
            if not bloc:
                break
            h.update(bloc)
            fait += len(bloc)
            if progression:
                progression(fait / max(1, taille))
    return h.hexdigest()


def sommaire_zenodo(record, nom, timeout=60):
    """→ sha256 attendu du fichier `nom`, lu dans le .sha256sum officiel
    de l'enregistrement (quelques centaines d'octets, téléchargé à la
    volée). Lève RuntimeError si l'entrée est introuvable."""
    sums = _requete_texte(url_fichier(record, nom + ".sha256sum"), timeout)
    m = re.search(r"^([0-9a-f]{64})\s+\*?" + re.escape(nom) + r"\s*$",
                  sums, re.M)
    if not m:
        raise RuntimeError(f"liste de sommes Zenodo sans entrée pour {nom}")
    return m.group(1)


def telecharger(url, dest, progression=None, timeout=60):
    """Télécharge url → dest (reprise par Range si un .part existe).
    → taille finale. Lève RuntimeError avec un message clair sinon."""
    part = dest + ".part"
    deja = os.path.getsize(part) if os.path.isfile(part) else 0
    try:
        tete = dict(_EN_TETES)
        if deja:
            tete["Range"] = f"bytes={deja}-"
        rep = urllib.request.urlopen(
            urllib.request.Request(url, headers=tete), timeout=timeout)
    except urllib.error.HTTPError as exc:
        if deja and exc.code == 416:      # .part déjà complet ?
            os.replace(part, dest)
            return os.path.getsize(dest)
        raise RuntimeError(f"téléchargement impossible (HTTP {exc.code}) "
                           "— réseau ou Zenodo indisponible") from exc
    except Exception as exc:
        raise RuntimeError(f"téléchargement impossible ({exc}) — réseau "
                           "indisponible ?") from exc
    with rep:
        status = getattr(rep, "status", 200)
        if deja and status != 206:
            deja = 0            # serveur qui ignore Range : on repart de zéro
        total = int(rep.headers.get("Content-Length") or 0) + deja
        fait = deja
        with open(part, "ab" if deja else "wb") as f:
            while True:
                bloc = rep.read(1 << 20)
                if not bloc:
                    break
                f.write(bloc)
                fait += len(bloc)
                if progression:
                    progression(fait / max(1, total or fait))
    if total and os.path.getsize(part) != total:
        raise RuntimeError(f"taille reçue ({os.path.getsize(part)} o) ≠ "
                           f"annoncée ({total} o) — fichier incomplet")
    os.replace(part, dest)
    return os.path.getsize(dest)


def verifier_ou_telecharger(dossier, nom, record, progression=None,
                            somme_attendue=None):
    """Assure la présence de `nom` dans `dossier`, sha256 conforme.
    → (chemin, telecharge: bool). Ne retélécharge PAS un fichier conforme ;
    retélécharge un fichier corrompu ; reprend un .part interrompu."""
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, nom)
    if os.path.isfile(chemin):
        if somme_attendue is None or sha256_fichier(chemin) == somme_attendue:
            return chemin, False
        os.remove(chemin)            # corrompu : on repart propre
    def prog(fraction):
        if progression:
            progression(nom, fraction)
    telecharger(url_fichier(record, nom), chemin, progression=prog)
    if somme_attendue is not None:
        if sha256_fichier(chemin) != somme_attendue:
            os.remove(chemin)
            raise RuntimeError(f"sha256 de {nom} non conforme après "
                               "téléchargement — fichier supprimé, "
                               "à retélécharger")
    return chemin, True


def telecharger_catalogue_astro(dossier, progression=None):
    """Télécharge le catalogue astrométrique Gaia DR3 de Siril dans
    `dossier` (1,1 Go compressé). → (chemin, telecharge: bool).
    `progression(nom, fraction)` est appelée régulièrement."""
    somme = sommaire_zenodo(RECORD_ASTRO, NOM_ASTRO)
    return verifier_ou_telecharger(dossier, NOM_ASTRO, RECORD_ASTRO,
                                   progression, somme)


def nom_chunk(chunk):
    """Nom (côté Zenodo) d'un morceau du catalogue spectrophotométrique.
    Le numéro final est le pixel HEALpix de NIVEAU 1 couvert (0–47)."""
    return f"siril_cat1_healpix8_xpsamp_{int(chunk)}.dat.bz2"


def chunks_du_champ(ra, dec, rayon_deg):
    """Numéros des morceaux (0–47) couvrant le disque (ra, dec, rayon_deg).

    POURQUOI CE CALCUL (et pas « prenez les 48 ») : l'ensemble pèse ≈ 10,6 Go
    compressés. Un champ tient dans UN à QUATRE morceaux de niveau 1 (un morceau
    = 4 096 pixels de niveau 8, soit 0,229° de côté chacun) : c'est ce que fait
    le script de Siril, et c'est ici 100 à 300 Mo au lieu de 10,6 Go. Le calcul
    passe par les MÊMES fonctions HEALpix que la lecture des catalogues
    (`pixels_cone` → `pixel_vers_chunk`) : une seule géométrie dans le projet.

    → liste TRIÉE de numéros (vide si les coordonnées sont inexploitables)."""
    from .healpix import pixel_vers_chunk, pixels_cone
    pix = pixels_cone(float(ra), float(dec), float(rayon_deg))
    return sorted({int(c) for c in pixel_vers_chunk(pix)})


def telecharger_chunks(dossier, chunks, progression=None):
    """Télécharge les morceaux `chunks` du catalogue spectrophotométrique.

    Chaque morceau a SON `.sha256sum` sur Zenodo (vérifié ici, comme pour le
    catalogue astrométrique) et un morceau déjà conforme n'est PAS
    retéléchargé : on peut rappeler la fonction pour compléter un champ voisin
    sans repayer ce qui est déjà là.

    `progression(nom, fraction)` est appelée fichier par fichier.
    → liste [(chunk, chemin, telecharge: bool)] dans l'ordre croissant.
    Une erreur (réseau, sha256) INTERROMPT la série : les morceaux déjà
    téléchargés restent en place, un nouvel appel reprend où l'on s'est arrêté.
    """
    out = []
    for n in sorted({int(c) for c in chunks}):
        # `progression` est déjà de la forme (nom, fraction) — celle de
        # `verifier_ou_telecharger` : aucune adaptation, donc aucun risque
        # d'inverser les deux arguments (le nom du morceau dit lequel avance).
        chemin, tele = telecharger_chunk_xpsamp(dossier, n, progression)
        out.append((n, chemin, tele))
    return out


def telecharger_tous_les_chunks(dossier, progression=None):
    """Les 48 morceaux (≈ 10,6 Go compressés) — pour un usage itinérant : tout
    le ciel disponible hors ligne. → même forme que `telecharger_chunks`."""
    return telecharger_chunks(dossier, range(TOTAL_CHUNKS), progression)


def telecharger_chunk_xpsamp(dossier, chunk, progression=None):
    """Télécharge UN morceau du catalogue spectrophotométrique (niveau 1,
    0–47), sha256 vérifié. → (chemin, telecharge: bool)."""
    nom = nom_chunk(chunk)
    somme = sommaire_zenodo(RECORD_XPSAMP, nom)
    return verifier_ou_telecharger(dossier, nom, RECORD_XPSAMP,
                                   progression, somme)


def etat_local(dossier):
    """→ dict d'état des catalogues sous `dossier` (pour l'UI) :
    {'dossier': dossier, 'astro': chemin ou None, 'chunks': {n: chemin}}.
    Scanne la racine ET les sous-dossiers (Siril range les chunks dans
    `siril_cat1_healpix8_xpsamp/`). Le catalogue astro peut être en .dat
    (cache décompressé) ou .bz2."""
    etat = {"dossier": dossier, "astro": None, "chunks": {}}
    if not dossier or not os.path.isdir(dossier):
        return etat
    racines = [dossier]
    try:
        racines += [os.path.join(dossier, n)
                    for n in sorted(os.listdir(dossier))
                    if os.path.isdir(os.path.join(dossier, n))]
    except OSError:
        pass
    for racine in racines:
        try:
            noms = os.listdir(racine)
        except OSError:
            continue
        if etat["astro"] is None:
            bz2_astro = os.path.join(racine, NOM_ASTRO)
            dat_astro = bz2_astro[:-4]
            if os.path.isfile(dat_astro):
                etat["astro"] = dat_astro
            elif os.path.isfile(bz2_astro):
                etat["astro"] = bz2_astro
        for nom in noms:
            m = re.match(r"^siril_cat1_healpix8_xpsamp_(\d+)\.dat(\.bz2)?$",
                         nom)
            if m:
                n = int(m.group(1))
                etat["chunks"].setdefault(n, os.path.join(racine, nom))
    return etat


# --------------------------------------------------------------------------
# Base de profils SPCC (jalon 77) : plus besoin de Siril pour les courbes de
# capteur, de filtre et de référence de blanc — l'archive du dépôt GitLab est
# téléchargée, son intégrité est vérifiée (ZIP lisible, catégories présentes),
# puis elle est extraite dans le dossier SPCC choisi par l'utilisateur.
# --------------------------------------------------------------------------
def _relatif_archive(nom_dans_zip):
    """Chemin relatif d'une entrée de ZIP, SANS son dossier racine (les
    archives GitLab enveloppent tout dans `<projet>-<ref>`), ou None pour ce
    qu'on ne garde pas (hors des cinq catégories, ou .json de la racine)."""
    morceaux = [m for m in str(nom_dans_zip).replace("\\", "/").split("/") if m]
    if len(morceaux) < 2:                     # une racine seule : rien à poser
        return None
    rel = morceaux[1:]
    if os.pardir in rel:
        raise RuntimeError(f"archive SPCC : chemin suspect ({nom_dans_zip})")
    garder = rel[0] in CATEGORIES_SPCC or (
        len(rel) == 1 and rel[0].lower().endswith(".json"))
    return "/".join(rel) if garder else None


def extraire_zip_spcc(zip_path, dossier, progression=None):
    """Extrait dans `dossier` une archive de la base SPCC → nombre de fichiers
    posés.

    Ordre volontaire (règle « aucune surprise ») : ① intégrité du ZIP (tout
    est lu dans un dossier TEMPORAIRE, rien n'est posé si l'archive est
    refusée) ; ② mise en place fichier par fichier — une base déjà installée
    reste utilisable pendant la copie ; ③ le temporaire disparaît toujours."""
    with zipfile.ZipFile(zip_path) as zf:
        defaut = zf.testzip()
        if defaut is not None:
            raise RuntimeError("archive SPCC corrompue (premier fichier en "
                               f"défaut : {defaut}) — à retélécharger")
        entrees = [i for i in zf.infolist() if not i.is_dir()]
        total = sum(int(i.file_size) for i in entrees)
        if total > GARDE_ZIP_SPCC:
            raise RuntimeError(f"archive SPCC anormalement grosse "
                               f"({total} o décompressés) — refusée")
        tmp = dossier + ".extraction"
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp, exist_ok=True)
        poses = 0
        try:
            for i, inf in enumerate(entrees):
                rel = _relatif_archive(inf.filename)
                if progression:
                    progression(inf.filename or "archive SPCC",
                                (i + 1) / max(1, len(entrees)))
                if rel is None:
                    continue
                cible = os.path.join(tmp, *rel.split("/"))
                if os.path.relpath(cible, tmp).startswith(os.pardir):
                    raise RuntimeError("archive SPCC : chemin hors dossier "
                                       f"({inf.filename})")
                os.makedirs(os.path.dirname(cible), exist_ok=True)
                with zf.open(inf) as src, open(cible, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            for racine, _dirs, noms in os.walk(tmp):
                for nom in noms:
                    src = os.path.join(racine, nom)
                    dst = os.path.join(dossier, os.path.relpath(src, tmp))
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    os.replace(src, dst)
                    poses += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return poses


def telecharger_base_spcc(dossier, progression=None):
    """Assure la base de profils SPCC (capteurs, filtres, références de blanc)
    dans `dossier`. → (dossier, nb_fichiers, telecharge: bool).

    Base complète déjà là → RIEN n'est téléchargé (re-cliquer est sans effet).
    L'archive (quelques Mo) n'est supprimée qu'APRÈS une extraction réussie :
    un transfert coupé laisse son `.part` et REPREND au prochain appel."""
    from .spcc_db import base_complete

    os.makedirs(dossier, exist_ok=True)
    if base_complete(dossier):
        return dossier, 0, False
    zip_path = os.path.join(dossier, NOM_ZIP_SPCC)
    # `telecharger` annonce `progression(fraction)` ; la convention du module est
    # `progression(nom, fraction)` — on l'adapte ICI, une seule fois.
    def prog(fraction):
        if progression:
            progression(NOM_ZIP_SPCC, fraction)

    telecharger(URL_SPCC, zip_path, progression=prog)
    poses = extraire_zip_spcc(zip_path, dossier, progression)
    try:
        os.remove(zip_path)          # la base est extraite : le ZIP ne sert plus
    except OSError:
        pass
    if not base_complete(dossier):
        raise RuntimeError("archive SPCC extraite mais base INCOMPLÈTE (une "
                           "des cinq catégories manque ou est vide) — "
                           "relancer le téléchargement")
    return dossier, poses, True


def etat_base_spcc(dossier=None):
    """Nombre de profils par catégorie de la base SPCC retenue (dict vide si
    aucune) — pour l'affichage, jamais une supposition."""
    from .spcc_db import resume_base
    return resume_base(dossier)
