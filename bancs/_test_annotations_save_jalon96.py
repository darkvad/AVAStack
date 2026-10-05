# -*- coding: utf-8 -*-
"""Banc jalon 96 (étapes 5-6) — ANNOTATION : BRANCHEMENT INTERFACE + PNG.

Vérifie le branchement tel que demandé par Alain : l'annotation est dessinée
sur l'image AFFICHÉE (objets célèbres + étoiles brillantes, deux cases
indépendantes), le FITS n'est JAMAIS annoté (linéarité photométrique
préservée), et un PNG compagnon `<nom>_annote.png` est écrit à côté du FITS
à la sauvegarde.

  [1] `_forme_pleine` : forme PLEINE RÉSOLUTION déduite du cadre d'intersection
      (jamais devinée) ;
  [2] `_annoter_image` : cases décochées = objet identique ; cases cochées +
      WCS résolu = COPIE annotée ; `_last_disp` reste AU BIT (le PNG compagnon
      et le zoom repartent de la version propre) ;
  [3] `_sauver_png_annote` : PNG écrit à côté du FITS, jamais DANS le FITS,
      rien d'écrit quand la case « PNG annoté » est décochée ni quand
      l'astrométrie n'est pas résolue ;
  [4] config aller-retour : les 4 clés (`annoter_objets`, `annoter_etoiles`,
      `annoter_sauvegarde`, `seuil_mag_etoiles`) survivent à la session,
      seuil borné (jamais de valeur aberrante) ;
  [5] coût : l'annotation est négligeable devant l'étirement.

Exécution : python bancs/_test_annotations_save_jalon96.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys
import tempfile
import time
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.ui.app as ui
from avastack.catalogues import WcsTan
from avastack.images import save_image
from avastack.processing import annotations as ann

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --- fixture : WCS TAN résolu (grille complète, 1,00″/px) -------------------
RA0, DEC0 = 10.6833, 41.2686
CADRE = (20, 10, 320, 370)             # (y0, x0, y1, x1) du recadrage
H_P, W_P = CADRE[2] - CADRE[0], CADRE[3] - CADRE[1]   # 300 × 360
ECHELLE = 1.0 / 3600.0
WCS_PLEIN = WcsTan((RA0, DEC0),
                   (W_P / 2.0 + CADRE[1], H_P / 2.0 + CADRE[0]),
                   [[-ECHELLE, 0.0], [0.0, ECHELLE]], forme=(H_P, W_P))

ui.CONFIG = {}                         # bac à sable config (cf. banc jalon 56)
ui.sauver_config = lambda *a, **k: None

# Catalogues STUBBÉS (aucun disque requis) — même convention que les bancs
# jalon 56/84 (filedialog/messagebox). Restaurés à la fin.
_ORTHES = {}


class SuiviBanc:
    """Suivi d'astrométrie factice : WCS résolu injecté (aucun catalogue)."""

    def __init__(self, wcs, ra, dec, champ):
        self.wcs = wcs
        self.ra0, self.dec0, self.champ = ra, dec, champ

    @property
    def resolu(self):
        return self.wcs is not None

    def wcs_grille(self, cadre=None, forme=None):
        if self.wcs is None:
            return None, "astrométrie non résolue"
        # même convention que SuiviAstrometrie.wcs_grille : le cadre décale
        # l'origine de (x0, y0) — pixel recadré p → complet p + (x0, y0),
        # donc crpix recadré = crpix complet − (x0, y0). Le banc le couvre
        # avec un cadre NON nul (la translation est exercée).
        if cadre:
            y0, x0, y1, x1 = (int(v) for v in cadre)
            return WcsTan(self.wcs.crval,
                          self.wcs.crpix - np.array([x0, y0], np.float64),
                          self.wcs.cd, forme=(y1 - y0, x1 - x0)), ""
        return self.wcs, ""


class StackerBanc:
    """Empilement factice : cadre d'intersection + n, rien d'autre."""
    cadre = CADRE
    n = 5


tmpw = tempfile.mkdtemp(prefix="avastack_annote_jalon96_")
root = tk.Tk()
root.withdraw()
app = ui.App(root)
app.camera = None
app.stacker = StackerBanc()
app.suivi_astro = SuiviBanc(WCS_PLEIN, RA0, DEC0, 0.5)
# aperçu 1600×904 → facteur 0,5 d'une grille 300×360 : les positions du WCS
# sont multipliées par 0,5 (même règle que `_echelle_apercu` du worker).

# Catalogues STUBBÉS (aucun disque requis) : mêmes signatures que les vrais.
_SAUVE_CEL = ui.cat_mod.celebres.cherche_celebres
_SAUVE_ETO = ui.photo_mod.etoiles_catalogue
ui.cat_mod.celebres.cherche_celebres = (
    lambda ra, dec, rayon, dossier=None: [ObjetCelebreBanc()])
ui.photo_mod.etoiles_catalogue = (
    lambda wcs, forme, dossier=None, limmag=None, spectres=False:
    ({"ra": np.array([RA0]), "dec": np.array([DEC0]), "g": np.array([6.0])},
     "banc"))


