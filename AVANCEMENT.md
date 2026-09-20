# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.21.5** (`avastack/__init__.py`),
  branche `master` — jalon 46 CORRIGÉ EN DEV (tout au vert), **VALIDÉ PAR
  ALAIN (20/09/2026, « c'est ok » — test réel en COMPOSITION depuis le PC
  de dev, dossiers pré-remplis d'acquisitions antérieures)**, **COMMITÉ ET
  POUSSÉ (f37c88e + AVANCEMENT bf90913)**, **installateur v2.21.5 REBUILD**
  (`installer/windows/output/avastack-setup.exe`) — copie de l'installateur
  vers le miniPC à faire (optionnel : les tests cadence se font depuis le
  dossier de dev).
- **Dernier jalon (46, 20/09/2026) — PLAFOND DE RAFALE (retour d'Alain :
  « rafale en cours » avec un grand nombre de brutes — ses dossiers
  contiennent déjà les acquisitions d'AUTRES soirées, donc la première
  rafale devait vider TOUT le backlog d'un coup : sablier en continu
  pendant des minutes au démarrage)** :
  - fait : chaque rafale empile AU PLUS `RAFALE_MAX` brutes (10,
    constante App.RAFALE_MAX) ; budget `_rafale_reste` décrémenté à chaque
    brute lue ; à l'épuisement du budget, la fenêtre est (ré)armée MÊME
    s'il reste des brutes détectées — elles attendent les rafales
    suivantes (aucune perte, fichiers sur le disque) ; la rafale se
    termine aussi naturellement quand le backlog est vide (jalon 42) ;
  - l'étiquette de cadence montre alors l'alternance attendue : « rafale
    en cours · N » (bref) → « prochaine rafale dans Xs · N » (compte à
    rebours) → … jusqu'à ce que le backlog soit vidé ;
  - Tests : _test_cadence_jalon42 32/32 (budget épuisé → armement,
    budget rechargé, App neuve pleine) ; jalon19 multi-dossiers.
- **LIMITE QHY (toujours valable)** : après « ■ Arrêter », relancer
  l'appli — le binding qhyccd n'expose AUCUNE libération du SDK (état
  irréinitialisable dans le process) ; le banc QHY l'annonce et conseille
  fermer + relancer.

## ⏭ Validations réelles en attente

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

**Restent en attente :**

2. **Banc Player One (2e setup)** : cf. jalon 28 ci-dessus — détection
   complète + verdict + TEC + bin + ROI + cadence ; copier le banc dans
   le dossier d'installation si testé depuis le miniPC.
3. **Jalon 24** : gradient/débruitage par couche (live + externe) ;
   garde-fous GraXpert jalon 23b en mono ; SCNR doux (jalon 23).
5. Suivi alignement en direct (« Align. : Δ(…) θ(…) » / « Frames non
   alignées »).
9. **Jalon 42-46 (v2.21.1 → v2.21.5) : CLOS ET VALIDÉ PAR ALAIN le
   20/09/2026** — cadence d'empilement en surveillance (dossier ET
   composition, choix commun dans les deux cadres), correctif jalon 43
   (fenêtre armée bloque TOUTE lecture), plafond de rafale RAFALE_MAX = 10
   (dossiers pré-remplis) ; verdict Alain : « c'est ok ». L'étiquette de
   cadence (compte à rebours / rafale en cours) reste un outil de
   diagnostic utile en session.

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
- Leçons PROPOSÉES, EN ATTENTE d'approbation d'Alain (ne pas écrire sans
  accord) : jalon 13 (appariements mutuels + seuil relevé quand la
  décision sert d'ANCRE ; deux normalisations rendent une SSD aveugle —
  partager les bornes) ; jalon 24 (valider les placeholders d'un gabarit
  AVANT la substitution).

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

## 🔚 Clôture de session — 20/09/2026 (v2.21.5, jalon 46 — VALIDÉE PAR ALAIN)

État exact : **v2.21.5 COMMITÉE ET POUSSÉE (f37c88e, AVANCEMENT bf90913),
installateur REBUILD, JALON 46 VALIDÉ PAR ALAIN (« c'est ok » — test réel
en COMPOSITION depuis le PC de dev, dossiers pré-remplis d'acquisitions
antérieures)**.
**VALIDATIONS RÉELLES notées par Alain en clôture** : tests QHY MiniCam8M
(setup 1) FAITS ET CONCLUANTS — connexion, TEC (alim 12 V), filtres,
plages et roue à filtres (sonde ctypes jalon 30, EFFET PHYSIQUE) ;
jalon 32/33 (capacités + UI aux bornes réelles + TEC pilotable) VALIDÉ ET
TESTÉ pour **Player One ET SVBONY** ; jalons 39-41 vérifiés en session
(cases couleur immédiates, curseur/⏳/résultat, cadres STF) ; jalons
42-46 (cadence) validés — « c'est ok ».
Session en huit jalons après la v2.20.7 : jalon 39 (v2.20.8, cases couleur
réactives) ; jalon 40 (v2.20.9, état du calcul : curseur + ⏳ + résultat) ;
jalon 41 (v2.21.0, UI indépendante du moteur) ; jalon 42 (v2.21.1, cadence
d'empilement) ; jalon 43 (v2.21.2, correctif : fenêtre armée bloque TOUTE
lecture) ; jalon 44 (v2.21.3, état de cadence visible) ; jalon 45
(v2.21.4, cadence commune aux deux modes — combobox aussi en composition,
étiquette « — » avant connexion) ; jalon 46 (v2.21.5, PLAFOND DE RAFALE :
RAFALE_MAX = 10 brutes max par rafale — dossiers déjà remplis
d'acquisitions antérieures → la première rafale vidait tout le backlog,
sablier en continu ; le reste attend les rafales suivantes, aucune perte).
Tout au vert en dev : _test_cadence_jalon42 32/32, jalon19 multi-dossiers.

**Prochaine étape (session NEUVE)** : (1) copier l'installateur v2.21.5
vers le miniPC (optionnel pour la cadence, testée depuis le dossier de
dev) ; (2) restent en attente : banc Player One (jalon 28 : détection
complète + verdict + TEC + bin + ROI + cadence), jalon 24 (gradient/
débruitage par couche + garde-fous mono + SCNR doux), suivi alignement en
direct.

Sessions précédentes : v2.21.4 (jalon 45, cadence commune, 265beff) ;
v2.21.3 (jalon 44, 966edae) ; v2.21.2 (jalon 43, d5b799d) ; v2.21.1
(jalon 42, 11f6dfb) ; v2.21.0 (jalon 41, 8ee2d8c) ; v2.20.9 (jalon 40,
45bbfc9) ; v2.20.8 (jalon 39, 097a9c8) ; v2.20.7 (jalon 38, d8d4055) —
détail dans l'historique git et le changelog du source.
