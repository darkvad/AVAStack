# -*- coding: utf-8 -*-
"""Banc du jalon 56 (étape « branchement du solveur au worker »).

Vérifie le branchement tel que décidé par Alain (22/09/2026) : l'astrométrie
de l'empilement est résolue UNE SEULE fois sur la grille COMPLÈTE, puis le WCS
est PROPAGÉ à chaque réempilement — aucun re-solve, aucun accès au catalogue
au re-stack. ASTAP reste la référence indépendante hors session.

[1] analyse des indices : décimal (degrés), sexagésimal et « h » (heures),
    refus EXPLICITES (valeur illisible, Dec/champ hors bornes) ;
[2] indices lus dans l'en-tête d'une brute (OBJCTRA/OBJCTDEC + FOCALLEN/XPIXSZ)
    — lecture STRICTE : sans mots-clés, refus clair, jamais d'invention ;
[3] SuiviAstrometrie : résolution UNIQUE (solveur injecté), réessais espacés et
    BORNÉS, invalidation du WCS quand les indices changent ;
[4] propagation & recadrage : VÉRITÉ analytique avec le StarAligner RÉEL (sens
    des matrices) + mots-clés FITS confrontés à astropy.wcs (RÉFÉRENCE
    INDÉPENDANTE, règle de CLAUDE.md) ;
[5] worker RÉEL (Tk) : l'empilement sauvegardé en linéaire porte les mots-clés
    WCS de la GRILLE RECADRÉE, et la ligne d'état annonce la mesure ;
[6] re-stack RÉEL : le WCS est PROPAGÉ par le chemin de production
    (`_do_restack` → aligneur privé → `SuiviAstrometrie.propager`) et la
    vérité analytique reste respectée.

Exécution : python _test_astro_branchement_jalon56.py
"""
import math
import os
import sys
import tempfile
import threading
import time
import tkinter as tk

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS as WcsAstropy

import avastack.ui.app as ui
from avastack.catalogues import WcsTan
from avastack.images import save_image
from avastack.processing import astrometrie as astro
from avastack.processing.alignment import StarAligner
from avastack.processing.framestore import ArchiveFrames
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):     # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# ----------------------------------------------------------- utilitaires
def ecart_ciel_deg(ra1, dec1, ra2, dec2):
    """Écart angulaire (deg) entre deux listes de positions célestes."""
    p1, d1, p2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    a = (np.sin((d2 - d1) / 2.0) ** 2
         + np.cos(d1) * np.cos(d2) * np.sin((p2 - p1) / 2.0) ** 2)
    return np.degrees(2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))))


def rendu_etoiles(forme, xy, amplitudes, fond=0.02, bruit=0.004, sigma=1.4,
                  graine=56):
    """Image synthétique : gaussiennes sous-pixel + fond + bruit gaussien."""
    rng = np.random.default_rng(graine)
    img = rng.normal(fond, bruit, forme).astype(np.float32)
    h, w = forme
    r = int(5 * sigma)
    for (x, y), a in zip(np.asarray(xy, float), amplitudes):
        ix, iy = int(round(x)), int(round(y))
        if ix - r < 0 or iy - r < 0 or ix + r >= w or iy + r >= h:
            continue
        xs = np.arange(ix - r, ix + r + 1, dtype=np.float64)
        ys = np.arange(iy - r, iy + r + 1, dtype=np.float64)
        r2 = (xs[None, :] - x) ** 2 + (ys[:, None] - y) ** 2
        img[iy - r:iy + r + 1, ix - r:ix + r + 1] += (
            a * np.exp(-r2 / (2 * sigma * sigma))).astype(np.float32)
    return img


def ecart_wcs_deg(w1, w2, forme, n=7):
    """Écart angulaire max (deg) entre deux WCS sur une grille couvrant
    `forme` (coins inclus)."""
    h, w = forme
    xs = np.linspace(0, w - 1, n)
    ys = np.linspace(0, h - 1, n)
    XX, YY = np.meshgrid(xs, ys)
    pts = np.column_stack([XX.ravel(), YY.ravel()])
    ra1, dec1 = w1.vers_radec(pts)
    ra2, dec2 = w2.vers_radec(pts)
    return float(ecart_ciel_deg(ra1, dec1, ra2, dec2).max())


