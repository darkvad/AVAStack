# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md. **Gardé LÉGER** : le changelog détaillé vit dans
`avastack/__init__.py` — ici, seul le DERNIER jalon reste détaillé, sa trace
étant dans le changelog du source et l'historique git.)

---

## PROCHAINE TÂCHE — à définir par Alain (SESSION CLOSE)

**SESSION DU 12/10/2026 CLOSE — v2.79.0 validée + les 3 vérifications réelles faites** :
installeur `.exe` OK ; Store : MSIX **v2.71.1 soumis, accepté, publié, testé OK** ;
contrôle « pixels à canal nul » sur les FITS du 11/10 → **0** (cf. « Session »).
Jalons 119→127 **poussés** sur `origin/master` ; **pas de release GitHub** (dernier
tag = v2.71.1). **Rien d'ouvert côté code → la prochaine tâche reste à choisir**
(pistes en « En attente / prochaine session »).

### Règles d'or (rappel)
Un jalon = un banc NEUF + rejeu des bancs concernés (TOUS VERTS, hors échecs
**préexistants** documentés) + garde-fou `_test_refactoring_garde_fou.py` VERT ;
commentaires en FRANÇAIS. Jamais l'état d'une case déduit de `config.json` : le
MESURER sur le fichier.

---

## Session du 12/10/2026 (10) — CLOSE — JALONS 126+127 FONDUS (v2.79.0) + 3 VÉRIFS

### État actuel
- **Jalon 126 (FONDU dans la v2.79.0)** — bancs chroma 63/65 RÉPARÉS (test-only, aucun
  code de production) : 3 causes (prédicat, moteur, course du rayon + assertion « deux
  chemins »).
- **Jalon 127 (v2.79.0)** — la CHROMA agit pour les DEUX moteurs : elle entre dans la
  chaîne PRÉ-ÉTIREMENT COMMUNE (`_vl_worker`, APRÈS la netteté) ; `process()` route dès
  que `vl_chroma` est actif ; la sauvegarde « tel que vu » n'est plus gardée par
  `stretch == "veralux"`. Sa case (« Fond et grain ») n'est plus inerte en STF.

### Fichiers modifiés
- `processing/display.py` (`_vl_worker`, `process()`) · `ui/saver.py` (gate chroma) ·
  `ui/app.py` (docstrings) · `bancs/_test_chroma_stf_jalon127.py` (neuf) ·
  `bancs/_test_chroma_nr_jalon63.py` · `bancs/_test_chroma_halo_jalon65.py` ·
  `bancs/_test_chaine_pre_etirement_jalon125.py` [4] · `avastack/__init__.py` · `CLAUDE.md`.

### Mesures / faits vérifiés (rejouables)
- Banc NEUF jalon 127 : VERT — [1] sortie de chaîne STF = chroma(entrée) ; [2] `process()`
  route (rendu CHANGE quand la case est cochée) ; [3] sauvegarde sans gate moteur ;
  [4] VeraLux : chroma PUIS étirement ; [5] chroma ET moteur dans la clé.
- Banc jalon 125 [4] MAJ : la chroma ENTRE dans la sortie STF (image COULEUR — sur du MONO
  la chroma est un NO-OP).
- Bancs 63/65 : VERTS (jalon 126). Rejeu VERTS (jalon 127) : veralux 2/3, graxpert_live 4,
  dn 7/8, sharp_live 12, couleurs 22, couleurs_immediat 39, etat_calcul 40, ui_moteur 41,
  ui_visibilite 47, save_brute 59, chroma_structure 67, zoom_pleine_res 68,
  pleine_res_traitee 69, histo 75, gx_parallele 81, piedestal 122, neutralisation 123,
  exclusivite 124, chaine_pre_etirement 125, chroma_stf 127.