class ObjetCelebreBanc:
    designation = "M31"
    aliases = ["NGC224"]
    type_obj = "galaxie"
    mag_v = 3.4
    size_arcmin = 190.0
    ra_deg = RA0
    dec_deg = DEC0
    healpix8 = 0


print("[1] _forme_pleine : forme PLEINE RÉSOLUTION depuis le cadre")
verifie(app._forme_pleine() == (H_P, W_P),
        f"cadre {CADRE} → forme {app._forme_pleine()} (attendu "
        f"{(H_P, W_P)})")

print("[2] _annoter_image : COPIE annotée, `_last_disp` reste au bit")
app.var_annoter_objets.set(False)
app.var_annoter_etoiles.set(False)
disp = (np.random.default_rng(3).integers(0, 60, (150, 180, 3))
        .astype(np.uint8))
app._last_disp = disp.copy()
sortie = app._annoter_image(disp)
verifie(sortie is disp, "cases décochées : objet identique (rien dessiné)")
app.var_annoter_objets.set(True)
app._annote_cache = None
sortie = app._annoter_image(disp)
verifie(sortie is not None and sortie is not disp
        and not np.array_equal(sortie, disp),
        "cases cochées + WCS résolu : COPIE annotée (pixels ajoutés)")
verifie(np.array_equal(disp, app._last_disp),
        "`_last_disp` reste AU BIT (pas d'annotation dans le buffer source)")
app.var_annoter_objets.set(False)
app._annote_cache = None

print("[3] _sauver_png_annote : PNG compagnon à côté du FITS, jamais dedans")
chemin_fits = os.path.join(tmpw, "empilement.fits")
save_image(chemin_fits, np.full((H_P, W_P, 3), 0.1, np.float32))
octets_fits = os.path.getsize(chemin_fits)
app.var_annoter_sauvegarde.set(True)
app.var_annoter_objets.set(True)
app.var_annoter_etoiles.set(False)
app._last_disp = disp.copy()
app._annote_cache = None
png, msg = app._sauver_png_annote(chemin_fits)
verifie(bool(png) and os.path.isfile(png)
        and png == os.path.splitext(chemin_fits)[0] + "_annote.png",
        f"PNG compagnon écrit : {os.path.basename(png or '—')}")
verifie(os.path.getsize(chemin_fits) == octets_fits,
        "le FITS linéaire est INTACT (annotations JAMAIS écrites dedans)")
app.var_annoter_sauvegarde.set(False)
png2, msg2 = app._sauver_png_annote(chemin_fits)
verifie(png2 is None and not os.path.exists(
            os.path.splitext(chemin_fits)[0] + "_annote2.png"),
        "case « PNG annoté » décochée : rien d'écrit")
app.var_annoter_sauvegarde.set(True)
app.suivi_astro = SuiviBanc(None, RA0, DEC0, 0.5)
png3, msg3 = app._sauver_png_annote(chemin_fits)
verifie(png3 is None, "astrométrie non résolue : rien d'annoté ni d'écrit")
app.suivi_astro = SuiviBanc(WCS_PLEIN, RA0, DEC0, 0.5)
app._annote_cache = None

print("[4] config aller-retour : les 4 clés survivent, seuil borné")
app.var_annoter_objets.set(True)
app.var_annoter_etoiles.set(True)
app.var_annoter_sauvegarde.set(False)
app.var_seuil_mag_etoiles.set("9,5")
app._on_annoter()
verifie(ui.CONFIG.get("annoter_objets") is True
        and ui.CONFIG.get("annoter_etoiles") is True
        and ui.CONFIG.get("annoter_sauvegarde") is False
        and abs(float(ui.CONFIG.get("seuil_mag_etoiles")) - 9.5) < 1e-9,
        f"4 clés écrites (objets/étoiles/PNG/seuil "
        f"{ui.CONFIG.get('seuil_mag_etoiles')})")
app.var_seuil_mag_etoiles.set("40")
verifie(abs(app._seuil_mag() - 20.0) < 1e-9,
        "seuil hors bornes → PLAFONNÉ à 20 (jamais de valeur aberrante)")

print("[5] coût : négligeable devant l'étirement")
grande = (np.random.default_rng(5).integers(0, 60, (904, 1600, 3))
          .astype(np.uint8))
app.var_annoter_objets.set(True)
app._last_disp = grande
app._annote_cache = None
t0 = time.perf_counter()
app._annoter_image(grande)
t1 = time.perf_counter()
verifie(t1 - t0 < 0.2,
        f"aperçu 1600×904 : {(t1 - t0) * 1000:.1f} ms (étirement VeraLux "
        "~0,4 s mesuré : cet étage est invisible)")

# restauration des stubs
ui.cat_mod.celebres.cherche_celebres = _SAUVE_CEL
ui.photo_mod.etoiles_catalogue = _SAUVE_ETO

print()
print("BANC TERMINÉ : " + ("TOUT AU VERT" if ok else "ÉCHEC — corriger avant de continuer"))
try:
    root.destroy()
except Exception:
    pass
sys.exit(0 if ok else 1)

