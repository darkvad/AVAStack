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

Versions : `LRGBHa` = **v2.84.0** (⑦ v2.82.1 + ① + **garde 133** en v2.82.2,
`586f860` ; **② choix C** jalon 134 `4dd335b`, validé en réel ; **③ jalon 135**
= phase retirée en narrowband, à valider en réel sur Sh2-132) · `master` publié =
**v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 18/10/2026 — ① + 133 (v2.82.2), ② choix C (v2.83.0), ③ LIVRÉE (v2.84.0)

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
- **v2.84.0 — étape ③ (jalon 135)** : `PHASE_EN_NARROWBAND = False` +
  `repli_phase_session()` qui lit l'une OU l'autre constante ; le repli « phase »
  n'existe plus dans les DEUX modes. Banc neuf 135 (7 volets) vert, banc 132
  mis à jour. **À valider en réel sur Sh2-132.**
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

### Étape ③ du plan ⑪ — MESURÉE puis LIVRÉE (v2.84.0, jalon 135)
- **Mesure 1 (jeux SANS retournement)** : **109 frames** (SHO Rosette 53 · HOO
  NGC 7000 26 · SHO IC 443 30 ; 300 s, multi-nuits, ancre Ha à **250 étoiles**) →
  **0 refus AVANT / 0 APRÈS**, méthodes identiques frame par frame, phase jamais
  retenue. Contrôle positif 200 étoiles **PASS** (199 étoiles, 198 appariements,
  0,0551 px à la vraie matrice, 1,4977 px pour 1,5 px ; volet « phase seule » :
  AVANT accepte à 0,10 px, APRÈS refuse).
