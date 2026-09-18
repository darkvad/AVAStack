# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version : AVAStack v2.13.0** (`avastack/__init__.py`,
  `AVASTACK_VERSION = "2.13.0"`), branche `master`. Dernier jalon livré :
  **JALON 24 « Gradient + débruitage PAR COUCHE »** (19/09/2026, décision
  d'Alain : « autant nettoyer les images le plus tôt possible » — pollution
  lumineuse et lune ne frappent pas pareil selon le filtre ; une palette
  Hubble n'est pas un fond physique). En COMPOSITION, gradient (GraXpert) et
  débruitage sont faits sur CHAQUE COUCHE AVANT composition ; la NETTETÉ
  reste SUR LE COMPOSITE (avis demandé par Alain, rendu et suivi :
  PSF identique pour
  toutes les couches, meilleur SNR après débruitage, moitié moins de
  calcul). Ordre : couches (gradient → débruitage) → recomposition →
  netteté → étirement. Live : worker pousse les couches via
  `disp.vl_compo` (`CompositeStacker.mean_avec_canaux`, une seule passe de
  moyennes) ; solveur = caches PAR RÔLE (une nouvelle frame ne relance QUE
  la couche qui en a reçu une). Externe (⚡) : GraXpert gradient +
  débruitage par couche en FITS 2D MONO (plus de convention canaux-en-tête
  pour ces étapes), recomposition, puis BXT + chaîne couleur sur le
  composite. Échec d'une couche = couche brute + message ; échec d'un
  subprocess = erreur claire. Mode mono : chaîne composite historique
  INCHANGÉE (jalons 4/9). **Les 31 fichiers `_test_*.py` PASSENT**
  (dont `_test_gradient_couche_jalon24.py`). Le garde-fou jalon 23b
  (canal mort) reste actif en mono ; en composition il devient inutile par
  construction (couches mono 2D).
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

## Rappels utiles (court terme)

- **Tests** (PowerShell, venv) :
  `C:\Astro\astrolivestack\venv\Scripts\python.exe _test_xxx.py` — les
  31 fichiers `_test_*.py` doivent passer avant tout commit. Vérification
  syntaxique systématique avant livraison : `python -c "import ast;
  ast.parse(open('AVAStack.py', encoding='utf-8').read())"`.
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
