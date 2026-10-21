# -*- coding: utf-8 -*-
"""DIAGNOSTIC — QUI tient le poste `rendu` de la jauge `postes` (21/10/2026).

LA QUESTION. Le relevé `perf-9` attribue **206,2 Mio** à l'attribut `rendu`
(l'instance `FilRendu`) — presque autant que `disp` (226,1). Or le fil de rendu
ne garde, par construction, qu'UN job et UN résultat (« le dernier gagne ») :
après application, `prendre()` a remis `_resultat` à None. 206 Mio ne peuvent
donc pas être « les images du fil ».

L'HYPOTHÈSE À VÉRIFIER (et c'est tout l'objet de ce diagnostic) : `FilRendu`
garde `_hote`, c'est-à-dire **l'application elle-même**. `perf.postes_memoire(app)`
parcourt les attributs de l'App dans leur ordre d'affectation ; en arrivant sur
`rendu`, il entre dans `vars(rendu)`, trouve `_hote`, RE-ENTRE dans l'App (qui
n'est pas encore marquée comme vue : la racine n'entre jamais dans `vus`) et
attribue au nom « rendu » les tableaux des attributs déclarés APRÈS `self.rendu`
dans `__init__` — `_stack_pleine_res`, `_last_disp`, `_hist_*`…

CE QUE CE DIAGNOSTIC MESURE (aucun fichier de l'application n'est modifié) :
  [1] la vue de la JAUGE (`postes_memoire(app)`) telle qu'elle part dans le JSON ;
  [2] la MÊME vue avec la boucle cassée (`app.rendu._hote = None`) ⇒ ce qui
      revient à son vrai propriétaire, et ce que le fil retient VRAIMENT ;
  [3] l'inventaire du `FilRendu` SEUL (chemins, tailles, alias par `id()`) ;
  [4] l'inventaire des attributs de PREMIER niveau de l'App > 1 Mio.

Exécution : python bancs/_diag_rendu_memoire.py [--geometrie HxW]
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import gc
import os
import sys
import time
import tkinter as tk

import numpy as np

from avastack import perf

if hasattr(sys.stdout, "reconfigure"):      # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MO = 1024.0 * 1024.0
GEOMETRIE = (2180, 3856)          # (hauteur, largeur) — géométrie NATIVE des brutes


def mem_mo():
    """RSS du processus en Mio (Windows : `psutil` si présent, sinon 0)."""
    try:
        import psutil                                   # noqa: PLC0415
        return psutil.Process(os.getpid()).memory_info().rss / MO
    except Exception:                                   # noqa: BLE001
        return 0.0


def main(argv):
    hh, ww = GEOMETRIE
    if "--geometrie" in argv:
        h, w = argv[argv.index("--geometrie") + 1].lower().split("x")
        hh, ww = int(h), int(w)
    px = hh * ww

    import avastack.ui.app as ui

    root = tk.Tk()
    root.withdraw()
    # Test HERMÉTIQUE (piège config.json) : config vierge simulée et sauvegarde
    # interceptée — le vrai fichier n'est jamais lu ni écrit.
    ui.CONFIG = {}
    ui.sauver_config = lambda d: None
    app = ui.App(root)

    print("=" * 78)
    print("DIAGNOSTIC DU POSTE `rendu` — qui le tient ?")
    print("=" * 78)
    print(f"  géométrie : {hh}x{ww} = {px:,} px (un float32 plein cadre ="
          f" {px * 4 / MO:.1f} Mio, un uint8 3 canaux = {px * 3 / MO:.1f} Mio)")

    # ---- état RÉALISTE : une image pleine résolution rendue par la VRAIE chaîne
    rng = np.random.default_rng(3)
    src = (0.002 + 0.02 * rng.random((hh, ww, 3)) ** 4).astype(np.float32)
    app._stack_pleine_res = src              # référence (v2.98.5 : plus de copie)
    app.var_vl_pleine_res.set(True)          # option « Rendu pleine résolution »
    app.rendu.immediat = True                # rendu SYNCHRONE (diagnostic)
    gc.collect()
    r_avant = mem_mo()
    t0 = time.time()
    app._rendre_et_afficher(src, live=True, hist=True, motif="audit")
    print(f"  rendu réel (VeraLux pleine résolution) : {time.time() - t0:.1f} s"
          f" · erreur = {app.disp.vl_error or 'aucune'}")
    gc.collect()
    r_apres = mem_mo()
    print(f"  RSS : avant {r_avant:,.0f} Mio → après {r_apres:,.0f} Mio"
          f" (delta {r_apres - r_avant:+,.0f})")

    def vue(titre, cible):
        """Affiche la vue d'une cible (mêmes règles que la jauge `postes`)."""
        tab = perf.postes_memoire(cible)
        print(f"\n{titre}")
        for nom, octets in sorted(tab["postes"].items(), key=lambda kv: -kv[1]):
            print(f"    {nom:34s} {float(octets) / MO:8.1f} Mio")
        print(f"    {'TOTAL':34s} {tab['total_octets'] / MO:8.1f} Mio"
              f"  ({tab['nb_tableaux']} tableaux)")

    vue("[1] VUE DE LA JAUGE — `perf.postes_memoire(app)` (ce qui part dans le JSON)",
        app)

    # ---- [2] la MÊME vue, la boucle `_hote` CASSÉE (l'hypothèse à vérifier)
    hote = app.rendu._hote
    app.rendu._hote = None
    vue("[2] MÊME VUE, boucle `FilRendu._hote` CASSÉE — l'attribution RÉELLE",
        app)
    vue("[3] LE `FilRendu` SEUL — ce que le fil retient vraiment",
        app.rendu)
    app.rendu._hote = hote

    # ---- [4] attributs de PREMIER niveau de l'App > 1 Mio
    print("\n[4] ATTRIBUTS DE PREMIER NIVEAU de l'App > 1 Mio (vrai propriétaire)")
    lignes = []
    for nom, valeur in vars(app).items():
        try:
            octets, nb = perf.taille_tableaux(valeur, profondeur=4)
        except Exception:                               # noqa: BLE001
            continue
        if octets > MO:
            lignes.append((nom, octets, nb))
    for nom, octets, nb in sorted(lignes, key=lambda t: -t[1]):
        print(f"    {nom:34s} {octets / MO:8.1f} Mio  ({nb} tableaux)")
    if not lignes:
        print("    (aucun)")
    print("\n  → LECTURE : un tableau compté sous `rendu` en [1] et sous son vrai"
          " nom en [2] est\n    un ARTEFACT de parcours (la boucle `_hote`), pas"
          " une rétention du fil de rendu.")

    root.destroy()


if __name__ == "__main__":
    main(sys.argv[1:])
