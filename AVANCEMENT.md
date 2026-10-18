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

Versions : `LRGBHa` = **v2.87.0** (①/②/③ validés en réel ; **136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface — prévenir
quand la composition change en session) · `master` publié = **v2.80.0** ·
Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 18/10/2026 — ① + 133, ② C, ③, 136 halo, 137 neutralisation STF, 141-B interface

### Ce qui est livré
- **v2.87.0 — jalon 141-B (interface)** : bandeau orange + UNE boîte quand la
  composition AFFICHÉE cesse de décrire la SESSION (`_compo_session`) ; le
  fichier, lui, reste correct (`AVACOMPO`). Banc neuf **141** (8 volets) vert.
  **VALIDÉE EN RÉEL par Alain (18/10)** : « ça fonctionne ».
- ①/②/③ (v2.82.2 `586f860`, v2.83.0 `4dd335b`, v2.84.0 `f35d349`) livrés et
  **validés en réel** ; **136** (halo coloré) et **137** (neutralisation après
  étirement en STF) livrés en v2.86.0 (`7e6cc88`). Détail :
  `avastack/__init__.py` (changelog) et `CLAUDE.md`.
- **Verdict ⑩** (rappel) : 11/50 puis 12/49 frames B empilées à l'envers par
  `phase` sur un champ à +177,07° — détail `CLAUDE.md`.

### Garde d'interface d'astrométrie (jalon 133) — LIVRÉE le 18/10
`worker._astro_indices_garde()` (appelée par `_astro_tour`, un seul point) compare
la SAISIE aux `OBJCTRA/OBJCTDEC` de la brute (seuil 0,25 × champ) ; au-delà elle
retient l'en-tête et REPOSE `suivi_astro.indice()`. Détail : `CLAUDE.md` §1300.

### Étape ② du plan ⑪ — choix C, LIVRÉ (v2.83.0) + mesure qui l'a décidé
- **Mesure (run réel LRGB+Ha, instrumenté PASSIVEMENT, 475 lues → 472 empilées,
  1 floue, 2 refus G)** : `triangles` porte **143/472 frames (30,3 %)** — B 16/51 ·
  G 33/61 · Ha 39/40 · L 31/240 · R 24/80. Résidu méd **0,083 px** (p90 0,675,
  max 1,385 ; 87/143 ≤ 0,10). Gain des centroïdes : **méd 0,002 px**, < 0,05 sur
  95/143 (66 %), **7 frames seulement** déplacées de > 1 px (pires 1,385 → 0,651).
  Par rôle : B 0,060→0,060 · G 0,082→0,084 · Ha 0,070→0,069 · **L 0,484→0,467** ·
  R 0,083→0,082. Contrôle positif 200 étoiles : 202 appariements, 0,0438 px à la
  vraie matrice, 1,4904 px pour une erreur connue de 1,5 px, 0,0104 px après
  raffinement. Détail : `CLAUDE.md` § « Étape ② du plan ⑪ ».
- **Livré** : seuil franchi seulement (`TRI_RAFFIN_SEUIL = 0,30` → 43/143
  frames du run), `pos=` pour ne PAS re-détecter les centroïdes, méthode
  `triangles+étoiles(n)`, `_last_t` final, `try/except` (une frame validée ne se
  perd jamais). Un raffinement ne refuse jamais ⇒ les **2 refus G** restent 2.
- **Mesures hors dépôt** : `_espion_155.py`, `_lance_155.py`, `_diag_155{a,b,c,d}*.py`,
  `_attendre_155.py` ; preuves `_155_centroides.jsonl`, `_trace155/155.jsonl`.

### Étape ③ du plan ⑪ — MESURÉE puis LIVRÉE (v2.84.0, jalon 135)
- **Mesure 1 (jeux SANS retournement)** : **109 frames** (SHO Rosette 53 · HOO
  NGC 7000 26 · SHO IC 443 30 ; 300 s, multi-nuits, ancre Ha à **250 étoiles**) →
  **0 refus AVANT / 0 APRÈS**, méthodes identiques frame par frame, phase jamais
  retenue. Contrôle positif 200 étoiles **PASS** (199 étoiles, 198 appariements,
  0,0551 px à la vraie matrice, 1,4977 px pour 1,5 px ; volet « phase seule » :
  AVANT accepte à 0,10 px, APRÈS refuse).
