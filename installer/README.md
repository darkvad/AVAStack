# installer/ — AVAStack

Installateurs d'AVAStack (live stacking) — déploiement LOCAL, aucun droit
administrateur requis (tout s'installe dans le profil de l'utilisateur) :

| Plateforme | Artéfact | Produit par |
| --- | --- | --- |
| Windows | `windows/output/avastack-setup-<version>.exe` | `windows/build_avastack.ps1` (Inno Setup 6) |
| Windows (paquet ZIP, sans exécutable) | `windows/output/avastack-setup-<version>-windows.zip` | `windows/build_avastack_zip.py` |
| Windows (paquet GELÉ, PyInstaller) | `windows/output/avastack-frozen-<version>-windows.zip` | `windows/build_avastack_frozen.ps1` |
| Linux | `linux/output/avastack-setup-<version>-linux.tar.gz` | `linux/build_avastack.py` |
| macOS | `macos/output/avastack-setup-<version>-macos.tar.gz` | `macos/build_avastack.py` |

Installation pas à pas (les trois plateformes, **et la préparation des données
Gaia** — catalogue astrométrique, morceaux de spectres, base de profils SPCC) :
**`INSTALLATION.md`**, à la racine du dépôt ; il est joint à chaque release comme
document d'accompagnement. AVAStack télécharge lui-même ces trois données
(boutons ⬇ de la fenêtre) : **Siril est facultatif** (utile seulement si l'on
préfère le laisser préparer ses catalogues).

**macOS** : le paquet est un `tar.gz` (pas de `.dmg`) dont l'installateur écrit
un bundle `~/Applications/AVAStack.app` (double-clic) et un lanceur
`~/.local/bin/avastack` ; il exige un Python AVEC Tkinter (python.org, ou
Homebrew + `python-tk`). État au 29/09/2026 : **écrit et vérifié au banc, pas
encore exécuté sur un Mac** (le paquet Windows et le paquet Linux, eux, sont
exécutés en réel).

**Le nom de l'artéfact PORTE LA VERSION** (règle du 27/09/2026) : elle
vient toujours de `AVASTACK_VERSION` (`avastack/__init__.py`), jamais d'un nom
figé — `avastack.iss` refuse même de compiler sans `/DAppVersion`. Deux
versions ne s'écrasent donc jamais (celle d'avant reste à côté et sert de
repli). Détail : CLAUDE.md, section « Installateur et tests réels ».

## Bancs embarqués : les DIAGNOSTICS MATÉRIEL caméra seulement

Les deux installateurs n'embarquent que les **outils de diagnostic matériel**
caméra — `bancs/cameras/_diag_*.py` : `_diag_camera_qhy.py`,
`_diag_camera_playerone.py`, `_diag_camera_svbony.py`,
`_diag_camera_touptek.py`, `_diag_qhy_sdk.py`. Ce sont les seuls outils que
l'utilisateur peut LANCER chez lui : ils parlent aux vraies DLL et à ses
caméras.

Les bancs de **régression** de la couche caméra (`bancs/cameras/_test_*.py` :
SDK factices, aucun matériel requis — `_test_qhy_camera.py`,
`_test_camera_*.py`, `_test_capacites*.py`, `_test_tec*.py`, `_test_ui_*`,
`_test_expo_*`, `_test_pilotage_*`, `_test_connexion_*`) sont des outils de
DÉVELOPPEMENT : ils restent dans le dépôt et ne partent PAS dans les
installateurs (décision de projet, 27/09/2026 : l'installation ne contient que
des outils réellement utilisables par l'utilisateur). Comme tous les autres bancs
(solveur, couleurs, chromatisme, sauvegardes, gradient, alignement…).

Les deux installateurs filtrent par **MOTIF**, jamais par liste de fichiers :
le `.iss` embarque `bancs\cameras\_diag_*.py`, le packer Linux la même
condition (`MOTIF_DIAG = "_diag_"`). Un nouveau diagnostic entre donc tout seul
dans les deux installateurs ; un banc de régression ne part jamais.

## Ce que fait l'installateur Windows (avastack-setup-<version>.exe)

1. Vérifie/présente Python 3.10+ (le télécharge et l'installe silencieusement
   depuis python.org si absent) — en **vérifiant son empreinte SHA-256 AVANT de
   l'exécuter**, avec une seconde tentative (v2.48.2 ; même empreinte que le
   paquet ZIP, verrouillée par le banc du jalon 89).
