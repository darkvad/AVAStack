# AVANCEMENT.md — mémoire de travail à court terme

(Complète `CLAUDE.md`, mémoire LONG terme. Ici : état courant, décisions, pièges
actifs, prochaine action. Le **récit des chantiers terminés** vit dans
`CLAUDE-ARCHIVES.md` ; le détail version par version dans `avastack/__init__.py`
(changelog) et `git log`.)

---

## ⚠️ BRANCHE DE TRAVAIL ACTIVE — **`master`** (depuis le 21/10/2026)

**`OptimisationUI` est FUSIONNÉE dans `master`** (merge `20755bf`) et **tout
travail futur se fait sur `master`**.

> **RÈGLE FERME** : `master` est la branche de travail ET de release.
> **`LRGBHa` est FERMÉE** — ne pas la recréer.

Versions : **`master` = v2.100.0, PUBLIÉE** (release GitHub du 01/11/2026, les
quatre installateurs + `INSTALLATION.md`) · **Store publié = v2.71.1** (inchangé ;
le MSIX **v2.100.0** est construit avec l'**identité Store** et signé
**localement**, jamais joint à la release — **prêt à soumettre**).

**Gouvernance** : **aucun lot de code sans demande explicite** ; ne jamais
déduire l'état d'une case de `config.json` — on MESURE le fichier produit.

---

## Session du 01/11/2026 — Stacks (FITS), palette « HSS » + 6 permutations ①b

### État actuel
- **v2.100.0 PUBLIÉE (01/11/2026)** empile TROIS livraisons du même jour : ① la
  source « Stacks (fichiers FITS) » ne bloque plus le démarrage sur une ligne
  incomplète ; ② une **NOUVELLE palette « HSS »** (R=Ha, G=S2, B=S2) ; ③ le
  chantier **①b** — les **6 permutations narrowband** (l'ORDRE DES LIGNES fait
  R/G/B : Ha, SII, OIII → **HSO**). ① et ② sont la v2.99.0, ③ la v2.100.0.
- **Release GitHub v2.100.0** (tag + release) : les **quatre installateurs**
  (`avastack-setup-2.100.0.exe` / `-windows.zip` / `-linux.tar.gz` /
  `-macos.tar.gz`) + `INSTALLATION.md` réédité (tailles + SHA-256 **MESURÉS**).
  **MSIX v2.100.0** construit avec l'**identité Store** et **signé localement**
  — hors release, **prêt à soumettre** au Store.
- **① Constat réel d'Alain** : TROIS fichiers pour un SHO étaient refusés par
  « Stacks, rôle B : choisissez le fichier de l'empilement (…) » — les lignes 4
  et 5 portaient un RÔLE resté en place dans `config.json`
  (`stacks_role_3 = "B"`, `stacks_role_4 = "L"`) **sans aucun fichier**.
- **① Deux règles de saisie désormais** : une ligne ne compte que si elle porte
  un rôle **et** un fichier — les autres sont **IGNORÉES**, et la ligne d'aide
  du panneau le dit ; deux lignes peuvent porter le **même rôle** (donc le même
  fichier) — les fichiers d'un rôle s'empilent dans la **même couche**.
- **② HSS** : le pendant SII du HOO (le même filtre sur DEUX canaux). Entrée de
  plus dans `COMPOSITIONS` (2 rôles, `canaux_rgb` R=Ha / G=S2 / B=S2), visible
  au menu de Composition ; `composition_pour_roles` gagne une passe par
  ENSEMBLE de rôles (un rôle écrit deux fois trouve quand même HSS), et HSS
  n'entre PAS dans le repli par sous-ensemble (`("S2",)` reste SHO).
- **③ ①b LIVRÉ (v2.100.0)** : les **6 permutations** de {S2, Ha, O3} sont des
  entrées de `COMPOSITIONS` — SHO (littéral, premier de la famille), HSO, HOS,
  SOH, OHS, OSH. Les **5 autres que SHO sont GÉNÉRÉES** après les entrées
  littérales par `_generer_permutations_narrowband()` (nom = l'ordre R/G/B, un
  rôle par canal, lettre S2→S / Ha→H / O3→O). **Aucun moteur ni interface
  changé** : `composition_pour_roles` comparait DÉJÀ le TUPLE exact ; le menu
  passe à **13 entrées**. ⚠ L'ordre n'est SÉLECTIF que si les 3 lignes sont
  remplies et les rôles DISTINCTS (sinon SHO, via la passe par ensemble).
