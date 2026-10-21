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

Versions : **`master` = v2.98.9, PUBLIÉE** (release GitHub du 21/10/2026, les
quatre installateurs) · **Store publié = v2.71.1** (inchangé ; le MSIX v2.98.9
est construit et signé **localement**, jamais joint à la release).

**Gouvernance** : **aucun lot de code sans demande explicite** ; ne jamais
déduire l'état d'une case de `config.json` — on MESURE le fichier produit.

---

## Session du 21/10/2026 — RELEASE v2.98.9 + `CLAUDE.md` allégé

### État actuel
- **v2.98.9 est PUBLIÉE** : tag `v2.98.9` sur `master`, release GitHub
  (**Latest**) avec les **quatre installateurs** (Windows `.exe`, Windows ZIP,
  Linux, macOS) et `INSTALLATION.md` —
  <https://github.com/darkvad/AVAStack/releases/tag/v2.98.9>. `master` poussé,
  arbre propre, **garde-fou vert** (aucun `.py` touché : que de la documentation).
- **`CLAUDE.md` est ALLÉGÉ : 4545 → 3449 lignes.** 18 sections de chantiers
  TERMINÉS ont été **recopiées au mot près** dans le nouveau
  **`CLAUDE-ARCHIVES.md`** — intégrité vérifiée ligne à ligne contre `HEAD`
  (4545 lignes recomposées à l'identique, **0 perte**). L'index des sections
  archivées est dans `CLAUDE.md`.
- **MSIX v2.98.9 construit ET signé** localement
  (`installer/windows/output/avastack-2.98.9-windows.msix`, identité d'ESSAI) —
  **volontairement absent de la release GitHub**.

### Fichiers modifiés dans cette phase
- `CLAUDE.md` : allégé + les 2 entrées v2.98.9 (décomposition mesurée
  d'`empilement`, piège des moyennes par poste) + la **règle d'allègement**.
- `CLAUDE-ARCHIVES.md` : **NEUF** — 18 sections historiques, recopie au mot près.
- `INSTALLATION.md` : réédité pour v2.98.9 (tailles et SHA-256 **MESURÉS** des
  quatre installateurs).
- `AVANCEMENT.md` : ce bloc.

### Décisions prises
- **L'historique part dans `CLAUDE-ARCHIVES.md`** (Alain, 21/10) : `CLAUDE.md`
  ne porte plus que ce qui sert à DÉCIDER (conventions, pièges actifs, doc des
  outils, comportement COURANT) ; l'archive se lit **sur demande**. C'est
  désormais une **règle de maintenance** écrite dans `CLAUDE.md`.
- **Le MSIX ne va PAS sur GitHub** (Alain, 21/10 : « il n'a rien à y faire »).
- **Option A** de l'audit performance/mémoire (déjà actée) : on n'optimise rien
  de plus.

### Problèmes ouverts
- **Chaîne gelé/MSIX — dépendance de BUILD non déclarée** : `matplotlib` absent
  du venv faisait ÉCHOUER PyInstaller (le hook `astropy` collecte TOUS les
  sous-modules ; `astropy.visualization.wcsaxes` fait
  `pytest.importorskip("matplotlib")` et, avec **pytest 9**, `Skipped` n'est pas
  une `Exception` → l'enfant isolé meurt). Contourné en installant matplotlib
  dans le venv (**aucun fichier du dépôt touché**) ; à trancher : documenter le
  prérequis de build, ou filtrer `astropy.visualization` par un hook local.
- **Banc 79** (`bancs/_test_perf_reactivite_jalon79.py`) : 4 échecs
  **PRÉEXISTANTS** (l'étape 1b a déplacé l'instrumentation
  `_maj_histogrammes` → `_draw_hist`). **Ce n'est pas une régression.**

### Prochaines étapes
- **Aucun lot ouvert** : le chantier est clos ET publié. Toute nouvelle tâche se
  **demande**.
- **Décision séparée** : soumettre (ou non) le MSIX au Store — il faudra alors le
  **reconstruire avec l'identité Partner Center** (`--nom` / `--publisher`, cf.
  `installer/windows/msix/SOUMISSION.md`) ; le paquet local est un paquet
  d'ESSAI.

### Points d'attention
- **`CLAUDE.md` ne grossit plus par l'historique** : le récit d'un chantier
  terminé part dans `CLAUDE-ARCHIVES.md` (recopie au mot près, jamais réécrit,
  jamais supprimé).
- **`INSTALLATION.md` porte la version ET les SHA-256 des artéfacts** : il se
  réédite à CHAQUE release, APRÈS la construction des paquets — ces valeurs se
  MESURENT, elles ne se recopient pas.

---

## Chantier en cours — **AUCUN** (audit performance/mémoire CLOS, Option A)

L'audit est **CLOS** : `ui_tick` **3,3 %** du mur (456,5 s → 18,6 s), pire tour
74 ms, image finale **au bit**, garde-fou vert, **aucune fuite**. Leviers
chiffrés puis ÉCARTÉS (alignement, moyenne en composition, `kappa`/
`winsorized`) : **ne pas les reprendre sans demande explicite** — détail dans
`CLAUDE.md`, section « Décomposition MESURÉE d'`empilement` ».

---

## En attente / prochaine session

- **Le MSIX v2.98.9** (construit + signé) : décision d'Alain sur une éventuelle
  **soumission au Store** — hors périmètre de la release GitHub.
- **Dépendance de build `matplotlib`** : décision à prendre (documenter le
  prérequis, ou corriger le hook `astropy`) — la chaîne MSIX en dépend.

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

- **21/10/2026 (soir)** : v2.98.5 → v2.98.7 livrées, validées en réel et poussées
  (`e307ad4`) — copie → référence (−96,2 Mio), jauge `postes`, persistance
  dark/flat. Détail : changelog (v2.98.5/6/7) et `git log`.
- **21/10/2026** : 1b validée en réel (v2.98.2) — `ui_rendu` 102 s → 2,2 s, calcul
  dans `fil_rendu`.
