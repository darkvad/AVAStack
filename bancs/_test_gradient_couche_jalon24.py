# -*- coding: utf-8 -*-
"""Jalon 24 — gradient et débruitage PAR COUCHE (live ET externe).

Décision d'Alain du 19/09/2026 : en composition, GraXpert gradient et
débruitage sont faits sur CHAQUE couche AVANT la recomposition (la pollution
lumineuse et la lune ne frappent pas pareil selon le filtre ; une palette
Hubble n'est pas un fond physique). La netteté reste SUR LE COMPOSITE
(PSF identique pour toutes les couches, meilleur SNR après débruitage).

Vérifie :
  - composition.mean_avec_canaux() : (composite, canaux) cohérents ;
  - solveur live : gradient + débruitage par couche (cache par rôle — les
    couches non modifiées sont servies par le cache), composite re-fait ;
  - sans compo → chaîne composite inchangée (jalons 4/9) ;
  - _run_external RÉEL en composition : FITS 2D MONO à chaque étape ;
  - repli : échec d'une étape → message clair, jamais de blocage.

Nécessite un affichage. Exécution : python bancs/_test_gradient_couche_jalon24.py
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
import tempfile
import time
import tkinter as tk

import numpy as np

import avastack.ui.app as ui
import avastack.processing.display as dp
import avastack.processing.veralux as veralux
from avastack.processing.composition import CompositeStacker, composer

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def resoudre(d, img, max_s=30.0):
    """Soumet et attend la fin du calcul VeraLux (cf. tests jalons 3+)."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < max_s:
        d.process(img.copy())
        time.sleep(0.02)
        with d._vl_lock:
            if not d._vl_pending and d._vl_job is None:
                return True
    return False


def champ(seed, h=48, w=64):
    """Ciel simulé BRUITÉ (piège jalon 21 : sans bruit, 0 étoile)."""
    r = np.random.default_rng(seed)
    return np.clip(r.normal(0.05, 0.01, (h, w)), 0, None).astype(np.float32)


print("[1] mean_avec_canaux : composite + couches cohérents")
fa = CompositeStacker("HOO", k=None)
fa.role_courant = "Ha"
fa.add(champ(1))
fa.role_courant = "O3"
fa.add(champ(2))
comp, canaux = fa.mean_avec_canaux()
verifie(comp is not None and comp.shape == (48, 64, 3),
        f"composite (H, W, 3) ({None if comp is None else comp.shape})")
verifie(set(canaux) == {"Ha", "O3"}
        and all(c.shape == (48, 64) for c in canaux.values()),
        "canaux : dict rôle → carte 2D, formes identiques")
verifie(np.allclose(comp, composer(canaux, "HOO")),
        "composite = composer(canaux) (une seule passe)")

# --- Outil factice : copie pure + journal de la forme vue -------------------
tmp = tempfile.mkdtemp(prefix="avastack_test_j24_")
outil = os.path.join(tmp, "outil_copie.py")
journal = os.path.join(tmp, "journal.log")
with open(outil, "w", encoding="utf-8") as f:
    f.write("import sys\n"
            "import numpy as np\n"
            "from astropy.io import fits\n"
            "d = np.asarray(fits.getdata(sys.argv[1]), dtype=np.float32)\n"
            "with open(sys.argv[3], 'a', encoding='utf-8') as fh:\n"
            "    fh.write('x'.join(map(str, d.shape)) + '\\n')\n"
            "fits.PrimaryHDU(d).writeto(sys.argv[2], overwrite=True)\n")
cmd_tpl = (f'"{sys.executable}" "{outil}" "{{input}}" "{{output}}" '
           f'"{journal}"')

# Fenêtre réelle, hermétique (ni config, ni sauvegarde — pièges jalon 20).
sauvegardes = []
ui.sauver_config = lambda d: sauvegardes.append(dict(d))
ui.CONFIG = {}
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()

print("[2] Solveur live : gradient + débruitage PAR COUCHE, caches par rôle")
with open(journal, "w", encoding="utf-8") as f:
    f.write("")
d = dp.DisplayProcessor()
d.stretch = "veralux"
d.vl_mode_res = veralux.MODE_LOG_D
d.vl_log_d = 2.0
canaux = {"Ha": champ(3), "O3": champ(4)}
comp_ref = composer(canaux, "HOO")
params = dict(mode=d.vl_mode_res, target_bg=0.25, log_d=2.0,
              profil=d.vl_profil)
d._vl_job = (comp_ref.copy(), params, "k24", (True, cmd_tpl),
             (True, "ondelettes", 0.5), (False, 3), (),
             (dict(canaux), "HOO", None, "synthetise"))
