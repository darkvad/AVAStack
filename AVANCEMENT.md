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

Versions : **`OptimisationUI` = v2.98.8** (Phase 0 + **1a** + **1b** + **`tick_avant`**
LIVRÉS ET **VALIDÉS EN RÉEL** — `perf-7` : `ui_tick` **3,3 %** du mur ; **mémoire
MESURÉE** par un outil neuf ; **« copie → référence » LIVRÉ ET VALIDÉ EN RÉEL**
(v2.98.5 : `perf-8` RSS max 4 458,9 → **4 247,1 Mo**) ; **jauge `postes` LIVRÉE**
(v2.98.6) ; **persistance dark/flat CORRIGÉE** (v2.98.7, validée en réel) ;
**DÉFAUT « STF = IMAGE BLANCHE » CORRIGÉ ET VALIDÉ EN RÉEL** (v2.98.8, reproduit
et mesuré AVANT correction) ; **aucune release**) ·
`master` = v2.96.1 · **Store publié = v2.71.1**.

**Gouvernance** : aucune release GitHub sans accord ; **demander AVANT de
démarrer le lot suivant** ; ne jamais déduire l'état d'une case de `config.json`
— on MESURE le fichier produit.

---

## Session des 20-21/10/2026 — Phase 0, **1a**, **1b** et `tick_avant` VALIDÉS EN RÉEL · mémoire MESURÉE · **copie → référence LIVRÉE (perf-8)** · **jauge `postes` LIVRÉE** · **persistance dark/flat CORRIGÉE (v2.98.7)** · **DÉFAUT « STF = IMAGE BLANCHE » CORRIGÉ (v2.98.8)**

