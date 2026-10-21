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

Versions : **`OptimisationUI` = v2.98.9** (Phase 0 + **1a** + **1b** + **`tick_avant`**
LIVRÉS ET **VALIDÉS EN RÉEL** — `perf-7` : `ui_tick` **3,3 %** du mur ; **mémoire
MESURÉE** par un outil neuf ; **« copie → référence » LIVRÉ ET VALIDÉ EN RÉEL**
(v2.98.5) ; **jauge `postes` LIVRÉE** (v2.98.6) ; **persistance dark/flat
CORRIGÉE** (v2.98.7) ; **DÉFAUT « STF = IMAGE BLANCHE » CORRIGÉ ET VALIDÉ EN
RÉEL** (v2.98.8) ; **`empilement` DÉCOMPOSÉ ET MESURÉ** (v2.98.9, **aucun pixel
changé** — le poste dominant n'est PAS celui qu'on croyait) ; **aucune
release**) · `master` = v2.96.1 · **Store publié = v2.71.1**.

**Gouvernance** : aucune release GitHub sans accord ; **demander AVANT de
démarrer le lot suivant** ; ne jamais déduire l'état d'une case de `config.json`
— on MESURE le fichier produit.

---

## Session des 20-21/10/2026 — Phase 1, mémoire, persistance dark/flat et défaut STF VALIDÉS EN RÉEL · **`empilement` DÉCOMPOSÉ ET MESURÉ (v2.98.9)**