def faux_solveur(wcs, appels=None):
    """Solveur FACTICE injectable : mêmes arguments et même convention de
    retour que `catalogues.resoudre` (wcs, info, message) ; `appels` compte
    les invocations — c'est ce qui prouve la résolution UNIQUE."""
    def solve(img, ra0, dec0, champ, dossier=None, limmag=None):
        if appels is not None:
            appels.append((float(ra0), float(dec0), float(champ)))
        return wcs, {"n_etoiles_img": 86, "n_etoiles_cat": 201,
                     "n_appariements": 53, "rms_px": 0.59,
                     "rms_arcsec": 1.45, "echelle_arcsec_px": 2.465,
                     "angle_deg": -8.0, "methode": "triangles"}, ""
    return solve


# ============================================ [1] analyse des indices
print("[1] analyse des indices : décimal, sexagésimal, heures, refus propres")
v, m = astro.analyser_angle("10.68333")
verifie(v is not None and abs(v - 10.68333) < 1e-9,
        f"décimal NU = DEGRÉS (10.68333 → {v:.5f}°)")
v, m = astro.analyser_angle("0h42m44s")
verifie(v is not None and abs(v - 10.683333) < 1e-5,
        f"« 0h42m44s » = HEURES → {v:.5f}° (attendu 10,68333°)")
v, m = astro.analyser_angle("00 42 44", en_heures=True)
verifie(v is not None and abs(v - 10.683333) < 1e-5,
        f"« 00 42 44 » (format OBJCTRA) → {v:.5f}°")
v, m = astro.analyser_angle("41d16m09s")
verifie(v is not None and abs(v - 41.269167) < 1e-5,
        f"« 41d16m09s » → {v:.5f}° (Dec)")
v, m = astro.analyser_angle("-05 12 30")
verifie(v is not None and abs(v + 5.208333) < 1e-5,
        f"signe porté par la 1re composante → {v:+.5f}°")
v, m = astro.analyser_angle("bonjour")
verifie(v is None and bool(m), f"texte illisible refusé (« {m} »)")
ra, dec, ch, m = astro.analyser_indices("10.68333", "41.26917", "2.6")
verifie(m == "" and abs(ra - 10.68333) < 1e-9 and abs(ch - 2.6) < 1e-9,
        "analyser_indices : triple valide accepté (aucune conversion cachée)")
ra, dec, ch, m = astro.analyser_indices("10.68333", "95", "2.6")
verifie(ra is None and "Dec hors bornes" in m, f"Dec 95° refusée (« {m} »)")
ra, dec, ch, m = astro.analyser_indices("10.68333", "41.26917", "99")
verifie(ra is None and "champ hors bornes" in m, f"champ 99° refusé (« {m} »)")
c = astro.champ_depuis_optique(243.0, 2.9011, 800)
verifie(c is not None and abs(c - 0.5466) < 0.002,
        f"champ depuis l'optique (243 mm, 2,9011 µm, 800 px → {c:.4f}°)")
verifie(astro.champ_depuis_optique(0.0, 2.9, 800) is None,
        "optique incomplète → None (jamais de division par zéro)")

# ================================= [2] indices lus dans l'en-tête FITS
print("[2] en-tête d'une brute : lecture STRICTE (OBJCTRA/OBJCTDEC/FOCALLEN)")
tmp = tempfile.mkdtemp(prefix="avastack_astro_")
brute = np.full((60, 800), 0.02, np.float32)


def ecrire(nom, entete=None):
    p = os.path.join(tmp, nom)
    save_image(p, brute, entete=entete)
    return p


p_nina = ecrire("nina.fit", {"OBJCTRA": "00 42 44", "OBJCTDEC": "+41 16 09",
                             "FOCALLEN": 243.0, "XPIXSZ": 2.9011})
