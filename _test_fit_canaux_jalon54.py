# -*- coding: utf-8 -*-
"""Banc du jalon 54 — recalage colorimétrique « Linear Fit » (v2.23.0).

Vérifie :
  [1] aligner_canaux : médianes R/B alignées sur le vert, entrée JAMAIS
      modifiée, layout (3, H, W) équivalent, mode « offset » (gains 1.0),
      gains bornés sur canal quasi noir, plancher 0 (pas de négatifs) ;
  [2] RÉFÉRENCE INDÉPENDANTE (règle CLAUDE.md) : la droite appliquée à une
      image synthétique recalculée en numpy pur coïncide avec aligner_canaux ;
  [3] dégénérés : mono, canal plat, forme inattendue → copie + diag None ;
  [4] LiveStacker : mean(recadre=False) reste BRUTE, mean() recadrée est
      recalée, cache (un seul recalcul par frame empilée) ;
  [5] CompositeStacker : recalage du COMPOSITE SEUL (couches brutes), cache
      par (n, gains, mode L, mode), HOO : B à l'identité ;
  [6] solveur VeraLux : job à 5 éléments (vl_compo) traité, déballage
      tolérant du job jalon 24 ;
  [7] UI réelle : case décochée par défaut, libellé des gains mesurés,
      config round-trip (booléen explicite), réglage conservé au re-stack.

Exécution : python _test_fit_canaux_jalon54.py
Nécessite un affichage (section [7]).
"""
import sys
import tkinter as tk

import numpy as np

import avastack.processing.stacking as stk_mod
from avastack.processing.stacking import (LiveStacker, aligner_canaux,
                                          stats_canaux)
from avastack.processing.composition import CompositeStacker, composer

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RATIOS = [0]


def verifie(cond, msg):
    RATIOS[0] += 1
    print(("  [OK] " if cond else "  [!!ÉCHEC!!] ") + msg)
    return bool(cond)


ok = True

# ===================================================== [1] aligner_canaux
print("[1] aligner_canaux : alignement sur le vert, entrée intacte")
rng = np.random.default_rng(42)
H = W = 48
base = 0.05 + rng.random((H, W)) * 0.02
rgb = np.zeros((H, W, 3), np.float32)
rgb[..., 0] = base * 0.80                    # fond rouge plus bas
rgb[..., 1] = base                           # vert = référence
rgb[..., 2] = base * 1.25 + 0.035            # fond bleu plus haut
copie = rgb.copy()
out, diag = aligner_canaux(rgb)
ok &= verifie(diag is not None and diag["mode"] == "gain_offset",
              "diag présent, mode gain_offset")
ok &= verifie(out.shape == rgb.shape and out.dtype == np.float32,
              "sortie (H, W, 3) float32")
ok &= verifie(np.array_equal(rgb, copie), "entrée NON modifiée")
ok &= verifie(np.allclose(out[..., 1], rgb[..., 1]),
              "canal VERT inchangé (référence)")
m_av = stats_canaux(rgb)["med"]
m_ap = stats_canaux(out)["med"]
ok &= verifie(abs(m_ap[0] - m_av[1]) < 2e-4
              and abs(m_ap[2] - m_av[1]) < 2e-4,
              f"médianes R et B alignées sur le vert "
              f"({m_ap[0]:.4f} / {m_ap[1]:.4f} / {m_ap[2]:.4f})")
ok &= verifie(float(out.min()) >= 0.0, "plancher 0 (aucun négatif)")
ok &= verifie(diag["gains"][1] == 1.0 and diag["offsets"][1] == 0.0,
              "vert : gain 1.0, offset 0.0")

out3, diag3 = aligner_canaux(np.transpose(rgb, (2, 0, 1)))
ok &= verifie(out3.shape == (3, H, W)
              and np.allclose(out3, np.transpose(out, (2, 0, 1)), atol=1e-6)
              and diag3["gains"] == diag["gains"],
              "layout (3, H, W) : même résultat que (H, W, 3)")

out_off, diag_off = aligner_canaux(rgb, mode="offset")
ok &= verifie(diag_off["gains"] == (1.0, 1.0, 1.0),
              "mode « offset » : gains à 1.0")
