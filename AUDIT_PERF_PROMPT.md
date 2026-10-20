# Prompt d'audit — performance et mémoire d'une application de live stacking (Python/Tkinter)

> À coller tel quel dans un modèle spécialisé en architecture logicielle.
> Le contexte ci-dessous est MESURÉ sur l'application réelle (Python 3,
> Tkinter, NumPy, OpenCV) ; les chiffres viennent d'outils de bancs conservés
> dans le dépôt.

## 1. Ce que fait le logiciel

Application de bureau **mono-processus** (Python, interface Tkinter) de **live
stacking** astronomique : elle lit des images brutes (FITS/PNG/TIFF) au fur et à
mesure qu'elles sont écrites sur le disque (ou depuis une caméra), les calibre
(dark/flat), les aligne (ORB+RANSAC, repli corrélation de phase), les empile
avec rejet kappa-sigma ou Winsorized (fenêtre glissante), puis **affiche en
continu** l'empilement étiré (STF auto ou manuel, ou un moteur tiers VeraLux) avec
deux histogrammes, et permet de sauvegarder le résultat.

Cible **multiplateforme Windows / Linux / macOS**. Aucune dépendance lourde
supplémentaire souhaitée (pas de Qt, pas de GPU obligatoire, pas de nouveau
service). L'empilement est **bit-à-bit verrouillé par des bancs** : toute
optimisation doit prouver qu'elle ne change pas les pixels produits.

Tailles réelles : capteurs de 8,3 Mpx (3840×2160) à 26 Mpx (6248×4176) ;
l'aperçu à l'écran est plafonné à **1600 px de côté** (1600×1200, soit 1,92 Mpx,
en float32 = 23 Mo) ; les empilements se font à **pleine résolution**.

## 2. Architecture actuelle (telle qu'elle est codée)

```
 [source: dossier surveillé / caméra SDK / simulation]
        │  (frames brutes, FITS)
        ▼
 thread ① « acquisition + empilement » (App.thread → core/worker.py::_worker)
   - calibration, alignement, LiveStacker.add()  (NumPy pur, verrous)
   - publie un ÉTAT partagé (dict `st`) + une file `q` (maxsize=2)
        │
        ▼
 thread ② interface Tk (MainThread)
   - boucle `_tick` planifiée toutes les 30 ms (budget auto-imposé 30 ms)
   - lit `st` ; si le compteur de frames a changé → rendu :
       _rendre_et_afficher() = DisplayProcessor.process()  → à l'écran
                             + 2 histogrammes                 → à l'écran
 thread ③ « chaîne lourde » (processing/display.py::_vl_worker, daemon)
   - GraXpert (sous-processus) → débruitage → netteté → chroma
   - publie une image par composition/paramètres ; résultat consommé par ②
 thread ④ « guet de gel » (surveille les gels du fil d'interface)
 + threads courts : mesures de disque, détection SDK, téléchargements.
```

Points structurels importants :

- **Tout le rendu d'affichage est fait sur le fil Tk** (`DisplayProcessor.process`
  puis `_show_image` → `cv2.resize` + `PhotoImage`). C'est un choix assumé
  (« un seul point de passage ») : la donnée affichée et les histogrammes sont
  toujours cohérents.
- La chaîne lourde (③) est **déjà** hors du fil Tk, mais son **application**
  (étirement + niveaux + gamma + saturations + histogrammes) est sur le fil Tk.
- Files bornées (`maxsize=2`) entre acquisition et UI : une nouvelle frame peut
  donc **attendre** que l'UI ait fini son rendu.
- Les curseurs de réglage ne recalculent plus rien pendant un glissement : un
  seul aperçu est produit au relâchement (optimisation déjà livrée et mesurée,
  voir §4).

## 3. Buffers mémoire à pleine résolution (calcul théorique, à vérifier)

`processing/stacking.py`, classe `LiveStacker` :

- `self.sum`, `self.sumsq`, `self.wsum` : **float64**, un par pixel et par canal
  (ligne ~441) → à 26 Mpx : **208 Mo chacun, 625 Mo les trois** (mono).
- Mode Winsorized : `self._buf = np.zeros((window,) + frame.shape, float32)` avec
  `window = 8` par défaut → **~833 Mo** à 26 Mpx mono.
- Plus `_moy`, `_sig`, `_dif` (float64, même taille) et `_pix`/`_masq` → encore
  ~600 Mo.
