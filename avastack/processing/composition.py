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

Chaîne de traitement (décisions des 18 et 24/09/2026, cf. AVANCEMENT.md) :
  normalisation LINÉAIRE par canal (percentiles) → composite LINÉAIRE BRUT
  (c'est l'empilement enregistré par la sauvegarde linéaire) → CORRECTIONS
  DE COULEUR de la chaîne de sortie (gains SPCC/Gaia/manuels, équilibrage,
  recalage colorimétrique) → étirement global existant (STF ou VeraLux), qui
  ne change PAS : le composite a la même forme (H, W, 3) float32 linéaire que
  l'empilement couleur actuel. AUCUNE correction de couleur dans `composer()`
  (règle d'Alain, 24/09/2026) : sinon le fichier linéaire ne serait ni brut
  ni fini.

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
                       aligner_canaux, gains_equilibre)

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


def composer(canaux, composition, bornes=None,
             normaliser_canal=True, mode_l="synthetise",
             lo_pct=0.25, hi_pct=99.7):
    """Composite linéaire d'une composition.

    canaux   : dict rôle → carte 2D float32 (empilement du rôle), ou None
               pour un rôle sans aucune frame.
    bornes   : dict rôle → (lo, hi) pour FIGER la normalisation par rôle
               (sinon recalculée à chaque appel — attention, la borne
               bouge légèrement à chaque nouvelle frame).
    normaliser_canal : False → les canaux sont déjà normalisés (le combine
               L reste appliqué).
    mode_l   : "synthetise" | "degrade" — sortie de la radio « Canal L »,
               utilisée SEULEMENT si le rôle L est vide.

    → (H, W, 3) float32 linéaire, (H, W) pour Mono, ou None si AUCUN rôle
    n'a de données. ValueError si les formes des rôles diffèrent (l'app
    doit recadrer sur le cadre commun AVANT d'appeler).

    AUCUNE correction de couleur n'est appliquée ici (décision d'Alain,
    24/09/2026) : les gains SPCC/Gaia/manuels, l'équilibrage des canaux et
    le recalage colorimétrique appartiennent à la CHAÎNE DE SORTIE, en aval
    (`corrections_couleur` / `CompositeStacker.mean(corrections=True)`).
    Conséquence directe : `composer()` seul produit l'EMPILEMENT BRUT — la
    référence linéaire sauvegardée."""
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

    # 3) canaux R/G/B du composite (SANS gain : les corrections de couleur
    #    sont appliquées APRÈS la composition, dans la chaîne de sortie)
    rgb = [_channel_de(norm, spec["canaux_rgb"][canal], forme)
           for canal in ("R", "G", "B")]
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


# ------------------------------------------- corrections de couleur (sortie) ---
# DÉCISION D'ALAIN (24/09/2026, cf. CLAUDE.md § Sauvegardes) : la sauvegarde
# linéaire est BRUTE — ni gradient retiré, ni correction de couleur. Les
# corrections de couleur (SPCC, gains photométriques Gaia, gains manuels de
# l'UI, équilibrage des canaux, recalage colorimétrique « Linear Fit ») vivent
# dans la CHAÎNE DE SORTIE : affichage, solveur live, sortie « traitée ». Elles
# sont donc appliquées APRÈS `composer()` (donc après la normalisation par
# rôle, qui n'absorbe plus rien) et JAMAIS dans le fichier brut.
#
# Ordre validé par Alain (décision (c)) : ... → débruitage → CORRECTIONS
# (gains + équilibrage + recalage) → netteté/chaîne couleur → étirement.

def appliquer_gains_canaux(img, gains, force=1.0):
    """Multiplie chaque canal d'un composite par un gain par CANAL
    (séquence de 3, ordre R/G/B). `force` < 1 atténue la correction
    (`gains ** force`, comme l'équilibrage à force partielle). → COPIE ;
    image inchangée si elle n'est pas un composite couleur ou sans gains."""
    if img is None or gains is None:
        return img
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return img
    g = np.asarray(gains, dtype=np.float32)
    if g.shape != (3,):
        return img
    if force < 1.0:
        g = g ** float(force)
    if bool(np.allclose(g, 1.0)):
        return img
    return (a * g.reshape(1, 1, 3)).astype(np.float32)


