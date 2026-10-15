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

## Session du 15/10/2026 — J1 testé EN RÉEL : le Ha est REFUSÉ à l'alignement (→ 129b)

**J1 (v2.81.0) est COMMITÉ** sur `LRGBHa` en **checkpoint** (plomberie seule, correctifs
non appliqués) ; **le test réel l'invalide en l'état** (rôle Ha quasi vide). Cette session
porte **129b** (banc + rejeu réel → les 4 correctifs), qui suivra en SECOND commit.

### État actuel
- Compositions `RGB+Ha` / `LRGB+Ha` déclarées : **5 lignes** rôle+dossier, ancre **broadband**
  (`_broadband_ha()`), **aucune fusion** appliquée (composite identique AU BIT, banc 129 vert).
- **Test réel M33, deux relevés** du même empilement (~30 min d'écart) :
  - (1) `Frames 57` = L14 · R14 · G14 · B14 · **Ha 1** · `Archive 69` · `non alignées 12` → **astrométrie BLOQUÉE** ;
  - (2) `Frames 118` = L30 · R30 · G29 · B20 · **Ha 9** · `Archive 138` · `non alignées 20` · `floues 1` →
    astrométrie + SPCC ont fonctionné. **Dossier Ha = 40 frames ⇒ ~69 % de REFUS sur le Ha.**
- **Le verrou de l'astrométrie est CONFIRMÉ en réel** : elle s'est débloquée pile quand `Ha` a atteint 3.

### Fichiers modifiés dans cette phase (lot 129 — COMMITÉ en checkpoint)
- `processing/composition.py` : `NB_LIGNES_COMPO` (5, source unique), `COMPOSITIONS_HA`,
  `composition_avec_ha()`, les 2 compositions nouvelles, repli `composition_pour_roles` (+Ha en DERNIER).
- `ui/panels/compo.py` (5 lignes) · `ui/app.py` (`range(4)` → `NB_LIGNES_COMPO`, `_maj_compo_info`,
  `_broadband_ha()` NEUF + `_narrowband_ha()` excluant les +Ha) · `ui/config_ui.py` (5 lignes) ·
  `cameras/multifolder.py` (« 1 à 5 ») · `avastack/__init__.py` (version 2.81.0 + changelog 129).
- `bancs/_test_compo_5roles_jalon129.py` (NEUF, 5 volets) · `bancs/_test_compo_ui_jalon19.py` (4 → 5 lignes).

### Mesures / faits vérifiés (rejouables)
- **Les refus SONT des refus d'ALIGNEMENT** : `bad_frames` n'est incrémenté QUE là (`worker.py:1129`) ;
  `Archive − Frames = refus` (138 − 118 = 20). Les frames FLOUES sont comptées à part et rejetées
  **avant** l'archivage (`worker.py:992`), d'où leur absence des 138.
- **`triangles_seuls` = False en LRGB+Ha** : `worker.py:1096` → `self._narrowband_ha()`, et J1 a **EXCLU**
  les compositions +Ha de ce prédicat ⇒ **l'ORB passe en premier**. Or le projet a MESURÉ au jalon 21
  qu'ORB « s'apparie mal d'un filtre à l'autre » (**86 refus** en début de session SHO) — la correction fut
  de SAUTER l'ORB. Ligne d'état passée par `phase` (relevé 1) puis `triangles` (relevé 2) : l'alignement
  VIT dans les replis.
- **Cas INÉDIT** : en HOO/SHO l'ancre EST la brute Ha (le Ha n'est jamais aligné contre un autre filtre) ;
  en LRGB+Ha (ancre broadband, choix J1) **le Ha est le SEUL rôle aligné en INTER-FILTRES**. Réponse
  mesurée à la question d'Alain du 15/10 (« espérons que ça n'empêche pas d'aligner le Ha ») : **oui, ça gêne**.
- **Le Ha n'entre PAS dans la SPCC** (prouvé DEUX fois) : bandes lues **par clé** (`spcc.py:812` et `548`),
  couches **BRUTES** (`moyennes()`, `composition.py:939-951`), conversion des gains par `canaux_rgb`
  (`composition.py:984-991`) — où le Ha n'apparaît pas.
- **Fond BLEU = SPCC appliquée hors modèle** : R ×0.2735 / G ×0.3550 / B ×1.0000 (l'appli AVERTIT :
  B/G 0.327 hors [0,5 ; 1,5]). Le remède DÉJÀ MESURÉ du projet (SPCC + Linear Fit = fond NEUTRE,
  `composition.py:1070-1072`) est neutralisé par `linear_fit_mode = "offset"`, qui force `gains = 1.0`
  (`stacking.py:205-207`) ⇒ **aucun rééchelonnement** : le facteur SPCC reste en place.

### Décisions prises
- **J1 COMMITÉ** sur `LRGBHa` en **checkpoint « plomberie seule »** (option A, Alain 15/10/2026) :
  bancs 129/19 + garde-fou verts (pyright 0 erreur) ; **129b suivra en second commit** et étendra
  l'entrée v2.81.0 (pas de bump) ; **aucune release** tant que le Ha n'est pas utilisable.
