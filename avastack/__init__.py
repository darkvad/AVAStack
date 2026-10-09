# -*- coding: utf-8 -*-
"""Package AVAStack — live stacking (empilement temps réel).

Structure (refactoring v2.0.0, depuis le fichier unique AstroLiveStack.py /
AVAStack.py) :
  avastack.compat       — constantes multiplateforme (Windows/Linux/macOS)
  avastack.config       — persistance config.json
  avastack.journal      — journal d'exécution (journal.txt) : « si l'appli ne démarre pas, elle le dit »
  avastack.travail      — dossier de travail, espace disque, écriture atomique
  avastack.siril_ini    — lecture de l'ini de Siril (outils + catalogues Gaia)
  avastack.images       — E/S image, débayerisation, utilitaires outils externes
  avastack.cameras      — sources d'images (simulée, dossier, OpenCV, ZWO)
  avastack.processing   — calibration, alignement, empilement, affichage
  avastack.core         — worker d'acquisition (mixin) + config (WorkerConfig)
  avastack.external     — détection + enchaînement des outils CLI (GraXpert/BXT)
  avastack.ui           — interface Tkinter
Le point d'entrée reste AVAStack.py à la racine (python AVAStack.py),
ou python -m avastack.
"""

AVASTACK_VERSION = "2.69.1"

# --- Changelog (entrée la plus récente en premier) --------------------------
# v2.69.1 : ALIGNEMENT — LE RAFFINEMENT SOUS-PIXEL PASSE À PORTE LARGE, ET RIEN
#   N'EST RETENU SANS ÊTRE VÉRIFIÉ SUR LES ÉTOILES (jalon 117b). Défaut mesuré le
#   09/10/2026 sur le jeu M31 deux nuits (176,2°) : sur les frames RETOURNÉES la
#   matrice rendue par `compute` laissait un résidu d'étoiles de 0,96 à 2,38 px
#   (contre 0,14-0,15 px pour les frames de la même nuit), et sur le fichier
#   livré « save as seen » le canal R était décalé de (−1,30, −1,33) px par
#   rapport au VERT → un ÉCHO ROUGE autour de chaque étoile. DEUX causes
#   racines : ① `_raffiner_centroides` (jalon 57) était GATED par un appariement
#   mutuel serré (≤ 1,5 px) calculé avec la matrice BRUTE — précisément là où
#   l'erreur dépasse 1,5 px il ne trouvait que 0-4 couples et ne corrigeait
#   RIEN ; ② rien ne VÉRIFIAIT la matrice retenue sur les centroïdes d'étoiles
#   (le seul garde-fou était le consensus RANSAC à 2 px sur les points ORB).
#   CORRECTIF : la porte d'appariement devient LARGE puis RESSERRÉE par
#   itérations (`RAFFIN_RAYONS` = 4,0 → 1,5 → 1,0 px), chaque passage ré-estimant
#   une similitude (RANSAC robuste puis LMEDS sur ses inliers) à partir du
#   précédent ; chaque matrice candidate est VÉRIFIÉE sur les centroïdes
#   (`_verif_centroides` : nombre d'appariements mutuels à 2,5 px et résidu
#   MÉDIAN), et seule une candidate de résidu MEILLEUR que la matrice d'entrée
#   est GARDÉE — jamais de régression (la matrice d'entrée est rendue INCHANGÉE
#   sinon). Nouveaux helpers `_appariements_mutuels`, `_reestimer_centroides`,
#   `_verif_centroides`. MESURÉ : une matrice à 2,83 px (0 appariement sous
#   1,5 px, 31 sous 4 px) est ramenée à < 0,01 px ; cas RETOURNÉ 176° corrigé à
#   0,02 px ; décalage sous-pixel 0,573 px ramené à 0,016 px (non-régression du
#   jalon 57). Banc neuf `bancs/_test_align_raffin_jalon117.py` (5 sections).
# v2.69.0 : RECADRAGE — LE CADRE DEVIENT LE PLUS GRAND RECTANGLE AXIAL INSCRIT
#   (jalon 117a). Défaut mesuré le 09/10/2026 sur le test réel M31 LRGB (deux
#   nuits à 176,2°) : `cadre_intersection` (processing/stacking.py) rendait la
#   BOÎTE ENGLOBANTE du polygone d'intersection des zones couvertes. Or, pour
#   une rotation de quelques degrés, ce polygone vaut ~96 % de la frame mais ses
#   extrêmes tombent au MILIEU des côtés → la boîte englobante vaut la PLEINE
#   image : mesuré `cadre` = (3, 3, 2176, 3852) sur 3856×2180 (seuls 23×17 px
#   retirés du PNG livré). Les coins NON couverts restaient visibles, avec une
#   teinte différente ET différente d'un coin à l'autre (c'est le recouvrement
#   des frames, pas la vignette) → le retrait de gradient échouait derrière
#   (GraXpert ne peut pas modéliser quatre coins peints chacun autrement).
#   CORRECTIF : `cadre_intersection` rend désormais le PLUS GRAND RECTANGLE
#   AXIAL INSCRIT dans le polygone (leçon « -framing=min » de Siril), calculé
#   EXACTEMENT sur une grille bornée grâce à la structure du polygone CONVEXE :
#   sur une bande [x0, x1] la hauteur disponible vaut min(hi(x0), hi(x1)) −
#   max(lo(x0), lo(x1)) (`hi` concave, `lo` convexe → les extrêmes tombent AUX
#   EXTRÉMITÉS ; aucune heuristique de pixels). Nouveaux helpers
#   `plus_grand_rect_inscrit` (aire maximale, en flottants) et
#   `_coupes_verticales` (coupe verticale du polygone) ; constante `_CROP_PAS_MAX`
#   (1 024 abscisses au plus — pas ≤ ~4 px sur une brute de 3 856 px). Le
#   résultat est arrondi ENTRANT aux pixels, puis `_MARGE_CROP` (3 px) est
#   retirée comme avant : le banc historique n'a pas bougé. Mesuré sur le jeu
#   réel : insets (62, 137) px → 3 732×1 906 px, 84,6 % de la frame conservés.
#   Vaut pour `LiveStacker` ET `CompositeStacker` (même appel). Banc neuf
#   `bancs/_test_crop_inscrit_jalon117.py` : rotation ⇒ coins retirés + rectangle
#   réellement inscrit (ses 4 coins sont dans le polygone), coïncidence avec un
#   balayage brute-force 1 px INDÉPENDANT (100,0 % de la vérité mesurée), cas
#   « diamant » (carré tourné de 45°, optimum HORS sommet) à l'aire théorique
#   s²/2, non-régression identité/translations, garde-fous et intégration.
# v2.68.0 : ALIGNEMENT — LES FRAMES D'UNE AUTRE NUIT (retournement ~176°) SONT
#   ENFIN EMPILÉES (jalon 116). Test réel d'Alain du 09/10/2026 (M31 LRGB :
#   L du 13/09 + R/G/B du 22-23/09, 210 frames) : 130 empilées, 80 NON ALIGNÉES
#   (L: 9 · R: 39 · G: 45 · B: 37), avec des DOUBLONS ROUGES, une trace sombre
#   et des biseaux noirs. Diagnostic HORS-LIGNE sur les archives de frames
#   (aucune ligne de code touchée dans cette session-là) : l'écart entre les
#   deux nuits vaut 176,2° — donc DANS la tolérance du retournement (180° ± 10°)
#   —, la géométrie n'était pas en cause, et les compteurs sont reproduits
#   EXACTEMENT par rejeu. Budget : côté A = 111 frames → toutes empilées ; côté
#   B (60 L + 39 RGB) = 99 frames → 19 empilées, 80 refusées. Les dossiers R/G/B
#   contiennent EUX-MÊMES les deux côtés du méridien (26 % des frames). DEUX
#   causes cumulées, mesurées :
#   - ① L'ORB TRAVAILLAIT DANS LE DOMAINE DE LA RÉFÉRENCE : `alignment._norm8`
#     étirait la frame avec les bornes de la RÉFÉRENCE, alors que le fond d'une
#     autre nuit/filtre diffère d'un facteur ~1,8× (R : lo 0,031 contre L :
#     0,0547) → 97,3 % / 93,7 % / 78,6 % des pixels écrasés à 0 et 2-3
#     appariements au lieu des 8 exigés ; avec SES PROPRES bornes la même frame
#     rend 22-96 appariements (10-62 inliers), au BON angle.
#   - ② `_triangles` NE PEUT PAS PORTER LE RETOURNEMENT : c'est le SEUL chemin
#     capable d'un saut de ~3 900 px (`_etoiles` vote à ±40/±100 px, `_phase`
#     n'accepte que ±40 px), mais il s'appuie sur les 12 étoiles les plus
#     brillantes et n'en apparie plus que 4-5 sur les couples INTER-NUITS
#     (seuil 6) ; élargir la base à 18 répare l'INTRA-nuit (5 → 150) sans rien
#     changer entre deux nuits.
#   CORRECTIFS (les DEUX, décision d'Alain) :
#   - ① `_compute_direct` normalise la frame sur SES PROPRES percentiles pour
#     l'ORB. Le repli « corrélation de phase » garde, LUI, le domaine PARTAGÉ
#     (bornes de la référence) : c'est `_sans_orb` qui recalcule cette seconde
#     normalisation, donc le chemin RAPIDE (une frame que l'ORB aligne) ne paie
#     rien de plus. ⚠ MESURÉ (rejeu des vraies frames) : en donnant au repli
#     phase le domaine LOCAL (l'essai du 09/10), 29 frames sur 60 étaient
#     « alignées » par phase avec une matrice QUASI-IDENTIQUE (0 appariement
#     d'étoiles mutuels) alors que leur vraie géométrie est à −176,2° (6 à 92
#     appariements) — ce sont ces FAUX alignements qui produisaient les doublons
#     rouges. Le domaine partagé les refuse (repli honnête), et le ② les remet
#     d'aplomb.
#   - ② `compute` ajoute un DERNIER RECOURS avant refus : un ORB ÉTOFFÉ
#     (`ORB_RENFORCE_FEATURES = 8000` points au lieu de 1 000, MÊMES garde-fous
#     que le chemin ORB : ratio de Lowe, RANSAC 2 px, minimum d'inliers,
#     `_M_valide`, puis raffinement par centroïdes), essayé sur la frame PUIS
#     sur la frame retournée de 180°. Ses descripteurs de RÉFÉRENCE sont
#     calculés à la première frame qui en a besoin puis MIS EN CACHE
#     (`_reference_forte`, invalidé par `set_reference` et `reset` — un cache
#     périmé apparierait la frame à l'ANCIENNE référence). Mesuré sur le cas
#     difficile : 3-5 inliers à 1 000 points contre 8-35 à 8 000. La matrice
#     composée du retournement est extraite dans `_composer_retournement` pour
#     que le dernier recours suive EXACTEMENT la même voie que le reste.
#   REJEU HORS-LIGNE des vraies frames du test (60 frames, 15 tours, règles du
#   worker) : code avec ① seul → 35 empilées / **26 refus** ; ① + ② → 61
#   empilées / **0 refus**, dont **26 frames sauvées par le dernier recours**
#   (24 « ORB étoffé » + 2 « ORB étoffé+étoiles »). Coût du ② sur ces frames :
#   p95 1 793 → 2 664 ms, max 1 901 → 3 037 ms (médiane 1 415 → 1 448 ms), sur
#   des brutes de 8,4 Mpx — payé UNIQUEMENT par les frames que tout le reste
#   refuse.
#   Banc NEUF : `_test_align_lumiere_jalon116.py` — le défaut ① mesuré (bornes
#   de la référence : 99 % de pixels nuls, médiane 0/255 ; propres bornes :
#   2 % et médiane 6/255), une frame « autre nuit » (fond ÷ 2 + rotation 176°)
#   ALIGNÉE et reconstruite ≈ la référence, 30°/90°/échelle 1,3/bruit toujours
#   REFUSÉS, dernier recours effectivement atteint quand la cascade historique
#   est neutralisée (et repris sur la frame retournée avec composition), image
#   plate refusée, cache des descripteurs de référence (calculé à la demande,
#   conservé, invalidé par `set_reference`). Bancs rejoués VERTS : align 13 et
#   15, méridien 111, ref-comp 113, narrowband 21, propagation/branchement/
#   domaine 56-115 ; garde-fou refactoring VERT (syntaxe 245 fichiers, surface
#   75, hash au bit, pyright 0 erreur sur 49 fichiers) ; ruff propre.
# v2.67.0 : ASTROMÉTRIE — CAUSE DU « toujours le même problème » TROUVÉE ET
#   CORRIGÉE (jalon 115) : le solveur recevait le COMPOSITE NORMALISÉ.
#   - PREUVE (journal v2.66.0, test réel M31 LRGB du 09/10, 7 échecs) : « pas
#     assez de correspondances mutuelles ; RANSAC paires : … (meilleur : 3
#     inliers, échelle 1.628″/px) » — l'échelle trouvée vaut ~0,66× la vraie.
#   - REPRODUIT HORS-LIGNE sur les frames RÉELLEMENT LUES (archives de session) :
#     en rejouant la session (alignement + rafraîchissements de référence), le
#     COMPOSITE `mean(recadre=False)` ÉCHOUE à l'identique (« aucune affinité
#     convaincante (5 étoiles) », fond 0,725, bruit 0,033) tandis que la COUCHE
#     BRUTE du rôle G, MÊME GRILLE, RÉSOUT avec 94 appariements à 2,466″/px
#     (108 pour la couche L). Données, catalogue (400 étoiles), indices
#     (AD/Dec/champ 2,63665°) et détection (120 étoiles) sont BONS.
#   - CAUSE : la détection du solveur seuille à `fond + 8σ`. Sur le composite
#     normalisé le fond vaut ~0,72 et σ ~0,033 → seuil ~0,99 : presque RIEN ne
#     passe et les « étoiles » retenues sont du BRUIT → appariement impossible.
#     C'est le MÊME défaut de DOMAINE que le correctif ① du jalon 113, mais
#     appliqué à l'ASTROMÉTRIE (le jalon 113 n'avait corrigé que l'ALIGNEUR).
#   - CORRECTIF : `core/worker.py` — nouveau `_image_reference_de(st)` (le corps
#     de l'ancienne `_image_reference`, jalon 113, déplacé tel quel) ; les TROIS
#     chemins d'astrométrie passent désormais la COUCHE BRUTE (`_image_reference_de`)
#     au lieu de `stacker.mean(recadre=False)` : `_astro_tour`, `_astro_aveugle`
#     (ASTAP travaille lui aussi sur un domaine de brutes) et surtout
#     `_astro_propager_restack` — ce dernier était la « piste NON corrigée »
#     signalée en AVANCEMENT : un composite d'un côté, une brute de l'autre,
#     la propagation du WCS après un re-stack était refusée pour la même raison.
#   - PLUS DE VISIBILITÉ ENCORE (`processing/astrometrie.py`) : `SuiviAstrometrie`
#     garde les COMPTEURS du dernier échec (`info_echec`) et les ajoute au message
#     (`resume_echec`) — « [image N étoiles, catalogue M, appariements K] ». Un
#     échec futur dira donc TOUT SEUL s'il vient de la détection, du catalogue ou
#     de l'appariement (avant, les compteurs étaient jetés en cas d'échec).
#   - Banc NEUF : `_test_astro_domaine_jalon115.py` (le domaine du composite vs
#     la couche, l'image RÉELLEMENT transmise par `_astro_tour`, `resume_echec`).
#   - INCOHÉRENCE DU JALON 113 SUPPRIMÉE (seuil de profondeur) : les seuils de la
#     PHOTOMÉTRIE et de la SPCC comparaient encore `stacker.n` — la SOMME des
#     rôles — à `ASTRO_MIN_FRAMES`, alors que l'astrométrie, elle, était passée à
#     la profondeur PAR RÔLE (v2.65.0 disait « seuils photo/SPCC inchangés » : ils
#     mesurent après un WCS résolu, donc l'écart était latent). Deux règles pour
#     une même décision = le genre de piège qu'on cherche trois mois plus tard :
#     `_photo_tour` et `_spcc_tour` passent désormais par `worker.
#     _profondeur_astro`, comme `_astro_tour`/`_astro_aveugle` → UN SEUL point de
#     décision, plus aucun seuil ne peut dériver de l'autre.
#   - MESSAGES ALIGNÉS SUR LA MÊME RÈGLE : la profondeur ANNONCÉE pendant une
#     mesure est celle PAR RÔLE (« 3 frames par rôle (12 au total) », même
#     formulation que la ligne d'astrométrie) et le libellé de la SPCC dit
#     « mesure faite sur N frames par rôle » (`processing/spcc.texte_resume`, clé
#     `frames_par_role` posée par le worker en composition) — le total reste
#     affiché, il ne décrit simplement plus la mesure.
#   - Banc du jalon 113 ÉTENDU (`_test_astro_profondeur_jalon113.py`) : section
#     [6] — `_photo_tour`/`_spcc_tour` ne mesurent plus à 1 frame par rôle (n = 4
#     en LRGB) et mesurent bien à 3 frames par rôle, comme l'astrométrie.
#   - Rappel jalon 114 (v2.66.0, inclus) : lignes d'état astro/photo/SPCC AU
#     JOURNAL au changement + libellés COPIABLES au clic droit.
# v2.66.0 : ASTROMÉTRIE VISIBLE — lignes d'état AU JOURNAL + libellés COPIABLES
#   (jalon 114). Deux doléances d'Alain, 09/10/2026, après le test réel de
#   v2.65.0 (M31 LRGB) :
#   - « TOUJOURS le même problème sur l'astrométrie — aucune info dans le
#     journal » : les messages d'échec (orange) n'existaient QUE dans
#     l'interface. `core/worker.py` n'importe même pas `journal` ; les seules
#     lignes écrites pendant une session étaient celles de DÉMARRAGE et les
#     DEBUG (case cochée). Diagnostic impossible après coup.
#     → `App._noter_etat(cle, texte)` écrit au journal la ligne d'état la
#     PREMIÈRE fois puis à chaque CHANGEMENT de texte (le worker pousse son
#     état à chaque frame : on ne journalise PAS 20 fois par seconde, seulement
#     les transitions). Branché sur les trois lignes de calcul — astrométrie,
#     photométrie, SPCC — côté texte du worker (`_update_status`) ET côté vue
#     de l'UI pour l'astrométrie (`_maj_astro_vue`, qui porte aussi les
#     « indices refusés — … »). Le journal donne désormais la chronologie
#     exacte : « résolution en cours », « échec — 3 inliers, échelle
#     1,794″/px (1/20 essais…) », « BALAYAGE… », etc.
#   - « impossible de copier les textes des libellés orange ou jaune » : les
#     `ttk.Label` de Tk ne sont pas sélectionnables.
#     → `App._poser_copie_libelles()` : un CLIC DROIT sur N'IMPORTE QUEL
#     libellé de la fenêtre ouvre un menu « Copier le texte » qui met la ligne
#     dans le presse-papiers (`bind_all`, donc aussi les libellés créés après
#     coup ; Button-3 = Windows/Linux, Button-2 et Control-clic = macOS).
#     `_texte_libelle` gère les libellés à `textvariable`. Jamais d'exception.
#   - Banc NEUF : `_test_journal_libelles_jalon114.py` (copie de texte fixe et
#     de `textvariable`, journalisation au changement et PAS de doublon à
#     l'identique, intégration `_update_status`). Garde-fou rejoué (surface 75
#     inchangée — deux méthodes privées ajoutées, hash au bit inchangé).
# v2.65.0 : ALIGNEMENT + ASTROMÉTRIE en COMPOSITION — DEUX CORRECTIFS (jalon 113)
#   - CONSTAT RÉEL (Alain, 09/10/2026, M31 LRGB ; rejeux des 08-09/10) : en mode
#     COMPOSITION, le rafraîchissement de référence écrasait les brutes suivantes
#     et l'astrométrie ne parvenait jamais à se faire.
#   - ① RAFAÎCHISSEMENT DE RÉFÉRENCE (`core/worker.py` : `_image_reference` /
#     `_rafraichir_reference`) : il passait `stacker.mean(recadre=False)`, donc en
#     composition le COMPOSITE NORMALISÉ (fond ~5× celui des brutes : ~0,27 contre
#     ~0,05 au banc ; 0,5-1,1 contre ~0,03 sur les vraies brutes). Comme
#     `StarAligner.set_reference` prend ses bornes SUR la référence, la brute
#     était tassée dans les bas niveaux 8 bits (médiane 1/255 contre 62/255 au
#     banc) → ORB aveugle → **8-9 refus sur 12 frames** MESURÉS (0 refus sans
#     rafraîchissement). On passe désormais la COUCHE 2D BRUTE du rôle qui
#     alimente le canal VERT (G en RGB/LRGB, O3 en HOO, Ha en SHO — le MÊME canal
#     que `canal_alignement` prenait sur le composite, mais dans le domaine des
#     brutes) ; repli sur le 1er rôle non vide (rôle vert encore vide en début de
#     session), et empilement tel quel hors composition. Banc : 12/12 refus → 0/12.
#   - ② PROFONDEUR MINIMALE PAR RÔLE (nouveau `CompositeStacker.profondeur_min()`
#     + `worker._profondeur_astro`) : `astrometrie.ASTRO_MIN_FRAMES` était comparé
#     à `stacker.n`, qui est la SOMME des rôles — en LRGB, 1 frame par rôle
#     donnait n = 4 ≥ 3 et le solveur tentait sa résolution sur une image DÉJÀ
#     INSOLUBLE (« image constante ») : l'essai était BRÛLÉ et le backoff
#     (20→300 s) éloignait les suivants, si bien que la profondeur où l'astrométrie
#     FONCTIONNE n'était jamais atteinte. C'est la profondeur du rôle le plus FAIBLE
#     qui est comparée au seuil (≈12 en LRGB). Mesure de référence : 2 frames/rôle
#     = échec (« 3 inliers, échelle 1,812″/px »), 3 = RÉSOLU. Appliqué aux trois
#     chemins : `_astro_tour` (`peut_essayer` ET `resoudre_sur(n_frames=…)`),
#     message d'état (« N frames par rôle (M au total) »), et le garde de
#     `_astro_aveugle` (ASTAP n'est plus sollicité sur une image insoluble).
#     Seuils photo/SPCC inchangés (ils ne s'exécutent qu'après un WCS résolu).
#   - Bancs NEUFS : `_test_refresh_ref_compo_jalon113.py` (domaine composite vs
#     couche, choix de la couche du canal vert, cécité de l'ORB, rejeu 12 frames) ;
#     `_test_astro_profondeur_jalon113.py` (`profondeur_min`, seuil par rôle,
#     `_astro_tour` avec suivi bouchonné, garde de `_astro_aveugle`).
#     `_test_astro_branchement_jalon56`, `_test_compo_worker_jalon19` et le
#     garde-fou rejoués VERTS (hash au bit inchangé, surface 75, pyright 0/49) ;
#     `ruff` propre.

# v2.64.0 : ALIGNEMENT — RETOURNEMENT AU MÉRIDIEN RÉELLEMENT RÉSOLU (jalon 112)
#   - CONSTAT RÉEL (Alain, 08/10/2026, M31 au SV555, deux nuits) : les en-têtes
#     FITS montrent PIERSIDE=West pour les brutes du 22/09 23:53 et East pour
#     celles du 13/09 et du 23/09 03:17 → retournement au méridien. Seules
#     46 frames sur 212 s'empilaient (R 3/50, G 3/50, B 4/50), et l'image LRGB
#     portait des « taches rouges » (étoiles fantômes de la couche retournée).
#   - CAUSE PROFONDE, mesurée sur les vraies brutes : `detecter_positions`
#     rendait les N composantes au plus FORT PIC ; or elles s'ENTASSENT dans un
#     bandeau (les 60 « plus brillantes » tenaient dans 20 % de la hauteur) →
#     liste d'étoiles explorable par AUCUN appariement. Mesure : 2 étoiles
#     communes entre deux frames du même champ → **35** avec une sélection
#     RÉPARTIE dans le champ.
#   - `processing/stars.py` : nouveau paramètre `distance_min` → SÉLECTION
#     RÉPARTIE (parcours glouton sur le tri par éclat, écart minimal imposé).
#     Défaut 0 = comportement ANTÉRIEUR inchangé.
#   - `processing/alignment.py` : ① `MAX_ALIGN_ETOILES` 60 → **250** et écart
#     `_distance_repartition()` ADAPTATIF (0,7 × espacement moyen, plafonné à
#     120 px — une petite image garde ses étoiles) ; ② **REPLI 180°** dans
#     `compute()` : si l'alignement direct échoue, on réessaie la frame
#     RETOURNÉE de 180° et on COMPOSE la matrice (le sens direct est essayé
#     d'abord ; le repli « phase » en est ÉCARTÉ, car il suppose des images de
#     même orientation). ③ `_M_valide` accepte ~180° (170°–190°).
#   - RÉSULTAT MESURÉ sur les dossiers réseau d'Alain : L 10/10, R 9/10 (les
#     frames West s'alignent à −176,2°, les East à −0,13°).
#   - `catalogues/propagation.py` : la sanitation d'angle accepte ~180°
#     (`ANGLE_SAN_FLIP_DEG`) — un ré-empilement basculé sur une frame retournée
#     garde son WCS.
#   - Bancs : `_test_meridien_flip_jalon111.py` (vert) ; align 13/15, narrowband
#     21, propagation 56 rejoués VERTS ; garde-fou VERT (hash au bit inchangé,
#     surface 75, pyright 0/49) ; `ruff` propre.
# v2.63.0 : ALIGNEMENT — RETOURNEMENT AU MÉRIDIEN ACCEPTÉ (jalon 111)
#   - CONSTAT RÉEL (Alain, 08/10/2026) : sur deux nuits d'acquisition (même
#     caméra, NINA), les couches R/G/B ont subi un retournement au méridien
#     (rotation ~180° par rapport au ciel) tandis que L ne l'a pas subi. Comme
#     toutes les images partagent UN SEUL aligneur (jalon 15/19), les frames
#     retournées étaient TOUTES rejetées (|angle| > 10°) : 3-4 frames R/G/B
#     empilées sur 50, un empilement appauvri ET une image LRGB hérissée de
#     « taches rouges » (la formule LRGB — L / luminance(RGB) — amplifie le
#     fond là où L seul portait encore un objet : les étoiles fantômes du côté
#     minoritaire du méridien).
#   - CORRECTIF `processing/alignment.py` : `_M_valide` accepte désormais une
#     rotation ~180° dans la MÊME tolérance que l'alignement normal
#     (`MERIDIAN_FLIP_DEG = 180`, `MERIDIAN_FLIP_TOL_DEG = 10` → 170°–190°).
#     TOUS les autres garde-fous restent INCHANGÉS (échelle [0.9, 1.1], inliers
#     minimum, contre-test d'appariements mutuels, continuité de translation) :
#     une fausse correspondance à 180° reste impossible (15° et 90° refusés).
#     AUCUN réglage à faire : la correction s'applique d'elle-même.
#   - `catalogues/propagation.py` : la SANITATION d'angle accepte elle aussi
#     ~180° (`ANGLE_SAN_FLIP_DEG`) — sinon un ré-empilement basculé sur une
#     frame retournée perdrait son WCS (`_astro_propager_restack`).
#   - Banc `_test_meridien_flip_jalon111.py` : `_M_valide` (0°/180° acceptés ;
#     15°/90°/165°/195° refusés ; échelle aberrante et NaN toujours bornés) ;
#     frame pivotée de 180° RÉELLEMENT alignée et reconstruite (méthode
#     « ORB+étoiles ») ; non-régression (translation normale conservée, 15°
#     refusé). Bancs d'alignement 13/15, narrowband 21 et propagation 56
#     rejoués VERTS ; garde-fou VERT (hash au bit, surface 75, pyright 0/49) ;
#     `ruff` propre sur les fichiers touchés.
# v2.62.1 : CHANTIER DE REFACTORING — TYPAGE RÉTROACTIF du RÉSIDU de `ui/`
#   (jalon 110 — clôture du chantier 100→110)
#   - ANNOTATIONS SEULES (aucun changement de comportement, rendu identique AU
#     BIT) sur `avastack/ui/app.py` (l'objet `App` — 217 fonctions — et ses
#     helpers), `avastack/ui/reactivite.py` (guet de gel du fil d'interface) et
#     le paquet `ui/__init__`. Paramètres, valeurs de retour et les 29 attributs
#     d'instance PROPRES à `app.py` annotés (`np.ndarray`, `dict[...]`,
#     `tuple[...] | None`, PEP 604) — les ~139 autres attributs étaient déjà
#     DÉCLARÉS par les mixins extraits (`ui/panels/*`, `ui/renderer.py`…), qui
#     font office d'interface typée pour `App`.
#   - 33 erreurs pyright préexistantes résorbées par annotations + ignores
#     CIBLÉS documentés (motif des jalons 103/107/108/109) : attributs posés sur
#     des widgets Tk (`Scale._pas/_boutons/_row/_lbl_txt`, `Frame._btn_header`),
#     `cam.roles` (caméras SDK sans cet attribut dans le stub), surcharge
#     `config`, `float(... | None)`, dépaquetage d'un `delais.borne(...)[0]`
#     Optionnel, et 3 `dict` locaux désormais typés (`job`, `msg`, `resultat`).
#   - 1 avertissement ruff PRÉEXISTANT neutralisé par un commentaire `noqa`
#     ciblé (ré-export de `tracer_evt` par `app.py`, comme `i_etape` au jalon 108).
#   - GARDE-FOU (jalon 100) : liste blanche portée à 49 fichiers ; TOUT AU VERT
#     (syntaxe, surface publique 75 symboles, hash d'empilement au bit,
#     **pyright 0 erreur / 49 fichiers**). `ruff` : `ui/` + `processing/` PROPRES.
#   - BANCS UI rejoués VERTS (ui 5, sliders 6, histo 75, config 6, visibilité 47,
#     dialogues 84, robuste 87, état calcul 40, zoom pleine res 68, annotations
#     overlay 96, save as-seen 5, graxpert live 4, robuste v2.48.3). ÉCHEC
#     PRÉEXISTANT de `_test_rafale_fin_rendu_jalon80` (section [6] bout-en-bout,
#     sensible au timing) : reproduit À L'IDENTIQUE sur la version d'origine
#     (git checkout) — NON imputable au typage.
#   - CLÔTURE du chantier de refactoring (100→110) : le résidu de `ui/app.py` et
#     les derniers modules `ui/` sont typés.
# v2.62.0 : CHANTIER DE REFACTORING — TYPAGE RÉTROACTIF de `processing/`
#   (jalon 109, les 16 modules de traitement)
#   - ANNOTATIONS SEULES (aucun changement de comportement, rendu identique AU
#     BIT) sur tout le paquet `avastack/processing/` : `calibration`,
#     `framestore`, `veralux`, `denoise`, `sharpness`, `stars`, `annotations`,
#     `astrometrie`, `photometrie`, `composition`, `couleurs`, `alignment`,
#     `stacking`, `spcc`, `display` et le `__init__` (ré-exports déclarés par
#     `__all__`, comme `catalogues/__init__.py`).
#   - paramètres, valeurs de retour et attributs d'instance annotés ; types
#     `numpy` (`np.ndarray`), `dict[...]`, `tuple[...] | None`, PEP 604
#     (`X | None`) — même style que la fondation (jalon 101) et `core`/`ui`.
#   - 8 modules se sont typés à 0 ERREUR pyright par la seule annotation ;
#     les 8 autres (alignment, annotations, astrometrie, denoise, display,
#     photometrie, spcc, stacking — 86 erreurs au départ) l'ont été avec des
#     ignores CIBLÉS et documentés : surcharges OpenCV (`estimateAffinePartial2D`,
#     `fastNlMeansDenoising`, `ORB_create`), `np.float32(liste)` (rend bien un
#     ndarray, pyright voit un scalaire), stub astropy (`hd[0].header`),
#     rétrécissement Optionnel (pyright ne suit pas les attributs à travers une
#     variable booléenne) et TAMPONS DE TRAVAIL préalloués typés `Any`.
#   - 4 avertissements ruff PRÉEXISTANTS neutralisés par `# noqa` (aucun
#     changement de comportement), comme `i_etape` au jalon 108 : ré-exports du
#     `__init__` (résolus par `__all__`), `import sys` inutilisé de `denoise`,
#     variable `ic` de `photometrie`, `scnr_actif`/`sd_actif`/`dm_actif` de
#     `display`.
#   - GARDE-FOU (jalon 100) : liste blanche portée à 46 fichiers ; TOUT AU VERT
#     (syntaxe, surface publique 75 symboles, hash d'empilement au bit,
#     **pyright 0 erreur / 46 fichiers typés**). `ruff` : `processing/` PROPRE.
#   - BANCS DE TRAITEMENT rejoués VERTS (align 13/15, stars 10, RL 11,
#     sharp live 12, dn local 8, denoise live 9, calib compo 53, composition 19,
#     couleurs 22, luminance 85, boost rouge 86, chroma structure 67, photométrie
#     56, spcc 58/58bis, propagation 56, fit canaux 54, rejet satellites 6,
#     veralux 1/2/3, crop intersection, norm commune 61, histo 75, gradient
#     couche 24, annotations overlay 96). ÉCHECS PRÉEXISTANTS de
#     `_test_chroma_nr_jalon63` / `_test_chroma_halo_jalon65` (chaîne « solveur
#     VeraLux ») : reproduits À L'IDENTIQUE sur la version d'origine (git stash)
#     — NON imputables au typage.
# v2.61.1 : CHANTIER DE REFACTORING — `ui/saver.py` + `ui/external_runner.py`
#   (jalon 108, sauvegardes + traitement externe)
#   - DEUX modules NEUFS (TYPÉS) extraits de `app.py`, sous forme de mixins dont
#     `App` HÉRITE (méthodes VERBATIM, `self` reste l'instance `App`,
#     comportement inchangé AU BIT) :
#       · `ui/saver.py` (mixin `Saver`) — tout ce qui ÉCRIT un fichier : `_save`,
#         `_save_canaux`, `_save_asseen`, `_save_traite_lineaire`, `_save_proc`,
#         la capture des réglages (`_reglages_rendu`), le contrôle GraXpert live
#         (`_gx_live_prete`), le THREAD pleine résolution (`_save_asseen_thread`,
#         `_couches_brutes`, `_couches_pleine_resolution`) et les EN-TÊTES FITS de
#         sortie (`_entete_reglages`, `_entete_externe`,
#         `_astro_entete_sauvegarde`) ;
#       · `ui/external_runner.py` (mixin `ExternalRunner`) — le TRAITEMENT EXTERNE
#         (GraXpert / BlurXTerminator, thread séparé) : `_request_ext`, `_pick_exe`,
#         `_set_ext_msg`, `_run_external`, `_run_external_compo`,
#         `_compo_couches_traitees`, `_ext_run_cmd`, `_fin_ext_tmp`.
#   - PIÈGE D'ISOLATION ÉCARTÉ : aucune méthode déplacée ne lit `CONFIG` /
#     `sauver_config` ni le module `journal` au niveau module (le banc qui
#     REMPLACE `ui.journal` a été rejoué vert) → AUCUN `_globals_app()` requis.
#     Les dépendances de module (`gx_live`, `travail`, `composition_mod`,
#     `couleurs_mod`, `denoiser_local`, `nettete_live`, `save_image`,
#     `borner_lineaire`, `find_output`, `auto_unflip`, `commande_avec_strength`)
#     sont importées à l'IDENTIQUE : les bancs qui patchent leurs ATTRIBUTS
#     (`ui.gx_live.appliquer`, `travail.espace_libre`…) restent EFFECTIFS.
#   - `app.py` : les imports devenus inutilisés sont conservés en RÉ-EXPORT
#     (`# noqa: F401`) → surface publique INCHANGÉE (75 symboles, banc garde-fou) ;
#     `import shutil` retiré (plus employé). `external_runner.py` porte le MÊME
#     avertissement préexistant `i_etape` (F841), désormais marqué `noqa`.
#   - Vérifications : garde-fou VERT (surface 75, hash au bit, pyright 0 erreur
#     sur 30 fichiers typés) ; `ruff` : `saver.py` et `external_runner.py`
#     PROPRES, `app.py` au seul avertissement PRÉEXISTANT (`tracer_evt`) ; bancs
#     rejoués verts — `_test_save_asseen_jalon5.py`, `_test_save_brute_jalon59.py`,
#     `_test_save_lineaire_echelle.py`, `_test_save_lineaire_fix.py`,
#     `_test_save_rgb_axes.py`, `_test_graxpert_live_jalon4.py`,
#     `_test_bxt_entete_jalon69.py`, `_test_gx_lot_externe_jalon83.py`,
#     `_test_denoise_live_jalon9.py`, `_test_sharp_live_jalon12.py`,
#     `_test_etat_calcul_jalon40.py`, `_test_annotations_save_jalon96.py`,
#     `_test_ui_robuste_jalon87.py`, `_test_ui_robuste_v2_48_3.py`,
#     `_test_demarrage_non_bloquant_jalon74.py`, `_test_reset_empilement_jalon76.py`.
#     ⚠ `_test_espace_jalon72.py` : UN échec de placement de boutons, PRÉEXISTANT
#     (reproduit à l'IDENTIQUE avec l'`app.py` d'origine — sans lien avec ce jalon).
#
# v2.61.0 : CHANTIER DE REFACTORING — `ui/renderer.py` (jalon 107, rendu + annotation)
#   - Module NEUF (TYPÉ) `avastack/ui/renderer.py` (mixin `Renderer`, dont `App`
#     HÉRITE) : tout ce qui DESSINE sur le Canvas d'image `cv_img` quitte
#     `app.py`, repris VERBATIM (comportement inchangé AU BIT) — la SÉLECTION DE
#     SOURCE (`_src_pleine_res`, `_src_rendu`, `_pleine_res_activee`,
#     `_on_vl_pleine_res`), la CHAÎNE D'AFFICHAGE UNIQUE (`_rendre_et_afficher`,
#     `_refresh_preview`), le DESSIN et les GESTES du Canvas (`_show_image`,
#     `_render`, zoom / pan, `_vider_ecran`) et l'ANNOTATION temps-réel du
#     jalon 96 (`_seuil_mag`, `_on_annoter`, `_forme_pleine`, `_wcs_affichage`,
#     `_donnees_annotation`, `_annoter_image`, `_sauver_png_annote`).
#   - PIÈGE D'ISOLATION : l'annotation LIT/ÉCRIT `CONFIG` (seuil de magnitude,
#     cases « annoter… ») et appelle `sauver_config` ; les bancs les interceptent
#     via `ui.CONFIG` / `ui.sauver_config` → ces globals sont résolus TARDIVEMENT
#     (`_globals_app()`, motif des jalons 104/105a) : l'interception reste
#     EFFECTIVE et le vrai config.json n'est jamais écrit pendant un test.
#   - `app.py` : `Image` / `ImageTk` (Pillow) RETIRÉS (plus employés depuis que
#     `_render` a migré) ; `annoter_mod` conservé en RÉ-EXPORT (`# noqa: F401`),
#     la surface publique reste INCHANGÉE (75 symboles, banc garde-fou).
#   - Vérifications : garde-fou VERT (surface 75, hash au bit, pyright 0 erreur
#     sur 28 fichiers typés) ; `ruff` : `renderer.py` PROPRE, `app.py` aux
#     2 avertissements PRÉEXISTANTS (`tracer_evt`, `i_etape`) ; bancs rejoués
#     verts —
#     `_test_histo_jalon75.py`, `_test_zoom_pleine_res_jalon68.py`,
#     `_test_pleine_res_traitee_jalon69.py`, `_test_annotations_overlay_jalon96.py`,
#     `_test_annotations_save_jalon96.py`.
#
# v2.60.3 : CHANTIER DE REFACTORING — `core/worker.py` (jalon 106d, mesures)
#   - Les MESURES (astrométrie + photométrie / SPCC) rejoignent le mixin : les
#     méthodes de CALCUL reprises VERBATIM de `ui/app.py` — `_astro_tour`,
#     `_astro_aveugle`, `_photo_tour`, `_photo_canaux`, `_source_rgb`,
#     `_spcc_tour`, `_astro_indices_entete`, `_astro_propager_restack`. Le bloc
#     d'appel de `_worker` devient la sous-méthode `_worker_mesures` (servi APRÈS
#     le re-stack, AVANT la construction de l'état poussé à l'UI).
#   - L'AFFICHAGE reste dans `ui/app.py` (méthodes `_maj_*_etat` / `_maj_*_vue`,
#     dialogues de nom de cible, helpers d'en-tête FITS de sortie — ceux-ci
#     relevant du jalon 108 `saver.py`) : séparation « mesures » / « affichage ».
#     Les appels `app._astro_tour(...)` des bancs restent valides (héritage).
#   - Vérifications : garde-fou VERT (surface 75, hash au bit, pyright 0/27) ;
#     `ruff` ; bancs rejoués verts — `_test_photometrie_jalon56.py`,
#     `_test_astro_branchement_jalon56.py`, `_test_spcc_jalon58.py`, plus
#     `_test_bxt_entete_jalon69.py` et `_test_norm_commune_jalon61.py`.
#
# v2.60.2 : CHANTIER DE REFACTORING — `core/worker.py` (jalon 106c, pilotage)
#   - Les deux blocs de « PILOTAGE » de `_worker` sont découpés en sous-méthodes
#     TYPÉES reprises VERBATIM (comportement inchangé AU BIT) :
#       · `_worker_pilotage` — sondage des contrôles à la connexion, demandes
#         filtre / refroidissement, relecture TEC, réglages expo/gain et
#         OFFSET ; servi en TÊTE de boucle, MÊME EMPILEMENT EN PAUSE ;
#       · `_worker_cadence_dossier` — pause sur une source FICHIERS (le bloc qui
#         portait `continue`) + scan périodique de la cadence ; renvoie True
#         quand le tour doit se terminer sans rien lire.
#   - AUCUN paramètre du seam `WorkerConfig` n'est lu sur ce chemin : la leçon
#     du jalon 106b interdit d'AJOUTER du code sur le chemin de la boucle (un
#     instantané en tête de tour décalait la course du banc 76). `rejet_*` reste
#     consommé par `_worker_empiler_frame` ; `cadence_lecture` reste lu
#     DIRECTEMENT.
#   - Vérifications : garde-fou VERT (surface 75, hash au bit, pyright 0/27) ;
#     `ruff` ; bancs rejoués verts — `_test_jalon17_filtre.py`,
#     `_test_cadence_jalon42.py`, `_test_pilotage_jalon35.py`,
#     `_test_reset_empilement_jalon76.py`. Étape suivante (106d) : « mesures »
#     (astrométrie/photométrie/SPCC).
#
# v2.60.1 : CHANTIER DE REFACTORING — `core/worker.py` (jalon 106b, boucle)
#   - `_worker` reste l'ORCHESTRATEUR de la boucle du thread d'acquisition ;
#     ses blocs cohérents sont découpés en sous-méthodes TYPÉES reprises
#     VERBATIM (comportement inchangé AU BIT) :
#       · `_worker_reinitialiser` — remise à zéro de session (« ▶ Démarrer » /
#         « Réinitialiser l'empilement »), servie en TÊTE de boucle ;
#       · `_worker_empiler_frame` — traitement d'une brute (filtre
#         défocalisation, archivage, (re)création de l'empileur, alignement,
#         empilement) ; renvoie `(sauter, last_good, stack)` ;
#       · `_worker_restack` — re-stack « à la Siril » (bouton ou auto) ;
#         renvoie `(fait, stack)`.
#   - Le SEAM `WorkerConfig` (`core/config.py`) est CONSOMMÉ : `kappa`,
#     `rejet_methode` et `rejet_fenetre` sont lus sur un instantané construit
#     au POINT D'USAGE (`WorkerConfig.depuis(self)`) — AUCUN code ajouté sur le
#     chemin de la boucle, donc le profil temporel du worker est IDENTIQUE.
#   - Le seam a révélé un `k` typé trop étroit (`LiveStacker`/`CompositeStacker`
#     annoncent `k: float` mais acceptent `None` — kappa « Off », usage des
#     bancs et de `app.py`) : 2 ignores `# pyright: ignore[reportArgumentType]`
#     CIBLÉS (motif du chantier).
#   - Vérifications : garde-fou VERT (surface 75, hash au bit, pyright 0/27) ;
#     `ruff` « All checks passed » ; bancs rejoués verts —
#     `_test_restack_jalon16.py`, `_test_restack_compo_jalon20.py`,
#     `_test_reset_empilement_jalon76.py`. Étapes suivantes (106c/106d) :
#     « pilotage » (roue/TEC/offset + cadence dossier) et « mesures »
#     (astrométrie/photométrie/SPCC).
#

# v2.60.0 : CHANTIER DE REFACTORING — `core/worker.py` (jalon 106a, squelette)
#   - Nouveau paquet TYPÉ `avastack/core/` : `config.py` (`WorkerConfig`,
#     dataclass gelé des paramètres du worker : rejet kappa-sigma, cadence de
#     lecture, instantanés expo/gain/offset) et `worker.py` (mixin
#     `AcquisitionWorker` dont `App` HÉRITE).
#   - La BOUCLE du thread d'acquisition (`_worker`, 782 lignes) quitte `app.py`
#     pour `avastack/core/worker.py`, reprise VERBATIM (`self` reste l'instance
#     `App`) : comportement inchangé AU BIT. `app.py` : 8 473 → 7 703 lignes.
#   - PIÈGE D'ISOLATION : `ArchiveFrames`, `RESTACK_MIN_FRAMES` et
#     `RESTACK_CADENCE` sont MONKEYPATCHÉS par les bancs (via `ui.<nom>`) → lus
#     par RÉSOLUTION TARDIVE (`_globals_app()`), comme `ui/widgets/collapsible.py`
#     et `ui/panels/stack.py` : l'interception des bancs reste EFFECTIVE.
#   - `_worker` s'appuie sur des GARDES D'EXÉCUTION que `pyright` ne voit pas
#     (garde sur variable locale `stack`, `isinstance(self.camera, QHYCamera)`
#     qui narrow un attribut `Any`) : ignores `# pyright: ignore[...]` CIBLÉS sur
#     les 17 accès concernés (motif du jalon 103, `collapsible.py`).
#   - Vérifications : surface publique INCHANGÉE (75 symboles) ; garde-fou VERT
#     (pyright 0 erreur sur 27 fichiers typés, hash au bit) ; bancs du worker
#     rejoués verts — `_test_reset_empilement_jalon76.py`,
#     `_test_restack_jalon16.py`, `_test_restack_compo_jalon20.py`,
#     `_test_restack_visu_jalon18.py`, `_test_compo_worker_jalon19.py`,
#     `_test_narrowband_ha_jalon21.py`, `_test_cadence_jalon42.py`,
#     `_test_jalon17_filtre.py`, `_test_astro_branchement_jalon56.py`,
#     `_test_save_asseen_jalon5.py`, `_test_ui_jalon5.py`,
#     `_test_config_jalon6.py`, `_test_ui_robuste_jalon87.py`,
#     `_test_ui_visibilite_jalon47.py`. Étapes suivantes (106b/106c/106d) :
#     découpage de la boucle en « boucle » / « pilotage » / « mesures ».
#
# v2.59.2 : CHANTIER DE REFACTORING — `ui/panels/` (jalon 105c, vague « sortie »)
#   - Cinq modules NEUFS (TYPÉS) dans `avastack/ui/panels/` : la TROISIÈME vague
#     d'extraction de la COLONNE GAUCHE, sous forme de mixins dont `App` HÉRITE
#     (méthodes reprises VERBATIM — `self` reste l'instance `App`, séquence de
#     pose et comportement inchangés AU BIT) :
#       · `display.py` — `PanneauAffichage` : « Affichage » (moteur STF/VeraLux,
#         réglages STF et communs, cadre VeraLux, rendu pleine résolution) ;
#       · `color.py` — `PanneauCouleur` : « Couleur de l'objet (APRÈS
#         étirement) » (SCNR, SCNR doux, démagenta, boost du rouge SII) ;
#       · `state.py` — `PanneauEtatCalculs` : « État des calculs » ;
#       · `external.py` — `PanneauTraitementExterne` : « Traitement externe »
#         (GraXpert, débruitage, BlurXTerminator, vue empilement/traitée, ⚡) ;
#       · `output.py` — `PanneauSortie` : « Sortie » (4 enregistrements).
#     `_build_ui` appelle désormais `self._poser_panneau_*` (14 appels) ;
#     `avastack/ui/app.py` : 8 922 → 8 473 lignes.
#   - Aucun de ces 5 panneaux ne lit `CONFIG` ni `sauver_config` : aucune
#     résolution TARDIVE n'est requise. `veralux_moteur` et `couleurs_mod` sont
#     importés directement dans les modules (aucun banc ne les mocke via
#     `ui.<nom>`).
#   - `DEFAULT_CMD_GRAXPERT`, `DEFAULT_CMD_GRAXPERT_DN` et `DEFAULT_CMD_BXT`
#     ne sont plus utilisés DANS `app.py` (le panneau Traitement externe a
#     migré) mais restent RÉ-EXPORTÉS (`# noqa: F401`) : surface publique
#     INCHANGÉE (75 symboles).
#   - `pyright` 0 ERREUR sur les 25 fichiers typés ; `ruff` : seuls les
#     2 avertissements PRÉEXISTANTS de `app.py` (`tracer_evt`, `i_etape`).
#   - Vérifications : garde-fou VERT ; bancs rejoués verts —
#     `_test_ui_moteur_jalon41.py`, `_test_sliders_jalon6.py`,
#     `_test_couleur_luminance_jalon85.py`, `_test_boost_rouge_jalon86.py`,
#     `_test_etat_calcul_jalon40.py`, `_test_ui_jalon5.py`,
#     `_test_save_asseen_jalon5.py`, `_test_bxt_entete_jalon69.py`,
#     `_test_graxpert_live_jalon4.py`, `_test_histo_jalon75.py`,
#     `_test_zoom_pleine_res_jalon68.py`, `_test_ui_visibilite_jalon47.py`,
#     `_test_ui_robuste_jalon87.py`, `_test_config_jalon6.py`,
#     `_test_pleine_res_traitee_jalon69.py`, `_test_dialogues_jalon84.py`,
#     `_test_annotations_overlay_jalon96.py`.
#
# v2.59.1 : CHANTIER DE REFACTORING — `ui/panels/` (jalon 105b, vague « traitement »)
#   - Cinq modules NEUFS (TYPÉS) dans `avastack/ui/panels/` : la DEUXIÈME vague
#     d'extraction de la COLONNE GAUCHE, sous forme de mixins dont `App` HÉRITE
#     (méthodes reprises VERBATIM — `self` reste l'instance `App`, séquence de
#     pose et comportement inchangés AU BIT) :
#       · `compo.py` — `PanneauComposition` : « Composition multi-filtres » ;
#       · `calib.py` — `PanneauCalibration` : « Calibration » ;
#       · `stack.py` — `PanneauEmpilement` : « Empilement » (stats, seeing,
#         re-stack, astrométrie + annotation, catalogues & données SPCC,
#         photométrie, SPCC, rejet, équilibrage des canaux, Linear Fit, filtre
#         anti-brutes floues) ;
#       · `bgnoise.py` — `PanneauFondGrain` : « Fond et grain » ;
#       · `sharp.py` — `PanneauNette` : « Netteté live ».
#     `_build_ui` appelle désormais `self._poser_panneau_*` (9 appels) ;
#     `avastack/ui/app.py` : 9 509 → 8 922 lignes.
#   - `stack.py` lit `CONFIG` par RÉSOLUTION TARDIVE (`_globals_app()`, motif du
#     correctif du jalon 105a dans `ui/widgets/collapsible.py`) : les mocks des
#     bancs (`ui.CONFIG`) restent EFFECTIFS et le vrai config.json n'est jamais
#     écrit pendant un test. En production, comportement IDENTIQUE (même objet).
#   - `ROLES` n'est plus utilisé DANS `app.py` (le panneau Composition a migré
#     vers `ui/panels/compo.py`) mais reste RÉ-EXPORTÉ (`# noqa: F401`) :
#     surface publique INCHANGÉE (75 symboles).
#   - `pyright` 0 ERREUR sur les 20 fichiers typés ; `ruff` : seuls les
#     2 avertissements PRÉEXISTANTS de `app.py` (`tracer_evt`, `i_etape`).
#   - Vérifications : garde-fou VERT ; bancs rejoués verts —
#     `_test_compo_ui_jalon19.py`, `_test_sharp_live_jalon12.py`,
#     `_test_ui_visibilite_jalon47.py`, `_test_config_jalon6.py`,
#     `_test_annotations_overlay_jalon96.py`, `_test_norm_commune_jalon61.py`,
#     `_test_spcc_osc.py`, `_test_ui_robuste_jalon87.py`,
#     `_test_sliders_jalon6.py`, `_test_ui_moteur_jalon41.py`,
#     `_test_reset_empilement_jalon76.py`, `_test_restack_jalon16.py`,
#     `_test_restack_compo_jalon20.py`, `_test_histo_jalon75.py`,
#     `_test_zoom_pleine_res_jalon68.py`, `_test_dialogues_jalon84.py`,
#     `_test_couleur_luminance_jalon85.py`, `_test_ergonomie_jalon52.py`,
#     `_test_cadence_jalon42.py`, `_test_capacites_ui_jalon32.py`,
#     `_test_expo_affichage_jalon34.py`. (`_test_rafale_fin_rendu_jalon80.py`
#     présente un échec de TIMING PRÉEXISTANT — reproduit sur l'arbre pristine,
#     indépendant de cette extraction.)
#
# v2.59.0 : CHANTIER DE REFACTORING — `ui/panels/` (jalon 105a, vague « sources »)
#   - Quatre modules NEUFS (TYPÉS) + `__init__.py` dans `avastack/ui/panels/` :
#     la première vague d'extraction de la COLONNE GAUCHE, sous forme de mixins
#     dont `App` HÉRITE (méthodes reprises VERBATIM — `self` reste l'instance
#     `App`, séquence de pose et comportement inchangés AU BIT) :
#       · `files.py` — `PanneauFichiers` : « Fichiers de travail et journal » ;
#       · `camera.py` — `PanneauCamera` : « Caméra » (+ `_fmt_expo`, déplacé) ;
#       · `cadence.py` — `PanneauCadence` : « Cadence d'empilement »
#         (`_creer_cadence` et `_maj_lbl_cadence` déplacés avec lui) ;
#       · `folder.py` — `PanneauDossierSurveille` : « Dossier surveillé ».
#     `_build_ui` appelle désormais `self._poser_panneau_*` (4 appels) ;
#     `avastack/ui/app.py` : 9 733 → 9 509 lignes.
#   - `_fmt_expo` (formateur d'exposition µs/ms/s) déplacé dans
#     `panels/camera.py` et RÉ-IMPORTÉ par `app.py` (ses méthodes `_maj_expo` /
#     `_valider_expo` l'utilisent, et `avastack.ui.app._fmt_expo` reste
#     résolvable — banc jalon 34). `SOURCES` et `CFA_MODE` ne sont plus utilisés
#     DANS `app.py` (leurs panneaux ont migré) mais restent RÉ-EXPORTÉS
#     (`# noqa: F401`) : surface publique INCHANGÉE (75 symboles).
#   - TROU D'ISOLATION DE BANC CORRIGÉ (cause d'un échec PRÉEXISTANT de
#     `_test_ui_visibilite_jalon47.py` constaté sur une machine dont le
#     config.json a des sections repliées) : `ui/widgets/collapsible.py` lit et
#     écrit désormais `CONFIG` / `sauver_config` via les GLOBALS de
#     `avastack.ui.app` (`_globals_app()`, motif du jalon 104) au lieu de
#     l'import direct — les mocks `ui.CONFIG` / `ui.sauver_config` des bancs
#     redeviennent EFFECTIFS et le vrai config.json n'est plus écrit pendant un
#     test. En production, comportement IDENTIQUE (même objet / même dict).
#   - `pyright` 0 ERREUR sur les 15 fichiers typés ; `ruff` : seuls les
#     2 avertissements PRÉEXISTANTS de `app.py` (`tracer_evt`, `i_etape`).
#   - Vérifications : garde-fou VERT ; bancs rejoués verts —
#     `_test_cadence_jalon42.py`, `_test_expo_affichage_jalon34.py`,
#     `_test_ui_visibilite_jalon47.py`, `_test_ui_robuste_jalon87.py`,
#     `_test_config_jalon6.py`, `_test_ergonomie_jalon52.py`,
#     `_test_capacites_ui_jalon32.py`, `_test_compo_ui_jalon19.py`,
#     `_test_histo_jalon75.py`, `_test_dialogues_jalon84.py`,
#     `_test_zoom_pleine_res_jalon68.py`, `_test_rafale_fin_rendu_jalon80.py`,
#     `_test_norm_commune_jalon61.py`, `_test_spcc_osc.py`.
#

# v2.58.2 : CHANTIER DE REFACTORING — `ui/config_ui.py` (jalon 104)
#   - Module NEUF (TYPÉ) `avastack/ui/config_ui.py` extrait de `app.py` : mixin
#     `ConfigUI` dont `App` HÉRITE, regroupant la PERSISTANCE de la config de
#     l'interface — `_restaurer_config` (chargement/restauration au démarrage)
#     et `_sauver_config_app` (écriture à la fermeture). Méthodes reprises
#     VERBATIM (`self` reste l'instance `App`) → comportement inchangé AU BIT.
#   - DEUX micro-réécritures ÉQUIVALENTES pour satisfaire `pyright` (aucun
#     changement de comportement) : `isinstance(_hm, str) and _hm in HIST_CODES`
#     (clé `hist_mode`) et `None if v is None else float(v)` (`v is None` ⟺
#     `etiquette == "Off"`).
#   - Surface publique de `app.py` INCHANGÉE (75 symboles) ; import en alias
#     PRIVÉ `_ConfigUI` ; import `MODES_L` retiré de `app.py` (devenu inutile).
#     `pyright` 0 ERREUR sur les 11 fichiers typés.
#   - Vérifications : garde-fou VERT + `_test_config_jalon6.py`,
#     `_test_histo_jalon75.py`, `_test_ui_visibilite_jalon47.py` rejoués verts.
#
# v2.58.1 : CHANTIER DE REFACTORING — `ui/widgets/` (jalon 103)
#   - DEUX modules de l'UI extraits de `app.py` (TYPÉS), sous forme de « mixins »
#     dont `App` HÉRITE — méthodes reprises VERBATIM (`self` reste l'instance
#     `App`), donc AUCUN changement de comportement : le rendu est identique AU
#     BIT.
#       · `avastack/ui/widgets/collapsible.py` — `SectionsPliables` :
#         `_creer_section_pliable` (sections pliables persistées, jalons 95/98/99).
#       · `avastack/ui/widgets/histogram.py` — `PanneauHistogramme` : tracé et
#         gestes de l'histogramme, étage de niveaux (barres Noir/Médian/Blanc,
#         gel/reprise de l'auto) et saturation par couleur R/V/B (jalon 75).
#   - `App` hérite des deux mixins (`class App(SectionsPliables,
#     PanneauHistogramme)`) : `App.<méthode>` et `self.<méthode>` restent valides
#     (les bancs qui font `App._hist_canaux(...)`, `App._maj_histogrammes = …` ou
#     `app._draw_hist()` fonctionnent à l'identique).
#   - SURFACE PUBLIQUE de `app.py` INCHANGÉE (75 symboles, vérifiée par le banc
#     garde-fou). `pyright` (mode `basic`) : 0 ERREUR sur les 10 fichiers typés.
#   - Vérifications : banc garde-fou VERT + `_test_histo_jalon75.py`,
#     `_test_dialogues_jalon84.py`, `_test_ui_visibilite_jalon47.py` rejoués verts.
#
# v2.58.0 : CHANTIER DE REFACTORING — `ui/constants.py` (jalon 102)
#   - PREMIER module de l'UI EXTRAIT de `app.py` : `avastack/ui/constants.py`
#     (TYPÉ) regroupe toutes les CONSTANTES de l'interface — seuils, palettes,
#     listes de choix (géométrie de la fenêtre et de l'histogramme, types SPCC,
#     sections pliables et leur habillage, débruitage live/externe, cadences,
#     plafond de rafale, topologie de re-stack, caméras « pilotées », filtre
#     anti-brutes très défocalisées). Les commentaires explicatifs migrent
#     AVEC les valeurs.
#   - `app.py` les RÉ-EXPOSE à l'identique — SURFACE PUBLIQUE INCHANGÉE (vérifiée
#     par le banc garde-fou : 75 symboles, aucun écart) : les constantes de
#     MODULE (SCORE_MAX_ETOILES, CAMERAS_PILOTEES, FLU_*, FWHM_*, RESTACK_*) sont
#     ré-importées telles quelles ; les constantes de CLASSE de `App`
#     (W_IMG/HIST_*/SPCC_TYPE_*/SECTIONS_NOM_MAP/SECTION_*/VL_DN_*/CADENCES/
#     RAFALE_*/DN_EXT_*) restent des attributs de classe, alimentés par l'alias
#     privé `_const` — `App.<NOM>` et `self.<NOM>` restent valides.
#   - ZÉRO changement de comportement : aucune ligne de logique modifiée, rendu
#     identique AU BIT (hash d'empilement du banc garde-fou inchangé).
#   - `avastack/ui/constants.py` entre dans la LISTE BLANCHE du banc garde-fou ;
#     `pyright` (mode `basic`) : 0 ERREUR sur les 8 fichiers typés.
#   - Vérifications : banc garde-fou VERT + `_test_ui_visibilite_jalon47.py`,
#     `_test_cadence_jalon42.py`, `_test_histo_jalon75.py`,
#     `_test_rafale_fin_rendu_jalon80.py`, `_test_spcc_osc.py` rejoués verts.
#
# v2.57.1 : CHANTIER DE REFACTORING — TYPAGE DE LA FONDATION (jalon 101)
#   - TYPAGE RÉTROACTIF (annotations SEULES, AUCUN changement de comportement)
#     des 7 modules de fondation : `compat`, `config`, `delais`, `journal`,
#     `ressources`, `travail`, `siril_ini`. Paramètres, valeurs de retour et
#     constantes sont annotés ; `delais.borne` devient GÉNÉRIQUE (TypeVar : le
#     type rendu suit celui de `fn`).
#   - `pyright` (mode `basic`) : 0 ERREUR sur ces 7 fichiers — ils entrent dans
#     la LISTE BLANCHE du banc garde-fou (`FICHIERS_TYPES`), vérifiée désormais
#     à CHAQUE jalon.
#   - Les accès volontairement spécifiques à une plateforme (`os.sysconf`,
#     `os.startfile`, `ctypes.windll`) et l'attribut RUNTIME `_avastack_icone`
#     (Tk) portent un `# pyright: ignore[...]` CIBLÉ et commenté : ce ne sont
#     pas des erreurs, seulement des noms absents du typeshed d'un autre OS.
#   - Vérifications : banc garde-fou VERT (pyright 0 erreur sur la liste
#     blanche) + bancs rejoués verts (`_test_config_jalon6.py`,
#     `_test_journal_jalon73.py`).

# v2.57.0 : CHANTIER DE REFACTORING — OUTILLAGE ET BANC GARDE-FOU (jalon 100)
#   - OUVERTURE DU CHANTIER « découpage de app.py + typage intégré » (décision
#     d'architecture du 06/10/2026 ; roadmap des jalons 100→110 dans
#     AVANCEMENT.md). RÈGLE DE FER : ZÉRO RÉGRESSION DE COMPORTEMENT — le rendu
#     reste identique AU BIT ; un jalon qui change le rendu est REJETÉ.
#   - OUTILLAGE DE DEV (jamais des dépendances d'exécution) : `pyproject.toml`
#     (configuration `pyright` + `ruff`) et `requirements-dev.txt` (`pyright`,
#     `ruff` — SIGNALÉS, à installer à la main : aucune CI distante, décision
#     d'Alain). Aucun de ces fichiers n'est embarqué par les installateurs.
#   - STUBS DE TYPAGE `avastack/stubs/` : `zwoasi.pyi` et `qhyccd.pyi` décrivent
#     la surface des SDK caméra OPTIONNELS réellement utilisée (zwo.py / qhy.py),
#     pour que le typage progressif ne les voie jamais comme « import inconnu ».
#     Fichiers de DEV uniquement — aucun comportement changé.
#   - BANC GARDE-FOU `bancs/_test_refactoring_garde_fou.py` (neuf) : LA référence
#     du chantier, REJOUÉE à CHAQUE jalon. Il verrouille ① la syntaxe de TOUS
#     les `.py` du dépôt, ② l'inventaire des symboles PUBLICS de `app.py`
#     (détecte une extraction qui casse l'API), ③ le hash SHA-256 d'un
#     empilement SIMULÉ déterministe (kappa, winsorized, kappa-RGB — le rendu
#     figé AU BIT), ④ `pyright` 0 erreur sur la liste blanche des fichiers
#     typés (IGNORÉ proprement tant que pyright n'est pas installé).
#   - AUCUN changement de comportement : `app.py` n'est PAS modifié par ce
#     jalon. Rejoués verts : garde-fou + bancs d'interface.

# v2.56.1 : COLONNE DE RÉGLAGES — SECTIONS PLIABLES ET CHANGEMENT DE SOURCE
#           RÉPARES (jalon 98 ; retour d'Alain, 06/10/2026 : « positionnement
#           bizarre des sections »)
#   - SECTION « FICHIERS DE TRAVAIL ET JOURNAL » COUPÉE EN DEUX : depuis la
#     v2.51.1 (jalon 95b), le replacement des cadres Cadence/Dossier/Composition
#     dans `_maj_visibilite_cadres` s'ancrait sur le LabelFrame « Fichiers » —
#     packé APRÈS son propre bouton d'en-tête : en mode Dossier/Composition,
#     Cadence et Dossier s'inséraient ENTRE l'en-tête et le contenu, laissant
#     le contenu orphelin sous « Dossier surveillé » (la section PARAISsait
#     repliée alors qu'elle était ouverte). Ancre déplacée sur le bouton
#     d'en-tête de Caméra (TOUJOURS packé — la combobox de source et
#     Démarrer/Arrêter restent visibles en toutes circonstances) : l'ordre
#     devient Fichiers → Cadence → Dossier/Composition → Caméra → Calibration
#     et n'a plus jamais besoin de toucher à « Fichiers ».
#   - TclError « window … isn't packed » AU CHANGEMENT DE SOURCE : si la
#     section Fichiers était réellement repliée (état persisté), l'ancienne
#     ancre n'était plus gérée et Tk levait l'exception DANS
#     `_on_source_choisie` — ABORTANT tout le reste : pas de déconnexion
#     caméra, pas de détection SDK, « ▶ Démarrer » non réactivé, cadres non
#     replacés (l'erreur finissait dans journal.txt). Avec l'ancre Caméra
#     (toujours gérée) + un garde-fou, changer de source est toujours sûr.
#   - ÉTAT REPLIÉ RESPECTÉ : une section (Cadence, Dossier, Composition)
#     repliée par l'utilisateur réapparaissait AVEC son contenu au simple
#     changement de source, mais avec sa flèche ▶ (état incohérent).
#     `_creer_section_pliable` expose désormais `lf._var_etat` et
#     `_maj_visibilite_cadres` ne re-packe le contenu que si la section est
#     dépliée : la visibilité de l'ENSEMBLE (bouton + contenu) suit la
#     source, le pli reste un choix de l'utilisateur.
#   - EN-TÊTE ORPHELIN D'UNE SECTION REPLIÉE DEVENUE INUTILE (trouvé par la
#     sonde de martèlement APRÈS les bancs verts — le cas « section repliée
#     AU MOMENT où elle devient inutile à la source » n'était couvert par
#     AUCUN banc) : la branche « cacher » de `_maj_visibilite_cadres`
#     testait `cadre.winfo_manager()` — l'état du CONTENU, déjà dépacké par
#     le pli — donc ne s'exécutait JAMAIS pour une section repliée : son
#     en-tête restait planté à son ancienne position, flottant au milieu de
#     la colonne jusqu'au prochain changement de source (c'est la cause
#     RÉELLE du « positionnement bizarre » constaté par Alain). La branche
#     teste maintenant l'en-tête AUSSI (`btn.winfo_manager()`) ; et
#     `on_change` (déplier/replier) ne tente plus `pack(after=btn)` quand
#     l'en-tête est lui-même caché (le pli est mémorisé dans `var_etat` et
#     appliqué au prochain changement de source).
#   - Banc `_test_ui_visibilite_jalon47.py` : sections [8] (9 vérifications)
#     et [8d] NEUVES (4 vérifications : l'en-tête d'une section repliée
#     disparaît quand la source la rend inutile, revient AVANT Dossier au
#     retour, toujours replié, contenu à sa place au redépliage) — ordre
#     VRAI du pack (boutons + LabelFrame) en mode Dossier, pli de Cadence
#     conservé au passage en Composition, changement de source sans
#     exception avec Fichiers replié. Rejoués verts : jalons 52, 53, 87,
#     76, 80 — TOUT AU VERT.
# v2.56.0 : CLASSIFICATION DES OBJETS RÉPARÉE (catalogue OpenNGC) + N'ENTOURER
#           QUE LES OBJETS RÉELLEMENT VISIBLES (retours d'Alain, 05/10/2026)
#   - TOUS LES OBJETS « (Nb) » : cause trouvée par sondes réseau — le
#     générateur d'origine du .dat embarqué pointait vers de MAUVAIS ids
#     VizieR : « VII/258 » est un catalogue de QUASARS (pas Messier !),
#     « VII/260 » n'existe pas en table IC, et le repli par défaut
#     « nebuleuse_diffuse » noyait tout code inconnu. Nouvelles sources :
#     OpenNGC (GitHub, CC-BY-SA-4.0 — types propres, cross-ids Messier,
#     tailles, noms communs) + VizieR miroir HARVARD au format VOTable pour
#     Sh2 (VII/20, B1900→ICRS par astropy), Barnard (VII/220A) et LDN
#     (VII/7A) — VizieR Strasbourg répond « Making sure you're not a bot! »
#     (Anubis) et l'asu-tsv de Harvard tronque à ~81 Ko ; le VOTable est
#     complet. .dat embarqué RÉGÉNÉRÉ : 14 178 objets ; M31/M32/M110 =
#     galaxie, NGC 206 = amas ouvert (*Ass), M42 = Cl+N.
#   - CASE « Seulement les objets visibles » (cochée par défaut) : l'entourage
#     n'est dessiné QUE si l'objet est détecté dans l'image affichée
#     (`_detecte_visibilite` : 95e percentile du disque lissé vs médiane de
#     la couronne ≥ max(8 niveaux, 3·σ_MAD)) — l'ÉTIQUETTE reste toujours ;
#     nébuleuses obscures exemptées ; objets sans taille connue sondés à
#     20 px (RAYON_PROBE_INCONNU). Mesuré sur la vraie capture M31 : NGC 206
#     (+5 niveaux, 0,6σ) → plus d'entourage ; M110 (+77, 4,8σ) → entourage.
#     La case entre dans la clé du cache du rendu (`_annote_rendu`).
# v2.55.3 : ÉTIQUETTES À TAILLE D'ÉCRAN CONSTANTE EN PLEINE RÉSOLUTION +
#           RETOUR IMMÉDIAT DE L'APERÇU AU DÉCOCHAGE (retours d'Alain, 05/10)
#   - TEXTES HYPER PETITS À PLEINE RÉSOLUTION : la police des étiquettes était
#     fixe (≈ 11 px DANS le buffer) — sur un rendu pleine résolution (6000 px)
#     réduit à l'écran par ~5, elles tombaient à ~2 px, illisibles. Nouveau
#     paramètre `echelle_police` à TRAVERS la chaîne d'annotation
#     (`generer_image_annotee` → `overlay_objets_celebres` /
#     `overlay_etoiles_brillantes` → `_position_etiquette` /
#     `_rayon_entourage` / `_dessine_entourage`) : textes, épaisseurs,
#     décrochages, marges, fond d'étiquette et plancher des entourages
#     suivent. `_render` calcule l'échelle d'affichage AVANT l'annotation :
#     `echelle_police = 1/échelle-écran` (jamais < 1, plafonné à 12) → taille
#     constante À L'ÉCRAN quel que soit le buffer ou le zoom.
#   - PNG COMPAGNON : même échelle que le dernier rendu à l'écran (repli :
#     taille de l'image / 1600) — le PNG reste ressemblant à l'écran.
#   - « NE REVIENT PAS » AU DÉCOCHAGE : le cache du solveur VeraLux n'avait
#     PAS la résolution dans sa clé (`_vl_params` = réglages seuls) — le
#     résultat PLEINE RÉSOLUTION en cache resservait pour l'aperçu (même
#     clé), l'écran gardait l'ancienne image et ses étiquettes minuscules
#     (jusqu'à ~12 s de chaîne lourde, ou indéfiniment à l'arrêt). La FORME
#     de la source entre maintenant dans la clé : après bascule, l'écran
#     montre IMMÉDIATEMENT l'image d'attente à la BONNE résolution (STF) en
#     attendant la chaîne complète.
#   - CACHE MONO-SLOT de l'overlay (`_annote_rendu`) : à pleine résolution
#     l'annotation recopie ~69 Mo à CHAQUE rendu (pan inclus) — clé =
#     identité du buffer + échelle + état des cases ; le glissement de vue
#     ne re-dessine plus.
#   - Bancs : [12] ajouté au banc overlay (étiquette ~3× plus haute à
#     échelle 3, plancher des entourages suit) — TOUT AU VERT ; save, dedup
#     réelle et VeraLux (jalon 3) rejoués verts.
# v2.55.2 : ÉTIQUETTES COMPRÉHENSIBLES — TYPES, DÉSIGNATIONS NGC, ELLIPSE
#           DE M31 PLUS FINE (retours d'Alain sur sa capture M31 du 05/10)
#   - « (?) » APRÈS LES NOMS : le lecteur du .dat inversait TYPE_MAP avec un
#     dict {v: k} où le DERNIER synonyme gagnait (« nebula ») — inconnu de
#     TYPE_ICON (noms français) → icône « ? » partout. Table inverse
#     EXPLICITE `TYPE_CODE_VERS_NOM` en français (catalogues.celebres).
#   - « 206 (?) » : c'est NGC 206 (nuage d'étoiles de M31, catalogue
#     NGC 2000 / VizieR VII/118) — le générateur d'ORIGINE du .dat stockait
#     les désignations NGC SANS préfixe et les beaux noms en alias SEULS
#     (« 221 » + « M  32 »). Nouveau `_designations_lisibles()` à la
#     LECTURE (répare le .dat DÉJÀ installé, sans régénération ni
#     retéléchargement) : espaces compactés (« M  31 » → « M 31 »),
#     promotion de l'alias préfixé (« 221 » → « M 32 »), préfixe « NGC »
#     pour les nombres nus sans alias préfixé (« 206 » → « NGC 206 » ;
#     no-op sur le format nouveau déjà préfixé).
#   - ELLIPSE DE M31 TROP ÉPAISSE : la mesure ne voyait qu'un crop borné à
#     300 px (le cœur rond de la galaxie) → ratio biaisé rond. Le crop de
#     mesure couvre maintenant l'ÉTENDUE de l'objet (réduction INTER_AREA
#     au-delà de 300 px — coût constant) et les poids sont CLIPPÉS au 99e
#     percentile (une étoile brillante du champ ou un cœur saturé ne
#     dominent plus les moments). Pour un objet DÉBORDANT de l'entourage
#     (taille réelle > plafond 50 %), un prior de finesse par type
#     (`TYPE_RATIO_MAX`) plafonne en plus le ratio mesuré (galaxie 0,45,
#     nébuleuse diffuse/HII 0,55, obscure 0,70, amas ouvert 0,85).
#   - NB : le .dat d'origine classe M31 en « nébuleuse diffuse » (types
#     NGC 2000 mal mappés par le générateur local) — l'icône « (Nb) » peut
#     donc rester imprécise pour les galaxies ; correctif structurel =
#     régénérer le catalogue (telecharger_et_indexer + mise à jour Zenodo),
#     à faire séparément.
#   - Bancs : overlay enrichi ([10] types + désignations préfixées,
#     [11] mesure à l'échelle : ratio 0,40 retrouvé sur un objet géant) —
#     TOUT AU VERT ; non-régression save + dédup réelle (« M 31 »/« M 32 »
#     maintenant, types français) vertes.
# v2.55.1 : ANNOTATIONS LISEIBLES — JAUNE RGB, UNE ÉTIQUETTE PAR OBJET,
#           ENTOURAGE CERCLE/ELLIPSE SELON LA FORME (retours d'Alain, 04/10)
#   - CORRECTION DES CANAUX : le buffer d'affichage est RGB (app.py :
#     cvtColor GRAY2RGB, PNG compagnon écrit tel quel) mais les couleurs
#     étaient définies à la mode OpenCV BGR — le « jaune » s'affichait CYAN
#     (et le « cyan » des étoiles s'affichait jaune). TOUT est maintenant
#     jaune RGB : entourages, textes, lignes de rappel, objets célèbres ET
#     étoiles brillantes (demande d'Alain).
#   - CORRECTION DES TEXTES ILLISIBLES (M31) : le chemin d'annotation appelait
#     `cherche_celebres` SANS déduplication — le catalogue brut renvoie M31 +
#     NGC 224 + « 224 » + « Great Nebula in » aux MÊMES coordonnées (vérifié
#     sur données réelles : 5 entrées pour 2 objets), tous dessinés au même
#     endroit. Nouvelle fonction PARTAGÉE `catalogues.celebres.
#     deduplique_celebres()` (+ `score_designation`), utilisée par
#     l'annotation ET par `_objets_celestes_resolus()` (une seule source de
#     vérité ; le code dupliqué d'app.py est supprimé).
#   - ANTI-CHEVAUCHEMENT refait (`_position_etiquette`) : empilement
#     VERTICAL sous la collision (M31/M32/M110 forment une pile lisible) au
#     lieu du zigzag horizontal qui saturait au bout de 8 essais.
#   - ENTOURAGE « SELON LA FORME » (demande d'Alain) : taille RÉELLE de
#     l'objet (`size_arcmin` convertie en pixels via le WCS — projection de
#     deux points, robuste à l'échelle et à la rotation, plafond 50 % de la
#     plus grande dimension pour les cibles géantes type M31 à 190′) ;
#     forme + orientation MESURÉES dans l'image par moments d'inertie du
#     crop (option A validée par Alain — le catalogue n'a pas d'angle de
#     position ; l'option B, l'ajouter au .dat + régénérer Zenodo, écartée) ;
#     objet rond (ratio ≥ 0,92), trop faible ou trop petit → CERCLE de
#     repli ; taille inconnue → petit cercle 4 px. Étoiles : petit cercle.
#   - Étiquettes d'étoiles : « mag 3,4 » (virgule française) — le « ★ »
#     sortait en « ? » : la police Hershey d'OpenCV ne le contient pas.
#   - Bancs : `_test_annotations_overlay_jalon96.py` enrichi ([6] dédup,
#     [7] forme mesurée : angle 30°/ratio 0,4 retrouvés, rond → None,
#     [8] jaune RGB + plafond/demi-axe, [9] empilement vertical sans
#     chevauchement) — TOUT AU VERT ; non-régression save + dédup réelle
#     M31/M32 rejouées verts ; coût 27 ms pour 10 objets à l'aperçu
#     1600×904 (invisible devant l'étirement ~0,4 s).
# v2.55.0 : ANNOTATION TEMPS-RÉEL DE L'IMAGE AFFICHÉE (JALON 96, ÉTAPES 5-6)
#   - Deux cases INDÉPENDANTES dans le panneau Astrométrie :
#     « Annoter objets célèbres » (catalogue célèbres embarqué) et
#     « Étoiles brillantes » (catalogue Gaia DR3, seuil de magnitude
#     configurable, défaut 8,0), + case « PNG annoté à côté du FITS »
#     (défaut coché). Persistance : clés `annoter_objets`, `annoter_etoiles`,
#     `annoter_sauvegarde`, `seuil_mag_etoiles`.
#   - Overlay dessiné sur une COPIE du buffer d'affichage dans `_render`
#     (UNIQUE point de passage : nouvelle image, réglage, zoom) — `_last_disp`
#     reste PROPRE, les données brutes et les FITS ne sont JAMAIS annotés
#     (linéarité photométrique préservée).
#   - CORRECTION du module `processing/annotations.py` : il appelait
#     `wcs.world_to_pixel(...)` — méthode qui N'EXISTE PAS dans ce projet (le
#     WCS expose `vers_pixels(ra, dec)` → tableau (N, 2)) : chaque étiquette
#     tombait sur une exception et RIEN ne se dessinait.
#   - Nouveau `WcsEchelle` : l'aperçu est une réduction UNIFORME de la grille
#     recadrée (facteur `_echelle_apercu` posé par le worker) — multiplier les
#     coordonnées suffit, aucun re-solve, aucune hypothèse de projection.
#   - Listes de ciel (objets + étoiles Gaia) en CACHE par (centre, champ,
#     seuil) : la lecture du catalogue Gaia (≈ 1 Go) n'est JAMAIS refaite à
#     chaque rendu ni sous le zoom.
#   - PNG compagnon `<nom>_annote.png` écrit à côté du FITS par `_save`,
#     `_save_asseen` et `_save_proc` — jamais d'exception propagée (un PNG
#     compagnon ne doit pas faire échouer la sauvegarde du FITS).
# v2.54.1 : CASE « DEBUG » DÉPLACÉE (FICHIERS DE TRAVAIL ET JOURNAL)
#   - Demande d'Alain : la case « Debug » quitte le panneau Astrométrie et
#     rejoint la PREMIÈRE section de la colonne de gauche
#     (« Fichiers de travail et journal »), à côté du bouton « Journal » —
#     logique : les logs DEBUG vont dans le journal, le réglage vit à côté
#     de son bouton.
# v2.54.0 : POPUP « NOM CIBLE » À RADIO-BOUTONS + DÉDUPLICATION CÉLESTE
#   - Nouvelle méthode `_objets_celestes_resolus()` : objets célèbres DÉDUPLIQUÉS
#     par position (~0,01°) — NGC 224 et M31 sont le même objet aux mêmes
#     coordonnées ; un seul représentant par groupe, avec le MEILLEUR nom
#     (score : Messier « M31 » > NGC/IC préfixé > autre ; un nombre nu « 224 »
#     ou un nom tronqué est le pire). Espaces internes collapsés (« M  31 » → « M31 »).
#   - Nouveau dialogue `_demander_nom_cible()` : radio-boutons listant les
#     objets trouvés (jusqu'à 6, libellé nom — type · mag · taille) + option
#     « Garder « actuel » » quand le champ est rempli ; OK / Annuler.
#   - Remplace le messagebox.askyesno de `_maj_astro_etat` (règle dialogue
#     directe du jalon 84 respectée : plus aucun messagebox direct hors aides).
# v2.53.9 : CORRECTION ATTRIBUTS RA/DEC SUIVI_ASTROMETRIE
#   - Fix : `_nom_cible_astro_only()` et `_nom_cible_pour_sauvegarde()` utilisaient
#     `suivi_astro.ra` / `suivi_astro.dec` au lieu de `ra0` / `dec0` (attributs réels
#     de la classe SuiviAstrometrie). Résultat : `cherche_celebres` appelé avec
#     None → aucun match céleste → pas de popup.
#   - Correction des 2 sites : lignes 2813-2814 et 2856-2857.
# v2.53.8 : POPUP NOM CIBLE À CHAQUE RÉSOLUTION + DEBUG AMÉLIORÉ
#   - Le popup de confirmation s'affiche maintenant à CHAQUE résolution astrométrique
#     (transition non-résolu → résolu), pas seulement la première fois.
#   - Reset de `_astro_name_proposed` : désactivation astrométrie, nouveaux indices,
#     ou nouvelle résolution (via `_astro_was_resolved`).
#   - Debug `_nom_cible_astro_only` : log détaillé de ce que `cherche_celebres` trouve
#     (designation, type, mag, taille) ou "AUCUN objet trouvé".
#   - Pas de fallback FITS dans le popup : n'annonce que le match céleste (catalogue).
# v2.53.7 : CORRECTION POPUP NOM CIBLE + DEBUG SPAM
#   - Fix : le popup de confirmation n'apparaissait pas car `_nom_cible_pour_sauvegarde()`
#     retourne le nom manuel (priorité 1) qui a été pré-rempli depuis FITS.
#     Maintenant `_maj_astro_etat()` récupère le nom d'astrométrie (match céleste)
#     SÉPARÉMENT pour le comparer au champ actuel.
#   - Fix DEBUG spam : `_mettre_a_jour_nom_depuis_fits()` n'est plus appelé à chaque
#     tick UI (~20-30×/s) mais seulement quand `camera.last_file` change
#     (nouvelle brute reçue). Suppression des logs "Aucun last_file" /
#     "Champ déjà rempli" qui noyaient le journal.
# v2.53.5 : LOGIQUE NOM CIBLE FINALE + DEBUG
#   - Remplissage auto depuis l'en-tête FITS (camera.last_file) tant que le
#     champ est vide.
#   - À la première résolution astrométrique : si le champ est vide → adoption
#     directe du nom détecté ; s'il contient déjà un nom différent → popup de
#     confirmation pour le remplacer. Un refus est définitif jusqu'à ce que
#     l'astrométrie soit décochée/recouchée.
#   - Le champ « Nom cible » n'existe plus qu'une fois (panneau Empilement).
#   - Case à cocher « Debug nom cible » dans le panneau Astrométrie → journal détaillé
#     (valeur de auto_nom, contenu du champ, décision adoption/popup/refus, lecture FITS).
# v2.53.4 : DEBUG NOM CIBLE
#   - Ajout d'une case à cocher « Debug nom cible » dans le panneau Astrométrie.
#   - Journalisation détaillée (journal.note) dans `_maj_astro_etat` et
#     `_mettre_a_jour_nom_depuis_fits` lorsque la case est cochée :
#       * valeur de `auto_nom` retournée par `_nom_cible_pour_sauvegarde`,
#       * contenu actuel du champ, décision adoption / popup / refus,
#       * lecture de `camera.last_file` et du nom extrait de l'en-tête FITS.
#   - Permet de comprendre pourquoi la popup n'apparaît pas.
# v2.53.3 : LOGIQUE NOM CIBLE FINALE
#   - Remplissage auto depuis l'en-tête FITS (camera.last_file) tant que le
#     champ est vide.
#   - À la première résolution astrométrique : si le champ est vide → adoption
#     directe du nom détecté ; s'il contient déjà un nom différent → popup de
#     confirmation pour le remplacer. Un refus est définitif jusqu'à ce que
#     l'astrométrie soit décochée/recouchée.
#   - Le champ « Nom cible » n'existe plus qu'une fois (panneau Empilement).
# v2.53.2 : CHAMP « NOM CIBLE » UNIQUE (PANNEAU EMPILEMENT) + POPUP ASTROMÉTRIE + AUTO FITS
#   - Suppression du doublon dans le panneau Astrométrie ; l'Entry reste
#     uniquement dans « Empilement » (var_nom_cible_manual partagée).
#   - À la première résolution astrométrique (vert), une popup propose
#     d'adopter le nom détecté (match céleste ou header FITS). L'utilisateur
#     valide ou refuse.
#   - Périodiquement (dans `_tick_corps`), si le champ est vide, on tente de
#     le remplir depuis l'en-tête FITS de la dernière brute (`camera.last_file`).
# v2.53.1 : CORRECTION BUG D'INITIALISATION + REMPLISSAGE AUTO DU CHAMP « NOM CIBLE »
#   - Initialisation de `var_nom_cible_manual` **avant** la construction de l'UI
#     (évite AttributeError au démarrage).
#   - Dans `_maj_astro_etat`, quand l'astrométrie devient résolue (vert),
#     le champ « Nom cible » est automatiquement rempli avec le nom détecté
#     (match céleste ou header FITS) si l'utilisateur n'a rien saisi.
# v2.53.0 : CHAMP « NOM CIBLE » VISIBLE DANS LE PANNEAU EMPILEMENT
#   - Ajout d'une ligne « Nom cible : » avec Entry lié à var_nom_cible_manual
#     (créée dans le panneau Astrométrie) afin que l'utilisateur voie et
#     modifie le nom de l'objet principal sans aller dans l'onglet astrométrie.
#   - La valeur manuelle a priorité absolue pour les 4 boîtes « Enregistrer »
#     (logique _nom_cible_pour_sauvegarde : manuel > match céleste > header FITS).
# v2.52.0 : NOMMAGE AUTOMATIQUE DES FICHIERS SAUVEGARDÉS (JALON 84)
#   L'option « nom_cible_auto » (cochée par défaut) propose désormais un nom
#   de fichier dérivé de l'en-tête FITS de la dernière brute :
#   mots-clés lus dans l'ordre OBJECT → OBJNAME → TARGNAME → TARGET,
#   premier non-vide retenu, nettoyé pour Windows (\\ / : * ? " < > | → _,
#   espaces multiples collapsés, blancs aux extrémités retirés).
#   Suffixe optionnel (_traite, _tel_que_vu…) et extension (.fits) ajoutés.
#   - avastack/processing/astrometrie.py : nouvelle fonction
#     nom_objet_entete_fits(chemin) → str|None
#   - avastack/ui/app.py : nouvelle méthode _nom_cible_auto(suffixe, extension)
#     appelée par les boîtes « Enregistrer sous » / « Enregistrer tel que vu »
#   - Configuration : clé nom_cible_auto (bool, True par défaut)
#   - Correctifs collatéraux : celebres.py (syntax + constante ECHELLE_ANGLE),
#     processing/__init__.py (SuiviAstrometrie import)
# v2.51.0 : _tick_corps TAIL LA ZONE « Traitement externe » QUAND ELLE
#   DISPARAÎT (retour macOS du 01/10/2026 — v2.48.1 et v2.48.2 ; pas de
#   changement de comportement depuis la v2.50.0). Tcl/Tk 8.6.12 sous macOS
#   27 (Tahoe, arm64) invalide ponctuellement le bouton `btn_ext`
#   (« invalid command name ".!…!labelframe13.!button" ») ; l'exception
#   remontait dans `_tick → _tick_corps → btn_ext.config`, mais
#   `_journal_erreur_tick` filtre par épisode (`_tick_err_sig`) → UNE seule
#   ligne dans le journal même si l'exception revient 33 fois/seconde. La
#   boucle survivait mais TOUS les rafraîchissements d'interface étaient
#   MORTS (les boutons ne répondaient plus, les combobox ne s'ouvraient
#   plus, le statut ne se mettait plus à jour) — Alain voyait « plein de
#   boutons qui ne répondent pas » sans qu'aucune ligne du journal ne le
#   dise après la première.
#   - avastack/ui/app.py : `_tick_corps` est désormais gardé par
#     `_widget_vivant()` (introduit au jalon 87 sur `_maj_libelle_fit`) sur
#     LES TROIS widgets de la zone « Traitement externe » — `btn_save_proc`,
#     `lbl_ext` (deux occurrences) et `btn_ext`. Un widget invalide TAIT
#     toute la séquence : pas d'exception, pas de ligne de journal, `_tick`
#     se replanifie normalement et les autres rafraîchissements (statut,
#     histogramme, mesures, etc.) continuent.
#   - AUCUNE clé de configuration ne change. AUCUN changement de
#     comportement visible côté UI. AUCUN changement sur Windows ou
#     Linux — `winfo exists` rend simplement True.
#   - Banc neuf `bancs/_test_ui_robuste_v2_48_3.py` :
#       [1] statique : aucun `.config(` direct dans `_tick_corps` n'est
#           plus atteint sans `_widget_vivant` à proximité ;
#       [2] dynamique : détruire `btn_ext` puis appeler `_tick_corps` ne
#           lève PLUS `TclError` et `_journal_erreur_tick` n'écrit plus.
#   - 11 bancs rejoués verts (87, 47, 22, 75, 80, 41, 5, 12, 59, 65, 69).
# v2.50.0 : ICÔNE DE L'APPLICATION (barre de titres + barre des tâches) ET
#   VIGNETTES MSIX DEPUIS L'ICÔNE RÉELLE (chantier « Microsoft Store »).
#   - assets/avastack.ico (multirésolution 16/32/48/256) + assets/avastack.png
#     (512×512, M31) : SOURCE unique de l'icône (fournis par Alain).
#   - avastack/ressources.py (NEUF) : `poser_icone_fenetre()` — Windows prend
#     le .ico (net à toutes les tailles), ailleurs le PNG via `iconphoto` ;
#     dossier résolu depuis `__file__`, donc identique gelé ou non.
#   - avastack/ui/app.py : la fenêtre principale reçoit l'icône au démarrage.
#   - installer/windows/msix/build_msix.py : les VIGNETTES (tuiles) sont
#     désormais recadrées « cover » + LANCZOS depuis assets/avastack.png, aux
#     tailles du manifeste (repli géométrique stdlib si PIL ou icône absents).
#   - Les QUATRE canaux embarquent assets/ : avastack.iss (SetupIconFile,
#     icône des raccourcis, copie), paquet ZIP, packers ET installateurs
#     Linux/macOS.
#   - bancs/_test_msix_jalon92.py étendu : vignettes depuis la vraie icône et
#     pose effective de l'icône de fenêtre.
#   - installer/windows/msix/images_fiche.py (NEUF, jalon 94) : images de la
#     FICHE Store depuis une capture RÉELLE — la capture telle quelle (≥1366×768
#     exigé) + tuiles 1:1 2160², 16:9 1920×1080, 4:3 1200×900 (fenêtre ENTIÈRE
#     sur fond flou ; `--recadrer` = « cover »), `--masquer x,y,l,h` neutralise
#     les zones PERSONNELLES (le dépôt reste sans donnée personnelle),
#     `--verifier` contrôle un dossier écrit. Banc bancs/_test_images_fiche_
#     jalon94.py. (Les vignettes DU PAQUET, elles, restent faites par
#     build_msix.py depuis l'icône : ce sont DEUX choses distinctes.)
# v2.49.0 : SCAN QHY RÉPARÉ POUR UNE APPLICATION GELÉE + PACKER WINDOWS GELÉ
#   (PyInstaller) — PREMIER PAS DU CHANTIER « MICROSOFT STORE » (jalon 91).
#   Contexte : la voie Store (MSIX, IMMUABLE : le venv ne peut pas se créer à
#   l'installation) impose une application GELÉE, et le gel a été MESURÉ
#   faisable au jalon 90 (214 Mo, fenêtre ouverte, mode « Simulée (démo) » OK,
#   `sdk_loader`/VeraLux/DLL QHY trouvés SANS modification). Le SEUL point de
#   code qui cassait en gelé était le scan QHY.
#   - avastack/cameras/qhy.py : `_commande_scan()` choisit la commande du scan
#     isolé. En dev, INCHANGÉ (`python -c …`). GELÉ, l'exe ne sait pas exécuter
#     `-c` (MESURÉ : il ignore ses arguments et rouvre l'interface) : il se
#     relance donc LUI-MÊME avec le drapeau `DRAPEAU_SCAN` (« --scan-qhy »).
#   - AVAStack.py : mode interne `--scan-qhy`, traité AVANT toute interface
#     (un JSON sur stdout, aucune fenêtre) : c'est le point d'entrée de l'enfant.
#   - installer/windows/build_avastack_frozen.ps1 : NOUVEAU packer — PyInstaller
#     `--onedir --windowed`, les 4 DLL constructeurs ajoutées par NOM (décision
#     confirmée : on les garde dans TOUS les installateurs), artefact
#     `output/avastack-frozen-<version>-windows/` + `.zip` (SHA-256 affiché).
#   - bancs/_test_gel_qhy_jalon91.py : 10 vérifications (drapeau unique, les deux
#     commandes, bout en bout RÉEL du drapeau, contrat du parent inchangé).
#   Le reste du pipeline tourne DÉJÀ en gelé sans aucun changement.
#   - installer/windows/msix/ : NOUVEAU — le paquet MSIX (voie Microsoft Store,
#     jalon 92). `build_msix.py` (staging + AppxManifest + vignettes PNG en
#     stdlib + appel de MakeAppx) et `signer_msix.ps1` (certificat auto-signé +
#     signtool, pour l'essai local). Le MSIX EMBALLE le paquet GELÉ (un MSIX est
#     immuable : on ne peut pas y créer un venv). Application déclarée pleine
#     confiance (Windows.FullTrustApplication + rescap:runFullTrust). Banc
#     `bancs/_test_msix_jalon92.py` (20 vérifications) ; paquet construit et
#     signé en réel (105,7 Mo). PIÈGE MESURÉ : le certificat doit être approuvé
#     dans Cert:\LocalMachine\TrustedPeople (PAS CurrentUser, qui donne l'erreur
#     0x800B0109 « racine non approuvée ») — donc une session ADMINISTRATEUR.
# v2.48.2 : LES INSTALLATEURS WINDOWS VÉRIFIENT L'EMPREINTE DU PYTHON TÉLÉCHARGÉ
#   (durcissement, sans aucun changement de comportement de l'application).
#   Contexte : un testeur a reçu « Impossible d'exécuter un fichier depuis le
#   dossier temporaire... Erreur 4551 : une stratégie de contrôle d'application a
#   bloqué ce fichier » — et la MESURE a montré que Smart App Control, APPLIQUÉ,
#   laisse pourtant exécuter depuis %TEMP% un fichier SIGNÉ (banc
#   `bancs/_diag_execution_temp.ps1`). Une cause possible restait : un
#   téléchargement INTERROMPU, donc un fichier TRONQUÉ sans signature valide,
#   aussitôt parti à l'exécution avec un message incompréhensible.
#   - installer/windows/avastack.iss : le fichier de python.org est désormais
#     vérifié par son empreinte SHA-256 (define PythonSha256, fonction
#     VerifierEmpreintePython → GetSHA256OfFile) AVANT d'être exécuté, avec UNE
#     seconde tentative si le fichier est incomplet ou altéré ; l'échec est dit
#     en clair (connexion, proxy/antivirus, ou installation manuelle de Python).
#   - installer/windows/install_avastack.ps1 (paquet ZIP) : MÊME contrôle
#     (Get-FileHash), DEUX tentatives, MÊME empreinte des deux côtés ; la
#     création du venv n'est pas touchée.
#   - installer/windows/install_avastack.ps1 : CORRECTION — la désinstallation
#     n'efface plus les raccourcis Bureau / Menu Démarrer quand l'installation a
#     été faite avec -SansRaccourci (marque ajoutée dans VERSION.txt, relue à la
#     désinstallation ; les installations antérieures gardent l'ancien
#     comportement). Défaut constaté le 02/10/2026 : une installation d'essai
#     pouvait effacer les raccourcis d'une AUTRE installation.
#   Les QUATRE installateurs (Windows .exe et .zip, Linux, macOS) sont reconstruits
#   pour porter la même version ; seul le couple Windows change de contenu utile.

# v2.48.1 : LA CHAÎNE COULEUR S'APPLIQUE ENFIN À LA VUE « TRAITÉE » — CORRECTION
#   (constat d'Alain, 01/10/2026 : « les corrections de couleurs ne sont plus
#   dans le traitement externe et celles du live ne sont pas appliquées sur
#   l'affichage de la vue traitée »). Le jalon 85 avait sorti la chaîne couleur
#   (SCNR, SCNR doux, démagenta, boost du rouge) de la chaîne LINÉAIRE externe
#   pour qu'elle suive l'ÉTIREMENT — mais les synchros de vue (`_sync_vl_*_vue`)
#   continuaient de la COUPER en vue « traitée », comme du temps où la chaîne
#   externe la portait. Résultat : en vue « traitée » (résultat ⚡ GraXpert/BXT),
#   l'écran ET le fichier « tel que vu » ne portaient plus AUCUNE correction de
#   couleur — l'image restait VERTE.
#   - avastack/ui/app.py : `_sync_vl_scnr_vue`, `_sync_vl_scnr_doux_vue`,
#     `_sync_vl_demagenta_vue` et `_sync_vl_boost_vue` suivent désormais la CASE
#     seule (plus de condition de vue) : les corrections APRÈS étirement
#     s'appliquent DANS LES DEUX VUES, avec les MÊMES réglages que le live
#     (aucun jeu de réglages séparé, aucune clé de configuration nouvelle).
#     Les corrections PRÉ-étirement (neutralisation du fond, bruit chromatique)
#     RESTENT coupées en vue « traitée », ainsi que GraXpert/débruitage/netteté
#     live : elles SONT dans la chaîne externe ⚡ — les refaire à l'affichage
#     serait un DEUXIÈME traitement.
#   - Aucune clé de configuration ni aucun réglage par défaut ne change : à
#     cases décochées (défaut), l'affichage reste identique AU BIT.
#   - Bancs adaptés au contrat neuf : `_test_couleurs_jalon22.py`,
#     `_test_couleurs_immediat_jalon39.py`, `_test_boost_rouge_jalon86.py`,
#     `_test_pleine_res_traitee_jalon69.py`.
#   MÊME VERSION — LA BOUCLE D'INTERFACE NE PEUT PLUS GELER (retour du testeur
#   macOS, 30/09/2026, v2.47.0 : « ce n'est pas mieux »). Son journal se
#   terminait par `TclError: invalid command name "…!labelframe7.!label11"` dans
#   `_tick` → `_maj_libelle_fit`. CAUSE : `_tick` se replanifiait en DERNIÈRE
#   ligne (`after(30, _tick)`) — la moindre exception tuait la boucle POUR DE
#   BON, donc l'interface restait GELÉE (les clics ne répondent plus). Le
#   widget était devenu invalide (arbre de widgets détruit : fermeture de la
#   fenêtre, ou boîte de dialogue NATIVE macOS pendant laquelle un `after` en
#   attente se déclenche).
#   - avastack/ui/app.py : `_tick` est dédoublé en un ORDONNANCEUR (`_tick`) et
#     un CORPS (`_tick_corps`). L'ordonnanceur protège le corps et REPLANIFIE
#     dans un `finally` : une exception n'arrête plus jamais la boucle ; elle
#     est ÉCRITE au journal UNE fois par épisode (`_journal_erreur_tick`, sinon
#     un widget durablement détruit produirait 33 exceptions par seconde).
#   - `_planifier_tick` MÉMORISE l'identifiant `after` (`_tick_id`) ;
#     `_on_close` l'ANNULE (`after_cancel`) AVANT `root.destroy()` — sans cela,
#     un `after` orphelin se déclenche sur l'arbre détruit (« invalid command
#     name ») et la fermeture peut ne pas aboutir.
#   - `_widget_vivant()` : `winfo exists` (seule interrogation qui ne lève pas
#     sur un widget détruit) permet aux rafraîchissements de se TAISIR au lieu
#     d'échouer ; `_maj_libelle_fit` l'utilise (c'était EXACTEMENT la ligne du
#     journal macOS : un widget créé n'est pas un widget VIVANT).
#   - Banc NEUF `bancs/_test_ui_robuste_jalon87.py` (4 sections, 12
#     vérifications) : widget détruit sans exception, `_maj_libelle_fit` muet,
#     boucle replanifiée malgré l'exception et JAMAIS deux fois par tour,
#     `after` annulé à la fermeture. Série rejouée verte : 84, 5, 75, 47, 40,
#     79, 74, 73, 77, 80, 22, 39, 86, 85, 41.
# v2.48.0 : LA CHAÎNE COULEUR SUIT L'ÉTIREMENT, LA L* EST PRÉSERVÉE, ET LE SHO
#   GAGNE — OU PAS — SON DORÉ (jalons 85 et 86). Déclencheur : le constat
#   d'Alain sur son empilement SHO NGC 2237 (« vert par défaut, manque de
#   doré »), avec trois exigences : la variante FIDÈLE SIRIL (préservation de la
#   L*), « l'UI doit respecter l'ordre des traitements », et pas d'exclusivité
#   SCNR/démagenta (en SHO la teinte magenta coexiste avec l'excès de vert).
#   MESURES QUI ONT DÉCIDÉ (ses données, AVANT tout code) :
#     ① le SCNR des jalons 22/23 ÉTEINT l'objet — L* de la nébuleuse 56,5 → 25,8
#        (composite SHO étiré VeraLux) et 82,5 → 9,8 (VeraLux live) ;
#     ② son fichier « empilement traité (linéaire) » était ÉCRÊTÉ EN VERT (excès
#        max 5,9·10⁻⁸ pour 100 % des pixels, contre 1,6·10⁻¹ sur le même
#        empilement d'origine) : c'est la chaîne LINÉAIRE qui portait le SCNR ;
#     ③ le moteur VeraLux est LIÉ (même plancher, même échelle, même MTF pour les
#        trois canaux) : le déséquilibre Ha/SII des brutes traverse tout
#        l'étirement (piste « étirement par canal » MESURÉE puis REFERMÉE : elle
#        mène au cyan).
#   - avastack/processing/couleurs.py : `scnr` / `scnr_doux` / `demagenta`
#     prennent `preserve_luminance=True` (défaut, comme Siril et PixInsight :
#     « lightness is preserved by default », `-nopreserve` l'annule) — la L* CIE
#     (Lab) du pixel est rendue APRÈS le retrait, sur les SEULS pixels réellement
#     corrigés, avec un garde de résolution `SEUIL_REMISE_LUMINANCE = 1e-6` : une
#     correction plus petite que le pas d'affichage n'est pas une correction, et
#     un empilement déjà écrêté par un SCNR antérieur ne doit pas voir des
#     millions de pixels retouchés par l'aller-retour Lab. `amount=1,
#     preserve_luminance=False` rend le résultat des jalons 22/23 AU BIT ;
#     `amount=0` rend l'entrée au bit.
#   - avastack/processing/display.py : la chaîne couleur est appliquée APRÈS
#     l'étirement (`couleur_apres_etirement`) — solveur VeraLux, `process()`
#     STF/manuel et `rendu_pleine_resolution` ; le sous-tuple `coul` du job
#     passe à 8 éléments (forces + préservation) avec déballage TOLÉRANT.
#   - avastack/ui/app.py : la chaîne couleur QUITTE les trois chaînes LINÉAIRES
#     (⚡ mono, ⚡ composition, « tel que vu ») — le fichier linéaire ne porte
#     plus le SCNR et n'est plus écrêté en vert ; le job de la chaîne externe
#     passe de 15 à 12 éléments (les cases 4/5/6 sont retirées du cadre, une note
#     explique où la couleur se règle désormais) et `AVAAPPLI` ne liste plus que
#     les corrections pré-étirement réellement appliquées ; les clés `ext_scnr*`
#     ne sont plus écrites — et sont RETIRÉES d'une configuration antérieure
#     (seule exception assumée à la règle « ne touche pas aux entrées
#     inconnues » : elles ne décrivent plus aucun réglage).
#   - UI : cadre « Couleur de l'objet (APRÈS étirement) » — case « Préserver la
#     luminosité (L*) » (cochée par défaut) + curseurs « Force du SCNR » et
#     « Force du démagenta » ; ordre des cadres revu pour que l'écran dise
#     l'ordre RÉEL des traitements : Fichiers → Caméra → Calibration → Empilement
#     → Fond et grain (AVANT étirement) → Netteté live → Affichage → Couleur de
#     l'objet (APRÈS étirement) → État des calculs → Traitement externe → Sortie
#     (AUCUN réglage, aucune clé et aucun comportement ne changent : seuls les
#     PARENTS des widgets). Clés `vl_preserve_luminance`, `vl_scnr_force`,
#     `vl_demagenta_force`.
#   - JALON 86 — `couleurs.boost_rouge(img, force, preserve_luminance=False)` :
#     boost du ROUGE (SII) MASQUÉ À L'OBJET par les centiles de luminance
#     40 → 97 (le gain suit la lumière du pixel : 0 dans le fond, 1 sur l'objet),
#     bornes `BOOST_ROUGE_MIN/MAX/DEFAUT = 1,00 / 4,00 / 3,00`, appliqué EN
#     DERNIER dans `couleur_apres_etirement` — APRÈS le SCNR, car le SCNR retire
#     l'excès de vert AU-DESSUS de (R+B)/2 : appliqué après le boost, il en
#     reprendrait une partie, donc les deux s'ADDITIONNENT au lieu de se
#     combattre. Le FOND reste identique AU PIXEL (écart nul mesuré à ×1,5,
#     ×3,00 et ×4,00) et l'outil est une identité AU BIT à force 1,00 comme à
#     toutes cases décochées. UI : case « Boost du rouge (SII) — masqué à
#     l'objet », DÉCOCHÉE par défaut (c'est une retouche ESTHÉTIQUE, pas la
#     correction d'un défaut de rendu : un rendu par défaut reste inchangé au
#     bit) + curseur « Force du boost » ; clés `vl_boost_rouge` /
#     `vl_boost_force` (config ET `_reglages_rendu`, donc le fichier « tel que
#     vu » suit l'écran) ; sous-tuple du job solveur 6 → 8 éléments.
#   - MESURES DE DÉCISION, gardées au dépôt (`bancs/_diag_couleur_dore_jalon85.py`
#     et `bancs/_diag_dore_choix_jalon86.py`) : ① le diagnostic du jalon 85
#     reproduisait la chaîne dans le MAUVAIS ORDRE (neutralisation AVANT le
#     recalage) — l'ordre réel est fit → neutralisation → chroma → étirement →
#     couleur (avec le bon ordre, le fond redevient neutre et chaud, comme à son
#     écran) ; ② le VERT vu à l'écran venait des CURSEURS, pas du principe : à
#     SCNR 0,55 le boost 1,60 laisse 61 % de l'objet vert ; à SCNR 0,75 (même
#     boost) il n'en reste que 5 % (88 % doré). Le Linear Fit, mesuré tel quel,
#     monte le rouge au PLAFOND (gain 4,000) et le bleu à 3,162 (le cœur OIII
#     part au cyan) avec une saturation d'objet plus basse (0,32 contre 0,41).
#     DÉCISION D'ALAIN (30/09/2026) : il garde SON Linear Fit « gain + offset » ;
#     le boost reste livré comme option DISPONIBLE et DORMANTE (décochée).
#   - Bancs NEUFS : `_test_couleur_luminance_jalon85.py` (7 sections,
#     19 vérifications : scènes synthétiques + ses empilements M31 réels +
#     NGC 2237 SHO réel ; 0 pixel de régression au bit) et
#     `_test_boost_rouge_jalon86.py` (7 sections, 28 vérifications).
#   - Bancs ADAPTÉS au contrat neuf (AUCUN rendu changé) :
#     `_test_couleurs_jalon22.py` (les formules historiques sont désormais
#     testées à `preserve_luminance=False`, la L* rendue est mesurée AU DÉFAUT
#     avec son témoin, sections externes réécrites pour le job 12-tuple et la
#     chaîne qui a déménagé), `_test_dn_jalon7.py` et
#     `_test_chroma_halo_jalon65.py` (indices du job externe),
#     `_test_bxt_entete_jalon69.py` (`AVAAPPLI` ne dit plus SCNR),
#     `_test_gradient_couche_jalon24.py` et `_test_gx_lot_externe_jalon83.py`
#     (jobs remis au format courant, commentaires compris). 30 bancs rejoués,
#     TOUS VERTS.
# v2.47.0 : PREMIER RETOUR UTILISATEUR macOS — DIALOGUES ATTACHÉS À LA FENÊTRE,
#   FENÊTRE MISE DEVANT, ET UN GEL D'INTERFACE QUI SE MESURE (jalon 84).
#   Constat RÉEL (testeur sous macOS 27 « Golden Gate », 30/09/2026) :
#   « l'UI a quelques soucis (boutons qui ne sont pas toujours cliquables, par
#   exemple le bouton "Dossier", mais qui le deviennent après que j'ai cliqué
#   frénétiquement dessus)… le bouton permettant de choisir le dossier à
#   surveiller ne répond pas… le bouton flat reste désespérément inactif ».
#   - avastack/ui/app.py : TOUS les dialogues (dossier, ouverture, enregistrement,
#     information, avertissement, erreur) passent par six aides qui posent
#     `parent=<fenêtre>`. Sur macOS, Tk ouvre SANS `parent` un panneau ou une
#     alerte APPLICATIVE LIBRE (NSOpenPanel / NSAlert non attaché), qui peut
#     rester DERRIÈRE la fenêtre principale — laquelle attend la réponse (attente
#     modale) : l'application paraît alors insensible, et les clics ne produisent
#     rien tant qu'ils n'atteignent pas la boîte invisible. Avec `parent=`, macOS
#     ATTACHE la boîte à la fenêtre (feuille) : elle est toujours devant.
#     47 appels directs remplacés ; un banc STATIQUE refuse tout appel direct
#     résiduel (un seul oublié ramènerait le défaut).
#   - `main()` : sur macOS, `activer_fenetre()` (lift + `-topmost` bref +
#     `focus_force`) — une application Tk lancée par un lanceur ou depuis un
#     terminal n'est pas « activée » par macOS à l'ouverture, et ses premiers
#     clics servent alors à activer l'application au lieu d'atteindre le widget.
#     La version de Tcl/Tk est désormais JOURNALISÉE au démarrage (piste d'un
#     Tk trop ancien soulevée par le testeur : elle doit être lisible sans avoir
#     à la demander).
#   - La boîte maison « ce dark/flat s'applique à : » est MAPPÉE avant son grab
#     puis levée : un grab posé sur une fenêtre pas encore affichée est au mieux
#     sans effet, au pire bloquant (macOS comme X11).
#   - avastack/ui/reactivite.py (NEUF) : GUET DE GEL du fil d'interface — un fil
#     démon compare l'horloge au BATTEMENT posé par `_tick` (30 ms) et écrit au
#     journal, avec la PILE du fil fautif, tout blocage au-delà de 1,5 s (5
#     rapports au plus par session, un par épisode de gel). C'est ce qui rend
#     « les boutons ne répondent pas » MESURABLE au lieu d'être supposé. Il ne
#     démarre PAS sans fenêtre affichée ni avec `AVASTACK_SANS_GUET=1` : un banc
#     masqué n'a pas de clic perdu à expliquer et ne doit pas voir ses mesures de
#     temps faussées (défaut réellement observé : la CONSTRUCTION d'une interface
#     dure 1,6 s et était rapportée comme un gel).
#   - Banc NEUF `bancs/_test_dialogues_jalon84.py` (7 sections, 28 vérifications,
#     TOUT AU VERT) : contrôle STATIQUE du source, `parent` posé sur les chemins
#     RÉELS de l'application (dossier surveillé, dark, enregistrement, dossier de
#     travail, information, avertissement, erreur), options historiques
#     conservées (titre, types de fichiers, extension), aucun `parent=None` quand
#     la fenêtre est détruite, boîte maison affichée avant son grab, et le guet
#     éprouvé sur un gel volontaire (durée + pile qui nomme le fichier fautif,
#     un seul rapport par gel, épisode suivant rapporté, débrayages).
#   - Régression : 25 bancs relancés VERTS (dont rafale_fin_rendu_jalon80, qui
#     avait révélé l'effet de bord du guet sur les mesures de temps des bancs).
# v2.46.0 : LE GRADIENT GraXpert DE LA CHAÎNE EXTERNE (⚡) PART EN UN SEUL LOT
#   (jalon 83) — décision d'Alain du 30/09/2026, prise APRÈS MESURE sur trois
#   machines. POURQUOI : le jalon 81 avait mis en lot le gradient du SOLVEUR LIVE
#   et de l'EXPORT pleine résolution, mais le TRAITEMENT EXTERNE (⚡, chaîne par
#   couche du jalon 24) appelait encore ses trois couches l'une APRÈS l'autre —
#   or chaque appel paie un démarrage FIXE (~3,4 s mesurés, IDENTIQUES sur iGPU
#   Intel, RTX 4070 et RTX 4060 Ti : c'est le chargement du binaire et du modèle,
#   pas le calcul).
#   MESURÉ sur ses 3 vraies couches (8,2-8,3 Mpx), série → lot :
#     11,45 → 4,92 s (+57 %) sur RTX 4060 Ti 8 Go / Linux (CUDA) ;
#     10,73 → 4,28 s (+60 %) sur RTX 4070 12 Go / Windows (DirectML) ;
#     10,12 → 4,24 s (+58 %) sur l'iGPU de dev (DirectML) —
#   sorties IDENTIQUES AU BIT dans les trois cas (même binaire, mêmes arguments,
#   entrées indépendantes : le parallélisme ne change que l'instant de départ).
#   Le DÉBRUITAGE GraXpert, lui, RESTE EN SÉRIE, et c'est mesuré : son lot ne
#   rapporte rien (−13 % sur iGPU, +12,9 % sur 4070, +1,2 % sur 4060 Ti) car un
#   seul appel sature DÉJÀ le GPU (100 % d'utilisation sur les trois), et il
#   coûte 2,2 à 3,7 Go de VRAM par appel (9,6 Go pour trois, mesuré).
#   - avastack/ui/app.py : `_compo_couches_traitees` — le GRADIENT des couches
#     part en UN lot (`external.live.appliquer_lot`, mémoire bornée par
#     `parallele_max`, repli SÉRIE automatique), avec validation du gabarit de
#     commande ET de l'exécutable AVANT le lancement (leçon du jalon 24 : après
#     substitution, les placeholders n'existent plus), garde « couche vide »
#     conservée et message de progression pendant le lot.
#     ÉCHEC PARTIEL du gradient : la couche fautive garde ses valeurs BRUTES, son
#     message est posé, et la chaîne CONTINUE (avant : tout s'arrêtait) ;
#     ÉCHEC TOTAL : arrêt et message d'erreur, comme avant. Le DÉBRUITAGE
#     (GraXpert IA ou local) garde son ordre et son fonctionnement, et le dossier
#     de la chaîne ne reçoit plus que les FITS réellement utiles (un par couche,
#     uniquement pour le débruitage GraXpert).
#   Test _test_gx_lot_externe_jalon83 (7 cas : égalité AU BIT avec le
#   comportement d'avant — témoin `MAX_PARALLELE = 1` —, chevauchement prouvé par
#   journal, ordre « tous les gradients puis les débruitages », couche vide
#   ignorée, échec partiel qui continue, échec total qui s'arrête, intégration
#   `_run_external_compo` au composite identique AU BIT) ; régression :
#   gradient_couche_jalon24, ext_rgb_jalon14, dn_jalon7, denoise_live_jalon9,
#   gx_parallele_jalon81, etat_calcul_jalon40, save_brute_jalon59,
#   compo_ui_jalon19, fit_canaux_jalon54, graxpert_live_jalon4.
# v2.45.0 : OUTILS EXTERNES PAR COUCHE EN PARALLÈLE (jalon 81) — décision
#   d'Alain du 29/09/2026, après avoir demandé la MESURE de la mémoire avant de
#   coder (et après l'essai de faisabilité de la piste « inférence ONNX en
#   processus », ÉCARTÉE — chiffres en fin d'entrée).
#   POURQUOI : le coût de GraXpert est FIXE par appel — démarrage de son binaire
#   figé puis chargement des 217 Mo du modèle IA, ~2,8 s MESURÉS à chaque
#   invocation — et la chaîne par couche (jalon 24) l'appelait TROIS fois de
#   suite, une par couche de composition : 8,3 s de pur démarrage par passe. Or
#   les couches sont INDÉPENDANTES (fichiers distincts, aucun état partagé) :
#   lancer les trois EN MÊME TEMPS chevauche leurs démarrages.
#   MESURÉ (3 vraies couches d'aperçu, machine de dev) : 13,70 s → 5,58 s
#   (59 %), fichiers produits IDENTIQUES OCTET À OCTET (SHA-256 égaux) ; en
#   pleine résolution 11,88 s → 5,74 s. MÉMOIRE mesurée : ~680 Mo par appel,
#   1,22 Go pour trois (pages du modèle partagées), tout rendu à la sortie.
#   - avastack/compat.py : `memoire_libre()` — octets physiques disponibles,
#     sans AUCUNE dépendance (Windows GlobalMemoryStatusEx, Linux
#     /proc/meminfo, macOS sysconf).
#   - avastack/external/live.py : `MAX_PARALLELE` (3), `parallele_max(nb)` —
#     borné par la mémoire libre (~800 Mo réservés par appel simultané, 1 Go
#     toujours laissé à la machine) — et `appliquer_lot(items)`, qui rend des
#     valeurs IDENTIQUES à des appels en série, avec REPLI SÉRIE automatique
#     (lot d'un élément, mémoire insuffisante, pool de fils en échec, élément
#     sans résultat) : jamais d'image perdue, jamais de trou silencieux.
#   - avastack/processing/display.py (solveur live) et avastack/ui/app.py
#     (`_couches_pleine_resolution`, export pleine résolution) : le GRADIENT par
#     couche part en UN lot ; le DÉBRUITAGE garde son ordre (gradient PUIS
#     débruitage, couche par couche) et les CACHES PAR RÔLE sont intacts.
#   Test _test_gx_parallele_jalon81 (9 cas : bornes de concurrence, chevauchement
#   prouvé par journal, égalité AU BIT avec et sans parallélisme sur le solveur
#   live ET sur l'export, caches par rôle, échec isolé, repli mémoire) ;
#   régression : graxpert_live_jalon4, couleurs_jalon22, denoise_live_jalon9,
#   etat_calcul_jalon40, sharp_live_jalon12, save_brute_jalon59,
#   fond_bleu_jalon62, chroma_nr_jalon63, compo_ui_jalon19, veralux_jalon3,
#   cadence_jalon42, ui_jalon5, multifolder_jalon19, rafale_fin_rendu_jalon80.
#   - PISTE « NOTRE INFÉRENCE ONNX » ÉCARTÉE (même session, essai demandé) :
#     le modèle est tuilable (256×256×3, lot dynamique) et se charge en 0,65 s
#     dans notre processus, MAIS ① l'inférence CPU coûte 119 ms/tuile (3,2 s
#     pour un aperçu : AUCUN gain face à l'appel CLI complet), ② DirectML donne
#     48 ms/tuile (1,36 s) mais épuise la mémoire PARTAGÉE de l'iGPU en pleine
#     résolution, ③ GraXpert reste plus rapide (~20 ms/tuile) et ④ surtout la
#     FIDÉLITÉ est mauvaise : corrélation **0,24** avec son propre modèle de fond
#     (`-bg`) — le prétraitement, le recollement et le lissage de GraXpert font
#     l'essentiel du résultat. L'environnement de l'essai a été restauré
#     (onnxruntime désinstallé, `pip check` propre).
# v2.44.0 : RENDU DÉCLENCHÉ EN FIN DE RAFALE (jalon 80, demande d'Alain,
#   29/09/2026) — « je lance sur des dossiers avec 50 brutes par couche : on en
#   lit 10, on les stacke, et seulement là on lance un rendu ? ».
#   DIAGNOSTIC (mesuré sur SA configuration relevée dans son `config.json` et son
#   journal GraXpert) : le solveur était relancé à CHAQUE nouvel empilement, donc
#   dès la PREMIÈRE brute d'une rafale — une passe ENTIÈRE de la chaîne lourde
#   (GraXpert live par couche) calculée sur une pile à 1 brute, puis une SECONDE
#   passe sur la pile de fin de rafale. Sur son réglage (aperçu 1600 px, GraXpert
#   live seul : 3 × 3,25 s = 9,7 s pour une passe de ~10,5 s), cela faisait ~21 s
#   de calcul par cycle de cadence de 30 s (70 % du temps occupé), dont une passe
#   entière perdue — et l'écran montrait pendant ce temps le STF d'une pile à une
#   brute (bruitée, gradient non retiré).
#   - avastack/ui/app.py : `_tick` ne déclenche plus le rendu à la réception d'un
#     empilement en rafale de DOSSIER (et composition) : il note le DERNIER
#     empilement (`_rendu_differ` / `_rendu_differ_t`) et le déclenche quand la
#     rafale s'est TUE — plus aucun empilement pendant `RAFALE_QUIET_S` (0,35 s)
#     — avec une BORNE (`RAFALE_MAX` brutes empilées depuis le dernier rendu)
#     pour qu'un dossier pré-rempli ne retarde jamais l'affichage indéfiniment.
#     Les sources NON-dossier (caméras, webcam, simulée) gardent le déclenchement
#     immédiat : leur file ne s'accumule pas et le rythme des frames y est déjà
#     le cooldown. `_reinit_etat_session` vide l'attente (aucun rendu fantôme de
#     la session précédente). AUCUN PIXEL NE CHANGE : même chaîne, même pile —
#     seule la DATE du déclenchement change.
#     Test _test_rafale_fin_rendu_jalon80 (logique du déclenchement sur messages
#     fabriqués + bout en bout avec le vrai worker : 1 rendu au lieu de 5 pour
#     une rafale de 6 brutes) ; régression : _test_cadence_jalon42,
#     _test_reset_empilement_jalon76, _test_veralux_jalon3,
#     _test_graxpert_live_jalon4, _test_ui_jalon5, _test_etat_calcul_jalon40,
#     _test_multifolder_jalon19, _test_config_jalon6, _test_save_brute_jalon59.
#   - VÉRIFIÉ AU PASSAGE (question d'Alain : « vérifie que tu utilises bien le
#     modèle 1.0.1 ») : la commande GraXpert de l'application ne passe AUCUN
#     `-ai_version` → c'est la version STOCKÉE dans les préférences de GraXpert
#     qui s'applique (`bge_ai_version` = 1.0.1, confirmé par son journal : « Using
#     AI version 1.0.1 … bge-ai-models\1.0.1\model.onnx »). À savoir : chaque
#     appel CLI RECHARGE ce modèle (217 Mo) — ~2,8 s FIXES par appel (5,6 s sur
#     8,4 Mpx contre 3,25 s sur 1,45 Mpx à l'aperçu) : c'est pourquoi Siril, qui
#     le garde en mémoire, paraît bien plus rapide.
# v2.43.0 : CHANTIER PERFORMANCE ET RÉACTIVITÉ (jalon 79) — TOUT EST LIVRÉ.
#   Demandes d'Alain (29/09/2026) : « optimiser les performances (surtout en
#   live) … maintenant qu'on a une version stable, on pourrait comparer les
#   temps et surtout la non-régression », puis « regarde aussi certains réglages
#   qui s'appliquent après étirement (comme la saturation, mais peut-être
#   d'autres aussi) pour vérifier qu'ils ne relancent pas toute la chaîne, ça
#   donnera de la réactivité visuelle ».
#   RÈGLE DE TOUT LE CHANTIER : **aucun pixel ne change.** Chaque étape est
#   mesurée avant/après par un banc dédié, et les accumulations sont comparées à
#   une référence INDÉPENDANTE (écart 0 exigé).
#   (A) L'INSTRUMENT — banc NEUF `bancs/_bench_performance.py` : 24 étapes du
#       pipeline chronométrées sur une séquence SYNTHÉTIQUE déterministe de
#       8,4 Mpx (la taille de la brute réelle), `--reel <dossier>` pour ajouter
#       une vraie image, référence machine écrite dans
#       `bancs/_bench_performance_ref.json` et comparaison automatique au run
#       précédent. DEUX PRÉCAUTIONS APPRISES EN LE FAISANT : mesures retenues au
#       MINIMUM de N itérations, et écarts NORMALISÉS par une calibration machine
#       (`a + a` float32 8,4 Mpx, au début ET à la fin) — deux runs STRICTEMENT
#       identiques différaient de 10 à 20 % (le premier, machine au repos, est le
#       plus rapide), ce qui faisait crier six fausses « régressions » avec un
#       seuil à 15 % (il est à 25 %).
#   (B) LES VERROUS — l'empilement produit par l'application est comparé à une
#       réimplémentation numpy ÉCRITE DANS LE BANC (kappa et winsorized, rejeu
#       du warmup compris) : **moyennes identiques AU BIT et rejets identiques**,
#       plus trois contrôles sur la mémoire du moteur d'étirement (rendu
#       mémoïsé = rendu recalculé, invariance à gamma/saturations, invalidation
#       par une nouvelle image). Sans ces verrous, « optimiser » n'aurait rien
#       prouvé.
#   (C) LE CŒUR D'EMPILEMENT — `LiveStacker.add` ne crée plus de tableaux
#       temporaires (une quinzaine de float64 de 67 Mo, jetés à CHAQUE frame :
#       c'était l'essentiel des 325 ms mesurés en warmup sur 8,4 Mpx) : tampons
#       préalloués par géométrie, opérations EN PLACE, calcul élémentaire en
#       float32, CARRÉS ET SEUIL DE REJET en float64 — le produit de deux
#       float32 y est EXACT, donc `sumsq` et la décision de rejet restent ceux
#       d'avant, bit à bit. Le travail est réparti par BANDES DE LIGNES
#       (`_en_parallele`, 4 fils au plus : les grandes opérations numpy
#       libèrent le GIL, mesuré ×3,3 sur une opération élémentaire) ; en mode
#       winsorized la médiane/MAD passe par bande, mêmes mathématiques et même
#       découpage en chunks `_CHUNK_PX`, avec un compteur de rejets par bande
#       (aucun verrou). Sur les petites images, UNE seule bande : les bancs
#       restent strictement séquentiels.
#       RÉSULTAT MESURÉ (mono 8,4 Mpx) : `add` kappa 295 → **56 ms (−81 %)**,
#       en warmup 80 → 14 ms, RGB 938 → 181 ms, **WINSORIZED 1 666 → 570 ms
#       (−66 %)**. Contrôles de correction : moyennes identiques AU BIT et
#       compteurs de rejets IDENTIQUES (kappa 517 906 ; winsorized 2 257 140).
#       Regard sur le coût mémoire : ces tampons sont PERSISTANTS (≈ +240 Mo en
#       mono 8,4 Mpx, ≈ +725 Mo en RGB 25 Mpx, PAR stacker — une composition en
#       tient un par rôle) ; ils sont libérés par `reset()` et alloués à la
#       première frame. C'est le prix de la vitesse, il est DIT.
#   (D) LE COMPOSITE MULTI-RÔLES — même diagnostic, même méthode. Mesuré (HOO,
#       2 rôles de 8,4 Mpx) : `composer()` 225 ms, `moyennes()` 107 ms,
#       `mean_avec_canaux()` 342 ms et **522 ms avec les corrections de couleur**
#       — appelé jusqu'à TROIS fois par frame (fin de boucle du worker, couches
#       du solveur, sauvegardes) et à chaque geste « donnée » (gain, SCNR,
#       chroma, cases live). CE QUI COÛTAIT N'ÉTAIT PAS LES MATHS mais des
#       COPIES INUTILES : `.astype(np.float32)` sur des tableaux DÉJÀ en float32
#       (numpy copie quand même), `np.mean` d'une liste d'UN SEUL rôle (une
#       copie de plus), et des bornes de normalisation recalculées à chaque
#       appel alors que le paramètre `bornes` existe pour les FIGER. Livré :
#       copies supprimées (résultat identique AU BIT, mesuré), bornes figées par
#       frame (`_bornes_par_role`), moyenne de rôle mémoïsée sur `n`
#       (`LiveStacker._moyenne_brute`), composite BRUT mémoïsé
#       (`CompositeStacker._memo_compo`) — clé = accumulation, cadre,
#       composition et mode L, JAMAIS les corrections de couleur : un geste de
#       gain RÉUTILISE donc l'assemblage au lieu de le refaire.
#       RÉSULTAT MESURÉ : premier calcul 298 → **163 ms**, GESTE 298 → **0 ms**,
#       `mean()` répété 43 → 0 ms. Contrôles : composite mémoïsé identique au
#       composite recalculé (écart 0), couches identiques ET réutilisées,
#       composite brut INDÉPENDANT des gains, invalidation par toute nouvelle
#       frame.
#   (E) LA RÉACTIVITÉ DES RÉGLAGES D'APRÈS ÉTIREMENT — mesuré d'abord
#       (aperçu couleur 1600x904) : AUCUN de ces réglages ne relançait la chaîne
#       LOURDE (la clé du solveur VeraLux ne contient ni gamma, ni saturations,
#       ni barres de niveaux : ni GraXpert, ni débruitage, ni VeraLux ne
#       repartaient). MAIS chaque geste de souris recalculait pour rien ① les
#       DEUX histogrammes (31 ms) — leurs deux bandes sont tracées AVANT ces
#       étages — et ② tout l'ÉTIREMENT (médiane/σ/p99,9 puis MTF, ~69 ms).
#       Livré : `hist=False` sur gamma, saturation globale et saturation par
#       couleur (même règle que les barres de niveaux depuis le jalon 75),
#       MÉMOIRE de la sortie du moteur (`DisplayProcessor._moteur_stf` ; clé =
#       image source comparée par IDENTITÉ + réglages + stats ; invalidée par
#       `reset()`, `reprendre_auto()` et toute nouvelle frame ; jamais active en
#       `live=True`, où le lissage temporel des stats avance), et `_auto_params`
#       ne calcule plus `_calc_stats` en `live=False` (son résultat était JETÉ).
#       RÉSULTAT MESURÉ : geste gamma 103 → 41 ms, saturation globale 147 →
#       74 ms, geste mono 29 → 3 ms ; dans l'interface réelle, un geste gamma
#       passe de ~137 ms à **28 ms**. TÉMOIN INVERSÉ vérifié : un réglage qui
#       change réellement la donnée (« Coupure du bruit ») recalcule toujours
#       les histogrammes — le drapeau n'est pas figé à False.
#       Banc NEUF `bancs/_test_perf_reactivite_jalon79.py` (18 vérifications,
#       interface réelle : les curseurs sont déclenchés comme au clic, les
#       compteurs enveloppent le code testé).
#   (F) NON-RÉGRESSION — **toute la série de bancs a été rejouée, 55 verts** :
#       jalon 6 (sommes/poids IDENTIQUES à l'ancien algorithme, `array_equal`,
#       et résultat inchangé quel que soit `_CHUNK_PX`), alignements 13 et 15,
#       re-stack 16/18/20, composition 19 (UI et worker compris), crop, calib
#       composition 53, fit canaux 54, norme commune 61, narrowband 21, état
#       calcul 40, reset empilement 76, histo 75, zoom pleine résolution 68
#       (« l'écran = le fichier » au bit), sauvegardes 5/59/échelle/axes/fix,
#       couleurs 22 et 39, sliders 6, moteur 41, débruitage 7/8/9, netteté 11/12,
#       chroma 63/65/67, visibilité 47, pleine résolution traitée 69, unflip 69,
#       espace 72, journal 73, outils 71, catalogues 56/70, sans Siril 77,
#       installeur macOS 78, solveur réel M31, erreurs de branchement 56,
#       astrométrie/photométrie/SPCC 56/58/OSC, caméras (11 bancs) — plus le banc
#       NEUF de réactivité 79 et le banc de performance.
#   GPU ÉCARTÉ SUR MESURES (pas par principe) : l'iGPU Intel partage la mémoire
#   du CPU (2× au mieux, transferts compris) et la RTX n'est pas sur la machine
#   de dev — le banc le rouvrira avec des chiffres le jour où elle y sera.
# v2.42.0 : SANS SIRIL — LES TROIS DONNÉES SE TÉLÉCHARGENT DEPUIS L'INTERFACE
#   (SPECTRES GAIA XP ET BASE DE PROFILS SPCC).
#   Question d'Alain (29/09/2026) : « si tu traites ce point (bouton pour les 48
#   morceaux de spectres Gaia XP), AVAStack pourra fonctionner sans Siril, y
#   compris pour l'astrométrie et les capteurs et filtres SPCC ? »
#   RÉPONSE MESURÉE : NON — ce point SEUL ne suffisait pas. Il manquait DEUX
#   jeux de données : les 48 morceaux de spectres Gaia XP (leur fonction de
#   téléchargement existait mais n'était branchée à AUCUNE interface) ET la base
#   de profils SPCC (capteurs, filtres, références de blanc), qui n'était LUE
#   que chez Siril (`%LOCALAPPDATA%\siril-spcc-database`) : sans elle, la SPCC
#   exigeait Siril installé ET une calibration lancée une fois. Les deux sont
#   désormais téléchargeables : l'application ne dépend plus de Siril pour
#   l'astrométrie (bouton « ⬇ Gaia », déjà là), la photométrie et la SPCC.
#   (1) SPECTRES GAIA XP — « ⬇ Spectres (champ) » ne prend QUE les 1 à 4
#       morceaux qui couvrent la cible (AD/Dec/champ°), comme le script de
#       Siril : ≈ 100-300 Mo au lieu des 10,6 Go des 48 morceaux. Le calcul
#       réutilise la géométrie HEALpix du projet (`pixels_cone` →
#       `pixel_vers_chunk`) — une seule implémentation, confrontée au banc à
#       astropy-healpix (niveau 8) ; « ⬇ les 48 » couvre tout le ciel pour un
#       usage itinérant. Chaîne du téléchargeur inchangée : reprise (Range/206),
#       `.sha256sum` de Zenodo VÉRIFIÉE morceau par morceau, jamais de
#       re-téléchargement d'un fichier conforme.
#   (2) BASE SPCC — « ⬇ Base SPCC » télécharge l'archive ZIP du dépôt public
#       `siril-spcc-database` (GPLv3 ; API GitLab, sans compte et sans nom de
#       branche figé dans le code), vérifie l'archive (ZIP lisible, taille
#       bornée, entrée piégée `..` refusée), l'extrait dans un dossier
#       TEMPORAIRE puis ne pose que les cinq catégories lues (`mono_sensors`,
#       `mono_filters`, `osc_sensors`, `osc_filters`, `wb_refs`) et les .json de
#       référence. Une base complète n'est jamais retéléchargée ; une archive
#       incomplète est REFUSÉE (aucun profil à moitié posé).
#   (3) OÙ EST LA BASE — `spcc_db.dossier_base()` suit désormais : dossier
#       `chemin_spcc` CHOISI (📂 Dossier SPCC) → copie d'AVAStack
#       (`<config>/spcc-database`, cible du bouton) → emplacements de Siril par
#       OS (comportement d'origine conservé). Un dossier VIDE ne masque jamais
#       une base utilisable ailleurs.
#   (4) LA SPCC DEVIENT UTILISABLE SANS REDÉMARRER — à la fin du transfert, la
#       case SPCC est rendue cochable, ses cinq listes remplies et sa sélection
#       par défaut posée (renfort mesuré au banc : sans lui, une base
#       téléchargée n'aurait servi à rien dans la session où on la télécharge).
#   (5) MISE EN PAGE (règle v2.38.9) — DEUX lignes nouvelles de DEUX boutons
#       chacune (jamais trois sur une ligne : `pack` ABANDONNE en silence le
#       widget qui ne tient plus), une ligne d'état « Base SPCC » bornée
#       (`wraplength`) qui DIT le dossier et le contenu, et les quatre boutons
#       entrent dans le contrôle de géométrie NOMMÉ du banc du jalon 72. Un
#       SEUL transfert à la fois : les quatre boutons sont neutralisés ensemble,
#       donc l'état affiché ne peut pas mentir.
#   (6) MESURES — banc NEUF `bancs/_test_sans_siril_jalon77.py`, SANS réseau
#       (serveur HTTP local) et sans Siril : morceaux d'un champ confrontés à
#       astropy-healpix, reprise/206 après effacement, sha256 non conforme
#       refusée, archive piégée et archive incomplète refusées, ordre des
#       dossiers de la base, puis UI réelle (transferts suivis, messages,
#       SPCC utilisable sans redémarrage, géométrie des quatre boutons). Bancs
#       jalon 70 (données de l'astrométrie) et jalon 72 (géométrie) REJOUÉS
#       sans modification. Fichiers touchés : `catalogues/telechargeur.py`,
#       `catalogues/spcc_db.py`, `catalogues/__init__.py`, `ui/app.py`,
#       `README.md`, `INSTALLATION.md`, `installer/README.md`.
#   Repli si régression : v2.41.0.
# v2.41.0 : « RÉINITIALISER L'EMPILEMENT » RÉINITIALISE VRAIMENT, ET LA SOURCE DE
#   FICHIERS SUIT L'INTERFACE (enchaîner deux cibles, mode dossier).
#   Constat réel d'Alain (28/09/2026, session « dossier surveillé ») : « quand
#   j'ai fini avec une cible, je ne peux pas enchaîner avec une autre en
#   choisissant 1 ou des nouveaux dossiers et en cliquant sur Réinitialiser
#   l'empilement — quand je clique sur Démarrer ça empile toujours la cible
#   précédente » / « il faudrait que le bouton réinitialiser réinitialise
#   vraiment » / « Démarrer, quand c'est accessible, ce qui n'est pas toujours le
#   cas ». MESURÉ sur le code d'AVANT (worktree HEAD, flux d'Alain rejoué) :
#   après « Réinitialiser », l'empilement restait ENTIER (3 frames), l'écran
#   gardait l'image de l'ancienne cible, et « ▶ Démarrer » relisait le dossier de
#   la cible PRÉCÉDENTE (aucune frame de la nouvelle) — avec DEUX puis TROIS
#   threads de worker en vie.
#   (1) RÉINITIALISATION — le drapeau `reset_request` n'était lu par le worker
#       qu'en TRAITANT une frame : à l'arrêt (pause, ou aucune brute qui arrive),
#       cliquer ne réinitialisait RIEN. Il est désormais servi en TÊTE de boucle
#       (donc MÊME EN PAUSE) et emprunte EXACTEMENT le chemin de « ▶ Démarrer »
#       (bloc de remise à zéro partagé ; `demarrer` distingue les deux : la
#       réinitialisation ne relance pas l'empilement). La remise à zéro visible
#       (compteurs, archive, écran, lignes d'état) est faite côté Tk
#       (`_reinit_etat_session`, extraite de `_start`) : elle a lieu même si le
#       worker ne tourne pas. Le chemin « une frame arrive » ne consomme plus le
#       drapeau (sinon la remise à zéro complète n'aurait jamais lieu).
#   (2) SOURCE DE FICHIERS — la caméra d'un dossier garde SON dossier et la
#       mémoire des brutes déjà lues : un autre dossier choisi dans l'interface
#       n'était donc jamais ouvert. `_start` compare la source connectée à la
#       configuration affichée (`_source_fichiers_obsolete`, comparaison
#       ABSOLUE et normalisée) et la REFERME si elle ne correspond plus
#       (`_refermer_source_fichiers` — jamais une caméra SDK, dont la
#       réouverture est impossible dans le même process) : le prochain
#       « ▶ Démarrer » la rouvre sur le dossier AFFICHÉ. Le bouton
#       « Réinitialiser » referme aussi la source (une vraie remise à zéro repart
#       des dossiers choisis), vide l'écran avec un message, rend « ▶ Démarrer »
#       accessible et DIT ce qui sera lu (`_resume_source_fichiers`).
#   (3) UN SEUL WORKER — `_start` lançait un SECOND thread `_worker` de façon
#       INCONDITIONNELLE (en plus du bloc « relancer s'il est mort ») : deux
#       threads lisaient la même source et écrivaient le même empilement
#       (mesuré : 2 workers dès le premier « Démarrer », 3 après le suivant).
#   (4) PAUSE ≠ PERTE — une source FICHIERS était LUE pendant la pause puis
#       JETÉE, le fichier restant marqué « traité » (donc impossible à empiler
#       ensuite, même après une nouvelle remise à zéro — exactement la fenêtre
#       « je finis une cible, je prépare la suivante »). Elle n'est plus lue tant
#       que l'empilement est en pause (le dossier est seulement SCANNÉ, pour que
#       « brutes en attente » reste juste) ; une caméra live, elle, continue
#       d'être lue et jetée (c'est ce qui vide la file du SDK).
#   (5) ROBUSTESSE — le worker SURVIT à une source refermée (garde
#       `self.camera is None` en tête de boucle, `read()` protégé, `name`
#       relu sans présumer) : avant, il mourait EN SILENCE sur un `None.read()`
#       et plus aucune frame n'arrivait — sans que rien ne le dise.
#   (6) « ▶ Démarrer » redevient ACCESSIBLE au changement de source non-SDK :
#       la déconnexion le grisait et, pour ces sources (simulée, dossier,
#       composition), aucune connexion automatique ne venait le réactiver.
#   (7) INDICES D'ASTROMÉTRIE — décision d'Alain, suite du même constat : quand
#       le DOSSIER de la cible change, les AD/Dec/champ° de l'ancienne cible sont
#       EFFACÉS (`_effacer_indices_astro` côté interface + nouveau
#       `SuiviAstrometrie.effacer_indices` : `reset()`, lui, CONSERVE les indices
#       d'une session à l'autre — un changement de cible, non). De fausses
#       coordonnées feraient chercher le solveur à l'ancien endroit du ciel, et
#       l'échec serait mis sur le compte du solveur. La saisie repart vide, ce qui
#       rouvre les deux chemins prévus : indices lus dans l'en-tête des brutes du
#       nouveau dossier, puis repli ASTAP. Dossier INCHANGÉ = même cible = indices
#       CONSERVÉS ; une caméra (pas un dossier) n'est jamais concernée. La ligne
#       d'état DIT l'effacement.
#   Banc NEUF `bancs/_test_reset_empilement_jalon76.py` (7 sections : worker réel
#   et VRAIES brutes FITS sur disque — enchaînement cible A → cible B, drapeau
#   servi en pause, indices d'astrométrie effacés au changement de cible et
#   CONSERVÉS sinon, pause sans perte de brute, caméra jamais refermée, bouton
#   réactivé, comparaison des sources) + TÉMOIN « avant » mesuré sur worktree
#   HEAD ; 18 bancs rejoués verts (jalon 15, 16, 17, 18, 19 worker/UI/compo, 20,
#   21, 42, 47, 53, 56 astro et photométrie, 59, 69, 72, 75).
# v2.40.0 : DEUX CORRECTIONS DU TRAVAIL OSC (capteur COULEUR, mode dossier) —
#   L'ASTROMÉTRIE INTERNE SUR CAMÉRA TOURNÉE, ET LA SPCC OUVERTE AUX CAPTEURS
#   COULEUR.
#   Constats d'Alain (28/09/2026, brutes OSC Uranus-C Pro sous N.I.N.A.,
#   NGC 7023, C8 @ 1280 mm → champ 0,5005°, 0,4714″/px) : « l'astrométrie ne
#   trouve pas de résultat » et « la case SPCC dit que c'est que pour du mono
#   multibande, alors que SPCC fonctionne en images couleurs dans Siril — il
#   faut juste lui dire que c'est un capteur couleur et le choisir ».
#   (1) ASTROMÉTRIE — LA ZONE DE SÉLECTION DU CATALOGUE ÉTAIT UN RECTANGLE :
#       `CLIP_MARGE = 1,6` gardait un rectangle (largeur = champ en ξ, hauteur
#       en η), ce qui suppose que l'axe X de la caméra suit les AD — FAUX dès
#       qu'on tourne la caméra (NGC 7023 : −94°). Il ne gardait que 43 % des
#       étoiles de l'image, ET gardait une BANDE HORS IMAGE où se trouvent
#       justement les plus brillantes du secteur. Remplacé par le DISQUE DU
#       CHAMP RÉEL (`masque_champ` : rayon = demi-diagonale de l'image), qui
#       est invariant en rotation — et SANS AUCUNE MARGE (mesuré : ×1,3 échoue
#       sur NGC 7023, le disque gardant alors trop d'étoiles hors image).
#       Deuxième cause, cumulée : le plafond `N_CAT_MAX` (400) était appliqué
#       AVANT la sélection → sur un champ étroit il ne gardait que les plus
#       brillantes d'une zone 2,6× plus large que l'image (9 étoiles dans
#       l'image, appariement impossible) ; il passe maintenant APRÈS.
#       Mesuré (`bancs/_diag_osc_ngc7023.py` sur les brutes RÉELLES + ASTAP en
#       référence croisée) : NGC 7023 RÉSOLU — 68 à 80 appariements, rms 0,43
#       à 0,46 px, 0,4716″/px (ASTAP : 0,4714″/px), et toujours résolu avec des
#       indices faux de ±0,2° / un champ faux de ×0,8 à ×1,1. M31 NON régressé :
#       112 et 115 appariements (contre 86 et 70 avant), écart max 9,5″ avec
#       ASTAP sur 2,6° de champ (distorsion : le juge est le rms sur les MÊMES
#       étoiles, 0,87 px contre 0,87 px pour ASTAP) — banc
#       `_test_solveur_reel_m31.py`.
#   (2) SPCC COULEUR — la SPCC n'était câblée que pour le mono multi-bandes
#       (trois filtres R/G/B distincts). Or la base de Siril décrit aussi les
#       capteurs couleur par TROIS entrées (canaux RED/GREEN/BLUE) et un filtre
#       LPF COMMUN : c'est exactement ce que Siril calcule sur une image OSC.
#       `processing/spcc.py` acquiert `noms_base()` couleur, `capteur_osc`,
#       `filtre_osc` (correspondance EXACTE d'abord : « No filter » ne doit pas
#       devenir « Full spectrum (no filter) », qui le contient), `reponses_osc`
#       (QE des trois canaux × le même filtre), `coherence_osc` (l'exigence
#       « trois filtres distincts » de `coherence_bandes` n'a aucun sens ici) et
#       un paramètre `mode` (« osc » / « mono » ; `None` = décidé par les
#       FILTRES via `mode_bandes`, car le nom du capteur est ambigu — « Sony
#       IMX585 » figure dans les DEUX listes de la base).
#       Côté interface : sélecteur « Type de capteur » (mono / couleur),
#       persisté (`spcc_type`) et restauré AVANT les profils (c'est lui qui
#       décide de la liste) ; en OSC les lignes « Filtre G » et « Filtre B »
#       restent mais sont GRISÉES (un seul filtre couvre les trois bandes) et
#       le défaut est la référence « sans filtre » — jamais un vrai LPF
#       appliqué en silence à une brute sans filtre. Changer de type invalide
#       la mesure (des coefficients d'autres bandes seraient faux).
#       Empilement d'une source COULEUR : nouveau `LiveStacker.gains` (gains
#       R/G/B appliqués avant l'équilibrage et le Linear Fit, jamais sur
#       l'empilement BRUT `corrections=False`), survit au re-stack.
#       Banc NEUF `bancs/_test_spcc_osc.py` (6 sections ; bout en bout sur une
#       image couleur synthétique : pentes R/G 0,6999 et B/G 1,2981 retrouvées
#       pour des gains vrais de 0,70 / 1,30, 41 étoiles) ; `_test_spcc_jalon58`
#       vert (non-régression du chemin mono, y compris ses avertissements).
# v2.39.0 : TROIS BARRES DE NIVEAUX SUR L'HISTOGRAMME (modèle du MINI de
#   SharpCap, place du GRAND), ÉTIREMENT GELABLE DANS LES DEUX MOTEURS, et
#   SATURATION PAR COULEUR.
#   Demande d'Alain (28/09/2026) : « mettre à disposition dans l'histogramme en
#   bas de l'UI 3 barres de réglages, un peu comme le grand histogramme de
#   SharpCap… Forcément lorsqu'on touche à cela, il faut réfléchir à l'étirement
#   existant VeraLux ou STF qui va (ou pas) se refaire à la frame suivante »,
#   puis ses deux précisions : c'est le GRAND histogramme (celui sous l'image),
#   et « si on passe en mode manuel avec figer, il faut que ce soit dispo AUSSI
#   en VeraLux qui étire bien mieux que STF pour dégrossir ».
#   CE QUE DIT SHARPCAP (doc + auteur, vérifié) : le MINI histogramme trace
#   « the image that comes out of live stacking (with live stack stretch
#   applied) » et son étirement n'agit que sur l'affichage (« the stretch in the
#   mini histogram affects the display only — there is no upstream effect ») ;
#   le GRAND (panneau Live Stack) trace la distribution NON étirée en ADU avec
#   les trois lignes « black, mid grey and white » ET des réglages R/V/B qui
#   sont une BALANCE appliquée AVANT l'étirement (« colour adjustments happen
#   before the stretch ») ; il existe un « Lock Stretch » pour geler l'auto.
#   DÉCISION MESURÉE, pas de goût : le STF a bien un point noir, un médian et un
#   point blanc, mais VeraLux n'en a AUCUN (`veralux_core_headless` : une ANCRE
#   + un logD) — « les barres = les points de l'étirement » ne peut donc PAS
#   marcher dans les deux moteurs. Les barres agissent sur la SORTIE DU MOTEUR
#   (modèle du mini), EN DÉCALAGE sur l'auto qui continue de s'ajuster à chaque
#   frame : mêmes gestes, même lecture et effet INSTANTANÉ en STF comme en
#   VeraLux, sans jamais relancer le solveur.
#   (1) `display.niveaux(x, noir, median, blanc)` — étage PUR appliqué après
#       l'étirement et AVANT gamma/saturation, court-circuité à l'identité
#       (0 / 0,5 / 1 = x AU BIT PRÈS : MTF(x, 0,5) = x, les deux opérations
#       étant exactes en binaire) → aucun rendu existant ne bouge tant qu'on ne
#       touche à rien. La position d'une barre EST le niveau : MTF(m, m) = 0,5
#       (le médian place le gris moyen), définition même de SharpCap.
#   (2) gel / reprise (bouton ⏹ / ▶) de l'AUTO DU MOTEUR : STF = stats lissées
#       gelées (elles ne se recalculent plus ET n'avancent plus — sans ça le gel
#       serait un leurre) ; VeraLux = logD RÉSOLU verrouillé (mode « logD forcé »
#       du jalon 3), la reprise rendant la main au fond cible. L'état est DIT en
#       clair sous l'histogramme (« auto FIGÉ (VeraLux) — tes barres seules
#       agissent ») : un étirement figé sans avertissement serait une chute
#       silencieuse.
#   (3) histogramme à DEUX BANDES, avec sélecteur « Les deux / Brut (linéaire) /
#       Sortie du moteur » (une seule bande rend 58 px à l'image) : en haut la
#       distribution LINÉAIRE (axe p99,9 × 1,15 comme avant + repères du moteur
#       « Noir 46,5 % · Médian 59,5 % · Blanc 87,0 % », exacts en STF auto), en
#       bas la SORTIE DU MOTEUR avant les barres, avec les trois barres
#       déplaçables (poignée, prise ±7 px, double-clic = valeur d'origine), la
#       COURBE JAUNE du transfert des niveaux et les repères intrinsèques
#       0 / 50 / 100 %. Champs de saisie chiffrés en % (motif du jalon 27) et
#       « ↺ Auto ». Les étiquettes sont placées par RANG LIBRE et espacées de la
#       hauteur réelle d'un texte (défaut trouvé par le banc : 11 px de pas pour
#       15 px de texte se chevauchaient).
#   (4) DÉFAUT CORRIGÉ AU PASSAGE : les trois courbes étaient normalisées CHACUNE
#       à son propre maximum — trois canaux inégaux se dessinaient à la même
#       hauteur, donc l'histogramme ne disait RIEN de l'équilibre des couleurs
#       (c'est justement l'usage qu'en fait Alain). Normalisation COMMUNE
#       (`App._courbes_pts`, fonction pure, vérifiée par le banc).
#   (5) saturation PAR COULEUR (R/V/B) dans la partie Saturation : SATURATION
#       PAR SECTEUR DE TEINTE — poids triangulaires sur 0° / 120° / 240° (rouge,
#       vert, bleu ; teintes OpenCV en float32, mesurées), qui somment à 1
#       partout (transition douce), appliqués APRÈS la saturation globale ;
#       1,00 = neutre, persistée, reprise par « tel que vu ». NB : les colonnes
#       R/V/B de SharpCap, elles, sont une balance des canaux AVANT l'étirement
#       — elle existe DÉJÀ chez nous (SPCC/Gaia, équilibrage, Linear Fit) et
#       n'est donc pas dupliquée à l'affichage.
#   (6) le calcul de l'histogramme quitte le thread d'ACQUISITION (où il coûtait
#       ~55 ms par frame) pour le thread d'affichage, sur l'image RÉELLEMENT
#       montrée (vue « empilement » comme vue « traitée »), échantillonné à
#       ~400 000 points pour que le coût ne dépende PAS de la résolution.
#   (7) CORRIGÉ APRÈS TES ESSAIS (28/09/2026), quatre points (①② = ton 1er
#       essai, ③ = ton 2e, ④ = ta décision après la mesure) :
#       ① SATURATION PAR COULEUR, 1re écriture REJETÉE : « c_c = Y + k_c·(c−Y) »
#          changeait le canal PARTOUT, quelle que soit la teinte du pixel —
#          mesuré sur un pixel vert franc (0,20 · 0,60 · 0,20), le curseur
#          « Saturation rouge » à 2,00 faisait TOMBER le rouge (0,20 → 0,00),
#          donc le pixel devenait PLUS VERT. Ton constat : « quand je pousse
#          l'un, c'est l'autre couleur qui semble se renforcer ». Ce n'était PAS
#          une inversion d'indice (vérifié : le curseur R agit bien sur le
#          rouge) mais une formule qui n'est pas une saturation par couleur.
#          Remplacée par les secteurs de teinte (5) ; vérifié : pousser « rouge »
#          sature les rouges et laisse les verts INTACTS, un gris ne bouge
#          jamais, un jaune (entre deux secteurs) réagit identiquement aux deux
#          curseurs voisins.
#       ② LA « COLLINE » DE LA BANDE « SORTIE DU MOTEUR » n'est pas une échelle
#          bizarre, et c'est MESURÉ sur ton NGC 7331 : l'axe BRUT est étiré par
#          les étoiles les plus brillantes (p99,9 × 1,15), si bien que le fond
#          n'y occupe que ~1,95 % de l'axe en σ — d'où une AIGUILLE ; la bande
#          « sortie » travaille dans [lo, hi], une plage 2,5 fois plus serrée,
#          et la MTF y a une pente locale de ×1,60 → le même fond y fait 7,7 %
#          de l'axe en σ, donc une colline de ~29 % de large. C'est exactement
#          ce que fait l'étirement : ouvrir les ombres. Pour lever le doute,
#          un repère « fond x % » (MESURÉ sur la somme des trois canaux) est
#          désormais tracé à la pointe de la colline. ATTENTION À LA CIBLE, et
#          c'est une rectification d'une formulation trop vague de la 1re
#          livraison (« la cible du moteur = 25 % ») : il n'y a PAS de cible
#          universelle — le STF vise `display.target` (curseur « Luminosité du
#          fond du ciel », DÉFAUT 0,25) et VeraLux vise `vl_target_bg` (curseur
#          « Luminosité du fond visée (VeraLux) », défaut 0,20, et 0,16 chez
#          Alain sur son M31). MESURÉ sur un empilement réel (NGC 7331, VeraLux
#          mode fond cible, marque = pic de l'histogramme de sortie) :
#          0,12 → médiane 11,9 % / pic 12,3 % ; 0,16 → 15,8 % / 16,6 % ;
#          0,20 → 19,8 % / 21,7 % ; STF 0,25 → 24,9 % / 23,6 %. Autrement dit la
#          marque SUIT le réglage de l'utilisateur à ~1 % près (pic ≠ médiane :
#          la distribution est asymétrique), et la cible est maintenant écrite
#          dans la ligne d'état du panneau (« fond visé 16 % (VeraLux) », ou
#          « cible du fond 25 % (STF) ») — les deux curseurs de cible la
#          rafraîchissent, et « , calcul en cours » s'ajoute quand le solveur
#          VeraLux n'a pas encore rendu (l'écran montre alors l'image d'attente
#          STF, dont le fond est à 25 % : la ligne ne doit pas annoncer un fond
#          visé que la marque ne peut pas encore refléter).
#       ③ LES BARRES NE SUIVAIENT PAS LE GESTE QUAND L'EMPILEMENT ÉTAIT FINI
#          (ton 2e constat, 28/09/2026 — reproduit et MESURÉ au banc) : « si on
#          touche aux barres quand l'empilement est fini, l'image change alors
#          que la position de la barre ne change pas, ou pas complètement, comme
#          si le bas n'était pas rafraîchi ». Cause : `_draw_hist()` n'était
#          appelé QUE par la mise à jour des DONNÉES (`_maj_histogrammes`, une
#          fois par frame) et par le sélecteur de bandes — le glissement
#          appliquait bien la valeur et re-rendait l'IMAGE, mais ne retraçait
#          jamais le PANNEAU : sans frame, il restait figé sur la position de
#          DÉPART (et à 0,2 fps une frame venait le rattraper par sauts, d'où la
#          barre « à moitié » déplacée). Le même défaut latent existait pour
#          « ↺ Auto », la saisie chiffrée et la remise à zéro de session quand
#          aucune image n'était encore affichée. Corrigé : glissement (chaque
#          pixel), relâchement, double-clic, ↺, saisie et nouvelle session
#          RETRACENT immédiatement — et SANS recalculer l'histogramme, la courbe
#          étant tracée sur la sortie du moteur AVANT l'étage de niveaux (une
#          barre ne la change pas). Coût MESURÉ d'un tracé complet : 3,1 ms
#          contre ~80 ms pour l'image, il peut donc suivre chaque pixel de
#          souris. Banc étendu : poignée réellement TRACÉE = position de la
#          valeur, zéro recalcul pendant le geste, et contre-épreuve faite sur
#          l'ancien code (contrôle qui échoue, donc contrôle qui sert).
#       ④ ÉCHELLE EN Y DE LA BANDE BASSE, RÉGLABLE (ton choix, 28/09/2026,
#          pris après mesure) : case « Échelle y linéaire (bande basse) ». En
#          LINÉAIRE, la hauteur d'un bac est PROPORTIONNELLE à son nombre de
#          pixels — le fond devient un vrai PIC au lieu de la colline, et les
#          rapports entre canaux deviennent les vrais rapports de comptes
#          (vérifié au banc : ×100 pour des comptes 1000/10, là où le log
#          comprime à ×2,9). MESURÉ SUR TES FRAMES (20 de ta session de
#          15 h 37, moyennées, aperçu 1600 px, STF auto) : la largeur à
#          mi-hauteur du fond passe de 170 bacs (66 % de l'axe) en LOG à
#          27 bacs (10,5 %) en LINÉAIRE ; en échange la queue tombe de 34 px à
#          0,65 px (p99 des pixels) — nébuleuse et étoiles quittent la courbe —
#          et les bacs visibles passent de 251/256 à 151/256. La bande HAUTE
#          garde TOUJOURS le log : mesurée en linéaire, elle ne laissait que
#          10 bacs visibles sur 256 (une aiguille) — plus aucun diagnostic
#          (piqué, clipping, dominante). DÉFAUT = LOG (une config.json d'avant
#          la case garde donc le rendu d'avant), case persistée ; les BARRES,
#          les repères, le « fond x % » et la courbe jaune (transfert, échelle
#          propre) sont en x : ils ne bougent pas d'un pixel. Basculer ne
#          recalcule AUCUN histogramme et ne re-rend PAS l'image (les bacs
#          sont en mémoire — règle du défaut ③), et l'échelle est DITE dans la
#          ligne d'état : une échelle muette serait un piège, la même courbe
#          ne raconte pas la même chose en log et en linéaire.
#   MESURES (son empilement réel NGC 7331, 11 880 s, aperçu 1600 px) : axe brut
#   0..0,0331 avec le fond à 52 % et p99/p99,9 à 57/87 % ; auto lo 0,01518
#   (46,3 %) · hi 0,02868 (86,6 %) · m 0,3636 ; fond affiché 65/255 (≈ la cible
#   25 %) ; un rendu complet = 82 ms d'étirement + 36 ms pour les DEUX
#   histogrammes + 3 ms de tracé. Non-régression : 40+ bancs rejoués verts.
#   Banc NEUF `bancs/_test_histo_jalon75.py` (11 sections) : identité au bit,
#   MTF(m,m) = 0,5, parité écran/fichier AU BIT avec barres + gel, gel/reprise,
#   saturation par couleur, coût indépendant de la résolution, échelle commune
#   des courbes, géométrie (positions, prise, glissement, LE TRACÉ QUI SUIT LE
#   GESTE sans aucune frame ni recalcul, étiquettes bornées ET sans
#   chevauchement), l'ÉCHELLE Y log/linéaire de la bande basse (hauteur
#   proportionnelle aux comptes, bande haute INTACTE, retour au log AU BIT, case
#   persistée), UI réelle, chaîne linéaire intacte. Bancs RÉPARÉS :
#   jalon 47 (il attendait « Caméra » en 1er alors que le cadre « Fichiers de
#   travail et journal » est en tête depuis la v2.38.9) et jalons 19 (ils
#   lisaient l'histogramme dans la file de l'UI).
#   Doc : CLAUDE.md — leçon PROPOSÉE (en attente d'accord) : ce que SharpCap
#   nomme mini vs grand histogramme, et POURQUOI les barres de niveaux vivent
#   après le moteur (VeraLux n'a ni point noir ni point blanc). Repli si
#   régression : v2.38.11.
#
# v2.38.11 : LE DÉMARRAGE NE PEUT PLUS SE BLOQUER (NAS, montage réseau, pare-feu).
#   Constat RÉEL d'Alain (27/09/2026, Linux, v2.38.10) : « cette version ne se
#   lance pas (ni depuis application, ni depuis ligne de commande) — pas
#   d'enregistrement dans le journal ; en ligne de commande ça affiche juste la
#   version ».
#   CAUSE MESURÉE (avec SA contre-épreuve : `nftables` arrêté → la même version
#   démarre) : ses dossiers de COUCHES R/G/B sont sur un **NAS** (et dans
#   config.json) ; un `stat`/`listdir` sur un montage réseau INJOIGNABLE attend
#   le montage INDÉFINIMENT (autofs n'a pas de délai). Or l'application
#   INSPECTAIT ces dossiers AVANT d'afficher (détection des outils à l'import du
#   module, dossier de travail, catalogues — dont `_on_astro`, appelée par la
#   restauration de la configuration) : la fenêtre ne venait donc jamais. Et
#   comme la PREMIÈRE ligne du journal était écrite APRÈS la mesure de
#   l'environnement, elle n'existait pas non plus — panne totale, muette. L'audit
#   du code, lui, ne montrait rien : il n'y avait pas de bug, seulement des
#   mesures de disque NON BORNÉES.
#   (1) module NEUF `avastack.delais` : `borne(fn, defaut, delai)` exécute une
#       mesure dans un fil DÉMON et rend `(valeur, abouti)` — au-delà du délai on
#       ABANDONNE, et l'interface le DIT. Délai dans `delais.DELAI_DEFAUT` (un
#       seul endroit à régler ; un banc peut le réduire pour éprouver le cas) ;
#   (2) `journal.etape()` : « miette de pain » écrite AVANT chaque étape qui
#       touche le disque — si elle se bloque, la dernière ligne du journal la
#       NOMME (c'est ce qui a manqué pour diagnostiquer en une minute) ;
#   (3) DÉMARRAGE : la première ligne du journal est écrite SANS AUCUN accès
#       disque (version, interpréteur, argv), et la mesure d'environnement est
#       bornée ; son échec est DIT (« environnement NON MESURÉ — un accès disque
#       BLOQUE : montage réseau NAS injoignable ? pare-feu ? ») ;
#   (4) INTERFACE : toute mesure de disque devient DIFFÉRÉE (après l'affichage) et
#       BORNÉE — nettoyage des résidus, dossier de travail, état des outils,
#       catalogues — dans UN fil démon dont les résultats passent par une file et
#       sont appliqués par `_tick` (jamais de Tk hors du fil d'interface) ; les
#       libellés annoncent « mesure en cours… » puis disent la vérité (« espace
#       NON MESURÉ », « ILLISIBLE », « état NON MESURÉ ») au lieu de garder un
#       texte trompeur ; la ligne de travail n'appelle plus `disk_usage` depuis le
#       fil Tk ;
#   (5) `external.detection` ne touche PLUS le disque À L'IMPORT (commandes par
#       défaut = valeur persistée ou repli binaire nu) : la détection réelle se
#       fait après l'affichage, bornée (`detecter_outils`), et la re-détection
#       d'un binaire disparu (v2.38.5, options conservées) suit la même voie ; les
#       MONTAGES RÉSEAU sont écartés des racines balayées et le PATH passé à
#       `shutil.which` est privé de ses dossiers réseau ;
#   (6) `travail.type_systeme()` / `sur_montage_reseau()` (le point de montage le
#       PLUS LONG décide, comme pour le tmpfs) — `est_tmpfs` s'appuie dessus ;
#   (7) les sondes d'un GESTE restent immédiates, mais BORNÉES quand elles
#       précèdent une boîte de dialogue (dossier initial).
#   Banc NEUF `bancs/_test_demarrage_non_bloquant_jalon74.py` (17 vérifs) :
#   `delais.borne` (résultat, délai chronométré, jamais d'exception), la miette de
#   pain, le point d'entrée malgré une mesure bloquée, **App(root) construit en
#   moins d'une seconde MALGRÉ trois sondes qui dorment 30 s**, les lignes qui
#   disent la vérité, les montages réseau écartés, et — mesuré dans un
#   SOUS-PROCESSUS — « import = zéro `which`/`glob` ».
#   Bancs RÉPARÉS au passage (causes consignées dans CLAUDE.md) :
#   ① jalon 72 bloquait sur un `messagebox.showinfo` NON INTERCEPTÉ (prouvé
#      préexistant : le banc de la version intacte bloque au même endroit, pile
#      mesurée au `faulthandler`) ;
#   ② jalons 70 et 71 attendaient les sondes SYNCHRONES : ils POMPENT désormais la
#      boucle d'événements jusqu'à ce que la mesure différée remplisse les lignes
#      (et leurs doublures de `shutil.which` acceptent le mot-clé `path`).
#   Doc : LISEZMOI Windows/Linux (« un NAS injoignable ne retient plus
#   l'ouverture »), CLAUDE.md (règle : le démarrage ne fait aucune mesure
#   susceptible de bloquer). Repli si régression : v2.38.10.
#
# v2.38.10 : LES LIGNES À TEXTE LIBRE NE PERDENT PLUS RIEN (astrométrie,
#   catalogues, re-stack) — même famille que le bouton « Journal » de la v2.38.9.
#   Constat RÉEL d'Alain (27/09/2026) : « le champ et le bouton pour récupérer
#   les coordonnées depuis les brutes ne sont pas visibles sans agrandir la
#   colonne ».
#   MESURE (géométrie Tk, avec chemins et messages LONGS comme les siens) —
#   CINQ widgets étaient abandonnés par `pack`, tous sur des lignes « à texte
#   libre » :
#   ① ligne d'astrométrie : ≈490 px requis pour 318 px disponibles → le champ
#      « champ° » ET le bouton 📷 n'étaient pas affichés ;
#   ② ligne des catalogues : le libellé du chemin est INSÉCABLE (un chemin n'a
#      pas d'espace, donc `wraplength` ne le replie PAS) → 📂 et « ⬇ Gaia »
#      abandonnés dès que le chemin est long (`~/.local/share/siril`) ;
#   ③ ligne de re-stack : un message long (≈110 caractères) faisait disparaître
#      le bouton ⓘ ;
#   et QUATRE lignes d'état étaient ROGNÉES (texte coupé, information perdue) —
#   jusqu'à 740 px requis pour 318 px affichés, dont le message qui explique
#   l'absence du catalogue Gaia.
#   (1) RÈGLES DE MISE EN PAGE appliquées partout : les petits boutons se posent
#       AVANT le texte libre (`side="right"`) et un texte libre reçoit une
#       LARGEUR BORNÉE (`wraplength` pour une phrase, `width` en caractères pour
#       un chemin) — plus rien ne peut manger la ligne ;
#   (2) astrométrie : TROIS lignes (case / AD + Dec / champ° + 📷) ;
#   (3) catalogues : DEUX lignes (chemin borné à 44 caractères, queue conservée,
#       puis « 📂 Dossier » et « ⬇ Gaia ») — le libellé porte son préfixe, la
#       ligne d'origine à trois widgets n'existe plus ;
#   (4) lignes d'état (astrométrie, catalogues, photométrie, re-stack) :
#       `wraplength` — les messages se replient au lieu d'être coupés ;
#   (5) banc jalon 72 : AUDIT DE GÉOMÉTRIE de toute la fenêtre (widget écrasé /
#       libellé rogné / widget débordé) exécuté avec des TEXTES LONGS, plus les
#       cas nommés (📷, 📂 Dossier, ⬇ Gaia, ⓘ, champ°) — c'est le contrôle qui
#       manquait pour attraper cette famille de défauts du premier coup.
#   Doc : CLAUDE.md (règles de mise en page). Repli si régression : v2.38.9.
#
# v2.38.9 : LA LIGNE « DOSSIER DE TRAVAIL » ET LE BOUTON « JOURNAL » SONT ENFIN
#   VISIBLES (constat RÉEL d'Alain, 27/09/2026, capture d'écran à l'appui :
#   « pas de chemin pour temp et pas de bouton journal », sur la v2.38.7).
#   MESURE (géométrie Tk réelle) : les deux reproches étaient FONDÉS, pour deux
#   raisons distinctes —
#   ① le bouton « Journal » n'était JAMAIS AFFICHÉ : les trois boutons ne
#      tenaient pas sur une ligne (cadre de 318 px = texte 243 + « Ouvrir » 43 +
#      « 📂 » 28) et `pack` abandonne SILENCIEUSEMENT le widget qui n'a plus de
#      place (`winfo_ismapped()` = 0) ;
#   ② la ligne était à y≈2421 px sur les 3218 px de la colonne DÉFILANTE de
#      gauche : sous le pli, donc invisible tant qu'on ne défile pas (et la
#      molette n'agit que si le pointeur est SUR le panneau).
#   (1) la ligne et ses boutons passent à DEUX lignes (le texte, puis les
#       boutons) : plus rien ne peut être écrasé ;
#   (2) ils remontent EN HAUT de la colonne, dans un cadre dédié « Fichiers de
#       travail et journal » — indicateur GLOBAL (où vont les fichiers lourds,
#       espace restant) et point d'entrée du DIAGNOSTIC : c'est là qu'on regarde
#       d'abord ; le cadre « Traitement externe (long) » garde son rôle, avec un
#       renvoi commenté vers le nouvel emplacement ;
#   (3) libellé à `wraplength=300` (chemin long + espace libre lisibles).
#   Banc `_test_espace_jalon72.py` : la GÉOMÉTRIE est désormais vérifiée (les
#   trois boutons mappés, et la ligne dans la zone visible SANS défilement) —
#   c'est exactement ce qui manquait pour attraper ce défaut. Doc : LISEZMOI
#   Linux/Windows (où est la ligne), CLAUDE.md (leçon : `pack` abandonne un
#   widget qui ne tient pas — le vérifier par `winfo_ismapped()`, pas à l'œil).
#   Repli si régression : v2.38.8.
#
# v2.38.8 : LES ÉCHECS DE DÉMARRAGE CONNUS SONT EXPLIQUÉS (session sans bureau,
#   Tkinter absent) — le journal a servi dès son premier jour.
#   FAITS (Alain, 27/09/2026, machine Linux) :
#   ① la v2.38.7 lancée par SSH, donc SANS BUREAU, est morte sur `tk.Tk()`
#      (`_tkinter.TclError: no display name and no $DISPLAY environment
#      variable`) : échec d'USAGE normal, mais qui ne disait rien d'actionnable ;
#   ② sa relance depuis le bureau a fonctionné, et le journal a nommé
#      l'environnement réel — `exe=/home/alain/.local/share/AVAStack/venv/bin/
#      python`, `Tk 8.6/8.6`, `travail=/home/alain/.cache/avastack (115,3 Go
#      libres)` — ce qui VALIDE au passage le repli hors tmpfs de la v2.38.6 sur
#      sa machine (son `/tmp` est bien un tmpfs) ;
#   ③ À NE PAS CONFONDRE : la panne de la v2.38.6 lancée depuis le MENU
#      Applications (aucune fenêtre, aucun message) reste SANS EXPLICATION — le
#      journal n'existait pas encore, il n'en existe donc AUCUNE trace, et toute
#      attribution (session SSH, venv, bibliothèque) serait une supposition.
#   (1) `journal.conseil_installation()` : conseil ACTIONNABLE pour les deux
#       échecs CONNUS — ① pas de session graphique (lancer depuis le bureau,
#       `ssh -X`, ou `DISPLAY`) ; ② Tkinter absent du python utilisé (paquet
#       SYSTÈME : apt `python3-tk`, dnf `python3-tkinter`, pacman `tk`) — et ""
#       pour toute autre cause : jamais de conseil inventé ;
#   (2) `journal.sans_affichage()` : détection à DEUX indices (message de Tk, et
#       `DISPLAY` vide SOUS LINUX seulement — la variable n'existe ni sous
#       Windows ni sous macOS, où l'on ne conclut que sur le message) ;
#   (3) `journal.rapport_echec()` : UNE mise en forme du message d'échec fatal
#       (conseil + fichier/ligne + chemin du journal), utilisée par les deux
#       points d'entrée (`AVAStack._echec()` s'y ramène) ;
#   (4) doc : LISEZMOI Linux (les deux cas, avec les commandes exactes),
#       CLAUDE.md (leçon de méthode : JAMAIS d'attribution de cause sans trace,
#       et expliquer un échec d'usage au lieu de le laisser en traceback).
#   Banc `_test_journal_jalon73.py` : section [6] (conseils, détection sans
#   affichage, absence de conseil inventé). Repli si régression : v2.38.7.
#
# v2.38.7 : SI L'APPLICATION NE DÉMARRE PAS, ELLE LE DIT — journal, message
#   visible, plus aucun échec muet au lancement (constat RÉEL d'Alain,
#   27/09/2026, machine Linux : « l'appli ne se lance pas sous linux (elle se
#   lance sous windows) », puis, relancé par le menu : « rien du tout : aucune
#   fenêtre, aucun message »).
#   CAUSE DE MÉTHODE : l'application n'a AUCUN journal (déjà la cause du
#   silence de l'astrométrie en v2.38.4) et son seul canal d'erreur est
#   `stderr` — or elle est lancée par une entrée de menu (`.desktop`,
#   `Terminal=false`) ou par `~/.local/bin/avastack` : tout échec AVANT
#   l'affichage (dépendance absente du venv, `tkinter` manquant, exception dans
#   la construction de l'interface) est donc invisible ET sans trace. L'audit
#   de la v2.38.6 (diffs, archive Linux, installateur, chaîne d'imports) n'a
#   montré AUCUNE cause statique certaine : ce qui manquait, c'est la MESURE —
#   d'où le filet ci-dessous, qui la rend possible.
#   (1) module NEUF `avastack.journal` : journal sur disque
#       (`<config>/journal.txt`, rotation à 1 Mio, jamais d'exception),
#       `note()`, `erreur()` (traceback COMPLET conservé + texte court à
#       montrer), `trace_env()` (versions, exécutable, Tk, OS, répertoire
#       courant, dossier de travail et son espace libre), `montrer()` (boîte de
#       dialogue Tk si possible, sinon `stderr`) et `ouvrir()` ;
#   (2) FILET DE DÉMARRAGE aux deux points d'entrée : le journal est ouvert
#       AVANT le premier import de l'application, TOUT (import de l'interface
#       compris) est enveloppé, et un échec est journalisé PUIS MONTRÉ — un
#       démarrage raté dit désormais pourquoi. `python -m avastack` n'est plus
#       un second chemin à maintenir : il exécute le MÊME script (`runpy`) ;
#   (3) ÉTAPES de démarrage journalisées (interface, configuration, nettoyage
#       des résidus, « prêt », « arrêt ») et erreurs de RAPPEL d'interface
#       (`Tk.report_callback_exception` → journal, au lieu d'un `stderr` que
#       personne ne voit) ;
#   (4) bouton « Journal » dans le cadre « Traitement externe », à côté du
#       dossier de travail : il ouvre `journal.txt` (`travail.ouvrir_chemin`,
#       qui ouvre aussi bien un FICHIER qu'un dossier) ;
#   (5) test de DÉMARRAGE RÉEL à l'installation Linux : `install_avastack.sh`
#       importe `avastack.ui.app` dans le venv et AFFICHE l'erreur exacte, au
#       lieu de conclure « installation terminée » sur une application
#       incapable de démarrer.
#   Doc : LISEZMOI Linux/Windows (« si l'application ne démarre pas »),
#   CLAUDE.md (leçon : tout échec au lancement doit laisser une trace ET être
#   montré). Banc NEUF `bancs/_test_journal_jalon73.py`. Repli : v2.38.6.
#
# v2.38.6 : L'ESPACE DISQUE SE DIT — FIN DE L'ÉCRITURE PARTIELLE SILENCIEUSE
#   (constat RÉEL d'Alain, 27/09/2026, Linux : « Erreur : 24962352 requested
#   and 10902832 written » pendant BlurX, outil pourtant détecté au vert).
#   CAUSE MESURÉE (df -h + du de sa machine) : `/tmp` est un tmpfs de 4,6 Go que
#   l'application REMPLISSAIT ELLE-MÊME (2,8 Go de dossiers `avastack_frames_*`
#   à 32 Mio la frame) pendant que 116 Go dormaient sur le disque. Le message
#   vient de `numpy.ndarray.tofile()`, appelé par astropy pour écrire les
#   données d'un FITS (`io/fits/util.py::_array_to_file` délègue à
#   `ndarray.tofile`) : écriture PARTIELLE (10 902 832 octets sur 24 962 352,
#   soit tout ce qui restait de libre) — signature d'un volume plein, pas d'un
#   chemin invalide. Trois défauts démontrés : ① le plafond d'archivage des
#   frames était de 20 Go EN DUR, donc inopérant dans un volume de 4,6 Go ;
#   ② rien ne nettoyait les résidus d'une session morte ; ③ l'échec ne disait ni
#   le fichier, ni la cause, ni le volume (et le dossier de travail était effacé
#   par le `finally`, donc indiagnosticable).
#   (1) module NEUF `avastack.travail` : dossier de travail EFFECTIF (réglage >
#       repli hors tmpfs > temporaire système), création UNIQUE des dossiers
#       temporaires (`creer_dossier`), espace libre du volume, détection tmpfs
#       (`/proc/mounts`), messages chiffrés (`texte_octets`, `verifier_espace`),
#       plafond calculé sur l'espace réel (`plafond_effectif`), nettoyage des
#       orphelins (`nettoyer_orphelins`) et ouverture du dossier ;
#   (2) RÉGLAGE + BOUTON « dossier de travail » dans l'interface (choix
#       persistant, espace libre affiché, alerte si le volume est un tmpfs,
#       bouton « Ouvrir ») — l'utilisateur peut le poser sur son disque de
#       données ; rafraîchi toutes les 10 s ;
#   (3) ÉCRITURE ATOMIQUE et CONTRÔLÉE (`images.ecrire_fichier`, `ecrire_fits`) :
#       espace vérifié AVANT d'écrire, fichier écrit en `.part` puis RENOMMÉ,
#       partiel TOUJOURS supprimé — plus jamais de FITS/PNG tronqué qui a l'air
#       valide ; une seule route d'écriture FITS pour toute l'application ;
#   (4) MESSAGES CLAIRS (`traduction_erreur_ecriture`) : « écriture incomplète
#       (10,4 Mo sur 23,8) — plus d'espace sur le volume de « /tmp » (1,2 Mo
#       libres, en RAM : tmpfs) : libérez de l'espace ou changez le dossier de
#       travail » ; erreurs ENOSPC/quota/`ulimit -f` nommées ;
#   (5) CONTRÔLE D'ESPACE AVANT la chaîne externe (image × nb d'étapes) : refus
#       immédiat et chiffré, au lieu d'un échec après plusieurs minutes ;
#   (6) PLAFOND D'ARCHIVAGE RÉEL : `min(20 Go, 50 % de l'espace libre)`,
#       recalculé à chaque frame — le garde-fou se déclenche enfin ;
#   (7) FICHIERS DE TRAVAIL CONSERVÉS en cas d'échec (FITS d'entrée, sorties
#       d'étape, journal `outils_sortie.txt`), chemin annoncé dans le message ;
#       RESIDUS nettoyés au démarrage (session morte, 2,8 Go chez Alain).
#   Doc : LISEZMOI Windows/Linux (section « espace disque et dossier de
#   travail ») + CLAUDE.md (leçon astropy → `numpy.tofile`). Banc NEUF
#   `bancs/_test_espace_jalon72.py`. Repli si régression : v2.38.5.

# --- Changelog (entrée la plus récente en premier) --------------------------
# v2.38.5 : DÉTECTION DES OUTILS EXTERNES — GRAXPERT SOUS LINUX, ET FIN DES
#   ÉCHECS SILENCIEUX (constat réel d'Alain, 27/09/2026 : « la détection de
#   l'emplacement de GraXpert ne s'est pas faite (celle de rec-astro BlurX
#   oui) »).
#   CAUSE MESURÉE : sous Linux le binaire officiel de GraXpert s'appelle
#   `GraXpert-linux` (archive `graxpert-linux-amd64.zip` des Releases
#   officielles, README : « chmod u+x ./GraXpert-linux » et « Linux: Replace
#   GraXpert-win64.exe by GraXpert-linux »), alors que le code ne cherchait
#   que `graxpert`/`GraXpert` — comparaison SENSIBLE À LA CASSE sous Linux, et
#   une archive décompressée n'est pas dans le PATH → détection impossible ;
#   les sous-chemins sondés (`<racine>/GraXpert/<nom>`, racines `~/.local`,
#   `/usr/local`, `/opt`) ne couvraient ni le nom ni le dossier d'extraction.
#   rc-astro était trouvé parce que son installeur le place DANS le PATH, avec
#   le nom attendu (vérifié : `C:\Program Files\RC-Astro\CLI\rc-astro.exe`).
#   Aggravant : la commande de REPLI (« graxpert … », binaire nu) est une
#   chaîne non vide → elle était PERSISTÉE dans config.json dès la première
#   session et restaurée à chaque lancement SANS re-test de l'exécutable (le
#   test n'avait lieu que si rien n'était enregistré) : une détection ratée
#   restait figée à vie, même après installation de GraXpert.
#   (1) `external.detection` : noms, sous-chemins et racines sont calculés PAR
#       OS et complétés — Linux `GraXpert-linux`, `GraXpert-linux-amd64`,
#       `bin/` utilisateur, `~/Applications`, `~` ; macOS
#       `GraXpert.app/Contents/MacOS/GraXpert` ; Windows
#       `Programs\GraXpert\` ; plus un filtre borné `GraXpert*` (dossier
#       d'archive décompressée, AppImage exécutable) ;
#   (2) l'INI DE SIRIL devient une source de détection : nouveau module
#       `avastack.siril_ini` (lecture tolérante, déséchappement GKeyFile,
#       chemins par OS vérifiés dans la doc Siril 1.4.4) — `graxpert_path`
#       pour l'outil, `catalogue_gaia_astro`/`catalogue_gaia_photo` pour le
#       dossier des catalogues (l'ini d'Alain porte les trois) ;
#   (3) plus de commande figée : `external.live.outil_manquant()` distingue
#       « chemin existant », « nom dans le PATH » et « outil introuvable » →
#       re-détection à l'ouverture si l'exécutable a disparu, et une commande
#       sans outil n'est PLUS persistée (elle était enregistrée telle quelle) ;
#   (4) l'interface DIT l'état de la détection : une ligne sous chaque commande
#       du cadre « Traitement externe » (« ✔ GraXpert : /chemin » ou
#       « ⚠ GraXpert : exécutable introuvable — bouton « … » pour le désigner »),
#       rafraîchie à chaque modification du champ ; avertissements AVANT de
#       lancer (case GraXpert live, bouton ⚡) au lieu d'un « command not found »
#       noyé dans la sortie de l'outil ;
#   (5) LISEZMOI Windows et Linux (section « outils externes » : nom exact sous
#       Linux, chmod, où le poser, bouton « … », variables AVASTACK_*) +
#       CLAUDE.md (nom Linux/macOS du binaire, ini Siril, piège de la commande
#       figée).
#   Banc NEUF `bancs/_test_outils_jalon71.py` (détection rejouée sous Linux /
#   macOS / Windows simulés, ini Siril, chemin disparu, ligne d'état de l'UI).
#   Repli si régression : v2.38.4.

# --- Changelog (entrée la plus récente en premier) --------------------------
# v2.38.4 : ASTRONOMÉTRIE SOUS LINUX — LES DONNÉES MANQUANTES SONT DITES, ET
#   TÉLÉCHARGEABLES DEPUIS L'APPLICATION (constat réel d'Alain, 27/09/2026 :
#   installateur Linux essayé — « l'astrométrie ne trouve pas de résultat…
#   et ça échoue en silence »).
#   CAUSE MESURÉE (rejoué depuis la branche Linux, HOME vierge) : le dossier
#   des catalogues n'était cherché QUE sous `%LOCALAPPDATA%\Siril` (Windows) et
#   `~/.local/share/kstars` — le dossier Linux de Siril (`~/.local/share/siril`,
#   vérifié dans la doc Siril 1.4.4 : `core.catalogue_gaia_astro`) n'était
#   JAMAIS essayé, et le dossier KStars ne contient justement PAS les fichiers
#   `siril_cat*` du projet → repli sur un dossier AVAStack VIDE, donc échec
#   certain du solveur interne ; aucun repli possible par ASTAP (astap_cli
#   absent sous Linux) ; et la raison ne vivait que dans une ligne d'état
#   remplacée au tour suivant (l'application n'a pas de journal) — d'où
#   l'impression de silence.
#   (1) `catalogues.dossiers_siril()` : chemins PAR OS (`~/.local/share/siril`
#       sous Linux, `%LOCALAPPDATA%\Siril` sous Windows, Application Support
#       sous macOS, `XDG_DATA_HOME` honoré) — et c'est le CONTENU (`siril_cat*`)
#       qui décide quel dossier est utilisable, plus un nom de dossier supposé ;
#   (2) la clé de config `chemin_catalogues` est RÉELLEMENT honorée (elle
#       n'existait que dans une docstring) : ligne « Catalogues » dans la
#       fenêtre Astrométrie (dossier utilisé + présence du catalogue + nombre de
#       chunks spectro), bouton 📂 pour choisir un autre dossier (persisté) ;
#   (3) bouton « ⬇ Gaia » : téléchargement du catalogue astrométrique Gaia DR3
#       de Siril (≈ 1,1 Go) dans le dossier affiché, en THREAD séparé, avec
#       reprise après coupure et sha256 vérifié (`catalogues.telechargeur`
#       existait mais n'était branché NULLE PART) : progression dans la ligne
#       d'état, jamais d'appel Tk depuis le thread ;
#   (4) `SuiviAstrometrie` : l'absence de catalogue est reconnue comme cause de
#       DONNÉES (`solveur.MSG_CATALOGUE_ABSENT`) → les essais s'ARRÊTENT au lieu
#       d'en consommer 20 pour rien, la ligne d'état dit « DONNÉES MANQUANTES —
#       … » avec le dossier cherché, et les essais repartent TOUT SEULS dès
#       qu'un catalogue apparaît (fichier déposé, téléchargé, dossier changé) ;
#   (5) LISEZMOI Windows et Linux : section « données de l'astrométrie » (ce
#       qui est requis, où le mettre, ce que fait le bouton).
#   Banc NEUF `_test_catalogues_jalon70.py` (chemins par OS, surcharge de config,
#   arrêt/reprise des essais, ligne « Catalogues » de l'UI avec téléchargeur
#   factice — jamais de réseau dans un banc). Repli si régression : v2.38.3.

# --- Changelog (entrée la plus récente en premier) --------------------------
# v2.38.3 : PARAMÈTRES BXT EXPLICITES ET TRAÇABILITÉ DES OUTILS EXTERNES. Trois
#   finitions demandées par Alain (27/09/2026), après la mesure du moucheté bleu
#   de son fichier traité (« image magnifique avec -sn 0.3 »).
#   (1) COMMANDE BXT PAR DÉFAUT EXPLICITE — le CLI rc-astro a des défauts qui
#       AGISSENT tant qu'on ne passe rien (lues dans `rc-astro bxt --help` du
#       CLI INSTALLÉ, v2.6.9 : --ss 0,50, --ash 0,00, --sn 0,50). La commande par
#       défaut ne passait que --ash : le volet « objets » (--sn) tournait donc à
#       0,50 sans que rien ne l'écrive — c'est lui qui ajoutait le moucheté
#       chromatique 2-8 px (MESURÉ ×1,28 contre la vue live, contre ×0,48 avec
#       0,3 ; σ/MAD du bleu 2,95 → 1,49). Nouvelle commande par défaut :
#       --ss 0.5 --ash -0.3 --sn 0.3. Les commandes MÉMORISÉES (config.json,
#       `cmd_bxt`) restent prioritaires : rien ne change tout seul chez un
#       utilisateur existant (ajouter « --sn 0.3 » au champ suffit).
#   (2) TRAÇABILITÉ DES OUTILS EXTERNES — leurs commandes (donc leurs
#       PARAMÈTRES) n'étaient écrites NULLE PART : `AVAAPPLI` ne décrivait que
#       les corrections de couleur, et les « tel que vu » n'avaient aucun
#       en-tête. `App._entete_externe()` (nouvelle) consigne maintenant, dans les
#       fichiers écrits DEPUIS un résultat du ⚡ : AVAOUTIL (outils cochés),
#       AVACMDGX / AVACMDDN / AVACMDBX (commandes réellement exécutées, options
#       comprises), AVAAPPLI (corrections pré-étirement), AVAFRAME, AVAVUE.
#       Appliqué à la sortie LINÉAIRE du ⚡ (« 💾 Enregistrer le résultat
#       traité ») ET au « tel que vu » de la vue « traitée » ; la vue
#       « empilement » garde son comportement d'origine (aucun mot-clé).
#       Déballage TOLÉRANT (job ancien à 8 éléments accepté).
#   (3) LISEZMOI de l'installateur : encadré « RÉGLAGES DE BXT » (les défauts du
#       CLI agissent, la commande fournie les écrit, « --sn 0.3 » à ajouter si
#       la commande mémorisée date d'avant).
#   Banc NEUF `_test_bxt_entete_jalon69.py` (commande par défaut, en-tête depuis
#   le job — complet, ancien, absent —, mots-clés RELUS par astropy dans les
#   deux fichiers écrits, vue « empilement » toujours sans mot-clé).
#   Repli si régression : v2.38.2.

# v2.38.2 : LE RÉSULTAT DU ⚡ N'EST PLUS À L'ENVERS (miroir vertical du CLI
#   rc-astro que `auto_unflip` ne détectait pas). Constat MESURÉ chez Alain
#   (27/09/2026) en comparant ses deux « tel que vu » de la v2.38.1 : le fichier
#   du ⚡ et celui de l'empilement montrent le même champ, mais l'un est retourné
#   haut-bas (corrélation +0,99 en miroir contre +0,35 tel quel). Le défaut
#   existait depuis l'arrivée de BXT (constaté sur les fichiers v2.373, v2.38.0
#   et v2.38.1) et touchait AUSSI l'écran en vue « traitée » — le seul endroit
#   qui applique les outils EXTERNES.
#   CAUSE : `images.auto_unflip` comparait les images LINÉAIRES brutes par une
#   corrélation de Pearson sur un sous-échantillonnage « 1 pixel sur N ».
#   Sur ses fichiers, les deux orientations donnaient +0,1085 (droite) et
#   +0,1212 (miroir) — écart +0,0127, très en dessous de la marge de 0,05 : la
#   mesure était ÉCRASÉE par tout ce qui n'est PAS partagé entre les deux images
#   (grain, texture fine des outils, cadrage légèrement différent — le ⚡
#   travaille sur un instantané PLUS RÉCENT que l'empilement sauvegardé : mesuré,
#   le rapport basses/hautes fréquences vaut 0,25 dans les deux images, cf.
#   `_diag_unflip_mecanisme.py`).
#   CORRECTIF : la comparaison se fait sur les images ÉTIRÉES et NORMALISÉES
#   (percentiles 0,5/99,5 puis racine carrée), sous-échantillonnées par MOYENNE
#   (INTER_AREA) au lieu d'un pas de sélection, et la marge passe à +0,20
#   (mesuré +0,27 à +0,46 sur les vrais miroirs, < 0,05 quand l'orientation est
#   bonne). Mesuré sur les mêmes fichiers : +0,539 (droite) contre +0,996
#   (miroir) → décision franche, miroir redressé.
#   BANC `_test_unflip_jalon69.py` : correction sur une scène franchement
#   asymétrique, QUATRE cas sans faux positif (image droite, miroir HORIZONTAL —
#   qui ne doit jamais être touché —, bruit seul, formes différentes), et les
#   VRAIS fichiers du ⚡ en témoin (l'ancienne formule, ré-écrite, y est
#   aveugle).
#   Repli si régression : v2.38.1.

# v2.38.1 : LE RENDU PLEINE RÉSOLUTION VAUT AUSSI POUR LA VUE « TRAITÉE » (et
#   corrige, dans cette vue, un écran qui montrait la MAUVAISE image). Demande
#   d'Alain (27/09/2026) : « ok pour le rendu pleine résolution en vue traitée,
#   je pensais que c'était évident de le faire ».
#   (1) CORRECTION — EN VUE « TRAITÉE », L'ÉCRAN MONTRAIT L'EMPILEMENT :
#       `_src_rendu` rendait `_stack_pleine_res` (l'empilement COMPLET) dès que
#       l'option était cochée, SANS regarder la vue. Or en vue « traitée »
#       l'écran doit montrer le RÉSULTAT du ⚡ traitement externe : il montrait
#       donc l'empilement, et le zoom « fidèle » ne portait pas sur l'image
#       annoncée. Constat rendu possible par la v2.38.0 (l'option n'existait pas
#       avant, la vue « traitée » retombait alors sur l'aperçu).
#   (2) NOUVELLE `App._src_pleine_res()` : la source pleine résolution suit la
#       VUE — « empilement » → `_stack_pleine_res` (copie de l'empilement
#       complet), « traitée » → `proc_full` (résultat externe, DÉJÀ mémorisé pour
#       les sauvegardes : AUCUNE copie supplémentaire, aucun octet en plus).
#       Décocher l'option libère la copie de l'empilement mais laisse `proc_full`
#       intact (il sert à « 💾 Enregistrer le résultat traité (linéaire) » et à
#       « tel que vu » en vue traitée) ; repli sur l'aperçu tant que l'image
#       complète de la vue n'existe pas (début de session, avant le premier ⚡).
#       Le libellé d'aide de la case dit maintenant que l'option couvre les deux
#       vues (empilement ou résultat traité).
#   (3) BANC `_test_pleine_res_traitee_jalon69.py` (NOUVEAU) : source par vue
#       (et NON l'empilement en vue traitée — le témoin serait muet sans la
#       correction), option décochée, replis, et « l'écran = le fichier » en vue
#       traitée (le rendu affiché comparé au fichier écrit par la chaîne de
#       sauvegarde « tel que vu », égalité exigée).
#   - Non-régression : `_test_zoom_pleine_res_jalon68.py` rejoué (l'option et le
#     zoom en vue « empilement » sont inchangés), ainsi que les bancs d'interface
#     qui touchent la vue (jalon 5, 9, 12, 39).
#   Repli si régression : v2.38.0.

# v2.38.0 : ZOOM SUR L'IMAGE PLEINE RÉSOLUTION (et deux corrections de fidélité
#   écran ⇄ fichier). Demande d'Alain (26/09/2026) : « sur l'écran, je veux
#   pouvoir zoomer sur l'image pleine résolution » — le zoom existait (molette
#   ×1 à ×32, double-clic pour ajuster) mais il agrandissait l'APERÇU 1600 px,
#   donc du flou interpolé, et la chaîne non linéaire y tournait à une AUTRE
#   échelle que pour le fichier.
#   (1) NOUVELLE OPTION « Rendu pleine résolution (zoom fidèle) » (case à cocher
#       dans le cadre « Affichage », DÉCOCHÉE par défaut, persistée
#       `vl_pleine_res_ecran`) : quand elle est cochée, la chaîne d'affichage
#       (GraXpert/débruitage/netteté/couleurs/neutralisation/chroma/étirement)
#       tourne sur l'empilement COMPLET → l'écran montre EXACTEMENT ce que le
#       fichier contiendra et le zoom recadre de VRAIS pixels (1:1 exact).
#       Coût MESURÉ (`_diag_couts_jalon66.py`) : 7,2-8,3 s par recalcul complet
#       contre 1,7-1,9 s (×4,3), d'où le choix d'une option. Décocher LIBÈRE la
#       copie pleine résolution (25 Mo). Repli sur l'aperçu si aucun empilement
#       complet n'existe (vue « traitée », début de session).
#       - le libellé du zoom affiche désormais l'échelle RÉELLE (px image par px
#         écran, « 1:1 ») et la mention PLEINE RÉSOLUTION.
#   (2) CORRECTION — LE FICHIER « tel que vu » NE CORRESPONDAIT PAS À L'ÉCRAN :
#       `DisplayProcessor.rendu_pleine_resolution` ne transmettait le FOND CIBLE
#       (`vl_target_bg`) que lorsque le logD restait à résoudre. Une fois le logD
#       mémorisé (cas courant en live), l'étirement reprenait le défaut du module
#       (0,20) au lieu du réglage de l'utilisateur. MESURÉ sur une image réelle :
#       fond final 0,197 contre 0,159 attendu, écart moyen 9,6 niveaux de 8 bits
#       (17 au pire) — le fichier était donc PLUS CLAIR que l'écran. Le fond cible
#       est maintenant transmis dans les deux modes : écran et fichier coïncident
#       au bit près (banc jalon 68 [3], écart 0).
#   (3) BANC `_test_zoom_pleine_res_jalon68.py` (NOUVEAU) : option (défaut,
#       persistance, libération mémoire), source de rendu (`_src_rendu`), ÉCRAN =
#       FICHIER (écart 0), zoom 1:1 au bit près contre l'aperçu grossi (détail fin
#       8,73 contre 1,49), libellé du zoom.
#   - Non-régression : 20 bancs rejoués (dont `_test_save_asseen_jalon5.py`,
#     `_test_sharp_live_jalon12.py`, `_test_coeur_crame_jalon64.py`, toute la
#     chaîne couleur), TOUS PASSENT.
#   Repli si régression : v2.37.5.
# v2.37.5 : L'ANNEAU DE COULEUR AUTOUR DES ÉTOILES DANS LES FICHIERS (poids de
#   structure du flou de chroma). Constat d'Alain (26/09/2026) : « les étoiles
#   moyennes rouges sont bien plus rouges et ont presque un halo. Cela se produit
#   aussi bien dans le tel que vu stack que dans le tel que vu traité alors que
#   l'affichage est correct ». ENQUÊTE PRÉALABLE (9 bancs de diagnostic
#   `_diag_*jalon66.py`, aucun code touché) :
#   - le FICHIER PNG n'est pas en cause : PNG ⇄ FITS du même rendu sont
#     identiques à 1/65535 près sur ses deux cas (moyenne 0,5 niveau, 0,000 % des
#     pixels au-delà d'un niveau) ;
#   - l'écart est entre l'ÉCRAN et le FICHIER : la chaîne non linéaire est
#     appliquée à l'APERÇU 1600 px pour l'écran, à la PLEINE RÉSOLUTION 3839 px
#     pour le fichier (écart moyen 0,015-0,023, max 0,37-0,49 aux cœurs) ;
#   - l'anneau est FABRIQUÉ par la réduction du bruit chromatique à PLEINE
#     RÉSOLUTION : R/G de l'anneau (× le R/G du fond) 1,80 sans chroma → 2,33 /
#     2,93 / 3,89 aux forces 0,25 / 0,50 / 0,85 (sa valeur), et le RAYON
#     l'élargit (3 px → 6,5 · 5 px → 10,2). À l'écran l'étoile fait 1 px : le flou
#     y écrase l'anneau — d'où un défaut visible SEULEMENT dans les fichiers ;
#   - mécanisme (mesuré au pixel) : le flou du RAPPORT `cn = (Cr−0,5)/den` dépose
#     la couleur du CŒUR (où `den = flou(y)` est petit) dans les AILES, où `den`
#     est au niveau du ciel : +0,0014 sur Cr pour un ciel à 0,03, soit ~5 % de la
#     luminance locale — le seul étirement VeraLux suffit ensuite à en faire un
#     anneau (R/G ×2,4).
#   CORRECTIF : `couleurs._poids_structure` — la correction est multipliée par
#   1 / (1 + (|Y − flou(Y)| / (3 σ)) ** 6), qui vaut ~1 sur le FOND (grain seul,
#   écart ≈ 1 σ : 0,999) et ~0 sur une STRUCTURE (0,5 à 3 σ, 0,045 à 5 σ, 0,0007
#   à 10 σ). σ est le MAD de l'écart de luminance à son propre flou (×1,4826),
#   échantillonné ; aucun flou supplémentaire (celui de `den` est réutilisé).
#   - MESURÉ sur son empilement réel : anneau des 4 étoiles 1,96 (sans chroma) →
#     4,63 (v2.37.4) → 2,00 (v2.37.5) ; grain chromatique du fond (MAD
#     passe-haut) ×0,16 (v2.37.4) → ×0,24 (v2.37.5), soit 76 % du grain coloré
#     toujours retiré — le bénéfice d'origine est conservé ;
#   - la couleur d'un objet étendu (nébuleuse) bouge de moins de 0,05 % et la
#     LUMINANCE (canal Y) n'est pas réécrite (résidu de reconstruction < 1,5e-6
#     sur le fond, 3,7e-05 au total, au cœur saturé) ;
#   - BANC `_test_chroma_structure_jalon67.py` (NOUVEAU, 7 sections) : contrat de
#     base, anneau sur une scène témoin (TÉMOIN = la formule v2.37.4 ré-écrite
#     exprès, qui doit, elle, fabriquer l'anneau), grain du fond, objet étendu,
#     luminance, transition du poids, et son FICHIER RÉEL (chemin donné en
#     argument, section sautée si absent).
#   - Deux bancs existants ont vu TROIS de leurs mesures adaptées au changement,
#     chacune documentée sur place (jamais affaiblie) : le grain est mesuré au MAD
#     et non au σ dans `_test_chroma_nr_jalon63.py` et `_test_chroma_halo_jalon65.py`
#     (la correction étant devenue SÉLECTIVE, le σ est dominé par la queue des
#     ~0,2 % de pixels protégés : ×0,092 contre ×0,027) ; le seuil du résidu de
#     luminance passe de 2e-05 à 1e-04 dans `_test_chroma_halo_jalon65.py` (queue
#     au CŒUR SATURÉ, B = 1,0000) ; et son assertion sur le rayon non ramené est
#     inversée (les ailes n'étant plus lissées, le rayon ne les déforme plus).
#   Repli si régression : v2.37.4 (9927539).
# v2.37.4 : LE RAYON DE RÉFÉRENCE DU FLOU DE CHROMA EST RÉGLABLE (visu live).
#   Retour d'Alain (26/09/2026) après la v2.37.3 : « on n'a plus le super halo de
#   couleur, ça c'est bien » — mais il RESTE des halos RÉELS (optiques), qu'il
#   traitera côté BlurXTerminator pour les fichiers ; pour la VISU LIVE il
#   demande le réglage du rayon de référence afin de faire des essais.
#   - Nouveau curseur « Rayon de référence (px pleine rés.) » (0,5 à 8 px, pas de
#     0,25) sous la case « Réduire le bruit chromatique », avec sa légende (plus
#     grand = grain coloré mieux retiré, mais couleur des étoiles plus étalée).
#   - Le réglage est en pixels PLEINE RÉSOLUTION : l'aperçu le ramène à SON
#     échelle (`App._poser_rayon_chroma` → `couleurs.rayon_chroma_apercu`), alors
#     que le rendu « tel que vu » et la chaîne EXTERNE (15e élément du job, après
#     la force) l'utilisent tel quel. `RAYON_CHROMA_MIN` passe de 0,6 à 0,2 px :
#     un petit rayon de référence ne doit pas être gonflé sur un aperçu réduit.
#   - Persistance `vl_chroma_rayon_ref`, restauration TOLÉRANTE (hors [0,5 ; 8] ou
#     illisible → la valeur d'usage reste, comme pour la force).
#   - BANC : `_test_chroma_halo_jalon65.py` [6bis] (curseur, échelle de l'aperçu,
#     bornes, rendu pleine résolution, 15e élément du job) et `_test_dn_jalon7.py`
#     mis à jour (le job externe passe de 14 à 15 éléments). Non-régression :
#     19 bancs rejoués, TOUS PASSENT. Les jobs antérieurs (≤ 14 éléments) restent
#     acceptés : déballage tolérant → rayon de référence.
#   Repli si régression : v2.37.3 (5c38d23).

# v2.37.3 : LE HALO DE COULEUR DES ÉTOILES ÉTAIT FABRIQUÉ PAR LA RÉDUCTION DE
#   BRUIT CHROMATIQUE. Constat d'Alain (26/09/2026) : « les étoiles brillantes
#   rouges et bleues ont un halo gênant », VISIBLE AUSSI dans le fichier passé
#   par BlurXTerminator (« en général, c'est un halo killer pourtant »).
#   MESURES QUI L'ÉTABLISSENT, sur son empilement M31 réel (anneau r = 3..9 px
#   autour des étoiles, en multiples du niveau de ciel local, fond neutralisé) :
#   - étoile la plus brillante (rouge) : R 41,3 → 34,9 (−16 %) et B 19,9 →
#     23,6 (+19 %) — le halo perdait la couleur de l'étoile et prenait celle du
#     fond (R/B 2,08 → 1,47) ;
#   - étoile bleue : R 3,53 → 1,74 (−51 %) et B 2,72 → 3,92 (+44 %) — un HALO
#     BLEU APPARAISSAIT là où il n'y en avait aucun (R/B 1,30 → 0,44) ;
#   - la LUMINANCE, elle, ne bougeait pas (±6 %) : c'est un halo de COULEUR ;
#   - contrôle : à force ≈ 0, la même conversion YCrCb→RVB rend l'image AU BIT
#     PRÈS → c'est le FLOU qui est en cause, pas la conversion.
#   CAUSE : un écart de chroma (Cr/Cb) ne dépend PAS de la luminosité du pixel.
#   Le flou mélangeait donc la couleur du CŒUR de l'étoile avec celle du CIEL
#   voisin et déposait ce mélange sur les AILES faibles, où un minuscule écart
#   devient une énorme couleur.
#   POURQUOI BXT N'A RIEN PU FAIRE : la chaîne externe applique les cases 7/8
#   APRÈS BlurXTerminator (fin de `_run_external`) — le halo est créé APRÈS le
#   « halo killer ». (BXT a bien un réglage de halos, `--ash` −0,5…+0,5, dont le
#   défaut 0,00 = « aucun ajustement » : la commande par défaut de l'appli ne le
#   passe pas — piste indépendante, NON modifiée ici.)
#   POURQUOI C'ÉTAIT PIRE À L'ÉCRAN : l'aperçu est réduit (facteur 1600/largeur,
#   0,417 sur son image de 3838 px) alors que le rayon restait fixé à 3 px : les
#   ÉTOILES rétrécissent avec l'aperçu, pas le flou → 3 px d'aperçu valaient
#   7,2 px pleine résolution, soit un halo 2,4 fois plus large par rapport aux
#   étoiles que dans les fichiers.
#   CORRECTIF (option (A) choisie par Alain, 26/09/2026 : « correctif complet ») :
#   1. `couleurs.reduire_bruit_chroma` lisse désormais le RAPPORT de couleur
#      (chroma / luminance locale) et le re-multiplie par cette échelle ; celle-ci
#      est le MINIMUM entre la luminance DU PIXEL et sa version LISSÉE — le pixel
#      borne la correction près d'une étoile (plus de halo), la version lissée
#      donne une échelle quasi constante sur le fond (le bruit de luminance ne se
#      re-dépose pas dans la couleur). MESURÉ (force 0,847) : grain coloré du fond
#      ×0,169 (ancienne formulation ×0,155 → l'essentiel du bénéfice est
#      conservé) et halo de l'étoile bleue R/B 1,26 (référence sans réduction
#      1,30) au lieu de 0,44 ;
#   2. `couleurs.rayon_chroma_apercu(scale)` + `DisplayProcessor.vl_chroma_rayon` :
#      le rayon SUIT LA RÉSOLUTION (l'interface le ramène à l'échelle de l'aperçu,
#      les fichiers gardent les 3 px de référence) — l'écran redevient fidèle au
#      fichier (règle du projet : « le fichier correspond à l'écran »).
#   BANC : `_test_chroma_halo_jalon65.py` (halo d'une étoile à ailes larges :
#   préservé à quelques %, grain du fond toujours retiré, rayon qui suit la
#   résolution, transport par le solveur) + `_test_chroma_nr_jalon63.py` rejoué.
#   Repli si régression : v2.37.2 (5545a9c).

# v2.37.2 : LE CŒUR « CRAMÉ » EST UNE COUPE, PAS UN PARAMÈTRE. Constat d'Alain
#   (25/09/2026) : « le cœur de M31 est vraiment cramé », DANS l'appli et pas
#   seulement sur le PNG — et il étire en VeraLux, donc ce n'était pas un
#   réglage d'étirement.
#   MESURE QUI L'ÉTABLIT, sur ses propres empilements : la VUE n'est pas le
#   fichier. Le fichier linéaire est ramené dans [0,1] par UN facteur global
#   (`images.borner_lineaire` : AVASCALE = 13,12 sur sa M31 2.37.1, 15,27 sur sa
#   115 frames), alors que le chemin d'étirement recevait l'image à l'échelle
#   MÉMOIRE et la COUPAIT à 1,0 avant d'étirer. Profil du cœur par anneaux
#   (0-10, 10-20, 20-30, 30-45, 45-60 px ; % du canal vert ; même fichier) :
#       image mémoire (coupe à 1,0)   : 86,00 | 86,00 | 86,00 | 86,00 | 86,00
#       fichier borné (facteur global): 85,83 | 78,67 | 73,12 | 67,37 | 62,61
#   Tout ce qui dépasse 1,0 — le cœur ENTIER, 0,43 à 0,79 % de l'image — devenait
#   UNE SEULE VALEUR : un disque blanc PLAT, sans le moindre dégradé, donc
#   « cramé », alors que le fichier sauvegardé, lui, gardait son dégradé. D'où
#   l'écart constaté entre ce qu'on voit dans l'appli et ce que contient le
#   fichier.
#   AUCUN paramètre VeraLux n'est en cause (mesuré sur son empilement : b de 2 à
#   25, target_bg de 0,10 à 0,35, color_grip, shadow_convergence,
#   convergence_power, logD forcé 2,0/4,0 → 0 pixel cramé dans TOUS les cas) :
#   c'est bien la coupe, en amont du moteur, qui écrasait le cœur.
#   CORRECTIF : `veralux.normaliser_lin()` — UN SEUL facteur GLOBAL (exactement
#   la règle des sauvegardes linéaires, jamais par canal : linéarité, équilibre
#   des couleurs et dégradé du cœur préservés), appliqué dans `etirer()` ET dans
#   `DisplayProcessor.rendu_pleine_resolution` (vue « tel que vu », donc le
#   PNG/TIFF aussi). Effets vérifiés : le rendu ne dépend PLUS de l'échelle
#   arbitraire de l'empilement (etirer(x) == etirer(3·x) à 1,2e-06), le cœur
#   retrouve son dégradé (0,00 point de % d'étendue avant → 18,8 à 23,2 points
#   après sur ses deux fichiers) ; une image déjà dans [0,1] n'est PAS modifiée
#   (aucun facteur retiré → rendu identique à un appel direct du moteur).
#   Au passage, l'ancien `np.clip(..., out=img)` écrasait le tableau de
#   l'APPELANT : `normaliser_lin` copie réellement, l'image reçue est intacte.
#   BANC : `_test_coeur_crame_jalon64.py` (échelle, dégradé du cœur avant/après,
#   non-régression sur image ≤ 1, entrée non modifiée, et ses deux empilements
#   M31 réels à l'échelle mémoire).

# v2.37.1 : LES AJOUTS RÉCENTS ENTRENT DANS LA CHAÎNE DE TRAITEMENT EXTERNE —
#   demande d'Alain (25/09/2026) : « intégrer les derniers ajouts (SPCC,
#   neutralisation, bruit chroma) dans la chaîne de traitement externe pour que
#   je puisse sortir une belle image à la fin du stack ».
#   - La SPCC y était DÉJÀ, et c'est vérifié dans le code : les corrections de
#     couleur du composite (gains EFFECTIFS — SPCC/Gaia/manuels —, équilibrage
#     des canaux, recalage « Linear Fit ») s'appliquent dans les DEUX chemins
#     externes : en mono l'instantané est `stacker.mean()` (corrections=True,
#     défaut) ; en composition, `_run_external_compo` applique
#     `composition.corrections_couleur(..., gains=gains_effectifs(), ...)` au
#     composite re-fait depuis les couches traitées (chantier 24/09/2026).
#     Le traitement PAR COUCHE (GraXpert gradient/débruitage) reste, lui, sur les
#     couches BRUTES (contrat du jalon 54) : rien n'est appliqué deux fois.
#   - Les DEUX corrections pré-étirement de la chaîne live rejoignent la chaîne
#     externe, au même rang qu'elle : « 7. Neutraliser la couleur du fond »
#     (COCHÉE par défaut, comme la case live : c'est un défaut de rendu — l'ancre
#     de VeraLux transforme 2 % d'écart de ciel en fond franc bleu) et
#     « 8. Réduire le bruit chromatique » (OPT-IN, force = curseur « Couleur
#     live »). Ordre : … → SCNR → SCNR doux → démagenta → neutralisation →
#     bruit chromatique, juste avant l'étirement d'affichage ; les gains de
#     neutralisation sont ANNONCÉS dans le message final, comme dans « État des
#     calculs » du live.
#     Transport : 12e, 13e et 14e éléments du job externe (déballage tolérant —
#     les jobs 11-tuple des bancs antérieurs restent valides, correctifs
#     inactifs) ; force CAPTURÉE au clic (le thread externe ne lit jamais une
#     variable Tk) ; cases persistées (`ext_neutre_fond`, `ext_chroma`).
#   - Vérifié par le banc `_test_couleurs_jalon22.py` [3bis] (les deux étapes
#     seules, la force transportée, la chaîne complète dans l'ordre, l'annonce
#     des gains sur un ciel bleui, les no-op mono, le job 11-tuple tolérant) et
#     [4] (persistance) ; banc jalon 7 mis à jour (14-tuple).
#   - Au passage, un libellé FAUX au lancement est corrigé (constat d'Alain :
#     « je viens de rouvrir […] les filtres sont bons ») : sans source choisie,
#     la case SPCC annonçait « sans effet en MONO » alors que l'application ne
#     sait pas encore ce que sera la source — elle dit maintenant qu'elle attend
#     la source, et ne parle de « sans effet » qu'une fois la source connue.
# v2.37.0 : DEUX DEMANDES D'ALAIN (25/09/2026), sur ses empilements M31 v2.36.1.
#   (a) RÉDUCTION DU BRUIT CHROMATIQUE — « un équivalent de SCNR pour le bleu »,
#       son mot, et sa réponse à la proposition : « oui […] et case décochée par
#       défaut ». MESURE QUI LA MOTIVE (ses deux fichiers 41/115 frames) : le
#       grain du fond s'améliore ENFIN avec l'intégration (σ ÷1,53 pour ×2,8 de
#       frames, fond/σ ×1,44 — l'objet même de la normalisation commune v2.36.0),
#       et le fond est neutre (R/G 0,9998 · B/G 0,9999) ; mais le grain restant
#       est COLORÉ et STABLE : R/G 0,90 (équilibré) et B/G 1,163 → 1,174. Cause
#       exacte, au chiffre près : une correction MULTIPLICATIVE amplifie le bruit
#       du canal qu'elle monte, et la SPCC applique K_B/K_G = 1,318 →
#       (σ_B·K_B)/(σ_G·K_G) = 0,891 × 1,318 = 1,174 (mesuré 1,174) et
#       (σ_R·K_R)/(σ_G·K_G) = 1,099 × 0,820 = 0,902 (mesuré 0,902). Ni
#       l'équilibrage des canaux ni le SCNR vert ne peuvent corriger un excès de
#       grain BLEU. `couleurs.reduire_bruit_chroma` lisse la CHROMA (espace YCrCb
#       de OpenCV : seuls Cr et Cb sont réécrits, donc la LUMINANCE ne bouge pas —
#       mesuré : écart < 2e-06 sur le fond, < 1,4e-05 en tout, cette queue venant
#       des pixels qui saturent au bord haut de l'échelle), appliquée JUSTE APRÈS
#       la neutralisation du fond et JUSTE AVANT l'étirement, dans le solveur
#       VeraLux (10e et 11e éléments de son job) ET dans le chemin « tel que vu »
#       — jamais dans la 3e sortie LINÉAIRE (règle du jalon 59). MESURÉ au banc :
#       le grain coloré tombe exactement de la part demandée (×0,751 à force 0,25,
#       ×0,502 à 0,5, ×0,024 à 1,0), la couleur de l'objet (chroma étendue) est
#       préservée à 0,86 %, et le grain de LUMINANCE n'est pas touché (le grain
#       restant est donc GRIS : c'est le débruitage qui réduit son amplitude).
#       UI : case « Réduire le bruit chromatique (live) » DÉCOCHÉE par défaut +
#       curseur de force, dans le cadre « Couleur live » ; rendu IMMÉDIAT au clic
#       (leçon du jalon 39, revécue avec la neutralisation du fond en v2.36.1 :
#       un callback de case couleur qui n'appelle pas _refresh_preview() semble
#       inerte jusqu'à la frame suivante). Banc : _test_chroma_nr_jalon63.py.
#   (b) REFAIRE UNE MESURE EN FIN DE STACK (SPCC, photométrie) — constat :
#       « je voulais refaire calculer la SPCC mais étant en fin de stack, ben ça
#       le fait pas en décochant et recochant et ça ne met donc rien à jour (le
#       libellé dessous ne passe pas au vert et reste gris avec les anciennes
#       valeurs) ». Cause : en fin de source (dossier épuisé) ou après
#       « ■ Arrêter », le worker sortait par « lu is None » ou
#       « not empilement_on » AVANT les tours de mesure (_astro_tour /
#       _photo_tour / _spcc_tour) : la mesure n'était tentée qu'à la PROCHAINE
#       frame, qui n'arrive jamais. Décocher/re-cocher une case de mesure pose
#       désormais une DEMANDE, servie par le worker même sans frame
#       (_servir_demandes_sans_frame), et le texte de la mesure est poussé à l'UI
#       (_pousser_rendu rafraîchit les lignes astro/photométrie/SPCC/re-stack du
#       dict d'état réutilisé). Les garde-fous des tours (mesure déjà valide,
#       case inactive, WCS, plancher de frames, délais et plafond d'essais) sont
#       inchangés : jamais de mesure en boucle.
# v2.36.2 : LA CASE « NEUTRALISER LA COULEUR DU FOND » AGIT IMMÉDIATEMENT
#          (constat d'Alain, 25/09/2026 : « la case Neutraliser la couleur du fond
#          ne provoque pas une visualisation immédiate quand on la coche et la
#          décoche, contrairement aux autres corrections de couleur. Ca semble
#          attendre une nouvelle frame »). C'est EXACTEMENT le bug corrigé au
#          jalon 39 pour SCNR / SCNR doux / démagenta : le callback de la case ne
#          faisait que POSER l'état (`_sync_vl_neutre_vue`, qui change la clé des
#          réglages du solveur) sans appeler `_refresh_preview()` — la nouvelle
#          chaîne n'était donc soumise au solveur qu'à la frame suivante ou au
#          prochain réglage déclenchant un rendu. `_on_vl_neutre` appelle
#          désormais `_refresh_preview()`, comme les autres cases couleur, et le
#          banc `_test_couleurs_immediat_jalon39.py` (qui verrouillait déjà les
#          trois autres cases) teste maintenant la quatrième : cochée → chaîne
#          soumise immédiatement et résultat affiché, décochée → retour immédiat,
#          sans nouvelle frame.
#          Aucun autre changement : le reste de la v2.36.1 est inchangé.
# v2.36.1 : LE FOND BLEU — DEUX CAUSES, DEUX CORRECTIFS (constats d'Alain,
#          25/09/2026 : « le fichier tel que vu en png : PROBLEME, vachement bleu
#          et ca me fait ca depuis le début je pense, donc problème vieux », puis
#          « il reste quand même pas mal de bruit bleu »).
#          ① PNG/TIFF : R ET B ÉTAIENT PERMUTÉS À L'ÉCRITURE. `save_image`
#            passait l'image RGB de l'appli à `cv2.imencode`, qui attend du BGR
#            (`load_image`, lui, convertit à la lecture) : TOUT PNG/TIFF exporté
#            sortait les canaux échangés. Piège SILENCIEUX : l'aller-retour
#            interne restait cohérent (écriture sans conversion, relecture avec),
#            donc ni les bancs ni l'application ne le voyaient — seulement les
#            visionneuses, Siril, GraXpert et Alain. MESURÉ sur son PNG :
#            PNG_R ≈ FITS_B et PNG_B ≈ FITS_R (corrélation 1,0000). Correctif :
#            conversion RGB→BGR avant `imencode` pour les images à 3 canaux ; le
#            banc relit désormais les fichiers écrits avec un lecteur
#            INDÉPENDANT (OpenCV brut ET PIL), jamais seulement par load_image.
#          ② L'ÉTIREMENT VERALUX AMPLIFIAIT LA COULEUR DU CIEL JUSQU'AU BLEU.
#            Le fichier linéaire a pourtant un fond NEUTRE (R/G 0,9991 ·
#            B/G 0,9991 mesuré), mais VeraLux soustrait une ANCRE (scalaire lu
#            dans l'histogramme de luminance) puis étire en log : pour le fond,
#            seul compte le RÉSIDU (niveau du canal − ancre). MESURÉ : ciels
#            0,0321 / 0,0326 / 0,0332 (3,6 % de bleu), ancre 0,0313 → résidus
#            +0,00080 / +0,00137 / +0,00196 (rapports 1 : 1,70 : 2,44) → fond
#            ÉTIRÉ R/G 0,363 · B/G 1,611. L'équilibrage des canaux ne l'enlève
#            pas : il estime le fond sur un PERCENTILE BAS (les coins les plus
#            sombres, déjà neutres à 0,1 %) alors que l'ancre vit dans
#            l'histogramme GLOBAL — les deux se complètent.
#            Correctif : `couleurs.neutraliser_fond` — gains par canal (~2 % ici)
#            mesurés sur la MÉDIANE DE LA MOITIÉ SOMBRE (robuste à un objet qui
#            remplirait le champ, contrairement à la médiane globale) et appliqués
#            JUSTE AVANT l'étirement → fond étiré R/G 1,020 · B/G 0,996 (mesuré
#            sur le même fichier). Case « Neutraliser la couleur du fond (live) »
#            dans « Couleur live », COCHÉE PAR DÉFAUT (c'est un défaut de rendu,
#            pas un choix esthétique ; décocher = ancien rendu), gains ANNONCÉS
#            dans l'état des calculs. Garde-fou ±10 % : sur un cadrage dominé par
#            un objet étendu la « moitié sombre » n'est plus du ciel (mesuré au
#            banc : les gains partent à la borne) — l'ampleur reste donc bornée,
#            et rien n'est appliqué si l'image est mono, déjà neutre, ou si un
#            canal est vide. Transport : clé des réglages du solveur (9e élément
#            du job), chemin de sauvegarde « tel que vu », config
#            (`vl_neutre_fond`). Banc : `_test_fond_bleu_jalon62.py` — qui
#            mesure aussi, en option, un fichier RÉEL donné en argument (fond
#            linéaire, gains, fond étiré avant/après, et contrôle du PNG écrit).
# v2.36.0 : NORMALISATION COMMUNE DES CANAUX EN COMPOSITION — **OPTION** (demande
#          d'Alain, 25/09/2026 : « ce bruit, qu'on utilise SPCC ou pas, est
#          présent ; plus on empile, plus VeraLux tire sur l'étirement »).
#          CONSTAT MESURÉ sur son empilement M31 RGB (`_diag_empilement_couleur`) :
#          l'empilement est CORRECT (grain ÷2,2 pour ×4 de frames, soit 1/√n) mais
#          le FOND du composite ne s'améliore pas : fond/σ = 2,88 à 28 frames
#          contre 2,50 à 111 frames. CAUSE : `composer()` normalise CHAQUE rôle par
#          SES percentiles, or le percentile bas (p0,25) est toujours ~2,8 σ sous
#          le ciel → le NIVEAU du fond du composite est proportionnel au BRUIT du
#          canal. Empiler plus fait donc baisser le fond ET le grain dans la même
#          proportion : l'étirement compense, et le grain du fond reste identique à
#          toute profondeur (VeraLux « tire » de plus en plus pour atteindre le
#          fond demandé). Effet secondaire : le grain est COLORÉ (R/G 0,66 ·
#          B/G 1,45) puisque chaque canal est divisé par SA dynamique.
#          CORRECTIF — case « Normalisation commune des canaux » (cadre
#          « Composition multi-filtres »), DÉCOCHÉE par défaut (le défaut existant
#          n'est pas cassé sans y être invité). Cochée, les trois rôles partagent
#          l'ÉCHELLE du rôle qui alimente le canal VERT (comme le recalage
#          « Linear Fit » cale R et B sur G) et AUCUN point noir n'est soustrait :
#          le fond garde son niveau et sa couleur PHYSIQUES, seul le bruit baisse
#          → le grain du fond s'améliore enfin en 1/√n et redevient gris (il garde
#          l'équilibre des couches). Un point noir COMMUN a été essayé puis écarté
#          (mesuré) : les ciels des trois canaux n'ont pas le même niveau, retrancher
#          celui du vert rendait le fond de R et B NÉGATIF (−4 % et −2 % de
#          l'amplitude → écrêtage du bruit et fond teinté en vert).
#          Bénéfice collatéral : les coefficients SPCC sont des RATIOS mesurés sur
#          les COUCHES — avec une échelle commune ils s'appliquent enfin sur la base
#          où ils ont été mesurés. Le fond gardant sa couleur physique, sa
#          neutralisation reste le rôle des offsets du recalage colorimétrique (ou
#          de GraXpert live, par couche) — comme les B0/B1/B2 de Siril.
#          Transport : l'option suit la voie des gains (instantané `_norm_commune`
#          → stacker → 7e élément du job du solveur → recomposition de la vue
#          « traitée », des couches pleine résolution ET de la chaîne externe) ;
#          elle survit au re-stack, est persistée (`norm_commune` en config) et
#          ANNONCÉE dans l'en-tête (AVACOMPO = « …, normalisation COMMUNE des canaux
#          (amplitude du vert) »). Banc : `_test_norm_commune_jalon61.py` — grain
#          du fond ×0,94 (constant) par rôle contre ×1,81 en échelle commune entre
#          30 et 120 frames, grain coloré B/G 2,10 par rôle contre 0,79 = celui des
#          couches.
# v2.35.2 : TROIS CORRECTIFS D'ERGONOMIE ET D'HONNÊTETÉ (constats d'Alain,
#          25/09/2026).
#          ① LA MOLETTE CHANGEait LA VALEUR DES LISTES DÉROULANTES. Tk associe
#            la molette aux `ttk.Combobox` par une liaison de CLASSE
#            (`ttk::combobox::Scroll`, vérifiée : un cran de molette fait passer
#            la valeur de « a » à « b ») : en défilant les réglages, si le
#            curseur passait sur (ou près de) une liste, elle changeait TOUTE
#            SEULE — profil de capteur/filtre de la SPCC, méthode du recalage,
#            référence de blanc… Des réglages ont donc pu changer sans que
#            l'utilisateur l'ait voulu, et FAUSSER DES TESTS. Les liaisons de
#            classe de la molette sont SUPPRIMÉES au démarrage (`unbind_class`
#            sur TCombobox/TSpinbox/Spinbox) : la molette ne modifie plus aucune
#            liste, elle continue de faire défiler le panneau ; pour changer une
#            valeur il faut désormais OUVRIR la liste. Banc :
#            `_test_ui_visibilite_jalon47.py` [7] (3 crans de molette → valeur
#            inchangée, et le choix explicite fonctionne toujours).
#          ② AVASPCC/AVAGAIA DISENT QUAND RIEN N'EST APPLIQUÉ : si la case est
#            cochée mais qu'aucune mesure exploitable n'existe, l'en-tête écrit
#            « non appliquee (case cochee, mesure indisponible) » au lieu de
#            rester muet — c'est ce silence qui avait fait croire que la SPCC
#            était entrée dans un fichier alors que non.
#          ③ LA MESURE SPCC EST FAITE UNE FOIS PAR SESSION (c'est son principe,
#            et un décochage/recochage la refait) : le libellé le DIT désormais
#            — « mesure faite sur N frames (décocher/recocher la case pour
#            refaire) ». Sans ça, la case semble « ne plus rien rafraîchir ».
# v2.35.1 : CORRECTIF DE LA CHAÎNE PLEINE RÉSOLUTION EN COMPOSITION (constat réel
#          d'Alain, 25/09/2026, sur son empilement M31 RGB de 165 frames).
#          LA CHAÎNE LIVE EST CONTRACTÉE POUR [0..1] ET LE COMPOSITE DÉPASSE 1 :
#          • le débruitage live (NLM) fait `np.clip(data, 0, 1)` pour passer en
#            16 bits — mesuré sur l'empilement réel : 71 232 des 73 766 pixels
#            > 1 ÉCRÊTÉS (96 %) ;
#          • GraXpert live reçoit une image > 1 qu'il normalise : sa sortie
#            revient autour de 1.
#          Conséquence sur la 3e sortie « empilement traité (linéaire) » écrite
#          par Alain : AVASCALE = 1,2106 au lieu de 17,94 (échelle divisée par
#          ~15) et cœurs d'étoiles écrêtés — le fichier n'était plus linéaire.
#          CORRECTIF : en COMPOSITION et vue « empilement », la sauvegarde
#          pleine résolution (« tel que vu » ET « empilement traité (linéaire) »)
#          exécute la chaîne PAR COUCHE, exactement comme le solveur live :
#          GraXpert puis débruitage sur CHAQUE couche 2D (toutes ≤ 1),
#          recomposition (`composer`), CORRECTIONS, puis netteté/SCNR. Le
#          composite reste dans sa plage linéaire (aucun écrêtage, aucune
#          remise à l'échelle) et le fichier correspond enfin à l'écran.
#          `ui.app._couches_pleine_resolution` porte la chaîne (sans cache : une
#          sauvegarde est un instantané) ; `denoise._nlm` documente désormais son
#          CONTRAT D'ÉCHELLE [0..1] (l'écrêtage était silencieux).
#          Aussi : les dialogues de sauvegarde portent le titre du bouton
#          employé, et les erreurs d'outil par couche sont affichées (non
#          bloquantes) au lieu d'être perdues.
#          OUTIL AJOUTÉ : `_diag_empilement_couleur.py` — que contiennent les
#          fichiers (fond et σ par canal, contraste de fond R/G et B/G, rapport
#          brut/traité, clés AVA*). C'est ce qui a identifié le problème.
#          BANC : `_test_save_brute_jalon59.py` [7] vérifie que GraXpert live
#          voit bien 2 COUCHES 2D (jamais le composite) et que l'échelle
#          linéaire est PRÉSERVÉE (AVASCALE ≈ celle du brut, contre 1,21 avant).
#          Aussi (même journée) : les dialogues d'enregistrement affichent la clé
#          AVAAPPLI du fichier écrit (« aucune (empilement BRUT) », « SPCC +
#          equilibrage canaux + recalage colorimetrique »…) — on n'avait AUCUN
#          moyen de savoir, au moment du clic, si la SPCC était entrée dans le
#          fichier ; et `_diag_empilement_couleur.py` mesure désormais le
#          PLANCHER DE BRUIT par canal (le GRAIN) et son équilibre R/G, B/G.
#          MESURE DURABLE (25/09/2026, M31 RGB 165 frames d'Alain) : le grain des
#          COUCHES brutes est équilibré (σ 0,000498 / 0,000557 / 0,000526 →
#          R/G 0,89 · B/G 0,94) mais il devient COLORÉ dans le composite
#          (0,00517 / 0,00781 / 0,01133 → R/G 0,66 · B/G 1,45) : la
#          normalisation par rôle de `composer()` divise chaque canal par SA
#          propre dynamique (p99,7−p0,25), celle du bleu étant 2,1× plus étroite
#          que celle du rouge → le grain bleu est amplifié 2,2× de plus que le
#          rouge. Le « grain bleu-vert » NAÎT donc dans la composition, avant
#          tout étirement et avant les corrections (voir AVANCEMENT.md, piste
#          ouverte : normalisation COMMUNE aux trois rôles).
# v2.35.0 : LA SAUVEGARDE LINÉAIRE DEVIENT BRUTE + LES CORRECTIONS DE COULEUR
#          PASSENT DANS LA CHAÎNE DE SORTIE (chantier du 24/09/2026, décisions
#          d'Alain ; étapes ①→⑦ du plan).
#          Règle appliquée : « la sauvegarde linéaire est BRUTE — elle ne
#          contient QUE l'empilement : ni retrait de gradient, ni correction de
#          couleur ». Avant cette version, les gains SPCC/Gaia, l'équilibrage
#          des canaux et le recalage « Linear Fit » entraient dans le fichier
#          (via composer()), donc l'état du fichier dépendait des cases cochées
#          — et une part des corrections y était absorbée par la normalisation
#          par rôle. C'est terminé.
#          • composer() n'applique PLUS de gains : il produit l'EMPILEMENT
#            BRUT (normalisation par rôle + combine L). Toutes les corrections
#            de couleur vivent désormais en AVAL, dans `corrections_couleur()`
#            (composition.py : gains R/G/B → équilibrage des canaux → recalage
#            Linear Fit) ; `composer(gains=…)` n'existe plus (un appelant qui
#            l'utilisait encore doit appeler `appliquer_gains()`).
#          • `CompositeStacker.mean()` / `mean_avec_canaux()` reçoivent
#            `corrections=True` (DÉFAUT = comportement d'affichage inchangé) ;
#            `corrections=False` rend l'EMPILEMENT BRUT. `LiveStacker.mean()`
#            accepte le même paramètre (il n'y a pas de correction de couleur
#            en mono, mais l'interface des deux est identique).
#          • SAUVEGARDE « 💾 Enregistrer l'empilement (linéaire)… » et
#            « 💾 Enregistrer les canaux (par filtre)… » : chemin BRUT. Le
#            fichier est IDENTIQUE avec ou sans SPCC / gains Gaia / équilibrage
#            / Linear Fit cochés (banc _test_save_brute_jalon59.py) — l'affichage,
#            lui, change bien.
#          • SOLVEUR LIVE (display._vl_worker) : les trois réglages de couleur
#            sont transportés dans le job (6e élément = équilibrage actif/force/
#            cadre, déballage tolérant) et appliqués APRÈS la recomposition des
#            couches traitées, AVANT la netteté — ordre validé par Alain :
#            GraXpert par couche → débruitage → CORRECTIONS → netteté/SCNR →
#            étirement. Le traitement EXTERNE par couche fait de même.
#          • NOUVELLE 3e SORTIE LINÉAIRE — « 💾 Enregistrer l'empilement traité
#            (linéaire)… », bouton DÉDIÉ dans le cadre « Sortie » (décision (a)) :
#            empilement brut → gradient live → débruitage live → CORRECTIONS →
#            netteté → SCNR, SANS étirement ni gamma/saturation ; en-tête
#            auto-descriptif (AVAAPPLI/AVAVUE). Le bouton « 💾 Enregistrer le
#            résultat traité (linéaire)… » du cadre « Traitement externe »
#            reste, lui, lié au ⚡ manuel (instantané GraXpert/BXT).
#          • EN-TÊTES (mesure vs appliqué) : AVASPCC/AVAGAIA étaient écrits
#            comme des APPLICATIONS — ils sont désormais les MESURES de la
#            session (même format, K=… / B=…), et la nouvelle clé AVAAPPLI dit
#            ce qui est RÉELLEMENT appliqué à l'image écrite (« aucune
#            (empilement BRUT) » pour le fichier brut, liste des corrections
#            pour la sortie traitée) ; AVAWB/AVAFIT ne sont écrits que s'ils
#            sont appliqués ; AVAVUE décrit la vue enregistrée. Sans cette
#            distinction, un fichier brut portant AVASPCC aurait MENTI.
#            _entete_reglages(applique=False) pour le brut ; les fichiers
#            canal_*.fit restent des couches brutes (AVALAYER).
#          • BANC NOUVEAU `_test_save_brute_jalon59.py` : [1] composer() ne
#            porte plus de gain (appliquer_gains le fait) ; [2] mean()
#            corrections=True/False : écarts exacts attendus, entrée jamais
#            modifiée ; [3] FICHIER LINÉAIRE IDENTIQUE cases cochées/décochées
#            (preuve de « brut ») + en-têtes mesure/appliqué ; [4] solveur live :
#            équilibrage transporté et appliqué après recomposition ;
#            [5] réel : worker → bouton « empilement traité (linéaire) » écrit un
#            fichier AUTO-DESCRIPTIF sans étirement.
# v2.34.7 : LES FICHIERS ENREGISTRÉS DEVIENNENT AUTO-DESCRIPTIFS (question
#          d'Alain, 24/09/2026 : « et la sauvegarde, empilement linéaire, elle
#          sauvegarde quoi au juste ? »).
#          Nouveaux mots-clés d'en-tête FITS, écrits à la sauvegarde LINÉAIRE de
#          l'empilement ET à celle des couches :
#            AVACOMPO — composition et normalisation appliquée
#                       (« HOO, normalisation par role (percentiles) ») ;
#            AVASPCC  — coefficients SPCC appliqués (« K=0.6232/0.7574/1.0000 »)
#                       ABSENT si la SPCC n'était pas active ;
#            AVAGAIA  — gains Gaia relatifs appliqués (« B=1.0459 G=1.3368 »),
#                       ABSENT si la case était décochée ;
#            AVAWB    — équilibrage des canaux auto et sa force (si coché) ;
#            AVAFIT   — recalage colorimétrique et son mode (si coché) ;
#            AVAFRAME — nombre de frames empilées ;
#            AVALAYER — « couche BRUTE (ni normalisation, ni gain) » sur les
#                       fichiers canal_<rôle>.fit.
#          POURQUOI : la sauvegarde linéaire n'est PAS l'image brute — elle
#          contient la moyenne temporelle par rôle, la normalisation par canal
#          de `composer()`, les gains (manuels × [SPCC OU Gaia]), l'équilibrage
#          des canaux et le recalage colorimétrique s'ils sont cochés, puis un
#          bornage global [0,1] (AVASCALE) — et AUCUN étirement. Il fallait
#          deviner tout cela à l'ouverture du fichier : c'est désormais écrit
#          dedans (ASCII, FITS standard, lisible par Siril/astropy).
#          Vérifié au banc : AVALAYER/AVAFRAME/FILTER sur les couches,
#          AVACOMPO sur l'empilement, AVASPCC présent quand la SPCC est active
#          et ABSENT sinon (le fichier ne ment pas sur ce qu'il contient).
# v2.34.6 : RÉPONSE COMPLÈTE À LA QUESTION D'ALAIN SUR LA SAUVEGARDE LINÉAIRE,
#          ET PIÈGE ÉVITÉ (une « correction » testée puis REJETÉE).
#          • SA QUESTION : « pourquoi dis-tu que la sauvegarde linéaire n'est pas
#            la même base que celle sur laquelle tu appliques la SPCC ? »
#            RÉPONSE, code en main : la mesure SPCC passe par
#            `CompositeStacker.moyennes()` → `LiveStacker.mean()` par rôle =
#            les couches BRUTES ; la SAUVEGARDE passe par `mean()` →
#            `composer()`, qui applique à CHAQUE RÔLE `normaliser(a, lo, hi)`
#            avec lo/hi = ses PROPRES percentiles (0,25 % / 99,7 %), soit
#            `(a − lo)/(hi − lo)`, PUIS les gains. Chaque canal est donc recalé
#            sur sa propre échelle avant que les coefficients s'appliquent : les
#            ratios de couleur de l'image enregistrée ne sont plus ceux des
#            couches. Vérifié au banc : un contraste R/G de 1,60 dans les
#            couches devient 1,000 dans le composite (écrasé par la
#            normalisation par rôle).
#          • PIÈGE TESTÉ PUIS REJETÉ : appliquer une normalisation COMMUNE aux
#            trois canaux quand des gains de couleur sont actifs (pour que la
#            mesure et l'image produite parlent de la même base) CASSE le
#            rendu : sans soustraction du fond, le fond pollué déséquilibré
#            devient visible et l'étirement l'amplifie (mesuré sur les couches
#            réelles d'Alain : R/G affiché 0,079 — image inutilisable). Le code
#            a été RETIRÉ (le commentaire de `mean_avec_canaux` garde la mesure
#            et la raison), et le banc de composition [10] documente désormais
#            le comportement RÉEL.
#          • LA BONNE RECETTE (mesurée sur ses couches, étirement réel) :
#            SPCC seule → fond linéaire 0,0130 / 0,0219 / 0,0385 (très bleu) ;
#            SPCC + RECALAGE COLORIMÉTRIQUE (Linear Fit, « Gain + offset ») →
#            0,0213 / 0,0219 / 0,0220 (fond NEUTRE), image à l'écran quasi
#            neutre (R/G 1,011 ; B/G 0,977). C'est exactement ce que Siril fait
#            en un clic (coefficients + « référence de fond du ciel » B0/B1/B2) :
#            dans AVAStack, les deux réglages existent séparément — à cocher
#            ENSEMBLE. Le banc [10] vérifie que le recalage neutralise des fonds
#            inégaux (0,200/0,050/0,020 → 0,053/0,050/0,052).
#          • Rappel : un enregistrement d'empilement n'est PAS comparable aux
#            couches pour valider une SPCC (utiliser `_diag_spcc.py
#            --export-rgb`), et la case « Équilibrage des canaux (auto) » est
#            indépendante de la SPCC (elle n'agit que si on la coche ; elle est
#            désormais fonctionnelle en composition, cf. v2.34.5).
# v2.34.5 : VALIDATION CROISÉE AVEC SIRIL RÉUSSIE (mêmes pixels) + BUG de
#          l'ÉQUILIBRAGE DES CANAUX en composition.
#          • VALIDATION (2e essai d'Alain, 24/09/2026) : `_diag_spcc.py
#            --export-rgb` a fourni à Siril les couches BRUTES concaténées
#            (spcc_brut_RGB.fit). Siril donne R/V = 0,087250 + 0,872563·cat
#            (σ 0,1226) et B/V = 0,114178 + 0,792972·cat (σ 0,1184), K = 0,636 /
#            0,775 / 1,000. AVAStack, sur les MÊMES pixels : pentes 0,888
#            (σ 0,020) et 0,782 (σ 0,019), K = 0,6232 / 0,7574 / 1,0000 →
#            ÉCART DE 1,4 À 1,8 % sur les pentes, ~2 % sur les coefficients, et
#            une dispersion 6 FOIS MEILLEURE. Les deux chaînes concordent : la
#            divergence des essais précédents venait bien des IMAGES analysées
#            (fichiers normalisés par rôle / gains Gaia appliqués), pas du
#            modèle — l'intuition d'Alain était juste.
#          • BUG CORRIGÉ : la case « Équilibrage des canaux (auto) », cochée,
#            n'avait AUCUN effet en mode composition — `LiveStacker._equilibrer`
#            est no-op sur une carte 2D, or chaque RÔLE d'une composition EST
#            une carte 2D (l'équilibrage attend une image couleur). Elle
#            s'applique désormais au COMPOSITE (H, W, 3), après la
#            normalisation par rôle, avec cache par (frames, force, cadre) et
#            force partielle comme en mono. Vérifié au banc : fonds R/G/B
#            0,30/0,15/0,10 → 0,16510 partout ; force 0,5 → partiel.
#          • MESURE DE FOND (documentée, non corrigée) : `composer()` normalise
#            DÉJÀ chaque rôle par ses percentiles (0,25 % / 99,7 %) — les fonds
#            sont donc écrasés canal par canal et une PART des corrections de
#            couleur est absorbée. C'est pourquoi la SPCC (comme les gains Gaia)
#            a un effet VISIBLE mais modéré sur l'image affichée (mesuré : R/G
#            0,877 → 0,793 et B/G 1,136 → 1,325 après étirement) — alors que
#            Siril, qui ne normalise PAS par canal, voit ses coefficients
#            s'appliquer pleinement (+ sa référence de fond par canal B0/B1/B2,
#            d'où son fond non bleu). PISTE NOTÉE : option de normalisation
#            COMMUNE aux trois canaux quand des gains de couleur sont actifs.
#          • RÉPONSES AUX QUESTIONS D'ALAIN : (1) la correction EST appliquée au
#            rendu et aux sauvegardes (le bloc qui pose les gains tourne à
#            chaque tour de worker, même sans nouvelle brute) ; (2) un
#            enregistrement d'empilement n'est PAS comparable aux couches
#            (normalisation par rôle + gains : gains implicites mesurés R/G
#            0,944 et B/G 1,242 sur le sien) — d'où l'export RGB brut ; (3) le
#            FOND coloré relève du retrait de gradient / du recalage
#            colorimétrique (offset), pas de la SPCC, qui s'adresse aux
#            ÉTOILES.
# v2.34.4 : OUTIL DE COMPARAISON STRICTE AVEC SIRIL + éclaircissement de trois
#          points soulevés par Alain après son 2e essai réel (153 frames).
#          • NOUVEAU `_diag_spcc.py --export-rgb FICHIER` : écrit un FITS RGB des
#            couches BRUTES (concaténation simple, AUCUNE normalisation ni gain)
#            avec les mots-clés WCS, à faire analyser par Siril. POURQUOI c'était
#            nécessaire : une sauvegarde d'empilement d'AVAStack passe par
#            `composer()`, qui NORMALISE chaque rôle par ses percentiles (et y
#            applique les gains) — ses ratios de couleur ne sont donc ceux
#            d'AUCUNE couche : les pentes de Siril sur un tel fichier ne sont pas
#            comparables aux nôtres (mesuré : gains implicites R/G 0,944 et
#            B/G 1,242 sur le fichier enregistré, ni les K SPCC 0,823/1,320 ni
#            les gains Gaia 0,945/1,153 — c'est bien la normalisation par rôle).
#            Vérifié : l'export contient EXACTEMENT les couches (canal par canal
#            identiques au bit près), dans l'ordre R/G/B standard, BITPIX -32.
#          • PIÈGE DE WCS dans le banc : il utilisait le fichier `.wcs` séparé,
#            qui décrit une AUTRE grille dès que la session a été ré-empilée
#            (couches recadrées de 6 px → 16 appariements au lieu de ~2000).
#            Le WCS est désormais lu DANS L'EN-TÊTE DE LA COUCHE (elle porte les
#            mots-clés de sa propre grille, jalon 56), le `.wcs` ne servant que
#            de secours.
#          • « JE NE VOIS PAS LA DIFFÉRENCE SPCC COCHÉE / DÉCOCHÉE » : vérifié
#            de bout en bout (canaux → composer() → DisplayProcessor, STF ET
#            VeraLux) — la correction EST appliquée et VISIBLE : avec les
#            coefficients d'Alain, le rapport R/G de l'image affichée passe de
#            0,877 à 0,793 et B/G de 1,136 à 1,325 (l'étirement atténue les
#            gains de moitié environ, mais ne les annule pas ; `_auto_params`
#            calcule ses statistiques sur la LUMINANCE, jamais par canal).
#            EXPLICATION DE FOND (et réponse à sa question sur le gradient) :
#            la SPCC corrige la couleur des ÉTOILES contre une référence
#            (galaxie spirale moyenne) et applique les MÊMES gains au FOND de
#            ciel — un fond pollué (bleu-vert) reste donc bleu-vert, voire le
#            devient davantage puisque la référence de blanc est plus rouge que
#            verte (K_G < K_R dans le repère instrument). C'est exactement
#            pourquoi Siril exige un retrait de gradient AVANT : la couleur du
#            FOND relève du retrait de gradient, celle des ÉTOILES de la SPCC —
#            deux traitements distincts, à ne pas confondre.
#          • Rafraîchissement du rendu en fin d'empilement : VÉRIFIÉ sain — le
#            bloc qui pose `gains_roles` et demande le rendu est AVANT la lecture
#            d'une frame (il tourne donc même quand plus aucune brute n'arrive,
#            leçon du jalon 55 appliquée).
# v2.34.3 : SÉLECTION DES ÉTOILES CORRIGÉE — un BIAIS RÉEL de mesure, révélé par
#          l'écart entre l'appli et les bancs (constat Alain, 24/09/2026).
#          L'appli mesurait sur les 300 étoiles les PLUS BRILLANTES seulement, et
#          n'écartait que celles à moins de 0,5 mag de la plus brillante.
#          MESURE sur les couches réelles d'Alain (1179 étoiles appariées) :
#            • 150 étoiles → pente R/G 0,518 et B/R ×1,255 ;
#            • 300 étoiles (réglage d'alors) → 0,576 et ×1,311 ;
#            • 900 étoiles → 0,765 et ×1,480 ;
#            • 2400 étoiles → 0,817 et ×1,499 (CONVERGE).
#          POURQUOI : les étoiles brillantes ont le cœur COMPRIMÉ (saturation,
#          sortie de linéarité du capteur) → leur contraste de COULEUR est
#          écrasé, ce qui atténue la pente de régression et fausse les
#          coefficients (chez Alain : K_R 0,7192 au lieu de 0,6683, soit une
#          correction de rouge fausse de 7 % et un rapport B/R de ×1,39 au lieu
#          de ×1,50). Les ±σ de l'appli (0,032 / 0,074) ne le voyaient pas : la
#          dispersion restait faible, c'était un BIAIS, pas du bruit.
#          CORRECTIF : MAX_ETOILES 300 → 1200 et MARGE_SATURATION 0,5 → 1,5 mag
#          (les deux constantes portent le constat complet en commentaire).
#          RÉSULTAT sur les mêmes couches : 946 étoiles retenues, pentes 0,819
#          (σ 0,037) et 0,782 (σ 0,017), K = 0,6683 / 0,7548 / 1,0000 — mesure
#          ENTIÈRE en 0,9 s (détection + catalogue spectral + régressions).
#          PIÈGE DE BANC corrigé au passage : les étoiles synthétiques du banc
#          n'avaient pas de plage de LUMINOSITÉ (les spectres sont normalisés à
#          500 nm par `photons`), donc toutes les magnitudes étaient voisines :
#          le nouveau seuil de saturation en écartaient la quasi-totalité et le
#          test ne mesurait plus rien. Le banc tire désormais une magnitude
#          (0-5 mag) indépendante de la couleur — la vérité analytique tient
#          toujours (pentes 0,6999 / 1,2998 retrouvées).
#          VERIFIÉ AUSSI : l'ÉQUILIBRAGE des canaux (auto) n'influence PAS la
#          SPCC ni la photométrie (`CompositeStacker.moyennes()` ne renvoie que
#          les couches BRUTES par rôle, et l'équilibrage est no-op sur une carte
#          2D) — la mesure porte bien sur l'image brute, comme il faut.
#          RESTE À FAIRE (noté, non fait) : la photométrie Gaia du jalon 56
#          garde MAX_ETOILES_PHOTO = 300 et sa marge de 0,5 mag — même famille
#          de biais possible sur ses ZÉRO-POINTS (à mesurer avant de toucher un
#          module validé).
# v2.34.2 : DEUX BUGS RÉELS CORRIGÉS (constatés par Alain sur la 2.34.0).
#          • np.trapz SUPPRIMÉ de numpy 2.x (renommé np.trapezoid, puis retiré
#            des versions suivantes : chez Alain, Python 3.14 + numpy récent) :
#            la ligne d'état affichait « SPCC : interrompue (AttributeError:
#            module 'numpy' has no attribute 'trapz') » et AUCUNE calibration
#            n'était possible. L'intégration passe par un appel COMPATIBLE numpy
#            1 ET 2 (`_trapeze` : trapezoid si présent, trapeze sinon — même
#            algorithme, résultat identique au bit près). Angle mort expliqué :
#            sur la machine de développement numpy 2.3.3 garde encore trapz
#            (déprécié), donc les bancs passaient ; le banc SUPPRIME désormais
#            np.trapz à la volée pour reproduire la panne et vérifier le calcul.
#          • COHÉRENCE DES BANDES : « Filtre R : QHYCCD MiniCam8M Luminance »
#            (vu sur la capture d'Alain) donnerait des coefficients FAUX (bande
#            large à la place d'une couleur), tout comme deux profils
#            identiques. Nouveau `spcc.coherence_bandes()`, partagé par le
#            diagnostic du module ET par l'UI, qui affiche l'alerte DÈS LA
#            SÉLECTION des profils (sans attendre une mesure) : le chiffre est
#            refusé/expliqué plutôt que trompeur. Les avertissements de bandes
#            et de pente/dispersion se CUMULENT désormais au lieu de s'écraser.
#          Banc SPCC : tests ajoutés (numpy sans trapz, luminance, filtres
#          répétés, filtres d'Alain sans avertissement, alerte immédiate dans
#          l'UI) et banc rendu HERMÉTIQUE (config.json de la machine vidée : la
#          case SPCC cochée et les profils choisis par l'utilisateur ne doivent
#          pas fausser les valeurs par défaut testées). Tous les bancs au vert.
# v2.34.1 : ENQUÊTE SIRIL CLOSE (2e log) — la divergence des pentes venait de
#          L'IMAGE, pas du modèle ; protection UI SPCC / gains Gaia.
#          • 2e log SPCC de Siril (après retrait de gradient) : ses pentes ne
#            bougent PAS (0,6459 → 0,6456 ; 1,0459 → 1,0449) → la divergence
#            n'était pas le gradient ;
#          • l'image qu'il analyse (`m31_stacl_lineaire.fits`) N'EST PAS la
#            somme de `canal_R/G/B.fit` : elle porte les GAINS GAIA de la
#            session (rapports mesurés R/G 0,9651 et B/G 1,2022 ≈ ×0,9451 /
#            ×1,1530 du jalon 56) — la sauvegarde avait été faite case « Gains
#            photométriques (Gaia) » COCHÉE. Siril calibrait une image DÉJÀ
#            refroidie par nos gains et ses K la réchauffent pour annuler ces
#            gains : les deux jeux n'étaient pas comparables. Règle pour toute
#            comparaison à venir : sauvegarder le linéaire avec les gains Gaia
#            DÉCOCHÉS ;
#          • protocole EXACT de Siril rejoué (disque 10,6 / anneau 10,6→20,6)
#            sur l'image équilibrée : nos pentes 0,756 / 0,899 contre 0,646 /
#            1,046 → écart ~15 %, du même ordre que SA dispersion (0,131 /
#            0,151 mag) : les deux mesures sont compatibles à ses barres
#            d'erreur, le résidu venant de la méthode (centroïdes PSF,
#            exclusion de 2081 étoiles, fond par canal), pas du modèle ;
#          • TEST DE SENSIBILITÉ aux bandes (7 jeux de filtres, jusqu'aux
#            Johnson-Cousins) : K_R ne varie que de 0,748 à 0,775 → les profils
#            de la base (qualité 2/5) ne sont PAS le maillon faible ;
#          • UI : quand la SPCC est active, la ligne des gains annonce
#            « REMPLACÉS par la SPCC » (aucune double correction silencieuse).
# v2.34.0 : SPCC ABSOLUE BRANCHÉE + VALIDATION CROISÉE AVEC SIRIL RÉUSSIE
#          (jalon 58, suite ; demande d'Alain : « une vraie correction de
#          couleur comme Siril et son SPCC »).
#          VALIDATION CROISÉE (la preuve qui manquait) : Alain a fourni le log
#          de SA SPCC dans Siril sur les mêmes couches M31 — R/V = 0,086296 +
#          0,645948·cat ; B/V = 0,194367 + 1,045936·cat ; K = 1,000 / 0,923 /
#          0,866. De k_G = 1/max = 0,923 on déduit les ratios de blanc que
#          Siril a utilisés (1,2953 / 0,8332). AVAStack obtient, avec les
#          profils Sony IMX585 × QHYCCD MiniCam8M R/G/B de la MÊME base
#          (copiée de cette machine) : 1,2954 / 0,8331 → ACCORD À 1e-4. Les
#          réponses QE × transmission et le traitement de la référence de blanc
#          sont donc validés au chiffre près.
#          PIÈGE MAJEUR TROUVÉ EN CHEMIN (et corrigé dans le modèle) : la
#          conversion des spectres en COMPTAGE DE PHOTONS (× λ, cf. Siril
#          `flux_to_relcount`) n'est PAS neutre sur les ratios — λ est À
#          L'INTÉRIEUR des intégrales, donc ∫S·λ·R/∫S·λ·G ≠ ∫S·R/∫S·G (17,2 %
#          d'écart mesuré au banc). La référence de blanc DOIT donc passer par
#          la même conversion que les étoiles : sans elle, les coefficients
#          passaient à 0,983/0,974/1,000 (quasi neutres, correction fausse de
#          ~20 %) au lieu de la vraie correction. Fonction dédiée
#          `spcc.spectre_reference` + docstring du piège.
#          ORCHESTRATION RÉUTILISABLE : `spcc.coefficients_spcc()` (détection,
#          appariement mutuel Gaia, flux d'ouverture par canal, étoiles
#          saturées et étoiles posées sur l'objet ÉTENDU écartées, réponses,
#          référence de blanc, régressions robustes, coefficients) et
#          `spcc.SessionSpcc` (état de session, gains par RÔLE, texte d'état).
#          GARDE-FOU repris de Siril : pente de régression hors [0,5 ; 1,5] ou
#          dispersion > 0,5 mag → « avertissement » affiché (Siril écrit
#          « solution imprécise, pensez à corriger d'abord le gradient ») —
#          jamais un chiffre présenté comme sûr quand la mesure ne l'est pas.
#          INTERFACE (jalon 58) : case « SPCC (couleurs absolues) », DÉCOCHÉE
#          PAR DÉFAUT (opt-in, même choix que les gains Gaia), sélecteurs
#          CAPTEUR / FILTRE R / G / B / RÉFÉRENCE DE BLANC peuplés par la base
#          Siril (15 capteurs, 50 filtres, 144 références mesurés ici ; profils
#          d'Alain pré-sélectionnés), ligne d'état qui dit toujours ce qui est
#          appliqué ou POURQUOI rien ne l'est (base absente, mode MONO, en
#          attente), persistance en config.json, actif seulement en
#          composition R/G/B avec WCS résolu. PRIORITÉ : quand la case SPCC est
#          cochée, ses coefficients remplacent les gains Gaia RELATIFS du
#          jalon 56 (mesurés, eux, contre une magnitude G trop large — c'est
#          ce biais de bande qui refroidissait l'image).
#          BANC `_test_spcc_jalon58.py` (11 sections) : ce banc FABRIQUE une
#          image cohérente avec le modèle (spectres de Planck × réponses,
#          atténuations instrumentales CONNUES ×0,7 / ×1,3) et vérifie la
#          VÉRITÉ ANALYTIQUE — pentes retrouvées 0,7000 et 1,3000 (au 1e-3
#          près), blanc rendu NEUTRE après correction, robustesse de la
#          régression (1 aberration sur 40 sans effet), refus propres (capteur
#          et filtre inconnus, catalogue vide, WCS absent, canaux incomplets),
#          unités de longueur d'onde (le piège des références en ÅNGSTRÖMS),
#          et tout le branchement UI (case, sélecteurs, config round-trip,
#          gains écrits par rôle). PIÈGE DE BANC documenté : sans BRUIT de
#          fond, le détecteur répond « image constante » (médiane-MAD) — même
#          leçon que les jalons 19/21.
#          RÉSERVES ASSUMÉES (mesurées, pas cachées) : sur les couches M31
#          d'Alain, nos pentes valent 0,81 (R/G) et 0,78 (B/G) avec une
#          dispersion de 0,04 mag, là où Siril trouve 0,65 / 1,05 avec 0,131 /
#          0,151 mag — 3 à 6 fois plus dispersé, et Siril signale lui-même sa
#          solution comme imprécise sur cette image (gradient d'abord). La
#          validation croisée finale se fera sur une image SANS gradient, avec
#          le log Siril en regard. Découverte au passage : les couches fournies
#          ont un décalage R-G de 0,56 px (B-G : 0,07 px) — d'où les franges
#          rouge/cyan : à ré-empiler avec l'alignement sous-pixel du jalon 57.
#          SUITE DE L'ENQUÊTE (2e log Siril, 24/09/2026) :
#          • le retrait de gradient ne change RIEN à ses pentes (0,6459 →
#            0,6456 ; 1,0459 → 1,0449) : la divergence n'était pas le gradient ;
#          • l'image qu'il analyse (`m31_stacl_lineaire.fits`) N'EST PAS la
#            somme de `canal_R/G/B.fit` : elle porte les GAINS GAIA de la
#            session (rapport mesuré R/G 0,9651 et B/G 1,2022 ≈ ×0,9451 /
#            ×1,1530 du jalon 56) — la sauvegarde avait été faite case
#            « Gains photométriques (Gaia) » COCHÉE. Siril calibrait donc une
#            image DÉJÀ refroidie par nos gains, et ses K la « réchauffent »
#            pour annuler ces gains : les deux jeux de coefficients ne sont pas
#            comparables. PROTECTION UI : quand la SPCC est active, les gains
#            Gaia sont ignorés et la ligne des gains le dit explicitement ;
#          • en recréant l'image équilibrée et en appliquant le protocole exact
#            de Siril (disque 10,6 / anneau 10,6→20,6), nos pentes remontent à
#            0,756 / 0,899 contre 0,646 / 1,046 : écart ~15 %, du même ordre
#            que SA dispersion (0,131 / 0,151 mag) — les deux mesures sont donc
#            compatibles à ses propres barres d'erreur, le résidu venant de la
#            méthode (centroïdes PSF, exclusion de 2081 étoiles, fond par
#            canal) et non du modèle ;
#          • TEST DE SENSIBILITÉ (mêmes données, 7 jeux de filtres différents,
#            jusqu'aux Johnson-Cousins) : K_R ne varie que de 0,748 à 0,775
#            (B/R ×1,290 à ×1,337) → les profils de la base (qualité 2/5) ne
#            sont PAS le maillon faible : la correction est robuste au choix
#            des bandes, elle est fixée par la référence de blanc.
# v2.33.0 : SPCC ABSOLUE « à la Siril » — FONDATIONS + BUG MAJEUR DU DÉCODAGE
#          DES SPECTRES GAIA CORRIGÉ (jalon 58, demande d'Alain du 24/09/2026 :
#          « je voulais une vraie correction de couleur comme Siril et son
#          SPCC »).
#          POURQUOI : la photométrie RELATIVE du jalon 56 (zéro-point par
#          bande contre la magnitude Gaia G) ne PEUT PAS corriger la couleur —
#          G est une bande très large et rien ne relie les flux des bandes
#          instrumentales entre eux. Mesuré sur les couches M31 d'Alain :
#          dispersion des ZP croissante vers le bleu (R 0,162 / G 0,233 /
#          B 0,376 mag) et gains qui refroidissent l'image (R ×0,7665 /
#          B ×1,0426).
#          CE QUI EST LIVRÉ (fondations, sans branchement UI) :
#            • `catalogues/spcc_db.py` — lecture de la base SPCC de Siril
#              (`%LOCALAPPDATA%\siril-spcc-database`) : profils de CAPTEURS
#              (mono/OSC), de FILTRES (par canal) et de RÉFÉRENCES DE BLANC.
#              PIÈGE MESURÉ : le schéma Siril autorise QUATRE unités de
#              longueur d'onde et les fichiers les utilisent vraiment (les
#              références de blanc sont en ANGSTRÖMS : 1005…25050 Å) — sans
#              conversion, la référence tombait hors de la grille spectrale
#              (336-1020 nm) et toutes les intégrales étaient nulles ;
#            • `processing/spcc.py` — le MODÈLE de Siril, repris de la source
#              (src/algos/photometric_cc.c `get_spcc_white_balance_coeffs` +
#              spcc.c, lu le 24/09/2026) : réponse du canal = QE × filtre sur
#              la grille xp_sampled, spectre Gaia converti en comptage de
#              photons (× λ, normalisation 500 nm — facteur par étoile, donc
#              sans effet sur des ratios), flux attendus par intégrale, ratios
#              catalogue vs mesurés, RÉGRESSION ROBUSTE PAR MÉDIANES RÉPÉTÉES
#              (Siegel, celle de `repeated_median_fit`), coefficient
#              k = 1/(a + b·w_ref) avec référence de blanc, normalisation par
#              le plus grand. Échec → coefficients NaN (jamais un gain négatif
#              appliqué) ;
#            • `_diag_spcc.py` — banc de bout en bout sur des couches RÉELLES :
#              spectres Gaia du champ (WCS), appariement, flux d'ouverture par
#              canal, réponses, référence de blanc, coefficients, ET
#              comparaison OBJECTIVE (erreur des couleurs d'étoiles en
#              magnitudes) entre brut / équilibrage du fond / Linear Fit /
#              gains Gaia relatifs / SPCC ;
#            • `photometrie.etoiles_catalogue(..., spectres=True)` : interroge
#              les 48 CHUNKS spectrophotométriques (clé « chunks » de
#              `etat_local`) et joint les 343 flux par étoile.
#          BUG MAJEUR CORRIGÉ (`catalogues/siril_cat.py`) : le décodage des
#          spectres lisait l'ENTIER 0-65535 au lieu du DEMI-FLOTTANT
#          (`astype(np.float16)` au lieu de `view(np.float16)`) et
#          MULTIPLIAIT par 10^fexpo au lieu de DIVISER (cf.
#          io/local_catalogues.c). Résultat : des spectres quasi PLATS
#          (rapport 400/700 nm à 1,02 pour toutes les étoiles au lieu de
#          0,85-3,6) et une échelle absurde (1e20) — la SPCC sortait des
#          régressions sans signification (pente 5,5, coefficients négatifs).
#          Le bug était LATENT : aucun module n'utilisait les spectres avant
#          la SPCC (la photométrie du jalon 56 n'utilise que la magnitude G).
#          Banc catalogues ajusté : les rares valeurs NÉGATIVES du half-float
#          (8 points sur 200×343) sont un artefact du format, conservé comme
#          par Siril → le contrôle vérifie la finitude et une positivité
#          majoritaire (> 99 %), plus l'exhaustivité.
#          VÉRIFIÉ EN RÉEL (canaux M31 d'Alain, 24/09/2026) : 5463 étoiles du
#          catalogue spectral dans le champ, 296 appariements (médiane
#          0,71 px), 269-240 étoiles exploitables selon le filtre de fond,
#          réponses Sony IMX585 × QHYCCD MiniCam8M R/G/B, blanc
#          « Average Spiral Galaxy ». Coefficients SPCC mesurés : K_R 0,983 /
#          K_G 0,974 / K_B 1,000 (rapport B/R ×1,017) — la correction de
#          COULEUR DES ÉTOILES est faible sur ce champ, alors que les gains
#          Gaia du jalon 56 demandaient ×0,945 / ×1,153 (rapport B/R ×1,22) :
#          c'est le biais de bande de G, mesuré noir sur blanc.
#          ATTENTION (corrigé en v2.34.0, cf. entrée suivante) : ces
#          coefficients 0,983/0,974/1,000 étaient calculés avec la référence de
#          blanc SANS la conversion en comptage de photons — donc ~20 % trop
#          neutres. La conversion a été validée le lendemain contre les K réels
#          de Siril (accord à 1e-4 sur les ratios de blanc).
#          RÉSERVES À LEVER (prochaine étape) : pente de régression 0,57 au
#          lieu de 1 (profils de filtres QHY de qualité 2/5 scannés d'un
#          graphique, ou compression réelle des couleurs par les filtres
#          LRGB) → VALIDATION CROISÉE avec Siril à faire sur la MÊME image
#          (Siril affiche ses K0/K1/K2 dans son log). Les bancs du jalon 56
#          (catalogues, photométrie, solveur, propagation, branchement) sont
#          tous AU VERT après la correction du décodage.
# v2.32.0 : ALIGNEMENT SOUS-PIXEL ENTRE COUCHES (jalon 57 — constat réel
#          d'Alain, 24/09/2026 : « l'astrométrie et Gaia sont bons, mais
#          l'image n'est pas correcte » — franges rouge/cyan autour des
#          étoiles sur un empilement M31 R+G+B de 31 frames).
#          MESURES sur les fichiers réels (m31_stacl_lineaire.fits et
#          canal_R/G/B.fit, écrits à la même minute depuis la MÊME session et
#          la MÊME grille : le défaut est donc DANS l'empilement, pas dans la
#          sauvegarde ni dans le recadrage) :
#            • la couche ROUGE sort décalée de 0,573 px (dX −0,207 ± 0,231 ;
#              dY −0,534 ± 0,116 px ; 271 appariements d'étoiles mutuels,
#              mesure indépendante du WCS) alors que B/G sont alignés à
#              0,049 px → décalage SYSTÉMATIQUE (σ 0,12 px) ;
#            • la transformation R→G n'est PAS une translation pure :
#              échelle 0,9998 (dX varie de −0,51 à −0,12 px selon la zone) —
#              les chemins qui estiment rotation et échelle sont justes, un
#              « décalage moyen » ne l'est pas (piège d'analyse vérifié) ;
#            • CAUSE RACINE : le chemin ORB, retenu en production sur les
#              compositions large bande, ne PEUT PAS corriger le sous-pixel.
#              Ses points clés sont localisés à ~0,5-1 px et le consensus
#              RANSAC (seuil 2 px) est gagné par l'IDENTITÉ : mesuré, ORB
#              renvoyait Δ=(0,000, 0,000) pour la paire R/G réelle, et
#              laissait 0,17 à 0,40 px d'erreur résiduelle pour des décalages
#              imposés de 0,15 à 1,5 px (seuil RANSAC resserré à 1,0 px,
#              LMEDS sur inliers ou RANSAC 0,5 px : PAS mieux — l'identité
#              reste le consensus). Les chemins par CENTROÏDES d'étoiles
#              (« étoiles », « triangles ») laissent 0,02-0,04 px sur les
#              mêmes images.
#          CORRECTIF (portée voulue : LA MATRICE, pas la cascade) : nouveau
#          `StarAligner._raffiner_centroides(frame, M)`, appelé après un
#          succès d'ORB — détection des centroïdes de la frame (~100 ms,
#          MOINS que les 213 ms d'ORB), appariement MUTUEL serré (≤ 1,5 px)
#          dans le repère de la référence, ré-estimation d'une similitude
#          (RANSAC 0,75 px) sur ces seuls appariements, contre-test mutuel
#          final (2,5 px). Échec ou trop peu d'appariements → matrice d'ORB
#          INCHANGÉE (aucune régression possible) ; ligne d'état : méthode
#          « ORB+étoiles(N) ». Le reste de la cascade est intact (les bancs
#          qui forcent triangles/phase voient le même comportement).
#          VÉRIFIÉ EN RÉEL (canal_R vs canal_G de M31) : méthode retenue
#          ORB+étoiles(46), reste après correction (−0,019, −0,020) px sur
#          274 étoiles — contre (−0,207, −0,534) px avant. Latence d'une
#          frame : 213 → 309 ms. Bancs AU VERT : align jalon 13 et 15,
#          compo worker/multifolder/composition jalon 19, narrowband jalon 21,
#          restack compo jalon 20, gradient couche jalon 24, calib compo
#          jalon 53, crop intersection, photométrie jalon 56.
#          Outil embarqué `_diag_align_precision.py` : vérité terrain
#          (appariement mutuel), répartition SPATIALE du décalage, second
#          avis par corrélation de phase, ce que chaque chemin retourne
#          (reste mesuré APRÈS application) et précision sur décalages connus.
#          AU PASSAGE, bug réel corrigé dans `photometrie.flux_ouverture` :
#          les bornes de la zone de flux peuvent sortir de l'image d'un
#          demi-pixel (arrondi du centroïde) — numpy TRONQUE alors la zone
#          pendant que `np.mgrid` garde la taille théorique → IndexError
#          (constaté le 24/09/2026 sur un crop 1024×1024). Bornes ramenées
#          dans l'image ; le disque reste entier (marge d'anneau).
# v2.31.3 : BUG DU SOLVEUR INTERNE — APPARIEMENT DIRECT/CROISÉ (jalon 56,
#          retour réel d'Alain, 24/09/2026 : « l'astrométrie reste en attente
#          sur un empilement M31 de 12 frames alors que les étoiles ne
#          manquent pas »). L'écran montrait « 2/20 essais » (le quota
#          corrigé en v2.31.1 fonctionnait) et « en attente d'un empilement
#          plus profond » ; or le seeing annonçait 195 étoiles. DIAGNOSTIC
#          sur les fichiers frais d'Alain (m31_stacl_lineaire.fits + canaux) :
#            • ASTAP (référence indépendante) trouve le champ à 2,7″/4,9″ des
#              indices, échelle 2,4633″/px → INDICES ET CADRAGE PARFAITS ;
#            • le WCS vrai d'ASTAP montre que les 120 étoiles détectées
#              tombent sur Gaia à 0,91 px de médiane (98 sur 120 à < 2 px),
#              et les 60 étoiles du vote à 95 % → les DONNÉES sont bonnes ;
#            • le vote (échelle, angle) était LUI AUSSI juste : pic 714 paires,
#              échelle 1,0012 (2,4723″/px), angle −89,83° ;
#            • mais l'étape 2 ne récoltait que 4 inliers.
#          CAUSE RACINE (par couple identifié) : le vote accumule 4 cas —
#          parité × sens — dans des cases distinctes, et le code DÉDUISAIT
#          l'ordre des correspondances du cas gagnant (`anc`). C'est FAUX :
#          l'appariement d'une paire n'est pas observable au vote (direct
#          i1↔k1 et croisé i1↔k2 ne diffèrent que de π sur l'angle, soit
#          exactement le décalage porté par `ac + π`). Mesure sur un couple
#          connu bon (img 43,48 ↔ cat 28,79, miroir=True) : sa vraie
#          correspondance est DIRECTE, mais elle vote dans le pic du cas
#          « anc=1 » (336 paires) → appariement croisé imposé → 4 inliers ;
#          la similitude construite depuis les vraies correspondances donne
#          les 94 inliers attendus. CORRECTIF : le vote ne retient plus qu'un
#          PIC PAR PARITÉ (le plus peuplé), et le raffinement essaie les DEUX
#          appariements de chaque paire candidate (coût inchangé : 2 parités
#          × 2 appariements = les 4 cas d'avant).
#          VÉRIFIÉ EN RÉEL sur les fichiers d'Alain : couche R 96
#          appariements, G 94, B 83, composite RGB 94 et fichier composite
#          sauvegardé 94 (rms 0,59-0,63 px) — tous RÉSOLUS là où les 5
#          échouaient. Bancs : solveur synthétique, banc RÉEL M31
#          (« TOUT AU VERT », 86 étoiles sur le composite 2,6°), branchement
#          astro jalon 56, photométrie jalon 56 — tous au vert.
#          LATENCE : le solveur ainsi corrigé coûtait 18,6 s sur 3844×2171
#          (profil : 6,4 s de np.histogram2d dont 4,9 s de searchsorted, plus
#          une boucle de raffinement à ~1 700 couples). Optimisations, TOUTES
#          mesurées sur 5 images réelles (3 canaux M31, composite, brute G
#          N.I.N.A.) avec des rms STRICTEMENT identiques :
#            • vote par COMPTAGE DIRECT de bins (np.bincount) au lieu de
#              np.histogram2d, l'échelle (li/lc) calculée une seule fois par
#              bloc et l'angle du cas « +π » obtenu par rotation CIRCULAIRE
#              des bins ;
#            • RANSAC_N_CAT ramené de 120 à 60 (le raffinement continue de
#              travailler sur TOUT le catalogue, N_CAT_MAX) ;
#            • couples candidats du raffinement triés par LONGUEUR DÉCROISSANTE
#              et plafonnés (RANSAC_CAND_MAX = 400).
#          → 18,6 s → 6,0 s (÷3,1), rms inchangés (0,593 / 0,626 / 0,601 /
#          0,626 / 0,443 px).
#          PIÈGE (mesuré puis ABANDONNÉ) : borner les paires catalogue au vote
#          aux plus LONGUES (2 000 sur 7 136) casse le vote sur une brute
#          unique peu profonde (brute G N.I.N.A. : pic erroné à 1,614″/px au
#          lieu de 2,465, solve en échec) — le pic correct a besoin de TOUTES
#          les paires. Ne pas refaire l'essai.
#          Nouveaux outils de diagnostic embarqués : `_diag_vote.py`
#          (instrumente le vote et le raffinement, compare au WCS vrai d'ASTAP)
#          et `_diag_appariement.py` (écart de chaque étoile détectée à Gaia).
# v2.31.2 : OUTIL `_diag_solve_compo.py` — diagnostic de la résolution d'une
#          COMPOSITION : résout CHACUNE des couches séparées (canal_R/G/B.fit
#          écrits par « Enregistrer les canaux ») ET le composite — exactement
#          celui que l'appli analyse — sur les mêmes indices, et affiche les
#          compteurs bruts (étoiles détectées, fond, bruit MAD, catalogue,
#          appariements, rms, échelle, chemin retenu).
#          VÉRIFIÉ EN RÉEL sur les canaux de M31 d'Alain (23/09/2026) :
#          couche R 77 appariements (2,4664″/px), G 85 (2,4651), B 83 (2,4668),
#          COMPOSITE RGB 85 (2,4651) à rms 0,60 px — le composite n'est donc
#          PAS un handicap quand l'empilement est profond. Ce diagnostic
#          confirme que l'échec observé venait de la PROFONDEUR de l'empilement
#          au moment des essais (5 étoiles appariées) et du quota de 6 essais
#          épuisé trop vite (corrigé en v2.31.1 : 20 essais, backoff, essai
#          immédiat dès que l'empilement double).
#          Outil embarqué dans l'installateur.
# v2.31.1 : RÉESSAIS DE RÉSOLUTION ASTROMÉTRIQUE — CORRIGÉS (constat réel
#          d'Alain, 23/09/2026 : « l'astrométrie qui passait après quelques
#          frames ne passe plus avec 33 frames empilées »). DÉFAUT trouvé au
#          code, indépendamment du message affiché : le plafond était de
#          6 essais avec un délai FIXE de 20 s → les 6 essais se consommaient
#          en ~2 minutes, sur un empilement encore trop court (échec certain),
#          puis PLUS AUCUNE tentative de la session, même à 33, 100 ou 300
#          frames. Correctifs :
#            • plafond porté à 20 essais ;
#            • délai CROISSANT (backoff) : 20 s, 40 s, 60 s… plafonné à 5 min —
#              au lieu de brûler le quota en deux minutes ;
#            • essai IMMÉDIAT dès que l'empilement a DOUBLÉ depuis le dernier
#              essai (34 frames après 17 n'est plus la même mesure) ;
#            • messages d'état explicites : « en attente d'un empilement plus
#              profond (n/N essais, dernier sur M frames) » et, en cas
#              d'échec, « réessai automatique dès que l'empilement double ».
#          Le compteur reste remis à zéro quand les INDICES changent (nouvelle
#          cible = quota neuf). Banc étendu (backoff mesuré, doublement,
#          plafond large) — TOUT AU VERT.
#          BANCS HERMÉTISÉS (13 + jalon 19) : plusieurs bancs instanciaient
#          `ui.App` SANS simuler la config et lisaient donc le vrai
#          config.json — qui contient désormais la case « Astrométrie »
#          cochée et ses indices → le worker lançait de VRAIES résolutions
#          (lecture du catalogue Gaia) pendant que le banc mesurait sa
#          cadence. Constaté sur _test_compo_worker_jalon19 (stat de la
#          dernière frame plus jamais reçue). Règle du projet rappelée :
#          tout banc qui touche l'UI simule sa config.
# v2.31.0 : GAINS PHOTOMÉTRIQUES APPLIQUÉS AU COMPOSITE (jalon 56, étape 5,
#          OPT-IN demandé par Alain le 23/09/2026) : les facteurs mesurés à
#          l'étape 4 peuvent enfin CORRIGER l'image — case « Gains
#          photométriques (Gaia) », DÉCOCHÉE PAR DÉFAUT (la mesure, elle, reste
#          sans effet tant qu'elle n'est pas cochée).
#          PIÈGE CENTRAL, découvert au banc : `composer()` normalise CHAQUE
#          RÔLE par ses propres percentiles AVANT d'appliquer les gains — un
#          facteur par rôle appliqué en amont était donc ABSORBÉ (le composite
#          ne changeait pas : vérifié). Les facteurs mesurés sont convertis de
#          RÔLE en CANAL via `canaux_rgb` de la composition (HOO : Ha→R,
#          O3→G et B ; SHO : S2→R, Ha→G, O3→B ; RGB/LRGB : 1:1) et appliqués
#          APRÈS la normalisation, exactement là où sont appliqués les gains
#          manuels R/G/B — dont ils sont MULTIPLIÉS (`gains_effectifs()`).
#          Un rôle alimentant plusieurs canaux applique le même facteur à tous ;
#          un canal alimenté par plusieurs rôles prend la MOYENNE GÉOMÉTRIQUE
#          (cas rare, documenté). Composition Mono : aucun canal R/G/B → aucun
#          gain appliqué (un gain global ne se verrait pas et déréglerait
#          VeraLux, qui travaille en valeurs absolues) — l'appli le DIT.
#          Les COUCHES restent BRUTES (contrat jalon 54) : le solveur live
#          re-compose depuis les couches brutes et reçoit désormais les gains
#          EFFECTIFS dans `vl_compo` (les deux vues — « empilement » et
#          « traitée » — restent donc cohérentes) ; le cache du recalage Linear
#          Fit inclut ces gains (sinon un facteur qui apparaît ne recalculerait
#          pas le fit).
#          Worker : la case opt-in écrit `CompositeStacker.gains_roles` à
#          chaque tour quand une mesure existe (comparaison avant/après →
#          rafraîchissement du rendu sans attendre une nouvelle brute) ;
#          libellé dédié sous la case (ce qui est appliqué, ou pourquoi rien).
#          BANC `_test_photometrie_jalon56.py` section [10] TOUT AU VERT :
#          défaut intact (image identique), conversion rôle→canal (R ×2,
#          G/B ×0,5 en HOO), composite qui SUIT (×2,000/×0,500/×0,500), couches
#          brutes préservées, Mono sans effet, worker : rien quand la case est
#          décochée / facteurs écrits quand elle est cochée.
# v2.30.0 : PHOTOMÉTRIE — ZÉRO-POINT INSTRUMENTAL PAR BANDE (jalon 56, étape 4,
#          accord d'Alain du 23/09/2026) : les étoiles détectées dans
#          l'empilement sont APPARIÉES MUTUELLEMENT aux étoiles du catalogue
#          Gaia de Siril (positions + magnitude G) grâce au WCS résolu puis
#          propagé (étapes 2-3), et un zéro-point par bande est mesuré :
#              m_G + 2,5·log10(flux) = ZP(bande)
#          L'écart de zéro-point ENTRE BANDES est le déséquilibre de
#          sensibilité à corriger — c'est la version RELATIVE et VÉRIFIABLE de
#          la SPCC (aucun spectre requis ; la SPCC absolue, spectres Gaia
#          xp_sampled × transmissions filtre/capteur de la base Siril, viendra
#          ensuite). L'écriture des gains sur le stacker est l'ÉTAPE 5 : ici on
#          MESURE, on ne touche pas à l'image.
#          Module `processing/photometrie.py` (glue, numpy seul) :
#          `flux_ouverture` (somme disque MOINS fond local médian de l'anneau —
#          insensible à un gradient et aux voisines), `etoiles_image`
#          (réutilise le détecteur du projet), `etoiles_catalogue` (rayon
#          déduit du WCS : coins projetés), `apparier` (MUTUEL, tolérance en
#          PIXELS), `zero_point` (médiane + rejet MAD avec PLANCHER 0,05 mag —
#          sur des mesures parfaites le MAD vaut 0 et rien ne serait rejeté),
#          `gains_depuis_zp` (référence = ZP MÉDIAN, gains bornés 0,25–4 comme
#          l'équilibrage/Linear Fit), classe `Photometrie` (catalogue
#          INJECTABLE, réessais espacés plafonnés, canaux = bandes).
#          Worker : mesure UNE fois quand l'astrométrie est résolue, sur la
#          grille RECADRÉE (canaux et WCS de la même grille — piège évité),
#          ligne d'état dédiée « Photométrie (Gaia G) : ZP par bande » ;
#          case « Photométrie (zéro-point Gaia) » persistée (cochée par défaut :
#          la mesure n'a AUCUN effet sur l'image).
#          PIÈGES tranchés par le banc : (1) `float(tableau)` et `math.hypot`
#          sur les CINQ positions rendues par le WCS de référence (les coins +
#          le centre) → TypeError au premier appel réel, corrigé en
#          `np.asarray(...).ravel()` / `np.hypot` ; (2) sur des mesures
#          parfaites le MAD vaut 0 et plus aucune aberration n'était rejetée →
#          PLANCHER de rejet à 0,05 mag (PLANCHER_SIGMA_MAG).
#          BANC `_test_photometrie_jalon56.py` TOUT AU VERT (9 sections) :
#          flux par ouverture (gradient, bord), détection, appariement mutuel
#          (leurres rejetés), zéro-point (exactitude ×2 → +0,7526 mag, rejet
#          d'aberration), gains (référence médiane, bornes), mesure bout en bout
#          3 bandes dont B atténuée ×0,5 → gain MESURÉ ×2,000, échecs propres,
#          worker réel, et GAIA RÉEL : 244 appariements sur la brute G de M31
#          (médiane 0,46 px) avec 0,156 mag de dispersion (G 9,4 → 14,2).
# v2.29.0 : REPLI ASTAP quand AUCUN INDICE n'est disponible (accord d'Alain,
#          23/09/2026) : caméra live sans en-tête FITS, ni saisie, ni
#          OBJCTRA/OBJCTDEC → ASTAP tente de localiser l'empilement LUI-MÊME
#          et son centre sert d'indice au solveur interne (le WCS d'ASTAP sert
#          ensuite de REPLI si l'interne refuse : « ASTAP = référence
#          indépendante/repli »).
#          CONSTAT RÉEL DÉCISIF (23/09/2026) : ASTAP ne sait chercher SANS
#          position de départ qu'avec une base de BALAYAGE (G18/H18/W08/V05) ;
#          avec une base D50/D80 — la plus courante, seule installée chez
#          Alain — il ne cherche qu'AU VOISINAGE d'une position : tout
#          balayage échoue en ~0,4 s, quel que soit `-fov` (mesuré sur son
#          empilement M31 ; le même fichier est résolu en 0,2 s avec indices).
#          L'appli SONDE donc les bases (`astap.bases_installees` /
#          `balayage_possible`) et, sans base de balayage, n'engage PAS
#          d'attente inutile : elle DIT la cause et conseille la saisie d'une
#          position approximative (le solveur interne tolère ~1°).
#          GARDE-FOUS pour ne jamais bloquer l'acquisition : 1 seul balayage
#          par valeur de champ (`fov`), plafond ASTRO_MAX_AVEUGLES = 2 par
#          session, délai entre balayages, timeout 90 s, image écrite BORNÉE à
#          [0,1] dans un dossier temporaire (leçon v2.27.1) ; le WCS rendu est
#          adopté par `SuiviAstrometrie.adopter` (repli, méthode « astap »)
#          et reste propageable aux réempilements (WcsTan en référence).
#          PIÈGE DE CONVENTION tranché en réel : `-fov` d'ASTAP est la HAUTEUR
#          du champ (l'appli raisonne en LARGEUR est-ouest) — passer 2,6° pour
#          1,47° attendu échoue aussi.
#          UI : le champ de saisie peut rester SEUL (focale connue, cible
#          inconnue) — il guide le balayage ; messages d'état toujours
#          explicites (origine des indices, cause d'un échec, bases trouvées).
#          OUTIL : `_diag_astap_aveugle.py` (diagnostic réel : essaie plusieurs
#          `-fov`, affiche le verdict brut d'ASTAP, liste les bases installées
#          et confronte au solveur interne indicé).
#          BANC : `_test_astro_branchement_jalon56.py` section [8] (ASTAP
#          factice : indices fournis → solve interne ; interne en échec → WCS
#          ASTAP adopté ; échec ASTAP → état clair ; sans base de balayage →
#          aucun essai ; confrontation ASTAP RÉELLE si l'image M31 est là).
# v2.28.2 : CORRECTIF du bouton 📷 (v2.28.1) — `indices_entete_fits` vit dans
#          `processing/astrometrie`, pas dans `images` : l'import local du
#          bouton levait ImportError au premier clic (attrapé par le banc,
#          section [7] nouvelle). L'origine des indices est désormais
#          CONSERVÉE : le libellé annonce « indices posés (image <fichier>) »
#          ou « (saisie) » — la provenance ne se perd plus derrière un
#          « saisie » générique.
# v2.28.1 : ERGONOMIE astrométrie — bouton 📷 « Lire depuis l'image
#          courante » dans l'UI (case Astrométrie) : pré-remplit les trois
#          champs AD/Dec/champ depuis le header FITS de la dernière brute
#          reçue (`camera.last_file`) ou du dernier empilement linéaire
#          sauvegardé (`saved_path`) — lecture STRICTE (OBJCTRA/OBJCTDEC +
#          FOCALLEN/XPIXSZ), jamais d'invention ; si header incomplet,
#          le libellé annonce la raison. L'utilisateur n'a plus qu'à valider
#          (Entrée / FocusOut) pour transmettre au worker.
# v2.28.0 : BRANCHEMENT DU SOLVEUR AU WORKER — astrométrie de l'empilement
#          (jalon 56, décision d'Alain du 22/09/2026) : le solveur interne
#          résout l'astrométrie UNE SEULE FOIS sur l'accumulation COMPLÈTE
#          (grille de l'aligneur, `mean(recadre=False)`), avec les INDICES
#          de la cible (saisis OU lus dans l'en-tête OBJCTRA/OBJCTDEC des
#          brutes). À chaque RÉEMPILEMENT, le WCS est PROPAGÉ par composition
#          de transformations (module `catalogues/propagation.py` — étape 3
#          validée au banc), AUCUN re-solve, AUCUN accès au catalogue.
#          ASTAP reste la référence indépendante/repli hors session.
#          Module de GLUE `processing/astrometrie.py` (numpy pur, sans cycle
#          d'import) : `SuiviAstrometrie` gère le cycle de vie (indices →
#          résolution unique → propagation cumulative), réessais espacés et
#          bornés, invalidation si indices changent, mots-clés FITS WCS
#          (CTYPE/CRVAL/CRPIX/CD) écrits à CHAQUE sauvegarde linéaire sur la
#          grille RÉELLEMENT écrite (recadrage d'intersection inclus).
#          UI : case « Astrométrie » + AD/Dec/champ (sexagésimal/heures/
#          décimal, interprétation explicite affichée), lecture d'en-tête
#          STRICTE (OBJCTRA/OBJCTDEC + FOCALLEN/XPIXSZ, jamais d'invention),
#          ligne d'état dédiée (mesure ou raison d'attente, jamais muette).
#          Banc : _test_astro_branchement_jalon56.py (6 sections : parseurs,
#          en-tête FITS, SuiviAstrometrie, propagation/recadrage/astropy.wcs,
#          worker réel FITS WCS + ligne d'état, re-stack réel propagation).
# v2.27.1 : EMPILEMENT LINÉAIRE BORNÉ À [0,1] AVANT ÉCRITURE (retour réel
#          d'Alain, 22/09/2026 — PRIORITÉ : « l'empilement linéaire en sortie,
#          mode dossiers (compo RGB), est saturé et non solvable par ASTAP ») :
#          - CONSTAT MESURÉ sur son fichier (3×2165×3839, float32, 3 canaux
#            sur NAXIS3 — les axes étaient donc BONS depuis v2.26.1) :
#            fond à 0,02 mais max 14,1, 0,3 % des pixels > 1, 25 000 px/canal.
#            L'en-tête ne portait AUCUN mot-clé d'échelle ;
#          - DEUX EFFETS, une seule cause. ASTAP ne résolvait pas : sortie
#            « Only 0 stars found in image » (sa conversion 16 bits écrase des
#            valeurs d'un fond à 0,04) → `ERROR=Not enough stars` dans le .ini
#            d'Alain — il ne voyait AUCUNE étoile de l'image, alors que le
#            MÊME contenu borné à 1 se résout en 0,2 s (143 quads sur 144,
#            échelle 2,4627″/px, identique à sa brute G du même setup). Et
#            tout lecteur qui suppose [0,1] clippe le cœur de M31 + les cœurs
#            d'étoiles en blanc : l'image « paraît saturée » (aperçus PNG
#            comparés : clip-à-1 vs percentiles) ;
#          - CAUSE RACINE : `composition.normaliser` cale chaque rôle sur ses
#            percentiles 0,25/99,7 SANS clip (voulu pour l'affichage : le
#            cœur garde sa tête linéaire). Sur M31 le cœur vaut ~14× le
#            p99,7 → composite à 14. C'est la SEULE donnée de l'appli qui
#            sort de [0,1] — or TOUT le reste suppose cette plage (VeraLux
#            clippe en entrée et piège « max > 1,1 → /65535 », le débruitage
#            clippe, les sorties TIFF/PNG clippent, ASTAP l' suppose) ;
#          - CORRECTIF (portée voulue : les FICHIERS, pas la vue) :
#            `images.borner_lineaire(arr, entete)` retire UN SEUL facteur
#            GLOBAL (jamais par canal : équilibre des couleurs et linéarité
#            préservés au bit près), le consigne dans l'en-tête (AVASCALE,
#            donc réversible, + HISTORY), neutralise/compte les valeurs non
#            finies (AVANAN). Appliqué aux trois écritures linéaires : bouton
#            « Enregistrer l'empilement (linéaire) », « Enregistrer le
#            résultat traité (linéaire) », sauvegarde des canaux (canal_*.fit)
#            — no-op dès que max ≤ 1 (mono, traitements externes) ;
#          - POURQUOI PAS au niveau du composite : le moteur VeraLux travaille
#            en valeurs ABSOLUES (target_bg, logD résolu) et clippe l'entrée à
#            1 → changer l'échelle du composite changerait la vue live (et le
#            rendu « tel que vu ») sans nécessité. La vue ne change donc pas :
#            ce sont les FICHIERS qui redeviennent lisibles ;
#          - NOTE v2.26.1 CORRIGÉE : elle affirmait « les valeurs > 1 d'un
#            composite linéaire sont NORMALES et les lecteurs externes étirent
#            sans problème ». FAUX pour ASTAP (0 étoile détectée → jamais
#            résolu) et pour tout lecteur qui suppose [0,1] (cœur clippé
#            blanc). Seule la phrase « ce n'était pas la cause de l'image
#            noire » restait juste (c'était bien NAXIS1 = 3) ;
#          - bancs : `_test_save_lineaire_echelle.py` (composite > 1 → fichier
#            borné, AVASCALE exact, FILTER conservé, forme (C,H,W), mono
#            intact au bit près, ASTAP RÉEL sur l'empilement M31 du disque si
#            présent) ; `_test_save_rgb_axes.py`, sauvegarde
#            linéaire (v2.5.1) et worker compo (jalon 19) repassés au vert.
# v2.27.0 : SOLVEUR INTERNE — REPLI RANSAC DE PAIRES + VALIDATION RÉELLE
#          (retour réel d'Alain, 22/09/2026 : sur SES images M31 — empilement
#          composite 2,6° @ 243 mm ET brute unique N.I.N.A. 3856×2180 — le
#          solve INTERNE échouait « pas assez de correspondances mutuelles (4) »,
#          les triangles se verrouillant sur une affinité dégénérée) :
#          - CAUSE : sur un champ large/riche, le top-12 d'image ≡ top-20 de
#            catalogue PAR INVARIANTS ne tient plus (les deux listes ne
#            coïncident plus : saturation, limmag, bruit de détection) →
#            l'affinité exacte 3 points est dégénérée et ne passe jamais les
#            garde-fous ;
#          - AJOUT : `_ransac_paires` (esprit astrometry.net) — vote
#            (échelle, angle) sur TOUTES les paires des top-60 image × top-120
#            catalogue (4 parités : direct/miroir × 2 sens), pic de vote →
#            similitude EXACTE issue de 2 correspondances évaluée par
#            appariements mutuels, puis stabilisation Umeyama (échelle +
#            rotation) à rayon croissant (3/5/8 px) ;
#          - PIÈGE n°1 (corrigé, attrapé par le banc réel) : le vote doit
#            comparer des PIXELS à des PIXELS — le catalogue est d'abord passé
#            dans la GRILLE INDICÉE ; voter longueurs d'image (px) contre
#            longueurs de catalogue (deg) donnait li/lc ≈ 1400 et AUCUN bin
#            atteignable (0 paire votante) ;
#          - PIÈGE n°2 : après échec des correspondances mutuelles, remettre
#            `best_M` à None — sinon le chemin « triangles » paraît valide et
#            `_finaliser(None, None, …)` fabrique un axe parasite
#            (pos[None] → (1, N, 2)) au lieu de basculer sur le repli ;
#          - ARCHITECTURE : les deux chemins (triangles, RANSAC) passent par
#            le MÊME `_finaliser` (Gauss-Newton + réjection 3σ + garde-fous
#            d'échelle/rms/nombre) et le repli prend le relais quand l'un est
#            REJETÉ — un chemin qui « réussit » n'est pas un chemin juste
#            (sur la brute G, l'affinité des triangles passait les mutuelles
#            puis divergeait : échelle résolue 369 841″/px) ;
#          - `info["methode"]` = « triangles » | « paires-ransac » : la méthode
#            effectivement retenue est désormais traçable (diagnostic réel) ;
#          - banc RÉEL ajouté `_test_solveur_reel_m31.py` (TOUT AU VERT) :
#            empilement composite 2,6° → 86 étoiles, rms 0,59 px, 2,4650″/px,
#            centre à 20″ des indices ; brute G → 70 étoiles, rms 0,44 px,
#            2,4652″/px — les DEUX images sortent de la même optique, donc
#            échelles concordantes au millième = contrôle croisé indépendant ;
#          - VALIDATION CROISÉE ASTAP sur la brute G : écart max 2,78″ sur
#            bords + centre, Δ échelle 0,0013″/px, Δ orientation locale au
#            centre 0,004° ;
#          - PIÈGE n°3 (mesuré, pas une régression) : l'angle du CD brut n'est
#            PAS comparable entre deux WCS de point tangent DIFFÉRENT (notre
#            solveur garde CRVAL = centre indicé, ASTAP le pose sur son pixel
#            de référence : 0,6° d'écart de CRVAL → 0,57° d'écart d'angle
#            apparent, alors que les positions concordent à 2,8″) — comparer
#            l'orientation LOCALE au même point du ciel (différence finie) ;
#          - bancs jalon 56 étapes 2 et 3 relancés : TOUJOURS AU VERT (le
#            chemin triangles reste le chemin principal ; le repli n'est
#            qu'un filet).
# v2.26.1 : CORRECTIF AXES FITS COULEUR (retour réel d'Alain, 22/09/2026 :
#          « Enregistrer l'empilement (linéaire) » produit un fichier où
#          ASIFitsView ne montre AUCUNE étoile) :
#          - CAUSE : save_image écrivait le RGB en numpy (H, W, C) → FITS
#            NAXIS1 = 3 : tout lecteur externe (ASIFitsView, Siril…)
#            interprète NAXIS1 comme la LARGEUR → N images de 3 px de large
#            (« 4/4 », tranches noires). Le projet contournait déjà le piège
#            pour GraXpert (jalon 14) mais PAS dans la sauvegarde standard ;
#          - FIX : save_image écrit les canaux sur NAXIS3 ((C, H, W) côté
#            astropy — LA convention astro) ; load_image normalise en
#            (H, W, C) UNE fois pour toutes (convention interne de l'appli) ;
#            mono 2D inchangé ;
#          - _test_save_rgb_axes.py (NAXIS vérifiés, aller-retour, lecture
#            d'un FITS « Siril », canal R identifié, mono, PNG) TOUT AU VERT ;
#            banc jalon 14 adapté (l'outil externe est lu avec astropy brut,
#            comme le vrai GraXpert) et repassé au vert ; sauvegarde
#            linéaire (fix v2.5.1) et worker compo (jalon 19) repassés ;
#          - NOTE (v2.26.1) : les valeurs > 1 d'un composite linéaire (jusqu'à
#            ~14 sur M31) venaient de la normalisation par percentile du
#            composite (Linear Fit/gains). Cette note concluait à tort que
#            « les lecteurs externes étirent sans problème » → CORRIGÉ en
#            v2.27.1 : ASTAP n'y détectait AUCUNE étoile (non résolvable) et
#            tout lecteur supposant [0,1] clippait le cœur en blanc. Les
#            fichiers sont désormais bornés à [0,1] à l'écriture. Ce n'était
#            bien PAS la cause de l'image noire (c'était NAXIS1 = 3) ;
#          - installateur rebuilit.
# v2.26.0 : PROPAGATION DU WCS PAR COMPOSITION — JALON 56, ÉTAPE 3 (décision
#          d'Alain : PAS de re-solve à chaque réempilement — solve UNE fois
#          sur la référence, puis propagation le long des transformations) :
#          - avastack/catalogues/propagation.py (numpy pur, sans dépendance
#            vers processing — le cycle d'import resterait interdit) :
#            `propager(wcs_ref, M)` → WcsCompose, le WCS EXACT du repère
#            transformé, M en convention ALIGNEUR (frame → référence,
#            warpAffine) ; `WcsCompose.vers_radec/vers_pixels` = composition
#            exacte (aucun ajustement) ; `compose_M` / `inverse_M` pour les
#            chaînes (réempilement : W1 = propager(W0, M10), un SEUL
#            alignement entre anciennes et nouvelles grilles) ;
#            `WcsCompose.vers_tan()` ré-ajuste un WcsTan équivalent pour
#            l'interopérabilité FITS (initialisation analytique cd₀ =
#            cd_ref·A, crpix₀ = A⁻¹(crpix_ref − t)) ;
#          - DÉCOUVERTE du banc : l'aligneur n'estime que des SIMILITUDES
#            (estimateAffinePartial2D) et la composition d'un TAN avec une
#            similitude est EXACTEMENT un autre TAN (rotation 3D du point
#            tangent) — le ré-ajustement retombe au bruit machine (2,6e-11 px)
#            et la propagation est SANS PERTE (2,3e-13 px vs vérité) ;
#          - SENS DES MATRICES (piège tranché au banc) : M d'aligneur =
#            frame→référence ; `vers_radec` lit le ciel à M(p) (le pixel p
#            montre le contenu arrivé de M(p)), `vers_pixels` pose le ciel en
#            M⁻¹(p_ref) — confondu une fois (46 px), tranché par la vérité
#            analytique puis verrouillé par StarAligner RÉEL (0,42 px) ;
#          - banc _test_propagation_jalon56.py TOUT AU VERT : compose_M/
#            inverse_M exactes (2e-13 px), identité/aller-retours (8e-11 px),
#            vérité analytique + centroïdes détectés (médian 0,14 px, max
#            0,60 px = rééchantillonnage bilinéaire), vers_tan ≡ astropy.wcs
#            (2,6e-14°), re-SOLVE indépendant ≈ propagé à 0,46″, chaîne de
#            réempilement exacte, échecs propres (NaN, forme, dégénérée,
#            échelle aberrante, WCS absent, vers_tan sans forme) ;
#          - rien d'UI ni de branché au worker : la propagation est prête,
#            la PHOTOMÉTRIE par bande (étape 4) suit ;
#          - bancs étapes 1 et 2 relancés : toujours au vert.
# v2.25.0 : SOLVEUR ASTROMÉTRIQUE INTERNE — JALON 56, ÉTAPE 2 (accord
#          d'Alain : résolution interne avec indices, ASTAP en référence
#          indépendante + repli) :
#          - avastack/catalogues/solveur.py : WcsTan (WCS TAN minimal :
#            CRVAL/CRPIX/matrice CD, conversions pixels↔ciel, mots-clés
#            FITS aller-retour — PIÈGE CRPIX 1-based en FITS vs 0-based en
#            tableau, tranché contre astropy.wcs) ; projection TAN
#            gnomonique numpy pur ; détection d'étoiles (recopie adaptée
#            de processing/stars pour éviter le cycle d'import
#            processing↔catalogues) ; appariement GLOBAL par triangles
#            canoniques (jalon 15, top-12 image vs top-20 catalogue APRÈS
#            clip du rectangle indicatif — sans ce clip, le top-N du cône
#            d'extraction n'est pas celui de l'image et les triangles
#            corrects n'existent plus) ; affinité exacte 3 points (PIÈGE :
#            l'affinité np.linalg.solve(A, dst) est (3, 2), partie
#            linéaire = M[:2,:].T — la transposée manquante inversait la
#            rotation de départ) ; ajustement TAN Gauss-Newton (8
#            paramètres) + réjection 3σ itérative + garde-fous (échelle
#            cohérente avec l'indice, rms ≤ 2 px, 6 appariements min) ;
#          - banc _test_solveur_jalon56.py TOUT AU VERT : projection TAN
#            ≡ astropy.wcs (écart 5e-14° sur 3 parités/orientations),
#            solve interne 0,07–0,10″ de la vérité sur images synthétiques
#            construites depuis le VRAI catalogue Gaia de Siril (indices
#            exacts, bruités ~6′, parité inversée ; échecs propres si
#            indices faux ou image sans étoiles), validation croisée
#            astap_cli ≈ interne à 0,2″ ;
#          - avastack/catalogues/astap.py : wrapper astap_cli —
#            conventions VÉRIFIÉES EN RÉEL le 22/09/2026 (CLI-2024.11.17) :
#            -ra en HEURES, -spd = 90 + dec (distance au pôle SUD ; l'écho
#            « Start position » a tranché : 90 − dec cherche à −dec),
#            -fov = hauteur du champ en degrés ; succès = exit 0 + .wcs
#            (matrice CD) + PLTSOLVD=T ; AVASTACK_ASTAP (variable
#            d'environnement) surcharge le chemin, sinon install Windows
#            par défaut puis PATH ;
#          - suite (étapes 3–6) : propagation WCS au réempilement, puis
#            photométrie et facteurs par bande posés sur les gains.
# v2.24.0 : ÉTALONNAGE PHOTOMÉTRIQUE (SPCC LOCAL) — JALON 56, ÉTAPE 1 :
#          FONDATIONS CATALOGUES (accord d'Alain, plan du 22/09/2026) :
#          - sous-package `avastack/catalogues` : HEALPix NESTED en numpy
#            PUR (healpix.py : entrelacement, pix2ang, ang2pix, pixels
#            d'un cône, chunks niveau 1) — validé contre astropy-healpix
#            (22 valeurs de référence en dur dans le banc, écart max
#            5e-11°, roundtrip exact sur 2000 directions) ;
#          - lecture du format « Siril HEALpixel Catalog » v1.0.0 (spec
#            Zenodo 14697486, CC-BY) : catalogue Gaia DR3 astrométrique
#            (monolithique, 16 o/étoile) ET spectrophotométrique xp_sampled
#            (48 chunks, 701 o/étoile, spectres 336–1020 nm en float16 +
#            exposant partagé) — en-têtes vérifiés (chunked, plages de
#            pixels = chunk<<14), lecture par seeks via index cumulatif ;
#            PIÈGE TRANCHE PAR LE SOURCE DE SIRIL (healpix.cpp) : l'index
#            d'un chunk de niveau L fait 4^(8-L) entrées (16 384 pour
#            L=1), PAS 12·4^(8-L) — toutes les extractions en dépendent ;
#          - téléchargeur Zenodo intégré (à froid, hors session) : reprise
#            Range/206 (repart de zéro si le serveur ignore Range),
#            sha256 vérifié contre le .sha256sum officiel, écriture .part
#            → rename atomique, en-têtes navigateur (Zenodo 403 les
#            clients nus) ; catalogue astro (record 14692304, 1,1 Go) et
#            chunks xpsamp (record 14738271) ;
#          - détection automatique : dossier des catalogues Siril si
#            présent (chunks d'Alain déjà là, y compris sous-dossier
#            `siril_cat1_healpix8_xpsamp/`), sinon config AVAStack ;
#          - banc _test_catalogues_jalon56 TOUT AU VERT : 48/48 chunks
#            lisibles, 201 étoiles M31 (flux finis positifs, G 8,9–15,0),
#            686 étoiles astro, cohérence croisée xpsamp ⊂ astro 201/201
#            à < 0,02°, téléchargeur (reprise Range, serveur sans Range),
#            sommaire Zenodo skippé proprement si réseau coupé ;
#          - suite (étapes 2–6) : solveur astrométrique interne, puis
#            facteurs par bande posés sur les gains du stacker.
# v2.23.3 : GAINS COMPO SUIVIS EN TEMPS RÉEL — MÊME SANS NOUVELLE BRUTE
#          (jalon 55, constat Alain du 21/09/2026 : « bouger un gain de
#          composition ne change rien, même en forçant VeraLux ») :
#          - BUG jalon 19 (oubli) : les gains R/G/B et la radio « Canal L »
#            n'étaient posés sur le stacker qu'à la CRÉATION de la session —
#            les saisies suivantes n'atteignaient que l'instantané
#            _compo_gains (vue « traitée » du solveur) et JAMAIS
#            stacker.gains → vue « empilement » et sauvegardes figées sur
#            les gains du démarrage, toute la session ;
#          - mode dossier SANS brute à lire : le worker faisait `continue`
#            AVANT tout le reste — rendu jamais recalculé ni repoussé tant
#            qu'aucune frame n'arrive ; désormais les réglages sont
#            resynchronisés à CHAQUE tour de boucle, et un changement de
#            réglage déclenche un recalcul + push du rendu (réutilise le
#            dernier dict d'état — les compteurs n'ont pas bougé) ;
#          - la résolution VeraLux est forcée quand gains/canal L/Linear
#            Fit changent (notify_new_stack) : ces réglages ne font pas
#            partie de sa clé, le solveur ne se serait jamais rendu compte
#            seul (c'est ce qui biaisait l'A/B Linear Fit d'Alain sans
#            nouvelle brute) ;
#          - Tests : bancs jalon 19 (UI + worker), 20 (re-stack), 54 au
#            vert.
# v2.23.2 : LINEAR FIT — RÉFÉRENCE D'ALIGNEMENT À NOUVEAU BRUTE (jalon 54d,
#          reprise à froid de la régression, 21/09/2026) :
#          - CONSTAT : le diagnostic optique d'Alain (_diag_canaux_compo,
#            M31 RGB) montre des couches PARFAITEMENT enregistrées
#            (Δ < 0,5 px, MAD 0,2 px) — le « comme décalé » ne peut pas être
#            géométrique (le fit est photométrique pur) ;
#          - BUG CORRIGÉ : en mode compo, mean_avec_canaux appliquait le fit
#            MÊME à recadre=False → la RÉFÉRENCE D'ALIGNEMENT n'était plus
#            brute (violation du contrat jalon 13, documenté dans les deux
#            docstrings). Correctif : le fit ne s'applique qu'au chemin
#            recadré (visu + sauvegardes) — exactement comme LiveStacker ;
#          - DÉCOUVERTE DE CONFIG : le config.json d'Alain portait
#            `linear_fit: true` (persisté des essais v2.23.0) — toutes les
#            sessions de test depuis ont tourné AVEC le fit actif ; remis à
#            false (l'A/B propre « case décochée » devient possible) ;
#          - PISTE RENDU restante (si case cochée encore « dégradée ») : le
#            plancher np.clip(0) sur un offset NÉGATIF (fond B > fond G)
#            écrase le plancher de bruit du canal — fond sale à l'étirement
#            fort ; à décider après l'A/B (replis possibles : ne pas clipper
#            / bornes de l'offset) ;
#          - Tests : banc jalon 54 à 39 vérifications (+ garde-fou permanent
#            « mean(recadre=False) compo = BRUTE »).
# v2.23.1 : LINEAR FIT — OFFSET SEUL PAR DÉFAUT (jalon 54b, retour du test
#          réel d'Alain, 21/09/2026) :
#          - CONSTAT : avec « gain + offset », le gain fondé sur le rapport
#            des bruits (σ vert / σ canal) amplifie le bleu d'une image OSC
#            déjà équilibrée par la case WB (mesuré : B ×1.52) → halos et
#            bruit bleus enflés à l'étirement → image « floue, comme
#            décalée » ;
#          - DÉCISION D'ALAIN : OFFSET SEUL par défaut (les médianes des
#            fonds sont alignées, le rapport signal/bruit n'est pas
#            touché — l'offset seul est ce qui élimine le masque bleu) ;
#            le gain reste disponible via un menu « Méthode » (« Offset
#            seul (fond) » / « Gain + offset ») pour les palettes
#            narrowband (équivalent du Linear Fit d'APP) ;
#          - UI : menu « Méthode » sous la case ; config `linear_fit_mode`
#            persistée (chaîne explicite) ; instantané `_fit_mode` pour le
#            worker (jamais de lecture Tk hors thread principal) ;
#            mode inconnu → repli « offset » (le plus doux) ;
#          - Tests : banc jalon 54 étendu (38 vérifications : défaut
#            offset, gain plafonné seulement en mode gain_offset,
#            référence indépendante recalculée, menu UI, config round-
#            trip) + régressions au vert.
# v2.23.0 : RECALAGE COLORIMÉTRIQUE « LINEAR FIT » (jalon 54) :
#          - DEMANDE D'ALAIN : neutraliser le MASQUE coloré qui surgit à
#            l'étirement (fond bleu dans les poussières de M31) — cause :
#            fonds de filtres différents dans le linéaire, que l'étirement
#            (STF à points noir/blanc communs, VeraLux qui préserve les
#            ratios) transforme en décalage de couleur ;
#          - mécanique (équivalent live du Linear Fit d'APP, version
#            robuste) : R et B recalés sur le VERT (référence) par une
#            droite Gain + Offset mesurée sur les stats ROBUSTES du
#            composite linéaire (médiane + MAD, quart central sous-
#            échantillonné) ; gain = σG/σX borné [0.25, 4.0], offset =
#            medG − gain·medX, plancher 0 ; mode « offset » seul possible
#            en code (FIT_MODES) — gain_offset PAR DÉFAUT (décision
#            d'Alain) ; canaux PLATS (rôle absent) → no-op explicite
#            (diag None) ;
#          - appliqué DANS mean() (décision d'Alain : visu ET sauvegardes)
#            — LiveStacker (mono couleur, après WB et recadrage ; la
#            référence d'alignement mean(recadre=False) reste BRUTE) et
#            CompositeStacker (composite SEUL, couches brutes) ; cache par
#            (n, mode, gains, mode L) → un seul calcul par frame empilée,
#            aucun pompage ;
#          - solveur live : le tuple vl_compo gagne un 5e élément (actif,
#            mode) — déballage tolérant — ré-appliqué au composite
#            RE-FAIT après la recomposition des couches traitées : la vue
#            « traitée » reste calée comme la vue « empilement » ;
#          - UI : case « Recalage colorimétrique (Linear Fit) » (décochée
#            par défaut) + libellé des gains/offsets MESURÉS (« Fit R ×…
#            · B ×… ») ; config `linear_fit` persistée (booléen explicite)
#            ; réglages conservés aux re-stacks mono et compo ;
#          - Tests : _test_fit_canaux_jalon54 (aligner_canaux confronté à
#            une référence numpy indépendante : médianes alignées, entrée
#            intacte, bornes, offset seul, plancher 0, dégénérés ;
#            LiveStacker et CompositeStacker : cache, recadre=False brut,
#            HOO dégénéré, couches brutes ; solveur : recomposition re-
#            calée ; UI réelle : case, libellé, config, re-stack) +
#            régressions au vert.
# v2.22.0 : DARK/FLAT UNIQUE OU PAR COUCHE EN MODE COMPOSITION (jalon 53) :
#          - DEMANDE D'ALAIN : en empilement multibande (composition
#            multi-dossiers), chaque dark et chaque flat peut viser UN RÔLE
#            (filtre) — DEUX CHOIX INDÉPENDANTS : un dark par filtre avec
#            un flat unique, l'inverse, ou les deux par filtre ;
#          - RETOUR D'ALAIN PENDANT LE TEST : la couche se choisit AU CLIC
#            sur « Charger un dark… » / « Charger un flat… » — boîte
#            modale « Ce dark s'applique à : Unique (toutes les couches) /
#            la couche « Ha »… » (rôles ACTIFS du cadre Composition) ;
#            PLUS de menus déroulants de ciblage préalable ; hors
#            composition, aucun dialogue (cible unique directe) ;
#          - RETOUR D'ALAIN : les libellés montrent TOUT ce qui est
#            chargé — « Dark unique : nom (H×W) » PUIS « Dark Ha : nom
#            (H×W) » pour chaque couche active (« Dark O3 : — » si le
#            master de cette couche manque) ; le Calibrator mémorise le
#            fichier d'origine de chaque master (*_sources) ;
#          - mécanique : Calibrator.darks/flats = {rôle: image} +
#            load_dark/load_flat(path, role=None) + apply(img, role=…) —
#            le master DU RÔLE prime, repli sur l'UNIQUE pour un rôle sans
#            master dédié (mono inchangé) ; le worker passe le rôle de la
#            frame ; « Effacer calibration » vide tout ; annulation de la
#            boîte = aucun chargement ; masters conservés aux allers-
#            retours de source et réaffichés au retour en composition ;
#          - Tests : _test_calib_compo_jalon53 (Calibrator : repli par
#            rôle, indépendance dark/flat, flat non constant à gradient ;
#            UI réelle : boîte modale pilotée par after — réponse Ha,
#            unique, O3, annulation ; libellés complets ; worker réel : le
#            dark DÉDIÉ de chaque couche appliqué, fonds mesurés 0.13/0.09,
#            jamais le dark du voisin) + régressions au vert.

# v2.21.10 : NOIR MESURÉ + OFFSET LU + TEC TOUPTEK PILOTABLE (jalon 51) :
#          - CONSTAT RÉEL (Alain, banc 21/09/2026, G3M662M) : la caméra
#            annonce 16 bits et la table de toupcam.h laissait croire à un
#            noir 0 → 7936, mais elle REFUSE 7936 (E_INVALIDARG), ACCEPTE
#            31/30/0 et REFUSE 32 → plage réelle 0 → 31. Ni constante ni
#            fonction du SDK n'est fiable : la borne est MESURÉE
#            (TouptekCamera._mesurer_noir — dichotomie « posé puis RELU »,
#            plafonnée par la table documentée, valeur d'origine restaurée) ;
#          - OFFSET LU PLUTÔT QU'IMPOSÉ (demande d'Alain, « règle valable
#            pour TOUTES les caméras ») : la sonde lit la valeur courante du
#            contrôle (Capacites.valeur_actuelle) et l'appli l'ADOPTe —
#            Touptek (get_Option 0x15), QHY (GetQHYCCDParam), ZWO
#            (ASIGetControlValue), SVBONY (SVBGetControlValue), Player One
#            (POAGetConfig) ; aucune marque muette n'est forcée ;
#          - TEC TOUPTEK PILOTABLE (demande d'Alain, même sans matériel de
#            test) : la DLL n'a PAS de CoolerOn — pilotage par OPTIONS
#            (TECTARGET 0x0f consigne en 0,1 °C, TEC 0x08 marche/arrêt,
#            plage lue via TECTARGET_RANGE 0x6d), température via
#            get_Temperature ; les boutons ❄/étiquette TEC de l'appli
#            fonctionnent dès que la caméra expose l'option (sinon E_NOTIMPL
#            → boutons grisés, aucune promesse en l'air) ;
#          - banc : dichotomie exécutée via la fonction de l'APPLICATION
#            (une seule source de vérité) + lecture TEC/consigne/température.
#          - Tests : _test_camera_touptek (58/58 — plage mesurée par la
#            caméra factice qui refuse > 31), _test_capacites_ui_jalon32
#            (offset ADOPTÉ dans la fenêtre), _test_capacites (29/29),
#            QHY 33, Player One 29/29, TEC jalons 33/38, UI jalons 31/34/35 :
#            toutes les régressions au vert.

# v2.22.0 : DARK/FLAT UNIQUE OU PAR COUCHE EN MODE COMPOSITION (jalon 53) —
#          demandé par Alain : chaque dark et chaque flat peut viser UN
#          RÔLE (filtre) via « Dark pour : » / « Flat pour : » (cadre
#          Calibration) — DEUX CHOIX INDÉPENDANTS (un dark par filtre avec
#          un flat unique, l'inverse, ou les deux par filtre) ; un rôle
#          sans master dédié RETOMBE sur le dark/flat unique (mono
#          inchangé) ; menus grisés hors composition, cibles ramenées à
#          « Unique » ; Calibrator : darks/flats = {rôle: image} +
#          apply(img, role=…) ; worker passe le rôle de la frame.
#          Tests : _test_calib_compo_jalon53 + régressions au vert.

# v2.21.10 : NOIR TOUPTEK MESURÉ + OFFSET LU (toutes marques) + TEC TOUPTEK
#            PILOTABLE (jalon 51) + ERGONOMIE DU CADRE « CAMÉRA » (jalon 52) :
#          - JALON 51 — CONSTAT RÉEL DU BANC (Alain, 21/09/2026, G3M662M) :
#            la caméra REFUSE 7936 (E_INVALIDARG) mais ACCEPTE 31/30/0 et
#            REFUSE 32 → plage de noir RÉELLE 0 → 31 : la table de toupcam.h
#            n'est qu'un PLAFOND de recherche — la borne max est désormais
#            MESURÉE par DICHOTOMIE posé/relu (TouptekCamera._mesurer_noir,
#            valeur d'origine restaurée) ; le banc exécute CETTE fonction de
#            l'appli (une seule source de vérité) ;
#          - OFFSET LU PLUTÔT QU'IMPOSÉ (demande d'Alain, valable pour
#            TOUTES les caméras) : la sonde lit la valeur COURANTE du
#            contrôle (cap.actuels) et l'appli l'ADOPTe au lieu d'écraser
#            avec son défaut — Touptek (option 0x15), QHY (GetQHYCCDParam),
#            ZWO (ASIGetControlValue), SVBONY (SVBGetControlValue),
#            Player One (POAGetConfig) ; marque muette → comportement
#            d'origine (valeur seulement ramenée dans la plage détectée) ;
#          - TEC TOUPTEK PILOTABLE (demande d'Alain, sans matériel de test
#            possible) : la DLL n'a PAS de CoolerOn → pilotage par OPTIONS :
#            TECTARGET 0x0f (consigne en 0,1 °C), TEC 0x08 (marche/arrêt),
#            plage lue via TECTARGET_RANGE 0x6d (champs SIGNÉS), température
#            get_Temperature ; consigne_refroidissement /
#            lire_refroidissement / arreter_refroidissement implémentés et
#            branchés sur les boutons ❄ de l'appli (un modèle sans TEC
#            répond E_NOTIMPL → boutons grisés ; chez Touptek PAS de
#            puissance PWM → étiquette « TEC : — », jamais un faux 0 %) ;
#          - MISE À JOUR IMMÉDIATE vérifiée (déjà en place) : chaque
#            mouvement de curseur est poussé au thread de travail
#            instantanément (_push_settings → pending_settings /
#            pending_offset consommés à chaque tick) pour TOUTES les marques
#            — sans redémarrer la session ;
#          - JALON 52 (demandes d'Alain, 21/09/2026) : le CHOIX DE SOURCE
#            (caméra/dossier/…) est EN HAUT du cadre « Caméra » DÈS LE
#            LANCEMENT — avant il était sous les contrôles, remontait dès
#            qu'on choisissait « Dossier » (contrôles cachés) et y restait
#            au retour caméra : sa place dépendait de l'histoire de la
#            session. Choix + Démarrer/Arrêter packés AVANT les contrôles →
#            ordre stable au va-et-vient ;
#          - « ⏏ Déconnecter » a SA PROPRE ligne sous « 🔎 Détecter » :
#            sur la même ligne (side="right"), un long libellé de caméra
#            détectée le poussait hors de la colonne (il fallait élargir la
#            colonne de gauche pour l'atteindre) ;
#          - Tests : _test_camera_touptek 58/58 (faux SDK qui refuse > 31),
#            _test_ergonomie_jalon52 (ordre de packing RÉEL + va-et-vient +
#            ligne dédiée), régressions _test_capacites 29/29,
#            _test_qhy_camera 33, _test_camera_playerone 29/29, TEC 33/38,
#            UI 47/32/31/34/35/6 : tous au vert.

# v2.21.9 : CAPACITÉS TOUPTEK (EXPO/GAIN/NOIR) → CURSEURS AUX BORNES RÉELLES
#           (jalon 50) :
#          - CONSTAT FONDATEUR (Alain, 21/09/2026, miniPC/G3M662M) : le banc
#            mesurait 100 µs → 1000 s et 100 % → 15000 % mais l'APPLI gardait
#            ses bornes EN DUR (« Gain (0 – 175) », « Offset (0 – 255) »,
#            échelles d'expo fixes) : TouptekCamera n'implémentait PAS
#            detecter_capacites() (seules QHY/POA/SVB/ZWO le faisaient) ;
#          - avastack/cameras/touptek.py : detecter_capacites() = RELEVÉ
#            DIRECT sur la caméra ouverte — Toupcam_get_ExpTimeRange (µs),
#            Toupcam_get_ExpoAGainRange (%), get_MonoMode, get_MaxBitDepth,
#            get_PixelSize ; le NOIR (option BLACKLEVEL 0x15 — l'« offset »
#            chez Touptek) se déduit de la table DOCUMENTÉE de toupcam.h
#            (TOUPCAM_BLACKLEVELn_MAX = 31 << (n - 8), indexée par la
#            profondeur annoncée par get_MaxBitDepth, les bits étant codés
#            dans le HRESULT) — profondeur hors table ⇒ AUCUNE plage
#            (jamais de curseur construit sur une valeur inventée). Les
#            signatures nouvelles passent par _proto() : une DLL plus
#            ancienne ne casse plus le chargement du SDK ;
#          - GAIN exprimé en POUR CENT (unité SDK, 100 = 1×) : les autres
#            marques passent leurs unités SDK telles quelles (l'ancien ×100
#            supposait un curseur gradué en « × » et aurait faussé le
#            curseur aux bornes réelles) ; l'AUTO-EXPOSITION est COUPÉE par
#            apply_settings (relevé réel : l'AE « continue » écrase l'expo
#            posée — les curseurs auraient menti) ;
#          - definir_offset() implémenté (put_Option BLACKLEVEL, borné à la
#            plage détectée) : le curseur « offset » AGIT enfin chez Touptek
#            (il était silencieusement sans effet, la base étant un no-op) ;
#          - capacites.py : rôle « offset » → option BLACKLEVEL 0x15 pour la
#            marque Touptek ; le TEC n'est PAS annoncé (l'appli ne sait pas
#            encore le piloter pour cette marque : pas de bouton ❄ factice) ;
#          - banc _diag_camera_touptek.py : affiche la plage DOCUMENTÉE du
#            noir ET l'ÉPROUVE sur la caméra (pose 0 puis la borne max,
#            RELIT après chaque pose, restaure la valeur d'origine) → verdict
#            « plage CONSTATÉE 0 → N » ;
#          - Tests : _test_camera_touptek (57/57 — capacités, unités du gain,
#            plage du noir, restauration, AE coupée), _test_capacites_ui_jalon32
#            (sonde Touptek RÉELLE sur fausse DLL → curseurs 100→15000 et
#            0→7936 dans la fenêtre) ; _test_capacites (29/29) et le reste
#            des régressions au vert.

# v2.21.8 : BANC DE DIAGNOSTIC TOUPTEK + CORRECTION DE LA SONDE (jalon 49) :
#          - CONSTAT FONDATEUR (banc _diag_camera_touptek.py, 20/09/2026) :
#            la sonde de la v2.2.0 était FAUSSE contre la DLL réelle
#            (ToupCam.dll 59.30239.20251209) :
#              · Toupcam_get_ExpoTimeRange N'EXISTE PAS → AttributeError au
#                chargement (le vrai nom est Toupcam_get_ExpTimeRange) ;
#              · Toupcam_Enum (legacy, déclarée obsolète dans toupcam.h)
#                remplit des ToupcamDevice {pointeur modèle, displayname,
#                id} et NON un tableau de modèles — la sonde lisait du
#                charabia ;
#              · Toupcam_Open veut l'ID OPAQUE de la caméra énumérée (champ
#                id), pas le nom du modèle ;
#          - avastack/cameras/touptek.py réécrite sur l'API MODERNE
#            Toupcam_EnumV2 / ToupcamDeviceV2 (disposition VALIDÉE
#            empiriquement sur la DLL : 201 modèles lisibles, champs
#            cohérents), conforme à l'entête officiel toupcam.h ;
#          - _diag_camera_touptek.py : banc autonome (détection V2 +
#            drapeaux TOUPCAM_FLAG_*, réglages mesurés, verdict
#            « possibilités », TEC piloté par OPTIONS (TOUPCAM_OPTION_TEC /
#            TECTARGET — la DLL n'a PAS de CoolerOn), expo/gain/noir, ROI,
#            binning matériel, flux événementiel (callback + PullImage),
#            pose (Snap/STILLIMAGE), rapport %TEMP%, mode --console) ;
#          - Test : _test_camera_touptek.py (fausse DLL, 37 vérifications,
#            structures V2, sonde avec callback simulé, banc complet).
#          - Test RÉEL d'Alain (G3M662M mono 16 bits USB3, 20/09/2026) :
#            détection V2 / ouverture / flux / poses expo-gain OK. Trois
#            constats intégrés : (a) deux prototypes ctypes manquants
#            (get_MaxSpeed, get_StillResolutionNumber) → OverflowError
#            « int too long » (handle 64 bits passé en int 32) — déclarés,
#            avec get_StillResolution et get_FinalSize ; (b) l'auto-
#            exposition « continue » ÉCRASE l'expo posée manuellement
#            (l'expo retombait à 350 ms) → bouton 🅰 on/off + avertissement
#            dans la liste ; (c) get_Roi relu suspecte (1080×1080×4 sur une
#            caméra 1920×1080) → croisement get_Size + get_FinalSize
#            journalisé après chaque pose ROI ; compteurs get_FrameRate
#            peu fiables (« 1000 fps ») → le fps MESURÉ fait foi ;
#            (d) second passage réel : Snap FONCTIONNE malgré 0 résolution
#            pose (livre à la résolution courante, 1920×1080) ; auto-expo
#            off/on validée en réel ; affichage « c_ulong(8) » du verdict
#            corrigé en entier simple ; (e) ROI sur G3M662M : put_Roi ACCEPTE
#            toute taille mais le flux ne livre QUE les 2 résolutions du
#            modèle (1920×1080, 960×540) — ROI libre non exploitable sur ce
#            capteur (constat d'Alain, « pas grave »), le banc journalise
#            relu + get_Size/get_FinalSize pour le voir.
# v2.21.7 : PETITES ERGONOMIES (jalon 48, demandes d'Alain) :
#          - le numéro de version s'affiche dans la BARRE DE TITRE
#            (« AVAStack v2.21.7 — live stacking (empilement temps réel) ») ;
#          - le cadre « Traitement externe » est étiqueté « Traitement
#            externe (long) » au lieu de « (instantané) » : GraXpert IA et
#            BXT durent PLUSIEURS MINUTES — l'« instantané » décrit le
#            mécanisme (copie de l'empilement traitée à part, l'accumulé
#            reste linéaire), pas la durée perçue par l'utilisateur.
#          - avastack/ui/app.py : titre en f-string avec AVASTACK_VERSION
#            (source unique : avastack/__init__.py) ; texte du cadre.
#          Test : _test_ui_visibilite_jalon47 étendu (titre = version du
#          package).
# v2.21.6 : COLONNE DE RÉGLAGES ÉPURÉE — cadres visibles selon la source
#          (jalon 47, demande d'ergonomie d'Alain : « la partie droite de
#          l'écran est surchargée inutilement » — en pratique la colonne de
#          réglages à gauche de l'image). Choisir une source n'affiche plus
#          QUE les cadres utiles : source caméra (simulée/OpenCV/SDK) →
#          contrôles caméra seuls (exposition, gain, offset, échelle longue,
#          roue, TEC, détection) ; « Dossier surveillé » → cadre dossier +
#          cadence d'empilement ; « Composition multi-dossiers » → cadre
#          composition + cadence. La combobox de source et Démarrer/Arrêter
#          restent toujours visibles.
#          - avastack/ui/app.py : les contrôles caméra quittent le cadre
#            « Caméra » pour un sous-cadre `frm_ctrl_cam` (masqué en
#            dossier/composition) ; le réglage de rafale (« Empiler les
#            brutes », jalons 42/45) sort des deux cadres où il était
#            DUPLIQUÉ : un seul cadre « Cadence d'empilement »
#            (`frm_rafale`) partagé dossier + composition, caché pour une
#            vraie caméra (sans objet) ; nouvelle méthode
#            `_maj_visibilite_cadres()` — pack_forget, AUCUNE destruction
#            (les valeurs saisies survivent aux allers-retours), replacement
#            via l'ancre stable `frm_calibration` (l'ordre des cadres ne
#            bouge jamais) ; appelée à la construction, à la restauration de
#            config et dans `_on_source_choisie` (AVANT la déconnexion,
#            même si la suite retourne tôt — cas QHY).
#          Tests : nouveau _test_ui_visibilite_jalon47 (visibilité par
#          source, conservation des valeurs, ordre stable, cadence unique
#          toujours reliée au moteur) ; _test_cadence_jalon42 section [7]
#          mise à jour (un seul couple combobox/étiquette) ; régression
#          large au vert : ui jalon 5, compo UI jalon 19, config jalon 6,
#          capacités UI jalon 32, expo jalon 34, pilotage jalon 35,
#          connexion SVBONY jalon 36, TEC jalon 38, couleurs jalon 39,
#          état de calcul jalon 40, moteur jalon 41.
# v2.21.5 : PLAFOND DE RAFALE (jalon 46, retour d'Alain en composition :
#          « rafale en cours » avec un grand nombre de brutes — ses dossiers
#          contiennent déjà les acquisitions d'AUTRES soirées, donc la
#          première rafale devait vider TOUT le backlog d'un coup : sablier
#          en continu pendant des minutes au démarrage). NOUVEAU : chaque
#          rafale empile AU PLUS RAFALE_MAX brutes (10, constante
#          App.RAFALE_MAX) ; à l'épuisement du budget, la fenêtre est
#          (ré)armée MÊME s'il reste des brutes détectées — elles attendent
#          les rafales suivantes (aucune perte, fichiers sur le disque) ;
#          la rafale se termine aussi naturellement quand le backlog est
#          vide (jalon 42). Le sablier ne peut donc plus durer plus que la
#          chaîne × RAFALE_MAX par rafale.
#          - avastack/ui/app.py : `App.RAFALE_MAX` (constante documentée),
#            budget `_rafale_reste` initialisé plein, décrémenté à chaque
#            brute lue (worker), `_armer_cadence()` arme sur budget épuisé
#            OU backlog vide et recharge le budget.
#          Test _test_cadence_jalon42 étendu (armement sur budget épuisé,
#          budget rechargé, App neuve pleine) ; régression : _test_ui_jalon5.
# v2.21.4 : CADENCE COMMUNE AUX DEUX MODES + ÉTIQUETTE AU REPOS AVANT
#          CONNEXION (jalon 45, retour d'Alain : l'étiquette affichait
#          « cadence : sans objet (source non dossier) » AVANT même de
#          démarrer, et la combobox n'existait que dans « Dossier
#          surveillé » alors qu'il teste en COMPOSITION multi-dossiers).
#          - avastack/ui/app.py : nouveau helper `_creer_cadence(parent)` —
#            UNE combobox + UNE étiquette d'état PAR MODE (« Dossier
#            surveillé » ET « Composition multi-filtres »), partageant la
#            MÊME variable `var_cadence` : choisir dans l'un met l'autre à
#            jour, et le worker applique la cadence aux DEUX sources
#            (MultiFolderCamera était déjà couvert par la porte — c'était
#            un problème de PLACEMENT d'UI, pas de moteur). Listes
#            `_cadence_cbs`/`_cadence_lbls` ; `cb_cadence`/`lbl_cadence`
#            restent les widgets de la première combobox (compatibilité
#            tests/config).
#          - `_maj_lbl_cadence()` : « — » quand AUCUNE source n'est
#            connectée (au repos — ne plus afficher « sans objet » avant
#            la connexion) ; « cadence : sans objet (source non dossier) »
#            réservé à une source réellement non dossier (caméra SDK,
#            webcam…) ; compte à rebours/rafale inchangés. Les deux
#            étiquettes sont mises à jour ensemble.
#          Test _test_cadence_jalon42 étendu : 2 comboboxes partageant la
#          variable, 2e dans le cadre « Composition multi-filtres », étiquette
#          « — » sans source ; régression : _test_ui_jalon5.
# v2.21.3 : ÉTAT DE LA CADENCE VISIBLE EN DIRECT (jalon 44, suite du retour
#          d'Alain : « ça travaille toujours toutes les 5 s »). Le correctif
#          jalon 43 (v2.21.2) est en place ; pour DISTINGUER les deux causes
#          possibles d'un rythme inchangé — (a) version testée encore
#          v2.21.1 (qui contenait le bug du court-circuit par le scan
#          interne de read()), (b) cadence réellement sélectionnée « toutes
#          les 5 s » (rafales toutes les 5 s = comportement CORRECT, mais
#          la chaîne composition dure bien plus que 5 s → sablier toujours
#          visible) — le throttling devient OBSERVABLE à l'écran :
#          - avastack/ui/app.py : nouvelle étiquette `lbl_cadence` sous la
#            combobox « Empiler les brutes », tenue à jour par
#            `_maj_lbl_cadence()` (appelée à chaque _tick, mémo anti-spam) :
#            pendant la fenêtre → « prochaine rafale dans Xs · N brute(s) en
#            attente » (ambre, compte à rebours VISIBLE) ; à l'échéance →
#            « rafale en cours · N » (vert) pendant le drain ; « — » = dès
#            réception ; cadence posée sur une source non dossier → «
#            cadence : sans objet (source non dossier) ».
#          Si l'étiquette reste « — » alors que la cadence est sélectionnée,
#          c'est que la version exécutée est antérieure à v2.21.1 ; si elle
#          compte à rebours, le throttling FONCTIONNE et le sablier ne doit
#          être visible qu'une fois par rafale (choisir une cadence
#          NETTEMENT au-dessus de la durée de la chaîne — en composition,
#          la chaîne lourde tourne PAR COUCHE).
#          Test _test_cadence_jalon42 étendu (étiquette : compte à rebours,
#          rafale en cours, dès réception) ; régression : _test_ui_jalon5.
# v2.21.2 : CORRECTIF CADENCE — LA FENÊTRE ARMÉE BLOQUE TOUTE LECTURE
#          (jalon 43, constat réel d'Alain en COMPOSITION multi-dossiers :
#          « les frames s'empilent toujours à la même vitesse »). BUG du
#          jalon 42 : quand AUCUNE brute n'était encore détectée
#          (`pending == 0`), la porte de cadence laissait passer read() —
#          or c'est le SCAN INTERNE des caméras dossier (à l'intérieur de
#          read(), et du round-robin MultiFolderCamera) qui détecte les
#          fichiers : la brute était renvoyée À L'INSTANT où elle devenait
#          complète, court-circuitant la fenêtre. Conséquence : le PREMIER
#          fichier de chaque « rafale » partait toujours immédiatement, et
#          pour des arrivées plus espacées que la fenêtre (composition :
#          un fichier par rôle à la cadence des poses), CHAQUE fichier
#          était « le premier » — la cadence ne ralentissait RIEN.
#          CORRECTION : `_autoriser_lecture()` n'a plus le cas « backlog
#          vide → autorisé » ; la fenêtre armée bloque TOUTE lecture
#          (read() n'est jamais appelé pendant la fenêtre — son scan
#          interne ne peut plus rien renvoyer). Pendant la fenêtre, le
#          worker ne fait que scanner (0,4 s) et attendre : les brutes
#          complétées attendent sur le disque puis sont drainées ENSEMBLE
#          à l'échéance — un recalcul par rafale, comme prévu. Cas « dès
#          réception » et sources non-dossier inchangés.
#          Test _test_cadence_jalon42 mis à jour (fenêtre armée + backlog
#          vide → REFUS, dossier ET composition) ; régression :
#          _test_multifolder_jalon19, _test_ui_jalon5.
# v2.21.1 : CADENCE D'EMPILEMENT EN SURVEILLANCE DE DOSSIER (jalon 42,
#          demande d'Alain) : avec la chaîne lourde live (gradient GraXpert,
#          débruitage) en mode dossier/multi-dossiers, CHAQUE brute relançait
#          la résolution — l'indicateur passait de « composition » à
#          « étirement » sans interruption, sablier en permanence. NOUVEAU :
#          combobox « Empiler les brutes » dans « Dossier surveillé »
#          (dès réception / 5 s / 15 s / 30 s / 1 min / 5 min ; persistée
#          `cadence_lecture`). SÉMANTIQUE : les brutes qui arrivent pendant
#          la fenêtre d'attente RESTENT SUR LE DISQUE (aucune perte —
#          FolderCamera/MultiFolderCamera ne lisent qu'un fichier détecté
#          complet) puis sont DRAINÉES EN RAFALE à l'échéance ; le solveur
#          VeraLux ne relance qu'une fois par rafale (dernier job gagnant)
#          au lieu d'à chaque brute — entre les rafales, l'aperçu est au
#          repos. L'empilement LINÉAIRE accumule TOUTES les brutes, la
#          cadence ne change que le RYTHME, jamais le contenu.
#          - avastack/cameras/folder.py : propriété `pending` (fichiers
#            détectés non lus — même contrat que MultiFolderCamera) +
#            `scanner()` (scan SANS lecture, pour que la décision de cadence
#            porte sur TOUT ce qui est arrivé, pas seulement sur ce qui a
#            déjà été détecté) ; avastack/cameras/multifolder.py :
#            `scanner()` (tous dossiers).
#          - avastack/ui/app.py : worker — scan (≤ 1/0,4 s) + porte
#            `_autoriser_lecture()` AVANT read(), armement `_armer_cadence()`
#            quand TOUTES les brutes détectées sont lues ; miroir thread-sûr
#            `cadence_lecture` (int UI → worker) ; sources NON-dossier
#            (caméras SDK, webcam, simulée) JAMAIS throttlées (leur file ne
#            doit pas s'accumuler en mémoire). Persistance tolérante (valeur
#            inconnue → « dès réception »).
#          Test _test_cadence_jalon42 (porte/armement/miroir/config, dossier
#          + composition) ; régression : _test_multifolder_jalon19,
#          _test_ui_jalon5.
# v2.21.0 : UI INDÉPENDANTE DU MOTEUR — COULEUR LIVE ET ÉTAT DES CALCULS
#          VISIBLES DANS LES DEUX MODES (jalon 41, décision d'Alain :
#          « rendre visible tout ce qui s'applique aussi en STF »).
#          - avastack/ui/app.py : la chaîne couleur (SCNR / SCNR doux /
#            démagenta) SORT du cadre VeraLux → nouveau cadre INDÉPENDANT
#            « Couleur live (SCNR / démagenta) » : les cases sont cochables
#            et EFFICACES en STF/manuel (le moteur STF les applique déjà,
#            testé au jalon 22 — c'était un rangement d'UI, pas une limite).
#            GX live et débruitage live RESTENT dans le cadre VeraLux (ils
#            ne s'appliquent QUE dans son solveur). L'étiquette d'état
#            (lbl_vl) et le curseur de calcul (pb_vl) sortent AUSSI →
#            nouveau cadre « État des calculs (live) » visible dans les
#            DEUX modes.
#          - _maj_lbl_vl étendue : en STF/manuel, elle signale le solveur
#            de netteté DÉDIÉ (jalon 12) — « ⏳ calcul : netteté… » +
#            curseur pendant la déconvolution, retour au repos (« — »)
#            ensuite ; en VeraLux, le solveur dédié (inutilisé) ne
#            déclenche RIEN. display.py : nouvelle méthode sh_en_cours()
#            (accès UI à _sh_pending).
#          - AU PASSAGE, correction d'une imprécision d'explication (pas un
#            bug) : le rendu STF n'est PAS à 20 fois/s — le worker ne pousse
#            l'aperçu qu'à CHAQUE IMAGE REÇUE (les caméras SDK renvoient
#            None entre deux poses) ; le 1/20 s n'est qu'un PLAFOND de
#            traitement pour les sources rapides (démo simulée, webcams,
#            poses courtes) — avec des poses longues, l'aperçu est rendu
#            une fois par pose, exactement à la fréquence des images.
#          Test _test_ui_moteur_jalon41 (cadres visibles dans les deux
#          modes, case SCNR efficace en STF, indicateur netteté STF) ;
#          _test_etat_calcul_jalon40 mis à jour (section STF) ; régression :
#          _test_ui_jalon5, _test_sharp_live_jalon12, _test_couleurs_jalon22,
#          _test_couleurs_immediat_jalon39.
# v2.20.9 : ÉTAT DU CALCUL VERA LUX MATÉRIALISÉ À L'ÉCRAN (jalon 40, demande
#          d'Alain : « matérialiser qu'on applique le traitement et que
#          c'est terminé »). Jusqu'ici, pendant un calcul (souvent plusieurs
#          secondes avec GraXpert/débruitage/netteté), la ligne d'état du
#          panneau VeraLux restait sur son texte précédent : impossible de
#          savoir SI un calcul tournait ni OÙ il en était. NOUVEAU :
#          - avastack/processing/display.py : le thread solveur écrit
#            `vl_stage` (préparation → composition → GraXpert → débruitage
#            → netteté → étirement) à CHAQUE étape, et le REMET à "" à la
#            fin (succès comme erreur) ; `vl_en_cours()` = accès UI à
#            _vl_pending. Écriture worker seule, lecture thread Tk
#            (simple str/bool, aucun verrou côté UI).
#          - avastack/ui/app.py : `_maj_lbl_vl()` (appelée à chaque _tick,
#            un seul écrivain thread UI) — PENDANT un calcul : curseur
#            INDETERMINATE animé (pb_vl, packé seulement pendant le calcul)
#            + « ⏳ calcul : <étape>… » en ambre ; À LA FIN : ligne de
#            RÉSULTAT avec les ✓ des étapes actives — GX ✓ · DN ✓ · NET ✓ ·
#            COUL ✓ (nouveau : la chaîne couleur du jalon 22/23 est
#            désormais signalée) — puis logD et fond mesuré ; erreur =
#            rouge. Mémo `_vl_lbl_txt` : le ⏳ n'est jamais reconfiguré
#            30 fois par seconde ; tous les autres écrivains de lbl_vl
#            (_on_moteur, _on_vl_graxpert) passent par `_lbl_vl_texte()`
#            pour garder le mémo cohérent. Le _refresh_preview sur résultat
#            (ex-bloc vl_new de _tick) est déplacé DANS _maj_lbl_vl :
#            comportement inchangé.
#          Test _test_etat_calcul_jalon40 (séquence des étapes du solveur
#          via outils factices + UI ⏳/curseur/résultat/erreur) ; régression :
#          _test_couleurs_immediat_jalon39, _test_veralux_jalon3,
#          _test_denoise_live_jalon9, _test_sharp_live_jalon12, _test_ui_jalon5.
# v2.20.8 : CASES COULEUR LIVE (SCNR / SCNR doux / démagenta) RÉACTIVES
#          IMMÉDIATEMENT (jalon 39, constat réel d'Alain du 20/09/2026 :
#          cliquer ces cases ne changeait l'affichage qu'à la prochaine
#          frame empilée — ou pas du tout, jusqu'à bouger par ex. le fond
#          cible VeraLux). CAUSE : les callbacks des trois cases couleur
#          mettaient à jour l'état du solveur (disp.vl_scnr etc. — la clé
#          changeait bien) mais OUBLIAIENT d'appeler _refresh_preview(),
#          contrairement à tous les autres contrôles du panneau VeraLux
#          (GraXpert live, débruitage, netteté, curseurs) : la nouvelle
#          chaîne n'était donc soumise au solveur qu'au prochain appel de
#          disp.process(), c.-à-d. à la frame suivante ou à un autre
#          réglage. CORRECTION : même structure que le débruitage/netteté —
#          _on_vl_scnr/_on_vl_scnr_doux/_on_vl_demagenta = sync de l'état +
#          _refresh_preview() (le solveur applique la chaîne couleur PUIS
#          l'étirement : le résultat est visible aussitôt résolu) ; nouvelles
#          méthodes _sync_vl_scnr_vue/_sync_vl_scnr_doux_vue/
#          _sync_vl_demagenta_vue (état SEUL) et _sync_vl_couleur_vue
#          n'appelle PLUS les _on_* mais les _sync_* — sinon le rendu serait
#          déclenché 3× toutes les 30 ms par _tick (qui suit la vue). Test :
#          _test_couleurs_immediat_jalon39 (soumission immédiate à la case,
#          aucun re-soumission en boucle via _sync_vl_couleur_vue) ;
#          régression : _test_couleurs_jalon22, _test_veralux_jalon3,
#          _test_denoise_live_jalon9, _test_sharp_live_jalon12.
# v2.20.7 : BOUTONS ❄ TOUJOURS ACTIFS SUR SVBONY — DÉCISION D'ALAIN
#          (jalon 38, annule la logique du jalon 37). Retour réel d'Alain
#          (20/09/2026) : les boutons ❄ restaient actifs sur sa SV305C
#          sans TEC — et il PRÉFÈRE ainsi : « si on a une caméra refroidie
#          et qu'on a oublié de brancher l'alim, il suffit de la brancher
#          et ça fonctionnera sans avoir besoin de déconnecter et
#          redétecter » (le sondage périodique toutes les 2 s détecte le
#          TEC dès que l'alim arrive). CORRECTION : retour au comportement
#          « contrôles TEC énumérés → cap.tec True + sondage → valeurs » ;
#          la sonde par l'EFFET du jalon 37 (tentative CoolerEnable = 1 à
#          la détection) est RETIRÉE ; le constat réel ET la décision sont
#          documentés DANS LE CODE (detecter_capacites + lire_refroidissement)
#          pour ne pas « re-corriger » plus tard. Le filet de sécurité
#          reste : « Réguler » sans TEC → message clair « vérifier
#          l'alimentation 12 V » (refus SDK CoolerEnable). Test :
#          _test_tec_boutons_jalon38 (remplace _test_tec_sonde_jalon37,
#          supprimé — il testait le comportement annulé) ; régression :
#          _test_capacites, _test_tec_jalon33, _test_pilotage_jalon35.
# v2.20.6 : SONDE TEC SVBONY PAR L'EFFET — CONTRÔLES PRÉSENTS ≠ TEC PRÉSENT
#          (jalon 37, retour réel d'Alain du 20/09/2026 : la connexion auto
#          SV305C du jalon 36 fonctionne, MAIS sa caméra SANS TEC affiche
#          quand même les contrôles TEC (14-17) avec « 20 °C, puissance
#          0 % » — valeurs bidon — et « Réguler » levait « CoolerEnable
#          refusé par le SDK — vérifier l'alimentation 12 V » ; le firmware
#          est probablement commun avec la SV305C Pro refroidie). CAUSE : le
#          SDK énumère les contrôles TEC même sans TEC physique — la
#          présence de contrôles ne prouve rien. CORRECTION (verdict par
#          l'EFFET, règle « réglage relu ≠ réglage appliqué ») :
#          detecter_capacites() TENTE CoolerEnable = 1 — refus → pas de TEC
#          (cap.tec False, pas de plage de consigne, note explicative dans
#          extras, lire_refroidissement() → None → boutons ❄ RESTENT
#          GRISÉS) ; succès → TEC présent ET l'état initial de CoolerEnable
#          est RESTAURÉ (ne pas laisser le TEC démarré rien que pour une
#          détection). La sonde app (_sonder_controles →
#          lire_refroidissement) reste le point d'activation des boutons :
#          sondage → None → grisés. Compatibilité : les bancs qui appellent
#          lire_refroidissement() sans detecter_capacites gardent
#          l'ancien comportement (défaut = pilotable). Test :
#          _test_tec_sonde_jalon37 (doubles de DLL : SV305C sans TEC qui
#          REFUSE CoolerEnable comme en réel, caméra avec TEC) ;
#          régression : _test_capacites, _test_tec_jalon33,
#          _test_pilotage_jalon35, _test_connexion_svbony_jalon36.
#          Point 4 de l'item 2d VALIDÉ EN RÉEL par Alain (connexion SV305C
#          OK avec le correctif du jalon 36).
# v2.20.5 : CONNEXION AUTOMATIQUE SVBONY RÉTABLIE (jalon 36, correctif du
#          point 4 de l'item 2d — retour réel d'Alain : « SVBONY (SDK) :
#          connexion impossible — Propriétés illisibles : SVBONY SV305C »)
#          — CAUSE (constat RÉEL du banc _diag_camera_svbony.py du
#          19/09/2026) : le SDK SVBONY REFUSE SVBGetCameraProperty tant que
#          la caméra n'est PAS ouverte, contrairement à la procédure « fiche
#          puis ouverture » de la doc (clone ZWO) ; SVBonyCamera.open()
#          lisait donc la fiche AVANT SVBOpenCamera et levait « Propriétés
#          illisibles » SANS JAMAIS tenter l'ouverture — alors que le banc,
#          qui ouvre d'abord, fonctionne. CORRECTION : ordre inversé dans
#          open() — SVBOpenCamera D'ABORD, fiche ENSUITE ; fiche encore
#          illisible → SVBCloseCamera propre avant l'échec (pas de caméra
#          orpheline) ; SVBSetAutoSaveParam(0) à l'ouverture (constat réel
#          du banc du 20/09/2026 : le SDK recharge ses paramètres
#          sauvegardés au redémarrage — expo/gain hérités sinon). Test :
#          _test_connexion_svbony_jalon36 (double de DLL qui rejoue le
#          refus pré-ouverture constaté en réel + vérification d'ordre) ;
#          régression : _test_capacites, _test_tec_jalon33,
#          _test_pilotage_jalon35. Test réel SV305C à faire par Alain
#          (setup 2) : connexion auto → bornes curseurs → TEC (⚠ alim 12 V)
#          → démarrage → déconnexion.
# v2.20.4 : PILOTAGE TEC ÉTENDU À TOUTES LES CAMÉRAS SDK (jalon 35, correctif
#          du point 3 de l'item 2d — retour réel d'Alain du 20/09/2026,
#          setup 2 : sur la POA Uranus-C Pro les contrôles TEC s'affichaient
#          (bornes de consigne détectées) mais les boutons ❄ restaient
#          GRISÉS) — CAUSE : `cam_pilotee` (la caméra que le thread de
#          travail sonde et pilote) était resté QHY-only depuis le jalon 25,
#          donc le sondage lire_refroidissement() n'était JAMAIS lancé pour
#          Player One / SVBONY / ZWO / Touptek : les implémentations du
#          jalon 33 étaient saines mais jamais appelées. CORRECTION :
#          constante CAMERAS_PILOTEES = toutes les caméras SDK (QHY, POA,
#          SVBONY, ZWO, Touptek), utilisée aux TROIS points d'installation
#          de la caméra (connexion auto jalon 32, chemin QHY, repli
#          « ▶ Démarrer ») ; les no-ops de CameraBase garantissent l'absence
#          d'effet pour une marque sans TEC/roue (boutons ❄ grisés,
#          combobox désactivée) ; garde hasattr(stop_live) sur le chemin
#          filtre (seul QHYCamera l'expose aujourd'hui). Le point 4
#          (connexion auto SVBONY « Propriétés illisibles ») reste à
#          traiter. Tests : _test_pilotage_jalon35 14/14 (NOUVEAU — câblage
#          app boutons ❄ POA + SVBONY) ; jalon33 21/21 ; jalon32 25/25 ;
#          jalon31 14/14 ; jalon34 21/21.
# v2.20.3 : COUPURE DE L'ÉCHELLE À 5 S (précision d'Alain du 20/09/2026,
#          après retest réel : « décoché, le curseur va du min à 5 s, coché
#          ça va de 5 s au max ») — pour TOUTES les caméras, bornes natives
#          comme échelles fixes :
#          - décochée : min → 5 s ; cochée : 5 s → exposition max (pivot
#            commun, les deux échelles se touchent, aucune valeur ne saute) ;
#          - le libellé affiche le pivot + la borne max RÉELLE (« Échelle
#            longue (5 s – 2 000 s) » sur Uranus-C Pro, « 5 s – 900 s » sans
#            sonde) ;
#          - bascule automatique à la saisie : > 5 s coche, < 5 s décoche ;
#          - plage native ENTIÈREMENT d'un côté du pivot : la case est
#            décochée (elle n'y aurait aucun effet — pas de réglage factice) ;
#          - _EXPO_LONG passe de (1 s, 900 s) à (5 s, 900 s) ;
#          - _test_expo_affichage_jalon34 : 21 vérifications.
# v2.20.2 : « ÉCHELLE LONGUE » RÉTABLIE (retour réel d'Alain du 20/09/2026 :
#          « tu as carrément supprimé la case à cocher, ce n'est pas ce que
#          j'avais demandé ») — la case reste TOUJOURS VISIBLE et redevient
#          UTILE avec des bornes natives : cochée, le curseur log ne couvre
#          que la longue portée (1 s → exposition max réelle, réglage fin
#          des longues poses) ; décochée, pleine plage (µs → max) ; le
#          libellé affiche la borne max RÉELLE (« Échelle longue
#          (1 s – 2 000 s) » sur Uranus-C Pro), 900 s si aucune sonde — le
#          point 1 (libellé en dur) reste donc corrigé ; la saisie d'une
#          valeur courte décoche automatiquement (retour pleine plage) ;
#          _test_expo_affichage_jalon34 mis en cohérence (17 vérifications).
# v2.20.1 : AFFICHAGE DE L'EXPOSITION (jalon 34, points 1 et 2 de l'item 2d —
#          retours RÉELS d'Alain du 20/09/2026, setup 2) :
#          - (point 2) _fmt_expo ne produit JAMAIS de notation scientifique
#            (avant : « 2e+03 s » au-delà de 1000 s, illisible) — au-delà de
#            10 s la valeur est arrondie à l'entier (le pas réel de la caméra
#            est ≥ 1 ms) et les milliers sont séparés par une espace fine
#            insécable (« 2 000 s », « 20 000 s ») ;
#          - (point 1) la case « Échelle longue » : le libellé « 1 s – 900 s »
#            était CODÉ EN DUR alors que la caméra va jusqu'à sa borne native
#            (2000 s sur Uranus-C Pro / SV305C) — le libellé est désormais
#            GÉNÉRÉ (_maj_libelle_expo_longue) ; ET comme la case n'a PLUS
#            AUCUN EFFET quand des bornes natives sont détectées (une seule
#            plage log dynamique, _expo_bornes la court-circuite), elle est
#            MASQUÉE à la connexion (pack_forget dans _adapter_ui_capacites)
#            et remontée au défaut à la déconnexion (ancre `_row` = la ligne
#            du curseur expo, after= pour retrouver sa place exacte) ;
#          - _test_expo_affichage_jalon34.py : 13 vérifications (format
#            décimal, milliers séparés, case masquée/remontée/libellé
#            régénéré) ; non-régression : jalon32 25/25, jalon31 15/15,
#            sliders jalon6 OK.
# v2.20.0 : PILOTAGE TEC PLAYER ONE / SVBONY (jalon 33, demande d'Alain du
#          20/09/2026) — le mécanisme app était DÉJÀ générique depuis le
#          jalon 26 (sondage lire_refroidissement → boutons ❄ activés,
#          demande consigne/arrêt exécutée dans le thread de travail,
#          rafraîchissement 2 s) ; seules les implémentations SDK manquaient :
#          - PlayerOneCamera : consigne POA_TARGET_TEMP (17, int OU float
#            selon les attributs) PUIS POA_COOLER ON (18) — ordre éprouvé par
#            le banc ; lire → (temp °C [ctrl 3 FLOAT], PWM 0-255 [puissance %
#            ctrl 16 convertie], consigne) ; arrêt = POA_COOLER OFF ; sonde
#            POASonde construite UNE fois (lister coûte ~31 lectures) ;
#          - SVBonyCamera : CoolerEnable (14) PUIS TargetTemp ×10 (15 —
#            unités de 0,1 °C, éprouvé par le banc) ; lire → (temp ctrl 16
#            /10, PWM [puissance % ctrl 17], consigne ctrl 15 /10) ; arrêt =
#            CoolerEnable 0 ; les trois méthodes ne lèvent JAMAIS sur caméra
#            sans TEC : lire → None (l'app laisse les boutons ❄ grisés) ;
#          - jalon 33 : _deconnecter_camera — la définition DUPLIQUÉE (la
#            version threadée jalon 26b écrasée par la version simple du
#            19/09 au soir) est supprimée ; DÉCISION ALAIN 20/09 : la version
#            du 19/09 (worker arrêté D'ABORD dans _on_close, close dans le
#            thread Tk) est celle qui fonctionnait, on la garde ;
#          - _test_tec_jalon33.py : 20 vérifications sur des doubles de DLL
#            (poses/lectures typées fidèles aux relevés réels, conversions
#            % → PWM et 0,1 °C, refus SDK → messages clairs « 12 V », caméra
#            sans TEC, caméra fermée).
# v2.19.0 : CAPACITÉS DYNAMIQUES POUR TOUTES LES MARQUES (jalon 32, demande
#          d'Alain du 20/09/2026 : « implémenter le mécanisme dynamique pour
#          toutes les caméras validées avec les diagnostics » — constat : en
#          réel, les bornes n'arrivaient QUE pour QHY) :
#          - CONSTATS CODE : le câblage jalon 31 ne détectait qu'à la
#            connexion QHY (Player One et SVBONY se connectaient au
#            « ▶ Démarrer » SANS détection) ; et _adapter_ui_capacites
#            cherchait les cid QHY LITTÉRAUX (« 6 » gain, « 7 » offset),
#            qui chez Player One désignent la balance des blancs B (ctrl 6)
#            et chez SVBONY « Flip » : les curseurs auraient été reconstruits
#            sur des bornes FAUSSES si la sonde avait répondu ;
#          - CID_CONTROLES_PAR_MARQUE (capacites.py) : ids PAR MARQUE des
#            enums officielles des SDK (QHY gain 6 / offset 7 / expo 8 /
#            TEC 18 ; Player One gain 1 / offset 7 / expo 0 / TEC 17 ;
#            SVBONY gain 0 / offset 13 BlackLevel / expo 1 / TEC 15 ;
#            ZWO gain 0 / offset 5 / expo 1 / TEC 16) ; Capacites.plage(rôle)
#            résout le cid selon la marque puis lit la plage du relevé
#            (repli : plages normalisées, step 1) ; l'UI n'interroge plus
#            AUCUN cid littéral ;
#          - detecter_capacites POA / SVB / ZWO : remplissent désormais
#            extras PAR CONTRÔLE (clé = id string : min/max/step/valeur/nom)
#            — les bancs réutilisent la même sonde, sans changement pour
#            eux ;
#          - App : connexion AUTOMATIQUE à la détection pour TOUTES les
#            marques SDK (_connecter_sdk, thread dédié, comme QHY jalon 26)
#            ; résultat consommé par _tick → detecter_capacites +
#            _adapter_ui_capacites via le facteur commun
#            _installer_camera_connectee (le chemin QHY appelle EXACTEMENT
#            le même code) ; connexion annulée proprement (close) si la
#            source change pendant l'ouverture ; « ▶ Démarrer » neutralisé
#            pendant la connexion ; _start (chemin de repli) détecte aussi
#            les capacités après open() ; dégradation silencieuse (sonde
#            muette → défauts, jamais d'erreur) ;
#          - déconnexion : inchangée (le vidage des capacités était déjà
#            générique).
#          Test : _test_capacites_ui_jalon32.py (POA Uranus-C Pro : gain
#          0→750, offset 0→250, expo 10 µs→2000 s, TEC -50→30 ; SV305C :
#          gain 0→450, BlackLevel 0→255, expo 36 µs→2000 s) ;
#          _test_capacites (29/29) et _test_ui_dynamique_jalon31 (15/15)
#          restent au vert.
# v2.18.0 : UI DYNAMIQUE — LA FENÊTRE S'ADAPTE À LA CAMÉRA BRANCHÉE
#          (jalon 31, demande d'Alain du 20/09/2026 : « quand tu connectes
#          une caméra tu fais ce travail de détection et ensuite tu
#          construis l'UI », pour TOUTES les marques — RIEN codé en dur) :
#          - avastack/cameras/qhyct.py (NOUVEAU) : sonde ctypes native
#            QHY extraite du banc (UNE définition — le banc délègue) :
#            plages MinMaxStep + roue CFW, validations réelles du jalon 30 ;
#          - QHYCamera.detecter_capacites() : traduit le relevé natif fait
#            À L'OUVERTURE (avant que le binding ne réclame l'USB — accès
#            séquentiel, PAS de ReleaseQHYCCDResource à côté du binding) ;
#          - App._adapter_ui_capacites() : à la connexion, curseurs
#            gain/offset RECONSTRUITS aux plages réelles (MiniCam8M : gain
#            0→230, offset 0→255), exposition bornée par la plage native
#            (1 µs → 3600 s — la case « échelle longue » devient inutile,
#            toute la plage passe dans le curseur log), consigne TEC
#            clampée à la plage réelle (-50 → 50 °C, bornes affichées),
#            roue limitée aux SLOTS détectés (8 sur la MiniCam8M) ;
#          - déconnexion → retour aux valeurs par défaut ; dégradation
#            silencieuse (sonde muette → UI d'origine, jamais d'erreur) ;
#          - BUG préexistant corrigé au passage : « ⏏ Déconnecter »
#            référençait btn_deconnecter (inexistant — AttributeError
#            garanti à l'usage) au lieu de btn_deconnect.
#          Test : _test_ui_dynamique_jalon31.py (15/15, fenêtre réelle +
#          Capacites du relevé MiniCam8M) ; 33/33 QHY ; 29/29 capacités.
# v2.17.2 : BANC QHY — CORRECTIF RÉEL n°2 (MiniCam8M, 20/09 matin) :
#          IsQHYCCDControlAvailable suit la convention du SDK ENTIER :
#          **0 (QHYCCD_SUCCESS) = contrôle DISPONIBLE** (pas « 1 = vrai » ;
#          confirmé par le driver INDI : « ... == QHYCCD_SUCCESS »). Le log
#          réel (26 × 0, 37 × 0xFFFFFFFF) l'a révélé — les 26 réponses 0
#          SONT les contrôles disponibles. Diagnostic affiché en clair si
#          la dispo ne répond jamais 0. v2.17.1 : SetQHYCCDStreamMode +
#          InitQHYCCD(handle) après OpenQHYCCD (obligatoire pour les
#          lectures) ; roue CFW native VALIDÉE EN RÉEL (détectée, 8 slots).
# v2.17.1 : BANC QHY — CORRECTIF RÉEL (MiniCam8M, 20/09 matin) : les plages
#          ctypes sortaient TOUTES « indisponibles » car la sonde appelait
#          IsQHYCCDControlAvailable SANS l'initialisation par handle — le
#          SDK exige SetQHYCCDStreamMode + InitQHYCCD(handle) APRÈS
#          OpenQHYCCD (l'en-tête officiel le déclare ; la séquence binding
#          du banc le faisait déjà). La sonde fait désormais les deux
#          (codes retour tracés) et affiche un diagnostic explicite si la
#          disponibilité ne répond toujours pas. EN RÉEL (20/09) : la roue
#          CFW native est VALIDÉE en lecture — détectée, **8 slots**
#          (ctrl 44 = 8, pas la valeur « 9 = non supporté » de la doc),
#          statut relu '3' (= le code 51 que relit le binding sur ctrl 17 :
#          les DEUX voies lisent le même ASCII — la convention '0' =
#          position 1 de la doc reste à trancher par l'EFFET PHYSIQUE).
# v2.17.0 : BANC QHY — SONDE CTYPES NATIVE (jalon 30, voie validée par
#          Alain le 19/09/2026 ; banc UNIQUEMENT, aucun changement de
#          comportement de l'application) :
#          - _diag_camera_qhy.py appelle qhyccd.dll DIRECTEMENT (sans le
#            binding PyPI) dans un SOUS-PROCESSUS isolé (Init/Release du SDK
#            sans danger, segfault éventuel ne tuant que l'enfant ; refus si
#            le flux est actif — jamais deux ouvertures) ;
#          - PLAGES des contrôles via GetQHYCCDParamMinMaxStep (absente du
#            binding ; nom VÉRIFIÉ dans les exports réels de la DLL livrée
#            par parseur PE — « GetQHYCCDParamMinMax » tout court n'existe
#            pas) : disponibilité + min/max/step + valeur pour chaque
#            contrôle 0..62, enum CONTROL_ID de l'en-tête officiel IDENTIQUE
#            à la table NOMS_CTRL du banc ; résumé « pour câbler l'UI »
#            (expo lisible en µs/ms/s, gain, offset, TEC, slots roue) ;
#          - ROUE INTÉGRÉE via les fonctions natives CFW (IsQHYCCDCFWPlugged
#            — 0 = roue trouvée, doc QHY —, GetQHYCCDCFWStatus, ordre ASCII
#            '0'+(position-1), relecture 0,5 s / timeout 25 s) : statut +
#            rotation avec VERDICT de confirmation ; l'EFFET PHYSIQUE reste
#            à vérifier en réel (la voie binding écrit 48+n, la doc dit
#            '0'=position 1 — à trancher demain matin sur la MiniCam8M) ;
#          - prototypes ctypes explicites (restype/argtypes — leçon v2.16),
#            buffers sur-alloués (leçon SVB), DLL recherchée dans
#            AVASTACK_QHY_DIR / dossier du banc / DLL embarquée du paquet
#            (site-packages/vendor/lib — chemin + date affichés).
# v2.16.0 : CAPACITÉS DYNAMIQUES PAR MARQUE (jalon 29, objectif d'Alain du
#          19/09/2026 : « pour une marque, être capable EN DYNAMIQUE de
#          connaître les capacités de la caméra » — il n'a pas accès à
#          toutes les caméras de ces marques, donc RIEN ne doit être codé
#          en dur par modèle) :
#          - avastack/cameras/capacites.py (NOUVEAU) : modèle commun
#            `Capacites` (plages expo/gain/offset, TEC + consigne, bins,
#            formats, USB3, ST4, roue, série, énumération brute des
#            contrôles) + `Controle` + table GAIN_UNITAIRE_CONNU
#            (annotation par capteur — IMX585 : 210 — jamais un réglage) +
#            vers_texte() (verdict) et vers_dict() (archivage JSON).
#          - Contrat `detecter_capacites()` sur `CameraBase` (no-op →
#            None), implémenté pour les 3 SDK qui exposent la découverte
#            dynamique (vérifié dans les exports des DLL livrées) :
#            * Player One : sonde `POASonde` (structures + validation du
#              layout « récent/ancien » déplacées du banc dans
#              playerone.py — UNE définition, le banc délègue désormais ;
#              POASetConfig passe enfin la vraie union POAConfigValue au
#              lieu d'un entier nu) ;
#            * ZWO : ctypes direct sur ASICamera2.dll (ASIGetNumOfControls
#              + ASIGetControlCaps + fiche ASI_CAMERA_INFO — structs du
#              wrapper de référence python-zwoasi, MIT) ;
#            * SVBONY : ctypes sur SVBCameraSDK.dll (SVBGetNumOfControls +
#              SVBGetControlCaps + fiche SVBCameraProperty — structs du
#              wrapper pysvbony, MIT) ;
#            * QHY : le binding PyPI n'expose aucune fonction de plages →
#              capacités PARTIELLES reportées (à compléter plus tard).
#          - Sonde = sur caméra OUVERTE : à appeler entre open() et
#            close(). Tests : nouveau `_test_capacites.py` (faux SDK) +
#            banc POA refactoré (25/25) + batterie complète au vert.
#          - PREMIER RELEVÉ RÉEL (Uranus-C Pro, 19/09/2026 soir, banc
#            v2.16) : gain 0→750 (PAS ce qu'on aurait deviné — preuve que
#            tout doit rester dynamique), offset 0→250, expo 10 µs→
#            2000000000 µs (ctrl 0), bins [1,2,3,4] (bin 3 inclus !), TEC
#            -50→30 °C, e-/ADU annoncé 11,4, formats RAW8/RAW16/RGB24/
#            MONO8, ST4 non, n° série CAMD31905CE042109000. FOURNIT AUSSI
#            4 DÉFAUTS, corrigés dans la foulée :
#            (1) contrôles FLOTTANTS relus comme des ENTIERS par le banc
#                (température affichée -1073741824 = bits du flottant -2.0)
#                → le banc passe désormais par sonde.lister() qui remplit
#                le cache de types (test 3b dédié) ;
#            (2) libellé « EGAIN lu » trompeur (c'était le défaut, qui est
#                d'ailleurs HORS de ses propres bornes [0,10] — signalé
#                « attribut peu fiable ») → le verdict montre courant +
#                défaut + avertissement de cohérence ;
#            (3) padding du tableau imgFormats_ compté comme formats
#                (4 × RAW8) → `dedupliquer()` appliqué aux bins/formats
#                dans les 3 sondes ;
#            (4) contrôle 31 « Exp » (exposition en SECONDES, flottant,
#                max 7200 s — DIFFÉRENT du ctrl 0 en µs) : au-delà de
#                l'enum documentée 0-30 → nommé, et signalé dans le
#                verdict (« contrôles au-delà de l'enum ») ;
#            (5) flux live sans diagnostic → état journalisé avant
#                départ, relance UNIQUE de l'exposition à mi-patience,
#                abandon expliqué (pistes : format/ROI lourds, expo
#                pilotée ailleurs) ; aperçu DÉCIMÉ avant calcul (frame
#                RGB24 plein format = 25 Mo) ; cadence d'UI accélérée
#                pendant le flux ; une seule frame en attente (écrasement).
#          - FLUX POA VALIDÉ EN RÉEL (~43 fps plein champ RGB24, >200 fps
#            en bin 2, TEC/gain/offset posés et relus) — et la cause du 1er
#            échec corrigée : _ouvrir() démarre l'exposition (POAStartExposure).
#          - BANC SVBONY (jalon 28b, demande d'Alain : « je préfère que tu
#            fasse le banc SVBony » — SV305C de guidage testable) :
#            _diag_camera_svbony.py, même architecture que le banc POA
#            (chargement diagnostiqué + garde « application trop ancienne »,
#            sonde RÉUTILISÉE via SVBonyCamera.detecter_capacites, poses
#            expo/gain/BlackLevel/TEC/flip/bin-ROI/format, flux live avec
#            diagnostic + relance stop/start, verdict + rapport %TEMP%,
#            mode --console). Spécificités SVBONY (en-tête officiel
#            SVBCameraSDK.h, dépôt pysvb) : PAS de SVBInitCamera
#            (SVBOpenCamera suffit, 36 exports vérifiés), températures en
#            unités de 0,1 °C (le banc convertit), flip = UN seul contrôle
#            (0-3), bin = taille FINALE dans SVBSetROIFormat, SupportedBins
#            terminé par 0. svbony.py : + constante SVB_FLIP.
#            plus d'effet grâce à défauts d'usine +
#            SVBSetAutoSaveParam(0) ; format interne RÉEL = RGB32 (4
#            o/pixel, déduit de la donnée — ni le set ni la relecture ne
#            disaient la vérité).
#            Installateur rebuildé (les 3 bancs embarqués : QHY, Player
#            One, SVBONY).
# v2.15.0 : OFFSET + ZONES DE SAISIE + DÉCONNEXION TRACÉE (jalon 27, demandes
#          d'Alain du 19/09/2026 : « il manque l'offset ; pour l'exposition,
#          l'offset et le gain, une zone de saisie en plus des sliders
#          serait très pratique » + « Déconnecter n'a rien fait, pas de
#          messages »).
#          (1) OFFSET (contrôle 7, unités SDK) : contrat no-op
#          `definir_offset` sur `CameraBase`, implémenté sur QHYCamera
#          (set_param(7)) ; slider « Offset (0 – 255) » dans le cadre
#          Caméra, valeur poussée comme les réglages (pending_offset,
#          exécutée par le worker, jamais depuis Tk) ; posée aussi à la
#          connexion. À VALIDER EN RÉEL (le SDK stocke sans valider : seul
#          l'effet physique tranche — leçon du 19/09).
#          (2) ZONES DE SAISIE : `_add_slider(..., saisie=True)` remplace le
#          label de valeur par une Entry (Return ou sortie de champ =
#          application + bornage sur la grille ; le curseur suit) — activé
#          pour Gain et Offset. EXPOSITION : Entry dédiée acceptant « 100 »,
#          « 0,5 », « 12 ms », « 2 s », « 11 µs » — bornée à l'échelle
#          courante avec BASCULE AUTOMATIQUE d'échelle si la valeur déborde.
#          (3) DÉCONNEXION TRACÉE : chaque étape de `_executer_deconnexion`
#          passe dans le journal QHY (avastack_qhy_debug.log) — close() en
#          PREMIER (coupe flux ET TEC en une opération ; l'écriture du
#          contrôle TEC en régulation avant close était le suspect du
#          blocage silencieux), arrêt TEC explicite en repli seulement ; si
#          la déconnexion ne confirme pas en 10 s, message visible dans
#          l'UI (rouge) invitant à fermer la fenêtre (fermeture bornée 15 s,
#          puis sortie forcée).
# v2.14.3 : CORRECTIFS ROUE + DÉCONNEXION + INSTALLATEUR (constats réels
#          d'Alain, 19/09/2026 en fin de soirée).
#          (1) CHANGEMENT DE FILTRE EN ÉCHEC (« QHYCamera object has no
#          attribute 'stop_live' ») : le changement de filtre appelle
#          stop_live()/begin_live() sur la CLASSE cam_pilotee (pas sur le
#          handle natif self.cam) — la classe QHYCamera les expose désormais
#          et délègue au handle avec trace (vérifié par le faux SDK).
#          (2) « ⏏ DÉCONNECTER » SANS EFFET + FERMETURE IMPOSSIBLE : les
#          appels natifs du SDK (TEC, close) étaient faits depuis le thread
#          Tk PENDANT que le thread de travail lit le flux — conflit du SDK
#          natif = blocage sans message. La déconnexion est maintenant une
#          DEMANDE exécutée par le thread de travail (TEC coupé, close),
#          dont la confirmation met à jour l'UI ; la fermeture de la fenêtre
#          demande puis attend (borne 15 s, l'UI se rafraîchit) avant de
#          forcer la sortie.
#          (3) INSTALLATEUR : les DLL des SDK constructeurs posées à la
#          racine du dépôt (ASICamera2.dll, PlayerOneCamera.dll, ToupCam.dll,
#          SVBCameraSDK.dll) sont désormais EMBARQUÉES dans l'installateur
#          (demande d'Alain) — sdk_loader.py les trouve dans le dossier du
#          programme ; le paquet pip zwoasi est installé (requirements.txt
#          décommenté) ; LISEZMOI.txt et la page SDK de l'installateur mis à
#          jour. Les DLL restent hors du dépôt git (*.dll dans .gitignore).
# v2.14.2 : CORRECTIF — CONNEXION QHY FIGÉE À « connexion de la caméra… »
#          (constat réel d'Alain, 19/09/2026 au soir : « Détecter » affichait
#          le message pour toujours, aucun contrôle actif, fermeture
#          impossible — tuer le process au gestionnaire des tâches).
#          CAUSE : le thread de connexion lisait des VARIABLES TKINTER
#          (var_expo.get() / var_gain.get() pour apply_settings) — un appel
#          Tcl depuis un thread secondaire peut bloquer SUR LE VERROU Tcl
#          SANS JAMAIS RENDRE LA MAIN (pas d'exception, thread mort-vivant) :
#          le résultat n'arrivait jamais, la connexion ne se consommait plus
#          et la fermeture de la fenêtre ne se faisait plus proprement.
#          CORRECTIF : le thread de connexion ne touche plus à AUCUNE
#          variable Tk — il se borne à ouvrir la caméra ; les réglages
#          (expo/gain) sont posés par le worker (pending_settings,
#          instantanés expo_ms/gain_val tenus par le thread Tk). Détection
#          ignorée pendant une connexion en cours, et « ⏏ Déconnecter »
#          reste actif pendant l'empilement (sortie de secours disponible).
# v2.14.1 : CONNEXION À LA DÉTECTION — RÉGLAGES AVANT L'EMPILEMENT (jalon 26,
#          demande d'Alain : « souvent la caméra a le filtre Dark à la mise
#          en marche ; que la caméra soit connectée quand elle est détectée,
#          et que Démarrer ne démarre que l'empilement, comme ça on peut
#          régler ce qu'on veut (attendre la bonne température) AVANT
#          d'empiler »).
#          (1) « 🔎 Détecter » CONNECTE désormais la caméra QHY (thread
#          dédié : open() + flux + apply_settings) dès la détection — le
#          sondage des contrôles (roue/TEC) et le refroidissement à la
#          consigne par défaut s'exécutent SANS attendre une frame, donc
#          AVANT l'empilement. Le thread de travail est PERMANENT : il
#          continue de piloter les contrôles et relire le TEC toutes les 2 s
#          même quand l'empilement est en pause.
#          (2) « ▶ Démarrer » = lancement de l'EMPILEMENT seulement (reset
#          complet de session exécuté par le worker via
#          empilement_start_request, purge de la file du SDK limitée aux
#          flux live — jamais pour les sources « dossier ») ; « ■ Arrêter »
#          = PAUSE (caméra connectée, refroidissement maintenu, contrôles
#          actifs, reprise sans rebrancher) ; nouveau bouton « ⏏
#          Déconnecter » (coupe le TEC puis referme la caméra — rappel : le
#          SDK QHY n'est pas réinitialisable dans le même process, il faut
#          relancer l'application pour reconnecter) ; changement de source
#          avec caméra connectée = déconnexion automatique (prévenue) ;
#          fermeture de l'application = déconnexion complète.
#          (3) Constat corrigé au passage : la relecture TEC (temp/PWM/18)
#          n'était jamais faite dans le worker (l'affichage restait à « — »)
#          → lecture périodique toutes les 2 s, en session comme en pause.
#          (4) Tests adaptés au nouveau flux (empilement_armé dans les 9
#          tests qui lancent le worker) — 32/32 fichiers au vert.
# v2.14.0 : CONTRÔLES CAMÉRA QHY — ROUE À FILTRES + REFROIDISSEMENT (jalon 25,
#          relevés réels d'Alain du 19/09/2026 : la roue INTÉGRÉE de la
#          MiniCam8M fonctionne par le contrôle 17 alors que le contrôle 44
#          « CfwSlotsNum » répond INDISPO — c'est 17 seul qui fait foi ; la
#          position est le code ASCII 48 + n, 48 = cran 0 = slot NOIR « Dark »,
#          puis L R G B SII Ha OIII ; 48+n testé EN RÉEL par Alain : la roue
#          tourne et l'image change).
#          (1) Contrat `cameras/base.py` : roue (roue_disponible /
#          position_filtre / choisir_filtre) et refroidissement
#          (consigne_refroidissement / lire_refroidissement /
#          arreter_refroidissement) — no-op par défaut, comme apply_settings.
#          (2) `cameras/qhy.py` : implémentation par les contrôles du SDK —
#          roue = dispo/position/écriture sur 17 (attente de fin de rotation
#          par relecture, timeout 25 s conseillé par la doc QHY) ;
#          refroidissement = consigne 18 (mode auto), lectures 14 (temp
#          capteur) / 15 (PWM 0-255) / 18, ARRÊT = PWM manuel 16 à 0.
#          (3) UI, cadre « Caméra » : EXPOSITION en curseur logarithmique à
#          deux échelles (11 µs → 5 s par défaut ; case « Échelle longue » →
#          1 s → 900 s ; `var_expo` reste en ms réelles pour le contrat
#          existant) ; GAIN 0 → 175 (unités SDK QHY, défaut 30) ; ligne
#          « Filtre : » (combobox Dark/L/R/G/B/SII/Ha/OIII, active seulement
#          si la roue répond au sondage) ; ligne refroidissement (consigne
#          °C + boutons ❄ Réguler / ⏹ Arrêter + affichage « Capteur : x °C ·
#          TEC : n % (pwm/255) · consigne »). TOUTES les demandes (filtre,
#          TEC) sont posées côté thread Tk et exécutées par le thread de
#          travail (aucun appel SDK depuis Tk) ; le sondage roue/TEC se fait
#          après la 1re frame reçue. Changement de filtre : stop_live →
#          déplacement → begin_live → PURGE des frames arrivées pendant la
#          rotation (décision d'Alain : jamais deux filtres empilés).
#          Arrêt de session : le TEC est COUPÉ automatiquement (⏹).
#          (4) `images.save_image(path, arr, entete=None)` : mots-clés FITS
#          optionnels — l'empilement sauvegardé porte désormais FILTER =
#          filtre courant (mono) ou rôle (canaux composés).
#          (5) `_test_qhy_camera.py` : faux SDK étendu (is_control_available,
#          get_param/set_param avec rotation simulée, TEC) — 31 vérifications.
#          À VALIDER EN RÉEL (miniPC) : déplacement réel de la roue depuis
#          l'appli, régulation TEC (alim. 12 V branchée), bornes réelles du
#          gain (0-175 = plage SDK annoncée, à confirmer par effet physique).
# v2.13.4 : DIAGNOSTIC CAMÉRA (aucun changement de comportement de l'appli ;
#          consigne d'Alain du 19/09/2026 : « on ne bosse que sur le
#          diagnostic caméra, arrête de rebuilder l'installateur » — donc
#          INSTALLATEUR NON REBUILDÉ à cette version).
#          (1) DÉCOUVERTE DE CAUSE : le log du miniPC montrait begin_live
#          SANS AUCUN set_resolution alors que le fichier était censé être
#          v2.13.2+ → les deux fichiers n'avaient pas été copiés ENSEMBLE
#          (banc récent + avastack/cameras/qhy.py resté en v2.13.1, la
#          version où set_resolution n'existait pas). D'où : « Démarrer »
#          plante (pas de ROI → segfault), « pas-à-pas » marche (le banc
#          pose la ROI lui-même), et la ROI cochée semble ignorée.
#          Correctif d'outillage : le banc AFFICHE désormais, à l'ouverture
#          ET à chaque démarrage, les fichiers réellement chargés (chemin,
#          date, présence de set_resolution, signature de open(), version
#          d'avastack) → une copie périmée devient VISIBLE au lieu d'être
#          invisible ; et si open() n'accepte pas de ROI, le banc le dit au
#          lieu de planter en TypeError.
#          (2) « Démarrer (séquence APPLI) » transmet enfin la ROI cochée
#          via open(roi=...) — la case ROI ne peut plus « ne rien faire ».
#          (3) NOUVEAU : balayage d'un contrôle (id, de, à, pas) : pose
#          chaque valeur, la relit, liste les refusées et affiche la plage
#          acceptée — c'est l'outil de DÉCOUVERTE DES VALEURS demandé (gain
#          QHY en unités constructeur, PWM du TEC, USB traffic…), préalable
#          au recalibrage des curseurs de l'appli (gain bridé à 8 alors que
#          le SDK QHY attend des unités constructeur).
#          (4) DÉCOUVERTE DE TOUTES LES VALEURS : « Lister les contrôles »
#          fait maintenant DEUX passes — les contrôles disponibles (nom
#          officiel + valeur), puis un balayage EXHAUSTIF 0..63, id
#          indisponibles compris, avec la valeur brute en hexadécimal.
#          C'est la seule façon de distinguer un contrôle ABSENT
#          (is_control_available() faux) d'un contrôle « drapeau » (valeur
#          sentinelle 0xFFFFFFFF).
#          (5) Test de CADENCE (bouton ⏸ Pause 3 s) et horodatage des 5
#          premières frames : à exposition 1000 ms on ne peut pas distinguer
#          « la caméra n'émet plus » de « nos lectures vident la file du
#          SDK ». La pause tranche ; les horodatages disent si le rythme est
#          tenu (t+1,0 / t+2,0…). Un compteur CUMULÉ de frames et l'âge de la
#          dernière frame sont affichés en permanence.
#          (6) VERDICT ROI AUTOMATIQUE (constat du 2e run, 19/09/2026 : le
#          log de « Démarrer » ne contenait TOUJOURS AUCUNE ligne
#          set_resolution, MÊME case ROI cochée). Le banc ne se contente plus
#          d'afficher les fichiers : il RELIT la tranche de trace produite
#          pendant l'ouverture (taille du log notée avant, lue après) et
#          conclut en clair — soit « ROI POSÉE ✔ (taille) », soit « TENTÉE
#          MAIS REFUSÉE par le SDK », soit « AUCUNE TENTATIVE → la copie
#          chargée de qhy.py est ANTÉRIEURE à la v2.13.2 : c'est la CAUSE,
#          pas la case ROI ». La case cochée ne pouvait RIEN prouver : un
#          fichier périmé ignore l'argument roi.
#          (7) RELANCE SANS FRAME (2e constat du même run) : après un
#          « ■ Arrêter », un nouveau « ▶ Démarrer » dans le MÊME process ne
#          recevait PLUS JAMAIS de frame (sans planter : 126 lectures sans
#          frame, ni 1er frame). Cause : le binding `qhyccd` n'expose AUCUNE
#          fonction de libération du SDK — vérifié par introspection, le
#          module ne contient que Camera, init_sdk, scan_cameras (+ des
#          utilitaires de chemins) : ni release_sdk ni ReleaseQHYCCDResource.
#          Fermer la caméra ne réinitialise donc PAS l'état global du SDK, et
#          rien ne permet de le faire dans le même process. Le banc le DIT
#          (au démarrage, après chaque close, et en avertissement si la
#          caméra a déjà été ouverte+fermée) : pour repartir proprement,
#          FERMER LE BANC et le relancer. LIMITE À REPORTER DANS L'APPLI :
#          même comportement côté appli → un redémarrage de la source QHY
#          après Arrêter exigera de relancer AVAStack.
#          (8) Ménage : suppression de définitions DUPLIQUÉES du banc (deux
#          copies de _infos_versions/_open_supporte_roi dont la 1re était
#          écrasée en silence — un doublon de fonction est exactement le
#          genre de piège que ce banc doit éviter).
#          ⚠ Le banc et avastack/cameras/qhy.py DOIVENT venir de la même
#          version : c'est l'affichage des fichiers chargés qui le garantit.
# v2.13.3 : BANC DE DIAGNOSTIC QHY enrichi et EMBARQUÉ dans l'installateur
#          (aucun changement de comportement de l'application : le banc est
#          un outil autonome, _diag_camera_qhy.py, désormais installé avec
#          elle — demandé par Alain pour déboguer la caméra hors de
#          l'application, sans relancer les tests de non-régression).
#          (1) Contrôles nommés d'après l'enum OFFICIEL du SDK QHY (crate
#          Rust `qhyccd-rs`, qui sous-tend le paquet PyPI) — fini les
#          libellés approximatifs : gain=6, offset=7, exposure(µs)=8 sont
#          VÉRIFIÉS en réel (trois relevés concordants : les valeurs posées
#          se relisent à l'identique) ; CurTemp=14, CurPWM=15,
#          ManualPWM=16, Cooler=18. La valeur 4294967295 lue partout est
#          la SENTINELLE D'ERREUR du SDK : elle marque les contrôles
#          « drapeaux » (CamBin2x2, Cam8bits, IsExposingDone…) et n'a
#          aucune signification physique (elle est maintenant affichée
#          comme telle).
#          (2) Panneau Refroidissement (TEC) dans le banc. CONSTAT
#          IMPORTANT : la MiniCam8M EST une caméra REFROIDIE (fiche QHY
#          « Cooled CMOS astronomy camera » ; alimentation 12 V requise
#          pour activer le circuit de régulation) — ma réponse précédente
#          (« pas de refroidissement sur ce modèle ») était FAUSSE. Le
#          binding n'expose AUCUNE méthode dédiée au froid : mode AUTO =
#          set_param(18, consigne °C), mode MANUEL = set_param(16, PWM
#          0-255, bascule le SDK en manuel), lectures get_param(14)
#          température capteur et (15) PWM courant — rafraîchies toutes les
#          2 s pendant le flux (cf. doc QHY « Temperature Control API »).
#          (3) Bouton d'introspection de l'API du binding (méthodes +
#          docstrings) : preuve qu'il n'existe pas de set_cooler, d'où le
#          passage par les id numériques.
#          (4) Garde-fou de la boucle de flux proportionnel à l'exposition
#          (2x, minimum 4 s) : à 5000 ms l'ancien seuil fixe de 4 s coupait
#          AVANT l'arrivée de la 1re frame (constat Alain : à 2000 ms le
#          flux tourne à 0,5 fps EXACTEMENT, ce qui prouve que l'exposition
#          est bien appliquée par le ctrl 8).
#          (5) Écriture/correction : les variables Tk sont lues dans le
#          thread principal (var.get() hors thread Tk est interdit) avant
#          de lancer l'écriture set_param dans un thread.
#          À FAIRE (constats du run) : le curseur Gain de l'application est
#          borné à 8 (échelle « 0.5-8.0 » héritée de Player One) alors que
#          le SDK QHY raisonne en unités constructeur (défaut relevé 30,
#          essai concluant à 90) — le gain QHY est donc bridé dans l'appli ;
#          et la température lue (ctrl 14, ~-1 °C) n'est plausible QUE si
#          l'alimentation 12 V est branchée (à confirmer).
# v2.13.2 : CORRECTION (constat Alain, run réel — banc _diag_camera_qhy,
#          19/09/2026) : « Démarrer (pas-à-pas + ROI) » échouait APRÈS
#          set_bin_mode avec « Operation failed with error code: 4294967295 »
#          (0xFFFFFFFF = erreur générique du SDK) sur
#          set_resolution(0,0,3864,2192) — taille tirée de la fiche Player
#          One de l'IMX585, REFUSÉE par le SDK QHY : la MiniCam8M expose
#          3840×2160. Et SANS ROI posée, begin_live/get_live_frame
#          segfaultent (la fenêtre mourait sans message — crash natif
#          identique au premier constat). Fix : QHYCamera.open() tente
#          set_resolution en repli (3840×2160, puis tailles candidates) ;
#          banc : défaut 3840×2160 + essais automatiques. Contrôles SDK
#          relevés par Alain (22 dispo sur 1..63) — numérotation OFFICIELLE
#          de l'enum, vérifiée ensuite : gain=6, offset=7, exposure(µs)=8,
#          CurTemp=14, CurPWM=15, ManualPWM=16, Cooler=18 (les libellés
#          « EXP=1, GAIN=2, OFFSET=3 » notés ici le 19/09 étaient ceux d'une
#          numérotation APPROXIMATIVE — corrigé en v2.13.3) — à exploiter
#          pour les bornes réelles des réglages (prochaine étape).
# v2.13.1 : CORRECTION (constat Alain, run réel — 1er test QHY Minicam8M,
#          19/09/2026) : source « QHY (SDK) » sans aucun retour d'info, et le
#          clic « Démarrer » FERMAIT l'application sans message. Cause : crash
#          NATIF (segfault) — QHYCamera.open() appelait cam.open() APRÈS
#          qhyccd.Camera(cid), alors que le CONSTRUCTEUR ouvre déjà la caméra
#          (vérifié sans matériel : RuntimeError « Failed to open camera: … »
#          sur un id inexistant) → double ouverture du handle USB, non
#          rattrapable par l'except de _start. Correctifs :
#          (1) séquence officielle du paquet (README wheel 0.1.3) — plus
#          d'appel open() explicite : Camera(id) → set_stream_mode(1) →
#          init() → set_bin_mode(1,1) → expos/gain → begin_live() ;
#          (2) read() normalise selon le dtype RÉEL du SDK (RAW8 → /255,
#          RAW16 → /65535 : le /65535 en dur aurait rendu une frame RAW8
#          noire) + COPIE float32 explicite (le ndarray du binding est
#          zero-copy côté Rust, buffer réutilisable à la frame suivante) ;
#          (3) trace d'étapes dans avastack_qhy_debug.log (dossier temp) —
#          un crash natif n'affiche rien : le log identifie la dernière
#          étape réussie ;
#          (4) UI : bouton « 🔎 Détecter » + auto-détection à la sélection
#          d'une source SDK, résultat affiché sous le panneau Caméra ; scan
#          QHY en SOUS-PROCESSUS isolé (timeout 25 s) — un segfault du SDK
#          au scan ne tue plus l'application ; l'id détecté est transmis à
#          QHYCamera (plusieurs caméras QHY branchées : la 1re est ouverte).
#          Nouveau test _test_qhy_camera.py (faux SDK, sans matériel).
# v2.13.0 : JALON 24 — GRADIENT + DÉBRUITAGE PAR COUCHE (décision d'Alain,
#          19/09/2026, reprise du chantier « reporté v2 » : « autant nettoyer
#          les images le plus tôt possible » — la pollution lumineuse et la
#          clarté de la lune ne frappent pas pareil selon le filtre, et une
#          palette Hubble n'est pas un fond physique : le modèle de fond de
#          GraXpert ne doit voir que des couches mono 2D ; élimine
#          STRUCTURELLEMENT le canal-mort SHO sans S du jalon 23b). En mode
#          COMPOSITION, le gradient (GraXpert) et le débruitage sont faits
#          sur CHAQUE COUCHE AVANT la composition ; la NETTETÉ reste sur le
#          composite (PSF identique pour toutes les couches, meilleur SNR
#          après débruitage par couche, moitié moins de calcul) — ordre :
#          couches (gradient → débruitage) → recomposition → netteté →
#          étirement. LIVE : le worker pousse les couches (CompositeStacker.
#          mean_avec_canaux, une seule passe de moyennes) via disp.vl_compo ;
#          le solveur traite chaque couche avec des CACHES PAR RÔLE (une
#          nouvelle frame ne relance que la couche qui en a reçu une — pas N
#          lancements CLI par frame) puis re-compose. EXTERNE (⚡) :
#          GraXpert gradient + débruitage exécutés sur chaque couche en FITS
#          2D MONO (plus de convention canaux-en-tête), recomposition, puis
#          BXT et chaîne couleur sur le composite. Échec d'une couche = couche
#          brute + message, la chaîne continue ; échec d'un subprocess =
#          erreur claire (même politique que la chaîne mono). En mode mono,
#          chaîne composite historique INCHANGÉE (jalons 4/9). Réutilisation
#          de _run_bloquant_survivable via le helper _ext_run_cmd (validation
#          du GABARIT avant substitution des placeholders — leçon du
#          débogage). Test _test_gradient_couche_jalon24.py.

# v2.12.1 : JALON 23b — GARDE-FOUS GRAXPERT (retour réel d'Alain : en SHO,
#          en cliquant GraXpert live pour le gradient, « plus d'image dans
#          la visu », non systématique mais fréquent). Cause : en SHO sans
#          S, le canal R du composite est ENTIEREMENT VIDE (aucun dossier
#          S2) — GraXpert reçoit une image à canal mort et son comportement
#          devient imprévisible (sortie dégénérée → image noire après
#          étirement). Trois garde-fous :
#          · couleurs.canal_mort(img) : détecte un canal entièrement vide
#            ('R'/'G'/'B') ;
#          · solveur VeraLux : si un canal est mort, GraXpert live n'est
#            PAS lancé — message clair « canal R vide (aucune donnée) :
#            GraXpert live ignoré » sur la ligne d'état, la chaîne
#            (débruitage/netteté/étirement) continue sur l'image brute ;
#          · external.live.appliquer + _run_external : sortie d'outil
#            DÉGÉNÉRÉE (NaN/Inf, image vide) rejetée → repli image brute /
#            erreur claire, au lieu d'un résultat noir.
#          Test _test_couleurs_jalon22.py section [5] (outils factices
#          autonomes astropy : NaN, image vide, copie ; canal mort jamais
#          appelé, image saine appelée une fois).

# v2.12.0 : JALON 23 — SCNR DOUX BORNÉ PAR LE BRUIT (décision d'Alain,
#          19/09/2026). Retour réel sur le jalon 22 : le SCNR « moyenne
#          neutre » classique vire une SHO sans S (R = 0, G = Ha, B = O3)
#          FRANCHEMENT AU BLEU — le neutre y devient (0+B)/2 = O3/2 et tout
#          le signal Ha est écrêté, car dans les palettes narrowband le vert
#          est de la DONNÉE, pas du bruit. Nouveau couleurs.scnr_doux :
#          n'ajouter que l'excès de vert DE L'ORDRE DU BRUIT — e = G −
#          (R+B)/2 ; σ estimé par MAD sur le DÉTAIL haute-fréquence de e
#          (1re couche starlet, cf. denoise.estimer_sigma) : insensible au
#          fait que la structure (nébuleuse) soit majoritaire, car une
#          nébuleuse est lisse et le grain seul vit en haute fréquence ;
#          seuil t = 3σ ; garotte douce sur la partie positive (e ≤ t → 0,
#          e > t → e − t²/e, e ≤ 0 inchangé) ; G' = (R+B)/2 + e'. Le
#          grésillement vert du fond disparaît, la teinte Ha/O3 est
#          préservée. Case « SCNR doux — bruit seul » en LIVE (cadre
#          VeraLux, entre SCNR et Démagenta ; clé _vl_params, chaîne « tel
#          que vu », vue « empilement » uniquement) et en TRAITEMENT
#          EXTERNE (« 5. SCNR doux — bruit seul », le Démagenta devient
#          « 6. » ; job 11-tuple, déballage tolérant). Ordre de la chaîne
#          couleur : SCNR classique → SCNR doux → démagenta. Persistance :
#          vl_scnr_doux / ext_scnr_doux. Test _test_couleurs_jalon22.py
#          étendu (grésillement retiré, structure préservée, mono no-op,
#          clé, chaîne externe, persistance).

# v2.11.0 : JALON 22 — SCNR (retrait du vert) + DÉMAGENTA (décision d'Alain,
#          19/09/2026). Nouveau module avastack/processing/couleurs.py :
#          SCNR « moyenne neutre » (G = min(G, (R+B)/2) — le vert excédentaire
#          est ramené à la moyenne des deux autres canaux, les étoiles
#          blanches restent intactes) et démagenta par la recette d'Alain
#          (négatif → SCNR → retour au positif). Placement demandé : APRÈS la
#          composition (sur l'image COULEUR du composite — « pour retirer du
#          vert, il faut de la couleur ») et JUSTE AVANT l'étirement ; no-op
#          sur un composite monochrome (source Mono). Quatre cases à cocher :
#          · LIVE (cadre VeraLux, sous le débruitage live) : « SCNR — retrait
#            du vert (live) » et « Démagenta — négatif + SCNR (live) » —
#            appliqués dans le solveur VeraLux après la netteté, et dans
#            process() pour les modes STF/manuel ; vue « empilement »
#            uniquement (suivent le changement de vue comme le débruitage
#            live) ; inclus dans la clé des réglages (_vl_params) et dans la
#            chaîne « tel que vu » ;
#          · TRAITEMENT EXTERNE : « 4. SCNR — retrait du vert » et
#            « 5. Démagenta (négatif + SCNR) » — appliqués EN FIN de chaîne
#            externe sur le résultat traité (job 10-tuple, déballage
#            tolérant pour les jobs 8-tuple).
#          Persistance : vl_scnr / vl_demagenta / ext_scnr / ext_demagenta
#          (booléens explicites). Test _test_couleurs_jalon22.py.

# v2.10.1 : JALON 21b — RETOUR RÉEL d'Alain (session SHO : 6 frames empilées
#          pour 86 refusées au début) : en « triangles d'abord » (HOO/SHO),
#          les canaux narrowband montrent souvent MOINS DE 6 étoiles communes
#          — le minimum exigé par les triangles — d'où des refus en masse.
#          REPLI après l'échec des triangles : chemin « étoiles »
#          (centroïdes + vote + contre-vérification mutuelle) puis
#          corrélation de phase honnête (Hann + gain SSD net exigé, ±40 px).
#          ORB reste ÉCARTÉ en narrowband (c'est lui qui s'apparie mal d'un
#          filtre à l'autre). La ligne d'état « Align. » affiche la méthode
#          réellement utilisée (triangles / étoiles / phase). Test
#          _test_narrowband_ha_jalon21.py enrichi (champ pauvre → phase).

# v2.10.0 : JALON 21 — NARROWBAND (HOO/SHO) : TRIANGLES SEULS + ANCRE HA
#          (décision d'Alain, 19/09/2026). En composition narrowband
#          contenant le rôle Ha (HOO, SHO) : (1) l'alignement se fait
#          SYSTÉMATIQUEMENT par TRIANGLES d'étoiles — nouveau mode
#          StarAligner.triangles_seuls : ORB (descripteurs de gradients,
#          qui s'apparient mal d'un filtre à l'autre), le chemin « étoiles »
#          et la phase ne sont PAS tentés ; si les triangles ne concluent
#          pas, la frame est refusée (jamais d'empilement approximatif) ;
#          (2) la référence d'alignement INITIALE est TOUJOURS une brute Ha
#          — tant qu'aucune brute Ha n'est arrivée, les frames des autres
#          rôles (déjà archivées) ne créent PAS l'empilement (ligne
#          d'état « en attente d'une brute Ha ») ; à la 1re Ha, l'ancre est
#          posée sur elle (_do_restack_compo avec ancre FORCÉE) et les
#          frames archivées entre-temps sont REJOUÉES — ensuite, en cas de
#          re-stack, comportement normal du jalon 20 (meilleure brute tous
#          rôles confondus). Mono, RGB et LRGB inchangés (cascade ORB →
#          triangles → étoiles → phase ; 1re frame = ancre). Tests :
#          _test_narrowband_ha_jalon21.py (nouveau) ; les images
#          synthétiques des tests jalon 19 sont maintenant BRUITÉES (sans
#          bruit, la détection d'étoiles renvoie « image constante » et les
#          triangles n'ont rien à appareiller) ; _test_compo_ui_jalon19.py
#          rendu hermétique à la vraie config (ui.CONFIG = {} + sauvegarde
#          interceptée — la vraie config contient les lignes compo réelles
#          d'Alain).

# v2.9.1 : CORRECTIF — débruitage robuste aux pixels invalides (retour réel
#          d'Alain : RuntimeWarning « invalid value encountered in cast »
#          dans denoise._nlm avec la case débruitage cochée). Un NaN/Inf
#          arrivant à l'entrée (sortie d'outil externe, FITS douteux…) était
#          jeté à 0 par la conversion 16 bits du NLM (points noirs + warning)
#          et les ondelettes propageaient le NaN à TOUTE la reconstruction.
#          denoiser() sanatisé l'entrée (NaN → 0, ±Inf → 1/0) AVANT les deux
#          algorithmes, avec compteur affiché en console
#          (« avastack.denoise : N pixels invalides… corrigés ») pour
#          diagnostiquer l'amont. Aucun changement d'algorithme sur des
#          données valides. Cas de régression ajouté à
#          _test_dn_local_jalon8.py (warning transformé en erreur).

# v2.9.0 : JALON 20 — RE-STACK MULTI-CANAL (mode composition). Le re-stack
#          « à la Siril » (jalon 16/18) s'applique AUSSI au mode composition
#          multi-filtres (HOO/SHO/RGB/LRGB) : chaque couche (rôle) a ses
#          mauvaises frames ou ses meilleures au fil du stack, et une
#          meilleure brute de N'IMPORTE QUELLE couche doit pouvoir re-ancre.
#          Scores qualité PAR RÔLE (nb d'étoiles mesuré sur le CANAL EXTRAIT
#          de chaque rôle — la même mesure que l'alignement, donc comparable
#          d'une couche à l'autre), mémorisés parallèlement aux archives PAR
#          RÔLE (jalon 19). Déclencheur AUTO : la meilleure brute TOUS RÔLES
#          confondus bat la référence courante de 1,5× (marges et constantes
#          du jalon 16 inchangées ; l'ancre courante, maintenant (rôle,
#          index), est exclue — pas de boucle) ; le bouton « ⟳ Re-stacker
#          (meilleure brute) » est désormais HONORÉ en mode compo. Le
#          recalcul (_do_restack_compo) : la meilleure brute devient la
#          référence de l'aligneur PARTAGÉ (même repère pour toutes les
#          couches) puis TOUTES les couches sont recalculées depuis leur
#          archive PAR RÔLE — canal du rôle ré-extrait de chaque brute
#          archivée, ré-alignement, ré-empilement : les frames qui avaient
#          refusé avec l'ancienne référence ont une seconde chance, couche
#          par couche. Nouvelle façade CompositeStacker avec réglages
#          conservés (composition, gains R/G/B, mode L, WB, méthode/fenêtre
#          de rejet). Ligne dédiée du re-stack enrichie du détail PAR CANAL
#          (« re-stack #2 (bouton · Ha 9/9 · O3 8/9) : … »). Le chemin mono
#          (jalon 16/18) est inchangé. Test _test_restack_compo_jalon20.py ;
#          _test_compo_worker_jalon19.py mis à jour (scores PAR RÔLE au lieu
#          de « re-stack désactivé »).

# v2.8.0 : JALON 19 — COMPOSITION MULTI-FILTRES (RGB/HOO/SHO/LRGB). Live
#          stacking de brutes prises avec des filtres différents (1 à 4
#          dossiers surveillés, un RÔLE = un filtre par dossier) et composite
#          temps réel. Sources « Composition multi-dossiers » au menu ;
#          cadre « Composition multi-filtres » : combobox composition
#          (Mono/HOO/SHO/RGB/LRGB) ⇄ 4 lignes rôle+dossier (le remplissage
#          des rôles CONTRAINT la composition, la composition pré-remplit
#          les rôles), auto-détection du filtre par bouton (« 🔎 Détecter
#          les filtres » : mot-clé FITS FILTER du FITS le plus récent de
#          chaque dossier, alias graphies Ha/H-alpha/OIII/Red/Lum… via
#          role_de_filtre, override manuel ensuite), gains R/G/B (texte,
#          virgule acceptée, bornés 0..10, appliqués au composite À CHAUD
#          via _tick — aucune re-session nécessaire), radio « Canal L »
#          (si dossier L vide : L synthétisé = luminance du composite,
#          combine identité — OU composite dégradé en RGB), persistance
#          config (rôles/dossiers/gains/mode L, restauration tolérante).
#          Chaîne (décisions d'Alain, 18/09/2026) : un seul aligneur
#          PARTAGÉ (référence commune obligatoire), extraction du canal du
#          rôle APRÈS calib + filtre flou (mono tel quel ; CFA débayerisé →
#          canal dominant CANAUX_CFA : Ha→R, OIII→G+B, S2→R, L→luma),
#          normalisation LINÉAIRE par canal dans le composer (percentiles
#          + gains) PUIS étirement global existant inchangé ; cadre commun
#          d'intersection GLOBALE ; re-stack DÉSACTIVÉ en mode compo
#          (reporté v2, l'archive par rôle est en place). Nouveaux
#          sauvegardes : composite (bouton existant) + bouton « 💾
#          Enregistrer les canaux (par filtre)… » (un canal_<rôle>.fit
#          linéaire recadré par rôle) ; ligne « Canaux : Ha: 12 · O3: 9 »
#          dans les stats. Tests _test_composition_jalon19.py,
#          _test_multifolder_jalon19.py, _test_compo_worker_jalon19.py,
#          _test_compo_ui_jalon19.py.
# v2.7.0 : JALON 18 — RE-STACK VISIBLE (UX). Retour réel d'Alain sur le
#          jalon 16 : « on est ok, pas simple de voir le restack » — le
#          message sur la ligne d'alignement était discret et vite écrasé
#          par la frame suivante. Décision d'Alain : chantier COMPLET.
#          Livré : ligne d'état DÉDIÉE « Re-stack : … » dans le cadre
#          Empilement (sous le bouton, avec bouton « ⓘ »), toujours
#          visible et JAMAIS écrasée — grise (aucun / en cours), VERTE
#          (re-stack réussi), AMBRE (échec : lecture archive / forme
#          différente) ; horodatage HH:MM:SS ; GAIN affiché (frames
#          récupérées vs l'ancien empilement « +N vs avant », et rapport
#          du score de la nouvelle référence à l'ancienne « ×1.50
#          (100 → 150 étoiles) », ou « réf. précédente non mesurée ») ;
#          compteur « Re-stacks (session) : N » dans les stats (ligne
#          seulement si N > 0) ; bouton « ⓘ » → historique horodaté de la
#          session (fenêtre modale, plus récent en premier, plafond
#          RESTACK_HIST_MAX = 12). Implémentation : app._noter_restack
#          (thread worker, attributs simples ; affichage par
#          _update_status dans le thread Tk) + app._montrer_restack_hist ;
#          _do_restack note SUCCÈS et ÉCHECS (« re-stack impossible ») et
#          affiche un état « en cours » immédiat — un échec ne compte PAS
#          dans le compteur ; état de session neuve à chaque « ▶
#          Démarrer ». Le message de la ligne d'alignement reste INCHANGÉ
#          (test jalon 16 inchangé). Test _test_restack_visu_jalon18.py.
# v2.6.0 : JALON 17 — FILTRE ANTI-BRUTES TRÈS DÉFOCALISÉES (AVANT
#          l'empilement). Constat réel d'Alain après le jalon 15 : « ça a
#          l'air OK sauf sur des brutes très défocalisées » — elles passaient
#          l'alignement (les triangles s'y retrouvent) mais dégradaient
#          l'empilement. DÉCISION d'Alain : rejet AUTOMATIQUE d'office + case
#          pour désactiver (« Rejeter les frames floues (auto) », cadre
#          Empilement, config `rejeter_flou` — booléen explicite). MÉTHODE :
#          chaque frame calibrée est mesurée à l'arrivée avec
#          `stars.mesurer_seeing` (jalon 10, ~15 ms) → (FWHM médiane, nb
#          d'étoiles) ; app._score_qualite + app._filtre_floue ; comparaison
#          RELATIVE à la médiane des frames gardées (≥ FLU_MIN_REF = 3 avant
#          tout rejet, jamais de rejet sur mesure impossible) : FWHM >
#          FWHM_MARGE = 2× la médiane (et > FWHM_ABS_MIN = 3 px absolus —
#          rien à rejeter en très courte focale), OU score étoiles effondré
#          (< FLU_NB_FRAC = 0,5× la médiane) combiné à une FWHM dégradée
#          (> 1,25×) ou non mesurable — seul il pourrait refléter un simple
#          changement de champ (dossier mixé) ; si AUCUNE frame gardée n'a
#          d'étoiles (nébulosité, champ pauvre), rien n'est jamais rejeté.
#          Une frame rejetée n'est NI archivée NI empilable (donc jamais
#          ramenée par un re-stack) ; compteur « Frames floues rejetées : N »
#          dans les stats + motif sur la ligne d'alignement. Test
#          _test_jalon17_filtre.py.
# v2.5.0 : JALON 16 — RE-STACK SUR LA MEILLEURE RÉFÉRENCE (étape 3 « à la
#          Siril »). Retour réel d'Alain après le jalon 15 : « ça a l'air OK
#          sauf sur des brutes très défocalisées » (un filtre qualité reste
#          à faire, noté dans AVANCEMENT.md) → on enchaîne le point 3.
#          Chaque brute archivée (jalon 15) reçoit un SCORE qualité = nb
#          d'étoiles détectées sur le canal vert (app._score_frame ; une
#          brute défocalisée en détecte peu — les étoiles larges sortent des
#          critères de forme — donc le score la pénalise déjà). DÉCLENCHEURS
#          : AUTO si la meilleure brute bat nettement la référence courante
#          (marge RESTACK_MARGE = 1,5×, au-delà de RESTACK_MIN_FRAMES = 5
#          frames archivées, avec cadence RESTACK_CADENCE = 10 entre deux
#          re-stacks) — utile surtout quand l'ancre initiale était médiocre ;
#          et MANUEL via le nouveau bouton « ⟳ Re-stacker (meilleure
#          brute) ». EFFET (_do_restack, thread worker) : re-ancre
#          l'alignement sur la meilleure brute ET RECALCULE TOUT
#          l'empilement depuis l'archive — les frames qui avaient REFUSÉ
#          avec l'ancienne référence ont une seconde chance (c'est le but) ;
#          l'ancre est ajoutée telle quelle (identité), les autres sont
#          ré-alignées par la cascade jalon 15. Les réglages du stacker
#          (k, méthode de rejet, fenêtre, équilibrage) sont conservés.
#          Toute substitution de référence passe par _definir_reference,
#          qui mesure aussi le score de la référence (seuil du déclencheur).
#          UI : bouton dans le cadre Empilement + message « re-stack N/M
#          frames · réf. = brute #i (S étoiles, auto|bouton) » sur la ligne
#          d'alignement. Test _test_restack_jalon16.py.
# v2.4.0 : JALON 15 — ALIGNEMENT « À LA SIRIL » (canal vert + triangles) et
#          ARCHIVE des frames calibrées. Constat réel d'Alain (17/09/2026) :
#          des brutes que SIRIL empile sans problème sortent de AVAStack avec
#          étoiles dédoublées et refus en masse. Causes traitées : Siril
#          aligne sur le canal VERT de la brute CFA (pleine résolution, zéro
#          interpolation) et apparie les étoiles de façon GLOBALE (similitude
#          de triangles, esprit astrometry.net), alors que nous alignions sur
#          la MOYENNE RGB après débayerisation et exigions une continuité de
#          translation (±40/100 px) — un dithering de NINA, une reprise de
#          session ou une autre nuit (dossiers mixés) faisait tout refuser.
#          ALIGNEMENT (alignment.py) : (1) TOUS les chemins travaillent sur
#          le canal VERT (couleur) ou l'image telle quelle (mono) —
#          canal_alignement() ; (2) NOUVEAU chemin TRIANGLES entre ORB et le
#          vote de centroïdes : triangles canoniques des plus brillantes
#          (apex + base ordonnée par distance à l'apex → deux rapports de
#          côtés invariants), paires candidates par tolérance sur les
#          rapports, transformation exacte candidate scorée sur la liste
#          complète des étoiles, consolidation RANSAC + LMEDS + contre-test
#          d'appariements mutuels — SANS fenêtre de continuité ; les
#          garde-fous échelle/angle restent, la phase reste le repli des
#          champs sans étoiles. ARCHIVE (nouveau module
#          processing/framestore.py, décision d'Alain : le futur re-stack
#          relira TOUJOURS ce dossier local, jamais le NAS) : chaque frame
#          calibrée est écrite en FITS float32 dans un dossier temporaire de
#          session, dans TOUS les modes ; garde-fous : 1 frame/s max
#          (webcams), plafond 20 Go, échec d'écriture → archivage arrêté et
#          message exposé (jamais de panne silencieuse) ; dossier supprimé à
#          la fermeture de session. UI : ligne « Archive (re-stack) : N ».
#          Le re-stack LUI-MÊME (meilleure référence + recalcul complet)
#          reste À FAIRE (étape 3) — tout est en place. Test
#          _test_align_jalon15.py.
# v2.3.9 : CORRECTION (constat réel d'Alain, 17/09/2026, jalon 14) — la
#          chaîne de TRAITEMENT EXTERNE (« Traiter l'empilement courant »)
#          plantait GraXpert dès la 1re étape sur un empilement RGB
#          (Uranus-C Pro) : boîte modale cx_Freeze « cv2.error …
#          !dsize.empty() in function 'cv::hal::resize' » (appelée par
#          background_extraction.py). C'est EXACTEMENT le piège de la
#          convention d'axes FITS diagnostiqué le 14/09/2026 : le lecteur
#          FITS de GraXpert suppose les canaux sur NAXIS3 ((C, H, W) côté
#          astropy) alors que save_image écrit (H, W, C) → NAXIS1=3. La
#          parade (écrire canaux-en-tête + retransposer la sortie) existait
#          DÉJÀ dans le chemin GraXpert LIVE (external/live.py, jalons 4/9)
#          mais n'avait JAMAIS été répercutée sur la chaîne externe — le
#          mono 2D n'étant pas concerné, le défaut est resté invisible
#          jusqu'au passage en couleur. Leçon (proposée à Alain) : une
#          parade documentée dans UN chemin doit être vérifiée dans les
#          AUTRES chemins qui partagent le même outil externe.
#          CORRECTIONS dans _run_external (avastack/ui/app.py) :
#          (1) le FITS d'entrée de la chaîne est écrit canaux-en-tête
#          (external.live._ecrire_entree) ; (2) après CHAQUE étape, la
#          sortie est normalisée ((3, H, W) → (H, W, 3)) puis réécrite
#          canaux-en-tête pour l'étape suivante — chaque outil reçoit la
#          même convention, quelle que soit celle de son prédécesseur ;
#          (3) l'étape de débruitage local lit normalisé et réécrit
#          canaux-en-tête ; (4) la lecture finale est normalisée avant
#          auto_unflip. En plus : le lanceur « survivable » (piège
#          subprocess + boîte modale cx_Freeze, documenté le 14/09) remplace
#          subprocess.run(capture_output) — sorties dans un fichier, kill de
#          l'arborescence au délai : un outil qui plante ne bloque plus
#          jamais la chaîne (message d'erreur + état error). Le mono 2D est
#          inchangé (les helpers ne transposent que le RGB).
#          Test _test_ext_rgb_jalon14.py (faux outils externes réels :
#          convention vue par les outils, chaîne RGB complète avec
#          débruitage local en mémoire, outil qui plante, mono inchangé).
# v2.3.8 : JALON 13 — ALIGNEMENT ROBUSTE + ÉQUILIBRAGE DES CANAUX (constat
#          réel d'Alain, 17/09/2026 : nouveau setup couleur Uranus-C Pro sur
#          C8 + réducteur 0,63 → 1280 mm ; sur NGC7023/NGC4565 les étoiles
#          sortent « en plusieurs points puis en trainées », 26/75 frames non
#          alignées, image très verte).
#          DIAGNOSTIC sur de vraies frames (_diag_align_1200.py, 19 FITS) :
#          (1) l'ORB ne s'apparie PLUS à cette focale — 0-6 appariements sur
#          1000 points-clés, MÊME entre frames d'une même nuit (il marchait
#          à 243 mm sur des champs riches en étoiles) ; (2) le repli
#          corrélation de phase renvoyait (0,0) PENDANT que le champ dérive
#          réellement (~90 px/h, mesuré par les centroïdes : (−15,+10) →
#          (−48,+77) px) et se déclarait TOUJOURS « confiant » → toutes les
#          frames empilées à l'identité = étoiles dédoublées puis trainées ;
#          (3) les RA/DEC d'en-tête sont des coordonnées MONTURE (stables)
#          et ne voient pas la dérive de l'image (flexure/erreur périodique).
#          ALIGNEMENT (alignment.py) en CASCADE : ORB (inchangé, excellent à
#          petite focale) → NOUVEAU repli par CENTROÏDES D'ÉTOILES
#          (stars.detecter_positions, calibré sur un balayage de paramètres
#          fait sur les 17 frames réelles : 60 étoiles les PLUS BRILLANTES
#          seulement — les étoiles saturées ont de mauvais centroïdes et
#          les objets faibles dispersent le vote ; vote de translation BRUT
#          sans lissage, recentré sur la moyenne des paires du bin vainqueur ;
#          sélection ±3 px ; RANSAC affine 2,5 px ; CONTRE-TEST
#          d'appariements mutuels ≤ 2,5 px, seuil 6 avec prédiction et 8
#          sans — un pic parasite auto-consistant du vote peut réunir 6
#          coïncidences, rarement 8 ; continuité : fenêtre de vote ±40 px
#          avec prédiction, ±100 px au 1er alignement) → corrélation de
#          phase DEVENUE HONNÊTE (fenêtre de Hann + retrait de la médiane ;
#          acceptée SEULEMENT si la SSD s'améliore ≥ 10 % et |Δ| ≤ 40 px,
#          sinon frame REFUSÉE au lieu d'empilée à l'identité). Garde-fous
#          communs : échelle [0.9, 1.1], |angle| ≤ 10°. Normalisation 8 bits
#          PARTAGÉE référence/frame (bornes de la référence) : une
#          normalisation indépendante rendait les étirements incohérents dès
#          qu'une frame a des bords non couverts (SSD insensible à la bonne
#          translation). BILAN SUR LES VRAIES FRAMES : 14 frames sur 17
#          retrouvées à ≤ 2,6 px de la dérive vraie (la plupart ≤ 0,5 px,
#          dérive mesurée (−9,+7) → (−48,+77) px en 35 min), 2 refus,
#          empilement final 77 étoiles · FWHM 2,71 px · ellipticité 0,05
#          (étoiles nettes et rondes) ; le lissage gaussien du vote était
#          NUISIBLE (3 réussites contre 14).
#          RÉFÉRENCE (app.py) : rafraîchissement AUTOMATIQUE toutes les N
#          frames (défaut 20, combobox « Rafraîchir la référence (frames) »,
#          « jamais » = ancien comportement) OU dès ≥ 50 % de frames
#          refusées (≥ 3) — la référence devient l'empilement courant SANS
#          recadrage (nouveau `mean(recadre=False)`) pour rester dans le
#          MÊME repère ; le bouton « Réf. = empilement » avait le BUG
#          INVERSE (il fournissait l'empilement RECADRÉ : chaque clic
#          décalait silencieusement l'empilement de (y0, x0)). Ligne d'état
#          « Align. : Δ=(…) · θ(…) · méthode » ajoutée aux stats d'empilement.
#          COULEUR (stacking.py) : « Équilibrage des canaux (auto) » (case +
#          force, config `wb_auto`/`wb_force`) — gains LINÉAIRES par canal
#          égalisant le FOND (20e percentile de la zone recadrée ; la
#          couleur des objets est préservée), cible = moyenne géométrique
#          des trois fonds, gains bornés [0.25, 4] ; appliqué à la SORTIE de
#          l'empilement (affichage, histogramme, sauvegardes, traitements),
#          mis en cache par (n, force, cadre). Case cochée par défaut.
#          stars.py : `detecter_positions()` (centroïdes pondérés par
#          l'intensité, tri par éclat décroissant) — même 1re étape de
#          détection que `mesurer_seeing`, sans la mesure de profil.
#          Test _test_align_jalon13.py (42 vérifications) ; les 17 tests
#          existants repassent.
# v2.3.7 : JALON 12 — NETTETÉ LIVE CÂBLÉE (Richardson-Lucy en direct).
#          Nouveau cadre « Netteté live (Richardson-Lucy) », INDÉPENDANT du
#          moteur d'étirement (demande d'Alain) : la netteté s'applique AVANT
#          l'étirement en STF/manuel comme en VeraLux. Case à cocher + curseur
#          d'ITÉRATIONS (1 à 10, défaut 5, « 3-5 = réglage utile ») et
#          étiquette d'état qui dit l'état RÉEL (active + provenance de la
#          PSF / refusée avec la raison / ignorée en vue « traitée »).
#          Position dans la chaîne : APRÈS le débruitage (on lisse d'abord, on
#          restaure ensuite), AVANT l'étirement.
#          DEUX CHEMINS, MÊMES RÉGLAGES ET MÊME MODULE : en mode VeraLux la
#          netteté est la dernière étape du solveur existant (elle y est donc
#          bien APRÈS GraXpert/débruitage : gradient → débruitage → netteté →
#          étirement) ; en STF/manuel, un second solveur DÉDIÉ (thread, dernier
#          job gagnant) la calcule sur l'aperçu, l'UI affichant l'image
#          d'attente NON nette — jamais bloquée. Le résultat mémorise l'objet
#          image déconvolué : jamais l'image nette d'un AUTRE empilement à
#          l'écran ; un REFUS est mémorisé lui aussi (sinon chaque tick d'UI
#          resoumettrait un job refusé, 30 fois par seconde). Les DEUX chemins
#          enveloppent l'appel du module d'un try/except : le module ne lève
#          jamais (contrat), mais un thread solveur MORT figerait l'aperçu pour
#          toujours — repli sur l'image non nette + raison remontée.
#          LA PSF EST CELLE DU SEEING MESURÉ (jalon 10) : la mesure du thread
#          d'acquisition est transmise au solveur (`vl_seeing`) — aucune 2e
#          détection d'étoiles, et la netteté suit le seeing réel de la nuit.
#          « 💾 tel que vu » reproduit la netteté en PLEINE RÉSOLUTION avec une
#          PSF MESURÉE sur le fichier (celle du live est exprimée en pixels de
#          l'APERÇU, réduit sur gros capteur : la réutiliser fausserait la
#          déconvolution du fichier).
#          Persistance : `vl_sharp` (booléen explicite) + `vl_sharp_iterations`
#          (entier ; hors [1, 10] → défaut 5, jamais de valeur bricolée en
#          silence). Vue « traitée » = netteté ignorée (même règle que
#          GraXpert/débruitage live : l'image a déjà subi le traitement
#          externe). Le job du solveur VeraLux passe de 5 à 6 éléments (les
#          réglages de netteté en dernier) → _test_denoise_live_jalon9.py mis à
#          jour. Test _test_sharp_live_jalon12.py (66 vérifications : fenêtre
#          réelle + solveurs réels) ; les 16 tests existants repassent au vert.
# v2.3.6 : JALON 11 — NETTETÉ LIVE, MODULE RICHARDSON-LUCY (module SEUL,
#          sans UI : le câblage live — case, curseur, cache du solveur,
#          « tel que vu », config — est le jalon 12). Nouveau module
#          avastack/processing/sharpness.py (numpy/OpenCV, AUCUNE dépendance
#          nouvelle — comme denoise.py et stars.py) : déconvolution de
#          Richardson-Lucy sur la seule LUMINANCE (couleur : le gain obtenu
#          est ré-appliqué aux 3 canaux → chromaticité intacte, aucun
#          artéfact couleur, comme SharpCap), PSF gaussienne ISOTROPE dont
#          le σ vient de la FWHM MESURÉE par stars.mesurer_seeing (jalon 10)
#          via stars.sigma_depuis_fwhm : la netteté suit le seeing réel de
#          la nuit, sans réglage à trouver. 3-5 itérations = réglage utile,
#          ITERATIONS_MAX (10) en plafond DUR. Refus EXPLICITE (image d'ENTRÉE
#          renvoyée inchangée + raison affichée) si moins de stars.MIN_ETOILES
#          (3) étoiles mesurables, si la PSF est hors bornes (« étoiles ~1 px :
#          ringing ») ou si un paramètre est invalide — jamais de no-op
#          silencieux, jamais d'exception (mêmes conventions que
#          denoise.denoiser / stars.mesurer_seeing).
#          MESURES DU MODULE (40 étoiles de FWHM VRAIE 3,00 px, bruit 0,006,
#          800×1200 px) : FWHM mesurée 2,91 px → 2,38 / 1,84 / 1,48 px à
#          3 / 5 / 10 it (63 / 75 / 105 ms) ; pic d'une étoile isolée ×2,35
#          avec FLUX conservé à ×1,000 (photométrie) ; PSF fausse de ±35 %
#          toujours tolérée, SANS halo sombre (le mode d'échec mesuré de
#          Wiener, −0,102 du pic, qui l'a fait écarter).
#          Deux CONSTATS DE MÉTHODE : (1) le « bruit ×1,22 » du banc d'essai
#          du 16/09 n'est PAS du bruit de fond — mesuré sur le fond (MAD) et
#          en hautes fréquences (starlet), RL ne dégrade rien (×0,92 à 5 it) ;
#          ce qui monte est le CONTRASTE des pics d'étoiles (écart-type
#          GLOBAL ×1,32) → c'est l'amplitude des étoiles qu'il faut
#          surveiller, pas le fond ; (2) le module est validé CONTRE une RL
#          de référence écrite en numpy pur (convolution 2D explicite, bords
#          réfléchis) : écart relatif < 1e-5 à 1, 3, 5 et 10 it — garantie
#          que c'est bien LA formule de Richardson-Lucy qui est appliquée.
#          Test _test_rl_jalon11.py (43 vérifications, headless) ; les 15
#          tests existants repassent au vert.
# v2.3.5 : JALON 10 — SEEING LIVE (détecteur d'étoiles, prérequis de la
#          netteté Richardson-Lucy). Nouveau module
#          avastack/processing/stars.py (numpy/OpenCV, AUCUNE dépendance
#          nouvelle — comme denoise.py) : fond/bruit par médiane/MAD, seuil
#          à 8σ, composantes 8-connexes, rejets (aire, bords, ellipticité),
#          puis PROFIL RADIAL par étoile → FWHM = 2 × rayon de retombée à
#          mi-hauteur ; médianes du champ = FWHM et ellipticité. Constat du
#          16/09/2026 : l'ORB de StarAligner n'est PAS un détecteur
#          photométrique — ce module est le prérequis manquant.
#          UI : étiquette « Seeing (FWHM) : x.xx px · N étoiles » dans le
#          cadre Empilement, mesurée sur l'APERÇU (≤ 1600 px, la résolution
#          où travaillera la netteté live) toutes les 3 s par le thread
#          d'acquisition ; mesure sur moins de 3 étoiles signalée
#          « (peu fiable) », et JAMAIS de silence (la raison est affichée).
#          Jalon « observation seule » : aucun réglage, aucune
#          persistance, RIEN n'est modifié dans l'image empilée.
#          Test _test_stars_jalon10.py (27 vérifications, fenêtre réelle
#          incluse) : FWHM mesurée à 3 % de la vraie sur étoiles
#          synthétiques (σ 1,2 et 1,8 px), 40/40 détectées, rejets
#          vérifiés (étoile filée, nébulosité σ 12 px, objet au bord, pixel
#          chaud) ; les 14 tests existants repassent tous au vert.
#          PIÈGES consignés (2 échecs du 1er essai) : (1) fenêtre de mesure
#          FIXE → FWHM surestimée de 170 % (le bruit du fond pèse alors
#          autant que les ailes de l'étoile) → fenêtre ADAPTÉE à la taille
#          apparente, fond retiré SANS clip, bruit annulé par la moyenne
#          par anneau ; (2) anneaux vides du profil radial (pixelisation)
#          → 45 % des étoiles perdues « sans retombée » → interpolation
#          vers le dernier anneau FINI au-dessus de la mi-hauteur.
# v2.3.4 : REMISE DU DÉBRUITAGE (demande d'Alain, 16/09/2026) — les jalons
#          7/8/9 (abandonnés le 15/09, code retiré, conservé dans le stash)
#          sont réintégrés RÉORGANISÉS selon la nature de chaque méthode :
#          - DÉBRUITAGE GRAXPERT IA → TRAITEMENT EXTERNE uniquement
#            (plusieurs MINUTES par image : jamais dans la chaîne live).
#          - DÉBRUITAGE LOCAL (ondelettes à trous / Non-local means,
#            numpy/OpenCV, aucune dépendance nouvelle) → disponible À LA
#            FOIS en traitement externe ET en live :
#            · traitement externe (jalon 8) : case « 2. Débruitage » +
#              combobox de méthode (GraXpert (IA, lent) / Ondelettes à
#              trous / Non-local means) + force commune 0..1. Les
#              algorithmes locaux tournent EN MÉMOIRE entre les étapes
#              subprocess (gradient → débruitage → BXT) ; BlurXTerminator
#              renuméroté « 3. ». Clés config : cmd_graxpert_dn, ext_dn,
#              dn_methode, dn_force.
#            · live (jalon 9) : cadre VeraLux — case « Débruitage live
#              (avant étirement) » + méthode (Non-local means, défaut /
#              Ondelettes à trous) + force 0..1. Dans le thread solveur,
#              APRÈS GraXpert live (même ordre que la chaîne externe) :
#              seuil k-sigma / force h AUTO-ADAPTÉS au bruit réel de
#              chaque empilement ; cache par (empreinte image après
#              gradient, méthode, force) ; échec = repli sans débruitage
#              + message, jamais bloqué. Vue « traitée » : désactivé
#              automatiquement (l'image y a déjà subi le traitement
#              externe — même règle que GX live). Clés config :
#              vl_denoise, vl_denoise_methode, vl_denoise_force.
#          - Sauvegarde « tel que vu » : reproduit le débruitage live en
#            PLEINE résolution (le fichier correspond à l'écran) ;
#            échec = sauvegarde abandonnée (comme GX live).
#          - Réintégration depuis le stash avec les correctifs anti-
#            « léopard » déjà éprouvés (ondelettes : 2 niveaux fins
#            seulement ; NLM : 2 passes faibles, h ≈ 0.8σ, petite
#            fenêtre) — rester DOUCE : à force utile, toute méthode
#            locale moutonne (cf. CLAUDE.md).
#          TEST RÉEL (Alain, 16/09/2026) : « pas top » dès que le retrait de
#          gradient est actif, « mieux mais pas parfait » sans → décision :
#          on GARDE le code tel quel, les cases restent DÉCOCHÉES (aucun
#          défaut modifié). Le fond « léopard » n'est donc PAS résolu, et un
#          constat nouveau est consigné : le débruitage se DÉGRADE après un
#          retrait de gradient (cf. CLAUDE.md → Pièges).
#          Tests : _test_dn_jalon7 (externe), _test_denoise_live_jalon9
#          (live), _test_dn_local_jalon8 (module).
# v2.3.3 : RECADRAGE AUTOMATIQUE À L'INTERSECTION (demande d'Alain,
#          16/09/2026) — l'empilement live est recadré à l'intersection
#          GÉOMÉTRIQUE RÉELLE des frames alignées (équivalent live du
#          `-framing=min` de Siril) : les coins de chaque frame sont
#          transformés par sa matrice d'alignement et l'intersection est
#          maintenue incrémentalement (Sutherland–Hodgman), avec marge de
#          sécurité de 3 px (l'interpolation « creuse » au ras des bords).
#          CAUSE (constat Alain) : les bords d'écart de recouvrement de
#          l'empilement — partiellement exposés, donc sombres — sont une
#          marche de fond pour GraXpert → « coussin » clair + signal
#          affaibli après background-extraction ; le recadrage manuel dans
#          Siril supprimait le problème. Le recadrage est appliqué à la
#          SOURCE (LiveStacker.mean()) : affichage, GX live, les 3
#          sauvegardes et le traitement externe en héritent d'un coup.
#          Statut live : « recadrée H×W ». Test _test_crop_intersection.py
#          (16 vérifications, headless) ; piège des axes de canaux traité
#          ((H,W), (H,W,3), (C,H,W)). Pas de case : automatique par défaut
#          (la demande d'Alain), M aberrante ignorée (jamais d'agrandissement).
# v2.3.2 : CORRECTION (constat Alain, 16/09/2026) — « 💾 Enregistrer
#          l'empilement (linéaire)… » ne faisait RIEN (aucun fichier, aucun
#          message, ni fin ni erreur) dès que plus aucune brute n'arrivait
#          (dossier surveillé terminé, caméra en pause). Cause : la demande
#          (save_request) n'était consommée par le thread d'acquisition
#          qu'APRÈS l'empilement d'une NOUVELLE frame — sans nouvelles
#          frames, le bloc n'était jamais atteint, en silence. Les deux
#          autres boutons de sauvegarde passaient par des threads dédiés
#          consommés AVANT la lecture de frame, d'où la différence. Fix :
#          la demande linéaire est désormais consommée au même endroit
#          (avant camera.read()), sur l'empilement courant — le fichier
#          correspond à ce qui était affiché au clic ; le message
#          « Empilement sauvegardé »/d'erreur de _tick s'affiche alors
#          fiablement. Test headless _test_save_lineaire_fix.py.
# v2.3.1 : Jalon 6, demande d'Alain AVANT son test réel — boutons « - »/« + »
#          sur TOUS les curseurs (_add_slider, avastack/ui/app.py) : réglage
#          fin sans viser à la souris. Un clic = ±1 pas du curseur (res),
#          recalé sur la grille (une valeur glissée à la main est réalignée) ;
#          clic MAINTENU = répétition (400 ms puis 80 ms) pour parcourir une
#          grande plage (exposition 5-1000 ms) sans cliquer 200 fois ;
#          annulation au relâchement/à la sortie du bouton, clamp aux
#          bornes, callback du curseur appelé exactement comme un
#          déplacement (rien d'autre ne change). Test UI
#          _test_sliders_jalon6.py (9 vérifications, fenêtre réelle).
# v2.3.0 : JALON 6 de l'intégration VeraLux (finitions) :
#          - REJET DES SATELLITES : LiveStacker (avastack/processing/
#            stacking.py) propose deux méthodes — « kappa » (kappa-sigma
#            séquentiel historique, STRICTEMENT inchangé) et « winsorized » :
#            adaptation au live stacking du Winsorized Sigma Clipping de
#            PixInsight — chaque frame est comparée à la MÉDIANE et au MAD
#            (sigma robuste = 1,4826×MAD) d'une fenêtre glissante des
#            dernières frames alignées (défaut 8, réglable 4-16) ; REJEU DU
#            WARMUP : quand la fenêtre se remplit pour la 1re fois
#            (elle contient alors toutes les frames), l'accumulation est
#            reconstruite avec les poids robustes — une trace passée pendant
#            le warmup est effacée, pas seulement diluée (le kappa cumulé
#            gonfle sigma pour toujours et masque ensuite les traces
#            faibles aux mêmes pixels) ; set_rejet() change méthode/fenêtre
#            à chaud sans perdre l'accumulation ; traitement par bandes de
#            lignes (_CHUNK_PX) pour borner la mémoire des temporaires.
#            UI (cadre Empilement) : combobox « Méthode de rejet »
#            (kappa-sigma / Winsorized satellites) + « Fenêtre de référence
#            (frames) » grisée en mode kappa. Test headless
#            _test_rejet_satellites_jalon6.py (21 vérifications ; scénario
#            poison : résidu kappa ~10e-3 vs winsorized ~0,01e-3).
#          - PERSISTANCE config.json : réglages VeraLux (moteur d'étirement,
#            mode de résolution du logD, fond visée, logD forcé, profil
#            capteur, GraXpert live) et d'empilement (kappa, méthode +
#            fenêtre de rejet), sauvegardés à la fermeture et restaurés au
#            démarrage (moteur VeraLux en dernier ; GX live seulement si la
#            commande est utilisable, sans popup) ; restauration TOLÉRANTE :
#            toute valeur inconnue/hors bornes laisse le défaut (config
#            corrompue = jamais de crash) ; booléens stockés
#            explicitement (True comme False). Test UI
#            _test_config_jalon6.py (sauver_config intercepté : le vrai
#            config.json n'est jamais touché par les tests).
# v2.2.7 : JALON 5 de l'intégration VeraLux (« 💾 Enregistrer tel que vu ») :
#          - avastack/processing/display.py : nouveau rendu_pleine_resolution()
#            — reproduit l'étirement affiché sur une image LINÉAIRE PLEINE
#            résolution (jamais l'aperçu 1600 px) : STF/manuel recalculé sur
#            l'image complète, VeraLux avec le DERNIER logD résolu (rendu
#            identique à l'écran, sans re-résolution ; repli target_bg si
#            aucun logD connu, repli STF/manuel si moteur absent), puis
#            gamma/saturation. Fonction PURE (aucun état partagé : pas de
#            stats EMA, pas de solveur, jamais black/white/gamma) — appelée
#            depuis un thread de travail. Refactor neutre : _calc_stats()
#            (stats STF sans lissage) et _gamma_saturation() (communs aux
#            deux chemins, rendu strictement identique à l'affichage).
#          - avastack/ui/app.py : bouton « 💾 Enregistrer tel que vu
#            (étiré)… » dans le cadre Sortie — vue « empilement » = chaîne
#            complète stack pleine résolution → GraXpert live si activé →
#            étirement → gamma/saturation ; vue « traitée » = proc_full
#            (résultat externe, déjà GraXpert/BXT) → étirement →
#            gamma/saturation. Réglages captés côté UI ; rendu + écriture
#            dans un thread dédié (comme _run_external), résultat consommé
#            par _tick (bouton grisé + messagebox, aucun appel Tk hors
#            thread UI). Échec GraXpert live = échec de la sauvegarde (pas
#            d'image « presque comme vue »). Le bouton d'enregistrement
#            linéaire reste inchangé.
#          - Retours d'Alain sur la 1re passe (corrigés dans la foulée) :
#            (1) GraXpert live ne s'applique plus QUE sur la vue
#            « empilement » — en vue « traitée » l'image a déjà subi le
#            traitement externe, le relancer (case laissée cochée) faisait
#            un DEUXIÈME traitement (_sync_vl_graxpert_vue, synchro dans
#            _tick/_on_view/_on_vl_graxpert, message explicite) ;
#            (2) combobox « Profil capteur » dans le cadre VeraLux
#            (avancé du jalon 6 demandé par Alain) — fait partie de la clé
#            des réglages, changement = re-résolution ;
#            (3) les réglages STF (case auto, coupure du bruit, fond,
#            black/white) sont regroupés dans un sous-cadre MASQUÉ en mode
#            VeraLux (ils n'ont aucun effet dans ce mode) ; gamma/saturation
#            restent visibles (communs aux deux moteurs).
#          - _test_save_asseen_jalon5.py : headless OK (STF pur =
#            process() au 1er rendu, aucune mutation d'état, manuel,
#            VeraLux logD forcé = etirer direct, fond cible = dernier logD
#            résolu, gamma/saturation, mono/RGB, repli moteur absent).
# v2.2.6 : JALON 4 de l'intégration VeraLux (GraXpert live, opt-in) :
#          - avastack/external/live.py : exécution du CLI GraXpert sur
#            l'APERÇU de l'empilement (FITS temporaire → commande configurée
#            {input}/{output}/{outbase} → relecture normalisée [0..1],
#            auto_unflip, contrôle des dimensions). Erreurs non fatales :
#            repli sur l'image brute + message.
#          - avastack/processing/display.py : le thread solveur enchaîne
#            stack → GraXpert → VeraLux quand vl_graxpert est True (ordre
#            photométrique correct, décision d'Alain) ; résultat GraXpert en
#            cache par CONTENU d'image (empreinte SHA-1) → bouger un curseur
#            VeraLux ne relance PAS GraXpert ; réglages GraXpert captés côté
#            UI dans le job (jamais lus depuis le thread) ; reset() vide le
#            cache ; erreurs "GraXpert live : …" affichées, étirement de
#            l'image brute en repli. BXT inchangé (manuel, bouton ⚡).
#          - avastack/ui/app.py : case « GraXpert live (avant étirement) »
#            dans le cadre VeraLux (refus + avertissement si la commande est
#            incomplète), synchro de la commande éditée dans _tick, label
#            d'état préfixé « GX ✓ · » quand le mode est actif.
#          - _test_graxpert_live_jalon4.py + _gx_factice.py : headless OK
#            (défaut inactif, chaîne appliquée, cache, erreur non fatale,
#            désactivation, reset, black/white intacts).
# v2.2.5 : JALON 3 de l'intégration VeraLux (mode target_bg + solveur par
#          frame) :
#          - avastack/processing/display.py : mode de résolution du logD
#            « target_bg » par DÉFAUT (le moteur résout lui-même le logD pour
#            amener le fond du ciel à la cible) ; nouveau notify_new_stack() :
#            la résolution est relancée à CHAQUE NOUVEL empilement (le rythme
#            des frames, ≥ 1 s, EST le cooldown — aucun calcul entre deux
#            frames, le worker ne garde que le DERNIER job, aucune file
#            d'attente) ; reset() vide aussi le cache VeraLux et force une
#            résolution au prochain rendu.
#          - avastack/ui/app.py : combobox « Résolution du logD : fond cible
#            (auto) / logD forcé » + curseur « Luminosité du fond visée »
#            (cible target_bg 0.10-0.45, recalcul immédiat via la clé) +
#            bouton « 🔒 Verrouiller le logD résolu »
#            (capte la dernière valeur résolue → calcul direct déterministe
#            et réactif ; 🔓 = retour à la résolution auto). Le nombre de
#            frames empilées est surveillé dans _tick pour déclencher
#            notify_new_stack() (le worker pousse ~20 im/s même sans nouvelle
#            frame : l'objet image seul ne peut plus déclencher de calcul).
#          - _test_veralux_jalon3.py : headless OK (défaut target_bg, fond
#            calé, aucun recalcul entre deux frames, dernier empilement
#            gagnant, verrouillage = déterminisme logD, reset, black/white
#            intacts).
# v2.2.4 : JALON 2 de l'intégration VeraLux (affichage, mode logD forcé) :
#          - avastack/processing/display.py : DisplayProcessor gagne un
#            mode "veralux" (opt-in, défaut "stf" STRICTEMENT inchangé).
#            Le calcul (~200 ms à taille aperçu) part dans un thread solveur
#            dédié (daemon) : résultat CACHÉ par image + clé de réglages ;
#            l'UI rend le dernier résultat terminé, fallback STF le temps du
#            1er calcul ; les jobs intermédiaires sont remplacés (jamais
#            empilés) → anti-blocage et anti-pompage. VeraLux n'écrit JAMAIS
#            dans black/white/gamma ; gamma/saturation communs appliqués
#            après, comme pour le STF. Flag vl_new lu par l'UI (aucun appel
#            Tk depuis le thread).
#          - avastack/ui/app.py : combobox « Moteur d'étirement : STF /
#            VeraLux » + cadre VeraLux (mode « logD forcé » seul au jalon 2,
#            slider logD 0-7, label d'état logD/fond/erreur). Repli STF +
#            message si le moteur tiers est introuvable.
#          - _test_veralux_jalon2.py : headless OK (fallback STF, cache,
#            recalcul logD, fond calé sur 0.20, black/white intacts, gamma,
#            RGB, retour STF).
# v2.2.3 : JALON 1 de l'intégration VeraLux (adaptateur, non câblé) :
#          - avastack/processing/veralux.py : import du moteur tiers
#            veralux_core_headless.py (GPL-3.0, JAMAIS modifié — racine du
#            projet déduite de __file__, pas du répertoire courant,
#            compatible installateur) ; API etirer(img, mode, ...) →
#            (image étirée, log_d, diagnostics) ; modes target_bg
#            (résolution auto du logD) et log_d (logD forcé, déterministe) ;
#            copie défensive + clip [0,1] en entrée (piège normalize_input :
#            float avec max > 1.1 → divisé par 65535) ; le moteur renvoie le
#            RGB en (3,H,W) → transposé en (H,W,3) ; mono (H,W) inchangé ;
#            repli silencieux sur Rec.709 si profil inconnu ; le module
#            reste importable même si le moteur tiers est absent
#            (MOTEUR_DISPONIBLE = False, RuntimeError à l'appel) ;
#          - _test_veralux_jalon1.py : test headless (mono, RGB, non
#            mutation, clip > 1.1, déterminisme logD, petite image, chrono).
#          Constat réel : « bug latent ligne ~276 » du tiers = FAUX POSITIF
#          (ligne apply_mtf complète). Chronos mesurés à 1600x1000 :
#          target_bg ≈ 264 ms, logD forcé ≈ 196 ms → l'étirement sera caché
#          par image (recalcul à chaque nouvel empilement, PAS à chaque tick
#          UI), slider logD « débouncé ».
# v2.2.2 : CORRECTION (constat Alain, run réel - 2026) : « Lecture impossible »
#          au chargement d'un master dark, et empilement dossier surveillé
#          muet (toutes les brutes comptées illisibles). Cause : OpenCV 5
#          REFUSE de débayeriser une image flottante (depth == CV_8U ||
#          CV_16U exigé) — or la devinette Bayer (_guess_bayer, chemin CFA
#          « Auto » sans BAYERPAT dans l'en-tête, cas des caméras mono comme
#          la QHYminiCam8M) passait une copie float32 à _debayer → exception
#          → fichier déclaré illisible. Bug latent depuis l'origine, révélé
#          par la mise à jour opencv-python 5.0.0. Correction dans
#          avastack/images.py :
#          - _guess_bayer : une image flottante (master dark/flat,
#            empilement, sortie outil externe) n'est jamais une brute Bayer
#            → traitée comme mono sans tenter la devinette ;
#          - _guess_bayer : la devinette débayerise l'image ENTIÈRE
#            d'origine (uint8/uint16), jamais la copie flottante.
#          Vérifié : master dark float32 + brutes uint16 N.I.N.A. chargent
#          et s'empilent. NB lancement Windows : utiliser `python
#          AVAStack.py` — `python3` désigne le Python du Microsoft Store
#          (hors venv) même avec le venv activé.
# v2.2.1 : qhyccd installe par defaut (etait en commentaire -> absent des
#          miniPC) [commit ef2e943, changelog non reporté ici].
# v2.2.0 : NOUVELLES CAMERAS TOUPTEK/ALTAIR + SVBONY (demande Alain, il
#          possede les deux) :
#          - avastack/cameras/touptek.py : ctypes sur toupcam.dll (SDK
#            officiel touptek.com), derive du wrapper NMGRL/toupcam
#            (Apache-2.0, Jake Ross). Couvre AUSSI les clones OEM (Altair
#            et autres marques revendant l'electronique ToupCam). Mode
#            "pull" evenementiel du SDK adapte a l'interface read()
#            synchrone de CameraBase (derniere frame + verrou + compteur).
#          - avastack/cameras/svbony.py : ctypes sur SVBCameraSDK.dll
#            (SDK officiel svbony.com), API quasi-clone de ZWO — derive des
#            wrappers MIT pysvbony (ssmichael1) / pysvb (olosnet).
#          Sources 'Touptek/Altair (SDK)' et 'SVBONY (SDK)' ajoutees au
#          menu (9 sources au total).
# v2.1.0 : NOUVELLES CAMERAS QHYCCD + PLAYER ONE (demande Alain, il possede
#          les deux) :
#          - avastack/cameras/qhy.py : via le paquet PyPI officiel `qhyccd`
#            (SDK natif inclus, `pip install qhyccd`) — NOUVELLE DEPENDANCE
#            OPTIONNELLE (ajoutee en commentaire dans requirements.txt) ;
#          - avastack/cameras/playerone.py : ctypes sur le SDK officiel
#            PlayerOneCamera.dll (telecharge sur player-one-astronomy.com),
#            derive du wrapper pyPOACamera.py (poa_view, Filipe Maia,
#            BSD-2-Clause) ;
#          - avastack/cameras/sdk_loader.py : chargement des SDK natifs
#            (variable d'env dediee AVASTACK_<MARQUE>_DIR, dossier projet,
#            PATH) — les SDK binaires proprietaires restent HORS du depot.
#          - Une seule classe par marque : N'IMPORTE QUELLE camera de la
#            marque (fiche lue sur la camera, rien en dur). Mono → 2D
#            (RAW16), couleur → RGB24 debayerise par la camera.
#          Sources 'QHY (SDK)' et 'Player One (SDK)' ajoutees au menu.
# v2.0.0 : REFACTORING MODULAIRE (demande Alain, préparation aux futures
#          fonctionnalités : nouvelles caméras à driver, nouveaux outils…) :
#          le fichier unique (~1500 lignes) est déplacé dans le package
#          avastack/ découpé par thème (cameras/, processing/, external/,
#          ui/). COMPORTEMENT IDENTIQUE — déménagement, pas réécriture.
#          Point d'entrée : AVAStack.py (lanceur fin) ou python -m avastack.
#          veralux_core_headless.py (tiers GPL-3.0) reste à la racine, tel quel.
# v1.1.0 : COMPATIBILITE MULTIPLATEFORME (demande Alain : Windows/Linux/macOS).
#          - Chemin Windows en dur de BlurXTerminator supprime : detection
#            automatique de GraXpert et rc-astro (variable d'environnement
#            AVASTACK_GRAXPERT / AVASTACK_RC_ASTRO, puis PATH, puis
#            emplacements d'installation courants selon l'OS).
#          - PERSISTANCE des reglages dans config.json (emplacement selon les
#            conventions de l'OS : %APPDATA%\AVAStack, ~/Library/Application
#            Support/AVAStack, ~/.config/AVAStack) : commandes des outils
#            externes (choisies via le bouton « ... » ou detectees), dossier
#            surveille, CFA, cases GraXpert/BXT, reglages d'etirement
#            (sigk/target/gamma/saturation). Plus rien a reconfigurer au
#            lancement suivant.
#          - Bibliotheque SDK ZWO selon l'OS (ASICamera2.dll /
#            libASICamera2.so / libASICamera2.dylib).
#          - Filtre de selection d'executable adapte a l'OS (bouton « ... »).
#          Aucune nouvelle dependance Python (json/sys/shutil : stdlib).
# v1.0.0 : RENOMMAGE (demande Alain) : AstroLiveStack → AVAStack (éviter la
#          confusion avec ALS - Astro Live Stacker). Fichier renommé en
#          AVAStack.py, titre de fenêtre, préfixe des dossiers temporaires
#          (avastack_), variable AVASTACK_VERSION créée (n'existait pas
#          auparavant malgré la convention CLAUDE.md).

