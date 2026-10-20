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

## Session du 20/10/2026 — **P6 : défauts d'interface corrigés (piste A) et VALIDÉS EN RÉEL** (v2.96.1)

### État actuel
- **v2.96.1 sur `master`** (fusion de `LRGBHa`, branche fermée),
  **VALIDÉE EN RÉEL par Alain le 20/10** (« testé en
  réel, validé ») : le cadre « Fusion Ha », les réglages du composite et le
  continuum sont accessibles avec la source « Stacks ». **Aucune release.**
  Base : P6 livré = `fb81b1d` (v2.96.0), correctif = `efb2911`.
- **Les deux défauts du test réel du 19/10 sont corrigés** (piste A validée par
  Alain) : avec la source « Stacks », le panneau « Composition » est de nouveau
  AFFICHÉ (donc les gains R/G/B, la normalisation commune, le lissage LRGB et le
  cadre « Fusion Ha »), la composition affichée se DÉDUIT des fichiers, les
  lignes rôle→DOSSIER sont verrouillées, et le continuum lit la présence de la
  couche R dans les FICHIERS (`_role_fourni("R")`) — il n'est plus forcé à
  l'arrêt.
- **Bancs** : P6 **vert, 59 vérifications** (les 43 d'avant + 16 de la section [6]
  « piste A »), joué **avec les vrais `canal_*.fit` de `C:\Astro\test\M33_Canaux_LRGBHa`**
  (repli sur FITS synthétiques si absents). Non-régressions **vertes** : 47
  (visibilité), 52 (ergonomie), 53 (calib compo), 19 (compo UI / worker /
  composition / restack), 129 (5 rôles), 141-B (compo session), J2, J3, J4, J5
  (fusion Ha), P4 (14 aides), P1, garde-fou (**pyright 0 sur 54 fichiers typés**,
  surface `app.py` inchangée).
- **Échecs PRÉEXISTANTS** : `_test_lot1_p2_p3` volet [3] (profil SPCC déjà
  corrigé dans le `config.json` local) — inchangé, cf. « Pièges récents ».

