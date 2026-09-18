# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version : AVAStack v2.13.3** (`avastack/__init__.py`), branche
  `master`. Dernier jalon : **BANC CAMÉRA QHY v2.13.3** (19/09/2026, aucun
  changement du comportement applicatif) : le banc `_diag_camera_qhy.py` est
  désormais **embarqué par l'installateur** (outil autonome : détection,
  ouverture tracée pas-à-pas, ROI, flux live, liste des contrôles SDK,
  écriture set_param, **refroidissement TEC**) — demandé par Alain pour
  déboguer hors application, sans relancer les tests de non-régression.
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
  substitution** (après, ils n'existent plus — constat jalon 24).

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
   donc l'exposition est bien appliquée par le ctrl 8). À tester ensuite :
   le **refroidissement TEC** (consigne ctrl 18 / PWM ctrl 16, lectures 14
   et 15) — avec l'**alimentation 12 V** branchée, sinon la régulation est
   inactive ; puis reporter les bornes réelles dans l'appli (gain QHY en
   unités constructeur, plage actuelle 0,5-8,0 = bridée). En cas de crash
   natif : `%TEMP%\avastack_qhy_debug.log` donne la dernière étape réussie.

## Rappels utiles (court terme)

- **Tests** (PowerShell, venv) :
  `C:\Astro\astrolivestack\venv\Scripts\python.exe _test_xxx.py` — les
  31 fichiers `_test_*.py` doivent passer avant tout commit. Vérification
  syntaxique systématique avant livraison : `python -c "import ast;
  ast.parse(open('AVAStack.py', encoding='utf-8').read())"`.
- **Build installateur** (version lue AUTOMATIQUEMENT du source
  `AVASTACK_VERSION`, plus de version figée dans l'.iss) :
  `powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\build_avastack.ps1`
  → artefact `installer\windows\output\avastack-setup.exe` (gitignore).
  Rebuilder après chaque montée de version (jalon).
- **Diagnostic QHY** : `%TEMP%\avastack_qhy_debug.log` trace chaque étape
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
