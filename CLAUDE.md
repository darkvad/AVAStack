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

Trois boutons d enregistrement aux rôles DISTINCTS — ne jamais fusionner :

- **« 💾 Enregistrer l'empilement (linéaire)… »** et **« 💾 Enregistrer le
  résultat traité (linéaire)… »** : sauvegardent l image LINÉAIRE (pile
  brute, ou résultat GraXpert/BXT sans étirement) — voulu, pour retraitement
  ultérieur dans un logiciel dédié. Comportement historique, inchangé.
- **« 💾 Enregistrer tel que vu (étiré)… »** : SEUL bouton qui applique la
  chaîne d étirement complète en PLEINE résolution (jamais l aperçu
  1600 px) : `DisplayProcessor.rendu_pleine_resolution()` — fonction PURE
  (aucun état partagé : pas de stats EMA, pas de solveur, jamais
  black/white/gamma). VeraLux y réutilise le DERNIER logD résolu (rendu
  identique à l écran, sans re-résolution). GraXpert live ne s applique
  qu en vue « empilement » (en vue « traitée », l image a déjà subi le
  traitement externe — le relancer ferait un DEUXIÈME traitement ; synchro
  `_sync_vl_graxpert_vue`). Les réglages STF sont MASQUÉS (pas grisés) en
  mode VeraLux — ils n y ont aucun effet.

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

- **DÉBRUITAGE LOCAL CLASSIQUE SUR STACKS ASTRO = FOND « LÉOPARD »**
  (expérience ABANDONNÉE par Alain le 15/09/2026, jalons 7/8/9 — code
  retiré du dépôt, trace complète dans AVANCEMENT.md § « Expérience
  abandonnée », code dans le stash). Constat réel : ondelettes à trous
  (starlet) ET Non-local Means OpenCV créent tous deux un moutonnement
  en plaques dès que la force est utile ; à force réduite, le bruit
  résiduel AUTOUR DES ÉTOILES rend le fond lisse encore plus visible par
  contraste. Causes identifiées : seuiller des niveaux GROSSIERS de la
  transformée (structure, pas bruit), seuil DUR (îlots), h/fenêtre de
  recherche NLM trop grands (la fenêtre FIXE l'échelle des plaques) — et
  structurellement, le bruit élevé d'un empilement live peu intégré.
  À retenir : (1) ne JAMAIS valider un débruiteur sur du bruit pur
  synthétique (les réglages agressifs y paraissent meilleurs) — image
  réelle obligatoire dès la première passe ; (2) si le sujet est reposé,
  viser des méthodes épargnant les étoiles par conception (IA légère
  locale type Noise2* entraîné astro) plutôt que re-raffiner le
  pixel-classique.
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
  n'est pas concerné (d'où des succès intermittents trompeurs). Parade dans
  `avastack/external/live.py` : entrée RGB écrite canaux-en-tête
  (`_ecrire_entree`) + sortie retransposée (`_lire_sortie`). NB : l'entrée
  TIFF plante aussi chez GraXpert (imagecodecs LZW absent de leur build).
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

## Maintenance des fichiers de connaissance (CLAUDE.md)

Ce fichier sert de mémoire à long terme pour les agents IA. **Règle
fondamentale : l agent ne modifie JAMAIS ce fichier de son propre chef.** Il
doit : (1) identifier une information digne d être retenue, (2) proposer la
mise à jour dans la conversation avec le texte exact, (3) attendre la
confirmation explicite d Alain avant d agir, (4) confirmer l action réalisée.

Déclencheurs de proposition : nouvelle erreur récurrente, nouveau
comportement inattendu, découverte architecturale, modification importante
du code, piège rencontré sur un outil externe. Cible : section « Pièges »
(à créer le cas échéant) ou ajustement des conventions.

**Exemple de dialogue** :

> **Agent** : « J ai constaté que [constat]. Je propose d ajouter à CLAUDE.md :
> [texte]. Puis-je procéder ? »
> **Alain** : « Oui, ajoute-le. »
> **Agent** : « ✅ Entrée ajoutée. »
