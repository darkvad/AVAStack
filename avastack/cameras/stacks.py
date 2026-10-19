# -*- coding: utf-8 -*-
"""Source « Stacks (fichiers FITS) » — P6, lot 5 des améliorations d'usage.

BUT (liste d'Alain du 19/10/2026) : pouvoir tester tout l'aval d'AVAStack
(astrométrie, Gaia, SPCC, fusion Ha, sauvegardes…) SANS réempiler les brutes —
on fournit des empilements DÉJÀ faits, un fichier par filtre voulu.

TROIS RÈGLES NON NÉGOCIABLES, écrites ici parce qu'elles sont le contrat :

1. **Ce sont des FICHIERS, pas un dossier.** Chaque ligne est un couple
   « rôle → fichier » ; les fichiers peuvent venir de dossiers différents (un
   stack peut sortir de Siril, PixInsight, ASTAP…). `NB_LIGNES_COMPO` (5)
   lignes au maximum, comme la composition multi-dossiers.

2. **Le RÔLE est celui que l'utilisateur INDIQUE, jamais un rôle deviné.**
   `canal_<rôle>.fit` n'est PAS un contrat (c'est le nom que NOTRE sauvegarde
   par canal donne, rien de plus) ; le mot-clé FITS `FILTER` n'est pas un
   contrat non plus (un stack peut être un composite de plusieurs filtres) et
   `AVAFRAME` n'est JAMAIS lu : on ne connaît pas la profondeur d'un empilement
   fourni, donc on n'en invente aucune. Un `FILTER` qui contredit le rôle est un
   simple AVERTISSEMENT (le choix de l'utilisateur fait foi).

3. **Un empilement fourni est déjà empilé** : la calibration (dark/flat) est
   sans objet et l'appelant la court-circuite ; chaque fichier est lu UNE fois
   par session (`relire()` remet le curseur au début pour une nouvelle
   session) ; la profondeur est réputée suffisante (seuil de profondeur forcé
   à 1 côté worker), sinon `astrometrie.ASTRO_MIN_FRAMES` bloquerait toutes les
   mesures sur un fichier unique.

LINÉARITÉ — refus seulement sur une PREUVE, avertissement sur une MESURE :
  - si notre propre en-tête (`AVAVUE`) dit que le fichier est ÉTIRÉ, `open()`
    refuse avec un message qui dit quoi faire (reprendre la version linéaire) :
    un étirement ne se défait pas ;
  - sinon (fichier venu d'ailleurs, aucun en-tête AVAStack) le fichier est
    ACCEPTÉ et, à la lecture, un avertissement MESURÉ (fond médian, plage,
    part de pixels saturés) est consigné — jamais un refus sur une supposition.

`read()` suit le contrat de `MultiFolderCamera` : `(image, rôle)` quand
PLUSIEURS fichiers sont fournis (le worker empile par rôle), et l'image SEULE
avec un fichier unique (empilement direct, « Mono »). `CameraBase` documente
l'écart assumé.

Banc : `bancs/_test_lot5_p6_stacks.py`.
"""

import os
import re
from typing import Any

import numpy as np

from .base import CameraBase
from ..images import FITS_OK, load_image

try:                                   # même garde que `avastack.images`
    from astropy.io import fits
except ImportError:                    # pragma: no cover — dépendance optionnelle
    fits = None                        # type: ignore[assignment]

EXT_FITS = (".fits", ".fit", ".fts")

# Mot-clé de NOTRE application qui décrit la nature du fichier (`saver.py`) :
# « resultat du traitement externe (LINEAIRE, avant etirement) », « resultat
# traite externe, tel que vu (ETIRE) », etc. C'est la SEULE preuve de
# non-linéarité acceptée — un fichier tiers n'en a pas et n'est donc jamais
# refusé pour cette raison.
CLE_VUE = "AVAVUE"

# « ETIRE » comme MOT (jamais « ETIREMENT » — l'en-tête linéaire de nos
# sorties externes contient « avant etirement » !). « TEL QUE VU » sans
# précision de linéarité est l'autre formulation d'un rendu étiré.
_MOTIF_ETIRE = re.compile(r"\bETIRE\b")
_MOTIF_VUE = re.compile(r"\bTEL QUE VU\b")

