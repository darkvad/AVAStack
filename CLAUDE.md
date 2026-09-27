# CLAUDE.md

## Projet

AVAStack — application Python unique (`AVAStack.py`, interface
Tkinter) de live stacking : empilement temps réel des brutes
pendant l acquisition. Sources : ciel simulé (démo sans matériel), dossier
surveillé (les brutes FITS/PNG/TIFF écrites par le logiciel d acquisition au
fur et a mesure), webcams/cartes OpenCV, caméras ZWO ASI (SDK).
Anciennement AstroLiveStack (renommé AVAStack pour éviter la confusion
avec ALS).

Pipeline : Acquisition → Calibration (dark/flat) → Alignement (ORB + RANSAC,
repli corrélation de phase) → Empilement avec rejet kappa-sigma → Étirement
temps réel (auto STF ou manuel) → Affichage + histogramme → Sauvegarde
FITS/TIFF/PNG. Traitement externe optionnel (GraXpert, BlurXTerminator) sur
un INSTANTANÉ de l empilement, dans un thread séparé — l empilement accumulé
reste linéaire et intact.

Alain (utilisateur/mainteneur) est amateur d astrophotographie, pas
développeur professionnel — explique les changements en français clair, sans
jargon inutile. Alain utilise divers logiciels pour l acquisition (N.I.N.A.,
APT, SGP, ASI Air…) — ne jamais présumer du logiciel de capture a partir
d une capture d écran sans vérification.

**Environnement** : cible multiplateforme Windows / Linux / macOS (contrainte
posée par Alain — l application doit tourner sur les trois). Le venv local de
dev Windows reste `C:\Astro\astrolivestack\venv` (le dossier n a PAS ete
renomme), mais AUCUN chemin specifique a un OS ne doit etre code en dur dans
le code sans repli — contrairement a la regle anterieure « Windows
uniquement » qui n est plus valable.

**Dépôt distant** : `origin` = https://github.com/darkvad/AVAStack.git
(GitHub, créé le 15/09/2026). Branche unique `master`, poussée et en suivi
(`git push` seul suffit, pas besoin de préciser origin/master). Aucun
fichier sensible ou volumineux n'est suivi (ni config.json, ni venv, ni
build/dist) — garder ainsi lors des futurs ajouts au `.gitignore`.

## AVANCEMENT.md — mémoire de session (court terme)

`AVANCEMENT.md` (racine du dépôt) suit l'état courant du développement :
version stable de référence, tâche en cours découpée en étapes, décisions,
pièges récents. CLAUDE.md reste la mémoire de LONG terme ; AVANCEMENT.md la
mémoire de COURT terme.

- **En début de session (ou en reprenant une tâche)** : lire AVANCEMENT.md
  AVANT de travailler, pour reprendre exactement où l'on s'était arrêté.
