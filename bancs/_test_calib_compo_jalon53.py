# -*- coding: utf-8 -*-
"""Test du jalon 53 — dark/flat UNIQUE ou PAR COUCHE en mode composition.

Vérifie :
  [1] Calibrator seul : dark/flat par rôle (repli sur l'unique pour un
      rôle sans master), cibles INDÉPENDANTES dark vs flat, clear() vide
      tout, compatibilité mono inchangée (signature historique apply(img)) ;
  [2] UI (App réelle, Tk) : la couche se choisit AU CLIC sur « Charger un
      dark/flat… » via une boîte modale (Unique + couches actives) —
      hors composition, pas de dialogue ; libellés DÉTAILLÉS (unique +
      chaque couche, « — » si le master manque) ; annulation sans effet ;
      masters conservés aux allers-retours de source ;
  [3] worker réel (MultiFolderCamera, dossiers temporaires Ha/O3) : la
      calibration PAR RÔLE est appliquée à chaque frame — le dark DÉDIÉ de
      chaque couche est soustrait, pas le dark unique, pas celui du voisin.

Le chemin mono ne doit PAS changer : les autres _test_*.py restent verts.
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
import threading
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
from avastack.processing.calibration import Calibrator
from avastack.cameras.multifolder import MultiFolderCamera
from avastack.processing.composition import composition_pour_roles
from avastack.images import save_image

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CFA_MODE_AVANT = images.CFA_MODE
images.CFA_MODE = "Non"                  # brutes mono dans ce test

H, W = 200, 260
ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK  " if cond else "  ÉCHEC ") + msg)


_ETOILES = None


def champ(dx=0.0, dy=0.0, fond=0.05, graine=0):
    """Carte float32 (H, W) : fond BRUITÉ + étoiles gaussiennes translatées
    (cf. _test_compo_worker_jalon19.py : le bruit est indispensable à la
    détection d'étoiles en chemin TRIANGLES)."""
    global _ETOILES
    rng = np.random.default_rng(7)
    if _ETOILES is None:
        _ETOILES = [(rng.uniform(15, W - 15), rng.uniform(15, H - 15),
                     rng.uniform(0.4, 0.9)) for _ in range(30)]
    img = np.full((H, W), fond, np.float32)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    for (sx, sy, f) in _ETOILES:
        xx, yy = sx + dx, sy + dy
        img += f * np.exp(-((x - xx) ** 2 + (y - yy) ** 2)
                          / (2.0 * 1.2 ** 2)).astype(np.float32)
    img += np.random.default_rng(100 + graine).normal(
        0, 0.004, img.shape).astype(np.float32)
    return img


# ====================================================== [1] Calibrator seul
print("[1] Calibrator : dark/flat par rôle, repli unique, indépendance")
cal = Calibrator()
# Darks/flats CONSTANTES pleines : la moyenne est exactement connue, aucun
# artefact d'étoiles ni de bruit ne pollue les vérifications.
d_ha = np.full((H, W), 0.02, np.float32)         # dark Ha : 0.02
d_o3 = np.full((H, W), 0.06, np.float32)         # dark O3 : 0.06
f_ha = np.full((H, W), 0.8, np.float32)          # flat Ha (atténue de 20 %)
rac = tempfile.mkdtemp(prefix="avastack_j53_")
p_dha = os.path.join(rac, "dark_ha.fit"); save_image(p_dha, d_ha)
p_do3 = os.path.join(rac, "dark_o3.fit"); save_image(p_do3, d_o3)
p_dun = os.path.join(rac, "dark_unique.fit")
save_image(p_dun, np.full((H, W), 0.10, np.float32))
p_fha = os.path.join(rac, "flat_ha.fit"); save_image(p_fha, f_ha)
p_fun = os.path.join(rac, "flat_unique.fit")
save_image(p_fun, np.full((H, W), 1.0, np.float32))
cal.load_dark(p_dha, role="Ha")
cal.load_dark(p_do3, role="O3")
cal.load_dark(p_dun)                              # unique
cal.load_flat(p_fha, role="Ha")
cal.load_flat(p_fun)                              # unique (neutre : 1.0)
verifie(set(cal.darks) == {"Ha", "O3"} and set(cal.flats) == {"Ha"}
        and cal.dark is not None and cal.flat is not None,
        "masters rangés : darks {Ha, O3} + unique, flats {Ha} + unique")

# apply() avec rôle : dark DU RÔLE soustrait (0.06 pour O3, pas 0.10).
img = champ(0, 0, fond=0.20, graine=4)
m_img = float(img.mean())
out_o3 = cal.apply(img.copy(), role="O3")
verifie(abs(float(out_o3.mean()) - (m_img - 0.06)) < 2e-3,
        "O3 : le dark DÉDIÉ (0.06) est soustrait, pas l'unique")
out_ha = cal.apply(img.copy(), role="Ha")
# Un flat CONSTANT est NEUTRE par construction (normalisé par sa propre
# médiane) — il ne doit RIEN changer : preuve qu'un flat par rôle ne
# déforme pas. Le VRAI test du flat (atténuation réelle) suit ci-dessous
# avec un flat non constant, chargé PAR RÔLE.
cal2 = Calibrator()
cal2.load_flat(p_fha, role="Ha")           # 0.8 constant → neutre aussi
out2 = cal2.apply(img.copy(), role="Ha")
verifie(np.array_equal(out2, np.clip(img, 0, None)),
        "flat constant (par rôle) appliqué → neutre (normalisation médiane)")
# Flat NON constant, PAR RÔLE : atténuation réelle à gauche, jamais à droite.
grad = np.concatenate([np.full((H, W // 2), 0.5, np.float32),
                       np.full((H, W - W // 2), 1.5, np.float32)], axis=1)
p_fgrad = os.path.join(rac, "flat_grad.fit"); save_image(p_fgrad, grad)
cal2.load_flat(p_fgrad, role="O3")
out3 = cal2.apply(img.copy(), role="O3")
gauche = float(out3[:, :W // 2].mean() / np.clip(img[:, :W // 2], 0, None).mean())
droite = float(out3[:, W // 2:].mean() / img[:, W // 2:].mean())
verifie(abs(gauche - 2.0) < 0.05 and abs(droite - (2.0 / 3.0)) < 0.05,
        "flat NON constant par rôle : moitié sombre ×2, moitié claire ×2/3 "
        "(normalisation médiane 1.0)")
verifie(abs(float(out_ha.mean()) - (m_img - 0.02)) < 2e-3,
        "Ha : dark dédié (0.02) appliqué (flat constant → neutre)")
# Rôle SANS master dédié → repli sur l'unique (0.10).
out_l = cal.apply(img.copy(), role="L")
verifie(abs(float(out_l.mean()) - (m_img - 0.10)) < 2e-3,
        "L (sans dark dédié) : REPLI sur le dark unique (0.10)")
# apply() sans rôle : comportement historique (unique uniquement).
out_mono = cal.apply(img.copy())
verifie(abs(float(out_mono.mean()) - (m_img - 0.10)) < 2e-3,
        "sans rôle (mono) : dark unique seul, comportement inchangé")
# Forme incompatible : master ignoré (règle historique).
petit = champ(0, 0)[:100, :100]
verifie(np.array_equal(cal.apply(petit.copy(), role="Ha"), petit),
        "forme incompatible → master ignoré (jamais d'exception)")
cal.clear()
verifie(cal.dark is None and cal.flat is None and not cal.darks
        and not cal.flats, "clear() : uniques ET dictionnaires vidés")

# ================================================================ [2] UI
print("[2] UI : choix de la couche AU CLIC, libellés détaillés")
import avastack.ui.app as ui

root = tk.Tk()
root.withdraw()
import avastack.ui.app as ui
# Test HERMÉTIQUE (piège config.json — cf. _test_compo_ui_jalon19) : la
# vraie config d'Alain peut contenir des rôles/dossiers réels qui
# réactiveraient des combobox avant l'heure. Config vierge simulée +
# sauvegarde interceptée : jamais toucher au vrai fichier.
ui.CONFIG = {}
ui.sauver_config = lambda d: None
app = ui.App(root)

# Hors composition : PAS de dialogue, cible « unique » directe.
verifie(app._choisir_cible("dark") == "unique"
        and app._choisir_cible("flat") == "unique",
        "hors composition : aucun dialogue, cible « unique » directe")
verifie(app.lbl_dark.cget("text") == "Dark unique : —"
        and app.lbl_flat.cget("text") == "Flat unique : —",
        "libellés initiaux : « Dark unique : — » / « Flat unique : — »")

# Passage en composition : le choix se fait AU CLIC via la boîte modale.
app.var_source.set("Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
app._maj_visibilite_cadres()
root.update_idletasks()
verifie(app._roles_actifs() == ["Ha", "O3"],
        "composition HOO par défaut : couches actives Ha, O3")


def _repond(valeur):
    """Répond automatiquement à la boîte modale (test) : sélectionne la
    cible et valide pendant que wait_window tourne."""
    def _go():
        app._dlg_var.set(valeur)
        app._dlg_ok()
    return _go


def _ligne(txt, pref):
    for l in txt.splitlines():
        if l.startswith(pref):
            return l
    return ""

# Dark chargé pour la couche « Ha » (réponse de la boîte au clic).
p_d1 = os.path.join(rac, "d1.fit")
save_image(p_d1, champ(0, 0, fond=0.03))
p_f1 = os.path.join(rac, "f1.fit")
save_image(p_f1, np.full((H, W), 0.9, np.float32))
ui.filedialog.askopenfilename = lambda **k: p_d1
root.after(200, _repond("Ha"))
app._load_dark()
verifie(set(app.calib.darks) == {"Ha"}
        and app.calib.darks_sources.get("Ha") == p_d1,
        "boîte modale : dark rangé pour la couche choisie (Ha), source notée")
txt_d = app.lbl_dark.cget("text")
verifie(_ligne(txt_d, "Dark unique") == "Dark unique : —"
        and _ligne(txt_d, "Dark Ha").startswith("Dark Ha : ")
        and _ligne(txt_d, "Dark Ha") != "Dark Ha : —"
        and _ligne(txt_d, "Dark O3") == "Dark O3 : —",
        "libellé dark : unique —, Ha chargé, O3 manquant (—) TOUS affichés")

# Flat UNIQUE (réponse « unique » de la boîte) : indépendant des darks.
ui.filedialog.askopenfilename = lambda **k: p_f1
root.after(200, _repond("unique"))
app._load_flat()
verifie(app.calib.flat is not None and not app.calib.flats,
        "boîte modale : réponse « unique » → master UNIQUE, dictionnaire vide")
txt_f = app.lbl_flat.cget("text")
verifie(_ligne(txt_f, "Flat unique") != "Flat unique : —"
        and _ligne(txt_f, "Flat Ha") == "Flat Ha : —"
        and _ligne(txt_f, "Flat O3") == "Flat O3 : —",
        "libellé flat : unique chargé, Ha et O3 manquants (—)")
# Flat PAR COUCHE aussi (réponse « O3 ») : unique ET O3 coexistent.
p_f2 = os.path.join(rac, "f2.fit")
save_image(p_f2, np.full((H, W), 1.2, np.float32))
ui.filedialog.askopenfilename = lambda **k: p_f2
root.after(200, _repond("O3"))
app._load_flat()
verifie(set(app.calib.flats) == {"O3"} and app.calib.flat is not None,
        "flats : unique ET O3 chargés, indépendamment des darks")
txt_f = app.lbl_flat.cget("text")
verifie(_ligne(txt_f, "Flat unique") != "Flat unique : —"
        and _ligne(txt_f, "Flat O3").startswith("Flat O3 : ")
        and _ligne(txt_f, "Flat O3") != "Flat O3 : —"
        and _ligne(txt_f, "Flat Ha") == "Flat Ha : —",
        "libellé flat : unique ✓, O3 ✓, Ha manquant (—) TOUS affichés")

# Annulation de la boîte (croix/Annuler) → AUCUN chargement.
avant = dict(app.calib.darks)
root.after(200, lambda: app._dlg.destroy())
app._load_dark()
verifie(app.calib.darks == avant,
        "boîte annulée → aucun chargement, rien n'est modifié")

# Retour hors composition : libellé simple (une ligne) ; les masters par
# rôle restent en mémoire et réapparaissent au retour en composition.
app.var_source.set("Dossier surveillé (brutes FITS/PNG/TIFF…)")
app._maj_visibilite_cadres()
root.update_idletasks()
verifie(app.lbl_dark.cget("text").count("\n") == 0
        and app.lbl_dark.cget("text").startswith("Dark unique : "),
        "retour hors composition : libellé simple, une seule ligne")
verifie(set(app.calib.darks) == {"Ha"} and set(app.calib.flats) == {"O3"},
        "masters par rôle conservés en mémoire")
app.var_source.set("Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
app._maj_visibilite_cadres()
root.update_idletasks()
verifie(_ligne(app.lbl_dark.cget("text"), "Dark Ha").startswith("Dark Ha : ")
        and _ligne(app.lbl_flat.cget("text"), "Flat O3").startswith("Flat O3 : "),
        "retour en composition : les masters par rôle réapparaissent")

# =========================================================== [3] worker réel
print("[3] worker réel : calibration PAR RÔLE appliquée aux empilements")
from avastack.processing.framestore import ArchiveFrames as _ArchiveFrames


class ArchiveRapide(_ArchiveFrames):
    """Archive sans limite de débit (test) — cf. _test_compo_worker_jalon19."""

    def __init__(self, *a, **k):
        k.setdefault("intervalle_s", 0.0)
        super().__init__(*a, **k)


ui.ArchiveFrames = ArchiveRapide

d_ha_w = os.path.join(rac, "Ha_w"); os.makedirs(d_ha_w)
d_o3_w = os.path.join(rac, "O3_w"); os.makedirs(d_o3_w)
N = 3
for i in range(N):
    save_image(os.path.join(d_ha_w, f"ha_{i}.fits"),
               champ(0.0, 0.0, fond=0.15, graine=10 + i))
    save_image(os.path.join(d_o3_w, f"o3_{i}.fits"),
               champ(0.0, 0.0, fond=0.15, graine=60 + i))
time.sleep(1.3)                      # taille stable + mtime > 0,5 s (folder)

root2 = tk.Tk()
root2.withdraw()
app2 = ui.App(root2)
app2.rejeter_flou = False
app2.ref_refresh = 0


class _Val:
    """Bouchon de variable Tk : var.get() interdit hors thread principal
    (cf. _test_compo_worker_jalon19.py)."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


app2.var_wb = _Val(False)
app2.var_wb_force = _Val(1.0)
cam = MultiFolderCamera([("Ha", d_ha_w), ("O3", d_o3_w)])
cam.open()
app2.camera = cam
app2._mode_compo = True
app2._compo_nom = composition_pour_roles(cam.roles)

# Calibration PAR COUCHE : dark Ha dédié (fond 0.02), dark O3 dédié
# (fond 0.06) — le worker doit soustraire LE BON dark pour chaque couche,
# et PAS le dark unique (0.10) qui est aussi chargé (repli L seulement).
app2.calib.load_dark(p_dha, role="Ha")
app2.calib.load_dark(p_do3, role="O3")
app2.calib.load_dark(p_dun)                    # unique : utilisé par L seul
app2.calib.load_flat(p_fun)                    # 1.0 → neutre

app2.running = True
app2.empilement_on = True
th = threading.Thread(target=app2._worker, daemon=True)
th.start()

t0 = time.time()
while time.time() - t0 < 60:
    if app2.stacker is not None and app2.stacker.n >= 2 * N:
        break
    try:
        app2.q.get(timeout=0.5)
    except Exception:
        pass
time.sleep(0.5)

verifie(app2.stacker is not None and app2.stacker.n == 2 * N,
        "worker : 6 frames empilées (3 Ha + 3 O3)")
if app2.stacker is not None and app2.stacker.n == 2 * N:
    moy = app2.stacker.moyennes()          # {rôle: carte 2D du canal}
    # Les brutes ont un fond de 0.15 ; le dark Ha dédié retire 0.02 → le
    # stack Ha doit tourner autour de 0.13. Avec le dark UNIQUE (0.10) on
    # mesurerait ~0.05 ; sans dark, ~0.15.
    fond_ha = float(np.median(moy["Ha"]))
    fond_o3 = float(np.median(moy["O3"]))
    verifie(abs(fond_ha - 0.13) < 0.01,
            f"couche Ha : dark DÉDIÉ appliqué (fond ≈ 0.13, mesuré "
            f"{fond_ha:.3f})")
    verifie(abs(fond_o3 - 0.09) < 0.01,
            f"couche O3 : dark DÉDIÉ appliqué (fond ≈ 0.09, mesuré "
            f"{fond_o3:.3f})")
    verifie(abs(fond_ha - fond_o3) > 0.02,
            "les deux couches ne partagent PAS le même dark (calibration "
            "par couche prouvée)")

app2.running = False
th.join(timeout=5)
cam.close()
root.destroy()
root2.destroy()
shutil.rmtree(rac, ignore_errors=True)
images.CFA_MODE = CFA_MODE_AVANT
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