ra, dec, champ, m = astro.indices_entete_fits(p_nina)
verifie(ra is not None and abs(ra - 10.683333) < 1e-4
        and dec is not None and abs(dec - 41.269167) < 1e-4
        and champ is not None and abs(champ - 0.5466) < 0.002,
        f"OBJCTRA/OBJCTDEC + FOCALLEN/XPIXSZ → AD {ra:.5f}°, Dec {dec:+.5f}°, "
        f"champ {champ:.4f}° (« {m} »)")
p_deg = ecrire("wcs.fit", {"RA": 10.68333, "DEC": 41.26917,
                           "FOCALLEN": 243.0, "PIXSIZE1": 2.9011})
ra, dec, champ, m = astro.indices_entete_fits(p_deg)
verifie(ra is not None and abs(ra - 10.68333) < 1e-6 and champ is not None,
        f"repli RA/DEC en degrés accepté (« {m} »)")
p_nu = ecrire("nu.fit")
ra, dec, champ, m = astro.indices_entete_fits(p_nu)
verifie(ra is None and "sans OBJCTRA" in m,
        f"sans mots-clés d'indices : refus explicite (« {m} »)")
p_pc = ecrire("partiel.fit", {"OBJCTRA": "00 42 44", "OBJCTDEC": "+41 16 09"})
ra, dec, champ, m = astro.indices_entete_fits(p_pc)
verifie(ra is not None and champ is None and "CHAMP non déductible" in m,
        f"indices lus mais champ indéductible → champ None (« {m[:52]}… »)")
ra, dec, champ, m = astro.indices_entete_fits(
    os.path.join(tmp, "absent.fit"))
verifie(ra is None and bool(m), f"fichier absent : refus propre (« {m[:40]}… »)")
ra, dec, champ, m = astro.indices_entete_fits(
    os.path.join(tmp, "image.png"))

# ================================ [3] SuiviAstrometrie : résolution UNIQUE
print("[3] SuiviAstrometrie : résolution unique, réessais bornés, invalidation")
FORME = (600, 800)                     # (H, W)
CRVAL = (10.700, 41.300)
ECH = 2.465 / 3600.0                   # 2,465 ″/px
W_VRAI = WcsTan(CRVAL, ((FORME[1] - 1) / 2.0, (FORME[0] - 1) / 2.0),
                [[-ECH, 0.0], [0.0, ECH]], forme=FORME)
CHAMP = FORME[1] * ECH

appels = []
s = astro.SuiviAstrometrie(solveur=faux_solveur(W_VRAI, appels))
verifie(not s.resolu and not s.pret, "session neuve : ni indices ni WCS")
verifie(s.peut_essayer(50) is False, "sans indices : aucune tentative possible")
s.indice(CRVAL[0], CRVAL[1], CHAMP)
verifie(s.pret and s.peut_essayer(50), "indices posés → tentative possible")
verifie(s.peut_essayer(2) is False,
        "empilement trop court (2 frames) → pas de tentative")
okk, msg = s.resoudre_sur(np.zeros(FORME, np.float32))
verifie(okk and s.resolu and len(appels) == 1,
        f"résolution UNIQUE ({len(appels)} appel du solveur)")
okk, _ = s.resoudre_sur(np.zeros(FORME, np.float32))
verifie(okk and len(appels) == 1 and not s.peut_essayer(50),
        "déjà résolu : le solveur n'est plus JAMAIS appelé (aucun re-solve)")
verifie((appels[0][0], appels[0][1]) == CRVAL
        and abs(appels[0][2] - CHAMP) < 1e-9,
        "les INDICES transmis au solveur sont ceux saisis (aucune invention)")
verifie(s.indice(CRVAL[0] + 0.1, CRVAL[1], CHAMP) is True and not s.resolu,
        "indices CHANGÉS → WCS oublié (autre cible/champ)")
verifie(s.indice(CRVAL[0] + 0.1, CRVAL[1], CHAMP) is False,
        "mêmes indices reposés → aucun effet (pas de re-solve en boucle)")

