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

Versions : `LRGBHa` = **v2.90.2** (①/②/③ validés en réel ; **136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum **VALIDÉ EN RÉEL le 19/10**, **J3** cinq modes,
**J3bis** validé en réel sauf `ha_luminance`, réécrite **à porte** en v2.90.2) ·
`master` publié = **v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 — **J2 et J3 VALIDÉS en réel** (v2.90.2, `LRGBHa`)

### État actuel
- **Code** : **v2.90.2** sur `LRGBHa`. **J2 VALIDÉ EN RÉEL** (ajout au rouge +
  continuum, inchangé, **AU BIT**). **J3 VALIDÉ EN RÉEL** : `fondu`, `ecran` et
  `eclaircir` sont OK (« bien mieux voire OK ») ; `ha_luminance` a été reprise
  deux fois (blanchiment mesuré → objet seul → **gain à porte**, retenu sur
  aperçus) et est livrée ainsi en v2.90.2.
- **Bancs** : J2 vert AU BIT, J3 vert (9 volets), non-régressions
  129/129b/130/136/137/141 + garde-fou vertes, `ruff`/`pyright` sans nouvelle
  erreur. **Aucune release sans accord d'Alain.**
- **Suite du chantier** : **J4** = continuum méthodes médiane / étoiles 5σ
  (+ case « recentrer »), puis **J5** = ancre réelle + doc.

### Verdict réel de J2 (consigné)
- **AVEC continuum** : réglage de force visible, rendu retenu. **SANS** : les
  rouges « s'éteignent un peu » ⇒ le continuum non soustrait se voit ; ne pas
  le prendre pour un défaut du Ha.
- **Q retenu : 0,80** (défaut) · **poids poussé à 1,5 SUR CETTE CIBLE** (M33) :
  réglage **PAR CIBLE**, le défaut reste **1,0**. Aucun défaut bloquant signalé.
- **Verdict global : VALIDÉ.**

### Pourquoi le J3 avait échoué (MESURÉ, 19/10, couches M33) — corrigé par J3bis
- En normalisation COMMUNE le rouge du composite vit entre **2,86 et 5,71**
  alors que `s` est écrêté dans [0 ; 1] : `1 − R < 0` (écran soustracteur),
  `max(0, s − R) = 0` (éclaircir inerte), et le fond perdait la moitié de son
  rouge. Détail : `CLAUDE.md` § « Verdict réel du J3 », changelog v2.90.0 ;
  contrôle de l'outil : `python bancs/_diag_fusion_ha_echelles.py --autotest`.

### Fichiers modifiés dans cette phase (J3bis v2.90.0, puis v2.90.1)
- `avastack/processing/composition.py` : **`_reperes_fusion_ha`** (fond_R, A_R,
  p99,7(s) sur sous-échantillon 512×512) ; les quatre opérateurs réécrits dans
  l'espace de R ; **`ajout_rouge` isolé en tête de bloc, AU BIT** ;
  `ha_luminance` = gain à porte sur le rouge (v2.90.2) ; docstrings réécrites.
- `avastack/ui/panels/compo.py` : aide du cadre « Fusion Ha » corrigée (elle
  annonçait « le Ha éclaire les TROIS canaux »).
- `avastack/__init__.py` : **2.90.1** + changelogs 2.90.0 et 2.90.1.
- `bancs/_test_fusion_ha_jalon3.py` : volets [2], [2b], [4] et [5] recalés sur
  les nouvelles formules, + **volet [5b] « composite HORS [0 ; 1] »** ; la
  référence (`mode_espace_r`) est écrite **à part de l'appli** pour ne pas se
  contenter de la recopier.
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
| `ha_luminance` | `R' = R × (1 + s̃·porte)`, `porte = rampe(s̃ ; 0,05 → 0,25)` |

Retour, commun aux QUATRE modes : `R' = max(0, fond_R + A_R·R̃')`, puis
`sortie = composite + poids × (R' − composite)` : le poids interpole dans
l'espace du COMPOSITE, et **poids 0 reste le composite du J1 AU BIT**.
Les CINQ modes ne touchent que le rouge : **V et B sont toujours au bit**.

**Rejeu du CODE LIVRÉ sur les couches M33 réelles** (§ des 5 `canal_*.fit`,
normalisation COMMUNE + lissage 117d, poids 1 ; Δ **médian** du rouge par zone) :

