# -*- coding: utf-8 -*-
"""Banc du jalon 135 — étape ③ du plan ⑪ : PLUS de repli « phase » en narrowband.

CHANTIER CAUSE AMONT, étape ③ (18/10/2026). En HOO/SHO la cascade est
TRIANGLES → ÉTOILES → PHASE, et une « réussite » de phase (translation SEULE)
court-circuite le réessai +180° de `compute` : c'est la cause MESURÉE au ⑩ en
broadband (11/50 puis 12/49 frames B empilées à l'envers sur un champ à
+177,07°).

MESURE qui précède la décision (hors dépôt, `_mesure_156_phase_narrowband.py`) :
109 frames RÉELLES, 3 jeux multi-nuits, deux `StarAligner` au code inchangé ne
différant QUE par l'interrupteur → **0 refus AVANT comme APRÈS**, méthodes
IDENTIQUES frame par frame ; la phase n'a JAMAIS été le chemin retenu. Limite
mesurée : aucun frame n'exigeait le +180°, donc ces jeux disent le COÛT (nul),
pas le RISQUE.

ÉTAPE ③ LIVRÉE ICI : `PHASE_EN_NARROWBAND = False` et `repli_phase_session()`
qui lit L'UNE OU L'AUTRE constante (un seul endroit décide ; le worker ne fait
qu'appliquer). L'ordre de la cascade, le verrou à deux conditions de
`_sans_phase` et les aligneurs du Ha de la VOIE A sont INCHANGÉS.

Ce banc vérifie :
  [1] L'INTERRUPTEUR : narrowband → False (état livré), broadband → False, et
      la BASCULE des deux constantes (comparaison possible sans toucher au code) ;
  [2] COMPATIBILITÉ : `StarAligner()` reste à True (bancs et appelants directs
      inchangés) et `_sans_phase` exige TOUJOURS les DEUX verrous ;
  [3] LE PIÈGE, AU NIVEAU DU CÂBLAGE : une « réussite » de phase en translation
      seule est-elle FINALE en narrowband ? Oui avec l'interrupteur à True
      (angle 0 sur une frame impossible à apparier ⇒ empilée à l'envers), NON
      avec l'interrupteur livré (`_phase` JAMAIS appelée, frame refusée) ;
  [4] LE RÉESSAI +180° N'EST PAS CASSÉ en narrowband : champ riche retourné de
      177,07° → matrice |angle| ≈ 177°, résidu < 2 px contre la pose VRAIE ;
  [5] LE COÛT MESURÉ : un champ riche translaté s'aligne SANS phase ; un champ
      FAIBLE (contraste 0,06) que seule la phase plaçait est ACCEPTÉ phase ON et
      REFUSÉ phase OFF — c'est le coût (ici synthétique), pas un défaut ;
  [6] TABLE PAR RÔLE (S2/Ha/O3) : 3 nettes, 2 faibles, 2 retournées, 1 retournée
      faible par rôle, dans les deux modes — aucune frame à l'envers, les nettes
      et les retournées passent, les faibles sont refusées et COMPTÉES ;
  [7] SESSION HOO RÉELLE : le worker applique l'interrupteur (False), garde
      `triangles_seuls=True`, empile Ha + O3 sans refus et n'utilise jamais
      « phase ».

Exécution : python bancs/_test_phase_narrowband_jalon135.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (et non plus à côté de l'application).
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import threading
import time
import tkinter as tk

import numpy as np
import cv2

cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
images.CFA_MODE = "Non"              # brutes synthétiques MONO
import avastack.ui.app as ui
ui.CONFIG = {}                       # config HERMÉTIQUE (règle du projet)
ui.sauver_config = lambda *a, **k: None   # JAMAIS le vrai config.json
import avastack.processing.alignment as align_mod

if hasattr(sys.stdout, "reconfigure"):    # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --------------------------------------------------------------- scènes de test
H, W = 200, 260
SHAPE = (H, W)
YY, XX = np.mgrid[0:H, 0:W]


def positions(graine, n, marge=20):
    """Positions d'étoiles FIXES (même ciel pour tous les « filtres »)."""
    pr = np.random.default_rng(graine)
    return [(float(pr.uniform(marge, W - marge)),
             float(pr.uniform(marge, H - marge)),
             float(pr.uniform(0.3, 0.9))) for _ in range(n)]