s2 = astro.SuiviAstrometrie(
    solveur=lambda *a, **k: (None, {}, "pas assez d'etoiles"))
s2.indice(CRVAL[0], CRVAL[1], CHAMP)
okk, msg = s2.resoudre_sur(np.zeros(FORME, np.float32))
verifie(not okk and "pas assez" in msg and s2.essais == 1,
        f"échec du solveur remonté tel quel (« {msg} »)")
verifie(not s2.peut_essayer(50), "échec récent → réessai DIFFÉRÉ (délai)")
verifie(s2.peut_essayer(50, maintenant=time.monotonic()
                        + astro.ASTRO_ESSAI_DELAI_S + 1.0) is True,
        "délai écoulé → réessai autorisé (empilement plus profond)")
for _ in range(astro.ASTRO_MAX_ESSAIS):
    s2.resoudre_sur(np.zeros(FORME, np.float32))
verifie(s2.essais == astro.ASTRO_MAX_ESSAIS
        and not s2.peut_essayer(50, maintenant=time.monotonic() + 1e6),
        f"plafond de {astro.ASTRO_MAX_ESSAIS} tentatives respecté (pas de boucle)")
verifie("chec apr" in s2.raison_attente(),
        f"la raison d'arrêt est exposée (« {s2.raison_attente()} »)")

# ======== [4] propagation & recadrage : vérité analytique + astropy.wcs
print("[4] propagation & recadrage : vérité analytique + référence astropy.wcs")
rng = np.random.default_rng(11)
pos = np.column_stack([rng.uniform(60, FORME[1] - 60, 40),
                       rng.uniform(60, FORME[0] - 60, 40)])
amp = rng.uniform(0.4, 1.0, 40)
ra_v, dec_v = W_VRAI.vers_radec(pos)
base = rendu_etoiles(FORME, pos, amp, graine=3)
D = (13.0, -7.0)               # la 2e image montre les étoiles en pos − D
ref = rendu_etoiles(FORME, pos - np.array(D), amp, graine=4)
p_new = pos - np.array(D)      # position des étoiles dans la NOUVELLE grille

s3 = astro.SuiviAstrometrie(solveur=faux_solveur(W_VRAI))
s3.indice(CRVAL[0], CRVAL[1], CHAMP)
s3.resoudre_sur(base)          # WCS de la grille de l'ancien empilement
al = StarAligner()
al.set_reference(base)
M, okk = al.compute(ref)
verifie(okk and M is not None,
        "StarAligner RÉEL : nouvelle référence ↔ ancien empilement appariés")
ok2, msg = s3.propager(M)
verifie(ok2 and s3.propagations == 1,
        f"propagation acceptée (matrice de l'aligneur, {s3.propagations})")
w_new, _ = s3.wcs_grille(None, forme=FORME)
ra_n, dec_n = w_new.vers_radec(p_new)
e = float(ecart_ciel_deg(ra_n, dec_n, ra_v, dec_v).max()) * 3600.0
verifie(e < 3.0, f"WCS PROPAGÉ vs vérité analytique : {e:.3f}″ (< 3″)")

cadre = (25, 40, FORME[0] - 15, FORME[1] - 20)      # (y0, x0, y1, x1)
w_crop, msg = s3.wcs_grille(cadre)
verifie(w_crop is not None, "WCS de la grille RECADRÉE calculé (translation)")
ra_c, dec_c = w_crop.vers_radec(p_new - np.array([cadre[1], cadre[0]]))
e2 = float(ecart_ciel_deg(ra_c, dec_c, ra_v, dec_v).max()) * 3600.0
verifie(e2 < 3.0, f"recadrage = simple TRANSLATION (+x0, +y0) : {e2:.3f}″")
h_c, w_c = cadre[2] - cadre[0], cadre[3] - cadre[1]
mc, msg = s3.mots_cles(cadre)
verifie(mc.get("CTYPE1") == "RA---TAN" and "CRVAL1" in mc and "CD1_1" in mc,
        f"mots-clés FITS produits (« {msg or 'ok'} »)")
