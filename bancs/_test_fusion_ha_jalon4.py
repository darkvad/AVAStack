# -*- coding: utf-8 -*-
"""Banc v2.91.0 — JALON J4 : LE CONTINUUM DU Ha, TROIS MÉTHODES.

Le J2 (v2.88.0, VALIDÉ EN RÉEL) estime le continuum par les BANDES PASSANTES :
`k = Q × 7/100` (théorie), ramené dans l'espace du Ha par `échelle(Ha)`. Le J4
ajoute les DEUX méthodes du plan figé du 15/10 — et rend VISIBLE le repli
(décision d'Alain du 19/10/2026) :

  · `bandes_passantes` : k = Q × (bw_ha / 100), bw_ha = 7 nm (défaut validé) ou
    3 nm (filtres serrés, courants) — la BANDE du filtre est choisie ;
  · `mediane`         : médiane du rapport Ha/R sur le continuum FRANC du champ
    (haut de R, sous les cœurs saturés), garde-fous de dispersion ;
  · `etoiles_5sigma`  : rapport des flux Ha/R des ÉTOILES détectées à 5σ
    (`stars.detecter_positions` + `photometrie.flux_ouverture`, rejet MAD).

Un échec de mesure NE CASSE RIEN : repli sur `bandes_passantes` avec le Q
courant, et `info["repli"]` + `info["raison"]` le disent — l'interface l'affiche
SUR LES CASES (J4).

Vérifie :
  [1] les TROIS méthodes, le choix de bande (7/3 nm), le Q par défaut de chaque
      méthode, les bornes et le dict complet de `fusion_ha_effectif` ;
  [2] `bandes_passantes` AU BIT (7 nm = J2 ; 3 nm = rapport 3/100), et le
      facteur exact de chaque bande ;
  [3] `mediane` retrouve un k CONNU sur une scène où le continuum est large et
      la raie compacte et décalée ; le repli quand le champ n'a pas de
      continuum franc ; l'égalité AU BIT avec `bandes_passantes` en repli ;
  [4] `etoiles_5sigma` retrouve le même k par les étoiles ; repli quand il y a
      trop peu d'étoiles ;
  [5] `composer()` remonte l'info (et le repli), `CompositeStacker` aussi (et
      la mémoïsation suit la MÉTHODE et la BANDE) ;
  [6] l'INTERFACE : cases EXCLUSIVES, bande grisée hors bandes passantes, case
      « recentrer » avec son risque, Q au défaut de la méthode, persistance et
      restitution des trois nouvelles clés, repli MONTRÉ sur les cases ;
  [7] la FICHE DE RENDU dit la méthode, la bande et le recentrage.

Exécution : python bancs/_test_fusion_ha_jalon4.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.processing import composition as compo
from avastack.processing.composition import (ALPHA_HA_DEFAUT, BW_HA_NM,
                                             BW_HA_NM_OPTIONS, BW_RGB_NM,
                                             CLIP_HA_MAX, CLIP_HA_MIN,
                                             CompositeStacker,
                                             METHODE_CONTINUUM_DEFAUT,
                                             METHODES_CONTINUUM_HA,
                                             Q_HA_DEFAUT, composer,
                                             fusion_ha_effectif, fusionner_ha,
                                             q_ha_defaut)

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def scene_continuum(k_vrai=0.07, graine=5, forme=(96, 96), etoiles=False):
    """Scène où le CONTINUUM est LARGE et la raie Ha COMPACTE et DÉCALÉE.

    PIÈGE du banc J3bis rappelé ici : une scène où le Ha pointe AU MÊME ENDROIT
    que le maximum de R rendrait la mesure ininterprétable. Ici le continuum est
    une tache large au centre-gauche, la raie une tache serrée en bas à droite.

    → (R, Ha, masque du continuum) en float32. `Ha = 0,10 + k·(R − 0,10) + raie`
    (k = la fraction de continuum à RETROUVER) ; `etoiles` ajoute 8 étoiles
    gaussiennes, présentes dans les DEUX couches avec le même rapport k."""
    rng = np.random.default_rng(graine)
    h, w = forme
    yy, xx = np.mgrid[0:h, 0:w]
    cont = np.exp(-(((yy - h * 0.45) ** 2 + (xx - w * 0.40) ** 2)
                    / (2.0 * (min(h, w) / 5.0) ** 2))).astype(np.float32)
    r = (0.10 + 0.60 * cont
         + rng.normal(0.0, 0.004, (h, w))).astype(np.float32)
    raie = np.exp(-(((yy - h * 0.62) ** 2 + (xx - w * 0.66) ** 2)
                    / (2.0 * (min(h, w) / 22.0) ** 2))).astype(np.float32)
    ha = (0.10 + k_vrai * (r - np.float32(0.10)) + 0.55 * raie
          + rng.normal(0.0, 0.004, (h, w))).astype(np.float32)
    if etoiles:
        for (sx, sy, amp) in ((20, 18, 1.2), (100, 22, 1.0), (30, 52, 0.9),
                              (72, 40, 1.4), (46, 80, 1.1), (104, 74, 0.8),
                              (86, 96, 1.0), (18, 70, 0.7)):
            g = np.exp(-(((yy - sy) ** 2 + (xx - sx) ** 2)
                         / (2.0 * 1.4 ** 2))).astype(np.float32)
            r = r + np.float32(amp) * g
            ha = ha + np.float32(amp * k_vrai) * g
    return r, ha, cont > np.float32(0.02)


def composite(forme=(96, 96), graine=11):
    """Composite (H, W, 3) dans l'espace normalisé (~0,25 au fond)."""
    rng = np.random.default_rng(graine)
    rgb = rng.normal(0.25, 0.02, (*forme, 3)).astype(np.float32)
    rgb[..., 0] += np.float32(0.15)
    return rgb
