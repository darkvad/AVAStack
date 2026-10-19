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

Versions : `LRGBHa` = **v2.91.0** (①/②/③ validés en réel ; **136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum **VALIDÉ EN RÉEL le 19/10**, **J3/J3bis** cinq modes
**VALIDÉS EN RÉEL le 19/10**, **J4** continuum **trois méthodes** (médiane, étoiles
5σ, bandes 7/3 nm) **LIVRÉ — à juger à l'écran**) ·
`master` publié = **v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 — **J4 LIVRÉ** (v2.91.0, `LRGBHa`) — à valider en réel

### État actuel
- **Code** : **v2.91.0** sur `LRGBHa`. **J4 LIVRÉ** : trois méthodes de continuum
  (`bandes_passantes` par défaut, `mediane`, `etoiles_5sigma`), choix du filtre
  **7 / 3 nm**, **repli VISIBLE sur les cases**, case « recentrer » exposée avec
  son risque écrit, Q par défaut selon la méthode (0,80 / 1,00).
- **Bancs** : **J4 vert** (7 volets), **J2 et J3 verts**, non-régressions
  129/129b/130/136/137/141 + garde-fou vertes ; `ruff` sans nouvelle erreur,
  `pyright` **0** sur la liste blanche (50 fichiers). **Aucune release.**
- **Suite** : **test réel de J4 par Alain**, puis **J5** = ancre réelle + doc.

### Rappel (clos — ne pas rouvrir)
- **J2 et J3 VALIDÉS en réel le 19/10** ; détail dans le changelog
  (`v2.88.0` → `v2.90.2`). Q retenu **0,80** ; le poids **1,5** était un réglage
  **par cible** (M33), le défaut reste **1,0**.

### Ce que fait J4 (4 décisions d'Alain du 19/10)

| Décision | Effet dans le code |
|---|---|
| Les deux méthodes + bandes passantes par défaut | défaut INCHANGÉ (validé en réel) |
| « notion » des filtres 3 nm | `bw_ha` = 7 nm (défaut) ou 3 nm : rapport 7/100 ou 3/100 |
| Repli VISIBLE sur les cases | « ← appliquée » + ligne d'état orange avec la raison |
| Q = 1,00 sur une mesure | 0,80 reste LE réglage des bandes passantes |

### Comment chaque méthode trouve k
- `bandes_passantes` : `k = Q x (bw_ha / 100)` — formule du J2, AU BIT.
- `mediane` : médiane de `Ha x échelle / R` sur le continuum FRANC (R recentré
  entre p70 et p99,5) ; dispersion MAD/médiane <= 0,50, sinon repli.
- `etoiles_5sigma` : `stars.detecter_positions(r, 5σ)` +
  `photometrie.flux_ouverture` (Ha ET R) : médiane des rapports, rejet à
  2,5 MAD, **>= 5 étoiles** sinon repli.
- Le facteur mesuré est multiplié par Q puis BORNÉ à [0 ; 0,5]. En repli, la
  sortie est AU BIT celle de `bandes_passantes` avec le Q courant.

### Mesures du banc J4 (scènes synthétiques, k connu = 0,070)

| méthode | k retrouvé | écart |
|---|---|---|
| `mediane` | 0,0661 | -5,6 % |
| `etoiles_5sigma` | 0,0689 | -1,6 % |
| `bandes_passantes` 7 nm | 0,0560 (= 0,80 x 7/100) | au bit |
| `bandes_passantes` 3 nm | 0,0240 (= 0,80 x 3/100) | au bit |

Les deux mesures CONCORDENT à 4 % ; repli vérifié (champ sans continuum,
0 étoile) et ÉGALITÉ AU BIT avec les bandes passantes dans ce cas.

### Fichiers modifiés
- `avastack/processing/composition.py` : `METHODES_CONTINUUM_HA` (3),
  `BW_HA_NM_OPTIONS` (7/3), `q_ha_defaut`, `borne_bw_ha`, `_facteur_mediane`,
  `_facteur_etoiles`, `_facteur_continuum`, `info` remplie par `fusionner_ha`,
  `composer(info_fusion_ha=…)`, `CompositeStacker.info_fusion_ha` + clé de
  mémoïsation (méthode ET bande).
- `avastack/ui/panels/compo.py` : CASES EXCLUSIVES, filtre 7/3 nm, case
  « recentrer » avec son risque, ligne d'état.
- `avastack/ui/app.py` : `_lire_fusion_ha` (3 clés), `_on_methode_continuum`
  (Q au défaut de la méthode), `_refléter_methode_continuum` (appelée par
  `_tick_corps`), `_maj_fusion_ha` (grisages selon la méthode).
- `avastack/ui/config_ui.py` : lecture/écriture des 3 clés (+ typage).
- `avastack/ui/saver.py` : `bw_ha_nm` dans la fiche de rendu.
- `avastack/__init__.py` : **2.91.0** + changelog.
- `bancs/_test_fusion_ha_jalon4.py` : NEUF (7 volets) ; bancs J2/J3 recalés
  (leurs dicts attendus portent `bw_ha`).

### Prochaines étapes
1. TEST RÉEL de J4 par Alain (M33) : ciel gris (pas de voile), extensions
   pleines (pas creusées), étoiles blanches.
2. Puis J5 (ancre réelle + doc). Release seulement sur accord explicite.

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
Arbre **v2.91.0** sur `LRGBHa` : **J2 et J3 sont VALIDÉS en réel** (19/10) et
**J4 est LIVRÉ** — continuum à **trois méthodes** (`bandes_passantes` 7/3 nm par
défaut, `mediane`, `etoiles_5sigma`), **repli visible sur les cases**, case
« recentrer » avec son risque ; banc J4 + J2/J3 + non-régressions verts, `pyright`
0, **aucune release faite**. Prochaine action : **faire juger J4 à l'écran par
Alain** (M33, puis une cible qui remplit le cadre pour voir le repli), ensuite J5
(ancre + doc).

---

## Chantier en cours — LRGB+Ha (jalons 129 → J5) — **J2, J3 validés ; J4 livré**

Le rôle Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le combine L.

| Jalon | Contenu | État |
|---|---|---|
| J1 / 129 (v2.81.0) | compositions + 5 lignes UI + séparation ancre / `_narrowband_ha` | commité |
| 129b | voie A (référence **PAR RÔLE** + recalage de l'empilement) + `profondeur_min` + refus par rôle | COMMITÉ ; validé en réel le 16/10 (441 frames, 2 refus en R) |
| **130 (v2.82.0)** | combine LRGB borné [0 ; 5] + repli local + fiche + banc neuf | COMMITÉ + POUSSÉ (`ef0c35c`) |
| **J2 (v2.88.0)** | fusion « ajout au rouge » + poids 1,0 + recentrage + **continuum (Q, case)** + cadre « Fusion Ha » | **VALIDÉ EN RÉEL le 19/10** |
| **J3 (v2.89.0)** | `fondu_rouge` (α), `ecran_rouge`, `eclaircir_rouge`, `ha_luminance` + poids = force globale | LIVRÉ — **verdict réel 19/10 : à reprendre** (fondu bleui, écran cyan, éclaircir inerte) |
| **J3bis (v2.90.2)** | les 4 opérateurs dans l'espace de R ; `ha_luminance` = gain **à porte** (0,05–0,25) ; `ajout_rouge` au bit | **VALIDÉ EN RÉEL (19/10)** |
| **J4 (v2.91.0)** | continuum **trois méthodes** (`bandes_passantes` 7/3 nm, `mediane`, `etoiles_5sigma`), **repli visible**, case « recentrer » | **LIVRÉ — à juger à l'écran** |
| J5 | ancre réelle + doc | à faire |

Plan figé (13 arbitrages du 15/10) : poids **1,0** (0–10) · α **0,5** · Q **0,80**
(0,10–2,00) · cadre « Fusion Ha » visible seulement si la compo contient Ha ·
continuum = **bandes passantes** (Ha 7 nm / RGB 100 nm), référence **R** ·
identifiants en français (`synthetise`).

---

## En attente / prochaine session (état au 19/10 — `LRGBHa`, v2.91.0)

- **J2 et J3 sont CLOS** (validés en réel le 19/10). Les cinq modes sont livrés :
  `ajout_rouge` (J2, au bit), `fondu_rouge` (α), `ecran_rouge`, `eclaircir_rouge`,
  `ha_luminance` à porte.
- **J4 est LIVRÉ, PAS ENCORE JUGÉ** : bancs verts, aucune mesure réelle. **À
  juger à l'écran** : la **médiane** et les **étoiles 5σ** sur M33 (et sur une
  cible qui REMPLIT le cadre, pour voir le repli), le filtre **3 nm** si Alain
  en a un, et la case **recentrer décochée** (voile rouge attendu, c'est le
  témoin du risque).
- **Prochaine action unique** : **test réel de J4 par Alain** ; ensuite **J5**
  (ancre réelle + doc). Ne pas démarrer J5 de soi-même.
- **Référence chiffrée** : `C:\Astro\test\M33_Canaux_LRGBHa` (5 `canal_*.fit` +
  fiches ; `AVACOMPO` = LRGB+Ha, **normalisation COMMUNE**, lissage 117d).
  Rejouer : `python bancs/_diag_fusion_ha_echelles.py --canaux <dossier>
  --norm-commune --lissage-halos --poids 1.5` (`--autotest` contrôle l'outil).
- **Ne pas retoucher** : `ajout_rouge` (AU BIT), la formule `bandes_passantes`
  7 nm, α, le poids, le principe « repli = bandes passantes AU BIT ».
- **141-B validée** (rien à retester) ; **teinte des COINS** notée, sans action.
- **Aucune release** sans accord explicite, et **pas avant le test réel de J4**.
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

- **J4 — le REPLI ne se devine pas côté interface** : `info_fusion_ha` est écrit
  par le thread worker sur le `CompositeStacker` ; l'interface ne doit PAS
  recalculer la mesure (ni lire les canaux). La case appliquée est marquée
  « ← appliquée » et la ligne d'état donne la raison — ne jamais déduire le
  repli de `config.json` ni d'une case cochée.
- **J4 — Q dépend de la MÉTHODE** : 0,80 en bandes passantes (c'est LE réglage),
  1,00 sur une mesure. Le remettre à zéro se fait dans `_on_methode_continuum`
  (le chemin des cases), JAMAIS dans `_lire_fusion_ha` — sinon une valeur
  persistée serait écrasée à chaque battement d'interface.
- **J4 — méthode ET bande sont dans la clé de mémoïsation** : sans elles,
  passer de 7 à 3 nm ou de médiane à étoiles resservirait le composite en cache
  (réglage « sans effet » apparent, même piège que le poids au J3).
- **J4 — une scène où le Ha n'est PAS le continuum de R fait REJETER la
  mesure** (dispersion) : c'est le garde-fou voulu, pas un bug. Un banc qui veut
  une mesure CONCLUANTE doit construire `Ha = k·(R − fond) + raie`.
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

- **19/10/2026** : **J4 LIVRÉ** (v2.91.0) — trois méthodes de continuum,
  filtre 7/3 nm, repli visible sur les cases, case « recentrer » ; banc J4 vert.
- **19/10/2026** : **J2 et J3 VALIDÉS en réel** (J2 : Q 0,80 ; J3/J3bis : cinq
  modes, `ha_luminance` à porte 0,05–0,25 en v2.90.2).
