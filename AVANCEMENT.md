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

## Session du 16/10/2026 (soir, suite) — CHANTIER « CAUSE AMONT » : ELLE EST NOMMÉE, CHIFFRÉE, REJOUABLE

> Ouverture du chantier décidé en fin de session précédente. **La cause amont n'est
> NI le capteur, NI l'étirement, NI M33** : c'est l'**HÉTÉROGÉNÉITÉ DES DOSSIERS DE
> BRUTES** — chaque dossier de filtre mélange **deux côtés du Pier et 2 à 5 nuits**,
> avec des niveaux de ciel qui diffèrent de **+22 % à +32 %** entre les deux côtés et
> jusqu'à **3,4×** frame à frame dans le bleu — **plus** le fait que le **combine LRGB
> amplifie le bruit de R et B (×1,49 / ×1,84)** alors que le bruit d'UNE frame est le
> MÊME partout (~6,5 %). **AUCUN fichier du dépôt modifié** (scripts hors dépôt).

### État actuel
- **Jalon 131 (diagnostic seul) reste valable** : l'étirement multiplie la dispersion chromatique locale par ×52
  (pente ×597 au fond) et le clip des ombres (`_calc_stats` mesure sur la MOYENNE des canaux, `np.clip` agit
  PAR canal) fabrique **282 742 px COLORÉS** à canal noir. Correctif STÉ (point noir/blanc/m par canal) NON décidé.
- **Chantier CAUSE AMONT ouvert ce soir : cause nommée et chiffrée, correctif À DÉCIDER.**
- **Jalon 130 COMMITÉ ET POUSSÉ** (`ef0c35c`, v2.82.0, branche `LRGBHa`) ; arbre propre, rien en attente.

### Composition réelle du run 473 frames (source : `%APPDATA%\AVAStack\config.json`)
Le **journal** ne porte PAS la composition (que des étapes de démarrage). Les dossiers sont ceux du
**22/09/2026** (et non du 10-11/10) : 475 frames .fit* dispo, **473 empilées** (2 refusées).

| rôle | dossier | N | expo | intégration | nuits | East/West |
|---|---|---|---|---|---|---|
| L | `1x1/60.00/.../L` | 240 | 60 s | 4,00 h | 13,14,15,20,23/09 | 120/120 |
| R | `1x1/60.00/.../R` | 80 | 60 s | 1,33 h | 14,15,20,23/09 | 40/40 |
| G | `1x1/60.00/.../G` | 64 | 60 s | 1,07 h | 14,15,16,20,23/09 | 24/40 |
| B | **`1x1/120.00/.../B`** | 51 | **120 s** | 1,70 h | 14,16,23/09 | 28/23 |
| Ha | `1x1/180.00/.../Ha` | 40 | 180 s | 2,00 h | 14,16/09 | 35/5 |

⚠ **Le canal B a le 2ᵉ temps d'intégration de la composition** : l'hypothèse « B bruité faute de frames » (relevée
au 130f) **est réfutée pour ce run**.


### Mesures décisives du chantier (scripts HORS DÉPÔT, sorties `_132*_out.txt`)
- **① LE BRUIT D'UNE FRAME EST LE MÊME PARTOUT (~6,5 %)** (`_diag_amont_132a.py`) : R 6,83 % · G 6,52 % ·
  B 6,51 % · L ~5,8 % (σ robuste/ciel, mesuré sur les brutes réelles, 2 zones de ciel, en ADU). Le prédit
  `/√N` donne R 0,76 · G 0,81 · B 0,91 %… or le **composite BRUT sort R 1,27 · G 0,84 · B 2,05 %** : **seul G
  est conforme**, R est ×1,66 et B ×2,25. ⇒ le grain coloré ne vient PAS des brutes.
- **② LE COMBINE LRGB AMPLIFIE R ET B** (`_diag_amont_132b.py`, **expérience décisive, pure et rejouable**) :
  en injectant dans le **vrai `compo.composer()`** des couches synthétiques portant EXACTEMENT ces bruits,
  on obtient R/G = **1,49** (mesuré 1,51 ✔) et B/G = **1,84** (mesuré 2,44) ; **sans le rôle L (RGB), les
  rapports retombent à 0,93 / 1,11** = les bruits intrinsèques. Mécanisme : `ratio = L / lum` où
  `lum = 0,299 R + 0,587 G + 0,114 B` — le bruit du ratio **se retranche au vert** (poids 0,587) et
  **s'ajoute aux canaux à faible poids**. Reste un **excédent propre à B (×1,33)** → ③.
