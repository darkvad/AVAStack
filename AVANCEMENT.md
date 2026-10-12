# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md. **Gardé LÉGER** : le changelog détaillé vit dans
`avastack/__init__.py` — ici, seul le DERNIER jalon reste détaillé, sa trace
étant dans le changelog du source et l'historique git.)

---

## PROCHAINE TÂCHE — 12/10/2026 : VALIDATION RÉELLE (M33, Alain)

**LES DEUX ARBITRAGES SONT LIVRÉS** : jalon 126 (**v2.78.0**) = bancs chroma 63/65
réparés ; jalon 127 (**v2.79.0**) = la CHROMA agit désormais pour les DEUX moteurs.
Bancs NEUFS + rejeu + garde-fou VERTS (détail à la « Session » ci-dessous).

### À faire, dans cet ordre
1. **À VALIDER EN RÉEL (Alain)** : relancer M33 — ① fond neutre attendu (le CŒUR reste
   magenta : hors périmètre, R/G 1,37 MESURÉ ; démagenta ÉCARTÉ — perte du vrai Hα) ;
   ② cocher GraXpert / débruitage **ET la chroma EN STF** : l'écran doit montrer le MÊME
   effet qu'en VeraLux, et le fichier « tel que vu » y correspondre.
2. Choisir la suite (cf. « En attente / prochaine session ») ; **PAS de release**
   (dernier tag publié = v2.71.1).

### Règles d'or (rappel)
Un jalon = un banc NEUF + rejeu des bancs concernés (TOUS VERTS, hors échecs
**préexistants** documentés) + garde-fou `_test_refactoring_garde_fou.py` VERT ;
commentaires en FRANÇAIS. Jamais l'état d'une case déduit de `config.json` : le
MESURER sur le fichier.

---

## Session du 12/10/2026 (10) — CLOSE — JALONS 126 & 127 (v2.78.0 · v2.79.0)

### État actuel
- **Jalon 126 (v2.78.0)** — BANCS CHROMA 63/65 RÉPARÉS (test-only, aucun code de
  production). Le « bug de prédicat » documenté n'était PAS la seule cause : **3
  réparations** (cf. Décisions). Bancs 63 ET 65 VERTS.
- **Jalon 127 (v2.79.0)** — LA CHROMA AGIT POUR LES DEUX MOTEURS : elle entre dans la
  chaîne PRÉ-ÉTIREMENT COMMUNE (`_vl_worker`, APRÈS la netteté) ; `process()` route par
  la chaîne dès que `vl_chroma` est actif ; la sauvegarde « tel que vu » n'est plus
  gardée par `stretch == "veralux"`. Sa case (visible dans « Fond et grain ») n'est donc
  plus inerte en STF. Banc NEUF VERT, rejeu + garde-fou VERTS. **PAS de release**
  (dernier tag publié = v2.71.1).

### Fichiers modifiés (jalon 127)
- `processing/display.py` : `_vl_worker` applique la chroma dans la chaîne COMMUNE (bloc RETIRÉ de la branche VeraLux) ; `process()` route si `vl_chroma` ; docstrings.
- `ui/saver.py` : gate chroma = `vue == "pile" and vl_chroma` (plus de `stretch == "veralux"`).
- `ui/app.py` : docstrings `_on_vl_chroma`/`_sync_vl_chroma_vue` (la vue « traitée » reste coupée : la chroma y vient de la chaîne EXTERNE ⚡).
- `bancs/_test_chaine_pre_etirement_jalon125.py` : [4] = la chroma ENTRE dans la sortie STF (image COULEUR, sinon no-op) ; `bancs/_test_chroma_stf_jalon127.py` (neuf).
- `avastack/__init__.py` (v2.79.0) + `CLAUDE.md` (section « chaîne pré-étirement »).

### Fichiers modifiés (jalon 126, test-only)
- `bancs/_test_chroma_nr_jalon63.py`, `bancs/_test_chroma_halo_jalon65.py`, `avastack/__init__.py` (v2.78.0).

