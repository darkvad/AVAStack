# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## Session du 10/10/2026 — JALON 117d : LISSAGE LRGB OPT-IN + σ RÉGLABLE (v2.71.0) — CLOSE, PUBLIÉE

### État actuel
- **Le 117c a été VALIDÉ EN RÉEL** (Alain, 10/10/2026) : halos ÉTEINTS, image qui
  convient (`C:\Astro\test\Andromeda Nebula2.70.0-117c.png`). MAIS son seuil de
  masque (20σ) est un réglage **EMPIRIQUE, calé sur ce jeu d'essai** : sa validité
  sur une autre image n'était pas garantie, et il s'appliquait PARTOUT, sans choix.
- **DÉCISION D'ALAIN** : en faire une OPTION VISIBLE. **v2.71.0 LIVRÉE ET
  PUBLIÉE** : case « Lisser le combine LRGB (halos d'étoiles) » **DÉCOCHÉE par
  défaut** (vrai opt-in) + champ **σ du masque** (défaut 20, bornes [3 ; 100]).
  **TESTÉ EN RÉEL PAR ALAIN (M31) : VALIDÉ.**
- **Intervient à la COMPOSITION** (les couches ne sont pas touchées) : on peut
  cocher/décocher et changer σ **À CHAUD**, à n'importe quelle frame, sans
  redémarrer la session.

### Fichiers modifiés dans cette phase
- `processing/composition.py` : `composer(..., seuil_masque_sigma=None)` ;
  `_masque_etoiles`/`_lisser_ratio_masque` reçoivent le seuil ; constantes
  `SEUIL_MASQUE_MIN/MAX` ; façade `CompositeStacker.lissage_halos` (défaut False)
  et `seuil_masque_halos` (défaut 20), tous deux dans la CLÉ de mémoïsation.
- `core/worker.py` : instantanés `_compo_lissage_halos`/`_compo_seuil_halos` +
  resync (création ET chaque `_tick`) ; **8e élément** du tuple `vl_compo`.
- `processing/display.py` : helper `params_lissage_halos(compo)` (déballage
  TOLÉRANT : jobs à 6/7 éléments → inactif) + passage à `composer`.
- `ui/panels/compo.py` (case + champ σ), `ui/app.py` (instantanés, callback
  `_on_lissage_halos`, `_lire_seuil_halos` borné, 2 points de snapshot + reprise
  à chaud, 8e élément des 2 `vl_compo`), `ui/config_ui.py` (persistance
  `lissage_halos` / `lissage_halos_sigma`), `ui/saver.py` (`AVACOMPO` dit l'état).
- `avastack/__init__.py` : **v2.71.0** + changelog. Banc neuf
  `bancs/_test_lissage_halos_optin_jalon117d.py` — VERT.

### Décisions prises
- **VRAI opt-in** : case décochée = `sigma_l = 0` = combine d'AVANT le 117c
  (vérifié AU BIT au banc) → halos visibles tant qu'on ne coche pas.
- **σ du MASQUE réglable** — pas le σ du flou, qui reste AUTO (1,7 × FWHM) car il
  s'adapte déjà à la résolution : c'est le seuil de masque qui dépendait de
  l'image (médiane-MAD gonflée par le disque d'une galaxie).
- **`composer()` GARDE ses défauts** (None = auto) : le 117c et son banc restent
  valides ; c'est la FAÇADE qui exprime le choix (décoché → σ = 0).
- **Application À CHAUD** : relue à chaque tour comme les gains (jalon 55), et
  lissage/seuil sont dans la CLÉ de mémoïsation (sinon réglage « sans effet »).

### Prochaines étapes
- Rien en attente sur le 117d (testé en réel, commité/poussé, **release v2.71.0
  publiée** : 4 paquets + `INSTALLATION.md`, tag `v2.71.0` sur `9fafc5e`).
- Prochaine session : au choix d'Alain (voir « En attente »).

### Points d'attention / pièges de cette session
- Le réglage entre aussi dans la SAUVEGARDE LINÉAIRE : `AVACOMPO` dit « lissage
  combine LRGB actif (masque N sigma) » / « inactif ».
- ⚠ `stars.detecter_positions` renvoie des positions **(x, y)**, pas (y, x).
- Coût : masque + seeing UNE fois par recomposition (mémoïsée) — jamais dans la
  boucle chaude.

---

## HISTORIQUE — jalon 117c (10/10/2026) : liseré rouge — lissage MASQUÉ du ratio (v2.70.0)
- Codé, **test réel OK** (halos éteints, image validée) ; lissage GLOBAL écarté (−9/−18 % de détail fin).
- Détail : changelog **v2.70.0**, banc `_test_lrgb_halo_jalon117c.py`. NE PAS REMESURER.
- La case UI + le σ réglable du masque sont LE 117d (bloc de session ci-dessus).

## HISTORIQUE — jalon 117 (09/10/2026, nuit) : recadrage v2.69.0 + alignement v2.69.1
- Livré, **test réel OK** (coins/biseaux retirés, écho rouge éteint), commité/poussé.
- Mesures (polygone d'intersection, résidu 0,96-2,38 px à 176°, R−V du livré 2.68.0) :
  changelog **v2.69.0/v2.69.1**, CLAUDE.md « Pièges » (116/117), git. NE PAS REMESURER.
- Le liseré rouge (≠ plancher ~0,8 px) laissé ouvert ici est corrigé par le **117c**.

### Problèmes ouverts (hérités du 117, toujours valides)
- L'**aligneur n'écrit toujours RIEN** au journal (`%APPDATA%\AVAStack\journal.txt`).
- L'alternative « paires d'invariants top-60 × top-120 » du solveur reste non mesurée.

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
retirés, écho rouge éteint. **Jalon 117c VALIDÉ EN RÉEL** (v2.70.0) : liseré rouge
éteint par un lissage **MASQUÉ** du ratio L/luma (le lissage GLOBAL, écarté,
retirait 9-18 % du détail). **Jalon 117d CODÉ** (v2.71.0) : ce lissage devient
**OPT-IN** (case décochée par défaut) et son **seuil de masque devient RÉGLABLE**
— **NON committé, test réel à faire**. Détail : changelog de `avastack/__init__.py`
et historique git.

**Règles d'or** :
- Un jalon = un banc neuf + rejeu des bancs concernés (TOUS VERTS) + garde-fou
  `bancs/_test_refactoring_garde_fou.py` VERT (syntaxe, surface 75, hash au bit).
- On ne réécrit JAMAIS un tag publié ; version + changelog + AVANCEMENT.md dans la
  même réponse ; commentaires et docstrings en FRANÇAIS.
- Le chantier de refactoring (jalons 100→110) est CLOS : plus de découpage de
  `app.py` ni de typage rétroactif.

---

## En attente / prochaine session

- **RIEN en attente** : le 117d est testé en réel, commité/poussé (`9fafc5e`) et
  **publié** — release GitHub **v2.71.0** (4 paquets + `INSTALLATION.md`).
  Dernier tag publié = **v2.71.0**.
- **Microsoft Store** : cadence SÉPARÉE — l'application publiée y reste la
  **v2.50.0** ; un MSIX v2.71.0 pourra être reconstruit puis resoumis plus tard
  (hors périmètre de cette session).
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

- **10/10/2026** : jalon 117d (v2.71.0) — lissage LRGB rendu **OPT-IN** (case
  décochée par défaut) avec **σ du masque réglable** à CHAUD ; **test réel OK
  (M31)**, commité/poussé et **PUBLIÉ** (release GitHub v2.71.0).
- **10/10/2026** : jalon 117c (v2.70.0) — liseré rouge corrigé par un lissage
  **MASQUÉ** du ratio L/luma, test réel OK ; la case UI est le 117d.

