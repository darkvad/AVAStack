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

Versions : `LRGBHa` = **v2.90.0** (①/②/③ validés en réel ; **136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum **VALIDÉ EN RÉEL le 19/10**, **J3** cinq modes puis
**J3bis option A LIVRÉ** — verdict réel attendu) · `master` publié = **v2.80.0** ·
Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 — J3bis LIVRÉ (v2.90.0), test réel attendu

### État actuel
- **Code** : **v2.90.0** sur `LRGBHa` — **J2 VALIDÉ EN RÉEL** (19/10, inchangé,
  **AU BIT**) et **J3bis IMPLÉMENTÉ** (option A : les quatre modes J3 vivent dans
  l'espace de R, `ha_luminance` devient MULTIPLICATIVE). Bancs J2 et J3 verts,
  non-régressions 129/130/136/137/141 + garde-fou vertes, aucune erreur pyright
  dans `composition.py` ; **aucune release sans accord**.
- **Ce qui reste** : le **test réel de J3bis à l'écran** (Alain), puis **J4**
  (continuum médiane / étoiles 5σ, case « recentrer ») et **J5** (ancre + doc).

### Verdict réel de J2 (consigné)
- **AVEC continuum** : réglage de force visible, rendu retenu. **SANS** : les
  rouges « s'éteignent un peu » ⇒ le continuum non soustrait se voit ; ne pas
  le prendre pour un défaut du Ha.
- **Q retenu : 0,80** (défaut) · **poids poussé à 1,5 SUR CETTE CIBLE** (M33) :
  réglage **PAR CIBLE**, le défaut reste **1,0**. Aucun défaut bloquant signalé.
- **Verdict global : VALIDÉ.**

### Verdict réel de J3 (19/10, M33, SPCC) — **À REPRENDRE (traité par J3bis)**
- `fondu` : image **BLEUIE** (α restait grisé — corrigé en v2.89.1), Ha
  invisible dans les zones rouges, zones Ha blanches/bleu très clair.
- `ecran` : zones Ha **CYAN**. `eclaircir` : zones Ha à peine rosées et **force
  SANS EFFET** (identique à 0 et à 3) — INERTE. `ha_luminance` : plus lumineux
  mais **plus blanc**.
- Avec les gains Gaia au lieu de SPCC, le rouge ressort ⇒ **le niveau de R
  commande tout**.

### MESURE FAITE le 19/10 (couches M33 réelles) — CAUSE CHIFFRÉE

Outil : `bancs/_diag_fusion_ha_echelles.py --canaux C:\Astro\test\M33_Canaux_LRGBHa
--norm-commune --lissage-halos --poids 1.5` (réglages lus dans `AVACOMPO` :
**normalisation COMMUNE + lissage combine 117d**).

| grandeur | norm. commune ON (session réelle) | norm. commune OFF |
|---|---|---|
| R composite p50 / p99,7 | **2,86 / 5,71** | 0,019 / 0,755 |
| **R > 1** | **100 %** des pixels | 0,23 % |
| s (Ha) p99,7 | 0,711 | 0,711 |
| amplitude R/s | **4,19** | **1,06** |
| plancher du fond R / s | 2,853 / 0 | 0,0171 / 0 |
| `fondu` Δ fond / Δ cœur Ha | −1,43 / −1,99 | −0,0085 / −0,027 |
| `ecran` Δ cœur Ha | **−1,51** (soustrait) | +0,19 (ajoute) |
| `eclaircir` pixels qui montent | **0 %** (inerte) | 41 % |
| `ha_luminance` Δ cœur Ha | +0,44 sur R, G **et** B | idem |

- **La cause n°1 est la NORMALISATION COMMUNE** : elle laisse le composite
  AU-DESSUS de 1 (×2,9 à ×5,7 ; le combine L y rajoute ×2,4), alors que `s` est
  écrêté dans [0 ; 1]. Les opérateurs avaient été écrits pour R ∈ [0 ; 1] :
  `1 − R < 0` PARTOUT (écran = soustracteur), `max(0, s − R) = 0` PARTOUT
  (éclaircir strictement inerte, donc le poids ne multiplie que zéro), et
  `fondu` retire α·R ≈ 1,43 = **la moitié du rouge du fond** (⇒ bleu), puis
  −45 % dans le cœur Ha (⇒ Ha invisible).
- **La cause n°2 est le NIVEAU** : même SANS normalisation commune, `s` a un
  plancher 0 (recentrage) et `R` un plancher de 0,0171 (2,3 % de son
  amplitude) ⇒ fondu assombrit encore le fond ; `R > s` sur 56 % des pixels Ha
  ⇒ éclaircir n'agit que sur ~41-44 %.
- **Amplitudes** : elles SONT appariées (1,06) quand la normalisation par rôle
  est active (chaque rôle vaut ≈ 1) ; c'est la normalisation COMMUNE qui les
  sépare (4,19). L'intuition « échelles non appariées » était donc juste POUR
  CETTE SESSION, et fausse comme explication générale.
- **Sonde (mesure hors appli, alors NON implémentée)** : c'est elle qui a chiffré
  les quatre défauts ; depuis, le **code livré rejoue sur les mêmes couches** (voir
  le tableau du § « J3bis — LIVRÉ ») avec les mêmes conclusions.
- **Piste RETENUE (Alain, 19/10) : (A)** — exprimer les opérateurs dans l'espace
  de R ; **(B)** (neutraliser si `R ∉ [0 ; 1]`) et **(C)** (borner seulement) sont
  **ÉCARTÉES**. **Ne pas toucher au J2.**

### Fichiers modifiés dans cette phase (J3bis, v2.90.0)
- `avastack/processing/composition.py` : **`_reperes_fusion_ha`** (fond_R, A_R,
  p99,7(s) sur sous-échantillon 512×512) ; les quatre opérateurs réécrits dans
  l'espace de R ; **`ajout_rouge` isolé en tête de bloc, AU BIT** ; docstrings
  (module + fonction) réécrites.
- `avastack/__init__.py` : **2.90.0** + changelog du jalon.
- `bancs/_test_fusion_ha_jalon3.py` : volets [2], [2b], [4] et [5] recalés sur
  les nouvelles formules, + **volet [5b] « composite HORS [0 ; 1] »** ; la
  référence (`mode_espace_r`, `luminance_attendue`) est écrite **à part de
  l'appli** pour ne pas se contenter de la recopier.
- `CLAUDE.md` (§ J3/J3bis) et `AVANCEMENT.md`.
- **Inchangés (exigence)** : `ajout_rouge`, continuum, α, poids, interface,
  fiche de rendu, clé de mémoïsation, `bancs/_diag_fusion_ha_echelles.py`.

### Décisions prises
- **J3bis = option A, implémentée telle que la spec** (espace de R, pas de
  neutralisation ni de simple bornage : B et C restent écartées par Alain).
- **`ajout_rouge` ne passe PAS par l'espace de R** : il est purement ADDITIF
  et validé en réel ; le banc J2 le prouve AU BIT.
- **Luminance MULTIPLICATIVE** (`rgb × (1 + poids·s̃)`, facteur borné à 0) : le
  même facteur sur les trois canaux supprime le blanchiment par construction.
- **Repères hors de la clé de mémoïsation** : ils dérivent du composite et du
  signal, jamais d'un réglage.
- **Le banc [5b] exige les quatre propriétés qui manquaient** : fond immobile,
  écran/éclaircir qui ne baissent JAMAIS, éclaircir qui agit ET suit le poids,
  luminance qui garde les rapports R/G/B.

### J3bis — LIVRÉ (v2.90.0) : ce qui a été fait

Dans `fusionner_ha` (`composition.py`), un helper `_reperes_fusion_ha` mesure sur
le COMPOSITE : `fond_R` (médiane de `R` sur le fond, `s` ≤ sa médiane), `A_R`
(p99,7(`R`) − fond_R) et `p99,7(s)` — sur un sous-échantillon 512×512, donc à
coût constant même en 16 Mpx. Les quatre modes travaillent ensuite dans
l'espace « 0 au fond du ciel, ≈ 1 au p99,7 » :

| mode | opérateur, dans l'espace de R |
|---|---|
| `fondu_rouge` | `R̃' = R̃ + α·(s̃ − R̃)` |
| `ecran_rouge` | `R̃' = R̃ + s̃·max(0, 1 − min(R̃, 1))` |
| `eclaircir_rouge` | `R̃' = R̃ + max(0, s̃ − R̃)` |
| `ha_luminance` | `rgb' = rgb × (1 + poids·s̃)` — aucun retour d'échelle |

Retour des trois modes « rouge » : `R' = max(0, fond_R + A_R·R̃')`, puis
`sortie = composite + poids × (R' − composite)` : le poids interpole dans
l'espace du COMPOSITE, et **poids 0 reste le composite du J1 AU BIT**.

**Rejeu du CODE LIVRÉ sur les couches M33 réelles** (§ des 5 `canal_*.fit`,
normalisation COMMUNE + lissage 117d, poids 1 ; Δ **médian** du rouge par zone) :

| mode | fond | Ha large | cœur Ha | pixels en baisse |
|---|---|---|---|---|
| `ajout_rouge` (J2) | +0,000 | +0,063 | +0,443 | 0 % |
| `fondu_rouge` α 0,5 | −0,000 | +0,037 | +0,020 | 38 % (là où R > Ha) |
| `ecran_rouge` | +0,000 | +0,221 | +0,659 | **0 %** |
| `eclaircir_rouge` | +0,000 | +0,075 | +0,040 | **0 %** |
| `ha_luminance` | +0,000 | +0,270 | +2,771 (×1,62) | 0 % |

`ha_luminance` préserve les rapports R/G/B à **5e-7** (bruit d'arrondi) : plus
de blanchiment. Les 38 % de baisse du `fondu` sont les structures LARGES où le
continuum R dépasse le Ha — c'est son objet (remplacer), pas le fond.

Garde-fous : `A_R` ou `p99,7(s)` ≈ 0 ⇒ **aucun ajout** (jamais d'exception, pas
de division par ~0) ; facteur de luminance borné à 0 (un facteur négatif
inverserait les couleurs) ; rouge jamais négatif. `ajout_rouge` est **inchangé,
au bit**, et n'entre JAMAIS dans cet espace. Contrôle de l'outil de mesure :
`python bancs/_diag_fusion_ha_echelles.py --autotest`.

### Prochaines étapes
1. **Test réel J3bis** par Alain sur M33 (`C:\Astro\test\M33_Canaux_LRGBHa`,
   mêmes réglages : LRGB+Ha, normalisation COMMUNE, lissage 117d, poids 1,5) :
   les quatre modes + α. À juger : le Ha reste-t-il ROUGE, le fond immobile,
   `eclaircir` sensible au poids, la luminance sans blanchiment ?
2. Si validé : **J4** (continuum médiane / étoiles 5σ, case « recentrer »), puis
   **J5** (ancre + doc).
3. **Release seulement sur accord explicite d'Alain**, jamais avant le test.

---

## HISTORIQUE — 18/10/2026 (détail : changelog v2.86.0 / v2.87.0 / v2.88.0 + git log)

①/②/③, 136 et 137 livrés et validés ; 141-B livrée ; J2 livré (validé le 19/10).
TRANCHÉ, **ne pas rouvrir** : combine LRGB innocenté (140/142/143) · `phase`
écartée en broadband ET narrowband · VeraLux CLOS (122/123/124) · 141 = B.
Astrométrie RÉSOLUE (AD/Dec de M31 saisies sur des brutes M33) — `CLAUDE.md`.
Teinte des COINS = DÉGRADÉ mesuré, sans action (voir « Problèmes ouverts »).

### Problèmes ouverts
- **Aucun bloquant** sur ①/②/③/136/137/141-B/J2/J3bis : livrés, mesurés, bancs
  verts. Reste à juger À L'ÉCRAN : le rendu des quatre modes J3bis (Alain).
- En attente d'une décision : **teinte des COINS ±15-20 %** (dégradé) — GraXpert/
  ABE ou estimateur par région, à trancher ; mesurée, non traitée.

### Points d'attention
- **TROIS noms de composition** (141-B) : `stacker.composition`/`_compo_nom` (ce
  que la SOURCE empile, source de `AVACOMPO`), `_compo_session` (armée au
  « ▶ Démarrer »), `var_compo` (le MENU). Le bandeau ne compare que les deux
  derniers. **`"RGB+Ha"` est une sous-chaîne de `"LRGB+Ha"`** : jamais
  `startswith`/`in` pour identifier une composition écrite.
- **J2 — la fusion est ACTIVE PAR DÉFAUT** : `CompositeStacker.fusion_ha = None`
  ne veut PAS dire « rien », mais « défauts figés » (ajout_rouge, poids 1,0).
  Pour désactiver : `{"poids": 0.0}`. Le réglage entre dans la CLÉ de
  mémoïsation (sinon bouger le poids ne réafficherait rien) et dans le 9e
  élément de `disp.vl_compo` (déballage tolérant : un ancien 9e élément
  booléen est ignoré) ; la fiche ne le déclare que si une couche Ha a des
  frames.
- **J2 — CONTINUUM** : actif par défaut, **case ET Q désactivés sans dossier
  R** (le réglage effectif est alors forcé à False) ; l'échelle qui ramène R
  dans l'espace du Ha est le DÉNOMINATEUR de normalisation du Ha — ne pas le
  remplacer par 1 sans regarder le mode de normalisation. La méthode est
  `bandes_passantes` ; les deux autres (médiane, étoiles 5σ) restent au J4.
- **J3 — α n'agit QUE sur `fondu_rouge`** : le champ est désactivé ailleurs mais
  TOUJOURS lu/persisté (`fusion_ha_alpha`), et α entre dans la CLÉ de
  mémoïsation (sinon le réglage paraît « sans effet »).
- **J3bis — `ha_luminance` est MULTIPLICATIVE** (`rgb × (1 + poids·s̃)`) : elle
  touche V et B (c'est son objet) et c'est ce qui préserve la couleur. Les
  quatre autres modes laissent V et B **AU BIT**.
- **J3bis — l'aller-retour par `R̃` coûte quelques ulp** : ne JAMAIS exiger
  l'égalité AU BIT sur les quatre modes (seul `ajout_rouge` l'est, et c'est
  volontaire). Les comparer à la référence avec `atol`/`rtol` ≈ 1e-6.
- **J3bis — un banc où le Ha pointe AU MÊME ENDROIT que le maximum de R rend
  `eclaircir` inerte** (`R̃ ≈ s̃` au cœur) : c'est un artefact de la scène, pas
  du code. La scène doit avoir un continuum LARGE et un Ha COMPACT et décalé
  (piège rencontré en écrivant le volet [5b]).
- **J3 — comparer les TROIS canaux** : `ajout_rouge` (additif sur R) et
  `ha_luminance` (multiplicatif sur les trois) n'agissent pas au même endroit ;
  un banc qui ne lit que R se trompe de diagnostic.
- **J3 — un banc d'INTERFACE doit rejouer le CHEMIN RÉEL** (la commande du
  widget) : le 19/10, le champ α restait grisé en vrai alors que le banc était
  vert, parce qu'il appelait `_maj_fusion_ha()` lui-même au lieu de
  `_on_fusion_ha` (la commande de la Combobox). Corrigé en v2.89.1.
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

### Contexte de reprise (à coller — 2 phrases)
Arbre **v2.90.0** sur `LRGBHa` : **J2 validé en réel** (inchangé, AU BIT) et
**J3bis implémenté** — les quatre modes J3 vivent dans l'espace de R (`R̃`/`s̃`,
`ha_luminance` multiplicative), bancs J2/J3 et non-régressions verts. Prochaine
action unique : **le test réel de J3bis à l'écran par Alain** (M33,
`C:\Astro\test\M33_Canaux_LRGBHa`) — ensuite J4/J5, aucune release sans accord.

