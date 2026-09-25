# -*- coding: utf-8 -*-
"""Package AVAStack — live stacking (empilement temps réel).

Structure (refactoring v2.0.0, depuis le fichier unique AstroLiveStack.py /
AVAStack.py) :
  avastack.compat       — constantes multiplateforme (Windows/Linux/macOS)
  avastack.config       — persistance config.json
  avastack.images       — E/S image, débayerisation, utilitaires outils externes
  avastack.cameras      — sources d'images (simulée, dossier, OpenCV, ZWO)
  avastack.processing   — calibration, alignement, empilement, affichage
  avastack.external     — détection + enchaînement des outils CLI (GraXpert/BXT)
  avastack.ui           — interface Tkinter
Le point d'entrée reste AVAStack.py à la racine (python AVAStack.py),
ou python -m avastack.
"""

AVASTACK_VERSION = "2.37.3"

# --- Changelog (entrée la plus récente en premier) --------------------------
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