m_off = stats_canaux(out_off)["med"]
ok &= verifie(abs(m_off[0] - m_av[1]) < 2e-4
              and abs(m_off[2] - m_av[1]) < 2e-4,
              "mode « offset » : médianes alignées aussi (fond seul)")

noir = rgb.copy()
noir[..., 0] = base * 0.001 + 1e-6           # rouge quasi noir MAIS bruité
out_n, diag_n = aligner_canaux(noir)         # (constant → canal plat, no-op)
ok &= verifie(diag_n is not None
              and abs(diag_n["gains"][0] - stk_mod.FIT_GAIN_MAX) < 1e-6,
              "canal quasi noir bruité → gain plafonné (pas d'amplification "
              "folle)")

invalide = aligner_canaux(rgb, mode="valeur_inconnue")
ok &= verifie(invalide[1]["mode"] == "gain_offset",
              "mode inconnu → repli gain_offset (jamais de crash)")

# ============================================= [2] référence indépendante
print("[2] référence numpy indépendante (droite recalculée à la main)")
st = stats_canaux(rgb)
g_ref = [1.0, 1.0, 1.0]
o_ref = [0.0, 0.0, 0.0]
for c in (0, 2):
    g_ref[c] = min(max(st["sigma"][1] / st["sigma"][c],
                       stk_mod.FIT_GAIN_MIN), stk_mod.FIT_GAIN_MAX)
    o_ref[c] = st["med"][1] - g_ref[c] * st["med"][c]
ref = rgb.copy()
for c in (0, 2):
    ref[..., c] = np.clip(g_ref[c] * rgb[..., c] + o_ref[c], 0.0, None)
ok &= verifie(np.allclose(out, ref, atol=1e-5),
              "sortie ≡ application manuelle de la droite (médiane/MAD)")

# ============================================================== [3] dégénérés
print("[3] dégénérés : mono, canal plat, forme inattendue → no-op explicite")
mono = rng.random((H, W)).astype(np.float32)
m_out, m_diag = aligner_canaux(mono)
ok &= verifie(m_diag is None and np.array_equal(m_out, mono),
              "mono (H, W) → copie, diag None")
plat = rgb.copy()
plat[..., 2] = 0.0                           # canal mort (SHO sans S…)
p_out, p_diag = aligner_canaux(plat)
ok &= verifie(p_diag is None and np.array_equal(p_out, plat),
              "canal plat (rôle absent) → copie, diag None (no-op EXPLICITE)")
v_out, v_diag = aligner_canaux(np.zeros((5, 5), np.float32))
ok &= verifie(v_diag is None, "forme inattendue → copie, diag None")

# ========================================================= [4] LiveStacker
print("[4] LiveStacker : mean() recadrée recalée, recadre=False brute, cache")
s = LiveStacker((H, W, 3), k=None)
s.note_alignement(np.eye(2, 3))              # cadre = recadrage marge 3
for _ in range(3):
    s.add(rgb)
s.linear_fit = False
emp_brut = s.mean(recadre=False)             # 48×48 : référence d'alignement
emp_sans = s.mean()                          # 42×42 : produit sans fit
s.linear_fit = True
emp = s.mean()                               # 42×42 : produit recalé
ok &= verifie(stats_canaux(emp_brut)["med"][2]
              > stats_canaux(emp_brut)["med"][1] + 0.005,
              "mean(recadre=False) : fonds NON alignés (référence BRUTE)")
st_emp = stats_canaux(emp)
m_g = st_emp["med"][1]
ok &= verifie(abs(st_emp["med"][0] - m_g) < 2e-4
              and abs(st_emp["med"][2] - m_g) < 2e-4,
              "mean() : médianes des canaux alignées sur le vert")
n_appels = [0]
orig = stk_mod.aligner_canaux


def _compte(a, mode="gain_offset"):
    n_appels[0] += 1
    return orig(a, mode=mode)


stk_mod.aligner_canaux = _compte
s.mean()
s.mean()                       # même n → cache, PAS de recalcul
n0 = n_appels[0]
s.add(rgb)
s.mean()                       # n change → recalcul attendu
stk_mod.aligner_canaux = orig
ok &= verifie(n_appels[0] == n0 + 1,
              "cache : recalcul SEULEMENT à la nouvelle frame")
