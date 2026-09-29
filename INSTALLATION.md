# AVAStack — installation rapide (v2.41.0)

AVAStack est un **live stacking** : il empile tes brutes **en temps réel**
pendant l'acquisition (calibration dark/flat, alignement, rejet kappa-sigma,
étirement, histogramme, sauvegardes FITS/TIFF/PNG) et il y ajoute
l'**astrométrie**, la **photométrie**, la **SPCC** (couleurs absolues) et le
passage aux **outils externes** (GraXpert, BlurXTerminator) sur un instantané.
Il tourne sur **Windows, Linux et macOS**, et s'installe **dans ton profil** :
aucun droit administrateur n'est nécessaire.

Ce document accompagne la **release v2.41.0** (les deux installateurs y sont
attachés). Il ne remplace pas le `LISEZMOI.txt` que l'installateur copie à côté
de l'application — celui-ci détaille **tous les réglages** de l'interface.

---

## 1. Les fichiers de cette release

| Plateforme | Fichier | Taille | SHA-256 |
| --- | --- | --- | --- |
| Windows (10/11, 64 bits) | `avastack-setup-2.41.0.exe` | 11,5 Mo | `FC81DD442E85F2EAE6D0A9560A41BC4D5A3F3A9B97E163DCF12787BC07253BA9` |
| Linux (x86_64) | `avastack-setup-2.41.0-linux.tar.gz` | 560 Kio | `16017928AE3587DFF4696B0E3F6005F738849F7BB8C32DD164C614660B055738` |
| Documentation | `INSTALLATION.md` | ce fichier | — |

Les artéfacts portent leur **numéro de version** : deux versions ne s'écrasent
jamais, et un installateur plus ancien peut rester à côté comme repli.

> Le dépôt est **privé** : cette release l'est aussi. Les liens ci-dessus ne
> fonctionnent que pour les comptes autorisés sur le dépôt.

---

## 2. Windows — `avastack-setup-2.41.0.exe`

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

## 3. Linux — `avastack-setup-2.41.0-linux.tar.gz`

```bash
tar xzf avastack-setup-2.41.0-linux.tar.gz
cd avastack-2.41.0-linux
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

**macOS** : il n'y a pas encore d'installateur. AVAStack se lance depuis les
sources (`python3 AVAStack.py` dans le dossier de l'application).

> **État de cet installateur (à jour le 29/09/2026)** : le paquet Linux est
> construit, son contenu est vérifié (62 fichiers, aucun `.so`/`.dll`, script
> `install_avastack.sh` exécutable, fins de ligne UNIX, racine unique
> `avastack-2.41.0-linux/`) **et il a été exécuté plusieurs fois EN RÉEL sur la
> machine d'Alain (Ubuntu 26.04 LTS)** : installation, prérequis système,
> création du venv, dépendances et lancement de l'application y sont validés.
> Restent à faire : le test sur une machine **vierge** (sans Python ni paquets
> prérequis) et le **test matériel caméras** sous Linux (option `--cameras`,
> quand les `*.so` constructeurs y seront déposés).

---

## 4. Siril et ses catalogues (à faire UNE fois)

L'**astrométrie**, la **photométrie** et la **SPCC** s'appuient sur les
**données Gaia DR3 de Siril** — des **fichiers d'étoiles**, pas des DLL — et,
pour la SPCC, sur la **base de profils de Siril** (réponses de capteurs,
transmissions de filtres, références de blanc). Rien de tout cela n'est
embarqué dans les installateurs (≈ 1,1 Go, licence CC-BY) : c'est la seule
étape à préparer soi-même.

| Donnée | Sert à | Fichier / dossier | Où AVAStack le cherche (Windows) | (Linux) |
| --- | --- | --- | --- | --- |
| Catalogue astrométrique Gaia DR3 de Siril | astrométrie, photométrie | `siril_cat_healpix8_astro.dat` (ou `.bz2`), ≈ 1,1 Go | dossier choisi (📂) → clés `catalogue_gaia_astro` / `catalogue_gaia_photo` de l'INI de Siril → `%LOCALAPPDATA%\Siril` → `%APPDATA%\AVAStack\catalogues` | dossier choisi → INI de Siril → `~/.local/share/siril` → `~/.local/share/kstars` |
| Spectres Gaia XP (« spectro ») | SPCC, photométrie | `siril_cat1_healpix8_xpsamp_<N>.dat` — **48 morceaux** | le **même** dossier de catalogues (y compris un sous-dossier `siril_cat1_healpix8_xpsamp/`) | idem |
| Base de profils SPCC de Siril | SPCC : capteurs, filtres, références de blanc | dossier `siril-spcc-database` contenant `mono_filters/`, `osc_filters/`, `osc_sensors/`, `wb_refs/` | `%LOCALAPPDATA%\siril-spcc-database` (aussi `%LOCALAPPDATA%\Siril\spcc-database`) | `~/.local/share/siril-spcc-database` |

### 4.1 Le plus simple : installer Siril une fois

1. Installer **Siril 1.4 ou plus récent** (siril.org) — Windows, macOS, Linux.
2. Lancer **une fois** une calibration SPCC dans Siril (`Ctrl + Shift + C`) :
   c'est ce geste qui met en place la **base de profils** dans le dossier
   attendu ci-dessus. AVAStack la lit ensuite, sans jamais y écrire.
3. Siril sait aussi télécharger les **catalogues Gaia** (astrométrique **et**
   SPCC/spectro) avec ses **scripts officiels** (dépôt `siril-scripts`,
   accessibles depuis le menu « Scripts » de Siril). Le dossier de destination
   est celui de ses préférences → onglet **Astrométrie**.

### 4.2 Ou tout faire depuis AVAStack

- **Catalogue astrométrique** : panneau « Astrométrie » → bouton **« ⬇ Gaia »**
  → téléchargement (≈ 1,1 Go) dans le dossier affiché, avec **reprise
  automatique** si la connexion coupe et **sha256 vérifiée** (Zenodo,
  enregistrement `14692304`). Tu peux aussi déposer toi-même le fichier
  `siril_cat_healpix8_astro.dat` (ou `.bz2`) dans le dossier affiché.
- **Spectres Gaia XP (48 morceaux)** : AVAStack **n'a pas encore de bouton pour
  eux** (v2.41.0) — c'est le seul point qui demande Siril ou un téléchargement
  manuel :
  - laisser **Siril** installer son catalogue SPCC local (scripts officiels) —
    il écrit les `siril_cat1_healpix8_xpsamp_<N>.dat` dans le dossier des
    catalogues ;
  - ou les prendre à la main : Zenodo, enregistrement **14738271**, 48 fichiers
    `siril_cat1_healpix8_xpsamp_<N>.dat.bz2`, à poser dans le dossier affiché
    (à la racine ou dans un sous-dossier — les deux sont lus).
- **Base de profils SPCC sans installer Siril** : son contenu est publié dans
  le dépôt `siril-spcc-database` ; copie-le dans le dossier attendu du tableau
  ci-dessus. AVAStack considère la base « présente » dès qu'il y trouve un
  dossier `mono_filters`.

### 4.3 Vérifier en cinq secondes, dans AVAStack

- La ligne **« Catalogues »** (panneau « Astrométrie ») dit le dossier utilisé,
  si le catalogue astro est présent et **combien de morceaux spectro** sont
  installés :
  - `catalogue astro : présent (siril_cat_healpix8_astro.dat) — spectres Gaia : 48 chunk(s)` → tout est là ;
  - `catalogue astro : ABSENT — l'astrométrie interne ne peut pas aboutir (bouton ⬇ Gaia, ou déposer le fichier ici)` → il manque le fichier astro.
