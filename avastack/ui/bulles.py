# -*- coding: utf-8 -*-
"""Aides contextuelles de la colonne gauche — infobulles « ⓘ » (lot 3 / P4).

CONSTAT (Alain, 19/10/2026) : « la colonne de gauche est pleine de textes
d'aide gris, on ne voit plus les réglages ». Mesuré AVANT de coder
(`bancs/_mesure_p4_aides.py`, vraie interface construite, sections ouvertes) :
**13 étiquettes d'aide = 1 267 px, soit 84,5 lignes de texte et 23,5 % de la
colonne** — de quoi pousser les réglages sous le pli.

CONTENU :
  · `Bulle` — UNE seule fenêtre d'aide à la fois (`tk.Toplevel`
    `overrideredirect`), affichée après `DELAI_MS` (400 ms), placée sous le
    widget et RAMENÉE dans l'écran (jamais hors champ) ;
  · `astuce(widget, texte)` — liaison SOURIS **et** CLAVIER : survol,
    `FocusIn` (le ⓘ est atteignable au Tab), `Échap`, clic (bascule) et
    destruction du widget ;
  · `Aides` — mixin dont `App` hérite : helper `App._aide(parent, texte,
    ligne=…, padx=…, pady=…)` qui pose SOIT l'ancienne étiquette grise
    (option « Aides en texte dans la colonne », DÉFAUT NON), SOIT un « ⓘ »
    muni de sa bulle. Les deux widgets existent toujours : `_maj_aides()`
    bascule à chaud, sans reconstruire la fenêtre.

RÈGLES DE MISE EN PAGE (leçons du jalon 72, cf. CLAUDE.md) : le « ⓘ » est
posé AVANT tout texte libre de sa ligne (`side="right"`, aucune ligne ne
contient de widget `expand=True` à cet endroit) ; sinon il a SA PROPRE ligne,
courte — c'est ce qui rend la place (une ligne au lieu de 2 à 8).

Option de configuration : `aides_texte` (bool, défaut `False` = bulles).
"""
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from typing import Any

# --- Réglages de la bulle (spec P4 : 400 ms) -------------------------------
DELAI_MS = 400              # attente avant affichage (survol ou focus)
LARGEUR_MAX = 360           # largeur de repli du texte (px)
MARGE_ECRAN = 8             # marge minimale avec les bords de l'écran
ECART_SOUS = 4              # écart entre le widget et sa bulle

FOND = "#fffce8"            # jaune très clair (lisible sans agresser)
TEXTE = "#222222"
BORDURE = "#8a8a8a"
COULEUR_INFO = "#3b6ea5"    # bleu du « ⓘ » (visible sur fond de section)

# La bulle affichée : une seule à la fois, quel que soit le nombre d'aides.
_ACTIVE: "Bulle | None" = None


def _globals_app() -> Any:
    """Globals du module d'application `avastack.ui.app` — résolution TARDIVE.

    Même raison que `ui/widgets/collapsible.py` : les bancs remplacent
    `avastack.ui.app.CONFIG` / `.sauver_config` pour INTERCEPTER le vrai
    config.json. Lire ces globals au MOMENT DE L'APPEL préserve cette
    interception ; en production c'est le MÊME objet que
    `avastack.config.CONFIG`."""
    from . import app as _app               # import TARDIF (évite le cycle)
    return _app
