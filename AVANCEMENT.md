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

Versions : **`OptimisationUI` = v2.98.4** (Phase 0 + **1a** + **1b** + **`tick_avant`**
LIVRÉS ET **VALIDÉS EN RÉEL** — `perf-7` : `ui_tick` **3,3 %** du mur ; **aucune
release**) · `master` = v2.96.1 · **Store publié = v2.71.1**.

**Gouvernance** : aucune release GitHub sans accord ; **demander AVANT de
démarrer le lot suivant** ; ne jamais déduire l'état d'une case de `config.json`
— on MESURE le fichier produit.

---

## Session des 20-21/10/2026 — Phase 0, **1a** et **1b** LIVRÉES ET VALIDÉES EN RÉEL · `tick_avant` ① MESURÉ

### État actuel
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
- **Prochain sujet, dans l'ordre** : ① **mémoire** (stackers 2 935 Mo = 61 % du
  RSS, float64 + fenêtre de 8 frames × 5 canaux) ; ② **`empilement`**
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

Repères `perf-7` (556 s, 47 frames) : `fil_rendu` 103,4 s (1 360 ms/rendu),
`empilement` **2 751 ms**, `lecture_frame` **6 697 ms**, stackers **2 935,7 Mo**,
RSS 3 163 Mo (pic 4 563), `cores_moyens` **1,12**, `rendus` 76, `vl_new` 76.
Détail complet : `perf-*.json` (hors dépôt) et changelog `avastack/__init__.py`.

**Lecture** : 1a et 1b ont tenu leurs promesses (`ui_rendu` 276 → 1,2 s), mais
`tick_avant` restait à 77 % du mur **sans travail mesuré dedans** — c'était de
l'**attente**, et la mesure ① puis la pile du Guet l'ont attribuée à une I/O
réseau (`getmtime`) faite à chaque tour. Corrigé en v2.98.4 : **3,3 %**.

