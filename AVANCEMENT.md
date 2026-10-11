# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md. **Gardé LÉGER** : le changelog détaillé vit dans
`avastack/__init__.py` — ici, seul le DERNIER jalon reste détaillé, sa trace
étant dans le changelog du source et l'historique git.)

---

## PROCHAINE TÂCHE — fin de session du 11/10/2026 : RESTENT (2) FICHE DE RENDU puis (3) correctif COULEUR

**Objectif** : **(1) BUG de restauration = FAIT** (jalon 120 / v2.72.1 — session (4)).
Restent, dans CET ordre : **(2)** la FICHE DE RENDU (traçabilité des paramètres par image
— « Chantier à ouvrir » (2)) ; **(3)** la COULEUR de l'étirement VeraLux (fond
magenta/cyan, cœur magenta) et les taches de couleur — le défaut visuel le plus visible,
mais APRÈS.
*(A/B chroma : TRANCHÉ le 11/10/2026 — la case MORD en réel ; le « % taches » qui semblait
dire le contraire venait du BUG (1), maintenant corrigé.)*

### À faire, dans cet ordre
1. **BUG DE RESTAURATION — FAIT (jalon 120, v2.72.1)** : `App._curseurs` (registre
   variable → curseur) + `App._poser_curseur(var, v)` = chemin d'un geste (`s.set`) ;
   `_restaurer_config` route par lui ; banc `_test_restauration_curseurs_jalon120.py`
   VERT. Détail en session (4) ; la règle est écrite dans CLAUDE.md.
2. **FICHE DE RENDU (traçabilité) — à FAIRE VALIDER AVANT DE CODER** : les 4 décisions
   d'Alain (nom et emplacement, toujours ou sur une case, chemins complets ou noms seuls,
   écrites aussi pour les sorties LINÉAIRES ?) sont listées dans « Chantier à ouvrir »
   (2), avec le contenu proposé du JSON compagnon et ses garde-fous.
3. **VOLET COULEUR (le vrai correctif, à découper en jalons)** — recette
   MESURÉE hors appli :
   (a) chroma 0,60 **AVANT** l'étirement ;
   (b) **PIÉDESTAL PAR CANAL** avant l'étirement (des OFFSETS, pas des gains :
       amener les niveaux de ciel des 3 canaux au MÊME niveau) ;
   (c) neutralisation du fond **APRÈS** l'étirement (gains mesurés sur le fond
       de la SORTIE) — et RETIRER `neutraliser_fond` d'AVANT l'étirement, qui
       vise 0,7 % à côté et FABRIQUE le magenta.
   Résultat mesuré : fond 0,99 · disque 0,95 · bras 1,09 · cœur 1,10 · taches
   2,5 % — contre fond 0,63 (cyan) et cœur 1,35 (magenta) aujourd'hui.

### Points de code à relire en premier
- `avastack/ui/saver.py` l.439 (la sortie LINÉAIRE est écrite APRÈS la netteté),
  l.465 (neutralisation) et l.473 (chroma) : chemin « tel que vu » ;
- `avastack/ui/app.py` l.2548-2572 : `_on_vl_chroma` / `_sync_vl_chroma_vue` ;
- `avastack/processing/couleurs.py` l.411-520 : `reduire_bruit_chroma` (poids de
  structure, rayon, plancher) — et l.237-273 `gains_fond`, dont l'estimateur
  (« moitié la plus sombre ») est la cause racine du magenta ;
- `avastack/processing/veralux.py` l.147-163 : `normaliser_lin` puis le moteur —
  c'est LÀ que le piédestal par canal doit entrer.

### Règles d'or (rappel)
Un jalon = un banc NEUF + rejeu des bancs concernés (TOUS VERTS) + garde-fou
`_test_refactoring_garde_fou.py` VERT ; commentaires en FRANÇAIS. Jamais l'état
d'une case déduit de `config.json` : le MESURER sur le fichier (détails au
« Chantier en cours »).

