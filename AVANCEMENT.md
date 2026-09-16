# AVANCEMENT.md — mémoire de travail à court terme

(Ce fichier complète CLAUDE.md : il suit l'état courant du développement et
la tâche en cours. CLAUDE.md reste la mémoire de long terme, inchangée.)

---

## État actuel (base stable)

- **Version : AVAStack v2.3.1** (`avastack/__init__.py`,
  `AVASTACK_VERSION = "2.3.1"`), branche `master`. Jalon 5 validé par
  Alain (14/09/2026) ; **jalon 6 VALIDÉ PAR ALAIN le 15/09/2026** (test
  réel avec vraies brutes) et commité.
- **❌ DÉBRUITAGE : EXPÉRIENCE ABANDONNÉE par Alain le 15/09/2026.** Les
  jalons 7/8/9 (débruitage GraXpert IA, puis algorithmes locaux rapides
  ondelettes/NLM en manuel puis en live) sont ANNULÉS et leur code a été
  SORTI du dépôt : retour au dernier commit validé `18e1480` (v2.3.1).
  Tout le travail est conservé dans le stash `stash@{0}` (« Jalons 7/8/9
  DÉBRUITAGE LOCAL - ABANDONNÉ… » — récupérable par `git stash pop`).
  Trace complète des essais, des causes d'échec et des leçons : section
  « Expérience abandonnée » ci-dessous + Pièges de CLAUDE.md. Alain
  cherche de son côté d'autres méthodes (pistes possibles si le sujet
  revient : débruitage IA léger local épargnant les étoiles).
- **✅ JALON 6 VALIDÉ PAR ALAIN le 15/09/2026** (test réel, vraies
  brutes) : rejet des satellites (Winsorized), persistance config.json,
  boutons « - »/« + » des curseurs — tout est bon. Aucune tâche en
  suspens : la prochaine étape est à définir avec Alain.
