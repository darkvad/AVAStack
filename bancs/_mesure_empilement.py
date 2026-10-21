# -*- coding: utf-8 -*-
"""MESURE — DÉCOMPOSITION de l'étage `empilement` (v2.98.9, branche `OptimisationUI`).

POURQUOI CE BANC AVANT LE CODE (protocole d'`AVANCEMENT.md`) : `perf-9` mesure
`empilement` à **2 938 ms/frame** — de loin le premier poste de CPU restant — mais
c'est un TOTAL. On ne sait pas qui pèse quoi entre ① le filtre anti-floues,
② l'extraction de canal, ③ l'ARCHIVAGE (écriture FITS, I/O) et le SCORE qualité
(détection d'étoiles), ④ la CRÉATION de l'empileur + la 1re référence,
⑤ l'ALIGNEMENT (ORB+RANSAC, repli corrélation de phase), ⑥ la reprojection
`warpAffine`, ⑦ le REJET (kappa-sigma / Winsorized) et ⑧ la MOYENNE. Choisir un
levier avant de savoir reviendrait à jouer aux dés : ce banc MESURE.

CE QU'IL FAIT — et rien d'autre
  - il arme l'instrumentation `perf` de l'application, dont les SOUS-CHRONOS
    `empilement_*` posés en v2.98.9 dans `core/worker.py` (opt-in, coût nul
    hors `--perf`) ;
  - il construit la VRAIE `App` (config HERMÉTIQUE : jamais le vrai
    `config.json`) et rejoue de VRAIES brutes — dossier surveillé réel, ou
    composition multi-dossiers réelle — à travers la VRAIE méthode
    `_worker_empiler_frame`, dans le MÊME bloc que le worker
    (`perf.occupe(True)` + `perf.chrono("empilement")`) ;
  - il publie le tableau de décomposition ET le RÉSIDUEL non nommé
    (`empilement` − somme des sous-chronos : `note_alignement`, ligne d'état,
    trace des rôles inactive, `_recaler_ha`), puis écrit le relevé JSON à côté
    du banc (`bancs/_mesure_empilement.json`, rejouable et comparable).

CE QU'IL NE FAIT PAS — volontairement
  - il ne modifie AUCUN fichier de l'application et ne change AUCUN pixel : le
    calcul traversé est exactement celui de production ;
  - il ne remplace pas une mesure en réel : `python AVAStack.py --perf` sur une
    vraie session donne les MÊMES sous-chronos, avec le vrai disque (partage
    réseau) et le vrai jeu de données. Ce banc est la lecture de référence
    REPRODUCTIBLE, disponible sans session d'acquisition.

NEUTRALISATIONS (elles servent la MESURE, elles sont affichées au démarrage)
  - `ref_refresh = 0` et `_veut_restack → False` : ni rafraîchissement
    automatique de référence, ni re-stack automatique. Ils ne font PAS partie
    de `empilement` (ils vivent dans `_worker`), et leurs re-stacks
    supplémentaires brouilleraient la moyenne par frame ;
  - le FILTRE ANTI-FLOUES reste ACTIF par défaut (c'est un étage à mesurer) —
    `--sans-filtre-flou` le coupe pour comparer.

USAGE
  python bancs/_mesure_empilement.py                       # OSC réel par défaut
  python bancs/_mesure_empilement.py --dossier CHEMIN --max 20
  python bancs/_mesure_empilement.py --racine CHEMIN --compo LRGB+Ha --max 10
  python bancs/_mesure_empilement.py --role L=DOSSIER_L --role R=DOSSIER_R
                                     --role G=DOSSIER_G --role B=DOSSIER_B
                                     --compo LRGB --max 10
  python bancs/_mesure_empilement.py --synthetique --cotes 1200x1800 --max 6
  python bancs/_mesure_empilement.py --methode kappa            # levier n°5
  python bancs/_mesure_empilement.py --autotest                 # mécanique seule
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import argparse
import json
import os
import sys
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
import avastack.ui.app as ui
from avastack import perf
from avastack.cameras.folder import FolderCamera
from avastack.cameras.multifolder import MultiFolderCamera
from avastack.processing.composition import COMPOSITIONS

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Dossier réel par défaut : les brutes OSC de référence (Player One Uranus-C
# PRO, IMX585, 3856×2180, 180 s) — le jeu qui répond le plus vite.
DEFAUT_DOSSIER = r"C:\Astro\Images_Stack\180.00s\LIGHT"
SORTIE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "_mesure_empilement.json")

# SOUS-CHRONOS posés en v2.98.9 dans `_worker_empiler_frame` — l'ORDRE est
# celui du déroulé d'une frame (sert à lire le tableau).
SOUS_CHRONOS = (
    ("empilement_flou", "filtre anti-floues (FWHM + score étoiles)"),
    ("empilement_canal", "extraction du canal du rôle"),
    ("empilement_archive", "ARCHIVAGE FITS (I/O disque)"),
    ("empilement_score", "score qualité (détection d'étoiles)"),
    ("empilement_creation", "création empileur + 1re référence"),
    ("empilement_rejeu", "rejeu d'ancre (re-stack de démarrage)"),
    ("empilement_align", "ALIGNEMENT (ORB+RANSAC / phase)"),
    ("empilement_warp", "reprojection warpAffine"),
    ("empilement_rejet", "REJET + accumulation (stacker.add)"),
    ("empilement_moyenne", "moyenne (sum/wsum)"),
)
NOMS_SOUS = tuple(n for n, _ in SOUS_CHRONOS)


def cotes(txt):
    """« 2180x3856 » → (2180, 3856) — tolérant aux séparateurs."""
    for sep in ("x", "X", "*", "×", " "):
        if sep in str(txt):
            h, _, w = str(txt).partition(sep)
            return int(h), int(w)
    raise SystemExit(f"cotes illisibles : {txt!r} (attendu 2180x3856)")


def _etoiles_synth(h, w, n=140, graine=7):
    """Champ d'étoiles FIGÉ (une seule graine) — la même pour toutes les frames."""
    rng = np.random.default_rng(graine)
    return [(float(rng.uniform(12, w - 12)), float(rng.uniform(12, h - 12)),
             float(rng.uniform(0.4, 0.9))) for _ in range(n)]


