# -*- coding: utf-8 -*-
"""Test du jalon 10 — détecteur d'étoiles + seeing live
(`avastack/processing/stars.py`), prérequis de la netteté live
(Richardson-Lucy, à venir).

Vérifie :
  [1] API : entrée mono/couleur jamais modifiée, image constante, image
      dégénérée → JAMAIS d'exception, message explicite ;
  [2] champ synthétique : la FWHM mesurée correspond à la FWHM vraie
      (±15 %) pour deux seeing différents, étoiles bien comptées, coût ;
  [3] rejets : étoile filée (ellipticité), nébulosité trop grosse, objet
      touchant un bord, pixel chaud isolé — aucun ne fausse la mesure ;
  [4] limites : image trop petite, étoiles insuffisantes → mesure renvoyée
      MAIS message (« pas de no-op silencieux ») ;
  [5] UI (fenêtre réelle) : `lbl_seeing` affiche la mesure, signale « (peu
      fiable) », et dit la RAISON quand aucune mesure n'est possible.

Nécessite un affichage (section [5]). Exécution :
python _test_stars_jalon10.py
"""
import sys
import time
import tkinter as tk

import numpy as np

from avastack.processing import stars as st_mod
import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def champ(shape, sigma_px, nb=40, bruit=0.004, fond=0.002,
          amp=(0.05, 0.6), graine=1, marge=25):
    """Champ synthétique : nb étoiles gaussiennes de σ connu + bruit."""
    rng = np.random.default_rng(graine)
    h, w = shape
    img = np.full((h, w), fond, dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    for _ in range(nb):
        y = int(rng.integers(marge, h - marge))
        x = int(rng.integers(marge, w - marge))
        a = float(rng.uniform(*amp))
        img += (a * np.exp(-((yy - y) ** 2 + (xx - x) ** 2)
                           / (2.0 * sigma_px ** 2))).astype(np.float32)
    img += rng.normal(0.0, bruit, img.shape).astype(np.float32)
    return img


print("[1] API : types, cas dégénérés, non-mutation")
h_plat = np.full((300, 400), 0.01, dtype=np.float32)
mes, err = st_mod.mesurer_seeing(h_plat)
verifie(err != "" and mes.get("nb") == 0,
        f"image constante → message explicite (« {err} ») et 0 étoile")
mes, err = st_mod.mesurer_seeing(np.zeros((10, 10), dtype=np.float32))
verifie(err != "" and "petite" in err, f"image trop petite → « {err} »")
mes, err = st_mod.mesurer_seeing(np.zeros(50, dtype=np.float32))
verifie(mes == {} and err != "", f"tableau 1D → message, pas d'exception "
                                 f"(« {err} »)")
img = champ((300, 400), 1.2, nb=12)
ref = img.copy()
rgb = np.stack([img, img * 0.9, img * 0.6], axis=-1)
mes_c, err_c = st_mod.mesurer_seeing(rgb)
mes_m, err_m = st_mod.mesurer_seeing(img)
verifie(err_c == "" and err_m == "" and mes_c["nb"] == mes_m["nb"],
        f"couleur (H,W,3) et mono (H,W) : même détection "
        f"({mes_c['nb']} étoiles, FWHM {mes_c['fwhm']:.2f} px)")
verifie(np.array_equal(img, ref), "image d'entrée jamais modifiée")
verifie(abs(st_mod.sigma_depuis_fwhm(2.354820045) - 1.0) < 1e-6,
        "conversion FWHM ↔ σ cohérente (2√(2 ln 2))")

print("[2] Champ synthétique : FWHM mesurée ≈ FWHM vraie")
for sigma_px in (1.2, 1.8):
    img = champ((600, 800), sigma_px, nb=40)
    t0 = time.perf_counter()
    mes, err = st_mod.mesurer_seeing(img)
    dt = time.perf_counter() - t0
    vraie = st_mod.fwhm_depuis_sigma(sigma_px)
    ecart = abs(mes["fwhm"] - vraie) / vraie
    verifie(err == "" and mes["nb"] >= 30,
            f"σ {sigma_px} px : {mes['nb']}/40 étoiles exploitables "
            f"(message « {err} »)")
    verifie(ecart < 0.15,
            f"σ {sigma_px} px : FWHM mesurée {mes['fwhm']:.2f} px vs vraie "
            f"{vraie:.2f} px (écart {100 * ecart:.1f} % < 15 %)")
    print(f"        (coût de la mesure : {1000 * dt:.1f} ms sur "
          f"800×600, {mes['objets']} objets au-dessus du seuil)")


print("[3] Rejets : objets qui ne sont PAS des étoiles")
yy, xx = np.mgrid[0:400, 0:600]


def etoile(img, cy, cx, amp=0.4, sy=1.2, sx=1.2):
    img += (amp * np.exp(-((yy - cy) ** 2 / (2.0 * sy ** 2)
                           + (xx - cx) ** 2 / (2.0 * sx ** 2)))
            ).astype(np.float32)


def fond_plat():
    rng = np.random.default_rng(7)
    return (np.full((400, 600), 0.002, dtype=np.float32)
            + rng.normal(0.0, 0.004, (400, 600)).astype(np.float32))


vraie = st_mod.fwhm_depuis_sigma(1.2)
seule = fond_plat()
etoile(seule, 200, 300)
mes, err = st_mod.mesurer_seeing(seule)
verifie(mes.get("nb") == 1 and abs(mes["fwhm"] - vraie) / vraie < 0.15,
        f"témoin : 1 étoile ronde bien mesurée ({mes['fwhm']:.2f} px vs "
        f"{vraie:.2f} px)")

# (a) étoile FILÉE (σx ≠ σy) : doit être écartée par l'ellipticité.
fil = fond_plat()
etoile(fil, 200, 300)
etoile(fil, 120, 150, amp=0.5, sy=0.9, sx=2.5)
mes, err = st_mod.mesurer_seeing(fil)
verifie(mes.get("nb") == 1,
        f"étoile filée écartée (ellipticité) : {mes.get('nb')} étoile retenue")

# (b) NÉBULOSITÉ (objet bien trop gros pour une étoile) : écartée.
neb = fond_plat()
etoile(neb, 200, 300)
etoile(neb, 130, 420, amp=0.5, sy=12.0, sx=12.0)
mes, err = st_mod.mesurer_seeing(neb)
verifie(mes.get("nb") == 1,
        f"nébulosité (σ 12 px) écartée : {mes.get('nb')} étoile retenue")

# (c) étoile COUPÉE PAR LE BORD : mesure incomplète → écartée.
bord = fond_plat()
etoile(bord, 200, 300)
etoile(bord, 300, 1, amp=0.5)
mes, err = st_mod.mesurer_seeing(bord)
verifie(mes.get("nb") == 1,
        f"étoile au bord écartée : {mes.get('nb')} étoile retenue")

# (d) PIXEL CHAUD isolé : écarté (aire < 2 px au-dessus du seuil).
chaud = fond_plat()
etoile(chaud, 200, 300)
chaud[40, 40] += 2.0
mes, err = st_mod.mesurer_seeing(chaud)
verifie(mes.get("nb") == 1,
        f"pixel chaud isolé écarté : {mes.get('nb')} étoile retenue")

# (e) TOUT ENSEMBLE : la mesure reste celle de la seule vraie étoile.
melange = fond_plat()
etoile(melange, 200, 300)
etoile(melange, 120, 150, amp=0.5, sy=0.9, sx=2.5)     # filée
etoile(melange, 130, 420, amp=0.5, sy=12.0, sx=12.0)   # nébulosité
etoile(melange, 300, 1, amp=0.5)                       # au bord
melange[40, 40] += 2.0                                 # pixel chaud
mes, err = st_mod.mesurer_seeing(melange)
verifie(mes.get("nb") == 1 and abs(mes["fwhm"] - vraie) / vraie < 0.15,
        f"champ pollué : seule la vraie étoile est mesurée "
        f"({mes['fwhm']:.2f} px, {mes.get('objets')} objets au seuil)")

print("[4] Limites : étoiles insuffisantes → mesure + raison (« pas de "
      "no-op silencieux »)")
deux = fond_plat()
etoile(deux, 200, 300)
etoile(deux, 260, 400, amp=0.3)
mes, err = st_mod.mesurer_seeing(deux)
verifie(mes.get("nb") == 2 and "peu fiable" in err,
        f"2 étoiles (< {st_mod.MIN_ETOILES}) : mesure renvoyée quand même "
        f"(FWHM {mes.get('fwhm', 0):.2f} px) + message « {err} »")
peu = fond_plat()
mes, err = st_mod.mesurer_seeing(peu)
verifie(mes.get("nb") == 0 and "indisponible" in err,
        f"champ sans étoile : message « {err} »")
mes, err = st_mod.mesurer_seeing(champ((400, 600), 1.2, nb=8),
                                 seuil_sigma=4.0)
verifie(err == "" and mes["nb"] >= 6,
        f"seuil plus permissif (4σ) : {mes['nb']}/8 étoiles "
        f"({mes.get('objets')} objets, bruit {mes.get('bruit', 0):.5f})")

print("[5] UI (fenêtre réelle) : affichage du seeing")
ui.CONFIG = {}                    # JAMAIS le vrai config.json du poste
ui.sauver_config = lambda d: None
root = tk.Tk()
app = ui.App(root)
root.update_idletasks()
verifie(app.seeing is None and app.lbl_seeing.cget("text").endswith("—"),
        f"état initial : « {app.lbl_seeing.cget('text')} »")


def statut(seeing=None, msg=""):
    """Passe un état de worker à l'UI et relit l'étiquette du seeing."""
    app._update_status(dict(frames=12, rejets=3, bad=0, fps=3.2,
                            cam="Simulée", file="", pending=0, failed=0,
                            seeing=seeing, seeing_msg=msg))
    return app.lbl_seeing.cget("text")


txt = statut({"nb": 42, "fwhm": 2.4134})
verifie("2.41" in txt and "42" in txt and "peu fiable" not in txt,
        f"mesure affichée : « {txt} »")
txt = statut({"nb": 2, "fwhm": 3.10})
verifie("3.10" in txt and "peu fiable" in txt,
        f"mesure douteuse signalée : « {txt} »")
txt = statut({}, "pas assez d'étoiles détectées (0 exploitable) : "
                 "seeing indisponible")
verifie("pas assez d'étoiles" in txt,
        f"aucune mesure : la RAISON est affichée : « {txt} »")
txt = statut(None, "")
verifie(txt.endswith("—"), f"retour à l'état neutre : « {txt} »")
verifie(ui.seeing_live is st_mod and app.seeing_periode > 0,
        "l'UI interroge bien ce module, périodiquement "
        f"(toutes les {app.seeing_periode:g} s)")
root.destroy()

print()
print("JALON 10 : " + ("TOUS LES TESTS PASSENT" if ok
                       else "ÉCHECS — à corriger"))
sys.exit(0 if ok else 1)