# ============================================ [1] trois méthodes, bandes, Q
print("[1] trois méthodes, choix de bande (7/3 nm), Q par défaut de chaque méthode")
verifie(METHODES_CONTINUUM_HA == ("bandes_passantes", "mediane",
                                  "etoiles_5sigma"),
        f"trois méthodes (bandes passantes D'ABORD) : {METHODES_CONTINUUM_HA}")
verifie(METHODE_CONTINUUM_DEFAUT == "bandes_passantes",
        "défaut INCHANGÉ : bandes passantes (validé en réel)")
verifie(BW_HA_NM == 7.0 and BW_HA_NM_OPTIONS == (7.0, 3.0) and BW_RGB_NM == 100.0,
        f"bandes : défaut {BW_HA_NM:g} nm, options {BW_HA_NM_OPTIONS}, R 100 nm")
verifie(q_ha_defaut("bandes_passantes") == Q_HA_DEFAUT == 0.80,
        "Q par défaut en bandes passantes : 0,80 (LE réglage)")
verifie(q_ha_defaut("mediane") == 1.00 and q_ha_defaut("etoiles_5sigma") == 1.00,
        "Q par défaut sur une MESURE : 1,00 (ajustement fin)")
d = fusion_ha_effectif("LRGB+Ha", None)
att = {"mode": "ajout_rouge", "poids": 1.0, "alpha": ALPHA_HA_DEFAUT,
       "recentrer": True, "continuum": True, "q": 0.80,
       "methode_continuum": "bandes_passantes", "bw_ha": 7.0}
verifie(d == att, f"défauts complets : {d}")
verifie(fusion_ha_effectif("LRGB+Ha", {"methode_continuum": "mediane"})["q"] == 1.0,
        "méthode mesurée sans Q saisi → Q part à 1,00")
verifie(fusion_ha_effectif("LRGB+Ha", {"q": 0.60, "methode_continuum": "mediane"})["q"] == 0.60,
        "un Q SAISI reste prioritaire (il n'est pas écrasé)")
verifie(fusion_ha_effectif("LRGB+Ha", {"methode_continuum": "inconnue"})
        ["methode_continuum"] == "bandes_passantes",
        "méthode inconnue → défaut (jamais une exception)")