- **Jalon 6 — rejet des satellites (demande d'Alain, 15/09/2026) : ✅
  CODÉ, commité puis VALIDÉ PAR ALAIN le 15/09/2026 (commit « Jalon 6 (1/3) »).** `avastack/processing/stacking.py` :
  `LiveStacker` a 2 méthodes de rejet — `method="kappa"` (comportement
  historique STRICTEMENT inchangé, régression testée bit-à-bit) et
  `method="winsorized"` : adaptation live du Winsorized Sigma Clipping
  de PixInsight — chaque frame est comparée à la MÉDIANE et au MAD
  (σ_robuste = 1,4826×MAD) d'une fenêtre glissante des dernières frames
  alignées (`window`, défaut 8 ; RAM ≈ window × frame en float32).
  REJEU DU WARMUP : quand la fenêtre se remplit pour la 1re fois (elle
  contient alors TOUTES les frames accumulées), l'accumulation est
  RECONSTRUITE avec les poids robustes — une trace passée pendant le
  warmup est effacée, pas seulement diluée (le kappa-sigma cumulé gonfle
  σ pour toujours via sumsq et masque ensuite les traces faibles aux
  mêmes pixels). `set_rejet(method=, window=)` change à chaud SANS
  perdre l'accumulation (seule la fenêtre est vidée). Traitement par
  bandes de lignes (`_CHUNK_PX`) pour borner les temporaires mémoire.
  `app.py` : cadre Empilement — combobox « Méthode de rejet »
  (« kappa-sigma (rapide) » / « Winsorized (satellites) ») + combobox
  « Fenêtre de référence (frames) » (4/6/8/12/16, grisée en mode kappa) ;
  appliqué à la création du stacker et à chaud (`_on_rejet`).
  Test : `_test_rejet_satellites_jalon6.py` (21 vérifications, headless)
  — scénario poison : résidu kappa ~10,0e-3 vs winsorized ~0,01e-3 ;
  étoiles/champ intacts ; RGB OK ; chunks OK ; jalons 1-5 relancés :
  TOUS PASSENT. (La persistance de ces réglages a été faite ensuite —
  cf. bullet suivant.)
- **Jalon 6 — persistance config.json (15/09/2026) : ✅ CODÉ, commité
  puis VALIDÉ PAR ALAIN le 15/09/2026.**
  `avastack/ui/app.py` : `_sauver_config_app` écrit désormais `kappa`,
  `rejet_methode`, `rejet_fenetre`, `moteur`, `vl_mode_res`, `vl_target`,
  `vl_logd`, `vl_profil`, `vl_graxpert` — booléen stocké EXPLICITEMENT
  (True comme False : une case décochée n'hérite pas d'un True ancien).
  `_restaurer_config` les relit au démarrage : kappa mappé sur les
  étiquettes Off/2σ-5σ ; méthode + fenêtre de rejet (état grisé
  synchronisé) ; réglages VeraLux restaurés AVANT le moteur (la bascule
  affiche le cadre avec les bonnes valeurs) ; moteur « VeraLux »
  SEULEMENT si le moteur tiers est disponible (aucun popup au démarrage) ;
  GX live SEULEMENT si la commande est utilisable (aucun popup) ;
  restauration TOLÉRANTE — kappa hors {2,3,4,5} → 3σ, fenêtre hors liste
  → 8, cible hors [0.10, 0.45] / logD hors [0, 7] / profil inconnu /
  mode inconnu → défauts (config corrompue = jamais de crash).
  Test `_test_config_jalon6.py` (19 vérifications, fenêtre Tkinter
  réelle ; `sauver_config` intercepté + `CONFIG` simulé : le VRAI
  config.json n'est jamais touché par les tests) : sauvegarde des 9
  clés, restauration complète (variables UI ET état du
  DisplayProcessor), réglages invalides → défauts sans crash.
  Jalons 1-5 relancés : TOUS PASSENT.
- **Jalon 6 — boutons « - »/« + » sur les curseurs (demande d'Alain,
  15/09/2026, avant son test réel) : ✅ CODÉ, commité (v2.3.1) puis
  VALIDÉ PAR ALAIN le 15/09/2026.**
  `_add_slider` (app.py) ajoute deux petits boutons autour de CHAQUE
  curseur (exposition, gain, black/white, gamma, saturation, fond visée,
  logD… — tous les sliders passent par cette fabrique) : clic = ±1 pas
  (res) recalé sur la grille du curseur (une valeur glissée à la main est
  réalignée) ; clic MAINTENU = répétition (400 ms puis 80 ms), annulée au
  relâchement ou en sortant du bouton ; clamp aux bornes frm/to ; le
  callback du curseur est appelé exactement comme lors d'un déplacement
  (aucun autre comportement changé). Test `_test_sliders_jalon6.py`
  (9 vérifications, fenêtre réelle). Jalons 1-5 + config relancés :
  TOUS PASSENT.
- **Stashes `stash@{0}`/`stash@{1}` DROPPÉS le 15/09/2026** (jalon 6
  validé ; la fonctionnalité VeraLux avait été réécrite proprement aux
  jalons 1-3, leur contenu n'était qu'une « inspiration » — rien à
  récupérer).
- **Jalon 5 — « 💾 Enregistrer tel que vu (étiré) » : ✅ VALIDÉ PAR ALAIN
  et commité (v2.2.7, 14/09/2026).** Détails du code :
  `display.py` : `rendu_pleine_resolution(img, reglages=None)` — rendu
  « tel que vu » d'une image linéaire PLEINE résolution, fonction PURE
  (aucun état partagé : pas de stats EMA, pas de solveur, jamais
  black/white/gamma) ; STF/manuel recalculé sur l'image complète, VeraLux
  avec le DERNIER logD résolu (rendu identique à l'écran, sans
  re-résolution ; replis target_bg si aucun logD connu / STF si moteur
  absent) ; gamma/saturation via `_gamma_saturation` et stats via
  `_calc_stats` (refactors neutres de `process()`/`_auto_params`).
  `app.py` : bouton « 💾 Enregistrer tel que vu (étiré)… » dans le cadre
  Sortie ; `_save_asseen()` capture (chemin, vue, réglages) côté UI ;
  `_worker` lance `_save_asseen_thread` (pattern `_run_external`,
  acquisition continue) : vue « pile » → stack pleine résolution →
  GraXpert live si activé (échec = sauvegarde abandonnée, message clair) ;
  vue « traitée » → `proc_full` (a déjà subi GraXpert/BXT) ; puis rendu +
  `save_image` ; résultat consommé par `_tick` (bouton grisé +
  messagebox). Libellés des boutons linéaires clarifiés (« (linéaire) »).
  Corrections sur retours d'Alain (test visuel) : (1) GraXpert live
  limité à la vue « empilement » (`_sync_vl_graxpert_vue`, synchro dans
  `_tick`/`_on_view`/`_on_vl_graxpert` + message explicite) — en vue
  « traitée » l'image a déjà subi le traitement externe, le relancer
  faisait un DEUXIÈME traitement ; (2) combobox « Profil capteur » dans
  le cadre VeraLux (avancé du jalon 6 demandé par Alain — 6 profils, fait
  partie de la clé → re-résolution au changement) ; (3) réglages STF
  regroupés dans `frm_stf` MASQUÉ en mode VeraLux (aucun effet dans ce
  mode), remis au retour STF ; gamma/saturation dans `frm_communs`
  (toujours visibles). Précision d'Alain : il avait utilisé « Enregistrer
  le résultat traité… » (linéaire, voulu) d'où sa question — libellés
  clarifiés, comportements inchangés.
  Tests : `_test_save_asseen_jalon5.py` (16 vérifications, headless),
  `_test_ui_jalon5.py` (15 vérifications, fenêtre Tkinter réelle) ;
  jalons 1-4 relancés : TOUS LES TESTS PASSENT.
- Arbre de travail **propre** au 15/09/2026 : jalon 6 validé et commité,
  rien en suspens ; les stashes de la tentative abandonnée ont été
  droppés (la fonctionnalité a été réécrite proprement aux jalons 1-3).
- **Dépôt distant créé (15/09/2026)** : `origin` =
  https://github.com/darkvad/AVAStack.git — `master` poussé et suivi
  (`git push` seul suffit désormais). Aucun fichier sensible suivi
  (pas de config.json, ni venv, ni build).
- Ce qui fonctionne (validé en réel) :
  - Pipeline complet : acquisition (sources simulées / dossier surveillé /
    OpenCV / ZWO ASI / QHYCCD / Player One / Touptek-Altair / SVBONY) →
    calibration dark/flat → alignement ORB + RANSAC (repli corrélation de
    phase) → empilement kappa-sigma → affichage temps réel → sauvegarde
    FITS/TIFF/PNG.
  - Étirement d'affichage actuel (`avastack/processing/display.py`,
    classe `DisplayProcessor`) : mode AUTO « STF façon PixInsight »
    (med − k·σ → p99.9, MTF calant le fond sur 0.25, stats lissées EMA
    anti-pompage) et mode MANUEL (black/white point), gamma et saturation
    communs. UI dans `avastack/ui/app.py` (case « Auto-stretch STF »).
  - Étirement VeraLux (moteur tiers, opt-in, validé en réel sur source
    simulée) : modes « fond cible (auto) » — le moteur résout le logD à
    CHAQUE nouvel empilement (thread dédié, dernier job gagnant, fallback
    STF) avec curseur « Luminosité du fond visée » — et « logD forcé »
    (curseur + bouton 🔒 de verrouillage du logD résolu).
  - Traitement externe optionnel sur INSTANTANÉ (GraXpert, BlurXTerminator)
    dans un thread séparé ; l'empilement accumulé reste linéaire et intact.
  - Sauvegarde « 💾 Enregistrer tel que vu (étiré)… » (jalon 5, v2.2.7) :
    vue courante rendue comme à l'écran en pleine résolution (chaîne
    complète : GraXpert live si activé → étirement STF/manuel ou VeraLux
    avec le dernier logD résolu → gamma/saturation) ; les deux autres
    boutons d'enregistrement restent LINÉAIRES (voulu).
  - Installateur Windows Inno Setup (v2.1.0).

