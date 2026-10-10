# -*- coding: utf-8 -*-
"""Persistance des réglages de l'interface (config.json) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 104 du chantier de refactoring :
- `_restaurer_config` : restaure les réglages persistés après la construction
  de l'UI (dossier, CFA, composition, traitement externe, étirement, moteur…) ;
- `_sauver_config_app` : persiste les réglages de l'interface à la fermeture.

Les méthodes sont reprises VERBATIM : `App` hérite de `ConfigUI`, donc `self`
reste l'instance `App` et le comportement est inchangé AU BIT.

Les attributs d'interface (constantes, variables Tk, état) utilisés par ce mixin
sont DÉCLARÉS ici pour le typage statique (`pyright`).
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ..external import live as gx_live
from ..processing import DisplayProcessor
from ..processing import couleurs as couleurs_mod
from ..processing import sharpness as nettete_live
from ..processing import veralux as veralux_moteur
from ..processing.composition import (COMPOSITIONS, MODES_L, ROLES,
                                       SEUIL_MASQUE_MAX, SEUIL_MASQUE_MIN,
                                       SEUIL_MASQUE_SIGMA)


def _globals_app():
    """Globals du module d'application `avastack.ui.app` — résolution TARDIVE.

    POURQUOI (jalon 104) : les bancs remplacent `avastack.ui.app.CONFIG` et
    `.sauver_config` (intercepter le VRAI config.json, ou simuler une session
    relue). Ces deux méthodes vivant désormais ICI, lire les globals du module
    d'application AU MOMENT DE L'APPEL préserve cette interception ; en
    production c'est le MÊME objet que `avastack.config.CONFIG` /
    `avastack.config.sauver_config`.
    """
    from . import app as _app              # import TARDIF (évite le cycle)
    return _app


class ConfigUI:
    """Mixin : restauration/sauvegarde de la config de l'interface."""

    # Interface attendue sur l'hôte (`App`) — DÉCLARATIONS DE TYPAGE seulement.
    # Constantes (classes `App`, depuis `constants.py`).
    CADENCE_LABELS: dict[int, str]
    DN_EXT_CODES: dict[str, str]
    DN_EXT_LABELS: dict[str, str]
    HIST_CODES: tuple[str, ...]
    HIST_LABELS: dict[str, str]
    SPCC_TYPE_MONO: str
    SPCC_TYPE_OSC: str
    VL_DN_CODES: dict[str, str]
    VL_DN_LABELS: dict[str, str]

    # Widgets et état de l'application.
    cb_fenetre: ttk.Combobox
    cb_ref_refresh: ttk.Combobox
    cb_vl_profil: ttk.Combobox
    cv_hist: tk.Canvas
    scl_sharp: ttk.Scale
    disp: DisplayProcessor
    hist_lineaire: bool
    hist_mode: str
    kappa: float | None
    rejet_methode: str
    rejet_fenetre: int
    ref_refresh: int
    cadence_lecture: int
    rayon_chroma_ref: float
    _echelle_apercu: float
    _norm_commune: bool
    _compo_lissage_halos: bool
    _compo_seuil_halos: float
    _spcc_vars: dict[str, tk.Variable]
    _spcc_noms: dict[str, Any]

    # Variables Tk (déclarées larges : `Variable` couvre IntVar/StringVar/
    # DoubleVar/BooleanVar — `.get()`/`.set()` restent typés `Any`).
    var_annoter_etoiles: tk.Variable
    var_annoter_objets: tk.Variable
    var_annoter_sauvegarde: tk.Variable
    var_annoter_visibles: tk.Variable
    var_astro: tk.Variable
    var_astro_champ: tk.Variable
    var_astro_dec: tk.Variable
    var_astro_ra: tk.Variable
    var_cadence: tk.Variable
    var_cfa: tk.Variable
    var_cmd_bxt: tk.Variable
    var_cmd_graxpert: tk.Variable
    var_cmd_graxpert_dn: tk.Variable
    var_compo: tk.Variable
    var_compo_mode_l: tk.Variable
    var_dn_force: tk.Variable
    var_dn_methode: tk.Variable
    var_ext_bxt: tk.Variable
    var_ext_chroma: tk.Variable
    var_ext_dn: tk.Variable
    var_ext_graxpert: tk.Variable
    var_ext_neutre: tk.Variable
    var_fenetre: tk.Variable
    var_fit: tk.Variable
    var_fit_methode: tk.Variable
    var_folder: tk.Variable
    var_gamma: tk.Variable
    var_hist_lineaire: tk.Variable
    var_hist_mode: tk.Variable
    var_kappa: tk.Variable
    var_lissage_halos: tk.Variable
    var_lissage_halos_sigma: tk.Variable
    var_moteur: tk.Variable
    var_norm_commune: tk.Variable
    var_photo: tk.Variable
    var_photo_gains: tk.Variable
    var_process_existing: tk.Variable
    var_ref_refresh: tk.Variable
    var_rejet: tk.Variable
    var_rejeter_flou: tk.Variable
    var_sat_b: tk.Variable
    var_sat_g: tk.Variable
    var_sat_r: tk.Variable
    var_saturation: tk.Variable
    var_seuil_mag_etoiles: tk.Variable
    var_sigk: tk.Variable
    var_spcc: tk.Variable
    var_spcc_type: tk.Variable
    var_target: tk.Variable
    var_vl_boost: tk.Variable
    var_vl_boost_force: tk.Variable
    var_vl_chroma: tk.Variable
    var_vl_chroma_force: tk.Variable
    var_vl_chroma_rayon: tk.Variable
    var_vl_demagenta: tk.Variable
    var_vl_demagenta_force: tk.Variable
    var_vl_dn: tk.Variable
    var_vl_dn_force: tk.Variable
    var_vl_dn_methode: tk.Variable
    var_vl_graxpert: tk.Variable
    var_vl_logd: tk.Variable
    var_vl_mode_res: tk.Variable
    var_vl_neutre: tk.Variable
    var_vl_pleine_res: tk.Variable
    var_vl_preserve: tk.Variable
    var_vl_profil: tk.Variable
    var_vl_scnr: tk.Variable
    var_vl_scnr_doux: tk.Variable
    var_vl_scnr_force: tk.Variable
    var_vl_sharp: tk.Variable
    var_vl_sharp_iter: tk.Variable
    var_vl_target: tk.Variable
    var_wb: tk.Variable
    var_wb_force: tk.Variable

    # Variables Tk COLLECTIVES (listes/dict).
    var_compo_dossiers: list[tk.StringVar]
    var_compo_roles: list[tk.StringVar]
    var_compo_gains: dict[str, tk.StringVar]

    # Méthodes de l'hôte (`App` et ses autres mixins) appelées ici.
    _annoncer_mesures: Callable[..., Any]
    _code_fit_methode: Callable[..., Any]
    _hauteur_hist: Callable[..., Any]
    _lire_gains: Callable[..., Any]
    _lire_seuil_halos: Callable[..., Any]
    _maj_lbl_sharp: Callable[..., Any]
    _maj_visibilite_cadres: Callable[..., Any]
    _on_astro: Callable[..., Any]
    _on_cadence: Callable[..., Any]
    _on_compo_roles: Callable[..., Any]
    _on_moteur: Callable[..., Any]
    _on_photo: Callable[..., Any]
    _on_photo_gains: Callable[..., Any]
    _on_ref_refresh: Callable[..., Any]
    _on_rejeter_flou: Callable[..., Any]
    _on_sat_canaux: Callable[..., Any]
    _on_spcc: Callable[..., Any]
    _on_spcc_type: Callable[..., Any]
    _on_vl_boost: Callable[..., Any]
    _on_vl_chroma: Callable[..., Any]
    _on_vl_demagenta: Callable[..., Any]
    _on_vl_denoise: Callable[..., Any]
    _on_vl_graxpert: Callable[..., Any]
    _on_vl_neutre: Callable[..., Any]
    _on_vl_pleine_res: Callable[..., Any]
    _on_vl_preserve: Callable[..., Any]
    _on_vl_scnr: Callable[..., Any]
    _on_vl_scnr_doux: Callable[..., Any]
    _on_vl_sharp: Callable[..., Any]
    _on_wb: Callable[..., Any]
    _poser_rayon_chroma: Callable[..., Any]
    _seuil_mag: Callable[..., Any]
    _sync_vl_mode: Callable[..., Any]

    # ------------------------------------------------------------ persistance config
    def _restaurer_config(self):
        """Restaure les réglages persistés (dossier surveillé, CFA, traitement
        externe, étirement) après la construction de l'UI. Les commandes des
        outils externes ont déjà été restaurées au niveau module
        (DEFAULT_CMD_*). Si une commande détectée automatiquement (pas
        persistée) n'existe plus sur cette machine, elle est re-détectée."""
        c = _globals_app().CONFIG
        if c.get("dossier"):
            self.var_folder.set(c["dossier"])
        if c.get("cfa") in ("Auto", "RGGB", "BGGR", "GRBG", "GBRG", "Non"):
            self.var_cfa.set(c["cfa"])
        # --- Jalon 19 : composition multi-filtres (rôles + dossiers des 4
        # lignes, gains, radio « Canal L ») — restauration TOLÉRANTE :
        # format inconnu / rôle hors liste → ligne ignorée (défauts).
        for i in range(4):
            entree = c.get(f"compo_dossier_{i}")
            if isinstance(entree, str) and entree:
                self.var_compo_dossiers[i].set(entree)
        for i in range(4):
            v = c.get(f"compo_role_{i}")
            if isinstance(v, str) and v in ROLES:
                self.var_compo_roles[i].set(v)
        if c.get("compo_nom") in COMPOSITIONS:
            self.var_compo.set(c["compo_nom"])
        gains = c.get("compo_gains")
        if isinstance(gains, dict):
            for canal in ("R", "G", "B"):
                v = gains.get(canal)
                if isinstance(v, (int, float)) and not isinstance(v, bool) \
                        and 0.0 <= float(v) <= 10.0:
                    self.var_compo_gains[canal].set(str(float(v)))
        if c.get("compo_mode_l") in MODES_L:
            self.var_compo_mode_l.set(c["compo_mode_l"])
        # v2.36.0 : normalisation commune des canaux (option). L'instantané est
        # posé ici aussi : le stacker le recevra à sa création.
        if "norm_commune" in c:
            self.var_norm_commune.set(bool(c.get("norm_commune")))
            self._norm_commune = bool(self.var_norm_commune.get())
        # v2.71.0 (jalon 117d) : LISSAGE DU COMBINE LRGB (halos d'étoiles), OPT-IN,
        # et son seuil de masque. Les instantanés sont posés ici aussi : le stacker
        # les recevra à sa création.
        if "lissage_halos" in c:
            self.var_lissage_halos.set(bool(c.get("lissage_halos")))
            self._compo_lissage_halos = bool(self.var_lissage_halos.get())
        v = c.get("lissage_halos_sigma")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            sig = float(min(SEUIL_MASQUE_MAX, max(SEUIL_MASQUE_MIN, float(v))))
            self.var_lissage_halos_sigma.set(sig)
            self._compo_seuil_halos = sig
        self._on_compo_roles()   # composition recollée aux rôles restaurés
        if c.get("process_existing") is False:
            self.var_process_existing.set(False)
        # Traitement externe : ne pas écraser une commande persistée par un
        # défaut re-détecté qui aurait changé — SAUF si son exécutable est
        # INTROUVABLE (v2.38.5). POURQUOI : l'ancienne version ne testait
        # l'existence du binaire QUE lorsqu'aucune commande n'était persistée ;
        # or la commande de REPLI (binaire nu « graxpert … », écrite par une
        # session où la détection avait échoué — cas Linux d'Alain,
        # 27/09/2026) est une chaîne non vide : elle se retrouvait donc figée
        # dans config.json à vie, invisible, et aucune correction de la
        # détection ne pouvait plus la déloger.
        # v2.38.11 : AUCUNE SONDE DISQUE ICI. On restaure les commandes
        # PERSISTÉES (texte), on ANNONCE que la mesure est en cours, et c'est le
        # fil de mesures (borné, APRÈS l'affichage) qui détecte les outils,
        # re-détecte un binaire disparu et sonde le dossier de travail.
        # POURQUOI : ces sondes (`which`, `isfile`, `glob`, `disk_usage`)
        # ATTENDENT indéfiniment sur un montage réseau injoignable — le
        # 27/09/2026, un dossier de couches R/G/B sur le NAS (filtré par
        # `nftables`) empêchait ainsi l'application de s'ouvrir, sans un mot.
        for cle, var in (("cmd_graxpert", self.var_cmd_graxpert),
                         ("cmd_graxpert_dn", self.var_cmd_graxpert_dn),
                         ("cmd_bxt", self.var_cmd_bxt)):
            enreg = (c.get(cle) or "").strip()
            if enreg:
                var.set(enreg)
        self._annoncer_mesures()
        if c.get("ext_graxpert"):
            self.var_ext_graxpert.set(True)
        # Jalons 7/8 (remis le 16/09/2026) — débruitage du traitement
        # externe : méthode au choix (GraXpert IA / ondelettes / NLM) +
        # force commune. La case n'est restaurée que si la méthode est
        # utilisable : ondelettes/NLM (aucun outil requis) ou GraXpert
        # avec commande complète (jamais de popup au démarrage).
        methode_ext = c.get("dn_methode")
        if methode_ext in self.DN_EXT_LABELS:
            self.var_dn_methode.set(self.DN_EXT_LABELS[methode_ext])
        v = c.get("dn_force")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 1.0:
            self.var_dn_force.set(float(v))
        if c.get("ext_dn") and (self.DN_EXT_CODES.get(
                self.var_dn_methode.get(), "graxpert") != "graxpert"
                or gx_live.commande_valide(
                    self.var_cmd_graxpert_dn.get().strip())):
            self.var_ext_dn.set(True)
        if c.get("ext_bxt"):
            self.var_ext_bxt.set(True)
        # v2.48.0 (jalon 85) : les clés `ext_scnr` / `ext_scnr_doux` /
        # `ext_demagenta` ne sont PLUS relues — la chaîne couleur suit
        # l'étirement (section « Couleur de l'objet (après étirement) »), elle
        # n'appartient plus à la chaîne externe. Une configuration antérieure
        # qui les portait reste lisible : elles sont simplement ignorées.
        # v2.37.1 : corrections pré-étirement de la chaîne externe. La
        # neutralisation est COCHÉE par défaut → on ne la modifie que si la
        # config porte la clé ET une valeur (même règle que vl_neutre_fond) ;
        # le bruit chromatique, OPT-IN, n'est activé que s'il est demandé.
        if "ext_neutre_fond" in c:
            self.var_ext_neutre.set(bool(c.get("ext_neutre_fond")))
        if c.get("ext_chroma"):
            self.var_ext_chroma.set(True)
        for cle, var, mini, maxi in (
                ("sigk", self.var_sigk, 0.5, 5.0),
                ("target", self.var_target, 0.10, 0.45),
                ("gamma", self.var_gamma, 0.2, 4.0),
                ("saturation", self.var_saturation, 0.0, 3.0),
                # Jalon 75 : saturation par couleur (R/V/B).
                ("sat_r", self.var_sat_r, 0.0, 3.0),
                ("sat_g", self.var_sat_g, 0.0, 3.0),
                ("sat_b", self.var_sat_b, 0.0, 3.0)):
            v = c.get(cle)
            if isinstance(v, (int, float)) and mini <= v <= maxi:
                var.set(float(v))
        self.disp.sigma_k = self.var_sigk.get()
        self.disp.target = self.var_target.get()
        # Jalon 75 : saturation par couleur + bandes d'histogramme affichées.
        # Les BARRES de niveaux et l'état « figé », eux, ne sont pas restaurés
        # (comme `auto` et black/white) : ils appartiennent à la session.
        self._on_sat_canaux()
        _hm = c.get("hist_mode")
        if isinstance(_hm, str) and _hm in self.HIST_CODES:
            self.hist_mode = _hm
            self.var_hist_mode.set(self.HIST_LABELS[_hm])
            self.cv_hist.config(height=self._hauteur_hist())
        # Jalon 75 (échelle y, décision d'Alain du 28/09/2026) : case persistée,
        # DÉFAUT = logarithmique — une config.json d'avant la case n'a pas la
        # clé et garde donc exactement le rendu d'avant.
        if "hist_lineaire" in c:
            self.hist_lineaire = bool(c.get("hist_lineaire"))
            self.var_hist_lineaire.set(self.hist_lineaire)
        # --- Jalon 6 : réglages d'empilement (kappa, méthode/fenêtre rejet)
        if "kappa" in c:
            v = c.get("kappa")
            v = None if v is None else round(float(v), 1)
            etiquette = {None: "Off", 2.0: "2σ", 3.0: "3σ",
                         4.0: "4σ", 5.0: "5σ"}.get(v)
            if etiquette:
                self.var_kappa.set(etiquette)
                self.kappa = None if v is None else float(v)
        methode = c.get("rejet_methode")
        if methode in ("kappa", "winsorized"):
            self.rejet_methode = methode
            self.var_rejet.set("Winsorized (satellites)"
                               if methode == "winsorized"
                               else "kappa-sigma (rapide)")
            self.cb_fenetre.configure(
                state="readonly" if methode == "winsorized" else "disabled")
        fen = c.get("rejet_fenetre")
        if isinstance(fen, int) and not isinstance(fen, bool) \
                and str(fen) in self.cb_fenetre["values"]:
            self.rejet_fenetre = fen
            self.var_fenetre.set(str(fen))
        # --- Jalon 13 : rafraîchissement auto de la référence + équilibrage
        # des canaux (booléen EXPLICITE : une case décochée ne doit pas
        # hériter d'un True d'une session précédente ; clé absente → défauts).
        v = c.get("ref_refresh")
        if isinstance(v, int) and not isinstance(v, bool) \
                and str(v) in self.cb_ref_refresh["values"]:
            self.var_ref_refresh.set(str(v))
        self._on_ref_refresh()
        if "wb_auto" in c:
            self.var_wb.set(bool(c.get("wb_auto")))
        v = c.get("wb_force")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 1.0:
            self.var_wb_force.set(float(v))
        # --- Jalon 17 : filtre anti-brutes très défocalisées — booléen
        # explicite (une case décochée ne doit pas hériter d'un True) ;
        # clé absente → défaut (rejet d'office).
        if "rejeter_flou" in c:
            self.var_rejeter_flou.set(bool(c.get("rejeter_flou")))
        # --- Jalon 54 : recalage colorimétrique « Linear Fit » — booléen
        # explicite (même convention : la clé absente garde le défaut) ;
        # jalon 54b : méthode (« offset » / « gain_offset »).
        if "linear_fit" in c:
            self.var_fit.set(bool(c.get("linear_fit")))
        code_fit = c.get("linear_fit_mode")
        for lib, code in getattr(self, "FIT_METHODES", ()):
            if code == code_fit:
                self.var_fit_methode.set(lib)
                break
        self._on_rejeter_flou()
        self._on_wb()
        # --- Jalon 56 : astrométrie (case + indices de la cible) — chaînes
        # relues par le parseur à l'activation ; case persistée comme les
        # autres (booléen EXPLICITE : décochée doit rester décochée).
        for cle, var in (("astro_ra", self.var_astro_ra),
                         ("astro_dec", self.var_astro_dec),
                         ("astro_champ", self.var_astro_champ)):
            v = c.get(cle)
            if isinstance(v, str):
                var.set(v.strip())
        if "astro_actif" in c:
            self.var_astro.set(bool(c.get("astro_actif")))
        self._on_astro()
        # --- Jalon 96 : annotation temps-réel (objets célèbres / étoiles) —
        # booléens EXPLICITES (une case décochée ne doit pas hériter d'un True
        # d'une session précédente) ; seuil de magnitude borné à la relecture
        # (une valeur aberrante en config ne doit pas noyer l'image).
        if "annoter_objets" in c:
            self.var_annoter_objets.set(bool(c.get("annoter_objets")))
        if "annoter_etoiles" in c:
            self.var_annoter_etoiles.set(bool(c.get("annoter_etoiles")))
        if "annoter_visibles" in c:
            self.var_annoter_visibles.set(bool(c.get("annoter_visibles")))
        if "annoter_sauvegarde" in c:
            self.var_annoter_sauvegarde.set(bool(c.get("annoter_sauvegarde")))
        v = c.get("seuil_mag_etoiles")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 20.0:
            self.var_seuil_mag_etoiles.set(f"{float(v):.1f}")
        # --- Jalon 56 (étape 4) : photométrie (zéro-point Gaia) — booléen
        # EXPLICITE, comme les autres cases.
        if "photo_actif" in c:
            self.var_photo.set(bool(c.get("photo_actif")))
        self._on_photo()
        # --- Jalon 56 (étape 5) : application des gains photométriques — OPT-IN
        # (case décochée par défaut : clé absente = décochée).
        if "photo_gains_actif" in c:
            self.var_photo_gains.set(bool(c.get("photo_gains_actif")))
        self._on_photo_gains()
        # --- Jalon 58 : SPCC absolue — case OPT-IN (clé absente = décochée) et
        # profils retenus (capteur, filtres R/G/B, référence de blanc). Un nom
        # qui ne figure PLUS dans la base est IGNORÉ (on garde le défaut) :
        # un profil disparu ne doit pas lancer une SPCC impossible.
        categorie = {"spcc_capteur": "capteur", "spcc_fr": "filtres",
                     "spcc_fg": "filtres", "spcc_fb": "filtres",
                     "spcc_blanc": "blancs"}
        # v2.40.0 : le TYPE de capteur (mono / couleur OSC) se restaure AVANT
        # les profils — c'est lui qui décide de LA LISTE dans laquelle ils
        # doivent exister (un capteur OSC n'est pas dans la liste mono, et
        # réciproquement). Valeur inconnue : type d'usage (mono) conservé.
        if c.get("spcc_type") in (self.SPCC_TYPE_MONO, self.SPCC_TYPE_OSC):
            self.var_spcc_type.set(c.get("spcc_type"))
            self._on_spcc_type()     # repeuple capteurs/filtres + libellés
        for cle, var in (("spcc_capteur", self._spcc_vars.get("capteur")),
                         ("spcc_fr", self._spcc_vars.get("fr")),
                         ("spcc_fg", self._spcc_vars.get("fg")),
                         ("spcc_fb", self._spcc_vars.get("fb")),
                         ("spcc_blanc", self._spcc_vars.get("blanc"))):
            v = c.get(cle)
            if var is None or not isinstance(v, str) or not v.strip():
                continue
            liste = self._spcc_noms.get(categorie[cle], ())
            if not liste or v.strip() in liste:
                var.set(v.strip())
        if "spcc_actif" in c:
            self.var_spcc.set(bool(c.get("spcc_actif")))
        self._on_spcc()
        # --- Jalon 6 : réglages VeraLux (moteur tiers opt-in)
        mode_res = c.get("vl_mode_res")
        if mode_res in ("fond cible (auto)", "logD forcé"):
            self.var_vl_mode_res.set(mode_res)
            self._sync_vl_mode()   # répercute dans disp + libellé bouton 🔒
        v = c.get("vl_target")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.10 <= float(v) <= 0.45:
            self.var_vl_target.set(float(v))
            self.disp.vl_target_bg = float(v)
        v = c.get("vl_logd")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 7.0:
            self.var_vl_logd.set(float(v))
            self.disp.vl_log_d = float(v)
        profil = c.get("vl_profil")
        if profil and profil in self.cb_vl_profil["values"]:
            self.var_vl_profil.set(profil)
            self.disp.vl_profil = profil
        if c.get("vl_graxpert") and gx_live.commande_valide(
                self.var_cmd_graxpert.get().strip()):
            self.var_vl_graxpert.set(True)
            self._on_vl_graxpert()   # sans popup : commande validée avant
        # --- Jalon 9 (remis le 16/09/2026) : débruitage live (méthode +
        # force tolérantes : méthode inconnue → nlm, force hors [0,1] → 0.5)
        methode_dn = c.get("vl_denoise_methode")
        if methode_dn in self.VL_DN_LABELS:
            self.var_vl_dn_methode.set(self.VL_DN_LABELS[methode_dn])
        v = c.get("vl_denoise_force")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 1.0:
            self.var_vl_dn_force.set(float(v))
        self.disp.vl_denoise_methode = self.VL_DN_CODES.get(
            self.var_vl_dn_methode.get(), "nlm")
        self.disp.vl_denoise_force = self.var_vl_dn_force.get()
        if c.get("vl_denoise"):
            self.var_vl_dn.set(True)
            self._on_vl_denoise()    # sans popup : aucun outil externe requis
        # --- Jalon 12 : netteté live (cadre INDÉPENDANT du moteur
        # d'étirement : elle s'applique en STF/manuel comme en VeraLux).
        # Itérations restaurées seulement si elles sont dans les bornes du
        # module : une valeur aberrante (99) n'est pas « rabattue »
        # silencieusement, le défaut (5) reste. scl_sharp.set() → passe par le
        # callback du curseur (valeur + étiquette + disp, une seule voie).
        v = c.get("vl_sharp_iterations")
        if isinstance(v, int) and not isinstance(v, bool) \
                and 1 <= v <= nettete_live.ITERATIONS_MAX:
            self.scl_sharp.set(float(v))
        self.disp.vl_sharp_iterations = int(round(self.var_vl_sharp_iter.get()))
        if c.get("vl_sharp"):
            self.var_vl_sharp.set(True)
            self._on_vl_sharp()      # sans popup : aucun outil externe requis
        # --- Jalon 22 : SCNR + démagenta live (booléens explicites, aucun
        # outil externe requis — appliqués après composition, avant étirement).
        if c.get("vl_scnr"):
            self.var_vl_scnr.set(True)
            self._on_vl_scnr()
        if c.get("vl_scnr_doux"):
            self.var_vl_scnr_doux.set(True)
            self._on_vl_scnr_doux()
        if c.get("vl_demagenta"):
            self.var_vl_demagenta.set(True)
            self._on_vl_demagenta()
        # v2.48.0 (jalon 85) : force du SCNR et du démagenta — restaurées de
        # façon TOLÉRANTE (valeur hors [0,1] ou illisible : IGNORÉE, la valeur
        # d'usage reste), comme la force du bruit chromatique plus bas.
        for _cle, _var in (("vl_scnr_force", self.var_vl_scnr_force),
                           ("vl_demagenta_force", self.var_vl_demagenta_force)):
            _f = c.get(_cle)
            if isinstance(_f, (int, float)) and not isinstance(_f, bool) \
                    and 0.0 <= float(_f) <= 1.0:
                _var.set(float(_f))
        self.disp.vl_scnr_force = float(self.var_vl_scnr_force.get())
        self.disp.vl_demagenta_force = float(self.var_vl_demagenta_force.get())
        # v2.48.0 (jalon 86) : boost du rouge (SII) — DÉFAUT DÉCOCHÉ, donc une
        # config antérieure (sans la clé) le laisse décoché ; la FORCE est
        # restaurée de façon TOLÉRANTE (hors bornes du module ou illisible :
        # IGNORÉE, la valeur d'usage — le défaut du module — reste).
        if "vl_boost_rouge" in c:
            self.var_vl_boost.set(bool(c.get("vl_boost_rouge")))
            self._on_vl_boost()
        _fb = c.get("vl_boost_force")
        if isinstance(_fb, (int, float)) and not isinstance(_fb, bool) \
                and couleurs_mod.BOOST_ROUGE_MIN <= float(_fb) \
                <= couleurs_mod.BOOST_ROUGE_MAX:
            self.var_vl_boost_force.set(float(_fb))
        self.disp.vl_boost_force = float(self.var_vl_boost_force.get())
        # Préservation de la luminosité : DÉFAUT COCHÉE (comme Siril et
        # PixInsight) — on ne la modifie que si la config porte la clé ET une
        # valeur (même règle que vl_neutre_fond : une config antérieure ne doit
        # pas changer le défaut).
        if "vl_preserve_luminance" in c:
            self.var_vl_preserve.set(bool(c.get("vl_preserve_luminance")))
            self._on_vl_preserve()
        # v2.36.1 : neutralisation de la couleur du fond — DÉFAUT COCHÉE, donc on
        # ne l'active que si la config la demande ET qu'une valeur est présente
        # (une config antérieure ne doit pas changer le défaut).
        if "vl_neutre_fond" in c:
            self.var_vl_neutre.set(bool(c.get("vl_neutre_fond")))
            self._on_vl_neutre()
        # v2.37.0 : réduction du bruit chromatique — DÉFAUT DÉCOCHÉE, donc une
        # config antérieure (sans la clé) la laisse décochée ; la FORCE est
        # restaurée de façon TOLÉRANTE (valeur hors [0,1] ou illisible :
        # IGNORÉE, la valeur d'usage reste — comme le débruitage live).
        v = c.get("vl_chroma_force")
        if isinstance(v, (int, float)) and not isinstance(v, bool) \
                and 0.0 <= float(v) <= 1.0:
            self.var_vl_chroma_force.set(float(v))
        self.disp.vl_chroma_force = float(self.var_vl_chroma_force.get())
        # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma, en pixels PLEINE
        # RÉSOLUTION — restauré TOLÉRANT (hors [0,5 ; 8] ou illisible : IGNORÉ, la
        # valeur d'usage reste le défaut du module) et immédiatement reposé à
        # l'échelle de l'aperçu (`_poser_rayon_chroma`), comme le fait le worker à
        # chaque aperçu.
        r = c.get("vl_chroma_rayon_ref")
        if isinstance(r, (int, float)) and not isinstance(r, bool) \
                and 0.5 <= float(r) <= 8.0:
            self.rayon_chroma_ref = float(r)
            self.var_vl_chroma_rayon.set(float(r))
        self._poser_rayon_chroma(self._echelle_apercu)
        if c.get("vl_chroma"):
            self.var_vl_chroma.set(True)
            self._on_vl_chroma()
        # v2.38.0 : RENDU PLEINE RÉSOLUTION de l'écran — booléen EXPLICITE ; clé
        # absente (config antérieure) → DÉCOCHÉE, le comportement d'origine
        # (aperçu 1600 px) est préservé.
        if c.get("vl_pleine_res_ecran"):
            self.var_vl_pleine_res.set(True)
            self._on_vl_pleine_res()
        # Jalon 42 : cadence d'empilement — restauration TOLÉRANTE (valeur
        # absente/inconnue → « dès réception », jamais de surprise).
        cad = c.get("cadence_lecture")
        if isinstance(cad, (int, float)) and int(cad) in self.CADENCE_LABELS:
            self.var_cadence.set(self.CADENCE_LABELS[int(cad)])
            self._on_cadence()
        self._maj_lbl_sharp()        # étiquette juste dès le démarrage
        # Moteur d'étirement en DERNIER : la bascule VeraLux masque les
        # réglages STF et affiche le cadre VeraLux avec les valeurs ci-dessus.
        # (moteur indisponible → STF conservé, sans popup)
        if c.get("moteur") == "VeraLux" and veralux_moteur.moteur_disponible():
            self.var_moteur.set("VeraLux")
            self._on_moteur()
        # Jalon 47 : source connue → montrer uniquement les cadres utiles
        # (no-op si la source n'a pas changé depuis la construction).
        self._maj_visibilite_cadres()

    def _sauver_config_app(self):
        """Persiste les réglages de l'interface dans config.json (appelé à la
        fermeture). Ne touche pas aux entrées inconnues (extensibilité)."""
        c = dict(_globals_app().CONFIG)          # conserve les clés futures/éventuelles
        if self.var_folder.get().strip():
            c["dossier"] = self.var_folder.get().strip()
        c["cfa"] = self.var_cfa.get()
        # Jalon 19 : réglages de la composition (rôles + dossiers des 4
        # lignes, gains, radio « Canal L ») — relus au démarrage suivant.
        for i in range(4):
            c[f"compo_role_{i}"] = self.var_compo_roles[i].get()
            c[f"compo_dossier_{i}"] = self.var_compo_dossiers[i].get().strip()
        c["compo_nom"] = self.var_compo.get()
        c["compo_gains"] = {canal: self._lire_gains()[canal]
                            for canal in ("R", "G", "B")}
        c["compo_mode_l"] = self.var_compo_mode_l.get()
        # v2.36.0 : normalisation commune des canaux (option, booléen explicite
        # comme les autres cases : une case décochée ne doit pas hériter d'un True).
        c["norm_commune"] = bool(self.var_norm_commune.get())
        # v2.71.0 (jalon 117d) : lissage du combine LRGB (halos d'étoiles) —
        # booléen EXPLICITE (une case décochée ne doit pas hériter d'un True), et
        # seuil de masque borné aux limites du module.
        c["lissage_halos"] = bool(self.var_lissage_halos.get())
        c["lissage_halos_sigma"] = float(self._lire_seuil_halos())
        c["process_existing"] = self.var_process_existing.get()
        # Les commandes ne sont persistées que si leur OUTIL EXISTE (v2.38.5) :
        # une commande de repli (« graxpert … », binaire nu) figée dans
        # config.json empêchait la détection de rejouer au lancement suivant —
        # l'utilisateur installait GraXpert après coup sans que rien ne change.
        # Une commande sans outil est donc RETIRÉE de la config (la détection
        # rejouera), la valeur restant affichée dans le champ de l'interface.
        for cle, var in (("cmd_graxpert", self.var_cmd_graxpert),
                         ("cmd_graxpert_dn", self.var_cmd_graxpert_dn),
                         ("cmd_bxt", self.var_cmd_bxt)):
            txt = var.get().strip()
            if txt and not gx_live.outil_manquant(txt):
                c[cle] = txt
            else:
                c.pop(cle, None)
        if self.var_ext_graxpert.get():
            c["ext_graxpert"] = True
        if self.var_ext_dn.get():
            c["ext_dn"] = True
        c["dn_methode"] = self.DN_EXT_CODES.get(self.var_dn_methode.get(),
                                                "graxpert")
        c["dn_force"] = self.var_dn_force.get()   # force débruitage externe
        if self.var_ext_bxt.get():
            c["ext_bxt"] = True
        # Jalon 22/23 : chaîne couleur (live et externe) — booléens
        # EXPLICITES (True comme False, cf. convention ci-dessous).
        c["vl_scnr"] = bool(self.var_vl_scnr.get())
        c["vl_scnr_doux"] = bool(self.var_vl_scnr_doux.get())
        c["vl_demagenta"] = bool(self.var_vl_demagenta.get())
        # v2.48.0 (jalon 85) : force des deux outils et préservation de la
        # luminosité (curseurs « Force du SCNR » / « Force du démagenta » et
        # case « Préserver la luminosité (L*) »).
        c["vl_scnr_force"] = float(self.var_vl_scnr_force.get())
        c["vl_demagenta_force"] = float(self.var_vl_demagenta_force.get())
        c["vl_preserve_luminance"] = bool(self.var_vl_preserve.get())
        # v2.48.0 (jalon 86) : boost du rouge (SII) — booléen EXPLICITE (comme
        # les autres cases) et force dans les bornes du module.
        c["vl_boost_rouge"] = bool(self.var_vl_boost.get())
        c["vl_boost_force"] = float(self.var_vl_boost_force.get())
        # v2.36.1 : neutralisation de la couleur du fond — booléen EXPLICITE
        # (comme les autres cases : si Alain la décoche, elle reste décochée).
        c["vl_neutre_fond"] = bool(self.var_vl_neutre.get())
        # v2.37.0 : réduction du bruit chromatique — booléen EXPLICITE (comme
        # les autres cases) + force dans [0, 1].
        c["vl_chroma"] = bool(self.var_vl_chroma.get())
        c["vl_chroma_force"] = float(self.var_vl_chroma_force.get())
        # v2.37.4 : rayon de RÉFÉRENCE du flou de chroma, en pixels PLEINE
        # RÉSOLUTION (curseur « Rayon de référence »).
        c["vl_chroma_rayon_ref"] = float(self.rayon_chroma_ref)
        # v2.38.0 : rendu pleine résolution de l'écran (booléen EXPLICITE, comme
        # les autres cases : décoché, il reste décoché).
        c["vl_pleine_res_ecran"] = bool(self.var_vl_pleine_res.get())
        # v2.48.0 : plus de cases couleur dans la chaîne externe (elles suivent
        # l'étirement) — clés ext_scnr / ext_scnr_doux / ext_demagenta plus
        # écrites.
        # Elles sont en plus RETIRÉES d'une configuration antérieure : c'est la
        # seule exception à la règle « ne touche pas aux entrées inconnues »
        # (la docstring de cette méthode) — ces clés ne décrivent plus AUCUN
        # réglage, les garder ferait croire à une case qui n'existe plus.
        for _cle in ("ext_scnr", "ext_scnr_doux", "ext_demagenta"):
            c.pop(_cle, None)
        # v2.37.1 : corrections pré-étirement de la chaîne externe (booléens
        # EXPLICITES, comme toutes les autres cases).
        c["ext_neutre_fond"] = bool(self.var_ext_neutre.get())
        c["ext_chroma"] = bool(self.var_ext_chroma.get())
        c["sigk"] = self.var_sigk.get()
        # Jalon 42 : cadence d'empilement (mode dossier), en secondes.
        c["cadence_lecture"] = int(self.cadence_lecture)
        c["target"] = self.var_target.get()
        c["gamma"] = self.var_gamma.get()
        c["saturation"] = self.var_saturation.get()
        # Jalon 75 : saturation par couleur (R/V/B) et bandes d'histogramme
        # affichées. Les barres de niveaux et l'état figé ne sont PAS persistés.
        c["sat_r"] = float(self.var_sat_r.get())
        c["sat_g"] = float(self.var_sat_g.get())
        c["sat_b"] = float(self.var_sat_b.get())
        c["hist_mode"] = self.hist_mode
        # Jalon 75 : échelle y de la bande basse (log par défaut) — c'est un
        # réglage de LECTURE, pas de session : il se retrouve au lancement.
        c["hist_lineaire"] = bool(getattr(self, "hist_lineaire", False))
        # Jalon 6 : réglages d'empilement et VeraLux. Les booléens sont
        # stockés EXPLICITEMENT (True comme False) : une case décochée ne
        # doit pas hériter d'un True d'une session précédente.
        c["kappa"] = self.kappa                  # None → null JSON (« Off »)
        c["rejet_methode"] = self.rejet_methode
        c["rejet_fenetre"] = int(self.rejet_fenetre)
        # Jalon 13 : alignement (référence auto) + équilibrage des canaux —
        # booléen explicite (comme les autres cases).
        c["ref_refresh"] = int(self.ref_refresh)
        c["wb_auto"] = bool(self.var_wb.get())
        c["wb_force"] = float(self.var_wb_force.get())
        # Jalon 17 : filtre défocalisation — booléen explicite (comme les
        # autres cases : une case décochée ne doit pas hériter d'un True).
        c["rejeter_flou"] = bool(self.var_rejeter_flou.get())
        # Jalon 54 : recalage colorimétrique « Linear Fit » — booléen
        # explicite (comme les autres cases : False doit être persisté) ;
        # jalon 54b : méthode persistée (offset seul par défaut, retour du
        # test réel d'Alain).
        c["linear_fit"] = bool(self.var_fit.get())
        c["linear_fit_mode"] = self._code_fit_methode()
        # Jalon 56 : astrométrie — case d'activation (booléen explicite) et
        # indices de la cible, persistés TELS QUE SAISIS (le parseur les relit
        # à l'activation ; une chaîne non interprétable est refusée à ce
        # moment-là, jamais silencieusement convertie).
        c["astro_actif"] = bool(self.var_astro.get())
        c["astro_ra"] = self.var_astro_ra.get().strip()
        c["astro_dec"] = self.var_astro_dec.get().strip()
        c["astro_champ"] = self.var_astro_champ.get().strip()
        # Jalon 56 (étape 4) : photométrie — case d'activation (booléen
        # explicite : la mesure n'a aucun effet sur l'image, mais son état doit
        # survivre à la session).
        c["photo_actif"] = bool(self.var_photo.get())
        # Jalon 56 (étape 5) : OPT-IN — la case qui écrit les gains dans le
        # stacker. Persistée comme les autres (une case cochée le reste).
        c["photo_gains_actif"] = bool(self.var_photo_gains.get())
        # Jalon 58 : SPCC absolue — case OPT-IN (décochée par défaut : une
        # calibration écrite dans l'image ne doit jamais être activée par
        # surprise) + profils choisis, persistés pour la prochaine session.
        c["spcc_type"] = self.var_spcc_type.get()
        c["spcc_actif"] = bool(self.var_spcc.get())
        for cle, var in (("spcc_capteur", self._spcc_vars.get("capteur")),
                         ("spcc_fr", self._spcc_vars.get("fr")),
                         ("spcc_fg", self._spcc_vars.get("fg")),
                         ("spcc_fb", self._spcc_vars.get("fb")),
                         ("spcc_blanc", self._spcc_vars.get("blanc"))):
            if var is not None:
                c[cle] = var.get()
        c["moteur"] = self.var_moteur.get()
        c["vl_mode_res"] = self.var_vl_mode_res.get()
        c["vl_target"] = self.var_vl_target.get()
        c["vl_logd"] = self.var_vl_logd.get()
        c["vl_profil"] = self.var_vl_profil.get()
        c["vl_graxpert"] = bool(self.var_vl_graxpert.get())
        # Jalon 9 : débruitage live — booléen explicite (comme vl_graxpert),
        # méthode en code interne ("nlm"/"ondelettes"), force dans [0, 1].
        c["vl_denoise"] = bool(self.var_vl_dn.get())
        c["vl_denoise_methode"] = self.VL_DN_CODES.get(
            self.var_vl_dn_methode.get(), "nlm")
        c["vl_denoise_force"] = self.var_vl_dn_force.get()
        # Jalon 12 : netteté live — booléen explicite (comme vl_graxpert/
        # vl_denoise) et itérations en ENTIER borné par le module. La PSF n'est
        # pas persistée : elle vient de la mesure de seeing de la session.
        c["vl_sharp"] = bool(self.var_vl_sharp.get())
        c["vl_sharp_iterations"] = int(self.disp.vl_sharp_iterations)
        # Jalon 96 : annotation temps-réel — booléens EXPLICITES (True comme
        # False) et seuil de magnitude (les cases survivent à la session).
        c["annoter_objets"] = bool(self.var_annoter_objets.get())
        c["annoter_etoiles"] = bool(self.var_annoter_etoiles.get())
        c["annoter_sauvegarde"] = bool(self.var_annoter_sauvegarde.get())
        c["seuil_mag_etoiles"] = self._seuil_mag()
        _globals_app().sauver_config(c)