verifie(fusion_ha_effectif("LRGB+Ha", {"bw_ha": 3})["bw_ha"] == 3.0
        and fusion_ha_effectif("LRGB+Ha", {"bw_ha": 5})["bw_ha"] == 7.0
        and fusion_ha_effectif("LRGB+Ha", {"bw_ha": "x"})["bw_ha"] == 7.0,
        "bande : 3 nm acceptée, 5 nm rapprochée de 7 nm, illisible → défaut")
verifie(fusion_ha_effectif("HOO", {"methode_continuum": "mediane"}) is None
        and fusion_ha_effectif("SHO") is None,
        "HOO/SHO : la fusion (et ses méthodes) reste EXCLUE")

# ======================================== [2] bandes passantes : 7 nm AU BIT
print("[2] bandes passantes : 7 nm AU BIT (J2), 3 nm = rapport 3/100")
r, ha, _cont = scene_continuum()
rgb = composite()
ECH = 1.0


def manuel(k, recentrer=True, continuum=True, q=Q_HA_DEFAUT, bw=7.0):
    """Rejeu MANUEL de la formule, avec le k calculé par le module."""
    h = ha.copy()
    r_ = r.copy()
    if recentrer:
        h = h - np.float32(np.median(h))
        r_ = r_ - np.float32(np.median(r_))
    sig = h - (np.float32(k / float(ECH)) * r_)
    sig = np.clip(sig, CLIP_HA_MIN, CLIP_HA_MAX)
    out = rgb.copy()
    out[..., 0] = rgb[..., 0] + np.float32(1.0) * sig
    return out


k7 = Q_HA_DEFAUT * BW_HA_NM / BW_RGB_NM
o7 = fusionner_ha(rgb, ha, mode="ajout_rouge", poids=1.0, recentrer=True,
                  continuum=True, q=Q_HA_DEFAUT, methode_continuum="bandes_passantes",
                  r_reference=r, echelle_ha=ECH, bw_ha=7.0)
verifie(np.array_equal(o7, manuel(np.float32(k7))),
        "bandes passantes 7 nm : R' = R + [Ha − fond − Q·7/100·(R − fond)] AU BIT")
verifie(np.array_equal(o7[..., 1:], rgb[..., 1:]),
        "7 nm : VERT et BLEU au bit")
k3 = Q_HA_DEFAUT * 3.0 / BW_RGB_NM
o3 = fusionner_ha(rgb, ha, mode="ajout_rouge", poids=1.0, recentrer=True,
                  continuum=True, q=Q_HA_DEFAUT, methode_continuum="bandes_passantes",
                  r_reference=r, echelle_ha=ECH, bw_ha=3.0)
verifie(np.array_equal(o3, manuel(np.float32(k3))),
        "3 nm : le rapport suit le filtre choisi (3/100), AU BIT")
verifie(float(np.max(np.abs(o3[..., 0] - o7[..., 0]))) > 1e-3,
        "3 nm et 7 nm ne donnent PAS le même rouge (le choix de bande AGIT)")



# ================================================= [3] méthode « médiane »
print("[3] médiane : le k du CONTINUUM est retrouvé (scène large/compacte)")
K_VRAI = 0.07
info = {}
o_m = fusionner_ha(rgb, ha, mode="ajout_rouge", poids=1.0, recentrer=True,
                   continuum=True, q=1.0, methode_continuum="mediane",
                   r_reference=r, echelle_ha=ECH, bw_ha=7.0, info=info)
verifie(info.get("methode_effective") == "mediane" and not info.get("repli"),
        f"mesure CONCLUANTE : {info.get('methode_effective')} (repli="
        f"{info.get('repli')}, facteur {info.get('facteur')})")
k_mes = float(info.get("facteur") or 0.0)
verifie(abs(k_mes - K_VRAI) <= 0.15 * K_VRAI,
        f"facteur mesuré {k_mes:.4f} contre {K_VRAI:.4f} attendu (±15 %)")
verifie(np.array_equal(o_m, manuel(np.float32(k_mes))),
        "le facteur MESURÉ est appliqué tel quel (formule du J2, au bit)")
