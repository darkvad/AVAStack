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

Versions : `LRGBHa` = **v2.96.0** (**136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum, **J3/J3bis** cinq modes, **J4/J4.1** continuum trois
méthodes et mesure indépendante de la case — tous **VALIDÉS EN RÉEL le 19/10** ;
**J5** ancre = couche large bande, **VALIDÉ EN RÉEL** ; **Lot 1 (P2 + P3)** base
SPCC la plus riche + astrométrie servie sans frame, **VALIDÉ EN RÉEL le 19/10** ;
**P7** recalcul après un choix de couleur, **CORRIGÉ ET VALIDÉ EN RÉEL le 19/10** ;
**P1** cadence de re-mesure, **VALIDÉ EN RÉEL le 19/10** ; **P4** infobulles
« ⓘ », **VALIDÉ EN RÉEL le 19/10** ; **P6** source « Stacks (fichiers FITS) »,
**LIVRÉ le 19/10** — **test réel en attente**)
· `master` publié = **v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 (nuit) — **LOT 5 = P6 LIVRÉ** (v2.96.0, à valider en réel) — lots 4/5 INVERSÉS

### État actuel
- **v2.96.0 sur `LRGBHa`** — **aucune release**. Dernier commit poussé avant ce
  lot : `5601f6` (doc, base `2ab5d82` pour P4).