### Décisions
- Instrumentation **opt-in** et **coût nul** hors `--perf` (protège la course du
  banc 76 et les hashes d'empilement au bit).
- **Pleine résolution = choix assumé** ⇒ réponse **architecturale** (rendu hors
  fil Tk), **pas** une réduction d'aperçu.
- **1a** : un seul rendu par frame ; c'est l'IMAGE FINALE qui s'affiche quand la
  chaîne est active. **Aucune image d'attente** à l'écran si une image est déjà
  affichée (`rendus_gardes`).
- **1b** : ① **un seul job** en attente (« le dernier gagne », aucune
  backpressure) ; ② **un seul écrivain** de `disp` (tout le rendu passe par le
  fil, `tick_traitee` compris) ; ③ **génération de session** : un résultat
  d'avant un reset est JETÉ (aucun gel au reset) ; ④ mode **`immediat`** pour
  les bancs ; ⑤ histogrammes **calculés dans le fil** (fonction PURE) et
  seulement TRACÉS dans le fil Tk.
- Ordre arrêté : 1a → 1b → **`tick_avant`** → mémoire → empilement.
- **`tick_avant` ① : MESURER AVANT de corriger.** Un mur de 64 ms ne dit pas si
  le fil travaille ou attend ; les deux hypothèses mènent à des correctifs
  opposés (dégraisser `_tick` contre borner OpenCV). `part_attente` tranche.
- **Attente INCONNUE ≠ attente nulle** : sur une plateforme sans
  `time.thread_time()` (macOS < 3.13) `duree_attente()` ne pose RIEN et
  `contexte.cpu_fil` vaut `false` — jamais un zéro trompeur.
- Coût **nul** hors `--perf` conservé : `t0_cpu()` rend None sans appeler
  d'horloge, `duree_attente()` sort au premier test.

### Problèmes ouverts
- **Phase 1 : critère ATTEINT** (`ui_tick` **3,3 %** < 20 %) — reste la décision
  d'Alain : clore la phase (merge/release ?) ou enchaîner sur la mémoire.
- **RÉSOLU (v2.98.4)** : l'attente de `tick_avant` (439,6 s) était une **I/O
  réseau** — `MultiFolderCamera.last_file` faisait `exists` + `getmtime` sur les
  5 dossiers à CHAQUE tour ; calcul déplacé dans `read()`, `ui_tick`
  456,5 → **18,6 s**.
- **MÉMOIRE (prochain sujet)** : stackers **2 935,7 Mo** = 61 % du RSS (pic
  4 563 Mo), `stackers_nb_tableaux` **49** ; 5 canaux en **float64** + fenêtre de
  8 frames. À **MESURER** avant toute conversion (cf. « Handoff »).
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
| **mémoire — MESURER** | **PROCHAINE ACTION** | stackers 2 935,7 Mo = 61 % du RSS |
| `empilement` | après | 2 751 ms/frame |

**Critères de sortie** : ① `rendus` ≈ frames (**atteint : 1,12×**) ;
② `ui_tick` < 20 % du mur (**61 %**) ; ③ image finale au bit (**atteint**) ;
④ 0 gel du Guet (**atteint** — pire tour 1,24 s) ; ⑤ garde-fou vert (**atteint**).


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
- **ACTION UNIQUE SUIVANTE (accord d'Alain AVANT de coder) : MESURER la
  mémoire.** Point de départ mesuré : `stackers_mo` **2 935,7 Mo** (61 % du RSS),
  `stackers_nb_tableaux` **49**, `stackers_octets` **3,08 Go**, RSS 3 163 Mo
  (pic 4 563). Piste : 5 canaux × accumulateurs **float64** + **fenêtre de
  8 frames** (leçon du handoff du 20/10).
  **Protocole (mesure seule, aucun changement d'image)** :
  ① partir de `bancs/_mesure_memoire.py` (existe depuis le 20/10) et des jauges
  `stackers_*` / de `perf.taille_tableaux()` ;
  ② inventorier **où** sont les octets : `processing/stacking.py` (accumulateurs
  du `LiveStacker`), `core/worker.py` (un stacker par canal), fenêtre de frames,
  buffers de rendu (`ui/rendu.py` : image uint8 + brut + bacs) et copies du
  composite ;
  ③ produire un tableau **dtype + forme + octets** par poste, et le total
  réconcilié avec le RSS (écart expliqué, sinon c'est une **fuite** — autre
  sujet) ;
  ④ **seulement ensuite** décider : float32 (−50 % sur les accumulateurs) avec
  **somme compensée** (Kahan/Neumaier) et **preuve sur les bancs d'empilement**
  (hashes au bit ou écart borné et expliqué). Une conversion non prouvée est un
  changement d'image, pas une optimisation.
- **Ensuite** : **`empilement`** (2 751 ms/frame) — décomposer alignement vs
  rejet kappa-sigma AVANT de toucher ; et **`lecture_frame`** (6 697 ms/frame,
  scan réseau 326 ms/dossier/passe) — sujet séparé, latence d'acquisition.
- **ÉCARTÉ, à ne pas réintroduire sans mesure** : `cv2.setNumThreads`,
  `sys.setswitchinterval`, priorité OS du fil Tk — le CPU n'était pas le
  problème (0,98 cœur utilisé sur 14).
- **`CLAUDE.md`** : à jour — leçon v2.98.3 (mesurer le CPU du fil), correction de
  l'affirmation fausse « le levier est `cv2.setNumThreads` », et la règle
  « AUCUNE I/O SUR LE FIL D'INTERFACE » avec son correctif et son banc.
- Aucune release ; `master` reste à v2.96.1 ; le Store à v2.71.1.

### Contexte de reprise (à coller — 2 phrases)
Branche **`OptimisationUI`, v2.98.4** : Phase 0 + 1a + 1b + `tick_avant`
**livrés et validés en réel** — `perf-7` prouve `ui_tick` **456,5 s → 18,6 s**
(3,3 % du mur), **1,23 ms/tour**, max **74 ms**, après suppression de l'I/O
réseau (`os.path.getmtime`) que le fil Tk faisait à chaque tour. Prochaine action
**unique** (accord d'abord) : **mesurer la mémoire** (stackers 2 935,7 Mo = 61 %
du RSS) — répartition exacte d'abord, conversion float32 avec preuve au bit
seulement ensuite.

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

- **Le fil Tk ATTEND, il ne travaille pas — et on sait POURQUOI (21/10)** :
  `perf-6` donne `tick_avant` = **439,6 s d'attente pour 14,3 s de CPU**
  (`part_attente` 0,969) avec `cores_moyens` **0,98**. La cause, nommée par la
  pile du Guet de gel, est un **`os.path.getmtime()` sur partage SMB** appelé à
  chaque tour (`multifolder.last_file`) : **178 ms/tour** mesurés.
  **Règle** : aucune I/O sur le fil d'interface ; `part_attente` ≈ 1 avec
  `cores_moyens` < 1 = **I/O ou verrou**, jamais un manque de cœurs (OpenCV a
  bien 14 fils natifs, mais ce n'était pas la cause).
- **1b — `disp.process()` NE SE LANCE QUE DANS LE FIL DE RENDU** : c'est lui qui
  met à jour les stats EMA du STF (`_stats`), le cache de chaîne et
  `dernier_brut_niveaux`. Un `self.disp.process(...)` ajouté dans un
  gestionnaire Tk (« juste un aperçu ») crée un SECOND écrivain ⇒ images
  différentes d'un run à l'autre. Passer par `_refresh_preview()` /
  `_rendre_et_afficher()` (une DEMANDE). Seule exception :
  `display.rendu_pleine_resolution()` (thread de sauvegarde, sans état partagé).
- **1b — ne JAMAIS attendre dans `_tick`** : `_tick_corps` APPLIQUE
  (`_appliquer_rendus_disponibles`) ; `app.attendre_rendu()` est réservé aux
  bancs et aux scripts sans boucle d'interface (il dort, borné).
- **1b — un banc qui lit l'image juste après l'avoir demandée doit passer en
  `app.rendu.immediat = True`** (sinon il compare l'image précédente) ;
  `_test_phase0_perf` vérifie le câblage du CALCUL dans `ui/rendu.py`.
- **1b — « le dernier gagne » est VOULU** : un seul job ; une rafale de réglages
  ne produit qu'un rendu. Si `rendus_ecrases` explose sur un relevé réel, c'est
  que le rendu est plus lent que les événements, pas un défaut.
- **`vl_actif`** : ne JAMAIS le déduire de `disp.vl_*` (`vl_neutre_gains` est un
  RÉSULTAT) ni d'un OR des neuf cases (`var_vl_neutre` est cochée par défaut) :
  la seule lecture juste est `disp.chaine_sollicitee()`.
- **`perf.json`** : écrit **à côté du programme** par `--perf` (toutes les 5 s) ;
  `--perf-json CHEMIN` pour garder un relevé (`perf*.json` hors dépôt).
- **NE PAS réécrire un fichier entier via PowerShell** (`Get-Content -Raw` +
  `Set-Content`) : double encodage constaté (mojibake sur `__init__.py`). Utiliser
  l'éditeur, ou un fichier neuf + `Move-Item -Force`.
- **P5 — un curseur ne rend plus par `set()`** : pour l'effet immédiat,
  `app._forcer_rendu_curseur(s)` ou `app._rendre_curseurs()` AVANT un rendu
  explicite ; un geste se simule par `s._debut_glissement()`/`_fin_glissement()`.
- **Un rendu sans nouvelle frame n'est PAS vu par `_tick`** : `_tick` ne force
  la chaîne que sur changement de `st["frames"]`. Tout point qui pousse une
  image RECALCULÉE doit appeler `disp.notify_new_stack()` (leçon P7).
- **Échecs PRÉEXISTANTS** (environnementaux, pas des régressions) :
  `_test_espace_jalon72` (géométrie d'écran), `_test_reset_empilement_jalon76`
  [4] (course `_stop()`), « ligne Base SPCC rognée » + « menu écrasé » (flaky),
  `_test_lot1_p2_p3` [3] (rejoue `Antlia R` sur le `config.json` RÉEL).
- **Un jeu SANS le défaut ne mesure que l'ABSENCE DE COÛT** : vérifier que le
  défaut est REPRÉSENTÉ avant de conclure.
- **Un seuil ABSOLU de temps est FLAKY** (constaté 21/10 sur le banc Phase 0) :
  « calcul pur ⇒ part d'attente < 0,2 » a échoué à 0,48 sur un poste chargé —
  il mesurait la CHARGE MACHINE, pas le code. Ancrer les assertions sur une
  comparaison INTERNE (cas A vs cas B du même run) ou sur une mesure directe.
- **La mémoire n'est PAS une fuite** : RSS 150 Mo au repos, puis **2 935 Mo de
  stackers** dès qu'on empile 5 canaux — ce sont les accumulateurs LÉGITIMES
  (`float64`) + la fenêtre de frames. Mesurer la répartition AVANT de conclure.
- **Une conversion de dtype CHANGE l'image** : float32 + somme compensée doit
  être **prouvée** sur les bancs d'empilement (hashes au bit, ou écart borné et
  expliqué) — jamais « à peu près », jamais sans l'accord d'Alain.
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`.

---

## Clôtures précédentes

- **21/10/2026** : **1b VALIDÉE EN RÉEL** (v2.98.2) — `ui_rendu` 102 s → 2,2 s,
  calcul dans `fil_rendu` (169 s), UI qui répond ; `tick_avant` reste à instruire.
- **20/10/2026** : **1a VALIDÉE EN RÉEL** (v2.98.1) — `rendus` 132 → 51,
  `ui_tick` 61 % → 48 %.

