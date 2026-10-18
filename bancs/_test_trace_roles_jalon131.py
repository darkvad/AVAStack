# -*- coding: utf-8 -*-
"""Banc du jalon 131 (v2.82.1) — TRACE PAR RÔLE de l'empilement.

Étape ⑦ du chantier CAUSE AMONT : les taches rouges/bleues du LRGB ne sont
portées par AUCUNE couche isolée, et le combine est innocenté trois fois
(runs 140/142/143). Ce qui reste à expliquer est un ÉTAT D'EMPILEMENT — quelle
référence d'alignement, quels offsets, quels pixels rejetés, avec quel σ, et
pour QUEL rôle — qui n'était journalisé nulle part. `processing/trace_roles.py`
l'écrit, sans jamais toucher aux calculs.

Ce banc vérifie :
  [1] INACTIVITÉ STRICTE (règle la plus importante) : sans `ouvrir()` ni
      `AVASTACK_TRACE_ROLES`, `actif()` est faux, AUCUN fichier n'est créé et
      les fonctions rendent sans lever, même sur des entrées absurdes ;
  [2] SCHÉMA des deux types de ligne : `entete` (version + argv), `reference`
      (motif, rôle source, profondeur, empreinte) et `frame` (rôle, étape,
      empreinte, référence en vigueur, offsets, profondeur de chaque rôle,
      rejets, poids, σ) — écrits par l'APP RÉELLE (`_definir_reference`) ;
  [3] POIDS et σ recalculés À LA MAIN sur une pile de 2 frames (poids
      `wsum/n`, σ temporel `sqrt(sumsq/wsum − moyenne²)`) ;
  [4] REJET RÉEL : une frame avec un pixel aberrant est REJETÉE par
      kappa-sigma, `rejets_cumules` l'enregistre et `poids_sous_pct` le voit ;
  [5] CARTES FITS (option) : poids = `wsum/n`, σ = l'écart-type recalculé,
      bords non couverts à 0 ;
  [6] JAMAIS D'EXCEPTION : app absente, image None, dossier impossible, cartes
      sur un rôle vide ;
  [7] GARDE DU REFACTORING : `_image_reference_et_role_de()` rend le MÊME
      tableau que `_image_reference_de()` ET nomme le rôle du canal VERT
      (G en RGB/LRGB) — c'est ce rôle qui répond à « quelle référence ».

Exécution : python bancs/_test_trace_roles_jalon131.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (et non plus à côté de l'application).
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import json
import os
import sys
import tempfile

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV/OpenCL au teardown sinon
import tkinter as tk

import avastack.ui.app as ui
from avastack import AVASTACK_VERSION
from avastack.processing import trace_roles
from avastack.processing.alignment import StarAligner
from avastack.processing.composition import CompositeStacker
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):   # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def lire_jsonl(chemin):
    """→ liste des lignes JSON d'une trace (ignore une ligne illisible)."""
    out = []
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne:
                    try:
                        out.append(json.loads(ligne))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


DOSSIER = tempfile.mkdtemp(prefix="avastack_j131_")
H, W = 48, 64

# ======================================== [1] INACTIVITÉ STRICTE (défaut)
print("[1] inactive par défaut : aucun calcul, aucun fichier")
os.environ.pop(trace_roles.ENV_DIR, None)
trace_roles.fermer()
verifie(trace_roles.actif() is False, "actif() est faux sans ouverture")
trace_roles.noter_frame(None, role="L", etape="empilee")          # ne lève pas
trace_roles.noter_reference(None, None, motif="auto")             # ne lève pas
verifie(os.listdir(DOSSIER) == [], "aucun fichier écrit quand la trace est fermée")
verifie(trace_roles.resume_pile(None) == {}, "resume_pile(None) → {} (pas d'exception)")
verifie(trace_roles.exporter_cartes(DOSSIER, "vide", {}) == [],
        "exporter_cartes sur rien → [] (pas d'exception)")


