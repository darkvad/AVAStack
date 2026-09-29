# installer/ — AVAStack

Installateurs d'AVAStack (live stacking) — déploiement LOCAL, aucun droit
administrateur requis (tout s'installe dans le profil de l'utilisateur) :

| Plateforme | Artéfact | Produit par |
| --- | --- | --- |
| Windows | `windows/output/avastack-setup-<version>.exe` | `windows/build_avastack.ps1` (Inno Setup 6) |
| Linux | `linux/output/avastack-setup-<version>-linux.tar.gz` | `linux/build_avastack.py` |

Installation pas à pas (les deux plateformes, **et la préparation des données
Gaia** — catalogue astrométrique, morceaux de spectres, base de profils SPCC) :
**`INSTALLATION.md`**, à la racine du dépôt ; il est joint à chaque release comme
document d'accompagnement. AVAStack télécharge lui-même ces trois données
(boutons ⬇ de la fenêtre) : **Siril est facultatif** (utile seulement si l'on
préfère le laisser préparer ses catalogues).

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
   depuis python.org si absent).
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
    LISEZMOI.txt          lisez-moi utilisateur (copié à l'installation)
    output/               artefact compilé (gitignore) :
                          avastack-setup-<version>.exe
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