# --- Seuils de l'AVERTISSEMENT de linéarité (mesurés, jamais un refus) ------
# Un empilement LINÉAIRE a un fond très bas (quelques pour cent) et peu de
# pixels collés à 1 ; un rendu étiré a un fond haut et/ou un écrêtage massif.
# Ces bornes ne servent qu'à ÉCRIRE un avertissement dans le journal.
SEUIL_FOND_ETIRE: float = 0.12
SEUIL_SATURE: float = 0.01



def entete_avastack(chemin: str) -> dict[str, Any]:
    """Mots-clés AVAStack utiles d'un FITS : `{"AVAVUE": "…"}` ou `{}` (fichier
    non FITS, mot-clé absent, astropy absent, en-tête illisible). Jamais
    d'exception : cette lecture ne doit jamais empêcher d'ouvrir une source."""
    if (not FITS_OK or fits is None
            or not str(chemin).lower().endswith(EXT_FITS)):
        return {}
    try:
        with fits.open(chemin) as hd:
            entete = hd[0].header            # pyright: ignore[reportAttributeAccessIssue]
            valeur = entete.get(CLE_VUE)
    except Exception:
        return {}
    if valeur is None:
        return {}
    return {CLE_VUE: str(valeur)}


def dit_etire(entete: dict[str, Any]) -> bool:
    """True si l'en-tête AVAStack DIT que l'image est étirée (preuve, pas
    supposition) — cf. `_MOTIF_ETIRE` / `_MOTIF_VUE`."""
    txt = str(entete.get(CLE_VUE, "") or "").upper()
    if not txt:
        return False
    return bool(_MOTIF_ETIRE.search(txt) or _MOTIF_VUE.search(txt))


def avertissement_lineaire(chemin: str, img: Any) -> str | None:
    """Avertissement MESURÉ sur la linéarité d'un fichier SANS en-tête
    AVAStack, ou None si rien d'anormal.

    Mesures : fond MÉDIAN, plage (min/max) et part de pixels au plafond. Le
    fichier n'est JAMAIS refusé sur cette base — il est utilisé tel quel et le
    journal dit ce qui a été vu (même esprit que le message « profondeur non
    vérifiée » : on ne prétend pas savoir)."""
    if entete_avastack(chemin):
        return None                      # notre en-tête répond (refus en amont)
    try:
        a = np.asarray(img, dtype=np.float32)
    except Exception:
        return None
    if a.size == 0:
        return None
    fond = float(np.median(a))
    haut = float(np.max(a))
    sat = float(np.mean(a >= 0.999)) if haut > 0 else 0.0
    if fond <= SEUIL_FOND_ETIRE and sat <= SEUIL_SATURE:
        return None
    return (f"« {os.path.basename(chemin)} » : fond médian {fond:.3f}, "
            f"{sat * 100.0:.1f} % de pixels à 1,00, plage "
            f"{float(np.min(a)):.3f}–{haut:.3f} — probablement DÉJÀ ÉTIRÉ "
            "(aucun en-tête AVAStack dans ce fichier). Il est utilisé tel "
            "quel : vérifiez que c'est bien la version LINÉAIRE.")


