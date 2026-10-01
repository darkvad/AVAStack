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

## 4. Notes de certification (champ « Notes de certification »)

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

## 5. Images de la fiche Store (à fournir)

- **Captures d'écran (au moins 1)** : 1366×768 minimum, PNG. Montrent de
  préférence la fenêtre en mode « Simulée (démo) » en cours d'empilement.
- **Tuiles** : 1:1 (300×300 minimum, idéal 2160×2160), 16:9 (1920×1080),
  4:3 (1200×900).
- Les **vignettes DU PAQUET** (StoreLogo, Square44/71/150/310, Wide310×150)
  sont déjà générées depuis `assets/avastack.png` — cf. `installer/README.md`.

## 6. Réglages de soumission

| Réglage | Valeur proposée |
| --- | --- |
| Catégorie | Photos et vidéo |
| Prix | Gratuit |
| Marchés | Tous (ou au choix) |
| Langue de la fiche | Français (fr-FR) |
| Classification d'âge | Questionnaire (aucun contenu sensible → « 3 ans et + ») |
| Plateforme | Windows Desktop (x64) |

## 7. Étapes de soumission (Partner Center)

1. **Products** → le produit → **Submissions** → **New submission**.
2. **Packages** : téléverser le `.msix` (celui qui porte l'identité Partner
   Center). Le Store **re-signe** le paquet à la publication : la signature
   locale sert au test, pas à la distribution.
3. **Store listing** : textes du § 3 + images du § 5.
4. **Properties** : catégorie et configuration requise (§ 6).
5. **Age rating** : remplir le questionnaire.
6. **Pricing and availability** : gratuit, marchés.
7. **Submit** — la **certification prend 1 à 3 jours ouvrés** ; toute version
   ultérieure repasse par cette étape (voir la note de cadence dans
   `AVANCEMENT.md`).

### Configuration système requise

- Windows 10 version 1809 (build 17763) ou ultérieure, **64 bits**.
- Pour le pilotage direct d'une caméra astronomique : le **pilote USB du
  constructeur** de cette caméra (installation séparée, hors Store).
