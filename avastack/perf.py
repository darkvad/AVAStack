# -*- coding: utf-8 -*-
"""Instrumentation PERFORMANCE / MÉMOIRE — audit du 20/10/2026 (branche `OptimisationUI`).

POURQUOI CE MODULE (Phase 0 de l'audit performance/mémoire)
-----------------------------------------------------------
L'audit du 20/10/2026 a posé trois symptômes RÉELS : « ça ne va guère plus vite »
après P5, « l'interface répond quand le spinner n'est pas actif » (donc la gêne
est PENDANT le calcul), et « mémoire à 80 % de 32 Go ». Les chiffres déjà
mesurés (aperçu ≈ 250–320 ms, canvas 12–14 ms, histogrammes 45–53 ms) venaient
d'un BANC qui rejoue une image factice : ils ne disent pas combien de temps
l'application RÉELLE passe, par frame, dans chaque étage, ni combien de frames
sont PERDUES par les files bornées (`maxsize=2`).

Ce module est la Phase 0 : MESURER D'ABORD, DANS L'APPLICATION, SANS RIEN
CHANGER AU COMPORTEMENT. Il ne remplace aucun chemin : il chronomètre ceux qui
existent (`with perf.chrono("…")`), compte les évènements (`perf.compter`) et
relève la mémoire du processus (`perf.memoire_mo`, sans `psutil` — aucune
dépendance nouvelle : `ctypes` sous Windows, `/proc` sous Linux, `ru_maxrss`
sous macOS).

RÈGLE D'OR — COÛT NUL QUAND C'EST INACTIF
-----------------------------------------
Inactif (le défaut : `AVASTACK_PERF` absente), `chrono()` rend un objet UNIQUE
partagé dont `__enter__`/`__exit__` ne font RIEN : pas d'allocation, pas
d'horloge, pas de verrou. C'est ce qui permet d'instrumenter la boucle du worker
(`_worker`) sans décaler la course du banc `_test_reset_empilement_jalon76`
(leçon du jalon 106b : du code AJOUTÉ en tête de tour a déjà fait échouer ce
banc). Actif, chaque catégorie tient `n`, total, maximum et dernière durée.

ACTIVATION
----------
    python AVAStack.py --perf                     → `perf.json` À CÔTÉ du programme
    python AVAStack.py --perf-json perf-6.json    → nom imposé (relatif au dossier
                                                    courant, ou chemin complet
                                                    du dossier de votre choix)
    AVASTACK_PERF=1 [AVASTACK_PERF_JSON=…]        → même chose par l'environnement
ou, par programme : `perf.activer(chemin)`.

POURQUOI UNE OPTION EN LIGNE DE COMMANDE (ajout du 20/10/2026) : Alain a cherché
le fichier pendant un empilement et ne l'a pas trouvé — deux causes possibles, et
les deux sont levées ici : ① la variable d'environnement posée dans un terminal
ne suit pas forcément le processus lancé autrement (raccourci, .bat, menu) ;
② le fichier était écrit dans le dossier de travail (`%TEMP%`), donc invisible.
`--perf` imprime le chemin dès le démarrage et `ecrire_periodique()` réécrit le
JSON TOUTES LES 5 SECONDES (atomique), donc on peut l'ouvrir PENDANT la session —
la première version n'écrivait qu'à la fermeture, ce qui ne mesurait rien de ce
qu'on voulait voir.

L'écriture (ATOMIQUE `.part` puis `os.replace`, motif de `avastack/fiche.py`)
part à la fermeture de la fenêtre, par `atexit`, et toutes les 5 s : une mesure
ratée ne fait JAMAIS échouer l'application.

CE QUE L'INSTANTANÉ CONTIENT
----------------------------
- `chronos`  : par catégorie → n, total_ms, moy_ms, max_ms, dernier_ms
- `compteurs`: évènements (frames reçues, files PLEINES, …)
- `jauges`   : dernière valeur posée (profondeur des files, stackers, octets)
- `memoire`  : rss_mo, pic_mo, rss_max_mo, pic_max_mo
- `attente`  : par fenêtre instrumentée → mur, CPU du fil et PART D'ATTENTE
- `contexte` : version, plateforme, python, horodatage, durée

MESURER L'ATTENTE, PAS SEULEMENT LA DURÉE (v2.98.3, 21/10/2026)
--------------------------------------------------------------
Un nombre comme « `tick_avant` = 64 ms par tour » ne dit pas si le fil
d'interface TRAVAILLE ou ATTEND. Les deux hypothèses mènent à des correctifs
opposés (dégraisser `_tick` contre borner les fils natifs d'OpenCV), donc il
faut les SÉPARER avant d'écrire une ligne d'optimisation. Le module fournit
pour cela trois primitives qui vont ensemble :

    t = perf.t0()          # départ MURAL (perf_counter)
    c = perf.t0_cpu()      # départ CPU DU FIL APPELANT (time.thread_time)
    …travail…
    perf.duree("tick_avant", t)               # le mur (inchangé)
    perf.duree_attente("tick_avant", t, c)    # CPU du fil + ATTENTE

`time.thread_time()` compte le temps CPU consommé par CE fil seulement : le
temps où il est prêt mais que l'OS ne planifie pas (famine) ou qu'il attend le
GIL n'y figure PAS. L'écart `mur − CPU` est donc de l'ATTENTE, quelle qu'en
soit la cause — c'est exactement le chiffre qui manquait le 21/10/2026
(`cpu_s` du processus à 1 270 s pour ~550 s de travail mesuré).

REPLI MULTIPLATEFORME : `time.thread_time()` existe depuis Python 3.7 sous
Windows et Linux, mais macOS ne le fournit qu'à partir de Python 3.13. Sur une
plateforme sans horloge de fil, `t0_cpu()` rend None et `duree_attente()` ne
pose RIEN : le mur reste mesuré, aucune exception ne remonte (`cpu_fil_disponible()`
dit lequel des deux cas on est, et `contexte.cpu_fil` le consigne dans le JSON).

Banc : `bancs/_test_phase0_perf.py` (mécanique du module + câblage réel vérifié
par AST, aucun écran nécessaire).
"""

