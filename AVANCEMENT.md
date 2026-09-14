# AVANCEMENT.md — mémoire de travail à court terme

(Ce fichier complète CLAUDE.md : il suit l'état courant du développement et
la tâche en cours. CLAUDE.md reste la mémoire de long terme, inchangée.)

---

## État actuel (base stable)

- **Version stable : AVAStack v2.2.6** (`avastack/__init__.py`,
  `AVASTACK_VERSION = "2.2.6"`), branche `master`. Jalon 4 (GraXpert
  live) validé par Alain (test visuel) et committé le 14/09/2026.
- **Prochaine session : commencer au JALON 5** — « 💾 Enregistrer tel
  que vu (étiré) », cf. plan détaillé ci-dessous. Les stashes
  `stash@{0}`/`stash@{1}` sont toujours en place : ne rien dropper tant
  que la fonctionnalité n'est pas entièrement validée (jalons 5-6
  restants).
- Arbre de travail **propre** au 14/09/2026 (fin de session) : jalon 4
  commité, rien en suspens ; la tentative abandonnée d'intégration VeraLux
  reste de côté dans `git stash -u` (plus dans les sources).
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
  - Installateur Windows Inno Setup (v2.1.0).

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
  affichage dans `DisplayProcessor` + UI (jalons 2-3). Tâche en cours :
  **jalon 4 — GraXpert live** (dans le même thread solveur, AVANT
  l'étirement).
- La tentative précédente (autre outil) est dans les stashes :
  - `stash@{0}` « WIP on master: 5f6895d » : modifications de
    `avastack/ui/app.py`, `avastack/processing/display.py`,
    `avastack/__init__.py` + fichier **non suivi**
    `avastack/processing/veralux.py` (233 lignes, adaptateur d'import du
    moteur tiers, mapping nom de caméra → profil capteur). Récupérable via
    `git show 'stash@{0}^3:avastack/processing/veralux.py'` (fichiers non
    suivis = 3e parent du stash) et `git stash show -p 'stash@{0}'`.
  - `stash@{1}` « WIP veralux - a reprendre proprement » : essai antérieur,
    `app.py` uniquement (45 insertions).
  - **Ne rien dropper tant que la fonctionnalité n'est pas validée.**
  - Le contenu des stashes a été écrit par l'outil précédent « aux
    incohérences » : à considérer comme une **inspiration, pas comme du
    code de confiance** — tout rélire et revalider avant réemploi.


## À faire ensuite (tâche : auto-stretch VeraLux — PLAN VALIDÉ par Alain le 14/09/2026)

Procéder **PAR JALONS** (leçon de la 1re tentative « grosse modification »
perdue) : un jalon = `ast.parse` après chaque édition, lancement de l'appli,
test par Alain quand l'affichage est touché, **commit avant de passer au
suivant**. Bump `AVASTACK_VERSION` + changelog à chaque jalon touchant le
code. Les stashes ne sont pas touchés tant que la fonctionnalité n'est pas
validée.

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
- **Jalon 6** — Finitions : persistance config.json de tous les réglages
  VeraLux, combobox profil capteur, curseurs STF grisés en mode VeraLux,
  changelog final, version 2.3.0, test réel complet par Alain (vraies
  brutes) avant commit final.

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
  automatiques de Cline). ATTENTION : le stash@{0} contient aussi un
  `.clinerules` non suivi (1 ligne, de l'outil précédent) — un futur
  `git stash pop/apply` échouera ou conflituera sur ce fichier ; au moment
  de récupérer le stash, restaurer les fichiers voulus un par un
  (`git checkout 'stash@{0}^3' -- avastack/processing/veralux.py` etc.)
  plutôt qu'un pop global.

- **Deux stashes coexistent** (`stash@{0}` dernière tentative avec
  `veralux.py` non suivi, `stash@{1}` essai antérieur) : ne pas confondre,
  ne rien dropper avant validation de la fonctionnalité. Les fichiers non
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

