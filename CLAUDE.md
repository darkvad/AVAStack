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
(GitHub, créé le 15/09/2026, **PUBLIC depuis le 29/09/2026** — licence MIT).
Branche unique `master`, poussée et en suivi (`git push` seul suffit, pas
besoin de préciser origin/master). Aucun fichier sensible ou volumineux n'est
suivi (ni config.json, ni venv, ni build/dist) — garder ainsi lors des futurs
ajouts au `.gitignore` ; **conséquence du passage en PUBLIC** : rien de
personnel ne doit entrer dans le dépôt non plus (les `.dll`/`.so` constructeurs
de la racine ne sont PAS suivis : garder ainsi), et **les documents publics ne
citent jamais le mainteneur** (cf. « Conventions non-négociables »).

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

# Lancer un BANC : TOUJOURS l'interpréteur du venv (cf. piège ci-dessous)
.\venv\Scripts\python.exe bancs\_test_histo_jalon75.py

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

**PIÈGE BANCS (constat réel du 28/09/2026)** : `python` NU (sans venv activé)
lance le Python du SYSTÈME (`C:\Python314`) — **sans numpy** : un banc meurt
alors sur `ModuleNotFoundError: No module named 'numpy'`, ce qui n'est PAS une
panne du banc. Lancer les bancs par l'interpréteur du venv, en clair :
`.\venv\Scripts\python.exe bancs\_test_histo_jalon75.py`.

**INSTALLATEUR WINDOWS EN PAQUET ZIP (jalon 88, 01/10/2026)** : à côté de
l'installateur Inno Setup (`.exe`, NON SIGNÉ) existe un paquet
`avastack-setup-<version>-windows.zip` (producteur
`installer/windows/build_avastack_zip.py`, script d'installation
`installer/windows/install_avastack.ps1`, lancé par `install_avastack.bat`). Il
fait la MÊME installation **sans exécuter aucun binaire à nous** : c'est la
réponse au blocage du `.exe` par le **Contrôle intelligent des applications**
(Smart App Control) d'un Windows 11 neuf — « Impossible d'exécuter un fichier
depuis le dossier temporaire. Abandon de l'installation. Erreur 4551 : une
stratégie de contrôle d'application a bloqué ce fichier. » (message INTÉGRÉ
d'Inno Setup ; Smart App Control ignore « Exécuter quand même » et n'a AUCUNE
exception par application : remède immédiat = l'arrêter, remède durable = signer
l'installateur).

- **Le Python du Microsoft Store est TOUJOURS ignoré** par ce script (consigne
  d'Alain, 01/10/2026), même s'il est présent : avec lui, `venv`+`pip` échoue
  (redirection de chemins → venv écrit sous `...\AppData\Local\Packages\
  PythonSoftwareFoundation...` → `No pyvenv.cfg file` → « Code retour : 1 », vu
  sur un poste de testeur en v2.45.0). Un Python est « du Store » si son chemin
  contient `\WindowsApps\` ou `\Packages\PythonSoftwareFoundation`. Sans Python
  utilisable, le script télécharge python.org (`InstallAllUsers=0`,
  `Include_tcltk=1`).
- **Les paquets pip caméras ne doivent JAMAIS faire échouer l'installation** :
  `qhyccd`/`zwoasi` sont retirés de la liste principale et tentés séparément, en
  avertissement seulement.
- **`$ErrorActionPreference='Stop'` + commande NATIVE écrivant sur `stderr` =
  ERREUR TERMINANTE (PowerShell 5.1).** Mesure du 02/10/2026 : le contrôle
  « import numpy, cv2, PIL » TUAIT l'installation au lieu d'avertir, et la sortie
  de `New-Venv` (qui doit rester une valeur unique) aurait été capturée avec le
  texte de pip. Règle : appel natif dont on veut seulement LIRE le résultat →
  `$ErrorActionPreference = 'Continue'` ramené ensuite (cf. `Test-ImportModules`) ;
  sortie à AFFICHER sans entrer dans le pipeline → `| Out-Host`.
- **Deux pièges PowerShell mesurés** : ① dans une FONCTION,
  `$MyInvocation.MyCommand.Path` est VIDE (le chemin du script n'existe qu'à la
  portée du script) → capturer `$PSScriptRoot` UNE fois ; ② `exit (Main)`
  CAPTURE la sortie de pipeline de `Main` au lieu de l'afficher (`-Aide`
  n'affichait plus RIEN) → passer le code par une variable de portée script.
- Le script a `-Aide` et `-Simulation` (montre le Python choisi **sans rien
  modifier**) : le banc `bancs/_test_installeur_windows_zip_jalon88.py` l'exécute
  réellement et vérifie que le Python du Store n'est jamais « retenu ».

**EMPREINTE DU PYTHON TÉLÉCHARGÉ, VÉRIFIÉE (v2.48.2, jalon 89)** : les DEUX
installateurs Windows contrôlent le **SHA-256** de l'installateur python.org
**AVANT de l'exécuter**, avec **une seconde tentative**, et le disent en clair si
le fichier est incomplet. Motif : chez un testeur l'installation s'est arrêtée sur
« Erreur 4551 : une stratégie de contrôle d'application a bloqué ce fichier » — et
le seul fichier exécuté depuis `%TEMP%` est celui-là. La MESURE a montré que
**Smart App Control APPLIQUÉ laisse exécuter depuis `%TEMP%` un fichier SIGNÉ**
(banc `bancs/_diag_execution_temp.ps1` : « EXECUTION AUTORISEE ») ; un
téléchargement TRONQUÉ était donc une cause restante plausible.

- **Inno Setup sait calculer un SHA-256 depuis la 6.1** :
  `GetSHA256OfFile(const Filename: String): String` (lève une exception en cas
  d'échec). Sa **casse n'est pas documentée** → `Lowercase()` des DEUX côtés.
- **La valeur est épinglée dans les deux fichiers** (`#define PythonSha256` côté
  Inno, `$PY_SHA256` côté PowerShell) : c'est le banc du jalon 89 qui les empêche
  de diverger, et il VÉRIFIE en plus l'empreinte déclarée contre le fichier réel
  quand celui-ci est présent dans `%TEMP%`.
- **Provenance de la valeur** (à refaire si la version de Python change) : la
  relever d'un téléchargement dont la **signature Authenticode est Valide** et
  signée « Python Software Foundation » — jamais d'un souvenir ni d'un site tiers.
- **`-Desinstaller` ne touche plus aux raccourcis s'ils n'ont pas été créés**
  (marque écrite dans `VERSION.txt`, relue à la désinstallation) : une
  installation d'essai faite en `-SansRaccourci` ne doit pas effacer les
  raccourcis d'une AUTRE installation — défaut constaté le 02/10/2026.

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

# Rebuild du paquet macOS (même règle)
python installer\macos\build_avastack.py
```

**NOM DES INSTALLATEURS : toujours le numéro de version (consigne d'Alain,
27/09/2026)** — c'est le nom de l'artefact qui dit ce que teste Alain, et deux
versions ne doivent JAMAIS s'écraser. Registre :

| Plateforme | Artefact | Producteur |
| --- | --- | --- |
| Windows | `installer/windows/output/avastack-setup-<version>.exe` | `build_avastack.ps1` (ISCC + `/DAppVersion`) |
| Linux | `installer/linux/output/avastack-setup-<version>-linux.tar.gz` | `installer/linux/build_avastack.py` |
| macOS | `installer/macos/output/avastack-setup-<version>-macos.tar.gz` | `installer/macos/build_avastack.py` |

Règles qui vont avec :
- la version vient TOUJOURS de `AVASTACK_VERSION` (`avastack/__init__.py`) —
  jamais recopiée à la main dans un nom de fichier ; `avastack.iss` **refuse**
  de compiler sans `/DAppVersion` (`#error`) et les packers Linux et macOS la
  lisent dans le source ;
- on ne renomme jamais un artefact après coup, et on ne remplace pas un
  artefact d'une version antérieure (l'ancien reste à côté : c'est lui qui sert
  de repli en cas de régression) ;
- après toute passe de code, annoncer en fin de réponse le CHEMIN EXACT de
  l'artefact reconstruit (version comprise) ;
