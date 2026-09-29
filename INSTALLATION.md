# AVAStack — installation rapide (v2.45.0)

AVAStack est un **live stacking** : il empile tes brutes **en temps réel**
pendant l'acquisition (calibration dark/flat, alignement, rejet kappa-sigma,
étirement, histogramme, sauvegardes FITS/TIFF/PNG) et il y ajoute
l'**astrométrie**, la **photométrie**, la **SPCC** (couleurs absolues) et le
passage aux **outils externes** (GraXpert, BlurXTerminator) sur un instantané.
Il tourne sur **Windows, Linux et macOS**, et s'installe **dans ton profil** :
aucun droit administrateur n'est nécessaire.

Ce document accompagne la **release v2.45.0** (les trois installateurs y sont
attachés). Il ne remplace pas le `LISEZMOI.txt` que l'installateur copie à côté
de l'application — celui-ci détaille **tous les réglages** de l'interface.

---

## 1. Les fichiers de cette release

| Plateforme | Fichier | Taille | SHA-256 |
| --- | --- | --- | --- |
| Windows (10/11, 64 bits) | `avastack-setup-2.45.0.exe` | 11,5 Mo | `CC0F742EA1A8DE90E337D3031FC3A8A8DEF71203C15E779AAF7A8F748180EB32` |
| Linux (x86_64) | `avastack-setup-2.45.0-linux.tar.gz` | 584 Kio | `880BD83E24AF837F292CE4877397EB1F887ED36FE5D9A272A60FE29004A0E1B4` |
| macOS (11 et plus) | `avastack-setup-2.45.0-macos.tar.gz` | 582 Kio | `5DFB85E3DF79B4E8185009EC556CB32A1D06F6287DF09C0DF418F114672DF3E5` |
| Documentation | `INSTALLATION.md` | ce fichier | — |

Les artéfacts portent leur **numéro de version** : deux versions ne s'écrasent
jamais, et un installateur plus ancien peut rester à côté comme repli.

> Le dépôt est **public** (licence MIT) : la release et ses fichiers sont
> accessibles à tous, et les empreintes **SHA-256** du tableau ci-dessus
> permettent de vérifier un téléchargement.

---

## 2. Windows — `avastack-setup-2.45.0.exe`

1. **Lancer l'exécutable.** Windows peut afficher un avertissement
   SmartScreen (l'exécutable n'est pas signé) : « Informations
   complémentaires » → « Exécuter quand même ».
2. L'installateur :
   1. vérifie la présence de **Python 3.10+** et, si besoin, le télécharge et
      l'installe silencieusement depuis python.org ;
   2. copie l'application dans `%LOCALAPPDATA%\AVAStack` (dossier modifiable
      pendant l'installation) ;
   3. crée un **venv** et installe les dépendances : `numpy`,
      `opencv-python`, `pillow`, `astropy`, et **`qhyccd`** (le SDK QHY natif
      est inclus dans le paquet pip) ;
   4. écrit les raccourcis **Bureau** et **Menu Démarrer**, plus un
      `lancer_avastack.bat` ;
   5. copie un `LISEZMOI.txt` à côté de l'application.
3. **Lancer AVAStack** par le raccourci.
4. **Caméras** : les SDK des autres marques (ZWO, Player One, Touptek/Altair,
   SVBONY) sont fournis par les constructeurs et **ne sont pas embarqués** —
   copie leurs DLL dans le dossier d'installation de l'application, ou
   désigne un dossier par variable d'environnement (ex.
   `AVASTACK_PLAYERONE_DIR=C:\chemin\vers\SDK\PlayerOne`).

L'application fonctionne **sans aucune caméra** (mode « Dossier surveillé »,
« Composition multi-dossiers », « OpenCV », « Simulée (démo) »).

---

## 3. Linux — `avastack-setup-2.45.0-linux.tar.gz`

```bash
tar xzf avastack-setup-2.45.0-linux.tar.gz
cd avastack-2.45.0-linux
bash installer/install_avastack.sh
```

Le script **teste les prérequis AVANT de copier quoi que ce soit** et dit
exactement quelle commande lancer (Tkinter n'existe pas sur pip : il vient du
paquet système — `python3-tk` sur Debian/Ubuntu, plus `python3-venv`).