def champ_synthetique(h, w, idx, etoiles):
    """Le MÊME champ d'étoiles TRANSLATÉ d'une dérive sous-pixel par frame.

    POURQUOI ce n'est pas un champ aléatoire par frame : un champ DIFFÉRENT à
    chaque frame ferait REFUSER l'alignement (c'est correct, mais le banc ne
    mesurerait alors que la cascade de refus — `warp` et `rejet` ne seraient
    jamais atteints, et l'autotest ne prouverait plus rien). Ici l'alignement
    DOIT réussir : les étages chauds sont réellement mesurés.
    """
    rng = np.random.default_rng(1000 + idx)      # bruit PROPRE à chaque frame
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.full((h, w), 0.05, np.float32)
    dx, dy = 0.4 * idx, 0.3 * idx
    for (x, y, a) in etoiles:
        cy, cx = y + dy, x + dx
        img += (a * np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2)
                             / (2.0 * 1.3 ** 2)))).astype(np.float32)
    img += rng.normal(0.0, 0.003, (h, w)).astype(np.float32)
    return np.clip(img, 0.0, 1.0).astype(np.float32)


def frames_du_dossier(dossier):
    """FITS du dossier (NON récursif : `rejected` reste dehors), ordre mtime."""
    try:
        noms = [e.path for e in os.scandir(dossier)
                if e.is_file() and e.name.lower().endswith(
                    (".fits", ".fit", ".fts"))]
    except OSError as exc:
        raise SystemExit(f"dossier illisible : {dossier} ({exc})")
    return sorted(noms, key=os.path.getmtime)


