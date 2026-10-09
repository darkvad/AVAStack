# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## Session du 09/10/2026 (soir) — TEST RÉEL M31 LRGB 2 NUITS : CAUSE des 80 refus TROUVÉE (diagnostic seul, RIEN de codé)

### État actuel
- `AVASTACK_VERSION = "2.67.0"` — **INCHANGÉE** : cette session n'a modifié
  AUCUN fichier de code (diagnostic hors-ligne seul, sur les archives de frames).
  Les DEUX correctifs décidés ci-dessous sont à écrire à la prochaine session
  (jalon 116).
- Test réel d'Alain (09/10, 19h27→20h01), composition **LRGB** = **L du 13/09**
  + **R/G/B du 22-23/09** : écran **130 empilées · 80 non alignées ·
  L: 9 · R: 39 · G: 45 · B: 37** ; astrométrie résolue (120 étoiles, 2,467″/px) ;
  SPCC mesurée sur 130 frames. Symptômes : **doublons rouges** au début, puis
  **trace sombre**, et **biseaux noirs dans les coins** (donc recadrage
  d'intersection NON appliqué) ; halo + couleurs fausses après retrait de gradient.
- Ces compteurs sont **reproduits EXACTEMENT** par rejeu hors-ligne : seules les
  frames qui exigent le **retournement de 176°** sont perdues.

### La cause (mesurée — deux défauts cumulés)

*Ce que disent les frames* (rejeu des archives = frames réellement lues,
ORB + similitude SANS garde-fou) :
- L (13/09) ↔ R/G/B (22-23/09) : **+176,2°**, échelle 0,999, translation
  ≈ (3924, 2036) px — donc DANS la tolérance 180° ± 10° : la géométrie n'est
  pas en cause ;
- dans la nuit L : 0,00-0,04° sur 76 min (aucune rotation de champ, dérive ≤ 5,6 px) ;
- **les dossiers R/G/B contiennent EUX-MÊMES les deux côtés du Pier** (frames
  0→38/36/35 d'un côté, la fin à −176,0°) ; la nuit **L est du côté des frames RGB
  TARDIVES** (écart 0,14°) ;
- budget : côté A = 38+36+37 = **111 frames → toutes empilées** ; côté B =
  60 L + 39 RGB = **99 frames → 19 empilées et 80 refusées**. Le compte tombe juste.

*Pourquoi le retournement échoue :*
- ① **La normalisation écrase la frame** — `alignment._norm8` convertit la frame
  en 8 bits avec les bornes de **la RÉFÉRENCE**. Entre deux nuits/filtres les fonds
  diffèrent de ~1,8× (R : lo 0,031 contre L : lo 0,0547) → **97,3 % / 93,7 % /
  78,6 %** des pixels de R/G/B **écrasés à 0** (et, dans l'autre sens, la frame L
  sature : 1 appariement) → ORB rend **2-3 appariements** au lieu des 8 exigés.
  **Avec les PROPRES bornes de la frame : 22-96 appariements et 10-62 inliers, au
  BON angle.**
- ② **`_triangles` ne peut pas porter le retournement** — c'est le SEUL chemin
  capable d'un saut de ~3900 px (`_etoiles` vote une translation à ±40/±100 px,
  `_phase` n'accepte que ±40 px). Or il s'appuie sur les **12 étoiles les plus
  brillantes** : mesuré **4-5 appariements** (seuil 6) sur TOUS les couples L↔RGB —
  et il s'écroule même DANS la nuit L (L[0]↔L[59] = 5). Base élargie à 18 :
  intra-nuit réparé (5 → **150**), **inter-nuits toujours 4-5** (ce sont vraiment
  d'autres étoiles qui dominent d'une nuit/filtre à l'autre).

### Preuve hors-ligne (rejeu du début de session, VRAIES frames, règles du worker)
- code **ACTUEL** : L 2/7 · R 7/1 · G 7/1 · B 7/1 → **10 refus** — le symptôme exact
  (couche L affamée) ;
- correctif **① seul** : L 9/0 · R 8/0 · G 7/1 · B 8/0 → **1 refus** ;
- correctifs **① + ② (ORB 8000)** : L 9/0 · R 8/0 · G 8/0 · B 8/0 → **0 refus**.
  (« empilées / refusées ».) Dose ORB mesurée sur le cas difficile : **8 000 points
  ⇒ 8-35 inliers à +176,2°**, contre 3-5 à 1 000 points — les 4 cas testés passent.

### Fichiers modifiés dans cette phase
- `AVANCEMENT.md` seulement (mémoire) : **AUCUN fichier de code**, version
  inchangée, rien de construit ni publié. La leçon durable pour `CLAUDE.md` sera
  écrite quand le jalon 116 sera validé en réel.

### Décisions prises
- **SOLUTION RETENUE PAR ALAIN (09/10/2026 soir) : les DEUX correctifs ensemble.**
  ① `alignment._compute_direct` normalise la frame sur **ses propres** percentiles
  (le chemin `_phase` garde, LUI, le domaine PARTAGÉ : son test SSD en a besoin) ;
  ② `compute` ajoute un **dernier recours avant refus** : ORB **étoffé (8 000
  points, MÊMES garde-fous)** essayé sur la frame, puis sur la frame retournée de
  180°, descripteurs de référence mis en cache.
- Coûts assumés : ① ≈ +40 ms par frame (une paire de percentiles) ; ② ≈ +0,3 s
  **uniquement** sur les frames qui échouent partout.
- C'est un **jalon** (116) : banc neuf + rejeu des bancs d'alignement + garde-fou
  vert + version **2.68.0** + changelog + ce fichier, dans la MÊME réponse.

### Outils de diagnostic jetables (`%TEMP%`, hors dépôt)
`avastack_diag_lrgb_roles.py` / `_roles2.py` (rôle d'une archive de frames),
`_geo.py` (angle vrai + couture de chaque chemin de l'aligneur), `_tri.py`
(triangles pas à pas), `_orb.py` (chemin ORB pas à pas), `_norm.py` (mesure de
l'écrasement 8 bits), `_base.py` (effet de la base TRI_N_MAX), `_orbdose.py` (dose
ORB utile), `_scan.py` (index du retournement dans la nuit), et **`_preuve.py`**
(rejeu comparatif code actuel / correctifs — c'est LUI qui a prouvé le gain).
Rappel : `%TEMP%\avastack_frames_*` = frames réellement LUES, supprimées par
l'appli au démarrage **6 h** après leur dernière écriture — les copier si la preuve
doit survivre ; en-têtes perdus, le rôle se déduit du NOMBRE de frames.

### Problèmes ouverts / Points d'attention
- ⚠ **La piste 180° n'est PAS abandonnée** (contrairement à la note du jalon 115) :
  le jeu mêlant DEUX nuits la porte réellement (176,2°), et **les dossiers R/G/B la
  portent aussi** (26 % des frames sont de l'autre côté).
- **À ARBITRER au jalon 116** : le MÊME défaut a DÉJÀ été rencontré puis corrigé
  dans le **solveur d'astrométrie** (`avastack/catalogues/solveur.py` : « sur un
  champ large/riche, le top-12 d'image ≡ top-20 catalogue par invariants ne tient
  plus » → remplacé par **`_ransac_paires`**, vote (échelle, angle) sur TOUTES les
  paires top-60 × top-120). Reprendre cette approche pour le ② de l'aligneur serait
  plus économe qu'un ORB de 8 000 points — **à mesurer avant de coder**.
- **L'aligneur échoue en SILENCE** : ni les alignements ni les empilements ne vont
  au journal (`%APPDATA%\AVAStack\journal.txt` ne porte que l'UI et l'astrométrie).
  Sans les archives de frames, ce diagnostic était impossible.
- **Recadrage d'intersection** : il ne s'applique QUE si le cadre est sain — un
  cadre dégénéré rend `None`, donc AUCUN recadrage. C'est ce qui laisse les biseaux
  noirs visibles et fait « coussin clair + couleurs fausses » au retrait de gradient
  (piège GraXpert déjà documenté dans CLAUDE.md). À vérifier AVANT d'accuser
  l'optique, le fond de ciel ou le traitement.
- Les versions **v2.63.0 → v2.67.0** attendent toujours leur commit de clôture ;
  **paquets et release GitHub ne sont PAS faits** (dernier tag publié = v2.62.1).

### Prochaines étapes
- **Jalon 116** : écrire les deux correctifs (① + ②), banc neuf
  (`bancs/_test_align_lumiere_jalon116.py` : une frame « autre nuit » = fond ÷2 et
  rotation 176° doit S'ALIGNER, alors qu'une rotation de 30° doit rester REFUSÉE),
  rejeu des bancs d'alignement + garde-fou, **v2.68.0** + changelog.
- Puis **REFAIRE LE TEST RÉEL** sur le MÊME jeu LRGB deux nuits : attendu
  **0 refus fantôme**, L ≈ 60 frames, plus de biseaux, gradient propre.
- Ensuite seulement : **paquets Windows/Linux/macOS + release GitHub**.

---

## Chantier en cours — ALIGNEMENT : retournement au méridien + astrométrie

**But** : que les frames d'UN côté du méridien (rotation ~180° par rapport à la
référence) s'empilent au lieu d'être rejetées, et que l'astrométrie fonctionne sur
un empilement LRGB.

**État (09/10/2026 soir)** : jalons **111→115 LIVRÉS, TESTÉS EN RÉEL et POUSSÉS**
(v2.67.0 — l'astrométrie est réparée par le correctif de DOMAINE : le solveur
recevait le composite normalisé au lieu de la couche brute). **Le RETOURNEMENT, en
revanche, est INVALIDÉ EN RÉEL** : le test du soir perd 80 frames sur 210 → c'est
l'objet du **jalon 116** (bloc de session ci-dessus). Le détail des jalons vit dans
le changelog de `avastack/__init__.py` et dans l'historique git.

**Règles d'or** :
- Un jalon = un banc neuf + rejeu des bancs concernés (TOUS VERTS) + garde-fou
  `bancs/_test_refactoring_garde_fou.py` VERT (syntaxe, surface 75, hash au bit).
- On ne réécrit JAMAIS un tag publié ; version + changelog + AVANCEMENT.md dans la
  même réponse ; commentaires et docstrings en FRANÇAIS.
- Le chantier de refactoring (jalons 100→110) est CLOS : plus de découpage de
  `app.py` ni de typage rétroactif.

---

## En attente / prochaine session

- **Jalon 116** (les deux correctifs d'alignement) PUIS **test réel du jeu M31 des
  deux nuits** — seul point du chantier non validé.
- **Publication** : paquets Windows/Linux/macOS + release GitHub **v2.67.0+**
  (dernier tag publié = **v2.62.1** ; les v2.63.0→v2.67.0 partent dans le commit de
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
- **ALIGNEUR — le retournement est le point faible (MESURÉ 09/10/2026)** : une
  frame retournée ne peut passer QUE par `_triangles` (base = top-12 des étoiles :
  **4-5 appariements au lieu de 6** sur des nuits réelles) OU par ORB — mais ORB
  est **aveuglé par `_norm8`**, qui étire la frame avec les bornes de la
  **RÉFÉRENCE** (entre deux nuits/filtres : **93-99 % des pixels écrasés à 0**, et
  1 appariement dans l'autre sens). Une brute CALIBRÉE (dark) peut aussi être
  refusée là où la même brute non calibrée passe.
- **Recadrage d'intersection** : il ne s'applique PAS si le cadre est dégénéré
  (⇒ biseaux noirs visibles + « coussin clair » et couleurs fausses au retrait de
  gradient). À contrôler AVANT d'accuser l'optique ou le traitement.

---

## Clôtures précédentes

- **09/10/2026** : jalons 111→115 (v2.67.0) — cause de l'échec d'astrométrie
  trouvée (le solveur recevait le composite normalisé au lieu de la couche brute),
  test réel OK **SANS** retournement, commité et poussé (détail : changelog
  `avastack/__init__.py`).
- **07/10/2026** : clôture du chantier de refactoring (jalons 100→110) —
  v2.62.1 livrée, testée en réel, publiée.

