# -*- coding: utf-8 -*-
"""Guet de GEL du fil d'interface (jalon 84).

POURQUOI (retour RÉEL d'un testeur sous macOS 27 « Golden Gate », 30/09/2026) :
« les boutons ne sont pas toujours cliquables… le bouton permettant de choisir
le dossier à surveiller ne répond pas ». Sous macOS, contrairement à Windows,
un clic qui tombe pendant que le fil d'interface travaille n'est pas mis en
file d'attente : il est PERDU, et l'application paraît insensible par
intermittence. Ce symptôme ne se raconte pas — il se MESURE : ce module écrit
dans le journal chaque période où le fil d'interface n'a pas rendu la main,
avec la PILE de ce fil (même méthode que la leçon du 27/09/2026 : un blocage se
désigne par sa pile, jamais par une hypothèse).

Fonctionnement : `Guet` compare l'horloge au dernier BATTEMENT posé par la
boucle d'interface (`_tick`, toutes les 30 ms). Un fil DÉMON (aucun coût pour
le calcul) vérifie quatre fois par seconde ; au-delà de `SEUIL_S` de retard, il
écrit une ligne de journal — durée + pile COMPLÈTE du fil d'interface, lue par
`sys._current_frames()` : le fil bloqué n'a rien à coopérer, et un gel dû à un
appel natif (Tk, OpenCV, réseau) est donc vu comme les autres.

Anti-bruit : un rapport par ÉPISODE (le suivant n'est écrit qu'après un retour
à la normale), plafonné à `MAX_RAPPORTS` par session ; les retards qui
précèdent le premier battement ne sont pas comptés (l'attente de démarrage
n'est pas un gel).

`AVASTACK_SANS_GUET=1` débraye le guet (bancs et exécutions sans écran).
"""

import os
import sys
import threading
import time
import traceback
from typing import Any

from .. import journal

SEUIL_S = 1.5          # retard qui signe un gel perceptible pour l'utilisateur
PERIODE_S = 0.25       # cadence de surveillance (nuit le calcul : elle dort)
MAX_RAPPORTS = 5       # plafond par session (le journal ne doit pas exploser)


class Guet:
    """Surveille le fil d'interface depuis un fil démon (cf. docstring)."""

    def __init__(self, racine: Any = None, seuil: float = SEUIL_S) -> None:
        self.racine: Any = racine      # fenêtre Tk (pour savoir si l'on vit)
        self.seuil: float = float(seuil)
        self.actif: bool = False
        self.battements: int = 0        # preuves de vie reçues
        self.rapports: list[tuple[float, str]] = []   # lu par les bancs
        self._dernier: float = time.monotonic()
        self._fil: int = threading.get_ident()   # fil d'interface = celui qui bat
        self._stop: threading.Event = threading.Event()
        self._episode: bool = False     # un rapport par gel

    # ------------------------------------------------------- fil d'interface
    def battement(self) -> None:
        """Posé par la boucle d'interface : c'est la preuve qu'elle vit.

        Appelé DES MILLIERS de fois par session : il ne fait que deux
        affectations (aucune allocation, aucun accès disque)."""
        self._dernier = time.monotonic()
        self.battements += 1
        self._episode = False

    def retard(self) -> float:
        """Secondes écoulées depuis le dernier battement (bancs et veille)."""
        return time.monotonic() - self._dernier

    # ------------------------------------------------------------- pilotage
    def demarrer(self) -> bool:
        """Lance le fil de surveillance. → True si (re)lancé, False sinon.

        Deux refus, tous deux MESURÉS au jalon 84 :
        - `AVASTACK_SANS_GUET=1` (bancs et exécutions sans écran) ;
        - fenêtre NON AFFICHÉE : le guet sert à expliquer des CLICS PERDUS, donc
          il n'a rien à dire sans fenêtre — et les bancs d'interface, qui
          construisent plusieurs `App` derrière un `withdraw()`, recevaient des
          rapports parasites (le gel mesuré était la CONSTRUCTION de l'interface
          suivante, 1,6 s ; pile lue dans le journal). Un guet sans fenêtre
          visible ne ferait que fausser leurs mesures de temps."""
        if self.actif or os.environ.get("AVASTACK_SANS_GUET"):
            return False
        if self.racine is not None and not self.fenetre_visible():
            return False
        self.actif = True
        self._stop.clear()
        self._episode = False
        self._dernier = time.monotonic()
        threading.Thread(target=self._veille, daemon=True,
                         name="guet-interface").start()
        return True

    def fenetre_visible(self) -> bool:
        """La fenêtre surveillée est-elle réellement AFFICHÉE ? (jamais d'exception)"""
        if self.racine is None:
            return True
        try:
            return bool(self.racine.winfo_viewable())
        except Exception:
            return False

    def arreter(self) -> None:
        self._stop.set()
        self.actif = False

    # ---------------------------------------------------------------- veille
    def _veille(self) -> None:
        while not self._stop.is_set():
            time.sleep(PERIODE_S)
            try:
                self._tour()
            except Exception:        # ce fil ne doit JAMAIS tuer l'appli
                pass

    def _tour(self) -> None:
        if not self.actif or self._episode:
            return
        retard = self.retard()
        if retard < self.seuil:
            return
        self._episode = True             # un seul rapport pour ce gel
        if len(self.rapports) >= MAX_RAPPORTS:
            return
        pile = self.pile_fil_interface()
        self.rapports.append((retard, pile))
        journal.note(
            "gel de l'interface",
            "le fil d'interface n'a pas rendu la main pendant %.1f s (sous "
            "macOS, les clics tombés pendant ce temps sont perdus ; un rendu "
            "d'aperçu complet dure légitimement ~1,7 s — c'est la PILE "
            "ci-dessous qui désigne le responsable) — pile du fil :%s%s"
            % (retard, os.linesep, pile))

    def pile_fil_interface(self) -> str:
        """Pile du fil d'interface, lue SANS sa coopération (`sys._current_frames`).

        C'est le cœur du diagnostic : elle nomme la fonction dans laquelle
        l'interface était retenue (Tk, OpenCV, accès disque…), ce qu'aucune
        hypothèse ne peut remplacer."""
        try:
            cadre = sys._current_frames().get(self._fil)
        except Exception:
            cadre = None
        if cadre is None:
            return "(pile indisponible)"
        try:
            return "".join(traceback.format_stack(cadre))
        except Exception:
            return "(pile illisible)"
