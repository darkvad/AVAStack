# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.21.8** (`avastack/__init__.py`),
  branche `master` — jalon 49 **VALIDÉ PAR ALAIN (20-21/09/2026, test RÉEL
  sur G3M662M au miniPC), COMMITÉ (8f40606) ET POUSSÉ, installateur
  v2.21.8 REBUILD (`installer/windows/output/avastack-setup.exe`, 21/09
  00:42)** — session close : aucun chantier en attente.
- **Dernier jalon (49, v2.21.8, 20-21/09/2026) — banc Touptek + CORRECTION
  DE LA SONDE (API V2)** :
  - CONSTAT FONDATEUR : la sonde `avastack/cameras/touptek.py` (v2.2.0,
    jamais testée sur matériel) était FAUSSE contre la DLL réelle du dépôt
    (ToupCam.dll 59.30239.20251209) : `Toupcam_get_ExpoTimeRange` n'existe
    PAS (AttributeError au chargement ; le vrai nom est
    `Toupcam_get_ExpTimeRange`) ; `Toupcam_Enum` (legacy, obsolète) remplit
    des ToupcamDevice et NON des modèles (charabia lu) ; `Toupcam_Open`
    veut l'ID opaque énuméré, pas le nom du modèle ;
  - sonde RÉÉCRITE sur l'API moderne `Toupcam_EnumV2 / ToupcamDeviceV2`
    (disposition VALIDÉE empiriquement : 201 modèles lisibles dans la DLL),
    conforme à l'entête officiel toupcam.h (miroir INDIGO v60.32499) ;
  - nouveau banc `_diag_camera_touptek.py` (réutilise la sonde) : détection
    V2 + drapeaux, réglages mesurés, verdict, TEC par options (TEC 0x08 /
    TECTARGET 0x0f — PAS de CoolerOn dans la DLL), expo/gain/noir,
    auto-expo on/off, ROI, binning matériel, flux événementiel (callback +
    PullImage), pose (Snap/STILLIMAGE), rapport, `--console` ; embarqué
    dans l'installateur (avastack.iss + LISEZMOI) ;
  - Tests sans matériel : `_test_camera_touptek.py` (fausse DLL) 37/37 OK ;
    régression `_test_capacites` 29/29, `_test_camera_playerone` 29/29.
  - **Tests RÉELS d'Alain (G3M662M mono 16 bits USB3/ST4, miniPC)** :
    détection V2, ouverture, flux, poses expo/gain, bascule auto-expo,
    Snap (malgré 0 résolution pose : livre à la résolution courante) →
    **FONCTIONNE**. Constats intégrés : (a) 2 prototypes ctypes manquants
    (`get_MaxSpeed`, `get_StillResolutionNumber`) → `OverflowError`
    (« int too long » : handle 64 bits passé en int 32) — déclarés (+
    `get_StillResolution`, `get_FinalSize`) ; (b) l'auto-exposition
    « continue » ÉCRASE l'expo posée → bouton « 🅰 Auto-expo on/off » +
    avertissement ; (c) `get_Roi` relu suspecte → croisement `get_Size` +
    `get_FinalSize` journalisé ; compteurs `get_FrameRate` peu fiables →
    fps MESURÉ fait foi ; (d) verdict : bits/pix affichés en entier simple ;
    (e) **ROI** : `put_Roi` ACCEPTE toute taille mais le flux ne livre QUE
    les 2 résolutions du modèle (1920×1080, 960×540) — ROI libre non
    exploitable sur ce capteur (verdict Alain : « pas grave »).
- **LIMITE QHY (toujours valable)** : après « ■ Arrêter », relancer
  l'appli — le binding qhyccd n'expose AUCUNE libération du SDK (état
  irréinitialisable dans le process) ; le banc QHY l'annonce et conseille
  fermer + relancer.

## ✅ Validations réelles — TOUT EST CLOS (verdicts d'Alain, 20/09/2026)

