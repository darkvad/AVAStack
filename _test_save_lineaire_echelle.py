# -*- coding: utf-8 -*-
"""Banc : ÉCHELLE des fichiers LINÉAIRES écrits par l'appli (v2.27.1).

Constat réel d'Alain (22/09/2026 — PRIORITÉ) : « l'empilement linéaire en
sortie, mode dossiers (compo RGB), est saturé et non solvable par ASTAP ».
Mesures sur son fichier : fond à 0,02, max 14,1, 0,3 % des pixels > 1 →
ASTAP « Only 0 stars found in image » (jamais résolu, ERROR=Not enough stars
dans le .ini) et cœur/étoiles clippés en blanc par tout lecteur qui suppose
[0,1]. Cause : seul le composite d'une composition sort de [0,1]
(normalisation par percentiles SANS clip, cf. composition.normaliser).
Fix : `images.borner_lineaire()` appelé par le worker avant CHAQUE écriture
linéaire (facteur GLOBAL consigné dans l'en-tête, AVASCALE).

[1] borner_lineaire : composite > 1 → borné à 1, facteur exact & réversible
[2] borner_lineaire : image déjà ≤ 1 → AUCUNE modification (mot-clé en moins)
[3] borner_lineaire : nan/inf neutralisés et comptés (AVANAN), jamais écrits
[4] worker RÉEL : sauvegarde d'un composite (mean() > 1) → fichier borné,
    AVASCALE exact, FILTER conservé, canaux sur NAXIS3, contenu proportionnel
[5] worker RÉEL, mono : 0,25 au bit près, aucun AVASCALE (comportement gardé)
[6] PNG/TIFF : le bornage supprime le plateau « tout blanc » du composite
[7] ASTAP RÉEL sur l'empilement M31 du disque (si présent) : le fichier borné
    est RÉSOLU et son échelle concorde avec la brute du même setup.

Exécution : python _test_save_lineaire_echelle.py
"""
import os
import sys
import tempfile
import threading
import time
import tkinter as tk

import numpy as np
from astropy.io import fits

import avastack.ui.app as ui
ui.CONFIG = {}                    # config HERMETIQUE (regle du projet :
ui.sauver_config = lambda *a, **k: None   # JAMAIS le vrai config.json)
from avastack.images import borner_lineaire, load_image, save_image
from avastack.processing.composition import CompositeStacker
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):        # sortie pipée ≠ console cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def facteur(entete):
    """Valeur d'AVASCALE : le dict passé à save_image porte (valeur, comment)
    (convention astropy value+comment) — l'en-tête RELU, lui, rend un float."""
    v = entete.get("AVASCALE")
    if isinstance(v, tuple):
        return float(v[0])
    return 0.0 if v is None else float(v)


tmp = tempfile.mkdtemp(prefix="avastack_echelle_")
rng = np.random.default_rng(11)
H, W = 240, 320
yy, xx = np.mgrid[0:H, 0:W]


def composite_factice():
    """Stacker RGB réaliste : fond bruité + cœur brillant (0,1 % des pixels).
    La normalisation par percentiles du composite fait monter le cœur très
    au-dessus de 1 — exactement le cas M31 d'Alain."""
    st = CompositeStacker("RGB")
    for role, amp in (("R", 1.0), ("G", 0.8), ("B", 0.6)):
        coeur = amp * 5.0 * np.exp(-((yy - 120.0) ** 2 + (xx - 160.0) ** 2)
                                   / (2 * 2.0 ** 2))
        cadre = (rng.normal(0.02, 0.004, (H, W)) + coeur).astype(np.float32)
        st.add(cadre, role=role)              # x2 : au-delà du warmup
        st.add(cadre, role=role)
    return st


# ============================================= [1] bornage d'un composite > 1
print("[1] borner_lineaire : composite > 1 → [0,1] + facteur consigné")
comp = composite_factice().mean()
mx = float(comp.max())
verifie(mx > 1.0, f"prémisse : le composite dépasse 1 (max {mx:.2f})")
borne, entete = borner_lineaire(comp, {"FILTER": "L"})
verifie(abs(float(borne.max()) - 1.0) < 1e-6,
        f"max ramené à 1 (obtenu {float(borne.max()):.6f})")
verifie(abs(facteur(entete) - mx) < max(1e-6, mx * 1e-6),
        f"AVASCALE = {facteur(entete):.4f} (max d'origine)")
verifie(str(entete.get("HISTORY", "")) != "" and "FILTER" in entete,
        "FILTER conservé + HISTORY explicatif ajouté")
