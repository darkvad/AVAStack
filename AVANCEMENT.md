# AVANCEMENT.md — mémoire de travail à court terme

(Complète `CLAUDE.md`, qui porte les leçons durables. Ici : état courant, décisions,
pièges actifs, prochaine action. Le détail daté vit dans `avastack/__init__.py`
(changelog) et `git log` — pas ici.)

---

## ⚠️ BRANCHE DE DÉVELOPPEMENT ACTIVE — NE PAS SUPPRIMER JUSQU'À DEMANDE EXPLICITE

**Branche : `LRGBHa`** (créée le 15/10/2026 à partir de `master`)

> **RÈGLE FERME — GRAVÉE DANS LE MARBRE** : jusqu'à nouvel ordre explicite,
> **TOUT** développement et **TOUTE** modification de code se font **EXCLUSIVEMENT**
> sur `LRGBHa`. `master` = branche stable, releases uniquement ; merge vers `master`
> seulement sur validation explicite (release).

Versions : `LRGBHa` = **v2.83.0** (⑦ v2.82.1 + ① + **garde 133** en v2.82.2,
`586f860` ; **② choix C** = jalon 134, **VALIDÉ en réel**) · `master` publié =
**v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 18/10/2026 — ① + 133 (v2.82.2) puis ② choix C LIVRÉ (v2.83.0, jalon 134)

### Ce qui est livré
- **v2.82.2, commitée et poussée `586f860`** — **étape ①** (plus de repli `phase`
  en BROADBAND : `PHASE_EN_BROADBAND = False`, `repli_phase_session(narrowband)`,
  verrou dans `_sans_phase` qui exige `avec_phase` **et** `repli_phase` ; ordre
  ORB → triangles INCHANGÉ ; banc neuf 132, 8 volets) et **garde d'interface
  d'astrométrie (jalon 133**, banc neuf 133, 6 volets).
- **v2.83.0 — étape ② choix C (jalon 134)** : `TRI_RAFFIN_SEUIL = 0,30` px et
  raffinement de `_triangles` **SEULEMENT** au-delà ; `_raffiner_centroides`
  reçoit `pos=` (centroïdes déjà en main : **0 re-détection**) ; méthode
  `triangles+étoiles(n)` ; `_last_t` posé avec la matrice FINALE. Banc neuf 134
  (7 volets, 30 vérifications, vert).
- **Verdict ⑩** (rappel) : 11/50 puis 12/49 frames B empilées à l'envers par
  `phase` sur un champ à +177,07° — détail `CLAUDE.md`.

### Garde d'interface d'astrométrie (jalon 133) — LIVRÉE le 18/10
`worker._astro_indices_garde()` (appelée par `_astro_tour`, un seul point) compare
la SAISIE aux `OBJCTRA/OBJCTDEC` de la brute (seuil 0,25 × champ) ; au-delà elle
retient l'en-tête et REPOSE `suivi_astro.indice()`. Détail : `CLAUDE.md` §1300.

### Étape ② du plan ⑪ — choix C, LIVRÉ (v2.83.0) + mesure qui l'a décidé
- **Mesure (run réel LRGB+Ha, instrumenté PASSIVEMENT, 475 lues → 472 empilées,
  1 floue, 2 refus G)** : `triangles` porte **143/472 frames (30,3 %)** — B 16/51 ·
  G 33/61 · Ha 39/40 · L 31/240 · R 24/80. Résidu méd **0,083 px** (p90 0,675,
  max 1,385 ; 87/143 ≤ 0,10). Gain des centroïdes : **méd 0,002 px**, < 0,05 sur
  95/143 (66 %), **7 frames seulement** déplacées de > 1 px (pires 1,385 → 0,651).
  Par rôle : B 0,060→0,060 · G 0,082→0,084 · Ha 0,070→0,069 · **L 0,484→0,467** ·
  R 0,083→0,082. Contrôle positif 200 étoiles : 202 appariements, 0,0438 px à la
  vraie matrice, 1,4904 px pour une erreur connue de 1,5 px, 0,0104 px après
  raffinement. Détail : `CLAUDE.md` § « Étape ② du plan ⑪ ».
