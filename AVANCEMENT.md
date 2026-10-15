# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md. **Gardé LÉGER** : le changelog détaillé vit dans
`avastack/__init__.py` — ici, seul le DERNIER jalon reste détaillé, sa trace
étant dans le changelog du source et l'historique git.)

---

## ⚠️ BRANCHE DE DÉVELOPPEMENT ACTIVE — NE PAS SUPPRIMER JUSQU'À DEMANDE EXPLICITE

**Branche : `LRGBHa`** (créée le 15/10/2026 à partir de `master`)

> **RÈGLE FERME — GRAVÉE DANS LE MARBRE** : Jusqu'à nouvel ordre explicite de l'utilisateur,
> **TOUTE** nouvelle fonctionnalité, **TOUT** développement, **TOUTE** modification de code
> se fait **EXCLUSIVEMENT** sur la branche `LRGBHa`.
>
> La branche `master` ne doit **JAMAIS** être touchée directement pour de nouvelles
> fonctionnalités.
>
> - `master` = branche stable, releases uniquement
> - `LRGBHa` = branche de développement, nouvelles fonctionnalités (SEULE branche autorisée)
> - Merge vers `master` = seulement sur validation explicite (release)

---

## Session du 12/10/2026 (11) — JALON 128 (v2.80.0) : image VeraLux gardée pendant un recalcul

**SESSION CLOSE** — jalon 128 livré, commité, poussé ; **release GitHub v2.80.0 PUBLIÉE**
(4 installateurs + `INSTALLATION.md`). Il ne reste AUCUNE action technique en attente.
Prochaine tâche à définir (pistes en « En attente / prochaine session »).

### État actuel
- **Jalon 128 (v2.80.0)** — en étirement VeraLux, un NOUVEAU calcul ne fait plus
  « sauter » l'écran vers l'aperçu STF : `_process_chaine` CONSERVE le dernier résultat
  VeraLux TERMINÉ jusqu'à ce que le recalcul aboutisse ; l'UI superpose « Recalculs en
  cours » (arc tournant, fond transparent, coin haut-gauche) tant que le calcul tourne.
- Vérifié par banc NEUF (8 volets) + rejeu des bancs concernés ; garde-fou VERT.

### Fichiers modifiés
- `processing/display.py` : `_vl_result_moteur` (moteur du dernier résultat, publié par
  `_vl_worker`), `_process_chaine` (conservation gardée par moteur + forme + `_vl_pending`).
- `ui/renderer.py` : `_render` (appel overlay + décalage du texte de zoom),
  `_spinner_vl_actif`, `_dessiner_spinner_vl` (item canvas tag « vl_spin »).
