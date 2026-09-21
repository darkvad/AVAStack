# -*- coding: utf-8 -*-
"""Compositions multi-filtres (jalon 19) : RGB, HOO, SHO, LRGB, Mono.

Rôles et mapping
----------------
Chaque dossier surveillé est étiqueté d'un RÔLE (le filtre utilisé) :
L, R, G, B, Ha, O3, S2. Une COMPOSITION déclare les rôles attendus et
comment ils alimentent les canaux R/G/B du composite :

  Mono  (1 dossier)  → composite monochrome (le rôle L)
  HOO   (2 dossiers) → R=Ha, G=O3, B=O3
  SHO   (3 dossiers) → R=S2, G=Ha, B=O3 (palette Hubble)
  RGB   (3 dossiers) → R=R, G=G, B=B
  LRGB  (4 dossiers) → R=R, G=G, B=B + luminance L (rôle OPTIONNEL)

Chaîne de traitement (décisions du 18/09/2026, cf. AVANCEMENT.md) :
  normalisation LINÉAIRE par canal (ici, percentiles + gains manuels)
  → composite LINÉAIRE → étirement global existant (STF ou VeraLux),
  qui ne change PAS : le composite a la même forme (H, W, 3) float32
  linéaire que l'empilement couleur actuel.

Extraction depuis une brute COULEUR (CFA débayerisée) : le signal d'un
filtre étroit se concentre dans des canaux précis (Ha→R, OIII→G+B,
SII→R) — cf. CANAUX_CFA. Une brute MONO (2D) est prise telle quelle :
c'est déjà le canal du rôle.

LRGB et radio « Canal L » (choix d'Alain) : si le dossier L est VIDE,
la radio décide entre « L synthétisé » (L = luminance du composite,
combine identité — prêt pour un futur traitement spécifique du canal L)
et « dégradé en RGB » (composite RGB pur). Si L contient des frames,
il est utilisé quoi qu'il arrive.
"""

import numpy as np

# Réutilisation SANS modification du socle d'empilement (jalon 15) : la
# façade multi-rôles tient la MÊME géométrie d'intersection (les helpers
# privés _aire_signee/_clip_poly restent dans stacking.py, source unique).
from .stacking import (LiveStacker, _aire_signee, _clip_poly,
                       cadre_intersection, quad_alignement,
                       aligner_canaux)

# Rôles possibles d'un dossier (un rôle = un filtre).
ROLES = ("L", "R", "G", "B", "Ha", "O3", "S2")

# Canal(x) d'une brute COULEUR (H, W, 3) à extraire pour chaque rôle.
# "luma" = luminance pondérée ; un tuple = moyenne des canaux listés.
_POIDS_LUMA = (0.299, 0.587, 0.114)          # R, G, B (cf. sharpness.py)
CANAUX_CFA = {
    "L": "luma",                             # luminance d'une brute couleur
    "R": (0,), "Ha": (0,), "S2": (0,),       # signal dans le rouge
    "G": (1,),
    "B": (2,),
    "O3": (1, 2),                            # OIII : vert + bleu
}

# Compositions : rôles attendus (ordre = ordre de saisie dans l'UI),
# rôles optionnels, mapping vers les canaux du composite.
COMPOSITIONS = {
    "Mono": {"roles": ("L",), "optionnels": ()},
    "HOO":  {"roles": ("Ha", "O3"), "optionnels": (),
             "canaux_rgb": {"R": ("Ha",), "G": ("O3",), "B": ("O3",)}},
    "SHO":  {"roles": ("S2", "Ha", "O3"), "optionnels": (),
             "canaux_rgb": {"R": ("S2",), "G": ("Ha",), "B": ("O3",)}},
    "RGB":  {"roles": ("R", "G", "B"), "optionnels": (),
             "canaux_rgb": {"R": ("R",), "G": ("G",), "B": ("B",)}},
    "LRGB": {"roles": ("L", "R", "G", "B"), "optionnels": ("L",),
             "canaux_rgb": {"R": ("R",), "G": ("G",), "B": ("B",)},
             "luminance": ("L",)},
}

