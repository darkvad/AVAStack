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
- **v2.98.7 — PERSISTANCE DES MAÎTRES DARK/FLAT LIVRÉE ET VALIDÉE EN RÉEL** :
  `_load_dark`/`_load_flat` chargeaient l'image en mémoire **sans rien écrire**
  dans `config.json` → re-sélection à chaque session. Correctif : clés
  `calib_dark_unique` / `calib_dark_<rôle>` (+ `calib_flat_*`) écrites **au
  geste** (`_persister_calib`), relues au démarrage et les fichiers chargés
  **HORS du fil d'interface** (fil démon borné 5 s/maître → file `_calib_q` →
  `_tick`), car un maître peut vivre sur le NAS. Banc
  `_test_calib_persistance.py` (**26 vérifications**, TOUT PASSE) ; non-régressions
  vertes (jalon 53, jalon 19, garde-fou : **pyright 0 / 56**, hashes au bit,
  surface 76 symboles).
  **CONFIRMÉ PAR ALAIN (21/10)** : « la sauvegarde fonctionne, on retrouve bien
  les dark quand on réouvre » — `config.json` porte ses **3 darks**
  (`MasterDark_60_90_25` en unique, `_120` pour B, `_180` pour Ha) et le relevé
  `perf-9` les compte dans le poste **`calib` : 96,2 Mio** (3 × 32,07).
- **Phase 0** (instrumentation `avastack/perf.py`, **opt-in**, coût nul) :
  livrée ; banc `_test_phase0_perf.py` (58 + câblage AST).
- **1a** (un seul rendu par frame) : livrée et **validée en réel**
  (`perf-4.json`), banc `_test_1a_rendu_final.py` (40).
- **1b** (rendu hors fil Tk) : livrée et **validée en réel** (`perf-5.json`),
  banc `_test_render_worker_bit_exact.py` (**41**), garde-fou vert (pyright 0
  sur **56** fichiers typés, hashes d'empilement au bit).
- **Ressenti d'Alain (le vrai critère)** : **l'interface répond nettement
  mieux** — plus de gel de 2 s pendant l'étirement.
- **VERDICT `perf-6` (21/10, 590 s, 47 frames, VeraLux + chroma) — LA CAUSE EST
  LE RÉSEAU, PAS OpenCV** : `attente.tick_avant.part_attente` = **0,969**
  (mur 453,6 s, **CPU du fil 14,3 s**) ; `ui_tick` 0,965. `cores_moyens` =
  **0,98** ⇒ le fil n'a pas soif de cœurs. Le **Guet de gel** a nommé le
  coupable (2 rapports, pile complète) : `app.py:6933` →
  `multifolder.py:131` → `genericpath.getmtime`. Les 5 dossiers surveillés sont
  sur un **partage SMB** (`//192.168.155.45/…`) : mesuré sur le poste,
  `exists` seul = **0,8 ms/tour**, `exists`+`getmtime` = **178 ms/tour** ⇒
  **439,6 s d'attente** = 10 requêtes réseau par tour d'interface.
- **Conséquence** : `cv2.setNumThreads` est **ÉCARTÉ** (hypothèse fausse, elle
  explique aussi les 26,7 ms/tour de `perf-3` et 64 ms de `perf-5` : même appel,
  partage plus ou moins rapide). Le correctif est de **3 lignes** dans
  `multifolder.py` (mémoriser le dernier fichier LU dans `read()`) — **sur
  accord d'Alain avant de coder**.
- **`tick_avant` étape ① (MESURER) LIVRÉE — v2.98.3** : `perf.t0_cpu()` +
  `perf.duree_attente(base, mur, cpu)` posent, **à côté du mur**, le CPU du
  **fil appelant** (`time.thread_time()`) et l'**ATTENTE** = mur − CPU, avec un
  bilan `attente` (`part_attente`) dans le JSON et une ligne dans `resume()`.
  Branché sur **`tick_avant`** (`_tick_corps`) et **`ui_tick`** (`_tick`) —
  deux points, **aucun pixel, aucun calcul déplacé**. Banc Phase 0 :
  **110 vérifications** exécutées (section **[2 bis]** : sommeil ⇒ part ≈ 1,
  CPU publié comparé à une mesure DIRECTE, calcul pur ⇒ attente nettement
  moindre — **pas de seuil absolu**, il mesurait la charge machine).
- **RÉSULTAT `perf-7` (21/10, 556 s, 47 frames, v2.98.4) — LE CORRECTIF PAIE** :
  `ui_tick` **456,5 s → 18,6 s** (**77 % → 3,3 %** du mur), **1,23 ms/tour**
  (contre 134,7), **max 74,1 ms** (contre 5 952), **27 tours/s** (contre 5,7),
  attente du fil 440,7 → **15,3 s**. `empilement` 2 865 → 2 751 ms ;
  `fil_rendu` inchangé (1 360 ms) ; `cores_moyens` 0,98 → 1,12 ; mémoire
  inchangée (stackers 2 935,7 Mo, RSS 3 163 Mo).
  **Lecture** : `part_attente` reste à 0,87 mais c'est le PLANCHER (0,39 ms de
  travail par tour) — l'indicateur devient le TOTAL, pas le ratio.
