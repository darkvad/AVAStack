# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md. **Gardé LÉGER** : le changelog détaillé vit dans
`avastack/__init__.py` — ici, seul le DERNIER jalon reste détaillé, sa trace
étant dans le changelog du source et l'historique git.)

---

## PROCHAINE TÂCHE — 12/10/2026 : VALIDATION RÉELLE (M33) + arbitrage bug 63/65

**VOLET A (chaîne de sortie) : CODÉ et LIVRÉ** au jalon 125 (**v2.77.0**) — banc NEUF
VERT, rejeu et garde-fou VERTS (détail à la « Session » ci-dessous).

### À faire, dans cet ordre
1. **À VALIDER EN RÉEL (Alain)** : relancer M33 — ① fond neutre attendu (le CŒUR reste
   magenta : hors périmètre, R/G 1,37 MESURÉ ; démagenta ÉCARTÉ — perte du vrai Hα) ;
   ② cocher GraXpert et/ou débruitage **EN STF** : l'écran doit montrer le MÊME effet
   qu'en VeraLux, et le fichier « tel que vu » y correspondre.
2. **BUG PRÉEXISTANT À ARBITRER (Alain)** : `chroma_nr_jalon63` [5]/[6] et
   `chroma_halo_jalon65` [6] portent le **MÊME bug de prédicat** que
   `couleurs_immediat_jalon39` (`_vl_result[0]` = clé+forme comparée à `_vl_params()`
   SEUL, sans forme, depuis la v2.55.3 → prédicat TOUJOURS faux). **1 ligne chacun**,
   NON réparés (hors périmètre). **Alain décide** s'il veut que je les répare.
