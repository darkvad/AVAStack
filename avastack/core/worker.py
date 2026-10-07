# -*- coding: utf-8 -*-
"""Thread d'acquisition — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 106a du chantier de refactoring : la
méthode `_worker` (boucle du thread d'acquisition) est reprise VERBATIM dans le
mixin `AcquisitionWorker`, dont `App` HÉRITE — `self` reste l'instance `App`,
donc le comportement est inchangé AU BIT.

Jalon 106b : `_worker` reste l'ORCHESTRATEUR de la boucle ; ses blocs cohérents
« acquisition » (traitement d'une brute), « reset » de session et « re-stack »
sont découpés en sous-méthodes (`_worker_empiler_frame`, `_worker_reinitialiser`,
`_worker_restack`), reprises VERBATIM. Le SEAM `WorkerConfig` (`config.py`) est
CONSOMMÉ par le worker : `_worker_empiler_frame` lit `kappa`/`rejet_methode`/
`rejet_fenetre` sur un instantané `cfg` construit au POINT D'USAGE (aucun ajout
au chemin de la boucle : comportement identique AU BIT).

Jalon 106c : les deux blocs de « PILOTAGE » sont à leur tour extraits VERBATIM —
`_worker_pilotage` (sondage des contrôles à la connexion, demandes filtre /
refroidissement, relecture TEC, réglages expo/gain et OFFSET ; servi en TÊTE de
boucle, MÊME EMPILEMENT EN PAUSE) et `_worker_cadence_dossier` (pause sur une
source FICHIERS + scan périodique de cadence ; renvoie True quand le tour doit
se terminer sans rien lire). Aucun paramètre du seam n'est lu sur ce chemin : la
leçon du 106b interdit d'AJOUTER du code sur le chemin de la boucle (un
instantané en tête de tour décalait la course du banc 76).

Jalon 106d : la dernière famille, les « MESURES » (astrométrie + photométrie /
SPCC), rejoint le mixin — les méthodes de CALCUL (`_astro_tour`, `_astro_aveugle`,
`_photo_tour`, `_photo_canaux`, `_source_rgb`, `_spcc_tour`,
`_astro_indices_entete`, `_astro_propager_restack`) sont reprises VERBATIM de
`ui/app.py`, et l'appel groupé de `_worker` devient `_worker_mesures` (servi
APRÈS le re-stack, AVANT la construction de l'état poussé). L'AFFICHAGE reste
dans `ui/app.py` (méthodes `_maj_*_etat` / `_maj_*_vue`, dialogues de nom de
cible, helpers d'en-tête FITS de sortie) : le worker MESURE, l'interface montre.

PIÈGE ÉVITÉ : trois globals de `avastack.ui.app` sont MONKEYPATCHÉS par les bancs
(`ui.ArchiveFrames` ; `ui.RESTACK_MIN_FRAMES`/`ui.RESTACK_CADENCE`) : ils sont
lus par RÉSOLUTION TARDIVE (`_globals_app()`), comme `ui/widgets/collapsible.py`
et `ui/panels/stack.py` — l'interception des bancs reste EFFECTIVE et le
comportement est identique AU BIT.
"""

import os
import queue
import threading
import time
from typing import Any

import numpy as np
import cv2

from ..cameras import QHYCamera
from ..images import borner_lineaire, save_image
from ..processing import StarAligner, LiveStacker
from ..processing import stars as seeing_live
from ..processing.composition import CompositeStacker, extraire_canal
# Jalon 106d : les MESURES (astrométrie / photométrie / SPCC) sont désormais
# CALCULÉES ici — mêmes modules d'appui que `ui/app.py` (aucun cycle : `core`
# importe `processing`, jamais l'inverse).
from ..processing import astrometrie as astro_mod
from ..processing import photometrie as photo_mod
from ..processing import spcc as spcc_mod
from .config import WorkerConfig


def _globals_app():
    """Globals du module d'application `avastack.ui.app` — résolution TARDIVE.

    Écho du correctif du jalon 105a : les bancs remplacent
    `avastack.ui.app.ArchiveFrames` et `.RESTACK_MIN_FRAMES`/`.RESTACK_CADENCE`
    pour piloter le re-stack AUTO. Lire ces globals au MOMENT DE L'APPEL
    préserve cette interception ; en production c'est le MÊME objet que
    `avastack.ui.app`."""
    from ..ui import app as _app              # import TARDIF (évite le cycle)
    return _app


