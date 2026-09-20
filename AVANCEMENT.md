# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.20.4** (`avastack/__init__.py`),
  branche `master` — jalon 35 CORRIGÉ EN DEV (tout au vert), **COMMITÉ ET
  POUSSÉ (0321914)**, **installateur v2.20.4 REBUILD** — **TEST RÉEL setup 2
  (Player One) : POINT 3 VALIDÉ PAR ALAIN le 20/09/2026** (boutons ❄ POA
  activés). (`installer/windows/output/avastack-setup.exe`) — copie de
  l'installateur vers le miniPC à faire.
- **Dernier jalon (35, 20/09/2026) — BOUTONS ❄ GRISÉS SUR LA POA (point 3
  de l'item 2d)** :
  - cause : `cam_pilotee` (la caméra que le worker sonde/pilote) était
    resté QHY-only depuis le jalon 25 → le sondage
    `lire_refroidissement()` n'était JAMAIS lancé pour Player One /
    SVBONY / ZWO / Touptek — les implémentations TEC du jalon 33 étaient
    saines mais jamais appelées ;
  - correction : constante `CAMERAS_PILOTEES` (toutes les caméras SDK)
    aux 3 points d'installation de la caméra (app.py : connexion auto
    jalon 32, chemin QHY, repli « ▶ Démarrer ») ; les no-ops de
    CameraBase garantissent l'absence d'effet pour une marque sans
    TEC/roue (boutons ❄ grisés, combobox désactivée) ; garde
    `hasattr(stop_live)` sur le chemin filtre (seul QHY l'expose) ;
  - Tests : _test_pilotage_jalon35 14/14 (NOUVEAU — câblage app boutons
    ❄ POA + SVBONY) ; jalon33 21/21 ; jalon32 25/25 ; jalon31 14/14 ;
    jalon34 21/21.
- **Reste à déboguer de l'item 2d : point 4** (connexion auto SVBONY
  refusée « Propriétés illisibles ») — comparer avec le banc de diag
  SVBONY VALIDÉ EN RÉEL (référence).
- **LIMITE QHY (toujours valable)** : après « ■ Arrêter », relancer
  l'appli — le binding qhyccd n'expose AUCUNE libération du SDK (état
  irréinitialisable dans le process) ; le banc QHY l'annonce et conseille
  fermer + relancer.

## ⏭ Validations réelles en attente

1. **QHY miniPC (v2.15.0 installée)** : connexion verte SANS démarrer
   l'empilement, TEC (alim 12 V), filtre avant puis PENDANT l'empilement,
   offset + saisies, ⏏ Déconnecter (en cas d'échec : log
   `%TEMP%\avastack_qhy_debug.log` à transmettre).
2. **Banc Player One (2e setup)** : cf. jalon 28 ci-dessus — détection
   complète + verdict + TEC + bin + ROI + cadence ; copier le banc dans
   le dossier d'installation si testé depuis le miniPC.
