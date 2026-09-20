# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.21.3** (`avastack/__init__.py`),
  branche `master` — jalon 44 CORRIGÉ EN DEV (tout au vert), **COMMITÉ ET
  POUSSÉ (voir clôture de session)**, **installateur v2.21.3 REBUILD**
  (`installer/windows/output/avastack-setup.exe`) — copie de l'installateur
  vers le miniPC à faire.
- **Dernier jalon (44, 20/09/2026) — ÉTAT DE LA CADENCE VISIBLE EN DIRECT
  (suite du retour d'Alain : « ça travaille toujours toutes les 5 s »)** :
  - le correctif jalon 43 (v2.21.2) est en place ; deux causes possibles
    pour un rythme inchangé : (a) version testée encore v2.21.1 (bug du
    court-circuit par le scan interne de read()), (b) cadence réellement
    « toutes les 5 s » → rafales toutes les 5 s = comportement CORRECT,
    mais la chaîne composition dure bien plus que 5 s → sablier toujours
    visible ;
  - fait : le throttling est maintenant OBSERVABLE — étiquette
    `lbl_cadence` sous la combobox « Empiler les brutes », tenue par
    `_maj_lbl_cadence()` (appelée par _tick, mémo anti-spam) : fenêtre
    armée → « prochaine rafale dans Xs · N brute(s) en attente » (ambre,
    compte à rebours) ; échéance → « rafale en cours · N » (vert) ;
    « — » = dès réception ; cadence sur source non dossier → « sans
    objet » ;
  - DIAGNOSTIC : étiquette restée « — » avec la cadence sélectionnée →
    version exécutée antérieure à v2.21.1 ; compte à rebours visible → le
    throttling fonctionne, choisir une cadence NETTEMENT au-dessus de la
    durée de la chaîne (composition = chaîne PAR COUCHE) ;
  - Tests : _test_cadence_jalon42 24/24 (étiquette étendue) ; jalon5 15/15.
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
    3 validé en réel (jalon 35), 4 validé en réel (jalon 36) ; le résidu
    TEC (contrôles affichés sur une caméra sans TEC) a été TRANCHÉ PAR
    ALAIN : boutons ❄ toujours actifs (jalon 38).
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
6. **Jalon 39 (v2.20.8)** : en session réelle (moteur VeraLux, vue
   « empilement »), cocher puis décocher SCNR, SCNR doux et démagenta →
   effet VISIBLE immédiat, sans attendre la frame suivante ni bouger le
   fond cible.
7. **Jalon 40 (v2.20.9)** : pendant un calcul (ex. case GX cochée avec un
   vrai GraXpert), vérifier le curseur animé + « ⏳ calcul : <étape>… »
   dans le panneau VeraLux, puis la ligne de résultat (GX ✓ · … · logD ·
   fond) une fois terminé.
8. **Jalon 41 (v2.21.0)** : en mode STF, vérifier le nouveau cadre
   « Couleur live » (cases SCNR/démagenta efficaces à l'écran) et le cadre
   « État des calculs » (⏳ netteté pendant la déconvolution STF).
9. **Jalon 42-44 (v2.21.1 → v2.21.3)** : en COMPOSITION multi-dossiers avec
   GX/débruitage live par couche, régler « Empiler les brutes » sur 1-5 min
   → l'étiquette sous la combobox doit montrer le compte à rebours
   (« prochaine rafale dans Xs · N brute(s) en attente »), le sablier ne
   doit travailler qu'une fois par rafale, et AUCUNE brute ne doit être
   perdue (compte « Frames » = total des brutes des dossiers).

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
- **Un callback UI qui change la CLÉ du solveur SANS rafraîchir ne produit
  un effet qu'au prochain `disp.process()`** — c.-à-d. à la frame entrante
  ou au prochain réglage qui rafraîchit (constat réel jalon 39 : les cases
  couleur semblaient inertes). Convention : tout contrôle `_on_*` finit
  par `_refresh_preview()` ; les `_sync_*_vue` (appelés par _tick toutes
  les 30 ms) ne touchent qu'à l'ÉTAT, JAMAIS au rendu.
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

## 🔚 Clôture de session — 20/09/2026 (v2.21.3, jalon 44)

État exact : **v2.21.3 COMMITÉE ET POUSSÉE (966edae), installateur REBUILD**.
Session en six jalons après la v2.20.7 : jalon 39 (v2.20.8, cases couleur
réactives) ; jalon 40 (v2.20.9, état du calcul : curseur + ⏳ + résultat) ;
jalon 41 (v2.21.0, UI indépendante du moteur — cadres « Couleur live » et
« État des calculs » en STF aussi) ; jalon 42 (v2.21.1, cadence
d'empilement — combobox « Empiler les brutes ») ; jalon 43 (v2.21.2,
CORRECTIF constaté en composition : le scan INTERNE de read()
court-circuitait la fenêtre — la fenêtre armée bloque désormais TOUTE
lecture) ; jalon 44 (v2.21.3, retour d'Alain « ça travaille toujours
toutes les 5 s » → le throttling devient OBSERVABLE : étiquette sous la
combobox « prochaine rafale dans Xs · N brute(s) en attente » / « rafale
en cours » / « — » — distingue une version ancienne d'une cadence trop
courte pour la chaîne). Tout au vert en dev : _test_cadence_jalon42 24/24,
jalon5 15/15.

**Prochaine étape** : (1) copier l'installateur v2.21.3 vers le miniPC ;
(2) validation réelle : étiquette de cadence (compte à rebours visible),
sablier une fois par rafale, AUCUNE brute perdue ; (3) suite des tests
réels en attente (QHY MiniCam8M : TEC + roue à filtres, verdict par EFFET
PHYSIQUE).

Sessions précédentes : v2.21.2 (jalon 43, correctif cadence, d5b799d) ;
v2.21.1 (jalon 42, cadence d'empilement, 11f6dfb) ; v2.21.0 (jalon 41,
8ee2d8c) ; v2.20.9 (jalon 40, 45bbfc9) ; v2.20.8 (jalon 39, 097a9c8) ;
v2.20.7 (jalon 38, d8d4055) — détail dans l'historique git et le
changelog du source.
