# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## Session du 09/10/2026 — RETOUR AU CODE v2.64.0 (jalons 111/112) : le repli 180° revient sur `master`

### Décision d'Alain (09/10/2026)
- Test de **v2.62.1** sur le jeu M31 LRGB (poses d'un SEUL côté du Pier, couche
  **L** seule) : **l'astrométrie ne s'améliore PAS**, et **moins de frames
  s'empilent / plus sont rejetées** qu'avec v2.64.0.
- **DÉCISION : remettre le CODE DE v2.64.0** (branche `meridien-wip`, commit
  `47ab25d` = jalons 111/112), qui empile mieux et n'ajoute pas d'erreur
  d'astrométrie. Le chantier méridien n'est donc plus « parqué » : il redevient
  le code de travail.
- **HYPOTHÈSE D'ALAIN (piste n°1, à instruire)** : dans son test M31 LRGB, l'image
  empilée est à **180°** parce que l'orientation est prise sur la couche **L**
  (alors qu'en RGB l'astrométrie fonctionne) — or une astrométrie NE DEVRAIT PAS
  être gênée par une rotation de 180° : à vérifier.

### Réalisé (09/10/2026) — code v2.64.0 remis dans `master`
- `git checkout meridien-wip -- <9 fichiers>` : les **4 fichiers de CODE** —
  `avastack/__init__.py` (version + changelog), `avastack/catalogues/propagation.py`,
  `avastack/processing/alignment.py`, `avastack/processing/stars.py` — et les
  **5 bancs/outils** de diagnostic (`_diag_align_dossiers.py`, `_diag_align_verite.py`,
  `_diag_meridien_flip_reel.py`, `_diag_orientation.py`,
  `_test_meridien_flip_jalon111.py`).
- **`AVASTACK_VERSION = "2.64.0"`**, import OK. Bancs rejoués **VERTS** :
  `_test_meridien_flip_jalon111` (TOUT AU VERT, section [4] incluse),
  `_test_align_jalon13`, `_test_propagation_jalon56`.
- ⚠ **RIEN n'est commité ni poussé, aucun paquet, aucune release.** La branche
  `meridien-wip` est CONSERVÉE ; filet `%TEMP%\jalons111-112.patch`.

### Ce que fait le code v2.64.0 (rappel ; détail au changelog `avastack/__init__.py`)
- `processing/stars.py` : SÉLECTION RÉPARTIE (`distance_min`, repli progressif,
  `CANDIDATS_MAX`, `MIN_REPARTI`). Défaut 0 = comportement antérieur inchangé.
- `processing/alignment.py` : `MAX_ALIGN_ETOILES` 60 → **250**, écart adaptatif
  `_distance_repartition()`, **REPLI 180°** dans `compute()` (sens direct d'abord,
  repli « phase » écarté pour ce cas), `_M_valide` accepte ~180° (170°–190°).
- `catalogues/propagation.py` : sanitation d'angle acceptant ~180° (le WCS est
  conservé sur un ré-empilement basculé sur une frame retournée).

### Mesures à réutiliser (session du 08/10/2026)
- Config test « RGB » (source Composition, lignes R/G/B) : `norm_commune = true`,
  `ref_refresh = 10`, filtre flou actif ; 150 brutes (50/rôle) → 111 empilées,
  39 refus d'ALIGNEUR.
- **Test A/B décisif** : la MÊME brute s'aligne (« triangles +180° »), mais la
  même brute **CALIBRÉE (dark) est REFUSÉE** → c'est la **structure du dark** qui
  change les étoiles détectées ; une frame retournée ne passe que par le chemin
  « triangles » (base = top-12, fragile).
- **Défaut réel à corriger** : le rafraîchissement de référence en mode
  COMPOSITION passe le composite (H, W, 3) → `canal_alignement` ne garde que le
  VERT → **l'ORB devient aveugle**.
- Note : `composition._echelle_commune` vient du rôle du canal **VERT** (G en
  RGB/LRGB), pas de L.