verifie(np.array_equal(o_m[..., 1:], rgb[..., 1:]),
        "médiane : VERT et BLEU au bit")
o_bp = fusionner_ha(rgb, ha, mode="ajout_rouge", poids=1.0, recentrer=True,
                    continuum=True, q=k_mes * BW_RGB_NM / BW_HA_NM,
                    methode_continuum="bandes_passantes",
                    r_reference=r, echelle_ha=ECH, bw_ha=7.0)
verifie(float(np.max(np.abs(o_bp[..., 0] - o_m[..., 0]))) < 1e-3,
        "médiane ≡ bandes passantes avec Q équivalent (les deux visent le MÊME k)")

# Champ SANS continuum franc : R n'est que du ciel bruité → mesure impossible.
rng = np.random.default_rng(21)
r_plat = (0.10 + rng.normal(0.0, 0.004, ha.shape)).astype(np.float32)
yy, xx = np.mgrid[0:ha.shape[0], 0:ha.shape[1]]
raie_seule = np.exp(-(((yy - ha.shape[0] * 0.5) ** 2
                       + (xx - ha.shape[1] * 0.5) ** 2)
                      / (2.0 * 6.0 ** 2))).astype(np.float32)
ha_seul = (0.10 + 0.55 * raie_seule
           + rng.normal(0.0, 0.004, ha.shape)).astype(np.float32)
info2 = {}
o_rep = fusionner_ha(rgb, ha_seul, mode="ajout_rouge", poids=1.0, recentrer=True,
                     continuum=True, q=1.0, methode_continuum="mediane",
                     r_reference=r_plat, echelle_ha=ECH, bw_ha=7.0, info=info2)
verifie(info2.get("repli") is True
        and info2.get("methode_effective") == "bandes_passantes"
        and bool(info2.get("raison")),
        f"pas de continuum franc → REPLI DIT : {info2.get('raison')!r}")
o_ref = fusionner_ha(rgb, ha_seul, mode="ajout_rouge", poids=1.0, recentrer=True,
                     continuum=True, q=1.0, methode_continuum="bandes_passantes",
                     r_reference=r_plat, echelle_ha=ECH, bw_ha=7.0)
verifie(np.array_equal(o_rep, o_ref),
        "en repli, la sortie est CELLE des bandes passantes, AU BIT")


# =============================================== [4] méthode « étoiles 5σ »
print("[4] étoiles 5σ : le MÊME k, mesuré sur les étoiles (continuum pur)")
r_st, ha_st, _ = scene_continuum(K_VRAI, graine=7, forme=(128, 128),
                                 etoiles=True)
rgb_st = composite((128, 128))
info3 = {}
o_s = fusionner_ha(rgb_st, ha_st, mode="ajout_rouge", poids=1.0, recentrer=True,
                   continuum=True, q=1.0, methode_continuum="etoiles_5sigma",
                   r_reference=r_st, echelle_ha=ECH, bw_ha=7.0, info=info3)
verifie(info3.get("methode_effective") == "etoiles_5sigma"
        and not info3.get("repli"),
        f"mesure par les ÉTOILES concluante : {info3.get('methode_effective')} "
        f"(facteur {info3.get('facteur')})")
k_etoiles = float(info3.get("facteur") or 0.0)
verifie(abs(k_etoiles - K_VRAI) <= 0.15 * K_VRAI,
        f"facteur mesuré {k_etoiles:.4f} contre {K_VRAI:.4f} attendu (±15 %)")
verifie(np.array_equal(o_s[..., 1:], rgb_st[..., 1:]),
        "étoiles : VERT et BLEU au bit")
verifie(abs(k_etoiles - k_mes) <= 0.20 * max(k_mes, 1e-6),
        f"les DEUX mesures concordent ({k_etoiles:.4f} contre {k_mes:.4f})")

info4 = {}
o_ns = fusionner_ha(rgb, ha_seul, mode="ajout_rouge", poids=1.0, recentrer=True,
                    continuum=True, q=1.0, methode_continuum="etoiles_5sigma",
                    r_reference=r_plat, echelle_ha=ECH, bw_ha=7.0, info=info4)