import atexit
import json
import os
import platform
import sys
import threading
import time
from typing import Any

# ---------------------------------------------------------------- état global
# Toutes les écritures passent par `_VERROU` : les chronos sont alimentés par le
# fil d'interface ET par le fil d'acquisition (et, demain, par un fil de rendu
# hors écran) — un dict alimenté par plusieurs fils sans verrou perdrait des
# mesures de façon silencieuse.
_VERROU = threading.Lock()
_CHRONOS: dict[str, dict[str, float]] = {}
_COMPTEURS: dict[str, int] = {}
_JAUGES: dict[str, Any] = {}
_MEMOIRE: dict[str, float] = {"rss_max_mo": 0.0, "pic_max_mo": 0.0,
                              "rss_mo": 0.0, "pic_mo": 0.0}
_ACTIF = False
_CHEMIN_JSON: str | None = None
_T_DEBUT = time.time()


def actif() -> bool:
    """L'instrumentation compte-t-elle ? (défaut : NON — coût nul en production)."""
    return _ACTIF


def activer(chemin: str | None = None) -> bool:
    """Arme l'instrumentation ; `chemin` non vide ⇒ écriture JSON à l'arrêt.

    Idempotent : un second appel ne réinitialise PAS les compteurs (appeler
    `activer()` deux fois ne doit pas perdre la première moitié de la session).
    """
    global _ACTIF, _CHEMIN_JSON
    _ACTIF = True
    if chemin:
        _CHEMIN_JSON = os.path.abspath(str(chemin))
    return _ACTIF


def desactiver() -> None:
    """Désarme (les mesures déjà accumulées restent lisibles)."""
    global _ACTIF
    _ACTIF = False


def chemin_json() -> str:
    """Chemin du JSON armé ("" si l'instrumentation n'écrit pas de fichier).

    Publique parce que c'est CE QUE L'UTILISATEUR CHERCHE : le fichier vivait
    dans le dossier de travail (souvent `%TEMP%`), donc introuvable à l'œil nu —
    l'application l'affiche au démarrage et le journal le note.
    """
    return _CHEMIN_JSON or ""


def chemin_defaut() -> str:
    """Chemin par défaut du `perf.json` : dossier de l'APPLICATION, sinon travail.

    POURQUOI ce choix (20/10/2026) : le fichier était écrit dans le dossier de
    travail (`%TEMP%` sous Windows), donc invisible — « je ne vois pas de
    perf.json ». On écrit donc À CÔTÉ du programme quand c'est possible (c'est
    là qu'on le cherche), et on retombe sur le dossier de travail quand le
    dossier de l'application est en lecture seule (installation « Program
    Files », paquet système). L'écriture d'essai est UNE fois, au démarrage.
    """
    try:
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        essai = os.path.join(racine, ".perf_ecriture.tmp")
        with open(essai, "w", encoding="utf-8") as f:
            f.write("")
        os.remove(essai)
        return os.path.join(racine, "perf.json")
    except Exception:                     # noqa: BLE001 (dossier non inscriptible)
        pass
    try:
        from . import travail
        return os.path.join(travail.dossier_travail(), "perf.json")
    except Exception:                     # noqa: BLE001
        return ""


def note_etat() -> str:
    """Écrit AU JOURNAL l'état de l'instrumentation (une ligne, au démarrage).

    POURQUOI : un `perf.json` absent n'a que deux causes — instrumentation
    INACTIVE (variable non transmise au processus) ou fichier écrit ailleurs.
    Une ligne au journal rend les deux cas lisibles sans deviner.
    """
    if _ACTIF:
        texte = ("instrumentation performance ACTIVE → %s"
                 % (_CHEMIN_JSON or "mémoire seule, aucun fichier"))
    else:
        texte = ("instrumentation performance INACTIVE "
                 "(relancer avec « AVAStack.py --perf » ou AVASTACK_PERF=1)")
    try:
        from . import journal
        journal.note("perf", texte)
    except Exception:                     # noqa: BLE001 (journal indisponible)
        pass
    return texte


def reinitialiser() -> None:
    """Vide chronos, compteurs et jauges (les bancs partent d'un état propre)."""
    global _T_DEBUT
    with _VERROU:
        _CHRONOS.clear()
        _COMPTEURS.clear()
        _JAUGES.clear()
        _MEMOIRE.update(rss_max_mo=0.0, pic_max_mo=0.0, rss_mo=0.0, pic_mo=0.0)
        _T_DEBUT = time.time()


# --------------------------------------------------------------------- chronos
class _ChronoInactif:
    """Chrono PARTAGÉ de l'état inactif : aucune allocation, aucun compteur.

    Un objet unique et SANS état se ré-entre sans danger (fil d'interface et
    fil d'acquisition l'utilisent en même temps) : `__enter__` rend l'objet,
    `__exit__` ne fait rien.
    """
    __slots__ = ()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def arreter(self) -> None:      # tolérance : ne lève jamais
        return None


