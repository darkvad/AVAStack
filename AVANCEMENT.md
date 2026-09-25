# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---


- **Version stable de référence : AVAStack v2.35.2** (`avastack/__init__.py`),
  branche `master` — **CORRECTIFS v2.35.2 (constats d'Alain, 25/09/2026)** :
  - **LA MOLETTE CHANGEait LA VALEUR DES LISTES DÉROULANTES** (Tk associe la
    molette aux `ttk.Combobox` par une liaison de CLASSE
    `ttk::combobox::Scroll` — vérifié : un cran fait passer « a » → « b »). En
    défilant les réglages, si le curseur passait sur une liste, elle changeait
    TOUTE SEULE → **des réglages ont pu changer sans intention et FAUSSER DES
    TESTS** (profil de filtre de la SPCC, méthode du recalage…). Les liaisons de
    classe sont supprimées au démarrage : la molette ne modifie plus aucune
    liste et fait défiler le panneau. ⚠️ **PENSER À RE-VÉRIFIER les profils
    SPCC** : sur sa capture du 25/09 le profil « Filtre B » était
    **QHYCCD MiniCam8M Green** (vraisemblablement modifié par cette molette) —
    d'où une mesure SPCC aberrante (pente B/G NÉGATIVE, avertissement « hors de
    [0,5 ; 1,5] ») appliquée quand même.
  - les en-têtes disent quand RIEN n'est appliqué : `AVASPCC` / `AVAGAIA` =
    « non appliquee (case cochee, mesure indisponible) » si la case est cochée
    sans mesure exploitable (avant, l'en-tête restait muet et laissait croire
    que la SPCC était dans le fichier).
  - la mesure SPCC est faite **UNE fois par session** (décocher/recocher la
    refait) : le libellé l'annonce désormais — « mesure faite sur N frames
    (décocher/recocher la case pour refaire) ».
- **Version stable précédente : AVAStack v2.35.1** — **CORRECTIF du 25/09/2026** :
  en COMPOSITION, la sauvegarde pleine résolution traitait GraXpert/débruitage
  live sur le COMPOSITE (> 1 : un cœur d'étoile monte à ~18 après la
  normalisation par rôle) alors que ces outils sont CONTRACTÉS POUR [0..1] —
  GraXpert rescalait sa sortie et le NLM la `clip(0,1)` (mesuré sur son
  empilement M31 : 96 % des pixels > 1 perdus, AVASCALE 1,21 au lieu de 17,94).
  La sauvegarde pleine résolution exécute désormais la chaîne **PAR COUCHE**
  (comme le solveur live) : GX + débruitage sur chaque couche 2D, recomposition,
  CORRECTIONS, puis netteté/SCNR → le fichier garde son échelle linéaire
  (banc `_test_save_brute_jalon59.py` [7]). Outil de diagnostic ajouté :
  `_diag_empilement_couleur.py`.
