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

Versions : `LRGBHa` = **v2.82.2** (⑦ v2.82.1 + étape ① + **garde 133** —
**COMMITÉE ET POUSSÉE** le 18/10, `586f860`) · `master` publié = **v2.80.0** ·
Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 18/10/2026 — ① + garde 133 livrées (v2.82.2) puis étape ② MESURÉE

### Ce qui est livré (v2.82.2, commité et poussé `586f860`)
- **Étape ①** : plus de repli `phase` en BROADBAND (`PHASE_EN_BROADBAND = False`,
  `repli_phase_session(narrowband)`, verrou dans `_sans_phase` : il exige
  `avec_phase` **et** `repli_phase`) ; ordre ORB → triangles INCHANGÉ. Un champ
  retourné est RETOURNÉ (réessai +180°) ou REFUSÉ, jamais empilé à l'envers.
  Banc neuf 132 (8 volets, vert), non-régression 21/13/116/131/129b.
- **Garde d'interface d'astrométrie (jalon 133)** : `_astro_indices_garde()`
  compare la saisie à `OBJCTRA/OBJCTDEC` de la brute (seuil 0,25 × champ),
  retient l'en-tête au-delà et REPOSE `suivi_astro.indice()` ; une seule
  comparaison par jeu d'indices. Banc neuf 133 (6 volets, vert).
- **Verdict ⑩** : 11/50 puis 12/49 frames B empilées à l'envers par `phase` sur
  un champ à +177,07° (translation ≥ 2 591 px impossible) — détail `CLAUDE.md`.


### Garde d'interface d'astrométrie (jalon 133) — LIVRÉE le 18/10
- **Où** : `worker._astro_indices_garde()`, appelée par `_astro_tour` **après**
  la lecture d'en-tête et **avant** la pose des indices — un seul point, jamais
  l'interface.
- **Quoi** : indices venus de la **saisie** + brute courante portant
  `OBJCTRA/OBJCTDEC` (repli `RA/DEC`) ⇒ `astrometrie.separation_deg()`
  (haversine) comparée à **`GARDE_INDICES_FRACTION` (0,25) × champ saisi**.
  Au-delà : **en-tête retenu** (AD/Dec de la brute ; champ de l'en-tête s'il est
  déductible, sinon **champ saisi**), `suivi_astro.indice()` **reposé** (WCS
  oublié, essais à zéro), ligne d'état + journal disant les DEUX valeurs et
  laquelle est retenue. Sous le seuil, ou sans coordonnées : **rien ne change**.
- **Coût borné** : UNE comparaison par jeu d'indices saisi (`_astro_garde_pour`) —
  aucun `fits.open` ajouté sur le chemin de la boucle.
- **Banc NEUF** `bancs/_test_astro_indices_garde_jalon133.py` (6 volets, **VERT**,
  23 vérifications) : M31 saisi sur M33 → en-tête retenu + message + journal et
  le **solveur reçoit les bons indices** ; même cible à 0,05° → saisie gardée +
  **une seule** lecture ; sans coordonnées → saisie gardée ; déjà d'en-tête →
  aucune lecture ; WCS résolu **toujours propagé** ; champ de l'en-tête adopté
  quand il est déductible.
- **Non-régression** : bancs **132, 115, 113, 56, 76** verts (banc 115 : son
  bouchon d'aligneur porte `repli_phase`, attribut né à l'étape ①).

### Étape ② du plan ⑪ — MESURÉE le 18/10 (AUCUNE ligne de code touchée)
- **Protocole** : run RÉEL LRGB+Ha instrumenté PASSIVEMENT (vrai `ui.App`, mêmes
  brutes/darks/ordre : L 240, R 80, G 64, B 51, Ha 40 ; `--no-save`), espion sur
  `StarAligner._triangles` qui mesure les centroïdes AVANT (`_verif_centroides`,
  appariements mutuels ≤ 2,5 px) et le candidat de `_raffiner_centroides` APRÈS,
  sans rien changer à la cascade. Re-stacks, recalage Ha et propagation
  d'astrométrie EXCLUS (ils réalignent des EMPILEMENTS). 475 frames lues,
  **472 empilées, 1 floue, 2 refus (G)**, 143 mesures, 0 erreur d'espion.
