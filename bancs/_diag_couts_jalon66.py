# -*- coding: utf-8 -*-
"""_diag_couts_jalon66.py — COMBIEN COÛTE DE RENDRE L'ÉCRAN FIDÈLE AU FICHIER ?

L'écran applique la chaîne non linéaire à l'APERÇU (~1600 px), le fichier à la
PLEINE RÉSOLUTION (`_save_asseen_thread` → `rendu_pleine_resolution`) : d'où
l'anneau de chroma visible SEULEMENT dans les fichiers (jalon 66). Pour que la
visu montre ce que le fichier contiendra, il faudrait appliquer la MÊME chaîne à
la pleine résolution au moment du rendu écran. Ce banc MESURE ce que cela coûte,
étape par étape, sur l'empilement réel d'Alain (réglages de sa config du
26/09/2026 : GraXpert live, débruitage NLM force 0,25, netteté 1 itération,
SCNR + démagenta, neutralisation du fond, chroma 0,847 / rayon 3 px).

Chaque élément est chronométré sur l'APERÇU (ce que fait l'appli aujourd'hui)
puis sur la PLEINE RÉSOLUTION (ce qu'il faudrait faire) ; le premier appel d'un
étirement sert de rodage (moteur tiers) et n'est pas compté.

Usage : python bancs/_diag_couts_jalon66.py [dossier]
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
import time

RACINE = sys.argv[1] if len(sys.argv) > 1 else r"C:\Astro\test"
sys.argv = [sys.argv[0]]

try:                                     # sortie console : jamais de plantage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import _diag_apercu_fichier_jalon66 as A                  # noqa: E402
from avastack.processing import veralux as _veralux        # noqa: E402
from avastack.processing import couleurs as _couleurs      # noqa: E402
from avastack.processing import denoise as _denoise        # noqa: E402

FORCE_CHROMA = 0.8471
RAYON_REF = 3.0
FORCE_NLM = 0.25


def main():
    lin = _veralux.normaliser_lin(A.lire_fits(
        os.path.join(RACINE, "M31_traite_lineaire_2.37.3.fits")))
    petit, ech = A.reduire(lin)
    print(f"empilement {lin.shape[1]}x{lin.shape[0]}  ->  aperçu "
          f"{petit.shape[1]}x{petit.shape[0]} (×{ech:.4f})")
    print(f"réglages : chroma force {FORCE_CHROMA} / rayon {RAYON_REF:.2f} px "
          f"pleine rés. (aperçu {_couleurs.rayon_chroma_apercu(ech, RAYON_REF):.2f} px) "
          f"· NLM force {FORCE_NLM}")

    # ---------------------------------------------------------------- APERÇU
    print("\n  ÉCRAN — chaîne de l'appli sur l'APERÇU (aujourd'hui) :")
    tot_prep = 0.0
    def _p(nom, fn, cumul=True):
        nonlocal tot_prep
        t0 = time.perf_counter()
        out = fn()
        dt = time.perf_counter() - t0
        print(f"      {nom:42s} {dt:7.3f} s", flush=True)
        if cumul:
            tot_prep += dt
        return out
    a = _p("neutraliser_fond(aperçu)",
           lambda: _couleurs.neutraliser_fond(petit))
    a = _p("reduire_bruit_chroma(aperçu)",
           lambda: _couleurs.reduire_bruit_chroma(
               a, force=FORCE_CHROMA,
               rayon=_couleurs.rayon_chroma_apercu(ech, RAYON_REF)))
    a = _p("scnr(aperçu)", lambda: _couleurs.scnr(a))
    a = _p("demagenta(aperçu)", lambda: _couleurs.demagenta(a))
    a = _p(f"denoiser nlm {FORCE_NLM} (aperçu)",
           lambda: _denoise.denoiser(a, "nlm", FORCE_NLM)[0])
    _veralux.etirer(a, mode=_veralux.MODE_TARGET_BG, target_bg=A.TARGET_BG,
                    profil=A.PROFIL)                    # rodage (non compté)
    apercu_logd = None

    def _etirer_apercu():
        nonlocal apercu_logd
        r, logd, _ = _veralux.etirer(a, mode=_veralux.MODE_TARGET_BG,
                                     target_bg=A.TARGET_BG, profil=A.PROFIL)
        apercu_logd = logd
        return r
    _p("etirer VeraLux (aperçu, fond cible)", _etirer_apercu)
    print(f"      {'— total chaîne d’aperçu':42s} {tot_prep:7.3f} s")
    print(f"      logD résolu sur l'aperçu : {apercu_logd:.4f}")

    # ---------------------------------------------------------- PLEINE RÉSOL.
    print("\n  FICHIER — les mêmes étapes en PLEINE RÉSOLUTION :")
    tot_plein = 0.0
    def _f(nom, fn):
        nonlocal tot_plein
        t0 = time.perf_counter()
        out = fn()
        dt = time.perf_counter() - t0
        print(f"      {nom:42s} {dt:7.3f} s", flush=True)
        tot_plein += dt
        return out
    b = _f("neutraliser_fond(pleine rés.)",
           lambda: _couleurs.neutraliser_fond(lin))
    b = _f("reduire_bruit_chroma(pleine rés.)",
           lambda: _couleurs.reduire_bruit_chroma(
               b, force=FORCE_CHROMA, rayon=RAYON_REF))
    b = _f("scnr(pleine rés.)", lambda: _couleurs.scnr(b))
    b = _f("demagenta(pleine rés.)", lambda: _couleurs.demagenta(b))
    b = _f(f"denoiser nlm {FORCE_NLM} (pleine rés.)",
           lambda: _denoise.denoiser(b, "nlm", FORCE_NLM)[0])
    _veralux.etirer(b, mode=_veralux.MODE_LOG_D, log_d=apercu_logd,
                    profil=A.PROFIL)                     # rodage (non compté)
    _f("etirer VeraLux (pleine rés., logD aperçu)",
       lambda: _veralux.etirer(b, mode=_veralux.MODE_LOG_D, log_d=apercu_logd,
                               profil=A.PROFIL)[0])
    print(f"      {'— total chaîne pleine résolution':42s} {tot_plein:7.3f} s")

    print(f"\n  Coût AJOUTÉ si l'écran passait en pleine résolution : "
          f"{tot_plein:.2f} s au lieu de {tot_prep:.2f} s "
          f"(×{tot_plein / max(tot_prep, 1e-9):.1f})")
    print("  (rappel : le rafraîchissement ne relance QUE ce qui a changé — "
          "les caches GraXpert/débruitage de l'appli ne rejouent pas l'étape "
          "dont l'entrée n'a pas bougé)")


if __name__ == "__main__":
    main()
