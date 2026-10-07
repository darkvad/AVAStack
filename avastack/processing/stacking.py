# -*- coding: utf-8 -*-
"""Empilement glissant avec rejet des traînées (satellites, avions, météores).

Deux méthodes de rejet :
- « kappa » : kappa-sigma séquentiel (historique, léger en mémoire) — chaque
  frame est comparée aux statistiques CUMULÉES (moyenne/écart-type).
  Faiblesse : une traînée passée pendant le warmup s'incruste dans la
  moyenne cumulée, puis ce sont les frames PROPRES qui s'en écartent et se
  font rejeter — la trace reste figée dans l'empilement.
- « winsorized » : adaptation au live stacking du Winsorized Sigma Clipping
  de PixInsight — chaque frame est comparée à la MÉDIANE et au MAD d'une
  fenêtre glissante des dernières frames alignées. La médiane est robuste
  aux traînées (minoritaires par pixel : un satellite ne traverse une
  position donnée que sur une fraction des frames), donc les traces sont
  rejetées dans les deux sens, y compris si elles sont passées pendant le
  warmup. Coût : la fenêtre de frames alignées reste en RAM (float32).
"""

import os
import threading
from typing import Any

import numpy as np

# Taille (en valeurs) des bandes de lignes traitées d'un coup en mode
# winsorized : borne la mémoire des temporaires de np.median/np.abs
# (surchargeable par les tests pour forcer le multi-bandes).
_CHUNK_PX: int = 4_000_000

# --- Jalon 79 : parallélisme du cœur d'empilement ---------------------------
# Nombre de BANDES de lignes traitées en parallèle (voir `_en_parallele`).
# Mesuré sur la machine de dev (Core Ultra 5 125U, 8,4 Mpx) : `add` kappa
# passe de 116 ms à 51 ms entre 1 et 4 bandes. Volontairement BAS : la
# mémoire et les cœurs sont partagés avec l'interface, les solveurs et
# l'archivage — saturer les 12 cœurs ne rendrait pas l'application plus
# rapide, seulement moins réactive.
_THREADS: int = max(1, min(4, (os.cpu_count() or 4) - 2))
# Sous ce nombre de pixels, une seule bande : le découpage (et le fil) coûte
# plus qu'il ne rapporte, et les petits bancs doivent rester strictement
# séquentiels (résultats identiques à l'ancien code).
_SEUIL_PARALLELE: int = 1_500_000