- **Prochain sujet, dans l'ordre** : ① **mémoire** — **MESURÉE** (cf.
  « Problèmes ouverts » : 3 096,0 Mio constatés = 69,4 % du RSS du run) ;
  **float32 ABANDONNÉ** (trop risqué, 21/10) ; la **copie** de
  `_stack_pleine_res` est **FAITE** (v2.98.5 : **−96,2 Mio** de rétention,
  preuve au bit) ; reste à **nommer le résiduel** (dernier chiffre de
  référence : **637,7 Mio**, à re-lire après un relevé réel) ; ② **`empilement`**
  2 751 ms/frame (alignement vs rejet kappa-sigma, à décomposer AVANT de
  toucher) ; ③ **`lecture_frame` 6 697 ms/frame** — le scan réseau
  (326 ms/dossier/passe) et l'attente des fichiers, sujet SÉPARÉ de l'interface.


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
- **Phase 1 : critère ATTEINT** (`ui_tick` **3,3 %** < 20 %) — reste la décision
  d'Alain : clore la phase (merge/release ?) ou enchaîner sur la mémoire.
- **RÉSOLU (v2.98.4)** : l'attente de `tick_avant` (439,6 s) était une **I/O
  réseau** — `MultiFolderCamera.last_file` faisait `exists` + `getmtime` sur les
  5 dossiers à CHAQUE tour ; calcul déplacé dans `read()`, `ui_tick`
  456,5 → **18,6 s**.
- **MÉMOIRE — MESURÉE (21/10, aucun pixel changé)** : outil NEUF
  `bancs/_mesure_memoire_stackers.py`. Géométrie RÉELLE des brutes =
  **3856×2180 = 8 406 080 px** (en-tête FITS) ; `source_px` (7,4 Mpx) est
  l'image **RECADRÉE** — ne pas s'en servir comme géométrie.
  Par rôle (5 rôles, winsorized, fenêtre 4) : tampons **1 162,4 Mio** ·
  accumulateurs float64 **962,0** · fenêtre **641,3** · composite mémoïsé
  **192,4** · moyennes **160,3** ⇒ modèle **3 118,5 Mio** ; **CONSTATÉ 3 096,0
  Mio** = **69,4 %** du RSS **pendant** le run (4 458,9) — le « 61 % » d'un RSS
  de fin était une erreur de lecture. La jauge **sous-compte 160,3 Mio**
  (`_memo_moy` est un tuple, invisible à `profondeur=3`) : une jauge se RECOUPE.