POS_RICHES = positions(99, 30)
POS_AUTRES = positions(7, 30)        # un AUTRE champ : aucun appariement possible


def ciel(pos, graine, fond=0.03, bruit=0.005, contraste=1.0, flou=0.0):
    """Champ d'étoiles + bruit indépendant (graine) — le ciel d'un « filtre »."""
    img = np.full(SHAPE, fond, np.float32)
    for x, y, a in pos:
        img += (a * np.exp(-((YY - y) ** 2 + (XX - x) ** 2)
                           / (2.0 * 1.3 ** 2))).astype(np.float32)
    img = fond + contraste * (img - fond)
    if flou:
        img = cv2.GaussianBlur(img, (0, 0), float(flou))
    img += np.random.default_rng(graine).normal(0, bruit, img.shape).astype(
        np.float32)
    return img


def transforme(img, deg, dx, dy):
    """Rotation autour du centre + translation (sens `warpAffine`) → (img, M)."""
    M = cv2.getRotationMatrix2D((W / 2.0, H / 2.0), deg, 1.0)
    M[0, 2] += dx
    M[1, 2] += dy
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR), M


def pose_inverse(Mv):
    """Matrice frame → référence attendue (inverse de la pose vraie)."""
    return np.linalg.inv(np.vstack([Mv, [0.0, 0.0, 1.0]]))[:2]


def residu_grille(M_rendue, M_vraie):
    """Résidu MÉDIAN (px) entre la matrice rendue et la pose VRAIE, sur une
    grille de 5 points répartis dans le champ (aucune statistique globale)."""
    pts = np.array([[0.15 * W, 0.15 * H], [0.85 * W, 0.15 * H],
                    [0.50 * W, 0.50 * H], [0.15 * W, 0.85 * H],
                    [0.85 * W, 0.85 * H]], np.float32).reshape(-1, 1, 2)
    attendu = cv2.transform(pts, pose_inverse(M_vraie).astype(np.float32))[:, 0]
    rendu = cv2.transform(pts, np.asarray(M_rendue, np.float32))[:, 0]
    return float(np.median(np.hypot(*(attendu - rendu).T)))


def angle_deg(M):
    a, b = float(M[0, 0]), float(M[1, 0])
    return float(np.degrees(np.arctan2(b, a)))


# ==================================== [1] L'INTERRUPTEUR
print("[1] repli_phase_session : narrowband → False (étape ③), broadband → False")
verifie(align_mod.PHASE_EN_NARROWBAND is False,
        "PHASE_EN_NARROWBAND vaut False (décision de l'étape ③)")
verifie(align_mod.PHASE_EN_BROADBAND is False,
        "PHASE_EN_BROADBAND vaut False (décision de l'étape ①, inchangée)")
verifie(align_mod.repli_phase_session(True) is False,
        "narrowband (HOO/SHO) : repli « phase » ÉCARTÉ")
verifie(align_mod.repli_phase_session(False) is False,
        "broadband (RGB/LRGB±Ha, mono, OSC) : repli « phase » ÉCARTÉ")
align_mod.PHASE_EN_NARROWBAND = True         # bascule de l'interrupteur
verifie(align_mod.repli_phase_session(True) is True,
        "interrupteur basculé à la main : la phase revient en narrowband "
        "(comparaison possible sans toucher au code)")
verifie(align_mod.repli_phase_session(False) is False,
        "…et le broadband n'est PAS touché par cette bascule")
align_mod.PHASE_EN_NARROWBAND = False
verifie(align_mod.repli_phase_session(True) is False,
        "interrupteur remis : la phase est de nouveau écartée en narrowband")

# ==================================== [2] COMPATIBILITÉ
print("[2] StarAligner() inchangé (True) et DEUX verrous dans _sans_phase")
al0 = align_mod.StarAligner()
verifie(al0.repli_phase is True,
        "StarAligner() par défaut : phase autorisée (bancs et appelants "
        "directs inchangés — le worker, lui, la fixe par session)")
