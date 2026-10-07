# -*- coding: utf-8 -*-
"""Panneau d'histogramme (jalon 75) : deux bandes, barres de niveaux et
saturation par couleur — mixin TYPÉ.

Extrait de `avastack/ui/app.py` au jalon 103 du chantier de refactoring : le
TRACÉ et les GESTES de l'histogramme, l'étage de NIVEAUX (barres Noir/Médian/
Blanc, gel/reprise de l'auto) et la SATURATION par couleur R/V/B. Les méthodes
sont reprises VERBATIM : `App` hérite de `PanneauHistogramme`, donc `self` reste
l'instance `App` et le rendu est inchangé AU BIT.

Les attributs d'interface (constantes et variables Tk de la classe `App`) sont
DÉCLARÉS ici pour le typage statique (`pyright`).
"""

import math
from typing import Callable

import numpy as np
import tkinter as tk
from tkinter import ttk

from ... import journal
from ...processing import DisplayProcessor
from ...processing import display as display_mod
from ..constants import HIST_POINTS


class PanneauHistogramme:
    """Mixin : histogramme 2 bandes + niveaux + saturation (cf. docstring)."""

    # Interface attendue sur l'hôte (`App`) — DÉCLARATIONS DE TYPAGE seulement.
    HIST_LABELS: dict[str, str]
    HIST_MODES: tuple[tuple[str, str], ...]
    HIST_MARGE: int
    HIST_PRISE: int
    HIST_RANG_PX: int
    W_HIST: int

    disp: DisplayProcessor
    cv_hist: tk.Canvas
    lbl_hist_etat: ttk.Label
    btn_figer: ttk.Button
    cb_hist_mode: ttk.Combobox
    chk_hist_lineaire: ttk.Checkbutton
    ent_bar: dict[str, ttk.Entry]
    var_bar_noir: tk.DoubleVar
    var_bar_median: tk.DoubleVar
    var_bar_blanc: tk.DoubleVar
    var_hist_mode: tk.StringVar
    var_hist_lineaire: tk.BooleanVar
    var_sat_r: tk.DoubleVar
    var_sat_g: tk.DoubleVar
    var_sat_b: tk.DoubleVar
    var_moteur: tk.StringVar
    var_vl_mode_res: tk.StringVar
    var_vl_logd: tk.DoubleVar

    hist_mode: str
    hist_lineaire: bool
    _hist_brut: tuple[list[np.ndarray], float] | None
    _hist_sortie: tuple[list[np.ndarray], float] | None
    _hist_erreur: str
    _hist_drag: str | None
    _vl_mode_avant_fige: str | None

    # Méthodes de l'hôte (`App`) appelées par ce mixin.
    _refresh_preview: Callable[..., None]
    _sync_vl_mode: Callable[..., None]

    def _hist_taille(self):
        """(largeur, hauteur) à utiliser pour le tracé et les gestes : les
        dimensions RÉELLES du Canvas, avec repli sur les dimensions demandées
        tant que la fenêtre n'est pas encore dessinée — `winfo_width()` rend 1
        pour un widget non affiché, et un histogramme tracé sur 1 px ne serait
        pas « approximatif » mais INVISIBLE (constat du banc : les gestes et le
        tracé étaient tous décalés au démarrage)."""
        w = self.cv_hist.winfo_width()
        h = self.cv_hist.winfo_height()
        return (w if w >= 40 else self.W_HIST,
                h if h >= 40 else self._hauteur_hist())

    # ============================= jalon 75 : histogramme 2 bandes + niveaux
    def _hauteur_hist(self):
        """Hauteur du Canvas d'histogramme : deux bandes, ou une seule (plus
        haute) — l'image regagne alors 58 px, utile sur une fenêtre réduite."""
        return 176 if self.hist_mode == "les_deux" else 118

    def _poser_panneau_hist(self, parent):
        """Panneau du jalon 75 sous l'histogramme : choix des bandes, les trois
        niveaux en CHAMPS DE SAISIE (motif du jalon 27 : on doit pouvoir viser
        une valeur précise), ⏹ Figer / ▶ Reprendre et « ↺ Auto », plus la ligne
        d'état qui dit TOUJOURS dans quel mode on est — un étirement figé sans
        avertissement serait une chute silencieuse, et c'est le seul vrai
        danger de cette fonction.

        La barre MÉDIAN est CONSERVÉE en même temps que le curseur « Gamma »
        (décision d'Alain, 28/09/2026 : les deux restent) — cf. le commentaire
        du curseur Gamma : deux courbes différentes, aucun doublon à retirer."""
        row = ttk.Frame(parent)
        row.pack(fill="x")
        ttk.Label(row, text="Histogramme :").pack(side="left")
        self.var_hist_mode = tk.StringVar(
            value=self.HIST_LABELS.get(self.hist_mode, "Les deux"))
        self.cb_hist_mode = ttk.Combobox(
            row, textvariable=self.var_hist_mode, state="readonly", width=16,
            values=[lib for lib, _ in self.HIST_MODES])
        self.cb_hist_mode.pack(side="left", padx=(2, 8))
        self.cb_hist_mode.bind("<<ComboboxSelected>>",
                               lambda e: self._on_hist_mode())
        self.btn_figer = ttk.Button(row, text="⏹ Figer l'auto",
                                    command=self._on_figer)
        self.btn_figer.pack(side="left", padx=2)
        ttk.Button(row, text="↺ Auto", command=self._on_niveaux_auto).pack(
            side="left", padx=2)
        self.lbl_hist_etat = ttk.Label(row, text="", foreground="#888888",
                                       wraplength=250)
        self.lbl_hist_etat.pack(side="left", padx=6)

        row2 = ttk.Frame(parent)
        row2.pack(fill="x")
        self.var_bar_noir = tk.DoubleVar(value=0.0)
        self.var_bar_median = tk.DoubleVar(value=0.5)
        self.var_bar_blanc = tk.DoubleVar(value=1.0)
        self.ent_bar = {}
        for cle, lib, var in (("noir", "Noir %", self.var_bar_noir),
                              ("median", "Médian %", self.var_bar_median),
                              ("blanc", "Blanc %", self.var_bar_blanc)):
            ttk.Label(row2, text=lib).pack(side="left", padx=(6, 2))
            ent = ttk.Entry(row2, textvariable=var, width=7, justify="right")
            ent.pack(side="left")
            ent.bind("<Return>", lambda e: self._on_niveaux_saisie())
            ent.bind("<FocusOut>", lambda e: self._on_niveaux_saisie())
            self.ent_bar[cle] = ent
        # Échelle VERTICALE de la bande basse (décision d'Alain, 28/09/2026 :
        # « linéaire » sur la SEULE bande basse — celle où l'on pose les
        # barres —, la bande haute gardant son log). Posée ICI et pas dans la
        # ligne du dessus : cette ligne-ci restait plus étroite que la
        # précédente, donc la géométrie de la fenêtre ne bouge pas (leçon du
        # jalon 72 : `pack` abandonne SILENCIEUSEMENT un widget qui ne tient
        # plus).
        self.var_hist_lineaire = tk.BooleanVar(value=bool(self.hist_lineaire))
        self.chk_hist_lineaire = ttk.Checkbutton(
            row2, text="Échelle y linéaire (bande basse)",
            variable=self.var_hist_lineaire, command=self._on_hist_lineaire)
        self.chk_hist_lineaire.pack(side="left", padx=(12, 4))
        ttk.Label(row2, text="(barres = bande basse « sortie du moteur » · "
                             "double-clic = défaut)",
                  foreground="#888888").pack(side="left", padx=8)
        self._maj_niveaux_vue()

    def _maj_niveaux_vue(self):
        """Resynchronise les champs de saisie et la ligne d'état sur l'état
        RÉEL de l'affichage (barres et gel) — appelée après tout changement venu
        de l'affichage lui-même (glissement d'une barre, ↺, nouvelle session) :
        une seule source de vérité, jamais deux affichages qui divergent."""
        d = self.disp
        for var, val in ((self.var_bar_noir, d.bar_noir),
                         (self.var_bar_median, d.bar_median),
                         (self.var_bar_blanc, d.bar_blanc)):
            if abs(float(var.get()) - float(val) * 100.0) > 0.05:
                var.set(round(float(val) * 100.0, 1))
        texte, coul = self._texte_etat_niveaux()
        self.lbl_hist_etat.config(text=texte, foreground=coul)

    def _texte_etat_niveaux(self):
        """Phrase d'état des niveaux + couleur : dit ce qui AGIT — l'auto du
        moteur (les barres sont un décalage PAR-DESSUS) ou l'utilisateur seul
        (étirement figé) — ET la cible de fond du moteur, parce que c'est elle
        qui décide où tombe la « colline » de la bande basse (demande d'Alain,
        28/09/2026 : « c'est quoi les 25 % ? » — c'est le défaut du STF ; en
        VeraLux c'est SON curseur, 0,16 sur son M31)."""
        d = self.disp
        av = self.var_moteur.get() if hasattr(self, "var_moteur") else "STF"
        if av == "VeraLux":
            cible = "fond visé %.0f %%" % (100 * float(d.vl_target_bg))
            # Tant que le solveur n'a pas rendu son résultat, l'écran (et donc
            # la bande basse, et donc la marque « fond ») montre l'image
            # d'ATTENTE du STF : la ligne doit le dire, sinon elle annonce un
            # fond visé que la marque ne peut pas encore refléter.
            if d.vl_en_cours():
                cible += ", calcul en cours"
        else:
            cible = "cible du fond %.0f %%" % (100 * float(d.target))
        if d.fige:
            texte, coul = ("auto FIGÉ (%s, %s) — tes barres seules agissent"
                           % (av, cible), "#c98a00")
        else:
            texte, coul = ("Niveaux : décalage sur l'auto (%s, %s, le moteur "
                           "continue)" % (av, cible), "#888888")
        # Échelle de la bande basse : DITE ici, parce qu'une échelle muette est
        # un piège (la même courbe ne raconte pas la même chose en log et en
        # linéaire — mesuré : le fond fait 66 % de l'axe en log, 10,5 % en
        # linéaire). Elle ne concerne QUE cette bande.
        if getattr(self, "hist_lineaire", False):
            texte += " · échelle y LINÉAIRE (bande basse)"
        return texte, coul


    def _niveaux_pose(self):
        """Reporte les 3 valeurs dans l'intervalle licite et dans l'ordre
        attendu (noir < médian < blanc, écart mini) : des barres croisées
        donnent un rendu absurde, on ne le laisse pas faire."""
        d = self.disp
        noir = min(max(float(d.bar_noir), 0.0), 0.98)
        blanc = min(max(float(d.bar_blanc), noir + 0.02), 1.0)
        median = min(max(float(d.bar_median), noir + 0.01), blanc - 0.01)
        d.bar_noir, d.bar_median, d.bar_blanc = noir, median, blanc

    def _on_hist_lineaire(self):
        """Case « Échelle y linéaire (bande basse) » — décision d'Alain du
        28/09/2026, prise sur MESURE (ses frames, 20 moyennées, STF auto) :
        la largeur à mi-hauteur du fond passe de **170 bacs (66 % de l'axe)**
        à **27 bacs (10,5 %)** — la « colline » devient un vrai PIC — au prix
        de la queue, qui tombe de 34 px à 0,65 px (p99 des pixels) : les
        étoiles et la nébuleuse quittent alors la courbe. La bande HAUTE n'est
        PAS concernée : en linéaire elle ne montrait plus que 10 bacs sur 256.

        Ni rendu d'image (l'échelle ne touche QUE le tracé) ni recalcul
        d'histogramme (les bacs sont déjà en mémoire) : tracé immédiat, règle
        du défaut ③ du 28/09/2026."""
        self.hist_lineaire = bool(self.var_hist_lineaire.get())
        self._maj_niveaux_vue()   # l'échelle est DITE dans la ligne d'état
        self._draw_hist()

    def _on_hist_mode(self):
        """Choix des bandes affichées (les deux / brut / sortie)."""
        lib = self.var_hist_mode.get()
        for etiquette, code in self.HIST_MODES:
            if etiquette == lib:
                self.hist_mode = code
                break
        self.cv_hist.config(height=self._hauteur_hist())
        self._draw_hist()

    def _on_niveaux_saisie(self, *_a):
        """Saisie chiffrée d'un niveau, en % de l'axe de sortie : borne,
        ordonne, applique et redessine immédiatement."""
        d = self.disp
        for cle, attr in (("noir", "bar_noir"), ("median", "bar_median"),
                          ("blanc", "bar_blanc")):
            try:
                v = float(self.ent_bar[cle].get().replace(",", ".")) / 100.0
            except (ValueError, tk.TclError):
                v = getattr(d, attr)
            setattr(d, attr, v)
        self._niveaux_pose()
        self._maj_niveaux_vue()
        # Règle des barres (défaut du 28/09/2026) : le tracé suit IMMÉDIATEMENT,
        # et sans recalcul — une barre ne change pas la courbe (elle est tracée
        # sur la sortie du moteur, AVANT l'étage de niveaux).
        self._draw_hist()
        self._refresh_preview(hist=False)

    def _on_niveaux_auto(self):
        """« ↺ Auto » : les trois barres reviennent à l'identité
        (0 / 50 / 100 %), c'est-à-dire au rendu du moteur — sans rien figer ni
        défiger (le gel est un autre bouton)."""
        d = self.disp
        d.bar_noir, d.bar_median, d.bar_blanc = 0.0, 0.5, 1.0
        self._maj_niveaux_vue()
        self._draw_hist()
        self._refresh_preview(hist=False)

    def _on_figer(self):
        """⏹ Figer / ▶ Reprendre l'étirement AUTOMATIQUE du moteur (jalon 75).

        STF : les stats lissées sont gelées (elles ne se recalculent plus ET
        n'avancent plus) → l'image ne bouge plus toute seule et les barres
        deviennent le seul levier.
        VeraLux : le moteur n'a pas de stats mais un logD RÉSOLU — le gel le
        VERROUILLE (mode « logD forcé », mécanisme du jalon 3), et Reprendre
        rend la main au fond cible. C'est ce qui rend la fonction disponible
        DANS LES DEUX MOTEURS (demande d'Alain, 28/09/2026)."""
        d = self.disp
        gel = not d.fige
        d.fige = gel
        veralux = self.var_moteur.get() == "VeraLux"
        if veralux and gel:
            self._vl_mode_avant_fige = self.var_vl_mode_res.get()
            resolu = d.vl_log_d_resolu
            if resolu is not None:
                self.var_vl_logd.set(round(float(resolu), 4))
            self.var_vl_mode_res.set("logD forcé")
            self._sync_vl_mode()
        elif veralux and not gel:
            self.var_vl_mode_res.set(self._vl_mode_avant_fige
                                     or "fond cible (auto)")
            self._sync_vl_mode()
        elif not gel:
            d.reprendre_auto()          # STF : stats oubliées → recalage net
        self.btn_figer.config(text=("▶ Reprendre l'auto" if gel
                                    else "⏹ Figer l'auto"))
        self._maj_niveaux_vue()
        self._refresh_preview()

    def _on_sat_canaux(self):
        """Saturation par couleur (R/V/B) : les trois gains sont posés
        ENSEMBLE, en un tuple (jamais muté en place — le solveur live lit une
        référence cohérente), puis l'aperçu est re-rendu.

        Jalon 79 : `hist=False` (même règle que gamma, saturation globale et
        barres de niveaux) — la saturation par couleur s'applique APRÈS la
        sortie du moteur d'étirement, donc AUCUNE des deux bandes de
        l'histogramme ne change : la recalculer coûtait les deux histogrammes
        (34 ms sur l'aperçu couleur) pour un tracé identique."""
        self.disp.sat_canaux = (float(self.var_sat_r.get()),
                                float(self.var_sat_g.get()),
                                float(self.var_sat_b.get()))
        self._refresh_preview(hist=False)


    # --- calcul des histogrammes ---------------------------------------------
    @staticmethod
    def _hist_canaux(img, plage=None, bins=256, points=None):
        """Histogrammes PAR CANAL d'une image, ÉCHANTILLONNÉE pour que le coût
        ne dépende pas de la résolution (jalon 75 : le calcul quitte le thread
        d'acquisition — où il coûtait ~55 ms par frame sur 1600 px, et jusqu'à
        ~60 ms en pleine résolution — pour le thread d'affichage).

        plage : (lo, hi) imposé — bande « sortie du moteur », 0..1 ; None =
        axe AUTOMATIQUE sur p99,9 × 1,15, comme depuis toujours (bande « brut »,
        c'est le seul choix qui rende un empilement linéaire lisible : mesuré
        sur NGC 7331, le fond tombe à 52 % de cet axe, les p99/p99,9 à 57/87 %).
        Retourne (liste des 256 comptes, valeur haute de l'axe).
        """
        img = np.asarray(img, np.float32)
        pas = max(1, int(round(math.sqrt(
            img.shape[0] * img.shape[1] / float(points or HIST_POINTS)))))
        ech = img[::pas, ::pas]
        chans = [ech] if ech.ndim == 2 else [ech[..., i] for i in range(3)]
        if plage is None:
            lo, hi = 0.0, float(np.percentile(ech, 99.9)) * 1.15 + 1e-6
        else:
            lo, hi = float(plage[0]), float(plage[1])
        return ([np.histogram(c, bins=bins, range=(lo, hi))[0].astype(np.float64)
                 for c in chans], hi)

    def _maj_histogrammes(self, src_lin, brut=None):
        """Recalcule les DEUX bandes et redessine : « Brut (linéaire) » (la
        source donnée à la chaîne d'affichage) et « Sortie du moteur » (l'image
        AVANT les barres — c'est elle que les barres découpent).

        Un échec ici ne doit JAMAIS emporter la boucle d'interface (un
        historique de panne muette dans ce projet) : il est journalisé et se
        voit à l'écran.
        """
        try:
            self._hist_brut = (None if src_lin is None
                               else self._hist_canaux(src_lin))
            self._hist_sortie = (None if brut is None
                                 else self._hist_canaux(brut, plage=(0.0, 1.0)))
            self._hist_erreur = ""
        except Exception as exc:                    # noqa: BLE001 (journalisé)
            self._hist_brut = self._hist_sortie = None
            self._hist_erreur = str(exc)
            journal.erreur("histogramme", exc)
        self._draw_hist()

    # --- barres : glisser / double-clic --------------------------------------
    def _hist_zone_sortie(self):
        """(y0, y1) de la bande « Sortie du moteur », ou None si elle n'est
        pas affichée (le mode « brut » ne porte pas les barres)."""
        h = self._hist_taille()[1]
        if self.hist_mode == "brut":
            return None
        if self.hist_mode == "sortie":
            return (4, h - 18)
        haut = (h - 30) // 2
        return (h - haut - 18, h - 18)

    def _hist_x(self, valeur, w=None):
        """Position en pixels d'une valeur [0..1] sur l'axe de sortie."""
        w = w or self._hist_taille()[0]
        m = self.HIST_MARGE
        return m + float(valeur) * (w - 2 * m)

    def _hist_valeur(self, x, w=None):
        """Valeur [0..1] sous une abscisse de l'axe de sortie."""
        w = w or self._hist_taille()[0]
        m = self.HIST_MARGE
        return min(max((x - m) / float(max(w - 2 * m, 1)), 0.0), 1.0)

    def _hist_hit(self, x, w=None):
        """Barre sous le curseur ('noir' / 'median' / 'blanc') ou None."""
        if self._hist_zone_sortie() is None:
            return None
        best, dmin = None, self.HIST_PRISE + 1
        for cle, val in (("noir", self.disp.bar_noir),
                         ("median", self.disp.bar_median),
                         ("blanc", self.disp.bar_blanc)):
            d = abs(self._hist_x(val, w) - x)
            if d < dmin:
                best, dmin = cle, d
        return best

    def _hist_press(self, e):
        self._hist_drag = self._hist_hit(e.x)
        if self._hist_drag:
            self.cv_hist.config(cursor="sb_h_double_arrow")

    def _hist_drag_move(self, e):
        """Glissement : la valeur suit le doigt, le TRACÉ aussi, puis le RENDU.

        `_draw_hist()` est appelé ICI, et il ne RECALCULE rien : il ne fait que
        retracer les canaux DÉJÀ en mémoire (`_hist_brut` / `_hist_sortie`) —
        c'est légitime, la donnée du moteur ne change pas quand une barre bouge,
        seule la découpe change (la bande basse est la sortie du moteur AVANT
        les barres). L'oublier était un DÉFAUT RÉEL (constat d'Alain après son
        essai du 28/09/2026) : « quand l'empilement est fini, si on touche aux
        barres, l'image change alors que la position de la barre ne change pas,
        ou pas complètement, comme si le bas n'était pas rafraîchi ». Exactement
        cela : sans frame qui arrive, plus rien n'appelait `_draw_hist()` (il ne
        vivait que dans `_maj_histogrammes`), donc le panneau restait figé sur
        la position de DÉPART ; et à 0,2 fps une frame venait le rattraper par
        sauts, d'où la barre « à moitié » déplacée. Le tracé est posé AVANT le
        rendu (il est ~20 fois moins cher, quelques ms contre ~80) pour que la
        poignée suive le doigt sans attendre la fin de l'image."""
        if not self._hist_drag:
            return
        v = self._hist_valeur(e.x)
        d = self.disp
        if self._hist_drag == "noir":
            d.bar_noir = min(v, d.bar_blanc - 0.02)
        elif self._hist_drag == "blanc":
            d.bar_blanc = max(v, d.bar_noir + 0.02)
        else:
            d.bar_median = v
        self._niveaux_pose()
        self._maj_niveaux_vue()
        self._draw_hist()
        self._refresh_preview(hist=False)

    def _hist_release(self, _e=None):
        self._hist_drag = None
        self.cv_hist.config(cursor="")
        # Le DERNIER mouvement peut manquer (relâchement hors du Canvas, ou
        # évènement perdu) : on retrace une fois pour que le panneau montre la
        # valeur RÉELLEMENT appliquée et non l'avant-dernière (même défaut que
        # celui corrigé dans `_hist_drag_move`).
        self._draw_hist()

    def _hist_dblclick(self, e):
        """Double-clic sur une barre : elle revient à sa valeur d'origine
        (0 / 50 / 100 %), c'est-à-dire au rendu du moteur."""
        cle = self._hist_hit(e.x)
        if not cle:
            return
        setattr(self.disp, "bar_" + cle,
                {"noir": 0.0, "median": 0.5, "blanc": 1.0}[cle])
        self._niveaux_pose()
        self._maj_niveaux_vue()
        # Même règle que le glissement : le tracé suit tout de suite, et
        # `hist=False` parce qu'une barre ne change PAS la courbe (elle est
        # tracée sur la sortie du moteur, avant l'étage de niveaux).
        self._draw_hist()
        self._refresh_preview(hist=False)

    def _hist_survol(self, e):
        """Curseur « ⇔ » au survol d'une barre : elle est attrapable."""
        if self._hist_drag:
            return
        self.cv_hist.config(cursor=("sb_h_double_arrow"
                                    if self._hist_hit(e.x) else ""))


    def _draw_hist(self):
        """Trace l'histogramme (jalon 75) : deux bandes possibles —
        « Brut (linéaire) » (diagnostic : fond, piqué, clipping, dominante) et
        « Sortie du moteur » (l'image étirée AVANT les barres, que les trois
        barres Noir/Médian/Blanc découpent)."""
        self.cv_hist.delete("all")
        w, h = self._hist_taille()
        if getattr(self, "_hist_erreur", ""):
            self.cv_hist.create_text(w / 2.0, h / 2.0, fill="#d04040",
                                     text="histogramme indisponible : %s"
                                          % self._hist_erreur)
            return
        if self.hist_mode == "les_deux":
            haut = max(40, (h - 26) // 2 - 6)
            self._bande_brut(w, 2, 2 + haut)
            # Séparateur fin entre les deux bandes : sans lui, la queue basse de
            # la bande « brut » et les étiquettes des barres se lisent comme un
            # seul fouillis (constat sur une capture réelle de NGC 7331).
            yb = h - haut - 14
            self.cv_hist.create_line(0, yb - 3, w, yb - 3, fill="#3a3a3a")
            self._bande_sortie(w, yb, h - 14)
        elif self.hist_mode == "brut":
            self._bande_brut(w, 2, h - 16)
        else:
            self._bande_sortie(w, 2, h - 16)

    @staticmethod
    def _courbes_pts(chans, w, y0, y1, lineaire=False):
        """Points des polylignes R/V/B d'une bande, ÉCHELLE LOGARITHMIQUE en y
        par défaut (les queues d'un empilement sont invisibles en linéaire) et
        NORMALISATION COMMUNE : le maximum est pris sur les TROIS canaux.

        Fonction PURE (le tracé s'en sert, et le banc vérifie ainsi la
        propriété qui compte) : avant le jalon 75 chaque courbe était ramenée à
        SON propre maximum, donc trois canaux très inégaux se dessinaient à la
        même hauteur — l'histogramme ne disait plus rien de l'équilibre des
        couleurs, ce qui est justement l'usage qu'en fait Alain.

        `lineaire=True` (jalon 75, case « Échelle y linéaire », bande BASSE
        seulement) : la hauteur d'un bac est PROPORTIONNELLE À SON NOMBRE DE
        PIXELS — le rapport des hauteurs de deux bacs est alors exactement le
        rapport de leurs comptes (mesuré au banc : ×100 pour des comptes
        1000 / 10, là où le log le compresse à ×2,9). C'est ce qui fait
        apparaître le fond comme un PIC au lieu d'une colline (mesuré sur les
        frames d'Alain : 170 bacs à mi-hauteur → 27), au prix de la queue.
        """
        if not chans:
            return []
        mx = max(float(c.max()) for c in chans) or 1.0
        lg = max(1.0, float(np.log1p(mx)))
        polylignes = []
        for arr in chans:
            n = len(arr)
            pts = []
            for i in range(n):
                if lineaire:
                    haut = float(arr[i]) / mx          # proportion DIRECTE
                else:
                    haut = float(np.log1p(arr[i])) / lg
                pts += [i / float(n - 1) * w,
                        y1 - haut * (y1 - y0) - 1]
            polylignes.append(pts)
        return polylignes

    @staticmethod
    def _rangs_etiquettes(xs, largs):
        """Rang d'affichage de chaque étiquette (0, 1, 2…) : le PREMIER rang où
        elle ne chevauche aucune étiquette déjà posée dans ce rang.

        Les étiquettes serrées (trois barres au même endroit, ou trois repères
        du moteur dans les 5 % de l'axe) montent alors d'un rang au lieu de se
        superposer — leçon des jalons 72/74 : un texte qui en cache un autre
        est un défaut, et il ne se réveille qu'avec des valeurs groupées.
        """
        rangs, places = [], []
        for x, larg in zip(xs, largs):
            boite = (x - larg / 2.0, x + larg / 2.0)
            choisi = None
            for i, occupe in enumerate(rangs):
                if all(boite[1] < a or b < boite[0] for a, b in occupe):
                    choisi = i
                    break
            if choisi is None:
                rangs.append([])
                choisi = len(rangs) - 1
            rangs[choisi].append(boite)
            places.append(choisi)
        return places

    def _courbes(self, w, y0, y1, chans, lineaire=False):
        """Trace les courbes R/V/B d'une bande (cf. `_courbes_pts`)."""
        if not chans:
            # Message d'attente EN BAS À GAUCHE : le haut de la bande porte les
            # barres et leurs étiquettes, le bas à droite la légende — à cet
            # endroit il ne peut chevaucher ni l'une ni l'autre.
            self.cv_hist.create_text(4, y1 - 1, anchor="sw", fill="#777777",
                                     text="en attente de données")
            return
        couleurs = (["#ff5555", "#55ff55", "#5599ff"] if len(chans) == 3
                    else ["#bbbbbb"])
        for pts, col in zip(self._courbes_pts(chans, w, y0, y1, lineaire),
                            couleurs):
            self.cv_hist.create_line(*pts, fill=col, width=1)

    def _bande_brut(self, w, y0, y1):
        """Bande HAUTE : les données LINÉAIRES — c'est l'axe du « GRAND »
        histogramme de SharpCap (valeurs brutes + repères du niveau de
        l'étirement). Les repères ne sont dessinés qu'en STF et en auto :
        VeraLux n'a NI point noir NI point blanc (ancre + logD), et en mode
        manuel il n'y a plus d'auto à montrer — on n'invente pas un repère."""
        chans, hi = (self._hist_brut or (None, 0.0))
        # TOUJOURS en log, ici : la case « Échelle y linéaire » ne concerne que
        # la bande basse. Mesuré sur les frames d'Alain : cette bande, en
        # linéaire, ne laissait plus que 10 bacs visibles sur 256 (une
        # aiguille) — elle perdait son rôle de diagnostic (piqué, clipping,
        # dominante), d'où la décision du 28/09/2026.
        self._courbes(w, y0, y1, chans)
        self.cv_hist.create_text(4, y0 + 1, anchor="nw", fill="#999999",
                                 text="Brut (linéaire) — axe 0 à %.5f" % hi)
        d = self.disp
        # Sans données, aucun repère : un repère de niveau posé sur une bande
        # vide n'apprend rien et irait se superposer au message d'attente.
        if not chans or self.var_moteur.get() != "STF" or not d.auto or hi <= 0:
            return
        if not (d.last_hi > d.last_lo > 0):
            return
        milieu = d.last_lo + float(getattr(d, "last_m", 0.5)) \
            * (d.last_hi - d.last_lo)
        repere = [(val, lib, col) for val, lib, col
                  in ((d.last_lo, "Noir", "#bbbbbb"),
                      (milieu, "Médian", "#ffd75e"),
                      (d.last_hi, "Blanc", "#ffffff"))
                  if 0.0 < val < hi]
        # Étiquettes courtes (« Noir 46,5 % » — l'axe est dans la légende) et
        # posées sur des rangs distincts : sur une vraie image les trois repères
        # vivent dans la moitié gauche de l'axe et se chevaucheraient.
        textes = ["%s %.1f %%" % (lib, 100.0 * val / hi)
                  for val, lib, _c in repere]
        xs = [val / hi * w for val, _lib, _c in repere]
        rangs = self._rangs_etiquettes(xs, [7.0 * len(t) + 4.0
                                            for t in textes])
        for (val, _lib, col), x, txt, rang in zip(repere, xs, textes, rangs):
            self.cv_hist.create_line(x, y0 + 11, x, y1, fill=col, dash=(3, 3))
            anc = "n" if 60 < x < w - 60 else ("nw" if x <= 60 else "ne")
            self.cv_hist.create_text(min(max(x, 3), w - 3),
                                     y1 - 13 - self.HIST_RANG_PX * rang,
                                     anchor=anc, fill=col, text=txt)

    def _bande_sortie(self, w, y0, y1):
        """Bande BASSE : l'image telle que LE MOTEUR l'étire, AVANT les barres.
        Les repères intrinsèques (0 / 50 / 100 % — les valeurs d'origine des
        barres) sont en pointillé ; la COURBE JAUNE est le transfert des niveaux
        (ce que chaque valeur de sortie devient après les barres), la même que
        chez SharpCap."""
        chans = (self._hist_sortie or (None,))[0]
        # Échelle y de CETTE bande : log par défaut, linéaire si la case est
        # cochée (décision du 28/09/2026) — les barres, les repères et la
        # courbe jaune, eux, sont en x et ne bougent donc pas d'un pixel.
        self._courbes(w, y0, y1, chans, lineaire=self.hist_lineaire)
        d = self.disp
        for v in (0.0, 0.5, 1.0):
            x = self._hist_x(v, w)
            self.cv_hist.create_line(x, y0 + 8, x, y1, fill="#4a4a4a",
                                     dash=(2, 3))
        pts = []
        for i in range(0, 101):
            v = i / 100.0
            y = float(display_mod.niveaux(np.float32(v), d.bar_noir,
                                          d.bar_median, d.bar_blanc))
            pts += [self._hist_x(v, w), y1 - y * (y1 - y0) - 1]
        self.cv_hist.create_line(*pts, fill="#8a7a20", width=1)
        # Repère du PIC DU FOND : c'est LA question que se pose l'œil devant
        # cette bande (« où est le pic ? »). Il est MESURÉ sur la somme des
        # trois canaux (la donnée affichée, pas une valeur supposée) — et il
        # n'a pas de poignée : il n'est pas déplaçable.
        pic = None
        if chans:
            cum = np.sum(chans, axis=0)
            if float(cum.max()) > 0.0:
                pic = (float(np.argmax(cum)) + 0.5) / float(len(cum))
        # Les trois barres : ligne + poignée (attrapable) + valeur, PLUS le
        # repère du pic. Les étiquettes sont posées sur le premier RANG libre
        # (largeur estimée à ~7 px par caractère) : quatre textes serrés
        # tiennent alors sur quatre rangs au lieu de se superposer — un texte
        # qui en chevauche un autre est un DÉFAUT (leçon des jalons 72/74).
        pos = sorted((("noir", d.bar_noir), ("median", d.bar_median),
                      ("blanc", d.bar_blanc)), key=lambda p: p[1])
        marques = [(x, {"noir": "#ffffff", "median": "#ffd75e",
                        "blanc": "#ffffff"}[cle],
                    "%s %.1f %%" % ({"noir": "Noir", "median": "Médian",
                                     "blanc": "Blanc"}[cle], val * 100), True)
                   for cle, val in pos
                   for x in [self._hist_x(val, w)]]
        if pic is not None:
            marques.append((self._hist_x(pic, w), "#7fb2d8",
                            "fond %.1f %%" % (100.0 * pic), False))
        marques.sort(key=lambda m: m[0])
        rangs = self._rangs_etiquettes([m[0] for m in marques],
                                       [7.0 * len(m[2]) + 4.0 for m in marques])
        for (x, col, lib, poignee), rang in zip(marques, rangs):
            if poignee:
                self.cv_hist.create_line(x, y0 + 8, x, y1, fill=col, width=2)
                self.cv_hist.create_rectangle(x - 4, y0 + 1, x + 4, y0 + 8,
                                              fill=col, outline="#101010")
            else:
                self.cv_hist.create_line(x, y0 + 8, x, y1, fill=col, width=1,
                                         dash=(4, 3))
            anc = "n" if 46 < x < w - 46 else ("nw" if x <= 46 else "ne")
            self.cv_hist.create_text(min(max(x, 3), w - 3),
                                     y0 + 10 + self.HIST_RANG_PX * rang,
                                     anchor=anc, fill=col, text=lib)
        # NB (constat sur capture réelle) : plus de légende DANS la bande basse
        # — celle-ci se posait sur la queue du tracé ; le sélecteur au-dessus et
        # la ligne d'état disent déjà ce que chaque bande contient.
