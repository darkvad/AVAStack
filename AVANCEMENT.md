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
- **Jalon 53 (v2.22.0, 21/09/2026) — DARK/FLAT UNIQUE OU PAR COUCHE EN MODE
  COMPOSITION — codé, suite verte SANS matériel, À TESTER/VALIDER PAR ALAIN** :
  - DEMANDE D'ALAIN : en empilement multibande (source « Composition
    multi-dossiers »), pouvoir choisir un dark UNIQUE ou PAR COUCHE, et le
    même choix pour les flats INDÉPENDAMMENT de celui des darks ;
  - RETOURS D'ALAIN PENDANT LE TEST (pris en compte) : (a) la couche se
    choisit AU CLIC sur « Charger un dark… » / « Charger un flat… » — boîte
    modale « Ce dark s'applique à : Unique (toutes les couches) / la couche
    « Ha »… » (rôles ACTIFS du cadre Composition), PLUS de menus déroulants
    de ciblage préalable ; hors composition, aucun dialogue ; (b) les
    libellés montrent TOUT : « Dark unique : nom (H×W) » PUIS « Dark Ha :
    nom (H×W) » pour CHAQUE couche active (« Dark O3 : — » si le master de
    cette couche manque) ;
  - justification : les couches ont souvent des POSES différentes (le dark
    dépend de la pose) et le vignettage/poussière dépend du FILTRE (le
    flat aussi) — d'où un ciblage séparé dark/flat ;
  - `Calibrator` : `darks`/`flats` = dictionnaires {rôle: image} (+ `*_sources`
    = fichier d'origine de chaque master, pour l'affichage) ;
    `load_dark(path, role=None)` / `load_flat(path, role=None)` /
    `apply(img, role=…)` — le master DU RÔLE prime, repli sur l'UNIQUE
    pour un rôle sans master dédié (mono inchangé) ; le worker passe le
    rôle de la frame (`calib.apply(frame, role=role)`) ;
  - GARDE-FOUS : annulation de la boîte = aucun chargement ; master de
    forme incompatible ignoré (règle historique) ; « Effacer calibration »
    vide tout (uniques ET par rôle) ; masters par rôle CONSERVÉS aux
    allers-retours de source et réaffichés au retour en composition ;
  - tests : `_test_calib_compo_jalon53` (Calibrator seul : repli,
    indépendance dark/flat, flat non constant à gradient ; UI réelle : la
    boîte modale pilotée par after — réponse Ha / unique / O3 / annulation,
    libellés complets, allers-retours de source ; worker réel
    multi-dossiers : le dark DÉDIÉ de chaque couche est appliqué — fonds
    mesurés 0.130/0.090, jamais le dark du voisin) ; régressions au vert
    (jalons 19/20/21/24/42/47/52, config 6, UI 5, cadence 42,
    capacités UI 32, jalon 17).
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

## 🔚 Clôture de session — 21/09/2026 (v2.22.0, jalon 53 — À TESTER PAR ALAIN)

État exact : **v2.22.0 codée et testée SANS matériel** (jalon 53, retours
d'Alain en cours de test pris en compte, suite verte), PAS encore commitée
ni poussée à l'écriture de ces lignes ; installateur rebuild (v2.22.0).
- **jalon 53 — calibration multibande** : en mode « Composition
  multi-dossiers », un clic sur « Charger un dark… » / « Charger un
  flat… » ouvre une boîte « Ce dark (resp. flat) s'applique à : » —
  Unique (toutes les couches) ou une des couches actives de la
  composition — DEUX choix INDÉPENDANTS. Un rôle sans master dédié
  retombe sur le dark/flat UNIQUE (mono inchangé). Les libellés
  détaillent TOUT : « Dark unique : … » puis « Dark Ha : … » par couche
  (« Dark O3 : — » si le master manque). Cas d'usage : un dark par filtre
  (poses différentes par couche) avec un flat unique — ou l'inverse — ou
  les deux par filtre. PREMIER TEST D'ALAIN : « cela semble bon ».

**Prochaine étape** : test d'Alain en composition (HOO p. ex.) —
1) cadre Calibration : cliquer « Charger un dark… » → la boîte propose
   « Unique (toutes les couches) » + les couches actives ; choisir « Ha » ;
2) les libellés affichent TOUT : « Dark unique : — » / « Dark Ha : nom
   (H×W) » / « Dark O3 : — » ; pareil pour les flats (indépendance) ;
   « Effacer calibration » remet tout à zéro ;
3) session réelle multi-dossiers : chaque couche doit être corrigée par SON
   master (vérifier l'absence d'ampli-cœur résiduel différent d'une couche
   à l'autre) ;
4) si OK : commit + push v2.22.0 (jalon 53).

Sessions précédentes : v2.21.10 (jalons 50-52, banc Touptek + ergonomie
caméra, 7d3034e, validés par Alain) ; v2.21.8 (jalon 49, banc Touptek +
sonde API V2, 8f40606, validé en réel) ; v2.21.7 (jalon 48, 2c44e5c) ;
v2.21.6 (jalon 47, 3cc0522) — détail dans l'historique git et le changelog
du source.
