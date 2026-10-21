# AVANCEMENT.md — mémoire de travail à court terme

(Complète `CLAUDE.md`, mémoire LONG terme. Ici : état courant, décisions, pièges
actifs, prochaine action. Le détail daté vit dans `avastack/__init__.py`
(changelog) et `git log`.)

---

## ⚠️ BRANCHE DE TRAVAIL ACTIVE — **`master`** (depuis le 21/10/2026)

**`OptimisationUI` est FUSIONNÉE dans `master`** (demande explicite d'Alain,
21/10/2026, après son choix **Option A** : on n'optimise RIEN de plus — cf.
« Décision » ci-dessous). Le chantier d'audit performance/mémoire est **CLOS** et
**tout travail futur se fait sur `master`**.

> **RÈGLE FERME** : `master` est désormais la branche de travail ET de release.
> `OptimisationUI` n'est plus développée (la garder pour mémoire jusqu'à demande
> explicite de suppression). **`LRGBHa` est FERMÉE** — ne pas la recréer.

Versions : **`master` = v2.98.9** (Phase 0 + **1a** + **1b** + **`tick_avant`** +
mémoire + persistance dark/flat + défaut STF + décomposition d'`empilement` :
tout est **livré**, les derniers lots sont **VALIDÉS EN RÉEL** ; **aucune
release**) · **Store publié = v2.71.1**.

**Gouvernance** : aucune release GitHub sans accord ; **demander AVANT de
démarrer le lot suivant** ; ne jamais déduire l'état d'une case de `config.json`
— on MESURE le fichier produit.

---

## Session des 20-21/10/2026 — audit performance/mémoire **CLOS** · **`master` = v2.98.9, prêt pour la RELEASE**

### État actuel
- **LE CHANTIER EST CLOS, PAR DÉCISION D'ALAIN (21/10/2026) : OPTION A — on
  n'optimise RIEN de plus.** La décomposition MESURÉE d'`empilement` a montré
  qu'il n'y a **pas de levier rentable** : en acquisition en direct les poses
  font 60 à 180 s et l'empilement n'en consomme que ~2,7 s (**jamais un
  goulot**) ; l'interface répond (**3,3 %** du mur) ; **aucun défaut n'est
  ouvert**. Les leviers chiffrés restent documentés plus bas **POUR MÉMOIRE** —
  **ne pas les reprendre sans demande explicite**.
- **`OptimisationUI` est FUSIONNÉE dans `master`** — merge `--no-ff` **`20755bf`**
  (la trace du lot est gardée), `master` passe de **v2.96.1 → v2.98.9** et est
  **poussé** (`efb2911..20755bf`) ; contenu **identique** à `OptimisationUI`
  (`git diff` vide), arbre de travail propre, branche active = **`master`**.
- **PROCHAINE SESSION : LA RELEASE** (tag + notes GitHub depuis `master`) — c'est
  la SEULE chose qui reste, et elle est **autorisée par Alain**. **Aucun code à
  écrire avant.**
- **Ce qui arrive dans `master`** : Phase 0 (instrumentation `perf` opt-in,
  coût nul), **1a** (un seul rendu par frame), **1b** (rendu hors fil Tk),
  **`tick_avant`** (I/O réseau retirée du fil d'interface : `ui_tick` 456,5 s →
  18,6 s), la **mémoire** (« copie → référence », jauge `postes`), la
  **persistance dark/flat**, le **défaut « basculer sur STF après VeraLux =
  image blanche »** et la **décomposition d'`empilement`** (mesure seule).
- **Tout est COMMITTÉ ET POUSSÉ**, arbre de travail propre, **garde-fou VERT**
  (306 `.py`, surface publique 76 symboles, **hash d'empilement inchangé AU BIT**
  ×3, `pyright` 0 sur 56 fichiers) et bancs du worker VERTS (J5, voie A Ha 129b,
  trace des rôles 131, phase 0 `perf`).