- **LE « Go INEXPLIQUÉ » EST RETROUVÉ PUIS RÉDUIT** : la chaîne de rendu retenait
  **376,8 Mio** (couches `vl_compo` 160,5 + brut niveaux 96,2 + uint8 24,0 +
  **copie** de `_stack_pleine_res` 96,2). Le lot **copie → référence** (v2.98.5,
  validé en réel par `perf-8`) l'a ramenée à **280,6 Mio** (247,3 à la géométrie
  du run). `_vl_src` retiré (écrit et jamais lu, mais il retenait l'image).
- **RÉSIDUEL (perf-8, post-lot)** : hors stackers 1 151,4 = postes d'image 200,4
  + chaîne 247,3 + base 148,0 ⇒ **555,6 Mio**. Nommé : **fragmentation +193 Mio**
  (mesurée), archive FITS **0** (chemins seuls), références d'alignement
  **21,2 Mio** max.
- **RÉSIDUEL NOMMÉ — `perf-9` (v2.98.7, 683 s, 67 frames, 3 darks)** : hors
  stackers **1 156,5 Mio** ; la jauge **`postes`** nomme **553,2 Mio** de tableaux
  applicatifs — `disp` **226,1** (brut niveaux + couches `vl_compo`) + `rendu`
  **206,2** (images publiées par le `FilRendu`) + **`calib` 96,2** (les 3 darks
  maîtres, 32,07 chacun) + 3 aligneurs **24,6** + petits 0,1. Reste **455,3 Mio
  sans tableau nommé** (1 156,5 − 553,2 − 148,0 de base), dont **193 Mio de
  fragmentation mesurée** ⇒ ~262 Mio de non-tableau (tas Tk/PIL/OpenCV, objets
  Python, arènes). **La chaîne de rendu (`disp` + `rendu` = 432,3 Mio) est 47,8 %
  du hors-stackers** — c'est le prochain poste à instruire.
  Le poste `calib` vaut **96,2** et non ~283 Mio : Alain a chargé **3 darks**
  (60/120/180 s, **aucun flat**) — le modèle est confirmé au chiffre près
  (3 × 32,07 ; 5 darks + 5 flats = ~321 Mio).
- **DÉFAUT TROUVÉ (21/10) — CORRIGÉ en v2.98.7** : les chemins dark/flat n'étaient
  PAS persistés — `_load_dark`/`_load_flat` chargeaient l'image en mémoire
  (`calib.darks`/`flats`) et n'écrivaient RIEN dans `CONFIG` : d'où la
  re-sélection à chaque session. Ils étaient bien APPLIQUÉS (`worker.py:703`,
  `calib.apply`, une fois par frame, sur les tableaux en mémoire — pas de
  relecture disque). Correctif : `_persister_calib` (au geste) + restauration
  différée (`_restaurer_calib_differe`, fil démon borné → `_calib_q` → `_tick`).
  PIÈGE : l'absence de clé dans `config.json` ne prouve PAS qu'aucun maître
  n'est chargé — c'est ce que la 1re version de l'outil affirmait à tort.
- **LOT « COPIE → RÉFÉRENCE » — PREUVE (v2.98.5)** : banc NEUF
  `_test_p1_memoire_reference.py` (**30 vérifications**, TOUT PASSE) — contrat
  d'immuabilité vérifié sur les vraies classes (image identique **au bit** après
  nouvelles frames, aucun partage avec `sum`/`wsum`), image du stacker **par
  identité**, rendu **SHA-256 égal** à l'ancien comportement, garde de source
  (plus de `.copy()` sur la branche `stack`), écart mémoire **mesuré** = nbytes,
  **RSS −96 Mo** rendus à la libération. Non-régressions : jalons 68/69, banc 1b,
  garde-fou (**pyright 0 / 56 fichiers**, hashes au bit).
- **`empilement`** 2 751 ms/frame et **`lecture_frame`** 6 697 ms/frame (scan
  réseau 326 ms/dossier/passe) : après la mémoire.
- **Pire tour `ui_tick`** : 74,1 ms (contre 5 952 ms) — sous le seuil du Guet.

### Fichiers touchés par l'audit (détail dans `CLAUDE.md` et le changelog)
- **Phase 0** : `avastack/perf.py` (NEUF, opt-in, coût nul) + câblage dans
  `ui/app.py`, `ui/renderer.py`, `core/worker.py` ; banc `_test_phase0_perf` (110).