- **J1 NON validé en l'état** ; **J2 n'est PAS démarré** : fusionner 1 frame Ha serait inobservable.
- **129b = préalable à J2** : (1) séparer l'**ANCRE** (broadband, inchangée) de la **MÉTHODE**
  (`triangles_seuls = True` dès qu'un Ha est fusionné) ; (2) exclure le Ha **FUSIONNÉ** de
  `profondeur_min()` (en HOO/SHO le Ha reste un CANAL, donc il continue de compter) ; (3) compteur de
  refus **PAR RÔLE** (aujourd'hui `bad_frames` est GLOBAL, `worker.py:720`) ; (4) libellé « frames par
  rôle » de la SPCC (il affiche le MIN = le Ha, un rôle que la SPCC ne mesure PAS).
- **Pas de correctif non mesuré** : le diagnostic doit passer par un **rejeu hors-ligne des vraies frames
  L/G + Ha** dans le vrai aligneur (méthode des jalons 116/117), `triangles_seuls` False vs True.

### Problèmes ouverts
- **Raison EXACTE du refus Ha** non encore nommée sur les frames réelles → objet du rejeu de 129b.
- `B: 20` contre L30 / R30 / G29 : dossier plus court (probable) ou refus caché ? à confirmer.
- **L'aligneur n'écrit RIEN au journal** (`%APPDATA%\AVAStack\journal.txt` ne porte que `démarrage`,
  `astrométrie` [configuration] et `étape`) — hérité 116-118, toujours vrai : c'est ce qui a rendu le
  diagnostic INDIRECT. Un « refus par rôle » journalisé serait un vrai progrès.
- « Patés bleus » de STRUCTURE (hors fond bleu SPCC) : à traiter à part (pistes : gains LRGB,
  `lissage_halos` coché σ = 20).

### Prochaines étapes
- **129b (cette session)** : banc + rejeu des frames réelles → les 4 correctifs → re-test réel.
- Puis **J2** (fusion « ajout au rouge » + poids + cadre « Fusion Ha ») → **J3** → **J4** → **J5**.

### Points d'attention
- **J1 EST COMMITÉ** (checkpoint plomberie : 8 fichiers + le banc 129) ; **le stash `stash@{0}` reste
  à GARDER** (essai antérieur, non commité).
- **Le rôle Ha COMPTE dans `profondeur_min()`** (`composition.py:857` / `worker.py:1267`) : c'est le seuil
  de l'astrométrie, de la photo ET de la SPCC (`ASTRO_MIN_FRAMES = 3`, `astrometrie.py:67`). Tant que le Ha
  reste bas, **les trois mesures sont bloquées** — MESURÉ, pas théorique.
- **Repli « phase »** (`alignment.py:839-864`) : refuse si la forme ≠ référence, si |Δ| > 40 px, ou sans
  gain SSD net — et il travaille dans le domaine 8 bits **PARTAGÉ** (leçon 116① : écrase une frame d'un
  autre filtre).
- Test décisif du fond bleu (5 s, à confirmer) : **décocher la case SPCC** → le bleu doit disparaître.
- Des images d'un AUTRE logiciel traînent dans `Pictures`/`Downloads` (caméra tout-ciel, labels avion) :
  ce ne sont **PAS** des preuves d'un test AVAStack — ne pas s'y tromper.

---

## Chantier en cours — LRGB+Ha / RGB+Ha (jalons 129 → 129b → J2 → J5)

Le rôle Ha **n'alimente AUCUN canal** : il est **FUSIONNÉ au composite** après le combine L (canal rouge).
L'UI a **5 lignes** (rôle + dossier) : L, R, G, B, Ha.

| Jalon | Contenu | État |
|---|---|---|
| **J1 / 129** (v2.81.0) | compositions + 5 lignes + séparation ancre / `_narrowband_ha` | **commité** (checkpoint, banc vert), test réel KO (Ha refusé) |
| **129b** | Ha utilisable : méthode d'alignement + `profondeur_min` + refus par rôle + libellé SPCC | **PROCHAINE SESSION** |
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

- **129b — SESSION EN COURS (J2 attend derrière)** : rendre le Ha utilisable — banc + rejeu hors-ligne
  des vraies frames L/G + Ha dans le vrai aligneur (`triangles_seuls` False vs True), puis les 4
  correctifs, puis re-test réel.
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

- **LE RÔLE Ha FUSIONNÉ FAUSSE `profondeur_min()`** (min des rôles non vides) : il bloque l'astrométrie,
  la photométrie ET la SPCC (`ASTRO_MIN_FRAMES = 3`) — MESURÉ au test réel du 15/10.
- **EN LRGB+Ha, LE Ha EST LE SEUL RÔLE ALIGNÉ EN INTER-FILTRES** (l'ancre est broadband) et il est REFUSÉ
  massivement (~2/3 mesuré) : `triangles_seuls` est False (ORB d'abord), et le projet SAIT depuis le
  jalon 21 qu'ORB s'apparie mal d'un filtre à l'autre.
- **SPCC : le mode « offset » du Linear Fit NE RÉÉCHELONNE PAS** (`gains = 1.0`, `stacking.py:205`) — un
  coefficient SPCC extrême (fond bleu) n'est donc PAS compensé. Et la SPCC AVERTIT quand son modèle décrit
  mal l'image (pente hors [0,5 ; 1,5]) : dans ce cas, ne pas l'appliquer sans réfléchir.
- **`bad_frames` est GLOBAL** (un seul compteur de session) : impossible de lire les refus PAR RÔLE.
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




