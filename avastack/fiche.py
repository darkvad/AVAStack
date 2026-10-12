# -*- coding: utf-8 -*-
"""FICHE DE RENDU — « que chaque image dise ce qu'elle a subi ».

POURQUOI CE MODULE (chantier ouvert le 11/10/2026, demande d'Alain) : un
fichier écrit par AVAStack ne disait PAS, de façon fiable, la chaîne qui
l'avait produit. Les mots-clés FITS n'existent que pour le FITS (un TIFF ou un
PNG n'en porte AUCUN), le « tel que vu » n'avait aucun en-tête, et l'on finissait
par DEVINER un réglage — soit depuis `config.json` (qui est l'état à la DERNIÈRE
FERMETURE, pas celui du moment où le fichier a été écrit), soit par une empreinte
mesurée. Le bug du 11/10/2026 (saturation bleue APPLIQUÉE à 3,0 mais AFFICHÉE à
1,00) est né de cet angle mort : rien ne disait ce qui était réellement appliqué.

La fiche est un fichier JSON COMPAGNON écrit à CÔTÉ de l'image, par le MÊME
thread qui écrit l'image :

    M33.fits  →  M33.ava.json

Rien n'entre dans le FITS : la linéarité des sorties reste intacte (règle du
projet). La fiche est le pendant MACHINE-LISIBLE et INDÉPENDANT DU FORMAT de
l'information de provenance : elle vaut pour FITS, TIFF et PNG.

Décisions d'Alain (11/10/2026, toutes validées) :
  ① nom et emplacement : `<image>.ava.json`, dans le MÊME dossier que l'image ;
  ② case à cocher dans l'interface, COCHÉE par défaut (clé `fiche_rendu`) ;
  ③ chemins COMPLETS dans le JSON (traçabilité maximale ; les EXEMPLES de la
     documentation publique, eux, restent neutres — dépôt PUBLIC) ;
  ④ écrite pour TOUTES les sorties (brut, traité linéaire, couches, tel que vu,
     résultat externe), avec un champ `type_sortie`.

Convention (celle du dépôt) : JAMAIS d'exception. Écrire une fiche est un
SERVICE, pas une étape du pipeline : une fiche ratée (disque plein, dossier
protégé…) ne doit JAMAIS faire échouer l'enregistrement de l'image. D'où
`ecrire()` qui rend un message d'erreur au lieu de lever, et l'écriture
ATOMIQUE (fichier temporaire puis remplacement) : un `M33.ava.json` n'est jamais
vu à moitié écrit.
"""

import json
import os
import platform
import subprocess
import sys
import time
from typing import Any

# Suffixe de la fiche. Il commence par un point et se TERMINE par `.json` : le
# nom dérivé (`M33.ava.json`) reste ainsi ouvrable par n'importe quel lecteur
# JSON, tout en restant reconnaissable et adjacent à `M33.fits`.
SUFFIXE = ".ava.json"

# Version du FORMAT de la fiche (indépendante de la version de l'application) :
# si la structure change un jour, un lecteur saura à quelle génération il a
# affaire.
FORMAT = 1

# Cache du commit git : calculé AU PLUS UNE FOIS par process (un sous-processus
# `git` à chaque enregistrement serait un coût inutile).
_COMMIT_CACHE: str | None = None


def chemin_fiche(chemin_image: str) -> str:
    """Chemin de la fiche COMPAGNON d'une image : `<image>.ava.json`.

    L'extension de l'image est retirée (`splitext`), pas seulement `.fits` :
    la même règle vaut pour TIFF et PNG."""
    base, _ext = os.path.splitext(chemin_image)
    return base + SUFFIXE