2. Copie l'application dans `%LOCALAPPDATA%\AVAStack`
   (modifiable pendant l'installation).
3. Crée un venv et installe les dépendances : numpy, opencv-python, pillow,
   astropy + **qhyccd** (SDK QHY natif inclus dans le paquet pip).
4. Crée les raccourcis Bureau + Menu Démarrer et un `lancer_avastack.bat`.
5. Affiche un rappel des SDK caméras à télécharger manuellement (ZWO,
   Player One, Touptek/Altair, SVBONY) et copie un LISEZMOI.txt.

## Les données de l'astrométrie ne sont pas embarquées (ni DLL, ni pip)

L'astrométrie (et la photométrie/couleurs qui en dépendent) a besoin des
**données Gaia DR3 de Siril** — des fichiers d'étoiles, jamais embarqués dans
un installateur (1,1 Go, licence CC-BY). Depuis la v2.38.4, l'application :

- CHERCHE aux bons endroits par OS (`~/.local/share/siril` sous Linux —
  l'emplacement documenté de Siril —, `%LOCALAPPDATA%\Siril` sous Windows,
  `~/Library/Application Support/Siril` sous macOS, plus les dossiers KStars) ;
- DIT où elle cherche et si le catalogue est présent (ligne « Catalogues ») ;
- le TÉLÉCHARGE à la demande (bouton « ⬇ Gaia », reprise + sha256) ;
- accepte un dossier choisi par l'utilisateur (config `chemin_catalogues`) ;
- ARRÊTE les essais d'astrométrie quand la cause est une donnée manquante
  (au lieu de répéter 20 fois le même échec) et repart dès qu'un catalogue
  apparaît.

## Ce que l'installateur n'embarque PAS

- Les **SDK binaires constructeurs** (ASICamera2.dll, PlayerOneCamera.dll,
  toupcam.dll, SVBCameraSDK.dll) : code propriétaire, jamais dans le dépôt ni
  dans l'installeur. L'utilisateur les télécharge et les dépose dans le
  dossier d'installation (instructions dans LISEZMOI.txt).
- Exception QHY : le paquet `qhyccd` (PyPI, MIT/Apache) **inclut** le SDK
  natif QHYCCD — aucune manipulation pour l'utilisateur.

## Installateur Linux (route ① retenue le 27/09/2026 : script + venv)

`linux/install_avastack.sh` — même esprit que l'installateur Windows, mais en
bash et sans rien qui ressemble à une DLL :

1. Teste les **prérequis système** AVANT toute copie : `python3` ≥ 3.10,
   `python3-venv` (ensurepip) et **`python3-tk`** (Tkinter n'existe pas sur
   pip) ; en cas de manque il affiche la commande exacte pour Debian/Ubuntu,
   Fedora et Arch, puis s'arrête (option `--forcer` pour passer outre).
2. Copie l'application dans `~/.local/share/AVAStack` (option `--prefix`),
   avec les **outils de diagnostic matériel caméra** (`bancs/cameras/_diag_*.py`
   — les autres bancs, y compris les tests de régression caméra, sont des outils
   de développement et ne sont PAS installés, cf. ci-dessus), et note la
   version installée dans `VERSION.txt`.
3. Crée le venv et installe les dépendances via `common/avastack_setup.py` —
   le MÊME outil que l'installateur Windows (une seule route d'installation
   des dépendances à maintenir).
4. Écrit `lancer_avastack.sh`, la commande `~/.local/bin/avastack` et l'entrée
   de menu `~/.local/share/applications/avastack.desktop`.
5. **Vérifie le résultat en interprétant réellement** : Tkinter,
   numpy/OpenCV/Pillow (avec le rappel `libgl1`/`libglib2.0-0`), astropy et
   l'état des caméras.

**CAMÉRAS : ABSENTES dans cette version** (livraison volontairement sans
caméras) — aucun
`*.so` constructeur n'est embarqué et les paquets pip `qhyccd`/`zwoasi` ne sont
PAS installés (le script les retire de `requirements.txt`). L'application
travaille donc en **mode dossier / composition multi-dossiers / OpenCV /
simulé** : tout AVAStack, sauf l'acquisition directe depuis une caméra.
L'option `--cameras` (à utiliser quand les `*.so` seront disponibles) installe
les paquets caméras, copie les `*.so` présents et pose les `*.rules` dans
`/lib/udev/rules.d` (sudo).

