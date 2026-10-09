# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## Session du 09/10/2026 (nuit) — JALON 117 : LES DEUX DÉFAUTS SONT CORRIGÉS (117a recadrage, 117b alignement)

### État actuel
- Version stable = **2.69.1** (117a recadrage v2.69.0 + 117b alignement v2.69.1),
  **TEST RÉEL OK** (09/10/2026, M31 deux nuits) : ① les **COINS/biseaux ont
  disparu** (retrait de gradient de nouveau possible) — validé par Alain ; ②
  l'**ÉCHO ROUGE** du recouvrement **s'est éteint**. Commit + push faits.
- ⚠ **RESTE un LISERÉ ROUGE sur les ÉTOILES LES PLUS BRILLANTES** (vu sur le PNG
  « save as seen ») : hypothèse = le plancher ~0,8 px inter-nuits — à MESURER et
  diagnostiquer dans une SESSION DÉDIÉE (rien à coder ici pour l'instant).
- Image de référence : `C:\Astro\test\Andromeda Nebula2.69.1.png` (hors dépôt).
- Bancs TOUS VERTS : recadrage 117, alignement 117b, alignement 13/15/116,
  garde-fou refactoring (surface 75, hash, pyright 0/49) ; mesures et leçons
  durables dans CLAUDE.md « Pièges ».

### Mesures qui ont guidé les correctifs (déjà exploitées — NE PAS REMESURER)
- **Défaut n° 1** (diag `%TEMP%\avastack_diag_j117_crop.py`, rejeu des 4 dossiers
  réels avec le code réel, replica du polygone vérifié == code réel) : le polygone
  d'intersection est JUSTE (96,11 % de la frame, 11-12 sommets) mais ses extrêmes
  tombent sur les **MILIEUX des côtés** → `cadre_intersection` rend
  **(3, 3, 2176, 3852)** = frame entière − 3 px de marge (99,5 % conservés) →
  **le recadrage ne recadre rien** (le PNG livré, 3833×2163, n'a perdu que
  23×17 px). Ce qu'il faudrait : le **plus grand rectangle AXIAL INSCRIT** dans le
  polygone = insets (62, 137) px → 3732×1906 px (**84,6 %**).
  Couverture par rôle (mesurée) : L (nuit 1, 0°) **0,00 %** de pixels non
  couverts ; R/G/B (nuit 2, 176°) **3,6 %** dans un motif de « moulin » (une
  grande casquette par coin). Sur le livré : les 4 coins sont à **0,11-0,25** du
  niveau du centre, avec une teinte différente **et différents entre eux** (c'est
  le recouvrement, pas la vignette) → c'est ce qui rend le retrait de gradient
  impossible.
- **Défaut n° 2** (diags `avastack_diag_j117_halo.py`, `_halo2.py`, `_png.py`) :
  résidu de la matrice de l'appli sur les frames à 176° = **0,96 à 2,38 px**
  (0-20 % des étoiles sous 0,30 px), contre **0,14-0,15 px** pour les frames de la
  nuit 1 (92 % des étoiles sous 0,30 px). La matrice **CONVERGÉE** par re-fit
  itératif (appariement mutuel à 4 px puis ré-estimation à 1,5/1,0 px) est la MÊME
  à ±1 px sur **7 frames indépendantes**, s'écarte de celle de l'appli de
  **2,0 à 6,5 px** en translation, fait remonter **120-146 couples** d'étoiles
  (contre 0-35) et ramène le résidu à ~0,8 px. L'affine (6 paramètres) n'améliore
  PAS ce plancher (0,80-0,87 px) ; l'homographie testée est NON CONCLUANTE
  (solution dégénérée) → le plancher de ~0,8 px reste à instruire.
  Sur le livré : **R − V = (−1,30, −1,33) px**, B − V = (+0,73, +0,91) px,
  |Δ| médian 1,9 px → l'écho rouge est la signature du décalage des canaux.

### Ce qui a été fait
- **117a (v2.69.0)** — recadrage = PLUS GRAND RECTANGLE AXIAL INSCRIT.
  `stacking.cadre_intersection` rendait la BOÎTE ENGLOBANTE du polygone
  d'intersection : pour une rotation de quelques degrés elle vaut la PLEINE image
  (mesuré (3, 3, 2176, 3852) sur 3856×2180 → seuls 23×17 px retirés) → coins non
  couverts visibles, retrait de gradient impossible. Désormais calculé par la
  structure du polygone CONVEXE : sur une bande [x0, x1] la hauteur vaut
  min(hi(x0), hi(x1)) − max(lo(x0), lo(x1)) (`hi` concave, `lo` convexe → les
  extrêmes tombent aux extrémités, aucune heuristique de pixels). Nouveaux
  `plus_grand_rect_inscrit`, `_coupes_verticales`, `_CROP_PAS_MAX` (1 024).
  Attendu sur le jeu M31 : insets (62, 137) px → 3732×1906 px (84,6 %).
- **117b (v2.69.1)** — raffinement sous-pixel à PORTE LARGE ET VÉRIFIÉ.
  `alignment._raffiner_centroides` était gated à 1,5 px avec la matrice BRUTE :
  au-delà il ne trouvait que 0-4 couples et ne corrigeait RIEN, et rien ne
  VÉRIFIAIT la matrice retenue sur les étoiles. Désormais porte 4,0 → 1,5 →
  1,0 px (`RAFFIN_RAYONS`), ré-estimation à chaque passage, VÉRIFICATION par
  centroïdes (`_verif_centroides`), matrice d'entrée rendue INCHANGÉE si rien
  n'est meilleur (jamais de régression). Nouveaux `_appariements_mutuels`,
  `_reestimer_centroides`, `_verif_centroides`.

### Fichiers modifiés dans cette phase
- `avastack/processing/stacking.py` : `cadre_intersection` remanié (117a) +
  helpers `plus_grand_rect_inscrit` / `_coupes_verticales` + `_CROP_PAS_MAX`.
- `avastack/processing/alignment.py` : `_raffiner_centroides` remanié (117b) +
  3 helpers + `RAFFIN_RAYONS` / `RAFFIN_VERIF_RAYON`.
- `avastack/__init__.py` : version **2.69.1** + changelog v2.69.0 / v2.69.1.
- `bancs/_test_crop_inscrit_jalon117.py` : banc NEUF (117a).
- `bancs/_test_align_raffin_jalon117.py` : banc NEUF (117b).
- `CLAUDE.md` : les deux pièges du 117 passés de « DÉFAUT OUVERT » à « CORRIGÉ ».
- Diags JETABLES dans `%TEMP%` (hors dépôt, `avastack_diag_j117_*.py`).

### Décisions prises
- Correctif n° 1 : plus grand rectangle AXIAL INSCRIT (un simple élargissement de
  la marge ne retirerait pas des coins asymétriques — mesuré (62, 137) px).
- Correctif n° 2 : porte d'appariement LARGE puis RESSERRÉE + vérification par
  centroïdes, avec la règle « jamais de régression » (matrice d'entrée rendue si
  aucune candidate n'est meilleure).
- La porte initiale de 4 px suffit : le résidu PAR POINT des frames retournées
  vaut 0,96-2,38 px (les 2,0-6,5 px mesurés concernent la TRANSLATION, pas le
  résidu par étoile).

### Problèmes ouverts
- **RESTE ROUGE sur les étoiles les plus brillantes** (test réel 117, vu sur le
  PNG « save as seen ») : piste principale = le plancher ~0,8 px inter-nuits —
  À MESURER/diagnostiquer en session dédiée (probable 117c).
- Plancher de ~0,8 px entre les deux nuits après convergence : inexpliqué (ni
  affine, ni homographie convergée) — suspect n° 1 du reste rouge ci-dessus.
- L'aligneur n'écrit toujours RIEN au journal (`%APPDATA%\AVAStack\journal.txt`).
- L'alternative « paires d'invariants top-60 × top-120 » du solveur reste non
  mesurée (le ② du 116 suffit, 0 refus).

### Prochaines étapes
- **Session dédiée** : MESURER et diagnostiquer le **reste rouge des étoiles les
  plus brillantes** (hypothèse : plancher ~0,8 px inter-nuits ; piste : décalage
  R/G/B sur le PNG « save as seen » + résidu par centroïdes d'étoiles). Ouvrir un
  **117c** si un correctif est identifié.
- Ensuite **paquets + release GitHub v2.69.x** (dernier tag publié = v2.62.1 ;
  Store toujours en v2.50.0).

### Points d'attention
- Les archives de frames (`%TEMP%\avastack_frames_*`, purgées par l'appli 6 h
  après leur dernière écriture) ont servi aux mesures : les COPIER avant de
  relancer un rejeu longtemps après.
- Le diag n° 1 recopie `note_alignement` pour voir l'intérieur du calcul ; sa
  réplique est vérifiée IDENTIQUE au code réel (le banc le dit en première ligne) :
  garder ce contrôle si le diag est rejoué après le correctif.
- `set_reference` ne passe PAS par `reset()` : tout nouveau cache doit y être
  invalidé AUSSI.

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
(v2.67.0) ; **jalon 116 LIVRÉ** (v2.68.0 : ① bornes propres pour l'ORB, ② dernier
recours ORB étoffé) — test réel **OK** (0 refus hors-ligne, deux nuits empilées).
**Jalon 117 LIVRÉ** (v2.69.0 recadrage + v2.69.1 alignement) : les deux défauts
vus au test réel du 116 sont corrigés. **TEST RÉEL OK** (09/10/2026) : coins
retirés, écho rouge éteint — reste un liseré rouge sur les étoiles brillantes (à
diagnostiquer). Détail : changelog de `avastack/__init__.py` et historique git.

**Règles d'or** :
- Un jalon = un banc neuf + rejeu des bancs concernés (TOUS VERTS) + garde-fou
  `bancs/_test_refactoring_garde_fou.py` VERT (syntaxe, surface 75, hash au bit).
- On ne réécrit JAMAIS un tag publié ; version + changelog + AVANCEMENT.md dans la
  même réponse ; commentaires et docstrings en FRANÇAIS.
- Le chantier de refactoring (jalons 100→110) est CLOS : plus de découpage de
  `app.py` ni de typage rétroactif.

---

## En attente / prochaine session

- **MESURER/DIAGNOSTIQUER le RESTE ROUGE des étoiles brillantes** (session
  dédiée) : image de référence `C:\Astro\test\Andromeda Nebula2.69.1.png`
  (« save as seen », hors dépôt) ; hypothèse = plancher ~0,8 px inter-nuits.
  Piste : décalage R/G/B SUR LE PNG (cf. diag `avastack_diag_j117_png.py`) et
  résidu inter-nuits par centroïdes d'étoiles.
- **Publication** : paquets Windows/Linux/macOS + release GitHub **v2.69.1**
  (dernier tag publié = **v2.62.1** ; les v2.63.0→v2.69.1 partent dans le commit
  de clôture).
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

- **09/10/2026 (nuit)** : jalon 117 (v2.69.0 recadrage + v2.69.1 alignement) —
  coins recadrés (117a) et écho rouge éteint (117b), **test réel OK**, commité et
  poussé ; reste un liseré rouge sur les étoiles brillantes (hypothèse plancher
  ~0,8 px), à mesurer en session dédiée.
- **09/10/2026 (nuit)** : jalon 116 (v2.68.0) — les deux nuits (176°) s'empilent
  (① bornes propres + ② ORB étoffé), **test réel OK** ; deux défauts mineurs notés
  (rectangle commun, halo-écho rouge) → corrigés par le 117.

