# -*- coding: utf-8 -*-
"""Test du jalon 121 (v2.73.0) — FICHE DE RENDU (`<image>.ava.json`).

« Que chaque image dise ce qu'elle a subi » : un JSON COMPAGNON est écrit à côté
de CHAQUE image enregistrée (brut, traité linéaire, couches, tel que vu, résultat
externe), par le MÊME code/thread que l'image — sans rien mettre dans le FITS.
Décisions d'Alain validées le 11/10/2026 : `<image>.ava.json` à côté de l'image,
case à cocher COCHÉE par défaut, chemins COMPLETS, écrite pour TOUTES les sorties.

Ce banc vérifie :
  [1] le module pur `avastack.fiche` (nommage, contenu, écriture ATOMIQUE et
      TOLÉRANTE : une fiche ratée ne lève JAMAIS) ;
  [2] la case « Fiche de rendu » (présente dans le panneau « sortie », cochée par
      défaut, persistance immédiate) ;
  [3] l'état APPLIQUÉ vs AFFICHÉ (`_fiche_etat`) — le bug du 11/10/2026 aurait
      été consigné dans `ecarts` ; on le PROVOQUE ici et on le détecte ;
  [4] un enregistrement RÉEL (empilement brut linéaire, via le worker) écrit
      l'image ET sa fiche, contenu conforme ;
  [5] case DÉCOCHÉE → aucune fiche (contexte None).

Sans toucher au vrai config.json (CONFIG simulé, sauver_config intercepté).
Nécessite un affichage.
Exécution : python bancs/_test_fiche_rendu_jalon121.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk

import numpy as np

import avastack.ui.app as ui
ui.CONFIG = {}                    # config HERMETIQUE (regle du projet :
ui.sauver_config = lambda *a, **k: None   # JAMAIS le vrai config.json)
from avastack import fiche as fiche_mod
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


TMP = tempfile.mkdtemp(prefix="avastack_banc121_")

# ============================================================================
print("[1] Module pur `avastack.fiche` : nommage, contenu, écriture")
chemin_img = os.path.join(TMP, "M33.fits")
attendu = os.path.join(TMP, "M33.ava.json")
verifie(fiche_mod.chemin_fiche(chemin_img) == attendu,
        f"`M33.fits` → `M33.ava.json` (obtenu {os.path.basename(fiche_mod.chemin_fiche(chemin_img))})")
verifie(fiche_mod.chemin_fiche(os.path.join(TMP, "x.tif")).endswith("x.ava.json"),
        "la règle vaut aussi pour un TIFF (le FITS n'a pas le monopole)")

img = np.zeros((48, 64), np.float32)
contenu = fiche_mod.construire(chemin_img, "tel que vu (etire)", image=img,
                               extra={"chaine": [{"etape": "gamma"}]})
verifie(contenu["fichier"] == os.path.abspath(chemin_img),
        "le fichier est consigné en chemin COMPLET (décision ③)")
verifie(contenu["dimensions"] == [48, 64], "les dimensions sont relues de l'image")
verifie(contenu["type_sortie"] == "tel que vu (etire)", "le type de sortie est là")
verifie(contenu["application"]["avastack"] == ui.AVASTACK_VERSION,
        f"version de l'appli : {contenu['application']['avastack']}")
verifie("commit" in contenu["application"], "le commit est présent (vide si hors dépôt)")
verifie(bool(contenu["date"]), "une date/heure est consignée")
verifie(contenu["chaine"] == [{"etape": "gamma"}], "l'extra est fusionné")

c_ecrit, msg = fiche_mod.ecrire(chemin_img, contenu)
verifie(c_ecrit == attendu and msg == "", "écriture réussie à côté de l'image")
verifie(not os.path.exists(attendu + ".part"),
        "aucun fichier provisoire `.part` laissé (écriture ATOMIQUE)")
with open(attendu, encoding="utf-8") as f:
    relu = json.load(f)
verifie(relu["type_sortie"] == "tel que vu (etire)", "le JSON est relisible")

# Tolérance : le dossier parent est un FICHIER → l'écriture échoue proprement.
bloque = os.path.join(TMP, "bloque")
with open(bloque, "w", encoding="utf-8") as f:
    f.write("x")
c_ko, msg_ko = fiche_mod.ecrire(os.path.join(bloque, "x.fits"), contenu)
verifie(c_ko is None and bool(msg_ko),
        f"dossier impossible → (None, message) SANS exception ({msg_ko[:40]}…)")


def cases_sous(w):
    """Toutes les cases à cocher sous un conteneur (récursif — la case vit dans
    le CORPS de la section, pas dans son en-tête)."""
    out = []
    for c in w.winfo_children():
        if isinstance(c, ttk.Checkbutton):
            out.append(c)
        out.extend(cases_sous(c))
    return out


# ============================================================================
print("[2] Case « Fiche de rendu » : présente, cochée par défaut, persistante")
root = tk.Tk()
root.withdraw()
app = ui.App(root)
root.update_idletasks()
textes = [str(c.cget("text")) for c in cases_sous(app._lf_sortie)]
verifie(any("Fiche de rendu" in t for t in textes),
        f"la case vit dans le panneau « sortie » ({textes})")
verifie(bool(app.var_fiche_rendu.get()) is True, "COCHÉE par défaut (décision ②)")
app.var_fiche_rendu.set(False)
app._on_fiche_rendu()
verifie(ui.CONFIG.get("fiche_rendu") is False,
        "décochée → `fiche_rendu` = False persisté (booléen EXPLICITE)")
app.var_fiche_rendu.set(True)
app._on_fiche_rendu()
verifie(ui.CONFIG.get("fiche_rendu") is True, "recochée → True persisté")

# ============================================================================
print("[3] État APPLIQUÉ vs AFFICHÉ : les écarts sont DÉTECTÉS")
ui.CONFIG = {}                            # défauts
root3 = tk.Tk()
root3.withdraw()
app3 = ui.App(root3)
root3.update_idletasks()
etat = app3._fiche_etat()
verifie("affiche" in etat and isinstance(etat["affiche"], dict)
        and "ecarts" in etat, "l'état porte `affiche` ET `ecarts`")
verifie(len(etat["ecarts"]) == 0,
        f"par défaut, AUCUN écart appliqué/affiché (obtenu {etat['ecarts']})")
# On PROVOQUE le bug du 11/10/2026 : sat_canaux appliqué à 3,0, écran à 1,00.
app3.disp.sat_canaux = (1.0, 1.0, 3.0)
etat2 = app3._fiche_etat()
bleus = [e for e in etat2["ecarts"] if e["reglage"] == "saturation_bleue"]
verifie(len(bleus) == 1 and bleus[0]["applique"] == 3.0
        and bleus[0]["affiche"] == 1.0,
        "divergence sat_b 3,0/1,00 CONSIGNÉE dans `ecarts` (le bug ne serait "
        "plus invisible)")
root3.destroy()


class CameraMuette:
    """Caméra factice : ne renvoie PLUS aucune frame (dossier terminé)."""
    name = "muette"

    def read(self):
        return None


def lance_worker(app, timeout=8.0):
    """Lance le worker d'acquisition jusqu'à ce que `saved_path` soit posé."""
    app.saved_path = None
    th = threading.Thread(target=app._worker, daemon=True)
    th.start()
    t0 = time.time()
    while time.time() - t0 < timeout and app.saved_path is None:
        time.sleep(0.05)
    app.running = False
    th.join(timeout=3.0)


# ============================================================================
print("[4] Enregistrement RÉEL : l'image ET sa fiche `<image>.ava.json`")
app.camera = CameraMuette()
app.running = True
stacker = LiveStacker((48, 64), k=3, method="kappa", window=8)
stacker.add(np.full((48, 64), 0.25, np.float32))
app.stacker = stacker
chemin_pile = os.path.join(TMP, "pile_brute.fits")
app.save_request = (chemin_pile, app._fiche_contexte())
lance_worker(app)
verifie(os.path.isfile(chemin_pile), "image linéaire écrite (worker)")
fiche_pile = fiche_mod.chemin_fiche(chemin_pile)
verifie(os.path.isfile(fiche_pile),
        f"fiche écrite à côté : {os.path.basename(fiche_pile)}")
with open(fiche_pile, encoding="utf-8") as f:
    fj = json.load(f)
verifie(str(fj["type_sortie"]).startswith("empilement brut"),
        f"type de sortie = {fj['type_sortie']!r}")
verifie(fj.get("dimensions") == [48, 64], "dimensions de l'image écrite")
verifie(fj["source"]["frames"] == 1, "SOURCE : nombre de frames empilées")
verifie(fj["chaine"] == [], "empilement brut : aucune chaîne de rendu")
verifie(bool(fj.get("entete_fits")) and "AVAVUE" in fj["entete_fits"],
        "l'en-tête FITS écrit est repris dans la fiche")
verifie(isinstance(fj.get("etat"), dict) and "affiche" in fj["etat"],
        "l'état appliqué/affiché fait partie de la fiche")

# ============================================================================
print("[5] Case DÉCOCHÉE → aucune fiche (mais l'image est bien écrite)")
app.var_fiche_rendu.set(False)
verifie(app._fiche_contexte() is None, "contexte None quand la case est décochée")
app.running = True
app.stacker = stacker
chemin_sans = os.path.join(TMP, "pile_sans_fiche.fits")
app.save_request = (chemin_sans, app._fiche_contexte())
lance_worker(app)
verifie(os.path.isfile(chemin_sans), "image écrite même sans fiche")
verifie(not os.path.exists(fiche_mod.chemin_fiche(chemin_sans)),
        "AUCUNE fiche quand la case est décochée")
app.var_fiche_rendu.set(True)

# ============================================================================
print("[6] Compatibilité : une demande SIMPLE (chaîne) reste valide")
app.running = True
app.stacker = stacker
chemin_chaine = os.path.join(TMP, "pile_ancien_format.fits")
app.save_request = chemin_chaine          # ancien format : une simple chaîne
lance_worker(app)
verifie(os.path.isfile(chemin_chaine),
        "l'ancien format (chaîne nue) écrit toujours l'image")
verifie(not os.path.exists(fiche_mod.chemin_fiche(chemin_chaine)),
        "chaîne nue = pas de contexte → aucune fiche (comportement sûr)")

# ============================================================================
print("[7] « tel que vu » : la CHAÎNE appliquée est décrite (5e élément retour)")
app.running = True
app.stacker = stacker
app.asseen_result = None
app.asseen_busy = False
chemin_vu = os.path.join(TMP, "tel_que_vu.fits")
app.save_asseen_request = (chemin_vu, "pile", app._reglages_rendu(), False,
                           app._fiche_contexte())
th4 = threading.Thread(target=app._worker, daemon=True)
th4.start()
t0 = time.time()
while time.time() - t0 < 20 and app.asseen_result is None:
    time.sleep(0.05)
app.running = False
th4.join(timeout=5.0)
verifie(isinstance(app.asseen_result, str)
        and not app.asseen_result.startswith("ERREUR"),
        f"rendu « tel que vu » écrit ({app.asseen_result})")
fiche_vu = fiche_mod.chemin_fiche(chemin_vu)
verifie(os.path.isfile(fiche_vu), "fiche du « tel que vu » écrite à côté")
with open(fiche_vu, encoding="utf-8") as f:
    fv = json.load(f)
verifie(str(fv["type_sortie"]).startswith("tel que vu"),
        f"type de sortie = {fv['type_sortie']!r}")
verifie(any(e.get("etape") == "etirement" and e.get("actif") for e in fv["chaine"]),
        "la chaîne décrit l'ÉTIREMENT (appliqué) — le 5e élément a bien voyagé")
verifie(all("etape" in e and "actif" in e for e in fv["chaine"]),
        f"chaîne ORDONNÉE, {len(fv['chaine'])} étapes")

root.destroy()
shutil.rmtree(TMP, ignore_errors=True)
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)


