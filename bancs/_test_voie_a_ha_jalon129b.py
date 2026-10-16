# -*- coding: utf-8 -*-
"""Banc du JALON 129b — VOIE A : le Ha FUSIONNÉ s'aligne sur LUI-MÊME.

Contexte (MESURÉ le 15/10/2026, rejeu des vraies frames M33) : en composition
BROADBAND+Ha, le Ha (bande 7 nm, retourné ~180°) ne partage que ~6 étoiles avec
le L — pile le minimum des triangles (`TRI_INLIERS_MIN = 6`) que la consolidation
fait tomber : `compute()` refuse **0/5** aligné contre une ancre broadband,
contre **4/4** aligné sur lui-même, et le recalage « Ha empilé → composite »
passe **5/5**. La voie A retenue est donc : référence PAR RÔLE (le Ha s'aligne
sur lui-même) puis UN SEUL recalage de l'EMPILEMENT Ha sur le composite.

Vérifie :
  [1] `role_ha_fusionne()` : "Ha" pour RGB+Ha et LRGB+Ha ; None pour HOO/SHO/
      RGB/LRGB/Mono (en HOO/SHO le Ha EST un canal) ;
  [2] `profondeur_min()` : le Ha FUSIONNÉ est EXCLU (c'est le seuil de
      l'astrométrie, de la photo ET de la SPCC) — le Ha d'un HOO/SHO compte
      toujours, et les compositions existantes ne changent pas ;
  [3] RECALAGE d'empilement : `set_recalage` + `moyennes()` ramènent la couche
      du rôle dans la grille du composite par UNE transformation, et
      `note_alignement(role=<Ha fusionné>)` n'entre PAS dans le cadre commun
      (alors qu'en HOO il y entre) ;
  [4] VOIE A en SESSION RÉELLE (worker + MultiFolderCamera, 5 dossiers) : les
      brutes Ha passent par l'aligneur DÉDIÉ (jamais par l'aligneur partagé) et
      sont EMPILÉES là où le TÉMOIN hors-ligne montre qu'elles seraient
      refusées ; les refus sont comptés PAR RÔLE ; le re-stack compo rejoue le
      Ha dans son propre repère ;
  [5] RECALAGE Ha → composite avec un VRAI aligneur : un empilement Ha décalé
      revient sur la grille du composite (le résidu au champ attendu DIVISE) ;
  [6] LIBELLÉ « frames par rôle » de la SPCC (et de la photo) : la profondeur
      annoncée est celle des BANDES MESURÉES (R/G/B), pas le MINIMUM (le Ha
      fusionné, que la mesure ne touche pas) ;
  [7] NON-RÉGRESSION : HOO/SHO inchangés (voie A fausse, Ha compté, aligneur
      partagé pour TOUS les rôles).

Exécution : python bancs/_test_voie_a_ha_jalon129b.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
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
import avastack.ui.app as ui
from avastack.cameras.multifolder import MultiFolderCamera
from avastack.processing import StarAligner
from avastack.processing.alignment import infos_M
from avastack.processing.composition import (CompositeStacker,
                                             role_ha_fusionne)
from avastack.processing.spcc import texte_resume as spcc_texte
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


# `_detecter_filtres()` se termine par `_dire(...)` — boîte MODALE : elle
# bloquerait le banc indéfiniment (constaté). Neutralisée sur la CLASSE.
ui.App._dire = lambda self, *a, **k: None


# --- deux champs d'étoiles SANS étoile commune (broadband vs Ha) ------------
def _etoiles(graine, n=30):
    rng = np.random.default_rng(graine)
    return [(rng.uniform(15, W - 15), rng.uniform(15, H - 15),
             rng.uniform(0.4, 0.9)) for _ in range(n)]


_ETOILES_A = _etoiles(11)      # champ BROADBAND
_ETOILES_B = _etoiles(29)      # champ Ha : AUCUNE étoile commune avec A


def champ(etoiles, dx=0.0, dy=0.0, fond=0.05, graine=0, bruit=0.004):
    """Carte float32 (H, W) : fond BRUITÉ + étoiles gaussiennes translatées.
    Le bruit est INDISPENSABLE (la détection médiane-MAD refuse « image
    constante » sans lui, cf. banc jalon 19)."""
    img = np.full((H, W), fond, np.float32)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    for (sx, sy, f) in etoiles:
        xx, yy = sx + dx, sy + dy
        img += f * np.exp(-((x - xx) ** 2 + (y - yy) ** 2)
                          / (2.0 * 1.2 ** 2)).astype(np.float32)
    img += np.random.default_rng(1000 + graine).normal(
        0, bruit, img.shape).astype(np.float32)
    return img


def carte(graine, fond=0.05, h=48, w=64):
    """Petite carte 2D bruitée (bornes de normalisation non dégénérées)."""
    rng = np.random.default_rng(graine)
    return (fond + rng.normal(0.0, 0.01, (h, w))).astype(np.float32)


def compo(nom, roles_frames):
    """CompositeStacker peuplé de `roles_frames[rôle]` frames par rôle."""
    st = CompositeStacker(nom, k=None)
    for role, n in roles_frames.items():
        for i in range(n):
            st.add(carte(10 + i), role=role)
    return st


# ================================================== [1] rôle Ha fusionné
print("[1] role_ha_fusionne : Ha FUSIONNÉ (hors canaux) vs Ha CANAL")
verifie(role_ha_fusionne("RGB+Ha") == "Ha"
        and role_ha_fusionne("LRGB+Ha") == "Ha",
        "RGB+Ha / LRGB+Ha → « Ha » (le Ha n'alimente aucun canal)")
verifie(role_ha_fusionne("HOO") is None
        and role_ha_fusionne("SHO") is None,
        "HOO / SHO → None (le Ha EST un canal : R en HOO, G en SHO)")
verifie(role_ha_fusionne("RGB") is None and role_ha_fusionne("LRGB") is None
        and role_ha_fusionne("Mono") is None,
        "RGB / LRGB / Mono → None (aucun Ha)")


# ============================================ [2] profondeur_min (le verrou)
print("[2] profondeur_min : le Ha FUSIONNÉ ne pend plus au seuil des mesures")
st_lrgbha = compo("LRGB+Ha", {"L": 25, "R": 30, "G": 29, "B": 20, "Ha": 1})
verifie(st_lrgbha.n == 105 and st_lrgbha.profondeur_min() == 20,
        f"LRGB+Ha (L25 R30 G29 B20 Ha1) → profondeur_min = 20 (le Ha est "
        f"EXCLU) — reçu {st_lrgbha.profondeur_min()}")
st_rgbha = compo("RGB+Ha", {"R": 14, "G": 14, "B": 14, "Ha": 1})
verifie(st_rgbha.profondeur_min() == 14,
        f"RGB+Ha (R14 G14 B14 Ha1) → 14 — reçu {st_rgbha.profondeur_min()}")
verifie(compo("LRGB+Ha", {"L": 1, "R": 1, "G": 1, "B": 1, "Ha": 1})
        .profondeur_min() == 1,
        "LRGB+Ha à 1 frame/rôle → 1 : le banc 129 (plomberie) reste valide")
verifie(compo("HOO", {"Ha": 2, "O3": 5}).profondeur_min() == 2
        and compo("SHO", {"S2": 4, "Ha": 9, "O3": 5}).profondeur_min() == 4,
        "HOO/SHO → le Ha COMPTE (il est un canal) : 2 puis 4")
verifie(compo("LRGB", {"L": 5, "R": 4, "G": 3, "B": 2}).profondeur_min() == 2
        and compo("RGB", {"R": 4, "G": 4, "B": 9}).profondeur_min() == 4,
        "NON-RÉGRESSION : LRGB → 2, RGB → 4 (inchangés)")


# ===================================== [3] recalage + cadre commun (façade)
print("[3] recalage d'EMPILEMENT : moyennes() ramène la couche dans la grille")
fa_ref = CompositeStacker("LRGB+Ha", k=None)
fa_ref.add(carte(1), role="G")
fa_ref.note_alignement(np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
                       role="G")
cadre_plein = fa_ref.cadre
fa = CompositeStacker("LRGB+Ha", k=None)
fa.add(carte(1), role="G")
fa.note_alignement(np.array([[1.0, 0.0, 5.0], [0.0, 1.0, 0.0]]), role="G")
verifie(cadre_plein is not None and fa.cadre is not None
        and (fa.cadre[2] - fa.cadre[0]) * (fa.cadre[3] - fa.cadre[1])
        < (cadre_plein[2] - cadre_plein[0]) * (cadre_plein[3] - cadre_plein[1]),
        f"note_alignement(role=G) rétrécit le cadre commun — plein "
        f"{cadre_plein} → décalé {fa.cadre}")

fa_ha = CompositeStacker("LRGB+Ha", k=None)
fa_ha.add(carte(1), role="Ha")
fa_ha.note_alignement(np.array([[1.0, 0.0, 5.0], [0.0, 1.0, 0.0]]),
                      role="Ha")
verifie(fa_ha.cadre is None,
        "note_alignement(role=Ha fusionné) est IGNORÉ (repère propre, hors "
        "grille du composite)")

fa_hoo = CompositeStacker("HOO", k=None)
fa_hoo.add(carte(1), role="Ha")
fa_hoo.note_alignement(np.array([[1.0, 0.0, 5.0], [0.0, 1.0, 0.0]]),
                       role="Ha")
verifie(fa_hoo.cadre is not None,
        "NON-RÉGRESSION : en HOO le Ha EST un canal → il entre dans le cadre")

fa2 = CompositeStacker("LRGB+Ha", k=None)
fa2.add(carte(7), role="G")
fa2.add(carte(7), role="Ha")
brut = fa2.stackers["Ha"].mean(recadre=False)
M_connu = np.array([[1.0, 0.0, 4.0], [0.0, 1.0, -3.0]])
fa2.set_recalage("Ha", M_connu)
rec = fa2.moyennes(recadre=False)["Ha"]
attendu = cv2.warpAffine(brut, M_connu, (brut.shape[1], brut.shape[0]))
verifie(np.allclose(rec, attendu, atol=1e-5),
        "moyennes() applique le recalage du rôle (warpAffine exact)")
verifie(np.array_equal(fa2.moyennes(recadre=False)["G"], brut),
        "les rôles SANS recalage sont rendus TELS QUELS (aucun warp)")
fa2.set_recalage("Ha", None)
verifie(fa2.recalage("Ha") is None
        and np.array_equal(fa2.moyennes(recadre=False)["Ha"], brut),
        "set_recalage(None) ramène le rôle dans la grille du composite")



# ================== [4] TÉMOIN hors-ligne : reproduit le refus, puis la voie A
print("[4] témoin hors-ligne : le Ha contre la RÉFÉRENCE broadband vs lui-même")
DEC_BB = {"L": [(0.0, 0.0), (2.0, 1.0), (4.0, 3.0)],
          "R": [(1.0, 2.0), (3.0, 0.0), (0.0, 3.0)],
          "G": [(2.0, 0.0), (0.0, 2.0), (3.0, 1.0)],
          "B": [(0.0, 1.0), (2.0, 3.0), (1.0, 0.0)]}
HA_DEC = [(0.0, 0.0, 71), (6.0, -4.0, 72), (-5.0, 7.0, 73)]

# Référence du composite = EMPILEMENT G aligné (comme `_image_reference_de`).
al_g = StarAligner()
al_g.set_reference(champ(_ETOILES_A, 2.0, 0.0, graine=41))
pile_g = [champ(_ETOILES_A, 2.0, 0.0, graine=41)]
for dx, dy, g in ((0.0, 2.0, 42), (3.0, 1.0, 43)):
    fr = champ(_ETOILES_A, dx, dy, graine=g)
    M, okk = al_g.compute(fr)
    if okk:
        pile_g.append(cv2.warpAffine(fr, M, (W, H)))
ref_composite = np.mean(np.stack(pile_g), axis=0)
verifie(len(pile_g) == 3, "témoin : les 3 brutes G s'alignent entre elles")

frames_ha = [champ(_ETOILES_B, dx, dy, fond=0.07, graine=g)
             for (dx, dy, g) in HA_DEC]
al_part = StarAligner()
al_part.set_reference(ref_composite)
res_part = []
for f in frames_ha:
    M, okk = al_part.compute(f)
    res_part.append((okk, (al_part.dernier or {}).get("methode")))
aligne = [1 for okk, _m in res_part if okk]
methodes = sorted(str(m) for okk, m in res_part if okk)
verifie(len(aligne) <= 1,
        f"TÉMOIN : l'aligneur PARTAGÉ (référence broadband) n'empile que "
        f"{len(aligne)}/{len(frames_ha)} brute(s) Ha → la couche Ha ne peut "
        f"PAS se construire (c'est le refus mesuré en réel, 0/5)")
verifie(all(m == "phase" for m in methodes),
        f"…et le rare « succès » vient du repli PHASE (traduction sur des "
        f"structures non apparentées), JAMAIS d'un appariement d'étoiles "
        f"({methodes or 'aucun'})")
al_ha = StarAligner()
al_ha.set_reference(frames_ha[0])
intra = []
for f in frames_ha[1:]:
    M, okk = al_ha.compute(f)
    intra.append((okk, (al_ha.dernier or {}).get("methode")))
verifie(all(okk for okk, _m in intra)
        and all(("ORB" in str(m) or "triangles" in str(m))
                for _o, m in intra),
        f"TÉMOIN : intra-rôle (référence = 1re brute Ha) → "
        f"{sum(1 for o, _m in intra if o)}/{len(intra)} acceptés par un "
        f"appariement d'ÉTOILES {[m for _o, m in intra]} : le Ha EST "
        f"alignable… sur lui-même")



# ================== [4bis] SESSION RÉELLE : le Ha passe par l'aligneur dédié
print("[4bis] session réelle (worker + 5 dossiers) : routage voie A")
racine = tempfile.mkdtemp(prefix="avastack_j129b_")
dossiers = {}
for _role in ("L", "R", "G", "B", "Ha"):
    _d = os.path.join(racine, _role)
    os.makedirs(_d)
    dossiers[_role] = _d
for _role, _dec in DEC_BB.items():
    for _i, (_dx, _dy) in enumerate(_dec):
        save_image(os.path.join(dossiers[_role], f"{_role}_{_i:02d}.fits"),
                   champ(_ETOILES_A, _dx, _dy, graine=500 + _i))
for _i, (_dx, _dy, _g) in enumerate(HA_DEC):
    save_image(os.path.join(dossiers["Ha"], f"Ha_{_i:02d}.fits"),
               champ(_ETOILES_B, _dx, _dy, fond=0.07, graine=_g))
time.sleep(1.3)                      # taille stable + mtime > 0,5 s (folder)

ui.CONFIG = {}                       # banc HERMÉTIQUE : jamais le vrai config
ui.sauver_config = lambda *a, **k: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
app.rejeter_flou = False             # test déterministe (pas de filtre flou)
app.ref_refresh = 0                  # pas de rafraîchissement de référence
app._veut_restack = lambda: False    # re-stack AUTO neutralisé (déterminisme)


class _Val:
    """Bouchon de variable Tk : `var.get()` est INTERDIT hors thread principal
    (RuntimeError « main thread is not in main loop ») — le worker lit
    var_wb/var_wb_force au moment de créer l'empilement."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