---

## Session du 11/10/2026 (4) — JALON 120 (v2.72.1) : « réglage appliqué mais non affiché » CORRIGÉ

### État actuel
- **Livré** : correctif + banc neuf + garde-fou VERT ; version **2.72.1**, changelog et
  CLAUDE.md à jour. Fichiers touchés : `avastack/ui/app.py`, `avastack/ui/config_ui.py`,
  `avastack/__init__.py` (version + changelog), `bancs/_test_restauration_curseurs_jalon120.py`.

### Ce qui a été fait
- `app.py` : `App._curseurs` (registre `str(var)` → curseur, rempli dans `_add_slider`)
  + `App._poser_curseur(var, valeur)` — repose une valeur par le CHEMIN D'UN GESTE
  (`s.set(v)` → `cmd` : variable + étiquette + callback), repli `var.set` si la variable
  n'a pas de curseur. `__init__` crée le registre AVANT `_build_ui`.
- `config_ui.py` : les **10 sites** de restauration de curseurs passent par
  `_poser_curseur` (sigk/target/gamma/saturation, saturation R/V/B, forces SCNR/démagenta/
  boost, `vl_target`/`vl_logd`, force + rayon du bruit chromatique, débruitage live et
  externe, itérations de netteté, force d'équilibrage) ; `_poser_curseur` DÉCLARÉ dans le
  mixin `ConfigUI` (typage — sinon pyright tombe).
- Banc neuf : étiquette == bouton == variable == config (== `disp.*`) POUR CHAQUE
  curseur, cas `sat_b = 3,0` (celui de M33) et valeurs hors bornes → défaut conservé.

### Mesures / faits vérifiés (rejouables)
- **Tk 8.6, 11/10/2026** : `var.set` NE déclenche PAS le `command` d'un `ttk.Scale` —
  ni sans `variable=` (le curseur ne bouge pas non plus), **ni AVEC `variable=`** (le
  curseur bouge, mais l'étiquette et les callbacks NON). Seul `s.set(v)` déclenche `cmd`.
  ⇒ l'option « lier `variable=var` » NE SUFFIT PAS ; il fallait le helper.
- Banc jalon 120 : TOUS VERTS. Banc rejoué avec l'ANCIEN comportement (`var.set` nu) :
  `sat_b` affiche 1,00 pendant que `disp` vaut 3,0 → le banc DÉTECTE le bug.
- Garde-fou (jalon 100) : TOUT AU VERT (syntaxe 252 fichiers, surface publique 75,
  hash d'empilement au bit, pyright 0/49).

### Problèmes ouverts
- **3 bancs échouent de façon PRÉEXISTANTE** (le résultat du solveur VeraLux n'est pas
  publié dans ce contexte de test) : `_test_chroma_nr_jalon63.py` [5]/[6],
  `_test_chroma_halo_jalon65.py` (« le solveur applique le rayon du job »),
  `_test_couleurs_immediat_jalon39.py` (« résultat affiché »). CHACUN REJOUÉ avec le code
  D'ORIGINE (mes 2 fichiers mis de côté par `git stash`) : **MÊMES échecs → PRÉEXISTANT,
  PAS causé par le jalon 120**. À traiter à part.

### Prochaines étapes
- Faire valider à Alain les 4 décisions de la fiche de rendu, puis la coder.
- Puis le volet couleur (piédestal par canal + neutralisation APRÈS l'étirement).

### Points d'attention
- Toute nouvelle valeur posée dans l'UI doit passer par `_poser_curseur` (ou `s.set`) :
  un `var.set` nu sur un curseur ne met à jour QUE la variable, pas l'affichage.

---

## Session du 11/10/2026 (3) — A/B chroma : RÉSULTAT (compact)
- La case chroma MORD en réel (2 FITS d'Alain, 95,9 % des pixels diffèrent ; bruit de
  couleur du fond ÷2,1 à ÷2,6). Le fichier COCHEE était identique au bit à son
  enregistrement de 18h24 → la chroma y était bien ; la métrique « % taches » qui disait
  le contraire était FAUSSÉE par le BUG (1).
- Les « patés » de couleur = pixels à canal échu à 0 (S = 1) produits par
  `sat_canaux = (1 ; 1 ; 3,0)` APPLIQUÉ mais NON AFFICHÉ (bug (1)) ; les EXCLURE de toute
  statistique de couleur. Détails pérennes : CLAUDE.md (« PIÈGE Tk MESURÉ », « config.json
  N'EST PAS LA RÉALITÉ ») ; diagnostics jetables `%TEMP%\ava_ab_chroma*.py`.

---

## Session du 11/10/2026 (2) — M33 : cause racine du magenta (compact)
- `neutraliser_fond` AVANT l'étirement vise avec un estimateur (« moitié la plus
  sombre ») qui n'est PAS la grandeur que l'ancre amplifie → fond CYAN puis MAGENTA ;
  REMÈDE MESURÉ = neutraliser APRÈS l'étirement (cf. « PROCHAINE TÂCHE » (3)). Légende
  des fichiers M33 (①..⑤) et point ouvert « aucun FITS ne portait de provenance » →
  chantier « fiche de rendu ». Fausses pistes écartées : gradient de fond de M33 (② PLAT
  à 0,3 %) et GraXpert non lancé (il a tourné). Détails : changelog + `%TEMP%\ava_m33_*.py`.

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
  moteur. **Neutralisation de fond** et **chroma** RESTENT VeraLux (elles compensent
  son ancre). **À FAIRE (non commencé, à valider)** : sortir ces cases du cadre VeraLux
  et donner aux modes STF / manuel le même chemin de sortie.
- **PRIORITÉ = VOLET B (MESURÉ)** : le magenta ne vient PAS du gradient ni du débruitage
  mais de `neutraliser_fond` AVANT l'étirement ; remède mesuré : neutraliser **APRÈS**
  l'étirement (le volet A ci-dessus ne corrige pas ce défaut-ci).
- **Règles d'or** (rappel) : voir PROCHAINE TÂCHE. On ne réécrit JAMAIS un tag publié ;
  version + changelog + AVANCEMENT.md dans la même réponse.

---
## Chantier à ouvrir — (1) BUG « valeur appliquée non affichée », (2) FICHE DE RENDU

### (1) BUG de restauration — FAIT (jalon 120, v2.72.1)
- Corrigé par `App._curseurs` + `App._poser_curseur` (chemin d'un geste `s.set`) ; les
  10 sites de `_restaurer_config` routés ; banc `_test_restauration_curseurs_jalon120.py`
  VERT. Détail en session (4) et règle dans CLAUDE.md.

### (2) FICHE DE RENDU — que chaque image dise ce qu'elle a subi (demande d'Alain)
Objectif : **ne plus jamais deviner un réglage** (ni depuis `config.json`, ni par
empreinte mesurée) ; « le fichier dit ce qu'on lui a fait ».
- **Forme** : JSON COMPAGNE écrit par le MÊME thread que l'image, à côté d'elle
  (`M33.fits` → `M33.ava.json`). Rien dans le FITS (linéarité des sorties intacte).
- **Contenu** : version + commit de l'appli, date, fichier écrit, type de sortie
  (tel que vu / traité linéaire / brut / couche), dimensions ; SOURCE (chemin, nombre
  de frames, filtres) ; la chaîne DANS L'ORDRE — recadrage, gradient (COMMANDE exacte),
  débruitage, netteté, chroma (force + rayon), neutralisation, corrections couleur
  (gains / WB / Linear Fit), moteur d'étirement (+ mode de résolution + **logD RÉSOLU**
  + fond cible), barres noir/médian/blanc, gamma, saturation globale et R/V/B, cases
  (SCNR, démagenta, boost rouge, GraXpert), vue ; et **l'état APPLIQUÉ À CÔTÉ de l'état
  AFFICHÉ** — si les deux diffèrent, le fichier le DIT (c'est ce qui a manqué ici).
- **Garde-fous** : écriture atomique (temporaire puis remplacement) et TOLÉRANTE à
  l'échec (une fiche ratée n'échoue jamais l'enregistrement) ; nom dérivé du fichier
  image ; dépôt PUBLIC → chemins complets ou noms seuls = décision d'Alain.
- **À TRANCHER par Alain** : nom et emplacement de la fiche, toujours ou sur une case,
  niveau de détail des chemins, et si elle est écrite aussi pour les sorties LINÉAIRES.

---
## En attente / prochaine session

- **PROCHAIN PAS — CHOIX D'ALAIN (clôture du 11/10/2026)** : **(a) FAIT** (BUG de
  restauration — jalon 120 / v2.72.1). RESTENT : **(c)** la FICHE DE RENDU (traçabilité
  — « Chantier à ouvrir » (2)), après validation des 4 décisions d'Alain ; **(b)** le
  REMÈDE COULEUR VeraLux (piédestal par canal + neutralisation APRÈS l'étirement —
  PROCHAINE TÂCHE §3) viendra ENSUITE.
- **Jalon 120 (v2.72.1)** : correctif + banc neuf + garde-fou VERT ; **commit + push
  faits** ; **PAS de release publiée** (à confirmer par Alain). Prochain test réel
  possible : relancer l'appli et vérifier qu'un curseur restauré hors défaut s'AFFICHE
  bien à sa valeur.
- **A/B chroma (FAIT, session (3))** : la case mord EN RÉEL ; et le fichier COCHEE
  d'Alain est identique au bit à son enregistrement de 18h24 → la chroma y était déjà.
- **Après (a) — contrôle simple** : quand Alain relancera M33, re-mesurer ses 2 FITS du
  11/10 pour vérifier que les pixels à 0 disparaissent (compter les canaux à 0).
- **Jalon 119 (v2.72.0) TERMINÉ** : testé en réel (OK), commité/poussé ; **release NON
  faite** (demande d'Alain). Dernier tag publié = **v2.71.1** (4 paquets + INSTALLATION).
- **À VÉRIFIER EN RÉEL** : l'installateur `.exe` corrigé (l'application démarre après
  installation) — c'est LE test qui manquait et qui a révélé le défaut.
- **Microsoft Store** : cadence SÉPARÉE — l'appli PUBLIÉE y reste la **v2.50.0** ; le
  **MSIX v2.71.1 est CONSTRUIT ET SIGNÉ** (prêt à resoumettre, cf. `SOUMISSION.md`
  §1/§7) ; reste le test « installer depuis le Store » (seule voie pour ce test).
- **Boutons de données SANS Siril** (« ⬇ Gaia », « ⬇ Spectres (champ) », « ⬇ Base
  SPCC ») — délégués à un utilisateur sans Siril.
- **Piste INDI** (un seul chemin pour les 3 OS et toutes les marques) — jalon à part,
  PAS avant le portage Linux avec les `.so`.

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
- **`neutraliser_fond` + `reduire_bruit_chroma` sont RÉSERVÉS à VeraLux** et **EXCLUS de
  la sortie linéaire traitée** (verrouillé, banc jalon 59 [6]) : un FITS linéaire ne les
  contient JAMAIS — ce n'est pas un bug.
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

- **11/10/2026** : jalon 120 (v2.72.1) — bug « réglage appliqué mais non affiché »
  CORRIGÉ (registre de curseurs + `_poser_curseur`), banc neuf, garde-fou VERT ;
  commité/poussé ; **PAS de release** (à confirmer).
- **11/10/2026 (sessions 2-3 — M33 couleur)** : analyse seule, **aucun fichier de code
  modifié** (AVANCEMENT.md seulement) ; livré = A/B chroma tranché en réel + BUG de
  restauration des curseurs prouvé + plan « fiche de rendu » écrit.

