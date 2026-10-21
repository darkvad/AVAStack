# -*- coding: utf-8 -*-
"""Banc du lot « COPIE → RÉFÉRENCE » (mémoire, branche `OptimisationUI`, 21/10/2026).

LE DÉFAUT MESURÉ : `App` mémorisait l'empilement COMPLET pour l'option « Rendu
pleine résolution » par `np.asarray(stack, np.float32).copy()` — une COPIE de
96,2 Mio (image 3856×2180×3 float32) que le stacker gardait DÉJÀ dans ses
propres caches. Le lot supprime la copie : `_stack_pleine_res` devient une
RÉFÉRENCE. Gain attendu : −96,2 Mio à la géométrie native, −85,0 Mio à la
géométrie RECADRÉE du run réel (7 425 000 px).

CE QUE CE BANC VERROUILLE — et ce qu'il ne suppose PAS
  [1] LE CONTRAT qui autorise la référence est VÉRIFIÉ sur les VRAIES classes :
      une image rendue par `LiveStacker.mean()` / `CompositeStacker.
      mean_avec_canaux()` n'est JAMAIS modifiée en place — elle reste identique
      AU BIT après de nouvelles frames, et ne partage aucune mémoire avec les
      accumulateurs réécrits ;
  [2] LE CHEMIN RÉEL de l'application (`App._pousser_rendu`, avec un vrai
      `CompositeStacker` aux réglages de `perf-7`) garde bien l'IMAGE DU STACKER
      elle-même (identité), et le rendu est IDENTIQUE AU BIT à celui de l'ancien
      comportement (copie) — les deux images sources sortent INTACTES ;
  [3] GARDE DE SOURCE : plus aucun `.copy()` sur la branche `stack`, et le repli
      « frame seule » (`stack is None`) garde, lui, une copie défensive (son
      tampon peut être réutilisé à la frame suivante) ;
  [4] MÉMOIRE : écart MESURÉ (comptage dédupliqué par `id()`) entre l'ancien
      comportement et le nouveau, + ce que libérer la copie REND au RSS à la
      géométrie native ;
  [5] `_vl_src` a DISPARU (écrit et jamais lu, il retenait l'image soumise : la
      décoche de l'option ne libérait donc pas réellement).

Nécessite un affichage (comme les bancs 68/69). Exécution :
    python bancs/_test_p1_memoire_reference.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent dans bancs/ et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
RACINE = None
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        RACINE = _d_banc
        _sys_banc.path.insert(0, str(_d_banc))
        break

import ast
import gc
import hashlib
import pathlib
import sys
import tkinter as tk

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.images as images
images.CFA_MODE = "Non"
import avastack.ui.app as ui
from avastack import perf
from avastack.processing.composition import CompositeStacker
from avastack.processing.display import DisplayProcessor
from avastack.processing.stacking import LiveStacker

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MIO = 1024.0 * 1024.0
ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def empreinte(img):
    """SHA-256 des octets de l'image — la preuve « AU BIT », pas une tolérance."""
    return hashlib.sha256(np.ascontiguousarray(img).tobytes()).hexdigest()


def brute(graine, h=96, w=128):
    """Brute synthétique déterministe : fond + des « objets » au-dessus du fond."""
    r = np.random.default_rng(graine)
    img = (0.02 + 0.05 * r.random((h, w))).astype(np.float32)
    img[20:26, 30:36] = 0.6
    img[60:64, 90:96] = 0.35
    return img


print("=" * 78)
print("[1] LE CONTRAT : l'image rendue par un stacker n'est JAMAIS réécrite")
print("=" * 78)

# --- 1a. Mono (LiveStacker) sans correction : l'image EST le cache du stacker
mono = LiveStacker((96, 128), k=3.0, warmup=2, method="kappa", window=4)
for i in range(4):
    mono.add(brute(i))