- **CHANTIER v2.35.0** (24/09/2026, décisions d'Alain) — tous les bancs
  logiciels au vert (sweep du 25/09/2026 : 50 bancs, code de sortie 0 ; les
  bancs matériels sont hors sweep) :
  **SAUVEGARDE LINÉAIRE BRUTE + CORRECTIONS DE COULEUR DANS LA CHAÎNE DE
  SORTIE** (étapes ①→⑦ du plan), en détail :
  - `composer()` ne porte PLUS aucun gain : il produit l'EMPILEMENT BRUT
    (normalisation par rôle + combine L). `composer(gains=…)` N'EXISTE PLUS.
  - Toutes les corrections de couleur vivent en AVAL, dans
    `composition.corrections_couleur()` = gains R/G/B (manuels × SPCC/Gaia) →
    équilibrage des canaux auto → recalage « Linear Fit ». Primitives :
    `appliquer_gains`, `appliquer_gains_canaux`, `appliquer_equilibrage`.
  - `CompositeStacker.mean()` / `mean_avec_canaux()` : nouveau paramètre
    `corrections=True` (DÉFAUT = comportement d'affichage inchangé) ;
    `corrections=False` = EMPILEMENT BRUT (ce que la sauvegarde linéaire
    enregistre). `LiveStacker.mean()` accepte le même paramètre (équilibrage et
    recalage sautés : c'est la voie du fichier brut, y compris en mono/OSC ;
    l'interface des deux classes reste identique).
  - Sauvegardes « empilement (linéaire) » et « canaux (par filtre) » : chemin
    BRUT. **Preuve au banc** (`_test_save_brute_jalon59.py` [4]) : le fichier
    est IDENTIQUE AU PIXEL PRÈS avec et sans SPCC/gains Gaia/équilibrage/
    Linear Fit cochés, alors que l'affichage, lui, change.
  - Solveur live : l'équilibrage est transporté (6e élément de `vl_compo` =
    actif/force/cadre, déballage tolérant) et appliqué APRÈS la recomposition
    des couches traitées, AVANT la netteté — ordre validé (c). Le traitement
    EXTERNE par couche (`_run_external_compo`) suit la même chaîne.
  - **NOUVEAU bouton** (décision (a)) : « 💾 Enregistrer l'empilement traité
    (linéaire)… » = 3e sortie linéaire — empilement brut → gradient live →
    débruitage live → CORRECTIONS → netteté → SCNR, SANS étirement ni
    gamma/saturation. Il emprunte le thread de « tel que vu »
    (`_save_asseen_thread(..., lineaire=True)`, 4e élément de la demande) et
    écrit un en-tête auto-descriptif. Le bouton « résultat traité (linéaire) »
    du cadre Traitement externe reste lié au ⚡ manuel (instantané).
  - En-têtes (étape ⑥) : `AVASPCC` / `AVAGAIA` sont désormais les MESURES de la
    session (mêmes formats `K=…` / `B=…`) ; la NOUVELLE clé `AVAAPPLI` dit ce
    qui est RÉELLEMENT appliqué à l'image écrite (« aucune (empilement BRUT) »
    pour le brut, liste des corrections pour le traité) ; `AVAWB` / `AVAFIT` ne
    sont écrits que s'ils sont appliqués ; `AVAVUE` décrit la vue enregistrée
    (« empilement BRUT … » / « empilement TRAITE … sans etirement »).
  - Bancs : `_test_save_brute_jalon59.py` (NOUVEAU, 6 sections : composer sans
    gain, façade deux chemins, ordre des corrections, **fichier identique
    cases cochées/décochées**, solveur live à 6 éléments, 3e sortie linéaire
    réelle) ; adaptés : `_test_composition_jalon19` [4] (gains via
    `appliquer_gains`), `_test_save_lineaire_echelle` [4] (référence =
    `mean(corrections=False)`), docstring de `_test_compo_worker_jalon19`.
- **PIÈGES DU CHANTIER (à retenir)** :
  - `composer()` est appelé par QUATRE chemins (façade, solveur, externe par
    couche, bancs) : retirer un paramètre ne casse RIEN à la compilation — le
    banc jalon 19 [4] est ce qui l'attrape ;
  - une correction appliquée APRÈS `composer()` n'est plus absorbée par la
    normalisation par rôle (c'est le but) : TOUTE vue qui doit ressembler à
    l'affichage doit passer par `corrections_couleur` (façade, solveur,
    sortie traitée) — sinon les vues divergent ;
  - `wb_auto` est posé sur le stacker à la CRÉATION seulement (le worker ne le
    resynchronise pas à chaque tour), alors que gains / mode L / recalage le
    sont ;
  - pour toute comparaison EXTERNE avec Siril, sauvegarder le linéaire
    (maintenant BRUT par construction : c'est la référence reproductible).
  - **LES OUTILS LIVE SONT CONTRACTÉS POUR [0..1]** (v2.35.1) : GraXpert live
    rescalait et le NLM (`denoise._nlm`) ÉCRÊTE à [0,1] + quantifie 16 bits.
    Une image qui dépasse 1 doit donc y entrer **PAR COUCHE** (les couches
    sont ≤ 1, le composite NON : ~18 après la normalisation par rôle).
    Vérifier AVASCALE dans l'en-tête d'un fichier écrit : s'il vaut ≈ 1 alors
    que le brut vaut ~18, l'écrêtage a eu lieu.
  - `_diag_empilement_couleur.py` répond en une commande à « pourquoi mon
    image est-elle colorée / bruitée ? » : fond et σ par canal (le BRUIT),
    contraste de fond R/G et B/G, rapport brut/traité, clés AVA*.
- **EN ATTENTE DE DÉCISION D'ALAIN (piste ouverte, 25/09/2026) — LE GRAIN
  BLEU-VERT NAÎT DANS LA COMPOSITION** (mesuré au plancher de bruit, zones les
  plus lisses, sur son M31 RGB de 165 frames) :
  - COUCHES brutes `canal_*.fit` : σ 0,000498 / 0,000557 / 0,000526 →
    **grain équilibré** (R/G 0,89 · B/G 0,94) ;
  - composite BRUT v2.35.0 : σ 0,00517 / 0,00781 / 0,01133 →
    **grain COLORÉ** (R/G 0,66 · B/G 1,45).
  Cause : `composer()` normalise CHAQUE rôle par ses propres percentiles
  (p0,25/p99,7) ; la dynamique du bleu est 2,1× plus étroite que celle du rouge
  (M31 est jaune : peu de signal bleu) → le grain bleu est amplifié 2,2× de plus
  que le rouge. Le grain est donc déjà coloré AVANT l'étirement et AVANT les
  corrections ; les corrections de couleur (SPCC R ×0,53 + Linear Fit R ×0,76 /
  B ×1,21) ne font que le modifier un peu. **Le mode STF ne le montre pas parce
  que son étirement auto est bien plus doux que VeraLux (logD 2,0 / fond visé
  0,12) sur une image bruitée.**
  Pistes : (a) **normalisation COMMUNE aux 3 rôles** quand des corrections sont
  actives — la piste rejetée en v2.34.6 le sera moins maintenant que GraXpert
  live retire le fond PAR COUCHE, et le recalage « Linear Fit » (offsets) sert
  de référence de fond à la Siril ; (b) gains appliqués AUX COUCHES avec bornes
  FIGÉES (argument `bornes=` déjà là) ; (c) ne pas empiler le GAIN du Linear Fit
  sur la SPCC (Siril n'ajoute qu'une référence de FOND) ; (d) accepter.
- **POURQUOI STF ET VERALUX NE MONTRE PAS LA MÊME IMAGE (constaté, documenté)** :
  tout le cadre VeraLux (GraXpert live, débruitage live, SCNR live) est MASQUÉ
  en mode STF (`_on_moteur` : `frm_veralux.pack_forget()`) et le thread solveur
  — seul chemin du GX live — ne tourne qu'en mode VeraLux. En STF, l'image est
  donc le composite corrigé + netteté, SANS retrait de gradient ni débruitage.
  Seule la netteté est commune aux deux moteurs. C'est une décision de
  conception ; à rouvrir si Alain veut un rendu identique entre les moteurs.
- **À FAIRE / À VALIDER PAR ALAIN** :
  - test RÉEL du correctif 2.35.1 : réécrire « empilement traité (linéaire) »
    avec GraXpert + débruitage live actifs et vérifier AVASCALE (~18, plus
    1,2) et des cœurs d'étoiles non écrêtés. **Installer l'installateur
    2.35.1 AVANT** ;
  - test RÉEL du chantier v2.35.0 : « empilement (linéaire) » neutre/brut
    (Siril : plus de gain implicite à annuler) ;
  - étape 6 du jalon 56 : validation Siril/ASTAP des fichiers écrits, puis test
    réel multi-filtres avec les gains photométriques cochés.
- **POINT CLARIFIÉ (24/09/2026)** : la SPCC de Siril exige les COURBES DE
  TRANSMISSION des filtres ET la réponse du capteur (profils Siril) pour
  prédire le flux attendu par bande ; la photométrie d'AVAStack est RELATIVE
  contre Gaia G (aucun spectre, aucune transmission) — d'où des gains Gaia qui
  refroidissent l'image (dispersion des zéro-points croissante vers le bleu :
  R 0,162 / G 0,233 / B 0,376 mag). La SPCC ABSOLUE (v2.33-2.34) est, elle,
  branchée et validée à 1,4-1,8 % contre Siril sur les MÊMES pixels
  (`_diag_spcc.py --export-rgb`).



## Statuts CLAUDE.md

- Leçons ÉCRITES le 19/09/2026 (accord d'Alain) : introspection des
  exports de la DLL sous le binding ; convention roue `48+n` vs `'0'`
  tranchée par l'effet physique ; SDK natif (init unique, état non
  libérable, crash → trace + sous-processus) ; identité des fichiers
  chargés avant toute interprétation ; réglage relu ≠ réglage appliqué
  (seul l'effet physique prouve).
- Leçons ÉCRITES le 20/09/2026 (accord d'Alain, « écris les 2 ») :
  jalon 13 (appariements mutuels + seuil relevé quand la décision sert
  d'ANCRE ; deux normalisations distinctes rendent une SSD aveugle —
  partager les bornes) ; jalon 24 (valider les placeholders d'un gabarit
  AVANT la substitution). Plus AUCUNE leçon en attente.

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
- **Outils astro locaux vérifiés (22/09/2026)** : Siril 1.4.4
  (catalogues : chunks Gaia XP dans `%LOCALAPPDATA%\Siril\...`,
  base SPCC capteurs/filtres dans `siril-spcc-database`) ; ASTAP
  (`C:\Program Files\astap`, astap_cli.exe + base D80 Gaia DR3 1,24 Go)
  ; PAS d'astrometry.net/ANSVR.


## Pièges récents (rappels opérationnels)

- **LIMITE QHY (toujours valable)** : après « ■ Arrêter », relancer
  l'appli — le binding qhyccd n'expose AUCUNE libération du SDK (état
  irréinitialisable dans le process) ; le banc QHY l'annonce et conseille
  fermer + relancer.
- Entry/Combobox/`var.get()` Tkinter interdits hors thread principal —
  lire les widgets DANS Tk puis passer les valeurs au worker (bouchons
  `_Val` dans l'appli) ; toute contrôle `_on_*` finit par
  `_refresh_preview()`, les `_sync_*_vue` ne touchent qu'à l'ÉTAT.
- **Installateur à REBUILDER avant tout test réel dès que la passe de code
  touche PLUS d'un ou deux fichiers** (`powershell -NoProfile
  -ExecutionPolicy Bypass -File installer\windows\build_avastack.ps1`) —
  à la charge de l'agent, sans qu'Alain ait à le demander.

## Clôtures précédentes

- 21/09/2026 (v2.23.3, aca5ca5) : jalon 55 VALIDÉ PAR ALAIN en réel
  (M31 RGB, mode dossier) — gains R/G/B temps réel, image équilibrée.
  Rappel opérationnel : équilibrage auto OU Linear Fit re-normalisent les
  canaux → gains manuels sans effet tant que l'un des deux est actif ;
  pour réchauffer les tons, MONTER R. Repli si régression : v2.22.0
  (225f026).
- 20/09/2026 : TOUTES les validations matérielles (QHY miniPC, Player
  One, SVBONY, roue, TEC, cadence 39-46, ergonomie 47-48) CLOS — verdicts
  d'Alain ; bancs `_diag_camera_*.py` conservés pour diagnostic futur.
- Crash OpenCV 5/OpenCL au teardown (`cv2.ocl.setUseOpenCL(False)`) ;
  tests `ui.App` hermétiques (`ui.CONFIG = {}` + sauver_config
  intercepté) ; images de tests bruitées (sinon 0 étoile).
- Ne JAMAIS mélanger grid et pack dans le même conteneur Tk (attrapé par
  le test UI du banc POA : `_tkinter.TclError` « grid is already
  managing its content windows »).
- SDK natif : chargement UNE fois par process ; crash natif non
  rattrapable → tracer chaque étape dans un fichier ; vérifier
  l'identité des fichiers réellement chargés AVANT d'interpréter un
  plantage (les bancs affichent DLL + module + dates).
- PIÈGE LANCEMENT : `python3` ≠ venv — toujours `python AVAStack.py`.
- Ordre de la chaîne (Alain, 16/09/2026) : recadrage → gradient →
  débruitage → netteté → étirement. Débruitage : code gelé, cases
  décochées (décision du 16/09/2026) — ne pas retoucher sans nouvelle
  demande ; défauts des traitements confirmés (live = désactivé, NLM,
  force 0,5 ; externe = désactivé, GraXpert IA, force 0,5).
