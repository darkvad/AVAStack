# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md. **Gardé LÉGER** : le changelog détaillé vit dans
`avastack/__init__.py` — ici, seul le DERNIER jalon reste détaillé, sa trace
étant dans le changelog du source et l'historique git.)

---

## PROCHAINE TÂCHE — 12/10/2026 : VOLET COULEUR BOUCLÉ (jalons 122 + 123 + 124)

**Volet « couleur VeraLux » de M33 : TERMINÉ** — piédestal par canal (122), neutralisation
APRÈS l'étirement (123), puis jalon 124 (retours de la VALIDATION de M33 en v2.75.0) : case
déplacée dans « Couleur de l'objet (APRÈS) », neutralisation posée JUSTE AVANT
gamma/saturation, et exclusivité Équilibrage/SPCC/Gaia.

### À faire, dans cet ordre
1. **COMMITER/POUSSER** les jalons 121, 122, 123 ET 124 (aucun n'est committé ; HEAD =
   jalon 120 / v2.72.1). **PAS de release** a priori.
2. **À VALIDER EN RÉEL (Alain)** : relancer M33 — fond neutre, cœur sans magenta. ATTENTION :
   la neutralisation ne vise QUE le fond (le CŒUR reste magenta, R/G 1,37 MESURÉ) ; le
   remède « démagenta » a été ÉCARTÉ par Alain (il y perd le vrai Hα).
3. **VOLET A (chantier en cours, NON commencé)** : sortir GraXpert + débruitage du cadre
   VeraLux et donner aux modes STF/manuel le même chemin de sortie (décision d'Alain du
   11/10 : corriger CÔTÉ ÉCRAN, « le fichier = l'écran »). Détail au « Chantier en cours ».

### Règles d'or (rappel)
Un jalon = un banc NEUF + rejeu des bancs concernés (TOUS VERTS, hors échecs
**préexistants** documentés) + garde-fou `_test_refactoring_garde_fou.py` VERT ;
commentaires en FRANÇAIS. Jamais l'état d'une case déduit de `config.json` : le
MESURER sur le fichier.

---

## Session du 12/10/2026 (8) — JALON 124 (v2.76.0) : NEUTRALISATION DÉPLACÉE + EXCLUSIVITÉ

### État actuel
- **Livré** (retours de la VALIDATION de M33 en v2.75.0) : ① la case « Neutraliser la
  couleur du fond » quitte « Fond et grain (AVANT étirement) » pour « Couleur de l'objet
  (APRÈS étirement) » ; ② la neutralisation n'est PLUS dans le solveur — `process()` et
  `rendu_pleine_resolution` l'appliquent APRÈS les niveaux, JUSTE AVANT gamma/saturation ;
  ③ ÉQUILIBRAGE / SPCC / GAINS GAIA mutuellement EXCLUSIFS. Version **2.76.0**, changelog
  + CLAUDE.md à jour ; banc NEUF VERT ; rejeu + garde-fou VERTS.

### Fichiers modifiés
- `avastack/ui/panels/bgnoise.py` : case neutralisation RETIRÉE (ne garde que le bruit chromatique).
- `avastack/ui/panels/color.py` : case neutralisation AJOUTÉE en tête de `frm_couleur`, libellé « après étirement ».
- `avastack/processing/display.py` : `_neutraliser_fond` (neuf) appelé par `process()` (après niveaux, avant `_finition`) et par `rendu_pleine_resolution` ; RETRAIT du solveur (`_vl_worker`) ; `vl_neutre_fond` quitte `_vl_params` ; `vl_neutre_gains` publié par `process()`.
- `avastack/ui/app.py` : `_exclusivite_couleur` (neuf) appelé par `_on_wb` / `_on_spcc` / `_on_photo_gains` ; docstrings.
- `avastack/__init__.py` + `CLAUDE.md` : version 2.76.0, changelog, entrée neutralisation MAJ + entrée exclusivité.

### Mesures / faits vérifiés (rejouables)
- Banc jalon 124 : VERT — [1] case dans `frm_couleur`, PLUS dans `frm_fond` ; [2] exclusivité dans les 3 sens ; [3] l'image ENTRANT dans `_finition` a un fond NEUTRE (0,0027) alors que sans la case elle est COLORÉE (0,0272) ; [4] écran == fichier (0 niveau).
- Banc 123 mis à jour : la neutralisation quitte le solveur → `process()` publie les gains.
- Rejeu VERTS : couleurs_immediat 39, ui_visibilite 47, fond_bleu 62, save_asseen 5, zoom_pleine_res 68, couleurs 22, save_brute 59, veralux 3, piedestal 122, align 13, photometrie 56, fit_canaux 54, boost_rouge 86, dn 7, histo 75.
- Garde-fou : syntaxe **257**, surface **75**, hash au bit, pyright **0/50** — VERT.

### Problèmes ouverts
- **PRÉEXISTANTS (NON causés par le 124)** : ① `chroma_nr_jalon63` [5]/[6] et `chroma_halo_jalon65` [6] — MÊME défaut de prédicat que `couleurs_immediat_jalon39` (`_vl_result[0]` clé+forme vs `_vl_params()` sans forme, depuis la v2.55.3). **Le 39 est RÉPARÉ au 124** ; 63/65 restent à réparer (même 1 ligne). ② `_test_espace_jalon72` : géométrie d'écran (dépend de l'écran, pas du code).
- **« SPCC pas top » : RÉSOLU par l'exclusivité (à valider en réel).** Cocher SPCC
  décoche l'équilibrage → les gains SPCC/Gaia SURVIVENT enfin. MESURÉ (M33, composite
  linéaire → VeraLux → neutralisation) : sans équilibrage, gaia et spcc DIFFÈRENT (écart max
  **0,3163** ; fond R/G 0,92 vs 0,99) alors qu'avec l'équilibrage ils étaient identiques
  (écart max 0,0000). Reste à confirmer à l'écran par Alain.