- **Tenir AVANCEMENT.md à jour** :
  - à chaque **jalon** (étape terminée, décision tranchée, test réel passé
    ou échoué) ;
  - **sur demande** d'Alain ;
  - quand **Alain indique la fin de session** (consigner l'état exact et
    la prochaine étape avant de s'arrêter).
- Ne pas y dupliquer ce qui appartient à CLAUDE.md ; les leçons durables
  remontent vers CLAUDE.md via la procédure de proposition décrite plus bas.
- **Garder AVANCEMENT.md LÉGER** (consigne d'Alain, 18/09/2026) : le
  changelog détaillé des versions vit dans `avastack/__init__.py`
  (source) — AVANCEMENT.md ne le duplique pas. La section « État actuel »
  reste courte : version stable de référence, résumé succinct du DERNIER
  jalon (une quinzaine de lignes maximum), tâche en cours et prochaine
  étape. À chaque nouveau jalon, les détails du jalon précédent sont
  SUPPRIMÉS (seul le dernier reste détaillé) et les jalons/tâches
  terminés plus anciens sont nettoyés — leur trace durable est dans le
  changelog du source et l'historique git. Seuls les rappels opérationnels
  encore utiles (pièges récents, prochains tests réels, réglages gelés
  sur décision d'Alain) sont conservés.

## Commandes essentielles (Windows, PowerShell)

```powershell
# Activer le venv
C:\Astro\astrolivestack\venv\Scripts\Activate.ps1

# Vérifier la syntaxe avant toute livraison (TOUJOURS)
python -c "import ast; ast.parse(open('AVAStack.py', encoding='utf-8').read())"

# Lancer l application
python AVAStack.py

# Installer / mettre a jour les dépendances (venv activé)
pip install -r requirements.txt
```

**PIÈGE LANCEMENT (constat réel)** : sur la machine d'Alain, `python3` ne
pointe PAS vers le venv — même avec le venv activé, `python3` lance le
Python du Microsoft Store (3.13, sans les paquets du projet). Le venv
n'a d'ailleurs pas de `python3.exe`. Toujours lancer avec `python
AVAStack.py`. Symptôme si mauvais interpréteur : l'appli démarre mais
comportements incohérents (dark « illisible », empilement sans effet) —
vérifier `python -c "import sys; print(sys.executable)"` avant de
soupçonner le code.

`requirements.txt` = dépendances de `AVAStack.py`. Toute nouvelle
dépendance ajoutée au script doit y être ajoutée — cf. Conventions
non-négociables.

**Installateur et tests réels (consigne d'Alain, 20/09/2026)** : dès qu'une
passe de code touche PLUS d'un ou deux fichiers, REBUILDER l'installateur
AVANT le test réel — sinon Alain teste une version sans les corrections.
C'est à la CHARGE DE L'AGENT : le faire et le signaler en fin de passe,
sans qu'Alain ait à y penser.

```powershell
# Rebuild de l installateur (lit la version dans avastack/__init__.py)
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\build_avastack.ps1

# Rebuild du paquet Linux (même version, lue dans le même source)
python installer\linux\build_avastack.py
```

**NOM DES INSTALLATEURS : toujours le numéro de version (consigne d'Alain,
27/09/2026)** — c'est le nom de l'artefact qui dit ce que teste Alain, et deux
versions ne doivent JAMAIS s'écraser. Registre :

| Plateforme | Artefact | Producteur |
| --- | --- | --- |
| Windows | `installer/windows/output/avastack-setup-<version>.exe` | `build_avastack.ps1` (ISCC + `/DAppVersion`) |
| Linux | `installer/linux/output/avastack-setup-<version>-linux.tar.gz` | `installer/linux/build_avastack.py` |

Règles qui vont avec :
- la version vient TOUJOURS de `AVASTACK_VERSION` (`avastack/__init__.py`) —
  jamais recopiée à la main dans un nom de fichier ; `avastack.iss` **refuse**
  de compiler sans `/DAppVersion` (`#error`) et le packer Linux la lit dans le
  source ;
- on ne renomme jamais un artefact après coup, et on ne remplace pas un
  artefact d'une version antérieure (l'ancien reste à côté : c'est lui qui sert
  de repli en cas de régression) ;
- après toute passe de code, annoncer en fin de réponse le CHEMIN EXACT de
  l'artefact reconstruit (version comprise).

## Bancs et diagnostics — emplacement (décision d'Alain, 27/09/2026)

Les bancs (`_diag_*.py` : diagnostics ; `_test_*.py` : non-régression) ne
vivent PLUS à la racine : ils sont rangés sous **`bancs/`**, avec un seul thème
séparé, **`bancs/cameras/`** (diagnostic matériel ET bancs de la couche caméra :
SDK constructeurs, capacités, TEC, câblage UI des contrôles).

- **Chaque banc porte un bootstrap autonome** (inséré juste après sa docstring)
  qui met dans `sys.path` le premier dossier parent contenant `AVAStack.py` —
  il trouve donc l'application qu'il soit dans le dépôt (`bancs/`,
  `bancs/cameras/`) ou dans le dossier d'installation. Ne pas le retirer, et ne
  jamais remettre de chemin absolu de machine de dev.
- **Lancement** : depuis la RACINE du dépôt (ou du dossier d'installation),
  `python bancs\_test_xxx.py` / `./venv/bin/python bancs/cameras/_diag_camera_qhy.py`.
  Les bancs qui lisent des images de test utilisent des chemins relatifs au
  dossier courant : on garde donc l'habitude de les lancer depuis la racine.
- **Installateurs** : SEUL le thème caméra est embarqué (`bancs/cameras/`) —
  « les autres bancs n'ont rien à y faire, c'est pour du dev » (Alain,
  27/09/2026). Le `.iss` et le packer Linux pointent le dossier, jamais une
  liste de fichiers : un banc caméra ajouté entre tout seul dans les deux
  installateurs ; un banc de dev ne part JAMAIS.
- Un banc cité dans CLAUDE.md ou AVANCEMENT.md le reste par son NOM (les
  fichiers n'ont pas été renommés) : pour le retrouver, chercher sous `bancs/`.

## Portage Linux / macOS — prérequis et installateur (étude du 27/09/2026)

Contrainte d'Alain : l'application doit tourner sur Windows / Linux / macOS. Le
code est DÉJÀ multiplateforme (chemins de config par OS, `compat.ZWO_DLL_NAME`,
`cameras/sdk_loader.nom_bibliotheque`, détection des outils externes selon l'OS) :
le chantier restant est l'INSTALLATION. Éléments vérifiés le 27/09/2026 (CLI
installé, documentations et pages constructeurs) :

- **Prérequis LINUX (ce ne sont PAS des DLL)** : `python3` ≥ 3.10 +
  `python3-venv` + **`python3-tk`** (Tkinter n'existe PAS sur pip : c'est LA
  différence de fond avec Windows), `libgl1` et `libglib2.0-0` (roues
  `opencv-python`), `libusb-1.0-0` (dépendance documentée du SDK Player One).
- **Accès USB : les règles udev** — sans elles, la caméra n'est visible QUE en
  root. Chaque SDK constructeur fournit son fichier : ZWO `asi.rules`
  (`sudo install asi.rules /etc/udev/rules.d`, le vendor id `03c3` est déjà
  écrit dedans), Player One `99-player_one_astronomy.rules`, ToupTek et SVBONY
  leurs fichiers respectifs.
- **Bibliothèques constructeurs** : `libASICamera2.so` (ZWO),
  `libPlayerOneCamera.so`, `libtoupcam.so`, `libSVBCameraSDK.so` (+ `.dylib` sous
  macOS) — exactement les noms que cherche le code. **QHY : rien à faire** (le
  paquet pip `qhyccd` embarque le SDK natif, roues `cp310-abi3` manylinux_2_34 +
  Windows ; PAS de roue macOS en revanche). Sur Debian/Ubuntu,
  `libplayeronecamera2t64` apporte la bibliothèque Player One.
- **Outils externes** : GraXpert existe en Linux (zip) et macOS (dmg) ; le CLI
  rc-astro (BlurXTerminator) existe pour Windows, macOS ET Linux.
- **macOS** : Python de python.org (Tk inclus) ou `brew install python-tk@3.14`,
  puis bundle `.app` + signature/notarisation Apple (sinon Gatekeeper bloque).
- **Route LINUX RETENUE (décision d'Alain, 27/09/2026) : ① script + venv**,
  implémentée le même jour — `installer/linux/install_avastack.sh` (copie dans
  `~/.local/share/AVAStack`, venv + `pip install`, lanceur
  `~/.local/bin/avastack`, entrée `.desktop`), distribué en
  `avastack-setup-<version>-linux.tar.gz` par `installer/linux/build_avastack.py`.
  Le `.deb`, l'AppImage et le Flatpak restent des options NON retenues.
  **Version livrée SANS CAMÉRAS** : les paquets `qhyccd`/`zwoasi` sont retirés de
  l'installation et aucun `*.so` n'est embarqué → l'application démarre et
  travaille en **mode dossier / composition / OpenCV / simulé** ; les caméras
  viendront quand les `.so` constructeurs seront là (option `--cameras` du
  script : installe les paquets pip et copie les `*.so` présents, puis rappelle
  la commande des règles udev). Prérequis système à dire à l'utilisateur dans
  cet ordre : `python3-venv`, **`python3-tk`**, `libgl1` + `libglib2.0-0`,
  `libusb-1.0-0` — le script teste Tkinter et les imports réels et affiche la
  commande par distribution.
  ⚠ **FINS DE LIGNE (constat du 27/09/2026)** : le dépôt vit sur Windows
  (`core.autocrlf=true`), donc les fichiers du disque sont en CRLF — or un
  script `.sh` en CRLF NE S'EXÉCUTE PAS sous Linux (`set -euo pipefail\r` =
  commande introuvable). Le packer convertit donc `.sh` et `.txt` en LF dans
  l'archive (et corrige `info.size` en conséquence). Un script `install_*`
  ajouté un jour doit passer par le packer, jamais être déposé dans le
  `.tar.gz` tel quel.
- **Piste « zéro .so » : INDI** — les pilotes INDI *embarquent* eux-mêmes le SDK
  constructeur (le dépôt `indi-3rdparty` redistribue des binaires constructeurs :
  `indi_asi_ccd`, `indi_qhy_ccd`, `indi_playerone_ccd`, `indi_toupbase`, pilote
  SVBony), mais sur Debian/Ubuntu c'est le PAQUET INDI qui apporte les `.so` ET
  les règles udev. Faire d'AVAStack un CLIENT INDI (socket 7624, XML + BLOBs
  FITS ; `indipyclient` = pur Python, pip) supprimerait tout `.so` côté
  application et unifierait les trois OS — jalon à part entière (nouvelle source
  d'acquisition, capacités lues sur les propriétés du pilote, test réel), à
  programmer APRÈS le portage direct (qui réutilise tout l'existant).

## Conventions non-négociables

- Commentaires et docstrings **en français**, cohérents avec l existant.
- Toute modification d `AVAStack.py` : bump `AVASTACK_VERSION`
  + entrée de changelog en tête de fichier expliquant le **constat réel** qui
  a motivé le changement (pattern établi : `CORRECTION (constat Alain, run
  réel - ...)`). Ne jamais casser un défaut existant sans y être invité —
  privilégier une option/variable qui préserve le comportement actuel si non
  précisé. (La variable s appelait `ASTROLIVESTACK_VERSION` dans la
  convention d origine, mais n a été réellement créée qu au renommage en
  AVAStack, v1.0.0.)
- Toute nouvelle dépendance Python (`import` d un paquet pip pas déjà utilisé
  dans le fichier) : **toujours signaler explicitement à Alain dans la
  réponse** ET l ajouter au `requirements.txt`. Ne pas décider unilatéralement
  de l éviter/la remplacer sans le dire — c est à Alain de trancher.
- Vérifier la syntaxe (`ast.parse`) après CHAQUE édition avant de la
  considérer terminée.
- **Installateurs nommés AVEC LE NUMÉRO DE VERSION** (consigne d'Alain,
  27/09/2026) : `avastack-setup-<version>.exe` (Windows),
  `avastack-setup-<version>-linux.tar.gz` (Linux), version lue dans
  `AVASTACK_VERSION` — jamais un nom figé, jamais un artefact écrasé. Détail
  et registre des producteurs : section « Installateur et tests réels ».
- **Stashes : jamais de stash qui traîne.** Un `stash` n'est qu'une étape
  temporaire : dès que son contenu est repris, VÉRIFIÉ et commité, il se
  droppe (`git stash drop`) — le garder n'apporte que de l'ambiguïté aux
  sessions suivantes. Seule exception : s'il est la SEULE copie d'un travail
  non commité. Avant de dropper : vérifier que chaque fichier du stash est
  réellement repris (comparer le CONTENU, pas le nombre de fichiers — un
  fichier de test peut avoir été réécrit depuis), relever le hash
  (`git rev-parse 'stash@{0}'`) et le consigner dans AVANCEMENT.md.

## Fichier tiers : veralux_core_headless.py (GPL-3.0-or-later)

`veralux_core_headless.py` (moteur d étirement hyperbolique VeraLux, extrait
headless de VeraLux_HyperMetric_Stretch.py de Riccardo Paterniti) est copié
dans ce dépôt **tel quel**, sous licence GPL-3.0-or-later — c est du code
tiers, PAS du code du projet. Il n importe que numpy (aucune dépendance
Siril : le wrapper pyscript Siril du projet d origine n a PAS été copié).
Utilisation : `solve_and_stretch(img_data, ...)` → (image étirée, log_d,
diagnostics), avec profils capteur `SENSOR_PROFILES` (Rec.709 par défaut,
IMX585, IMX662, IMX533, IMX571/2600, IMX294). L image en entrée peut être
2D (H,W) mono ou (H,W,3) RGB (retransposée automatiquement).

**Ne jamais reproduire ni modifier `veralux_core_headless.py` à la légère.**
Tout besoin d adaptation (ex : câblage dans DisplayProcessor) se fait dans
un fichier séparé du projet, jamais par édition du fichier tiers.

## Sauvegardes : linéaire vs « tel que vu » (v2.2.7)

Quatre boutons d enregistrement aux rôles DISTINCTS — ne jamais fusionner
(le 2e a été ajouté en v2.35.0, cf. la règle ci-dessous) :

- **« 💾 Enregistrer l'empilement (linéaire)… »** : l EMPILEMENT BRUT (moyenne
  temporelle + normalisation par rôle de `composer()`), sans gradient, sans
  correction de couleur, sans étirement — la référence reproductible
  (cf. la règle ci-dessous). Depuis la v2.35.0, AUCUNE case de couleur ne
  change ce fichier (banc `_test_save_brute_jalon59.py`).
- **« 💾 Enregistrer l'empilement traité (linéaire)… »** (cadre Sortie, ajouté
  en v2.35.0) : la CHAÎNE DE SORTIE sans étirement — gradient live, débruitage
  live, corrections de couleur, netteté, SCNR — donc le fichier « prêt à
  traiter » dans un logiciel externe. En-tête auto-descriptif (`AVAAPPLI`,
  `AVAVUE`).
- **« 💾 Enregistrer le résultat traité (linéaire)… »** (cadre « Traitement
  externe ») : le résultat du ⚡ manuel (GraXpert/BXT à la demande, sur un
  INSTANTANÉ), sans étirement — voulu, pour retraitement ultérieur dans un
  logiciel dédié. Comportement historique, inchangé ; ne pas le confondre avec
  le bouton « empilement traité (linéaire) » du cadre Sortie (chaîne LIVE).
- **« 💾 Enregistrer tel que vu (étiré)… »** : SEUL bouton qui applique la
  chaîne d étirement complète en PLEINE résolution (jamais l aperçu
  1600 px) : `DisplayProcessor.rendu_pleine_resolution()` — fonction PURE
  (aucun état partagé : pas de stats EMA, pas de solveur, jamais
  black/white/gamma). VeraLux y réutilise le DERNIER logD résolu (rendu
  identique à l écran, sans re-résolution). Le retrait de gradient LIVE
  (GraXpert live) n est disponible qu AVEC LE MOTEUR VERALUX — PAS en
  mode STF : sa case vit dans le cadre VeraLux, MASQUÉ quand le moteur
  STF est sélectionné (`_on_moteur`), et le thread solveur — seul chemin
  du GX live — ne tourne qu en mode VeraLux (la restauration de config
  respecte cette dépendance : VeraLux AVANT le moteur). GraXpert live ne
  s applique qu en vue « empilement » (en vue « traitée », l image a déjà
  subi le traitement externe — le relancer ferait un DEUXIÈME traitement ;
  synchro `_sync_vl_graxpert_vue`). Les réglages STF sont MASQUÉS
  (pas grisés) en mode VeraLux — ils n y ont aucun effet.

**RÈGLE (décision d'Alain, 24/09/2026) — LA SAUVEGARDE LINÉAIRE EST BRUTE.**
Elle ne contient QUE l'empilement : ni retrait de gradient, ni correction de
couleur. Les corrections de couleur — SPCC, gains photométriques (Gaia),
équilibrage des canaux, recalage colorimétrique (Linear Fit) — appartiennent à
la CHAÎNE DE SORTIE (affichage et sortie « traitée »), JAMAIS au fichier
linéaire : sinon celui-ci n'est ni brut ni fini. Justification : une correction
appliquée en amont est absorbée en partie par la normalisation par canal de
`composer()` — c'est pour cela que les corrections sont appliquées APRÈS
`composer()` depuis la v2.35.0 —, et le retrait de gradient vit déjà sur une
COPIE (GraXpert live ne modifie jamais l'empilement) ; garder le fichier brut est
donc le seul moyen d'avoir une référence reproductible et un traitement ultérieur
propre.
Sorties attendues : ① **empilement linéaire BRUT** (référence) ; ② **empilement
traité linéaire** (gradient retiré + corrections, sans étirement) par un **bouton
DÉDIÉ** — distinct de « Enregistrer le résultat traité (linéaire) » qui reste
lié au traitement EXTERNE manuel (⚡, GraXpert/BXT à la demande sur un
instantané) ; ③ **tel que vu** (étiré). ÉTAT DU CODE depuis la **v2.35.0**
(25/09/2026) : CONFORME, codé et au banc. `composer()` ne porte plus AUCUNE
correction de couleur (il rend l'empilement BRUT) ; les gains (manuels ×
SPCC/Gaia), l'équilibrage des canaux et le recalage « Linear Fit » vivent dans
`composition.corrections_couleur()`, appliquée par
`CompositeStacker.mean(corrections=True)` (DÉFAUT = affichage), par le solveur
live APRÈS la recomposition des couches traitées, et par le 3e bouton « empilement
traité (linéaire) » ; `mean(corrections=False)` est l'empilement BRUT que la
sauvegarde linéaire enregistre (banc `_test_save_brute_jalon59.py` : fichier
IDENTIQUE au pixel près avec et sans les cases de couleur cochées). Ordre de la
chaîne de sortie : GraXpert (par couche en composition) → débruitage →
CORRECTIONS (gains + équilibrage + recalage) → netteté/SCNR → étirement.

## Doc outils externes (CLI)

### GraXpert CLI

Syntaxe (le flag `-cli` est INDISPENSABLE en ligne de commande) :

```
graxpert.exe <image> -cli -cmd background-extraction|denoising
            [-correction Subtraction|Division] [-smoothing 0..1]
            [-output <nom_sans_extension>] [-bg] [-ai_version X]
```

Pièges :
- `-correction` est **SENSIBLE À LA CASSE** (`Subtraction`/`Division`,
  S et D majuscules — une casse différente échoue silencieusement ou avec
  une erreur obscure).
- Le DÉBRUITAGE (`-cmd denoising`) utilise `-strength` (0..1, défaut
  0.5) — `-smoothing` ne concerne QUE le retrait de gradient
  (`-cmd background-extraction`) : confondre les deux = échec
  silencieux. (Doc officielle du dépôt Steffenhir/GraXpert, vérifiée
  le 15/09/2026.)
- `-output` attend un chemin **SANS extension** (GraXpert choisit lui-même
  l extension de sortie, souvent avec un suffixe `_GraXpert`).
- Les modèles IA sont téléchargés au premier usage de chaque fonction
  (`-ai_version` sélectionne la version) — un premier lancement peut être
  long et nécessiter Internet.

### RC-Astro CLI (BlurXTerminator / StarXTerminator)

Un seul exécutable `rc-astro.exe` pour tous les outils RC-Astro ; le premier
argument choisit l outil (`bxt`, `sxt`, `nxt`) :

```
rc-astro.exe bxt <image> -o <sortie> --overwrite
             [--ss 0..0.7] [--sn 0..1] [--correct-only] [--device gpu]
```

Pièges :
- BXT et SXT sont deux **licences payantes séparées** malgré le même
  exécutable — avoir installé le logiciel ne garantit pas les deux licences.
- Bornes officielles : `--ss` (sharpness stars) 0–0.7, `--sn` 0–1,
  halos -0.5–0.5. Les dépasser donne des résultats imprévisibles, pas une
  erreur claire.
- La licence RC-Astro est liée **par utilisateur** (pas par machine) :
  si l outil est lancé sous un autre compte que celui où la licence a été
  activée, il répond « not licensed on this computer » — constaté en prod
  sur le projet pipeline siril (compte système systemd vs compte personnel).
- Au premier lancement sous un nouveau compte, rc-astro peut devoir
  recontacter les serveurs RC-Astro et télécharger ses modèles IA (~300 Mo)
  — prévoir un accès réseau une fois, ensuite c est mis en cache local.
- La sortie (`-o`) peut porter un suffixe différent de la demande selon
  l outil — toujours rechercher le fichier réellement produit, jamais
  présumer du nom exact.

### Pièges généraux des outils externes (leçons du projet pipeline siril)

- **Détecter un échec par simple sous-chaîne du stdout ("erreur"/"échoué")
  est structurellement fragile** : mots accentués non normalisés par
  `.lower()`, compteurs (« 0 en échec » = succès), variantes selon version.
  Au moindre doute, instrumenter (faire dire au code quel motif a matché)
  plutôt que deviner une nouvelle hypothèse sans preuve. Préférer le code
  de retour du process + l existence réelle du fichier de sortie.
- **Un symptôme anormal en aval peut venir d une étape très en amont** :
  vérifier la chaîne complète (données d entrée) avant de soupçonner
  l outil/l étape qui manifeste le symptôme.
- **Rejouer le même test sur un état de code déjà validé** (version d avant
  la modification suspectée) avant de conclure que la modification récente
  est la cause.
- Sur une cible difficile, plusieurs problèmes indépendants peuvent se
  manifester EN MÊME TEMPS — isoler UNE SEULE variable à la fois.
- **Une fonctionnalité optionnelle à risque non nul, même faible, gagne à
  rester opt-in (désactivée par défaut)** plutôt qu opt-out.

## Pièges (leçons du projet AVAStack)

- **`cv2.imencode` ATTEND DU BGR** (constat réel du 25/09/2026, v2.36.1) :
  toute l'appli travaille en **RGB** et `load_image` convertit à la lecture
  (`COLOR_BGR2RGB`), mais `save_image` passait l'image RGB telle quelle à
  `cv2.imencode` → **tout PNG/TIFF exporté avait R et B PERMUTÉS** (mesuré sur
  un vrai fichier : PNG_R ≈ FITS_B, corrélation 1,0000). Le piège est
  **silencieux** : l'aller-retour interne (écriture sans conversion, relecture
  avec conversion) restait cohérent, seuls les visionneuses, Siril, GraXpert et
  Alain le voyaient — depuis des versions (Alain : « ça me fait ça depuis le
  début »). **Règle : avant tout `imencode`/`imwrite` d'une image à 3 canaux,
  convertir `COLOR_RGB2BGR` ; et un banc qui teste l'écriture d'un fichier image
  doit le RELIRE avec un lecteur indépendant (OpenCV brut, PIL), jamais
  seulement par `load_image`.** Banc : `_test_fond_bleu_jalon62.py` [1].
- **UN ÉTIREMENT LOG AMPLIFIE LA COULEUR DU FOND** (constat réel du
  25/09/2026, v2.36.1) : VeraLux soustrait une **ancre** (scalaire lu dans
  l'histogramme de luminance) puis étire en log ; pour le fond, seul compte le
  **résidu** (niveau du canal − ancre) → 3,6 % d'écart de ciel (fond pourtant
  mesuré NEUTRE à 0,1 % sur les zones les plus lisses) devenaient un fond étiré
  R/G 0,363 · B/G 1,611, franchement bleu. Ne pas chercher la cause dans
  l'empilement : **mesurer le fond du fichier LINÉAIRE** (`_diag_empilement_couleur.py`)
  avant d'accuser la composition. Correctif : `couleurs.neutraliser_fond` juste
  avant l'étirement (gains ~2 % mesurés sur la médiane de la moitié sombre).
  Attention au corollaire : sur un cadrage **dominé par un objet étendu**, la
  « moitié sombre » n'est plus du ciel et les gains partent à la borne (d'où le
  garde-fou ±10 % et l'annonce des gains à l'écran). Banc :
  `_test_fond_bleu_jalon62.py` [2]/[3].
- **UN GAIN MULTIPLICATIF AMPLIFIE LE BRUIT DU CANAL QU'IL MONTE** (mesure du
  25/09/2026, v2.37.0) : sur ses empilements M31, le grain du fond était
  équilibré en R/G (0,902) mais **B/G = 1,174** — et les comptes tombent
  exactement : (σ_B·K_B)/(σ_G·K_G) = 0,891 × (1,0000/0,7587) = 1,174, c'est-à-dire
  **K_B/K_G = 1,32 de la SPCC** appliqué à un grain de couche déjà plus fin en
  bleu (0,891). Corollaire : ni l'équilibrage des canaux ni un SCNR de canal ne
  peuvent corriger un excès de grain BLEU. Le levier est de lisser la **CHROMA**
  (`couleurs.reduire_bruit_chroma`, espace YCrCb : seuls Cr/Cb sont réécrits,
  donc la LUMINANCE ne bouge pas) — et il ne peut, par construction, retirer que
  la *couleur* du grain : la part de LUMINANCE (mesurée ×1,00 après lissage)
  relève du débruitage/l'intégration. Mesurer le grain CHROMATIQUE sur les écarts
  de couleur (R−G, B−G), pas sur les canaux : le grain de luminance y est commun
  et s'annule. Banc : `_test_chroma_nr_jalon63.py`.
- **LES MESURES ASTRO/PHOTOMÉTRIE/SPCC SONT RELANCÉES PAR LE WORKER, PAS PAR
  L'UI** (constat réel d'Alain du 25/09/2026, v2.37.0 : « je voulais refaire
  calculer la SPCC mais étant en fin de stack, ben ça le fait pas en décochant et
  recochant… le libellé reste gris avec les anciennes valeurs »). Les tours
  `_astro_tour` / `_photo_tour` / `_spcc_tour` vivent dans la boucle de frames :
  dès qu'aucune brute n'est lisible (« lu is None ») ou que l'empilement est en
  pause (« ■ Arrêter »), le worker sort **avant** eux → une mesure demandée par
  une case n'était tentée qu'à la PROCHAINE frame, qui n'arrive jamais en fin de
  source. Parade : une case de mesure pose une **demande** servie par le worker
  même sans frame (`_servir_demandes_sans_frame`), et le texte de la mesure est
  poussé à l'UI (`_pousser_rendu` rafraîchit les lignes de mesure du dict d'état
  réutilisé). **Règle : ne jamais déclencher une mesure depuis un callback Tk**
  (elle est lente et mute l'état du worker) — poser une demande, laisser le
  worker la servir.
- **DÉBRUITAGE LOCAL CLASSIQUE SUR STACKS ASTRO = FOND « LÉOPARD »**
  (constat réel du 15/09/2026 ; jalons 7/8/9 ABANDONNÉS ce jour-là, puis
  **REMIS le 16/09/2026 à la demande d'Alain — v2.3.4, mêmes algorithmes,
  désactivé par défaut, force par défaut 0,5 sur la plage 0-1**. Test réel
  du 16/09/2026 (MÊME verdict) : « pas top » **dès que le retrait de
  gradient est actif**, « mieux mais pas parfait » sans → décision d'Alain :
  code conservé tel quel, **cases simplement décochées** (détails et état
  courant : AVANCEMENT.md § « Débruitage : abandonné le 15/09/2026, REMIS le
  16/09/2026 »). Constat réel : ondelettes à trous
  (starlet) ET Non-local Means OpenCV créent tous deux un moutonnement
  en plaques dès que la force est utile ; à force réduite, le bruit
  résiduel AUTOUR DES ÉTOILES rend le fond lisse encore plus visible par
  contraste. Causes identifiées : seuiller des niveaux GROSSIERS de la
  transformée (structure, pas bruit), seuil DUR (îlots), h/fenêtre de
  recherche NLM trop grands (la fenêtre FIXE l'échelle des plaques) — et
  structurellement, le bruit élevé d'un empilement live peu intégré.
  À retenir : (1) ne JAMAIS valider un débruiteur sur du bruit pur
  synthétique (les réglages agressifs y paraissent meilleurs) — image
  réelle obligatoire dès la première passe ; (2) rester DOUX : à force
  utile, toute méthode locale moutonne ; (3) si le sujet est reposé,
  viser des méthodes épargnant les étoiles par conception (IA légère
  locale type Noise2* entraîné astro) plutôt que re-raffiner le
  pixel-classique.
- **DÉBRUITAGE APRÈS RETRAIT DE GRADIENT = PIRE QUE SANS** (constat réel
  d'Alain, 16/09/2026 — dégradation observée sur vraies images) : enchaîner
  GraXpert (gradient) PUIS un débruiteur local donne un résultat MOINS bon
  que le débruiteur seul sur l'empilement brut — alors que l'ordre appliqué
  (gradient → débruitage) est le « bon » en théorie. À retenir : le
  post-traitement d'un outil peut changer la STATISTIQUE du bruit et
  dérégler un débruiteur qui estime son seuil sur l'image qu'il reçoit
  (nos k-sigma/h sont auto-adaptés par MAD, cf. `processing/denoise.py`) —
  hypothèse NON vérifiée, à instrumenter si le sujet est rouvert ; en
  attendant, ne pas empiler les deux dans une validation réelle.
- **OpenCV 5 : `fastNlMeansDenoising` sur uint16 n'existe qu'avec
  `normType=cv2.NORM_L1` et h en TABLEAU passé en 2e argument
  POSITIONNEL** (l'ordre des paramètres diffère entre les deux
  surcharges Python !) : `cv2.fastNlMeansDenoising(u16,
  h=np.array([h], np.float32), templateWindowSize=…, searchWindowSize=…,
  normType=cv2.NORM_L1)` — sinon « Unsupported depth! Only CV_8U » ou
  échec silencieux. (Constat 15/09/2026, expérience débruitage.)
- **OpenCV 5 refuse de débayeriser une image flottante** (`depth == CV_8U
  || CV_16U` exigé, sinon `cv2.error`). Toute image float32/float64
  (master dark/flat, empilement, sortie GraXpert/BXT) doit être traitée
  comme mono sans tenter de débayerisation — et la devinette Bayer doit
  opérer sur l'image ENTIÈRE d'origine, jamais sur une copie flottante.
  (Constat v2.2.2 : « Lecture impossible » sur master dark float32 et
  brutes uint16 comptées illisibles — bug latent révélé par la montée
  d'opencv-python en 5.0.0.)
- **Un symptôme anormal peut venir de l'interpréteur, pas du code** :
  sur Windows, `python3` ≠ `python` (Store vs venv). Vérifier
  `sys.executable` avant de chercher un bug applicatif.
- **GraXpert (CLI 3.1.0rc2) lit les FITS couleur avec les canaux sur
  NAXIS3** (astropy data = (C, H, W)), alors que la convention astropy
  standard écrit NAXIS1=3. Un RGB « standard » est déformé à la lecture :
  crash `cv2.resize !dsize.empty()` (boîte de dialogue modale cx_Freeze)
  avec l'interpolation AI, ou sortie dégénérée (W, 3) avec RBF ; le mono 2D
  n'est pas concerné (d'où des succès intermittents trompeurs). Parade :
  entrée RGB écrite canaux-en-tête (`external/live._ecrire_entree`) +
  sortie retransposée (`_lire_sortie`). **PIÈGE AJOUTÉ (17/09/2026, jalon
  14)** : la parade n'avait été codée que dans le chemin GraXpert LIVE —
  la chaîne de TRAITEMENT EXTERNE (ui/app.py, `_run_external`) plantait
  toujours, invisible tant que le setup était mono. **Une parade documentée
  dans UN chemin doit être vérifiée dans tous les AUTRES chemins qui
  partagent le même outil externe** (et entre chaque étape d'une chaîne :
  normaliser la sortie puis réécrire canaux-en-tête). NB : l'entrée TIFF
  plante aussi chez GraXpert (imagecodecs LZW absent de leur build).
- **subprocess + boîte de dialogue modale cx_Freeze** : quand un outil
  packagé cx_Freeze plante, sa boîte d'erreur MODALE bloque le processus
  jusqu'au clic ; avec `subprocess.run(capture_output=True)` les tubes
  restent ouverts et `communicate()` ne revient JAMAIS, même après le
  timeout (le kill ne touche que cmd.exe, pas l'outil). Parade : sorties
  écrites dans des FICHIERS + Popen + `taskkill /F /T /PID` au délai (tue
  l'arborescence et la dialogue) — cf. `_run_bloquant_survivable` dans
  `avastack/external/live.py`.
- **Sortie Python pipée/redirigée sur Windows = cp1252 en mode strict** :
  un `print` contenant un caractère hors cp1252 (→, ≠, …) fait CRASHER le
  script, alors que la même sortie dans la console passe (console = UTF-8).
  Constaté sur les scripts de test : un test qui réussit en direct peut
  « échouer » via un pipe (`| Select-Object`). Parade : en tête des scripts
  de test, `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`.
- **Une transformation auto-consistante n'est pas une bonne transformation**
  (constat réel du 17/09/2026, jalon 13 — alignement des frames) : un
  consensus de 6 correspondances peut être un motif répété du champ qui
  passe les seuils. Toujours contre-vérifier par APPARIEMENTS MUTUELS
  (plus proche voisin des DEUX côtés), et RELEVER le seuil quand la décision
  sert d'ANCRE (1er alignement sans prédiction : 8 mutuels au lieu de 6) —
  une ancre faussée décale tout le repère de la session. Complément : deux
  NORMALISATIONS INDÉPENDANTES (percentiles calculés séparément par image)
  rendent une SSD insensible à la BONNE translation dès qu'une image a des
  bords non couverts — toute comparaison d'images doit PARTAGER les bornes
  de normalisation de la référence.
- **Live stacking, rejet des traînées de satellites** : le kappa-sigma
  CUMULÉ gonfle σ pour toujours (les pixels de la trace entrent dans les
  sommes de référence). La méthode robuste est celle type PixInsight :
  référence = **médiane / MAD d'une fenêtre glissante** (σ = 1,4826 × MAD),
  et **rejouer le warmup** (reconstruire sum/sumsq/wsum avec les poids
  robustes) quand la fenêtre se remplit — sinon le σ gonflé initial reste
  à vie. Implémentation : `LiveStacker` (avastack/processing/stacking.py),
  jalon 6 / v2.3.x.
- **Persistance de configuration au démarrage : restaurer de façon
  TOLÉRANTE** — chaque valeur lue est validée (bornes, énumération) et
  retombe sur le défaut si invalide. Une config.json corrompue, incomplète
  ou d'une version antérieure ne doit JAMAIS provoquer de crash ni de
  popup au lancement. Ordre de restauration parfois significatif : ici,
  VeraLux est restauré AVANT le moteur pour que la dépendance
  (GX live n'a de sens qu'avec le bon moteur) soit satisfaite.
- **GraXpert background-extraction sur un stack à bords d'écart de
  recouvrement = « coussin » clair sur ces bords** : les marches de fond
  partiellement exposées (zones sombres décalées où les frames ne couvrent
  pas tout le champ, ex. 3 côtés sur M33) parasitent le modèle de fond IA
  — bande claire périphérique + signal faible amputé, IDENTIQUE en live et
  en traitement externe. Toujours recadrer à l'intersection GÉOMÉTRIQUE
  RÉELLE des frames alignées AVANT tout retrait de gradient — méthode
  exacte via les matrices d'alignement (équivalent live du `-framing=min`
  de Siril, leçon astromatix : jamais d'heuristique de pixels) ;
  implémenté v2.3.3 (`LiveStacker.note_alignement` + `mean()` recadrée,
  toute la chaîne en hérite). NB : `-correction Division` PLAANTE dans
  GraXpert 3.1.0rc2 → rester en Subtraction. (Constat Alain 16/09/2026 :
  coussin disparu après recadrage manuel dans Siril ; recadrage auto
  validé par Alain, v2.3.3.)
- **Un « bruit × » mesuré par l'écart-type GLOBAL d'une image d'étoiles n'est
  pas du bruit** (constat réel du 16/09/2026, jalon 11 « netteté ») : un
  filtre d'accentuation NON LINÉAIRE laisse le FOND intact — voire le lisse
  un peu (Richardson-Lucy : MAD du fond ×0,92 et hautes fréquences ×0,89 à
  5 it) — alors que l'écart-type global monte ×1,32, uniquement parce que les
  PICS D'ÉTOILES sont amplifiés (pic ×2,35 pour un flux total conservé à
  ×1,000). Le « bruit ×1,14-1,39 » d'un banc d'essai jetable a donc été mal
  interprété et a coûté une ré-analyse. Règle : mesurer le bruit TOUJOURS sur
  une zone de FOND (MAD hors étoiles) et/ou en hautes fréquences (1re couche
  de la transformée starlet, cf. `denoise.estimer_sigma`) — et **noter la
  MÉTHODE de mesure à côté du chiffre** : un facteur de bruit sans sa
  définition est inexploitable. Corollaire : sur une image accentuée, ce
  qu'il faut surveiller à l'œil, ce sont les halos autour des étoiles, pas le
  fond.
- **Opération par pixel entre une image COULEUR et une carte 2D en numpy :
  `gain[..., None]` obligatoire** (constat réel du 16/09/2026, jalon 11) :
  `(H,W,3) * (H,W)` ne diffuse PAS — numpy aligne les DERNIÈRES dimensions —
  et l'erreur était SILENCIEUSE parce qu'enveloppée dans un repli sûr (le
  module renvoyait l'image d'entrée avec un message : la netteté ne
  s'appliquait tout simplement pas en couleur). Deux règles : multiplier par
  `gain[..., None]` et tester le mono ET la couleur ; et un test de
  fonctionnalité doit vérifier que le résultat est bien MODIFIÉ, pas
  seulement l'absence d'exception — un « repli sûr » peut masquer un bug de
  forme.

- **SDK natif d'une caméra : INTROSPECTION D'ABORD — ne jamais conclure à un
  bug matériel avant** (constat réel du 19/09/2026, MiniCam8M via le paquet
  `qhyccd`). Trois faits à établir avant toute autre piste, tous obtenus en
  quelques secondes de `dir()` / `inspect` : (1) `init_sdk()` ne doit être
  appelé qu'**UNE seule fois par process** — un second appel (ex. `lister()`
  puis `open()`) laisse l'état global du SDK incohérent et l'application se
  ferme sans message ; (2) le binding **n'expose AUCUNE fonction de
  libération** du SDK (`dir(qhyccd)` = `Camera`, `init_sdk`, `scan_cameras`
  + utilitaires de chemins : ni `release_sdk`, ni `ReleaseQHYCCDResource`) →
  l'état global est **IRRÉINITIALISABLE dans le process** : après un
  « Arrêter », une nouvelle ouverture ne reçoit PLUS JAMAIS de frame (relevé
  réel : 126 lectures sans frame, sans planter) et la seule sortie est de
  **relancer le programme** — limite qui vaut aussi pour l'application ;
  (3) un **crash natif (segfault) n'est JAMAIS rattrapable par un `except`
  Python** : il faut TRACER chaque étape dans un fichier (ici
  `%TEMP%\avastack_qhy_debug.log`) et isoler les appels risqués en
  **SOUS-PROCESSUS** (le scan QHY tourne ainsi, pour qu'un segfault du SDK ne
  tue pas l'interface). Corollaire : 5 secondes d'introspection ont répondu à
  des questions que des heures de tâtonnement matériel n'auraient pas
  tranchées.
- **AVANT d'interpréter un log de plantage, vérifier l'identité des fichiers
  RÉELLEMENT chargés** (constat réel du 19/09/2026). Un `begin_live` présent
  dans le log SANS AUCUNE ligne `set_resolution`, alors que le code était
  censé poser la ROI depuis deux versions, a été pris pour un bug de
  l'application — c'était une **copie PÉRIMÉE du module** sur la machine
  d'essai. Comme un fichier ancien **ignore silencieusement l'argument**
  qu'on lui passe, la case « imposer la ROI » cochée ne pouvait RIEN
  démontrer : les deux symptômes (plantage au démarrage, ROI « ignorée »)
  s'expliquaient par cette seule divergence de fichiers. Règle : tout outil
  de diagnostic autonome doit **AFFICHER au lancement** les chemins, dates et
  capacités (`set_resolution` présent ? signature de `open()` ?) des modules
  qu'il importe, et une **erreur explicite** doit remplacer l'ignorance
  silencieuse d'un paramètre ; sans cela, l'outil diagnostique un code qui
  n'est pas celui qu'on croit.
- **Un réglage RELU à l'identique ne prouve pas qu'il est APPLIQUÉ : seul son
  EFFET PHYSIQUE le prouve** (constat réel du 19/09/2026, gain/exposition
  QHY). `set_param` **accepte toute valeur** puis la relit telle quelle : un
  balayage « tout accepté » (gain 0→100, offset, USB traffic) ne révèle donc
  **AUCUNE borne réelle** et n'est pas concluant — c'est du simple STOCKAGE,
  pas une validation. Le seul verdict fiable est l'effet mesurable :
  exposition 2000 ms → **0,5 fps exactement** (donc réellement appliquée),
  tandis qu'un balayage sans refus laisse la plage **INCONNUE**. À retenir :
  (a) chercher l'effet physique (cadence, température du capteur, niveau
  d'image) avant de croire un read-back ; (b) ne jamais déduire une plage de
  réglage d'un balayage qui n'échoue jamais ; (c) une valeur « acceptée » par
  un SDK sans doc de bornes reste INCONNUE tant qu'un effet n'est pas mesuré.

- **AVANT de conclure qu'une fonctionnalité MANQUE, introspecter AUSSI la
  DLL native embarquée sous le binding Python** (constat réel du 19/09/2026,
  roue à filtres de la MiniCam8M). Le paquet PyPI `qhyccd` n'expose que trois
  entrées (`Camera`, `init_sdk`, `scan_cameras` + des utilitaires de chemins)
  et AUCUNE API de roue à filtres — ce qui laissait croire qu'il faudrait
  réimplémenter tout le cycle SDK en ctypes (init, scan, ouverture du handle,
  code de la roue). Or la DLL que ce paquet EMBARQUE et charge lui-même
  (`site-packages/vendor/lib/windows-x86_64/qhyccd.dll`, **SDK QHYCCD
  26-06-04**) exporte l'API C complète : `IsQHYCCDCFWPlugged`,
  `GetQHYCCDCFWStatus`, `SendOrder2QHYCCDCFW`, `GetQHYCCDParam`,
  `SetQHYCCDParam` — et aussi `ReleaseQHYCCDResource`, ABSENTE du binding, ce
  qui prouve que la limite « état global du SDK irréinitialisable dans le
  process » vient du BINDING et non de la bibliothèque. Mieux : le pilotage
  utile passait par de simples CONTRÔLES déjà exposés en Python
  (`get_param(44)` = nombre de positions, `set_param(17, 48 + n)` =
  position). Corollaire : l'introspection d'un binding se fait à DEUX niveaux
  (surface Python ET exports de la DLL), le code source de la crate Rust qui
  le sous-tend (ici `qhyccd-rs`, MIT/Apache) documente ce que la surface Python
  ne montre pas, et la VERSION du SDK embarqué doit être relevée (un modèle
  récent n'est pas forcément implémenté par une DLL ancienne).
- **La correspondance « valeur d'API ↔ position PHYSIQUE » ne se déduit ni
  d'une relecture ni d'une documentation : seul l'effet sur le matériel
  tranche** (constat réel du 19/09/2026, position de la roue à filtres QHY). La
  position s'échange en ASCII : la doc QHY et le pilote INDI encodent la
  position 1 en `'0'`, tandis que la crate `qhyccd-rs` (donc le binding Python
  utilisé) l'encode `'1'` — un cran d'écart entre deux implémentations de la
  MÊME commande, et c'est la convention `48 + n` qui a été constatée sur la
  caméra (`ctrl 17 = 49` alors que la roue était sur le filtre 1). Aucune
  relecture ne distingue ce décalage : seul un repère VISIBLE dans l'image
  (slot vide, filtre opaque, niveau de fond) dit quel slot physique a
  réellement été appelé.
- **Un banc/outil qui RÉUTILISE le code de l'application doit charger ce code
  de façon DIAGNOSTIQUÉE, et refuser proprement au lieu de planter** (constat
  réel du 19/09/2026, banc Player One sur miniPC : banc v2.16 copié à côté
  d'une application installée v2.15 → `AttributeError` nu sur un symbole que
  l'ancienne copie n'expose pas). Depuis que la sonde du banc vit DANS
  l'application (une seule définition — deux copies finissent par diverger),
  le banc vérifie les symboles attendus à l'import, affiche la version lue +
  chemins/dates des fichiers réellement chargés + les symboles manquants, et
  refuse l'opération concernée AVEC le remède exact (les 2 fichiers à copier,
  ou réinstaller). Il ne faut PAS recopier une version locale des définitions
  « pour que ça marche » : c'est la duplication qui a créé le problème, et le
  message clair qui est le correctif durable.
- **Le TYPE d'une valeur lue d'un SDK doit venir de la MÊME routine qui l'a
  énumérée (cache unique) — jamais d'un second parcours parallèle** (constat
  réel du 19/09/2026, Uranus-C Pro : la température s'affichait
  « -1073741824 » — ce sont les bits du flottant -2.0 lus comme entier — et
  « Exp » 1202590843). Cause : le banc réénumérait les contrôles en dehors de
  la sonde, dont le cache de types restait donc VIDE, et toute valeur
  flottante était relue en `long` SANS AUCUN message d'erreur. Deux leçons
  annexes du même constat : (a) les tableaux à taille FIXE des SDK
  (`imgFormats_[8]`) n'ont pas toujours un vrai terminateur — leur remplissage
  (zéro = `RAW8`, valeur d'énumération valide) doit être DÉDUPRIQUÉ et non
  tronqué ; (b) les attributs d'un SDK peuvent être INCOHÉRENTS avec eux-mêmes
  (défaut 11,40 hors de ses propres bornes [0, 10]) : afficher le défaut en le
  présentant comme « lu » est trompeur — distinguer courant / défaut / bornes
  et signaler l'incohérence. Et la DLL peut exposer des contrôles AU-DELÀ de
  l'enum documentée (contrôle 31 « Exp » en secondes, max 7200 s, alors que le
  contrôle 0 annonce 2000 s en µs) : les noms viennent d'abord du SDK, la
  table locale n'est qu'un repli.

- **TOUT thread secondaire doit avoir un try/except qui remonte au JOURNAL
  de l'interface** (constat réel du 20/09/2026, flux du banc SVBONY) : une
  exception non interceptée dans un thread tue le thread SANS AUCUN message
  (ni console quand le programme a une fenêtre) — le programme paraît
  simplement « morte » et le journal s'arrête net à la dernière étape
  réussie. Symptôme signature : la dernière ligne du journal est une action
  de démarrage, et ni le message d'échec attendu ni l'abandon ne viennent.
  Correctif systématique : envelopper la boucle du thread, logger le
  traceback complet (`traceback.format_exc()`) via la file de l'UI, et
  journaliser périodiquement (1×/s) les boucles d'attente muettes — un
  traceback ainsi journalisé a désigné la cause exacte du premier coup
  (`access violation` dans `SVBGetVideoData`).
- **La relecture d'un SDK peut MENTIR, et son buffer de réception peut être
  écrit SANS vérification de taille : sur-allouer et déduire le format de
  la DONNÉE** (constats réels des 19-20/09/2026, SV305C via
  SVBCameraSDK.dll v1.13.4) : `SVBSetOutputImageType(RGB24)` renvoie OK,
  la relecture `SVBGetOutputImageType` répond RAW8, et `SVBGetVideoData`
  écrit sa frame AU-DELÀ du buffer alloué « nominal » → access violation
  (crash avec 2,1 Mo nominal RAW8, PUIS avec 6,2 Mo RGB24 ; le format
  interne réel est **RGB32, 4 o/pixel**). Méthode fiable : buffer
  initialisé à zéro et sur-dimensionné (pire cas = 4 o/pixel + marge),
  puis format réel DÉDUIT de la donnée par le DERNIER OCTET NON NUL (fin =
  dernier indice non nul + 1 ; octets/pixel = ceil(fin / surface)) —
  « frame entièrement à zéro » = image noire, à signaler. Et les PARAMÈTRES
  du SDK peuvent RECHARGER leurs valeurs sauvegardées au redémarrage de la
  capture (expo posée 30 ms revenue à 2000 ms après stop/start) →
  désactiver l'auto-sauvegarde si le SDK l'expose (`SVBSetAutoSaveParam(0)`)
  et reposer les réglages après chaque restart.
- **Une variable Tkinter (`BooleanVar`, `StringVar`…) ne peut être LUE que depuis
  le THREAD D'INTERFACE** : toute lecture depuis un thread de travail lève
  `RuntimeError: main thread is not in main loop` (ou rend une valeur périmée
  silencieuse sur d'autres plateformes). Constat réel (26/09/2026, v2.38.0) :
  l'option « Rendu pleine résolution », lue par la boucle d'acquisition pour
  mémoriser l'empilement complet, faisait planter le cycle d'acquisition — plus
  AUCUNE sauvegarde ne sortait, et c'est le banc de sauvegarde qui l'a attrapé.
  Un état partagé entre l'interface et les threads de travail doit vivre dans un
  ATTRIBUT PYTHON mis à jour par l'interface ; la variable Tk n'est que son
  reflet d'affichage.
- **Après un traitement SÉLECTIF (masque, poids de structure…), un σ ne mesure
  plus le NIVEAU de ce qui reste : il mesure la QUEUE.** Constat réel
  (26/09/2026, v2.37.5) : la réduction de bruit chromatique épargne désormais les
  pixels structurés (~0,2 % d'entre eux gardent tout leur grain) → le σ du grain
  restant valait ×0,092 alors que le grain réellement restant valait ×0,027
  (MAD). Deux bancs donnaient donc un faux échec. Règle : mesurer un NIVEAU au
  MAD (×1,4826) et garder le σ imprimé à côté, comme information.
- **Une scène de banc doit reproduire le MÉCANISME du défaut, pas seulement son
  allure.** Constat réel (26/09/2026, banc jalon 67) : l'étoile synthétique était
  écrêtée à 1,0 par un `clip` — cœur BLANC, donc aucune couleur à déposer ;
  l'anneau de couleur ne se reproduisait pas et le TÉMOIN ne discrimininait rien
  (+5 % au lieu de +140 % sur les données réelles). Les valeurs à respecter se
  relèvent sur le fichier RÉEL : cœur ~0,5 pour un ciel ~0,03, AUCUN écrêtage
  haut, PSF plus FINE que le flou testé, grain ~2 % du niveau de ciel.
- **En mode logD imposé, les diagnostics du moteur VeraLux affichent une ancre
  `0,000000` : c'est un ARTEFACT**, pas une mesure (l'ancre n'est calculée que
  pendant la résolution du logD, sur un sous-échantillon). Ne jamais en conclure
  « l'ancre du fichier est nulle ». L'ancre réellement utilisée se mesure en
  rejouant les méthodes du moteur — comparaison bit à bit possible (écart
  0,000000), à condition de passer le MÊME `target_bg` que la chaîne (avec le
  défaut 0,20 au lieu de 0,16, l'écart monte à 0,068).
- **Une option qui prétend rendre « l'écran identique au fichier » doit être
  verrouillée par un banc qui compare les DEUX CHEMINS sur la MÊME image, avec
  égalité exigée (pas une tolérance).** Constat réel (26/09/2026, v2.38.0) :
  c'est cette assertion (écart 0) qui a révélé que `rendu_pleine_resolution` ne
  transmettait pas le fond cible au moteur — le fichier était plus clair que
  l'écran de 9,6 niveaux de 8 bits en moyenne (fond 0,197 au lieu de 0,159),
  sans que l'écart de résolution, lui, l'explique.

- **« NE RIEN PASSER » À UN CLI TIERS N'EST PAS NEUTRE — et la source qui fait
  foi est le `--help` de l'outil INSTALLÉ.** Constat réel (27/09/2026, v2.38.3) :
  la commande BXT ne passait que `--ash -0.3` ; le volet « objets »
  (`--sn/--sharpen-nonstellar`) restait donc à son défaut de **0,50**, invisible
  dans le champ de commande — et c'est lui qui ajoutait un moucheté chromatique
  2-8 px (mesuré ×1,28 contre la vue live ; ×0,48 avec 0,3 ; σ/MAD du bleu
  2,95 → 1,49). La page d'aide web était TRONQUÉE : c'est `rc-astro bxt --help`
  (CLI v2.6.9 installé chez Alain) qui a donné noms, plages ET défauts.
  Corollaires : écrire les paramètres EXPLICITEMENT dans la commande par défaut,
  et les CONSIGNER dans le fichier (en-tête) — sinon un fichier ne dit pas de
  quelle chaîne il vient.
- **COMPARER DEUX IMAGES LINÉAIRES NON ÉTIRÉES REND LA MESURE AVEUGLE.**
  Constat réel (27/09/2026) : `auto_unflip` comparait les images linéaires brutes
  (corrélation de Pearson, sous-échantillonnage « 1 pixel sur N ») et mesurait
  +0,1085 (bonne orientation) contre +0,1212 (miroir) — écart +0,0127, SOUS la
  marge de 0,05, donc aucune décision : le résultat du CLI rc-astro est resté en
  MIROIR VERTICAL dans les fichiers ET à l'écran (v2.373, v2.38.0, v2.38.1),
  parce que ce qui n'est PAS partagé (grain, texture d'outil) écrase tout — mesuré :
  la variance hautes fréquences vaut 4× les basses. Sur les MÊMES images, la
  comparaison ÉTIRÉE et NORMALISÉE (percentiles 0,5/99,5 puis racine, moyenne par
  INTER_AREA) donne +0,539 contre +0,996 : décision franche. Règle : normaliser et
  étirer AVANT de corréler, et exiger une marge LARGE (+0,20 : un vrai miroir
  gagne de +0,27 à +0,46, une orientation correcte reste sous 0,05).
- **DEUX FICHIERS DU MÊME CHAMP PEUVENT NE PAS ÊTRE SUPERPOSÉS AU PIXEL.** Le ⚡
  travaille sur un INSTANTANÉ de l'empilement, plus récent que les fichiers de
  l'empilement déjà enregistrés : grain et textures fines diffèrent, et une
  comparaison « même ciel » au pixel près devient fausse (mesuré : 11 blocs
  communs trouvés sur 858 au lieu de 84 après redressement). Vérifier ORIENTATION
  et alignement avant toute mesure, et FIGER l'empilement pour un A/B propre —
  sinon on attribue à un réglage ce qui vient du nombre de poses.
- **LOCALISER UN DÉFAUT PAR ÉCHELLE ET PAR CLASSE DE FOND AVANT D'ACCUSER UN
  MAILLON.** L'échelle dit le coupable : 1-2 px = grain, 2-8 px = texture
  d'outil (IA/déconvolution), 8-30 px = plaques. Constat réel (27/09/2026) : le
  moucheté du fichier traité était ×1,27-1,31 PARTOUT (ciel pur comme halo de
  galaxie) — donc PAS un défaut « des structures » mais une texture ajoutée
  globalement —, tandis que le grain fin était RÉDUIT (×0,76) : le débruitage
  travaillait. C'est cette mesure qui a orienté vers le volet « objets » de BXT.
- **LE RAPPORT σ/MAD DÉCRIT L'ALLURE DU BRUIT, à mesurer sur le MÊME ciel.**
  σ/MAD ≈ 1,5 : du grain ; ≈ 3 : du moucheté « en plaques » (mesuré sur un fond
  réel : 2,95 à `--sn 0,50`, 1,49 à 0,3). Le calculer sur des blocs de fond
  COMMUNS aux deux images (le masque se choisit une fois, pas par image), sinon
  deux ciels différents sont comparés.

## Leçons générales transposables (projet pipeline siril)
- **Toute fonction opérant sur des données image : vérifier si elle suppose
  implicitement un nombre de canaux fixe** avant de la réutiliser sur un
  chemin mono/narrowband (bug réel : tableau (H,W) mono indexé comme
  (3,H,W) → image noire, sans aucune erreur).
- **Une formule "purement additive" reste fausse si une entrée peut être
  négative** : une donnée passée par interpolation/recalage géométrique ne
  doit jamais être supposée rester dans [0,1] sans clip explicite (artefact
  en anneaux noirs, constat réel).
- **Une propriété mathématique d une formule n est garantie que si le
  DOMAINE de ses entrées est lui-même garanti.**
- **Vérifier l existence d un mécanisme natif dans l outil sous-jacent avant
  d investir dans le raffinement itératif d un contournement maison**, même
  après plusieurs itérations "presque bonnes".
- **Un `%` littéral non échappé (`%%`) dans un texte d aide `argparse`**
  plante tout le script au démarrage sur Python 3.14+ (validation eager),
  invisiblement sur 3.13 — et `ast.parse()` NE DÉTECTE PAS ce bug.
- **Un fichier de sortie à nom stable peut être mis en cache navigateur** :
  ajouter un paramètre `?v=<mtime>` aux URL si exposition web un jour.
- **`subprocess` sans `shell=True` protège l OS, pas le système de fichiers
  applicatif** : toute valeur provenant de l extérieur et utilisée comme
  chemin doit être validée contre la racine attendue AVANT usage. Et valider
  le CHEMIN ne protège pas des CARACTÈRES du nom lui-même (guillemets,
  sauts de ligne…) s il est ensuite interpolé dans un autre langage de
  script — les deux vérifications sont indépendantes.
- **Une fenêtre de mesure ou de calcul FIXE appliquée à un objet de taille
  VARIABLE biaise la mesure** : la fenêtre doit suivre la taille apparente de
  l objet (dimension de sortie du détecteur, taille estimée, etc.). Un fond
  de fenêtre trop vaste finit par peser autant que le signal recherché
  (constat réel : FWHM surestimée de 170 % — étoile de ~1,2 px mesurée dans
  une fenêtre fixe de ±9 px, dont presque tout le contenu était du bruit de
  fond non retranché ; correction = fenêtre adaptative + soustraction du fond
  réellement mesuré + moyennage par anneau).
- **Sur un profil ou une statistique échantillonné(e) en « bins », les bins
  VIDES doivent être sautés explicitement** : les compter comme des valeurs
  invalides (NaN) fait perdre des mesures parfaitement valides (constat réel :
  45 % des étoiles déclarées « sans retombée à mi-hauteur » alors que leur
  profil était net — il faut interpoler vers le dernier bin FINI au-dessus du
  seuil, pas vers le bin voisin immédiat ; un échantillonnage par anneaux est
  clairsemé par nature dès que le rayon grandit).
- **Toute implémentation d'un algorithme connu doit être confrontée à une
  RÉFÉRENCE INDÉPENDANTE**, et cette comparaison doit RESTER dans les tests
  permanents (constat réel du 16/09/2026, jalon 11 : la Richardson-Lucy du
  projet coïncide à moins de 1e-5 avec une RL écrite en numpy pur —
  convolution 2D explicite, bords réfléchis — à 1, 3, 5 et 10 itérations).
  Sans cette référence, un « ça marche » visuel ne distingue pas la vraie
  formule d'une variante approximative (damping, ordre des convolutions,
  normalisation du noyau, gestion des bords).
- **Quand un appariement sert d'ANCRE pour tout le reste, les appariements
  doivent être MUTUELS et le seuil RELEVÉ en conséquence** (constat réel du
  jalon 13 : étoiles « en plusieurs points puis en traînées » à 1280 mm) —
  accord d'Alain, 20/09/2026. Un appariement non mutuel (A → B sans B → A)
  injecte des correspondances fantômes qui faussent la transformation
  estimée ; et comparer deux images chacune normalisée par SES propres
  bornes (min/max locaux distincts) rend une SSD aveugle — les bornes
  doivent être PARTAGÉES (min/max communs aux deux images) avant toute
  comparaison pixel à pixel. Les deux règles ensemble : ancre fiable =
  appariements mutuels à seuil relevé sur images normalisées de façon
  commune.
- **Valider les PLACEHOLDERS d'un gabarit AVANT la substitution**
  (jalon 24, commandes des outils externes GraXpert/BXT) — accord d'Alain,
  20/09/2026 : vérifier que les champs attendus ({input}, {output},
  {outbase}…) sont présents et bien formés AVANT d'y injecter les chemins,
  et rejeter une commande incomplète avec un message clair. Une substitution
  dans un gabarit qui n'a pas la place produit une commande tronquée ou
  fausse SILENCIEUSEMENT — découverte à l'exécution (voire jamais, si le
  résultat est simplement mauvais) au lieu d'être attrapée à la
  configuration.

- **La couleur d'un pixel est un RAPPORT, pas un écart absolu** (constat réel
  d'Alain, 26/09/2026, v2.37.3 — « les étoiles brillantes rouges et bleues ont un
  halo gênant », visible aussi après BlurXTerminator). Lisser une chroma
  ABSOLUE (les Cr/Cb de YCrCb tels quels) autour d'une étoile mélange la couleur
  de son CŒUR avec celle du CIEL voisin et dépose ce mélange sur ses AILES
  FAIBLES, où un minuscule écart devient une énorme couleur. MESURÉ sur son
  empilement M31 (anneau r = 3..9 px, en multiples du niveau de ciel local) : la
  couronne d'une étoile rouge passait de R 41,3 à 34,9 et de B 19,9 à 23,6
  (+19 %) ; celle d'une étoile bleue de R 3,53 à 1,74 (−51 %) avec B 2,72 → 3,92
  (+44 %) — un HALO BLEU créé là où il n'y en avait aucun (R/B 1,30 → 0,44) —
  alors que la LUMINANCE ne bougeait que de ±6 % : c'est un halo de COULEUR. Le
  correctif lisse le RAPPORT de couleur (chroma ÷ échelle locale, l'échelle étant
  bornée par la luminance DU PIXEL — le fond gardant, lui, sa luminance LISSÉE
  pour que le bruit de luminance ne se re-dépose pas dans la couleur) : le grain
  coloré du fond tombe toujours (×0,17), le halo redevient celui de l'image non
  traitée (R/B 1,32 contre 1,30), et l'écart RENDU sur 6 étoiles brillantes ne
  dépasse plus 1,9 point de % du pic contre 24,5 points avant. Vérification de
  méthode à refaire : à force ≈ 0, la même conversion YCrCb→RVB rend l'image AU
  BIT PRÈS — c'est le FLOU qui est en cause, jamais la conversion.
- **Toute échelle SPATIALE (rayon de flou, seuil de détection, taille de fenêtre)
  doit suivre la RÉSOLUTION** (constat réel d'Alain, 26/09/2026, v2.37.3/v2.37.4).
  La même valeur en PIXELS appliquée à un APERÇU RÉDUIT étale relativement plus
  qu'aux fichiers : l'aperçu de l'appli est réduit d'un facteur 1600/largeur
  (0,417 sur son image de 3838 px) alors que le rayon restait fixé à 3 px → 3 px
  d'aperçu = 7,2 px pleine résolution, soit un halo 2,4 fois plus large par
  rapport aux étoiles à l'écran que dans le fichier (mesuré — c'est exactement ce
  qu'Alain voyait). Le rayon se règle désormais en pixels PLEINE RÉSOLUTION
  (curseur « Rayon de référence », 0,5 à 8 px) et l'APERÇU le ramène à son
  échelle (`couleurs.rayon_chroma_apercu`) ; les fichiers (rendu « tel que vu »,
  chaîne externe) l'utilisent tel quel. Règle générale : l'écran doit montrer ce
  que le fichier contient — et un plancher du type « jamais moins de 0,6 px »
  fausse la fidélité d'un PETIT rayon, à vérifier à chaque fois.

- **Une correction appliquée EN FIN de chaîne externe est invisible à l'outil qui
  la précède** (constat réel d'Alain, 26/09/2026, v2.37.3 : « en général, c'est un
  halo killer pourtant », à propos de BlurXTerminator). L'ordre de la chaîne
  externe place les corrections couleur (cases 7/8) APRÈS BXT
  (`ui/app._run_external`) : un halo FABRIQUÉ par l'une de ces corrections ne peut
  pas être corrigé par l'outil, qui a travaillé sur une image encore saine. Trois
  corollaires du même constat : (a) une correction OPT-IN n'est pas INOFFENSIVE
  parce qu'elle est décochée par défaut — celle-ci fabriquait un halo de couleur
  sur les étoiles vives ; (b) quand un outil externe a une option DÉDIÉE au
  symptôme, la vérifier AVANT de suspecter le reste : BXT a bien
  `--ash`/`--adjust-star-halos` (−0,5…+0,5), mais son défaut est **0,00 = aucun
  ajustement** et la commande par défaut de l'appli ne le passe pas (mesuré sur un
  extrait réel : `-0.30` réduit encore, `+0.30` conserve) — « halo killer » n'était
  donc pas en cause, il n'était simplement pas activé ; (c) les vraies sorties
  d'un outil doivent être VÉRIFIÉES à la lecture : BXT rendait l'image en MIROIR
  VERTICAL (corrélation 0,94 avec l'entrée retournée, 0,00 sans) et recadre les
  valeurs dans [0,1] — deux faits qui invalident toute mesure faite sans
  redresser ni normaliser (`images.auto_unflip` le fait déjà).
- **Quand une formule change de NATURE, la propriété du banc doit être ré-énoncée
  honnêtement — et une FIDÉLITÉ se mesure PAR RAPPORT à son plancher de mesure**
  (constat de méthode du 26/09/2026, v2.37.3/v2.37.4). Le banc du jalon 63
  affirmait que la part demandée du grain coloré disparaissait EXACTEMENT
  (×1−force) : vrai de l'ancienne formulation (un mélange linéaire de chroma),
  faux de la nouvelle (normalisée par la luminance locale) — l'assertion a été
  remplacée par une BORNE HAUTE documentée (au pire +8 points ; mesuré 7,0 à
  force 1,0 sur un fond teinté) plutôt que d'infléchir la formule pour satisfaire
  un test devenu faux. De même, pour comparer un APERÇU réduit à une image pleine
  résolution, le double redimensionnement introduit sa propre erreur (mesurée 5 à
  6 % sur la couleur d'une couronne) : la comparaison doit se lire PAR RAPPORT à
  ce plancher (mesuré sur la même image SANS le traitement), sinon on attribue au
  traitement une erreur qui vient de la mesure. Corollaire : un banc qui veut
  prouver qu'il DISCRIMINE doit embarquer un TÉMOIN (ici l'ancienne formule
  ré-écrite dans le banc, qui doit échouer là où la nouvelle passe).

## Maintenance des fichiers de connaissance (CLAUDE.md)

Ce fichier sert de mémoire à long terme pour les agents IA. **Règle
fondamentale : l agent ne modifie JAMAIS ce fichier de son propre chef.** Il
doit : (1) identifier une information digne d être retenue, (2) proposer la
mise à jour dans la conversation avec le texte exact, (3) attendre la
confirmation explicite d Alain avant d agir, (4) confirmer l action réalisée.

**EXCEPTION explicite (Alain, 20/09/2026)** : quand Alain demande à l agent
de « noter » ou « se souvenir » de quelque chose, il autorise IMPLICITEMENT
la mise à jour de CLAUDE.md si elle est pertinente : écrire l entrée dans
la section appropriée, la signaler dans la réponse, sans attendre une
confirmation séparée. Le dialogue de proposition reste la voie normale pour
les ajouts qu Alain n a PAS lui-même demandé de noter.

Déclencheurs de proposition : nouvelle erreur récurrente, nouveau
comportement inattendu, découverte architecturale, modification importante
du code, piège rencontré sur un outil externe. Cible : section « Pièges »
(à créer le cas échéant) ou ajustement des conventions.

**Exemple de dialogue** :

> **Agent** : « J ai constaté que [constat]. Je propose d ajouter à CLAUDE.md :
> [texte]. Puis-je procéder ? »
> **Alain** : « Oui, ajoute-le. »
> **Agent** : « ✅ Entrée ajoutée. »
