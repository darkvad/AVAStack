# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.34.5** (`avastack/__init__.py`),
  branche `master` — **SPCC ABSOLUE : VALIDATION CROISÉE AVEC SIRIL RÉUSSIE**
  (jalon 58) + **BUG de l'ÉQUILIBRAGE DES CANAUX en composition corrigé** :
  - **VALIDATION (24/09/2026, mêmes pixels)** : sur les couches BRUTES
    concaténées fournies à Siril (`spcc_brut_RGB.fit`, via
    `_diag_spcc.py --export-rgb`), Siril mesure R/V = 0,087250 + **0,872563**·cat
    (σ 0,1226) et B/V = 0,114178 + **0,792972**·cat (σ 0,1184), **K = 0,636 /
    0,775 / 1,000** ; AVAStack, mêmes pixels : **0,888** (σ 0,020) et **0,782**
    (σ 0,019), **K = 0,6232 / 0,7574 / 1,0000** → **écart 1,4 à 1,8 %** sur les
    pentes et ~2 % sur les coefficients, avec une **dispersion 6× meilleure**.
    Les chaînes CONCORDENT : les divergences des essais précédents venaient des
    IMAGES analysées (fichiers normalisés par rôle, gains Gaia appliqués), pas du
    modèle.
  - **BUG CORRIGÉ** : la case « Équilibrage des canaux (auto) », cochée, n'avait
    **aucun effet en composition** (`LiveStacker._equilibrer` est no-op sur une
    carte 2D, et chaque rôle EST une carte 2D). Elle s'applique maintenant au
    **COMPOSITE**, après la normalisation par rôle, avec cache (frames, force,
    cadre) et force partielle. Banc : fonds 0,30/0,15/0,10 → 0,16510 partout.
  - **MESURE DE FOND (piste ouverte)** : `composer()` **normalise déjà chaque
    rôle** par ses percentiles (0,25 %/99,7 %) → les fonds sont écrasés canal
    par canal et une PART des corrections de couleur est absorbée ; c'est
    pourquoi la SPCC a un effet **visible mais modéré** sur l'affichage
    (mesuré : R/G 0,877 → 0,793 ; B/G 1,136 → 1,325 après étirement), alors que
    Siril — qui ne normalise PAS par canal et applique en plus une **référence
    de fond par canal** (B0/B1/B2) — obtient un fond non bleu et un effet plein.
    Piste : option de normalisation COMMUNE aux trois canaux quand des gains de
    couleur sont actifs.
  - **Sauvegarde vs couches** : un enregistrement d'empilement n'est PAS
    comparable aux couches (normalisation par rôle + gains : gains implicites
    mesurés R/G 0,944 et B/G 1,242 sur le fichier d'Alain) → utiliser
    `--export-rgb` pour toute comparaison externe.

  branche `master` — **SPCC ABSOLUE BRANCHÉE ET VALIDÉE CONTRE SIRIL (jalon 58,
  24/09/2026)** :
  - **VALIDATION CROISÉE RÉUSSIE** : à partir du log SPCC réel de Siril fourni
    par Alain (mêmes couches M31 : `R/V = 0,086296 + 0,645948·cat`,
    `B/V = 0,194367 + 1,045936·cat`, `K0/K1/K2 = 1,000 / 0,923 / 0,866`), on
    déduit les ratios de blanc utilisés par Siril (1,2953 / 0,8332). AVAStack
    obtient 1,2954 / 0,8331 avec les MÊMES profils (Sony IMX585 × QHYCCD
    MiniCam8M R/G/B) → **accord à 1e-4** : réponses QE × transmission et
    traitement de la référence de blanc validés au chiffre près.
  - **PIÈGE MAJEUR CORRIGÉ DANS LE MODÈLE** : la conversion en COMPTAGE DE
    PHOTONS (× λ, cf. `flux_to_relcount` de Siril) n'est PAS neutre sur les
    ratios — λ est DANS l'intégrale (écart mesuré 17,2 %). La référence de
    blanc doit donc passer par la même conversion que les étoiles
    (`spcc.spectre_reference`) ; sans cela les coefficients sortaient quasi
    neutres (0,983/0,974/1,000) — la correction était fausse d'environ 20 %.
  - `spcc.coefficients_spcc()` : chaîne complète réutilisable (catalogue
    spectral Gaia, appariement mutuel, flux d'ouverture par canal, rejet des
    saturées ET des étoiles posées sur l'objet ÉTENDU, réponses, blanc,
    régressions robustes, garde-fou pente/dispersion comme Siril) ;
    `spcc.SessionSpcc` : état de session, gains par rôle, texte d'état.
  - **UI** : case « SPCC (couleurs absolues) » DÉCOCHÉE PAR DÉFAUT + sélecteurs
    Capteur / Filtre R / G / B / Référence de blanc peuplés par la base Siril
    (15 capteurs, 50 filtres, 144 références ; profils d'Alain pré-sélectionnés),
    ligne d'état qui dit toujours ce qui est appliqué ou POURQUOI rien ne l'est,
    persistance en config.json, actif en composition R/G/B avec WCS résolu.
    **Priorité** : cochée, la SPCC remplace les gains Gaia relatifs du jalon 56.
  - **BANC `_test_spcc_jalon58.py`** (11 sections) : fabrique une image
    cohérente avec le modèle (Planck × réponses, atténuations connues ×0,7 /
    ×1,3) et vérifie la VÉRITÉ ANALYTIQUE — pentes retrouvées **0,7000 /
    1,3000**, blanc rendu NEUTRE, robustesse, refus propres, piège des unités
    (blanc en ÅNGSTRÖMS), tout le branchement UI. Piège de banc : sans BRUIT de
    fond, la détection répond « image constante ».
  - **BUGS RÉELS CORRIGÉS le 24/09/2026 (v2.34.2, constatés sur la capture
    d'Alain)** : (1) `np.trapz` SUPPRIMÉ de numpy 2.x récent → la SPCC
    s'arrêtait sur « module 'numpy' has no attribute 'trapz' » (intégration via
    `_trapeze`, compatible numpy 1 ET 2 ; angle mort de la machine de
    développement, où numpy 2.3.3 garde encore `trapz`) ; (2) « Filtre R :
    QHYCCD MiniCam8M Luminance » — un profil de LUMINANCE (bande large) à la
    place d'une couleur, ou deux filtres identiques, donnent des coefficients
    FAUX : alerte affichée DÈS LA SÉLECTION des profils
    (`spcc.coherence_bandes`, partagé module/UI), et les avertissements de
    bandes + pente se cumulent. **ACTION UTILISATEUR** : remettre « Filtre R »
    sur `QHYCCD MiniCam8M Red`.
  - **BIAIS DE MESURE CORRIGÉ (v2.34.3, révélé par le 1er essai réel d'Alain le
    24/09/2026)** : l'appli ne mesurait que les **300 étoiles les plus
    brillantes** et n'écartait que celles à moins de 0,5 mag de la plus
    brillante. Or les étoiles brillantes ont le cœur **comprimé** (saturation)
    → contraste de couleur écrasé → pente de régression ATTÉNUÉE : sur ses
    couches, 150 étoiles → pente R/G 0,518 (B/R ×1,255), 300 → 0,576
    (×1,311), 900 → 0,765 (×1,480), 2400 → **0,817 (×1,499, converge)**. Sa
    mesure (R ×0,7192 / G ×0,8626 / B ×1,0000) était donc fausse (K_R 7 % trop
    haut). **Correctif** : `MAX_ETOILES` 300 → **1200** et `MARGE_SATURATION`
    0,5 → **1,5 mag** → 946 étoiles retenues, pentes 0,819 (σ 0,037) / 0,782
    (σ 0,017), K = **0,6683 / 0,7548 / 1,0000** (B/R ×1,496) en **0,9 s**.
    Les σ faibles (0,032/0,074) ne révélaient pas le problème : c'était un
    BIAIS, pas du bruit — leçon retenue.
  - **VÉRIFIÉ** : l'**équilibrage des canaux (auto)** et la **profondeur de
    l'empilement** n'affectent pas la mesure — `CompositeStacker.moyennes()`
    ne renvoie que les couches **BRUTES** par rôle (l'équilibrage est no-op sur
    une carte 2D). La SPCC porte donc bien sur l'image brute, comme il faut.
  - **PIDGE DE BANC** corrigé : les étoiles synthétiques du banc n'avaient pas
    de plage de luminosité (spectres normalisés à 500 nm) → toutes les
    magnitudes voisines, et le nouveau seuil de saturation les écartait toutes.
    Le banc tire désormais une magnitude (0-5 mag) indépendante de la couleur.
  - **COMPARAISON STRICTE AVEC SIRIL (v2.34.4)** : `_diag_spcc.py --export-rgb
    FICHIER` écrit un **FITS RGB des couches BRUTES** (concaténation, sans
    normalisation ni gain) avec les mots-clés WCS — **c'est l'objet à analyser
    par Siril** : une sauvegarde d'empilement d'AVAStack n'est PAS comparable
    (elle passe par `composer()`, qui normalise chaque rôle par ses
    percentiles et y applique les gains : gains implicites mesurés R/G 0,944 et
    B/G 1,242 sur le fichier d'Alain). Fichier produit pour son cas :
    `C:\Astro\test\spcc_brut_RGB.fit` (3838×2168×3, 32 bits, ordre R/G/B
    standard). PIÈGE corrigé au passage : le WCS du banc est lu **dans
    l'en-tête de la couche** (le `.wcs` séparé décrit une AUTRE grille dès que
    la session a été ré-empilée — 16 appariements au lieu de ~2000 sur des
    couches recadrées de 6 px).
  - **« PAS DE DIFFÉRENCE VISIBLE SPCC COCHÉE / DÉCOCHÉE » (v2.34.4)** :
    vérifié de bout en bout sur ses couches (canaux → `composer()` →
    `DisplayProcessor`, en STF **et** VeraLux) : la correction EST appliquée et
    visible — R/G affiché 0,877 → 0,793 et B/G 1,136 → 1,325 avec ses
    coefficients (l'étirement atténue les gains de moitié, sans les annuler ;
    les stats d'étirement sont prises sur la LUMINANCE, jamais par canal).
    **Explication de fond** : la SPCC corrige la couleur des **ÉTOILES**
    (référence : galaxie spirale moyenne) et applique les **mêmes gains au
    FOND** — un fond pollué reste donc bleu-vert, voire davantage (le blanc de
    référence est plus rouge que vert). La couleur du **FOND** relève du
    **retrait de gradient**, celle des **ÉTOILES** de la SPCC : deux
    traitements distincts (c'est la raison de l'avertissement de Siril).
  - **Rafraîchissement du rendu en fin d'empilement : vérifié sain** — le bloc
    qui pose `gains_roles` et demande le rendu est AVANT la lecture d'une frame
    (il tourne même quand aucune brute n'arrive : leçon du jalon 55).



  - **À FAIRE (prochaine étape)** : validation croisée FINALE avec Siril sur une
    image **SANS gradient** (Siril signale lui-même sa solution comme imprécise
    sur l'image actuelle : dispersion 0,131/0,151 mag contre 0,04 mag chez
    nous, et pentes divergentes 0,65/1,05 vs 0,81/0,78). **Découverte à
    creuser** : les couches fournies ont un **décalage R-G de 0,56 px** (B-G :
    0,07 px) — ré-empiler avec l'alignement sous-pixel du jalon 57 avant toute
    nouvelle mesure.
  - **PIÈGE MAJEUR DÉCOUVERT (24/09/2026, 2e log Siril)** : le retrait de
    gradient ne change RIEN aux pentes de Siril (0,6459 → 0,6456 ; 1,0459 →
    1,0449) → la divergence des pentes n'était pas le gradient. En revanche,
    `m31_stacl_lineaire.fits` (l'image que Siril a réellement analysée) **n'est
    PAS** la somme de `canal_R/G/B.fit` : ses canaux portent des gains
    implicites R/G 0,9651 et B/G 1,2022 — soit exactement les **gains Gaia
    relatifs du jalon 56** (×0,9451 / ×1,1530) : la sauvegarde linéaire avait
    été faite **case « Gains photométriques (Gaia) » cochée**. Siril a donc
    calibré une image DÉJÀ refroidie par nos gains, et ses K « réchauffent »
    simplement pour annuler ces gains. Leçon pour toute comparaison future :
    **sauvegarder le linéaire avec les gains Gaia DÉCOCHÉS**. Sur l'image
    équilibrée + le protocole exact de Siril (disque 10,6 / anneau
    10,6→20,6) nos pentes remontent à 0,76 / 0,90 (contre 0,65 / 1,05) : la
    convergence est partielle, le résidu venant de la méthode de photométrie
    (Siril : centroïdes PSF, exclusion fine des étoiles, fond par canal) et
    peut-être des profils de filtres de la base (qualité 2/5) face aux filtres
    réels d'Alain. **Protection ajoutée dans l'UI** : quand la SPCC est active,
    les gains Gaia sont ignorés et la ligne des gains le DIT.

- **Historique immédiat** : v2.33.0 (veille, même jalon 58) apportait les
  FONDATIONS — `catalogues/spcc_db.py` (lecture de la base SPCC de Siril :
  capteurs, filtres, références de blanc, PIÈGE des QUATRE unités de longueur
  d'onde — les références de blanc sont en ÅNGSTRÖMS), `processing/spcc.py`
  (modèle de Siril : réponse = QE × filtre, spectres, régressions robustes,
  coefficients) et surtout la **correction d'un BUG MAJEUR du décodage des
  spectres Gaia** (`catalogues/siril_cat.py` : `astype(np.float16)` au lieu de
  `view(np.float16)` et `× 10^fexpo` au lieu de `÷` — spectres plats à 1,02
  pour TOUTES les étoiles ; bug LATENT, aucun module ne les utilisait avant la
  SPCC). Détail complet : changelog de `avastack/__init__.py`.

- **Historique immédiat** : v2.32.0 (jalon 57, veille) corrigeait l'ALIGNEMENT
  SOUS-PIXEL ENTRE COUCHES — constat réel d'Alain (« astrométrie et Gaia
  bons, mais image pas correcte » — franges rouge/cyan autour des étoiles,
  empilement M31 R+G+B de 31 frames). Mesure sur les fichiers réels :
  la couche ROUGE sort décalée de 0,573 px (dX −0,207±0,231 ; dY
  −0,534±0,116 ; 271 appariements mutuels d'étoiles) quand B/G sont alignés
  à 0,049 px, et la transformation R→G porte une ÉCHELLE de 0,9998 (pas une
  simple translation). Les canaux et le composite étant écrits depuis la
  MÊME grille, la cause est dans l'empilement : **le chemin ORB ne PEUT PAS
  corriger le sous-pixel** (points clés localisés à ~0,5-1 px → l'IDENTITÉ
  gagne le consensus RANSAC à 2 px : mesuré Δ=(0,000, 0,000) pour un
  décalage réel de 0,573 px, 0,17-0,40 px d'erreur résiduelle sur des
  décalages imposés de 0,15 à 1,5 px). **Correctif** : raffinement par
  CENTROÏDES d'étoiles après ORB (`_raffiner_centroides`, appariement
  mutuel ≤ 1,5 px + similitude RANSAC 0,75 px + contre-test 2,5 px ;
  échec → matrice d'ORB inchangée), vérifié en réel : reste
  (−0,019, −0,020) px, méthode affichée « ORB+étoiles(46) », latence
  213 → 309 ms par frame. Bug réel corrigé au passage :
  `photometrie.flux_ouverture` plantait (IndexError) sur une étoile proche
  d'un bord. Outil embarqué `_diag_align_precision.py`.
- **ÉTAPES 4 ET 5 LIVRÉES les 23/09/2026 (jalon 56)** :
  - **étape 4, MESURE** (v2.30.0) : étoiles de l'empilement appariées
    MUTUELLEMENT au catalogue Gaia (positions + G) via le WCS résolu/propagé,
    ZÉRO-POINT par bande (`m_G + 2,5·log10(flux) = ZP(bande)`) — module
    `processing/photometrie.py`. **RÉSULTAT RÉEL** (brute G de M31) :
    244 appariements, médiane 0,46 px, dispersion 0,156 mag (G 9,4→14,2),
    sans aucun spectre (SPCC relative).
  - **étape 5, APPLICATION** (v2.31.0, OPT-IN d'Alain) : case « Gains
    photométriques (Gaia) », DÉCOCHÉE PAR DÉFAUT, qui écrit les facteurs dans
    le composite. **PIÈGE CENTRAL** : `composer()` normalise chaque rôle par
    ses percentiles AVANT les gains → un facteur par rôle était ABSORBÉ
    (vérifié au banc) ; les facteurs sont donc convertis RÔLE → CANAL
    (`canaux_rgb` : HOO Ha→R/O3→G,B ; SHO S2→R/Ha→G/O3→B) et appliqués APRÈS
    la normalisation, multipliés aux gains manuels R/G/B
    (`CompositeStacker.gains_effectifs()`). Les COUCHES restent BRUTES
    (contrat jalon 54) et le solveur live reçoit les gains EFFECTIFS dans
    `vl_compo` (vues « empilement » et « traitée » cohérentes). Composition
    Mono : aucun gain appliqué (l'appli le dit). Banc : composite ×2,000 /
    ×0,500 exactement là où attendu, défaut intact, worker opt-in vérifié.
  Rappel v2.29.0 : repli ASTAP quand aucun indice — le poste d'Alain n'a que
  **D80** (pas de base de balayage) : l'appli le DIT au lieu d'attendre pour
  rien ; le solveur interne tolère des coordonnées approximatives (~1°).
- **BUG TROUVÉ ET CORRIGÉ (v2.31.3, retour réel d'Alain le 24/09/2026)** —
  « l'astrométrie reste en attente d'un empilement plus profond (2/20 essais)
  alors que les étoiles ne manquent pas » (195 étoiles au seeing). Le quota de
  réessais corrigé en v2.31.1/2 fonctionnait bien (2 essais sur 20) : le vrai
  défaut était **DANS le solveur interne**. Diagnostic mené sur les fichiers
  FRAIS d'Alain (`C:\Astro\test\m31_stacl_lineaire.fits` + canaux) : ASTAP
  place le champ à 2,7″/4,9″ des indices (échelle 2,4633″/px) et son WCS vrai
  montre que 98 des 120 étoiles détectées tombent sur Gaia à moins de 2 px
  (médiane 0,91 px) → **indices, cadrage et données parfaits** ; le vote
  (échelle, angle) était juste lui aussi (pic 714 paires, échelle 1,0012,
  angle −89,83°) mais le raffinement ne récoltait que **4 inliers**.
  **CAUSE RACINE** : le vote ne peut PAS dire si l'appariement d'une paire est
  direct (i1↔k1) ou croisé (i1↔k2) — les deux ne diffèrent que de π sur
  l'angle, soit exactement le décalage porté par `ac + π` ; le code DÉDUISAIT
  l'ordre des correspondances du cas gagnant (`anc`). Sur M31, le pic de 336
  paires du cas « anc=1 » était peuplé de paires **directes**, auxquelles il
  imposait donc l'appariement croisé (mesuré sur un couple connu bon : 4
  inliers au lieu de 94). **CORRECTIF** : un pic PAR PARITÉ (le plus peuplé)
  et les DEUX appariements essayés au raffinement (coût inchangé : 2 parités
  × 2 appariements = les 4 cas d'avant).
  **VÉRIFIÉ EN RÉEL** : couche R 96 appariements, G 94, B 83, composite RGB
  94, fichier composite 94 — tous RÉSOLUS (rms 0,59-0,63 px) là où les 5
  échouaient. Bancs solveur + banc RÉEL M31 + astro jalon 56 + photométrie
  jalon 56 : tous au vert. Latence réellement mesurée du solve : **6,0 s** sur
  3844×2171 (une seule fois par empilement, puis propagation) — après
  optimisation du vote (comptage direct de bins au lieu de `np.histogram2d`,
  échelle calculée une fois par bloc, angle du cas « +π » dérivé par rotation
  circulaire des bins), `RANSAC_N_CAT` 120 → 60 et plafond des couples
  candidats à 400 (les plus longs d'abord) : **18,6 s → 6,0 s (÷3,1) à rms
  STRICTEMENT identiques** (vérifié sur 5 images réelles).
  **PIÈGE mesuré et ABANDONNÉ** : borner les paires catalogue au vote aux plus
  LONGUES (2 000 sur 7 136) casse le vote sur une brute unique peu profonde
  (brute G N.I.N.A. : pic erroné à 1,614″/px au lieu de 2,465) — le pic
  correct a besoin de TOUTES les paires.
  Outils de diagnostic ajoutés : `_diag_vote.py` (vote et raffinement
  instrumentés, comparés au WCS vrai d'ASTAP), `_diag_appariement.py` (écart
  de chaque étoile détectée à Gaia). Au passage : **13 bancs + le jalon 19
  n'étaient pas hermétiques** (ils lisaient le vrai config.json, qui contient
  astrométrie cochée + indices → de vraies résolutions pendant les bancs) —
  tous corrigés.
- **Tâche en cours** : **jalon 57 — vérification en réel du correctif
  d'alignement** (l'utilisateur doit RE-EMPILER ses couches M31 avec la
  v2.32.0 : la ligne d'état doit afficher « ORB+étoiles(N) » et les franges
  rouge/cyan autour des étoiles doivent disparaître ; si les brutes R/G/B de
  la session sont retrouvées, on mesurera le décalage résiduel entre canaux
  directement sur les empilements rejoués). Reste ouvert : décider si les
  couches DÉJÀ empilées (avec franges) méritent une correction a posteriori
  (translation mesurée par appariement d'étoiles à la composition) — utile
  seulement si l'utilisateur ne peut pas ré-empiler.
- **Tâche en cours (jalon 56)** : **étape 6 — validation Siril + test réel
  multibande** (vérifier que les en-têtes WCS écrits sont relus par Siril, et
  juger les gains photométriques sur une vraie série multi-filtres d'Alain).
  POINT CLARIFIÉ le 24/09/2026 : la SPCC de Siril exige, elle, les COURBES DE
  TRANSMISSION des filtres ET la RÉPONSE DU CAPTEUR (profils fournis par
  Siril) pour prédire le flux attendu par bande ; AVAStack ne mesure qu'une
  photométrie RELATIVE contre Gaia G (aucun spectre, aucune transmission) —
  c'est pourquoi les gains Gaia refroidissent l'image (dispersion des
  zéro-points croissante vers le bleu : R 0,162 / G 0,233 / B 0,376 mag).
- **Prochaine étape** : étape 6 (validation Siril/ASTAP sur les fichiers
  écrits, puis test réel HOO/SHO ou LRGB avec la case des gains cochée).
  Option ouverte : la SPCC ABSOLUE (spectres Gaia xp_sampled × transmissions
  filtre/capteur de la base Siril) par-dessus cette calibration relative —
  à décider : embarquer la base Siril de transmission, ou s'en tenir à la
  mesure relative avec un garde-fou de fiabilité (dispersion des ZP).

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

## 🔚 Clôture de session — 22/09/2026 (v2.26.0, jalon 56 étape 3 : livré, bancs au vert)

État exact : **jalon 56 étape 3 (propagation WCS par composition) LIVRÉ,
banc `_test_propagation_jalon56.py` TOUT AU VERT (exit 0)** — composition
exacte 2,3e-13 px vs vérité analytique, `vers_tan` ≡ astropy.wcs (2,6e-14°),
re-solve indépendant ≈ propagé à 0,46″, chaîne de réempilement exacte,
StarAligner réel 0,42 px, échecs propres vérifiés. Bancs étapes 1 et 2
relancés : toujours au vert. Découverte validée : similitude ∘ TAN = TAN
exact (propagation SANS PERTE). Rien d'UI ni de branché au worker : la
propagation est prête, le BRANCHEMENT + la PHOTOMÉTRIE par bande (étape 4) suivent.
- Décisions de la session (accord d'Alain) : SPCC local multibande
  MiniCam8M en premier puis OSC ; solveur astrométrique interne avec
  indices (pas de re-solve à chaque réempilement : propagation WCS par
  composition de transformations) ; ASTAP = référence indépendante/repli.
- Conventions astap_cli VÉRIFIÉES EN RÉEL (22/09/2026, CLI-2024.11.17) :
  `-ra` en heures, `-spd` = 90 + dec, `-fov` = hauteur du champ en degrés,
  succès = exit 0 + `.wcs` (matrice CD) + `PLTSOLVD=T`.
- **BUG CORRIGÉ EN COURS DE SESSION (v2.26.1, retour réel d'Alain)** :
  « Enregistrer l'empilement (linéaire) » écrivait le RGB avec les canaux
  sur NAXIS1 → ASIFitsView/Siril voyaient N images de 3 px de large
  (image « noire »). save_image écrit maintenant les canaux sur NAXIS3
  (convention astro) et load_image normalise en (H, W, C) ;
  `_test_save_rgb_axes.py` au vert. La note d'alors (« les valeurs > 1 d'un
  composite — jusqu'à ~14 sur M31 — sont normales ») a été CORRIGÉE en
  v2.27.1 : ces valeurs rendaient le fichier NON résolvable par ASTAP et
  « saturé » pour tout lecteur qui suppose [0,1]. Ce n'était bien PAS la
  cause de l'image noire (c'était NAXIS1 = 3). Bancs jalon 14 / save
  linéaire / worker compo repassés au vert.
- **PRIORITÉ RÉSOLUE (v2.27.1, 22/09/2026) — l'empilement linéaire d'une
  composition est maintenant RÉSOLVABLE par ASTAP** (consigne d'Alain :
  « l'empilement linéaire en sortie, mode dossiers (compo RGB), est saturé
  et non solvable par ASTAP ») :
  - MESURES sur son fichier (`c:\Astro\test\m31_test_solve.fits`,
    3×2165×3839 float32, canaux sur NAXIS3 — axes donc BONS depuis v2.26.1) :
    fond à 0,02, **max 14,1**, 0,3 % des pixels > 1 ; en-tête sans aucun
    mot-clé d'échelle ;
  - DIAGNOSTIC ASTAP (astap_cli CLI-2024.11.17) : **« Only 0 stars found in
    image »** → `ERROR=Not enough stars` dans le .ini ; le MÊME contenu borné
    à 1 se résout en 0,2 s (143 quads sur 144). Cause : sa conversion 16 bits
    écrase un fond à 0,04. Et un lecteur qui suppose [0,1] clippe le cœur de
    M31 + les cœurs d'étoiles en blanc — l'image « paraît saturée »
    (aperçus PNG comparés : clip-à-1 vs percentiles) ;
  - CAUSE RACINE : `composition.normaliser` (percentiles 0,25/99,7 SANS
    clip) — sur M31 le cœur vaut ~14× le p99,7. Le composite est la SEULE
    donnée de l'appli hors [0,1], alors que VeraLux (clip d'entrée + piège
    max > 1,1 → /65535), le débruitage, les sorties TIFF/PNG et ASTAP
    supposent tous [0,1] ;
  - FIX : `images.borner_lineaire(arr, entete)` — UN facteur GLOBAL (jamais
    par canal : couleurs et linéarité au bit près), consigné dans l'en-tête
    (**AVASCALE**, réversible, + HISTORY), nan/inf neutralisés et comptés
    (**AVANAN**). Appliqué aux 3 écritures linéaires (empilement, résultat
    traité, canaux `canal_*.fit`) ; no-op dès que max ≤ 1 ;
  - POURQUOI PAS au niveau du composite : VeraLux travaille en valeurs
    ABSOLUES (target_bg, logD résolu) → changer l'échelle du composite
    changerait la vue live et le rendu « tel que vu ». **La vue ne change
    PAS** : ce sont les FICHIERS qui redeviennent lisibles ;
  - BANCS : `_test_save_lineaire_echelle.py` (nouveau) TOUT AU VERT — [1]
    bornage + AVASCALE + réversibilité, [2] no-op si ≤ 1, [3] nan/inf, [4]
    worker réel → fichier borné / (C,H,W) / FILTER / proportionnalité, [5]
    mono 0,25 au bit près, [6] TIFF : 693 px blancs → 1, [7] **ASTAP RÉEL
    résout le fichier borné : 2,4639″/px ≈ la brute G du même setup** (et
    l'original non borné reste non résolu — contrôle informatif, un outil
    tiers ne fait pas échouer le banc) ; `_test_solveur_reel_m31.py` passe
    désormais ASTAP sur la version BORNÉE du composite : Δ max 4,73″,
    Δ échelle 0,0010″/px, Δ orientation locale 0,006° ;
  - bancs repassés au vert : axes FITS couleur, save linéaire (v2.5.1),
    worker compo (jalon 19 — attendu adapté : le fichier = composite /
    AVASCALE), compo UI (canaux), calib compo, re-stack compo, tel que vu ;
  - installateur rebuili (v2.27.1).
- **RÉSOLU (v2.27.0, 22/09/2026) — le solve INTERNE résout maintenant les
  vraies images d'Alain** : `_diag_solve_reel.py` avait montré l'échec en
  réel (empilement composite 2,6° @ 243 mm ET brute G N.I.N.A. : « pas assez
  de correspondances mutuelles (4) »). Cause : sur un champ large/riche, le
  top-12 d'image ≡ top-20 de catalogue PAR INVARIANTS ne tient plus (listes
  qui ne coïncident plus : saturation, limmag, bruit) → l'affinité exacte
  3 points est dégénérée. Correctif : **repli RANSAC de paires**
  (`_ransac_paires`, esprit astrometry.net) — vote (échelle, angle) sur
  toutes les paires top-60 image × top-120 catalogue en 4 parités, similitude
  exacte 2 points évaluée par appariements mutuels, puis stabilisation
  Umeyama à rayon croissant ; les DEUX chemins passent par le même
  `_finaliser` (Gauss-Newton + 3σ + garde-fous) et se remplacent quand l'un
  est REJETÉ ; `info["methode"]` trace le chemin retenu.
  - banc RÉEL `_test_solveur_reel_m31.py` AU VERT : composite 2,6° → 86
    étoiles, rms 0,59 px, 2,4650″/px (centre à 20″ des indices) ; brute G →
    70 étoiles, rms 0,44 px, 2,4652″/px. Même optique → échelles concordant
    au millième (contrôle croisé gratuit) ;
  - **validation croisée ASTAP (brute G)** : écart max 2,78″ sur bords +
    centre, Δ échelle 0,0013″/px, Δ orientation locale 0,004° ;
  - pièges : le vote doit comparer des PIXELS à des PIXELS (catalogue passé
    dans la grille indicée) ; remettre `best_M = None` après échec des
    mutuelles (sinon `_finaliser(None, None, …)` fabrique un axe parasite) ;
    l'angle du CD brut n'est PAS comparable entre deux CRVAL différents
    (0,57° d'écart apparent pour des positions concordant à 2,8″) ;
  - bancs jalon 56 étapes 1/2/3 relancés : TOUJOURS AU VERT (le chemin
    triangles reste le principal, le repli est un filet).
- Prochaine étape (à froid) : **branchement au worker** (solve une fois
  sur l'accumulation avec les indices de la cible ; propagation à chaque
  re-stack : UN seul alignement nouvelle référence ↔ ancien empilement),
  puis **étape 4 — photométrie + facteurs par bande**, 5 (gains du
  stacker), 6 (validation Siril + réel).

Sessions précédentes : v2.23.3 (jalon 55 : gains compo temps réel,
aca5ca5, validé Alain) ; v2.21.10 (jalons 50-52, banc Touptek +
ergonomie caméra, 7d3034e, validés par Alain) — détail dans l'historique
git et le changelog du source.

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
