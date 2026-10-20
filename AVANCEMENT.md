# AVANCEMENT.md — mémoire de travail à court terme

(Complète `CLAUDE.md`, qui porte les leçons durables. Ici : état courant, décisions,
pièges actifs, prochaine action. Le détail daté vit dans `avastack/__init__.py`
(changelog) et `git log` — pas ici.)

---

## ⚠️ BRANCHE DE DÉVELOPPEMENT ACTIVE — NE PAS SUPPRIMER JUSQU'À DEMANDE EXPLICITE

**Branche : `OptimisationUI`** (créée le 20/10/2026 à partir de `master`, pour le
**lot 5 = P5**, audit MESURÉ de la réactivité de l'interface)

> **RÈGLE FERME — GRAVÉE DANS LE MARBRE** : jusqu'à nouvel ordre explicite,
> **TOUT** développement et **TOUTE** modification de code se font **EXCLUSIVEMENT**
> sur `OptimisationUI`. `master` = branche stable, releases uniquement ; merge vers
> `master` seulement sur validation explicite (demande d'Alain).
>
> **`LRGBHa` est FERMÉE le 20/10/2026** : fusionnée en **fast-forward** dans
> `master` (commit `efb2911`, après validation réelle de P6), puis **supprimée**
> en local et sur `origin`. Sa trace vit dans `git log` et dans le changelog de
> `avastack/__init__.py`. Ne pas la recréer sans demande d'Alain.

Versions : `master` et `OptimisationUI` = **v2.96.1** (**136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum, **J3/J3bis** cinq modes, **J4/J4.1** continuum trois
méthodes et mesure indépendante de la case — tous **VALIDÉS EN RÉEL le 19/10** ;
**J5** ancre = couche large bande, **VALIDÉ EN RÉEL** ; **Lot 1 (P2 + P3)** base
SPCC la plus riche + astrométrie servie sans frame, **VALIDÉ EN RÉEL le 19/10** ;
**P7** recalcul après un choix de couleur, **CORRIGÉ ET VALIDÉ EN RÉEL le 19/10** ;
**P1** cadence de re-mesure, **VALIDÉ EN RÉEL le 19/10** ; **P4** infobulles
« ⓘ », **VALIDÉ EN RÉEL le 19/10** ; **P6** source « Stacks (fichiers FITS) »,
**testée en RÉEL le 19/10** (empilement OK) — **ses 2 défauts d'INTERFACE ont été
CORRIGÉS (piste A) ET VALIDÉS EN RÉEL le 20/10** (**v2.96.1**))
· `master` publié = **v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 20/10/2026 — **P6 VALIDÉ EN RÉEL** (v2.96.1) puis **P5 : réactivité MESURÉE** (chiffres seuls, AUCUN correctif)

### État actuel
- **v2.96.1 sur `master`** — P6 **VALIDÉ EN RÉEL par Alain le 20/10** (« testé en
  réel, validé ») : cadre « Fusion Ha », réglages du composite et continuum
  accessibles avec la source « Stacks ». **Aucune release** (`fb81b1d` = P6,
  `efb2911` = correctif piste A, fusionné dans `master`).
- **Branche de travail : `OptimisationUI`** (depuis `master`, poussée et suivie).
  **`LRGBHa` fermée** (local + `origin`).
- **P5 = MESURÉ le 20/10** avec l'outil neuf `bancs/_mesure_p5_reactivite.py`
  (JSON conservé) : **aucun correctif appliqué**, conformément à la règle
  « mesurer d'abord, corriger ensuite ». Le banc `_test_perf_reactivite_jalon79`
  est étendu aux cases / listes / spinners (**29 vérifications, tout passe**).
- **Bancs** : P6 **vert, 59 vérifications** (joué avec les vrais `canal_*.fit` de
  `C:\Astro\test\M33_Canaux_LRGBHa`, repli synthétique sinon). Non-régressions
  vertes : 47, 52, 53, 19, 129, 141-B, J2, J3, J4, J5, P4, P1, garde-fou
  (**pyright 0 sur 54 fichiers typés**). **Échec PRÉEXISTANT** :
  `_test_lot1_p2_p3` volet [3] (profil SPCC déjà corrigé dans `config.json`).

### P5 — LES CHIFFRES (mesurés le 20/10, machine de dev, `--n 5`)
> JSON : `bancs/_mesure_p5_reactivite.json`. Rejouer :
> `python bancs/_mesure_p5_reactivite.py` (écran requis ; `--autotest` sans écran).

| ce qui est mesuré | chiffre |
|---|---|
| geste gamma / saturation (après étirement) | **31 ms** |
| geste « fond du ciel » / « coupure du bruit » / black | **57–59 ms** |
| glissement de **200 px** sur un curseur | **6,5 s** (gamma) → **12 s** (black) |
| charge pour suivre 60 Hz de souris | **361 % d'un cœur** |
| aperçu complet / sans histogrammes | 46 ms / 27 ms (histogrammes **20 ms**) |
| `_tick_corps` (budget 30 ms) | **0,06 ms = 0,2 %** |
| clic de case (`invoke`) | 1 aperçu (31 ms) ; **auto-STF = 2,33 aperçus** (84 ms) |
| `var.set` nu (case / liste / spinner) | **0 rappel** (piège Tk, prouvé) |
| liste SPCC **147** valeurs : repeuplement / sélection | **0,12 ms / 0,02 ms** |
| `_maj_visibilite_cadres` | 0,2–0,3 ms, 12 pack + 3–9 forget |
| rafale (60 pas, boucle ACTIVE) | 60 battements / 100 attendus, écart max **58 ms** |
| opérations > **0,25 s** (Guet abaissé) | **0** |

**Lecture** : la boucle `_tick`, les listes (même 147 valeurs) et `pack/forget`
ne sont **PAS** en cause. Tout le coût est dans **`_refresh_preview` rappelé à
chaque pixel** (30–60 ms) et dans les **écritures non conditionnelles**
(`_on_auto` repose deux curseurs puis redessine = 2,33 aperçus par clic). Aucun
gel UNIQUE > 0,25 s : la gêne est l'**EMPILEMENT** des gestes (361 % d'un cœur).

### Le correctif P6 (piste A) — détail durable dans `CLAUDE.md`
- **Visibilité** : `est_stacks` → fichiers puis composition ; « Fusion Ha »,
  gains, normalisation commune et lissage LRGB sont des enfants de `frm_compo`.
- **Composition déduite** (`_maj_compo_depuis_stacks`), **verrouillage**
  (`_maj_compo_verrouillage` : menu, lignes DOSSIER, `…`, détection grisés ;
  réglages du composite ACTIFS), **présence d'un rôle** (`_role_fourni`, qui
  pilote aussi le continuum). **Piste B écartée** (refactor plus large).