img = mono.mean()
verifie(img is not None, "LiveStacker.mean() rend une image")
verifie(mono._memo_moy is not None and mono._memo_moy[1] is img,
        "sans correction, l'image rendue EST celle que le stacker garde déjà "
        "(`_memo_moy`) → la garder par référence ne coûte RIEN")
h_img = empreinte(img)
for i in range(4, 8):
    mono.add(brute(i))
img2 = mono.mean()
verifie(img2 is not img,
        "une nouvelle frame rend un NOUVEAU tableau (jamais une écriture en place)")
verifie(empreinte(img) == h_img,
        "l'image GARDÉE est identique AU BIT après 4 frames de plus")
verifie(not np.shares_memory(img, mono.sum)
        and not np.shares_memory(img, mono.wsum),
        "…et elle ne partage aucune mémoire avec les accumulateurs réécrits "
        "(`sum`/`wsum`)")

# --- 1b. Mono AVEC correction : tableau FRAIS (non gardé) mais toujours immuable
mono.wb_auto = True
mono.wb_force = 1.0
for i in range(8, 10):
    mono.add(brute(i))
img3 = mono.mean()
h_img3 = empreinte(img3)
for i in range(10, 12):
    mono.add(brute(i))
mono.mean()
verifie(empreinte(img3) == h_img3,
        "corrections actives (tableau FRAIS, non gardé par le stacker) : la "
        "référence ne gagne rien mais ne perd rien — et reste immuable")

# --- 1c. Composite (réglages de `perf-7` : winsorized, Linear Fit, norm. commune)
comp_s = CompositeStacker("LRGB", k=3.0, method="winsorized", window=4)
comp_s.linear_fit = True
comp_s.linear_fit_mode = "offset"
comp_s.normalisation_commune = True
ROLES = ("L", "R", "G", "B")
for j, role in enumerate(ROLES):
    for i in range(4):
        comp_s.add(brute(100 + i + 10 * j).astype(np.float32), role=role)
comp, canaux = comp_s.mean_avec_canaux()
verifie(comp is not None and comp.ndim == 3 and comp.shape[-1] == 3,
        "CompositeStacker rend un composite COULEUR (H, W, 3)")
garde = ((comp_s._fit_cache is not None and comp_s._fit_cache[1][0] is comp)
         or (comp_s._memo_compo is not None and comp_s._memo_compo[1] is comp))
verifie(garde,
        "Linear Fit actif (config du run) : l'image rendue est le CACHE du "
        "stacker (`_fit_cache` ou `_memo_compo`)")
h_comp = empreinte(comp)
for role in ROLES:
    comp_s.add(brute(300).astype(np.float32), role=role)
comp2, _ = comp_s.mean_avec_canaux()
verifie(comp2 is not comp, "un composite plus récent est un AUTRE tableau")
verifie(empreinte(comp) == h_comp,
        "le composite GARDÉ reste identique AU BIT après une frame de plus")
verifie(not np.shares_memory(comp, comp_s.stackers["L"].sum),
        "…et ne partage rien avec les accumulateurs du stacker de rôle")



print("=" * 78)
print("[2] LE CHEMIN RÉEL : `App._pousser_rendu` garde l'IMAGE DU STACKER")
print("=" * 78)
ui.CONFIG = {}
ui.sauver_config = lambda d: None          # aucun fichier touché
root = tk.Tk()
root.withdraw()
app = ui.App(root)
root.update_idletasks()

app.stacker = comp_s                       # 4 rôles, réglages du run
app._mode_compo = True                     # comme en composition multi-rôles
app._compo_gains = {"R": 1.0, "G": 1.0, "B": 1.0}
app._compo_mode_l = comp_s.mode_l
app._compo_fusion_ha = None
app._dernier_st = None
app.pleine_res_ecran = True                # miroir lu par `_pleine_res_activee`
verifie(app._pleine_res_activee(), "option « Rendu pleine résolution » active")
while not app.q.empty():                   # file vide : on ne juge que ce lot
    app.q.get_nowait()