- **Mesure 2 — DÉCISIVE (jeu d'Alain `SV555\SH2-132\240.00`)** : Ha 55 · OIII 71 ·
  SII 80 à 240 s, 4-5 nuits, dark 240 s → **204 frames** (S2 79 · Ha 54 · O3 71),
  **0 refus** dans les deux branches, **31 retournements** (S2 24 · O3 7) tous
  retournés. La phase était le chemin **FINAL de 22 frames** :
  · **Ha 21 frames** : résidu médian **0,857 px** (max 1,071) — translation fausse
    de 1,1 à 2,3 px acceptée telle quelle ; sans phase (ORB étoffé) **0,065 px**.
    La couche Ha = canal VERT du SHO ⇒ flou réel dans l'image livrée ;
  · **O3 1 frame empilée À L'ENVERS** : phase angle 0 avec **0 appariement**
    contre |angle| **173,4°** et **4 435 px** d'écart ⇒ le défaut du ⑩, reproduit.
- **Livré** : `PHASE_EN_NARROWBAND = False` et `repli_phase_session()` qui lit
  L'UNE OU L'AUTRE constante (①/③, un seul endroit décide, les deux restent
  basculables). Cascade, verrou à deux conditions et aligneurs Ha de la VOIE A
  INCHANGÉS. Banc neuf **135** (7 volets) vert ; banc **132** mis à jour (son
  volet [1] datait d'avant ③) ; non-régression 13/15/21/116/117/129b/131/132/133/
  134 verte.
- **Outils hors dépôt** : `_mesure_156_phase_narrowband.py` (`--controle`,
  `--jeu`, `--tag`, `--max`), preuves `_156_*` et `_156b_*` (3 jeux) +
  `_156c_*` (Sh2-132). Détail durable : `CLAUDE.md` § « Étape ③ du plan ⑪ ».
- **DÉCISION D'ALAIN** : ③ retenu et livré ; **reste la validation en réel** sur
  son run SHO de Sh2-132 (le jeu qui contient les retournements).

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
- **Code** : **v2.84.0** (③, jalon 135) — bancs 135 neuf + non-régression verte ;
  **validation réelle Sh2-132 à faire par Alain**.
- **RUN RÉEL LRGB (Alain, 18/10)** : plus aucune tache bleue NI rouge ⇒ `phase`
  en broadband était la seule cause. Astrométrie réussie (garde 133).
- **Reste à faire** : **valider ③ en réel** (run SHO de Sh2-132 : 31
  retournements, 22 frames que la phase finalisait à tort).
- **Combine** innocenté trois fois (140/142/143) : `_ratio_combine` intact.

### Fichiers modifiés dans cette phase (v2.84.0)
- `avastack/processing/alignment.py` (`PHASE_EN_NARROWBAND`, `repli_phase_session`
  par mode, docstrings), `avastack/core/worker.py` (commentaires ③ ; aligneurs
  Ha de la VOIE A explicitement hors périmètre), `avastack/__init__.py`
  (**v2.84.0** + changelog), `bancs/_test_phase_narrowband_jalon135.py` (NEUF,
  7 volets), `bancs/_test_phase_broadband_jalon132.py` (volet [1] mis à jour),
  `CLAUDE.md` et `AVANCEMENT.md`. Rappel v2.83.0 : `4dd335b`.

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
1. **③ — LIVRÉE (v2.84.0), VALIDATION RÉELLE à faire** : run SHO sur
   `SV555\SH2-132\240.00` (dossiers `Ha` · `OIII` · `SII`, dark maître 240 s,
   composition **SHO**), avec `AVASTACK_TRACE_ROLES=<dossier>` pour compter les
   méthodes. À vérifier : **0 refus** par rôle, **retournements corrects**, plus
   aucune méthode « phase », et un canal Ha **net** (les 21 frames que la phase
   finalisait étaient à ~0,86 px de résidu). Si le rendu régresse : la constante
   `PHASE_EN_NARROWBAND` suffit à revenir en arrière (banc 135 le prouve).
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
Arbre propre, **v2.84.0** : étapes ① (v2.82.2), ② choix C (v2.83.0, validée en
réel) et **③ LIVRÉE (jalon 135)** — `PHASE_EN_NARROWBAND = False`, bancs 135 neuf
et non-régression verte. Mesure décisive : sur **Sh2-132** (204 frames, 31
retournements), la phase finalisait **22 frames** à tort — 21 Ha à **0,857 px**
de résidu (au lieu de 0,065) et **1 O3 empilée à l'envers** (|angle| 173,4°).
Prochaine action unique : **validation réelle par Alain** d'un run SHO de Sh2-132
(0 refus, retournements corrects, aucune méthode « phase », canal Ha net) — pas
de nouvelle modification de code avant ce verdict.

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
- **Décisions d'Alain** : **② TRANCHÉ (C), LIVRÉ et VALIDÉ en réel** (v2.83.0) ;
  **③ TRANCHÉ (retirer `phase` en narrowband), LIVRÉ en v2.84.0** — attend sa
  **validation réelle** sur Sh2-132 ; restent l'interface 141 (A/B/C), SPCC et
  VeraLux. Une release GitHub ne se fera QUE sur accord explicite.
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

- **Un jeu SANS le défaut ne mesure que l'ABSENCE DE COÛT** : 109 frames
  narrowband sans aucun retournement donnaient « retirer `phase` ne change rien » ;
  sur **Sh2-132** (204 frames, **31 retournements**), la phase finalisait
  **22 frames** — 21 Ha **fausses de 1,1 à 2,3 px** (résidu 0,857 px au lieu de
  0,065) et **1 O3 À L'ENVERS** (0 appariement, |angle| 173,4°). Avant de conclure
  « aucun coût », vérifier que le défaut est REPRÉSENTÉ dans le jeu (compter les
  |angle| > 170° ET les méthodes retenues, pas seulement les refus).
- **Mesure A/B d'un interrupteur** : deux `StarAligner` au code inchangé, même
  référence, même ordre, même calibration ; seule la valeur testée diffère.
  Une mesure qui rejoue une seule branche ne dit rien du delta.

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