verifie(info4.get("repli") is True
        and info4.get("methode_effective") == "bandes_passantes",
        f"aucune étoile → REPLI DIT : {info4.get('raison')!r}")

# ========================== [5] composer() et CompositeStacker remontent l'info
print("[5] composer() remonte la méthode et le repli ; la mémoïsation les suit")
rng = np.random.default_rng(31)
# Scène PHYSIQUEMENT COHÉRENTE : le Ha porte le continuum de R (même k) + la
# raie — sinon la mesure est, à juste titre, rejetée pour dispersion.
canaux = {"R": r.copy(),
          "G": (r * 0.80).astype(np.float32),
          "B": (r * 0.60).astype(np.float32),
          "L": (r * 0.95).astype(np.float32)}
canaux["Ha"] = ha.copy()
inf = {}
comp = composer(canaux, "LRGB+Ha", fusion_ha={"mode": "ajout_rouge",
                                              "methode_continuum": "mediane"},
                info_fusion_ha=inf)
verifie(comp is not None and inf.get("methode_effective") == "mediane"
        and not inf.get("repli"),
        f"composer() remplit l'info : {inf.get('methode_effective')} "
        f"(repli={inf.get('repli')}, facteur {inf.get('facteur')})")
verifie(abs(float(inf.get("facteur") or 0.0) - K_VRAI) <= 0.25 * K_VRAI,
        f"le k retrouvé par composer() reste le bon : {inf.get('facteur')}")
inf_hoo = {}
composer({"Ha": ha.copy(), "O3": ha.copy()}, "HOO", info_fusion_ha=inf_hoo)
verifie(inf_hoo.get("methode_effective") is None,
        "HOO : aucune fusion, aucune méthode (l'info reste vide)")


class _FauxStacker:
    """Stacker de rôle minimal : `moyennes()` ne lit que `.n` et `.mean()`."""

    def __init__(self, img):
        self.img = img
        self.n = 5

    def mean(self, recadre: bool = False):
        return self.img


st = CompositeStacker("LRGB+Ha")
st.stackers = {r: _FauxStacker(a) for r, a in canaux.items()}
st.cadre = None
st.fusion_ha = {"mode": "ajout_rouge", "methode_continuum": "mediane", "q": 1.0}
c1 = st.mean()
verifie(isinstance(st.info_fusion_ha, dict)
        and st.info_fusion_ha.get("methode_effective") in ("mediane",
                                                           "bandes_passantes"),
        f"le stacker EXPOSE la méthode appliquée : {st.info_fusion_ha}")
c1b = st.mean()
verifie(c1b is c1 and isinstance(st.info_fusion_ha, dict)
        and st.info_fusion_ha.get("methode_effective") is not None,
        "cache-hit : la même info est rendue (elle ne se vide pas)")
st.fusion_ha = {"mode": "ajout_rouge", "methode_continuum": "bandes_passantes",
                "q": 0.8, "bw_ha": 7.0}
c2 = st.mean()
st.fusion_ha = {"mode": "ajout_rouge", "methode_continuum": "bandes_passantes",
                "q": 0.8, "bw_ha": 3.0}
c3 = st.mean()
verifie(c3 is not c2,
        "BANDE changée (7 → 3 nm) → composite REFAIT (elle est dans la clé)")
st.fusion_ha = {"mode": "ajout_rouge", "methode_continuum": "mediane", "q": 1.0}
c4 = st.mean()
verifie(c4 is not c3,
        "MÉTHODE changée → composite REFAIT (elle est dans la clé)")


# ====================================================== [6] interface (App)
print("[6] interface : cases EXCLUSIVES, bande, recentrage, repli MONTRÉ")
root = tk.Tk()
root.withdraw()
import avastack.ui.app as ui               # noqa: E402
ui.CONFIG = {}                             # jamais toucher à la vraie config
captures: list[dict] = []
ui.sauver_config = lambda d: captures.append(dict(d))
ui.App._avertir = lambda self, titre, message: None   # aucune boîte modale
app = ui.App(root)
app._mode_compo = False
app.var_compo.set("LRGB+Ha")
app._on_compo()
verifie(sorted(app.rb_fusion_ha_methode) == sorted(METHODES_CONTINUUM_HA),
        f"trois CASES, une par méthode : {sorted(app.rb_fusion_ha_methode)}")
