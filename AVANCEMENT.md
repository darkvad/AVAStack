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

Versions : `LRGBHa` = **v2.82.2** (⑦ v2.82.1 + étape ① + **garde 133** — **NON
COMMITÉS** ; dernier commit `d95a19e` = v2.82.0) · `master` publié = **v2.80.0** ·
Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 18/10/2026 — plan ⑪ : étape ① + garde 133 LIVRÉES (v2.82.2), bancs verts

### Ce qui est livré
- **Étape ① : plus de repli `phase` en BROADBAND.** `StarAligner.repli_phase`
  (défaut **True** = comportement historique) + `PHASE_EN_BROADBAND = False` +
  `repli_phase_session(narrowband)` dans `processing/alignment.py` ; le worker
  l'applique **PAR SESSION** à la création de l'empileur : **False** en
  broadband (RGB/LRGB±Ha, mono, OSC), **True** en HOO/SHO (étape ③).
  `_sans_phase` exige les DEUX verrous (`avec_phase` du réessai +180° **et**
  `repli_phase`) ; l'ordre **ORB → triangles** est INCHANGÉ.
- **Conséquence VOULUE** : une « réussite » de phase en translation seule n'est
  plus finale ⇒ `compute` atteint son réessai **+180°** (puis l'ORB étoffé) ; un
  champ retourné est RETOURNÉ ou REFUSÉ, jamais empilé à l'envers.
- **Banc NEUF** `bancs/_test_phase_broadband_jalon132.py` (8 volets, **VERT**) :
  piège reproduit (angle 0 quand l'interrupteur est à True), `_phase` plus jamais
  appelée à False, retournée 177,07° à **0,01 px** de la pose vraie, table
  **par rôle** (L/R/G/B) : **6/8** faibles refusées contre **1/8** avec la phase,
  **0 frame à l'envers**. Non-régression : bancs 21, 13, 116, 131, 129b **verts**.
- **Verdict ⑩ (rappel — détail dans `CLAUDE.md` § « Pose vraie contre pose
  appliquée »)** : les 4 divergentes sont fausses dans LES DEUX runs ; **11/50**
  (140) et **12/49** (143) frames B ont été empilées **à l'envers** par `phase`
  sur un champ à **+177,07°** (résidu d'une translation ≥ **2 591 px**) ; ce n'est
  ni la référence ni le rejet par kappa-sigma.

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

### État actuel
- **Code** : ⑦ (v2.82.1), ① (v2.82.2) **et** la garde 133 sont écrits mais **NON
  COMMITÉS** — l'arbre de travail porte les trois. Bancs 132 + **133** verts, plus
  les voisins 115, 113, 56, 76.
- **RUN RÉEL LRGB (Alain, 18/10)** : **plus aucune tache bleue NI rouge**, très
  peu de rejets (**2 R + 1 G**, à confirmer sur la trace) ⇒ `phase` en broadband
  était la **seule** cause des deux couleurs. Test taches **TERMINÉ**.
- **Astrométrie** : run relancé avec les **bons indices** ⇒ **réussie** ; cause
  = AD/Dec de **M31** restées dans les champs ⇒ **garde 133 LIVRÉE** (le piège
  est fermé côté worker).
- **Reste à faire** : le **commit de la v2.82.2**, puis ② et ③ du plan ⑪.
- **Combine** innocenté trois fois (140/142/143) : `_ratio_combine` intact.

### Fichiers modifiés dans cette phase
- `avastack/processing/alignment.py` : `PHASE_EN_BROADBAND`,
  `repli_phase_session`, `StarAligner.repli_phase`, verrou dans `_sans_phase`,
  doc du module et de `_compute_direct`.
- `avastack/core/worker.py` : interrupteur appliqué par session (création de
  l'empileur), copié par l'aligneur de propagation WCS, note sur les aligneurs Ha ;
  **diagnostic `AVASTACK_DUMP_ASTRO`** (inactif par défaut) : dump de l'image
  exacte donnée au solveur d'astrométrie + JSON + verdict ; **garde 133** :
  `_astro_indices_garde`, `_astro_journal`, `_brute_courante` (extrait de
  `_astro_indices_entete`), appel dans `_astro_tour` ; `_nom_cible_proche`.
- `avastack/processing/astrometrie.py` : `GARDE_INDICES_FRACTION` (0,25),
  `separation_deg()` (haversine).
- `avastack/ui/app.py` : `_astro_garde_pour` initialisé avec les autres états
  d'astrométrie.
- `avastack/processing/trace_roles.py` : champ `repli_phase` (ligne `reference`).
- `avastack/__init__.py` : **v2.82.2** + changelog (①, dump astro, garde 133).
- `bancs/_test_phase_broadband_jalon132.py` : **NEUF** (8 volets).
- `bancs/_test_astro_indices_garde_jalon133.py` : **NEUF** (6 volets).
- `bancs/_test_astro_domaine_jalon115.py` : bouchons d'aligneur complets
  (`repli_phase`).
- `CLAUDE.md` (§ étape ①, § garde 133) et `AVANCEMENT.md`.

### Mesures du chantier (détail dans `CLAUDE.md` et le changelog v2.82.2)
- **140** RGB : aucune tache. **142** LRGB : R +103,9 % · B +132,1 %.
  **143** L←R : B +80,7 %. **144** L←B : B +34,6 %. Rejeux 146/147 au bit :
  force du bleu **4,5 / 81,1 / 46,1 %** ; poids 0,857 et σ **×4,38** aux 243
  taches ; couches B entre runs r 0,985 · **Δ méd +72,3** aux 243 taches.

### Astrométrie — RÉSOLUE le 18/10 : les AD/Dec étaient celles de M31
- **Cause** : les champs d'astrométrie avaient gardé **M31** (10,683333 /
  +41,268611) alors que les brutes étaient **M33** (en-tête 23,4625 / +30,66) ;
  Alain a corrigé la saisie, le run suivant **résout**. Détail et leçon durable :
  `CLAUDE.md` § « Diagnostic de l'entrée d'astrométrie ».
- **Preuve** (dump, vrai `ui.App`, 12 brutes M33 du 22/09, 3/rôle) : les deux
  entrées sont **identiques au pixel** (r = 1,000000, écart médian 0) ;
  indices M31 → **échec** « 5 étoiles, 4 inliers, 1,615″/px » (le sien :
  3 inliers, 1,603) ; indices M33 → **OK, 115 appariements, 2,469″/px,
  rms 0,30 px**. Le champ (2,637°) ne distinguait PAS les deux cibles.
- **Mécanisme** : à l'ouverture, `_source_fichiers_obsolete()` rend `False`
  (aucune caméra) ⇒ les AD/Dec restaurées de la config servent à la NOUVELLE
  cible. D'où la **garde d'interface** en prochaine action.
- **Outils hors dépôt** : `_run_astro_154_capture.py`, `_diag_astro_154d_jeu.py`,
  `_diag_astro_154e_compare.py` ; preuves `_dump154_indicesM31\`, `_dump154_off\`.

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
- **VeraLux** : à instruire (ancre calculée puis soustraite par canal) — APRÈS ②/③.
- **② et ③** du plan ⑪ : à démarrer sur ton accord.

### Prochaines étapes
1. **COMMIT de la v2.82.2** (⑦ + ① + garde 133) — bancs 132 **et 133** verts, plus
   21/13/116/129b/115/113/56/76 ; run réel LRGB OK ; astrométrie OK.
   ⚠ La garde a été ajoutée **sous la MÊME version** (précédent : le dump astro) ;
   si Alain préfère une **v2.82.3** pour le jalon 133, seul `AVASTACK_VERSION` et
   l'en-tête du bloc changent.
2. **② du plan ⑪** : centroïdes APRÈS `triangles` (mesure, pas de correction avant).
3. **③** : SHO/HOO sans `phase` — décision après mesure du coût.
5. Contrôle positif 200 étoiles OBLIGATOIRE à chaque mesure.

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

### Contexte de reprise (à coller)
Étape ① validée en réel (aucune tache bleue ni rouge, 2 refus R + 1 G),
astrométrie réussie avec les bons indices et **garde 133 livrée** (banc vert) ;
le code (⑦ + ① + 133) reste **NON COMMITÉ**.
Prochaine action unique : le **commit de la v2.82.2**, puis l'étape ② du plan ⑪.

---

## Chantier en cours — CAUSE AMONT (taches rouges/bleues du LRGB) — **CLOS le 18/10**

> Conservé comme TRACE de la recherche : ne rejouer aucune de ces mesures. La
> synthèse exploitable est dans `CLAUDE.md` (§ pose vraie, § repli `phase`) et
> le changelog v2.82.2.

**Objectif** : supprimer les taches vues sur M33 en LRGB (absentes en RGB et en mono).
**Règles d'or** : aucune correction avant d'avoir nommé la cause ; contrôle positif de
recalage à chaque mesure ; mesurer sur les couches du **même run** ; rien n'est corrigé
sans l'accord d'Alain.

| Étape | Contenu | État |
|---|---|---|
| ① 131→133 | étirement (×600 au fond) et dark innocentés ; `2.82.0 bis` reproductible au bit | fait |
| ② 134→139 | analyse des taches ; 134c invalide ; 135/136/138 sur couches de 40 f ⇒ annulées | fait |
| ③ **140** | RGB sans L : **AUCUNE tache** ⇒ le rôle L est nécessaire | fait |
| ④ **142 / 142b / 142c** | taches DANS les couches R et B ; combine innocenté ; blob compact ×6,25 | fait |
| ⑤ **143** | L ← dossier R : **rouge parti, bleu là** ⇒ deux causes | fait |
| ⑥ **144** | L ← dossier B (dark 120 s) : **rouge toujours propre, bleu partiel** | fait |
| ⑦ **145** (v2.82.1) | instrumentation du worker par rôle ; rejeu 140/143/144 (agrégats **globaux** : B inchangée) ; retournement 177° et σ de B empoisonné découverts | fait |
| ⑧ **146** | rejeu avec `--canaux` + `--trace` : **force du bleu retrouvée (4,5 / 81,1 / 46,1 %)**, couches refaites **au bit** ; écart **local** (+72 points aux 243 taches) | **fait (18/10)** |
| ⑨ **147** | cartes `poids`/`σ` aux 243 taches : **rejet ET géométrie** — poids 0,857 (témoin rouge 1,2 % sous p5), σ **×4,38** (témoin 1,00) ; 11,4 % des frames B posées à > 2 px d'un run à l'autre (max 32,8) | **fait (18/10)** |
| ⑩ **148** | pose vraie mesurée hors appli (**ASTAP**) : les 4 divergentes sont fausses dans **les DEUX** runs ; **11/50** et **12/49** frames B empilées **à l'envers** par le repli `phase` (rotation 0 sur un champ à **+177,07°**) ⇒ ce n'est ni la référence ni le rejet | **fait (18/10)** |
| ⑪ **① — 132 (v2.82.2)** | plan ⑪ étape ① : **plus de repli `phase` en broadband** (interrupteur `PHASE_EN_BROADBAND` + verrou dans `_sans_phase`) ; banc neuf (8 volets) : piège supprimé, retournée 177,07° à 0,01 px, refus **par rôle** mesurés | **LIVRÉ le 18/10** · banc vert · **NON COMMITÉ** |
| ⑫ **run réel LRGB** | **VALIDATION EN RÉEL (Alain, 18/10)** : **plus aucune tache bleue ni rouge** ; rejets **2 R + 1 G** ; astrométrie **réussie** avec les bons indices ⇒ cause amont **CLOSE** | **validé** · reste le commit |

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
- **Décisions d'Alain attendues** : **commit de la v2.82.2** (⑦ + ① + garde 133)
  ou version séparée **v2.82.3** pour le jalon 133 ; démarrage de **②**
  (centroïdes après `triangles`) puis **③** (SHO/HOO sans `phase`) ; interface
  141 (A/B/C).
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


