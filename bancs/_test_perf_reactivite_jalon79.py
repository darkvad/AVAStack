# -*- coding: utf-8 -*-
"""Banc du jalon 79 : RÉACTIVITÉ DES RÉGLAGES D'APRÈS ÉTIREMENT.

QUESTION D'ALAIN (29/09/2026) : « regarde aussi certains réglages qui
s'appliquent après étirement (comme la saturation, mais peut-être d'autres
aussi) pour vérifier qu'ils ne relancent pas toute la chaîne, ça donnera de la
réactivité visuelle ».

RÉPONSE MESURÉE (banc de performance, 29/09/2026) : aucun de ces réglages ne
relançait la chaîne LOURDE — la clé du solveur VeraLux (`_vl_params`) ne
contient ni gamma, ni saturations, ni barres de niveaux, donc ni GraXpert, ni
débruitage, ni VeraLux ne repartaient. MAIS chaque geste de souris recalculait
deux choses pour rien : ① les DEUX histogrammes (34 ms mesurés sur l'aperçu
couleur) alors que les deux bandes sont tracées AVANT ces étages ; ② tout
l'ÉTIREMENT (médiane/σ/p99,9 puis MTF : 78 ms) alors que ces réglages
s'appliquent APRÈS. D'où, même jalon : `hist=False` sur gamma / saturation
globale / saturation par couleur (même règle que les barres de niveaux depuis le
jalon 75) et une MÉMOIRE de la sortie du moteur
(`DisplayProcessor._moteur_stf`).

Ce banc verrouille les deux — ET LE CONTRAIRE : un réglage qui change VRAIMENT
la donnée doit continuer de recalculer les histogrammes (sinon on aurait figé
l'affichage pour gagner du temps).

Vérifie :
  [0] l'aperçu initial passe bien par les deux histogrammes (témoin de départ) ;
  [1] gamma (curseur RÉEL) : l'image affichée CHANGE, les histogrammes NON ;
  [2] saturation globale : idem ;
  [3] saturation par couleur R/V/B : idem ;
  [4] barres de niveaux (glissement réel) : idem (jalon 75, verrouillé ici) ;
  [5] TÉMOIN INVERSÉ : « Coupure du bruit » (qui change la sortie du moteur)
      DOIT recalculer les histogrammes ;
  [6] mémoire du moteur : un geste ne mesure NI ne recalcule l'étirement, et le
      rendu mémoïsé est IDENTIQUE AU BIT au rendu recalculé sans mémoire ;
  [7] coût d'un geste : mesure indicative avec garde-fou généreux (ce n'est pas
      un objectif de performance, c'est un filet anti-absurdité).

Exécution : python bancs/_test_perf_reactivite_jalon79.py   (nécessite un affichage)
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import time
import tkinter as tk
from tkinter import ttk

import numpy as np

import avastack.ui.app as ui
from avastack.processing.display import DisplayProcessor

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def image_factice(h=360, w=560, seed=7):
    """Aperçu linéaire RVB factice [0..1] : fond + nébulosité + étoiles."""
    rng = np.random.default_rng(seed)
    img = rng.normal(0.02, 0.006, (h, w, 3))
    yy, xx = np.mgrid[0:h, 0:w]
    prof = 0.05 * np.exp(-((yy - h / 3.0) ** 2 + (xx - w / 2.0) ** 2)
                         / (h * w / 30.0))
    for _ in range(30):
        cy, cx = rng.integers(0, h), rng.integers(0, w)
        prof = prof + 0.6 * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / 6.0)
    img = img + prof[..., None]
    return np.clip(img, 0.0, 1.0).astype(np.float32)


class Ev:
    """Évènement minimal (le banc n'a pas de souris) : le code de l'interface
    ne lit que `x`/`y` (et `delta` pour la molette)."""
    def __init__(self, x=0, y=0, delta=0):
        self.x, self.y, self.delta = x, y, delta


# --- compteurs : on ENVELOPPE le code testé, on ne le remplace pas ----------
COMPTES = {"hist": 0, "stats": 0, "affichees": []}


def instrumenter():
    hist0 = ui.App._maj_histogrammes

    def hist(self, *a, **k):
        COMPTES["hist"] += 1
        return hist0(self, *a, **k)
    ui.App._maj_histogrammes = hist

    show0 = ui.App._show_image

    def show(self, img8):
        COMPTES["affichees"].append(np.array(img8, copy=True))
        return show0(self, img8)
    ui.App._show_image = show

    stats0 = DisplayProcessor._calc_stats          # @staticmethod

    def stats(img):
        COMPTES["stats"] += 1
        return stats0(img)
    DisplayProcessor._calc_stats = staticmethod(stats)


def parcours(w):
    yield w
    for e in w.winfo_children():
        yield from parcours(e)


def curseur(app, texte):
    """Le `ttk.Scale` RÉEL portant l'étiquette `texte` : l'interface est
    construite par `_add_slider` (ligne → tête [libellé, valeur] + curseur), on
    la retrouve par le libellé plutôt que par une position en dur."""
    for w in parcours(app.root):
        if not isinstance(w, ttk.Scale):
            continue
        ligne = w.master
        row = ligne.master if ligne is not None else None
        if row is None:
            continue
        for cadre in row.winfo_children():
            for c in cadre.winfo_children():
                try:
                    txt = c.cget("text")
                except Exception:                      # noqa: BLE001
                    continue
                if str(txt) == texte:
                    return w
    return None


def geste(app, texte, valeur):
    """Déclenche le curseur COMME UN GESTE DE SOURIS : Tk appelle la commande
    du curseur quand sa valeur change → c'est bien le câblage de l'interface
    qui est éprouvé, pas un appel écrit par le banc. True si le curseur existe."""
    s = curseur(app, texte)
    if s is None:
        verifie(False, f"curseur « {texte} » INTROUVABLE")
        return False
    s.set(float(valeur))
    app.root.update()
    return True


# ============================================================ [0] état de départ
print("=" * 78)
print("[0] INTERFACE RÉELLE (hermétique) ET APERÇU POSÉ")
print("=" * 78)
ui.CONFIG = {}                       # état initial DÉTERMINÉ (moteur STF)
ui.sauver_config = lambda d: None
root = tk.Tk()
app = ui.App(root)
root.update()
instrumenter()
rgb = image_factice()
app.var_view.set("pile")
app.last_show = rgb
COMPTES["hist"], COMPTES["affichees"] = 0, []
app._refresh_preview()               # rendu initial (témoin de départ)
root.update()
verifie(COMPTES["hist"] == 1,
        "l'aperçu initial recalcule BIEN les histogrammes (témoin de départ)")
verifie(bool(COMPTES["affichees"]), "une image a bien été affichée")
verifie(app.disp.stretch == "stf",
        "moteur STF : c'est lui qui est recalé par ce banc (aucune surprise)")


def controle_geste(nom, texte, valeur):
    """Un geste d'APRÈS étirement : l'image affichée doit CHANGER (le réglage
    agit), les histogrammes NON (ils sont calculés avant ces étages)."""
    avant = COMPTES["affichees"][-1] if COMPTES["affichees"] else None
    COMPTES["hist"], COMPTES["affichees"] = 0, []
    if not geste(app, texte, valeur):
        return
    apres = COMPTES["affichees"][-1] if COMPTES["affichees"] else None
    verifie(avant is not None and apres is not None
            and not np.array_equal(avant, apres),
            f"{nom} : l'image affichée CHANGE (le réglage agit vraiment)")
    verifie(COMPTES["hist"] == 0,
            f"{nom} : AUCUN recalcul d'histogramme (0 attendu, "
            f"{COMPTES['hist']} obtenu)")


print("\n[1] GAMMA (réglage d'après étirement)")
controle_geste("gamma 1,50", "Gamma (les 2 moteurs)", 1.5)

print("\n[2] SATURATION GLOBALE (réglage d'après étirement)")
controle_geste("saturation 1,60", "Saturation (globale)", 1.6)

print("\n[3] SATURATION PAR COULEUR R/V/B (réglage d'après étirement)")
for texte, val in (("Saturation rouge", 1.40), ("Saturation verte", 0.80),
                   ("Saturation bleue", 1.20)):
    controle_geste(f"{texte} {val:.2f}", texte, val)

print("\n[4] BARRES DE NIVEAUX (glissement réel au clic-glisser)")
larg = app._hist_taille()[0]
COMPTES["hist"], COMPTES["affichees"] = 0, []
app._hist_press(Ev(app._hist_x(0.50, larg)))
if app._hist_drag is None:
    verifie(False, "la barre médian n'a pas été saisie (banc non concluant)")
else:
    app._hist_drag_move(Ev(app._hist_x(0.62, larg)))
    app._hist_release()
    root.update()
    verifie(COMPTES["hist"] == 0,
            f"barres : AUCUN recalcul d'histogramme (0 attendu, "
            f"{COMPTES['hist']} obtenu)")
    verifie(bool(COMPTES["affichees"]),
            "le glissement a bien redessiné l'image (le geste agit)")

print("\n[5] TÉMOIN INVERSÉ — un réglage qui CHANGE la donnée doit recalculer")
COMPTES["hist"], COMPTES["affichees"] = 0, []
geste(app, "Coupure du bruit (k·σ sous le fond)", 3.4)
verifie(COMPTES["hist"] == 1,
        "« Coupure du bruit » (change la sortie du moteur) recalcule les "
        f"histogrammes (1 attendu, {COMPTES['hist']} obtenu) — le drapeau "
        "n'est donc pas figé à False")

print("\n[6] MÉMOIRE DU MOTEUR — un geste ne recalcule pas l'étirement")
geste(app, "Gamma (les 2 moteurs)", 1.0)      # retour à l'identité
app.disp._memo_moteur = None
app._refresh_preview(hist=False)              # rendu de référence (recalculé)
COMPTES["stats"], COMPTES["affichees"] = 0, []
geste(app, "Gamma (les 2 moteurs)", 1.35)     # geste : servi par la mémoire
verifie(COMPTES["stats"] == 0,
        f"aucune mesure de stats pendant le geste (0 attendu, "
        f"{COMPTES['stats']} obtenu)")
avec_memo = COMPTES["affichees"][-1] if COMPTES["affichees"] else None
app.disp._memo_moteur = None                  # mémoire EFFACÉE, même réglage
COMPTES["affichees"] = []
app._refresh_preview(hist=False)
sans_memo = COMPTES["affichees"][-1] if COMPTES["affichees"] else None
verifie(avec_memo is not None and sans_memo is not None
        and np.array_equal(avec_memo, sans_memo),
        "rendu mémoïsé IDENTIQUE AU BIT au rendu recalculé (écart 0)")
COMPTES["stats"] = 0
app.disp.process(rgb, live=True)              # arrivée d'une frame
verifie(COMPTES["stats"] == 1,
        "témoin : `live=True` (nouvelle frame) mesure bien les stats")

print("\n[7] COÛT D'UN GESTE (mesure indicative, garde-fou généreux)")
n = 12
t0 = time.perf_counter()
for i in range(n):
    geste(app, "Gamma (les 2 moteurs)", 1.0 + 0.04 * i)
dt = (time.perf_counter() - t0) / n * 1000.0
print(f"    geste gamma mesuré : {dt:.1f} ms (avant le jalon 79 : ~103 ms "
      "mesurés au banc de performance, + 34 ms d'histogrammes)")
verifie(dt < 250.0,
        f"un geste reste sous le garde-fou ({dt:.1f} ms < 250 ms) — un geste "
        "ne bloque jamais l'interface")

root.destroy()
print()
print("BANC JALON 79 (réactivité des réglages d'après-étirement) : "
      + ("TOUT PASSE ✅" if ok else "ÉCHEC ✗"))
sys.exit(0 if ok else 1)
