# AVANCEMENT.md — mémoire de travail à court terme

(Complète `CLAUDE.md`, mémoire LONG terme. Ici : état courant, décisions, pièges
actifs, prochaine action. Le détail daté vit dans `avastack/__init__.py`
(changelog) et `git log`.)

---

## ⚠️ BRANCHE DE DÉVELOPPEMENT ACTIVE — NE PAS SUPPRIMER JUSQU'À DEMANDE EXPLICITE

**Branche : `OptimisationUI`** (depuis `master`, 20/10/2026) — audit MESURÉ
performance/mémoire, puis refonte du rendu.

> **RÈGLE FERME** : tout développement se fait **exclusivement** sur
> `OptimisationUI` ; `master` = branche stable, releases uniquement ; merge
> seulement sur demande explicite d'Alain. **`LRGBHa` est FERMÉE** — ne pas la
> recréer.

Versions : **`OptimisationUI` = v2.98.7** (Phase 0 + **1a** + **1b** + **`tick_avant`**
LIVRÉS ET **VALIDÉS EN RÉEL** — `perf-7` : `ui_tick` **3,3 %** du mur ; **mémoire
MESURÉE** par un outil neuf ; **« copie → référence » LIVRÉ ET VALIDÉ EN RÉEL**
(v2.98.5 : `perf-8` RSS max 4 458,9 → **4 247,1 Mo**) ; **jauge `postes` LIVRÉE**
(v2.98.6) ; **persistance dark/flat CORRIGÉE** (v2.98.7, en attente du test
réel) ; **aucune release**) ·
`master` = v2.96.1 · **Store publié = v2.71.1**.

**Gouvernance** : aucune release GitHub sans accord ; **demander AVANT de
démarrer le lot suivant** ; ne jamais déduire l'état d'une case de `config.json`
— on MESURE le fichier produit.

---

## Session des 20-21/10/2026 — Phase 0, **1a**, **1b** et `tick_avant` VALIDÉS EN RÉEL · mémoire MESURÉE · **copie → référence LIVRÉE (perf-8)** · **jauge `postes` LIVRÉE** · **persistance dark/flat CORRIGÉE (v2.98.7)**

### État actuel
- **Tout est LIVRÉ, VALIDÉ EN RÉEL et COMMITTÉ/PUSHÉ** (`OptimisationUI`,
  commit `e307ad4`). Phase 0, **1a**, **1b**, `tick_avant` ① + ②, la mesure
  mémoire, **copie → référence**, la **jauge `postes`** et la **persistance
  dark/flat** (v2.98.7) : rien n'est en attente de code.
- **Le fil d'interface ne fait plus le calcul** : `ui_tick` **3,3 %** du mur
  (`perf-7` 456,5 → 18,6 s ; `perf-9` 22,7 s / 683 s), `tick_avant` 0,70 ms/tour,
  pire tour 92 ms (plus de gel de 2 s). Ressenti d'Alain (le vrai critère) :
  **l'interface répond nettement mieux**.
- **La mémoire est NOMMÉE** (v2.98.6 jauge `postes` + `perf-9`) : voir
  « Enveloppe » ci-dessous et « Problèmes ouverts ». **`calib` 96,2 Mio** =
  les 3 darks d'Alain — la persistance (v2.98.7) les rend désormais visibles
  dans la config ET dans la mesure.
- **Le défaut corrigé (v2.98.7)** : `_load_dark`/`_load_flat` chargeaient
  l'image sans rien écrire dans `config.json` → re-sélection à chaque session.
  Clés `calib_dark_unique` / `calib_dark_<rôle>` (+ `calib_flat_*`) écrites **au
  geste**, restauration au démarrage **hors du fil d'interface** (fil démon
  borné → file `_calib_q` → `_tick`) car un maître peut vivre sur le NAS.
  **Confirmé par Alain** : « la sauvegarde fonctionne, on retrouve bien les dark
  quand on réouvre ».


### Relevés de référence (M33, 5 canaux, pleine résolution, VeraLux + chroma)