ref_riche = ciel(POS_RICHES, 900)
fr_dither, _Mv_d = transforme(ciel(POS_RICHES, 901), 0.0, 6.0, 3.0)
al0.set_reference(ref_riche)
g_partage = al0._norm8(fr_dither, al0._ref_lo, al0._ref_hi)
Mp, okp = al0._sans_phase(g_partage, True)
verifie(okp and angle_deg(Mp) < 1.0,
        "phase autorisée : une translation seule est rendue "
        f"(Δ=({Mp[0, 2]:+.1f},{Mp[1, 2]:+.1f}) px)")
al0.repli_phase = False
Ma, oka = al0._sans_phase(g_partage, True)
verifie(not oka and np.allclose(Ma, np.eye(2, 3)),
        "interrupteur à False : _sans_phase rend l'IDENTITÉ + REFUS")
verifie(not al0._sans_phase(g_partage, False)[1],
        "avec_phase=False (réessai +180°) reste un refus, interrupteur ou non")

# ==================================== [3] LE PIÈGE, au niveau du câblage
print("[3] une réussite « phase » (translation seule) est-elle FINALE en "
      "narrowband ?")


class AligneurEspion(align_mod.StarAligner):
    """`_phase` remplacée par une réussite en TRANSLATION SEULE — exactement ce
    que le ⑩ a mesuré sur les vraies brutes (angle 0 sur une frame impossible à
    apparier)."""

    appels_phase = 0

    def _phase(self, g):
        AligneurEspion.appels_phase += 1
        M = np.array([[1.0, 0.0, 5.0], [0.0, 1.0, -3.0]])
        self._last_t = (5.0, -3.0)
        self._noter(M, "phase")
        return M, True


fr_etranger = ciel(POS_AUTRES, 902)          # aucun appariement possible
align_mod.PHASE_EN_NARROWBAND = True         # « ancien » comportement
esp_on = AligneurEspion()
esp_on.triangles_seuls = True
esp_on.repli_phase = align_mod.repli_phase_session(True)
esp_on.set_reference(ref_riche)
M_on, ok_on = esp_on.compute(fr_etranger)
verifie(ok_on and esp_on.dernier is not None
        and esp_on.dernier["methode"] == "phase" and abs(angle_deg(M_on)) < 1.0,
        "phase autorisée : la « réussite » en translation seule est FINALE "
        f"(angle {angle_deg(M_on):+.1f}° sur un champ étranger)")
verifie(esp_on.appels_phase == 1, "…la phase a bien été consultée")
align_mod.PHASE_EN_NARROWBAND = False        # état LIVRÉ
AligneurEspion.appels_phase = 0
esp_off = AligneurEspion()
esp_off.triangles_seuls = True
esp_off.repli_phase = align_mod.repli_phase_session(True)
esp_off.set_reference(ref_riche)
M_off, ok_off = esp_off.compute(fr_etranger)
verifie(esp_off.appels_phase == 0,
        "phase ÉCARTÉE (état livré) : _phase n'est JAMAIS consultée (0 appel)")
verifie(not ok_off,
        "…et la frame est REFUSÉE, jamais empilée à l'envers")

# ==================================== [4] le réessai +180° n'est pas cassé
print("[4] narrowband, champ retourné de 177,07° : la frame est RETOURNÉE")
fr_flip, Mv_flip = transforme(ciel(POS_RICHES, 903), 177.07, 40.0, -25.0)
al4 = align_mod.StarAligner()
al4.triangles_seuls = True
al4.repli_phase = align_mod.repli_phase_session(True)
al4.set_reference(ref_riche)
M4, ok4 = al4.compute(fr_flip)
ang4 = abs(angle_deg(M4)) if (ok4 and M4 is not None) else None
verifie(ok4 and ang4 is not None and 170.0 <= ang4 <= 190.0,
        f"retournée de 177,07° : matrice RETOURNÉE (|angle| = "
        f"{'—' if ang4 is None else f'{ang4:.2f}'}°, méthode « "
        f"{al4.dernier['methode'] if al4.dernier else '?'} »)")