### Mesures / faits vérifiés (rejouables)
- Banc jalon 127 (NEUF) : VERT — [1] STF : sortie de chaîne = chroma(entrée) ; [2] STF : `process()` route (le rendu CHANGE quand la case est cochée) ; [3] sauvegarde : chroma appliquée sans gate moteur ; [4] VeraLux : chroma PUIS étirement (inchangé) ; [5] chroma ET moteur dans la clé.
- Banc jalon 125 [4] MAJ : la chroma ENTRE dans la sortie STF (image COULEUR — sur du MONO la chroma est un NO-OP).
- Bancs 63/65 : VERTS (jalon 126) — voir « Décisions » (3 causes).
- Rejeu VERTS (jalon 127) : veralux 2/3, graxpert_live 4, dn 7/8, sharp_live 12, couleurs 22, couleurs_immediat 39, etat_calcul 40, ui_moteur 41, ui_visibilite 47, save_brute 59, chroma_structure 67, zoom_pleine_res 68, pleine_res_traitee 69, histo 75, gx_parallele 81, piedestal 122, neutralisation 123, exclusivite 124, chaine_pre_etirement 125, chroma_stf 127.
- Échec **PRÉEXISTANT** restant : `_test_espace_jalon72` (géométrie d'écran — dépend de la machine).
- Garde-fou : syntaxe 259, surface **75**, hash au bit, pyright **0/50** — VERT.

### Décisions prises
- **Arbitrage 1 (Alain) — RÉPARER les bancs 63/65** : 3 causes, pas une seule. ① PRÉDICAT : `_vl_result[0]` (clé+forme) comparé à `_vl_params()` SEUL (clé sans forme, depuis la v2.55.3) → TOUJOURS faux ; réparé en `+ (img.shape,)`. ② MOTEUR (hérité du jalon 125) : `_process_chaine` branche sur le moteur → ces bancs (qui mesurent le solveur VeraLux) posent `stretch = "veralux"`. ③ halo 65 [6] : rayon posé AVANT `_on_vl_chroma` (un job en cours n'est pas remplacé, `_vl_pending`) + assertion « deux chemins » adaptée à l'extraction de l'acquisition (`App` + `core/worker.AcquisitionWorker`).
- **Arbitrage 2 (Alain) — OUVRIR la chroma aux DEUX moteurs** (et non la masquer en STF) : elle entre dans la chaîne COMMUNE ; écran ET fichier ; contrat jalon 59 inchangé (pas de chroma dans la sortie LINÉAIRE).

### Prochaines étapes
- **VALIDATION RÉELLE (Alain)** : M33 — ① fond neutre attendu ; ② GraXpert / débruitage / CHROMA cochés **EN STF** → écran == fichier.
- **COMMITTÉS, PAS ENCORE POUSSÉS** : jalon 126 = `400ba7c` ; jalon 127 = `3f9b4d9`
  (soit 2 commits d'avance sur `origin/master`) — `git push` quand Alain le décide.
  **PAS de release** (dernier tag publié = v2.71.1).
- **À ARBITRER (Alain)** : le jalon 126 étant TEST-ONLY, faut-il garder son bump de version
  v2.78.0 (convention « 1 jalon = 1 version ») ou le fondre dans le jalon 127 ?

### Points d'attention
- **La chroma est un NO-OP sur une image MONOCHROME** (Cr/Cb nuls) : tout banc qui la teste doit utiliser une image COULEUR (leçon du banc 125 [4]).
- **`_vl_params()` ARRONDIT** `vl_chroma_rayon` à 2 décimales, mais le JOB porte la valeur NON arrondie : une clé peut « matcher » un résultat calculé avec un rayon légèrement différent (piège vu au banc 65).
- Le worker ne touche JAMAIS aux stats EMA du STF ; en STF/manuel il publie l'image PRÉ-ÉTIRÉE (chroma incluse) et `process()` étire.
- La vue « traitée » reste coupée pour la chroma (elle y vient de la chaîne EXTERNE ⚡) ; la 3e sortie LINÉAIRE ne la contient jamais.
- Ne JAMAIS remettre les cases GraXpert/débruitage dans `frm_veralux` (masquées en STF → actives à la sauvegarde).

### Historique — jalon 125 (v2.77.0), 12/10/2026
- VOLET A : chaîne pré-étirement UNIQUE (GraXpert → débruitage → netteté à l'écran POUR
  LES DEUX moteurs) ; cases sorties du cadre VeraLux ; solveur de netteté dédié supprimé.
  Trace : changelog v2.77.0 ; commit `e185ffc`.

---

## Problèmes ouverts HORS session (hérités des jalons 116-118, toujours valides)
- L'**aligneur n'écrit RIEN** au journal (`%APPDATA%\AVAStack\journal.txt`) ;
  l'alternative « paires d'invariants top-60 × top-120 » du solveur reste non mesurée.

---

## Chantier CLOS — chaîne de sortie : gradient & débruitage pour TOUS les moteurs

- **Demande d'Alain (11/10/2026)** : « je ne comprends pas pourquoi on ne pourrait
  pas mettre le retrait de gradient et la suppression de bruit pour STF aussi. »
- **DÉCISION D'ALAIN (11/10/2026)** : l'incohérence fichier ↔ écran (GraXpert +
  débruitage appliqués par la SAUVEGARDE mais pas par l'écran en STF) se corrige
  **CÔTÉ ÉCRAN** — on GARDE la sauvegarde et on fait tourner GraXpert + débruitage AUSSI
  à l'écran en STF/manuel (« le fichier = l'écran »).
- **VOLET A = FAIT (jalon 125, v2.77.0)** : option « refonte » RETENUE par Alain le
  12/10 — `_vl_worker` devient LA chaîne pré-étirement UNIQUE (GraXpert → débruitage →
  netteté) ; seule la DERNIÈRE étape dépend du moteur (le MOTEUR entre dans `_vl_params`).
  Cases GraXpert/débruitage sorties du cadre VeraLux → « Chaîne avant étirement »
  (visible dans les DEUX modes) ; solveur de netteté DÉDIÉ supprimé. Détail : changelog
  v2.77.0.
- **VOLET B = FAIT** (jalons 122 + 123, v2.74.0 + v2.75.0) : le magenta venait de
  `neutraliser_fond` AVANT l'étirement — remède LIVRÉ.
- **Reste à TRANCHER (Alain)** : la **CHROMA** — réservée à VeraLux (écran ET fichier),
  sa case est visible dans « Fond et grain » mais n'agit PAS en STF. L'ouvrir aux deux
  moteurs, ou la masquer en STF ?
- **Règles d'or** (rappel) : voir PROCHAINE TÂCHE. On ne réécrit JAMAIS un tag publié ;
  version + changelog + AVANCEMENT.md dans la même réponse.

---
## Chantier CLOS — (1) BUG de restauration · (2) FICHE DE RENDU

- **(1) FAIT (jalon 120, v2.72.1)** : `App._curseurs` + `App._poser_curseur` (chemin d'un
  geste) ; les 10 sites de `_restaurer_config` routés ; règle dans CLAUDE.md.
- **(2) FAIT (jalon 121, v2.73.0)** : `avastack/fiche.py` (JSON compagnon
  `<image>.ava.json`, atomique + tolérant), case « Fiche de rendu » (panneau Sortie, cochée
  par défaut), écriture aux **5** sorties, état APPLIQUÉ vs AFFICHÉ. **4 décisions d'Alain
  VALIDÉES le 11/10/2026** : ① `<image>.ava.json` à côté de l'image ; ② case cochée par
  défaut ; ③ chemins COMPLETS (les exemples de doc publique restent neutres — dépôt PUBLIC) ;
  ④ écrite pour TOUTES les sorties. Détail : changelog v2.73.0 ; règles durables dans CLAUDE.md.

---
## En attente / prochaine session

- **LIVRÉ AUX JALONS 126/127** : bancs chroma 63/65 réparés ; la CHROMA agit désormais
  pour les DEUX moteurs (chaîne pré-étirement COMMUNE, écran ET fichier). GraXpert +
  débruitage : déjà livrés au jalon 125. Reste à **VALIDER EN RÉEL**.
- **À VALIDER EN RÉEL (Alain)** : relancer M33 — fond neutre attendu ; le CŒUR restera
  magenta (hors périmètre). Démagenta ÉCARTÉ (perte du vrai Hα). Cocher GraXpert /
  débruitage / chroma **EN STF**.
- **Contrôle simple au passage** : re-mesurer les 2 FITS du 11/10 → les pixels à CANAL NUL
  (S = 1, fabriqués par le bug de restauration, corrigé au jalon 120) doivent avoir disparu.
- **Jalons 119 à 127** : committés (`cd3a312`, `b8ec81f`, `e185ffc`, `400ba7c`, `3f9b4d9`) ;
  **2 commits d'avance sur `origin/master`** (pas encore poussés) ; **release NON faite**
  (dernier tag publié = **v2.71.1**).
- **À VÉRIFIER EN RÉEL** : l'installateur `.exe` corrigé (l'application démarre après
  installation) — c'est LE test qui manquait et qui a révélé le défaut (jalon 118).
- **Microsoft Store** : cadence SÉPARÉE — l'appli PUBLIÉE y reste la **v2.50.0** ; le
  **MSIX v2.71.1 est CONSTRUIT ET SIGNÉ** (prêt à resoumettre, cf. `SOUMISSION.md` §1/§7) ;
  reste le test « installer depuis le Store » (seule voie pour ce test).
- **Boutons de données SANS Siril** (« ⬇ Gaia », « ⬇ Spectres (champ) », « ⬇ Base SPCC ») —
  délégués à un utilisateur sans Siril.
- **Piste INDI** (un seul chemin pour les 3 OS et toutes les marques) — jalon à part, PAS
  avant le portage Linux avec les `.so`.

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
  chroma) — les EXCLURE avant de mesurer. `_test_chroma_nr_jalon63.py` échoue en [5]/[6]
  de façon **PRÉEXISTANTE** (solveur VeraLux non publié ici ; rejoué avec le code d'origine).
- **`config.json` NE DIT PAS LA RÉALITÉ** : c'est l'état à la DERNIÈRE FERMETURE
  (chez Alain : 13h59 le 11/10), pas celui du moment où un fichier est écrit. On ne
  l'utilise donc JAMAIS pour affirmer l'état d'un réglage ni pour expliquer un écart :
  **on MESURE le fichier produit** (ou on AFFICHE l'état réellement appliqué — c'est
  le chantier « fiche de rendu » ci-dessus).
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

- **12/10/2026** : jalon 127 (v2.79.0) — la CHROMA agit pour les DEUX moteurs (chaîne
  pré-étirement commune, écran + fichier ; sa case n'est plus inerte en STF) ; banc neuf +
  rejeu + garde-fou VERTS ; **commité**, pas de release.
- **12/10/2026** : jalon 126 (v2.78.0) — bancs chroma 63/65 réparés (test-only : prédicat,
  moteur, course du rayon, assertion « deux chemins ») ; **commité** (`400ba7c`).

