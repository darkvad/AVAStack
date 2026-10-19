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

Versions : `LRGBHa` = **v2.93.0** (①/②/③ validés en réel ; **136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum, **J3/J3bis** cinq modes, **J4/J4.1** continuum trois
méthodes et mesure indépendante de la case — tous **VALIDÉS EN RÉEL le 19/10** ;
**J5** ancre = couche large bande, **VALIDÉ EN RÉEL** ; **Lot 1 (P2 + P3)** base
SPCC la plus riche + astrométrie servie sans frame, **VALIDÉ EN RÉEL le 19/10**
(SPCC et astro empilement arrêté) — **P7 ouvert**) · `master` publié =
**v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 (soir) — **Lot 1 VALIDÉ EN RÉEL** (SPCC + astro empilement arrêté) → **P7 noté, handoff**

### État actuel
- **v2.93.0 sur `LRGBHa`** — **aucune release**. Commits locaux `011981c`
  (Lot 1) + `d69add3` (correctifs du test réel), **non poussés**.
- **Lot 1 VALIDÉ EN RÉEL par Alain (19/10)** : ① la SPCC trouve et applique les
  filtres **MiniCam** (base Siril 13 retenue, `Antlia R` → `QHYCCD MiniCam8M
  Red`) ; ② l'**astrométrie fonctionne à l'empilement arrêté** (P3).
- **Deux défauts du premier test réel corrigés le 19/10** : le champ
  « Filtre R » recevait `osc_filtres` (MiniCam introuvables au clic) → listes
  selon le **TYPE** ; l'avis « profil remplacé » était rouge et permanent →
  **ambre et temporisé** (12 s), les vrais problèmes seuls restent en rouge.
- **Bancs** : Lot 1 vert (7 volets, **51 vérifications**, dont l'UI réelle),
  non-régressions 58 / 58 bis / 56 astro / 56 photo / 6 / 5 / 113 / 133 / 124
  vertes ; `ruff` propre ; `pyright` 0.
- **NOUVEAU — P7** (un choix de correction de couleur ne recalcule pas toujours,
  ou avec le choix précédent) : voir « Problèmes ouverts » — cause probable
  LOCALISÉE, **aucun code touché** (handoff demandé).

### Décisions
- **La richesse se compte en FICHIERS .json** (pas en objets) : compter les
  objets parserait tous les JSON à chaque `dossier_base()`, appelée par chaque
  `lister()`. Le choix est journalisé **une fois par décision**.
- **`liste[0]` n'est JAMAIS un défaut** : défaut **par canal** ; sans défaut
  possible, la valeur est **conservée et signalée** (journal + ligne rouge).
- **Repose de modèle seulement avec majorité** : les DEUX autres canaux
  doivent désigner le même modèle ET le défaut du canal doit exister dans ce
  modèle ; sinon on avertit seulement. Un choix manuel fait toujours foi.
- **P3 : la fin de source est une TRANSITION** (jamais un état) et ne concerne
  que les sources FICHIERS ; sur une caméra live, `read()` vide entre deux
  poses n'est pas une fin.

### Fichiers modifiés (commit Lot 1)
- `avastack/catalogues/spcc_db.py` (base la plus riche + compteurs + journal),
  `avastack/catalogues/telechargeur.py` (gardes de richesse),
  `avastack/processing/spcc.py` (`_profil`, défauts par canal,
  `profils_filtres`, `filtre_compatible`, noms proches),
  `avastack/ui/app.py` (`_astro_demande`, service astro d'abord, alertes,
  garde FILTER), `avastack/ui/config_ui.py` (valeurs conservées + vérif),
  `avastack/ui/panels/stack.py` (choix manuel = alerte effacée),
  `avastack/core/worker.py` (fin de source, garde FILTER, reset),
  `bancs/_test_lot1_p2_p3.py` (neuf), `bancs/_test_sans_siril_jalon77.py`
  (contrat P2), `avastack/__init__.py` (2.93.0 + changelog), `CLAUDE.md`,
  `AVANCEMENT.md`.


### Problèmes ouverts (liste d'Alain du 19/10) — **P2 et P3 VALIDÉS EN RÉEL**
- **P1 — mesures trop rares** (LOT 2) : astrométrie, gains Gaia et SPCC ne
  mesurent qu'à la demande / **une seule fois** (`SessionSpcc.valide`,
  `Photometrie.valide`, WCS résolu puis propagé), dès `ASTRO_MIN_FRAMES = 3`
  — donc au pire moment. Voulu : re-mesurer en s'approfondissant, jusqu'à
  **chaque frame** en mono-dossier / **1 frame par rôle** en multi.