- **Livré** : seuil franchi seulement (`TRI_RAFFIN_SEUIL = 0,30` → 43/143
  frames du run), `pos=` pour ne PAS re-détecter les centroïdes, méthode
  `triangles+étoiles(n)`, `_last_t` final, `try/except` (une frame validée ne se
  perd jamais). Un raffinement ne refuse jamais ⇒ les **2 refus G** restent 2.
- **Mesures hors dépôt** : `_espion_155.py`, `_lance_155.py`, `_diag_155{a,b,c,d}*.py`,
  `_attendre_155.py` ; preuves `_155_centroides.jsonl`, `_trace155/155.jsonl`.

### Run de VALIDATION du ② (Alain, 18/10, v2.83.0) — MESURÉ
- **472 frames empilées** (L 240 · R 79 · G 62 · B 51 · Ha 40), **2 non alignées
  (G 1 · R 1)**, 1 floue, 474 en archive. Total des refus **identique** au run de
  mesure (2) ; la composition par rôle glisse d'UNE frame (G 2 → G 1 · R 1)
  parce que `_last_t` et la référence suivent les matrices raffinées.
- **Contrôle sur le fichier livré** (`M 33 2.83.0 lineaire.fits`, 1948×3725) :
  **0,00 %** de pixels à 0 dans les 3 canaux (aucun coin noir ⇒ aucune frame à
  l'envers) ; décalage des étoiles entre canaux **R−V |Δ| méd 0,079 px** (Δx
  −0,004 · Δy −0,009) et **B−V 0,130 px** (−0,037 · −0,085). Run précédent
  (146_144) : 0,087 et 0,155 px ⇒ **aucune régression**.
- ⚠ **Le « tel que vu » se mesure MAL** (0,44 et 1,07 px) : saturation à 1,0 et
  point noir par canal (0,46 % / 1,65 % de pixels à 0) biaisent les centroïdes.
  La géométrie se lit sur le **LINÉAIRE**.
- **La trace ⑦ n'était PAS activée** : les 5 lignes d'état copiées ne montrent
  pas `triangles+étoiles(n)`, mais elles ne couvrent que 5 frames sur 472 — on ne
  peut PAS compter la branche ②. Pour la compter : relancer avec
  `AVASTACK_TRACE_ROLES=<dossier>` (champ `align_methode` par frame).
