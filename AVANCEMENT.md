# AVANCEMENT.md — mémoire de travail à court terme

(Complète `CLAUDE.md`, qui porte les leçons durables. Ici : état courant, décisions,
pièges actifs, prochaine action. Le détail daté vit dans `avastack/__init__.py`
(changelog) et `git log` — pas ici.)

---

## ⚠️ BRANCHE DE DÉVELOPPEMENT ACTIVE — NE PAS SUPPRIMER JUSQU'À DEMANDE EXPLICITE

**Branche : `LRGBHa`** (créée le 15/10/2026 à partir de `master`)

> **RÈGLE FERME — GRAVÉE DANS LE MARBRE** : jusqu'à nouvel ordre explicite,
> **TOUT** développement et **TOUTE** modification de code se font **EXCLUSIVEMENT**
> sur `LRGBHa`. `master` = branche stable, releases uniquement ; merge vers `master`
> seulement sur validation explicite (release).

Versions : `LRGBHa` = **v2.92.0** (①/②/③ validés en réel ; **136** halo coloré,
**137** neutralisation après étirement en STF, **141-B** interface, **J2** fusion
du Ha au rouge + continuum, **J3/J3bis** cinq modes, **J4/J4.1** continuum trois
méthodes et mesure indépendante de la case — tous **VALIDÉS EN RÉEL le 19/10** ;
**J5** ancre = couche large bande, **LIVRÉ, VALIDÉ EN RÉEL**) ·
`master` publié = **v2.80.0** · Store publié = **v2.71.1**.

**Gouvernance** : **aucune release GitHub sans l'accord d'Alain** ; **à CHAQUE jalon validé,
lui demander AVANT de démarrer le suivant** ; ne jamais déduire l'état d'une case de
`config.json` — on MESURE le fichier produit.

---

## Session du 19/10/2026 — **J5 LIVRÉ, VALIDÉ EN RÉEL, POUSSÉ** (v2.92.0)

### État actuel
- **v2.92.0 poussée sur `LRGBHa`** — **aucune release**. **J5** : dans un
  `+Ha`, l'ancre d'alignement **partagée** vient toujours d'une couche **large
  bande** ; une frame Ha ne crée plus l'empilement (attente + archive + rejeu
  dès la 1re large bande) et le Ha fusionné est **exclu** du re-ancrage.
- **VALIDÉ EN RÉEL (19/10)** : démarrage avec le dossier **Ha en premier** →
  « rejeu des brutes Ha (démarrage) · R 1/1 · Ha 1/1 » (ancre **R**) ; puis
  **re-stack manuel → 12/12** frames, aucune perte.
- **Bancs** : J5 vert (5 volets, 23 vérifications), non-régression
  19/20/129/129b/J2/J3/J4 verte, `ruff` propre, `pyright` 0.

### Décisions
- L'ancre d'un `+Ha` ne peut pas venir du Ha **parce qu'il ne se sert jamais de
  l'aligneur partagé** (voie A) — **pas** parce qu'il aurait peu d'étoiles
  (mesuré : 4 391, plus que G/B ; FWHM la plus fine, 2,46 px).
- Le score « meilleure brute » = **nombre d'étoiles** (plafond 200), pas une
  qualité : ne jamais s'en servir pour comparer des **filtres**. Un score FWHM
  serait un **jalon séparé** (il touche toutes les compositions).
- Quatre chemins posent l'ancre : ① repli et ④ rafraîchissement **verrouillés
  par le banc** ; ② création et ③ re-ancrage **fermés par le code**. Détail
  durable : `CLAUDE.md` § « Ancre d'alignement ».

### Fichiers modifiés (commit J5)
- `avastack/core/worker.py` (attente + rejeu), `avastack/ui/app.py` (exclusion
  du Ha des candidats), `bancs/_test_fusion_ha_jalon5.py`, `README.md`
  (section « Fusion du Ha »), `avastack/__init__.py` (2.92.0 + changelog),
  `CLAUDE.md`, `AVANCEMENT.md`.

### Problèmes ouverts
- **Bugs / irritants relevés par Alain en test** : **non encore détaillés** —
  il les fournira au début de la session suivante. **À corriger AVANT la
  release.**

### Prochaines étapes
1. **Lister puis corriger** les bugs/irritants du test (Alain).
2. **Release v2.92.0** sur accord explicite, une fois les correctifs faits.


