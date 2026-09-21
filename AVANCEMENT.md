# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.21.10** (`avastack/__init__.py`),
  branche `master` — **jalons 51 + 52 VALIDÉS PAR ALAIN (21/09/2026,
  « tout est validé »), COMMITÉS (7d3034e) ET POUSSÉS, installateur
  v2.21.10 REBUILD, SESSION CLOSE**.
- **Jalon 52 (v2.21.10, 21/09/2026) — ERGONOMIE DU CADRE « CAMÉRA » —
  VALIDÉ PAR ALAIN, clos** :
  - DEMANDE D'ALAIN : le choix de source (caméra/dossier/…) était SOUS les
    contrôles caméra au lancement ; choisir « Dossier » (contrôles cachés)
    le faisait passer EN HAUT (« c'est mieux ») et il y RESTAIT au retour
    caméra — sa place dépendait de l'histoire de la session. CORRIGÉ :
    choix + Démarrer/Arrêter packés AVANT frm_ctrl_cam → en haut DÈS LE
    DÉBUT, ordre stable au va-et-vient dossier/caméra ;
  - DEMANDE D'ALAIN : « ⏏ Déconnecter » (side="right" de la ligne
    Détecter) était poussé hors de la colonne par un long libellé de
    caméra détectée (il fallait élargir la colonne pour l'atteindre).
    CORRIGÉ : SA PROPRE ligne sous « 🔎 Détecter », toujours visible ;
  - `_test_ergonomie_jalon52` : ordre de packing RÉEL (pack_slaves),
    va-et-vient dossier/caméra, ligne dédiée — vert ; régressions UI
    (jalons 47/32/31/34/6) et batteries caméras : au vert.
- **Confirmé PAR ALAIN (21/09/2026) — jalon 52 clos** : choix de source en
  haut du cadre « Caméra » dès le lancement ; bouton « ⏏ Déconnecter »
  visible en toutes circonstances (même avec un long libellé de caméra
  détectée).
- **Jalon 51 (v2.21.10, 21/09/2026) — NOIR MESURÉ + OFFSET LU + TEC
  TOUPTEK — VALIDÉ PAR ALAIN (21/09/2026), clos** :
  - CONSTAT RÉEL DU BANC (Alain, 21/09/2026, G3M662M) : la caméra REFUSE
    7936 (E_INVALIDARG) alors qu'elle ACCEPTE 31/30/0 et REFUSE 32 → sa
    plage de noir réelle est **0 → 31** ; la table de toupcam.h n'est donc
    qu'un PLAFOND : la borne max est désormais MESURÉE par dichotomie
    posé/relu (`TouptekCamera._mesurer_noir`, valeur d'origine restaurée) ;
  - OFFSET LU PLUTÔT QU'IMPOSÉ (demande d'Alain, valable pour TOUTES les
    caméras) : la sonde lit la valeur courante du contrôle et l'appli
    l'ADOPTe — Touptek (option 0x15), QHY (GetQHYCCDParam), ZWO
    (ASIGetControlValue), SVBONY (SVBGetControlValue), Player One
    (POAGetConfig) ; marque muette → comportement d'origine ;
  - MISE À JOUR IMMÉDIATE (déjà en place, vérifié) : tout changement de
    curseur est poussé au thread de travail instantanément
    (`_push_settings` → `pending_settings`/`pending_offset` consommés à
    chaque tick) pour TOUTES les marques — pas de redémarrage de session ;
  - TEC TOUPTEK PILOTABLE (demande d'Alain, sans matériel de test possible) :
    la DLL n'a PAS de CoolerOn → pilotage par OPTIONS (TECTARGET 0x0f
    consigne en 0,1 °C, TEC 0x08, plage via TECTARGET_RANGE 0x6d champs
    signés), température `get_Temperature` ; boutons ❄/étiquette branchés
    (consigne_refroidissement/lire_refroidissement/arrêter_refroidissement) ;
    un modèle sans TEC répond E_NOTIMPL → boutons grisés (aucun faux bouton) ;
  - banc : la dichotomie est exécutée VIA LA FONCTION DE L'APPLI (une seule
    source de vérité) ; lecture TEC/consigne/température ajoutée ;
  - tests sans matériel : `_test_camera_touptek` **58/58** (faux SDK qui
    refuse > 31), `_test_capacites_ui_jalon32` (offset ADOPTÉ dans la
    fenêtre), `_test_capacites` 29/29, `_test_qhy_camera` 33,
    `_test_camera_playerone` 29/29, TEC jalons 33/38, UI jalons 31/34/35/6/47,
    `_test_connexion_svbony_jalon36` : tous au vert.
