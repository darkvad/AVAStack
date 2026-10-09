# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## Session du 09/10/2026 — CLÔTURE : jalons 111→115 (v2.67.0), CAUSE de l'astrométrie corrigée, TEST RÉEL OK

### État actuel
- **`AVASTACK_VERSION = "2.67.0"` — TESTÉE EN RÉEL OK (09/10/2026) sur le jeu M31
  LRGB SANS retournement au méridien : l'astrométrie se RÉSOUT** (l'échec
  chronique de v2.65.0/v2.66.0 est réglé). Commit + push faits à la clôture.
- Ce qui a débloqué : le **journal de v2.66.0** (test réel, 7 échecs) —
  « pas assez de correspondances mutuelles ; RANSAC paires : … (meilleur : 3
  inliers, échelle 1.628″/px) », **aucune résolution, aucun balayage ASTAP** —
  a donné le message EXACT à reproduire hors-ligne.
- **CAUSE trouvée et REPRODUITE hors-ligne** (rejeu de la session sur les frames
  archivées) : le solveur recevait le **COMPOSITE NORMALISÉ**
  (`stacker.mean(recadre=False)`) — fond ~**0,72**, σ ~0,033 → son seuil
  `fond + 8σ` tombe à ~**0,99** : presque rien ne passe, les « étoiles »
  détectées sont du **BRUIT** → appariement impossible. La **COUCHE BRUTE du rôle
  G** (même grille) **RÉSOUT : 94 appariements à 2,466″/px** (couche L : 108) ⇒
  données, catalogue (400 étoiles), indices (champ 2,63665°) et détection (120
  étoiles) sont **BONS**.
- C'est le **même défaut de DOMAINE que le correctif ① du jalon 113**, qui n'avait
  corrigé que l'**ALIGNEUR** — l'astrométrie, elle, gardait `mean(recadre=False)`.

