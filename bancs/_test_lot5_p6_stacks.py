# -*- coding: utf-8 -*-
"""P6 (lot 5) — source « Stacks (fichiers FITS) » : banc de non-régression.

Vérifie, sur des fichiers RÉELS (les 5 couches `canal_*.fit` de la référence
M33 quand elles sont présentes) et sur des FITS synthétiques temporaires :

  [1] `StackFilesCamera` : fichiers choisis (pas un dossier), rôle INDIQUÉ,
      `read()` UNE fois par fichier → `(image, rôle)` à plusieurs, image SEULE
      à un seul ; `pending` ; `relire()` ; aucune pose unitaire ; refus d'un
      fichier ABSENT ;
  [2] LINÉARITÉ : refus SEULEMENT si notre en-tête (`AVAVUE`) dit « ETIRE »
      (« ETIREMENT » dans un en-tête linéaire ne doit PAS déclencher le
      refus) ; fichier sans en-tête AVAStack ACCEPTÉ + avertissement MESURÉ ;
  [3] composition : les 5 rôles M33 donnent LRGB+Ha ; un seul fichier ne
      compose rien (« Mono ») ; rôles inconnus → composition None ;
  [4] worker RÉEL : les deux fichiers sont empilés par rôle, lus une fois,
      CALIBRATION IGNORÉE (un dark énorme ne change rien), seuil de profondeur
      = 1, message « empilement fourni (profondeur non vérifiée) », fin de
      source armée, `relire()` + seuil de cadence au démarrage suivant ;
  [5] interface : panneau à 5 lignes, visibilité par source, ligne d'aide
      (composition déduite + FILTER contradictoire), validation des lignes,
      persistance `stacks_role_i` / `stacks_fichier_i` ;
  [6] PISTE A (v2.96.1) : avec 5 FICHIERS, la composition AFFICHÉE est déduite
      des fichiers, la composition est VISIBLE (donc les réglages du composite
      et le cadre « Fusion Ha »), le continuum est ACTIF (couche R fournie),
      les lignes DOSSIER sont verrouillées, et tout est rendu au retour d'une
      source à dossiers.

Exécution : .\\venv\\Scripts\\python.exe bancs\\_test_lot5_p6_stacks.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import os
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
from avastack.cameras import SOURCES, StackFilesCamera
from avastack.cameras import stacks as stacks_mod
from avastack.processing.composition import composition_pour_roles
from avastack.processing.framestore import ArchiveFrames
from avastack.images import save_image

if hasattr(sys.stdout, "reconfigure"):        # sortie pipée ≠ console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CFA_MODE_AVANT = images.CFA_MODE
images.CFA_MODE = "Non"                       # fichiers mono dans ce banc

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


H, W = 200, 260
_ETOILES = None


def champ(dx=0.0, dy=0.0, fond=0.05, graine=0):
    """Champ d'étoiles synthétique (fond bruité + étoiles gaussiennes) —
    même motif que le banc du jalon 19 : sans bruit, la détection d'étoiles
    renvoie « image constante » et l'alignement n'a rien à apparier."""
    global _ETOILES
    rng = np.random.default_rng(7)
    if _ETOILES is None:
        _ETOILES = [(rng.uniform(15, W - 15), rng.uniform(15, H - 15),
                     rng.uniform(0.4, 0.9)) for _ in range(30)]
    img = np.full((H, W), fond, np.float32)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    for (sx, sy, f) in _ETOILES:
        img += f * np.exp(-((x - (sx + dx)) ** 2 + (y - (sy + dy)) ** 2)
                          / (2.0 * 1.2 ** 2)).astype(np.float32)
    img += np.random.default_rng(100 + graine).normal(
        0, 0.004, img.shape).astype(np.float32)
    return img


racine = tempfile.mkdtemp(prefix="avastack_p6_")
f_ha = os.path.join(racine, "mon_empilement_ha.fit")
f_o3 = os.path.join(racine, "stack_o3.fits")
save_image(f_ha, champ(0.0, 0.0, fond=0.05, graine=1),
           entete={"FILTER": "Ha"})
save_image(f_o3, champ(3.0, 2.0, fond=0.07, graine=2),
           entete={"FILTER": "O3"})
M33 = os.path.join("C:\\Astro\\test", "M33_Canaux_LRGBHa")

# ====================================================== [1] la caméra seule
print("[1] StackFilesCamera : fichiers choisis, rôle indiqué, lecture UNE fois")
cam = StackFilesCamera([("Ha", f_ha), ("O3", f_o3)])
verifie(cam.par_roles and cam.roles == ["Ha", "O3"] and cam.pending == 2
        and cam.name == "Stacks : Ha + O3",
        f"caméra : rôles {cam.roles}, {cam.pending} fichiers en attente")
cam.open()
r1 = cam.read()
verifie(isinstance(r1, tuple) and r1[1] == "Ha" and r1[0].shape == (H, W),
        "read() → (image, rôle) : 1er fichier = rôle Ha")
verifie(cam.pending == 1 and cam.count == 1,
        f"après lecture : pending={cam.pending}, count={cam.count}")
r2 = cam.read()
verifie(isinstance(r2, tuple) and r2[1] == "O3" and cam.pending == 0,
        "2e fichier : rôle O3, plus rien en attente")
verifie(cam.read() is None and cam.count == 2,
        "3e lecture → None (chaque fichier est lu UNE seule fois)")
verifie(cam.exposure_time_sec is None and cam.last_file == cam.fichiers[1],
        "aucune pose unitaire inventée (exposure_time_sec = None)")
cam.relire()
verifie(cam.pending == 2 and cam.count == 0,
        "relire() : curseur au début, compteurs remis à zéro (nouvelle session)")
cam.close()


# ============================================================ [2] linéarité
print("[2] Linéarité : refus sur PREUVE, avertissement sur MESURE")
f_etire = os.path.join(racine, "stack_etire.fits")
save_image(f_etire, champ(),
           entete={"AVAVUE": "resultat traite externe, tel que vu (ETIRE)"})
leve = False
try:
    StackFilesCamera([("Ha", f_etire)]).open()
except RuntimeError as e:
    leve = "ÉTIRÉ" in str(e) or "ETIRE" in str(e)
verifie(leve, "en-tête AVAStack « ETIRE » → refus au démarrage (avec remède)")

f_lineaire = os.path.join(racine, "stack_lineaire.fits")
save_image(f_lineaire, champ(),
           entete={"AVAVUE": "resultat du traitement externe (LINEAIRE, "
                             "avant etirement)"})
cam_l = StackFilesCamera([("Ha", f_lineaire)])
cam_l.open()
verifie(cam_l.read() is not None,
        "« avant ETIREMENT » (mot) n'est PAS confondu avec « ETIRE » → accepté")
cam_l.close()

# Fichier d'ailleurs : AUCUN en-tête AVAStack, mais un fond haut + écrêtage
# massif → accepté quand même, avec un avertissement MESURÉ.
f_tiers = os.path.join(racine, "tiers_etire.fits")
etire = np.clip(champ() * 3.0 + 0.35, 0.0, 1.0).astype(np.float32)
save_image(f_tiers, etire)
cam_t = StackFilesCamera([("L", f_tiers), ("R", f_tiers)])
cam_t.open()
img_t = cam_t.read()[0]
verifie(img_t is not None and cam_t.avertissements
        and "probablement DÉJÀ ÉTIRÉ" in cam_t.avertissements[0],
        "fichier tiers étiré : ACCEPTÉ + avertissement mesuré "
        f"(fond {float(np.median(img_t)):.3f})")
cam_t.close()

sain = os.path.join(racine, "tiers_lineaire.fits")
save_image(sain, champ())
cam_s = StackFilesCamera([("L", sain), ("R", sain)])
cam_s.open()
cam_s.read()
verifie(not cam_s.avertissements,
        "fichier tiers LINÉAIRE (fond bas, pas d'écrêtage) : aucun avertissement")
cam_s.close()

# ========================================================= [3] composition
print("[3] Composition déduite des RÔLES (jamais du nom de fichier)")
verifie(composition_pour_roles(("Ha", "O3")) == "HOO"
        and composition_pour_roles(("L", "R", "G", "B", "Ha")) == "LRGB+Ha",
        "composition_pour_roles : HOO et LRGB+Ha (rappel)")
cinq = [("L", f_ha), ("R", f_ha), ("G", f_o3), ("B", f_o3), ("Ha", f_o3)]
cam5 = StackFilesCamera(cinq)
verifie(composition_pour_roles(cam5.roles) == "LRGB+Ha"
        and cam5.par_roles and cam5.name == "Stacks : L + R + G + B + Ha",
        "5 rôles indiqués → LRGB+Ha (le nom des fichiers n'est PAS consulté)")
cam5.close()

if os.path.isdir(M33):
    fichiers = [os.path.join(M33, f"canal_{r}.fit")
                for r in ("L", "R", "G", "B", "Ha")]
    cam_m33 = StackFilesCamera([(r, f) for r, f in
                                zip(("L", "R", "G", "B", "Ha"), fichiers)])
    cam_m33.open()             # en-têtes seuls : aucune image chargée
    verifie(composition_pour_roles(cam_m33.roles) == "LRGB+Ha"
            and cam_m33.pending == 5,
            "référence M33 : LRGB+Ha déduite des rôles, 5 fichiers en attente")
    verifie(not stacks_mod.dit_etire(
                stacks_mod.entete_avastack(fichiers[0])),
            "référence M33 : AVACOMPO/AVALAYER présents, aucun AVAVUE → "
            "linéaire (accepté sans avertissement)")
    cam_m33.close()
else:
    print("  (référence M33 absente — volet ignoré)")

cam1 = StackFilesCamera([("L", f_ha)])
cam1.open()
seul = cam1.read()
verifie(not cam1.par_roles and not isinstance(seul, tuple)
        and seul.shape == (H, W),
        "UN seul fichier : read() rend l'image SEULE (empilement direct, Mono)")
cam1.close()


# ============================================== [4] worker réel (2 fichiers)
print("[4] worker réel : empilement par rôle, calibration IGNORÉE, seuil = 1")


class ArchiveRapide(ArchiveFrames):
    """Archive sans limite de débit (test)."""

    def __init__(self, *a, **k):
        k.setdefault("intervalle_s", 0.0)
        super().__init__(*a, **k)


ui.ArchiveFrames = ArchiveRapide
ui.CONFIG = {}                       # config HERMÉTIQUE (jamais celle d'Alain)
capture = {}
ui.sauver_config = lambda c: capture.update(c)     # aucune écriture disque

root = tk.Tk()
root.withdraw()
app = ui.App(root)
app.rejeter_flou = False             # déterminisme (pas de filtre de flou)
app.ref_refresh = 0                  # pas de rafraîchissement de référence
# Aucune mesure réelle dans ce banc (pas de catalogue, pas de Gaia).
app._astro_actif = app._photo_actif = app._spcc_actif = False
app._photo_gains_actif = False


class _Val:
    """Bouchon de variable Tk (le worker lit var_wb hors thread principal)."""

    def __init__(self, v):
        self.v = v

    def get(self):
        return self.v


app.var_wb = _Val(False)
app.var_wb_force = _Val(1.0)

cam = StackFilesCamera([("Ha", f_ha), ("O3", f_o3)])
cam.open()
app.camera = cam
verifie(app._source_stacks() and app._source_fichiers()
        and not app._cadence_dossier(),
        "source « Stacks » : source de FICHIERS, PAS de cadence dossier")
verifie(app._seuil_profondeur() == 1,
        "seuil de profondeur = 1 (sinon ASTRO_MIN_FRAMES = 3 bloquerait)")
verifie(app._mode_compo_de(cam) and app._mode_compo_de(cam1) is False,
        "mode composition : vrai à 2 fichiers, faux à 1 seul (Mono)")
app._mode_compo = app._mode_compo_de(cam)
app._compo_nom = composition_pour_roles(cam.roles)
verifie(app._compo_nom == "HOO", f"composition déduite : {app._compo_nom}")
verifie(app._detail_profondeur(1, 2)
        == "empilement fourni (profondeur non vérifiée)",
        "message de mesure : « empilement fourni (profondeur non vérifiée) » "
        "(aucun « N frames » inventé)")
verifie("472" not in app._detail_profondeur(472, 472),
        "AVAFRAME n'est jamais repris dans les messages (aucune profondeur)")

# Calibration : un dark ÉNORME (2,0) ramènerait tout à zéro s'il était
# appliqué — c'est le discriminant « calibration ignorée ».
app.calib.dark = np.full((H, W), 2.0, np.float32)

app.running = True
app.empilement_on = True
th = threading.Thread(target=app._worker, daemon=True)
th.start()

t0 = time.time()
while time.time() - t0 < 60:
    if app.stacker is not None and app.stacker.n >= 2:
        break
    time.sleep(0.1)
time.sleep(0.6)                      # la fin de source est servie au tour suivant

verifie(app.stacker is not None
        and type(app.stacker).__name__ == "CompositeStacker",
        "worker : façade CompositeStacker posée (composition HOO)")
verifie(app.stacker is not None and app.stacker.n == 2
        and app.stacker.stackers["Ha"].n == 1
        and app.stacker.stackers["O3"].n == 1,
        "worker : UNE frame par rôle (chaque fichier lu une seule fois)")
couche = app.stacker.moyennes()["Ha"] if app.stacker is not None else None
verifie(couche is not None and float(np.max(couche)) > 0.5,
        f"worker : calibration IGNORÉE (dark 2,0 non soustrait, max "
        f"{float(np.max(couche)) if couche is not None else '?' } > 0,5)")
verifie(cam.count == 2 and cam.pending == 0 and app._source_epuisee,
        "worker : source ÉPUISÉE (2 fichiers lus, 0 en attente) — la fin de "
        "source est bien détectée")

# Démarrage suivant : `relire()` + seuil de cadence à 1.
app.running = False
th.join(timeout=5)
app.empilement_start_request = True
app._worker_reinitialiser()
verifie(cam.pending == 2 and cam.count == 0,
        "« ▶ Démarrer » suivant : relire() → les fichiers seront relus "
        "(sinon l'empilement repartait VIDE)")
verifie(all(getattr(app, n).seuil == 1 for n in
            ("_cadence_astro", "_cadence_photo", "_cadence_spcc")),
        "cadences de re-mesure : seuil posé à 1 pour cette source")

leve = False
try:
    StackFilesCamera([("Ha", os.path.join(racine, "absent.fit"))]).open()
except RuntimeError as e:
    leve = "introuvable" in str(e)

# ======================================================= [5] interface (UI)
print("[5] Interface : panneau, visibilité, ligne d'aide, persistance")
from avastack.processing.composition import NB_LIGNES_COMPO

verifie("Stacks (fichiers FITS)" in SOURCES
        and "Stacks (fichiers FITS)" in tuple(app.cb_source.cget("values")),
        "source proposée dans le menu (SOURCES + combobox)")
verifie(len(app.var_stacks_roles) == NB_LIGNES_COMPO
        and len(app.var_stacks_fichiers) == NB_LIGNES_COMPO,
        f"panneau : {NB_LIGNES_COMPO} lignes rôle + fichier")
verifie(app.SECTIONS_NOM_MAP.get("stacks") == "Stacks (fichiers FITS)",
        "section pliable « stacks » déclarée avec son titre")

app.var_source.set("Stacks (fichiers FITS)")
app._maj_visibilite_cadres()
verifie(bool(app._lf_stacks.winfo_manager())
        and not app.frm_ctrl_cam.winfo_manager(),
        "source « Stacks » : le cadre stacks est visible, les contrôles "
        "caméra sont masqués")
app.var_source.set("Dossier surveillé (brutes FITS/PNG/TIFF…)")
app._maj_visibilite_cadres()
verifie(not app._lf_stacks.winfo_manager(),
        "autre source : le cadre stacks est masqué (aucun widget orphelin)")
app.var_source.set("Stacks (fichiers FITS)")
app._maj_visibilite_cadres()

# Ligne d'aide : composition déduite + FILTER contradictoire (avertissement).
app.var_stacks_roles[0].set("Ha")
app.var_stacks_fichiers[0].set(f_o3)       # en-tête FILTER = O3 !
app.var_stacks_roles[1].set("O3")
app.var_stacks_fichiers[1].set(f_o3)
app._maj_stacks_info()
txt = app.lbl_stacks_info.cget("text")
verifie("HOO" in txt, "ligne d'aide : composition déduite des rôles → HOO")
verifie("FILTER" in txt and "fait foi" in txt,
        "ligne d'aide : FILTER contradictoire = AVERTISSEMENT (le rôle "
        "indiqué fait foi)")

# Un seul fichier → empilement direct, dit tel quel.
app.var_stacks_roles[1].set("")
app.var_stacks_fichiers[1].set("")
app._maj_stacks_info()
verifie("empilement direct" in app.lbl_stacks_info.cget("text"),
        "ligne d'aide : un seul fichier = empilement direct (sans composition)")

# Validation des lignes (les erreurs doivent être CLAIRES).
def _erreur(fn):
    try:
        fn()
        return None
    except RuntimeError as e:
        return str(e)


app.var_stacks_roles[0].set("Ha")
app.var_stacks_fichiers[0].set("")
verifie("choisissez le fichier" in str(_erreur(app._lire_roles_fichiers_stacks)),
        "rôle sans fichier → erreur claire")
app.var_stacks_roles[0].set("")
app.var_stacks_fichiers[0].set(f_ha)
verifie("aucun rôle" in str(_erreur(app._lire_roles_fichiers_stacks)),
        "fichier sans rôle → erreur claire (le rôle n'est jamais deviné)")
app.var_stacks_roles[0].set("Ha")
app.var_stacks_fichiers[0].set(f_ha)
app.var_stacks_roles[1].set("Ha")
app.var_stacks_fichiers[1].set(f_o3)
verifie("un rôle = un seul fichier"
        in str(_erreur(app._lire_roles_fichiers_stacks)),
        "rôle en double → erreur claire")
app.var_stacks_roles[1].set("O3")
app.var_stacks_fichiers[1].set(os.path.join(racine, "nulle_part.fit"))
verifie("introuvable" in str(_erreur(app._lire_roles_fichiers_stacks)),
        "fichier inexistant → erreur claire")
app.var_stacks_fichiers[1].set(f_o3)
paires = app._lire_roles_fichiers_stacks()
verifie(paires == [("Ha", f_ha), ("O3", f_o3)],
        f"lignes valides → {paires}")

# Persistance (relue au démarrage suivant).
app._sauver_config_app()
verifie(capture.get("stacks_role_0") == "Ha"
        and capture.get("stacks_role_1") == "O3"
        and capture.get("stacks_fichier_0") == f_ha
        and capture.get("stacks_fichier_1") == f_o3,
        "config.json : rôles ET fichiers persistés (stacks_role_i / "
        "stacks_fichier_i)")

# Sélection changée → la source connectée est jugée OBSOLÈTE (refermée).
app.camera = cam
verifie(not app._source_fichiers_obsolete(),
        "sélection inchangée → la source n'est pas refermée")
app.var_stacks_fichiers[1].set(f_ha)
verifie(app._source_fichiers_obsolete(),
        "fichier remplacé → source jugée obsolète (relue au démarrage)")

# ============ [6] PISTE A : réglages du COMPOSITE et « Fusion Ha » (UI)
# Constat réel d'Alain (19/10) : avec la source « Stacks », la composition
# LRGB+Ha était bien déduite, mais le cadre « Fusion Ha » ET les réglages du
# composite (gains, normalisation commune, lisser le combine LRGB) étaient
# INVISIBLES, et le continuum était forcé à l'arrêt. Le cadre « Fusion Ha » est
# un ENFANT de `frm_compo` (panels/compo.py) : masquer la composition les
# masquait TOUS ; et le test « la couche R existe-t-elle ? » ne lisait que les
# lignes DOSSIER de la composition (`_dossier_role_compo`), d'où `""` avec des
# FICHIERS. Correctif = piste A (v2.96.1).
print("[6] Piste A : composition + « Fusion Ha » ACCESSIBLES avec des FICHIERS")

# Les 5 couches du test réel quand la référence M33 est là (mêmes fichiers que
# le volet [3]) ; sinon les FITS synthétiques du banc. Le NOM des fichiers
# n'entre dans aucune décision : seule compte la ligne « rôle → fichier ».
if os.path.isdir(M33):
    _cinq = [(r, os.path.join(M33, f"canal_{r}.fit"))
             for r in ("L", "R", "G", "B", "Ha")]
    _cinq = [(r, f) if os.path.isfile(f) else (r, f_ha) for r, f in _cinq]
    _origine = "référence M33 (5 canal_*.fit)"
else:
    _cinq = [("L", f_ha), ("R", f_ha), ("G", f_o3), ("B", f_o3), ("Ha", f_ha)]
    _origine = "FITS synthétiques (référence M33 absente)"
print(f"  (fichiers : {_origine})")

for i, (r, f) in enumerate(_cinq):
    app.var_stacks_roles[i].set(r)
    app.var_stacks_fichiers[i].set(f)
app.var_source.set("Stacks (fichiers FITS)")
app._maj_visibilite_cadres()          # la source seule doit tout régler
root.update_idletasks()

verifie(app.var_compo.get() == "LRGB+Ha",
        f"composition AFFICHÉE déduite des fichiers : {app.var_compo.get()}")
verifie(bool(app._lf_stacks.winfo_manager())
        and bool(app._lf_composition.winfo_manager()),
        "cadres visibles : panneau des FICHIERS **et** composition "
        "(les réglages du composite en sont des enfants)")
verifie(bool(app.frm_fusion_ha.winfo_manager()),
        "cadre « Fusion Ha » PACKÉ (invisible avant le correctif)")
verifie(app._role_fourni("R") and app._role_fourni("Ha")
        and not app._role_fourni("O3"),
        "_role_fourni connaît la SOURCE : R et Ha fournis par des FICHIERS, "
        "O3 absent")
verifie(str(app.chk_fusion_ha_continuum.cget("state")) == "normal"
        and str(app.sp_fusion_ha_q.cget("state")) == "normal"
        and all(str(rb.cget("state")) == "normal"
                for rb in app.rb_fusion_ha_methode.values()),
        "continuum ACTIF (couche R fournie) : case, force Q et les trois "
        "méthodes accessibles")
app.var_fusion_ha_continuum.set(True)
verifie(app._lire_fusion_ha()["continuum"] is True,
        "`_lire_fusion_ha` GARDE le continuum demandé (R fourni)")
verifie("déduite des fichiers" in app.lbl_compo_info.cget("text"),
        "ligne d'aide : dit que la composition est déduite des fichiers")
verifie(str(app.cb_compo.cget("state")) == "disabled"
        and all(str(w.cget("state")) == "disabled"
                for w in (app.cb_compo_roles + app.ent_compo_dossiers
                          + app.btn_compo_dossiers))
        and str(app.btn_detecter_filtres.cget("state")) == "disabled",
        "menu de composition et lignes DOSSIER VERROUILLÉS (aucun dossier ici)")

# Jalon 141-B : la composition affichée est celle de la SESSION → aucun bandeau.
app._compo_session = "LRGB+Ha"
app._maj_compo_info()
verifie(app.lbl_compo_session.cget("text") == "",
        "141-B : composition affichée = composition de session → aucun "
        "bandeau de divergence")

# Sans fichier R : le continuum se désactive ET se force à False.
app.var_stacks_roles[1].set("")        # plus de couche R
app._on_stacks_roles()
root.update_idletasks()
verifie(not app._role_fourni("R")
        and str(app.chk_fusion_ha_continuum.cget("state")) == "disabled"
        and str(app.sp_fusion_ha_q.cget("state")) == "disabled",
        "sans fichier R : continuum DÉSACTIVÉ (case + force Q)")
verifie(app._lire_fusion_ha()["continuum"] is False,
        "sans fichier R : continuum FORCÉ à False (rien à soustraire)")

# La couche R revient → le réglage redevient accessible.
app.var_stacks_roles[1].set("R")
app._on_stacks_roles()
root.update_idletasks()
verifie(str(app.chk_fusion_ha_continuum.cget("state")) == "normal"
        and app._lire_fusion_ha()["continuum"] is True,
        "fichier R de nouveau fourni : continuum réactivé et relu")

# Un SEUL fichier = empilement direct : aucune composition, donc pas de fusion.
for i in range(1, len(app.var_stacks_roles)):
    app.var_stacks_roles[i].set("")
    app.var_stacks_fichiers[i].set("")
app._on_stacks_roles()
root.update_idletasks()
verifie(not app.frm_fusion_ha.winfo_manager(),
        "un SEUL fichier (empilement direct) : cadre « Fusion Ha » masqué")

# Retour à une source à DOSSIERS : rien n'a été détruit, tout est rendu.
app.var_source.set("Composition multi-dossiers (RGB/HOO/SHO/LRGB)")
app._maj_visibilite_cadres()
root.update_idletasks()
verifie(str(app.cb_compo.cget("state")) == "readonly"
        and all(str(w.cget("state")) == "readonly" for w in app.cb_compo_roles)
        and all(str(w.cget("state")) == "normal"
                for w in (app.ent_compo_dossiers + app.btn_compo_dossiers))
        and str(app.btn_detecter_filtres.cget("state")) == "normal",
        "source à dossiers : menu et lignes DOSSIER RENDUS (readonly/normal)")
verifie(not app._lf_stacks.winfo_manager()
        and bool(app._lf_composition.winfo_manager()),
        "source à dossiers : le panneau stacks est masqué, la composition reste")

try:
    root.destroy()
except Exception:
    pass

# ============================================================== conclusion
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
images.CFA_MODE = CFA_MODE_AVANT
sys.exit(0 if ok else 1)

verifie(leve, "fichier absent → open() lève un message clair")