# ============================================================================
# LA VRAIE APPLICATION, EN CONFIG HERMÉTIQUE
# ============================================================================
def preparer_app():
    """→ (root, app) : vraie `App` sur une fenêtre RETIRÉE, config hermétique.

    Règle du projet (cf. les autres bancs) : `ui.CONFIG` et `ui.sauver_config`
    sont interceptés pour que le banc n'écrive JAMAIS le vrai `config.json`
    (l'archivage des maîtres de calibration, en v2.98.7, l'a rendu obligatoire).
    """
    ui.CONFIG = {}
    ui.sauver_config = lambda *a, **k: None
    # `_dire()` est une boîte MODALE : elle bloquerait le banc indéfiniment.
    ui.App._dire = lambda self, *a, **k: None
    root = tk.Tk()
    root.withdraw()
    app = ui.App(root)
    # Neutralisations (elles ne concernent PAS `empilement`, cf. docstring).
    app.ref_refresh = 0
    app._veut_restack = lambda: False
    return root, app


def camera_dossier(dossier):
    """Dossier surveillé RÉEL (mêmes règles de complétude que l'application)."""
    if not os.path.isdir(dossier):
        raise SystemExit(f"dossier introuvable : {dossier}")
    return FolderCamera(dossier, process_existing=True, poll=0.05)


def role_dossier(txt):
    """« B=C:\\…\\B » → ("B", "C:\\…\\B") — un dossier de rôle EXPLICITE.

    POURQUOI : les vraies arborescences d'acquisition n'ont pas forcément un
    sous-dossier par rôle à la racine (chez Alain : `…/60.00/-10.00/90/25/L`).
    `--racine` ne suffit donc pas toujours ; `--role` dit exactement où lire.
    """
    role, sep, dossier = str(txt).partition("=")
    role, dossier = role.strip(), dossier.strip()
    if not sep or not role:
        raise SystemExit(f"--role illisible : {txt!r} (attendu ROLE=DOSSIER)")
    if not os.path.isdir(dossier):
        raise SystemExit(f"--role {role} : dossier absent — {dossier}")
    return (role, dossier)


def camera_roles(paires, compo):
    """Composition à partir de couples (rôle, dossier) EXPLICITES."""
    if len(paires) < 2:
        raise SystemExit("--role : au moins DEUX rôles (sinon --dossier suffit"
                         " pour un empilement simple)")
    print(f"  composition {compo} : rôles {[r for r, _ in paires]}")
    return MultiFolderCamera(paires, process_existing=True, poll=0.05)


def camera_compo(racine, compo):
    """Composition : `MultiFolderCamera` sur les sous-dossiers NOMMÉS PAR RÔLE.

    Les rôles attendus viennent de `COMPOSITIONS` (source de vérité de
    l'application) ; un rôle absent du disque est simplement IGNORÉ, avec son
    nom affiché — jamais de devinette silencieuse.
    """
    if compo not in COMPOSITIONS:
        raise SystemExit(f"composition inconnue : {compo!r} "
                         f"(connues : {', '.join(COMPOSITIONS)})")
    attendus = list(COMPOSITIONS[compo]["roles"])
    presents = [r for r in attendus
                if os.path.isdir(os.path.join(racine, r))]
    if not presents:
        raise SystemExit(f"aucun sous-dossier de rôle sous {racine} "
                         f"(attendu : {', '.join(attendus)})")
    absents = [r for r in attendus if r not in presents]
    print(f"  composition {compo} : rôles présents {presents}"
          + (f" · ABSENTS {absents}" if absents else ""))
    return MultiFolderCamera([(r, os.path.join(racine, r)) for r in presents],
                             process_existing=True, poll=0.05)