- **Population `triangles`** : **143 / 472 frames (30,3 %)** — B 16/51,
  G 33/61, **Ha 39/40**, L 31/240, R 24/80. Les refus restent **G 2**
  (réf `G/auto`, seq 215 et 271) : le ② ne peut PAS en retirer, un raffinement
  ne refuse jamais une frame.
- **Résidu de la matrice `triangles` sur les étoiles (AVANT)** : méd 0,083 px ·
  p90 0,675 · max 1,385. Par classe : **87/143 ≤ 0,10 px**, 13 dans 0,10-0,30,
  30 dans 0,30-0,70, 13 > 0,70.
- **Ce que les centroïdes changent (APRÈS)** : candidate GARDÉE **112/143**
  (78 %), 31 inchangées ; résidu méd 0,0855 · p90 0,644 · **max 1,141** ;
  107 meilleures, 5 égales (plus d'appariements), **0 pire** (par construction).
  Gain : **90 frames < 0,05 px**, 4 dans 0,05-0,10, 12 dans 0,1-0,3, **1 seule
  ≥ 0,3** (max 0,734) ; méd 0,002 px. Déplacement de translation : méd 0,018 px,
  p90 0,784, max 2,934 — **7 frames seulement > 1 px**, et ce sont les pires
  (ex. 1,385 → 0,651 px).
- **PAR RÔLE (résidu méd avant → après · déplacement méd)** : B 0,060 → 0,060
  (0,035 px) · G 0,082 → 0,084 (0,005) · Ha 0,070 → 0,069 (0,006) ·
  **L 0,484 → 0,467 (0,164)** · R 0,083 → 0,082 (0,024).
- **LECTURE** : `_triangles` n'est PAS « la matrice LMEDS brute » — il consolide
  déjà (RANSAC 2,5 px + LMEDS + contre-test mutuel 2,5 px). Le ② garde une
  candidate sur 112/143 frames mais le gain reste **< 0,05 px sur 95/143
  (66 %)** ; il corrige PARTIELLEMENT les 7 pires et ne touche PAS le résidu
  systématique de la couche **L (~0,48 px)**, qui est une DISTORSION inter-nuits
  (le palier ~0,8 px du jalon 117, qu'un affine n'améliore pas) : ce n'est pas
  la translation que les centroïdes corrigent.
- **Contrôle positif 200 étoiles** (transformation CONNUE) : 202 appariements,
  résidu **0,0438 px** à la vraie matrice, **1,4904 px** pour une erreur connue
  de 1,5 px (lu − connu = −0,0096), retour à **0,0104 px** après raffinement ;
  scénario rotation+échelle : 176 appariements, 0,0533 px, erreur retrouvée à
  0,0148 px. ⇒ la mesure réagit à une erreur connue.
- **Outils hors dépôt** : `_espion_155.py`, `_lance_155.py`,
  `_diag_155b_controle.py`, `_diag_155c_analyse.py`, `_diag_155d_detail.py`,
  `_diag_155a_methodes.py` ; preuves `_155_centroides.jsonl`,
  `_trace155/155.jsonl`, `_155b_controle.json`, `_155_resultat.txt`.

### État actuel
- **Code** : v2.82.2 **COMMITÉE ET POUSSÉE** (`586f860`, `origin/LRGBHa`) ;
  arbre de travail **propre** — le ② n'a modifié AUCUN fichier du dépôt.
- **RUN RÉEL LRGB (Alain, 18/10)** : plus aucune tache bleue NI rouge ⇒ `phase`
  en broadband était la seule cause. Test taches **TERMINÉ**.
- **Astrométrie** : réussie après correction des indices (garde 133 livrée).
- **Reste à faire** : décider du ② (mesure faite, gain marginal) puis ③
  (SHO/HOO sans `phase`).
- **Combine** innocenté trois fois (140/142/143) : `_ratio_combine` intact.


### Fichiers modifiés dans cette phase
- **Étape ② : AUCUN fichier du dépôt** (mesure hors dépôt ; outils listés dans
  la section ② ci-dessus). Les fichiers ci-dessous sont ceux de la v2.82.2.
- `avastack/processing/alignment.py` (interrupteur + verrou `_sans_phase`),
  `avastack/core/worker.py` (session, dump astro, garde 133),
  `avastack/processing/astrometrie.py` (`separation_deg`, seuil),
  `avastack/processing/trace_roles.py` (`repli_phase`), `avastack/ui/app.py`,
  `avastack/__init__.py` (**v2.82.2** + changelog).
- Bancs NEUFS : `_test_phase_broadband_jalon132.py` (8 volets),
  `_test_astro_indices_garde_jalon133.py` (6 volets) ; bouchons d'aligneur du
  banc 115 complétés (`repli_phase`).
- `CLAUDE.md` (§ étape ①, § garde 133, § étape ②) et `AVANCEMENT.md`.


### Mesures du chantier (détail dans `CLAUDE.md` et le changelog v2.82.2)
- **140** RGB : aucune tache. **142** LRGB : R +103,9 % · B +132,1 %.
  **143** L←R : B +80,7 %. **144** L←B : B +34,6 %. Rejeux 146/147 au bit :
  force du bleu **4,5 / 81,1 / 46,1 %** ; poids 0,857 et σ **×4,38** aux 243
  taches ; couches B entre runs r 0,985 · **Δ méd +72,3** aux 243 taches.

### Astrométrie — RÉSOLUE le 18/10 : les AD/Dec étaient celles de M31
- **Cause** : les champs gardaient **M31** (10,683333 / +41,268611) alors que les
  brutes étaient **M33** ; après correction de la saisie, le solve **résout**
  (115 appariements, 2,469″/px, rms 0,30 px). Le champ (2,637°) ne distinguait
  pas les deux cibles. Leçon durable : `CLAUDE.md` § « Diagnostic de l'entrée
  d'astrométrie » ; preuves `_dump154_indicesM31\`, `_dump154_off\`.


### Décisions prises
- **Combine hors de cause** (140/142/143) ⇒ on ne touche pas à `_ratio_combine`.
- **Cause UNIQUE mesurée** : `phase` en broadband. Le run réel de ① efface les
  **deux** couleurs (bleu ET rouge) ⇒ l'hypothèse « rouge = contenu des 240
  brutes L » est **ABANDONNÉE** : ne pas la rouvrir sans un NOUVEAU symptôme.
- **Étape ① appliquée TELLE QUELLE** : `phase` écartée en broadband, **conservée**
  en HOO/SHO (étape ③) ; les aligneurs du Ha (voie A) ne sont PAS touchés.
- **Le correctif est un INTERRUPTEUR** (`PHASE_EN_BROADBAND`) : le rebasculer à
  `True` rend le comportement d'avant sans toucher au reste — comparaison possible.
- **PAS de case dans l'interface** (décision d'Alain du 18/10/2026) : on teste
  d'abord en mode unique (phase écartée en broadband). Une case ne sera ajoutée
  que si le besoin de **jongler entre les 2 modes selon les cibles** apparaît ;
  l'architecture est déjà prête (le drapeau est fixé PAR SESSION, une case
  n'aurait qu'à écrire `aligner.repli_phase`).