# ================================================ [2] ouverture + schéma réel
print("[2] ouverte : entête, référence et frame écrites par l'APP RÉELLE")
verifie(trace_roles.ouvrir(DOSSIER, "banc") is True, "ouvrir() → True")
CHEMIN = os.path.join(DOSSIER, "banc.jsonl")
_lignes = lire_jsonl(CHEMIN)
verifie(len(_lignes) == 1 and _lignes[0].get("type") == "entete"
        and _lignes[0].get("version") == AVASTACK_VERSION
        and isinstance(_lignes[0].get("argv"), list),
        "ligne « entete » : version de l'appli + argv (reproductibilité)")

# Config HERMÉTIQUE (règle du projet) : jamais le vrai config.json du poste.
ui.CONFIG = {}
ui.sauver_config = lambda *a, **k: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
app._mode_compo = True


def champ(val=0.05, graine=0, tache=None):
    """Carte (H, W) float32 : fond + bruit ; `tache` = (y, x, amplitude)."""
    img = np.full((H, W), val, np.float32)
    img += np.random.default_rng(graine).normal(0, 0.002, img.shape).astype(np.float32)
    if tache is not None:
        img[tache[0], tache[1]] += np.float32(tache[2])
    return img


st = CompositeStacker("LRGB", k=None)
for i in range(6):                      # le rôle G du vert a 6 frames
    st.role_courant = "G"
    st.add(champ(graine=i))
for i in range(3):                      # L et R existent, moins profonds
    st.role_courant = "L"
    st.add(champ(graine=10 + i))
    st.role_courant = "R"
    st.add(champ(graine=20 + i))
app.stacker = st
app._compo_nom = "LRGB"

ref_img, ref_role = app._image_reference_et_role_de(st)
app._definir_reference(ref_img, motif="auto", role_source=ref_role)
_lignes = lire_jsonl(CHEMIN)
_ref = [r for r in _lignes if r.get("type") == "reference"]
verifie(len(_ref) == 1, "une ligne « reference » écrite par _definir_reference()")
r0 = _ref[0] if _ref else {}
verifie(r0.get("motif") == "auto" and r0.get("role") == "G"
        and int(r0.get("n", -1)) == 6,
        f"référence : motif=auto, rôle=G, profondeur=6 (lu {r0.get('motif')!r}, "
        f"{r0.get('role')!r}, {r0.get('n')!r})")
verifie(len(str(r0.get("empreinte", ""))) == 16,
        "empreinte de la référence = 16 caractères hexadécimaux")
verifie(r0.get("n_roles") == {"G": 6, "L": 3, "R": 3},
        f"profondeur de CHAQUE rôle à cet instant ({r0.get('n_roles')})")

al = StarAligner()
al.dernier = {"methode": "étoiles", "dx": 3.5, "dy": -1.25,
              "angle": 0.12, "echelle": 1.0004}
trace_roles.noter_frame(app, role="G", etape="empilee", image=champ(graine=99),
                        aligneur=al, ok=True, expo=60.0)
_fr = [r for r in lire_jsonl(CHEMIN) if r.get("type") == "frame"]
f0 = _fr[-1] if _fr else {}
verifie(f0.get("role") == "G" and f0.get("etape") == "empilee",
        "ligne « frame » : rôle et étape")
verifie(f0.get("dx") == 3.5 and f0.get("dy") == -1.25
        and abs(float(f0.get("distance") or 0) - 3.716) < 1e-3,
        f"offsets rendus (Δ = {f0.get('distance')} px, θ = {f0.get('angle')}°)")
verifie(f0.get("echelle") == 1.0004,
        "ECHELLE conservée par StarAligner._noter (elle était jetée)")
verifie(f0.get("ref_role") == "G" and f0.get("ref_seq") == 0
        and int(f0.get("ref_age") or -1) == 1,
        "la frame porte la RÉFÉRENCE EN VIGUEUR (rôle + âge)")
verifie(len(str(f0.get("empreinte", ""))) == 16,
        "empreinte de la brute (appariement des runs « mêmes brutes »)")