def poser_mode(app, cam, compo):
    """Pose la caméra et l'état de session, comme le fait `_start()`."""
    app.camera = cam
    # `_start()` OUVRE la source : sans `open()`, `FolderCamera.read()` rend
    # None indéfiniment (`_running` reste faux) et le banc ne mesurerait rien.
    ouvrir = getattr(cam, "open", None)
    if callable(ouvrir):
        ouvrir()
    app._mode_compo = ui.App._mode_compo_de(cam)
    if app._mode_compo:
        app._compo_nom = compo
        app.archives = {}
        app._scores_par_role = {}
    else:
        app.archive = ui.ArchiveFrames()
        app._scores = []
    app.stacker = None
    app.aligner.reset()
    app.aligner_ha.reset()
    app._ha_ref_posee = False
    app._ha_ref_bad = 0
    app._ref_bad = 0
    app._ref_frames = 0
    app.bad_frames = 0
    app.bad_frames_par_role = {}
    app.floues_rejetees = 0
    app._ancre_role = app._ancre_idx = app._ancre_score = None
    app.align_info = ""


def vider_archives(app):
    """Supprime les dossiers d'archive de session (rien ne reste sur le disque)."""
    try:
        if app._mode_compo:
            for arch in (app.archives or {}).values():
                arch.vider()
        else:
            app.archive.vider()
    except Exception as exc:              # noqa: BLE001 (nettoyage, jamais fatal)
        print(f"  (nettoyage des archives : {exc})")


# ============================================================================
# LE REJEU — MÊME BLOC QUE LE WORKER, VRAIE MÉTHODE, VRAIES BRUTES
# ============================================================================
def rejouer(app, max_frames, synthetique=None):
    """Rejoue `max_frames` brutes dans la VRAIE `_worker_empiler_frame`.

    Le bloc `perf.occupe(True)` + `perf.chrono("empilement")` est celui de
    `_worker` (l. 720-726) : le TOTAL mesuré ici est donc comparable, au
    millième près, à celui d'une session réelle.

    `synthetique` = (h, w) : au lieu de lire des fichiers, on fabrique un champ
    d'étoiles translaté (aucune donnée nécessaire — mécanique du banc).
    """
    n, last_good = 0, None
    refus, floues, formes = 0, 0, set()
    etoiles = _etoiles_synth(*synthetique) if synthetique else None
    t_mur = time.perf_counter()
    while n < max_frames:
        if synthetique is not None:
            frame = champ_synthetique(synthetique[0], synthetique[1], n, etoiles)
            role = None
        else:
            lu = app.camera.read(timeout=2.0)
            if lu is None:
                print("  (source épuisée)")
                break
            frame, role = lu if app._mode_compo else (lu, None)
        if not app._source_stacks():
            # Exactement la chaîne du worker : calibration AVANT l'empilement
            # (sans dark/flat chargé, `apply` ne fait que normaliser le dtype).
            frame = app.calib.apply(frame, role=role)
        formes.add(tuple(np.shape(frame)))
        t0 = time.perf_counter()
        perf.occupe(True)
        try:
            with perf.chrono("empilement"):
                sauter, last_good, _stack = app._worker_empiler_frame(
                    frame, role, last_good, t0)
        finally:
            perf.occupe(False)
        n += 1
        if sauter:
            floues += 1
        if app.align_info.startswith("refus"):
            refus += 1
        print(f"    frame {n:3d}" + (f" [{role}]" if role else "")
              + (f"  floues={app.floues_rejetees}" if sauter else ""),
              end="\r" if n < max_frames else "\n")
    return {"n": n, "refus": refus, "floues": floues,
            "duree_mur_s": time.perf_counter() - t_mur,
            "formes": sorted(formes)}


