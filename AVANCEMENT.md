# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---


- **CHANTIER PERFORMANCE ET RÉACTIVITÉ (jalon 79, EN COURS) — décisions d'Alain
  du 29/09/2026.** But : le live plus rapide **sans qu'un seul pixel change.**
  Ordre tranché par Alain : **A (instrument) → C-bis (réactivité des réglages
  d'après-étirement) → B (cœur d'empilement)**, C (chaîne d'images) plus tard ;
  **B4 garde les maths EXACTEMENT telles quelles** (médiane = moyenne des 2
  valeurs centrales, MAD exact : seuls le tampon, la mise en place et le
  parallélisme changent). GPU **clos** : mesuré, l'iGPU Intel partage la même
  mémoire (2× au mieux, transfert compris) et la RTX n'est pas sur cette
  machine.
  - **① ÉTAPE A FAITE ET VALIDÉE (29/09/2026)** — banc NEUF
    `bancs/_bench_performance.py` + référence machine
    `bancs/_bench_performance_ref.json` (portable de dev). Il chronomètre
    24 étapes du pipeline sur une séquence SYNTHÉTIQUE déterministe de 8,4 Mpx
    (la taille de ta brute ; `--reel <dossier>` ajoute une vraie image de ton
    dossier de test) : empilement kappa et winsorized, moyenne, composite HOO,
    alignement ORB et triangles, étoiles/seeing, redimensionnement, chaîne
    d'affichage (STF, gamma, saturation), les deux histogrammes. **Surtout, il
    VÉRIFIE l'empilement** : les deux accumulations (kappa et winsorized, rejeu
    du warmup compris) sont comparées à une réimplémentation numpy ÉCRITE DANS
    LE BANC → **trois contrôles passent à l'écart ZÉRO** (moyennes identiques
    au bit, rejets identiques). C'est ce garde-fou qui autorise à optimiser.
  - **② LE BANC A DÛ ÊTRE ÉTALONNÉ — leçon à retenir : deux runs STRICTEMENT
    identiques différaient de 10 à 20 %** (le premier, machine au repos, est le
    plus rapide). D'où : mesures retenues au **MINIMUM** de N itérations (4 pour
    les étapes lourdes, 10-20 pour les légères), écarts **NORMALISÉS par une
    calibration machine** prise au début ET à la fin, et seuil d'alerte à
    **25 %** (à 15 %, un run à blanc faisait crier six fausses « régressions »).
    Contrôle repassé : « = » partout, ±10 %.
  - **③ CE QU'IL DIT DÉJÀ (machine au repos, 8,4 Mpx) : `add` kappa 349 ms
    installé (80 ms en warmup), `add` winsorized 1 836 ms, `mean` 59 ms, add
    RGB 990 ms, composite HOO 326 ms, alignement ORB 414 ms / triangles 48 ms,
    étoiles 28 ms (pleine rés.) et 15 ms (aperçu), aperçu d'affichage 72 ms
    (STF RVB) / 113 ms (gamma) / 147 ms (saturation) / histogrammes 34 ms,
    VeraLux 189 ms.** Diagnostic (mesuré, prototype à l'appui) : le coût n'est
    pas dans les maths mais dans les **temporaires float64** (~15 tableaux de
    67 Mo par frame) et dans l'absence de parallélisme (numpy est mono-thread :
    4 fils sur des bandes de lignes donnent ×3,3 sur un simple `a + a`) ;
    prototype `add` kappa préalloué/float32/4 fils : **325 → 51 ms, bit à bit
    identique**.
  - **④ ÉTAPE C-BIS FAITE ET VALIDÉE (29/09/2026)** — gamma, saturation globale
    et saturation par couleur ne recalculent plus RIEN pour rien (`hist=False`,
    même règle que les barres de niveaux depuis le jalon 75) et l'étirement
    lui-même est MÉMOÏSÉ (`DisplayProcessor._moteur_stf`) : **geste gamma
    103 → 41 ms, saturation 147 → 74 ms, geste mono 29 → 3 ms, et 137 → 28 ms
    mesurés dans l'interface réelle**. `_auto_params` ne calcule plus
    `_calc_stats` en `live=False` (son résultat était JETÉ). Témoin inversé
    vérifié : un réglage qui change vraiment la donnée (« Coupure du bruit »)
    recalcule toujours les histogrammes. Banc NEUF
    `bancs/_test_perf_reactivite_jalon79.py` (18 vérifications, interface
    réelle) + **11 bancs d'affichage rejoués verts**, dont « l'écran = le
    fichier » AU BIT du jalon 68. Version passée à **v2.43.0** (changelog
    détaillé dans `avastack/__init__.py`).
  - **⑤ ÉTAPE B FAITE ET VALIDÉE (29/09/2026) — LE CŒUR D'EMPILEMENT.** `add`
    ne crée plus de tableaux temporaires (ils étaient jetés à chaque frame :
    c'était l'essentiel des 325 ms du warmup) : tampons préalloués, opérations
    en place, élémentaire en float32, **carrés et seuil de rejet en float64**
    (le produit de deux float32 y est exact → `sumsq` et la décision de rejet
    restent **bit à bit** ceux d'avant), travail réparti par **bandes de
    lignes** (4 fils au plus ; une seule bande sous 1,5 Mpx, donc les bancs
    restent séquentiels). **MESURÉ (mono 8,4 Mpx) : add kappa 295 → 56 ms
    (−81 %), warmup 80 → 14 ms, RGB 938 → 181 ms, winsorized 1 666 → 570 ms
    (−66 %)** ; contrôles à **écart ZÉRO** (moyennes au bit, rejets identiques :
    517 906 et 2 257 140). **55 bancs rejoués verts**, dont le jalon 6 qui exige
    `array_equal(sum/wsum)` avec l'ancien algorithme. Prix dit : les tampons
    sont persistants (+240 Mo en mono, +725 Mo en RGB par stacker, libérés par
    `reset()`). Changelog détaillé dans `avastack/__init__.py`.
  - **⑥ INSTALLATEURS v2.43.0 RECONSTRUITS (29/09/2026, à la charge de l'agent
    avant tout essai réel)** — les trois, mêmes sources que le code testé :
    `avastack-setup-2.43.0.exe` (11 492 708 o, SHA-256 `FF3565BE…8457B4`),
    `avastack-setup-2.43.0-linux.tar.gz` (589 243 o, `392E6AD9…BCDE2C`),
    `avastack-setup-2.43.0-macos.tar.gz` (586 837 o, `B3ECD82E…EB08BB9`). Le
    `.gitignore` a été complété : le dossier de sortie **macOS** n'était pas
    ignoré (le paquet apparaissait comme « non suivi ») — c'est réparé, et les
    artefacts ne partent jamais dans le dépôt. **Aucun tag, aucune release :
    la v2.43.0 n'est pas publiée** (elle attend ton essai réel).
  - **⑦ PROCHAINE ÉTAPE — RIEN À CODER EN ATTENTE DE TA PAROLE : TU ESSAIES EN
    RÉEL** (session live : fluidité, gestes gamma/saturation, empilement
    identique à avant). Ce qui resterait à optimiser, si tu le veux (mesuré,
    non fait) : `composite_mean_avec_canaux` 296 ms (percentiles par rôle),
    `mean()` 44 ms, chemin ORB 377 ms (les triangles, 39 ms, restent le chemin
    recommandé), winsorized 570 ms (mur du médian), geste de saturation 74 ms.


- **PASSE DE CLÔTURE (29/09/2026, soir) — v2.42.0 : INSTALLATEUR macOS, TES
  VALIDATIONS CONSIGNÉES ET LEÇONS REMONTÉES.** Trois choses, sans toucher au
  code de l'application (donc **même version 2.42.0**) :
  - **① INSTALLATEUR macOS (jalon 78)** — `installer/macos/` (script
    `install_avastack.sh` + packer `build_avastack.py`) : app + venv dans
    `~/Library/Application Support/AVAStack/app`, lanceur `~/.local/bin/avastack`,
    **bundle `.app` minimal** (Info.plist + lanceur, donc **pas de Python
    embarqué**). Prérequis dit et testé : un Python **avec Tkinter**. **ÉTAT
    DATÉ : écrit, vérifié par le banc `_test_installeur_macos_jalon78.py` et par
    l'exécution réelle de ses garde-fous, mais PAS ENCORE EXÉCUTÉ SUR UN MAC.**
  - **② TES VALIDATIONS** — le **point 2 est TESTÉ ET VALIDÉ par ton essai**
    (« Réinitialiser l'empilement » puis nouvelle cible en mode dossier : le
    bloc « EN ATTENTE » de la v2.41.0 est donc clos et peut être supprimé) ; le
    **point 1 (les boutons de données sans Siril) n'est PAS testable chez toi** —
    tu n'as pas de configuration sans Siril : le test est **délégué aux
    utilisateurs** qui voudront bien l'essayer (c'est écrit dans la doc comme un
    état daté, pas comme une promesse).
  - **③ LEÇONS REMONTÉES DANS CLAUDE.md** (ton accord explicite : « tu peux
    remonter les leçons dans claude.md ») : les **quatre leçons du jalon 77**
    sont écrites dans la section « Pièges » (deux conventions de `progression`
    dans `telechargeur.py` ; un banc qui isole l'environnement doit basculer les
    constantes d'OS ; un audit de géométrie doit ignorer les parents de taille
    0/1 px ; une donnée téléchargeable doit devenir utilisable dans la même
    session) ; la section « Portage Linux / macOS » décrit l'installateur macOS
    et la route commune aux deux packers.
  - **RELEASE v2.42.0 COMPLÉTÉE (29/09/2026, soir)** : le paquet macOS a été
    **AJOUTÉ** (aucun écrasement) à la release déjà publiée, et son
    `INSTALLATION.md` **réédité** (§ 1 avec la 3e ligne, **nouveau § 3 bis
    macOS**). État final vérifié sur l'API : 4 pièces — `avastack-setup-2.42.0.exe`
    (11 485 284 o), `avastack-setup-2.42.0-linux.tar.gz` (582 385 o),
    `avastack-setup-2.42.0-macos.tar.gz` (580 015 o,
    SHA-256 `8F070116B4744BA8AE75DD8A6170604ADE5A8E69C3B58C0CFEE141D738CDAA23`) et
    `INSTALLATION.md` (18 467 o) ; notes réécrites (résumé « sans Siril **et un
    installateur macOS** » + doc, 20 295 octets, UTF-8 intact). Commits de la
    passe : `4ec3ccd` (installateur macOS + banc 78 + leçons dans CLAUDE.md +
    docs) puis le commit de clôture mémoire — **arbre propre**, `master = origin`.

