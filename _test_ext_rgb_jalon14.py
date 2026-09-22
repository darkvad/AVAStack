# -*- coding: utf-8 -*-
"""Test du jalon 14 — traitement externe RGB (convention FITS des outils).

Constat réel d'Alain (17/09/2026) : « Traiter l'empilement courant » sur un
empilement RGB (Uranus-C Pro) plantait GraXpert dès la 1re étape — boîte
modale cx_Freeze « cv2.error … !dsize.empty() in 'cv::hal::resize' ». Cause :
le lecteur FITS de GraXpert suppose les canaux sur NAXIS3 ((C, H, W)), alors
que la chaîne externe écrivait (H, W, C) ; la parade du chemin LIVE
(external/live.py, 14/09/2026) n'avait jamais été répercutée ici.

Vérifie sur la fenêtre RÉELLE (Tkinter), SANS toucher au vrai config.json :
  [1] helpers : round-trip (H, W, 3) → FITS canaux-en-tête → (H, W, 3),
      mono 2D inchangé ;
  [2] _run_external RÉEL mono : les outils voient (H, W), résultat ok ;
  [3] _run_external RÉEL RGB (GX → débruitage local → BXT) : les outils
      voient (3, H, W) canaux-en-tête à CHAQUE étape, résultat (H, W, 3),
      débruitage appliqué ;
  [4] outil qui plante (code != 0, stderr) : message d'erreur avec détail,
      état « error », ext_busy repassé à False — AUCUN blocage.

Nécessite un affichage. Exécution : python _test_ext_rgb_jalon14.py
"""
import os
import sys
import tempfile
import tkinter as tk

import numpy as np

import avastack.ui.app as ui
from avastack.external import live as gx_live
from avastack.images import load_image, save_image

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# Faux outil EXTERNE : journalise la FORME de l'entrée telle qu'il la voit
# (argv[4] = étiquette, argv[3] = journal) et écrit la sortie dans la
# convention du VRAI GraXpert (canaux sur NAXIS3 → (3, H, W) côté astropy).
FAKE_TOOL = r"""
import sys
import numpy as np
from astropy.io import fits
d = np.asarray(fits.getdata(sys.argv[1]), dtype=np.float32)
with open(sys.argv[3], "a", encoding="utf-8") as f:
    f.write(sys.argv[4] + " " + "x".join(map(str, d.shape)) + "\n")
fits.PrimaryHDU(d).writeto(sys.argv[2], overwrite=True)
"""

# Faux outil qui PLANTE comme le vrai GraXpert sur une entrée mal lue :
# message sur stderr + code de sortie non nul (boîte modale cx_Freeze réelle
# en dehors du test — ici on vérifie que la chaîne le SIGNALE sans bloquer).
FAKE_FAIL = ("import sys\n"
             "sys.stderr.write('cv2.error: !dsize.empty() in resize\\n')\n"
             "sys.exit(3)\n")

print("[1] Helpers : round-trip FITS canaux-en-tête")
rng = np.random.default_rng(14)
rgb = (rng.normal(0.05, 0.01, (48, 64, 3))).astype(np.float32)
rgb = np.clip(rgb, 0.0, None)
tmp = tempfile.mkdtemp(prefix="avastack_test_ext_")
f_rgb = os.path.join(tmp, "entree_rgb.fits")
gx_live._ecrire_entree(f_rgb, rgb)
# ce que voit un outil externe = astropy BRUT (load_image normalise
# désormais en (H, W, C) pour l'appli — correctif axes du 22/09/2026)
from astropy.io import fits as _fits
d = np.asarray(_fits.getdata(f_rgb), dtype=np.float32)
verifie(d.shape == (3, 48, 64),
        f"RGB écrit canaux-en-tête : l'outil voit {d.shape} (= (C, H, W))")
retour = gx_live._lire_sortie(f_rgb)
verifie(retour.shape == (48, 64, 3) and np.allclose(retour, rgb),
        "relecture normalisée : (H, W, 3), valeurs inchangées")
