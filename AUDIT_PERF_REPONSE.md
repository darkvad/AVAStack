# Réponse d'audit — performance et mémoire (reçue le 20/10/2026)

**Provenance** : modèle spécialisé en architecture logicielle, à qui Alain a soumis
`AUDIT_PERF_PROMPT.md`. Texte **conservé tel que reçu** (relu ensuite contre le
code : fichiers et lignes cités conformes).

**Statut** : **PROPOSITION**, aucune ligne de code écrite à ce titre. Les chiffres
cités viennent soit des bancs du dépôt (`bancs/_mesure_p5_reactivite.json`), soit
du calcul sur les buffers (`processing/stacking.py`). Seule la **Phase 0**
(instrumentation) est engagée ; les phases suivantes ne partent qu'après
**mesure** et **accord d'Alain** (gouvernance : demander AVANT chaque lot).

---

## Résumé exécutif (du modèle)

« L'analyse du codebase confirme les symptômes rapportés : **le vrai goulot est le
rendu synchrone complet sur le fil Tk à chaque frame reçue (≈300 ms/frame)**,
amplifié par une pression mémoire importante sur les accumulateurs float64 à
pleine résolution. Les optimisations de curseurs (P5) sont correctes et mesurées —
le problème restant est **structurel**, pas ponctuel. »

---

## 1. Où est le vrai goulot ? (classement par espérance de gain)

| Rang | Hypothèse | Espérance | Certitude | Preuve dans le code |
|------|-----------|-----------|-----------|---------------------|
| **1** | **(b) Rendu synchrone sur fil Tk à chaque frame** | **ÉNORME** (×10–×30) | **CERTAIN** | `_tick_corps()` : `if st["frames"] != self._vl_frames: self._rendre_et_afficher(show)` → rendu complet (250–320 ms) **sur le MainThread** |
| **2** | **(c) Copies/temporaires NumPy + pression mémoire** | **MAJEUR** (RSS 80 % de 32 Go) | **CERTAIN** | `LiveStacker` : 6 arrays float64 (`sum`, `sumsq`, `wsum`, `_moy`, `_sig`, `_dif`) + `_buf` float32 fenêtre 8 + `_pix`/`_masq` → **≈2,2 Go/canal à 26 Mpx** ; ×5 canaux = **>11 Go** |
| **3** | **(a) Contention CPU/GIL empilement ↔ Tk** | **MODÉRÉ** | **HYPOTHÈSE À MESURER** | `_en_parallele()` : N `threading.Thread` + `join()` — les ops NumPy libèrent le GIL, mais les bandes concurrencent le MainThread |
| **4** | **(d) Attentes des files bornées (maxsize=2)** | **FAIBLE** en conditions normales | **HYPOTHÈSE À MESURER** | `self.q = queue.Queue(maxsize=2)` + `except queue.Full: pass` — **perte silencieuse** si l'UI prend 300 ms/frame |
| **5** | **(e) Autre (histogrammes, annotation, VeraLux)** | **MINEUR** (45–53 ms) | **CERTAIN** | `_maj_histogrammes()` + tracé Canvas Tk — incompressible sans changer l'UX |

**Preuve décisive — le grain élémentaire** : le budget `_tick` de 30 ms est violé
à chaque frame (≈10× le budget). L'UI ne rend la main qu'entre deux frames — d'où
« l'interface répond quand le spinner n'est pas actif ».

---

## 2. Expériences de mesure reproductibles (SANS refonte)

**Protocole 1 — coût du rendu pur** (existant)
`python -m bancs._mesure_p5_reactivite --frames 50 --source simulee`
Chiffres : `t_rendu_total` (cible < 30 ms), `t_stretch`, `t_hist`, `t_draw`.

**Protocole 2 — contention GIL worker ↔ MainThread**
Accumuler `perf_counter()` autour de `_worker_empiler_frame` et de
`_rendre_et_afficher`. Chiffres : % temps worker vs % temps UI sur 100 frames ;
`threading.active_count()` pendant le rendu ; CPU % par fil.

**Protocole 3 — mémoire par composant**
`tracemalloc` avant/après `LiveStacker.reset()`, puis après 50 frames, plus RSS
(`perf.memoire_mo()`, sans dépendance). Chiffres : RSS repos / 10 / 50 / 100
frames ; `sum.nbytes + sumsq.nbytes + …` par stacker ; **nombre de stackers**.

**Protocole 4 — saturation de la file `q`**
Compter les `queue.Full` et la profondeur de file en fin de `_tick`.
Chiffres : taux de `Full` pour 100 frames ; `qsize` max observé.