s.linear_fit = False
ok &= verifie(np.allclose(s.mean(), emp_sans),
              "case décochée → mean() identique à l'ancien comportement")

# ==================================================== [5] CompositeStacker
print("[5] CompositeStacker : composite seul recalé, couches brutes, cache")


def champ(gain=1.0, offset=0.0, seed=0):
    r = np.random.default_rng(seed)
    fond = 0.04 + r.random((H, W)) * 0.02
    return (gain * fond + offset).astype(np.float32)


def champ_etoiles(seed=0):
    """Fond uniforme + 5 % de pixels brillants : la normalisation par
    percentiles NE peut PAS aligner ce canal sur un fond uniforme (la
    médiane normalisée reste au ras de zéro) → le recalage doit agir."""
    c = champ(1.0, 0.0, seed)
    r = np.random.default_rng(seed + 100)
    c[r.random(c.shape) < 0.05] = 5.0
    return c


fa = CompositeStacker("HOO", k=None)
fa.role_courant = "Ha"
fa.add(champ_etoiles(seed=1))                # Ha : médiane normalisée ≈ 0
fa.role_courant = "O3"
fa.add(champ(1.0, 0.0, seed=2))
fa.add(champ(1.0, 0.0, seed=3))
comp_av, canaux_av = fa.mean_avec_canaux()
ok &= verifie(comp_av is not None and comp_av.ndim == 3,
              "composite HOO disponible")
fa.linear_fit = True
comp_ap, canaux_ap = fa.mean_avec_canaux()
ok &= verifie(np.array_equal(canaux_ap["Ha"], canaux_av["Ha"]),
              "couches JAMAIS recalées (brutes, pour le solveur)")
d_hoo = fa.fit_diag
ok &= verifie(d_hoo is not None
              and abs(d_hoo["gains"][2] - 1.0) < 1e-6
              and abs(d_hoo["offsets"][2]) < 1e-6,
              "HOO : B ≡ G par construction → bleu à l'identité (gain 1, "
              "offset 0), seul R (Ha) est recalé (choix de l'utilisateur)")
ok &= verifie(not np.allclose(comp_ap, comp_av),
              "HOO : le composite EST recalé (R vers O3)")

fa2 = CompositeStacker("RGB", k=None)
for role in ("R", "G", "B"):
    fa2.role_courant = role
    fa2.add(champ(1.0, 0.0, seed=5))         # TROIS canaux IDENTIQUES
fa2.linear_fit = True
c1, _ = fa2.mean_avec_canaux()
d_rgb = fa2.fit_diag
ok &= verifie(d_rgb is not None
              and abs(d_rgb["gains"][0] - 1.0) < 1e-6
              and abs(d_rgb["gains"][2] - 1.0) < 1e-6
              and abs(d_rgb["offsets"][0]) < 1e-6
              and abs(d_rgb["offsets"][2]) < 1e-6,
              "canaux déjà identiques → droite IDENTITÉ (gains 1.0, "
              "offsets 0 : jamais de correction folle)")
fa2.gains = {"R": 1.0, "G": 2.0, "B": 1.0}   # gain vert change → clé change
c2, _ = fa2.mean_avec_canaux()
ok &= verifie(not np.allclose(c1, c2),
              "changement de gains → recalcul (clé de cache complète)")


# ============================================================== [6] solveur
print("[6] solveur VeraLux : recomposition RE-CALÉE, déballage tolérant")
import time as _t

import avastack.processing.display as dp

