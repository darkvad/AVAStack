# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## Session du 09/10/2026 (suite) — JALON 117c : MESURE DU LISERÉ ROUGE (diagnostic, RIEN corrigé)

### État actuel
- Le **liseré rouge des étoiles brillantes** (signalé après le 117) est **MESURÉ et
  CAUSÉ** : c'est le **COMBINE LRGB** qui amplifie les AILES des étoiles (PSF de L
  bien plus large que celle du RGB) — **PAS** un décalage d'alignement ni l'optique.
  Confirmé par l'observation d'Alain (halos SEULEMENT avec L) et par un **rejeu réel**
  des couches (`canal_*.fit`) : halo ×2,8, supprimé par un ratio LISSE (σ ≈ 4 px).
- **Rien n'est codé ni corrigé** : session de diagnostic. Version stable inchangée
  = **2.69.1**.

### Ce qui a été mesuré (PNG livré `C:\Astro\test\Andromeda Nebula2.69.1.png`)
- **Décalage des canaux** (corrélation de phase, 4 zones concordantes) : 2.68.0
  R↔V = **(+0,19, +0,29) px** → 2.69.1 **R↔V = (−0,06, −0,21)**, **B↔V =
  (+0,05, +0,21)** ; |Δ| = **0,21 px**. Donc ① l'écho du 117b est bien parti
  (0,35 → 0,21 px) ; ② il RESTE un résidu systématique de **~0,2 px**, R et B
  **symétriques par rapport à V**.
- **Optique ÉCARTÉE** : la FWHM des étoiles **par filtre**, mesurée sur les frames
  réelles (rôles connus), est la MÊME — L 2,42 / R 2,37 / V 2,28 / B 2,32 px →
  **R/G = 1,039 · B/G = 1,019** (aucune PSF plus large en R).
- **Signature du liseré** : sur une étoile brillante `R/V` vaut 1,25 au cœur et
  **MAXIMAL (1,60) dans l'anneau** (r≈4-5 px), où `B/V` tombe à ~0,5 ; sur les
  étoiles faibles l'anneau n'apparaît PAS → l'effet **dépend de la luminosité**.
  Les crops zoomés (diag `j117c_etoiles_2691.png`) montrent un cœur pâle/blanchi
  entouré d'un anneau orange.

### Cause identifiée (MESURÉE sur les couches réelles)
- **C'est le COMBINE LRGB (luminance), pas la couleur ni l'alignement** — conforme à
  l'observation d'Alain : halos SEULEMENT avec L (RGB seul = rien).
- **Mismatch de PSF L vs RGB (mesuré)** : sur `canal_L/R/G/B.fit` (run LRGB réel) le
  profil de L est bien plus large que celui de la luminance RGB — `L/luma` = 1,00 au
  cœur, **1,5 (r=2,5), 2,5 (r=3,5), 3,3 (r=4,5)**, ~3 dans les ailes. (Centroïde
  L vs luma décalé de ~0,19 px = nuit 1 vs nuit 2.)
- Le combine `rgb *= L/luma` **amplifie donc les AILES des étoiles** : sur le REJEU
  réel (mêmes couches, même étirement VeraLux), le rapport **anneau/cœur à r≈4 px
  passe de 0,124 (RGB seul) à 0,347 (avec L)** = **halo ×2,8**. Preuve visuelle :
  `%TEMP%\j117c_fix_visuel.png` (colonne 2 = halo jaune/rouge ; colonnes 1 et 3 = net).
- **Correctif DeepSeek testé** (flouter le ratio `L/luma`) : à **σ = 0,5-1 px il NE
  SUFFIT PAS** (0,347 → 0,338 / 0,286) ; il faut **σ ≈ 4 px** pour revenir au niveau
  RGB seul (0,128), et σ=4 est VISUELLEMENT identique au RGB seul. Le diagnostic est
  juste, mais le RAYON proposé est **4-8× trop petit**.
- Écartés : l'**alignement** (le dipôle est parti) ; l'**optique par filtre** (FWHM
  R/G = 1,039) ; le combine comme source DIRECTE de couleur (il est neutre :
  `rgb * ratio[...,None]`) — l'anneau prend la couleur des ailes ; VeraLux (l'anneau
  de convergence existe mais ~20 % seulement, cf. diag synthétique `..._veralux.py`).

### Prochaines étapes
- **117c correctif (à VALIDER par Alain avant de coder)** : porter le combine L sur un
  ratio **LISSÉ** (gaussienne **σ ≈ 4 px** à cette échelle → à rendre PROPORTIONNEL à
  la FWHM/à la taille des étoiles), pour que la luminance n'apporte QUE le grand
  échelle (nébuleuse) et n'épaississe plus les halos d'étoiles. Banc à prévoir :
  étoile colorée + L à ailes larges → halo divisé par ≥ 2, RGB seul inchangé.
- **Session CLOSE ici (09/10/2026)** : aucun code touché ; le correctif 117c est
  PROPOSÉ et attend le feu vert d'Alain (cf. « En attente / prochaine session »).