**Protocole 5 — découpler affichage / frames**
Dans `_tick` : ne rendre que si `Δt > 1/30 s` **et** frame neuve. Chiffres :
fps UI effectif, latence frame→écran, rapports du Guet.

---

## 3. Architecture cible (mono-processus, Tkinter, pixels identiques)

Trois couches strictement séparées :

```
THREAD ① : ACQUISITION + EMPILEMENT (inchangé)
   - calibration, alignement, LiveStacker.add()
   - publie ÉTAT (dict st) + IMAGE LINÉAIRE dans q (maxsize=2, inchangé)
        │ q.get_nowait()
        ▼
THREAD ② : RENDU OFFSCREEN (NOUVEAU — daemon)
   - consomme q : (image linéaire, st)
   - DisplayProcessor.process(linéaire, live=True)   ← MÊME code, MÊME ordre
   - histogrammes calculés sur l'image RENDUE
   - produit un buffer PRÊT À DESSINER : uint8 (H,W,3) + les deux jeux de bacs
   - pousse dans q_rendu (maxsize=1, ÉCRASEMENT : le dernier gagne)
        │ q_rendu.get_nowait()
        ▼
THREAD ③ : MAINTHREAD TK (interface)
   - _tick 30 ms : seulement q_rendu.get_nowait() + _show_image
   - _show_image = cv2.resize(uint8) + PhotoImage (12–14 ms)
   - histogrammes : blit de bacs pré-calculés (_draw_hist ne recalcule rien)
   - ZÉRO calcul NumPy, ZÉRO étirement, ZÉRO histogramme ici
```

| Aspect | Actuel | Cible | Gain |
|--------|--------|-------|------|
| Fréquence de rendu | = fréquence des frames (1–10 Hz irrégulier) | **30 fps max, régulier** | UI fluide même à 1 frame/s |
| Étirement + histogrammes | MainThread (250–320 ms) | fil de rendu | MainThread **< 5 ms/tick** |
| Résolution de travail | 1600×1200 | **inchangée** (déjà optimale) | — |
| Transfert fil → fil | float32 (23 Mo) | **uint8 (5,7 Mo)** | ×4 moins de copie |
| Égalité des pixels | garantie (chemin unique) | **garantie** (`DisplayProcessor.process` inchangé, 1 appel/frame) | bancs verts |