_INACTIF = _ChronoInactif()


class _Chrono:
    """Chrono d'une catégorie : la durée est ajoutée à la sortie du `with`."""
    __slots__ = ("_cat", "_t0", "_arme")

    def __init__(self, categorie: str):
        self._cat = categorie
        self._t0 = time.perf_counter()
        self._arme = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.arreter()
        return False

    def arreter(self) -> None:
        """Ajoute la durée écoulée (idempotent : deux appels n'ajoutent qu'une fois)."""
        if not self._arme:
            return
        self._arme = False
        _ajouter(self._cat, (time.perf_counter() - self._t0) * 1000.0)


def _ajouter(categorie: str, duree_ms: float) -> None:
    """Ajoute une durée (ms) à une catégorie — SEUL point d'écriture des chronos."""
    with _VERROU:
        case = _CHRONOS.get(categorie)
        if case is None:
            _CHRONOS[categorie] = {"n": 1.0, "total_ms": duree_ms,
                                   "max_ms": duree_ms,
                                   "dernier_ms": duree_ms}
        else:
            case["n"] += 1.0
            case["total_ms"] += duree_ms
            case["dernier_ms"] = duree_ms
            if duree_ms > case["max_ms"]:
                case["max_ms"] = duree_ms


def chrono(categorie: str):
    """Chronomètre `categorie` : `with perf.chrono("ui_rendu"): …`.

    INACTIF ⇒ objet partagé sans effet (aucun coût) ; ACTIF ⇒ chrono réel.
    """
    if not _ACTIF:
        return _INACTIF
    return _Chrono(categorie)


def duree(categorie: str, depart: float | None) -> None:
    """Ajoute une durée déjà mesurée (`depart` = valeur de `perf.t0()`).

    Pour les points où envelopper le code d'un `with` serait intrusif (ou quand
    un `try/finally` existe déjà) : `t = perf.t0()` … `perf.duree("x", t)`.
    `depart` peut être None (instrumentation inactive) : no-op.
    """
    if not _ACTIF or depart is None:
        return
    _ajouter(categorie, (time.perf_counter() - depart) * 1000.0)


def t0() -> float | None:
    """Instant de départ, ou None si l'instrumentation est INACTIVE.

    Permet un point d'appel d'UNE ligne, sans `if perf.actif():` autour.
    """
    return time.perf_counter() if _ACTIF else None


# --------------------------------------- CPU DU FIL vs MUR : l'attente (v2.98.3)
# POURQUOI (21/10/2026, relevé `perf-5` de la branche `OptimisationUI`) : après
# l'étape 1b le fil Tk n'applique plus qu'un rendu déjà calculé (2,2 s au total
# pour 84 rendus), et pourtant `tick_avant` a DOUBLÉ (24,5 → 64,0 ms par tour)
# alors que le travail mesuré dedans vaut 6 ms. Deux lectures opposées restent
# possibles — « `_tick` est devenu plus lourd » ou « le fil Tk n'obtient plus de
# cœur (fils natifs d'OpenCV, 14, jamais bornés) » — et elles n'appellent PAS le
# même correctif. `time.thread_time()` tranche : il ne compte que le temps CPU
# du fil APPELANT, jamais le temps où il est prêt mais non planifié.
_CPU_FIL_OK: bool | None = None          # None = pas encore testé


def _cpu_fil() -> float | None:
    """CPU consommé par le fil APPELANT (secondes), None si non mesurable ici.

    La disponibilité est testée UNE fois (macOS ne fournit `thread_time()` qu'à
    partir de Python 3.13) puis mémorisée : appelable à chaque tour de boucle.
    """
    global _CPU_FIL_OK
    if _CPU_FIL_OK is None:
        try:
            time.thread_time()
            _CPU_FIL_OK = True
        except Exception:                 # noqa: BLE001 (plateforme sans horloge de fil)
            _CPU_FIL_OK = False
    if not _CPU_FIL_OK:
        return None
    try:
        return time.thread_time()
    except Exception:                     # noqa: BLE001 (jamais fatal)
        return None


def cpu_fil_disponible() -> bool:
    """Le CPU du fil appelant est-il mesurable sur cette plateforme ?"""
    return _cpu_fil() is not None


def t0_cpu() -> float | None:
    """Départ du CPU DU FIL, jumeau de `t0()` ; None si inactif ou non mesurable.

    Même contrat que `t0()` : point d'appel d'UNE ligne, aucun `if perf.actif():`
    autour, et None quand l'instrumentation est inactive (coût nul).
    """
    return _cpu_fil() if _ACTIF else None


def duree_attente(base: str, depart_mur: float | None,
                  depart_cpu: float | None) -> None:
    """Pose `<base>_cpu` et `<base>_attente` (= mur − CPU du fil) pour `base`.

    Se pose À CÔTÉ du chrono du MUR (`duree(base, depart_mur)` ou un `with
    chrono(base)`) : le mur n'est pas recompté ici, seule la part d'ATTENTE est
    ajoutée. `attente` est bornée à 0 (l'horloge de fil peut paraître « en
    avance » de quelques microsecondes après un arrondi système).

    No-op si `depart_mur` ou `depart_cpu` est None — c'est le cas INACTIF, et
    c'est aussi le cas d'une plateforme sans `time.thread_time()` (macOS
    antérieur à Python 3.13) : le mur reste mesuré, l'attente est simplement
    inconnue plutôt que fausse.
    """
    if not _ACTIF or depart_mur is None or depart_cpu is None:
        return
    cpu = _cpu_fil()
    if cpu is None:
        return
    mur_ms = (time.perf_counter() - depart_mur) * 1000.0
    cpu_ms = (cpu - depart_cpu) * 1000.0
    _ajouter(base + "_cpu", cpu_ms)
    _ajouter(base + "_attente", max(0.0, mur_ms - cpu_ms))


