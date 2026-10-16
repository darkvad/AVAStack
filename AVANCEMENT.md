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

## Session du 16/10/2026 (fin) — JALON 131 : LES « TACHES » — CAUSE NOMMÉE, CHIFFRÉE, REJOUABLE

> **Diagnostic mené à son terme sur les fichiers d'Alain** (scripts HORS DÉPÔT
> `C:\Astro\test\_diag_taches_131*.py`, sorties `_131*_out.txt`, planches
> `_131*.jpg/png`). **Ni l'empilement, ni l'alignement, ni M33, ni le matériel, ni
> le combine** : le brut ET l'image traitée sont PROPRES (fond neutre à 1,000,
> halo d'étoile neutre, bruit local 0,05-0,07 %). **La cause est l'ÉTIREMENT, qui
> multiplie par ×46-52 la dispersion chromatique locale du fond**, plus un défaut
> du clip des ombres (calculé sur la moyenne des canaux, appliqué PAR CANAL).
> `AVANCEMENT.md` a été recadré sur ce jalon.

### État actuel
- **Jalon 130 COMMITÉ ET POUSSÉ** (`ef0c35c`, branche `LRGBHa`, v2.82.0) : combine LRGB borné + banc neuf
  (8 volets, bancs VERTs), poussé sur `origin` le 16/10 au soir.
- **Jalon 131 = DIAGNOSTIC SEUL, AUCUN CODE MODIFIÉ** : cause nommée, chiffrée, rejouable — correctif à décider.
- **SESSION CLOSE sur la décision d'Alain (16/10, fin)** : ① l'explication STF ↔ VeraLux lui a été donnée ;
  ② le jalon 130 est poussé ; ③ **la prochaine session commence par la CAUSE AMONT** (le fond du composite).
  Le problème existe dans **les DEUX moteurs** et **VeraLux reste la méthode préférée d'Alain** : aucun
  correctif ne doit le dégrader.
- Le re-test STF d'Alain (`M 33 2.82.0 bis STF  sans chroma sans nettete.fits`) **n'a pas innocenté l'étirement :
  il a innocenté TOUT LE RESTE**.

### Mesures décisives (toutes rejouables)
- **Preuve visuelle à échelle COMMUNE** (`_131d_echelle_commune.jpg`, gris = fond×0,90 → ×1,50, *la même
  règle pour les trois images*) : **BRUT propre · TRAITÉ propre · STF = patchwork rouge/vert/bleu/magenta**.
  ⚠ Leçon : comparer des tuiles en étirant le contraste PAR TUILE ne prouve rien (piège du 130, reproduit ici).
- **Gain du bruit par l'étirement (TRAITÉ → STF)** : bruit local du fond 0,07 %/0,05 %/0,07 % (R/G/B) →
  **7,32 %/3,21 %/5,55 % = ×111/×66/×81**. Dispersion chromatique locale (G−R, N=31 px) : 1,61 % → **84,88 % = ×52**.
- **Pourquoi un gain pareil** : fond = 0,0249, `lo = med − 2,6 σ` = 0,02470, `hi = p99,9` = 0,09471 →
  **le fond n'est qu'à 0,265 % de la plage au-dessus du noir**, `m = 0,02338` → **pente ×597 au fond**.
- **Défaut du clip des ombres (display.py)** : `_calc_stats` mesure médiane/σ sur la **MOYENNE des canaux**
  (`_calc_stats`, l. 523) mais `np.clip((img − lo)/(hi − lo))` (`_moteur_stf`, l. 614) est appliqué **par canal**.
  Le fond R est à +1,73 σ de `lo` (3,56 % de ses pixels écrasés à 0), G à +3,49 σ (2,14 %), B à +2,82 σ (3,01 %)
  → **364 905 px ont un canal noir, dont 282 742 COLORÉS** (un canal à 0, les autres non) = points rouges/bleus purs.
  Prédiction vérifiée : fond **G/R = 1,88 prédit contre 1,84 mesuré** (et G−R local médian +13,3 %).