### Fichiers modifiés dans cette phase
- `bancs/_mesure_p5_reactivite.py` (**neuf**) : outil de mesure P5 (9 sections) ;
- `bancs/_mesure_p5_reactivite.json` (**neuf**) : chiffres du passage, rejouable ;
- `bancs/_test_perf_reactivite_jalon79.py` : sections **[8] cases**, **[9] listes**,
  **[10] spinners** (chemin RÉEL : `invoke`, `<<ComboboxSelected>>`, `command`) ;
- (P6, déjà livré) `avastack/ui/app.py`, `panels/compo.py`, `panels/stacks.py`,
  `bancs/_test_lot5_p6_stacks.py`, `avastack/__init__.py`, `CLAUDE.md`.


### Décisions
- **Piste A TRANCHÉE (Alain, 20/10)** : réutiliser le panneau « Composition »
  pour les FICHIERS en verrouillant les lignes DOSSIER — piste B (panneau
  « composite » séparé) écartée comme refactor plus large sans bénéfice.
- **La composition AFFICHÉE suit la source** : fichiers → déduite (menu
  verrouillé) ; dossiers → choisie au menu. **Un seul fichier n'est pas une
  composition** (cadre « Fusion Ha » masqué).
- **Rappels P6** : le rôle n'est JAMAIS déduit ; refus sur PREUVE seulement ;
  seuil de profondeur = 1 ; `_source_fichiers()` ≠ `_cadence_dossier()`.
- **P5 : mesurer SANS toucher au produit** (20/10) — `Guet.SEUIL_S` reste à
  1,5 s : le banc compte lui-même les opérations au-delà de 0,25 s (`--seuil`),
  même information, rien à remettre en état après coup. **Aucun correctif**
  avant l'accord d'Alain.