- **ORDRE DES LOTS INVERSÉ (demande d'Alain du 19/10)** : le **lot 5 = P6**
  (source « Stacks ») passe AVANT le **lot 4 = P5** (réactivité), qui devient le
  prochain lot. P5 n'a reçu AUCUN début de code : son audit mesuré reste à faire.
- **P6 LIVRÉ, EN ATTENTE DE TEST RÉEL** : nouvelle source « Stacks (fichiers
  FITS) » — un FITS par filtre choisi, **rôle indiqué** (jamais deviné), lecture
  **une fois** par fichier, **calibration ignorée**, **seuil de profondeur = 1**,
  messages « empilement fourni (profondeur non vérifiée) », refus seulement si
  l'en-tête AVAStack dit « ETIRE » (sinon avertissement MESURÉ).
  Détail durable dans `CLAUDE.md` (« Source « Stacks (fichiers FITS) » »).
- **Bancs** : P6 **vert (39 vérifications)** — dont le worker RÉEL avec un dark
  à 2,0 qui prouve que la calibration est court-circuitée. Non-régressions
  **vertes** : 19 (multifolder), 42 (cadence), P1, compo worker 19, 113, 115,
  133, 56, 47 (visibilité), P4 (14 aides), 129, 76 (2e passage), 53, 120, 113b,
  87, 5, 41, garde-fou (**pyright 0 sur 54 fichiers typés**, surface `app.py`
  inchangée) ; `ruff` propre sur les fichiers touchés.
- **Échecs PRÉEXISTANTS** : `_test_lot1_p2_p3` volet [3] (profil SPCC déjà
  corrigé dans le `config.json` local) — inchangé, cf. « Pièges récents ».

### Fichiers modifiés (session P6)
- `avastack/cameras/stacks.py` (**neuf, typé**) : `StackFilesCamera`
  (`read()` → `(image, rôle)` à plusieurs, image seule à un ; `relire()` ;
  `pending` ; aucune pose unitaire), `entete_avastack`, `dit_etire`
  (motif `\bETIRE\b`), `avertissement_lineaire` (mesure) ;
- `avastack/cameras/__init__.py` : export + entrée « Stacks (fichiers FITS) » ;
- `avastack/ui/panels/stacks.py` (**neuf, typé**) : 5 lignes rôle + fichier,
  ligne d'aide, 14e aide « ⓘ » ;
- `avastack/ui/constants.py` : section pliable `stacks` ;
- `avastack/ui/app.py` : panneau + héritage, visibilité par source,
  `_make_camera`, `_lire_roles_fichiers_stacks`, `_maj_stacks_info`,
  `_mode_compo_de`, `_source_stacks`, `_source_fichiers`,
  `_seuil_profondeur`, `_suffixe_cadence`, `_meme_fichier`,
  fermeture/réouverture sur sélection changée, avertissements au journal ;
- `avastack/core/worker.py` : calibration court-circuitée, mesures après
  lecture de TOUS les fichiers, seuil de profondeur, messages, `relire()` +
  seuil des cadences à chaque démarrage, pause qui ne lit rien ;
- `avastack/processing/astrometrie.py` : `peut_essayer(..., seuil=…)` ;
- `avastack/ui/config_ui.py` : `stacks_role_i` / `stacks_fichier_i` (aucune
  sonde disque à la restauration) ;
- `bancs/_test_lot5_p6_stacks.py` (neuf, 39 vérifications),
  `bancs/_test_p1_cadence.py`, `_test_lot1_p2_p3.py`,
  `_test_astro_profondeur_jalon113.py`, `_test_astro_domaine_jalon115.py`,
  `_test_p4_aides.py` (13 → 14 aides), `_test_refactoring_garde_fou.py` ;
  `avastack/__init__.py` (2.96.0 + changelog), `CLAUDE.md`, `AVANCEMENT.md`.

### Décisions
- **Inversion 4/5 demandée par Alain** : P6 d'abord, P5 ensuite — aucun code de
  P5 n'est laissé en chantier.
- **Le rôle n'est JAMAIS déduit** : ni du nom (`canal_*.fit`), ni de `FILTER`,
  ni de `AVAFRAME` (jamais lue). Un FILTER contradictoire = avertissement dans
  le panneau ; le choix de l'utilisateur fait foi.
- **Refus sur PREUVE seulement** : `AVAVUE` disant « ETIRE » ; tout le reste est
  accepté avec une mesure au journal (fond médian, part de pixels à 1,00).
- **Seuil de profondeur = 1 pour cette source** (`App._seuil_profondeur`), et
  `seuil` passé explicitement à `peut_essayer` (défaut inchangé pour tous les
  autres appelants).
- **`relire()` au démarrage** : sans lui, « Démarrer » après « Arrêter »
  repartait d'un empilement VIDE (défaut trouvé par le banc, pas en réel).
- **`_source_fichiers()` distincte de `_cadence_dossier()`** : la fin de source
  et la pause concernent toute source de FICHIERS ; la cadence reste réservée
  aux dossiers.

### Problèmes ouverts / prochaines étapes
1. **TEST RÉEL de P6 par Alain** (référence : `C:\Astro\test\M33_Canaux_LRGBHa`,
   5 `canal_*.fit` → LRGB+Ha déduite des rôles). À surveiller : astrométrie
   (les couches n'ont ni OBJCTRA/OBJCTDEC ni RA/DEC — saisir AD/Dec ou utiliser
   ASTAP), SPCC, enregistrements par canal.
2. **Puis LOT 4 = P5** (audit MESURÉ de la réactivité) — **accord d'Alain avant
   de démarrer**.
3. **Release v2.96.x** sur accord explicite (aucune release depuis v2.80.0).

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
Arbre **v2.96.0** sur `LRGBHa` : Lot 1, P7, P1 et **P4 validés en réel** le
19/10, **P6 livré** (source « Stacks ») et **en attente de test réel**, aucune
release. **Prochaine action** : tester P6 sur `C:\Astro\test\M33_Canaux_LRGBHa`
(5 rôles L/R/G/B/Ha), puis **LOT 5 = P5** — mesurer la réactivité AVANT tout
correctif.

---

## Chantier CLOS — LRGB+Ha (jalons 129 → J5) — **J2 à J5 validés en réel**

Le rôle Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le
combine L. **Tout est CLOS et VALIDÉ EN RÉEL le 19/10** (J2 v2.88.0, J3bis
v2.90.2, J4 v2.91.0, J4.1 v2.91.1, J5 v2.92.0) : les règles durables (poids 1,0 ·
α 0,5 · Q 0,80 · continuum trois méthodes avec repli VISIBLE · ancre = couche
large bande) vivent dans `CLAUDE.md` (« Fusion du Ha… ») et le changelog.

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
| **4** | **P6** | source « stacks » : fichiers choisis, **rôles saisis**, seuil de profondeur = 1 | **LIVRÉ le 19/10** (v2.96.0) — **test réel en attente** ; lots 4/5 INVERSÉS |
| **5** | **P5** | audit MESURÉ de la réactivité | **PROCHAIN** (aucun code commencé) |

### Lot 1 — P2 + P3 : **VALIDÉ EN RÉEL le 19/10** (v2.93.0) — détails dans `CLAUDE.md`
Base SPCC **la plus riche** (compteurs au journal, extraction jamais plus pauvre,
défauts par canal, valeur absente conservée + alerte, garde FILTER rouge) et
`_astro_demande` (service astro → photo → SPCC, demande consommée UNE fois).
Banc `bancs/_test_lot1_p2_p3.py` (7 volets, 51 vérifications).

### P1 — cadence (lot 2) : **VALIDÉ EN RÉEL le 19/10** (v2.94.0) — détails dans `CLAUDE.md`
`processing/cadence.py` (`CadenceMesure`) : seuil 3 → passe finale → plafond 6 →
doublement (3→6→12→24…) → délai 20 s, branche dans `_astro_tour` /
`_photo_tour` / `_spcc_tour`, passe finale armée par `_armer_astro_fin_source`.
Mesuré AVANT de coder : 6,87 s de mesures pour 65 s d'empilement (JSON
`bancs/_mesure_p1_cadence.json`) ; banc `_test_p1_cadence.py` (29 vérifications).

