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

Versions : **`OptimisationUI` = v2.97.0** — **P5 « rendu AU RELÂCHEMENT »
IMPLÉMENTÉ le 20/10** (banc vert, chiffres après correctif mesurés), **à VALIDER
EN RÉEL** ; aucune release. **`master` = v2.96.1** : **136** halo coloré, **137**
neutralisation après étirement en STF, **141-B** interface, **J2** fusion du Ha
au rouge + continuum, **J3/J3bis** cinq modes, **J4/J4.1** continuum trois
méthodes et mesure indépendante de la case, **J5** ancre = couche large bande,
**Lot 1 (P2 + P3)** base SPCC la plus riche + astrométrie servie sans frame,
**P7** recalcul après un choix de couleur, **P1** cadence de re-mesure, **P4**
infobulles « ⓘ », **P6** source « Stacks (fichiers FITS) » + ses 2 défauts
d'interface (piste A) — tous **VALIDÉS EN RÉEL** (19 et 20/10).
· `master` publié = **v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 20/10/2026 — **P6 VALIDÉ EN RÉEL** (v2.96.1), puis **P5 IMPLÉMENTÉ** (v2.97.0, **à tester en réel**)

### État actuel
- **v2.96.1 sur `master`** — P6 **VALIDÉ EN RÉEL par Alain le 20/10** (« testé en
  réel, validé ») : cadre « Fusion Ha », réglages du composite et continuum
  accessibles avec la source « Stacks ». **Aucune release** (`fb81b1d` = P6,
  `efb2911` = correctif piste A, fusionné dans `master`).
- **Branche de travail : `OptimisationUI`** (depuis `master`, poussée et suivie).
  **`LRGBHa` fermée** (local + `origin`).
- **P5 « RENDU AU RELÂCHEMENT » IMPLÉMENTÉ le 20/10 (v2.97.0)** sur
  `OptimisationUI` — mesuré d'abord, corrigé ensuite, **commité EN LOCAL, pas
  poussé**. `_add_slider` : rien pendant le glissement, **UN aperçu au
  relâchement**, minuteur de secours (150 ms, rafale = 1 aperçu), filet (600 ms)
  si le relâchement se perd ; gestes discrets et `_poser_curseur` **immédiats**
  (`_forcer_rendu_curseur` / `_rendre_curseurs`). Banc NEUF
  `bancs/_test_p5_rendu_relachement.py` (**20 vérifications, vert**).