app._pousser_rendu()
ref = app._stack_pleine_res
verifie(ref is not None, "l'empilement complet est mémorisé")
verifie(ref is comp_s._fit_cache[1][0] or ref is comp_s._memo_compo[1],
        "c'est l'IMAGE DU STACKER elle-même (identité `is`), PAS une copie")
verifie(ref.dtype == np.float32 and ref.ndim == 3,
        "l'image mémorisée est bien le composite float32 (H, W, 3)")
verifie(empreinte(ref) == empreinte(comp_s.mean()),
        "…et son contenu est identique AU BIT au composite recalculé")

# --- la preuve qui compte : ANCIEN comportement (copie) contre NOUVEAU (référence)
src_ref = app._stack_pleine_res
src_copie = src_ref.copy()                 # ce que faisait `.copy()`
h_ref, h_copie = empreinte(src_ref), empreinte(src_copie)
verifie(h_ref == h_copie, "la copie d'hier et la référence d'aujourd'hui "
        "portent les mêmes octets")
# Deux `DisplayProcessor` NEUFS : aucun cache partagé (sinon la mémo du moteur
# STF servirait la première image et la comparaison ne prouverait rien).
d_ancien = DisplayProcessor()
d_nouveau = DisplayProcessor()
out_ancien = d_ancien.process(src_copie, live=True)
out_nouveau = d_nouveau.process(src_ref, live=True)
verifie(out_ancien.shape == out_nouveau.shape,
        f"même géométrie de rendu {out_nouveau.shape}")
verifie(empreinte(out_ancien) == empreinte(out_nouveau),
        "RENDU IDENTIQUE AU BIT (SHA-256) : ancien (copie) contre nouveau "
        "(référence)")
verifie(empreinte(src_ref) == h_ref and empreinte(src_copie) == h_copie,
        "les DEUX images sources sortent INTACTES du rendu (aucune écriture en "
        "place)")
verifie(d_ancien.last_lo == d_nouveau.last_lo
        and d_ancien.last_hi == d_nouveau.last_hi,
        "mêmes paramètres d'étirement (black/white) : le rendu n'a pas "
        "seulement l'air identique, il l'est")

# --- une frame de plus ne doit RIEN changer à ce qui est retenu (pas d'alias vif)
h_ref = empreinte(ref)
for role in ROLES:
    comp_s.add(brute(400).astype(np.float32), role=role)
comp_s.mean_avec_canaux()
verifie(app._stack_pleine_res is ref and empreinte(ref) == h_ref,
        "après une frame de plus, l'image retenue par l'interface est "
        "TOUJOURS la même, intacte")

print("=" * 78)
print("[3] GARDE DE SOURCE : plus de `.copy()` sur la branche `stack`")
print("=" * 78)


def affectations(rel, cible="_stack_pleine_res"):
    """Textes (`ast.unparse`) des affectations `self.<cible> = <appel>` d'un module."""
    src = pathlib.Path(RACINE, rel).read_text(encoding="utf-8")
    out = []
    for n in ast.walk(ast.parse(src)):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1
                and isinstance(n.targets[0], ast.Attribute)
                and n.targets[0].attr == cible
                and isinstance(n.value, ast.Call)):
            out.append(ast.unparse(n.value))
    return out


site_app = affectations("avastack/ui/app.py")
verifie(len(site_app) == 1
        and ".copy(" not in site_app[0] and "copy=True" not in site_app[0],
        f"`ui/app.py` → {site_app[0] if site_app else '—'} : AUCUNE copie")
site_worker = affectations("avastack/core/worker.py")
avec_copie = [t for t in site_worker if "copy=True" in t or ".copy(" in t]
sans_copie = [t for t in site_worker if t not in avec_copie]
verifie(len(site_worker) == 2,
        f"`core/worker.py` : {len(site_worker)} affectations (les deux branches)")