- **SPCC (observation d'Alain)** : R ×0,7837 / G 1,0000 / B ×0,6299, pentes R/G
  0,942 (σ 0,015) et B/G **1,626** (σ 0,031) sur 1013 étoiles ; l'alerte « hors
  [0,5 ; 1,5] » est donc PAR CONSTRUCTION, et le rendu est jugé plus naturel
  qu'avec les gains Gaia ⇒ à instruire, pas à corriger à l'aveugle.

### État actuel
- **Code** : **v2.83.0** (② choix C, jalon 134) — commitée et poussée ; banc 134
  vert et **run réel d'Alain VALIDÉ** (aucune régression mesurée).
- **RUN RÉEL LRGB (Alain, 18/10)** : plus aucune tache bleue NI rouge ⇒ `phase`
  en broadband était la seule cause. Astrométrie réussie (garde 133).
- **Reste à faire** : **③** (SHO/HOO sans `phase`) — mesure du coût avant décision.
- **Combine** innocenté trois fois (140/142/143) : `_ratio_combine` intact.

### Fichiers modifiés dans cette phase (v2.83.0)
- `avastack/processing/alignment.py` (`TRI_RAFFIN_SEUIL`, branchement dans
  `_triangles`, `pos=None`), `avastack/__init__.py` (**v2.83.0** + changelog),
  `bancs/_test_triangles_raffin_jalon134.py` (banc NEUF, 7 volets, 30 vérifs),
  `CLAUDE.md` et `AVANCEMENT.md`. Rappel v2.82.2 : voir `586f860`.

### Mesures du chantier (détail dans `CLAUDE.md` et le changelog v2.82.2)
140 RGB propre · 142 LRGB R +103,9 % / B +132,1 % · 143 B +80,7 % · 144 B +34,6 % ·
poids 0,857 et σ ×4,38 aux 243 taches — **ne pas rejouer**.

### Astrométrie — RÉSOLUE le 18/10 : les AD/Dec étaient celles de M31
Les champs gardaient **M31** (10,683333 / +41,268611) sur des brutes **M33** ;
avec les bons indices le solve résout (115 appariements, 2,469″/px, rms 0,30 px).
Leçon durable et preuves : `CLAUDE.md` § « Diagnostic de l'entrée d'astrométrie ».

### Décisions prises
- **Combine hors de cause** (140/142/143) ⇒ on ne touche pas à `_ratio_combine`.
- **Cause UNIQUE mesurée** : `phase` en broadband. Le run réel de ① efface les
  **deux** couleurs (bleu ET rouge) ⇒ l'hypothèse « rouge = contenu des 240
  brutes L » est **ABANDONNÉE** : ne pas la rouvrir sans un NOUVEAU symptôme.
- **Étape ① appliquée TELLE QUELLE** : `phase` écartée en broadband, **conservée**
  en HOO/SHO (étape ③) ; les aligneurs du Ha (voie A) ne sont PAS touchés.
- **PAS de case dans l'interface** (décision d'Alain du 18/10/2026) : on teste
  d'abord en mode unique. Une case n'aurait qu'à écrire `aligner.repli_phase`
  (le drapeau est déjà fixé PAR SESSION) si le besoin de jongler apparaît.
- **② = CHOIX C (Alain, 18/10/2026), LIVRÉ et VALIDÉ en v2.83.0** : raffiner
  SEULEMENT si le résidu de `triangles` dépasse `TRI_RAFFIN_SEUIL` (0,30 px →
  43/143 frames ; 0,10 en toucherait 56, 0,50 seulement 13). Gain < 0,05 px sur
  95/143 frames (66 %) ⇒ inutile de toucher une matrice déjà bonne ; là où il sert
  (7 frames > 1 px, pires 1,385 → 0,651) il corrige 12 à 50 % de l'erreur.
- **La composition d'un fichier se lit dans son `AVACOMPO`**, jamais dans l'interface (141).
- **134c invalide** (brute dithérée) ; **135/136/138** annulées. **Interface (141)** :
  (A) documenter, (B) prévenir, (C) invalider — à trancher.

### Problèmes ouverts
- **Résidu systématique de la couche L (0,48 px)** : distorsion inter-nuits
  (palier ~0,8 px du jalon 117) que ni la similitude ni l'affine ne corrige —
  à instruire SÉPARÉMENT (le ② ne le traite pas).
- **VeraLux** : à instruire (ancre calculée puis soustraite par canal) — APRÈS ②/③.

### Prochaines étapes
1. **③** : SHO/HOO sans `phase` — MESURER le coût (refus par rôle) AVANT toute
   décision. Contrôle positif 200 étoiles OBLIGATOIRE à chaque mesure ; si un run
   réel est fait, l'activer avec `AVASTACK_TRACE_ROLES=<dossier>` (on pourra alors
   compter `triangles+étoiles(n)` vs `triangles`, jamais mesuré à ce jour).
2. **SPCC** à instruire (pente B/G 1,626 hors [0,5 ; 1,5]) — APRÈS ③.
3. Interface 141 (A/B/C) et **VeraLux** restent en attente.

### Points d'attention
- **Une brute est DITHÉRÉE** : seul un empilement ALIGNÉ prouve quelque chose.
- **`--dossier` sans `--dark` = run invalide** dès que l'exposition change.
- **Comparer deux BRUTES par corrélation est INVALIDE si le dossier mélange des
  nuits** (B : 14→23/09) ; les `cadre` de deux runs ne se comparent pas non plus.
