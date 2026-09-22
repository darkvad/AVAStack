# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.25.0** (`avastack/__init__.py`),
  branche `master` — **jalon 56 ÉTAPE 2 (solveur astrométrique interne) :
  banc au vert le 22/09/2026**. Jalon 55 (v2.23.3) validé par Alain en
  réel (M31 RGB), commité aca5ca5.
- **Jalon 56, étape 2 (v2.25.0, 22/09/2026) — résumé du dernier jalon** :
  - livré : `avastack/catalogues/solveur.py` (WcsTan : WCS TAN minimal
    CRVAL/CRPIX/CD, conversions pixels↔ciel, mots-clés FITS ; projection
    TAN gnomonique numpy pur ; détection d'étoiles recopiée de
    processing/stars pour éviter le cycle d'import ; triangles canoniques
    jalon 15 ; ajustement TAN Gauss-Newton + réjection 3σ) et
    `avastack/catalogues/astap.py` (wrapper astap_cli, référence
    indépendante + repli) ;
  - banc `_test_solveur_jalon56.py` TOUT AU VERT : TAN ≡ astropy.wcs
    (écart 5e-14° sur 3 parités/orientations) ; solve interne 0,07–0,10″
    de la vérité sur images synthétiques construites depuis le VRAI
    catalogue Gaia de Siril (indices exacts, bruités ~6′, parité
    inversée) ; validation croisée astap_cli ≈ interne à 0,2″ ; échecs
    PROPRES vérifiés (indices faux à 1,5°, image sans étoiles, image
    absente pour ASTAP) ;
  - PIÈGES TRANCHÉS : `-spd` d'astap_cli = 90 **+** dec (l'écho « Start
    position » a tranché — 90 − dec cherche à −dec) ; `-ra` en HEURES ;
    `-fov` = hauteur du champ en degrés ; CRPIX FITS 1-based vs tableau
    0-based (±1) ; l'affinité `np.linalg.solve(A, dst)` est (3, 2),
    partie linéaire = `M[:2,:].T` (sans la transposée, la rotation de
    départ est inversée) ; le catalogue doit être CLIPPÉ au rectangle
    indicatif AVANT le top-N (sinon le top-N du cône d'extraction n'est
    pas celui de l'image et les triangles corrects n'existent plus) ;
  - chemin d'ASTAP surchargeable par la variable d'environnement
    `AVASTACK_ASTAP` (défaut : install Windows, puis PATH).
- **Tâche en cours** : étape 3 — propagation WCS au réempilement
  (composition de transformations, PAS de re-solve à chaque frame),
  puis étape 4 (photométrie + facteurs par bande), étape 5 (application
  aux gains du stacker), étape 6 (validation Siril + test réel
  multibande).
- **Prochaine étape** : démarrer l'étape 3 à froid.

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

## 🔚 Clôture de session — 22/09/2026 (v2.25.0, jalon 56 étape 2 : livré, bancs au vert)

État exact : **jalon 56 étape 2 (solveur astrométrique interne) LIVRÉ,
banc `_test_solveur_jalon56.py` TOUT AU VERT (exit 0)** — projection TAN
conforme à astropy.wcs (5e-14°), solve interne 0,07–0,10″ de la vérité sur
images synthétiques construites depuis le VRAI catalogue Gaia (indices
exacts/bruités/parité inversée), validation croisée astap_cli ≈ interne à
0,2″, échecs propres vérifiés. Banc étape 1 relancé : toujours au vert.
Rien d'UI ni de branché au worker : le solveur est prêt, la PROPAGATION
WCS (étape 3) suit.
- Décisions de la session (accord d'Alain, reports de la veille) : SPCC
  local multibande MiniCam8M en premier puis OSC ; solveur astrométrique
  interne avec indices (pas de re-solve à chaque réempilement :
  propagation WCS par composition de transformations) ; ASTAP =
  référence indépendante/repli.
- Conventions astap_cli VÉRIFIÉES EN RÉEL (22/09/2026, CLI-2024.11.17) :
  `-ra` en heures, `-spd` = 90 + dec, `-fov` = hauteur du champ en degrés,
  succès = exit 0 + `.wcs` (matrice CD) + `PLTSOLVD=T`.
- Prochaine étape (à froid) : **étape 3 — propagation WCS au
  réempilement** (composition de transformations entre frames, re-solve
  interne seulement à la référence), puis étape 4 (photométrie + facteurs
  par bande), 5 (gains du stacker), 6 (validation Siril + réel).

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
