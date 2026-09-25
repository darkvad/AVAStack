# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---


- **Version stable de référence : AVAStack v2.37.3** (`avastack/__init__.py`),
  branche `master` — **LE HALO DE COULEUR DES ÉTOILES ÉTAIT FABRIQUÉ PAR LA
  RÉDUCTION DE BRUIT CHROMATIQUE** (constat d'Alain, 26/09/2026 : « les étoiles
  brillantes rouges et bleues ont un halo gênant », VISIBLE AUSSI dans le fichier
  passé par BlurXTerminator — « en général, c'est un halo killer pourtant ») :
  - **Mesure** sur son empilement M31 réel, couronne r = 3..9 px en multiples du
    niveau de ciel local (fond neutralisé = l'ordre réel de la chaîne) : étoile
    la plus brillante (rouge) R 41,3 → 34,9 (−16 %) et B 19,9 → 23,6 (+19 %) ;
    étoile bleue R 3,53 → 1,74 (−51 %) et B 2,72 → 3,92 (+44 %) — un **HALO BLEU
    créé là où il n'y en avait aucun** (R/B 1,30 → 0,44) ; la LUMINANCE, elle, ne
    bougeait pas (±6 %). Contrôle : à force ≈ 0, la même conversion YCrCb→RVB rend
    l'image AU BIT PRÈS → c'est le FLOU qui est en cause, pas la conversion.
  - **Cause** : un écart de chroma (Cr/Cb) ne dépend PAS de la luminosité du
    pixel ; le flou mélangeait donc la couleur du CŒUR de l'étoile avec celle du
    CIEL voisin et déposait ce mélange sur les AILES faibles, où un minuscule
    écart devient une énorme couleur.
  - **Pourquoi BXT n'a rien pu faire** : la chaîne externe applique les cases 7/8
    APRÈS BlurXTerminator (`_run_external`) — le halo naît APRÈS le « halo
    killer ». À noter : BXT a bien un réglage de halos, `--ash` /
    `--adjust-star-halos` (−0,5…+0,5) dont le DÉFAUT 0,00 signifie « aucun
    ajustement », et la commande par défaut de l'appli ne le passe pas — piste
    INDÉPENDANTE, non modifiée ici (à essayer côté BXT si des halos RÉELS
    subsistent ; testé sur un extrait : `-0.30` réduit encore, `+0.30` conserve).
  - **Correctif (option (A) choisie par Alain, 26/09/2026)** : ① `reduire_bruit_
    chroma` lisse désormais le RAPPORT de couleur (chroma ÷ échelle locale), et
    l'échelle locale est le MINIMUM entre la luminance DU PIXEL (elle borne la
    correction près d'une étoile → plus de halo) et sa version LISSÉE (échelle
    constante sur le fond → le bruit de luminance ne se re-dépose pas dans la
    couleur) ; ② le rayon SUIT la RÉSOLUTION (`couleurs.rayon_chroma_apercu` +
    `DisplayProcessor.vl_chroma_rayon`) : l'aperçu de l'appli (facteur 0,417 sur
    son image) passait de 3 px effectifs (7,2 px pleine résolution) à 1,25 px —
    l'écran redevient fidèle au fichier.
  - **Effets mesurés** : grain coloré du fond ×0,17 sur son fichier (×0,16 avant →
    bénéfice conservé) ; halo de son étoile bleue R/B 1,32 (référence 1,30) au
    lieu de 0,44 ; **écart RENDU** du halo (après VeraLux, en points de % du pic
    vert) sur 6 étoiles brillantes de son fichier : **1,4 à 1,9 point** avec le
    correctif contre 2,7 à 24,5 points avec l'ancienne formule.
  - **Bancs** : `_test_chroma_halo_jalon65.py` (NOUVEAU — halo d'une étoile à
    ailes larges préservé, TÉMOIN = l'ancienne formule ré-écrite exprès pour
    prouver que le banc DISCRIMINE, rayon ⇄ résolution avec plancher de mesure,
    transport par le solveur, et son fichier réel en argument) ;
    `_test_chroma_nr_jalon63.py` ajusté (borne haute documentée au lieu de
    l'égalité (1−force) : la formulation par ratio n'est plus exactement
    linéaire) ; non-régression rejouée — jalon1/2/3, jalon4, jalon5, jalon6,
    jalon7, jalon19 (×2), jalon22, jalon39, jalon40, jalon41, jalon47, jalon62,
    jalon63, jalon64 : **TOUS PASSENT**.
  - **Preuve visuelle à juger par Alain** : `C:\Astro\test\
    _diag_halo_etoiles_AVANT_APRES.jpg` (aperçu de l'appli ET pleine résolution,
    avant/après + écart ×8).
  - **PROCHAINE ÉTAPE** : Alain relance l'appli (v2.37.3) et dit si le halo a
    disparu DANS LA VISU et dans un fichier passé par BXT ; ses commentaires
    décideront si l'on baisse aussi le rayon de RÉFÉRENCE (3 px) ou si l'on
    ajoute `--ash` à la commande BXT pour les halos réels.

- **Version stable précédente : AVAStack v2.37.2** — le cœur « cramé » était une
  COUPE à 1,0 appliquée avant l'étirement, alors que l'empilement vit à une
  échelle arbitraire (13-18) : correctif `veralux.normaliser_lin()` (UN SEUL
  facteur GLOBAL, la règle des sauvegardes linéaires), le dégradé du cœur est
  revenu ; validé par Alain le 25/09/2026, y compris la chaîne externe complète.
  (Détails : changelog du source + `_test_coeur_crame_jalon64.py`.)

- **Avant cela : AVAStack v2.37.1** — les ajouts récents (SPCC,
  déjà présente dans la chaîne externe, plus les cases **« 7. Neutraliser la
  couleur du fond »** — cochée par défaut — et **« 8. Réduire le bruit
  chromatique »**) intégrés à la chaîne de traitement EXTERNE au même rang que
  dans le live ; libellé SPCC corrigé. (Détails : changelog du source.)
- **Avant cela : v2.37.0** — réduction du bruit chromatique (opt-in, force =
  curseur « Couleur live ») et mesures (astrométrie/photométrie/SPCC) relançables
  en fin de stack (case décochée/recochée = demande servie sans frame).
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

- **VALIDATION VISUELLE D'ALAIN SUR v2.37.3** (le halo de couleur) : relancer
  l'appli, vérifier la visu (l'aperçu applique maintenant le rayon ramené) ET un
  fichier passé par BlurXTerminator ; la planche
  `C:\Astro\test\_diag_halo_etoiles_AVANT_APRES.jpg` sert de référence visuelle.
  Selon son verdict : (a) rien à faire ; (b) baisser aussi le rayon de RÉFÉRENCE
  (3 px) ; (c) ajouter `--ash` (−0,3 … −0,5) à sa commande BXT pour les halos
  RÉELS. Son verdict décidera aussi si l'on reconstruit à nouveau l'installateur
  2.37.3 (déjà reconstruit en fin de passe).
