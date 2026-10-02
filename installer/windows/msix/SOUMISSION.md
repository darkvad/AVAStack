# Soumission au Microsoft Store — AVAStack (MSIX)

Note d'atelier : comment soumettre le paquet MSIX déjà construit par
`build_msix.py` (build) puis `signer_msix.ps1` (signature).

> **Aucune donnée de compte n'est écrite dans ce fichier** (identité Partner
> Center, GUID, PFN…) : ces valeurs sont dans **Partner Center**, page
> *Product identity* du produit. Le dépôt reste sans donnée personnelle.

## 1. Relier le paquet à l'identité du produit

Page **Product identity** (Partner Center) → trois valeurs, à reporter telles
quelles :

| Partner Center | Paramètre du packer |
| --- | --- |
| **Package/Identity/Name** | `--nom` |
| **Package/Identity/Publisher** (`CN=…`) | `--publisher` |
| **Package/Properties/PublisherDisplayName** | `--publisher-display` |

La **version** n'est pas à saisir : elle vient de `AVASTACK_VERSION` (+ « .0 »).

```powershell
# 1) build avec l'identité réelle
python installer\windows\msix\build_msix.py `
    --nom "<Package/Identity/Name>" `
    --publisher "<Package/Identity/Publisher>" `
    --publisher-display "<PublisherDisplayName>" `
    --affiche "AVAStack"

# 2) signature (le Publisher ci-dessous DOIT être le même que --publisher)
powershell -NoProfile -ExecutionPolicy Bypass -File installer\windows\msix\signer_msix.ps1 `
    -Msix "installer\windows\output\avastack-<version>-windows.msix" `
    -Publisher "<Package/Identity/Publisher>"
```

Le `Publisher` du manifeste et le **sujet du certificat** ne font qu'un : c'est
la même chaîne. Elle doit être **identique à l'octet** côté Partner Center, sinon
l'upload est refusé.

## 2. Essai local (facultatif, recommandé)

```powershell
# a) PowerShell ADMINISTRATEUR : approuver le certificat (magasin LOCAL MACHINE)
Import-Certificate -FilePath "installer\windows\output\avastack-<version>-windows.cer" `
    -CertStoreLocation Cert:\LocalMachine\TrustedPeople
