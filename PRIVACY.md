# AVAStack — Politique de confidentialité

**Dernière mise à jour : 2 octobre 2026.**

S'applique à l'application **AVAStack** (Windows, Linux, macOS), y compris sa
version distribuée sur le Microsoft Store.

## En résumé

- **Aucune donnée personnelle n'est collectée**, ni transmise, ni vendue.
- **Aucun compte**, aucune inscription, aucun identifiant d'appareil.
- **Aucune télémétrie, aucune statistique d'usage, aucune publicité.**
- **Vos images ne quittent jamais votre ordinateur** : empilement, astrométrie,
  photométrie et SPCC sont calculés **localement**.
- Le **seul accès réseau** sert à **télécharger**, à votre demande, des fichiers
  de référence astronomique **publics**. Rien n'est envoyé en retour.

## Ce qu'AVAStack ne fait pas

AVAStack ne collecte ni ne transmet : nom, adresse, courriel, téléphone,
identifiant de compte ou de connexion, identifiant d'appareil, adresse IP
conservée, données de localisation, contacts, contenu de vos fichiers
personnels, statistiques d'usage ou de plantage.

L'application ne comporte **ni publicité, ni traqueur, ni profil utilisateur**,
et ne partage rien avec des tiers : puisqu'elle ne collecte rien, elle n'a
aucun destinataire.

## Ce qui reste sur votre ordinateur

AVAStack n'écrit que dans les emplacements prévus par votre système :

| Élément | Emplacement |
| --- | --- |
| Réglages (`config.json`) | `%APPDATA%\AVAStack` (Windows), `~/Library/Application Support/AVAStack` (macOS), `~/.config/AVAStack` (Linux, respecte `XDG_CONFIG_HOME`) |
| Journal d'exécution (`journal.txt`) | **le même dossier** que les réglages |
| Catalogues téléchargés | `<dossier de réglages>\catalogues` et `<dossier de réglages>\spcc-database` |
| Images empilées (FITS / TIFF / PNG) | **les dossiers que vous choisissez** |

Ces fichiers restent chez vous. Les supprimer ne gêne pas l'application : elle
les recrée (les réglages repartent alors de leurs valeurs par défaut).

Si **Siril** est installé sur la machine, AVAStack **lit** son fichier de
configuration pour y trouver les catalogues — **en lecture seule**, sans rien y
modifier.

**Sous Windows, version Microsoft Store** : le paquet est une application de
bureau « pleine confiance » (comme tout logiciel installé classiquement) ; elle
n'accède qu'aux fichiers et dossiers que **vous** désignez, ne demande **aucun
droit administrateur**, n'installe ni pilote ni service et ne se lance **jamais
d'elle-même** (ni au démarrage du système, ni après avoir été fermée).

## Le seul accès réseau

Une seule partie du code ouvre une connexion : le téléchargement de
**catalogues de référence publics**, et **uniquement quand vous cliquez sur un
bouton de téléchargement** dans l'application (« ⬇ Gaia », « ⬇ Spectres
(champ) », « ⬇ les 48 », « ⬇ Base SPCC ») :

| Donnée téléchargée | Source |
| --- | --- |
| Catalogue astrométrique Gaia DR3 (distribution Siril) | `zenodo.org` |
| 48 morceaux de spectres Gaia XP | `zenodo.org` |
| Base de profils SPCC (`siril-spcc-database`) | `gitlab.com` |

Le catalogue d'**objets célèbres** (étiquettes d'annotation) est
**embarqué dans l'application** : il ne se télécharge pas, il est copié
depuis l'installation vers le dossier des catalogues. Il a été régénéré
hors ligne depuis [OpenNGC](https://github.com/mattiaverga/OpenNGC)
(CC-BY-SA-4.0) et les catalogues VizieR VII/20, VII/220A et VII/7A
(CC-BY-4.0, miroir Harvard).

Ces requêtes sont des **lectures** : elles demandent un fichier et le reçoivent.
**Rien n'est transmis** — ni vos images, ni vos réglages, ni une identification
quelconque, au-delà de l'en-tête technique que ces sites exigent de tout client
web. Les fichiers téléchargés sont vérifiés (empreinte SHA-256) et repris après
une coupure réseau.

Il n'y a **aucun contrôle de mise à jour en ligne** : l'application ne contacte
pas le dépôt du projet et ne signale aucune nouvelle version.

## Outils externes (facultatifs)

AVAStack peut **lancer** des logiciels que vous possédez déjà (GraXpert,
BlurXTerminator, ASTAP, Siril) sur des copies de vos images, **en local**. Ces
programmes sont **indépendants** : ce qu'ils font ensuite — y compris un accès
réseau de leur part, par exemple le téléchargement de leurs propres modèles —
relève de **leur** politique de confidentialité, pas de celle-ci.

## Le journal, à relire avant de l'envoyer

Le journal d'exécution (`journal.txt`) sert au diagnostic : il décrit les étapes
du démarrage, les erreurs et l'environnement technique (versions, OS,
répertoire de travail et son espace libre). Il peut donc contenir des **chemins
locaux** (nom du dossier de travail, nom d'utilisateur de votre système). Il ne
quitte **jamais** votre ordinateur de lui-même : si vous le joignez à un rapport
de bug (les *issues* du dépôt), relisez-le d'abord.

## Enfants

L'application ne collecte aucune donnée, quel que soit l'âge de l'utilisateur,
et ne comporte ni contenu ni interaction en ligne. Sa classification d'âge
reflète cette absence de contenu sensible.

## Modifications

Cette politique peut évoluer avec l'application : la **date en tête** change à
chaque révision, et l'historique complet de ce fichier reste consultable dans
l'historique Git du dépôt.

## Contact

Les **issues** du dépôt du projet :
<https://github.com/darkvad/AVAStack/issues>

---

## Summary in English

AVAStack does **not collect, store or transmit any personal data**: no account,
no telemetry, no analytics, no advertising, no device identifier. Your images
never leave your computer — stacking, astrometry and photometry are computed
locally. The only network access is a **read-only download** of public
astronomical reference catalogues (from `zenodo.org` and `gitlab.com`),
triggered only when you click a download button in the application; nothing is
sent back, and there is no online update check. Settings and a diagnostic log
are stored locally (`%APPDATA%\AVAStack` on Windows) and the log may contain
local file paths — review it before sharing it in a bug report. Optional
external tools that you launch yourself (GraXpert, BlurXTerminator, ASTAP,
Siril) are separate programs with their own privacy policies.