# ============================================================================
# LE TABLEAU — QUI PÈSE QUOI, ET LE RÉSIDUEL NON NOMMÉ
# ============================================================================
def tableau(doc, etat, cotes_px, reglages):
    """Affiche la décomposition lue dans `perf.instantane()` → dict du relevé."""
    ch = doc.get("chronos") or {}
    tot = ch.get("empilement") or {}
    n = int(tot.get("n") or 0)
    tot_moy = float(tot.get("moy_ms") or 0.0)
    if n <= 0 or tot_moy <= 0.0:
        print("\n  AUCUN chrono `empilement` : rien n'a été empilé — rien à"
              " décomposer.")
        return None
    print(f"\n[1] TOTAL `empilement` — {n} frame(s) mesurée(s)")
    print(f"    moyenne {tot_moy:9.1f} ms/frame · maximum "
          f"{float(tot.get('max_ms') or 0.0):9.1f} ms · total "
          f"{float(tot.get('total_ms') or 0.0) / 1000.0:.1f} s")
    if cotes_px:
        h, w = cotes_px
        print(f"    géométrie des brutes : {w}×{h} = {h * w / 1e6:.1f} Mpx"
              "  (celle des BRUTES ; `source_px` de `perf.json` est l'image"
              " RECADRÉE)")
    print(f"    rejeu mural {etat['duree_mur_s']:.1f} s · refus d'alignement "
          f"{etat['refus']} · rejets flous {etat['floues']}")
    print(f"    réglages mesurés : rejet {reglages['methode']} "
          f"fenêtre {reglages['fenetre']} kappa {reglages['kappa']} · "
          f"filtre anti-floues {'ACTIF' if reglages['flou'] else 'COUPÉ'}")

    print("\n[2] DÉCOMPOSITION")
    print("    TOUS les postes sont ramenés à LA MÊME base : le nombre d'appels de"
          " `empilement`")
    print("    (un poste qui n'arrive qu'une fois — création, rejeu — est donc"
          " réparti sur toutes")
    print("    les frames : c'est ainsi que la somme des postes égale le total).")
    print(f"    {'poste':<24s} {'ms/frame':>9s} {'% total':>8s} {'n':>5s}"
          f"  étage")
    tot_ms = float(tot.get("total_ms") or 0.0)
    somme, releve = 0.0, {}
    for nom, libelle in SOUS_CHRONOS:
        c = ch.get(nom)
        if not c:
            continue
        total = float(c.get("total_ms") or 0.0)
        nn = int(c.get("n") or 0)
        somme += total
        releve[nom] = {"total_ms": total, "n": nn,
                       "par_frame_ms": total / n,
                       "part_total": (total / tot_ms) if tot_ms > 0 else 0.0,
                       "max_ms": float(c.get("max_ms") or 0.0)}
        print(f"    {nom:<24s} {total / n:9.1f} {100.0 * total / tot_ms:7.1f} % "
              f"{nn:5d}  {libelle}")
    residuel = tot_ms - somme
    print(f"    {'RÉSIDUEL non nommé':<24s} {residuel / n:9.1f} "
          f"{100.0 * residuel / tot_ms:7.1f} %")
    print(f"    {'SOMME des sous-chronos':<24s} {somme / n:9.1f} "
          f"{100.0 * somme / tot_ms:7.1f} %")
    print("    (résiduel : `note_alignement`, ligne d'état, trace des rôles"
          " INACTIVE, `_recaler_ha`)")

    # Le poste DOMINANT est la seule chose à retenir d'un relevé.
    if releve:
        dominant = max(releve.items(), key=lambda kv: kv[1]["total_ms"])
        print(f"\n[3] POSTE DOMINANT : {dominant[0]} — "
              f"{dominant[1]['par_frame_ms']:.1f} ms/frame "
              f"({100.0 * dominant[1]['part_total']:.1f} % du total)")
    return {"total_ms": tot_ms, "total_ms_par_frame": tot_ms / n, "total_n": n,
            "sous": releve, "residuel_ms": residuel,
            "residuel_ms_par_frame": residuel / n,
            "somme_sous_ms": somme,
            "etat": etat, "cotes_px": list(cotes_px) if cotes_px else None,
            "reglages": reglages}