# ------------------------------------------- occupation du fil d'empilement
# Phase 0 bis (20/10/2026) : « le fil d'interface met 60 ms par tour » a DEUX
# explications opposées — du travail Tk dans `_tick_corps`, ou l'attente du GIL
# pendant que l'empilement travaille sur ses bandes. Les deux se séparent par une
# seule mesure : la MÊME durée, classée selon qu'un empilement était en cours ou
# non. Le worker pose le drapeau (deux affectations) ; le fil d'interface le lit.
_OCCUPE = False


def occupe(valeur: bool) -> None:
    """Pose/relâche le drapeau « un empilement est en cours » (worker)."""
    global _OCCUPE
    _OCCUPE = bool(valeur)


def est_occupe() -> bool:
    """Un empilement est-il en cours ? (lu par le fil d'interface)."""
    return _OCCUPE


# --------------------------------------------------------- compteurs et jauges
def compter(nom: str, n: int = 1) -> None:
    """Incrémente un compteur d'évènements (no-op si inactif)."""
    if not _ACTIF:
        return
    with _VERROU:
        _COMPTEURS[nom] = _COMPTEURS.get(nom, 0) + int(n)


def poser_gauge(nom: str, valeur: Any) -> None:
    """Pose une JAUGE : dernière valeur lue (profondeur de file, nb de stackers…)."""
    if not _ACTIF:
        return
    with _VERROU:
        _JAUGES[nom] = valeur



# -------------------------------------------------------------------- mémoire
def _lecteur_memoire():
    """Rend `f() -> (rss_mo, pic_mo)` pour la plateforme, ou None.

    Aucune dépendance nouvelle : `ctypes` + API système sous Windows, `/proc`
    sous Linux, `resource` sous macOS. La sonde est choisie UNE fois (premier
    appel) et mise en cache : elle est appelée à chaque frame.
    """
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            class _PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD),
                            ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t),
                            ("PrivateUsage", ctypes.c_size_t)]

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            try:                              # Windows Vista+ : K32…
                _fn = kernel32.K32GetProcessMemoryInfo
            except AttributeError:            # repli : psapi historique
                _fn = ctypes.WinDLL("psapi").GetProcessMemoryInfo
            _fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC),
                            wintypes.DWORD]
            _fn.restype = wintypes.BOOL
            _proc = kernel32.GetCurrentProcess()

            def _windows():
                pmc = _PMC()
                pmc.cb = ctypes.sizeof(_PMC)
                if not _fn(_proc, ctypes.byref(pmc), pmc.cb):
                    return (0.0, 0.0)
                mo = 1024.0 * 1024.0
                return (pmc.WorkingSetSize / mo, pmc.PeakWorkingSetSize / mo)

            return _windows
        except Exception:                     # noqa: BLE001 (sonde optionnelle)
            return None

    if sys.platform.startswith("linux"):
        try:
            with open("/proc/self/statm", "r", encoding="ascii") as f:
                f.read(1)                     # la sonde doit ÉCHOUER maintenant
        except OSError:
            return None                       # /proc absent (conteneur, etc.)

        def _linux():
            # `os.sysconf` n'existe PAS sous Windows : `getattr` évite à la fois
            # le plantage (on n'est ici que sous Linux) et une annotation
            # `pyright: ignore` (le garde-fou exige 0 erreur sur ce module).
            sysconf: Any = getattr(os, "sysconf", None)
            pages = 4096
            if sysconf is not None:
                try:
                    pages = int(sysconf("SC_PAGE_SIZE"))
                except (TypeError, ValueError, OSError):
                    pages = 4096
            rss = 0
            try:
                with open("/proc/self/statm", "r", encoding="ascii") as f:
                    champs = f.read().split()
                rss = int(champs[1]) * int(pages)
            except (OSError, IndexError, ValueError):
                rss = 0
            pic = 0
            try:
                with open("/proc/self/status", "r", encoding="ascii") as f:
                    for ligne in f:
                        if ligne.startswith("VmHWM:"):
                            pic = int(ligne.split()[1]) * 1024
                            break
            except (OSError, ValueError, IndexError):
                pic = rss
            mo = 1024.0 * 1024.0
            return (rss / mo, pic / mo)

        return _linux

    # macOS (et tout POSIX avec `resource`) : `ru_maxrss` est le PIC ; il est en
    # OCTETS sous macOS et en KILOOCTETS sous Linux (traité plus haut).
    try:
        import resource

        # `resource` est POSIX : sous Windows il n'existe même pas (on n'entre
        # donc jamais ici), et `getattr` évite une annotation `pyright: ignore`
        # que le garde-fou refuserait sur ce module.
        _getrusage = getattr(resource, "getrusage")
        _rss_self = getattr(resource, "RUSAGE_SELF")

        def _posix():
            pic = float(_getrusage(_rss_self).ru_maxrss)
            if sys.platform == "darwin":
                pic_mo = pic / (1024.0 * 1024.0)
            else:
                pic_mo = pic / 1024.0
            return (pic_mo, pic_mo)           # pas de RSS courant sans /proc

        return _posix
    except Exception:                         # noqa: BLE001
        return None


