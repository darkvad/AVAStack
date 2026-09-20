# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.21.7** (`avastack/__init__.py`),
  branche `master` — jalon 48 **VALIDÉ PAR ALAIN (20/09/2026, « c'est ok »),
  COMMITÉ ET POUSSÉ (2c44e5c + AVANCEMENT), installateur v2.21.7 REBUILD
  (`installer/windows/output/avastack-setup.exe`)** — session close :
  TOUT est validé pour le moment, aucun test réel en attente.
- **Dernier jalon (48, 20/09/2026) — petites ergonomies (demandes d'Alain)** :
  - le numéro de version s'affiche dans la **barre de titre**
    (« AVAStack v2.21.7 — live stacking (empilement temps réel) ») ;
  - le cadre « Traitement externe » est étiqueté **« (long) »** au lieu de
    « (instantané) » — GraXpert IA/BXT durent plusieurs minutes ; le mot
    « instantané » reste valable en INTERNE (copie de l'empilement traitée
    à part, l'accumulé reste linéaire) ;
  - Tests : _test_ui_visibilite_jalon47 étendu (titre = version) ; suite UI
    au vert.
- **Jalon 47 (v2.21.6) — VALIDÉ PAR ALAIN (« ça me paraît bon »), COMMITÉ ET
  POUSSÉ (3cc0522)** : colonne de réglages épurée — cadres visibles selon la
  source (caméra → contrôles caméra seuls ; dossier → dossier + cadence ;
  composition → composition + cadence) ; réglage de rafale sorti des deux
  cadres : un seul cadre « Cadence d'empilement » partagé ; on cache sans
  détruire (valeurs conservées), ancre stable « Calibration ».
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
10. **Jalons 47-48 (v2.21.6 → v2.21.7) : CLOS ET VALIDÉS PAR ALAIN le
    20/09/2026** — colonne de réglages épurée (cadres selon la source, un
    seul cadre « Cadence d'empilement » partagé dossier/composition),
    version dans la barre de titre, cadre « Traitement externe (long) » ;
    verdicts : « ça me paraît bon », « c'est ok ».

**Restent en attente :**

2. **Banc Player One (2e setup)** : cf. jalon 28 ci-dessus — détection
   complète + verdict + TEC + bin + ROI + cadence ; copier le banc dans
   le dossier d'installation si testé depuis le miniPC.
3. **Jalon 24** : gradient/débruitage par couche (live + externe) ;
   garde-fous GraXpert jalon 23b en mono ; SCNR doux (jalon 23).
5. Suivi alignement en direct (« Align. : Δ(…) θ(…) » / « Frames non
   alignées »).

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

## 🔚 Clôture de session — 20/09/2026 (v2.21.7, jalon 48 — VALIDÉE PAR ALAIN)

État exact : **v2.21.7 COMMITÉE ET POUSSÉE (2c44e5c + AVANCEMENT), 
installateur REBUILD** ; jalon 47 (v2.21.6, ergonomie colonne) committé et
poussé (3cc0522), jalon 46 (v2.21.5, plafond de rafale) validé plus tôt
(f37c88e). **TOUT EST VALIDÉ PAR ALAIN POUR LE MOMENT** (« ça me paraît
bon », « c'est ok ») — aucun test réel en attente.

Session en deux jalons après la v2.21.5 :
- jalon 47 (v2.21.6) — ERGONOMIE : colonne de réglages épurée, les cadres
  suivent la SOURCE choisie (caméra → contrôles caméra seuls ; dossier →
  dossier + cadence ; composition → composition + cadence) ; le réglage de
  rafale « Empiler les brutes » sort des deux cadres où il était dupliqué
  (jalons 42/45) → un seul cadre « Cadence d'empilement » partagé ; on
  cache SANS détruire (valeurs conservées), ancre stable « Calibration »
  (l'ordre des cadres ne bouge jamais) ; nouveau _test_ui_visibilite_jalon47,
  section [7] de _test_cadence_jalon42 réécrite (cadence unique) ;
- jalon 48 (v2.21.7) — version dans la BARRE DE TITRE (« AVAStack
  v2.21.7 — live stacking… », f-string sur AVASTACK_VERSION, source
  unique) ; cadre « Traitement externe (long) » au lieu de
  « (instantané) » — l'instantané reste le mot INTERNE (copie de
  l'empilement traitée à part, l'accumulé reste linéaire).
Tout au vert : _test_ui_visibilite_jalon47, _test_cadence_jalon42, ui
jalon 5, config jalon 6 (régression large faite au jalon 47 : jalons
5/6/19/32/34/35/36/38/39/40/41).

**Prochaine étape (session NEUVE)** : (1) copier l'installateur v2.21.7
vers le miniPC si besoin ; (2) restent en attente : banc Player One
(jalon 28 : détection complète + verdict + TEC + bin + ROI + cadence),
jalon 24 (gradient/débruitage par couche + garde-fous mono + SCNR doux),
suivi alignement en direct.

Sessions précédentes : v2.21.6 (jalon 47, 3cc0522) ; v2.21.5 (jalon 46,
plafond de rafale, f37c88e) ; v2.21.4 (jalon 45, cadence commune,
265beff) ; v2.21.3 (jalon 44, 966edae) ; v2.21.2 (jalon 43, d5b799d) ;
v2.21.1 (jalon 42, 11f6dfb) ; v2.21.0 (jalon 41, 8ee2d8c) ; v2.20.9
(jalon 40, 45bbfc9) ; v2.20.8 (jalon 39, 097a9c8) ; v2.20.7 (jalon 38,
d8d4055) — détail dans l'historique git et le changelog du source.