app.var_wb = _Val(False)
app.var_wb_force = _Val(1.0)

# Espions : QUEL aligneur a calculé chaque brute (le cœur de la voie A).
appels = {"partage": 0, "ha": 0}
_orig_partage = app.aligner.compute
_orig_ha = app.aligner_ha.compute


def _c_partage(frame):
    appels["partage"] += 1
    return _orig_partage(frame)


def _c_ha(frame):
    appels["ha"] += 1
    return _orig_ha(frame)


app.aligner.compute = _c_partage
app.aligner_ha.compute = _c_ha

cam = MultiFolderCamera([(r, dossiers[r]) for r in ("L", "R", "G", "B", "Ha")])
cam.open()
app.camera = cam
app._mode_compo = True
app._compo_nom = "LRGB+Ha"

app.running = True
app.empilement_on = True
th = threading.Thread(target=app._worker, daemon=True)
th.start()
t0 = time.time()
while time.time() - t0 < 60:
    if app.stacker is not None and app.stacker.n >= 15:
        break
    try:
        app.q.get(timeout=0.5)
    except Exception:
        pass
time.sleep(0.4)
app.running = False
th.join(timeout=5.0)
# Les archives de la session (une par rôle) sont vidées en fin de banc — le
# dossier de travail de l'appli est PARTAGÉ (`avastack_frames_*`) et n'est
# nettoyé qu'au démarrage suivant : on ne laisse pas de résidu derrière soi.
archives_session = list(app.archives.values())

