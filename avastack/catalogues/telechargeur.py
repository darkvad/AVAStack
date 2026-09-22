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
import urllib.error
import urllib.request

# Enregistrements Zenodo (vérifiés le 22/09/2026) :
RECORD_ASTRO = "14692304"      # Siril Astrometry Catalogue from Gaia DR3
RECORD_XPSAMP = "14738271"     # Siril Spectrophotometric Catalog (48 chunks)
NOM_ASTRO = "siril_cat_healpix8_astro.dat.bz2"

_EN_TETES = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": "*/*",
}


def url_fichier(record, nom):
    return f"https://zenodo.org/records/{record}/files/{nom}?download=1"


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


def telecharger_chunk_xpsamp(dossier, chunk, progression=None):
    """Télécharge UN chunk du catalogue spectrophotométrique (niveau 1,
    0–47). → (chemin, telecharge: bool)."""
    nom = f"siril_cat1_healpix8_xpsamp_{int(chunk)}.dat.bz2"
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