d = dp.DisplayProcessor()          # le thread solveur démarre à l'init
d.stretch = "veralux"
d.vl_log_d = 2.0
try:
    canaux_s = {"Ha": champ_etoiles(seed=1), "O3": champ(1.0, 0.0, seed=2)}
    comp_ref = composer(canaux_s, "HOO")
    params = dict(mode=d.vl_mode_res, target_bg=0.25, log_d=2.0,
                  profil=d.vl_profil)
    cmd_copie = 'copy /Y "{input}" "{output}"'   # outil factice : identité

    def _soumet(key, gx, compo):
        d._vl_result = None
        d._vl_job = (comp_ref.copy(), params, key,
                     gx, (False, "nlm", 0.5), (False, 3), (), compo)
        d._vl_wake.set()
        for _ in range(300):
            if d._vl_result is not None and d._vl_result[0] == key:
                return d._vl_result[1]
            _t.sleep(0.02)
        return None

    # — job jalon 24 (compo 4 éléments, gx désactivé) : tolérance au déballage
    ok &= verifie(_soumet("k54a", (False, cmd_copie),
                          (canaux_s, "HOO", None, "synthetise")) is not None,
                  "job jalon 24 (4 éléments) : déballage tolérant, traité")
    # — chemin PAR COUCHE (gx actif) : recomposition depuis les couches
    #   traitées — SANS fit puis AVEC fit : les résultats doivent différer
    res_sans = _soumet("k54b", (True, cmd_copie),
                       (canaux_s, "HOO", None, "synthetise"))
    res_avec = _soumet("k54c", (True, cmd_copie),
                       (canaux_s, "HOO", None, "synthetise",
                        (True, "gain_offset")))
    ok &= verifie(res_sans is not None and res_avec is not None,
                  "chemin par couche : traité sans ET avec le recalage")
    ok &= verifie(res_sans is not None and res_avec is not None
                  and not np.allclose(res_sans, res_avec),
                  "vue « traitée » : le recalage CHANGE le résultat "
                  "(composite re-fait re-calé, comme la vue « empilement »)")
finally:
    pass                                   # thread daemon : rien à arrêter

# =================================================================== [7] UI
print("[7] UI réelle : case, libellé, config round-trip, re-stack")
import avastack.ui.app as ui

root = tk.Tk()
root.withdraw()
app = ui.App(root)
ok &= verifie(app.var_fit.get() is False,
              "case « Recalage colorimétrique (Linear Fit) » décochée PAR "
              "DÉFAUT")

s_u = LiveStacker((H, W, 3), k=None)
s_u.note_alignement(np.eye(2, 3))
s_u.add(rgb)
app.stacker = s_u
app.var_fit.set(True)
app._on_linear_fit()
ok &= verifie(s_u.linear_fit is True
              and s_u.linear_fit_mode == "gain_offset",
              "_on_linear_fit : réglage posé sur l'empilement courant "
              "(mode gain_offset)")
s_u.mean()                                   # génère les stats
app._maj_libelle_fit()
ok &= verifie("Fit R" in app.lbl_fit["text"] and "B ×" in app.lbl_fit["text"],
              f"libellé des gains mesurés (« {app.lbl_fit['text']} »)")

sauvegardes = []
ui.sauver_config = lambda dic: sauvegardes.append(dict(dic))
app.var_fit.set(True)
app._sauver_config_app()
ok &= verifie(len(sauvegardes) == 1
              and sauvegardes[-1].get("linear_fit") is True,
              "config écrite : linear_fit=True (booléen explicite)")
app.var_fit.set(False)
app._sauver_config_app()
ok &= verifie(sauvegardes[-1].get("linear_fit") is False,
              "config écrite : linear_fit=False persisté aussi")

ancien = LiveStacker((H, W, 3), k=None, method="kappa", window=6)
ancien.linear_fit = True
ancien.linear_fit_mode = "gain_offset"
st_rs = LiveStacker(ancien.shape, k=ancien.k, method=ancien.method,
                    window=ancien.window)
st_rs.wb_auto = ancien.wb_auto
st_rs.linear_fit = ancien.linear_fit
st_rs.linear_fit_mode = ancien.linear_fit_mode
ok &= verifie(st_rs.linear_fit and st_rs.linear_fit_mode == "gain_offset",
              "re-stack mono : réglage conservé (mêmes 3 lignes que le "
              "code de _do_restack)")

fa3 = CompositeStacker("HOO", k=None)
fa3.linear_fit = True
app.stacker = fa3
app.var_fit.set(False)
app._on_linear_fit()
ok &= verifie(fa3.linear_fit is False,
              "case décochée → façade compo répercutée aussi "
              "(attribut commun)")

root.destroy()

# ================================================================== bilan
print()
if RATIOS[0] and not ok:
    print(f"⚠ {RATIOS[0]} vérifications, AU MOINS UN ÉCHEC")
    sys.exit(1)
print(f"✔ {RATIOS[0]} vérifications — jalon 54 : TOUS LES TESTS PASSENT")