verifie(app.stacker is not None
        and type(app.stacker).__name__ == "CompositeStacker",
        "session : la façade CompositeStacker est posée")
prof = {r: s.n for r, s in app.stacker.stackers.items()}
verifie(app.stacker.stackers.get("Ha") is not None
        and app.stacker.stackers["Ha"].n == 3,
        f"session : la couche Ha est EMPILÉE 3/3 (voie A) — états {prof}")
verifie(appels["ha"] == 3 and appels["partage"] == 12,
        f"session : les 3 brutes Ha sont passées par l'aligneur DÉDIÉ "
        f"(ha={appels['ha']}) et les 12 broadband par l'aligneur PARTAGÉ "
        f"(partage={appels['partage']})")
verifie(app.bad_frames == 0 and not app.bad_frames_par_role,
        f"session : AUCUN refus (bad={app.bad_frames}, par rôle="
        f"{app.bad_frames_par_role})")

# Re-stack compo : le Ha est rejoué dans SON repère. La cadence d'archivage
# (une frame par seconde et par rôle, garde-fou anti-vidéo) empêche la session
# ci-dessus — trop rapide — d'archiver ses 3 brutes Ha : l'archive du re-stack
# est donc construite EXPLICITEMENT (mêmes images, même géométrie).
from avastack.processing.framestore import ArchiveFrames as _AF  # noqa: E402