## ⚠️ Diagnostic en cours : retrait de gradient GraXpert — bords clairs + signal affaibli (signalement d'Alain, 15/09/2026)

Copies d'écran reçues (M33) : (1) sans retrait de gradient = fond uniforme
jusqu'aux bords ; (2) avec retrait (GraXpert live VeraLux ET traitement
externe manuel — même commande) = **bande claire périphérique régulière sur
tout le pourtour** (effet « coussin ») + rendu différent des bras spiraux.
Alain : « me détruit du signal et me crée un gradient sur les bords ».

Cause identifiée (analyse du 15/09/2026, comportement intrinsèque de
l'outil sur CE type d'image, pas un bug du code AVAStack) :
- La commande par défaut (`_GX_OPTIONS`, `avastack/external/detection.py`)
  est `-cmd background-extraction -correction Subtraction -smoothing 0.5`.
- L'image fournie est la pile LINÉAIRE déjà calibrée (flat appliqué) :
  son fond est DÉJÀ plat. GraXpert ajuste alors un modèle de fond à du
  bruit ; le modèle ondule et retombe vers les bords (extrapolation, les
  points d'échantillonnage ne touchent pas les bords).
- En **Subtraction**, on retire ce modèle : beaucoup au centre, presque
  rien en périphérie → le fond brut (skyglow + offset) y reste → BANDE
  CLAIRE. Le gradient de bord est CRÉÉ par la correction, pas révélé.
- Le modèle lisse peut aussi absorber l'enveloppe diffuse de la galaxie :
  la soustraction l'ampute = « signal détruit ». La différence de rendu
  des spirales entre les 2 copies d'écran est en partie une ILLUSION de
  renormalisation (l'étirement auto se recalibre sur le fond abaissé →
  contraste ET bruit remontent), en partie une vraie perte de lueur
  faible si le modèle a capté la galaxie.

Essais à faire par Alain (commande ÉDITABLE dans le champ GraXpert, aucun
code à changer) — dans l'ordre :
1. `-smoothing 0.8` (modèle rigide → quasi-plan → peu de soustraction) ;
2. `-correction Division` au lieu de `Subtraction` (multiplicatif,
   préserve mieux les niveaux faibles) ;
3. les deux combinés ; comparer les mêmes zones (bords + bras externes).
À noter : sur une pile déjà plate (flat correct), le retrait de gradient
n'a presque rien d'utile à corriger — le rapport coût/artefact est défavor.
Constat Bonus (Alain) : « le débruitage non-local means semble fonctionner
presque correctement sur la version SANS gradient » — le code NLM est dans
le stash `stash@{0}` (jalons 8/9), PAS dans l'arbre courant : clarifier
comment ce test a été fait avant tout développement.


## ❌ Expérience abandonnée : débruitage (jalons 7, 8, 9 — 15/09/2026)

Demande d'Alain : le débruitage GraXpert IA (jalon 7) fonctionne mais
« très long et peu efficace » → essai d'algorithmes classiques locaux
rapides (numpy/OpenCV, aucune dépendance nouvelle) : jalon 8 en
traitement externe manuel, jalon 9 en LIVE dans le thread solveur
VeraLux. Après 3 itérations et 3 tests réels sur ses vraies images,
Alain a ABANDONNÉ : « soit ça fait le léopard, soit je baisse la force
et ça laisse du bruit autour des étoiles, ce qui le rend d'autant plus
visible. Je vais chercher de mon côté quelles autres méthodes existent. »

Ce qui avait été codé puis SORTI du dépôt (conservé dans `stash@{0}`) :
- **jalon 7** : débruitage GraXpert CLI dans les outils externes manuels
  (`-cmd denoising` + `-strength`, PAS `-smoothing`) — fonctionnel mais
  plusieurs MINUTES par image (IA) ;
- **jalon 8** : module `avastack/processing/denoise.py` — « ondelettes »
  (starlet à trous B3-spline 5 niveaux, seuillage k-sigma par couche,
  bruit estimé par MAD) et « nlm » (Non-local means OpenCV 16 bits,
  h auto-adapté au bruit réel par MAD) ; choix radio « 2. Débruitage »
  dans le traitement externe manuel, force commune ; étape locale
  exécutée EN MÉMOIRE entre les étapes subprocess ;
- **jalon 9** : le même débruitage offert EN LIVE (case dans le cadre
  VeraLux) — chaîne du thread solveur : stack → GraXpert live →
  débruitage local → étirement, résultat en cache par (empreinte image,
  méthode, force), persistance, sauvegarde « tel que vu » cohérente.
  Perf OK (~0,2-0,4 s à taille aperçu) — le problème n'était PAS la
  vitesse mais la QUALITÉ VISUELLE.

Le problème non résolu (constats réels d'Alain sur vraies images) :
- le FOND « LÉOPARD » (moutonnement en plaques) apparaît dès que la
  force est assez élevée pour être utile ;
- en baissant la force, le léopard disparaît MAIS il reste du bruit fin
  AUTOUR DES ÉTOILES — et le contraste rend le lissage du fond encore
  plus visible. Le compromis est structurel pour un débruiteur « pixel
  classique » appliqué à un empilement live peu intégré.

Corrections tentées, insuffisantes (v2.6.1 puis v2.6.2) :
1. seuillage DUR → GARROTE non-négative (transition continue, pas
   d'îlots de coefficients survécus) ;
2. ondelettes : ne seuiller QUE les niveaux fins (5 → 3 → 2 niveaux :
   les couches grossières contiennent de la STRUCTURE, les seuiller
   moutonne) ; k relevé jusqu'à 4σ ;
3. NLM : h 3σ → 0.8σ, fenêtre de recherche 21 → 15 px, gabarit 7 → 5 px,
   une passe forte → deux passes faibles (la fenêtre de recherche FIXE
   l'échelle des plaques ; le lissage itératif homogénéise).
Chaque correction a réduit le défaut sans l'éliminer.

LEÇONS retenues (reprises dans CLAUDE.md → Pièges) :
- sur du bruit PUR synthétique, les réglages agressifs paraissent
  MEILLEURS (les grandes échelles y sont du bruit) — seul un test sur
  image RÉELLE révèle le défaut ; valider réel dès la première passe ;
- pas de réglage « gratuit » : force utile = artefacts, force sûre =
  bruit résiduel autour des étoiles.
Si le sujet est reposé un jour : viser des méthodes qui épargnent les
étoiles par conception (IA légère locale, type Noise2* entraîné astro,
ou débruitage au moment de l'étirement) plutôt que re-raffiner le
pixel-classique. Pièges techniques consignés au passage : OpenCV 5
(fastNlMeansDenoising 16 bits = NORM_L1 + h tableau en 2e positionnel)
et GraXpert CLI (-strength pour le débruitage, -smoothing = gradient).

## Le code VeraLux : où il en est

- `veralux_core_headless.py` (racine du dépôt) = moteur d'étirement
  hyperbolique **tiers** (extrait de VeraLux_HyperMetric_Stretch.py v1.5.2,
  Riccardo Paterniti, GPL-3.0-or-later), copié tel quel, déjà suivi dans git.
  Point d'entrée : `solve_and_stretch(img, ...) → (image étirée, log_d,
  diagnostics)`, profils capteur `SENSOR_PROFILES` (Rec.709 par défaut,
  IMX585/662/533/571-2600/294). N'importe numpy uniquement → **aucune
  dépendance pip nouvelle**.
- Ce fichier est **câblé depuis les jalons 1-3** : adaptateur
  `avastack/processing/veralux.py` (jalon 1, import robuste, clip [0,1]),
  affichage dans `DisplayProcessor` + UI (jalons 2-3). La chaîne complète
  est câblée et VALIDÉE (jalons 1-6) : fond cible + verrouillage logD,
  GraXpert live, sauvegarde « tel que vu », rejet des satellites
  (Winsorized), persistance config.json, boutons fins des curseurs.
- La tentative précédente (autre outil) était conservée dans les stashes
  `stash@{0}`/`stash@{1}` — **droppés le 15/09/2026** après validation du
  jalon 6 : la fonctionnalité avait été réécrite proprement (adaptateur
  `avastack/processing/veralux.py` du jalon 1) et le contenu des stashes,
  écrit « aux incohérences » par l'outil précédent, n'a jamais été
  réemployé (simple inspiration).


## Historique : tâche « auto-stretch VeraLux » — PLAN VALIDÉ par Alain le 14/09/2026, TERMINÉE le 15/09/2026

Procéder **PAR JALONS** (leçon de la 1re tentative « grosse modification »
perdue) : un jalon = `ast.parse` après chaque édition, lancement de l'appli,
test par Alain quand l'affichage est touché, **commit avant de passer au
suivant**. Bump `AVASTACK_VERSION` + changelog à chaque jalon touchant le
code. (Les stashes ont été droppés le 15/09/2026, après validation du
jalon 6.)

- **Jalon 0** — Mémoire : ce fichier mis à jour (plan + jalons), commit
  AVANCEMENT.md seul. ✅ 14/09/2026.
- **Jalon 1** — Adaptateur `avastack/processing/veralux.py` (réécrit
  proprement, stashes = inspiration seulement) : import robuste du moteur
  tiers (racine déduite de `__file__` via `parents[2]`, PAS du répertoire
  courant — installateur), clip défensif [0,1] en entrée (piège
  `normalize_input` : float avec max > 1.1 → divisé par 65535 !), mono
  (H,W) et RGB (H,W,3)↔(C,H,W), API `etirer(...)` → (image étirée, log_d,
  diagnostics). Test headless mono PUIS RGB avant tout câblage. L'appli
  reste inchangée à ce stade. ✅ 14/09/2026 : test headless OK (mono, RGB,
  non-mutation, clip, déterminisme logD, petite image, repli profil).
  **Chronos mesurés à 1600×1000** : target_bg ≈ 264 ms, logD forcé
  ≈ 196 ms (et 124 ms à 800×1200 en logD) → pour les jalons 2-3 : résultat
  VeraLux CACHÉ par image (recalcul à chaque nouvel empilement, jamais à
  chaque tick UI ~30 ms) et slider logD débouncé (~150 ms).
- **Jalon 2** — Affichage VeraLux, mode logD forcé : mode opt-in dans
  `DisplayProcessor` (calcul direct dans `process()` : pure fonction,
  ~20-50 ms sur l'aperçu), UI « Auto-stretch : STF / VeraLux » + slider
  logD forcé (0-7). VeraLux ne touche JAMAIS à black/white/gamma ;
  gamma/saturation communs appliqués après, comme pour le STF.
  ✅ 14/09/2026 (code + tests headless OK) : calcul en thread solveur dédié
  avec cache par image + clé de réglages (même en logD forcé, ~196 ms à
  1600×1000 → trop pour le thread UI), fallback STF au 1er calcul, jobs
  remplacés (jamais empilés), flag `vl_new` lu par `_tick` (aucun appel Tk
  hors thread UI). UI : combobox « Moteur d'étirement » + cadre VeraLux
  (slider logD, label logD/fond/erreur).
  ✅ **VALIDÉ PAR ALAIN le 14/09/2026 (test visuel, source simulée)** :
  « tout est bon » — UI non figée, slider logD réactif, STF par défaut
  inchangé, black/white/gamma intacts. Commité (v2.2.4).
- **Jalon 3** — Mode target_bg + solveur par frame : thread dédié
  déclenché à CHAQUE nouvel empilement (frames espacées de ≥1 s, souvent
  bien plus → le rythme des frames EST le cooldown ; résoudre toujours le
  DERNIER empilement, jamais une file d'attente), fallback STF le temps du
  1er calcul, bouton « 🔒 Verrouiller le logD résolu » (capte la dernière
  valeur résolue → calcul direct déterministe et réactif).
  🔧 14/09/2026 (code + tests headless OK) :
  `display.py` : `vl_mode_res = MODE_TARGET_BG` par défaut, `notify_new_stack()`
  (drapeau `_vl_force` consommé SEULEMENT quand un job est réellement soumis ;
  l'objet image nouveau à chaque tick UI ne déclenche plus rien — le worker
  pousse ~20 im/s même sans nouvelle frame), `reset()` vide aussi le cache
  VeraLux. `app.py` : combobox « Résolution du logD : fond cible (auto) /
  logD forcé » (défaut = fond cible) + curseur « Luminosité du fond visée
  (VeraLux) » 0.10-0.45 (recalcul immédiat : vl_target_bg fait partie de la
  clé), `_tick` surveille `st["frames"]` →
  `notify_new_stack()`, bouton 🔒 (capte `vl_log_d_resolu` via le curseur →
  mode logD forcé ; 🔓 = retour fond cible). `_test_veralux_jalon3.py` :
  18 vérifications OK (fond calé 0.20, aucun recalcul entre deux frames,
  dernier empilement gagnant sans file, verrouillage = déterminisme
  écart max 0.0000, reset, black/white intacts). **`_test_veralux_jalon2.py`
  adapté** : il doit forcer `vl_mode_res = MODE_LOG_D` (le comportement
  « logD forcé » n'est plus le défaut).
  ✅ **VALIDÉ PAR ALAIN le 14/09/2026 (test visuel, source simulée)** :
  curseur « Luminosité du fond visée » réactif (ajouté après son premier
  retour — il manquait), UI jamais figée, verrouillage logD opérationnel.
  Commité (v2.2.5).
- **Jalon 4** — GraXpert live (opt-in) : case « GraXpert live (avant
  étirement) » ; chaîne stack → GraXpert → VeraLux dans le thread solveur
  (ordre photométrique correct). BXT reste manuel (bouton ⚡, inchangé).
  ✅ **VALIDÉ PAR ALAIN le 14/09/2026 (test visuel, source simulée RGB)**
  puis commité (v2.2.6). Détails du code (14/09/2026) :
  `avastack/external/live.py` : `appliquer(img, cmd, timeout=300)` →
  (image traitée, ""), (image, erreur) en cas d'échec ; FITS temporaire →
  commande configurée ({input}/{output}/{outbase}, MÊME commande que le
  traitement manuel) → `find_output` + `load_image` + `auto_unflip` +
  contrôle des dimensions ; `commande_valide()`, `cle_image()` (SHA-1).
  **Exécution robuste** (`_run_bloquant_survivable`) : sorties dans des
  FICHIERS (pas de tubes) + Popen + `taskkill /F /T` au délai — sinon la
  boîte de dialogue modale cx_Freeze d'un crash GraXpert garde les tubes
  ouverts et BLOQUE le thread solveur même après le timeout (constaté en
  réel). **FITS RGB canaux-en-tête** (`_ecrire_entree`/`_lire_sortie`) :
  cf. piège ci-dessous (crash AI sur RGB corrigé).
  `display.py` : `vl_graxpert` / `vl_graxpert_cmd` (captés côté UI dans le
  job, jamais lus depuis le thread) ; le worker enchaîne GraXpert PUIS
  `_veralux.etirer` ; cache GraXpert indexé par (CONTENU image, COMMANDE) —
  bouger un curseur VeraLux ne relance PAS GraXpert, mais changer la
  commande l'invalide (bug évité au test) ; erreur → vl_error
  « GraXpert live : … » + étirement de l'image BRUTE en repli ; `reset()`
  vide le cache. `_vl_params()` intègre les réglages GraXpert.
  `app.py` : case dans le cadre VeraLux (refus + avertissement si commande
  incomplète), synchro de la commande éditée dans `_tick`, label préfixé
  « GX ✓ · ». Version 2.2.6 + changelog. `_test_graxpert_live_jalon4.py` +
  `_gx_factice.py` : 24 vérifications OK (défaut inactif, chaîne, cache,
  erreur non fatale, désactivation, reset, round-trip FITS, black/white
  intacts). Jalons 1-3 relancés : TOUS LES TESTS PASSENT.
  ✅ Test RÉEL (`_diag_gx_reel.py`, GraXpert 3.1.0rc2 installé) :
  mono 960×640 (3,4 s), RGB 960×640 (3,4 s), RGB 1600×1000 (3,6 s) —
  tous OK, interpolation AI, aucune erreur. Nettoyage des fichiers de
  diagnostic fait (gardé : `_diag_gx_reel.py` uniquement).
  ⚠️ Limites connues : GraXpert CLI recharge son modèle IA à CHAQUE
  appel → plusieurs secondes par frame possible ; le solveur « dernier
  job gagnant » absorbe le retard, l'UI reste fluide (STF d'attente).
  GraXpert clamp aussi sa sortie RGB à [0, 1] (étoiles > 1 légèrement
  écrêtées dans l'aperçu live — sans conséquence pour l'affichage).
- **Jalon 5** — « 💾 Enregistrer tel que vu (étiré) » : vue « empilement » →
  stack linéaire pleine résolution + GraXpert live + étirement PLEINE
  résolution (jamais l'aperçu 1600 px) ; vue « traitée » → inclut le
  résultat BXT (décision Alain). Gamma/saturation tels qu'affichés inclus.
  Le bouton d'enregistrement linéaire actuel reste inchangé.
  ✅ **VALIDÉ PAR ALAIN le 14/09/2026 puis commité (v2.2.7)** — cf.
  détails dans « État actuel » ci-dessus. Corrections intégrées : GX live
  limité à la vue « empilement », combobox profil capteur (avancé du
  jalon 6), réglages STF masqués en mode VeraLux, libellés « (linéaire) »
  clarifiés.
- **Jalon 6** — Finitions : ~~persistance config.json~~ (✅ CODÉ le
  15/09/2026, cf. « État actuel »), ~~combobox profil capteur~~ (✅ FAIT au
  jalon 5), ~~curseurs STF grisés en mode VeraLux~~ (✅ FAIT au jalon 5 :
  masqués, décision d'Alain), ~~rejet des satellites~~ (✅ CODÉ le
  15/09/2026, ajouté au jalon sur demande d'Alain), ~~changelog final,
  version 2.3.0~~ (✅ FAIT le 15/09/2026), ~~boutons « - »/« + » des
  curseurs~~ (✅ CODÉ le 15/09/2026, demande d'Alain).
  ✅ **VALIDÉ PAR ALAIN le 15/09/2026 (test réel, vraies brutes)** —
  jalon clos, stashes droppés, aucune tâche en suspens.

### Décisions d'Alain (14/09/2026)

- Étirement recalculé à CHAQUE frame (pas de cooldown figé 2-3 s) : les
  frames arrivent toutes les ≥1 s, souvent bien plus — quitte à attendre
  l'empilement de la suivante.
- GraXpert AVANT l'étirement, à chaque frame (« c'est bien mieux ») ;
  BXT, plus long, reste en manuel sur clic.
- Sauvegarde étirée = « save as seen » : TOUTE la chaîne (calibration →
  alignement → empilement → GraXpert si activé → BXT si vue « traitée » →
  VeraLux pleine résolution → gamma/saturation).
- logD verrouillable après résolution pour gagner en réactivité.
- Travail par jalons avec commit à chaque jalon.

## Décisions prises (issues de CLAUDE.md — s'imposent à cette tâche)

- Multiplateforme Windows / Linux / macOS : aucun chemin OS en dur sans
  repli ; venv de dev `C:\Astro\astrolivestack\venv` (dossier non renommé).
- `veralux_core_headless.py` est du code TIERS GPL-3.0 : jamais reproduit ni
  modifié ; toute adaptation se fait dans un fichier séparé du projet.
- Fonctionnalité optionnelle à risque → **opt-in** (désactivée par défaut).
- Ne jamais casser un défaut existant sans y être invité.
- Toute modification : bump `AVASTACK_VERSION` + changelog expliquant le
  constat réel ; vérifier la syntaxe par `ast.parse` après chaque édition.
- Nouvelle dépendance pip : signaler explicitement à Alain + requirements.txt
  (ici : aucune nécessaire, le moteur n'importe que numpy).
- Commentaires/docstrings en français ; CLAUDE.md jamais modifié par l'agent
  sans proposition + confirmation explicite d'Alain.

## Pièges connus

Repris de CLAUDE.md (tous applicables à cette tâche) :

- **OpenCV 5 refuse de débayeriser une image flottante** (float32/64) :
  tout float doit être traité comme mono sans débayerisation ; la devinette
  Bayer opère sur l'image ENTIÈRE d'origine, jamais sur une copie flottante.
- **`python3` ≠ `python`** sur la machine d'Alain (Store vs venv) : un
  symptôme anormal peut venir de l'interpréteur, pas du code — vérifier
  `sys.executable` avant de soupçonner le code.
- **Une fonction opérant sur des images peut supposer un nombre de canaux
  fixe** : le moteur VeraLux travaille en (canaux, H, W), AVAStack en
  (H, W, canaux) — bug réel du genre = image noire sans aucune erreur.
- **Une formule « additive » reste fausse si une entrée peut être négative** :
  données recalées/interpolées → clip explicite avant étirement.
- Rejouer un test sur la version d'avant la modification avant d'en conclure
  la cause ; isoler UNE variable à la fois en cas de multiples symptômes.

Constats propres à cette tâche (exploration du 14/09/2026) :

- **`.clinerules` créé à la racine (14/09/2026)** : il impose la lecture de
  CLAUDE.md + AVANCEMENT.md à chaque nouvelle session (mécanisme de règles
  automatiques de Cline). (NB 15/09/2026 : le `.clinerules` non suivi de
  l'outil précédent est parti avec stash@{0}, droppé — plus aucun risque
  de conflit.)

- **Deux stashes coexistaient** (`stash@{0}` dernière tentative avec
  `veralux.py` non suivi, `stash@{1}` essai antérieur) : **droppés le
  15/09/2026 après validation du jalon 6** (fonctionnalité réécrite
  proprement, rien à récupérer). Leçon conservée : les fichiers non
  suivis d'un stash vivent dans son **3e parent** (`stash@{0}^3`), pas dans
  le diff principal.
- **« Bug latent ligne ~276 » du fichier tiers : FAUX POSITIF (fichier relu
  intégralement le 14/09/2026)** — la ligne est
  `img_data[i] = VeraLuxCore.apply_mtf(img_data[i], m)`, complète et
  correcte ; le fichier tiers semble intact. Confirmation par test réel
  mono puis RGB (jalon 1) avant de s'y fier définitivement.
- **Coût CPU de `solve_and_stretch`** : résolution itérative de log_D,
  histogrammes 65 536 cases, sous-échantillonnage ~100k px — hors de
  proportion avec le `process()` STF actuel (~quelques opérations
  vectorielles). **Constat réel de la 1re tentative** : le moteur était
  recalculé à CHAQUE rafraîchissement d'écran (~toutes les 30 ms) DANS le
  thread de l'interface dès la case VeraLux cochée → appli complètement
  figée (plus d'empilement visible, boutons morts, impossible de charger un
  dark). Le calcul DOIT partir dans un thread séparé (ou un mécanisme
  cooldown/résolution périodique) — c'est la condition n°1 du câblage.
- **Corruption des réglages d'affichage (constat réel de la 1re tentative)** :
  le code de bascule VeraLux de l'époque modifiait `black`/`white`/`gamma`
  du `DisplayProcessor` pour « tricher », puis ne les **restaurait jamais** —
  après un seul rendu, les réglages manuels d'Alain étaient écrasés
  définitivement. Règle : VeraLux ne touche JAMAIS aux paramètres
  black/white/gamma de l'afficheur ; il produit sa propre image étirée et
  les réglages communs (gamma/saturation) s'appliquent ensuite comme pour
  le STF, sans réécriture des variables utilisateur.
- **État global côté moteur** : `VeraLuxCore._last_linear_expansion_diag`
  est un attribut de CLASSE (état partagé mutable) — en tenir compte si le
  calcul part dans un thread séparé (lecture seule ou verrou).
- **Anti-pompage à repenser** : le STF actuel lisse ses stats (EMA) entre
  frames ; VeraLux recalcule tout à chaque appel → prévoir le même type de
  lissage ou une résolution périodique, sinon l'image « pompe ».
- **Import du tiers hors package** : `veralux_core_headless.py` est à la
  racine, hors `avastack/` — l'adaptateur doit rendre ce chemin importable
  (le stash@{0} insérait la racine dans `sys.path`) ; attention au
  lancement via installateur/exe où la racine n'est pas le répertoire
  courant.
- **Piège `normalize_input` du moteur** : pour une image flottante, si
  `max > 1.1` le moteur divise par 65 535 (heuristique de détection
  d'entiers « oubliés de normaliser »). Un empilement avec quelques
  pixels > 1.1 (flat mal appliqué, hot pixel) serait écrasé. L'adaptateur
  clippe donc l'entrée à [0, 1] avant tout appel.
- **PIÈGE convention d'axes FITS couleur (GraXpert 3.1.0rc2, diagnostiqué
  le 14/09/2026)** : le lecteur FITS de GraXpert suppose les canaux sur
  NAXIS3 (astropy data = (C, H, W)), alors que `save_image` écrit la
  convention astropy standard (data (H, W, C) → NAXIS1=3). Un aperçu RGB
  mal lu est déformé : crash cv2.resize « !dsize.empty() » (boîte de
  dialogue modale cx_Freeze) avec l'interpolation AI, ou sortie dégénérée
  (W, 3) avec RBF. Le mono 2D n'est pas concerné (d'où des succès
  manuels sporadiques). Parade dans `avastack/external/live.py` : écrire
  l'entrée RGB canaux-en-tête (`_ecrire_entree`, transpose (2,0,1)) et
  retransposer la sortie (3, H, W) → (H, W, 3) (`_lire_sortie`). Avec ça,
  l'AI fonctionne sur RGB (test réel mono/RGB/RGB 1600×1000 OK en ~3,5 s).
  NB : l'entrée TIFF plante aussi chez GraXpert (imagecodecs LZW absent
  de leur build) → ne PAS passer de TIFF à GraXpert.
- **PIÈGE subprocess + boîte de dialogue cx_Freeze (14/09/2026)** : quand
  GraXpert plante, cx_Freeze affiche une boîte MODALE qui bloque le
  processus jusqu'au clic ; avec subprocess.run(capture_output=True) les
  tubes restent ouverts et communicate() ne revient JAMAIS, même après le
  timeout (le kill ne touche que cmd.exe). Parade : sorties dans des
  fichiers + Popen + `taskkill /F /T /PID` au délai (tue l'arborescence,
  la dialogue disparaît, le thread solveur repart). Cf.
  `_run_bloquant_survivable` dans `avastack/external/live.py`.

