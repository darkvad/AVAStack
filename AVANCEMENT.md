# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.20.5** (`avastack/__init__.py`),
  branche `master` — jalon 36 CORRIGÉ EN DEV (tout au vert), **COMMITÉ ET
  POUSSÉ (c09e191)**, **installateur v2.20.5 REBUILD**
  (`installer/windows/output/avastack-setup.exe`) — copie de l'installateur
  vers le miniPC à faire + TEST RÉEL SV305C à faire.
- **Dernier jalon (36, 20/09/2026) — CONNEXION AUTO SVBONY RÉTABLIE (point 4
  de l'item 2d, DERNIER POINT DE L'ITEM)** :
  - cause (constat RÉEL du banc `_diag_camera_svbony.py` du 19/09/2026,
    déjà consigné dans le banc) : le SDK SVBONY REFUSE
    `SVBGetCameraProperty` tant que la caméra n'est PAS ouverte, alors que
    la doc (clone ZWO) recommande fiche AVANT ouverture ;
    `SVBonyCamera.open()` lisait donc la fiche AVANT `SVBOpenCamera` et
    levait « Propriétés illisibles » SANS JAMAIS tenter l'ouverture —
    alors que le banc, qui ouvre d'abord, fonctionne ;
  - correction : ordre inversé dans `open()` — `SVBOpenCamera` D'ABORD,
    fiche ENSUITE ; fiche encore illisible → `SVBCloseCamera` propre avant
    l'échec (pas de caméra orpheline) ; `SVBSetAutoSaveParam(0)` à
    l'ouverture (constat réel du banc du 20/09 : le SDK recharge ses
    paramètres sauvegardés au redémarrage — expo/gain hérités sinon) ;
  - Tests : _test_connexion_svbony_jalon36 8/8 (NOUVEAU — double de DLL
    qui rejoue le refus pré-ouverture + vérification d'ordre) ;
    _test_capacites 29/29 ; _test_camera_playerone 29/29 ; jalon33 20/20 ;
    jalon35 15/15 ; jalon31 15/15 ; jalon32 25/25 ; jalon34 21/21.
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
   4. ✅ CORRIGÉ EN DEV (jalon 36, v2.20.5) — cause (constat réel du banc
      SVBONY du 19/09) : le SDK refuse `SVBGetCameraProperty` tant que la
      caméra n'est pas ouverte ; l'app lisait la fiche AVANT
      `SVBOpenCamera` → « Propriétés illisibles » sans tenter l'ouverture.
      Correctif : ordre inversé (ouverture d'abord, fiche ensuite) + close
      propre + `SVBSetAutoSaveParam(0)`. **TEST RÉEL SV305C À FAIRE PAR
      ALAIN** (installation v2.20.5 : connexion auto → bornes curseurs →
      TEC ⚠ alim 12 V → « ▶ Démarrer » → ⏏ Déconnecter).
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

## 🔚 Clôture de session — 20/09/2026 (v2.20.5, jalon 36)

État exact : **v2.20.5 COMMITÉE ET POUSSÉE (c09e191), installateur REBUILD,
POINT 4 DE L'ITEM 2D CORRIGÉ EN DEV** — l'item 2d n'a plus que des tests
réels en attente. Contenu du jalon : la connexion auto SVBONY était refusée
(« Propriétés illisibles : SVBONY SV305C ») parce que `open()` lisait la
fiche `SVBGetCameraProperty` AVANT `SVBOpenCamera`, alors que le SDK SVBONY
(constat réel du banc du 19/09/2026) refuse la fiche tant que la caméra
n'est pas ouverte — l'app levait donc l'erreur SANS JAMAIS tenter
l'ouverture. Correctif : ordre inversé (ouverture d'abord, fiche ensuite),
close propre si la fiche reste illisible, `SVBSetAutoSaveParam(0)` à
l'ouverture (paramètres hérités sinon, constat banc du 20/09). Tout au
vert en dev : _test_connexion_svbony_jalon36 8/8 (NOUVEAU),
_test_capacites 29/29, _test_camera_playerone 29/29, jalon33 20/20,
jalon35 15/15, jalon31 15/15, jalon32 25/25, jalon34 21/21.

**Prochaine étape (session NEUVE)** : (1) copier l'installateur v2.20.5
vers le miniPC ; (2) TEST RÉEL SV305C (setup 2) sur la connexion auto
« Propriétés illisibles » corrigée : connexion auto → bornes curseurs
(gain 0–450, offset 0–255, expo 36 µs–2000 s) → boutons ❄ (⚠ alim 12 V) →
« ▶ Démarrer » → ⏏ Déconnecter ; (3) tests réels setup 1 (MiniCam8M) :
TEC + roue à filtres (point 2c : plages + CFW, verdict par EFFET
PHYSIQUE).

Sessions précédentes : v2.20.4 (jalon 35, point 3 de l'item 2d, VALIDÉ EN
RÉEL par Alain, 0321914) ; v2.20.3 (jalon 34, points 1-2, ea7108c) —
détail dans l'historique git et le changelog du source.