def autotest(app, max_frames=8):
    """Mécanique SEULE (aucune donnée) : les sous-chronos existent et se somment.

    Vérifie que la décomposition est MESURABLE : ① le total `empilement` est
    posé, ② chaque étage attendu apparaît, ③ la somme des sous-chronos ne
    dépasse jamais le total (le résiduel ne peut pas être négatif), ④ au moins
    une frame est réellement empilée (sinon `warp`/`rejet` ne seraient pas
    mesurés et le banc ne prouverait rien).
    """
    ok = True

    def verifie(cond, msg):
        nonlocal ok
        ok = ok and bool(cond)
        print(("  OK    " if cond else "  ÉCHEC ") + msg)

    print("[AUTOTEST] champ d'étoiles synthétique — mécanique de la mesure")
    app.rejeter_flou = False               # déterministe (aucune décision floue)
    perf.reinitialiser()
    perf.activer(None)
    etat = rejouer(app, max_frames, synthetique=(480, 640))
    doc = perf.instantane()
    ch = doc.get("chronos") or {}
    verifie(etat["n"] == max_frames,
            f"{max_frames} frames rejouées — reçu {etat['n']}")
    tot = ch.get("empilement")
    verifie(tot is not None and tot.get("n", 0) >= 1,
            "le chrono TOTAL `empilement` est posé")
    attendus = ("empilement_flou", "empilement_canal", "empilement_archive",
                "empilement_score", "empilement_creation", "empilement_align",
                "empilement_moyenne")
    manquants = [n for n in attendus if n not in ch]
    verifie(not manquants, f"les étages attendus sont mesurés — manquants "
                           f"{manquants}")
    verifie(app.stacker is not None and getattr(app.stacker, "n", 0) >= 1,
            "au moins une frame est réellement empilée (sinon rien à mesurer)")
    for nom in ("empilement_warp", "empilement_rejet"):
        verifie(nom in ch, f"l'étage chaud `{nom}` est mesuré")
    somme = sum(float((ch.get(nm) or {}).get("total_ms") or 0.0)
                for nm in NOMS_SOUS)
    tot_ms = float(tot.get("total_ms") or 0.0)
    verifie(somme <= tot_ms * 1.0001,
            f"la somme des sous-chronos ({somme:.1f} ms) ne dépasse pas le "
            f"total ({tot_ms:.1f} ms)")
    verifie(tot_ms - somme >= 0.0,
            f"le RÉSIDUEL est positif ({tot_ms - somme:.1f} ms)")
    print("  → " + ("AUTOTEST VERT" if ok else "AUTOTEST ROUGE"))
    return ok


class _CameraMuette:
    """Source sans fichier (autotest / synthétique) : `_cadence_dossier()` FAUX.

    Même bouchon que `bancs/_diag_bascule_stf_blanc.py` : aucune I/O, et le
    worker se comporte comme devant une CAMÉRA (pas de scan de dossier).
    """

    pending = 0
    last_file = ""

    def read(self, timeout=1.0):
        return None


def ecrire_json(chemin, doc):
    """Écrit le relevé en JSON, ATOMIQUEMENT (motif `avastack/fiche.py`)."""
    chemin = os.path.abspath(str(chemin))
    try:
        part = chemin + ".part"
        with open(part, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1, ensure_ascii=False)
        os.replace(part, chemin)
        print(f"\n  relevé écrit : {chemin}")
    except OSError as exc:
        print(f"\n  (relevé NON écrit : {exc})")