ecart = float(np.abs(borne.astype(np.float64) * mx - comp).max())
verifie(ecart < 1e-4 * max(1.0, mx),
        f"opération RÉVERSIBLE (× AVASCALE : écart max {ecart:.2e})")
verifie(float(comp.max()) == mx and comp.shape == borne.shape,
        "l'image d'entrée n'est pas modifiée sur place")

# ================================================== [2] image déjà ≤ 1 : no-op
print("[2] borner_lineaire : image ≤ 1 → aucune modification")
mono = (0.25 + rng.normal(0.0, 0.01, (H, W))).astype(np.float32)
m2, e2 = borner_lineaire(mono, {"FILTER": "R"})
verifie(m2.dtype == np.float32 and np.array_equal(m2, mono),
        "contenu bit à bit identique (aucun facteur retiré)")
verifie("AVASCALE" not in e2 and e2.get("FILTER") == "R",
        "aucun AVASCALE ajouté, entête transmis tel quel")

# ==================================================== [3] nan/inf neutralisés
print("[3] borner_lineaire : nan/inf neutralisés et comptés")
sale = mono.copy()
sale[3, 4], sale[10, 20], sale[0, 0] = np.nan, np.inf, -np.inf
propre, e3 = borner_lineaire(sale)
verifie(bool(np.isfinite(propre).all()), "plus aucune valeur non finie")
verifie(e3.get("AVANAN") == 3, f"AVANAN = {e3.get('AVANAN')} (3 comptées)")

# ================================ [4] worker RÉEL : composite → fichier borné
print("[4] worker : « Enregistrer l'empilement (linéaire) » d'un composite > 1")
root = tk.Tk()
root.withdraw()
app = ui.App(root)


class CameraMuette:
    """Caméra factice : ne renvoie plus aucune frame (dossier terminé)."""
    name = "muette"

    def read(self):
        return None


app.camera = CameraMuette()
app.running = True
app._mode_compo = False                # pas de synchro de gains du worker
app.filtre_courant = "Ha"
st_compo = composite_factice()
app.stacker = st_compo
attendu = st_compo.mean()
p_compo = os.path.join(tmp, "empilement_compo.fits")
app.save_request = p_compo
th = threading.Thread(target=app._worker, daemon=True)
th.start()
t0 = time.time()
while time.time() - t0 < 8.0 and app.saved_path is None:
    time.sleep(0.05)
app.running = False
th.join(timeout=3.0)

verifie(isinstance(app.saved_path, str)
        and not app.saved_path.startswith("ERREUR"),
        f"sauvegarde sans erreur ({app.saved_path})")
if os.path.isfile(p_compo):
    h = fits.getheader(p_compo)
    d = fits.getdata(p_compo)
    verifie(float(d.max()) <= 1.0 + 1e-6,
            f"fichier écrit borné à [0,1] (max {float(d.max()):.6f})")
    verifie(int(h["NAXIS1"]) == W and int(h["NAXIS2"]) == H
            and int(h["NAXIS3"]) == 3,
            f"canaux sur NAXIS3 (NAXIS={int(h['NAXIS1'])},"
            f"{int(h['NAXIS2'])},{int(h['NAXIS3'])})")
    verifie(str(h.get("FILTER", "")) == "Ha", "mot-clé FILTER conservé")
    av = h.get("AVASCALE")
    verifie(av is not None and abs(float(av) - float(attendu.max())) < 1e-3,
            f"AVASCALE = {av} (max du composite avant écriture "
            f"{float(attendu.max()):.4f})")
    relu = load_image(p_compo)
    ec = float(np.abs(relu.astype(np.float64) * float(attendu.max())
                      - attendu).max())
    verifie(ec < 1e-4 * max(1.0, float(attendu.max())),
            f"contenu ∝ composite (écart max {ec:.2e} — aucun clip)")
else:
    verifie(False, "fichier non écrit")

# =========================================== [5] worker mono : rien ne bouge
print("[5] worker, empilement MONO : comportement historique inchangé")
app.saved_path = None
app.running = True
mono_st = LiveStacker((48, 64), k=3, method="kappa", window=8)
mono_st.add(np.full((48, 64), 0.25, np.float32))
app.stacker = mono_st
p_mono = os.path.join(tmp, "empilement_mono.fits")
app.save_request = p_mono
th2 = threading.Thread(target=app._worker, daemon=True)
th2.start()
t0 = time.time()
while time.time() - t0 < 8.0 and app.saved_path is None:
    time.sleep(0.05)