vars_cases = {str(rb.cget("variable")) for rb in app.rb_fusion_ha_methode.values()}
verifie(len(vars_cases) == 1,
        f"EXCLUSIVES : une seule variable Tk pour les trois cases ({vars_cases})")
verifie(str(app.var_fusion_ha_methode.get()) == "bandes_passantes",
        "défaut : bandes passantes (réglage validé en réel)")
verifie(bool(app.var_fusion_ha_recentrer.get()) is True
        and "voile rouge" in str(app.chk_fusion_ha_recentrer.cget("text")),
        "case « recentrer » cochée par défaut, RISQUE écrit dessus")
# Sans dossier R : plus rien n'est réglable (aucune méthode ne peut mesurer).
ligne_r = next(i for i in range(compo.NB_LIGNES_COMPO)
               if app.var_compo_roles[i].get() == "R")
app.var_compo_dossiers[ligne_r].set("")
app._maj_fusion_ha()
verifie(all(str(rb.cget("state")) == "disabled"
            for rb in app.rb_fusion_ha_methode.values())
        and str(app.cb_fusion_ha_bw.cget("state")) == "disabled"
        and str(app.chk_fusion_ha_recentrer.cget("state")) == "disabled",
        "aucun dossier R : méthodes, bande et recentrage DÉSACTIVÉS")
app.var_compo_dossiers[ligne_r].set("C:/brutes/R")
app._maj_fusion_ha()
verifie(all(str(rb.cget("state")) == "normal"
            for rb in app.rb_fusion_ha_methode.values())
        and str(app.cb_fusion_ha_bw.cget("state")) == "readonly",
        "dossier R : cases ACTIVES et bande réglable (méthode bandes passantes)")
app.var_fusion_ha_methode.set("mediane")
app._maj_fusion_ha()
verifie(str(app.cb_fusion_ha_bw.cget("state")) == "disabled",
        "méthode mesurée : la BANDE est grisée (elle ne sert qu'à la théorie)")
app.var_fusion_ha_q.set(0.6)
app.var_fusion_ha_methode.set("mediane")
app._on_methode_continuum()
verifie(float(app.var_fusion_ha_q.get()) == 1.0,
        "choix d'une MESURE → Q repart à 1,00 (ajustement fin)")
app.var_fusion_ha_methode.set("bandes_passantes")
app._on_methode_continuum()
verifie(float(app.var_fusion_ha_q.get()) == 0.8,
        "retour aux bandes passantes → Q repart à 0,80 (LE réglage)")
# Bande passante : la liste vient des options du module, et « 3 nm » est lu.
verifie(len(app.cb_fusion_ha_bw.cget("values")) == len(BW_HA_NM_OPTIONS),
        f"liste des bandes lue dans BW_HA_NM_OPTIONS : "
        f"{app.cb_fusion_ha_bw.cget('values')}")
app.var_fusion_ha_bw.set("3 nm")
lue = app._lire_fusion_ha()
verifie(lue["bw_ha"] == 3.0 and lue["methode_continuum"] == "bandes_passantes"
        and lue["recentrer"] is True,
        f"lecture : bande {lue['bw_ha']} nm, méthode {lue['methode_continuum']}")
app.var_fusion_ha_recentrer.set(False)
verifie(app._lire_fusion_ha()["recentrer"] is False,
        "case DÉCOCHÉE → recentrage False (elle AGIT, elle n'est pas décorative)")
app.var_fusion_ha_recentrer.set(True)


# Le repli est MONTRÉ sur les cases (décision d'Alain du 19/10).
class _StInfo:
    info_fusion_ha = {"methode_demandee": "etoiles_5sigma",
                      "methode_effective": "bandes_passantes",
                      "repli": True, "raison": "3 étoiles détectées (< 5)",
                      "facteur": 0.056, "facteur_mesure": ""}


