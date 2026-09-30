# -*- coding: utf-8 -*-
"""Test du jalon 83 (v2.46.0) — LE GRADIENT DE LA CHAÎNE EXTERNE (⚡) PART EN UN
SEUL LOT, le débruitage reste couche par couche.

POURQUOI : le jalon 81 avait mis en lot le gradient du SOLVEUR LIVE et de l'EXPORT
pleine résolution, mais le TRAITEMENT EXTERNE par couche (jalon 24) appelait
encore ses trois couches l'une APRÈS l'autre, chaque appel payant un démarrage
FIXE (~3,4 s mesurés, identiques sur iGPU Intel, RTX 4070 et RTX 4060 Ti).
MESURÉ sur ses 3 vraies couches (8,2-8,3 Mpx) : 11,45 → 4,92 s (+57 %) sur 4060 Ti,
10,73 → 4,28 s (+60 %) sur 4070, 10,12 → 4,24 s (+58 %) sur l'iGPU de dev —
sorties IDENTIQUES AU BIT dans les trois cas. Le DÉBRUITAGE reste en SÉRIE : son
lot ne rapporte rien (−13 % / +12,9 % / +1,2 %) car un seul appel sature déjà le
GPU.

Vérifie, sur des FAUX OUTILS qui dorment et JOURNALISENT (étiquette + horodatage),
et sans toucher au vrai config.json :

  [1] égalité AU BIT : le résultat du lot est celui du repli SÉRIE (témoin
      `MAX_PARALLELE = 1`) — et chaque couche est appelée EXACTEMENT une fois,
      l'entrée de chaque appel étant vérifiée sur ses VALEURS (moyennes du
      journal) ;
  [2] les appels du lot se CHEVAUCHENT vraiment (maximum simultané ≥ 2, contre 1
      pour le témoin) ;
  [3] ordre : TOUS les gradients d'abord, puis les débruitages — conséquence
      STRUCTURELLE du lot (elle vaut aussi pour le témoin série), chaque couche
      recevant bien son débruitage APRÈS son gradient (vérifié par les moyennes) ;
  [4] une couche VIDE n'est pas envoyée à l'outil (et les autres le sont) ;
  [5] ÉCHEC PARTIEL du gradient : la couche fautive garde ses valeurs BRUTES, son
      message est posé, la chaîne CONTINUE (les autres couches sont traitées) ;
  [6] ÉCHEC TOTAL du gradient : la chaîne s'ARRÊTE (None) et l'état est `error` ;
  [7] intégration `_run_external_compo` (fenêtre réelle + composition à 3 rôles,
      gradient + débruitage GraXpert + BXT factices) : composite identique AU BIT
      avec et sans parallélisme, état `ok`.

Nécessite un affichage (Tk) pour [7]. Exécution :
  python bancs/_test_gx_lot_externe_jalon83.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import os
import shutil
import sys
import tempfile
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.ui.app as ui
from avastack.external import live as gx_live
from avastack.processing.composition import CompositeStacker

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def chevauchement(lignes_j):
    """Nombre MAXIMAL d'appels simultanés, d'après les horodatages du journal."""
    ouverts, maxi = 0, 0
    for l in sorted(lignes_j, key=lambda x: float(x.split()[-1])):
        if l.startswith("start"):
            ouverts += 1
            maxi = max(maxi, ouverts)
        elif l.startswith("end"):
            ouverts -= 1
    return maxi


# --- Faux outil : journalise « start/end <étiquette> <moyenne> <temps> », dort,
# puis DOUBLE son entrée. Il ÉCHOUE (code 3) si la moyenne de l'entrée dépasse
# le seuil reçu (argv[6], vide = jamais) : de quoi faire échouer UNE couche et
# pas les autres sans toucher au code de l'application.
FAUX = '''# -*- coding: utf-8 -*-
import sys, time
import numpy as np
from astropy.io import fits
src, out, journal, etiquette, dodo, seuil = sys.argv[1:7]
d = np.asarray(fits.getdata(src), dtype=np.float32)
with open(journal, "a", encoding="utf-8") as f:
    f.write("start %s %.4f %.3f\\n" % (etiquette, float(d.mean()), time.time()))
time.sleep(float(dodo))
if seuil and float(d.mean()) > float(seuil):
    sys.stderr.write("echec voulu : moyenne %.4f\\n" % float(d.mean()))
    sys.exit(3)
fits.PrimaryHDU((d * 2.0).astype(np.float32)).writeto(out, overwrite=True)
with open(journal, "a", encoding="utf-8") as f:
    f.write("end %s %.4f %.3f\\n" % (etiquette, float(d.mean()), time.time()))
'''

RACINE = tempfile.mkdtemp(prefix="avastack_banc83_")
OUTIL = os.path.join(RACINE, "faux_outil.py")
JOURNAL = os.path.join(RACINE, "journal.txt")
with open(OUTIL, "w", encoding="utf-8") as f:
    f.write(FAUX)


def cmd(etiquette, dodo="0.4", seuil=""):
    """Commande factice complète (mêmes placeholders qu'un vrai outil)."""
    return (f'"{sys.executable}" "{OUTIL}" "{{input}}" "{{output}}" '
            f'"{JOURNAL}" {etiquette} {dodo} "{seuil}"')


def vide_journal():
    with open(JOURNAL, "w", encoding="utf-8") as f:
        f.write("")


def lignes():
    if not os.path.isfile(JOURNAL):
        return []
    with open(JOURNAL, encoding="utf-8") as f:
        return [l.strip() for l in f if l.strip()]


class FauxApp:
    """Le MINIMUM que `_compo_couches_traitees` et `_ext_run_cmd` demandent à
    l'application : `_set_ext_msg`. Tout le reste du code testé est celui de
    l'application (appelé non lié, jamais recopié)."""

    def __init__(self):
        self.ext_msg, self.ext_state = "", None

    def _set_ext_msg(self, txt, state=None):
        self.ext_msg = txt
        if state:
            self.ext_state = state

    def _ext_run_cmd(self, *args, **kwargs):
        """Le lanceur RÉEL de l'application (jalon 24), sur ce harnais."""
        return ui.App._ext_run_cmd(self, *args, **kwargs)


def champ(niveau, h=48, w=64, graine=0):
    """Couche mono d'un NIVEAU connu : la moyenne identifie la couche dans le
    journal et dit ce que l'outil a réellement reçu."""
    rng = np.random.default_rng(graine)
    return np.clip(rng.normal(niveau, max(niveau * 0.02, 1e-3), (h, w)),
                   0, None).astype(np.float32)


def canaux_test():
    return {"Ha": champ(0.05, graine=1), "O3": champ(0.20, graine=2),
            "S2": champ(0.35, graine=3)}


def lancer(canaux, cmd_gx, cmd_dn, parallele, n_etapes=6):
    """Appelle la VRAIE `_compo_couches_traitees` avec un harnais minimal
    → (résultat, messages, état, message posé)."""
    faux, msgs = FauxApp(), []
    ancien = gx_live.MAX_PARALLELE
    gx_live.MAX_PARALLELE = parallele
    tmp = tempfile.mkdtemp(prefix="avastack_banc83_tmp_")
    try:
        res = ui.App._compo_couches_traitees(
            faux, canaux, True, cmd_gx, True, cmd_dn, "graxpert", 0.5,
            tmp, JOURNAL, 10, n_etapes, msgs)
    finally:
        gx_live.MAX_PARALLELE = ancien
        shutil.rmtree(tmp, ignore_errors=True)
    return res, msgs, faux.ext_state, faux.ext_msg


def identiques(a, b):
    return (a is not None and b is not None and set(a) == set(b)
            and all(np.array_equal(a[r], b[r]) for r in a))


def moyennes_du_journal(lignes_j, etiquette):
    """Moyennes que l'outil a VUES, pour un type d'appel (GX / DN)."""
    return sorted(float(l.split()[2]) for l in lignes_j
                  if l.startswith("start " + etiquette))


# ============================================ [1] égalité AU BIT (lot = série)
print("[1] LOT contre TÉMOIN (MAX_PARALLELE = 1) : égalité AU BIT")
c0 = canaux_test()
vide_journal()
res_serie, msgs_s, _etat_s, _msg_s = lancer(c0, cmd("GX"), cmd("DN"), 1)
l_serie = lignes()
vide_journal()
res_lot, msgs_l, _etat_l, msg_l = lancer(c0, cmd("GX"), cmd("DN"), 3)
l_lot = lignes()
verifie(identiques(res_serie, res_lot),
        "les couches traitées sont IDENTIQUES AU BIT (lot = comportement "
        "d'avant)")
verifie(res_lot is not None and set(res_lot) == {"Ha", "O3", "S2"}
        and all(v.shape == (48, 64) for v in res_lot.values()),
        "les 3 couches sont rendues, formes conservées")
verifie(len([l for l in l_serie if l.startswith("start GX")]) == 3
        and len([l for l in l_lot if l.startswith("start GX")]) == 3,
        "3 appels de gradient dans les DEUX cas (aucun appel en double)")
verifie(all(np.allclose(res_lot[r], np.asarray(c0[r], np.float32) * 4.0,
                        rtol=1e-6) for r in c0),
        "chaque couche subit bien les DEUX étapes (gradient ×2 puis débruitage "
        "×2)")
entrees = sorted(float(np.mean(np.asarray(c0[r], np.float32))) for r in c0)
vues_gx = moyennes_du_journal(l_lot, "GX")
vues_dn = moyennes_du_journal(l_lot, "DN")
verifie(len(vues_gx) == 3
        and all(abs(a - b) < 1e-3 for a, b in zip(entrees, vues_gx)),
        f"le gradient a vu les 3 couches d'ENTRÉE ({[round(v, 4) for v in vues_gx]})")
verifie(len(vues_dn) == 3
        and all(abs(2 * a - b) < 1e-3 for a, b in zip(entrees, vues_dn)),
        f"le débruitage a vu les couches APRÈS gradient ({[round(v, 4) for v in vues_dn]})")

# ======================================================== [2] chevauchement réel
print("[2] Chevauchement réel des appels (journal horodaté)")
verifie(chevauchement(l_serie) == 1,
        f"témoin MAX_PARALLELE=1 : jamais deux appels à la fois "
        f"({chevauchement(l_serie)})")
verifie(chevauchement(l_lot) >= 2,
        f"lot : les appels se CHEVAUCHENT vraiment (maximum simultané "
        f"{chevauchement(l_lot)})")

# ====================================== [3] ordre : gradients puis débruitages
print("[3] Ordre de la chaîne : tous les gradients, PUIS les débruitages")
etiquettes_lot = [l.split()[1] for l in
                  sorted(l_lot, key=lambda x: float(x.split()[-1]))
                  if l.startswith("start")]
verifie(etiquettes_lot == ["GX"] * 3 + ["DN"] * 3,
        f"journal du lot : {etiquettes_lot} — conséquence assumée du lot "
        "(les 3 gradients d'abord)")
verifie([l.split()[1] for l in l_serie if l.startswith("start")]
        == ["GX", "GX", "GX", "DN", "DN", "DN"],
        "témoin (1 appel à la fois) : MÊME ordre — le lot ne change QUE la "
        "simultanéité")

# ============================================================ [4] couche vide
print("[4] Une couche VIDE n'est pas envoyée à l'outil")
vide_journal()
c_vide = canaux_test()
c_vide["O3"] = np.zeros((48, 64), np.float32)
res_v, msgs_v, _e, _m = lancer(c_vide, cmd("GX"), cmd("DN"), 3)
l_v = lignes()
verifie(len([l for l in l_v if l.startswith("start GX")]) == 2,
        "2 appels de gradient seulement (la couche vide est écartée)")
verifie(len([l for l in l_v if l.startswith("start DN")]) == 3,
        "le débruitage, lui, voit les 3 couches (comportement inchangé)")
verifie(any("O3" in m and "vide" in m for m in msgs_v),
        f"message clair pour la couche vide ({msgs_v})")
verifie(res_v is not None and np.array_equal(res_v["O3"], c_vide["O3"]),
        "la couche vide ressort inchangée (aucune valeur inventée)")

# ========================================================== [5] échec PARTIEL
print("[5] ÉCHEC PARTIEL du gradient : couche brute conservée, chaîne CONTINUE")
vide_journal()
c_p = canaux_test()
res_p, msgs_p, etat_p, _m = lancer(c_p, cmd("GX", seuil="0.25"), cmd("DN"), 3)
verifie(res_p is not None and set(res_p) == {"Ha", "O3", "S2"},
        "la chaîne a CONTINUÉ (les 3 couches sont rendues)")
verifie(any("S2" in m for m in msgs_p),
        f"le message nomme la couche fautive ({msgs_p})")
verifie(np.allclose(res_p["S2"], np.asarray(c_p["S2"], np.float32) * 2.0,
                    rtol=1e-6),
        "S2 : gradient raté → valeurs BRUTES conservées, puis débruitage "
        "(aucune image perdue)")
verifie(np.allclose(res_p["Ha"], np.asarray(c_p["Ha"], np.float32) * 4.0,
                    rtol=1e-6)
        and np.allclose(res_p["O3"], np.asarray(c_p["O3"], np.float32) * 4.0,
                        rtol=1e-6),
        "Ha et O3 : gradient ET débruitage appliqués (×4)")
verifie(etat_p != "error", f"état non bloquant ({etat_p!r})")

# ============================================================ [6] échec TOTAL
print("[6] ÉCHEC TOTAL du gradient : la chaîne S'ARRÊTE et le dit")
vide_journal()
res_t, msgs_t, etat_t, msg_t = lancer(canaux_test(), cmd("GX", seuil="0.001"),
                                      cmd("DN"), 3)
verifie(res_t is None, "résultat None (chaîne arrêtée)")
verifie(etat_t == "error", f"état 'error' ({etat_t!r})")
verifie("gradient" in msg_t.lower(),
        f"message nommant l'étape (« {msg_t[:70]}… »)")
verifie(len([l for l in lignes() if l.startswith("start DN")]) == 0,
        "aucun débruitage lancé après un échec total du gradient")

# ============================== [7] intégration : la chaîne ⚡ complète (Tk)
print("[7] Intégration _run_external_compo : composite identique AU BIT")
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
ui.CONFIG = {}
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()
fa = CompositeStacker("HOO", k=None)
for i, role in enumerate(("Ha", "O3", "S2")):
    fa.role_courant = role
    fa.add(champ(0.05 * (i + 1), graine=10 + i))
app.stacker = fa
comp, canaux_compo = fa.mean_avec_canaux()
app.ext_job = (True, cmd("GX"),          # 0,1 : gradient par couche
               True, cmd("DN"),          # 2,3 : débruitage GraXpert par couche
               True, cmd("BXT"),         # 4,5 : un seul appel sur le composite
               "graxpert", 0.5,          # 6,7 : mode et force du débruitage
               # v2.48.0 (jalon 85) : le job n'a plus que 12 éléments — les
               # trois cases couleur ont quitté la chaîne externe (elles suivent
               # l'étirement) :
               False,                    # 8 : neutralisation du fond
               False,                    # 9 : réduction du bruit chromatique
               0.5, 3.0)                 # 10,11 : force et rayon de chroma
res = {}
for parallele in (1, 3):
    vide_journal()
    app.proc_full, app.proc_new = None, False
    app.ext_msg, app.ext_state = "", None
    ancien = gx_live.MAX_PARALLELE
    gx_live.MAX_PARALLELE = parallele
    try:
        app._run_external_compo(comp, canaux_compo, 12, 0)
    finally:
        gx_live.MAX_PARALLELE = ancien
    res[parallele] = (None if app.proc_full is None else app.proc_full.copy(),
                      app.ext_state, app.ext_msg, lignes())
verifie(res[1][0] is not None and res[3][0] is not None,
        "les deux exécutions produisent un composite")
verifie(res[1][0].shape == comp.shape,
        f"composite rendu en (H, W, 3) ({res[1][0].shape})")
verifie(np.array_equal(res[1][0], res[3][0]),
        "composite IDENTIQUE AU BIT (chaîne ⚡ avec lot = chaîne ⚡ d'avant)")
verifie(res[3][1] == "ok" and "Traité par couche" in res[3][2],
        f"état 'ok' et message de succès ({res[3][1]!r} : « {res[3][2][:60]}… »)")
verifie(len([l for l in res[3][3] if l.startswith("start GX")]) == 3
        and len([l for l in res[3][3] if l.startswith("start DN")]) == 3
        and len([l for l in res[3][3] if l.startswith("start BXT")]) == 1,
        "3 gradients + 3 débruitages + 1 BXT (le BXT reste UN appel sur le "
        "composite)")
verifie(chevauchement(res[3][3]) >= 2,
        f"les gradients du lot se chevauchent (maximum {chevauchement(res[3][3])})")
verifie(chevauchement(res[1][3]) == 1,
        f"témoin : aucun chevauchement ({chevauchement(res[1][3])})")
root.destroy()

print()
print("TOUT PASSE" if ok else "ÉCHECS À CORRIGER")
shutil.rmtree(RACINE, ignore_errors=True)
sys.exit(0 if ok else 1)