- **③ CHAQUE DOSSIER MÉLANGE 2 CÔTÉS DU PIER ET 2-5 NUITS, AVEC DES CIELS TRÈS DIFFÉRENTS**
  (`_diag_amont_132c.py`, lecture d'UNE fenêtre par frame, 475 frames) :

  | rôle | ciel médian | min … max | σ/méd | East | West | frames hors norme (>1,5×) |
  |---|---|---|---|---|---|---|
  | L | 6 304 | 5 552 … **12 672** | 12,6 % | 6 696 | 6 072 | 1 / 240 |
  | R | 3 272 | 2 896 … 4 576 | 13,2 % | 3 664 | 3 008 (**+21,8 %**) | 0 / 80 |
  | G | 3 296 | 3 152 … 6 144 | 20,9 % | 4 224 | 3 208 (**+31,7 %**) | 4 / 64 |
  | B | 3 584 | 3 280 … **11 984** | **49,8 %** | 3 632 | 3 344 | **8 / 51** (les 8 dernières, 23/09) |
  | Ha | 1 808 | 1 792 … 1 840 | 0,8 % | 1 808 | 1 792 | 0 / 40 |

  ⚠ **Le rapport East/West n'est PAS le même par canal** (+21,8 % en R, +31,7 % en G) ⇒ mélanger les deux
  côtés du Pier, qui couvrent le ciel différemment (rotation 177°), **fabrique de la COULEUR** — et comme la
  proportion de chaque côté VARIE avec la position dans le cadre, cette couleur est **STRUCTURÉE**. Un rejet
  kappa-sigma ne peut rien contre un **décalage de niveau partagé par la moitié des frames** (le σ temporel
  vaut alors 13-50 %, aucun mode n'est aberrant).
- **④ DARKS MAÎTRES À INSTRUIRE** (`_132a` §3) : `C:\IA\Darks\masters\-15\...\MasterDark_60/120_90_25.fit`
  sont écrits par **Siril 1.4.0-rc2** en **float32 normalisé [0;1]** (méd 0,03 · max 1) — or `load_image`
  laisse les FLOTTANTS tels quels alors qu'il divise les uint16 par 65 535 : à vérifier avant toute conclusion
  (question ouverte ci-dessous).
- **Rappel jalon 131 (toujours valable)** : étirement pente ×597 au fond (fond 0,0249 · `lo` 0,02470 · `hi` 0,09471) ;
  dispersion chromatique locale 1,82 % (BRUT) / 1,61 % (TRAITÉ) / 84,9 % (STF) ; 1 022 taches rouges + 393 bleues
  dans le BRUT (aire médiane 4-7 px, +40 % du fond local) ; VeraLux = 21 624 px écrasés contre 244 en STF.


### Fichiers produits (hors dépôt, `C:\Astro\test\`)
- **Nouveaux (chantier)** : `_diag_amont_132a.py` (bruit par frame + darks), `_diag_amont_132b.py`
  (expérience du combine dans le vrai `composer`), `_diag_amont_132c.py` (ciel de TOUTES les frames par rôle
  et par `PIERSIDE`) + sorties `_132a_out.txt`, `_132b_out.txt`, `_132c_out.txt`.
- Rappel jalon 131 : `_diag_taches_131*.py` (+ `_131*_out.txt`, planches `_131*.jpg/png`) — hors dépôt.
- **AUCUN fichier du dépôt modifié** (hors cette mise à jour d'`AVANCEMENT.md`).

### Prochaines étapes (ordre proposé, à trancher par Alain)
1. **PROUVER LE LIEN ③ → COULEUR** (le seul maillon encore en « mécanisme » et non en « mesure ») : empiler
   ~16 frames R + 16 frames G **en deux configurations** — (A) mélange East/West comme l'appli, (B) un SEUL
   côté du Pier — et mesurer σ(G−R) local du mini-composite. Si (A) fabrique la structure colorée et (B) non,
   la cause est PROUVÉE sur les brutes réelles et le correctif est dessiné.
2. **DÉCIDER LE CORRECTIF** (aucun n'est choisi) : pistes — caler le NIVEAU de chaque frame avant empilement
   (par côté/nuit), ou grouper/filtrer par côté+nuit, ou compléter le rejet par un test de NIVEAU (et non
   d'aberration), ou corriger le fond PAR CANAL à l'étirement. **VeraLux (méthode préférée d'Alain) ne doit
   pas être dégradé** ; le correctif du clip par canal (131f) reste à décider séparément.
3. **Axes restants du chantier** : (a) l'origine des **1 022 taches rouges + 393 bleues** du BRUT (traçage sur
   les brutes via les matrices d'alignement, jamais fait) ; (c) les **pixels chauds résiduels** (2 135 fixes en R,
   97 % éliminés par le rejet).
4. **Après** : l'ancre VeraLux (calculée sur la LUMINANCE puis soustraite `max(x,0)` PAR CANAL, 21 624 px écrasés) ;
   en réserve : « SPCC : ne pas appliquer une pente hors bornes ».

### Problèmes ouverts
- **Les darks maîtres Siril (float32 [0;1], méd 0,03) sont-ils réellement appliqués, et à la bonne échelle ?**
  `config.json` ne porte PAS les masters (choisis dans le panneau Calibration, non persistés) : à mesurer.
- **Le journal ne porte PAS la composition** d'un run (que des étapes de démarrage) → seul `config.json`
  (dernier état) ou la fiche de rendu renseignent.

### Points d'attention (encore actifs)
- **PIÈGE** : `moyennes()` (voie A) applique le recalage de rôle — qui veut un empilement BRUT doit passer par
  `LiveStacker.mean()`.
- **Cadence d'archivage = 1 frame/s PAR RÔLE** (`framestore.ARCHIVE_INTERVALLE_S`) : un banc qui veut N frames
  par rôle doit poser l'archive EXPLICITEMENT (`ArchiveFrames(intervalle_s=0)`).
- **Repli « phase »** (`alignment.py`) peut « aligner » deux champs NON apparentés (mesuré 1/3) ; garde-fou
  `_invariants_triangles` : `n_max` ≤ ~30 (au-delà, 13,7 Go de RSS).
- Des images d'un AUTRE logiciel traînent dans `Pictures`/`Downloads` : **PAS** des preuves d'un test.
- Tk : jamais `grid` et `pack` mélangés ; `cv2.ocl.setUseOpenCL(False)` ; bancs `ui.App` : patcher `_dire`.


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

- **CHANTIER « CAUSE AMONT » — EN COURS, INSTRUIT CE SOIR** (voir le bloc de session ci-dessus) : la cause est
  nommée (hétérogénéité des dossiers : 2 côtés du Pier × 2-5 nuits, ciels qui diffèrent de +22 à +32 % entre les
  côtés et jusqu'à ×3,4 dans B ; **plus** l'amplification asymétrique du combine LRGB), et le prédit `/√N` est
  validé pour le vert seulement. **RESTE À FAIRE** : ① prouver le lien « mélange des côtés → couleur » par un
  mini-empilement East/West contre mono-côté (`_diag_amont_132*` sont les outils de départ) ; ② **DÉCIDER LE
  CORRECTIF** (Alain) ; ③ les 1 022 taches rouges + 393 bleues du BRUT (traçage sur les brutes, jamais fait) et
  les pixels chauds résiduels ; ④ le sort des **darks maîtres Siril** (float32 [0;1]) — question ouverte.

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

- **16/10/2026 (fin)** : jalon 130 (v2.82.0) COMMITÉ + POUSSÉ (`ef0c35c`) — le combine LRGB est borné ; et le
  diagnostic 131 INNOCENTE l'empilement, l'alignement et M33 en nommant la cause des « taches » :
  l'ÉTIREMENT (gain ×50-600 au fond) + le clip des ombres calculé sur la moyenne des canaux et appliqué
  PAR CANAL (fond vert, 282 742 px à un canal noir). Prochaine session : la CAUSE AMONT.
- **12/10/2026** : jalon 128 (v2.80.0) — l'image VeraLux reste à l'écran pendant un recalcul (« Recalculs en
  cours ») ; release GitHub PUBLIÉE (4 installateurs + `INSTALLATION.md`).
- **12/10/2026** : jalon 127 (v2.79.0, incl. 126) — chroma pour les DEUX moteurs + bancs 63/65 réparés ;
  validé M33 ; poussé.




