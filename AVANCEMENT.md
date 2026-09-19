# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.16.0** (`avastack/__init__.py`),
  branche `master` (local, pas encore poussée).
- **Dernier jalon (29, objectif d'Alain du 19/09/2026) — CAPACITÉS
  DYNAMIQUES PAR MARQUE** : « pour une marque, être capable EN DYNAMIQUE
  de connaître les capacités de la caméra » — Alain n'a pas accès à toutes
  les caméras de ces marques, donc RIEN n'est codé en dur par modèle.
  - **`avastack/cameras/capacites.py` (NOUVEAU)** : modèle commun
    `Capacites` — marque, modèle, capteur, couleur/mono, bits, plein champ,
    pixel µm, plages `expo_us` / `gain` / `offset`, TEC (+ plage de
    consigne, température lisible), bins, bin matériel, formats, USB3,
    ST4, roue, n° série, énumération brute des contrôles — plus
    `vers_texte()` (verdict) et `vers_dict()` (archivage JSON), et la table
    `GAIN_UNITAIRE_CONNU` (IMX585 → 210) qui ne sert qu'à ANNOTER.
  - **Contrat `detecter_capacites()`** sur `CameraBase` (no-op → None),
    implémenté sur caméra OUVERTE (appeler entre `open()` et `close()`) :
    - **Player One** : sonde `POASonde` (structures ctypes + validation
      des DEUX layouts de POAConfigAttributes sur 2 configs) DÉPLACÉE du
      banc dans `playerone.py` — une seule définition, le banc délègue
      désormais (fin de la duplication) ; au passage `POASetConfig` passe
      la vraie union `POAConfigValue` (8 octets) au lieu d'un entier nu.
    - **ZWO** : ctypes direct sur `ASICamera2.dll` via `sdk_loader.py` —
      `ASIGetNumOfControls` + `ASIGetControlCaps` + fiche `ASI_CAMERA_INFO`
      (structs du wrapper de référence python-zwoasi, MIT). Contrôles ASI :
      GAIN=0, EXPOSURE=1 (µs), OFFSET=5, TEMPERATURE=8 (×10), TARGET_TEMP=16,
      COOLER_ON=17, HARDWARE_BIN=13.
    - **SVBONY** : ctypes sur `SVBCameraSDK.dll` — `SVBGetNumOfControls` +
      `SVBGetControlCaps` + fiche `SVBCameraProperty` + taille de pixel
      (structs du wrapper pysvbony, MIT). Contrôles SVB : GAIN=0,
      EXPOSURE=1, « offset » = BLACK_LEVEL=13, TEC 14/15/16/17.
    - **QHY : NON couvert** — le binding PyPI n'expose AUCUNE fonction de
      plages (ni `GetQHYCCDParamMinMax`) → capacités partielles à décider
      plus tard (ton « pas de ctypes » concernait la roue : à trancher).
  - Les exports des 3 DLL ont été VÉRIFIÉS réellement (parseur PE) avant
    d'écrire : `GetNumOfControls` + `GetControlCaps` existent bien partout.
  - Tests : **`_test_capacites.py` (NOUVEAU, faux SDK ZWO/SVB + modèle,
    26/26)** ; banc POA refactoré (**25/25**) ; batterie **34/34 OK** ;
    banc UI + mode `--console` revérifiés après refactor.
  - **BUG RÉEL + CORRECTIF (constat d'Alain, miniPC)** : le banc recentré
    sur la sonde a planté chez lui — `AttributeError: module
    'avastack.cameras.playerone' has no attribute '_POAConfigValue'`
    (l'installation y est en **v2.15.0**, le banc neuf à côté). C'est
    exactement le piège déjà connu du banc QHY (banc récent + module
    ancien). Correctif : le banc **charge l'application de façon
    DIAGNOSTIQUÉE** — si des symboles manquent (ou si `capacites.py`
    absent), il affiche « ⚠ L'APPLICATION EST TROP ANCIENNE POUR CE BANC »
    avec la version lue, les chemins/dates chargés, les symboles
    manquants et les 2 fichiers à copier ; la fenêtre s'ouvre quand même
    (bannière rouge, Ouvrir désactivé, détection utilisable), le mode
    `--console` explique et sort en code 2. **Reproduit et vérifié** dans
    une copie temporaire « appli v2.15.0 + banc neuf » (message exact,
    GUI OK, bouton désactivé).
  - **INSTALLATEUR RECONSTRUIT (v2.16.0)** :
    `installer\windows\output\avastack-setup.exe` (19/09 22:50 puis
    après correctifs) — embarque désormais **les DEUX bancs**
    (`_diag_camera_qhy.py` ET `_diag_camera_playerone.py`, ajouté au
    `.iss`), LISEZMOI.txt réécrit (section « BANCS DE DIAGNOSTIC
    CAMÉRA » + rappel du contrôle de version). C'est la voie recommandée
    pour le miniPC (réinstaller), la copie manuelle (playerone.py +
    capacites.py) restant possible.
  - **PREMIER RELEVÉ RÉEL (Uranus-C Pro, 19/09/2026 soir, rapport
    `avastack_poa_diag_20260919_225446.txt`)** — valeurs RÉFÉRENCE pour le
    futur câblage UI : **gain 0→750** (PAS ce qu'on aurait deviné), **offset
    0→250**, **exposition 10 µs → 2000 s** (ctrl 0) + un DEUXIÈME contrôle
    **31 « Exp » en SECONDES, flottant, 1e-05→7200 s** (au-delà de l'enum
    documentée 0-30 !), **bins [1, 2, 3, 4]** (bin 3 inclus), TEC -50→30 °C,
    e-/ADU annoncé 11,4, formats RAW8/RAW16/RGB24/MONO8, ST4 non, USB3 oui,
    n° série CAMD31905CE042109000, layout « récent » validé. CE RELEVÉ A
    FOURNI 5 CORRECTIFS (tous faits, tests dédiés ajoutés) :
    (1) contrôles FLOTTANTS relus comme des ENTIERS par le banc
        (température « -1073741824 » = bits du flottant -2.0) → le banc
        passe désormais par `sonde.lister()` qui remplit le cache de types
        (test 3b : `lister()` + `lire()` sur un faux SDK INT/FLOAT) ;
    (2) « EGAIN lu » trompeur (c'était le DÉFAUT, hors de ses propres
        bornes [0,10]) → verdict = courant + défaut + avertissement «
        attribut peu fiable » quand le défaut sort de ses bornes ;
    (3) padding du tableau imgFormats_ (4 × RAW8) → `dedupliquer()`
        appliqué aux bins/formats des 3 sondes (test dédié) ;
    (4) contrôle 31 nommé dans NOMS_CONFIGS + ligne « contrôles au-delà
        de l'enum documentée » dans le verdict ;
    (5) flux live : état journalisé AVANT le départ, relance UNIQUE de
        l'exposition à mi-patience, abandon expliqué avec pistes
        (format/ROI trop lourds pour l'USB, expo pilotée ailleurs) ;
        aperçu DÉCIMÉ avant calcul (frame RGB24 = 25 Mo) ; cadence d'UI
        200 ms pendant le flux ; une seule frame en attente (écrasement).
  - **FLUX LIVE POA VALIDÉ EN RÉEL (19/09/2026 23:18)** : **~43 fps** en
    plein champ RGB24 (3856×2180, 25 Mo/frame) puis **>200 fps en bin 2**
    (1928×1090 relu exactement) — TEC posé/relu (-10 °C), gain 210, offset 6.
    Premier échec expliqué et corrigé : le banc ne démarrait JAMAIS
    l'exposition à l'ouverture → `_ouvrir()` appelle désormais
    `POAStartExposure(0)` (log « POAStartExposure(0) → OK »).
  - **SONDE SVBONY VALIDÉE EN RÉEL (SV305C, 19/09/2026 23:52, rapport
    `avastack_svb_diag_20260919_235449.txt`)** : SDK v1.13.4, 1920×1080,
    12 bits, COULEUR, USB 2.0, plages exactes — **expo 36 µs → 2000 s**,
    **gain 0 → 450**, **BlackLevel (offset) 0 → 255**, bins [1, 2],
    formats RAW8/RAW16/Y8/RGB24, pas de TEC (normal), 14 contrôles.
    DEUX CONSTATS → CORRECTIFS :
    (1) le FLUX n'a rien donné ET le log s'arrêtait après « ▶ flux » :
        thread mort SANS message (exception non interceptée dans un thread
        secondaire = thread tué silencieusement). → try/except global avec
        traceback journalisé dans la boucle de flux, état périodique 1×/s
        pendant les timeouts, log de la 1re frame ;
    (2) le format relu au flux était RAW8 alors que l'ouverture avait posé
        RGB24 SANS vérifier le résultat → poser + RELIRE + logger à
        l'ouverture (réessai une fois si divergent) ; expo/gain courants
        loggés (les réglages SVBONY PERSISTENT — expo 2 s et gain 225
        hérités) + bouton « ⚙ défauts d'usine » (SVBRestoreDefaultParam) ;
    (3) SVBGetCameraProperty échoue AVANT SVBOpenCamera (« fiche
        illisible » à la détection) → essai bref open → lire → close dans
        la détection ; capteur = nom du modèle (le SDK SVB n'a pas de champ
        séparé).
    **À (re)tester** : le flux doit maintenant soit donner une image, soit
    EXPLIQUER ce qui bloque (timeouts 1×/s, traceback s'il y a crash, ou
    abandon à 6 s avec les valeurs du moment). Commencer par « ⚙ défauts
    d'usine » si expo/gain hérités suspects.
  - **CAUSE DU CRASH FLUX TROUVÉE PAR LE TRACEBACK (SV305C, 20/09/2026
    00:06)** : `access violation writing` au 1er `SVBGetVideoData` — le
    SDK écrit sa frame SANS vérifier la taille du buffer, et son format
    interne est PLUS GRAND que le format relu (`SVBGetOutputImageType`
    renvoyait RAW8 après un set RGB24 « OK » : la relecture MENT). →
    (a) buffer SUR-ALLLOCUÉ au pire cas RGB24 + marge et taille réelle
        passée au SDK ; (b) format de référence pour le DÉCODAGE = celui
        QU'ON A POSÉ (`self._fmt_pose`), la relecture n'est qu'un
        diagnostic (+ décodage adaptatif en repli, log du désaccord) ;
    (c) `_pose_format` RÉAPPLIQUE la ROI après le changement de type
        (certains SDK recalculent la taille de frame au SetROIFormat).
    Installateur rebuildé (00:13). À retester : flux → image attendue (ou
    rapport avec le nouveau diagnostic).
  - **FLUX SVBONY : LES FRAMES ARRIVENT (20/09/2026 00:16)** — le décodage
    adaptatif a confirmé en réel : **la frame réelle est RGB24 (3 o/pixel)
    alors que la relecture dit RAW8** (SVBGetOutputImageType ment, cf.
    leçon CLAUDE.md proposée), une frame toutes les ~2 s = cohérent avec
    l'expo héritée de 2000 ms. BUG résiduel corrigé : l'incrément
    `_n_frames` avait été perdu dans une édition → compteur bloqué à 0,
    warning « décodage adaptatif » répété à chaque frame, fps à 0,00,
    « 1re frame » jamais loguée. Réintégré + warning unique (flag).
    Installateur rebuildé (00:20).
  - **EXPO « REVENUE » APRÈS STOP/START (constat du même log)** : expo
    posée à 30 ms (relu 30009 ✓) puis REVENUE à 2000 ms après les cycles
    stop/start du changement de format et de la ROI → le SDK SVBONY
    RECHARGE ses paramètres sauvegardés au redémarrage de capture.
    Correctifs : `SVBSetAutoSaveParam(0)` posé À L'OUVERTURE (la DLL
    exporte cette fonction) + avertissement après chaque
    SVBStartVideoCapture (« reposer expo/gain si besoin »). Installateur
    rebuildé (00:2x).
  - **CRASH ENCORE PRÉSENT AVEC 6,2 Mo (20/09/2026 00:25)** → le format
    interne du SDK est ENCORE PLUS GRAND : seul candidat à 1920×1080,
    **RGB32 (4 o/pixel, 8,3 Mo)**. Solution DÉFINITIVE : buffer alloué à
    **4 o/pixel + marge (16,4 Mo)**, et le VRAI format est DÉDUIT DE LA
    DONNÉE (dernier octet non nul d'un buffer initialisé à zéro →
    octets/pixel = ceil(fin / surface)) — « 🔎 FORMAT RÉEL DÉTECTÉ »
    journalisé (une fois par changement), frame noire (tout à zéro)
    signalée et décodée avec le format posé. Installateur rebuildé
    (00:28). **À retester** : le log dira enfin le format réel du SDK
    (attendu : 4 o/pixel = RGB32).
  - **BANC SVBONY VALIDÉ EN RÉEL (20/09/2026 00:30)** : « 🔎 FORMAT RÉEL
    DÉTECTÉ : 4 o/pixel (8.3 Mo par frame) » — le format interne du SDK
    est bien **RGB32**, que NI le set NI la relecture ne révélaient ; le
    décodage adaptatif marche, **1re frame reçue immédiatement** (0,0 s),
    expo posée/relu (30 ms), défauts d'usine OK, auto-save désactivé OK.
    Les réglages hérités (expo 2 s, gain 225) n'ont plus deffet grâce à
    défauts d'usine + SVBSetAutoSaveParam(0). À explorer plus tard
    (optionnel) : bin 2, RAW16/RAW8, ROI, cadence réelle.
  - **Reste à faire (suite logique)** : brancher ces capacités dans l'UI
    (bornes de gain/offset et présence TEC/ROI/binning RÉGLÉES PAR LA
    CAMÉRA au lieu des valeurs actuelles figées) — à faire APRÈS les
    relevés réels sur les 4 caméras d'Alain, pour ne pas figer des
    suppositions.
- Jalon 28 (**v2.15.0**, banc `_diag_camera_playerone.py` pour le 2e setup
  Uranus-C Pro / C8 + 0,63 / Open Astro Mount) : **VALIDÉ EN RÉEL** (voir
  jalon 29 — verdict, TEC posé/relu, gain 210, offset, bin 2 → 1928×1090,
  flux 42 fps plein champ RGB24 puis >200 fps en bin 2). Jalon 28b : banc
  **`_diag_camera_svbony.py`** (même architecture : chargement diagnostiqué,
  sonde RÉUTILISÉE de l'appli `SVBonyCamera.detecter_capacites`, poses en
  direct, flux avec diagnostic + relance stop/start, rapport
  `avastack_svb_diag_*.txt`, mode `--console`) — à tester avec la SV305C.
  Spécificités SVBONY couvertes : PAS de SVBInitCamera (SVBOpenCamera
  suffit, 36 exports vérifiés), températures en UNITÉS DE 0,1 °C
  (conversion dans le banc), flip = UN seul contrôle (0-3), bin/ROI par
  SVBSetROIFormat (taille FINALE après bin), SupportedBins à terminateur 0
  (en-tête officiel). Installateur rebuildé (23:48, 3 bancs embarqués).
- Jalons précédents : **v2.15.0 (jalon 27)** : offset QHY (ctrl 7), zones
  de saisie expo/gain/offset (µs/ms/s), déconnexion tracée ;
  **v2.14.x** : roue 17/48+n, TEC 18/14/15/16, expo log, stop_live/
  begin_live, DLL SDK embarquées + zwoasi. **À valider en réel (miniPC,
  QHY)** : offset (effet physique), saisies, ⏏ Déconnecter, filtre
  pendant pause/empilement.
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
2c. **QHY par ctypes — VOIE VALIDÉE PAR ALAIN (19/09/2026)** : « pour QHY,
   dans le diag seulement pour le moment, comme les autres, on peut tenter
   avec la DLL et ctypes effectivement, et tant qu'on y est pour la roue à
   filtre aussi ». Donc, dans le BANC QHY uniquement (pas dans l'appli
   pour l'instant) : appeler directement `qhyccd.dll` (SDK 26-06-04, déjà
   embarqué) via ctypes pour (1) les PLAGES des contrôles — fonction
   `GetQHYCCDParamMinMax` (absente du binding PyPI) et (2) la ROUE
   INTÉGRÉE (`IsQHYCCDCFWPlugged`, `GetQHYCCDCFWStatus`,
   `SendOrder2QHYCCDCFW`) — chemins, ordre d'appel et conventions à
   relever dans l'en-tête du SDK ; vérifier l'EFFET PHYSIQUE (l'API relue
   à l'identique ne prouve rien).
3. **Jalon 24** : gradient/débruitage par couche (live + externe) ;
   garde-fous GraXpert jalon 23b en mono ; SCNR doux (jalon 23).
4. **Roue à filtres MiniCam8M** : voie validée (contrôles 44/17 du
   binding, ASCII 48+n ; **PAS de ctypes** — décision d'Alain). À tester
   au banc QHY : `44 CfwSlotsNum` (slots réels) puis écriture 17=48+n
   avec vérification de l'EFFET PHYSIQUE (slot vide/opaque → l'image
   change). **Aucun code appli avant ce verdict.**
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

## 🔚 Clôture de session — 20/09/2026 (nuit)

Demande d'Alain : « Si c'est ok pour toi, met à jour claude.md, commite et
pousse et on stoppe la session ». État : **v2.16.0 poussée**, installateur
REBUILDÉ avec les 3 bancs, tests 34/34 + bancs auto-testés.

**Réalisé dans la session** :
1. **Capacités dynamiques par marque** (jalon 29, objectif d'Alain) :
   `avastack/cameras/capacites.py` + contrat `detecter_capacites()` + sondes
   Player One (POASonde), ZWO et SVBONY — rien de codé en dur par modèle ;
   QHY NON couvert (binding sans plages — voie ctypes validée par Alain,
   À FAIRE).
2. **Banc Player One** (`_diag_camera_playerone.py`) : **VALIDÉ EN RÉEL**
   (Uranus-C Pro : gain 0→750, offset 0→250, expo 10 µs→2000 s + ctrl 31
   « Exp » en secondes, TEC -50→30 °C, bins 1-4, flux 42 fps plein champ
   RGB24, >200 fps bin 2).
3. **Banc SVBONY** (`_diag_camera_svbony.py`) : **VALIDÉ EN RÉEL** (SV305C :
   expo 36 µs→2000 s, gain 0→450, BlackLevel 0→255, bins 1-2, **format
   interne réel RGB32 déduit de la donnée**, flux OK immédiat, défauts
   d'usine + SVBSetAutoSaveParam(0) OK).
4. Leçons CLAUDE.md ajoutées (accord d'Alain) : chargement diagnostiqué des
   bancs, type lu = routine d'énumération unique, thread secondaire =
   try/except + traceback au log, relecture SDK menteuse + buffer non
   vérifié → sur-allocation + déduction empirique, paramètres SDK
   rechargés au restart.

**Prochaines étapes (prochaine session)** :
1. **Banc QHY en ctypes** (voie validée par Alain) : plages via
   `GetQHYCCDParamMinMax` + roue à filtres via les CFW — dans le banc
   seulement pour l'instant.
2. **Câblage de l'UI aux capacités dynamiques** : bornes/contrôles réels
   par caméra (le slider Gain 0-175 actuel est faux pour Player One 0→750
   comme pour QHY).
3. Optionnel : compléments banc SVBONY (bin 2, RAW16/RAW8, ROI, cadence).
4. Validations réelles QHY toujours en attente (offset, saisies,
   Déconnecter, filtre, TEC) — cf. section « Validations réelles ».