verifie("AVARMS" in mc,
        f"AVARMS consigné (rms du ré-ajustement TAN : {mc.get('AVARMS')})")
xs = np.linspace(0, w_c - 1, 5)
ys = np.linspace(0, h_c - 1, 5)
XX, YY = np.meshgrid(xs, ys)
pts_c = np.column_stack([XX.ravel(), YY.ravel()])
ra_c2, dec_c2 = w_crop.vers_radec(pts_c)
entiere = fits.Header([(k, v) for k, v in mc.items() if k != "AVARMS"])
sky = WcsAstropy(entiere).all_pix2world(pts_c, 0)
e3 = float(np.degrees(np.hypot(
    (sky[:, 0] - ra_c2) * np.cos(np.radians(sky[:, 1])),
    sky[:, 1] - dec_c2)).max())
verifie(e3 < 1e-6,
        f"mots-clés ≡ astropy.wcs (référence INDÉPENDANTE) : {e3:.2e}°")

s4 = astro.SuiviAstrometrie()
mc_vide, msg_vide = s4.mots_cles(None)
verifie(mc_vide == {} and bool(msg_vide),
        f"sans WCS : aucun mot-clé inventé (« {msg_vide} »)")
M_nan = np.eye(2, 3)
M_nan[0, 2] = np.nan
verifie(s3.propager(M_nan)[0] is False, "matrice non finie refusée")
verifie(s3.propager(np.zeros((3, 3)))[0] is False, "matrice (3, 3) refusée")
verifie(s3.propager(np.array([[9.0, 0.0, 0.0], [0.0, 9.0, 0.0]]))[0] is False,
        "échelle cumulée aberrante refusée (le WCS reste celui d'avant)")
verifie(s3.propagations == 1, "aucune propagation comptée sur les refus")

verifie(ra is None and "PNG" in m, f"source sans en-tête FITS (« {m} »)")

# ===================== [5] worker RÉEL : en-tête WCS + ligne d'état
print("[5] worker RÉEL : mots-clés WCS dans la sauvegarde + ligne d'état")
ui.CONFIG = {}                              # bac à sable config (cf. pièges)
ui.sauver_config = lambda *a, **k: None
tmpw = tempfile.mkdtemp(prefix="avastack_astro_worker_")
root = tk.Tk()
root.withdraw()
app = ui.App(root)


class CameraMuette:
    """Caméra factice : ne renvoie plus aucune frame — la sauvegarde demandée
    est tout de même consommée par le worker (chemin réel de production)."""
    name = "muette"

    def read(self):
        return None


class WcsAstropyAdapte:
    """Adapte un astropy.wcs.WCS à l'interface `vers_radec` du projet, pour
    confronter les mots-clés ÉCRITS dans un fichier aux WCS du projet."""

    def __init__(self, w):
        self.w = w

    def vers_radec(self, xy):
        xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
        ra, dec = self.w.all_pix2world(xy, 0).T
        return ra, dec


app.camera = CameraMuette()
app.var_astro.set(True)
app.var_astro_ra.set("10.700")
app.var_astro_dec.set("41.300")
app.var_astro_champ.set(f"{CHAMP:.5f}")
app.suivi_astro = astro.SuiviAstrometrie(solveur=faux_solveur(W_VRAI))
app._on_astro()
_ind = app._astro_indices
verifie(app._astro_actif and _ind is not None
        and abs(_ind[0] - CRVAL[0]) < 1e-9 and abs(_ind[1] - CRVAL[1]) < 1e-9
        and abs(_ind[2] - CHAMP) < 1e-4,
        f"UI → worker : indices validés et case active (instantané Tk {_ind})")

st = LiveStacker(FORME, k=None, method="kappa", window=8)
for _ in range(4):                    # 4 frames : au-delà du minimum (3)
    st.add(base)
st.note_alignement(np.eye(2, 3))      # cadre d'intersection RÉEL (marge 3 px)
app.stacker = st
app._astro_tour(st)                   # une passe de worker (appel direct)
verifie(app.suivi_astro.resolu and app.suivi_astro.essais == 1,
        f"worker : résolution lancée sur l'empilement — {app.astro_info[:50]}…")
