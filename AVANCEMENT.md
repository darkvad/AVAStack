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

Versions : `LRGBHa` = **v2.92.0** (①/②/③ validés en réel ; **136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum, **J3/J3bis** cinq modes, **J4/J4.1** continuum trois
méthodes et mesure indépendante de la case — tous **VALIDÉS EN RÉEL le 19/10** ;
**J5** ancre = couche large bande, **LIVRÉ, VALIDÉ EN RÉEL**) ·
`master` publié = **v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 — **J5 LIVRÉ, VALIDÉ EN RÉEL, POUSSÉ** (v2.92.0) → **plan P1→P6 figé**

### État actuel
- **v2.92.0 poussée sur `LRGBHa`** — **aucune release**. **J5** : dans un
  `+Ha`, l'ancre d'alignement **partagée** vient toujours d'une couche **large
  bande** ; une frame Ha ne crée plus l'empilement (attente + archive + rejeu
  dès la 1re large bande) et le Ha fusionné est **exclu** du re-ancrage.
- **VALIDÉ EN RÉEL (19/10)** : démarrage avec le dossier **Ha en premier** →
  « rejeu des brutes Ha (démarrage) · R 1/1 · Ha 1/1 » (ancre **R**) ; puis
  **re-stack manuel → 12/12** frames, aucune perte.
- **Bancs** : J5 vert (5 volets, 23 vérifications), non-régression
  19/20/129/129b/J2/J3/J4 verte, `ruff` propre, `pyright` 0.

### Décisions
- L'ancre d'un `+Ha` ne peut pas venir du Ha **parce qu'il ne se sert jamais de
  l'aligneur partagé** (voie A) — **pas** parce qu'il aurait peu d'étoiles
  (mesuré : 4 391, plus que G/B ; FWHM la plus fine, 2,46 px).
- Le score « meilleure brute » = **nombre d'étoiles** (plafond 200), pas une
  qualité : ne jamais s'en servir pour comparer des **filtres**. Un score FWHM
  serait un **jalon séparé** (il touche toutes les compositions).
- Quatre chemins posent l'ancre : ① repli et ④ rafraîchissement **verrouillés
  par le banc** ; ② création et ③ re-ancrage **fermés par le code**. Détail
  durable : `CLAUDE.md` § « Ancre d'alignement ».

### Fichiers modifiés (commit J5)
- `avastack/core/worker.py` (attente + rejeu), `avastack/ui/app.py` (exclusion
  du Ha des candidats), `bancs/_test_fusion_ha_jalon5.py`, `README.md`
  (section « Fusion du Ha »), `avastack/__init__.py` (2.92.0 + changelog),
  `CLAUDE.md`, `AVANCEMENT.md`.

### Problèmes ouverts (liste d'Alain du 19/10 — À CORRIGER AVANT LA RELEASE)
- **P1 — mesures trop rares.** Astrométrie, gains Gaia et SPCC ne mesurent
  qu'à la demande / **une seule fois** (`SessionSpcc.valide`,
  `Photometrie.valide`, WCS résolu puis propagé), dès `ASTRO_MIN_FRAMES = 3`
  — donc au pire moment. Voulu : re-mesurer en s'approfondissant, jusqu'à
  **chaque frame** en mono-dossier / **1 frame par rôle** en multi.
- **P2 — SPCC ne trouve plus les filtres MiniCam8M.** **CAUSE PROUVÉE** :
  la copie de base d'AVAStack (`%APPDATA%\AVAStack\spcc-database`, écrite
  **19/10 12:36**) a **12** `mono_filters` et **n'a pas**
  `QHYCCD_MiniCam8M_LRGB.json` ; la base Siril en a **13** et l'a. Or
  `spcc_db.dossier_base()` prend le **premier** dossier valide (config →
  copie AVAStack → Siril) : la copie incomplète **masque** la base complète.
  Aggravant : `_spcc_defaut` remplace **silencieusement** une valeur absente
  par `liste[0]` → `config.json` porte `spcc_fr = "Antlia R"` au lieu de
  `QHYCCD MiniCam8M Red` (aucun message, « Antlia R » existe dans la base).
- **P3 — astrométrie en fin de brutes.** Toujours vrai, mais **seulement**
  si l'astrométrie n'était pas cochée ou est décochée/recochée : le WCS
  manque et **entraîne** Gaia + SPCC. Cause exacte :
  `_servir_demandes_sans_frame` (app.py:5720) sert `_spcc_demande` et
  `_photo_demande` mais **pas l'astrométrie** (aucun `_astro_demande`), et
  `_astro_tour` n'est appelé qu'après un re-stack.
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
1. **Lot 1 (prochain jalon)** : P2 (code seul, **sans réparer la base à la
   main** — Alain veut vérifier que le correctif suffit) + P3.