### LE CORRECTIF (piste A) — ce qu'il faut vérifier en réel
1. **Visibilité** (`_maj_visibilite_cadres`) : pour `est_stacks`, cadres visibles
   = `[self._lf_stacks, self._lf_composition]`, empilés dans cet ordre (les
   FICHIERS d'abord, les réglages du composite ensuite).
2. **Composition déduite** (`_maj_compo_depuis_stacks`) : `var_compo` vient de
   `composition_pour_roles` sur les rôles FOURNIS (rôle + fichier) ; ≥ 2 fichiers
   seulement (1 fichier = empilement direct, aucune composition). Appelée au
   changement de rôle, de fichier (y compris un chemin TAPÉ, via `<Return>` /
   `<FocusOut>`), au choix de source, et par `_on_compo_roles` (qui ne réécrit
   plus la composition depuis les lignes dossier sous cette source).
3. **Verrouillage** (`_maj_compo_verrouillage`) : menu de composition, lignes
   rôle→DOSSIER, `…` et « Détecter les filtres » en `disabled` — les réglages du
   COMPOSITE restent ACTIFS. Rien n'est détruit : tout reprend son état
   (`readonly`/`normal`) dès qu'une source à dossiers revient.
4. **Présence d'un rôle** (`_role_fourni(role)`) : fichiers pour Stacks,
   dossiers sinon — sert à `_maj_fusion_ha` (état des cases) ET à
   `_lire_fusion_ha` (`continuum = case and _role_fourni("R")`).
5. **Ligne d'aide** : « Composition déduite des fichiers fournis · … ».

**VÉRIFIÉ EN RÉEL le 20/10 (mêmes 5 `canal_*.fit`)** : le cadre « Fusion Ha »
apparaît, le continuum est ACTIF et réglable, les gains / la normalisation
commune / le lissage LRGB sont accessibles, et le composite réagit aux réglages
sans redémarrer la session. **Verdict d'Alain : testé en réel, validé.**

### Diagnostic (rappel, condensé — le détail durable est dans `CLAUDE.md`)
- **Cause 1** : `est_stacks` ne rendait visible que `_lf_stacks`, alors que
  « Fusion Ha », les gains R/G/B, la normalisation commune et le lissage LRGB
  sont des ENFANTS de `frm_compo` → tout était masqué.
- **Cause 2** : `_dossier_role_compo("R")` ne lit que les lignes DOSSIER (→ `""`
  avec des FICHIERS) : continuum, Q, méthodes et recentrage désactivés, et
  `continuum` forcé à `False`.
- **Piste B** (panneau « composite » séparé) **non retenue** : la piste A a suffi,
  et un refactor plus large aurait touché `compo.py` + tous ses bancs.


### Fichiers modifiés dans cette phase (correctif piste A)
- `avastack/ui/panels/compo.py` : `cb_compo`, `cb_compo_roles`,
  `ent_compo_dossiers`, `btn_compo_dossiers`, `btn_detecter_filtres` stockés en
  attributs (+ déclarations typées) — sans eux, rien n'était verrouillable ;
- `avastack/ui/panels/stacks.py` : un chemin TAPÉ vaut un fichier choisi
  (`<Return>` / `<FocusOut>` → `_on_stacks_roles`) ;
- `avastack/ui/app.py` : `_source_est_stacks`, `_role_fourni`,
  `_roles_stacks_fournis`, `_maj_compo_depuis_stacks`, `_maj_compo_verrouillage`,
  visibilité (stacks + composition, FICHIERS d'abord), garde dans
  `_on_compo_roles`, mention de la ligne d'aide, continuum par `_role_fourni` ;
- `bancs/_test_lot5_p6_stacks.py` : section [6] (16 vérifications) sur les
  VRAIS `canal_*.fit` quand ils sont là ;
- `avastack/__init__.py` (2.96.1 + changelog), `CLAUDE.md`, `AVANCEMENT.md`.

### Décisions
- **Piste A TRANCHÉE (Alain, 20/10)** : réutiliser le panneau « Composition »
  pour les FICHIERS en verrouillant les lignes DOSSIER — piste B (panneau
  « composite » séparé) écartée comme refactor plus large sans bénéfice immédiat.
- **La composition AFFICHÉE suit la source** : fichiers → déduite (menu
  verrouillé) ; dossiers → choisie au menu. `_on_compo_roles` ne réécrit donc
  jamais la composition depuis les lignes dossier quand la source est Stacks.
- **Un seul fichier n'est pas une composition** : le cadre « Fusion Ha » est
  masqué (`_maj_fusion_ha`), même si le menu garde une composition +Ha en
  mémoire (c'est un état d'affichage, pas une session).
- Rappels P6 inchangés : **le rôle n'est JAMAIS déduit** (ni du nom, ni de
  `FILTER`, ni d'`AVAFRAME`) ; **refus sur PREUVE seulement** (`AVAVUE`
  « ETIRE ») ; **seuil de profondeur = 1** ; **`relire()` au démarrage** ;
  **`_source_fichiers()` distincte de `_cadence_dossier()`**.

### Problèmes ouverts / prochaines étapes
1. **LOT 5 = P5** (audit MESURÉ de la réactivité de l'interface) sur la branche
   **`OptimisationUI`** — **accord d'Alain avant de démarrer** (aucun code
   commencé).
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
Arbre **v2.96.1** sur la branche **`OptimisationUI`** : **P6 VALIDÉ EN RÉEL le
20/10** (piste A : composition affichée et verrouillée, composition déduite des
fichiers, continuum piloté par `_role_fourni("R")`) et **`LRGBHa` fermée** (fusion
dans `master`). **Prochaine action** : LOT 5 = P5 (audit MESURÉ de la réactivité),
sur accord d'Alain.

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
| **5** | **P5** | audit MESURÉ de la réactivité | **PROCHAIN** (aucun code commencé) |

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

### P5 — réactivité (lot 5, APRÈS P6) — **PROCHAIN**
- **Mesurer d'abord, corriger ensuite** : outil de mesure nommé
  `bancs/_mesure_p5_reactivite.py` (motif P1/P4 : chiffres AVANT le code,
  JSON conservé), plus `Guet.SEUIL_S` à 0,25 s temporairement et
  `_test_perf_reactivite_jalon79` étendu aux **cases / listes / spinners**.
- **Chiffrer** : `_add_slider.onchange` à chaque pixel, `_tick` à 30 ms,
  combobox de 147/200 valeurs, `pack/forget` de `_maj_visibilite_cadres`,
  réactivité des cases (`var.set` + `command`).
- **Correctifs APRÈS les chiffres** (coalescing ~20 Hz, écritures
  conditionnelles, tick adaptatif). Audit d'architecture éventuel : mode plan,
  AVEC ces mesures. **Un lot = un jalon, avec l'accord d'Alain.**

### P6 — source « Stacks (fichiers FITS) » (lot 4, INVERTÉ avec P5) — **VALIDÉ EN RÉEL le 20/10 (v2.96.1)**
- **Verdict d'Alain** : empilement OK le 19/10 (« test réel dans l'ensemble OK
  sur fichier sauvé par AVAStack »), puis **« testé en réel, validé » le 20/10**
  après le correctif des deux défauts d'interface.
- **DÉFAUTS CONSTATÉS puis CORRIGÉS (piste A)** : cadre « Fusion Ha » et réglages
  du composite invisibles, continuum forcé à l'arrêt → composition désormais
  AFFICHÉE et VERROUILLÉE, composition déduite des fichiers, continuum piloté
  par `_role_fourni("R")` (détail en tête de session).
- Contrat durable (rôle JAMAIS déduit, `AVAFRAME` jamais lue, profondeur non
  inventée, calibration court-circuitée, lecture unique par session, linéarité
  sur PREUVE) : `CLAUDE.md` (« Source « Stacks (fichiers FITS) » »).
- Banc `_test_lot5_p6_stacks.py` (**59** vérifications, dont 16 pour la piste A).

---

## En attente / prochaine session (état au 20/10 — branche `OptimisationUI`, v2.96.1)

- **P6 est CLOS ET VALIDÉ EN RÉEL** (v2.96.1, fusionné dans `master` ; `LRGBHa`
  fermée) : le banc P6 est vert (59 vérifications, joué avec les 5 vrais
  `canal_*.fit`) et le test réel d'Alain a confirmé l'interface.
- **Prochaine action unique** : **LOT 5 = P5** (audit MESURÉ de la réactivité),
  **avec l'accord d'Alain avant de démarrer** — mesurer d'abord
  (`bancs/_mesure_p5_reactivite.py`), corriger ensuite.
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
