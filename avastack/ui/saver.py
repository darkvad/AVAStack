# -*- coding: utf-8 -*-
"""Sauvegardes (FITS/TIFF/PNG) et en-têtes FITS de sortie — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 108 du chantier de refactoring. Ce
module regroupe tout ce qui ÉCRIT un fichier depuis l'application :

  - les sauvegardes DIRECTES déclenchées par l'interface : `_save` (empilement
    linéaire brut), `_save_canaux` (empilements par canal), `_save_asseen`
    (« tel que vu » étiré), `_save_traite_lineaire` (empilement traité linéaire)
    et `_save_proc` (résultat du traitement externe) ;
  - la CAPTURE des réglages de rendu (`_reglages_rendu`) et le contrôle préalable
    de la chaîne GraXpert live (`_gx_live_prete`) ;
  - le THREAD de sauvegarde pleine résolution (`_save_asseen_thread`) et sa
    chaîne par couche (`_couches_brutes`, `_couches_pleine_resolution`) ;
  - les EN-TÊTES FITS AUTO-DESCRIPTIFS de sortie (`_entete_reglages`,
    `_entete_externe`, `_astro_entete_sauvegarde`) ;
  - la FICHE DE RENDU (jalon 121) : `_fiche_actif`, `_fiche_contexte`,
    `_fiche_etat` (état APPLIQUÉ vs AFFICHÉ), `_fiche_source`, `_fiche_chaine`,
    `_ecrire_fiche` — le JSON compagnon `<image>.ava.json`, écrit ici même par
    le thread qui écrit l'image. Les décisions d'Alain et le format sont dans
    `avastack/fiche.py` et CLAUDE.md.

Les méthodes sont reprises VERBATIM : `App` hérite de `Saver`, donc `self`
reste l'instance `App` et le comportement est inchangé AU BIT. Les dépendances
de module (`gx_live`, `composition_mod`, `couleurs_mod`, `denoiser_local`,
`nettete_live`, `save_image`, `borner_lineaire`) sont importées ICI : ce sont
les MÊMES objets qu'`app.py` — les bancs qui patchent leurs ATTRIBUTS
(`ui.gx_live.appliquer = …`) restent donc effectifs.

Les attributs d'interface (constantes et variables Tk de la classe `App`) sont
DÉCLARÉS ici pour le typage statique (`pyright`) — aucune valeur, aucune
logique.
"""

from typing import Any, Callable

import numpy as np
import tkinter as tk

from ..images import borner_lineaire, save_image
from ..processing import DisplayProcessor
from ..processing import composition as composition_mod
from ..processing import couleurs as couleurs_mod
from ..processing import denoise as denoiser_local
from ..processing import sharpness as nettete_live
from ..external import live as gx_live
from .. import fiche as fiche_mod


def _globals_app():
    """Globals du module d'application `avastack.ui.app` — résolution TARDIVE.

    Écho des jalons 104/105a/107 : les bancs remplacent
    `avastack.ui.app.CONFIG` pour intercepter le vrai config.json. Lire ce global
    au MOMENT DE L'APPEL préserve cette interception ; en production c'est le
    MÊME objet que `avastack.config.CONFIG`."""
    from . import app as _app              # import TARDIF (évite le cycle)
    return _app


# Table de contrôle « APPLIQUÉ ↔ AFFICHÉ » (exigence d'Alain, fiche de rendu,
# jalon 121) : (clé du JSON, nom de la variable Tk, valeur réellement APPLIQUÉE
# par le rendu). Le lecteur reçoit (app, disp) — certaines grandeurs vivent sur
# `disp` (réglage appliqué au moteur), d'autres sur l'app elle-même (ex. le
# rayon de chroma de RÉFÉRENCE, que l'aperçu met à l'échelle). Elle sert à
# PROUVER que l'écran et le rendu ne divergent pas : le bug du 11/10/2026
# (« saturation bleue » APPLIQUÉE à 3,0 pendant que l'écran affichait 1,00)
# aurait été écrit NOIR SUR BLANC ici.
_CONTROLE_AFFICHAGE: tuple[tuple[str, str, Callable[[Any, Any], float]], ...] = (
    ("sigma_k", "var_sigk", lambda a, d: float(d.sigma_k)),
    ("target", "var_target", lambda a, d: float(d.target)),
    ("black", "var_black", lambda a, d: float(d.black)),
    ("white", "var_white", lambda a, d: float(d.white)),
    ("gamma", "var_gamma", lambda a, d: float(d.gamma)),
    ("saturation", "var_saturation", lambda a, d: float(d.saturation)),
    ("saturation_rouge", "var_sat_r", lambda a, d: float(d.sat_canaux[0])),
    ("saturation_verte", "var_sat_g", lambda a, d: float(d.sat_canaux[1])),
    ("saturation_bleue", "var_sat_b", lambda a, d: float(d.sat_canaux[2])),
    ("vl_target_bg", "var_vl_target", lambda a, d: float(d.vl_target_bg)),
    ("vl_log_d", "var_vl_logd", lambda a, d: float(d.vl_log_d)),
    ("vl_chroma_force", "var_vl_chroma_force", lambda a, d: float(d.vl_chroma_force)),
    # Le rayon de chroma de l'interface est une RÉFÉRENCE pleine résolution ; la
    # valeur de `disp` est mise à l'échelle de l'aperçu — on compare donc à la
    # référence, jamais à l'effectif (sinon faux écart systématique).
    ("vl_chroma_rayon", "var_vl_chroma_rayon", lambda a, d: float(a.rayon_chroma_ref)),
    ("vl_scnr_force", "var_vl_scnr_force", lambda a, d: float(d.vl_scnr_force)),
    ("vl_demagenta_force", "var_vl_demagenta_force",
     lambda a, d: float(d.vl_demagenta_force)),
    ("vl_boost_force", "var_vl_boost_force", lambda a, d: float(d.vl_boost_force)),
    ("vl_denoise_force", "var_vl_dn_force", lambda a, d: float(d.vl_denoise_force)),
    ("vl_sharp_iterations", "var_vl_sharp_iter",
     lambda a, d: float(d.vl_sharp_iterations)),
    # Les barres de l'histogramme sont en POUR CENT à l'écran (0..100) et en
    # FRACTION dans `disp` (0..1) : on compare dans l'unité AFFICHÉE (×100),
    # sinon on signalerait un « écart » qui n'en est pas un.
    ("bar_noir", "var_bar_noir", lambda a, d: float(d.bar_noir) * 100.0),
    ("bar_median", "var_bar_median", lambda a, d: float(d.bar_median) * 100.0),
    ("bar_blanc", "var_bar_blanc", lambda a, d: float(d.bar_blanc) * 100.0),
)