d._vl_pending = True
d._vl_wake.set()
fini = resoudre(d, comp_ref)
ordre = [l.strip() for l in open(journal, encoding="utf-8") if l.strip()]
verifie(fini and d.vl_error == "",
        f"solveur : chaîne par couche sans erreur ({d.vl_error[:80]!r})")
verifie(all("48x64" in o for o in ordre),
        f"outils appelés sur des couches 2D ({ordre})")
verifie(len(ordre) == 2,
        f"gradient : 1 exécution par couche, 2 couches ({ordre})")
verifie(set(d._gx_couches) == {"Ha", "O3"}
        and set(d._dn_couches) == {"Ha", "O3"},
        "caches par rôle remplis (gradient + débruitage)")

print("[3] Live : seule la couche modifiée est relancée")
with open(journal, "w", encoding="utf-8") as f:
    f.write("")
canaux2 = {"Ha": champ(3), "O3": champ(5)}          # seule O3 change
comp2 = composer(canaux2, "HOO")
d._vl_job = (comp2.copy(), params, "k24b", (True, cmd_tpl),
             (True, "ondelettes", 0.5), (False, 3), (),
             (dict(canaux2), "HOO", None, "synthetise"))
d._vl_pending = True
d._vl_wake.set()
resoudre(d, comp2)
ordre2 = [l.strip() for l in open(journal, encoding="utf-8") if l.strip()]
verifie(len(ordre2) == 1,
        f"une seule exécution : la couche modifiée seule ({ordre2})")

print("[4] Live mono SANS compo : chaîne composite inchangée (jalons 4/9)")
with open(journal, "w", encoding="utf-8") as f:
    f.write("")
mono = champ(6)
d2 = dp.DisplayProcessor()
d2.stretch = "veralux"
d2.vl_mode_res = veralux.MODE_LOG_D
d2.vl_log_d = 2.0
d2._vl_job = (mono.copy(), dict(mode=d2.vl_mode_res, target_bg=0.25,
                                log_d=2.0, profil=d2.vl_profil),
              "k24c", (True, cmd_tpl), (False, "nlm", 0.5), (False, 3), ())
d2._vl_pending = True
d2._vl_wake.set()
verifie(resoudre(d2, mono),
        "sans compo : résolution terminée, chaîne composite")
verifie("48x64" in open(journal, encoding="utf-8").read(),
        "sans compo : GraXpert live sur le composite, comme avant")

print("[5] _run_external RÉEL en composition : FITS mono par couche")
with open(journal, "w", encoding="utf-8") as f:
    f.write("")
app._mode_compo = True
fa.gains, fa.mode_l = None, "synthetise"
app.stacker = fa
comp_full, canaux_full = fa.mean_avec_canaux()
# v2.48.0 (jalon 85) : plus de cases couleur dans le job externe (elles suivent
# l'étirement) — les quatre derniers éléments sont la neutralisation du fond
# (9e, cochée par défaut), le bruit chromatique (10e, opt-in), sa FORCE (11e)
# et le RAYON DE RÉFÉRENCE du flou de chroma (12e).
app.ext_job = (True, cmd_tpl + " GX_C", True, "", False, "", "nlm", 0.5,
               True, False, 0.5, 3.0)
app._session = 0
app._run_external(comp_full, 2, 0)
root.update_idletasks()
ordre3 = [l.strip() for l in open(journal, encoding="utf-8") if l.strip()]
verifie(ordre3 == ["48x64", "48x64"],
        f"externe : gradient sur CHAQUE couche, en 2D MONO ({ordre3})")
verifie(app.proc_full is not None
        and app.proc_full.shape == comp_full.shape,
        f"externe : composite traité (H, W, 3) ({app.proc_full.shape})")
verifie(app.ext_state in ("ok", "busy")
        and "par couche" in app.ext_msg,
        f"externe : message de succès ({app.ext_msg[:70]})")

print("[6] Externe : échec d'une étape → message clair, aucun blocage")
fail = os.path.join(tmp, "plante.py")
with open(fail, "w", encoding="utf-8") as f:
    f.write("import sys\nsys.exit(3)\n")
cmd_fail = f'"{sys.executable}" "{fail}" "{{input}}" "{{output}}"'
app.ext_job = (True, cmd_fail, False, "", False, "", "nlm", 0.5,
               True, False, 0.5, 3.0)        # mêmes réglages que ci-dessus
app._run_external(comp_full, 2, 0)
root.update_idletasks()
verifie(app.ext_state == "error",
        f"échec d'une étape par couche → erreur ({app.ext_msg[:60]})")
verifie(app.ext_busy is False, "ext_busy repassé à False (pas de blocage)")

root.destroy()
import shutil
shutil.rmtree(tmp, ignore_errors=True)

print()
print("JALON 24 : " + ("TOUS LES TESTS PASSENT" if ok
                     else "ÉCHECS — à corriger"))
sys.exit(0 if ok else 1)