# b) PowerShell normal : installer
Add-AppxPackage -Path "installer\windows\output\avastack-<version>-windows.msix"
# désinstaller :  Get-AppxPackage *AVAStack* | Remove-AppxPackage
```

## 3. Textes de la fiche Store (fr-FR)

> **À COLLER EN TEXTE BRUT.** Ce document est en Markdown pour *notre*
> lisibilité : **Partner Center n'interprète AUCUN balisage**. Ne collez donc
> jamais les `**`, les `#`, les backticks ou les `>` : ils s'afficheraient tels
> quels (ex. `**MATÉRIEL ET PILOTES**` deviendrait un titre couvert d'astérisques).
> Microsoft interdit en outre explicitement **HTML, extraits de code et adresses
> URL** dans la description (les liens vont dans *Privacy policy URL* /
> *Website*). Collez le texte **rendu**, en gardant les retours à la ligne ; les
> puces sont de **vrais caractères « • »**, pas des tirets Markdown.
>
> **Longueurs MESURÉES** (texte brut, balises retirées) : description
> **1489 caractères** (maximum **10 000**) ; description courte **297 caractères**
> (maximum **1000**, conseillé **< 270**) ; notes de certification
> **1034 caractères** (champ libre, texte brut, aucune mise en forme).
> Si vous préférez passer sous les 270 conseillés, une variante mesurée à
> **263 caractères** est fournie en fin de section.

### Description (champ « Description »)

> Le début de la description ANNONCE la dépendance pilotes : c'est l'exigence de
> la politique **10.2.4** (Software Dependencies).

AVAStack — empilement d'images astronomiques en temps réel.

**MATÉRIEL ET PILOTES (à lire avant l'installation).** AVAStack fonctionne SANS
AUCUN pilote tiers dans trois modes : « Simulée (démo) » (ciel synthétique),
« Dossier surveillé » (les brutes écrites par votre logiciel d'acquisition) et
webcams USB (pilote standard fourni par Windows). Le PILOTAGE DIRECT d'une
caméra astronomique — ZWO ASI, QHYCCD, Player One, ToupTek/Altair, SVBONY —
exige en revanche le PILOTE USB DU CONSTRUCTEUR, qui n'est PAS fourni par
Microsoft : installez-le depuis le site du constructeur de votre caméra.
AVAStack s'appuie sur les SDK officiels publiés par ces constructeurs.

**Ce que fait AVAStack**
- Empile vos brutes PENDANT l'acquisition : surveillez le dossier où votre
  logiciel (N.I.N.A., APT, SGP, ASI Air…) écrit ses images, ou pilotez
  directement une caméra compatible.
- Calibration (darks, flats), alignement automatique des poses, empilement avec
  rejet des traînées (satellites, avions, météores).
- Étirement des niveaux en temps réel (automatique ou manuel) et histogramme.
- Composition multi-filtres (LRGB, HOO, SHO…).
- Sauvegarde FITS / TIFF / PNG des résultats.
- Outils avancés facultatifs : astrométrie (catalogue Gaia), photométrie SPCC,
  et traitement par des logiciels externes que vous possédez déjà (GraXpert,
  BlurXTerminator).

**Pour commencer sans matériel** : choisissez la source « Simulée (démo) » puis
cliquez sur « ▶ Démarrer » — l'empilement temps réel démarre immédiatement.

### Description courte (champ « Short description »)

Empilez vos images astronomiques en temps réel, pendant l'acquisition :
calibration, alignement, rejet des traînées, étirement et histogramme.
Fonctionne sans pilote tiers en mode démo, dossier surveillé ou webcam ; le
pilotage direct d'une caméra astronomique nécessite le pilote du constructeur.

### Variante de description courte (< 270 caractères) — facultative

> À utiliser **à la place** du texte ci-dessus si vous voulez rester sous le
> seuil conseillé de 270 caractères (au-delà, certaines vues n'affichent que le
> début, avec un lien « voir plus »). Mesurée : **263 caractères**.

Empilez vos images astronomiques en temps réel, pendant l'acquisition :
calibration, alignement, rejet des traînées, étirement et histogramme. Sans
pilote tiers : démo, dossier surveillé ou webcam ; le pilotage direct d'une
caméra exige le pilote du constructeur.

## 4. Notes de certification (champ « Notes de certification »)

> Encadré par des triples apostrophes inverses (`` ``` ``) **pour ce document
> seulement** : copier le texte SEUL, sans ces lignes. Champ libre (texte brut,
> aucune mise en forme) ; mesuré : **1034 caractères**.

```
DEMANDE D'EXCEPTION — POLITIQUE 10.2.4 (Software Dependencies)

AVAStack est un outil d'empilement d'images astronomiques. Pour sa fonction de
PILOTAGE DIRECT de caméras astronomiques, elle dépend de PILOTES USB fournis
par les constructeurs (ZWO, QHYCCD, Player One, ToupTek/Altair, SVBONY). Ces
pilotes ne sont PAS fournis par Microsoft et NE SONT PAS inclus dans le paquet :
l'utilisateur les installe lui-même depuis le site du constructeur.

SANS AUCUN pilote tiers, l'application reste pleinement fonctionnelle :
 1) mode « Simulée (démo) » — ciel synthétique, aucune caméra requise ;
 2) mode « Dossier surveillé » — lit les images écrites par un logiciel
    d'acquisition (N.I.N.A., APT, SGP, ASI Air…) ;
 3) webcams USB — pilote UVC fourni par Windows.

Procédure de test SANS MATÉRIEL : choisir la source « Simulée (démo) », puis
cliquer « ▶ Démarrer » ; l'empilement temps réel se lance immédiatement.

Nous demandons l'exception prévue par la politique 10.2.4 pour cette dépendance
documentée à des pilotes non-Microsoft.
```

### 4 bis. Capacités restreintes — justification `runFullTrust` (OBLIGATOIRE)

Le manifeste déclare **`rescap:Capability Name="runFullTrust"`** (cf.
`AppxManifest.xml.template`) : Partner Center **détecte** cette capacité et
exige, dans *Submission options* → **Restricted capabilities**, de dire
« why your app needs to declare the capability and how it is used ». **Sans ce
texte, la certification échoue** (et la revue peut allonger le délai de
quelques jours). Texte à coller — texte brut, à copier SANS les ``` :

```
AVAStack est une application de bureau classique (interface Python/Tkinter
empaquetée en MSIX, EntryPoint=Windows.FullTrustApplication). runFullTrust est
le mécanisme DOCUMENTÉ par Microsoft pour empaqueter une telle application :
sans elle, l'application ne peut pas fonctionner, et il n'existe pas
d'équivalent en bac à sable.

Ce que la capacité permet, et pourquoi :
- lire et écrire les dossiers CHOISIS PAR L'UTILISATEUR où un logiciel
  d'acquisition (N.I.N.A., APT, SGP, ASI Air…) écrit ses images FITS, sur
  n'importe quel disque ou partage réseau (mode « Dossier surveillé ») ;
- charger via ctypes les bibliothèques SDK des constructeurs de caméras (ZWO,
  QHYCCD, Player One, ToupTek/Altair, SVBONY) installées hors Store, pour
  piloter la caméra en USB ;
- écrire sa configuration et son journal dans %APPDATA% (chemins RÉELS, non
  virtualisés) ;
- lancer des outils externes que l'utilisateur possède déjà (GraXpert,
  BlurXTerminator, ASTAP, Siril) avec leurs propres lignes de commande.

L'application ne demande AUCUN privilège administrateur, n'installe ni pilote
ni service, ne s'exécute pas en arrière-plan et ne collecte aucune donnée
personnelle. C'est l'usage standard et attendu de runFullTrust pour une
application de traitement d'images de bureau.
```

## 5. Images de la fiche Store (à fournir)

**Un outil les fabrique** : `installer/windows/msix/images_fiche.py` — il part
d'UNE capture d'écran réelle de la fenêtre et écrit, dans un dossier de sortie :

```powershell
python installer\windows\msix\images_fiche.py `
    --capture "C:\...\capture.png" `
    --masquer "x,y,l,h" [--masquer ...]   # zone PERSONNELLE à neutraliser
# contrôle d'un dossier déjà écrit :  --verifier installer\windows\output\fiche
```

Il écrit la **capture telle quelle** (c'est elle qu'on téléverse) **et** les
**trois tuiles** aux tailles ci-dessous (fenêtre ENTIÈRE sur fond flou ;
`--recadrer` remplit « cover » sans bandes). Répartition exacte : la **capture**
va dans *Screenshots*, la tuile **1:1** dans *Store logos* et la **16:9** dans
*Windows 10/11 and Xbox image (Super hero art)* ; la **4:3** n'a pas d'usage
dans Partner Center (tableau ci-après).

- **Captures d'écran (au moins 1)** : **1366×768 minimum**, PNG (4K accepté,
  jusqu'à 10 captures). Une capture RÉELLE de la fenêtre EN TRAIN D'EMPILER
  convient. **Aucun élément personnel** : ni chemin local lisible, ni adresse
  réseau, ni notification Windows. Ces éléments peuvent être **floutés dans la
  source** et/ou **neutralisés** par `--masquer x,y,l,hauteur` (le masquage
  s'applique aussi à la capture téléversée).
- **Tuiles** : 1:1 (**2160×2160** → *Store logos 1:1 box art*, **obligatoire**) ;
  16:9 (**1920×1080** → *Super hero art*, **sans titre ni texte**, exigence
  Microsoft) ; 4:3 (**1200×900** → **sans usage** dans Partner Center, cf.
  tableau ci-après).
- Les **vignettes DU PAQUET** (StoreLogo, Square44/71/150/310, Wide310×150)
  sont déjà générées depuis `assets/avastack.png` — cf. `installer/README.md`.
  Ce sont DEUX choses distinctes (les vignettes du manifeste d'un côté, les
  images de la fiche de l'autre).

**Où va CHAQUE fichier dans Partner Center** (Store listing) :

| Champ Partner Center | Fichier à téléverser | Taille (et exigence Microsoft) |
| --- | --- | --- |
| **Screenshots** (Desktop) | `avastack-ecran-1.png` | 1916×1018 — **≥1366×768 exigé**, PNG ≤ 50 Mo, 10 max |
| **Store logos → 1:1 box art** (OBLIGATOIRE) | `avastack-tuile-1x1-2160.png` | 2160×2160 (1080² ou 2160²) |
| **Windows 10/11 and Xbox image → 16:9 Super hero art** | `avastack-tuile-16x9-1920x1080.png` | 1920×1080 (1920×1080 ou 3840×2160) |
| *(aucun)* | `avastack-tuile-4x3-1200x900.png` | **à NE PAS téléverser** (voir ci-dessous) |

> ⚠ **La tuile 4:3 (1200×900) n'a AUCUN usage dans Partner Center** : une capture
> Desktop doit faire **au moins 1366×768** (1200 < 1366) et les deux autres
> emplacements ont leurs tailles propres. Elle reste un visuel de communication
> (site, README, GitHub) — pas pour la fiche.
>
> ⚠ Le **16:9 (hero art)** ne doit porter **ni titre ni texte** (exigence
> Microsoft) : nos tuiles n'en ajoutent aucun. Garde les éléments importants
> dans les **deux tiers supérieurs** (une bande peut recouvrir le tiers bas).
> Chaque capture accepte une **légende de 200 caractères max** (facultative).

**Jeu réellement produit (02/10/2026)** : `installer/windows/output/fiche/`
(4 fichiers ; `--verifier` → CONFORME) à partir d'une capture RÉELLE de
l'empilement **SHO NGC 2237** d'Alain, ses chemins **floutés dans la source**
(nom d'utilisateur et adresse réseau illisibles). Seul l'élément NON lié à
l'application restait à neutraliser : la **notification Windows**
(`--masquer 1428,860,488,158`). Le masquage s'applique AVANT l'écriture : la
**capture téléversée** le porte donc aussi (aucune retouche à refaire à la
main). La voie « Simulée (démo) » n'est PAS utilisable ici : la caméra simulée
(`avastack/cameras/simulated.py`) ne produit qu'un ciel synthétique, pas
l'objet voulu.

## 6. Réglages de soumission — champ par champ

Les libellés sont ceux de Partner Center (interface anglaise entre parenthèses).
Quand c'est marqué « défaut », **ne touche à rien**.

### Pricing and availability (Prix et disponibilité)

| Champ | Valeur à mettre |
| --- | --- |
| Markets (Marchés) | **Tous** (défaut) — tu peux retirer des marchés non francophones |
| Audience | **Public** (défaut) |
| Discoverability | **Make this product available and discoverable in the Microsoft Store** (défaut) |
| Schedule | **Release as soon as possible** ; Stop acquisition : **never** (défauts) |
| Base price | **Free** (gratuit) |
| Free trial / Sale pricing / Organizational licensing | laisser vide (défauts) |

### Properties (Propriétés)

| Champ | Valeur à mettre |
| --- | --- |
| Category | la catégorie **photo/vidéo** — le tableau Microsoft l'écrit « **Photo + video** » (l'interface peut afficher « Photo & video » / « Photo et vidéo ») |
| Subcategory | **(aucune)** — facultative |
| Secondary category | **(aucune)** |
| Privacy policy | l'URL de `PRIVACY.md` : `https://github.com/darkvad/AVAStack/blob/master/PRIVACY.md` (**§ 6 bis**) |
| Website | `https://github.com/darkvad/AVAStack` (facultatif, recommandé) |
| Support contact info | page *Issues* du dépôt, ou ton adresse de support (facultatif hors Xbox) |
| Game settings | n'apparaît PAS (catégorie ≠ Jeux) |
| Display mode | **tout décoché** |
| Product declarations | garder les **cases par défaut** (installation sur un autre disque ; sauvegarde OneDrive) ; **ne cocher AUCUNE autre** : pas d'achats hors Store, pas d'accessibilité, pas de stylet/encre, pas d'IA générative |
| System requirements | voir **§ 6 ter** |

### Age ratings (Classification d'âge)

- « Do you already have an IARC rating ID? » → **No** (sauf si tu en as déjà un).
- **1re question** : catégorie décrivant le mieux l'application → choisis
  l'option « utilitaire / productivité / référence » la plus proche :
  **ce n'est PAS un jeu** (ne pas choisir Games).
- **Toutes les questions de contenu → « Non »** : violence, sang, peur, sexe et
  nudité, drogues/alcool/tabac, jeux d'argent, langage grossier, **contenu créé
  par les utilisateurs**, **réseaux sociaux**, **partage de position ou de
  données personnelles**, achats intégrés.
- **Save and generate** → attendu : **3+** (les classifications ESRB/PEGI/USK…
  sont attribuées d'office par marché). Celle-ci vaut pour toutes les mises à
  jour suivantes.

### Packages (Paquets)

| Champ | Valeur à mettre |
| --- | --- |
| Package | `installer\windows\output\avastack-2.50.0-windows.msix` — celui à **identité Partner Center** (§ 1). Attendre l'état **Validated** |
| Device family availability | ne rien changer (Windows Desktop x64) |

### Store listing (langue : Français (France))

| Champ | Valeur à mettre |
| --- | --- |
| Description | **§ 3** — texte brut |
| Short description | **§ 3** (ou la variante < 270) |
| Product features | facultatif (20 max) : recopie les puces « Ce que fait AVAStack » |
| Screenshots | **§ 5** (≥ 1 ; 4 à 8 conseillées) |
| Store logos (1:1 box art) | **§ 5** — **obligatoire** |
| Windows 10/11 and Xbox image (16:9) | **§ 5** (recommandé ; sans aucun texte) |
| Search terms | facultatif : astronomie, astrophotographie, empilement, live stacking, FITS, caméra, ciel profond |
| Copyright and trademark info | ex. « © 2026 AVAStack » |
| Developed by | `AVAStack` |

### Submission options (Options de soumission)

| Champ | Valeur à mettre |
| --- | --- |
| Publishing hold options | **Publish this submission as soon as it passes certification** (défaut) |
| Notes for certification | **§ 4** — texte brut |
| **Restricted capabilities** | **§ 4 bis — OBLIGATOIRE** (`runFullTrust`) |
| Submission notification audience | défaut |
| Additional testing information | si la section apparaît : recopie **§ 4** |

### 6 bis. Politique de confidentialité (FAIT — 02/10/2026)

Partner Center demande si l'application « accède à, collecte ou transmet des
informations personnelles ». **Réponse : NON** — AVAStack n'envoie rien vers un
serveur : aucune télémétrie, aucun compte, aucun analytics. Le SEUL accès réseau
du code est le **téléchargement de catalogues publics** (Zenodo, GitLab) depuis
`avastack/catalogues/telechargeur.py`, à la demande de l'utilisateur.

> ⚠ Microsoft peut **exiger une URL** d'après les capacités déclarées (ici
> `runFullTrust`) : « Failure to include a required privacy policy may result in
> certification failure. »
>
> **DÉCISION (02/10/2026) : on FOURNIT l'URL.** La politique est désormais
> **publiée dans le dépôt** : **`PRIVACY.md`** (racine ; français + résumé
> anglais ; **aucune donnée personnelle** — le contact est la page *Issues*).
> **À coller dans le champ *Privacy policy* :**
> `https://github.com/darkvad/AVAStack/blob/master/PRIVACY.md`
>
> Son texte a été écrit d'après le **code VÉRIFIÉ** (aucun `requests` ni
> `socket` dans `avastack/` ; seuls `zenodo.org` et `gitlab.com`, en LECTURE) et
> n'est donc pas recopié ici : la source de vérité est ce fichier.

### 6 ter. Configuration système requise (Properties → System requirements)

Chaque ligne fait **200 caractères maximum**, jusqu'à 11 lignes par catégorie.
Ces exigences s'affichent **en liste à puces** : ne pas mettre ses propres puces.

| Catégorie | Lignes proposées |
| --- | --- |
| Minimum hardware | `Processeur 64 bits (x64)` ; `8 Go de RAM` ; `Windows 10 version 1809 (build 17763) ou ultérieure` |
| Recommended hardware | `16 Go de RAM` ; `SSD (les brutes FITS sont volumineuses)` |
| Additional system requirements | `Le pilotage direct d'une caméra astronomique nécessite le pilote USB du constructeur, installé séparément (hors Store).` |

## 7. Étapes de soumission (clic par clic)

**Avant de commencer** (tout doit être prêt) : le MSIX à identité réelle est
construit ET signé (§ 1) ; les images sont dans `installer\windows\output\fiche\`
(§ 5, `--verifier` → CONFORME) ; les textes sont prêts en TEXTE BRUT (§ 3, § 4,
§ 4 bis) ; la politique de confidentialité est publiée (**`PRIVACY.md`**, § 6 bis).

1. Va sur **https://partner.microsoft.com/dashboard** → **Apps and games**
   (Produits) → clique sur **AVAStack**.
2. **Start submission** → une soumission en **brouillon** s'ouvre : les sections
   sont listées à gauche (l'ordre de remplissage est libre).
3. **Pricing and availability** → valeurs de **§ 6** (défauts + Gratuit) →
   **Save**.
4. **Properties** → **§ 6** (catégorie, déclarations, § 6 ter) et **§ 6 bis**
   (politique de confidentialité) → **Save**.
5. **Age ratings** → questionnaire de **§ 6** → **Save and generate**.
   Attendu : **3+**.
6. **Packages** → **Browse your files** → choisis
   `installer\windows\output\avastack-2.50.0-windows.msix` → attends
   **Validated** / « Packages validated ». Le Store **re-signera** le paquet à
   la publication (ta signature locale sert au test, cf. § 2).
7. **Store listing** → langue **Français (France)** → colle la **Description**,
   la **Description courte** (texte brut, § 3), puis téléverse les images de
   **§ 5** (capture dans *Screenshots*, tuile 1:1 dans *Store logos*, tuile 16:9
   dans *Windows 10/11 and Xbox image*) → **Save**.
8. **Submission options** → **§ 6**, et surtout la section
   **Restricted capabilities** : colle la justification de **§ 4 bis**
   (`runFullTrust`). **Sans elle, la certification échoue.**
9. **Submit for certification** (bouton en haut de la page du produit).
10. **Attente : 1 à 3 jours ouvrés** (statut « In certification » sur la page du
    produit). La revue de `runFullTrust` peut ajouter quelques jours.
11. **Si c'est validé** : le Store re-signe le paquet et publie selon le réglage
    « Publishing hold options » (ici : dès la fin de la certification).
    **Si c'est refusé** : lis le **rapport de certification**, corrige, puis
    **New submission**.

### Pièges connus (rencontrés par d'autres développeurs)

- Une section peut rester affichée **« Incomplete »** alors que tout est rempli :
  rouvre-la, clique **Save**, recharge la page. Ce n'est **pas** bloquant tant
  que **Submit** passe (ce n'est pas causé par `runFullTrust`).
- **Restricted capabilities** : la justification est lue par un humain → reste
  factuel et précis (le texte de § 4 bis l'est).
- **Description** : ni URL, ni HTML, ni balisage Markdown (§ 3), sinon rejet.
- **Images** : une capture Desktop doit faire **≥ 1366×768** (la tuile 4:3 de
  1200×900 est donc inutilisable, § 5) ; le **Store logo 1:1 est obligatoire**.
- Toute **nouvelle version** repasse par une soumission complète (cadence :
  cf. `AVANCEMENT.md`).

## 8. Après la soumission (quoi surveiller)

**SOUMISSION FAITE le 02/10/2026** (AVAStack **v2.50.0**, paquet MSIX).

1. **Statut** : sur la page du produit, la soumission passe à **« In
   certification »**, puis à **« Published »** (ou « Certification failed »).
   Compter **1 à 3 jours ouvrés** ; la revue de `runFullTrust` (§ 4 bis) peut
   ajouter quelques jours.
2. **Pendant l'attente** : rien à faire. Éviter de lancer une seconde
   soumission sur le même produit tant que celle-ci est en cours.
3. **Si la certification ÉCHOUE** : ouvrir le **rapport de certification**
   (lien sur la page de la soumission), corriger exactement ce qui est
   reproché, puis **New submission**. Distinguer deux cas :
   - le reproche porte sur la **fiche** (texte, image, réglage) → corriger et
     resoumettre, **le paquet ne change pas** ;
   - il porte sur le **CODE** → alors **bumper `AVASTACK_VERSION`** (nouvelle
     version, ex. v2.51.0), reconstruire (et re-signer) le MSIX (§ 1) et
     téléverser celui-là : le numéro de version doit être **supérieur** à celui
     publié, sinon l'upload est refusé.
4. **Une fois PUBLIÉE** :
   - le **Store re-signe** le paquet : la signature locale ne sert qu'aux essais
     (§ 2) — rien à faire ;
   - la fiche peut mettre **quelques heures** à se propager dans le Store ;
   - faire le **dernier test qui n'existe que par cette voie** : installer
     **depuis le Store** sur un poste (menu Démarrer) et vérifier que
     l'application s'ouvre et empile ;
   - le lien public de la fiche est celui affiché sur la page produit.
5. **Mises à jour** : chaque version repasse par une **soumission complète**
   (mêmes sections). La **classification d'âge** et les **capacités déjà
   approuvées** ne se redemandent pas.
6. **Mettre à jour la mémoire après publication** : `AVANCEMENT.md` (version
   publiée + date) — et corriger toute affirmation d'état devenue fausse dans
   la documentation publique (règle du projet : un état publié ne ment jamais).
