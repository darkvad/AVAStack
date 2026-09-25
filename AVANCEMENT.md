# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---


- **Version stable de référence : AVAStack v2.36.1** (`avastack/__init__.py`),
  branche `master` — **CORRECTIFS « FOND BLEU » (constats d'Alain, 25/09/2026 :
  « le fichier tel que vu en png : PROBLEME, vachement bleu et ca me fait ca
  depuis le début » + « il reste quand même pas mal de bruit bleu »)** :
  - ① **LE PNG/TIFF EXPORTÉ AVAIT R ET B PERMUTÉS** (bug VIEUX, silencieux) :
    `save_image` donnait l'image RGB de l'appli à `cv2.imencode`, qui attend du
    BGR (`load_image` convertit à la lecture) → l'aller-retour interne restait
    cohérent, donc invisible, mais TOUS les fichiers exportés (visionneuses,
    Siril, GraXpert) montraient les canaux échangés. Mesuré sur son PNG :
    PNG_R ≈ FITS_B, corrélation 1,0000. → conversion RGB→BGR avant `imencode` ;
    les bancs relisent désormais les fichiers écrits avec un lecteur INDÉPENDANT.
  - ② **L'ÉTIREMENT VERALUX BLEUISSAIT LE FOND** : le fichier LINÉAIRE a un fond
    neutre (R/G 0,9991 · B/G 0,9991), mais VeraLux soustrait une **ancre**
    (0,0313) puis étire en log → pour le fond ne compte que le **résidu** (canal
    − ancre) : ciels 0,0321/0,0326/0,0332 (3,6 % de bleu) → résidus 1 : 1,70 :
    2,44 → **fond étiré R/G 0,363 · B/G 1,611**. → nouvelle case **« Neutraliser
    la couleur du fond (live) »** (COCHÉE par défaut, cadre « Couleur live ») :
    gains ~2 % mesurés sur la médiane de la moitié sombre, appliqués juste avant
    l'étirement → fond étiré **1,020 · 0,996**. Les gains appliqués sont ANNONCÉS
    dans « État des calculs » ; garde-fou ±10 % (sur un cadrage dominé par un
    objet étendu la moitié sombre n'est plus du ciel). ⚠️ L'équilibrage des
    canaux ne corrige PAS ça : il estime le fond sur un percentile bas (les
    coins, déjà neutres) alors que l'ancre vit dans l'histogramme global.
  - **À TESTER PAR ALAIN** : réécrire « tel que vu » (FITS **et PNG** — le PNG
    doit maintenant être d'accord avec le FITS) sur le même empilement ;
    vérifier de visu que le fond bleu a disparu à l'écran (case cochée) et, si
    un fond coloré reste voulu, décocher la case. Le banc `_test_fond_bleu_jalon62.py`
    accepte un fichier RÉEL en argument : `python _test_fond_bleu_jalon62.py
    <fits>` affiche fond linéaire, gains, fond étiré avant/après.
- **Version stable précédente : AVAStack v2.36.0** — **OPTION « NORMALISATION
  COMMUNE DES CANAUX » (demande d'Alain, 25/09/2026)** : « ce bruit, qu'on utilise
  SPCC ou pas, est présent ; plus on empile, plus VeraLux tire sur l'étirement ». Mesure sur son empilement
  M31 : l'empilement est CORRECT (grain ÷2,2 pour ×4 de frames) mais le **fond du
  composite ne s'améliore pas** (fond/σ 2,88 à 28 frames → 2,50 à 111) et son
  grain est **coloré** (R/G 0,66 · B/G 1,45). CAUSE : `composer()` calait CHAQUE
  rôle sur SES percentiles, et le percentile bas est toujours ~2,8 σ sous le ciel
  → le niveau du fond du composite était proportionnel au bruit du canal (donc
  l'étirement compensait, et le grain du fond restait identique à toute
  profondeur). **Case « Normalisation commune des canaux » (DÉCOCHÉE par
  défaut** — cadre « Composition multi-filtres ») : cochée, les trois rôles
  partagent l'ÉCHELLE du rôle du VERT et aucun point noir n'est soustrait → le
  fond garde son niveau ET sa couleur physiques, son grain s'améliore enfin en
  1/√n et redevient gris ; les coefficients SPCC (des ratios mesurés sur les
  COUCHES) s'appliquent alors sur la base où ils ont été mesurés. **À TESTER PAR
  ALAIN** (il l'a demandé : « on testera après ») — en RGB d'abord, sur le même
  jeu que le diagnostic, en comparant case cochée/décochée sur les mêmes frames.
  Repères attendus : grain du fond PLUS FIN quand on empile (la différence se voit
  sur ~60-120 frames), grain GRIS ; le fond pouvant rester coloré (c'est
  physique) → le neutraliser avec l'équilibrage des canaux ou le recalage
  colorimétrique. Banc : `_test_norm_commune_jalon61.py` (grain/fond ×0,94
  constant par rôle contre ×1,81 en échelle commune entre 30 et 120 frames ;
  grain B/G 2,10 coloré par rôle contre 0,79 = celui des couches).
- **Version stable précédente : AVAStack v2.35.2** — **CORRECTIFS v2.35.2 (constats d'Alain, 25/09/2026)** :
  - **LA MOLETTE CHANGEait LA VALEUR DES LISTES DÉROULANTES** (Tk associe la
    molette aux `ttk.Combobox` par une liaison de CLASSE
    `ttk::combobox::Scroll` — vérifié : un cran fait passer « a » → « b »). En
    défilant les réglages, si le curseur passait sur une liste, elle changeait
    TOUTE SEULE → **des réglages ont pu changer sans intention et FAUSSER DES
    TESTS** (profil de filtre de la SPCC, méthode du recalage…). Les liaisons de
    classe sont supprimées au démarrage : la molette ne modifie plus aucune
    liste et fait défiler le panneau. ⚠️ **PENSER À RE-VÉRIFIER les profils
    SPCC** : sur sa capture du 25/09 le profil « Filtre B » était
    **QHYCCD MiniCam8M Green** (vraisemblablement modifié par cette molette) —
    d'où une mesure SPCC aberrante (pente B/G NÉGATIVE, avertissement « hors de
    [0,5 ; 1,5] ») appliquée quand même.
  - les en-têtes disent quand RIEN n'est appliqué : `AVASPCC` / `AVAGAIA` =
    « non appliquee (case cochee, mesure indisponible) » si la case est cochée
    sans mesure exploitable (avant, l'en-tête restait muet et laissait croire
    que la SPCC était dans le fichier).
  - la mesure SPCC est faite **UNE fois par session** (décocher/recocher la
    refait) : le libellé l'annonce désormais — « mesure faite sur N frames
    (décocher/recocher la case pour refaire) ».
- **Version stable précédente : AVAStack v2.35.1** — **CORRECTIF du 25/09/2026** :
  en COMPOSITION, la sauvegarde pleine résolution traitait GraXpert/débruitage
  live sur le COMPOSITE (> 1 : un cœur d'étoile monte à ~18 après la
  normalisation par rôle) alors que ces outils sont CONTRACTÉS POUR [0..1] —
  GraXpert rescalait sa sortie et le NLM la `clip(0,1)` (mesuré sur son
  empilement M31 : 96 % des pixels > 1 perdus, AVASCALE 1,21 au lieu de 17,94).
  La sauvegarde pleine résolution exécute désormais la chaîne **PAR COUCHE**
  (comme le solveur live) : GX + débruitage sur chaque couche 2D, recomposition,
  CORRECTIONS, puis netteté/SCNR → le fichier garde son échelle linéaire
  (banc `_test_save_brute_jalon59.py` [7]). Outil de diagnostic ajouté :
  `_diag_empilement_couleur.py`.
- **CHANTIER v2.35.0** (24/09/2026, décisions d'Alain) — tous les bancs
  logiciels au vert (sweep du 25/09/2026 : 50 bancs, code de sortie 0 ; les
  bancs matériels sont hors sweep) :
  **SAUVEGARDE LINÉAIRE BRUTE + CORRECTIONS DE COULEUR DANS LA CHAÎNE DE
  SORTIE** (étapes ①→⑦ du plan), en détail :
  - `composer()` ne porte PLUS aucun gain : il produit l'EMPILEMENT BRUT
    (normalisation par rôle + combine L). `composer(gains=…)` N'EXISTE PLUS.
  - Toutes les corrections de couleur vivent en AVAL, dans
    `composition.corrections_couleur()` = gains R/G/B (manuels × SPCC/Gaia) →
    équilibrage des canaux auto → recalage « Linear Fit ». Primitives :
    `appliquer_gains`, `appliquer_gains_canaux`, `appliquer_equilibrage`.
  - `CompositeStacker.mean()` / `mean_avec_canaux()` : nouveau paramètre
    `corrections=True` (DÉFAUT = comportement d'affichage inchangé) ;
    `corrections=False` = EMPILEMENT BRUT (ce que la sauvegarde linéaire
    enregistre). `LiveStacker.mean()` accepte le même paramètre (équilibrage et
    recalage sautés : c'est la voie du fichier brut, y compris en mono/OSC ;
    l'interface des deux classes reste identique).
  - Sauvegardes « empilement (linéaire) » et « canaux (par filtre) » : chemin
    BRUT. **Preuve au banc** (`_test_save_brute_jalon59.py` [4]) : le fichier
    est IDENTIQUE AU PIXEL PRÈS avec et sans SPCC/gains Gaia/équilibrage/
    Linear Fit cochés, alors que l'affichage, lui, change.
  - Solveur live : l'équilibrage est transporté (6e élément de `vl_compo` =
    actif/force/cadre, déballage tolérant) et appliqué APRÈS la recomposition
    des couches traitées, AVANT la netteté — ordre validé (c). Le traitement
    EXTERNE par couche (`_run_external_compo`) suit la même chaîne.
  - **NOUVEAU bouton** (décision (a)) : « 💾 Enregistrer l'empilement traité
    (linéaire)… » = 3e sortie linéaire — empilement brut → gradient live →
    débruitage live → CORRECTIONS → netteté → SCNR, SANS étirement ni
    gamma/saturation. Il emprunte le thread de « tel que vu »
    (`_save_asseen_thread(..., lineaire=True)`, 4e élément de la demande) et
    écrit un en-tête auto-descriptif. Le bouton « résultat traité (linéaire) »
    du cadre Traitement externe reste lié au ⚡ manuel (instantané).
  - En-têtes (étape ⑥) : `AVASPCC` / `AVAGAIA` sont désormais les MESURES de la
    session (mêmes formats `K=…` / `B=…`) ; la NOUVELLE clé `AVAAPPLI` dit ce
    qui est RÉELLEMENT appliqué à l'image écrite (« aucune (empilement BRUT) »
    pour le brut, liste des corrections pour le traité) ; `AVAWB` / `AVAFIT` ne
    sont écrits que s'ils sont appliqués ; `AVAVUE` décrit la vue enregistrée
    (« empilement BRUT … » / « empilement TRAITE … sans etirement »).
  - Bancs : `_test_save_brute_jalon59.py` (NOUVEAU, 6 sections : composer sans
    gain, façade deux chemins, ordre des corrections, **fichier identique
    cases cochées/décochées**, solveur live à 6 éléments, 3e sortie linéaire
    réelle) ; adaptés : `_test_composition_jalon19` [4] (gains via
    `appliquer_gains`), `_test_save_lineaire_echelle` [4] (référence =
    `mean(corrections=False)`), docstring de `_test_compo_worker_jalon19`.
- **PIÈGES DU CHANTIER (à retenir)** :
  - `composer()` est appelé par QUATRE chemins (façade, solveur, externe par
    couche, bancs) : retirer un paramètre ne casse RIEN à la compilation — le
    banc jalon 19 [4] est ce qui l'attrape ;
  - une correction appliquée APRÈS `composer()` n'est plus absorbée par la
    normalisation par rôle (c'est le but) : TOUTE vue qui doit ressembler à
    l'affichage doit passer par `corrections_couleur` (façade, solveur,
    sortie traitée) — sinon les vues divergent ;
  - `wb_auto` est posé sur le stacker à la CRÉATION seulement (le worker ne le
    resynchronise pas à chaque tour), alors que gains / mode L / recalage le
    sont ;
  - pour toute comparaison EXTERNE avec Siril, sauvegarder le linéaire
    (maintenant BRUT par construction : c'est la référence reproductible).
  - **LES OUTILS LIVE SONT CONTRACTÉS POUR [0..1]** (v2.35.1) : GraXpert live
    rescalait et le NLM (`denoise._nlm`) ÉCRÊTE à [0,1] + quantifie 16 bits.
    Une image qui dépasse 1 doit donc y entrer **PAR COUCHE** (les couches
    sont ≤ 1, le composite NON : ~18 après la normalisation par rôle).
    Vérifier AVASCALE dans l'en-tête d'un fichier écrit : s'il vaut ≈ 1 alors
    que le brut vaut ~18, l'écrêtage a eu lieu.
  - `_diag_empilement_couleur.py` répond en une commande à « pourquoi mon
    image est-elle colorée / bruitée ? » : fond et σ par canal (le BRUIT),
    contraste de fond R/G et B/G, rapport brut/traité, clés AVA*.
- **DÉCISION D'ALAIN (25/09/2026) → IMPLÉMENTÉE EN OPTION (v2.36.0) — LE GRAIN
  BLEU-VERT NAÎT DANS LA COMPOSITION** (mesuré au plancher de bruit, zones les
  plus lisses, sur son M31 RGB) :
  - COUCHES brutes `canal_*.fit` : σ 0,000498 / 0,000557 / 0,000526 →
    **grain équilibré** (R/G 0,89 · B/G 0,94) ;
  - composite BRUT v2.35.0 : σ 0,00517 / 0,00781 / 0,01133 →
    **grain COLORÉ** (R/G 0,66 · B/G 1,45).
  Cause : `composer()` calait CHAQUE rôle sur ses propres percentiles
  (p0,25/p99,7), et le percentile BAS est toujours ~2,8 σ sous le ciel → le
  niveau du fond du composite était proportionnel au BRUIT du canal : empiler
  plus faisait baisser le fond ET le grain dans la même proportion, l'étirement
  (VeraLux) compensait, donc **le grain du fond ne s'améliorait jamais**
  (fond/σ 2,88 à 28 frames → 2,50 à 111, alors que le grain diminuait bien en
  1/√n). Le grain était en plus coloré car chaque canal était divisé par SA
  dynamique (celle du bleu 2,1× plus étroite : M31 est jaune).
  **Couvert par la case « Normalisation commune des canaux » (v2.36.0, DÉCOCHÉE
  par défaut)** : échelle du vert partagée par les trois rôles, AUCUN point noir
  soustrait → le fond garde son niveau et sa couleur physiques, son grain
  s'améliore enfin en 1/√n et redevient gris ; les coefficients SPCC, qui sont
  des ratios mesurés sur les COUCHES, s'appliquent alors sur la base où ils ont
  été mesurés. Pistes qui restent en réserve si le test réel ne suffit pas :
  (b) gains appliqués AUX COUCHES avec bornes FIGÉES (argument `bornes=` déjà
  là) ; (c) ne pas empiler le GAIN du Linear Fit sur la SPCC (Siril n'ajoute
  qu'une référence de FOND) ; (d) accepter.
- **POURQUOI STF ET VERALUX NE MONTRE PAS LA MÊME IMAGE (constaté, documenté)** :
  tout le cadre VeraLux (GraXpert live, débruitage live, SCNR live) est MASQUÉ
  en mode STF (`_on_moteur` : `frm_veralux.pack_forget()`) et le thread solveur
  — seul chemin du GX live — ne tourne qu'en mode VeraLux. En STF, l'image est
  donc le composite corrigé + netteté, SANS retrait de gradient ni débruitage.
  Seule la netteté est commune aux deux moteurs. C'est une décision de
  conception ; à rouvrir si Alain veut un rendu identique entre les moteurs.
- **À FAIRE / À VALIDER PAR ALAIN** :
  - **test RÉEL de l'option v2.36.0** (« Normalisation commune des canaux ») sur
    le même jeu M31 RGB : cocher, empiler, comparer au décoché. Repères : grain du
    fond PLUS FIN à mesure que l'on empile (l'écart se voit vers 60-120 frames),
    grain GRIS au lieu de bleu-vert ; le fond peut rester coloré (c'est physique)
    → le neutraliser avec l'équilibrage des canaux ou le recalage colorimétrique.
    **Installer l'installateur 2.36.0 AVANT** ;
  - **re-vérifier les 4 profils SPCC** (le bug de molette v2.35.2 a pu en changer
    un : « Filtre B » était QCMiniCam8M Green sur sa capture du 25/09) puis
    décocher/recocher la case pour relancer la mesure ;
  - test RÉEL du correctif 2.35.1 : réécrire « empilement traité (linéaire) »
    avec GraXpert + débruitage live actifs et vérifier AVASCALE (~18, plus
    1,2) et des cœurs d'étoiles non écrêtés. **Installer l'installateur
    2.35.1 AVANT** ;
  - test RÉEL du chantier v2.35.0 : « empilement (linéaire) » neutre/brut
    (Siril : plus de gain implicite à annuler) ;
  - étape 6 du jalon 56 : validation Siril/ASTAP des fichiers écrits, puis test
    réel multi-filtres avec les gains photométriques cochés.
- **POINT CLARIFIÉ (24/09/2026)** : la SPCC de Siril exige les COURBES DE
  TRANSMISSION des filtres ET la réponse du capteur (profils Siril) pour
  prédire le flux attendu par bande ; la photométrie d'AVAStack est RELATIVE
  contre Gaia G (aucun spectre, aucune transmission) — d'où des gains Gaia qui
  refroidissent l'image (dispersion des zéro-points croissante vers le bleu :
  R 0,162 / G 0,233 / B 0,376 mag). La SPCC ABSOLUE (v2.33-2.34) est, elle,
  branchée et validée à 1,4-1,8 % contre Siril sur les MÊMES pixels
  (`_diag_spcc.py --export-rgb`).



## Statuts CLAUDE.md

- Leçons ÉCRITES le 19/09/2026 (accord d'Alain) : introspection des
  exports de la DLL sous le binding ; convention roue `48+n` vs `'0'`
  tranchée par l'effet physique ; SDK natif (init unique, état non
  libérable, crash → trace + sous-processus) ; identité des fichiers
  chargés avant toute interprétation ; réglage relu ≠ réglage appliqué
  (seul l'effet physique prouve).
- Leçons ÉCRITES le 20/09/2026 (accord d'Alain, « écris les 2 ») :
  jalon 13 (appariements mutuels + seuil relevé quand la décision sert
  d'ANCRE ; deux normalisations distinctes rendent une SSD aveugle —
  partager les bornes) ; jalon 24 (valider les placeholders d'un gabarit
  AVANT la substitution). Plus AUCUNE leçon en attente.

## Setup d'Alain

- **Setup 1 (miniPC)** : QHY MiniCam8M (mono refroidie, roue intégrée,
  alim. 12 V requise) ; N.I.N.A. → dossiers
  `TargetSchedulerSequence/<cible>/<expo>/LIGHT` — un dossier peut
  MÉLANGER plusieurs nuits (la 1re frame par mtime n'est pas forcément de
  la nuit courante).
- **Setup 2** : C8 défourché + réducteur 0,63 → 1280 mm ; Player One
  Uranus-C Pro (couleur, IMX585, 3856×2180, RGGB, gain unitaire 210,
  TEC) sur monture DIY **Open Astro Mount** ; guidage SVBONY SV305C sur
  lunette 60/240. Constat 17/09/2026 à 1280 mm : étoiles « en plusieurs
  points puis en trainées » → origine du jalon 13 (alignement robuste).
  Banc POA : `_diag_camera_playerone.py` (jalon 28).
- **Outils astro locaux vérifiés (22/09/2026)** : Siril 1.4.4
  (catalogues : chunks Gaia XP dans `%LOCALAPPDATA%\Siril\...`,
  base SPCC capteurs/filtres dans `siril-spcc-database`) ; ASTAP
  (`C:\Program Files\astap`, astap_cli.exe + base D80 Gaia DR3 1,24 Go)
  ; PAS d'astrometry.net/ANSVR.


## Pièges récents (rappels opérationnels)

- **LIMITE QHY (toujours valable)** : après « ■ Arrêter », relancer
  l'appli — le binding qhyccd n'expose AUCUNE libération du SDK (état
  irréinitialisable dans le process) ; le banc QHY l'annonce et conseille
  fermer + relancer.
- Entry/Combobox/`var.get()` Tkinter interdits hors thread principal —
  lire les widgets DANS Tk puis passer les valeurs au worker (bouchons
  `_Val` dans l'appli) ; toute contrôle `_on_*` finit par
  `_refresh_preview()`, les `_sync_*_vue` ne touchent qu'à l'ÉTAT.
- **Installateur à REBUILDER avant tout test réel dès que la passe de code
  touche PLUS d'un ou deux fichiers** (`powershell -NoProfile
  -ExecutionPolicy Bypass -File installer\windows\build_avastack.ps1`) —
  à la charge de l'agent, sans qu'Alain ait à le demander.

## Clôtures précédentes

- 21/09/2026 (v2.23.3, aca5ca5) : jalon 55 VALIDÉ PAR ALAIN en réel
  (M31 RGB, mode dossier) — gains R/G/B temps réel, image équilibrée.
  Rappel opérationnel : équilibrage auto OU Linear Fit re-normalisent les
  canaux → gains manuels sans effet tant que l'un des deux est actif ;
  pour réchauffer les tons, MONTER R. Repli si régression : v2.22.0
  (225f026).
- 20/09/2026 : TOUTES les validations matérielles (QHY miniPC, Player
  One, SVBONY, roue, TEC, cadence 39-46, ergonomie 47-48) CLOS — verdicts
  d'Alain ; bancs `_diag_camera_*.py` conservés pour diagnostic futur.
- Crash OpenCV 5/OpenCL au teardown (`cv2.ocl.setUseOpenCL(False)`) ;
  tests `ui.App` hermétiques (`ui.CONFIG = {}` + sauver_config
  intercepté) ; images de tests bruitées (sinon 0 étoile).
- Ne JAMAIS mélanger grid et pack dans le même conteneur Tk (attrapé par
  le test UI du banc POA : `_tkinter.TclError` « grid is already
  managing its content windows »).
- SDK natif : chargement UNE fois par process ; crash natif non
  rattrapable → tracer chaque étape dans un fichier ; vérifier
  l'identité des fichiers réellement chargés AVANT d'interpréter un
  plantage (les bancs affichent DLL + module + dates).
- PIÈGE LANCEMENT : `python3` ≠ venv — toujours `python AVAStack.py`.
- Ordre de la chaîne (Alain, 16/09/2026) : recadrage → gradient →
  débruitage → netteté → étirement. Débruitage : code gelé, cases
  décochées (décision du 16/09/2026) — ne pas retoucher sans nouvelle
  demande ; défauts des traitements confirmés (live = désactivé, NLM,
  force 0,5 ; externe = désactivé, GraXpert IA, force 0,5).
