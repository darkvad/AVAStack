# -*- coding: utf-8 -*-
"""Test headless du jalon 4 — GraXpert live (opt-in) avant l'étirement VeraLux.

Vérifie, SANS Tk, avec un outil CLI factice (_gx_factice.py : copie pure de
l'entrée vers la sortie + compteur d'exécutions) :
  - défauts : vl_graxpert = False → AUCUN appel externe (comportement jalon 3
    strictement inchangé) ;
  - chaîne stack → GraXpert → VeraLux : le résultat VeraLux est calculé sur
    la SORTIE de l'outil (identique à l'entrée ici) — comparaison à un appel
    direct du moteur ;
  - cache : bouger un curseur VeraLux (nouvelle clé de réglages) NE relance
    PAS l'outil externe ;
  - erreur non fatale : commande invalide → vl_error « GraXpert live : … »,
    l'image brute est quand même étirée (pas d'image figée) ;
  - désactivation → plus aucun appel externe ;
  - reset() vide le cache → l'outil est relancé ;
  - black/white/gamma jamais écrits (leçon de la 1re tentative).
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
import time

import numpy as np

# Sortie redirigée (fichier/pipe) → cp1252 ne sait pas encoder →/—/× des prints
for _flux in (sys.stdout, sys.stderr):
    if hasattr(_flux, "reconfigure"):
        _flux.reconfigure(errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from avastack.processing import display as _disp
from avastack.processing import veralux as vl
from avastack.external import live as gxl

RACINE = os.path.dirname(os.path.abspath(__file__))
FAKE = os.path.join(RACINE, "_gx_factice.py")
COMPTEUR = os.path.join(RACINE, "_gx_jalon4_compteur.txt")

ECHOUEES = []


def verifie(cond, msg):
    print(("  OK  " if cond else "  ÉCHEC") + " — " + msg)
    if not cond:
        ECHOUEES.append(msg)


def nb_executions():
    if not os.path.isfile(COMPTEUR):
        return 0
    with open(COMPTEUR, encoding="utf-8") as f:
        return len([l for l in f.read().splitlines() if l.strip()])


def resoudre(d, img):
    """Soumet un job, attend la fin du thread solveur, rend le résultat."""
    d.process(img)
    t0 = time.time()
    while (d._vl_pending or d._vl_job is not None) and time.time() - t0 < 60:
        time.sleep(0.01)
    d.process(img)
    return d._vl_result is not None


def image_test():
    """Image linéaire mono déterministe (dégradé + bruit fixe)."""
    h, w = 240, 320
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    img = 0.05 + 0.10 * (x / w) + 0.05 * (y / h)
    rs = np.random.RandomState(42)
    img += 0.01 * rs.randn(h, w).astype(np.float32)
    return np.clip(img, 0.0, 1.0)


def main():
    img = image_test()
    cmd_ok = (f'"{sys.executable}" "{FAKE}" "{{input}}" "{{output}}" '
              f'"{COMPTEUR}"')

    d = _disp.DisplayProcessor()
    d.stretch = "veralux"
    d.vl_mode_res = vl.MODE_LOG_D          # déterministe pour les comparaisons
    d.vl_log_d = 2.0
    d.vl_profil = vl.PROFIL_PAR_DEFAUT

    # --- 1. Défauts : GraXpert live DÉSACTIVÉ --------------------------------
    print("[1] Défauts jalon 4")
    verifie(d.vl_graxpert is False, "vl_graxpert désactivé par défaut")
    verifie(gxl.commande_valide(cmd_ok), "commande factice valide")
    verifie(not gxl.commande_valide(""), "commande vide rejetée")
    verifie(not gxl.commande_valide("graxpert in.fits"),
            "commande sans {output}/{outbase} rejetée")

    # --- 2. Chaîne stack → GraXpert → VeraLux --------------------------------
    print("[2] Chaîne avec outil factice (copie pure)")
    d.vl_graxpert = True
    d.vl_graxpert_cmd = cmd_ok
    if os.path.isfile(COMPTEUR):
        os.remove(COMPTEUR)
    verifie(resoudre(d, img), "résolution terminée (1er appel)")
    verifie(d.vl_error == "", f"pas d'erreur ({d.vl_error!r})")
    verifie(nb_executions() == 1,
            f"outil externe appelé UNE fois ({nb_executions()})")
    ref, ld_ref, _ = vl.etirer(img.copy(), mode=vl.MODE_LOG_D, log_d=2.0,
                               profil=vl.PROFIL_PAR_DEFAUT)
    ecart = (float(np.max(np.abs(d._vl_result[1] - ref)))
             if d._vl_result[1].shape == ref.shape else 9.9)
    verifie(ecart < 1e-5, f"résultat = étirement VeraLux de la sortie outil "
            f"(écart max {ecart:.6f})")

    # --- 3. Cache : bouger un curseur ne relance PAS l'outil ------------------
    print("[3] Cache GraXpert par contenu d'image")
    d.vl_log_d = 3.0
    verifie(resoudre(d, img), "résolution relancée (nouvelle clé logD)")
    verifie(nb_executions() == 1,
            f"outil externe PAS relancé ({nb_executions()})")
    verifie(abs(d.vl_log_d_resolu - 3.0) < 1e-6,
            f"logD utilisé = 3.0 ({d.vl_log_d_resolu:.3f})")

    # --- 4. Nouvelle frame (contenu différent) → l'outil est relancé ---------
    print("[4] Nouvel empilement (contenu différent)")
    img2 = np.ascontiguousarray(image_test() * 1.3, dtype=np.float32)
    d.notify_new_stack()          # ce que _tick fait à chaque nouvel empilement
    verifie(resoudre(d, img2), "résolution terminée sur la nouvelle image")
    verifie(nb_executions() == 2, f"outil externe relancé pour la nouvelle "
            f"image ({nb_executions()})")

    # --- 5. Erreur non fatale --------------------------------------------------
    print("[5] Commande invalide → erreur signalée, étirement en repli")
    avant = (d.black, d.white, d.gamma)
    d.vl_graxpert_cmd = "outil_inexistant_xyz {input} -o {output}"
    verifie(resoudre(d, img), "résolution terminée malgré l'erreur outil")
    verifie(d.vl_error.startswith("GraXpert live :"),
            f"erreur signalée ({d.vl_error!r})")
    ref5, _, _ = vl.etirer(img.copy(), mode=vl.MODE_LOG_D, log_d=3.0,
                           profil=vl.PROFIL_PAR_DEFAUT)
    ecart5 = (float(np.max(np.abs(d._vl_result[1] - ref5)))
              if d._vl_result[1].shape == ref5.shape else 9.9)
    verifie(ecart5 < 1e-5, "image BRUTE étirée en repli "
            f"(écart max {ecart5:.6f})")
    verifie((d.black, d.white, d.gamma) == avant, "black/white/gamma intacts")

    # --- 6. Désactivation -------------------------------------------------------
    print("[6] Désactivation")
    d.vl_error = ""
    d.vl_graxpert = False
    verifie(resoudre(d, img), "résolution terminée")
    verifie(d.vl_error == "", "plus d'erreur")
    verifie(nb_executions() == 2,
            f"plus aucun appel externe ({nb_executions()})")

    # --- 7. reset() vide le cache ------------------------------------------------
    print("[7] reset() vide le cache GraXpert")
    d.vl_graxpert = True
    d.vl_graxpert_cmd = cmd_ok
    d.vl_log_d = 2.0
    d.reset()
    verifie(d._gx_cache is None, "cache vidé")
    verifie(resoudre(d, img), "résolution terminée après reset")
    verifie(nb_executions() == 3,
            f"outil relancé après reset ({nb_executions()})")

    # --- 8. Round-trip FITS de l'adaptateur live ----------------------------------
    print("[8] appliquer() : identité via outil factice")
    out, err = gxl.appliquer(img, cmd_ok)
    verifie(err == "", f"pas d'erreur ({err!r})")
    verifie(out.shape == img.shape and
            float(np.max(np.abs(out - img))) < 1e-6,
            "image renvoyée ≈ image d'entrée (FITS float32 sans perte)")
    verifie(gxl.appliquer(img, "")[1] != "",
            "commande vide → message d'erreur, image d'origine renvoyée")

    print()
    if ECHOUEES:
        print(f"ÉCHECS ({len(ECHOUEES)}) :")
        for m in ECHOUEES:
            print("  -", m)
        sys.exit(1)
    print("Tous les tests du jalon 4 sont passés.")


if __name__ == "__main__":
    main()