- Échec **PRÉEXISTANT** restant : `_test_espace_jalon72` (géométrie d'écran — machine).
- Garde-fou : syntaxe 259, surface 75, hash au bit, pyright 0/50 — VERT.

### Décisions prises
- **Arbitrage 1 (Alain) — RÉPARER les bancs 63/65** (3 causes) : ① `_vl_result[0]` (clé +
  forme) comparé à `_vl_params()` SEUL → TOUJOURS faux ; réparé en `+ (img.shape,)` ;
  ② MOTEUR : ces bancs posent `stretch = "veralux"` ; ③ halo 65 [6] : rayon posé AVANT
  `_on_vl_chroma`, assertion adaptée à `core/worker.AcquisitionWorker`.
- **Arbitrage 2 (Alain) — OUVRIR la chroma aux DEUX moteurs** (pas la masquer) : chaîne
  COMMUNE ; écran ET fichier ; contrat jalon 59 inchangé (pas de chroma dans la sortie
  LINÉAIRE).
- **Arbitrage 3 (Alain) — jalon 126 FONDU dans la v2.79.0** : pas de version v2.78.0 à part.

### Vérifications réelles (Alain, 12/10/2026)
- ① **Installeur `.exe`** (jalon 118) : vérifié, testé, **OK** (démarre après installation).
- ② **Microsoft Store** : MSIX **v2.71.1 soumis, accepté, PUBLIÉ, testé OK**.
- ③ **Contrôle « pixels à canal nul »** (canal échu à 0) sur les FITS du 11/10 au dossier
  `C:\Astro\test` : la paire A/B chroma (`M33_AB_chroma_DECOCHEE`/`COCHEE`) et
  `M33_AA_controle_1/2` → **0** ; **veralux** post-correctif (12/10) → **0** (contre
  **963 430** AVANT correctif le 11/10 17:47). Le **STF** « tel que vu » garde des canaux
  à 0 (~527 k sur l'image 12/10) — **clippage LÉGITIME du moteur STF**, sans rapport avec
  le bug `sat_b = 3,0` (jalon 120). Mesure faite hors dépôt (script jetable).

### Points d'attention
- Ne JAMAIS remettre les cases GraXpert/débruitage dans `frm_veralux` (masquées en STF →
  actives à la sauvegarde).
- Le worker ne touche JAMAIS aux stats EMA du STF ; en STF/manuel il publie l'image
  PRÉ-ÉTIRÉE (chroma incluse) et `process()` étire.
- La vue « traitée » reste coupée pour la chroma (elle y vient de la chaîne EXTERNE ⚡) ;
  la 3e sortie LINÉAIRE ne la contient jamais.

### Historique — jalon 125 (v2.77.0)
- Chaîne pré-étirement UNIQUE (GraXpert → débruitage → netteté à l'écran pour les DEUX
  moteurs). Trace : changelog v2.77.0 ; commit `e185ffc`.

---

## Problèmes ouverts HORS session (hérités des jalons 116-118, toujours valides)
- L'**aligneur n'écrit RIEN** au journal (`%APPDATA%\AVAStack\journal.txt`) ;
  l'alternative « paires d'invariants top-60 × top-120 » du solveur reste non mesurée.

---

## En attente / prochaine session

- **LIVRÉ ET VALIDÉ (v2.79.0)** : GraXpert + débruitage (jalon 125), chroma pour les DEUX
  moteurs (jalon 127), bancs chroma 63/65 réparés (jalon 126) — **validé en réel (M33)** ;
  plus les 3 vérifs réelles du 12/10 (`.exe`, **Store MSIX v2.71.1 publié**, canal nul) : OK.
- **Boutons de données SANS Siril** (« ⬇ Gaia », « ⬇ Spectres (champ) », « ⬇ Base SPCC ») —
  délégués à un utilisateur sans Siril.
- **Piste INDI** (un seul chemin pour les 3 OS et toutes les marques) — jalon à part, PAS
  avant le portage Linux avec les `.so`.
- **Release GitHub** : NON faite (dernier tag publié = **v2.71.1**) ; jalons 119→127 poussés
  sur `origin/master`. Côté **Store**, la version publiée est désormais **v2.71.1**.

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