class Bulle:
    """Fenêtre d'aide flottante attachée à un widget (cf. docstring module).

    Création PARESSEUSE : le `Toplevel` n'existe qu'au premier affichage (une
    colonne peut porter des dizaines d'aides sans payer une fenêtre chacune).
    Aucune exception ne remonte : une bulle est un CONFORT, jamais une panne
    (Tk sans gestionnaire de fenêtres, widget détruit en cours de route…)."""

    def __init__(self, proprietaire: tk.Misc, texte: str) -> None:
        self.proprietaire: tk.Misc = proprietaire
        self.texte: str = texte
        self._fenetre: tk.Toplevel | None = None
        self._job: str | None = None
        self._visible: bool = False

    # --- Construction / placement ------------------------------------------
    def _creer(self) -> tk.Toplevel | None:
        try:
            fen = tk.Toplevel(self.proprietaire)
            fen.withdraw()
            fen.overrideredirect(True)
            try:
                fen.attributes("-topmost", True)
            except tk.TclError:          # certains gestionnaires l'ignorent
                pass
            cadre = tk.Frame(fen, bg=BORDURE, bd=0)
            cadre.pack(fill="both", expand=True)
            tk.Label(cadre, text=self.texte, justify="left", anchor="w",
                     bg=FOND, fg=TEXTE, wraplength=LARGEUR_MAX,
                     padx=8, pady=6, bd=0).pack(fill="both", expand=True,
                                                 padx=1, pady=1)
            return fen
        except tk.TclError:
            return None

    def _placer(self) -> None:
        fen = self._fenetre
        if fen is None:
            return
        try:
            fen.update_idletasks()
            largeur = max(1, fen.winfo_reqwidth())
            hauteur = max(1, fen.winfo_reqheight())
            x = self.proprietaire.winfo_rootx()
            bas = (self.proprietaire.winfo_rooty()
                   + self.proprietaire.winfo_height())
            y = bas + ECART_SOUS
            ecran_l = self.proprietaire.winfo_screenwidth()
            ecran_h = self.proprietaire.winfo_screenheight()
            # Jamais hors champ : on ramène la bulle dans l'écran (à gauche si
            # elle déborderait à droite, au-dessus si elle déborderait en bas).
            x = max(MARGE_ECRAN, min(x, ecran_l - largeur - MARGE_ECRAN))
            if y + hauteur + MARGE_ECRAN > ecran_h:
                y = max(MARGE_ECRAN,
                        self.proprietaire.winfo_rooty() - hauteur - ECART_SOUS)
            fen.wm_geometry("+%d+%d" % (x, y))
        except tk.TclError:
            pass

    # --- Affichage ---------------------------------------------------------
    def montrer(self) -> None:
        """Affiche la bulle (et cache la précédente : une seule à la fois)."""
        global _ACTIVE
        self._annuler()
        if _ACTIVE is not None and _ACTIVE is not self:
            _ACTIVE.cacher()
        if self._fenetre is None or not self._fenetre.winfo_exists():
            self._fenetre = self._creer()
        fen = self._fenetre
        if fen is None:
            return
        self._placer()
        try:
            fen.deiconify()
            fen.lift()
        except tk.TclError:
            self._fenetre = None
            return
        self._visible = True
        _ACTIVE = self

    def cacher(self) -> None:
        global _ACTIVE
        self._annuler()
        self._visible = False
        if self._fenetre is not None:
            try:
                self._fenetre.withdraw()
            except tk.TclError:
                pass
        if _ACTIVE is self:
            _ACTIVE = None

    def detruire(self) -> None:
        """Détruit la fenêtre (fermeture de l'application ou du widget)."""
        global _ACTIVE
        self.cacher()
        if self._fenetre is not None:
            try:
                self._fenetre.destroy()
            except tk.TclError:
                pass
            self._fenetre = None

    def visible(self) -> bool:
        return self._visible

    def _annuler(self) -> None:
        """Annule l'affichage DIFFÉRÉ en cours (sans toucher à la fenêtre)."""
        if self._job is None:
            return
        try:
            self.proprietaire.after_cancel(self._job)
        except tk.TclError:
            pass
        self._job = None



def astuce(widget: tk.Misc, texte: str, delai: int = DELAI_MS) -> Bulle:
    """Attache `texte` en infobulle à `widget` — SOURIS et CLAVIER.

    Souris : survol (`<Enter>`) → affichage après `delai` ; sortie → fermeture ;
    clic → bascule (utile sur le « ⓘ »).
    Clavier : `FocusIn` (le widget doit être `takefocus=True`) → même délai ;
    `FocusOut` et `Échap` → fermeture. La destruction du widget détruit la
    bulle : aucune fenêtre orpheline après la fermeture de l'application."""
    bulle = Bulle(widget, texte)

    def armer(_e: Any = None) -> None:
        bulle.cacher()                    # annule un éventuel affichage en cours
        try:
            bulle._job = widget.after(delai, bulle.montrer)
        except tk.TclError:
            bulle._job = None

    def desarmer(_e: Any = None) -> None:
        bulle.cacher()

    def basculer(_e: Any = None) -> None:
        if bulle.visible():
            bulle.cacher()
        else:
            bulle.montrer()

    def sur_destroy(evenement: Any) -> None:
        if evenement.widget is widget:
            bulle.detruire()

    for suite, rappel in (("<Enter>", armer), ("<Leave>", desarmer),
                          ("<FocusIn>", armer), ("<FocusOut>", desarmer),
                          ("<ButtonPress-1>", basculer), ("<Escape>", desarmer)):
        widget.bind(suite, rappel, add="+")
    widget.bind("<Destroy>", sur_destroy, add="+")
    return bulle


