# -*- coding: utf-8 -*-
"""Test du jalon 81 (v2.45.0) — APPELS EXTERNES PAR COUCHE, EN PARALLÈLE.

POURQUOI : le coût de GraXpert est FIXE par appel (démarrage de son binaire figé
+ chargement des 217 Mo du modèle IA, ~2,8 s mesurés) et la chaîne par couche
(jalon 24) l'appelait TROIS fois de suite, une par couche de composition. Les
couches étant indépendantes, les trois appels sont désormais lancés ENSEMBLE
(mémoire bornée). Mesuré sur la machine de dev, 3 couches d'aperçu :
**13,70 s → 5,58 s**, fichiers produits **identiques octet à octet**.

Vérifie, avec un outil factice qui DORT et JOURNALISE ses entrées/sorties :

  [1] bornes de `parallele_max` : plafond, nombre d'éléments, MÉMOIRE LIBRE
      (repli série quand elle manque) ;
  [2] un lot de 3 appels de 0,8 s dure MOINS de la série et les appels se
      CHEVAUCHENT vraiment (journal d'entrées/sorties) ;
  [3] les résultats d'un lot sont **identiques au bit** à ceux d'appels en série
      (même image par rôle) ;
  [4] `MAX_PARALLELE = 1` → comportement d'AVANT (strictement en série) ;
  [5] l'échec d'un élément n'empêche pas les autres et son message est exact ;
  [6] chemin LIVE (solveur, composition à 3 canaux) : le composite final est
      **identique au bit** avec et sans parallélisme, et l'outil est bien appelé
      UNE fois par couche ;
  [7] les caches par rôle tiennent : un second rendu inchangé n'appelle RIEN ;
  [8] mémoire libre insuffisante → repli SÉRIE automatique ;
  [9] export pleine résolution (`_couches_pleine_resolution`) : identique au bit.

Nécessite un affichage (Tk) pour les cas 6, 7 et 9.
Exécution : python bancs/_test_gx_parallele_jalon81.py
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
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.external import live as gx
import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# ------------------------------------------------------- outil externe factice
# Copie l'entrée vers la sortie en la DOUBLANT (le résultat est donc vérifiable),
# DORT le temps demandé et JOURNALISE chaque début/fin : c'est ce journal qui
# prouve le chevauchement (« start A, start B, start C, end A… »).
FAUX = '''# -*- coding: utf-8 -*-
import os, sys, time
import numpy as np
from astropy.io import fits
entree, sortie, journal, dodo = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
nom = os.path.basename(entree)
f = open(journal, "a", encoding="utf-8"); f.write("start %.2f %s\\n" % (time.time(), nom)); f.close()
time.sleep(dodo)
d = np.asarray(fits.open(entree)[0].data, dtype="float32")
fits.PrimaryHDU(d * 2.0).writeto(sortie, overwrite=True)
f = open(journal, "a", encoding="utf-8"); f.write("end %.2f %s\\n" % (time.time(), nom)); f.close()
'''

RACINE = tempfile.mkdtemp(prefix="avastack_banc81_")
FAUX_PY = os.path.join(RACINE, "faux_outil.py")
JOURNAL = os.path.join(RACINE, "journal.txt")
with open(FAUX_PY, "w", encoding="utf-8") as f:
    f.write(FAUX)
CMD = f'"{sys.executable}" "{FAUX_PY}" "{{input}}" "{{output}}" "{JOURNAL}" 0.8'
CMD_RAPIDE = CMD.replace("0.8", "0.05")


def journal(lignes=None):
    """Contenu du journal (ou seulement ses N dernières lignes)."""
    if not os.path.isfile(JOURNAL):
        return []
    with open(JOURNAL, encoding="utf-8") as f:
        tout = [l.strip() for l in f if l.strip()]
    return tout if lignes is None else tout[-lignes:]


def vide_journal():
    if os.path.isfile(JOURNAL):
        os.remove(JOURNAL)


def chevauchement(lignes):
    """Nombre MAXIMAL d'appels simultanés, d'après le journal."""
    ouverts, maxi = 0, 0
    for l in lignes:
        if l.startswith("start"):
            ouverts += 1
            maxi = max(maxi, ouverts)
        elif l.startswith("end"):
            ouverts -= 1
    return maxi


def image_test(h=120, w=160, graine=0):
    rng = np.random.default_rng(graine)
    return (0.05 + 0.3 * rng.random((h, w))).astype(np.float32)


def en_serie(items, timeout=gx.TIMEOUT_S):
    """Mêmes appels, l'un APRÈS l'autre (référence « avant le jalon »)."""
    return {cle: gx.appliquer(img, cmd, timeout) for cle, img, cmd in items}

# ==================================== [1] bornes de parallele_max
print("[1] bornes de parallele_max (plafond, éléments, mémoire libre)")
verifie(gx.parallele_max(0) == 1 and gx.parallele_max(1) == 1,
        "0 ou 1 élément → série (jamais d'erreur, jamais de lancement vide)")
verifie(gx.parallele_max(9) == gx.MAX_PARALLELE,
        "9 éléments → plafond MAX_PARALLELE (%d)" % gx.MAX_PARALLELE)
_libre_reel = gx.memoire_libre
gx.memoire_libre = lambda: 512 << 20           # 512 Mo libres seulement
verifie(gx.parallele_max(3) == 1,
        "512 Mo libres → repli SÉRIE (un appel simultané réserve ~800 Mo)")
gx.memoire_libre = lambda: None                # sonde muette
verifie(gx.parallele_max(3) == gx.MAX_PARALLELE,
        "sonde muette → plafond nominal (jamais moins que prévu)")
gx.memoire_libre = _libre_reel
_libre = _libre_reel()
verifie(_libre is None or _libre > 0,
        "sonde RÉELLE : mémoire libre = %s Mo"
        % (int(_libre / 2**20) if _libre else "indéterminée"))

# ==================================== [2] lot parallèle (chevauchement)
print("[2] lot de 3 appels de 0,8 s : chevauchement réel et durée")
imgs = {r: image_test(graine=i) for i, r in enumerate("RGB")}
items = [(r, imgs[r], CMD) for r in "RGB"]
vide_journal()
t0 = time.perf_counter()
serie = en_serie(items)
t_serie = time.perf_counter() - t0
vide_journal()
t0 = time.perf_counter()
lot = gx.appliquer_lot(items)
t_par = time.perf_counter() - t0
lignes = journal()
chevau = chevauchement(lignes)
verifie(len(lignes) == 6,
        "journal : 3 « start » + 3 « end » (%d lignes)" % len(lignes))
verifie(chevau >= 2,
        "les appels sont RÉELLEMENT simultanés (maximum observé : %d)" % chevau)
verifie(t_par < 0.8 * t_serie,
        "durée parallèle %.2f s contre %.2f s en série (%.0f %% gagnés)"
        % (t_par, t_serie, 100 * (1 - t_par / t_serie)))

# ==================================== [3] égalité stricte (au bit)
print("[3] égalité STRICTE : lot parallèle = appels en série, au bit")
identiques = True
for r in "RGB":
    identiques = (identiques and lot[r][1] == serie[r][1]
                  and np.array_equal(lot[r][0], serie[r][0]))
verifie(identiques, "chaque rôle rend EXACTEMENT l'image qu'en série")
verifie(all(np.array_equal(lot[r][0],
                           np.asarray(imgs[r], np.float32) * 2.0)
            for r in "RGB"),
        "et c'est bien le résultat de l'OUTIL (entrée × 2), rôle par rôle")

# ==================================== [4] repli série (MAX_PARALLELE = 1)
print("[4] MAX_PARALLELE = 1 → comportement d'AVANT (strictement en série)")
_ancien = gx.MAX_PARALLELE
gx.MAX_PARALLELE = 1
vide_journal()
t0 = time.perf_counter()
lot1 = gx.appliquer_lot(items)
t1 = time.perf_counter() - t0
lignes1 = journal()
gx.MAX_PARALLELE = _ancien
verifie(chevauchement(lignes1) == 1 and len(lignes1) == 6,
        "avec MAX_PARALLELE = 1, deux appels ne se chevauchent JAMAIS")
verifie(all(np.array_equal(lot1[r][0], lot[r][0]) for r in "RGB"),
        "résultats identiques à ceux du lot parallèle (au bit)")
verifie(t1 > 1.5 * t_par,
        "et le repli est bien plus lent (%.2f s contre %.2f s)"
        % (t1, t_par))

# ==================================== [5] échec d'un élément
print("[5] échec d'un élément : les autres aboutissent, message exact")
items_kaput = [("R", imgs["R"], CMD),
               ("G", imgs["G"], "outil_inexistant_xyz {input} {output}"),
               ("B", imgs["B"], CMD)]
vide_journal()
lot2 = gx.appliquer_lot(items_kaput)
verifie(lot2["R"][1] == "" and lot2["B"][1] == "" and lot2["G"][1] != "",
        "R et B réussissent, G signale une erreur (« %s »)"
        % lot2["G"][1][:70])
verifie(np.array_equal(lot2["G"][0], imgs["G"]),
        "l'élément en échec rend l'image d'ENTRÉE (contrat d'`appliquer`)")


# ==================================== [6] et [7] chemin LIVE (le solveur)
print("[6] solveur live (composition RGB) : composite identique AU BIT")
from avastack.processing import display as dp_mod          # noqa: E402
from avastack.processing import veralux as vl_mod          # noqa: E402

IMG = image_test(160, 200, graine=9)
canaux = {"R": image_test(120, 160, 1), "G": image_test(120, 160, 2),
          "B": image_test(120, 160, 3)}


def solveur(parallele):
    """Solveur NEUF (caches vides) → (image affichée, solveur, journal)."""
    ancien = gx.MAX_PARALLELE
    gx.MAX_PARALLELE = parallele
    try:
        d = dp_mod.DisplayProcessor()
        d.stretch = "veralux"
        d.vl_mode_res = vl_mod.MODE_LOG_D    # déterministe (pas de logD auto)
        d.vl_log_d = 2.0
        d.vl_profil = vl_mod.PROFIL_PAR_DEFAUT
        d.vl_graxpert = True
        d.vl_graxpert_cmd = CMD_RAPIDE
        # Job de composition : (canaux, nom, gains, mode_l, fit, wb, norm)
        d.vl_compo = (dict(canaux), "RGB", None, None, None, None, False)
        vide_journal()
        d.notify_new_stack()
        d.process(IMG)
        t0 = time.time()
        while (d._vl_pending or d._vl_job is not None) \
                and time.time() - t0 < 60:
            time.sleep(0.01)
        d.process(IMG)
        res = (None if d._vl_result is None
               else np.asarray(d._vl_result[1]).copy())
        return res, d, journal()
    finally:
        gx.MAX_PARALLELE = ancien


res_serie, d_serie, lignes_serie = solveur(1)
res_par, d_par, lignes_par = solveur(max(2, gx.MAX_PARALLELE))
_n_serie = len([l for l in lignes_serie if l.startswith("start")])
_n_par = len([l for l in lignes_par if l.startswith("start")])
verifie(res_serie is not None and res_par is not None,
        "les deux solveurs rendent une image (composition RGB à 3 canaux)")
verifie(_n_serie == 3, "en série : l'outil est appelé UNE fois par couche "
        "(%d appels)" % _n_serie)
verifie(_n_par == 3, "en parallèle : MÊME nombre d'appels (%d) — le travail "
        "est identique" % _n_par)
verifie(chevauchement(lignes_par) >= 2,
        "en parallèle, les appels se chevauchent (maximum %d simultanés)"
        % chevauchement(lignes_par))
verifie(np.array_equal(res_serie, res_par),
        "image AFFICHÉE identique AU BIT avec et sans parallélisme (zéro pixel)")

print("[7] caches par rôle : un second rendu inchangé n'appelle RIEN")
vide_journal()
d_par.notify_new_stack()
d_par.process(IMG)
t0 = time.time()
while (d_par._vl_pending or d_par._vl_job is not None) \
        and time.time() - t0 < 60:
    time.sleep(0.01)
d_par.process(IMG)
verifie(journal() == [],
        "aucun appel d'outil (les caches GraXpert PAR RÔLE tiennent)")

# ==================================== [8] mémoire insuffisante → série
print("[8] mémoire libre insuffisante → repli série automatique")
gx.memoire_libre = lambda: 512 << 20
vide_journal()
lot3 = gx.appliquer_lot(items)
lignes3 = journal()
gx.memoire_libre = _libre_reel
verifie(chevauchement(lignes3) == 1 and len(lignes3) == 6,
        "avec 512 Mo libres, les appels repartent EN SÉRIE")
verifie(all(np.array_equal(lot3[r][0], lot[r][0]) for r in "RGB"),
        "résultats identiques (au bit) — le repli ne change que le calendrier")

# ==================================== [9] export pleine résolution
print("[9] export pleine résolution (_couches_pleine_resolution) : au bit")
root = tk.Tk()
root.withdraw()
ui.CONFIG = {}
ui.sauver_config = lambda d: None
app = ui.App(root)


class _Stacker:
    composition = "RGB"
    mode_l = None
    normalisation_commune = False


app.stacker = _Stacker()
reglages = {"vl_graxpert": True, "vl_graxpert_cmd": CMD_RAPIDE,
            "vl_denoise": False, "corr_gains": None, "corr_wb": False,
            "corr_wb_force": 1.0, "corr_cadre": None, "corr_fit": False,
            "corr_fit_mode": "offset"}
gx.MAX_PARALLELE = 1
vide_journal()
comp_serie, msg_serie = app._couches_pleine_resolution(canaux, reglages)
lignes_s = journal()
gx.MAX_PARALLELE = _ancien
vide_journal()
comp_par, msg_par = app._couches_pleine_resolution(canaux, reglages)
lignes_p = journal()
gx.MAX_PARALLELE = _ancien
verifie(comp_serie is not None and comp_par is not None,
        "les deux exports produisent un composite (%s)"
        % (msg_serie or msg_par or "aucun message"))
verifie(len([l for l in lignes_s if l.startswith("start")]) == 3
        and len([l for l in lignes_p if l.startswith("start")]) == 3,
        "3 appels d'outil dans les deux cas (un par couche)")
verifie(chevauchement(lignes_p) >= 2,
        "les 3 appels de l'export se chevauchent (maximum %d)"
        % chevauchement(lignes_p))
verifie(np.array_equal(comp_serie, comp_par),
        "composite EXPORTÉ identique AU BIT avec et sans parallélisme")
root.destroy()

shutil.rmtree(RACINE, ignore_errors=True)
print("\n" + ("BANC jalon 81 : OK" if ok else "BANC jalon 81 : ÉCHECS"))
sys.exit(0 if ok else 1)

