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
**testée en RÉEL le 19/10** — empilement OK, **2 défauts d'interface à corriger**)
· `master` publié = **v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 (nuit) — **P6 testé en RÉEL : empilement OK, DEUX DÉFAUTS D'INTERFACE à corriger** (v2.96.0)

### État actuel
- **v2.96.0 sur `LRGBHa`** — **aucune release**. Code + doc P6 = commit
  `fb81b1d` (poussé). Base précédente : `5601f6` (doc P4 ; code P4 = `2ab5d82`).
- **ORDRE DES LOTS INVERSÉ (demande d'Alain du 19/10)** : le **lot 4 = P6**
  (source « Stacks ») est passé AVANT le **lot 5 = P5** (réactivité), qui reste
  le prochain lot et n'a reçu AUCUN début de code.
- **TEST RÉEL de P6 (19/10, Alain)** : **verdict global OK sur des fichiers
  sauvegardés par AVAStack** — la composition **LRGB+Ha** est bien détectée des
  rôles, les 5 fichiers sont lus une fois, l'empilement et l'affichage
  fonctionnent. **MAIS deux défauts d'INTERFACE** (même racine) : voir la
  section suivante — **à corriger en priorité à la prochaine session**.
- **Bancs** : P6 **vert (39 vérifications)** — dont le worker RÉEL avec un dark
  à 2,0 qui prouve que la calibration est court-circuitée. Non-régressions
  **vertes** : 19 (multifolder + compo UI/worker), 42, P1, 20 (restack compo),
  113 (b, profondeur), 115, 133, 56, 47, P4 (14 aides), 129, 76, 53, 120, 87,
  5, 41, garde-fou (**pyright 0 sur 54 fichiers typés**, surface `app.py`
  inchangée). **Les bancs ne couvrent PAS ces deux défauts** (ils ne testent pas
  la visibilité du cadre « Fusion Ha » sous la source Stacks) → à AJOUTER au
  banc P6 avec le correctif.
- **Échecs PRÉEXISTANTS** : `_test_lot1_p2_p3` volet [3] (profil SPCC déjà
  corrigé dans le `config.json` local) — inchangé, cf. « Pièges récents ».

### DÉFAUTS P6 À CORRIGER (constat réel d'Alain, 19/10) — priorité n°1
**Symptôme** : avec la source « Stacks (fichiers FITS) » et 5 rôles L/R/G/B/Ha,
la composition **LRGB+Ha** est bien déduite, mais **le cadre « Fusion Ha »
n'apparaît pas** et **rien du panneau « Composition multi-filtres » n'est
accessible** (gains R/G/B, normalisation commune, lisser le combine LRGB).

**Cause 1 — visibilité** : `_maj_visibilite_cadres` (app.py, `est_stacks`) ne
rend visible que `_lf_stacks` ; `_lf_composition` est masqué. Or le cadre
« Fusion Ha » est un ENFANT de `frm_compo` (`panels/compo.py` : `box =
self.frm_compo`, `frm_fusion_ha = ttk.LabelFrame(box, …)`) → masquer la
composition masque **aussi** la fusion Ha, les gains, la normalisation commune
et le lissage.

**Cause 2 — test de présence du R** : `_maj_fusion_ha` et `_lire_fusion_ha`
testent la couche R avec `_dossier_role_compo("R")`, qui ne lit QUE les lignes
**dossier** de la composition. Avec des FICHIERS, elle rend `""` → la case
« continuum », Q, les trois méthodes et le recentrage sont **désactivés**, et
`continuum` est forcé à `False`. Le test réel a donc tourné avec la fusion par
DÉFAUT (`ajout_rouge`, poids 1,0) et le **continuum COUPÉ** (voile rouge
possible) — sans moyen de le régler.

**Correctif prévu (piste A, recommandée — à valider par Alain avant de coder)** :
1. `_maj_visibilite_cadres` : pour `est_stacks`, visibles =
   `[self._lf_stacks, self._lf_composition]` (la composition porte les réglages
   du composite, y compris la fusion Ha).
2. `_on_stacks_roles()` : déduire `var_compo` des rôles
   (`composition_pour_roles`) puis appeler `_maj_compo_info()` (donc
   `_maj_fusion_ha`) — aujourd'hui elle n'appelle que `_maj_stacks_info`.
3. Nouvelle méthode `App._role_fourni(role)` : pour une source Stacks, lit
   `var_stacks_roles` / `var_stacks_fichiers` ; sinon `_dossier_role_compo`.
   À utiliser dans `_maj_fusion_ha` (état des cases) ET dans `_lire_fusion_ha`
   (`continuum = case and self._role_fourni("R")`).
4. Verrouiller ce qui n'a PAS de sens pour des fichiers : menu de composition
   (`cb_compo`, à stocker en attribut) en `disabled`, lignes rôle→**dossier**
   grisées ou masquées ; `lbl_compo_info` dit « composition déduite des fichiers
   fournis ». Sinon `_on_compo` réécrirait des rôles de DOSSIERS et le bandeau
   141-B signalerait un écart menteur (`var_compo` ≠ `_compo_session`).
5. Banc : étendre `_test_lot5_p6_stacks.py` — avec une sélection L/R/G/B/Ha,
   `_lf_composition` visible, `frm_fusion_ha` packé, case continuum ACTIVE
   (`_role_fourni("R")` vrai), `continuum` vrai dans `_lire_fusion_ha`, et
   `var_compo == "LRGB+Ha"` (aucun bandeau de divergence).

**Piste B (si A résiste)** : extraire « Fusion Ha » + gains + normalisation +
lissage dans un panneau propre, affiché aussi pour Stacks — plus propre à terme,
mais refactor plus large (compo.py + tous ses bancs).


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
- **À TRANCHER (nouvelle session)** : les réglages du COMPOSITE (gains,
  normalisation commune, lissage LRGB) et la FUSION Ha sont aujourd'hui rangés
  dans le seul panneau « Composition multi-filtres », dont les lignes
  rôle→DOSSIER n'ont aucun sens pour des fichiers. Piste A = réutiliser ce
  panneau en verrouillant les lignes dossier ; piste B = en extraire un panneau
  « composite ». Décision d'Alain attendue.

### Problèmes ouverts / prochaines étapes
1. **CORRIGER LES DEUX DÉFAUTS D'INTERFACE DE P6** (section ci-dessus, piste A) :
   panneau composition + cadre « Fusion Ha » inaccessibles et continuum coupé
   avec la source Stacks. **Accord d'Alain sur la piste A avant de coder.**
2. **NOUVEAU TEST RÉEL de P6** après correctif (mêmes 5 fichiers) : les réglages
   du Ha doivent apparaître, le continuum doit être ACTIF (la couche R est
   fournie) et réglable.
3. **Puis LOT 5 = P5** (audit MESURÉ de la réactivité) — accord d'Alain avant
   de démarrer.
4. **Release v2.96.x** sur accord explicite (aucune release depuis v2.80.0).

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
Arbre **v2.96.0** sur `LRGBHa` : test réel de **P6** (source « Stacks ») concluant
sur l'empilement, mais le **cadre « Fusion Ha » et les réglages du composite sont
invisibles** avec cette source et le **continuum est forcé à l'arrêt** (diagnostic
et correctif prévu en tête d'AVANCEMENT). **Prochaine action** : appliquer la
piste A, étendre `_test_lot5_p6_stacks.py`, puis re-tester en réel.

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
| **4** | **P6** | source « stacks » : fichiers choisis, **rôles saisis**, seuil de profondeur = 1 | **testé en RÉEL le 19/10** : empilement OK, **2 défauts d'INTERFACE à corriger** (fusion Ha / réglages composite invisibles) |
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
`ui/bulles.py` (`Bulle`, `astuce`, mixin `Aides` → `App._aide(...)`), 13 aides
migrées (**14** depuis le panneau Stacks), option `aides_texte` (défaut NON),
**702 px repris** (mesuré). Détail durable dans `CLAUDE.md` (« Aides
contextuelles de la colonne »).

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

### P6 — source « Stacks (fichiers FITS) » (lot 4, INVERTÉ avec P5) — **testé en RÉEL le 19/10**
- **Verdict d'Alain** : « test réel dans l'ensemble OK sur fichier sauvé par
  AVAStack » — LRGB+Ha détectée des rôles, 5 fichiers lus une fois, empilement
  et affichage corrects.
- **DÉFAUTS CONSTATÉS** : le cadre « Fusion Ha » et les réglages du composite
  (gains R/G/B, normalisation commune, lissage LRGB) sont **invisibles** avec
  cette source, et le **continuum est forcé à l'arrêt** (voir « DÉFAUTS P6 À
  CORRIGER » en tête de session : cause, correctif prévu, banc à étendre).
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
- **P6 testé en RÉEL** le 19/10 (v2.96.0) : empilement OK sur fichiers
  sauvegardés par AVAStack (LRGB+Ha déduite des rôles) ; **2 défauts
  d'INTERFACE à corriger** — cadre « Fusion Ha » et réglages du composite
  invisibles, continuum forcé à l'arrêt. Détail + correctif prévu en tête de
  session (« DÉFAUTS P6 À CORRIGER »).
- **Prochaine action unique** : **corriger ces deux défauts** (piste A : rendre
  `_lf_composition` visible pour la source Stacks, déduire/verrouiller
  `var_compo`, nouvelle `_role_fourni(role)` pour le test du R, étendre le banc
  P6), **puis re-tester en réel**. Ensuite **LOT 5 = P5** (audit MESURÉ de la
  réactivité), avec l'accord d'Alain.
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