**CLOS le 20/09/2026 (verdicts d'Alain)** :
1. **QHY miniPC (v2.15.0 installée)** : CLOS — tests MiniCam8M FAITS ET
   CONCLUANTS (verdict Alain, 20/09/2026) : connexion, TEC (alim 12 V),
   filtres, plages, roue à filtres.
2b. **Jalon 32 + 33 : CLOS — VALIDÉ ET TESTÉ PAR ALAIN pour Player One ET SVBONY (20/09/2026)** : détection des capacités + UI aux bornes réelles + TEC pilotable (boutons ❄).
2d. ✅ CLOS (jalons 34/35/36/38 — validés en réel par Alain le 20/09/2026).
2c. ✅ CLOS — sonde ctypes testée et concluante sur MiniCam8M (verdict Alain, 20/09/2026).
4. ✅ CLOS — roue à filtres MiniCam8M testée et concluante (verdict Alain, 20/09/2026).
6-8. ✅ **Jalons 39-41 vérifiés en session** (cases couleur réactives ; curseur + ⏳ + ligne de résultat ; cadres « Couleur live » et « État des calculs » en STF).
9. **Jalon 42-46 (v2.21.1 → v2.21.5) : CLOS ET VALIDÉ PAR ALAIN le
   20/09/2026** — cadence d'empilement en surveillance (dossier ET
   composition, choix commun dans les deux cadres), correctif jalon 43
   (fenêtre armée bloque TOUTE lecture), plafond de rafale RAFALE_MAX = 10
   (dossiers pré-remplis) ; verdict Alain : « c'est ok ». L'étiquette de
   cadence (compte à rebours / rafale en cours) reste un outil de
   diagnostic utile en session.
10. **Jalons 47-48 (v2.21.6 → v2.21.7) : CLOS ET VALIDÉS PAR ALAIN le
    20/09/2026** — colonne de réglages épurée (cadres selon la source, un
    seul cadre « Cadence d'empilement » partagé dossier/composition),
    version dans la barre de titre, cadre « Traitement externe (long) » ;
    verdicts : « ça me paraît bon », « c'est ok ».

**RIEN N'EST EN ATTENTE** (Alain, 20/09/2026 : « ces deux points sont
testés et validés depuis longtemps ») :