### État actuel
- **Tout est LIVRÉ, VALIDÉ EN RÉEL, COMMITTÉ ET POUSSÉ** (`OptimisationUI`,
  v2.98.9). Phase 0, **1a**, **1b**, `tick_avant` ① + ②, la mesure mémoire,
  **copie → référence**, la **jauge `postes`**, la **persistance dark/flat**
  (v2.98.7), le **défaut « basculer sur STF après VeraLux = image blanche »**
  (v2.98.8, **« Testé OK » d'Alain**) et la **DÉCOMPOSITION de `empilement`**
  (v2.98.9, **mesure seule, aucun pixel changé**) : **rien n'est en attente de
  code**. Ce qui reste n'est plus une mesure mais une DÉCISION : **quel levier
  optimiser, et dans quel ordre** — elle appartient à Alain.
- **`empilement` EST DÉCOMPOSÉ ET MESURÉ (v2.98.9)** : outil NEUF
  `bancs/_mesure_empilement.py` (rejoue de VRAIES brutes dans la VRAIE
  `_worker_empiler_frame`, config HERMÉTIQUE, `perf` armé, MÊME bloc que le
  worker) + DIX sous-chronos `perf` opt-in dans `core/worker.py` (coût nul hors
  `--perf`, **résultat identique AU BIT**). **Le levier attendu par l'audit
  n'est PAS le poste dominant** : sur 8 brutes OSC réelles de 8,4 Mpx,
  `empilement` = **2 704,6 ms/frame** (même ordre que les 2 938 de `perf-9`) et
  **l'ALIGNEMENT (ORB+RANSAC) pèse 40,9 %** — le REJET kappa-sigma ne pèse que
  **4,7 %**.
- **LEVIER n°5 CHIFFRÉ sur le MÊME jeu de brutes** : `winsorized` fenêtre 4
  porte `empilement` à **5 369,9 ms/frame (×1,99)** — le REJET passe de 127,6 à
  **2 167,9 ms/frame (×17)** et DEVIENT dominant (40,4 %). `winsorized` coûte
  donc **~2,67 s/frame de plus** que `kappa` à cette géométrie.
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

Repères `perf-9` (683,2 s, 67 frames, **3 darks maîtres**) : `fil_rendu` 148,0 s
(1 276 ms/rendu), `empilement` **2 938 ms**, `lecture_frame` **4 765 ms**,
stackers 2 935,4 Mo, **RSS max 4 252,2 Mo** (pic 4 687,5), `cores_moyens` 1,24,
`rendus` 116 pour 67 frames, `tick_postes` 4,9 ms (~0,02 % du mur). Repères
`perf-7` (556 s, 47 frames) : `fil_rendu` 103,4 s, `empilement` 2 751 ms,
`lecture_frame` 6 697 ms, RSS 3 163 Mo, `cores_moyens` 1,12, `rendus` 76.
Détail complet : `perf-*.json` (hors dépôt) et changelog `avastack/__init__.py`.

**Lecture** : 1a et 1b ont tenu leurs promesses (`ui_rendu` 276 → 1,2 s) ; le
`tick_avant` à 77 % du mur **sans travail mesuré dedans** était de l'**attente**
(une I/O réseau — `getmtime` — à chaque tour), corrigé en v2.98.4 : **3,3 %**.

### DÉCOMPOSITION de `empilement` — MESURÉE (v2.98.9)

Outil : `bancs/_mesure_empilement.py` (8 brutes **OSC réelles** de 8,4 Mpx,
dossier surveillé réel, vraie `_worker_empiler_frame`, `perf` armé). Relevés :
`bancs/_mesure_empilement.json` et `_mesure_empilement_wins.json` (hors dépôt).

| poste | `kappa` f.8 | `winsorized` f.4 |
|---|---|---|
| **`empilement` (TOTAL)** | **2 704,6** | **5 369,9** (×1,99) |
| `empilement_align` — ORB+RANSAC | **1 105,3 (40,9 %)** | 1 363,3 (25,4 %) |
| `empilement_archive` — FITS (I/O) | 483,8 (17,9 %) | 478,8 (8,9 %) |
| `empilement_moyenne` — sum/wsum | 415,2 (15,4 %) | 549,2 (10,2 %) |
| `empilement_flou` — filtre anti-floues | 291,5 (10,8 %) | 429,7 (8,0 %) |
| `empilement_creation` — 1× (démarrage) | 133,7 (4,9 %) | 196,8 (3,7 %) |
| `empilement_rejet` | **127,6 (4,7 %)** | **2 167,9 (40,4 %)** |
| `empilement_score` — détection d'étoiles | 91,1 (3,4 %) | 113,2 (2,1 %) |
| `empilement_warp` — `warpAffine` | 20,5 (0,8 %) | 17,1 (0,3 %) |
| `empilement_canal` · `empilement_rejeu` | 0,0 | 0,0 |
| **RÉSIDUEL non nommé** | 35,8 (1,3 %) | 53,8 (1,0 %) |

**Le poste dominant n'est PAS celui que l'audit attendait** : c'est
**l'ALIGNEMENT** (40,9 %), pas le rejet (4,7 %). Le résiduel à 1,3 % prouve que
la décomposition est quasi complète. **Levier n°5 CHIFFRÉ** (2e colonne, même
jeu de brutes) : `winsorized` f.4 **double** le total et fait du REJET le poste
dominant (×17) — **−2,67 s/frame** sur 8 brutes réelles.

**ANCRE COMPOSITION** (le plus proche de `perf-9` : brutes **MONO** réelles M33,
4 rôles L/R/G/B, `winsorized` f.4, 12 frames = 3 par rôle → relevé
`bancs/_mesure_empilement_lrgb.json`) : `empilement` **4 506,9 ms/frame** —
`empilement_align` **2 212,8 (49,1 %)** · `empilement_moyenne` **1 438,1
(31,9 %)** · flou 292,4 (6,5 %) · score 160,2 (3,6 %) · archive 157,1 (3,5 %) ·
création 133,0 (3,0 %) · rejet 47,3 (1,0 %) · warp 13,2 (0,3 %) · résiduel 52,8
(1,2 %). ⇒ **la MOYENNE devient le poste n°2** et grandit avec le nombre de rôles
(415,2 ms à 1 rôle → 1 438,1 à 4). ⚠️ Le rejet y paraît faible parce que
**3 frames par rôle ne remplissent pas la fenêtre** (warmup) : ce n'est PAS un
coût stabilisé de `winsorized`.

**ATTENTION — ce qu'un relevé de banc ne dit pas** : les durées ABSOLUES
dépendent de la machine et du chemin mesuré (ici OSC 3 canaux mono rôle ; l'ancre
composition est MONO 4 rôles). Ce qui se transporte, c'est la **répartition** et
le **rapport kappa/winsorized** (×1,99 sur la MÊME machine et les MÊMES brutes).
Pour la mesure qui engage la production : `python AVAStack.py --perf` sur une
session réelle — les mêmes sous-chronos y sont posés, coût nul hors `--perf`.

### Enveloppe mémoire MESURÉE (21/10/2026 — outil, aucune session requise)

| poste | **MONO** 1 dossier | **OSC** 3 canaux | **MAX** 5 rôles |
|---|---|---|---|
| **RSS réel attendu** | **~1,2 Go** | **~2,6 Go** | **~4,5 Go** |
| **PIC réel attendu** (rendu VeraLux) | **~1,7 Go** | **~4,0 Go** | **~5,0 Go** |

Ancre réelle : `perf-9` (5 rôles, 3 darks) → RSS max **4 252,2 Mo**, pic
**4 687,5 Mo**. **Recommandation : 4 Go** pour un dossier MONO, **8 Go** pour une
source OSC, **8 Go = plancher / 16 Go conseillé** pour 5 rôles avec darks ET
flats. Leviers : fenêtre 4 → 2 (−320 Mio à 5 rôles), méthode `kappa` au lieu de
`winsorized` (supprime `_buf`), moins de rôles. Détail du modèle, par poste et
par rôle : **`CLAUDE.md` (« ENVELOPPE MÉMOIRE »)** + outil
`bancs/_mesure_memoire_stackers.py` (`--roles`, `--canaux`, `--maitres`).

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
- ✅ **CORRIGÉ (v2.98.8) — « STF = IMAGE BLANCHE »** : reproduit AVANT de corriger,
  mesuré, corrigé ; l'hypothèse n°1 du handoff était FAUSSE (la chaîne n'était pas
  en cause — c'était la **MÉMOIRE du STF**, `_stats`, posée en VeraLux et
  réutilisée à la bascule). Leçon : **un état « d'après étirement » du STF ne se
  périme pas tout seul** (détail : `CLAUDE.md` + changelog v2.98.8).
