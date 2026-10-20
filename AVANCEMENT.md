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

Versions : **`OptimisationUI` = v2.98.3** (Phase 0 + **1a** + **1b** LIVRÉES et
**validées en réel**, **aucune release** ; **`tick_avant` étape ① (MESURER)
livrée**, relevé réel à faire) · `master` = v2.96.1 · **Store publié = v2.71.1**.

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
- **Reste ouvert** : `tick_avant` = **380,5 s (64,0 ms/tour)** — le fil Tk
  **ATTEND** (hypothèse dominante : OpenCV tourne à **14 fils**, jamais
  bornés) ; `ui_tick` reste à **61 %** du mur. **À PROUVER** par `perf-6.json`.
- **`tick_avant` étape ① (MESURER) LIVRÉE — v2.98.3** : `perf.t0_cpu()` +
  `perf.duree_attente(base, mur, cpu)` posent, **à côté du mur**, le CPU du
  **fil appelant** (`time.thread_time()`) et l'**ATTENTE** = mur − CPU, avec un
  bilan `attente` (`part_attente`) dans le JSON et une ligne dans `resume()`.
  Branché sur **`tick_avant`** (`_tick_corps`) et **`ui_tick`** (`_tick`) —
  deux points, **aucun pixel, aucun calcul déplacé**. Banc Phase 0 :
  **110 vérifications** exécutées (section **[2 bis]** : sommeil ⇒ part ≈ 1,
  CPU publié comparé à une mesure DIRECTE, calcul pur ⇒ attente nettement
  moindre — **pas de seuil absolu**, il mesurait la charge machine).
- **Rien n'est encore PROUVÉ** : la famine du fil Tk ne sera établie que par un
  relevé réel **`perf-6.json`**. L'étape ② (borner `cv2.setNumThreads`) ne
  s'engage pas avant.


### Les trois relevés qui commandent la suite (M33, 5 canaux, pleine résolution)

| mesure | `perf-3` (avant 1a) | `perf-4` (1a) | `perf-5` (1b) |
|---|---|---|---|
| `rendus` | 132 (2,75/frame) | 51 (1,06) | **84 pour 75 frames (1,12)** |
| `ui_rendu` (fil Tk) | 276 s | 102 s | **2,2 s** |
| `fil_rendu` (hors Tk) | — | — | **169,4 s (84 × 2 017 ms)** |
| `fil_etirement` | — | — | 163,9 s (1 951 ms, 7,41 Mpx) |
| `tick_conso` | 151,6 s | 0,67 s | 3,2 s |
| `tick_avant` | 202,5 s (26,7 ms) | 200,2 s (24,5 ms) | **380,5 s (64,0 ms)** |
| `ui_tick` | 482,8 s = **61 %** | 307 s = **48 %** | **388,7 s = 61 %** |
| `ui_tick_libre` / `occupe` | — | 25 / 108 ms | **61,6 / 70,9 ms** |
| `cores_moyens` / `cpu_s` | 1,59 | 1,28 | **1,99 / 1 270 s** |
| `empilement` | 4 356 ms | — | 4 503 ms |
| `stackers_mo` / RSS (pic) | 2 935 / 4 503 | 2 936 / 3 161 | 2 935 / 4 804 (5 057) |

Compteurs `perf-5` : `rendus_demandes` 84, **`rendus_ecrases` 0**,
**`rendus_perimes` 0**, `rendus_gardes` 22, `rendus_differe` 75/75, `vl_new` 82,
`file_q` 0. Jauges : `vl_actif` true, moteur **VeraLux**, `vl_etapes` « CH »,
`source_px` 7,41 Mpx. Pire tour `ui_tick` : **1 239 ms**.

**Lecture** : 1b a fait ce qu'il devait (`ui_rendu` 102 s → 2,2 s, calcul
déplacé dans `fil_rendu`), mais le temps mural du fil Tk n'a pas baissé :
`tick_avant` a DOUBLÉ sans travail mesuré dedans (FITS 38 ms, mesures 3,1 s,
réglages 2,8 s) — **c'est de l'attente**, pas du travail Tk.

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
- **`tick_avant` = 380,5 s (64,0 ms/tour)** : 98 % de `ui_tick`. Le travail
  mesuré y est négligeable ⇒ **ATTENTE** (à PROUVER par `perf-6.json` :
  `attente.tick_avant.part_attente`). `ui_tick_libre` = 61,6 ms/tour alors
  qu'aucun empilement ne tourne (mais le fil de rendu, si). **OpenCV est
  configuré à 14 fils** (`cv2.getNumThreads()` = 14 ; 14 cœurs logiques) et
  l'application ne le borne **jamais** : ces fils sont NATIFS, invisibles pour
  `threading.active_count()` (jauge `threads` = 5) et pour les chronos — mais
  `cpu_s` = **1 270 s** pour ~550 s de travail mesuré (**~700 s de CPU
  fantômes**). ⇒ Le fil Tk n'obtient plus de cœur pendant le rendu.