- **Correctif testé en SIMULATION** (`_131f`, `_131g_avant_apres.jpg`) — **point noir, point blanc et m PAR CANAL** :
  fond **G/R = 1,000 B/R = 1,000** (vert → neutre), pixels à canal noir 108 648 → 34 390, points rouges
  228 418 → 110 013 px, couronne d'étoile R +30,4 % → +14,7 / G +16,1 / B +9,6 (anneau coloré quasi corrigé).
  **MAIS le patchwork subsiste** (110 013 px rouges) → le clip n'est PAS la cause première.
- **La source amont est dans l'EMPILEMENT BRUT, pas dans le traitement** : dispersion chromatique locale du fond
  BRUT 1,82 % · TRAITÉ 1,61 % (le débruitage/GraXpert ne la réduit PAS) ; corrélation des motifs (G−R)/(B−R)
  = +0,70 (structure commune). Le brut porte 1 022 taches rouges + 393 bleues (aire médiane 4-7 px, seuil +40 % local).
- **VeraLux** : même famille de défaut, autre dosage — dispersion ×6,8 seulement mais **21 624 px écrasés** contre
  244 en STF (les 244 px du STF sont TOUS dans le VeraLux). Le test STF a donc réduit le désastre d'un facteur 88.

### Fichiers produits (hors dépôt, `C:\Astro\test\`)
- `_diag_taches_131.py`, `_diag_taches_131b.py`, `_diag_taches_131c.py`, `_diag_taches_131d.py`,
  `_diag_taches_131e.py`, `_diag_taches_131f.py`, `_diag_taches_131g.py`, `_diag_taches_131h.py`
  (+ sorties `_131*_out.txt`, planches `_131_apercu.jpg`, `_131_carte_taches.png`,
  `_131b_gros_plans_stf.jpg`, `_131b_meme_zone.jpg`, `_131d_echelle_commune.jpg`, `_131g_avant_apres.jpg`).
- **AUCUN fichier du dépôt modifié** pour ce diagnostic (hors cette mise à jour de `AVANCEMENT.md`).


### Points d'attention
- **PIÈGE — un banc de combine doit poser ses pièges DANS l'ESPACE NORMALISÉ** : les poser en valeurs brutes
  juste au-dessus de p0,25 est FRAGILE (le point noir est lui-même dans le bruit et le p0,25 dépend de la
  graine). Les valeurs 1,1e-6 / −0,02 / −0,30 ne veulent rien dire en brut mais sont celles du mécanisme.
- **PIÈGE — `_amplitude()` est LA référence d'échelle** (p99,7 − p0,25, sous-échantillonnée, coût constant) :
  toute borne « relative » passe par elle, JAMAIS par une constante absolue (c'est le bug du 1e-6).
- **PIÈGE** : `moyennes()` (voie A) applique le recalage de rôle — qui veut un empilement BRUT doit passer
  par `LiveStacker.mean()`.
- **Cadence d'archivage = 1 frame/s PAR RÔLE** (`framestore.ARCHIVE_INTERVALLE_S`) : un banc qui veut N
  frames par rôle doit poser l'archive EXPLICITEMENT (`ArchiveFrames(intervalle_s=0)`).
- **Repli « phase »** (`alignment.py`) peut « aligner » deux champs NON apparentés (mesuré 1/3) : ne jamais
  conclure d'un repli phase qu'un appariement d'étoiles existe.
- Des images d'un AUTRE logiciel traînent dans `Pictures`/`Downloads` : **PAS** des preuves d'un test.

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

- **PROCHAINE SESSION — CHANTIER « CAUSE AMONT » (décidé par Alain, 16/10 au soir)** : le fond du composite
  porte des écarts chromatiques STRUCTURÉS de σ = 1,6 % (BRUT 1,82 % → TRAITÉ 1,61 % : ni le débruitage ni
  GraXpert ne les réduisent) que l'étirement multiplie par ×52. **À INSTRUIRE AVANT TOUTE CORRECTION** :
  (a) les 1 022 taches rouges et 393 bleues du BRUT (aire médiane 4-7 px, +40 % du fond local) et leur
  origine ; (b) le bruit du canal B (2,26 % contre 0,95 % en G — 17-20 frames seulement) ; (c) les pixels
  chauds FIXES résiduels (~2 135 dans R) ; (d) la rotation à 177° d'une partie des frames. Les scripts de
  mesure sont prêts : `C:\Astro\test\_diag_taches_131*.py` (+ sorties `_131*_out.txt`).
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




