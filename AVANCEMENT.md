# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---


- **Version stable de référence : AVAStack v2.37.1** (`avastack/__init__.py`),
  branche `master` — **LES AJOUTS RÉCENTS ENTRENT DANS LA CHAÎNE EXTERNE**
  (demande d'Alain, 25/09/2026 : « intégrer les derniers ajouts (SPCC,
  neutralisation, bruit chroma) dans la chaîne de traitement externe pour que je
  puisse sortir une belle image à la fin du stack ») :
  - la **SPCC y était déjà** (vérifié dans le code) : les corrections de couleur
    du composite — gains EFFECTIFS SPCC/Gaia/manuels, équilibrage, recalage
    « Linear Fit » — s'appliquent en mono (`mean()` corrigé, défaut) et en
    composition (`corrections_couleur` après recomposition, `_run_external_compo`)
    ; le traitement par couche (GraXpert gradient/débruitage) reste sur les
    couches BRUTES (contrat jalon 54) → rien n'est appliqué deux fois ;
  - **« 7. Neutraliser la couleur du fond »** (Cochée par défaut, comme la case
    live) et **« 8. Réduire le bruit chromatique »** (opt-in, force = curseur
    « Couleur live ») dans le cadre « Traitement externe », appliquées au même
    rang que dans le live (… → SCNR → SCNR doux → démagenta → fond → chromatique) ;
    gains de neutralisation annoncés dans le message final ; transport 12e/13e/
    14e éléments du job (déballage tolérant : les jobs 11-tuple restent valides) ;
    cases persistées (`ext_neutre_fond`, `ext_chroma`). Banc
    `_test_couleurs_jalon22.py` [3bis]/[4] ; banc jalon 7 mis à jour (14-tuple).
  - libellé corrigé au passage : sans source choisie, la case SPCC annonçait
    « sans effet en MONO » alors que l'appli ne sait pas encore ce que sera la
    source (constat d'Alain en rouvrant l'appli).
- **Version stable précédente : AVAStack v2.37.0** — **RÉDUCTION DU BRUIT
  CHROMATIQUE + MESURES RELANCÉES EN FIN DE STACK** :
  - **(a) Réduction du bruit chromatique** (« un équivalent de SCNR pour le bleu »
    — son mot ; sa réponse : « oui […] et case DÉCOCHÉE par défaut »). Nouvelle
    primitive `couleurs.reduire_bruit_chroma(img, force)` : lissage de la CHROMA
    en espace YCrCb (seuls Cr/Cb réécrits → luminance intacte, écart < 2e-06 sur
    le fond), appliquée APRÈS la neutralisation et AVANT l'étirement, dans le
    solveur VeraLux (10e/11e éléments du job) et dans le chemin « tel que vu » —
    jamais dans la sortie 3 (linéaire). Case + curseur de force dans « Couleur
    live », rendu immédiat. Banc `_test_chroma_nr_jalon63.py` (le grain coloré
    tombe exactement de la part demandée : ×0,751/×0,502/×0,024 pour 0,25/0,5/1,0
    ; couleur de l'objet préservée à 0,86 % ; le grain de LUMINANCE n'est pas
    touché → le grain restant est GRIS, c'est le débruitage qui réduit son
    amplitude).
  - **(b) Refaire une mesure en fin de stack** (« en fin de stack, ça ne met rien
    à jour : le libellé reste gris avec les anciennes valeurs ») : le worker
    sortait par « lu is None » / « not empilement_on » AVANT `_astro_tour` /
    `_photo_tour` / `_spcc_tour`. Désormais une case décochée/recochée pose une
    DEMANDE servie sans frame (`_servir_demandes_sans_frame`) et le texte de la
    mesure est poussé (`_pousser_rendu` rafraîchit les lignes de mesure).
