# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---


- **DERNIER JALON (30/09/2026, jalons 85 + 86, v2.48.0 — TERMINÉ, BANCS VERTS,
  PUBLIÉE) —
  PRÉSERVATION DE LA LUMINANCE DU RETRAIT DU VERT + ORDRE DE LA CHAÎNE COULEUR.**
  Déclencheur : ton constat sur ton empilement SHO (NGC 2237) — « vert par
  défaut, manque de doré » ; exigences : la **variante fidèle Siril**
  (préservation de L*), « **l'UI doit respecter l'ordre des traitements** »,
  **pas d'exclusivité** SCNR/démagenta (en SHO la teinte magenta coexiste avec
  l'excès de vert), et **tests de non-régression RGB avant de coder dans
  l'appli** (sur tes images M31, pas sur une nébuleuse).
  **MESURES (tes données, AVANT tout code)** : ① le SCNR des jalons 22/23
  ÉTEINT l'objet — L* de la nébuleuse 56,5 → 25,8 (composite SHO étiré VeraLux)
  et 82,5 → 9,8 (VeraLux live) ; ② `scnr_doux` après `scnr` (force 1) est un
  **no-op** (écart 2,98·10⁻⁸) ; ③ ton fichier « empilement traité (linéaire) »
  `M31_traite_lineaire_2.38.0.fits` était **écrêté en vert** (excès max 5,9·10⁻⁸
  pour 100 % des pixels contre 1,6·10⁻¹ sur le même empilement d'origine) : la
  chaîne LINÉAIRE portait le SCNR ; ④ le moteur VeraLux est **LIÉ** (même
  plancher, même échelle, même MTF pour les 3 canaux —
  `veralux_core_headless.py:203-279`), donc le déséquilibre Ha/SII de tes brutes
  traverse tout l'étirement → piste conservée pour un jalon suivant : une
  **OPTION d'étirement PAR CANAL** (non lié ; mesuré : vert 91,7 % → 16,8 %).
  **LIVRÉ (code + banc NEUF ; PAS encore les bancs de régression ni le
  changelog)** : ① `processing/couleurs.py` :
  `scnr/scnr_doux/demagenta(amount=1.0, preserve_luminance=True)` — préservation
  de la **L\* CIE (Lab)** sur les **SEULS pixels corrigés** + garde de résolution
  `SEUIL_REMISE_LUMINANCE = 1e-6` ; `amount=1, preserve=False` rend l'ancien
  résultat **au bit**, `amount=0` rend l'entrée au bit ; ②
  `processing/display.py` : chaîne couleur **APRÈS l'étirement**
  (`couleur_apres_etirement`) dans le solveur VeraLux, `process()` STF/manuel et
  `rendu_pleine_resolution` ; sous-tuple `coul` de 6 (déballage tolérant) ;
  ③ `ui/app.py` : la chaîne couleur **quitte les trois chaînes LINÉAIRES** (⚡
  mono, ⚡ composition, « tel que vu ») ; job externe **15 → 12 éléments** ; les
  cases 4/5/6 du cadre externe sont **retirées** (note explicative) et
  `AVAAPPLI` suit ; UI : cadre « **Couleur de l'objet (APRÈS étirement)** »
  avec case « Préserver la luminosité (L\*) » (**cochée par défaut, comme
  Siril/PixInsight**) + curseurs « Force du SCNR » et « Force du démagenta » ;
  clés `vl_preserve_luminance` / `vl_scnr_force` / `vl_demagenta_force` (et les
  clés `ext_scnr*` sont **retirées** à la sauvegarde) ; ④ **BANC NEUF
  `bancs/_test_couleur_luminance_jalon85.py` : TOUT AU VERT** (7 sections,
  19 vérifications : scènes synthétiques + tes empilements M31 réels + NGC 2237
  SHO réel lu sur le NAS ; 0 pixel de régression au bit).
  **TEST RÉEL D'ALAIN (30/09/2026 au soir, ta capture) : la préservation de la
  luminosité MARCHE — la nébuleuse n'est plus éteinte — MAIS elle reste VERTE
  (« manque de doré »). MESURÉ (diagnostic NEUF
  `bancs/_diag_couleur_dore_jalon85.py`, sur les BRUTES de TA session live lues
  dans `compo_dossier_*` : 17 SII + 17 Ha + 21 OIII de 300 s, moyenne en cache
  locale) : ① le vert est PHYSIQUE — dans la nébuleuse SII/Ha = **0,219** et
  OIII/Ha = **0,260** (Ha = 4,6× SII) : un SHO à poids égaux (R=SII, V=Ha,
  B=OIII) ne PEUT pas être doré ; ② le SCNR ne peut PAS créer du doré — force
  0,35 : vert 86,6 % / R:G:B 1:1,68:0,95 ; force 0,75 : 78,4 % ; force 1,00 :
  vert 0 %, mais l'objet devient GRIS (R:G:B 1:1,00:0,99, saturation 0,19) —
  la préservation de L* tient (L* 37,7 → 37,6 sur tout le balayage) ; ③
  l'étirement PAR CANAL ne donne pas non plus du doré : il fait virer au CYAN
  (logD 3,45 pour le B contre 3,00 pour le V) — 24 % vert mais 60 % cyan ; ④
  le démagenta (force 1) est quasi neutre sur la nébuleuse (R:G 1,63 → 1,68) :
  sans danger ; ⑤ il faut **R ×2,0 à 2,5** pour que le rouge atteigne le vert
  (gain mesuré : 1,68× pour R = V, 2,2× pour R = 1,3·V) — mais un boost
  GLOBAL teinte aussi le ciel (fond R:G 1:0,59 à ×2,5, R>V 97 %), et la
  recette « Linear Fit (offset) » est un PIÈGE sur un objet qui remplit le
  champ (offsets R +0,235 / B +0,242 : nébuleuse délavée sat 0,20, fond bleu
  96 %) ; ⑥ le curseur « saturation par couleur » R ne crée pas de doré
  (86,6 % de vert à ×3,0) ; ⑦ **ta piste « Linear Fit (gain + offset) sans
  SCNR » (capture de 22:09) est MESURÉE et ÉCARTÉE** : le fit se cale sur le
  QUART CENTRAL, qui sur ta Rosette est à **60,6 % de pixels d'OBJET** → il
  égalise la NÉBULEUSE et pas le ciel (gains R **4,000 = le plafond** · B 2,875,
  offsets R **−0,1661** · B +0,0014) ; comparé sur TES DEUX ÉCRANS, mêmes 4
  coins : fond **sat 0,08 (neutre) à 21:47** (chaîne actuelle, SCNR 0,35, sans
  fit) → **sat 0,34 (brun) à 22:09** (fit), la nébuleuse du centre passant de
  R:G:B 1:1,64:1,09 à 1:1,90:1,54 (un peu PLUS verte) et sa saturation tombant
  de 0,72 à 0,31 (délavée). Le doré n'apparaît QUE sur le masque des 20 % les
  plus clairs (vert 88,5 % → 15,6 %, doré 6 % → 33 %) : le fit « marche » au
  niveau de brillance où il a été calibré et se trompe partout ailleurs (fond
  coloré, mi-tons plus verts) — mesure non reproductible d'ailleurs d'une
  session à l'autre (ma reproduction hors appli donne un fond BLEU là où ton
  écran donne un fond BRUN : les offsets sont en unités absolues, donc
  dépendants de la calibration de la session) ; ⑧ **la PROPOSITION est
  VALIDÉE par la mesure** : un boost du ROUGE pondéré par la luminance (0 dans
  le fond, `bancs/_diag_couleur_dore_jalon85.py::boost_rouge_masque`) atteint
  sur l'objet le MÊME R:G que le fit (**1,07 à ×3,0** contre 1,05) en gardant
  la saturation (0,70 contre 0,31 ; avec L* gardée : L* 37,99 = celle de la
  base) et en laissant le FOND **rigoureusement inchangé, au pixel** (les 4
  lignes « FOND » sont identiques à la base pour ×1,5 → ×4,0). ×4,0 = doré
  franc (R>V 55,6 %, rouge/orange 12,4 % + jaune 25,2 %), fond toujours intact.
  **CONCLUSION (mise à jour) : le levier est le boost du ROUGE (SII) MASQUÉ À
  L'OBJET, après l'étirement — et le Linear Fit doit rester DÉCOCHÉ en
  narrowband (c'est un outil de fond pour l'OSC).**
  **① FAIT (cette session) : L'ORDRE DES CADRES SUIT L'ORDRE DES TRAITEMENTS.**
  Le cadre couleur du jalon 22 est SCINDÉ en « **Fond et grain (AVANT
  étirement)** » (neutralisation du fond + bruit chromatique — ses deux réglages
  pré-étirement) et « **Couleur de l'objet (APRÈS étirement)** » (L*, SCNR, SCNR
  doux, démagenta, + le boost du rouge) ; « **Netteté live** » remonte AVANT
  « Affichage (temps réel) » (son titre disait « avant étirement » depuis le
  jalon 12 alors qu'il était affiché APRÈS le cadre qui porte l'étirement). Ordre
  vérifié sur l'application EN MARCHE : Fichiers → Caméra → Calibration →
  Empilement → **Fond et grain** → **Netteté live** → **Affichage** → **Couleur
  de l'objet** → État des calculs → Traitement externe → Sortie. AUCUN réglage,
  aucune clé de configuration et aucun comportement ne changent (seuls les
  PARENTS des widgets changent) ; le texte gris de la neutralisation ne cite plus
  les chiffres historiques du jalon 61 comme s'ils étaient mesurés (les gains
  RÉELS sont annoncés par « État des calculs (live) »). Le banc
  `_test_ui_visibilite_jalon47.py` porte une section **[5bis] NEUVE** qui
  verrouille l'ordre ET le contenu de chaque cadre.
  **④ FAIT (cette session) : JALON 86 — BOOST DU ROUGE (SII) MASQUÉ À L'OBJET.**
  `couleurs.boost_rouge(img, force=3.00, preserve_luminance=False)` avec
  `BOOST_ROUGE_MIN/MAX/DEFAUT = 1,00 / 4,00 / 3,00` et un masque de **centiles de
  luminance 40 → 97** : le gain du rouge suit la lumière du pixel (0 dans le
  fond, 1 sur l'objet), donc le FOND reste identique AU PIXEL (mesuré : écart
  exactement nul à ×1,5, ×3,00 et ×4,00). Appliqué EN DERNIER dans
  `display.couleur_apres_etirement` (après le SCNR — le SCNR retire l'excès de
  vert AU-DESSUS de (R+B)/2 : appliqué après le boost, il en reprendrait une
  partie ; les deux s'ADDITIONNENT donc au lieu de se combattre). UI : case
  « **Boost du rouge (SII) — masqué à l'objet** » (DÉCOCHÉE par défaut : c'est
  une retouche ESTHÉTIQUE, pas un défaut de rendu — un rendu par défaut reste
  inchangé au bit) + curseur « Force du boost (1,00 → 4,00, défaut 3,00 = le doré
  mesuré) » dans le cadre « Couleur de l'objet (APRÈS étirement) » ; clés
  `vl_boost_rouge` / `vl_boost_force` (config + `_reglages_rendu`, donc le
  fichier « tel que vu » suit l'écran) ; sous-tuple du job solveur 6 → 8
  éléments (déballage TOLÉRANT côté worker). **BANC NEUF
  `bancs/_test_boost_rouge_jalon86.py` : TOUT AU VERT (7 sections, 28
  vérifications)** — identité AU BIT à 1,00 et à toutes cases décochées, fond
  inchangé AU BIT, objet qui part vers le doré (G:R 3,22 → 1,21 à ×4,00 ; R>V
  0 → 7,6 % sur la scène synthétique, 6,2 % → 55,6 % sur l'empilement réel au
  diagnostic), saturation de l'objet CONSERVÉE (le Linear Fit la faisait tomber
  à 0,31 pour 0,72), variante « L* gardée » à 0,15 % de la lumière d'avant, ordre
  de la chaîne vérifié au bit, centiles insensibles au sous-échantillonnage
  (4,4·10⁻⁵), bornes/config/vue « traitée », coût 0,079 s sur l'aperçu 1600×904.
  NON-RÉGRESSION : 8 bancs rejoués (85, 47, 41, 39, 62, 63, 12, 59) → TOUS VERTS.
  **⑥ FAIT (cette session) : LES BANCS SONT AU CONTRAT NEUF — AUCUN RENDU N'A
  CHANGÉ.** Adaptation sans affaiblissement (chaque assertion reformulée mesure
  ce que le contrat neuf promet) : `_test_couleurs_jalon22.py` — les formules
  HISTORIQUES sont testées à `preserve_luminance=False` (« R et B inchangés » et
  « démagenta = négatif → SCNR → positif » ne sont vrais QUE là), la préservation
  de L* est mesurée AU DÉFAUT avec son TÉMOIN sur le même masque (0,21 unité de
  Lab rendue, contre 14 quand elle ne l'est pas) et l'assertion « les pixels non
  corrigés sont intacts AU BIT près » ; sections externes réécrites — la chaîne
  couleur **n'y retire plus rien** (résultat = entrée AU PIXEL, l'excès de vert
  la traverse intact : 0,0784 → 0,0784), les corrections pré-étirement sont
  lues aux indices **9 à 12** (neutralisation, chroma, force, rayon) et les clés
  `ext_scnr*` sont ABSENTES puis **retirées** d'une configuration antérieure.
  `_test_dn_jalon7.py` et `_test_chroma_halo_jalon65.py` **[6bis]** : le job
  externe est un **12-tuple** (le rayon de référence en est le 12e élément).
  **DÉCOUVERT AU PASSAGE** : `_test_bxt_entete_jalon69.py` était ROUGE sans avoir
  été vu (il attendait « SCNR » dans `AVAAPPLI`), et
  `_test_gradient_couche_jalon24.py` / `_test_gx_lot_externe_jalon83.py` étaient
  VERTS tout en encodant l'ANCIENNE disposition du job (leurs commentaires
  mentaient : la 12e valeur « neutralisation » y était devenue un rayon) — les
  trois remis au format courant. **30 bancs rejoués : TOUS VERTS.**
  **DÉCISION D'ALAIN (30/09/2026) : IL GARDE SON LINEAR FIT.** Le boost reste
  livré, DISPONIBLE et **DORMANT** (case décochée par défaut, rendu inchangé au
  bit près) : plus rien à coder pour son rendu. La piste « étirement par canal »
  reste MESURÉE et **refermée** (elle mène au cyan, cf. ③ ci-dessus).
  **⑤ FAIT (cette session) : LE RENDU SHO SE CHOISIT SUR DES IMAGES, PAS SUR
  DES STATISTIQUES.** Retour d'Alain sur le boost : « bof, pas satisfait par le
  boost du rouge, je préférais ma version avec linear fit offset + gain ».
  Diagnostic NEUF `bancs/_diag_dore_choix_jalon86.py` (chaîne de PRODUCTION
  étage par étage, sur les 3 moyennes SII/Ha/OIII déjà en cache) : 9 variantes
  rendues en PNG dans `%TEMP%\avastack_diag_dore\comparaison\` (planche contact
  + un PNG par variante) et un tableau de balayage SCNR × boost. **Deux mesures
  qui changent la lecture** : ① la reproduction du diagnostic jalon 85 était
  dans le MAUVAIS ORDRE (neutralisation AVANT le fit) : la chaîne réelle est
  **fit → neutralisation → chroma → étirement → couleur** (`display.py:833`
  puis `938-941` ; idem `app.py:5682→5806`, `6638→6674`) — avec le bon ordre le
  fond redevient neutre et chaud, comme sur l'écran d'Alain ; ② le VERT de son
  écran vient des CURSEURS, pas du principe : à SCNR 0,55 le boost 1,60 laisse
  **61 %** de l'objet vert, alors que SCNR **0,75** (même boost 1,60) n'en
  laisse plus que **5 %** (doré 88 %) — le doré était à un cran de curseur. Le
  fit reste mesuré tel quel : gain R **4,000 = PLAFOND**, gain B 3,162 (le cœur
  OIII part au CYAN), objet à saturation 0,32 contre 0,41 sans fit.

- **ÉTAT À LA CLÔTURE DE SESSION (30/09/2026, jalons 85 + 86, v2.48.0) — À LIRE
  EN PREMIER.** Le travail est TERMINÉ et prêt à livrer : working tree = jalons
  85 + 86 + bancs adaptés, **30 bancs rejoués TOUS VERTS** (dont les 4 qui
  bloquaient), changelog écrit et version **v2.48.0**.
  **DÉCISION D'ALAIN (30/09/2026) : IL GARDE SON LINEAR FIT « gain + offset ».**
  Le boost du rouge reste livré, DISPONIBLE et **DORMANT** (case décochée par
  défaut : le rendu par défaut est inchangé AU BIT près) — plus rien à coder pour
  son rendu.
  **CE QUI EST LIVRÉ (jalons 85 et 86)** : la chaîne couleur (SCNR / SCNR doux /
  démagenta) **suit désormais l'ÉTIREMENT** et préserve la **L\* CIE** des seuls
  pixels corrigés (comme Siril / PixInsight) — l'objet n'est plus éteint et le
  fichier linéaire n'est plus écrêté en vert ; le job de la chaîne externe passe
  de 15 à 12 éléments ; les clés `ext_scnr*` ne sont plus écrites (et sont
  RETIRÉES d'une configuration antérieure) ; l'ordre des cadres de l'écran dit
  l'ordre réel des traitements (… → Fond et grain → Netteté live → Affichage →
  Couleur de l'objet → État des calculs → Traitement externe → Sortie) ; le boost
  du rouge (SII) masqué à l'objet est disponible (1,00 → 4,00, défaut 3,00).
  **PAQUETS ET RELEASE v2.48.0 : PUBLIÉS (30/09/2026).** Les trois installeurs
  ont été reconstruits sur le code des jalons 85 + 86, puis vérifiés en lisant
  les archives (63 fichiers chacun, aucun `.so`/`.dll`/`.dylib`/`.rules`,
  `install_avastack.sh` en 0755, fins de ligne UNIX, racine unique) : Windows
  `installer/windows/output/avastack-setup-2.48.0.exe` (**11 501 171 o**, SHA-256
  `30960641917085A7B43C96506F2043078F8D284D8A83A523F8AF931335D9F895`), Linux
  `installer/linux/output/avastack-setup-2.48.0-linux.tar.gz` (619 127 o,
  `20ECD02D30EACFFF1352AEA0EFA4891B3921330372E856E3687ABFF032211777`), macOS
  `installer/macos/output/avastack-setup-2.48.0-macos.tar.gz` (616 744 o,
  `1AC09C224B63A4C6A1467FF8527AD902A71E41E7CA66FD88FB5917E0FC5A4B7D`).
  `INSTALLATION.md` est passé en v2.48.0 (titre, tableau des trois fichiers,
  noms cités dans les sections Windows/Linux/macOS, section 8 et repli porté à
  la v2.47.0). **Tag annoté `v2.48.0` sur `63ca10b`** (code + doc) et **release
  GitHub v2.48.0** publiée avec les trois paquets + `INSTALLATION.md` (notes =
  résumé « ce qui change » + la doc d'installation complète, relues par l'API :
  35 tirets longs, 268 « é », ZÉRO caractère de remplacement) :
  https://github.com/darkvad/AVAStack/releases/tag/v2.48.0
  **REPLI : v2.47.0** (publiée : tag annoté sur `5ecc0a1`, release GitHub
  https://github.com/darkvad/AVAStack/releases/tag/v2.47.0) — rien n'est perdu à
  revenir en arrière.
  **PISTES OUVERTES, À MESURER AVANT DE CODER** : ① `_on_source_choisie` attend
  la fin de la déconnexion d'une caméra dans une BOUCLE `root.update()` +
  `time.sleep(0.05)` bornée à 8 s — boucle RÉENTRANTE dans le fil Tk, piège connu
  sur macOS ; le guet de gel la DÉSIGNERA (pile « _on_source_choisie ») si un
  testeur la rencontre : attendre cette mesure plutôt que de réécrire à
  l'aveugle. ② TEST RÉEL macOS toujours en attente du testeur sur la v2.47.0
  (« 📂 Dossier » et « Charger un flat… » doivent répondre au PREMIER clic ; toute
  ligne « gel de l'interface » du `journal.txt` donne la pile du blocage).
  **LEÇONS DE CETTE PASSE (bancs)** : un banc qui encode un ANCIEN contrat doit
  être ADAPTÉ, pas contourné — le contrat neuf s'écrit dans le même langage
  (formules historiques testées à `preserve_luminance=False`, indices du job mis
  à jour, TÉMOIN mesuré pour prouver que l'assertion discrimine) ; un banc peut
  être ROUGE sans que personne ne le voie (après un changement de contrat,
  rejouer la SÉRIE, pas seulement les bancs qui semblent liés : c'est ainsi que
  `_test_bxt_entete_jalon69.py` a été trouvé) ; et un banc VERT peut mentir
  (commentaires et disposition du job périmés dans
  `_test_gradient_couche_jalon24.py` et `_test_gx_lot_externe_jalon83.py`).
  **NETTOYAGE DE CE FICHIER toujours à prévoir** (blocs antérieurs au 29/09) :
  à faire par petites touches, JAMAIS par un aller-retour PowerShell.
- **ÉTAT DE LA SESSION 30/09/2026 (jalon 83, v2.46.0 — version PUBLIÉE).**
  **Version stable de référence : v2.46.0**, PUBLIÉE (tag annoté + release GitHub,
  trois paquets + `INSTALLATION.md` ; installeur Windows
  `installer/windows/output/avastack-setup-2.46.0.exe`, **11 487 452 o**, SHA-256
  `60BAFCEA916F6186A3E674EAE2C2F18328902A93D69A7244789A7E4051FC7F60`).
  **TEST RÉEL EN ATTENTE sur cette version** : un ⚡ traitement par couche
  (composition à 3 rôles) — l'étape gradient doit s'annoncer « 3 couche(s) en
  parallèle… » et le résultat être celui d'avant. **Repli : v2.45.0** (testée et
  validée par Alain le 29/09 : « testé et OK, il y a un petit mieux »).
  **Livré par cette session (30/09/2026)** : ① les **MESURES de parallélisme sur
  TROIS machines** (jalon 82 : le débruitage LOCAL en lot PERD avec son réglage
  NLM ; le lot du gradient GraXpert gagne +57 à +60 % partout ; le lot du
  débruitage GraXpert ne rapporte rien → écarté) ; ② **v2.46.0** = le gradient de
  la chaîne externe ⚡ part en UN SEUL LOT (jalon 83, zéro pixel changé).
  **Coût de la chaîne live aujourd'hui** (ses réglages : aperçu 1600 px, GraXpert
  live, chroma/neutralisation/démagenta, VeraLux ; débruitage et netteté live
  DÉCOCHÉS) : GraXpert ~4,5-5 s (3 couches en parallèle) + le reste ~0,5 s →
  **passe ~5 s**, UNE seule passe par rafale, rafales d'1 minute → panneau
  occupé ~8 % du temps. ⚠ **Sur les machines à GPU dédié**, le débruitage GraXpert
  d'une couche de 8,2 Mpx coûte 26 s (4070) / 41 s (4060 Ti) contre **290 s** sur
  l'iGPU de dev : la chaîne ⚡ complète y est jouable (~1 min 30), ce qui n'était
  pas le cas ici.
  **IDÉES ÉCARTÉES — NE PAS LES REPROPOSER** (détail plus bas ; l'essentiel est
  aussi dans CLAUDE.md) : ① **décimation** de la chaîne lourde (« GraXpert/NLM
  une fois sur N ») — un débruitage ou un gradient n'est pas un modèle
  réutilisable : ne pas le refaire montrerait la pile NON corrigée ; ② **retrait
  du gradient sur l'image COMPOSÉE** — refus argumenté : en SHO/HOO chaque filtre
  à bande étroite a SON gradient (décision des jalons 24/54) ; ③ **inférence ONNX
  en processus** — mesurée : aucun gain en CPU, mémoire GPU épuisée en DirectML,
  et surtout **fidélité 0,24** avec le fond de GraXpert.
  **Piste du débruitage : MESURÉE ET CLOSE (30/09/2026, jalons 82 et 83)** —
  paralléliser le DÉBRUITAGE LOCAL perd du temps avec son réglage (NLM : 5,86 s →
  9,63 s en pleine résolution ; un appel NLM prend DÉJÀ tous les cœurs) et ne
  rapporte que 0,9 s avec « ondelettes » ; paralléliser le DÉBRUITAGE GraXpert ne
  rapporte rien non plus (mesuré sur trois GPU : un seul appel sature déjà la
  carte). **Le lot ne sert QUE là où un appel ATTEND** : le gradient, dont les
  appels passent 3,4 s à démarrer — il part en un seul lot partout depuis la
  v2.46.0.
  **NETTOYAGE À PRÉVOIR au prochain jalon** : les blocs « PASSE PRÉCÉDENTE » et
  « PASSES ANTÉRIEURES » antérieurs au 29/09 peuvent être supprimés (leur trace
  vit dans le changelog d'`avastack/__init__.py` et dans l'historique git) — à
  faire par petites touches, JAMAIS par un aller-retour PowerShell (piège
  d'encodage connu).
- **CLÔTURE DE LA SESSION 30/09/2026 — RELEASE v2.46.0 PUBLIÉE** :
  https://github.com/darkvad/AVAStack/releases/tag/v2.46.0 — tag **annoté** sur
  `6a261e1`, assets : `avastack-setup-2.46.0.exe` (11 487 452 o, SHA-256
  `60BAFCEA…`), `avastack-setup-2.46.0-linux.tar.gz` (599 904 o, `047B45AE…`),
  `avastack-setup-2.46.0-macos.tar.gz` (597 521 o, `3B9380C7…`) et
  `INSTALLATION.md` (18 468 o) ; notes de release = résumé « ce qui change » + la
  doc d'installation complète, fichier fabriqué hors dépôt en UTF-8 sans BOM
  (`gh release create --notes-file`), **relues par l'API : 38 tirets longs,
  284 « é », ZÉRO caractère de remplacement**. Commits de la session : `e688670`
  (mesures + 2 bancs) → `b877daa`/`590c28d` (banc GPU + mémoires) → `a104e0d`
  (correction DirectML, précision d'Alain) → `ec39d55` (résultat Linux/4060 Ti) →
  `b3a0980` (jalon 83) → `6a261e1` (INSTALLATION.md v2.46.0, commit taggé).
  **Arbre propre, `origin/master` à jour.**
- **JALON 83 (v2.46.0) — LE GRADIENT DE LA CHAÎNE EXTERNE ⚡ PART EN UN SEUL LOT :
  LIVRÉ, BANCS VERTS.** Décision d'Alain (30/09/2026), prise après la mesure des
  trois machines (jalon 82 : +57 à +60 % pour le gradient ; le lot du débruitage,
  lui, ne rapporte rien → il RESTE en série).
  - **CODE** : `avastack/ui/app.py` → `_compo_couches_traitees` : le gradient des
    couches part en UN appel à `gx_live.appliquer_lot` (mémoire bornée par
    `parallele_max`, repli SÉRIE automatique), avec validation du GABARIT de
    commande et de l'EXÉCUTABLE avant tout lancement (mêmes messages que la
    chaîne mono), garde « couche vide » conservée et message de progression
    pendant le lot (« N couche(s) en parallèle… »). Le DÉBRUITAGE garde son
    déroulé couche par couche, et le dossier de la chaîne ne reçoit plus que les
    FITS utiles (un par couche, seulement pour le débruitage GraXpert).
  - **CHANGEMENTS DE COMPORTEMENT, ASSUMÉS ET TESTÉS** : ① un échec PARTIEL du
    gradient conserve la couche brute (message posé) et la chaîne CONTINUE —
    avant, une seule couche en échec arrêtait tout ; un échec TOTAL arrête et le
    dit, comme avant ; ② l'ordre devient « TOUS les gradients, puis les
    débruitages » (chaque couche reçoit bien son débruitage APRÈS son gradient,
    vérifié par les moyennes du journal).
  - **BANC NEUF `bancs/_test_gx_lot_externe_jalon83.py` (7 sections, 28
    vérifications, TOUT PASSE)** : égalité AU BIT avec le repli série
    (`MAX_PARALLELE = 1`), chevauchement prouvé par journal horodaté, entrées
    vérifiées par leurs MOYENNES, couche vide écartée, échec partiel qui
    continue, échec total qui s'arrête, intégration `_run_external_compo` (App
    réelle + composition à 3 rôles) au composite identique AU BIT.
    **13 bancs de régression verts** : gradient_couche_jalon24, ext_rgb_jalon14,
    dn_jalon7, denoise_live_jalon9, gx_parallele_jalon81, etat_calcul_jalon40,
    save_brute_jalon59, compo_ui_jalon19, fit_canaux_jalon54, graxpert_live_jalon4,
    pleine_res_traitee_jalon69, outils_jalon71, rafale_fin_rendu_jalon80.
  - **VERSION v2.46.0** (changelog en tête d'`avastack/__init__.py`). **Aucun
    paquet ni release reconstruit** : à décider (l'installeur Windows + Linux +
    macOS et une release sont la suite naturelle). **TEST RÉEL À FAIRE** : un
    ⚡ traitement par couche (composition 3 rôles) — surveiller la ligne d'état
    pendant l'étape gradient (« 3 couche(s) en parallèle… ») et vérifier que le
    résultat est celui d'avant.
- **JALON 82 — MESURES DE PARALLÉLISME (30/09/2026) : LE DÉBRUITAGE PERD, LES
  GRAXPERT NE SE PARTAGENT PAS.** Demande d'Alain : « mesurer le gain en
  parallélisant le débruitage (et éventuellement celui de GraXpert dans le
  traitement externe) ». Deux bancs NEUFS, sur ses VRAIES couches
  (`C:\Astro\test\canal_R/G/B.fit`, 2168 × 3838 = 8,32 Mpx chacune) et son VRAI
  GraXpert installé (mesures faites sur sa machine, GraXpert 3.1.0rc2) :
  - **① `bancs/_diag_parallele_debruitage_jalon82.py` — débruitage LOCAL par
    couche** (NLM = son réglage, force 0,40 ; lot et série rendent TOUJOURS des
    pixels identiques AU BIT) : **le LOT PERD** — 0,95-1,37 s → 1,61-2,02 s à
    l'aperçu 1600 px, **5,86 s → 9,63 s en pleine résolution (-64 %)**. Cause
    MESURÉE (courbe de mise à l'échelle incluse au banc) : un appel NLM utilise
    DÉJÀ les cœurs (×4,26 de 1 à 14 fils à l'aperçu, ×3,73 en pleine résolution),
    donc trois appels se partagent des cœurs déjà pris. Symétriquement
    « ondelettes » GAGNE +53 % en lot (1,82 s → 0,85 s pleine résolution) parce
    qu'un de ses appels n'utilise QU'UN fil (×1,13) — gain absolu 0,9 s, et ce
    n'est pas son réglage. **Conséquence : ne PAS paralléliser le débruitage
    local**, et NE PAS brider OpenCV (à 1 fil le NLM passe de 5,9 s à 22,2 s).
  - **② `bancs/_diag_parallele_gx_externe_jalon82.py` — traitement externe ⚡ par
    couche** (ce chemin était resté SÉRIE au jalon 81) : **GRADIENT
    (`cmd_graxpert`, pleine résolution) : 10,12 s → 4,24 s (+58,1 %)**, sorties
    identiques À L'OCTET (le gain du jalon 81 se vérifie donc sur la chaîne ⚡) ;
    **DÉBRUITAGE GraXpert (`cmd_graxpert_dn`, mode « graxpert ») : 869,80 s
    (14 min 30 s, 290 s par appel) contre 981,69 s en lot → -12,9 % (PERTE)**,
    sorties identiques à l'octet aussi.
  - **CE QUE LA MESURE APPREND SUR SON RÉGLAGE** : dans la chaîne ⚡, le gradient
    des 3 couches coûte ~10 s et le DÉBRUITAGE GraXpert ~14 min 30 s — c'est lui
    qui coûte la chaîne. Son modèle de débruitage est le **3.0.2**
    (`denoise-ai-models\3.0.2\model.onnx`, DirectML, batch 4) et **chaque appel
    consomme ~3,45 Go** (working set mesuré) : les trois simultanés ont tenu
    ~10 Go. Trace du partage des cœurs : un appel SEUL brûle ~282 s de CPU en
    290 s ; les trois simultanés en ont brûlé ~880 s CHACUN (×3,1 pour le même
    travail) tout en restant plus LENTS — le lot ne recouvre ici aucun temps mort,
    il ajoute de la contention. ⚠ Pour un futur code : la constante du jalon 81
    (`PAR_APPEL_OCTETS = 800 Mo`) a été mesurée sur le GRADIENT (modèle 1.0.1) et
    ne couvre PAS le débruitage GraXpert.
  - **POUR COMPARAISON (banc ①, même machine, mêmes couches)** : ces MÊMES 3
    couches en débruitage LOCAL (« nlm », force 0,4) coûtent **5,9 s** en pleine
    résolution. L'écart 5,9 s contre 14 min 30 s est un CHOIX DE QUALITÉ, pas une
    contrainte technique.
  - **③ BANC GPU NVIDIA LIVRÉ — LA SUITE SE JOUE SUR LES DEUX AUTRES MACHINES
    (décision d'Alain, 30/09/2026 : « on s'arrête là sur cette machine »)** :
    `bancs/_diag_parallele_gpu_jalon82.py` (neuf, AUTONOME — aucun chemin
    absolu, couches synthétiques à la bonne définition si on ne lui en donne pas,
    rapport écrit dans le dossier de travail). Il répond à trois questions, dans
    cet ordre : **(1) GraXpert utilise-t-il VRAIMENT le GPU ?** en LISANT le
    journal du CLI (`Providers :` / `Used providers :` pour le gradient,
    `Available/Used inference providers :` pour le débruitage — DEUX formulations
    différentes, constat du 30/09/2026) ; **(2)** série contre lot sur les
    3 couches, gradient ET débruitage ; **(3)** VRAM et RAM de pic
    (`nvidia-smi`, absent de cette machine → dit « non mesurée », jamais
    inventée). **Validé ici** : `diagnostic` = ~25 s et n'entraîne AUCUNE mesure
    longue ; le reste (`gradient` / `debruitage` / `tout`, `--px N` réservé à la
    validation) est à lancer sur la **RTX 3060 Ti 8 Go sous Linux** et la
    **RTX 4070 12 Go sous Windows** :
    `python bancs/_diag_parallele_gpu_jalon82.py <dossier des couches> diagnostic`
    puis l'étape voulue. Ce que la mesure a déjà établi ICI et qui reste à
    confirmer là-bas : le gain du lot **dépend de la taille** (+22 % à 300 px,
    **−13 % à 8,32 Mpx** pour le débruitage) — et l'appel instrumenté du banc
    rend la MÊME image que l'application, au bit (vérifié à l'exécution).
  - **④ PREMIER RÉSULTAT RENVOYÉ PAR ALAIN + CORRECTION DU BANC (30/09/2026)** :
    sur son **Windows à RTX 4070**, le diagnostic donne
    `Used inference providers : ['DmlExecutionProvider', 'CPUExecutionProvider']`
    → **le GPU SERT, mais via DirectML — pas via CUDA** : le build Windows de
    GraXpert embarque DirectML, qui calcule sur tout GPU DirectX 12, **NVIDIA
    comprise**. Le banc annonçait à tort « CUDA absent → l'inférence ne passe pas
    par le GPU NVIDIA » : **message corrigé** (grille de lecture
    DML/CUDA/CoreML/CPU, et « CPUExecutionProvider SEUL » = le seul cas sans GPU),
    et il **sonde désormais la VRAM de la carte NVIDIA pendant l'appel** — c'est
    elle qui dira si la 4070 (ou l'iGPU) fait le travail, le moteur nommé ne le
    disant pas. Leçon remontée dans CLAUDE.md. **Reste à mesurer** : la même chose
    sur le **Linux/3060 Ti** (CUDA attendu là-bas, mais rien n'est présumé) et les
    mesures série/lot sur les deux machines.
  - **⑤ RÉSULTAT COMPLET WINDOWS / RTX 4070 12 Go (Alain, 30/09/2026)** — couches
    réelles de 8,21 Mpx (`D:\astro\test`), 16 cœurs, DirectML, GraXpert 3.1.0rc2 :
    - **GRADIENT** : 1 appel 3,58 s (identique à l'iGPU : c'est du démarrage) ·
      série 10,73 s → **lot 4,28 s = +60,1 %**, images **identiques au bit** ;
    - **DÉBRUITAGE** (modèle 3.0.2) : **1 appel 25,9 s** contre **290 s** sur
      l'iGPU de dev (**11× plus rapide**) · série 77,71 s → **lot 67,65 s =
      +12,9 %** (un GAIN ici, là où l'iGPU PERDAIT 13 %), images identiques au bit ;
    - **VRAM** : gradient 972 Mo (série) / 683 Mo (lot) · débruitage **3 686 Mo
      pour UN appel, 9 642 Mo pour trois** sur 12 282 Mo — **78 % de la carte** ;
      GPU à 100 % même avec un seul appel (d'où le gain modeste du lot).
    - **CONSÉQUENCES** : ① sur une carte à GPU dédié, le lot est utile pour les
      DEUX étapes (et jamais au détriment d'un pixel) ; ② **le verdict du lot
      dépend du GPU** (même appli, mêmes couches : −13 % sur iGPU, +13 % sur
      4070) ; ③ ⚠ **trois débruitages simultanés demandent ~9,6 Go de VRAM** :
      **ça ne rentre PAS dans les 8 Go de la 3060 Ti**, et le garde-fou actuel
      (`PAR_APPEL_OCTETS = 800 Mo`) ne compte que la mémoire SYSTÈME — d'où
      `--simultane N` ajouté au banc pour sonder une carte limite (à mesurer
      d'abord à 2).
    - Observation à ne pas perdre : sur cette machine **la config d'AVAStack est
      vide** (commandes par défaut : `graxpert … -correction Subtraction
      -smoothing 0.5` au lieu des siennes `Division -smoothing 0.8`) — le rendu du
      gradient y sera donc DIFFÉRENT s'il traite des images là-bas sans régler le
      cadre « Traitement externe ».
  - **⑥ RÉSULTAT LINUX / RTX 4060 Ti 8 Go (Alain, 30/09/2026)** — mêmes couches
    (8,32 Mpx, copiées dans `./bancs`), machine à **4 cœurs** et 7,7 Go de RAM,
    GraXpert-linux (`~/apps/graxpert/GraXpert-linux/GraXpert`) :
    - **CUDA est bien le moteur sous LINUX** (`Used providers :
      ['CUDAExecutionProvider', …]` pour le gradient ET le débruitage) → ta
      remarque du 30/09 est MESURÉE : Linux = CUDA, Windows = DirectML, et la
      nouvelle mesure de VRAM confirme l'adaptateur (+270 Mo sur le gradient,
      +2 200 Mo sur le débruitage, « c'est BIEN la carte NVIDIA qui a calculé ») ;
    - **GRADIENT** : série 11,45 s → lot 4,92 s = **+57,0 %**, identiques au bit,
      VRAM 2 001 Mo au pic (sur 8 188) — le lot du gradient tient donc dans 8 Go ;
    - **DÉBRUITAGE `--simultane 2`** : 40,65 s par appel (contre 25,9 s sur la
      4070 et 290 s sur l'iGPU de dev) · série 121,95 s → **lot de 2 : 120,50 s =
      +1,2 % = RIEN**, identiques au bit, GPU à **100 % dans les deux cas**,
      VRAM 2 217 → 4 410 Mo (2,2 Go par appel en CUDA) ;
    - **VERDICT FINAL, TRIPLE MESURE (iGPU dev, 4070 Windows, 4060 Ti Linux)** :
      ① **le lot du GRADIENT gagne PARTOUT (+57 à +60 %)** — c'est le seul gain
      universel, gratuit, à coder si on veut ces ~6 s par chaîne ; ② **le lot du
      DÉBRUITAGE est ABANDONNÉ** (−13 % sur iGPU, +12,9 % sur 4070, +1,2 % sur
      4060 Ti) : un seul appel sature déjà le GPU (100 % partout), il n'y a aucun
      temps mort à recouvrir ; ③ les sorties sont **identiques au bit dans les
      3 × 2 configurations**.
    - À SAVOIR pour cette machine : **4 cœurs** (le direct live y sera limité par
      le processeur, cf. le NLM qui prend 14 fils ici), et sa **config AVAStack
      est vide** (commandes GraXpert par défaut : `-correction Subtraction
      -smoothing 0.5`, ses `Division -smoothing 0.8` n'y sont pas).
  - **ÉTAT** : AUCUNE ligne de l'application n'a été modifiée (mesures seules ;
    les deux bancs sont les seuls fichiers neufs). Décision d'Alain attendue :
    ② le gradient ⚡ en lot est prêt à coder (même mécanisme que le jalon 81,
    zéro pixel) — à noter qu'il ne fait gagner que ~6 s sur une chaîne ⚡ dominée
    par le débruitage.
- **CLÔTURE DE LA SESSION 29-30/09/2026 — RELEASE v2.45.0 PUBLIÉE** :
  https://github.com/darkvad/AVAStack/releases/tag/v2.45.0 — tag annoté sur
  `4af8621`, assets : `avastack-setup-2.45.0.exe`,
  `avastack-setup-2.45.0-linux.tar.gz`, `avastack-setup-2.45.0-macos.tar.gz`,
  `INSTALLATION.md` (notes de release = résumé « ce qui change » + la doc
  d'installation complète, fichier de notes fabriqué hors dépôt en UTF-8 sans
  BOM, `gh release create --notes-file` — procédure du projet respectée).
  Commits de la session : `245200f` (v2.43.0) → `4dfe57e`/`0456607`/`f1193d7`
  (v2.44.0) → `79d55d8`/`4af8621` (v2.45.0). **Arbre propre, `origin/master` à
  jour.** Retour d'Alain : « testé et OK, il y a un petit mieux ».


- **JALON 80 (v2.44.0) — RENDU DÉCLENCHÉ EN FIN DE RAFALE : LIVRÉ, BANCS VERTS
  (détail en ⑬, plus bas).** Vérification demandée par Alain au même moment
  (« utilises-tu bien le modèle GraXpert 1.0.1 ? ») : OUI, c'est en ⑭.
  **RELEASE v2.44.0 PUBLIÉE (29/09/2026)** —
  https://github.com/darkvad/AVAStack/releases/tag/v2.44.0 — tag annoté sur le
  commit `f1193d7`, **trois** paquets + `INSTALLATION.md` attachés.
  **PROCHAINE ÉTAPE : tes essais réels sur v2.44.0.**
  Ce jalon fait suite au **CHANTIER PERFORMANCE ET RÉACTIVITÉ (jalon 79, LIVRÉ en
  v2.43.0 — installeur Windows `avastack-setup-2.43.0.exe`, 11 481 938 o, SHA
  `17646C4B…`)**, dont le détail (①…⑫ ci-dessous) reste jusqu'au prochain
  nettoyage du fichier.
- **CHANTIER PERFORMANCE ET RÉACTIVITÉ (jalon 79) — décisions d'Alain
  du 29/09/2026.** But : le live plus rapide **sans qu'un seul pixel change.**
  Ordre tranché par Alain : **A (instrument) → C-bis (réactivité des réglages
  d'après-étirement) → B (cœur d'empilement)**, C (chaîne d'images) plus tard ;
  **B4 garde les maths EXACTEMENT telles quelles** (médiane = moyenne des 2
  valeurs centrales, MAD exact : seuls le tampon, la mise en place et le
  parallélisme changent). GPU **clos** : mesuré, l'iGPU Intel partage la même
  mémoire (2× au mieux, transfert compris) et la RTX n'est pas sur cette
  machine.
  - **① ÉTAPE A FAITE ET VALIDÉE (29/09/2026)** — banc NEUF
    `bancs/_bench_performance.py` + référence machine
    `bancs/_bench_performance_ref.json` (portable de dev). Il chronomètre
    24 étapes du pipeline sur une séquence SYNTHÉTIQUE déterministe de 8,4 Mpx
    (la taille de ta brute ; `--reel <dossier>` ajoute une vraie image de ton
    dossier de test) : empilement kappa et winsorized, moyenne, composite HOO,
    alignement ORB et triangles, étoiles/seeing, redimensionnement, chaîne
    d'affichage (STF, gamma, saturation), les deux histogrammes. **Surtout, il
    VÉRIFIE l'empilement** : les deux accumulations (kappa et winsorized, rejeu
    du warmup compris) sont comparées à une réimplémentation numpy ÉCRITE DANS
    LE BANC → **trois contrôles passent à l'écart ZÉRO** (moyennes identiques
    au bit, rejets identiques). C'est ce garde-fou qui autorise à optimiser.
  - **② LE BANC A DÛ ÊTRE ÉTALONNÉ — leçon à retenir : deux runs STRICTEMENT
    identiques différaient de 10 à 20 %** (le premier, machine au repos, est le
    plus rapide). D'où : mesures retenues au **MINIMUM** de N itérations (4 pour
    les étapes lourdes, 10-20 pour les légères), écarts **NORMALISÉS par une
    calibration machine** prise au début ET à la fin, et seuil d'alerte à
    **25 %** (à 15 %, un run à blanc faisait crier six fausses « régressions »).
    Contrôle repassé : « = » partout, ±10 %.
  - **③ CE QU'IL DIT DÉJÀ (machine au repos, 8,4 Mpx) : `add` kappa 349 ms
    installé (80 ms en warmup), `add` winsorized 1 836 ms, `mean` 59 ms, add
    RGB 990 ms, composite HOO 326 ms, alignement ORB 414 ms / triangles 48 ms,
    étoiles 28 ms (pleine rés.) et 15 ms (aperçu), aperçu d'affichage 72 ms
    (STF RVB) / 113 ms (gamma) / 147 ms (saturation) / histogrammes 34 ms,
    VeraLux 189 ms.** Diagnostic (mesuré, prototype à l'appui) : le coût n'est
    pas dans les maths mais dans les **temporaires float64** (~15 tableaux de
    67 Mo par frame) et dans l'absence de parallélisme (numpy est mono-thread :
    4 fils sur des bandes de lignes donnent ×3,3 sur un simple `a + a`) ;
    prototype `add` kappa préalloué/float32/4 fils : **325 → 51 ms, bit à bit
    identique**.
  - **④ ÉTAPE C-BIS FAITE ET VALIDÉE (29/09/2026)** — gamma, saturation globale
    et saturation par couleur ne recalculent plus RIEN pour rien (`hist=False`,
    même règle que les barres de niveaux depuis le jalon 75) et l'étirement
    lui-même est MÉMOÏSÉ (`DisplayProcessor._moteur_stf`) : **geste gamma
    103 → 41 ms, saturation 147 → 74 ms, geste mono 29 → 3 ms, et 137 → 28 ms
    mesurés dans l'interface réelle**. `_auto_params` ne calcule plus
    `_calc_stats` en `live=False` (son résultat était JETÉ). Témoin inversé
    vérifié : un réglage qui change vraiment la donnée (« Coupure du bruit »)
    recalcule toujours les histogrammes. Banc NEUF
    `bancs/_test_perf_reactivite_jalon79.py` (18 vérifications, interface
    réelle) + **11 bancs d'affichage rejoués verts**, dont « l'écran = le
    fichier » AU BIT du jalon 68. Version passée à **v2.43.0** (changelog
    détaillé dans `avastack/__init__.py`).
  - **⑤ ÉTAPE B FAITE ET VALIDÉE (29/09/2026) — LE CŒUR D'EMPILEMENT.** `add`
    ne crée plus de tableaux temporaires (ils étaient jetés à chaque frame :
    c'était l'essentiel des 325 ms du warmup) : tampons préalloués, opérations
    en place, élémentaire en float32, **carrés et seuil de rejet en float64**
    (le produit de deux float32 y est exact → `sumsq` et la décision de rejet
    restent **bit à bit** ceux d'avant), travail réparti par **bandes de
    lignes** (4 fils au plus ; une seule bande sous 1,5 Mpx, donc les bancs
    restent séquentiels). **MESURÉ (mono 8,4 Mpx) : add kappa 295 → 56 ms
    (−81 %), warmup 80 → 14 ms, RGB 938 → 181 ms, winsorized 1 666 → 570 ms
    (−66 %)** ; contrôles à **écart ZÉRO** (moyennes au bit, rejets identiques :
    517 906 et 2 257 140). **55 bancs rejoués verts**, dont le jalon 6 qui exige
    `array_equal(sum/wsum)` avec l'ancien algorithme. Prix dit : les tampons
    sont persistants (+240 Mo en mono, +725 Mo en RGB par stacker, libérés par
    `reset()`). Changelog détaillé dans `avastack/__init__.py`.
  - **⑥ INSTALLATEURS v2.43.0 RECONSTRUITS (29/09/2026, à la charge de l'agent
    avant tout essai réel)** — les trois, mêmes sources que le code testé :
    `avastack-setup-2.43.0.exe` (11 492 708 o, SHA-256 `FF3565BE…8457B4`),
    `avastack-setup-2.43.0-linux.tar.gz` (589 243 o, `392E6AD9…BCDE2C`),
    `avastack-setup-2.43.0-macos.tar.gz` (586 837 o, `B3ECD82E…EB08BB9`). Le
    `.gitignore` a été complété : le dossier de sortie **macOS** n'était pas
    ignoré (le paquet apparaissait comme « non suivi ») — c'est réparé, et les
    artefacts ne partent jamais dans le dépôt. **Aucun tag, aucune release :
    la v2.43.0 n'est pas publiée** (elle attend ton essai réel).
  - **⑧ LE COMPOSITE MULTI-RÔLES FAIT AUSSI (29/09/2026, ton accord)** — même
    diagnostic, même méthode, **maths inchangées**. Ce qui coûtait n'était pas
    l'assemblage mais des **copies inutiles** (`.astype(float32)` sur des
    tableaux déjà float32, `np.mean` d'une liste d'un seul rôle, bornes de
    normalisation recalculées à chaque appel). Livré : copies supprimées,
    bornes **figées par frame**, **moyenne de rôle mémoïsée** sur `n`, et
    **composite brut mémoïsé** (clé = accumulation/cadre/composition/mode L,
    **jamais** les corrections de couleur → un geste de gain réutilise
    l'assemblage). **MESURÉ (HOO, 2 rôles de 8,4 Mpx) : premier calcul
    298 → 163 ms, geste 298 → 0 ms, `mean()` répété 43 → 0 ms.** Quatre
    contrôles à écart 0 dans le banc (composite mémoïsé = recalculé, couches
    réutilisées, composite brut indépendant des gains, invalidation par
    nouvelle frame). **55 bancs rejoués verts** + 11 bancs caméras.
  - **⑨ INSTALLATEURS v2.43.0 RECONSTRUITS UNE SECONDE FOIS** après ce
    chantier (le code a changé : la règle « rebuilder avant tout essai réel »
    s'applique à nouveau — mêmes noms de fichiers, aucune release publiée) :
    `avastack-setup-2.43.0.exe` (11 481 938 o, SHA-256 `17646C4B…52E16`),
    `…-linux.tar.gz` (591 174 o, `1462834C…630DD`), `…-macos.tar.gz`
    (588 841 o, `037FDD49…2371A`). **TON ESSAI DE LA v2.43.0 (première
    version) : « déjà pas de régression »** ✔, avec ton constat honnête : **la
    différence n'est pas flagrante** — normal sur des poses longues (le
    processeur n'était pas le facteur limitant) ; les gains se voient sur les
    gestes (~137 → ~30 ms), sur le winsorized (1,7 → 0,5 s) et sur les sources
    rapides (~1,6 → 5 images/s).
  - **⑩ PROCHAINE ÉTAPE — RIEN À CODER EN ATTENTE DE TA PAROLE.** Si un jour tu
    veux aller plus loin (mesuré, non fait) : chemin ORB 378 ms (les triangles,
    40 ms, restent recommandés), médian winsorized 493 ms (le mur
    mathématique), geste de saturation 79 ms, `_hist_canaux` 35-50 ms.
  - **⑪ ÉTAT DE FIN DE SESSION (29/09/2026, soir) — EN ATTENTE DE TON ESSAI.**
    Tu réessaies **`installer/windows/output/avastack-setup-2.43.0.exe`**
    (11 481 938 o, SHA-256 `17646C4B…52E16`) — soit par-dessus l'installation
    existante, soit après désinstallation. **Aucun tag, aucune release** avant
    ton retour ; la v2.43.0 reste non publiée. Dépôt : `origin/master` =
    **`d053651`**, arbre propre, **8 commits** pour le jalon 79. Ce que tu peux
    regarder (et qui ne concerne QUE la composition) : bouger un **gain**, une
    case **SCNR / chroma / démagenta** en mode HOO/SHO → plus d'attente d'un
    demi-seconde ; en mono/OSC simple, rien ne change (c'est normal, ces chemins
    n'étaient pas concernés). Précédent essai (première version) : « déjà pas de
  - **⑫ DIAGNOSTIC DE L'ÉTAT DES CALCULS (29/09/2026, soir) — la chaîne LIVE
    mesurée sur TES données et TES réglages** (composition RGB 3 rôles, GraXpert
    live + NLM + netteté + chroma + neutralisation + VeraLux) :
    **~30 s par passe en pleine résolution** (GraXpert 16,8 s — 3 sous-processus,
    5,6 s chacun — NLM 7,1 s, VeraLux 2,5-3,1, netteté 0,6, chroma 0,5,
    neutralisation 0,4, corrections ~1-2) et **~12 s en aperçu 1600 px**
    (GraXpert 9,7 s, NLM 1,0, VeraLux 0,39, le reste < 0,2). **GraXpert domine
    même en aperçu : ~2,5 s FIXES par appel** (rechargement du modèle IA du
    sous-processus) — d'où 9,7 s pour 3 couches.
    - **Pourquoi le panneau reste occupé** : une passe (30 s) ≈ le cycle de
      rafale (33 s) et le solveur ne s'arrête jamais (il n'y a AUCUN travail
      perdu : il relance dès qu'il est libre, une seule passe en attente). Le
      temps occupé est de l'**arithmétique**, pas un défaut.
    - **Idées ÉCARTÉES (décisions prises avec Alain, consignées pour ne pas les
      reproposer)** : ① **décimation de la chaîne lourde** (« GraXpert/NLM une
      fois sur N ») — **son objection est décisive** : un débruitage ou un
      retrait de gradient n'est pas un modèle réutilisable ; ne pas le refaire
      sur la pile suivante montrerait la pile NON corrigée, donc l'image
      sauterait d'une passe à l'autre. Abandonné. ② **Cooldown seul** (ⓐ) —
      invisible : le solveur ne gaspille rien aujourd'hui, il enchaîne. Non
      implémenté.
    - **TON USAGE EST DÉJÀ POSSIBLE** : « Rendu pleine résolution » se bascule à
      tout moment (décochée = chaîne sur l'aperçu, 12 s/passe ; cochée = pleine
      résolution, 30 s/passe ; cochée à la fin = UNE passe puis plus rien, la
      laisser cochée ne coûte donc rien sans nouvelle brute). **Correction
      consignée** : le `config.json` ne dit QUE l'état au dernier
      enregistrement (écrit à la fermeture) — il ne prouve pas l'état pendant
      la session.
    - **RESTE À TRANCHER** : GraXpert live **une fois sur le composite** au lieu
      d'une fois par couche → ~3-4 s au lieu de 9,7 (aperçu), passe ~6 s au lieu
      de 12 — MAIS le gradient serait retiré après recomposition (le jalon 24
      avait choisi l'avant). Décision d'Alain, sur comparaison visuelle (à
      préparer sur ses images M31 si tu le veux).
  - **⑬ JALON 80 — RENDU EN FIN DE RAFALE (v2.44.0) : IMPLÉMENTÉ, BANCS VERTS.**
    Décision d'Alain (29/09/2026, juste après le diagnostic ⑫) : « code le rendu
    en fin de rafale ». `_tick` ne relance plus la chaîne lourde à la PREMIÈRE
    brute d'une rafale : il note le dernier empilement (`_rendu_differ`) et le
    rend au SILENCE (`RAFALE_QUIET_S = 0,35 s`), avec la borne `RAFALE_MAX` pour
    qu'un dossier pré-rempli ne retarde jamais l'affichage. Mesuré bout en bout
    sur une rafale de 6 brutes : **1 rendu au lieu de 5** (les deux runs sont
    dans le même banc, `RAFALE_QUIET_S = 0` reproduisant l'ancien comportement)
    → sur son réglage le panneau passe de ~70 % à ~35 % d'occupation, et l'image
    affichée est toujours la plus PROFONDE (plus de passe entière sur une pile à
    1 brute). Zéro pixel changé : même chaîne, même pile, seule la DATE du
    déclenchement change. Sources NON-dossier (caméras) : strictement inchangées.
    Bancs : `_test_rafale_fin_rendu_jalon80` (6 cas) + régression cadence42,
    reset76, veralux3, graxpert_live4, ui5, etat_calcul40, multifolder19,
    config6, save_brute59 — **tous verts**. ⚠ Le banc 76 ÉCHOUE quand il tourne
    juste après les autres (mesures de scan sensibles à la charge du disque) :
    le relancer SEUL.
    PIÈGE TROUVÉ PAR LE BANC (et corrigé) : `_vl_frames` vaut `None` en début de
    session → `st["frames"] - self._vl_frames` plantait `_tick` à la 2e brute
    d'une rafale ; la borne compte désormais depuis 0 (`(self._vl_frames or 0)`).
  - **⑭ VÉRIFICATION DEMANDÉE PAR ALAIN : le modèle GraXpert EST bien 1.0.1.**
    La commande de l'application ne passe aucun `-ai_version` → c'est la version
    STOCKÉE des préférences GraXpert
    (`%LOCALAPPDATA%\GraXpert\GraXpert\preferences.json`,
    `"bge_ai_version": "1.0.1"`) qui s'applique — confirmé par SON journal
    (« Using AI version 1.0.1 … bge-ai-models\1.0.1\model.onnx »).
    Son étonnement (« dans Siril c'est très rapide ») est expliqué : chaque appel
    CLI RECHARGE le modèle (217 Mo) → **~2,8 s FIXES par appel** (5,6 s sur
    8,4 Mpx contre 3,25 s sur 1,45 Mpx à l'aperçu), donc ≥ 8 s pour ses 3 couches
    quel que soit le travail ; Siril garde le modèle en mémoire entre les appels.
    → PISTE (gros levier, à proposer comme jalon) : faire l'inférence ONNX **en
    processus** dans notre venv (le modèle est un `.onnx` lisible) → le modèle
    serait chargé UNE fois, quelques centaines de ms par couche au lieu de
    3,25 s. Et RESTE À PROPOSER, gratuit : épingler `-ai_version 1.0.1` dans sa
    commande (aujourd'hui elle suit les préférences de GraXpert, qui peuvent
    changer silencieusement et modifier le rendu).
  - **⑮ PAQUETS v2.44.0 RECONSTRUITS (29/09/2026, à la charge de l'agent — trois
    packers lancés, version lue dans `AVASTACK_VERSION`)** :
    - Windows `installer/windows/output/avastack-setup-2.44.0.exe` — **11 483 167 o**,
      SHA-256 `D064D5AEE0AD3BFBF1448FF31D14E0D0719709E4CFFB34681C4F1FAED9CAE186`
    - Linux `installer/linux/output/avastack-setup-2.44.0-linux.tar.gz` — 593 581 o,
      SHA-256 `1EC90CC9177F86802DD6C82D7A25AAC6A33E959FCB1718AA3B3DA717803334BC`
    - macOS `installer/macos/output/avastack-setup-2.44.0-macos.tar.gz` — 591 226 o,
      SHA-256 `ABA1E04FE814E088BE68B5397E32B4BFB79522F2197A1500975EDF47317A372C`
    Commit de la passe : `4dfe57e` (code + banc + mémoires) puis `0456607`
    (paquets), `f1193d7` (INSTALLATION.md v2.44.0), poussés sur `origin/master`.
    **TAG `v2.44.0`** (annoté, sur `f1193d7`) et **RELEASE PUBLIÉE** :
    https://github.com/darkvad/AVAStack/releases/tag/v2.44.0 — assets :
    les trois paquets ci-dessus **+ `INSTALLATION.md`** (notes de release =
    résumé « ce qui change » + la doc d'installation complète, fichier de notes
    fabriqué HORS dépôt en UTF-8 sans BOM, `gh release create --notes-file` —
    procédure v2.42.0 respectée).
  - **⑯ DÉCISIONS D'ALAIN APRÈS ESSAIS DE v2.44.0 (29/09/2026)** :
    - **RAFALES DE 1 MINUTE** — ses essais montrent que c'est mieux ainsi
      (cadence « toutes les 1 min ») : avec la v2.44.0 il n'y a plus qu'UNE passe
      par rafale, le panneau est donc calme (10,5 s de calcul pour 60 s de
      cycle). Rien à coder : c'est la combobox du jalon 42.
    - **ON NE FIGE PAS `-ai_version`** : il préfère **suivre les mises à jour de
      modèles GraXpert** (conséquence assumée : le fond retiré peut changer
      silencieusement quand GraXpert change de modèle). Note CLAUDE.md corrigée.
    - **PISTE À ÉTUDIER : l'inférence ONNX EN PROCESSUS** (point 2 de
      l'explication donnée le 29/09/2026) — il l'a trouvée séduisante et demande
      d'abord l'explication, puis éventuellement un **essai de faisabilité
      borné** : charger `bge-ai-models/<v>/model.onnx` avec `onnxruntime` DANS
      notre venv, mesurer l'inférence (CPU vs DirectML) et comparer le fond
      obtenu à celui du CLI sur une de ses images. Enjeu mesuré : ~2,8 s FIXES
      par appel × 3 couches = 8,3 s des 9,7 s que coûte GraXpert sur sa passe de
      10,5 s (aperçu). ⚠ À dire franchement si on y va : ce n'est PAS « zéro
      pixel changé » (réimplémentation, pas le même binaire) → comparaison
      chiffrée + visuelle, REPLI automatique sur le CLI en cas d'échec, et le
      modèle n'est JAMAIS redistribué (on lit celui de SON installation).
    - **FAITS VÉRIFIÉS LE 29/09/2026 POUR CETTE PISTE (ne pas les rechercher)** :
      ① **un « processus GraXpert permanent » est IMPOSSIBLE tel quel** — leur CLI
      traite **une image par invocation** (aucun mode serveur ni « lot
      d'images » ; le `-batch_size` ne concerne que les TUILES du débruitage) et
      l'installation est un bundle **PyInstaller figé** : modules en `.pyc`
      compilés pour **Python 3.11** (le bundle porte `python311.dll`), donc
      **inimportables** par notre venv en **Python 3.14**, et aucun
      `python.exe` pilotable n'est livré. ② **leur paquet Python EXISTE sur
      PyPI** (`graxpert`, versions alpha `3.2.0a0.dev4…3.2.0a3`,
      `requires_python >= 3.11`, **licence GPL-3.0**) → charger LEUR code une
      fois dans un worker permanent est donc *techniquement* possible (résultats
      identiques, même modèle), mais : version **alpha** ≠ la 3.1.0rc2 utilisée,
      **GPL-3.0** qui contaminerait la chaîne live (projet MIT ; précédent
      assumé mais ponctuel : `veralux_core_headless.py`), et dépendances
      lourdes (onnxruntime, scipy, astropy) à installer et maintenir.
      → **DÉCONSEILLÉ par l'agent**, décision d'Alain à prendre.
      ③ **ALTERNATIVE ÉCARTÉE PAR ALAIN (29/09/2026) — NE PAS LA REPROPOSER** :
      retirer le gradient **sur l'image composée** (1 appel au lieu de 3) a été
      refusé, argument à l'appui : **le retrait PAR COUCHE est une décision
      argumentée des jalons 24/54** (en SHO/HOO, chaque filtre à bande étroite a
      SON propre gradient — ce qui marche sur M31 ne doit pas être adopté avant
      d'être validé sur des nébuleuses SHO). Il ne veut pas d'aller-retours.
      → La seule voie restante pour raccourcir la passe est de réduire le coût
      FIXE par appel : piste B (essai de faisabilité demandé le 29/09/2026).
    - **ESSAI DE FAISABILITÉ PISTE B — EN COURS (29/09/2026)** : Alain a des
      doutes sur la fidélité (« je doute d'arriver au même résultat
      rapidement ») mais demande l'essai. Points à mesurer, dans cet ordre :
      ① `onnxruntime` s'installe-t-il dans notre venv **Python 3.14** (les roues
      cp314 sont récentes : si non, la piste B exige un environnement séparé) ;
      ② contrat du modèle (`onxx` inputs/outputs : taille, dtype, plage) ;
      ③ **vitesse** d'une inférence chez nous vs le « travail » mesuré de
      GraXpert (0,5 s à l'aperçu, 2,8 s en pleine résolution) ;
      ④ **fidélité** : comparer notre fond à celui du CLI — le CLI sait SORTIR
      son modèle de fond (`-bg`), c'est le juge de paix chiffré.
    - **VERDICT DE L'ESSAI (29/09/2026) — PISTE B ÉCARTÉE, chiffres à l'appui** :
      ① notre inférence **CPU** (onnxruntime 1.30, 12 fils) : **119 ms/tuile** →
      aperçu 3,2 s (**aucun gain** vs l'appel CLI complet de 3,25 s !), pleine
      résolution 17 s/couche (3× PIRE que 5,6 s) ; ② avec **DirectML** (l'iGPU,
      comme GraXpert) : **48 ms/tuile** → aperçu **1,36 s** ✔ mais
      **E_OUTOFMEMORY** en envoyant les 135 tuiles de la pleine résolution d'un
      seul lot (iGPU à mémoire PARTAGÉE → il faut découper) ; GraXpert lui-même
      tourne à **~20 ms/tuile** (il réduit probablement l'image avant
      inférence — paramètre `downscale_factor` de son API) ; ③ **FIDÉLITÉ :
      corrélation 0,24** entre notre fond et le sien (`-bg`) — **le modèle seul
      ne suffit PAS** : leur prétraitement, leur recollement et leur lissage
      font l'essentiel du résultat. Le reproduire fidèlement = ingénierie
      inverse lourde, sans garantie. → **ON ARRÊTE LÀ** (décision attendue
      d'Alain). Environnement de l'essai **entièrement restauré** :
      `onnxruntime`/`onnxruntime-directml` + leurs dépendances désinstallés,
      `pip check` = aucune dépendance cassée ; aucun code d'AVAStack n'importe
      onnxruntime.
    - **★ TROUVÉ AU PASSAGE — LE VRAI GAIN EST LÀ (mesuré, ZÉRO pixel)** : le coût
      de GraXpert est **FIXE par appel** (~2,8 s de démarrage + chargement des
      217 Mo) et la chaîne live l'appelle **3 fois EN SÉRIE** (une par couche).
      Or les couches sont **INDÉPENDANTES** : lancer les **3 sous-processus EN
      PARALLÈLE** chevauche leurs démarrages. Mesuré sur 3 vraies couches
      d'aperçu : **13,70 s → 5,58 s** (gain **8,12 s, 59 %**) ; en pleine
      résolution : **11,88 s → 5,74 s** (gain 6,14 s) ; et les fichiers produits
      sont **identiques OCTET À OCTET** (SHA-256 égaux) — même binaire, mêmes
      arguments, entrées indépendantes ⇒ **aucun pixel ne change par
      CONSTRUCTION**. Piste à implémenter (**jalon 81**) dans le solveur live
      ET dans la chaîne externe (⚡) : GraXpert par couche en parallèle, puis le
      débruitage. ⚠ À prévoir : mémoire (3 × ~500 Mo : ~1,5-2 Go), arrêt des
      trois enfants au délai, concurrence bornée si la machine est petite.
    - **★★ MÉMOIRE MESURÉE (29/09/2026, demandée par Alain AVANT de coder)** :
      un processus GraXpert consomme **~680 Mo** (les 217 Mo du modèle + son
      runtime Python) ; **3 simultanés = pic cumulé ~1,22 Go** mesuré en direct
      (2 simultanés : 950 Mo), et **tout est rendu à la sortie** des processus
      (RAM libre de la machine revenue exactement à son niveau d'avant : aucun
      résidu). Durées sur les 3 couches d'aperçu : **5 s à 2 comme à 3
      processus simultanés** (contre 13,7 s en série) — et un PREMIER appel
      après une longue inactivité coûte 13 s (disque froid : les 217 Mo du
      modèle à relire), autre raison de ne pas multiplier les appels.
      Sur sa machine (32 Go, ~16 Go libres avec l'application ouverte) ce coût
      est négligeable ; sur une petite machine, **borner la concurrence** (2-3
      selon la mémoire libre) est le garde-fou à prévoir.
  - **⑰ JALON 81 — OUTILS EXTERNES PAR COUCHE EN PARALLÈLE (v2.45.0) : LIVRÉ,
    BANCS VERTS.** Décision d'Alain (29/09/2026), après avoir demandé la MESURE
    de la mémoire avant de coder. Implémentation : `compat.memoire_libre()`
    (Windows/Linux/macOS, aucune dépendance), `external/live.py` →
    `MAX_PARALLELE = 3`, `parallele_max(nb)` (borné par la mémoire : ~800 Mo
    réservés par appel simultané, 1 Go laissé à la machine) et
    `appliquer_lot(items)` (mêmes valeurs qu'en série, repli SÉRIE automatique) ;
    le **GRADIENT par couche** part en UN lot dans le solveur live
    (`display.py`) et dans l'export pleine résolution (`app.py`), le DÉBRUITAGE
    garde son ordre et les CACHES PAR RÔLE sont intacts.
    Banc NEUF `_test_gx_parallele_jalon81` (9 cas) : bornes de concurrence,
    chevauchement prouvé par journal d'entrées/sorties, **égalité AU BIT** avec
    et sans parallélisme sur le solveur live ET sur l'export, caches, échec
    isolé, repli mémoire. Gain sur le banc : 3 appels factices de 0,8 s →
    4,10 s en série contre **1,47 s** en lot (64 %).
    LEÇON DE BANC À RETENIR : un banc qui REMPLACE une fonction (`appliquer`)
    doit lui donner la MÊME SIGNATURE — le bouchon à 2 arguments du banc 59 a
    cassé dès que le lot a passé le délai (3 arguments) ; corrigé, et les autres
    bancs (jalon 9/12/22/40) étaient déjà tolérants.
    Régressions relancées, **toutes vertes** : graxpert_live_jalon4,
    couleurs_jalon22, denoise_live_jalon9, etat_calcul_jalon40,
    sharp_live_jalon12, save_brute_jalon59, fond_bleu_jalon62,
    chroma_nr_jalon63, compo_ui_jalon19, veralux_jalon3, cadence_jalon42,
    ui_jalon5, multifolder_jalon19, rafale_fin_rendu_jalon80.
    **PROCHAINE ÉTAPE : rebuild des trois installateurs v2.45.0 + release.**
  - **⑱ PAQUETS v2.45.0 RECONSTRUITS (29/09/2026, trois packers lancés)** :
    - Windows `installer/windows/output/avastack-setup-2.45.0.exe` — **11 486 570 o**,
      SHA-256 `CC0F742EA1A8DE90E337D3031FC3A8A8DEF71203C15E779AAF7A8F748180EB32`
    - Linux `installer/linux/output/avastack-setup-2.45.0-linux.tar.gz` — 598 080 o,
      SHA-256 `880BD83E24AF837F292CE4877397EB1F887ED36FE5D9A272A60FE29004A0E1B4`
    - macOS `installer/macos/output/avastack-setup-2.45.0-macos.tar.gz` — 595 750 o,
      SHA-256 `5DFB85E3DF79B4E8185009EC556CB32A1D06F6287DF09C0DF418F114672DF3E5`
    `INSTALLATION.md` mis à jour en v2.45.0 (artéfacts, SHA, repli v2.44.0).
    Commit de la passe : `79d55d8`. **Aucun tag, aucune release** (à décider —
    Alain a demandé celle de v2.44.0 le 29/09, celle-ci reste à valider).



  - **⑦ bis LEÇONS DU JALON REMONTÉES DANS CLAUDE.md (ton accord explicite,
    29/09/2026)** — section « Pièges », trois leçons : ① un **fichier de mémoire
    ne passe JAMAIS par un aller-retour PowerShell** (UTF-8 sans BOM lu en
    ANSI → accents double-encodés : AVANCEMENT.md corrompu puis restauré par
    git, avec les contrôles à refaire) ; ② un **banc de performance doit être
    étalonné** (minimum de N itérations, calibration machine au début ET à la
    fin, seuil à 25 %, et mesurer AVAStack FERMÉ) **et vérifier la correction**
    (écart 0 exigé contre une référence écrite dans le banc) ; ③ le **coût d'un
    chemin par frame est souvent l'allocation, pas le calcul** (tampons
    préalloués, opérations en place, float32 élémentaire, float64 pour les
    carrés et le seuil → exactitude AU BIT, bandes de lignes parallèles, prix
    mémoire DIT). Commit de la passe : `8e98031` (+ le présent commit mémoire).


- **PASSE DE CLÔTURE (29/09/2026, soir) — v2.42.0 : INSTALLATEUR macOS, TES
  VALIDATIONS CONSIGNÉES ET LEÇONS REMONTÉES.** Trois choses, sans toucher au
  code de l'application (donc **même version 2.42.0**) :
  - **① INSTALLATEUR macOS (jalon 78)** — `installer/macos/` (script
    `install_avastack.sh` + packer `build_avastack.py`) : app + venv dans
    `~/Library/Application Support/AVAStack/app`, lanceur `~/.local/bin/avastack`,
    **bundle `.app` minimal** (Info.plist + lanceur, donc **pas de Python
    embarqué**). Prérequis dit et testé : un Python **avec Tkinter**. **ÉTAT
    DATÉ : écrit, vérifié par le banc `_test_installeur_macos_jalon78.py` et par
    l'exécution réelle de ses garde-fous, mais PAS ENCORE EXÉCUTÉ SUR UN MAC.**
  - **② TES VALIDATIONS** — le **point 2 est TESTÉ ET VALIDÉ par ton essai**
    (« Réinitialiser l'empilement » puis nouvelle cible en mode dossier : le
    bloc « EN ATTENTE » de la v2.41.0 est donc clos et peut être supprimé) ; le
    **point 1 (les boutons de données sans Siril) n'est PAS testable chez toi** —
    tu n'as pas de configuration sans Siril : le test est **délégué aux
    utilisateurs** qui voudront bien l'essayer (c'est écrit dans la doc comme un
    état daté, pas comme une promesse).
  - **③ LEÇONS REMONTÉES DANS CLAUDE.md** (ton accord explicite : « tu peux
    remonter les leçons dans claude.md ») : les **quatre leçons du jalon 77**
    sont écrites dans la section « Pièges » (deux conventions de `progression`
    dans `telechargeur.py` ; un banc qui isole l'environnement doit basculer les
    constantes d'OS ; un audit de géométrie doit ignorer les parents de taille
    0/1 px ; une donnée téléchargeable doit devenir utilisable dans la même
    session) ; la section « Portage Linux / macOS » décrit l'installateur macOS
    et la route commune aux deux packers.
  - **RELEASE v2.42.0 COMPLÉTÉE (29/09/2026, soir)** : le paquet macOS a été
    **AJOUTÉ** (aucun écrasement) à la release déjà publiée, et son
    `INSTALLATION.md` **réédité** (§ 1 avec la 3e ligne, **nouveau § 3 bis
    macOS**). État final vérifié sur l'API : 4 pièces — `avastack-setup-2.42.0.exe`
    (11 485 284 o), `avastack-setup-2.42.0-linux.tar.gz` (582 385 o),
    `avastack-setup-2.42.0-macos.tar.gz` (580 015 o,
    SHA-256 `8F070116B4744BA8AE75DD8A6170604ADE5A8E69C3B58C0CFEE141D738CDAA23`) et
    `INSTALLATION.md` (18 467 o) ; notes réécrites (résumé « sans Siril **et un
    installateur macOS** » + doc, 20 295 octets, UTF-8 intact). Commits de la
    passe : `4ec3ccd` (installateur macOS + banc 78 + leçons dans CLAUDE.md +
    docs) puis le commit de clôture mémoire — **arbre propre**, `master = origin`.

- **PASSE PRÉCÉDENTE (29/09/2026, matin) — AVAStack v2.42.0 : AVAStack SANS SIRIL
  — LES SPECTRES GAIA XP ET LA BASE DE PROFILS SPCC SE TÉLÉCHARGENT DEPUIS
  L'INTERFACE.** Ta question : « si tu traites ce point
  (bouton pour les 48 morceaux de spectres Gaia XP), AVAStack pourra fonctionner
  sans Siril, y compris pour l'astrométrie et les capteurs et filtres SPCC ? »
  **Jalon 77.** Réponse mesurée : **NON, ce point SEUL ne suffisait pas** — il
  manquait DEUX jeux de données (les spectres Gaia XP **et** la base de profils
  SPCC), et la passe les prend tous les deux :
  - **① SPECTRES GAIA XP** : la fonction de téléchargement existait
    (`telecharger_chunk_xpsamp`) mais n'était branchée à **AUCUNE** interface, et
    elle ne savait prendre qu'**un** morceau sans savoir lequel. Deux boutons :
    **« ⬇ Spectres (champ) »** ne prend QUE les 1 à 4 morceaux qui couvrent la
    cible (AD/Dec/champ° **saisis**, mêmes règles que l'astrométrie ; calcul par
    la géométrie HEALpix du projet, `pixels_cone` → `pixel_vers_chunk`) —
    **≈ 100-300 Mo au lieu des 10,6 Go** — et **« ⬇ les 48 »** couvre tout le
    ciel (usage itinérant). sha256 de Zenodo vérifiée **morceau par morceau**,
    reprise (Range/206) après coupure, jamais de re-téléchargement d'un fichier
    conforme.
  - **② BASE DE PROFILS SPCC** : elle n'était **LUE que chez Siril**
    (`%LOCALAPPDATA%\siril-spcc-database`) — la SPCC exigeait donc Siril installé
    ET une calibration lancée une fois. Bouton **« ⬇ Base SPCC »** : archive ZIP
    du dépôt public `siril-spcc-database` (GPLv3 ; API GitLab, sans compte et
    **sans nom de branche figé** dans le code — vérifié : 200, application/zip),
    ZIP vérifié (lisible, taille bornée, entrée piégée `../` **refusée**) puis
    extrait dans un dossier **temporaire**, et seules les cinq catégories lues
    (`mono_sensors`, `mono_filters`, `osc_sensors`, `osc_filters`, `wb_refs`) +
    les .json de référence sont posées : ce qui n'est pas une base n'entre pas.
    Base complète = rien à retélécharger ; archive incomplète = **refusée**
    (aucun profil à moitié posé).
  - **③ OÙ EST LA BASE** : `spcc_db.dossier_base()` suit désormais dossier choisi
    (`chemin_spcc`, bouton **📂 Dossier SPCC**) → copie d'AVAStack
    (`<config>/spcc-database`, cible du bouton) → emplacements de Siril par OS
    (ordre d'origine conservé : aucun utilisateur de Siril ne perd sa base). Un
    dossier VIDE ne masque jamais une base utilisable ailleurs.
  - **④ LA SPCC EST UTILISABLE DANS LA SESSION** : à la fin du transfert, la case
    SPCC redevient **cochable**, ses **cinq listes sont remplies** et sa sélection
    et sa sélection par défaut posée — sans ce renfort, une base téléchargée
    n'aurait servi à rien avant un redémarrage (vérifié au banc, c'est un des
    points testés).
  - **⑤ MISE EN PAGE** (règle v2.38.9) : **deux lignes de deux boutons** (jamais
    trois sur une ligne : `pack` abandonne en silence), une ligne d'état
    « Base SPCC » **bornée** (`wraplength`) qui DIT le dossier et le contenu, et
    les **quatre** boutons entrent dans le contrôle de géométrie **nommé** du
    banc du jalon 72. Un **seul** transfert à la fois : les quatre boutons sont
    neutralisés ensemble (l'état affiché ne peut pas mentir).
  - **⑥ Banc NEUF `bancs/_test_sans_siril_jalon77.py`** — **sans réseau** (serveur
    HTTP local qui sert fichiers et archives factices) et **sans Siril** :
    champ → morceaux confrontés à une référence **indépendante**
    (astropy-healpix, niveau 8), reprise/206 après effacement, sha256 non
    conforme refusée, archive piégée et archive incomplète refusées, ordre des
    dossiers de la base, puis **UI réelle** (transferts suivis, messages, SPCC
    utilisable sans redémarrage, géométrie des quatre boutons avec textes
    longs). **Rejoués sans modification : jalons 70 (données astro), 72
    (géométrie), 56 (astrométrie/catalogues/photométrie), 58 et 58 bis (SPCC),
    71, 73, 75, 76 — tous verts.**
  - **PROCHAINE ÉTAPE : ton test en séance réelle** — un clic sur chaque bouton
    (les trois ⬇ et 📂 Dossier SPCC), idéalement sur une machine **où Siril n'est
    pas installé** : attendu = la ligne d'état qui annonce chaque téléchargement
    et sa fin, la case SPCC qui devient cochable **sans redémarrer**, et une SPCC
    calculée sans Siril. **Repli si régression : v2.41.0.**
  - **INSTALLATEURS RECONSTRUITS EN v2.42.0** (règle : toute passe qui touche
    plus d'un fichier → rebuild AVANT le test réel) :
    `installer/windows/output/avastack-setup-2.42.0.exe` (11 485 284 o,
    SHA-256 `848E770D…1905F`) et
    `installer/linux/output/avastack-setup-2.42.0-linux.tar.gz` (582 385 o,
    SHA-256 `7016471b…3e4c1`). **Aucune release publiée** pour cette passe (à
    faire sur ta demande, avec `gh release create --notes-file`).
  - **CLÔTURE DE LA PASSE (29/09/2026) — v2.42.0 PUBLIÉE** : `git push`
    (`b7cb76a..9fb8a71`, `master` synchronisé), **release GitHub `v2.42.0`**
    (`https://github.com/darkvad/AVAStack/releases/tag/v2.42.0`, tag `v2.42.0`
    sur le commit `9fb8a71` — présent en local ET sur `origin`, marquée
    « Latest ») avec **trois pièces** : `avastack-setup-2.42.0.exe`
    (11 485 284 o), `avastack-setup-2.42.0-linux.tar.gz` (582 385 o) et
    `INSTALLATION.md` (15 804 o). **Les notes de la release = un court résumé
    « ce qui change » suivi de la doc d'installation complète** (méthode
    `gh release create --notes-file`, **jamais** un message en ligne de commande :
    au-delà de ~1 000 caractères la ligne est tronquée sous Windows — le fichier
    de notes est fabriqué hors dépôt en UTF-8 sans BOM). Commits de la session :
    `d8ec4f5` (code + doc + banc), `cf65e8f` (mémoire), `9fb8a71`
    (INSTALLATION.md en v2.42.0 : artéfacts, tailles, SHA-256, repli v2.41.0) —
    **arbre propre**.
  - **TRAÇABILITÉ DU TAG — TON CHOIX (29/09/2026) : NE PAS DÉPLACER LE TAG.** Le
    tag `v2.42.0` reste sur le commit `9fb8a71` (code + doc de l'application) ;
    l'installateur macOS, ajouté après, vit dans les commits `4ec3ccd`/`ca59086`/
    `d4dbdbb` et la release publiée porte bien les **trois** paquets.
    **La prochaine évolution de code prendra donc la version `v2.43.0`** (règle
    écrite dans CLAUDE.md, section « Installateur et tests réels » : on ne
    réécrit JAMAIS un tag publié — c'est le prochain changement de code qui porte
    la version suivante). Conséquence pratique pour la prochaine passe : dès
    qu'un fichier de code change, bump `AVASTACK_VERSION` à **2.43.0** +
    changelog, rebuild des **trois** packers, release `v2.43.0`.


## En attente / prochaine session

- **ÉTAT COMPACT POUR LA PROCHAINE SESSION (30/09/2026, clôture — jalons 85/86,
  v2.48.0 PUBLIÉE)** : **tout est livré, publié et poussé** — trois paquets
  reconstruits, `INSTALLATION.md` en v2.48.0, tag annoté `v2.48.0` sur `63ca10b`,
  release GitHub publiée, working tree propre. **Rien en attente de l'agent** :
  ce qui reste attend des ESSAIS.
  ① **ESSAI RÉEL D'ALAIN (le plus important)** : son rendu SHO avec **SON Linear
  Fit** (case « Recalage colorimétrique » cochée, mode « Gain + offset ») et la
  chaîne couleur après étirement ; le boost du rouge reste DÉCOCHÉ (il l'a
  refusé : le doré exagéré effaçait le bleu). Ses curseurs SCNR restent les siens :
  à SCNR 0,55 il reste 61 % de vert sur l'objet, à 0,75 seulement 5 %.
  ② **ESSAI RÉEL macOS (testeur)** : paquet `avastack-setup-2.48.0-macos.tar.gz` —
  « 📂 Dossier » (dossier surveillé) et « Charger un flat… » doivent répondre au
  PREMIER clic. Si ça résiste : **son `journal.txt`** décide (version de Tcl/Tk
  notée, et la **pile** du fil retenu pour toute ligne « gel de l'interface »).
  ③ **ESSAI RÉEL de la chaîne ⚡ par couche** (v2.46.0, toujours en attente) : un
  ⚡ traitement par couche en composition 3 rôles — la ligne d'état doit annoncer
  « 3 couche(s) en parallèle… » à l'étape gradient, et le résultat être celui
  d'avant.
  ④ **Piste à MESURER avant de coder** : `_on_source_choisie` boucle
  `root.update()` + `time.sleep(0.05)` jusqu'à 8 s pour attendre la fin d'une
  déconnexion caméra — piège connu sur macOS (boucle `update()` réentrante). Le
  guet de gel la désignera par sa pile si elle gêne.
  ⑤ Les attentes « **déléguées aux utilisateurs** » des blocs ci-dessous restent
  valables (boutons de données sans Siril : « ⬇ Gaia », « ⬇ Spectres (champ) »,
  « ⬇ Base SPCC »).
  **Prochaine passe de code : version `v2.49.0`** (règle : on ne réécrit jamais
  un tag publié — cf. CLAUDE.md).
- **ÉTAT COMPACT POUR UNE NOUVELLE SESSION (29/09/2026, clôture de soirée)** :
  **rien en attente de l'agent**. Dernière passe : **v2.42.0** — AVAStack ne
  dépend plus de Siril (spectres Gaia XP + base de profils SPCC téléchargeables,
  jalons 77) **et un installateur macOS existe** (jalon 78, écrit le 29/09/2026,
  **pas encore exécuté sur un Mac**). Release GitHub `v2.42.0` publiée (deux
  installateurs + la doc ; le paquet macOS y est ajouté). Le dépôt est **public**
  (licence MIT, titulaire = identifiant GitHub), un **`README.md`** de
  présentation existe à la racine, les documents publiés ne citent plus le
  mainteneur (règle écrite dans CLAUDE.md) et **les commentaires du
  code/garde-fous internes restent tels quels** (décision explicite). **Les deux
  tests réels restants ne sont pas chez toi** : voir les deux blocs ci-dessous.
- **DÉLÉGUÉ AUX UTILISATEURS (29/09/2026) — v2.42.0 : LES BOUTONS DE DONNÉES**
  (catalogues + spectres + base SPCC). **Ton retour : « les boutons sont là mais
  je n'ai aucune configuration sans Siril pour tester »** — normal : tes machines
  ont Siril, et c'est justement le cas « sans Siril » qu'il faut éprouver. À
  valider par quiconque a une machine **sans Siril** : ① « ⬇ Gaia » ;
  ② **« ⬇ Spectres (champ) »** avec AD/Dec/champ° saisis (attendu : la ligne
  d'état nomme les morceaux du champ, ≈ 100-300 Mo, et la ligne « Catalogues »
  passe à `n/48 morceaux`) ; ③ **« ⬇ les 48 »** (≈ 10,6 Go, reprise
  automatique) ; ④ **« ⬇ Base SPCC »** (quelques Mo) puis la **case SPCC** : elle
  doit devenir cochable **sans redémarrer** et ses listes se remplir. La
  mécanique est mesurée au banc (jalon 77) ; ce qui reste à voir, c'est le monde
  réel (réseau, dossiers, droits). Repli si régression : **installateur v2.41.0**.
- **VALIDÉ PAR TON ESSAI (29/09/2026) — v2.41.0 : bouton « RÉINITIALISER »**
  (release GitHub `v2.41.0`, tag `4b7efe8`). Tu as testé et validé : fin de cible
  → nouveau dossier → « Réinitialiser l'empilement » → « ▶ Démarrer » se comporte
  comme prévu (nouvelle cible uniquement). **Ce bloc est clos** — reste seulement,
  hérité des passes précédentes, à confirmer sur une trace écrite : l'étoile
  verte + le ″/px de l'astrométrie, et l'en-tête `AVASPCC` d'une sauvegarde.
- **NOUVEAU (28/09/2026, soir) — v2.40.0 : ASTROMÉTRIE SUR CAMÉRA TOURNÉE (OSC) ET
  SPCC COULEUR.** NGC 7023 **résolu sur tes brutes** (68-80 appariements, rms
  0,43-0,46 px, 0,4716″/px contre 0,4714″/px pour ASTAP), M31 non régressé ; la
  SPCC accepte un **capteur couleur (OSC)** avec son filtre LPF commun
  (`mode`, `reponses_osc`), et les gains par canal d'une source couleur passent
  par `LiveStacker.gains`. **Ton essai réel du 28/09 (soir) : « tout à l'air
  bon »** — session dossier OSC NGC 7023, ~40 brutes (détails en tête de
  fichier). Bancs NEUFS/rejoués : `_test_spcc_osc.py` (NEUF, 6 sections),
  `_test_spcc_jalon58.py`, `_test_solveur_reel_m31.py`, diag
  `bancs/_diag_osc_ngc7023.py` sur brutes réelles. **RELEASE GITHUB `v2.40.0`
  publiée** (`https://github.com/darkvad/AVAStack/releases/tag/v2.40.0`) : les
  **DEUX** installateurs (Windows 11 463 956 o, Linux 564 997 o) **ET** la
  nouvelle documentation `INSTALLATION.md` (installation rapide Windows/Linux,
  puis la préparation des données Siril/Gaia : catalogue astrométrique, 48
  morceaux de spectres, base de profils SPCC). Le dépôt étant **public** depuis
  le 29/09/2026, la release l'est aussi. L'installateur v2.39.0 n'a pas été
  construit (version dépassée) —
  **repli si régression : v2.38.11**. **CLÔTURE DU 28/09/2026 : rien en attente de
  ton côté** — les deux propositions de fin de session (bouton « ⬇ spectres » des
  48 morceaux Gaia XP, `INSTALLATION.md` embarqué dans les paquets) ont été
  **déclinées par toi** (« non, c'est bon ») : à ne pas reproposer spontanément.
- **PRÉCÉDENT (28/09/2026) — v2.39.0 VALIDÉE PAR TON ESSAI (« points 1, 2 et 3
  testés et validés »)** : les **trois barres de niveaux** de l'histogramme
  (Noir / Médian / Blanc), le **⏹/▶ geler-reprendre** de l'étirement auto (STF
  **et** VeraLux), le **sélecteur de bandes**, la **saturation par couleur R/V/B**
  et la **case « Échelle y linéaire (bande basse) »**. **Plus aucun point
  ouvert** : l'histogramme à deux bandes reste **tel quel** (ta décision du
  28/09, 176 px), et les quatre essais qui restaient en attente (`nftables`/NAS,
  chaîne BlurX, rendu BXT `--sn 0.3`, `--cameras`) sont **VALIDÉS par toi** — plus
  à reproposer. **Installateurs v2.39.0 non reconstruits** (à faire sur ta
  demande).
- **LEÇONS DU JALON 75 ÉCRITES DANS CLAUDE.md (28/09/2026, sur ta demande
  « mettre à jour les .md nécessaires (y compris claude) »)** — quatre leçons
  durables, section « Pièges (leçons du projet AVAStack) » : **① les barres de
  niveaux vivent APRÈS le moteur** (mini vs grand histogramme de SharpCap, et
  pourquoi : VeraLux n'a ni point noir ni point blanc → « les barres = les points
  de l'étirement » n'est possible que dans un seul moteur) ; **② une saturation
  par couleur doit viser une TEINTE** (la formule `c = Y + k·(c−Y)` change le
  canal PARTOUT et verdissait l'image quand on poussait « rouge ») ; **③ un
  panneau rafraîchi SEULEMENT par les données ne suit pas les gestes** (et la
  règle inverse : si le geste ne change pas la donnée, NE PAS recalculer —
  3,1 ms contre ~80 ms) ; **④ une échelle d'axe muette est un piège** (mesures
  log/linéaire consignées). Plus une note opérationnelle : les bancs se lancent
  avec l'interpréteur du VENV (`python` seul, sur ta machine, n'a pas numpy).
