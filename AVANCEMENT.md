# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.26.0** (`avastack/__init__.py`),
  branche `master` — **jalon 56 ÉTAPE 3 (propagation WCS par composition) :
  banc au vert le 22/09/2026**. Jalon 55 (v2.23.3) validé par Alain en
  réel (M31 RGB), commité aca5ca5.
- **Jalon 56, étape 3 (v2.26.0, 22/09/2026) — résumé du dernier jalon** :
  - livré : `avastack/catalogues/propagation.py` (numpy pur, SANS
    dépendance vers processing — le cycle d'import resterait interdit) :
    `propager(wcs_ref, M)` → `WcsCompose`, le WCS EXACT du repère
    transformé (M en convention ALIGNEUR : frame → référence, warpAffine) ;
    `compose_M` / `inverse_M` pour les chaînes de réempilement
    (W1 = propager(W0, M10) — UN SEUL alignement entre anciennes et
    nouvelles grilles) ; `WcsCompose.vers_tan()` ré-ajuste un WcsTan
    équivalent pour les en-têtes FITS (init analytique) ;
  - banc `_test_propagation_jalon56.py` TOUT AU VERT : composition exacte
    vs vérité analytique (2,3e-13 px), `vers_tan` ≡ astropy.wcs (2,6e-14°),
    re-SOLVE indépendant (étape 2) de l'image warpée ≈ propagé à 0,46″,
    chaîne de réempilement G0→G1→frame exacte, StarAligner RÉEL (sens des
    matrices) 0,42 px, échecs propres (NaN, forme, dégénérée, échelle,
    WCS absent, vers_tan sans forme) ;
  - DÉCOUVERTE (à retenir) : l'aligneur n'estime que des SIMILITUDES
    (`estimateAffinePartial2D`) et la composition d'un TAN avec une
    similitude est EXACTEMENT un autre TAN (rotation 3D du point tangent)
    → propagation SANS PERTE, le ré-ajustement retombe au bruit machine
    (2,6e-11 px) ;
  - PIÈGE SENS DES MATRICES tranché au banc : M d'aligneur = frame→référence ;
    `vers_radec` lit le ciel à M(p) (le pixel p montre le contenu arrivé de
    M(p)), `vers_pixels` pose le ciel en M⁻¹(p_ref) — confondu une fois
    (46 px), tranché par la vérité analytique ;
  - bancs étapes 1 et 2 relancés : toujours au vert.
- **Tâche en cours** : étape 4 — photométrie + facteurs par bande
  (appariement catalogue Gaia ↔ étoiles de l'accumulation via le WCS),
  puis étape 5 (application aux gains du stacker), étape 6 (validation
  Siril + test réel multibande).
- **Prochaine étape** : branchement au worker (solve sur l'accumulation
  avec les indices de la cible, propagation à chaque re-stack), puis
  l'étape 4 à froid.

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
- **TEST RÉEL PRÊT (à la charge d'Alain)** : `_diag_solve_reel.py` —
  résout l'astrométrie d'une VRAIE image (empilement M31 du jalon 55…) avec
  le solveur INTERNE, confronte à ASTAP, verdict ″. Ex. :
  `python _diag_solve_reel.py <stack.fit> --ra 0h42m44s --dec +41d16m09s --focal 1280 --pixel 2.9`
  (ou `--champ 0.50` ; sans --ra/--dec, ASTAP d'abord et son centre sert
  d'indice). Validé sur synthétique (centre exact, garde-fous d'échelle OK).
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