- **La composition d'un fichier se lit dans son `AVACOMPO`**, jamais dans l'interface (141).
- **134c invalide** (brute dithérée) ; **135/136/138** sur 40 frames ⇒ annulées.
- **Interface (141)** : (A) documenter, (B) prévenir, (C) invalider — à trancher.

### Problèmes ouverts
- **Décision ②** : la mesure est faite (gain méd 0,002 px ; 7 frames > 1 px dont
  les pires 1,385 → 0,651). Options : (A) ne RIEN ajouter, (B) ajouter le
  raffinement tel quel (coût mesuré : **~0,10 s** par frame `triangles`, max
  0,41 s, sur 143 frames), (C) ne l'appliquer qu'aux matrices dont le résidu
  dépasse un seuil. **Alain tranche.**
- **Résidu systématique de la couche L (0,48 px)** : distorsion inter-nuits
  (palier ~0,8 px du jalon 117) que ni la similitude ni l'affine ne corrige —
  à instruire SÉPARÉMENT (ce n'est pas le ②).
- **VeraLux** : à instruire (ancre calculée puis soustraite par canal) — APRÈS ②/③.

### Prochaines étapes
1. **Décision d'Alain sur le ②** (A/B/C ci-dessus) — aucune ligne de code n'est
   écrite avant son accord.
2. **③** : SHO/HOO sans `phase` — mesure du coût (refus par rôle) avant décision.
3. Contrôle positif 200 étoiles OBLIGATOIRE à chaque mesure.

### Points d'attention
- **Une brute est DITHÉRÉE** : seul un empilement ALIGNÉ (mono ou couche) prouve quelque chose.
- **`--dossier` sans `--dark` = run invalide** dès que l'exposition change (L ← B, 120 s).
- **Comparer deux BRUTES par corrélation est INVALIDE si le dossier mélange des
  nuits** (B : 14→23/09) ; les `cadre` de deux runs ne se comparent pas non plus.
- `save_canaux_request` : attendre l'écriture des couches avant de quitter l'appli ;
  brutes NINA : `BZERO/BSCALE` ⇒ `memmap=True` refusé par astropy.
- **Banc 132** : la corrélation de phase ne se scénarise pas (elle réussit ou non
  selon le contenu) — le volet « piège » teste le CHEMIN DE DÉCISION avec un
  espion ; le volet « coût » exige une frame douce (contraste 0,10, flou σ = 1).
- **Banc 133** : le message de la garde nomme les cibles via le catalogue
  d'objets célèbres — le banc **patche `wk._nom_cible_proche`** (aucun catalogue
  requis) et vérifie le JOURNAL, pas seulement `astro_info` (la résolution
  remplace la ligne d'état par son résumé).
- **Instrumentation de l'aligneur** : l'EMPREINTE seule ne suffit pas à joindre
  une mesure à une frame — les re-stacks, le recalage de la couche Ha et la
  propagation d'astrométrie réalignent des EMPILEMENTS dont l'empreinte peut
  COÏNCIDER avec une brute (couche Ha à 1 frame). Les marquer et les exclure
  (`_espion_155.marquer_restack`), sinon la population est doublée.
- **`_triangles` n'est PAS « la matrice LMEDS brute »** : il consolide déjà
  (RANSAC 2,5 px + LMEDS + contre-test mutuel). Ne pas réécrire cette phrase
  dans un plan sans revérifier le code.

### Contexte de reprise (à coller)
v2.82.2 **commitée et poussée** (`586f860`) ; arbre de travail **propre**.
**Étape ② du plan ⑪ MESURÉE le 18/10** : 143/472 frames (30,3 %) posées par
`triangles`, résidu méd 0,083 px (L 0,484), gain des centroïdes méd **0,002 px**
(90/143 < 0,05), 7 frames seulement déplacées de plus de 1 px, **0 refus
supprimable** ; contrôle positif 200 étoiles PASS. Prochaine action unique :
**attendre la décision d'Alain (A ne rien ajouter / B ajouter / C sous seuil)**
avant d'écrire la moindre ligne de code.


---

## Chantier CLOS — CAUSE AMONT (taches rouges/bleues du LRGB) — clos le 18/10
Cause UNIQUE mesurée : le repli `phase` en broadband (frames B empilées à
l'envers sur un champ à +177,07°, 11/50 puis 12/49) ; **corrigé à l'étape ①**
et validé par le run réel d'Alain (plus aucune tache bleue ni rouge).
Trace complète : `CLAUDE.md` (§ pose vraie, § repli `phase`), changelog v2.82.2,
`git log` (140 → 149) — **ne rejouer aucune de ces mesures**.


---

## Chantier en cours — LRGB+Ha (jalons 129 → J5) — reprend APRÈS la garde d'interface

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

## En attente / prochaine session

- **Validé en réel (18/10)** : run LRGB **sans aucune tache bleue ni rouge**,
  **2 refus R + 1 G**, astrométrie **réussie** avec les bons indices.
- **Reprise** : § « Astrométrie — RÉSOLUE » ci-dessus +
  `CLAUDE.md` § « Diagnostic de l'entrée d'astrométrie » (leçon durable : lire
  `indices` dans le dump AVANT tout). Mesures antérieures dans `C:\Astro\test\` :
  `_astap148*\`, `_148h_toutes.txt`, `_diag_astro_152.py`, `_diag_astro_153_entree.py`,
  et pour cette séance `_dump154_indicesM31\`, `_dump154_off\`, `_154*_etat.json`.
- **Décisions d'Alain attendues** : le **②** est MESURÉ (gain méd 0,002 px,
  7 frames > 1 px, 0 refus supprimable) ⇒ trancher **A** (ne rien ajouter),
  **B** (ajouter le raffinement) ou **C** (seulement sous seuil de résidu) ;
  restent **③** (SHO/HOO sans `phase`) et l'interface 141 (A/B/C).
  Une release GitHub ne se fera QUE sur accord explicite.
- **RÉSOLU (141)** : « M33 en RGB montre les mêmes taches » = session **LRGB+Ha** avec
  l'interface passée en « RGB » **pendant** l'empilement ; le fichier porte
  `AVACOMPO=LRGB+Ha…`. Un vrai RGB (après « Arrêter » ou « Réinitialiser ») n'a rien.
- **VeraLux** : ancre calculée sur la luminance pondérée puis soustraite par canal
  (`max(x, 0)`), ~97 % du niveau de ciel consommé ⇒ tout écart de fond sort ×20 à ×40 ;
  remède déjà actif = **piédestal par canal** (jalon 122).
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
- **Jeux de test (QHY + SV555)** : **M31** (L du 13/09 + R/G/B des 22-23/09, 60 s, −15 °C ;
  un dossier peut mêler les deux côtés du Pier) ; **M33** (nuit du 10-11/10 : L 60×60 s,
  R/G/B 60-120 s) + un dossier **Ha de 40 frames** (cible du test J1).
  Darks maîtres : 60 s (L/R/G), 120 s (B), 180 s (Ha).
- **Outils locaux** : Siril 1.4.4 (catalogues Gaia XP, base SPCC), ASTAP (D80 Gaia DR3) ;
  pas d'astrometry.net. **Ubuntu 26.04 LTS** : installateur Linux éprouvé ; restent la
  machine VIERGE et le test matériel caméras (`--cameras`).

---

## Pièges récents (encore actifs)

- **AD/Dec d'astrométrie PERSISTÉES d'une cible à l'autre** : à l'ouverture de
  l'appli, `_source_fichiers_obsolete()` rend `False` (aucune caméra) donc les
  coordonnées restaurées de la config servent à la NOUVELLE cible. Mesuré le
  18/10 : M31 (`10,683333 / +41,268611`) sur des brutes M33 → « 5 étoiles,
  4 inliers, 1,615″/px ». Lire **`indices`** dans le dump. **FERMÉ au jalon 133**
  côté worker (`_astro_indices_garde`, seuil 0,25 × champ) — le piège reste à
  connaître pour lire un journal d'AVANT la v2.82.2.

- **Un agrégat GLOBAL est AVEUGLE à un écart LOCAL** : 243 taches (~0,03 % des
  7,3 Mpx) font passer la couche B de +1,7 % à +80,7 % AUX POSITIONS sans
  bouger le poids moyen (0,916 → 0,919), le σ p50 ni les rejets. « La couche ne
  change pas » ne se lit jamais sur des percentiles : on lit **sur les
  positions** du défaut (c'est le trou du 145, comblé par le 146).
- **Les CARTES sont sur le CANEVAS d'empilement** (union des cadres), pas sur la
  couche croisée : décalage > 100 px → `decalage_etoiles(..., lim=300)` (avec
  `lim=60` : 2 % appariées et un contrôle positif à +0 %).
- **`poids` n'est JAMAIS 1,0** : kappa-sigma retire des frames partout
  (médiane 0,918). Lire un rejet **contre le p5 du fond du même run**, avec témoin.
- **Comparer des tuiles n'a de sens qu'à ÉCHELLE COMMUNE** : ramener chaque image
  à son propre fond (×0,90 → ×1,50) ; une tuile étirée seule paraît toujours propre.
- **Le refus Ha n'est pas un problème de méthode** : `triangles_seuls` True/False → 0/5 ;
  Ha retourné ~180°, ~6 étoiles communes, `TRI_INLIERS_MIN(6)` non tenable. Ne pas le remettre.
- **Le repli « phase » n'est PAS une preuve d'alignement** (1/3 au banc 129b ;
  11-12 frames B par run empilées **à l'envers** au ⑩) : une translation seule ne
  peut pas aligner un champ retourné. **CORRIGÉ (①, v2.82.2)** : `_sans_phase`
  exige `avec_phase` ET `repli_phase` — ne jamais rendre une réussite de phase
  FINALE du chemin direct. **Et elle ne se scénarise pas** : à paramètres voisins
  elle réussit ou refuse selon le contenu → un banc teste le **chemin de décision**
  (espion sur `_phase`), et son coût se mesure sur une frame **douce** (contraste
  0,10, bruit 0,008, flou σ = 1).
- **Une empreinte ne dit pas le SENS du champ** : `PIERSIDE` (West/East) et
  `ANGLE`/`OBJCTROT` sont dans l'en-tête FITS ; `align_ok=True` avec `angle=0`
  reste compatible avec une frame retournée.
- **Garde-fou `_invariants_triangles`** : `n_max` > ~30 explose la mémoire (13,7 Go de RSS
  constatés) ⇒ plafonner à 12/18/24/30.
- **SPCC** : le mode « offset » du Linear Fit ne rééchelonne pas (`gains = 1.0`) — un
  coefficient extrême n'est pas compensé ; ne pas appliquer une pente hors [0,5 ; 1,5].
- **`moyennes()` APPLIQUE le recalage de rôle** : lire un empilement BRUT via `mean()`.
- **Pixels à CANAL NUL** (bug corrigé au jalon 120) : les exclure de toute statistique.
- **La CHROMA est un NO-OP sur une image monochrome** : tester sur une image couleur.
- **`config.json` NE DIT PAS LA RÉALITÉ** (état à la dernière fermeture) : on MESURE.
- **VeraLux amplifie le fond** ; la neutralisation est réservée à VeraLux,
  `reduire_bruit_chroma` est commune, les DEUX sont exclues de la sortie linéaire traitée.
- **JOB EXTERNE = 11 éléments** (un job plus court est lu tolérant) ; **`_vl_params()`
  n'inclut pas la forme** et arrondit `vl_chroma_rayon` à 2 décimales.
- **Échecs PRÉEXISTANTS** : `_test_espace_jalon72` (géométrie d'écran),
  `_test_reset_empilement_jalon76` [4] (course `_stop()`, sensible à la charge CPU).
- **`_fmt_expo` est DÉJÀ PRIS dans `app.py`** ; **Tk** : jamais `grid` + `pack` dans le même
  conteneur ; **OpenCV** : `cv2.ocl.setUseOpenCL(False)` ; bancs `ui.App` : `ui.CONFIG = {}`
  et `ui.App._dire` patché (`_dire` = boîte MODALE, sinon blocage).
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`.
- **Ordre de la chaîne** : recadrage → gradient → débruitage → netteté → étirement.

---

## Clôtures précédentes

- **18/10/2026 (matin)** : ⑧ + ⑨ + ⑩ — force du bleu réelle et LOCALE ; cause
  mesurée à l'ASTAP = frames B empilées **à l'envers** par le repli `phase`
  (11/50 et 12/49), pas la référence ni le rejet ⇒ correctif = étape ①.
- **17/10/2026 (matin)** : 133 — le fichier `2.82.0 bis` est reproductible AU BIT ;
  le dark est innocenté (le 132f mesurait les brutes du disque : méthode invalide).