- **P2 — SPCC / filtres MiniCam8M : CORRIGÉ ET VALIDÉ EN RÉEL (19/10).**
  Base Siril (13) retenue, filtres MiniCam proposés et appliqués, profil
  `Antlia R` reposé en `QHYCCD MiniCam8M Red` (avis ambre temporisé + journal).
- **P3 — astrométrie en fin de brutes : CORRIGÉ ET VALIDÉ EN RÉEL (19/10)** —
  fonctionne **empilement arrêté**.
- **P7 — NOUVEAU (Alain, 19/10) : un choix de correction de couleur ne
  recalcule pas toujours l'image, ou la recalcule avec le choix PRÉCÉDENT.**
  « Des fois » seulement → suspecter une COURSE, pas une absence de code.
  **Cause probable LOCALISÉE (aucune mesure faite, aucun code touché)** :
  · les gains de couleur (SPCC / Gaia) ne sont **pas** écrits par l'UI : le
    worker d'acquisition les pose dans le stacker **à son tour suivant**
    (`core/worker.py` ~563-643), puis lève `_rafraichir_rendu` et pousse le
    rendu. Entre le clic et ce tour, l'UI peut rendre avec les gains
    PRÉCÉDENTS — et quand on passe à SPCC, `spcc.valide` est faux tant que la
    mesure n'a pas abouti, donc `nouveaux = {}` : l'image est rendue SANS
    correction, puis corrigée au tour d'après ;
  · côté VeraLux, la clé de mémoïsation `display._vl_params()` (749) ne
    contient **NI les gains, NI l'équilibrage, NI le Linear Fit** : si les
    corrections sont appliquées DANS la chaîne (`display.py:997`,
    `corrections_couleur`), un changement de choix ne change pas la clé
    (1203/1210) → l'image VeraLux en cache est **republiée à l'identique**.
  **À FAIRE (prochain lot, avec mesure)** : reproduire en STF **et** en
  VeraLux, journaliser la séquence clic → gains posés → rendu ; décider entre
  ⓐ attendre/forcer un rendu après la pose des gains (UI informée par un
  compteur de version) et ⓑ faire entrer l'état des corrections dans
  `_vl_params`. Banc : espion sur `_pousser_rendu` + gains changés sans frame.
- **P4 — place perdue dans la colonne gauche.** Les textes d'aide (31
  étiquettes grises `wraplength`) doivent devenir des **infobulles** sur un
  **ⓘ** posé à côté du champ concerné.
- **P5 — contrôles moins réactifs** (cases, listes, spinners, curseurs) :
  audit **mesuré** avant correctifs (cf. chantier).
- **P6 — nouvelle source = stacks déjà empilés**, par **SÉLECTION DE
  FICHIERS** (un FITS par filtre voulu, où qu'ils soient — pas un dossier
  unique). **Rôle indiqué par l'utilisateur** (jamais déduit : un stack peut
  venir d'un autre logiciel) et **seuil de profondeur forcé à 1** pour cette
  source, sinon `ASTRO_MIN_FRAMES` bloquerait astro/Gaia/SPCC. But : tester
  sans réempiler les brutes.

### Prochaines étapes
1. **P7 D'ABORD** (correctif du Lot 1, à trancher avec Alain) : reproduire et
   mesurer la course « choix de couleur → recalcul », puis corriger (ⓐ et/ou
   ⓑ ci-dessus) avec un banc.