MODES_L = ("synthetise", "degrade")          # radio « Canal L » (L vide)


def roles_de(composition):
    """Rôles attendus d'une composition (dans l'ordre de saisie UI)."""
    return COMPOSITIONS[composition]["roles"]


def roles_optionnels(composition):
    """Rôles qui peuvent rester vides sans bloquer la composition."""
    return COMPOSITIONS[composition]["optionnels"]

# Alias usuels du mot-clé FITS FILTER (jalon 19) : N.I.N.A., APT, SGP, ASI
# Air et les roues à filtres écrivent des graphies différentes du même
# filtre. Clés NORMALISÉES (majuscules, séparateurs supprimés à la lecture).
FILTRES_USUELS = {
    "HA": "Ha", "HALPHA": "Ha", "H": "Ha",
    "OIII": "O3", "O3": "O3", "O": "O3",
    "SII": "S2", "S2": "S2", "S": "S2",
    "RED": "R", "R": "R",
    "GREEN": "G", "G": "G",
    "BLUE": "B", "B": "B",
    "LUM": "L", "LUMINANCE": "L", "L": "L", "CLEAR": "L", "CL": "L",
    "IR": "L", "IRCUT": "L", "NONE": "L",
}


def role_de_filtre(filtre):
    """Rôle (ROLES) correspondant à la valeur du mot-clé FITS FILTER
    (« Ha », « H-alpha », « OIII », « Red », « L »…), ou None si non reconnu
    (le dossier garde alors son rôle déclaré à la main)."""
    if filtre is None:
        return None
    cle = str(filtre).strip().upper()
    for sep in (" ", "-", "_", ".", "/"):
        cle = cle.replace(sep, "")
    return FILTRES_USUELS.get(cle)




# ------------------------------------------------------------ extraction ---
def extraire_canal(img, role):
    """Carte 2D float32 du rôle depuis une brute/empilement du dossier :
    mono (H, W) → telle quelle ; couleur (H, W, 3) → canal(x) du rôle
    (CANAUX_CFA : moyenne si plusieurs, luma pondérée pour L).
    Rôle inconnu → luminance (comportement sûr par défaut)."""
    a = np.asarray(img, dtype=np.float32)
    if a.ndim == 2:
        return a
    if a.ndim != 3 or a.shape[-1] != 3:
        raise ValueError(f"Forme d'image non gérée pour le rôle "
                         f"{role!r} : {a.shape}")
    c = CANAUX_CFA.get(role, "luma")
    if c == "luma":
        return (_POIDS_LUMA[0] * a[..., 0] + _POIDS_LUMA[1] * a[..., 1]
                + _POIDS_LUMA[2] * a[..., 2]).astype(np.float32)
    return a[..., list(c)].mean(axis=-1).astype(np.float32)


# ------------------------------------------------------- normalisation ----
def _echantillon(img, cible=512 * 512):
    """Sous-échantillonnage régulier (~`cible` pixels) : les percentiles
    restent représentatifs à coût constant, même en 16 Mpx."""
    pas = max(1, int(round(np.sqrt(img.size / float(cible)))))
    return img[::pas, ::pas]


def bornes_normalisation(img, lo_pct=0.25, hi_pct=99.7):
    """Bornes (lo, hi) robustes d'un canal (percentiles bas/haut).
    Public : permet à l'app de les FIGER (composite stable entre deux
    frames) avant d'appeler composer()."""
    s = _echantillon(np.asarray(img, dtype=np.float32))
    lo = float(np.percentile(s, lo_pct))
    hi = float(np.percentile(s, hi_pct))
    if hi - lo < 1e-9:
        hi = lo + 1e-9                        # canal plat → éviter /0
    return lo, hi


