# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## Session du 09/10/2026 (nuit) — JALON 116 LIVRÉ et TESTÉ EN RÉEL (v2.68.0 — commité, PAS de release)

### État actuel
- `AVASTACK_VERSION = "2.68.0"` — jalon **116 LIVRÉ, TESTÉ EN RÉEL, COMMITÉ et
  POUSSÉ** (pas de release : décision d'Alain) : ① l'ORB normalise la frame sur
  SES PROPRES bornes, ② un DERNIER RECOURS ORB étoffé (8 000 points) est essayé
  sur la frame puis sur la frame retournée avant tout refus.
- **TEST RÉEL d'Alain (09/10/2026)** : **OK** — les frames des DEUX nuits
  (retournement 176°) s'empilent désormais. « Save as seen » conservée :
  `C:\Astro\test\Andromeda Nebula2.68.0.png` (41,7 Mo).
- **Rejeu hors-ligne des VRAIES frames, avec le code réel** (60 frames, 15 tours) :
  ① + ② → **0 refus** (61 empilées, dont **26 sauvées par le ②**), contre
  **26 refus** avec ① seul. Bancs rejoués VERTS + garde-fou VERT.
- Restent **DEUX DÉFAUTS MINEURS** notés par Alain après ce test (recadrage du
  rectangle commun / halo-écho rouge) → voir « Défauts mineurs », à traiter dans
  une **AUTRE session**.

### Défauts MINEURS vus au test réel (À TRAITER PLUS TARD — notés par Alain)
1. **Coins d'image différents entre deux orientations** : les frames retournées
   de 176° ne couvrent pas le même rectangle que les autres, donc les bords/coins
   diffèrent et **le retrait de gradient n'est pas possible dans cet état**.
   Alain demande un **recadrage sur le RECTANGLE COMMUN**. ⚠ Le recadrage
   d'intersection EXISTE déjà (`bancs/_test_crop_intersection.py`) mais il rend
   `None` sur un cadre dégénéré (cf. piège « Recadrage d'intersection ») : **à
   MESURER d'abord** (pourquoi il ne s'applique pas ici — angle ? cadre dégénéré ?)
   AVANT de coder quoi que ce soit.
2. **Halo / écho décalé ROUGE sur beaucoup d'étoiles** : RIEN de conclu — c'est
   une **piste à instruire** (alignement résiduel d'une partie des frames ?
   décalage du canal rouge ? règle de couleur de la composition LRGB ?). Le
   « save as seen » de la session est conservé en PNG pour pouvoir mesurer.

### Fichiers modifiés dans cette phase
- `avastack/processing/alignment.py` : ① `_compute_direct` (et `_orb_renforce`)
  normalisent la frame sur ses propres percentiles ; le repli « phase » garde le
  domaine PARTAGÉ, recalculé dans `_sans_orb` (donc gratuit sur le chemin
  rapide) ; ② nouveaux `_reference_forte` (descripteurs de référence étoffés,
  calculés à la demande puis EN CACHE — invalidés par `set_reference` ET
  `reset`) et `_orb_renforce` (mêmes garde-fous que le chemin ORB) ;
  `_composer_retournement` extrait de `compute` pour que le ② suive la même voie.
- `avastack/__init__.py` : version **2.68.0** + changelog du jalon 116.
- `bancs/_test_align_lumiere_jalon116.py` : banc NEUF, 5 sections, TOUT AU VERT.

### Mesures du jour (à réutiliser, ne pas remesurer)
- Code RÉEL sur les vraies frames : ① seul → 35 empilées / 26 refus ;
  ① + ② → 61 empilées / **0 refus** (24 « ORB étoffé » + 2 « ORB étoffé+étoiles »).
- Coût du ② sur ces mêmes frames (brutes 8,4 Mpx) : p95 **1 793 → 2 664 ms**,
  max 1 901 → 3 037 ms (médiane 1 415 → 1 448 ms).
- **DÉCOUVERTE (à garder)** : le repli « phase » en domaine LOCAL (l'essai du
  09/10 sur lequel la preuve était fondée) « alignait » 29 frames sur 60 par une
  matrice QUASI-IDENTIQUE (**0 appariement d'étoiles mutuels**) alors que leur
  vraie géométrie est à **−176,2°** (6, 92 et 80 appariements mesurés sur G[5],
  G[20], G[35], Δ≈(3775, 2297) px). Ces FAUX alignements sont la cause directe
  des **doublons rouges** et de la **trace sombre** du test réel : le domaine
  PARTAGÉ (décision d'Alain) les refuse, et le ② les aligne VRAIMENT.

### Décisions prises
- ① + ② conformes à la décision d'Alain du 09/10 au soir ; le domaine PARTAGÉ du
  repli phase est CONSERVÉ — c'est la mesure ci-dessus qui le justifie (il évite
  29 faux alignements sur 60 frames).
- Le ② est un DERNIER RECOURS : il ne remplace pas l'ORB principal (1 000 points)
  et n'est tenté que quand TOUTE la cascade a échoué.
- Il s'applique AUSSI en mode narrowband (`triangles_seuls`) : il ne peut qu'y
  SAUVER des frames que tout le reste refusait, avec les mêmes garde-fous.

### Problèmes ouverts
- L'alternative « paires d'invariants top-60 × top-120 » (cf.
  `catalogues/solveur.py::_ransac_paires`) n'est PAS mesurée : le ② fonctionne
  (0 refus) et coûte ~0,9 s de p95 sur les frames concernées — à rouvrir
  seulement si ça gêne en session réelle.
- L'aligneur n'écrit toujours RIEN au journal (`%APPDATA%\AVAStack\journal.txt`) :
  un futur diagnostic dépend encore des archives de frames.

### Prochaines étapes
- **Prochaine session** : les DEUX DÉFAUTS MINEURS ci-dessus — **mesurer d'abord**
  (le n° 1, « rectangle commun », débloque à lui seul le retrait de gradient).
- **Paquets + release GitHub v2.68.0** NON faits (choix d'Alain : commit/push
  seulement). Dernier tag publié = **v2.62.1** ; Microsoft Store toujours en
  **v2.50.0** (cadence séparée, certification à part).
- L'aligneur n'écrit toujours RIEN au journal : un futur diagnostic dépend des
  archives de frames (`%TEMP%\avastack_frames_*`, purgées après 6 h).

### Points d'attention
- `set_reference` ne passe PAS par `reset()` : tout nouveau cache doit être
  invalidé LÀ AUSSI (piège rencontré avec `ref_des_fort`).
- Les archives de frames (`%TEMP%\avastack_frames_*`) sont supprimées par
  l'appli 6 h après leur dernière écriture — les COPIER si un rejeu doit servir
  plus tard.

---

## Jalon précédent (09/10/2026, soir) — diagnostic des 80 refus
Compteurs du test LRGB reproduits par rejeu : écart **176,2°** (dans la tolérance
180° ± 10°), côté A = 111 frames toutes empilées / côté B = 99 frames → 19
empilées et 80 refusées ; R/G/B mêlent les DEUX côtés du Pier (26 % des frames).
Détail complet : changelog **v2.68.0** (`avastack/__init__.py`) et git.

---

## Chantier en cours — ALIGNEMENT : retournement au méridien + astrométrie

**But** : que les frames d'UN côté du méridien (rotation ~180° par rapport à la
référence) s'empilent au lieu d'être rejetées, et que l'astrométrie fonctionne sur
un empilement LRGB.

**État (09/10/2026, nuit)** : jalons **111→115** livrés, testés en réel et poussés
(v2.67.0) ; **jalon 116 ÉCRIT** (v2.68.0 : ① bornes propres pour l'ORB, ② dernier
recours ORB étoffé) — **rejeu hors-ligne des vraies frames : 0 refus**. Il reste à
le faire **VALIDER PAR LE TEST RÉEL** du jeu M31 deux nuits (bloc de session
ci-dessus). Le détail des jalons vit dans le changelog de `avastack/__init__.py`
et dans l'historique git.

**Règles d'or** :
- Un jalon = un banc neuf + rejeu des bancs concernés (TOUS VERTS) + garde-fou
  `bancs/_test_refactoring_garde_fou.py` VERT (syntaxe, surface 75, hash au bit).
- On ne réécrit JAMAIS un tag publié ; version + changelog + AVANCEMENT.md dans la
  même réponse ; commentaires et docstrings en FRANÇAIS.
- Le chantier de refactoring (jalons 100→110) est CLOS : plus de découpage de
  `app.py` ni de typage rétroactif.

---

## En attente / prochaine session

- **TEST RÉEL du jeu M31 deux nuits** (jalon 116 écrit, 0 refus hors-ligne) — seul
  point du chantier non validé.
- **Publication** : paquets Windows/Linux/macOS + release GitHub **v2.68.0**
  (dernier tag publié = **v2.62.1** ; les v2.63.0→v2.68.0 partent dans le commit de
  clôture).
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
  26 % des frames RGB sont à 176°).
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
- **ALIGNEUR — corrigé en v2.68.0, mais la règle reste (MESURÉ 09/10/2026)** : une
  frame retournée (~176°) ne pouvait passer QUE par `_triangles` (base = top-12 des
  étoiles : **4-5 appariements au lieu de 6** sur des nuits réelles) OU par ORB —
  celui-ci étant **aveugle** car `_norm8` l'étirait avec les bornes de la
  **RÉFÉRENCE** (**93-99 % des pixels écrasés à 0**). Désormais ① l'ORB travaille
  sur les bornes PROPRES de la frame et ② un ORB étoffé (8 000 points) sert de
  dernier recours. ⚠ **Le repli « phase » DOIT garder le domaine PARTAGÉ** : en
  domaine local il « alignait » des frames à 176° par une QUASI-IDENTITÉ (0
  appariement d'étoiles mutuels) — c'est ce qui produisait les doublons rouges.
  Une brute CALIBRÉE (dark) peut aussi être refusée là où la brute non calibrée passe.
- **Recadrage d'intersection** : il ne s'applique PAS si le cadre est dégénéré
  (⇒ biseaux noirs visibles + « coussin clair » et couleurs fausses au retrait de
  gradient). À contrôler AVANT d'accuser l'optique ou le traitement.

---

## Clôtures précédentes

- **09/10/2026 (nuit)** : jalon 116 (v2.68.0) — les deux nuits (176°) s'empilent
  (① bornes propres + ② ORB étoffé), **test réel OK**, commité et poussé ; deux
  défauts mineurs notés (rectangle commun, halo-écho rouge).
- **09/10/2026 (soir)** : diagnostic des 80 refus du test LRGB (176,2°) → les deux
  correctifs du 116 ; jalons 111→115 (v2.67.0, astrométrie réparée) poussés.