---
## Points d'attention
- **TROIS noms de composition** (141-B) : `stacker.composition`/`_compo_nom`,
  `_compo_session`, `var_compo` ; **`"RGB+Ha"` est une sous-chaîne de
  `"LRGB+Ha"`** ⇒ jamais `startswith`/`in` pour identifier une composition.
- **J2 — fusion ACTIVE PAR DÉFAUT** : `fusion_ha = None` = défauts figés ;
  désactiver = `{"poids": 0.0}`. Le réglage entre dans la clé de mémoïsation et
  dans `disp.vl_compo`.
- **J2 — continuum** : actif par défaut, **case ET Q désactivés sans dossier
  R** ; l'échelle R est le DÉNOMINATEUR de normalisation du Ha (ne pas le
  remplacer par 1 sans regarder le mode de normalisation).
- **J3bis — les cinq modes ne touchent que le ROUGE** (V/B au bit) ;
  `ha_luminance` = gain **à porte** (0,05–0,25) : ne pas baisser la porte sous
  0,05 sans refaire la mesure.
- **Une brute est DITHÉRÉE** : seul un empilement ALIGNÉ prouve quelque chose ;
  `--dossier` sans `--dark` = run invalide dès que l'exposition change.
- **Un jeu SANS le défaut ne mesure que l'ABSENCE DE COÛT** : vérifier que le
  défaut est REPRÉSENTÉ (ex. retournements) avant de conclure « aucun coût ».
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`. Bancs UI :
  `cv2.ocl.setUseOpenCL(False)`, `ui.CONFIG = {}`, `ui.App._dire` patché
  (boîte MODALE, sinon blocage), jamais `grid` + `pack` dans le même conteneur.

### Contexte de reprise (à coller — 2 phrases)
Arbre **v2.92.0 poussé** sur `LRGBHa` : **J2 à J5 sont VALIDÉS en réel** (J5 :
ancre d'un `+Ha` toujours large bande, démarrage ancre R + Ha rejouée, re-stack
12/12 ; banc J5 et non-régressions vertes, `pyright` 0, **aucune release**).
**Prochaine action** : Alain liste les **bugs/irritants** vus en test, on les
corrige, **puis** release sur accord explicite.

---

## Chantier en cours — LRGB+Ha (jalons 129 → J5) — **J2 à J5 livrés ; J5 validé en réel**

Le rôle Ha **n'alimente aucun canal** : il est **FUSIONNÉ** au composite après le combine L.

| Jalon | Contenu | État |
|---|---|---|
| J1 / 129 (v2.81.0) | compositions + 5 lignes UI + séparation ancre / `_narrowband_ha` | commité |
| 129b | voie A (référence **PAR RÔLE** + recalage de l'empilement) + `profondeur_min` + refus par rôle | COMMITÉ ; validé en réel le 16/10 (441 frames, 2 refus en R) |
| **130 (v2.82.0)** | combine LRGB borné [0 ; 5] + repli local + fiche + banc neuf | COMMITÉ + POUSSÉ (`ef0c35c`) |
| **J2 (v2.88.0)** | fusion « ajout au rouge » + poids 1,0 + recentrage + **continuum (Q, case)** + cadre « Fusion Ha » | **VALIDÉ EN RÉEL le 19/10** |
| **J3bis (v2.90.2)** | les 4 opérateurs dans l'espace de R ; `ha_luminance` = gain **à porte** (0,05–0,25) ; `ajout_rouge` au bit | **VALIDÉ EN RÉEL (19/10)** |
| **J4 (v2.91.0)** | continuum **trois méthodes** (`bandes_passantes` 7/3 nm, `mediane`, `etoiles_5sigma`), **repli visible**, case « recentrer » | **VALIDÉ EN RÉEL le 19/10** |
| **J4.1 (v2.91.1)** | la **mesure** ne dépend plus de la case (fond de ciel), seuil médiane 1,20 | **VALIDÉ EN RÉEL le 19/10 (soir)** |
| **J5 (v2.92.0)** | ancre = couche **large bande** (une frame Ha ne crée plus l'empilement ; Ha exclu du re-ancrage) + doc README | **VALIDÉ EN RÉEL le 19/10** |

Plan figé (13 arbitrages du 15/10) : poids **1,0** (0–10) · α **0,5** · Q **0,80**
(0,10–2,00) · cadre « Fusion Ha » visible seulement si la compo contient Ha ·
continuum = **bandes passantes** (Ha 7 nm / RGB 100 nm), référence **R** ·
identifiants en français (`synthetise`).

---

## En attente / prochaine session (état au 19/10 — `LRGBHa`, v2.92.0)

- **J2 à J5 sont CLOS** (validés en réel le 19/10) : cinq modes de fusion,
  continuum à trois méthodes (repli VISIBLE, mesure indépendante de la case) et
  ancre d'un `+Ha` toujours large bande.
- **Prochaine action unique** : **corriger les bugs/irritants** relevés par
  Alain en test — **liste à fournir** (non détaillée à la clôture). **Rien ne
  part en release avant.**
- **Ensuite** : **release v2.92.0** sur accord explicite.
- **Optionnel** : cible qui REMPLIT le cadre (repli attendu et DIT) et filtre
  **3 nm** si Alain en a un.
- **Référence chiffrée** : `C:\Astro\test\M33_Canaux_LRGBHa` (5 `canal_*.fit` +
  fiches ; `AVACOMPO` = LRGB+Ha, **normalisation COMMUNE**, lissage 117d).
  Rejouer : `python bancs/_diag_fusion_ha_echelles.py --canaux <dossier>
  --norm-commune --lissage-halos --poids 1.5` (`--autotest` contrôle l'outil).
- **Ne pas retoucher** : `ajout_rouge` (AU BIT), la formule `bandes_passantes`
  7 nm, α, le poids, le principe « repli = bandes passantes AU BIT ».
- **141-B validée** (rien à retester) ; **teinte des COINS** notée, sans action.
- Retour arrière en un geste : `git checkout -- avastack/core/worker.py
  avastack/ui/app.py`.

---

## Setup d'Alain

- **Setup 1 (miniPC)** : QHY MiniCam8M (mono refroidie, roue intégrée) ; N.I.N.A. →
  `TargetSchedulerSequence/<cible>/<expo>/LIGHT` — un dossier peut MÉLANGER plusieurs nuits.
- **Setup 2** : C8 défourché + réducteur 0,63 (1280 mm) ; Player One Uranus-C Pro (couleur,
  IMX585, RGGB) sur monture DIY **Open Astro Mount** ; guidage SV305C sur 60/240.
- **Jeux de test (QHY + SV555)** : **M31** (L du 13/09 + R/G/B des 22-23/09, 60 s,
  −15 °C ; un dossier peut mêler les deux côtés du Pier) ; **M33** (nuit du
  10-11/10 : L 60×60 s, R/G/B 60-120 s) + un dossier **Ha de 40 frames**.
  Darks maîtres : 60 s (L/R/G), 120 s (B), 180 s (Ha).
- **Outils locaux** : Siril 1.4.4 (Gaia XP, base SPCC), ASTAP (D80 Gaia DR3) ; pas
  d'astrometry.net. **Ubuntu 26.04 LTS** : installateur éprouvé ; restent la
  machine VIERGE et le test matériel caméras (`--cameras`).

---

## Pièges récents (encore actifs — le reste est passé dans `CLAUDE.md`)

- **Un jeu SANS le défaut ne mesure que l'ABSENCE DE COÛT** : 109 frames sans
  retournement donnaient « retirer `phase` ne change rien » ; sur **Sh2-132**
  (204 frames, **31 retournements**), la phase finalisait 22 frames dont 21 Ha
  fausses de 1,1 à 2,3 px. Vérifier que le défaut est REPRÉSENTÉ (compter les
  |angle| > 170°, pas seulement les refus) avant de conclure.
- **Une réussite de repli n'est pas une preuve d'alignement** : `phase` en
  translation seule a posé 11/50 puis 12/49 frames B **à l'envers**. Un banc
  teste le **chemin de décision** (espion) et son coût sur une frame douce.
- **Échecs PRÉEXISTANTS** : `_test_espace_jalon72` (géométrie d'écran),
  `_test_reset_empilement_jalon76` [4] (course `_stop()`, sensible à la charge CPU).
- **Lancement** : `python AVAStack.py` (venv) — jamais `python3`.

---

## Clôtures précédentes

- **19/10/2026** : **J5 VALIDÉ EN RÉEL** (v2.92.0, poussé) — ancre d'un `+Ha`
  toujours large bande (démarrage ancre R + Ha rejouée ; re-stack 12/12) ;
  **aucune release**.
- **19/10/2026** : **J4/J4.1 VALIDÉS en réel** (v2.91.1) — trois méthodes de
  continuum, mesure indépendante de la case « recentrer ».