- **PASSE PRÉCÉDENTE (29/09/2026, matin) — AVAStack v2.42.0 : AVAStack SANS SIRIL
  — LES SPECTRES GAIA XP ET LA BASE DE PROFILS SPCC SE TÉLÉCHARGENT DEPUIS
  L'INTERFACE.** Ta question : « si tu traites ce point
  (bouton pour les 48 morceaux de spectres Gaia XP), AVAStack pourra fonctionner
  sans Siril, y compris pour l'astrométrie et les capteurs et filtres SPCC ? »
  **Jalon 77.** Réponse mesurée : **NON, ce point SEUL ne suffisait pas** — il
  manquait DEUX jeux de données (les spectres Gaia XP **et** la base de profils
  SPCC), et la passe les prend tous les deux :
  - **① SPECTRES GAIA XP** : la fonction de téléchargement existait
    (`telecharger_chunk_xpsamp`) mais n'était branchée à **AUCUNE** interface, et
    elle ne savait prendre qu'**un** morceau sans savoir lequel. Deux boutons :
    **« ⬇ Spectres (champ) »** ne prend QUE les 1 à 4 morceaux qui couvrent la
    cible (AD/Dec/champ° **saisis**, mêmes règles que l'astrométrie ; calcul par
    la géométrie HEALpix du projet, `pixels_cone` → `pixel_vers_chunk`) —
    **≈ 100-300 Mo au lieu des 10,6 Go** — et **« ⬇ les 48 »** couvre tout le
    ciel (usage itinérant). sha256 de Zenodo vérifiée **morceau par morceau**,
    reprise (Range/206) après coupure, jamais de re-téléchargement d'un fichier
    conforme.
  - **② BASE DE PROFILS SPCC** : elle n'était **LUE que chez Siril**
    (`%LOCALAPPDATA%\siril-spcc-database`) — la SPCC exigeait donc Siril installé
    ET une calibration lancée une fois. Bouton **« ⬇ Base SPCC »** : archive ZIP
    du dépôt public `siril-spcc-database` (GPLv3 ; API GitLab, sans compte et
    **sans nom de branche figé** dans le code — vérifié : 200, application/zip),
    ZIP vérifié (lisible, taille bornée, entrée piégée `../` **refusée**) puis
    extrait dans un dossier **temporaire**, et seules les cinq catégories lues
    (`mono_sensors`, `mono_filters`, `osc_sensors`, `osc_filters`, `wb_refs`) +
    les .json de référence sont posées : ce qui n'est pas une base n'entre pas.
    Base complète = rien à retélécharger ; archive incomplète = **refusée**
    (aucun profil à moitié posé).
  - **③ OÙ EST LA BASE** : `spcc_db.dossier_base()` suit désormais dossier choisi
    (`chemin_spcc`, bouton **📂 Dossier SPCC**) → copie d'AVAStack
    (`<config>/spcc-database`, cible du bouton) → emplacements de Siril par OS
    (ordre d'origine conservé : aucun utilisateur de Siril ne perd sa base). Un
    dossier VIDE ne masque jamais une base utilisable ailleurs.
  - **④ LA SPCC EST UTILISABLE DANS LA SESSION** : à la fin du transfert, la case
    SPCC redevient **cochable**, ses **cinq listes sont remplies** et sa sélection
    et sa sélection par défaut posée — sans ce renfort, une base téléchargée
    n'aurait servi à rien avant un redémarrage (vérifié au banc, c'est un des
    points testés).
  - **⑤ MISE EN PAGE** (règle v2.38.9) : **deux lignes de deux boutons** (jamais
    trois sur une ligne : `pack` abandonne en silence), une ligne d'état
    « Base SPCC » **bornée** (`wraplength`) qui DIT le dossier et le contenu, et
    les **quatre** boutons entrent dans le contrôle de géométrie **nommé** du
    banc du jalon 72. Un **seul** transfert à la fois : les quatre boutons sont
    neutralisés ensemble (l'état affiché ne peut pas mentir).
  - **⑥ Banc NEUF `bancs/_test_sans_siril_jalon77.py`** — **sans réseau** (serveur
    HTTP local qui sert fichiers et archives factices) et **sans Siril** :
    champ → morceaux confrontés à une référence **indépendante**
    (astropy-healpix, niveau 8), reprise/206 après effacement, sha256 non
    conforme refusée, archive piégée et archive incomplète refusées, ordre des
    dossiers de la base, puis **UI réelle** (transferts suivis, messages, SPCC
    utilisable sans redémarrage, géométrie des quatre boutons avec textes
    longs). **Rejoués sans modification : jalons 70 (données astro), 72
    (géométrie), 56 (astrométrie/catalogues/photométrie), 58 et 58 bis (SPCC),
    71, 73, 75, 76 — tous verts.**
  - **PROCHAINE ÉTAPE : ton test en séance réelle** — un clic sur chaque bouton
    (les trois ⬇ et 📂 Dossier SPCC), idéalement sur une machine **où Siril n'est
    pas installé** : attendu = la ligne d'état qui annonce chaque téléchargement
    et sa fin, la case SPCC qui devient cochable **sans redémarrer**, et une SPCC
    calculée sans Siril. **Repli si régression : v2.41.0.**
  - **INSTALLATEURS RECONSTRUITS EN v2.42.0** (règle : toute passe qui touche
    plus d'un fichier → rebuild AVANT le test réel) :
    `installer/windows/output/avastack-setup-2.42.0.exe` (11 485 284 o,
    SHA-256 `848E770D…1905F`) et
    `installer/linux/output/avastack-setup-2.42.0-linux.tar.gz` (582 385 o,
    SHA-256 `7016471b…3e4c1`). **Aucune release publiée** pour cette passe (à
    faire sur ta demande, avec `gh release create --notes-file`).
  - **CLÔTURE DE LA PASSE (29/09/2026) — v2.42.0 PUBLIÉE** : `git push`
    (`b7cb76a..9fb8a71`, `master` synchronisé), **release GitHub `v2.42.0`**
    (`https://github.com/darkvad/AVAStack/releases/tag/v2.42.0`, tag `v2.42.0`
    sur le commit `9fb8a71` — présent en local ET sur `origin`, marquée
    « Latest ») avec **trois pièces** : `avastack-setup-2.42.0.exe`
    (11 485 284 o), `avastack-setup-2.42.0-linux.tar.gz` (582 385 o) et
    `INSTALLATION.md` (15 804 o). **Les notes de la release = un court résumé
    « ce qui change » suivi de la doc d'installation complète** (méthode
    `gh release create --notes-file`, **jamais** un message en ligne de commande :
    au-delà de ~1 000 caractères la ligne est tronquée sous Windows — le fichier
    de notes est fabriqué hors dépôt en UTF-8 sans BOM). Commits de la session :
    `d8ec4f5` (code + doc + banc), `cf65e8f` (mémoire), `9fb8a71`
    (INSTALLATION.md en v2.42.0 : artéfacts, tailles, SHA-256, repli v2.41.0) —
    **arbre propre**.
  - **TRAÇABILITÉ DU TAG — TON CHOIX (29/09/2026) : NE PAS DÉPLACER LE TAG.** Le
    tag `v2.42.0` reste sur le commit `9fb8a71` (code + doc de l'application) ;
    l'installateur macOS, ajouté après, vit dans les commits `4ec3ccd`/`ca59086`/
    `d4dbdbb` et la release publiée porte bien les **trois** paquets.
    **La prochaine évolution de code prendra donc la version `v2.43.0`** (règle
    écrite dans CLAUDE.md, section « Installateur et tests réels » : on ne
    réécrit JAMAIS un tag publié — c'est le prochain changement de code qui porte
    la version suivante). Conséquence pratique pour la prochaine passe : dès
    qu'un fichier de code change, bump `AVASTACK_VERSION` à **2.43.0** +
    changelog, rebuild des **trois** packers, release `v2.43.0`.


- **PASSE PRÉCÉDENTE (28/09/2026) — AVAStack v2.41.0 :
  « RÉINITIALISER L'EMPILEMENT » RÉINITIALISE VRAIMENT, ET LA SOURCE DE FICHIERS
  SUIT L'INTERFACE (enchaîner deux cibles en mode dossier).** Ton constat :
  « quand j'ai fini avec une cible, je ne peux pas enchaîner avec une autre en
  choisissant 1 ou des nouveaux dossiers et en cliquant sur Réinitialiser
  l'empilement — quand je clique sur Démarrer ça empile toujours la cible
  précédente », « il faudrait que le bouton réinitialiser réinitialise
  vraiment », et « quand c'est accessible, ce qui n'est pas toujours le cas ».
  **Jalon 76.** Quatre causes corrigées, plus un ajout demandé en séance :
  - **MESURE « AVANT » (témoin du banc, worktree sur HEAD, ton flux rejoué de bout
    en bout)** : après « Réinitialiser », l'empilement restait **ENTIER**
    (3 frames), l'écran gardait l'image de l'ancienne cible, et « ▶ Démarrer »
    **relisait le dossier de la cible PRÉCÉDENTE** (0 frame de la nouvelle) —
    avec **2 threads de worker** dès le premier démarrage, **3** ensuite.
  - **① Le bouton ne réinitialisait RIEN à l'arrêt** : le drapeau de remise à
    zéro n'était lu par le worker qu'en **TRAITANT une frame**. Il est servi en
    **tête de boucle** (donc **même en pause**) et emprunte le **chemin exact** de
    « ▶ Démarrer » (bloc partagé) ; la remise à zéro visible est faite côté
    interface → elle a lieu **même si le worker ne tourne pas**.
  - **② La source de fichiers gardait SON dossier** (et la mémoire des brutes
    déjà lues) : un autre dossier choisi dans l'interface n'était **jamais**
    ouvert. `_start` compare la source connectée à la configuration affichée et la
    **referme** si elle ne correspond plus (jamais une caméra SDK) → le prochain
    « ▶ Démarrer » la rouvre **sur le dossier affiché**. Le bouton referme aussi
    la source (une vraie remise à zéro repart des dossiers choisis), **vide
    l'écran** avec un message, rend « ▶ Démarrer » accessible et **dit ce qui sera
    lu**.
  - **③ UN SEUL worker** : `_start` lançait un **second** thread `_worker`
    inconditionnel (deux threads lisaient la même source et écrivaient le même
    empilement).
  - **④ PAUSE ≠ PERTE** : une source dossier était **lue pendant la pause puis
    jetée** (le fichier restait marqué « traité », donc jamais empilable — même
    après une nouvelle remise à zéro). Elle n'est plus lue en pause (le dossier
    est seulement **scanné** : « brutes en attente » reste juste) ; une caméra
    live, elle, continue d'être lue et jetée (c'est ce qui vide le SDK).
  - **⑤ Robustesse** : le worker **survit** à une source refermée (avant : mort
    **silencieuse** sur `None.read()`, plus aucune frame ensuite) ; « ▶ Démarrer »
    redevient **accessible** au changement de source non-SDK.
  - **⑥ INDICES D'ASTROMÉTRIE** (ta décision en séance : « oui, on réinitialise les
    indices si le dossier change ») : les AD/Dec/champ° de l'ancienne cible sont
    **effacés** quand le DOSSIER change — de fausses coordonnées feraient chercher
    le solveur à l'ancien endroit du ciel (et l'échec serait mis sur son compte).
    La saisie repart vide, ce qui rouvre la lecture d'en-tête des brutes du
    nouveau dossier, puis le repli ASTAP ; **dossier inchangé = indices
    conservés**, une caméra n'est jamais concernée, et la ligne d'état **dit**
    l'effacement. Nouveau `SuiviAstrometrie.effacer_indices` (distinct de
    `reset()`, qui CONSERVE les indices d'une session à l'autre).
  - **Banc NEUF `bancs/_test_reset_empilement_jalon76.py`** (7 sections, **worker
    réel + vraies brutes FITS sur disque**, témoin « avant » ci-dessus) :
    **TOUT PASSE**. **18 bancs rejoués verts** : 15, 16, 17, 18, 19 (worker, UI,
    compo), 20, 21, 42, 47, 53, 56 (astro, photométrie), 59, 69, 72, 75. Repli si
    régression : v2.40.0.
  - **MÉMOIRES (ta demande : « mets à jour claude avec ceci »)** : les 4 leçons du
    jalon sont **écrites dans CLAUDE.md** (section « Pièges », en tête) et
    **retirées** de « Pièges récents » ci-dessous (une seule place par leçon).
  - **Installateurs v2.41.0 reconstruits** (après l'ajout des indices) :
    `installer/windows/output/avastack-setup-2.41.0.exe` (11 468 655 o,
    SHA-256 `FC81DD44…53BA9`) et
    `installer/linux/output/avastack-setup-2.41.0-linux.tar.gz` (572 903 o,
    SHA-256 `16017928…55738`). `INSTALLATION.md` documente encore la release
    publiée v2.40.0 (c'est sa doc) — à mettre à jour seulement si tu publies une
    release v2.41.0.
  - **TEST RÉEL TOUJOURS EN ATTENTE (v2.41.0)** — fin de cible → choix du
    nouveau dossier → « Réinitialiser l'empilement » → « ▶ Démarrer » : l'écran
    doit se vider, la ligne d'état annoncer le nouveau dossier, les indices
    d'astrométrie repartir vides, et l'empilement ne contenir que la nouvelle
    cible.
  - **RELEASE ET CLÔTURE DE LA PASSE (28/09/2026)** — v2.41.0 **poussée et
    publiée** : **release GitHub `v2.41.0`**
    (`https://github.com/darkvad/AVAStack/releases/tag/v2.41.0`, tag sur le commit
    `4b7efe8`, présent en local et sur `origin`) avec les **DEUX** installateurs
    **+ `INSTALLATION.md`** (remis à jour en v2.41.0 : artefacts, tailles,
    SHA-256, repli v2.40.0) ; les **notes de la release** = court résumé « ce qui
    change » suivi de la doc d'installation (méthode `gh release create
    --notes-file`, jamais un message en ligne de commande : troncature au-delà de
    ~1 000 caractères). Commits de la session : `69d715e` (le correctif),
    `467d83b` (indices d'astrométrie + CLAUDE.md), `4b7efe8` (doc) — **arbre
    propre**, `master` synchronisé avec `origin`.
  - **CORRECTION DE DOC (29/09/2026, signalée par toi)** : « l'installateur Linux a
    été testé plusieurs fois sur ma config Ubuntu 26.04 LTS, contrairement à ce qui
    est dit dans la doc ». `INSTALLATION.md` (§ 3 « état de cet installateur », § 8
    limites) et `installer/README.md` (§ Tests) affirmaient **« pas encore exécuté
    sur une vraie machine Linux »** : **c'était FAUX** — corrigé partout (+ les
    dates/tailles des artefacts du README, restées en v2.38.3), et la **release
    `v2.41.0` a été remise à jour** : notes rééditées (`gh release edit
    --notes-file`) et `INSTALLATION.md` remplacé en pièce jointe (`gh release
    upload --clobber`, 14 930 o). **Aucun code touché** : version toujours 2.41.0,
    installateurs **non reconstruits** (SHA-256 inchangés).
  - **DÉPÔT PUBLIC + FIN DES CITATIONS NOMINATIVES (29/09/2026, à ta demande)** :
    le dépôt est **public** (licence MIT) et la consigne est de **ne plus te citer
    dans les publications** (« testé sur la machine d'Alain » est de trop). Fait :
    les trois mentions « dépôt **privé** » (`INSTALLATION.md` § 1, § 8, § 10) sont
    devenues « **public** (licence MIT) », et **12 citations nominatives** ont été
    neutralisées dans les documents publics — `INSTALLATION.md` (« exécuté sur une
    machine **Ubuntu 26.04 LTS** »), `installer/README.md`,
    `installer/linux/install_avastack.sh`, `installer/linux/build_avastack.py`,
    `installer/windows/avastack.iss`, `installer/windows/build_avastack.ps1`
    (« décision/consigne **de projet** », « par l'utilisateur »). Règle écrite
    dans **CLAUDE.md** (conventions) et entrée d'état faite dans « Portage Linux ».
    Les releases `v2.41.0` **et** `v2.40.0` ont été **rééditées** (notes +
    `INSTALLATION.md` joint) pour retirer la mention « privé » ; les **artefacts
    binaires ne sont PAS reconstruits** (seuls des commentaires ont changé — leurs
    SHA-256 restent ceux publiés).
  - **LICENCE ET README (29/09/2026, tes décisions)** : `LICENSE` porte désormais
    le titulaire **identifiant GitHub** (`darkvad`) — il affichait un prénom, et il
    était en **UTF-16** : réécrit en **UTF-8** (les diffs et les outils texte
    redeviennent lisibles, git le voyait comme binaire) ; et un **`README.md`** de
    présentation a été écrit à la racine (français, **aucun nom propre** :
    pipeline, sources d'images, installation, première séance, données
    Gaia/Siril, traçabilité des en-têtes, **78 bancs** de non-régression, limites,
    licence MIT + mention **GPL-3.0-or-later** du moteur VeraLux). **Les
    commentaires du code, des bancs et des mémoires gardent le style d'origine**
    (ta décision) : la règle de CLAUDE.md les excepte explicitement.

- **PASSE PRÉCÉDENTE (28/09/2026, soir) — AVAStack v2.40.0 : ASTROMÉTRIE SUR TA CAMÉRA
  OSC (NGC 7023 RÉSOLU) ET SPCC OUVERTE AU CAPTEUR COULEUR.** Tes deux constats
  du 28/09 sur tes brutes OSC (Uranus-C Pro, **mode dossier**, C8 @ 1280 mm →
  0,5005° / 0,4714″/px, caméra tournée à −94°) :
  « l'astrométrie ne trouve pas de résultat » et « la case SPCC dit que c'est
  que pour du mono multibande, alors que SPCC fonctionne en images couleurs
  dans Siril — il faut juste lui dire que c'est un capteur couleur et le
  choisir ». **Les deux sont fondés, les deux sont corrigés.**
  - **① ASTROMÉTRIE** : la zone de catalogue était un **RECTANGLE** — elle
    suppose que l'axe X de la caméra suit les AD (faux dès qu'on tourne la
    caméra) : **43 % des étoiles** étaient gardées en trop peu, **et une bande
    HORS image** était conservée ; de plus le plafond `N_CAT_MAX` tombait
    **avant** la sélection. Remplacés par le **DISQUE DU CHAMP RÉEL**
    (`masque_champ`, sans aucune marge) et un plafond appliqué **après**.
    **Mesuré sur TES brutes** (`bancs/_diag_osc_ngc7023.py`) : **NGC 7023
    résolu** (68-80 appariements, rms 0,43-0,46 px, **0,4716″/px contre
    0,4714″/px pour ASTAP**, robuste à des indices faux de ±0,2° et à un champ
    faux de ×0,8 à ×1,1), **M31 NON régressé** (`_test_solveur_reel_m31.py`).
  - **② SPCC COULEUR (OSC)** : la SPCC n'était câblée que pour le **mono
    multi-bandes** ; elle accepte désormais les **capteurs couleur** de la base
    Siril (trois canaux + **filtre LPF commun**), avec un **sélecteur « Type de
    capteur »** persisté (lignes G/B grisées en OSC, défaut « No filter ») et les
    gains par canal appliqués par le nouveau `LiveStacker.gains` (jamais sur
    l'empilement BRUT). **Banc NEUF `_test_spcc_osc.py`** : pentes **R/G 0,6999**
    et **B/G 1,2981** retrouvées pour des gains vrais de 0,70 / 1,30 ; chemin
    mono intact (`_test_spcc_jalon58.py` vert).
  - **TON VERDICT EN SÉANCE RÉELLE : « tout à l'air bon »** (session dossier OSC
    NGC 7023, ~40 brutes, 36 empilées, étoiles bien colorées). Les deux contrôles
    formels (étoile verte + ″/px ; en-tête `AVASPCC`) restent **à confirmer sur
    une trace écrite** quand tu voudras — la mécanique des deux est mesurée au
    banc.
  - **CLOS** : diag jetable retiré de la racine (`bancs/_diag_osc_ngc7023.py`
    conservé) ; **les DEUX installateurs v2.40.0 construits et publiés** dans la
    **première release GitHub** du dépôt (voir le bloc de clôture ci-dessous).

- **CLÔTURE DE SESSION PRÉCÉDENTE (28/09/2026, soir — 2ᵉ clôture du jour)** — v2.40.0 livrée,
  poussée et **publiée** : **release GitHub `v2.40.0`**, la **première du dépôt**
  (`https://github.com/darkvad/AVAStack/releases/tag/v2.40.0`, tag sur le commit
  `4314c6e`), avec les **DEUX** installateurs (Windows 11 463 956 o, Linux
  564 997 o) et **les RELEASE NOTES = la doc d'installation** `INSTALLATION.md`
  (259 lignes : les deux plateformes, la préparation des données Siril/Gaia —
  catalogue astrométrique, 48 morceaux de spectres, base de profils SPCC —, les
  caméras, la check-list de première séance, les limites de la version et le
  repli v2.38.11), ce même fichier étant **aussi joint en pièce**. Commits de la
  session : `28b123c` (code v2.40.0), `304948d`, `164f753`, `4314c6e` (doc +
  renvoi depuis `installer/README.md`), `3027c0e` (mémoire) — **arbre propre**,
  `master` synchronisé avec `origin`, tag `v2.40.0` présent en local et sur
  `origin`.
  - **Rappel de clôture (mis à jour le 29/09/2026)** : deux propositions t'ont
    été faites le 28/09 et tu les avais déclinées (« non, c'est bon ») — **le
    bouton « ⬇ spectres » des 48 morceaux Gaia XP a finalement été DEMANDÉ par
    toi le 29/09 et il est LIVRÉ en v2.42.0** (avec la base de profils SPCC,
    jalon 77 — voir le bloc en tête de fichier) ; reste disponible « sur ta
    demande » : **`INSTALLATION.md` embarqué dans les deux paquets** (cela impose
    de reconstruire les installateurs et donc de refaire les SHA-256 de la
    release).
  - **Aucune leçon durable en attente pour CLAUDE.md** : les deux pièges de la
    session sont consignés dans « Pièges récents » ci-dessous (workflow
    `gh release create` dont les notes SONT la doc ; **ligne de commande Windows
    tronquée au-delà d'environ 1 000 caractères** → message long = FICHIER), ce
    qui suffit à l'usage. À ne remonter vers CLAUDE.md que si tu le demandes.


- **PASSE PRÉCÉDENTE DU MÊME JOUR (28/09/2026, soir) — v2.39.0** : trois barres de
  niveaux sur l'histogramme (Noir / Médian / Blanc) agissant sur la **sortie du
  moteur**, ⏹/▶ gel-reprise de l'étirement auto (STF **et** VeraLux), bandes R/V/B,
  saturation par couleur, échelle y réglable. **VALIDÉE par ton essai réel
  (« points 1, 2 et 3 testés et validés »)** ; tes deux décisions : **la barre
  MÉDIAN et le curseur GAMMA restent tous les deux** (« on laisse comme c'est »)
  et **l'histogramme à deux bandes reste TEL QUEL** (176 px) — toutes deux
  consignées **dans le code** pour qu'un futur nettoyage ne retire rien. Repli si
  régression : v2.38.11. Commit `07b511b`. Quatre leçons durables écrites dans
  CLAUDE.md (barres APRÈS le moteur, saturation par TEINTE, panneau rafraîchi par
  les données, échelle d'axe muette). **Installateurs v2.39.0 non reconstruits**
  (à faire sur ta demande).

- **PASSES PRÉCÉDENTES DU MÊME JOUR (28/09/2026, nuit) — v2.38.9, v2.38.10,
  v2.38.11** : lignes à texte libre visibles (astrométrie, catalogues, re-stack),
  cadre « Fichiers de travail et journal » en tête, et surtout **le démarrage ne
  peut plus se BLOQUER** (mesures de disque différées et bornées, NAS
  injoignable DIT au lieu d'attendre). Résumé complet et commits : bloc de
  **CLÔTURE DE SESSION (28/09/2026)** ci-dessous ; détails : changelog de
  `avastack/__init__.py` + historique git.

- **PASSES ANTÉRIEURES (27/09/2026) — v2.38.7 et v2.38.8** : **si l'application
  ne démarre pas, elle le DIT** (`avastack/journal.py` : `journal.txt` en
  rotation, jamais d'exception ; journal ouvert AVANT les imports ; filet dans
  les deux points d'entrée ; `Tk.report_callback_exception` remplacé ; bouton
  « Journal » ; test de démarrage réel à l'installation) puis, en v2.38.8, les
  DEUX échecs de démarrage connus sont EXPLIQUÉS (session sans bureau, `tkinter`
  absent — conseil actionnable, jamais inventé). Ces deux passes sont résumées
  dans le bloc de CLÔTURE ci-dessous ; détails : changelog + git. **La panne du
  27/09 (v2.38.6 lancée par le menu) reste SANS EXPLICATION** : le journal
  n'existait pas, il n'en subsiste aucune trace — ne jamais attribuer de cause
  sans trace.

- **Jalons antérieurs immédiats** (détails dans le changelog de
  `avastack/__init__.py` et l'historique git) : **v2.38.6** espace disque (dossier
  de travail effectif + alerte tmpfs, écriture atomique `.part`, plafond
  `min(20 Go, 50 % du libre)`, fichiers de travail CONSERVÉS à l'échec — la cause
  était une écriture PARTIELLE de FITS sur un `/tmp` **tmpfs de 4,6 Go** :
  « Erreur : 24962352 requested and 10902832 written ») — ton essai restait EN
  ATTENTE, il est désormais couvert par l'essai de la v2.38.7 ; **v2.38.5**
  détection des outils externes (`GraXpert-linux` — casse sensible ! — ini de
  Siril, état ✔/⚠ affiché, re-détection qui CONSERVE les options) ✔ ; **v2.38.4**
  astrométrie Linux (dossiers Siril par OS, `chemin_catalogues` honorée, bouton
  ⬇ Gaia, « DONNÉES MANQUANTES » dit au lieu d'un silence) ✔.

- **CLÔTURE DE SESSION (28/09/2026)** — SIX passes livrées et poussées d'affilée
  sur `origin/master` (arbre propre) : **v2.38.7** (le démarrage ne peut
  plus être muet : journal + message + bouton « Journal »), **v2.38.8** (les
  échecs de démarrage CONNUS sont expliqués), **v2.38.9** (ligne « Fichiers de
  travail et journal » visible et bouton « Journal » réellement affiché),
  **v2.38.10** (les lignes à texte libre ne perdent plus rien : astrométrie,
  catalogues, re-stack), **v2.38.11** (**le démarrage ne peut plus se BLOQUER** :
  mesures différées + bornées, miettes de pain au journal) et **v2.39.0**
  (**histogramme à deux bandes + trois barres de niveaux** agissant sur la SORTIE
  du moteur, gel/reprise de l'auto en STF **et** VeraLux, saturation par couleur
  R/V/B, échelle y réglable). Commits (v2.38.7 → v2.38.11) : `bd04f20`,
  `59d07e3`, `07f0c34`, `6642c4a`, `c8ffcf6`, `1acd3f6`, `9a01674`, `15cb6b7`,
  `2ec4d67` ; plus le commit **v2.39.0** : **`07b511b`** (poussé).
  - **VALIDÉ par tes essais réels** : v2.38.7/2.38.8 (démarrage par le MENU et en
    terminal ✔, journal reçu ✔) ; v2.38.9/2.38.10 (vérification à l'écran ✔) ;
    **v2.38.11 : « c'est tout bon » — avec `nftables` ACTIF, l'application
    s'ouvre, le journal s'écrit, et le NAS injoignable est DIT au lieu de
    bloquer.** ; **v2.39.0 (28/09, soir) : « points 1, 2 et 3 testés et
    validés »** — la barre suit le doigt **empilement fini** (③), ⏹/▶ marche en
    STF **et** en VeraLux, les trois curseurs de saturation par couleur ne
    touchent que leur couleur (①) — et ta décision est tombée : **la barre
    MÉDIAN et le curseur GAMMA restent tous les deux** (consigné dans le code).
  - **LA PANNE DU 27/09 EST CLOSE** : tes dossiers de couches R/G/B sont sur le
    NAS ; `nftables` le filtre ; un `stat`/`listdir` sur ce montage attendait
    INDÉFINIMENT, et l'application le faisait AVANT d'afficher — et même avant sa
    première ligne de journal (donc panne muette). Ce n'était pas un bug mais des
    mesures de disque NON BORNÉES : elles le sont désormais (règle écrite dans
    CLAUDE.md, avec sa contre-épreuve : `App(root)` en 0,8 s malgré trois sondes
    qui dorment 30 s).
  - **Bancs** : 10 rejoués VERTS + 1 NEUF (`_test_demarrage_non_bloquant_jalon74`,
    17 vérifs) ; 3 RÉPARÉS (72 : dialog `showinfo` jamais intercepté — prouvé
    préexistant au `faulthandler` ; 70 et 71 : sondes devenues différées). Pour
    v2.39.0 : banc NEUF `_test_histo_jalon75.py` (**11 sections**) + **~45 bancs
    rejoués verts**, dont l'audit de géométrie du 72.
  - **Prochaine étape** : **RIEN en attente de ton côté** — les quatre essais qui
    restaient ouverts (`nftables`/NAS, chaîne BlurX avec le dossier de travail,
    rendu BXT `--sn 0.3`, `--cameras`) sont **VALIDÉS par toi le 28/09/2026** (cf.
    § « En attente / prochaine session »). Aucun point ouvert non plus sur
    v2.39.0 : **l'histogramme à deux bandes reste tel quel** (ta décision du
    28/09 — 176 px, le sélecteur « Sortie »/« Brut » rend la place quand on en a
    besoin). Une nouvelle session part donc d'une ardoise propre.
- **PASSES TERMINÉES ET POUSSÉES (27/09/2026, hors code applicatif) — BANCS
  RÉORGANISÉS, INSTALLATEURS NOMMÉS PAR VERSION, INSTALLATEUR LINUX** : 109
  bancs déplacés dans `bancs/` (`bancs/cameras/` : 16 — seuls installés) avec
  bootstrap uniforme ; `.iss` et packer Linux tirent le nom de l'artefact de
  `AVASTACK_VERSION` (compilation REFUSÉE sans `/DAppVersion`) ; installateur
  Linux `installer/linux/install_avastack.sh` (venv, prérequis vérifiés, SANS
  caméras par défaut, option `--cameras`). Détails durables : changelog de
  `avastack/__init__.py`, `installer/README.md`, section CLAUDE.md « Bancs et
  diagnostics — emplacement ». **`--cameras` : VALIDÉ par toi (28/09/2026)** —
  plus rien à faire de ce côté.

- **PASSE LIVRÉE ET VALIDÉE — AVAStack v2.38.3 : PARAMÈTRES BXT
  EXPLICITES, TRAÇABILITÉ DES OUTILS EXTERNES, LISEZMOI** (code + banc livrés le
  27/09/2026 ; installateur 2.38.3 reconstruit ; **essai BXT `--sn 0.3` validé par
  toi le 28/09/2026**). Les trois finitions demandées
  après ton essai BXT (`--sn 0.3`, « image magnifique ») :
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

- **Version stable VALIDÉE sur ta machine (27/09/2026) : AVAStack v2.38.5** —
  ton retour : « pour linux : astrométrie, spcc OK / GraXpert OK » (v2.38.4 et
  v2.38.5 confirmées par l'EFFET). BXT restait à confirmer — non par un défaut
  du code, mais par saturation de `/tmp` (traité en v2.38.6). Les successeurs
  immédiats à tester : v2.38.6.
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

- **ÉTAT COMPACT POUR UNE NOUVELLE SESSION (29/09/2026, clôture de soirée)** :
  **rien en attente de l'agent**. Dernière passe : **v2.42.0** — AVAStack ne
  dépend plus de Siril (spectres Gaia XP + base de profils SPCC téléchargeables,
  jalons 77) **et un installateur macOS existe** (jalon 78, écrit le 29/09/2026,
  **pas encore exécuté sur un Mac**). Release GitHub `v2.42.0` publiée (deux
  installateurs + la doc ; le paquet macOS y est ajouté). Le dépôt est **public**
  (licence MIT, titulaire = identifiant GitHub), un **`README.md`** de
  présentation existe à la racine, les documents publiés ne citent plus le
  mainteneur (règle écrite dans CLAUDE.md) et **les commentaires du
  code/garde-fous internes restent tels quels** (décision explicite). **Les deux
  tests réels restants ne sont pas chez toi** : voir les deux blocs ci-dessous.
- **DÉLÉGUÉ AUX UTILISATEURS (29/09/2026) — v2.42.0 : LES BOUTONS DE DONNÉES**
  (catalogues + spectres + base SPCC). **Ton retour : « les boutons sont là mais
  je n'ai aucune configuration sans Siril pour tester »** — normal : tes machines
  ont Siril, et c'est justement le cas « sans Siril » qu'il faut éprouver. À
  valider par quiconque a une machine **sans Siril** : ① « ⬇ Gaia » ;
  ② **« ⬇ Spectres (champ) »** avec AD/Dec/champ° saisis (attendu : la ligne
  d'état nomme les morceaux du champ, ≈ 100-300 Mo, et la ligne « Catalogues »
  passe à `n/48 morceaux`) ; ③ **« ⬇ les 48 »** (≈ 10,6 Go, reprise
  automatique) ; ④ **« ⬇ Base SPCC »** (quelques Mo) puis la **case SPCC** : elle
  doit devenir cochable **sans redémarrer** et ses listes se remplir. La
  mécanique est mesurée au banc (jalon 77) ; ce qui reste à voir, c'est le monde
  réel (réseau, dossiers, droits). Repli si régression : **installateur v2.41.0**.
- **VALIDÉ PAR TON ESSAI (29/09/2026) — v2.41.0 : bouton « RÉINITIALISER »**
  (release GitHub `v2.41.0`, tag `4b7efe8`). Tu as testé et validé : fin de cible
  → nouveau dossier → « Réinitialiser l'empilement » → « ▶ Démarrer » se comporte
  comme prévu (nouvelle cible uniquement). **Ce bloc est clos** — reste seulement,
  hérité des passes précédentes, à confirmer sur une trace écrite : l'étoile
  verte + le ″/px de l'astrométrie, et l'en-tête `AVASPCC` d'une sauvegarde.
- **NOUVEAU (28/09/2026, soir) — v2.40.0 : ASTROMÉTRIE SUR CAMÉRA TOURNÉE (OSC) ET
  SPCC COULEUR.** NGC 7023 **résolu sur tes brutes** (68-80 appariements, rms
  0,43-0,46 px, 0,4716″/px contre 0,4714″/px pour ASTAP), M31 non régressé ; la
  SPCC accepte un **capteur couleur (OSC)** avec son filtre LPF commun
  (`mode`, `reponses_osc`), et les gains par canal d'une source couleur passent
  par `LiveStacker.gains`. **Ton essai réel du 28/09 (soir) : « tout à l'air
  bon »** — session dossier OSC NGC 7023, ~40 brutes (détails en tête de
  fichier). Bancs NEUFS/rejoués : `_test_spcc_osc.py` (NEUF, 6 sections),
  `_test_spcc_jalon58.py`, `_test_solveur_reel_m31.py`, diag
  `bancs/_diag_osc_ngc7023.py` sur brutes réelles. **RELEASE GITHUB `v2.40.0`
  publiée** (`https://github.com/darkvad/AVAStack/releases/tag/v2.40.0`) : les
  **DEUX** installateurs (Windows 11 463 956 o, Linux 564 997 o) **ET** la
  nouvelle documentation `INSTALLATION.md` (installation rapide Windows/Linux,
  puis la préparation des données Siril/Gaia : catalogue astrométrique, 48
  morceaux de spectres, base de profils SPCC). Le dépôt étant **public** depuis
  le 29/09/2026, la release l'est aussi. L'installateur v2.39.0 n'a pas été
  construit (version dépassée) —
  **repli si régression : v2.38.11**. **CLÔTURE DU 28/09/2026 : rien en attente de
  ton côté** — les deux propositions de fin de session (bouton « ⬇ spectres » des
  48 morceaux Gaia XP, `INSTALLATION.md` embarqué dans les paquets) ont été
  **déclinées par toi** (« non, c'est bon ») : à ne pas reproposer spontanément.
- **PRÉCÉDENT (28/09/2026) — v2.39.0 VALIDÉE PAR TON ESSAI (« points 1, 2 et 3
  testés et validés »)** : les **trois barres de niveaux** de l'histogramme
  (Noir / Médian / Blanc), le **⏹/▶ geler-reprendre** de l'étirement auto (STF
  **et** VeraLux), le **sélecteur de bandes**, la **saturation par couleur R/V/B**
  et la **case « Échelle y linéaire (bande basse) »**. **Plus aucun point
  ouvert** : l'histogramme à deux bandes reste **tel quel** (ta décision du
  28/09, 176 px), et les quatre essais qui restaient en attente (`nftables`/NAS,
  chaîne BlurX, rendu BXT `--sn 0.3`, `--cameras`) sont **VALIDÉS par toi** — plus
  à reproposer. **Installateurs v2.39.0 non reconstruits** (à faire sur ta
  demande).
- **LEÇONS DU JALON 75 ÉCRITES DANS CLAUDE.md (28/09/2026, sur ta demande
  « mettre à jour les .md nécessaires (y compris claude) »)** — quatre leçons
  durables, section « Pièges (leçons du projet AVAStack) » : **① les barres de
  niveaux vivent APRÈS le moteur** (mini vs grand histogramme de SharpCap, et
  pourquoi : VeraLux n'a ni point noir ni point blanc → « les barres = les points
  de l'étirement » n'est possible que dans un seul moteur) ; **② une saturation
  par couleur doit viser une TEINTE** (la formule `c = Y + k·(c−Y)` change le
  canal PARTOUT et verdissait l'image quand on poussait « rouge ») ; **③ un
  panneau rafraîchi SEULEMENT par les données ne suit pas les gestes** (et la
  règle inverse : si le geste ne change pas la donnée, NE PAS recalculer —
  3,1 ms contre ~80 ms) ; **④ une échelle d'axe muette est un piège** (mesures
  log/linéaire consignées). Plus une note opérationnelle : les bancs se lancent
  avec l'interpréteur du VENV (`python` seul, sur ta machine, n'a pas numpy).
- **AUCUN DÉFAUT CONNU OUVERT** sur les v2.38.3 à v2.40.0 (livrées).
  **CONFIRMÉ PAR TES ESSAIS RÉELS (27-28/09/2026, Linux)** : astrométrie ✔, SPCC ✔,
  GraXpert ✔ (« astrométrie, spcc OK / GraXpert OK ») ; démarrage par le MENU et
  en terminal ✔ ; **v2.38.11 sous `nftables` actif : « c'est tout bon »** (elle
  s'ouvre, journalise, et DIT le NAS injoignable au lieu de bloquer).
  **VALIDÉS PAR TOI (28/09/2026) — À NE PLUS TE REPROPROPOSER** : les quatre
  essais que la clôture de la nuit laissait « en attente » sont **VALIDÉS** —
  `nftables`/NAS (les couches R/G/B sont lues normalement), **chaîne BlurX** avec
  le dossier de travail, **rendu BXT `--sn 0.3`**, et `--cameras`. **Plus RIEN
  n'est en attente de ton côté**, et il n'y a plus aucun point ouvert sur v2.39.0
  (ta décision du 28/09 : on GARDE l'histogramme à deux bandes **tel quel**,
  176 px — le point est clos, plus à trancher).

- Sujets OUVERTS (analyse close, décisions livrées), par ordre d'intérêt :
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
- Leçons ÉCRITES le 27/09/2026 (3e passe, v2.38.6) — section « Espace disque et
  fichiers de travail » : le message « N requested and M written » est celui de
  `numpy.ndarray.tofile()`, appelé par astropy pour écrire un FITS (donc =
  écriture partielle = volume plein, jamais un chemin invalide) ; `/tmp` sous
  Linux est souvent un tmpfs rempli par l'application elle-même ; toute écriture
  passe par `images.ecrire_fichier` (espace vérifié avant, `.part` renommé) et
  tout `mkdtemp` par `travail.creer_dossier` ; un plafond de taille se calcule
  sur l'espace RÉEL ; un contrôle ajouté dans un `try` large doit venir APRÈS
  ses dépendances (sinon `NameError` avalé = échec silencieux).
- Leçons ÉCRITES le 27/09/2026 (2e passe, v2.38.5) — section « Doc outils
  externes (CLI) → Détection de l'exécutable » : le nom du binaire d'un outil
  tiers CHANGE d'un OS à l'autre (`GraXpert-linux` sous Linux, bundle macOS) et
  la comparaison est sensible à la casse hors Windows ; l'INI DE SIRIL
  (`graxpert_path`, `catalogue_gaia_*`) est une source de détection déjà
  renseignée par l'utilisateur (et GKeyFile échappe les antislashs) ; une
  commande de REPLI persistée sans exécutable fige une détection ratée à vie →
  re-tester, ne pas persister, et DIRE l'état dans l'interface.
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
- Leçon PROPOSÉE le 25/09/2026, **sans urgence — à trancher quand tu le voudras,
  et elle ne bloque RIEN** : toute
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
  qui a révélé le fond cible non transmis. Reste PROPOSÉE (25/09/2026, sans
  urgence, ne bloque rien) : la
  parité des corrections pré-étirement entre chaîne LIVE et chaîne EXTERNE.
- Leçons ÉCRITES le 28/09/2026 (jalon 75, v2.39.0) — section « Pièges », 4 entrées :
  ① **les barres de niveaux vivent APRÈS le moteur d'étirement** (comme le mini de
  SharpCap, elles n'agissent que sur l'affichage ; « les barres = les points de
  l'étirement » est IMPOSSIBLE, VeraLux n'a ni point noir ni point blanc) ;
  ② **un curseur de saturation par couleur doit viser une TEINTE** (la première
  formule, par canal, verdissait l'image) ; ③ **un panneau rafraîchi seulement par
  les données ne suit pas les gestes** (corollaire de la leçon « les mesures sont
  relancées par le WORKER ») ; ④ **une échelle d'axe non dite est un piège**
  (log/linéaire, choisie par MESURE et DITE dans la ligne d'état).
- Leçons ÉCRITES le 28/09/2026 (2ᵉ passe, v2.40.0) — section « Pièges », 2 entrées :
  ① **la zone de catalogue de l'astrométrie est un DISQUE, pas un rectangle — et
  `N_CAT_MAX` passe APRÈS la sélection** (le rectangle suppose que l'axe X de la
  caméra suit les AD : sur une caméra tournée il ne gardait que 43 % des étoiles
  de l'image et gardait une bande HORS image ; le juge d'un champ large est le rms
  sur les MÊMES étoiles, jamais l'écart point par point des deux WCS) ; ② **la
  SPCC n'est PAS réservée au mono multi-bandes** (un capteur couleur = trois
  entrées + un filtre LPF COMMUN ; le nom du capteur est AMBIGU — « Sony IMX585 »
  est dans les deux listes — c'est l'interface qui tranche ; et le défaut d'un
  filtre OSC est la référence « sans filtre », jamais un vrai LPF en silence).
  Plus AUCUNE leçon en attente.
- **Leçons du 29/09/2026 (jalon 77, v2.42.0) — ÉCRITES dans CLAUDE.md le même
  jour, sur ton accord explicite** (« tu peux remonter les leçons dans
  claude.md »), section « Pièges » : ① deux conventions de rappel `progression`
  cohabitent dans `telechargeur.py` (`(nom, fraction)` et `(fraction)`) — dire
  laquelle on prend, l'inversion des arguments n'ayant été vue que par le banc ;
  ② **un banc qui isole l'environnement doit aussi basculer les constantes d'OS**
  (`%APPDATA%` reste sinon dans le vrai dossier de configuration — le banc lisait
  le VRAI `config.json`) ; ③ **l'audit de géométrie doit ignorer les parents de
  taille 0/1 px** (une configuration VIDE laisse un sas de panedwindow à 1 px :
  29 widgets « écrasés » dès la construction, **préexistant**, vérifié sur un
  worktree de HEAD) ; ④ **une donnée téléchargeable doit devenir utilisable dans
  la session** (case/combos rafraîchis à la fin du transfert), sinon le
  téléchargement ne sert à rien avant un redémarrage. La section « Portage
  Linux / macOS » y décrit désormais l'installateur macOS et la route commune aux
  deux packers.

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
- **Machine LINUX d'Alain (fait du 29/09/2026, à sa demande)** : **Ubuntu 26.04
  LTS** — l'**installateur Linux d'AVAStack y a été exécuté PLUSIEURS FOIS**
  (installation, prérequis, venv, dépendances, lancement) et l'application y est
  employée : l'astrométrie, la SPCC et GraXpert y sont validés (constats des 27 et
  28/09/2026). **La documentation disait le contraire** (« pas encore exécuté sur
  une vraie machine Linux ») : corrigé dans `INSTALLATION.md` (§ 3 et § 8),
  `installer/README.md` et dans la release `v2.41.0` (notes + pièce jointe).
  Restent à faire : machine **vierge** (sans Python) et **test matériel caméras**
  sous Linux (`--cameras`).


## Pièges récents (rappels opérationnels)

- **Leçons du jalon 78 (installateur macOS, v2.42.0)** :
  - **Un installateur d'un OS qu'on ne peut PAS exécuter se vérifie par ce qui
    est vérifiable** : ① `bash -n` (analyse syntaxique — le bash de Git Bash
    suffit) ; ② **exécution réelle des garde-fous** (le script doit REFUSER de
    s'installer hors macOS et `--aide` doit répondre : deux tests lancés depuis
    Windows) ; ③ un banc qui contrôle le CONTENU du paquet (racine unique,
    fichiers indispensables, modes, fins de ligne, aucun binaire). Et l'état est
    écrit **daté** partout (« écrit le 29/09/2026, pas encore exécuté sur un
    Mac »), jamais déguisé en test réussi.
  - **Charger un script pour tester ses fonctions sans exécuter son `main`** :
    `grep -v '^main "\$@"' script.sh > copie.sh` puis `. copie.sh` — un simple
    `sed '$d'` ne suffit pas quand le fichier se termine par une ligne vide (le
    `main` s'exécute et le test s'arrête). Et **le script chargé active
    `set -euo pipefail`** : remettre `set +e` juste après, sinon la première
    vérification « qui doit échouer » (le refus hors macOS) arrête tout.
  - **Sous macOS, l'application doit être CLIQUABLE sans droits administrateur** :
    un bundle minimal `~/Applications/AVAStack.app` (Info.plist + exécutable
    shell qui lance le venv) suffit — **ne pas embarquer Python ni le venv** dans
    le bundle, sinon chaque mise à jour exige de refaire le paquet. Le bundle
    n'étant pas signé, prévenir : clic droit → « Ouvrir », ou
    `xattr -dr com.apple.quarantine`.

- **Leçons du jalon 77 (v2.42.0)** :
  - **DEUX conventions de `progression` cohabitent dans `telechargeur.py`** :
    `progression(nom, fraction)` pour `verifier_ou_telecharger`/`chunks` et
    `progression(fraction)` pour `telecharger` (bas niveau) — l'adaptation se fait
    à UN SEUL endroit, et l'inversion des deux arguments a été attrapée par le
    banc du jalon 77 (le « nom » arrivait comme `float`, la « fraction » comme
    chaîne). Toute nouvelle fonction qui annonce une progression doit dire
    laquelle des deux elle prend.
  - **Un banc qui isole l'environnement ne peut pas se contenter d'`os.environ`
    sous Windows** : `config.dossier_config()` lit `%APPDATA%` quand
    `IS_WINDOWS` est vrai — le banc du jalon 77 lisait donc le **VRAI**
    `config.json` (et la case SPCC d'Alain, cochée, faisait échouer un test
    d'interface). Il faut basculer les constantes d'OS comme le fait le banc du
    jalon 70 (`simule_linux()`), et **retirer `APPDATA` de l'environnement du
    banc**.
  - **`winfo_ismapped()` n'a de sens que sur une fenêtre DÉJÀ dimensionnée** :
    avec une configuration VIDE (départ après effacement du `config.json`), un
    **sas du panedwindow interne reste à 1 px** → 29 widgets « gérés mais non
    affichés » **dès la construction**, et c'est **préexistant** (mesuré sur un
    `git worktree` de HEAD, avant les changements du jalon 77). Un audit de
    géométrie doit donc ignorer les parents de taille 0/1 px (et le contrôle de
    référence reste le banc du jalon 72, qui tourne avec la vraie configuration).
  - **Un parent de widget peut être MAPPÉ et 1×1 pendant quelques centaines de
    millisecondes** après un `deiconify()` : laisser la mise en page se terminer
    (plusieurs `update()`) avant de mesurer la géométrie, sinon on mesure du
    bruit.

- **Leçons du jalon 76 (v2.41.0) REMONTÉES dans CLAUDE.md** (accord d'Alain,
  28/09/2026) — section « Pièges », 4 entrées : ① une demande de l'interface se
  sert en TÊTE de boucle du worker (jamais dans le chemin d'une donnée) ; ② un
  objet de source porte l'état de sa configuration (comparer/refermer ; indices
  d'astrométrie EFFACÉS quand la cible change, `effacer_indices`) ; ③ une source
  de fichiers ne se lit pas « pour rien » en pause (+ deux
  `Thread(_worker).start()` dans la même méthode = deux workers) ; ④ mesurer
  « AVANT » sur un `git worktree` HEAD pour prouver qu'un banc discrimine.
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
- **Inno Setup 6 est dans `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`** (PAS
  dans `Program Files`) : `build_avastack.ps1` y cherche en premier et le trouve.
  Un `Test-Path` sur `Program Files` seul ne prouve donc RIEN — leçon du
  28/09/2026 : l'absence d'ISCC a été annoncée à tort AVANT de lancer le script
  (il se construit en 9 s, l'artefact fait ~11,5 Mo).
- **RELEASES GITHUB : `gh release create vX.Y.Z --title <titre> --notes-file <fichier>
  --target master <les 2 installateurs> INSTALLATION.md`** — `gh` est installé et
  authentifié sur ce poste (compte `darkvad`, portée `repo` ; **dépôt PUBLIC
  depuis le 29/09/2026** — la release l'est donc aussi). **Les notes de la release SONT la doc
  d'installation** (`INSTALLATION.md` précédé d'un court résumé « ce qui
  change ») : elle se lit directement sur la page de la release, et le même
  fichier est joint en pièce. Les installateurs des versions précédentes ne
  sont PAS dans la release (dossier `output/` ignoré par git) : le repli reste
  sur la machine.
- **LA LIGNE DE COMMANDE WINDOWS EST TRONQUÉE au-delà d'environ 1 000
  caractères** (constaté le 28/09/2026, deux fois) : un `git commit -m "…"`
  de plusieurs milliers de caractères part TRONQUÉ et, avec une chaîne non
  fermée, sème le doute sur l'état du dépôt. Pour tout message long, passer par
  un FICHIER (`git commit -F`, `gh release create --notes-file`) — et vérifier
  après coup (`git log -1`, `git status`) qu'aucun commit partiel n'est né.

## Clôtures précédentes

- 28/09/2026 (v2.40.0) : SESSION « ASTROMÉTRIE SUR CAMÉRA TOURNÉE (NGC 7023
  RÉSOLU) ET SPCC OUVERTE AU CAPTEUR COULEUR » — tes deux constats OSC du jour,
  **tous deux fondés** : ① la zone de catalogue du solveur était un RECTANGLE
  (faux dès que la caméra est tournée : il ne gardait que 43 % des étoiles de
  l'image ET gardait une bande HORS image, là où sont les plus brillantes) →
  **disque du champ réel**, et `N_CAT_MAX` appliqué **après** la sélection :
  **NGC 7023 résolu sur tes brutes** (68-80 appariements, rms 0,43-0,46 px,
  0,4716″/px contre 0,4714″/px pour ASTAP) et **M31 non régressé** (112/115
  appariements contre 86/70 avant) ; ② la SPCC accepte un **capteur COULEUR
  (OSC)** — trois canaux + un filtre LPF COMMUN de la base Siril, `mode`,
  `reponses_osc`, gains par canal appliqués par `LiveStacker.gains` — banc NEUF
  `_test_spcc_osc.py` (6 sections, tout au vert). **Verdict réel (ton essai du
  soir) : « tout à l'air bon »** (session dossier OSC NGC 7023, ~40 brutes).
  **Installateur v2.40.0 construit à la clôture.** Repli si régression : v2.38.11.
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