3. **CHROMA en STF (piste)** : sa case (visible dans « Fond et grain ») n'agit PAS en
   STF (réservée VeraLux, écran ET fichier) — à TRANCHER : l'ouvrir aux deux moteurs
   comme GraXpert/débruitage, ou la masquer en STF (aujourd'hui : visible mais inerte).

### Règles d'or (rappel)
Un jalon = un banc NEUF + rejeu des bancs concernés (TOUS VERTS, hors échecs
**préexistants** documentés) + garde-fou `_test_refactoring_garde_fou.py` VERT ;
commentaires en FRANÇAIS. Jamais l'état d'une case déduit de `config.json` : le
MESURER sur le fichier.

---

## Session du 12/10/2026 (9) — JALON 125 (v2.77.0) : VOLET A — CHAÎNE PRÉ-ÉTIREMENT UNIQUE

### État actuel
- **Livré (VOLET A)** : GraXpert + débruitage tournent à l'écran AUSSI en STF/manuel
  (décision d'Alain du 11/10 : « le fichier = l'écran »). `_vl_worker` est LA chaîne
  pré-étirement UNIQUE (GraXpert → débruitage → netteté) ; seule la DERNIÈRE étape
  (l'étirement) dépend du moteur, qui entre donc dans `_vl_params`. Le solveur de netteté
  DÉDIÉ est SUPPRIMÉ. Cases GraXpert/débruitage SORTIES du cadre VeraLux →
  « Chaîne avant étirement ». Version **2.77.0**, changelog + CLAUDE.md à jour ; banc
  NEUF VERT ; rejeu + garde-fou VERTS. **PAS de release** (dernier tag publié = v2.71.1).

### Fichiers modifiés
- `processing/display.py` : `_vl_worker` = chaîne COMMUNE (branche par moteur : STF publie l'image PRÉ-ÉTIRÉE, VeraLux l'image étirée) ; `_process_chaine` (ex-`_process_veralux`, moteur dans la clé ET le job) ; `process()` route LES DEUX moteurs par la chaîne ; SUPPRESSION de `_sh_worker`/`_process_nettete`/`_sh_key`/`_sh_*` ; `sh_en_cours()` → False ; image d'attente STF = LINÉAIRE (sinon double étirement).
- `ui/panels/sharp.py` : cases GraXpert + débruitage AJOUTÉES ; le panneau devient « Chaîne avant étirement » (`frm_sharp`).
- `ui/panels/display.py` : ces cases RETIRÉES de `frm_veralux`.
- `ui/constants.py` : titre de section « nette » → « Chaîne avant étirement (…) ».
- `ui/app.py` : `_maj_lbl_vl` suit `vl_en_cours()`/`vl_stage` pour les deux moteurs (+ `_refresh_preview` sur `vl_new` pour les deux).
- `ui/saver.py` : `_gx_live_prete` ne se limite plus à VeraLux.
- `avastack/__init__.py` + `CLAUDE.md` : version 2.77.0, changelog, section « chaîne pré-étirement ».

### Mesures / faits vérifiés (rejouables)
- Banc jalon 125 : VERT — [1] cases GraXpert/débruitage DANS `frm_sharp`, PLUS dans `frm_veralux`, cadre partagé visible en STF ET VeraLux ; [2]/[3] sortie STF = GraXpert PUIS débruitage (== ce que la sauvegarde enchaîne AVANT l'étirement), `process()` étire dessus ; [4] moteur dans la clé, chroma N'ENTRE PAS dans la sortie STF.
- Bancs MAJ : 12 (netteté dans la chaîne unique — sortie = image nette, refus explicite, exception rattrapée), 40 et 41 (état des calculs = `vl_stage`, STF inclus), 47 (titre de section + ordre).
- Rejeu VERTS : veralux 2/3, graxpert_live 4, dn 7, sharp_live 12, couleurs 22, couleurs_immediat 39, etat_calcul 40, ui_moteur 41, ui_visibilite 47, save_brute 59, fond_bleu 62, chroma_structure 67, coeur_crame 64, zoom_pleine_res 68, pleine_res_traitee 69, histo 75, gx_parallele 81, save_rgb_axes, piedestal 122, neutralisation 123, exclusivite 124, chaine_pre_etirement 125.
- Échecs **PRÉEXISTANTS** (inchangés, cf. ci-dessous) : `chroma_nr_jalon63` [5]/[6] et `chroma_halo_jalon65` [6] ; `_test_espace_jalon72` (géométrie d'écran).
- Garde-fou : syntaxe 259, surface **75**, hash au bit, pyright **0/50** — VERT.

### Problèmes ouverts
- **BUG PRÉEXISTANT (1 ligne chacun, NON réparé)** : `chroma_nr_jalon63` [5]/[6] et `chroma_halo_jalon65` [6] comparent `_vl_result[0]` à `_vl_params()` SEUL (clé+forme vs clé sans forme) → prédicat TOUJOURS faux. **Alain décide** s'il veut la réparation.
- **CHROMA reste VeraLux** : sa case (visible dans « Fond et grain ») n'agit pas en STF (écran ET fichier) — à TRANCHER (cf. « PROCHAINE TÂCHE » point 3).

### Prochaines étapes
- **VALIDATION RÉELLE (Alain)** : M33 (fond neutre) + cocher GraXpert/débruitage **EN STF**.
- Puis COMMITER/POUSSER le jalon 125 (**pas de release** a priori).

### Points d'attention
- **Le CŒUR magenta N'EST PAS traité** : la neutralisation ne vise QUE le fond. MESURÉ M33 : cœur R/G 1,37 ; fond neutre (R/G 1,01). Démagenta ÉCARTÉ (perte du vrai Hα).
- Le worker ne touche JAMAIS aux stats EMA du STF (elles vivent dans le fil d'interface) : en STF/manuel il publie l'image PRÉ-ÉTIRÉE, et c'est `process()` qui étire.
- `sh_en_cours()` renvoie False (compat) : NE PAS s'en servir pour l'état des calculs (utiliser `vl_en_cours()` / `vl_stage`).
- Ne JAMAIS remettre les cases GraXpert/débruitage dans `frm_veralux` : masquées en STF, elles resteraient actives à la sauvegarde (c'est le défaut corrigé).

### Historique — jalon 124 (v2.76.0), 12/10/2026
- Neutralisation APRÈS les niveaux, JUSTE AVANT gamma/saturation + case déplacée dans
  « Couleur de l'objet (APRÈS) » + EXCLUSIVITÉ Équilibrage/SPCC/Gaia. Trace : changelog
  v2.76.0 ; commit `cd3a312` (jalons 121 à 124).

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

- **VOLET A = LIVRÉ (jalon 125, v2.77.0)** : GraXpert + débruitage tournent désormais à
  l'écran AUSSI en STF/manuel (chaîne pré-étirement UNIQUE). Reste à **VALIDER EN RÉEL**.
- **À ARBITRER (Alain)** : réparer ou NON le bug de prédicat PRÉEXISTANT de
  `chroma_nr_jalon63` [5]/[6] et `chroma_halo_jalon65` [6] (1 ligne chacun).
- **À TRANCHER (Alain)** : CHROMA en STF — sa case est visible mais inerte (réservée
  VeraLux, écran ET fichier) : l'ouvrir aux deux moteurs, ou la masquer en STF ?
- **À VALIDER EN RÉEL (Alain)** : relancer M33 — fond neutre attendu ; le CŒUR restera
  magenta (hors périmètre). Démagenta ÉCARTÉ (perte du vrai Hα).
- **Contrôle simple au passage** : re-mesurer les 2 FITS du 11/10 → les pixels à CANAL NUL
  (S = 1, fabriqués par le bug de restauration, corrigé au jalon 120) doivent avoir disparu.
- **Jalons 119 à 124** : committés/poussés ; **jalon 125 : à COMMITER/POUSSER** ; **release
  NON faite** (dernier tag publié = **v2.71.1**).
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
- **La neutralisation du fond (APRÈS l'étirement depuis le jalon 123 ; JUSTE AVANT
  gamma/saturation depuis le jalon 124) + `reduire_bruit_chroma` sont RÉSERVÉS à VeraLux**
  et **EXCLUS de la sortie linéaire traitée** (verrouillé, banc jalon 59 [6]) : un FITS
  linéaire ne les contient JAMAIS — ce n'est pas un bug. Au jalon 124 elle n'est PLUS dans
  le solveur : `process()` / `rendu_pleine_resolution` l'appliquent (le 9e élément `nf` du
  job reste transporté mais IGNORÉ).
- **JOB EXTERNE = 11 éléments** (jalon 123 : la neutralisation du fond en est SORTIE ;
  chroma = 8, force = 9, rayon = 10). Le « 12e élément » des anciens commentaires/bancs
  n'existe plus : un job plus court est lu TOLÉRANT (indices manquants → inactifs). Clé
  `ext_neutre_fond` plus écrite ni relue.
- **`_vl_params()` N'INCLUT PAS LA FORME** : le solveur indexe son cache par
  `_vl_params() + (img.shape,)`. Un prédicat qui compare `_vl_result[0]` à `_vl_params()`
  SEUL est donc TOUJOURS faux (« solveur jamais publié ») — cause des échecs PRÉEXISTANTS de
  `couleurs_immediat_jalon39` (réparé au 124), `chroma_nr_jalon63` [5]/[6] et
  `chroma_halo_jalon65` [6] (à réparer, même 1 ligne).
- **`_test_espace_jalon72` échoue en GÉOMÉTRIE D'ÉCRAN** (« aucun bouton écrasé » +
  « rogné/débordé ») : échec **PRÉEXISTANT** (reproduit à l'IDENTIQUE sur le HEAD du jalon
  120 via `git worktree`) — dépend de la taille d'écran de la machine, PAS du code.
- **La case chroma est IGNORÉE en vue « traitée »** (voulu : `_sync_vl_chroma_vue` la
  coupe, le résultat ⚡ la porte déjà). Conséquence PRATIQUE : un enregistrement fait
  depuis cette vue ne contient pas la chroma — vérifier la vue AVANT d'accuser le code.
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

- **12/10/2026** : jalon 125 (v2.77.0) — VOLET A : chaîne pré-étirement UNIQUE (GraXpert +
  débruitage à l'écran AUSSI en STF/manuel ; netteté dans la même chaîne ; solveur dédié
  supprimé) ; cases sorties du cadre VeraLux → « Chaîne avant étirement » ; banc neuf +
  rejeu + garde-fou VERTS ; **à commiter**, pas de release.
- **12/10/2026** : jalon 124 (v2.76.0) — NEUTRALISATION DÉPLACÉE (après niveaux, avant
  gamma/saturation) + case déplacée dans « Couleur de l'objet (APRÈS) » + EXCLUSIVITÉ
  Équilibrage/SPCC/Gaia ; **commité** (`cd3a312`), pas de release.