### Points d'attention / pièges de cette session
- Diags jetables (`%TEMP%`, hors dépôt) : `avastack_diag_j117c_lisere.py`,
  `_crops.py`, `_psf.py`, `_star.py`, `_phase.py`, `_veralux.py`, `_lrgb.py`,
  `_lrgb2.py`, `_lpsf.py`, `_fix.py`, `_visuel.py`.
- ⚠ `stars.detecter_positions` renvoie des positions **(x, y)**, pas (y, x) —
  ce piège fausse tout crop/centroïde d'étoile.
- Les composites de rejeu sont sauvés dans `%TEMP%\j117c_rgb_only.npy` /
  `j117c_lrgb.npy` (rechargeables pour ne pas refaire l'étirement VeraLux).

---

## HISTORIQUE — jalon 117 (09/10/2026, nuit) : 117a recadrage v2.69.0 + 117b alignement v2.69.1
(bloc d'époque conservé ; les mesures vivent aussi dans CLAUDE.md « Pièges » et le changelog)

### État actuel
- Version stable = **2.69.1** (117a recadrage v2.69.0 + 117b alignement v2.69.1),
  **TEST RÉEL OK** (09/10/2026, M31 deux nuits) : ① les **COINS/biseaux ont
  disparu** (retrait de gradient de nouveau possible) — validé par Alain ; ②
  l'**ÉCHO ROUGE** du recouvrement **s'est éteint**. Commit + push faits.
- Le liseré rouge des étoiles brillantes laissé OUVERT ici a été **MESURÉ au 117c**
  (bloc en tête de fichier) : ce n'est **PAS** le plancher ~0,8 px supposé.
- Image de référence : `C:\Astro\test\Andromeda Nebula2.69.1.png` (hors dépôt).
- Bancs TOUS VERTS : recadrage 117, alignement 117b, alignement 13/15/116,
  garde-fou refactoring (surface 75, hash, pyright 0/49) ; mesures et leçons
  durables dans CLAUDE.md « Pièges ».

### Mesures d'époque (117) — RENVOI
- Défaut n° 1 (polygone d'intersection → coins non recadrés) et défaut n° 2 (résidu
  d'alignement 0,96-2,38 px des frames à 176°, plancher ~0,8 px après convergence,
  R−V = (−1,30, −1,33) px sur le livré 2.68.0) : mesures détaillées au changelog
  **v2.69.0/v2.69.1** et dans CLAUDE.md « Pièges ». NE PAS REMESURER.
- ⚠ Le **liseré rouge** n'est PAS ce plancher : cf. bloc **117c** en tête de fichier.

### Détail d'implémentation (117a/117b) — renvoi
- 117a (recadrage) et 117b (raffinement sous-pixel vérifié) : code, fichiers touchés,
  bancs neufs et décisions → changelog **v2.69.0/v2.69.1** (`avastack/__init__.py`),
  git, et CLAUDE.md « Pièges » (jalons 116/117). NE PAS REDÉTAILLER ICI.


### Problèmes ouverts
- **Reste rouge des étoiles brillantes** : **MESURÉ au 117c** (bloc en tête) — ce
  n'est PAS le plancher ~0,8 px, mais un anneau de couleur (VeraLux).
- Plancher de ~0,8 px entre les deux nuits après convergence : toujours non résolu,
  mais **mis HORS DE CAUSE** pour le liseré (117c).
- L'aligneur n'écrit toujours RIEN au journal (`%APPDATA%\AVAStack\journal.txt`).
- L'alternative « paires d'invariants top-60 × top-120 » du solveur reste non
  mesurée (le ② du 116 suffit, 0 refus).

### Prochaines étapes (à l'époque)
- Session dédiée de mesure du liseré rouge → **FAITE** (bloc 117c en tête).
- Puis **paquets + release GitHub v2.69.x** (dernier tag publié = v2.62.1 ;
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

- **Liseré rouge des étoiles brillantes** : **MESURÉ et CAUSÉ au 117c** (bloc en
  tête) — c'est le **combine LRGB** (PSF de L bien plus large que le RGB → ailes
  d'étoiles amplifiées ×2,8). Correctif testé : **lisser le ratio L/luma
  (σ ≈ 4 px)**. À **VALIDER par Alain** avant de coder le **117c correctif**.
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

- **09/10/2026 (suite)** : jalon 117c — **DIAGNOSTIC** (aucun code) du liseré rouge
  des étoiles brillantes : **causé** par le combine LRGB (PSF de L trop large → ailes
  d'étoiles ×2,8) ; correctif proposé (ratio L/luma lissé σ≈4 px) à valider.
- **09/10/2026 (nuit)** : jalon 117 (v2.69.0 recadrage + v2.69.1 alignement) — coins
  recadrés et écho rouge éteint, **test réel OK**, commité et poussé ; le liseré rouge
  restant est expliqué par le 117c.