### Fichiers modifiés dans cette phase (jalon 115)
- `avastack/core/worker.py` : nouveau **`_image_reference_de(st)`** (corps de
  l'ancienne `_image_reference`, jalon 113, déplacé tel quel) ; **`_image_reference()`**
  délègue ; les TROIS chemins d'astrométrie passent la COUCHE BRUTE :
  `_astro_tour`, `_astro_aveugle` (ASTAP aussi) et **`_astro_propager_restack`**
  (l'ancien empilement via `_image_reference_de(ancien)`) — la piste ouverte du
  jalon 113 est donc FERMÉE.
- `avastack/processing/astrometrie.py` : `SuiviAstrometrie` garde les compteurs du
  dernier échec (**`info_echec`**, **`resume_echec()`**) et les ajoute au message :
  « [image N étoiles, catalogue M, appariements K] ».
- `avastack/core/worker.py` (suite, même jalon) : **`_photo_tour` et `_spcc_tour`
  passent par `_profondeur_astro`** — le seuil de profondeur de la photo et de la
  SPCC comparait encore `stacker.n` (la SOMME des rôles) alors que l'astrométrie
  était passée au min PAR RÔLE (jalon 113). Un seul point de décision ; les
  messages annoncent la profondeur par rôle (« N frames par rôle (M au total) »).
- `avastack/processing/spcc.py` : `texte_resume` dit « mesure faite sur N frames
  **par rôle** » quand le worker a posé `diag["frames_par_role"]`.
- `avastack/__init__.py` : version **2.67.0** + changelog (jalons 114 + 115).
- `bancs/_test_astro_domaine_jalon115.py` (NEUF) ; `_test_astro_profondeur_jalon113.py`
  **ÉTENDU** (section [6] : photo/SPCC au même seuil).

### Décisions prises
- ① **L'astrométrie reçoit la MÊME image que l'aligneur** (`_image_reference_de`) :
  la couche BRUTE du rôle du canal VERT, JAMAIS le composite normalisé. Un SEUL
  corps pour les deux consommateurs ⇒ plus de divergence possible.
- ② Les compteurs du solveur sont AJOUTÉS au message d'échec (le dict `info` était
  jeté en cas d'échec) : un échec futur dira seul s'il vient de la DÉTECTION, du
  catalogue ou de l'appariement.
- ③ Le jalon 114 (journal au changement + libellés copiables) a PERMIS cette
  trouvaille : c'est ce journal qui a donné le message exact à reproduire.
- ④ **UN SEUL seuil de profondeur** pour les trois mesures (astro, photo, SPCC) :
  le jalon 113 avait laissé la photo et la SPCC sur `stacker.n` (« sans effet,
  elles mesurent après un WCS résolu »), mais deux règles pour une même décision
  finissent toujours par se contredire — Alain a demandé la suppression de
  l'écart AVANT le test réel, pour ne pas le chercher dans trois mois.
  `_profondeur_astro` est désormais le point unique (`stacker.n` ne sert plus
  JAMAIS de seuil, uniquement de total affiché).

### Vérifications du jalon 115 (toutes vertes)
- Banc NEUF vert ; `_test_astro_profondeur_jalon113` (section [6] INCLUSE),
  `_test_astro_branchement_jalon56`,
  `_test_propagation_jalon56`, `_test_compo_worker_jalon19`, `_test_photometrie_jalon56`,
  `_test_catalogues_jalon70`, `_test_journal_libelles_jalon114`, `_test_spcc_jalon58` verts.
- **Preuve hors-ligne sur les VRAIES frames** : composite `mean(recadre=False)` →
  ÉCHEC (message identique au journal) ; couche G → RÉSOLU 94 app. à 2,466″/px.
- Garde-fou VERT : syntaxe 244 fichiers, **surface 75 inchangée**, hash au bit
  inchangé, **pyright 0/49** ; `ruff` propre.

### Mesures de référence (à réutiliser pour le test réel)
- Le composite NORMALISÉ a un fond ~**5×** celui des brutes (banc : 0,273 contre
  0,050 ; vrai jeu : 0,5-1,1 contre ~0,03) → la brute est tassée dans les BAS
  niveaux 8 bits (**médiane 1/255 contre 62/255**) → ORB aveugle → **8-9 refus sur
  12 frames** (témoin : **0 refus** sans rafraîchissement). ⇒ « rafraîchir sur
  Jamais » n'améliorait rien : la cause n'était pas le rafraîchissement, mais ce
  qu'on lui PASSAIT.
- Astrométrie : **2 frames/rôle = ÉCHEC** (« 3 inliers, échelle 1,812″/px » — le
  message EXACT d'Alain : 3 inliers, 1,794″) ; **3 frames/rôle = RÉSOLU** (111
  appariements) ; 1 frame/rôle = « 0 étoiles, image constante ».
- Le solveur RÉSOUT TOUT hors-ligne (couches, composites, avec/sans normalisation
  commune) ⇒ ni les données, ni le solveur, ni la composition ne sont en cause.
  **Piste 180° ABANDONNÉE** (Alain a trié les frames ; le RGB seul fonctionne).
- Config test « RGB » (08/10) : `norm_commune = true`, `ref_refresh = 10`, filtre
  flou actif ; 150 brutes (50/rôle) → 111 empilées, 39 refus d'ALIGNEUR.
- **Test A/B décisif (08/10)** : la MÊME brute s'aligne, mais la même brute
  **CALIBRÉE (dark) est REFUSÉE** → c'est la structure du dark qui change les
  étoiles détectées ; une frame retournée ne passe que par le chemin « triangles »
  (base = top-12, fragile).
- Une frame refusée n'est PAS empilée (`worker.py:1034-1039`).

### Outils de diagnostic jetables (hors dépôt, dans `%TEMP%`)
`avastack_diag_refresh.py` (rejeu de session : ordre + rafraîchissements),
`avastack_diag_archive.py` (archive vs source + test A/B), `jalons111-112.patch`,
`avastack_diag_astro_lrgb.py`, `avastack_diag_astro_solve.py`,
`avastack_diag_astro_session.py` (diag astrométrie du 09/10).
**Jalon 115** : `avastack_diag_astro_now.py` (compteurs fond/bruit/détection/
catalogue/appariements par couche et par composite) et
`avastack_diag_astro_replay.py` (REJEU de la session complète — alignement +
rafraîchissements — puis solve du composite produit : c'est LUI qui a reproduit
l'échec hors-ligne et prouvé le correctif de domaine).
Archives de session (`%TEMP%\avastack_frames_*` = frames réellement LUES) :
⚠ supprimées par l'appli au démarrage **6 h après** leur dernière écriture — les
copier si la preuve doit survivre. Le rôle d'une archive se DÉDUIT du NOMBRE de
frames (en-têtes perdus) : ~50-60 = L, 12-14 ×3 = R/G/B.

### Problèmes ouverts / Points d'attention
- **VALIDÉ SANS retournement SEULEMENT** : le test réel du 09/10/2026 porte sur le
  jeu M31 **d'un seul côté du méridien**. Le jeu mêlant les DEUX côtés du Pier
  (repli 180°) n'a PAS été rejoué depuis les correctifs → ne pas présenter le
  retournement au méridien comme validé.
- Les versions **v2.63.0 → v2.67.0** partent dans le MÊME commit de clôture
  (jalons 111→115) ; **paquets et release GitHub ne sont PAS encore faits**.
- ✅ FERMÉ au jalon 115 : `worker._astro_propager_restack` prend l'ancien
  empilement en couche BRUTE (même défaut de domaine que l'astrométrie).
- AVANCEMENT.md : rester ≤ 300 lignes (cf. `.clinerules`).

### Prochaines étapes
- **TEST RÉEL AVEC RETOURNEMENT** (jeu M31 des deux nuits, deux côtés du Pier) :
  c'est le seul point du chantier non validé (empilement des frames retournées +
  astrométrie). Journal (`%APPDATA%\AVAStack\journal.txt`, bouton « Journal ») ;
  un CLIC DROIT sur un libellé en copie le texte.
- Si concluant : **paquets Windows/Linux/macOS + release GitHub v2.67.0** (rien
  n'est construit ni publié à ce stade ; dernier tag publié = v2.62.1).

---

## Chantier en cours — ALIGNEMENT : retournement au méridien + astrométrie

**But** : que les frames d'UN côté du méridien (rotation ~180° par rapport au
ciel) s'empilent au lieu d'être rejetées, et que l'astrométrie (solveur +
propagation) fonctionne sur un empilement LRGB.

**État (09/10/2026 — CLÔTURE)** : **jalons 111→115 LIVRÉS, TESTÉS EN RÉEL (jeu M31
sans retournement) ET COMMITÉS/POUSSÉS** → `AVASTACK_VERSION = "2.67.0"` (v2.63.0
= retournement ACCEPTÉ ; v2.64.0 = retournement RÉELLEMENT résolu ; v2.65.0 =
correctifs composition : rafraîchissement de référence + profondeur par rôle ;
v2.66.0 = astrométrie visible au journal ; v2.67.0 = **cause de l'échec astro
trouvée et corrigée** : le solveur recevait le composite normalisé au lieu de la
couche brute). Le correctif de domaine a été **mesuré sur les VRAIES frames
hors-ligne** (composite ÉCHEC ↔ couche G RÉSOLU 94 app. / 2,466″/px) PUIS **vu
dans l'appli**. Restent : le **test du repli 180° sur un jeu des deux côtés du
Pier** et la **publication** (paquets + release GitHub).

**Règles d'or** :
- Un jalon = un banc neuf + rejeu des bancs concernés (TOUS VERTS) + garde-fou
  `bancs/_test_refactoring_garde_fou.py` VERT (syntaxe, surface 75, hash au bit).
- On ne réécrit JAMAIS un tag publié ; version + changelog + AVANCEMENT.md dans la
  même réponse ; commentaires et docstrings en FRANÇAIS.
- Le chantier de refactoring (jalons 100→110) est CLOS : plus de découpage de
  `app.py` ni de typage rétroactif.

---

## En attente / prochaine session

- **Chantier courant — TEST RÉEL AVEC RETOURNEMENT attendu** (jeu M31 des deux
  nuits, deux côtés du Pier) : seul point du chantier non validé. Ensuite
  **publication** : paquets Windows/Linux/macOS + release GitHub **v2.67.0** (le
  dernier tag publié est **v2.62.1**).
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

- **09/10/2026** : astrométrie en composition (jalons 111→115) — v2.67.0 testée OK
  (M31 sans retournement), commitée et poussée (détail : bloc « Session » ci-dessus).
- **07/10/2026** : clôture du chantier de refactoring (jalons 100→110) —
  v2.62.1 livrée, testée en réel, publiée.