- `save_canaux_request` : attendre l'écriture des couches avant de quitter
  l'appli ; brutes NINA : `BZERO/BSCALE` ⇒ `memmap=True` refusé par astropy.
- **Bancs 132 / 133 / 134** : ce qui ne se scénarise pas se teste par le CHEMIN
  DE DÉCISION (espion) — voir `CLAUDE.md` (phase : espion sur `_phase` ; garde
  133 : `wk._nom_cible_proche` patché + JOURNAL ; 134 : `cv2.setRNGSeed`).
- **Instrumentation de l'aligneur** : l'empreinte seule ne joint pas une mesure à
  une frame (re-stacks, recalage Ha et propagation réalignent des EMPILEMENTS) —
  les marquer et les exclure (`_espion_155.marquer_restack`).
- **`_triangles` n'est PAS « la matrice LMEDS brute »** : il consolide déjà et
  laisse **0,015-0,035 px** sur un champ synthétique. Un décalage synthétique ne
  franchit donc JAMAIS `TRI_RAFFIN_SEUIL` — on teste le CÂBLAGE, pas une fiction.
- **Banc 134** : « au bit » exige `cv2.setRNGSeed(n)` avant CHAQUE appel
  (RANSAC/LMEDS tirent dans le générateur global d'OpenCV). Et `triangles` /
  `triangles+étoiles(n)` sont deux méthodes distinctes : les bancs 15 et 21
  exigent `== "triangles"` et restent verts (leur résidu est ~0,03 px).

### Contexte de reprise (à coller)
Arbre propre, **`4dd335b` poussé** : le ② choix C (jalon 134, v2.83.0) est
**LIVRÉ ET VALIDÉ en réel** (472 frames, 2 refus G 1 · R 1, canaux à
0,079 / 0,130 px, aucune régression). Prochaine action unique : **MESURER
l'étape ③ (SHO/HOO sans `phase`)** — refus par rôle AVANT/APRÈS et contrôle
positif 200 étoiles —, **sans toucher au code avant d'avoir les chiffres**.

---

## Chantier CLOS — ② choix C : raffiner `triangles` AU-DELÀ DU SEUIL (jalon 134, v2.83.0)

**Livré le 18/10** : `TRI_RAFFIN_SEUIL = 0,30` px et, dans
`StarAligner._triangles` **APRÈS** le contre-test mutuel final (le résidu y était
DÉJÀ calculé : `median(dist_cur[mutuel])`), un raffinement conditionnel
`_raffiner_centroides(frame, M, pos=pos)` — les centroïdes de la frame sont en
main, donc **aucune re-détection**. S'il conclut : `M` remplacée, méthode
`triangles+étoiles(n)` ; sinon `triangles` (rien ne change). `_last_t` posé APRÈS,
avec la matrice FINALE ; `try/except` autour de l'appel (une frame validée ne se
perd jamais). Banc 134 (7 volets, 30 vérifs) **vert** ; non-régression
**13 / 15 / 21 / 116 / 117 / 129b / 131 / 132 / 133** verte ; `py_compile` OK.
**VALIDÉ en réel le 18/10** : 472 frames (L 240 · R 79 · G 62 · B 51 · Ha 40),
2 refus (G 1 · R 1), 1 floue, **0,00 % de pixels noirs** et canaux alignés à
**0,079 px (R)** / **0,130 px (B)** sur le linéaire livré — le run précédent
donnait 0,087 / 0,155 px.
Trace complète : `CLAUDE.md` § « Raffinement `triangles` au-delà du seuil ».

**⚠ Le plan d'origine se trompait sur un point, et c'est MESURÉ** : il annonçait
« frame synthétique décalée de 1,0-1,5 px → raffinée, résidu ≤ 0,1 px ». FAUX :
`_triangles` laisse déjà **0,015-0,035 px** sur un champ propre, même décalé de
1,2 px (il consolide RANSAC + LMEDS sur appariements mutuels), et les centroïdes
ne peuvent pas améliorer ce qui est déjà au niveau du bruit (même similitude,
mêmes points). Un décalage synthétique ne franchit donc JAMAIS le seuil : le banc
134 teste le **câblage** (espion, seuils 0 et 10, matrice prise, méthode,
`_last_t`) + une frame **faible et floue** (résidu 0,236 px → 0,214 px).