2. **Puis Lot 2 = P1** (cadence de re-mesure) — **accord d'Alain avant**.
3. **Puis P4, P5, P6** — un jalon par lot.
4. **Release v2.93.0** sur accord explicite, une fois P7 et les lots voulus
   faits.


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
Arbre **v2.93.0** sur `LRGBHa` : **Lot 1 (P2 + P3) VALIDÉ EN RÉEL** (SPCC/
MiniCam + astro empilement arrêté), banc neuf vert, `pyright` 0, commits locaux
`011981c` + `d69add3` **non poussés**, **aucune release**. **Prochaine action** :
**P7** — au clic sur un choix de correction de couleur, l'image ne se recalcule
pas toujours ou garde le choix précédent (course : gains posés par le worker au
tour suivant ; clé `_vl_params` sans les corrections) — mesurer puis corriger
avant **Lot 2 = P1**.

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
| **1** | **P2 + P3** | base SPCC la plus riche, zéro substitution silencieuse, `_astro_demande` | **VALIDÉ EN RÉEL le 19/10** (SPCC + astro empilement arrêté) — **P7 ouvert** |
| 2 | P1 | cadence de re-mesure Gaia/SPCC | **PROCHAIN après P7 (accord d'Alain)** |
| 3 | P4 | infobulles ⓘ | en attente |
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

### P1 — cadence (lot 2)
- Re-mesure quand la profondeur **double** (3 → 6 → 12 → 24…), délai minimal
  20 s, **plafond** de re-mesures ; **passe finale** quand la source s'épuise.
- Multi-dossier : profondeur = **min des rôles R/G/B** (`_profondeur_spcc`),
  donc « 1 frame de chaque ». WCS jamais re-solvé une fois résolu.
- L'état affiché dit la profondeur mesurée et la prochaine échéance.

### P4 — infobulles (lot 3)
- `avastack/ui/bulles.py` : `Bulle` (Toplevel `overrideredirect`, 400 ms,
  souris + clavier) et `astuce(widget, texte)` ; helper `App._aide()`.
- Migrer les **31** étiquettes d'aide par panneau (commencer par Stack/mesure).
- Option de config « Aides en texte dans la colonne » (défaut NON).

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

## En attente / prochaine session (état au 19/10 — `LRGBHa`, v2.93.0)

- **J2 à J5 sont CLOS** (validés en réel le 19/10).
- **Lot 1 (P2 + P3) est VALIDÉ EN RÉEL** le 19/10 : SPCC/MiniCam et astrométrie
  à l'empilement arrêté. Correctifs du test réel inclus (listes selon le TYPE,
  avis de correction temporisé). **Rien ne part en release avant P7.**
- **P7 est OUVERT** (choix de correction de couleur : recalcul manquant ou
  valeur précédente) — cause probable localisée, **à mesurer puis corriger**
  (cf. « Problèmes ouverts »).
- **Prochaine action unique** : **diagnostiquer P7** (STF **et** VeraLux,
  séquence clic → gains posés → rendu), puis le corriger ; **ensuite**
  **Lot 2 = P1** sur accord d'Alain.
- **Ensuite** : P4 (infobulles), P5 (audit réactivité), P6 (source stacks par
  fichiers) — **accord d'Alain avant chaque lot**.
- **Puis** : **release v2.93.0** sur accord explicite.
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

- **P7 — un choix de couleur peut rendre avec l'ANCIEN réglage** : les gains
  SPCC/Gaia sont écrits dans le stacker par le **worker** (tour suivant), et la
  clé VeraLux `_vl_params()` ne contient ni gains, ni équilibrage, ni Linear
  Fit. Ne pas conclure « la case ne fait rien » : mesurer la séquence clic →
  gains posés → rendu (STF **et** VeraLux) avant de corriger.
- **Échecs PRÉEXISTANTS** : `_test_espace_jalon72` (géométrie d'écran),
  `_test_reset_empilement_jalon76` [4] (course `_stop()`, sensible à la charge
  CPU) et, dans `_test_sans_siril_jalon77`, « ligne Base SPCC rognée de 1-2 px »
  + « menu écrasé » (prouvés sur HEAD dans un worktree : flaky, la longueur du
  dossier temporaire décide).
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

- **19/10/2026** : **LOT 1 VALIDÉ EN RÉEL** (v2.93.0, commits locaux `011981c`
  + `d69add3`, non poussés) — SPCC/MiniCam + astro empilement arrêté ; les deux
  défauts du test réel corrigés ; **P7 ouvert**, aucune release.
- **19/10/2026** : **J5 VALIDÉ EN RÉEL** (v2.92.0, poussé) — ancre d'un `+Ha`
  toujours large bande (démarrage ancre R + Ha rejouée ; re-stack 12/12).
