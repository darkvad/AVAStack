# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.29.0** (`avastack/__init__.py`),
  branche `master` — **REPLI ASTAP livré le 23/09/2026 (v2.29.0)** : quand
  AUCUN indice n'est disponible (caméra live sans en-tête FITS, ni saisie, ni
  OBJCTRA/OBJCTDEC), ASTAP tente de localiser l'empilement lui-même et son
  centre sert d'indice au solveur interne ; son WCS est le REPLI si l'interne
  refuse (`SuiviAstrometrie.adopter`, méthode « astap »). Le champ de saisie
  peut rester SEUL (focale connue, cible inconnue) : il guide le balayage.
  **CONSTAT RÉEL DÉCISIF (23/09/2026, banc + `_diag_astap_aveugle.py`)** :
  ASTAP ne balaie le ciel SANS position de départ qu'avec une base de BALAYAGE
  (G18/H18/W08/V05) ; le poste d'Alain n'a que **D80** (base « solution
  voisine ») → tout balayage échoue en ~0,4 s, quel que soit `-fov` (le même
  fichier est résolu en 0,2 s AVEC indices). L'appli SONDE donc les bases
  (`astap.bases_installees` / `balayage_possible`) et n'engage pas d'attente
  inutile : elle dit la cause et conseille AD/Dec approximatifs (le solveur
  interne tolère ~1°). Garde-fous : 1 balayage par valeur de champ, plafond 2
  par session, timeout 90 s, image temporaire bornée [0,1]. PIÈGE tranché en
  réel : `-fov` d'ASTAP = HAUTEUR du champ (l'appli raisonne en LARGEUR).
  Outil `_diag_astap_aveugle.py` embarqué dans l'installateur.
  Banc `_test_astro_branchement_jalon56.py` section [8] TOUT AU VERT
  (indices d'ASTAP → solve interne ; interne en échec → WCS ASTAP adopté ;
  échec ASTAP → état clair ; sans base de balayage → aucun essai).
- **Tâche en cours** : **étape 4 — photométrie + facteurs par bande**
  (appariement catalogue Gaia ↔ étoiles de l'accumulation via le WCS), suivie
  de l'étape 5 (application aux gains du stacker), étape 6 (validation Siril +
  test réel multibande).
- **Prochaine étape** : étape 4 (photométrie) — appariement Gaia ↔ étoiles de
  l'accumulation avec le WCS propagé, puis facteurs par bande.

## Statuts CLAUDE.md