# ============================================================================
# LIGNE DE COMMANDE
# ============================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Décompose l'étage `empilement` (mesure seule, AUCUN pixel "
                    "changé) sur de vraies brutes ou un champ synthétique.")
    ap.add_argument("--dossier", default=DEFAUT_DOSSIER,
                    help=f"dossier de brutes FITS (défaut : {DEFAUT_DOSSIER})")
    ap.add_argument("--racine", default="",
                    help="racine d'une COMPOSITION (sous-dossiers par rôle)")
    ap.add_argument("--role", action="append", default=[], metavar="ROLE=DOSSIER",
                    help="dossier d'un rôle (répétable, ≥ 2) — pour les "
                         "arborescences qui n'ont pas un dossier par rôle à la "
                         "racine ; remplace --racine")
    ap.add_argument("--compo", default="LRGB+Ha",
                    help="composition à jouer avec --racine (défaut : LRGB+Ha)")
    ap.add_argument("--max", type=int, default=12, help="frames à rejouer")
    ap.add_argument("--synthetique", action="store_true",
                    help="champ d'étoiles fabriqué (aucune donnée nécessaire)")
    ap.add_argument("--cotes", default="480x640",
                    help="géométrie du champ synthétique (défaut : 480x640)")
    ap.add_argument("--sans-filtre-flou", action="store_true",
                    help="coupe le filtre anti-floues (comparaison)")
    ap.add_argument("--methode", default="", help="rejet : kappa | winsorized")
    ap.add_argument("--fenetre", type=int, default=0, help="fenêtre du rejet")
    ap.add_argument("--kappa", type=float, default=0.0, help="kappa du rejet")
    ap.add_argument("--sortie", default=SORTIE, help="chemin du relevé JSON")
    ap.add_argument("--autotest", action="store_true",
                    help="mécanique seule (champ synthétique, aucune donnée)")
    args = ap.parse_args(argv)

    root, app = preparer_app()
    try:
        if args.autotest:
            poser_mode(app, _CameraMuette(), "Mono")
            ok = autotest(app, max_frames=8)
            return 0 if ok else 1

        if args.role:
            paires = [role_dossier(r) for r in args.role]
            cam, compo = camera_roles(paires, args.compo), args.compo
        elif args.racine:
            cam, compo = camera_compo(args.racine, args.compo), args.compo
        elif args.synthetique:
            cam, compo = _CameraMuette(), "Mono"
        else:
            cam, compo = camera_dossier(args.dossier), "Mono"
            print(f"  dossier : {args.dossier} — "
                  f"{len(frames_du_dossier(args.dossier))} FITS")
        poser_mode(app, cam, compo)
        if args.sans_filtre_flou:
            app.rejeter_flou = False
        if args.methode:
            app.rejet_methode = args.methode
        if args.fenetre:
            app.rejet_fenetre = int(args.fenetre)
        if args.kappa:
            app.kappa = float(args.kappa)
        reglages = {"methode": getattr(app, "rejet_methode", "?"),
                    "fenetre": int(getattr(app, "rejet_fenetre", 0) or 0),
                    "kappa": getattr(app, "kappa", None),
                    "flou": bool(getattr(app, "rejeter_flou", False))}
        print(f"  mode : {'COMPOSITION ' + compo if app._mode_compo else 'simple'}"
              f" · CFA {images.CFA_MODE} · rejet {reglages['methode']}"
              f" (fenêtre {reglages['fenetre']}, kappa {reglages['kappa']})"
              f" · filtre anti-floues "
              f"{'ACTIF' if reglages['flou'] else 'COUPÉ'}")

        perf.reinitialiser()
        perf.activer(None)
        etat = rejouer(app, max(1, int(args.max)),
                       synthetique=(cotes(args.cotes) if args.synthetique
                                    else None))
        cotes_px = None
        if etat["formes"]:
            forme = etat["formes"][0]
            cotes_px = (int(forme[0]), int(forme[1]))
        releve = tableau(perf.instantane(), etat, cotes_px, reglages)
        if releve is None:
            return 1
        releve["contexte"] = {
            "version": ui.AVASTACK_VERSION,
            "horodatage": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": ("composition " + args.compo if args.racine
                       else ("champ synthétique" if args.synthetique
                             else args.dossier)),
            "cfa": images.CFA_MODE,
        }
        ecrire_json(args.sortie, releve)
        return 0
    finally:
        try:
            vider_archives(app)
        finally:
            root.destroy()


if __name__ == "__main__":
    raise SystemExit(main())