- **1a** : `ui/renderer.py` + `ui/app.py` ; banc `_test_1a_rendu_final` (40).
- **1b** : `avastack/ui/rendu.py` (NEUF, typé), `ui/renderer.py`,
  `ui/widgets/histogram.py` (`_histogrammes_purs`, PURE) ; banc
  `_test_render_worker_bit_exact` (41, hashes d'empilement au bit) ; bancs passés
  en rendu **immédiat**.
- **`tick_avant` ① (v2.98.3)** : `perf.t0_cpu` / `perf.duree_attente`, branchés
  sur `ui_tick` et `tick_avant` ; banc Phase 0 section [2 bis].
- **`tick_avant` ② (v2.98.4)** : `cameras/multifolder.py` SEUL (calcul déplacé
  dans `read()`) ; banc NEUF `_test_multifolder_last_file` (24).
- **Mémoire (21/10, mesure seule)** : `bancs/_mesure_memoire_stackers.py`
  (NEUF — inventaire nommé p3/p4, postes mesurés au RSS, **[3 bis] chaîne de
  rendu** avec la vraie `DisplayProcessor`, projection à la géométrie réelle,
  réconciliation, levier float32 chiffré).
- **Copie → référence (v2.98.5)** : `core/worker.py`, `ui/app.py`,
  `processing/display.py` (`_vl_src` retiré) ; banc NEUF
  `_test_p1_memoire_reference.py` (30) ; `_mesure_memoire_stackers.py` mis à
  jour (la chaîne ne compte plus une copie ; note de millésime sur le RSS).
- **Persistance dark/flat (v2.98.7)** : `processing/calibration.py`
  (`poser_dark`/`poser_flat`, `cles_persistees`, `lire_cles_persistees`) ;
  `ui/app.py` (`_persister_calib`, `_restaurer_calib_differe`, `_charger_maitre`,
  `_appliquer_calib`, file `_calib_q` drainée par `_tick_corps`) ;
  `ui/config_ui.py` (appel depuis `_restaurer_config`) ; banc NEUF
  `_test_calib_persistance.py` (26).

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

- **`perf-6` RELEVÉ le 21/10** (590 s, 47 frames, VeraLux + chroma) :
  `attente.tick_avant.part_attente` = **0,969** (439,6 s d'attente pour 14,3 s
  de CPU), `cores_moyens` = **0,98** ⇒ ce n'est PAS un manque de cœurs.
  Cause nommée par la pile du Guet de gel : `MultiFolderCamera.last_file` fait
  `exists` + `getmtime` sur **5 dossiers SMB** à CHAQUE tour d'interface.
- **LIVRÉ le 21/10 (v2.98.4, « zéro changement »)** : `last_file` ne fait plus
  aucune I/O ; le calcul identique est fait par `read()`, une fois par image,
  dans le fil d'acquisition. Banc `_test_multifolder_last_file.py` (22
  vérifications) : détection live intacte, **0 appel système** espionné.
- **`perf-7` RELEVÉ ET GAGNÉ le 21/10** : `ui_tick` 456,5 s → **18,6 s**
  (77 % → **3,3 %** du mur), 1,23 ms/tour, max 74,1 ms, 27 tours/s.
  La mesure du fil (`t0_cpu` + `duree_attente`) et le correctif `last_file`
  sont **validés en réel** ; plus aucune I/O sur le fil d'interface.
- **MESURE MÉMOIRE LIVRÉE le 21/10 (aucun fichier applicatif touché)** : outil
  `bancs/_mesure_memoire_stackers.py` — ① inventaire nommé (p3 **et** p4),
  ② projection à la géométrie réelle, ③ postes d'image mesurés au RSS,
  **[3 bis] chaîne de rendu** (vraie `DisplayProcessor`, rendu VeraLux réel),
  ④ réconciliation, ⑤ levier float32 chiffré. Résultats : **3 096,0 Mio
  constatés** (69,4 % du RSS du run), jauge qui **sous-compte 160,3 Mio**,
  **chaîne de rendu 376,8 Mio** (le « Go inexpliqué »), **résiduel ramené à
  637,7 Mio**. Détail chiffré dans « Problèmes ouverts ».
