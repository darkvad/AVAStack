# installer/ — AVAStack

Installateur Windows pour AVAStack (live stacking) — déploiement local,
aucun droit administrateur requis (installe dans le profil utilisateur).

## Ce que fait l'installateur (avastack-setup.exe)

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

## Compilation

Méthode recommandée — le wrapper lit la version dans `avastack/__init__.py`
(`AVASTACK_VERSION`, source unique de vérité) et la passe à ISCC via
`/DAppVersion=...` :

```
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_avastack.ps1
```

Compilation manuelle (sans wrapper) : `ISCC.exe avastack.iss` — dans ce cas
vérifier le `#define AppVersion` de repli du script (seule `AVASTACK_VERSION`
du source fait foi).

Artefact : `output/avastack-setup.exe` (~2 Mo). Rebuilder l'installateur après
toute montée de version de l'application (le numéro embarqué suit le source
avec le wrapper).

## Structure

```
installer/
  common/
    avastack_setup.py     création de venv + dépendances (stdlib only),
                          appelé par l'installateur à la fin
  windows/
    avastack.iss          script Inno Setup (version passée via /DAppVersion)
    build_avastack.ps1    wrapper ISCC : lit AVASTACK_VERSION, appelle ISCC
    LISEZMOI.txt          lisez-moi utilisateur (copié à l'installation)
    output/               artefact compilé (gitignore)
```

## Tests

- **Compilation** : OK (Inno Setup 6.7.3, zéro warning) — refaite avec la
  version d'application v2.13.0 (jalon 24, gradient + débruitage par couche).
- **Exécution réelle sur machine vierge** : à faire — installer sur une
  machine Windows sans Python ni caméra pour valider le chemin
  "téléchargement silencieux de Python" (jamais déclenché sur la machine de
  dev, Python y est déjà présent), et le lancement via raccourci.
- **Test matériel caméras** : à faire avec les vraies caméras d'Alain
  (QHY Minicam8M — test prévu à la nuit du jour, Player One Uranus-C Pro,
  Touptek, SVBONY).
