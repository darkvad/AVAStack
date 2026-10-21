# -*- coding: utf-8 -*-
"""FIL DE RENDU — étape 1b de la Phase 1 (branche `OptimisationUI`, 20/10/2026).

LE DÉFAUT MESURÉ. Après l'étape 1a il ne restait plus QU'UN rendu par frame,
mais ce rendu pesait encore **102 s sur le fil Tk** (relevé `perf-4.json`,
637 s, 48 frames : 51 rendus × ~2 000 ms) : `ui_tick` restait à 48 % du temps
mural, et l'interface ne pouvait rien faire pendant ces deux secondes.

CE QUE FAIT CE MODULE
  - un fil DÉMON unique qui reçoit une DEMANDE (`Job`) et publie un RÉSULTAT
    (`Resultat` : image uint8 + les DEUX jeux de bacs + l'image d'avant les
    barres de niveaux) ;
  - **UN SEUL job en attente** : une nouvelle demande ÉCRASE l'ancienne
    (« le dernier gagne »), aucune backpressure — l'interface ne doit JAMAIS
    attendre un rendu, c'est tout l'objet de l'étape ;
  - **UN SEUL ÉCRIVAIN de l'état de `DisplayProcessor`** : en marche normale,
    `process()` n'est appelé QUE d'ici. Les stats EMA du STF (`_stats`) et le
    cache de la chaîne pré-étirement vivent dans `disp` ; les écrire depuis
    deux fils en même temps produirait des images différentes d'un run à
    l'autre. Les bancs (et les mesures) qui exigent un rendu SYNCHRONE mettent
    le fil en mode `immediat` : le rendu est alors fait SUR PLACE, comme avant.
  - Le fil Tk ne garde que ce qui exige Tk : le CHOIX DE LA SOURCE (variables
    Tk), puis l'AFFICHAGE d'un résultat déjà calculé (`_show_image` +
    `_draw_hist` sur des bacs tout prêts).

MESURE (Phase 0, `avastack/perf.py`) : `fil_rendu` / `fil_etirement` /
`fil_histogrammes` sont les chronos du fil de rendu ; `ui_rendu` /
`ui_histogrammes` / `ui_dessin` ne mesurent plus que l'APPLICATION du résultat
sur le fil d'interface (c'est ce que 1b fait chuter). Compteurs :
`rendus` (rendus produits), `rendus_demandes`, `rendus_ecrases` (demande
remplacée avant calcul), `rendus_perimes` (résultat remplacé avant affichage),
`rendus_erreur`. Jauge `rendu_q` (0 ou 1 : un calcul attend).
"""

import threading
from typing import Any, NamedTuple

from .. import perf


class Job(NamedTuple):
    """Demande de rendu — TOUT est résolu dans le fil Tk avant l'envoi.

    `src` : image LINÉAIRE déjà choisie (aperçu ou pleine résolution).
    `live` : fait avancer le lissage temporel des stats du STF (nouvelle frame).
    `hist` : recalculer les deux jeux de bacs.
    `attente_ok` : au moment de la demande, AUCUNE image n'était affichée —
             l'image d'attente doit donc être calculée ET affichée (sinon
             l'écran resterait vide au tout premier rendu).
    `generation` : jeton de session ; un résultat d'une génération périmée
             (reset, écran vidé) est JETÉ, jamais affiché.
    `motif` : libellé de diagnostic (« frame », « vl_new », « reglage »…).
    """

    src: Any
    live: bool
    hist: bool
    attente_ok: bool
    generation: int
    motif: str


class Resultat(NamedTuple):
    """Rendu terminé, prêt à être affiché par le fil Tk (aucun calcul)."""

    img8: Any
    brut: Any
    hist_brut: Any
    hist_sortie: Any
    hist_erreur: str
    etait_attente: bool
    hist: bool
    generation: int
    motif: str
    src: Any