---

## Chantier en cours — LRGB+Ha (jalons 129 → J5) — J2 validé, J3bis livré

Le rôle Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le combine L.

| Jalon | Contenu | État |
|---|---|---|
| J1 / 129 (v2.81.0) | compositions + 5 lignes UI + séparation ancre / `_narrowband_ha` | commité |
| 129b | voie A (référence **PAR RÔLE** + recalage de l'empilement) + `profondeur_min` + refus par rôle | COMMITÉ ; validé en réel le 16/10 (441 frames, 2 refus en R) |
| **130 (v2.82.0)** | combine LRGB borné [0 ; 5] + repli local + fiche + banc neuf | COMMITÉ + POUSSÉ (`ef0c35c`) |
| **J2 (v2.88.0)** | fusion « ajout au rouge » + poids 1,0 + recentrage + **continuum (Q, case)** + cadre « Fusion Ha » | **VALIDÉ EN RÉEL le 19/10** |
| **J3 (v2.89.0)** | `fondu_rouge` (α), `ecran_rouge`, `eclaircir_rouge`, `ha_luminance` + poids = force globale | LIVRÉ — **verdict réel 19/10 : à reprendre** (fondu bleui, écran cyan, éclaircir inerte) |
| **J3bis (v2.90.0)** | les 4 opérateurs dans l'espace de R + `ha_luminance` multiplicative ; `ajout_rouge` au bit | **LIVRÉ — test réel attendu** |
| J4 → J5 | continuum méthodes **médiane / étoiles 5σ** (+ case recentrer) ; ancre réelle + doc | à faire |

Plan figé (13 arbitrages du 15/10) : poids **1,0** (0–10) · α **0,5** · Q **0,80**
(0,10–2,00) · cadre « Fusion Ha » visible seulement si la compo contient Ha ·
continuum = **bandes passantes** (Ha 7 nm / RGB 100 nm), référence **R** ·
identifiants en français (`synthetise`).

---

## En attente / prochaine session (état au 19/10 — `LRGBHa`, v2.90.0)

- **Prochaine action unique** : **test réel de J3bis par Alain** — les quatre
  modes + α sur M33 (réglages de la session : LRGB+Ha, normalisation COMMUNE,
  lissage 117d, poids 1,5). Ensuite seulement : **J4** (continuum médiane /
  étoiles 5σ) et **J5** (ancre + doc).
- **Référence chiffrée** : `C:\Astro\test\M33_Canaux_LRGBHa` (5 `canal_*.fit` +
  fiches ; `AVACOMPO` = LRGB+Ha, **normalisation COMMUNE**, lissage 117d).
  Rejouer : `python bancs/_diag_fusion_ha_echelles.py --canaux <dossier>
  --norm-commune --lissage-halos --poids 1.5` (`--autotest` contrôle l'outil).
- **J2 reste VALIDÉ** (Q 0,80 ; poids 1,5 sur M33 = réglage PAR CIBLE ; défaut
  1,0) : ne pas le retoucher — J3bis doit le laisser **AU BIT**.
- **141-B validée** (rien à retester) ; **teinte des COINS** notée, sans action.
- **Aucune release** sans accord explicite, et **pas avant le test réel de J3bis**.
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

- **141-B — les noms de composition se CONTIENNENT** : `"RGB+Ha"` est une
  sous-chaîne de `"LRGB+Ha"` ⇒ jamais `startswith`/`in` pour prouver ce qui est
  écrit ; lire `AVACOMPO` en coupant à la virgule (`split(",")[0].strip()`).
  Et armer une session sans avoir posé le menu crée un écart LÉGITIME (défaut du
  menu = HOO) : poser le menu avant `_armer_compo_session()`.
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

- **19/10/2026** : J2 validé en réel (Q 0,80 ; poids 1,5 sur M33, par cible) ;
  J3 livré (v2.89.0) puis **remplacé par J3bis** (v2.90.0, option A).
- **18/10/2026** : 141-B (v2.87.0) et J2 (v2.88.0) livrés ; ①/②/③, 136 et 137
  validés en réel.