Autres options : `--sans-raccourci`, `--forcer`, `--desinstaller [--purger]`,
`-h|--aide`. Lisez-moi utilisateur : `linux/LISEZMOI.txt` (copié dans le
dossier d'installation).

## Compilation

### Windows

Méthode recommandée — le wrapper lit la version dans `avastack/__init__.py`
(`AVASTACK_VERSION`, source unique de vérité) et la passe à ISCC via
`/DAppVersion=...` :

```
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_avastack.ps1
```

Compilation manuelle (sans wrapper) : `ISCC.exe /DAppVersion=<version>
avastack.iss`. Sans `/DAppVersion`, la compilation est REFUSÉE (`#error`) :
depuis le 27/09/2026 le nom de l'artéfact porte la version, donc un
installateur sans version serait un installateur MAL NOMMÉ.

Artéfact : `windows/output/avastack-setup-<version>.exe` (~11 Mo).

### Linux

```
python  installer/linux/build_avastack.py     (Windows)
python3 installer/linux/build_avastack.py     (Linux / macOS)
```

Le packer lit la MÊME `AVASTACK_VERSION` et écrit
`linux/output/avastack-setup-<version>-linux.tar.gz` (dossier racine
`avastack-<version>-linux/`, `installer/install_avastack.sh` en 0755). Il
REFUSE d'embarquer le moindre `*.so` / `*.dll` / `*.dylib` / `*.rules`
(garde-fou : les SDK constructeurs restent hors du dépôt) et n'inclut ni venv
ni config. Il convertit en LF les `.sh` et `.txt` de l'archive : le dépôt
Windows les écrit en CRLF, et un script `.sh` en CRLF ne s'exécute pas sous
Linux.

Rebuilder les installateurs après toute montée de version (le numéro suit le
source) et annoncer le chemin EXACT de l'artéfact en fin de passe.

## Ce que fait l'installateur Windows en paquet ZIP

Pourquoi il existe (constat réel du 01/10/2026) : `avastack-setup-<version>.exe`
est un **exécutable non signé** ; sur un Windows 11 neuf, le **Contrôle
intelligent des applications** (Smart App Control) bloque un fichier temporaire
d'Inno Setup et l'installation s'arrête sur « Erreur 4551 : une stratégie de
contrôle d'application a bloqué ce fichier ». Ce paquet-ci n'exécute **aucun
exécutable à nous** : un script PowerShell fait tout le travail.

1. **Clic droit sur le `.zip` → Extraire tout** (ne pas travailler depuis
   l'intérieur de l'archive), puis **double-cliquer sur
   `installer\install_avastack.bat`**.
2. Le script cherche un **Python de python.org ≥ 3.10 AVEC Tkinter**. Le
   **Python du Microsoft Store est TOUJOURS ignoré** — même s'il est présent
   (consigne d'Alain, 01/10/2026) : avec lui, la création d'un venv avec pip
   échoue de façon connue (redirection de chemins → `No pyvenv.cfg file`, le
   « Code retour : 1 » observé en v2.45.0).
3. **S'il n'en trouve pas, il télécharge et installe Python depuis python.org**
   (par utilisateur : `InstallAllUsers=0`, `Include_tcltk=1` → Tkinter inclus) —
   en **vérifiant son empreinte SHA-256 AVANT de l'exécuter**, avec une seconde
   tentative (v2.48.2).
4. Il copie l'application dans `%LOCALAPPDATA%\AVAStack` (le MÊME dossier que le
   `.exe`), copie les SDK constructeurs présents, crée le venv, écrit le lanceur
   `lancer_avastack.bat` et les raccourcis (Bureau + Menu Démarrer), puis fait un
   **TEST DE DÉMARRAGE RÉEL** (import de `avastack.ui.app`, aucune fenêtre) et
   **affiche l'erreur exacte** si l'application ne peut pas démarrer.
5. Options : `-Prefix`, `-Python`, `-Simulation` (montre le Python choisi et ce
   qui serait fait, sans rien modifier), `-SansRaccourci`, `-Forcer`,
   `-Desinstaller [-Purge]`, `-Aide`. Le script natif reste appelable :
   `powershell -NoProfile -ExecutionPolicy Bypass -File install_avastack.ps1`.

Paquets pip caméras : `qhyccd` et `zwoasi` sont **tentés séparément et SANS
bloquer** l'installation (un paquet caméra en échec ne doit jamais faire échouer
tout le reste — c'est précisément la cause du « Code retour : 1 » d'un venv).