- **Mesure 2 — DÉCISIVE (jeu d'Alain `SV555\SH2-132\240.00`)** : Ha 55 · OIII 71 ·
  SII 80 à 240 s, 4-5 nuits, dark 240 s → **204 frames** (S2 79 · Ha 54 · O3 71),
  **0 refus** dans les deux branches, **31 retournements** (S2 24 · O3 7) tous
  retournés. La phase était le chemin **FINAL de 22 frames** :
  · **Ha 21 frames** : résidu médian **0,857 px** (max 1,071) — translation fausse
    de 1,1 à 2,3 px acceptée telle quelle ; sans phase (ORB étoffé) **0,065 px**.
    La couche Ha = canal VERT du SHO ⇒ flou réel dans l'image livrée ;
  · **O3 1 frame empilée À L'ENVERS** : phase angle 0 avec **0 appariement**
    contre |angle| **173,4°** et **4 435 px** d'écart ⇒ le défaut du ⑩, reproduit.
- **Livré** : `PHASE_EN_NARROWBAND = False` et `repli_phase_session()` qui lit
  L'UNE OU L'AUTRE constante (①/③, un seul endroit décide, les deux restent
  basculables). Cascade, verrou à deux conditions et aligneurs Ha de la VOIE A
  INCHANGÉS. Banc neuf **135** (7 volets) vert ; banc **132** mis à jour (son
  volet [1] datait d'avant ③) ; non-régression 13/15/21/116/117/129b/131/132/133/
  134 verte.
- **Outils hors dépôt** : `_mesure_156_phase_narrowband.py` (`--controle`,
  `--jeu`, `--tag`, `--max`), preuves `_156_*` et `_156b_*` (3 jeux) +
  `_156c_*` (Sh2-132). Détail durable : `CLAUDE.md` § « Étape ③ du plan ⑪ ».
- **DÉCISION D'ALAIN** : ③ retenu et livré.

### Halo d'étoile coloré (136) + neutralisation après étirement en STF (137) — v2.86.0
- **136 — halo** : cause en TROIS étages (détail : `CLAUDE.md` § « Halo d'étoile
  coloré ») : ① ciel inégal par canal (**R −14,0 % / B +25,6 %**, identique dans
  les quatre coins ⇒ **multiplicatif** ⇒ GAINS, pas offsets) ; ② le point noir
  COMMUN du STF passe au-dessus du ciel R ⇒ **97,34 % des pixels à 0 dans R**,
  ciel rendu **R 0,00 / G 0,07 / B 0,71** ; ③ la pente de la MTF (≈ 18) amplifie
  tout résidu de 1-3 % en 20-100 %.
- **136 — correctif** : `display.gains_avant_etirement` / `source_etirement` —
  gains par canal AVANT la courbe, **stats recalculées sur l'image neutralisée**,
  `GARDE_NEUTRE_STF = 0,35`. Ciel neutre ⇒ aucun gain ⇒ rendu **identique AU
  BIT**. Couronne à r = 14 : **R +4,9 % / B −6,8 %** (contre −100 % / −81 %).
- **137 — neutralisation après étirement EN STF** : elle était réservée à
  VeraLux ⇒ case **visible et inerte**. Portée : option cochée **ET moteur
  AUTOMATIQUE** (mode manuel exclu — point noir réglé à la main). Gains ANNONCÉS
  en STF (« FOND ✓ »). Scène décisive : écart du fond **0,130 → 0,045**.
- **LIMITE MESURÉE (les deux)** : en STF, le 136 égalise déjà le ciel avec le
  MÊME estimateur, donc le 137 ne corrige qu'un RÉSIDU ; la **teinte des COINS**
  (±15-20 %) est un **DÉGRADÉ** (1,3 % en linéaire, ×18 par la pente de la MTF) ⇒
  modèle de fond réel (GraXpert/ABE) ou estimateur par région : **décision
  d'Alain**. Gains bornés ±10 %, détail : `CLAUDE.md` § « Neutralisation APRÈS
  étirement ».
- Bancs neufs **136** (8 volets) et **137** (8 volets) verts ; non-régression
  5/39/41/62/68/69/75/79/121/123/124/125/127/128 verte. **Pas de release.**

### Interface 141-B — LIVRÉE (v2.87.0)
- **Défaut réel (141)** : session LRGB+Ha avec le menu passé en « RGB » PENDANT
  l'empilement ⇒ le fichier était JUSTE (`AVACOMPO = LRGB+Ha`) et l'écran ne
  disait RIEN de l'écart : la composition de la session ne se lisait plus.
- **Livré** : `_compo_session` (armée en fin de `_start`, effacée au reset, à la
  fermeture de source et à la déconnexion), `_compo_divergente()`,
  `_maj_compo_session()` (bandeau orange du panneau Composition),
  `_prevenir_compo_session()` (UNE boîte par couple session/affichée) ;
  `_maj_compo_info()` rafraîchit TOUJOURS le bandeau.
- **RIEN d'autre ne change** : composite, voie A du Ha, `AVACOMPO`, fiche.
- Banc neuf **141** (8 volets) vert ; non-régression 19 (UI + worker) / 61 /
  117d / 129 / 136 / 137 + **garde-fou** vert.
- **Bonus** : le garde-fou signalait un « APPARU » PRÉEXISTANT (`trace_roles`,
  importé au jalon 131 sans être figé) ⇒ figé dans `SURFACE_PUBLIQUE`.

### Validations en réel du 18/10 (détail dans `CLAUDE.md`)
- **② (v2.83.0)** : 472 frames (L 240 · R 79 · G 62 · B 51 · Ha 40), 2 refus,
  **0,00 %** de pixels à 0, canaux **R−V 0,079 px** et **B−V 0,130 px** ⇒ aucune
  régression. ⚠ Le « tel que vu » se mesure MAL (saturation, point noir par
  canal) : la géométrie se lit sur le **LINÉAIRE**.
- **③ (v2.84.0)** : 206 frames (S2 80 · Ha 55 · O3 71), **0 non alignée**,
  1 re-stack, ligne d'état `triangles` (Δ +8,9/+11,5 px, θ −0,19°), **aucune
  méthode « phase »** ; canal Ha net, aucun coin noir.
- **SPCC — LA FONCTION RESTE, l'enquête est CLOSE** (Alain, 18/10) : R ×0,7837 /
  G 1,0000 / B ×0,6299, pentes R/G 0,942 et B/G **1,626** sur 1013 étoiles ⇒
  l'alerte « hors [0,5 ; 1,5] » est **PAR CONSTRUCTION**, rendu jugé MEILLEUR
  qu'avec les gains Gaia : **ne pas rouvrir**.
- **Run LRGB (18/10)** : plus aucune tache bleue NI rouge ⇒ `phase` en broadband
  était la SEULE cause ; astrométrie réussie avec les bons indices (garde 133).


### État actuel
- **Code** : **v2.87.0** sur `LRGBHa`, commité et poussé (`09fd60f`) —
  **141-B VALIDÉE EN RÉEL par Alain** (18/10) ; ①/②/③ validés en réel ;
  136/137 livrés en v2.86.0.
- **À FAIRE PAR ALAIN** : juger à l'écran le halo (136) et la neutralisation STF
  (137) sur une session — 141-B est acquise, ne plus la retester.
- **Reste à faire** : **chantier LRGB+Ha J2 → J5** (plan figé ci-dessous) ;
  aucune release sans accord.
- **Combine** innocenté trois fois (140/142/143) : `_ratio_combine` intact.

### Fichiers modifiés dans cette phase (v2.87.0 / 141-B)
- `avastack/ui/app.py` : `_compo_session` + `_compo_alerte` (`__init__`),
  `_compo_divergente()`, `_maj_compo_session()`, `_prevenir_compo_session()`,
  `_armer_compo_session()` ; appels dans `_on_compo`, `_on_compo_roles`,
  `_maj_compo_info`, `_start`, `_reinit_etat_session`,
  `_refermer_source_fichiers`, `_deconnecter_camera`.
- `avastack/ui/panels/compo.py` : `lbl_compo_session` (bandeau orange).
- `bancs/_test_compo_session_jalon141.py` (NEUF, 8 volets) ;
  `bancs/_test_refactoring_garde_fou.py` (`trace_roles` figé — préexistant).
- `avastack/__init__.py` (**v2.87.0**), `CLAUDE.md`, `AVANCEMENT.md`.
- Rappel v2.86.0 (136 + 137) — `avastack/processing/display.py` : **136** `GARDE_NEUTRE_STF`,
  `SEUIL_NEUTRE_STF`, `gains_avant_etirement`, `source_etirement`,
  `gains_etirement`, branchés dans `_moteur_stf`, `_process_chaine` et
  `rendu_pleine_resolution` ; **137** `_neutraliser_fond` +
  `rendu_pleine_resolution` : neutralisation d'APRÈS étirement pour les DEUX
  moteurs AUTOMATIQUES (manuel exclu).
- `ui/panels/color.py` (aide de la case), `ui/app.py` (annonce « FOND ✓ » en STF),
  `ui/saver.py` (fiche : plus de verrou sur `stretch`), `bancs/_test_halo_couleur_
  jalon136.py` et `bancs/_test_neutralisation_stf_jalon137.py` (NEUFS, 8 volets
  chacun), `avastack/__init__.py` (**v2.86.0**), `CLAUDE.md`, `AVANCEMENT.md`.
- Commits de référence : v2.86.0 `7e6cc88` ; v2.84.0 `f35d349` ; v2.83.0
  `4dd335b` ; v2.82.2 `586f860`.

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
- **134c invalide** (brute dithérée) ; **135/136/138** annulées.

### Problèmes ouverts
- **Aucun** sur ①/②/③/136/137/141-B : livrés, mesurés, bancs verts. Le rendu est
  à JUGER À L'ÉCRAN par Alain (le 136 ne change le rendu que si le ciel est
  coloré ; le 137 corrige un résidu ; le 141-B ne touche pas au rendu).
- En attente d'une décision : **teinte des COINS ±15-20 %** (dégradé) — GraXpert/
  ABE ou estimateur par région, à trancher ; mesurée, non traitée.

### Prochaines étapes
1. **Chantier LRGB+Ha J2 → J5** (le gros reste fonctionnel, plan figé ci-dessous).
2. **Release GitHub v2.87.0** (4 paquets) — **sur accord explicite d'Alain**.
3. Reste, sans urgence : Store (v2.71.1 publiée), Linux machine vierge +
   `--cameras`, INDI après Linux, macOS jamais testé.

### Points d'attention
- **TROIS noms de composition** (141-B) : `stacker.composition`/`_compo_nom` (ce
  que la SOURCE empile, source de `AVACOMPO`), `_compo_session` (armée au
  « ▶ Démarrer »), `var_compo` (le MENU). Le bandeau ne compare que les deux
  derniers. **`"RGB+Ha"` est une sous-chaîne de `"LRGB+Ha"`** : jamais
  `startswith`/`in` pour identifier une composition écrite.
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
Arbre **v2.87.0** sur `LRGBHa`, propre et poussé (`09fd60f`) : ①/②/③ validés en
réel, **136** (halo coloré), **137** (neutralisation après étirement en STF) et
**141-B** (bandeau + une boîte quand la composition affichée cesse de décrire la
session) livrés — **141-B VALIDÉE EN RÉEL par Alain** —, bancs verts, aucune
release faite ; mode manuel hors neutralisation, teinte des coins ±15-20 % notée
sans action. Prochaine action unique : le **chantier LRGB+Ha J2 → J5** (fusion
« ajout au rouge » + poids + cadre) — aucune release sans accord.

---

## Chantier en cours — LRGB+Ha (jalons 129 → J5) — 141-B LIVRÉE, J2 à démarrer

Le rôle Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le combine L.

| Jalon | Contenu | État |
|---|---|---|
| J1 / 129 (v2.81.0) | compositions + 5 lignes UI + séparation ancre / `_narrowband_ha` | commité |
| 129b | voie A (référence **PAR RÔLE** + recalage de l'empilement) + `profondeur_min` + refus par rôle | COMMITÉ ; validé en réel le 16/10 (441 frames, 2 refus en R) |
| **130 (v2.82.0)** | combine LRGB borné [0 ; 5] + repli local + fiche + banc neuf | COMMITÉ + POUSSÉ (`ef0c35c`) |
| J2 → J5 | fusion « ajout au rouge » + poids + cadre ; 4 autres modes ; continuum ; ancre réelle + doc | à faire |

Plan figé (13 arbitrages du 15/10) : poids **1,0** (0–10) · α **0,5** · Q **0,80**
(0,10–2,00) · cadre « Fusion Ha » visible seulement si la compo contient Ha ·
continuum = **bandes passantes** (Ha 7 nm / RGB 100 nm), référence **R** ·
identifiants en français (`synthetise`).

---

## En attente / prochaine session (état au 18/10 — jalon 141-B livré, branche `LRGBHa`)

- **Prochaine action unique** : **chantier LRGB+Ha J2 → J5** — démarrer par J2
  (fusion « ajout au rouge » + poids 1,0 + α 0,5 + cadre).
- **DÉCIDÉ le 18/10 (Alain)** : neutralisation **hors mode manuel** (confirmé) ;
  boutons sans Siril (⬇ Gaia / Spectres / Base SPCC) **laissés en l'état**
  (secondaire) ; **teinte des COINS** **notée, sans action**. Seule attente :
  **release v2.87.0**, sur accord explicite.
- **141-B VALIDÉE EN RÉEL (Alain, 18/10)** : bandeau + boîte confirmés au
  changement de composition en session ; le fichier garde l'`AVACOMPO` de la
  session (comportement voulu). **Rien à retester.**

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

- **18/10/2026 (soir)** : 141-B — la composition AFFICHÉE ne peut plus mentir en
  silence sur celle que la session empile (bandeau + une boîte, v2.87.0).
- **18/10/2026 (matin)** : ⑧ + ⑨ + ⑩ — force du bleu réelle et LOCALE ; cause
  mesurée à l'ASTAP = frames B empilées **à l'envers** par le repli `phase`
  (11/50 et 12/49), pas la référence ni le rejet ⇒ correctif = étape ①.