- **LOT « COPIE → RÉFÉRENCE » LIVRÉ le 21/10 (v2.98.5)** : `_stack_pleine_res`
  garde une référence (worker + `_pousser_rendu`), repli « frame seule » en
  copie défensive, `_vl_src` retiré. Banc `_test_p1_memoire_reference.py` (**30
  vérifications**, TOUT PASSE) : immuabilité vérifiée sur les vraies classes,
  image du stacker **par identité**, rendu **SHA-256 égal** à l'ancien
  comportement, écart mémoire mesuré, **RSS −96 Mo** à la libération.
  Non-régressions vertes : jalons 68 et 69, banc 1b (« TOUS LES TESTS
  PASSENT »), garde-fou (**pyright 0 / 56 fichiers**, hashes d'empilement au
  bit). La chaîne de rendu re-mesurée vaut **280,6 Mio** (376,8 − 96,2).
- **TEST UNIQUE (v2.98.7) — FAIT LE 21/10, LES DEUX SUJETS EN UNE SESSION** :
  ① la persistance dark/flat est **validée en réel** (Alain : « la sauvegarde
  fonctionne, on retrouve bien les dark quand on réouvre ») ; ② le relevé
  **`perf-9.json`** existe (683,2 s, 67 frames, 3 darks chargés) et la jauge
  `postes` a **nommé le poste `calib` : 96,2 Mio**. `ui_tick` reste à **3,3 %**
  du mur (22,7 s / 683 s), `tick_avant` 0,70 ms/tour.
- **PROCHAINE ACTION (accord d'Alain AVANT de coder)** : instruire le poste
  **`rendu` 206,2 Mio** (ce que le `FilRendu` RETIENT : image étirée publiée,
  pré-étirée, job) — avec `disp` 226,1, la chaîne de rendu pèse **432,3 Mio**,
  soit **47,8 % du hors-stackers**. Règle : **une copie ne se supprime qu'après
  avoir lu QUI la lit** (auditer les lecteurs AVANT d'agir, preuve au bit) — et
  pas de proposition float32 (écartée).
  Ensuite : **`empilement`** 2 938 ms/frame (décomposer alignement vs rejet
  kappa-sigma AVANT de toucher) ; puis **`lecture_frame`** 4 765 ms/frame.
- **ÉCARTÉ, à ne pas réintroduire sans mesure** : `cv2.setNumThreads`,
  `sys.setswitchinterval`, priorité OS du fil Tk — le CPU n'était pas le
  problème (0,98 cœur utilisé sur 14). Et **float32 : ÉCARTÉ DÉFINITIVEMENT**
  (Alain, 21/10 — peut changer l'image ; le chiffrage reste une TRACE, pas un
  plan).
- **`CLAUDE.md`** : à jour — leçon v2.98.3 (mesurer le CPU du fil), correction de
  l'affirmation fausse « le levier est `cv2.setNumThreads` », règle
  « AUCUNE I/O SUR LE FIL D'INTERFACE » avec son correctif et son banc, et
  section NEUVE « Calibration dark/flat — persistance des maîtres (v2.98.7) ».
- Aucune release ; `master` reste à v2.96.1 ; le Store à v2.71.1.

### Contexte de reprise (à coller — 2 phrases)
Branche **`OptimisationUI`, v2.98.7** : la **persistance dark/flat est VALIDÉE EN
RÉEL** (les 3 darks reviennent à l'ouverture) et le relevé **`perf-9`** nomme le
résiduel — `calib` **96,2 Mio** (3 darks), `disp` + `rendu` **432,3 Mio** (47,8 %
du hors-stackers), reste **455,3 Mio** sans tableau nommé dont **193 Mio de
fragmentation** ; `ui_tick` tient à **3,3 %**. Prochaine action (accord AVANT de
coder) : instruire ce que le `FilRendu` **retient** (`rendu` 206,2 Mio) — audit
des lecteurs et preuve au bit, jamais float32.

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

- **21/10/2026** : **1b VALIDÉE EN RÉEL** (v2.98.2) — `ui_rendu` 102 s → 2,2 s,
  calcul dans `fil_rendu` (169 s), UI qui répond ; `tick_avant` reste à instruire.
- **20/10/2026** : **1a VALIDÉE EN RÉEL** (v2.98.1) — `rendus` 132 → 51,
  `ui_tick` 61 % → 48 %.

