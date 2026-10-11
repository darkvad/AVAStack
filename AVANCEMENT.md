# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## Session du 11/10/2026 — jalon 119 (v2.72.0) : temps de pose & intégration par couche

### État actuel
- Chantier **CODÉ et vérifié en local** : la barre d'état affiche le temps de
  pose unitaire et la durée d'intégration cumulée — mono (« 20×60s = 20min
  (intégration) ») et PAR COUCHE en composition (… « | Total: 17min »).
- Garde-fou `_test_refactoring_garde_fou.py` **VERT** (surface 75, hash au bit,
  pyright 0/49) + banc neuf **VERT** + 22 bancs du domaine rejoués **VERTS**.
- **TESTÉ EN RÉEL PAR ALAIN (OK)** le 11/10/2026, **COMMITÉ ET POUSSÉ** sur
  `master`. **PAS de release** cette session (demande d'Alain) : le code porte la
  version **v2.72.0**, à publier plus tard.

### Fichiers modifiés dans cette phase
- `avastack/images.py` : `load_image(..., avec_expo=True)` (overloads, défaut
  rétro-compatible), `_expo_depuis_entete`, `lire_exptime_fits` (s / ms / µs).
- `avastack/processing/stacking.py` : `LiveStacker.exposure_times`,
  `expo_unitaire`, `expo_min_max`, `integration_totale` ; `add(exposure=…)`.
- `avastack/processing/composition.py` : `add(exposure=…)`, `expo_par_role`,
  `integration_totale`, `etat_expo`.
- `avastack/processing/framestore.py` : `ArchiveFrames.expositions` (le re-stack
  restitue l'intégration, qui sinon repartait de zéro).
- `avastack/cameras/folder.py` + `multifolder.py` : expo lue AVEC l'image.
- `avastack/cameras/base.py` + 7 caméras : `exposure_time_sec` (consigne SDK).
- `avastack/core/worker.py` : `_expo_camera`, `_etat_expo`, clé `st['expo']`.
- `avastack/ui/app.py` : `_fmt_duree` / `_fmt_pose` / `_fmt_pose_plage`,
  `_texte_expo`, ligne `lbl_status`, expo préservée au re-stack.
- `avastack/__init__.py` : version **2.72.0** + changelog.
- `bancs/_test_expo_integration_jalon119.py` : banc neuf (6 sections).

### Décisions prises
- Le temps de pose suit la frame DÈS l'empilement (`add(exposure=…)`) : pas de
  recalcul tardif ; source = en-tête FITS (fichiers) ou consigne (SDK).
- Unités : intégration AUTO (60s→1min, 3600s→1h) ; pose unitaire en SECONDES
  (« 60s »), variable affichée en PLAGE (« 30-60s »).
- Helper nommé `_fmt_pose` et NON `_fmt_expo` : ce dernier est déjà pris par le
  formateur du panneau Caméra, ré-importé dans `app.py` (cf. Pièges).
- L'expo est archivée par frame (`framestore.expositions`) → re-stack juste.

### Prochaines étapes
- **Release GitHub v2.72.0** (SUR DEMANDE d'Alain — NON faite cette session) :
  code validé, commité et poussé. Cadence Store séparée.
- .exe v2.71.1, macOS, Linux vierge : tests encore en attente (cf. ci-dessous).

### Points d'attention
- `load_image` : le défaut reste l'IMAGE SEULE — ne pas rompre les appelants.
- Ne JAMAIS redéfinir `_fmt_expo` au niveau module de `app.py` (déjà importé).

---

## HISTORIQUE — jalon 118 (10/10/2026) : installateur Windows `.exe` réparé (v2.71.1), PUBLIÉ
- `[Files]` d'`avastack.iss` → source RÉCURSIVE (+ `Excludes`) : les sous-paquets
  (`core/`, `ui/widgets/`, `ui/panels/`) n'étaient plus embarqués depuis v2.58.1.
- Banc neuf `_test_installeur_iss_fichiers_jalon118.py` (couverture + ISCC) — VERT.
- Complément doc macOS (Python 3.13.16) : aucun code, doc seule.
- Détail : changelog **v2.71.1**, banc 118. NE PAS REMESURER.

---

## Problèmes ouverts (hérités des jalons 116-118, toujours valides)
- L'**aligneur n'écrit toujours RIEN** au journal (`%APPDATA%\AVAStack\journal.txt`).
- L'alternative « paires d'invariants top-60 × top-120 » du solveur reste non mesurée.

---

## Chantier en cours — CLOS : temps de pose & intégration par couche (jalon 119)

Livré en **v2.72.0** (11/10/2026). Le plan (7 fichiers) a été suivi et complété
par `framestore.py` (archivage du temps de pose → re-stack juste) et
`multifolder.py` (expo en composition). Détail : changelog **v2.72.0** du source
et banc `_test_expo_integration_jalon119.py`. **NE PAS REMESURER.**

**Règles d'or** (rappel) :
- Un jalon = un banc neuf + rejeu des bancs concernés (TOUS VERTS) + garde-fou
  `_test_refactoring_garde_fou.py` VERT (syntaxe, surface 75, hash au bit).
- On ne réécrit JAMAIS un tag publié ; version + changelog + AVANCEMENT.md dans
  la même réponse ; commentaires et docstrings en FRANÇAIS.

---

## En attente / prochaine session

- **Jalon 119 (v2.72.0) TERMINÉ** : testé en réel par Alain (OK), commité et
  poussé ; **release NON faite** (demande d'Alain). Dernier tag publié = v2.71.1.
- **Release GitHub v2.71.1 PUBLIÉE** (4 paquets + `INSTALLATION.md`).
- **À VÉRIFIER EN RÉEL** : l'installateur `.exe` corrigé (l'application démarre
  après installation) — c'est LE test qui manquait et qui a révélé le défaut.
- **Microsoft Store** : cadence SÉPARÉE — l'application PUBLIÉE y reste la
  **v2.50.0** ; le **MSIX v2.71.1 est CONSTRUIT ET SIGNÉ** (prêt à resoumettre).
  Prochaine action (Alain, manuelle) : soumettre ce MSIX dans Partner Center
  (cf. `SOUMISSION.md` §1 et §7).
- **Test « installer depuis le Microsoft Store »** (seul test qui n'existe que par
  cette voie ; l'appli v2.50.0 y est publiée).
- **Paquet macOS** : test réel par le testeur — « 📂 Dossier » et « Charger un
  flat… » doivent répondre au PREMIER clic (sinon : son `journal.txt`).
- **Linux** : restent la machine VIERGE (sans Python) et le test matériel caméras
  (`--cameras`).
- **Boutons de données SANS Siril** (« ⬇ Gaia », « ⬇ Spectres (champ) », « ⬇ Base
  SPCC ») — délégués à un utilisateur sans Siril.
- **Piste INDI** (client INDI : un seul chemin pour les 3 OS et toutes les marques)
  — jalon à part, PAS avant le portage Linux avec les `.so`.

---

## Setup d'Alain

- **Setup 1 (miniPC)** : QHY MiniCam8M (mono refroidie, roue intégrée,
  alim. 12 V requise) ; N.I.N.A. → dossiers
  `TargetSchedulerSequence/<cible>/<expo>/LIGHT` — un dossier peut
  MÉLANGER plusieurs nuits (la 1re frame par mtime n'est pas forcément de
  la nuit courante).
- **Setup 2** : C8 défourché + réducteur 0,63 → 1280 mm ; Player One
  Uranus-C Pro (couleur, IMX585, 3856×2180, RGGB, gain unitaire 210,
  TEC) sur monture DIY **Open Astro Mount** ; guidage SVBONY SV305C sur
  lunette 60/240. Constat 17/09/2026 à 1280 mm : étoiles « en plusieurs
  points puis en trainées » → origine du jalon 13 (alignement robuste).
  Banc POA : `_diag_camera_playerone.py` (jalon 28).
- **Jeu du test LRGB (09/10/2026)** : QHY MiniCam8M (mono) + lunette **SV555** ;
  M31 = **L du 13/09** + **R/G/B du 22-23/09**, ~50-60 frames par filtre, 60 s,
  -15 °C. ⚠ **Un dossier de filtre peut MÊLER les DEUX côtés du Pier** (mesuré :
  26 % des frames RGB sont à 176°). PNG « save as seen » du test **v2.69.1** :
  `C:\Astro\test\Andromeda Nebula2.69.1.png` (hors dépôt — dépôt PUBLIC).
- **Outils astro locaux vérifiés (22/09/2026)** : Siril 1.4.4
  (catalogues : chunks Gaia XP dans `%LOCALAPPDATA%\Siril\...`,
  base SPCC capteurs/filtres dans `siril-spcc-database`) ; ASTAP
  (`C:\Program Files\astap`, astap_cli.exe + base D80 Gaia DR3 1,24 Go)
  ; PAS d'astrometry.net/ANSVR.
- **Machine LINUX d'Alain (fait du 29/09/2026, à sa demande)** : **Ubuntu 26.04
  LTS** — l'installateur Linux y a été exécuté PLUSIEURS fois (installation,
  prérequis, venv, dépendances, lancement) ; l'astrométrie, la SPCC et GraXpert
  y sont validés. Restent : machine **VIERGE** (sans Python) et **test matériel
  caméras** sous Linux (`--cameras`).

---

## Pièges récents (encore actifs)

- **`_fmt_expo` est DÉJÀ PRIS dans `app.py`** (jalon 119) : ce nom est importé de
  `ui/panels/camera.py` (format de la SAISIE d'exposition, µs/ms/s). Un `def
  _fmt_expo(...)` au niveau module de `app.py` l'ÉCRASE et casse l'affichage du
  panneau Caméra — le banc `cameras/_test_expo_affichage_jalon34.py` le détecte.
  D'où le nom `_fmt_pose` pour le temps de pose (jalon 119).
- **PIÈGE LANCEMENT** : `python3` ≠ venv — toujours `python AVAStack.py`.
- **Ordre de la chaîne** (Alain, 16/09/2026) : recadrage → gradient →
  débruitage → netteté → étirement. Débruitage : code gelé, cases décochées
  (décision du 16/09/2026) — ne pas retoucher sans nouvelle demande.
- **Tk** : ne JAMAIS mélanger `grid` et `pack` dans le même conteneur
  (`TclError` « grid is already managing its content windows »).
- **OpenCV/OpenCL** : crash au teardown → `cv2.ocl.setUseOpenCL(False)`. Tests
  `ui.App` hermétiques : `ui.CONFIG = {}` + `sauver_config` intercepté.
- **SDK natif caméras** : chargement UNE fois par process ; crash natif non
  rattrapable → tracer chaque étape dans un fichier ; vérifier l'identité des
  fichiers réellement chargés AVANT d'interpréter un plantage.
- **Installateur d'un OS qu'on ne peut pas exécuter** (macOS/Linux) : se vérifie
  par ce qui EST vérifiable (`bash -n`, refus hors OS, banc de contenu du paquet) ;
  l'état est écrit DATÉ, jamais déguisé en test réussi.
- **ALIGNEUR (jalons 116 + 117 corrigés)** : les détails mesurés vivent dans
  CLAUDE.md (« Pièges », entrées des jalons 116 et 117). À retenir ici : une
  frame d'une AUTRE NUIT/filtre se normalise sur ses PROPRES bornes (sauf le
  repli « phase », qui garde le domaine PARTAGÉ) ; le raffinement sous-pixel
  démarre désormais à 4 px puis resserre (117b) et n'est retenu que s'il VÉRIFIE
  mieux la matrice sur les étoiles. Une brute CALIBRÉE (dark) peut aussi être
  refusée là où la brute non calibrée passe.
- **Recadrage** : `cadre_intersection` rend le plus grand rectangle AXIAL INSCRIT
  (117a) — si des coins/biseaux apparaissent encore, contrôler le polygone
  d'intersection AVANT d'accuser l'optique ou le traitement.

---

## Clôtures précédentes

- **10/10/2026** : jalon 118 (v2.71.1) — installateur Windows `.exe` réparé
  (copie RÉCURSIVE du package ; sous-paquets manquants depuis v2.58.1) ; banc
  garde-fou de contenu ; **PUBLIÉ** (release GitHub v2.71.1).
- **11/10/2026** : jalon 119 (v2.72.0) — temps de pose & intégration par couche
  dans la barre d'état (mono + par couche) ; **test réel OK**, commité/poussé ;
  **PAS de release** (demande d'Alain).