- ✅ **CORRIGÉ (v2.98.7)** : les chemins dark/flat n'étaient PAS persistés
  (`_load_dark`/`_load_flat` chargeaient sans écrire dans `CONFIG`) → re-sélection
  à chaque session. PIÈGE : l'absence de clé dans `config.json` ne prouve PAS
  qu'aucun maître n'est chargé.
- **Phase 1 : critère ATTEINT** (`ui_tick` 3,3 % < 20 %) — **test complet d'Alain
  AVANT toute fusion vers `master` et toute release** (sa décision, pas la nôtre).
- **MÉMOIRE — l'audit est CLOS, le résiduel est NOMMÉ** : le poste `rendu` est un
  **artefact de parcours MESURÉ** (`FilRendu` garde `_hote` = l'App, que la jauge
  re-traverse : **il n'y a rien à récupérer dans le fil**, il ne retient 0 tableau).
  `perf-9` : hors stackers 1 156,5 Mio, dont la jauge `postes` nomme 553,2 Mio
  (`disp` 226,1 · `rendu` 206,2 · **`calib` 96,2** · 3 aligneurs 24,6) ⇒ ~540 Mio
  sans tableau nommé (dont **193 Mio de fragmentation MESURÉE**). **Aucune fuite.**
  Les 3 corrections de mesure proposées sont **ABANDONNÉES** (Alain, 21/10).
- **`lecture_frame`** 4 765 ms/frame (`perf-9`, scan réseau, dont de l'ATTENTE) :
  dernier poste non instruit, **APRÈS `empilement`**. Pire tour `ui_tick` : 92 ms
  (sous le seuil du Guet). Géométrie RÉELLE des brutes = **3856×2180 = 8 406 080
  px** ; `source_px` (7,4 Mpx) est l'image **RECADRÉE** — ne pas confondre.

### Fichiers touchés par l'audit (détail : changelog `avastack/__init__.py` + `git log`)
- **v2.98.9 (ce lot)** : `core/worker.py` (DIX sous-chronos `empilement_*`
  opt-in dans `_worker_empiler_frame`) ; `bancs/_mesure_empilement.py` (NEUF,
  outil de MESURE + `--autotest`) ; `avastack/__init__.py` (version + changelog).
- **v2.98.0 → v2.98.8** (détail : commits `e307ad4`, `f902040` et le changelog) :
  `perf.py` (NEUF), `ui/rendu.py` (NEUF), `ui/app.py`, `ui/renderer.py`,
  `ui/config_ui.py`, `processing/display.py`, `processing/calibration.py`,
  `cameras/multifolder.py`, et les bancs `_test_phase0_perf` (110),
  `_test_1a_rendu_final` (40), `_test_render_worker_bit_exact` (41),
  `_test_multifolder_last_file` (24), `_test_p1_memoire_reference` (30),
  `_test_p1_postes_memoire` (17), `_test_calib_persistance` (32),
  `_test_bascule_stf_blanc` (12), `_mesure_memoire_stackers.py`, `_diag_*`.

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
| **`empilement` — DÉCOMPOSÉ (v2.98.9)** | **LIVRÉE : MESURÉE** (0 pixel changé) | **2 704,6 ms/frame** (OSC) · **align 40,9 %** · archive 17,9 % · moyenne 15,4 % · rejet 4,7 % · résiduel 1,3 % |

**Critères de sortie** : ① `rendus` ≈ frames (**atteint en `perf-7` : 1,12×** ;
`perf-9` 1,73× — gestes de réglages) ;
② `ui_tick` < 20 % du mur (**atteint : 3,3 %**) ; ③ image finale au bit
(**atteint**) ; ④ 0 gel du Guet (**atteint** — pire tour 92 ms) ; ⑤ garde-fou
vert (**atteint**).


---

## En attente / prochaine session

- **`empilement` EST MESURÉ (v2.98.9) — CE QUI ATTEND MAINTENANT, C'EST UNE
  DÉCISION, PAS UNE MESURE.** Trois leviers, chiffrés, par ordre de poids sur le
  jeu réel mesuré :
  ① **l'ALIGNEMENT** (`empilement_align`, ORB+RANSAC) : **40,9 %** à 1 rôle,
     **49,1 %** à 4 rôles — le vrai premier poste. Piste à INSTRUIRE (pas à
     coder) : ce que `StarAligner.compute` fait par frame (nombre de features
     ORB, cascade triangles → étoiles → phase, réessai +180°, résolution des
     détections), et si la référence d'alignement est recalculée trop souvent.
  ② **la MOYENNE** (`empilement_moyenne`, `sum/wsum`) : 15,4 % à 1 rôle mais
     **31,9 % à 4 rôles** — elle grandit avec le nombre de rôles. Piste : `mean()`
     est appelée UNE fois par frame (mémoïsée sur `n`) ; vérifier ce qui, en
     composition, la rend si lourde (recadrage d'intersection, combine L,
     normalisation commune).
  ③ **le REJET** : **4,7 % en `kappa`**, mais **40,4 % en `winsorized`** — le
     levier le PLUS direct (un réglage, pas du code), chiffré à **−2,67 s/frame**
     sur 8 brutes réelles. Attention : ce n'est PAS un défaut à corriger, c'est
     un ARBITRAGE (la qualité du rejet) — décision d'Alain.
- **CE QUI ATTEND ALAIN** : ① choisir le levier (et l'ordre) ; ② sa **fusion vers
  `master` + la release** (aucune n'a été faite : `master` = v2.96.1, Store =
  v2.71.1) ; ③ le **test complet en réel** de la branche (la décomposition ne
  change aucun pixel, mais elle a ajouté des lignes sur le chemin du worker).
- **ABANDONNÉ (Alain, 21/10/2026)** : les 3 corrections de mesure proposées
  (ne pas traverser `_hote` dans la jauge, ne pas compter les alias des
  stackers, formule [6] de l'outil) — **ne pas les reprendre** sans demande.
- **ÉCARTÉ, à ne pas réintroduire sans mesure** : `cv2.setNumThreads`,
  `sys.setswitchinterval`, priorité OS du fil Tk — le CPU n'était pas le
  problème (0,98 cœur utilisé sur 14). Et **float32 : ÉCARTÉ DÉFINITIVEMENT**
  (Alain, 21/10 — peut changer l'image ; le chiffrage reste une TRACE, pas un
  plan).
- **Banc 79 (`_test_perf_reactivite_jalon79.py`)** : 4 échecs **PRÉEXISTANTS**
  (identiques sans le lot v2.98.8) — l'étape 1b a déplacé l'instrumentation du
  banc (`_maj_histogrammes` → `_draw_hist`). **Ce n'est pas une régression.**
- **`CLAUDE.md`** : une entrée est **PROPOSÉE** (le fichier ne s'écrit jamais
  sans accord — c'est sa règle de maintenance) : les **sous-chronos `empilement`
  (v2.98.9)** et le piège « un relevé `perf` se lit en TOTAUX, pas en moyennes
  par poste ». Le reste est à jour : leçon v2.98.3, « AUCUNE I/O SUR LE FIL
  D'INTERFACE », persistance des maîtres (v2.98.7), « la mémoire du STF se
  périme » (v2.98.8), ENVELOPPE MÉMOIRE.
- Aucune release ; `master` reste à v2.96.1 ; le Store à v2.71.1.

### Contexte de reprise (à coller — 2 phrases)
Branche **`OptimisationUI`, v2.98.9** : Phase 1, mémoire, persistance dark/flat,
défaut « basculer sur STF après du VeraLux = image blanche » et **décomposition
MESURÉE de `empilement`** sont livrés (**aucun pixel changé**). `empilement`
2 704,6 ms/frame (OSC réel) : **ALIGNEMENT 40,9 %** (et **49,1 %** à 4 rôles),
moyenne 15,4 % (31,9 % à 4 rôles), archive 17,9 %, rejet 4,7 % — et `winsorized`
f.4 **double** le total (rejet ×17). Prochaine action : **instruire l'ALIGNEMENT**
(ce que `StarAligner.compute` fait par frame) — ou la décision d'Alain de prendre
le levier `kappa`.

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
- **Un seuil ABSOLU de temps est FLAKY** : ancrer les assertions sur une
  comparaison INTERNE (cas A vs cas B du même run) ou sur une mesure directe.
- **Un relevé de `perf` se lit en TOTAUX, jamais en moyennes par poste**
  (v2.98.9) : `moy_ms` divise chaque poste par SON propre `n` — un poste qui
  n'arrive qu'une fois (création, rejeu) pèse alors `total/1` et la « somme des
  postes » dépasse le total (constaté : 121 % d'un total). `bancs/_mesure_empilement.py`
  ramène donc TOUS les postes au nombre d'appels de `empilement` : la somme égale
  le total et le résiduel devient interprétable (1,0-1,3 %).
- **Un coût mesuré en banc n'est pas un coût de production** : le rejet
  `winsorized` mesuré à **3 frames par rôle** est en WARMUP (la fenêtre n'est pas
  pleine, rien n'est rejeté) — il paraît 46× moins cher qu'à 8 frames par rôle.
  Toujours publier `n` À CÔTÉ de la durée.
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