- **Grain GRIS résiduel** : la réduction du bruit chromatique ne touche PAS le
  grain de luminance (mesuré ×1,00) — seul le débruitage live (NLM, force 0,5)
  ou plus d'intégration le réduit. Sujet OUVERT si Alain veut aller plus loin
  (piste : débruiteur épargnant les étoiles, cf. CLAUDE.md).
- **CLOS par cette session** : cœur de M31 VALIDÉ par Alain sur l'appli v2.37.2
  (« Le cœur n'est effectivement plus cramé ni plat ») ✔ ; **chaîne EXTERNE
  complète VALIDÉE** par lui dans la foulée (« validée pour le moment ») ✔ ;
  débruitage NLM essayé par lui sans dégradation du cœur → laissé tel quel ✔ ;
  profils SPCC re-sélectionnés par Alain
  (« les filtres sont bons » : R/G/B MiniCam8M +
  « Average Spiral Galaxy ») ✔ ; option « normalisation commune des canaux »
  UTILISÉE et mesurée sur ses deux empilements M31 (AVACOMPO dans les fichiers) ✔ ;
  fond bleu des PNG/FITS clos ✔ ;
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
- Leçons EN ATTENTE d'accord d'Alain (26/09/2026, constats de sa session « halo
  des étoiles » — texte proposé, rien n'est écrit dans CLAUDE.md sans son accord) :
  1. **La couleur d'un pixel est un RAPPORT, pas un écart absolu** : lisser une
     chroma ABSOLUE (Cr/Cb de YCrCb) mélange la couleur du CŒUR d'une étoile avec
     celle du CIEL et la dépose sur les AILES faibles, où un minuscule écart
     devient une énorme couleur — halo de couleur fabriqué (mesuré : R/B d'une
     couronne d'étoile 1,30 → 0,44). Lisser le RAPPORT de couleur, à une échelle
     bornée par la luminance locale, le supprime sans perdre le bénéfice.
  2. **Toute échelle SPATIALE (rayon de flou, seuil de détection) doit suivre la
     RÉSOLUTION** : la même valeur en pixels appliquée à un APERÇU RÉDUIT étale
     relativement plus qu'aux fichiers (constat : 3 px d'aperçu = 7,2 px pleine
     résolution sur son image de 3838 px → halo 2,4× plus large à l'écran) ;
     l'écran doit montrer ce que le fichier contient.
  3. **Une correction appliquée EN FIN de chaîne externe est invisible à l'outil
     qui la précède** : BXT tourne AVANT les cases 7/8, donc son « halo killer »
     ne peut rien contre un halo créé après lui (et son réglage de halos `--ash`
     vaut 0,00 par défaut, absent de la commande par défaut de l'appli).
  4. **Quand une formule change de NATURE, la propriété du banc doit être
     ré-énoncée honnêtement** (borne haute documentée au lieu d'une égalité
     devenue impossible) — et **une fidélité (aperçu ⇄ fichier) se mesure PAR
     RAPPORT au plancher de mesure** du redimensionnement, jamais en absolu.

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

- 25/09/2026 (v2.37.2, 5545a9c) : SESSION « LE CŒUR CRAMÉ ÉTAIT UNE COUPE »,
  VALIDÉE PAR ALAIN (« Le cœur n'est effectivement plus cramé ni plat »). Livré :
  la CAUSE (le chemin d'étirement COUPAIT l'image vivante à 1,0 alors que
  l'empilement vit à l'échelle mémoire 13-18 → le cœur entier sur une valeur
  unique, disque plat, pendant que le fichier borné gardait son dégradé) et le
  correctif `veralux.normaliser_lin()` (facteur GLOBAL, règle des sauvegardes
  linéaires, appliqué à `etirer()` et à la vue « tel que vu ») ; au passage,
  l'ancien `np.clip(out=img)` écrasait le tableau de l'appelant. Bancs : 64 dont
  `_test_coeur_crame_jalon64.py` (nouveau) ; non-régression rejouée (jalon1/2/3/5,
  jalon40, jalon63). Verdict annexe : cocher NLM ne dégrade PAS le cœur en vrai
  (contrairement à la mesure du banc sur image synthétique) → débruitage laissé
  tel quel. Sa **chaîne EXTERNE complète** (GraXpert + BXT + cases 7/8) VALIDÉE
  dans la foulée (« pour le moment »). Installateur 2.37.2 reconstruit ; les
  fichiers de diagnostic de la séance (dont la planche avant/après) ont été
  supprimés à sa demande — la preuve reste reproductible par le banc. Repli si
  régression : v2.37.1 (db0e870).

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