- **Vérifié** : banc `_test_lot5_p6_stacks.py` **64 vérifications OK** +
  `_test_compo_5roles_jalon129.py` (table à **13 entrées**, les **6 déductions
  par ordre**, non-régression du repli) + `_test_composition_jalon19`,
  `_test_compo_worker_jalon19`, `_test_calib_compo_jalon53`,
  `_test_restack_compo_jalon20`, `_test_narrowband_ha_jalon21`,
  `_test_fusion_ha_jalon2`, `_test_voie_a_ha_jalon129b` — **tous verts** — et
  **garde-fou tout au vert** (306 fichiers compilés 0 erreur, surface publique
  de `app.py` inchangée, empilement simulé identique au bit, `pyright` 0 erreur).
  Contrôle « App réelle » (script jetable hors dépôt, supprimé) : menu **13
  entrées**, HSO/OSH pré-remplis, ligne d'aide = mapping, ordre respecté sur les
  deux sources.

### Fichiers modifiés dans cette phase
- `avastack/ui/app.py` : `_lire_roles_fichiers_stacks` (ligne incomplète
  IGNORÉE au lieu d'un refus ; plus de refus « un rôle = un seul fichier ») et
  `_maj_stacks_info` (dit les lignes ignorées, et le rôle fourni deux fois).
- `avastack/cameras/stacks.py` : docstrings (lignes complètes seules ; même
  rôle accepté → même couche).
- `avastack/ui/panels/stacks.py` : docstring du mixin + texte de l'aide « ⓘ ».
- `bancs/_test_lot5_p6_stacks.py` : volet [5] réécrit (ligne incomplète
  ignorée, panneau vide refusé, fichier sans rôle refusé, même rôle deux fois
  accepté, fichier introuvable refusé) et volet [3] étendu (6 permutations par
  l'ordre des lignes) → **64 vérifications**.
- `avastack/__init__.py` : `AVASTACK_VERSION = 2.99.0` → **2.100.0** + entrées
  de changelog (v2.99.0 puis v2.100.0).
- `avastack/processing/composition.py` : palette **HSS** dans `COMPOSITIONS`
  (+ docstring de module) et passe par ENSEMBLE de rôles dans
  `composition_pour_roles` ; puis **①b** — `_generer_permutations_narrowband()`
  ajoute les 5 permutations narrowband après les entrées littérales (+ docstring).
- `README.md` : HSS puis les 6 permutations citées dans la ligne des compositions.
- `bancs/_test_compo_5roles_jalon129.py` : table (**13 compositions**), mapping
  HSS, les **6 déductions par ordre**, non-régression du repli (l'ancienne
  assertion `("Ha","S2","O3") → SHO` devient `HSO` — c'est le lot).
- `CLAUDE.md` : la règle de saisie COURANTE de cette source + la palette HSS +
  les 6 permutations (ordre des lignes).
- `AVANCEMENT.md` : ce bloc.

### Décisions prises
- **La saisie ne bloque plus le démarrage** (Alain, 01/11) : le panneau propose
  `NB_LIGNES_COMPO` (5) lignes pour TOUTES les compositions, rien n'oblige à
  les remplir toutes. Une ligne incomplète est ignorée, et la ligne d'aide le
  dit. Restent refusés, avec un message clair : fichier choisi sans rôle,
  fichier introuvable, panneau sans aucune ligne complète.
- **Le même filtre (et le même fichier) peut être fourni DEUX fois** (demande
  d'Alain : « mettre 2 fois le même fichier et même filtre ») : les fichiers
  d'un rôle s'empilent dans la MÊME couche — la ligne d'aide le DIT, parce que
  le résultat (deux fichiers, UNE couche) n'est pas celui qu'on imagine.
- **PALETTE « HSS » LIVRÉE** (Alain, 01/11 — « pour faire une compo HOO ou
  HSS ») : `roles: ("Ha", "S2")`, `canaux_rgb: {"R": ("Ha",), "G": ("S2",),
  "B": ("S2",)}`, aucun rôle optionnel, AUCUNE fusion au rouge (le Ha y est un
  CANAL). Elle apparaît au menu de Composition et dans la ligne d'aide ; deux
  rôles → deux dossiers OU deux fichiers.
- **HSS n'entre PAS dans le repli par sous-ensemble** de
  `composition_pour_roles` : `("S2",)` y renvoie SHO depuis le jalon 19 et HSS,
  plus petit, l'aurait emporté — un comportement historique ne se change pas
  sans demande. À la place, une passe par ENSEMBLE de rôles (juste après la
  passe exacte) fait trouver HSS quand un rôle est fourni DEUX fois.
- **①b — LES 6 PERMUTATIONS, LIVRÉES** (Alain, 01/11 : « l'ordre des lignes fait
  R/G/B ») : **inscrire les permutations dans `COMPOSITIONS` suffit** (la passe
  EXACTE de `composition_pour_roles` porte l'ordre). SHO reste LITTÉRAL et
  **PREMIER de la famille** ; les 5 autres sont **GÉNÉRÉES** après les entrées
  littérales. Le mode « libre » généralisé (③) reste ÉCARTÉ (transport d'un
  mapping jusqu'au solveur live, `AVACOMPO`, fiche, persistance, ~8 bancs).
- **Stash `LRGBHa` DROPPÉ** (Alain, 01/11) : `stash@{0}` =
  `3a900d20ed74c7fe00493f5917fc9758f4e557f7` (commit `3a900d2`, 15/10/2026,
  « Mise de côté avant reprise propre du chantier LRGB+Ha / RGB+Ha », 9 fichiers,
  +665/−32). Vérifié AVANT de dropper, contenu par contenu : c'est un brouillon
  **ABANDONNÉ** du chantier Ha — ses entrées de changelog (v2.80.2/v2.80.3)
  n'existent dans AUCUN historique, ses bancs (`_test_continuum_sub_lrgb_ha.py`,
  `_test_continuum_sub_rgb_ha.py`) n'existent plus, et ses identifiants
  (`_k_auto_continuum`, `_fusion_ha` modes `add_to_red`/`blend_red`,
  `_on_ha_method`, `_on_continuum_sub`, attributs `continuum_sub` /
  `continuum_ref` / `continuum_k`) sont **absents du code final** : le chantier
  a été REFait et livré autrement (v2.81.0 → v2.92.0, jalons 129 → J5). Rien
  d'unique n'est perdu ; `git stash list` est **vide**.
- **Les règles de SAISIE de cette source vivent dans `CLAUDE.md`** (elles
  supersèdent deux points du § archivé `CLAUDE-ARCHIVES.md`) : c'est du
  comportement COURANT, pas de l'historique.

### Problèmes ouverts
- **Aucun** sur ce lot. Reste connu et NON régressif : **banc 79**
  (`bancs/_test_perf_reactivite_jalon79.py`), 4 échecs **PRÉEXISTANTS**
  (l'étape 1b a déplacé l'instrumentation `_maj_histogrammes` → `_draw_hist`).

### Prochaines étapes
- **v2.100.0 est PUBLIÉE** (tag + release GitHub, 4 installateurs +
  `INSTALLATION.md`). Rien en attente côté code.
- **PROCHAINE ACTION — décision d'Alain** : **soumettre (ou non) le MSIX
  v2.100.0 au Store**. Le paquet est **construit avec l'identité Store et
  signé** ; la soumission se fait dans **Partner Center** (fiche, images, notes
  de certification : `installer/windows/msix/SOUMISSION.md`). La signature
  locale (certificat auto-signé) ne sert qu'à l'ESSAI ; celle du Store n'existe
  qu'APRÈS soumission. Cadence SÉPARÉE (Store publié = v2.71.1).

### Points d'attention
- **Un rôle laissé sans fichier n'est PAS un oubli signalé** : c'est une ligne
  IGNORÉE, et la ligne d'aide le dit (« Ligne 4 : rôle B sans fichier — ligne
  IGNORÉE. »). Ne pas réintroduire de refus à cet endroit : c'est exactement le
  défaut corrigé ici.
- **Le `config.json` d'Alain porte encore `stacks_role_3 = "B"` et
  `stacks_role_4 = "L"`** (fichiers vides) : inoffensif depuis ce correctif —
  ne pas « nettoyer » ces clés à la main, elles se réécrivent à la fermeture.
- **Vérification du scénario réel = script JETABLE hors dépôt** (supprimé) :
  ne pas créer un banc permanent pour un cas déjà couvert par le volet [5].
- **Toucher `COMPOSITIONS` réveille des bancs** : `_test_compo_5roles_jalon129`
  fige la liste des compositions et le repli de `composition_pour_roles` — le
  mettre à jour AVEC la table, jamais après.

### Contexte de reprise (à coller — 2 phrases)
**`master` = v2.100.0 PUBLIÉE** (release GitHub du 01/11/2026, 4 installateurs +
`INSTALLATION.md`) : la source « Stacks (fichiers FITS) » ignore les lignes
incomplètes et accepte un rôle en double, la palette **HSS** (R=Ha, G=S2, B=S2)
existe, et les **6 permutations narrowband** suivent l'ORDRE DES LIGNES
(Ha, SII, OIII → **HSO**).
**Prochaine action : décider de la soumission du MSIX v2.100.0 au Store**
(paquet construit avec l'identité Store et signé, hors release).

---

## Chantier ①b — **LIVRÉ** (v2.100.0, 01/11/2026)

Les **6 permutations narrowband** sont des entrées de `COMPOSITIONS` (SHO
littéral et premier de la famille ; les 5 autres GÉNÉRÉES après les littérales) :
l'ORDRE DES LIGNES fait R/G/B (Ha, SII, OIII → **HSO**). Détail : changelog
`avastack/__init__.py` (v2.100.0) et `git log`.

---

## En attente / prochaine session

- **v2.100.0 PUBLIÉE** : release GitHub (4 installateurs + `INSTALLATION.md`).
- **PROCHAINE ACTION — décision d'Alain** : **soumettre (ou non) le MSIX
  v2.100.0 au Store**. Le paquet est **construit avec l'identité Store et signé
  localement** (hors release). La soumission se fait dans **Partner Center**
  (fiche, images, notes de certification) : `installer/windows/msix/SOUMISSION.md`.
  Rappel : la version Store est une **cadence SÉPARÉE** (Store publié = v2.71.1).
- **Recette de la v2.100.0** (déjà couverte par le banc et l'App réelle) :
  · source **« Stacks (fichiers FITS) »** — HOO = lignes Ha + O3 ; **HSS** =
  lignes Ha + S2 ; l'ORDRE fait R/G/B : Ha + S2 + O3 → **HSO**, O3 + S2 + Ha
  → OSH… (menu verrouillé : la composition se DÉDUIT des fichiers) ;
  · source **« Composition multi-dossiers »** — menu à **13 entrées** : choisir
  HOO, HSS ou une permutation (HSO…) ; les rôles se pré-remplissent, puis les
  dossiers.

---

## Setup d'Alain

- **Setup 1 (miniPC)** : QHY MiniCam8M (mono refroidie, roue intégrée) ; N.I.N.A. →
  `TargetSchedulerSequence/<cible>/<expo>/LIGHT` — un dossier peut MÉLANGER
  plusieurs nuits.
- **Setup 2** : C8 défourché + réducteur 0,63 (1280 mm) ; Player One Uranus-C Pro
  (couleur, IMX585, RGGB) sur monture DIY **Open Astro Mount** ; guidage SV305C
  sur 60/240.
- **Jeux de test (QHY + SV555)** : **M31** (L du 13/09 + R/G/B des 22-23/09,
  60 s, −15 °C) ; **M33** (nuit du 10-11/10 : L 60×60 s, R/G/B 60-120 s) + un
  dossier **Ha de 40 frames**. Darks maîtres : 60 s (L/R/G), 120 s (B), 180 s
  (Ha).
- **Outils locaux** : Siril 1.4.4 (Gaia XP, base SPCC), ASTAP (D80 Gaia DR3) ;
  pas d'astrometry.net. **Ubuntu 26.04 LTS** : installateur éprouvé ; restent la
  machine VIERGE et le test matériel caméras (`--cameras`).

---

## Pièges récents (encore actifs — le reste est passé dans `CLAUDE.md`)

- **Un banc qui charge un dark/flat ÉCRIT la config** (v2.98.7) :
  `_load_dark`/`_load_flat`/`_clear_calib` persistent désormais les chemins — un
  banc qui les appelle DOIT intercepter `ui.CONFIG` **et** `ui.sauver_config`
  (motif de `_test_calib_compo_jalon53`), sinon il écrit le vrai `config.json`
  avec un chemin de test.
- **Une conversion de dtype CHANGE l'image** : preuve au bit exigée sur les bancs
  d'empilement — jamais « à peu près », jamais sans l'accord d'Alain.
- **Échecs PRÉEXISTANTS** (environnementaux, pas des régressions) :
  `_test_espace_jalon72` (géométrie d'écran), `_test_reset_empilement_jalon76`
  [4] (course `_stop()`), « ligne Base SPCC rognée » + « menu écrasé » (flaky),
  `_test_lot1_p2_p3` [3] (rejoue `Antlia R` sur le `config.json` RÉEL), et le
  **banc 79** (4 échecs : instrumentation déplacée par l'étape 1b,
  `_maj_histogrammes` → `_draw_hist`).

---

## Clôtures précédentes

- **21/10/2026 (jour)** : v2.98.9 PUBLIÉE (release GitHub, quatre
  installateurs) + `CLAUDE.md` allégé (18 sections dans `CLAUDE-ARCHIVES.md`).
  Détail : changelog (v2.98.9) et `git log`.
- **21/10/2026 (soir)** : v2.98.5 → v2.98.7 livrées, validées en réel et poussées
  (`e307ad4`) — copie → référence (−96,2 Mio), jauge `postes`, persistance
  dark/flat. Détail : changelog (v2.98.5/6/7) et `git log`.
- **21/10/2026** : 1b validée en réel (v2.98.2) — `ui_rendu` 102 s → 2,2 s, calcul
  dans `fil_rendu`.
