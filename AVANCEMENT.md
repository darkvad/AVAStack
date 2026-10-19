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

Versions : `LRGBHa` = **v2.95.0** (**136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum, **J3/J3bis** cinq modes, **J4/J4.1** continuum trois
méthodes et mesure indépendante de la case — tous **VALIDÉS EN RÉEL le 19/10** ;
**J5** ancre = couche large bande, **VALIDÉ EN RÉEL** ; **Lot 1 (P2 + P3)** base
SPCC la plus riche + astrométrie servie sans frame, **VALIDÉ EN RÉEL le 19/10** ;
**P7** recalcul après un choix de couleur, **CORRIGÉ ET VALIDÉ EN RÉEL le 19/10** ;
**P1** cadence de re-mesure, **VALIDÉ EN RÉEL le 19/10** ; **P4** infobulles
« ⓘ », **LIVRÉ le 19/10 — à valider en réel**)
· `master` publié = **v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 (nuit) — **LOT 3 = P4 LIVRÉ** (v2.95.0) → **à valider en réel**

### État actuel
- **v2.95.0 sur `LRGBHa`** — **aucune release**. Code P4 = commit `2ab5d82`,
  **poussé** (`origin/LRGBHa`). Base poussée précédente : `e53d7eb` (doc P1,
  code P1 = `cb75201`).
- **P4 est CODÉ, MESURÉ et BANCS VERTS ; reste la VALIDATION EN RÉEL.**
  Les 13 textes d'aide de la colonne gauche sont devenus des infobulles
  derrière un « ⓘ » ; l'option « Aides en texte dans la colonne » rétablit
  l'ancien affichage (défaut NON, bascule immédiate, persistée).