### Problèmes ouverts / prochaines étapes
1. **P5 — CORRECTIFS, sur accord d'Alain** (un lot = un jalon), dans l'ordre des
   chiffres : ① **coalescing ~20 Hz** des rappels de curseur (un aperçu pour
   plusieurs pixels) ; ② **écritures conditionnelles** (`_on_auto` : 2,33
   aperçus par clic) ; ③ histogrammes différés pendant un glissement.
   Cibles : 31 ms → ~5 ms par aperçu utile, glissement 200 px sous 1 s.
2. **Release v2.96.x** sur accord explicite (aucune release depuis v2.80.0 ;
   `master` porte la fusion de `LRGBHa`, branche fermée le 20/10).


---
## Points d'attention
- **TROIS noms de composition** (141-B) : `stacker.composition`/`_compo_nom`,
  `_compo_session`, `var_compo` ; **`"RGB+Ha"` est une sous-chaîne de
  `"LRGB+Ha"`** ⇒ jamais `startswith`/`in` pour identifier une composition.
- **J2 — fusion ACTIVE PAR DÉFAUT** : `fusion_ha = None` = défauts figés ;
  désactiver = `{"poids": 0.0}`. Le réglage entre dans la clé de mémoïsation et
  dans `disp.vl_compo`.
- **J2 — continuum** : actif par défaut, **case ET Q désactivés sans couche R
  FOURNIE** — un **dossier** en composition, un **fichier** pour la source
  « Stacks » (`_role_fourni`, piste A) ; l'échelle R est le DÉNOMINATEUR de
  normalisation du Ha (ne pas le remplacer par 1 sans regarder le mode de
  normalisation).
- **P6 piste A — la composition est VERROUILLÉE sous la source « Stacks »** :
  `_maj_compo_verrouillage` grise le menu, les lignes rôle→DOSSIER, `…` et
  « Détecter les filtres » ; les réglages du COMPOSITE (gains, normalisation
  commune, lissage LRGB, « Fusion Ha ») restent ACTIFS. Ne jamais réintroduire
  un chemin qui réécrit `var_compo` depuis les lignes dossier sous cette source
  (`_on_compo` / `_on_compo_roles` sont gardés).
- **J3bis — les cinq modes ne touchent que le ROUGE** (V/B au bit) ;
  `ha_luminance` = gain **à porte** (0,05–0,25) : ne pas baisser la porte sous
  0,05 sans refaire la mesure.
