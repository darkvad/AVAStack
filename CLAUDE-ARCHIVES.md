# CLAUDE-ARCHIVES.md — historique des chantiers (complément de `CLAUDE.md`)

Ce fichier est le complément **HISTORIQUE** de `CLAUDE.md` : il contient le
**récit daté** des chantiers TERMINÉS — mesures, étapes, essais, témoins,
corrections successives — **recopié au mot près** depuis `CLAUDE.md` (aucune
réécriture, aucune perte) lors de l'allègement du 21/10/2026 (v2.98.9).

**Comment s'en servir** : `CLAUDE.md` reste la mémoire chargée à CHAQUE session
(conventions non-négociables, règles de codage, pièges encore actifs, doc des
outils externes, comportement COURANT). Ce fichier-ci se lit **SUR DEMANDE**,
quand une session touche le domaine d'un chantier archivé — l'index des
sections archivées se trouve dans `CLAUDE.md`, section « Historique des
chantiers — ARCHIVÉ (`CLAUDE-ARCHIVES.md`) ».

**Règle d'écriture** : un chantier TERMINÉ dont le récit ne sert plus à décider
est **déplacé ici** (jamais supprimé, jamais réécrit) ; restent dans `CLAUDE.md`
les règles, les conventions, les pièges encore actifs et la description du
comportement COURANT. L'historique détaillé version par version vit de toute
façon dans `avastack/__init__.py` (changelog) et `git log`.

---

## Pose vraie contre pose appliquée (étape ⑩, 18/10/2026) — repli `phase` piégé

- **QUESTION** : les 4 brutes B divergentes entre runs recevaient des poses
  différentes. Deux hypothèses à trancher : « 143 se trompe de référence » ou
  « 140 rejette à tort ». Réponse MESURÉE : **ni l'une ni l'autre**.
- **PROTOCOLE (reproductible, hors appli)** :
  ① les empreintes de la trace ne disent pas le NOM du fichier — on les apparie
  en rejouant `images.load_image` → `calibration.Calibrator.apply` (dark du
  rôle) → `trace_roles.empreinte` (`_diag_148_apparie_empreintes.py`) ;
  ② la référence initiale des deux runs est la 1re brute **R** du 14/09 à
  **02:36:47** (empreinte `780545b1…`, retrouvée par `_diag_148b`) ;
  ③ `astap_cli.exe -f <fits> -fov 1.5 -r 10 -D d80` écrit un `.ini` avec la
  **matrice CD** (TAN) — pas besoin de l'interface ;
  ④ la pose VRAIE relative à la référence s'obtient en projetant une grille de
  points frame → ciel → référence et en ajustant `p_ref = A·p_frame + t`
  (`_diag_148d_pose_vraie.py`). `t = (dx, dy)` est EXACTEMENT ce que la trace
  nomme `dx/dy` (OpenCV `M[0,2]`, `M[1,2]`, source → référence).
- **CONTRÔLE DE CONVENTION** : la seule brute prise AVANT le retournement
  (`B_0000`, PIERSIDE=West) rend t = (+0,90 ; −5,95) px contre (+0,85 ; −6,18)
  appliqués, soit **0,2 px** — la chaîne de mesure est juste.