_LECTEUR: Any = "?"          # « ? » = sonde non choisie ; None = indisponible


def _sonde():
    global _LECTEUR
    if _LECTEUR == "?":
        _LECTEUR = _lecteur_memoire()
    return _LECTEUR


def memoire_mo() -> tuple[float, float]:
    """(RSS courant, pic RSS) en MÉGAOCTETS ; (0, 0) si la sonde manque."""
    f = _sonde()
    if f is None:
        return (0.0, 0.0)
    try:
        return f()
    except Exception:                         # noqa: BLE001
        return (0.0, 0.0)


# ------------------------------------------------------------------- CPU réel
def _lecteur_cpu():
    """Rend `f() -> secondes CPU` (user + noyau) pour la plateforme, ou None.

    POURQUOI (20/10/2026, 3e relevé) : le MÊME travail NumPy a coûté **deux fois
    plus cher** d'une session à l'autre (étirement 1 166 → 2 426 ms, empilement
    2 656 → 5 360 ms). Deux causes possibles : la machine était chargée par un
    AUTRE programme, ou nous la saturons nous-mêmes (bandes d'empilement +
    débruitage + GraXpert). Le rapport `secondes CPU / durée murale` donne le
    nombre de CŒURS réellement occupés par le processus : c'est ce qui tranche.
    """
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            _fn = kernel32.GetProcessTimes
            _fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                            ctypes.POINTER(wintypes.FILETIME),
                            ctypes.POINTER(wintypes.FILETIME),
                            ctypes.POINTER(wintypes.FILETIME)]
            _fn.restype = wintypes.BOOL
            _proc = kernel32.GetCurrentProcess()

            def _windows():
                cree, sorti = wintypes.FILETIME(), wintypes.FILETIME()
                noyau, user = wintypes.FILETIME(), wintypes.FILETIME()
                if not _fn(_proc, ctypes.byref(cree), ctypes.byref(sorti),
                           ctypes.byref(noyau), ctypes.byref(user)):
                    return 0.0
                # FILETIME : 100 ns par unité, deux DWORD (bas puis haut).
                total = ((noyau.dwHighDateTime << 32) | noyau.dwLowDateTime) \
                    + ((user.dwHighDateTime << 32) | user.dwLowDateTime)
                return total / 1e7

            return _windows
        except Exception:                 # noqa: BLE001 (sonde optionnelle)
            return None
    try:
        import resource

        _getrusage = getattr(resource, "getrusage")
        _rss_self = getattr(resource, "RUSAGE_SELF")

        def _posix():
            u = _getrusage(_rss_self)
            return float(u.ru_utime) + float(u.ru_stime)   # type: ignore[attr-defined]

        return _posix
    except Exception:                     # noqa: BLE001
        return None


_LECTEUR_CPU: Any = "?"


def cpu_s() -> float:
    """Secondes CPU consommées par le PROCESSUS (0 si la sonde manque)."""
    global _LECTEUR_CPU
    if _LECTEUR_CPU == "?":
        _LECTEUR_CPU = _lecteur_cpu()
    f = _LECTEUR_CPU
    if f is None:
        return 0.0
    try:
        return float(f())
    except Exception:                     # noqa: BLE001
        return 0.0


def echantillon_memoire() -> None:
    """Relève RSS + pic et met à jour les maxima (no-op si inactif)."""
    if not _ACTIF:
        return
    rss, pic = memoire_mo()
    with _VERROU:
        _MEMOIRE["rss_mo"] = rss
        _MEMOIRE["pic_mo"] = pic
        if rss > _MEMOIRE["rss_max_mo"]:
            _MEMOIRE["rss_max_mo"] = rss
        if pic > _MEMOIRE["pic_max_mo"]:
            _MEMOIRE["pic_max_mo"] = pic



# ------------------------------------------------- comptage des gros tableaux
def taille_tableaux(obj: Any, profondeur: int = 2) -> tuple[int, int]:
    """(octets, nombre) des `numpy.ndarray` atteignables depuis `obj`.

    Sert à CHIFFRER les accumulateurs de l'empileur (§3 de l'audit : `sum`,
    `sumsq`, `wsum`, `_moy`, `_sig`, `_dif`, `_pix`, `_masq`, `_buf`) sans
    importer `stacking` ici et sans supposer leurs noms : on parcourt `__dict__`,
    dicts et listes jusqu'à `profondeur` niveaux. Un tableau RENCONTRÉ est
    toujours compté, même au dernier niveau. Aucun tableau n'est copié.
    """
    try:
        import numpy as _np
    except Exception:                     # noqa: BLE001 (numpy est requis)
        return (0, 0)
    vus: set[int] = set()
    octets = 0
    nb = 0

    def visite(o: Any, p: int) -> None:
        nonlocal octets, nb
        if o is None or id(o) in vus:
            return
        vus.add(id(o))
        if isinstance(o, _np.ndarray):
            octets += int(o.nbytes)
            nb += 1
            return
        if p <= 0:
            return
        if isinstance(o, dict):
            for v in list(o.values()):
                visite(v, p - 1)
        elif isinstance(o, (list, tuple, set)):
            for v in list(o):
                visite(v, p - 1)
        elif hasattr(o, "__dict__"):
            try:
                for v in list(vars(o).values()):
                    visite(v, p - 1)
            except Exception:             # noqa: BLE001 (objet exotique)
                return

    visite(obj, profondeur)
    return (octets, nb)


