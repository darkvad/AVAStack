# -*- coding: utf-8 -*-
"""MESURE MÉMOIRE — répartition des octets d'un empilement 5 canaux (Phase 1).

POURQUOI (21/10/2026, branche `OptimisationUI`, v2.98.4). Après la Phase 1
(rendu hors fil Tk, `ui_tick` 456,5 s → 18,6 s), le sujet suivant est la
**mémoire** : `perf-7` annonce `stackers_mo` **2 935,7 Mo** pour un RSS de
**4 459 Mo** pendant le run (pic 4 564). Avant de toucher au moindre dtype — ce
qui CHANGERAIT l'image —, il faut savoir OÙ sont ces octets. C'est exactement le
protocole d'`AVANCEMENT.md` :

  ① partir de `bancs/_mesure_memoire.py` (RSS sans psutil) et de
    `perf.taille_tableaux()` (déjà utilisée par la jauge `stackers_*`) ;
  ② inventorier les postes RÉELS : accumulateurs du `LiveStacker`, un stacker
    par canal (`CompositeStacker`), fenêtre glissante, tampons de travail,
    moyennes et composite mémoïsés ;
  ③ produire un tableau **dtype + forme + octets** par poste, projeté à la
    géométrie RÉELLE du run (en-tête FITS), et le RÉCONCILIER avec le chiffre
    de la jauge puis avec le RSS (écart chiffré, jamais « à peu près ») ;
  ④ chiffrer ensuite seulement le levier float32 — sans l'appliquer.

CE QUE CET OUTIL NE FAIT PAS — et c'est volontaire
  - il ne modifie AUCUN fichier de l'application et ne convertit AUCUN
    tableau : **aucun pixel ne change**. Les chiffres « float32 » de la
    section [5] sont une projection arithmétique, pas une modification ;
  - il n'ouvre aucune image du run (seul l'EN-TÊTE FITS est lu, sur le
    partage, pour connaître la géométrie) ;
  - il ne remplace pas une mesure en réel : le graphe d'objets est reconstruit
    avec les MÊMES classes et les MÊMES réglages (`config.json` du run), sur
    une géométrie RÉDUITE, puis projeté (toutes les allocations d'un stacker
    sont des tableaux PLEINE FRAME ou des vues recadrées — la projection est
    linéaire en pixels, et l'écart résiduel est affiché, pas masqué).

USAGE
  python bancs/_mesure_memoire_stackers.py
  python bancs/_mesure_memoire_stackers.py --geometrie 2180x3856
  python bancs/_mesure_memoire_stackers.py --sans-allocation   # rien n'est alloué
  python bancs/_mesure_memoire_stackers.py --sans-rendu        # [3 bis] sautée

ENVELOPPE MÉMOIRE (21/10/2026) — mesurer le MINIMUM et le MAXIMUM
  python bancs/_mesure_memoire_stackers.py --roles L --maitres 2
  python bancs/_mesure_memoire_stackers.py --roles L,R,G,B,Ha --maitres 10
  `--roles` (1 rôle = le chemin MONO/OSC, sans composition : un `LiveStacker`
  nu, exactement comme `core/worker.py` hors mode composition) et `--maitres N`
  (N maîtres de calibration dark/flat, float32 PLEINE FRAME, gardés en mémoire
  toute la session) servent à CHIFFRER l'enveloppe au lieu de l'estimer. Le
  reste du protocole est inchangé ; aucun fichier de l'application n'est touché.

LA SECTION [3 bis] mesure le **Go inexpliqué** : elle instancie la VRAIE classe
`DisplayProcessor`, aux réglages du run, et fait tourner un rendu VeraLux
pleine résolution (~2 s, ~1,5 Go de pointe) pour inventorier ce que la chaîne
d'affichage GARDE (couches de composition, image soumise, copie de job,
résultat étiré, brut niveaux) — puis le compare au pic RSS.
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import gc
import json
import os
import sys
import time

import numpy as np

from avastack import perf
from avastack.processing.composition import CompositeStacker

if hasattr(sys.stdout, "reconfigure"):      # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MO = 1024.0 * 1024.0

# --- Géométrie RÉELLE du run `perf-7` (en-tête FITS des brutes M33 QHY) ------
# Mesurée sur le partage le 21/10/2026 : NAXIS1=3856, NAXIS2=2180 (IMX585 mono,
# « Full Resolution/1x1 »). Surchargeable par --geometrie, ou relue sur le
# premier FITS de la config si le partage répond (jamais d'échec bloquant).
GEOMETRIE_REEL = (2180, 3856)       # (hauteur, largeur)
# Réglages du run (config.json figé après `perf-7`) : 5 rôles, winsorized 4.
COMPOSITION = "LRGB+Ha"
ROLES = ("L", "R", "G", "B", "Ha")
METHODE = "winsorized"
FENETRE = 4
KAPPA = 3.0
# Nombre de CANAUX d'une brute hors composition (`--canaux`) : 1 = MONO (brute
# 2D), 3 = OSC (brute débayerisée). N'a d'effet qu'avec UN SEUL rôle.
CANAUX = 1
# Base applicative au repos (Tk + OpenCV + astropy + caches), MESURÉE le
# 20/10/2026 par `bancs/_mesure_memoire.py` : 148 Mio (pic 259). Sert à retirer
# du hors-stackers la part qui n'appartient à aucune image — sans elle, tout
# écart deviendrait « inexpliqué » par construction.
BASE_APP_REPOS_MO = 148.0


# --------------------------------------------------------------- RSS du process
def mem_mo():
    """(RSS, pic RSS) du processus en Mo — natif, SANS psutil (cf. `_mesure_memoire`).

    Windows : `K32GetProcessMemoryInfo`. Ailleurs : `/proc/self/status` (Linux)
    ou `resource.getrusage` (macOS). Zéro si la sonde manque — jamais une
    exception (la cible est multiplateforme).
    """
    if sys.platform.startswith("win"):
        import ctypes
        import ctypes.wintypes as wt

        class _PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wt.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [wt.HANDLE,
                                                ctypes.POINTER(_PMC),
                                                wt.DWORD]
        k32.K32GetProcessMemoryInfo.restype = wt.BOOL
        p = _PMC()
        p.cb = ctypes.sizeof(_PMC)
        if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(),
                                           ctypes.byref(p), p.cb):
            return 0.0, 0.0
        return (p.WorkingSetSize / MO, p.PeakWorkingSetSize / MO)
    try:
        with open("/proc/self/status", "r", encoding="ascii",
                  errors="ignore") as f:
            for ligne in f:
                if ligne.startswith("VmRSS:"):
                    mo = int(ligne.split()[1]) / 1024.0
                    return mo, mo
    except OSError:
        pass
    try:
        import resource
        u = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        mo = u / MO if sys.platform == "darwin" else u / 1024.0
        return mo, mo
    except Exception:                     # noqa: BLE001 (sonde absente)
        return 0.0, 0.0


# ------------------------------------------------- inventaire NOMMÉ des tableaux
def inventaire(obj, profondeur=3):
    """[(chemin, dtype, forme, octets)] des `ndarray` atteignables depuis `obj`.

    MÊME parcours que `perf.taille_tableaux` (dicts, listes, `__dict__`), mais
    il retient le CHEMIN de chaque tableau : c'est ce qui transforme une jauge
    (« 2 935,7 Mo, 49 tableaux ») en répartition exploitable. Aucun tableau
    n'est copié. La somme est vérifiée égale à `perf.taille_tableaux` au [1].
    """
    vus = set()
    out = []

    def visite(o, p, chemin):
        if o is None or id(o) in vus:
            return
        vus.add(id(o))
        if isinstance(o, np.ndarray):
            out.append((chemin, str(o.dtype), tuple(o.shape), int(o.nbytes)))
            return
        if p <= 0:
            return
        if isinstance(o, dict):
            for k, v in list(o.items()):
                visite(v, p - 1, f"{chemin}[{k}]")
        elif isinstance(o, (list, tuple)):
            for i, v in enumerate(list(o)):
                visite(v, p - 1, f"{chemin}[{i}]")
        elif hasattr(o, "__dict__"):
            try:
                for k, v in list(vars(o).items()):
                    visite(v, p - 1, f"{chemin}.{k}" if chemin else k)
            except Exception:             # noqa: BLE001 (objet exotique)
                return

    visite(obj, profondeur, "")
    return out


CATEGORIES = (
    (("sum", "sumsq", "wsum"), "accumulateurs (float64)"),
    (("_moy", "_sig", "_dif", "_pix", "_masq"), "tampons de travail"),
    (("_buf",), "fenêtre glissante (frames)"),
    (("_memo_moy",), "moyennes de rôle mémoïsées"),
    (("_memo_compo", "_fit_cache", "_wb_cache_comp", "_bornes_cache"),
     "composite mémoïsé / caches couleur"),
)


def categorie(chemin):
    """Catégorie d'un poste, à partir du NOM D'ATTRIBUT du chemin.

    Le parcours produit des chemins comme `stackers[L]._buf` ou
    `_fit_cache[1][0]` : on isole le dernier attribut et on retire les
    INDICES (`[1]`, `[0]`) — sinon un cache rangé dans un tuple
    (`_memo_compo`, `_fit_cache`, `_memo_moy`) tomberait dans « divers » et le
    tableau de répartition mentirait par omission.
    """
    nom = chemin.rsplit(".", 1)[-1]
    if "[" in nom:
        nom = nom.split("[", 1)[0]
    for noms, libelle in CATEGORIES:
        if nom in noms:
            return libelle
    return "divers (polylignes, diag)"


# ------------------------------------------------------------ contexte du relevé
def geometrie_reelle():
    """(h, w, origine) des brutes du run — relue sur le 1er FITS de la config.

    Lecture d'EN-TÊTE seule (un bloc de 2880 octets, jamais les données) :
    aucune image n'est chargée, aucun pixel n'est touché. Repli silencieux sur
    la géométrie MESURÉE le 21/10/2026 (NAXIS1=3856, NAXIS2=2180).
    """
    conf = os.path.join(os.environ.get("APPDATA", ""), "AVAStack",
                        "config.json")
    try:
        with open(conf, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        dossier = cfg.get("compo_dossier_0") or cfg.get("dossier") or ""
        fichiers = []
        if dossier and os.path.isdir(dossier):
            fichiers = sorted(n for n in os.listdir(dossier)
                              if n.lower().endswith((".fits", ".fit")))
        if fichiers:
            with open(os.path.join(dossier, fichiers[0]), "rb") as f:
                bloc = f.read(2880).decode("ascii", "replace")
            vals = {}
            for carte in bloc.split("END")[0].splitlines():
                cle = carte[:8].strip()
                if cle in ("NAXIS1", "NAXIS2") and len(carte) > 10:
                    vals[cle] = int(carte[10:30])
            if "NAXIS1" in vals and "NAXIS2" in vals:
                return vals["NAXIS2"], vals["NAXIS1"], "en-tête FITS"
    except Exception:                     # noqa: BLE001 (partage absent)
        pass
    return GEOMETRIE_REEL[0], GEOMETRIE_REEL[1], "constante du 21/10/2026"


def releve_perf(chemin="perf-7.json"):
    """Charge le relevé `perf` (hors dépôt, cf. `.gitignore`) — None si absent."""
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:                     # noqa: BLE001
        return None


# ------------------------------------------------- le graphe RÉEL, en réduction
def construire_graphe(forme):
    """Reconstruit le graphe RÉEL (`CompositeStacker`, 5 rôles) sur `forme`.

    MÊMES réglages que le run `perf-7` (config.json figé après le relevé) :
    winsorized, fenêtre 4, kappa 3, Linear Fit, lissage des halos, normalisation
    commune, fusion Ha. Ce sont eux qui décident QUELLES allocations existent
    (`_tampons` seulement si k est actif, `_buf` seulement en winsorized,
    `_fit_cache` seulement si Linear Fit…). `mean()` est appelé pour peupler les
    caches exactement comme à la fin d'un run (moyennes de rôle, composite).

    1 SEUL rôle (`--roles L`) : c'est le chemin MONO/OSC de l'application —
    un `LiveStacker` NU, comme `core/worker.py` hors composition (aucun cache
    de composite, aucun `_memo_compo`). Un rôle de composition est MONO-canal :
    son coût est donc, au pixel près, celui d'une brute mono.
    """
    h, w = forme
    rng = np.random.default_rng(7)
    if len(ROLES) == 1:
        from avastack.processing.stacking import LiveStacker
        # `--canaux` : une brute MONO est 2D ; une brute OSC (débayérée) est
        # 3 canaux — TOUTES les allocations du stacker triplent alors.
        forme_mono = (h, w) if CANAUX <= 1 else (h, w, CANAUX)
        st = LiveStacker(forme_mono, k=KAPPA, method=METHODE, window=FENETRE)
        st.wb_auto = False
        st.linear_fit = True                  # config : linear_fit = True
        st.linear_fit_mode = "offset"
        for _ in range(FENETRE + 2):          # fenêtre pleine + rejeu du warmup
            st.add((rng.random(forme_mono) * 0.01).astype(np.float32))
        try:
            st.mean()
        except Exception as exc:              # noqa: BLE001 (géométrie de banc)
            print(f"  (mean() a échoué : {exc} — caches non peuplés)")
        return st
    cs = CompositeStacker(COMPOSITION, k=KAPPA, method=METHODE,
                          window=FENETRE)
    cs.wb_auto = False
    cs.linear_fit = True                  # config : linear_fit = True
    cs.linear_fit_mode = "offset"
    cs.mode_l = "synthetise"
    cs.normalisation_commune = True       # config : norm_commune = True
    cs.lissage_halos = True               # config : lissage_halos = True
    cs.seuil_masque_halos = 20.0
    cs.fusion_ha = {"mode": "fondu_rouge", "poids": 0.2, "alpha": 0.5,
                    "recentrer": True, "continuum": True, "q": 1.0,
                    "methode_continuum": "mediane", "bw_ha": 7.0}
    h, w = forme
    rng = np.random.default_rng(7)
    for role in ROLES:
        for _ in range(FENETRE + 2):       # fenêtre pleine + rejeu du warmup
            cs.add((rng.random((h, w)) * 0.01).astype(np.float32), role=role)
    try:
        cs.mean()                          # peuple `_memo_moy` et `_memo_compo`
    except Exception as exc:               # noqa: BLE001 (géométrie de banc)
        print(f"  (mean() a échoué : {exc} — caches non peuplés, écart au [2])")
    return cs


def mesurer_chaine_rendu(hh, ww):
    """[3 bis] CHAÎNE DE RENDU — ce que le moteur d'affichage et l'UI GARDENT.

    POURQUOI (21/10/2026) : la réconciliation laissait **~1 Go non
    instrumenté**. Le soupçon, vérifié ICI avec la VRAIE classe et les MÊMES
    réglages que le run : la chaîne d'affichage garde plusieurs images PLEINE
    RÉSOLUTION à la fois — les couches de composition (`vl_compo`, une par
    rôle), la COPIE défensive du job (`_vl_job`, vivante pendant le calcul), le
    résultat étiré (`_vl_result`), le brut avant niveaux
    (`dernier_brut_niveaux`) — plus, côté interface, l'image affichée et
    l'image uint8 rendue.

    Depuis l'audit du 21/10/2026 (même jour, lot « copie → référence »),
    `_stack_pleine_res` n'est PLUS une copie : c'est une RÉFÉRENCE sur l'image
    gardée par le stacker (0 octet de plus ici, et `_vl_src` n'existe plus).

    Aucun fichier de l'application n'est modifié : on INSTANCIE et on MESURE.
    → octets retenus (inventaire dédupliqué) ET pic RSS pendant le calcul.
    """
    from avastack.processing.display import DisplayProcessor

    def regler(disp):
        """Réglages EXACTS du relevé `perf-7` (config.json figé après le run)."""
        disp.stretch = "veralux"
        disp.vl_mode_res = "fond cible (auto)"
        disp.vl_target_bg = 0.13
        disp.vl_log_d = 1.15678
        disp.vl_profil = "Rec.709 (Recommended)"
        disp.vl_graxpert = False
        disp.vl_denoise = False
        disp.vl_sharp = False
        disp.vl_scnr = False
        disp.vl_demagenta = False
        disp.vl_preserve_luminance = True
        disp.vl_boost_rouge = True
        disp.vl_boost_force = 1.15
        disp.vl_neutre_fond = True
        disp.vl_chroma = True
        disp.vl_chroma_force = 0.652542
        disp.vl_chroma_rayon = 3.0

    rng = np.random.default_rng(11)
    # Composite LINÉAIRE réaliste (fond sombre + quelques hautes lumières) :
    # une image plate rendrait les percentiles dégénérés et le solveur
    # basculerait en repli — on mesurerait alors un AUTRE chemin.
    if len(ROLES) == 1:
        # MONO/OSC (`--roles L`) : l'image rendue est 2D (MONO) ou 3 canaux
        # (OSC, `--canaux 3`) et `App._pousser_rendu` NE POSE PAS `vl_compo`
        # (hors composition, `canaux = None`). C'est le chemin RÉEL du minimum —
        # le mesurer évite de l'estimer.
        forme_mono = (hh, ww) if CANAUX <= 1 else (hh, ww, CANAUX)
        comp = (0.002 + 0.02 * rng.random(forme_mono) ** 4).astype(np.float32)
        canaux = {}
    else:
        comp = (0.002 + 0.02 * rng.random((hh, ww, 3)) ** 4).astype(np.float32)
        canaux = {role: (0.002 + 0.02 * rng.random((hh, ww)) ** 4).astype(np.float32)
                  for role in ROLES}
    # `App._pousser_rendu` fait EXACTEMENT ceci depuis le 21/10/2026 : il garde
    # une RÉFÉRENCE sur le composite rendu par le stacker (aucune copie). C'est
    # CETTE image qui part au rendu (`_src_rendu` → `process`) ; elle est déjà
    # tenue par le stacker (`_fit_cache` / `_memo_compo`), donc pour la chaîne
    # d'affichage elle coûte 0 octet — la modéliser comme une copie ajoutait
    # 96,2 Mio à tort (mesuré avant le lot).
    stack_pleine_res = np.asarray(comp, np.float32)
    assert stack_pleine_res is comp, "la référence doit ALIASER le composite"
    disp = DisplayProcessor()
    regler(disp)
    if canaux:
        # MÊME structure que `App._pousser_rendu` (9 éléments, déballage
        # tolérant). Hors composition, `App._pousser_rendu` NE TOUCHE PAS
        # `vl_compo` : on ne le pose donc pas non plus (chemin mono mesuré).
        disp.vl_compo = (dict(canaux), COMPOSITION,
                         {"R": 1.0, "G": 1.0, "B": 1.0}, "synthetise",
                         (True, "offset"), (False, 1.0, None), True, (True, 20.0),
                         {"mode": "fondu_rouge", "poids": 0.2, "alpha": 0.5,
                          "recentrer": True, "continuum": True, "q": 1.0,
                          "methode_continuum": "mediane", "bw_ha": 7.0})
    gc.collect()
    r0, _ = mem_mo()
    t0 = time.time()
    disp.process(stack_pleine_res, live=True)   # soumet le job à VeraLux
    pic_rss = 0.0
    fin = time.time() + 180.0
    while disp.vl_en_cours() and time.time() < fin:
        pic_rss = max(pic_rss, mem_mo()[0])
        time.sleep(0.05)
    img8 = disp.process(stack_pleine_res, live=False)   # sert le cache
    duree = time.time() - t0
    r1, _ = mem_mo()
    pic_rss = max(pic_rss, r1)

    class _Graphe:
        pass

    g = _Graphe()
    g.disp = disp
    # Ni `comp` ni `stack_pleine_res` n'entrent dans ce graphe : ce sont des
    # ALIAS du cache du STACKER (`_memo_compo` / `_fit_cache`), déjà compté au
    # [2] (parcours p4). On compte ce que la chaîne AJOUTE.
    g.interface = {"resultat_img8": img8}
    # Profondeur 5 : `g` → `disp` → `__dict__` → tuple (`_vl_job`, `_vl_result`,
    # `vl_compo`) → dict des couches → tableaux. À profondeur 3 (celle de la
    # jauge) la moitié de ce graphe serait INVISIBLE.
    tab = inventaire(g, profondeur=5)
    octets_ref, nb_ref = perf.taille_tableaux(g, profondeur=5)
    total = sum(t[3] for t in tab)
    print(f"  VeraLux : {duree:.1f} s, erreur = {disp.vl_error or 'aucune'}")
    print(f"  {len(tab)} tableaux retenus, {total:,} o ({total / MO:.1f} Mio)"
          f" — cohérent avec perf.taille_tableaux :"
          f" {'OUI' if (total == octets_ref and len(tab) == nb_ref) else 'NON'}")
    for chemin, dt, forme, n in sorted(tab, key=lambda t: -t[3]):
        print(f"  {chemin:44s} {dt:8s} {str(forme):18s} {n / MO:8.1f} Mio")
    print(f"  RSS : avant {r0:,.0f} Mio → après {r1:,.0f} Mio"
          f" (delta {r1 - r0:+,.0f}) · PIC pendant le calcul {pic_rss:,.0f}"
          f" (delta {pic_rss - r0:+,.0f})")
    print("  → DÉDUPLICATION : `_stack_pleine_res` ALIASE le composite du"
          " stacker (0 octet\n    ajouté, `is` vérifié) et `_vl_result` est la"
          " MÊME image que\n    `dernier_brut_niveaux` (le résultat étiré est"
          " réutilisé tel quel) — compter les\n    deux doublerait. `_vl_src`"
          " n'existe plus (retiré le 21/10/2026 : écrit,\n    jamais lu, il"
          " retenait l'image soumise). Ce qui est RETENU après un rendu,\n    c'est"
          " ce que la jauge `stackers_*` ne voit pas ; le PIC inclut en plus la"
          " copie\n    de job (`_vl_job`) et les temporaires du moteur — BORNE"
          " HAUTE sur image de\n    synthèse à 8,4 Mpx (le run réel rend 7,4 Mpx"
          " recadrés).")
    del disp, comp, canaux, img8, stack_pleine_res, g, tab
    gc.collect()
    # FRAGMENTATION / TAS : tout ce que la chaîne vient d'allouer est LIBÉRÉ ;
    # ce que le RSS garde encore est ce que l'allocateur ne rend pas au système
    # (trous laissés par ~1,5 Go de temporaires VeraLux, tas Python, arènes
    # OpenCV). C'est la seule part du résiduel qu'on peut chiffrer SANS session
    # réelle — et elle explique pourquoi `rss_max` dépasse la somme des postes.
    r_final = mem_mo()[0]
    garde = r_final - r0
    print(f"  après libération de TOUT (gc) : RSS {r_final:,.0f} Mio"
          f" → gardé {garde:+,.0f} Mio")
    print("    ↑ NON-TABLEAU retenu par le processus : arènes de l'allocateur"
          " (trous des\n    temporaires), tas Python, tampons internes"
          " OpenCV/Tk. Un chiffre positif et\n    stable ici n'est PAS une"
          " fuite : c'est de la fragmentation.")
    return total


def _config_app():
    """CONFIG réelle de l'utilisateur (LECTURE SEULE) — None si absente."""
    conf = os.path.join(os.environ.get("APPDATA", ""), "AVAStack",
                        "config.json")
    try:
        with open(conf, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:                     # noqa: BLE001
        return None


def mesurer_app(secondes=90.0, frames=6):
    """[7] BANC EN VRAI — l'APPLICATION elle-même, avec la config de l'utilisateur.

    POURQUOI (21/10/2026, « nommer le résiduel ») : la jauge `postes` range les
    tableaux par attribut de premier niveau (`aligner`, `calib`, `disp`,
    `_hist_*`, caches de catalogues…). Elle ne dit la vérité que sur une VRAIE
    session : les caches se peuplent au fil des frames (astrométrie, SPCC,
    annotation) et c'est justement là que se cache le résiduel.

    Rien n'est écrit : `config.json` est lu en copie et `sauver_config` est
    neutralisé. L'acquisition tourne jusqu'à `frames` frames empilées (ou
    `secondes`), puis l'inventaire est imprimé. Nécessite un affichage.
    """
    import tkinter as tk

    import avastack.ui.app as ui

    cfg = _config_app()
    if cfg is None:
        print("  config.json introuvable : section [7] sautée")
        return
    ui.CONFIG = dict(cfg)                 # copie : le vrai fichier n'est pas
    ui.sauver_config = lambda d: None     # touché (aucune écriture)
    root = tk.Tk()
    root.withdraw()
    app = ui.App(root)
    root.update_idletasks()
    # Source : la caméra est construite ICI si l'App n'en a pas ouvert (le
    # démarrage par l'interface dépend de variables Tk ; on reproduit la config
    # des DOSSIERS, elle, sans ambiguïté).
    if getattr(app, "camera", None) is None:
        try:
            from avastack.cameras.multifolder import MultiFolderCamera
            paires = [(cfg.get(f"compo_role_{i}"), cfg.get(f"compo_dossier_{i}"))
                      for i in range(5)]
            paires = [(r, d) for r, d in paires if r and d]
            if len(paires) >= 2:
                app.camera = MultiFolderCamera(paires)
                app.var_source.set(
                    "Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
        except Exception as exc:          # noqa: BLE001 (partage absent)
            print(f"  caméra de composition impossible ({exc})")
    perf.activer()                        # les jauges de l'app se remplissent
    try:
        app._start()
    except Exception as exc:              # noqa: BLE001 (source indisponible)
        print(f"  démarrage impossible ({exc}) — section [7] sautée")
        root.destroy()
        return
    print(f"  source={app.var_source.get()!r} ·"
          f" caméra={type(app.camera).__name__ if app.camera else None} ·"
          f" empilement_on={app.empilement_on} · running={app.running}")
    n = 0
    t0 = time.time()
    dernier = 0.0
    while time.time() - t0 < secondes:
        root.update()
        n = app.stacker.n if getattr(app, "stacker", None) is not None else 0
        if n >= frames:
            break
        if time.time() - dernier >= 10.0:      # progression (diagnostic)
            dernier = time.time()
            fil = getattr(app, "thread", None)
            etat = ""
            try:
                etat = app.lbl_status.cget("text")
            except Exception:                  # noqa: BLE001
                pass
            lu = getattr(app.camera, "last_file", "") or "—"
            print(f"    · t+{time.time() - t0:4.0f} s · n={n} ·"
                  f" fil={'vivant' if fil and fil.is_alive() else 'arrêté'} ·"
                  f" lu={os.path.basename(str(lu))[:28]!r} · {etat[:60]!r}")
        time.sleep(0.05)
    rss = perf.memoire_mo()[0]
    if n == 0:
        print("  ⚠ AUCUNE frame empilée : la session n'a pas démarré dans ce"
              " processus\n    (l'App reste « Prêt » — le démarrage par"
              " l'interface dépend de la boucle\n    Tk complète). Les postes"
              " ci-dessous décrivent l'ÉTAT DE REPOS.\n    Pour le régime"
              " établi : `python AVAStack.py --perf --perf-json perf-9.json`.")
    inst = perf.instantane()
    jg = inst.get("jauges") or {}
    print(f"  frames empilées : {n} · RSS {rss:,.0f} Mo ·"
          f" stackers {jg.get('stackers_mo')} Mio ·"
          f" postes {jg.get('postes_mo')} Mio")
    tab = perf.postes_memoire(app)
    for nom, octets in sorted(tab["postes"].items(),
                              key=lambda kv: -kv[1])[:18]:
        print(f"  {nom:34s} {octets / MO:9.1f} Mio")
    print(f"  {'TOTAL tableaux (hors empileur)':34s}"
          f" {tab['total_octets'] / MO:9.1f} Mio"
          f" sur {tab['nb_tableaux']} tableaux")
    app.running = False
    app.empilement_on = False
    if getattr(app, "thread", None) is not None and app.thread.is_alive():
        app.thread.join(timeout=5.0)
    root.destroy()


def main(argv):
    global ROLES, COMPOSITION, CANAUX
    sans_alloc = "--sans-allocation" in argv
    sans_rendu = "--sans-rendu" in argv
    # ENVELOPPE MÉMOIRE (21/10/2026) : `--roles` (1 rôle = chemin MONO/OSC, un
    # `LiveStacker` nu comme `core/worker.py` hors composition), `--canaux 3`
    # (brute OSC débayerisée, hors composition) et `--maitres N` (N maîtres
    # dark/flat en mémoire). Posés AVANT toute construction.
    n_maitres = int(argv[argv.index("--maitres") + 1]) \
        if "--maitres" in argv else 0
    if "--canaux" in argv:
        CANAUX = max(1, int(argv[argv.index("--canaux") + 1]))
    if "--roles" in argv:
        _roles = tuple(r.strip() for r
                       in argv[argv.index("--roles") + 1].split(",") if r.strip())
        if _roles:
            ROLES = _roles
            if len(_roles) > 1:
                from avastack.processing.composition import composition_pour_roles
                COMPOSITION = composition_pour_roles(list(_roles)) or COMPOSITION
    base_processus, _ = mem_mo()      # AVANT toute allocation de ce banc
    forme_banc = (120, 160)
    if "--geometrie" in argv:
        h, w = argv[argv.index("--geometrie") + 1].lower().split("x")
        hh, ww, origine = int(h), int(w), "option --geometrie"
    else:
        hh, ww, origine = geometrie_reelle()
    px_reel = hh * ww
    bh, bw = forme_banc
    px_banc = bh * bw
    perf_json = releve_perf(argv[argv.index("--perf-json") + 1]
                            if "--perf-json" in argv else "perf-7.json")

    print("=" * 78)
    print("MESURE MÉMOIRE — répartition des octets d'un empilement 5 canaux")
    print("=" * 78)
    print(f"  géométrie de référence : {hh}x{ww} = {px_reel:,} px  ({origine})")
    print(f"  graphe de banc         : {bh}x{bw} = {px_banc:,} px"
          f"  (rôles {'+'.join(ROLES)} · {METHODE}, fenêtre {FENETRE},"
          f" k={KAPPA})")
    print(f"  maîtres de calibration : {n_maitres} (float32 pleine frame,"
          f" {hh * ww * 4 / MO:.1f} Mio chacun, géométrie NATIVE)")
    print(f"  projection             : x{px_reel / px_banc:,.1f} sur les"
          " tableaux PLEINE FRAME")

    # ------------------------------------------------ [1] INVENTAIRE (étape ②)
    print("\n[1] INVENTAIRE du graphe RÉEL (géométrie de banc) — chemin, dtype,"
          " forme, octets")
    cs = construire_graphe(forme_banc)
    tab = inventaire(cs, profondeur=3)
    total_banc = sum(t[3] for t in tab)
    octets_ref, nb_ref = perf.taille_tableaux(cs, profondeur=3)
    coherent = (total_banc == octets_ref and len(tab) == nb_ref)
    print(f"  {len(tab)} tableaux, {total_banc:,} octets  |  "
          f"perf.taille_tableaux : {octets_ref:,} o / {nb_ref} tableaux  → "
          f"{'IDENTIQUE' if coherent else 'ÉCART (parcours à revoir)'}")
    for chemin, dt, forme, n in sorted(tab, key=lambda t: -t[3]):
        px = int(np.prod(forme))
        if px == px_banc:
            marque = "pleine frame"
        elif px % px_banc == 0:
            marque = f"{px / float(px_banc):g} frame(s) de banc"
        else:
            marque = f"{px:,} px (vue)"
        print(f"  {chemin:36s} {dt:8s} {str(forme):18s} {n:10,d} o   {marque}")
    par_role = {}
    for chemin, _dt, _f, n in tab:
        if chemin.startswith("stackers["):
            role = chemin.split("]")[0][len("stackers["):]
            par_role[role] = par_role.get(role, 0) + n
    print("  octets par rôle : " + " · ".join(
        f"{r} {n / 1024.0:,.0f} Kio" for r, n in par_role.items()))
    print("  par catégorie :")
    cats = {}
    for chemin, _dt, _f, n in tab:
        c = categorie(chemin)
        cats[c] = cats.get(c, 0) + n
    for c, n in sorted(cats.items(), key=lambda kv: -kv[1]):
        print(f"    {c:38s} {n:10,d} o  ({n / MO:7.2f} Mio de banc)")

    # La jauge `jauger_empileur` parcourt à profondeur 3. Ce parcours s'arrête
    # AVANT le contenu des tuples d'un `LiveStacker` : les moyennes mémoïsées
    # (`_memo_moy`, un tuple (n, image)) lui échappent. On le MESURE ici.
    tab4 = inventaire(cs, profondeur=4)
    total_banc4 = sum(t[3] for t in tab4)
    vus = {t[0] for t in tab}
    manquants = [t for t in tab4 if t[0] not in vus]
    print(f"  profondeur 4 (réelle) : {len(tab4)} tableaux,"
          f" {total_banc4:,} octets  → le parcours de la jauge en MANQUE"
          f" {len(manquants)}")
    for chemin, dt, forme, n in manquants:
        print(f"    manquant : {chemin:34s} {dt:8s} {str(forme):18s}"
              f" {n:9,d} o")

    # --------------------------------------- [2] PROJECTION à la géométrie réelle
    print(f"\n[2] PROJECTION à {hh}x{ww} ({px_reel:,} px) — étape ③ du protocole")
    facteur = px_reel / float(px_banc)

    def projeter(table):
        """Projection linéaire : vaut pour une pleine frame COMME pour N frames
        empilées (`_buf`) ou un composite 3 canaux — tout tableau dont le
        nombre de pixels est un multiple de la frame de banc."""
        out = []
        for chemin, dt, forme, n in table:
            px = int(np.prod(forme))
            lineaire = (px % px_banc == 0)
            out.append((chemin, dt, forme, n,
                        int(round(n * facteur)) if lineaire else n, lineaire))
        return out

    proj3 = projeter(tab)                  # MÊME parcours que la jauge (p3)
    proj = projeter(tab4)                  # parcours RÉEL (p4)
    total_proj3 = sum(p[4] for p in proj3)
    total_proj = sum(p[4] for p in proj)
    aveugle = total_proj - total_proj3      # ce que la jauge (p3) ne voit pas
    poids_cat = {}
    for chemin, _dt, _f, _n, p, _lin in proj:
        poids_cat[categorie(chemin)] = (poids_cat.get(categorie(chemin), 0)
                                        + p)
    print("  par catégorie (parcours réel, profondeur 4) :")
    for c, n in sorted(poids_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {c:38s} {n / MO:8.1f} Mio")
    print(f"  {'TOTAL parcours de la jauge (p3)':38s}"
          f" {total_proj3 / MO:8.1f} Mio")
    print(f"  {'TOTAL RÉEL (p4, moyennes comprises)':38s}"
          f" {total_proj / MO:8.1f} Mio  ({total_proj:,} o)")
    print("    ↑ modèle : caches supposés PLEINE FRAME. Dans le run ils sont"
          " RECADRÉS (le\n    composite mémoïsé est composé depuis les moyennes"
          " recadrées) : le total constaté\n    se déduit donc de la jauge, pas"
          " du modèle.")
    if perf_json:
        jauge = perf_json.get("jauges") or {}
        cible = jauge.get("stackers_octets")
        nb_roles_releve = jauge.get("stackers_nb")
        if isinstance(cible, int) and cible > 0 \
                and isinstance(nb_roles_releve, int) and nb_roles_releve != len(ROLES):
            # HONNÊTETÉ (21/10/2026) : comparer une projection MONO (ou 2 rôles)
            # à la jauge d'un relevé à 5 rôles donnerait un écart de −80 % qui ne
            # mesure RIEN (ce ne sont pas les mêmes tableaux). On le DIT au lieu
            # de l'afficher comme un résultat.
            print(f"  COMPARAISON À LA JAUGE NON FAITE : le relevé porte"
                  f" {nb_roles_releve} empileur(s), cette projection en modélise"
                  f" {len(ROLES)} —\n    les deux ne décrivent pas le même graphe"
                  " (relancer l'application avec --perf pour ce cas).")
        elif isinstance(cible, int) and cible > 0:
            ecart = total_proj3 - cible
            print(f"  jauge RÉELLE perf-7 (même parcours p3) : {cible:,} o"
                  f" ({cible / MO:.1f} Mio,"
                  f" {jauge.get('stackers_nb_tableaux')} tableaux)")
            print(f"  écart projection p3 − jauge : {ecart:+,} o "
                  f"({ecart / MO:+.1f} Mio, {100.0 * ecart / cible:+.2f} %)")
            print(f"  AVEUGLEMENT de la jauge (p4 − p3) : {aveugle:+,} o"
                  f" ({aveugle / MO:+.1f} Mio) — les moyennes de rôle")
            constate = cible + aveugle
            print(f"  TOTAL CONSTATÉ (jauge + aveuglement mesuré) : {constate:,} o"
                  f" ({constate / MO:.1f} Mio) ← le chiffre à retenir")
            print("  → lecture : un écart p3 sous le pour cent prouve que le"
                  " MODÈLE est juste (mêmes\n    tableaux, mêmes dtypes) ; le"
                  " run n'avait que des vues RECADRÉES (le composite mémoïsé"
                  " est\n    recadré au cadre commun, donc plus petit qu'une"
                  " pleine frame). L'aveuglement p4 − p3\n    est en revanche un"
                  " DÉFAUT DE MESURE chiffré : la jauge ne voit pas les"
                  " moyennes.")

    # --------------------------------- [3] POSTES HORS STACKERS, MESURÉS AU RSS
    print("\n[3] POSTES HORS STACKERS — allocations RÉELLES à la géométrie du run")
    print("    (alloués REMPLIS pour toucher les pages, mesurés au RSS, puis"
          " libérés ;\n     « non rendu » = pages que l'allocateur garde —"
          " ce n'est PAS une fuite)")
    postes = [
        ("brute uint16 (lue du FITS)", (hh, ww), np.uint16, False),
        ("frame calibrée float32 (worker)", (hh, ww), np.float32, False),
        ("canal du rôle extrait (float32)", (hh, ww), np.float32, False),
        ("image affichée uint8 (3 canaux)", (hh, ww, 3), np.uint8, False),
        ("brut niveaux float32 (3 canaux)", (hh, ww, 3), np.float32, False),
        ("composite 3 canaux (déjà dans les stackers)",
         (hh, ww, 3), np.float32, True),
        (f"fenêtre {FENETRE} frames (déjà dans les stackers)",
         (FENETRE, hh, ww), np.float32, True),
        ("fenêtre 8 frames (ancien réglage, info)",
         (8, hh, ww), np.float32, True),
    ]
    total_postes = 0
    for nom, forme, dt, deja in postes:
        n = int(np.prod(forme)) * np.dtype(dt).itemsize
        if not deja:                        # jamais deux fois le même octet
            total_postes += n
        if sans_alloc:
            print(f"  {nom:44s} {n / MO:8.1f} Mio  (théorique)")
            continue
        gc.collect()
        r0, _ = mem_mo()
        arr = np.full(forme, 1, dtype=dt)          # REMPLI : pages touchées
        r1, _ = mem_mo()
        del arr
        gc.collect()
        r2, _ = mem_mo()
        print(f"  {nom:44s} {n / MO:8.1f} Mio · RSS {r1 - r0:+7.1f} Mio"
              f" · non rendu {r2 - r0:+6.1f} Mio")
    # MAÎTRES DE CALIBRATION (v2.98.7) : un dark ET un flat par rôle, gardés en
    # mémoire TOUTE la session (float32 PLEINE FRAME, géométrie NATIVE — jamais
    # recadrée). `--maitres N` les alloue ENSEMBLE (c'est leur coût RÉEL : ils
    # coexistent) et les mesure au RSS ; sans option, aucun maître.
    if n_maitres:
        n_m = hh * ww * 4
        libelle = f"{n_maitres} maître(s) dark/flat (float32)"
        if sans_alloc:
            print(f"  {libelle:44s} {n_maitres * n_m / MO:8.1f} Mio  (théorique)")
        else:
            gc.collect()
            r0, _ = mem_mo()
            _maitres = [np.full((hh, ww), 1, dtype=np.float32)
                        for _ in range(n_maitres)]
            r1, _ = mem_mo()
            del _maitres
            gc.collect()
            r2, _ = mem_mo()
            print(f"  {libelle:44s} {n_maitres * n_m / MO:8.1f} Mio"
                  f" · RSS {r1 - r0:+7.1f} Mio · non rendu {r2 - r0:+6.1f} Mio")
        total_postes += n_maitres * n_m
    print(f"  {'TOTAL hors accumulateurs (sans double compte)':44s}"
          f" {total_postes / MO:8.1f} Mio")
    print("  → la fenêtre glissante et le composite mémoïsé sont DÉJÀ dans les"
          " stackers : les\n    compter ici doublerait le total. Le pic du run"
          " vient de la COEXISTENCE\n    de ces postes avec les stackers, pas de"
          " leur somme.")

    # ------------------------------- [3 bis] CHAÎNE DE RENDU (le Go inexpliqué)
    total_rendu = 0
    if sans_rendu:
        print("\n[3 bis] CHAÎNE DE RENDU — SAUTÉE (--sans-rendu)")
    elif sans_alloc:
        print("\n[3 bis] CHAÎNE DE RENDU — SAUTÉE (--sans-allocation : elle"
              " instancie un vrai moteur)")
    else:
        print("\n[3 bis] CHAÎNE DE RENDU (VRAIE classe `DisplayProcessor`,"
              " réglages du run, pleine résolution)")
        total_rendu = mesurer_chaine_rendu(hh, ww)

    # ---------------------------------------- [4] RÉCONCILIATION avec le RSS
    print("\n[4] RÉCONCILIATION — stackers (jauge) + postes + chaîne de rendu")
    print(f"  base du processus AVANT toute allocation du banc :"
          f" {base_processus:,.0f} Mio\n    (interpréteur + numpy + module"
          " d'empilement — borne basse de ce que l'appli traîne)")
    print(f"  base applicative de RÉFÉRENCE (Tk + OpenCV + astropy, mesurée le"
          f" 20/10 par\n    `bancs/_mesure_memoire.py`) : {BASE_APP_REPOS_MO:,.0f}"
          " Mio au repos — c'est la base à retirer, pas celle du banc")
    rss_run = rss_fin = pic = stackers_mo = 0.0
    residuel = 0.0
    hors = 0.0
    if perf_json:
        mem = perf_json.get("memoire") or {}
        rss_run = float(mem.get("rss_max_mo") or 0.0)
        rss_fin = float(mem.get("rss_mo") or 0.0)
        pic = float(mem.get("pic_max_mo") or 0.0)
        stackers_mo = float((perf_json.get("jauges") or {})
                            .get("stackers_mo") or 0.0)
        reel_mo = (stackers_mo + aveugle / MO) if stackers_mo > 0 \
            else total_proj / MO            # jauge + aveuglement MESURÉ
        if rss_run > 0.0 and reel_mo > 0.0:
            # HONNÊTETÉ : la réconciliation soustrait CE QUE CE RUN modélise
            # (rôles + maîtres) du RSS d'un relevé qui n'avait pas forcément la
            # même configuration. Sans ce garde-fou, « 10 maîtres » soustraits à
            # un relevé qui n'en portait que 3 afficherait un résiduel FAUX de
            # −224 Mio (l'écart de maîtres, pas une économie).
            _calib_releve = ((perf_json.get("jauges") or {}).get("postes")
                             or {}).get("calib")
            _n_m_releve = (int(round(float(_calib_releve) / (px_reel * 4 / MO)))
                           if _calib_releve else 0)
            _ecarts = []
            if isinstance(nb_roles_releve, int) and nb_roles_releve != len(ROLES):
                _ecarts.append(f"{nb_roles_releve} empileur(s) dans le relevé,"
                               f" {len(ROLES)} ici")
            if _n_m_releve != n_maitres:
                _ecarts.append(f"{_n_m_releve} maître(s) dans le relevé,"
                               f" {n_maitres} ici")
            if _ecarts:
                print("  ⚠ INDICATIF SEULEMENT — le relevé et cette mesure ne"
                      " décrivent pas la même\n    configuration ("
                      + " ; ".join(_ecarts) + ") : le résiduel ci-dessous est une"
                      " BORNE,\n    pas le résiduel de ce relevé.")
            hors = rss_run - reel_mo
            postes_mo = total_postes / MO
            rendu_mo = total_rendu / MO
            # La chaîne est mesurée à la géométrie NATIVE (8,4 Mpx) ; le run rend
            # l'image RECADRÉE (`source_px`). Sans cette remise à l'échelle, le
            # résiduel est SOUS-estimé d'environ 33 Mio (toutes les images de la
            # chaîne — couches, brut niveaux, uint8 — sont à la taille du run).
            src_px = int((perf_json.get("jauges") or {}).get("source_px") or 0)
            if src_px > 0 and rendu_mo > 0.0 and src_px < px_reel:
                ech = src_px / float(px_reel)
                print(f"  chaîne [3 bis] ramenée à la géométrie du run"
                      f" ({src_px:,} px / {px_reel:,} px, ×{ech:.3f})"
                      f" : {rendu_mo * ech:,.1f} Mio")
                rendu_mo *= ech
            residuel = hors - postes_mo - rendu_mo - BASE_APP_REPOS_MO
            print(f"  RSS PENDANT le run (max) : {rss_run:,.1f} Mio · pic"
                  f" {pic:,.1f} Mio")
            print(f"  RSS en fin de run        : {rss_fin:,.1f} Mio — la jauge"
                  " n'est PAS réémise après\n    la fermeture : comparer les"
                  " deux n'aurait aucun sens (c'est l'erreur du « 61 % »)")
            print(f"  stackers CONSTATÉS       : {reel_mo:,.1f} Mio ="
                  f" {100.0 * reel_mo / rss_run:.1f} % du RSS du run")
            print(f"    dont jauge perf-7 (p3) : {stackers_mo:,.1f} Mio"
                  f"  + sous-compte MESURÉ (p4 − p3)"
                  f" {aveugle / MO:.1f} Mio")
            print(f"  hors stackers            : {hors:,.1f} Mio")
            print(f"  − postes mesurés au [3]  : {postes_mo:,.1f} Mio"
                  f" ({100.0 * postes_mo / hors:.1f} % du hors-stackers)")
            print(f"  − chaîne de rendu [3 bis] : {rendu_mo:,.1f} Mio"
                  f" ({100.0 * rendu_mo / hors:.1f} % du hors-stackers)")
            print(f"  − base applicative       : {BASE_APP_REPOS_MO:,.1f} Mio")
            print(f"  = RÉSIDUEL non instrumenté : {residuel:+,.1f} Mio"
                  f" ({100.0 * residuel / rss_run:+.1f} % du RSS du run)")
            print("  → le résiduel n'est PAS une fuite démontrée : c'est ce"
                  " qu'aucune jauge ne\n    nomme encore — maîtres de"
                  " calibration (dark/flat), image de référence de\n"
                  "    l'aligneur, tampons OpenCV/Tk, archive FITS,"
                  " fragmentation de l'allocateur.")
            if rendu_mo > 0.0:
                print("    Il est passé de 1 014,5 Mio à ce chiffre grâce à"
                      " [3 bis] : la chaîne de\n    rendu était bien l'essentiel"
                      " du « Go inexpliqué ».")
            # MILLÉSIME : le RSS de référence doit être POSTÉRIEUR au lot
            # « copie → référence » (v2.98.5). Sinon la chaîne mesurée ici
            # (280,6 Mio, sans la copie) ne correspond pas au RSS relevé : le
            # résiduel paraît gonflé de 96,2 Mio.
            version = str((perf_json.get("contexte") or {}).get("version") or "")

            def _v(s):
                return tuple(int(x) for x in s.split(".") if x.isdigit())

            if _v(version) and _v(version) < (2, 98, 5):
                print(f"  ⚠ relevé en v{version}, ANTÉRIEUR au lot « copie →"
                      " référence » (v2.98.5)\n    qui a retiré 96,2 Mio de"
                      " rétention : le résiduel ci-dessus en est gonflé.\n    À"
                      " REFAIRE avec un relevé postérieur — la valeur d'après"
                      " serait\n    sensiblement plus basse, jamais plus haute.")
            elif version:
                print(f"  relevé en v{version} : postérieur au lot « copie →"
                      " référence » (v2.98.5),\n    le résiduel ci-dessus est"
                      " cohérent avec la chaîne mesurée.")
    else:
        print("  perf-7.json absent (fichier hors dépôt) : réconciliation"
              " impossible —\n  relancer l'application avec --perf pour"
              " produire un relevé.")

    # ------------------------------------ [6] POSTES : QUI tient le résiduel ?
    print("\n[6] POSTES DE L'APPLICATION — qui tient le « hors stackers » ?")
    postes = ((perf_json or {}).get("jauges") or {}).get("postes")
    if not isinstance(postes, dict) or not postes:
        print("  jauge `postes` ABSENTE de ce relevé (instrumentation v2.98.6) :")
        print("  relancer l'application avec `--perf` pour la produire — c'est"
              " ELLE qui\n  nomme les tableaux par attribut (`aligner`, `calib`,"
              " `disp`, `_hist_*`…).")
    else:
        total_p = float(sum(postes.values()))
        for nom, mo in sorted(postes.items(), key=lambda kv: -kv[1])[:14]:
            print(f"  {nom:34s} {float(mo):8.1f} Mio")
        print(f"  {'TOTAL tableaux applicatifs (hors empileurs)':34s}"
              f" {total_p:8.1f} Mio")
        if hors > 0.0:
            non_tab = hors - total_p - BASE_APP_REPOS_MO
            print(f"  hors stackers {hors:,.1f} Mio − tableaux applicatifs"
                  f" {total_p:,.1f} − base {BASE_APP_REPOS_MO:,.1f}"
                  f"\n  = {non_tab:,.1f} Mio SANS TABLEAU nommé")
            print("    → tampons Tk/PIL/OpenCV/astropy NON comptés par la jauge,"
                  " objets Python\n    et FRAGMENTATION de l'allocateur (les"
                  " temporaires VeraLux ~1,5 Go laissent\n    des trous). La"
                  " chaîne de rendu et les postes d'image SONT dans les tableaux"
                  "\n    applicatifs : ne pas les retirer une seconde fois.")
            print("    Une part NÉGATIVE signalerait un double compte, pas une"
                  " économie.")
    # CANDIDATS VÉRIFIÉS SANS SESSION (21/10/2026) : ce que l'on peut nommer
    # SANS relever une nouvelle session — mesuré ici ou vérifié dans le code.
    # HISTORIQUE (correction du 21/10, DÉFAUT CORRIGÉ en v2.98.7) : l'ABSENCE de
    # clé `dark`/`flat` dans `config.json` ne prouvait PAS qu'aucun maître
    # n'était chargé — les chemins de calibration n'étaient **PAS persistés**
    # (`_load_dark`/`_load_flat` chargeaient l'image en mémoire sans rien
    # écrire). Depuis v2.98.7 ils le sont (`calib_dark_*` / `calib_flat_*`), et
    # ils sont RELUS au démarrage : un relevé `--perf` postérieur porte donc les
    # chemins, et les maîtres se comptent dans le poste **`calib`** de la jauge
    # `postes` (N × ~32,1 Mio à 8,4 Mpx, ~28 Mio à la géométrie du run).
    try:
        cfg = _config_app() or {}
        chemins = [k for k in cfg
                   if "dark" in k.lower() or "flat" in k.lower()]
        px_run = int(((perf_json or {}).get("jauges") or {})
                    .get("source_px") or 0) or px_reel
        ref_mio = px_run / MO                     # ref_gray : uint8, 1 octet/px
        maitre_mio = px_run * 4.0 / MO            # master : float32, 4 octets/px
        print("  candidats VÉRIFIÉS hors session :")
        print(f"    chemins de calibration PERSISTÉS : {len(chemins)}"
              " (v2.98.7 : ils le sont désormais ; AVANT ce correctif un relevé"
              " n'en\n      portait aucun, et le poste `calib` valait 0 même"
              " maîtres chargés)")
        print(f"    un maître chargé               : {maitre_mio:5.1f} Mio"
              f" (float32 à {px_run:,} px) → un dark + un flat par rôle"
              f" = {2 * maitre_mio:.0f} Mio par rôle")
        print(f"    archive FITS           : {0.0:5.1f} Mio — écrit sur disque,"
              " ne garde que des CHEMINS (`ArchiveFrames`)")
        print(f"    références d'alignement: {3 * ref_mio:5.1f} Mio max —"
              f" 3 aligneurs × `ref_gray` uint8 à {px_run:,} px"
              f" ({ref_mio:.1f} chacune)")
        print("    fragmentation mesurée  : cf. section [3 bis] (RSS gardé après"
              " libération de TOUT)")
    except Exception as exc:                  # noqa: BLE001
        print(f"  (candidats non calculés : {exc})")

    # ------------------------------------ [5] LEVIER float32 (chiffré, NON fait)
    print("\n[5] LEVIER float32 — chiffré, NON appliqué (aucun pixel changé)")

    def octets_float64(cat):
        """Octets PROJETÉS des tableaux float64 d'une catégorie."""
        return sum(p[4] for p in proj
                   if categorie(p[0]) == cat and p[1] == "float64")

    acc = octets_float64("accumulateurs (float64)")
    tamp = octets_float64("tampons de travail")
    buf = poids_cat.get("fenêtre glissante (frames)", 0)
    print(f"  accumulateurs sum/sumsq/wsum float64 : {acc / MO:8.1f} Mio"
          f"  → float32 : −{acc / 2 / MO:.1f} Mio")
    print(f"  tampons _moy/_sig/_dif float64       : {tamp / MO:8.1f} Mio"
          f"  → float32 : −{tamp / 2 / MO:.1f} Mio")
    for nom, gain in (("accumulateurs seuls", acc / 2.0),
                      ("tampons seuls", tamp / 2.0),
                      ("les deux ensemble", (acc + tamp) / 2.0)):
        part = (f"  ({100.0 * gain / MO / rss_run:.1f} % du RSS du run)"
                if rss_run > 0.0 else "")
        print(f"    gain {nom:22s} : −{gain / MO:7.1f} Mio{part}")
    print(f"  fenêtre de {FENETRE} frames × 5 rôles : {buf / MO:.1f} Mio"
          " — piste SÉPARÉE (réduire la\n    fenêtre change la qualité du rejet"
          " : à mesurer, pas à décider ici)")
    print("  ⚠ une conversion de dtype CHANGE l'image : somme COMPENSÉE"
          " (Kahan/Neumaier) et preuve\n    au bit — ou écart borné et expliqué"
          " — sur les bancs d'empilement, accord d'Alain AVANT.")
    print("  ⛔ ÉCARTÉ DÉFINITIVEMENT (décision d'Alain, 21/10/2026) : trop"
          " risqué pour l'image.\n    Ce chiffrage est conservé comme TRACE,"
          " pas comme plan — ne pas le reproposer.")
    # ------------------------- [7] BANC EN VRAI (opt-in `--app`, affichage requis)
    if "--app" in argv:
        print("\n[7] BANC EN VRAI — l'application, sa config, ses VRAIS tableaux")
        print("  (aucune écriture : `config.json` est lu en copie)")
        secondes = (float(argv[argv.index("--app") + 1])
                    if len(argv) > argv.index("--app") + 1
                    and argv[argv.index("--app") + 1].replace(".", "", 1).isdigit()
                    else 90.0)
        mesurer_app(secondes=secondes)

    print("\n" + "=" * 78)
    print("CONCLUSION — le poste dominant est identifié et chiffré ; la décision"
          " float32 se prend")
    print("sur ce tableau, pas sur une intuition. Aucun fichier de l'application"
          " n'a été modifié.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