- **MESURES SUR SES DEUX FICHIERS v2.36.1 (41 et 115 frames, 51/123 empilées)** —
  `_diag_empilement_couleur.py` :
  - grain (plancher de bruit) : σ 0,000519 / 0,000579 / 0,000673 à 41 frames →
    **0,000338 / 0,000375 / 0,000440** à 115 frames, soit **÷1,53** pour ×2,8 de
    frames (théorie 1/√n = 1,67 ; l'écart vient du ciel lui-même 6 % plus sombre).
    **LE GRAIN DU FOND S'AMÉLIORE ENFIN AVEC L'INTÉGRATION** : le rapport
    fond/σ passe de ~63/57/49 (R/G/B) à ~91/82/70, soit **×1,44** — c'est
    exactement ce que la normalisation commune devait apporter (avant, il restait
    CONSTANT : 2,88 → 2,50 sur 28→111 frames) ;
  - fond toujours **neutre** (R/G 0,9998 · B/G 0,9999) ✔ ;
  - **grain résiduel COLORÉ et STABLE** : R/G 0,898→0,902 (équilibré) mais
    **B/G 1,163→1,174** : le bleu reste ~17 % plus bruité que le vert. Cause
    MESURÉE (comptes exacts) : une correction MULTIPLICATIVE amplifie le bruit du
    canal qu'elle monte. Les gains appliqués (SPCC K=0,6223/0,7587/1,0000 +
    équilibrage force 0,43 + offsets) donnent
    (σ_R·K_R)/(σ_G·K_G) = 1,099 × 0,820 = 0,902 ✔ (mesuré 0,902) et
    (σ_B·K_B)/(σ_G·K_G) = 0,891 × 1,318 = 1,174 ✔ (mesuré 1,174) : **c'est la SPCC
    elle-même qui monte le grain bleu** (K_B/K_G = 1,32), pas la normalisation.
    Sans correction, l'équilibre serait R/G 1,10 · B/G 0,89.