# --- persistance / restitution des trois nouvelles clés ----------------------
app.stacker = CompositeStacker("LRGB+Ha")
app.var_fusion_ha_methode.set("etoiles_5sigma")
app.var_fusion_ha_bw.set("3 nm")
app.var_fusion_ha_recentrer.set(False)
app._on_fusion_ha()
app._sauver_config_app()
c = captures[-1]
verifie(c.get("fusion_ha_methode") == "etoiles_5sigma"
        and float(c.get("fusion_ha_bw", -1)) == 3.0
        and c.get("fusion_ha_recentrer") is False,
        f"persisté : méthode={c.get('fusion_ha_methode')} "
        f"bande={c.get('fusion_ha_bw')} recentrer={c.get('fusion_ha_recentrer')}")
ui.CONFIG = c
app.var_fusion_ha_methode.set("bandes_passantes")   # on casse les valeurs…
app.var_fusion_ha_bw.set("7 nm")
app.var_fusion_ha_recentrer.set(True)
app._restaurer_config()                             # … puis on relit la config
verifie(app.var_fusion_ha_methode.get() == "etoiles_5sigma"
        and float(str(app.var_fusion_ha_bw.get()).split(" ")[0]) == 3.0
        and bool(app.var_fusion_ha_recentrer.get()) is False,
        "config relue : méthode, bande et recentrage RESTAURÉS")

# ======================================================== [7] fiche de rendu
print("[7] fiche de rendu : méthode, bande et recentrage sont dits")
app.var_compo.set("LRGB+Ha")
app._on_compo()
app.var_fusion_ha_mode.set("ajout_rouge")
app.var_fusion_ha_methode.set("etoiles_5sigma")
app.var_fusion_ha_bw.set("3 nm")
app.var_fusion_ha_recentrer.set(False)
app.var_fusion_ha_continuum.set(True)
app._maj_fusion_ha()
app.stacker = CompositeStacker("LRGB+Ha")
app.stacker.stackers = {"Ha": _FauxStacker(canaux["Ha"]),
                        "R": _FauxStacker(canaux["R"])}
app._on_fusion_ha()
reg = app._reglages_rendu()
fus_reg = reg.get("compo_fusion") or {}
verifie(fus_reg.get("methode_continuum") == "etoiles_5sigma"
        and float(fus_reg.get("bw_ha", 0.0)) == 3.0
        and fus_reg.get("recentrer") is False,
        f"réglages capturés : {fus_reg}")
chaine = app._fiche_chaine(reg, "empilement", False)
noms = [e["etape"] for e in chaine]
verifie("fusion Ha" in noms, "la chaîne porte une étape « fusion Ha »")
if "fusion Ha" in noms:
    etape = chaine[noms.index("fusion Ha")]
    verifie(etape.get("methode_continuum") == "etoiles_5sigma"
            and float(etape.get("bw_ha_nm", 0.0)) == 3.0
            and etape.get("recentrer") is False,
            f"l'étape nomme la méthode, la bande et le recentrage : {etape}")

app.stacker = CompositeStacker("HOO")
verifie((app._reglages_rendu().get("compo_fusion")) is None,
        "HOO : aucune méthode de continuum dans les réglages")

root.destroy()
print()
print("VERDICT :", "TOUS LES VOLETS VERTS" if ok else "ÉCHEC")
sys.exit(0 if ok else 1)


app.stacker = _StInfo()
app._refléter_methode_continuum()
txt_note = str(app.lbl_fusion_ha_note.cget("text"))
verifie("REPLI" in txt_note and "3 étoiles" in txt_note,
        f"repli DIT dans la ligne d'état : {txt_note!r}")
verifie("appliquée" in str(app.rb_fusion_ha_methode["bandes_passantes"].cget("text"))
        and "appliquée" not in str(app.rb_fusion_ha_methode["mediane"].cget("text")),
        "la case de la méthode APPLIQUÉE est marquée « ← appliquée »")