- Une **composition multi-canaux** (jusqu'à 5 rôles L/R/G/B/Ha) instancie
  plusieurs de ces objets : l'ordre de grandeur atteint **plusieurs Go**, voire
  >10 Go à 26 Mpx.

Mesure sur une instance **au repos** (aucun empilement) : RSS ≈ **150 Mo**,
pic ≈ **260 Mo** après quelques aperçus 1600×1200 (3 threads vivants).

## 4. Symptômes RÉELS rapportés par l'utilisateur (et déjà mesurés)

1. « **Ça ne va guère plus vite** » après l'optimisation des curseurs — alors que
   cette optimisation est prouvée : un pas de glissement coûte **0,036 ms**
   (avant : ~300 ms, un aperçu PAR pixel), un glissement de 200 px **230–324 ms**
   au lieu de 50–76 s, et la charge pour suivre 60 Hz de souris est passée de
   **2 284 %** à **0,22 %** d'un cœur.
2. « **L'interface répond quand le spinner « traitement en cours » n'est pas
   actif** » : la gêne est donc **pendant le calcul**, pas pendant les gestes.
3. « **Mémoire bien occupée : 80 % de 32 Go** », à peine mieux avec l'éditeur
   fermé (piste : les buffers d'empilement, §3).

Mesures déjà faites sur le rendu (aperçu 1600×1200, fenêtre plein écran) :

| poste | mesure |
|---|---|
| un aperçu complet (étirement + niveaux + gamma/sat + 2 histogrammes) | **~250–320 ms** |
| dont dessin du canvas (`cv2.resize` + `PhotoImage`) | **12–14 ms** |
| dont les deux histogrammes | **45–53 ms** |
| `_tick` lui-même (hors rendu) | **0,08 ms** (0,3 % du budget de 30 ms) |
| clic de case / cran de spinner (1 aperçu chacun) | 250–300 ms |
| listes déroulantes à 147 valeurs, `pack/forget` des cadres | **< 1 ms** |

Déjà écarté par la mesure : la boucle `_tick`, les listes, la visibilité des
cadres, et le coût « par pixel » des gestes. L'aperçu lui-même (~300 ms) est le
grain élémentaire : **chaque frame reçue déclenche un aperçu complet sur le fil
Tk**.

## 5. Questions posées (dans cet ordre)

1. **Où est le vrai goulot ?** Classer les hypothèses par espérance de gain :
   (a) contention CPU/GIL entre empilement et fil Tk ; (b) rendu synchrone sur le
   fil Tk à chaque frame ; (c) copies/temporaires NumPy et pression mémoire
   (§3) ; (d) verrous/attentes entre threads et files bornées ; (e) autre.
2. **Quelles expériences de mesure** permettent de trancher **sans** refonte
   (instrumentation existante : compteurs de durée, guet de gel, RSS du
   processus, temps passé fil par fil) ? Donner des protocoles reproductibles et
   les chiffres à comparer.
3. **Quelle architecture cible** pour que l'interface reste fluide pendant un
   empilement à pleine résolution, en gardant : mono-processus, Tkinter, pixels
   identiques au bit, multiplateforme. Discuter au minimum : budget de
   rafraîchissement (découpler la fréquence d'affichage de celle des frames),
   calcul d'image hors fil Tk + transfert d'un buffer prêt à dessiner, réduction
   de la résolution de TRAVAIL de l'aperçu (l'empilement restant pleine
   résolution), et séparation stricte « état » / « rendu ».
4. **Mémoire** : comment réduire l'empreinte des accumulateurs sans changer les
   résultats (float32 vs float64, somme compensée, fenêtre glissante bornée,
   buffer préalloué réutilisé, libération explicite, un seul stacker par canal
   actif), et comment **prouver** l'égalité au bit ou une tolérance acceptée.
5. **Ordre de mise en œuvre** : un plan par étapes, chacune avec gain attendu,
   risque de régression, coût de développement et **banc de vérification**.
   Commencer par ce qui est mesurable en une journée.

## 6. Contraintes de la réponse

- Pas de « il suffit de passer en asyncio/Qt/multiprocessing » sans traiter les
  contraintes (Tkinter imposé, mono-processus, multiplateforme, égalité des
  pixels).
- Ne pas proposer d'optimiser les gestes de curseurs : **c'est déjà fait et
  mesuré** ; ne pas proposer d'aperçu réduit pendant un geste (refusé).
- Chaque recommandation doit venir avec **la mesure qui la valide** et **le
  risque de régression** associé.
- Distinguer clairement : (i) ce qui est certain, (ii) ce qui est une hypothèse à
  mesurer, (iii) ce qui relève d'une refonte lourde.