- **AUCUN DÉFAUT CONNU OUVERT** sur les v2.38.3 à v2.40.0 (livrées).
  **CONFIRMÉ PAR TES ESSAIS RÉELS (27-28/09/2026, Linux)** : astrométrie ✔, SPCC ✔,
  GraXpert ✔ (« astrométrie, spcc OK / GraXpert OK ») ; démarrage par le MENU et
  en terminal ✔ ; **v2.38.11 sous `nftables` actif : « c'est tout bon »** (elle
  s'ouvre, journalise, et DIT le NAS injoignable au lieu de bloquer).
  **VALIDÉS PAR TOI (28/09/2026) — À NE PLUS TE REPROPROPOSER** : les quatre
  essais que la clôture de la nuit laissait « en attente » sont **VALIDÉS** —
  `nftables`/NAS (les couches R/G/B sont lues normalement), **chaîne BlurX** avec
  le dossier de travail, **rendu BXT `--sn 0.3`**, et `--cameras`. **Plus RIEN
  n'est en attente de ton côté**, et il n'y a plus aucun point ouvert sur v2.39.0
  (ta décision du 28/09 : on GARDE l'histogramme à deux bandes **tel quel**,
  176 px — le point est clos, plus à trancher).

- Sujets OUVERTS (analyse close, décisions livrées), par ordre d'intérêt :
  - **CLOS PAR LA v2.38.3 — MOUCHETÉ BLEU DU FICHIER TRAITÉ** (piste BXT d'Alain,
    27/09/2026) : mesuré ×1,27-1,31 PARTOUT dans le champ (donc pas « les
    structures » ; le grain fin était au contraire réduit), cause = le volet
    « objets » de BXT (`--sn`, défaut 0,50 tant que rien n'est passé — options du
    CLI installé v2.6.9) ; son essai `--sn 0.3` mesuré (moucheté ×0,37 sur la
    chaîne externe, ×0,48 face à la vue live, σ/MAD du bleu 2,95 → 1,49) est
    **livré par défaut** (`--ss 0.5 --ash -0.3 --sn 0.3`). Détails : changelog
    v2.38.3, `_diag_mouchete_structures_jalon69.py`, CLAUDE.md.
  - **CLOS PAR LA v2.38.3 — TRAÇABILITÉ DES OUTILS EXTERNES** : `AVAOUTIL`,
    `AVACMDGX`, `AVACMDDN` et `AVACMDBX` sont écrits dans les fichiers issus du ⚡
    (sortie linéaire ET « tel que vu » de la vue traitée). Reste possible (non
    demandé) : écrire aussi un en-tête sur le « tel que vu » de la vue
    « empilement ».
  - **INSTALLATEUR LINUX / macOS (demande d'Alain, 27/09/2026 : « il faudra
    regarder comment faire un installateur pour Linux … et comment avoir les
    prérequis, ce ne sera pas les dll »)** — étude FAITE (27/09/2026), route
    TRANCHÉE par Alain : ① **SCRIPT + venv** — IMPLÉMENTÉE le 27/09/2026 (bloc
    en tête de ce fichier : `installer/linux/install_avastack.sh` →
    `~/.local/share/AVAStack`, venv, `pip install -r requirements.txt`, lanceur
    + `.desktop`) ; ② paquet
    **.deb** (Debian/Ubuntu) ; ③ **AppImage** (un seul fichier, embarque
    Python+Tk) ; ④ **Flatpak** (sandbox → ouvrir l'accès USB des caméras).
    **PRÉREQUIS LINUX (ce ne sont PAS des DLL)** : `python3` ≥ 3.10,
    `python3-venv`, **`python3-tk`** (Tkinter n'existe PAS en pip), `libgl1` et
    `libglib2.0-0` (roues `opencv-python`), `libusb-1.0-0`, plus les
    **règles udev** des caméras (accès USB sans root). Les bibliothèques
    constructeurs deviennent `libASICamera2.so`, `libPlayerOneCamera.so`,
    `libtoupcam.so`, `libSVBCameraSDK.so` (Linux) / `*.dylib` (macOS) — le code
    les cherche DÉJÀ sous ces noms (`compat.ZWO_DLL_NAME`,
    `cameras.sdk_loader.nom_bibliotheque`), et l'installateur Windows les
    embarque : même mécanisme côté Linux. **QHY : rien à faire** (le paquet pip
    `qhyccd` 0.1.3 fournit des roues `cp310-abi3` manylinux_2_34 + Windows ; PAS
    de roue macOS en revanche). **Outils externes** : GraXpert existe en Linux
    (zip) et macOS (dmg) ; le CLI BlurXTerminator (rc-astro) existe pour
    Windows/macOS/**Linux**. **macOS** : Python de python.org (Tk inclus) ou
    `brew install python-tk@3.14`, puis bundle `.app` + signature/notarisation
    Apple pour éviter le blocage Gatekeeper.
    - **À FAIRE QUAND LES `.so` ARRIVENT** (décision d'Alain, 27/09/2026 :
      « on va attendre que je récupère les .so » ; ordre de priorité = le sien :
      QHY, Player One, ToupTek, SVBony, ZWO). Fichiers attendus par le code (il
      les cherche DÉJÀ sous ces noms, `cameras/sdk_loader.nom_bibliotheque`) :
      ① **QHY = RIEN à télécharger** (la roue pip `qhyccd` manylinux embarque
      déjà `libqhyccd.so` ; repli `AVASTACK_QHY_DIR`) ; ② **Player One** :
      `libPlayerOneCamera.so` + `99-player_one_astronomy.rules`, et
      **`libusb-1.0-0`** (dépendance du .so, documentée par Player One —
      `apt install libusb-1.0-0`), ou le paquet Debian/Ubuntu
      `libplayeronecamera2t64` ; ③ **ToupTek** : `libtoupcam.so` (variante x64,
      glibc ≥ 2.14) + les règles udev du SDK ; ④ **SVBony** :
      `libSVBCameraSDK.so` + ses règles ; ⑤ **ZWO** : `libASICamera2.so` +
      **`asi.rules`** (`sudo install asi.rules /etc/udev/rules.d`), vendor id
      `03c3`, déjà écrit dans le fichier fourni. Dépôt : RACINE du projet (ou
      sous-dossier `sdk/`, ou `AVASTACK_*_DIR`). L'installateur Linux copiera les
      `*.so`/`*.dylib` avec l'application et posera les `*.rules` dans
      `/lib/udev/rules.d/` (une seule fois, sudo) — `*.so`/`*.dylib`/`*.rules`
      ajoutés au `.gitignore` le 27/09/2026 (comme `*.dll`).
  - **PISTE INDI (question d'Alain, 27/09/2026 : « les softs astro Linux
    utilisent les drivers INDI, ça remplacerait les .so ? »)** — vérifié :
    NON, les pilotes INDI **embarquent/lient eux-mêmes** le SDK constructeur
    (le dépôt `indi-3rdparty` redistribue des binaires **fournis par les
    constructeurs** — `indi_asi_ccd`, `indi_qhy_ccd`, `indi_playerone_ccd`,
    `indi_toupbase` pour la famille ToupTek, pilote SVBony dédié) ; mais sur
    Debian/Ubuntu c'est le PAQUET INDI qui apporte les `.so` **et** les règles
    udev → pour Alain, aucun téléchargement manuel. LÀ où INDI change vraiment
    la donne : faire d'AVAStack un **CLIENT INDI** (socket 7624, XML + BLOBs
    FITS ; `indipyclient` = pur Python, pip, aucune bibliothèque constructeur) →
    plus AUCUN `.so` ni `zwoasi`/`qhyccd` côté appli, et **une seule route pour
    les trois OS** et toutes les marques (indiserver local ou distant, comme
    Ekos « remote »). À programmer comme un **jalon à part** (nouvelle source
    d'acquisition, capacités lues sur les propriétés INDI du pilote au lieu de
    `capacites.py`, test matériel réel) — **PAS avant** le portage Linux avec
    les `.so`, qui réutilise tout l'existant.
  - **Coût du rendu pleine résolution quand le débruitage NLM live est actif**
    (son réglage) : ~7-8 s par nouvelle frame (le NLM pleine résolution pèse
    3,9-4,1 s à lui seul). Pistes : ne le refaire que sur nouvelle frame (déjà le
    cas via les caches), ou un bouton « rendu pleine résolution » à la demande,
    ou suspendre pendant l'acquisition et rafraîchir à l'arrêt.
  - **Grain GRIS résiduel** : la réduction du bruit chromatique ne touche PAS le
    grain de luminance (mesuré ×1,00) — seul le débruitage live (NLM, force 0,5)
    ou plus d'intégration le réduit. Piste : débruiteur épargnant les étoiles
    (cf. CLAUDE.md).
  - **Curseur « Rayon de référence » (v2.37.4)** : depuis la v2.37.5 il agit
    surtout sur le FOND et les objets lisses (la couleur des étoiles n'est plus
    lissée du tout). Son choix sera persisté : aucun code à changer. Halos RÉELS
    restants → BXT (`--ash`, −0,3 … −0,5, absent de la commande par défaut).
  - **Vérifié pendant la clôture** : la chaîne EXTERNE ne porte AUCUN fond cible
    à elle (aucun `target_bg` dans `avastack/external` ni `avastack/processing`
    hors du module VeraLux) — elle passe par le même `rendu_pleine_resolution`,
    donc elle bénéficie du correctif de fidélité de la v2.38.0.
- **CLOS par la passe en cours (v2.38.1, en attente du test réel d'Alain)** : le
  rendu pleine résolution ne se limite plus à la vue « empilement » — la vue
  « traitée » a SA source pleine résolution (le résultat du ⚡), et le défaut
  d'affichage que ce manque cachait est corrigé ✔ (banc `_test_pleine_res_traitee_jalon69.py`).
- **CLOS par cette session** : anneau de couleur des étoiles dans les fichiers
  (corrigé et validé par Alain) ✔ ; zoom sur la pleine résolution (livré et
  validé) ✔ ; « le fichier correspond à l'écran » pour un étirement VeraLux
  (écart 0 mesuré au banc jalon 68) ✔ ; PNG ⇄ FITS (hors de cause, 1/65535 près) ✔.
- **CLOS par les sessions précédentes** : cœur de M31 VALIDÉ par Alain sur
  l'appli v2.37.2 (« Le cœur n'est effectivement plus cramé ni plat ») ✔ ;
  **chaîne EXTERNE complète VALIDÉE** par lui ✔ ; débruitage NLM essayé sans
  dégradation du cœur ✔ ; profils SPCC re-sélectionnés
  (« les filtres sont bons ») ✔ ; option « normalisation commune des canaux »
  UTILISÉE et mesurée sur ses deux empilements M31 ✔ ; fond bleu des PNG/FITS
  clos ✔ ; halo des étoiles brillantes du jalon 65 ✔.

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
- Leçons ÉCRITES le 27/09/2026 (3e passe, v2.38.6) — section « Espace disque et
  fichiers de travail » : le message « N requested and M written » est celui de
  `numpy.ndarray.tofile()`, appelé par astropy pour écrire un FITS (donc =
  écriture partielle = volume plein, jamais un chemin invalide) ; `/tmp` sous
  Linux est souvent un tmpfs rempli par l'application elle-même ; toute écriture
  passe par `images.ecrire_fichier` (espace vérifié avant, `.part` renommé) et
  tout `mkdtemp` par `travail.creer_dossier` ; un plafond de taille se calcule
  sur l'espace RÉEL ; un contrôle ajouté dans un `try` large doit venir APRÈS
  ses dépendances (sinon `NameError` avalé = échec silencieux).
- Leçons ÉCRITES le 27/09/2026 (2e passe, v2.38.5) — section « Doc outils
  externes (CLI) → Détection de l'exécutable » : le nom du binaire d'un outil
  tiers CHANGE d'un OS à l'autre (`GraXpert-linux` sous Linux, bundle macOS) et
  la comparaison est sensible à la casse hors Windows ; l'INI DE SIRIL
  (`graxpert_path`, `catalogue_gaia_*`) est une source de détection déjà
  renseignée par l'utilisateur (et GKeyFile échappe les antislashs) ; une
  commande de REPLI persistée sans exécutable fige une détection ratée à vie →
  re-tester, ne pas persister, et DIRE l'état dans l'interface.
- Leçons ÉCRITES le 27/09/2026 (accord d'Alain : « met a jour claude ») — section
  « Pièges », 5 entrées : ① « ne rien passer » à un CLI tiers n'est PAS neutre, et
  la source qui fait foi est le `--help` de l'outil INSTALLÉ (BXT `--sn` resté à
  0,50, responsable du moucheté) → écrire les paramètres explicitement ET les
  consigner dans le fichier ; ② comparer deux images LINÉAIRES non étirées rend
  une corrélation aveugle (`auto_unflip` : +0,1085 contre +0,1212 → miroir non
  corrigé pendant quatre versions) → normaliser et ÉTIRER avant de corréler,
  marge large (+0,20) ; ③ deux fichiers du même champ peuvent ne pas être
  superposés (le ⚡ part d'un instantané plus récent que les fichiers déjà
  enregistrés) → vérifier orientation et alignement, et FIGER l'empilement pour un
  A/B propre ; ④ localiser un défaut par ÉCHELLE (1-2 px grain, 2-8 px texture
  d'outil, 8-30 px plaques) et par classe de fond AVANT d'accuser un maillon ;
  ⑤ le rapport σ/MAD décrit l'ALLURE du bruit (1,5 = grain, 3 = plaques), à
  mesurer sur des blocs de fond COMMUNS aux deux images. AJOUTÉE aussi : la
  section « Portage Linux / macOS — prérequis et installateur » (prérequis
  système, règles udev, noms des `.so`, paquets pip par OS, piste INDI).
- Leçons ÉCRITES le 25/09/2026 (au fil de la session, constats d'Alain) : un
  `imencode` attend du BGR (PNG/TIFF R-B permutés pendant des mois) ; un étirement
  log AMPLIFIE la couleur du fond (l'ancre de VeraLux) ; un gain MULTIPLICATIF
  amplifie le bruit du canal qu'il monte (le grain bleu vient de la SPCC) ; les
  mesures astro/photométrie/SPCC sont relancées par le WORKER (une case qui
  déco/recoche pose une DEMANDE servie même sans frame).
- Leçon PROPOSÉE le 25/09/2026, **sans urgence — à trancher quand tu le voudras,
  et elle ne bloque RIEN** : toute
  correction PRÉ-ÉTIREMENT ajoutée à la chaîne LIVE doit être vérifiée/mirrorée
  dans la chaîne de TRAITEMENT EXTERNE (et réciproquement) — les deux chaînes
  doivent produire le même rendu (constat : la SPCC y était déjà via les
  corrections de couleur, mais la neutralisation du fond et le bruit chromatique
  manquaient → v2.37.1).
- Leçons ÉCRITES le 26/09/2026 (accord d'Alain en clôture : « tu peux mettre à jour
  claude ») — section « Pièges », 4 entrées : ① **la couleur d'un pixel est un
  RAPPORT, pas un écart absolu** (le halo de couleur des étoiles venait de là) ;
  ② **toute échelle SPATIALE doit suivre la RÉSOLUTION** (aperçu ⇄ fichiers, avec
  le piège du plancher qui fausse un petit rayon) ; ③ **une correction en FIN de
  chaîne externe est invisible à l'outil qui la précède** (et l'option DÉDIÉE d'un
  outil doit être vérifiée — `--ash` de BXT, `0,00` par défaut — de même que ses
  sorties : miroir vertical, recadrage dans [0,1]) ; ④ **ré-énoncer honnêtement la
  propriété d'un banc quand la formule change**, mesurer une fidélité PAR RAPPORT
  à son plancher de mesure, et embarquer un TÉMOIN dans un banc qui doit prouver
  qu'il discrimine.
- Leçons ÉCRITES le 26/09/2026 (2ᵉ passe, accord d'Alain en clôture : « Oui,
  ajoute les 5 entrées ») — section « Pièges », 5 entrées : ① **une variable
  Tkinter ne peut être LUE que depuis le thread d'interface** (l'état partagé vit
  dans un attribut Python ; constat : la sauvegarde ne sortait plus) ; ② **après un
  traitement SÉLECTIF, un σ mesure la queue et non le niveau** → mesurer au MAD
  (deux bancs donnaient un faux échec) ; ③ **une scène de banc doit reproduire le
  MÉCANISME du défaut** (une étoile écrêtée à 1,0 = cœur blanc = aucun anneau, le
  témoin ne discriminait rien) ; ④ **les diagnostics du moteur VeraLux en logD
  imposé affichent une ancre 0,000000 : artefact** (et la comparaison bit à bit
  exige le même `target_bg`) ; ⑤ **une option « l'écran = le fichier » doit être
  verrouillée par une égalité exigée, pas une tolérance** — c'est cette assertion
  qui a révélé le fond cible non transmis. Reste PROPOSÉE (25/09/2026, sans
  urgence, ne bloque rien) : la
  parité des corrections pré-étirement entre chaîne LIVE et chaîne EXTERNE.
- Leçons ÉCRITES le 28/09/2026 (jalon 75, v2.39.0) — section « Pièges », 4 entrées :
  ① **les barres de niveaux vivent APRÈS le moteur d'étirement** (comme le mini de
  SharpCap, elles n'agissent que sur l'affichage ; « les barres = les points de
  l'étirement » est IMPOSSIBLE, VeraLux n'a ni point noir ni point blanc) ;
  ② **un curseur de saturation par couleur doit viser une TEINTE** (la première
  formule, par canal, verdissait l'image) ; ③ **un panneau rafraîchi seulement par
  les données ne suit pas les gestes** (corollaire de la leçon « les mesures sont
  relancées par le WORKER ») ; ④ **une échelle d'axe non dite est un piège**
  (log/linéaire, choisie par MESURE et DITE dans la ligne d'état).
- Leçons ÉCRITES le 28/09/2026 (2ᵉ passe, v2.40.0) — section « Pièges », 2 entrées :
  ① **la zone de catalogue de l'astrométrie est un DISQUE, pas un rectangle — et
  `N_CAT_MAX` passe APRÈS la sélection** (le rectangle suppose que l'axe X de la
  caméra suit les AD : sur une caméra tournée il ne gardait que 43 % des étoiles
  de l'image et gardait une bande HORS image ; le juge d'un champ large est le rms
  sur les MÊMES étoiles, jamais l'écart point par point des deux WCS) ; ② **la
  SPCC n'est PAS réservée au mono multi-bandes** (un capteur couleur = trois
  entrées + un filtre LPF COMMUN ; le nom du capteur est AMBIGU — « Sony IMX585 »
  est dans les deux listes — c'est l'interface qui tranche ; et le défaut d'un
  filtre OSC est la référence « sans filtre », jamais un vrai LPF en silence).
  Plus AUCUNE leçon en attente.
- **Leçons du 29/09/2026 (jalon 77, v2.42.0) — ÉCRITES dans CLAUDE.md le même
  jour, sur ton accord explicite** (« tu peux remonter les leçons dans
  claude.md »), section « Pièges » : ① deux conventions de rappel `progression`
  cohabitent dans `telechargeur.py` (`(nom, fraction)` et `(fraction)`) — dire
  laquelle on prend, l'inversion des arguments n'ayant été vue que par le banc ;
  ② **un banc qui isole l'environnement doit aussi basculer les constantes d'OS**
  (`%APPDATA%` reste sinon dans le vrai dossier de configuration — le banc lisait
  le VRAI `config.json`) ; ③ **l'audit de géométrie doit ignorer les parents de
  taille 0/1 px** (une configuration VIDE laisse un sas de panedwindow à 1 px :
  29 widgets « écrasés » dès la construction, **préexistant**, vérifié sur un
  worktree de HEAD) ; ④ **une donnée téléchargeable doit devenir utilisable dans
  la session** (case/combos rafraîchis à la fin du transfert), sinon le
  téléchargement ne sert à rien avant un redémarrage. La section « Portage
  Linux / macOS » y décrit désormais l'installateur macOS et la route commune aux
  deux packers.

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
- **Outils astro locaux vérifiés (22/09/2026)** : Siril 1.4.4
  (catalogues : chunks Gaia XP dans `%LOCALAPPDATA%\Siril\...`,
  base SPCC capteurs/filtres dans `siril-spcc-database`) ; ASTAP
  (`C:\Program Files\astap`, astap_cli.exe + base D80 Gaia DR3 1,24 Go)
  ; PAS d'astrometry.net/ANSVR.
- **Machine LINUX d'Alain (fait du 29/09/2026, à sa demande)** : **Ubuntu 26.04
  LTS** — l'**installateur Linux d'AVAStack y a été exécuté PLUSIEURS FOIS**
  (installation, prérequis, venv, dépendances, lancement) et l'application y est
  employée : l'astrométrie, la SPCC et GraXpert y sont validés (constats des 27 et
  28/09/2026). **La documentation disait le contraire** (« pas encore exécuté sur
  une vraie machine Linux ») : corrigé dans `INSTALLATION.md` (§ 3 et § 8),
  `installer/README.md` et dans la release `v2.41.0` (notes + pièce jointe).
  Restent à faire : machine **vierge** (sans Python) et **test matériel caméras**
  sous Linux (`--cameras`).


## Pièges récents (rappels opérationnels)

- **Leçons du jalon 78 (installateur macOS, v2.42.0)** :
  - **Un installateur d'un OS qu'on ne peut PAS exécuter se vérifie par ce qui
    est vérifiable** : ① `bash -n` (analyse syntaxique — le bash de Git Bash
    suffit) ; ② **exécution réelle des garde-fous** (le script doit REFUSER de
    s'installer hors macOS et `--aide` doit répondre : deux tests lancés depuis
    Windows) ; ③ un banc qui contrôle le CONTENU du paquet (racine unique,
    fichiers indispensables, modes, fins de ligne, aucun binaire). Et l'état est
    écrit **daté** partout (« écrit le 29/09/2026, pas encore exécuté sur un
    Mac »), jamais déguisé en test réussi.
  - **Charger un script pour tester ses fonctions sans exécuter son `main`** :
    `grep -v '^main "\$@"' script.sh > copie.sh` puis `. copie.sh` — un simple
    `sed '$d'` ne suffit pas quand le fichier se termine par une ligne vide (le
    `main` s'exécute et le test s'arrête). Et **le script chargé active
    `set -euo pipefail`** : remettre `set +e` juste après, sinon la première
    vérification « qui doit échouer » (le refus hors macOS) arrête tout.
  - **Sous macOS, l'application doit être CLIQUABLE sans droits administrateur** :
    un bundle minimal `~/Applications/AVAStack.app` (Info.plist + exécutable
    shell qui lance le venv) suffit — **ne pas embarquer Python ni le venv** dans
    le bundle, sinon chaque mise à jour exige de refaire le paquet. Le bundle
    n'étant pas signé, prévenir : clic droit → « Ouvrir », ou
    `xattr -dr com.apple.quarantine`.

- **Leçons du jalon 77 (v2.42.0)** :
  - **DEUX conventions de `progression` cohabitent dans `telechargeur.py`** :
    `progression(nom, fraction)` pour `verifier_ou_telecharger`/`chunks` et
    `progression(fraction)` pour `telecharger` (bas niveau) — l'adaptation se fait
    à UN SEUL endroit, et l'inversion des deux arguments a été attrapée par le
    banc du jalon 77 (le « nom » arrivait comme `float`, la « fraction » comme
    chaîne). Toute nouvelle fonction qui annonce une progression doit dire
    laquelle des deux elle prend.
  - **Un banc qui isole l'environnement ne peut pas se contenter d'`os.environ`
    sous Windows** : `config.dossier_config()` lit `%APPDATA%` quand
    `IS_WINDOWS` est vrai — le banc du jalon 77 lisait donc le **VRAI**
    `config.json` (et la case SPCC d'Alain, cochée, faisait échouer un test
    d'interface). Il faut basculer les constantes d'OS comme le fait le banc du
    jalon 70 (`simule_linux()`), et **retirer `APPDATA` de l'environnement du
    banc**.
  - **`winfo_ismapped()` n'a de sens que sur une fenêtre DÉJÀ dimensionnée** :
    avec une configuration VIDE (départ après effacement du `config.json`), un
    **sas du panedwindow interne reste à 1 px** → 29 widgets « gérés mais non
    affichés » **dès la construction**, et c'est **préexistant** (mesuré sur un
    `git worktree` de HEAD, avant les changements du jalon 77). Un audit de
    géométrie doit donc ignorer les parents de taille 0/1 px (et le contrôle de
    référence reste le banc du jalon 72, qui tourne avec la vraie configuration).
  - **Un parent de widget peut être MAPPÉ et 1×1 pendant quelques centaines de
    millisecondes** après un `deiconify()` : laisser la mise en page se terminer
    (plusieurs `update()`) avant de mesurer la géométrie, sinon on mesure du
    bruit.

- **Leçons du jalon 76 (v2.41.0) REMONTÉES dans CLAUDE.md** (accord d'Alain,
  28/09/2026) — section « Pièges », 4 entrées : ① une demande de l'interface se
  sert en TÊTE de boucle du worker (jamais dans le chemin d'une donnée) ; ② un
  objet de source porte l'état de sa configuration (comparer/refermer ; indices
  d'astrométrie EFFACÉS quand la cible change, `effacer_indices`) ; ③ une source
  de fichiers ne se lit pas « pour rien » en pause (+ deux
  `Thread(_worker).start()` dans la même méthode = deux workers) ; ④ mesurer
  « AVANT » sur un `git worktree` HEAD pour prouver qu'un banc discrimine.
- **LIMITE QHY (toujours valable)** : après « ■ Arrêter », relancer
  l'appli — le binding qhyccd n'expose AUCUNE libération du SDK (état
  irréinitialisable dans le process) ; le banc QHY l'annonce et conseille
  fermer + relancer.
- Entry/Combobox/`var.get()` Tkinter interdits hors thread principal —
  lire les widgets DANS Tk puis passer les valeurs au worker (bouchons
  `_Val` dans l'appli) ; toute contrôle `_on_*` finit par
  `_refresh_preview()`, les `_sync_*_vue` ne touchent qu'à l'ÉTAT.
- **Installateur à REBUILDER avant tout test réel dès que la passe de code
  touche PLUS d'un ou deux fichiers** (`powershell -NoProfile
  -ExecutionPolicy Bypass -File installer\windows\build_avastack.ps1`) —
  à la charge de l'agent, sans qu'Alain ait à le demander.
- **Inno Setup 6 est dans `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`** (PAS
  dans `Program Files`) : `build_avastack.ps1` y cherche en premier et le trouve.
  Un `Test-Path` sur `Program Files` seul ne prouve donc RIEN — leçon du
  28/09/2026 : l'absence d'ISCC a été annoncée à tort AVANT de lancer le script
  (il se construit en 9 s, l'artefact fait ~11,5 Mo).
- **RELEASES GITHUB : `gh release create vX.Y.Z --title <titre> --notes-file <fichier>
  --target master <les 2 installateurs> INSTALLATION.md`** — `gh` est installé et
  authentifié sur ce poste (compte `darkvad`, portée `repo` ; **dépôt PUBLIC
  depuis le 29/09/2026** — la release l'est donc aussi). **Les notes de la release SONT la doc
  d'installation** (`INSTALLATION.md` précédé d'un court résumé « ce qui
  change ») : elle se lit directement sur la page de la release, et le même
  fichier est joint en pièce. Les installateurs des versions précédentes ne
  sont PAS dans la release (dossier `output/` ignoré par git) : le repli reste
  sur la machine.
- **LA LIGNE DE COMMANDE WINDOWS EST TRONQUÉE au-delà d'environ 1 000
  caractères** (constaté le 28/09/2026, deux fois) : un `git commit -m "…"`
  de plusieurs milliers de caractères part TRONQUÉ et, avec une chaîne non
  fermée, sème le doute sur l'état du dépôt. Pour tout message long, passer par
  un FICHIER (`git commit -F`, `gh release create --notes-file`) — et vérifier
  après coup (`git log -1`, `git status`) qu'aucun commit partiel n'est né.

## Clôtures précédentes

- 28/09/2026 (v2.40.0) : SESSION « ASTROMÉTRIE SUR CAMÉRA TOURNÉE (NGC 7023
  RÉSOLU) ET SPCC OUVERTE AU CAPTEUR COULEUR » — tes deux constats OSC du jour,
  **tous deux fondés** : ① la zone de catalogue du solveur était un RECTANGLE
  (faux dès que la caméra est tournée : il ne gardait que 43 % des étoiles de
  l'image ET gardait une bande HORS image, là où sont les plus brillantes) →
  **disque du champ réel**, et `N_CAT_MAX` appliqué **après** la sélection :
  **NGC 7023 résolu sur tes brutes** (68-80 appariements, rms 0,43-0,46 px,
  0,4716″/px contre 0,4714″/px pour ASTAP) et **M31 non régressé** (112/115
  appariements contre 86/70 avant) ; ② la SPCC accepte un **capteur COULEUR
  (OSC)** — trois canaux + un filtre LPF COMMUN de la base Siril, `mode`,
  `reponses_osc`, gains par canal appliqués par `LiveStacker.gains` — banc NEUF
  `_test_spcc_osc.py` (6 sections, tout au vert). **Verdict réel (ton essai du
  soir) : « tout à l'air bon »** (session dossier OSC NGC 7023, ~40 brutes).
  **Installateur v2.40.0 construit à la clôture.** Repli si régression : v2.38.11.
- 27/09/2026 (v2.38.2 puis v2.38.3) : SESSION « LE FICHIER DU ⚡ ÉTAIT À
  L'ENVERS, ET LE MOUCHETÉ BLEU VIENT DE BXT », **mesures validées par Alain**
  (« image magnifique avec -sn 0.3 ») : ① son test de la v2.38.1 (« le fichier
  traité a plus de bruit bleu que le stack ») MESURÉ — le grain est au contraire
  MEILLEUR (×0,73) mais le moucheté 2-8 px est ×1,28 ; ② en mesurant, découverte
  que le fichier du ⚡ était en **MIROIR VERTICAL** (v2.373, v2.38.0, v2.38.1),
  cause `auto_unflip` (corrélation aveugle sur images linéaires : +0,1085 contre
  +0,1212) → **v2.38.2** (comparaison étirée/normalisée, marge +0,20, banc
  `_test_unflip_jalon69.py`) — vérifié ensuite sur son fichier v2.38.2 (bon sens) ;
  ③ sa piste BXT confirmée : `--sn` (volet objets) restait au défaut 0,50 →
  son essai `--sn 0.3` mesuré (moucheté 2-8 px ×0,37, excursions 4,15 % → 0,72 %,
  σ/MAD 2,95 → 1,49) → **v2.38.3** (paramètres BXT explicites par défaut :
  `--ss 0.5 --ash -0.3 --sn 0.3` ; traçabilité `AVAOUTIL`/`AVACMDGX`/`AVACMDDN`/
  `AVACMDBX` dans les fichiers issus du ⚡ ; encadré LISEZMOI) ; ④ au passage :
  installateur Linux/macOS ÉTUDIÉ (prérequis, règles udev, noms des `.so`, piste
  INDI) et consigné dans AVANCEMENT + CLAUDE.md (5 leçons + la section portage) ;
  ⑤ son PNG est identique au FITS (écart max 1/65535, même sens, canaux dans le
  bon ordre). Repli si régression : v2.38.2.
- 26/09/2026 (v2.38.0, ce54c55) : SESSION « ANNEAU DE COULEUR CORRIGÉ ET
  ZOOM PLEINE RÉSOLUTION », **VALIDÉE PAR ALAIN (« C'est OK, on valide »)** —
  installateur 2.38.0 installé et testé le jour même. Livré, sur sa décision
  (« b) et c), car sur l'écran je veux pouvoir zoomer sur l'image pleine
  résolution ») : ① l'enquête du
  jalon 66 (PNG hors de cause ; écart écran ⇄ fichier dû à la RÉSOLUTION ; anneau
  fabriqué par la chroma NR) ; ② le CORRECTIF par POIDS DE STRUCTURE
  (`couleurs._poids_structure`, v2.37.5 : la correction est éteinte là où la
  luminance s'écarte de son voisinage lissé) — anneau 4,63 → 2,00 sur son
  empilement, grain coloré du fond encore retiré à 76 % ; ③ une TROISIÈME cause
  écran ⇄ fichier trouvée et corrigée : `rendu_pleine_resolution` ne transmettait
  pas le FOND CIBLE au moteur quand le logD était déjà résolu (fichier rendu avec
  0,20 au lieu de 0,16 : fond final 0,197 contre 0,159, écart moyen 9,6 niveaux) ;
  ④ l'option « Rendu pleine résolution (zoom fidèle) » : la chaîne d'affichage
  tourne sur l'empilement COMPLET, l'écran montre ce que le fichier contiendra et
  le zoom recadre de vrais pixels (1:1 ; coût ×4,3 mesuré, décocher libère la
  copie). Bancs : `_test_chroma_structure_jalon67.py` et
  `_test_zoom_pleine_res_jalon68.py` (NOUVEAUX) ; 32 bancs rejoués, TOUS PASSENT.
  Trois mesures de bancs 63/65 adaptées et documentées (grain au MAD, seuil du
  résidu de luminance, assertion du rayon inversée). Piège : une variable Tk lue
  depuis un thread de travail lève `RuntimeError: main thread is not in main loop`
  — corrigé pendant la passe (l'état vit dans un attribut Python). **5 leçons
  écrites dans CLAUDE.md** (accord d'Alain en clôture). Installateur 2.38.0
  reconstruit. Repli si régression : v2.37.5, puis v2.37.4 (9927539).

- 26/09/2026 (v2.37.4, 9927539) : SESSION « LE HALO DE COULEUR DES ÉTOILES »,
  VALIDÉE PAR ALAIN (« on a plus le super halo de couleur, ça c'est bien » ;
  essais du curseur de rayon OK). Livré : ① la CAUSE — la réduction de bruit
  chromatique (v2.37.0) lissait une chroma ABSOLUE, donc autour d'une étoile le
  flou mélangeait la couleur du cœur avec celle du ciel et la déposait sur les
  ailes faibles (mesuré sur son M31 : R/B d'une couronne 1,30 → 0,44 sur une
  étoile bleue, R −51 %, B +44 %), et le correctif qui lisse désormais le RAPPORT
  de couleur (échelle = min(luminance du pixel, sa version lissée)) ; ② le RAYON
  qui SUIT LA RÉSOLUTION (`couleurs.rayon_chroma_apercu` +
  `DisplayProcessor.vl_chroma_rayon`) — l'aperçu montrait un halo 2,4× plus large
  que les fichiers ; ③ le CURSEUR « Rayon de référence » (0,5 à 8 px, v2.37.4,
  à sa demande pour ses essais en visu), transporté jusqu'à la chaîne EXTERNE
  (job 14 → 15 éléments) et persistant (`vl_chroma_rayon_ref`). Effets mesurés :
  grain coloré du fond ×0,17 (bénéfice conservé), écart RENDU du halo ≤ 1,9 point
  de % du pic contre 24,5 avant. Bancs : `_test_chroma_halo_jalon65.py` (NOUVEAU,
  avec TÉMOIN de l'ancienne formule pour prouver qu'il discrimine) +
  `_test_chroma_nr_jalon63.py` (borne haute documentée) + `_test_dn_jalon7.py`
  (job 15 éléments) ; 19 bancs rejoués, TOUS PASSENT. Installateur 2.37.4
  reconstruit (le banc est ajouté au .iss). Constats annexes : BXT rend ses
  sorties en MIROIR VERTICAL et recadrées dans [0,1], et son réglage de halos
  `--ash` vaut 0,00 par défaut (donc inactif) — laissé à Alain pour les halos
  RÉELS. Leçons de méthode ÉCRITES dans CLAUDE.md (4 entrées, accord d'Alain).
  Repli si régression : v2.37.2 (5545a9c).

- 25/09/2026 (v2.37.2, 5545a9c ; puis v2.37.1, db0e870) : DEUX SESSIONS VALIDÉES
  PAR ALAIN — « le cœur cramé » (CAUSE : l'étirement COUPAIT l'image vivante à 1,0
  alors que l'empilement vit à l'échelle mémoire 13-18 → cœur entier sur une seule
  valeur, disque plat ; correctif `veralux.normaliser_lin()`, facteur GLOBAL, règle
  des sauvegardes linéaires, appliqué à `etirer()` et à la vue « tel que vu » — au
  passage `np.clip(out=img)` écrasait le tableau de l'appelant) et « fond bleu →
  grain bleu → chaîne externe » (PNG/TIFF sans permutation R-B ; neutralisation de
  la couleur du fond avant étirement, défaut coché ; réduction du bruit
  chromatique opt-in, force = curseur « Couleur live » ; mesures SPCC/photométrie
  relançables en fin de stack ; cases couleur à rendu immédiat ; les deux
  corrections pré-étirement INTÉGRÉES à la chaîne EXTERNE, validée par lui dans la
  foulée). Bancs neufs `_test_coeur_crame_jalon64.py`, `_test_chroma_nr_jalon63.py`.
  Repli : v2.36.0 (5f91ae0).
- 21/09/2026 (v2.23.3, aca5ca5) : jalon 55 VALIDÉ PAR ALAIN en réel
  (M31 RGB, mode dossier) — gains R/G/B temps réel, image équilibrée.
  Rappel opérationnel : équilibrage auto OU Linear Fit re-normalisent les
  canaux → gains manuels sans effet tant que l'un des deux est actif ;
  pour réchauffer les tons, MONTER R. Repli si régression : v2.22.0
  (225f026).
- 20/09/2026 : TOUTES les validations matérielles (QHY miniPC, Player
  One, SVBONY, roue, TEC, cadence 39-46, ergonomie 47-48) CLOS — verdicts
  d'Alain ; bancs `_diag_camera_*.py` conservés pour diagnostic futur.
- Crash OpenCV 5/OpenCL au teardown (`cv2.ocl.setUseOpenCL(False)`) ;
  tests `ui.App` hermétiques (`ui.CONFIG = {}` + sauver_config
  intercepté) ; images de tests bruitées (sinon 0 étoile).
- Ne JAMAIS mélanger grid et pack dans le même conteneur Tk (attrapé par
  le test UI du banc POA : `_tkinter.TclError` « grid is already
  managing its content windows »).
- SDK natif : chargement UNE fois par process ; crash natif non
  rattrapable → tracer chaque étape dans un fichier ; vérifier
  l'identité des fichiers réellement chargés AVANT d'interpréter un
  plantage (les bancs affichent DLL + module + dates).
- PIÈGE LANCEMENT : `python3` ≠ venv — toujours `python AVAStack.py`.
- Ordre de la chaîne (Alain, 16/09/2026) : recadrage → gradient →
  débruitage → netteté → étirement. Débruitage : code gelé, cases
  décochées (décision du 16/09/2026) — ne pas retoucher sans nouvelle
  demande ; défauts des traitements confirmés (live = désactivé, NLM,
  force 0,5 ; externe = désactivé, GraXpert IA, force 0,5).
