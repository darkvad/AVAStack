# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.20.2** (`avastack/__init__.py`),
  branche `master` — jalon 34 testé en dev (tout au vert), **COMMITÉ
  SANS POUSSER**, **installateur v2.20.2 REBUILD**
  (`installer/windows/output/avastack-setup.exe`) — poussée + copie de
  l'installateur vers le miniPC à faire.
- **Dernier jalon (34, 20/09/2026) — AFFICHAGE EXPOSITION (points 1 et 2 de
  l'item 2d, retours réels setup 2)** :
  - point 2 : `_fmt_expo` sans notation scientifique (avant : « 2e+03 s »)
    — arrondi à l'entier au-delà de 10 s (pas réel ≥ 1 ms), milliers
    séparés par espace fine insécable (« 2 000 s », « 20 000 s ») ;
  - point 1 : case « Échelle longue » — libellé GÉNÉRÉ (plus de « 900 s »
    en dur) : « Échelle longue (1 s – 2 000 s) » avec la borne max RÉELLE ;
  - CORRECTION retour réel (v2.20.2) : la case doit rester VISIBLE — la
    v2.20.1 la masquait à tort ; désormais cochée = longue portée seule
    (1 s → max, réglage fin), décochée = pleine plage, saisie courte =
    décochage auto ;
  - Tests : _test_expo_affichage_jalon34 17/17 (NOUVEAU) ; jalon32 25/25 ;
    jalon31 15/15 ; sliders jalon6 OK.
- **Reste à déboguer de l'item 2d : points 3 et 4** (TEC POA boutons ❄
  grisés ; connexion auto SVBONY refusée « Propriétés illisibles ») —
  comparer avec les bancs de diag VALIDÉS EN RÉEL (référence).
- **Jalon 33 (v2.20.0, 20/09)** : pilotage TEC POA/SVBONY (poses éprouvées
  par les bancs, lire → None si pas de TEC) + `_deconnecter_camera`
  dédoublonnée (décision d'Alain, version du 19/09 conservée). Jalon 32
  (v2.19.0) : capacités dynamiques toutes marques. Jalon 31 (v2.18.0) : UI
  dynamique QHY (sonde native qhyct.py).
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
   1. ✅ TRAITÉ (jalon 34, v2.20.1) — libellé « Échelle longue » généré
      (bornes réelles), case masquée si bornes natives détectées.
   2. ✅ TRAITÉ (jalon 34, v2.20.1) — `_fmt_expo` sans notation
      scientifique : « 2 000 s » au lieu de « 2e+03 s ».
   3. **Player One : contrôles TEC affichés mais boutons ❄ GRISÉS** —
      alors que LE BANC DE DIAG POA VALIDAIT LE TEC EN RÉEL (régulation
      + lecture température + puissance, _diag_camera_playerone.py).
      La détection (bornes de consigne) s'affiche bien ; c'est
      l'activation des boutons qui échoue (le sondage de l'app active
      si `lire_refroidissement() is not None` — à tracer : la sonde
      TEC répond-elle dans le process de l'app ?).
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

## 🔚 Clôture de session — 20/09/2026 (v2.20.2, jalon 34)

État exact : **v2.20.2 COMMITÉE SANS POUSSER, installateur v2.20.2
REBUILD** (points 1 et 2 de l'item 2d, passe de debug demandée par Alain —
« on commence par 1 et 2 dans la même passe et on s'arrête »). Consignes
NOTÉES à la demande d'Alain, écrites dans CLAUDE.md : (a) rebuild de
l'installateur dès qu'une passe touche plus de 1-2 fichiers (FAIT pour
v2.20.1 puis v2.20.2) ; (b) « noter / se souvenir » = autorisation
implicite de mettre CLAUDE.md à jour. Tout au vert en dev :
_test_expo_affichage_jalon34 17/17, jalon32 25/25, jalon31 15/15, sliders
jalon6 OK. Réalisé : (a) point 2 — `_fmt_expo` sans notation scientifique
(arrondi à l'entier au-delà de 10 s, milliers séparés par espace fine
insécable — VALIDÉ EN RÉEL par Alain) ; (b) point 1 — libellé de la case
« Échelle longue » généré avec la borne max RÉELLE ; (c) CORRECTION du
retour réel d'Alain (v2.20.2) : la case ne doit PAS être masquée — elle
reste visible et utile (cochée = longue portée seule 1 s → max, décochée =
pleine plage, saisie courte = décochage auto).

**Prochaine étape** : (1) déboguer les points 3 et 4 de l'item 2d (TEC POA
boutons ❄ grisés ; connexion auto SVBONY refusée) EN COMPARANT avec les
bancs de diag validés en réel, qui restent la référence ; (2) pousser +
copier l'installateur vers le miniPC ; (3) refaire le test réel setup 1
(MiniCam8M) et setup 2.

Session précédente (v2.20.0, jalons 32 + 33) : capacités dynamiques toutes
marques + TEC POA/SVBONY, commitée e70c6d7, installateur rebuild.
Sessions v2.19.0 (jalon 32) e70c6d7 / v2.18.0 (jalon 31) bb84f72 : détail
dans l'historique git et le changelog du source.
