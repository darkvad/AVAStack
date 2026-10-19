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

Versions : `LRGBHa` = **v2.89.1** (①/②/③ validés en réel ; **136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum **VALIDÉ EN RÉEL le 19/10**, **J3** cinq modes
**MESURÉ puis remplacé par J3bis option A**) · `master` publié = **v2.80.0** ·
Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 — J2 VALIDÉ, J3 MESURÉ, J3bis = OPTION A CHOISIE

### État actuel
- **Code** : **v2.89.1** sur `LRGBHa` — **J2 VALIDÉ EN RÉEL** par Alain (19/10) ;
  **J3 LIVRÉ mais À REPRENDRE**, sa cause est désormais **MESURÉE** (tableau plus
  bas) et **Alain a choisi l'option A** pour J3bis (opérateurs exprimés dans
  l'espace de R + luminance multiplicative). Bancs J2/J3 verts, non-régressions
  vertes, garde-fou vert, pyright 0 ; **aucune release sans accord**.
  **AUCUN code d'application n'a été touché par la mesure** : seuls l'outil
  `bancs/_diag_fusion_ha_echelles.py` et les deux fichiers de mémoire changent.
- **J3bis** = la spécification ci-dessous (section « J3bis — SPÉCIFICATION
  RETENUE ») ; **J4** = continuum (médiane / étoiles 5σ, case « recentrer ») ;
  **J5** = ancre + doc.

### Verdict réel de J2 (consigné)
- **AVEC continuum** : réglage de force visible, rendu retenu. **SANS** : les
  rouges « s'éteignent un peu » ⇒ le continuum non soustrait se voit ; ne pas
  le prendre pour un défaut du Ha.
- **Q retenu : 0,80** (défaut) · **poids poussé à 1,5 SUR CETTE CIBLE** (M33) :
  réglage **PAR CIBLE**, le défaut reste **1,0**. Aucun défaut bloquant signalé.
- **Verdict global : VALIDÉ.**

### Verdict réel de J3 (19/10, M33, SPCC) — **À REPRENDRE**
- **`fondu_rouge`** : α affiché **GRISÉ** (défaut corrigé en v2.89.1) ; image
  **BLEUIE**, **Ha invisible dans les zones rouges**, étoiles bleues/vertes ;
  un SCNR retire le vert et laisse une forte dominante bleue ; zones Ha
  **blanches / bleu très clair** (à α 0,5).
- **`ecran_rouge`** : zones Ha **CYAN**.
- **`eclaircir_rouge`** : image quasi normale, zones Ha **à peine rosées**, et
  **la force est SANS EFFET** (identique à 0 et à 3) — le mode est INERTE.
- **`ha_luminance`** : effet VISIBLE (zones Ha plus lumineuses) mais **plus
  blanches**.
- **Avec les gains Gaia au lieu de SPCC** : éclaircir laisse voir le rouge,
  luminance donne un rose (très léger) ⇒ **le niveau de R commande tout**.
- **CAUSE PROBABLE (hypothèse de départ) — échelles NON APPARIÉES** :
  `composer()` normalise CHAQUE rôle séparément ; `s` (Ha) et `R` ne sont donc
  pas comparables. Un remplacement (`fondu` ×(1−α)) divise le rouge du FOND
  (⇒ cyan/bleu) ; un `s·(1−R)` devient négatif là où `R > 1` (⇒ cyan) ; un
  `max(R, s)` est nul partout si `s < R` (⇒ le poids ne multiplie que zéro).
  `ajout_rouge` (J2) est le seul à échapper au piège : il est purement ADDITIF.
  **→ CHIFFRÉE ci-dessous : l'axe n'est pas l'amplitude mais l'ESPACE.**

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
- **Sonde (hors appli, non implémentée)** : opérateurs exprimés dans l'espace
  de R (`R̃ = (R − fond_R)/A_R`, `s̃ = s/amplitude(s)`) puis ramenés dans
  l'espace du composite → fondu neutre au fond (+0,037 en Ha large), écran
  n'AJOUTE plus que (+0,22 ; 0 % de baisse), éclaircir agit (66 %), et
  `luminance MULTIPLICATIVE` (`rgb × (1 + s̃)`) donne +62 % sur les TROIS
  canaux en cœur Ha (couleur préservée, aucun blanchiment par construction).
