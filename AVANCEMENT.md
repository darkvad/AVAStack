# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version stable de référence : AVAStack v2.23.3** (`avastack/__init__.py`),
  branche `master` — **jalon 55 (gains compo + Linear Fit suivis en temps
  réel, MÊME SANS nouvelle brute) IMPLÉMENTÉ, bancs AU VERT — À TESTER PAR
  ALAIN (M31 RGB : bouger un gain doit changer l'image tout de suite)**.
  Jalon 53 (v2.22.0) validé, commité (225f026), poussé.
- **Jalon 55 (v2.23.3, 21/09/2026) — résumé du dernier jalon** :
  - constat d'Alain : bouger un gain de composition ne changeait RIEN, même
    en forçant VeraLux (target_bg), en mode dossier avec toutes les brutes
    consommées ;
  - BUG jalon 19 (oubli) : gains R/G/B + canal L posés sur le stacker à la
    CRÉATION de la session SEULEMENT — les saisies suivantes n'atteignaient
    jamais stacker.gains (vue « empilement » + sauvegardes figées) ;
  - 2e cause : en mode dossier sans brute à lire, le worker faisait
    `continue` avant TOUT — rendu jamais recalculé ni repoussé ;
  - correctif : réglages resynchronisés à CHAQUE tour de boucle worker ;
    changement de réglage → recalcul + push du rendu (_pousser_rendu,
    dernier dict d'état réutilisé) ; résolution VeraLux forcée
    (notify_new_stack) quand gains/canal L/Linear Fit changent ;
  - conséquence : l'A/B Linear Fit d'Alain sans nouvelle brute était biaisé
    par ce double blocage — à REFAIRE proprement maintenant ;
  - tests : bancs 19 UI + worker, 16, 20, 54 (39 vérifs), VeraLux 2/3,
    jalon 5 — tous au vert.
- **Jalon 54d (v2.23.2) — condensé** : diag d'Alain (_diag_canaux_compo,
  M31 RGB) → couches parfaitement enregistrées (Δ < 0,5 px) — pas de
  désalignement géométrique ; BUG corrigé : le fit s'appliquait AUSSI à
  mean(recadre=False) compo (référence d'alignement non brute, contrat
  jalon 13) → `and recadre` dans mean_avec_canaux + garde-fou au banc.
  Découverte : config.json d'Alain portait `linear_fit: true` (persisté des
  essais v2.23.0) → remis à false. Verdict d'Alain après test : session
  M31 SANS problème d'image. Piste rendu restante : voile bleu = SNR du
  canal B (IMX585 très sensible au rouge : noyau/poussières chauds, bruit
  bleu domine les zones faibles) — remèdes : gains compo (R↓ ou B↑),
  débruitage par rôle (à venir ?), plus de poses en bleu.
- **Jalons 54/54b/54c (v2.23.0/v2.23.1, 21/09/2026) — condensé** (détail
  dans le changelog du source) : Linear Fit R/B→vert (offset = medG − medX,
  gain optionnel borné, stats médiane+MAD quart central) appliqué DANS
  mean() (visu + sauvegardes), solveur live re-calé (vl_compo 5 éléments,
  déballage tolérant), UI case + menu « Méthode » + libellé des gains
  mesurés, config persistée, instantanés `_fit_actif`/`_fit_mode` (jamais
  de Tk dans le worker). Retours d'Alain : gain+offset → « floue comme
  décalé » (gain mesurait B ×1.52) → offset seul par défaut ; mêmes brutes
  qu'avant le jalon → régression confirmée, hyp. optique ÉCARTÉE
  (54c : banc _diag_canaux_compo).
  Tests : `_test_fit_canaux_jalon54` (39 vérifications) ; régressions AU
  VERT : jalons 19/20/21/22/24/13/16/42/17/5/6/47/52/53.
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
14. **Jalon 53 (v2.22.0) — dark/flat unique ou par couche en composition :
    CLOS — VALIDÉ PAR ALAIN (21/09/2026, « C'est Ok »)** — choix de la
    couche AU CLIC sur « Charger un dark/flat… » (boîte modale), DEUX
    ciblages indépendants dark/flat, libellés complets par couche.

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

## 🔚 Clôture de session — 21/09/2026 (v2.23.1, jalons 54/54b/54c — À REPRENDRE À FROID)

État exact : **jalon 54 (Linear Fit) CAUSE UNE RÉGRESSION confirmée par
l'A/B d'Alain (mêmes brutes que depuis le début du projet : correctes
AVANT le jalon 54, dégradées avec) — installateur v2.23.1 rebuildé et
poussé (c174eba, df9f568)**. La case « Recalage colorimétrique (Linear
Fit) » doit rester DÉCOCHÉE en attendant le correctif.
- **jalon 54 — Linear Fit** : R et B recalés sur le vert DANS mean() —
  visu ET sauvegardes ; case décochée par défaut ; solveur live re-calé ;
  config persistée ; réglage conservé au re-stack.
- **jalon 54b** : gain+offset → offset seul par défaut (le gain mesurait
  B ×1.52 et amplifiait halos/bruit bleus) + menu « Méthode ».
- **jalon 54c** : `_diag_canaux_compo.py` (FWHM par couche + translation
  inter-couches, validé sur synthétique). INFO FINALE D'ALAIN : mêmes
  brutes que depuis le début → RÉGRESSION du jalon 54, pas la optique.

**Prochaine étape (jalon 55, v2.23.3)** : Alain re-teste sur la session
M31 RGB (mode dossier, brutes consommées) : bouger un gain R/G/B doit
maintenant changer l'image IMMÉDIATEMENT (resync worker + recalcul du
rendu + forçage VeraLux), de même que la case Linear Fit. L'A/B du fit est
à refaire proprement — l'ancien était biaisé par le double blocage (gains
jamais propagés + rendu jamais recalculé sans nouvelle brute). Si le voile
bleu persiste après équilibrage des gains : piste = débruitage par rôle
(force B plus forte) et/ou MAD par canal dans _diag_canaux_compo. Repli
d'ensemble si nécessaire : revenir avant le jalon 54 (v2.22.0, 225f026).

Sessions précédentes : v2.21.10 (jalons 50-52, banc Touptek + ergonomie
caméra, 7d3034e, validés par Alain) ; v2.21.8 (jalon 49, banc Touptek +
sonde API V2, 8f40606, validé en réel) ; v2.21.7 (jalon 48, 2c44e5c) ;
v2.21.6 (jalon 47, 3cc0522) — détail dans l'historique git et le changelog
du source.