class StackFilesCamera(CameraBase):
    """Source « Stacks (fichiers FITS) » : N fichiers choisis, un rôle chacun.

    `roles_fichiers` : liste de couples (rôle, chemin), 1 à
    `composition.NB_LIGNES_COMPO`. Le rôle est celui INDIQUÉ (jamais déduit du
    nom ni de l'en-tête) ; les fichiers peuvent venir de dossiers différents.
    """

    def __init__(self, roles_fichiers: Any) -> None:
        paires = [(str(r).strip(), str(f).strip())
                  for r, f in roles_fichiers]
        paires = [(r, f) for r, f in paires if r and f]
        if not paires:
            raise RuntimeError(
                "Stacks : choisissez au moins un rôle et son fichier")
        self.apparies: list[tuple[str, str]] = [
            (role, os.path.abspath(os.path.expanduser(chemin)))
            for role, chemin in paires]
        self.roles: list[str] = [r for r, _ in self.apparies]
        self.fichiers: list[str] = [f for _, f in self.apparies]
        # UN seul fichier = empilement DIRECT (le rôle ne compose rien) ; à
        # partir de deux, `read()` rend (image, rôle) comme une composition.
        self.par_roles: bool = len(self.apparies) > 1
        self.name = "Stacks : " + " + ".join(self.roles)
        self.last_file = ""
        self.last_exposure = None            # jamais utilisée (cf. propriété)
        self.count = 0                       # fichiers lus depuis `relire()`
        self.failed = 0                      # fichiers illisibles
        self.avertissements: list[str] = []  # linéarité / lecture, pour le journal
        self._idx = 0
        self._running = False

    # -- cycle de vie -----------------------------------------------------
    def open(self) -> None:
        """Vérifie les fichiers (présents, linéaires d'après NOTRE en-tête) et
        arme la lecture. Lève une erreur CLAIRE sur le premier problème."""
        for role, chemin in self.apparies:
            if not os.path.isfile(chemin):
                raise RuntimeError(
                    f"Stacks : fichier introuvable pour le rôle {role} — "
                    f"{chemin}")
            if dit_etire(entete_avastack(chemin)):
                raise RuntimeError(
                    f"Stacks : « {os.path.basename(chemin)} » (rôle {role}) "
                    "est un empilement DÉJÀ ÉTIRÉ — son en-tête AVAStack le "
                    "dit (AVAVUE). Choisissez la version LINÉAIRE : un "
                    "étirement ne se défait pas.")
        self._running = True

    def close(self) -> None:
        self._running = False

    def relire(self) -> None:
        """Remet le curseur au DÉBUT pour une NOUVELLE session : chaque fichier
        fourni est relu une fois (les empilements ne changent pas en cours de
        route, contrairement à un dossier surveillé). Appelé par le worker au
        démarrage d'une session — compteurs de lecture remis à zéro."""
        self._idx = 0
        self.count = 0
        self.failed = 0
        self.avertissements.clear()

    def apply_settings(self, *a: Any) -> None:
        """Exposition/gain : sans objet (l'empilement est déjà fait)."""

    def scanner(self) -> None:
        """Aucun scan : les fichiers sont connus d'avance. No-op qui satisfait
        le contrat des sources FICHIERS (`_worker_cadence_dossier`)."""

    # -- lecture ----------------------------------------------------------
    @property
    def pending(self) -> int:
        """Fichiers fournis pas encore lus (ligne d'état « en attente »)."""
        return max(0, len(self.apparies) - self._idx)

    @property
    def exposure_time_sec(self) -> None:
        """AUCUNE pose unitaire : un empilement fourni n'en a pas. On ne
        fabrique jamais une durée d'intégration à partir de `AVAFRAME`."""
        return None



    def read(self, timeout: float = 1.0) -> Any:
        """→ la PROCHAINE image fournie, puis None quand tout a été lu.

        `timeout` est accepté pour le contrat commun (`CameraBase`) mais n'est
        pas utilisé : rien n'« arrive » ici, les fichiers sont sur le disque.

        Plusieurs fichiers : `(image, rôle)` (le worker empile par rôle).
        Un seul fichier : l'image SEULE (empilement direct, « Mono »)."""
        if not self._running:
            return None
        while self._idx < len(self.apparies):
            role, chemin = self.apparies[self._idx]
            self._idx += 1                   # tenté = définitif (jamais de boucle)
            try:
                img, expo = load_image(chemin, avec_expo=True)
            except Exception:
                self.failed += 1
                self.avertissements.append(
                    f"« {os.path.basename(chemin)} » (rôle {role}) : lecture "
                    "impossible — fichier ignoré")
                continue
            self.count += 1
            self.last_file = chemin
            # `expo` n'est PAS publiée : un empilement n'a pas de pose unitaire
            # (cf. `exposure_time_sec`) — on la garde seulement pour la trace.
            self.last_exposure = expo
            avert = avertissement_lineaire(chemin, img)
            if avert:
                self.avertissements.append(avert)
            if self.par_roles:
                return img, role
            return img
        return None