11. **Jalon 28 — banc Player One : CLOS** — détection complète + verdict +
    TEC + bin + ROI + cadence : testés et validés depuis longtemps (verdict
    d'Alain). Le banc `_diag_camera_playerone.py` reste installé pour tout
    diagnostic matériel futur.
12. **Jalon 24 — gradient/débruitage par couche + garde-fous mono + SCNR
    doux : CLOS** — testé et validé depuis longtemps (verdict d'Alain).
13. **Suivi alignement en direct (« Align. : Δ(…) θ(…) » / « Frames non
    alignées ») : CLOS** — Alain n'en voit pas l'usage : l'alignement,
    l'empilement et le stack fonctionnent bien en session réelle (verdict
    du 20/09/2026). Ce suivi aurait affiché en direct le décalage/rotation
    de chaque brute par rapport à la référence — inutile tant que ça marche.

## Pièges récents (rappels opérationnels)

- Entry/Combobox/`var.get()` Tkinter interdits hors thread principal —
  lire les widgets DANS Tk puis passer les valeurs au worker (appliqué
  dans le banc POA ; bouchons `_Val` dans l'appli).
- Ne JAMAIS mélanger grid et pack dans le même conteneur Tk (attrapé par
  le test UI du banc POA : `_tkinter.TclError` « grid is already
  managing its content windows »).
- Crash OpenCV 5/OpenCL au teardown (`cv2.ocl.setUseOpenCL(False)`) ;
  tests `ui.App` hermétiques (`ui.CONFIG = {}` + sauver_config
  intercepté) ; images de tests bruitées (sinon 0 étoile).
- SDK natif : chargement UNE fois par process ; crash natif non
  rattrapable → tracer chaque étape dans un fichier ; vérifier
  l'identité des fichiers réellement chargés AVANT d'interpréter un
  plantage (les bancs affichent DLL + module + dates).
- Ordre de la chaîne (Alain, 16/09/2026) : recadrage → gradient →
  débruitage → netteté → étirement. Débruitage : code gelé, cases
  décochées (décision du 16/09/2026) — ne pas retoucher sans nouvelle
  demande ; défauts des traitements confirmés (live = désactivé, NLM,
  force 0,5 ; externe = désactivé, GraXpert IA, force 0,5).
- PIÈGE LANCEMENT : `python3` ≠ venv — toujours `python AVAStack.py`.
- **Un callback UI qui change la CLÉ du solveur SANS rafraîchir ne produit
  un effet qu'au prochain `disp.process()`** — c.-à-d. à la frame entrante
  ou au prochain réglage qui rafraîchit (constat réel jalon 39 : les cases
  couleur semblaient inertes). Convention : tout contrôle `_on_*` finit
  par `_refresh_preview()` ; les `_sync_*_vue` (appelés par _tick toutes
  les 30 ms) ne touchent qu'à l'ÉTAT, JAMAIS au rendu.
- **Installateur à REBUILDER avant tout test réel dès que la passe de code
  touche PLUS d'un ou deux fichiers** (`powershell -NoProfile
  -ExecutionPolicy Bypass -File installer\windows\build_avastack.ps1`) —
  à la charge de l'agent, sans qu'Alain ait à le demander (consigne du
  20/09/2026, écrite dans CLAUDE.md).

## Statuts CLAUDE.md

- Leçons ÉCRITES le 19/09/2026 (accord d'Alain) : introspection des
  exports de la DLL sous le binding ; convention roue `48+n` vs `'0'`
  tranchée par l'effet physique ; SDK natif (init unique, état non
  libérable, crash → trace + sous-processus) ; identité des fichiers
  chargés avant toute interprétation ; réglage relu ≠ réglage appliqué
  (seul l'effet physique prouve).
- Leçons ÉCRITES le 20/09/2026 (accord d'Alain, « écris les 2 ») :
  jalon 13 (appariements mutuels + seuil relevé quand la décision sert
  d'ANCRE ; deux normalisations distinctes rendent une SSD aveugle —
  partager les bornes) ; jalon 24 (valider les placeholders d'un gabarit
  AVANT la substitution). Plus AUCUNE leçon en attente.

## Setup d'Alain

- **Setup 1 (miniPC)** : QHY MiniCam8M (mono refroidie, roue intégrée,
  alim. 12 V requise) ; N.I.N.A. → dossiers
  `TargetSchedulerSequence/<cible>/<expo>/LIGHT` — un dossier peut
  MÉLANGER plusieurs nuits (la 1re frame par mtime n'est pas forcément de
  la nuit courante).
- **Setup 2** : C8 défourché + réducteur 0,63 → 1280 mm ; Player One
  Uranus-C Pro (couleur, IMX585, 3856×2180, RGGB, gain unitaire 210,
  TEC) sur monture DIY **Open Astro Mount** ; guidage SVBONY SV305C sur
  lunette 60/240. Constat 17/09/2026 à 1280 mm : étoiles « en plusieurs
  points puis en trainées » → origine du jalon 13 (alignement robuste).
  Banc POA : `_diag_camera_playerone.py` (jalon 28).

## 🔚 Clôture de session — 21/09/2026 (v2.21.8, jalon 49 — VALIDÉE PAR ALAIN)

État exact : **v2.21.8 COMMITÉE (8f40606) ET POUSSÉE, installateur REBUILD**
(`installer/windows/output/avastack-setup.exe`, 21/09 00:42, avec le banc
Touptek + la sonde corrigée + ToupCam.dll). Verdict Alain sur test RÉEL
G3M662M au miniPC : **VALIDÉ** (détection, ouverture, flux, expo/gain,
auto-expo, snap, identité ; ROI libre muette sur ce capteur = constat
consigné, « pas grave »).

**Prochaine étape (session NEUVE)** : AUCUN chantier en attente — la
prochaine étape sera une NOUVELLE demande d'Alain (fonction ou ergonomie).
Copier l'installateur v2.21.8 vers le miniPC remplacera la copie manuelle
des 2 fichiers faite pour le test.

Sessions précédentes : v2.21.7 (jalon 48, 2c44e5c) ; v2.21.6 (jalon 47,
3cc0522) ; v2.21.5 (jalon 46, plafond de rafale, f37c88e) — détail dans
l'historique git et le changelog du source.