- **TEC Touptek (jalon 51) : codé, SANS test matériel possible** (pas de
  caméra refroidie Touptek au miniPC) — sur une caméra refroidie un jour :
  boutons ❄ + étiquette « Capteur : x °C · TEC : — » (pas de PWM chez
  Touptek) ; SUR UN MODÈLE SANS TEC : boutons ❄ restent grisés.
- **Jalon 50 (v2.21.9, 21/09/2026) — VALIDÉ PAR ALAIN (test réel) :
  capacités Touptek EN DYNAMIQUE** — `detecter_capacites()` = relevé direct
  sur la caméra ouverte (expo µs, gain %, mono/bits/pixel), gain en %
  (unité SDK), auto-exposition coupée par `apply_settings`,
  `definir_offset()` implémenté (option BLACKLEVEL 0x15) → les curseurs
  Expo/Gain/Offset passent aux bornes réelles (détail dans le changelog
  v2.21.9 de `avastack/__init__.py`).
- **Jalon 49 (v2.21.8, 20-21/09/2026) — VALIDÉ PAR ALAIN, clos** : banc
  Touptek + correction de la sonde (API V2 EnumV2/DeviceV2) ; détection,
  ouverture, flux, poses expo/gain, auto-expo, snap, identité OK au miniPC ;
  ROI libre muette sur ce capteur (constat consigné, « pas grave »).
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

## 🔚 Clôture de session — 21/09/2026 (v2.21.10, jalons 50-51 — À TESTER PAR ALAIN)

État exact : **v2.21.10 codée et testée SANS matériel** (suite verte), PAS
encore commitée ni poussée à l'écriture de ces lignes. Objets cumulés :
- jalon 50 : les curseurs Expo/Gain/Offset de l'APPLI passent enfin aux
  bornes RÉELLES pour Touptek (100 µs → 1000 s, gain 100 % → 15000 %),
  le gain est en POUR CENT (unité SDK), l'auto-exposition est coupée quand
  l'appli pose ses réglages et le curseur offset AGIT (option BLACKLEVEL) ;
- jalon 51 : le NOIR est MESURÉ (constat banc : plage réelle 0 → 31, la
  caméra refuse 7936 et 32, accepte 31/30/0 — la table de toupcam.h ne sert
  que de PLAFOND de recherche) ; l'OFFSET est LU sur la caméra et ADOPTÉ à
  la connexion (demande d'Alain, règle valable pour TOUTES les marques) ;
  le TEC Touptek est PILOTABLE (options TECTARGET 0x0f / TEC 0x08, plage
  via TECTARGET_RANGE 0x6d, température get_Temperature — boutons ❄ et
  étiquette branchés ; PWM inconnu chez Touptek → « TEC : — »).

**Prochaine étape** : test RÉEL d'Alain au miniPC (G3M662M) —
1) banc `_diag_camera_touptek.py` → ligne « noir bornes » (dichotomie
exécutée par la fonction de l'appli) et verdict « plage CONSTATÉE 0 → 31 »
attendu ;
2) appli → l'offset affiché DOIT être celui de la caméra (1 sur G3M662M),
curseurs Gain (100 – 15000) / Offset (0 – 31) / expo 100 µs → 1000 s,
une pose change bien l'image (AE coupée), l'offset agit ;
3) boutons ❄ : restent GRISÉS sur G3M662M (pas de TEC) — à essayer si une
caméra refroidie Touptek est branchée (étiquette « Capteur : x °C ·
TEC : — », Touptek n'expose pas de puissance de refroidissement).

Sessions précédentes : v2.21.8 (jalon 49, banc Touptek + sonde API V2,
8f40606, validé en réel) ; v2.21.7 (jalon 48, 2c44e5c) ; v2.21.6 (jalon 47,
3cc0522) ; v2.21.5 (jalon 46, plafond de rafale, f37c88e) — détail dans
l'historique git et le changelog du source.