- **MESURE** : le retournement méridien a eu lieu vers **04:04** (PIERSIDE West
  → East dans l'en-tête FITS). Toute brute East exige une **rotation de
  +177,07°** et une translation ≈ **(+3911, +2074)** px ; un modèle « translation
  seule » laisse un résidu de **2591 px** ⇒ aucune translation ne peut l'aligner.
  Or les 4 divergentes (`382c13ae`, `e9c346e6`, `28e2b89d`, `68e09a71`) sont
  empilées avec **|angle| = 0** dans **les DEUX runs** (erreur ≈ 4 400 px).
- **ÉTENDUE — LES 51 BRUTES B RÉSOLUES** (`_diag_148g_solve_toutes.py` puis
  `_diag_148h_toutes.py`, 0 échec) : **23 West** à **+0,004…+0,013°** (résidu
  d'une translation seule ≤ **0,4 px**) et **28 East** à **+177,019…+177,070°**
  (résidu ≥ **2 590,9 px**) ⇒ aucune translation ne peut aligner une East. Au
  140 : 50 empilées, **39 justes** (méd 0,21 px, max 1,33) et **11 à l'envers**
  (22 %) ; au 143 : 49 empilées, **37 justes** (méd 0,19, max 1,65) et **12 à
  l'envers** (24,5 %). **Toutes** les fausses sont dans le **lot East du 14/09**
  (11/16 et 12/16) ; 16/09 West (20 f.) et 23/09 East (11/10 f.) sont **toutes
  justes**. `b1441134` est le cas révélateur : ORB réussit au 140 (erreur
  **1,0 px**) et `phase` prend sa place au 143 (erreur 4 424 px) — même brute,
  même instant, seule la référence diffère.
- **CAUSE DANS LE CODE** : `StarAligner.compute()` rend dès que
  `_compute_direct()` « réussit » — et cet essai INCLUT le repli `phase`
  (`_sans_orb` → `_sans_phase`). Le réessai **+180°** n'a lieu que si le direct
  ÉCHOUE. Sur un champ retourné où ORB/triangles ne trouvent pas d'étoiles
  communes, `phase` (corrélation de translation, qui s'accroche au MOTIF FIXE du
  capteur) « réussit » à ~0 px : la frame est empilée à l'envers et **jamais
  rejetée**. Le commentaire de `_compute_direct` le dit déjà (« la phase
  validerait du bruit retourné ») — l'interdiction n'était appliquée qu'au
  réessai, pas au chemin direct.
- **CE QUE ÇA EXPLIQUE** : ce n'est PAS la profondeur de la pile G qui crée le
  défaut ; elle déplace le pic de `phase`, donc les translations bidon. Quand
  elles se RESSERRENT (143 : 7 frames à ±10 px), les étoiles retournées
  s'accumulent au même pixel, gonflent σ (×4,38) et **survivent** à
  kappa-sigma ; quand elles se DISPERSENT (140 : +37,8 / +21,9 / −14,1),
  kappa-sigma les rejette (σ ×1,02). D'où une « force du bleu » qui dépend de ce
  que porte la référence, à défaut du nombre de rôles.
- **SUITE — PLAN ⑪ décidé par Alain (3 étapes, chacune testée par LUI)** : ①
  supprimer `phase` en broadband (RGB/LRGB±Ha), à essayer aussi en mono/OSC, ordre
  ORB → triangles inchangé ; ② ajouter le **raffinement centroïdes APRÈS
  `triangles`** (aujourd'hui ABSENT : `_triangles` rend la matrice LMEDS brute,
  contrairement aux chemins ORB et `étoiles` — c'est le gain « parfait ») ; ③
  tester **SHO/HOO sans `phase`** pour savoir si elle y sert. MESURÉ avant de
  toucher au code : `phase` porte aussi les AUTRES rôles — **29/80 R, 11/50 B,
  3/59 G** (140) et **14/80 R, 13/80 L, 9/62 G, 12/49 B** (143) — donc ① REFUSERA
  des frames (toutes méthodes à étoiles déjà essayées avant `phase`). Nuance : une
  partie de ces frames tombe sur des nuits **West** (16/09), où une translation
  seule est légitime — les classer exige d'apparier les empreintes R/G/L aux
  fichiers (même méthode que `_diag_148`). En SHO/HOO `triangles_seuls=True` : la
  cascade y est DÉJÀ triangles → étoiles → `phase`. **ÉTAPE ① LIVRÉE le
  18/10/2026 (v2.82.2)** — cf. la section suivante ; ② et ③ restent à faire.
- **PIÈGES** : une empreinte ne dit pas le SENS du champ — `PIERSIDE` et
  `ANGLE`/`OBJCTROT` sont dans l'en-tête FITS ; `astap_cli` n'accepte pas les
  chemins UNC (copier en local) ; le `.wcs`/`.ini` d'ASTAP est en convention
  FITS (même tableau que `load_image`, aucun flip) ; une frame « alignée »
  n'est pas une frame JUSTE : `align_ok=True` avec `angle=0` reste compatible
  avec un champ retourné.

## Étape ① du plan ⑪ — plus de repli `phase` en broadband (v2.82.2, 18/10/2026)

- **CE QUI EST CHANGÉ** : `StarAligner.repli_phase` (interrupteur) + la constante
  `PHASE_EN_BROADBAND = False` + `repli_phase_session(narrowband)` dans
  `processing/alignment.py`. **Une seule source décide** ; le worker ne fait
  qu'appliquer, **PAR SESSION**, à la création de l'empileur :
  `self.aligner.repli_phase = repli_phase_session(self._narrowband_ha())`.
  En **broadband** (RGB/LRGB±Ha, mono, OSC) → **False** ; en **HOO/SHO** → **True**
  (l'étape ③ mesurera ce que la phase y apporte). L'aligneur privé de propagation
  du WCS (`_astro_propager_restack`) COPIE le drapeau ; les deux aligneurs du Ha
  (voie A : `aligner_ha`, `_recalage_ha_aligneur`) restent au comportement
  historique — canal narrowband, hors périmètre du ①.
- **LE VERROU EST DANS `_sans_phase`, PAS DANS `compute`** : `_sans_phase` exige
  **les deux** conditions (`avec_phase` du réessai +180° **et** `repli_phase`).
  Conséquence VOULUE : le chemin direct ne peut plus « réussir » par une
  translation seule, donc `compute` atteint son réessai **+180°** puis l'ORB
  étoffé. L'**ORDRE** de la cascade est inchangé : ORB → triangles → étoiles →
  (phase) — ne pas le réordonner sans mesure.
- **DÉFAUT PAR DÉFAUT `True`** : `StarAligner()` reste au comportement historique,
  sinon tous les bancs et les appelants directs changeraient de résultat sans le
  vouloir. C'est le **worker** qui décide, une fois par session.
- **PAS DE CASE DANS L'INTERFACE (décision d'Alain du 18/10/2026)** : l'interrupteur
  reste la constante `PHASE_EN_BROADBAND` (modification + relance de l'appli, puis
  nouvelle session — il est appliqué à la création de l'empileur). Une case ne sera
  ajoutée que si le besoin de jongler entre les 2 modes **selon les cibles**
  apparaît ; le drapeau étant fixé PAR SESSION, une case n'aurait qu'à écrire
  `aligner.repli_phase` (penser au miroir thread-sûr : le worker ne lit jamais Tk).
- **MESURÉ AU BANC NEUF** `bancs/_test_phase_broadband_jalon132.py` (8 volets) :
  une réussite « phase » en translation seule n'est plus **jamais finale** (avec
  l'interrupteur à True elle était acceptée à **angle 0** sur une frame
  impossible à apparier ; à False, `_phase` n'est **plus appelée du tout** et la
  frame est **refusée**) ; un champ retourné de **177,07°** est **RETOURNÉ**
  (|angle| ≈ 177°, **résidu 0,01 px** contre la pose vraie) ; une frame RICHE
  simplement translatée s'aligne toujours sans phase ; la table **par rôle**
  (L/R/G/B × 8 frames) donne le **COÛT** : **6/8** frames faibles refusées contre
  **1/8** avec la phase, et **0 frame à l'envers** dans les deux modes.
- **COÛT RÉEL ATTENDU** (mesuré au ⑩, à confirmer par le run d'Alain) : ce sont
  les frames que **seule** la phase plaçait qui seront refusées — **29/80 R,
  11/50 B, 3/59 G** au run 140 et **14/80 R, 13/80 L, 9/62 G, 12/49 B** au 143 ;
  une partie tombe sur des nuits **West** où la translation était légitime.
- **PIÈGE DE BANC — `phase` ne se scénarise pas** : la corrélation de phase réussit
  ou non selon le CONTENU (elle a « réussi » sur un champ tourné dans une scène
  et refusé dans une autre, à paramètres voisins). Le volet « le piège » teste donc
  le **CHEMIN DE DÉCISION** avec un espion (`_phase` remplacée par une réussite en
  translation seule) : c'est la cause dans le code, et elle est déterministe. Pour
  le **coût**, il faut une frame **douce et peu contrastée** (contraste 0,10,
  bruit 0,008, flou σ = 1) : les étoiles y perdent leurs points ORB, la structure
  à basse fréquence reste.
- **TRACE** : `trace_roles.noter_reference` écrit désormais `repli_phase` — sans
  ce drapeau, un run « avec » et un run « sans » phase se ressemblent (mêmes
  brutes, même référence) et la mesure des refus par rôle ne se compare pas.
  Le compteur de refus par rôle (`bad_frames_par_role`, ligne « Non alignées par
  rôle ») reste la mesure de terrain.

## Étape ② du plan ⑪ — centroïdes APRÈS `triangles` : MESURE (18/10/2026)

- **QUESTION** : `_triangles` rend-il une matrice MOINS précise que les chemins
  ORB et `étoiles`, qui la raffinent sur les centroïdes
  (`_raffiner_centroides`) ? Le plan ⑪ le supposait (« la matrice LMEDS brute ») ;
  le code, lui, **consolide déjà** (correspondances mutuelles ≤ 2,5 px → RANSAC
  2,5 px → LMEDS → contre-test final d'appariements mutuels). Mesure AVANT toute
  correction, comme au ①.
- **PROTOCOLE (reproductible)** : run **réel LRGB+Ha** par le vrai `ui.App`
  (`_run_133b_fresh_linear.py` : mêmes brutes, mêmes masters dark, même ordre,
  même politique de référence, `--no-save`, `--trace`), avec un espion PASSIF
  greffé sur la CLASSE `StarAligner` **avant** la construction de l'appli
  (`_espion_155.py`). Pour chaque matrice `triangles` réussie il écrit : l'empreinte
  de la brute, le domaine (`direct` / `retournee`), les étoiles détectées, le
  couple (`n_avant`, `res_avant`) de `_verif_centroides` sur la matrice de
  `triangles`, puis `n_raff` de `_raffiner_centroides` et le couple
  (`n_apres`, `res_apres`) **sur le MÊME jeu de centroïdes**, plus `d_px`,
  `d_angle`, `d_echelle` et les deux matrices. L'espion rend EXACTEMENT
  `(M, ok)` de l'original, avale toute erreur, et n'est jamais sur le chemin
  d'une décision.
- **PIÈGE D'INSTRUMENTATION — L'EMPREINTE NE SUFFIT PAS À JOINDRE UNE FRAME** :
  les re-stacks (`_do_restack`, `_do_restack_compo`), le recalage de la couche
  Ha (`_recaler_ha`) et la propagation d'astrométrie (`_astro_propager_restack`)
  réalignent des **EMPILEMENTS**. Leur empreinte peut COÏNCIDER avec une brute
  (couche Ha à **1 frame** = la brute elle-même) : mesuré au 1er essai, une
  « frame Ha » était en réalité le recalage de la couche, et la jointure avec la
  trace ⑦ attribuait à une frame un chemin qu'elle n'avait pas pris. Il faut
  MARQUER ces trois chemins (`marquer_restack`) et les exclure — 40 frames vues
  passer en re-stack dans le run final, aucune mesurée.
- **POPULATION MESURÉE** (475 lues → **472 empilées**, 1 floue, **2 refus G**) :
  `triangles` porte **143 frames (30,3 %)** — B 16/51, G 33/61, **Ha 39/40**,
  L 31/240, R 24/80. Les refus sont **G 2**, sur référence `G/auto` : un
  raffinement ne REFUSE jamais, le ② ne peut donc en retirer aucun.
- **RÉSIDU DE LA MATRICE `triangles` SUR LES ÉTOILES** : méd **0,083 px** ·
  p90 **0,675** · max **1,385**. Classes : **87/143 ≤ 0,10 px** · 13 dans
  0,10-0,30 · 30 dans 0,30-0,70 · 13 > 0,70.
- **CE QUE LES CENTROÏDES CHANGENT** : candidate gardée **112/143** (78 %), 31
  inchangées ; résidu méd 0,0855 · p90 0,644 · max **1,141** ; 107 meilleures,
  5 égales (plus d'appariements), **0 pire** (par construction). Gain :
  **90 frames < 0,05 px**, 4 dans 0,05-0,10, 12 dans 0,1-0,3, **1 seule ≥ 0,3**
  (max 0,734) ; méd **0,002 px**. Translation déplacée : méd 0,018 px, p90 0,784,
  max 2,934 — **7 frames seulement > 1 px**, et ce sont les pires (ex.
  1,385 → 0,651 px).
- **PAR RÔLE (résidu méd avant → après)** : B 0,060 → 0,060 · G 0,082 → 0,084 ·
  Ha 0,070 → 0,069 · **L 0,484 → 0,467** · R 0,083 → 0,082.
- **CONTRÔLE POSITIF 200 ÉTOILES** (transformation CONNUE) : **202**
  appariements, résidu **0,0438 px** à la vraie matrice, **1,4904 px** pour une
  erreur connue de 1,5 px (lu − connu = −0,0096), retour à **0,0104 px** après
  raffinement ; scénario rotation 0,15° + échelle : 176 appariements, 0,0533 px,
  erreur retrouvée à 0,0148 px. ⇒ la chaîne de mesure réagit à une erreur connue.
- **COÛT** de `_raffiner_centroides` par frame `triangles` : méd **100 ms** ·
  p90 160 · max 405 (l'alignement d'une frame dure des secondes : le ② serait
  indolore).
- **LECTURE** : le gain est NÉGLIGEABLE sur 95/143 frames (66 %, < 0,05 px,
  dont 5 nuls) même si une candidate est GARDÉE sur 112/143 ; il est réel
  seulement sur les 7 pires (correction PARTIELLE, 12 à 50 % de l'erreur).
  Le résidu systématique de la couche **L (~0,48 px)** n'est PAS touché : c'est
  la **distorsion inter-nuits** du jalon 117 (palier ~0,8 px, qu'un affine
  n'améliore pas), ce n'est pas une translation. **DÉCISION D'ALAIN (18/10) :
  choix C** — raffiner SEULEMENT au-delà de `TRI_RAFFIN_SEUIL` (0,30 px) ;
  plan d'implémentation et banc dans `AVANCEMENT.md` § « Prochain chantier ».
- **OUTILS hors dépôt** : `_espion_155.py` (espion), `_lance_155.py` /
  `_lance_155_fond.py` (run réel détaché), `_diag_155a_methodes.py` (méthodes des
  traces 140/143), `_diag_155b_controle.py` (contrôle 200 étoiles),
  `_diag_155c_analyse.py` (jointure + agrégats), `_diag_155d_detail.py`
  (distribution des gains, refus), `_attendre_155.py`. Preuves :
  `_155_centroides.jsonl`, `_trace155/155.jsonl`, `_155b_controle.json`,
  `_155_resultat.txt`.


## Raffinement `triangles` au-delà du seuil (jalon 134, v2.83.0 — étape ② choix C)

- **CE QUI EST LIVRÉ** : `TRI_RAFFIN_SEUIL = 0,30` px et, dans `_triangles`
  APRÈS le contre-test mutuel final, un raffinement conditionnel
  (`_raffiner_centroides`) dont le résultat remplace la matrice et renomme la
  méthode en `triangles+étoiles(n)`. Sous le seuil, matrice rendue **AU BIT**
  telle quelle, méthode `triangles`. `_last_t` est posé APRÈS (matrice FINALE).
- **PIÈGE — UN CHAMP SYNTHÉTIQUE NE PRODUIT PAS DE RÉSIDU ÉLEVÉ** : le plan ⑪
  annonçait « frame décalée de 1,0-1,5 px → raffinée ». MESURÉ FAUX :
  `_triangles` laisse **0,015-0,035 px** sur un champ propre décalé de 0 à
  2 px (il consolide déjà RANSAC + LMEDS sur appariements mutuels). Même en
  poussant (bruit ×8, flou σ 1,2, amp 0,15) on plafonne à **0,24 px** sans que
  les centroïdes puissent faire mieux — les deux estiment la MÊME similitude
  sur les MÊMES points. Les résidus > 0,30 px du run réel viennent de la
  distorsion inter-nuits et d'appariements douteux, pas d'un décalage. Un banc
  qui exigerait « décalage 1,5 px → raffinement » mesurerait une FICTION.
  ⇒ le banc 134 teste le **câblage** (espion : appelé / jamais, matrice prise,
  méthode, `_last_t`) + un cas réel de frame **faible et floue**
  (résidu 0,236 px, 34 appariements) où le raffinement gagne 0,022 px.
- **PIÈGE — « AU BIT » EXIGE UNE GRAINE FIXÉE** : `estimateAffinePartial2D`
  (RANSAC et LMEDS) tire dans le générateur GLOBAL d'OpenCV. Deux appels ne
  rendent pas la même matrice sans `cv2.setRNGSeed(n)` avant chacun : sans
  cela, la comparaison bit-à-bit du volet « résidu faible » ne prouve rien.
- **La méthode devient un marqueur de chemin** : `triangles` = seuil non
  franchi ; `triangles+étoiles(n)` = seuil franchi ET raffinement concluant
  (n = ses appariements). Un échec de raffinement laisse `triangles` — donc la
  trace ⑦ et la ligne d'état disent lequel des deux a servi. ⚠ Un ancien run
  ne se réinterprète pas : après le correctif, `_lance_155.py` mesurerait la
  matrice DÉJÀ raffinée.
- **Coût** : `_raffiner_centroides(..., pos=...)` réutilise les centroïdes que
  `_triangles` vient de calculer ⇒ **0 re-détection** (≈100 ms économisés par
  frame raffinée ; vérifié par espion sur `stars.detecter_positions`, résultat
  IDENTIQUE avec et sans `pos`). Les appelants ORB / étoiles / ORB étoffé sont
  inchangés (détection faite sur place).
- **Garde-fou** : un raffinement ne REFUSE jamais et rend l'entrée INCHANGÉE
  s'il ne fait pas mieux ⇒ les **2 refus G** du run de mesure ne peuvent pas
  changer ; l'appel est de plus entouré d'un `try/except` (une frame DÉJÀ
  validée ne se perd pas sur une erreur d'outil).
- Banc `bancs/_test_triangles_raffin_jalon134.py` (7 volets, 30 vérifications).
  Non-régression : **13, 15, 21, 116, 117, 129b, 131, 132, 133** verts.


## Étape ③ du plan ⑪ — repli `phase` en NARROWBAND : MESURE (18/10/2026)

- **QUESTION** : en HOO/SHO la cascade est TRIANGLES → ÉTOILES → PHASE ; une
  « réussite » de phase (translation SEULE) court-circuite le réessai +180° de
  `compute` — c'est le défaut mesuré au ⑩ en broadband. L'étape ③ demande ce
  que COÛTE de la retirer aussi en narrowband.
- **PROTOCOLE (aucune ligne du dépôt modifiée)** :
  `_mesure_156_phase_narrowband.py` rejoue les brutes RÉELLES, même ordre
  (`MultiFolderCamera` : round-robin des dossiers, chaque dossier trié
  (mtime, nom)), même dark maître 300 s, même référence (1re brute Ha,
  jalon 21), sur DEUX `StarAligner` au code INCHANGÉ : AVANT
  `repli_phase=True`, APRÈS `repli_phase=False`. Preuves hors dépôt :
  `_156_mesure.jsonl`, `_156_synthese.txt`, `_156_controle.json` (+ `_156b_*`
  pour IC 443).
- **RÉSULTAT 1 — COÛT NUL sur un jeu SANS retournement** : **109 frames** réelles,
  **3 jeux multi-nuits** (SHO Rosette 53 · HOO NGC 7000 26 · SHO IC 443 30),
  références à **250 étoiles** : **0 refus AVANT, 0 refus APRÈS**, méthodes
  IDENTIQUES frame par frame (`triangles` 61, `étoiles` 44,
  `triangles+étoiles(n)` 4). La phase n'a JAMAIS été le chemin retenu.
- **RÉSULTAT 2 — DÉCISIF, jeu AVEC retournements (SH2-132, 18/10)** :
  `\\192.168.155.45\…\SV555\SH2-132\240.00` (Ha 55 · OIII 71 · SII 80, 240 s,
  4-5 nuits, dark 240 s), **204 frames réelles** (S2 79 · Ha 54 · O3 71), ancre
  Ha, 250 étoiles : **0 refus dans les deux branches**, **31 retournements**
  (S2 24 · O3 7) tous correctement RETOURNÉS. Mais la phase était le chemin
  FINAL sur **22 frames (Ha 21 · O3 1)** :
  · Ha : matrice de phase à **résidu médian 0,857 px** (max 1,071) — une
    translation seule fausse de **1,1 à 2,3 px**, acceptée comme finale ; la
    branche APRÈS (ORB étoffé après échec du direct) donne **0,065 px**
    (max 0,071) ⇒ 21 frames Ha étaient empilées **nettement moins bien** (la
    couche Ha est le canal VERT du SHO : flou visible) ;
  · O3 : **1 frame empilée À L'ENVERS** — phase Δ=(−0,33 ; +0,53) px, angle 0,
    **0 appariement** (acceptation non vérifiable) contre **|angle| = 173,4°** et
    **4 435 px** d'écart de translation pour la branche APRÈS : c'est LE défaut
    du ⑩, reproduit en narrowband sur une vraie brute.
  ⇒ l'étape ③ n'est pas un compromis « on perd 0 frame » : c'est un **CORRECTIF**
  (0 refus, 21 frames Ha mieux alignées, 1 frame O3 plus jamais à l'envers).
- **VALIDÉ EN RÉEL le 18/10 (v2.84.0, run SHO de Sh2-132 par Alain)** :
  **206 frames** (S2 80 · Ha 55 · O3 71), **0 frame non alignée**, **1 re-stack**,
  107 556 437 pixels rejetés (σ), archive 206, ligne d'état `triangles`
  (Δ +8,9/+11,5 px, θ −0,19°) — **aucune méthode « phase »**. 204 + 1 frame S2
  arrivée avant l'ancre = 206, et le re-stack de session réaligne cette frame.

## Interface 141-B — la composition de la SESSION n'est pas celle du menu (jalon 141, v2.87.0, 18/10/2026)

- **LE DÉFAUT ÉTAIT SILENCIEUX, PAS FAUX.** Session **LRGB+Ha** conduite avec le
  menu « Composition » passé en « RGB » **pendant** l'empilement : le fichier
  était JUSTE (`AVACOMPO = LRGB+Ha, …`, écrit depuis `stacker.composition`) mais
  l'écran affichait « RGB ». La composition réellement empilée ne se lisait donc
  plus nulle part sans ouvrir le FITS. Option **B = PRÉVENIR** (Alain) ;
  A = documenter (l'écran continuerait de mentir) et C = invalider l'empilement
  (perd une session qui est bonne) sont écartées.
- **TROIS NOMS À NE PAS CONFONDRE** : ① `stacker.composition` / `_compo_nom` =
  ce que la SOURCE empile (c'est lui qui pilote la voie A du Ha, la profondeur,
  et `AVACOMPO`) ; ② `_compo_session` = la composition ARMÉE au « ▶ Démarrer »
  (elle survit à une pause « ■ Arrêter » et meurt à la remise à zéro, à la
  fermeture de la source et à la déconnexion) ; ③ `var_compo` = ce que le MENU
  affiche. Le jalon ne compare que ② et ③ ; il ne touche NI ① NI l'empilement.
- **OÙ LE DIRE** : bandeau `lbl_compo_session` du panneau Composition (orange
  `#c98a00`, `wraplength=310`), **vide** quand tout concorde, donc invisible
  dans le cas normal ; PLUS **une** boîte (`_avertir`) par couple
  (session, affichée) au moment où l'écart naît — `_compo_alerte` empêche la
  boîte à chaque frappe dans les rôles, et `_armer_compo_session()` remet ce
  garde à zéro. Le bandeau seul resterait manquable (section pliable fermée) ;
  la boîte seule serait oubliable une fois fermée : les deux.
- **POINTS D'ACCROCHAGE** : `_on_compo` et `_on_compo_roles` (naissance de
  l'écart), `_start` → `_armer_compo_session()` (APRÈS `_reinit_etat_session` et
  après la pose de `_compo_nom`, sinon l'armement est effacé),
  `_reinit_etat_session`, `_refermer_source_fichiers` et `_deconnecter_camera`
  (effacement + rafraîchissement du bandeau). `_maj_compo_info()` termine
  TOUJOURS par `_maj_compo_session()` — y compris sur son retour anticipé
  (`spec is None`), sinon le bandeau resterait figé sur un texte périmé.
- **PIÈGE DE MESURE — LES NOMS SE CONTIENNENT** : `"RGB+Ha"` est une
  SOUS-CHAÎNE de `"LRGB+Ha"` ⇒ jamais `startswith`/`in` pour prouver quelle
  composition est écrite. Le banc lit `ent.split(",")[0].strip() == "LRGB+Ha"`.
  Autre piège du même genre : au démarrage le menu vaut « HOO » ; armer une
  session « LRGB+Ha » sans poser le menu crée un écart LÉGITIME — le banc pose
  donc le menu avant d'armer.
- Banc `bancs/_test_compo_session_jalon141.py` (8 volets, App réelle, Tk,
  `App._avertir` espionné au niveau CLASSE — une boîte modale bloquerait le
  banc) : pas de session → rien ; écart par le menu → bandeau + une boîte ;
  même écart rejoué → pas de seconde boîte ; autre écart → nouvelle boîte ;
  retour à la composition de la session → bandeau vidé ; écart né par les
  rôles ; `AVACOMPO` dit toujours la SESSION ; nouveau « ▶ Démarrer » →
  bandeau vidé + alerte réarmée ; déconnexion → plus d'écart. Non-régression
  19 (UI + worker compo) / 61 / 117d / 129 / 136 / 137 et garde-fou verts.
- **HORS PÉRIMÈTRE, ASSUMÉ** : la teinte des COINS (±15-20 %) et le mode MANUEL
  restent comme avant ; la composition d'un fichier déjà écrit ne se corrige
  pas — c'est `AVACOMPO` qui fait foi.

## Fusion du Ha au rouge (jalon J2, v2.88.0, 18/10/2026)

- **LE PROBLÈME** : dans « RGB+Ha » et « LRGB+Ha » le rôle Ha n'alimente AUCUN
  canal (`canaux_rgb` ne le cite pas). Depuis le 129 il s'empile et s'aligne
  (voie A du 129b) mais le composite l'IGNORAIT : `Ha: N` s'affichait dans
  l'état par rôle, l'image ne changeait pas d'un pixel.
- **LA FORMULE (mode `ajout_rouge`, défaut figé du 15/10)** :
  `R' = R + poids × signal`, appliquée dans `composer()` APRÈS le combine L,
  dans l'espace NORMALISÉ des rôles, avec
  `signal = [ (Ha − fond(Ha)) − continuum ]` ÉCRÊTÉ dans [0 ; 1].
  `poids` = 1,0 par défaut, borné [0 ; 10]. G et B ne sont JAMAIS touchés.
- **LE CONTINUUM EST DANS LE J2 (demande d'Alain du 18/10)** : un filtre Ha de
  7 nm ne laisse pas passer QUE la raie, il porte aussi le continuum de l'objet
  et du ciel ; l'ajouter tel quel ajoute de la lumière blanche — et c'est à ce
  mélange qu'on attribue à tort des « défauts du Ha ». Les cinq étapes :
  ① `continuum = Q × (BW_Ha / BW_RGB) × (R − fond(R)) / échelle(Ha)` ;
  ② la référence est la couche BROADBAND **R** (JAMAIS L) ;
  ③ `BW_Ha` = 7 nm, `BW_RGB` = 100 nm (constantes `BW_HA_NM` / `BW_RGB_NM`) ;
  ④ `Q` (0,10–2,00, défaut **0,80**) absorbe ce que le rapport de bandes ne dit
  pas (transmission, temps de pose, optique) — c'est le réglage À L'ŒIL ;
  ⑤ le signal est ÉCRÊTÉ à [0 ; 1] (aucun rouge négatif, pas de rouge > 1).
  **L'échelle(Ha)** est le dénominateur qui a normalisé la couche Ha : c'est
  elle qui ramène le continuum brut de R dans l'espace normalisé du Ha, quel
  que soit le mode de normalisation (percentiles par rôle, échelle commune, ou
  canaux déjà normalisés → 1,0).
  · Le continuum est **ACTIF PAR DÉFAUT** et se COUPE d'une case : c'est
    précisément ce qui permet de juger AVEC et SANS — **ne jamais conclure à un
    défaut du Ha sans avoir regardé le rendu avec le continuum**.
  · **Case et Q DÉSACTIVÉS quand aucun dossier R n'est renseigné** (il n'y a
    rien pour estimer le continuum) ; `_lire_fusion_ha()` force alors
    `continuum = False`, et la fiche ne le déclare actif que si la couche R a
    des frames.
  · Méthode **bandes passantes** au J2 ; les deux autres du plan (médiane,
    étoiles 5σ) restent au J4 — `METHODES_CONTINUUM_HA` les accueillera sans
    changer l'API.
- **POURQUOI LE Ha EST RECENTRÉ SUR SON FOND (médiane d'un sous-échantillon
  512×512)** : avec l'option « normalisation commune des canaux », AUCUN point
  noir n'est soustrait et le fond du Ha vaut alors ~1 (son niveau physique
  divisé par l'amplitude du vert) — l'ajouter tel quel inonderait le rouge.
  MESURÉ au banc : fond du ciel immobile à ±0,001 avec recentrage, +0,30 (tout
  le fond du Ha) sans. C'est aussi le défaut figé du J4 (case cochée).
- **LA FUSION EST ACTIVE PAR DÉFAUT** dès qu'une couche Ha a des frames :
  `CompositeStacker.fusion_ha = None` signifie « défauts figés », PAS
  « désactivé ». Pour revenir EXACTEMENT au composite du J1 : `{"poids": 0.0}`
  (vérifié AU BIT au banc 129). Conséquence assumée : le volet « composite
  identique avec et sans Ha » du banc 129 a été MIS À JOUR volontairement.
- **`fusion_ha_effectif(composition, fusion)` EST LA SOURCE UNIQUE** : elle rend
  None hors RGB+Ha/LRGB+Ha (HOO/SHO ont le Ha dans un canal : ne jamais les
  toucher), complète un dict partiel, borne le poids et retombe sur le défaut
  si la valeur est illisible. `composer()`, la fiche de rendu et les bancs la
  lisent — ne pas recopier la validation ailleurs.
- **PIÈGES DE CÂBLAGE, tous vérifiés par le banc** :
  · le réglage entre dans la CLÉ DE MÉMOÏSATION du `CompositeStacker` (mode,
    poids arrondi, recentrage, continuum, Q arrondi, méthode) — sans quoi
    bouger le poids, Q ou la case resservirait le composite en cache (même
    piège que le lissage du 117d) ;
  · il voyage dans le 9e élément de `disp.vl_compo` (`display.params_fusion_ha`,
    déballage TOLÉRANT : un ancien 9e élément booléen — la neutralisation
    d'avant le 124 — est ignoré) pour que la vue « traitée » recompose à
    l'identique ;
  · le worker resynchronise `stacker.fusion_ha` À CHAQUE TOUR (comme les gains),
    donc le réglage s'applique sans redémarrer la session ;
  · la FICHE ne déclare l'étape « fusion Ha » que si la composition a un Ha
    fusionné ET que la couche Ha a des frames — sinon elle annoncerait un
    ajout qui n'a rien ajouté.
- **INTERFACE** : cadre « Fusion Ha » du panneau Composition, visible SEULEMENT
  si `composition_avec_ha(var_compo)` (le menu, pas la session) ; mode lu dans
  `MODES_FUSION_HA` (cinq valeurs depuis le J3) ; poids 0–10
  pas 0,1 ; case « Soustraire le continuum (référence R) » ; force Q
  0,10–2,00 pas 0,05 ; persistés (`fusion_ha_mode`, `fusion_ha_poids`,
  `fusion_ha_continuum`, `fusion_ha_q`, `fusion_ha_alpha`).
- **VALIDÉ EN RÉEL (Alain, 19/10/2026)** : « avec continuum et réglage de force
  visible ; sans continuum on voit la différence, les rouges s'éteignent un
  peu » — le continuum se voit donc bien, et ne pas le soustraire fabrique
  l'impression d'un défaut du Ha. Sur M33, poids poussé à **1,5** et **Q 0,80**
  retenu : **le poids 1,5 est un réglage PAR CIBLE**, le défaut reste 1,0.
- **DÉFINI POUR LA SUITE, PAS ENCORE UTILISÉ AU J2** : `ALPHA_HA_DEFAUT` 0,5
  (livré au J3) ; `METHODES_CONTINUUM_HA` n'a que `bandes_passantes` (J4 :
  médiane, étoiles 5σ). `RECENTRER_HA_DEFAUT` (True) est DÉJÀ le comportement du
  J2 ; sa case sera exposée au J4.
- Banc `bancs/_test_fusion_ha_jalon2.py` (8 volets) : défauts et bornes (dont Q),
  formule au bit, G/B au bit, continuum exact au bit (`Q × 7/100 / échelle`,
  écrêtage [0 ; 1]), continuum COUPÉ = ajout pur au bit, fond immobile, no-ops
  rendant le MÊME objet, `composer()` (continuum par défaut, sans R, HOO,
  RGB+Ha, Ha absent), clé de mémoïsation (poids, Q, recentrage), App réelle
  (visibilité du cadre, case continuum désactivée sans R, bornes, persistance)
  et fiche de rendu. Non-régression : 19 (×3), 117d, 121, 129 (mis à jour),
  129b, 130, 136, 141, garde-fou vert, pyright 0.

## Fusion du Ha — les cinq modes (jalons J3 et J3bis, v2.90.0, 19/10/2026)

- **CE QUE LE J3 AJOUTE** : le J2 n'avait qu'`ajout_rouge` ; les quatre autres
  modes du plan figé sont livrés avec α (0–1, pas 0,05, défaut 0,5). Le signal
  est COMMUN aux cinq modes :
  `s = (Ha − fond(Ha)) − continuum` (écrêté [0 ; 1] **seulement** si le
  continuum agit — sans lui le J2 reste linéaire, validé en réel).
- **LE POIDS EST UNE FORCE GLOBALE, PAS UN FACTEUR DE CHAQUE FORMULE** :
  `sortie = composite + poids × (opérateur − composite)`. Conséquences :
  · `poids 1` = l'opérateur EXACT du mode ;
  · `poids 0` = le composite du J1 **AU BIT, pour les cinq modes** — la sortie
    d'urgence validée en réel au J2 ne dépend donc pas du mode choisi ;
  · `poids 2` EXTRAPOLE (2 × l'écart du mode), il n'est pas plafonné à 1.
  Ne jamais réécrire une formule en y multipliant le signal par le poids : deux
  modes deviendraient identiques au facteur près. Depuis J3bis, l'interpolation
  porte sur le RÉSULTAT de l'opérateur, déjà revenu dans l'espace du composite —
  pour les QUATRE modes (v2.90.1 incluse).
- **J3bis (v2.90.0) — LES QUATRE MODES VIVENT DANS L'ESPACE DE R** : voir le
  verdict réel plus bas (ils comparaient `R` et `s` d'échelles différentes).
  Repères, mesurés sur le COMPOSITE et le signal (aucun réglage n'y entre, donc
  RIEN de plus dans la clé de mémoïsation) :
  `fond_R` = médiane de `R` sur le fond (`s` ≤ sa médiane) · `A_R` = p99,7(`R`)
  − `fond_R` · `p_s` = p99,7(`s`) ; puis `R̃ = (R − fond_R)/A_R` et `s̃ = s/p_s`
  (« 0 au fond du ciel, ≈ 1 au p99,7 » pour les deux). Retour au composite :
  `R' = max(0, fond_R + A_R·R̃')` puis `sortie_R = R + poids×(R' − R)`.
- **LES CINQ MODES** (V et B **JAMAIS touchés** — les cinq ne travaillent que
  sur le rouge) :
  · `ajout_rouge` (J2, INCHANGÉ AU BIT) : `R' = R + p·s`. Il est purement
    ADDITIF : ne JAMAIS le faire passer par l'espace de R ;
  · `fondu_rouge` : `R̃' = R̃ + α·(s̃ − R̃)` — fondu `R̃(1−α) + s̃·α`, donc
    NEUTRE AU FOND (R̃ ≈ 0 et s̃ ≈ 0) ; α 0 = rouge intact, α 1 = rouge = s̃ ;
  · `ecran_rouge` : `R̃' = R̃ + s̃·max(0, 1 − min(R̃, 1))` — écran
    `1 − (1−R̃)(1−s̃)` : monte sans écraser, et **c'est lui qui BORNE** (R̃ peut
    dépasser 1 aux cœurs et aux étoiles) ;
  · `eclaircir_rouge` : `R̃' = R̃ + max(0, s̃ − R̃)` — `max(R̃, s̃)` : ne fait
    que MONTER, et le poids n'est plus multiplié par zéro ;
  · `ha_luminance` (v2.90.2, décision d'Alain sur aperçus) :
    `R' = R × (1 + poids·s̃·porte)`, `porte = clip((s̃ − 0,05)/0,20 ; 0 ; 1)` —
    le gain multiplicatif porte sur le ROUGE, mais **seulement là où le Ha est
    FRANC** : sous `s̃` = 0,05 le rouge est **inchangé AU BIT** (le bruit du ciel
    reste du bruit), au-delà de 0,25 le gain est plein. V/B jamais touchés.
    Historique : facteur sur les TROIS canaux (v2.90.0) → BLANCHISSAIT ; gain
    sur l'objet au-dessus du fond (v2.90.1) → trop faible à l'écran.
- **PIÈGE — `ha_luminance` n'est PAS « une luminance sur trois canaux »** : la
  version multiplicative sur R+V+B était juste en théorie (rapports préservés)
  mais blanchissait à l'écran : G et B, qui ne portent aucun Ha, étaient
  multipliés dans TOUTE la zone, ciel compris (saturation 0,19 → 0,12). Et
  multiplier le rouge ENTIER sans porte verse du bruit rouge dans le ciel.
  La forme retenue — gain À PORTE sur `s̃` — chiffre le compromis : sous 0,05 le
  rouge est INCHANGÉ AU BIT, la bande diffuse reste à 0 % de pixels touchés, et
  la bande Ha gagne 2 à 5 fois plus qu'un gain limité à l'objet. **Ne pas
  baisser la porte sous 0,05 sans mesurer** : la rampe 0,02-0,12 versait déjà
  +0,041 dans le halo.
- **`fusion_ha_effectif` PORTE α** désormais : le dict complet est
  `{mode, poids, alpha, recentrer, continuum, q, methode_continuum}`, α borné et
  TOUJOURS présent même hors fondu (changer de mode ne perd pas le réglage).
  Cette fonction reste la SOURCE UNIQUE — ne pas revalider α ailleurs.
- **CLÉ DE MÉMOÏSATION** : `(mode, poids arrondi, alpha arrondi, recentrer,
  continuum, Q arrondi, méthode)`. α y est INDISPENSABLE : sans lui, changer α
  resservirait le composite en cache, et le réglage paraîtrait « sans effet »
  (même piège que le poids au J2 et le lissage du 117d).
- **INTERFACE** : champ « Fondu α (mode fondu) » dans le cadre « Fusion Ha »,
  DÉSACTIVÉ hors `fondu_rouge` (`_maj_fusion_ha()`), mais TOUJOURS lu et
  persisté (`fusion_ha_alpha`) ; l'aide en clair nomme les cinq modes. Le
  Spinbox α ne doit pas être activé par la même règle que Q (qui, elle, dépend
  du dossier R).
- **FICHE DE RENDU** : l'étape « fusion Ha » porte `alpha` en plus de mode,
  poids, recentrage, continuum, Q et méthode ; elle reste conditionnée à une
  composition à Ha fusionné ET à une couche Ha non vide.
- Banc `bancs/_test_fusion_ha_jalon3.py` (9 volets depuis J3bis) : cinq modes,
  bornes d'α, chaque formule (espace de R ; `ajout_rouge` restant AU BIT), poids
  0 = même objet et 0,5 = mi-chemin pour les cinq modes, continuum partagé,
  `composer()` (poids 0, formules, HOO intact, mode inconnu), **volet [5b]
  « composite HORS [0 ; 1] » (R ≈ 2,9-5,7)** qui exige : fond immobile (à 1 % de
  `A_R` près), écran et éclaircir qui ne baissent JAMAIS, éclaircir qui AGIT et
  dont le POIDS agit, fondu qui fait MONTER le Ha, luminance : bande diffuse
  INTACTE, V/B **au bit**, gain = 1 + s̃ au cœur et **rouge AU BIT sous la
  porte** ;
  mémoïsation (α, mode), App réelle (α activé seulement en
  fondu, borné, persisté, restauré) et fiche. **Le banc J2 a été mis à jour
  VOLONTAIREMENT** sur trois volets (liste des modes, dict des défauts, dict de
  la fiche) : il vérifiait « un seul mode », vrai au J2.
  Non-régression : J2 (vert **AU BIT**), 129, 130, 136, 137, 141, garde-fou,
  pyright (aucune erreur dans `composition.py`).

- **VERDICT RÉEL DU J3 (Alain, 19/10, M33, SPCC) : À REPRENDRE (J3bis)** — les
  quatre modes ne sont PAS validés :
  · `fondu` : image BLEUIE, Ha invisible en zone rouge, étoiles bleues/vertes,
  zones Ha blanches/bleu très clair ;
  · `ecran` : zones Ha CYAN ;
  · `eclaircir` : quasi normal, Ha à peine rosé, et **le poids est SANS EFFET**
  (identique à 0 et à 3) — le mode est INERTE ;
  · `ha_luminance` : effet visible, zones Ha plus lumineuses mais plus blanches.
  Avec les gains Gaia au lieu de SPCC, le rouge ressort (éclaircir) et le rose
  apparaît (luminance) : **le niveau de R commande tout**.
  **CAUSE MESURÉE (19/10, couches réelles M33 ; outil
  `bancs/_diag_fusion_ha_echelles.py`)** : ce n'est pas « l'absence
  d'appariement en général », c'est un **espace de travail non défini**. Avec la
  **normalisation COMMUNE** (celle de la session de test, lue dans `AVACOMPO`),
  `R` vit entre **2,86 et 5,71** (p50 / p99,7 ; **`R > 1` sur 100 % des pixels**
  — le combine L y multiplie encore par ≈ 2,4) alors que `s` est écrêté dans
  **[0 ; 1]**. Les quatre formules avaient été écrites pour `R ∈ [0 ; 1]` :
  · `ecran` : `1 − R < 0` PARTOUT ⇒ il SOUSTRAIT du rouge (mesuré **−1,51** au
    cœur Ha, sur une base de 4,40) ⇒ zones CYAN ;
  · `eclaircir` : `max(0, s − R) = 0` sur **100 %** des pixels ⇒ strictement
    INERTE, le poids ne multiplie que zéro ⇒ « force sans effet » ;
  · `fondu` : retire `α·R ≈ 1,43` = **la moitié du rouge du FOND** (⇒ bleu) et
    −45 % au cœur Ha (⇒ Ha invisible dans les zones rouges) ;
  · `ha_luminance` : `+0,44` sur R **ET** G **ET** B, or G/B sont ~5× plus
    faibles que R ⇒ les zones blanchissent (mesuré, pas une impression).
  **SANS normalisation commune**, les amplitudes sont en fait APPARIÉES
  (`R/s = 1,06`), `R > 1` sur 0,23 %, `écran` AJOUTE (+0,19) et `eclaircir` agit
  (41 % des pixels Ha) : il ne reste que le NIVEAU (`s` recentré à 0, `R` avec un
  plancher de 0,0171, soit 2,3 % de son amplitude).
  ⇒ **RÈGLE** : un opérateur qui COMPARE `R` et `s` ne doit JAMAIS supposer que
  le composite tient dans [0 ; 1] — ni que `s` et `R` ont le même plancher.
  **J3bis LIVRÉ (v2.90.2)** et **rejoué sur les couches M33 RÉELLES avec le code
  livré** (`C:\Astro\test\M33_Canaux_LRGBHa`, Δ médian du rouge, poids 1) :
  · fond : **−0,000 pour les CINQ modes** (le J3 retirait 1,43) ;
  · `fondu` α 0,5 : Ha large +0,037, cœur +0,020 — le Ha n'est plus retiré ;
  · `ecran` : Ha large +0,22, cœur +0,66, **0 % de pixels en baisse** (J3 : −1,51) ;
  · `eclaircir` : Ha large +0,075, cœur +0,040, **53 %** des pixels du cœur
    montent (J3 : 0 %, strictement inerte) ;
  · `ha_luminance` (v2.90.2, à porte) : bande Ha **+0,037 médian / +0,665 au
    p90** (v2.90.1 : +0,016 / +0,135), cœur +2,77 ; **bande diffuse 0 % touchée**
    et **89,6 % des pixels sont sous la porte → rouge AU BIT** ; V/B au bit ;
  · `ajout_rouge` : fond +0,000, cœur +0,443 — **le J2 n'a pas bougé d'un bit**.
  Le `fondu` baisse encore 38 % des pixels : ceux où le continuum R DÉPASSE le
  Ha (structures larges) — c'est son objet (remplacer), pas le fond.
  **VERDICT RÉEL D'ALAIN (19/10) : J2 et J3 VALIDÉS.** `fondu`, `ecran` et
  `eclaircir` sont OK (« tout est bien mieux voire OK ») ; `ha_luminance`
  réécrite deux fois (v2.90.1 objet, puis **v2.90.2 à porte** sur choix
  d'aperçus) et livrée ainsi.
- **PIÈGE D'INTERFACE (défaut réel du 19/10, corrigé en v2.89.1)** : le champ α
  restait GRISÉ en passant en mode fondu. La Combobox appelle `_on_fusion_ha`,
  qui ne rafraîchissait pas l'état des widgets ; le banc appelait
  `_maj_fusion_ha()` **lui-même** et ne pouvait donc pas voir le défaut. Un banc
  d'interface doit rejouer le **chemin RÉEL** (la commande du widget), pas la
  méthode d'état.

## Continuum du Ha — TROIS méthodes, repli VISIBLE (jalon J4, v2.91.0, 19/10/2026)

- **CE QUE LE J4 AJOUTE** : le J2 n'estimait le continuum que par les BANDES
  PASSANTES (`k = Q × 7/100`, un rapport THÉORIQUE corrigé à la main). Trois
  méthodes estiment désormais le MÊME facteur `k` (fraction de continuum de R
  qui tombe dans la bande du Ha) :
  · `bandes_passantes` : `k = Q × (bw_ha / BW_RGB)` — **la formule du J2**, avec
    `bw_ha` = 7 nm (défaut validé) ou **3 nm** (filtres serrés, courants). Le
    rapport suit donc le filtre RÉEL : 7/100 ou 3/100 ;
  · `mediane` : médiane de `Ha × échelle / R` sur les pixels de continuum FRANC
    (R recentré au-dessus de p70 et sous p99,5 — les cœurs saturés sont
    écartés), avec rejet par dispersion (MAD/médiane ≤ 0,50) ;
  · `etoiles_5sigma` : `stars.detecter_positions(R, 5σ)` puis
    `photometrie.flux_ouverture` sur Ha ET R ; médiane des rapports, rejet à
    2,5 MAD, **au moins 5 étoiles**. Les étoiles sont du continuum PUR : c'est
    la mesure la plus directe (transmission, temps de pose et optique comprises
    — exactement ce que Q compense à la main).
- **LE REPLI EST UNE RÈGLE, PAS UN ACCIDENT** : une mesure qui échoue (champ
  sans continuum franc, moins de 5 étoiles, rapports dispersés, facteur absurde
  > 0,5) retombe sur `bandes_passantes` **avec le Q courant**, et la sortie est
  alors **AU BIT** celle de la méthode choisie explicitement. Le facteur mesuré
  est multiplié par Q (ajustement fin) puis borné à [0 ; 0,5].
- **LE REPLI SE MONTRE SUR LES CASES** (décision d'Alain du 19/10) :
  `fusionner_ha` remplit un dict `info` (`methode_demandee`, `methode_effective`,
  `repli`, `raison`, `facteur`, `facteur_mesure`), `composer()` le remonte et
  `CompositeStacker.info_fusion_ha` l'expose (mémorisé AVEC le composite : un
  cache-hit doit rendre la même info). L'interface (`_tick_corps`) marque la
  case appliquée « ← appliquée » et écrit la raison en orange. **Ne jamais
  recalculer la mesure côté interface** : elle ne lit pas les canaux, et
  `config.json` ne dit que le CHOIX, jamais ce qui a tourné.
- **Q PAR DÉFAUT SELON LA MÉTHODE** (`q_ha_defaut`) : **0,80** en bandes
  passantes (c'est LE réglage, validé en réel) ; **1,00** sur une mesure
  (ajustement fin). Le passage au défaut se fait dans `_on_methode_continuum`
  (le chemin des CASES), jamais dans `_lire_fusion_ha` — sinon une valeur
  persistée serait écrasée à chaque battement d'interface (~20×/s).
- **LA BANDE PASSANTE EST UN RÉGLAGE** : `bw_ha` entre dans le dict de
  `fusion_ha_effectif` (validé par `borne_bw_ha` : 3 ou 7 nm, l'option la plus
  proche, jamais d'exception), dans la **clé de mémoïsation** (sinon 7 → 3 nm
  ne refait rien) et dans la **fiche de rendu** (`bw_ha_nm`). La liste des
  options et les libellés des méthodes vivent dans `composition.py`
  (`BW_HA_NM_OPTIONS`, `METHODES_CONTINUUM_LIBELLES`) : l'interface ne recopie
  ni l'un ni l'autre.
- **POURQUOI LA MÉDIANE PEUT SE TROMPER** (risque ASSUMÉ, à connaître) : sur un
  objet qui REMPLIT le cadre (grande nébuleuse), le « continuum franc » est
  lui-même dominé par la raie → rapports dispersés → repli. Sur M33, le corps de
  la galaxie fournit un continuum propre : la mesure passe, mais la dispersion
  RÉELLE y vaut **0,80** (régions HII) — c'est pour cela que le seuil de la
  médiane est 1,20 et pas 0,50 (cf. « J4.1 » ci-dessous). Les bandes passantes
  restent le DÉFAUT.
- **POURQUOI LES ÉTOILES PEUVENT SE TROMPER** : champ pauvre en étoiles (moins
  de 5 détectées à 5σ) ou étoiles saturées/filées (rejetées par le MAD). Dans
  les deux cas, repli.
- **IMPORT LOCAL de `photometrie`** dans `_facteur_etoiles` : ce module tire les
  catalogues Gaia/Siril ; on ne le paie que si la méthode est choisie (jamais
  d'import au chargement de `composition.py`).
- **PIÈGE DE BANC** : une scène où le Ha n'est PAS `k·(R − fond) + raie` fait
  REJETER la mesure (dispersion) — c'est le garde-fou, pas un bug. Le banc J4
  construit donc `Ha = 0,10 + k·(R − 0,10) + raie` (raie COMPACTE et DÉCALÉE du
  maximum de R, leçon du J3bis) et retrouve k = 0,070 à **+1,7 %** (médiane,
  depuis J4.1) et −1,6 % (étoiles), avec égalité AU BIT en repli.
- Banc `bancs/_test_fusion_ha_jalon4.py` (8 volets, dont **[3bis]**) : trois
  méthodes et défauts, bandes 7 nm AU BIT / 3 nm, mesure médiane et son repli,
  mesure étoiles et son repli, **indépendance de la mesure vis-à-vis de la case
  « recentrer »**, `composer()` + `CompositeStacker` (info, mémoïsation
  méthode/bande), interface (cases exclusives, grisages, Q au défaut,
  persistance/restauration, repli affiché), fiche de rendu. Non-régressions :
  J2, J3, 129, 129b, 130, 136, 137, 141, garde-fou (pyright 0 sur la liste
  blanche).


## Continuum du Ha — la MESURE ne dépend pas de la case « recentrer » (J4.1, v2.91.1, VALIDÉ EN RÉEL le 19/10/2026)

- **VALIDÉ EN RÉEL (19/10, soir)** : après correctif, « la médiane s'applique
  quel que soit l'état de la case recentrer le Ha ». Bancs J4/J2/J3 verts,
  `pyright` 0.

- **DÉFAUT CONSTATÉ EN RÉEL** : `mediane` **REPLIAIT** case cochée
  (« MAD/médiane 3,02 > 0,50 ») et **PASSAIT** décochée (« facteur 0,1511 ») ;
  la case « recentrer » ne changeait rien à l'image, continuum actif ou coupé.
- **CAUSE** : la mesure était faite sur les cartes **DÉJÀ recentrées par la
  MÉDIANE GLOBALE** (`_mediane`). Sur une cible qui remplit une partie du cadre,
  cette médiane monte avec la nébuleuse : le Ha recentré a des trous négatifs et
  le rapport Ha/R se disperse (3,02). Décochée, le **piédestal de R** diluait la
  dispersion (0,0168 sur les canaux M33) : la mesure passait **par accident**.
  Deux mesures différentes pour un réglage d'AFFICHAGE.
- **CORRECTIF** : `_fond_ciel` (médiane de la **MOITIÉ BASSE**, sous-échantillon
  512×512) retire à CHAQUE carte son propre fond de ciel AVANT
  `_facteur_continuum`, **quel que soit l'état de la case**. Le rapport redevient
  le vrai k : **0,1794** sur les canaux M33, **identique en normalisation par
  canal ET commune**. Le recentrage de SORTIE est **INCHANGÉ** (J2 au bit) : la
  case agit toujours sur l'image, plus sur le facteur.
- **SOUS CONTINUUM, recentrer les DEUX cartes est NEUTRE** :
  `(h−mh) − c·(r−mr) = h − c·r − (mh − c·mr)` — un **offset constant**, absorbé
  par l'écrêtage à 0. La case n'agit donc QUE sur la SORTIE, et seulement
  **continuum COUPÉ** : elle y ajoute `médiane(Ha)` au rouge.
- **MAIS CET OFFSET EST SOUVENT INVISIBLE À L'ÉCRAN** (mesuré sur les canaux
  M33, 19/10, continuum coupé) : **+0,0590** par canal (= 315 % du fond rouge
  0,0187) et **+0,1310** en normalisation commune (= 4,6 % d'un fond à 2,86) —
  **uniforme**, donc l'étirement automatique recale le point noir et l'efface.
  En `ha_luminance` il est **quasi NUL** (+0,0000 médian, +0,0008 au p90 : le
  fond du Ha est sous la porte). Ne pas conclure « réglage mort » d'un écran :
  c'est un réglage de **données LINÉAIRES**, visible dans l'image sauvegardée et
  l'histogramme. Ne pas le retirer pour autant (comportement du J2, au bit).
- **DEUX SEUILS DE DISPERSION** : `DISPERSION_MAX` (**0,50**) pour les ÉTOILES ;
  `DISPERSION_MAX_MEDIANE` (**1,20**) pour la MÉDIANE. MESURÉ : M33 réelle =
  **0,80** (0,50 rejetait donc TOUTE galaxie), champ sans continuum = **1,71**
  (banc J4). 1,20 sépare les deux ; c'est le SEUL curseur si une cible réelle
  replie encore.
- **PHOTOMÉTRIE DES ÉTOILES** : `photometrie.flux_ouverture` retire DÉJÀ le fond
  local en anneau ; la carte reçue (brute ou recentrée) ne change pas le
  résultat — ne pas ajouter un second retrait.
- **BANC** : volet **[3bis]** de `bancs/_test_fusion_ha_jalon4.py` — même facteur
  coché/décoché, médiane APPLIQUÉE dans les deux cas, et `_fond_ciel` < médiane
  globale sur une nébuleuse couvrant 54 % du cadre. Médiane du banc : k =
  **0,0712** (+1,7 % du vrai 0,070 ; 0,0661 avant le correctif). J2 et J3 verts
  AU BIT.


## Ancre d'alignement : le Ha fusionné ne peut PAS être la référence partagée (J5, v2.92.0, 19/10/2026)

- **RÈGLE** : dans une composition `RGB+Ha` / `LRGB+Ha`, le rôle Ha FUSIONNÉ
  n'est **jamais** la référence d'alignement **partagée**. Il garde son propre
  repère (voie A, jalon 129b) ; l'ancre partagée vient TOUJOURS d'une couche
  LARGE BANDE (L/R/G/B).
- **POURQUOI — PAS « le Ha a peu d'étoiles » (c'est FAUX)** : MESURÉ sur les
  canaux M33 réels (`C:\Astro\test\M33_Canaux_LRGBHa`, `stars.detecter_positions`
  puis `stars.mesurer_seeing`, sans plafond) : **L 5 395 étoiles / FWHM 3,45 px**,
  R 5 061 / 2,65, **Ha 4 391 / 2,46 (la plus FINE)**, G 3 932 / 2,65,
  B 3 594 / 3,03. Le Ha détecte donc PLUS d'étoiles que G et B, et il est la
  couche la plus fine : l'argument « bande étroite = peu d'étoiles » ne tient
  pas. La raison est **ARCHITECTURALE** : en `+Ha` le Ha ne se sert JAMAIS de
  l'aligneur partagé — le choisir comme ancre ne lui apporte **rien**, et impose
  aux couches large bande un repère venu d'une bande de 7 nm (et un
  ré-échantillonnage de L, qui porte le détail).
- **LE SCORE QUI TRANCHAIT N'EST PAS UNE QUALITÉ** : `_score_frame` =
  **nombre d'étoiles**, **plafonné à `SCORE_MAX_ETOILES = 200`**, marge de
  re-ancrage `RESTACK_MARGE = 1,5×`. Il compare des **FLUX**. La FWHM est
  mesurée par frame mais SERT AU REJET seulement (`_filtre_floue`, 2× la médiane
  du RÔLE — une nuit entièrement floue passe donc le filtre). Un vrai score
  qualité (FWHM) est un sujet **SÉPARÉ** : il toucherait mono/RGB/LRGB/HOO/SHO,
  pas seulement le Ha. Ne pas le glisser dans J5.
- **QUATRE chemins posent l'ancre partagée — DEUX étaient ouverts** :
  ① **repli après refus répétés** : déjà fermé par un `if voie_a` EXPLICITE
  (`worker._worker_empiler_frame` : le Ha incrémente `_ha_ref_bad` et repose SON
  repère par `_definir_reference_ha`, jamais `_definir_reference`) ;
  ② **création de l'empilement** : FERMÉE par J5 — une frame Ha ne crée plus
  l'empilement d'un `+Ha`. MIROIR du jalon 21 : HOO/SHO attendent leur 1re Ha,
  un `+Ha` attend sa 1re brute **LARGE BANDE** (« en attente d'une brute large
  bande (référence d'alignement)… »). Les frames Ha arrivées avant sont
  **ARCHIVÉES** (rien n'est perdu) et **REJOUÉES** dans leur propre repère dès la
  1re large bande (`_do_restack_compo` avec ancre forcée) ; un empilement d'une
  AUTRE géométrie est jeté au passage (`self.stacker = None`) ;
  ③ **re-ancrage « meilleure brute »** : FERMÉE par J5 —
  `_meilleure_archive_compo` EXCLUT le rôle Ha fusionné (donc `_veut_restack`
  aussi). En HOO/SHO le Ha EST un canal et reste candidat ;
  ④ **rafraîchissement auto (toutes les N frames) / bouton manuel** : fermé
  **PAR CONSTRUCTION** dès que ② l'est — `_image_reference_et_role_de` prend la
  couche qui alimente le **VERT**, puis l'ordre `G → L → R → B → Ha`, et
  `moyennes()` OMET les rôles vides : le Ha n'est atteint que si TOUTES les
  couches large bande sont vides, impossible si l'empilement ne peut plus naître
  sur une frame Ha.
- **LA PROTECTION EST AUX SITES D'APPEL, PAS DANS L'OBJET** : `StarAligner.
  set_reference(img)` **ne connaît pas le rôle** de l'image qu'on lui donne.
  « Le Ha n'est pas dans l'aligneur partagé » veut dire que ses frames ne
  PASSENT pas par lui (`compute`), pas qu'on ne peut pas lui DONNER une image
  Ha en référence. C'est pourquoi ① et ④ sont verrouillés par des ASSERTIONS du
  banc, pas supposés.
- **BANC** : `bancs/_test_fusion_ha_jalon5.py` (5 volets, 23 vérifications) —
  exclusion (+Ha) / Ha conservé (HOO/SHO/RGB), session `+Ha` avec 1re frame Ha
  (rien n'est créé, message, archive) puis 1re large bande (création, ancre,
  rejeu), assertion ① (refus Ha ×3 → 0 appel à `_definir_reference`, repli Ha
  = 1), assertion ④ (vert vide → L, jamais Ha), non-régression HOO (message
  inchangé, ancre Ha). Non-régressions 19/20/129/129b/J2/J3/J4 vertes, `ruff`
  propre, `pyright` 0.
- **VALIDÉ EN RÉEL le 19/10** : (1) démarrage avec le dossier **Ha en premier**
  → « rejeu des brutes Ha (démarrage) · R 1/1 · Ha 1/1 », ancre **R** ;
  (2) **re-stack manuel** → « L 2/2 · R 3/3 · G 2/2 · B 2/2 · Ha 3/3 :
  12/12 frames (0 vs avant) », **aucune perte**. La ligne persistante du
  re-stack ne nomme pas le rôle d'ancre ; il est sur la ligne d'alignement
  (« réf. = brute X#i ») et dans `_ancre_role`.
- **NON LIVRÉ (assumé)** : le score qualité FWHM (cf. ci-dessus) et la doc
  utilisateur (README § « Fusion du Ha ») — le README documente les modes, le
  continuum et l'ancre ; la fiche de rendu dit déjà méthode/bande/recentrage.




## Base SPCC et demandes de mesure sans frame (Lot 1 P2/P3, v2.93.0, 19/10/2026)

- **La base SPCC la PLUS RICHE gagne** (`catalogues/spcc_db.dossier_base`) :
  `chemin_spcc` explicite s'il contient des profils, sinon comparaison du
  nombre TOTAL de fichiers `.json` entre la copie AVAStack et les emplacements
  de Siril (à égalité, la copie AVAStack — ordre historique). **Ne jamais
  revenir au « premier dossier valide »** : le 19/10, la copie AVAStack avait
  12 `mono_filters` sans `QHYCCD_MiniCam8M_LRGB.json` et MASQUAIT la base Siril
  (13) → filtres MiniCam introuvables, sans aucun message. Le choix et ses
  compteurs sont JOURNALISÉS une fois par décision (`_DERNIER_CHOIX`) : une
  décision automatique doit se voir.
- **La richesse se compte en FICHIERS** (un fichier = un profil ou un JEU de
  profils) : compter les objets exigerait de parser tous les JSON à chaque
  appel de `dossier_base`, or `lister()` l'appelle. `lister(cat, base=…)`
  laisse les appelants multi-catégories (`noms_base`, `base_presente`,
  `_profil`) ne décider qu'UNE fois.
- **Une extraction ne rend jamais la base plus pauvre** (`telechargeur.
  extraire_zip_spcc`) : comparaison par catégorie AVANT de poser quoi que ce
  soit (refus global, base intacte) et fichier existant CONSERVÉ si l'archive
  n'en porte pas plus d'objets (`_nb_objets`).
- **JAMAIS de substitution silencieuse d'un profil** : une valeur absente de la
  base est CONSERVÉE et signalée (journal + ligne rouge sous la case) ; elle
  n'est remplacée que si un défaut PAR CANAL existe (RED/GREEN/BLUE via
  `spcc.defaut_profil`) — et le remplacement est DIT. `liste[0]` n'est plus un
  défaut : la liste est triée par FICHIER, son premier élément est arbitraire
  (c'est ainsi que « Antlia R » est devenu le filtre R d'un jeu MiniCam).
- **Cohérence de MODÈLE** (`App._spcc_verifier_profils`) : si les deux autres
  canaux désignent le même modèle et que le troisième vient d'un autre modèle
  dont le défaut existe dans ce modèle, il est REPOSÉ avec message
  (`Antlia R` → `QHYCCD MiniCam8M Red`). Sans majorité ou sans défaut : on
  avertit seulement. Appelée APRÈS la restauration des profils (jamais au
  milieu : `_on_spcc_type(verifier=False)` pendant la restauration) et après
  une lecture de base.
- **`spcc._profil` en TROIS essais** : exact, puis normalisé (casse, espaces,
  `_`/`-`/`/`), puis sous-chaîne — l'ancien « sous-chaîne seule » faisait
  désigner « Full spectrum (no filter) » par « No filter ». Échec = message
  avec les noms les plus proches (`proches_noms`, difflib).
- **Garde FILTER** (`App._spcc_garde_filtre`, posée par `_spcc_tour`) : le
  mot-clé FILTER de la brute courante est confronté aux MODÈLES des filtres
  choisis (`filtre_compatible`) → avertissement ROUGE, jamais un refus. Un
  FILTER réduit à un rôle (« R », « Ha », « L ») ne dit rien : aucun bruit.
- **Les listes de profils SPCC suivent le TYPE de capteur**
  (`App._appliquer_spcc_base_vue`) : `fr` recevait TOUJOURS `osc_filtres`
  (reliquat OSC) — en mono la valeur affichée (« QHYCCD MiniCam8M Red »)
  n'existait pas dans la liste déroulante, donc introuvable au clic (test réel
  du 19/10). Mono → `capteur`/`filtres` ; OSC → `osc_capteurs`/`osc_filtres`.
- **Une correction APPLIQUÉE ne s'affiche jamais en rouge permanent** : l'avis
  « profil remplacé » est AMBRE et **temporisé** (`_spcc_correction`,
  `SPCC_CORRECTION_MS = 12 s`, `after` annulé à la fermeture) ; il rend ensuite
  la parole à l'état de mesure. Seuls les problèmes ACTUELS (`_spcc_alerte` :
  valeur absente, mauvais canal ; `_spcc_garde` : FILTER) restent en rouge.
  Le journal garde le détail des deux.
- **`_astro_demande`** (`ui/app.py`) : posée par `_on_astro` (cochage,
  changement d'indices, WCS non résolu), par la FIN DE SOURCE (worker) et par
  une remise à zéro. `_servir_demandes_sans_frame` sert **ASTRO → PHOTO →
  SPCC** et repose photo/SPCC après une astro qui VIENT de résoudre. La
  demande est consommée UNE fois : essais, délais et WCS restent seuls juges.
- **Fin de source = TRANSITION, pas état** (`worker._armer_astro_fin_source`) :
  le worker repasse par `lu is None` à chaque tour ; armer à chaque fois
  rejouerait `_astro_tour` en boucle. Jamais d'armement sur une caméra LIVE
  (un `read()` vide y est normal entre deux poses).
- **Échecs PRÉEXISTANTS du banc 77** : « ligne Base SPCC rognée » (1-2 px, la
  longueur du dossier temporaire décide) et « menu écrasé ». Vérifiés sur HEAD
  dans un `git worktree` : ils échouent AUSSI sans nos changements — ne pas
  les imputer à une modification.

## Cadence de re-mesure astro / Gaia / SPCC (P1, v2.94.0, 19/10/2026 — VALIDÉ EN RÉEL)

- **UNE SEULE politique** : `processing/cadence.py` (`CadenceMesure`), une
  instance PAR mesure (`_cadence_astro`, `_cadence_photo`, `_cadence_spcc` sur
  `App`). Règles, dans cet ordre : seuil (`SEUIL_PROFONDEUR = 3`, =
  `ASTRO_MIN_FRAMES`) → **passe finale** si `fin_source` et profondeur
  supérieure à la dernière mesure → **plafond** (`MAX_REMESURES = 6`) →
  **doublement** de la profondeur mesurée → **délai** (`DELAI_MIN_S = 20`).
  La passe finale passe AVANT le plafond et le délai : la source est épuisée,
  il n'y aura plus d'occasion.
- **Ne jamais réintroduire `if self.photometrie.valide: return`** (ni
  `self.spcc.valide`) dans les tours : c'est le défaut P1 lui-même — la mesure
  faite à 3 frames restait figée pour toute la session.
- **La profondeur de DÉCISION est `_profondeur_spcc`** (bandes réellement
  mesurées : min des rôles R/G/B en composition, Ha fusionné exclu), alors que
  le SEUIL d'entrée reste `_profondeur_astro` (comme avant). En multi-dossier,
  cela veut dire « une frame de plus dans CHAQUE bande ».
- **`_photo_essais` / `_spcc_essais` ne comptent QUE les échecs** : le quota
  `MAX_ESSAIS` et le délai de réessai protègent des échecs ; les succès ne les
  consomment pas (sinon 3-4 re-mesures épuisaient le quota). Le délai des échecs
  reste `DELAI_ESSAI_S` de `photometrie`/`spcc`, distinct du délai de cadence.
- **Passe finale sans frame** : `_armer_astro_fin_source` arme AUSSI
  `_photo_demande` / `_spcc_demande` (une fois, sur la TRANSITION
  `_source_epuisee`), servies par `_servir_demandes_sans_frame`. Un armement de
  trop ne coûte rien (le tour revérifie la règle) ; un armement manquant perd la
  mesure.
- **L'astrométrie n'a pas de re-mesure** : le WCS est résolu UNE fois puis
  PROPAGÉ (jalon 56). Sa cadence est celle des ESSAIS
  (`SuiviAstrometrie.peut_essayer` : doublé + backoff + plafond), inchangée ;
  `_astro_tour` ne fait que consigner la profondeur du WCS pour l'état.
- **Remises à zéro** : session neuve (worker `_worker_reinitialiser`, reset UI),
  case recochée (`_on_photo`, `_on_spcc`), changement d'indices astro — sinon
  un plafond ou un délai hérité refuserait une demande explicite de
  l'utilisateur.
- **État affiché** : `_maj_photo_etat` / `_maj_spcc_etat` ajoutent
  `suffixe_etat(cadence, profondeur courante)` (« prochaine mesure à N frames »,
  « re-mesure due à N frames (délai en cours) »). `_maj_astro_etat` ajoute
  « mesure faite sur N frames » — jamais d'échéance pour un WCS propagé.
- **COÛT MESURÉ avant de coder** (`bancs/_mesure_p1_cadence.py`, 89 brutes
  réelles vdB 126 180 s OSC, empilement aligné, paliers 3/6/12/24/48) :
  astro **3,11 s** au premier essai puis **0** ; gains Gaia 0,44 → **0,91 s** ;
  SPCC 0,74 → **1,01 s**. Les DEUX mesures sur les cinq paliers = **6,87 s**
  pour **65 s** d'empilement. **Conclusion durable : le coût de la cadence est
  négligeable devant l'acquisition ; ne pas allonger le délai de 20 s « pour
  économiser »** — c'est l'inverse qui coûtait (mesures faites trop tôt).
- **Bancs** : `bancs/_test_p1_cadence.py` (29 vérifications, espion sur
  `mesurer`, aucune mesure réelle : décision 1→24 frames, quota d'échecs,
  profondeur par rôle, passe finale une seule fois, WCS jamais re-solu) et
  `bancs/_mesure_p1_cadence.py --autotest` (mécanique du banc de mesure).

## Aides contextuelles de la colonne — infobulles « ⓘ » (P4, v2.95.0, 19/10/2026 — VALIDÉ EN RÉEL)

- **LE POINT DE PASSAGE EST UNIQUE** : toute explication posée dans la colonne
  gauche passe par `App._aide(parent, texte, ligne=…, padx=…, pady=…)`
  (`avastack/ui/bulles.py`, mixin `Aides`). N'écrire JAMAIS un
  `ttk.Label(..., foreground="#888888", wraplength=…)` d'aide à la main : il
  échapperait à l'option « Aides en texte » et à la mesure.
- **DEUX WIDGETS PAR AIDE**, créés ensemble : l'ÉTIQUETTE grise (ancien
  affichage) et le « ⓘ » avec sa `Bulle`. `_placer_aide` en pose UN seul ;
  `_maj_aides()` bascule TOUTES les aides à chaud (aucune reconstruction).
- **OPTION `aides_texte`** (bool, **défaut NON** = bulles), case « Aides en
  texte dans la colonne » dans le panneau « Fichiers de travail et journal »
  (elle-même une ligne DÉDIÉE : la ligne des boutons est pleine, leçon du
  jalon 72). Persistée DEUX fois : à la bascule (`_on_aides_texte`) et à la
  fermeture (`_sauver_config_app`, booléen EXPLICITE).
- **RÈGLE DE PLACEMENT** : quand la ligne du réglage existe, passer `ligne=…`
  → le « ⓘ » s'y pose à droite (`side="right"`), COÛT ZÉRO. La ligne ne doit
  contenir AUCUN widget `expand=True` (sinon `pack` abandonne le « ⓘ »,
  exactement le défaut du bouton ⓘ du re-stack). Sans `ligne`, le « ⓘ » a une
  ligne courte — déjà 2 à 8 lignes de gagnées.
- **MESURÉ** (`bancs/_mesure_p4_aides.py`, VRAIE interface, sections ouvertes
  par le banc) : 13 aides, **1 267 px = 84,5 lignes = 23,5 % de la colonne**
  avant ; **702 px repris** après (46,8 lignes, 13 % de la colonne, 5 405 →
  4 703 px) ; les ⓘ coûtent 247 px. Le JSON `bancs/_mesure_p4_aides.json`
  conserve les deux modes (`texte`, `bulles`) et affiche le GAIN.
- **CE QUI N'EST PAS UNE AIDE** : les lignes d'ÉTAT (`self.lbl_*` — grises,
  souvent longues : « Photométrie :… », « mesure en cours… ») portent une
  information VIVANTE, jamais une explication. Un banc les reconnaît en
  remontant `dir(ui)` sur les attributs `lbl_*`.
- **PIÈGES DE BANC** : `winfo_ismapped()` est TROMPEUR dans la colonne
  DÉFILANTE (tout ce qui est sous le pli est « non mappé » sans être écrasé) →
  vérifier `winfo_manager() == "pack"` ET `winfo_width() > 1`, en ignorant les
  aides dont un cadre parent est fermé (Fusion Ha hors composition Ha,
  VeraLux en STF). Échap est une TOUCHE : `event_generate("<Escape>")` ne
  l'atteint que si le widget a le FOCUS (`focus_force()`), sinon le test passe
  ou échoue pour la mauvaise raison.
- **Banc** : `bancs/_test_p4_aides.py` — 34 vérifications (paresse de la
  bulle, délai 400 ms, unicité, sortie/clic/Échap, destruction, 13 aides,
  aucun texte gris orphelin, bascule aller-retour avec hauteur EXACTEMENT
  retrouvée, aucun ⓘ écrasé). `ui/bulles.py` est dans la liste blanche typée
  du garde-fou.

## Source « Stacks (fichiers FITS) » — P6, v2.96.1, 20/10/2026 (corrigé et VALIDÉ EN RÉEL)

- **CE QUE C'EST** : une source d'empilements DÉJÀ FAITS, choisis **FICHIER par
  FICHIER** (pas un dossier) — un FITS par filtre voulu, où qu'il soit (Siril,
  PixInsight, ASTAP, AVAStack…). But : tester tout l'aval (astrométrie, Gaia,
  SPCC, fusion Ha, sauvegardes) **sans réempiler les brutes**.
- **LE RÔLE EST CELUI INDIQUÉ, JAMAIS DEVINÉ** (contrat, pas une préférence) :
  `canal_<rôle>.fit` n'est qu'un nom que NOTRE sauvegarde par canal donne ;
  `FILTER` ne prouve rien (un stack peut être un composite) et `AVAFRAME` n'est
  **jamais lue**. Un `FILTER` qui contredit le rôle est un AVERTISSEMENT affiché
  dans le panneau, le choix de l'utilisateur fait foi.
- **AUCUNE PROFONDEUR INVENTÉE** : les messages des mesures disent
  « empilement fourni (profondeur non vérifiée) » (`App._detail_profondeur`) et
  l'échéance en « frames » des lignes d'état est supprimée
  (`App._suffixe_cadence`). Ne jamais réintroduire `AVAFRAME` dans un message.
- **SEUIL DE PROFONDEUR = 1** (`App._seuil_profondeur`, SEULE source du seuil
  pour astro / Gaia / SPCC) : un empilement fourni est déjà profond, mais
  `stacker.n` ne vaut qu'**1 par rôle** ; avec `ASTRO_MIN_FRAMES` (3) toutes les
  mesures seraient bloquées. Les trois cadences de re-mesure reçoivent aussi
  `seuil = 1` à chaque démarrage de session.
- **LA CALIBRATION EST COURT-CIRCUITÉE** dans la boucle du worker
  (`if not self._source_stacks(): frame = self.calib.apply(...)`) : un empilement
  n'a plus de signal brut à corriger. Vérifié par un dark à 2,0 qui, s'il était
  appliqué, ramènerait tout à zéro (banc).
- **LECTURE UNE FOIS PAR SESSION**, puis `read()` → `None` : la source est
  FINIE (`_source_epuisee`), ce qui arme UNE fois les trois mesures à la fin de
  source. `relire()` remet le curseur au début — sans lui, « ▶ Démarrer » après
  « ■ Arrêter » repartait d'un empilement **VIDE** (défaut trouvé en écrivant le
  banc, pas en réel).
- **MESURER AVANT DE MESURER LES MESURES** : rien n'est tenté tant que TOUS les
  fichiers ne sont pas lus (`_worker_mesures` rend la main) — au premier fichier
  le composite n'a qu'un rôle, et le seuil valant 1 aucune « profondeur qui
  double » ne viendrait rattraper la mesure fausse.
- **LINÉARITÉ — refus sur PREUVE, avertissement sur MESURE.** Refus au démarrage
  SEULEMENT si notre en-tête `AVAVUE` dit « ETIRE » (motif `\bETIRE\b` : le
  « avant ETIREMENT » des sorties linéaires ne doit PAS déclencher le refus).
  Un fichier tiers est ACCEPTÉ et un avertissement MESURÉ (fond médian, part de
  pixels à 1,00) part au journal — jamais un refus sur une supposition.
- **`App._source_fichiers()` ≠ `App._cadence_dossier()`** : la première dit
  « source FINIE et pas de lecture en pause » (dossier, composition, stacks) ;
  la seconde ne concerne que la CADENCE d'empilement (dossier, composition).
  Les trois stacks ne sont pas cadencés (fichiers fournis) et leur `scanner()`
  est un no-op.
- **LES RÉGLAGES DU COMPOSITE HABITENT LE PANNEAU « COMPOSITION »** : gains
  R/G/B, normalisation commune, lissage du combine LRGB **et le cadre « Fusion
  Ha »** sont des ENFANTS de `frm_compo` (`panels/compo.py`). Toute source qui
  doit les offrir (aujourd'hui « Stacks (fichiers FITS) ») doit donc afficher
  `_lf_composition` dans `_maj_visibilite_cadres` — masquer la composition les
  masque TOUS. Constat réel du 19/10 : avec la source Stacks, la fusion Ha
  tournait avec ses DÉFAUTS (`ajout_rouge`, poids 1,0) sans aucun réglage
  accessible. **CORRIGÉ (v2.96.1)** : `visibles = [_lf_stacks, _lf_composition]`
  pour `est_stacks`, empilés dans cet ordre (FICHIERS puis réglages).
- **CE QUI N'A AUCUN SENS SANS DOSSIER EST VERROUILLÉ, PAS MASQUÉ**
  (`App._maj_compo_verrouillage`, appelée en fin de `_maj_visibilite_cadres`) :
  menu de composition, lignes rôle→**DOSSIER**, `…` et « Détecter les filtres »
  passent en `disabled` ; les réglages du COMPOSITE restent ACTIFS. Rien n'est
  détruit : tout reprend son état (`readonly`/`normal`) au retour d'une source à
  dossiers. `ui/panels/compo.py` stocke pour cela `cb_compo`, `cb_compo_roles`,
  `ent_compo_dossiers`, `btn_compo_dossiers` et `btn_detecter_filtres` en
  attributs.
- **LA COMPOSITION AFFICHÉE SUIT LA SOURCE** (`App._maj_compo_depuis_stacks`) :
  avec des FICHIERS elle se DÉDUIT des rôles fournis (rôle **et** fichier),
  ≥ 2 fichiers (un seul = empilement direct « Mono », le cadre « Fusion Ha » est
  alors masqué) ; appelée au changement de rôle, de fichier (y compris un chemin
  TAPÉ via `<Return>` / `<FocusOut>`), au choix de source, et par
  `_on_compo_roles` — qui, sous cette source, ne réécrit plus la composition
  depuis les lignes dossier (sinon bandeau 141-B menteur : `var_compo` ≠
  `_compo_session`).
- **PRÉSENCE D'UN RÔLE ≠ PRÉSENCE D'UN DOSSIER** : `_dossier_role_compo(role)`
  ne lit QUE les lignes dossier de la composition et rend `""` quand les rôles
  viennent de FICHIERS. Le test « la couche R existe-t-elle ? » (continuum du
  Ha, case et méthodes) doit passer par `App._role_fourni(role)` : fichiers pour
  Stacks, dossiers sinon. Utilisé par `_maj_fusion_ha` (état des widgets) **et**
  `_lire_fusion_ha` (`continuum = case and _role_fourni("R")`). Sinon le
  continuum est **forcé à l'arrêt** alors que la couche R est fournie (défaut
  du test réel du 19/10, corrigé en v2.96.1).
- **PERSISTANCE SANS SONDE DISQUE** : `stacks_role_i` / `stacks_fichier_i` sont
  relus au démarrage, mais la ligne d'aide est reconstruite avec
  `verifier_fichiers=False` — aucune lecture `isfile`/FITS pendant
  `_restaurer_config` (un montage réseau injoignable ne doit pas retarder
  l'ouverture, leçon v2.38.11).
- **Banc** : `bancs/_test_lot5_p6_stacks.py` (**59** vérifications : caméra,
  linéarité, composition, worker RÉEL avec calibration ignorée, panneau,
  validation, persistance, **et section [6] « piste A »** — composition visible
  et déduite des fichiers, cadre « Fusion Ha » packé, continuum ACTIF avec la
  couche R, verrouillage des lignes DOSSIER, tout rendu au retour d'une source à
  dossiers ; les 5 vrais `canal_*.fit` de `C:\Astro\test\M33_Canaux_LRGBHa` sont
  utilisés quand ils existent, sinon des FITS synthétiques). Modules NEUFS typés :
  `avastack/cameras/stacks.py` et `avastack/ui/panels/stacks.py` (liste blanche
  du garde-fou).
- **P4 : 14 aides désormais** (13 + celle du panneau Stacks) — `_test_p4_aides`
  a été mis à jour avec ce chiffre ; toute nouvelle aide doit y être ajoutée.


## Halo d'étoile coloré — cause, correctif et résidu (jalon 136, v2.85.0, 18/10/2026)


- **CE QUE LA PREMIÈRE FICHE DISAIT ÉTAIT INCOMPLET.** La note du 18/10 parlait
  d'un « clip PAR CANAL après étirement » avec R +41 % / G +19 % / B +23 %. La
  MESURE refaite sur le fichier LINÉAIRE livré (`M 33 2.83.0 lineaire.fits`,
  1948×3725) donne la vraie chaîne causale, et elle commence AVANT l'étirement.
- **CAUSE 1 — LE CIEL N'EST PAS AU MÊME NIVEAU DANS LES TROIS CANAUX.**
  `couleurs.niveaux_ciel_canaux` : **R 0,02657 · G 0,03089 · B 0,03878** (médiane
  de la moitié sombre), soit **R −14,0 % / B +25,6 %** ; les **quatre coins** et
  les **quatre milieux de bord** donnent R −12,7…−14,2 % et B +26,4…+27,2 % —
  donc c'est du **CIEL**, pas la galaxie, et l'écart est **MULTIPLICATIF** (même
  rapport partout) : c'est l'affaire de **GAINS**, pas d'offsets. (Vérifié : un
  piédestal par OFFSETS, même sans garde, laisse R/G ≈ 0,73 dans les coins — il
  n'aligne que le point où l'estimateur a mesuré, pas le reste du cadre.)
- **CAUSE 2 — LE POINT NOIR COMMUN ÉCRÊTE LE CANAL LE PLUS FAIBLE.** Le STF
  calcule UN `lo` sur la luminance (`med − 2,8 σ`) : ici **lo = 0,03108**, donc
  AU-DESSUS du ciel du R (0,02657). **MESURÉ sur le rendu par défaut du fichier
  livré : 97,34 % des pixels ont R = 0** (49,08 % pour G, 0 % pour B), le ciel
  s'affiche **R 0,00 / G 0,07 / B 0,71** (bleu vif) et, à **r = 14 px** d'une
  étoile brillante (6 étoiles, médiane), **R/G 0,11 et B/G 2,11 contre 0,88 et
  1,30 dans le fond local (r = 26)** — c'est ça, le halo coloré : la couronne est
  neutre dans le linéaire, mais seul le R y est encore écrêté.
- **CAUSE 3 — LA PENTE DE LA MTF AMPLIFIE TOUT LE RESTE.** À hauteur de ciel, la
  dérivée de la MTF vaut **≈ 18** (m = 0,0384) : un écart résiduel de 1 % devient
  18 %. Mesure sur le fichier « linéaire traité » (ciel neutre EN MOYENNE, mais
  ±2 % d'un bout à l'autre du cadre) : rendu **R +39 % / B +19 %** sur un ciel
  neutre. Corollaire : **une correction d'avant-étirement ne peut pas rendre un
  fond parfaitement neutre** ; il ne faut pas promettre l'inverse.
- **CORRECTIF LIVRÉ** (`display.gains_avant_etirement` / `source_etirement`) :
  gains de `couleurs.gains_fond` — la **primitive d'espace LINÉAIRE** du projet,
  celle que VeraLux utilisait déjà avant son étirement — appliqués AVANT la
  courbe, **et les statistiques recalculées sur l'image neutralisée** (sinon le
  point noir reste calé sur un ciel moyen que deux canaux sur trois ne touchent
  jamais). `GARDE_NEUTRE_STF = 0,35` : la garde par défaut (10 %) est calibrée
  pour un ciel déjà presque neutre (M31 : 3,6 %) et NE SUFFIT PAS ici (+16,3 % /
  −20,4 %) ; 0,35 couvre le cas et borne le pire cas. Ciel neutre ⇒ **aucun gain
  ⇒ identité AU BIT** (c'est ce qui rend le correctif sans risque).
- **MESURÉ APRÈS, MÊME FICHIER** : gains **R ×1,1626 / B ×0,7964** ; pixels à 0
  **R 1,05 %** (au lieu de 97,34 %), G 0,16 %, B 4,56 % ; ciel du rendu **R
  +19,4 % / B +16,7 %** (contre −100 % / +888 %) ; couronne à r = 14 **R +5,0 % /
  B −6,6 %** (contre −100 % / −81 %). Sur le fichier « traité » : couronne
  −2,8/−3,6 % → **−0,2/−0,4 %**, fond +39/+19 % → **+17,6/+2,9 %**.
- **RÉSIDU ASSUMÉ** : la teinte de fond de ±20 % (cause 3). Le levier suivant
  serait la **neutralisation APRÈS étirement** (jalon 123,
  `couleurs.neutraliser_apres_etirement`), aujourd'hui réservée à VeraLux par
  `_neutraliser_fond` — **à trancher par Alain**, pas à ajouter d'office.
- **NE PAS TOUCHER** : mode **manuel** (pas de MTF raide ⇒ pas de halo) et moteur
  **VeraLux** (il applique déjà `piedestal_canaux` + neutralisation) : le banc
  136 vérifie que les deux sont inchangés.
- **COÛT** : estimation **~6 ms** (sous-échantillon 256×256 ; `gains_fond` sur
  l'image entière coûtait 70 ms à l'aperçu et 460 ms en pleine résolution) +
  ~20 ms de multiplication — **uniquement à chaque nouvel empilement**, jamais
  sur un geste de souris (mémo du jalon 79). `process()` à l'aperçu
  1600×904 : 121 ms → 155 ms avec un ciel coloré.
- **MÉTHODE — trois leçons de mesure.**
  1. **Un rendu se mesure avec le VRAI moteur**, pas avec une ré-écriture de sa
     formule : `DisplayProcessor().process(img)` a donné le ciel (0,00 ; 0,07 ;
     0,71) que la diag « à la main » ne montrait pas.
  2. **Le halo se lit PAR RAPPORT au fond local du MÊME rendu** (r = 14 contre
     r = 26-30) et par canal ; un agrégat global est aveugle (écart global ~1 %).
  3. **Le fichier « tel que vu » livré ne reproduisait PAS le défaut** (couronne
     +0,2 %/−0,5 %) : il avait été rendu depuis le « linéaire TRAITÉ », dont le
     ciel est neutre. Le défaut dépend donc de l'image qui entre dans le STF —
     d'où la mesure sur le **linéaire** ET sur le **traité**, les deux rapportés.
- Banc : `bancs/_test_halo_couleur_jalon136.py` (8 volets : identité au bit sur
  ciel neutre, halo divisé par > 3 et sous 10 %, garde bornée, mono, parité
  écran/fichier, mode manuel, idempotence, fond à la cible). Diagnostics hors
  dépôt : `C:\Astro\test\_diag_halo_136{,b,c,d,e,f,g,h,i,j}*.py`.



## Neutralisation APRÈS étirement — désormais pour STF aussi (jalon 137, v2.86.0)

- **CE QUI ÉTAIT FAUX** : la case « Neutraliser la couleur du fond (après
  étirement) », **cochée par défaut**, n'agissait que si le moteur était VeraLux
  (`_veralux_actif()`) — en STF elle était donc VISIBLE et SANS EFFET. C'est le
  défaut du jalon 127 (la chroma inerte en STF), revécu : **une case visible doit
  agir dans le moteur où elle est montrée**, sinon elle ment.
- **PORTÉE** : option cochée **ET moteur AUTOMATIQUE** (`self.auto` ou VeraLux
  actif). Le **mode manuel est exclu, délibérément** : l'utilisateur y règle le
  point noir à la main, souvent AU niveau du fond ⇒ il n'y a plus de « couleur
  du fond » à mesurer, et une correction mesurée sur du noir serait du bruit
  appliqué à toute l'image. Le banc 137 vérifie que le manuel ne bouge pas.
- **LA GARDE DES DEUX CHEMINS DOIT RESTER MIROIR** : `_neutraliser_fond` (écran)
  et `rendu_pleine_resolution` (fichier) portent la MÊME condition. Elles avaient
  divergé une fois (l'écran testait le moteur, le fichier testait `stretch`) :
  c'est la parité au bit du banc 137 qui verrouille l'accord.
- **MESURÉ (scène décisive, hors dépôt `_diag_137_probe.py`)** : ciel décalé
  AU-DELÀ de la garde du 136 (R ×0,80 · B ×0,72) ⇒ écart de couleur du fond
  rendu **0,130 → 0,045** (÷3), gains publiés **[1,0029 · 1,0 · 1,1]** (bornés
  ±10 %). Ciel NEUTRE ⇒ aucun gain, rendu identique AU BIT.
- **MESURÉ SUR LE RUN RÉEL** (correctif 136 compris) — `M 33 2.83.0
  lineaire.fits` : gains **[1,0106 · 1,0 · 0,9535]**, coins (médiane des QUATRE
  coins) **R +13,8 → +15,0 %** et **B +19,7 → +14,1 %**, région brillante
  R/G +1,1 %, B/G −4,6 % ; sur la SEULE tuile du coin haut-gauche :
  R +19,4 → +22,5 %, B +16,7 → +12,7 % ; `lineaire traite.fits` : gains
  [0,9966 · 1,0 · 0,9900], coins +18,6/+13,4 → +18,2/+12,3 %.
  ⚠ **La correction n'est pas « toujours mieux »** : elle fait monter R et
  baisser B parce que l'estimateur (moitié sombre) ne voit pas la même chose que
  les coins — c'est exactement la limite ci-dessous, et la raison pour laquelle
  les gains sont BORNÉS et ANNONCÉS.
- **LIMITE MESURÉE — NE PAS LA VENDRE COMME UN REMÈDE AU DÉGRADÉ** : en STF, la
  neutralisation d'AVANT étirement (136) égalise déjà le ciel **avec le MÊME
  estimateur** (la moitié sombre) ; cet étage ne corrige donc qu'un **résidu**
  de quelques %. La **teinte des COINS** (±15-20 %) n'est PAS une dominante
  globale mais un **DÉGRADÉ** : les coins diffèrent de la moitié sombre de
  **1,3 % en linéaire**, que la **pente de la MTF (×18)** porte à 20 %. Un gain
  global ne peut pas la corriger ; il faudrait un **modèle de fond réel**
  (GraXpert/ABE, déjà disponible dans l'appli) ou un estimateur PAR RÉGION —
  **décision d'Alain**, pas un ajout d'office.
- **NE PAS OUBLIER** : le rendu « tel que vu » et la fiche (`saver`) décrivent le
  même étage (la fiche ne doit plus verrouiller la neutralisation sur `stretch`),
  et les gains sont **annoncés en STF** aussi (« FOND ✓ · fond neutralisé
  (R … / G … / B …) » dans « État des calculs (live) ») — c'est la mesure qu'il
  faut lire, jamais un exemple.
- Banc : `bancs/_test_neutralisation_stf_jalon137.py` (8 volets : la case AGIT,
  gains publiés et bornés, ordre avant la finition, parité écran/fichier au bit,
  ciel neutre → identité au bit, manuel hors périmètre, mono).


## Diagnostic de l'entrée d'astrométrie (18/10/2026) — lire le message AVANT de corriger

- **CAUSE TROUVÉE LE 18/10/2026 — CE N'ÉTAIT NI L'IMAGE NI LE CODE : LES INDICES
  ÉTAIENT CEUX DE LA CIBLE PRÉCÉDENTE (M31) SUR DES BRUTES M33.** Mesure :
  12 brutes M33 LRGB (3/rôle, jeu du 22/09), le VRAI `ui.App`, dump activé ;
  deux runs qui ne diffèrent QUE par les AD/Dec d'astrométrie.
  · indices restaurés par l'interface (config : `astro_ra=10,683333`,
    `astro_dec=+41,268611` = **M31**) → **ÉCHEC** « aucune affinité convaincante
    (5 étoiles) ; RANSAC paires : 4 inliers, **1,615″/px** » — le message exact
    du run d'Alain (3 inliers, 1,603″/px) ;
  · indices de l'EN-TÊTE (`OBJCTRA/OBJCTDEC` = 23,4625 / +30,66 = M33) →
    **OK, 115 appariements, 2,469″/px, rms 0,30 px**.
  Les deux entrées sont **IDENTIQUES AU PIXEL** (r = 1,000000, écart médian 0) :
  la même FITS re-soumise hors appli échoue avec M31 et résout avec M33. Donc
  NI l'empilement, NI `repli_phase`, NI la profondeur ne sont en cause.
- **MÉCANISME (interface)** : `ui.app._effacer_indices_astro()` n'est appelée que
  si `_start()` / « Réinitialiser » voit une source OBSOLÈTE, et
  `_source_fichiers_obsolete()` rend **False quand `camera is None`** — c'est le
  cas à l'ouverture de l'application. Les AD/Dec de la cible PRÉCÉDENTE,
  restaurés de `%APPDATA%\\AVAStack\\config.json`, sont donc **réutilisés
  silencieusement** pour la nouvelle cible ; le champ (2,637°) étant le même
  pour les deux cibles, rien ne le trahit. Le message, lui, ne dit JAMAIS les
  indices utilisés — seul le dump les porte.
- **RÈGLE DE TRI** : devant un échec de solveur, lire **`indices`** dans le dump
  AVANT tout le reste. Une échelle trouvée ~**0,65× la vraie** (ici 1,615 contre
  2,462″/px) sur 3-4 inliers est la signature du fit sur un mauvais endroit du
  ciel ou d'une image normalisée — pas d'une preuve sur le contenu.
- **Piège de méthode** : « mêmes brutes, mêmes nuits, mêmes en-têtes » ne rend
  PAS les indices constants — ils viennent de la SAISIE (persistée), pas des
  fichiers, tant que les champs ne sont pas vides. Vérifier `astro_source`
  (`saisie` vs `en-tête …`) avant de suspecter l'image.

- **GARDE EN PLACE DEPUIS LE JALON 133 (18/10/2026)** — le piège est fermé dans
  le **worker**, jamais dans l'interface : `worker._astro_indices_garde()`,
  appelée par `_astro_tour` juste AVANT la pose des indices. Si les indices
  viennent de la SAISIE (`_astro_source == "saisie"`) et que la brute courante
  porte `OBJCTRA/OBJCTDEC` (repli `RA/DEC`), `astrometrie.separation_deg()`
  compare les deux positions ; au-delà de `GARDE_INDICES_FRACTION × champ
  saisi` (**0,25** : M31 ↔ M33 = **14,78°**, seuil 0,66° sur un champ de
  2,637°) l'**EN-TÊTE est retenu** — coordonnées de la brute, champ de l'en-tête
  s'il est déductible (sinon champ saisi, même optique) — `suivi_astro.indice()`
  est reposé (WCS oublié, essais à zéro), et la ligne d'état + le journal
  DISENT les deux valeurs et laquelle est retenue. Sous le seuil, ou sans
  coordonnées dans l'en-tête (caméra SDK, PNG/TIFF), **rien ne change**.
  · **PIÈGE DE COÛT** : la comparaison est faite **UNE fois par jeu d'indices
    saisi** (`_astro_garde_pour`) — relire un en-tête FITS à CHAQUE frame
    ajouterait un `fits.open` sur le chemin de la boucle d'acquisition.
  · **PIÈGE D'ÉTAT** : les indices saisis ont DÉJÀ été posés par l'interface
    (`_on_astro` → `suivi_astro.indice`), donc `pret` est vrai — l'appel gardé
    par `if not self.suivi_astro.pret` ne reposerait RIEN. La garde doit appeler
    `indice()` elle-même, sinon le solveur cherche encore à l'ancienne position.
  · Le NOM des cibles dans le message vient du catalogue d'objets célèbres
    (`cherche_celebres`, 0,5°) quand il est installé, sinon des coordonnées : le
    message ne dépend JAMAIS d'un catalogue téléchargé (banc hermétique).
  · `_brute_courante()` (même chemin que `_astro_indices_entete` : `last_file`,
    repli `stats()` en composition) est le SEUL lecteur du fichier courant.
  · Banc : `bancs/_test_astro_indices_garde_jalon133.py` (6 volets : décision,
    seuil, sans en-tête, déjà d'en-tête, WCS propagé, champ de l'en-tête).

- **LE MESSAGE D'ÉCHEC MENT SUR DEUX CHIFFRES** : `[image 120 étoiles, catalogue
  400, appariements 0]` — 120 est `MAX_ETOILES_DETECTION`, 400 est `N_CAT_MAX`
  (des **plafonds**), et `n_appariements` n'est renseigné qu'au **succès**
  (`solveur.resoudre` ne l'écrit qu'en l. 857) : « 0 » est la valeur par défaut,
  pas une mesure. Seul chiffre exploitable : le nombre d'**inliers** du meilleur
  essai (échec sous `TRI_INLIERS_MIN = 6`).
- **CE QUI ENTRE DANS LE SOLVEUR** : `worker._image_reference_de` →
  `moyennes(recadre=False)` → **la couche du canal VERT** (G en RGB/LRGB, O3 en
  HOO, Ha en SHO) → repli « premier rôle non vide ». **Cette sélection n'a PAS
  changé** entre la v2.82.0 et la v2.82.2 (le ⑦ ne fait que rendre le rôle) ;
  l'astrométrie ne lit NI `repli_phase` NI la trace.
- **RÈGLE** : avant de toucher au solveur ou aux indices, **comparer l'entrée**.
  Un désaccord « ça marchait, ça ne marche plus » sur les MÊMES brutes ne peut
  venir que du code ; mais l'entrée peut changer par son **CONTENU** (poses et
  refus de l'alignement : une frame retournée correctement laisse des zones non
  couvertes dans la grille NON recadrée, une frame posée par `phase` non).
- **INSTRUMENT** : `AVASTACK_DUMP_ASTRO=<dossier>` (env) → `worker._astro_dump_entree`
  écrit, à CHAQUE tentative, l'image exacte (FITS) + un JSON (`median`, `p1`,
  `p99_7`, **`pixels_nuls_pct`**, `seuil_solveur`, `pixels_au_dessus_pct`,
  profondeurs par rôle, indices) + `_resultat.json` (verdict). **INACTIF par
  défaut** — sans la variable, aucun calcul, aucune écriture (comportement
  identique). Même esprit que `AVASTACK_TRACE_ROLES`.
- **CONTRÔLE DE NON-RÉGRESSION MESURÉ** (jeu M33 LRGB réel, 3 frames/rôle) :
  l'entrée est **identique au chiffre près** avec `repli_phase` True et False, et
  le solve passe dans les deux (118 appariements, 2,466"/px, rms 0,22 px) — sur
  ce jeu aucune frame n'est placée par la phase. Scripts hors dépôt :
  `_diag_astro_152.py` (champ/centre), `_diag_astro_153_entree.py` (entrée
  phase ON/OFF).
- **PIÈGE DE MÉTHODE** : ne pas suspecter le pointage, la profondeur ni le champ
  indicé quand les brutes et les nuits sont les mêmes — ce sont des constantes,
  pas des variables. La question est « quelle image, et quelle différence avec
  avant », pas « pourquoi le solveur se trompe ».

