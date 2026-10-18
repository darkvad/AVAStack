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

Versions : `LRGBHa` = **v2.89.0** (①/②/③ validés en réel ; **136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum **VALIDÉ EN RÉEL le 19/10**, **J3** cinq modes) ·
`master` publié = **v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 — J2 VALIDÉ EN RÉEL + J3 LIVRÉ (cinq modes)

### État actuel
- **Code** : **v2.89.0** sur `LRGBHa` — **J2 VALIDÉ EN RÉEL** par Alain (19/10)
  et **J3 LIVRÉ** (les 4 autres modes + α) ; bancs J2/J3 verts, non-régressions
  vertes, garde-fou vert, pyright 0. **Commité et poussé** (`8714afb`) : J2 et J3
  dans le MÊME commit (le J2 n'avait pas encore été commité) ; **aucune release
  sans accord**.
- **J4** = continuum (méthodes médiane / étoiles 5σ, case « recentrer ») ;
  **J5** = ancre réelle + doc.

### Verdict réel de J2 (consigné)
- **AVEC continuum** : réglage de force visible, rendu retenu. **SANS** : les
  rouges « s'éteignent un peu » ⇒ le continuum non soustrait se voit ; ne pas
  le prendre pour un défaut du Ha.
- **Q retenu : 0,80** (défaut) · **poids poussé à 1,5 SUR CETTE CIBLE** (M33) :
  réglage **PAR CIBLE**, le défaut reste **1,0**. Aucun défaut bloquant signalé.
- **Verdict global : VALIDÉ.**

### Fichiers modifiés dans cette phase
- `avastack/processing/composition.py` : 5 modes, α, poids = interpolation,
  clé de mémoïsation (α), docstrings.
- `avastack/ui/panels/compo.py` (champ α), `ui/app.py` (`_lire_fusion_ha`,
  `_maj_fusion_ha`), `ui/config_ui.py` (`fusion_ha_alpha`), `ui/saver.py` (fiche).
- `avastack/__init__.py` (**2.89.0** + changelog), `CLAUDE.md` (§ J3 + verdict J2).
- `bancs/_test_fusion_ha_jalon3.py` (NEUF, 8 volets) ;
  `bancs/_test_fusion_ha_jalon2.py` (3 volets mis à jour VOLONTAIREMENT).

### Décisions prises
- **J3 — le POIDS est une FORCE GLOBALE** : `sortie = composite + poids ×
  (mode − composite)` ⇒ poids 0 = composite du J1 AU BIT pour les CINQ modes,
  poids 1 = opérateur exact. Évite que α et poids se confondent.
- **`ha_luminance` touche V et B** (ajout de `s` aux trois canaux) : seule
  exception assumée à « V et B jamais touchés ».
- **α n'agit que sur `fondu_rouge`** ; champ désactivé ailleurs, valeur conservée.

### Prochaines étapes
1. **Test réel de J3 par Alain** (comparer les modes, surtout fondu et écran) ;
2. **J4** sur son accord, puis **J5** ; **release v2.89.0 sur accord explicite**.

---

## HISTORIQUE — 18/10/2026 (détail : changelog v2.86.0/v2.87.0/v2.88.0)

①/②/③ validés en réel · **136** halo coloré et **137** neutralisation STF
(v2.86.0) · **141-B** interface, validée (v2.87.0) · **J2** fusion du Ha +
continuum (v2.88.0, validé le 19/10) · garde 133 astrométrie livrée · `phase`
écartée en broadband ET narrowband · combine innocenté (140/142/143).

### Validations en réel du 18/10 (détail dans `CLAUDE.md`)
- **②** : 472 frames (L 240 · R 79 · G 62 · B 51 · Ha 40), 2 refus, **0,00 %** de
  pixels à 0, canaux R−V 0,079 px / B−V 0,130 px ⇒ aucune régression. ⚠ Le « tel
  que vu » se mesure MAL : la géométrie se lit sur le **LINÉAIRE**.
- **③** : 206 frames (S2 80 · Ha 55 · O3 71), 0 non alignée, aucune méthode
  `phase`, canal Ha net, aucun coin noir.
- **SPCC** : la FONCTION RESTE, l'enquête est CLOSE (alerte « par construction »,
  rendu meilleur qu'avec les gains Gaia) — **ne pas rouvrir**.
- **Run LRGB** : plus aucune tache bleue NI rouge ⇒ `phase` en broadband était la
  SEULE cause ; astrométrie réussie avec les bons indices (garde 133).

### Mesures du chantier (détail dans `CLAUDE.md`, changelog v2.82.2) — **ne pas rejouer**
140 RGB propre · 142 LRGB R +103,9 % / B +132,1 % · 143 B +80,7 % · 144 B +34,6 % ·
poids 0,857 et σ ×4,38 aux 243 taches.

### Astrométrie — RÉSOLUE (18/10) : les AD/Dec saisies étaient celles de M31
Champs **M31** sur des brutes **M33** ; avec les bons indices le solve résout
(115 appariements, 2,469″/px, rms 0,30 px) — `CLAUDE.md` § « Diagnostic de
l'entrée d'astrométrie » ; preuves dans `C:\Astro\test\` (`_dump154_*`).

### Décisions prises (18/10 — TRANCHÉES, ne pas rouvrir)
- **Combine hors de cause** (140/142/143) ⇒ on ne touche pas à `_ratio_combine` ;
  **cause UNIQUE mesurée** : `phase` en broadband (le run de ① efface bleu ET
  rouge) ⇒ l'hypothèse « rouge = contenu des 240 brutes L » est ABANDONNÉE.
- **①/③** : `phase` écartée en broadband ET en narrowband, aligneurs du Ha
  (voie A) NON touchés ; **pas de case** (le drapeau est fixé par session).
- **② = choix C** (raffiner au-delà de `TRI_RAFFIN_SEUIL` 0,30 px) : gain
  < 0,05 px sur 66 % des frames, mais 12 à 50 % de l'erreur là où il sert.
- **141 = B (PRÉVENIR), LIVRÉE (v2.87.0) ET VALIDÉE EN RÉEL** : la composition
  affichée ne peut plus mentir en silence ; A = documenter, C = invalider :
  écartés.
- **VeraLux = CLOS** (piédestal 122 + neutralisation 123/124 suffisent, fichier
  tiers GPL NON modifié) ; **résidu L (~0,48 px) = ABANDONNÉ** ; **la FONCTION
  SPCC RESTE** (seule l'enquête sur son alerte est close).
- **Teinte des COINS ±15-20 % = DÉGRADÉ** (1,3 % en linéaire, ×18 par la MTF) :
  un gain global n'y peut rien ⇒ GraXpert/ABE ou estimateur par région, **à
  trancher par Alain** ; mesurée, non traitée.
- **J2 = fusion « ajout au rouge » ACTIVE PAR DÉFAUT** (poids 1,0) : le Ha
  n'est plus ignoré ; le Ha est RECENTRÉ sur son fond (sans quoi la
  normalisation commune inonderait le rouge) ; **poids 0 = retour AU BIT au
  composite du J1** ; seules RGB+Ha / LRGB+Ha sont concernées. **VALIDÉ EN RÉEL
  le 19/10** (poids 1,5 sur M33, par cible ; défaut 1,0).
- **J2 inclut le CONTINUUM** (Alain, 18/10) : `Q × 7/100 × (R − fond(R)) /
  échelle(Ha)`, référence **R**, **Q 0,80**, écrêtage [0 ; 1], **ACTIF par
  défaut** et **coupable d'une case** — pour juger AVEC et SANS (un défaut vu
  sans continuum peut n'être que du continuum non soustrait). **Vérifié en
  réel** : sans la case, les rouges s'éteignent un peu.
- **J3 = cinq modes + α** : le poids est une **FORCE GLOBALE**
  (`composite + poids × (mode − composite)`) ⇒ poids 0 = composite du J1 au bit
  pour TOUS les modes ; `ha_luminance` touche V et B (exception assumée) ;
  α ne sert qu'au fondu.
- **134c invalide** (brute dithérée) ; **135/136/138** annulées.

### Problèmes ouverts
- **Aucun** sur ①/②/③/136/137/141-B/J2/J3 : livrés, mesurés, bancs verts. Seul
  reste à JUGER À L'ÉCRAN : le rendu des modes J3 (fondu, écran en priorité).
- En attente d'une décision : **teinte des COINS ±15-20 %** (dégradé) — GraXpert/
  ABE ou estimateur par région, à trancher ; mesurée, non traitée.

### Reste, sans urgence
Store (v2.71.1 publiée), Linux machine vierge + `--cameras`, INDI après Linux,
macOS jamais testé.

### Points d'attention
- **TROIS noms de composition** (141-B) : `stacker.composition`/`_compo_nom` (ce
  que la SOURCE empile, source de `AVACOMPO`), `_compo_session` (armée au
  « ▶ Démarrer »), `var_compo` (le MENU). Le bandeau ne compare que les deux
  derniers. **`"RGB+Ha"` est une sous-chaîne de `"LRGB+Ha"`** : jamais
  `startswith`/`in` pour identifier une composition écrite.
- **J2 — la fusion est ACTIVE PAR DÉFAUT** : `CompositeStacker.fusion_ha = None`
  ne veut PAS dire « rien », mais « défauts figés » (ajout_rouge, poids 1,0).
  Pour désactiver : `{"poids": 0.0}`. Le réglage entre dans la CLÉ de
  mémoïsation (sinon bouger le poids ne réafficherait rien) et dans le 9e
  élément de `disp.vl_compo` (déballage tolérant : un ancien 9e élément
  booléen est ignoré) ; la fiche ne le déclare que si une couche Ha a des
  frames.
- **J2 — CONTINUUM** : actif par défaut, **case ET Q désactivés sans dossier
  R** (le réglage effectif est alors forcé à False) ; l'échelle qui ramène R
  dans l'espace du Ha est le DÉNOMINATEUR de normalisation du Ha — ne pas le
  remplacer par 1 sans regarder le mode de normalisation. La méthode est
  `bandes_passantes` ; les deux autres (médiane, étoiles 5σ) restent au J4.
- **J3 — α n'agit QUE sur `fondu_rouge`** : le champ est désactivé ailleurs mais
  TOUJOURS lu/persisté (`fusion_ha_alpha`), et α entre dans la CLÉ de
  mémoïsation (sinon le réglage paraît « sans effet »).
- **J3 — `ha_luminance` touche V et B** : c'est son objet. Ne pas en conclure
  une régression du type « la fusion ne devrait toucher que le rouge » — les
  quatre autres modes, eux, laissent V et B AU BIT.
- **J3 — comparer les TROIS canaux** : `ajout_rouge` et `ha_luminance` ont le
  même rouge ; un banc qui ne lit que R croit à un doublon (piège rencontré).
- **Une brute est DITHÉRÉE** : seul un empilement ALIGNÉ prouve quelque chose.
- **`--dossier` sans `--dark` = run invalide** dès que l'exposition change.
- **Comparer deux BRUTES par corrélation est INVALIDE si le dossier mélange des
  nuits** (B : 14→23/09) ; les `cadre` de deux runs ne se comparent pas non plus.
- `save_canaux_request` : attendre l'écriture des couches avant de quitter
  l'appli ; brutes NINA : `BZERO/BSCALE` ⇒ `memmap=True` refusé par astropy.
- **Bancs 132 / 133 / 134** : ce qui ne se scénarise pas se teste par le CHEMIN
  DE DÉCISION (espion) — voir `CLAUDE.md` (phase : espion sur `_phase` ; garde
  133 : `wk._nom_cible_proche` patché + JOURNAL ; 134 : `cv2.setRNGSeed`).
- **Instrumentation de l'aligneur** : l'empreinte seule ne joint pas une mesure à
  une frame (re-stacks, recalage Ha et propagation réalignent des EMPILEMENTS) —
  les marquer et les exclure (`_espion_155.marquer_restack`).
- **`_triangles` n'est PAS « la matrice LMEDS brute »** : il consolide déjà et
  laisse **0,015-0,035 px** sur un champ synthétique. Un décalage synthétique ne
  franchit donc JAMAIS `TRI_RAFFIN_SEUIL` — on teste le CÂBLAGE, pas une fiction.
- **Banc 134** : « au bit » exige `cv2.setRNGSeed(n)` avant CHAQUE appel
  (RANSAC/LMEDS tirent dans le générateur global d'OpenCV). Et `triangles` /
  `triangles+étoiles(n)` sont deux méthodes distinctes : les bancs 15 et 21
  exigent `== "triangles"` et restent verts (leur résidu est ~0,03 px).

### Contexte de reprise (à coller — 2 phrases)
Arbre **v2.89.0** sur `LRGBHa` : **J2 VALIDÉ EN RÉEL** (19/10 — Q 0,80, poids 1,5
sur M33, par cible ; défaut 1,0) et **J3 LIVRÉ** (cinq modes de fusion + α), bancs
J2/J3 verts, non-régressions vertes, garde-fou vert, pyright 0. Prochaine action
unique : **test réel de J3 par Alain** (comparer les modes), puis **J4** sur son
accord — aucune release sans accord.

---

## Chantier en cours — LRGB+Ha (jalons 129 → J5) — J2 validé, J3 livré

Le rôle Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le combine L.

| Jalon | Contenu | État |
|---|---|---|
| J1 / 129 (v2.81.0) | compositions + 5 lignes UI + séparation ancre / `_narrowband_ha` | commité |
| 129b | voie A (référence **PAR RÔLE** + recalage de l'empilement) + `profondeur_min` + refus par rôle | COMMITÉ ; validé en réel le 16/10 (441 frames, 2 refus en R) |
| **130 (v2.82.0)** | combine LRGB borné [0 ; 5] + repli local + fiche + banc neuf | COMMITÉ + POUSSÉ (`ef0c35c`) |
| **J2 (v2.88.0)** | fusion « ajout au rouge » + poids 1,0 + recentrage + **continuum (Q, case)** + cadre « Fusion Ha » | **VALIDÉ EN RÉEL le 19/10** |
| **J3 (v2.89.0)** | `fondu_rouge` (α), `ecran_rouge`, `eclaircir_rouge`, `ha_luminance` + poids = force globale | **LIVRÉ** — test réel à faire |
| J4 → J5 | continuum méthodes **médiane / étoiles 5σ** (+ case recentrer) ; ancre réelle + doc | à faire |

Plan figé (13 arbitrages du 15/10) : poids **1,0** (0–10) · α **0,5** · Q **0,80**
(0,10–2,00) · cadre « Fusion Ha » visible seulement si la compo contient Ha ·
continuum = **bandes passantes** (Ha 7 nm / RGB 100 nm), référence **R** ·
identifiants en français (`synthetise`).

---

## En attente / prochaine session (état au 19/10 — J2 validé, J3 livré, `LRGBHa`)

- **Prochaine action unique** : **test réel de J3 par Alain** — comparer les
  modes (fondu et écran en priorité), régler α si besoin ; J4 ne s'ouvre
  qu'après son verdict.
- **J2 VALIDÉ EN RÉEL (19/10)** : AVEC continuum, réglage de force visible et
  rendu retenu (Q 0,80) ; SANS, les rouges « s'éteignent un peu ». Poids 1,5
  poussé sur M33 = réglage **par cible** (défaut 1,0).
- **J3 LIVRÉ (v2.89.0)** : cinq modes, poids = force globale (0 = composite du
  J1 au bit), α du fondu persisté ; banc neuf vert.
- **DÉCIDÉ le 18/10 (Alain)** : neutralisation **hors mode manuel** (confirmé) ;
  boutons sans Siril (⬇ Gaia / Spectres / Base SPCC) **laissés en l'état**
  (secondaire) ; **teinte des COINS** **notée, sans action**. Seule attente :
  **release v2.89.0**, sur accord explicite.
- **141-B VALIDÉE EN RÉEL (18/10)** : bandeau + boîte confirmés ; le fichier
  garde l'`AVACOMPO` de la session (comportement voulu). **Rien à retester.**
- Rappel de méthode : un défaut vu **sans** continuum peut n'être que du
  continuum non soustrait — le noter comme tel, pas comme un défaut du Ha.

- **Validé en réel (18/10)** : run LRGB **sans aucune tache bleue ni rouge**,
  **2 refus R + 1 G**, astrométrie **réussie** avec les bons indices.
- **Reprise** : `CLAUDE.md` § « Diagnostic de l'entrée d'astrométrie » (lire
  `indices` dans le dump AVANT tout) ; mesures dans `C:\Astro\test\`
  (`_dump154_*`, `_diag_astro_152/153*.py`, `_astap148*\`) — astrométrie RÉSOLUE.
- **Décisions d'Alain (18/10, après-midi)** : **①, ② (C) et ③** sont **LIVRÉS et
  VALIDÉS en réel** (v2.82.2 / v2.83.0 / v2.84.0) ; **141 = B (prévenir)**,
  **LIVRÉE en v2.87.0** ; **VeraLux = clos** (piédestal + neutralisation
  suffisent, fichier GPL intact) ; **halo coloré = CORRIGÉ (136)** ;
  **neutralisation après étirement en STF = FAITE (137)** ; **résidu L =
  abandonné** (trace `CLAUDE.md`) ; **la FONCTION SPCC RESTE** — seule l'enquête
  sur l'alerte orange est close. Prochain jalon : **LRGB+Ha J2**.
- **RÉSOLU (141)** : « M33 en RGB montre les mêmes taches » = session **LRGB+Ha**
  avec l'interface passée en « RGB » **pendant** l'empilement (`AVACOMPO=LRGB+Ha…`).
  ⇒ remède retenu (B) : **prévenir** quand la composition change en session —
  bandeau + une boîte, v2.87.0.
- **VeraLux (CLOS)** : ancre soustraite par canal, ~97 % du ciel consommé ⇒ fond
  ×20 à ×40, **déjà traité** par le piédestal (122) + la neutralisation après
  étirement (123/124). **Ne pas modifier `veralux_core_headless.py` (GPL).**
- **136 / 137 (détails dans `CLAUDE.md`)** : halo coloré corrigé par **gains par
  canal AVANT la courbe** (le point noir COMMUN du STF écrêtait R à 0 dans 97,34 %
  des pixels) ; neutralisation après étirement désormais active **en STF aussi**
  (moteurs automatiques, manuel exclu) et ne corrige qu'un RÉSIDU. La **teinte
  des coins ±15-20 %** est un DÉGRADÉ : à trancher (GraXpert/ABE ou estimateur
  par région).
- Boutons de données sans Siril (« ⬇ Gaia », « ⬇ Spectres », « ⬇ Base SPCC ») :
  **LAISSÉS EN L'ÉTAT** — ils téléchargent les CATALOGUES, pas la correction.
  **INDI** = jalon à part, après Linux ; **Store** = cadence séparée (v2.71.1).
- Retour arrière en un geste : `git checkout -- avastack/processing/composition.py`.

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

- **141-B — les noms de composition se CONTIENNENT** : `"RGB+Ha"` est une
  sous-chaîne de `"LRGB+Ha"` ⇒ jamais `startswith`/`in` pour prouver ce qui est
  écrit ; lire `AVACOMPO` en coupant à la virgule (`split(",")[0].strip()`).
  Et armer une session sans avoir posé le menu crée un écart LÉGITIME (défaut du
  menu = HOO) : poser le menu avant `_armer_compo_session()`.
- **Un jeu SANS le défaut ne mesure que l'ABSENCE DE COÛT** : 109 frames
  narrowband sans aucun retournement donnaient « retirer `phase` ne change rien » ;
  sur **Sh2-132** (204 frames, **31 retournements**), la phase finalisait
  **22 frames** — 21 Ha **fausses de 1,1 à 2,3 px** (résidu 0,857 px au lieu de
  0,065) et **1 O3 À L'ENVERS** (0 appariement, |angle| 173,4°). Avant de conclure
  « aucun coût », vérifier que le défaut est REPRÉSENTÉ dans le jeu (compter les
  |angle| > 170° ET les méthodes retenues, pas seulement les refus).
- **Mesure A/B d'un interrupteur** : deux `StarAligner` au code inchangé, même
  référence, même ordre, même calibration ; seule la valeur testée diffère.
  Une mesure qui rejoue une seule branche ne dit rien du delta.

- **Une réussite de repli n'est pas une preuve d'alignement** : `phase` en
  translation seule a posé 11/50 puis 12/49 frames B **à l'envers**. Depuis ①,
  `_sans_phase` exige `avec_phase` ET `repli_phase` — ne jamais rendre une
  réussite de phase FINALE du chemin direct. Elle ne se scénarise pas : un banc
  teste le **chemin de décision** (espion), son coût sur une frame **douce**.
- **Un agrégat GLOBAL est AVEUGLE à un écart LOCAL** : 243 taches (~0,03 % des
  7,3 Mpx) font passer la couche B de +1,7 % à +80,7 % AUX POSITIONS sans bouger
  le poids moyen, le σ p50 ni les rejets. On lit **sur les positions** du défaut.
- **`poids` n'est JAMAIS 1,0** (médiane 0,918) : lire un rejet **contre le p5 du
  fond du même run**, avec témoin ; **comparer des tuiles** exige une ÉCHELLE
  COMMUNE (ramener chaque image à son propre fond).
- **Ne pas remettre `triangles_seuls`** : le refus Ha n'était pas un problème de
  méthode (0/5 contre 5/5, ~6 étoiles communes, `TRI_INLIERS_MIN(6)` non tenable).
- **Garde-fou `_invariants_triangles`** : `n_max` > ~30 explose la mémoire
  (13,7 Go de RSS constatés) ⇒ plafonner à 12/18/24/30.
- **`config.json` NE DIT PAS LA RÉALITÉ** (état à la dernière fermeture) : on MESURE.
- **Échecs PRÉEXISTANTS** : `_test_espace_jalon72` (géométrie d'écran),
  `_test_reset_empilement_jalon76` [4] (course `_stop()`, sensible à la charge CPU).
- **Tk / OpenCV / bancs `ui.App`** : jamais `grid` + `pack` dans le même conteneur ;
  `cv2.ocl.setUseOpenCL(False)` ; `ui.CONFIG = {}` et `ui.App._dire` patché
  (`_dire` = boîte MODALE, sinon blocage).
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`.

---

## Clôtures précédentes

- **19/10/2026** : J2 **validé en réel** (Q 0,80 ; poids 1,5 sur M33, par cible) et
  **J3 livré** — cinq modes de fusion du Ha + α, v2.89.0.
- **18/10/2026** : 141-B (v2.87.0) et J2 (v2.88.0) livrés ; ①/②/③, 136 et 137
  validés en réel.