class Saver:
    """Mixin : sauvegardes (fichiers) et en-têtes FITS de sortie."""

    # Interface attendue sur l'hôte (`App`) — DÉCLARATIONS DE TYPAGE seulement.
    # Moteur d'affichage et empileur.
    disp: DisplayProcessor
    stacker: Any
    # État de session.
    running: Any
    _session: Any
    _mode_compo: Any
    # Mesures de la session (SPCC / photométrie) et corrections.
    _spcc_actif: Any
    _photo_gains_actif: Any
    _compo_gains: Any
    spcc: Any
    photometrie: Any
    suivi_astro: Any
    filtre_courant: Any
    rayon_chroma_ref: Any
    var_view: tk.Variable
    # Demandes de sauvegarde et résultat consommés par le thread / _tick.
    save_request: Any
    save_canaux_request: Any
    save_asseen_request: Any
    asseen_busy: Any
    asseen_result: Any
    asseen_titre: Any
    msg_outils: Any
    dernier_applicatif: Any
    astro_info: Any
    astro_couleur: Any
    proc_full: Any
    proc_entete: Any
    # Traitement externe (lu par `_entete_externe`).
    ext_job: Any
    # Méthodes de l'hôte (`App`, portées par d'autres mixins) appelées ici.
    _avertir: Callable[..., Any]
    _demander_dossier: Callable[..., Any]
    _dire: Callable[..., Any]
    _enregistrer_sous: Callable[..., Any]
    _nom_cible_pour_sauvegarde: Callable[..., Any]
    _sauver_png_annote: Callable[..., Any]
    _signaler: Callable[..., Any]

    def _save_canaux(self):
        """Sauvegarde des empilements PAR CANAL (jalon 19) : un fichier
        « canal_<rôle>.fit » (linéaire, recadré au cadre commun) par rôle
        empilé. Consommée par le thread d'acquisition (comme save_request)."""
        if not (self._mode_compo and self.stacker is not None
                and self.stacker.n > 0):
            self._dire(
                "Canaux", "Rien à enregistrer : démarrez une session en mode "
                          "composition et attendez au moins une frame.")
            return
        d = self._demander_dossier(
            "Dossier où enregistrer les empilements par canal")
        if d:
            # Jalon 121 : contexte de fiche de rendu transporté avec la demande.
            self.save_canaux_request = (d, self._fiche_contexte())

    def _save(self):
        if not self.running or self.stacker is None or self.stacker.n == 0:
            self._dire("Enregistrer", "Aucun empilement à enregistrer.")
            return
        path = self._enregistrer_sous(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"), ("PNG 16 bits", "*.png")],
            initialfile=self._nom_cible_pour_sauvegarde())
        if path:
            # Jalon 121 : la demande transporte AUSSI le contexte de fiche de
            # rendu (capturé ici, dans le fil d'interface). Un contexte None
            # (case décochée) = aucune fiche — le worker le tolère.
            self.save_request = (path, self._fiche_contexte())
            # Jalon 96 (étape 6) : PNG annoté COMPAGNON, écrit à côté (le FITS
            # linéaire, lui, part par le thread — deux fichiers indépendants).
            _png, _msg = self._sauver_png_annote(path)

    def _gx_live_prete(self, titre):
        """Contrôle AVANT toute sauvegarde pleine résolution : si le retrait de
        gradient live est actif et que sa commande est incomplète, la chaîne ne
        peut pas être reproduite — message clair et abandon (jamais de fichier
        « presque comme vu »). → True si l'on peut continuer."""
        if (self.disp.vl_graxpert
                and not gx_live.commande_valide(self.disp.vl_graxpert_cmd)):
            self._avertir(
                "GraXpert live",
                "Commande GraXpert absente ou incomplète — impossible de "
                "reproduire la chaîne live.\nVérifiez la commande dans "
                "« Traitement externe ».")
            return False
        return True

    def _reglages_rendu(self):
        """Capture des réglages de la chaîne de sortie DANS le thread principal
        (jalon 5) : le thread de sauvegarde ne lira JAMAIS les variables
        Tkinter, et l'état de `disp` (curseurs, solveur) continue de vivre
        pendant le rendu. Inclut, depuis le chantier du 24/09/2026, les
        CORRECTIONS DE COULEUR (`corr_*`) appliquées en pleine résolution."""
        d = self.disp
        reglages: dict[str, Any] = dict(
            stretch=d.stretch, auto=d.auto, sigma_k=d.sigma_k, target=d.target,
            black=d.black, white=d.white, gamma=d.gamma, saturation=d.saturation,
            vl_mode_res=d.vl_mode_res, vl_target_bg=d.vl_target_bg,
            vl_log_d=d.vl_log_d, vl_profil=d.vl_profil,
            vl_log_d_resolu=d.vl_log_d_resolu,
            vl_graxpert=d.vl_graxpert, vl_graxpert_cmd=d.vl_graxpert_cmd,
            vl_denoise=d.vl_denoise, vl_denoise_methode=d.vl_denoise_methode,
            vl_denoise_force=d.vl_denoise_force,
            vl_scnr=d.vl_scnr, vl_demagenta=d.vl_demagenta,
            vl_scnr_doux=d.vl_scnr_doux,
            # v2.48.0 (jalon 85) : force des deux outils et préservation de la
            # luminosité — la chaîne couleur suit l'étirement, donc le rendu
            # pleine résolution doit les recevoir pour rester identique à
            # l'écran (règle du projet : le fichier = l'écran).
            vl_scnr_force=float(d.vl_scnr_force),
            vl_demagenta_force=float(d.vl_demagenta_force),
            vl_preserve_luminance=bool(d.vl_preserve_luminance),
            # v2.48.0 (jalon 86) : boost du rouge (SII) masqué à l'objet — la
            # sauvegarde « tel que vu » doit être l'écran au pixel près.
            vl_boost_rouge=bool(d.vl_boost_rouge),
            vl_boost_force=float(d.vl_boost_force),
            vl_neutre_fond=bool(d.vl_neutre_fond),   # v2.36.1
            # v2.37.0 : réduction du bruit chromatique (case + force).
            vl_chroma=bool(d.vl_chroma),
            vl_chroma_force=float(d.vl_chroma_force),
            # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma, en pixels PLEINE
            # RÉSOLUTION — le rendu pleine résolution l'utilise TEL QUEL (l'écran,
            # lui, le ramène à l'échelle de l'aperçu : `_poser_rayon_chroma`).
            vl_chroma_rayon_ref=float(self.rayon_chroma_ref),
            vl_sharp=d.vl_sharp, vl_sharp_iterations=d.vl_sharp_iterations,
            # Jalon 75 : étage de niveaux (barres de l'histogramme) et
            # saturation par couleur — SANS ces clés, « tel que vu » ne serait
            # pas ce qui est à l'écran (règle du projet : le fichier = l'écran).
            bar_noir=float(d.bar_noir), bar_median=float(d.bar_median),
            bar_blanc=float(d.bar_blanc),
            sat_canaux=tuple(float(v) for v in d.sat_canaux),
            # Étirement GELÉ (⏹) : le rendu pleine résolution recalcule les
            # stats sur l'image complète — il doit utiliser les MÊMES stats
            # gelées que l'affichage, sinon le fichier dériverait de l'écran.
            stats_gelees=(d._stats if d.fige else None))
        st = self.stacker
        if st is not None:
            # NB : en MONO, l'empilement porte AUSSI des corrections (équilibrage
            # et recalage s'appliquent à une image couleur d'un dossier OSC) —
            # on les transporte donc quelle que soit la classe de stacker, pour
            # que « empilement traité (linéaire) » corresponde à l'affichage.
            reglages.update(
                corr_gains=(dict(st.gains_effectifs())
                            if hasattr(st, "gains_effectifs") else None),
                corr_wb=bool(getattr(st, "wb_auto", False)),
                corr_wb_force=float(getattr(st, "wb_force", 1.0)),
                corr_cadre=getattr(st, "cadre", None),
                corr_fit=bool(getattr(st, "linear_fit", False)),
                corr_fit_mode=getattr(st, "linear_fit_mode", "offset"),
                # Jalon 130 : le COMBINE LRGB de la composition (et son lissage
                # du 117d, OPT-IN) entre dans le composite LINÉAIRE écrit — la
                # fiche de rendu doit donc le DIRE (seul l'en-tête AVACOMPO le
                # portait, et c'est ce silence qui a fait croire le 16/10 que la
                # case était décochée alors qu'elle était cochée).
                compo_combine=("luminance" in composition_mod.COMPOSITIONS.get(
                    str(getattr(st, "composition", "")), {})),
                compo_lissage=bool(getattr(st, "lissage_halos", False)),
                compo_seuil=getattr(st, "seuil_masque_halos", None))
        return reglages

    # ============================================================= fiche de rendu
    # (jalon 121) — JSON compagnon `<image>.ava.json` : « le fichier dit ce qu'on
    # lui a fait ». Le CONTEXTE (source + état appliqué/affiché) est capturé dans
    # le FIL D'INTERFACE au moment de la demande ; le thread d'écriture ne lit
    # JAMAIS une variable Tk (règle du projet).
    def _fiche_actif(self):
        """La fiche doit-elle être écrite ? (case « Fiche de rendu ».)

        Lu dans le fil d'interface : la variable Tk (si la fenêtre existe) ET la
        persistance `fiche_rendu` de config.json. Défaut COCHÉ (décision
        d'Alain, 11/10/2026) : sans variable ni config, on écrit."""
        var = getattr(self, "var_fiche_rendu", None)
        if var is not None:
            try:
                if not bool(var.get()):
                    return False
            except tk.TclError:
                pass
        try:
            return bool(_globals_app().CONFIG.get("fiche_rendu", True))
        except Exception:
            return True

    def _fiche_contexte(self):
        """Capture, DANS LE FIL D'INTERFACE, ce que le thread ne pourra pas lire
        plus tard : le dossier surveillé / la source (variables Tk) et l'état
        APPLIQUÉ vs AFFICHÉ des réglages. → dict, ou None si la fiche est
        décochée (aucune lecture Tk inutile)."""
        if not self._fiche_actif():
            return None
        contexte: dict[str, Any] = {"etat": self._fiche_etat()}
        for cle, nom_var in (("dossier", "var_folder"), ("source", "var_source")):
            var = getattr(self, nom_var, None)
            if var is None:
                continue
            try:
                v = str(var.get()).strip()
            except tk.TclError:
                continue
            if v:
                contexte[cle] = v
        return contexte

    def _fiche_etat(self):
        """État APPLIQUÉ (ce que le rendu utilise) mis À CÔTÉ de l'état AFFICHÉ
        (ce que l'interface montre) — exigence d'Alain, jalon 121.

        Sur la table `_CONTROLE_AFFICHAGE`, chaque réglage est comparé : s'ils
        DIFFÈRENT, l'écart est consigné dans `ecarts` (c'est ce que le bug du
        11/10/2026 avait rendu invisible). Fil d'interface uniquement."""
        d = self.disp
        affiche: dict[str, float] = {}
        ecarts: list[dict[str, Any]] = []
        for cle, nom_var, lire in _CONTROLE_AFFICHAGE:
            var = getattr(self, nom_var, None)
            if var is None:
                continue
            try:
                vu = float(var.get())
                applique = float(lire(self, d))
            except (tk.TclError, TypeError, ValueError, AttributeError, IndexError):
                continue
            affiche[cle] = vu
            if abs(applique - vu) > 1e-6:
                ecarts.append({"reglage": cle, "applique": applique,
                               "affiche": vu})
        return {"affiche": affiche, "ecarts": ecarts}

    def _fiche_source(self, contexte):
        """Décrit la SOURCE de l'image pour la fiche (lisible depuis un thread :
        aucun accès Tk — ce qui vient de l'interface est dans `contexte`)."""
        st = self.stacker
        d: dict[str, Any] = {
            "frames": int(getattr(st, "n", 0) or 0),
            "filtre": self.filtre_courant or None,
            "mode": "composition" if self._mode_compo else "mono",
        }
        if contexte:
            if contexte.get("dossier"):
                d["dossier_brutes"] = contexte.get("dossier")
            if contexte.get("source"):
                d["source"] = contexte.get("source")
        return d

    def _fiche_chaine(self, reglages, vue, lineaire):
        """Chaîne de traitement DANS L'ORDRE, telle qu'elle a été APPLIQUÉE.

        L'ordre suit le pipeline réel : recadrage → gradient → débruitage →
        corrections couleur → netteté → chroma → étirement → NEUTRALISATION du
        fond → niveaux → gamma → saturation → cases couleur. Depuis le jalon 123
        la neutralisation du fond est APRÈS l'étirement (elle était AVANT). En
        sortie LINÉAIRE, la chaîne s'ARRÊTE avant l'étirement (donc pas de
        neutralisation : c'est ce que le fichier contient)."""
        if not reglages:
            return []
        r = reglages
        etapes: list[dict[str, Any]] = []

        def ajoute(nom, actif, **params):
            e = {"etape": nom, "actif": bool(actif)}
            e.update({k: v for k, v in params.items() if v is not None})
            etapes.append(e)

        # Jalon 130 : le COMBINE LRGB vient EN TÊTE — c'est lui qui FABRIQUE le
        # composite linéaire que toute la chaîne reçoit. Deux informations y sont
        # portées : les BORNES du rapport L/luma (toujours actives, jalons 130)
        # et le LISSAGE du 117d (OPT-IN). Sans cette étape, la fiche était MUETTE
        # sur les deux — seul l'en-tête `AVACOMPO` les portait.
        ajoute("combine LRGB (rapport L/luma borne)", r.get("compo_combine"),
               lissage_halos=r.get("compo_lissage"),
               seuil_masque_sigma=r.get("compo_seuil"),
               plafond_ratio=composition_mod.RATIO_L_MAX,
               plancher_ratio_relatif=composition_mod.PLANCHER_RATIO_FRAC)
        ajoute("recadrage", bool(r.get("corr_cadre")), cadre=r.get("corr_cadre"))
        ajoute("gradient GraXpert live", r.get("vl_graxpert"),
               commande=r.get("vl_graxpert_cmd"))
        ajoute("debruitage live", r.get("vl_denoise"),
               methode=r.get("vl_denoise_methode"),
               force=r.get("vl_denoise_force"))
        ajoute("corrections couleur (gains / equilibrage / linear fit)",
               bool(r.get("corr_gains") or r.get("corr_wb") or r.get("corr_fit")),
               gains=r.get("corr_gains"), equilibrage=bool(r.get("corr_wb")),
               linear_fit=bool(r.get("corr_fit")),
               mode_linear_fit=r.get("corr_fit_mode"))
        ajoute("nettete live", r.get("vl_sharp"),
               iterations=r.get("vl_sharp_iterations"))
        ajoute("bruit chromatique", r.get("vl_chroma"),
               force=r.get("vl_chroma_force"),
               rayon_ref_px=r.get("vl_chroma_rayon_ref"))
        if lineaire:
            etapes.append({"etape": "etirement", "actif": False,
                           "note": "sortie LINEAIRE : aucun etirement"})
        else:
            ajoute("etirement", True, moteur=r.get("stretch"),
                   mode_resolution=r.get("vl_mode_res"),
                   log_d_resolu=r.get("vl_log_d_resolu"),
                   fond_cible=r.get("vl_target_bg"), profil=r.get("vl_profil"))
            # Jalon 123 : la neutralisation du fond se MESURE sur la sortie et
            # s'applique APRÈS l'étirement — réservée à VeraLux (c'est son ancre
            # qui amplifie la couleur du fond).
            ajoute("neutralisation du fond",
                   r.get("vl_neutre_fond") and r.get("stretch") == "veralux")
            ajoute("etage de niveaux",
                   any(float(r.get(k) or 0.0) != 0.0 for k in
                       ("bar_noir", "bar_median", "bar_blanc")),
                   noir=r.get("bar_noir"), median=r.get("bar_median"),
                   blanc=r.get("bar_blanc"))
            ajoute("gamma", abs(float(r.get("gamma") or 1.0) - 1.0) > 1e-9,
                   valeur=r.get("gamma"))
            ajoute("saturation globale",
                   abs(float(r.get("saturation") or 1.0) - 1.0) > 1e-9,
                   valeur=r.get("saturation"))
            sat = tuple(float(v) for v in (r.get("sat_canaux") or (1.0, 1.0, 1.0)))
            ajoute("saturation par couleur (R/V/B)",
                   any(abs(v - 1.0) > 1e-9 for v in sat), valeur=list(sat))
        ajoute("SCNR", r.get("vl_scnr"), doux=r.get("vl_scnr_doux"),
               force=r.get("vl_scnr_force"))
        ajoute("demagenta", r.get("vl_demagenta"), force=r.get("vl_demagenta_force"))
        ajoute("boost rouge (SII)", r.get("vl_boost_rouge"),
               force=r.get("vl_boost_force"))
        ajoute("preservation de la luminosite", r.get("vl_preserve_luminance"))
        return etapes

    def _ecrire_fiche(self, chemin, type_sortie, contexte, image=None,
                      reglages=None, entete=None, vue=None, lineaire=False):
        """Écrit la fiche COMPAGNON de l'image qui vient d'être enregistrée.

        Appelé par le MÊME code/thread que l'image. `contexte` = ce qui a été
        capturé dans le fil d'interface (source + état appliqué/affiché) ; None
        = case décochée → rien. JAMAIS bloquant : toute erreur est rendue
        (message) et n'empêche jamais l'enregistrement de l'image."""
        if not contexte:
            return ""
        try:
            extra: dict[str, Any] = {
                "source": self._fiche_source(contexte),
                "chaine": self._fiche_chaine(reglages, vue, lineaire),
                "vue": vue,
                "lineaire": bool(lineaire),
                "etat": contexte.get("etat") or {},
                "entete_fits": dict(entete) if entete else None,
            }
            _chemin, msg = fiche_mod.ecrire_fiche(chemin, type_sortie,
                                                  image=image, extra=extra)
            if msg:                          # échec : au journal, jamais un popup
                try:
                    from .. import journal
                    journal.note("fiche de rendu",
                                 f"non écrite pour {chemin} : {msg}")
                except Exception:
                    pass
            return msg
        except Exception as exc:             # une fiche ne casse jamais une sauvegarde
            return f"{type(exc).__name__}: {exc}"

    def _save_asseen(self):
        """Jalon 5 — « 💾 Enregistrer tel que vu (étiré) » : sauvegarde la vue
        courante (empilement ou traitée) RENDUE comme à l'écran, en PLEINE
        résolution (jamais l'aperçu 1600 px) : chaîne complète stack →
        GraXpert live si activé (vue « empilement » ; en vue « traitée »,
        l'image a déjà subi le traitement externe) → débruitage live si
        activé (jalon 9) → netteté live si activée (jalon 12) → étirement
        STF/manuel ou VeraLux → gamma/saturation. Le bouton d'enregistrement
        LINÉAIRE reste inchangé. Le rendu (plusieurs secondes possibles) part
        dans un thread dédié via _worker — comme un traitement externe."""
        if self.asseen_busy or self.save_asseen_request is not None:
            self._dire("Enregistrer tel que vu",
                       "Un enregistrement est déjà en cours — patientez.")
            return
        if not self.running or self.stacker is None or self.stacker.n == 0:
            self._dire("Enregistrer tel que vu",
                       "Aucun empilement à enregistrer.")
            return
        vue = self.var_view.get()
        if vue == "traitée" and self.proc_full is None:
            self._dire(
                "Enregistrer tel que vu",
                "Aucun résultat traité — cliquez d'abord « ⚡ Traiter "
                "l'empilement courant ».")
            return
        if not self._gx_live_prete("tel que vu"):
            return
        path = self._enregistrer_sous(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"),
                       ("PNG 16 bits", "*.png")],
            initialfile=self._nom_cible_pour_sauvegarde())
        if not path:
            return
        self.asseen_titre = "Enregistrer tel que vu"
        # Jalon 96 (étape 6) : PNG annoté COMPAGNON, écrit à côté du FITS.
        _png, _msg = self._sauver_png_annote(path)
        # Jalon 121 : 5e élément = contexte de fiche de rendu (ou None).
        self.save_asseen_request = (path, vue, self._reglages_rendu(), False,
                                    self._fiche_contexte())

    def _save_traite_lineaire(self):
        """Chantier 24/09/2026 (décision (a) d'Alain) — « 💾 Enregistrer
        l'empilement traité (linéaire)… » : 3e sortie LINÉAIRE. Elle contient ce
        que la vue « empilement » a subi AVANT l'étirement : empilement BRUT →
        GraXpert live (gradient) si activé → débruitage live si activé →
        CORRECTIONS DE COULEUR (gains SPCC/Gaia/manuels, équilibrage des
        canaux, recalage Linear Fit) → netteté live si activée → chaîne couleur
        (SCNR…). C'est le fichier « prêt à traiter » dans un logiciel externe,
        intermédiaire entre l'empilement brut et l'image « tel que vu » (aucun
        étirement, aucun gamma/saturation). Réglages capturés dans le thread
        principal ; le rendu part dans le thread de sauvegarde, comme « tel que
        vu » (l'acquisition continue)."""
        titre = "Enregistrer l'empilement traité (linéaire)"
        if self.asseen_busy or self.save_asseen_request is not None:
            self._dire(titre, "Un enregistrement est déjà en cours — "
                              "patientez.")
            return
        if not self.running or self.stacker is None or self.stacker.n == 0:
            self._dire(titre, "Aucun empilement à enregistrer.")
            return
        if not self._gx_live_prete(titre):
            return
        path = self._enregistrer_sous(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"),
                       ("PNG 16 bits", "*.png")],
            initialfile=self._nom_cible_pour_sauvegarde())
        if not path:
            return
        self.asseen_titre = titre
        # Jalon 121 : 5e élément = contexte de fiche de rendu (ou None).
        self.save_asseen_request = (path, "pile", self._reglages_rendu(), True,
                                    self._fiche_contexte())

    def _couches_brutes(self):
        """Couches BRUTES recadrées (dict rôle → carte 2D) pour la chaîne par
        couche, ou None hors composition (mono : une seule image)."""
        st = self.stacker
        if st is None or not hasattr(st, "moyennes"):
            return None
        try:
            return st.moyennes()
        except Exception:
            return None

    def _couches_pleine_resolution(self, canaux, reglages):
        """Chaîne PAR COUCHE en pleine résolution — identique à celle du
        solveur live (jalon 24) : GraXpert live puis débruitage live sur CHAQUE
        couche 2D, puis recomposition (composer) et CORRECTIONS de couleur.

        POURQUOI par couche : GraXpert live et le débruitage live sont
        contractés pour des images de [0..1] (cf. `external.live.appliquer` et
        `denoise`) — les COUCHES le sont, le COMPOSITE non : la normalisation
        par rôle laisse un cœur d'étoile monter bien au-dessus de 1 (mesuré :
        17,94 sur l'empilement M31 d'Alain, 165 frames). Appliquer ces outils au
        composite le rescalait (GraXpert normalise sa sortie) et l'ÉCRÊTAIT (le
        NLM fait `clip(0, 1)` : 96 % des pixels > 1 perdus à la mesure) : le
        fichier n'était plus linéaire. Par couche, tout reste ≤ 1 et le
        composite recomposé garde son échelle.

        → (composite corrigé, message) ; jamais d'exception (les erreurs d'outil
        sont remontées en message et l'appelant décide)."""
        traites, msgs = {}, []
        couches = {role: np.asarray(couche, dtype=np.float32)
                   for role, couche in canaux.items()}
        # --- ① GRADIENT par couche, EN PARALLÈLE (jalon 81) : à l'export, TOUS
        # les appels sont à faire — c'est là que le gain est maximal (chaque
        # appel paie ~2,8 s fixes de démarrage + chargement du modèle de 217 Mo,
        # et les trois couches sont indépendantes : cf. `appliquer_lot`).
        if reglages.get("vl_graxpert"):
            a_lancer = []                    # (role, image)
            for role, c in couches.items():
                if float(np.max(np.abs(c))) < 1e-9:
                    msgs.append(f"GraXpert live ({role}) : couche vide — "
                                "ignorée")
                else:
                    a_lancer.append((role, c))
            if a_lancer:
                lot = gx_live.appliquer_lot(
                    [(role, c, reglages["vl_graxpert_cmd"])
                     for role, c in a_lancer])
                for role, _c in a_lancer:
                    c2, err = lot.get(role, (None, "appel non exécuté"))
                    if err or c2 is None:
                        msgs.append(f"GraXpert live ({role}) : "
                                    f"{err or 'aucun résultat'}")
                    else:
                        couches[role] = c2
        # --- ② DÉBRUITAGE par couche : même ordre qu'avant, inchangé.
        if reglages.get("vl_denoise"):
            for role, c in couches.items():
                c2, err = denoiser_local.denoiser(
                    c, reglages.get("vl_denoise_methode", "nlm"),
                    reglages.get("vl_denoise_force", 0.5))
                if err:
                    msgs.append(f"Débruitage live ({role}) : {err}")
                else:
                    couches[role] = c2
        traites = couches
        try:
            comp = composition_mod.composer(
                traites, self.stacker.composition,
                mode_l=self.stacker.mode_l,
                normalisation_commune=bool(getattr(
                    self.stacker, "normalisation_commune", False)))
        except Exception as exc:
            return None, f"Recomposition impossible : {exc}"
        if comp is None:
            return None, "Recomposition impossible (aucune couche exploitable)"
        comp, _diag = composition_mod.corrections_couleur(
            comp,
            gains=reglages.get("corr_gains"),
            wb_auto=bool(reglages.get("corr_wb", False)),
            wb_force=float(reglages.get("corr_wb_force", 1.0)),
            cadre=reglages.get("corr_cadre"),
            linear_fit=bool(reglages.get("corr_fit", False)),
            linear_fit_mode=reglages.get("corr_fit_mode", "offset"))
        return comp, " ; ".join(msgs)

    def _save_asseen_thread(self, path, vue, source, reglages, session,
                            lineaire=False, canaux=None, fiche=None):
        """Thread de sauvegarde « tel que vu » (jalon 5) : GraXpert live si
        activé (vue « empilement » uniquement), puis débruitage/netteté live,
        puis rendu pleine résolution identique à l'affichage, puis écriture du
        fichier. AUCUN appel Tk ici : le résultat est consommé par _tick
        (messagebox thread-safe).

        `lineaire=True` (chantier 24/09/2026) : MÊME chaîne, mais elle s'arrête
        AVANT l'étirement et écrit l'image LINÉAIRE (bornée [0,1], en-tête FITS
        AUTO-DESCRIPTIF) — c'est la 3e sortie « empilement traité (linéaire) ».

        `canaux` (couches BRUTES) : en COMPOSITION et vue « empilement », la
        chaîne GraXpert/débruitage est faite PAR COUCHE (cf.
        `_couches_pleine_resolution`) — sans quoi le composite (> 1) serait
        rescalé et écrêté par des outils contractés pour [0..1]. Le composite
        est alors déjà corrigé : les corrections ne sont pas réappliquées.

        `fiche` (jalon 121) : contexte de fiche de rendu capturé dans le fil
        d'interface (None = case décochée). La fiche compagnon est écrite ICI,
        par le MÊME thread que l'image."""
        corrige = False
        try:
            if (vue == "pile" and canaux
                    and (reglages.get("vl_graxpert")
                         or reglages.get("vl_denoise"))):
                comp, msg = self._couches_pleine_resolution(canaux, reglages)
                if comp is None:
                    self.asseen_result = f"ERREUR: {msg}"
                    return
                if msg:
                    self.msg_outils = msg     # erreurs d'outil non bloquantes
                source = comp
                corrige = True
            if not corrige and vue == "pile" and reglages.get("vl_graxpert"):
                gx, err = gx_live.appliquer(source, reglages["vl_graxpert_cmd"])
                if err:
                    # On ne sauvegarde PAS une image « presque comme vue » :
                    # échec GraXpert = échec de la sauvegarde (message clair).
                    self.asseen_result = f"ERREUR: GraXpert live : {err}"
                    return
                source = gx
            # Jalon 9 : le débruitage live fait partie de la chaîne affichée
            # (stack → GX → débruitage → étirement) — reproduit ici en pleine
            # résolution pour que le fichier corresponde à l'écran.
            if not corrige and vue == "pile" and reglages.get("vl_denoise"):
                img_dn, err = denoiser_local.denoiser(
                    source, reglages.get("vl_denoise_methode", "nlm"),
                    reglages.get("vl_denoise_force", 0.5))
                if err:
                    self.asseen_result = f"ERREUR: Débruitage live : {err}"
                    return
                source = img_dn
            # --- CHANTIER 24/09/2026 (décision (c) d'Alain) : les CORRECTIONS
            # DE COULEUR s'appliquent ICI, après le débruitage et AVANT la
            # netteté — c'est l'ordre de la chaîne de sortie. Seule la 3e sortie
            # LINÉAIRE en a besoin, et seulement si la chaîne par couche ne les
            # a pas déjà appliquées (elle finit par `corrections_couleur`).
            if lineaire and not corrige:
                source, _diag = composition_mod.corrections_couleur(
                    source,
                    gains=reglages.get("corr_gains"),
                    wb_auto=bool(reglages.get("corr_wb", False)),
                    wb_force=float(reglages.get("corr_wb_force", 1.0)),
                    cadre=reglages.get("corr_cadre"),
                    linear_fit=bool(reglages.get("corr_fit", False)),
                    linear_fit_mode=reglages.get("corr_fit_mode", "offset"))
            # Jalon 12 : la netteté live fait aussi partie de la chaîne
            # affichée (stack → GX → débruitage → netteté → étirement).
            # ⚠️ La PSF est MESURÉE ici, en pleine résolution (aucun `mesure=`
            # transmis) : celle du live est exprimée en pixels de l'APERÇU,
            # réduit sur les gros capteurs — l'utiliser telle quelle fausserait
            # la déconvolution du fichier.
            if vue == "pile" and reglages.get("vl_sharp"):
                img_net, err = nettete_live.deconvoluer(
                    source,
                    iterations=reglages.get("vl_sharp_iterations",
                                            nettete_live.ITERATIONS_DEFAUT))
                if err:
                    self.asseen_result = f"ERREUR: Netteté live : {err}"
                    return
                source = img_net
            # v2.48.0 (jalon 85) : la chaîne couleur n'est PLUS appliquée ici.
            # Elle suit désormais l'ÉTIREMENT, donc elle vit dans
            # `rendu_pleine_resolution` (appelé plus bas), exactement comme à
            # l'écran — « le fichier correspond à l'écran » reste vrai.
            # CONSÉQUENCE VOULUE : la 3e sortie LINÉAIRE ci-dessous n'est plus
            # écrêtée en vert (elle était la SEULE à porter le SCNR des jalons
            # 22/23 — MESURÉ sur son empilement M31 : excès de vert max 5,9·10⁻⁸
            # contre 1,6·10⁻¹ sur l'empilement d'origine).
            if lineaire:
                # 3e sortie LINÉAIRE (« empilement traité ») : on écrit l'image
                # telle quelle, bornée [0,1] comme la sauvegarde brute, AVEC
                # l'en-tête auto-descriptif de la chaîne de sortie — aucun
                # étirement, aucun gamma/saturation.
                if session != self._session:   # session relancée entre-temps
                    return
                entete = self._astro_entete_sauvegarde(
                    {"FILTER": self.filtre_courant} if self.filtre_courant
                    else None, source.shape[:2] if source is not None else None)
                entete.update(self._entete_reglages(applique=True))
                entete["AVAVUE"] = ("empilement TRAITE (lineaire, sans "
                                    "etirement)")
                img, entete = borner_lineaire(source, entete)
                save_image(path, img, entete=entete)
                self.dernier_applicatif = entete.get("AVAAPPLI")
                # Jalon 121 : fiche de rendu compagne (même thread que l'image).
                self._ecrire_fiche(
                    path, "empilement traite (lineaire)", fiche, image=img,
                    reglages=reglages, entete=entete, vue=vue, lineaire=True)
                self.asseen_result = path
                return
            # JALON 123 : la NEUTRALISATION de la couleur du fond a QUITTÉ cet
            # étage pré-étirement (elle FABRIQUAIT le magenta — cf. couleurs.py).
            # Elle est désormais appliquée APRÈS l'étirement, DANS
            # `rendu_pleine_resolution` (juste après le moteur), exactement comme
            # le solveur live — le fichier « tel que vu » reste l'écran.
            # v2.37.0 / JALON 127 : réduction du bruit chromatique — juste AVANT
            # l'étirement, exactement comme dans la chaîne live (commune aux
            # DEUX moteurs depuis le jalon 127). Elle n'est donc PLUS réservée à
            # VeraLux : l'écran l'applique AUSSI en STF, et « le fichier =
            # l'écran » impose de l'appliquer ici quel que soit le moteur. Elle
            # reste, elle, JAMAIS dans la 3e sortie LINÉAIRE ci-dessus (la
            # sortie linéaire a déjà rendu la main) ; en vue « traitée », elle
            # vient de la chaîne EXTERNE ⚡ (ne pas la refaire).
            if vue == "pile" and reglages.get("vl_chroma"):
                source = couleurs_mod.reduire_bruit_chroma(
                    source, force=float(reglages.get("vl_chroma_force") or 0.5),
                    # v2.37.4 : rayon de RÉFÉRENCE, pleine résolution (l'image
                    # rendue ici est en pleine résolution — l'aperçu, lui, est
                    # ramené à son échelle par `_poser_rayon_chroma`).
                    rayon=float(reglages.get("vl_chroma_rayon_ref")
                                or couleurs_mod.RAYON_CHROMA_DEFAUT))
            rendu = self.disp.rendu_pleine_resolution(source, reglages)
            if session != self._session:    # session relancée entre-temps
                return
            # v2.38.3 : en vue « traitée », cette image VIENT de la chaîne
            # externe (c'était le SEUL fichier sans aucune traçabilité).
            entete = None
            if vue == "traitée":
                entete = self._entete_externe()
                entete["AVAVUE"] = ("resultat traite externe, tel que vu "
                                    "(ETIRE)")
            save_image(path, rendu, entete=entete)
            # Jalon 121 : fiche de rendu compagne (même thread que l'image).
            # C'est LE cas qui manquait de provenance : « tel que vu » n'avait
            # aucun en-tête, et la vue « traitée » vient d'une chaîne externe.
            type_sortie = ("resultat externe, tel que vu (etire)"
                           if vue == "traitée" else "tel que vu (etire)")
            self._ecrire_fiche(path, type_sortie, fiche, image=rendu,
                               reglages=reglages, entete=entete, vue=vue,
                               lineaire=False)
            self.asseen_result = path
        except Exception as e:
            self.asseen_result = f"ERREUR: {e}"
        finally:
            self.asseen_busy = False

    def _save_proc(self):
        if self.proc_full is None:
            return
        path = self._enregistrer_sous(
            defaultextension=".fits",
            filetypes=[("FITS", "*.fits"), ("TIFF 16 bits", "*.tif"), ("PNG 16 bits", "*.png")],
            initialfile=self._nom_cible_pour_sauvegarde())
        if path:
            try:
                # v2.27.1 : même garantie d'échelle que la sauvegarde de
                # l'empilement linéaire (un résultat d'outil externe peut
                # lui aussi dépasser 1 : le borner évite un fichier que les
                # lecteurs supposant [0,1] afficheraient « saturé »).
                img, entete = borner_lineaire(self.proc_full,
                                              dict(self.proc_entete or {}))
                save_image(path, img, entete=entete)
                # Jalon 96 (étape 6) : PNG annoté COMPAGNON, écrit à côté du
                # FITS (jamais dans le fichier : linéarité préservée).
                _png, _msg = self._sauver_png_annote(path)
                # Jalon 121 : fiche de rendu compagne (fil d'interface ici).
                self._ecrire_fiche(
                    path, "resultat du traitement externe (lineaire)",
                    self._fiche_contexte(), image=img, reglages=None,
                    entete=entete, vue="traitée", lineaire=True)
                self._dire("Enregistrer", f"Résultat traité sauvegardé :\n{path}")
            except Exception as e:
                self._signaler("Enregistrer", str(e))

    def _entete_reglages(self, applique=True):
        """Mots-clés FITS décrivant une sauvegarde LINÉAIRE — question d'Alain
        (24/09/2026) : « la sauvegarde empilement linéaire, elle sauvegarde quoi
        au juste ? ». Le fichier devient AUTO-DESCRIPTIF.

        Chantier du 24/09/2026 — MESURE vs APPLICATION (étape ⑥ du plan) :
        depuis que la sauvegarde linéaire est BRUTE, AVASPCC et AVAGAIA
        décrivent une MESURE (ce que la session a mesuré), pas ce que le
        fichier contient. La clé AVAAPPLI dit, elle, ce qui est RÉELLEMENT
        appliqué à l'image écrite : « aucune (empilement BRUT) » pour le
        fichier brut, la liste des corrections pour la sortie traitée. Sans
        cette distinction, un fichier brut portant AVASPCC=K=… laisserait
        croire que la SPCC y est appliquée : il mentirait.

        ASCII uniquement (convention FITS) et clés courtes (≤ 8 caractères) :
        AVACOMPO (composition), AVAAPPLI (corrections appliquées au fichier),
        AVAWB (équilibrage auto et sa force — si appliqué), AVAFIT (recalage
        colorimétrique — si appliqué), AVASPCC (coefficients SPCC MESURÉS),
        AVAGAIA (gains Gaia MESURÉS), AVAFRAME (frames empilées), AVALAYER
        (sauvegarde d'une COUCHE brute, posée par l'appelant)."""
        st = self.stacker
        ent = {}
        n = int(getattr(st, "n", 0) or 0)
        if n:
            ent["AVAFRAME"] = n
        # NB : ces mots-clés ne dépendent PAS de l'existence du stacker (les
        # réglages sont connus même sans empilement) — seule la description de
        # l'empilement lui-même en dépend (getattr défensifs).
        spcc_ok = (self._spcc_actif and self.spcc is not None
                   and self.spcc.valide)
        gaia_ok = (self._photo_gains_actif and self.photometrie is not None
                   and self.photometrie.valide)
        if self._mode_compo:
            # v2.36.0 : le fichier DIT quelle normalisation a servi (c'est un
            # choix visible : le fond et le grain en dépendent).
            norm = ("normalisation COMMUNE des canaux (amplitude du vert)"
                    if bool(getattr(st, "normalisation_commune", False))
                    else "normalisation par role (percentiles)")
            # v2.71.0 (jalon 117d) : le fichier DIT aussi si le LISSAGE DU COMBINE
            # LRGB (halos d'etoiles) a servi — c'est OPT-IN (decochage = combine
            # d'avant le 117c) et cela change le composite lineaire ecrit.
            if bool(getattr(st, "lissage_halos", False)):
                liss = ("lissage combine LRGB actif (masque %g sigma)"
                        % float(getattr(st, "seuil_masque_halos",
                                        composition_mod.SEUIL_MASQUE_SIGMA)))
            else:
                liss = "lissage combine LRGB inactif"
            ent["AVACOMPO"] = (f"{getattr(st, 'composition', '?')}, {norm}, "
                               f"{liss}")
        # MESURES de la session (indépendantes de ce qui est appliqué).
        if spcc_ok:
            k = self.spcc.coefficients  # pyright: ignore[reportOptionalMemberAccess]
            ent["AVASPCC"] = f"K={k[0]:.4f}/{k[1]:.4f}/{k[2]:.4f}"
        elif self._spcc_actif:
            # Case cochée SANS mesure exploitable : le dire, sinon on croit que
            # la SPCC est entrée dans le fichier alors que rien n'a été appliqué
            # (constat d'Alain, 25/09/2026 : fichiers écrits avant que la mesure
            # ne soit disponible, en-tête muet).
            ent["AVASPCC"] = ("non appliquee (case cochee, mesure "
                              "indisponible)")
        if gaia_ok:
            ent["AVAGAIA"] = " ".join(
                f"{b}={g:.4f}" for b, g in sorted(self.photometrie.gains.items()))  # pyright: ignore[reportOptionalMemberAccess]
        elif self._photo_gains_actif:
            ent["AVAGAIA"] = ("non appliques (case cochee, mesure "
                              "indisponible)")
        # CE QUI EST APPLIQUÉ à l'image écrite (étape ⑥).
        if not applique:
            ent["AVAAPPLI"] = "aucune (empilement BRUT)"
            return ent
        parts = []
        if spcc_ok:
            parts.append("SPCC")
        elif gaia_ok:
            parts.append("gains Gaia")
        gains_ui = {c: float(g) for c, g in (self._compo_gains or {}).items()
                    if abs(float(g) - 1.0) > 1e-9}
        if gains_ui:
            parts.append("gains manuels")
        if bool(getattr(st, "wb_auto", False)):
            parts.append("equilibrage canaux")
            ent["AVAWB"] = (f"equilibrage canaux auto, force "
                            f"{getattr(st, 'wb_force', 1.0):.2f}")
        if bool(getattr(st, "linear_fit", False)):
            parts.append("recalage colorimetrique")
            ent["AVAFIT"] = (f"recalage colorimetrique "
                             f"{getattr(st, 'linear_fit_mode', 'offset')}")
        ent["AVAAPPLI"] = " + ".join(parts) if parts else "aucune"
        return ent

    def _entete_externe(self, n_frames=None):
        """En-tête FITS du RÉSULTAT du ⚡ traitement externe (v2.38.3).

        POURQUOI (constat d'Alain, 27/09/2026) : les commandes des outils — donc
        leurs PARAMÈTRES — n'étaient écrites NULLE PART. `AVAAPPLI` ne décrivait
        que les corrections de couleur, et les « tel que vu » n'avaient aucun
        en-tête : un fichier ne disait pas de quelle chaîne il venait, alors que
        le réglage des outils change la texture fine (mesuré : moucheté chroma
        2-8 px ×0,37 entre `--sn 0,50` — le défaut du CLI non passé — et 0,3).

        Les commandes RÉELLEMENT utilisées par le ⚡ sont consignées telles
        quelles (elles portent leurs options : `--ash`, `--sn`, `-strength`…) ;
        l'en-tête est construit au moment du traitement, depuis `ext_job` (lu par
        le thread de travail, jamais une variable Tk). Déballage TOLÉRANT : un
        job à 8 éléments (formats antérieurs) reste accepté."""
        j = tuple(self.ext_job or ())

        def val(i, defaut=None):
            return j[i] if len(j) > i else defaut

        outils = []
        if val(0):
            outils.append("GraXpert gradient")
        if val(2):
            methode = val(6) or "?"
            outils.append("debruitage "
                          + ("GraXpert" if methode == "graxpert" else methode))
        if val(4):
            outils.append("BXT")
        preet = []
        # v2.48.0 (jalon 85) : la chaîne couleur (SCNR / SCNR doux / démagenta)
        # NE FAIT PLUS PARTIE de la chaîne externe — elle suit l'étirement et
        # est appliquée à l'affichage comme à « tel que vu »
        # (`display.couleur_apres_etirement`).
        # JALON 123 : la NEUTRALISATION du fond a elle aussi quitté cette chaîne
        # (elle s'applique APRÈS l'étirement, cf. `display`) — le fichier ⚡ ne
        # porte donc plus que la réduction du bruit chromatique, ce que dit
        # AVAAPPLI.
        if val(8):
            preet.append("chroma force %.2f rayon %.1fpx"
                         % (float(val(9, 0.5)), float(val(10, 3.0))))
        ent: dict[str, Any] = {
               "AVAOUTIL": " + ".join(outils) if outils else "aucun",
               "AVAAPPLI": " + ".join(preet) if preet else "aucune",
               "AVAVUE": ("resultat du traitement externe (LINEAIRE, "
                          "avant etirement)")}
        if val(1):
            ent["AVACMDGX"] = str(val(1))
        if val(3):
            ent["AVACMDDN"] = str(val(3))
        if val(5):
            ent["AVACMDBX"] = str(val(5))
        if n_frames:
            ent["AVAFRAME"] = int(n_frames)
        return ent

    def _astro_entete_sauvegarde(self, entete=None, forme=None):
        """Jalon 56 : complète un en-tête de sauvegarde avec les mots-clés WCS
        de la grille ACTUELLE (recadrage d'intersection inclus) — le FITS écrit
        devient localisable par Siril, astropy, PixInsight… Sans astrométrie
        résolue : en-tête INCHANGÉ (jamais de mot-clé faux dans un fichier)."""
        entete = dict(entete or {})
        if self.suivi_astro is None or not self.suivi_astro.resolu:
            return entete
        cadre = None
        if self.stacker is not None:
            cadre = getattr(self.stacker, "cadre", None)
        mc, msg = self.suivi_astro.mots_cles(cadre, forme=forme)
        if not mc:
            if msg:
                self.astro_info = f"Astrométrie : en-tête WCS indisponible — {msg}"
                self.astro_couleur = "#c98a00"
            return entete
        entete.update(mc)
        return entete
