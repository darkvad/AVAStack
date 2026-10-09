# -*- coding: utf-8 -*-
"""DIAGNOSTIC — alignement de VOS vrais fichiers (retournement au méridien).

Reproduit EXACTEMENT ce que fait l'appli : prend la 1re frame du 1er dossier
comme référence d'alignement, puis tente d'aligner quelques frames de CHAQUE
dossier, et affiche l'angle et la méthode réellement mesurés. C'est la seule
façon de savoir si le 180° est bien retrouvé sur VOS données.

Utilisation (PowerShell, dans le dossier du projet) :

    .\\venv\\Scripts\\python.exe bancs\\_diag_align_dossiers.py `
        "C:\\chemin\\vers\\L" "C:\\chemin\\vers\\R" `
        "C:\\chemin\\vers\\G" "C:\\chemin\\vers\\B"

Options :
    --par-dossier N   nombre de frames testées par dossier (défaut 4)
    --tous            teste TOUTES les frames de chaque dossier (long)

Sortie : une ligne par frame — rôle, fichier, ok, angle, échelle, méthode.
Un angle ≈ ±180° = le correctif fonctionne ; « REFUS » = l'aligneur n'a rien
trouvé (on regarde alors la méthode et le nombre d'étoiles).
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys

import numpy as np

from avastack.processing import alignment as al_mod
from avastack.processing.composition import extraire_canal, role_de_filtre
import avastack.images as images

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXT = (".fits", ".fit", ".fts", ".png", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp")


def _role_dossier(dossier, chemin):
    """Rôle du dossier : mot-clé FITS FILTER, puis nom du dossier, puis « L »."""
    filtre = images.lire_filtre_fits(chemin)
    role = role_de_filtre(filtre) if filtre else None
    if role:
        return role
    base = os.path.basename(os.path.normpath(dossier)).upper()
    for cand in ("HA", "O3", "OIII", "S2", "SII", "LRGB", "L", "R", "G", "B"):
        if cand in base:
            return {"OIII": "O3", "SII": "S2", "LRGB": "L"}.get(cand, cand)
    return "L"



def lister(dossier):
    """Fichiers image du dossier, dans l'ordre chronologique (mtime puis nom)."""
    out = []
    for e in os.scandir(dossier):
        if e.is_file() and e.name.lower().endswith(EXT):
            out.append((e.stat().st_mtime, e.name, e.path))
    out.sort()
    return [p for _t, _n, p in out]


def main(argv):
    par = 4
    tous = "--tous" in argv
    if "--par-dossier" in argv:
        par = int(argv[argv.index("--par-dossier") + 1])
    dossiers = [a for a in argv if os.path.isdir(a)]
    if len(dossiers) < 2:
        print(__doc__)
        return 2

    print("Module alignment :", al_mod.__file__)
    print("MERIDIAN_FLIP_DEG =",
          getattr(al_mod, "MERIDIAN_FLIP_DEG", "ABSENT (ancien code !)"),
          "· tolérance =", getattr(al_mod, "MERIDIAN_FLIP_TOL_DEG", "?"))
    print()

    # Référence = 1re frame du 1er dossier (comme l'appli).
    premier = lister(dossiers[0])
    if not premier:
        print("Aucune image dans", dossiers[0])
        return 1
    ref_role = _role_dossier(dossiers[0], premier[0])
    ref_img = extraire_canal(
        np.asarray(images.load_image(premier[0]), np.float32), ref_role)
    al = al_mod.StarAligner()
    al.set_reference(ref_img)
    print(f"RÉFÉRENCE = {os.path.basename(premier[0])} (rôle {ref_role})\n")

    for d in dossiers:
        fichiers = lister(d)
        choisir = fichiers if tous else _echantillon(fichiers, par)
        role = _role_dossier(d, choisir[0]) if choisir else "?"
        print(f"--- {d} — rôle {role} "
              f"({len(fichiers)} fichiers, {len(choisir)} testés) ---")
        for chemin in choisir:
            try:
                img = extraire_canal(
                    np.asarray(images.load_image(chemin), np.float32), role)
            except Exception as exc:
                print(f"    {os.path.basename(chemin):40s} ILLISIBLE ({exc})")
                continue
            M, okk = al.compute(img)
            if M is None or not okk:
                print(f"    {os.path.basename(chemin):40s} REFUS        "
                      f"({al.dernier})")
                continue
            ang, ech, dx, dy = al_mod.infos_M(M)
            print(f"    {os.path.basename(chemin):40s} ok  "
                  f"angle={ang:+8.2f}°  éch={ech:.4f}  "
                  f"Δ=({dx:+6.1f},{dy:+6.1f})  {al.dernier['methode']}")
        print()
    print("LECTURE : angle ≈ 0° = même orientation que la référence ;")
    print("          angle ≈ ±180° = RETOURNEMENT (le correctif le rattrape) ;")
    print("          REFUS = l'aligneur n'a rien trouvé (voir la méthode/nb étoiles).")
    return 0


def _echantillon(fichiers, n):
    """n fichiers répartis (début, milieu, fin) pour couvrir les 2 nuits."""
    if len(fichiers) <= n:
        return fichiers
    idx = np.linspace(0, len(fichiers) - 1, n).astype(int)
    return [fichiers[i] for i in dict.fromkeys(idx)]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
