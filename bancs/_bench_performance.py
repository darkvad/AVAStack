# -*- coding: utf-8 -*-
"""_bench_performance.py — MESURER LE COÛT DU PIPELINE ET SURVEILLER SA DÉRIVE.

POURQUOI CET OUTIL EXISTE (jalon 79) : les algorithmes du live sont corrects,
mais leur COÛT n'était mesuré nulle part. Constat du 29/09/2026 sur la machine
de dev (Core Ultra 5 125U, brute 3856x2180 = 8,4 Mpx) : `LiveStacker.add`
coûtait 325 ms par frame alors que le même calcul sans temporaires float64 en
coûte 51 ms — le coût n'était donc pas dans les maths mais dans les
ALLOCATIONS. Sans instrument, on ne peut ni le prouver, ni garantir qu'une
optimisation n'a rien cassé.

DEUX CHOSES, INDISSOCIABLES :
  (1) des TEMPS, par étape, comparés au run précédent (régression / gain) ;
  (2) des CONTRÔLES DE CORRECTION — l'empilement produit est comparé à une
      référence numpy ÉCRITE ICI, indépendante du code de l'application : une
      optimisation qui changerait les valeurs ÉCHOUE au banc, même si elle est
      plus rapide. C'est ce qui autorise à optimiser le cœur sans peur.

CE QUE LE BANC MESURE (jalon 79) : empilement kappa et winsorized (mono et
RVB), moyenne, composite multi-rôles, alignement ORB et triangles, détection
d'étoiles et seeing, redimensionnement, chaîne d'affichage STF (neutre, gamma,
saturation), les deux histogrammes.

USAGE (depuis la RACINE du dépôt, avec l'interpréteur du VENV) :
  .\\venv\\Scripts\\python.exe bancs\\_bench_performance.py
      -> prend les mesures, AFFICHE la comparaison au run précédent et ÉCRIT
         la référence (bancs/_bench_performance_ref.json)
  .\\venv\\Scripts\\python.exe bancs\\_bench_performance.py --verifier
      -> prend les mesures et n'écrit RIEN : dit seulement gain / régression
  .\\venv\\Scripts\\python.exe bancs\\_bench_performance.py --reel C:\\Astro\\test
      -> ajoute les mesures sur une VRAIE brute FITS du dossier (si présente)
  .\\venv\\Scripts\\python.exe bancs\\_bench_performance.py --rapide
      -> moins d'itérations (repérage rapide, chiffres plus bruités)

La référence est propre à UNE machine : elle porte le nom du processeur et les
versions lues — un run sur une autre machine n'écrase pas la comparaison, il
l'annonce (le GPU RTX se mesurera ainsi, sans toucher au code de l'appli).

LIRE LES CHIFFRES : un portable qui vient de travailler ralentit (chaleur,
limite de puissance). Les valeurs ABSOLUES d'un run isolé ne veulent donc rien
dire — ce qui compte, c'est la comparaison à la référence de la MÊME machine,
prise dans les mêmes conditions (le banc rejoue exactement la même séquence,
la même graine, le même nombre d'itérations). Chaque étape est retenue au
MINIMUM de ses itérations et l'écart entre deux runs est NORMALISÉ par une
calibration machine prise au début et à la fin (cf. `_calibrer`) : sans ces
deux précautions, deux runs du même code montraient déjà ±25 % d'écart, donc de
fausses régressions. Comparer deux passes : lancer le banc avant, puis après la
modification.

LIMITE CONNUE DE LA CALIBRATION (mesurée le 29/09/2026) : elle ne normalise que
les opérations BORNÉES PAR LA MÉMOIRE. Sur un portable freiné par la chaleur,
une mesure de CALCUL dérive toute seule à calibration identique — constaté :
`align_orb` 409 → 607 ms (+48 %) et `mesurer_seeing_apercu` 31 → 49 ms avec la
même calibration (7,5 ms). D'où la règle : comparer deux passes prises dans le
MÊME état (machine au repos quelques minutes), et ne croire que les gros
mouvements — les gains du jalon 79 se comptent en dizaines de pourcents.
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import glob
import json
import os
import platform
import sys
import time
from datetime import datetime

import numpy as np

try:                                     # sortie console : jamais de plantage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import cv2

import avastack                                            # noqa: E402
from avastack.images import load_image                      # noqa: E402
from avastack.processing import stars as _stars             # noqa: E402
from avastack.processing import veralux as _veralux         # noqa: E402
from avastack.processing.alignment import StarAligner       # noqa: E402
from avastack.processing.composition import CompositeStacker  # noqa: E402
from avastack.processing.display import DisplayProcessor    # noqa: E402
from avastack.processing.stacking import LiveStacker        # noqa: E402

# Le calcul des DEUX histogrammes vit dans l'application (`App._hist_canaux`,
# méthode STATIQUE) : on la mesure par le vrai code plutôt que par une copie
# qui pourrait diverger. L'import d'`avastack.ui.app` n'ouvre aucune fenêtre —
# s'il échoue (Tkinter absent d'un Python système), la seule mesure perdue est
# celle des histogrammes, et le banc le DIT.
try:
    import avastack.ui.app as _ui
    _hist_canaux = _ui.App._hist_canaux
except Exception:                                            # noqa: BLE001
    _hist_canaux = None

# --- Réglages du banc -------------------------------------------------------
TAILLE = (2180, 3856)          # (H, W) de la brute RÉELLE d'Alain (IMX571)
TAILLE_APERCU = (904, 1600)    # aperçu d'affichage (le seul que l'UI rend)
NB_FRAMES = 10                 # frames synthétiques de la séquence
GRAINE = 20260929              # graine fixe : la séquence est reproductible
K_KAPPA = 3.0                  # kappa du rejet (défaut de l'application)
WARMUP = 5                     # warmup (défaut de l'application)
FENETRE = 8                    # fenêtre winsorized (défaut si la config en a 8)

# Au-delà de ce facteur, l'écart entre deux runs est annoncé comme une
# RÉGRESSION (au-dessous de l'INVERSE, comme un gain). POURQUOI 25 % et pas
# 5 % : mesuré le 29/09/2026, deux runs STRICTEMENT IDENTIQUES de ce banc
# diffèrent de 10 à 20 % sur les petites étapes (le premier run, machine au
# repos, est le plus rapide : fragmentation du tas après un long banc,
# fréquence du processeur) — la calibration seule ne suffit pas à l'effacer.
# Un vrai gain du chantier jalon 79 se compte en DIZAINES de pourcents
# (winsorized ×2,5 ; `add` ×6) : il passera donc très au-dessus du bruit.
SEUIL_DERIVE = 25.0            # %

FICHIER_REF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "_bench_performance_ref.json")

# --- Mesures ---------------------------------------------------------------
MESURES = {}                   # nom -> ms (MINIMUM des itérations)
CONTROLES = {}                 # nom -> écart mesuré (doit rester ~0)
CALIBRATIONS = []              # ms de l'opération de référence (début / fin)


def _calibrer(iterations=30):
    """Vitesse COURANTE de la machine : 30 fois `a + a` sur un tableau float32
    de 8,4 Mpx (opération purement bornée par la mémoire, ~9 ms). Pourquoi une
    calibration ? Un portable RALENTIT quand il chauffe : deux runs du MÊME code
    peuvent donc différer de 10-25 % sur les petites étapes, ce qui ferait
    crier « régression » à tort (constat du 29/09/2026 : six fausses
    régressions sur un run à blanc). En rapportant chaque étape à cette mesure
    de référence, prise au DÉBUT et à la FIN du banc, l'effet de la chaleur est
    retiré et le seuil redevient fiable."""
    a = np.ones((TAILLE[0], TAILLE[1]), np.float32)
    _calibrer.a = a if getattr(_calibrer, "a", None) is None else _calibrer.a
    durees = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        _calibrer.a + _calibrer.a
        durees.append(time.perf_counter() - t0)
    mini = min(durees) * 1000.0
    CALIBRATIONS.append(round(mini, 3))
    return mini


def chrono(nom, fn, iterations):
    """Chronomètre `fn` (1 appel de RODAGE non compté, puis `iterations`) et
    enregistre le **MINIMUM** en ms sous `nom` — c'est la mesure ROBUSTE :
    la moyenne d'un portable est polluée par la chaleur, les autres processus
    et le ramasse-miettes, alors que le minimum représente le coût réel de
    l'étape (le meilleur passage est celui qu'aucune interférence n'a touché).
    La moyenne est AFFICHÉE à côté, pour que le bruit du run soit VISIBLE.
    Renvoie la sortie du dernier appel (les contrôles s'en servent)."""
    fn()                                     # rodage (caches, threads…)
    durees = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        out = fn()
        durees.append(time.perf_counter() - t0)
    mini = min(durees) * 1000.0
    moy = sum(durees) / float(len(durees)) * 1000.0
    MESURES[nom] = round(mini, 3)
    print(f"    {nom:38s} {mini:9.1f} ms (moyenne {moy:8.1f})", flush=True)
    return out


# --- Machine et référence --------------------------------------------------
def _processeur():
    """Nom du processeur, best effort et SANS chemin de machine de dev codé en
    dur (le banc part dans le dépôt) : variable d'environnement Windows, sinon
    /proc/cpuinfo (Linux), sinon platform.processor()."""
    id_w = os.environ.get("PROCESSOR_IDENTIFIER")
    if id_w:
        return id_w.strip()
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
            for ligne in f:
                if ligne.lower().startswith("model name"):
                    return ligne.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or platform.machine() or "inconnu"


def _empreinte():
    """Identité du run : machine + versions. La comparaison ne vaut qu'entre
    deux runs de MÊME empreinte (sinon elle est annoncée comme telle)."""
    return {
        "processeur": _processeur(),
        "plateforme": platform.platform(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "avastack": avastack.AVASTACK_VERSION,
        "taille": list(TAILLE),
    }


def _lire_reference():
    try:
        with open(FICHIER_REF, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _ecrire_reference(empreinte, note):
    charge = {"empreinte": empreinte, "date": datetime.now().isoformat(
        timespec="seconds"), "note": note, "calibration": CALIBRATIONS,
        "mesures": MESURES, "controles": CONTROLES}
    try:
        with open(FICHIER_REF, "w", encoding="utf-8") as f:
            json.dump(charge, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"\n  référence écrite : {os.path.basename(FICHIER_REF)}")
    except Exception as exc:
        print(f"\n  référence NON écrite ({exc}) — non bloquant")
    return charge


def _calibration(charge):
    """Facteur de vitesse d'un run conservé : moyenne des calibrations prises
    au début et à la fin (None si la référence est antérieure à la
    calibration — la comparaison retombe alors sur les chiffres bruts)."""
    cal = [c for c in ((charge or {}).get("calibration") or []) if c]
    return (sum(cal) / float(len(cal))) if cal else None


def _comparer(ancienne, empreinte):
    """Compare les mesures du run à la référence (même machine) : dit le gain
    ou la régression, étape par étape. L'écart RETENU est NORMALISÉ par la
    calibration machine (cf. `_calibrer`) : sans elle, la chaleur du portable
    produirait de fausses régressions. Ne modifie RIEN."""
    if not ancienne:
        print("\n  (aucune référence : premier run sur cette machine)")
        return
    emp = ancienne.get("empreinte", {})
    for cle in ("processeur", "numpy", "opencv"):
        if emp.get(cle) and emp.get(cle) != empreinte.get(cle):
            print(f"\n  /!\\ référence d'une AUTRE configuration ({cle} : "
                  f"« {emp.get(cle)} » contre « {empreinte.get(cle)} ») — "
                  "comparaison donnée à titre indicatif")
            break
    cal_av, cal_ap = _calibration(ancienne), _calibration(
        {"calibration": CALIBRATIONS})
    if cal_av and cal_ap:
        print(f"\n  calibration machine : {cal_av:.1f} ms → {cal_ap:.1f} ms "
              f"({(cal_ap / cal_av - 1) * 100:+.1f} %) — les écarts ci-dessous "
              "sont NORMALISÉS par elle")
    else:
        print("\n  (référence sans calibration : écarts BRUTS, à lire avec "
              "prudence)")
    print(f"\n  comparaison à la référence du {ancienne.get('date', '?')} :")
    print(f"    {'étape':36s} {'avant':>9s} {'après':>9s} "
          f"{'brut':>8s} {'normalisé':>10s}")
    pires = []
    for nom, avant in sorted(ancienne.get("mesures", {}).items()):
        apres = MESURES.get(nom)
        if apres is None or not avant:
            continue
        brut = (apres - avant) / float(avant) * 100.0
        if cal_av and cal_ap:
            norm = ((apres / cal_ap) / (avant / cal_av) - 1.0) * 100.0
        else:
            norm = brut
        if norm >= SEUIL_DERIVE:
            verdict = "RÉGRESSION"
            pires.append((nom, norm))
        elif norm <= -SEUIL_DERIVE:
            verdict = "gain"
        else:
            verdict = "="
        print(f"    {nom:36s} {avant:8.1f} ms {apres:8.1f} ms "
              f"{brut:+7.1f} % {norm:+9.1f} % {verdict}")
    for nom in MESURES:
        if nom not in ancienne.get("mesures", {}):
            print(f"    {nom:36s} {'—':>9s} {MESURES[nom]:8.1f} ms "
                  "(étape NOUVELLE)")
    if pires:
        print(f"\n  /!\\ RÉGRESSIONS (> +{int(SEUIL_DERIVE)} % après "
              "normalisation) :")
        for nom, norm in pires:
            print(f"      {nom} : {norm:+.1f} %")
    else:
        print(f"\n  aucune régression de plus de +{int(SEUIL_DERIVE)} % "
              "(après normalisation)")


# --- Séquence d'essai (déterministe) ---------------------------------------
def _psf():
    """Petit noyau gaussien 7x7 d'une étoile (sigma 0,9 px), normalisé."""
    y, x = np.mgrid[-3:4, -3:4]
    g = np.exp(-(x * x + y * y) / (2.0 * 0.9 ** 2)).astype(np.float32)
    return g / g.sum()


def _fond_synthetique(h, w, graine):
    """Fond commun d'une séquence : bruit de fond + étoiles réparties
    aléatoirement (densité ~ 1 étoile pour 38 000 px, amplitudes variées)."""
    rng = np.random.default_rng(graine)
    img = np.full((h, w), 0.0012, np.float32)
    img += rng.normal(0.0, 0.00035, (h, w)).astype(np.float32)
    psf = _psf()
    n = max(120, int(h * w / 38000))
    ys = rng.integers(4, h - 4, n)
    xs = rng.integers(4, w - 4, n)
    amp = rng.uniform(0.04, 0.9, n).astype(np.float32)
    for y, x, a in zip(ys, xs, amp):
        img[y - 3:y + 4, x - 3:x + 4] += a * psf
    return img


def _sequence(nb, taille, graine):
    """`nb` frames float32 [0..1] : MÊME fond (étoiles), DÉRIVÉ de quelques
    pixels d'une frame à l'autre (l'alignement a donc du travail) et bruité
    indépendamment. Reproductible : tout part d'une graine fixe."""
    h, w = taille
    fond = _fond_synthetique(h, w, graine)
    rng = np.random.default_rng(graine + 1)
    frames = []
    for i in range(nb):
        M = np.float32([[1.0, 0.0, 1.7 * i], [0.0, 1.0, -0.9 * i]])
        f = cv2.warpAffine(fond, M, (w, h), flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_REFLECT)
        f = f + rng.normal(0.0, 0.0005, (h, w)).astype(np.float32)
        frames.append(np.clip(f, 0.0, 1.0))
    return frames


def _rbg(mono):
    """Image couleur d'essai dérivée d'une image mono (canaux légèrement
    différents : la chaîne couleur a quelque chose à mesurer)."""
    return np.ascontiguousarray(
        np.stack([mono * 0.92, mono, mono * 1.08], axis=-1)).astype(np.float32)


# --- Références numériques INDÉPENDANTES de l'application -------------------
def _ref_kappa(frames, k=K_KAPPA, warmup=WARMUP):
    """Réimplémentation de l'accumulation kappa de `LiveStacker` (relue dans
    stacking.py le 29/09/2026, DTYPES COMPRIS) : la frame courante est pesée
    contre les statistiques CUMULÉES AVANT son ajout ; warmup à poids 1.
    → (moyenne float32, nombre de rejets)."""
    forme = frames[0].shape
    somme = np.zeros(forme, np.float64)
    carres = np.zeros(forme, np.float64)
    poids = np.zeros(forme, np.float64)
    n, rejets = 0, 0
    for f in frames:
        f64 = f.astype(np.float64)
        if n >= warmup:
            moy = somme / np.maximum(poids, 1e-9)
            var = np.maximum(carres / np.maximum(poids, 1e-9) - moy * moy,
                             1e-12)
            w = np.where(np.abs(f64 - moy) > k * np.sqrt(var), 0.0, 1.0)
            rejets += int((w == 0).sum())
        else:
            w = 1.0
        somme += f64 * w
        carres += (f64 * f64) * w
        poids += w
        n += 1
    return (somme / np.maximum(poids, 1e-9)).astype(np.float32), rejets


def _ref_winsorized(frames, k=K_KAPPA, warmup=WARMUP, window=FENETRE):
    """Réimplémentation du rejet winsorized (médiane + MAD de la fenêtre
    glissante, REJEU DU WARMUP compris) — relue dans stacking.py le
    29/09/2026. Les dtypes sont ceux du code : tampon float32, médianes et
    écarts calculés sur le tampon, accumulations en float64. → (moyenne, rejets)."""
    forme = frames[0].shape
    buf = np.zeros((window,) + forme, np.float32)
    nbuf, n, rejets = 0, 0, 0
    rejeu_fait = False
    somme = np.zeros(forme, np.float64)
    carres = np.zeros(forme, np.float64)
    poids = np.zeros(forme, np.float64)
    for f in frames:
        if nbuf < window:                      # insertion dans la fenêtre
            buf[nbuf] = f
            nbuf += 1
        else:
            buf[:-1] = buf[1:]
            buf[-1] = f
        w = 1.0
        if not (nbuf < min(warmup, window) or nbuf < 2):
            blk = buf[:nbuf]
            med = np.median(blk, axis=0)
            mad = np.median(np.abs(blk - med), axis=0)
            sigma = np.maximum(1.4826 * mad, 1e-6)
            hors = np.abs(blk - med) > k * sigma
            rejeu = (not rejeu_fait and nbuf == window and n + 1 == nbuf)
            if rejeu:                          # rejeu : AFFECTATION (comme le code)
                passe = hors[:-1]
                somme = (blk[:-1] * ~passe).sum(axis=0).astype(np.float64)
                carres = (blk[:-1] * blk[:-1] * ~passe).sum(axis=0).astype(
                    np.float64)
                poids = (~passe).sum(axis=0).astype(np.float64)
                rejets = int(passe.sum())
                rejeu_fait = True
            w = np.where(hors[-1], 0.0, 1.0)
            rejets += int((w == 0).sum())
        f64 = f.astype(np.float64)
        somme += f64 * w
        carres += (f64 * f64) * w
        poids += w
        n += 1
    return (somme / np.maximum(poids, 1e-9)).astype(np.float32), rejets


# --- Sections de mesure -----------------------------------------------------
def _sec_coeur(frames, it):
    h, w = frames[0].shape
    it = max(it, 6)                  # plus d'itérations : le minimum est plus
                                     # stable (mesuré : ±25 % à 4 itérations)
    print(f"\n[2] CŒUR D'EMPILEMENT — mono {w}x{h} "
          f"({h * w / 1e6:.1f} Mpx), k={K_KAPPA}, fenêtre {FENETRE}")
    sk = LiveStacker((h, w), k=K_KAPPA, method="kappa", window=FENETRE)
    chrono("add_kappa_warmup", lambda: sk.add(frames[0]), it)
    for f in frames[1:WARMUP]:                 # jusqu'à la fin du warmup
        sk.add(f)
    chrono("add_kappa_etabli", lambda: sk.add(frames[0]), it)
    chrono("mean_kappa_etabli", lambda: sk.mean(), it)

    skw = LiveStacker((h, w), k=K_KAPPA, method="winsorized", window=FENETRE)
    for f in frames[:FENETRE]:                 # on remplit la fenêtre
        skw.add(f)
    chrono("add_winsorized_etabli", lambda: skw.add(frames[0]), it)
    chrono("mean_winsorized", lambda: skw.mean(), it)

    rgb = _rbg(frames[0])
    srgb = LiveStacker(rgb.shape, k=K_KAPPA, method="kappa", window=FENETRE)
    for _ in range(WARMUP):                    # remplissage (non mesuré)
        srgb.add(rgb)
    chrono("add_kappa_rgb", lambda: srgb.add(rgb), max(2, it // 2))


def _sec_composite(frames, it):
    print("\n[3] COMPOSITE MULTI-RÔLES (HOO, 2 rôles x 5 frames)")
    comp = CompositeStacker("HOO", k=K_KAPPA, method="kappa", window=FENETRE)
    for role in ("Ha", "O3"):
        for f in frames[:WARMUP]:
            comp.add(f, role)

    def _vider_memoires():
        """Force le calcul COMPLET (mémo du composite, bornes figées, moyennes
        de rôle). La mesure SANS vidage est celle d'un GESTE sur un réglage de
        couleur : le composite brut est alors réutilisé au lieu d'être
        réassemblé (c'est tout l'objet du jalon 79)."""
        comp._memo_compo = None
        comp._bornes_cache = None
        for s in comp.stackers.values():
            s._memo_moy = None

    chrono("composite_mean_complet",
           lambda: (_vider_memoires(), comp.mean_avec_canaux()), it)
    chrono("composite_mean_geste", lambda: comp.mean_avec_canaux(), it)
    chrono("composite_moyennes_complet",
           lambda: (_vider_memoires(), comp.moyennes()), it)
    chrono("composite_moyennes_geste", lambda: comp.moyennes(), it)


def _sec_alignement(frames, it):
    print("\n[4] ALIGNEMENT (brute dérivée de 15 px)")
    al = StarAligner()
    al.set_reference(frames[0])
    chrono("align_orb", lambda: al.compute(frames[-1]), it)
    alt = StarAligner()
    alt.triangles_seuls = True
    alt.set_reference(frames[0])
    chrono("align_triangles_seuls", lambda: alt.compute(frames[-1]), it)


def _sec_etoiles(frames, apercu, it):
    it = max(it, 10)                 # étapes légères : plus d'itérations
    print("\n[5] MESURES D'ÉTOILES ET SEEING")
    chrono("detecter_etoiles_pleine_res",
           lambda: _stars.detecter_positions(frames[0], max_etoiles=60), it)
    chrono("detecter_etoiles_apercu",
           lambda: _stars.detecter_positions(apercu), it * 2)
    chrono("mesurer_seeing_apercu",
           lambda: _stars.mesurer_seeing(apercu), it * 2)


def _sec_affichage(frames, apercu, it):
    it = max(it, 10)                 # étapes légères : plus d'itérations
    print(f"\n[6] AFFICHAGE — aperçu {apercu.shape[1]}x{apercu.shape[0]}")
    d = DisplayProcessor()
    p_rgb = _rbg(apercu)
    d.process(p_rgb, live=False)
    # `live=True` = ARRIVÉE D'UNE FRAME : le lissage temporel des stats avance,
    # donc rien n'est mémoïsable — c'est le coût du rendu COMPLET.
    chrono("process_stf_rgb_complet", lambda: d.process(p_rgb, live=True), it)
    # `live=False` = GESTE sur un réglage (rafraîchissement de l'aperçu) :
    # c'est le chemin que le jalon 79 rend instantané.
    chrono("process_stf_rgb_geste", lambda: d.process(p_rgb, live=False), it)
    d.gamma = 1.5                              # réglage APRÈS étirement
    chrono("process_gamma_rgb", lambda: d.process(p_rgb, live=False), it)
    d.gamma = 1.0
    d.saturation = 1.6
    d.sat_canaux = (1.3, 1.0, 1.0)
    chrono("process_saturation_rgb", lambda: d.process(p_rgb, live=False), it)
    d.saturation, d.sat_canaux = 1.0, (1.0, 1.0, 1.0)
    dm = DisplayProcessor()
    dm.process(apercu, live=False)
    chrono("process_stf_mono", lambda: dm.process(apercu, live=False), it)
    h, w = frames[0].shape
    ech = min(1.0, 1600.0 / max(h, w))
    chrono("resize_mono_pleine_res",
           lambda: cv2.resize(frames[0], None, fx=ech, fy=ech,
                              interpolation=cv2.INTER_AREA), it)
    rgb_plein = _rbg(frames[0])                # construit UNE fois (hors mesure)
    chrono("resize_rgb_pleine_res",
           lambda: cv2.resize(rgb_plein,
                              (1600, int(round(h * 1600.0 / w))),
                              interpolation=cv2.INTER_AREA), max(2, it // 2))
    if _hist_canaux is None:                   # nécessite avastack.ui.app
        print("    histogrammes_deux_bandes : NON MESURÉ (avastack.ui.app non "
              "importable ici — sans incidence sur le reste)")
    else:
        # Le cas RÉEL d'une caméra couleur : les deux bandes portent TROIS
        # canaux chacune (c'est là que le coût se voit — mesuré ~59 ms contre
        # ~15 ms en mono).
        sortie_rgb = getattr(d, "dernier_brut_niveaux", None)
        if sortie_rgb is not None:
            chrono("histogrammes_deux_bandes_rgb",
                   lambda: (_hist_canaux(p_rgb),
                            _hist_canaux(sortie_rgb, plage=(0.0, 1.0))), it)
    if _veralux.moteur_disponible():
        chrono("veralux_logd_apercu",
               lambda: _veralux.etirer(apercu, mode=_veralux.MODE_LOG_D,
                                       log_d=2.0)[0], it)
    else:
        print("    veralux_logd_apercu : NON MESURÉ (moteur tiers absent)")


def _verdict(titre, condition, detail):
    print(f"    [{'OK ' if condition else 'ÉCHEC'}] {titre} — {detail}")
    return bool(condition)


def _sec_controles(frames):
    """LES CONTRÔLES QUI AUTORISENT À OPTIMISER : l'accumulation produite par
    l'application est comparée à la référence numpy écrite DANS CE BANC. Tant
    qu'ils passent, une optimisation de performance ne peut pas avoir changé
    l'image empilée — c'est le garde-fou de tout le chantier du jalon 79."""
    print("\n[7] CONTRÔLES DE CORRECTION (l'empilement doit rester IDENTIQUE)")
    h, w = frames[0].shape
    ok = True

    attendu, rejets = _ref_kappa(frames[:6])
    sk = LiveStacker((h, w), k=K_KAPPA, method="kappa", window=FENETRE)
    for f in frames[:6]:
        sk.add(f)
    ecart = float(np.max(np.abs(sk.mean(recadre=False) - attendu)))
    CONTROLES["kappa_ecart_max"] = ecart
    CONTROLES["kappa_rejets_ecart"] = abs(int(sk.rejected_total) - rejets)
    ok &= _verdict("kappa : moyenne identique à la référence", ecart <= 1e-6,
                   f"écart max {ecart:.3g}, rejets {sk.rejected_total} / "
                   f"{rejets}")

    attendu, rejets = _ref_winsorized(frames[:FENETRE])
    skw = LiveStacker((h, w), k=K_KAPPA, method="winsorized", window=FENETRE)
    for f in frames[:FENETRE]:
        skw.add(f)
    ecart = float(np.max(np.abs(skw.mean(recadre=False) - attendu)))
    CONTROLES["winsorized_ecart_max"] = ecart
    CONTROLES["winsorized_rejets_ecart"] = abs(int(skw.rejected_total) - rejets)
    ok &= _verdict("winsorized : moyenne identique à la référence",
                   ecart <= 1e-6,
                   f"écart max {ecart:.3g}, rejets {skw.rejected_total} / "
                   f"{rejets}")

    a, b = skw.mean(), skw.mean()
    identique = (a is not None and b is not None and a.shape == b.shape
                 and float(np.max(np.abs(a - b))) == 0.0)
    CONTROLES["mean_appels_successifs_identiques"] = 0.0 if identique else 1.0
    ok &= _verdict("mean() appelée deux fois : résultat identique", identique,
                   "aucun pompage possible entre deux appels sans nouvelle "
                   "frame")
    return ok


def _sec_memoire(apercu):
    """CONTRÔLES DE LA MÉMOIRE DU MOTEUR (jalon 79) : elle ne doit RIEN changer
    au rendu, et elle doit être invalidée par tout ce qui change l'image."""
    print("\n[7 bis] MÉMOIRE DU MOTEUR D'ÉTIREMENT (elle ne change rien)")
    d = DisplayProcessor()
    img_a = _rbg(apercu)
    ok = True

    d._memo_moteur = None                    # mémo froide → recalcul complet
    r_calcul = d.process(img_a, live=False)
    r_memo = d.process(img_a, live=False)    # servi par la mémo
    ecart = int(np.max(np.abs(r_calcul.astype(np.int16)
                              - r_memo.astype(np.int16))))
    CONTROLES["memo_rendu_ecart"] = ecart
    ok &= _verdict("rendu mémoïsé identique au rendu recalculé", ecart == 0,
                   f"écart max {ecart} niveau(x) sur 255")

    brut1 = None if d.dernier_brut_niveaux is None \
        else d.dernier_brut_niveaux.copy()
    d.gamma, d.saturation = 1.6, 1.4         # réglages d'APRÈS étirement
    d.sat_canaux = (1.2, 1.0, 0.9)
    d.process(img_a, live=False)
    brut2 = d.dernier_brut_niveaux
    identique = (brut1 is not None and brut2 is not None
                 and np.array_equal(brut1, brut2))
    CONTROLES["memo_moteur_invariance_apres_etirement"] = 0 if identique else 1
    ok &= _verdict("gamma/saturations ne changent PAS la sortie du moteur",
                   identique,
                   "c'est la propriété qui justifie toute la passe C-bis")
    d.gamma, d.saturation, d.sat_canaux = 1.0, 1.0, (1.0, 1.0, 1.0)

    img_b = np.ascontiguousarray(_rbg(apercu) * 0.6 + 0.05)   # NOUVELLE image
    r_b = d.process(img_b, live=False)
    invalide = not np.array_equal(r_memo, r_b)
    CONTROLES["memo_invalidee_par_nouvelle_image"] = 0 if invalide else 1
    ok &= _verdict("une nouvelle image invalide la mémo", invalide,
                   "aucun rendu périmé ne peut être resservi")
    return ok


def _sec_memo_composite(frames):
    """CONTRÔLES DE LA MÉMOIRE DU COMPOSITE (jalon 79) : le composite brut
    mémoïsé doit être IDENTIQUE au composite recalculé, ne PAS dépendre des
    corrections de couleur (c'est ce qui rend un geste instantané) et être
    invalidé par toute nouvelle frame."""
    print("\n[7 ter] MÉMOIRE DU COMPOSITE (mode composition)")
    c = CompositeStacker("HOO", k=K_KAPPA, method="kappa", window=FENETRE)
    for role in ("Ha", "O3"):
        for f in frames[:3]:
            c.add(f, role)
    ok = True
    comp1, canaux1 = c.mean_avec_canaux(corrections=False)
    if comp1 is None:
        return _verdict("composite disponible", False, "banc non concluant")
    comp2, canaux2 = c.mean_avec_canaux(corrections=False)   # servi par la mémo
    ecart = float(np.max(np.abs(comp1 - comp2)))
    CONTROLES["compo_memo_ecart"] = ecart
    ok &= _verdict("composite mémoïsé identique au composite calculé",
                   ecart == 0.0, f"écart max {ecart:.3g}")

    ec = float(np.max(np.abs(canaux1["Ha"] - canaux2["Ha"])))
    meme = canaux1["Ha"] is canaux2["Ha"]
    CONTROLES["compo_memo_couches_ecart"] = ec
    ok &= _verdict("couches identiques ET réutilisées (moyenne mémoïsée)",
                   ec == 0.0 and meme,
                   f"écart max {ec:.3g}, même objet : {meme}")

    c.gains = {"R": 1.1, "G": 1.0, "B": 0.9}       # réglage APRÈS composition
    comp3, _ = c.mean_avec_canaux(corrections=False)
    e3 = float(np.max(np.abs(comp1 - comp3)))
    CONTROLES["compo_brut_independant_des_gains"] = e3
    ok &= _verdict("le composite BRUT ne dépend pas des gains", e3 == 0.0,
                   f"écart max {e3:.3g} — un geste de gain réutilise "
                   "l'assemblage")

    c.add(frames[3], "Ha")                        # NOUVELLE frame
    comp4, _ = c.mean_avec_canaux(corrections=False)
    invalide = not np.array_equal(comp3, comp4)
    CONTROLES["compo_memo_invalidee_par_frame"] = 0 if invalide else 1
    ok &= _verdict("une nouvelle frame invalide la mémoire du composite",
                   invalide, "aucun composite périmé ne peut être affiché")
    return ok


def _sec_reel(dossier, it):
    """Mesures sur une VRAIE image du dossier (facultatif, `--reel`) : la
    densité d'étoiles et le rapport signal/bruit réels ne se devinent pas."""
    print(f"\n[8] IMAGE RÉELLE ({dossier})")
    if not dossier or not os.path.isdir(dossier):
        print("    dossier absent : section passée")
        return
    chemins = []
    for motif in ("*.fit", "*.fits", "*.fts", "*.FIT", "*.FITS"):
        chemins += glob.glob(os.path.join(dossier, motif))
    if not chemins:                            # repli : TIFF / PNG
        for motif in ("*.tif", "*.tiff", "*.TIF", "*.TIFF", "*.png", "*.PNG"):
            chemins += glob.glob(os.path.join(dossier, motif))
    if not chemins:
        print("    aucune image lisible : section passée")
        return
    chemin = sorted(set(chemins))[0]
    try:
        img = np.asarray(load_image(chemin), np.float32)
    except Exception as exc:
        print(f"    lecture impossible ({exc}) : section passée")
        return
    mono = img if img.ndim == 2 else img[..., 1]
    print(f"    {os.path.basename(chemin)} {img.shape} — canal "
          f"{mono.shape[1]}x{mono.shape[0]}")
    sk = LiveStacker(mono.shape, k=K_KAPPA, method="kappa", window=FENETRE)
    for _ in range(WARMUP):
        sk.add(mono)
    chrono("reel_add_kappa", lambda: sk.add(mono), it)
    chrono("reel_detecter_etoiles",
           lambda: _stars.detecter_positions(mono, max_etoiles=60), it)
    al = StarAligner()
    al.set_reference(mono)
    chrono("reel_align_orb", lambda: al.compute(mono), it)


# --- Programme --------------------------------------------------------------
def _argument(nom, defaut=None):
    """Valeur d'une option `--nom valeur` (sans dépendance : le banc doit
    rester lançable partout)."""
    if nom in sys.argv:
        i = sys.argv.index(nom)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return defaut


def main():
    rapide = "--rapide" in sys.argv
    verifier = "--verifier" in sys.argv          # n'écrit AUCUNE référence
    dossier_reel = _argument("--reel")
    it = 2 if rapide else 4                      # itérations des étapes lourdes
    empreinte = _empreinte()

    print("=" * 78)
    print("BANC DE PERFORMANCE — AVAStack " + empreinte["avastack"])
    print("=" * 78)
    print(f"  machine   : {empreinte['processeur']}")
    print(f"              {empreinte['plateforme']}")
    print(f"  logiciels : Python {empreinte['python']} · numpy "
          f"{empreinte['numpy']} · OpenCV {empreinte['opencv']}")
    print(f"  réglages  : {TAILLE[1]}x{TAILLE[0]} "
          f"({TAILLE[0] * TAILLE[1] / 1e6:.1f} Mpx), {NB_FRAMES} frames, "
          f"k={K_KAPPA}, warmup {WARMUP}, fenêtre {FENETRE}")
    print(f"  (chaque étape : 1 appel de rodage puis le MINIMUM de {it} "
          "itérations — un chiffre isolé ne dit rien)")

    print("\n[1] SÉQUENCE D'ESSAI (déterministe)")
    t0 = time.perf_counter()
    frames = _sequence(NB_FRAMES, TAILLE, GRAINE)
    apercu = cv2.resize(frames[0], (TAILLE_APERCU[1], TAILLE_APERCU[0]),
                        interpolation=cv2.INTER_AREA)
    print(f"    {NB_FRAMES} frames {TAILLE[1]}x{TAILLE[0]} + aperçu "
          f"{apercu.shape[1]}x{apercu.shape[0]} fabriqués en "
          f"{time.perf_counter() - t0:.1f} s")

    cal = _calibrer()
    print(f"    calibration machine AVANT mesures : {cal:.1f} ms (opération de "
          "référence, cf. l'en-tête du banc)")
    _sec_coeur(frames, it)
    _sec_composite(frames, it)
    _sec_alignement(frames, it)
    _sec_etoiles(frames, apercu, it)
    _sec_affichage(frames, apercu, it)
    ok = _sec_controles(frames)
    ok &= _sec_memoire(apercu)
    ok &= _sec_memo_composite(frames)
    if dossier_reel:
        _sec_reel(dossier_reel, it)
    cal2 = _calibrer()
    print(f"\n  calibration machine APRÈS mesures : {cal2:.1f} ms")

    _comparer(_lire_reference(), empreinte)
    if not verifier:
        _ecrire_reference(empreinte,
                          "référence du jalon 79 (banc de performance)")
    print("\n  " + ("CONTRÔLES DE CORRECTION : TOUS VERTS" if ok
                    else "CONTRÔLES DE CORRECTION : ÉCHEC — voir [7]"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
