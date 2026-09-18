# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version : AVAStack v2.8.0** (`avastack/__init__.py`,
  `AVASTACK_VERSION = "2.8.0"`), branche `master`. Dernier jalon livré :
  **JALON 19 « Composition multi-filtres » (RGB/HOO/SHO/LRGB)** — 4
  phases livrées les 18-19/09/2026. Live stacking de brutes prises avec
  des filtres différents (1 à 4 dossiers surveillés, un RÔLE = un filtre
  par dossier), composite temps réel. Source « Composition
  multi-dossiers » + cadre UI dédié (combobox composition ⇄ 4 lignes
  rôle+dossier, détection FITS FILTER + override manuel, gains R/G/B à
  chaud, radio « Canal L », config persistée) ; worker : un LiveStacker
  par rôle, aligneur partagé (référence commune), cadre commun
  d'intersection, normalisation linéaire par canal PUIS étirement global
  inchangé ; sauvegardes composite + par canal ; ligne « Canaux : … »
  dans les stats ; re-stack désactivé en mode compo (v2). Détails :
  changelog v2.8.0 du source + historique git. **Les 27 fichiers
  `_test_*.py` PASSENT.** **✅ Validé en réel par Alain le 19/09/2026 :
  le stack RGB fonctionne bien** (HOO/SHO/LRGB : même code, à
  confirmer sur narrowband).
- **Base stable précédente : v2.7.0** (jalon 18). Validations réelles
  d'Alain les plus récentes : **jalon 19 RGB « le stack RGB fonctionne
  bien » (19/09/2026)**, jalon 13 « empilement et couleur ok »,
  jalon 14 « l'appel d'outils externes fonctionne » (17/09/2026), jalon
  16 partiel (« on est ok, pas simple de voir le restack » → jalon 18).
  Historique complet : changelog du source + git.
- **Pièges récents (jalon 19)** : `var.get()` Tkinter interdit hors
  thread principal (bouchons `_Val` dans les tests) ; crash OpenCV
  5/OpenCL au teardown (`cv2.ocl.setUseOpenCL(False)`) ;
  `_sauver_config_app` travaille sur une COPIE de CONFIG
  (`c = dict(CONFIG)`) — dans les tests, intercepter `ui.sauver_config`
  et simuler `ui.CONFIG` (jamais toucher au vrai config.json, cf.
  `_test_config_jalon6.py`).

## 🔜 À faire — suite et validations du jalon 19

- **✅ VALIDÉ EN RÉEL par Alain (19/09/2026) : le stack RGB fonctionne
  bien** — source « Composition multi-dossiers », 3 dossiers R/G/B,
  composite temps réel. Le socle (détection FITS FILTER, empilement par
  rôle, cadre commun, étirement global sur le composite) est donc
  confirmé sur le vrai ciel ; HOO/SHO/LRGB utilisent le MÊME chemin
  (seule la table de composition change) — à confirmer quand même sur
  une vraie série narrowband la prochaine occasion.
- **Reportés v2 (assumés)** : re-stack multi-canal (désactivé en mode
  compo), darks/flats par filtre, STF par canal (opt-in), traitement
  externe = sur le composite.

## ⏭ Validations réelles en attente (nuits suivantes)

1. **Jalon 19 — variantes narrowband** : HOO (Ha+O3), puis SHO/LRGB si
   l'occasion se présente (même code que RGB, risque faible).
2. **Valider le jalon 18 en réel** : la ligne dédiée doit sauter aux
   yeux au re-stack (auto ET bouton) ; vérifier le gain affiché
   (frames + Δ score) sur un vrai re-stack.
3. **Anti-boucle sur dossier mixé** (reporté du jalon 16 ; l'historique
   « ⓘ » du jalon 18 sert aussi de diagnostic) : vérifier qu'un
   re-stack AUTO ne part pas en boucle — le déclencheur exclut déjà
   l'ancre courante et exige la marge 1,5×.
4. **Jalon 17 à re-vérifier sur vrai ciel** : seuil 2× (FWHM) et
   comportement sur dossier mixé.

## Rappels utiles (court terme)

- **Tests** (PowerShell, venv) :
  `C:\Astro\astrolivestack\venv\Scripts\python.exe _test_xxx.py` — les
  27 fichiers `_test_*.py` doivent passer avant tout commit. Vérification
  syntaxique systématique avant livraison : `python -c "import ast;
  ast.parse(open('AVAStack.py', encoding='utf-8').read())"`.
- **PIÈGE LANCEMENT** (voir aussi CLAUDE.md) : `python3` ne pointe PAS
  vers le venv — toujours lancer avec `python AVAStack.py`.
- **ORDRE DE LA CHAÎNE** (Alain, 16/09/2026 — ne pas l'oublier) :
  recadrage → gradient → débruitage → netteté → étirement. Le recadrage
  et le retrait de gradient ne sont pas des options.
- **Débruitage** : code gelé tel quel, cases décochées (décision du
  16/09/2026, test réel « pas top ») — ne pas retoucher sans nouvelle
  demande ; si le sujet est rouvert, le vrai chantier est l'interaction
  gradient × débruitage, pas la force.
- **Défauts livrés des traitements** (live = désactivé, NLM, force 0,5 ;
  externe = désactivé, GraXpert IA, force 0,5) confirmés par Alain :
  ne pas retoucher sans nouvelle demande.
- **CLAUDE.md — 2 leçons du jalon 13 PROPOSÉES le 17/09/2026, EN ATTENTE
  d'approbation d'Alain** (ne pas écrire sans accord explicite) :
  (1) contre-vérification par appariements mutuels des deux côtés + seuil
  relevé quand la décision sert d'ANCRE (sans prédiction) ; (2) deux
  normalisations indépendantes rendent une SSD aveugle — toute
  comparaison d'images doit partager les bornes de normalisation.
- **Prochaines vérifications de nuit** : suivre en direct la ligne
  « Align. : Δ(…) θ(…) méthode » et « Frames non alignées ».
- **Setup d'Alain** (17/09/2026) : C8 défourché + réducteur 0,63 →
  1280 mm ; Player One Uranus-C Pro (couleur, IMX585, 3856×2180, RGGB,
  GAIN 210) ; N.I.N.A. → dossiers
  `TargetSchedulerSequence/<cible>/<expo>/LIGHT` sur le miniPC — un
  dossier peut MÉLANGER plusieurs nuits (la 1re frame par mtime n'est pas
  forcément de la nuit courante).
