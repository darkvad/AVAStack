# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version : AVAStack v2.15.0** (`avastack/__init__.py`), branche `master`.
  Dernier jalon : **OFFSET + ZONES DE SAISIE + DÉCONNEXION TRACÉE** (jalon 27,
  demandes d'Alain du 19/09/2026).
  - **OFFSET** : contrôle 7 (unités SDK) — contrat no-op `definir_offset`
    (`CameraBase`), implémenté sur QHYCamera ; slider « Offset (0 – 255) »
    (défaut 10) dans le cadre Caméra, poussé comme les réglages
    (pending_offset, exécuté par le worker) et posé à la connexion. À
    valider en réel (le SDK stocke sans valider — effet physique).
  - **ZONES DE SAISIE** : Gain et Offset → Entry à la place du label de
    valeur (Return/sortie de champ = application + bornage, curseur suit) ;
    EXPOSITION → Entry dédiée acceptant « 100 », « 0,5 », « 12 ms », « 2 s »,
    « 11 µs », avec bascule automatique d'échelle (courte ↔ longue) si la
    valeur déborde.
  - **DÉCONNEXION TRACÉE** : chaque étape dans le journal QHY ; close() en
    premier (coupe flux + TEC — l'écriture TEC en régulation avant close
    était le suspect du blocage silencieux) ; si pas de confirmation en
    10 s → message rouge dans l'UI (fermer la fenêtre = sortie bornée 15 s).
  - Jalons précédents : v2.14.3 (stop_live/begin_live sur la classe QHY,
    déconnexion via le worker, DLL SDK embarquées + zwoasi), v2.14.2
    (connexion figée = Tk hors thread), v2.14.1 (connexion à la détection,
    Démarrer = empilement seul, Arrêter = pause, relecture TEC 2 s),
    v2.14.0 (roue ctrl 17/48+n, TEC 18/14/15/16, exposition log, gain
    0-175, FITS FILTER).
  - **À valider en réel (miniPC)** : offset (effet physique), saisies
    expo/gain/offset, ⏏ Déconnecter (si échec : message rouge + log QHY à
    transmettre), filtre pendant pause/empilement.

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

## 🔚 Clôture de session — 19/09/2026 (fin de soirée)

Demande d'Alain : « mon setup est en train d'imager, je testerai une autre
fois, clôture la session ». État : **v2.15.0 poussée** (`0a10a3e`),
installateur REBUILDÉ (avec DLL SDK + zwoasi), tests **32/32 OK**.

**Prochaines vérifications de nuit (à reprendre à la prochaine session,
miniPC, version installée v2.15.0) — dans l'ordre :**
1. **Connexion** : sélection QHY → « connectée » vert en quelques secondes ;
   lignes Filtre + Refroidissement actives SANS démarrer l'empilement (jalon
   26 — les jalons 26/27 n'ont PAS encore été validés en réel).
2. **Refroidissement** : consigne (alim. 12 V branchée), % TEC, ⏹ Arrêter.
3. **Filtre** : choisir L/R/G/B/… avant puis PENDANT l'empilement (le
   stop_live AttributeError de v2.14.2 est corrigé — non revérifié en réel).