class FilRendu:
    """Fil de rendu unique — cf. la docstring du module.

    `immediat = True` : AUCUN fil, le rendu est exécuté par l'appelant. C'est
    le mode des BANCS et des mesures de réactivité (ils lisent l'image juste
    après l'avoir demandée) ; en production il reste False.
    """

    # Attente maximale du fil quand il n'a rien à faire : il se réveille de
    # toute façon sur `_evt`, ce délai n'est qu'un filet pour `arreter()`.
    ATTENTE_S = 0.2

    def __init__(self, hote: Any) -> None:
        # `hote` = l'application : le fil lit `hote.disp` (moteur d'affichage)
        # et `hote._histogrammes_purs` (fonction PURE, sans Tk).
        self._hote = hote
        self.immediat: bool = False
        self._verrou = threading.Lock()
        self._job: Job | None = None
        self._resultat: Resultat | None = None
        # Un job PRIS par le fil mais pas encore terminé : sans ce drapeau,
        # `en_attente()` répondrait « vide » pendant tout le calcul et
        # `attendre_rendu()` rendrait la main trop tôt (défaut vu au banc).
        self._en_cours = False
        self._generation = 0
        self._evt = threading.Event()
        self._stop = threading.Event()
        self._fil = threading.Thread(target=self._boucle, name="rendu",
                                     daemon=True)
        self._fil.start()

    # ------------------------------------------------------------ cycle de vie
    def arreter(self) -> None:
        """Arrête le fil (fermeture de la fenêtre). Toujours BORNÉ."""
        self._stop.set()
        self._evt.set()
        try:
            self._fil.join(timeout=2.0)
        except RuntimeError:            # jamais démarré / déjà joint
            pass
        with self._verrou:
            self._en_cours = False
            perf.poser_gauge("rendu_q", 0)

    def vivant(self) -> bool:
        """True si le fil tourne encore (diagnostic et bancs)."""
        return self._fil.is_alive()

    def ident(self) -> int | None:
        """Identifiant du fil de rendu — l'espion du banc 1b s'en sert pour
        vérifier qu'AUCUN rendu ne se fait sur le fil d'interface."""
        return self._fil.ident

    # ------------------------------------------------------------- soumissions
    def generation(self) -> int:
        """Jeton de session courant (à recopier dans `Job`)."""
        with self._verrou:
            return self._generation

    def demander(self, job: Job) -> Resultat | None:
        """Confie `job` au fil de rendu.

        Mode IMMÉDIAT : le rendu est fait ici même et le résultat est RENDU
        (l'appelant l'applique) — exceptions comprises, comme avant 1b.
        Mode normal : rend None tout de suite ; le résultat sera pris par
        `prendre()` au prochain tour d'interface.
        """
        if self.immediat or not self._fil.is_alive():
            return self.executer(job)
        perf.compter("rendus_demandes")
        with self._verrou:
            if self._job is not None:
                # « Le dernier gagne » : la demande précédente n'a pas encore
                # été prise par le fil — elle est ABANDONNÉE, pas retardée.
                perf.compter("rendus_ecrases")
            self._job = job
            perf.poser_gauge("rendu_q", 1)
            self._evt.set()
        return None

    def prendre(self) -> Resultat | None:
        """Prend le résultat prêt (fil Tk) — un seul à la fois, le plus récent.

        Un résultat d'une génération PÉRIMÉE est jeté ici aussi (le fil a pu
        le publier juste avant un reset) : il ne doit jamais repeindre une
        image de la session précédente.
        """
        with self._verrou:
            res = self._resultat
            self._resultat = None
            if res is not None and res.generation != self._generation:
                perf.compter("rendus_perimes")
                return None
            if res is None and self._job is None:
                perf.poser_gauge("rendu_q", 0)
            return res

    def en_attente(self) -> bool:
        """True si un rendu est en cours, ou si une demande / un résultat non
        affiché existe encore (c'est la condition d'attente de `attendre_rendu`)."""
        with self._verrou:
            return (self._en_cours or self._job is not None
                    or self._resultat is not None)

    def purger(self) -> None:
        """Vide la demande et le résultat, et INVALIDE le calcul en cours.

        Appelé sur une SESSION NEUVE (`_reinit_etat_session`) et quand l'écran
        est vidé : une image calculée avant le reset ne doit jamais réapparaître
        après (`_last_disp = None` serait annulé par une application tardive).
        Le calcul éventuellement en cours, lui, se termine mais son résultat
        est jeté (génération).
        """
        with self._verrou:
            self._generation += 1
            self._job = None
            self._resultat = None
            self._evt.clear()
            perf.poser_gauge("rendu_q", 0)

    # ------------------------------------------------------------- exécution
    def executer(self, job: Job) -> Resultat | None:
        """Rend le `Job` : `process()` puis les deux histogrammes.

        AUCUN widget, aucune variable Tk : c'est la condition pour que ce code
        tourne hors du fil d'interface. Rend None si la génération a changé
        pendant le calcul (reset intervenu entre-temps).
        """
        with perf.chrono("fil_rendu"):
            perf.compter("rendus")
            src = job.src
            perf.poser_gauge("source_px",
                             int(src.shape[0] * src.shape[1])
                             if hasattr(src, "shape") else 0)
            with perf.chrono("fil_etirement"):
                img8 = self._hote.disp.process(src, live=job.live)
            # Lus DANS LE MÊME FIL que `process()` : `dernier_etait_attente` et
            # `dernier_brut_niveaux` décrivent CE rendu-là (un seul écrivain).
            etait = bool(getattr(self._hote.disp, "dernier_etait_attente",
                                 False))
            brut = getattr(self._hote.disp, "dernier_brut_niveaux", None)
            hist_brut = hist_sortie = None
            hist_err = ""
            # Une image d'ATTENTE n'apporte pas les bacs utiles — sauf au tout
            # premier rendu, où elle est la seule image (écran jamais vide).
            if job.hist and (not etait or job.attente_ok):
                with perf.chrono("fil_histogrammes"):
                    hist_brut, hist_sortie, hist_err = \
                        self._hote._histogrammes_purs(src, brut)
        if self.generation() != job.generation:
            perf.compter("rendus_perimes")
            return None
        return Resultat(img8=img8, brut=brut, hist_brut=hist_brut,
                        hist_sortie=hist_sortie, hist_erreur=hist_err,
                        etait_attente=etait, hist=bool(job.hist),
                        generation=job.generation, motif=job.motif, src=src)

    # ---------------------------------------------------------------- le fil
    def _boucle(self) -> None:
        """Boucle du fil : une demande → un rendu → un résultat (le plus récent).

        Aucune exception ne sort d'ici : un rendu raté est JOURNALISÉ (compteur
        `rendus_erreur`) et le fil continue — sinon une seule erreur figerait
        l'affichage pour de bon, ce que l'étape 1b ne doit pas introduire.
        """
        from .. import journal          # import TARDIF (cycle au démarrage)
        while not self._stop.is_set():
            self._evt.wait(self.ATTENTE_S)
            if self._stop.is_set():
                break
            with self._verrou:
                job = self._job
                self._job = None
                if job is None:
                    self._evt.clear()
                    perf.poser_gauge("rendu_q", 0)
                    continue
                self._en_cours = True
            try:
                res = self.executer(job)
            except Exception:           # noqa: BLE001 (journalisé, jamais fatal)
                perf.compter("rendus_erreur")
                journal.erreur("rendu (fil de rendu)")
                res = None
            with self._verrou:
                self._en_cours = False
                if res is not None:
                    if self._resultat is not None:
                        perf.compter("rendus_perimes")
                    self._resultat = res
                # Une demande est arrivée PENDANT le calcul : on la prend tout
                # de suite (l'évènement reste armé, il ne faut pas l'effacer).
                if self._job is None:
                    self._evt.clear()