- **HISTORIQUE CONDENSÉ (v2.35.0 → v2.36.1)** — traces complètes dans le
  changelog de `avastack/__init__.py` et l'historique git ; les leçons durables
  sont dans les « Pièges » de CLAUDE.md :
  - **v2.36.1 — FOND BLEU, deux causes** : ① `save_image` donnait une image RGB à
    `cv2.imencode` (qui attend du BGR) → TOUT PNG/TIFF exporté avait R et B
    permutés, depuis des mois et invisiblement (l'aller-retour interne restait
    cohérent) ; ② l'étirement VeraLux soustrait une ANCRE puis étire en log : 3,6 %
    d'écart de ciel → fond étiré R/G 0,363 · B/G 1,611. Correctif ② : case
    « Neutraliser la couleur du fond » (défaut coché ; gains ~2 % sur la médiane de
    la moitié sombre, garde-fou ±10 %, gains ANNONCÉS) — l'équilibrage des canaux
    ne le remplace pas (il lit un percentile bas — les coins, déjà neutres —
    alors que l'ancre vit dans l'histogramme global).
  - **Références de mesure sur ses empilements M31 v2.36.1** (41/51 et 115/123
    frames, `_diag_empilement_couleur.py`) : grain σ 0,000519/0,000579/0,000673 →
    0,000338/0,000375/0,000440 (÷1,53 pour ×2,8 de frames, théorie 1,67) ;
    fond/σ ×1,44 ; fond NEUTRE (R/G 0,9998 · B/G 0,9999) ; grain résiduel
    B/G 1,163 → 1,174 avec R/G 0,90 — le point de départ du grain bleu réglé en
    v2.37.0 (gains multiplicatifs : 0,891 × 1,318 = 1,174).
  - **v2.36.0 — normalisation COMMUNE des canaux (option, décochée)** : par défaut
    `composer()` calait chaque rôle sur SES percentiles, donc le niveau du fond du
    composite était proportionnel au bruit du canal (fond/σ 2,88 à 28 frames →
    2,50 à 111 : il ne s'améliorait PAS en empilant) et le grain était coloré
    (R/G 0,66 · B/G 1,45). En échelle commune (celle du rôle vert), le fond garde
    son niveau physique : fond/σ ×1,81 entre 30 et 120 frames, grain B/G 0,79 =
    celui des couches. Ses deux empilements v2.36.1 l'ont UTILISÉE (AVACOMPO dans
    les fichiers) ✔. Banc `_test_norm_commune_jalon61.py`.
  - **v2.35.2 — la MOLETTE changeait les listes déroulantes** (liaison de CLASSE Tk
    `ttk::combobox::Scroll`) : des profils SPCC pouvaient changer sans intention
    (son « Filtre B » était sur MiniCam8M Green) — re-vérifiés par Alain le
    25/09/2026 ✔. En-têtes muets levés (`AVASPCC`/`AVAGAIA` disent quand rien n'est
    appliqué) ; la mesure SPCC est faite UNE fois par session.
  - **v2.35.1 — sauvegarde pleine résolution PAR COUCHE** en composition :
    GraXpert/débruitage voyaient un composite > 1 (outils contractés pour [0..1])
    → 96 % des pixels perdus, AVASCALE 1,21 au lieu de 17,94. Contrat de sortie :
    le fichier linéaire reste « empilement + corrections », l'étirement n'y entre
    JAMAIS (vérifié par `_test_save_brute_jalon59.py` [6]).
  - **Repères durables de la chaîne de sortie (chantier v2.35.0)** :
    `composer()` ne porte AUCUN gain (empilement BRUT) ; toutes les corrections
    vivent dans `composition.corrections_couleur()` = gains (manuels × SPCC/Gaia) →
    équilibrage des canaux → recalage « Linear Fit », appliquées au COMPOSITE en
    aval (jamais aux couches : le solveur live re-compose et ré-applique lui-même,
    et le traitement par couche reste sur des couches BRUTES) ;
    `mean(corrections=False)` = fichier linéaire brut ; STF et VeraLux ne montrent
    pas la même image (une seule transformation sur la luminance, contre ancre +
    log) ; la SPCC ABSOLUE exige les COURBES DE TRANSMISSION et la réponse du
    capteur (base Siril) alors que la photométrie Gaia est RELATIVE (gains qui
    refroidissent l'image) — validée à 1,4-1,8 % contre Siril sur les mêmes pixels.

## En attente / prochaine session

- **Alain teste la chaîne EXTERNE complète** sur sa M31 (GraXpert gradient +
  débruitage PAR COUCHE, BXT, puis cases **7** « Neutraliser la couleur du fond »
  — cochée par défaut — et **8** « Réduire le bruit chromatique ») et juge : la
  neutralisation par défaut est-elle utile/suffisante sur la version traitée ?
  la force 0,5 du bruit chromatique est-elle trop douce (curseur « Couleur
  live ») ?
- **Grain GRIS résiduel** : la réduction du bruit chromatique ne touche PAS le
  grain de luminance (mesuré ×1,00) — seul le débruitage live (NLM, force 0,5)
  ou plus d'intégration le réduit. Sujet OUVERT si Alain veut aller plus loin
  (piste : débruiteur épargnant les étoiles, cf. CLAUDE.md).
- **CLOS par cette session** : profils SPCC re-sélectionnés par Alain (« les
  filtres sont bons » : R/G/B MiniCam8M + « Average Spiral Galaxy ») ✔ ; option
  « normalisation commune des canaux » UTILISÉE et mesurée sur ses deux
  empilements M31 (AVACOMPO dans les fichiers) ✔ ; fond bleu des PNG/FITS clos ✔ ;
  PNG ↔ FITS concordants (à revérifier à la prochaine exportation « tel que vu »).

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
- Leçons ÉCRITES le 25/09/2026 (au fil de la session, constats d'Alain) : un
  `imencode` attend du BGR (PNG/TIFF R-B permutés pendant des mois) ; un étirement
  log AMPLIFIE la couleur du fond (l'ancre de VeraLux) ; un gain MULTIPLICATIF
  amplifie le bruit du canal qu'il monte (le grain bleu vient de la SPCC) ; les
  mesures astro/photométrie/SPCC sont relancées par le WORKER (une case qui
  déco/recoche pose une DEMANDE servie même sans frame).
- Leçon EN ATTENTE d'accord d'Alain (25/09/2026, une ligne, proposition) : toute
  correction PRÉ-ÉTIREMENT ajoutée à la chaîne LIVE doit être vérifiée/mirrorée
  dans la chaîne de TRAITEMENT EXTERNE (et réciproquement) — les deux chaînes
  doivent produire le même rendu (constat : la SPCC y était déjà via les
  corrections de couleur, mais la neutralisation du fond et le bruit chromatique
  manquaient → v2.37.1).

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

- 25/09/2026 (v2.37.1, db0e870) : SESSION « FOND BLEU → GRAIN BLEU → CHAÎNE
  EXTERNE », VALIDÉE PAR ALAIN (« Ça me parait OK »). Livré : PNG/TIFF sans
  permutation R-B (v2.36.1) ; neutralisation de la couleur du fond avant étirement
  (défaut COCHÉ) ; réduction du BRUIT CHROMATIQUE (opt-in, force = curseur
  « Couleur live ») ; mesures SPCC/photométrie relançables EN FIN DE STACK ; cases
  couleur à rendu IMMÉDIAT ; et les deux corrections pré-étirement intégrées à la
  chaîne de traitement EXTERNE (la SPCC y était déjà, vérifié). Bancs : 63 dont
  `_test_chroma_nr_jalon63.py` (nouveau) et `_test_couleurs_immediat_jalon39.py`
  étendu aux quatre cases. Installateur 2.37.1 reconstruit. Repli si régression :
  v2.36.0 (5f91ae0) = comportement d'avant ces correctifs.
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
