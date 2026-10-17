# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md. **Gardé LÉGER** : le changelog détaillé vit dans
`avastack/__init__.py` — ici, seul le DERNIER jalon reste détaillé, sa trace
étant dans le changelog du source et l'historique git.)

---

## ⚠️ BRANCHE DE DÉVELOPPEMENT ACTIVE — NE PAS SUPPRIMER JUSQU'À DEMANDE EXPLICITE

**Branche : `LRGBHa`** (créée le 15/10/2026 à partir de `master`)

> **RÈGLE FERME — GRAVÉE DANS LE MARBRE** : Jusqu'à nouvel ordre explicite de l'utilisateur,
> **TOUTE** nouvelle fonctionnalité, **TOUT** développement, **TOUTE** modification de code
> se fait **EXCLUSIVEMENT** sur la branche `LRGBHa`.
>
> La branche `master` ne doit **JAMAIS** être touchée directement pour de nouvelles
> fonctionnalités.
>
> - `master` = branche stable, releases uniquement
> - `LRGBHa` = branche de développement, nouvelles fonctionnalités (SEULE branche autorisée)
> - Merge vers `master` = seulement sur validation explicite (release)

---

## Session du 17/10/2026 (après-midi) — 134/135/138 : LES TACHES NE SONT DANS AUCUNE COUCHE

### État actuel
- **Étape ① FAITE : le rôle R SEUL est empilé, et il est PROPRE.** Empilement mono réel
  (vrai `ui.App`, source « Dossier surveillé », 80 frames, dark 60 s UNIQUE, 6 min 20) →
  `M 33 R seul 134 lineaire.fits` (1959×3740, AVAFRAME 80, 0 refus, 0 floue).
- **LES TACHES NE SONT NI DANS L'EMPILEMENT R, NI DANS LES BRUTES, NI DANS AUCUNE DES
  5 COUCHES BRUTES.** Elles n'existent que dans le plan R du fichier de 473 frames.
- Ni dark, ni brutes, ni empilement du rôle, ni alignement, ni combine ne les expliquent
  séparément : c'est l'EMPILEMENT DU RÔLE R DE CE RUN-LÀ (session à 5 rôles) qui diffère
  de l'empilement R seul.