- **Piste RETENUE (Alain, 19/10) : (A)** — exprimer les opérateurs dans l'espace
  de R, mesurée ci-dessus ; **(B)** (neutraliser si `R ∉ [0 ; 1]`) et **(C)**
  (borner seulement) sont **ÉCARTÉES** par Alain. **Ne pas toucher au J2.**

### Fichiers modifiés dans cette phase
- `avastack/processing/composition.py` : 5 modes, α, poids = interpolation,
  clé de mémoïsation (α), docstrings.
- `avastack/ui/panels/compo.py` (champ α), `ui/app.py` (`_lire_fusion_ha`,
  `_maj_fusion_ha`, **`_on_fusion_ha` rafraîchit l'état des widgets**),
  `ui/config_ui.py` (`fusion_ha_alpha`), `ui/saver.py` (fiche).
- `avastack/__init__.py` (**2.89.1** + changelog), `CLAUDE.md` (§ J3, verdicts).
- `bancs/_test_fusion_ha_jalon3.py` (NEUF, 8 volets + volet « chemin RÉEL de la
  Combobox ») ; `bancs/_test_fusion_ha_jalon2.py` (3 volets mis à jour).
- `bancs/_diag_fusion_ha_echelles.py` (NEUF, **outil de mesure du J3bis**) :
  rejoue `composer()` sur les `canal_*.fit`, mesure p0,25/p50/p99,7 de `s` et
  `R`, le plancher de R, le signe de `s − R` par zone et le delta des quatre
  modes (avant / après appariement) ; `--composite` CONTRÔLE le rejeu contre
  le FITS linéaire (écart max mesuré 4e-6 sur un jeu synthétique) ;
  `--autotest` valide l'outil sur un jeu condamné ET un jeu sain.

### Décisions prises
- **J2 : rien ne change** — ajout au rouge + continuum validés en réel.
- **J3 : les formules des 4 modes sont SUSPENDUES** — elles supposaient
  `R ∈ [0 ; 1]`, ce qui est FAUX en normalisation commune (mesuré : 2,86-5,71).
  Le poids reste une force globale (acquis) ; ce sont les OPÉRATEURS qui
  doivent être exprimés dans un espace défini.
- **`ha_luminance` touche V et B** : propriété du mode, pas un défaut — mais le
  blanchiment est MESURÉ (+0,44 sur les trois canaux, base G/B 5× plus petite
  que R) : le rendu « plus blanc » n'est pas une impression.

### J3bis — SPÉCIFICATION RETENUE (option A, choisie par Alain le 19/10)

**Principe** : les quatre modes J3 ne comparent plus `R` (qui vit entre 2,9 et
5,7 en normalisation commune) à `s` (écrêté dans [0 ; 1]) : ils comparent
`R̃` et `s̃`, tous deux ramenés à « 0 au fond du ciel, ≈ 1 au p99,7 ».
`ajout_rouge` (J2) est **INCHANGÉ** (purement additif, validé en réel).

**Dans `fusionner_ha` (composition.py), pour les 4 modes J3 seulement** :
1. `fond_R` = médiane de `R` sur le fond (l'outil mesure sur la moitié basse de
   `s` ; une estimation par médiane/MAD du fond convient) ;
   `A_R` = p99,7(`R`) − `fond_R` ; `R̃ = (R − fond_R) / A_R`
2. `s̃ = s / p99,7(s)` (`s` déjà recentré + continuum + écrêtage : NE PAS y
   toucher, c'est le J2) ;
3. opérateurs :
   · `fondu`      : `R̃' = R̃ + α·(s̃ − R̃)`
   · `ecran`      : `R̃' = R̃ + s̃·max(0, 1 − min(R̃, 1))`
   · `eclaircir`  : `R̃' = R̃ + max(0, s̃ − R̃)`
   · `ha_luminance`: **multiplicatif**, sur les TROIS canaux :
     `rgb' = rgb × (1 + s̃)` (la couleur est préservée par construction) ;
4. retour pour les trois modes « rouge » : `R' = max(0, fond_R + A_R·R̃')` ;
   pour `ha_luminance`, aucun retour d'échelle (le facteur s'applique au RGB) ;
5. **poids** : l'interpolation reste celle d'aujourd'hui, dans l'espace du
   COMPOSITE — `sortie = composite + poids × (résultat_mode − composite)` —
   pour que **poids 0 = composite du J1 AU BIT** (acquis des cinq modes).

**Garde-fous à écrire** : `A_R` ou `p99,7(s)` ≈ 0 → aucun ajout (no-op, jamais
d'exception) ; `R̃` peut dépasser 1 (cœurs/étoiles) → l'écran borne, le fondu
non ; `R̃'` ne doit jamais rendre un rouge négatif. `fond_R`/`A_R` dérivent du
COMPOSITE, pas d'un réglage : **ne pas les mettre dans la clé de mémoïsation**
(la clé garde mode, poids, α, recentrer, continuum, Q, méthode).

**Bancs** : `_test_fusion_ha_jalon3.py` teste aujourd'hui les formules AU BIT →
il va casser VOLONTAIREMENT sur les 4 modes (le J2 doit rester au bit). Ajouter
un volet « composite HORS [0 ; 1] » (R ≈ 2,9-5,7, comme la session M33) qui
exige : aucun mode ne baisse le rouge du FOND, `eclaircir` AGIT, `ecran`
n'abaisse JAMAIS, `ha_luminance` ne change pas les rapports R/G/B. Référence de
comportement : `python bancs/_diag_fusion_ha_echelles.py --autotest`.

**NE PAS TOUCHER** : `ajout_rouge`, continuum, α, poids, l'interface (aucun
nouveau réglage visible), la fiche de rendu, la clé de mémoïsation.

### Prochaines étapes
1. **Implémenter A** dans `fusionner_ha` (+ docstring des cinq modes) ;
2. **Bancs** : mettre à jour le J3, ajouter le volet « composite > 1 », rejouer
   J2 / 129 / 130 / 136 / 137 / 141 + le garde-fou + pyright (J2 AU BIT exigé) ;
3. **test réel J3bis** sur M33 (mêmes couches : `C:\Astro\test\M33_Canaux_LRGBHa`
   reste la référence chiffrée) ; puis **J4** et **J5** ; **release sur accord
   explicite d'Alain** — jamais avant.

---

## HISTORIQUE — 18/10/2026 (détail : changelog v2.86.0/v2.87.0/v2.88.0)

①/②/③ validés en réel · **136** halo coloré et **137** neutralisation STF
(v2.86.0) · **141-B** interface, validée (v2.87.0) · **J2** fusion du Ha +
continuum (v2.88.0, validé le 19/10) · garde 133 astrométrie livrée · `phase`
écartée en broadband ET narrowband · combine innocenté (140/142/143).

### Mesures du chantier (détail dans `CLAUDE.md`, changelog v2.82.2) — **ne pas rejouer**
140 RGB propre · 142 LRGB R +103,9 % / B +132,1 % · 143 B +80,7 % · 144 B +34,6 % ·
poids 0,857 et σ ×4,38 aux 243 taches.

### Astrométrie — RÉSOLUE (18/10) : les AD/Dec saisies étaient celles de M31
Champs **M31** sur des brutes **M33** ; avec les bons indices le solve résout
(115 appariements, 2,469″/px, rms 0,30 px) — `CLAUDE.md` § « Diagnostic de
l'entrée d'astrométrie » ; preuves dans `C:\Astro\test\` (`_dump154_*`).

### Décisions 18/10 — TRANCHÉES, **ne pas rouvrir** (détail : `CLAUDE.md` + changelog)
- Combine LRGB **hors de cause** (140/142/143) ; cause unique mesurée = `phase` en
  broadband ⇒ l'hypothèse « rouge = contenu des 240 brutes L » est ABANDONNÉE.
- `phase` **écartée** en broadband ET narrowband (pas de case : drapeau par
  session) ; aligneurs du Ha (voie A) NON touchés ; ② = choix C (raffiner au-delà
  de `TRI_RAFFIN_SEUIL`).
- **141 = B (PRÉVENIR)**, livrée et validée ; A (documenter) / C (invalider) écartés.
- **VeraLux CLOS** (122/123/124 suffisent, fichier tiers GPL non modifié) ;
  résidu L (~0,48 px) ABANDONNÉ ; la FONCTION SPCC RESTE (seule son enquête
  d'alerte est close) — **ne pas rouvrir**.
- **Teinte des COINS = DÉGRADÉ** (1,3 % en linéaire, ×18 par la MTF) : GraXpert/ABE
  ou estimateur par région, **à trancher par Alain** — mesurée, non traitée.
- **J2** : fusion ACTIVE PAR DÉFAUT (poids 1,0 ; **1,5 sur M33, réglage par
  cible**), Ha RECENTRÉ, **poids 0 = composite du J1 AU BIT**, continuum ACTIF
  (Q 0,80, référence R, écrêtage [0 ; 1], coupable d'une case). VALIDÉ EN RÉEL.
- **J3** : cinq modes, poids = FORCE GLOBALE (poids 0 = J1 au bit pour TOUS), α
  réservé au fondu ⇒ **formules SUSPENDUES**, remplacées par J3bis (option A).
- **134c invalide** (brute dithérée) ; **135/136/138** annulées.

### Problèmes ouverts
- **Aucun bloquant** sur ①/②/③/136/137/141-B/J2 : livrés, mesurés, bancs verts.
  Reste à juger À L'ÉCRAN : le rendu de J3bis, une fois implémenté (option A).
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
- **J3 — `ha_luminance` touche V et B** : c'est son objet. Ne pas en conclure
  une régression du type « la fusion ne devrait toucher que le rouge » — les
  quatre autres modes, eux, laissent V et B AU BIT.
- **J3 — comparer les TROIS canaux** : `ajout_rouge` et `ha_luminance` ont le
  même rouge ; un banc qui ne lit que R croit à un doublon (piège rencontré).
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
Arbre **v2.89.1** sur `LRGBHa` : **J2 VALIDÉ en réel** ; **J3 mesuré sur les
couches M33** — avec la normalisation COMMUNE le rouge du composite vit entre
2,86 et 5,71 alors que `s` est écrêté dans [0 ; 1], d'où `écran` qui soustrait
(−1,51 au cœur Ha), `éclaircir` strictement inerte, `fondu` qui retire la moitié
du rouge du fond et `ha_luminance` qui blanchit. Prochaine action unique :
**implémenter J3bis OPTION A** (spécification complète dans ce fichier, section
« J3bis — SPÉCIFICATION RETENUE ») dans `fusionner_ha`, **J2 devant rester AU
BIT** — aucune release sans accord.

---

## Chantier en cours — LRGB+Ha (jalons 129 → J5) — J2 validé, J3 livré

Le rôle Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le combine L.

| Jalon | Contenu | État |
|---|---|---|
| J1 / 129 (v2.81.0) | compositions + 5 lignes UI + séparation ancre / `_narrowband_ha` | commité |
| 129b | voie A (référence **PAR RÔLE** + recalage de l'empilement) + `profondeur_min` + refus par rôle | COMMITÉ ; validé en réel le 16/10 (441 frames, 2 refus en R) |
| **130 (v2.82.0)** | combine LRGB borné [0 ; 5] + repli local + fiche + banc neuf | COMMITÉ + POUSSÉ (`ef0c35c`) |
| **J2 (v2.88.0)** | fusion « ajout au rouge » + poids 1,0 + recentrage + **continuum (Q, case)** + cadre « Fusion Ha » | **VALIDÉ EN RÉEL le 19/10** |
| **J3 (v2.89.0)** | `fondu_rouge` (α), `ecran_rouge`, `eclaircir_rouge`, `ha_luminance` + poids = force globale | **LIVRÉ mais À REPRENDRE** — verdict réel 19/10 : fondu bleui, écran cyan, éclaircir INERTE |
| J3bis | appariement d'échelle R ↔ Ha puis reprise des 4 opérateurs | à faire |
| J4 → J5 | continuum méthodes **médiane / étoiles 5σ** (+ case recentrer) ; ancre réelle + doc | à faire |

Plan figé (13 arbitrages du 15/10) : poids **1,0** (0–10) · α **0,5** · Q **0,80**
(0,10–2,00) · cadre « Fusion Ha » visible seulement si la compo contient Ha ·
continuum = **bandes passantes** (Ha 7 nm / RGB 100 nm), référence **R** ·
identifiants en français (`synthetise`).

---

## En attente / prochaine session (état au 19/10 — `LRGBHa`, v2.89.1)

- **Prochaine action unique** : **implémenter J3bis option A** — la
  spécification complète est dans « J3bis — SPÉCIFICATION RETENUE » ci-dessus.
  Ensuite seulement : **test réel** par Alain, puis la suite (J4, J5).
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

- **19/10/2026** : J2 **validé en réel** (Q 0,80 ; poids 1,5 sur M33, par cible) et
  **J3 livré** — cinq modes de fusion du Ha + α, v2.89.0.
- **18/10/2026** : 141-B (v2.87.0) et J2 (v2.88.0) livrés ; ①/②/③, 136 et 137
  validés en réel.