@dataclass
class _EntreeAide:
    """Une aide : son étiquette de texte ET son « ⓘ » (jamais les deux actifs)."""
    texte: ttk.Label
    info: ttk.Label
    parent: tk.Misc
    ligne: tk.Misc | None
    padx: int
    pady: Any



class Aides:
    """Mixin : aides contextuelles de la colonne (cf. docstring du module).

    `App` en hérite : `App._aide(...)` est le SEUL point de création d'une aide,
    ce qui garantit que l'option de configuration bascule TOUTES les aides
    d'un coup (`_maj_aides`)."""

    # Interface attendue sur l'hôte (`App`) — DÉCLARATIONS seulement.
    var_aides_texte: tk.Variable
    _aides: list[_EntreeAide]
    _aides_mode_texte: bool

    # --- Création d'une aide -------------------------------------------------
    def _aide(self, parent: tk.Misc, texte: str, *,
              ligne: tk.Misc | None = None,
              padx: int = 0, pady: Any = 0) -> ttk.Label:
        """Pose une aide et rend son « ⓘ ».

        · `parent` : cadre où vit l'aide (l'étiquette de texte y est posée) ;
        · `ligne` : ligne du RÉGLAGE concerné. Fournie, le « ⓘ » s'y place à
          droite (`side="right"`) et NE COÛTE AUCUNE LIGNE — la ligne ne doit
          contenir aucun widget `expand=True` (règle du jalon 72) ;
        · sans `ligne`, le « ⓘ » a sa propre ligne, courte : 1 ligne au lieu
          des 2 à 8 que prenait le texte ;
        · `padx`/`pady` : mêmes marges que l'ancienne étiquette (rendu
          identique quand l'option « Aides en texte » est active)."""
        if not hasattr(self, "_aides"):
            self._aides = []
        if not hasattr(self, "_aides_mode_texte"):
            self._aides_mode_texte = bool(
                _globals_app().CONFIG.get("aides_texte", False))
        etiquette = ttk.Label(parent, text=texte, foreground="#888888",
                              wraplength=310, justify="left")
        info = ttk.Label(parent if ligne is None else ligne, text="ⓘ",
                         foreground=COULEUR_INFO, cursor="hand2",
                         takefocus=True)
        astuce(info, texte)
        entree = _EntreeAide(etiquette, info, parent, ligne, padx, pady)
        self._aides.append(entree)
        self._placer_aide(entree)
        return info

    def _placer_aide(self, entree: _EntreeAide) -> None:
        """Pose l'aide dans le mode courant (texte gris ou « ⓘ »)."""
        entree.texte.pack_forget()
        entree.info.pack_forget()
        if self._aides_mode_texte:
            entree.texte.pack(anchor="w", padx=entree.padx, pady=entree.pady)
        elif entree.ligne is not None:
            entree.info.pack(side="right", padx=(4, 0))
        else:
            entree.info.pack(anchor="w", padx=(6, 0), pady=0)

    # --- Option « Aides en texte dans la colonne » ---------------------------
    def _on_aides_texte(self) -> None:
        """Case de l'option : bascule À CHAUD et persiste le choix."""
        _app = _globals_app()
        mode_texte = bool(self.var_aides_texte.get())
        _app.CONFIG["aides_texte"] = mode_texte
        _app.sauver_config(_app.CONFIG)
        self._aides_mode_texte = mode_texte
        self._maj_aides()

    def _maj_aides(self) -> None:
        """Réapplique le mode à TOUTES les aides déjà posées."""
        for entree in getattr(self, "_aides", []):
            self._placer_aide(entree)
        # La colonne change de hauteur : le canvas doit recalculer sa zone
        # défilante tout de suite (sinon la barre garde l'ancienne).
        racine = getattr(self, "root", None)
        if racine is not None:
            try:
                racine.update_idletasks()
            except tk.TclError:
                pass