- **Ce qui a été corrigé et VALIDÉ EN RÉEL** : `ui_tick` **3,3 %** du mur
  (`perf-7` 456,5 → 18,6 s ; `perf-9` 22,7 s / 683 s) — le fil d'interface ne
  fait plus le calcul et plus aucune I/O ; pire tour **92 ms** (plus de gel de
  2 s). Ressenti d'Alain (le vrai critère) : **« l'interface répond nettement
  mieux »**. La **persistance dark/flat** (v2.98.7, « on retrouve bien les dark
  quand on réouvre ») et le **défaut « basculer sur STF après VeraLux = image
  blanche »** (v2.98.8, **« Testé OK »**) sont corrigés : causes et preuves au
  changelog + `CLAUDE.md`. La mémoire est **NOMMÉE** (jauge `postes`) et
  **AUCUNE fuite** n'a été trouvée.

### Mesures de référence — POUR MÉMOIRE (ne pas reprendre sans demande)

**Décomposition d'`empilement`** (outil `bancs/_mesure_empilement.py` : 8 brutes
OSC réelles de 8,4 Mpx, `perf` armé, VRAIE `_worker_empiler_frame`) — ms/frame :

| poste | `kappa` f.8 | `winsorized` f.4 |
|---|---|---|
| **`empilement` (TOTAL)** | **2 704,6** | **5 369,9** (×1,99) |
| `empilement_align` — ORB+RANSAC | **1 105,3 (40,9 %)** | 1 363,3 (25,4 %) |
| `empilement_archive` — FITS (I/O) | 483,8 (17,9 %) | 478,8 (8,9 %) |
| `empilement_moyenne` — sum/wsum | 415,2 (15,4 %) | 549,2 (10,2 %) |
| `empilement_flou` — filtre anti-floues | 291,5 (10,8 %) | 429,7 (8,0 %) |
| `empilement_creation` — 1× (démarrage) | 133,7 (4,9 %) | 196,8 (3,7 %) |
| `empilement_rejet` | **127,6 (4,7 %)** | **2 167,9 (40,4 %)** |
| `empilement_score` · `_warp` · `_canal` · `_rejeu` | 91,1 · 20,5 · 0 · 0 | 113,2 · 17,1 · 0 · 0 |
| **RÉSIDUEL non nommé** | 35,8 (1,3 %) | 53,8 (1,0 %) |

**Le poste dominant n'est PAS celui que l'audit attendait** : l'ALIGNEMENT
(40,9 %), pas le rejet (4,7 %). **En composition** (4 rôles MONO réels M33,
`winsorized` f.4, 3 frames/rôle) : `empilement` 4 506,9 ms/frame — align **49,1 %**
et **moyenne 31,9 %** (elle grandit avec le nombre de rôles) ; le rejet y paraît
à 1,0 % **par WARMUP** (fenêtre non pleine), ce n'est pas un coût stabilisé.
⚠️ Les durées ABSOLUES dépendent de la machine : ce qui se transporte est la
**répartition** et le **rapport kappa/winsorized**.

**Le « mur » d'un tour de frame** (`perf-9`, session réelle de 683 s) :
`lecture_frame` **4 765 ms** + `empilement` **2 938 ms** + `fil_étirement`
~1 250 ms ≈ **9 s par image**. Les 67 frames de ce relevé ne peuvent PAS venir
d'une acquisition en direct (67 × 60 s de pose ≫ 683 s) : c'était un
**RATTRAPAGE de dossier déjà rempli**. En direct (poses de 60-180 s), il reste
**60 à 180 s de repos** entre deux images pour ~2,7 s de travail.

### Décision — **OPTION A : ON N'OPTIMISE RIEN DE PLUS** (Alain, 21/10/2026)

