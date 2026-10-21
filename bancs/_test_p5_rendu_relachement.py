# -*- coding: utf-8 -*-
"""Banc P5 (lot 5) — RENDU AU RELÂCHEMENT des curseurs.

DÉCISION D'ALAIN (20/10/2026, après MESURE) : pendant un GLISSEMENT, on ne
calcule RIEN ; l'aperçu part UNE fois au `<ButtonRelease-1>`. Prix assumé :
pendant le geste, l'image ne correspond plus à la valeur affichée. Les gestes
DISCRETS (boutons « - »/« + », zone de saisie, `_poser_curseur`) restent
immédiats, et un changement SANS relâchement (flèches clavier, `s.set()`
programmatique) est rattrapé par un minuteur (~150 ms), remis à zéro à chaque
pose : une rafale de poses = UN aperçu.

CE QUE CE BANC VERROUILLE (interface RÉELLE, widgets réels)
  [0] témoin : l'aperçu initial passe par `_refresh_preview` (compteur armé) ;
  [1] câblage : `<ButtonPress-1>` et `<ButtonRelease-1>` du curseur mènent bien
      aux gestionnaires de glissement (vérifié par `bind`, pas supposé) ;
  [2] PENDANT un glissement : 30 pas de souris → AUCUN aperçu, la variable et
      l'étiquette suivent la dernière valeur, et le réglage n'est PAS encore
      appliqué (`disp.gamma` inchangé) — c'est bien le CALCUL qui est différé,
      pas l'affichage de la valeur ;
  [3] AU RELÂCHEMENT : UN SEUL aperçu, `disp.gamma` appliqué, et l'image
      affichée est IDENTIQUE AU BIT à un rendu direct du même réglage ; attendre
      ensuite plus que le filet ne produit AUCUN second aperçu (minuteur annulé) ;
  [4] FILET : un glissement qui n'a PAS de relâchement (grab perdu) rend quand
      même, après le délai du filet — jamais d'image périmée ;
  [5] gestes DISCRETS : `_pas(±1)` et une saisie validée rendent IMMÉDIATEMENT
      (un aperçu chacun, sans passer par un minuteur) ; `_poser_curseur`
      (restauration de config) applique tout de suite ;
  [6] changement SANS relâchement : 5 `s.set()` en rafale = 0 aperçu immédiat,
      puis UN SEUL après le minuteur (coalescence mesurée, pas supposée).

Exécution : python bancs/_test_p5_rendu_relachement.py   (nécessite un affichage)
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
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

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def image_factice(h=240, w=320, seed=7):
    """Aperçu linéaire RVB factice [0..1] : fond + nébulosité + étoiles."""
    rng = np.random.default_rng(seed)
    img = rng.normal(0.02, 0.006, (h, w, 3))
    yy, xx = np.mgrid[0:h, 0:w]
    prof = 0.05 * np.exp(-((yy - h / 3.0) ** 2 + (xx - w / 2.0) ** 2)
                         / (h * w / 30.0))
    for _ in range(20):
        cy, cx = rng.integers(0, h), rng.integers(0, w)
        prof = prof + 0.6 * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / 6.0)
    img = img + prof[..., None]
    return np.clip(img, 0.0, 1.0).astype(np.float32)


# --- compteurs : on ENVELOPPE le code testé, on ne le remplace pas ----------
COMPTES = {"preview": 0, "affichees": []}


def instrumenter():
    p0 = ui.App._refresh_preview

    def preview(self, *a, **k):
        COMPTES["preview"] += 1
        return p0(self, *a, **k)
    ui.App._refresh_preview = preview            # pyright: ignore

    s0 = ui.App._show_image

    def show(self, img8):
        COMPTES["affichees"].append(np.array(img8, copy=True))
        return s0(self, img8)
    ui.App._show_image = show                    # pyright: ignore


def remise_a_zero():
    COMPTES["preview"] = 0
    COMPTES["affichees"] = []


def parcours(w):
    yield w
    for e in w.winfo_children():
        yield from parcours(e)


def curseur(app, texte):
    """Le `ttk.Scale` RÉEL portant l'étiquette `texte` (par le libellé, jamais
    par une position en dur)."""
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
                except Exception:                  # noqa: BLE001
                    continue
                if str(txt) == texte:
                    return w
    return None


def etiquette(app, var):
    """Texte du widget de valeur du curseur lié à `var` (Label, ou Entry en mode
    saisie) — même lecture que le banc du jalon 120."""
    s = app._curseurs[str(var)]
    tete = s._row.winfo_children()[0]
    w = tete.winfo_children()[-1]
    return w.get() if isinstance(w, ttk.Entry) else w.cget("text")


def attendre(app, duree_s):
    """Laisse filer le temps DANS la boucle Tk (les minuteurs `after` partent)."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < duree_s:
        app.root.update()
        time.sleep(0.01)