Contrairement aux packers Linux/macOS (qui REFUSENT tout binaire constructeur),
ce packer-ci **embarque les quatre DLL nommées** d'`avastack.iss` quand elles
sont présentes à la racine : sans elles, le paquet ZIP offrirait moins de caméras
que le `.exe`.

## Packer GELÉ (PyInstaller) — antichambre de la voie Store (v2.49.0)

`windows/build_avastack_frozen.ps1` produit une application **GELÉE** par
PyInstaller (`--onedir --windowed`) — **sans venv, sans Python à installer** :
c'est ce qu'exige un futur **MSIX** (un MSIX est immuable, donc on ne peut pas y
créer un venv à l'installation). C'est un **paquet d'ESSAI**, en plus des quatre
installateurs.

- Artefact : `output/avastack-frozen-<version>-windows/` (+ `.zip`, SHA-256
  affiché) ; le nom PORTE la version, comme les autres packers.
- Les **4 DLL constructeurs sont EMBARQUÉES** (liste nommée, `--add-binary`) —
  décision d'Alain du 02/10/2026 : **on les garde dans TOUS les installateurs**
  (la politique Store 10.2.4 ne vise que les PILOTES noyau / services NT, pas les
  DLL en mode utilisateur ; et la lecture seule d'un MSIX rendrait leur dépôt
  manuel impossible). Une DLL absente au build est ANNONCÉE, jamais inventée.
- Prérequis de build : **PyInstaller ≥ 6.16** dans le venv (Python 3.14) ;
  **outil de DEV**, jamais dans `requirements.txt`.
- Le **scan QHY** fonctionne en gelé (correctif v2.49.0 : l'exe se relance avec
  `--scan-qhy`, car un exe PyInstaller ignore `-c`).

## Paquet MSIX (voie Microsoft Store) — jalon 92

`msix/build_msix.py` + `msix/signer_msix.ps1` préparent la **voie Microsoft
Store** : le Store distribue des **MSIX**, or un MSIX est **immuable** (fichiers
en lecture seule) → on y emballe l'application **GELÉE** produite ci-dessus.

1. **Construire** (partie déterministe, testable) :
   `python installer/windows/msix/build_msix.py`
   → `output/avastack-<version>-windows.msix` (NON signé). Il copie le paquet
   gelé, écrit `AppxManifest.xml` (depuis `AppxManifest.xml.template`) et génère
   les **vignettes** (PNG, stdlib seule), puis appelle `MakeAppx.exe`.
2. **Signer** (un MSIX non signé NE s'installe PAS) :
   `powershell -File installer/windows/msix/signer_msix.ps1 -Msix "...msix"`
   → certificat **auto-signé** (créé si absent), `.cer`/`.pfx` exportés,
   signature `signtool`. **La signature du Store n'existe qu'APRÈS soumission**
   (Microsoft re-signe le paquet publié) : l'auto-signé sert au test LOCAL.
   `-Installer` fait confiance au certificat puis installe ; `-Timestamp`
   horodate (exige Internet ; pour la soumission).
   ⚠ **PIÈGE MESURÉ (02/10/2026)** : le certificat doit être approuvé dans
   **`Cert:\LocalMachine\TrustedPeople`**, PAS `CurrentUser\TrustedPeople`
   (l'installation AppX échoue alors sur **`0x800B0109`** « certificat racine
   non approuvé »). Le magasin « LocalMachine » exige donc une session
   **administrateur** — c'est ce que fait `-Installer` (qui refuse clairement
   sinon). Faire confiance à un certificat **machine** affecte tous les
   utilisateurs : le retirer quand l'essai est fini.

**Identity** : `Name`/`Publisher` sont des paramètres — pour un ESSAI, les
défauts (`AVAStack` / `CN=AVAStack Test`) suffisent ; **pour le Store**, ils
doivent être EXACTEMENT ceux de Partner Center (`--nom`, `--publisher`), et le
`Publisher` doit être le **sujet** du certificat signataire.

Les **vignettes** (tuiles) sont générées depuis la **vraie icône**
(`assets/avastack.png`, 512×512) — recadrage « cover » + LANCZOS — aux tailles
du manifeste (50, 44, 71, 150, 310 et 310×150) ; repli géométrique stdlib si
PIL ou l'icône manque. L'**icône de l'application** (`assets/avastack.ico` +
`assets/avastack.png`) est posée par `avastack/ressources.py` (barre de titres
et barre des tâches) et embarquée par les **quatre** canaux. L'application est
déclarée **pleine confiance** (`Windows.FullTrustApplication` +
`rescap:runFullTrust`) → son `%APPDATA%\AVAStack` reste RÉEL (config + journal
non virtualisés).