app.archives = {}
for _role, _dec in DEC_BB.items():
    _a = _AF(intervalle_s=0.0)
    for _i, (_dx, _dy) in enumerate(_dec):
        _a.ajouter(champ(_ETOILES_A, _dx, _dy, graine=500 + _i))
    app.archives[_role] = _a
_a_ha = _AF(intervalle_s=0.0)
for _dx, _dy, _g in HA_DEC:
    _a_ha.ajouter(champ(_ETOILES_B, _dx, _dy, fond=0.07, graine=_g))
app.archives["Ha"] = _a_ha
verifie(sum(a.n for a in app.archives.values()) == 15,
        "archive de re-stack : 15 frames (3 par rôle)")
avant = appels["ha"]
info = app._do_restack_compo("banc voie A", ancre_role="G", ancre_idx=0)
verifie(app.stacker.stackers["Ha"].n == 3 and appels["ha"] - avant == 2
        and "Ha 3/3" in app.restack_info,
        f"re-stack : le Ha est rejoué par l'aligneur DÉDIÉ (3/3, "
        f"+{appels['ha'] - avant} calculs) — « {info} » / "
        f"« {app.restack_info} »")
# Champs NON apparentés : le recalage ne doit PAS être posé sur une matrice
# aberrante (échec SÛR, on garde le précédent — ici : aucun).
verifie(app.stacker.recalage("Ha") is None,
        "re-stack : aucun recalage ABERRANT posé sur des champs non "
        "apparentés (échec sûr)")