2. Puis P1, P4, P5, P6 — un jalon par lot, **demander l'accord d'Alain
   avant chaque nouveau lot**.
3. **Release v2.92.0** sur accord explicite, une fois les correctifs faits.


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
Arbre **v2.92.0 poussé** sur `LRGBHa` : **J2 à J5 VALIDÉS en réel**, `pyright` 0,
**aucune release**. **Prochaine action** : **Lot 1 = P2 + P3** (base SPCC la
plus riche + zéro substitution silencieuse ; `_astro_demande` en fin de source),
puis test réel avec les filtres MiniCam **sans réparer la base à la main**.

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
| **1** | **P2 + P3** | base SPCC la plus riche, zéro substitution silencieuse, `_astro_demande` | **PROCHAIN** |
| 2 | P1 | cadence de re-mesure Gaia/SPCC | en attente |
| 3 | P4 | infobulles ⓘ | en attente |
| 4 | P5 | audit MESURÉ de la réactivité | en attente |
| 5 | P6 | source « stacks » : fichiers choisis, **rôles saisis**, seuil de profondeur = 1 | en attente |

### Lot 1 — P2 : spécifications
- `spcc_db.dossier_base()` : priorité au dossier choisi EXPLICITEMENT
  (`chemin_spcc`) ; sinon **la base la plus riche** (nb de profils) entre copie
  AVAStack et Siril, choix + compteurs au journal. Chez Alain, Siril (13
  filtres) doit gagner sur la copie incomplète (12), **sans rien copier**.
- `telechargeur` : refuser qu'une extraction rende la base **plus pauvre**, ne
  jamais supprimer un profil existant (garde + message).
- UI : **plus aucune substitution silencieuse** ; défauts **par canal**
  (RED/GREEN/BLUE) et non `liste[0]` ; valeur absente = conservée + alerte.
- Cas réel : si le profil enregistré vient d'un **autre modèle** que le défaut
  du champ ET que ce défaut existe dans la base → défaut REPOSÉ avec message
  (`Antlia R` → `QHYCCD MiniCam8M Red`) ; sinon avertir seulement.
- `_profil` : exact, puis normalisé (casse/espaces), puis sous-chaîne ; échec
  = message avec les **noms les plus proches**.
- Garde-fou : `FILTER` de la brute courante (« QHYCCD MiniCam8M… ») ≠ modèle du
  profil choisi → **avertissement rouge**.
- Banc : bases factices 12 vs 13 → Siril gagne ; valeur absente → pas de
  substitution ; `Antlia R` → défaut MiniCam reposé ; nom plus long que la base
  → résolution normalisée.

### Lot 1 — P3 : spécifications
- `_astro_demande` posé par `_on_astro` (re-cochage), par un changement
  d'indices et par la **fin de source**.
- `_servir_demandes_sans_frame` : **astro D'ABORD**, puis photo, puis SPCC ;
  après une astro résolue, reposer `_photo_demande` / `_spcc_demande` si leurs
  cases sont cochées (c'est le « ça entraîne le reste »).
- Consommée une fois, pas de boucle : essais/délais/WCS restent seuls juges.
- Banc : fin de source + astro décochée → re-cochage = 1 solve, puis photo et
  SPCC sans nouvelle frame ; aucun appel si le WCS est déjà résolu.

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
- **Sélection de fichiers**, PAS un dossier : jusqu'à `NB_LIGNES_COMPO` (5)
  lignes **rôle → fichier** (bouton …), chaque FITS venant d'où l'on veut.
- **Le RÔLE est celui INDIQUÉ DANS LA LIGNE, jamais déduit** : un stack peut
  venir de Siril, PixInsight, APP… (`canal_*.fit`, `FILTER`, `AVAFRAME` ne
  sont PAS des contrats). L'en-tête sert au plus de **pré-remplissage
  indicatif** ; s'il porte un `FILTER` **différent** du rôle choisi → simple
  avertissement, **le choix de l'utilisateur fait foi** (même esprit que les
  dossiers de composition).