- `ui/app.py` : `_maj_lbl_vl` (anime l'arc), `_vl_spin_angle` (initialisé dans `__init__`).
- `bancs/_test_conservation_veralux_jalon128.py` (neuf) · `avastack/__init__.py` (version+changelog).

### Mesures / faits vérifiés (rejouables)
- Banc NEUF 128 VERT : [0] moteur publié (« veralux »/« stf ») ; [1] conservation VeraLux
  (identité d'objet, ≠ repli STF) ; [2] garde-fou moteur ; [3] garde-fou forme ; [4] hors
  calcul → repli STF ; [5] `process()` IDENTIQUE avant/pendant ; [6] overlay UI ; [7] arc
  qui tourne (30°→60°) puis retiré en fin.
- Rejeu VERTS : veralux 2/3, etat_calcul 40, ui_moteur 41, chaine_pre_etirement 125,
  chroma_stf 127, zoom_pleine_res 68. Garde-fou : syntaxe 260, surface 75, hash au bit,
  pyright 0/50 — VERT.

### Décisions prises
- **Conservation gardée par le MOTEUR du résultat** : seul un résultat RÉELLEMENT étiré
  par VeraLux est conservé (sinon, après STF→VeraLux, on garderait l'image PRÉ-ÉTIRÉE
  linéaire = image sombre). Nouvel attribut `_vl_result_moteur` plutôt que relire la clé
  (dont la position du moteur est un détail interne).
- **Conservation gardée par la FORME** : un basculement aperçu↔pleine résolution retombe
  sur le repli STF (pas d'image périmée de mauvaise taille).
- **Overlay réservé à VeraLux** : en STF/manuel le worker tourne aussi mais l'étirement
  est instantané → aucun overlay (l'indicateur ne ment pas sur un « calcul »).

### Prochaines étapes
- Prochaine tâche à définir (pistes en « En attente ») ; côté **Store**, soumettre une
  version plus récente quand ce sera décidé (cadence séparée).

### Points d'attention
- Le worker publie `_vl_result_moteur` SOUS LE MÊME VERROU que `_vl_result` (jamais l'un
  sans l'autre : un désaccord afficherait une mauvaise image).
- `_vl_spin_angle` est DÉCLARÉ sur `Renderer` (typage) mais INITIALISÉ dans `App.__init__` ;
  les accès passent par `getattr(..., 0.0)` (robuste si un banc construit l'App autrement).
- L'overlay est un item CANVAS (jamais baké dans l'image) : `_last_disp` reste propre pour
  l'annotation et la sauvegarde.

### Règles d'or (rappel)
Un jalon = un banc NEUF + rejeu des bancs concernés (TOUS VERTS, hors échecs
**préexistants** documentés) + garde-fou `_test_refactoring_garde_fou.py` VERT ;
commentaires en FRANÇAIS. Jamais l'état d'une case déduit de `config.json` : le
MESURER sur le fichier.

---

## Historiques (trace détaillée : `avastack/__init__.py` + git log)

- **12/10/2026 — jalons 126+127 (v2.79.0)** : chroma ouverte AUX DEUX moteurs (écran ET
  fichier ; la 3e sortie LINÉAIRE ne la contient toujours pas), bancs chroma 63/65 réparés ;
  validé M33 ; `.exe` + Store (MSIX v2.71.1) + canal nul OK ; poussé.
- **12/10/2026 — jalon 125 (v2.77.0)** : chaîne pré-étirement UNIQUE (GraXpert + débruitage
  à l'écran pour les DEUX moteurs) ; poussé (`e185ffc`).

---

## Problèmes ouverts HORS session (hérités des jalons 116-118, toujours valides)
- L'**aligneur n'écrit RIEN** au journal (`%APPDATA%\AVAStack\journal.txt`) ;
  l'alternative « paires d'invariants top-60 × top-120 » du solveur reste non mesurée.

---

## En attente / prochaine session

- **Jalon 128 (v2.80.0) — À VALIDER EN RÉEL** : pendant un recalcul VeraLux, l'image
  VeraLux RESTE à l'écran (plus de saut vers le STF) + « Recalculs en cours » (arc
  tournant, fond transparent, haut-gauche). Alain : en live stacking VeraLux, bouger un
  curseur / cocher une case → l'image doit rester VeraLux, l'arc tourner, puis disparaître
  au résultat.
- **Livré et validé (v2.79.0)** : GraXpert + débruitage (125), chroma des DEUX moteurs (127),
  bancs 63/65 (126) — validé M33 ; 3 vérifs du 12/10 (`.exe`, **Store MSIX v2.71.1**, canal
  nul) OK.
- **Boutons de données SANS Siril** (« ⬇ Gaia », « ⬇ Spectres (champ) », « ⬇ Base SPCC ») —
  délégués à un utilisateur sans Siril.
- **Piste INDI** (un seul chemin pour les 3 OS et toutes les marques) — jalon à part, PAS
  avant le portage Linux avec les `.so`.
- **Release GitHub** : **v2.80.0 PUBLIÉE le 12/10/2026** (tag `v2.80.0` sur le commit de
  doc `92919f9`) — `.exe` + ZIP Windows + Linux + macOS + `INSTALLATION.md` attachés.
  Côté **Store**, la version publiée reste **v2.71.1** (cadence séparée).

---

## Setup d'Alain

- **Setup 1 (miniPC)** : QHY MiniCam8M (mono refroidie, roue intégrée, alim. 12 V) ;
  N.I.N.A. → `TargetSchedulerSequence/<cible>/<expo>/LIGHT` — un dossier peut MÉLANGER
  plusieurs nuits (la 1re frame par mtime n'est pas forcément de la nuit courante).
- **Setup 2** : C8 défourché + réducteur 0,63 → 1280 mm ; Player One Uranus-C Pro
  (couleur, IMX585, 3856×2180, RGGB, gain unitaire 210, TEC) sur monture DIY **Open
  Astro Mount** ; guidage SVBONY SV305C sur lunette 60/240. Constat 17/09/2026 à
  1280 mm : étoiles « en plusieurs points puis en trainées » → origine du jalon 13
  (alignement robuste). Banc POA : `_diag_camera_playerone.py` (jalon 28).
- **Jeux de test (QHY MiniCam8M + SV555)** : M31 (09/10) = L du 13/09 + R/G/B du
  22-23/09, ~50-60 frames/filtre, 60 s, −15 °C (⚠ un dossier de filtre peut MÊLER les
  deux côtés du Pier : 26 % des frames RGB à 176°) ; M33 (nuit du 10-11/10) = L 60×60s ·
  R 20×60s · G 20×60s · B 17×120s → 2,2 h, recadré 3747×1983 (master dark 60 s pour
  L/R/G, 120 s pour B).
- **Outils astro locaux vérifiés (22/09/2026)** : Siril 1.4.4 (catalogues Gaia XP dans
  `%LOCALAPPDATA%\Siril\...`, base SPCC dans `siril-spcc-database`) ; ASTAP
  (`C:\Program Files\astap`, base D80 Gaia DR3 1,24 Go) ; PAS d'astrometry.net/ANSVR.
- **Machine LINUX d'Alain (fait du 29/09/2026)** : **Ubuntu 26.04 LTS** — installateur
  Linux exécuté PLUSIEURS fois (installation, prérequis, venv, dépendances, lancement) ;
  astrométrie, SPCC et GraXpert y sont validés. Restent : machine **VIERGE** (sans
  Python) et **test matériel caméras** (`--cameras`).

---

## Pièges récents (encore actifs)

- **Pixels à CANAL NUL (S = 1)** — fabriqués par le bug de restauration (CORRIGÉ au
  jalon 120) : ils POLLUENT toute statistique de couleur (« % de taches », bruit de
  chroma) — les EXCLURE avant de mesurer.
- **La CHROMA est un NO-OP sur une image MONOCHROME** (Cr/Cb nuls) : tout banc qui la
  teste doit utiliser une image COULEUR (leçon du banc 125 [4]).
- **`config.json` NE DIT PAS LA RÉALITÉ** : c'est l'état à la DERNIÈRE FERMETURE
  (chez Alain : 13h59 le 11/10), pas celui du moment où un fichier est écrit. On ne
  l'utilise donc JAMAIS pour affirmer l'état d'un réglage ni pour expliquer un écart :
  **on MESURE le fichier produit** (ou on AFFICHE l'état réellement appliqué — fiche
  de rendu, jalons 121/123).
- **VERALUX AMPLIFIE LE FOND (MESURÉ)** : son ANCRE (scalaire lu dans l'histogramme de
  luminance) consomme **~97 % du niveau de ciel** → tout écart de fond par canal sort
  **×20 à ×40** ; un fond d'empilement neutre à 0,9 % ressort à R/G 0,77, et la moindre
  correction par canal décide de la couleur (cyan ↔ magenta). Le STF amplifie aussi mais
  identique aux 3 canaux : il ne peut pas fabriquer de dominante.
- **La NEUTRALISATION du fond (APRÈS l'étirement depuis le jalon 123 ; JUSTE AVANT
  gamma/saturation depuis le jalon 124) est RÉSERVÉE à VeraLux ; `reduire_bruit_chroma`
  est, elle, COMMUNE aux deux moteurs depuis le jalon 127. Les DEUX sont EXCLUES de la
  sortie linéaire traitée** (verrouillé, banc jalon 59 [6]) : un FITS linéaire ne les
  contient JAMAIS — ce n'est pas un bug. La neutralisation n'est PAS dans le solveur :
  `process()` / `rendu_pleine_resolution` l'appliquent (le 9e élément `nf` du job reste
  transporté mais IGNORÉ).
- **JOB EXTERNE = 11 éléments** (jalon 123 : la neutralisation du fond en est SORTIE ;
  chroma = 8, force = 9, rayon = 10). Le « 12e élément » des anciens commentaires/bancs
  n'existe plus : un job plus court est lu TOLÉRANT (indices manquants → inactifs). Clé
  `ext_neutre_fond` plus écrite ni relue.
- **`_vl_params()` N'INCLUT PAS LA FORME** : le solveur indexe son cache par
  `_vl_params() + (img.shape,)`. Un prédicat qui compare `_vl_result[0]` à `_vl_params()`
  SEUL est donc TOUJOURS faux (« solveur jamais publié ») — cause des échecs PRÉEXISTANTS de
  `couleurs_immediat_jalon39` (réparé au 124), `chroma_nr_jalon63` [5]/[6] et
  `chroma_halo_jalon65` [6] (TOUS réparés au jalon 126). À retenir pour tout NOUVEAU banc.
- **`_vl_params()` ARRONDIT `vl_chroma_rayon` à 2 décimales** alors que le JOB porte la
  valeur NON arrondie : une clé peut « matcher » un résultat calculé à un rayon voisin.
- **`_test_espace_jalon72` échoue en GÉOMÉTRIE D'ÉCRAN** (« aucun bouton écrasé » +
  « rogné/débordé ») : échec **PRÉEXISTANT** (reproduit à l'IDENTIQUE sur le HEAD du jalon
  120 via `git worktree`) — dépend de la taille d'écran de la machine, PAS du code.
- **La case chroma est IGNORÉE en vue « traitée »** (voulu : `_sync_vl_chroma_vue` la
  coupe, le résultat ⚡ la porte déjà ; depuis le jalon 127 elle vaut pour les DEUX moteurs
  en vue « empilement »). Conséquence PRATIQUE : un enregistrement fait depuis la vue
  « traitée » ne reçoit PAS la chroma de l'écran — vérifier la vue AVANT d'accuser le code.
- **`_fmt_expo` est DÉJÀ PRIS dans `app.py`** (jalon 119) : ce nom est importé de
  `ui/panels/camera.py`. Un `def _fmt_expo(...)` au niveau module de `app.py` l'ÉCRASE et
  casse le panneau Caméra (banc `cameras/_test_expo_affichage_jalon34.py`).
- **PIÈGE LANCEMENT** : `python3` ≠ venv — toujours `python AVAStack.py`.
- **Ordre de la chaîne** (Alain, 16/09/2026) : recadrage → gradient → débruitage →
  netteté → étirement. Débruitage : code gelé, cases décochées (16/09/2026).
- **Tk** : ne JAMAIS mélanger `grid` et `pack` dans le même conteneur (`TclError`).
- **OpenCV/OpenCL** : crash au teardown → `cv2.ocl.setUseOpenCL(False)`. Tests `ui.App`
  hermétiques : `ui.CONFIG = {}` + `sauver_config` intercepté.
- **SDK natif caméras** : chargement UNE fois par process ; crash natif non rattrapable →
  tracer chaque étape dans un fichier et vérifier l'identité des fichiers réellement
  chargés AVANT d'interpréter un plantage. **Installateur d'un OS non exécutable**
  (macOS/Linux) : se vérifie par ce qui EST vérifiable (`bash -n`, refus hors OS, banc de
  contenu) ; état écrit DATÉ, jamais déguisé en test réussi.
- **ALIGNEUR & RECADRAGE (jalons 116/117)** : détails dans CLAUDE.md. À retenir : une
  frame d'une AUTRE NUIT/filtre se normalise sur ses PROPRES bornes ; une brute CALIBRÉE
  (dark) peut être refusée là où la non calibrée passe ; `cadre_intersection` rend le plus
  grand rectangle AXIAL INSCRIT — contrôler le polygone AVANT d'accuser l'optique.

---

## Clôtures précédentes

- **12/10/2026** : jalon 127 (v2.79.0, incl. 126) — CHROMA pour les DEUX moteurs + bancs
  63/65 réparés ; validé M33 ; **.exe + Store (MSIX v2.71.1) + canal nul** TOUS OK ; poussé.
- **12/10/2026** : jalon 125 (v2.77.0) — chaîne pré-étirement UNIQUE (GraXpert + débruitage
  à l'écran pour les DEUX moteurs) ; **poussé** (`e185ffc`).