verifie(f0.get("n_roles") == {"G": 6, "L": 3, "R": 3} and f0.get("n_role") == 6,
        "profondeurs et profondeur du rôle joints à la frame")
verifie("poids_moyen" in f0 and "sigma_p50" in f0,
        "poids et σ de la pile joints à la frame")

# Refus : les offsets de l'aligneur NE DOIVENT PAS être recopiés (ils sont périmés).
trace_roles.noter_frame(app, role="L", etape="refus_alignement", image=None,
                        aligneur=al, ok=False)
_fr = [r for r in lire_jsonl(CHEMIN) if r.get("type") == "frame"]
verifie(_fr[-1].get("align_ok") is False and "dx" not in _fr[-1],
        "frame refusée : align_ok=False et AUCUN offset (celui d'avant serait faux)")


# ================================== [3] poids et σ recalculés à la main
print("[3] resume_pile : poids wsum/n et σ temporel, recalculés à la main")
st2 = LiveStacker((H, W), k=None)
st2.add(np.full((H, W), 1.0, np.float32))
st2.add(np.full((H, W), 3.0, np.float32))
r2 = trace_roles.resume_pile(st2, pas=1)
# moyenne 2 · variance = (1² + 3²)/2 − 2² = 1 → σ = 1 partout.
verifie(r2.get("poids_moyen") == 1.0 and r2.get("poids_plein_pct") == 100.0
        and r2.get("poids_sous_pct") == 0.0,
        f"2 frames gardées partout → poids 1,0 / plein 100 % ({r2.get('poids_moyen')})")
verifie(abs(float(r2.get("sigma_p50", -1)) - 1.0) < 1e-9
        and abs(float(r2.get("sigma_p99", -1)) - 1.0) < 1e-9,
        f"σ = 1,0 partout (p50={r2.get('sigma_p50')}, p99={r2.get('sigma_p99')})")
verifie(r2.get("px_couverts_pct") == 100.0, "aucun bord non couvert ici")


# ============================================== [4] un rejet RÉEL est compté
print("[4] rejet kappa-sigma : compté, et visible dans le poids")
st3 = LiveStacker((H, W), k=3.0, warmup=1)
for _i in range(4):
    st3.add(np.ones((H, W), np.float32))
_pic = np.ones((H, W), np.float32)
_pic[5, 7] = 100.0                      # un seul pixel aberrant
st3.add(_pic)
verifie(st3.rejected_total == 1,
        f"UNE frame refusée au pixel (5,7) → rejected_total = {st3.rejected_total}")
r3 = trace_roles.resume_pile(st3, pas=1)
_n = st3.n
_attendu = 100.0 / float(H * W)          # UN pixel sous le poids plein
verifie(abs(float(r3.get("poids_sous_pct", -1)) - _attendu) < 1e-3,
        f"poids_sous_pct = 1 pixel sur {H * W} ({r3.get('poids_sous_pct')} % "
        f"attendu {_attendu:.6f} %)")
verifie(abs(float(r3.get("poids_moyen", -1))
            - (1.0 - 1.0 / (float(_n) * float(H * W)))) < 1e-6,
        f"poids_moyen = 1 − 1/(n·Npix) ({r3.get('poids_moyen')})")


# ======================================================== [5] cartes FITS
print("[5] exporter_cartes : poids = wsum/n, σ recalculé, bords à 0")
from astropy.io import fits as _fits
_ecrits = trace_roles.exporter_cartes(DOSSIER, "banc", {"L": st3})
verifie(sorted(os.path.basename(p) for p in _ecrits)
        == ["banc_L_moyenne.fits", "banc_L_poids.fits", "banc_L_sigma.fits"],
        f"trois cartes écrites ({len(_ecrits)})")