- **PROCHAINE ACTION : test réel d'Alain** — c'est LUI qui dira si l'absence de
  retour PENDANT le geste gêne (et si l'« aperçu réduit » devient utile ;
  il n'est PAS codé).
- **Bancs rejoués verts après le correctif** : P5 (20), jalon 79 (**29**),
  jalon 6 (boutons ±), jalon 120 (restauration), garde-fou (**pyright 0 sur 54
  fichiers typés**, surface publique d'`app.py` inchangée). **Échec
  PRÉEXISTANT** inchangé : `_test_lot1_p2_p3` volet [3] (profil SPCC déjà
  corrigé dans `config.json`).

### P5 — LES CHIFFRES AVANT (20/10, `--n 5`, **fenêtre PLEIN ÉCRAN**, aperçu **1600×1200**)
> JSON : `bancs/_mesure_p5_reactivite.json`. Rejouer :
> `python bancs/_mesure_p5_reactivite.py` (écran requis ; `--autotest` sans écran).
> **Correction du 20/10 (remarque d'Alain)** : le premier passage avait été fait
> sur un aperçu de banc 360×560 — **ce n'est pas l'usage réel**. L'application
> plafonne l'aperçu à **1600 px de côté** (`min(1, 1600/max(h,w))`) et dessine à
> la taille du CANVAS : les chiffres ci-dessous sont les VRAIS (canvas mesuré
> **1548×744**, aperçu **1,92 Mpx**).

| ce qui est mesuré | chiffre |
|---|---|
| geste gamma / saturation (après étirement) | **250–326 ms** |
| geste « fond du ciel » / « coupure du bruit » / black | **364–383 ms** |
| aperçu complet / sans histogrammes | **306 ms** / 261 ms (histogrammes **53 ms**, dessin **14 ms**) |
| courbe de taille : 560×360 → 1280×720 → 1600×1200 | **59 → 143 → 302 ms** |
| clic de case (`invoke`) | **284–299 ms** (1 aperçu) ; **auto-STF 326 ms** (2,33 aperçus) |
| cran de spinner / `sp.set` nu | **311–332 ms** / 0,01 ms (0 rappel) |
| `var.set` nu (case / liste / spinner) | **0 rappel** (piège Tk, prouvé) |
| rafale (60 pas, boucle ACTIVE) | **20,15 s** (336 ms/pas), **60 battements au lieu de 671**, écart max **395 ms** |
| opérations > **0,25 s** (Guet abaissé) | **21** (pire : **409 ms**) |
| glissement de **200 px** (théorique, la file) | **50 s → 76 s** |
| charge pour suivre 60 Hz de souris | **2 284 % d'un cœur** |

**Lecture** : un seul aperçu coûte **~300 ms**, dont **14 ms de dessin** → le coût
est le **pipeline numpy** (étirement/saturation/histogrammes), pas Tk. Cliquer une
case, c'est donc déjà ~300 ms d'attente (constat d'Alain : « même les clics sur
les cases mettent un temps certain »). `_tick`, les listes (147 valeurs) et
`pack/forget` restent HORS DE CAUSE. **Décision d'Alain** : pendant un glissement
on ne calcule **RIEN**, **un seul aperçu AU RELÂCHEMENT** (le coalescing n'était
qu'un pis-aller) ; l'**aperçu réduit n'est PAS retenu** à ce stade.

### P5 — LES CHIFFRES APRÈS le correctif (même outil, même taille, 20/10 — v2.97.0)

| ce qui est mesuré | avant | après |
|---|---|---|
| un PAS de glissement de souris | **~300 ms** (un aperçu PAR pixel) | **0,036 ms** |
| aperçus pour un glissement complet | 1 par pixel | **1** (au relâchement) |
| glissement de **200 px** | **50 à 76 s** | **230–324 ms** |
| rafale 60 pas, boucle ACTIVE | **20,15 s**, 60 aperçus, 60 battements / 671 attendus | **1,35 s**, **1 aperçu**, 31 battements / 44 attendus, écart max 254 ms |
| charge pour suivre 60 Hz de souris | **2 284 %** d'un cœur | **0,22 %** |
| aperçu complet / sans histogrammes | 306 / 261 ms | **252 / 204 ms** (inchangé, c'est le prix d'UN aperçu) |
| clic de case / cran de spinner | 284–326 / 311–332 ms | **inchangés** (~250–300 ms, 1 aperçu) |

**Lecture** : le coût d'un geste n'est plus proportionnel au NOMBRE de pixels
parcourus mais à **un seul aperçu** — c'est exactement l'arbitrage d'Alain. Le
prix assumé : pendant le geste, l'image ne correspond plus à la valeur affichée
(elle rattrape au relâchement). **Ce qui reste à ~300 ms** (case, spinner, un
relâchement) est le pipeline numpy d'un aperçu : hors du champ de P5.



### Le correctif P6 (piste A) — **CLOS, détail durable dans `CLAUDE.md`**
- Visibilité (`_lf_stacks` + `_lf_composition`), composition **déduite**
  (`_maj_compo_depuis_stacks`) et **verrouillage** (`_maj_compo_verrouillage`),
  présence d'un rôle (`_role_fourni`, pilote aussi le continuum). **Piste B
  écartée** (refactor plus large).

### Fichiers modifiés dans cette phase
- `avastack/ui/app.py` : **P5** — `_add_slider` (rendu au relâchement, minuteur,
  filet, gestionnaires de geste), `_forcer_rendu_curseur`, `_rendre_curseurs`,
  `_poser_curseur` (+ rendu forcé), `_on_auto` et 🔒 logD (forcent avant leur
  rendu explicite), constantes `DELAI_SECOURS_CURSEUR_MS` (150) et
  `DELAI_SECOURS_GLISSE_MS` (600) ;
- `bancs/_test_p5_rendu_relachement.py` (**neuf**) : contrat P5, **20
  vérifications** (câblage, zéro calcul pendant le geste, image du relâchement
  identique au bit, filet, gestes discrets, coalescence du minuteur) ;
- `bancs/_mesure_p5_reactivite.py` : sections **[1]** et **[8]** réécrites sur le
  VRAI geste (`_debut_glissement`/`_fin_glissement`) + comptage des aperçus ;
- `bancs/_test_perf_reactivite_jalon79.py` : le helper `geste()` **force** le
  rendu (un `s.set()` seul ne rend plus) ;
- `bancs/_mesure_p5_reactivite.json` : passage APRÈS correctif (rejouable) ;
- `avastack/__init__.py` : **v2.97.0** + changelog ; `CLAUDE.md` : leçon durable
  « rendu au relâchement » + piège `event_generate`/focus ;
- (P6, déjà livré) `panels/compo.py`, `panels/stacks.py`,
  `bancs/_test_lot5_p6_stacks.py`.


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
  même information, rien à remettre en état après coup.
- **P5 — RENDU AU RELÂCHEMENT (décision d'Alain, 20/10)** : un glissement de
  curseur ne déclenche **AUCUN** calcul ; la variable et l'étiquette suivent
  (≈ 0 ms) et l'aperçu part au `<ButtonRelease-1>`. Les gestes **DISCRETS**
  (boutons `-`/`+`, flèches clavier, zone de saisie, `_poser_curseur`) rendent
  **immédiatement** (un seul aperçu). **Garde-fou** : sans relâchement (focus
  perdu, `s.set` programmatique), un minuteur (~150 ms) déclenche le rendu —
  jamais d'image périmée. **Prix assumé** : pendant le glissement, l'image ne
  correspond plus à la valeur affichée.
- **NON retenu à ce stade** : l'aperçu RÉDUIT pendant le geste (~80–100 ms à
  800×600). À n'ajouter qu'APRÈS un test réel, et sur demande d'Alain.
- **P5 — IMPLÉMENTATION (20/10, v2.97.0)** : un seul chemin de rendu différé
  (`_rendre`) pour le minuteur ET le relâchement ⇒ jamais deux aperçus pour un
  même changement ; le relâchement rend par **`after_idle`** (les liaisons de
  CLASSE du `ttk.Scale` posent la valeur finale du clic APRÈS notre liaison
  d'évènement) ; **filet de 600 ms** ajouté pour un geste stoppé sans
  relâchement (aucun aperçu pendant un geste qui bouge, mais jamais d'image
  figée) ; **`_poser_curseur` FORCE le rendu** — déviation assumée par rapport au
  « bonus ~1 aperçu à la restauration » : une restauration doit être complète en
  sortant (`_test_restauration_curseurs_jalon120` lit `disp.*` juste après
  `App()`), et le bonus était de toute façon théorique (aucune image au
  démarrage ⇒ 40 aperçus qui ne dessinaient rien).

### Problèmes ouverts / prochaines étapes
1. **TEST RÉEL D'ALAIN — P5** (branche `OptimisationUI`, v2.97.0, **rien n'est
   poussé**) : lancer `python AVAStack.py`, puis, sur une vraie image :
   - glisser **Gamma**, **Saturation**, **Luminosité du fond du ciel**,
     **Coupure du bruit**, **Black point** : l'image ne doit **pas** bouger
     pendant le geste et se mettre à jour **UNE fois** au relâchement ;
   - vérifier que l'étiquette suit le doigt pendant le geste ;
   - éprouver les **gestes discrets** : boutons `-`/`+`, flèches clavier,
     saisie du gain (caméra), et la restauration de config au démarrage ;
   - **c'est LUI qui juge** si l'absence de retour pendant le geste gêne. Si
     oui → l'« **aperçu réduit** » (800×600 pendant le geste) sera ajouté, et
     seulement sur sa demande.
2. **Release v2.97.x** sur accord explicite (aucune release depuis v2.80.0 ;
   `master` porte la fusion de `LRGBHa`). Ne pas oublier : le lot 5 sera alors
   **clos** (P5 validé) — c'était le DERNIER lot du plan figé du 19/10.



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
Arbre **v2.97.0** sur **`OptimisationUI`** : **P5 « rendu au relâchement » est
IMPLÉMENTÉ et vert au banc** (20 vérifications ; jalon 79, jalon 6, jalon 120 et
garde-fou/pyright 0 rejoués OK), chiffres après correctif mesurés (1 aperçu par
geste, 0,036 ms par pas, rafale 1,35 s). **Prochaine action unique** : **test
réel d'Alain** de P5 (glissements + gestes discrets) — rien n'est poussé, aucune
release.


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
| **5** | **P5** | audit MESURÉ de la réactivité | **IMPLÉMENTÉ le 20/10 (v2.97.0)** — mesuré, puis « rendu au RELÂCHEMENT » codé et vert au banc ; **TEST RÉEL À FAIRE** |

### Lots 1 → 3 et 4 — **VALIDÉS EN RÉEL** (détails dans `CLAUDE.md` + changelog)
- **Lot 1** : P2 + P3 (v2.93.0, base SPCC la plus riche + astrométrie servie sans
  frame) puis **P7** (v2.93.1) ; **Lot 2** : P1 (v2.94.0, `processing/cadence.py`) ;
  **Lot 3** : P4 (v2.95.0, infobulles ⓘ, **702 px repris**) ; **Lot 4** : P6
  (v2.96.0/2.96.1, source « Stacks » + piste A — banc **59** vérifications,
  `_test_lot5_p6_stacks.py`).

### P5 — réactivité (lot 5) — **CORRIGÉ le 20/10 (v2.97.0), à valider en réel**
- Outil `bancs/_mesure_p5_reactivite.py` (10 sections, `--autotest` sans écran,
  JSON rejouable), **sans modification du produit** pour la mesure : seuil du
  Guet inchangé (1,5 s), le banc compte lui-même les opérations > 0,25 s.
- **Suspicions LEVÉES** : `_tick` (0,3 % du budget), listes SPCC 147 valeurs
  (0,2 ms), `pack/forget` (0,5 ms). **Confirmée** : un aperçu complet par pixel
  de souris. Chiffres avant/après en tête de session.
- Banc `_test_perf_reactivite_jalon79` : 29 vérifications vertes (+ sections
  cases / listes / spinners), et **banc NEUF** `_test_p5_rendu_relachement.py`
  (20 vérifications).



### P6 — source « Stacks (fichiers FITS) » (lot 4) — **CLOS : VALIDÉ EN RÉEL (v2.96.1)**
- Empilement OK le 19/10, puis **« testé en réel, validé »** le 20/10 après le
  correctif des deux défauts d'interface (piste A). Contrat durable et banc
  (**59** vérifications) : `CLAUDE.md` + changelog.


---

## En attente / prochaine session (état au 20/10 — branche `OptimisationUI`, v2.97.0)

- **P5 est IMPLÉMENTÉ** (v2.97.0) : banc NEUF
  `bancs/_test_p5_rendu_relachement.py` **vert (20 vérifications)**, chiffres
  après correctif au JSON `bancs/_mesure_p5_reactivite.json`. **Rien n'est
  poussé, aucune release.**
- **Prochaine action UNIQUE** : **test réel d'Alain** (glissements de curseurs +
  gestes discrets). C'est LUI qui jugera si l'absence de retour PENDANT le geste
  gêne ; l'« aperçu réduit » n'est PAS codé et ne le sera que sur sa demande.
- **Puis** : **release v2.97.x** sur accord explicite (`master` porte tout le
  chantier depuis v2.80.0 ; `master` est à v2.96.1).

- **Référence chiffrée** : `C:\Astro\test\M33_Canaux_LRGBHa` (5 `canal_*.fit` +
  fiches ; `AVACOMPO` = LRGB+Ha, **normalisation COMMUNE**, lissage 117d).
  Rejouer : `python bancs/_diag_fusion_ha_echelles.py --canaux <dossier>
  --norm-commune --lissage-halos --poids 1.5` (`--autotest` contrôle l'outil).
- **Ne pas retoucher** : `ajout_rouge` (AU BIT), la formule `bandes_passantes`
  7 nm, α, le poids, le principe « repli = bandes passantes AU BIT ».
- **Optionnel** : cible qui REMPLIT le cadre (repli attendu et DIT) et filtre
  **3 nm** si Alain en a un.
- **141-B validée** (rien à retester) ; **teinte des COINS** notée, sans action.
- Retour arrière en un geste (correctif P5 seul) : `git checkout HEAD~1 --
  avastack/ui/app.py avastack/__init__.py` (+ remettre `AVASTACK_VERSION` à
  2.96.1 en cas de doute).

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

- **P5 — un curseur ne rend plus par `set()`** : depuis le rendu au relâchement,
  `s.set()` ne fait que la variable et l'étiquette (minuteur 150 ms). Un banc ou
  un code qui veut l'effet TOUT DE SUITE appelle
  `app._forcer_rendu_curseur(s)` (un curseur) ou `app._rendre_curseurs()` (tous)
  AVANT un rendu explicite — sinon le rendu part avec les `disp.*` précédents.
  Un geste se simule par `s._debut_glissement()` / `s._fin_glissement()`.
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