| mode | fond | Ha large | cœur Ha | pixels en baisse |
|---|---|---|---|---|
| `ajout_rouge` (J2) | +0,000 | +0,063 | +0,443 | 0 % |
| `fondu_rouge` α 0,5 | −0,000 | +0,037 | +0,020 | 38 % (là où R > Ha) |
| `ecran_rouge` | +0,000 | +0,221 | +0,659 | **0 %** |
| `eclaircir_rouge` | +0,000 | +0,075 | +0,040 | **0 %** |
| `ha_luminance` (v2.90.2) | **+0,000** | +0,037 (p90 0,665) | +2,77 | 0 % |

`ha_luminance` à porte : **bande DIFFUSE 0 % touchée**, **89,6 % des pixels sont
sous la porte ⇒ rouge AU BIT**, V/B au bit ; bande Ha **+0,037 médian / +0,665
au p90** (contre +0,016 / +0,135 pour un gain limité à l'objet, v2.90.1), cœur
+2,77. Les 38 % de baisse du `fondu` sont les structures LARGES où le continuum
R dépasse le Ha — c'est son objet (remplacer), pas le fond.

Garde-fous : `A_R` ou `p99,7(s)` ≈ 0 ⇒ **aucun ajout** (jamais d'exception, pas
de division par ~0) ; rouge jamais négatif. `ajout_rouge` est **inchangé, au
bit**, et n'entre JAMAIS dans cet espace. Contrôle de l'outil de mesure :
`python bancs/_diag_fusion_ha_echelles.py --autotest`.

### Verdict réel de J3 (Alain, 19/10) — **VALIDÉ** ; `ha_luminance` reprise 2 fois
- `fondu`, `ecran`, `eclaircir` : **« bien mieux voire OK »** (validés).
- `ha_luminance` **blanchissait** → **CAUSE MESURÉE** (code livré + **étirement
  d'affichage réel** : stats sur l'image, `sigma_k` 2,8, cible 0,25, fond
  neutralisé par canal) : le facteur `1 + s̃` multipliait **aussi le CIEL de G
  et B**, qui ne portent aucun Ha. Zone Ha large : saturation **0,19 → 0,12**
  (−37 %) pendant que la luminance montait (0,48 → 0,55).
- **ÉTAPES RÉELLES** : v2.90.1 = « V9 objet seul » (plus de blanchiment, mais
  bande Ha **+0,016** seulement) → **v2.90.2 = PORTE douce 0,05–0,25, RETENUE
  par Alain sur aperçus** : `R' = R × (1 + p·s̃·porte)`. Sous la porte
  (**89,6 % des pixels**) le rouge est **AU BIT** ; bande **DIFFUSE 0 %**
  touchée ; bande Ha **+0,037 médian / +0,665 p90** ; V/B au bit.
- Portes mesurées et ÉCARTÉES : 0,02–0,12 (bande Ha +0,148 mais +0,041 dans le
  halo), 0,20–0,50 (trop fermée, 12 % de la bande), et « facteur sur les trois
  canaux » (blanchit). Aperçus : `C:\Astro\test\_j3bis_luminance\` —
  `C_PORTE_douce` = la version livrée.

### Prochaines étapes
1. **J4** — continuum : méthodes **médiane** et **étoiles 5σ** (+ case
   « recentrer »), puis **J5** (ancre réelle + doc). Aucun autre chantier ouvert.
2. **Release seulement sur accord explicite d'Alain**, jamais avant.
   **J5** (ancre + doc).
3. **Release seulement sur accord explicite d'Alain**, jamais avant.

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
- **J3bis — les CINQ modes ne touchent que le ROUGE** : V et B sont toujours
  AU BIT (la v2.90.1 a retiré la seule exception, `ha_luminance`).
- **`ha_luminance` = gain À PORTE sur le rouge** : `R' = R × (1 + p·s̃·porte)`,
  `porte = clip((s̃ − 0,05)/0,20 ; 0 ; 1)`. Sous la porte, **rouge AU BIT**
  (89,6 % des pixels) : le bruit du ciel reste du bruit. Multiplier `R` SANS
  porte y verse ce bruit rouge (piste « V9 ») ; ne multiplier que l'objet
  au-dessus du fond ne montre presque rien (v2.90.1) ; multiplier les trois
  canaux blanchit (saturation 0,19 → 0,12). **Ne pas baisser la porte sous 0,05
  sans refaire la mesure** (0,02–0,12 versait +0,041 dans le halo).
- **`ajout_rouge` et `ha_luminance` ne se distinguent pas sur un pixel isolé** :
  l'un ajoute `s` (constant), l'autre multiplie le rouge par `1 + s̃·porte` (le
  gain suit le signal). Comparer une ZONE, pas une valeur — c'est le volet [5b].
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
Arbre **v2.90.2** sur `LRGBHa` : **J2 et J3 VALIDÉS en réel** (19/10) — les cinq
modes de fusion du Ha vivent dans l'espace de R, `ha_luminance` est un gain **à
porte** (0,05–0,25), `ajout_rouge` reste AU BIT ; bancs J2/J3 et non-régressions
verts, **aucune release faite**. Prochaine action : demander à Alain s'il ouvre
**J4** (continuum médiane / étoiles 5σ + case « recentrer »), puis J5 (ancre + doc).

---

## Chantier en cours — LRGB+Ha (jalons 129 → J5) — **J2 et J3 VALIDÉS**

Le rôle Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le combine L.

| Jalon | Contenu | État |
|---|---|---|
| J1 / 129 (v2.81.0) | compositions + 5 lignes UI + séparation ancre / `_narrowband_ha` | commité |
| 129b | voie A (référence **PAR RÔLE** + recalage de l'empilement) + `profondeur_min` + refus par rôle | COMMITÉ ; validé en réel le 16/10 (441 frames, 2 refus en R) |
| **130 (v2.82.0)** | combine LRGB borné [0 ; 5] + repli local + fiche + banc neuf | COMMITÉ + POUSSÉ (`ef0c35c`) |
| **J2 (v2.88.0)** | fusion « ajout au rouge » + poids 1,0 + recentrage + **continuum (Q, case)** + cadre « Fusion Ha » | **VALIDÉ EN RÉEL le 19/10** |
| **J3 (v2.89.0)** | `fondu_rouge` (α), `ecran_rouge`, `eclaircir_rouge`, `ha_luminance` + poids = force globale | LIVRÉ — **verdict réel 19/10 : à reprendre** (fondu bleui, écran cyan, éclaircir inerte) |
| **J3bis (v2.90.2)** | les 4 opérateurs dans l'espace de R ; `ha_luminance` = gain **à porte** (0,05–0,25) ; `ajout_rouge` au bit | **VALIDÉ EN RÉEL (19/10)** |
| J4 → J5 | continuum méthodes **médiane / étoiles 5σ** (+ case recentrer) ; ancre réelle + doc | à faire |

Plan figé (13 arbitrages du 15/10) : poids **1,0** (0–10) · α **0,5** · Q **0,80**
(0,10–2,00) · cadre « Fusion Ha » visible seulement si la compo contient Ha ·
continuum = **bandes passantes** (Ha 7 nm / RGB 100 nm), référence **R** ·
identifiants en français (`synthetise`).

---

## En attente / prochaine session (état au 19/10 — `LRGBHa`, v2.90.2)

- **J2 et J3 sont CLOS** (validés en réel le 19/10). Les cinq modes sont livrés :
  `ajout_rouge` (J2, au bit), `fondu_rouge` (α), `ecran_rouge`, `eclaircir_rouge`,
  `ha_luminance` à porte.
- **Prochaine action unique** : **demander à Alain s'il ouvre J4** (continuum
  méthodes médiane / étoiles 5σ + case « recentrer ») — ne pas le démarrer de
  soi-même. Ensuite **J5** (ancre réelle + doc).
- **Référence chiffrée** : `C:\Astro\test\M33_Canaux_LRGBHa` (5 `canal_*.fit` +
  fiches ; `AVACOMPO` = LRGB+Ha, **normalisation COMMUNE**, lissage 117d).
  Rejouer : `python bancs/_diag_fusion_ha_echelles.py --canaux <dossier>
  --norm-commune --lissage-halos --poids 1.5` (`--autotest` contrôle l'outil).
- **Ne pas retoucher** : `ajout_rouge` (AU BIT), le continuum, α, le poids,
  l'interface, la fiche, la clé de mémoïsation.
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

- **19/10/2026** : **J2 et J3 VALIDÉS en réel**. J2 (v2.88.0) : Q 0,80, poids
  1,5 sur M33 (par cible) ; J3/J3bis : cinq modes, `ha_luminance` reprise deux
  fois (v2.90.1 « objet seul », **v2.90.2 « porte 0,05–0,25 »**) — branche
  `LRGBHa`, v2.90.2 poussée.
- **18/10/2026** : 141-B (v2.87.0) et J2 (v2.88.0) livrés ; ①/②/③, 136 et 137
  validés en réel.