def appliquer_gains(img, gains):
    """Applique des gains R/G/B (dict 'R'/'G'/'B' → facteur) à un composite
    (H, W, 3). → COPIE (ou l'image telle quelle si rien à faire) ; no-op sur
    une image qui n'est pas un composite couleur."""
    if img is None or not gains:
        return img
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return img
    g = [float(gains.get(c, 1.0)) for c in ("R", "G", "B")]
    if abs(g[0] - 1.0) < 1e-9 and abs(g[1] - 1.0) < 1e-9 \
            and abs(g[2] - 1.0) < 1e-9:
        return img
    return appliquer_gains_canaux(a, np.array(g, np.float32))


def appliquer_equilibrage(img, cadre=None, force=1.0):
    """Équilibrage des canaux (« auto », jalon 13) appliqué à un COMPOSITE :
    gains dérivés du FOND (percentile bas), force < 1 → correction partielle.
    → COPIE ; no-op si l'image n'est pas un composite couleur ou si le fond
    est dégénéré (canal noir : aucun gain raisonnable)."""
    if img is None:
        return img
    a = np.asarray(img, dtype=np.float32)
    if a.ndim != 3 or a.shape[-1] != 3:
        return img
    gains = gains_equilibre(a, cadre)
    if gains is None:
        return img
    return appliquer_gains_canaux(a, gains, force)


