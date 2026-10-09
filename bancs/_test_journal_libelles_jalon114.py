# -*- coding: utf-8 -*-
"""Banc du jalon 114 — ASTROMÉTRIE VISIBLE : JOURNAL des lignes d'état + LIBELLÉS COPIABLES.

Deux doléances d'Alain (09/10/2026), après le test réel de v2.65.0 (M31 LRGB) :
  ① « toujours le même problème sur l'astrométrie — AUCUNE INFO DANS LE
     JOURNAL » : les messages d'échec n'existaient que dans l'interface (le
     worker n'écrit rien au journal) ;
  ② « impossible de copier les textes des libellés orange ou jaune » : les
     `ttk.Label` de Tk ne sont pas sélectionnables.

Vérifie :
  [1] `App._texte_libelle` : texte FIGÉ (`text=`) et texte ANIMÉ
      (`textvariable=`, y compris vide) ;
  [2] `App._copier_libelle` : le texte part RÉELLEMENT dans le presse-papiers ;
  [3] le clic droit est ARMÉ (`bind_all`) et ne concerne QUE les libellés (hors
      libellé, le handler n'intercepte pas l'événement) ;
  [4] `App._noter_etat` : écrit au journal la 1re fois ET à chaque CHANGEMENT,
      jamais de doublon à l'identique, jamais de ligne vide ;
  [5] intégration `App._update_status` : une ligne d'astrométrie poussée par le
      worker (clé « astro ») part AU JOURNAL — c'est le chemin réel du défaut.

Exécution : python bancs/_test_journal_libelles_jalon114.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV/OpenCL au teardown sinon

import avastack.ui.app as ui
from avastack import journal

if hasattr(sys.stdout, "reconfigure"):   # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# Journal intercepté AVANT la construction de l'App : le banc reste hermétique
# (aucune ligne écrite dans le vrai journal.txt) tout en voyant tout ce que
# l'application journalise.
captures = []


def _note_bouchon(etape, detail=""):
    captures.append((str(etape), str(detail)))
    return True


_origine_note = journal.note
journal.note = _note_bouchon

ui.CONFIG = {}
ui.sauver_config = lambda *a, **k: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)


# ============================================ [1] _texte_libelle
print("[1] App._texte_libelle : texte figé et texte animé (textvariable)")
lbl_fige = tk.Label(root, text="Astrométrie : échec — 3 inliers, 1,794″/px")
verifie(ui.App._texte_libelle(lbl_fige) == "Astrométrie : échec — 3 inliers, 1,794″/px",
        "libellé `text=` : le texte est relu tel quel")

var = tk.StringVar(value="")
lbl_var = tk.Label(root, textvariable=var)
verifie(ui.App._texte_libelle(lbl_var) == "",
        "libellé `textvariable=` vide : chaîne vide, jamais d'exception")
var.set("Photométrie : en attente de l'astrométrie (WCS)")
verifie(ui.App._texte_libelle(lbl_var) == "Photométrie : en attente de l'astrométrie (WCS)",
        "libellé `textvariable=` renseigné : la VALEUR est relue (pas le nom de variable)")

lbl_ttk = ttk.Label(root, text="SPCC : en attente de la mesure")
verifie(ui.App._texte_libelle(lbl_ttk) == "SPCC : en attente de la mesure",
        "`ttk.Label` (le type réel des lignes d'état) : texte relu")


# ============================================ [2] _copier_libelle
print("[2] App._copier_libelle : le texte part dans le presse-papiers")
app._copier_libelle(lbl_fige)
root.update()
verifie(root.clipboard_get() == "Astrométrie : échec — 3 inliers, 1,794″/px",
        f"presse-papiers = texte du libellé (reçu « {root.clipboard_get()[:40]}… »)")


# ============================================ [3] clic droit armé, libellés seuls
print("[3] clic droit : armé (bind_all) et réservé aux libellés")
verifie(bool(root.bind_all("<Button-3>")),
        "clic droit <Button-3> armé sur la fenêtre (bind_all)")
canvas = tk.Canvas(root)
verifie(app._clic_droit_libelle(
            SimpleNamespace(widget=canvas, x_root=0, y_root=0)) is None,
        "clic droit HORS libellé : aucune interception (menu non ouvert)")


# ============================================ [4] _noter_etat
print("[4] App._noter_etat : 1re fois + changements, sans doublon ni vide")
captures.clear()
app._etats_logges = {}
app._noter_etat("astrométrie", "Astrométrie : résolution en cours (12 frames)…")
app._noter_etat("astrométrie", "Astrométrie : résolution en cours (12 frames)…")
app._noter_etat("astrométrie", "Astrométrie : échec — 3 inliers, échelle 1,794″/px")
app._noter_etat("astrométrie", "")
attendu = [("astrométrie", "Astrométrie : résolution en cours (12 frames)…"),
           ("astrométrie", "Astrométrie : échec — 3 inliers, échelle 1,794″/px")]
verifie(captures == attendu,
        f"journal = 1re ligne + changement, rien d'autre — reçu {captures}")


# ============================================ [5] _update_status → journal
print("[5] App._update_status : la ligne d'astrométrie du WORKER part au journal")
captures.clear()
app._etats_logges = {}
st = dict(frames=12, rejets=0, bad=9, fps=1.0, cam="test", file="", pending=0,
          failed=0, seeing=None, seeing_msg="",
          astro="Astrométrie : échec — 3 inliers, échelle 1,794″/px "
                "(1/20 essais, réessai automatique dès que l'empilement double)")
app._update_status(st)
verifie(("astrométrie",
         "Astrométrie : échec — 3 inliers, échelle 1,794″/px "
         "(1/20 essais, réessai automatique dès que l'empilement double)")
        in captures,
        f"l'échec du worker est tracé au journal — reçu {captures}")
verifie(app.lbl_astro.cget("text").startswith("Astrométrie : échec"),
        "le même texte est affiché à l'écran (journal et interface cohérents)")

# Rejeu IDENTIQUE : aucun doublon (le worker pousse son état à chaque frame).
n_avant = len(captures)
app._update_status(st)
verifie(len(captures) == n_avant,
        "rejeu de la MÊME ligne : aucun doublon (pas de pollution du journal)")

journal.note = _origine_note
root.destroy()
print()
print("RÉSULTAT : " + ("TOUS LES TESTS PASSENT" if ok else "ÉCHECS À CORRIGER"))
sys.exit(0 if ok else 1)
