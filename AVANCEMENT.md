# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## Session du 10/10/2026 — JALON 118 : INSTALLATEUR WINDOWS .EXE RÉPARÉ (v2.71.1) — FAIT, PUBLIÉ

### État actuel
- **Défaut RÉEL trouvé par Alain** (10/10/2026) : après une installation PROPRE
  par l'`.exe`, l'application NE DÉMARRAIT PAS —
  `ModuleNotFoundError: No module named 'avastack.ui.widgets'` (`app.py`, ligne
  104).
- **Cause** : la section `[Files]` d'`avastack.iss` énumérait ses sources
  DOSSIER PAR DOSSIER (UN seul niveau) → les SOUS-PAQUETS créés par le
  refactoring (`avastack/core/`, `avastack/ui/widgets/`, `avastack/ui/panels/`,
  le 07/10/2026) n'étaient PAS embarqués. L'installateur `.exe` livrait donc un
  paquet AMPUTÉ depuis la **v2.58.1** jusqu'à la **v2.71.0** incluse. Les autres
  canaux (ZIP, gelé/MSIX, Linux, macOS) copient RÉCURSIVEMENT : SAINS — et
  l'appli publiée au Store (v2.50.0) est ANTÉRIEURE au refactoring, donc saine.
- **CORRECTIF** : une SEULE source RÉCURSIVE dans `avastack.iss`
  (`Source: "{#RepoRoot}\avastack\*" … recursesubdirs` ; `Excludes` écarte
  `__pycache__`/`.pyc`/`.pyi`). Sémantique Inno VÉRIFIÉE EN RÉEL (mini-paquet
  compilé **et installé** : arborescence préservée sous `{app}\avastack`).
- **v2.71.1 LIVRÉE ET PUBLIÉE** : les 4 paquets + `INSTALLATION.md` régénéré
  (nouveaux SHA-256) ; **MSIX v2.71.1 reconstruit et signé** (cadence Store
  séparée). **Restait à VÉRIFIER en réel** l'installateur `.exe` corrigé.

### Fichiers modifiés dans cette phase
- `installer/windows/avastack.iss` : `[Files]` → une source RÉCURSIVE
  (`{#RepoRoot}\avastack\*` + `recursesubdirs` + `Excludes` des fichiers de DEV)
  remplace l'énumération par dossier.
- `bancs/_test_installeur_iss_fichiers_jalon118.py` : banc NEUF (couverture du
  package + compilation ISCC) — **VERT**.
- `avastack/__init__.py` : **v2.71.1** + changelog.
- `INSTALLATION.md` : v2.71.1 + SHA-256/tailles des 4 paquets.
- Artéfacts de BUILD (non suivis, `installer/*/output/`) : les 4 paquets 2.71.1,
  le gelé 2.71.1 (+ `.zip`) et le MSIX 2.71.1 signé (+ `.cer`/`.pfx`).

### Décisions prises
- **Copie RÉCURSIVE** (plutôt qu'ajouter 3 lignes) : rend le défaut impossible
  pour tout **sous-paquet FUTUR** — c'est déjà ce que font ZIP / Linux / macOS.
- **Banc de COUVERTURE** : simule la sélection de fichiers d'Inno et exige que
  TOUT `avastack/` (sous-paquets compris) soit embarqué → rouge si on « oublie ».
- **Release patch v2.71.1** : on ne réécrit JAMAIS un tag publié (v2.71.0).

### Prochaines étapes
- **Test EN RÉEL du nouvel `.exe`** (déjà installé sur le PC d'Alain) : lancer
  `avastack-setup-2.71.1.exe` et vérifier que l'application DÉMARRE.
- **MSIX v2.71.1** : prêt ; **reste à le SOUMETTRE** dans Partner Center (action
  manuelle d'Alain, cf. `SOUMISSION.md` §1 et §7).
- Prochaine session : au choix d'Alain (voir « En attente »).

### Points d'attention / pièges de cette session
- ⚠ **L'installateur `.exe` n'avait AUCUN banc de CONTENU** (contrairement au
  paquet ZIP, banc 88) : c'est POURQUOI le défaut est passé 2 semaines. Le banc
  118 comble ce trou — toute omission future d'un sous-paquet rougira.
- Ordre des imports de `app.py` : `ui/widgets` (l. 104) → `ui/panels` (l. 121+)
  → `core` (l. 182) — c'est widgets qui tombe EN PREMIER quand le paquet est
  amputé (message d'erreur utile).
- Un paquet GELÉ/MSIX embarque tout (analyse des imports) : non concerné.

---

## HISTORIQUE — jalon 117d (10/10/2026) : lissage LRGB OPT-IN + σ réglable (v2.71.0)
- Case « lisser le combine LRGB » DÉCOCHÉE par défaut + champ σ du masque [3 ; 100] ; test réel OK (M31).
- Détail : changelog **v2.71.0**, banc `_test_lissage_halos_optin_jalon117d.py`. NE PAS REMESURER.

## Problèmes ouverts (hérités des jalons 116-117, toujours valides)
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
retirait 9-18 % du détail). **Jalon 117d LIVRÉ ET PUBLIÉ** (v2.71.0) : ce lissage devient
**OPT-IN** (case décochée par défaut) et son **seuil de masque devient RÉGLABLE**
— test réel OK (M31), commité/poussé et publié. Détail : changelog de
`avastack/__init__.py` et historique git.

**Règles d'or** :
- Un jalon = un banc neuf + rejeu des bancs concernés (TOUS VERTS) + garde-fou
  `bancs/_test_refactoring_garde_fou.py` VERT (syntaxe, surface 75, hash au bit).
- On ne réécrit JAMAIS un tag publié ; version + changelog + AVANCEMENT.md dans la
  même réponse ; commentaires et docstrings en FRANÇAIS.
- Le chantier de refactoring (jalons 100→110) est CLOS : plus de découpage de
  `app.py` ni de typage rétroactif.

---

## En attente / prochaine session

- **Release GitHub v2.71.1 PUBLIÉE** (4 paquets + `INSTALLATION.md`). Dernier
  tag publié = **v2.71.1**.
- **À VÉRIFIER EN RÉEL** : l'installateur `.exe` corrigé (l'application démarre
  après installation) — c'est LE test qui manquait et qui a révélé le défaut.
- **Microsoft Store** : cadence SÉPARÉE — l'application PUBLIÉE y reste la
  **v2.50.0** ; le **MSIX v2.71.1 est CONSTRUIT ET SIGNÉ** (prêt à resoumettre).
  Prochaine action (Alain, manuelle) : soumettre ce MSIX dans Partner Center
  (cf. `SOUMISSION.md` §1 et §7).
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

- **10/10/2026** : jalon 118 (v2.71.1) — installateur Windows `.exe` réparé
  (copie RÉCURSIVE du package ; sous-paquets manquants depuis v2.58.1) ; banc
  garde-fou de contenu ; **PUBLIÉ** (release GitHub v2.71.1).
- **10/10/2026** : jalon 117d (v2.71.0) — lissage LRGB rendu **OPT-IN** (case
  décochée par défaut) avec **σ du masque réglable** à CHAUD ; **test réel OK
  (M31)** ; **PUBLIÉ** (release GitHub v2.71.0).