print("=" * 78)
print("[0] INTERFACE RÉELLE (hermétique) — APERÇU POSÉ")
print("=" * 78)
ui.CONFIG = {}                       # état initial DÉTERMINÉ (moteur STF)
ui.sauver_config = lambda *a, **k: None
ui.App._dire = lambda self, *a, **k: None        # jamais de boîte MODALE
root = tk.Tk()
app = ui.App(root)
# 1b (20/10/2026) : le banc compte les aperçus RENDUS (P5) → rendu IMMÉDIAT
# (le fil de rendu ne sert qu'en production).
app.rendu.immediat = True
root.update()
instrumenter()
app.var_view.set("pile")
app.last_show = image_factice()
remise_a_zero()
app._refresh_preview()
root.update()
verifie(COMPTES["preview"] == 1 and bool(COMPTES["affichees"]),
        f"témoin : l'aperçu initial rend UNE fois ({COMPTES['preview']})")
verifie(app.disp.stretch == "stf", "moteur STF (état du banc déterminé)")

TEXTE = "Gamma (les 2 moteurs)"
s = curseur(app, TEXTE)
var = app.var_gamma
if s is None:
    verifie(False, f"curseur « {TEXTE} » INTROUVABLE")
    root.destroy()
    sys.exit(1)

print("\n[1] CÂBLAGE — le geste mène aux gestionnaires de glissement")
verifie(bool(s.bind("<ButtonPress-1>")),
        "« <ButtonPress-1> » du curseur est lié (début de geste)")
verifie(bool(s.bind("<ButtonRelease-1>")),
        "« <ButtonRelease-1> » du curseur est lié (rendu au relâchement)")
verifie(callable(getattr(s, "_debut_glissement", None))
        and callable(getattr(s, "_fin_glissement", None)),
        "les deux gestionnaires sont exposés (bancs et outil de mesure)")

print("\n[2] PENDANT un glissement — AUCUN calcul, la valeur suit")
app._poser_curseur(var, 1.0)               # état de départ DÉTERMINÉ
root.update()
gamma_avant = float(app.disp.gamma)
remise_a_zero()
s._debut_glissement()
for i in range(30):
    s.set(1.0 + 0.02 * i)                  # 30 pas de souris (1,00 → 1,58)
verifie(COMPTES["preview"] == 0,
        f"30 pas de glissement : AUCUN aperçu ({COMPTES['preview']} appel)")
verifie(abs(float(var.get()) - 1.58) < 1e-6,
        f"la VARIABLE suit le geste ({float(var.get()):.2f})")
verifie(abs(float(str(etiquette(app, var)).replace(",", ".")) - 1.58) < 1e-6,
        f"l'ÉTIQUETTE suit le geste ({etiquette(app, var)})")
verifie(abs(float(app.disp.gamma) - gamma_avant) < 1e-9,
        f"le RÉGLAGE n'est pas encore appliqué (disp.gamma reste "
        f"{float(app.disp.gamma):.2f}) — c'est bien le calcul qui est différé")

print("\n[3] AU RELÂCHEMENT — UN aperçu, et le bon")
s._fin_glissement()
root.update()
verifie(COMPTES["preview"] == 1,
        f"le relâchement rend UNE fois ({COMPTES['preview']} appel)")
verifie(abs(float(app.disp.gamma) - 1.58) < 1e-6,
        f"le réglage est appliqué au relâchement (disp.gamma "
        f"{float(app.disp.gamma):.2f})")
image_relachement = COMPTES["affichees"][-1] if COMPTES["affichees"] else None
app.disp._memo_moteur = None               # rendu direct, sans mémoire
remise_a_zero()
app._refresh_preview()
root.update()
image_directe = COMPTES["affichees"][-1] if COMPTES["affichees"] else None
verifie(image_relachement is not None and image_directe is not None
        and np.array_equal(image_relachement, image_directe),
        "l'image du relâchement est IDENTIQUE AU BIT à un rendu direct "
        "(aucune image périmée)")