- **Mesure faite AVANT et APRÈS le code** (`bancs/_mesure_p4_aides.py`,
  VRAIE interface, sections ouvertes par le banc, JSON
  `bancs/_mesure_p4_aides.json`) : **avant** 13 aides = **1 267 px = 84,5
  lignes = 23,5 % de la colonne** ; **après** colonne **5 405 → 4 703 px =
  702 px repris** (46,8 lignes, **13 % de la colonne**), les 13 « ⓘ » coûtant
  247 px au total. Gain plus grand encore cadres « Fusion Ha » / « Affichage »
  dépliés (l'aide du Ha à elle seule : 304 px).
- **Bancs** : P4 **vert (34 vérifications)** ; non-régressions 72 / 47 / 19 /
  5 / 41 / 84 / 87 / 48.3 / 79 / 6 **vertes** ; garde-fou VERT (pyright **0**
  sur **52** fichiers typés, surface de `app.py` inchangée) ; `ruff` propre.
- **Échec PRÉEXISTANT confirmé sur HEAD** (worktree) : banc 72 « aucun widget
  écrasé : `('écrasé', 'Menu', 'Menu', 99, 1300)` » — reproduit SANS ce lot.
  Banc Lot 1 `[7]` (profil SPCC déjà corrigé dans le `config.json` local) :
  inchangé, préexistant.

### Fichiers modifiés (session P4)
- `avastack/ui/bulles.py` (**neuf, typé**) : `Bulle` (Toplevel
  `overrideredirect`, 400 ms, une seule à la fois, ramenée dans l'écran),
  `astuce(widget, texte)` (souris + clavier, `<Destroy>` nettoie) et mixin
  `Aides` (`_aide`, `_placer_aide`, `_on_aides_texte`, `_maj_aides`) ;
- `avastack/ui/app.py` : import `_Aides` (alias PRIVÉ → surface inchangée),
  héritage, `_aides` / `_aides_mode_texte` posés AVANT `_build_ui()` ;
- `avastack/ui/panels/files.py` : case « Aides en texte dans la colonne »
  (ligne dédiée) + `_globals_app` local ;
- `avastack/ui/config_ui.py` : `aides_texte` persisté à la fermeture ;
- `avastack/ui/panels/{compo,color,bgnoise,external,display}.py` : 13 aides
  migrées vers `self._aide(...)` (2 posées SUR une ligne de réglage :
  `ligne=row_lh`, `ligne=row_fq`) + déclaration `_aide` pour pyright ;
- `bancs/_test_p4_aides.py` (neuf, 34 vérifications),
  `bancs/_mesure_p4_aides.py` (neuf) + `bancs/_mesure_p4_aides.json`,
  `bancs/_test_refactoring_garde_fou.py` (liste typée + `bulles.py`) ;
  `avastack/__init__.py` (2.95.0 + changelog), `CLAUDE.md`, `AVANCEMENT.md`.

### Décisions
- **Le compte réel est 13, pas 31** : la liste du 19/10 comptait TOUTES les
  étiquettes grises `wraplength`, y compris les lignes d'ÉTAT (`lbl_*`) qui
  portent une information VIVANTE et ne doivent pas devenir des bulles.
  Mesuré à l'AST puis à l'exécution : 13 textes d'aide statiques.
- **Un point de passage unique** `App._aide(...)` (mixin `Aides`) : c'est lui
  qui crée l'étiquette ET le « ⓘ », donc l'option bascule TOUT d'un coup.
- **Défaut = bulles** (l'option « Aides en texte » est DÉCOCHÉE), et la case
  vit dans « Fichiers de travail et journal » (panneau « application », en
  haut de la colonne) ; la ligne des boutons était pleine → ligne dédiée.
- **`ligne=` quand la ligne du réglage existe** : le « ⓘ » s'y pose à droite,
  coût ZÉRO — jamais sur une ligne contenant `expand=True` (leçon jalon 72).
- **Pas de bulle sur le panneau histogramme** (hors colonne gauche, à droite) :
  sa légende reste un texte ; à faire seulement si Alain le demande.

### Problèmes ouverts (liste d'Alain du 19/10) — **P1, P2, P3, P7 VALIDÉS ; P4 à valider**
- **P1, P2, P3, P7 : VALIDÉS EN RÉEL** le 19/10 (détails durables dans
  `CLAUDE.md` : cadence de re-mesure, base SPCC la plus riche, astrométrie
  servie en fin de source, recalcul après un choix de couleur).
- **P4 — place perdue dans la colonne gauche : LIVRÉ (v2.95.0)**, à VALIDER
  EN RÉEL : survoler les « ⓘ » (400 ms), vérifier qu'une bulle ne sort jamais
  de l'écran, cocher « Aides en texte dans la colonne » (retour à l'ancien
  affichage, sans redémarrer) et rouvrir l'application (choix conservé).

### Prochaines étapes
1. **VALIDER P4 EN RÉEL** (Alain) : bulles ⓘ, option texte, persistance.
2. **Puis LOT 4 = P5** (audit MESURÉ de la réactivité) — **accord d'Alain
   avant chaque lot**.
3. **Puis LOT 5 = P6** (source « stacks » par fichiers).
4. **Release v2.95.x** sur accord explicite (aucune release depuis v2.80.0).

### Rappel des lots suivants (liste d'Alain du 19/10)
- **P5 — contrôles moins réactifs** (cases, listes, spinners, curseurs) : audit
  **mesuré** avant correctifs (cf. chantier).
- **P6 — nouvelle source = stacks déjà empilés**, par **SÉLECTION DE
  FICHIERS** (un FITS par filtre voulu, où qu'ils soient — pas un dossier
  unique). **Rôle indiqué par l'utilisateur** (jamais déduit : un stack peut
  venir d'un autre logiciel) et **seuil de profondeur forcé à 1** pour cette
  source, sinon `ASTRO_MIN_FRAMES` bloquerait astro/Gaia/SPCC. But : tester
  sans réempiler les brutes.

---
## Points d'attention
- **TROIS noms de composition** (141-B) : `stacker.composition`/`_compo_nom`,
  `_compo_session`, `var_compo` ; **`"RGB+Ha"` est une sous-chaîne de
  `"LRGB+Ha"`** ⇒ jamais `startswith`/`in` pour identifier une composition.
- **J2 — fusion ACTIVE PAR DÉFAUT** : `fusion_ha = None` = défauts figés ;
  désactiver = `{"poids": 0.0}`. Le réglage entre dans la clé de mémoïsation et
  dans `disp.vl_compo`.
- **J2 — continuum** : actif par défaut, **case ET Q désactivés sans dossier
  R** ; l'échelle R est le DÉNOMINATEUR de normalisation du Ha (ne pas le
  remplacer par 1 sans regarder le mode de normalisation).
- **J3bis — les cinq modes ne touchent que le ROUGE** (V/B au bit) ;
  `ha_luminance` = gain **à porte** (0,05–0,25) : ne pas baisser la porte sous
  0,05 sans refaire la mesure.
- **Une brute est DITHÉRÉE** : seul un empilement ALIGNÉ prouve quelque chose ;
  `--dossier` sans `--dark` = run invalide dès que l'exposition change.
- **Un jeu SANS le défaut ne mesure que l'ABSENCE DE COÛT** : vérifier que le
  défaut est REPRÉSENTÉ (ex. retournements) avant de conclure « aucun coût ».
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`. Bancs UI :
  `cv2.ocl.setUseOpenCL(False)`, `ui.CONFIG = {}`, `ui.App._dire` patché
  (boîte MODALE, sinon blocage), jamais `grid` + `pack` dans le même conteneur.

### Contexte de reprise (à coller — 2 phrases)
Arbre **v2.95.0** sur `LRGBHa` : **LOT 3 = P4 LIVRÉ** (infobulles « ⓘ », option
« Aides en texte », 702 px repris — mesuré), Lot 1 / P7 / P1 **validés en réel**
le 19/10, **aucune release**, pas encore poussé. **Prochaine action** :
**VALIDER P4 EN RÉEL**, puis **LOT 4 = P5** (audit mesuré de la réactivité).

---

## Chantier CLOS — LRGB+Ha (jalons 129 → J5) — **J2 à J5 validés en réel**

Le rôle Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le combine L.

| Jalon | Contenu | État |
|---|---|---|
| J1 / 129 (v2.81.0) | compositions + 5 lignes UI + séparation ancre / `_narrowband_ha` | commité |
| 129b | voie A (référence **PAR RÔLE** + recalage de l'empilement) + `profondeur_min` + refus par rôle | COMMITÉ ; validé en réel le 16/10 (441 frames, 2 refus en R) |
| **130 (v2.82.0)** | combine LRGB borné [0 ; 5] + repli local + fiche + banc neuf | COMMITÉ + POUSSÉ (`ef0c35c`) |
| **J2 (v2.88.0)** | fusion « ajout au rouge » + poids 1,0 + recentrage + **continuum (Q, case)** + cadre « Fusion Ha » | **VALIDÉ EN RÉEL le 19/10** |
| **J3bis (v2.90.2)** | les 4 opérateurs dans l'espace de R ; `ha_luminance` = gain **à porte** (0,05–0,25) ; `ajout_rouge` au bit | **VALIDÉ EN RÉEL (19/10)** |
| **J4 (v2.91.0)** | continuum **trois méthodes** (`bandes_passantes` 7/3 nm, `mediane`, `etoiles_5sigma`), **repli visible**, case « recentrer » | **VALIDÉ EN RÉEL le 19/10** |
| **J4.1 (v2.91.1)** | la **mesure** ne dépend plus de la case (fond de ciel), seuil médiane 1,20 | **VALIDÉ EN RÉEL le 19/10 (soir)** |
| **J5 (v2.92.0)** | ancre = couche **large bande** (une frame Ha ne crée plus l'empilement ; Ha exclu du re-ancrage) + doc README | **VALIDÉ EN RÉEL le 19/10** |

Plan figé (13 arbitrages du 15/10) : poids **1,0** (0–10) · α **0,5** · Q **0,80**
(0,10–2,00) · cadre « Fusion Ha » visible seulement si la compo contient Ha ·
continuum = **bandes passantes** (Ha 7 nm / RGB 100 nm), référence **R** ·
identifiants en français (`synthetise`).

---

## Chantier en cours — Améliorations d'usage (P1 → P6) — **PLAN FIGÉ le 19/10**

**Un lot = un jalon** ; demander l'accord d'Alain avant chaque nouveau lot.
**LOT 0 SUPPRIMÉ** (décision d'Alain) : la base SPCC n'est PAS réparée à la
main — le correctif de code doit suffire, et le test réel le prouve.

| Lot | Points | Contenu | État |
|---|---|---|---|
| **1** | **P2 + P3** | base SPCC la plus riche, zéro substitution silencieuse, `_astro_demande` | **VALIDÉ EN RÉEL le 19/10** ; **P7 validé en réel** (v2.93.1) |
| 2 | P1 | cadence de re-mesure Gaia/SPCC | **VALIDÉ EN RÉEL le 19/10** (v2.94.0) |
| 3 | P4 | infobulles ⓘ | **LIVRÉ (v2.95.0) — à VALIDER EN RÉEL** |
| 4 | P5 | audit MESURÉ de la réactivité | en attente |
| 5 | P6 | source « stacks » : fichiers choisis, **rôles saisis**, seuil de profondeur = 1 | en attente |

### Lot 1 — P2 + P3 : **VALIDÉ EN RÉEL le 19/10** (v2.93.0) — détails durables dans `CLAUDE.md`
- **P2** : base **la plus riche** (compteurs au journal), extraction jamais plus
  pauvre, défauts **par canal**, valeur absente **conservée + alerte**,
  `Antlia R` → `QHYCCD MiniCam8M Red` (message + journal), `_profil` exact →
  normalisé → sous-chaîne + noms proches, garde **FILTER** rouge.
- **P3** : `_astro_demande` (cochage / indices / **fin de source** / reset),
  service **astro → photo → SPCC**, repose des mesures après une résolution,
  demande consommée **une fois**.
- **Banc** : `bancs/_test_lot1_p2_p3.py` (7 volets, 51 vérifications) — vert,
  dont la liste R réelle (50 filtres mono, valeur affichée présente) et l'avis
  de correction effacé.

### P1 — cadence (lot 2) — **VALIDÉ EN RÉEL le 19/10 (v2.94.0)**
- **Mesuré AVANT de coder** (`bancs/_mesure_p1_cadence.py`, 89 brutes réelles
  vdB 126 180 s OSC, paliers 3/6/12/24/48) : astro 3,11 s puis 0 (WCS
  propagé) ; Gaia 0,44→0,91 s ; SPCC 0,74→1,01 s ; **6,87 s** de mesures pour
  **65 s** d'empilement. Le coût ne justifie aucun délai plus long.
- **Où c'est décidé maintenant** : `processing/cadence.py` (`CadenceMesure`),
  appelé par `core/worker.py` `_astro_tour` (profondeur consignée),
  `_photo_tour` et `_spcc_tour` (décision + quota d'échecs séparé) ;
  `_armer_astro_fin_source` arme la passe finale photo/SPCC.
- **Règles** : seuil 3 → passe finale → plafond 6 → doublement (3→6→12→24…)
  → délai 20 s. La profondeur de décision est `_profondeur_spcc` (« min des
  rôles R/G/B », donc 1 frame de plus dans CHAQUE bande). WCS jamais re-solu.
- **Bancs** : `_test_p1_cadence.py` (29 vérifications, chemin de décision,
  espion) ; `_mesure_p1_cadence.py --autotest`.
- **Validé en réel** : les lignes Photométrie/SPCC disent la profondeur mesurée
  et la prochaine échéance, et la mesure se rafraîchit en s'approfondissant.

### P4 — infobulles (lot 3) — **LIVRÉ (v2.95.0), à valider en réel**
- `avastack/ui/bulles.py` (neuf, typé) : `Bulle` (Toplevel `overrideredirect`,
  400 ms, **une seule à la fois**, ramenée dans l'écran) et `astuce(widget,
  texte)` (souris + clavier : survol, FocusIn/Out, Échap, clic) ; mixin
  `Aides` → `App._aide(parent, texte, ligne=…, padx=…, pady=…)`.
- **13** aides migrées (compo 3, color 4, bgnoise 2, external 3, display 1) ;
  celles du panneau Composition et du cadre « Fusion Ha » se posent SUR une
  ligne de réglage (`ligne=row_lh`, `ligne=row_fq`) → coût zéro.
- Option **`aides_texte`** (défaut NON = bulles) : case « Aides en texte dans
  la colonne » dans « Fichiers de travail et journal », bascule **à chaud**,
  persistée à la bascule ET à la fermeture.
- **Mesure** : `bancs/_mesure_p4_aides.py` (avant/après, JSON conservé) —
  **702 px repris** (46,8 lignes, 13 % de la colonne ; 5 405 → 4 703 px).
- **Banc** : `bancs/_test_p4_aides.py`, 34 vérifications, VERT.

### P5 — réactivité (lot 4)
- Mesurer d'abord : `Guet.SEUIL_S` à 0,25 s temporairement, banc
  `_test_perf_reactivite_jalon79` étendu aux cases/listes/spinners.
- Chiffrer : `_add_slider.onchange` à chaque pixel, `_tick` 30 ms, combobox de
  147/200 valeurs, `pack/forget` de `_maj_visibilite_cadres`.
- Correctifs APRÈS les chiffres (coalescing ~20 Hz, écritures conditionnelles,
  tick adaptatif). Audit d'architecture éventuel : mode plan, AVEC ces mesures.

### P6 — source « Stacks (fichiers FITS) » (lot 5)
- **Sélection de FICHIERS**, pas un dossier : jusqu'à `NB_LIGNES_COMPO` (5)
  lignes **rôle → fichier** ; le **RÔLE est celui INDIQUÉ**, jamais déduit
  (`canal_*.fit`, `FILTER`, `AVAFRAME` ne sont PAS des contrats ; un `FILTER`
  contradictoire n'est qu'un avertissement, le choix de l'utilisateur fait foi).
- **`AVAFRAME` n'est PAS lue** ; seuil de profondeur **forcé à 1** pour cette
  source (`_seuil_profondeur()`), sinon astro/Gaia/SPCC seraient bloqués.
  Messages : « empilement fourni (profondeur non vérifiée) », aucun « N frames »
  inventé.
- `avastack/cameras/stacks.py` : `StackFilesCamera` lit chaque fichier **une
  fois** et rend `(image, rôle)` → `_mode_compo`, composition déduite des rôles,
  tout l'aval inchangé. **Calibration ignorée**, cadence/rafale inactives, un
  seul fichier = **Mono**.
- **Linéarité** : refus seulement si l'en-tête AVAStack dit non linéaire ;
  sinon **avertissement MESURÉ** (fond médian, plage) pour un fichier venu
  d'ailleurs — jamais un refus sur une supposition.
- Ajout à `cameras.SOURCES`, panneau dédié, persistance rôle/fichier. Banc :
  `M33_Canaux_LRGBHa` → LRGB+Ha déduite des rôles, seuil 1, zéro calibration,
  lecture unique ; FITS sans en-tête AVAStack accepté.

---

## En attente / prochaine session (état au 19/10 — `LRGBHa`, v2.95.0)

- **J2 à J5 sont CLOS** (validés en réel le 19/10).
- **Lot 1 (P2 + P3) VALIDÉ EN RÉEL** le 19/10 : SPCC/MiniCam et astrométrie à
  l'empilement arrêté.
- **P7 VALIDÉ EN RÉEL** le 19/10 (v2.93.1) : `_pousser_rendu()` force la chaîne,
  `_vl_params()` porte `params_corrections()`.
- **P1 VALIDÉ EN RÉEL** le 19/10 (v2.94.0) : `processing/cadence.py`, branches
  dans `_photo_tour` / `_spcc_tour` / `_astro_tour`, passe finale dans
  `_armer_astro_fin_source`, états avec échéance.
- **P4 LIVRÉ** le 19/10 (v2.95.0), **à VALIDER EN RÉEL** : `ui/bulles.py`
  (`Bulle` + `astuce` + mixin `Aides`), 13 aides migrées, option
  `aides_texte` (« Aides en texte dans la colonne »), **702 px repris**.
  Détail en « P4 — infobulles ».
- **Prochaine action unique** : **validation réelle de P4** (survol des ⓘ,
  option texte, persistance après redémarrage).
- **Ensuite** : **LOT 4 = P5** (audit MESURÉ de la réactivité), puis **P6**
  (source stacks par fichiers) — **accord d'Alain avant chaque lot**.
- **Puis** : **release v2.95.x** sur accord explicite (et `git push` du lot).
- **Optionnel** : cible qui REMPLIT le cadre (repli attendu et DIT) et filtre
  **3 nm** si Alain en a un.
- **Référence chiffrée** : `C:\Astro\test\M33_Canaux_LRGBHa` (5 `canal_*.fit` +
  fiches ; `AVACOMPO` = LRGB+Ha, **normalisation COMMUNE**, lissage 117d).
  Rejouer : `python bancs/_diag_fusion_ha_echelles.py --canaux <dossier>
  --norm-commune --lissage-halos --poids 1.5` (`--autotest` contrôle l'outil).
- **Ne pas retoucher** : `ajout_rouge` (AU BIT), la formule `bandes_passantes`
  7 nm, α, le poids, le principe « repli = bandes passantes AU BIT ».
- **141-B validée** (rien à retester) ; **teinte des COINS** notée, sans action.
- Retour arrière en un geste : `git checkout -- avastack/core/worker.py
  avastack/ui/app.py`.

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

- **19/10/2026** : **P1 VALIDÉ EN RÉEL** (v2.94.0) — `processing/cadence.py`,
  re-mesure 3→6→12…, passe finale en fin de source ; poussé, aucune release.
- **19/10/2026** : **P7 VALIDÉ EN RÉEL** (v2.93.1) — un choix de correction de
  couleur recalcule l'image (forçage du rendu + corrections dans la clé).