Après la décomposition MESURÉE d'`empilement`, les trois leviers possibles ont
été chiffrés PUIS ÉCARTÉS, pour une raison de TERRAIN et non technique : **en
acquisition en direct, 2,7 s de travail ne gênent rien** (60 à 180 s de repos
entre deux poses), l'interface répond (3,3 % du mur) et **aucun défaut n'est
ouvert**. Écartés **POUR MÉMOIRE**, à ne pas reprendre sans demande explicite :
① l'ALIGNEMENT (40,9 %, mais c'est le cœur de la qualité — risqué) ;
② la MOYENNE en composition (31,9 %, risque moyen sur les pixels) ;
③ le réglage `kappa` ↔ `winsorized` (un menu déroulant, mais c'est un arbitrage
de QUALITÉ, pas de performance). Si un jour le RATTRAPAGE d'un gros dossier
gêne, le premier poste à instruire est **`lecture_frame`** (4 765 ms, dont de
l'attente), pas l'alignement.

### Enveloppe mémoire (dimensionnement)

**~1,2 Go** MONO · **~2,6 Go** OSC · **~4,5 Go** 5 rôles avec darks et flats
(pic ~+0,5 Go au rendu VeraLux) ; ancre `perf-9` : RSS max 4 252,2 Mo.
**Recommandation : 4 Go** pour un dossier MONO, **8 Go** pour une source OSC,
**8 Go = plancher / 16 Go conseillé** en composition. Leviers : fenêtre 4 → 2
(−320 Mio à 5 rôles), méthode `kappa` au lieu de `winsorized` (supprime `_buf`),
moins de rôles. Détail : `CLAUDE.md` (« ENVELOPPE MÉMOIRE »).

### Décisions (détail dans `CLAUDE.md` et le changelog)
- **MESURER AVANT de corriger** — et **une mesure peut conclure « ne rien
  faire »** (c'est le cas ici). Un mur de 64 ms ne dit pas si le fil travaille
  ou attend : **attente INCONNUE ≠ attente nulle** (macOS < 3.13).
- Instrumentation **opt-in**, **coût nul** hors `--perf` (protège les hashes
  d'empilement au bit et la course du banc 76).
- **Pleine résolution = choix assumé** ⇒ réponse **architecturale** (rendu hors
  fil Tk), pas une réduction d'aperçu.
- **float32 ÉCARTÉ DÉFINITIVEMENT (Alain, 21/10/2026)** : −481 Mio possibles,
  mais l'image peut changer — **ne pas le reproposer**.
- **Une COPIE ne se supprime qu'après avoir lu QUI la lit** : mesurer, auditer
  les usages, puis agir (leçon du « ~192 Mio sans risque », faux).
- **Persistance dark/flat (v2.98.7)** : on persiste le **CHEMIN** au geste (jamais
  l'image) et on **restaure HORS du fil d'interface** — un maître peut être sur
  le NAS, et une lecture au démarrage empêcherait l'ouverture (règle v2.98.4).
  Un maître illisible n'est **pas** retiré de la config (perte évitée) : il est DIT.

### Problèmes ouverts
**AUCUN.** Les deux défauts trouvés pendant l'audit sont **CORRIGÉS ET VALIDÉS
EN RÉEL** (persistance dark/flat v2.98.7 ; « basculer sur STF après VeraLux =
image blanche » v2.98.8) et l'audit mémoire est **CLOS SANS FUITE** : le poste
`rendu` de la jauge est un **artefact de parcours** (`FilRendu` garde l'App, que
la jauge re-traverse — **rien à récupérer dans le fil**), le résiduel « ~540 Mio »
est NOMMÉ (dont **193 Mio de fragmentation MESURÉE**), et les 3 corrections de
mesure proposées sont **ABANDONNÉES** (Alain, 21/10).

### Fichiers touchés par l'audit (détail : changelog + `git log`)
- **v2.98.9** : `core/worker.py` (DIX sous-chronos `empilement_*` opt-in) ;
  `bancs/_mesure_empilement.py` (NEUF, mesure + `--autotest`) ;
  `avastack/__init__.py` (version + changelog) ; `.gitignore`.
- **v2.98.0 → v2.98.8** : `perf.py` et `ui/rendu.py` (NEUFS), `ui/app.py`,
  `ui/renderer.py`, `ui/config_ui.py`, `processing/display.py`,
  `processing/calibration.py`, `cameras/multifolder.py` + les bancs
  (`_test_phase0_perf`, `_test_1a_rendu_final`, `_test_render_worker_bit_exact`,
  `_test_multifolder_last_file`, `_test_p1_memoire_reference`,
  `_test_p1_postes_memoire`, `_test_calib_persistance`, `_test_bascule_stf_blanc`,
  `_mesure_memoire_stackers.py`).

---

## Chantier — AUDIT PERFORMANCE/MÉMOIRE : **TERMINÉ ET CLOS (Option A)**

**Objectif initial** : fil Tk de **61 % → < 20 %** du temps mural, **sans changer
un pixel**. **ATTEINT : 3,3 %**. Les étapes suivantes (mémoire, `empilement`) ont
été menées jusqu'à leur terme de MESURE ; l'audit se **clôt par la décision
Option A** (rien de plus à optimiser).

| jalon | état | preuve |
|---|---|---|
| 1a — un seul rendu par frame | **LIVRÉE** (v2.98.1) | `perf-4`, banc 40 |
| 1b — rendu hors fil Tk | **LIVRÉE** (v2.98.2) | `perf-5`, banc 41 |
| `tick_avant` ① — MESURER | **LIVRÉE** (v2.98.3) | `perf-6` (96,9 % d'attente) |
| `tick_avant` ② — AGIR | **VALIDÉE EN RÉEL** (v2.98.4) | 77 % → **3,3 %** |
| mémoire — MESURER | **LIVRÉE** (outil, 0 pixel changé) | chaîne de rendu 376,8 Mio retrouvée |
| copie → référence | **LIVRÉE** (v2.98.5) | rendu SHA-256 égal, −96,2 Mio |
| jauge `postes` | **LIVRÉE** (v2.98.6) | nomme 553,2 Mio (dont `calib` 96,2) |
| persistance dark/flat | **VALIDÉE EN RÉEL** (v2.98.7) | « on retrouve bien les dark » |
| défaut STF/blanc | **VALIDÉ EN RÉEL** (v2.98.8) | image identique AU BIT ; « Testé OK » |
| `empilement` — DÉCOMPOSER | **LIVRÉE : MESURÉE** (v2.98.9) | align 40,9 % · rejet 4,7 % |
| **levier retenu** | **AUCUN — OPTION A** (21/10/2026) | « en direct, 2,7 s ne gênent rien » |

**Critères de sortie — TOUS ATTEINTS** : ① `rendus` ≈ frames ; ② `ui_tick`
**3,3 %** < 20 % ; ③ image finale **au bit** ; ④ 0 gel du Guet (pire tour 92 ms) ;
⑤ **garde-fou VERT**.


---

## En attente / prochaine session

- **UNE SEULE CHOSE À FAIRE : LA RELEASE** (accordée par Alain, 21/10/2026). Le
  code est **GELÉ** : `master` = v2.98.9, fusionné, poussé, **garde-fou vert**.
  **N'ouvrir aucun lot de code avant la release** — et **demander** ensuite.
- **Ce qu'une release demande** (détail : `CLAUDE.md`, sections installateurs et
  conventions de release) : tag `v2.98.9` sur `master`, **notes de version**
  tirées du changelog `avastack/__init__.py` (v2.96.1 → v2.98.9 : Phase 0, 1a,
  1b, `tick_avant`, mémoire, persistance dark/flat, défaut STF, décomposition
  d'`empilement`), et les **installateurs Windows / Linux / macOS** si la release
  les embarque. ⚠️ Le **Store est à v2.71.1** : le mettre à jour est une
  **décision séparée d'Alain** (hors périmètre de cette release par défaut).
- **À NE PAS REPRENDRE sans demande explicite** : les leviers d'optimisation
  (alignement, moyenne, `kappa`/`winsorized` — cf. « Décision »), les 3
  corrections de mesure de la jauge (abandonnées), `cv2.setNumThreads`,
  `sys.setswitchinterval`, priorité OS du fil Tk, et **float32 (écarté
  définitivement)**.
- **Banc 79 (`_test_perf_reactivite_jalon79.py`)** : 4 échecs **PRÉEXISTANTS**
  (l'étape 1b a déplacé l'instrumentation du banc : `_maj_histogrammes` →
  `_draw_hist`). **Ce n'est pas une régression.**
- **`CLAUDE.md`** : une entrée est **PROPOSÉE** (le fichier ne s'écrit jamais sans
  accord — c'est sa règle de maintenance) : les **sous-chronos `empilement`
  (v2.98.9)** et le piège « un relevé `perf` se lit en TOTAUX, pas en moyennes par
  poste ». Le reste est à jour (leçon v2.98.3, « AUCUNE I/O SUR LE FIL
  D'INTERFACE », persistance des maîtres, « la mémoire du STF se périme »,
  ENVELOPPE MÉMOIRE).

### Contexte de reprise (à coller — 2 phrases)
**`master` = v2.98.9** (`OptimisationUI` fusionnée le 21/10/2026, poussée,
garde-fou vert, **audit performance/mémoire CLOS par la décision Option A : on
n'optimise rien de plus**) — tout travail futur se fait sur `master`. Action
unique de la prochaine session : **faire la RELEASE de v2.98.9 depuis `master`**
(tag + notes depuis le changelog `avastack/__init__.py` ; le Store à v2.71.1 est
hors périmètre par défaut) — **aucun code à écrire avant**.

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

- **Aucune I/O sur le fil d'interface** (leçon v2.98.4, ÉTENDUE au démarrage en
  v2.98.7) : un `getmtime()` SMB à chaque tour coûtait **178 ms/tour**. Signature
  qui ne trompe pas : `part_attente` ≈ 1 avec `cores_moyens` < 1 ⇒ **I/O ou
  verrou**, jamais un manque de cœurs.
- **Un banc qui charge un dark/flat ÉCRIT la config** (v2.98.7) :
  `_load_dark`/`_load_flat`/`_clear_calib` persistent désormais les chemins — un
  banc qui les appelle DOIT intercepter `ui.CONFIG` **et** `ui.sauver_config`
  (motif de `_test_calib_compo_jalon53`), sinon il écrit le vrai `config.json`
  avec un chemin de test.
- **Le calcul de rendu ne vit QUE dans le fil de rendu** : `disp.process()` appelé
  depuis un gestionnaire Tk fabrique un SECOND écrivain (EMA du STF, caches) —
  passer par `_refresh_preview()` / `_rendre_et_afficher()` ; exception :
  `display.rendu_pleine_resolution()` (thread de sauvegarde). Et **ne jamais
  attendre dans `_tick`** (`attendre_rendu()` = bancs seulement ; un banc qui lit
  juste après avoir demandé passe `app.rendu.immediat = True`).
- **`vl_actif`** : seule lecture juste = `disp.chaine_sollicitee()` (jamais un OR
  des cases, jamais `vl_neutre_gains` qui est un RÉSULTAT).
- **Un rendu sans nouvelle frame n'est pas vu par `_tick`** : tout point qui
  pousse une image RECALCULÉE doit appeler `disp.notify_new_stack()` (leçon P7).
- **La mémoire du STF se PÉRIME** (v2.98.8) : `_stats` ne décrit que l'image
  COURANTE. Elle **ne traverse pas** une période VeraLux et **avance** au rendu du
  `vl_new` d'une nouvelle pile (`_refresh_preview(live=True)`) — sinon le STF auto
  reste GELÉ et devient **blanc** dès que le NIVEAU de l'empilement change
  (mesuré : médiane 255, 100 % ≥ 250). Détail : `CLAUDE.md`.
- **`perf.json`** : écrit à côté du programme (`--perf`, toutes les 5 s) ;
  `--perf-json CHEMIN` sert à **garder ET relire** un relevé (hors dépôt), qui
  doit être POSTÉRIEUR au lot mesuré (l'outil compare la version).
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

- **21/10/2026 (soir)** : v2.98.5 → v2.98.7 livrées, validées en réel et poussées
  (`e307ad4`) — copie → référence (−96,2 Mio), jauge `postes`, persistance
  dark/flat. Détail : changelog (v2.98.5/6/7) et `git log`.
- **21/10/2026** : 1b validée en réel (v2.98.2) — `ui_rendu` 102 s → 2,2 s, calcul
  dans `fil_rendu`.

