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
  - **Découverte des valeurs** : « Lister les contrôles » fait 2 passes —
    disponibles (nom officiel + valeur) puis **balayage exhaustif 0..63** avec
    valeur brute hexadécimale (distingue un contrôle ABSENT d'un contrôle
    « drapeau » à sentinelle 0xFFFFFFFF) ; **« ▶ Balayer »** pose/relit
    chaque valeur d'un id et affiche la plage acceptée (outil de recalibrage
    à venir). **⏸ Pause 3 s** + horodatage des 5 premières frames +
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