4. **Offset + saisies** : effet physique de l'offset (SDK stocke sans
   valider), saisie directe expo (« 2 s » → bascule d'échelle auto),
   gain/offset.
5. **⏏ Déconnecter** : message attendu « Caméra déconnectée. » — si blocage
   encore silencieux, message rouge à 10 s puis transmettre
   `%TEMP%\avastack_qhy_debug.log` (les étapes de déconnexion y sont
   tracées depuis v2.15.0 — close() en premier).
6. **Pause/reprise** : ▶/■ avec le MÊME empilement ; fermeture de la
   fenêtre propre (borne 15 s).
⚠️ Le setup IMAGE pendant ces tests : ne pas perturber la session
N.I.N.A. en cours sur le miniPC (tester AVAStack sur une autre machine ou
après la nuit).

---

## ✅ Jalon 25 (v2.14.0) — CONTRÔLES CAMÉRA QHY : ROUE À FILTRES +
## REFROIDISSEMENT (19/09/2026, session suivante)

Reprise demandée par Alain : « j'ai fait les tests. Le contrôle 44 indique
INDISPONIBLE mais le contrôle 17 fonctionne, j'ai pu changer les filtres
avec 48 + n (48 = position 0 = black, ensuite LRGBSHO). Tu peux déjà
implémenter cela. Dans le contrôle de la caméra : Exposition (11 µs → 900 s
avec case pour changer l'échelle : de 11 µs à 5 s, et de 1 à 900 s), Gain
de 0 à 175, température de consigne + affichage de la temp et du % de
chauffe (PWM) + bouton arrêt chauffage, choix du filtre Dark, L, R, G, B,
SII, Ha, OIII. » → **Implémenté, tests 32/32 OK, installateur REBUILDÉ
(v2.14.0)**.

- **`cameras/base.py`** : contrat no-op roue (`roue_disponible`,
  `position_filtre`, `choisir_filtre`) et refroidissement
  (`consigne_refroidissement`, `lire_refroidissement`,
  `arreter_refroidissement`) + constante `FILTRES_ROUE` = (Dark, L, R, G, B,
  SII, Ha, OIII) — position 0 = cran noir « Dark ».
- **`cameras/qhy.py`** : implémentation par les contrôles du SDK — roue :
  disponibilité testée sur **17 seul** (44 indispo en réel), position =
  `get_param(17)` − 48 (sentinelle 0xFFFFFFFF / code < 48 → None, jamais
  d'erreur), déplacement = `set_param(17, 48+n)` puis relectures jusqu'à
  confirmation (timeout 25 s, doc QHY) ; refroidissement : consigne = ctrl
  18 (mode auto), lectures = 14 (temp capteur) / 15 (PWM 0-255) / 18, arrêt
  = **PWM manuel ctrl 16 à 0**. Trace du log QHY à chaque étape.
- **`ui/app.py` — cadre Caméra** : exposition en CURSEUR LOGARITHMIQUE
  (0-1000 → 11 µs…5 s par défaut ; case « Échelle longue » → 1 s…900 s ;
  boutons ± au pas ×1,25 ; affichage µs/ms/s ; `var_expo` reste en ms
  réelles — contrat apply_settings et tests inchangés) ; gain 0 → 175
  (défaut 30, unités SDK QHY) ; ligne « Filtre : » (combobox
  Dark/L/R/G/B/SII/Ha/OIII, ACTIVE seulement si le sondage — fait par le
  worker après la 1re frame — trouve la roue) ; ligne refroidissement
  (consigne °C + boutons ❄ Réguler / ⏹ Arrêter + affichage « Capteur :
  x °C · TEC : n % (pwm/255) · consigne »). Demandes posées côté Tk,
  exécutées par le thread de travail (jamais d'appel SDK dans Tk).
  Changement de filtre : stop_live → déplacement → begin_live → PURGE des
  frames arrivées pendant la rotation (jamais deux filtres empilés —
  décision d'Alain). Le TEC est coupé automatiquement à l'arrêt de session.
- **`images.py`** : `save_image(path, arr, entete=None)` — mot-clé FITS
  FILTER = filtre courant (mono) / rôle (canaux composés).
- **`_test_qhy_camera.py`** : faux SDK étendu (is_control_available,
  get_param/set_param avec rotation simulée, contrôles TEC) — **31
  vérifications**, les 32 fichiers de tests restent verts.
- **Installateur REBUILDÉ** : `installer\windows\output\avastack-setup.exe`
  (v2.14.0, lue automatiquement du source).
- **À valider en réel (miniPC)** : déplacement de la roue DEPUIS L'APPLI,
  régulation TEC (alim. 12 V branchée), bornes réelles du gain (0-175 =
  plage SDK annoncée — seul l'effet physique tranche). Rappel : après un
  « ■ Arrêter », relancer l'appli (SDK QHY non réinitialisable dans le
  process).

