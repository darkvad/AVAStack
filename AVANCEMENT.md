# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---


- **PASSE EN COURS — AVAStack v2.38.1 : LE RENDU PLEINE RÉSOLUTION VAUT AUSSI
  POUR LA VUE « TRAITÉE »** (code + banc livrés le 27/09/2026, **EN ATTENTE DE
  TON TEST RÉEL** ; installateur 2.38.1 reconstruit). Demande d'Alain :
  « ok pour le rendu pleine résolution en vue traitée, je pensais que c'était
  évident de le faire ». Deux choses :
  - **DÉFAUT CORRIGÉ** : en vue « traitée », cocher l'option affichait
    l'EMPILEMENT au lieu du résultat du ⚡ (`_src_rendu` rendait
    `_stack_pleine_res` sans regarder la vue) ;
  - **NOUVELLE `App._src_pleine_res()`** : la source pleine résolution suit la
    VUE — empilement complet en vue « empilement », `proc_full` (résultat
    externe, DÉJÀ mémorisé pour les sauvegardes → aucun octet en plus) en vue
    « traitée » ; repli sur l'aperçu tant que l'image complète de la vue n'existe
    pas. Banc NEUF `_test_pleine_res_traitee_jalon69.py` (source par vue avec
    TÉMOIN qui discrimine, replis, ÉCRAN = FICHIER en vue traitée ÉCART 0 avec la
    VRAIE chaîne de sauvegarde, libellé d'aide) ; non-régression : 11 bancs
    rejoués, TOUS PASSENT. Repli si régression : v2.38.0.

- **Version stable VALIDÉE de référence : AVAStack v2.38.0** (`avastack/__init__.py`),
  branche `master` — **JALON 67/68 : L'ANNEAU DE COULEUR EST CORRIGÉ DANS LES
  FICHIERS, ET L'ÉCRAN PEUT MONTRER LA PLEINE RÉSOLUTION. VALIDÉ PAR ALAIN
  (26/09/2026 : « C'est OK, on valide »)** — installateur 2.38.0 installé et
  testé. Décision d'Alain à l'origine de la passe (26/09/2026, après l'enquête du
  jalon 66) : « b) et c), car sur l'écran je veux pouvoir zoomer sur l'image
  pleine résolution — ça aurait été ma prochaine demande ». Détail complet :
  changelog du source (v2.38.0, v2.37.5) et `## Clôtures précédentes` ci-dessous.
  Trois choses ont été faites dans la même passe :
  - **① LE CORRECTIF DE L'ANNEAU (v2.37.5)** — `couleurs._poids_structure` : la
    correction du flou de chroma est multipliée par 1/(1 + (|Y − flou(Y)|/(3 σ))⁶),
    qui vaut ~1 sur le FOND (écart ≈ 1 σ : 0,999) et ~0 sur une STRUCTURE
    (0,5 à 3 σ, 0,045 à 5 σ). MESURÉ sur son empilement réel : anneau des 4
    étoiles (R/G × le fond) **1,96 sans chroma → 4,63 (v2.37.4) → 2,00 (v2.37.5)** ;
    grain chromatique du fond toujours retiré à 76 % (×0,24 contre ×0,16) ; objet
    étendu : couleur préservée à 0,05 % ; luminance jamais réécrite. Banc NEUF
    `_test_chroma_structure_jalon67.py` (7 sections, TÉMOIN = la formule v2.37.4
    ré-écrite exprès pour prouver que le banc DISCRIMINE ; son fichier réel en
    [7], section sautée s'il est absent).
  - **② TROISIÈME CAUSE ÉCRAN ⇄ FICHIER, TROUVÉE ET CORRIGÉE (v2.38.0)** :
    `DisplayProcessor.rendu_pleine_resolution` ne transmettait le FOND CIBLE
    (`vl_target_bg`) que lorsque le logD restait à résoudre. Une fois le logD
    mémorisé (cas courant en live), l'étirement reprenait le défaut du module
    (0,20) au lieu du réglage d'Alain (0,16) : MESURÉ sur une image réelle, fond
    final **0,197 contre 0,159** — écart moyen **9,6 niveaux** de 8 bits (17 au
    pire). Le fichier était donc PLUS CLAIR que l'écran. Corrigé : écran et
    fichier coïncident maintenant AU BIT PRÈS (banc jalon 68 [3], écart 0).
  - **③ ZOOM SUR LA PLEINE RÉSOLUTION (v2.38.0)** : nouvelle case « Rendu pleine
    résolution (zoom fidèle) » (cadre « Affichage », DÉCOCHÉE par défaut,
    persistée `vl_pleine_res_ecran`). Cochée, la chaîne d'affichage tourne sur
    l'empilement COMPLET → l'écran montre ce que le fichier contiendra et le zoom
    recadre de VRAIS pixels (1:1 exact, libellé du zoom = échelle réelle en px
    image/px écran + mention PLEINE RÉSOLUTION). Coût mesuré 7,2-8,3 s contre
    1,7-1,9 s (×4,3) — d'où l'option ; décocher libère la copie (25 Mo) ; repli
    sur l'aperçu si aucun empilement complet (vue « traitée », début de session).
    `App._src_rendu` choisit la source ; l'état vit dans un attribut PYTHON
    (`pleine_res_ecran`) car les threads de travail ne peuvent PAS lire une
    variable Tk (`RuntimeError: main thread is not in main loop`, constatée et
    corrigée pendant la passe — la sauvegarde ne sortait plus). Banc NEUF
    `_test_zoom_pleine_res_jalon68.py` (option/persistance/libération, source de
    rendu, ÉCRAN = FICHIER écart 0, zoom 1:1 au bit près contre l'aperçu grossi —
    détail fin 8,73 contre 1,49 —, libellé).
  - **NON-RÉGRESSION : 32 bancs rejoués, TOUS PASSENT.** Trois mesures de
    `_test_chroma_nr_jalon63.py` et `_test_chroma_halo_jalon65.py` ont été
    adaptées, chacune documentée sur place (jamais affaiblie) : le grain est mesuré
    au MAD et non au σ (la correction étant devenue SÉLECTIVE, le σ est dominé par
    la queue des ~0,2 % de pixels protégés : ×0,092 contre ×0,027) ; le seuil du
    résidu de luminance passe de 2e-05 à 1e-04 (queue au CŒUR SATURÉ, B = 1,0000) ;
    et l'assertion sur le rayon non ramené est INVERSÉE (les ailes n'étant plus
    lissées, le rayon ne les déforme plus — c'est le but du correctif).
  - **VALIDÉ PAR ALAIN (26/09/2026) — « C'est OK, on valide »** : installateur
    2.38.0 installé et testé (étoiles des fichiers sans anneau de couleur ; zoom
    pleine résolution opérationnel). Prochaine session : voir
    `## En attente / prochaine session` (aucune urgence : aucun défaut connu ouvert
    sur cette passe). Repli si une régression apparaissait : v2.37.5, puis v2.37.4
    (9927539).

  **JALON 66 — RAPPEL CONDENSÉ (enquête, aucun code touché)** : le PNG n'était pas
  en cause (PNG ⇄ FITS identiques à 1/65535 près, moyenne 0,5 niveau) ; l'écart
  venait de la RÉSOLUTION (chaîne sur l'aperçu 1600 px à l'écran, sur les 3839 px
  pour le fichier : écart moyen 0,0147-0,0234, max 0,3728-0,4941) ; l'anneau était
  fabriqué par la chroma NR à pleine résolution (1,80 → 2,33/2,93/3,89 aux forces
  0,25/0,50/0,85, le rayon l'élargissant) ; coût de l'écran pleine résolution
  mesuré (1,7-1,9 s → 7,2-8,3 s, ×4,3). Détail complet : changelog du source,
  `_diag_*jalon66.py` (9 bancs + 2 planches) et `_diag_couts_jalon66.py`.

  **JALON 65 — RAPPEL CONDENSÉ** : halo de couleur des étoiles brillantes fabriqué
  par la chroma NR d'alors (étoile bleue R/B 1,30 → 0,44), corrigé en v2.37.3 en
  lissant le RAPPORT de couleur (échelle = min(luminance du pixel, sa version
  lissée)) puis en faisant SUIVRE la RÉSOLUTION au rayon (v2.37.3) ; curseur
  « Rayon de référence » 0,5-8 px ajouté en v2.37.4 (`vl_chroma_rayon_ref`).
  Verdict d'Alain : « on a plus le super halo de couleur, ca c'est bien ». Détail :
  changelog du source + `_test_chroma_halo_jalon65.py`.

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

- **AUCUN DÉFAUT CONNU OUVERT** sur la v2.38.0 (validée). Sujets OUVERTS, par ordre
  d'intérêt, à trancher par Alain quand il le souhaite :
  - **INSTALLATEUR LINUX / macOS (demande d'Alain, 27/09/2026 : « il faudra
    regarder comment faire un installateur pour Linux … et comment avoir les
    prérequis, ce ne sera pas les dll »)** — étude FAITE (27/09/2026), route à
    trancher par Alain : ① **SCRIPT + venv** (équivalent exact de l'installateur
    Windows : `installer/linux/install_avastack.sh` → `~/.local/share/AVAStack`,
    venv, `pip install -r requirements.txt`, lanceur + `.desktop`) ; ② paquet
    **.deb** (Debian/Ubuntu) ; ③ **AppImage** (un seul fichier, embarque
    Python+Tk) ; ④ **Flatpak** (sandbox → ouvrir l'accès USB des caméras).
    **PRÉREQUIS LINUX (ce ne sont PAS des DLL)** : `python3` ≥ 3.10,
    `python3-venv`, **`python3-tk`** (Tkinter n'existe PAS en pip), `libgl1` et
    `libglib2.0-0` (roues `opencv-python`), `libusb-1.0-0`, plus les
    **règles udev** des caméras (accès USB sans root). Les bibliothèques
    constructeurs deviennent `libASICamera2.so`, `libPlayerOneCamera.so`,
    `libtoupcam.so`, `libSVBCameraSDK.so` (Linux) / `*.dylib` (macOS) — le code
    les cherche DÉJÀ sous ces noms (`compat.ZWO_DLL_NAME`,
    `cameras.sdk_loader.nom_bibliotheque`), et l'installateur Windows les
    embarque : même mécanisme côté Linux. **QHY : rien à faire** (le paquet pip
    `qhyccd` 0.1.3 fournit des roues `cp310-abi3` manylinux_2_34 + Windows ; PAS
    de roue macOS en revanche). **Outils externes** : GraXpert existe en Linux
    (zip) et macOS (dmg) ; le CLI BlurXTerminator (rc-astro) existe pour
    Windows/macOS/**Linux**. **macOS** : Python de python.org (Tk inclus) ou
    `brew install python-tk@3.14`, puis bundle `.app` + signature/notarisation
    Apple pour éviter le blocage Gatekeeper.
    - **À FAIRE QUAND LES `.so` ARRIVENT** (décision d'Alain, 27/09/2026 :
      « on va attendre que je récupère les .so » ; ordre de priorité = le sien :
      QHY, Player One, ToupTek, SVBony, ZWO). Fichiers attendus par le code (il
      les cherche DÉJÀ sous ces noms, `cameras/sdk_loader.nom_bibliotheque`) :
      ① **QHY = RIEN à télécharger** (la roue pip `qhyccd` manylinux embarque
      déjà `libqhyccd.so` ; repli `AVASTACK_QHY_DIR`) ; ② **Player One** :
      `libPlayerOneCamera.so` + `99-player_one_astronomy.rules`, et
      **`libusb-1.0-0`** (dépendance du .so, documentée par Player One —
      `apt install libusb-1.0-0`), ou le paquet Debian/Ubuntu
      `libplayeronecamera2t64` ; ③ **ToupTek** : `libtoupcam.so` (variante x64,
      glibc ≥ 2.14) + les règles udev du SDK ; ④ **SVBony** :
      `libSVBCameraSDK.so` + ses règles ; ⑤ **ZWO** : `libASICamera2.so` +
      **`asi.rules`** (`sudo install asi.rules /etc/udev/rules.d`), vendor id
      `03c3`, déjà écrit dans le fichier fourni. Dépôt : RACINE du projet (ou
      sous-dossier `sdk/`, ou `AVASTACK_*_DIR`). L'installateur Linux copiera les
      `*.so`/`*.dylib` avec l'application et posera les `*.rules` dans
      `/lib/udev/rules.d/` (une seule fois, sudo) — `*.so`/`*.dylib`/`*.rules`
      ajoutés au `.gitignore` le 27/09/2026 (comme `*.dll`).
  - **PISTE INDI (question d'Alain, 27/09/2026 : « les softs astro Linux
    utilisent les drivers INDI, ça remplacerait les .so ? »)** — vérifié :
    NON, les pilotes INDI **embarquent/lient eux-mêmes** le SDK constructeur
    (le dépôt `indi-3rdparty` redistribue des binaires **fournis par les
    constructeurs** — `indi_asi_ccd`, `indi_qhy_ccd`, `indi_playerone_ccd`,
    `indi_toupbase` pour la famille ToupTek, pilote SVBony dédié) ; mais sur
    Debian/Ubuntu c'est le PAQUET INDI qui apporte les `.so` **et** les règles
    udev → pour Alain, aucun téléchargement manuel. LÀ où INDI change vraiment
    la donne : faire d'AVAStack un **CLIENT INDI** (socket 7624, XML + BLOBs
    FITS ; `indipyclient` = pur Python, pip, aucune bibliothèque constructeur) →
    plus AUCUN `.so` ni `zwoasi`/`qhyccd` côté appli, et **une seule route pour
    les trois OS** et toutes les marques (indiserver local ou distant, comme
    Ekos « remote »). À programmer comme un **jalon à part** (nouvelle source
    d'acquisition, capacités lues sur les propriétés INDI du pilote au lieu de
    `capacites.py`, test matériel réel) — **PAS avant** le portage Linux avec
    les `.so`, qui réutilise tout l'existant.
  - **Coût du rendu pleine résolution quand le débruitage NLM live est actif**
    (son réglage) : ~7-8 s par nouvelle frame (le NLM pleine résolution pèse
    3,9-4,1 s à lui seul). Pistes : ne le refaire que sur nouvelle frame (déjà le
    cas via les caches), ou un bouton « rendu pleine résolution » à la demande,
    ou suspendre pendant l'acquisition et rafraîchir à l'arrêt.
  - **Grain GRIS résiduel** : la réduction du bruit chromatique ne touche PAS le
    grain de luminance (mesuré ×1,00) — seul le débruitage live (NLM, force 0,5)
    ou plus d'intégration le réduit. Piste : débruiteur épargnant les étoiles
    (cf. CLAUDE.md).
  - **Curseur « Rayon de référence » (v2.37.4)** : depuis la v2.37.5 il agit
    surtout sur le FOND et les objets lisses (la couleur des étoiles n'est plus
    lissée du tout). Son choix sera persisté : aucun code à changer. Halos RÉELS
    restants → BXT (`--ash`, −0,3 … −0,5, absent de la commande par défaut).
  - **Vérifié pendant la clôture** : la chaîne EXTERNE ne porte AUCUN fond cible
    à elle (aucun `target_bg` dans `avastack/external` ni `avastack/processing`
    hors du module VeraLux) — elle passe par le même `rendu_pleine_resolution`,
    donc elle bénéficie du correctif de fidélité de la v2.38.0.
- **CLOS par la passe en cours (v2.38.1, en attente du test réel d'Alain)** : le
  rendu pleine résolution ne se limite plus à la vue « empilement » — la vue
  « traitée » a SA source pleine résolution (le résultat du ⚡), et le défaut
  d'affichage que ce manque cachait est corrigé ✔ (banc `_test_pleine_res_traitee_jalon69.py`).
- **CLOS par cette session** : anneau de couleur des étoiles dans les fichiers
  (corrigé et validé par Alain) ✔ ; zoom sur la pleine résolution (livré et
  validé) ✔ ; « le fichier correspond à l'écran » pour un étirement VeraLux
  (écart 0 mesuré au banc jalon 68) ✔ ; PNG ⇄ FITS (hors de cause, 1/65535 près) ✔.
- **CLOS par les sessions précédentes** : cœur de M31 VALIDÉ par Alain sur
  l'appli v2.37.2 (« Le cœur n'est effectivement plus cramé ni plat ») ✔ ;
  **chaîne EXTERNE complète VALIDÉE** par lui ✔ ; débruitage NLM essayé sans
  dégradation du cœur ✔ ; profils SPCC re-sélectionnés
  (« les filtres sont bons ») ✔ ; option « normalisation commune des canaux »
  UTILISÉE et mesurée sur ses deux empilements M31 ✔ ; fond bleu des PNG/FITS
  clos ✔ ; halo des étoiles brillantes du jalon 65 ✔.

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
- Leçons ÉCRITES le 26/09/2026 (accord d'Alain en clôture : « tu peux mettre à jour
  claude ») — section « Pièges », 4 entrées : ① **la couleur d'un pixel est un
  RAPPORT, pas un écart absolu** (le halo de couleur des étoiles venait de là) ;
  ② **toute échelle SPATIALE doit suivre la RÉSOLUTION** (aperçu ⇄ fichiers, avec
  le piège du plancher qui fausse un petit rayon) ; ③ **une correction en FIN de
  chaîne externe est invisible à l'outil qui la précède** (et l'option DÉDIÉE d'un
  outil doit être vérifiée — `--ash` de BXT, `0,00` par défaut — de même que ses
  sorties : miroir vertical, recadrage dans [0,1]) ; ④ **ré-énoncer honnêtement la
  propriété d'un banc quand la formule change**, mesurer une fidélité PAR RAPPORT
  à son plancher de mesure, et embarquer un TÉMOIN dans un banc qui doit prouver
  qu'il discrimine.
- Leçons ÉCRITES le 26/09/2026 (2ᵉ passe, accord d'Alain en clôture : « Oui,
  ajoute les 5 entrées ») — section « Pièges », 5 entrées : ① **une variable
  Tkinter ne peut être LUE que depuis le thread d'interface** (l'état partagé vit
  dans un attribut Python ; constat : la sauvegarde ne sortait plus) ; ② **après un
  traitement SÉLECTIF, un σ mesure la queue et non le niveau** → mesurer au MAD
  (deux bancs donnaient un faux échec) ; ③ **une scène de banc doit reproduire le
  MÉCANISME du défaut** (une étoile écrêtée à 1,0 = cœur blanc = aucun anneau, le
  témoin ne discriminait rien) ; ④ **les diagnostics du moteur VeraLux en logD
  imposé affichent une ancre 0,000000 : artefact** (et la comparaison bit à bit
  exige le même `target_bg`) ; ⑤ **une option « l'écran = le fichier » doit être
  verrouillée par une égalité exigée, pas une tolérance** — c'est cette assertion
  qui a révélé le fond cible non transmis. Reste EN ATTENTE (25/09/2026) : la
  parité des corrections pré-étirement entre chaîne LIVE et chaîne EXTERNE.

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

- 26/09/2026 (v2.38.0, ce54c55) : SESSION « ANNEAU DE COULEUR CORRIGÉ ET
  ZOOM PLEINE RÉSOLUTION », **VALIDÉE PAR ALAIN (« C'est OK, on valide »)** —
  installateur 2.38.0 installé et testé le jour même. Livré, sur sa décision
  (« b) et c), car sur l'écran je veux pouvoir zoomer sur l'image pleine
  résolution ») : ① l'enquête du
  jalon 66 (PNG hors de cause ; écart écran ⇄ fichier dû à la RÉSOLUTION ; anneau
  fabriqué par la chroma NR) ; ② le CORRECTIF par POIDS DE STRUCTURE
  (`couleurs._poids_structure`, v2.37.5 : la correction est éteinte là où la
  luminance s'écarte de son voisinage lissé) — anneau 4,63 → 2,00 sur son
  empilement, grain coloré du fond encore retiré à 76 % ; ③ une TROISIÈME cause
  écran ⇄ fichier trouvée et corrigée : `rendu_pleine_resolution` ne transmettait
  pas le FOND CIBLE au moteur quand le logD était déjà résolu (fichier rendu avec
  0,20 au lieu de 0,16 : fond final 0,197 contre 0,159, écart moyen 9,6 niveaux) ;
  ④ l'option « Rendu pleine résolution (zoom fidèle) » : la chaîne d'affichage
  tourne sur l'empilement COMPLET, l'écran montre ce que le fichier contiendra et
  le zoom recadre de vrais pixels (1:1 ; coût ×4,3 mesuré, décocher libère la
  copie). Bancs : `_test_chroma_structure_jalon67.py` et
  `_test_zoom_pleine_res_jalon68.py` (NOUVEAUX) ; 32 bancs rejoués, TOUS PASSENT.
  Trois mesures de bancs 63/65 adaptées et documentées (grain au MAD, seuil du
  résidu de luminance, assertion du rayon inversée). Piège : une variable Tk lue
  depuis un thread de travail lève `RuntimeError: main thread is not in main loop`
  — corrigé pendant la passe (l'état vit dans un attribut Python). **5 leçons
  écrites dans CLAUDE.md** (accord d'Alain en clôture). Installateur 2.38.0
  reconstruit. Repli si régression : v2.37.5, puis v2.37.4 (9927539).

- 26/09/2026 (v2.37.4, 9927539) : SESSION « LE HALO DE COULEUR DES ÉTOILES »,
  VALIDÉE PAR ALAIN (« on a plus le super halo de couleur, ça c'est bien » ;
  essais du curseur de rayon OK). Livré : ① la CAUSE — la réduction de bruit
  chromatique (v2.37.0) lissait une chroma ABSOLUE, donc autour d'une étoile le
  flou mélangeait la couleur du cœur avec celle du ciel et la déposait sur les
  ailes faibles (mesuré sur son M31 : R/B d'une couronne 1,30 → 0,44 sur une
  étoile bleue, R −51 %, B +44 %), et le correctif qui lisse désormais le RAPPORT
  de couleur (échelle = min(luminance du pixel, sa version lissée)) ; ② le RAYON
  qui SUIT LA RÉSOLUTION (`couleurs.rayon_chroma_apercu` +
  `DisplayProcessor.vl_chroma_rayon`) — l'aperçu montrait un halo 2,4× plus large
  que les fichiers ; ③ le CURSEUR « Rayon de référence » (0,5 à 8 px, v2.37.4,
  à sa demande pour ses essais en visu), transporté jusqu'à la chaîne EXTERNE
  (job 14 → 15 éléments) et persistant (`vl_chroma_rayon_ref`). Effets mesurés :
  grain coloré du fond ×0,17 (bénéfice conservé), écart RENDU du halo ≤ 1,9 point
  de % du pic contre 24,5 avant. Bancs : `_test_chroma_halo_jalon65.py` (NOUVEAU,
  avec TÉMOIN de l'ancienne formule pour prouver qu'il discrimine) +
  `_test_chroma_nr_jalon63.py` (borne haute documentée) + `_test_dn_jalon7.py`
  (job 15 éléments) ; 19 bancs rejoués, TOUS PASSENT. Installateur 2.37.4
  reconstruit (le banc est ajouté au .iss). Constats annexes : BXT rend ses
  sorties en MIROIR VERTICAL et recadrées dans [0,1], et son réglage de halos
  `--ash` vaut 0,00 par défaut (donc inactif) — laissé à Alain pour les halos
  RÉELS. Leçons de méthode ÉCRITES dans CLAUDE.md (4 entrées, accord d'Alain).
  Repli si régression : v2.37.2 (5545a9c).

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
