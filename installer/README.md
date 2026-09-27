# installer/ — AVAStack

Installateurs d'AVAStack (live stacking) — déploiement LOCAL, aucun droit
administrateur requis (tout s'installe dans le profil de l'utilisateur) :

| Plateforme | Artéfact | Produit par |
| --- | --- | --- |
| Windows | `windows/output/avastack-setup-<version>.exe` | `windows/build_avastack.ps1` (Inno Setup 6) |
| Linux | `linux/output/avastack-setup-<version>-linux.tar.gz` | `linux/build_avastack.py` |

**Le nom de l'artéfact PORTE LA VERSION** (consigne d'Alain, 27/09/2026) : elle
vient toujours de `AVASTACK_VERSION` (`avastack/__init__.py`), jamais d'un nom
figé — `avastack.iss` refuse même de compiler sans `/DAppVersion`. Deux
versions ne s'écrasent donc jamais (celle d'avant reste à côté et sert de
repli). Détail : CLAUDE.md, section « Installateur et tests réels ».

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

## Ce que l'installateur n'embarque PAS

- Les **SDK binaires constructeurs** (ASICamera2.dll, PlayerOneCamera.dll,
  toupcam.dll, SVBCameraSDK.dll) : code propriétaire, jamais dans le dépôt ni
  dans l'installeur. L'utilisateur les télécharge et les dépose dans le
  dossier d'installation (instructions dans LISEZMOI.txt).
- Exception QHY : le paquet `qhyccd` (PyPI, MIT/Apache) **inclut** le SDK
  natif QHYCCD — aucune manipulation pour l'utilisateur.

## Installateur Linux (route ① retenue par Alain, 27/09/2026 : script + venv)

`linux/install_avastack.sh` — même esprit que l'installateur Windows, mais en
bash et sans rien qui ressemble à une DLL :

1. Teste les **prérequis système** AVANT toute copie : `python3` ≥ 3.10,
   `python3-venv` (ensurepip) et **`python3-tk`** (Tkinter n'existe pas sur
   pip) ; en cas de manque il affiche la commande exacte pour Debian/Ubuntu,
   Fedora et Arch, puis s'arrête (option `--forcer` pour passer outre).
2. Copie l'application dans `~/.local/share/AVAStack` (option `--prefix`),
   avec les bancs et diagnostics autonomes, et note la version installée dans
   `VERSION.txt`.
3. Crée le venv et installe les dépendances via `common/avastack_setup.py` —
   le MÊME outil que l'installateur Windows (une seule route d'installation
   des dépendances à maintenir).
4. Écrit `lancer_avastack.sh`, la commande `~/.local/bin/avastack` et l'entrée
   de menu `~/.local/share/applications/avastack.desktop`.
5. **Vérifie le résultat en interprétant réellement** : Tkinter,
   numpy/OpenCV/Pillow (avec le rappel `libgl1`/`libglib2.0-0`), astropy et
   l'état des caméras.

**CAMÉRAS : ABSENTES dans cette version** (livraison voulue par Alain) — aucun
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

## Tests

- **Compilation Windows** : OK (Inno Setup 6.7.3) — dernière refaite le
  27/09/2026 sur la passe v2.38.3 → `windows/output/avastack-setup-2.38.3.exe`.
  Le garde-fou de nommage est vérifié : compilation sans `/DAppVersion`
  REFUSÉE avec le message « AppVersion non defini… » (aucun artefact produit).
- **Paquet Linux** : construit le 27/09/2026 →
  `linux/output/avastack-setup-2.38.3-linux.tar.gz` (162 fichiers, 773 Kio,
  `install_avastack.sh` en 0755, zéro `*.so`/`*.dll`/`*.rules`, dossier racine
  unique `avastack-2.38.3-linux/`).
- **Exécution réelle de l'installateur Linux : À FAIRE par Alain** — le script
  n'a PAS pu être exécuté sur la machine de développement (Windows, sans bash
  ni WSL) : ce qui est validé ici est sa rédaction (garde-fous, options,
  inventaire du paquet) et la présence de tous les fichiers dont il dépend.
  À vérifier au premier essai : détection de `python3-tk`, création du venv via
  `common/avastack_setup.py`, lancement par le raccourci/`.desktop`, ouverture
  d'un dossier de brutes, message clair quand une source caméra est choisie.
- **Exécution réelle sur machine vierge (Windows)** : à faire — installer sur
  une machine Windows sans Python ni caméra pour valider le chemin
  "téléchargement silencieux de Python" (jamais déclenché sur la machine de
  dev, Python y est déjà présent), et le lancement via raccourci.
- **Test matériel caméras** : fait pour Windows (QHY Minicam8M, Player One
  Uranus-C Pro, Touptek, SVBONY — verdicts d'Alain 19-20/09/2026) ; côté Linux,
  à faire quand les `*.so` constructeurs seront récupérés (option `--cameras`).