verifie("résolue" in app.astro_info and app.astro_couleur == "#1d7f1d",
        "ligne d'état : la mesure est annoncée (vert)")

p_fits = os.path.join(tmpw, "empilement_wcs.fits")
app.save_request = p_fits
app.running = True
th = threading.Thread(target=app._worker, daemon=True)
th.start()
t0 = time.time()
while time.time() - t0 < 8.0 and app.saved_path is None:
    time.sleep(0.05)
app.running = False
th.join(timeout=2.0)
verifie(os.path.isfile(p_fits), f"fichier écrit ({app.saved_path})")
h = fits.getheader(p_fits)
manquants = [k for k in ("CTYPE1", "CRVAL1", "CRVAL2", "CRPIX1", "CRPIX2",
                         "CD1_1", "CD1_2", "CD2_1", "CD2_2")
             if k not in h]
verifie(not manquants, f"mots-clés WCS présents dans l'en-tête (absents : {manquants})")
cadre_w = st.cadre
verifie(cadre_w is not None and cadre_w[0] > 0,
        f"recadrage d'intersection actif {cadre_w} — le WCS doit en tenir compte")
w_att, _ = app.suivi_astro.wcs_grille(cadre_w)
h_c2, w_c2 = cadre_w[2] - cadre_w[0], cadre_w[3] - cadre_w[1]
e5 = ecart_wcs_deg(w_att, WcsAstropyAdapte(WcsAstropy(h)), (h_c2, w_c2))
verifie(e5 * 3600.0 < 1e-3,
        f"en-tête écrit ≡ WCS de la grille recadrée attendue : {e5 * 3600.0:.2e}″")
ra_f, dec_f = WcsAstropy(h).all_pix2world(
    pos - np.array([cadre_w[1], cadre_w[0]]), 0).T
e6 = float(ecart_ciel_deg(ra_f, dec_f, ra_v, dec_v).max()) * 3600.0
verifie(e6 < 3.0,
        f"le FITS écrit est LOCALISABLE : étoiles replacées à {e6:.3f}″ de la vérité")


# ================= [6] re-stack RÉEL : le WCS est PROPAGÉ (jamais re-solvé)
print("[6] re-stack RÉEL : propagation du WCS sur la nouvelle grille")
app2 = ui.App(root)
app2.var_astro.set(True)
app2.var_astro_ra.set("10.700")
app2.var_astro_dec.set("41.300")
app2.var_astro_champ.set(f"{CHAMP:.5f}")
app2.suivi_astro = astro.SuiviAstrometrie(solveur=faux_solveur(W_VRAI))
app2.suivi_astro.indice(CRVAL[0], CRVAL[1], CHAMP)
okk, _ = app2.suivi_astro.resoudre_sur(base)     # WCS de la grille de départ
app2._mode_compo = False
app2.archive = ArchiveFrames(intervalle_s=0.0)   # 1 frame/s interdirait la 2e
app2.archive.ajouter(base)                       # brute 0 = référence initiale
app2.archive.ajouter(ref)                        # brute 1 = « meilleure » (pos − D)
app2._scores = [50, 200]                         # la brute 1 l'emporte
app2.aligner.set_reference(base)
app2._ref_score = 50
app2.stacker = LiveStacker(FORME, k=None, method="kappa", window=8)
app2.stacker.add(base)
app2.stacker.note_alignement(np.eye(2, 3))
verifie(app2.suivi_astro.resolu and app2.suivi_astro.propagations == 0,
        "re-stack : WCS de départ résolu (aucune propagation encore)")
info = app2._do_restack("banc")
verifie("re-stack 2/2" in info,
        f"re-stack effectué sur la meilleure brute (« {info[:52]}… »)")
verifie(app2.suivi_astro.propagations == 1 and app2.suivi_astro.essais == 1,
        f"WCS PROPAGÉ ({app2.suivi_astro.propagations}) sans re-solve "
        f"({app2.suivi_astro.essais} essai de solveur)")
