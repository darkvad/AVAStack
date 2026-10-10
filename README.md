# AVAStack — live stacking pour l'astrophotographie

**Empiler les brutes EN TEMPS RÉEL, pendant l'acquisition.** Pendant que le
logiciel de capture écrit ses fichiers (N.I.N.A., APT, SGP, ASI Air…), AVAStack
les calibre, les aligne et les empile au fur et à mesure, et montre tout de suite
— à l'écran **et** dans les fichiers — un résultat étiré, prêt à juger : le
contrôle qualité de la séance se fait en direct, sans attendre la fin de la nuit.

Il ne remplace pas le logiciel d'acquisition : il **lit** ce que celui-ci
produit, ou pilote directement une caméra. Tout s'installe **dans le profil de
l'utilisateur**, sans droits administrateur.

| | |
|---|---|
| **Plateformes** | Windows 10/11 · Linux · macOS 11+ |
| **Installation** | [dernière release](https://github.com/darkvad/AVAStack/releases/latest) · guide [`INSTALLATION.md`](INSTALLATION.md) |
| **Licence** | MIT — les SDK constructeurs de caméras ne sont **pas** redistribués |
| **Version** | `AVASTACK_VERSION` dans `avastack/__init__.py` (affichée dans la barre de titre) |

## Sommaire

- [Le pipeline](#le-pipeline)
- [Sources d'images](#sources-dimages)
- [Installation](#installation)
- [Première séance](#première-séance)
- [Données astronomiques](#données-astronomiques-astrométrie-photométrie-spcc)
- [Sauvegardes et traçabilité](#sauvegardes-et-traçabilité)
- [Qualité : bancs de non-régression](#qualité--bancs-de-non-régression)
- [Limites connues](#limites-connues)
- [Licence](#licence)

## Le pipeline

1. **Acquisition** — les brutes arrivent d'un ou plusieurs dossiers surveillés
   (un dossier par rôle en composition : `Ha`, `O3`, `S2`, `L`, `R`, `G`, `B`),
   d'une webcam/carte OpenCV, d'un ciel simulé (démo sans matériel) ou d'une
   caméra **ZWO ASI · QHY · Player One · Touptek · SVBONY** par son SDK.
2. **Calibration** — dark et flat, par rôle (composition) ou uniques.
3. **Alignement** — ORB + RANSAC, repli par corrélation de phase ; re-stack
   « à la Siril » sur la meilleure brute ; repère commun entre les rôles.
4. **Empilement** — moyenne avec **rejet kappa-sigma** : le grain du fond
   diminue en 1/√n, cadre commun en composition.
5. **Étirement temps réel** — auto STF ou moteur **VeraLux**, gelable, barres de
   niveaux (Noir / Médian / Blanc), balance des canaux, saturation par teinte.
6. **Mesures** (optionnelles) — **astrométrie** interne (catalogue Gaia DR3),
   **photométrie**, **SPCC** (couleurs absolues, capteurs mono multi-bandes
   *et* couleur).
7. **Traitement externe** (optionnel) — **GraXpert** / **BlurXTerminator** sur un
   **instantané** de l'empilement, dans un thread séparé : l'empilement accumulé
   reste linéaire et intact.
8. **Sauvegardes** — FITS / TIFF 16 bits / PNG 16 bits : empilement **brut
   linéaire**, fichier « tel que vu », ou résultat traité.

## Sources d'images

| Source | À quoi ça sert |
|---|---|
| **Dossier surveillé** | le cas courant : le logiciel de capture écrit, AVAStack empile |
| **Composition multi-dossiers** | un dossier par filtre → composite temps réel (mono, RGB, LRGB, HOO, SHO) |
| **Caméra (SDK constructeur)** | ZWO ASI, QHY, Player One, Touptek/Altair, SVBONY — flux direct, roue à filtres et refroidissement (TEC) |
| **Webcam / carte d'acquisition** | tests, suivi en direct (OpenCV) |
| **Ciel simulé** | démonstration et essais **sans aucun matériel** |

## Installation

| Plateforme | Fichier | Marche à suivre |
|---|---|---|
| **Windows 10/11** | `avastack-setup-<version>.exe` | lancer l'exécutable (il installe Python si besoin, crée l'environnement et les raccourcis) |
| **Windows 10/11** (si l'exécutable est bloqué) | `avastack-setup-<version>-windows.zip` | extraire, puis double-cliquer sur `installer\install_avastack.bat` — aucun exécutable à nous (utile quand le Contrôle intelligent des applications bloque le `.exe`) |
| **Linux x86_64** | `avastack-setup-<version>-linux.tar.gz` | `tar xzf …` puis `bash installer/install_avastack.sh` |
| **macOS 11+** | `avastack-setup-<version>-macos.tar.gz` | `tar xzf …` puis `bash installer/install_avastack.sh` (Python **3.13 récent avec Tkinter** requis : python.org, ou Homebrew + `python-tk`) |

Les **trois** installateurs sont joints à la
[dernière release](https://github.com/darkvad/AVAStack/releases/latest) ; le
détail (prérequis système, dossiers, caméras, dépannage) est dans
[`INSTALLATION.md`](INSTALLATION.md), et un `LISEZMOI.txt` complet est installé
à côté de l'application. Sous macOS, l'installateur écrit un bundle
`~/Applications/AVAStack.app` (double-clic) — **exécuté en réel sur un Mac**
(macOS 27). Prérequis : un **Python 3.13 récent AVEC Tkinter** (python.org, ou
Homebrew + `python-tk`) ; un Python d'ancienne génération pouvait laisser
l'interface figée (voir [`INSTALLATION.md`](INSTALLATION.md) § 3 bis).

## Première séance

1. **Source** : « Dossier surveillé » → choisir le dossier où le logiciel
   d'acquisition écrit ses brutes (FITS/PNG/TIFF).
2. **Données astronomiques** : vérifier la ligne « Catalogues » — c'est ce qui
   débloque l'astrométrie, la photométrie et la SPCC. Les boutons de la fenêtre
   les téléchargent : « ⬇ Gaia » (catalogue astrométrique, ≈ 1,1 Go),
   « ⬇ Spectres (champ) » (les morceaux de spectres Gaia XP qui couvrent la
   cible, ≈ 100–300 Mo ; « ⬇ les 48 » pour tout le ciel, ≈ 10,6 Go) et
   « ⬇ Base SPCC » (profils de capteurs et de filtres, quelques Mo). Reprise
   après coupure et empreintes vérifiées ; **Siril n'est pas requis**.
3. **Astrométrie** : la lancer sur une brute ; l'étoile passe au vert et
   l'échelle s'affiche en ″/pixel.
4. **SPCC** (option) : cocher la case, choisir le **Type de capteur**
   (mono multi-bandes / couleur), le capteur et le filtre.
5. **Empiler** puis **sauvegarder** : les fichiers portent les en-têtes de
   traçabilité qui disent ce qui a été appliqué.

## Données astronomiques (astrométrie, photométrie, SPCC)

Ces trois mesures s'appuient sur des **fichiers d'étoiles**, pas sur des DLL :
le catalogue astrométrique Gaia DR3 de Siril, les 48 morceaux de spectres Gaia XP
et la base de profils SPCC (capteurs, filtres, références de blanc). AVAStack les
**télécharge lui-même** (boutons « ⬇ Gaia », « ⬇ Spectres (champ) » — seulement
les morceaux qui couvrent la cible —, « ⬇ les 48 » et « ⬇ Base SPCC »), les
cherche aussi aux emplacements habituels de Siril, et accepte un dossier choisi
dans l'interface : **Siril n'est pas nécessaire**. Préparation détaillée :
[`INSTALLATION.md`](INSTALLATION.md) § 4.

## Sauvegardes et traçabilité

Chaque fichier écrit dit ce qu'il contient : les en-têtes `AVASPCC`, `AVAGAIA`,
`AVAOUTIL`, `AVACMDGX`, `AVACMDDN`, `AVACMDBX` consignent les coefficients, les
outils externes et leurs paramètres exacts — une image peut donc être réexpliquée
des mois plus tard, et comparée à ce qui était affiché.

## Qualité : bancs de non-régression

Le dépôt contient **80 bancs de non-régression** (`bancs/_test_*.py`) qui
mesurent réellement ce qu'ils vérifient : chaînes de traitement sur images
synthétiques, worker d'acquisition réel sur de vraies brutes FITS, solveurs
factices pour l'astrométrie et la photométrie, mise en page de l'interface…
Ces bancs restent au dépôt ; les **outils de diagnostic matériel caméra**
(`bancs/cameras/_diag_*.py`) sont, eux, embarqués dans les installateurs (ils
parlent aux vraies DLL constructeurs).

## Limites connues

- L'**installateur macOS** n'a pas encore été **exécuté sur un Mac** (29/09/2026) :
  paquet et garde-fous vérifiés au banc, reste le test réel. Son bundle n'est pas
  signé (pas de compte Apple) — clic droit → « Ouvrir » la première fois.
- **Aucune caméra** n'est embarquée (SDK constructeurs, licences) : les `.so`/`.dll`
  sont à déposer à côté de l'application ou désignés par variable
  d'environnement.
- Les **données Gaia** ne sont pas embarquées (≈ 1,1 Go de catalogue
  astrométrique, ≈ 10,6 Go si l'on prend les 48 morceaux de spectres, quelques Mo
  de base SPCC) : les boutons ⬇ d'AVAStack les téléchargent, avec reprise après
  coupure et empreintes vérifiées.
- Les limites de la version courante sont listées franchement à la fin de
  [`INSTALLATION.md`](INSTALLATION.md) § 8.

## Licence

[MIT](LICENSE) pour AVAStack. Les SDK constructeurs de caméras et les
bibliothèques tierces gardent leurs licences propres et ne sont **pas**
redistribués par ce dépôt — notamment l'étirement **VeraLux**
(`veralux_core_headless.py`, extrait de *VeraLux_HyperMetric_Stretch.py* v1.5.2
de Riccardo Paterniti), sous **GPL-3.0-or-later**. Le catalogue d'objets
célèbres embarqué est régénéré depuis **OpenNGC** (© Mattia Verga et
contributeurs, **CC-BY-SA-4.0** — https://github.com/mattiaverga/OpenNGC)
et les catalogues VizieR **VII/20 / VII/220A / VII/7A** (CC-BY-4.0,
miroir Harvard) : ces données gardent leurs licences propres.

Questions, anomalies, propositions : les **issues** de ce dépôt sont l'endroit
indiqué — avec, si possible, la version (`barre de titre`), le journal
(`journal.txt`, cadre « Fichiers de travail et journal ») et la marche suivie.

**Confidentialité** : AVAStack ne collecte **aucune** donnée personnelle et ne
transmet rien ; son seul accès réseau est le téléchargement, à votre demande, de
catalogues astronomiques publics. Détail complet :
[`PRIVACY.md`](PRIVACY.md).