remise_a_zero()
attendre(app, 0.9)                         # > filet de glissement (600 ms)
verifie(COMPTES["preview"] == 0,
        f"le minuteur du geste a bien été ANNULÉ par le relâchement "
        f"({COMPTES['preview']} aperçu tardif)")

print("\n[4] FILET — glissement SANS relâchement (grab perdu)")
remise_a_zero()
s._debut_glissement()
s.set(1.70)                                # pas de `_fin_glissement`
attendre(app, 0.9)                         # > 600 ms de filet
verifie(COMPTES["preview"] == 1,
        f"le filet rend UNE fois sans relâchement ({COMPTES['preview']} appel) "
        "— jamais d'image périmée")
verifie(abs(float(app.disp.gamma) - 1.70) < 1e-6,
        f"le réglage du geste abandonné est appliqué ({float(app.disp.gamma):.2f})")
s._fin_glissement()                        # remise en état : le geste est clos
attendre(app, 0.3)
remise_a_zero()                            # son after_idle ne rend rien de plus

print("\n[5] Gestes DISCRETS — effet IMMÉDIAT (aucun minuteur attendu)")
remise_a_zero()
v0 = float(var.get())
s._pas(1)                                  # clic « + »
verifie(COMPTES["preview"] == 1,
        f"un clic « + » rend immédiatement ({COMPTES['preview']} appel)")
verifie(abs(float(app.disp.gamma) - round(v0 + 0.05, 6)) < 1e-6,
        f"le pas est appliqué dans la foulée (disp.gamma "
        f"{float(app.disp.gamma):.2f})")
remise_a_zero()
app._poser_curseur(var, 1.25)              # restauration de config
verifie(COMPTES["preview"] == 1 and abs(float(app.disp.gamma) - 1.25) < 1e-6,
        f"« _poser_curseur » applique TOUT DE SUITE ({COMPTES['preview']} aperçu, "
        f"disp.gamma {float(app.disp.gamma):.2f})")
# Zone de saisie : le gamma n'en a pas (Label) — on éprouve un curseur qui en a
# une (gain caméra). Absente (panneau non construit) → volet sauté, pas échoué.
sg = getattr(app, "sl_gain", None)
if sg is None:
    print("  (curseur de gain absent : volet « saisie » sauté)")
else:
    ent = None
    for c in sg._row.winfo_children()[0].winfo_children():
        if isinstance(c, ttk.Entry):
            ent = c
            break
    if ent is None:
        verifie(False, "zone de saisie du gain INTROUVABLE")
    else:
        remise_a_zero()
        # `event_generate` d'une TOUCHE ne part que si le widget a le FOCUS
        # (mesuré ici : sans focus, aucun rappel — le banc ne testerait rien).
        ent.focus_force()
        root.update()
        ent.delete(0, "end")
        ent.insert(0, "42")
        ent.event_generate("<KeyPress-Return>")
        root.update()
        # Le gain ne rend pas d'aperçu (son callback pose `pending_settings`
        # pour le worker) : « immédiat » se juge donc sur l'APPLICATION du
        # réglage, pas sur un compteur d'images.
        verifie(int(app.var_gain.get()) == 42 and int(app.gain_val) == 42,
                f"une saisie validée s'applique immédiatement (gain "
                f"{int(app.var_gain.get())}, gain_val {int(app.gain_val)})")

print("\n[6] Changement SANS relâchement — minuteur, rafale = UN aperçu")
remise_a_zero()
for i in range(5):
    s.set(1.10 + 0.01 * i)                 # 5 poses programmatiques
verifie(COMPTES["preview"] == 0,
        f"5 poses en rafale : AUCUN aperçu immédiat ({COMPTES['preview']})")
attendre(app, 0.5)                         # > minuteur (150 ms)
verifie(COMPTES["preview"] == 1,
        f"le minuteur rend UNE fois pour la rafale ({COMPTES['preview']} appel)")
verifie(abs(float(app.disp.gamma) - 1.14) < 1e-6,
        f"la DERNIÈRE valeur est celle appliquée (disp.gamma "
        f"{float(app.disp.gamma):.2f})")

root.destroy()
print()
print("BANC P5 (rendu au relâchement) : " + ("TOUT PASSE ✅" if ok else "ÉCHEC ✗"))
sys.exit(0 if ok else 1)