---

## Chantier CLOS — CAUSE AMONT (taches rouges/bleues du LRGB) — clos le 18/10
Cause UNIQUE mesurée : le repli `phase` en broadband (frames B à l'envers sur un
champ à +177,07°, 11/50 puis 12/49) ; **corrigé à l'étape ①** et validé en réel.
Trace : `CLAUDE.md`, changelog v2.82.2, `git log` (140 → 149) — **ne rien rejouer**.

---

## Chantier en cours — LRGB+Ha (jalons 129 → J5) — reprend APRÈS ③

Le rôle Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le combine L.

| Jalon | Contenu | État |
|---|---|---|
| J1 / 129 (v2.81.0) | compositions + 5 lignes UI + séparation ancre / `_narrowband_ha` | commité |
| 129b | voie A (référence **PAR RÔLE** + recalage de l'empilement) + `profondeur_min` + refus par rôle | COMMITÉ ; validé en réel le 16/10 (441 frames, 2 refus en R) |
| **130 (v2.82.0)** | combine LRGB borné [0 ; 5] + repli local + fiche + banc neuf | COMMITÉ + POUSSÉ (`ef0c35c`) |
| J2 → J5 | fusion « ajout au rouge » + poids + cadre ; 4 autres modes ; continuum ; ancre réelle + doc | à faire |

Plan figé (13 arbitrages du 15/10) : poids **1,0** (0–10) · α **0,5** · Q **0,80**
(0,10–2,00) · cadre « Fusion Ha » visible seulement si la compo contient Ha ·
continuum = **bandes passantes** (Ha 7 nm / RGB 100 nm), référence **R** ·
identifiants en français (`synthetise`).

---

## En attente / prochaine session (état au 18/10)

- **Validé en réel (18/10)** : run LRGB **sans aucune tache bleue ni rouge**,
  **2 refus R + 1 G**, astrométrie **réussie** avec les bons indices.
- **Reprise** : `CLAUDE.md` § « Diagnostic de l'entrée d'astrométrie » (lire
  `indices` dans le dump AVANT tout) ; mesures dans `C:\Astro\test\`
  (`_dump154_*`, `_diag_astro_152/153*.py`, `_astap148*\`) — astrométrie RÉSOLUE.
- **Décisions d'Alain** : le **② est TRANCHÉ (C) et LIVRÉ** (v2.83.0) — il reste à
  le valider en réel ; restent **③** (SHO/HOO sans `phase`) et l'interface 141
  (A/B/C). Une release GitHub ne se fera QUE sur accord explicite.
- **RÉSOLU (141)** : « M33 en RGB montre les mêmes taches » = session **LRGB+Ha**
  avec l'interface passée en « RGB » **pendant** l'empilement (`AVACOMPO=LRGB+Ha…`).
- **VeraLux** : ancre calculée sur la luminance pondérée puis soustraite par canal
  (`max(x, 0)`), ~97 % du ciel consommé ⇒ le fond sort ×20 à ×40 (remède = piédestal).
- **Halo d'étoile** : couronne NEUTRE dans le brut, COLORÉE par le STF (R +41 % / G +19 % /
  B +23 % à r=14) ⇒ ce n'est pas l'empilement, c'est l'étirement + le clip par canal.
- Boutons de données sans Siril (« ⬇ Gaia », « ⬇ Spectres », « ⬇ Base SPCC ») ; **INDI** =
  jalon à part, après le portage Linux ; **Store** = cadence séparée (v2.71.1 publiée).
- Retour arrière en un geste : `git checkout -- avastack/processing/composition.py`.

---

## Setup d'Alain

- **Setup 1 (miniPC)** : QHY MiniCam8M (mono refroidie, roue intégrée) ; N.I.N.A. →
  `TargetSchedulerSequence/<cible>/<expo>/LIGHT` — un dossier peut MÉLANGER plusieurs nuits.
- **Setup 2** : C8 défourché + réducteur 0,63 (1280 mm) ; Player One Uranus-C Pro (couleur,
  IMX585, RGGB) sur monture DIY **Open Astro Mount** ; guidage SV305C sur 60/240.
- **Jeux de test (QHY + SV555)** : **M31** (L du 13/09 + R/G/B des 22-23/09, 60 s,
  −15 °C ; un dossier peut mêler les deux côtés du Pier) ; **M33** (nuit du
  10-11/10 : L 60×60 s, R/G/B 60-120 s) + un dossier **Ha de 40 frames**.
  Darks maîtres : 60 s (L/R/G), 120 s (B), 180 s (Ha).
- **Outils locaux** : Siril 1.4.4 (Gaia XP, base SPCC), ASTAP (D80 Gaia DR3) ; pas
  d'astrometry.net. **Ubuntu 26.04 LTS** : installateur éprouvé ; restent la
  machine VIERGE et le test matériel caméras (`--cameras`).

---

## Pièges récents (encore actifs — le reste est passé dans `CLAUDE.md`)

- **Une réussite de repli n'est pas une preuve d'alignement** : `phase` en
  translation seule a posé 11/50 puis 12/49 frames B **à l'envers**. Depuis ①,
  `_sans_phase` exige `avec_phase` ET `repli_phase` — ne jamais rendre une
  réussite de phase FINALE du chemin direct. Elle ne se scénarise pas : un banc
  teste le **chemin de décision** (espion), son coût sur une frame **douce**.
- **Un agrégat GLOBAL est AVEUGLE à un écart LOCAL** : 243 taches (~0,03 % des
  7,3 Mpx) font passer la couche B de +1,7 % à +80,7 % AUX POSITIONS sans bouger
  le poids moyen, le σ p50 ni les rejets. On lit **sur les positions** du défaut.
- **`poids` n'est JAMAIS 1,0** (médiane 0,918) : lire un rejet **contre le p5 du
  fond du même run**, avec témoin ; **comparer des tuiles** exige une ÉCHELLE
  COMMUNE (ramener chaque image à son propre fond).
- **Ne pas remettre `triangles_seuls`** : le refus Ha n'était pas un problème de
  méthode (0/5 contre 5/5, ~6 étoiles communes, `TRI_INLIERS_MIN(6)` non tenable).
- **Garde-fou `_invariants_triangles`** : `n_max` > ~30 explose la mémoire
  (13,7 Go de RSS constatés) ⇒ plafonner à 12/18/24/30.
- **`config.json` NE DIT PAS LA RÉALITÉ** (état à la dernière fermeture) : on MESURE.
- **Échecs PRÉEXISTANTS** : `_test_espace_jalon72` (géométrie d'écran),
  `_test_reset_empilement_jalon76` [4] (course `_stop()`, sensible à la charge CPU).
- **Tk / OpenCV / bancs `ui.App`** : jamais `grid` + `pack` dans le même conteneur ;
  `cv2.ocl.setUseOpenCL(False)` ; `ui.CONFIG = {}` et `ui.App._dire` patché
  (`_dire` = boîte MODALE, sinon blocage).
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`.

---

## Clôtures précédentes

- **18/10/2026 (matin)** : ⑧ + ⑨ + ⑩ — force du bleu réelle et LOCALE ; cause
  mesurée à l'ASTAP = frames B empilées **à l'envers** par le repli `phase`
  (11/50 et 12/49), pas la référence ni le rejet ⇒ correctif = étape ①.
- **17/10/2026 (matin)** : 133 — le fichier `2.82.0 bis` est reproductible AU BIT ;
  le dark est innocenté (le 132f mesurait les brutes du disque : méthode invalide).
