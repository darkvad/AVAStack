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