### Mesures (scripts hors dépôt `_134*`/`_135*`/`_137*`/`_138*`, sorties `_134*_out.txt`…)
| Mesure | Résultat |
|---|---|
| 134 — critère 131b | contrôle OK : **1022 rouges / 393 bleus** ; mono R : 2786 taches > +40 % = 380/Mpx |
| 134e — recalage mono ↔ composite | ORB : échelle 1,00000 · rotation 0,000° · translation 0 ; **97,8 % des 400 étoiles à (0,−1)** |
| 134 — les taches projetées dans le mono | 809/810 dans le cadre · écart médian **−0,7 %** · 5,8 % encore > +40 % (hasard 0,4 %) |
| 134b — ratio composite/mono aux taches | méd **2,65** (p90 7,3 · max 9,0) contre 1,03 au fond |
| 134d — anatomie d'une tache | **PSF de ~5 px** : R composite ×8,9 au pic · G ×2,2 · B ~0 · mono plat |
| 134f — santé | corrélation après lissage 101×101 : **0,9925** (même scène) ; mono plat au centre |
| 135 — CONTRÔLE POSITIF (200 étoiles brillantes) | couches R/G/B/L : **+852 à +2026 %**, 100 % > +40 % ⇒ recalage VALIDE |
| 135 — aux 810 taches | R −0,8 % · G −0,6 % · B −0,5 % · L −0,8 % · Ha −2,2 % (0,5-2,5 % > +40 %) |
| 135 — couche R vs mono R | dy=0 · dx=1 · **r = 0,985** ⇒ la couche R EST l'empilement R seul |
| 136 — `composer()` rejoué sur les couches | COMMUN : 1762 taches (361 d'aire ≥ 3) ; PAR RÔLE : 287 806 ⇒ le fichier réel est COMMUN |
| 138 — rejeu AUX POSITIONS RÉELLES | **−0,7 %** (1,9 % > +40 %) alors que le fichier réel y est à **+156,7 %** |

### Fichiers produits (hors dépôt, `C:\Astro\test\`)
- `M 33 R seul 134 lineaire.fits` · `_134_rmono_run_out.txt` / `_134_rmono_etat.json` ;
- `_canaux134g\canal_{L,R,G,B,Ha}.fit` (run 40 frames, via `--canaux` du driveur) ;
- `_diag_134_rmono.py`, `_diag_134b_ou_sont_les_taches.py`, `_diag_134c_tracer_frames.py`,
  `_diag_134d_anatomie.py`, `_diag_134e_recalage_etoiles.py`, `_diag_134f_sante.py`,
  `_diag_135_couches.py`, `_diag_136_rejoue_combine.py`, `_diag_137_multiple.py`,
  `_diag_138_positions.py` ;
- driveur `_run_133b_fresh_linear.py` enrichi : `--mono DOSSIER` et `--canaux DOSSIER`.
- **AUCUN fichier du dépôt modifié.**

### Décisions prises
- **On ne corrige rien** tant que la couche R d'un run long n'a pas été comparée au mono.
- Le 134c (« les brutes ne portent rien ») est **INVALIDE** par construction : une brute est
  dithérée, l'échantillonner à une coordonnée capteur fixe ne prouve rien.
- La piste « pixels chauds du dark » reste écartée (133e), la piste « combine » est écartée
  pour ces positions (138 : `composer()` n'y fabrique rien).

### Prochaines étapes
1. **Run composition R+G** (80 + 64 frames, `--canaux`, `--no-save`) ≈ 17 min : comparer
   `canal_R.fit` au mono R **aux positions des taches** (contrôle positif obligatoire).
2. Si la couche R du run long porte les taches → chercher dans l'ACCUMULATION du rôle
   (rafraîchissement de référence tous les 20 frames, re-stack, rejet).
3. Sinon → instrumenter `composer()` **dans** l'appli (dump de `norm_R/G/B` et du `ratio`).
4. Ensuite seulement : décider le correctif (Alain).

### Points d'attention
- **Une brute est DITHÉRÉE** : le seul test valable est un empilement ALIGNÉ (mono ou couche).
- **Les `cadre` de deux RUNS ne sont pas comparables** (chacun a son canevas) : recaler par
  les ÉTOILES (histogramme des écarts), jamais par les cadres (±18 px d'erreur constatés).
- Les couches brutes passent par `save_canaux_request` (`canal_<rôle>.fit`) ; l'appli doit
  ATTENDRE leur écriture avant de quitter (300 ms de `root.quit` ne suffisent pas).
- Les brutes NINA portent `BZERO/BSCALE` : `memmap=True` est refusé par astropy.
- `config.json` pointe sur M31 (test de non-régression d'Alain, cible SAINE) ; M33 est la
  cible qui montre les taches — Alain a confirmé que **M33 en RGB (sans L) montre les mêmes**.

---

## Chantier en cours — LRGB+Ha / RGB+Ha (jalons 129 → 129b → J2 → J5)

Le rôle Ha **n'alimente AUCUN canal** : il est **FUSIONNÉ au composite** après le combine L (canal rouge).
L'UI a **5 lignes** (rôle + dossier) : L, R, G, B, Ha.

| Jalon | Contenu | État |
|---|---|---|
| **J1 / 129** (v2.81.0) | compositions + 5 lignes + séparation ancre / `_narrowband_ha` | **commité** (checkpoint, banc vert), test réel KO (Ha refusé) |
| **129b-A** | Ha utilisable : **voie A** (référence PAR RÔLE + recalage de l'EMPILEMENT) + `profondeur_min` + refus par rôle + libellé SPCC | **COMMITÉ** (`cfd40d0`) — re-test réel du 16/10 : voie A **VALIDÉE** (441 frames, 2 refus en R) |
| **J-CLRGB = JALON 130** (v2.82.0) | combine LRGB : **domaine** + **bornes [0 ; 5]** + **repli = moyenne LOCALE** + la fiche DIT le combine + banc NEUF (8 volets) | **IMPLÉMENTÉ**, banc/garde-fou VERT, mesure sur couches réelles faite — **à VALIDER EN RÉEL** (non commité) |
| **J2** | fusion « ajout au rouge » (DÉFAUT) + poids + cadre « Fusion Ha » | après le re-test du 130 |

| **J3** | les 4 autres modes : `fondu_rouge` (α), `ecran_rouge`, `eclaircir_rouge` (max), `ha_luminance` | |
| **J4** | continuum (défaut = BANDES PASSANTES, BW_Ha 7 nm / BW_RGB 100 nm ; référence **R**, jamais L) | |
| **J5** | ancre EN RÉEL + fiche de rendu + doc | |

**Plan FIGÉ — 13 arbitrages d'Alain (15/10/2026).** Identifiants en **FRANÇAIS** (comme `synthetise`).
Défauts/bornes : poids **1,0** (0–10, pas 0,05) · α **0,5** (0–1, pas 0,05) · Q **0,80** (0,10–2,00, pas 0,05).
Cadre « Fusion Ha » visible SEULEMENT si la compo contient Ha. Continuum : 3 méthodes, défaut **bandes
passantes** (source : `NBRGBCombination.js` de PixInsight, LU sur le disque d'Alain) ; case « recentrer le
Ha sur son fond » (`Ha − med(Ha)`) COCHÉE ; écrêtage [0,1] ; case DÉSACTIVÉE si le dossier R est vide ;
seuil de détection d'étoiles 5σ = constante INTERNE. **HORS PÉRIMÈTRE** : poids par canal R/G/B, starless,
versions non linéaires.

**RÈGLES D'OR.** Un jalon = un banc NEUF + rejeu des bancs concernés (TOUS VERTS, hors échecs préexistants
documentés) + garde-fou `_test_refactoring_garde_fou.py` VERT ; commentaires en FRANÇAIS ; **jamais** l'état
d'une case déduit de `config.json` — le MESURER. **AUCUNE release GitHub sans l'accord d'Alain** ; **à CHAQUE
jalon validé, LUI DEMANDER AVANT de démarrer le suivant**.

---

## En attente / prochaine session

- **CHANTIER « CAUSE AMONT » — ÉTAPE ①+② FAITES (17/10)** : le rôle R seul est empilé et
  **PROPRE** ; les taches ne sont ni dans les brutes (dithérées — le traçage fixe est
  invalide), ni dans les 5 couches brutes, ni dans un `composer()` rejoué sur ces couches.
  Elles n'existent QUE dans le plan R du fichier de 473 frames ⇒ l'empilement du rôle R
  de ce run-là diffère de l'empilement R seul. **PROCHAINE ACTION, UNE SEULE** : run
  composition **R+G** avec `--canaux` (~17 min) et comparaison de `canal_R.fit` au mono R
  **aux positions des taches** (contrôle positif aux étoiles brillantes obligatoire).
  Puis seulement : décider le correctif. Reste aussi ④ l'hétérogénéité des dossiers
  (2 côtés du Pier × 2-5 nuits, ciels +22 à +32 %) et l'amplification asymétrique du
  combine — mesure faite, correctif non décidé.

- **VeraLux (méthode préférée d'Alain) — à instruire APRÈS la cause amont** : son ANCRE est calculée sur la
  LUMINANCE PONDÉRÉE puis soustraite avec un `max(x, 0)` **PAR CANAL** (code tiers
  `veralux_core_headless.py`, `calculate_anchor_adaptive` + `extract_luminance`) ; l'ancre consomme ~97 %
  du niveau de ciel → **21 624 px écrasés = 88 × le STF** (les 244 px du STF sont TOUS dedans). Remède DÉJÀ
  en place de ce côté : le **PIÉDESTAL PAR CANAL** (jalon 122, ACTIF, `couleurs.piedestal_canaux`).
- **DIRE si les anneaux sombres autour des étoiles sont toujours là** : **MESURÉ** — la couronne d'étoile est
  NEUTRE dans le brut ET le traité (±0 % à r=14) et devient COLORÉE dans le STF (R +41 %, G +19 %, B +23 %
  à r=14). Ce n'est donc PAS un anneau de l'empilement : l'étirement colore le halo (le clip par canal le
  réduit : R +30,4 % → +14,7 %).
- **Jalon en RÉSERVE (pas décidé)** : « SPCC : ne pas appliquer une pente hors bornes » (piste du
  diagnostic 130).
- **Retour arrière possible en un geste** : `git checkout -- avastack/processing/composition.py` remet le
  combine d'avant (le correctif est isolé dans `_ratio_combine`).
- Livré/validé : **v2.81.0** (compositions +Ha + voie A) sur `LRGBHa` — **PAS publiée** (pas de release tant
  que le Ha n'est pas fusionné) ; **v2.80.0** publiée sur `master`.
- Boutons de données SANS Siril (« ⬇ Gaia », « ⬇ Spectres (champ) », « ⬇ Base SPCC ») ; **piste INDI** = jalon à
  part, PAS avant le portage Linux ; côté **Store**, cadence séparée (v2.71.1 publiée).
- `installer/` : règle « plus d'un ou deux fichiers touchés → rebuild ».

---

## Setup d'Alain

- **Setup 1 (miniPC)** : QHY MiniCam8M (mono refroidie, roue intégrée, alim. 12 V) ;
  N.I.N.A. → `TargetSchedulerSequence/<cible>/<expo>/LIGHT` — un dossier peut MÉLANGER
  plusieurs nuits (la 1re frame par mtime n'est pas forcément de la nuit courante).
- **Setup 2** : C8 défourché + réducteur 0,63 → 1280 mm ; Player One Uranus-C Pro
  (couleur, IMX585, 3856×2180, RGGB, gain unitaire 210, TEC) sur monture DIY **Open
  Astro Mount** ; guidage SVBONY SV305C sur lunette 60/240. Constat 17/09/2026 à
  1280 mm : étoiles « en plusieurs points puis en trainées » → origine du jalon 13
  (alignement robuste). Banc POA : `_diag_camera_playerone.py` (jalon 28).
- **Jeux de test (QHY MiniCam8M + SV555)** : M31 (09/10) = L du 13/09 + R/G/B du
  22-23/09, ~50-60 frames/filtre, 60 s, −15 °C (⚠ un dossier de filtre peut MÊLER les
  deux côtés du Pier : 26 % des frames RGB à 176°) ; M33 (nuit du 10-11/10) = L 60×60s ·
  R 20×60s · G 20×60s · B 17×120s → 2,2 h, recadré 3747×1983 (master dark 60 s pour
  L/R/G, 120 s pour B). **15/10/2026 : jeu M33 + un dossier Ha de 40 frames — cible du test J1.**
- **Outils astro locaux vérifiés (22/09/2026)** : Siril 1.4.4 (catalogues Gaia XP dans
  `%LOCALAPPDATA%\Siril\...`, base SPCC dans `siril-spcc-database`) ; ASTAP
  (`C:\Program Files\astap`, base D80 Gaia DR3 1,24 Go) ; PAS d'astrometry.net/ANSVR.
- **Machine LINUX d'Alain (fait du 29/09/2026)** : **Ubuntu 26.04 LTS** — installateur
  Linux exécuté PLUSIEURS fois (installation, prérequis, venv, dépendances, lancement) ;
  astrométrie, SPCC et GraXpert y sont validés. Restent : machine **VIERGE** (sans
  Python) et **test matériel caméras** (`--cameras`).

---

## Pièges récents (encore actifs)

- **L'ÉTIREMENT A UN GAIN DE ×600 AU FOND** (jalon 131, MESURÉ sur le re-test du 16/10) : fond 0,0249,
  `lo = med − 2,6 σ` = 0,02470, `hi = p99,9` = 0,09471 → le fond n'est qu'à **0,265 % de la plage** au-dessus
  du noir, `m = 0,0234`, **pente ×597**. Conséquence mesurée : le bruit local du fond passe de 0,05-0,07 %
  (image traitée) à 3-7 % (image étirée) = **×66-111**, et la dispersion chromatique locale (G−R, N=31 px)
  de 1,61 % à **84,9 % = ×52**. Un « grain » invisible en linéaire devient un patchwork saturé : **c'est
  attendu ; ce qui ne l'est pas, c'est que le fond porte des structures COLORÉES (σ 1,6 %) dès l'empilement
  BRUT** (le débruitage/GraXpert ne les réduit pas : 1,82 % → 1,61 %).
- **`_calc_stats` MESURE SUR LA MOYENNE DES CANAUX, MAIS LE CLIP S'APPLIQUE PAR CANAL** (`display.py`,
  `_calc_stats` l. 523 → `_moteur_stf` l. 614) : le fond R est à +1,73 σ de `lo` (3,56 % de ses pixels
  écrasés à 0), G à +3,49 σ (2,14 %), B à +2,82 σ (3,01 %) → **364 905 px ont un canal noir, dont 282 742
  COLORÉS** (points rouges/bleus purs) **et un fond VERT** (G/R = 1,88 prédit contre 1,84 mesuré). Un point
  noir/blanc par canal remet le fond à 1,000/1,000 et divise les pixels à canal noir par 3 (simulé, `_131f`).
- **COMPARER DES TUILES N'A DE SENS QU'À ÉCHELLE COMMUNE** : étirer le contraste de chaque tuile séparément
  (percentiles par tuile) fait paraître le brut toujours propre — ses étoiles écrasent l'échelle (piège déjà
  rencontré au 130). Règle qui marche : **afficher chaque image relativement à SON PROPRE FOND** (gris =
  fond × 0,90 → fond × 1,50) — c'est ce qui a montré le patchwork (`_131d_echelle_commune.jpg`).
- **LE REFUS Ha N'EST PAS UN PROBLÈME DE MÉTHODE** (rejeu 129b, MESURÉ) : `triangles_seuls` False ou True
  → **0/5** ; Ha RETOURNÉ ~180°, **~6 étoiles communes** avec le L, `TRI_INLIERS_MIN(6)` non tenable en
  consolidation ; ORB **good 1-7 < 8** des deux côtés. ⇒ ne PAS remettre `triangles_seuls` pour le Ha.
- **REPLI « PHASE » TROMPEUR SUR DES CHAMPS NON APPARENTÉS** (mesuré au banc 129b : 1/3 « aligné ») : un
  succès `phase` ne prouve AUCUN appariement d'étoiles — ne pas s'en servir comme preuve d'alignabilité.
- **GARDE-FOU `_invariants_triangles`** : un `n_max` > ~30 explose la mémoire — C(60,3) = 34 220
  triangles et la matrice (T×T) qui suit font grimper le processus à **13,7 Go de RSS** (constaté, à
  tuer). Les rejeux/essais de base élargie doivent PLAFONNER (12/18/24/30).
- **SPCC : le mode « offset » du Linear Fit NE RÉÉCHELONNE PAS** (`gains = 1.0`, `stacking.py:205`) — un
  coefficient SPCC extrême (fond bleu) n'est donc PAS compensé. Et la SPCC AVERTIT quand son modèle décrit
  mal l'image (pente hors [0,5 ; 1,5]) : dans ce cas, ne pas l'appliquer sans réfléchir.
- **`moyennes()` APPLIQUE le recalage de rôle** (voie A) : tout consommateur qui doit lire un empilement
  BRUT doit passer par `LiveStacker.mean()` — sinon double transformation.
- **Pixels à CANAL NUL (S = 1)** — fabriqués par le bug de restauration (CORRIGÉ au jalon 120) : ils
  POLLUENT toute statistique de couleur — les EXCLURE avant de mesurer.
- **La CHROMA est un NO-OP sur une image MONOCHROME** (Cr/Cb nuls) : tout banc qui la teste doit utiliser
  une image COULEUR (leçon du banc 125 [4]).
- **`config.json` NE DIT PAS LA RÉALITÉ** : c'est l'état à la DERNIÈRE FERMETURE, pas celui du moment où un
  fichier est écrit. On ne l'utilise JAMAIS pour affirmer l'état d'un réglage : **on MESURE** le fichier produit.
- **VERALUX AMPLIFIE LE FOND (MESURÉ)** : son ancre consomme ~97 % du niveau de ciel → tout écart de fond par
  canal sort ×20 à ×40 ; la moindre correction par canal décide de la couleur (cyan ↔ magenta).
- **La NEUTRALISATION du fond est RÉSERVÉE à VeraLux ; `reduire_bruit_chroma` est COMMUNE aux deux moteurs ;
  les DEUX sont EXCLUES de la sortie linéaire traitée** (verrouillé, banc jalon 59 [6]).
- **JOB EXTERNE = 11 éléments** (jalon 123) ; un job plus court est lu TOLÉRANT.
- **`_vl_params()` N'INCLUT PAS LA FORME** : un prédicat qui compare `_vl_result[0]` à `_vl_params()` SEUL est
  TOUJOURS faux ; et il ARRONDIT `vl_chroma_rayon` à 2 décimales (une clé peut « matcher » un rayon voisin).
- **Échecs PRÉEXISTANTS** : `_test_espace_jalon72` (géométrie d'écran, dépend de la machine) ;
  `_test_reset_empilement_jalon76` [4] (course `_stop()`, sensible à la charge CPU).
- **`_fmt_expo` est DÉJÀ PRIS dans `app.py`** (jalon 119) : le redéfinir casse le panneau Caméra.
- **PIÈGE LANCEMENT** : `python3` ≠ venv — toujours `python AVAStack.py`.
- **Ordre de la chaîne** (Alain, 16/09/2026) : recadrage → gradient → débruitage → netteté → étirement.
- **Tk** : ne JAMAIS mélanger `grid` et `pack` dans le même conteneur (`TclError`).
- **OpenCV/OpenCL** : crash au teardown → `cv2.ocl.setUseOpenCL(False)` ; bancs `ui.App` hermétiques :
  `ui.CONFIG = {}` + `sauver_config` intercepté.
- **Bancs : `_detecter_filtres()` se termine par `_dire()` = boîte MODALE** → patcher `ui.App._dire`
  (`lambda self, *a, **k: None`), sinon blocage indéfini.

---

## Clôtures précédentes

- **17/10/2026 (matin)** : 133 — le fichier `2.82.0 bis` est reproductible AU BIT par un
  empilement frais avec les darks par rôle ; le dark est innocenté (le 132f, qui affirmait
  l'inverse, mesurait les brutes du disque — méthode invalide).
- **16/10/2026 (fin)** : jalon 130 (v2.82.0) COMMITÉ + POUSSÉ (`ef0c35c`) — le combine LRGB
  est borné ; le diagnostic 131 innocentait l'empilement et nommait l'étirement + le clip
  par canal.