## Structure

```
installer/
  common/
    avastack_setup.py     création de venv + dépendances (stdlib only),
                          appelé par les DEUX installateurs (Windows et Linux)
  windows/
    avastack.iss          script Inno Setup (version passée via /DAppVersion ;
                          refus de compiler sans version)
    build_avastack.ps1    wrapper ISCC : lit AVASTACK_VERSION, appelle ISCC
    install_avastack.ps1  installateur ALTERNATIF (paquet ZIP) : Python de
                          python.org (le Python du Microsoft Store est ignoré),
                          venv, lanceur, raccourcis, test de démarrage
    install_avastack.bat  lanceur double-clic de install_avastack.ps1
    build_avastack_zip.py packer (stdlib) : lit AVASTACK_VERSION et écrit
                          output/avastack-setup-<version>-windows.zip
    build_avastack_frozen.ps1
                          packer PyInstaller (gel) : lit AVASTACK_VERSION,
                          embarque les 4 DLL NOMMEES, écrit
                          output/avastack-frozen-<version>-windows/ (+ .zip)
    msix/
      AppxManifest.xml.template  modele du manifeste MSIX (jetons __X__)
      build_msix.py    packer (stdlib) : staging + manifeste + vignettes, puis
                       MakeAppx -> output/avastack-<version>-windows.msix
      signer_msix.ps1  certificat AUTO-SIGNE + signtool (essai local) ;
                       -Installer fait confiance au certificat et installe
    LISEZMOI.txt          lisez-moi utilisateur (copié à l'installation)
    output/               artefact compilé (gitignore) :
                          avastack-setup-<version>.exe
                          avastack-setup-<version>-windows.zip
                          avastack-frozen-<version>-windows/ (+ .zip)
                          avastack-<version>-windows.msix (+ .cer/.pfx)
  linux/
    install_avastack.sh   installateur (bash) : prérequis, copie, venv,
                          lanceur, entrée .desktop, vérification ; sans caméras
    build_avastack.py     packer (stdlib) : lit AVASTACK_VERSION et écrit
                          output/avastack-setup-<version>-linux.tar.gz
    LISEZMOI.txt          lisez-moi utilisateur Linux (dans le paquet)
    output/               artefact (gitignore)
```

Et, à la racine du DÉPÔT (c'est là que vivent les bancs désormais) :

```
bancs/
  cameras/                SEUL thème embarqué par les deux installateurs
  *.py                    outils de développement (jamais installés)
```

## Tests

- **Compilation Windows** : OK (Inno Setup 6.7.3) — dernière refaite le
  29/09/2026 (passe v2.41.0) → `windows/output/avastack-setup-2.41.0.exe`
  (11 468 655 o). Le garde-fou de nommage est vérifié : compilation sans
  `/DAppVersion` REFUSÉE avec le message « AppVersion non defini… » (aucun
  artefact produit).
- **Paquet Linux** : construit le 29/09/2026 (passe v2.41.0) →
  `linux/output/avastack-setup-2.41.0-linux.tar.gz` (62 fichiers, 572 903 o,
  `install_avastack.sh` en 0755, zéro `*.so`/`*.dll`/`*.rules`, dossier racine
  unique `avastack-2.41.0-linux/`).
- **Exécution réelle de l'installateur Linux : FAITE, plusieurs fois** —
  exécuté en réel sur une machine **Ubuntu 26.04 LTS** (constat du 29/09/2026) :
  détection de `python3-tk`, création du venv via `common/avastack_setup.py`,
  installation des dépendances et lancement par le raccourci/`.desktop` sont
  donc exercés en réel (l'application y est employée en séance : astrométrie,
  SPCC et GraXpert fonctionnent côté Linux). Restent à faire : machine
  **vierge** (sans Python) et **test matériel caméras** (option `--cameras`,
  quand les `*.so` constructeurs y seront déposés).
- **Exécution réelle sur machine vierge (Windows)** : à faire — installer sur
  une machine Windows sans Python ni caméra pour valider le chemin
  "téléchargement silencieux de Python" (jamais déclenché sur la machine de
  dev, Python y est déjà présent), et le lancement via raccourci.
- **Test matériel caméras** : fait pour Windows (QHY Minicam8M, Player One
  Uranus-C Pro, Touptek, SVBONY — verdicts des tests des 19-20/09/2026) ; côté
  Linux, à faire quand les `*.so` constructeurs seront récupérés (option
  `--cameras`).