| relevé | `ui_rendu` (fil Tk) | `tick_avant` | `ui_tick` |
|---|---|---|---|
| `perf-3` (avant 1a) | 276 s | 202,5 s (26,7 ms) | 482,8 s = 61 % |
| `perf-4` (après 1a) | 102 s | 200,2 s (24,5 ms) | 307 s = 48 % |
| `perf-5` (après 1b) | 2,2 s | 380,5 s (64,0 ms) | 388,7 s = 61 % |
| `perf-6` (mesure de l'attente) | 1,1 s | 453,6 s (133,9 ms) | 456,5 s = **77 %** |
| **`perf-7` (correctif I/O)** | **1,2 s** | **11,1 s (0,74 ms)** | **18,6 s = 3,3 %** |
| **`perf-9` (v2.98.7, darks chargés)** | **1,8 s** | **13,0 s (0,70 ms)** | **22,7 s = 3,3 %** |

Repères `perf-9` (683,2 s, 67 frames, **3 darks maîtres chargés**) : `fil_rendu`
148,0 s (1 276 ms/rendu), `empilement` **2 938 ms**, `lecture_frame` **4 765 ms**,
stackers 2 935,4 Mo, **RSS max 4 252,2 Mo** (pic 4 687,5), `cores_moyens` **1,24**,
`rendus` 116 pour 67 frames (1,73×), `tick_postes` **4,9 ms** (la jauge coûte
~0,02 % du mur).

Repères `perf-7` (556 s, 47 frames) : `fil_rendu` 103,4 s (1 360 ms/rendu),
`empilement` **2 751 ms**, `lecture_frame` **6 697 ms**, stackers **2 935,7 Mo**,
RSS 3 163 Mo (pic 4 563), `cores_moyens` **1,12**, `rendus` 76, `vl_new` 76.
Détail complet : `perf-*.json` (hors dépôt) et changelog `avastack/__init__.py`.

**Lecture** : 1a et 1b ont tenu leurs promesses (`ui_rendu` 276 → 1,2 s), mais
`tick_avant` restait à 77 % du mur **sans travail mesuré dedans** — c'était de
l'**attente**, et la mesure ① puis la pile du Guet l'ont attribuée à une I/O
réseau (`getmtime`) faite à chaque tour. Corrigé en v2.98.4 : **3,3 %**.

### Enveloppe mémoire MESURÉE (21/10/2026 — outil, aucune session requise)

Géométrie native 8,4 Mpx, fenêtre 4, winsorized, k=3, Linear Fit. Commandes :
`--roles L` (mono 2D) · `--roles R --canaux 3` (OSC) · `--roles L,R,G,B,Ha --maitres 10`.

| poste (Mio) | **MONO** 1 dossier | **OSC** 3 canaux | **MAX** 5 rôles |
|---|---|---|---|
| empileur(s) | **585,2** | **1 755,6** | **3 118,5** |
| chaîne de rendu retenue | 40,1 | 120,2 | 280,6 |
| postes de session (brute/calibrée/canal/uint8/brut niveaux) | 200,4 | 200,4 | 200,4 |
| maîtres dark/flat (**32,07 CHACUN**) | 2 → **64,1** | 2 → 64,1 | 10 → **320,7** |
| base applicative (Tk+OpenCV+astropy) | 148,0 | 148,0 | 148,0 |
| **TOTAL modèle au repos** | **1 038** | **2 288** | **4 068** |
| non-tableau mesuré (fragmentation + tas) | ~+150 | ~+300 | **+440** (dont 193 de fragmentation) |
| **RSS réel attendu** | **~1,2 Go** | **~2,6 Go** | **~4,5 Go** |
| pic pendant un rendu VeraLux (mesuré) | +513 | +1 487 | +1 449 |
| **PIC réel attendu** | **~1,7 Go** | **~4,0 Go** | **~5,0 Go** |

**Ancre réelle** : `perf-9` (5 rôles, **3** darks) → RSS max **4 252,2 Mo**, pic
**4 687,5 Mo** (modèle 3 811 + 440 de non-tableau ✓). Avec 5 darks + 5 flats :
**+224 Mo** (7 maîtres de plus) ⇒ **~4,5 Go au repos, ~4,9 Go de pic**.
**Recommandation** : **4 Go** suffisent pour un dossier MONO ; **8 Go** pour une
source OSC ; **8 Go = plancher, 16 Go conseillé** pour 5 rôles avec darks ET
flats. Leviers si besoin : fenêtre 4 → 2 (−320 Mio pour 5 rôles), méthode
`kappa` au lieu de `winsorized` (supprime `_buf`), moins de rôles.

### Décisions (détail dans `CLAUDE.md` et le changelog)
- Instrumentation **opt-in**, **coût nul** hors `--perf` (protège les hashes
  d'empilement au bit et la course du banc 76).
- **Pleine résolution = choix assumé** ⇒ réponse **architecturale** (rendu hors
  fil Tk), pas une réduction d'aperçu. Ordre arrêté : 1a → 1b → `tick_avant` →
  mémoire → empilement.
- **`tick_avant` : MESURER AVANT de corriger** — un mur de 64 ms ne dit pas si
  le fil travaille ou attend. **Attente INCONNUE ≠ attente nulle** (macOS < 3.13 :
  `contexte.cpu_fil = false`, jamais un zéro trompeur).
- **float32 ÉCARTÉ DÉFINITIVEMENT (Alain, 21/10/2026)** : −481 Mio possibles,
  mais l'image peut changer — **ne pas le reproposer**.
- **Une COPIE ne se supprime qu'après avoir lu QUI la lit** : mesurer, auditer
  les usages, puis agir (leçon du « ~192 Mio sans risque », faux).
- **Persistance dark/flat (v2.98.7)** : on persiste le **CHEMIN** au geste (jamais
  l'image) et on **restaure HORS du fil d'interface** — un maître peut être sur
  le NAS, et une lecture au démarrage empêcherait l'ouverture (règle v2.98.4).
  Un maître illisible n'est **pas** retiré de la config (perte évitée) : il est DIT.

### Problèmes ouverts
- 🔴 **DÉFAUT À INSTRUIRE — STF = IMAGE BLANCHE (retour d'Alain, 21/10/2026)**.
  Le **test complet est BON**, SAUF ceci : après avoir joué en fin d'empilement
  avec « un peu tous les paramètres » **en étirement VeraLux**, il a basculé sur
  l'**étirement STF** pour vérifier → **image blanche**. C'est le SEUL point qui
  bloque la fusion vers `master` et la release.
  **À FAIRE (action unique, MESURER AVANT de corriger)** : reproduire dans un
  banc DÉTERMINISTE, sans écran ni session — vraie `DisplayProcessor` : rendre en
  VeraLux, puis **basculer le moteur en STF SANS nouvelle frame** et regarder
  l'image (`_on_moteur`, `app.py:2960` → `disp.stretch`). Le défaut est
  PROBABLEMENT le même que celui du jalon P7 : **un rendu sans nouvelle frame
  doit FORCER la chaîne** (`disp.notify_new_stack()`) — sinon le cache republie
  l'image **déjà étirée par VeraLux** et le STF l'étire **une seconde fois**
  (d'où le blanc). Seconde piste : l'image d'**ATTENTE** (leçon 1a : « image
  blanche entre deux images »).
  **Points d'entrée** : `app.py:2960` (`_on_moteur`), `app.py:_pousser_rendu`
  (`notify_new_stack`), `display.py:449` (défaut `stretch="stf"`),
  `display.py:1477` (`stretch == "veralux" and not vl_error`),
  `display.py:1580` (`_vl_params()` : le MOTEUR est dans la clé),
  `display.py:1668`. **Bancs à rejouer/étendre** :
  `_test_p7_recalcul_corrections.py` (le précédent exact),
  `_test_chaine_pre_etirement_jalon125.py`, `_test_ui_moteur_jalon41.py`,
  `_test_1a_rendu_final.py`, `_test_chroma_stf_jalon127.py`,
  `_test_neutralisation_stf_jalon137.py`, `_test_render_worker_bit_exact.py`.
  **Aucun pixel ne doit changer** : preuve au bit exigée.
- **Phase 1 : critère ATTEINT** (`ui_tick` 3,3 % < 20 %) — **test complet d'Alain
  AVANT toute fusion vers `master` et toute release** (sa décision, pas la nôtre).
- **AUDIT DU POSTE `rendu` (21/10, outil `bancs/_diag_rendu_memoire.py`) — le
  poste est un ARTEFACT de parcours, MESURÉ** : `FilRendu` garde `_hote` (= l'App
  elle-même) ; `perf.postes_memoire(app)` re-entre donc dans l'App sous le nom
  « rendu » et y range les tableaux déclarés APRÈS `self.rendu` dans `__init__`.
  Mesure : vue jauge `rendu` **120,2 Mio** ; boucle cassée ⇒ **`_stack_pleine_res`
  96,2 + `_last_disp` 24,0** (même total 216,5 — **aucun octet perdu ni compté
  deux fois**) ; **le `FilRendu` SEUL retient 0,0 Mio (0 tableau)**.
  ⇒ **il n'y a rien à récupérer dans le fil de rendu** (l'hypothèse « 206 Mio à
  instruire » tombe). Deux conséquences à trancher par Alain :
  ① **corriger la jauge** (ne pas traverser `_hote` : ~3 lignes dans
  `perf.postes_memoire`) pour que le relevé NOMME au lieu d'entasser sous
  `rendu` ; ② **ne pas compter les alias des stackers dans `postes`** :
  `_stack_pleine_res` est une **RÉFÉRENCE** sur le cache du stacker (v2.98.5),
  donc compté DEUX fois (stackers **et** hors stackers). ⚠️ **SENS DU DÉFAUT** :
  la formule du [6] (`hors stackers − postes − base`) SOUS-ESTIME alors le
  résiduel de ~85 Mio au déploiement du run ⇒ **455,3 Mio est un PLANCHER ;
  le résiduel réel est ~540 Mio** (dont 193 de fragmentation). La formule du [4]
  (postes du [3] + chaîne du [3 bis], qui excluent DÉJÀ le composite) donnait
  **560,7** — elle était la bonne. **À corriger dans l'outil AVANT de conclure
  sur un prochain relevé.**
- **MÉMOIRE — le résiduel est NOMMÉ** (voir aussi l'« Enveloppe » ci-dessus) :
  - Géométrie RÉELLE des brutes = **3856×2180 = 8 406 080 px** (en-tête FITS) ;
    `source_px` (7,4 Mpx) est l'image **RECADRÉE** — ne pas confondre.
  - `perf-9` : hors stackers **1 156,5 Mio**, dont la jauge `postes` nomme
    **553,2 Mio** (`disp` 226,1 · `rendu` 206,2 · **`calib` 96,2** · 3 aligneurs
    24,6) ⇒ **455,3 Mio sans tableau nommé** (dont **193 Mio de fragmentation
    MESURÉE**) = tas Tk/PIL/OpenCV, objets Python, arènes. **Aucune fuite.**
    ⚠️ **PLANCHER** : `rendu` est un artefact et l'alias du composite est compté
    deux fois ⇒ le résiduel réel est **~540 Mio** (cf. l'audit `rendu` ci-dessus).
  - **La chaîne de rendu (`disp` + `rendu` = 432,3 Mio) est 47,8 % du
    hors-stackers** : c'est le prochain poste à instruire (le `rendu` 206,2 =
    ce que le `FilRendu` RETIENT) — **auditer les lecteurs AVANT d'agir**, preuve
    au bit.
  - PIÈGE MESURÉ : la jauge **sous-compte 160,3 Mio** (`_memo_moy` est un tuple,
    invisible à `profondeur=3`) — **une jauge se RECOUPE**.
- **DÉFAUT CORRIGÉ (v2.98.7)** : les chemins dark/flat n'étaient PAS persistés
  (`_load_dark`/`_load_flat` chargeaient l'image sans rien écrire dans `CONFIG`)
  → re-sélection à chaque session. Ils étaient bien APPLIQUÉS (`worker.py:703`,
  `calib.apply`, une fois par frame). PIÈGE : l'absence de clé dans
  `config.json` ne prouve PAS qu'aucun maître n'est chargé.
- **`empilement`** 2 938 ms/frame (`perf-9`) et **`lecture_frame`**
  4 765 ms/frame (scan réseau) : APRÈS la mémoire, et à décomposer avant de
  toucher. Pire tour `ui_tick` : 92 ms (sous le seuil du Guet).

### Fichiers touchés par l'audit (détail : commit `e307ad4` + changelog)
- **v2.98.0 → v2.98.4** : `avastack/perf.py` (NEUF, opt-in, coût nul) ; câblage
  `ui/app.py`, `ui/renderer.py`, `core/worker.py` ; `avastack/ui/rendu.py`
  (NEUF, fil de rendu) ; `ui/widgets/histogram.py` (`_histogrammes_purs`) ;
  `cameras/multifolder.py` (`last_file` sans I/O).
- **v2.98.5 → v2.98.7** : `processing/display.py` (`_vl_src` retiré),
  `core/worker.py` + `ui/app.py` (copie → référence), `perf.py` (jauge `postes`),
  `processing/calibration.py` + `ui/app.py` + `ui/config_ui.py` (persistance des
  maîtres), `bancs/_mesure_memoire_stackers.py` (NEUF, options `--roles`,
  `--canaux`, `--maitres` pour l'enveloppe).
- **Bancs** : `_test_phase0_perf` (110), `_test_1a_rendu_final` (40),
  `_test_render_worker_bit_exact` (41, hashes au bit),
  `_test_multifolder_last_file` (24), `_test_p1_memoire_reference` (30),
  `_test_p1_postes_memoire` (17), `_test_calib_persistance` (32).

---

## Chantier en cours — PHASE 1 : **rendu hors fil Tk** (1a + 1b + `tick_avant` LIVRÉS ET VALIDÉS)

**Objectif** : fil Tk de **61 % → < 20 %** du temps mural, **sans changer un
pixel**. **ATTEINT : 3,3 %** (`perf-7`). Le chantier suivant est la **MÉMOIRE**.

| jalon | état | preuve |
|---|---|---|
| 1a — un seul rendu par frame | **LIVRÉE** (v2.98.1) | `perf-4`, banc 40 |
| 1b — rendu hors fil Tk | **LIVRÉE** (v2.98.2) | `perf-5`, banc 41 |
| `tick_avant` ① — MESURER | **LIVRÉE** (v2.98.3) | `perf-6` (96,9 % d'attente), banc 110 |
| `tick_avant` ② — AGIR | **VALIDÉE EN RÉEL** (v2.98.4) | `perf-7` : 77 % → **3,3 %**, banc 24 |
| **mémoire — MESURER** | **LIVRÉE** (outil, 0 pixel changé) | 3 096,0 Mio = 69,4 % du RSS du run ; **Go inexpliqué retrouvé** (chaîne de rendu 376,8) |
| **copie → référence** | **LIVRÉE** (v2.98.5) | banc 30 : rendu SHA-256 égal, −96,2 Mio de rétention, RSS −96 Mo |
| **jauge `postes`** | **LIVRÉE** (v2.98.6) | `perf-9` : nomme 553,2 Mio (dont `calib` 96,2), `tick_postes` 4,9 ms |
| **persistance dark/flat** | **VALIDÉE EN RÉEL** (v2.98.7) | banc 26 ; « on retrouve bien les dark quand on réouvre » |
| `empilement` | après | 2 938 ms/frame (`perf-9`) |

**Critères de sortie** : ① `rendus` ≈ frames (**atteint en `perf-7` : 1,12×** ;
`perf-9` 1,73× — gestes de réglages) ;
② `ui_tick` < 20 % du mur (**atteint : 3,3 %**) ; ③ image finale au bit
(**atteint**) ; ④ 0 gel du Guet (**atteint** — pire tour 92 ms) ; ⑤ garde-fou
vert (**atteint**).


---

## En attente / prochaine session

- **TOUT EST FAIT ET POUSSÉ** (commit `e307ad4` sur `origin/OptimisationUI`) :
  Phase 1 validée en réel, mémoire nommée, persistance dark/flat corrigée et
  validée. **RIEN n'attend d'accord de code** : Alain fait son **test complet**
  avant de décider la fusion vers `master` et la release.
- **Résultats du 21/10 en une ligne chacun** : `perf-6` a désigné le RÉSEAU
  (0,969 d'attente, `cores_moyens` 0,98) ; v2.98.4 a supprimé l'I/O du fil
  (`ui_tick` 456,5 → 18,6 s) ; v2.98.5 a rendu la copie de `_stack_pleine_res`
  à la référence (−96,2 Mio, rendu SHA-256 égal) ; v2.98.6 a livré la jauge
  `postes` ; v2.98.7 a corrigé la persistance des maîtres. `perf-9` a servi aux
  deux dernières preuves.
- **PROCHAINE ACTION — LE DÉFAUT STF/BLANC (accord donné, priorité absolue)** :
  voir le premier point de « Problèmes ouverts ». **Action unique** : écrire le
  banc qui reproduit le blanc (VeraLux rendu → bascule STF **sans nouvelle
  frame**), MESURER, puis corriger. **Rien d'autre ne passe avant.**
- **ABANDONNÉ (Alain, 21/10/2026)** : les 3 corrections de mesure proposées
  (ne pas traverser `_hote` dans la jauge, ne pas compter les alias des
  stackers, formule [6] de l'outil) — **ne pas les reprendre** sans demande.
  L'audit du poste `rendu` reste VALIDE (artefact mesuré, rien à récupérer dans
  le fil) ; le résiduel « 455,3 Mio » reste un PLANCHER (~540 Mio en réalité).
- **Ensuite** : **`empilement`** 2 938 ms/frame (décomposer alignement vs rejet
  kappa-sigma AVANT de toucher) ; puis **`lecture_frame`** 4 765 ms/frame.
- **ÉCARTÉ, à ne pas réintroduire sans mesure** : `cv2.setNumThreads`,
  `sys.setswitchinterval`, priorité OS du fil Tk — le CPU n'était pas le
  problème (0,98 cœur utilisé sur 14). Et **float32 : ÉCARTÉ DÉFINITIVEMENT**
  (Alain, 21/10 — peut changer l'image ; le chiffrage reste une TRACE, pas un
  plan).
- **`CLAUDE.md`** : à jour — leçon v2.98.3 (mesurer le CPU du fil), la règle
  « AUCUNE I/O SUR LE FIL D'INTERFACE » (et son application au démarrage),
  section NEUVE « Calibration dark/flat — persistance des maîtres (v2.98.7) »,
  et l'**ENVELOPPE MÉMOIRE** (dimensionnement 4 / 8 / 16 Go).
- Aucune release ; `master` reste à v2.96.1 ; le Store à v2.71.1.

### Contexte de reprise (à coller — 2 phrases)
Branche **`OptimisationUI`, v2.98.7** (commit `84d5eb5` poussé) : Phase 1 validée
(`ui_tick` 3,3 %), mémoire nommée, persistance dark/flat validée en réel,
enveloppe mesurée, audit du poste `rendu` clos (artefact de parcours) — **le test
complet d'Alain est BON sauf UN défaut** : après avoir joué en VeraLux en fin
d'empilement, **basculer sur l'étirement STF donne une IMAGE BLANCHE**. Action
unique de la prochaine session : reproduire le blanc dans un banc déterministe
(VeraLux rendu → bascule STF **sans nouvelle frame**, vraie `DisplayProcessor`),
MESURER, puis corriger — hypothèse n°1 : la chaîne n'est pas forcée et le STF
étire une image DÉJÀ étirée (même famille que le défaut P7, `notify_new_stack`).

---

## Setup d'Alain

- **Setup 1 (miniPC)** : QHY MiniCam8M (mono refroidie, roue intégrée) ; N.I.N.A. →
  `TargetSchedulerSequence/<cible>/<expo>/LIGHT` — un dossier peut MÉLANGER
  plusieurs nuits.
- **Setup 2** : C8 défourché + réducteur 0,63 (1280 mm) ; Player One Uranus-C Pro
  (couleur, IMX585, RGGB) sur monture DIY **Open Astro Mount** ; guidage SV305C
  sur 60/240.
- **Jeux de test (QHY + SV555)** : **M31** (L du 13/09 + R/G/B des 22-23/09,
  60 s, −15 °C) ; **M33** (nuit du 10-11/10 : L 60×60 s, R/G/B 60-120 s) + un
  dossier **Ha de 40 frames**. Darks maîtres : 60 s (L/R/G), 120 s (B), 180 s
  (Ha).
- **Outils locaux** : Siril 1.4.4 (Gaia XP, base SPCC), ASTAP (D80 Gaia DR3) ;
  pas d'astrometry.net. **Ubuntu 26.04 LTS** : installateur éprouvé ; restent la
  machine VIERGE et le test matériel caméras (`--cameras`).


---

## Pièges récents (encore actifs — le reste est passé dans `CLAUDE.md`)

- **Aucune I/O sur le fil d'interface** (leçon v2.98.4) : un `getmtime()` SMB à
  chaque tour coûtait **178 ms/tour**. Et `part_attente` ≈ 1 avec
  `cores_moyens` < 1 = **I/O ou verrou**, jamais un manque de cœurs. Depuis
  v2.98.7 la règle s'applique aussi au DÉMARRAGE : les maîtres dark/flat
  persistés sont lus dans un **fil démon borné** (5 s/maître), jamais pendant la
  construction de la fenêtre.
- **Un banc qui charge un dark/flat ÉCRIT la config** (v2.98.7) :
  `_load_dark`/`_load_flat`/`_clear_calib` persistent désormais les chemins — un
  banc qui les appelle DOIT intercepter `ui.CONFIG` **et** `ui.sauver_config`
  (motif de `_test_calib_compo_jalon53`), sinon il écrit le vrai `config.json`
  avec un chemin de test.
- **1b — `disp.process()` ne se lance QUE dans le fil de rendu** (seul écrivain
  de l'EMA du STF et des caches) : un appel depuis un gestionnaire Tk fabrique un
  second écrivain. Passer par `_refresh_preview()` / `_rendre_et_afficher()`.
  Exception : `display.rendu_pleine_resolution()` (thread de sauvegarde).
- **1b — ne jamais attendre dans `_tick`** (`attendre_rendu()` = bancs
  seulement) ; un banc qui lit l'image juste après l'avoir demandée passe en
  `app.rendu.immediat = True` ; « le dernier gagne » est VOULU.
- **`vl_actif`** : seule lecture juste = `disp.chaine_sollicitee()` (jamais un OR
  des cases, jamais `vl_neutre_gains` qui est un RÉSULTAT).
- **Un rendu sans nouvelle frame n'est pas vu par `_tick`** : tout point qui
  pousse une image RECALCULÉE doit appeler `disp.notify_new_stack()` (leçon P7).
- **`perf.json`** : écrit à côté du programme (`--perf`, toutes les 5 s) ;
  `--perf-json CHEMIN` sert à **garder ET à relire** un relevé (`perf*.json` hors
  dépôt). Le relevé doit être POSTÉRIEUR au lot mesuré (l'outil compare la
  version) et la chaîne est lue **ramenée à la géométrie du run** (`source_px`).
- **Pic ≠ retenu** : VeraLux crée ~1,5 Go de temporaires à 8,4 Mpx pour
  ~281 Mio retenus — ne jamais confondre les deux, ni appeler « fuite » ce
  qu'aucune jauge ne nomme (fragmentation comprise).
- **`source_px` n'est PAS la géométrie des stackers** : c'est l'image
  **recadrée** (7,4 Mpx) ; les brutes M33 font **3856×2180 = 8 406 080 px**.
- **Un seuil ABSOLU de temps est FLAKY** : ancrer les assertions sur une
  comparaison INTERNE (cas A vs cas B du même run) ou sur une mesure directe.
- **Échecs PRÉEXISTANTS** (environnementaux, pas des régressions) :
  `_test_espace_jalon72` (géométrie d'écran), `_test_reset_empilement_jalon76`
  [4] (course `_stop()`), « ligne Base SPCC rognée » + « menu écrasé » (flaky),
  `_test_lot1_p2_p3` [3] (rejoue `Antlia R` sur le `config.json` RÉEL).
- **Une conversion de dtype CHANGE l'image** : preuve au bit exigée sur les bancs
  d'empilement — jamais « à peu près », jamais sans l'accord d'Alain.
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`.

---

## Clôtures précédentes

- **21/10/2026 (soir)** : **v2.98.5 → v2.98.7 LIVRÉES, VALIDÉES EN RÉEL et
  POUSSÉES** (`e307ad4`) — copie → référence (−96,2 Mio), jauge `postes`, et
  **persistance dark/flat corrigée** (« on retrouve bien les dark quand on
  réouvre ») ; `perf-9` nomme le résiduel et l'enveloppe mémoire est mesurée.
  Détail : changelog `avastack/__init__.py` (v2.98.5/6/7) et `git log`.
- **21/10/2026** : **1b VALIDÉE EN RÉEL** (v2.98.2) — `ui_rendu` 102 s → 2,2 s,
  calcul dans `fil_rendu` (169 s), UI qui répond ; `tick_avant` reste à instruire.
- **20/10/2026** : **1a VALIDÉE EN RÉEL** (v2.98.1) — `rendus` 132 → 51,
  `ui_tick` 61 % → 48 %.