- **Profondeur : `AVAFRAME` N'EST PAS LUE** (non fiable hors AVAStack). Pour
  cette source, le **seuil effectif de profondeur vaut 1**
  (`_seuil_profondeur()` : 1 si source stacks, sinon `ASTRO_MIN_FRAMES`) —
  astro, Gaia et SPCC peuvent donc mesurer dès le premier passage.
  `SuiviAstrometrie.peut_essayer` reçoit ce seuil (défaut inchangé = 3).
- **Aucun chiffre inventé** : les messages disent « empilement fourni
  (profondeur non vérifiée) » au lieu d'un « N frames » déduit.
- `avastack/cameras/stacks.py` : `StackFilesCamera` lit chaque fichier **une
  fois** et rend `(image, rôle)` (contrat `MultiFolderCamera`) →
  `_mode_compo`, composition déduite **des rôles saisis**, tout l'aval
  inchangé (fusion Ha, couleurs, SPCC, Gaia, sauvegardes, fiches).
- **Calibration IGNORÉE** (couche déjà empilée), cadence/rafale inactives,
  lecture unique puis silence ; un seul fichier = composition **Mono**.
- **Linéarité** : refus seulement si l'en-tête AVAStack dit explicitement non
  linéaire ; sinon, pour un fichier venu d'ailleurs, **avertissement MESURÉ**
  (fond médian et plage de valeurs) quand l'image ne ressemble pas à du
  linéaire — **jamais un refus sur une supposition**.
- Ajout à `cameras.SOURCES`, panneau dédié, persistance rôle/fichier.
- Banc : `M33_Canaux_LRGBHa` → LRGB+Ha déduite **des rôles**, seuil de
  profondeur = 1, zéro calibration, lecture unique ; un FITS sans en-tête
  AVAStack (imité Siril/PixInsight) passe quand même ; `FILTER` contradictoire
  → avertissement sans changer le rôle.

---

## En attente / prochaine session (état au 19/10 — `LRGBHa`, v2.92.0)

- **J2 à J5 sont CLOS** (validés en réel le 19/10) : cinq modes de fusion,
  continuum à trois méthodes (repli VISIBLE, mesure indépendante de la case) et
  ancre d'un `+Ha` toujours large bande.
- **Prochaine action unique** : **Lot 1 = P2 + P3** (cf. « Chantier en cours —
  Améliorations d'usage »). **Rien ne part en release avant.**
- **Ensuite** : P1 (cadence), P4 (infobulles), P5 (audit réactivité), P6
  (source stacks par fichiers) — **accord d'Alain avant chaque lot**.
- **Puis** : **release v2.92.0** sur accord explicite.
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

- **Une base SPCC neuve peut être PLUS PAUVRE que celle de Siril et la
  masquer** : `dossier_base()` prend le premier dossier valide, et
  `base_complete()` ne vérifie que « les cinq catégories sont non vides ». La
  copie AVAStack du 19/10 a **12** `mono_filters` sans
  `QHYCCD_MiniCam8M_LRGB.json` alors que la base Siril en a **13** → filtres
  MiniCam introuvables, et `liste[0]` a remplacé `spcc_fr` par « Antlia R ».
  Vérifier les COMPTEURS par catégorie avant de conclure à un bug de mesure.

- **Un jeu SANS le défaut ne mesure que l'ABSENCE DE COÛT** : 109 frames sans
  retournement donnaient « retirer `phase` ne change rien » ; sur **Sh2-132**
  (204 frames, **31 retournements**), la phase finalisait 22 frames dont 21 Ha
  fausses de 1,1 à 2,3 px. Vérifier que le défaut est REPRÉSENTÉ (compter les
  |angle| > 170°, pas seulement les refus) avant de conclure.
- **Une réussite de repli n'est pas une preuve d'alignement** : `phase` en
  translation seule a posé 11/50 puis 12/49 frames B **à l'envers**. Un banc
  teste le **chemin de décision** (espion) et son coût sur une frame douce.
- **Échecs PRÉEXISTANTS** : `_test_espace_jalon72` (géométrie d'écran),
  `_test_reset_empilement_jalon76` [4] (course `_stop()`, sensible à la charge CPU).
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`.

---

## Clôtures précédentes

- **19/10/2026** : **J5 VALIDÉ EN RÉEL** (v2.92.0, poussé) — ancre d'un `+Ha`
  toujours large bande (démarrage ancre R + Ha rejouée ; re-stack 12/12) ;
  **aucune release**.
- **19/10/2026** : **J4/J4.1 VALIDÉS en réel** (v2.91.1) — trois méthodes de
  continuum, mesure indépendante de la case « recentrer ».