Ce qu'il installe, sans droits administrateur :

| Élément | Emplacement |
| --- | --- |
| Application | `~/.local/share/AVAStack` (modifiable : `--prefix`) |
| Lanceur | `~/.local/bin/avastack` |
| Entrée de menu | `~/.local/share/applications/avastack.desktop` |

Options utiles :

```
--prefix DIR      dossier d'installation (défaut : ~/.local/share/AVAStack)
--cameras         installe AUSSI les paquets pip caméras (qhyccd, zwoasi)
                  et copie les bibliothèques constructeurs du paquet
--sans-raccourci  n'écrit ni ~/.local/bin/avastack ni l'entrée .desktop
--forcer          passe outre un garde-fou (ex. Tkinter absent)
--desinstaller    supprime l'installation (GARDE les réglages) ; --purger les
                  supprime aussi
-h, --aide        affiche l'aide
```

**Caméras sous Linux** : ce sont des fichiers `lib*.so` du constructeur (plus
les règles `udev`), pas des paquets pip — le paquet n'en embarque aucun. Dépose
les bibliothèques dans le dossier extrait (ou un sous-dossier `sdk/`) puis
relance `bash installer/install_avastack.sh --cameras` ; l'installateur copie
les `.so` et pose les règles `udev` (avec `sudo`). Sans les règles, la caméra
n'est visible **qu'en root**.

**macOS** : l'installateur macOS existe depuis le **29/09/2026** — voir le § 3 bis.

> **État de cet installateur (à jour le 29/09/2026)** : le paquet Linux est
> construit, son contenu est vérifié (62 fichiers, aucun `.so`/`.dll`, script
> `install_avastack.sh` exécutable, fins de ligne UNIX, racine unique
> `avastack-2.45.0-linux/`) **et il a été exécuté plusieurs fois EN RÉEL sur une
> machine Ubuntu 26.04 LTS** : installation, prérequis système, création du venv,
> dépendances et lancement de l'application y sont validés. Restent à faire : le
> test sur une machine **vierge** (sans Python ni paquets prérequis) et le
> **test matériel caméras** sous Linux (option `--cameras`, quand les `*.so`
> constructeurs y seront déposés).

---

## 3 bis. macOS — `avastack-setup-2.45.0-macos.tar.gz`

```bash
tar xzf avastack-setup-2.45.0-macos.tar.gz
cd avastack-2.45.0-macos
bash installer/install_avastack.sh
```

