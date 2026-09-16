# AVANCEMENT.md — mémoire de travail à court terme

(Ce fichier complète CLAUDE.md : il suit l'état courant du développement et
la tâche en cours. CLAUDE.md reste la mémoire de long terme, inchangée.)

---

## État actuel (base stable)

- **Version : AVAStack v2.3.4** (`avastack/__init__.py`,
  `AVASTACK_VERSION = "2.3.4"`), branche `master`. **v2.3.4 = travail du
  16/09/2026 : tests automatiques 14/14 au vert, TESTÉ EN RÉEL par Alain et
  COMMITÉ ET POUSSÉ** (débruitage : verdict « on garde comme ça », cf. bullet
  ci-dessous + « Tâche en cours »).
  Bases VALIDÉES par Alain : v2.3.3 (recadrage auto à
  l'intersection) et v2.3.2 (sauvegarde linéaire sans frames), test réel du
  16/09/2026 (« C'est maintenant OK ») ; jalon 6 validé le 15/09/2026 ;
  jalon 5 validé le 14/09/2026.
- **v2.3.2 — CORRECTION (constat Alain, 16/09/2026) : « 💾 Enregistrer
  l'empilement (linéaire)… » ne faisait RIEN** (aucun fichier, aucun
  message, ni fin ni erreur) dès que plus aucune brute n'arrivait
  (dossier surveillé terminé). Cause : la demande (`save_request`) était
  consommée par le thread d'acquisition UNIQUEMENT après l'empilement
  d'une nouvelle frame — sans frames, le bloc n'était jamais atteint, en
  silence ; les deux autres boutons de sauvegarde passent par des threads
  dédiés consommés AVANT la lecture (d'où « tel que vu » et « résultat
  traité » fonctionnaient). Fix : la demande linéaire est consommée au
  même endroit (avant `camera.read()`), sur l'empilement courant.
  Test `_test_save_lineaire_fix.py` (8 vérifications, headless) ; jalons
  1-4 + 6 relancés : TOUS PASSENT. NB : l'échec de `_test_ui_jalon5.py`
  (« état initial moteur STF ») signalé ici était PRÉEXISTANT et a été
  CORRIGÉ le 16/09/2026 (v2.3.4) : le test neutralise maintenant la
  persistance (`ui.CONFIG = {}` + `sauver_config` intercepté) au lieu de
  lire le vrai `config.json` d'Alain → il repasse au VERT.
- **✅ DÉBRUITAGE : REMIS le 16/09/2026 (v2.3.4, demande d'Alain), TESTÉ EN
  RÉEL ET CONSERVÉ TEL QUEL.** Historique : les jalons 7/8/9 (GraXpert IA
  puis ondelettes/NLM locaux, en manuel puis en live) avaient été
  ABANDONNÉS par Alain le 15/09/2026 (fond « léopard ») et leur code sorti
  du dépôt (conservé dans `stash@{0}`). Alain a demandé le 16/09 leur
  RÉINTRODUCTION, réorganisée selon la nature de chaque méthode :
  **GraXpert IA → TRAITEMENT EXTERNE uniquement** (minutes par image, jamais
  dans la chaîne live) et **ondelettes à trous + Non-local means → LIVE
  (cadre VeraLux) ET TRAITEMENT EXTERNE** (en mémoire, sans commande
  externe). **Verdict du test réel d'Alain (16/09/2026) : « pas top » dès
  que le retrait de gradient est actif, « mieux mais pas parfait » sans —
  décision : on garde le code, il ne cochera simplement pas les cases.** Le
  fond « léopard » reste donc NON résolu, et un constat nouveau s'ajoute :
  le débruitage se DÉGRADE après un retrait de gradient (cf. section
  « Débruitage » ci-dessous + Pièges de CLAUDE.md).
- **✅ JALON 6 VALIDÉ PAR ALAIN le 15/09/2026** (test réel, vraies
  brutes) : rejet des satellites (Winsorized), persistance config.json,
  boutons « - »/« + » des curseurs — tout est bon.
- **Jalon 6 — rejet des satellites (demande d'Alain, 15/09/2026) : ✅
  CODÉ, commité puis VALIDÉ PAR ALAIN le 15/09/2026 (commit « Jalon 6 (1/3) »).** `avastack/processing/stacking.py` :
  `LiveStacker` a 2 méthodes de rejet — `method="kappa"` (comportement
  historique STRICTEMENT inchangé, régression testée bit-à-bit) et
  `method="winsorized"` : adaptation live du Winsorized Sigma Clipping
  de PixInsight — chaque frame est comparée à la MÉDIANE et au MAD
  (σ_robuste = 1,4826×MAD) d'une fenêtre glissante des dernières frames
  alignées (`window`, défaut 8 ; RAM ≈ window × frame en float32).
  REJEU DU WARMUP : quand la fenêtre se remplit pour la 1re fois (elle
  contient alors TOUTES les frames accumulées), l'accumulation est
  RECONSTRUITE avec les poids robustes — une trace passée pendant le
  warmup est effacée, pas seulement diluée (le kappa-sigma cumulé gonfle
  σ pour toujours via sumsq et masque ensuite les traces faibles aux
  mêmes pixels). `set_rejet(method=, window=)` change à chaud SANS
  perdre l'accumulation (seule la fenêtre est vidée). Traitement par
  bandes de lignes (`_CHUNK_PX`) pour borner les temporaires mémoire.
  `app.py` : cadre Empilement — combobox « Méthode de rejet »
  (« kappa-sigma (rapide) » / « Winsorized (satellites) ») + combobox
  « Fenêtre de référence (frames) » (4/6/8/12/16, grisée en mode kappa) ;
  appliqué à la création du stacker et à chaud (`_on_rejet`).
  Test : `_test_rejet_satellites_jalon6.py` (21 vérifications, headless)
  — scénario poison : résidu kappa ~10,0e-3 vs winsorized ~0,01e-3 ;
  étoiles/champ intacts ; RGB OK ; chunks OK ; jalons 1-5 relancés :
  TOUS PASSENT. (La persistance de ces réglages a été faite ensuite —
  cf. bullet suivant.)
- **Jalon 6 — persistance config.json (15/09/2026) : ✅ CODÉ, commité
  puis VALIDÉ PAR ALAIN le 15/09/2026.**
  `avastack/ui/app.py` : `_sauver_config_app` écrit désormais `kappa`,
  `rejet_methode`, `rejet_fenetre`, `moteur`, `vl_mode_res`, `vl_target`,
  `vl_logd`, `vl_profil`, `vl_graxpert` — booléen stocké EXPLICITEMENT
  (True comme False : une case décochée n'hérite pas d'un True ancien).
  `_restaurer_config` les relit au démarrage : kappa mappé sur les
  étiquettes Off/2σ-5σ ; méthode + fenêtre de rejet (état grisé
  synchronisé) ; réglages VeraLux restaurés AVANT le moteur (la bascule
  affiche le cadre avec les bonnes valeurs) ; moteur « VeraLux »
  SEULEMENT si le moteur tiers est disponible (aucun popup au démarrage) ;
  GX live SEULEMENT si la commande est utilisable (aucun popup) ;
  restauration TOLÉRANTE — kappa hors {2,3,4,5} → 3σ, fenêtre hors liste
  → 8, cible hors [0.10, 0.45] / logD hors [0, 7] / profil inconnu /
  mode inconnu → défauts (config corrompue = jamais de crash).
  Test `_test_config_jalon6.py` (19 vérifications, fenêtre Tkinter
  réelle ; `sauver_config` intercepté + `CONFIG` simulé : le VRAI
  config.json n'est jamais touché par les tests) : sauvegarde des 9
  clés, restauration complète (variables UI ET état du
  DisplayProcessor), réglages invalides → défauts sans crash.
  Jalons 1-5 relancés : TOUS PASSENT.
- **Jalon 6 — boutons « - »/« + » sur les curseurs (demande d'Alain,
  15/09/2026, avant son test réel) : ✅ CODÉ, commité (v2.3.1) puis
  VALIDÉ PAR ALAIN le 15/09/2026.**
  `_add_slider` (app.py) ajoute deux petits boutons autour de CHAQUE
  curseur (exposition, gain, black/white, gamma, saturation, fond visée,
  logD… — tous les sliders passent par cette fabrique) : clic = ±1 pas
  (res) recalé sur la grille du curseur (une valeur glissée à la main est
  réalignée) ; clic MAINTENU = répétition (400 ms puis 80 ms), annulée au
  relâchement ou en sortant du bouton ; clamp aux bornes frm/to ; le
  callback du curseur est appelé exactement comme lors d'un déplacement
  (aucun autre comportement changé). Test `_test_sliders_jalon6.py`
  (9 vérifications, fenêtre réelle). Jalons 1-5 + config relancés :
  TOUS PASSENT.
- **Stashes `stash@{0}`/`stash@{1}` DROPPÉS le 15/09/2026** (jalon 6
  validé ; la fonctionnalité VeraLux avait été réécrite proprement aux
  jalons 1-3, leur contenu n'était qu'une « inspiration » — rien à
  récupérer).
- **Jalon 5 — « 💾 Enregistrer tel que vu (étiré) » : ✅ VALIDÉ PAR ALAIN
  et commité (v2.2.7, 14/09/2026).** Détails du code :
  `display.py` : `rendu_pleine_resolution(img, reglages=None)` — rendu
  « tel que vu » d'une image linéaire PLEINE résolution, fonction PURE
  (aucun état partagé : pas de stats EMA, pas de solveur, jamais
  black/white/gamma) ; STF/manuel recalculé sur l'image complète, VeraLux
  avec le DERNIER logD résolu (rendu identique à l'écran, sans
  re-résolution ; replis target_bg si aucun logD connu / STF si moteur
  absent) ; gamma/saturation via `_gamma_saturation` et stats via
  `_calc_stats` (refactors neutres de `process()`/`_auto_params`).
  `app.py` : bouton « 💾 Enregistrer tel que vu (étiré)… » dans le cadre
  Sortie ; `_save_asseen()` capture (chemin, vue, réglages) côté UI ;
  `_worker` lance `_save_asseen_thread` (pattern `_run_external`,
  acquisition continue) : vue « pile » → stack pleine résolution →
  GraXpert live si activé (échec = sauvegarde abandonnée, message clair) ;
  vue « traitée » → `proc_full` (a déjà subi GraXpert/BXT) ; puis rendu +
  `save_image` ; résultat consommé par `_tick` (bouton grisé +
  messagebox). Libellés des boutons linéaires clarifiés (« (linéaire) »).
  Corrections sur retours d'Alain (test visuel) : (1) GraXpert live
  limité à la vue « empilement » (`_sync_vl_graxpert_vue`, synchro dans
  `_tick`/`_on_view`/`_on_vl_graxpert` + message explicite) — en vue
  « traitée » l'image a déjà subi le traitement externe, le relancer
  faisait un DEUXIÈME traitement ; (2) combobox « Profil capteur » dans
  le cadre VeraLux (avancé du jalon 6 demandé par Alain — 6 profils, fait
  partie de la clé → re-résolution au changement) ; (3) réglages STF
  regroupés dans `frm_stf` MASQUÉ en mode VeraLux (aucun effet dans ce
  mode), remis au retour STF ; gamma/saturation dans `frm_communs`
  (toujours visibles). Précision d'Alain : il avait utilisé « Enregistrer
  le résultat traité… » (linéaire, voulu) d'où sa question — libellés
  clarifiés, comportements inchangés.
  Tests : `_test_save_asseen_jalon5.py` (16 vérifications, headless),
  `_test_ui_jalon5.py` (15 vérifications, fenêtre Tkinter réelle) ;
  jalons 1-4 relancés : TOUS LES TESTS PASSENT.
- Arbre de travail **propre** au 15/09/2026 : jalon 6 validé et commité,
  rien en suspens ; les stashes de la tentative abandonnée ont été
  droppés (la fonctionnalité a été réécrite proprement aux jalons 1-3).
  (État du **16/09/2026** — v2.3.4 débruitage remise, NON commitée : voir
  la section « ⏭ TÂCHE EN COURS » en tête de ce fichier.)
- **Dépôt distant créé (15/09/2026)** : `origin` =
  https://github.com/darkvad/AVAStack.git — `master` poussé et suivi
  (`git push` seul suffit désormais). Aucun fichier sensible suivi
  (pas de config.json, ni venv, ni build).
- Ce qui fonctionne (validé en réel) :
  - Pipeline complet : acquisition (sources simulées / dossier surveillé /
    OpenCV / ZWO ASI / QHYCCD / Player One / Touptek-Altair / SVBONY) →
    calibration dark/flat → alignement ORB + RANSAC (repli corrélation de
    phase) → empilement kappa-sigma → affichage temps réel → sauvegarde
    FITS/TIFF/PNG.
  - Étirement d'affichage actuel (`avastack/processing/display.py`,
    classe `DisplayProcessor`) : mode AUTO « STF façon PixInsight »
    (med − k·σ → p99.9, MTF calant le fond sur 0.25, stats lissées EMA
    anti-pompage) et mode MANUEL (black/white point), gamma et saturation
    communs. UI dans `avastack/ui/app.py` (case « Auto-stretch STF »).
  - Étirement VeraLux (moteur tiers, opt-in, validé en réel sur source
    simulée) : modes « fond cible (auto) » — le moteur résout le logD à
    CHAQUE nouvel empilement (thread dédié, dernier job gagnant, fallback
    STF) avec curseur « Luminosité du fond visée » — et « logD forcé »
    (curseur + bouton 🔒 de verrouillage du logD résolu).
  - Traitement externe optionnel sur INSTANTANÉ (GraXpert gradient,
    débruitage — GraXpert IA OU ondelettes/NLM locaux —, BlurXTerminator)
    dans un thread séparé ; l'empilement accumulé reste linéaire et intact.
  - Débruitage LIVE opt-in (v2.3.4) : ondelettes à trous / Non-local means
    AVANT l'étirement, dans le thread solveur (cadre VeraLux).
  - Sauvegarde « 💾 Enregistrer tel que vu (étiré)… » (jalon 5, v2.2.7) :
    vue courante rendue comme à l'écran en pleine résolution (chaîne
    complète : GraXpert live si activé → débruitage live si activé →
    étirement STF/manuel ou VeraLux avec le dernier logD résolu →
    gamma/saturation) ; les deux autres boutons d'enregistrement restent
    LINÉAIRES (voulu).
  - Installateur Windows Inno Setup (v2.1.0).

## ⏭ TÂCHE EN COURS (reprise de session, 16/09/2026)

**Dernière demande d'Alain (16/09/2026)** : « remettre les fonctions de
denoise, graxpert dans traitement externe, et les 2 autres [ondelettes à
trous, Non-local means] qui peuvent s'exécuter en live — pour ondelette et
NLM dans live ET dans external bien sûr. » → **FAIT, TESTÉ EN RÉEL PAR ALAIN
ET COMMITÉ (v2.3.4)** (détails : changelog de `avastack/__init__.py` +
section « Débruitage » ci-dessous).

**CE QUI EST À REPRENDRE À LA PROCHAINE SESSION = LA NETTETÉ LIVE
(Richardson-Lucy)** — tout est déjà décidé et documenté dans la section
« Netteté live (page à venir) » ci-dessous : méthode arrêtée avec Alain le
16/09/2026 (**RL retenu ; Unsharp Mask et Wiener ÉCARTÉS**, mesure à
l'appui), chiffres du banc d'essai, contraintes techniques DÉJÀ vérifiées
(résolution de travail 1600 px, coût, PSF), et le plan d'attaque en 3 étapes
qui commence par le **détecteur d'étoiles + affichage du seeing live**.

État exact à la reprise :
- **v2.3.4 : commitée et poussée le 16/09/2026** (bases validées : v2.3.3
  et v2.3.2 ; cf. « État actuel » en tête de fichier). **tests : LES 14
  fichiers `_test_*.py` PASSENT** (code de sortie 0), lancés UN PAR UN avec
  le venv : `C:/Astro/astrolivestack/venv/Scripts/python.exe _test_xxx.py`
- **débruitage : PLUS RIEN EN ATTENTE.** Test réel d'Alain (16/09/2026) :
  « pas top » après retrait de gradient, « mieux mais pas parfait » sans —
  décision : **on garde le code tel quel, cases décochées** (aucun
  ajustement de défaut demandé). La prochaine session n'a donc PAS à
  retoucher le débruitage.
- **ORDRE DE LA CHAÎNE, précisé par Alain le 16/09/2026 (ne pas l'oublier)** :
  **recadrage → gradient → débruitage → netteté → étirement.** Les deux
  premières étapes ne sont pas des options : le recadrage (automatique à
  l'intersection, v2.3.3) et le retrait de gradient sont ce qui permet de
  travailler sur les images les plus propres possible — et le gradient
  comme la PSF (netteté) se dégradent sur des bords d'écart non recadrés.

Notes de mise en œuvre (pour ne pas les redécouvrir) :
- **live** : chaîne du thread solveur = **recadrage auto (`stacker.mean()`,
  v2.3.3) → GraXpert live → débruitage → [netteté RL, à venir] → étirement
  VeraLux** ; cache par (empreinte image ENTRANTE, méthode,
  force) ; échec = repli sans débruitage + message (`vl_error`), jamais
  figé ; vue « traitée » = débruitage live DÉSACTIVÉ (pas de 2e
  traitement) ; sauvegarde « tel que vu » reproduit le débruitage en
  pleine résolution.
- **externe** : `ext_job` est un 8-tuple (méthode + force transportées) ;
  les algorithmes locaux ne consomment AUCUNE commande (le champ de
  commande GraXpert dédié n'est utilisé QUE par la méthode GraXpert).
- **défauts livrés (v2.3.4), CONFIRMÉS par le test réel du 16/09/2026** :
  live = désactivé, méthode « Non-local means », force 0,5 ; externe =
  désactivé, méthode « GraXpert (IA, lent) », force 0,5. Alain garde le code
  tel quel (« je n'aurai qu'à ne pas cocher les cases ») → **NE PAS retoucher
  ces valeurs sans nouvelle demande** ; si le sujet est rouvert un jour, le
  vrai chantier est l'interaction **gradient × débruitage** (cf. section
  « Débruitage »), pas le réglage de la force.
- `_test_ui_jalon5.py` : l'échec « état initial moteur STF » (préexistant,
  cf. v2.3.2) est corrigé DANS le test (CONFIG simulé vide + `sauver_config`
  intercepté) — plus aucune dépendance au vrai `config.json` du poste.
- `.gitignore` : il avait été COMMITÉ CORROMPU (une ligne de sortie d'outil
  + BOM en tête du fichier) ; nettoyé le 16/09/2026 et complété
  (`_gx_jalon4_compteur.txt`, artefact du test jalon 4).

## ✅ RÉSOLU : retrait de gradient GraXpert — bords clairs + signal affaibli (signalement d'Alain, 15/09 → 16/09/2026)

Symptôme (M33) : avec retrait GraXpert (live VeraLux ET traitement externe —
même commande `-correction Subtraction -smoothing 0.5`), **bande claire
périphérique** (« coussin ») + spirales affaiblies ; sans retrait, fond
uniforme. Investigations successives : hypothèses « modèle IA sur image
quasi plate » (pile dark sans flat ; astrographe APS-C + IMX585 = pas de
vignettage), mesure objective (`_diag_gx_bords.py`, racine), comparaison
Siril — toutes PARTIELLEMENT fausses, la vraie cause était ailleurs.

**CAUSE RÉELLE trouvée par Alain (16/09, test Siril très instructif)** :
les **bords d'écart de recouvrement de l'empilement** (3 côtés sombres
décalés où les frames ne couvrent pas tout le champ). Ces marches de fond
parasitent le modèle de fond de GraXpert, qui crée le coussin EXACTEMENT
sur ces bords-là. En recadrant l'image AVANT le retrait (Soustraction,
smoothing 0.5 INCHANGÉS), GraXpert retrouve un comportement correct ; et
Siril n'a jamais montré le coussin parce qu'il recadre déjà à l'intersection
lors du stacking. À NOTER : le test `-correction Division` PLAANTE dans
cette version de GraXpert → piste abandonnée, ne pas y revenir.

FIX v2.3.3 — recadrage AUTOMATIQUE à l'intersection GÉOMÉTRIQUE RÉELLE des
frames alignées (équivalent live du `-framing=min` de Siril ; leçon du
pipeline astromatix d'Alain : méthode exacte, jamais d'heuristique de
pixels) : `LiveStacker.note_alignement(M)` maintient l'intersection
incrémentalement (clipping de polygones Sutherland–Hodgman, marge 3 px —
l'interpolation « creuse » au ras des bords ; garde-fous : M aberrante
ignorée, jamais d'agrandissement, min 16 px par côté) et `mean()` renvoie
l'accumulation recadrée → affichage, GX live, les 3 sauvegardes et le
traitement externe héritent du recadrage d'un coup. Statut live :
« recadrée H×W ». Test `_test_crop_intersection.py` (16 vérifications,
headless, piège des axes de canaux traité) ; jalons 1-6 relancés : TOUS
PASSENT (l'échec `_test_ui_jalon5.py` est préexistant — persistance jalon 6,
voir bullet v2.3.2).

Piège à retenir (consigné dans CLAUDE.md § Pièges, accord d'Alain) :
**GX background-extraction sur un stack à bords d'écart de recouvrement =
coussin clair sur ces bords** — recadrer à l'intersection AVANT tout retrait
de gradient ; `-correction Division` plante (ne pas y revenir).

**VALIDATION FINALE (Alain, 16/09/2026) : « C'est maintenant OK »** — le
recadrage automatique v2.3.3 fonctionne en réel : les bords d'écart sortent
de l'empilement, GraXpert (live et externe) se comporte correctement avec
ses réglages par défaut (Subtraction, smoothing 0.5).

Constat Bonus conservé (Alain, 15/09) : « le débruitage non-local means
semble fonctionner presque correctement sur la version SANS gradient » —
son process tournait alors encore avec le code NLM des jalons 8/9 chargé
en mémoire. **Cette piste est désormais ACTIVE : le débruitage NLM est
REMIS dans le dépôt le 16/09/2026 (v2.3.4, live ET traitement externe)** —
et l'observation d'Alain (NLM meilleur sur l'image SANS gradient) est une
piste de réglage à retester : dans la chaîne live le débruitage s'applique
APRÈS le GraXpert live éventuel, dans la chaîne externe APRÈS l'étape de
gradient — cf. section suivante.



## Débruitage : abandonné le 15/09/2026, REMIS le 16/09/2026 (v2.3.4)

**ÉTAT : code REMIS, tests automatiques 14/14 au vert, TESTÉ EN RÉEL par
Alain le 16/09/2026 → CONSERVÉ EN L'ÉTAT (cases laissées DÉCOCHÉES).**
Verdict réel d'Alain : « le débruitage n'est pas top si on garde l'extraction
de gradient ; si je la décoche, il est mieux mais pas parfait. On va garder
comme ça pour l'instant, je n'aurais qu'à ne pas cocher les cases. »
→ **CONSTAT CAPITAL : le débruitage se DÉGRADE quand il s'applique APRÈS le
retrait de gradient** (l'ordre appliqué, pourtant le « bon » en théorie :
gradient → débruitage) ; sur l'empilement brut il est un peu meilleur, sans
être convaincant pour autant. Le fond « léopard » n'est donc PAS résolu —
c'est le même problème qu'au 15/09, vu sur de vraies images. Les défauts
livrés (désactivé par défaut) sont exactement ce qu'il faut : **aucun
changement de code demandé à ce stade** ; Alain décoche simplement les cases.
Hypothèse (NON vérifiée, à investiguer si le sujet est rouvert) : GraXpert
lisse/restructure le fond avant le débruiteur, si bien que le bruit résiduel
n'a plus les mêmes statistiques et que le seuil k-sigma / le h NLM
AUTO-ADAPTÉS (estimés par MAD sur l'image entrante) se calibrent de travers.
Réorganisation demandée par Alain le 16/09/2026 — chaque
méthode est désormais placée selon sa nature :
- **GraXpert IA (débruitage)** → **traitement EXTERNE uniquement** (case
  « 2. Débruitage » + méthode « GraXpert (IA, lent) ») : plusieurs MINUTES
  par image, jamais dans la chaîne live.
- **Ondelettes à trous** et **Non-local means** (module
  `avastack/processing/denoise.py`, numpy/OpenCV, AUCUNE dépendance
  nouvelle) → **LIVE (_et_ traitement EXTERNE)** : live = case dans le
  cadre VeraLux (avant l'étirement, thread solveur, après GraXpert live
  éventuel) ; externe = étape EN MÉMOIRE insérée entre les étapes
  subprocess (gradient → débruitage → BXT « 3. »).
Le reste de cette section est la TRACE de l'abandon du 15/09 : elle reste
valable (le fond « léopard » n'est PAS résolu) et doit être relue avant
tout réglage agressif.

### Comparaison avec SharpCap (doc officielle, analyse du 16/09/2026)

Demande d'Alain : « regarde ce que fait SharpCap en débruitage — est-ce que
ça pourrait être mieux que ce qui est prévu chez nous ? » Onglet
« Enhancement » de SharpCap : 5 outils (sauf le flou gaussien, tous
réservés à la licence Pro).

- **Gaussian Blur** : flou pur — sans intérêt (pire que ce qu'on a).
- **Bilateral Filter** (Radius + Luminance Tolerance) : MÊME FAMILLE que
  notre NLM (filtre local préservant les contours) → même limite
  structurelle (plaques à forte force). Seul intérêt : coût plus faible
  (`cv2.bilateralFilter`) — alternative, pas un progrès.
- **Colour Noise Reduction** (uniquement les canaux Cb/Cr du YCbCr, la
  luminance est INTACTE) : **LE point vraiment intéressant, et il n'existe
  PAS chez nous.** SharpCap le présente comme efficace « dans les premiers
  stades de l'empilement, quand peu de frames sont accumulées » = exactement
  notre cas d'usage live. Parce qu'il ne touche pas la luminance, il ne peut
  PAS créer de fond « léopard » ni de contraste fond lisse / bruit autour
  des étoiles — les deux défauts qui ont fait abandonner notre expérience.
  → **Piste n°1 à proposer si le sujet est rouvert après le test réel.**
- **Unsharp Mask** (Radius + Amount, option « Luminance Only ») :
  accentuation de netteté — AUGMENTE le bruit ; ce n'est pas un débruitage.
  **ÉCARTÉ le 16/09/2026 après mesures** (cf. section « Netteté live ») :
  sature (n'accentue que les ailes, jamais le cœur de la PSF) pour ×1,6-2,5
  de bruit.
- **Wiener Deconvolution** (luminance seule ; PSF estimée par la forme
  moyenne des étoiles détectées) : RESTAURATION de flou (netteté), pas
  débruitage ; AMPLIFIE le bruit → outil de netteté, pas un remède au bruit.
  **ÉCARTÉ le 16/09/2026 après mesures** : s'effondre dès que la PSF estimée
  s'écarte de ±10 % (halo sombre −0,10 du pic = l'« orange peel » de sa
  doc) — remplacé par **Richardson-Lucy**. ⚠️ CORRECTION : « nous l'avons
  déjà par l'aligneur » était FAUX — l'ORB de l'aligneur n'est PAS un
  détecteur photométrique, aucune PSF n'est disponible aujourd'hui.

**Conclusion** : sur le débruitage de LUMINANCE, SharpCap ne fait pas mieux
que ce que nous avons remis — mêmes familles d'algorithmes (bilatéral ≈
NLM, ondelettes), mêmes limites à forte force. Le seul apport réellement
nouveau de sa doc est le **débruitage de CHROMA seule** (Cb/Cr), peu
risqué, rapide et adapté au live peu intégré : à garder comme prochaine
piste.
⚠️ **Sur la NETTETÉ, ne pas suivre SharpCap** : sa doc ne propose que le
Wiener (fragile, cf. mesures) — le **Richardson-Lucy** fait MIEUX et plus
sûrement (décision d'Alain du 16/09/2026 : on ira directement sur RL,
Unsharp Mask et Wiener sont OUBLIÉS). Détail chiffré et plan : section
« Netteté live » ci-dessous.

### Trace de l'abandon (15/09/2026)

Demande d'Alain : le débruitage GraXpert IA (jalon 7) fonctionne mais
« très long et peu efficace » → essai d'algorithmes classiques locaux
rapides (numpy/OpenCV, aucune dépendance nouvelle) : jalon 8 en
traitement externe manuel, jalon 9 en LIVE dans le thread solveur
VeraLux. Après 3 itérations et 3 tests réels sur ses vraies images,
Alain a ABANDONNÉ : « soit ça fait le léopard, soit je baisse la force
et ça laisse du bruit autour des étoiles, ce qui le rend d'autant plus
visible. Je vais chercher de mon côté quelles autres méthodes existent. »

Ce qui avait été codé puis SORTI du dépôt (conservé dans `stash@{0}`) :
- **jalon 7** : débruitage GraXpert CLI dans les outils externes manuels
  (`-cmd denoising` + `-strength`, PAS `-smoothing`) — fonctionnel mais
  plusieurs MINUTES par image (IA) ;
- **jalon 8** : module `avastack/processing/denoise.py` — « ondelettes »
  (starlet à trous B3-spline 5 niveaux, seuillage k-sigma par couche,
  bruit estimé par MAD) et « nlm » (Non-local means OpenCV 16 bits,
  h auto-adapté au bruit réel par MAD) ; choix radio « 2. Débruitage »
  dans le traitement externe manuel, force commune ; étape locale
  exécutée EN MÉMOIRE entre les étapes subprocess ;
- **jalon 9** : le même débruitage offert EN LIVE (case dans le cadre
  VeraLux) — chaîne du thread solveur : stack → GraXpert live →
  débruitage local → étirement, résultat en cache par (empreinte image,
  méthode, force), persistance, sauvegarde « tel que vu » cohérente.
  Perf OK (~0,2-0,4 s à taille aperçu) — le problème n'était PAS la
  vitesse mais la QUALITÉ VISUELLE.

Le problème non résolu (constats réels d'Alain sur vraies images) :
- le FOND « LÉOPARD » (moutonnement en plaques) apparaît dès que la
  force est assez élevée pour être utile ;
- en baissant la force, le léopard disparaît MAIS il reste du bruit fin
  AUTOUR DES ÉTOILES — et le contraste rend le lissage du fond encore
  plus visible. Le compromis est structurel pour un débruiteur « pixel
  classique » appliqué à un empilement live peu intégré.

Corrections tentées, insuffisantes (v2.6.1 puis v2.6.2) :
1. seuillage DUR → GARROTE non-négative (transition continue, pas
   d'îlots de coefficients survécus) ;
2. ondelettes : ne seuiller QUE les niveaux fins (5 → 3 → 2 niveaux :
   les couches grossières contiennent de la STRUCTURE, les seuiller
   moutonne) ; k relevé jusqu'à 4σ ;
3. NLM : h 3σ → 0.8σ, fenêtre de recherche 21 → 15 px, gabarit 7 → 5 px,
   une passe forte → deux passes faibles (la fenêtre de recherche FIXE
   l'échelle des plaques ; le lissage itératif homogénéise).
Chaque correction a réduit le défaut sans l'éliminer.

LEÇONS retenues (reprises dans CLAUDE.md → Pièges) :
- sur du bruit PUR synthétique, les réglages agressifs paraissent
  MEILLEURS (les grandes échelles y sont du bruit) — seul un test sur
  image RÉELLE révèle le défaut ; valider réel dès la première passe ;
- pas de réglage « gratuit » : force utile = artefacts, force sûre =
  bruit résiduel autour des étoiles.
Si le sujet est reposé un jour : viser des méthodes qui épargnent les
étoiles par conception (IA légère locale, type Noise2* entraîné astro,
ou débruitage au moment de l'étirement) plutôt que re-raffiner le
pixel-classique. Pièges techniques consignés au passage : OpenCV 5
(fastNlMeansDenoising 16 bits = NORM_L1 + h tableau en 2e positionnel)
et GraXpert CLI (-strength pour le débruitage, -smoothing = gradient).

## Netteté live (page à venir) : Richardson-Lucy retenu, UM et Wiener ÉCARTÉS (analyse 16/09/2026)

Demande d'Alain : « j'avais mis Unsharp Mask et Wiener Deconvolution pour
savoir si ça valait le coup de rajouter une page de netteté dans le live
(contrairement à BlurX qui prend 45 s sur mon laptop et qu'on laisserait en
externe) ». Banc d'essai chiffré (scripts JETABLES, étoile synthétique
FWHM 3,00 px + bruit σ = 0,006 ; coût mesuré en convolutions séparables),
puis décision d'Alain : **on ira DIRECTEMENT sur Richardson-Lucy — Unsharp
Mask et Wiener sont OUBLIÉS.**

### Ordre de la chaîne (précisé par Alain : ne pas oublier les 2 premières)

**recadrage → gradient → débruitage → netteté → étirement.**

- **recadrage** = déjà AUTOMATIQUE (intersection des frames alignées,
  v2.3.3, dans `LiveStacker.mean()`) : c'est le `mean()` RECADRÉ qui
  alimente l'affichage, le GX live, les 3 sauvegardes et le traitement
  externe. Rien à ajouter, MAIS **c'est ce qui conditionne la qualité du
  gradient et de la PSF** (les bords d'écart = marches de fond qui affolent
  le modèle de GraXpert, puis faussent la PSF estimée sur les étoiles).
  Autrement dit : travailler sur une image propre dès le départ.
- **gradient** = GraXpert (live : cadre VeraLux / externe : étape « 1. »).
- **débruitage** = live (cadre VeraLux) OU externe (étape « 2. »).
- **netteté** = page À CRÉER (RL, luminance seule) — **APRÈS le débruitage,
  AVANT l'étirement** : on lisse d'abord, on restaure ensuite. L'ordre
  inverse amplifierait le bruit que le débruitage doit ensuite retirer, et
  déconvoluer une image déjà lissée par NLM accentue les plaques du
  « léopard ». ⚠️ Les deux à la fois = DÉCONSEILLÉ en 1re version.
- **étirement** = VeraLux (ou STF).

### Chiffres (FWHM avant 3,06 px ; « bruit × » en LINÉAIRE)

| méthode | FWHM après | bruit × | coût (1,6 Mpx) |
|---|---|---|---|
| Unsharp Mask 0,4 / 1,0 / 1,5 | 2,94 / 2,83 / 2,83 px | 1,39 / 1,99 / 2,48 | 6-11 ms |
| Wiener SNR 5 / 10 / 25 | 2,59 / 2,35 / 2,00 px | 1,09 / 2,22 / 5,56 | ~80 ms |
| Richardson-Lucy 3 / 5 / 10 it | 2,47 / 2,24 / 2,00 px | 1,14 / 1,22 / 1,39 | 44 / 74 / 142 ms |

Trois constats qui fondent la décision :
1. **Unsharp Mask SATURE** : dès amount ≈ 0,6 il n'améliore plus (2,83 px)
   — il n'accentue que les AILES, jamais le CŒUR de la PSF (gain réel
   ×1,08) et coûte ×1,6-2,5 de bruit. Écarté : mauvais rapport gain/bruit.
2. **Wiener > UM mais FRAGILE** : meilleur rapport gain/bruit que l'UM
   (2,35 px pour ×2,22) MAIS un seul bouton (SNR) et **il s'effondre si la
   PSF estimée est fausse** — mesuré (PSF vraie 1,27 px) : halo sombre de
   −0,005 (PSF 0,9) à **−0,102 (PSF 1,70)** du pic, exactement l'« orange
   peel » que sa doc décrit. C'est structurel : Wiener DIVISE par le
   spectre de la PSF (les hautes fréquences explosent).
3. **Richardson-Lucy GAGNE** : à bruit ÉGAL il resserre bien plus que l'UM
   (×1,22 de bruit → 2,24 px, contre 2,83 px) ; son réglage est un NOMBRE
   D'ITÉRATIONS (prévisible, plafonnable ; 3-5 it = le réglage utile) ;
   il est conservatif en flux (photométrie : 0,9163 × 1,22² = 1,00 — les
   étoiles gardent leur éclat total) et **tolère une PSF fausse de ±35 %**
   (creux du halo −0,015 à PSF juste, −0,021 à PSF 1,70 : pas
   d'effondrement).

### Découverte non évidente : le bruit AFFICHÉ ne bouge pas

Mesuré APRÈS l'étirement d'affichage (donc ce que l'œil voit), le bruit
reste **×0,99-1,01 pour TOUTES les méthodes**, y compris celles à ×2,5 en
linéaire. Raison : le point noir auto vaut `médiane − k·σ` et σ est mesuré
sur l'image COURANTE → amplifier le bruit fait DESCENDRE le point noir,
l'écran se renormalise tout seul.
**Asymétrie majeure avec le débruitage** :
- le **débruitage** change la TEXTURE → très visible à l'écran → risque
  d'artefacts (notre « léopard ») ;
- la **netteté** change l'AMPLITUDE, que le noir auto compense → peu
  visible en bruit ; le risque se limite aux halos sombres autour des
  étoiles et à l'« orange peel ».
⚠️ Corollaire : « enregistrer tel que vu » embarque le bruit AMPLIFIÉ que
l'écran ne montrait pas (même mise en garde chez SharpCap) ; en mode manuel
(black/white figés) le bruit accentué, lui, se voit.

### Contraintes techniques déjà vérifiées

- **Résolution de travail** : toute la chaîne live tourne sur l'aperçu
  **≤ 1600 px** (comme le débruitage et GraXpert live, `app.py`) → RL 3-5 it
  = 44-74 ms, ×2-3 sur le laptop d'Alain ≈ **0,15-0,25 s** : compatible
  avec le rythme d'empilement, d'autant que le solveur « dernier job
  gagnant » existe DÉJÀ (aucun threading à écrire). ⚠️ Sur un capteur
  26 Mpx l'aperçu est réduit ×0,25 → étoiles ~1 px : la déconvolution n'a
  plus rien à mordre (et fabrique du ringing) ; sur IMX585/533/662 l'aperçu
  est quasi NATIF → gain réel. SharpCap, lui, applique ses filtres à la
  résolution de la pile (d'où leur inclusion dans « Save Exactly as
  Seen ») : son avantage sur gros capteur se paie en temps de calcul.
- **PRÉREQUIS : détection d'étoiles + PSF — PAS disponible aujourd'hui.**
  ⚠️ L'ORB de `StarAligner` n'est PAS un détecteur photométrique (aucune
  PSF, aucune liste d'étoiles exploitable) : l'affirmation contraire d'une
  première analyse était FAUSSE. À écrire (~60-100 lignes) : tri par
  brillance + composantes 8-connexes + flux/moments sur une sous-image,
  médiane de σ + ellipticité (rejet des étoiles filées).
  **Argument décisif : ce détecteur sert AILLEURS** → affichage du
  **seeing live** (FWHM + nombre d'étoiles, très utile en EAA), rejet de
  frames par FWHM, diagnostic tilt/coma, et base d'un futur « débruitage
  des étoiles seules ».
- **Luminance seule** (comme SharpCap) : pas d'artefacts couleur.
- **Pas de no-op silencieux** : SharpCap n'applique RIEN si aucune étoile
  n'est détectée, sans le dire — nous afficherons un message explicite
  (« pas assez d'étoiles détectées : netteté inactive »).
- **BlurXTerminator reste en EXTERNE** (45 s sur son laptop, PSF par étoile
  non linéaire) : chaîne propre = **RL léger en live pendant la capture,
  BXT en post-traitement**.

### Plan proposé (ordre d'attaque)

0. ~~test réel du débruitage~~ ✅ **FAIT le 16/09/2026** : verdict « pas top »
   (encore moins bon après retrait de gradient), code conservé tel quel,
   cases simplement décochées — **chantier clos**, cf. section
   « Débruitage » ;
1. **détecteur d'étoiles + affichage du seeing SEUL** — validable en une
   nuit réelle (comparable à ce qu'Alain connaît déjà) ;
2. **module RL + page UI + « tel que vu » + config**, calqué sur la page
   débruitage (module séparé dans `avastack/processing/`, opt-in, DÉSACTIVÉ
   par défaut, plafond d'itérations) ;
3. **réglage sur ses vraies images**.

Effort : **3-6 h de code + tests**, mais la vraie dépense = la validation
sur images RÉELLES (leçon du « léopard » : jamais de validation sur du
synthétique — les réglages agressifs y paraissent toujours meilleurs).

## Le code VeraLux : où il en est

- `veralux_core_headless.py` (racine du dépôt) = moteur d'étirement
  hyperbolique **tiers** (extrait de VeraLux_HyperMetric_Stretch.py v1.5.2,
  Riccardo Paterniti, GPL-3.0-or-later), copié tel quel, déjà suivi dans git.
  Point d'entrée : `solve_and_stretch(img, ...) → (image étirée, log_d,
  diagnostics)`, profils capteur `SENSOR_PROFILES` (Rec.709 par défaut,
  IMX585/662/533/571-2600/294). N'importe numpy uniquement → **aucune
  dépendance pip nouvelle**.
- Ce fichier est **câblé depuis les jalons 1-3** : adaptateur
  `avastack/processing/veralux.py` (jalon 1, import robuste, clip [0,1]),
  affichage dans `DisplayProcessor` + UI (jalons 2-3). La chaîne complète
  est câblée et VALIDÉE (jalons 1-6) : fond cible + verrouillage logD,
  GraXpert live, sauvegarde « tel que vu », rejet des satellites
  (Winsorized), persistance config.json, boutons fins des curseurs.
- La tentative précédente (autre outil) était conservée dans les stashes
  `stash@{0}`/`stash@{1}` — **droppés le 15/09/2026** après validation du
  jalon 6 : la fonctionnalité avait été réécrite proprement (adaptateur
  `avastack/processing/veralux.py` du jalon 1) et le contenu des stashes,
  écrit « aux incohérences » par l'outil précédent, n'a jamais été
  réemployé (simple inspiration).


## Historique : tâche « auto-stretch VeraLux » — PLAN VALIDÉ par Alain le 14/09/2026, TERMINÉE le 15/09/2026

Procéder **PAR JALONS** (leçon de la 1re tentative « grosse modification »
perdue) : un jalon = `ast.parse` après chaque édition, lancement de l'appli,
test par Alain quand l'affichage est touché, **commit avant de passer au
suivant**. Bump `AVASTACK_VERSION` + changelog à chaque jalon touchant le
code. (Les stashes ont été droppés le 15/09/2026, après validation du
jalon 6.)

- **Jalon 0** — Mémoire : ce fichier mis à jour (plan + jalons), commit
  AVANCEMENT.md seul. ✅ 14/09/2026.
- **Jalon 1** — Adaptateur `avastack/processing/veralux.py` (réécrit
  proprement, stashes = inspiration seulement) : import robuste du moteur
  tiers (racine déduite de `__file__` via `parents[2]`, PAS du répertoire
  courant — installateur), clip défensif [0,1] en entrée (piège
  `normalize_input` : float avec max > 1.1 → divisé par 65535 !), mono
  (H,W) et RGB (H,W,3)↔(C,H,W), API `etirer(...)` → (image étirée, log_d,
  diagnostics). Test headless mono PUIS RGB avant tout câblage. L'appli
  reste inchangée à ce stade. ✅ 14/09/2026 : test headless OK (mono, RGB,
  non-mutation, clip, déterminisme logD, petite image, repli profil).
  **Chronos mesurés à 1600×1000** : target_bg ≈ 264 ms, logD forcé
  ≈ 196 ms (et 124 ms à 800×1200 en logD) → pour les jalons 2-3 : résultat
  VeraLux CACHÉ par image (recalcul à chaque nouvel empilement, jamais à
  chaque tick UI ~30 ms) et slider logD débouncé (~150 ms).
- **Jalon 2** — Affichage VeraLux, mode logD forcé : mode opt-in dans
  `DisplayProcessor` (calcul direct dans `process()` : pure fonction,
  ~20-50 ms sur l'aperçu), UI « Auto-stretch : STF / VeraLux » + slider
  logD forcé (0-7). VeraLux ne touche JAMAIS à black/white/gamma ;
  gamma/saturation communs appliqués après, comme pour le STF.
  ✅ 14/09/2026 (code + tests headless OK) : calcul en thread solveur dédié
  avec cache par image + clé de réglages (même en logD forcé, ~196 ms à
  1600×1000 → trop pour le thread UI), fallback STF au 1er calcul, jobs
  remplacés (jamais empilés), flag `vl_new` lu par `_tick` (aucun appel Tk
  hors thread UI). UI : combobox « Moteur d'étirement » + cadre VeraLux
  (slider logD, label logD/fond/erreur).
  ✅ **VALIDÉ PAR ALAIN le 14/09/2026 (test visuel, source simulée)** :
  « tout est bon » — UI non figée, slider logD réactif, STF par défaut
  inchangé, black/white/gamma intacts. Commité (v2.2.4).
- **Jalon 3** — Mode target_bg + solveur par frame : thread dédié
  déclenché à CHAQUE nouvel empilement (frames espacées de ≥1 s, souvent
  bien plus → le rythme des frames EST le cooldown ; résoudre toujours le
  DERNIER empilement, jamais une file d'attente), fallback STF le temps du
  1er calcul, bouton « 🔒 Verrouiller le logD résolu » (capte la dernière
  valeur résolue → calcul direct déterministe et réactif).
  🔧 14/09/2026 (code + tests headless OK) :
  `display.py` : `vl_mode_res = MODE_TARGET_BG` par défaut, `notify_new_stack()`
  (drapeau `_vl_force` consommé SEULEMENT quand un job est réellement soumis ;
  l'objet image nouveau à chaque tick UI ne déclenche plus rien — le worker
  pousse ~20 im/s même sans nouvelle frame), `reset()` vide aussi le cache
  VeraLux. `app.py` : combobox « Résolution du logD : fond cible (auto) /
  logD forcé » (défaut = fond cible) + curseur « Luminosité du fond visée
  (VeraLux) » 0.10-0.45 (recalcul immédiat : vl_target_bg fait partie de la
  clé), `_tick` surveille `st["frames"]` →
  `notify_new_stack()`, bouton 🔒 (capte `vl_log_d_resolu` via le curseur →
  mode logD forcé ; 🔓 = retour fond cible). `_test_veralux_jalon3.py` :
  18 vérifications OK (fond calé 0.20, aucun recalcul entre deux frames,
  dernier empilement gagnant sans file, verrouillage = déterminisme
  écart max 0.0000, reset, black/white intacts). **`_test_veralux_jalon2.py`
  adapté** : il doit forcer `vl_mode_res = MODE_LOG_D` (le comportement
  « logD forcé » n'est plus le défaut).
  ✅ **VALIDÉ PAR ALAIN le 14/09/2026 (test visuel, source simulée)** :
  curseur « Luminosité du fond visée » réactif (ajouté après son premier
  retour — il manquait), UI jamais figée, verrouillage logD opérationnel.
  Commité (v2.2.5).
- **Jalon 4** — GraXpert live (opt-in) : case « GraXpert live (avant
  étirement) » ; chaîne stack → GraXpert → VeraLux dans le thread solveur
  (ordre photométrique correct). BXT reste manuel (bouton ⚡, inchangé).
  ✅ **VALIDÉ PAR ALAIN le 14/09/2026 (test visuel, source simulée RGB)**
  puis commité (v2.2.6). Détails du code (14/09/2026) :
  `avastack/external/live.py` : `appliquer(img, cmd, timeout=300)` →
  (image traitée, ""), (image, erreur) en cas d'échec ; FITS temporaire →
  commande configurée ({input}/{output}/{outbase}, MÊME commande que le
  traitement manuel) → `find_output` + `load_image` + `auto_unflip` +
  contrôle des dimensions ; `commande_valide()`, `cle_image()` (SHA-1).
  **Exécution robuste** (`_run_bloquant_survivable`) : sorties dans des
  FICHIERS (pas de tubes) + Popen + `taskkill /F /T` au délai — sinon la
  boîte de dialogue modale cx_Freeze d'un crash GraXpert garde les tubes
  ouverts et BLOQUE le thread solveur même après le timeout (constaté en
  réel). **FITS RGB canaux-en-tête** (`_ecrire_entree`/`_lire_sortie`) :
  cf. piège ci-dessous (crash AI sur RGB corrigé).
  `display.py` : `vl_graxpert` / `vl_graxpert_cmd` (captés côté UI dans le
  job, jamais lus depuis le thread) ; le worker enchaîne GraXpert PUIS
  `_veralux.etirer` ; cache GraXpert indexé par (CONTENU image, COMMANDE) —
  bouger un curseur VeraLux ne relance PAS GraXpert, mais changer la
  commande l'invalide (bug évité au test) ; erreur → vl_error
  « GraXpert live : … » + étirement de l'image BRUTE en repli ; `reset()`
  vide le cache. `_vl_params()` intègre les réglages GraXpert.
  `app.py` : case dans le cadre VeraLux (refus + avertissement si commande
  incomplète), synchro de la commande éditée dans `_tick`, label préfixé
  « GX ✓ · ». Version 2.2.6 + changelog. `_test_graxpert_live_jalon4.py` +
  `_gx_factice.py` : 24 vérifications OK (défaut inactif, chaîne, cache,
  erreur non fatale, désactivation, reset, round-trip FITS, black/white
  intacts). Jalons 1-3 relancés : TOUS LES TESTS PASSENT.
  ✅ Test RÉEL (`_diag_gx_reel.py`, GraXpert 3.1.0rc2 installé) :
  mono 960×640 (3,4 s), RGB 960×640 (3,4 s), RGB 1600×1000 (3,6 s) —
  tous OK, interpolation AI, aucune erreur. Nettoyage des fichiers de
  diagnostic fait (gardé : `_diag_gx_reel.py` uniquement).
  ⚠️ Limites connues : GraXpert CLI recharge son modèle IA à CHAQUE
  appel → plusieurs secondes par frame possible ; le solveur « dernier
  job gagnant » absorbe le retard, l'UI reste fluide (STF d'attente).
  GraXpert clamp aussi sa sortie RGB à [0, 1] (étoiles > 1 légèrement
  écrêtées dans l'aperçu live — sans conséquence pour l'affichage).
- **Jalon 5** — « 💾 Enregistrer tel que vu (étiré) » : vue « empilement » →
  stack linéaire pleine résolution + GraXpert live + étirement PLEINE
  résolution (jamais l'aperçu 1600 px) ; vue « traitée » → inclut le
  résultat BXT (décision Alain). Gamma/saturation tels qu'affichés inclus.
  Le bouton d'enregistrement linéaire actuel reste inchangé.
  ✅ **VALIDÉ PAR ALAIN le 14/09/2026 puis commité (v2.2.7)** — cf.
  détails dans « État actuel » ci-dessus. Corrections intégrées : GX live
  limité à la vue « empilement », combobox profil capteur (avancé du
  jalon 6), réglages STF masqués en mode VeraLux, libellés « (linéaire) »
  clarifiés.
- **Jalon 6** — Finitions : ~~persistance config.json~~ (✅ CODÉ le
  15/09/2026, cf. « État actuel »), ~~combobox profil capteur~~ (✅ FAIT au
  jalon 5), ~~curseurs STF grisés en mode VeraLux~~ (✅ FAIT au jalon 5 :
  masqués, décision d'Alain), ~~rejet des satellites~~ (✅ CODÉ le
  15/09/2026, ajouté au jalon sur demande d'Alain), ~~changelog final,
  version 2.3.0~~ (✅ FAIT le 15/09/2026), ~~boutons « - »/« + » des
  curseurs~~ (✅ CODÉ le 15/09/2026, demande d'Alain).
  ✅ **VALIDÉ PAR ALAIN le 15/09/2026 (test réel, vraies brutes)** —
  jalon clos, stashes droppés, aucune tâche en suspens.

### Décisions d'Alain (14/09/2026)

- Étirement recalculé à CHAQUE frame (pas de cooldown figé 2-3 s) : les
  frames arrivent toutes les ≥1 s, souvent bien plus — quitte à attendre
  l'empilement de la suivante.
- GraXpert AVANT l'étirement, à chaque frame (« c'est bien mieux ») ;
  BXT, plus long, reste en manuel sur clic.
- Sauvegarde étirée = « save as seen » : TOUTE la chaîne (calibration →
  alignement → empilement → GraXpert si activé → BXT si vue « traitée » →
  VeraLux pleine résolution → gamma/saturation).
- logD verrouillable après résolution pour gagner en réactivité.
- Travail par jalons avec commit à chaque jalon.

## Décisions prises (issues de CLAUDE.md — s'imposent à cette tâche)

- Multiplateforme Windows / Linux / macOS : aucun chemin OS en dur sans
  repli ; venv de dev `C:\Astro\astrolivestack\venv` (dossier non renommé).
- `veralux_core_headless.py` est du code TIERS GPL-3.0 : jamais reproduit ni
  modifié ; toute adaptation se fait dans un fichier séparé du projet.
- Fonctionnalité optionnelle à risque → **opt-in** (désactivée par défaut).
- Ne jamais casser un défaut existant sans y être invité.
- Toute modification : bump `AVASTACK_VERSION` + changelog expliquant le
  constat réel ; vérifier la syntaxe par `ast.parse` après chaque édition.
- Nouvelle dépendance pip : signaler explicitement à Alain + requirements.txt
  (ici : aucune nécessaire, le moteur n'importe que numpy).
- Commentaires/docstrings en français ; CLAUDE.md jamais modifié par l'agent
  sans proposition + confirmation explicite d'Alain.

## Pièges connus

Repris de CLAUDE.md (tous applicables à cette tâche) :

- **OpenCV 5 refuse de débayeriser une image flottante** (float32/64) :
  tout float doit être traité comme mono sans débayerisation ; la devinette
  Bayer opère sur l'image ENTIÈRE d'origine, jamais sur une copie flottante.
- **`python3` ≠ `python`** sur la machine d'Alain (Store vs venv) : un
  symptôme anormal peut venir de l'interpréteur, pas du code — vérifier
  `sys.executable` avant de soupçonner le code.
- **Une fonction opérant sur des images peut supposer un nombre de canaux
  fixe** : le moteur VeraLux travaille en (canaux, H, W), AVAStack en
  (H, W, canaux) — bug réel du genre = image noire sans aucune erreur.
- **Une formule « additive » reste fausse si une entrée peut être négative** :
  données recalées/interpolées → clip explicite avant étirement.
- Rejouer un test sur la version d'avant la modification avant d'en conclure
  la cause ; isoler UNE variable à la fois en cas de multiples symptômes.

Constats propres à cette tâche (exploration du 14/09/2026) :

- **`.clinerules` créé à la racine (14/09/2026)** : il impose la lecture de
  CLAUDE.md + AVANCEMENT.md à chaque nouvelle session (mécanisme de règles
  automatiques de Cline). (NB 15/09/2026 : le `.clinerules` non suivi de
  l'outil précédent est parti avec stash@{0}, droppé — plus aucun risque
  de conflit.)

- **Deux stashes coexistaient** (`stash@{0}` dernière tentative avec
  `veralux.py` non suivi, `stash@{1}` essai antérieur) : **droppés le
  15/09/2026 après validation du jalon 6** (fonctionnalité réécrite
  proprement, rien à récupérer). Leçon conservée : les fichiers non
  suivis d'un stash vivent dans son **3e parent** (`stash@{0}^3`), pas dans
  le diff principal.
- **« Bug latent ligne ~276 » du fichier tiers : FAUX POSITIF (fichier relu
  intégralement le 14/09/2026)** — la ligne est
  `img_data[i] = VeraLuxCore.apply_mtf(img_data[i], m)`, complète et
  correcte ; le fichier tiers semble intact. Confirmation par test réel
  mono puis RGB (jalon 1) avant de s'y fier définitivement.
- **Coût CPU de `solve_and_stretch`** : résolution itérative de log_D,
  histogrammes 65 536 cases, sous-échantillonnage ~100k px — hors de
  proportion avec le `process()` STF actuel (~quelques opérations
  vectorielles). **Constat réel de la 1re tentative** : le moteur était
  recalculé à CHAQUE rafraîchissement d'écran (~toutes les 30 ms) DANS le
  thread de l'interface dès la case VeraLux cochée → appli complètement
  figée (plus d'empilement visible, boutons morts, impossible de charger un
  dark). Le calcul DOIT partir dans un thread séparé (ou un mécanisme
  cooldown/résolution périodique) — c'est la condition n°1 du câblage.
- **Corruption des réglages d'affichage (constat réel de la 1re tentative)** :
  le code de bascule VeraLux de l'époque modifiait `black`/`white`/`gamma`
  du `DisplayProcessor` pour « tricher », puis ne les **restaurait jamais** —
  après un seul rendu, les réglages manuels d'Alain étaient écrasés
  définitivement. Règle : VeraLux ne touche JAMAIS aux paramètres
  black/white/gamma de l'afficheur ; il produit sa propre image étirée et
  les réglages communs (gamma/saturation) s'appliquent ensuite comme pour
  le STF, sans réécriture des variables utilisateur.
- **État global côté moteur** : `VeraLuxCore._last_linear_expansion_diag`
  est un attribut de CLASSE (état partagé mutable) — en tenir compte si le
  calcul part dans un thread séparé (lecture seule ou verrou).
- **Anti-pompage à repenser** : le STF actuel lisse ses stats (EMA) entre
  frames ; VeraLux recalcule tout à chaque appel → prévoir le même type de
  lissage ou une résolution périodique, sinon l'image « pompe ».
- **Import du tiers hors package** : `veralux_core_headless.py` est à la
  racine, hors `avastack/` — l'adaptateur doit rendre ce chemin importable
  (le stash@{0} insérait la racine dans `sys.path`) ; attention au
  lancement via installateur/exe où la racine n'est pas le répertoire
  courant.
- **Piège `normalize_input` du moteur** : pour une image flottante, si
  `max > 1.1` le moteur divise par 65 535 (heuristique de détection
  d'entiers « oubliés de normaliser »). Un empilement avec quelques
  pixels > 1.1 (flat mal appliqué, hot pixel) serait écrasé. L'adaptateur
  clippe donc l'entrée à [0, 1] avant tout appel.
- **PIÈGE convention d'axes FITS couleur (GraXpert 3.1.0rc2, diagnostiqué
  le 14/09/2026)** : le lecteur FITS de GraXpert suppose les canaux sur
  NAXIS3 (astropy data = (C, H, W)), alors que `save_image` écrit la
  convention astropy standard (data (H, W, C) → NAXIS1=3). Un aperçu RGB
  mal lu est déformé : crash cv2.resize « !dsize.empty() » (boîte de
  dialogue modale cx_Freeze) avec l'interpolation AI, ou sortie dégénérée
  (W, 3) avec RBF. Le mono 2D n'est pas concerné (d'où des succès
  manuels sporadiques). Parade dans `avastack/external/live.py` : écrire
  l'entrée RGB canaux-en-tête (`_ecrire_entree`, transpose (2,0,1)) et
  retransposer la sortie (3, H, W) → (H, W, 3) (`_lire_sortie`). Avec ça,
  l'AI fonctionne sur RGB (test réel mono/RGB/RGB 1600×1000 OK en ~3,5 s).
  NB : l'entrée TIFF plante aussi chez GraXpert (imagecodecs LZW absent
  de leur build) → ne PAS passer de TIFF à GraXpert.
- **PIÈGE subprocess + boîte de dialogue cx_Freeze (14/09/2026)** : quand
  GraXpert plante, cx_Freeze affiche une boîte MODALE qui bloque le
  processus jusqu'au clic ; avec subprocess.run(capture_output=True) les
  tubes restent ouverts et communicate() ne revient JAMAIS, même après le
  timeout (le kill ne touche que cmd.exe). Parade : sorties dans des
  fichiers + Popen + `taskkill /F /T /PID` au délai (tue l'arborescence,
  la dialogue disparaît, le thread solveur repart). Cf.
  `_run_bloquant_survivable` dans `avastack/external/live.py`.