- Leçons ÉCRITES le 19/09/2026 (accord d'Alain) : introspection des
  exports de la DLL sous le binding ; convention roue `48+n` vs `'0'`
  tranchée par l'effet physique ; SDK natif (init unique, état non
  libérable, crash → trace + sous-processus) ; identité des fichiers
  chargés avant toute interprétation ; réglage relu ≠ réglage appliqué
  (seul l'effet physique prouve).
- Leçons ÉCRITES le 20/09/2026 (accord d'Alain, « écris les 2 ») :
  jalon 13 (appariements mutuels + seuil relevé quand la décision sert
  d'ANCRE ; deux normalisations distinctes rendent une SSD aveugle —
  partager les bornes) ; jalon 24 (valider les placeholders d'un gabarit
  AVANT la substitution). Plus AUCUNE leçon en attente.

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

## 🔚 Clôture de session — 22/09/2026 (v2.26.0, jalon 56 étape 3 : livré, bancs au vert)

État exact : **jalon 56 étape 3 (propagation WCS par composition) LIVRÉ,
banc `_test_propagation_jalon56.py` TOUT AU VERT (exit 0)** — composition
exacte 2,3e-13 px vs vérité analytique, `vers_tan` ≡ astropy.wcs (2,6e-14°),
re-solve indépendant ≈ propagé à 0,46″, chaîne de réempilement exacte,
StarAligner réel 0,42 px, échecs propres vérifiés. Bancs étapes 1 et 2
relancés : toujours au vert. Découverte validée : similitude ∘ TAN = TAN
exact (propagation SANS PERTE). Rien d'UI ni de branché au worker : la
propagation est prête, le BRANCHEMENT + la PHOTOMÉTRIE par bande (étape 4) suivent.
- Décisions de la session (accord d'Alain) : SPCC local multibande
  MiniCam8M en premier puis OSC ; solveur astrométrique interne avec
  indices (pas de re-solve à chaque réempilement : propagation WCS par
  composition de transformations) ; ASTAP = référence indépendante/repli.
- Conventions astap_cli VÉRIFIÉES EN RÉEL (22/09/2026, CLI-2024.11.17) :
  `-ra` en heures, `-spd` = 90 + dec, `-fov` = hauteur du champ en degrés,
  succès = exit 0 + `.wcs` (matrice CD) + `PLTSOLVD=T`.
- **BUG CORRIGÉ EN COURS DE SESSION (v2.26.1, retour réel d'Alain)** :
  « Enregistrer l'empilement (linéaire) » écrivait le RGB avec les canaux
  sur NAXIS1 → ASIFitsView/Siril voyaient N images de 3 px de large
  (image « noire »). save_image écrit maintenant les canaux sur NAXIS3
  (convention astro) et load_image normalise en (H, W, C) ;
  `_test_save_rgb_axes.py` au vert. La note d'alors (« les valeurs > 1 d'un
  composite — jusqu'à ~14 sur M31 — sont normales ») a été CORRIGÉE en
  v2.27.1 : ces valeurs rendaient le fichier NON résolvable par ASTAP et
  « saturé » pour tout lecteur qui suppose [0,1]. Ce n'était bien PAS la
  cause de l'image noire (c'était NAXIS1 = 3). Bancs jalon 14 / save
  linéaire / worker compo repassés au vert.
- **PRIORITÉ RÉSOLUE (v2.27.1, 22/09/2026) — l'empilement linéaire d'une
  composition est maintenant RÉSOLVABLE par ASTAP** (consigne d'Alain :
  « l'empilement linéaire en sortie, mode dossiers (compo RGB), est saturé
  et non solvable par ASTAP ») :
  - MESURES sur son fichier (`c:\Astro\test\m31_test_solve.fits`,
    3×2165×3839 float32, canaux sur NAXIS3 — axes donc BONS depuis v2.26.1) :
    fond à 0,02, **max 14,1**, 0,3 % des pixels > 1 ; en-tête sans aucun
    mot-clé d'échelle ;
  - DIAGNOSTIC ASTAP (astap_cli CLI-2024.11.17) : **« Only 0 stars found in
    image »** → `ERROR=Not enough stars` dans le .ini ; le MÊME contenu borné
    à 1 se résout en 0,2 s (143 quads sur 144). Cause : sa conversion 16 bits
    écrase un fond à 0,04. Et un lecteur qui suppose [0,1] clippe le cœur de
    M31 + les cœurs d'étoiles en blanc — l'image « paraît saturée »
    (aperçus PNG comparés : clip-à-1 vs percentiles) ;
  - CAUSE RACINE : `composition.normaliser` (percentiles 0,25/99,7 SANS
    clip) — sur M31 le cœur vaut ~14× le p99,7. Le composite est la SEULE
    donnée de l'appli hors [0,1], alors que VeraLux (clip d'entrée + piège
    max > 1,1 → /65535), le débruitage, les sorties TIFF/PNG et ASTAP
    supposent tous [0,1] ;
  - FIX : `images.borner_lineaire(arr, entete)` — UN facteur GLOBAL (jamais
    par canal : couleurs et linéarité au bit près), consigné dans l'en-tête
    (**AVASCALE**, réversible, + HISTORY), nan/inf neutralisés et comptés
    (**AVANAN**). Appliqué aux 3 écritures linéaires (empilement, résultat
    traité, canaux `canal_*.fit`) ; no-op dès que max ≤ 1 ;
  - POURQUOI PAS au niveau du composite : VeraLux travaille en valeurs
    ABSOLUES (target_bg, logD résolu) → changer l'échelle du composite
    changerait la vue live et le rendu « tel que vu ». **La vue ne change
    PAS** : ce sont les FICHIERS qui redeviennent lisibles ;
  - BANCS : `_test_save_lineaire_echelle.py` (nouveau) TOUT AU VERT — [1]
    bornage + AVASCALE + réversibilité, [2] no-op si ≤ 1, [3] nan/inf, [4]
    worker réel → fichier borné / (C,H,W) / FILTER / proportionnalité, [5]
    mono 0,25 au bit près, [6] TIFF : 693 px blancs → 1, [7] **ASTAP RÉEL
    résout le fichier borné : 2,4639″/px ≈ la brute G du même setup** (et
    l'original non borné reste non résolu — contrôle informatif, un outil
    tiers ne fait pas échouer le banc) ; `_test_solveur_reel_m31.py` passe
    désormais ASTAP sur la version BORNÉE du composite : Δ max 4,73″,
    Δ échelle 0,0010″/px, Δ orientation locale 0,006° ;
  - bancs repassés au vert : axes FITS couleur, save linéaire (v2.5.1),
    worker compo (jalon 19 — attendu adapté : le fichier = composite /
    AVASCALE), compo UI (canaux), calib compo, re-stack compo, tel que vu ;
  - installateur rebuili (v2.27.1).
- **RÉSOLU (v2.27.0, 22/09/2026) — le solve INTERNE résout maintenant les
  vraies images d'Alain** : `_diag_solve_reel.py` avait montré l'échec en
  réel (empilement composite 2,6° @ 243 mm ET brute G N.I.N.A. : « pas assez
  de correspondances mutuelles (4) »). Cause : sur un champ large/riche, le
  top-12 d'image ≡ top-20 de catalogue PAR INVARIANTS ne tient plus (listes
  qui ne coïncident plus : saturation, limmag, bruit) → l'affinité exacte
  3 points est dégénérée. Correctif : **repli RANSAC de paires**
  (`_ransac_paires`, esprit astrometry.net) — vote (échelle, angle) sur
  toutes les paires top-60 image × top-120 catalogue en 4 parités, similitude
  exacte 2 points évaluée par appariements mutuels, puis stabilisation
  Umeyama à rayon croissant ; les DEUX chemins passent par le même
  `_finaliser` (Gauss-Newton + 3σ + garde-fous) et se remplacent quand l'un
  est REJETÉ ; `info["methode"]` trace le chemin retenu.
  - banc RÉEL `_test_solveur_reel_m31.py` AU VERT : composite 2,6° → 86
    étoiles, rms 0,59 px, 2,4650″/px (centre à 20″ des indices) ; brute G →
    70 étoiles, rms 0,44 px, 2,4652″/px. Même optique → échelles concordant
    au millième (contrôle croisé gratuit) ;
  - **validation croisée ASTAP (brute G)** : écart max 2,78″ sur bords +
    centre, Δ échelle 0,0013″/px, Δ orientation locale 0,004° ;
  - pièges : le vote doit comparer des PIXELS à des PIXELS (catalogue passé
    dans la grille indicée) ; remettre `best_M = None` après échec des
    mutuelles (sinon `_finaliser(None, None, …)` fabrique un axe parasite) ;
    l'angle du CD brut n'est PAS comparable entre deux CRVAL différents
    (0,57° d'écart apparent pour des positions concordant à 2,8″) ;
  - bancs jalon 56 étapes 1/2/3 relancés : TOUJOURS AU VERT (le chemin
    triangles reste le principal, le repli est un filet).
- Prochaine étape (à froid) : **branchement au worker** (solve une fois
  sur l'accumulation avec les indices de la cible ; propagation à chaque
  re-stack : UN seul alignement nouvelle référence ↔ ancien empilement),
  puis **étape 4 — photométrie + facteurs par bande**, 5 (gains du
  stacker), 6 (validation Siril + réel).

Sessions précédentes : v2.23.3 (jalon 55 : gains compo temps réel,
aca5ca5, validé Alain) ; v2.21.10 (jalons 50-52, banc Touptek +
ergonomie caméra, 7d3034e, validés par Alain) — détail dans l'historique
git et le changelog du source.

## Pièges récents (rappels opérationnels)

- **LIMITE QHY (toujours valable)** : après « ■ Arrêter », relancer
  l'appli — le binding qhyccd n'expose AUCUNE libération du SDK (état
  irréinitialisable dans le process) ; le banc QHY l'annonce et conseille
  fermer + relancer.
- Entry/Combobox/`var.get()` Tkinter interdits hors thread principal —
  lire les widgets DANS Tk puis passer les valeurs au worker (bouchons
  `_Val` dans l'appli) ; toute contrôle `_on_*` finit par
  `_refresh_preview()`, les `_sync_*_vue` ne touchent qu'à l'ÉTAT.
- **Installateur à REBUILDER avant tout test réel dès que la passe de code
  touche PLUS d'un ou deux fichiers** (`powershell -NoProfile
  -ExecutionPolicy Bypass -File installer\windows\build_avastack.ps1`) —
  à la charge de l'agent, sans qu'Alain ait à le demander.

## Clôtures précédentes

- 21/09/2026 (v2.23.3, aca5ca5) : jalon 55 VALIDÉ PAR ALAIN en réel
  (M31 RGB, mode dossier) — gains R/G/B temps réel, image équilibrée.
  Rappel opérationnel : équilibrage auto OU Linear Fit re-normalisent les
  canaux → gains manuels sans effet tant que l'un des deux est actif ;
  pour réchauffer les tons, MONTER R. Repli si régression : v2.22.0
  (225f026).
- 20/09/2026 : TOUTES les validations matérielles (QHY miniPC, Player
  One, SVBONY, roue, TEC, cadence 39-46, ergonomie 47-48) CLOS — verdicts
  d'Alain ; bancs `_diag_camera_*.py` conservés pour diagnostic futur.
- Crash OpenCV 5/OpenCL au teardown (`cv2.ocl.setUseOpenCL(False)`) ;
  tests `ui.App` hermétiques (`ui.CONFIG = {}` + sauver_config
  intercepté) ; images de tests bruitées (sinon 0 étoile).
- Ne JAMAIS mélanger grid et pack dans le même conteneur Tk (attrapé par
  le test UI du banc POA : `_tkinter.TclError` « grid is already
  managing its content windows »).
- SDK natif : chargement UNE fois par process ; crash natif non
  rattrapable → tracer chaque étape dans un fichier ; vérifier
  l'identité des fichiers réellement chargés AVANT d'interpréter un
  plantage (les bancs affichent DLL + module + dates).
- PIÈGE LANCEMENT : `python3` ≠ venv — toujours `python AVAStack.py`.
- Ordre de la chaîne (Alain, 16/09/2026) : recadrage → gradient →
  débruitage → netteté → étirement. Débruitage : code gelé, cases
  décochées (décision du 16/09/2026) — ne pas retoucher sans nouvelle
  demande ; défauts des traitements confirmés (live = désactivé, NLM,
  force 0,5 ; externe = désactivé, GraXpert IA, force 0,5).