**Prérequis : un Python AVEC Tkinter** (Tkinter n'est pas installable par pip) :

- Python de **python.org** (Tk inclus) — le plus simple : télécharger 3.12/3.13,
  installer le `.pkg`, puis lancer ce script ;
- ou **Homebrew** : `brew install python@3.13 python-tk@3.13`.

Vérification en une commande : `python3 -c 'import tkinter; print(tkinter.TkVersion)'`.
Le Python livré par macOS (`/usr/bin/python3`) **n'a pas** de Tkinter utilisable :
le script le dit et refuse d'installer sans Tkinter (sauf `--forcer`).

Ce que le script écrit (tout dans ton profil, **aucun droit administrateur**) :

| Élément | Emplacement |
| --- | --- |
| Application (code + venv) | `~/Library/Application Support/AVAStack/app` (modifiable : `--prefix`) |
| Double-clic (bundle `.app`) | `~/Applications/AVAStack.app` |
| Lanceur Terminal | `~/.local/bin/avastack` |
| Réglages / journal | `~/Library/Application Support/AVAStack/` |

Le bundle est **minimal** (Info.plist + lanceur) : il ne contient ni Python ni
venv, il pointe sur l'installation — d'où la mise à jour sans le retoucher. Il
n'est **pas signé ni notarisé** (pas de compte Apple) : si macOS refuse de
l'ouvrir, faire un **clic droit → « Ouvrir »** (une fois), ou lever la
quarantaine :

```bash
xattr -dr com.apple.quarantine ~/Applications/AVAStack.app
```

Désinstallation : `bash installer/install_avastack.sh --desinstaller` (garde les
réglages et les données téléchargées) ; `--purger` supprime aussi les réglages.

> **État de cet installateur (29/09/2026) — daté et sans exagération** : écrit à
> partir de l'installateur **Linux** (éprouvé en réel), vérifié par analyse
> syntaxique (`bash -n`), par **exécution réelle** de ses garde-fous (il refuse
> de s'installer hors macOS, `--aide` répond) et par un banc qui contrôle le
> contenu du paquet (`bancs/_test_installeur_macos_jalon78.py`). Il n'a **pas
> encore été exécuté sur une machine macOS** : c'est le prochain test à faire,
> et le premier retour d'un utilisateur macOS vaut de l'or.

---

## 4. Données astronomiques (catalogues Gaia et base SPCC) — une seule fois

L'**astrométrie**, la **photométrie** et la **SPCC** s'appuient sur les
**données Gaia DR3 de Siril** — des **fichiers d'étoiles**, pas des DLL — et,
pour la SPCC, sur la **base de profils SPCC** (réponses de capteurs,
transmissions de filtres, références de blanc). Rien de tout cela n'est
embarqué dans les installateurs (≈ 11,7 Go au total, licences CC-BY et GPLv3) :
c'est la seule étape à préparer soi-même — **mais AVAStack sait désormais tout
télécharger lui-même** (boutons ⬇, § 4.1), donc **Siril n'est plus nécessaire**.

| Donnée | Sert à | Fichier / dossier | Où AVAStack le cherche (Windows) | (Linux) |
| --- | --- | --- | --- | --- |
| Catalogue astrométrique Gaia DR3 de Siril | astrométrie, photométrie | `siril_cat_healpix8_astro.dat` (ou `.bz2`), ≈ 1,1 Go | dossier choisi (📂) → clés `catalogue_gaia_astro` / `catalogue_gaia_photo` de l'INI de Siril → `%LOCALAPPDATA%\Siril` → `%APPDATA%\AVAStack\catalogues` | dossier choisi → INI de Siril → `~/.local/share/siril` → `~/.local/share/kstars` |
| Spectres Gaia XP (« spectro ») | SPCC, photométrie | `siril_cat1_healpix8_xpsamp_<N>.dat` — **48 morceaux** (0–47), ≈ 10,6 Go au complet | le **même** dossier de catalogues (y compris un sous-dossier `siril_cat1_healpix8_xpsamp/`) | idem |
| Base de profils SPCC (capteurs, filtres, références de blanc) | SPCC | dossier contenant `mono_filters/`, `mono_sensors/`, `osc_filters/`, `osc_sensors/`, `wb_refs/` | `chemin_spcc` choisi (📂 Dossier SPCC) → `%APPDATA%\AVAStack\spcc-database` (copie téléchargée par AVAStack) → `%LOCALAPPDATA%\siril-spcc-database` (aussi `%LOCALAPPDATA%\Siril\spcc-database`) | dossier choisi → `~/.config/AVAStack/spcc-database` → `~/.local/share/siril-spcc-database` |

### 4.1 Le plus simple : tout faire depuis AVAStack (Siril **non** requis)

Les trois données se téléchargent depuis la fenêtre, panneau « Astrométrie »
(cadres « Catalogues » puis « Spectres / Base SPCC ») — **reprise automatique**
si la connexion coupe, **empreintes vérifiées** (Zenodo : sha256 officielles) :

- **catalogue astrométrique** : bouton **« ⬇ Gaia »** → ≈ 1,1 Go (Zenodo
  `14692304`) ;
- **spectres Gaia XP** : bouton **« ⬇ Spectres (champ) »** → seulement les 1 à 4
  morceaux qui couvrent la cible des champs AD/Dec/champ° (≈ 100–300 Mo au lieu
  de 10,6 Go — c'est ce qui suffit à la SPCC et à la photométrie sur ce champ) ;
  **« ⬇ les 48 »** télécharge tout le ciel (≈ 10,6 Go) pour un usage itinérant
  (Zenodo `14738271`) ;
- **base de profils SPCC** : bouton **« ⬇ Base SPCC »** → quelques Mo, tirés de
  l'archive du dépôt public `siril-spcc-database` (GPLv3), extraite dans le
  dossier SPCC (copie propre à AVAStack, sans rien modifier chez Siril).

Un **seul transfert à la fois** : pendant qu'il travaille, les quatre boutons
sont grisés et la ligne d'état annonce le fichier et son pourcentage.

### 4.2 Variantes : Siril installé, ou dépôt manuel

- **Siril 1.4 ou plus récent** (siril.org) : lancer **une fois** une calibration
  SPCC (`Ctrl + Shift + C`) → Siril met en place sa base de profils, qu'AVAStack
  lit ensuite (sans jamais y écrire) ; ses **scripts officiels** (dépôt
  `siril-scripts`) téléchargent aussi les catalogues Gaia, dans le dossier de ses
  préférences (onglet **Astrométrie**).
- **Dépôt manuel** : les fichiers du tableau ci-dessus peuvent être posés à la
  main dans le dossier affiché par AVAStack (catalogue astro `.dat`/`.bz2`,
  morceaux `siril_cat1_healpix8_xpsamp_<N>.dat.bz2` à la racine ou dans un
  sous-dossier — les deux sont lus) ; pour la base SPCC, recopier le contenu du
  dépôt `siril-spcc-database` dans le dossier affiché par « 📂 Dossier SPCC ».

### 4.3 Vérifier en cinq secondes, dans AVAStack

- La ligne **« Catalogues »** (panneau « Astrométrie ») dit le dossier utilisé,
  si le catalogue astro est présent et **combien de morceaux spectro** sont
  installés :
  - `catalogue astro : présent (siril_cat_healpix8_astro.dat) — spectres Gaia : 48/48 morceaux` → tout est là ;
  - `catalogue astro : ABSENT — l'astrométrie interne ne peut pas aboutir (bouton ⬇ Gaia, ou déposer le fichier ici)` → il manque le fichier astro.
- La ligne **« Base SPCC »** dit le dossier des profils et son contenu
  (`Base SPCC : …\spcc-database — mono 15, mono 13, osc 48, osc 46, wb 144`) ;
  si elle annonce `ABSENTE`, le bouton **« ⬇ Base SPCC »** la télécharge — la
  case **SPCC** devient alors cochable **sans redémarrer** l'application.
  AVAStack **n'invente jamais** de courbes : sans base, il refuse et l'explique.
- Les boutons **📂 Dossier** (catalogues) et **📂 Dossier SPCC** mémorisent leur
  choix entre deux sessions.
- Autre voie, indépendante de Siril : **ASTAP** (`astap_cli` + une base
  d'étoiles G18/H18) est détecté automatiquement (PATH, `C:\Program Files\astap`,
  emplacements Linux/macOS) et sert de solutionneur de secours.

---

## 5. Caméras (facultatif : sans elles, tout le reste fonctionne)

| Marque | Windows | Linux |
| --- | --- | --- |
| **QHY** | rien à faire : le SDK est inclus dans le paquet pip `qhyccd` | `--cameras` |
| ZWO | `ASICamera2.dll` (fournie par le constructeur) | `libASICamera2.so` + `asi.rules` |
| Player One | `PlayerOneCamera.dll` | `libPlayerOneCamera.so` + règles, et `libusb-1.0-0` |
| Touptek / Altair | `ToupCam.dll` | `libtoupcam.so` + règles |
| SVBONY | `SVBCameraSDK.dll` | `libSVBCameraSDK.so` + règles |

Windows : copie les DLL dans le dossier de l'application (ou désigne un dossier
avec `AVASTACK_<MARQUE>_DIR`). Linux : dépose les `.so` dans le dossier extrait
puis `bash installer/install_avastack.sh --cameras`.

Des **outils de diagnostic caméra** sont installés avec l'application (sous
`bancs/cameras`) : `_diag_camera_qhy.py`, `_diag_camera_playerone.py`,
`_diag_camera_svbony.py`, `_diag_camera_touptek.py`, `_diag_qhy_sdk.py`. Ils
utilisent le même code que l'application mais **hors** de celle-ci : c'est ce
qu'il faut lancer quand une caméra n'est pas vue (ils disent quelle DLL manque).

---

## 6. Première séance — la check-list

1. **Source d'images** : « Dossier surveillé » → choisis le dossier où ton
   logiciel d'acquisition écrit ses brutes (FITS/PNG/TIFF).
2. **Catalogues** : vérifie la ligne « Catalogues » (§ 4.3) — c'est ce qui
   débloque l'astrométrie, la photométrie et la SPCC.
3. **Astrométrie** : résous une brute ; l'étoile passe au vert et l'échelle
   s'affiche en ″/pixel.
4. **SPCC** (si tu la veux) : coche la case, choisis le **Type de capteur**
   (« Mono (filtres R/G/B) » ou « **Couleur (OSC)** »), le capteur et le filtre.
   En OSC **un seul filtre** couvre les trois bandes (les lignes G/B sont
   grisées) ; si tes brutes sont prises **sans filtre**, laisse « **No filter** »
   — l'application n'applique jamais un LPF réel en silence.
5. **Empile** (l'accumulation est continue), puis **sauvegarde** : les fichiers
   portent les en-têtes de traçabilité (`AVASPCC`, `AVAGAIA`, `AVAOUTIL`,
   `AVACMDGX`, `AVACMDDN`, `AVACMDBX`) qui disent ce qui a été appliqué.

---

## 7. Régler, dépanner, où sont les réglages

- **Réglages persistants** (`config.json`) :
  `%APPDATA%\AVAStack` (Windows), `~/.config/AVAStack` (Linux),
  `~/Library/Application Support/AVAStack` (macOS).
- **Journal** : cadre « Fichiers de travail et journal », **en haut** de la
  colonne de gauche (le journal ne se cherche pas dans une zone défilante).
- **Le démarrage ne peut plus se bloquer** : un NAS ou un montage réseau
  injoignable est **dit** au lieu d'être attendu (les mesures de disque sont
  différées et bornées).
- **Dossier de travail** : le dossier choisi dans l'interface, affiché en clair
  (c'est là que vivent les fichiers de travail et le journal).
- Un `LISEZMOI.txt` détaillé est installé à côté de l'application.

---

## 8. Limites connues de la v2.45.0 (dites franchement)

- **Installateur Linux : TESTÉ EN RÉEL** — exécuté **plusieurs fois** sur une
  machine **Ubuntu 26.04 LTS** (installation, prérequis, venv, dépendances,
  lancement) ; l'application y est employée en séance, astrométrie, SPCC et
  GraXpert comprises.
- Restent à faire : l'installateur Linux sur une machine **vierge** (sans Python
  ni paquets prérequis) et le **test matériel caméras** sous Linux (option
  `--cameras`, quand les `*.so` constructeurs y seront déposés).
- **Installateur macOS : ÉCRIT mais PAS ENCORE EXÉCUTÉ sur un Mac** (29/09/2026) —
  contenu du paquet vérifié au banc et garde-fous essayés en réel (refus hors
  macOS, `--aide`), mais c'est le prochain test à faire sur une vraie machine ;
  la signature/notarisation Apple n'est pas faite (bundle local non signé).
- **Aucune caméra** n'est embarquée (SDK constructeurs, licences).
- Les **données Gaia** ne sont pas embarquées : ≈ 1,1 Go (catalogue astro),
  ≈ 10,6 Go (les 48 morceaux de spectres — le bouton « ⬇ les 48 ») et quelques
  Mo de base SPCC. Les boutons ⬇ d'AVAStack les récupèrent, mais un
  téléchargement interrompu **reprend** à l'endroit où il s'est arrêté (relancer
  le bouton), et un fichier déjà conforme n'est jamais retéléchargé.
- La base de profils SPCC est publiée sous **GPLv3** : elle est téléchargée à la
  demande dans un dossier propre à AVAStack (elle n'est **pas** redistribuée par
  ses installateurs).

## 9. Repli si régression

Le repli de référence est la **v2.44.0**. Les installateurs des versions
antérieures restent à côté des nouveaux, dans `installer/windows/output/`,
`installer/linux/output/` et `installer/macos/output/` : aucun nouveau
installateur n'écrase une version précédente.

## 10. Liens utiles

- Dépôt AVAStack : `https://github.com/darkvad/AVAStack` (**public**, licence MIT)
- Siril : `https://siril.org` — scripts officiels : `https://gitlab.com/free-astro/siril-scripts`
- Base de profils SPCC : `https://gitlab.com/free-astro/siril-spcc-database`
- Catalogue astrométrique Gaia DR3 de Siril (Zenodo) : enregistrement `14692304`
- Catalogue SPCC local Gaia DR3 XP (Zenodo, 48 morceaux) : enregistrement `14738271`