def normaliser(img, lo=None, hi=None, lo_pct=0.25, hi_pct=99.7):
    """Normalisation LINÉAIRE [lo..hi] → 0..1, SANS clip : les étoiles
    brillantes restent > 1 (l'empilement reste linéaire, convention du
    projet). bornes figées = composite stable entre deux frames."""
    a = np.asarray(img, dtype=np.float32)
    if lo is None or hi is None:
        lo, hi = bornes_normalisation(a, lo_pct, hi_pct)
    return ((a - lo) / (hi - lo)).astype(np.float32)


# ------------------------------------------------------------- composer ---
def _channel_de(norm, roles, forme):
    """Moyenne des rôles normalisés alimentant un canal ; absent → zéros
    (canal neutre, la composition ne plante jamais sur un dossier vide)."""
    dispo = [norm[r] for r in roles if norm.get(r) is not None]
    if not dispo:
        return np.zeros(forme, np.float32)
    return np.mean(dispo, axis=0).astype(np.float32)


def _luma(rgb):
    """Luminance pondérée d'un composite (H, W, 3)."""
    return (_POIDS_LUMA[0] * rgb[..., 0] + _POIDS_LUMA[1] * rgb[..., 1]
            + _POIDS_LUMA[2] * rgb[..., 2]).astype(np.float32)


def composer(canaux, composition, gains=None, bornes=None,
             normaliser_canal=True, mode_l="synthetise",
             lo_pct=0.25, hi_pct=99.7):
    """Composite linéaire d'une composition.

    canaux   : dict rôle → carte 2D float32 (empilement du rôle), ou None
               pour un rôle sans aucune frame.
    gains    : dict 'R'/'G'/'B' → facteur multiplicatif (défaut 1.0).
    bornes   : dict rôle → (lo, hi) pour FIGER la normalisation par rôle
               (sinon recalculée à chaque appel — attention, la borne
               bouge légèrement à chaque nouvelle frame).
    normaliser_canal : False → les canaux sont déjà normalisés (les gains
               et le combine L restent appliqués).
    mode_l   : "synthetise" | "degrade" — sortie de la radio « Canal L »,
               utilisée SEULEMENT si le rôle L est vide.

    → (H, W, 3) float32 linéaire, (H, W) pour Mono, ou None si AUCUN rôle
    n'a de données. ValueError si les formes des rôles diffèrent (l'app
    doit recadrer sur le cadre commun AVANT d'appeler)."""
    if composition not in COMPOSITIONS:
        raise ValueError(f"Composition inconnue : {composition!r}")
    if mode_l not in MODES_L:
        mode_l = "synthetise"
    spec = COMPOSITIONS[composition]
    bornes = bornes or {}

    # 1) normalisation par rôle (rôle vide → ignoré, jamais bloquant)
    norm = {}
    for role in spec["roles"]:
        img = canaux.get(role)
        if img is None:
            continue
        a = np.asarray(img, dtype=np.float32)
        if a.size == 0:
            continue
        if normaliser_canal:
            lo, hi = bornes.get(role) or (None, None)
            a = normaliser(a, lo, hi, lo_pct, hi_pct)
        norm[role] = a

    if not norm:
        return None                            # aucune donnée du tout

    # 2) Mono : composite monochrome direct
    if "canaux_rgb" not in spec:
        return norm[spec["roles"][0]]

    forme = norm[next(iter(norm))].shape
    for r, a in norm.items():
        if a.shape != forme:
            raise ValueError(
                f"Formes hétérogènes entre les rôles ({r} : {a.shape} vs "
                f"{forme}) — recadrer sur le cadre commun avant composer()")

    # 3) canaux R/G/B du composite (gains APRÈS normalisation)
    gains = gains or {}
    rgb = []
    for canal in ("R", "G", "B"):
        c = _channel_de(norm, spec["canaux_rgb"][canal], forme)
        g = float(gains.get(canal, 1.0))
        rgb.append(c if g == 1.0 else (c * g).astype(np.float32))
    rgb = np.stack(rgb, axis=-1)

    # 4) LRGB : combine luminance — L du dossier s'il a des frames, sinon
    #    la radio décide (« synthétisé » = luminance du composite, combine
    #    identité aujourd'hui, prêt pour un traitement spécifique de L)
    if "luminance" in spec:
        L = norm.get(spec["luminance"][0])
        if L is None and mode_l == "synthetise":
            L = _luma(rgb)
        if L is not None:
            lum = _luma(rgb)
            ratio = np.where(lum > 1e-6,
                             L / np.maximum(lum, 1e-6),
                             1.0).astype(np.float32)
            rgb = (rgb * ratio[..., None]).astype(np.float32)

    return rgb