### Outils de diagnostic jetables (hors dépôt, dans `%TEMP%`)
`avastack_diag_refresh.py` (rejeu de session : ordre + rafraîchissements),
`avastack_diag_archive.py` (archive vs source + test A/B), `jalons111-112.patch`.
Archives de session (`%TEMP%\avastack_frames_*` = frames réellement LUES) :
⚠ supprimées par l'appli au démarrage **6 h après** leur dernière écriture — les
copier si la preuve doit survivre.

### Prochaine étape (UNE seule)
Instruire l'**erreur RANSAC de l'astrométrie** en testant la piste n°1 d'Alain
(image empilée à 180° car l'orientation est prise sur L) : reproduire hors-ligne
l'astrométrie sur un empilement M31 LRGB, **ancre L vs ancre R**, à 0° et 180°.
Si concluant ensuite : **paquets + release**.

### Points d'attention
- Ne PAS présenter v2.64.0 comme un correctif « validé » : le test réel du 08/10
  (jeux mêlant les deux côtés du méridien) restait non concluant.
- AVANCEMENT.md dépasse largement la cible de taille (cf. `.clinerules`, ≤ 300
  lignes) : les blocs HISTORIQUE antérieurs sont à nettoyer.

---

## Chantier en cours — ALIGNEMENT : retournement au méridien + astrométrie

**But** : que les frames d'UN côté du méridien (rotation ~180° par rapport au
ciel) s'empilent au lieu d'être rejetées, et que l'astrométrie (solveur +
propagation) fonctionne sur un empilement LRGB.

**État (09/10/2026)** : le code **v2.64.0** (jalons 111/112) est REMIS dans
`master` (cf. session ci-dessus) — `AVASTACK_VERSION = "2.64.0"`, NON commité.
Il n'est PAS encore validé en réel sur un jeu mêlant les deux côtés du méridien.

**Règles d'or** :
- Un jalon = un banc neuf + rejeu des bancs concernés (TOUS VERTS) + garde-fou
  `bancs/_test_refactoring_garde_fou.py` VERT (syntaxe, surface 75, hash au bit).
- On ne réécrit JAMAIS un tag publié ; version + changelog + AVANCEMENT.md dans la
  même réponse ; commentaires et docstrings en FRANÇAIS.
- Le chantier de refactoring (jalons 100→110) est CLOS : plus de découpage de
  `app.py` ni de typage rétroactif.

---

## En attente / prochaine session

- **Chantier courant** : instruire l'erreur RANSAC d'astrométrie (piste n°1 :
  image empilée à 180° car l'orientation est prise sur L) — cf. session du
  09/10/2026.
- **Test « installer depuis le Microsoft Store »** (seul test qui n'existe que par
  cette voie ; l'appli v2.50.0 y est publiée).
- **Paquet macOS** : test réel par le testeur — « 📂 Dossier » et « Charger un
  flat… » doivent répondre au PREMIER clic (sinon : son `journal.txt`).
- **Linux** : restent la machine VIERGE (sans Python) et le test matériel caméras
  (`--cameras`).
- **Boutons de données SANS Siril** (« ⬇ Gaia », « ⬇ Spectres (champ) », « ⬇ Base
  SPCC ») — délégués à un utilisateur sans Siril.
- **Piste INDI** (client INDI : un seul chemin pour les 3 OS et toutes les
  marques) — jalon à part, PAS avant le portage Linux avec les `.so`.

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
- **Aligneur** : une frame retournée ne s'aligne que par le chemin « triangles »
  (base = top-12 des étoiles, fragile) ; une brute CALIBRÉE (dark) peut être
  refusée là où la même brute non calibrée passe.

---

## Clôtures précédentes

- **08/10/2026** : retour à v2.62.1 et park du chantier méridien (jalons 111/112)
  — REVERSÉ le 09/10 (le test 2.62.1 empile MOINS de frames).
- **07/10/2026** : clôture du chantier de refactoring (jalons 100→110) —
  v2.62.1 livrée, testée en réel, publiée.

