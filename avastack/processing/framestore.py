# -*- coding: utf-8 -*-
"""Archive TEMPORAIRE des frames calibrées — fondation du re-stack (jalon 15).

Décision d'Alain (17/09/2026, constat « Siril empile des brutes que nous
refusons ») : l'alignement devient « à la Siril » (canal vert, appariement
par triangles) ET l'empilement devra pouvoir être recalculé sur une MEILLEURE
frame de référence, comme Siril choisit la sienne. Pour cela il faut garder
les frames — dans TOUS les modes : en « dossier surveillé » les brutes sont
souvent lues à travers le réseau (NAS, mini-PC d'acquisition) et leur relecture
n'est pas garantie ; une caméra SDK, elle, n'écrit aucun fichier.

Chaque frame CALIBRÉE (donc directement re-empilable, sans rejouer darks/
flats) est écrite en FITS float32 dans un dossier de travail de session.
Garde-fous (jamais de panne silencieuse) :
- au plus une frame archivée par `intervalle_s` secondes : une source vidéo
  (webcam OpenCV ~30 fps, ciel simulé) ne doit pas noyer le disque — aux
  poses d'astronomie (≥ 30 s) la limite ne joue jamais ;
- plafond de taille `max_octets` : au-delà, l'archivage S'ARRÊTE et le
  message est exposé dans la ligne d'état ; l'empilement continue normalement ;
- **v2.38.6 — le plafond est RÉEL, pas déclaré** : un plafond de 20 Go en dur
  ne protégeait rien dans un `/tmp` de 4,6 Go (constat d'Alain : « 24962352
  requested and 10902832 written » pendant BlurX, tmpfs saturé). Le plafond
  effectif vaut `min(max_octets, 50 % de l'espace libre du volume)` et il est
  recalculé à chaque frame (`travail.plafond_effectif`) ;
- tout échec d'écriture arrête aussi l'archivage (`erreur`), sans jamais
  interrompre le thread d'acquisition.
Le dossier est supprimé à la fermeture de la session (`vider`) ; les résidus
d'une session morte sont nettoyés au démarrage (`travail.nettoyer_orphelins`).
"""
import os
import shutil
import time

import numpy as np

from .. import travail
from ..images import save_image

# Une frame archivée au plus toutes les `ARCHIVE_INTERVALLE_S` secondes.
ARCHIVE_INTERVALLE_S: float = 1.0
# Plafond de taille VOULU du dossier d'archive (20 Go ≈ 3 h de frames RGB
# float32 8 Mpx à 120 s de pose) : il n'est JAMAIS dépassé, mais il est
# abaissé à la moitié de l'espace libre réel (cf. `plafond_effectif`) — un
# volume de 4,6 Go ne doit pas être rempli à 100 %.
ARCHIVE_MAX_OCTETS: int = 20 * 1024 ** 3
PREFIXE_DOSSIER: str = "avastack_frames_"


class ArchiveFrames:
    """Dossier temporaire de session contenant les frames calibrées (FITS
    float32, ordre d'arrivée). `n` = nombre de frames archivées ; `erreur`
    non vide = archivage arrêté (message à exposer, jamais une exception)."""

    def __init__(self, max_octets: int = ARCHIVE_MAX_OCTETS,
                 intervalle_s: float = ARCHIVE_INTERVALLE_S) -> None:
        self.max_octets: int = max(1, int(max_octets))
        self.intervalle_s: float = max(0.0, float(intervalle_s))
        self.dossier: str | None = None    # créé à la première frame archivée
        self.chemins: list[str] = []        # chemins écrits, ordre d'arrivée
        self.n: int = 0
        self.erreur: str = ""               # non vide = archivage arrêté
        self._t0: float | None = None       # monotonic du dernier archivage
        self._taille: int = 0               # somme des tailles (octets)

    def ajouter(self, frame: np.ndarray) -> str | None:
        """Archive une frame calibrée → chemin écrit, ou None (limite de
        débit, erreur d'écriture, ou plafond atteint). `frame` n'est PAS
        modifiée ; aucune exception n'est propagée (l'empilement continue)."""
        if self.erreur:
            return None
        if (self._t0 is not None
                and time.monotonic() - self._t0 < self.intervalle_s):
            return None
        try:
            if self.dossier is None:
                self.dossier = travail.creer_dossier(PREFIXE_DOSSIER)
            # v2.38.6 : plafond recalculé sur l'espace RÉEL (un tmpfs de 4,6 Go
            # ne doit jamais être rempli par l'archive des frames).
            plafond = travail.plafond_effectif(self.dossier, self.max_octets)
            if self._taille >= plafond:
                self.erreur = (f"plafond atteint ({self._taille / (1 << 30):.1f} "
                               f"Go sur {plafond / (1 << 30):.1f} Go disponibles "
                               "pour le travail) : archivage arrêté, l'empilement "
                               "continue")
                return None
            chemin = os.path.join(self.dossier, f"frame_{self.n:06d}.fits")
            save_image(chemin, frame)
            self._t0 = time.monotonic()
            self._taille += os.path.getsize(chemin)
            self.chemins.append(chemin)
            self.n += 1
            if self._taille > plafond:
                self.erreur = (f"plafond atteint "
                               f"({self._taille / (1 << 30):.1f} Go) : "
                               "archivage arrêté, l'empilement continue")
            return chemin
        except Exception as exc:
            self.erreur = f"écriture impossible ({exc}) : archivage arrêté"
            return None

    def vider(self) -> None:
        """Supprime le dossier temporaire et réinitialise l'archive."""
        if self.dossier:
            shutil.rmtree(self.dossier, ignore_errors=True)
        self.dossier = None
        self.chemins = []
        self.n = 0
        self.erreur = ""
        self._t0 = None
        self._taille = 0