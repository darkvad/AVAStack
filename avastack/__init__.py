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

AVASTACK_VERSION = "2.14.0"

# --- Changelog (entrée la plus récente en premier) --------------------------
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