def jauger_empileur(stacker: Any) -> None:
    """Pose `stackers_nb` / `stackers_octets` / `stackers_mo` / `..._nb_tableaux`.

    Accepte un `LiveStacker` (mono) comme un `CompositeStacker` (dict
    `stackers` par rôle) : le parcours générique de `taille_tableaux` couvre les
    deux cas, y compris un futur empileur qui renommerait ses buffers. La
    profondeur 3 est celle du motif le plus profond
    (`CompositeStacker.__dict__` → `stackers` → `LiveStacker` → tableaux).
    """
    if not _ACTIF:
        return
    octets, nb_tab = taille_tableaux(stacker, profondeur=3)
    nb_stackers = 1
    try:
        pile = getattr(stacker, "stackers", None)
        if isinstance(pile, dict):
            nb_stackers = len(pile)
    except Exception:                     # noqa: BLE001
        pass
    with _VERROU:
        _JAUGES["stackers_nb"] = nb_stackers
        _JAUGES["stackers_octets"] = octets
        _JAUGES["stackers_mo"] = round(octets / (1024.0 * 1024.0), 1)
        _JAUGES["stackers_nb_tableaux"] = nb_tab



# ------------------------------------------------------------------ instantané
def _version() -> str:
    try:
        from . import AVASTACK_VERSION
        return AVASTACK_VERSION
    except Exception:                     # noqa: BLE001 (banc isolé)
        return "?"


