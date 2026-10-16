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

## Session du 16/10/2026 — ⏹ SESSION CLOSE — re-test 129b validé (alignement) + DÉFAUT D'IMAGE NOMMÉ (combine LRGB) — 129b COMMITÉ ET POUSSÉ

> **CLÔTURE.** Décision d'Alain : « Lisser le combine LRGB » **était déjà cochée** (la fiche ne le dit pas —
> voir le piège ci-dessous) ; **129b est COMMITÉ et POUSSÉ** sur `LRGBHa` ; le jalon « halos et points
> colorés » (combine LRGB) est OUVERT mais **RIEN N'A ÉTÉ CODÉ** (consigne explicite : prendre connaissance,
> commiter, clôturer).

### État actuel
- **129b COMMITÉ et POUSSÉ** (décision d'Alain, cette session) — commit **`cfd40d0`** sur `LRGBHa` :
  6 fichiers (4 code + `CLAUDE.md` + `AVANCEMENT.md`) + 2 bancs (`_test_voie_a_ha_jalon129b.py`,
  `_diag_align_ha_reel_129b.py`), 8 fichiers / +1353 −112. Entrée de changelog **v2.81.0 étendue**
  (pas de bump, pas de release). Bancs rejoués avant le commit : **129b (7 volets) VERT** +
  **garde-fou refactoring VERT** (pyright 0 erreur).
- **Re-test réel du 16/10 (M33, composition `LRGB+Ha`, 441 frames, v2.81.0 + 129b non commité) : le Ha
  MONTE ENFIN** — retour d'Alain : « tout empilé à part 2 frames du rôle R ». La **voie A est VALIDÉE sur
  son point d'acceptation** (plus de ~69 % de refus sur le Ha) ; astrométrie/photo/SPCC ne sont plus
  freinées par le Ha. **129b-A reste NON COMMITÉ.**
- **MAIS l'image finale n'est pas utilisable** (FITS + PNG + fiche `M 33_LRGBHa 2.81.0.*`, 16/10 11:16) :
  **anneaux sombres autour des étoiles**, **« points colorés » partout**, fond bleu.
- **CAUSE NOMMÉE PAR LA MESURE : le COMBINE LRGB de `composer()`** (`ratio = L/luma` puis
  `rgb *= ratio`, `processing/composition.py:596-614`). **PAS imputable à 129b** : le diff 129b ne touche
  que le RÔLE Ha (le broadband est inchangé) et le MÊME défaut existait le 14/10 en v2.80.3 — dans un
  fichier qu'Alain avait déjà nommé `M 33_LRGBHa_points_colores.fits`.

### Fichiers modifiés / produits dans cette phase
- **AUCUN fichier de code modifié** (session de DIAGNOSTIC). Les 6 fichiers + 2 bancs de 129b restent NON
  COMMITÉS, tels quels.
- `CLAUDE.md` : 2 leçons durables ajoutées (§ combine LRGB du jalon 117) — le rapport `L/luma` **brut**
  est NON BORNÉ et NÉGATIF, il fabrique les points colorés ET les anneaux noirs ; un banc de combine ne
  vaut que par son ÉCHELLE (ciel 0,03/cœur 0,5 ne reproduit rien).
- Diagnostics (hors dépôt, `C:\Astro\test\`) : `_diag_image1..7_129b.py` (image finale + comparaison de
  toutes les sorties du banc d'essai), `_diag_chroma_129b.py`, `_diag_anneaux_rejeu_129b.py` (GraXpert +
  NLM par couche), `_diag_composer_rejeu_129b.py` (4 vraies couches → `composer()`), `_diag_extremes_129b.py`
  (origine des extrêmes). **À CONSOLIDER EN UN SEUL BANC** quand le jalon s'ouvrira.

### Mesures / faits vérifiés (rejouables)
- **Sortie du 16/10 contre tout le banc d'essai** (`_diag_image7_129b.py`, 18 fiches FITS+JSON) : pixels à
  écart inter-canal > 0,1 = **18,1 %** (5-6 % partout ailleurs) ; **B écrêté à 1,0 = 0,582 %** (0,01-0,10 %
  avant) ; **G au PLANCHER exact 0,0010 = 0,93 %** (l'ancien défaut était un plancher à 0,0) ;
  **corr(R,B) = −0,06** (les canaux ne portent plus la même image) ; géométrie des zones fautives =
  **anneaux** (bord rempli 0,14-0,25) de 40-48 px autour des étoiles, plus des points isolés de 1 px.
- **GraXpert live PAR COUCHE est INNOCENT** (`_diag_anneaux_rejeu_129b.py`, vraie brute G, **commande exacte**
  du test) : creux r 3..12 px = **0,999**, **aucun négatif**, profil de l'étoile préservé (20,6 → 2,7 → 1,0).
- **NLM (force 1,0) par couche INNOCENT** : creux **1,010**, profil inchangé.
- **Chroma INNOCENTE** (`_diag_chroma_129b.py`, scène fidèle ciel 0,001 / cœur 10, rapport 10⁴) : correction
  ≤ 1 % dans les ailes, aucun extrême créé ; à l'échelle du banc 67 (ciel 0,03 / cœur 0,5) l'effet est nul
  aussi. *(Warning `overflow in power` de `_poids_structure` : bénin, poids → 0, mais à nettoyer.)*
- **`composer()` REJOUÉ sur 4 vraies couches** (une brute par rôle L/R/G/B de la nuit du 22/09, alignées par
  le vrai `StarAligner`, recadrées au cadre du test) :
  **anneau ×2,8 à r ≈ 8-10 px** autour de l'étoile quand la case « Lisser le combine LRGB » est DÉCOCHÉE
  (`sigma_l=0`, le réglage du test) — creux R/G/B = 1,195/1,099/1,095 ; **il DISPARAÎT avec le lissage**
  (`sigma_l=None`) — creux 0,982/1,019/0,921 et profil monotone. C'est le mécanisme du jalon 117c, reproduit
  au chiffre près (« halo ×2,8 »).
- **Le rapport `L/luma` est NON BORNÉ, et même NÉGATIF** : mesuré **max 110,1**, p99,99 = 4,29, 0,54 % des
  pixels > 2, **min −1,037** (la normalisation par rôle `(a − p0,25)/(p99,7 − p0,25)`, SANS clip, laisse L et
  `luma(rgb)` de signes opposés). Sur le composite : R **−36..425**, G **−467..15**, B **−0,33..1292** —
  alors que le MÊME composite **SANS** la couche L reste sain (R −0,17..26,9, G −0,20..28,5, B −0,18..21,9).
  ⇒ **les extrêmes qui deviennent, après étirement et écrêtages, les points colorés et les anneaux noirs
  viennent TOUS du combine LRGB** (pas d'un outil externe, pas du débruitage, pas de la chroma).

### Décisions prises
- **129b-A est VALIDÉ sur son point d'acceptation** (le rôle Ha n'est plus refusé, 441 frames empilées,
  2 refus en R seulement) — **son commit reste à l'accord d'Alain** : l'image n'est pas exploitable tant que
  le combine LRGB n'est pas réglé.
- **Périmètre 129b INCHANGÉ** : voie A + 3 correctifs + banc neuf. **Aucun correctif de code n'a été écrit
  cette session** (règle « pas de correctif non mesuré » + « demander avant de démarrer le jalon suivant »).
- **J2 (fusion Ha) NON DÉMARRÉ** : il reste derrière la décision sur le combine LRGB.

### Problèmes ouverts
- **LA CASE « Lisser le combine LRGB » ÉTAIT DÉJÀ COCHÉE au test du 16/10** (constat d'Alain) ⇒ **le
  lissage NE SUFFIT PAS** : mesuré, l'excès ×2,8 des ailes disparaît mais les **extrêmes du ratio sont
  IDENTIQUES** (+1292 / −467 avec ET sans lissage). **Le correctif BORNÉ est donc nécessaire** (il n'y a
  aucun remède « sans code » à proposer).
- **Correctif à écrire** (jalon « halos et points colorés », AVANT J2) : BORNER le ratio (`clip`, jamais
  négatif) et remonter le PLANCHER du dénominateur de 1e-6 à une fraction de l'échelle du rôle, + banc NEUF
  à échelle réelle (la scène du banc 67 est aveugle à ce défaut). **Inclure** : faire DIRE à la fiche de
  rendu si le lissage du combine est actif (`_fiche_chaine()` n'émet AUCUNE étape pour lui — seul l'en-tête
  `AVACOMPO` du fichier linéaire le porte ; c'est ce silence qui a fait croire à une case décochée).
- `B: 20` contre L30/R30/G29 dans le test du 15/10 : dossier plus court ou refus caché ? toujours à confirmer.
- **L'aligneur n'écrit RIEN au journal** (hérité 116-118) : le diagnostic reste indirect (les refus par rôle
  sont à l'ÉCRAN, pas encore au journal).
- **Limites connues de la voie A** : bords de la couche Ha recalée à zéro hors champ couvert ; référence Ha
  posée UNE fois par session ; recalage d'empilement qui garde le précédent en cas d'échec.

### Prochaines étapes
- **DÉCISION attendue d'Alain** : (1) commiter 129b tel quel (plomberie J1 + voie A) — l'alignement est
  validé et l'image dépend d'un défaut PRÉEXISTANT ; (2) ouvrir le jalon « combine LRGB : halos et points
  colorés » (correctif borné + banc neuf) AVANT J2.
- Si accord : rejouer d'abord le défaut sur une **couche réelle complète** (empilement, pas une brute) pour
  chiffrer le gain du correctif.

### Points d'attention
- **129b-A est NON COMMITÉ** : 6 fichiers + 2 bancs, plus `CLAUDE.md` et cet `AVANCEMENT.md`. Le stash
  `stash@{0}` reste à GARDER.
- **PIÈGE (mesuré cette session) — un banc de combine doit utiliser de VRAIES couches ET la vraie échelle** :
  ciel normalisé ~10⁻³ / cœur 10-27 (rapport 10⁴) ; l'alignement et les PSF par filtre font partie du
  mécanisme. La scène « banc 67 » (ciel 0,03 / cœur 0,5) ne montre NI anneau NI extrême.
- **PIÈGE — LA FICHE DE RENDU NE DIT PAS TOUT** : `_fiche_chaine()` (`ui/saver.py`) n'émet AUCUNE étape pour
  le **lissage du combine LRGB** (seul l'en-tête `AVACOMPO` du fichier linéaire le porte). Un JSON muet sur un
  réglage n'est donc PAS une preuve qu'il était inactif — ne jamais conclure sans MESURER (leçon « config.json
  ne dit pas la réalité », appliquée ici à la fiche).
- **PIÈGE** : `moyennes()` (voie A) applique le recalage de rôle — tout consommateur qui veut un empilement
  BRUT doit passer par `LiveStacker.mean()`.
- **PIÈGE** : en mode MONO `self.stacker` est un `LiveStacker` — pas de `note_alignement(role=…)`.
- **Cadence d'archivage = 1 frame/s PAR RÔLE** (`framestore.ARCHIVE_INTERVALLE_S`) : un banc qui veut
  N frames par rôle doit poser l'archive EXPLICITEMENT (`ArchiveFrames(intervalle_s=0)`).
- **Repli « phase »** (`alignment.py`) peut « aligner » deux champs NON apparentés (mesuré 1/3) : ne jamais
  conclure d'un repli phase qu'un appariement d'étoiles existe.
- Des images d'un AUTRE logiciel traînent dans `Pictures`/`Downloads` : ce ne sont **PAS** des preuves
  d'un test AVAStack.

---

## Chantier en cours — LRGB+Ha / RGB+Ha (jalons 129 → 129b → J2 → J5)

Le rôle Ha **n'alimente AUCUN canal** : il est **FUSIONNÉ au composite** après le combine L (canal rouge).
L'UI a **5 lignes** (rôle + dossier) : L, R, G, B, Ha.

| Jalon | Contenu | État |
|---|---|---|
| **J1 / 129** (v2.81.0) | compositions + 5 lignes + séparation ancre / `_narrowband_ha` | **commité** (checkpoint, banc vert), test réel KO (Ha refusé) |
| **129b-A** | Ha utilisable : **voie A** (référence PAR RÔLE + recalage de l'EMPILEMENT) + `profondeur_min` + refus par rôle + libellé SPCC | **IMPLÉMENTÉ** (banc neuf 7 volets VERT, pyright 0) — **re-test réel du 16/10 : voie A VALIDÉE** (441 frames, 2 refus en R seulement) ; **commit en attente d'accord** |
| **J-CLRGB** (nouveau, proposé) | combine LRGB : **borner** le rapport `L/luma` + plancher de dénominateur relatif + banc NEUF à échelle réelle | **à ouvrir sur accord d'Alain** (cause mesurée des anneaux/points colorés du 16/10) |
| **J2** | fusion « ajout au rouge » (DÉFAUT) + poids + cadre « Fusion Ha » | après 129b |
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

- **DÉCISION D'ALAIN (2 points)** : ① **commiter 129b** (les 6 fichiers modifiés + `bancs/_test_voie_a_ha_jalon129b.py`
  + `bancs/_diag_align_ha_reel_129b.py` ; l'entrée de changelog **v2.81.0 est déjà étendue** — pas de bump, pas
  de release) : la voie A est **validée en réel** (441 frames, 2 refus en R) et le défaut d'image vient du
  combine LRGB, PRÉEXISTANT ; ② **ouvrir le jalon « combine LRGB : halos et points colorés »** (borner le
  rapport `L/luma`, jamais négatif, plancher de dénominateur RELATIF à l'échelle du rôle, + banc NEUF sur de
  vraies couches) — c'est le chemin pour rendre l'image utilisable avant de démarrer **J2**.
- **Remède à tester par Alain** : il n'y en a plus de « gratuit » — la case « Lisser le combine LRGB » était
  DÉJÀ cochée au test du 16/10 et l'image est mauvaise quand même (les extrêmes du ratio ne sont pas traités
  par le lissage). **Le seul chemin est le correctif borné du jalon « halos et points colorés »**.
- Jalon 128 (v2.80.0) : à valider en réel si ce n'est pas déjà fait (l'image VeraLux reste pendant un recalcul).
- Livré/validé : v2.79.0 (chaîne pré-étirement unique + chroma des DEUX moteurs) validé M33 ; v2.80.0 publiée.
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

- **TRAITÉ au 129b-A — À VÉRIFIER EN RÉEL** : le Ha **FUSIONNÉ** ne pend plus à `profondeur_min()`
  (`role_ha_fusionne()`), les refus sont comptés **PAR RÔLE** (`bad_frames_par_role` → ligne UI) et le
  libellé « frames par rôle » (SPCC **et** photo) décrit les **bandes mesurées** (`_profondeur_spcc`).
  Le VERROU D'ALIGNEMENT du Ha est traité par la **voie A** (le Ha s'aligne sur lui-même).
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

- **12/10/2026** : jalon 128 (v2.80.0) — l'image VeraLux reste à l'écran pendant un recalcul (« Recalculs en
  cours ») ; release GitHub PUBLIÉE (4 installateurs + `INSTALLATION.md`).
- **12/10/2026** : jalon 127 (v2.79.0, incl. 126) — chroma pour les DEUX moteurs + bancs 63/65 réparés ;
  validé M33 ; poussé.