- La case **SPCC** : si elle est grisée, la ligne du dessous dit pourquoi —
  `SPCC : base de profils de Siril introuvable (%LOCALAPPDATA%\siril-spcc-database) — installez Siril et lancez une calibration SPCC une fois`.
  AVAStack **n'invente jamais** de courbes : sans base, il refuse et l'explique.
- Les boutons **📂 Dossier** (choisir un autre dossier de catalogues, choix
  mémorisé entre deux sessions) et **⬇ Gaia** sont sur la même ligne.
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

## 8. Limites connues de la v2.41.0 (dites franchement)

- **Installateur Linux : TESTÉ EN RÉEL** — exécuté **plusieurs fois** par Alain
  sur sa machine **Ubuntu 26.04 LTS** (installation, prérequis, venv, dépendances,
  lancement) ; l'application y est employée, et ses mesures y sont validées
  (astrométrie, SPCC, GraXpert — constats des 27 et 28/09/2026).
- Restent à faire : l'installateur Linux sur une machine **vierge** (sans Python
  ni paquets prérequis) et le **test matériel caméras** sous Linux (option
  `--cameras`, quand les `*.so` constructeurs y seront déposés).
- Pas d'installateur **macOS** : lancement depuis les sources.
- **Aucune caméra** n'est embarquée (SDK constructeurs, licences).
- Pas de bouton pour les **48 morceaux de spectres Gaia** : téléchargement via
  Siril ou à la main (Zenodo `14738271`).
- Le dépôt étant **privé**, la release et ses fichiers le sont aussi.

## 9. Repli si régression

Le repli de référence est la **v2.40.0**. Sur la machine de développement, les
installateurs des versions antérieures restent à côté des nouveaux, dans
`installer/windows/output/` et `installer/linux/output/` (dossier ignoré par
git) : aucun nouveau installateur n'écrase une version précédente.

## 10. Liens utiles

- Dépôt AVAStack : `https://github.com/darkvad/AVAStack` (**privé**)
- Siril : `https://siril.org` — scripts officiels : `https://gitlab.com/free-astro/siril-scripts`
- Base de profils SPCC : `https://gitlab.com/free-astro/siril-spcc-database`
- Catalogue astrométrique Gaia DR3 de Siril (Zenodo) : enregistrement `14692304`
- Catalogue SPCC local Gaia DR3 XP (Zenodo, 48 morceaux) : enregistrement `14738271`