class AcquisitionWorker:
    """Mixin : boucle du thread d'acquisition (cf. docstring du module)."""

    # Interface attendue sur l'hôte (`App`) — DÉCLARATIONS de typage seulement.
    # Ce sont les membres de `self` (l'instance `App`) que la boucle lit/écrit ;
    # regroupés ici pour le typage statique (`pyright`). Après le jalon 106d
    # (mesures rapatriées), il ne reste ici que l'interface VIVANTE de l'hôte —
    # un typage plus fin viendra au jalon 110 (typage rétroactif d'`app.py`).
    _a_lu_une_frame: Any
    _ancre_idx: Any
    _ancre_role: Any
    _ancre_score: Any
    _appliquer_demande_tec: Any
    _appliquer_filtre_demande: Any
    _armer_cadence: Any
    _astro_actif: Any
    _astro_aveugles: Any
    _astro_balayage: Any
    _astro_bases: Any
    _astro_champ_seul: Any
    _astro_dernier_aveugle: Any
    _astro_entete_sauvegarde: Any
    _astro_fov_essayes: Any
    _astro_indices: Any
    _astro_msg_indices: Any
    _astro_source: Any
    _astro_wcs_secours: Any
    _autoriser_lecture: Any
    _cadence_dossier: Any
    _compo_gains: Any
    _compo_mode_l: Any
    _compo_nom: Any
    _controles_sondes: Any
    _couches_brutes: Any
    _definir_reference: Any
    _dernier_st: Any
    _do_restack: Any
    _do_restack_compo: Any
    _entete_reglages: Any
    _ext_popup: Any
    _filtre_floue: Any
    _fit_actif: Any
    _fit_mode: Any
    _fwhm_hist: Any
    _fwhm_par_role: Any
    _last_disp: Any
    _mode_compo: Any
    _narrowband_ha: Any
    _norm_commune: Any
    _photo_actif: Any
    _photo_dernier: Any
    _photo_essais: Any
    _photo_gains_actif: Any
    _photo_gains_pose: Any
    _pleine_res_activee: Any
    _poser_rayon_chroma: Any
    _pousser_rendu: Any
    _prochain_scan: Any
    _rafale_reste: Any
    _rafraichir_rendu: Any
    _ref_bad: Any
    _ref_frames: Any
    _ref_score: Any
    _rendu_differ: Any
    _restack_depuis: Any
    _run_external: Any
    _save_asseen_thread: Any
    _score_frame: Any
    _scores: Any
    _scores_par_role: Any
    _seeing_t0: Any
    _servir_demandes_sans_frame: Any
    _session: Any
    _sonder_controles: Any
    _spcc_actif: Any
    _spcc_dernier: Any
    _spcc_dispo: Any
    _spcc_essais: Any
    _stack_pleine_res: Any
    _tec_dernier: Any
    _tec_dernier_t0: Any
    _veut_restack: Any
    _vider_archive: Any
    _vl_frames: Any
    align_info: Any
    aligner: Any
    archive: Any
    archives: Any
    asseen_busy: Any
    asseen_result: Any
    astro_couleur: Any
    astro_info: Any
    bad_frames: Any
    cadence_lecture: Any
    calib: Any
    cam_pilotee: Any
    camera: Any
    dernier_applicatif: Any
    disp: Any
    empilement_on: Any
    empilement_start_request: Any
    ext_busy: Any
    ext_request: Any
    ext_state: Any
    ext_t0: Any
    filtre_courant: Any
    floues_rejetees: Any
    fps: Any
    kappa: Any
    last_show: Any
    pending_offset: Any
    pending_settings: Any
    photo_couleur: Any
    photo_info: Any
    photometrie: Any
    proc_entete: Any
    proc_full: Any
    proc_new: Any
    proc_show: Any
    q: Any
    ref_refresh: Any
    ref_request: Any
    rejet_fenetre: Any
    rejet_methode: Any
    reset_request: Any
    restack_couleur: Any
    restack_hist: Any
    restack_info: Any
    restack_request: Any
    restack_total: Any
    running: Any
    save_asseen_request: Any
    save_canaux_request: Any
    save_request: Any
    saved_path: Any
    seeing: Any
    seeing_msg: Any
    seeing_periode: Any
    show_stack: Any
    spcc: Any
    spcc_couleur: Any
    spcc_info: Any
    stacker: Any
    suivi_astro: Any
    var_wb: Any
    var_wb_force: Any
    view_cx: Any
    view_cy: Any
    zoom: Any

    # Jalon 106d : méthodes de l'HÔTE (`App`, encore dans `ui/app.py`) appelées
    # par les MESURES rapatriées — l'AFFICHAGE de l'état (`_maj_*_etat`), la vue
    # SPCC (`_maj_spcc_vue`) et les profils SPCC (`_spcc_osc` / `_spcc_profils`).
    # `Any` : elles ne sont PAS dans le mixin (séparation « mesures » /
    # « affichage »).
    _maj_astro_etat: Any
    _maj_photo_etat: Any
    _maj_spcc_etat: Any
    _maj_spcc_vue: Any
    _spcc_osc: Any
    _spcc_profils: Any

    def _worker(self):
        last_good = None
        self._controles_sondes = False
        # Jalon 26 : le thread est PERMANENT — tant que la caméra est
        # connectée, il continue de piloter les contrôles (roue, TEC,
        # réglages) même quand l'EMPILEMENT est en pause (« ■ Arrêter ») ;
        # c'est ce qui permet de régler/refroidir AVANT puis ENTRE les
        # sessions d'empilement.
        while self.running:
            t0 = time.perf_counter()

            # Jalon 106c : pilotage des contrôles caméra (sondage à la
            # connexion, demandes filtre / refroidissement, relecture TEC,
            # réglages expo/gain et OFFSET) — corps extrait VERBATIM dans
            # `_worker_pilotage`. Servi en TÊTE de boucle, MÊME EMPILEMENT
            # EN PAUSE (règle du jalon 26).
            self._worker_pilotage()

            # (Le mécanisme « déconnexion demandée au worker » du jalon 26b
            # a été SUPPRIMÉ (décision d'Alain, 20/09/2026 : la version
            # simple côté thread Tk fonctionne) — le worker ne ferme plus
            # jamais la caméra lui-même.)

            # Jalon 106b : remise à zéro de session (boutons « ▶ Démarrer »
            # et « Réinitialiser l'empilement ») — servie en TÊTE de boucle,
            # donc MÊME EMPILEMENT EN PAUSE. Corps extrait dans
            # `_worker_reinitialiser` (repris VERBATIM).
            self._worker_reinitialiser()

            # v2.41.0 : la SOURCE peut avoir été REFERMÉE par l'interface
            # (« Réinitialiser l'empilement » sur une source de fichiers,
            # « ⏏ Déconnecter ») : le worker SURVIT au lieu de mourir sur un
            # `None.read()` (une exception dans un thread tue le thread EN
            # SILENCE — plus aucune frame n'arrivait ensuite, et rien ne le
            # disait). Il attend ici la prochaine source ; c'est « ▶ Démarrer »
            # qui la crée, et qui le relance s'il s'était arrêté.
            if self.camera is None:
                self._servir_demandes_sans_frame()
                time.sleep(0.02)
                continue

            # Traitement externe demandé → thread dédié, l'acquisition continue.
            # Placé AVANT la lecture d'une frame : doit fonctionner même si
            # aucune brute n'arrive (acquisition en pause, dossier silencieux…).
            if self.ext_request and self.stacker is not None and not self.ext_busy:
                stack_now = self.stacker.mean()
                if stack_now is not None:
                    self.ext_request = False
                    self.ext_busy = True
                    threading.Thread(target=self._run_external,
                                     args=(stack_now, self.stacker.n, self._session),
                                     daemon=True).start()

            # Sauvegarde « tel que vu » (jalon 5) → thread dédié, l'acquisition
            # continue : le rendu pleine résolution (GraXpert live + étirement)
            # peut prendre plusieurs secondes.
            # Chantier 24/09/2026 : 4e élément `lineaire` — la 3e sortie
            # « empilement traité (linéaire) » emprunte la MÊME chaîne mais
            # part de l'empilement BRUT (mean(corrections=False)) et s'arrête
            # avant l'étirement.
            if (self.save_asseen_request is not None and self.stacker is not None
                    and self.stacker.n > 0 and not self.asseen_busy):
                req = self.save_asseen_request
                self.save_asseen_request = None
                path, vue, reglages = req[:3]
                lineaire = bool(req[3]) if len(req) > 3 else False
                if vue == "traitée" and self.proc_full is None:
                    self.asseen_result = ("ERREUR: aucun résultat traité à "
                                          "enregistrer")
                else:
                    if vue == "traitée":
                        # copie défensive : proc_full peut être remplacé
                        source = self.proc_full.astype(np.float32).copy()  # pyright: ignore[reportOptionalMemberAccess]
                        canaux = None
                    else:
                        # Pleine résolution. « tel que vu » : le composite de la
                        # chaîne affichée (corrections comprises) ; 3e sortie
                        # linéaire : l'empilement BRUT — les corrections sont
                        # appliquées plus loin, après le débruitage (décision (c)).
                        source = self.stacker.mean(corrections=not lineaire)
                        # Couches BRUTES : en COMPOSITION, la chaîne
                        # GraXpert/débruitage du fichier est faite PAR COUCHE
                        # (comme le solveur live) — le composite dépasse 1 et
                        # serait rescale/écrêté (cf. _couches_pleine_resolution).
                        canaux = self._couches_brutes()
                    self.asseen_busy = True
                    threading.Thread(
                        target=self._save_asseen_thread,
                        args=(path, vue, source, reglages, self._session,
                              lineaire, canaux),
                        daemon=True).start()

            # Sauvegarde LINÉAIRE de l'empilement : consommation de la demande
            # AVANT la lecture d'une frame — doit fonctionner même si aucune
            # brute n'arrive (dossier surveillé terminé, caméra en pause…).
            # Historiquement placé APRÈS l'empilement d'une nouvelle frame :
            # sans nouvelles frames, le worker ne l'atteignait JAMAIS
            # (demande silencieusement ignorée — constat Alain, 16/09/2026).
            if (self.save_request is not None and self.stacker is not None
                    and self.stacker.n > 0):
                path, self.save_request = self.save_request, None
                try:
                    # Jalon 25 : mot-clé FILTER (roue à filtres QHY) — utile
                    # pour les dossiers N.I.N.A. et la détection des rôles.
                    # v2.27.1 : l'empilement est BORNÉ à [0,1] avant écriture
                    # (borner_lineaire) — le composite d'une composition
                    # multi-dossiers dépasse largement 1 (cœur de galaxie
                    # normalisé par percentiles) : écrit tel quel, le fichier
                    # n'était PAS résolvable par ASTAP (« Only 0 stars found
                    # in image ») et paraissait saturé partout ailleurs
                    # (retour réel d'Alain, 22/09/2026, M31 RGB en mode
                    # dossiers). Mono : no-op (l'empilement est déjà ≤ 1).
                    img = self.stacker.mean(corrections=False)
                    # Jalon 56 : mots-clés WCS de la grille RÉELLEMENT écrite
                    # (recadrage d'intersection inclus) — le FITS devient
                    # localisable par Siril/astropy/PixInsight. Sans
                    # astrométrie résolue : en-tête inchangé (jamais de
                    # mot-clé faux dans un fichier).
                    entete = self._astro_entete_sauvegarde(
                        {"FILTER": self.filtre_courant}
                        if self.filtre_courant else None,
                        img.shape[:2] if img is not None else None)
                    # Question d'Alain (« la sauvegarde linéaire, elle sauvegarde
                    # quoi au juste ? ») : le fichier DÉCRIT ce qu'il contient.
                    # Chantier 24/09/2026 : plus AUCUNE correction de couleur
                    # ici (`applique=False`) — AVASPCC/AVAGAIA restent la MESURE
                    # (ce qui a été mesuré), AVAAPPLI dit ce qui est APPLIQUÉ au
                    # fichier (« aucune (empilement BRUT) »).
                    entete.update(self._entete_reglages(applique=False))
                    entete["AVAVUE"] = ("empilement BRUT (lineaire, sans "
                                        "etirement)")
                    img, entete = borner_lineaire(img, entete)
                    save_image(path, img, entete=entete)
                    self.saved_path = path
                    # Ce qui est ÉCRIT dans le fichier, montré à l'utilisateur
                    # (constat du 25/09/2026 : on ne savait pas, à la lecture du
                    # dialogue, si la SPCC était entrée dans le fichier ou non).
                    self.dernier_applicatif = entete.get("AVAAPPLI")
                except Exception as e:
                    self.saved_path = f"ERREUR: {e}"

            # Jalon 19 : sauvegarde des empilements PAR CANAL (mode compo) —
            # un fichier « canal_<rôle>.fit » par rôle empilé, linéaire et
            # recadré au cadre commun (composite = bouton « Enregistrer »).
            if (self.save_canaux_request is not None and self._mode_compo
                    and self.stacker is not None and self.stacker.n > 0):
                d_canaux, self.save_canaux_request = \
                    self.save_canaux_request, None
                try:
                    for role, carte in self.stacker.moyennes().items():
                        # v2.27.1 : même garantie d'échelle que la sauvegarde
                        # du composite (no-op ici en pratique : une moyenne de
                        # rôles reste ≤ 1).
                        # Jalon 56 : les couches sont empilées sur la MÊME
                        # grille que le composite → mêmes mots-clés WCS que
                        # la sauvegarde de l'empilement (recadrage inclus).
                        bordee, entete = borner_lineaire(
                            carte,
                            self._astro_entete_sauvegarde(
                                {"FILTER": role}, carte.shape[:2]))
                        # Ces fichiers sont les COUCHES BRUTES (moyenne par rôle,
                        # sans normalisation par canal ni gain) : la SPCC et la
                        # photométrie MESURENT sur ces mêmes valeurs — le dire
                        # dans l'en-tête évite toute confusion.
                        entete["AVALAYER"] = "couche BRUTE (ni normalisation, ni gain)"
                        # Aucune correction de couleur n'est appliquée à une
                        # couche (elle est BRUTE par construction) : le dire
                        # explicitement (étape ⑥).
                        entete.update(self._entete_reglages(applique=False))
                        save_image(os.path.join(
                            d_canaux, f"canal_{role}.fit"), bordee,
                            entete=entete)
                    self.saved_path = d_canaux
                except Exception as e:
                    self.saved_path = f"ERREUR: {e}"

            # Jalon 55 : réglages saisis en cours de session (gains compo,
            # canal L, Linear Fit) — resynchronisés sur le stacker À CHAQUE
            # tour. AVANT : posés à la création SEULEMENT (jalon 19) — un
            # gain changé en cours de session n'avait AUCUN effet sur la
            # vue « empilement » ni sur les sauvegardes (constat Alain :
            # « bouger un gain ne change rien »).
            if self.stacker is not None:
                if self._mode_compo:
                    self.stacker.gains = dict(self._compo_gains or {})
                    self.stacker.mode_l = self._compo_mode_l
                    # v2.36.0 : normalisation commune (option) — resynchronisée
                    # à chaque tour, comme les gains et le canal L.
                    if hasattr(self.stacker, "normalisation_commune"):
                        self.stacker.normalisation_commune = bool(
                            self._norm_commune)
                self.stacker.linear_fit = bool(self._fit_actif)
                self.stacker.linear_fit_mode = self._fit_mode
                # Jalon 56 (étape 5) : gains PHOTOMÉTRIQUES par rôle — écrits
                # dans le stacker SEULEMENT si la case opt-in est cochée, qu'une
                # mesure existe et qu'on est en COMPOSITION (un gain global en
                # mono n'a pas de sens). Comparé à ce qui est déjà posé : tout
                # changement force le rafraîchissement du rendu sans attendre
                # une nouvelle brute (leçon du jalon 55).
                if self._mode_compo and hasattr(self.stacker, "gains_roles"):
                    # Jalon 58 : la SPCC ABSOLUE prime sur les gains Gaia
                    # RELATIFS (elle compare des RATIOS de couleur prédits par
                    # les spectres, au lieu d'une magnitude G trop large) —
                    # chacune n'agit que si SA case est cochée.
                    if (self._spcc_actif and self.spcc is not None
                            and self.spcc.valide):
                        nouveaux = dict(self.spcc.gains())
                    elif (self._photo_gains_actif
                            and self.photometrie is not None
                            and self.photometrie.valide):
                        nouveaux = dict(self.photometrie.gains)
                    else:
                        nouveaux = {}
                    if nouveaux != (self.stacker.gains_roles or {}):
                        self.stacker.gains_roles = nouveaux
                        self._photo_gains_pose = dict(nouveaux)
                        self._rafraichir_rendu = True
                elif (self._source_rgb(self.stacker)
                      and hasattr(self.stacker, "gains")):
                    # v2.40.0 : source COULEUR (capteur OSC en mode dossier) —
                    # la SPCC y corrige DIRECTEMENT les canaux R/G/B de
                    # l'empilement (`LiveStacker.gains`, appliqués avant
                    # l'équilibrage et le recalage, comme la chaîne de sortie).
                    # Les gains Gaia RELATIFS restent, eux, réservés à la
                    # composition : ils sont mesurés par RÔLE, et une source
                    # couleur simple n'a pas de rôles.
                    nouveaux = (dict(self.spcc.gains())
                                if (self._spcc_actif and self.spcc is not None
                                    and self.spcc.valide) else {})
                    if nouveaux != (self.stacker.gains or {}):
                        self.stacker.gains = nouveaux
                        self._photo_gains_pose = dict(nouveaux)
                        self._rafraichir_rendu = True
                # Aucune brute à lire (mode dossier consommé, pause…) : si
                # un réglage vient de changer, le rendu est recalculé et
                # repoussé UNE fois — sinon l'affichage reste figé sur les
                # réglages du démarrage jusqu'à la prochaine brute.
                if self._rafraichir_rendu:
                    self._rafraichir_rendu = False
                    if self.stacker.n > 0 and self._dernier_st is not None:
                        self._pousser_rendu()

            # Jalon 106c : cadence de lecture des sources DOSSIER (pause sur
            # une source FICHIERS + scan périodique) — corps extrait VERBATIM
            # dans `_worker_cadence_dossier`. Renvoie True quand l'empilement
            # étant en pause sur une source FICHIERS, le tour doit se terminer
            # sans rien lire (le bloc historique portait `continue`).
            if self._worker_cadence_dossier():
                continue
            lu = None
            if self._autoriser_lecture():
                try:
                    lu = self.camera.read()
                except AttributeError:
                    # v2.41.0 : la source vient d'être refermée par
                    # l'interface (réinitialisation d'une source de fichiers) —
                    # le tour suivant la verra absente et attendra proprement,
                    # au lieu de tuer ce thread en silence.
                    continue
            if lu is None:
                # v2.37.0 : aucune frame à lire (fin de source, lecture en
                # pause) — les demandes qui ne dépendent PAS d'une frame sont
                # servies ICI (SPCC/photométrie redemandées par leur case).
                self._servir_demandes_sans_frame()
                time.sleep(0.005)
                continue
            # Jalon 26 : empilement en pause (« ■ Arrêter ») sur une CAMÉRA →
            # on maintient la lecture du flux (la caméra reste connectée, la
            # file du SDK se vide : elle s'accumulerait sinon en mémoire) mais
            # on n'empile rien. (Les sources FICHIERS, elles, ne sont plus
            # lues du tout en pause — cf. le garde ci-dessus.)
            if not self.empilement_on:
                self._servir_demandes_sans_frame()   # idem : mesures sans frame
                time.sleep(0.05)
                continue
            # Jalon 19 : source « composition » → read() renvoie (img, rôle).
            if self._mode_compo:
                frame, role = lu
            else:
                frame, role = lu, None
            frame = self.calib.apply(frame, role=role)
            self._a_lu_une_frame = True   # jalon 42 : une brute vient d'être lue
            self._rafale_reste -= 1       # jalon 46 : budget de rafale consommé

            # Jalon 106b : traitement complet de la brute calibrée (filtre
            # défocalisation, archivage, (re)création de l'empilement,
            # alignement et empilement) — extrait dans
            # `_worker_empiler_frame`. `sauter` = brute REJETÉE (très
            # défocalisée) : le tour suivant reprend sans empiler ni pousser
            # d'image.
            canaux = None
            sauter, last_good, stack = self._worker_empiler_frame(
                frame, role, last_good, t0)
            if sauter:
                continue

            # Jalon 13 : rafraîchissement AUTOMATIQUE de la référence — la
            # dérive lente éloigne les frames de la référence initiale et
            # l'appariement dégénère ; une référence JEUNE (l'empilement,
            # SANS recadrage → même repère que les frames alignées) suit.
            # Déclencheurs : toutes les N frames, ou ≥ 50 % de frames
            # refusées (et ≥ 3) depuis le dernier — sinon on ne se remet
            # jamais d'une série d'échecs (la prédiction reste bloquée).
            if stack is not None and self.ref_refresh > 0 and (
                    self._ref_frames >= self.ref_refresh
                    or (self._ref_bad >= 3
                        and 2 * self._ref_bad >= self._ref_frames)):
                self._definir_reference(self.stacker.mean(recadre=False))  # pyright: ignore[reportOptionalMemberAccess]
                self._ref_frames = self._ref_bad = 0

            if self.ref_request and stack is not None:
                self.ref_request = False
                # jalon 13 : SANS recadrage (même repère que les frames —
                # l'ancien code passait l'empilement RECADRÉ : chaque clic
                # décalait silencieusement tout l'empilement de (y0, x0))
                self._definir_reference(self.stacker.mean(recadre=False))  # pyright: ignore[reportOptionalMemberAccess]

            # Jalon 106b : re-stack « à la Siril » (bouton ou auto) — extrait
            # dans `_worker_restack` ; renvoie le nouvel empilement pour
            # l'affichage immédiat quand un re-stack a eu lieu.
            fait, st_restack = self._worker_restack()
            if fait:
                stack = st_restack

            # Jalon 106d : MESURES (astrométrie + photométrie + SPCC) — corps
            # extrait VERBATIM dans `_worker_mesures`. Servi APRÈS le re-stack
            # (le WCS doit décrire la grille COURANTE) et AVANT la construction
            # de l'état poussé à l'UI (la ligne d'état part avec le bon texte).
            self._worker_mesures()

            show = stack if stack is not None else (last_good if last_good is not None else frame)

            # Jalon 24 : couches de la composition (même passe que le
            # composite — ni double calcul, ni incohérence entre les deux).
            if stack is not None and self._mode_compo \
                    and hasattr(self.stacker, "mean_avec_canaux"):
                comp, canaux = self.stacker.mean_avec_canaux()  # pyright: ignore[reportOptionalMemberAccess]
                if comp is not None:
                    stack = comp
            # Aperçu allégé pour l'UI : réactif même en 16 Mpx ; l'étirement est
            # recalculé côté interface → curseurs réactifs entre deux frames.
            h, w = show.shape[:2]
            scale = min(1.0, 1600.0 / float(max(h, w)))
            if scale < 1.0:
                show = cv2.resize(show, None, fx=scale, fy=scale,
                                  interpolation=cv2.INTER_AREA)
            # v2.38.0 : garde l'empilement COMPLET sous la main pour l'option
            # « Rendu pleine résolution » (copie défensive : le stacker réécrit
            # son tampon à la frame suivante).
            if self._pleine_res_activee():
                self._stack_pleine_res = np.asarray(
                    stack if stack is not None else show, np.float32).copy()
            # v2.37.3/v2.37.4 : le rayon du flou de chroma suit la RÉSOLUTION —
            # l'aperçu est réduit d'un facteur `scale`, les ÉTOILES aussi : à
            # rayon constant en pixels, leur couleur s'étalerait 1/scale fois plus
            # loin à l'écran que dans les fichiers (halo 2,4 fois plus large à
            # 3838 px). Le réglage est le curseur « Rayon de référence » (pleine
            # résolution) : cf. `_poser_rayon_chroma`.
            self._poser_rayon_chroma(scale)
            # Jalon 10 : seeing live (FWHM médiane + nombre d'étoiles) sur
            # l'APERÇU — c'est la résolution sur laquelle la netteté live
            # travaillera, la PSF mesurée y est donc directement exploitable.
            # Mesure au plus toutes les `seeing_periode` s (quelques ms, mais
            # inutile 20 fois par seconde : le seeing ne change pas si vite).
            if time.perf_counter() - self._seeing_t0 >= self.seeing_periode:
                self._seeing_t0 = time.perf_counter()
                self.seeing, self.seeing_msg = seeing_live.mesurer_seeing(show)
                # Jalon 12 : la netteté live consomme cette mesure comme PSF —
                # elle est faite sur l'APERÇU, exactement la résolution où la
                # netteté travaille, et évite une 2e détection d'étoiles dans
                # le solveur. (Affectation atomique : le solveur lit la
                # référence, il ne la modifie jamais.)
                self.disp.vl_seeing = self.seeing
            # Jalon 75 : plus d'histogramme ici — il est calculé par le thread
            # d'affichage, sur l'image réellement montrée (l'aperçu 1600 px
            # d'ici ne décrit pas forcément ce qui est à l'écran : vue
            # « traitée », rendu pleine résolution).

            # Jalon 24 : couches + paramètres de recomposition poussés vers le
            # solveur live (remplacement ENTIER de la référence — jamais de
            # mutation en place, le solveur lit toujours un dict cohérent).
            # Gains/mode_l recopiés des valeurs lues côté thread principal en
            # tête de _tick (le worker n'a jamais le droit de lire les Tk).
            if self._mode_compo and canaux:
                # Jalon 56 (étape 5) puis chantier 24/09/2026 : le solveur live
                # re-compose depuis les couches BRUTES — il doit donc recevoir
                # TOUTES les corrections de couleur, exactement celles que la
                # façade applique à la vue « empilement » (sinon les deux vues
                # divergeraient dès qu'une case est cochée) : gains EFFECTIFS
                # (manuels × SPCC/Gaia), recalage « Linear Fit » et équilibrage
                # des canaux (avec son cadre, pour le fond mesuré).
                gains_eff = (self.stacker.gains_effectifs()  # pyright: ignore[reportOptionalMemberAccess]
                             if hasattr(self.stacker, "gains_effectifs")
                             else self._compo_gains)
                self.disp.vl_compo = (dict(canaux), self.stacker.composition,  # pyright: ignore[reportOptionalMemberAccess]
                                      gains_eff, self._compo_mode_l,
                                      # 5e élément (jalon 54) : recalage
                                      # « Linear Fit » — ré-appliqué à la
                                      # recomposition des couches traitées.
                                      (bool(self.stacker.linear_fit),  # pyright: ignore[reportOptionalMemberAccess]
                                       self.stacker.linear_fit_mode),  # pyright: ignore[reportOptionalMemberAccess]
                                      # 6e élément (chantier 24/09/2026) :
                                      # équilibrage des canaux (actif, force,
                                      # cadre) — déballage tolérant côté
                                      # display.
                                      (bool(self.stacker.wb_auto),  # pyright: ignore[reportOptionalMemberAccess]
                                       float(self.stacker.wb_force),  # pyright: ignore[reportOptionalMemberAccess]
                                       self.stacker.cadre),  # pyright: ignore[reportOptionalMemberAccess]
                                      # 7e élément (v2.36.0) : normalisation
                                      # COMMUNE des canaux (option d'Alain) —
                                      # la vue « traitée » doit recomposer
                                      # comme la vue « empilement ».
                                      bool(getattr(self.stacker,
                                                   "normalisation_commune",
                                                   False)))
            else:
                self.disp.vl_compo = None

            dt = time.perf_counter() - t0
            inst = 1.0 / max(dt, 1e-4)
            self.fps = inst if self.fps == 0 else 0.9 * self.fps + 0.1 * inst
            # Jalon 19 : en mode compo, `pending` est une propriété (somme
            # des dossiers) et l'archive est tenue PAR RÔLE — totaux pour
            # l'état ; `compo` = état par canal (« Ha: 12 · O3: 9 »).
            if self._mode_compo:
                pend = getattr(self.camera, "pending", 0)
                n_arch = sum(a.n for a in self.archives.values())
                err_arch = "; ".join(a.erreur for a in self.archives.values()
                                     if a.erreur)
            else:
                pend = len(getattr(self.camera, "_pending", []))
                n_arch, err_arch = self.archive.n, self.archive.erreur
            st = dict(frames=(self.stacker.n if self.stacker is not None
                              else 0),
                      rejets=(self.stacker.rejected_total
                              if self.stacker is not None else 0),
                      bad=self.bad_frames, floues=self.floues_rejetees,
                      fps=self.fps, cam=getattr(self.camera, "name", "—"),
                      file=getattr(self.camera, "last_file", ""),
                      pending=pend,
                      failed=getattr(self.camera, "failed", 0),
                      align=self.align_info,
                      seeing=self.seeing, seeing_msg=self.seeing_msg,
                      archive=n_arch, archive_err=err_arch,
                      compo=(self.stacker.etat()
                             if self._mode_compo and self.stacker is not None
                             else None),
                      restack=self.restack_info, restack_n=self.restack_total,
                      astro=self.astro_info, photo=self.photo_info,
                      spcc=self.spcc_info)
            if self.stacker is not None and self.stacker.cadre is not None:
                y0, x0, y1, x1 = self.stacker.cadre
                st["crop_w"], st["crop_h"] = x1 - x0, y1 - y0
            self._dernier_st = st           # jalon 55 : réutilisé par
            try:                            # _pousser_rendu (sans brute)
                self.q.put_nowait((show, st))
            except queue.Full:
                pass
            # Jalon 42 : quand TOUTES les brutes détectées ont été lues, la
            # fenêtre de cadence est (ré)armée — la prochaine rafale n'aura
            # lieu qu'à l'échéance (les brutes qui arrivent entre-temps
            # attendent sur le disque, aucune perte).
            if self._a_lu_une_frame:
                self._armer_cadence()
                self._a_lu_une_frame = False
            time.sleep(max(0.0, 1.0 / 20.0 - (time.perf_counter() - t0)))

    def _worker_pilotage(self):
        """Pilotage des contrôles caméra — servi en TÊTE de boucle (jalon 106c).

        Corps repris VERBATIM de `_worker` (commentaires d'origine conservés,
        jalons 26/27) : sondage des contrôles à la connexion, demandes filtre /
        refroidissement posées côté Tk, relecture périodique du TEC, réglages
        (expo/gain) et OFFSET demandés. Tourne à CHAQUE tour, MÊME EMPILEMENT
        EN PAUSE (règle du jalon 26). Aucun paramètre du seam `WorkerConfig` n'y
        est lu : ce bloc vit en tête de boucle, or la leçon du 106b est qu'aucun
        code ne doit être AJOUTÉ sur le chemin de la boucle."""
        # Sondage des contrôles une fois, dès la connexion (la caméra
        # est ouverte : les contrôles répondent sans attendre une frame).
        if not self._controles_sondes and self.cam_pilotee is not None:
            self._controles_sondes = True
            try:
                self._sonder_controles()
            except Exception:
                pass

        # Demandes filtre / refroidissement posées côté Tk — traitées
        # ICI (thread de travail, jamais d'appel SDK depuis le thread Tk).
        try:
            self._appliquer_filtre_demande()
            self._appliquer_demande_tec()
        except Exception:
            pass

        # Relecture TEC (temp/PWM/consigne) toutes les 2 s — display
        # permanent, empilement démarré ou non.
        if (self.cam_pilotee is not None
                and time.monotonic() - self._tec_dernier_t0 >= 2.0):
            self._tec_dernier_t0 = time.monotonic()
            try:
                self._tec_dernier = self.cam_pilotee.lire_refroidissement()
            except Exception:
                pass

        if self.pending_settings is not None:
            self.camera.apply_settings(*self.pending_settings)  # pyright: ignore[reportOptionalMemberAccess]
            self.pending_settings = None

        # Jalon 27 : OFFSET (contrôle 7, SDK QHY) — demande posée par
        # le thread Tk, exécutée ICI ; no-op silencieux pour les sources
        # qui n'ont pas d'offset (base no-op).
        if self.pending_offset is not None:
            off, self.pending_offset = self.pending_offset, None
            try:
                self.camera.definir_offset(off)  # pyright: ignore[reportOptionalMemberAccess]
            except Exception:
                pass

    def _worker_cadence_dossier(self):
        """Cadence de lecture des sources DOSSIER — jalons 42 / v2.41.0 (106c).

        Corps repris VERBATIM de `_worker` (commentaires d'origine conservés).
        Renvoie True quand l'empilement étant EN PAUSE sur une source FICHIERS,
        le tour doit se TERMINER sans rien lire (le bloc qui portait
        `continue`) ; sinon il effectue au plus le scan périodique de la cadence
        et renvoie False. `self.cadence_lecture` reste lu DIRECTEMENT (le seam
        `WorkerConfig` n'est pas consommé ici : la leçon du 106b interdit
        d'ajouter du code sur le chemin de la boucle)."""
        # v2.41.0 : empilement EN PAUSE sur une source FICHIERS → on ne lit
        # RIEN. Pourquoi : une brute lue pendant la pause était marquée
        # « traitée » puis JETÉE (le `if not self.empilement_on` ci-dessous
        # ne gardait que la lecture d'une caméra live) — elle ne pouvait
        # plus JAMAIS être empilée, ni à la reprise, ni après une nouvelle
        # remise à zéro. C'est exactement la fenêtre « je finis une cible,
        # je prépare la suivante » (constat d'Alain, 28/09/2026). Le dossier
        # est seulement SCANNÉ, pour que l'état « brutes en attente » reste
        # juste ; les fichiers attendent sur le disque.
        if not self.empilement_on and self._cadence_dossier():
            maintenant = time.monotonic()
            if maintenant >= self._prochain_scan:   # au plus toutes les 0,4 s
                try:
                    self.camera.scanner()  # pyright: ignore[reportAttributeAccessIssue]
                except Exception:
                    pass
                self._prochain_scan = maintenant + 0.4
            self._servir_demandes_sans_frame()
            time.sleep(0.05)
            return True

        # Jalon 42 : cadence d'empilement (sources dossier, cf.
        # _autoriser_lecture). Le scan SANS lecture ne tourne que si une
        # cadence est posée, au plus toutes les 0,4 s — il permet de
        # connaître les brutes EN ATTENTE SUR LE DISQUE avant de décider
        # de lire (sinon la décision ne porterait que sur ce qui a déjà
        # été détecté, et chaque brute isolée serait lue immédiatement).
        if self.cadence_lecture > 0 and self._cadence_dossier():
            maintenant = time.monotonic()
            if maintenant >= self._prochain_scan:
                try:
                    self.camera.scanner()  # pyright: ignore[reportAttributeAccessIssue]
                except Exception:
                    pass
                self._prochain_scan = maintenant + 0.4
        return False

    def _worker_reinitialiser(self):
        """Remise à zéro de session — servie en TÊTE de boucle (jalon 106b).

        Corps repris VERBATIM de `_worker` (commentaire d'origine conservé :
        jalons 26 et 26b), découpé en sous-méthode par le jalon 106b. Seule
        différence entre « ▶ Démarrer » et « Réinitialiser » : le second ne
        RELANCE pas l'empilement (il reste en pause)."""
        if not (self.empilement_start_request or self.reset_request):
            return
        demarrer = bool(self.empilement_start_request)
        self.empilement_start_request = self.reset_request = False
        self.empilement_on = False
        self.aligner = StarAligner()
        self.stacker = None
        self.disp.reset()          # stats d'affichage repartent de zéro
        self._vl_frames = None     # le 1er empilement relancera le solveur
        self._rendu_differ = None  # jalon 80 : aucun rendu en attente
        self.bad_frames, self.fps = 0, 0.0
        self.floues_rejetees = 0   # jalon 17 : compteur de session
        self._fwhm_hist = []       # jalon 17 : mesures de session neuve
        self._fwhm_par_role = {}   # jalon 19 : idem, PAR RÔLE (compo)
        self.seeing, self.seeing_msg = None, ""   # jalon 10
        self._seeing_t0 = 0.0      # → dès la 1re frame
        self.disp.vl_seeing = None   # jalon 12 : PSF de session neuve
        self.show_stack = None
        self.last_show = None
        self._session += 1         # invalide tout traitement externe en vol
        self._vider_archive()      # jalon 15/16 : archive de session neuve
        self.restack_request = False
        self._ref_score = self._ancre_score = None
        self._ancre_idx = None
        self._ancre_role = None
        self._restack_depuis = 0
        self.restack_info = ""     # jalon 18 : état dédié de session neuve
        self.restack_couleur = "#888888"
        self.restack_total = 0
        self.restack_hist = []
        # Jalon 56 : astrométrie de session neuve — indices conservés
        # (ils viennent de l'UI/instantané), WCS oublié.
        self.suivi_astro.reset()
        self.astro_info = ""
        self.astro_couleur = "#888888"
        self._astro_wcs_secours = None
        self._astro_aveugles = 0
        self._astro_dernier_aveugle = 0.0
        self._astro_fov_essayes = set()
        self._astro_balayage = None
        self._astro_source = ""
        # Jalon 56 (étape 4) : photométrie de session neuve.
        self.photometrie.reset()  # pyright: ignore[reportOptionalMemberAccess]
        self.photo_info = ""
        self.photo_couleur = "#888888"
        self._photo_essais = 0
        self._photo_dernier = 0.0
        self._photo_gains_pose = {}
        # Jalon 58 : SPCC de session neuve (mêmes raisons).
        if getattr(self, "spcc", None) is not None:
            self.spcc.reset()  # pyright: ignore[reportOptionalMemberAccess]
        self.spcc_info = ""
        self.spcc_couleur = "#888888"
        self._spcc_essais = 0
        self._spcc_dernier = 0.0
        self.proc_show = self.proc_full = None
        self.proc_entete = None           # v2.38.3
        self.proc_new = False
        self.save_asseen_request = None   # sauvegarde « tel que vu » annulée
        self.asseen_busy = False
        self.asseen_result = None
        self.ext_request = False
        self.ext_busy = False
        self.ext_state = "idle"
        self.ext_t0 = None
        self._ext_popup = False
        self.zoom, self.view_cx, self.view_cy = 1.0, None, None
        self._last_disp = None
        self.q = queue.Queue(maxsize=2)
        if isinstance(self.camera, QHYCamera):
            # Purge de la file du SDK UNIQUEMENT pour un flux live
            # (les sources « dossier » consommeraient de VRAIES
            # frames — jamais jetées).
            t_purge = time.monotonic()
            while time.monotonic() - t_purge < 0.3:
                self.camera.read()
        self.empilement_on = demarrer   # « Réinitialiser » ne démarre pas

    def _worker_empiler_frame(self, frame, role, last_good, t0):
        """Traite une brute CALIBRÉE : filtre défocalisation, archivage,
        (re)création de l'empilement, alignement et empilement (jalon 106b).

        Corps repris VERBATIM de `_worker`. Consomme le « seam » `WorkerConfig`
        (bâti ICI, au point d'usage, pour ne rien ajouter au chemin de la
        boucle) : le rejet kappa-sigma (kappa, méthode, fenêtre) est lu sur
        l'instantané `cfg` à la création des empileurs — résultat identique AU
        BIT. Renvoie `(sauter, last_good, stack)` : `sauter` = brute REJETÉE
        (très défocalisée), le tour suivant reprend sans empiler ; sinon `stack`
        est la moyenne courante (None si l'alignement a refusé la frame)."""
        # Jalon 106b : instantané typé des paramètres de travail (seam
        # `WorkerConfig`) — construit ici seulement, pour laisser le chemin de
        # la boucle strictement inchangé.
        cfg = WorkerConfig.depuis(self)
        # Jalon 17 : filtre anti-brutes TRÈS DÉFOCALISÉES — AVANT tout le
        # reste (une frame rejetée n'est ni archivée ni empilable, donc
        # jamais ramenée par un re-stack). Rejet d'office, case pour
        # désactiver (décision d'Alain). La mesure (~15 ms) est presque
        # rien devant une pose de 120 s. La frame rejetée est comptée,
        # signalée sur la ligne d'alignement, et le worker respire (au
        # plus 20 analyses/s) sans empiler ni déclencher de re-calage.
        verdict = self._filtre_floue(frame, role=role)
        if verdict:
            self.floues_rejetees += 1
            self.align_info = verdict
            time.sleep(max(0.0, 1.0 / 20.0 - (time.perf_counter() - t0)))
            return True, last_good, None

        # Jalon 15 : chaque frame calibrée est archivée (dossier temp de
        # session, garde-fous débit/taille) — matière du futur re-stack
        # « à la Siril » (recalcul sur une meilleure référence). Aucun
        # échec d'archivage n'interrompt l'empilement (erreur exposée).
        # Jalon 19 : extraction du CANAL du rôle (mono → tel quel ; CFA
        # débayerisé → canal dominant du rôle, CANAUX_CFA). Tout le reste
        # du flux (référence, alignement, empilement) travaille sur ce
        # canal 2D — le repère reste COMMUN (aligneur unique, décision
        # tranchée du 18/09/2026).
        img_travail = (extraire_canal(frame, role)
                       if self._mode_compo else frame)
        if self.stacker is not None \
                and self.stacker.shape != img_travail.shape:
            # changement de géométrie : les frames archivées (autre
            # taille) ne sont plus ré-empilables → archive neuve
            self._vider_archive()
        if self._mode_compo:          # archive PAR RÔLE (re-stack jalon 20)
            chemin_archive = self.archives.setdefault(
                role, _globals_app().ArchiveFrames()).ajouter(frame)
        else:
            chemin_archive = self.archive.ajouter(frame)
        if chemin_archive is not None:
            if self._mode_compo:
                # Jalon 20 : score qualité PAR RÔLE — mesuré sur le CANAL
                # EXTRAIT (img_travail, la même image que l'alignement),
                # donc comparable d'une couche à l'autre pour choisir la
                # meilleure brute TOUS RÔLES confondus.
                self._scores_par_role.setdefault(role, []).append(
                    self._score_frame(img_travail))
                self._restack_depuis += 1
            else:
                # Jalon 16 : score qualité (nb d'étoiles détectées, canal
                # vert) de chaque brute archivée — matière du choix de
                # référence à la Siril (meilleure référence + re-stack).
                self._scores.append(self._score_frame(frame))
                self._restack_depuis += 1

        # (re)création de l'empilement / nouvelle référence — SEULEMENT
        # si la frame a passé le filtre jalon 17 (une brute très floue ne
        # doit jamais devenir la référence d'alignement ni créer
        # l'empilement — c'est le défaut que le filtre élimine).
        # Jalon 21 (décision d'Alain) : HOO/SHO — l'ancre initiale est
        # TOUJOURS une brute Ha. Tant qu'aucune brute Ha n'est arrivée,
        # les frames des autres rôles (déjà archivées) ne créent PAS
        # l'empilement ; à la 1re Ha, l'ancre est posée sur elle et les
        # frames archivées entre-temps sont rejouées (via
        # _do_restack_compo, exactement comme un re-stack).
        deja_rejoue = False
        if (self._mode_compo and self._narrowband_ha()
                and self.stacker is None and role != "Ha"):
            self.align_info = ("en attente d'une brute Ha "
                               "(référence d'alignement)…")
        # v2.41.0 : `reset_request` n'est PLUS lu ici — la remise à zéro
        # complète est servie en TÊTE de boucle (donc même en pause) ; la
        # laisser ici la consommerait sans refaire le reste (archive,
        # compteurs, mesures). Ne reste donc que le vrai changement de
        # géométrie.
        elif (self.stacker is None
                or self.stacker.shape != img_travail.shape):
            etait_vide = self.stacker is None
            # Jalon 106b : `kappa` peut valoir None (« Off ») — les empileurs
            # l'acceptent À L'EXÉCUTION (bancs et `app.py` l'emploient) mais
            # pyright lit leurs `k` typés `float` : ignores CIBLÉS sur les 2
            # appels ci-dessous.
            if self._mode_compo:       # façade multi-rôles : un stacker
                self.stacker = CompositeStacker(   # par rôle, mean() =
                    self._compo_nom,   # composite (cadre commun)
                    k=cfg.kappa, method=cfg.rejet_methode,  # pyright: ignore[reportArgumentType]
                    window=cfg.rejet_fenetre)
                # Jalon 19 phase 3 : gains + canal L posés dès la
                # création (instantanés tenus à jour par _tick).
                self.stacker.gains = dict(self._compo_gains or {})
                self.stacker.mode_l = self._compo_mode_l
                self.stacker.normalisation_commune = bool(
                    self._norm_commune)          # v2.36.0 (option)
            else:
                self.stacker = LiveStacker(img_travail.shape, k=cfg.kappa,  # pyright: ignore[reportArgumentType]
                                           method=cfg.rejet_methode,
                                           window=cfg.rejet_fenetre)
            self.stacker.wb_auto = bool(self.var_wb.get())
            self.stacker.wb_force = float(self.var_wb_force.get())
            # Jalon 54 : recalage « Linear Fit » posé dès la création —
            # via l'INSTANTANÉ (le worker n'a jamais le droit de lire
            # les variables Tk) ; les changements de la case passent
            # par _on_linear_fit (thread principal).
            self.stacker.linear_fit = bool(self._fit_actif)
            self.stacker.linear_fit_mode = self._fit_mode
            self.aligner.reset()
            # Jalon 21 : HOO/SHO → TRIANGLES seuls pour toute la session.
            self.aligner.triangles_seuls = self._narrowband_ha()
            self._definir_reference(img_travail)
            self.disp.reset()          # stats d'affichage repartent de zéro
            # Jalon 21 : 1re brute Ha → ancre + rejeu des frames
            # archivées entre-temps (les autres rôles arrivés avant).
            if (etait_vide and self._mode_compo and self._narrowband_ha()
                    and role == "Ha"
                    and self.archives.get(role, _globals_app().ArchiveFrames()).n > 0):
                idx_ancre = len(self.archives[role].chemins) - 1
                self._ancre_role, self._ancre_idx = role, idx_ancre
                info = self._do_restack_compo(
                    f"ancre {role} (démarrage)", ancre_role=role,
                    ancre_idx=idx_ancre)
                if info:
                    self.align_info = info
                deja_rejoue = True

        stack = None
        if self.stacker is not None and not deja_rejoue:
            M, ok = self.aligner.compute(img_travail)
            if ok:
                aligned = cv2.warpAffine(img_travail, M,
                                         (img_travail.shape[1],
                                          img_travail.shape[0]),
                                         flags=cv2.INTER_LINEAR)
                if self._mode_compo:       # routage vers le stacker du rôle
                    self.stacker.role_courant = role
                self.stacker.add(aligned)
                self.stacker.note_alignement(M)   # intersection des zones
                last_good = aligned
                self._ref_bad = 0
            else:
                self.bad_frames += 1
                self._ref_bad += 1
                # Jalon 13 : dossier MIXÉ (brutes de plusieurs nuits, p.ex.
                # TargetSchedulerSequence de NINA) — si TOUT refuse alors que
                # l'empilement est quasi vide (≤ 2 frames), la référence
                # (1re frame, autre nuit — ou une ancre faussée) ne convient
                # à rien : on la recale sur la frame courante. Sûr : ≤ 2
                # frames d'ancien repère dans l'accumulation seront rejetées
                # ensuite par la médiane Winsorized (dilution). (Jalon 17 :
                # la frame courante a déjà passé le filtre défocalisation.)
                if self.stacker.n <= 2 and self._ref_bad >= 3:
                    self._definir_reference(frame)
                    self._ref_frames = self._ref_bad = 0
            self._ref_frames += 1
            # Jalon 13 : ligne d'état de l'alignement (Δ, θ, méthode ou refus).
            if ok and self.aligner.dernier:
                d = self.aligner.dernier
                self.align_info = (f"Δ=({d['dx']:+.1f},{d['dy']:+.1f}) px · "
                                   f"θ {d['angle']:+.2f}° · {d['methode']}")
            elif not ok:
                self.align_info = "refus (frame non empilée)"

            stack = self.stacker.mean()
        return False, last_good, stack

    def _worker_restack(self):
        """Re-stack sur la meilleure brute archivée — bouton ou AUTO (106b).

        Corps repris VERBATIM de `_worker` (jalons 16 et 20). Renvoie
        `(fait, stack)` : `fait` True quand un re-stack a eu lieu (bouton
        consommé) ; `stack` est alors la moyenne recalculée (affichage
        immédiat), sinon None."""
        # Jalon 16 : re-stack sur la MEILLEURE brute archivée (choix de
        # référence à la Siril) — auto si une brute bat nettement la
        # référence courante (marge en étoiles), ou sur bouton. Le
        # recalcul rejoue TOUTES les frames archivées : celles qui
        # avaient refusé avec l'ancienne référence ont une seconde chance.
        # Jalon 20 : le re-stack s'applique AUSSI au mode compo — la
        # meilleure brute, TOUS RÔLES confondus, re-ancre l'aligneur
        # PARTAGÉ et toutes les couches sont recalculées depuis les
        # archives PAR RÔLE (chaque couche a ses mauvaises frames).
        n_arch = (sum(a.n for a in self.archives.values())
                  if self._mode_compo else self.archive.n)
        if (self.stacker is not None and (
                self.restack_request
                or (n_arch >= _globals_app().RESTACK_MIN_FRAMES
                    and self._restack_depuis >= _globals_app().RESTACK_CADENCE
                    and self._veut_restack()))):
            raison = "bouton" if self.restack_request else "auto"
            self.restack_request = False
            info = self._do_restack(raison)
            if info:
                self.align_info = info
                return True, self.stacker.mean()   # affichage immédiat
        return False, None

    # ========================================================================
    # Jalon 106d : MESURES (astrométrie + photométrie / SPCC) — CALCUL
    # ========================================================================
    # Méthodes reprises VERBATIM de `ui/app.py`. Le worker MESURE ; l'AFFICHAGE
    # (`_maj_*_etat` / `_maj_*_vue`, dialogues de nom de cible, en-têtes FITS de
    # sortie) reste dans `ui/app.py`, appelé via `self`.

    def _worker_mesures(self):
        """Mesures de l'empilement — servi APRÈS le re-stack (jalon 106d).

        Corps repris VERBATIM de `_worker` (commentaire d'origine conservé) :
        astrométrie, puis photométrie (le WCS doit être résolu), puis SPCC. La
        grille décrite est la COURANTE (la propagation vient d'y pourvoir) et
        l'état poussé à l'UI est construit APRÈS, avec le bon texte."""
        # Jalon 56 : astrométrie de l'empilement — APRÈS le re-stack (le
        # WCS doit décrire la grille COURANTE : la propagation vient d'y
        # pourvoir), AVANT la construction de l'état poussé à l'UI (la
        # ligne d'état part alors avec le bon texte).
        if self.stacker is not None and self.stacker.n > 0:
            self._astro_tour(self.stacker)
            # Jalon 56 (étape 4) : photométrie — APRÈS l'astrométrie (elle
            # a besoin du WCS résolu) ; mesure SANS effet sur l'image.
            self._photo_tour(self.stacker)
            # Jalon 58 : SPCC absolue — APRÈS la photométrie (mêmes
            # prérequis) ; elle PRIORISE ses coefficients sur les gains
            # Gaia relatifs quand sa case est cochée.
            self._spcc_tour(self.stacker)

    def _astro_tour(self, stacker):
        """Appelé par le worker APRÈS le re-stack (la grille est alors celle
        qui sera affichée et sauvegardée) : indices → RÉSOLUTION UNIQUE → état.

        - WCS déjà résolu : rien à faire, la ligne rappelle la mesure (et le
          nombre de propagations) ;
        - case décochée / indices manquants : la ligne DIT pourquoi (jamais de
          silence) ; en mode dossier, une lecture des indices dans l'en-tête
          de la brute courante est tentée AVANT de renoncer ;
        - sinon `peut_essayer` décide (frames empilées, délai, plafond) : une
          résolution coûte du temps d'acquisition, elle n'est tentée que sur
          un empilement déjà consistant, et au plus une fois par délai."""
        if self.suivi_astro is None or stacker is None or stacker.n <= 0:
            return
        if self.suivi_astro.resolu:
            self._maj_astro_etat()
            return
        if not self._astro_actif:
            self.astro_info = "Astrométrie : désactivée"
            self.astro_couleur = "#888888"
            return
        if self._astro_indices is None:
            self._astro_indices_entete()
        if self._astro_indices is None:
            # Jalon 56 : ni saisie ni en-tête de brute (caméra live sans
            # en-tête FITS) → REPLI ASTAP « aveugle » : c'est LUI qui fournit
            # les indices (son centre), puis le solveur interne reprend la main
            # sur un champ indicé fiable (chemin validé par _diag_solve_reel).
            self._astro_aveugle(stacker)
        if self._astro_indices is None:
            self.astro_info = ("Astrométrie : " + (self._astro_msg_indices
                               or "indices de la cible manquants"))
            self.astro_couleur = "#c98a00"
            return
        if not self.suivi_astro.pret:
            self.suivi_astro.indice(*self._astro_indices)
        if not self.suivi_astro.peut_essayer(stacker.n):
            raison = self.suivi_astro.raison_attente()
            if raison:
                self.astro_info = f"Astrométrie : {raison}"
                self.astro_couleur = "#c98a00"
            return
        img = stacker.mean(recadre=False)
        if img is None:
            return
        # Message posé AVANT le calcul : le thread Tk le lit PENDANT la
        # résolution (le worker, lui, est occupé) — l'utilisateur voit ainsi
        # d'où vient la pause d'acquisition d'une frame environ.
        self.astro_info = (f"Astrométrie : résolution en cours "
                           f"({stacker.n} frames)…")
        self.astro_couleur = "#888888"
        okk, msg = self.suivi_astro.resoudre_sur(img, n_frames=stacker.n)
        if okk:
            self._maj_astro_etat()
            return
        # Jalon 56 : le solveur INTERNE a refusé — si ASTAP avait résolu en
        # aveugle, son WCS devient le WCS de la session (repli prévu par la
        # décision d'Alain : « ASTAP = référence indépendante/repli »).
        if self._astro_wcs_secours is not None:
            ok2, msg2 = self.suivi_astro.adopter(self._astro_wcs_secours,
                                                 img.shape[:2])
            if ok2:
                self._astro_wcs_secours = None     # adopté : plus de secours
                self._astro_source = "ASTAP (repli)"
                self._maj_astro_etat()
                return
            msg = f"{msg} — repli ASTAP refusé ({msg2})"
        essais = self.suivi_astro.essais
        self.astro_couleur = ("#c98a00" if essais < astro_mod.ASTRO_MAX_ESSAIS
                              else "#d04040")
        suite = ("réessai automatique dès que l'empilement double"
                 if essais < astro_mod.ASTRO_MAX_ESSAIS else "plafond atteint")
        self.astro_info = (f"Astrométrie : échec — {msg} "
                           f"({essais}/{astro_mod.ASTRO_MAX_ESSAIS} essais, "
                           f"{suite})")

    def _astro_aveugle(self, stacker):
        """Jalon 56 — REPLI ASTAP : quand AUCUN indice n'est disponible (ni
        saisie, ni en-tête de brute), ASTAP balaie le ciel seul (`fov` auto) et
        son centre sert d'indice au solveur interne. Le WCS rendu est GARDÉ
        (`_astro_wcs_secours`) : si le solveur interne refuse ensuite, il est
        adopté tel quel (repli) au lieu de laisser la session sans astrométrie.

        Appel LENT (balayage complet : plusieurs secondes à une minute) → au
        plus `ASTRO_MAX_AVEUGLES` fois par session, espacées du même délai que
        les essais internes, et jamais pendant qu'un empilement est trop court.
        Sans astap_cli installé, l'échec est immédiat et parfaitement clair."""
        if self._astro_aveugles >= astro_mod.ASTRO_MAX_AVEUGLES:
            self._astro_msg_indices = (f"aucun indice (ASTAP aveugle : plafond "
                                       f"de {astro_mod.ASTRO_MAX_AVEUGLES} "
                                       f"tentatives atteint)")
            return
        # SONDE des bases ASTAP, UNE fois par session (listdir d'un dossier de
        # plus de 1000 fichiers) : sans base de BALAYAGE (G18/H18…), ASTAP ne
        # peut PAS chercher sans position — inutile de bloquer l'acquisition
        # pour un échec certain (constat réel du 23/09/2026 : avec la seule
        # base D80, tout balayage échoue en ~0,4 s). On le DIT à l'utilisateur.
        if self._astro_balayage is None:
            self._astro_balayage = astro_mod.balayage_possible()
            self._astro_bases = (", ".join(sorted(astro_mod.bases_installees()))
                                 or "aucune")
        if not self._astro_balayage:
            self._astro_msg_indices = (
                f"aucun indice (ASTAP : bases installées = {self._astro_bases}; "
                f"PAS de base de BALAYAGE — saisir AD/Dec approximatifs, ou "
                f"installer une base G18/H18)")
            return
        if stacker.n < astro_mod.ASTRO_MIN_FRAMES:
            return
        # Un seul essai PAR VALEUR de champ : rebalayer à l'identique redonne
        # exactement le même échec (« No solution found! », constat réel).
        fov = float(self._astro_champ_seul or 0.0)
        if fov in self._astro_fov_essayes:
            self._astro_msg_indices = (
                f"aucun indice (ASTAP déjà tenté avec un champ de "
                f"{fov:.3f}° : balayage NON répété — saisir AD/Dec, ou "
                f"corriger le champ)")
            return
        self._astro_fov_essayes.add(fov)
        t = time.monotonic()
        if (self._astro_aveugles
                and t - self._astro_dernier_aveugle
                < astro_mod.ASTRO_ESSAI_DELAI_S):
            return
        img = stacker.mean(recadre=False)
        if img is None:
            return
        self._astro_aveugles += 1
        self._astro_dernier_aveugle = t
        self.astro_info = (
            "Astrométrie : aucun indice — balayage ASTAP en cours"
            + (f" (champ indicatif {fov:.3f}°)…" if fov
               else " (sans champ indicatif : LENT)…"))
        self.astro_couleur = "#c98a00"
        try:
            wcs, ra, dec, champ, msg = astro_mod.resoudre_aveugle_astap(
                img, fov_deg=fov)
        except Exception as exc:       # un outil externe ne tue jamais le worker
            wcs, ra, dec, champ = None, None, None, None
            msg = f"exception ASTAP ({exc})"
        if wcs is None or ra is None:
            self._astro_msg_indices = f"ASTAP aveugle : {msg}"
            self.astro_info = f"Astrométrie : {self._astro_msg_indices}"
            self.astro_couleur = "#c98a00"
            return
        self._astro_wcs_secours = wcs
        self._astro_indices = (ra, dec, champ)
        self._astro_msg_indices = ""
        self._astro_source = "ASTAP (aveugle)"
        self.suivi_astro.indice(ra, dec, champ)
        self.astro_info = (f"Astrométrie : indices d'ASTAP — {msg}"
                           f" → solve interne…")
        self.astro_couleur = "#888888"

    def _photo_tour(self, stacker):
        """Mesure le zéro-point PAR BANDE quand l'astrométrie est RÉSOLUE (le
        WCS est indispensable : c'est lui qui relie les étoiles de l'image au
        catalogue Gaia), l'empilement assez profond et la case cochée.

        Mesure UNE fois par session (réessais espacés, plafonnés) et SANS AUCUN
        effet sur l'image : l'application de ces gains au stacker est l'étape 5.
        Le catalogue (1,1 Go) n'est lu QUE par une mesure — d'où le plafond."""
        if self.photometrie is None or stacker is None or stacker.n <= 0:
            return
        if self.photometrie.valide:
            return                     # déjà mesuré : rien à refaire
        if not self._photo_actif:
            return
        if self.suivi_astro is None or not self.suivi_astro.resolu:
            return                     # sans WCS : aucune photométrie possible
        if stacker.n < astro_mod.ASTRO_MIN_FRAMES:
            return
        if self._photo_essais >= photo_mod.MAX_ESSAIS:
            self.photo_info = (f"Photométrie : {self.photometrie.derniere_erreur}"
                               f" — {self._photo_essais} essais, plafond atteint")
            self.photo_couleur = "#d04040"
            return
        t = time.monotonic()
        if (self._photo_essais
                and t - self._photo_dernier < photo_mod.DELAI_ESSAI_S):
            return
        canaux, wcs, forme = self._photo_canaux(stacker)
        if not canaux or wcs is None:
            return
        self._photo_essais += 1
        self._photo_dernier = t
        self.photo_info = ("Photométrie : mesure du zéro-point en cours "
                           f"({stacker.n} frames, "
                           f"{len(canaux)} bande(s))…")
        self.photo_couleur = "#888888"
        try:
            res, msg = self.photometrie.mesurer(canaux, wcs, forme=forme)
        except Exception as exc:       # une mesure ne tue jamais le worker
            res, msg = None, f"exception ({exc})"
        if res is None:
            self.photo_info = f"Photométrie : {msg}"
            self.photo_couleur = ("#c98a00"
                                  if self._photo_essais < photo_mod.MAX_ESSAIS
                                  else "#d04040")
            return
        self._maj_photo_etat()

    @staticmethod
    def _source_rgb(stacker):
        """L'empilement porte-t-il les trois canaux R/G/B ? VRAI en composition
        multi-rôles (le composite est recoloré) ET pour une source COULEUR
        (capteur OSC en mode dossier) ; FAUX en mono. Purement géométrique (la
        forme d'UNE frame), donc GRATUIT : aucune image à moyenner pour le
        savoir — la SPCC a besoin des trois canaux, et le dire vaut mieux que
        d'échouer."""
        shp = getattr(stacker, "shape", None) or getattr(stacker, "_shape", None)
        try:
            return shp is not None and len(tuple(shp)) == 3
        except TypeError:
            return False

    def _photo_canaux(self, stacker):
        """Canaux (bandes) + WCS de la MÊME grille pour la photométrie.

        Grille RECADRÉE (celle de la vue et des sauvegardes) — en composition,
        les cartes PAR RÔLE (`moyennes`) sont les bandes ; pour une source
        COULEUR (capteur OSC en mode dossier), les trois canaux R/G/B de
        l'empilement BRUT (`corrections=False`) sont les bandes — c'est sur
        cette image-là que la SPCC doit mesurer : un équilibrage ou un
        recalage déjà appliqué fausserait les ratios de couleur (et les gains
        se cumuleraient). En mono, une seule bande « L ». Le WCS est celui de
        cette grille exacte (recadrage d'intersection inclus) : les deux
        DOIVENT décrire la même grille, sinon l'appariement au catalogue
        serait faux. → (canaux, WCS, forme)."""
        cadre = getattr(stacker, "cadre", None)
        try:
            if hasattr(stacker, "moyennes"):
                canaux = stacker.moyennes(recadre=True) or {}
            else:
                img = stacker.mean(corrections=False)
                if img is None:
                    canaux = {}
                elif getattr(img, "ndim", 2) == 3:
                    a = (img if img.shape[-1] == 3
                         else np.transpose(img, (1, 2, 0)))
                    canaux = {"R": a[..., 0], "G": a[..., 1], "B": a[..., 2]}
                else:
                    canaux = {"L": img}
        except Exception as exc:
            self.photo_info = f"Photométrie : canaux indisponibles ({exc})"
            self.photo_couleur = "#c98a00"
            return {}, None, None
        canaux = {b: v for b, v in canaux.items() if v is not None}
        if not canaux:
            return {}, None, None
        forme = tuple(np.asarray(next(iter(canaux.values()))).shape[:2])
        wcs, msg = self.suivi_astro.wcs_grille(cadre, forme=forme)
        if wcs is None:
            self.photo_info = f"Photométrie : WCS indisponible ({msg})"
            self.photo_couleur = "#c98a00"
            return {}, None, None
        return canaux, wcs, forme

    # -------------------------------- jalon 58 : SPCC absolue
    def _spcc_tour(self, stacker):
        """Calcule les coefficients SPCC de la session (une fois, réessais
        espacés). Mêmes prérequis que la photométrie (WCS résolu, empilement
        assez profond) PLUS les trois canaux R/G/B et la base de profils."""
        if self.spcc is None or stacker is None or stacker.n <= 0:
            return
        if self.spcc.valide:
            return                     # déjà calibré : rien à refaire
        if not self._spcc_actif or not getattr(self, "_spcc_dispo", False):
            return
        if not (self._mode_compo or self._source_rgb(stacker)):
            return                     # il faut une image COULEUR (R, G et B)
        if self.suivi_astro is None or not self.suivi_astro.resolu:
            return
        if stacker.n < astro_mod.ASTRO_MIN_FRAMES:
            return
        if self._spcc_essais >= spcc_mod.MAX_ESSAIS:
            self.spcc_info = (f"SPCC : {self.spcc.derniere_erreur}"
                              f" — {self._spcc_essais} essais, plafond atteint")
            self.spcc_couleur = "#d04040"
            return
        t = time.monotonic()
        if (self._spcc_essais
                and t - self._spcc_dernier < spcc_mod.DELAI_ESSAI_S):
            return
        canaux, wcs, forme = self._photo_canaux(stacker)
        if not canaux or wcs is None:
            return
        capteur, filtres, blanc = self._spcc_profils()
        self._spcc_essais += 1
        self._spcc_dernier = t
        self.spcc_info = ("SPCC : calibration en cours (spectres Gaia × profils "
                          f"capteur/filtres, {stacker.n} frames)…")
        self.spcc_couleur = "#888888"
        try:
            res, msg = self.spcc.mesurer(canaux, wcs, capteur, filtres, blanc,
                                         forme=forme,
                                         mode=("osc" if self._spcc_osc()
                                               else "mono"))
        except Exception as exc:       # une mesure ne tue jamais le worker
            res, msg = None, f"exception ({exc})"
        if res is None:
            self.spcc_info = f"SPCC : {msg}"
            self.spcc_couleur = ("#c98a00"
                                 if self._spcc_essais < spcc_mod.MAX_ESSAIS
                                 else "#d04040")
            self._maj_spcc_vue()
            return
        # Sur COMBIEN de frames la mesure a été faite : la mesure SPCC est faite
        # UNE fois par session (SessionSpcc) — le dire évite de croire que la
        # case ne « rafraîchit » plus rien (constat d'Alain, 25/09/2026).
        if isinstance(self.spcc.diag, dict):
            self.spcc.diag.setdefault("frames", int(stacker.n))
        self._maj_spcc_etat()
        self._maj_spcc_vue()

    def _astro_indices_entete(self):
        """Indices de la cible déduits de l'en-tête de la brute courante
        (source DOSSIER) quand la saisie est vide — lecture STRICTE
        (OBJCTRA/OBJCTDEC + FOCALLEN/XPIXSZ), jamais de supposition : sans
        mots-clés explicites, rien n'est inventé et le message le dit."""
        chemin = getattr(self.camera, "last_file", "") or ""
        if not chemin:
            try:      # composition : dernier fichier du rôle le plus récent
                stats = self.camera.stats() or {}
                cands = [v.get("last_file") or "" for v in stats.values()]
                cands = [c for c in cands if c]
                if cands:
                    chemin = max(cands, key=os.path.getmtime)
            except Exception:
                chemin = ""
        if not chemin:
            return
        ra, dec, champ, msg = astro_mod.indices_entete_fits(chemin)
        if ra is None or champ is None:
            self._astro_msg_indices = msg
            return
        self._astro_indices = (ra, dec, champ)
        self._astro_msg_indices = ""
        self._astro_source = f"en-tête {os.path.basename(chemin)}"
        self.suivi_astro.indice(ra, dec, champ)

    def _astro_propager_restack(self, ancien, ref):
        """Jalon 56 : le RÉEMPILEMENT change la référence d'alignement, donc la
        GRILLE de l'empilement — le WCS est PROPAGÉ (aucun re-solve, aucun
        accès au catalogue : décision d'Alain du 22/09/2026).

        `M10` (nouvelle grille → ANCIENNE grille) est mesuré par un aligneur
        PRIVÉ : référence = l'ancien empilement COMPLET (`mean(recadre=False)`
        — le même repère que toutes les frames alignées, contrat du jalon 13),
        source = la nouvelle référence. C'est exactement le chemin confronté au
        StarAligner réel par le banc du jalon 56 (étape 3) ; l'aligneur de la
        SESSION n'est pas touché (il est sur le point d'être re-référencé).

        Échec (appariement refusé, WCS absent) : SANS EFFET sur l'empilement,
        message exposé sur la ligne dédiée — un WCS d'ancienne grille est
        signalé, jamais présenté comme valable."""
        if self.suivi_astro is None or not self.suivi_astro.resolu:
            return
        try:
            base = ancien.mean(recadre=False)
        except Exception:
            base = None
        if base is None:
            return
        al = StarAligner()
        al.triangles_seuls = bool(self.aligner.triangles_seuls)  # HOO/SHO
        try:
            al.set_reference(base)
            M, okk = al.compute(ref)
        except Exception as exc:
            self.astro_couleur = "#c98a00"
            self.astro_info = f"Astrométrie : propagation impossible ({exc})"
            return
        if not okk or M is None:
            self.astro_couleur = "#c98a00"
            self.astro_info = ("Astrométrie : propagation refusée (nouvelle "
                               "référence ↔ ancien empilement) — le WCS reste "
                               "celui de l'ancienne grille")
            return
        ok2, msg = self.suivi_astro.propager(M)
        if ok2:
            self._maj_astro_etat()
        else:
            self.astro_couleur = "#c98a00"
            self.astro_info = f"Astrométrie : propagation refusée — {msg}"
