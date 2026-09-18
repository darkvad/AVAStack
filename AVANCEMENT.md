# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version : AVAStack v2.12.1** (`avastack/__init__.py`,
  `AVASTACK_VERSION = "2.12.1"`), branche `master`. Dernier jalon livré :
  **JALON 23b « Garde-fous GraXpert »** (19/09/2026, retour réel
  d'Alain : en SHO, GraXpert live pour le gradient → « plus d'image dans
  la visu », fréquent mais non systématique). Cause : en SHO sans S le
  canal R du composite est ENTIEREMENT VIDE → GraXpert reçoit une image à
  canal mort, comportement imprévisible (sortie dégénérée → noir après
  étirement). Garde-fous : (1) `couleurs.canal_mort` détecte un canal
  vide ; (2) le solveur VeraLux refuse de lancer GraXpert sur un canal
  mort — message clair « canal R vide (aucune donnée) : GraXpert live
  ignoré », la chaîne continue sur l'image brute ; (3) sortie d'outil
  dégénérée (NaN/Inf, image vide) rejetée avec repli/erreur claire
  (live ET externe). **⚠️ Le gradient (GraXpert live comme externe) est
  retiré sur le COMPOSITE, pas sur chaque couche** — un retrait par
  couche reste à faire (workflow manuel : sauvegarde par canal → GX par
  canal ; en live ce serait N lancements CLI par frame). Détails :
  changelog v2.12.1 + git. **Les 30 fichiers `_test_*.py` PASSENT.**
- **Base stable précédente : v2.12.0** (jalon 23 « SCNR doux borné par
  le bruit » : ne retire que l'excès de vert ≤ 3σ — σ sur le détail
  haute-fréquence — structure préservée, pensé pour les palettes
  narrowband où le SCNR classique fait virer l'image au bleu ; cases
  live « SCNR doux — bruit seul » et externe « 5. », Démagenta « 6. » ;
  ordre SCNR → SCNR doux → démagenta). Jalon 22 : SCNR classique +
  démagenta live/externe. Historique complet : changelog du source + git.
- **Pièges récents (jalon 20-23b)** : `var.get()` Tkinter interdit hors
  thread principal (bouchons `_Val`) ; crash OpenCV 5/OpenCL au teardown
  (`cv2.ocl.setUseOpenCL(False)`) ; **la vraie config d'Alain contient
  désormais ses lignes compo réelles (LRGB, dossiers N.I.N.A.)** — tout
  test qui crée `ui.App` doit être HERMÉTIQUE (`ui.CONFIG = {}` +
  `ui.sauver_config` intercepté) ; les images synthétiques des tests
  doivent être BRUITÉES (sans bruit, détection « image constante » →
  0 étoile → triangles impossibles, constat jalon 21) ; **mesurer
  l'effet d'un traitement d'affichage en STF AUTO est biaisé** (stats
  EMA/par image — comparer en manuel à points fixes, constat jalon 23) ;
  **les outils factices de tests subprocess doivent être autonomes**
  (astropy seul : le subprocess est lancé avec cwd = dossier temporaire,
  le package avastack n'y est pas importable, constat jalon 23b).

## 🔜 À faire — suite et validations du jalon 23b

- **Valider en réel les garde-fous GraXpert** : en SHO sans S, cocher
  GraXpert live → la ligne d'état doit afficher « canal R vide (aucune
  donnée) : GraXpert live ignoré » et l'image RESTER visible ; en
  RGB/LRGB (canaux vivants), GraXpert live doit fonctionner comme avant.
- **Valider en réel le SCNR doux** (jalon 23) : en SHO sans S et HOO —
  grésillement vert du fond retiré SANS bascule bleue.
- **Valider en réel le jalon 21b** : méthodes triangles/étoiles/phase
  affichées ; refus de début de session SHO réduits.
- **Reportés v2 (assumés)** : darks/flats par filtre, STF par canal
  (opt-in), curseur de force du SCNR doux (k réglable), **retrait de
  gradient PAR COUCHE** (workflow : canaux sauvegardés → GX par canal).

## ⏭ Validations réelles en attente (nuits suivantes)

1. **Jalon 23b** : garde-fous GraXpert en SHO sans S (ci-dessus).
2. **Jalon 23** : SCNR doux live et externe.
3. **Jalon 21b** : HOO/SHO en réel — refus de début de session réduits,
   méthode affichée par frame.
4. **Jalon 20** : re-stack compo en réel (ligne verte + détail par
   canal).

## Rappels utiles (court terme)

- **Tests** (PowerShell, venv) :
  `C:\Astro\astrolivestack\venv\Scripts\python.exe _test_xxx.py` — les
  30 fichiers `_test_*.py` doivent passer avant tout commit. Vérification
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
- **Prochaines vérifications de nuit** : suivre en direct la ligne
  « Align. : Δ(…) θ(…) méthode » et « Frames non alignées ».
- **Setup d'Alain** (17/09/2026) : C8 défourché + réducteur 0,63 →
  1280 mm ; Player One Uranus-C Pro (couleur, IMX585, 3856×2180, RGGB,
  GAIN 210) ; N.I.N.A. → dossiers
  `TargetSchedulerSequence/<cible>/<expo>/LIGHT` sur le miniPC — un
  dossier peut MÉLANGER plusieurs nuits (la 1re frame par mtime n'est pas
  forcément de la nuit courante).
