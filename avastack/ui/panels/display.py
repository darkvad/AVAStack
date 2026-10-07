# -*- coding: utf-8 -*-
"""Panneau « Affichage » (colonne gauche) — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 105c du chantier de refactoring.
La méthode `_poser_panneau_affichage` est reprise VERBATIM (seul le parent de la colonne
passe de `left` à `parent`, comme aux jalons 105a/105b) : `App` hérite de
`PanneauAffichage`, donc `self` reste l'instance `App` et le comportement est
inchangé AU BIT.

Les attributs d'interface (variables Tk, widgets, méthodes de l'hôte)
sont DÉCLARÉS ici pour le typage statique (`pyright`) — aucune valeur,
aucune logique.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from ...processing import veralux as veralux_moteur


class PanneauAffichage:
    """Mixin : panneau « Affichage » (cf. docstring)."""

    # --- Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement ------
    _lf_affichage: tk.Frame
    rowm: ttk.Frame
    var_moteur: tk.Variable
    cb_moteur: ttk.Combobox
    frm_stf: ttk.Frame
    var_auto: tk.Variable
    var_sigk: tk.Variable
    var_target: tk.Variable
    var_black: tk.Variable
    var_white: tk.Variable
    scl_black: ttk.Scale
    scl_white: ttk.Scale
    frm_communs: ttk.Frame
    var_gamma: tk.Variable
    var_saturation: tk.Variable
    var_sat_r: tk.Variable
    var_sat_g: tk.Variable
    var_sat_b: tk.Variable
    frm_veralux: ttk.Frame
    var_vl_mode_res: tk.Variable
    cb_vl_mode: ttk.Combobox
    var_vl_target: tk.Variable
    var_vl_logd: tk.Variable
    scl_vl_logd: ttk.Scale
    btn_vl_lock: ttk.Button
    var_vl_graxpert: tk.Variable
    var_vl_dn: tk.Variable
    var_vl_dn_methode: tk.Variable
    cb_vl_dn_methode: ttk.Combobox
    var_vl_dn_force: tk.Variable
    var_vl_profil: tk.Variable
    cb_vl_profil: ttk.Combobox
    var_vl_pleine_res: tk.Variable
    disp: Any
    VL_DN_LABELS: Any
    VL_DN_METHODES: Any

    _creer_section_pliable: Callable[..., Any]
    _add_slider: Callable[..., Any]
    _refresh_preview: Callable[..., Any]
    _on_moteur: Callable[..., Any]
    _on_auto: Callable[..., Any]
    _on_target_auto: Callable[..., Any]
    _on_vl_mode: Callable[..., Any]
    _on_vl_target: Callable[..., Any]
    _on_vl_lock: Callable[..., Any]
    _on_vl_graxpert: Callable[..., Any]
    _on_vl_denoise: Callable[..., Any]
    _on_vl_profil: Callable[..., Any]
    _on_vl_pleine_res: Callable[..., Any]
    _on_sat_canaux: Callable[..., Any]

    # --- Jalon 105c : construction du panneau « Affichage »
    def _poser_panneau_affichage(self, parent: tk.Misc) -> None:
        # Corps repris VERBATIM de `app.py` (jalon 105c).
        # --- Affichage
        self._lf_affichage, box, _, _ = self._creer_section_pliable(
            parent, "affichage")
        # Moteur d'étirement : STF intégré (défaut, inchangé) ou VeraLux
        # (moteur tiers, opt-in). Le calcul VeraLux part dans un thread
        # dédié côté DisplayProcessor : l'interface n'est jamais bloquée.
        rowm = self.rowm = ttk.Frame(box)
        rowm.pack(fill="x", pady=(0, 2))
        ttk.Label(rowm, text="Moteur d'étirement :").pack(side="left")
        self.var_moteur = tk.StringVar(value="STF")
        self.cb_moteur = ttk.Combobox(rowm, textvariable=self.var_moteur,
                                      state="readonly", width=9,
                                      values=["STF", "VeraLux"])
        self.cb_moteur.pack(side="left", padx=4)
        self.cb_moteur.bind("<<ComboboxSelected>>", lambda e: self._on_moteur())
        # Réglages propres au STF — regroupés pour être MASQUÉS en mode
        # VeraLux (sinon ils restent visibles et laissés « cochés », sans
        # aucun effet sur l'image : source de confusion).
        self.frm_stf = ttk.Frame(box)
        self.frm_stf.pack(fill="x")
        self.var_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.frm_stf, text="Auto-stretch STF (fond calé sur la cible)",
                        variable=self.var_auto, command=self._on_auto).pack(anchor="w")
        self.var_sigk = tk.DoubleVar(value=2.8)
        self._add_slider(self.frm_stf, "Coupure du bruit (k·σ sous le fond)",
                         self.var_sigk, 0.5, 5.0, 0.1,
                         lambda: (setattr(self.disp, "sigma_k", self.var_sigk.get()),
                                  self._refresh_preview()), "{:.1f}")
        self.var_target = tk.DoubleVar(value=0.25)
        self._add_slider(self.frm_stf, "Luminosité du fond du ciel",
                         self.var_target, 0.10, 0.45, 0.01,
                         self._on_target_auto, "{:.2f}")
        ttk.Separator(self.frm_stf).pack(fill="x", pady=4)
        ttk.Label(self.frm_stf, text="Manuel (si auto décoché) :").pack(anchor="w")
        self.var_black = tk.DoubleVar(value=0.0)
        self.var_white = tk.DoubleVar(value=1.0)
        self.scl_black = self._add_slider(self.frm_stf, "Black point", self.var_black, 0.0, 1.0, 0.005,
                                          lambda: (setattr(self.disp, "black", self.var_black.get()),
                                                   self._refresh_preview()), "{:.3f}")
        self.scl_white = self._add_slider(self.frm_stf, "White point", self.var_white, 0.0, 2.0, 0.005,
                                          lambda: (setattr(self.disp, "white", self.var_white.get()),
                                                                                                      self._refresh_preview()), "{:.3f}")
        # Gamma / saturation : COMMUNS aux deux moteurs (toujours visibles,
        # appliqués après l'étirement quel que soit le mode).
        # NON REDONDANT AVEC LA BARRE « MÉDIAN » de l'histogramme — décision
        # d'Alain, 28/09/2026 : « on laisse comme c'est, à savoir les deux ».
        # À NE PAS « NETTOYER » : la barre médian place le gris moyen PAR LA MTF
        # (MTF(m, m) = 0,5 : la valeur de la barre DEVIENT le gris moyen, c'est
        # elle qui découpe l'histogramme à l'écran), le gamma est une courbe de
        # PUISSANCE appliquée APRÈS l'étage de niveaux — deux courbes
        # différentes : à m = 0,25 la MTF envoie 0,5 sur 0,75, là où γ = 4
        # l'envoie sur 0,06.
        self.frm_communs = ttk.Frame(box)
        self.frm_communs.pack(fill="x")
        vg = tk.DoubleVar(value=1.0)
        self.var_gamma = vg
        # Jalon 79 — `hist=False` sur gamma ET saturation (même règle que les
        # barres de niveaux depuis le jalon 75) : les DEUX bandes de
        # l'histogramme sont calculées AVANT ces étages — bande « brut » =
        # source linéaire, bande « sortie » = sortie du moteur d'étirement —
        # donc un geste sur ces curseurs ne change AUCUNE des deux courbes.
        # Sans cela, chaque pixel de souris payait en plus les deux
        # histogrammes (34 ms mesurés sur l'aperçu couleur) pour un tracé
        # identique. Le moteur d'étirement lui-même n'est plus recalculé non
        # plus (mémoire `DisplayProcessor._moteur_stf`, même jalon).
        self._add_slider(self.frm_communs, "Gamma (les 2 moteurs)", vg, 0.2, 4.0, 0.05,
                         lambda: (setattr(self.disp, "gamma", vg.get()),
                                  self._refresh_preview(hist=False)), "{:.2f}")
        vs = tk.DoubleVar(value=1.0)
        self.var_saturation = vs
        self._add_slider(self.frm_communs, "Saturation (globale)", vs, 0.0, 3.0,
                         0.05,
                         lambda: (setattr(self.disp, "saturation", vs.get()),
                                  self._refresh_preview(hist=False)), "{:.2f}")
        # --- Jalon 75 : saturation PAR COULEUR (R/V/B), demande d'Alain du
        # 28/09/2026 (les colonnes de couleur du grand histogramme de SharpCap).
        # Précision VÉRIFIÉE dans la doc et chez l'auteur : chez SharpCap ces
        # colonnes sont une BALANCE DES CANAUX appliquée AVANT l'étirement
        # (« colour adjustments happen before the stretch ») — or cette
        # correction existe DÉJÀ chez nous, et à sa place photométrique (gains
        # SPCC/Gaia, équilibrage des canaux, Linear Fit) : la rejouer à
        # l'affichage la dupliquerait. Ici c'est donc une VRAIE saturation par
        # couleur : le secteur de TEINTE visé seulement (poids triangulaires
        # sur R/V/B, cf. display.saturation_canaux), après la saturation
        # globale, 1,00 = neutre. La 1re écriture (« c_c = Y + k_c·(c − Y) »)
        # a été REJETÉE après l'essai réel d'Alain : elle changeait le canal
        # partout, si bien que pousser « rouge » verdissait les pixels verts
        # (constat : « quand je pousse l'un, c'est l'autre couleur qui semble
        # se renforcer »).
        self.var_sat_r = tk.DoubleVar(value=1.0)
        self.var_sat_g = tk.DoubleVar(value=1.0)
        self.var_sat_b = tk.DoubleVar(value=1.0)
        for lib, var in (("Saturation rouge", self.var_sat_r),
                         ("Saturation verte", self.var_sat_g),
                         ("Saturation bleue", self.var_sat_b)):
            self._add_slider(self.frm_communs, lib, var, 0.0, 3.0, 0.05,
                             self._on_sat_canaux, "{:.2f}")

        # --- VeraLux (moteur tiers) — caché tant que « STF » est sélectionné
        self.frm_veralux = ttk.Frame(box)
        ttk.Label(self.frm_veralux, text="Résolution du logD :").pack(anchor="w")
        self.var_vl_mode_res = tk.StringVar(value="fond cible (auto)")
        # Jalon 3 : « fond cible (auto) » = le moteur résout lui-même le logD
        # pour amener le fond à la cible, à CHAQUE nouvel empilement (le
        # rythme des frames est le cooldown) ; « logD forcé » = déterministe
        # et réactif (curseur ou bouton 🔒).
        self.cb_vl_mode = ttk.Combobox(self.frm_veralux,
                                       textvariable=self.var_vl_mode_res,
                                       state="readonly", width=16,
                                       values=["fond cible (auto)", "logD forcé"])
        self.cb_vl_mode.pack(anchor="w")
        self.cb_vl_mode.bind("<<ComboboxSelected>>",
                             lambda e: self._on_vl_mode())
        self.var_vl_target = tk.DoubleVar(value=veralux_moteur.TARGET_BG_PAR_DEFAUT)
        self._add_slider(self.frm_veralux, "Luminosité du fond visée (VeraLux)",
                         self.var_vl_target, 0.10, 0.45, 0.01,
                         self._on_vl_target, "{:.2f}")
        self.var_vl_logd = tk.DoubleVar(value=veralux_moteur.LOG_D_PAR_DEFAUT)
        self.scl_vl_logd = self._add_slider(
            self.frm_veralux, "logD forcé",
            self.var_vl_logd, 0.0, 7.0, 0.05,
            lambda: (setattr(self.disp, "vl_log_d", self.var_vl_logd.get()),
                     self._refresh_preview()), "{:.2f}")
        self.btn_vl_lock = ttk.Button(self.frm_veralux,
                                      text="🔒 Verrouiller le logD résolu",
                                      command=self._on_vl_lock)
        self.btn_vl_lock.pack(anchor="w", pady=(2, 0))
        # Jalon 4 : GraXpert « live » — appliqué AVANT l'étirement VeraLux,
        # dans le thread solveur, à chaque nouvel empilement (opt-in). Le BXT
        # reste manuel (bouton ⚡ de la section Traitement externe).
        self.var_vl_graxpert = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_veralux,
                        text="GraXpert live (avant étirement)",
                        variable=self.var_vl_graxpert,
                        command=self._on_vl_graxpert).pack(anchor="w",
                                                           pady=(2, 0))
        # Jalon 9 (remis le 16/09/2026) : débruitage local AVANT l'étirement
        # — algorithmes rapides numpy/OpenCV (aucun subprocess), opère en
        # vue « empilement » uniquement (cf. _sync_vl_denoise_vue). Force en
        # 0..1 : seuil k-sigma (ondelettes) / h (NLM) auto-adaptés au bruit
        # réel de chaque empilement.
        rowdn = ttk.Frame(self.frm_veralux)
        rowdn.pack(fill="x", pady=(2, 0))
        self.var_vl_dn = tk.BooleanVar(value=False)
        ttk.Checkbutton(rowdn, text="Débruitage live (avant étirement)",
                        variable=self.var_vl_dn,
                        command=self._on_vl_denoise).pack(side="left")
        self.var_vl_dn_methode = tk.StringVar(value=self.VL_DN_LABELS["nlm"])
        self.cb_vl_dn_methode = ttk.Combobox(
            rowdn, textvariable=self.var_vl_dn_methode, state="readonly",
            width=15, values=[lib for _, lib in self.VL_DN_METHODES])
        self.cb_vl_dn_methode.pack(side="left", padx=(4, 0))
        self.cb_vl_dn_methode.bind("<<ComboboxSelected>>",
                                   lambda e: self._on_vl_denoise())
        self.var_vl_dn_force = tk.DoubleVar(value=0.5)
        self._add_slider(self.frm_veralux, "Force du débruitage (live)",
                         self.var_vl_dn_force, 0.0, 1.0, 0.05,
                         self._on_vl_denoise, "{:.2f}")
        # Jalon 22 (décision d'Alain) : SCNR + démagenta — APRÈS composition
        # (image COULEUR du composite) ; no-op sur un composite monochrome
        # (Mono). Depuis le jalon 85 la chaîne couleur suit l'ÉTIREMENT (elle
        # n'est plus dans la chaîne externe) : elle vaut pour LES DEUX VUES
        # (v2.48.1), « empilement » comme « traitée ».
        # Jalon 41 (décision d'Alain) : les CASES couleur sont sorties du
        # cadre VeraLux (cadre « Couleur live » indépendant, plus bas) — la
        # chaîne couleur est appliquée par le solveur VeraLux ET par le
        # moteur STF/manuel (process(), testé au jalon 22). L'étiquette et le
        # curseur d'état des calculs sont sortis AUSSI (cadre « État des
        # calculs », visible dans les DEUX modes).

        # Jalon 5 : profil capteur du moteur VeraLux (réponse couleur du
        # capteur — Rec.709 par défaut). Fait partie de la clé des réglages :
        # changer de profil relance la résolution au prochain rendu.
        ttk.Label(self.frm_veralux, text="Profil capteur :").pack(anchor="w")
        self.var_vl_profil = tk.StringVar(value=veralux_moteur.PROFIL_PAR_DEFAUT)
        self.cb_vl_profil = ttk.Combobox(self.frm_veralux,
                                         textvariable=self.var_vl_profil,
                                         state="readonly",
                                         values=list(veralux_moteur.profils_disponibles()))
        self.cb_vl_profil.pack(anchor="w")
        self.cb_vl_profil.bind("<<ComboboxSelected>>",
                               lambda e: self._on_vl_profil())

        # --- v2.38.0 : RENDU PLEINE RÉSOLUTION pour l'écran (demande d'Alain,
        # 26/09/2026 : « sur l'écran, je veux pouvoir zoomer sur l'image pleine
        # résolution »). Coché : la chaîne d'affichage (GraXpert/débruitage/
        # netteté/couleurs/étirement) tourne sur l'empilement COMPLET — l'écran
        # montre alors EXACTEMENT ce que le fichier contiendra, et le zoom
        # recadre de VRAIS pixels au lieu de grossir l'aperçu 1600 px (mesuré au
        # jalon 66 : l'anneau de couleur des étoiles, invisible sur l'aperçu,
        # n'apparaît que dans les fichiers). Coût mesuré ×4,3 (~7-8 s par
        # recalcul complet contre ~1,7 s) : décoché par défaut.
        # v2.38.1 (demande d'Alain, 27/09/2026 : « ok pour le rendu pleine
        # résolution en vue traitée ») : l'option vaut pour les DEUX vues — en
        # vue « traitée » la source est le résultat du ⚡ traitement externe
        # (`proc_full`, déjà mémorisé pour les sauvegardes : aucune copie en
        # plus), cf. `_src_pleine_res`.
        self.var_vl_pleine_res = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.frm_veralux,
                        text="Rendu pleine résolution (zoom fidèle)",
                        variable=self.var_vl_pleine_res,
                        command=self._on_vl_pleine_res).pack(anchor="w",
                                                             pady=(6, 0))
        ttk.Label(self.frm_veralux,
                  text="L'écran étire l'image COMPLÈTE — empilement, ou résultat "
                       "traité en vue « traitée » : le zoom montre de vrais "
                       "pixels, identiques au fichier enregistré. Plus lent "
                       "(~7-8 s par rendu, contre ~2 s pour l'aperçu).",
                  foreground="#888888", wraplength=310).pack(anchor="w")