try:
    with _fits.open(os.path.join(DOSSIER, "banc_L_poids.fits")) as hd:
        _poi = np.asarray(hd[0].data)
        _hdr = hd[0].header
    with _fits.open(os.path.join(DOSSIER, "banc_L_sigma.fits")) as hd:
        _sig = np.asarray(hd[0].data)
    _ok_cartes = True
except Exception as exc:                 # une carte illisible = échec explicite
    _poi = _sig = np.zeros((1, 1), np.float32)
    _hdr = {}
    _ok_cartes = False
    print("    (lecture des cartes impossible : %s)" % exc)
verifie(_ok_cartes and _poi.shape == (H, W) and _sig.shape == (H, W),
        "cartes (H, W) relues par astropy")
verifie(_hdr.get("AVAROLE") == "L" and int(_hdr.get("AVAFRAME", 0)) == st3.n,
        "en-têtes AVAROLE / AVAFRAME (provenance de la carte)")
verifie(abs(float(_poi[5, 7]) - (1.0 - 1.0 / float(_n))) < 1e-6
        and abs(float(_poi[0, 0]) - 1.0) < 1e-6,
        f"poids : {_poi[5, 7]:.4f} au pixel rejeté, 1,0 ailleurs")
verifie(float(_sig[5, 7]) < 1e-6 and float(_sig[0, 0]) < 1e-6,
        "σ = 0 sur une pile constante (le rejet n'invente pas de bruit)")


# ==================================== [6] jamais d'exception, taille bornée
print("[6] entrées absurdes : aucune exception ; écriture bornée")
verifie(trace_roles.empreinte(None) == ""
        and trace_roles.empreinte("pas une image") == "",
        "empreinte(None) et empreinte(texte) → '' (pas d'exception)")
trace_roles.noter_frame(object(), role=None, etape="empilee")
trace_roles.noter_reference(object(), np.zeros((8, 8), np.float32), motif="x")
verifie(True, "app sans pile ni aligneur : noter_frame / noter_reference rendent")
verifie(trace_roles.exporter_cartes(os.path.join(DOSSIER, "sous"), "vide",
                                    {"L": None}) == [],
        "carte demandée pour un rôle VIDE → [] (pas de fichier, pas d'exception)")
verifie(trace_roles.ouvrir("", "") is False, "ouvrir('') → False (aucun effet de bord)")
_taille = os.path.getsize(CHEMIN)
_max = trace_roles.MAX_OCTETS
try:
    trace_roles.MAX_OCTETS = -1          # force la borne (test déterministe)
    trace_roles.noter_frame(app, role="G", etape="empilee", image=champ())
finally:
    trace_roles.MAX_OCTETS = _max
verifie(os.path.getsize(CHEMIN) == _taille,
        "borne MAX_OCTETS atteinte → la trace CESSE d'écrire (pas de disque rempli)")


# ===================== [7] garde du refactoring : même image, rôle nommé
print("[7] _image_reference_et_role_de : même image que _image_reference_de")
verifie(np.array_equal(app._image_reference_de(st),
                       app._image_reference_et_role_de(st)[0]),
        "le tableau rendu est IDENTIQUE (le refactoring ne change pas la référence)")
verifie(ref_role == "G" and np.array_equal(ref_img, st.moyennes(recadre=False)["G"]),
        "le rôle NOMMÉ est celui du canal VERT (G) et l'image est sa couche brute")
app._mode_compo = False
_stm = LiveStacker((H, W), k=None)
_stm.add(champ())
_img_m, _role_m = app._image_reference_et_role_de(_stm)
verifie(_role_m is None and _img_m is not None,
        "hors composition : l'empilement tel quel, sans rôle")
app._mode_compo = True
verifie(app._image_reference_et_role_de(None) == (None, None),
        "empilement absent → (None, None)")

trace_roles.fermer()
_lignes = lire_jsonl(CHEMIN)
verifie(bool(_lignes) and _lignes[-1].get("type") == "fin",
        "fermer() écrit la ligne « fin »")
verifie(trace_roles.actif() is False, "après fermeture, la trace est INACTIVE")

root.destroy()
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