def _en_parallele(bandes: list[tuple[int, int]], travail: Any) -> None:
    """Exécute `travail(i, debut, fin)` sur chaque bande de lignes, dans un fil
    par bande dès qu'il y en a plusieurs. Les grandes opérations numpy libèrent
    le GIL : les bandes calculent réellement en parallèle (mesuré ×3,3 sur une
    opération élémentaire de 8,4 Mpx). Aucun verrou n'est nécessaire : chaque
    bande n'écrit que dans SES lignes, et les compteurs de rejets ont une case
    par bande."""
    if len(bandes) <= 1:
        travail(0, *bandes[0])
        return
    fils = [threading.Thread(target=travail, args=(i,) + b, daemon=True)
            for i, b in enumerate(bandes)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()

# Marge (pixels) retirée de chaque côté du rectangle d'intersection : le
# warpAffine linéaire « creuse » (undershoot) au ras des bords couverts,
# et quelques pixels d'hale à l'intersection suffisent à perturber le
# modèle de fond de GraXpert (leçon du pipeline astromatix : recadrage à
# l'intersection RÉELLE, jamais au ras du bord).
_MARGE_CROP: int = 3

# Le recadrage n'a de sens qu'au-delà de ce nombre minimal de pixels par
# côté (sinon on garde l'image entière plutôt qu'un timbre-poste).
_CROP_MIN_COTE: int = 16


# --- Équilibrage des canaux (jalon 13) ---------------------------------------
# Les capteurs couleur ont 2 sites verts sur 4 (matrice de Bayer) et une
# réponse spectrale déséquilibrée : un empilement brut OSC domine dans le
# vert (constat réel d'Alain, NGC7023, Uranus-C Pro, 17/09/2026). L'option
# « Équilibrage des canaux (auto) » multiplie chaque canal par un gain
# LINÉAIRE égalisant le FOND du ciel des trois canaux : le fond (percentile
# bas), pas les objets — la couleur de la nébulose est donc préservée.
# Géométrique moyenne = flux total conservé ; gains bornés contre les
# extrêmes (canal quasi noir → amplification folle interdite).
WB_PERCENTILE: float = 20.0
WB_GAIN_MIN: float = 0.25
WB_GAIN_MAX: float = 4.0


def gains_equilibre(img: np.ndarray,
                    cadre: Any = None) -> np.ndarray | None:
    """Gains (r, v, b) égalisant le fond des 3 canaux de `img` ((H, W, 3) ou
    (C, H, W)). Stats sur la zone recadrée si `cadre` est fourni (les bords
    jamais couverts par les frames alignées y sont à zéro et fausseraient
    les percentiles), sinon sur le quart central ; sous-échantillonnage ×4
    (largement suffisant). → numpy (3,) float32, ou None si dégénéré."""
    if img.ndim != 3:
        return None
    hwc = img.shape[-1] == 3
    if cadre is not None:
        y0, x0, y1, x1 = cadre
        zone = img[y0:y1, x0:x1, :] if hwc else img[:, y0:y1, x0:x1]
    else:
        h, w = img.shape[:2] if hwc else img.shape[1:3]
        zone = (img[h // 4: max(h // 4 + 1, 3 * h // 4),
                    w // 4: max(w // 4 + 1, 3 * w // 4), :] if hwc else
                img[:, h // 4: max(h // 4 + 1, 3 * h // 4),
                    w // 4: max(w // 4 + 1, 3 * w // 4)])
    if zone.size == 0:
        return None
    if hwc:
        echant = zone[::4, ::4, :]
        bgs = [float(np.percentile(echant[..., c], WB_PERCENTILE))
               for c in range(3)]
    else:
        echant = zone[:, ::4, ::4]
        bgs = [float(np.percentile(echant[c], WB_PERCENTILE)) for c in range(3)]
    if min(bgs) <= 1e-9:
        return None
    cible = (bgs[0] * bgs[1] * bgs[2]) ** (1.0 / 3.0)
    return np.array([min(max(cible / b, WB_GAIN_MIN), WB_GAIN_MAX)
                     for b in bgs], np.float32)


# --- Recalage colorimétrique « Linear Fit » (jalon 54) ------------------------
# Équivalent live du Linear Fit d'Astro Pixel Processor (version robuste) :
# les canaux R et B sont recalés sur le VERT (référence) par une droite
# Gain + Offset, mesurée sur les statistiques ROBUSTES du composite
# linéaire (médiane + MAD). La différence de fond de ciel (pollution qui
# ne frappe pas pareillement les filtres) est un DÉCALAGE (offset), la
# différence de sensibilité (transmission optique, QE, rendement debayer)
# est un FACTEUR (gain) : la droite les corrige tous les deux, l'offset
# seul ne corrige que le fond. Indispensable AVANT l'étirement : le STF
# (points noir/blanc communs aux 3 canaux) et VeraLux (préserve les
# ratios) amplifient sinon le décalage en un MASQUE coloré (constat réel
# d'Alain : fond bleu dans les poussières de M31).
FIT_GAIN_MIN: float = 0.25
FIT_GAIN_MAX: float = 4.0                   # mêmes bornes que l'équilibrage
FIT_MODES: tuple[str, ...] = ("gain_offset", "offset")


def stats_canaux(rgb: np.ndarray) -> dict[str, Any] | None:
    """Stats (médiane, σ_robuste = MAD × 1,4826) des 3 canaux d'une image
    couleur, layouts (H, W, 3) ou (3, H, W) — quart central sous-
    échantillonné ×4 (largement suffisant ; évite les bords jamais couverts
    par les frames alignées, qui restent à zéro et fausseraient tout).
    → {"med": (r, g, b), "sigma": (r, g, b)}, ou None si dégénéré (forme
    inattendue, quart vide, ou canal PLAT — rôle absent, canal mort : la
    droite n'y a pas de sens, l'appelant ne doit rien corriger)."""
    a = np.asarray(rgb, dtype=np.float32)
    hwc = a.ndim == 3 and a.shape[-1] == 3
    if not hwc and not (a.ndim == 3 and a.shape[0] == 3):
        return None
    h, w = (a.shape[0], a.shape[1]) if hwc else (a.shape[1], a.shape[2])
    sl_h = slice(h // 4, max(h // 4 + 1, 3 * h // 4), 4)
    sl_w = slice(w // 4, max(w // 4 + 1, 3 * w // 4), 4)
    z = a[sl_h, sl_w] if hwc else a[:, sl_h, sl_w]
    if z.size == 0:
        return None
    med, sig = [], []
    for c in range(3):
        m = float(np.median(z[..., c]))
        s = 1.4826 * float(np.median(np.abs(z[..., c] - m)))
        med.append(m)
        sig.append(s)
    if min(sig) <= 1e-12:
        return None
    return {"med": tuple(med), "sigma": tuple(sig)}


def aligner_canaux(rgb: np.ndarray, mode: str = "offset"
                   ) -> tuple[np.ndarray, dict[str, Any] | None]:
    """Recalage « Linear Fit » : R et B recalés sur le VERT (référence).
      gain_X   = σ_G / σ_X, borné [FIT_GAIN_MIN, FIT_GAIN_MAX] — 1.0 en
                 mode « offset » (recalage du fond seul, DÉFAUT — retour
                 du test réel d'Alain, 21/09/2026 : le gain fondé sur le
                 rapport des bruits amplifie halos et bruit du canal bleu
                 d'une image OSC déjà équilibrée → aspect flou/décalé à
                 l'étirement ; le gain reste disponible pour les palettes
                 narrowband, via le menu de l'UI) ;
      offset_X = med_G − gain_X · med_X
      pixel    : X' = gain_X·X + offset_X, plancher 0 (un offset négatif ne
                 doit jamais créer de valeurs négatives) ; G inchangé.
    → (image corrigée — COPIE, diag) avec diag = {"mode", "gains", "offsets"}
    (tuples (R, G, B), G = 1.0 / 0.0), ou (copie, None) si dégénéré (mono,
    canal plat : cf. stats_canaux). L'entrée n'est JAMAIS modifiée ;
    aucune exception (numpy seul)."""
    a = np.asarray(rgb, dtype=np.float32)
    hwc = a.ndim == 3 and a.shape[-1] == 3
    if not hwc and not (a.ndim == 3 and a.shape[0] == 3):
        return a.copy(), None
    plan = a if hwc else np.transpose(a, (1, 2, 0))
    st = stats_canaux(plan)
    if st is None:
        return a.copy(), None
    if mode not in FIT_MODES:
        mode = "offset"                    # mode inconnu → le plus doux
    med, sig = st["med"], st["sigma"]
    g = [1.0, 1.0, 1.0]
    o = [0.0, 0.0, 0.0]
    for c in (0, 2):
        gc = (1.0 if mode == "offset"
              else float(min(max(sig[1] / sig[c], FIT_GAIN_MIN),
                             FIT_GAIN_MAX)))
        g[c] = gc
        o[c] = med[1] - gc * med[c]
    out = plan.copy()
    for c in (0, 2):
        out[..., c] = np.clip(g[c] * plan[..., c] + o[c], 0.0, None)
    res = out if hwc else np.transpose(out, (2, 0, 1))
    diag = {"mode": mode, "gains": tuple(g), "offsets": tuple(o)}
    return res.astype(np.float32, copy=False), diag


def quad_alignement(M: Any, shape: Any) -> np.ndarray:
    """Coins (x, y) de l'image `shape` transformés par la matrice affine
    `M` (2×3, celle de cv2.warpAffine) — le quadrilatère couvert par la
    frame alignée, dans le repère de l'image cible (H, W). Accepte (H, W),
    (H, W, C) ou (C, H, W) : seuls H et W comptent."""
    shape = tuple(shape)
    if len(shape) == 2:
        h, w = shape
    elif shape[0] <= 4:                       # (C, H, W)
        h, w = shape[1], shape[2]
    else:                                     # (H, W, C)
        h, w = shape[0], shape[1]
    pts = np.array([[0.0, 0.0], [w, 0.0], [w, h], [0.0, h]])
    M = np.asarray(M, np.float64)
    pts = pts @ M[:, :2].T + M[:, 2]
    return pts


def _aire_signee(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def _clip_poly(suj: Any, clip: Any) -> np.ndarray | None:
    """Sutherland–Hodgman : clippe le polygone convexe `suj` par le
    polygone convexe `clip` (numpy (n, 2)). Renvoie numpy (m, 2) ou None
    si l'intersection est vide."""
    res = [tuple(p) for p in np.asarray(suj, np.float64)]
    cl = [tuple(p) for p in np.asarray(clip, np.float64)]
    m = len(cl)
    for i in range(m):
        a, b = cl[i], cl[(i + 1) % m]
        dx, dy = b[0] - a[0], b[1] - a[1]

        def dedans(p, a=a, b=b, dx=dx, dy=dy):
            return (dx * (p[1] - a[1]) - dy * (p[0] - a[0])) >= 0.0

        nouveau = []
        n = len(res)
        for j in range(n):
            c, d = res[j], res[(j + 1) % n]
            sc, sd = dedans(c), dedans(d)
            if sc:
                nouveau.append(c)
            if sc != sd:                    # le segment traverse la frontière
                ex, ey = d[0] - c[0], d[1] - c[1]
                t = (dx * (a[1] - c[1]) - dy * (a[0] - c[0])) / \
                    (dx * ey - dy * ex)
                t = min(1.0, max(0.0, t))
                nouveau.append((c[0] + t * ex, c[1] + t * ey))
        res = nouveau
        if not res:
            return None
    return np.array(res, np.float64)


def cadre_intersection(poly: Any, marge: int = _MARGE_CROP,
                       min_cote: int = _CROP_MIN_COTE
                       ) -> tuple[int, int, int, int] | None:
    """Rectangle (y0, x0, y1, x1) englobant STRICTEMENT l'intérieur du
    polygone (arrondi vers l'intérieur + marge de sécurité), ou None si le
    polygone est dégénéré ou trop petit pour valoir un recadrage."""
    if poly is None or len(poly) < 3:
        return None
    y0 = int(np.ceil(poly[:, 1].min())) + marge
    y1 = int(np.floor(poly[:, 1].max())) - marge
    x0 = int(np.ceil(poly[:, 0].min())) + marge
    x1 = int(np.floor(poly[:, 0].max())) - marge
    if y1 - y0 < min_cote or x1 - x0 < min_cote:
        return None
    return (y0, x0, y1, x1)


def _gains_canaux(img: np.ndarray, gains: Any = None) -> np.ndarray:
    """Gains R/G/B (dict « R »/« G »/« B ») sur une image couleur, quel que soit
    l'ordre des axes — (H, W, 3) comme (3, H, W). Délégation à
    `composition.appliquer_gains` par import LOCAL (composition importe ce
    module : un import en tête ferait un cycle). → l'image telle quelle si rien
    à faire (mono, pas de gains)."""
    if not gains or img is None or img.ndim != 3:
        return img
    from .composition import appliquer_gains
    if img.shape[-1] == 3:
        return appliquer_gains(img, gains)
    if img.shape[0] == 3:
        return np.ascontiguousarray(
            np.transpose(appliquer_gains(np.transpose(img, (1, 2, 0)), gains),
                         (2, 0, 1)))
    return img


class LiveStacker:
    """Moyenne glissante + rejet kappa-sigma ou Winsorized (fenêtre glissante)."""

    METHODES: tuple[str, ...] = ("kappa", "winsorized")

    def __init__(self, shape: Any, k: float | None = 3.0, warmup: int = 5,
                 method: str = "kappa", window: int = 8) -> None:
        self.shape: Any = shape
        self.k: float | None = k
        self.warmup: int = warmup
        self.method: str = method if method in self.METHODES else "kappa"
        self.window: int = max(3, int(window))
        # Équilibrage des canaux (jalon 13) : désactivé au niveau module —
        # l'interface l'active (config persistée) ; les tests existants
        # voient donc l'ancien comportement.
        self.wb_auto: bool = False
        self.wb_force: float = 1.0
        # Recalage colorimétrique « Linear Fit » (jalon 54) : désactivé au
        # niveau module — l'interface l'active (config persistée) ; les tests
        # existants voient l'ancien comportement. Mode « offset » PAR DÉFAUT
        # (retour du test réel d'Alain, 21/09/2026 : le gain fondé sur le
        # rapport des bruits amplifie halos/bruit bleus d'une image OSC
        # équilibrée → aspect flou/décalé ; le gain reste en option UI).
        self.linear_fit: bool = False
        self.linear_fit_mode: str = "offset"
        self.fit_diag: Any = None         # gains/offsets mesurés (UI)
        # Jalon 58 bis (v2.40.0) : gains R/G/B par CANAL du composite — c'est
        # ici que la SPCC (capteur couleur/OSC) corrige une source COULEUR
        # (« mode dossier » d'une caméra OSC) : en composition, ces gains sont
        # portés par la façade (`CompositeStacker.gains_roles`) ; en source
        # couleur simple, il n'y avait AUCUN chemin pour les appliquer, d'où
        # l'ajout. Appliqués AVANT l'équilibrage et le recalage, comme
        # `corrections_couleur` (gains → équilibrage → Linear Fit).
        self.gains: Any = None
        self.reset()

    def reset(self) -> None:
        self.sum: np.ndarray = np.zeros(self.shape, np.float64)
        self.sumsq: np.ndarray = np.zeros(self.shape, np.float64)
        self.wsum: np.ndarray = np.zeros(self.shape, np.float64)
        self.n: int = 0
        self.rejected_total: int = 0
        self._buf: Any = None       # fenêtre glissante (winsorized)
        self._nbuf: int = 0
        self._rejeu: bool = False    # rejeu du warmup déjà effectué ?
        # Jalon 79 : tampons de travail préalloués (cf. `_tampons`) — libérés
        # ici, réalloués à la première frame de la nouvelle géométrie ; et la
        # moyenne mémoïsée (cf. `_moyenne_brute`) n'a plus cours.
        self._moy: Any = None
        self._sig: Any = None
        self._dif: Any = None
        self._pix: Any = None
        self._masq: Any = None
        self._memo_moy: Any = None
        self._poly: np.ndarray | None = None      # intersection des zones
        self.cadre: tuple[int, int, int, int] | None = None   # recadrage
        self._wb_cache: Any = None  # (clé, gains) de l'équilibrage des canaux
        self._fit_cache: Any = None  # (clé, (image, diag)) du recalage Linear Fit
        self.fit_diag: Any = None

    def note_alignement(self, M: Any) -> None:
        """Met à jour l'intersection géométrique des zones couvertes avec la
        matrice d'alignement `M` de la frame qui vient d'être empilée
        (équivalent live du `-framing=min` de Siril : l'intersection RÉELLE
        calculée par les transformations, pas une heuristique de pixels).
        mean() renvoie ensuite l'accumulation RECADRÉE à cette intersection —
        les bords d'écart de recouvrement (partiellement exposés) sortent de
        tout ce qui en découle, y compris de l'image envoyée à GraXpert."""
        if M is None:
            return
        q = quad_alignement(M, self.shape)
        if _aire_signee(q) < 0:        # orientation normalisée
            q = q[::-1].copy()
        if self._poly is None:         # le cadre cible est la borne absolue
            self._poly = quad_alignement(
                np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]), self.shape)
        p = _clip_poly(self._poly, q)
        if p is not None:              # vide = M aberrante → on ignore
            self._poly = p
        self.cadre = cadre_intersection(self._poly)

    def set_rejet(self, method: str | None = None,
                  window: int | None = None) -> None:
        """Change de méthode / de taille de fenêtre à chaud, sans perdre
        l'accumulation : seule la fenêtre de référence est vidée (elle se
        remplit à nouveau, le rejet redevient effectif dès qu'elle est
        pleine — cf. warmup)."""
        changed = False
        if method is not None and method in self.METHODES and method != self.method:
            self.method = method
            changed = True
        if window is not None:
            window = max(3, int(window))
            if window != self.window:
                self.window = window
                changed = True
        if changed:
            self._buf = None
            self._nbuf = 0
            self._rejeu = False

    def add(self, frame: np.ndarray) -> None:
        """Empile une frame (jalon 79) : tampons de travail PRÉALLOUÉS, calcul
        élémentaire en float32, et accumulations comme SEUIL DE REJET en
        float64 — les mathématiques et jusqu'aux valeurs accumulées sont
        exactement celles d'avant (vérifié au banc : sommes identiques AU BIT,
        compteur de rejets identique), seules la mémoire et le parallélisme
        changent. Avant : ~15 tableaux float64 créés puis jetés par frame.
        """
        f = frame if frame.dtype == np.float32 else frame.astype(np.float32)
        self._tampons(f.shape)
        bandes = self._bandes()
        masque = self._masque_rejet(f, bandes)   # True = rejeté, None = garder tout
        _en_parallele(bandes,
                      lambda i, a, b: self._cumuler(f, masque, a, b))
        self.n += 1

    # ------------------------------------- jalon 79 : mémoire et parallélisme
    def _tampons(self, forme: Any) -> None:
        """Tampons de travail PRÉALLOUÉS, une fois par géométrie (jalon 79).
        Le coût de `add` venait des tableaux float64 créés à chaque frame : sur
        8,4 Mpx, 325 ms en warmup dont l'essentiel en allocation (le même calcul
        sans temporaires en coûte 51 ms avec 4 fils). Aucun n'est lu avant
        d'être écrit → `np.empty`, jamais de remise à zéro."""
        if self._moy is not None and self._moy.shape == forme:
            return
        self._moy = np.empty(forme, np.float64)     # moyenne cumulée
        self._sig = np.empty(forme, np.float64)     # seuil k·σ
        self._dif = np.empty(forme, np.float64)     # écart |frame − moyenne|
        self._pix = np.empty(forme, np.float32)     # frame masquée (poids 0/1)
        self._masq = np.empty(forme, bool)          # pixels rejetés

    def _bandes(self) -> list[tuple[int, int]]:
        """Bornes de lignes des bandes de travail. Plusieurs bandes = plusieurs
        fils (cf. `_en_parallele`) ; une seule pour les petites images, où le
        découpage coûterait plus qu'il ne rapporte — et où les bancs doivent
        rester strictement séquentiels pour comparer à l'ancien code."""
        h = int(self.shape[0])
        px = int(np.prod(self.shape[1:], dtype=np.int64))
        n = _THREADS if (h * px) >= _SEUIL_PARALLELE else 1
        n = max(1, min(int(n), h))
        if n <= 1:
            return [(0, h)]
        pas = max(1, h // n)
        bornes = [(i * pas, (i + 1) * pas) for i in range(n - 1)]
        bornes.append((bornes[-1][1] if bornes else 0, h))
        return bornes

    def _masque_rejet(self, f: np.ndarray,
                      bandes: Any) -> np.ndarray | None:
        """Masque des pixels REJETÉS de la frame courante (True = rejeté), ou
        None quand rien n'est rejeté (k désactivé, ou warmup).

        Les mathématiques sont CELLES D'AVANT : moyenne et σ cumulés en
        float64, comparaison |frame − moyenne| > k·σ elle aussi en float64 (la
        frame float32 y est promue exactement). `rejected_total` est incrémenté
        ici, comme avant."""
        if self.k is None:
            return None
        if self.method == "winsorized":
            return self._masque_winsorized(f, bandes)
        if self.n < self.warmup:
            return None                     # warmup : tout est gardé à poids 1
        _en_parallele(bandes,
                      lambda i, a, b: self._masque_kappa(f, a, b))
        self.rejected_total += int(np.count_nonzero(self._masq))
        return self._masq

    def _masque_kappa(self, f: np.ndarray, a: int, b: int) -> None:
        """Kappa-sigma séquentiel sur les lignes [a, b) — relecture EXACTE de
        l'ancien code, les opérations étant simplement faites en place :
            moyenne = sum / max(wsum, 1e-9)
            σ       = sqrt(max(sumsq / max(wsum, 1e-9) − moyenne², 1e-12))
            rejet si |frame − moyenne| > k·σ
        """
        cum, car, poi = self.sum[a:b], self.sumsq[a:b], self.wsum[a:b]
        moy, sig, dif = self._moy[a:b], self._sig[a:b], self._dif[a:b]
        np.maximum(poi, 1e-9, out=dif)          # dénominateur (jamais nul)
        np.divide(cum, dif, out=moy)
        np.divide(car, dif, out=sig)
        np.multiply(moy, moy, out=dif)
        np.subtract(sig, dif, out=sig)          # variance
        np.maximum(sig, 1e-12, out=sig)
        np.sqrt(sig, out=sig)
        np.multiply(sig, self.k, out=sig)       # seuil k·σ  # pyright: ignore[reportCallIssue, reportArgumentType]
        # |frame − moyenne| : la frame float32 est promue en float64 par le
        # calcul lui-même (casting unsafe) → mêmes valeurs qu'avant, au bit.
        np.subtract(f[a:b], moy, out=dif, casting="unsafe")
        np.abs(dif, out=dif)
        np.greater(dif, sig, out=self._masq[a:b])

    def _cumuler(self, f: np.ndarray, masque: np.ndarray | None,
                 a: int, b: int) -> None:
        """Cumule la frame `f` sur les lignes [a, b) : chaque bande n'écrit que
        dans SES lignes. Les CARRÉS sont calculés en float64 — le produit de
        deux float32 y est EXACT — donc `sumsq` est bit à bit celui de l'ancien
        code, et la décision de rejet des frames suivantes est identique."""
        fb = f[a:b]
        cum, car, poi = self.sum[a:b], self.sumsq[a:b], self.wsum[a:b]
        scar = self._dif[a:b]
        if masque is None:                      # tout garder (warmup, k=None)
            np.multiply(fb, fb, out=scar, casting="unsafe")
            np.add(cum, fb, out=cum, casting="unsafe")
            np.add(car, scar, out=car)
            np.add(poi, 1.0, out=poi)
            return
        mb = masque[a:b]
        pix = self._pix[a:b]
        # Masque NÉGATIF (gardés = 1) : `np.where` n'accepte pas `out` — la
        # multiplication par un booléen est exacte (×1.0 ou ×0.0).
        np.logical_not(mb, out=mb)
        np.multiply(fb, mb, out=pix, casting="unsafe")   # rejetés → 0
        np.add(cum, pix, out=cum, casting="unsafe")
        np.multiply(pix, pix, out=scar, casting="unsafe")
        np.add(car, scar, out=car)
        np.add(poi, mb, out=poi, casting="unsafe")

    def mean(self, recadre: bool = True,
             corrections: bool = True) -> np.ndarray | None:
        """Moyenne pondérée courante. `recadre=False` renvoie l'accumulation
        COMPLÈTE, sans le recadrage d'intersection — réservé à la référence
        d'alignement (jalon 13) : la référence doit rester dans le MÊME repère
        que les frames alignées, sinon chaque rafraîchissement décalerait tout
        l'empilement (c'était le bug silencieux du bouton « Réf. =
        empilement », qui fournissait l'empilement RECADRÉ).

        `corrections=False` (chantier 24/09/2026, règle d'Alain : la sauvegarde
        linéaire est BRUTE) → ni équilibrage des canaux ni recalage
        colorimétrique : l'EMPILEMENT BRUT. Ce paramètre existe aussi pour que
        l'interface reste identique à celle de `CompositeStacker.mean()` ;
        en composition multi-rôles, les corrections sont portées par la façade."""
        if self.n == 0:
            return None
        img = self._moyenne_brute()
        if corrections:
            img = _gains_canaux(img, self.gains)   # gains R/G/B (SPCC, OSC)
            img = self._equilibrer(img)
        if not recadre or self.cadre is None:  # pas de recadrage (dégénéré)
            return img
        y0, x0, y1, x1 = self.cadre
        if img.ndim == 3 and img.shape[0] <= 4:    # (C, H, W)
            crop = img[:, y0:y1, x0:x1]
        else:                                      # (H, W) ou (H, W, C)
            crop = img[y0:y1, x0:x1, ...]
        return self._recaler_fit(crop) if corrections else crop

    def _moyenne_brute(self) -> np.ndarray:
        """Moyenne pondérée de l'accumulation (sum / wsum), en float32 —
        MÉMOÏSÉE sur `n` (jalon 79).

        POURQUOI : `mean()` est appelée plusieurs fois pour UNE MÊME frame (fin
        de boucle du worker, couches du solveur, sauvegardes, gestes de
        l'interface) et le résultat ne change qu'à l'arrivée d'une frame — `n`
        est donc la clé exacte. Le recadrage reste une VUE (`y0:y1, x0:x1`) et
        les corrections gardent leurs propres caches.

        CONTRAT : l'image rendue peut être PARTAGÉE entre plusieurs appelants
        (elle n'est jamais modifiée en place par aucun d'eux — elle est lue,
        recadrée en vue, recopiée par `cv2.resize` ou transmise à `composer`).
        Le cache est vidé par `reset()`."""
        if self._memo_moy is not None and self._memo_moy[0] == self.n:
            return self._memo_moy[1]
        img = (self.sum / np.maximum(self.wsum, 1e-9)).astype(np.float32)
        self._memo_moy = (self.n, img)
        return img

    def _recaler_fit(self, img: np.ndarray) -> np.ndarray:
        """Recalage colorimétrique « Linear Fit » (jalon 54) : R et B
        alignés sur le VERT (gain + offset), APRÈS l'équilibrage WB et le
        recadrage — visu et sauvegardes uniquement (la référence
        d'alignement, mean(recadre=False), reste BRUTE : un recalage
        colorimétrique n'a rien à faire dans l'ancre de l'aligneur).
        Cache par (n, mode) : mean() est appelée à chaque nouvelle frame
        mais les stats ne dépendent que de l'accumulation → un seul calcul
        par frame empilée, aucun pompage entre deux ticks. no-op en mono ou
        si désactivé ; dégénéré (canal plat, cf. aligner_canaux) → image
        inchangée + diag None."""
        if not self.linear_fit or img.ndim != 3 \
                or 3 not in (img.shape[-1], img.shape[0]):
            return img
        cle = (self.n, self.linear_fit_mode)
        if self._fit_cache is not None and self._fit_cache[0] == cle:
            out, diag = self._fit_cache[1]
        else:
            out, diag = aligner_canaux(img, mode=self.linear_fit_mode)
            self._fit_cache = (cle, (out, diag))
        self.fit_diag = diag
        return out if diag is not None else img

    def _equilibrer(self, img: np.ndarray) -> np.ndarray:
        """Équilibrage des canaux (auto, jalon 13) : gains par canal dérivés
        du FOND de l'accumulation, mis en cache (recalculés une seule fois
        par frame empilée — `mean()` est appelée ~20×/s mais `n` ne change
        qu'à l'arrivée d'une frame). no-op en mono ou si désactivé."""
        if (not self.wb_auto or img.ndim != 3
                or 3 not in (img.shape[-1], img.shape[0])):
            return img
        cle = (self.n, round(float(self.wb_force), 4), self.cadre)
        if self._wb_cache is not None and self._wb_cache[0] == cle:
            gains = self._wb_cache[1]
        else:
            gains = gains_equilibre(img, self.cadre)
            self._wb_cache = (cle, gains)
        if gains is None:
            return img
        if self.wb_force < 1.0:
            gains = gains ** float(self.wb_force)
        if img.shape[-1] == 3:               # (H, W, 3) : diffuse sur l'axe couleur
            return img * gains
        return img * gains[:, None, None]    # (C, H, W) : piège du broadcast

    # ------------------------------------------------------------- rejet
    def _masque_winsorized(self, f: np.ndarray,
                           bandes: Any) -> np.ndarray | None:
        """Rejet contre la médiane/MAD de la fenêtre glissante (PixInsight).

        σ_robuste = 1.4826 × MAD (équivalent gaussien de l'écart-type
        médian absolu) : insensible aux valeurs aberrantes du buffer lui-
        même, contrairement à l'écart-type cumulé du mode kappa (une
        traînée passée pendant le warmup y gonfle σ pour toujours, ce qui
        masque les traces suivantes aux mêmes pixels). Rejet symétrique
        |frame − médiane| > k·σ_robuste (le k de la combobox kappa sert de
        seuil haut/bas).

        REJEU DU WARMUP : pendant les premières frames, la médiane
        n'existe pas encore et tout est accumulé à poids 1 — une trace
        passée là s'incrusterait à jamais (diluée en A/n). Quand la
        fenêtre se remplit pour la PREMIÈRE fois (elle contient alors
        toutes les frames accumulées), l'accumulation est reconstruite
        avec les poids robustes : la trace précoce est effacée, pas
        seulement diluée.

        Jalon 79 — MÊMES mathématiques, mais réparties par BANDES DE LIGNES :
        la médiane d'une bande ne dépend pas du reste de l'image, donc le
        découpage ne change RIEN au résultat (vérifié au banc : sommes et
        rejets identiques) et les bandes calculent en parallèle."""
        self._push_buf(f)
        if self._nbuf < min(self.warmup, self.window) or self._nbuf < 2:
            return None                       # fenêtre incomplète : poids 1
        buf = self._buf[:self._nbuf]           # (n, H, W) ou (n, H, W, 3)
        # Rejeu uniquement si le buffer plein contient TOUTES les frames
        # accumulées (n+1 == window) : sinon la reconstruction écraserait
        # des frames plus anciennes jamais rejouées.
        rejeu = (not self._rejeu and self._nbuf == self.window
                 and self.n + 1 == self._nbuf)
        rejets = [0] * len(bandes)             # une case par bande (pas de verrou)
        _en_parallele(bandes,
                      lambda i, a, b: self._winsorized_bande(
                          buf, rejets, i, a, b, rejeu))
        if rejeu:
            self._rejeu = True
            self.rejected_total = sum(rejets)  # rejets des frames 0..n-2
        self.rejected_total += int(np.count_nonzero(self._masq))
        return self._masq

    def _winsorized_bande(self, buf: np.ndarray, rejets: list[int],
                          i: int, a: int, b: int, rejeu: bool) -> None:
        """Médiane/MAD de la fenêtre sur les lignes [a, b), puis masque de rejet
        de la frame courante — code IDENTIQUE à celui d'avant, découpé en chunks
        de `_CHUNK_PX` valeurs pour borner les temporaires de np.median."""
        px_par_ligne = int(np.prod(buf.shape[2:], dtype=np.int64))  # W ou W*3
        lignes = max(1, _CHUNK_PX // max(1, px_par_ligne * buf.shape[0]))
        for d in range(a, b, lignes):
            e = min(b, d + lignes)
            blk = buf[:, d:e]                              # (n, l, ...)
            med = np.median(blk, axis=0)
            mad = np.median(np.abs(blk - med), axis=0)
            sigma = np.maximum(1.4826 * mad, 1e-6)         # plancher zones plates
            hors = np.abs(blk - med) > self.k * sigma      # (n, l, ...)
            if rejeu:
                # frames 0..n-2 reconstruites avec les poids robustes
                # (la frame courante, dernière du buffer, est ajoutée
                # ensuite — jamais de double comptage) ;
                # AFFECTATION (pas +=) : on remplace l'accumulation
                # contaminée du warmup.
                passe = hors[:-1]
                self.sum[d:e] = (blk[:-1] * ~passe).sum(axis=0)
                self.sumsq[d:e] = (blk[:-1] * blk[:-1] * ~passe).sum(axis=0)
                self.wsum[d:e] = (~passe).sum(axis=0)
                rejets[i] += int(passe.sum())
            np.copyto(self._masq[d:e], hors[-1])           # frame courante

    def _push_buf(self, frame: np.ndarray) -> None:
        """Insère la frame dans la fenêtre glissante (buffer circulaire)."""
        if self._buf is None or self._buf.shape[1:] != frame.shape:
            self._buf = np.zeros((self.window,) + frame.shape, np.float32)
            self._nbuf = 0
        if self._nbuf < self.window:
            self._buf[self._nbuf] = frame
            self._nbuf += 1
        else:
            self._buf[:-1] = self._buf[1:]                 # décalage memcpy
            self._buf[-1] = frame
