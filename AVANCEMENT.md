# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---


- **PASSE EN COURS — AVAStack v2.38.4 : ASTRONOMÉTRIE SOUS LINUX (DONNÉES DITES
  ET TÉLÉCHARGEABLES)** (code + banc + doc + installateurs, 27/09/2026, **EN
  ATTENTE DE TON TEST**). Ton constat après l'installateur Linux : « l'astrométrie
  ne trouve pas de résultat… et ça échoue en silence ». **Cause trouvée et
  mesurée** :
  - `catalogues.dossier_catalogues()` ne cherchait que `%LOCALAPPDATA%\Siril`
    (Windows) et `~/.local/share/kstars` — le dossier Linux de Siril
    (`~/.local/share/siril`, doc Siril 1.4.4) n'était JAMAIS essayé, et le
    dossier KStars ne contient pas les `siril_cat*` du projet → repli sur un
    dossier AVAStack VIDE (rejoué ici : `dossier_catalogues()` = dossier de
    config vide) → échec certain du solveur interne, sans repli ASTAP (absent
    sous Linux) et sans trace (l'appli n'a pas de journal : la raison ne vivait
    que dans la ligne d'état).
  - **① chemins par OS** : `dossiers_siril()` (Linux/Windows/macOS, XDG honoré)
    et `dossier_catalogues()` réécrit (surcharge de config > dossier Siril
    utilisable > dossier de config AVAStack).
  - **② `chemin_catalogues` RÉELLEMENT honorée** (elle n'existait que dans une
    docstring) : ligne « Catalogues » dans la fenêtre Astrométrie — dossier
    utilisé, présence du catalogue, nombre de chunks spectro — + bouton 📂
    (dossier choisi et mémorisé).
  - **③ bouton « ⬇ Gaia »** : téléchargement du catalogue astrométrique
    (≈ 1,1 Go) dans le dossier affiché, en THREAD, reprise + sha256 (le
    téléchargeur existait mais n'était branché NULLE PART) ; progression et fin
    affichées, bouton neutralisé pendant le transfert.
  - **④ fin du silence** : `solveur.MSG_CATALOGUE_ABSENT` reconnu par
    `SuiviAstrometrie` → les essais S'ARRÊTENT (au lieu de 20 pour rien), la
    ligne dit « DONNÉES MANQUANTES — … » avec le dossier cherché, et les essais
    repartent TOUT SEULS dès qu'un catalogue apparaît.
  - **⑤ LISEZMOI** Windows/Linux : section « catalogue d'étoiles » (ce qui est
    requis, où le mettre, ce que font les boutons) ; README installateur ;
    CLAUDE.md (leçon).
  - Banc NEUF `_test_catalogues_jalon70.py` (24 vérifications : chemins par OS,
    surcharge de config, arrêt/reprise des essais, ligne « Catalogues » + 
    téléchargeur FACTICE). **Non-régression : 12 bancs rejoués, TOUS PASSENT**
    (catalogues jalon56, branchement astrométrie, photométrie, SPCC, config,
    UI ×2, BXT, chroma structure, zoom pleine rés, sauvegarde brute).
  - **Artéfacts RECONSTRUITS** : installateur Windows
    `avastack-setup-2.38.4.exe` et paquet Linux
    `avastack-setup-2.38.4-linux.tar.gz`. Repli si régression : v2.38.3.
  - Reste à faire : ton essai sous Linux (l'astrométrie doit maintenant DIRE
    « DONNÉES MANQUANTES » puis fonctionner après le téléchargement ou le
    dépôt du fichier).


  EST INSTALLÉ** (décision d'Alain, 27/09/2026 : « dossier bancs PARTOUT avec
  juste un thème à part pour les caméras ; seuls les bancs caméra seront dans
  les installateurs — le reste n'a rien à y faire, c'est pour du dev ») :
  - **109 bancs déplacés** par `git mv` (historique conservé) → `bancs/` : 93,
    `bancs/cameras/` : 16. Le thème caméra a été établi par le CONTENU, pas par
    le nom : les 5 bancs « composition » importent `MultiFolderCamera` et ne
    sont donc PAS caméra (piège évité).
  - **Bootstrap uniforme posé dans les 109** (5 lignes, juste après la
    docstring) : il remonte les dossiers parents jusqu'à celui qui porte
    `AVAStack.py` et l'ajoute à `sys.path` → le banc fonctionne depuis le dépôt
    (`bancs/`, `bancs/cameras/`) ET depuis le dossier d'installation. **9 anciens
    bootstraps supprimés** : 8 chemins absolus `c:\Astro\AstroLiveStack` (déjà
    faux hors de ta machine) et 1 `__file__.rsplit("\\")`.
  - **Installateurs** : `.iss` (109 lignes de bancs → UNE ligne) et packer Linux
    n'embarquent QUE `bancs/cameras/` (16 fichiers) ; le script Linux copie
    l'arbre `bancs/` du paquet (il listait encore les bancs à la racine du
    paquet — corrigé). Paquet Linux : 162 → **69 fichiers** (505 Kio).
  - **Doc** : LISEZMOI Windows et Linux réécrits (chemins `bancs\cameras\…`,
    autres bancs = outils de dev non installés) ; les **97 lignes d'usage des
    bancs** (« Usage : python _diag_xxx.py ») portent maintenant leur dossier
    réel (`python bancs/…`, `python bancs/cameras/…`), résolu banc par banc dans
    l'arbre ; CLAUDE.md : nouvelle section « Bancs et diagnostics —
    emplacement » (bootstrap, lancement depuis la racine, règle des
    installateurs) ; `installer/README.md` mis à jour.
  - **Vérifications faites** : `ast.parse` des 109 (OK) ; 3 bancs REJOUÉS depuis
    leur nouveau dossier et verts (`bancs/_test_veralux_jalon1.py`,
    `bancs/cameras/_test_qhy_camera.py` 33/33, `bancs/cameras/_test_capacites.py`
    29/29) ; un banc caméra rejoué depuis le PAQUET LINUX EXTRAIT (29/29) et
    `import avastack` depuis ce paquet (2.38.3) ; les deux installateurs
    reconstruits puis leur contenu contrôlé (16 bancs caméra, rien d'autre).
  - Reste à faire : ton essai de l'installateur Linux, et `--cameras` quand les
    `.so` constructeurs arriveront.

- **PASSE ANNEXE (27/09/2026, hors code applicatif) — INSTALLATEURS NOMMÉS AVEC
  LEUR VERSION, INSTALLATEUR LINUX SANS CAMÉRAS** :
  - **① nommage (demande d'Alain)** : tout artefact porte sa VERSION et la tire
    de `AVASTACK_VERSION` — `installer/windows/output/avastack-setup-2.38.3.exe`
    (l'`.iss` utilise `OutputBaseFilename=avastack-setup-{#AppVersion}` et REFUSE
    désormais de compiler sans `/DAppVersion` : plus de define de repli à
    maintenir, garde-fou TESTÉ) et
    `installer/linux/output/avastack-setup-2.38.3-linux.tar.gz`. Convention
    écrite dans CLAUDE.md (non négociable + registre des producteurs) et dans
    `installer/README.md`.
  - **② installateur LINUX — route ① tranchée par Alain** :
    `installer/linux/install_avastack.sh` : prérequis VÉRIFIÉS avant toute copie
    (`python3` ≥ 3.10, `python3-venv`/ensurepip, **`python3-tk`** — Tkinter
    n'existe pas sur pip — avec la commande exacte par distribution), copie dans
    `~/.local/share/AVAStack` (+ `VERSION.txt`), venv et dépendances via
    `installer/common/avastack_setup.py` (le MÊME outil que Windows), lanceur
    `lancer_avastack.sh` + `~/.local/bin/avastack` + entrée `.desktop`, puis
    vérification en interprétant réellement (Tkinter, numpy/OpenCV/Pillow avec
    rappel `libgl1`, astropy, état des caméras). Options : `--prefix`,
    `--cameras` (pour plus tard), `--sans-raccourci`, `--forcer`,
    `--desinstaller [--purger]`. Packer portable (stdlib, Windows/Linux/macOS) :
    `installer/linux/build_avastack.py` — il convertit en LF les `.sh`/`.txt`
    de l'archive (le dépôt Windows les écrit en CRLF, et un `.sh` en CRLF ne
    s'exécute pas sous Linux : piège réel, corrigé et consigné dans CLAUDE.md).
    **SANS CAMÉRAS** (demande d'Alain) : paquets `qhyccd`/`zwoasi` retirés de
    l'installation et aucun `*.so` embarqué (garde-fou dans le packer) → mode
    dossier / composition / OpenCV / simulé pleinement fonctionnel (imports
    caméra PARESSEUX, vérifié dans le code).
  - **③ reste à faire côté Linux** : essayer l'installateur sur une vraie machine
    Linux (pas exécutable ici : Windows sans bash ni WSL — contrôles faits à la
    lecture + inventaire de l'archive) ; puis `--cameras` quand les `.so`
    constructeurs seront récupérés (liste des fichiers attendus plus bas).
  - **④ ce lot est COMMITÉ et POUSSÉ** : `8b28e7f` (master, `origin/master`) —
    `installer/linux/install_avastack.sh` est enregistré en 0755 dans le dépôt
    (exécutable après un clone Linux). Aucun code applicatif touché : aucun
    impact sur la v2.38.3 en attente de test.


- **PASSE EN COURS — AVAStack v2.38.3 : PARAMÈTRES BXT EXPLICITES, TRAÇABILITÉ
  DES OUTILS EXTERNES, LISEZMOI** (code + banc livrés le 27/09/2026, **EN
  ATTENTE DE TON TEST** ; installateur 2.38.3 reconstruit). Les trois finitions
  demandées après ton essai BXT (`--sn 0.3`, « image magnifique ») :
  - **① commande BXT par défaut EXPLICITE** : `--ss 0.5 --ash -0.3 --sn 0.3`
    (`external/detection._BXT_OPTIONS`). « Ne rien passer » laissait le volet
    OBJETS à 0,50 (défaut du CLI) — MESURÉ : moucheté 2-8 px ×1,28 contre la vue
    live, ×0,48 avec 0,3. ⚠ ta commande MÉMORISÉE (config.json, `cmd_bxt`) reste
    prioritaire : ajoute `--sn 0.3` au champ pour en profiter.
  - **② traçabilité** : `App._entete_externe()` écrit maintenant, dans les
    fichiers issus du ⚡ (sortie LINÉAIRE **et** « tel que vu » de la vue
    traitée) : `AVAOUTIL`, `AVACMDGX`, `AVACMDDN`, `AVACMDBX` (commandes
    RÉELLES, options comprises → un fichier dit quel `--sn` l'a produit),
    `AVAAPPLI`, `AVAFRAME`, `AVAVUE`. La vue « empilement » garde son
    comportement (aucun mot-clé).
  - **③ LISEZMOI** de l'installateur : encadré « RÉGLAGES DE BXT ».
  - Banc NEUF `_test_bxt_entete_jalon69.py` (commande par défaut, en-tête depuis
    le job — complet / ancien / absent —, mots-clés RELUS par astropy, vue
    « empilement » toujours sans mot-clé). Non-régression : 12 bancs rejoués,
    TOUS PASSENT. Repli : v2.38.2.

- **PASSE PRÉCÉDENTE, VALIDÉE PAR LA MESURE — AVAStack v2.38.2 : LE RÉSULTAT DU
  ⚡ N'EST PLUS À L'ENVERS** (27/09/2026 ; **vérifié sur TON fichier** : le « tel
  que vu » du ⚡ en v2.38.2 est dans le BON SENS — +0,870 tel quel contre +0,309
  en miroir — alors que ceux des v2.373, v2.38.0 et v2.38.1 sont en miroir).
  Découvert en mesurant ton impression de
  « bruit bleu » (voir le bloc suivant) : tes deux « tel que vu » v2.38.1
  montraient le MÊME champ, mais **l'un retourné haut-bas** (corrélation +0,99
  en miroir contre +0,35 tel quel) — défaut présent depuis BXT (v2.373, v2.38.0,
  v2.38.1), qui touchait aussi l'ÉCRAN en vue « traitée ». CAUSE MESURÉE :
  `auto_unflip` comparait les images LINÉAIRES brutes (« 1 pixel sur N ») — sur
  tes fichiers, droite +0,1085 contre miroir +0,1212, écart +0,0127 < marge
  0,05 → aucune décision (le grain et la texture d'outil, non partagés,
  écrasent la mesure : rapport basses/hautes fréquences 0,25). CORRECTIF :
  comparaison sur images ÉTIRÉES + normalisées, sous-échantillonnage par MOYENNE
  (INTER_AREA), marge +0,20 → mesuré +0,539 contre +0,996, décision franche.
  Banc NEUF `_test_unflip_jalon69.py` (correction sur scène asymétrique, 4 cas
  SANS faux positif dont le miroir HORIZONTAL, tes vrais fichiers en témoin).
  Non-régression : 12 bancs rejoués, TOUS PASSENT. Repli : v2.38.1.

- **TON TEST DE LA v2.38.1 (27/09/2026) — « le fichier traité a plus de bruit
  bleu que le stack » : VÉRIFIÉ, MAIS PAS COMME ON LE CROIT** (mesuré sur le
  MÊME ciel — 84 blocs de fond communs —, `_diag_bleu_externe_jalon69.py`) : le
  **grain** bleu (1 px) est au contraire PLUS FAIBLE dans le fichier traité
  (×0,73 ; rouge ×0,65 ; luminance ×0,75), MAIS le **moucheté bleu 2-8 px est
  28 % PLUS FORT** (×1,28), son fond est **33 % plus clair** (0,259 → 0,343 :
  l'étirement est résolu séparément sur chaque image) et son bruit est « en
  plaques » (σ/MAD 2,95 contre 2,21) — signature d'un traitement IA (BXT
  `--ash -0.3` + débruitage GraXpert) que la réduction du bruit chromatique
  **épargne volontairement sur les structures** (correctif v2.37.5). Sujet à
  trancher (cf. « En attente »), rien n'est appliqué.

- **PASSE PRÉCÉDENTE — AVAStack v2.38.1 : LE RENDU PLEINE RÉSOLUTION VAUT AUSSI
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

- **Version stable VALIDÉE précédente : AVAStack v2.38.0** — l'anneau de couleur
  des étoiles dans les FICHIERS (fabriqué par la réduction du bruit chromatique,
  corrigé par un poids de structure en v2.37.5 : anneau mesuré 4,63 → 2,00), le
  fichier « tel que vu » qui ne correspondait pas à l'écran (fond cible non
  transmis au moteur : fond 0,197 contre 0,159, 9,6 niveaux d'écart) et l'écran
  capable de rendre la PLEINE RÉSOLUTION (option « Rendu pleine résolution »,
  coût ×4,3). Validé par Alain le 26/09/2026 (« C'est OK, on valide »),
  installateur 2.38.0 testé. Détails : changelog du source (v2.38.0, v2.37.5) et
  bancs `_test_zoom_pleine_res_jalon68.py`, `_test_chroma_structure_jalon67.py`.
  Repli si régression : v2.37.5 puis v2.37.4 (9927539).

  **JALONS 66 ET 65 (condensés)** : l'écart écran ⇄ fichier venait de la
  RÉSOLUTION (chaîne sur l'aperçu 1600 px, fichier en 3839 px : écart moyen
  0,015-0,023) et l'anneau de couleur était fabriqué par la chroma NR pleine
  résolution — d'où le rendu pleine résolution à l'écran (jalon 68) et le correctif
  par poids de structure (v2.37.5). Le halo des étoiles brillantes (R/B 1,30 →
  0,44) avait été réglé en v2.37.3 (flou du RAPPORT de couleur, rayon suivant la
  résolution), puis le curseur « Rayon de référence » en v2.37.4. Détails :
  changelog du source, `_diag_*jalon66.py`, `_test_chroma_halo_jalon65.py`.

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
- **Référence de mesure (v2.36.1, `_diag_empilement_couleur.py`)** : grain du fond
  ÷1,53 pour ×2,8 de poses (σ 0,000519 → 0,000338 à 41 → 115 frames) ; fond/σ
  ×1,44 ; fond NEUTRE (R/G 0,9998 · B/G 0,9999) ; **grain bleu B/G 1,17**, monté
  par les gains multiplicatifs de la SPCC (σ_B·K_B / σ_G·K_G = 0,891 × 1,318) —
  point de départ du grain bleu réglé en v2.37.0. Détail : changelog du source.
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

- **AUCUN DÉFAUT CONNU OUVERT** sur la v2.38.3 (livrée) ni sur la v2.38.2
  (vérifiée par la mesure). Sujets OUVERTS, par ordre d'intérêt :
  - **CLOS PAR LA v2.38.3 — MOUCHETÉ BLEU DU FICHIER TRAITÉ** (piste BXT d'Alain,
    27/09/2026) : mesuré ×1,27-1,31 PARTOUT dans le champ (donc pas « les
    structures » ; le grain fin était au contraire réduit), cause = le volet
    « objets » de BXT (`--sn`, défaut 0,50 tant que rien n'est passé — options du
    CLI installé v2.6.9) ; son essai `--sn 0.3` mesuré (moucheté ×0,37 sur la
    chaîne externe, ×0,48 face à la vue live, σ/MAD du bleu 2,95 → 1,49) est
    **livré par défaut** (`--ss 0.5 --ash -0.3 --sn 0.3`). Détails : changelog
    v2.38.3, `_diag_mouchete_structures_jalon69.py`, CLAUDE.md.
  - **CLOS PAR LA v2.38.3 — TRAÇABILITÉ DES OUTILS EXTERNES** : `AVAOUTIL`,
    `AVACMDGX`, `AVACMDDN` et `AVACMDBX` sont écrits dans les fichiers issus du ⚡
    (sortie linéaire ET « tel que vu » de la vue traitée). Reste possible (non
    demandé) : écrire aussi un en-tête sur le « tel que vu » de la vue
    « empilement ».
  - **INSTALLATEUR LINUX / macOS (demande d'Alain, 27/09/2026 : « il faudra
    regarder comment faire un installateur pour Linux … et comment avoir les
    prérequis, ce ne sera pas les dll »)** — étude FAITE (27/09/2026), route
    TRANCHÉE par Alain : ① **SCRIPT + venv** — IMPLÉMENTÉE le 27/09/2026 (bloc
    en tête de ce fichier : `installer/linux/install_avastack.sh` →
    `~/.local/share/AVAStack`, venv, `pip install -r requirements.txt`, lanceur
    + `.desktop`) ; ② paquet
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
- Leçons ÉCRITES le 27/09/2026 (accord d'Alain : « met a jour claude ») — section
  « Pièges », 5 entrées : ① « ne rien passer » à un CLI tiers n'est PAS neutre, et
  la source qui fait foi est le `--help` de l'outil INSTALLÉ (BXT `--sn` resté à
  0,50, responsable du moucheté) → écrire les paramètres explicitement ET les
  consigner dans le fichier ; ② comparer deux images LINÉAIRES non étirées rend
  une corrélation aveugle (`auto_unflip` : +0,1085 contre +0,1212 → miroir non
  corrigé pendant quatre versions) → normaliser et ÉTIRER avant de corréler,
  marge large (+0,20) ; ③ deux fichiers du même champ peuvent ne pas être
  superposés (le ⚡ part d'un instantané plus récent que les fichiers déjà
  enregistrés) → vérifier orientation et alignement, et FIGER l'empilement pour un
  A/B propre ; ④ localiser un défaut par ÉCHELLE (1-2 px grain, 2-8 px texture
  d'outil, 8-30 px plaques) et par classe de fond AVANT d'accuser un maillon ;
  ⑤ le rapport σ/MAD décrit l'ALLURE du bruit (1,5 = grain, 3 = plaques), à
  mesurer sur des blocs de fond COMMUNS aux deux images. AJOUTÉE aussi : la
  section « Portage Linux / macOS — prérequis et installateur » (prérequis
  système, règles udev, noms des `.so`, paquets pip par OS, piste INDI).
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

- 27/09/2026 (v2.38.2 puis v2.38.3) : SESSION « LE FICHIER DU ⚡ ÉTAIT À
  L'ENVERS, ET LE MOUCHETÉ BLEU VIENT DE BXT », **mesures validées par Alain**
  (« image magnifique avec -sn 0.3 ») : ① son test de la v2.38.1 (« le fichier
  traité a plus de bruit bleu que le stack ») MESURÉ — le grain est au contraire
  MEILLEUR (×0,73) mais le moucheté 2-8 px est ×1,28 ; ② en mesurant, découverte
  que le fichier du ⚡ était en **MIROIR VERTICAL** (v2.373, v2.38.0, v2.38.1),
  cause `auto_unflip` (corrélation aveugle sur images linéaires : +0,1085 contre
  +0,1212) → **v2.38.2** (comparaison étirée/normalisée, marge +0,20, banc
  `_test_unflip_jalon69.py`) — vérifié ensuite sur son fichier v2.38.2 (bon sens) ;
  ③ sa piste BXT confirmée : `--sn` (volet objets) restait au défaut 0,50 →
  son essai `--sn 0.3` mesuré (moucheté 2-8 px ×0,37, excursions 4,15 % → 0,72 %,
  σ/MAD 2,95 → 1,49) → **v2.38.3** (paramètres BXT explicites par défaut :
  `--ss 0.5 --ash -0.3 --sn 0.3` ; traçabilité `AVAOUTIL`/`AVACMDGX`/`AVACMDDN`/
  `AVACMDBX` dans les fichiers issus du ⚡ ; encadré LISEZMOI) ; ④ au passage :
  installateur Linux/macOS ÉTUDIÉ (prérequis, règles udev, noms des `.so`, piste
  INDI) et consigné dans AVANCEMENT + CLAUDE.md (5 leçons + la section portage) ;
  ⑤ son PNG est identique au FITS (écart max 1/65535, même sens, canaux dans le
  bon ordre). Repli si régression : v2.38.2.
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

- 25/09/2026 (v2.37.2, 5545a9c ; puis v2.37.1, db0e870) : DEUX SESSIONS VALIDÉES
  PAR ALAIN — « le cœur cramé » (CAUSE : l'étirement COUPAIT l'image vivante à 1,0
  alors que l'empilement vit à l'échelle mémoire 13-18 → cœur entier sur une seule
  valeur, disque plat ; correctif `veralux.normaliser_lin()`, facteur GLOBAL, règle
  des sauvegardes linéaires, appliqué à `etirer()` et à la vue « tel que vu » — au
  passage `np.clip(out=img)` écrasait le tableau de l'appelant) et « fond bleu →
  grain bleu → chaîne externe » (PNG/TIFF sans permutation R-B ; neutralisation de
  la couleur du fond avant étirement, défaut coché ; réduction du bruit
  chromatique opt-in, force = curseur « Couleur live » ; mesures SPCC/photométrie
  relançables en fin de stack ; cases couleur à rendu immédiat ; les deux
  corrections pré-étirement INTÉGRÉES à la chaîne EXTERNE, validée par lui dans la
  foulée). Bancs neufs `_test_coeur_crame_jalon64.py`, `_test_chroma_nr_jalon63.py`.
  Repli : v2.36.0 (5f91ae0).
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