### P4 — infobulles (lot 3) — **VALIDÉ EN RÉEL le 19/10 (v2.95.0)**
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

### P6 — source « Stacks (fichiers FITS) » (lot 4, INVERTÉ avec P5) — **LIVRÉ le 19/10 (v2.96.0), test réel en attente**
- **Sélection de FICHIERS**, pas un dossier : jusqu'à `NB_LIGNES_COMPO` (5)
  lignes **rôle → fichier** ; le **RÔLE est celui INDIQUÉ**, jamais déduit
  (`canal_*.fit`, `FILTER`, `AVAFRAME` ne sont PAS des contrats ; un `FILTER`
  contradictoire n'est qu'un avertissement, le choix de l'utilisateur fait foi).
- **`AVAFRAME` n'est PAS lue** ; seuil de profondeur **forcé à 1** pour cette
  source (`App._seuil_profondeur`, passé à `peut_essayer`), sinon astro/Gaia/
  SPCC seraient bloqués. Messages : « empilement fourni (profondeur non
  vérifiée) », aucun « N frames » inventé.
- `avastack/cameras/stacks.py` : `StackFilesCamera` lit chaque fichier **une
  fois** et rend `(image, rôle)` → `_mode_compo`, composition déduite des rôles,
  tout l'aval inchangé. **Calibration ignorée**, cadence/rafale inactives, un
  seul fichier = **Mono**. `relire()` au démarrage d'une session.
- **Linéarité** : refus SEULEMENT si l'en-tête AVAStack dit « ETIRE » ; sinon
  **avertissement MESURÉ** (fond médian, part de pixels à 1,00) au journal.
- Mesures : attendues APRÈS la lecture de TOUS les fichiers (la source est
  finie), armées une fois à la fin de source.
- Ajout à `cameras.SOURCES`, panneau dédié (`ui/panels/stacks.py`), persistance
  `stacks_role_i` / `stacks_fichier_i`. Banc `_test_lot5_p6_stacks.py` (39
  vérifications) : `M33_Canaux_LRGBHa` → LRGB+Ha déduite des rôles, seuil 1,
  zéro calibration (dark 2,0), lecture unique ; FITS sans en-tête AVAStack
  accepté.

---

## En attente / prochaine session (état au 19/10 — `LRGBHa`, v2.96.0)

- **J2 à J5 sont CLOS** (validés en réel le 19/10).
- **Lot 1 (P2 + P3) VALIDÉ EN RÉEL** le 19/10 : SPCC/MiniCam et astrométrie à
  l'empilement arrêté.
- **P7 VALIDÉ EN RÉEL** le 19/10 (v2.93.1) : `_pousser_rendu()` force la chaîne,
  `_vl_params()` porte `params_corrections()`.
- **P1 VALIDÉ EN RÉEL** le 19/10 (v2.94.0) : `processing/cadence.py`, branches
  dans `_photo_tour` / `_spcc_tour` / `_astro_tour`, passe finale dans
  `_armer_astro_fin_source`, états avec échéance.
- **P4 VALIDÉ EN RÉEL** le 19/10 (v2.95.0) : `ui/bulles.py` (`Bulle` +
  `astuce` + mixin `Aides`), 13 aides migrées (+1 en P6 = **14**), option
  `aides_texte`, **702 px repris** (mesuré). Détail en « P4 — infobulles ».
- **P6 LIVRÉ** le 19/10 (v2.96.0) — **TEST RÉEL EN ATTENTE** : source « Stacks
  (fichiers FITS) », rôles saisis, calibration ignorée, seuil de profondeur 1.
  Détail en « P6 — source Stacks ».
- **Prochaine action unique** : **TEST RÉEL de P6** sur
  `C:\Astro\test\M33_Canaux_LRGBHa` (5 `canal_*.fit`, rôles L/R/G/B/Ha →
  LRGB+Ha), puis **LOT 5 = P5** (audit MESURÉ de la réactivité, aucun correctif
  avant les chiffres), **avec l'accord d'Alain**.
- **Puis** : **release v2.96.x** sur accord explicite.
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

- **19/10/2026** : **P4 VALIDÉ EN RÉEL** (v2.95.0) — 13 aides de la colonne en
  infobulles « ⓘ » + option « Aides en texte » ; 702 px repris (mesuré).
- **19/10/2026** : **P1 VALIDÉ EN RÉEL** (v2.94.0) — `processing/cadence.py`,
  re-mesure 3→6→12…, passe finale en fin de source ; aucune release.