def _commit_git() -> str:
    """Commit git (court) du code qui tourne, ou "" si indisponible.

    BEST EFFORT, jamais d'exception : sous forme FIGÉE (l'installeur) il n'y a
    pas de `.git` ; sur une machine sans `git` la commande échoue. Dans les deux
    cas la fiche reste valable (la version de l'application suffit) — le commit
    n'est qu'un détail EN PLUS, utile en développement."""
    try:
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not os.path.isdir(os.path.join(racine, ".git")):
            return ""
        res = subprocess.run(["git", "-C", racine, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:                       # `git` absent, `.git` illisible…
        pass
    return ""


def _commit() -> str:
    """`_commit_git()` mis en cache (calcul au plus une fois par process)."""
    global _COMMIT_CACHE
    if _COMMIT_CACHE is None:
        _COMMIT_CACHE = _commit_git()
    return _COMMIT_CACHE


def horodatage() -> str:
    """Date/heure LOCALE de l'écriture, en ISO 8601 (lisible ET triable)."""
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def infos_application() -> dict[str, Any]:
    """Version de l'application, commit, Python et plateforme.

    Chaque élément est calculé dans son propre `try` : un environnement
    exotique ne doit pas empêcher d'écrire la fiche."""
    try:
        from . import AVASTACK_VERSION
        version = AVASTACK_VERSION
    except Exception:
        version = "?"
    d: dict[str, Any] = {"avastack": version, "commit": _commit()}
    try:
        d["python"] = sys.version.split()[0]
    except Exception:
        pass
    try:
        d["plateforme"] = platform.platform()
    except Exception:
        pass
    return d


def construire(chemin_image: str, type_sortie: str, image: Any = None,
               extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble le CONTENU de la fiche (sans l'écrire).

    - `chemin_image` : le fichier écrit (chemin COMPLET retenu, décision ③) ;
    - `type_sortie`  : « tel que vu (étiré) », « empilement brut (linéaire) »…
    - `image`        : le tableau écrit (on en relit les DIMENSIONS) ;
    - `extra`        : source, chaîne appliquée, état appliqué/affiché, en-tête
      FITS… — fourni par l'appelant, qui seul connaît le contexte du rendu.
    """
    contenu: dict[str, Any] = {
        "fiche": "rendu AVAStack",
        "format": FORMAT,
        "date": horodatage(),
        "application": infos_application(),
        "fichier": os.path.abspath(chemin_image),
        "type_sortie": str(type_sortie),
    }
    forme = getattr(image, "shape", None)
    if forme is not None:
        try:
            contenu["dimensions"] = [int(x) for x in forme]
        except Exception:
            pass
    if extra:
        contenu.update(extra)
    return contenu


def ecrire(chemin_image: str, contenu: dict[str, Any]) -> tuple[str | None, str]:
    """Écrit la fiche à côté de l'image, de façon ATOMIQUE et TOLÉRANTE.

    → `(chemin écrit, "")` en cas de succès ; `(None, message)` en cas d'échec
    (jamais d'exception : une fiche ratée n'échoue jamais l'enregistrement).

    ATOMIQUE : le JSON est d'abord écrit dans `<fiche>.part`, puis RENOMMÉ sur
    le nom final (`os.replace`, atomique sur le même volume). Un lecteur ne voit
    donc jamais un `.ava.json` tronqué."""
    chemin = chemin_fiche(chemin_image)
    provisoire = chemin + ".part"
    try:
        dossier = os.path.dirname(chemin)
        if dossier:
            os.makedirs(dossier, exist_ok=True)
        with open(provisoire, "w", encoding="utf-8") as f:
            json.dump(contenu, f, ensure_ascii=False, indent=1)
        os.replace(provisoire, chemin)
        return chemin, ""
    except OSError as exc:
        try:                                # ne pas laisser traîner un `.part`
            if os.path.exists(provisoire):
                os.remove(provisoire)
        except OSError:
            pass
        return None, str(exc)


def ecrire_fiche(chemin_image: str, type_sortie: str, image: Any = None,
                 extra: dict[str, Any] | None = None) -> tuple[str | None, str]:
    """Construit PUIS écrit la fiche compagnon (raccourci de l'appelant).

    Même contrat que `ecrire()` : jamais d'exception, message d'erreur rendu."""
    try:
        contenu = construire(chemin_image, type_sortie, image=image, extra=extra)
    except Exception as exc:                 # structure inattendue d'`extra`
        return None, f"{type(exc).__name__}: {exc}"
    return ecrire(chemin_image, contenu)