verifie(len(sans_copie) == 1 and "stack" in sans_copie[0],
        f"branche empilement → {sans_copie[0] if sans_copie else '—'} (référence)")
verifie(len(avec_copie) == 1 and "show" in avec_copie[0],
        f"repli frame seule → {avec_copie[0] if avec_copie else '—'} "
        "(copie défensive, tampon de la brute)")

print("=" * 78)
print("[4] MÉMOIRE : écart MESURÉ (dédupliqué par `id()`) et RSS rendu")
print("=" * 78)


class _Graphe:
    pass


def octets_retenus(cache, interface):
    """Octets retenus par un graphe (stacker + interface), dédupliqués par `id()`."""
    g = _Graphe()
    g.stackers = {"composite": cache}
    g.ui = interface
    return perf.taille_tableaux(g, profondeur=4)[0]


avant = octets_retenus(ref, {"stack_pleine_res": ref.copy()})   # hier
apres = octets_retenus(ref, {"stack_pleine_res": ref})          # aujourd'hui
ecart = avant - apres
verifie(ecart == int(ref.nbytes),
        f"écart mesuré = {ecart:,} o = nbytes de l'image ({ref.nbytes:,} o) : "
        "c'est EXACTEMENT la copie qui disparaît")
px_natif = 3856 * 2180
px_run = 7_425_000
octets_natif = px_natif * 3 * 4
octets_run = px_run * 3 * 4
verifie(abs(octets_natif / MIO - 96.2) < 0.05,
        f"géométrie NATIVE 3856×2180×3 float32 = {octets_natif / MIO:.1f} Mio "
        "(le « −96,2 Mio » de l'audit)")
verifie(abs(octets_run / MIO - 85.0) < 0.05,
        f"géométrie RECADRÉE du run (7 425 000 px) = {octets_run / MIO:.1f} Mio "
        "(chiffre à opposer au relevé réel)")
if perf.memoire_mo()[0] > 0:
    gc.collect()
    r0 = perf.memoire_mo()[0]
    grand = np.ones((2180, 3856, 3), np.float32)      # l'image, taille réelle
    r1 = perf.memoire_mo()[0]
    copie = grand.copy()                              # ce que faisait `.copy()`
    r2 = perf.memoire_mo()[0]
    del copie
    gc.collect()
    r3 = perf.memoire_mo()[0]
    print(f"  RSS : départ {r0:,.0f} · +image {r1 - r0:+,.0f} · +copie "
          f"{r2 - r1:+,.0f} · libération {r3 - r2:+,.0f} Mo")
    verifie((r2 - r3) > 0.8 * octets_natif / 1e6,
            f"libérer la copie REND {(r2 - r3):,.0f} Mo au processus (> 80 % de "
            f"{octets_natif / 1e6:.0f} Mo : les pages reviennent à l'OS)")
    del grand
    gc.collect()
else:
    print("  (sonde RSS indisponible : mesure directe sautée)")

print("=" * 78)
print("[5] `_vl_src` RETIRÉ : plus rien ne retient l'image soumise")
print("=" * 78)
d = DisplayProcessor()
verifie(not hasattr(d, "_vl_src"),
        "`DisplayProcessor` n'a plus d'attribut `_vl_src`")
src_txt = pathlib.Path(RACINE, "avastack/processing/display.py").read_text(
    encoding="utf-8")
attrs = {n.attr for n in ast.walk(ast.parse(src_txt))
         if isinstance(n, ast.Attribute)}
verifie("_vl_src" not in attrs,
        "aucun ACCÈS `._vl_src` ne subsiste dans le module (l'image soumise "
        "n'est plus retenue après un rendu)")
verifie("_vl_key" in attrs,
        "…mais `_vl_key` (clé des réglages du dernier calcul) est toujours là")

root.destroy()
print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)