**File `q_rendu` — producteur** : `put_nowait` ; si pleine, `get_nowait` (jeter
l'ancien) puis `put_nowait` → **aucune backpressure** sur l'empilement.
**Consommateur** : `get_nowait` ; `queue.Empty` ⇒ on garde l'affichage courant.

**VeraLux** : `_vl_worker` publie **déjà** `self.proc_show`. Le fil de rendu
consomme `proc_show` quand `view == "traitée"` : la chaîne lourde ne change pas,
seul le LIEU de l'étirement/affichage change.

---

## 4. Mémoire — réduire l'empreinte sans changer les résultats

### Empreinte actuelle (26 Mpx mono, 1 canal)

| Buffer | dtype | Taille | Total |
|--------|-------|--------|-------|
| `sum`, `sumsq`, `wsum` | float64 | 208 Mo chacun | 625 Mo |
| `_moy`, `_sig`, `_dif` | float64 | 208 Mo chacun | 625 Mo |
| `_pix` | float32 | 104 Mo | 104 Mo |
| `_masq` | bool | 26 Mo | 26 Mo |
| `_buf` (winsorized, fenêtre 8) | float32 | 833 Mo | 833 Mo |
| **TOTAL / canal** | | | **≈ 2,2 Go** |
| **×5 canaux (LRGBHa)** | | | **≈ 11 Go** |

### Optimisations, par risque croissant

1. **float32 pour les accumulateurs** (certain, ×2, risque faible) —
   `sum`/`sumsq`/`wsum` en float32. Preuve : banc bit-à-bit sur 100 frames
   déterministes ; tolérance 0 avec somme compensée.
2. **Somme compensée (Kahan-Babuška)** pour `sum` — conserve la précision du
   float64 en float32 ; 1000 frames, comparaison à la référence float64.
3. **Fenêtre glissante bornée** — `_buf` est déjà un buffer circulaire float32
   (copie memcpy) ; ne PAS passer en float16 (précision du MAD).
4. **Un seul `LiveStacker` par rôle ACTIF** (certain, ×N) — instanciation
   PARESSEUSE dans `CompositeStacker`, pas au démarrage : LRGBHa avec L+R actifs
   = 2 stackers au lieu de 5 (**–60 %**).
5. **Winsorized sans buffer de frames** (hypothèse, risque élevé) — médiane/MAD
   glissantes par chunk au lieu de 8 frames stockées : **–800 Mo/canal**, mais
   change les mathématiques de rejet ⇒ banc bit-à-bit obligatoire.
6. **Libération explicite** — `del` + `gc.collect()` dans `reset()` : marge OS
   (sous Linux/macOS le RSS ne redescend pas seul).

### Cible après 1+2+4

| Configuration | Avant | Après |
|---|---|---|
| 1 canal 26 Mpx | 2,2 Go | **≈ 550 Mo** |
| 5 canaux 26 Mpx | 11 Go | **≈ 1,1 Go** |
| 1 canal 8,3 Mpx | 700 Mo | **≈ 175 Mo** |

**Preuve d'égalité** : chaque changement passe par un banc qui génère 100 frames
déterministes (graine fixe), exécute l'ancien ET le nouveau code, et compare
`sum`, `sumsq`, `wsum`, `rejected_total` et l'image finale **bit-à-bit**
(`np.array_equal`) — accepté seulement à **0 différence**.


---

## 5. Ordre de mise en œuvre

| Phase | Contenu | Gain | Risque | Jours | Banc |
|---|---|---|---|---|---|
| **0** | Instrumentation (chronos par étage, compteurs de files pleines, RSS, octets des stackers) | visibilité | **nul** | **1** | `_test_phase0_perf.py` |
| **1** | Fil de RENDU OFFSCREEN + `q_rendu` (maxsize 1, écrasement) ; `_tick` ne dessine plus que l'image prête | **×30–×60** (300 ms → 5 ms/tick) | moyen | 3–4 | `_test_render_worker_bit_exact.py` |
| **2** | float32 + Kahan + instanciation paresseuse des stackers | **×4–×10** mémoire | faible | 2–3 | `_test_kahan_equivalence.py` |
| **3** | Winsorized en flux (seulement si RSS > 4 Go après 1+2) | –800 Mo/canal | élevé | 3–5 | `_test_winsorized_streaming_bit_exact.py` |
| **4** | Finitions (« frames sautées », pause du rendu si file vide) + tests réels | stabilité | faible | 2 | jeux M31/M33/Sh2-132 |

Critère d'acceptation de la Phase 1 : **0 rapport du Guet** sur 50 frames
simulées, `_tick` moyen < 5 ms, image finale **bit-à-bit** identique.

---

## 6. Risques de régression et parades

| Risque | Probabilité | Parade |
|---|---|---|
| Ordre des frames altéré | faible | `q.maxsize=2` inchangé ; `q_rendu` en écrasement = dernier gagne, aucune perte côté empilement |
| Désynchronisation VeraLux | moyenne | le fil de rendu lit `proc_show` (affectation atomique : contrat déjà en place) |
| Précision float32/Kahan | très faible | banc bit-à-bit sur 1000 frames + jeux réels |
| Interblocage `q_rendu` | nulle | `put_nowait`/`get_nowait` uniquement — jamais de `block=True` |
| Sécurité des fils sous macOS/Tk | faible | le fil de rendu ne touche **jamais** Tk : il ne produit que du NumPy |

---

## 7. Action immédiate retenue

**Phase 0 uniquement** : instrumentation dans `core/worker.py` et
`ui/app.py`/`ui/renderer.py` (durées par étage, taux de `queue.Full`, RSS, octets
d'accumulateurs), puis **rejouer** `_mesure_p5_reactivite.py` et relever le JSON
de référence. Aucune refonte avant ces chiffres.

---

## Annexe — points de code vérifiés dans le dépôt

- `avastack/ui/app.py::_tick_corps` — consommation de `self.q` (`get_nowait`) et
  appel `_rendre_et_afficher(show)` **par frame**.
- `avastack/ui/renderer.py::_rendre_et_afficher` — `_src_rendu` →
  `disp.process` → `_maj_histogrammes` → `_show_image` (4 étages mesurables).
- `avastack/ui/app.py::_pousser_rendu` — `self.q.put_nowait(...)` avec
  `except queue.Full: pass` (**perte silencieuse** à compter).
- `avastack/core/worker.py::_worker` — `self.q.put_nowait((show, st))`, même
  motif ; `time.sleep(max(0, 1/20 - dt))` en fin de tour.
- `avastack/processing/stacking.py::LiveStacker` — `_moy`/`_sig`/`_dif` float64,
  `_pix` float32, `_masq` bool, `_buf` float32 (fenêtre).
- `avastack/processing/composition.py::CompositeStacker.stackers` — un
  `LiveStacker` par rôle, dict public (comptage mémoire aisé).

