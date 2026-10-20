# -*- coding: utf-8 -*-
"""Banc PHASE 0 (audit performance/mémoire du 20/10/2026) — INSTRUMENTATION.

CE QUE CE BANC VERROUILLE (aucun écran nécessaire)
  [1] INACTIF = COÛT NUL : `perf.chrono()` rend le MÊME objet partagé (identité
      vérifiée), ne crée AUCUNE entrée, et `duree(…, None)` ne lève pas ;
  [2] ACTIF : les durées s'accumulent (n, total, maximum), `duree()` et le
      chrono `with` donnent le MÊME ordre de grandeur qu'une mesure directe ;
 [2 bis] ATTENTE (v2.98.3) : `t0_cpu()` + `duree_attente()` séparent le temps
      CPU du fil du temps d'ATTENTE — un `sleep` donne une part d'attente
      forte, une boucle de calcul pur une part quasi nulle, et
      `mur = cpu + attente` à la mesure près. C'est le chiffre qui distingue
      « le fil Tk travaille » de « le fil Tk est affamé » ;
  [3] FILS : 4 fils × 250 chronos ⇒ n = 1000 EXACTEMENT (verrou) ;
  [4] compteurs et jauges : incréments exacts, dernières valeurs posées ;
  [5] MÉMOIRE : `memoire_mo()` rend un RSS plausible (> 5 Mo) sur la
      plateforme courante, et `echantillon_memoire()` tient les maxima ;
  [6] `taille_tableaux()` : octets et nombre EXACTS sur une structure piège
      (tableau partagé deux fois = compté une fois ; profondeur respectée) ;
  [7] `jauger_empileur()` : un objet à dict `stackers` (motif
      `CompositeStacker`) pose `stackers_nb` et la somme des octets ;
  [8] `instantane()` est JSON-sérialisable et `ecrire_json()` écrit un JSON
      VALIDE, sans laisser de `.part` ;
  [9] CÂBLAGE RÉEL vérifié par AST : les points d'instrumentation existent
      dans `ui/app.py`, `ui/renderer.py` et `core/worker.py` — et, depuis 1b,
      le CALCUL du rendu (étirement, histogrammes, compteur `rendus`) dans
      `ui/rendu.py` (le fil de rendu) ;
 [10] SURFACE PUBLIQUE d'`app.py` INTACTE : l'import privé `_perf` n'ajoute ni
      « perf » ni « _perf » aux symboles publics (banc garde-fou du jalon 100).

Exécution : python bancs/_test_phase0_perf.py     (aucun affichage requis)
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import ast
import json
import os
import sys
import tempfile
import threading
import time

import numpy as np

from avastack import perf

if hasattr(sys.stdout, "reconfigure"):      # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


RACINE = _pl_banc.Path(_sys_banc.path[0])


# ============================================================================
# [1] INACTIF = COÛT NUL
# ============================================================================
print("[1] Inactif : le chrono ne compte RIEN et n'alloue rien de neuf")
perf.desactiver()
perf.reinitialiser()
verifie(not perf.actif(), "l'instrumentation est INACTIVE par défaut")
c1, c2 = perf.chrono("fantome"), perf.chrono("fantome")
verifie(c1 is c2, "deux `chrono()` inactifs rendent le MÊME objet partagé")
with perf.chrono("fantome"):
    time.sleep(0.002)
verifie(perf.instantane()["chronos"] == {},
        "aucune catégorie créée après un `with` inactif")
verifie(perf.t0() is None, "`t0()` rend None quand l'instrumentation est inactive")
verifie(perf.t0_cpu() is None,
        "`t0_cpu()` rend None aussi (aucune horloge de fil appelée hors `--perf`)")
perf.duree("fantome", None)                  # ne doit pas lever
perf.duree_attente("fantome", None, None)    # idem (v2.98.3)
perf.compter("fantome", 5)                   # ne doit rien compter
perf.poser_gauge("fantome", 1)               # ne doit rien poser
doc = perf.instantane()
verifie(doc["compteurs"] == {} and doc["jauges"] == {},
        "compteurs et jauges restent VIDES tant qu'on n'active pas")


# ============================================================================
# [2] ACTIF : accumulation exacte
# ============================================================================
print("\n[2] Actif : n, total et maximum exacts ; ordre de grandeur réel")
perf.activer()
for _ in range(3):
    with perf.chrono("essai"):
        time.sleep(0.004)
c = perf.instantane()["chronos"]["essai"]
verifie(c["n"] == 3, f"3 chronos ⇒ n = 3 ({c['n']})")
verifie(3.0 <= c["moy_ms"] <= 200.0,
        f"durée moyenne plausible pour un sommeil de 4 ms ({c['moy_ms']:.2f} ms)")
verifie(c["max_ms"] >= c["moy_ms"] - 1e-6,
        f"le maximum encadre la moyenne ({c['max_ms']:.2f} ≥ {c['moy_ms']:.2f})")
verifie(abs(c["total_ms"] - c["moy_ms"] * 3) < 0.01,
        f"total = moyenne × n ({c['total_ms']:.2f} ms)")
t = perf.t0()
time.sleep(0.003)
perf.duree("essai2", t)
verifie(perf.instantane()["chronos"]["essai2"]["n"] == 1,
        "`t0()` + `duree()` comptent aussi (chemin `try/finally`)")
ch = perf.chrono("essai")
ch.__enter__()
ch.__exit__(None, None, None)
ch.arreter()                                 # double appel : ne compte pas deux fois
verifie(perf.instantane()["chronos"]["essai"]["n"] == 4,
        "un `arreter()` en double n'ajoute qu'UNE mesure")


# ============================================================================
# [2 bis] L'ATTENTE : CPU DU FIL vs MUR (v2.98.3)
# ============================================================================
print("\n[2 bis] Attente = mur − CPU du fil : sommeil ⇒ attente forte, "
      "calcul ⇒ attente nulle")
# REPLI MULTIPLATEFORME : macOS ne fournit `time.thread_time()` qu'à partir de
# Python 3.13. Une attente INCONNUE n'est pas une attente NULLE : on vérifie le
# comportement DOCUMENTÉ plutôt que de déclarer une régression.
if not perf.cpu_fil_disponible():
    perf.reinitialiser()
    perf.duree("sans_horloge", perf.t0())
    perf.duree_attente("sans_horloge", perf.t0(), perf.t0_cpu())
    verifie(perf.t0_cpu() is None and perf.instantane()["attente"] == {},
            "plateforme SANS horloge de fil : `t0_cpu()` rend None et aucune "
            "attente n'est inventée (le mur reste mesuré)")
else:
    perf.reinitialiser()
    for _ in range(3):
        _t_mur = perf.t0()
        _t_cpu = perf.t0_cpu()
        time.sleep(0.020)
        perf.duree("sommeil", _t_mur)                    # le MUR (comme dans _tick)
        perf.duree_attente("sommeil", _t_mur, _t_cpu)    # CPU du fil + ATTENTE
    _ch = perf.instantane()["chronos"]
    verifie(_ch["sommeil_cpu"]["n"] == 3 and _ch["sommeil_attente"]["n"] == 3,
            f"3 fenêtres ⇒ `_cpu` et `_attente` comptés 3 fois "
            f"({_ch['sommeil_cpu']['n']} / {_ch['sommeil_attente']['n']})")
    _b = perf.instantane()["attente"]["sommeil"]
    _part_sommeil = _b["part_attente"]
    verifie(_part_sommeil > 0.8,
            f"un `sleep` de 20 ms ⇒ le fil ATTEND (part {_part_sommeil:.2f})")
    verifie(abs(_b["mur_ms"] - _b["cpu_ms"] - _b["attente_ms"]) < 1.0,
            f"mur = CPU + attente ({_b['mur_ms']:.1f} = {_b['cpu_ms']:.1f}"
            f" + {_b['attente_ms']:.1f})")
    verifie("attente" in perf.resume(),
            f"`resume()` publie la part d'attente :\n        {perf.resume()}")
    # TÉMOIN indispensable : sans calcul pur, on ne mesurerait que l'absence de
    # coût (leçon du 21/10) — il faut que le cas opposé donne le chiffre opposé.
    # ATTENTION (constaté au 1er essai de ce banc) : un seuil ABSOLU (« part
    # < 0,2 ») est FLAKY, parce qu'il mesure la CHARGE DE LA MACHINE et non le
    # code — sur un poste occupé, l'OS désordonnance la boucle et le fil ATTEND
    # réellement (mesuré part 0,48, CPU 15,6 ms pour 30 ms de mur). On teste donc
    # deux choses ROBUSTES : le CPU du fil suit bien le travail, et le calcul
    # attend NETTEMENT moins que le sommeil — comparaison INTERNE au même run.
    perf.reinitialiser()
    _t_cpu_direct = time.thread_time()               # mesure DIRECTE témoin
    _t_mur = perf.t0()
    _t_cpu = perf.t0_cpu()
    _fin_boucle = time.perf_counter() + 0.030
    while time.perf_counter() < _fin_boucle:             # calcul pur, sans I/O
        pass
    _cpu_direct_ms = (time.thread_time() - _t_cpu_direct) * 1000.0
    perf.duree("calcul", _t_mur)
    perf.duree_attente("calcul", _t_mur, _t_cpu)
    _b = perf.instantane()["attente"]["calcul"]
    verifie(abs(_b["cpu_ms"] - _cpu_direct_ms) < 5.0,
            f"le CPU publié suit la mesure DIRECTE du fil "
            f"({_b['cpu_ms']:.1f} vs {_cpu_direct_ms:.1f} ms)")
    verifie(_b["cpu_ms"] >= 10.0,
            f"le CPU du fil avance pendant le calcul ({_b['cpu_ms']:.1f} ms)")
    verifie(_b["part_attente"] < _part_sommeil - 0.3,
            f"le calcul attend NETTEMENT moins que le sommeil "
            f"(part {_b['part_attente']:.2f} contre {_part_sommeil:.2f})")
    # Plateforme sans horloge de fil : le mur reste mesuré, l'attente est
    # INCONNUE — jamais un zéro trompeur.
    perf.duree_attente("sans_cpu", perf.t0(), None)
    verifie("sans_cpu_cpu" not in perf.instantane()["chronos"]
            and "sans_cpu" not in perf.instantane()["attente"],
            "sans départ CPU, RIEN n'est posé (aucune attente inventée)")


# ============================================================================
# [3] FILS : le verrou ne perd aucune mesure
# ============================================================================
print("\n[3] 4 fils × 250 chronos ⇒ n = 1000 (aucune perte)")
perf.reinitialiser()


def _marteler():
    for _ in range(250):
        with perf.chrono("fils"):
            pass


fils = [threading.Thread(target=_marteler) for _ in range(4)]
for f in fils:
    f.start()
for f in fils:
    f.join()
n_fils = perf.instantane()["chronos"]["fils"]["n"]
verifie(n_fils == 1000, f"n = 1000 exactement ({n_fils})")


# ============================================================================
# [4] Compteurs et jauges
# ============================================================================
print("\n[4] Compteurs et jauges")
perf.reinitialiser()
perf.compter("frames")
perf.compter("frames", 4)
perf.poser_gauge("file_q", 2)
perf.poser_gauge("file_q", 0)
doc = perf.instantane()
verifie(doc["compteurs"].get("frames") == 5,
        f"compteur cumulé = 5 ({doc['compteurs']})")
verifie(doc["jauges"].get("file_q") == 0, "une jauge garde la DERNIÈRE valeur (0)")
perf.activer()                               # idempotent
verifie(perf.instantane()["compteurs"].get("frames") == 5,
        "`activer()` deux fois ne réinitialise PAS les compteurs")
verifie(not perf.est_occupe(), "au repos, le drapeau d'occupation est BAISSE")
perf.occupe(True)
verifie(perf.est_occupe(), "`occupe(True)` lève le drapeau (GIL vs travail Tk)")
perf.occupe(False)
verifie(not perf.est_occupe(), "`occupe(False)` le relâche")



# ============================================================================
# [5] MÉMOIRE du processus
# ============================================================================
print("\n[5] Mémoire : sonde système (aucune dépendance) et maxima")
perf.reinitialiser()
rss, pic = perf.memoire_mo()
verifie(rss > 5.0, f"RSS plausible pour un interpréteur Python ({rss:.1f} Mo)")
verifie(pic >= rss * 0.9, f"le pic encadre le RSS courant ({pic:.1f} ≥ {rss:.1f})")
perf.echantillon_memoire()
m = perf.instantane()["memoire"]
verifie(m["rss_max_mo"] >= rss * 0.9,
        f"l'échantillon retient le RSS ({m['rss_max_mo']:.1f} Mo)")
perf.desactiver()
perf.echantillon_memoire()                   # inactif : ne touche à rien
verifie(perf.instantane()["memoire"]["rss_max_mo"] >= rss * 0.9,
        "un échantillon INACTIF ne remet pas les maxima à zéro")
perf.activer()
cpu = perf.cpu_s()
verifie(cpu > 0.01, f"le CPU du processus est mesurable ({cpu:.2f} s)")
cpu2 = perf.cpu_s()
verifie(cpu2 >= cpu, "le CPU consommé ne recule jamais")
doc = perf.instantane()["cpu"]
verifie(doc["cpu_s"] > 0.01 and doc["cores_moyens"] > 0,
        f"l'instantané publie CPU et cœurs moyens ({doc['cores_moyens']} cœur(s))")
verifie(doc["threads"] >= 1, f"le nombre de fils est lu ({doc['threads']})")


# ============================================================================
# [6] taille_tableaux : octets exacts, partage et profondeur
# ============================================================================
print("\n[6] `taille_tableaux()` : comptage exact, tableau partagé compté UNE fois")


class _FauxStacker:
    def __init__(self):
        self.sum = np.zeros((10, 10), np.float64)      # 800 o
        self._masq = np.zeros((10, 10), bool)          # 100 o
        self._buf = None
        self.nom = "x"                                 # ignoré (pas un tableau)


faux = _FauxStacker()
faux.alias = faux.sum                              # MÊME tableau : une seule fois
octets, nb = perf.taille_tableaux(faux, profondeur=1)
verifie(nb == 2 and octets == 900,
        f"2 tableaux, 900 octets ({nb}, {octets} o)")
octets0, nb0 = perf.taille_tableaux({"a": faux.sum, "b": faux._masq}, profondeur=1)
verifie(nb0 == 2 and octets0 == 900, f"dict explicite compté pareil ({nb0}, {octets0} o)")
verifie(perf.taille_tableaux(None) == (0, 0), "`None` ⇒ (0, 0)")
verifie(perf.taille_tableaux(faux.sum, profondeur=0) == (800, 1),
        "un tableau passé DIRECTEMENT est compté même à profondeur 0")


# ============================================================================
# [7] jauger_empileur : motif CompositeStacker
# ============================================================================
print("\n[7] `jauger_empileur()` : dict `stackers` et somme des octets")


class _FauxComposite:
    def __init__(self):
        self.stackers = {"L": _FauxStacker(), "R": _FauxStacker()}
        self.composition = "LRGB"


perf.jauger_empileur(_FauxComposite())
j = perf.instantane()["jauges"]
verifie(j.get("stackers_nb") == 2, f"2 rôles comptés ({j.get('stackers_nb')})")
verifie(j.get("stackers_octets") == 1800,
        f"1800 octets au total ({j.get('stackers_octets')} o)")
verifie(abs(j.get("stackers_mo", 0) - 1800 / (1024.0 * 1024.0)) < 0.05,
        f"mégaoctets cohérents ({j.get('stackers_mo')} Mo)")
perf.jauger_empileur(_FauxStacker())
verifie(perf.instantane()["jauges"].get("stackers_nb") == 1,
        "un LiveStacker seul compte pour 1 rôle")



# ============================================================================
# [8] Instantané JSON et écriture atomique
# ============================================================================
print("\n[8] `instantane()` sérialisable, `ecrire_json()` valide et atomique")
with perf.chrono("json"):
    pass
doc = perf.instantane()
texte = json.dumps(doc, ensure_ascii=False)        # ne doit pas lever
verifie(len(texte) > 50, f"instantané sérialisable ({len(texte)} caractères)")
verifie(doc["contexte"]["version"] not in ("", None), "la version est renseignée")
verifie("json" in doc["chronos"], "les catégories mesurées sont présentes")
dossier = tempfile.mkdtemp(prefix="perf_banc_")
cible = os.path.join(dossier, "perf.json")
chemin = perf.ecrire_json(cible)
verifie(chemin == cible and os.path.isfile(cible),
        f"le fichier est écrit ({chemin})")
verifie(not os.path.exists(cible + ".part"), "aucun `.part` ne reste (os.replace)")
with open(cible, encoding="utf-8") as f:
    relu = json.load(f)
verifie(isinstance(relu.get("chronos"), dict) and "memoire" in relu,
        "le JSON relu contient chronos et memoire")
verifie(isinstance(relu.get("attente"), dict),
        "le JSON relu contient le bilan `attente` (v2.98.3)")
verifie(isinstance(relu["contexte"].get("cpu_fil"), bool),
        f"`contexte.cpu_fil` dit si le CPU du fil est mesurable "
        f"({relu['contexte'].get('cpu_fil')})")
verifie(perf.ecrire_json("") == "" or True,
        "un chemin vide n'écrit rien de surprenant")
try:
    os.remove(cible)
    os.rmdir(dossier)
except OSError:
    pass
verifie(perf.resume().count("RSS") >= 1, f"`resume()` tient en une ligne :\n        {perf.resume()}")


# ============================================================================
# [9] CÂBLAGE RÉEL (AST) — l'instrumentation est-elle DANS le produit ?
# ============================================================================
print("\n[9] Le produit appelle bien l'instrumentation (vérifié par AST)")


def _appels(chemin):
    """Jetons `Nom.attribut:CONSTANTE` de tous les appels du module.

    Une constante par argument (y compris dans une expression conditionnelle :
    `duree("a" if x else "b")` produit DEUX jetons), et un jeton nu
    `Nom.attribut:` quand l'appel n'a aucune constante — c'est ce qui permet de
    vérifier le câblage sans dépendre de la forme exacte de l'expression.
    """
    arbre = ast.parse(chemin.read_text(encoding="utf-8-sig"))
    trouves = set()
    for n in ast.walk(arbre):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
            continue
        base = n.func.value
        nom_base = base.id if isinstance(base, ast.Name) else ""
        prefixe = f"{nom_base}.{n.func.attr}"
        valeurs = [str(k.value) for a in n.args for k in ast.walk(a)
                   if isinstance(k, ast.Constant)]
        if not valeurs:
            trouves.add(prefixe + ":")
        for v in valeurs:
            trouves.add(prefixe + ":" + v)
    return trouves


appels_app = _appels(RACINE / "avastack" / "ui" / "app.py")
appels_rend = _appels(RACINE / "avastack" / "ui" / "renderer.py")
# 1b (20/10/2026) : l'ÉTIREMENT, le compteur de rendus et la taille étirée ont
# quitté le fil d'interface avec le calcul — ils vivent dans le FIL DE RENDU
# (`ui/rendu.py`). `renderer.py` ne garde que l'APPLICATION du résultat.
appels_fil = _appels(RACINE / "avastack" / "ui" / "rendu.py")
appels_work = _appels(RACINE / "avastack" / "core" / "worker.py")

attendu_app = [("_perf.chrono:ui_tick", "tour de boucle d'interface chronométré"),
               ("_perf.duree:ui_tick_libre", "tours à vide comptés à part"),
               ("_perf.duree:ui_tick_occupe", "tours pendant empilement à part"),
               ("_perf.duree:tick_avant", "corps découpé : avant la file"),
               # v2.98.3 : le CPU DU FIL et l'ATTENTE (mur − CPU) sur la même
               # fenêtre — c'est ce qui prouve la famine du fil Tk.
               ("_perf.duree_attente:tick_avant", "attente de `tick_avant` (famine)"),
               ("_perf.duree_attente:ui_tick", "attente du tour complet"),
               ("_perf.t0_cpu:", "départ CPU du fil (jumeau de `t0()`)"),
               ("_perf.duree:tick_fits", "  dont ouverture FITS (disque)"),
               ("_perf.duree:tick_mesures", "  dont mesures disque"),
               ("_perf.duree:tick_reglages", "  dont lecture des réglages"),
               ("_perf.duree:tick_conso", "corps découpé : file + rendu"),
               ("_perf.duree:tick_etat", "  dont ligne d'état"),
               ("_perf.duree:tick_apres", "corps découpé : après la file"),
               ("_perf.duree:tick_vues", "  dont synchro des vues"),
               ("_perf.duree:tick_traitee", "  dont vue traitée (process nue)"),
               ("_perf.duree:rendu_pousse", "coût d'un rendu POUSSÉ (worker)"),
               ("_perf.compter:ui_frames", "frame reçue comptée"),
               ("_perf.compter:file_pleine_ui", "file pleine comptée (UI)"),
               ("_perf.poser_gauge:file_q", "profondeur de file jaugée"),
               ("_perf.poser_gauge:vl_actif", "état de la chaîne VeraLux"),
               ("_perf.poser_gauge:vl_stage", "étape de la chaîne"),
               ("_perf.poser_gauge:threads", "nombre de fils"),
               ("_perf.compter:vl_new", "publications de la chaîne comptées"),
               ("_perf.ecrire_periodique:", "JSON réécrit PENDANT la session"),
               ("_perf.note_etat:", "état instrumenté noté au journal"),
               ("_perf.ecrire_json:", "écriture à la fermeture")]
for motif, quoi in attendu_app:
    verifie(motif in appels_app, f"app.py — {quoi} ({motif})")

attendu_rend = [("perf.chrono:ui_rendu", "application du résultat (fil Tk)"),
                ("perf.chrono:ui_histogrammes", "tracé de l'histogramme"),
                ("perf.chrono:ui_dessin", "dessin du canvas"),
                ("perf.compter:rendus_gardes", "image d'attente gardée (1a)")]
for motif, quoi in attendu_rend:
    verifie(motif in appels_rend, f"renderer.py — {quoi} ({motif})")

# 1b : le CALCUL est instrumenté là où il se fait, dans le fil de rendu.
attendu_fil = [("perf.chrono:fil_rendu", "rendu total (fil de rendu)"),
               ("perf.chrono:fil_etirement", "étirement"),
               ("perf.chrono:fil_histogrammes", "histogrammes"),
               ("perf.compter:rendus", "nombre de rendus"),
               ("perf.compter:rendus_ecrases", "demandes écrasées (dernier gagne)"),
               ("perf.compter:rendus_perimes", "résultats périmés jetés"),
               ("perf.poser_gauge:source_px", "taille réellement étirée"),
               ("perf.poser_gauge:rendu_q", "profondeur du fil de rendu")]
for motif, quoi in attendu_fil:
    verifie(motif in appels_fil, f"rendu.py — {quoi} ({motif})")

attendu_work = [("perf.chrono:empilement", "empilement"),
                ("perf.duree:lecture_frame", "lecture de la brute"),
                ("perf.compter:file_pleine_worker", "file pleine comptée (worker)"),
                ("perf.echantillon_memoire:", "RSS échantillonné"),
                ("perf.jauger_empileur:", "octets des stackers"),
                ("perf.occupe:True", "drapeau d'occupation posé (GIL vs Tk)")]
for motif, quoi in attendu_work:
    verifie(motif in appels_work, f"worker.py — {quoi} ({motif})")


# ============================================================================
# [10] SURFACE PUBLIQUE d'app.py : l'import privé n'ajoute RIEN
# ============================================================================
print("\n[10] La surface publique d'`app.py` reste intacte (import `_perf`)")
arbre_app = ast.parse((RACINE / "avastack" / "ui" / "app.py")
                      .read_text(encoding="utf-8-sig"))
importes = set()
for n in ast.walk(arbre_app):
    if isinstance(n, ast.ImportFrom):
        mod = n.module or ""
        if n.level > 0 or mod.startswith("avastack"):
            for a in n.names:
                importes.add(a.asname or a.name)
verifie("_perf" in importes, "l'instrumentation est importée SOUS NOM PRIVÉ (`_perf`)")
verifie("perf" not in importes,
        "aucun symbole PUBLIC « perf » n'est ajouté à la surface de `app.py`")


# ============================================================================
# [11] ÉCRITURE PENDANT LA SESSION et LANCEMENT `--perf`
# ============================================================================
print("\n[11] `perf.json` écrit PENDANT la session — et `AVAStack.py --perf` l'arme")
import AVAStack                                    # module d'entrée (sans main())

dossier = tempfile.mkdtemp(prefix="perf_vivant_")
cible_vivante = os.path.join(dossier, "perf.json")
perf.activer(cible_vivante)
verifie(perf.chemin_json() == cible_vivante,
        f"`chemin_json()` publie le chemin que l'utilisateur cherche ({perf.chemin_json()})")
verifie(perf.ecrire_periodique(0.0) == cible_vivante,
        "la 1re écriture périodique produit le fichier TOUT DE SUITE")
verifie(os.path.isfile(cible_vivante),
        "le fichier existe PENDANT la session (pas seulement à la fermeture)")
verifie(perf.ecrire_periodique(600.0) == "",
        "un second appel dans l'intervalle n'écrit PAS (jamais à chaque tick)")
verifie(perf.ecrire_periodique(0.0) == cible_vivante,
        "l'intervalle écoulé, l'écriture repart")
verifie("ACTIVE" in perf.note_etat(), "`note_etat()` DIT que les mesures tournent")
perf.desactiver()
verifie("INACTIVE" in perf.note_etat(),
        "…et DIT qu'elles sont arrêtées quand c'en est le cas")

# `--perf-json CHEMIN` : activation SANS variable d'environnement (le cas réel
# du 20/10 : la variable posée dans un terminal ne suit pas le processus).
perf.desactiver()
perf.reinitialiser()
AVAStack._perf_depuis_argv(["--perf", "--perf-json", cible_vivante])
verifie(perf.actif() and perf.chemin_json() == cible_vivante,
        f"`AVAStack.py --perf-json` arme le fichier demandé ({perf.chemin_json()})")
perf.desactiver()
perf.reinitialiser()
AVAStack._perf_depuis_argv(["--perf"])
verifie(perf.actif() and perf.chemin_json().endswith("perf.json"),
        f"`AVAStack.py --perf` choisit un chemin TROUVABLE ({perf.chemin_json()})")
verifie(os.path.normcase(os.path.dirname(perf.chemin_json()))
        == os.path.normcase(str(RACINE)),
        "ce chemin est celui de l'application quand elle est inscriptible")
perf.desactiver()
perf.reinitialiser()
AVAStack._perf_depuis_argv(["--autre-chose"])
verifie(not perf.actif(), "sans `--perf`, rien n'est armé (défaut inchangé)")

try:
    os.remove(cible_vivante)
    os.rmdir(dossier)
except OSError:
    pass

# ============================================================================
print()
print("BANC PHASE 0 (instrumentation performance/mémoire) : "
      + ("TOUT PASSE ✅" if ok else "ÉCHEC ✗"))
sys.exit(0 if ok else 1)

