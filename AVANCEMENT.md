# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version : AVAStack v2.13.4** (`avastack/__init__.py`), branche `master`.
  Dernier jalon : **DIAGNOSTIC CAMÉRA QHY v2.13.4** (19/09/2026) — consigne
  d'Alain : « on ne bosse QUE sur le diagnostic caméra, arrête de rebuilder
  l'installateur » → **installateur NON rebuildé** (l'artefact en place reste
  celui de la v2.13.3).
  - **Cause du dernier plantage identifiée** : le log du miniPC montrait
    `begin_live` SANS AUCUN `set_resolution` alors que le fichier était censé
    être en v2.13.2+ → **les deux fichiers n'avaient pas été copiés
    ENSEMBLE** (banc récent + `avastack/cameras/qhy.py` resté en **v2.13.1**,
    la version où `set_resolution` n'existait pas). D'où « Démarrer » qui
    plante (pas de ROI posée → segfault natif), le pas-à-pas qui marche (le
    banc pose la ROI lui-même) et la **case ROI qui semble ignorée**.
  - **Le banc affiche désormais les fichiers réellement chargés** (chemin,
    date, présence de `set_resolution`, signature de `open()`, version
    d'avastack) à l'ouverture ET à chaque démarrage : une copie périmée
    devient VISIBLE. Si `open()` n'accepte pas de ROI, le banc le dit au lieu
    de lever un TypeError.
  - Bouton unique « ▶ Démarrer (QHYCamera.open(), séquence APPLI) » qui
    **transmet enfin la ROI cochée** via `open(roi=...)` ; case « forcer côté
    banc » pour comparer (l'ancien pas-à-pas). Garde-fou `_SDK_PRET`
    (init_sdk UNE seule fois par process) conservé.
  - **Découverte des valeurs — NON CONCLUANTE (constat d'Alain, 19/09/2026
    au soir)** : le balayage passe PARTOUT, sans aucun refus, sur gain (6),
    offset (7) et USB traffic (12) → le SDK **stocke** les valeurs sans les
    valider, donc la plage RÉELLE du gain QHY reste **INCONNUE** et le
    recalibrage du curseur de l'appli n'est PAS encore possible. Méthode à
    reprendre autrement : chercher un **effet physique** (niveau d'image /
    bruit à gain croissant, en s'appuyant sur l'exposition qui, elle, est
    PROUVÉE appliquée : 2000 ms → 0,5 fps exactement) ou consulter la doc
    constructeur QHY du capteur IMX585 ; un balayage qui n'échoue jamais ne
    démontre rien (leçon correspondante écrite dans CLAUDE.md).
  - **Découverte des valeurs (outils)** : « Lister les contrôles » fait
    2 passes — disponibles (nom officiel + valeur) puis **balayage exhaustif
    0..63** avec valeur brute hexadécimale (distingue un contrôle ABSENT d'un
    contrôle « drapeau » à sentinelle 0xFFFFFFFF) ; **« ▶ Balayer »**
    pose/relit chaque valeur d'un id (cf. constat ci-dessus : non
    concluant) ; **⏸ Pause 3 s** + horodatage des 5 premières frames +
    compteur cumulé pour trancher « la caméra n'émet plus » vs « nos lectures
    vident la file du SDK ».
  - Contrôles nommés d'après l'enum OFFICIEL (crate `qhyccd-rs`) : gain=6,
    offset=7, expo µs=8 (VÉRIFIÉS en réel), CurTemp=14, CurPWM=15,
    ManualPWM=16, Cooler=18 ; 4294967295 = sentinelle d'erreur.
  - **Constat à corriger (après le diagnostic)** : la MiniCam8M EST refroidie
    (alim. 12 V requise — ma réponse précédente était fausse) et le curseur
    Gain de l'appli est bridé à 8 alors que le SDK QHY raisonne en unités
    constructeur (défaut 30, essai concluant à 90).
  - Jalons précédents : banc embarqué v2.13.3, ROI QHY v2.13.2, double
    ouverture v2.13.1.
  - **Verdict ROI automatique** (2e run réel, 19/09/2026) : le log de
    « Démarrer » ne contenait TOUJOURS aucune ligne `set_resolution`, même
    case ROI cochée → le banc relit la tranche de trace écrite PENDANT
    l'ouverture et conclut (« POSÉE ✔ » / « REFUSÉE » / « AUCUNE TENTATIVE →
    qhy.py antérieur à la v2.13.2 »). C'est le verdict qui désigne la cause
    sans ambiguïté.
  - **LIMITE DÉCOUVERTE — le binding ne peut PAS libérer le SDK** : après
    « ■ Arrêter », un nouveau « ▶ Démarrer » dans le même process n'a plus
    JAMAIS reçu de frame (126 lectures sans frame, sans planter). Cause :
    l'introspection du module `qhyccd` ne montre que `Camera`, `init_sdk`,
    `scan_cameras` (+ utilitaires de chemins) — **ni `release_sdk` ni
    `ReleaseQHYCCDResource`** : l'état global du SDK est irréinitialisable
    dans le process. Le banc l'annonce (démarrage, après chaque `close`,
    avertissement si déjà ouverte+fermée) et conseille FERMER LE BANC +
    relancer. **À reporter dans l'appli** : même limite → relancer AVAStack
    après un Arrêter/redémarrer de la source QHY.
  - Ménage : définitions dupliquées du banc supprimées (deux copies de
    `_infos_versions`/`_open_supporte_roi`, la 1re écrasée en silence).
  **Correctif apporté dans le même jalon** (constat d'Alain : dans le banc,
  « Démarrer » SANS détection préalable « ferme l'appli direct ») :
  `init_sdk()` n'est plus appelé qu'**UNE fois par process** (garde-fou
  `_SDK_PRET` dans `cameras/qhy.py`) — le chemin fautif enchaînait
  `QHYCamera.lister()` (init #1 + scan) puis `open()` (init #2), alors que
  le pas-à-pas, lancé APRÈS « Détecter », n'en faisait qu'une ; le banc ne
  fait plus de scan dans le même process. En prime, `open(roi=None)` accepte
  une ROI imposée et lève une erreur **claire** si AUCUNE taille n'est
  acceptée, au lieu d'appeler `begin_live()` sans résolution (segfault).
  `_test_qhy_camera.py` : **19 vérifications** (ajout de la sécurité ROI et
  du garde-fou init_sdk).
  Contrôles nommés d'après l'enum OFFICIEL du SDK (crate `qhyccd-rs`) :
  gain=6, offset=7, expo µs=8 (VÉRIFIÉS en réel : posés puis relus à
  l'identique), CurTemp=14, CurPWM=15, ManualPWM=16, Cooler=18 ; la valeur
  4294967295 est la SENTINELLE D'ERREUR du SDK (contrôles « drapeaux »).
  **Constat à corriger** : la MiniCam8M EST refroidie (alim. 12 V requise —
  ma réponse précédente était fausse) et le curseur Gain de l'appli est
  bridé à 8 alors que le SDK QHY raisonne en unités constructeur (défaut 30,
  essai concluant à 90). Jalons précédents : ROI QHY v2.13.2 (3840×2160
  imposée avant `begin_live`, sinon segfault), double ouverture v2.13.1
  (séquence officielle sans `open()`, trace %TEMP%\avastack_qhy_debug.log,
  détection UI + scan sous-processus isolé). Tests : **32/32 passent**
  (dont `_test_qhy_camera.py`, banc auto-testé sans caméra). Jalon 24
  (v2.13.0, gradient + débruitage par couche) : validations réelles
  toujours en attente ; garde-fou jalon 23b actif en mono.
- **Recherche « roue à filtres intégrée » (19/09/2026, en soirée) —
  VOIE A VALIDÉE par Alain, AUCUN code écrit** (reprise prévue, cf. section
  « Roue à filtres » plus bas) :
  - La roue INTÉGRÉE de la MiniCam8M se pilote par les CONTRÔLES de la
    caméra, avec les méthodes DÉJÀ exposées par le binding : nombre de slots
    = `get_param(44)` (**CfwSlotsNum**), position courante = `get_param(17)`
    (**CfwPort**, valeur **ASCII**), déplacement = `set_param(17, 48 + n)`,
    disponibilité = `is_control_available(17/44)`. **Relevé réel d'Alain :
    ctrl 17 = 49 alors qu'on était sur le filtre 1 → la convention est
    `48 + n`** (celle de la crate Rust `qhyccd-rs`), et NON le `'0'` =
    position 1 de la doc QHY / du pilote INDI, décalé d'un cran (l'ambiguïté
    ne se tranche que par le slot PHYSIQUE, pas par une relecture).
  - Le paquet PyPI `qhyccd` 0.1.3 **n'expose AUCUNE API de roue** (seuls
    `Camera`, `init_sdk`, `scan_cameras` + utilitaires de chemins) : la
    classe `FilterWheel` existe dans la crate Rust mais n'est pas exportée.
    En revanche le SDK natif COMPLET est embarqué :
    `venv\Lib\site-packages\vendor\lib\windows-x86_64\qhyccd.dll`
    (**SDK QHYCCD 26-06-04**, 6 Mo) exporte `IsQHYCCDCFWPlugged`,
    `GetQHYCCDCFWStatus`, `SendOrder2QHYCCDCFW`, `GetQHYCCDParam`,
    `SetQHYCCDParam` et **`ReleaseQHYCCDResource`** — absente du binding :
    la limite « état du SDK irréinitialisable dans le process » vient donc
    du BINDING, pas de la DLL (la DLL, elle, connaît explicitement la
    miniCAM8 : `QHYMINICAM8.CPP` / `.H`).
  - **DÉCISION d'Alain : pas de ctypes du tout** → tout passe par les
    contrôles 17/44 du binding ; les fonctions CFW natives ne seront pas
    appelées.

- **Pièges récents (jalon 20-24)** : `var.get()` Tkinter interdit hors
  thread principal (bouchons `_Val`) ; crash OpenCV 5/OpenCL au teardown
  (`cv2.ocl.setUseOpenCL(False)`) ; tout test qui crée `ui.App` doit être
  HERMÉTIQUE (`ui.CONFIG = {}` + `ui.sauver_config` intercepté) ; images
  synthétiques des tests BRUITÉES (sinon 0 étoile) ; mesurer un traitement
  d'affichage en STF AUTO est biaisé (comparer en manuel à points fixes) ;
  outils factices de tests subprocess AUTONOMES (astropy seul, cwd = dossier
  temporaire) ; **valider les placeholders d'une commande AVANT la
  substitution** (après, ils n'existent plus — constat jalon 24) ;
  **SDK natif (QHY) : `init_sdk()` UNE SEULE fois par process** — le
  garde-fou `_SDK_PRET` de `cameras/qhy.py` a été ajouté après le constat
  « Démarrer sans Détecter ferme l'appli » (lister() = init #1 puis open()
  = init #2) ; un crash NATIF n'est jamais rattrapable par un `except`
  Python : tracer chaque étape dans un fichier et isoler les appels risqués
  (le scan QHY tourne en sous-processus pour cette raison).

## 🔜 À faire — validations réelles du jalon 24

- **Valider en réel le gradient/débruitage par couche** : en composition
  (HOO ou SHO), cocher GraXpert live + débruitage live → chaque couche
  traitée (la ligne d'état peut mentionner « (rôle) : couche vide —
  ignorée » pour un rôle sans données), composite re-fait, image visible.
  Puis bouton ⚡ : progression « GraXpert gradient Ha (1/2)… », message
  final « Traité par couche à … ».
- **Valider en réel les garde-fous GraXpert jalon 23b en mono** (SHO sans
  S mais session MONO composite) : message « canal R vide… » et image
  RESTANT visible.
- **Valider en réel le SCNR doux** (jalon 23) : SHO sans S et HOO —
  grésillement vert du fond retiré SANS bascule bleue.
- **Reportés v2 (assumés)** : darks/flats par filtre, STF par canal
  (opt-in), curseur de force du SCNR doux (k réglable).

## ⏭ Validations réelles en attente (nuits suivantes)

1. **Jalon 24** : gradient/débruitage par couche, live et externe (ci-dessus).
2. **Jalon 21b** : HOO/SHO en réel — refus de début de session réduits,
   méthode affichée par frame.
3. **Jalon 20** : re-stack compo en réel (ligne verte + détail par canal).
4. **Poursuivre le débogage QHY avec la Minicam8M** via le banc embarqué
   (`venv\Scripts\python.exe _diag_camera_qhy.py` dans le dossier
   d'installation) : le flux est validé (à 2000 ms → 0,5 fps exactement,
   donc l'exposition est bien appliquée par le ctrl 8). Le flux de travail
   du 19/09/2026 (« Démarrer » sans `set_resolution` dans le log, donc ROI
   jamais posée → plantage ; après un Arrêter, plus aucune frame) impose
   désormais cet ordre :
   1. **Copier LES DEUX fichiers ensemble** depuis le dépôt :
      `_diag_camera_qhy.py` ET `avastack\cameras\qhy.py`. Le banc affiche
      au lancement le bloc « fichiers réellement chargés » : vérifier que
      `set_resolution dans qhy.py : OUI` et
      `signature open() : (self, roi=None)`.
   2. **Verdict ROI** (automatique, en bas) : il doit dire « POSÉE ✔ ». S'il
      dit « AUCUNE TENTATIVE… ANTÉRIEURE à la v2.13.2 », c'est le FICHIER
      qui est en cause, pas la caméra → recopier `qhy.py`.
   3. Après un « ■ Arrêter » : **fermer le banc et le relancer** (le SDK ne
      peut pas être libéré dans le process — le binding n'expose aucune
      fonction de libération).
   4. Découverte des valeurs : **▶ Balayer** sur gain (6), offset (7) et USB
      traffic (12) ; **⏸ Pause 3 s** pour distinguer « la caméra n'émet
      plus » de « nos lectures vident la file du SDK ».
   5. **Refroidissement TEC** : consigne ctrl 18 / PWM ctrl 16, lectures 14
      et 15 — avec l'**alimentation 12 V** branchée, sinon la régulation est
      inactive.
   Puis reporter les bornes réelles dans l'appli (gain QHY en unités
   constructeur, plage actuelle 0,5-8,0 = bridée). En cas de crash natif :
   `%TEMP%\avastack_qhy_debug.log` donne la dernière étape réussie.

5. **Roue à filtres MiniCam8M (nouveau, 19/09/2026)** : sur le miniPC,
   avec le banc — « 🔬 Lister les contrôles » doit montrer
   `44 CfwSlotsNum` (le nombre RÉEL de slots) et `17 CfwPort` (48-55 = code
   ASCII) ; puis « ✍ Écrire » ctrl 17 = 48+n et vérifier l'EFFET PHYSIQUE
   (slot vide ou filtre opaque → l'image change). **Aucun code appli avant
   ce verdict.**

## 🎡 Roue à filtres MiniCam8M — conception validée (19/09/2026)

- **Pilotage** : position = contrôle 17 (`CfwPort`) en ASCII `48 + n`
  (n = 1..N), nombre de slots = 44 (`CfwSlotsNum`), roue présente =
  `is_control_available(17)`. Position relue À LA DEMANDE, jamais mémorisée
  (QHY précise que la position n'est fiable qu'une fois la rotation de retour
  au « home » terminée — logiciel lancé trop tôt = position affichée fausse).
- **Fin de rotation** : relecture de 17 en boucle jusqu'à la position cible,
  **timeout 25 s** (valeur conseillée par la doc QHY) + temporisation entre
  deux lectures. Écriture et attente DANS le thread de travail, jamais sur le
  thread Tk.
- **Jeu de filtres** : libellés configurables (L/R/G/B/Hα/SII/OIII…) et
  **filtre écrit dans les en-têtes FITS** des images en sortie.
- **Séquence d'acquisition** (décision d'Alain, vaut aussi pour le live
  stacking MULTIBANDE) : le changement de filtre **arrête l'acquisition**
  puis la **reprend** quand la rotation est terminée → **purge des frames
  arrivées pendant la rotation** (ne jamais empiler deux filtres dans le
  même empilement).
- **À implémenter (prochaine session)** : contrat dans `cameras/base.py`
  (no-op par défaut, dans l'esprit d'`apply_settings`) ; lecture /
  disponibilité + déplacement TRACÉ dans `cameras/qhy.py` (log QHY existant) ;
  ligne « Filtre » dans le cadre Caméra de `ui/app.py`, active seulement si
  la source a une roue ; demande consommée par le `_worker` à la manière de
  `pending_settings` (~ligne 2776) ; `_test_qhy_camera.py` étendu (faux SDK
  gérant 17/44 — les 32 tests actuels doivent rester verts) ; bump de version
  + changelog dans `avastack/__init__.py`. **Aucune dépendance nouvelle** →
  `requirements.txt` inchangé.
- **Pièges** : `48 + n` et non `47 + n` (un décalage d'un cran est invisible
  sans comparaison au slot PHYSIQUE) ; roue absente
  (`is_control_available(17)` faux) → l'UI reste inactive, sans erreur ;
  ne jamais écrire 17 avant que la caméra soit ouverte.

## Rappels utiles (court terme)

- **Tests** (PowerShell, venv) :
  `C:\Astro\astrolivestack\venv\Scripts\python.exe _test_xxx.py` — les
  32 fichiers `_test_*.py` doivent passer avant tout commit. Vérification
  syntaxique systématique avant livraison : `python -c "import ast;
  ast.parse(open('AVAStack.py', encoding='utf-8').read())"`.
- **Build installateur** (version lue AUTOMATIQUEMENT du source
  `AVASTACK_VERSION`, plus de version figée dans l'.iss) :
  `powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\build_avastack.ps1`
  → artefact `installer\windows\output\avastack-setup.exe` (gitignore).
  Rebuilder après chaque montée de version (jalon).
- **Diagnostic QHY** : le banc `_diag_camera_qhy.py` est **embarqué par
  l'installateur** (dossier d'installation) — détection, ouverture tracée,
  ROI, flux, tous les contrôles SDK et le refroidissement TEC.
  `%TEMP%\avastack_qhy_debug.log` trace chaque étape
  d'ouverture/fermeture de la caméra (un crash natif n'affiche RIEN à
  l'écran — le log dit la dernière étape réussie).
- **PIÈGE LANCEMENT** (voir aussi CLAUDE.md) : `python3` ne pointe PAS
  vers le venv — toujours lancer avec `python AVAStack.py`.
- **ORDRE DE LA CHAÎNE** (Alain, 16/09/2026 — ne pas l'oublier) :
  recadrage → gradient → débruitage → netteté → étirement. Le recadrage
  et le retrait de gradient ne sont pas des options.
- **Débruitage** : code gelé tel quel, cases décochées (décision du
  16/09/2026, test réel « pas top ») — ne pas retoucher sans nouvelle
  demande ; si le sujet est rouvert, le vrai chantier est l'interaction
  gradient × débruitage, pas la force.
- **Défauts livrés des traitements** (live = désactivé, NLM, force 0,5 ;
  externe = désactivé, GraXpert IA, force 0,5) confirmés par Alain :
  ne pas retoucher sans nouvelle demande.
- **CLAUDE.md — 2 leçons du jalon 13 PROPOSÉES le 17/09/2026, EN ATTENTE
  d'approbation d'Alain** (ne pas écrire sans accord explicite) :
  (1) contre-vérification par appariements mutuels des deux côtés + seuil
  relevé quand la décision sert d'ANCRE (sans prédiction) ; (2) deux
  normalisations indépendantes rendent une SSD aveugle — toute
  comparaison d'images doit partager les bornes de normalisation.
- **CLAUDE.md — 2 leçons « roue à filtres » ÉCRITES le 19/09/2026**
  (accord explicite d'Alain, même session) : (1) avant de conclure qu'une
  fonctionnalité manque, introspecter AUSSI les exports de la DLL native
  embarquée sous le binding (et sa version) — la DLL `qhyccd.dll` (SDK
  26-06-04) exporte toute l'API `...CFW...` alors que le binding Python
  n'expose que `Camera`/`init_sdk`/`scan_cameras` ; (2) une correspondance
  « valeur d'API ↔ position physique » ne se déduit ni d'une relecture ni d'une
  doc : `'0'` (doc QHY/INDI) vs `48 + n` (crate Rust, relevé réel
  `ctrl 17 = 49` sur le filtre 1) — seul l'effet sur le matériel tranche.
- **CLAUDE.md — 3 leçons du diagnostic caméra QHY ÉCRITES le 19/09/2026**
  (accord explicite d'Alain en clôture de session) : (1) SDK natif :
  introspection d'abord (`init_sdk` une seule fois, aucune fonction de
  libération donc état irréinitialisable dans le process, crash natif non
  rattrapable → trace fichier + sous-processus) ; (2) vérifier l'identité des
  fichiers réellement chargés AVANT d'interpréter un log de plantage (copie
  périmée = symptômes d'un bug) ; (3) un réglage relu à l'identique ne prouve
  pas qu'il est appliqué — seul l'effet physique le prouve.
- **CLAUDE.md — 1 leçon du jalon 24 PROPOSÉE le 19/09/2026, EN ATTENTE
  d'approbation d'Alain** (ne pas écrire sans accord explicite) :
  valider les placeholders d'un gabarit de commande AVANT la
  substitution (après, ils n'existent plus — le contrôle « il manque
  {input} » passait à tort sur une commande déjà remplacée, constat
  réel du débogage du 19/09/2026).
- **Prochaines vérifications de nuit** : suivre en direct la ligne
  « Align. : Δ(…) θ(…) méthode » et « Frames non alignées ».
- **Setup d'Alain** (17/09/2026) : C8 défourché + réducteur 0,63 →
  1280 mm ; Player One Uranus-C Pro (couleur, IMX585, 3856×2180, RGGB,
  GAIN 210) ; N.I.N.A. → dossiers
  `TargetSchedulerSequence/<cible>/<expo>/LIGHT` sur le miniPC — un
  dossier peut MÉLANGER plusieurs nuits (la 1re frame par mtime n'est pas
  forcément de la nuit courante).
---

## 🔚 Clôture de session — 19/09/2026 (soir)

Demande d'Alain : « on clôture cette session ». État : tests **32/32 OK**
(vérifiés par Alain), banc validé (test de fumée), **commit `1717b94` poussé**
sur `master`. **Installateur NON rebuildé** (consigne de la session : on ne
travaille que sur le diagnostic caméra) → l'artefact en place reste celui de
la **v2.13.3** : à rebuilder à la prochaine occasion, la version source étant
2.13.4.

**Prochaines étapes, dans l'ordre (à reprendre au début de la prochaine
session) :**

1. **Diagnostic caméra QHY — non terminé**. Le flux fonctionne (banc :
   détection → ouverture → ROI posée → frames), mais deux points restent
   ouverts :
   - **ROI sur le miniPC** : confirmer par le bloc « fichiers réellement
     chargés » + le **verdict ROI** du banc que la copie installée de
     `avastack/cameras/qhy.py` est bien à jour (c'est la cause désignée du
     plantage « Démarrer »).
   - **Plage réelle du gain QHY : INCONNUE** (le balayage passe partout,
     donc ne démontre rien) → méthode à changer : effet physique à gain
     croissant, ou doc constructeur.
2. **Relancer le banc ET l'appli en cas de reprise** : l'état du SDK QHY
   n'est pas réinitialisable dans le process (après un Arrêter, plus aucune
   frame) — limite qui vaut aussi pour l'appli (à traiter côté appli le jour
   où ce sera prioritaire).
3. **Ensuite seulement** : recalibrer le curseur de gain de l'appli (0,5-8,0
   actuellement = échelle Player One, inadaptée au SDK QHY) et rebuilder
   l'installateur.