def _bilan_attente(bruts: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Bilan « mur / CPU du fil / attente » par fenêtre instrumentée.

    Lit les chronos BRUTS (déjà sous verrou par l'appelant : ne PAS rappeler
    `_ajouter` ni reprendre `_VERROU`, qui n'est pas réentrant). Une fenêtre est
    retenue dès qu'elle a son chrono MURAL et son jumeau `_cpu` — c'est-à-dire
    partout où `duree_attente()` a été posée. La PART D'ATTENTE est le chiffre
    qui décide : proche de 1, le fil ATTEND ; proche de 0, il TRAVAILLE.
    """
    bilan: dict[str, dict[str, float]] = {}
    for cat, case in bruts.items():
        if not cat.endswith("_cpu"):
            continue
        base = cat[:-4]
        mur = (bruts.get(base) or {}).get("total_ms")
        attente = (bruts.get(base + "_attente") or {}).get("total_ms")
        if mur is None or attente is None or mur <= 0.0:
            continue
        bilan[base] = {"mur_ms": round(mur, 1),
                       "cpu_ms": round(case["total_ms"], 1),
                       "attente_ms": round(attente, 1),
                       "part_attente": round(attente / mur, 3)}
    return bilan


def postes_memoire(obj: Any, profondeur: int = 4, max_postes: int = 12,
                   exclure: tuple[str, ...] = ("stacker",),
                   seuil_octets: int = 65536) -> dict[str, Any]:
    """{attribut de PREMIER niveau → octets de tableaux}, sans double compte.

    POURQUOI (21/10/2026, lot « nommer le résiduel ») : la réconciliation de
    `_mesure_memoire_stackers.py` laissait **637,7 Mio** que la jauge des
    empileurs ne voyait pas. Pour les NOMMER, il faut un inventaire de
    l'APPLICATION elle-même : on range chaque tableau sous l'attribut de premier
    niveau qui le tient (`aligner`, `calib`, `_hist_brut`, `disp`, …) et on
    déduplique **par `id()`** — une image aliasée par deux attributs (leçon du
    « Go inexpliqué ») n'est comptée qu'une fois, sous le PREMIER attribut
    rencontré (ordre d'affectation de l'objet : c'est le plus souvent celui qui
    la possède réellement, les alias venant après).

    CE QUI N'EST PAS TRAVERSÉ (et pourquoi) : on ne descend que dans les
    conteneurs (dict/list/tuple/set) et dans les objets du PROJET
    (`type(o).__module__` commence par « avastack »). Tk, PIL, astropy et
    numpy-scalaires sont ignorés : les parcourir coûterait des secondes et ne
    contient aucun tableau de l'application (le tas Tk se mesure au RSS, pas
    ici).

    `profondeur` compte les SAUTS (4 couvre `App.__dict__` → objet → dict →
    tableau). `seuil_octets` évite le bruit : en dessous, les tableaux sont
    agrégés sous « petits tableaux ».

    → {"postes": {nom: octets} (top `max_postes` + « (autres) »),
       "total_octets": int, "nb_tableaux": int}
    """
    try:
        import numpy as _np
    except Exception:                         # noqa: BLE001 (numpy requis)
        return {"postes": {}, "total_octets": 0, "nb_tableaux": 0}
    vus: set[int] = set()
    par_nom: dict[str, int] = {}
    nb = [0]

    def visite(o: Any, p: int, nom: str) -> None:
        if o is None:
            return
        if isinstance(o, _np.ndarray):
            if id(o) in vus:
                return
            vus.add(id(o))
            nb[0] += 1
            n = int(o.nbytes)
            cle = nom if n >= seuil_octets else "petits tableaux"
            par_nom[cle] = par_nom.get(cle, 0) + n
            return
        if isinstance(o, (dict, list, tuple, set, frozenset)):
            if id(o) in vus or p <= 0:
                return
            vus.add(id(o))
            valeurs = list(o.values()) if isinstance(o, dict) else list(o)
            for v in valeurs:
                visite(v, p - 1, nom)
            return
        module = type(o).__module__ or ""
        if not module.startswith("avastack"):
            return                            # Tk, PIL, astropy… : au RSS
        if id(o) in vus or p <= 0:
            return
        vus.add(id(o))
        try:
            membres = list(vars(o).items())
        except Exception:                     # noqa: BLE001 (objet exotique)
            return
        for k, v in membres:
            visite(v, p - 1, nom)

    try:
        attributs = list(vars(obj).items())    # ordre d'affectation : l'OWNER
    except Exception:                         # noqa: BLE001      d'abord
        return {"postes": {}, "total_octets": 0, "nb_tableaux": 0}
    for nom, valeur in attributs:
        if nom in exclure:
            continue                          # compté par `jauger_empileur`
        visite(valeur, profondeur, nom)
    total = sum(par_nom.values())
    top = dict(sorted(par_nom.items(), key=lambda kv: -kv[1])[:max_postes])
    autres = total - sum(top.values())
    if autres > 0:
        top["(autres)"] = autres
    return {"postes": top, "total_octets": total, "nb_tableaux": nb[0]}


def jauger_postes(obj: Any, profondeur: int = 4, max_postes: int = 12,
                  exclure: tuple[str, ...] = ("stacker",)) -> None:
    """Pose `postes` (Mio par attribut), `postes_mo` et `postes_nb_tableaux`.

    À appeler sur une cadence LENTE (20 s) : le parcours coûte quelques
    millisecondes et n'a de sens qu'en régime établi. Coût nul hors `--perf`.
    """
    if not _ACTIF:
        return
    r = postes_memoire(obj, profondeur=profondeur, max_postes=max_postes,
                       exclure=exclure)
    with _VERROU:
        _JAUGES["postes"] = {k: round(v / (1024.0 * 1024.0), 1)
                             for k, v in r["postes"].items()}
        _JAUGES["postes_mo"] = round(r["total_octets"] / (1024.0 * 1024.0), 1)
        _JAUGES["postes_nb_tableaux"] = r["nb_tableaux"]


def instantane() -> dict[str, Any]:
    """Photographie JSON-compatible des mesures accumulées."""
    if _ACTIF:
        echantillon_memoire()          # l'instantané relève la mémoire DU MOMENT
    with _VERROU:
        chronos = {}
        for cat, c in _CHRONOS.items():
            n = float(c["n"]) or 1.0
            chronos[cat] = {"n": int(c["n"]),
                            "total_ms": round(c["total_ms"], 3),
                            "moy_ms": round(c["total_ms"] / n, 3),
                            "max_ms": round(c["max_ms"], 3),
                            "dernier_ms": round(c["dernier_ms"], 3)}
        _cpu = cpu_s()
        _duree = max(1.0, time.time() - _T_DEBUT)
        doc = {
            "contexte": {
                "version": _version(),
                "python": sys.version.split()[0],
                "plateforme": platform.platform(),
                "debut": time.strftime("%Y-%m-%dT%H:%M:%S",
                                       time.localtime(_T_DEBUT)),
                "duree_s": round(time.time() - _T_DEBUT, 1),
                "actif": _ACTIF,
                # v2.98.3 : dit si le CPU du FIL est mesurable ici (faux sur
                # macOS antérieur à Python 3.13) — sans quoi l'absence des
                # chronos `*_cpu` se lirait à tort comme « travail nul ».
                "cpu_fil": cpu_fil_disponible(),
            },
            "chronos": chronos,
            "attente": _bilan_attente(_CHRONOS),
            "compteurs": dict(_COMPTEURS),
            "jauges": dict(_JAUGES),
            "memoire": {k: round(v, 1) for k, v in _MEMOIRE.items()},
            "cpu": {"cpu_s": round(_cpu, 1),
                    "cores_moyens": round(_cpu / _duree, 2),
                    "threads": threading.active_count()},
        }
    return doc


def resume() -> str:
    """Une LIGNE compacte pour le journal (les chiffres qui décident)."""
    doc = instantane()
    ch = doc["chronos"]
    cp = doc["compteurs"]
    j = doc["jauges"]
    m = doc["memoire"]
    morceaux = []
    for cle, libelle in (("ui_tick", "tick"),
                         ("ui_tick_libre", "  à vide"),
                         ("ui_tick_occupe", "  pendant empilement"),
                         ("tick_avant", "    avant file"),
                         ("tick_fits", "      ouverture FITS"),
                         ("tick_mesures", "      mesures disque"),
                         ("tick_reglages", "      lecture réglages"),
                         ("tick_conso", "    file+rendu"),
                         ("tick_etat", "      ligne d'état"),
                         ("tick_apres", "    après file"),
                         ("tick_vues", "      synchro vues"),
                         ("tick_traitee", "      vue traitée"),
                         ("ui_rendu", "rendu UI (application)"),
                         # 1b (20/10/2026) : le CALCUL a quitté le fil Tk — ces
                         # trois chronos mesurent le fil de rendu, pas `_tick`.
                         ("fil_rendu", "rendu (fil)"),
                         ("fil_etirement", "  étirement (fil)"),
                         ("fil_histogrammes", "  histogrammes (fil)"),
                         ("ui_histogrammes", "  histogrammes (tracé)"),
                         ("ui_dessin", "  dessin"),
                         ("empilement", "empilement"),
                         ("rendu_pousse", "rendu poussé"),
                         ("lecture_frame", "lecture")):
        c = ch.get(cle)
        if c:
            morceaux.append("%s n=%d moy=%.1f ms max=%.1f ms"
                            % (libelle, c["n"], c["moy_ms"], c["max_ms"]))
    if cp:
        morceaux.append("compteurs=" + ", ".join(
            "%s:%d" % (k, v) for k, v in sorted(cp.items())))
    if j.get("stackers_nb") is not None:
        morceaux.append("stackers=%s (%s Mo, %s tableaux)"
                        % (j.get("stackers_nb"), j.get("stackers_mo"),
                           j.get("stackers_nb_tableaux")))
    if j.get("file_q") is not None:
        morceaux.append("file_q=%s" % j.get("file_q"))
    morceaux.append("RSS %.0f Mo (pic %.0f Mo)" % (m["rss_max_mo"],
                                                   m["pic_max_mo"]))
    # v2.98.3 : LE chiffre qui tranche entre « le fil travaille » et « le fil
    # attend » — une ligne par fenêtre instrumentée par `duree_attente()`.
    for base, bilan in sorted((doc.get("attente") or {}).items()):
        morceaux.append("%s : attente %.0f %% (mur %.1f s, CPU du fil %.1f s)"
                        % (base, bilan["part_attente"] * 100.0,
                           bilan["mur_ms"] / 1000.0, bilan["cpu_ms"] / 1000.0))
    c = doc.get("cpu") or {}
    if c:
        morceaux.append("CPU %.0f s = %.2f cœur(s) — %s fil(s)"
                        % (c.get("cpu_s", 0.0), c.get("cores_moyens", 0.0),
                           c.get("threads", 0)))
    return " | ".join(morceaux)


def ecrire_json(chemin: str | None = None) -> str:
    """Écrit l'instantané (ATOMIQUE) ; rend le chemin, ou "" en cas d'échec.

    TOLÉRANT (motif de `avastack/fiche.py`) : une mesure ratée ne doit jamais
    faire échouer la fermeture de l'application. Sans `chemin` ni chemin armé
    par `activer()`, RIEN n'est écrit (aucune écriture surprise).
    """
    cible = chemin or _CHEMIN_JSON
    if not cible:
        return ""
    try:
        dossier = os.path.dirname(os.path.abspath(cible)) or "."
        os.makedirs(dossier, exist_ok=True)
        tmp = cible + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(instantane(), f, ensure_ascii=False, indent=1)
        os.replace(tmp, cible)
        return cible
    except Exception:                     # noqa: BLE001 (jamais fatal)
        return ""


# ------------------------------------------------- écriture PÉRIODIQUE (live)
_INTERVALLE_ECRITURE_S = 5.0
_DERNIERE_ECRITURE = 0.0


def ecrire_periodique(intervalle_s: float | None = None) -> str:
    """Réécrit le JSON au plus toutes les `intervalle_s` secondes (5 s par défaut).

    POURQUOI (défaut RÉEL constaté le 20/10/2026) : la première version n'écrivait
    qu'à la FERMETURE — inutilisable pour regarder une session EN COURS (« je ne
    vois pas de perf.json alors que l'empilement de M33 est en cours »). Le JSON
    est donc réécrit régulièrement, de façon ATOMIQUE : on peut l'ouvrir à tout
    moment sans risquer de lire un fichier à moitié écrit.

    Appelé depuis la boucle d'interface (une fois par tick) : inactif, c'est un
    simple test de booléen ; actif, c'est UNE écriture de quelques kilo-octets
    toutes les 5 s (jamais à chaque frame).
    """
    global _DERNIERE_ECRITURE
    if not _ACTIF or not _CHEMIN_JSON:
        return ""
    intervalle = (_INTERVALLE_ECRITURE_S if intervalle_s is None
                  else float(intervalle_s))
    maintenant = time.monotonic()
    if _DERNIERE_ECRITURE and (maintenant - _DERNIERE_ECRITURE) < intervalle:
        return ""
    _DERNIERE_ECRITURE = maintenant
    return ecrire_json()


# ------------------------------------------------- activation par l'environnement
def _depuis_environnement() -> None:
    """Active si `AVASTACK_PERF` est posée (opt-in explicite, jamais par défaut).

    Valeurs vraies : 1 / true / oui / yes / on (casse indifférente). Le chemin
    JSON vient de `AVASTACK_PERF_JSON`, sinon `chemin_defaut()` (dossier de
    l'application, à défaut le dossier de travail) — aucun chemin propre à un OS
    n'est codé en dur.
    """
    valeur = os.environ.get("AVASTACK_PERF", "").strip().lower()
    if valeur not in ("1", "true", "oui", "yes", "on"):
        return
    chemin = os.environ.get("AVASTACK_PERF_JSON", "").strip()
    if not chemin:
        chemin = chemin_defaut()
    activer(chemin or None)


def _a_l_arret() -> None:
    """`atexit` : une ligne au journal + le JSON si un chemin est armé."""
    if not _ACTIF:
        return
    try:
        from . import journal
        journal.note("perf", resume())
    except Exception:                     # noqa: BLE001
        pass
    ecrire_json()


_depuis_environnement()
atexit.register(_a_l_arret)