- **Une brute est DITHÉRÉE** : seul un empilement ALIGNÉ prouve quelque chose ;
  `--dossier` sans `--dark` = run invalide dès que l'exposition change.
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`. Bancs UI :
  `cv2.ocl.setUseOpenCL(False)`, `ui.CONFIG = {}`, `ui.App._dire` patché
  (boîte MODALE, sinon blocage), jamais `grid` + `pack` dans le même conteneur.

### Contexte de reprise (à coller — 2 phrases)
Arbre **v2.96.1** sur la branche **`OptimisationUI`** : **P6 VALIDÉ EN RÉEL**
(20/10, `LRGBHa` fermée) et **P5 MESURÉ** (chiffres dans `AVANCEMENT.md` +
`bancs/_mesure_p5_reactivite.json`, **aucun correctif appliqué**).
**Prochaine action** : correctifs P5 (coalescing des curseurs, écritures
conditionnelles), sur accord d'Alain.


---

## Chantier CLOS — LRGB+Ha (jalons 129 → J5) — **J2 à J5 validés en réel**

Le Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le
combine L. Règles durables (poids 1,0 · α 0,5 · Q 0,80 · continuum trois
méthodes avec repli VISIBLE · ancre = couche large bande) : `CLAUDE.md`
(« Fusion du Ha… ») et changelog.

---

## Chantier en cours — Améliorations d'usage (P1 → P6) — **PLAN FIGÉ le 19/10**

**Un lot = un jalon** ; demander l'accord d'Alain avant chaque nouveau lot.
**LOT 0 SUPPRIMÉ** (décision d'Alain) : la base SPCC n'est PAS réparée à la
main — le correctif de code doit suffire, et le test réel le prouve.

| Lot | Points | Contenu | État |
|---|---|---|---|
| **1** | **P2 + P3** | base SPCC la plus riche, zéro substitution silencieuse, `_astro_demande` | **VALIDÉ EN RÉEL le 19/10** ; **P7 validé en réel** (v2.93.1) |
| 2 | P1 | cadence de re-mesure Gaia/SPCC | **VALIDÉ EN RÉEL le 19/10** (v2.94.0) |
| 3 | P4 | infobulles ⓘ | **VALIDÉ EN RÉEL le 19/10** (v2.95.0) |
| **4** | **P6** | source « stacks » : fichiers choisis, **rôles saisis**, seuil de profondeur = 1 | **VALIDÉ EN RÉEL le 20/10** (v2.96.1) — empilement le 19/10, défauts d'interface corrigés (piste A) puis validés |
| **5** | **P5** | audit MESURÉ de la réactivité | **MESURÉ le 20/10** (chiffres en tête de session) — **correctifs à venir sur accord d'Alain** |

### Lot 1 — P2 + P3 (v2.93.0) · P1 (v2.94.0) · P4 (v2.95.0) — **VALIDÉS EN RÉEL le 19/10**
- **P2 + P3** : base SPCC **la plus riche** (compteurs au journal, extraction jamais
  plus pauvre, défauts par canal, garde FILTER) + `_astro_demande`. Banc
  `_test_lot1_p2_p3.py` (7 volets, 51 vérifications). Détails dans `CLAUDE.md`.
- **P1** : `processing/cadence.py` (`CadenceMesure`) — 3 → passe finale → plafond
  6 → doublement → délai 20 s, branches dans `_astro_tour` / `_photo_tour` /
  `_spcc_tour`. Mesuré AVANT de coder : 6,87 s pour 65 s d'empilement (JSON
  `bancs/_mesure_p1_cadence.json`) ; banc `_test_p1_cadence.py` (29).
- **P4** : `ui/bulles.py` (`Bulle`, `astuce`, mixin `Aides`), 13 aides migrées
  (**14** avec le panneau Stacks), option `aides_texte` (défaut NON), **702 px
  repris** (mesuré). Détail dans `CLAUDE.md` (« Aides contextuelles »).

### P5 — réactivité (lot 5) — **MESURÉ le 20/10, aucun correctif**
- Outil `bancs/_mesure_p5_reactivite.py` (9 sections, `--autotest` sans écran,
  JSON `bancs/_mesure_p5_reactivite.json`), **sans modifier le produit** : le
  seuil du Guet reste 1,5 s, le banc compte lui-même les opérations > 0,25 s.
- **Suspicions LEVÉES par la mesure** : `_tick` (0,2 % du budget), listes SPCC
  jusqu'à 147 valeurs (0,1 ms), `pack/forget` de `_maj_visibilite_cadres`
  (0,3 ms). **Suspicion CONFIRMÉE** : un aperçu complet par pixel de curseur
  (31–59 ms) et des réécritures non conditionnelles (2,33 aperçus par clic).
- Banc `_test_perf_reactivite_jalon79` étendu : [8] cases, [9] listes,
  [10] spinners → **29 vérifications vertes**.

### P6 — source « Stacks (fichiers FITS) » (lot 4) — **VALIDÉ EN RÉEL le 20/10 (v2.96.1)**
- **Verdict d'Alain** : empilement OK le 19/10, puis **« testé en réel, validé »
  le 20/10** après le correctif des deux défauts d'interface (piste A).
- Contrat durable (rôle JAMAIS déduit, `AVAFRAME` jamais lue, profondeur non
  inventée, calibration court-circuitée, lecture unique par session, linéarité
  sur PREUVE) : `CLAUDE.md` (« Source « Stacks (fichiers FITS) » »).
- Banc `_test_lot5_p6_stacks.py` (**59** vérifications, dont 16 piste A).


---

## En attente / prochaine session (état au 20/10 — branche `OptimisationUI`, v2.96.1)

- **P6 est CLOS ET VALIDÉ EN RÉEL** (v2.96.1, fusionné dans `master` ; `LRGBHa`
  fermée) : banc P6 vert (59 vérifications) et test réel d'Alain concluant.
- **P5 est MESURÉ** (20/10) : outil `bancs/_mesure_p5_reactivite.py` + JSON,
  banc jalon 79 étendu (29 vérifications vertes), **aucun correctif appliqué**.
- **Prochaine action unique** : **CORRECTIFS P5 sur `OptimisationUI`** — **accord
  d'Alain requis** (un lot = un jalon). Ordre proposé, dicté par les chiffres :
  ① coalescing ~20 Hz des rappels de curseur ; ② écritures conditionnelles
  (`_on_auto` = 2,33 aperçus par clic) ; ③ histogrammes différés en glissement.
  Re-mesurer avec le MÊME outil après correctif (diff des deux JSON).
- **Puis** : **release v2.96.x** sur accord explicite (`master` porte désormais
  tout le chantier depuis v2.80.0).

- **Référence chiffrée** : `C:\Astro\test\M33_Canaux_LRGBHa` (5 `canal_*.fit` +
  fiches ; `AVACOMPO` = LRGB+Ha, **normalisation COMMUNE**, lissage 117d).
  Rejouer : `python bancs/_diag_fusion_ha_echelles.py --canaux <dossier>
  --norm-commune --lissage-halos --poids 1.5` (`--autotest` contrôle l'outil).
- **Ne pas retoucher** : `ajout_rouge` (AU BIT), la formule `bandes_passantes`
  7 nm, α, le poids, le principe « repli = bandes passantes AU BIT ».
- **Optionnel** : cible qui REMPLIT le cadre (repli attendu et DIT) et filtre
  **3 nm** si Alain en a un.
- **141-B validée** (rien à retester) ; **teinte des COINS** notée, sans action.
- Retour arrière en un geste (correctif seul) : `git checkout HEAD~1 --
  avastack/ui/app.py avastack/ui/panels/compo.py avastack/ui/panels/stacks.py`.

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

- **Un rendu sans nouvelle frame n'est PAS vu par `_tick`** : `_tick` ne force
  la chaîne que sur changement de `st["frames"]`. Tout point qui pousse une
  image RECALCULÉE doit appeler `disp.notify_new_stack()` (leçon P7, désormais
  dans `CLAUDE.md`).
- **Échecs PRÉEXISTANTS** : `_test_espace_jalon72` (géométrie d'écran — dont
  `('écrasé', 'Menu', 'Menu', 99, 1300)`, reproduit sur HEAD le 19/10),
  `_test_reset_empilement_jalon76` [4] (course `_stop()`, sensible à la charge
  CPU), dans `_test_sans_siril_jalon77`, « ligne Base SPCC rognée de 1-2 px » +
  « menu écrasé » (prouvés sur HEAD dans un worktree : flaky, la longueur du
  dossier temporaire décide), et — **constaté le 19/10** — `_test_lot1_p2_p3`
  volet [3] « le profil corrigé est annoncé en AVIS » : le banc rejoue le cas
  `Antlia R` sur le `config.json` RÉEL, or le test réel l'a déjà corrigé en
  `QHYCCD MiniCam8M Red` → plus rien à reposer (échec reproduit sur HEAD, sans
  les correctifs P7 : **environnemental, pas une régression**).
- **Un jeu SANS le défaut ne mesure que l'ABSENCE DE COÛT** : 109 frames sans
  retournement donnaient « retirer `phase` ne change rien » ; sur **Sh2-132**
  (204 frames, **31 retournements**), la phase finalisait 22 frames dont 21 Ha
  fausses de 1,1 à 2,3 px. Vérifier que le défaut est REPRÉSENTÉ (compter les
  |angle| > 170°, pas seulement les refus) avant de conclure.
- **Une réussite de repli n'est pas une preuve d'alignement** : `phase` en
  translation seule a posé 11/50 puis 12/49 frames B **à l'envers**. Un banc
  teste le **chemin de décision** (espion) et son coût sur une frame douce.
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`.

---

## Clôtures précédentes

- **19/10/2026** : **P4 VALIDÉ EN RÉEL** (v2.95.0) — 13 aides de la colonne en
  infobulles « ⓘ » + option « Aides en texte » ; 702 px repris (mesuré).
- **19/10/2026** : **P1 VALIDÉ EN RÉEL** (v2.94.0) — `processing/cadence.py`,
  re-mesure 3→6→12…, passe finale en fin de source ; aucune release.
