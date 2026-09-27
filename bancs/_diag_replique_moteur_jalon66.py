# -*- coding: utf-8 -*-
"""_diag_replique_moteur_jalon66.py — CONTRÔLE : la réplique `chaine()` des bancs
du jalon 66 est-elle FIDÈLE au moteur tiers (à l'unité flottante près) ?

TOUTES les mesures du jalon 66 (ancre, plancher, plafond, rôle de la RÉSOLUTION
sur l'anneau de couleur des étoiles) reposent sur `chaine()` de
`_diag_veralux_resolution_jalon66.py`, une COPIE de `process_veralux_ready_to_use`
qui rejoue la chaîne en appelant les MÉTHODES du moteur — la copie existe pour
pouvoir SUBSTITUER l'ancre et les constantes de sortie (tests (b), (c), (d) du
banc de résolution). Si cette copie ne rendait pas exactement la même image que
`avastack.processing.veralux.etirer()`, les mesures ne prouveraient rien.

Ce banc l'exige explicitement, sur l'APERÇU et sur la PLEINE RÉSOLUTION, et
rappelle les constantes internes trouvées par les deux chemins.

Usage : python bancs/_diag_replique_moteur_jalon66.py [dossier]
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import os
import sys

import numpy as np
from astropy.io import fits

RACINE = sys.argv[1] if len(sys.argv) > 1 else r"C:\Astro\test"
sys.argv = [sys.argv[0]]

try:                                     # sortie console : jamais de plantage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _diag_veralux_resolution_jalon66 as R               # noqa: E402
from avastack.processing import veralux as _veralux        # noqa: E402


def main():
    lin = _veralux.normaliser_lin(np.asarray(
        fits.getdata(os.path.join(RACINE, R.LIGNE)), np.float32))
    if lin.ndim == 3 and lin.shape[0] == 3:
        lin = np.transpose(lin, (1, 2, 0))
    petit, ech = R.reduire(lin)
    _, logd, _ = _veralux.etirer(petit, mode=_veralux.MODE_TARGET_BG,
                                 target_bg=R.TARGET_BG, profil=R.PROFIL)
    print(f"logD résolu sur l'aperçu : {logd:.4f} (imposé aux deux, "
          f"mode {_veralux.MODE_LOG_D}, fond cible {R.TARGET_BG})")
    pire = 0.0
    for nom, img in (("APERÇU", petit), ("PLEINE RÉSOLUTION", lin)):
        # target_bg DOIT être celui des bancs (0,16) : la réplique code en dur le
        # fond cible de l'étape `adaptive_output_scaling` (MTF de sortie), un
        # appel avec le défaut du module (0,20) ne comparerait pas la même chose.
        ref, _, dg = _veralux.etirer(img, mode=_veralux.MODE_LOG_D, log_d=logd,
                                     profil=R.PROFIL, target_bg=R.TARGET_BG)
        copie, infos = R.chaine(np.ascontiguousarray(img), logd)
        ecart = float(np.max(np.abs(ref - copie)))
        pire = max(pire, ecart)
        print(f"\n  {nom} ({img.shape[1]}×{img.shape[0]})")
        print(f"    écart max copie ⇄ moteur : {ecart:.6f}"
              f"   (moyenne {float(np.mean(np.abs(ref - copie))):.8f})")
        print(f"    ancre   copie {infos['ancre']:.6f}"
              f"   (le diagnostic du moteur affiche {float(dg.get('anchor', float('nan'))):.6f}"
              f" : en mode logD imposé il n'en calcule AUCUNE — artefact à ne pas lire)")
        for cle, val in (("plancher", infos["plancher"]),
                         ("plafond", infos["plafond"])):
            print(f"    {cle:8s} copie {val:.6f}")
    print(f"\n  (réduction d'aperçu appliquée : ×{ech:.4f})")
    print(f"\n  VERDICT : {'FIDÈLE' if pire == 0.0 else 'ÉCART ' + f'{pire:.6f}'}"
          f" — la réplique {'rend la même image au bit près' if pire == 0.0 else 'DIVERGE'}"
          f" ; les mesures du jalon 66 {'portent donc' if pire == 0.0 else 'NE portent PAS'}"
          " sur le moteur réel.")


if __name__ == "__main__":
    main()