app.running = False
th2.join(timeout=3.0)
if os.path.isfile(p_mono):
    hm = fits.getheader(p_mono)
    dm = fits.getdata(p_mono)
    verifie(abs(float(dm.max()) - 0.25) < 1e-7,
            f"valeur 0,25 au bit près (max {float(dm.max()):.7f})")
    verifie("AVASCALE" not in hm, "aucun AVASCALE (mono déjà ≤ 1)")
    verifie(dm.ndim == 2, "mono 2D intact")
else:
    verifie(False, "fichier mono non écrit")

# ================================ [6] PNG/TIFF : plus de plateau « tout blanc »
print("[6] PNG/TIFF : le bornage préserve la gradation du cœur")
try:
    import cv2
    t_raw = os.path.join(tmp, "compo_brut.tif")
    t_bor = os.path.join(tmp, "compo_borne.tif")
    save_image(t_raw, comp)
    save_image(t_bor, borne)
    r_raw = cv2.imread(t_raw, cv2.IMREAD_UNCHANGED)
    r_bor = cv2.imread(t_bor, cv2.IMREAD_UNCHANGED)
    if r_raw is None or r_bor is None:
        print("  (TIFF illisible par cv2 — skippé)")
    else:
        n_raw = int((r_raw >= 65535).sum())
        n_bor = int((r_bor >= 65535).sum())
        verifie(n_raw >= 10 and n_bor <= 2,
                f"pixels à 65535 (blanc) : {n_raw} (brut) → {n_bor} (borné)")
except ImportError:
    print("  (cv2 absent — skippé)")

# ============================= [7] ASTAP RÉEL sur l'empilement M31 du disque
print("[7] ASTAP RÉEL : le fichier borné est résolu (empilement M31 d'Alain)")
SRC = r"c:\Astro\test\m31_test_solve.fits"
RA0, DEC0 = 10.68333, 41.26917          # indices du centre de M31
try:
    from avastack.catalogues.astap import resoudre_avec_astap
    astap_ok = True
except Exception as exc:                # jamais bloquant : banc « réel »
    astap_ok = False
    print(f"  (module astap indisponible : {exc} — skippé)")
if astap_ok and os.path.isfile(SRC):
    reel = load_image(SRC)                       # (H, W, 3) tel quel
    hh, ww = reel.shape[:2]
    borne_reel, entete_reel = borner_lineaire(reel, {"FILTER": "L"})
    print(f"  empilement réel : {ww}×{hh}, max {float(reel.max()):.3f}, fond "
          f"{float(np.median(reel)):.5f} → écrit borné "
          f"(AVASCALE {facteur(entete_reel):.3f})")
    dst = os.path.join(tmp, "m31_borne.fits")
    save_image(dst, borne_reel, entete=entete_reel)
    wcs_a, msg_a = resoudre_avec_astap(dst, RA0, DEC0, rayon_deg=3.0,
                                       fov_deg=2.625 * hh / ww,
                                       dossier_sortie=tmp)
    if wcs_a is None:
        verifie(False, f"ASTAP ne résout PAS le fichier borné : {msg_a}")
    else:
        print(f"  astap_cli : {msg_a or 'PLTSOLVD=T'} — échelle "
              f"{wcs_a.echelle_arcsec:.4f}\"/px")
        verifie(True, "ASTAP résout le fichier BORNÉ (exigence d'Alain)")
        verifie(abs(wcs_a.echelle_arcsec - 2.465) < 0.02,
                f"échelle {wcs_a.echelle_arcsec:.4f}\"/px ≈ 2,465\" (brute G "
                "du même setup — contrôle croisé)")
    # Contrôle INFORMATIF (comportement d'un outil TIERS : une montée de
    # version d'ASTAP ne doit pas faire échouer le banc) : l'original non
    # borné, lui, n'était pas résolu — c'est la cause du constat d'Alain.
    wcs_b, msg_b = resoudre_avec_astap(SRC, RA0, DEC0, rayon_deg=3.0,
                                       fov_deg=2.625 * hh / ww,
                                       dossier_sortie=os.path.join(tmp,
                                                                  "brut"))
    print("  contrôle (informatif) : original non borné → "
          + ("résolu (ASTAP a évolué ?)" if wcs_b is not None
             else f"non résolu ({msg_b})"))
else:
    print("  (empilement M31 ou astap_cli absent — skippé)")

print()
print("BANC ÉCHELLE DES FICHIERS LINÉAIRES : TOUT AU VERT" if ok
      else "BANC ÉCHELLE DES FICHIERS LINÉAIRES : ÉCHECS")
sys.exit(0 if ok else 1)
