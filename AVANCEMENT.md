# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.17.0** (`avastack/__init__.py`),
  branche `master` — NON poussée, installateur NON rebuildé : à faire AVANT
  le test réel de demain matin (cf. « Prochaine étape »).
- **Dernier jalon (30, 20/09/2026) — BANC QHY : SONDE CTYPES NATIVE**
  (voie validée par Alain ; banc UNIQUEMENT, l'appli inchangée) :
  - `_diag_camera_qhy.py` appelle `qhyccd.dll` DIRECTEMENT (sans le binding
    PyPI) via ctypes, dans un SOUS-PROCESSUS isolé (Init/Release du SDK
    sans danger pour l'état du banc, un segfault natif ne tue que l'enfant ;
    REFUS si le flux est actif — jamais deux ouvertures de caméra).
  - **PLAGES** : `GetQHYCCDParamMinMaxStep` — nom VÉRIFIÉ dans les exports
    RÉELS de la DLL livrée (parseur PE, 328 exports ; « GetQHYCCDParamMinMax
    » tout court n'existe PAS) : disponibilité + min/max/step + valeur pour
    chaque contrôle 0..62. Enum CONTROL_ID de l'en-tête officiel =
    table NOMS_CTRL du banc (gain 6, offset 7, expo µs 8, temp 14-16, CFW
    17/44, consigne 18) ; résumé « pour câbler l'UI » (expo lisible en
    µs/ms/s, gain, offset, TEC, slots roue).
  - **ROUE intégrée** : `IsQHYCCDCFWPlugged` (0 = roue TROUVÉE, doc QHY —
    PAS un booléen), `GetQHYCCDCFWStatus` + `SendOrder2QHYCCDCFW` (ordre =
    1 caractère ASCII '0'+(position-1), relecture 0,5 s, timeout 25 s)
    avec VERDICT de confirmation ; l'EFFET PHYSIQUE reste à vérifier
    (voie binding : 48+n ; doc : '0' = position 1 — à trancher en réel).
  - Signatures prises dans l'en-tête OFFICIEL (qhyccd.h/qhyccdstruct.h) ;
    prototypes ctypes explicites (leçon v2.16), buffers sur-alloués
    (leçon SVB) ; DLL cherchée AVASTACK_QHY_DIR → dossier du banc → DLL
    embarquée du paquet (site-packages/vendor/lib — chemin + date affichés).
  - Testé SANS caméra (dev, 20/09) : DLL chargée, InitQHYCCDResource → 0,
    ScanQHYCCD → 0 → erreur propre JSON ; smoke UI OK ; tests 29/29
    (`_test_capacites`) et 33/33 (`_test_qhy_camera`) au vert.
  - LISEZMOI.txt à jour (section banc QHY) ; **installateur à REBUIRDER**.
- **Jalon 29 (v2.16.0, TERMINÉ, validé en réel)** : capacités dynamiques
  par marque (`capacites.py` + contrat `detecter_capacites()` sur
  caméra OUVERTE ; POA via sonde, ZWO et SVBONY via ctypes sur leurs DLL,
  QHY PARTIEL → la sonde ctypes du jalon 30 le complète côté banc) +
  bancs Player One et SVBONY validés en réel (Uranus-C Pro : **gain 0→750,
  offset 0→250, expo 10 µs→2000 s** + ctrl 31 « Exp » en secondes, bins
  1-4, TEC -50→30 °C, ~43 fps plein champ ; SV305C : **expo 36 µs→2000 s,
  gain 0→450, BlackLevel 0→255, bins 1-2**, format interne RGB32 DÉDUIT DE
  LA DONNÉE). Bancs chargeant l'appli de façon DIAGNOSTIQUÉE (bannière
  « application trop ancienne »). Installateur 3 bancs rebuildé.
- Jalons précédents : jalon 28 = banc Player One (v2.15.0, VALIDÉ EN RÉEL) + jalon 28b = banc SVBONY (validé en réel, format interne RGB32 déduit de la donnée) ; jalon 27 (v2.15.0) = offset QHY (ctrl 7), zones de saisie expo/gain/offset (µs/ms/s), déconnexion tracée ; v2.14.x = roue 17/48+n, TEC 18/14/15/16, expo log, stop_live/begin_live, DLL SDK embarquées + zwoasi.
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
2b. **Capacités dynamiques (jalon 29)** : dès que possible, appeler
   `detecter_capacites()` sur CHAQUE caméra et noter le verdict — les
   tableaux de bord (banc POA) et le futur câblage UI s'appuient dessus.
   Toute valeur « codée en dur » encore présente dans l'UI (gain 0-175
   QHY, etc.) devra céder la place aux plages découvertes.
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

## 🔚 État de session — 20/09/2026 (fin de nuit)

Demande d'Alain : « diag QHY avec les ctypes comme prévu, à tester demain matin ». FAIT (jalon 30, v2.17.0) :
1. Sonde ctypes native dans le banc QHY (sous-processus isolé) : plages GetQHYCCDParamMinMaxStep + roue native CFW (statut + rotation avec confirmation) ; exports de la DLL vérifiés par parseur PE ; signatures de l'en-tête officiel du SDK ; prototypes ctypes explicites ; DLL identifiée (chemin + date) à chaque sonde.
2. UI : 3 boutons (📏 Plages, 🌀 Tourner, 📖 Statut CFW) + résumé « pour câbler l'UI » ; refus de la sonde si le flux est actif.
3. Tests sans caméra : charge DLL + init OK + erreur propre JSON ; smoke UI OK ; _test_capacites 29/29 ; _test_qhy_camera 33/33.
4. LISEZMOI.txt à jour. v2.17.0 NON commitée, NON poussée, installateur NON rebuildé.

**Prochaine étape (demain matin, miniPC, MiniCam8M + alim 12 V)** :
1. Commiter/pousser v2.17.0, REBUIRDER l'installateur, réinstaller (ou copier _diag_camera_qhy.py + avastack/ dans le dossier d'installation).
2. Banc QHY : « 📏 Plages (MinMaxStep) » → noter les plages réelles (expo/gain/offset/TEC) pour le futur câblage UI.
3. Roue : « 📖 Statut CFW » puis « 🌀 Tourner » 1↔2 avec confirmation par relecture ET vérification de l'EFFET PHYSIQUE ; trancher la convention 48+n (binding) contre '0' = position 1 (doc).
4. Ensuite : câblage de l'UI aux capacités dynamiques (jalon 29/30 : bornes réelles par caméra au lieu des valeurs figées).