- **Critère de sortie de la Phase 1 NON atteint** : `ui_tick` < 20 % du mur
  (aujourd'hui 61 %).
- **Réactivité sous chaîne lente** (1a) : l'écran suit les `vl_new` ; à
  surveiller en réel. 1b ajoute : une rafale de réglages ne produit qu'UN rendu
  (le dernier) — voulu.
- **Mémoire** (`stackers_mo` 2 935 Mo = 61 % du RSS) et **`empilement`**
  (4 503 ms/frame) : APRÈS `tick_avant`.
- Pire tour `ui_tick` = 1 239 ms (sous le seuil du Guet de 1,5 s, mais c'est un
  à-coup encore visible).

### Fichiers de l'étape ① `tick_avant` (v2.98.3)
- `avastack/perf.py` : `t0_cpu()` (CPU du fil, `time.thread_time()`),
  `duree_attente(base, mur, cpu)` → `<base>_cpu` + `<base>_attente`,
  `cpu_fil_disponible()` ; bilan `attente` dans `instantane()`, ligne dans
  `resume()`, `contexte.cpu_fil` dans le JSON.
- `avastack/ui/app.py` : `_tick` (`ui_tick`) et `_tick_corps` (`tick_avant`) —
  deux points de mesure, rien d'autre.
- `bancs/_test_phase0_perf.py` : section **[2 bis]** (8 vérifications neuves,
  témoin calcul pur) + `t0_cpu` inactif + 2 contrôles JSON — **110** au total.
- `avastack/__init__.py` : v2.98.3 + changelog.

### Fichiers de l'étape 1b (v2.98.2)
- `avastack/ui/rendu.py` : **NEUF** (typé) — `FilRendu`, `Job`/`Resultat`,
  génération, mode `immediat`, compteurs, chronos `fil_*`.
- `avastack/ui/renderer.py` : `_rendre_et_afficher()` = DEMANDE ;
  `_appliquer_rendu()`, `_appliquer_rendus_disponibles()`, `attendre_rendu()` ;
  `_vider_ecran()` purge.
- `avastack/ui/app.py` : `self.rendu = FilRendu(self)` ; application dans
  `_tick_corps` ; `tick_traitee` par le fil ; purge au reset ; arrêt du fil à
  la fermeture.
- `avastack/ui/widgets/histogram.py` : `_histogrammes_purs()` (PURE).
- `bancs/_test_render_worker_bit_exact.py` : **NEUF** (41).
- Bancs passés en **rendu immédiat** : `_test_1a_rendu_final`,
  `_test_couleurs_immediat_jalon39`, `_test_histo_jalon75`,
  `_test_reset_empilement_jalon76`, `_test_p5_rendu_relachement`,
  `_test_perf_reactivite_jalon79`, `_mesure_p5_reactivite`, `_mesure_memoire`.
- `_test_phase0_perf` : vérifie le câblage du CALCUL dans `ui/rendu.py` ;
  garde-fou : `ui/rendu.py` typé.
- `avastack/__init__.py` : v2.98.2 + changelog ; `CLAUDE.md` : section 1b.
- Détail complet (Phase 0, 1a, 1b) : changelog `avastack/__init__.py`.

---

## Chantier en cours — PHASE 1 : **rendu hors fil Tk** (1a + 1b LIVRÉES, `tick_avant` ① mesuré)

**Objectif** : fil Tk de **61 % → ~10-15 %** du temps mural, **sans changer un
pixel** (même `DisplayProcessor.process`, même ordre).
**Contraintes** : mono-processus, Tkinter, multiplateforme, **pixels identiques
au bit** (bancs), pas d'aperçu réduit, pas de calcul pendant un geste (P5 livré).

| jalon | état | preuve |
|---|---|---|
| 1a — un seul rendu par frame | **LIVRÉE** (v2.98.1) | `perf-4`, banc 40 |
| 1b — rendu hors fil Tk | **LIVRÉE** (v2.98.2) | `perf-5`, banc 41 |
| **`tick_avant` ① — MESURER** | **LIVRÉE** (v2.98.3) | `t0_cpu`/`duree_attente`, banc 75 |
| **`tick_avant` ② — AGIR** | en attente du relevé | `perf-6.json` (`part_attente`) |
| mémoire | après | `stackers_mo` 2 935 Mo |
| `empilement` | après | 4 503 ms/frame |

**Critères de sortie** : ① `rendus` ≈ frames (**atteint : 1,12×**) ;
② `ui_tick` < 20 % du mur (**61 %**) ; ③ image finale au bit (**atteint**) ;
④ 0 gel du Guet (**atteint** — pire tour 1,24 s) ; ⑤ garde-fou vert (**atteint**).


---

## En attente / prochaine session

- **`tick_avant` — étape ① LIVRÉE (v2.98.3)** : la mesure du CPU du fil Tk est
  branchée (`t0_cpu` + `duree_attente` sur `tick_avant` et `ui_tick`).
  **Il ne reste qu'à RELEVER** : session réelle VeraLux + chroma, même jeu M33,
  puis

  `python AVAStack.py --perf`

  (le fichier s'écrit **à côté du programme** — le chemin est imprimé au
  démarrage — et se lit PENDANT la session, réécrit toutes les 5 s ; pour garder
  un relevé, copier/renommer `perf.json` en `perf-6.json` APRÈS la fermeture :
  `perf*.json` est dans `.gitignore`).

  et lire **`attente.tick_avant.part_attente`** (et `attente.ui_tick`).
- **Si `part_attente` ≈ 1** ⇒ famine **PROUVÉE** : passer à l'étape ②, dans cet
  ordre — (a) **`cv2.setNumThreads(N)`** borné au démarrage (N = 2 ou la moitié
  des cœurs, repli multiplateforme : ne jamais supposer Windows) ; (b)
  `sys.setswitchinterval(0.001)` ; si les deux ne suffisent pas : borne de
  concurrence (ne pas relancer un rendu pendant un empilement) ou priorité OS du
  fil Tk (à discuter, multiplateforme).
- **Si `part_attente` est FAIBLE** ⇒ le temps est réellement passé dans `_tick` :
  chercher les sous-chronos (`tick_fits`, `tick_mesures`, `tick_reglages`,
  `tick_vues`) AVANT tout correctif — et NE PAS borner OpenCV « au cas où ».
- **Ensuite** : **mémoire** (float32 + somme compensée + stackers paresseux,
  2 935 Mo → ~1,4 Go) puis **décomposition d'`empilement`** (alignement vs rejet).
- **`CLAUDE.md`** : mise à jour de 1b faite (accord d'Alain, 21/10) ; reste à y
  porter la leçon de v2.98.3 (mesurer le CPU du fil, pas seulement le mur) —
  **proposée, pas encore écrite**.
- Aucune release ; `master` reste à v2.96.1 ; le Store à v2.71.1.

### Contexte de reprise (à coller — 2 phrases)
Branche **`OptimisationUI`, v2.98.3** : Phase 0 + **1a** + **1b** livrées et
**validées en réel**, et l'étape **① de `tick_avant` (mesurer l'attente du fil
Tk)** est livrée — `perf.t0_cpu` / `duree_attente` publient `part_attente` pour
`tick_avant` et `ui_tick`, banc Phase 0 à **75 vérifications**. Prochaine action
**unique** : **relever `perf-6.json` en réel** (`--perf --perf-json …`) et lire
`attente.tick_avant.part_attente` — proche de 1 ⇒ famine prouvée, on borne
**OpenCV (14 fils !)** ; faible ⇒ le temps se passe vraiment dans `_tick`
(banc Phase 0 à **110** vérifications).

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

- **Le fil Tk ATTEND, il ne travaille pas** (`perf-5`) : `tick_avant` =
  64 ms/tour pour 3,2 ms de travail mesuré. Ne PAS conclure à un coût de Tk.
  **Depuis v2.98.3 c'est MESURÉ et non plus supposé** : `perf.t0_cpu()` +
  `perf.duree_attente()` posent `<base>_cpu` et `<base>_attente`, et le JSON
  publie `attente[base].part_attente` (proche de 1 = famine). **OpenCV ouvre
  14 fils NATIFS** (`cv2.getNumThreads()`), jamais bornés : invisibles pour
  `threading.active_count()` ET pour les chronos, mais visibles dans `cpu_s`
  (1 270 s pour ~550 s mesurées).
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
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`.

---

## Clôtures précédentes

- **21/10/2026** : **1b VALIDÉE EN RÉEL** (v2.98.2) — `ui_rendu` 102 s → 2,2 s,
  calcul dans `fil_rendu` (169 s), UI qui répond ; `tick_avant` reste à instruire.
- **20/10/2026** : **1a VALIDÉE EN RÉEL** (v2.98.1) — `rendus` 132 → 51,
  `ui_tick` 61 % → 48 %.