# ------------------------------------------------------ façade worker -----
def composition_pour_roles(roles):
    """Composition correspondant à un ensemble de rôles (jalon 19, phase 2 :
    SANS choix UI encore, le worker la déduit des dossiers configurés).
    Correspondance EXACTE d'abord ; sinon la première composition dont les
    rôles englobent ceux fournis (ordre HOO, SHO, RGB, LRGB) — ex.
    (« Ha »,) → HOO (O3 restera vide, canal neutre). → nom, ou None si vide."""
    roles = tuple(roles)
    if not roles:
        return None
    for nom in COMPOSITIONS:
        if COMPOSITIONS[nom]["roles"] == roles:
            return nom
    ens = set(roles)
    for nom in ("HOO", "SHO", "RGB", "LRGB"):
        if ens <= set(COMPOSITIONS[nom]["roles"]):
            return nom
    return None


class CompositeStacker:
    """Façade multi-rôles (jalon 19, phase 2) : UN LiveStacker par rôle.

    Imite l'interface de LiveStacker telle que le worker l'utilise
    (add / mean / n / cadre / note_alignement / k / set_rejet / wb_auto /
    wb_force / reset) — ainsi TOUT le code existant du worker (aperçu,
    sauvegardes, traitement externe) fonctionne sans le savoir : mean()
    renvoie le COMPOSITE linéaire.

    Décisions tranchées (AVANCEMENT.md, 18/09/2026) :
    - les stackers de rôle accumulent des CANAUX 2D (extraire_canal) dans le
      repère des frames alignées — l'aligneur est PARTAGÉ (référence unique),
      donc tous les rôles partagent le MÊME repère ;
    - l'intersection des zones couvertes est tenue GLOBALEMENT (un seul
      polygone, tous rôles confondus) : c'est le CADRE COMMUN appliqué avant
      composer() — les stackers de rôle n'ont pas à se recadrer entre eux ;
    - mean(recadre=False) renvoie le composite SANS recadrage (même repère
      que les frames) : utilisable comme référence d'alignement, exactement
      comme LiveStacker.mean(recadre=False) en mono (jalon 13).
    """

    def __init__(self, composition, k=3.0, warmup=5, method="kappa",
                 window=8):
        if composition not in COMPOSITIONS:
            raise ValueError(f"Composition inconnue : {composition!r}")
        self.composition = composition
        self._k = k
        self.warmup = warmup
        self._method = method if method in LiveStacker.METHODES else "kappa"
        self._window = max(3, int(window))
        self._wb_auto = False
        self._wb_force = 1.0
        self.gains = None                 # gains R/G/B (UI, phase 3)
        self.mode_l = "synthetise"        # radio « Canal L » (UI, phase 3)
        # Recalage colorimétrique « Linear Fit » (jalon 54) : appliqué au
        # COMPOSITE SEUL — JAMAIS aux couches (le solveur live re-fait la
        # recomposition depuis les couches brutes et ré-applique le recalage
        # lui-même, réglage transporté dans disp.vl_compo). Mode « offset »
        # PAR DÉFAUT (retour du test réel d'Alain : le gain fondé sur le
        # rapport des bruits amplifie halos/bruit bleus d'une image OSC).
        self.linear_fit = False
        self.linear_fit_mode = "offset"
        self.fit_diag = None              # gains/offsets mesurés (UI)
        self._fit_cache = None
        self.role_courant = None          # rôle de la frame en cours d'ajout
        self.stackers = {}                # rôle → LiveStacker (canaux 2D)
        self._shape = None                # forme des canaux (posée au 1er add)
        self._poly = None                 # intersection GLOBALE des couvertures
        self.cadre = None                 # cadre commun (y0, x0, y1, x1)

    # -- attributs répercutés sur tous les stackers (existants ET futurs) ---
    @property
    def k(self):
        return self._k

    @k.setter
    def k(self, v):
        self._k = v
        for s in self.stackers.values():
            s.k = v

    @property
    def wb_auto(self):
        return self._wb_auto

    @wb_auto.setter
    def wb_auto(self, v):
        self._wb_auto = bool(v)
        for s in self.stackers.values():
            s.wb_auto = self._wb_auto

    @property
    def wb_force(self):
        return self._wb_force

    @wb_force.setter
    def wb_force(self, v):
        self._wb_force = float(v)
        for s in self.stackers.values():
            s.wb_force = self._wb_force

    @property
    def method(self):
        return self._method

    @property
    def window(self):
        return self._window

    def set_rejet(self, method=None, window=None):
        """Change la méthode / fenêtre de rejet à chaud, sur tous les rôles
        (accumulations préservées — cf. LiveStacker.set_rejet)."""
        if method is not None and method in LiveStacker.METHODES:
            self._method = method
        if window is not None:
            self._window = max(3, int(window))
        for s in self.stackers.values():
            s.set_rejet(method=method, window=window)

    # -- compteurs (somme sur les rôles) ------------------------------------
    @property
    def shape(self):
        return self._shape

    @property
    def n(self):
        return sum(s.n for s in self.stackers.values())

    @property
    def rejected_total(self):
        return sum(s.rejected_total for s in self.stackers.values())

    # -- accumulation --------------------------------------------------------
    def _stacker_de(self, role):
        s = self.stackers.get(role)
        if s is None:                     # 1re frame de ce rôle
            s = LiveStacker(self._shape, k=self._k, warmup=self.warmup,
                            method=self._method, window=self._window)
            s.wb_auto = self._wb_auto
            s.wb_force = self._wb_force
            self.stackers[role] = s
        return s

    def add(self, frame, role=None):
        """Empile `frame` (canal 2D du rôle) dans le stacker de son rôle.
        Le rôle vient de l'argument ou de `role_courant` (posé par le worker)."""
        role = role or self.role_courant
        if not role:
            raise ValueError("CompositeStacker.add : rôle inconnu (ni "
                             "argument ni role_courant)")
        if self._shape is None:
            self._shape = tuple(frame.shape)
        self._stacker_de(role).add(frame)

    def note_alignement(self, M):
        """Intersection GLOBALE des zones couvertes (tous rôles confondus —
        même repère, aligneur partagé) : le cadre commun appliqué à CHAQUE
        moyenne de rôle avant composer(), garantissant des formes identiques.
        Même géométrie que LiveStacker.note_alignement (jalon 15)."""
        if M is None or self._shape is None:
            return
        q = quad_alignement(M, self._shape)
        if _aire_signee(q) < 0:           # orientation normalisée
            q = q[::-1].copy()
        if self._poly is None:            # le cadre cible est la borne absolue
            self._poly = quad_alignement(
                np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]), self._shape)
        p = _clip_poly(self._poly, q)
        if p is not None:                 # vide = M aberrante → on ignore
            self._poly = p
        self.cadre = cadre_intersection(self._poly)

    def reset(self):
        """Vide TOUT (tous rôles + cadre commun)."""
        self.stackers.clear()
        self._poly = None
        self.cadre = None
        self._shape = None
        self._fit_cache = None            # recalage Linear Fit (jalon 54)
        self.fit_diag = None

    # -- lecture du composite -------------------------------------------------
    def _recadrer(self, img):
        if self.cadre is None:
            return img
        y0, x0, y1, x1 = self.cadre
        return img[y0:y1, x0:x1]

    def moyennes(self, recadre=True):
        """{rôle: carte 2D float32 de l'empilement du rôle} — recadrées au
        cadre COMMUN si `recadre` (formes identiques, exigence de composer()).
        Matière de l'état par canal et des futures sauvegardes par canal."""
        out = {}
        for role, s in self.stackers.items():
            if s.n == 0:
                continue
            m = s.mean(recadre=False)     # accumulation complète, même repère
            out[role] = self._recadrer(m) if recadre else m
        return out

    def mean_avec_canaux(self, recadre=True):
        """(composite, {rôle: carte 2D}) en UNE passe de moyennes (jalon 24) :
        le worker a besoin des DEUX à chaque nouvel empilement (composite pour
        l'affichage, couches pour le traitement par couche du solveur live) —
        une seule exécution de mean()/recadrage au lieu de deux.
        Jalon 54 : le recalage « Linear Fit » est appliqué au COMPOSITE SEUL
        (les couches restent brutes — elles alimentent les caches du solveur
        et sa recomposition, qui ré-applique le recalage lui-même).
        → (composite ou None, dict — vide si aucun rôle n'a de frame)."""
        canaux = self.moyennes(recadre=recadre)
        if not canaux:
            return None, None
        try:
            comp = composer(canaux, self.composition, gains=self.gains,
                            mode_l=self.mode_l)
        except ValueError:
            comp = None                   # formes hétérogènes (ne doit pas
        if comp is not None and self.linear_fit:   # arriver : cadre commun
            comp = self._recaler_fit(comp)         # → case DÉCOCHÉE = brut
        return comp, canaux

    def _recaler_fit(self, comp):
        """Recalage « Linear Fit » du composite (jalon 54) : cf.
        CompositeStacker.linear_fit. Cache par (frames totales, gains, mode L,
        mode) : les stats du composite dépendent de l'accumulation ET des
        réglages qui la composent → recalcul seulement quand l'un change
        (aucun pompage entre deux ticks). Dégénéré (canal plat, cf.
        aligner_canaux) → composite inchangé + diag None."""
        if comp.ndim != 3 or comp.shape[-1] != 3:
            return comp
        gains_sig = (tuple(round(float(self.gains.get(c, 1.0)), 4)
                           for c in ("R", "G", "B"))
                     if self.gains else None)
        cle = (sum(s.n for s in self.stackers.values()),
               self.linear_fit_mode, gains_sig, self.mode_l)
        if self._fit_cache is not None and self._fit_cache[0] == cle:
            out, diag = self._fit_cache[1]
        else:
            out, diag = aligner_canaux(comp, mode=self.linear_fit_mode)
            self._fit_cache = (cle, (out, diag))
        self.fit_diag = diag
        return out if diag is not None else comp

    def mean(self, recadre=True):
        """Composite LINÉAIRE courant (composer : normalisation par canal +
        gains + LRGB), recadré au cadre commun si `recadre`. → (H, W, 3)
        float32 (ou (H, W) en Mono), None si aucun rôle n'a de frame."""
        comp, _ = self.mean_avec_canaux(recadre=recadre)
        return comp

    def etat(self):
        """État par canal « Ha: 12 · O3: 9 » (frames EMPILÉES par rôle, dans
        l'ordre de la composition ; rôles vides absents)."""
        ordre = list(roles_de(self.composition))
        parties = []
        for role in ordre + [r for r in self.stackers if r not in ordre]:
            s = self.stackers.get(role)
            if s is not None and s.n > 0:
                parties.append(f"{role}: {s.n}")
        return " · ".join(parties)