def corrections_couleur(img, gains=None, wb_auto=False, wb_force=1.0,
                        cadre=None, linear_fit=False, linear_fit_mode="offset"):
    """CHAÎNE DES CORRECTIONS DE COULEUR d'un composite (décision (c)) :
    gains (manuels × SPCC/Gaia) → équilibrage des canaux (auto) → recalage
    colorimétrique « Linear Fit ». SANS état ni cache : utilisable telle
    quelle depuis la façade (`CompositeStacker`, qui gère ses caches) comme
    depuis le thread du solveur live, qui re-compose l'image traitée.

    → (image corrigée, diag du recalage — None si aucun recalcul). L'entrée
    n'est JAMAIS modifiée ; une image non couleur (mono, 2D) ressort telle
    quelle (ces corrections portent sur les couleurs)."""
    out = appliquer_gains(img, gains)
    diag = None
    if wb_auto:
        out = appliquer_equilibrage(out, cadre, wb_force)
    if linear_fit:
        out, diag = aligner_canaux(out, mode=linear_fit_mode)
    return out, diag


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
    renvoie le COMPOSITE linéaire, corrections de couleur comprises
    (`mean(corrections=False)` renvoie l'empilement BRUT).

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
        # Jalon 56 (étape 5) : gains PHOTOMÉTRIQUES par rôle (zéro-point Gaia,
        # mesuré par processing/photometrie). Posés par le worker depuis la
        # mesure de la SESSION ; vide = AUCUNE correction (défaut : la mesure
        # seule n'a jamais touché l'image). Appliqués aux CARTES DE RÔLE dans
        # `moyennes()` — donc au composite ET aux couches transmises au solveur
        # live, en un seul point : les deux vues restent cohérentes.
        self.gains_roles = {}
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
        # v2.34.5 : cache de l'équilibrage des canaux appliqué au COMPOSITE
        # (la case n'agissait qu'en mono : no-op sur une carte 2D de rôle).
        self._wb_cache_comp = None
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
        self._wb_cache_comp = None        # équilibrage des canaux du composite
                                          # (v2.34.5 : la case n'agissait qu'en
                                          # mono — no-op sur un rôle 2D)

    # -- lecture du composite -------------------------------------------------
    def _recadrer(self, img):
        if self.cadre is None:
            return img
        y0, x0, y1, x1 = self.cadre
        return img[y0:y1, x0:x1]

    def moyennes(self, recadre=True):
        """{rôle: carte 2D float32 de l'empilement du rôle} — recadrées au
        cadre COMMUN si `recadre` (formes identiques, exigence de composer()).
        Matière de l'état par canal et des futures sauvegardes par canal.

        Jalon 56 (étape 5) : les gains photométriques par rôle ne sont PAS
        appliqués ici — `composer()` normalise chaque rôle par ses propres
        percentiles, ce qui ABSORBERAIT un facteur global (vérifié : le
        composite ne changeait pas). Ils passent par `gains_effectifs()`, donc
        par les gains de CANAL appliqués APRÈS la composition, dans la chaîne
        de sortie (`_appliquer_corrections`) ; les couches restent BRUTES
        (contrat jalon 54 : le solveur live re-compose depuis les couches
        brutes et ré-applique les corrections lui-même)."""
        out = {}
        for role, s in self.stackers.items():
            if s.n == 0:
                continue
            m = s.mean(recadre=False)     # accumulation complète, même repère
            out[role] = self._recadrer(m) if recadre else m
        return out

    def gains_effectifs(self):
        """Gains R/G/B du composite : gains MANUELS (UI) × gains
        PHOTOMÉTRIQUES convertis de RÔLE en CANAL (jalon 56, étape 5).

        Pourquoi par canal : `composer()` normalise chaque rôle par ses propres
        percentiles AVANT toute correction → un facteur par rôle appliqué en
        amont serait absorbé (piège vérifié au banc : le composite ne
        changeait pas). Les facteurs mesurés sont donc convertis via
        `canaux_rgb` de la composition, puis appliqués APRÈS la composition
        (chaîne de sortie, `_appliquer_corrections`) — donc JAMAIS dans la
        sauvegarde linéaire brute.

        Rôle alimentant PLUSIEURS canaux (O3 → G et B en HOO) : même facteur
        partout. Canal alimenté par plusieurs rôles (cas rare) : MOYENNE
        GÉOMÉTRIQUE de leurs facteurs. → dict 'R'/'G'/'B' → facteur."""
        gains = dict(self.gains or {})
        if not self.gains_roles:
            return gains
        spec = COMPOSITIONS.get(self.composition) or {}
        mapping = spec.get("canaux_rgb")
        if not mapping:
            return gains                       # Mono : aucun canal RGB
        for canal, roles in mapping.items():
            facteurs = [float(self.gains_roles[r]) for r in roles
                        if r in self.gains_roles
                        and float(self.gains_roles[r]) > 0.0]
            if not facteurs:
                continue
            g = float(np.exp(np.mean(np.log(facteurs))))
            gains[canal] = float(gains.get(canal, 1.0)) * g
        return gains

    def mean_avec_canaux(self, recadre=True, corrections=True):
        """(composite, {rôle: carte 2D}) en UNE passe de moyennes (jalon 24) :
        le worker a besoin des DEUX à chaque nouvel empilement (composite pour
        l'affichage, couches pour le traitement par couche du solveur live) —
        une seule exécution de mean()/recadrage au lieu de deux.
        Jalon 54 : le recalage « Linear Fit » est appliqué au COMPOSITE SEUL
        (les couches restent brutes — elles alimentent les caches du solveur
        et sa recomposition, qui ré-applique le recalage lui-même).

        `corrections` (chantier 24/09/2026 — décision d'Alain) :
          True  (DÉFAUT)  → chaîne de SORTIE : composite + corrections de
                            couleur (gains SPCC/Gaia/manuels, équilibrage,
                            recalage colorimétrique) = ce qui s'AFFICHE ;
          False           → composite BRUT, sans AUCUNE correction : c'est la
                            référence enregistrée par « Enregistrer
                            l'empilement (linéaire) ». Le fichier ne dépend
                            donc plus de l'état des cases de couleur.
        Les corrections ne s'appliquent QUE sur le chemin recadré (visu +
        sauvegardes) : `recadre=False` est la référence d'ALIGNEMENT (jalon 13)
        et reste brutalement brute, comme en mono.

        → (composite ou None, dict — vide si aucun rôle n'a de frame)."""
        canaux = self.moyennes(recadre=recadre)
        if not canaux:
            return None, None
        try:
            comp = composer(canaux, self.composition, mode_l=self.mode_l)
        except ValueError:
            comp = None                   # formes hétérogènes (ne doit pas
        # Jalon 58b/chantier 24-09 : ÉQUILIBRAGE DES CANAUX (auto, jalon 13)
        # sur le COMPOSITE, puis RECALAGE « Linear Fit » — et, en amont, les
        # GAINS (manuels × SPCC/Gaia). BUG CORRIGÉ (constat Alain, 24/09/2026) :
        # l'équilibrage n'avait AUCUN effet en mode composition —
        # `LiveStacker._equilibrer` est no-op sur une carte 2D, or chaque rôle
        # de la composition EST une carte 2D (l'équilibrage attend une image
        # couleur). Ici les corrections s'appliquent au composite (H, W, 3),
        # là où les trois canaux existent enfin — même fonction
        # `gains_equilibre`, même force.
        # NOTE MESURÉE (24/09/2026) : les corrections étant appliquées APRÈS
        # `composer()` (qui normalise chaque rôle par SES percentiles), elles ne
        # sont PLUS absorbées par cette normalisation : c'est tout l'intérêt du
        # chantier. Une normalisation COMMUNE aux trois canaux (testée) NE
        # suffisait PAS : sans soustraction du fond, le fond pollué
        # déséquilibré devient visible et l'étirement l'amplifie (mesuré :
        # R/G affiché 0,079 — image inutilisable). La neutralisation du fond
        # relève du RECALAGE COLORIMÉTRIQUE (Linear Fit, mode « Gain + offset ») :
        # mesuré sur les couches réelles, SPCC seule laisse un fond linéaire
        # 0,0130/0,0219/0,0385 (très bleu) alors que SPCC + Linear Fit donne
        # 0,0213/0,0219/0,0220 — fond NEUTRE.
        if comp is not None and corrections and recadre:
            comp = self._appliquer_corrections(comp)
        return comp, canaux

    def _appliquer_corrections(self, comp):
        """Chaîne des corrections de couleur du composite (chantier
        24/09/2026, décision (b)/(c)) — MÊME ordre que `corrections_couleur` :
        gains effectifs (manuels × SPCC/Gaia) → équilibrage des canaux →
        recalage « Linear Fit » (avec ses caches : `mean()` est appelée ~20×/s).
        No-op sur une image non couleur (Mono : aucune correction de couleur,
        l'empilement mono est déjà brut)."""
        if comp is None or comp.ndim != 3 or comp.shape[-1] != 3:
            return comp
        comp = appliquer_gains(comp, self.gains_effectifs())
        if self._wb_auto:
            comp = self._equilibrer_composite(comp)
        if self.linear_fit:
            comp = self._recaler_fit(comp)         # → case DÉCOCHÉE = brut
        return comp

    def _equilibrer_composite(self, comp):
        """Équilibrage des canaux du COMPOSITE (jalon 13 appliqué au composite,
        v2.34.5) : gains par canal dérivés du FOND (percentile bas), mis en
        cache par (frames totales, force, cadre) — `mean()` est appelée ~20×/s
        mais rien ne change entre deux frames. Force < 1 → gains partiels
        (`gains ** force`), comme dans `LiveStacker._equilibrer`."""
        if comp.ndim != 3 or comp.shape[-1] != 3:
            return comp
        cle = (sum(s.n for s in self.stackers.values()),
               round(float(self.wb_force), 4), self.cadre)
        if self._wb_cache_comp is not None and self._wb_cache_comp[0] == cle:
            gains = self._wb_cache_comp[1]
        else:
            gains = gains_equilibre(comp, self.cadre)
            self._wb_cache_comp = (cle, gains)
        return appliquer_gains_canaux(comp, gains, self.wb_force)

    def _recaler_fit(self, comp):
        """Recalage « Linear Fit » du composite (jalon 54) : cf.
        CompositeStacker.linear_fit. Cache par (frames totales, GAINS EFFECTIFS,
        mode L, mode) : les stats du composite dépendent de l'accumulation ET
        des réglages qui la composent → recalcul seulement quand l'un change
        (aucun pompage entre deux ticks). Les gains EFFECTIFS (manuels ×
        photométriques) entrent dans la clé : un facteur photométrique qui
        apparaît doit recalculer le fit, sinon la vue serait incohérente."""
        if comp.ndim != 3 or comp.shape[-1] != 3:
            return comp
        ge = self.gains_effectifs()
        gains_sig = (tuple(round(float(ge.get(c, 1.0)), 4)
                           for c in ("R", "G", "B"))
                     if ge else None)
        cle = (sum(s.n for s in self.stackers.values()),
               self.linear_fit_mode, gains_sig, self.mode_l)
        if self._fit_cache is not None and self._fit_cache[0] == cle:
            out, diag = self._fit_cache[1]
        else:
            out, diag = aligner_canaux(comp, mode=self.linear_fit_mode)
            self._fit_cache = (cle, (out, diag))
        self.fit_diag = diag
        return out if diag is not None else comp

    def mean(self, recadre=True, corrections=True):
        """Composite LINÉAIRE courant (composer : normalisation par canal,
        puis — si `corrections` — les corrections de couleur de la chaîne de
        sortie), recadré au cadre commun si `recadre`. → (H, W, 3) float32
        (ou (H, W) en Mono), None si aucun rôle n'a de frame.

        `corrections=False` → EMPILEMENT BRUT (aucun gain, aucun équilibrage,
        aucun recalage) : c'est ce que la sauvegarde linéaire enregistre."""
        comp, _ = self.mean_avec_canaux(recadre=recadre, corrections=corrections)
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