if ok4 and M4 is not None:
    res4 = residu_grille(M4, Mv_flip)
    verifie(res4 < 2.0,
            f"…résidu de {res4:.2f} px contre la pose VRAIE (grille de 5 points)")
    verifie(al4.dernier is not None and al4.dernier["methode"] != "phase",
            "…et ce n'est PAS la phase qui l'a placée")

# ==================================== [5] ordre inchangé + coût mesuré
print("[5] ordre triangles → étoiles conservé ; le coût de ③ est mesuré")
al5 = align_mod.StarAligner()
al5.triangles_seuls = True
al5.repli_phase = align_mod.repli_phase_session(True)
al5.set_reference(ref_riche)
fr_nette, _Mv_n = transforme(ciel(POS_RICHES, 904), 0.0, 6.0, 3.0)
M5, ok5 = al5.compute(fr_nette)
verifie(ok5 and al5.dernier is not None and al5.dernier["methode"] != "phase",
        f"champ RICHE translaté : aligné SANS phase (méthode « "
        f"{al5.dernier['methode'] if al5.dernier else '?'} »)")
if ok5 and M5 is not None:
    d5 = al5.dernier or {}
    verifie(abs(float(d5.get("dx", 0.0)) + 6.0) < 1.5
            and abs(float(d5.get("dy", 0.0)) + 3.0) < 1.5,
            f"…translation retrouvée (Δ=({d5.get('dx', 0.0):+.1f},"
            f"{d5.get('dy', 0.0):+.1f}) px pour (−6, −3) attendus)")

# Champ FAIBLE (contraste 0,06) : ni triangles, ni « étoiles » — seule la phase
# le plaçait. C'est la population que l'étape ③ REFUSE désormais.
ref_faible = ciel(POS_RICHES, 905, contraste=0.06, bruit=0.008)
fr_faible, _Mv_f = transforme(ciel(POS_RICHES, 906, contraste=0.06,
                                   bruit=0.008), 0.0, 6.0, 3.0)
align_mod.PHASE_EN_NARROWBAND = True
al5o = align_mod.StarAligner()
al5o.triangles_seuls = True
al5o.repli_phase = align_mod.repli_phase_session(True)
al5o.set_reference(ref_faible)
_Mo, oko = al5o.compute(fr_faible)
do = al5o.dernier or {}
verifie(oko and al5o.dernier is not None
        and al5o.dernier["methode"] == "phase",
        f"champ FAIBLE, phase autorisée : secouru par la phase "
        f"(Δ=({do.get('dx', 0.0):+.1f},{do.get('dy', 0.0):+.1f}) px)")
align_mod.PHASE_EN_NARROWBAND = False
al5f = align_mod.StarAligner()
al5f.triangles_seuls = True
al5f.repli_phase = align_mod.repli_phase_session(True)
al5f.set_reference(ref_faible)
_Mf, okf = al5f.compute(fr_faible)
verifie(not okf,
        "le MÊME champ faible, phase écartée (état livré) : REFUSÉ — c'est le "
        "coût mesuré ; en RÉEL il est de 0 frame sur 109 (cf. docstring)")

# ==================================== [6] MESURE DES REFUS PAR RÔLE
print("[6] REFUS PAR RÔLE : 8 frames × 3 rôles narrowband, dans les deux modes")
ROLES = ("S2", "Ha", "O3")
FONDS = {"S2": 0.050, "Ha": 0.035, "O3": 0.045}
rng_pop = np.random.default_rng(2026)