for _a in app.archives.values():
    _a.vider()
app.archives = {}
for _a in archives_session:          # archives de la SESSION ci-dessus
    _a.vider()


# =============== [5] recalage Ha → composite mesuré par un VRAI aligneur
print("[5] voie A mesurée : un empilement Ha DÉCALÉ rejoint la grille")
st5 = CompositeStacker("LRGB+Ha", k=None)
app.stacker = st5
app._mode_compo = True
app._compo_nom = "LRGB+Ha"
g_ref = champ(_ETOILES_A, 0.0, 0.0, graine=601)
for k in (602, 603):
    st5.add(champ(_ETOILES_A, 0.0, 0.0, graine=k), role="G")
ha_dec = champ(_ETOILES_A, 9.0, -6.0, graine=604)     # MÊME champ, DÉCALÉ
for _k in range(3):
    st5.add(ha_dec, role="Ha")
pile_ha = st5.stackers["Ha"].mean(recadre=False)
app._recaler_ha()
M_ha = st5.recalage("Ha")
verifie(M_ha is not None,
        "voie A : le recalage Ha → composite est MESURÉ (empilement Ha "
        "contre la couche broadband)")
if M_ha is not None:
    _ang, _ech, dxr, dyr = infos_M(M_ha)
    verifie(abs(dxr + 9.0) < 1.0 and abs(dyr - 6.0) < 1.0,
            f"voie A : la translation mesurée est la BONNE "
            f"(Δ=({dxr:+.2f},{dyr:+.2f}) px pour un décalage réel (−9,+6))")
    reg = st5.moyennes(recadre=False)["Ha"]
    zone = (slice(50, 150), slice(70, 190))
    res_avant = float(np.mean(np.abs(pile_ha[zone] - g_ref[zone])))
    res_apres = float(np.mean(np.abs(reg[zone] - g_ref[zone])))
    verifie(res_apres < 0.5 * res_avant,
            f"voie A : l'empilement Ha rejoint la grille du composite "
            f"(résidu {res_avant:.4f} → {res_apres:.4f})")