### Prochaines étapes
- **COMMITER/POUSSER** (jalons 121+122+123+124), puis validation réelle M33, puis VOLET A.

### Points d'attention
- **Le CŒUR magenta N'EST PAS traité** : la neutralisation ne vise QUE la moitié SOMBRE (le fond). MESURÉ M33 : cœur R/G 1,37 (magenta) alors que le fond est neutre (R/G 1,01). Démagenta ÉCARTÉ par Alain (perte du vrai Hα).
- Neutralisation TOUJOURS réservée à VeraLux : le 9e élément `nf` du job solveur reste transporté mais IGNORÉ.
- Écran == fichier : `process()` ET `rendu_pleine_resolution` appliquent le MÊME étage avant `_finition` (bancs 123 [3] et 124 [3]/[4]).

### Historique — jalon 123 (v2.75.0), 12/10/2026
- NEUTRALISATION APRÈS l'étirement (`couleurs.neutraliser_apres_etirement`) ; ancien étage
  pré-étirement retiré aux 3 sites ; banc neuf + rejeu + garde-fou VERTS. Trace : changelog
  v2.75.0. (Le 124 ci-dessus déplace son application juste avant gamma/saturation.)

---

## Problèmes ouverts HORS session (hérités des jalons 116-118, toujours valides)
- L'**aligneur n'écrit RIEN** au journal (`%APPDATA%\AVAStack\journal.txt`) ;
  l'alternative « paires d'invariants top-60 × top-120 » du solveur reste non mesurée.

---

## Chantier en cours — chaîne de sortie : gradient & débruitage pour TOUS les moteurs

- **Demande d'Alain (11/10/2026)** : « je ne comprends pas pourquoi on ne pourrait
  pas mettre le retrait de gradient et la suppression de bruit pour STF aussi. »
- **C'est un choix d'ARCHITECTURE, pas une contrainte** : le thread solveur qui enchaîne
  GraXpert → débruitage → netteté → étirement ne tourne qu'en mode VeraLux (`_vl_worker`)
  et ses cases vivent dans le cadre VeraLux (masqué en STF) — or l'ORDRE de la chaîne
  (recadrage → gradient → débruitage → netteté → étirement) est INDÉPENDANT du moteur ;
  seule la dernière étape diffère.
- **DÉCISION D'ALAIN (11/10/2026)** : l'incohérence fichier ↔ écran (GraXpert +
  débruitage appliqués par la SAUVEGARDE mais pas par l'écran en STF) se corrige
  **CÔTÉ ÉCRAN** — on GARDE la sauvegarde et on fait tourner GraXpert + débruitage AUSSI
  à l'écran en STF (« le fichier = l'écran »).
- **Périmètre (à confirmer au lancement)** : les cases GraXpert/débruitage SORTENT du
  cadre VeraLux (cadre « pré-étirement » partagé) ; `_vl_worker` devient (ou est
  dupliqué en) un worker de chaîne pré-étirement dont seule la DERNIÈRE étape dépend du
  moteur. **Chroma** RESTE pré-étirement (elle aussi VeraLux : elle compense les gains de
  la chaîne). **À FAIRE (non commencé, à valider)** : sortir ces cases du cadre VeraLux
  et donner aux modes STF / manuel le même chemin de sortie.
- **VOLET B = FAIT** (jalons 122 + 123, v2.74.0 + v2.75.0) : le magenta venait de
  `neutraliser_fond` AVANT l'étirement — remède LIVRÉ (piédestal par canal + neutralisation
  APRÈS l'étirement). Le VOLET A ci-dessus, lui, n'était PAS la cause de ce défaut-ci.
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

- **PROCHAIN PAS = COMMITER/POUSSER** les jalons 121, 122, 123 ET 124 (aucun committé ; HEAD
  = jalon 120 / v2.72.1). **PAS de release** a priori.
- **À VALIDER EN RÉEL (Alain)** : relancer M33 — fond neutre attendu ; le CŒUR restera
  magenta (hors périmètre). Démagenta ÉCARTÉ (perte du vrai Hα).
- **Contrôle simple au passage** : re-mesurer les 2 FITS du 11/10 → les pixels à CANAL NUL
  (S = 1, fabriqués par le bug de restauration, corrigé au jalon 120) doivent avoir disparu.
- **VOLET A (à lancer)** : sortir GraXpert + débruitage du cadre VeraLux (voir « Chantier en
  cours »).
- **Jalons 119/120** : committés/poussés ; **release NON faite** (dernier tag publié =
  **v2.71.1**). Jalons 121/122/123/124 : **à commiter/pousser**, **pas de release**.
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

- **12/10/2026** : jalon 124 (v2.76.0) — NEUTRALISATION DÉPLACÉE (après niveaux, avant
  gamma/saturation) + case déplacée dans « Couleur de l'objet (APRÈS) » + EXCLUSIVITÉ
  Équilibrage/SPCC/Gaia ; banc neuf + rejeu + garde-fou VERTS ; **à commiter**, **pas de release**.
- **12/10/2026** : jalon 123 (v2.75.0) — NEUTRALISATION APRÈS l'étirement
  (`couleurs.neutraliser_apres_etirement`) ; ancien étage pré-étirement retiré aux 3 sites ;
  banc neuf + rejeu + garde-fou VERTS ; **à commiter**, **pas de release**.