def population(role):
    """8 frames du rôle : 3 NETTES, 2 FAIBLES (seule la phase les plaçait),
    2 RETOURNÉES nettes (le +180° doit les sauver) et 1 RETOURNÉE FAIBLE
    (la population du ⑩ : une translation seule l'empilerait à l'envers)."""
    i = ROLES.index(role)
    lots = []

    def dither():
        return float(rng_pop.uniform(-8.0, 8.0)), float(rng_pop.uniform(-8.0, 8.0))

    for k in range(3):
        dx, dy = dither()
        lots.append(("nette", ciel(POS_RICHES, 100 + 10 * i + k,
                                   FONDS[role], 0.005), 0.0, dx, dy))
    for k in range(2):
        dx, dy = dither()
        lots.append(("faible", ciel(POS_RICHES, 200 + 10 * i + k,
                                    FONDS[role], 0.008, 0.10, 1.0),
                     0.0, dx, dy))
    for k in range(2):
        dx, dy = dither()
        lots.append(("retournee", ciel(POS_RICHES, 300 + 10 * i + k,
                                       FONDS[role], 0.005), 177.07, dx, dy))
    dx, dy = dither()
    lots.append(("retournee_faible", ciel(POS_RICHES, 400 + i,
                                          FONDS[role], 0.008, 0.10, 1.0),
                 177.07, dx, dy))
    return lots


def mesurer(role, phase):
    """Compte, POUR CE RÔLE : nettes justes, faibles acceptées/refusées,
    retournées justes/refusées, et frames empilées À L'ENVERS (angle ~0)."""
    al = align_mod.StarAligner()
    al.triangles_seuls = True            # HOO/SHO (jalon 21)
    al.repli_phase = phase
    al.set_reference(ciel(POS_RICHES, 900 + ROLES.index(role),
                          FONDS[role], 0.005))
    c = {"nettes_ok": 0, "nettes_refus": 0, "faibles_ok": 0, "faibles_refus": 0,
         "flips_ok": 0, "flips_refus": 0, "flip_faible_ok": 0,
         "flip_faible_refus": 0, "a_l_envers": 0}
    for cat, img, deg, dx, dy in population(role):
        fr, _Mv = transforme(img, deg, dx, dy)
        M, okk = al.compute(fr)
        ang = abs(angle_deg(M)) if (okk and M is not None) else None
        if cat == "nette":
            if okk and ang is not None and ang < 10.0:
                c["nettes_ok"] += 1
            else:
                c["nettes_refus"] += 1
        elif cat == "faible":
            c["faibles_ok" if okk else "faibles_refus"] += 1
        else:
            prefixe = "flip_faible" if cat == "retournee_faible" else "flips"
            if okk and ang is not None and ang < 10.0:
                c["a_l_envers"] += 1
            elif okk and ang is not None and ang >= 170.0:
                c[prefixe + "_ok"] += 1
            else:
                c[prefixe + "_refus"] += 1
    return c


mesures = {ph: {r: mesurer(r, ph) for r in ROLES} for ph in (True, False)}
for ph, tag in ((True, "phase AUTORISÉE (ancien comportement)"),
                (False, "phase ÉCARTÉE (étape ③ — état livré)")):
    print(f"  -- {tag}")
    for r in ROLES:
        c = mesures[ph][r]
        print(f"     {r} : nettes {c['nettes_ok']}/3 · faibles "
              f"{c['faibles_ok']}/2 acceptées ({c['faibles_refus']} refus) · "
              f"retournées {c['flips_ok']}/2 justes, {c['flips_refus']} refus · "
              f"retournée faible "
              f"{'refusée' if c['flip_faible_refus'] else 'acceptée'}"
              f" · À L'ENVERS {c['a_l_envers']}")

faibles_on = sum(mesures[True][r]["faibles_ok"] for r in ROLES)
refus_off = sum(mesures[False][r]["faibles_refus"] for r in ROLES)
refus_on = sum(mesures[True][r]["faibles_refus"] for r in ROLES)
for r in ROLES:
    c_on, c_off = mesures[True][r], mesures[False][r]
    verifie(c_off["a_l_envers"] == 0 and c_on["a_l_envers"] == 0,
            f"{r} : AUCUNE frame à l'envers (phase écartée "
            f"{c_off['a_l_envers']}, autorisée {c_on['a_l_envers']})")
    verifie(c_off["nettes_ok"] == 3,
            f"{r} : les 3 frames NETTES passent toujours "
            f"({c_off['nettes_ok']}/3, {c_off['nettes_refus']} refus)")
    verifie(c_off["flips_ok"] == 2,
            f"{r} : les 2 RETOURNÉES nettes sont bien retournées "
            f"({c_off['flips_ok']}/2)")