2b. **TEST RÉEL jalon 32 + 33 (v2.19.0/v2.20.0)** : la détection des
   capacités + UI aux bornes réelles s'exécute à la connexion de CHAQUE
   marque SDK, et le TEC POA/SVBONY est DÉSORMAIS PILOTABLE (les boutons
   ❄ s'activent automatiquement quand la caméra répond). Sur les deux
   setups (POA Uranus-C Pro puis SVBONY SV305C guidage) : choisir la
   source → connexion automatique → VÉRIFIER les bornes des curseurs
   (POA : gain 0–750, offset 0–250, expo 10 µs–2000 s, consigne -50 à 30 ;
   SV305C : gain 0–450, offset 0–255, expo 36 µs–2000 s) → boutons ❄
   activés, consigne posée, descente de température constatée dans le
   label (⚠ SV305C : vérifier que le refroidissement est branché —
   sans TEC les boutons restent gris, c'est normal) → « ▶ Démarrer » →
   ⏏ Déconnecter (le TEC doit être coupé à la déconnexion).

2d. **À DÉBOGUER avant de démarrer une nouvelle session** — 4 points
   relevés EN RÉEL par Alain le 20/09/2026 (setup 2) :
   1. ✅ TRAITÉ ET VALIDÉ EN RÉEL (jalon 34, v2.20.3) — libellé « Échelle
      longue » généré (pivot 5 s + borne max réelle), coupure à 5 s.
   2. ✅ TRAITÉ ET VALIDÉ EN RÉEL (jalon 34, v2.20.1) — `_fmt_expo` sans
      notation scientifique : « 2 000 s » au lieu de « 2e+03 s ».
   3. ✅ CORRIGÉ ET VALIDÉ EN RÉEL (jalon 35, v2.20.4) — cause trouvée :
       `cam_pilotee`
       (sondage/pilotage du worker) était resté QHY-only depuis le jalon 25,
       le sondage `lire_refroidissement()` n'était JAMAIS lancé hors QHY
       (les implémentations TEC du jalon 33 n'étaient jamais appelées).
       Correctif : `CAMERAS_PILOTEES` = toutes les caméras SDK (app.py).
       Boutons ❄ POA activés — validé par Alain le 20/09/2026.
   4. **SVBONY : connexion auto REFUSÉE** — message « SVBONY (SDK) :
      connexion impossible — Propriétés illisibles : SVBONY SV305C »
      lors de la détection automatique, alors que LE BANC DE DIAG
      SVBONY AVAIT ÉTÉ VALIDÉ EN RÉEL (ouverture + TEC + flux OK,
      _diag_camera_svbony.py). À déboguer : comparer le chemin
      d'ouverture de l'app (`_connecter_sdk` → `SVBGetCameraProperty`)
      avec celui du banc.
2c. **QHY par ctypes (jalon 30, CODE FAIT le 20/09/2026)** : la sonde ctypes est dans le banc (_diag_camera_qhy.py, sous-processus isolé) : plages via GetQHYCCDParamMinMaxStep (le nom réel dans les exports de la DLL — « ...MinMax » tout court n'existe pas) + roue via les fonctions natives CFW. RESTE LE TEST RÉEL (demain matin, MiniCam8M) : (a) « 📏 Plages » → noter min/max/step de expo/gain/offset/TEC pour câbler l'UI ; (b) « 📖 Statut CFW » → vérifier détection + statut ; (c) « 🌀 Tourner » → position 1 puis 2, CONFIRMATION PAR RELECTURE ET EFFET PHYSIQUE (slot vide/opaque → le flux change) ; trancher la convention binding 48+n contre doc QHY '0' = position 1.
3. **Jalon 24** : gradient/débruitage par couche (live + externe) ;
   garde-fous GraXpert jalon 23b en mono ; SCNR doux (jalon 23).
4. **Roue à filtres MiniCam8M** : à tester au banc avec les DEUX voies (jalon 30) : la sonde ctypes native (bouton « 🌀 Tourner », ordre ASCII '0'+(position-1), statut relu) et la voie binding (écriture 17=48+n). **Aucun code appli avant le verdict par l'EFFET PHYSIQUE.**
5. Suivi alignement en direct (« Align. : Δ(…) θ(…) » / « Frames non
   alignées »).

## Pièges récents (rappels opérationnels)

- Entry/Combobox/`var.get()` Tkinter interdits hors thread principal —
  lire les widgets DANS Tk puis passer les valeurs au worker (appliqué
  dans le banc POA ; bouchons `_Val` dans l'appli).
- Ne JAMAIS mélanger grid et pack dans le même conteneur Tk (attrapé par
  le test UI du banc POA : `_tkinter.TclError` « grid is already
  managing its content windows »).
- Crash OpenCV 5/OpenCL au teardown (`cv2.ocl.setUseOpenCL(False)`) ;
  tests `ui.App` hermétiques (`ui.CONFIG = {}` + sauver_config
  intercepté) ; images de tests bruitées (sinon 0 étoile).
- SDK natif : chargement UNE fois par process ; crash natif non
  rattrapable → tracer chaque étape dans un fichier ; vérifier
  l'identité des fichiers réellement chargés AVANT d'interpréter un
  plantage (les bancs affichent DLL + module + dates).
- Ordre de la chaîne (Alain, 16/09/2026) : recadrage → gradient →
  débruitage → netteté → étirement. Débruitage : code gelé, cases
  décochées (décision du 16/09/2026) — ne pas retoucher sans nouvelle
  demande ; défauts des traitements confirmés (live = désactivé, NLM,
  force 0,5 ; externe = désactivé, GraXpert IA, force 0,5).
- PIÈGE LANCEMENT : `python3` ≠ venv — toujours `python AVAStack.py`.
- **Installateur à REBUILDER avant tout test réel dès que la passe de code
  touche PLUS d'un ou deux fichiers** (`powershell -NoProfile
  -ExecutionPolicy Bypass -File installer\windows\build_avastack.ps1`) —
  à la charge de l'agent, sans qu'Alain ait à le demander (consigne du
  20/09/2026, écrite dans CLAUDE.md).

## Statuts CLAUDE.md

- Leçons ÉCRITES le 19/09/2026 (accord d'Alain) : introspection des
  exports de la DLL sous le binding ; convention roue `48+n` vs `'0'`
  tranchée par l'effet physique ; SDK natif (init unique, état non
  libérable, crash → trace + sous-processus) ; identité des fichiers
  chargés avant toute interprétation ; réglage relu ≠ réglage appliqué
  (seul l'effet physique prouve).
- Leçons PROPOSÉES, EN ATTENTE d'approbation d'Alain (ne pas écrire sans
  accord) : jalon 13 (appariements mutuels + seuil relevé quand la
  décision sert d'ANCRE ; deux normalisations rendent une SSD aveugle —
  partager les bornes) ; jalon 24 (valider les placeholders d'un gabarit
  AVANT la substitution).

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

## 🔚 Clôture de session — 20/09/2026 (v2.20.4, jalon 35)

État exact : **v2.20.4 COMMITÉE ET POUSSÉE (0321914), installateur
REBUILD, POINT 3 DE L'ITEM 2D VALIDÉ EN RÉEL PAR ALAIN** (boutons ❄ POA
activés sur le setup 2). Contenu du jalon : les boutons ❄ TEC POA
restaient grisés parce que `cam_pilotee` (la caméra que le worker
sonde/pilote) était resté QHY-only depuis le jalon 25 — les
implémentations TEC du jalon 33 n'étaient JAMAIS appelées pour
POA/SVBONY/ZWO/Touptek. Correctif : constante `CAMERAS_PILOTEES` (toutes
les caméras SDK) aux 3 points d'installation (app.py) + garde
`hasattr(stop_live)` sur le chemin filtre. Tout au vert en dev :
_test_pilotage_jalon35 14/14 (NOUVEAU), jalon33 21/21, jalon32 25/25,
jalon31 14/14, jalon34 21/21.

**Prochaine étape (session NEUVE)** : (1) déboguer le point 4 de l'item
2d — DERNIER POINT RESTANT (connexion auto SVBONY refusée « Propriétés
illisibles ») EN COMPARANT le chemin d'ouverture de l'app
(`_connecter_sdk` → `SVBGetCameraProperty`) avec le banc de diag SVBONY
validé en réel ; (2) copier l'installateur v2.20.4 vers le miniPC +
tests réels setup 1 (MiniCam8M) et SV305C une fois le point 4 réglé.

Sessions précédentes : v2.20.3 (jalon 34, points 1-2 de l'item 2d,
VALIDÉS EN RÉEL par Alain, ea7108c) ; v2.20.0 (jalons 32 + 33, e70c6d7) —
détail dans l'historique git et le changelog du source.
