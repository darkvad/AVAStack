# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.20.0** (`avastack/__init__.py`),
  branche `master` — jalons 32+33 testés en dev (tous les tests au vert),
  **installateur v2.20.0 REBUILD** (`installer/windows/output/
  avastack-setup.exe`) — **COMMITÉ SANS POUSSER** (poussée + copie de
  l'installateur vers le miniPC à faire).
- **Dernier jalon (33, 20/09/2026) — PILOTAGE TEC PLAYER ONE / SVBONY**
  (demande d'Alain : « il faut le faire quand la caméra le supporte ») :
  - le mécanisme app était DÉJÀ générique depuis le jalon 26 (sondage
    `lire_refroidissement` à la connexion → boutons ❄ activés, demandes
    consigne/arrêt exécutées dans le thread de travail, rafraîchissement
    2 s) : seules les implémentations SDK manquaient (no-op de la base) ;
  - `PlayerOneCamera` : consigne POA_TARGET_TEMP (17, int OU float selon
    les attributs) PUIS POA_COOLER ON (18) — ordre éprouvé par le banc ;
    lire → (temp °C [ctrl 3 FLOAT], PWM 0-255 [puissance % ctrl 16
    convertie], consigne) ; arrêt = POA_COOLER OFF ; sonde POASonde
    construite UNE seule fois (cache) ; message « vérifier l'alim 12 V »
    si le SDK refuse ;
  - `SVBonyCamera` : CoolerEnable (14) PUIS TargetTemp ×10 (15 — unités
    de 0,1 °C, éprouvé par le banc) ; lire → (temp ctrl 16 /10, PWM
    [puissance % ctrl 17], consigne ctrl 15 /10) ; arrêt = CoolerEnable 0 ;
  - les deux n'occupent JAMAIS une caméra sans TEC : `lire_refroidissement`
    → None → l'app laisse les boutons ❄ grisés (comportement voulu) ;
  - **Point 1 tranché (décision Alain du 20/09)** : la définition dupliquée
    de `_deconnecter_camera` est supprimée — la version du 19/09 (worker
    arrêté D'ABORD dans `_on_close`, close dans le thread Tk) est celle qui
    fonctionnait, elle est conservée et documentée dans le code ;
  - Tests : _test_tec_jalon33 20/20 (NOUVEAU — doubles de DLL fidèles aux
    relevés réels) ; jalon32 25/25 ; _test_capacites 29/29 ; jalon31 15/15 ;
    POA 29/29 ; QHY 33/33 ; sliders 6 OK.
- **Jalon 32 (v2.19.0, FAIT)** : capacités dynamiques pour TOUTES les
  marques — `CID_CONTROLES_PAR_MARQUE` (ids par marque des enums SDK),
  `Capacites.plage(rôle)`, `extras` par contrôle POA/SVB/ZWO, connexion
  automatique à la détection pour toutes les marques SDK (thread dédié,
  `_installer_camera_connectee` facteur commun).
- **Jalon 31 (v2.18.0, FAIT)** : UI dynamique à la connexion QHY (curseurs,
  expo, TEC, roue aux bornes réelles, sonde native qhyct.py) ; jalon 30 =
  sonde ctypes QHY dans le banc (validé en réel : plages MinMaxStep, roue 8
  slots) ; jalon 29/28 = capacités par marque + bancs POA et SVBONY validés
  en réel ; v2.15.x = offset QHY, saisies expo/gain/offset, TEC, roue.
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

## 🔚 Clôture de session — 20/09/2026 (v2.19.0, jalon 32)

État exact : **v2.19.0 testée en dev, NON committée** (tout est au vert :
jalon32 25/25, capacités 29/29, jalon31 15/15, POA 29/29, QHY 33/33,
sliders OK). Réalisé : le câblage dynamique (capacités → UI aux bornes
réelles) s'applique désormais À LA CONNEXION DE TOUTES LES MARQUES SDK,
pas seulement QHY — cid par marque (`CID_CONTROLES_PAR_MARQUE` +
`Capacites.plage(rôle)`, finis les cid QHY littéraux qui auraient donné
des bornes fausses chez POA/SVBONY), extras remplies par les sondes
POA/SVB/ZWO, connexion automatique à la détection (thread, comme QHY),
facteur commun `_installer_camera_connectee`. AVANCEMENT.md à jour
(jalon 32 + item 2b réécrit). Détails complets : changelog v2.19.0 dans
`avastack/__init__.py`.

**Prochaine étape** : (1) committer/pousser v2.19.0 + REBUILDER
l'installateur ; (2) test réel miniPC : MiniCam8M (vérifier bornes QHY
comme prévu au jalon 31) PUIS setup 2 : POA Uranus-C Pro et SV305C guidage
(connexion auto → vérifier les bornes affichées contre les relevés
POA 0–750/0–250/10 µs–2000 s/-50→30 et SVB 0–450/0–255/36 µs–2000 s) ;
(3) trancher avec Alain le double `_deconnecter_camera` (détail dans
l'état actuel) ; (4) chantier candidat : pilotage TEC POA/SVBONY
(consigne + lecture température) — les bornes s'affichent déjà mais les
classes restent en no-op.

Session précédente (v2.18.0, jalon 31) : câblage dynamique QHY (sonde
native qhyct.py, curseurs/TEC/roue aux bornes réelles), commitée bb84f72,
installateur rebuildé — le test réel MiniCam8M reste à faire avec la
v2.19.0.
