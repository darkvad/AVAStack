# AVANCEMENT.md — mémoire de travail à court terme

(Complète CLAUDE.md : état courant du développement et tâche en cours.
**Gardé LÉGER** (consigne d'Alain, 18/09/2026, cf. CLAUDE.md) : le
changelog détaillé des versions vit dans `avastack/__init__.py` — ici,
seul le DERNIER jalon reste détaillé ; les jalons et tâches terminés
antérieurs sont nettoyés à chaque nouveau jalon — leur trace durable est
dans le changelog du source et l'historique git.)

---

## État actuel

- **Version : AVAStack v2.7.0** (`avastack/__init__.py`,
  `AVASTACK_VERSION = "2.7.0"`), branche `master`. Dernier jalon livré :
  **JALON 18 « re-stack VISIBLE (UX) »** (17/09/2026) — réponse au retour
  réel d'Alain sur le jalon 16 (« on est ok, pas simple de voir le
  restack »), décision d'Alain : **chantier COMPLET**. Livré :
  ligne d'état DÉDIÉE « Re-stack : … » dans le cadre Empilement (juste
  sous le bouton, avec bouton « ⓘ »), toujours visible et JAMAIS écrasée
  par les messages de frames — **grise** (aucun / re-stack en cours),
  **verte** (re-stack réussi), **ambre** (échec : lecture archive /
  forme différente) ; horodatage HH:MM:SS ; **GAIN** affiché (frames
  récupérées vs l'ancien empilement « +N vs avant », et rapport du score
  de la nouvelle référence à l'ancienne « ×1.50 (100 → 150 étoiles) »,
  ou « réf. précédente non mesurée ») ; compteur « Re-stacks (session) :
  N » dans les stats (ligne seulement si N > 0) ; bouton « ⓘ » →
  historique horodaté de la session (fenêtre modale, plus récent en
  premier, plafond RESTACK_HIST_MAX = 12). Implémentation :
  `app._noter_restack` (thread worker, attributs simples) +
  `app._montrer_restack_hist` ; `_do_restack` note SUCCÈS et ÉCHECS et
  affiche un état « en cours » immédiat — un échec ne compte PAS dans le
  compteur ; état de session neuve à chaque « ▶ Démarrer » ; le message
  de la ligne d'alignement reste INCHANGÉ (test jalon 16 inchangé).
  Test `_test_restack_visu_jalon18.py` (30 vérifications) ; **les 23
  fichiers `_test_*.py` PASSENT**.
- **Base stable précédente : v2.6.0** (jalon 17). Validations réelles
  d'Alain les plus récentes : jalon 13 « empilement et couleur ok »,
  jalon 14 « l'appel d'outils externes fonctionne » (17/09/2026), jalon 16
  partiel (« on est ok, pas simple de voir le restack » → d'où le
  jalon 18). Historique complet : changelog du source + git.
- **Piège récent (jalon 18)** : Tk 9 / Python 3.14 —
  `ttk.Label.cget("foreground")` renvoie un `Tcl_Obj` NON comparable à
  une chaîne (`str()` obligatoire) ; le `tk.Label` classique renvoie déjà
  une `str`. Ajouté comme commentaire dans le test du jalon 18.

## ⏭ Prochaines étapes (validation réelle, prochaine nuit)

1. **Valider le jalon 18 en réel** : la ligne dédiée doit sauter aux
   yeux au re-stack (auto ET bouton) ; vérifier le gain affiché
   (frames + Δ score) sur un vrai re-stack.
2. **Anti-boucle sur dossier mixé** (reporté du jalon 16 ; le nouvel
   historique « ⓘ » du jalon 18 sert aussi de diagnostic) : vérifier
   qu'un re-stack AUTO ne part pas en boucle — le déclencheur exclut déjà
   l'ancre courante et exige la marge 1,5×.
3. **Jalon 17 à re-vérifier sur vrai ciel** : seuil 2× (FWHM) et
   comportement sur dossier mixé.

## Rappels utiles (court terme)

- **Tests** (PowerShell, venv) :
  `C:\Astro\astrolivestack\venv\Scripts\python.exe _test_xxx.py` — les
  23 fichiers `_test_*.py` doivent passer avant tout commit. Vérification
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