verifie("propagation" in app2.astro_info,
        f"ligne d'état : propagation annoncée (« {app2.astro_info[:52]}… »)")
w_apres, _ = app2.suivi_astro.wcs_grille(None, forme=FORME)
ra_a, dec_a = w_apres.vers_radec(p_new)
e7 = float(ecart_ciel_deg(ra_a, dec_a, ra_v, dec_v).max()) * 3600.0
verifie(e7 < 3.0,
        f"WCS propagé sur la NOUVELLE grille : étoiles à {e7:.3f}″ de la vérité")
cadre2 = app2.stacker.cadre
w_crop2, _ = app2.suivi_astro.wcs_grille(cadre2)
ra_b, dec_b = w_crop2.vers_radec(
    p_new - np.array([cadre2[1], cadre2[0]]))
e8 = float(ecart_ciel_deg(ra_b, dec_b, ra_v, dec_v).max()) * 3600.0
verifie(e8 < 3.0,
        f"grille RECADRÉE après re-stack {cadre2} : étoiles à {e8:.3f}″")
mc2, _ = app2.suivi_astro.mots_cles(cadre2)
w_f2 = WcsAstropy(fits.Header([(k, v) for k, v in mc2.items()
                               if k != "AVARMS"]))
e9 = ecart_wcs_deg(w_crop2, WcsAstropyAdapte(w_f2),
                   (cadre2[2] - cadre2[0], cadre2[3] - cadre2[1]))
verifie(e9 * 3600.0 < 1e-2,
        f"mots-clés FITS de la nouvelle grille ≡ WCS propagé : "
        f"{e9 * 3600.0:.2e}″")

# ========= [7] ergonomie : bouton 📷 « Lire depuis l'image courante »
print("[7] bouton 📷 : indices lus de l'image courante → champs pré-remplis")
p_brute = os.path.join(tmpw, "brute_nina.fit")
save_image(p_brute, brute, entete={"OBJCTRA": "00 42 44",
                                   "OBJCTDEC": "+41 16 09",
                                   "FOCALLEN": 243.0, "XPIXSZ": 2.9011})


class CameraFichier(CameraMuette):
    """Caméra factice façon « dossier surveillé » : annonce son dernier
    fichier (`last_file`), comme FolderCamera au fil des brutes lues."""
    last_file = p_brute


app.camera = CameraFichier()
app.var_astro_ra.set("")
app.var_astro_dec.set("")
app.var_astro_champ.set("")
app._lire_indices_image()
verifie(bool(app.var_astro_ra.get()) and bool(app.var_astro_dec.get())
        and bool(app.var_astro_champ.get()),
        "les 3 champs sont PRÉ-REMPLIS (« %s », « %s », « %s »)"
        % (app.var_astro_ra.get(), app.var_astro_dec.get(),
           app.var_astro_champ.get()))
_ind2 = app._astro_indices
verifie(_ind2 is not None and abs(_ind2[0] - 10.683333) < 1e-4
        and abs(_ind2[1] - 41.269167) < 1e-4 and _ind2[2] is not None,
        "indices issus du header FITS VALIDÉS (aucune saisie manuelle)")
verifie(app._astro_source.startswith("image "),
        f"l'origine est annoncée (« {app._astro_source} »)")
app.camera = CameraMuette()        # plus aucun fichier disponible
app.saved_path = None
app.var_astro_ra.set("")
app.var_astro_dec.set("")
app.var_astro_champ.set("")
app._lire_indices_image()
verifie(app.var_astro_ra.get() == ""
        and "aucune image" in app._astro_msg_indices,
        f"sans image disponible : rien d'inventé (« {app._astro_msg_indices} »)")

root.destroy()

# ============================================================ récapitulatif
print()
if ok:
    print("BANC JALON 56 (branchement astrométrie) : TOUT AU VERT")
else:
    print("BANC JALON 56 (branchement astrométrie) : ÉCHECS — voir ci-dessus")
sys.exit(0 if ok else 1)