- **TAG ET ARTEFACT AJOUTÉ APRÈS COUP : on ne DÉPLACE jamais un tag publié
  (décision d'Alain, 29/09/2026)** — un paquet de distribution ajouté après la
  release (cas réel : l'installateur macOS joint à `v2.42.0` le 29/09/2026, dont
  le tag reste sur le commit de code + doc) est simplement **ajouté à la release**
  (`gh release upload`, aucun écrasement), la doc de release rééditée
  (`INSTALLATION.md`) est réuploadée avec `--clobber`, et c'est le **prochain
  changement de code** qui porte la version suivante (**v2.43.0** en l'occurrence).
  Le tag marque le CODE + la DOC d'une version, pas les ajouts de distribution
  qui l'ont suivie — et c'est dit tel quel dans les mémoires.

- **Données astronomiques exigées (jalon 70, constat réel d'Alain du
  27/09/2026 : « l'astrométrie ne trouve pas de résultat… et ça échoue en
  silence »)** : l'astrométrie interne exige le catalogue Gaia DR3 de Siril ;
  sous Linux, Siril le range dans **`~/.local/share/siril`** (documentation
  Siril 1.4.4, `core.catalogue_gaia_astro`) — chemin que l'application ne
  cherchait PAS (elle ne testait que `~/.local/share/kstars`, qui ne contient
  justement pas les fichiers `siril_cat*`, puis retombait sur un dossier
  AVAStack vide ; le repli ASTAP, lui, est absent si `astap_cli` n'est pas
  installé). Depuis la v2.38.4 : `catalogues.dossiers_siril()` (chemins par OS,
  `XDG_DATA_HOME` honoré), clé `chemin_catalogues` RÉELLEMENT honorée + ligne
  « Catalogues » (dossier utilisé, présence, boutons 📂/⬇ Gaia), téléchargement
  du catalogue dans un THREAD (reprise + sha256), et **arrêt des essais** quand
  la cause est une donnée manquante (`solveur.MSG_CATALOGUE_ABSENT`), qui
  repartent dès qu'un catalogue apparaît. Leçon générale : **une donnée absente
  doit être dite, avec le chemin cherché** — un « aucun résultat » silencieux
  coûte une soirée de test à Alain.

## Bancs et diagnostics — emplacement (décision d'Alain, 27/09/2026)

Les bancs (`_diag_*.py` : diagnostics ; `_test_*.py` : non-régression) ne
vivent PLUS à la racine : ils sont rangés sous **`bancs/`**, avec un seul thème
séparé, **`bancs/cameras/`** (diagnostic matériel ET bancs de la couche caméra :
SDK constructeurs, capacités, TEC, câblage UI des contrôles) — seuls les
`_diag_*` partent dans les installateurs, cf. la puce « Installateurs ».

- **Chaque banc porte un bootstrap autonome** (inséré juste après sa docstring)
  qui met dans `sys.path` le premier dossier parent contenant `AVAStack.py` —
  il trouve donc l'application qu'il soit dans le dépôt (`bancs/`,
  `bancs/cameras/`) ou dans le dossier d'installation. Ne pas le retirer, et ne
  jamais remettre de chemin absolu de machine de dev.
- **Lancement** : depuis la RACINE du dépôt (ou du dossier d'installation),
  `python bancs\_test_xxx.py` / `./venv/bin/python bancs/cameras/_diag_camera_qhy.py`.
  Les bancs qui lisent des images de test utilisent des chemins relatifs au
  dossier courant : on garde donc l'habitude de les lancer depuis la racine.
- **Installateurs** : seuls les OUTILS DE DIAGNOSTIC MATÉRIEL caméra sont
  embarqués (`bancs/cameras/_diag_*.py`) — décision d'Alain du 27/09/2026 :
  « l'installation ne contient que des outils réellement utilisables par moi »
  (ces outils parlent aux VRAIES DLL et à SES caméras). Les bancs de RÉGRESSION
  de la couche caméra (`bancs/cameras/_test_*.py` : SDK factices, aucun matériel
  requis) sont des outils de DEV, comme tous les autres bancs : ils restent au
  dépôt. Les deux producteurs filtrent par **MOTIF**, jamais par liste : le
  `.iss` embarque `bancs\cameras\_diag_*.py`, le packer Linux la même condition
  (`MOTIF_DIAG = "_diag_"`) → un NOUVEAU diagnostic entre tout seul dans les deux
  installateurs, un banc de test ne part JAMAIS.
- Un banc cité dans CLAUDE.md ou AVANCEMENT.md le reste par son NOM (les
  fichiers n'ont pas été renommés) : pour le retrouver, chercher sous `bancs/`.
- **Un banc qui doit tourner AILLEURS que sur la machine de dev doit être
  AUTONOME** (constat du 30/09/2026, banc GPU) : aucun chemin absolu, repli
  documenté quand une donnée manque — `bancs/_diag_parallele_gpu_jalon82.py`
  fabrique des couches SYNTHÉTIQUES à la bonne définition si on ne lui donne pas
  de couches réelles (et le DIT dans son rapport : les durées d'un appel
  GraXpert dépendent de la taille, pas du contenu) —, et il écrit un **fichier de
  rapport dans le dossier de travail** en plus de l'affichage : la mesure se lit
  sur une autre machine que celle qui l'a produite.

## Portage Linux / macOS — prérequis et installateur (étude du 27/09/2026)

Contrainte d'Alain : l'application doit tourner sur Windows / Linux / macOS. Le
code est DÉJÀ multiplateforme (chemins de config par OS, `compat.ZWO_DLL_NAME`,
`cameras/sdk_loader.nom_bibliotheque`, détection des outils externes selon l'OS) :
le chantier restant est l'INSTALLATION. Éléments vérifiés le 27/09/2026 (CLI
installé, documentations et pages constructeurs) :

- **ÉTAT RÉEL (29/09/2026)** : l'**installateur Linux a été exécuté plusieurs
  fois** sur une machine **Ubuntu 26.04 LTS** — installation, prérequis, venv,
  dépendances et lancement validés en réel, l'application y étant employée en
  séance (astrométrie, SPCC, GraXpert). La documentation affirmait le contraire
  en **trois** endroits (`INSTALLATION.md` § 3 et § 8, `installer/README.md`) :
  **une affirmation d'ÉTAT doit être DATÉE et corrigée dès qu'elle est démentie —
  et vérifiée jusque dans les releases DÉJÀ PUBLIÉES** (notes et pièces jointes
  ont dû être rééditées pour `v2.41.0` *et* `v2.40.0`). Restent à faire : machine
  **vierge** (sans Python ni paquets prérequis) et **test matériel caméras** sous
  Linux (option `--cameras`).
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
- **Outils externes** : GraXpert existe en Linux (`graxpert-linux-amd64.zip`,
  binaire **`GraXpert-linux`** à rendre exécutable) et macOS (dmg → bundle
  `GraXpert.app`) ; le CLI rc-astro (BlurXTerminator) existe pour Windows,
  macOS ET Linux. Détection détaillée : section « Détection de l'exécutable »
  plus bas (v2.38.5).
- **macOS** : Python de python.org (Tk inclus) ou `brew install python-tk@3.13`,
  puis bundle `.app` + signature/notarisation Apple (sinon Gatekeeper bloque).
  **INSTALLATEUR ÉCRIT LE 29/09/2026** (`installer/macos/install_avastack.sh`,
  distribué par `installer/macos/build_avastack.py` en
  `avastack-setup-<version>-macos.tar.gz`) : app + venv dans
  `~/Library/Application Support/AVAStack/app`, lanceur `~/.local/bin/avastack`
  et bundle **minimal** `~/Applications/AVAStack.app` (Info.plist + lanceur qui
  pointe sur le venv — pas de Python embarqué, donc mise à jour sans retoucher le
  bundle) ; **bundle non signé** (pas de compte Apple) → clic droit « Ouvrir » ou
  `xattr -dr com.apple.quarantine`. Prérequis : un Python **avec Tkinter**
  (python.org, ou Homebrew + `python-tk@3.13`) ; le Python système n'en a pas.
  Il **refuse** de s'installer hors macOS et fait le MÊME test de démarrage que
  Linux (`import avastack.ui.app` dans le venv). **ÉTAT DATÉ : écrit et vérifié
  au banc (`_test_installeur_macos_jalon78.py`) et par exécution réelle de ses
  garde-fous, mais PAS ENCORE EXÉCUTÉ SUR UN MAC** — c'est le prochain test.
- **Route LINUX RETENUE (décision d'Alain, 27/09/2026) : ① script + venv**,
  implémentée le même jour — `installer/linux/install_avastack.sh` (copie dans
  `~/.local/share/AVAStack`, venv + `pip install`, lanceur
  `~/.local/bin/avastack`, entrée `.desktop`), distribué en
  `avastack-setup-<version>-linux.tar.gz` par `installer/linux/build_avastack.py`.
  **macOS suit la MÊME route** (décision d'Alain, 29/09/2026 : « si tu peux
  facilement faire l'installateur pour macOS ») : `installer/macos/` reprend le
  script et le packer Linux avec les seules différences de plateforme (dossiers
  `~/Library/...`, bundle `.app`, `*.dylib`, prérequis Tkinter par Homebrew ou
  python.org) — les deux packers partagent les mêmes règles de contenu (version
  lue dans le source, aucun binaire constructeur, `.sh`/`.txt` convertis en LF,
  seuls les `bancs/cameras/_diag_*.py` embarqués).
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

- **PUBLICATIONS : jamais de citation nominative du mainteneur** (consigne du
  29/09/2026, dépôt passé en public). Tout document qui SORT de l'atelier —
  `INSTALLATION.md`, `installer/**` (scripts et commentaires compris),
  `LISEZMOI*`, notes de release, futur README — écrit les faits SANS nom propre :
  « testé en réel sur une machine Ubuntu 26.04 LTS », « validation utilisateur »,
  « décision de projet ». Les mémoires INTERNES (CLAUDE.md, AVANCEMENT.md) et les
  commentaires du CODE gardent le style d'origine (constats datés, nom du
  mainteneur) : la règle vise ce qui est PUBLIÉ, pas la mémoire.
  Corollaire : une affirmation d'état (« pas encore testé ») est TOUJOURS DATÉE,
  et une release **déjà publiée** se corrige aussi (notes + pièces jointes) quand
  elle devient fausse — l'état publié ne doit jamais mentir.
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

### Détection de l'exécutable (v2.38.5 — leçon du 27/09/2026)

**Le nom du binaire n'est PAS le même selon l'OS** ; la comparaison est
sensible à la casse sous Linux :

| OS | GraXpert | rc-astro |
|---|---|---|
| Windows | `GraXpert.exe` (`%LOCALAPPDATA%\Programs\GraXpert\`) | `rc-astro.exe` |
| Linux | **`GraXpert-linux`** (archive `graxpert-linux-amd64.zip`, `chmod u+x`) | `rc-astro` |
| macOS | `GraXpert.app/Contents/MacOS/GraXpert` | `rc-astro` |

Constat déclencheur : sous Linux, « la détection de l'emplacement de GraXpert
ne s'est pas faite » — le code ne cherchait que `graxpert`/`GraXpert`, alors
que le binaire s'appelle `GraXpert-linux` et qu'une archive décompressée n'est
pas dans le PATH. Ordre de recherche implémenté (`external/detection.py`) :

1. **l'INI DE SIRIL** (`graxpert_path`) — l'utilisateur l'a déjà désignée là ;
2. la variable `AVASTACK_GRAXPERT` (resp. `AVASTACK_RC_ASTRO`) ;
3. le PATH (`shutil.which`) ;
4. les noms/emplacements de l'OS (`_noms_graxpert()`, `_sous_graxpert()`…) ;
5. un filtre borné `GraXpert*` (dossier d'archive, AppImage exécutable).

`avastack/siril_ini.py` lit le fichier de configuration de Siril
(`~/.config/siril/configX.Y.ini` sous Linux, `%LOCALAPPDATA%\siril\` sous
Windows, `~/Library/Application Support/org.free-astro.Siril/siril/` sous
macOS — doc Siril 1.4.4) : `graxpert_path` pour l'outil,
`catalogue_gaia_astro`/`catalogue_gaia_photo` pour le dossier des catalogues
d'astrométrie. Piège : GKeyFile **échappe les antislashs** (`C:\\Users\\…`) —
toute lecture doit déséchaîner, sinon le chemin n'existe pas.

Piège majeur (mesuré) : la commande de REPLI (« `graxpert` … » sans chemin) est
une chaîne non vide → elle était **persistée dans config.json** et restaurée
sans re-test de l'exécutable : une détection ratée restait figée À VIE, même
après installation de l'outil. Règles désormais :

- on ne persiste jamais une commande dont l'exécutable est introuvable
  (`external.live.outil_manquant()`) ;
- à l'ouverture, une commande sans outil est **re-détectée** en conservant les
  OPTIONS de l'utilisateur (`external.live.remplacer_binaire()`) : seuls le
  chemin collé change, `-correction Division -smoothing 0.8` restent ;
- l'interface AFFICHE l'état (« ✔ … : chemin » / « ⚠ … introuvable ») et
  refuse de lancer un traitement externe sans outil (message AVANT, pas un
  « command not found » noyé dans la sortie de l'outil).

### GraXpert CLI

Syntaxe (le flag `-cli` est INDISPENSABLE en ligne de commande) :

```
GraXpert.exe <image> -cli -cmd background-extraction|denoising
             [-correction Subtraction|Division] [-smoothing 0..1]
             [-output <nom_sans_extension>] [-bg] [-ai_version X]
```

(Sous Linux : `GraXpert-linux` au lieu de `GraXpert.exe` ; sous macOS : le
binaire du bundle. Le reste de la ligne est identique.)

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
- **VERSION DU MODÈLE SANS `-ai_version` (vérifié le 29/09/2026, GraXpert
  3.1.0rc2)** : GraXpert prend alors la version **STOCKÉE dans SES préférences**
  (`%LOCALAPPDATA%\GraXpert\GraXpert\preferences.json`, clé `bge_ai_version` —
  ici `1.0.1`), pas forcément la plus récente du disque. Comme nos commandes par
  défaut ne passent pas `-ai_version`, le rendu dépend d'un réglage EXTERNE au
  projet. **DÉCISION D'ALAIN (29/09/2026) : ON N'ÉPINGLE PAS** — il veut
  bénéficier **automatiquement des mises à jour de modèles** ; conséquence
  assumée : si GraXpert change de modèle, le fond retiré peut changer sans qu'un
  seul de nos fichiers ait bougé (c'est à SAVOIR, pas à corriger).
  ⚠ Le CLI **RÉÉCRIT ce `preferences.json` à chaque appel** (il y « stocke » les
  options reçues) : les réglages de l'interface GraXpert peuvent donc changer
  après un run d'AVAStack — sans effet sur notre rendu, qui passe toujours ses
  options explicitement.
- **COÛT RÉEL D'UN APPEL (mesuré le 29/09/2026)** : le modèle de retrait de
  gradient pèse **217 Mo** et est **RECHARGÉ À CHAQUE APPEL** — ~**2,8 s fixes
  par appel** (5,6 s sur 8,4 Mpx, encore 3,25 s sur 1,45 Mpx à l'aperçu). D'où
  9,7 s pour 3 couches à l'aperçu, et l'impression que Siril fait « instantané »
  (il garde le modèle en mémoire). Pour aller plus vite un jour : inférence ONNX
  **en processus** (le modèle est un `.onnx` lisible) plutôt qu'un sous-processus
  par couche.
- **LE DÉBRUITAGE A SON PROPRE MODÈLE, ET SON PROPRE COÛT** (mesuré le
  30/09/2026, GraXpert 3.1.0rc2) : le retrait de gradient charge
  `bge-ai-models\<version>\model.onnx` (version STOCKÉE, ici 1.0.1) tandis que le
  débruitage charge `denoise-ai-models\<version>\model.onnx` (ici **3.0.2**) —
  deux familles et deux versions INDÉPENDANTES : ne pas conclure de l'une à
  l'autre. Coût mesuré sur une couche mono de 8,32 Mpx : **290 s par appel**
  (14 min 30 s pour trois couches en série, contre ~10 s pour les trois retraits
  de gradient), **~3,45 Go de working set par processus**, avec les réglages
  STOCKÉS « batch size 4 » et « gpu acceleration True ». C'est LE poste dominant
  d'une chaîne externe par couche ; le MÊME débruitage en local (« nlm ») coûte
  5,9 s pour les trois couches — c'est un choix de qualité, pas une contrainte
  technique. ⚠ Garde-fou à ne pas oublier : `PAR_APPEL_OCTETS = 800 Mo`
  (jalon 81) a été mesuré sur le GRADIENT et ne couvre PAS le débruitage.
- **LE JOURNAL DE GRAXPERT DIT TOUT — MAIS PAS AVEC LES MÊMES MOTS SELON LA
  TÂCHE** (constat du 30/09/2026) : le retrait de gradient écrit
  `Providers : [...]` puis `Used providers : [...]` ; le débruitage écrit
  `Available inference providers : [...]` puis `Used inference providers :
  [...]`. Ces lignes nomment le MOTEUR D'INFÉRENCE réellement employé
  (`['DmlExecutionProvider', 'CPUExecutionProvider']`, `CUDAExecutionProvider`
  sur un GPU NVIDIA…) : **c'est LA ligne à lire pour savoir si le GPU sert**. Un
  analyseur qui n'en connaîtrait qu'UNE formulation ne saurait rien dire de
  l'autre tâche (erreur commise puis corrigée dans le banc GPU). Le CLI écrit
  aussi `Using AI version …`, `AI model path - …`, `batch size`, `gpu
  acceleration`. ⚠ `external.live.appliquer` envoie cette sortie dans un fichier
  du dossier temporaire, qu'il SUPPRIME quand tout va bien : pour LIRE le
  journal, il faut un appel instrumenté — c'est ce que fait
  `bancs/_diag_parallele_gpu_jalon82.py`, qui vérifie au passage que son appel
  rend la MÊME image que `appliquer`, au bit.
- **`DmlExecutionProvider` EST UN MOTEUR GPU — NE JAMAIS LE LIRE COMME « PAS DE
  GPU »** (correction apportée par Alain, 30/09/2026, après un diagnostic sur son
  Windows à RTX 4070 : « tu dis qu'il n'y a pas CUDA, mais c'est DML qui est
  utilisé »). Le build **Windows** de GraXpert embarque **DirectML**, qui calcule
  sur n'importe quel GPU **DirectX 12**, NVIDIA comprise ; la machine de dev
  (iGPU Intel) écrit la MÊME ligne. Grille de lecture d'un journal :
  `DmlExecutionProvider` → GPU via DirectML (cas de Windows) ·
  `CUDAExecutionProvider` → GPU via CUDA (build Linux : **À MESURER, ne pas
  présumer**) · `CoreMLExecutionProvider` → GPU Apple · **`CPUExecutionProvider`
  SEUL → aucun GPU** (tout est calculé par le processeur : le seul cas où le
  débruitage s'effondre). ⚠ Le moteur NOMMÉ ne dit pas quel ADAPTATEUR travaille
  (iGPU ou RTX) : c'est la **VRAM de la carte NVIDIA, sondée PENDANT l'appel**,
  qui le dit — hausse de plusieurs centaines de Mo = c'est elle qui calcule,
  VRAM immobile = l'inférence tourne sur l'autre adaptateur. Le banc GPU applique
  cette grille et ce sondage (un message « CUDA absent » y a été écrit par erreur,
  puis corrigé).
- Les méthodes **classiques** (RBF / Splines / Kriging) existent mais exigent des
  **points de fond fournis** (`-preferences_file`) : il n'y a pas de mode
  automatique sans IA en ligne de commande (le mode IA est justement celui qui
  n'en demande aucun).

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

## Espace disque et fichiers de travail (v2.38.6)

Leçon du 27/09/2026 (machine Linux d'Alain) : « Erreur : 24962352 requested and
10902832 written » pendant BlurX, outil pourtant détecté au vert.

- **Ce message est celui de `numpy.ndarray.tofile()`**, appelé par astropy pour
  écrire les données d'un FITS (`astropy/io/fits/util.py::_array_to_file` —
  docstring du paquet installé : « If writing directly to an on-disk file this
  delegates directly to `ndarray.tofile` »). Il signifie **écriture PARTIELLE**
  (ici 10 902 832 octets sur 24 962 352 : tout ce qui restait de libre), donc
  **volume plein** — PAS un chemin invalide (lequel échouerait à l'ouverture).
  Ne jamais afficher ce message brut à l'utilisateur : passer par
  `images.traduction_erreur_ecriture()`.
- **`/tmp` sous Linux est souvent un tmpfs** (RAM) : mesuré chez Alain, 4,6 Go
  que l'application remplissait elle-même (2,8 Go de dossiers
  `avastack_frames_*` — frames de 32 Mio) pendant que 116 Go dormaient sur le
  disque. D'où `avastack/travail.py` : dossier de travail EFFECTIF (réglage
  `dossier_travail` > repli hors tmpfs `~/.cache/avastack` > temporaire
  système), détection tmpfs par `/proc/mounts` (point de montage le PLUS LONG).
- **Règles d'écriture (non négociables)** : toute écriture passe par
  `images.ecrire_fichier`/`ecrire_fits` (espace vérifié AVANT, fichier `.part`
  puis `os.replace`, partiel supprimé) ; tout `mkdtemp` passe par
  `travail.creer_dossier` ; un plafond de taille se calcule sur l'espace RÉEL
  (`travail.plafond_effectif`) — un garde-fou « 20 Go » en dur ne protège rien
  dans un volume de 4,6 Go.
- **Un échec doit laisser de quoi comprendre** : la chaîne externe CONSERVE son
  dossier de travail (journal `outils_sortie.txt`, FITS d'entrée et d'étapes) et
  annonce le chemin ; les résidus de plus de 6 h sont nettoyés au démarrage
  (`travail.nettoyer_orphelins`).
- **Piège de code associé** : un contrôle ajouté AVANT la définition d'une
  variable (`n_etapes`) a fait échouer la chaîne par couche — et le `except`
  général l'a transformé en échec SILENCIEUX (attrapé par le banc jalon 24).
  Tout nouveau contrôle dans un `try` large doit être placé après ses
  dépendances.

## Démarrage, journal et échecs muets (v2.38.7 / v2.38.8)

Constat du 27/09/2026 (machine Linux d'Alain, v2.38.6) : « l'appli ne se lance
pas sous linux », puis, relancé par l'entrée de menu : « rien du tout : aucune
fenêtre, aucun message ». L'audit du code n'a montré AUCUNE cause statique
certaine (diffs de la version, archive Linux, installateur, chaîne d'imports) :
ce qui manquait n'était pas une correction mais une MESURE.

- **Une application lancée par un menu n'a pas de `stderr`.** L'entrée
  `.desktop` est en `Terminal=false` et le lanceur (`~/.local/bin/avastack`)
  n'est pas plus bavard : tout échec AVANT l'affichage (paquet absent du venv,
  `tkinter` manquant, exception dans la construction de l'interface) est
  INVISIBLE et ne laisse AUCUNE trace. **Règle : tout point d'entrée doit
  écrire un journal sur disque ET MONTRER l'erreur** — même famille que le
  silence de l'astrométrie en v2.38.4 (« l'application n'a pas de journal »).
- **`avastack/journal.py`** : journal `<config>/journal.txt` (rotation à
  1 Mio), `note()`, `erreur()` (traceback complet + texte court avec fichier et
  ligne), `trace_env()`, `montrer()` (boîte Tk, repli `stderr`), `ouvrir()`. Le
  journal est ouvert AVANT le premier import de l'application : il ne dépend que
  de la bibliothèque standard (`config` importé PARESSEUSEMENT, repli sur le
  dossier personnel) — c'est ce qui lui permet de dire POURQUOI l'application ne
  démarre pas.
- **Le filet vit dans les points d'entrée, UNE seule fois** : `AVAStack.py`
  enveloppe TOUT (imports compris) et `python -m avastack` n'est plus un second
  chemin — `avastack/__main__.py` exécute le même script (`runpy`). Deux
  enchaînements recopiés finissent toujours par diverger.
- **`Tk.report_callback_exception` doit être remplacé** (`main()` le branche sur
  `journal.rapport_callback`) : sans cela, une exception dans un rappel (clic,
  curseur, touche) n'est écrite que sur `stderr`, donc perdue pour un lancement
  par le menu.
- **`AVASTACK_SANS_DIALOGUE=1`** force `montrer()` en mode `stderr` : c'est ce
  qui permet à un banc de traverser le chemin d'ÉCHEC RÉEL sans qu'une boîte de
  dialogue attende qu'on la ferme (et à une exécution sans écran de continuer).
- **Un démarrage cassé se mesure vraiment** : copier l'application dans un bac à
  sable, y casser un module d'interface, lancer un SOUS-PROCESSUS et vérifier
  code de sortie, journal et message — pas seulement simuler des appels (banc
  `_test_journal_jalon73.py` [4]).
- **À l'installation aussi** : `install_avastack.sh` importe `avastack.ui.app`
  dans le venv à la fin (aucune fenêtre ouverte) et AFFICHE l'erreur exacte. Un
  installateur qui conclut « terminé » sur une application incapable de démarrer
  envoie l'utilisateur chercher au mauvais endroit.
- **Un banc qui échoue n'accuse pas forcément le code** : avant de corriger,
  rejouer la vérification sur la version PRÉCÉDENTE intacte (ici un `git
  worktree` détaché sur HEAD, sans toucher à l'arbre de travail). Constat du
  27/09/2026 : `_test_catalogues_jalon70.py` [4] échouait déjà sur v2.38.6. Cause
  mesurée : `_tick` VIDE la file des messages du téléchargement d'un coup
  (`get_nowait` en boucle) — un faux transfert qui pose ses deux paliers en
  0,3 s n'a donc aucun texte intermédiaire à afficher, alors qu'un vrai
  transfert annonce une progression par seconde. Réparé côté BANC (rendez-vous :
  attendre que la file soit consommée avant de poser le palier suivant).
- **Un échec de démarrage CONNU mérite un CONSEIL, pas un traceback** (v2.38.8) :
  `journal.conseil_installation()` nomme les deux cas réellement rencontrés —
  session SANS BUREAU (lancement par SSH sans `-X` : « lance depuis le bureau,
  `ssh -X`, ou `DISPLAY=:0` ») et `tkinter` absent du python utilisé (paquet
  SYSTÈME, jamais pip : apt `python3-tk`, dnf `python3-tkinter`, pacman `tk`).
  Pour toute autre cause il rend `""` : **un conseil ne s'invente JAMAIS**.
  `journal.sans_affichage()` conclut à DEUX indices (message de Tk ET `DISPLAY`
  vide, ce dernier SOUS LINUX seulement — ailleurs la variable n'existe pas) ;
  un `env` fourni fait autorité, ce qui permet de rejouer le cas Linux depuis
  n'importe quel OS (banc `_test_journal_jalon73.py` [6]).
- **NE JAMAIS ATTRIBUER UNE CAUSE SANS TRACE — même de bonne foi** (27/09/2026,
  leçon durement apprise) : la panne de la v2.38.6 (« l'appli ne se lance pas »)
  a été attribuée par erreur à un lancement par SSH ; Alain a corrigé — la
  v2.38.6 avait été lancée par le **MENU Applications**, et c'est la **v2.38.7**
  qui a planté en SSH (pas de bureau, `tk.Tk()` impossible). Deux échecs
  distincts restent distincts ; une hypothèse vraisemblable n'est PAS une mesure,
  et un échec sans trace reste SANS EXPLICATION (ici : aucune trace, le journal
  n'existait pas encore). Corollaire : quand une panne est irréproductible,
  proposer une expérience qui la rendrait observable (relancer par le menu et
  comparer les lignes de journal) au lieu de conclure. **Résultat de cette
  expérience (27/09/2026, 23:02)** : la v2.38.7 relancée PAR LE MENU démarre ✔
  (même venv, `Tk 8.6/8.6`, `cwd` = dossier d'installation, « arrêt — fenêtre
  fermée (sortie normale) ») → panne **NON REPRODUITE**. On écrit alors « non
  reproduite » + l'hypothèse la plus compatible avec TOUS les faits
  (installation 2.38.6 à la copie/venv incomplet → plantage à l'import, muet car
  `Terminal=false`), en la marquant **NON PROUVÉE** — jamais présentée comme la
  cause. Ce que la panne a produit de durable : un test de démarrage à
  l'installation ET un journal à chaque lancement.
- **LE DÉMARRAGE NE FAIT AUCUNE MESURE SUSCEPTIBLE DE BLOQUER** (v2.38.11, règle
  née d'une panne MUETTE) : un `stat`/`listdir` sur un montage réseau INJOIGNABLE
  (NAS filtré par un pare-feu, autofs sans délai) **attend indéfiniment**. D'où :
  ① la **FENÊTRE d'abord**, les mesures ensuite — jamais l'inverse ; ② toute
  mesure de disque passe par `delais.borne()` (fil démon + délai : on ABANDONNE et
  l'interface le DIT) ; ③ la première ligne du journal est écrite **sans aucun
  accès disque** — une trace qui dépend d'un accès disque n'est pas une trace ;
  ④ `journal.etape()` AVANT chaque étape qui touche le disque (si elle se bloque,
  la dernière ligne du journal la NOMME) ; ⑤ les montages réseau sont ÉCARTÉS des
  balayages (`travail.TYPES_RESEAU` via `sur_montage_reseau`, et PATH privé de ses
  dossiers réseau avant `shutil.which`) ; ⑥ la détection des outils externes n'est
  plus faite à l'IMPORT du module (elle est bornée, après l'affichage).
  Contre-épreuve : `App(root)` se construit en **0,8 s malgré trois sondes qui
  dorment 30 s** (banc jalon 74). **VALIDÉ en RÉEL (28/09/2026)** : avec
  `nftables` actif — donc NAS injoignable pour l'application — elle s'ouvre, écrit
  son journal et dit « NON MESURÉ » ; la règle n'est plus théorique.
- **Pour NOMMER la ligne où un programme Python se BLOQUE** (technique, utilisée
  deux fois le 27/09/2026) : `faulthandler.dump_traceback_later(N, exit=True)`
  puis lancer le programme — au bout de N secondes, la pile de TOUS les fils est
  écrite et le processus s'arrête. C'est ce qui a désigné précisément le banc 72
  bloqué dans `messagebox.showinfo` et `App(root)` bloqué dans
  `_sonder_catalogues` via `_on_astro` — sans cette mesure, on aurait deviné.
  Même esprit pour un blocage d'IMPORT : `python -X importtime -c "import …"`
  (la dernière ligne nomme le module en cours).
- **Un banc qui bloque n'accuse pas forcément le code (bis)** : le banc 72
  s'arrêtait sur un `messagebox.showinfo` JAMAIS intercepté — un dialog modal
  attend un clic indéfiniment. Reproduit sur la version INTACTE (worktree sur
  HEAD) avec la pile `faulthandler` : **préexistant**, pas une régression. Règle :
  dans un banc, intercepter TOUS les dialogues (`askdirectory`, `showinfo`,
  `showwarning`, `showerror`) — et quand une sonde devient DIFFÉRÉE, POMPER la
  boucle (`_tick` + `update`) au lieu de lire un libellé qui n'est pas encore
  rempli.
- **Ce qu'un journal apporte dès son premier jour** (preuve par les faits) : les
  5 lignes envoyées par Alain ont nommé l'interpréteur réel
  (`…/AVAStack/venv/bin/python`), `Tk 8.6/8.6`, le noyau, et le dossier de
  travail (`~/.cache/avastack`, 115,3 Go libres) — soit la VALIDATION sur sa
  machine du repli hors tmpfs de la v2.38.6 (son `/tmp` est bien un tmpfs) — sans
  rien lui demander d'autre que de lancer l'application.
- **`pack` ABANDONNE silencieusement un widget qui ne tient plus** (v2.38.9,
  mesuré) : trois boutons ajoutés sur une ligne du cadre « Traitement externe
  (long) » (cadre de 318 px = texte 243 + « Ouvrir » 43 + « 📂 » 28) ont fait
  disparaître le TROISIÈME — « Journal » — sans le moindre message :
  `winfo_ismapped()` = 0, `winfo_width()` = 52 px. À l'œil, le bouton n'existe
  pas (constat d'Alain : « pas de bouton journal », capture d'écran à l'appui).
  Règle : un widget ajouté dans une ligne DÉJÀ chargée se vérifie par la
  GÉOMÉTRIE (`winfo_ismapped()`, `winfo_width()`, `winfo_rooty()`), jamais à
  l'œil — et un banc peut le faire (banc jalon 72 : les TROIS boutons doivent
  être mappés ; la fenêtre est affichée le temps de la mesure, car
  `winfo_ismapped` ne dit rien sur une fenêtre retirée/`withdraw`).
- **Un indicateur GLOBAL va EN HAUT de la colonne** (v2.38.9, même constat) : la
  ligne « dossier de travail + espace libre » et les boutons 📂/Ouvrir/Journal
  vivaient en premières lignes du cadre « Traitement externe (long) », soit à
  y≈2421 px sur les 3218 px d'une colonne DÉFILANTE → invisibles sans défilement
  (« pas de chemin pour temp »). Ils ont désormais leur propre cadre « Fichiers
  de travail et journal », TOUT EN HAUT de la colonne de gauche. Leçon : ce qui
  répond à « où est-ce écrit ? » et « qu'est-ce qui s'est passé ? » ne doit pas
  dépendre d'un défilement — et une ligne trop chargée se met sur DEUX lignes
  (le texte, puis les boutons) plutôt que d'en sacrifier un.
- **Règles de MISE EN PAGE de la colonne de gauche (v2.38.9/v2.38.10, mesurées)**
  — `pack` alloue dans l'ORDRE DE POSE et **ABANDONNE silencieusement** ce qui ne
  tient plus :
  ① un petit bouton qui doit toujours être là se pose **AVANT** le texte libre
     (`side="right"` ; ex. le ⓘ du re-stack) ;
  ② un texte libre à largeur variable reçoit une **BORNE** : `wraplength` pour
     une PHRASE, `width` (en caractères) pour un **CHEMIN** — car `wraplength`
     ne replie PAS un chemin (il n'a pas d'espace) ;
  ③ une ligne de contrôles à taille FIXE qui ne tient pas se répartit sur
     PLUSIEURS lignes (astrométrie : case / AD+Dec / champ°+📷) ;
  ④ ce qui répond à « où est-ce écrit ? / qu'est-ce qui s'est passé ? » va EN
     HAUT de la colonne, pas à 2 400 px dans une zone défilante.
  La vérification est **GÉOMÉTRIQUE et AUTOMATIQUE** : `bancs/_test_espace_jalon72.py`
  audite TOUTE la fenêtre (widget géré mais non affiché ; libellé dont le texte
  ne tient pas ; widget qui déborde) **avec des textes longs**. Ce contrôle a
  trouvé cinq widgets écrasés et quatre textes rognés le 27/09/2026 — après deux
  allers-retours avec Alain, dont un constat à l'écran. Un défaut de mise en page
  ne se voit pas sur un chemin court dans un bac à sable : il faut des textes
  LONGS pour le réveiller.

## Pièges (leçons du projet AVAStack)

- **SUR macOS, UNE BOÎTE DE DIALOGUE Tk SANS `parent` PEUT RESTER DERRIÈRE LA
  FENÊTRE PRINCIPALE — et l'application paraît alors insensible** (retour RÉEL
  d'un testeur sous macOS 27 « Golden Gate », 30/09/2026 : « les boutons ne sont
  pas toujours cliquables… le bouton permettant de choisir le dossier à
  surveiller ne répond pas », « le bouton flat reste désespérément inactif »,
  alors que le mode simulation marchait). Sans `-parent`, Tk demande à macOS un
  panneau ou une alerte **APPLICATIVE LIBRE** (NSOpenPanel / NSAlert non
  attaché) ; la fenêtre principale, elle, **attend la réponse** (attente modale)
  : les clics ne produisent rien tant qu'ils n'atteignent pas la boîte invisible,
  et « insister » finit par la toucher. AVEC `parent=`, macOS **attache** la
  boîte à la fenêtre (feuille) : toujours devant. Règle : tout
  `filedialog.*` / `messagebox.*` passe par les **six aides de `App`**
  (`_demander_dossier`, `_demander_fichier`, `_enregistrer_sous`, `_dire`,
  `_avertir`, `_signaler`) — **47 appels** convertis au jalon 84, et un banc
  **STATIQUE** (`bancs/_test_dialogues_jalon84.py`, analyse du source) refuse
  tout appel direct résiduel : un seul oublié ramènerait le défaut. Le diagnostic
  vaut pour les symptômes voisins : **le point commun de deux boutons « qui ne
  répondent pas » a désigné la cause** (tous deux ouvraient une boîte de
  dialogue), et `journal.montrer()` faisait déjà `parent=` + `-topmost` — la
  leçon était connue à un endroit et pas au reste du code. Deux corollaires :
  ① au démarrage, une application Tk lancée par un lanceur ou depuis un terminal
  n'est pas « activée » par macOS : ses premiers clics servent à **activer
  l'application** au lieu d'atteindre le widget → `activer_fenetre()` (`lift` +
  `-topmost` bref + `focus_force`, **macOS seulement** — ailleurs `focus_force`
  volerait le focus de l'utilisateur) ; ② une boîte MAISON (Toplevel) doit être
  **MAPPÉE avant son `grab_set()`** (`update_idletasks()`, puis `lift` et
  `focus_force`) : un grab posé sur une fenêtre pas encore affichée est au mieux
  sans effet, au pire bloquant (macOS comme X11).
- **UN SYMPTÔME « L'INTERFACE NE RÉPOND PAS » SE MESURE — DURÉE + PILE DU FIL
  FAUTIF** (`avastack/ui/reactivite.py`, jalon 84 ; même esprit que la leçon du
  27/09/2026 : un blocage se désigne par sa pile, jamais par une hypothèse). Sous
  macOS, un clic qui tombe pendant que le fil d'interface travaille n'est pas mis
  en file d'attente : il est **perdu** — d'où « les boutons ne répondent pas
  toujours ». Un fil DÉMON compare l'horloge au **battement** posé par `_tick`
  (30 ms) et écrit au journal, au-delà de 1,5 s, la durée ET
  `traceback.format_stack()` du fil principal lu par `sys._current_frames()` (le
  fil bloqué n'a rien à coopérer : un gel natif — Tk, OpenCV, disque — est vu
  comme les autres). Garde-fous mesurés : un rapport **par épisode** (5 par
  session), `AVASTACK_SANS_GUET=1` pour débrayer, et **le guet ne démarre pas
  sans fenêtre AFFICHÉE** — leçon de banc : armé dans un banc, il rapportait
  comme « gel » la **CONSTRUCTION de l'interface suivante** (1,6 s, pile lue
  dans le journal) et déstabilisait `rafale_fin_rendu_jalon80`, un banc de
  timing. Un instrument de mesure doit être **aveugle là où il n'y a pas
  d'utilisateur**. Corollaire : la **version de Tcl/Tk** est journalisée au
  démarrage (`info patchlevel`) dès qu'un testeur évoque un Tk ancien —
  vérifier ce fait avant de refuser ou d'accuser le code.

- **TROIS OPTIMISATIONS DE LA CHAÎNE LIVE SONT ÉCARTÉES — NE PAS LES
  REPROPOSER** (décisions d'Alain des 29-30/09/2026, argumentées ET mesurées ;
  elles reviennent naturellement dès qu'on cherche à raccourcir la chaîne) :
  ① **Décimation** (« GraXpert/NLM une fois sur N ») — un débruitage ou un
     retrait de gradient n'est **pas un modèle réutilisable** : ne pas le refaire
     sur la pile suivante montrerait la pile NON corrigée, donc l'image sauterait
     d'une passe à l'autre (objection d'Alain, décisive).
  ② **Retrait du gradient sur l'image COMPOSÉE** (un seul appel au lieu de
     trois) — refusé : la chaîne PAR COUCHE est une **décision argumentée des
     jalons 24/54** (en SHO/HOO, chaque filtre à bande étroite a SON propre
     gradient ; ce qui marche sur M31 ne se généralise pas).
  ③ **Inférence ONNX en processus** (charger le modèle une fois plutôt que
     relancer le CLI) — mesuré : CPU **119 ms/tuile** (aucun gain face à l'appel
     complet, qui inclut pourtant son démarrage), DirectML **48 ms/tuile** mais
     **mémoire GPU épuisée** en pleine résolution (iGPU à mémoire PARTAGÉE),
     GraXpert restant plus rapide (~20 ms/tuile) ; et surtout **fidélité
     mauvaise : corrélation 0,24** avec son propre modèle de fond (`-bg`) — leur
     prétraitement, leur recollement et leur lissage font l'essentiel du
     résultat. L'environnement de l'essai a été restauré (`onnxruntime`
     désinstallé, `pip check` propre).
  Le gain réel est venu ailleurs, **sans toucher aux maths** : le rendu part en
  **fin de rafale** (jalon 80) et les appels externes par couche partent en
  **un seul lot** (jalon 81).

- **LES OUTILS EXTERNES PAR COUCHE PARTENT EN UN SEUL LOT** (jalon 81, v2.45.0,
  décision d'Alain du 29/09/2026). Le coût de GraXpert est **FIXE par appel**
  (démarrage de son binaire figé + chargement des **217 Mo** du modèle IA :
  ~2,8 s MESURÉS à chaque invocation) et la chaîne par couche (jalon 24)
  l'appelait **trois fois de suite**. Les couches étant INDÉPENDANTES,
  `external.live.appliquer_lot()` les lance ENSEMBLE : **13,70 s → 5,58 s** pour
  3 couches d'aperçu, sorties **identiques octet à octet** (mêmes commandes,
  entrées indépendantes : le parallélisme ne peut pas changer un pixel, il ne
  change que l'instant de départ). Garde-fous : `MAX_PARALLELE = 3`,
  `parallele_max()` borné par la MÉMOIRE LIBRE (`compat.memoire_libre()` —
  ~800 Mo réservés par appel simultané, mesuré 1,22 Go pour trois, tout rendu à
  la sortie) et **REPLI SÉRIE automatique** (lot d'un élément, mémoire
  insuffisante, pool en échec) : le comportement d'avant reste le filet.
  Corollaire pour les bancs : un bouchon qui remplace `appliquer` doit accepter
  la MÊME signature (`img, cmd, timeout=…`) — un lambda à 2 arguments casse dès
  que le lot passe le délai (constat réel sur `_test_save_brute_jalon59`).

- **LA CHAÎNE ⚡ PAR COUCHE : GRADIENT EN LOT, DÉBRUITAGE EN SÉRIE** (jalon 83,
  v2.46.0, décision d'Alain du 30/09/2026, après la mesure des TROIS machines).
  `App._compo_couches_traitees` envoie le GRADIENT de toutes les couches en UN
  lot (`external.live.appliquer_lot`, repli SÉRIE automatique) : **+57 à +60 %**
  mesurés sur iGPU Intel / RTX 4070 / RTX 4060 Ti, sorties **identiques AU BIT**
  (banc `_test_gx_lot_externe_jalon83`). Le DÉBRUITAGE GraXpert reste couche par
  couche : son lot ne rapporte rien (un seul appel sature déjà le GPU) et il
  coûte 2,2 à 3,7 Go de VRAM par appel. Deux conséquences à connaître :
  ① l'ordre est désormais « TOUS les gradients, puis les débruitages » (chaque
  couche reçoit bien son débruitage APRÈS son gradient) ; ② un échec PARTIEL du
  gradient ne bloque PLUS la chaîne — la couche fautive garde ses valeurs
  BRUTES, son message est posé, et la chaîne continue (un échec TOTAL arrête
  toujours, comme avant).

- **LE LOT NE RAPPORTE QUE LÀ OÙ UN APPEL ATTEND — MESURER AVANT DE PARALLÉLISER**
  (jalon 82, mesuré le 30/09/2026, demande d'Alain : « mesurer le gain en
  parallélisant le débruitage »). Paralléliser par couche ne multiplie rien : ou
  l'on **recouvre un temps mort** (démarrage, E/S), ou l'on **partage des cœurs
  déjà pris**. Bancs : `bancs/_diag_parallele_debruitage_jalon82.py` et
  `bancs/_diag_parallele_gx_externe_jalon82.py`, sur ses 3 vraies couches
  (2168 × 3838 = 8,32 Mpx) ; dans TOUS les cas série et lot rendent des pixels
  **identiques au bit**.
  - **Débruitage LOCAL (nlm, son réglage) : le LOT PERD** — 0,95-1,37 s → 1,61-
    2,02 s à l'aperçu 1600 px, **5,86 s → 9,63 s en pleine résolution (−64 %)**.
    Cause MESURÉE : un appel NLM utilise DÉJÀ les cœurs (×4,3 à ×4,5 de 1 à
    14 fils). Corollaire : **ne jamais brider `cv2.setNumThreads`** (à 1 fil, le
    NLM passe de 5,9 s à 22,5 s). Seule exception, « ondelettes » gagne +53 %
    (1,82 s → 0,85 s) parce qu'un appel n'utilise qu'UN fil : gain absolu 0,9 s,
    ce n'est pas son réglage.
  - **GraXpert débruitage par couche : le LOT PERD aussi** sur cette machine
    (−12,9 % : 869,80 s contre 981,69 s), avec **~10 Go** pour les trois
    simultanés. Trace : un appel SEUL brûle ~282 s de CPU en 290 s, les trois
    simultanés en ont brûlé **~880 s CHACUN** pour le même travail.
  - **Le gain dépend donc de la NATURE de l'appel, de la TAILLE et du GPU** : le
    même débruitage gagne +22 % à 300 px et perd −13 % à 8,32 Mpx (les
    démarrages fixes pèsent proportionnellement plus à petite définition).
    **Un banc qui conclut autre chose qu'en PLEINE RÉSOLUTION ne conclut rien.**
  - **TROIS MACHINES MESURÉES, UN SEUL GAIN UNIVERSEL (30/09/2026)** — mêmes
    couches (8,21-8,32 Mpx), même application, GraXpert 3.1.0rc2, sorties
    **identiques AU BIT** dans toutes les configurations :
    - iGPU Intel (dev, mémoire partagée) · DirectML · gradient 10,12 → 4,24 s
      (**+58 %**) · débruitage 869,8 → 981,7 s (**−13 %**) · 1 débruitage 290 s ;
    - RTX 4070 12 Go (Windows, 16 cœurs) · DirectML · gradient 10,73 → 4,28 s
      (**+60 %**) · débruitage 77,7 → 67,6 s (**+12,9 %**) · 1 débruitage 25,9 s ;
    - RTX 4060 Ti 8 Go (Linux, 4 cœurs) · **CUDA** · gradient 11,45 → 4,92 s
      (**+57 %**) · débruitage 121,9 → 120,5 s (**+1,2 %**) · 1 débruitage 40,7 s.
    → **le LOT du GRADIENT gagne PARTOUT (+57 à +60 %)** : ses appels sont dominés
    par leur démarrage (3,4 s fixes quel que soit le GPU), et le lot recouvre ces
    temps morts. C'est le seul gain UNIVERSEL — et gratuit (zéro pixel).
    → **le LOT du DÉBRUITAGE ne se justifie PAS** : −13 % sur iGPU, +12,9 % sur
    4070, **+1,2 % (rien) sur 4060 Ti**, avec le GPU à **100 % dans les trois
    cas** — un seul appel sature déjà la carte, il n'y a aucun temps mort GPU à
    recouvrir. Mesuré sur trois GPU et deux moteurs d'inférence : c'est la
    NATURE du calcul qui décide, pas la puissance de la carte.
    → **Linux = CUDA, Windows = DirectML** (lu dans les journaux des deux
    machines le même jour) : le moteur d'inférence dépend de la BUILD, pas de la
    carte graphique.
  - **⚠ LA VRAM EST UN GARDE-FOU QUE NOUS N'AVONS PAS (mesuré le 30/09/2026)** :
    un débruitage GraXpert de 8,2 Mpx occupe **2,2 Go (CUDA, 4060 Ti)** ou
    **3,7 Go (DirectML, 4070)** ; trois simultanés = **9 642 Mo sur 12 282**
    (78 %) ; le GRADIENT, lui, tient dans **0,7 à 2,0 Go même en lot** (mesuré sur
    les trois machines). Sur une carte à 8 Go, trois débruitages ne rentrent PAS
    (le pilote bascule en mémoire système et tout s'écroule) — or
    `parallele_max()` ne borne que la mémoire SYSTÈME (`PAR_APPEL_OCTETS =
    800 Mo`, mesuré sur le GRADIENT). C'est une raison de plus de NE PAS
    paralléliser le débruitage ; le banc GPU sait sonder une carte limite
    (`--simultane N`, VRAM de pic affichée, échantillonnée à 1 s).
  - Pour les machines à GPU NVIDIA (RTX 3060 Ti 8 Go sous Linux, RTX 4070 12 Go
    sous Windows), le banc dédié est `bancs/_diag_parallele_gpu_jalon82.py` :
    il lit les « inference providers » du journal de GraXpert, puis remesure
    série/lot et sonde VRAM/RAM (`nvidia-smi`). Voir « GraXpert CLI » pour les
    deux formulations du journal.

- **LE RENDU (chaîne lourde) PART EN FIN DE RAFALE, JAMAIS SUR LA PREMIÈRE BRUTE**
  (jalon 80, v2.44.0, demande d'Alain du 29/09/2026 : « on en lit 10, on les
  stacke, et seulement là on lance un rendu »). Le solveur était relancé à
  CHAQUE nouvel empilement : en rafale de dossier il calculait donc une passe
  ENTIÈRE de la chaîne lourde (GraXpert live par couche) sur une pile à **1
  brute**, puis une SECONDE passe sur la pile complète — ~70 % de panneau occupé
  et une image bruitée à l'écran pour rien. `App._tick` note désormais le
  DERNIER empilement (`_rendu_differ` / `_rendu_differ_t`) et le rend quand la
  rafale s'est **TUE** (`RAFALE_QUIET_S = 0,35 s`), avec la BORNE `RAFALE_MAX`
  (un dossier pré-rempli ne doit jamais retarder l'affichage). INVARIANTS :
  sources NON-dossier (caméras, webcam, simulée) = déclenchement immédiat
  inchangé ; `_reinit_etat_session` vide l'attente (aucun rendu fantôme) ;
  **aucun pixel ne change** (même chaîne, même pile — seule la DATE du
  déclenchement change). ⚠ `_vl_frames` peut valoir `None` (début de session) :
  la borne compte alors depuis 0. Banc : `_test_rafale_fin_rendu_jalon80.py`
  (compare `RAFALE_QUIET_S = 0`, l'ancien comportement, au nouveau : **1 rendu
  au lieu de 5** pour une rafale de 6 brutes).

- **UNE DEMANDE DE L'INTERFACE SE SERT EN TÊTE DE BOUCLE DU WORKER, JAMAIS DANS
  LE CHEMIN D'UNE DONNÉE** (constat réel d'Alain, 28/09/2026, v2.41.0) : le bouton
  « Réinitialiser l'empilement » posait un drapeau que le worker ne lisait qu'en
  **TRAITANT une frame** — à l'arrêt (pause, ou aucune brute qui arrive) il ne
  réinitialisait donc **RIEN**, et la session suivante repartait sur l'empilement
  de la cible précédente (« il faudrait que le bouton réinitialiser réinitialise
  vraiment »). Toute demande posée par le thread Tk est désormais servie au même
  endroit que `empilement_start_request` (**tête de boucle**, donc même en pause),
  et sa partie **VISIBLE** est faite côté Tk (`_reinit_etat_session`) pour
  fonctionner **même worker arrêté**. Corollaire : un bouton sans effet visible ne
  prouve pas qu'il n'a rien fait — il peut n'avoir **jamais été lu**. Banc :
  `_test_reset_empilement_jalon76.py` (témoin : le compteur de session avance
  DEUX fois, interface puis worker).
- **UN OBJET DE SOURCE PORTE L'ÉTAT DE SA CONFIGURATION** (constat réel d'Alain,
  28/09/2026, v2.41.0) : la caméra d'un « dossier surveillé » garde SON dossier et
  la mémoire des brutes déjà lues — changer le dossier dans l'interface ne
  changeait donc **rien** à l'objet connecté, d'où un « ▶ Démarrer » qui empilait
  encore la cible précédente. Règle : avant d'utiliser une source connectée,
  **comparer la configuration AFFICHÉE à celle de l'objet** — chemins **absolus et
  normalisés** (barres, casse sous Windows : sans normalisation, une simple
  retouche du texte relancerait la lecture de tout le dossier) — et la
  **refermer** si elle a changé. **Jamais** une caméra SDK (la réouverture est
  impossible dans le même process, § QHY). Corollaire (décision d'Alain) : quand la
  CIBLE change, les **indices d'astrométrie** de l'ancienne sont **EFFACÉS**
  (`SuiviAstrometrie.effacer_indices`, distinct de `reset()` qui les CONSERVE) —
  de fausses coordonnées feraient chercher le solveur à l'ancien endroit du ciel.
  La saisie repart vide, ce qui rouvre la lecture d'en-tête des brutes du nouveau
  dossier, puis le repli ASTAP.
- **UNE SOURCE DE FICHIERS NE SE LIT PAS « POUR RIEN »** (constat réel d'Alain,
  28/09/2026, v2.41.0) : lire pendant une pause est le bon comportement pour un
  flux **live** (ça vide la file du SDK) mais, pour un **dossier**, la brute lue
  est marquée « traitée » : elle n'est **plus jamais** empilable, même après une
  nouvelle remise à zéro — exactement la fenêtre « je finis une cible, je prépare
  la suivante ». En pause, le dossier est seulement **SCANNÉ** (l'état « brutes en
  attente » reste juste, les fichiers restent sur le disque). Même passe : deux
  `Thread(target=self._worker).start()` dans la même méthode = **DEUX workers**
  (mesuré : 2 puis 3, invisibles à l'œil car ils se partagent les frames) —
  relancer un worker se fait UNIQUEMENT sous `if self.thread is None or not
  self.thread.is_alive()`.
- **POUR PROUVER QU'UN BANC DISCRIMINE, MESURER « AVANT » SUR UN WORKTREE HEAD**
  (méthode, 28/09/2026, v2.41.0) : `git worktree add --detach <chemin> HEAD`,
  rejouer le MÊME flux avec les moyens d'avant, puis `git worktree remove --force`
  + `git worktree prune` — sans jamais toucher au travail en cours. Mesure du
  jalon 76 : empilement resté entier, dossier de l'ancienne cible relu, 2 puis 3
  workers en vie — c'est le témoin du banc `_test_reset_empilement_jalon76.py`.
- **LES BARRES DE NIVEAUX VIVENT APRÈS LE MOTEUR D'ÉTIREMENT** (conception du
  28/09/2026, jalon 75 — v2.39.0) : ce que SharpCap appelle le **mini**
  histogramme trace « the image that comes out of live stacking (with live stack
  stretch applied) » et **n'agit que sur l'affichage** (« the stretch in the mini
  histogram affects the display only ») ; son **grand** histogramme trace le brut
  en ADU, et ses colonnes R/V/B sont une BALANCE appliquée **avant** l'étirement
  (chez nous cette balance existe déjà : SPCC/Gaia, équilibrage, Linear Fit).
  Le modèle le plus direct — « les barres = les points de l'étirement » lus dans
  l'histogramme — est **IMPOSSIBLE dans les deux moteurs** :
  `veralux_core_headless` n'a **ni point noir ni point blanc** (une ancre + un
  `logD`) alors que le STF a bien les trois. Les barres agissent donc sur la
  **SORTIE DU MOTEUR**, en **décalage sur l'auto qui continue** de s'ajuster :
  mêmes gestes, même lecture et effet instantané en STF comme en VeraLux, sans
  jamais relancer le solveur. Corollaire : la position d'une barre EST le niveau
  (`display.niveaux`, MTF — `MTF(m, m) = 0,5` place le gris moyen), et l'identité
  0 / 0,5 / 1 est **exacte en binaire**, donc **court-circuitée** plutôt
  qu'approchée (zéro régression possible sur les rendus existants). Banc :
  `_test_histo_jalon75.py` [1]/[2].
- **UN CURSEUR DE SATURATION PAR COULEUR DOIT VISER UNE TEINTE** (constat réel
  d'Alain, 28/09/2026, v2.39.0) : la première écriture appliquait
  `c_c = Y + k_c · (c − Y)` canal par canal. Elle change le canal **PARTOUT**,
  quelle que soit la teinte du pixel : mesuré sur un pixel vert franc
  (0,20 · 0,60 · 0,20), le curseur « Saturation rouge » à 2,00 faisait **CHUTER
  le rouge** (0,20 → 0,00) — donc le pixel devenait **plus vert**. Son constat
  (« quand je pousse l'un, c'est l'autre couleur qui semble se renforcer ») était
  donc exact, et **ce n'était PAS une inversion d'indice**. Correctif : saturation
  par **SECTEURS DE TEINTE** (poids triangulaires sur 0° / 120° / 240°, qui
  somment à 1 partout — transition douce), en teintes OpenCV float32 (H sur
  0..360). Vérifié au banc : pousser « rouge » sature les rouges et laisse les
  verts **intacts**, un gris (S = 0) ne bouge jamais. **Leçon transposable : un
  réglage qui porte un nom de COULEUR doit être testé sur un pixel de CETTE
  couleur** — un test sur du gris, du bruit ou une image factice quelconque passe
  quelle que soit la formule. Banc : `_test_histo_jalon75.py` [6].
- **UN PANNEAU RAFRAÎCHI SEULEMENT PAR LES DONNÉES NE SUIT PAS LES GESTES**
  (constat réel d'Alain, 28/09/2026, v2.39.0) : « quand l'empilement est fini, si
  on touche aux barres, l'image change alors que la position de la barre ne change
  pas, ou pas complètement, comme si le bas n'était pas rafraîchi ». **Cause
  exacte** : `_draw_hist()` n'était appelé QUE par la mise à jour des données
  (une fois par frame) et par le sélecteur de bandes — le geste appliquait la
  valeur et re-rendait l'IMAGE, mais ne retraçait jamais le PANNEAU : **sans
  frame, il restait figé sur la position de départ** ; à 0,2 fps, une frame venait
  le rattraper par sauts, d'où la barre « à moitié » déplacée. Le même défaut
  latent existait pour ↺ Auto, la saisie chiffrée et la remise à zéro de session
  tant qu'aucune image n'était affichée. **Deux règles** : (1) **tout geste
  retrace immédiatement** (glissement à chaque pixel, relâchement, double-clic,
  champs, boutons) ; (2) si le geste **ne change pas la donnée** tracée, **NE PAS
  la recalculer** — `_draw_hist()` retrace des bacs déjà en mémoire, mesuré
  **3,1 ms** contre ~80 ms pour l'image, et c'est ce qui lui permet de suivre
  chaque pixel de souris. Banc : `_test_histo_jalon75.py` [8], avec
  **contre-épreuve faite sur l'ancien code** (le contrôle échoue dessus : 464 px
  tracé contre 628,5 px attendu). **MÊME FAMILLE que la leçon « LES MESURES
  ASTRO/PHOTOMÉTRIE/SPCC SONT RELANCÉES PAR LE WORKER, PAS PAR L'UI » (v2.37.0,
  plus bas) : en fin de source, il n'y a plus de frame — un rafraîchissement qui
  passe par la voie des données ne vient JAMAIS.**
- **UNE ÉCHELLE D'AXE NON DITE EST UN PIÈGE — ET ELLE SE MESURE AVANT DE SE
  CHOISIR** (décision d'Alain, 28/09/2026, v2.39.0 : case « Échelle y linéaire
  (bande basse) ») : la même courbe ne raconte pas la même chose en log et en
  linéaire, or l'axe X (valeurs, barres, repères) ne bouge pas — seul le REGARD
  change. **Mesuré sur ses frames réelles** (20 frames moyennées, aperçu 1600 px,
  STF auto) : la largeur à mi-hauteur du fond passe de **66 % de l'axe en log**
  (la « colline ») à **10,5 % en linéaire** (un vrai **pic**, ×6,3 plus étroit) ;
  en échange la queue tombe de 34 px à 0,65 px (p99 des pixels) et les bacs
  visibles de 251/256 à 151/256. Sur la bande « brut (linéaire) », le linéaire en
  y ne laissait que **10 bacs visibles sur 256** (une aiguille) : la case ne
  s'applique donc **qu'à la bande basse**. Elle est **persistée** (défaut = log,
  donc une config.json d'avant garde le rendu d'avant), basculer **ne recalcule
  rien et ne re-rend pas l'image**, et l'échelle est **DITE dans la ligne d'état**
  — une échelle muette serait un piège. Banc : `_test_histo_jalon75.py` [11] ;
  chiffres et choix : `AVANCEMENT.md`, passe v2.39.0.

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
- **LA ZONE DE CATALOGUE DE L'ASTROMÉTRIE EST UN DISQUE, PAS UN RECTANGLE — ET
  LE PLAFOND N_CAT_MAX PASSE APRÈS** (constat réel d'Alain, 28/09/2026, v2.40.0 :
  « l'astrométrie ne trouve pas de résultat » sur des brutes OSC NGC 7023, caméra
  tournée à −94°). Le rectangle de sélection (`CLIP_MARGE`) supposait que l'axe X
  de la caméra suit les AD : sur une caméra tournée il ne gardait que **43 %** des
  étoiles de l'image **et gardait une bande HORS image** où sont justement les
  plus brillantes. Remplacé par `masque_champ` = **disque du champ réel** (rayon =
  demi-diagonale, invariant en rotation) **sans aucune marge** — mesuré : un
  disque ×1,3 **échoue** (trop d'étoiles hors image). Second point, cumulé : la
  troncature aux `N_CAT_MAX` plus brillantes doit venir **APRÈS** la sélection
  (avant, sur un champ étroit, elle ne gardait que les brillantes d'une zone 2,6×
  plus large que l'image : **9 étoiles dans l'image**). Vérifier une astrométrie
  sur un champ large se fait par le **rms des appariements sur les MÊMES
  étoiles** contre ASTAP, jamais par l'écart point par point des deux WCS (un
  champ large a de la distorsion : 9,5″ d'écart de WCS pour un rms identique).
  Bancs : `_diag_osc_ngc7023.py` (brutes réelles), `_test_solveur_reel_m31.py`.
- **LA SPCC N'EST PAS RÉSERVÉE AU MONO MULTI-BANDES** (constat réel d'Alain,
  28/09/2026, v2.40.0 : « la case SPCC dit que c'est que pour du mono multibande,
  alors que SPCC fonctionne en images couleurs dans Siril — il faut juste lui
  dire que c'est un capteur couleur »). La base de Siril décrit un capteur
  COULEUR par **trois entrées** (`channel` RED/GREEN/BLUE, même `model`) plus un
  filtre LPF **commun** : c'est le calcul de Siril sur une image OSC. Pièges de ce
  chemin, tous mesurés : (1) un capteur s'appelle « Sony IMX585 » **dans les deux
  listes** de la base → le nom du capteur ne dit PAS le type, c'est l'interface
  qui le dit (`mode`), et pour un appelant qui l'ignore `mode_bandes` tranche sur
  les **filtres** (le même filtre OSC sur trois canaux = capteur couleur ; trois
  filtres mono = mono) ; (2) exiger « trois filtres distincts » (règle du mono,
  `coherence_bandes`) est **faux en OSC** — d'où `coherence_osc` ; (3) la
  correspondance des noms se fait **exactement d'abord** (« No filter » tombait
  sur « Full spectrum (no filter) », qui le contient) ; (4) le **défaut** d'un
  filtre OSC ne doit JAMAIS être le premier de la liste (c'est un vrai LPF,
  « Antlia Quad Band… » : l'appliquer en silence fausserait toute la couleur) →
  viser la référence « sans filtre » ; (5) les gains par canal d'une SOURCE
  COULEUR s'appliquent par `LiveStacker.gains` (avant l'équilibrage et le Linear
  Fit) et **jamais** sur l'empilement brut `corrections=False`. Banc :
  `_test_spcc_osc.py` (bout en bout : gains vrais 0,70 / 1,30 retrouvés à 1 %).
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
- **DEUX CONVENTIONS DE RAPPEL `progression` COHABITENT DANS `telechargeur.py`**
  (v2.42.0, mesuré) : `verifier_ou_telecharger` et `telecharger_chunks` appellent
  `progression(nom, fraction)`, mais le téléchargement de BAS NIVEAU
  (`telecharger`) appelle `progression(fraction)`. Les enchaîner sans adaptation
  INVERSE les deux arguments — constaté au premier essai du chemin complet : le
  nom du fichier arrivait comme `float` et la fraction comme chaîne. Rien ne le
  voit à l'œil : c'est le banc du jalon 77 qui l'a attrapé. Règle : une fonction
  neuve qui annonce une progression DIT laquelle des deux formes elle prend, et
  l'adaptation se fait à UN seul endroit.
- **UN BANC QUI ISOLE L'ENVIRONNEMENT DOIT AUSSI BASCULER LES CONSTANTES D'OS**
  (v2.42.0, mesuré) : poser `HOME`/`XDG_*`/`LOCALAPPDATA` ne suffit PAS sous
  Windows — `config.dossier_config()` lit `%APPDATA%` tant que `IS_WINDOWS` est
  vrai, donc le banc lisait le **VRAI** `config.json` (et la case SPCC cochée de
  la machine de dev faisait échouer un test d'interface qui n'avait rien à voir
  avec le code testé). Règle : basculer `IS_WINDOWS`/`IS_MACOS` des modules
  concernés (et de `config`), retirer `APPDATA` en plus de `LOCALAPPDATA`, et
  restaurer les deux en sortie de banc.
- **UN AUDIT DE GÉOMÉTRIE DOIT IGNORER LES PARENTS DE TAILLE 0/1 px** (v2.42.0 ;
  mesuré, puis vérifié sur un `git worktree` de HEAD) : avec une configuration
  VIDE (premier lancement), un **sas de panedwindow reste à 1 px** → 29 widgets
  « gérés mais non affichés » **dès la construction**, identiques AVANT et APRÈS
  les changements testés (donc préexistants). Le contrôle de référence reste le
  banc du jalon 72 (vraie configuration) ; un banc qui part d'une configuration
  neuve vérifie NOMMÉMENT les widgets qu'il ajoute, et laisse la mise en page se
  terminer (plusieurs `update()`) avant de mesurer quoi que ce soit.
- **UNE DONNÉE TÉLÉCHARGEABLE DOIT DEVENIR UTILISABLE DANS LA MÊME SESSION**
  (v2.42.0) : télécharger la base de profils SPCC sans rendre sa case cochable ni
  remplir ses listes ne sert à rien avant un redémarrage — la fin du transfert
  relit donc la base et rafraîchit l'interface (case, listes, ligne d'état).
  Règle générale : après un téléchargement, l'état affiché est RECALCULÉ, et le
  banc le vérifie point par point (banc du jalon 77).
- **UN FICHIER DE MÉMOIRE NE PASSE JAMAIS PAR UN ALLER-RETOUR POWERSHELL**
  (constat réel du 29/09/2026, jalon 79) : `Get-Content -Raw` lit un fichier
  **UTF-8 SANS BOM** avec l'encodage ANSI de Windows (1252) ; réécrit ensuite en
  UTF-8, il **DOUBLE-ENCODE tous les accents** (« mémoire » → « mÃ©moire ») et
  ajoute un BOM — `AVANCEMENT.md` a été corrompu en une seule commande (restauré
  par `git checkout -- AVANCEMENT.md`, puis réédité). Règle : ces documents
  s'éditent avec l'OUTIL D'ÉDITION (il préserve les fins de ligne du fichier et
  écrit l'UTF-8 correct) ; si un script est indispensable, forcer l'UTF-8 en
  LECTURE **et** en écriture. **Contrôle après toute retouche documentaire** :
  `git diff --numstat` doit rester PETIT (sinon c'est le fichier entier qui a
  été réécrit) et l'on cherche les motifs de mojibake (`Ã©`, `Â«`, `â€`) ;
  `git ls-files --eol <fichier>` dit les fins de ligne réelles du dépôt
  (`i/lf w/crlf` pour `AVANCEMENT.md` et `app.py`, `w/lf` pour `stacking.py`).
- **UN BANC DE PERFORMANCE DOIT ÊTRE ÉTALONNÉ — ET VÉRIFIER LA CORRECTION**
  (constat réel du 29/09/2026, jalon 79) : sur un portable, **deux runs
  STRICTEMENT identiques** du même banc diffèrent de **10 à 20 %** (le premier,
  machine au repos, est le plus rapide) ; un seuil de régression à 15 % a produit
  **six fausses alertes** sur un run à blanc. Les deux remèdes, mesurés : retenir
  le **MINIMUM** d'un nombre d'itérations (la moyenne est polluée par la chaleur,
  le reste du système et le ramasse-miettes) et **normaliser** les écarts par une
  **calibration machine** prise **au DÉBUT et à la FIN** (`a + a` float32 sur une
  taille fixe) ; seuil tenable : **25 %** — un vrai gain du chantier se compte en
  dizaines de pourcents. LIMITE de cette calibration, mesurée le même jour : elle
  ne couvre que les opérations **bornées par la mémoire** — sur un portable
  freiné par la chaleur, une mesure de CALCUL dérive SEULE à calibration
  identique (`align_orb` 409 → 607 ms, +48 %, calibration inchangée à 7,5 ms).
  D'où : comparer deux passes prises dans le MÊME état (machine au repos quelques
  minutes) et ne croire que les gros mouvements. Deux corollaires appris le même jour : ① un banc de
  performance ne vaut que par son **garde-fou de correction** — celui du jalon 79
  compare l'empilement produit à une réimplémentation numpy ÉCRITE DANS LE BANC,
  écart ZÉRO exigé ; ② **mesurer AVAStack FERMÉ** : les premiers chiffres du
  jalon ont été pris pendant que l'application empilait en parallèle, ils étaient
  **1,5 à 2× trop lents** — la référence a été refaite au repos (`--verifier`
  n'écrit rien, c'est le mode de contrôle).
- **LE COÛT D'UN CHEMIN PAR FRAME EST SOUVENT L'ALLOCATION, PAS LE CALCUL**
  (constat réel du 29/09/2026, jalon 79) : `LiveStacker.add` coûtait **325 ms**
  sur 8,4 Mpx là où le même calcul sans temporaires en coûte **14 ms** — l'écart
  tenait aux ~15 tableaux float64 de 67 Mo créés puis jetés à CHAQUE frame.
  Recette appliquée (mesurée ×5 à ×6) : tampons **préalloués** une fois par
  géométrie, opérations **en place** (`out=`), calcul élémentaire en **float32**,
  et **bandes de lignes en parallèle** (les grandes opérations numpy libèrent le
  GIL — ×3,3 mesuré sur une opération élémentaire ; 4 fils suffisent, en garder
  pour l'interface et les solveurs). TROIS RÈGLES QUI VONT AVEC : ①
  **l'exactitude se gagne avec le dtype, pas avec la vitesse** — carrés et seuil
  de rejet restent en **float64**, où le produit de deux float32 est EXACT, donc
  l'accumulation reste **bit à bit** celle d'avant (prouvé : `array_equal` des
  sommes et des poids sur l'ancien algorithme, compteurs de rejets identiques) ;
  ② un **seuil de parallélisme** (une seule bande sous 1,5 Mpx) garde les petits
  cas SÉQUENTIELS, donc comparables à l'ancien code ; ③ **dire le prix** — ces
  tampons sont PERSISTANTS (+240 Mo en mono 8,4 Mpx, +725 Mo en RGB 25 Mpx, par
  stacker ; une composition en tient un par rôle), libérés par `reset()`.
  Bancs : `_bench_performance.py` (mesures + contrôles) et
  `_test_rejet_satellites_jalon6.py` [1]/[6] (exactitude et invariance au
  découpage).

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