### État actuel
- **Tout est LIVRÉ, VALIDÉ EN RÉEL, COMMITTÉ ET POUSSÉ** (`OptimisationUI`,
  v2.98.8). Phase 0, **1a**, **1b**, `tick_avant` ① + ②, la mesure mémoire,
  **copie → référence**, la **jauge `postes`**, la **persistance dark/flat**
  (v2.98.7) et le **défaut « basculer sur STF après VeraLux = image blanche »**
  (v2.98.8, **« Testé OK » d'Alain**) : **rien n'est en attente de code**.
- **DÉFAUT STF/BLANC — MESURÉ PUIS CORRIGÉ (v2.98.8)** : la MÉMOIRE d'étirement
  du STF (`_stats`) était **posée pendant la phase VeraLux** (une image d'attente
  suffit : un geste, `_pousser_rendu`, le filet) et **jamais rafraîchie** (depuis
  1a, le rendu de frame n'existe plus quand la chaîne est attendue) ; à la
  bascule, `_moteur_stf(live=False)` la RÉUTILISAIT. Mesure : `hi` 11 fois SOUS
  le fond ⇒ **médiane 255, 100 % ≥ 250** (écart 180,3 avec le STF sain).
  Correctif : ① la mémoire **ne traverse pas** une période VeraLux ; ② elle
  **avance** au rendu du `vl_new` d'une nouvelle pile. Détail : changelog
  v2.98.8 + `CLAUDE.md` (« la mémoire du STF se périme ») ; banc
  `_test_bascule_stf_blanc.py`, mesure `_diag_bascule_stf_blanc.py`.
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
- ✅ **CORRIGÉ (v2.98.8) — « STF = IMAGE BLANCHE » (retour d'Alain, 21/10/2026)**.
  Reproduit dans un banc déterministe AVANT de corriger (`_test_bascule_stf_blanc.py`,
  vraie `DisplayProcessor` : VeraLux rendu → bascule STF **sans nouvelle frame**),
  MESURÉ (`_diag_bascule_stf_blanc.py`), puis corrigé — cause et preuves dans
  « État actuel » ci-dessus et dans le changelog (v2.98.8).
  **L'hypothèse n°1 du handoff était FAUSSE** : la chaîne n'est PAS en cause (la
  clé contient bien le moteur, `_vl_params()` dernier élément) — la vraie cause
  est la **MÉMOIRE du STF** (`_stats`) posée pendant la phase VeraLux et
  réutilisée à la bascule. À retenir : **un état « d'après étirement » du STF ne
  se périme pas tout seul** — il faut le JETER quand le STF n'a plus rendu
  l'empilement depuis longtemps (moteur changé), et le FAIRE AVANCER à chaque
  nouvelle pile même quand la chaîne est attendue.
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
- **v2.98.8** : `processing/display.py` (`_dernier_moteur_rendu`,
  `oublier_memoire_stf()`, garde-fou dans `process()`), `ui/renderer.py`
  (`_refresh_preview(live=…)`), `ui/app.py` (`_maj_lbl_vl` → `live=True` au rendu
  du `vl_new` d'une nouvelle pile), `bancs/_test_bascule_stf_blanc.py` (NEUF,
  5 volets), `bancs/_diag_bascule_stf_blanc.py` (NEUF, outil de MESURE).
- **Bancs** : `_test_phase0_perf` (110), `_test_1a_rendu_final` (40),
  `_test_render_worker_bit_exact` (41, hashes au bit),
  `_test_multifolder_last_file` (24), `_test_p1_memoire_reference` (30),
  `_test_p1_postes_memoire` (17), `_test_calib_persistance` (32),
  `_test_bascule_stf_blanc` (12, v2.98.8).

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
| **défaut STF/blanc** | **VALIDÉ EN RÉEL** (v2.98.8) | banc neuf : témoin inversé (médiane 255) + image identique AU BIT au STF sain ; « Testé OK » |
| **`empilement` — DERNIER POINT** | **À FAIRE : DÉCOMPOSER** (mesurer d'abord) | `perf-9` : **2 938 ms/frame** (le 1er poste de CPU restant) |

**Critères de sortie** : ① `rendus` ≈ frames (**atteint en `perf-7` : 1,12×** ;
`perf-9` 1,73× — gestes de réglages) ;
② `ui_tick` < 20 % du mur (**atteint : 3,3 %**) ; ③ image finale au bit
(**atteint**) ; ④ 0 gel du Guet (**atteint** — pire tour 92 ms) ; ⑤ garde-fou
vert (**atteint**).


---

## En attente / prochaine session

- **DÉFAUT STF/BLANC — CLOS (v2.98.8, VALIDÉ EN RÉEL : « Testé OK »)** :
  reproduit dans un banc déterministe, mesuré, corrigé, banc neuf vert +
  non-régression rejouée. Voir « État actuel » et « Problèmes ouverts ».
- **LE CHANTIER N'A PLUS QU'UN POINT : `empilement`** (dernier jalon du tableau
  ci-dessus ; `lecture_frame` reste APRÈS). `perf-9` : **2 938 ms/frame** — c'est
  de loin le premier poste de CPU restant, et il n'est PAS décomposé.
  **PROCHAINE ACTION — UNIQUE, et MESURER AVANT DE TOUCHER** : **décomposer**
  `empilement`, sans changer un pixel. Points d'entrée :
  `core/worker.py:722` (`with perf.chrono("empilement")`) → la méthode
  `_worker_empiler_frame` (`core/worker.py:1212`), qui contient, DANS ce même
  chrono : ① le filtre anti-floues (~15 ms, annoncé), ② l'extraction de canal,
  ③ **l'ARCHIVAGE + le score qualité** (I/O disque — piste n°1 : sur un NAS ou
  un dossier réseau, cf. la leçon v2.98.4 « aucune I/O sur le fil d'interface »,
  ici c'est le fil worker mais le coût peut être le même), ④ **l'ALIGNEMENT**
  (`aligner`, ORB+RANSAC / corrélation de phase), ⑤ **le REJET kappa-sigma**
  (`stacker.ajouter`, accumulateurs float64). Le levier attendu est le n°5
  (fenêtre `winsorized` → `kappa` supprime `_buf`) et/ou le n°4 (coût ORB), mais
  **on ne touche rien avant de savoir qui pèse quoi** : sous-chronos `perf`
  (opt-in, coût nul hors `--perf`, comme la Phase 0) ou un outil de banc, puis
  UN relevé de référence.
- **CE QUI ATTEND ALAIN** : rien pour coder — le chantier est prêt à reprendre
  sur `empilement`. Sa décision reste la **fusion vers `master` + la release**
  (aucune n'a été faite : `master` = v2.96.1, Store = v2.71.1).
- **Résultats du 21/10 en une ligne chacun** : `perf-6` a désigné le RÉSEAU
  (0,969 d'attente, `cores_moyens` 0,98) ; v2.98.4 a supprimé l'I/O du fil
  (`ui_tick` 456,5 → 18,6 s) ; v2.98.5 a rendu la copie de `_stack_pleine_res`
  à la référence (−96,2 Mio, rendu SHA-256 égal) ; v2.98.6 a livré la jauge
  `postes` ; v2.98.7 a corrigé la persistance des maîtres ; v2.98.8 a corrigé la
  mémoire du STF (bascule VeraLux → STF). `perf-9` a servi aux dernières preuves.
- **ABANDONNÉ (Alain, 21/10/2026)** : les 3 corrections de mesure proposées
  (ne pas traverser `_hote` dans la jauge, ne pas compter les alias des
  stackers, formule [6] de l'outil) — **ne pas les reprendre** sans demande.
  L'audit du poste `rendu` reste VALIDE (artefact mesuré, rien à récupérer dans
  le fil) ; le résiduel « 455,3 Mio » reste un PLANCHER (~540 Mio en réalité).
- **ÉCARTÉ, à ne pas réintroduire sans mesure** : `cv2.setNumThreads`,
  `sys.setswitchinterval`, priorité OS du fil Tk — le CPU n'était pas le
  problème (0,98 cœur utilisé sur 14). Et **float32 : ÉCARTÉ DÉFINITIVEMENT**
  (Alain, 21/10 — peut changer l'image ; le chiffrage reste une TRACE, pas un
  plan).
- **Banc 79 (`_test_perf_reactivite_jalon79.py`)** : 4 échecs **PRÉEXISTANTS**
  (vérifié : identiques sans le lot v2.98.8) — l'étape 1b a déplacé
  l'instrumentation du banc (`_maj_histogrammes` → `_draw_hist`). À reprendre
  un jour, **ce n'est pas une régression**.
- **`CLAUDE.md`** : à jour — leçon v2.98.3 (mesurer le CPU du fil), la règle
  « AUCUNE I/O SUR LE FIL D'INTERFACE » (et son application au démarrage),
  section « Calibration dark/flat — persistance des maîtres (v2.98.7) »,
  section NEUVE « la mémoire du STF se périme » (v2.98.8) et l'**ENVELOPPE
  MÉMOIRE** (dimensionnement 4 / 8 / 16 Go).
- Aucune release ; `master` reste à v2.96.1 ; le Store à v2.71.1.

### Contexte de reprise (à coller — 2 phrases)
Branche **`OptimisationUI`, v2.98.8** (commit `f902040`, poussé) : Phase 1,
mémoire, persistance dark/flat ET le défaut « basculer sur STF après du VeraLux =
image blanche » sont **livrés et validés en réel** (« Testé OK ») — le chantier
n'a plus qu'**UN point** : **`empilement`, 2 938 ms/frame** (`perf-9`). Action
unique de la prochaine session : **DÉCOMPOSER `empilement`** (fil d'interface non
concerné : `worker.py:722` → `_worker_empiler_frame`, soit archivage/score I/O,
alignement ORB, rejet kappa-sigma) **en MESURANT d'abord** — sous-chronos `perf`
opt-in ou outil de banc, un relevé de référence, **aucun pixel changé**.

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
- **La mémoire du STF se PÉRIME** (leçon v2.98.8) : `_stats` est un lissage
  TEMPOREL de l'empilement — il n'est réutilisé (`live=False`) que parce qu'il
  décrit l'image COURANTE. Depuis 1a, le rendu de frame n'existe plus quand la
  chaîne est attendue : en VeraLux, une **image d'attente** (un geste, le filet,
  `_pousser_rendu`) peut le POSER et rien ne le rafraîchit ensuite. Deux règles :
  ① la mémoire **ne traverse pas** une période VeraLux (elle est jetée dans
  `process()` au changement de moteur) ; ② elle **avance** au rendu du `vl_new`
  d'une nouvelle pile (`_refresh_preview(live=True)`) — sinon le STF auto reste
  GELÉ, et dès que le NIVEAU de l'empilement change (calibration, autre nuit,
  Lune), le point noir mémorisé est sous le fond : **image blanche** (mesuré :
  médiane 255, 100 % ≥ 250).
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
  POUSSÉES** (`e307ad4`) — copie → référence (−96,2 Mio), jauge `postes`,
  persistance dark/flat ; `perf-9` nomme le résiduel. Détail : changelog
  (v2.98.5/6/7) et `git log`.
- **21/10/2026** : **1b VALIDÉE EN RÉEL** (v2.98.2) — `ui_rendu` 102 s → 2,2 s,
  calcul dans `fil_rendu` ; `tick_avant` restait à instruire (v2.98.3/4 depuis).