mono = np.abs(rng.normal(0.05, 0.01, (48, 64))).astype(np.float32)
f_mono = os.path.join(tmp, "entree_mono.fits")
gx_live._ecrire_entree(f_mono, mono)
dm = load_image(f_mono)
verifie(dm.shape == (48, 64) and np.allclose(dm, mono),
        f"mono 2D inchangé ({dm.shape})")

# --- Fenêtre réelle pour les _run_external ---------------------------------
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
ui.CONFIG = {}
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()

print("[2] _run_external RÉEL mono : convention (H, W), succès")
outil = os.path.join(tmp, "outil_simule.py")
journal = os.path.join(tmp, "journal.log")
with open(outil, "w", encoding="utf-8") as f:
    f.write(FAKE_TOOL)
with open(journal, "w", encoding="utf-8") as f:
    f.write("")
cmd_tpl = f'"{sys.executable}" "{outil}" "{{input}}" "{{output}}" "{journal}"'
stack_m = np.clip(rng.normal(0.05, 0.01, (48, 64)), 0, None).astype(np.float32)
app.ext_job = (True, cmd_tpl + " GX_M", False, "", True, cmd_tpl + " BXT_M",
               "nlm", 0.5)
app._session = 0
app._run_external(stack_m, 7, 0)
root.update_idletasks()
ordre = [l.strip() for l in open(journal, encoding="utf-8") if l.strip()]
verifie(ordre == ["GX_M 48x64", "BXT_M 48x64"],
        f"mono : les 2 outils voient (H, W) ({ordre})")
verifie(app.proc_full is not None and app.proc_full.shape == stack_m.shape
        and app.ext_state == "ok",
        "mono : résultat produit, ext_state='ok'")

print("[3] _run_external RÉEL RGB : canaux-en-tête à CHAQUE étape")
with open(journal, "w", encoding="utf-8") as f:
    f.write("")
stack = np.stack([(lambda a: a / a.max())(
    np.clip(rng.normal(0.05, 0.02, (48, 64)), 0, None).astype(np.float32)
) for _ in range(3)], axis=2)
app.ext_job = (True, cmd_tpl + " GX_RGB",
               True, "",                       # débruitage LOCAL en mémoire
               True, cmd_tpl + " BXT_RGB",
               "nlm", 0.5)
app._run_external(stack, 12, 0)
root.update_idletasks()
ordre = [l.strip() for l in open(journal, encoding="utf-8") if l.strip()]
verifie(ordre == ["GX_RGB 3x48x64", "BXT_RGB 3x48x64"],
        f"RGB : les 2 outils voient (3, H, W) canaux-en-tête ({ordre}) "
        f"— C'ÉTAIT LE CRASH")
verifie(app.proc_full is not None and app.proc_full.shape == stack.shape,
        f"RGB : résultat (H, W, 3) produit ({app.proc_full.shape})")
verifie(app.ext_state == "ok" and "Traité à" in app.ext_msg,
        "RGB : message de succès")
# le débruitage local a bien tourné (sur la copie traitée, pas sur le stack)
verifie(not np.allclose(app.proc_full, stack),
        "RGB : l'image traitée diffère de l'entrée (chaîne appliquée)")

print("[4] Outil qui plante : message avec détail, AUCUN blocage")
fail_script = os.path.join(tmp, "outil_plante.py")
with open(fail_script, "w", encoding="utf-8") as f:
    f.write(FAKE_FAIL)
cmd_fail = f'"{sys.executable}" "{fail_script}" "{{input}}" "{{output}}"'
app.ext_job = (True, cmd_fail, False, "", False, "", "nlm", 0.5)
app._run_external(stack, 12, 0)
root.update_idletasks()
verifie(app.ext_state == "error", "outil planté → ext_state='error'")
verifie("dsize.empty()" in app.ext_msg and "Erreur" in app.ext_msg,
        f"message d'erreur avec le détail stderr (« {app.ext_msg[:70]}… »)")
verifie(app.ext_busy is False, "ext_busy repassé à False (pas de blocage)")

root.destroy()
import shutil
shutil.rmtree(tmp, ignore_errors=True)

print()
print("JALON 14 : " + ("TOUS LES TESTS PASSENT" if ok
                       else "ÉCHECS — à corriger"))
sys.exit(0 if ok else 1)