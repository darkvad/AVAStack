# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.20.6** (`avastack/__init__.py`),
  branche `master` — jalon 37 CORRIGÉ EN DEV (tout au vert), **COMMITÉ ET
  POUSSÉ (a8a3930)**, **installateur v2.20.6 REBUILD**
  (`installer/windows/output/avastack-setup.exe`) — copie de l'installateur
  vers le miniPC à faire + TEST RÉEL jalon 37 à faire.
- **Dernier jalon (37, 20/09/2026) — SONDE TEC SVBONY PAR L'EFFET
  (contrôles présents ≠ TEC présent)** :
  - constat RÉEL d'Alain (test SV305C du 20/09, connexion du jalon 36 OK) :
    sa SV305C SANS TEC affiche quand même les contrôles TEC 14-17
    (temp 20 °C, puissance 0 % — valeurs bidon) et « Réguler » levait
    « CoolerEnable refusé par le SDK — vérifier l'alimentation 12 V »
    (firmware probablement commun avec la SV305C Pro refroidie) ;
  - cause : le SDK énumère les contrôles TEC même sans TEC physique — la
    présence de contrôles ne prouve RIEN ;
  - correction (verdict par l'EFFET) : `detecter_capacites()` TENTE
    `CoolerEnable = 1` — refus → `cap.tec` False + note dans extras +
    `lire_refroidissement()` → None → **boutons ❄ RESTENT GRISÉS** ;
    succès → TEC présent ET état initial de CoolerEnable RESTAURÉ (ne pas
    laisser le TEC démarré pour une détection). Compatibilité : les bancs
    qui appellent `lire_refroidissement()` sans `detecter_capacites()`
    gardent l'ancien comportement (défaut = pilotable) ;
  - Tests : _test_tec_sonde_jalon37 11/11 (NOUVEAU) ; _test_capacites
    29/29 ; jalon36 8/8 ; jalon33 20/20 ; jalon35 15/15 ;
    _test_camera_playerone 29/29 ; jalon31 15/15 ; jalon32 25/25 ;
    jalon34 21/21.
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

2d. **Item 2d CLOS** — les 4 points relevés en réel par Alain le
    20/09/2026 (setup 2) sont traités : 1-2 validés en réel (jalon 34),
    3 validé en réel (jalon 35), 4 validé en réel (jalon 36) + sonde TEC
    par l'effet en suivi (jalon 37, test réel ci-dessous).
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
   4. ✅ **VALIDÉ EN RÉEL PAR ALAIN le 20/09/2026** (jalon 36, v2.20.5) —
      connexion auto SV305C OK après correction de l'ordre
      (ouverture d'abord, fiche ensuite). Résidu constaté au test → jalon 37
      (v2.20.6) : contrôles TEC affichés sur une caméra SANS TEC → sonde
      par l'EFFET (voir jalon 37 ci-dessus), boutons ❄ grisés attendus.
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

## 🔚 Clôture de session — 20/09/2026 (v2.20.6, jalon 37)

État exact : **v2.20.6 COMMITÉE ET POUSSÉE (a8a3930), installateur REBUILD,
ITEM 2D ENTIÈREMENT CLOS** — point 4 VALIDÉ EN RÉEL par Alain (connexion
auto SV305C OK, correctif jalon 36) + jalon 37 en suivi : sa SV305C SANS
TEC affichait quand même les contrôles TEC 14-17 (temp 20 °C, puissance
0 % — firmware probablement commun avec la SV305C Pro) et « Réguler »
levait « CoolerEnable refusé ». Correctif jalon 37 : sonde TEC PAR
L'EFFET dans detecter_capacites() — tentative CoolerEnable = 1 ; refus →
pas de TEC (cap.tec False, lire_refroidissement → None → boutons ❄
GRISÉS) ; succès → TEC présent + état initial restauré. Tout au vert en
dev : _test_tec_sonde_jalon37 11/11 (NOUVEAU), _test_capacites 29/29,
jalon36 8/8, jalon33 20/20, jalon35 15/15, _test_camera_playerone 29/29,
jalon31 15/15, jalon32 25/25, jalon34 21/21.

**Prochaine étape (session NEUVE)** : (1) copier l'installateur v2.20.6
vers le miniPC ; (2) TEST RÉEL jalon 37 (setup 2, SV305C) : connexion
auto → les boutons ❄ doivent rester GRISÉS (pas de TEC) et « Réguler »
inaccessible — comportement normal ; (3) tests réels setup 1 (MiniCam8M) :
TEC + roue à filtres (point 2c : plages + CFW, verdict par EFFET
PHYSIQUE).

Sessions précédentes : v2.20.5 (jalon 36, point 4 item 2d — connexion
auto SVBONY, validé en réel par Alain, c09e191) ; v2.20.4 (jalon 35,
0321914) — détail dans l'historique git et le changelog du source.