verifie(faibles_on >= 4,
        f"phase autorisée : {faibles_on}/6 frames FAIBLES secourues par la "
        f"phase (2 par rôle à la conception)")
verifie(refus_off > refus_on,
        f"phase écartée : {refus_off}/6 FAIBLES REFUSÉES contre {refus_on}/6 "
        f"avec la phase — le COÛT de ③ est mesuré PAR RÔLE (en réel : 0 frame "
        f"sur 109)")

# ==================================== [7] SESSION HOO RÉELLE
print("[7] SESSION HOO RÉELLE : le worker applique l'interrupteur")


class ArchiveRapide(ui.ArchiveFrames):
    """Archive sans limite de débit (test)."""

    def __init__(self, *a, **k):
        k.setdefault("intervalle_s", 0.0)
        super().__init__(*a, **k)


class CamRoles:
    """Source de test : liste figée de (image, rôle) — comme MultiFolderCamera."""

    name = "test"

    def __init__(self, items):
        self.items = items
        self.i = 0

    def read(self):
        self.i += 1
        return None if self.i > len(self.items) else self.items[self.i - 1]


class _Val:
    """Bouchon de variable Tk : `var.get()` est interdit hors thread principal."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


ui.ArchiveFrames = ArchiveRapide
ui.App._dire = lambda *a, **k: None      # jamais de boîte MODALE dans un banc
root = tk.Tk()
root.withdraw()
app = ui.App(root)
app.rejeter_flou = False                 # test déterministe (aucun filtre)
app.ref_refresh = 0                      # pas de rafraîchissement de référence
app._veut_restack = lambda: False        # re-stack AUTO neutralisé
app.var_wb = _Val(False)
app.var_wb_force = _Val(1.0)
# Composition HOO : l'ancre est TOUJOURS une brute Ha (jalon 21) → le 1er item
# doit être Ha, sinon la session attend et rien ne s'empile.
FR = [("Ha", 0.0, 4.0, -3.0), ("O3", 0.0, -5.0, 2.0),
      ("Ha", 0.0, 7.0, 1.0), ("O3", 0.0, 2.0, -6.0)]
frames = []
for i, (role, deg, dx, dy) in enumerate(FR):
    frames.append((transforme(ciel(POS_RICHES, 800 + i, FONDS[role], 0.005),
                              deg, dx, dy)[0], role))
app.camera = CamRoles(frames)
app._mode_compo = True
app._compo_nom = "HOO"

try:
    app.running = True
    app.empilement_on = True             # le worker n'empile que si armé
    th = threading.Thread(target=app._worker, daemon=True)
    th.start()
    t0 = time.time()
    while time.time() - t0 < 30.0 and (app.stacker is None or app.stacker.n < 4):
        time.sleep(0.05)
    app.running = False
    th.join(timeout=5.0)
    verifie(app.aligner.repli_phase is False,
            "session HOO : le worker a fixé repli_phase = False sur l'aligneur "
            "PARTAGÉ (étape ③)")
    verifie(app.aligner.triangles_seuls is True,
            "…et triangles_seuls = True (narrowband, jalon 21, inchangé)")
    verifie(app.aligner_ha.repli_phase is True
            and app._recalage_ha_aligneur.repli_phase is True,
            "…et laissé True aux aligneurs du Ha de la VOIE A (hors périmètre)")
    verifie(app.bad_frames == 0 and not app.bad_frames_par_role,
            f"aucun refus (bad={app.bad_frames}, par rôle="
            f"{app.bad_frames_par_role})")
    verifie(app.stacker is not None and app.stacker.n == 4,
            f"les 2 rôles sont empilés (n="
            f"{0 if app.stacker is None else app.stacker.n})")
    meth = str((app.aligner.dernier or {}).get("methode", ""))
    verifie(app.aligner.dernier is not None and "phase" not in meth,
            f"la méthode retenue n'est pas la phase (« {meth} »)")
finally:
    app.running = False
    for a in app.archives.values():
        a.vider()

root.destroy()

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)