# ================ [6] libellé « frames par rôle » : les BANDES mesurées
print("[6] profondeur annoncée par la SPCC/photo : les bandes R/G/B")
st6 = compo("LRGB+Ha", {"L": 5, "R": 30, "G": 20, "B": 12, "Ha": 1})
app.stacker = st6
app._mode_compo = True
verifie(app._profondeur_spcc(st6) == 12,
        f"LRGB+Ha (L5 R30 G20 B12 Ha1) → la mesure porte sur R/G/B → 12 "
        f"(reçu {app._profondeur_spcc(st6)})")
verifie(st6.profondeur_min() == 5 and app._profondeur_spcc(st6) == 12,
        "…et le libellé ne dit plus le MINIMUM tous rôles (5) : il décrit "
        "ce que la mesure voit")
diag = {"capteur": "Test", "n_regression": 40,
        "frames": app._profondeur_spcc(st6), "frames_par_role": True}
txt = spcc_texte(np.array([1.0, 1.0, 1.0]), diag)
verifie("mesure faite sur 12 frames par rôle" in txt,
        f"libellé SPCC : « …{txt[-70:]} »")
st6b = compo("HOO", {"Ha": 7, "O3": 4})
verifie(app._profondeur_spcc(st6b) == 4,
        "HOO : la mesure porte sur Ha ET O3 → 4 (le Ha reste compté)")
app._mode_compo = False
verifie(app._profondeur_spcc(compo("Mono", {"L": 6})) == 6,
        "hors composition (mono) : la profondeur reste celle de l'empilement")


# ================= [7] NON-RÉGRESSION : HOO/SHO gardent l'ancre Ha
print("[7] non-régression : la voie A ne concerne QUE le Ha d'un +Ha")
app._mode_compo = True
app._compo_nom = "HOO"
verifie(not app._voie_a_ha("Ha") and not app._voie_a_ha("O3"),
        "HOO : voie A fausse (le Ha est un CANAL et l'ancre)")
app._compo_nom = "SHO"
verifie(not app._voie_a_ha("Ha"),
        "SHO : voie A fausse (le Ha alimente le canal VERT)")
app._compo_nom = "LRGB"
verifie(not app._voie_a_ha("Ha") and not app._voie_a_ha("L"),
        "LRGB : voie A fausse (aucun Ha dans la composition)")
app._compo_nom = "LRGB+Ha"
verifie(app._voie_a_ha("Ha") and not app._voie_a_ha("G"),
        "LRGB+Ha : voie A pour le Ha SEUL (les broadband gardent l'aligneur "
        "PARTAGÉ, donc le repère commun)")
app._mode_compo = False
verifie(not app._voie_a_ha("Ha"), "hors composition : voie A fausse")

root.destroy()
shutil.rmtree(racine, ignore_errors=True)
images.CFA_MODE = CFA_MODE_AVANT
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)

