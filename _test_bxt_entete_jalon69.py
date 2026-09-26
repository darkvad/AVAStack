# -*- coding: utf-8 -*-
"""Banc v2.38.3 — PARAMÈTRES BXT EXPLICITES + TRAÇABILITÉ DES OUTILS EXTERNES.

Décisions d'Alain (27/09/2026), après la mesure du moucheté bleu : ① la commande
BXT par défaut doit ÉCRIRE ses paramètres (`--ss 0.5 --ash -0.3 --sn 0.3`) —
« ne rien passer » n'est pas neutre, le CLI rc-astro applique alors ses propres
défauts (dont `--sn` = 0,50, responsable du moucheté : ×1,28 contre la vue live,
×0,48 avec 0,3) ; ② les commandes réellement utilisées doivent être consignées
dans l'en-tête du fichier, sinon rien ne dit de quelle chaîne il vient.

Vérifie :
  [1] la commande BXT par défaut porte les TROIS paramètres explicites ;
  [2] `App._entete_externe()` : mots-clés attendus depuis `ext_job` (job complet,
      job ANCIEN à 8 éléments, aucun job), valeurs exactes des commandes ;
  [3] le fichier LINÉAIRE écrit par « 💾 Enregistrer le résultat traité » PORTE
      ces mots-clés (relu par astropy, lecteur indépendant) ;
  [4] le « tel que vu » de la vue « traitée » les porte aussi (AVAVUE « ETIRE »),
      et celui de la vue « empilement » n'a AUCUN mot-clé AVA* (inchangé).

Exécution : python _test_bxt_entete_jalon69.py
"""
import os
import sys
import tempfile
import tkinter as tk

import numpy as np

import avastack.ui.app as ui
from avastack.external.detection import commande_par_defaut_bxt

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


print("=" * 78)
print("[1] la commande BXT par défaut écrit ses paramètres")
print("=" * 78)
cmd = commande_par_defaut_bxt()
print(f"    {cmd}")
for opt in ("--ss 0.5", "--ash -0.3", "--sn 0.3"):
    verifie(opt in cmd, f"la commande contient « {opt} » (explicite)")
verifie("{input}" in cmd and "{output}" in cmd and "--overwrite" in cmd,
        "placeholders et --overwrite préservés")

print()
print("=" * 78)
print("[2] en-tête construit depuis le job du ⚡")
print("=" * 78)
ui.CONFIG = {}
ui.sauver_config = lambda d: None
root = tk.Tk()
root.withdraw()
app = ui.App(root)
root.update_idletasks()

JOB = (True, '"graxpert.exe" "{input}" -cli -cmd background-extraction '
             '-correction Division -smoothing 0.8 -output "{outbase}"',
       True, '"graxpert.exe" "{input}" -cli -cmd denoising -strength 0.4 '
             '-output "{outbase}"',
       True, '"rc-astro.exe" bxt "{input}" -o "{output}" --overwrite '
             '--ss 0.5 --ash -0.3 --sn 0.3',
       "graxpert", 0.4, True, False, True, True, True, 0.6, 3.0)
app.ext_job = JOB
ent = app._entete_externe(42)
for cle, val in sorted(ent.items()):
    print(f"    {cle:<9} = {val}")
verifie("BXT" in ent["AVAOUTIL"] and "GraXpert gradient" in ent["AVAOUTIL"]
        and "GraXpert" in ent["AVAOUTIL"],
        "AVAOUTIL liste les outils réellement cochés")
verifie("--sn 0.3" in ent["AVACMDBX"],
        "AVACMDBX consigne la commande BXT AVEC ses paramètres")
verifie("strength 0.4" in ent["AVACMDDN"],
        "AVACMDDN consigne la commande de débruitage (force incluse)")
verifie("SCNR" in ent["AVAAPPLI"] and "fond neutre" in ent["AVAAPPLI"]
        and "chroma force 0.60 rayon 3.0px" in ent["AVAAPPLI"],
        "AVAAPPLI liste les corrections pré-étirement appliquées")
verifie(ent.get("AVAFRAME") == 42, "AVAFRAME = frames empilées au moment du ⚡")
app.ext_job = (True, "gx", False, "", False, "", "nlm", 0.5)   # job ancien
ent8 = app._entete_externe()
verifie(ent8["AVAOUTIL"] == "GraXpert gradient" and "AVACMDBX" not in ent8
        and ent8["AVAAPPLI"] == "aucune",
        "job ANCIEN (8 éléments) accepté : pas de commande inventée")
app.ext_job = None
verifie(app._entete_externe()["AVAOUTIL"] == "aucun",
        "aucun job : en-tête honnête (« aucun »), pas de plantage")

print()
print("=" * 78)
print("[3] le fichier LINÉAIRE du ⚡ porte ces mots-clés")
print("=" * 78)
from astropy.io import fits

tmp = tempfile.mkdtemp(prefix="avastack_j69_")
p_lin = os.path.join(tmp, "resultat_traite_lineaire.fits")
app.ext_job = JOB
app.proc_full = np.full((40, 60, 3), 0.05, np.float32)
app.proc_full[10:20, 10:20] = 3.0          # > 1 : force le BORNAGE du fichier
app.proc_entete = app._entete_externe(42)
ui.filedialog.asksaveasfilename = lambda **k: p_lin
ui.messagebox.showinfo = lambda *a, **k: None
ui.messagebox.showerror = lambda *a, **k: None
app._save_proc()
h = fits.open(p_lin)[0].header
verifie(os.path.isfile(p_lin), "le fichier a été écrit")
verifie("--sn 0.3" in str(h.get("AVACMDBX", "")),
        "AVACMDBX relu par astropy (lecteur indépendant)")
verifie(str(h.get("AVAOUTIL", "")).startswith("GraXpert gradient"),
        "AVAOUTIL relu")
verifie("AVASCALE" in h and float(np.max(fits.getdata(p_lin))) <= 1.0,
        "AVASCALE (facteur de bornage) ajouté par borner_lineaire, sans perdre "
        "les mots-clés de la chaîne externe")

print()
print("=" * 78)
print("[4] « tel que vu » : vue traitée OUI, vue empilement NON")
print("=" * 78)
p_tv = os.path.join(tmp, "telquevu_traitee.fits")
src = np.full((48, 64, 3), 0.05, np.float32)
src[16:32, 20:40] = 0.4
app.asseen_busy = True
app._save_asseen_thread(p_tv, "traitée", src.copy(), app._reglages_rendu(),
                        app._session)
h2 = fits.open(p_tv)[0].header
verifie(os.path.isfile(p_tv), "fichier « tel que vu » (vue traitée) écrit")
verifie("--sn 0.3" in str(h2.get("AVACMDBX", "")),
        "la vue traitée consigne la chaîne externe (AVACMDBX)")
verifie("ETIRE" in str(h2.get("AVAVUE", "")),
        "AVAVUE dit qu'il s'agit du résultat ÉTIRÉ (« tel que vu »)")
p_pile = os.path.join(tmp, "telquevu_pile.fits")
app.asseen_busy = True
app._save_asseen_thread(p_pile, "pile", src.copy(), app._reglages_rendu(),
                        app._session)
h3 = fits.open(p_pile)[0].header
ava = [k for k in h3.keys() if k.startswith("AVA")]
verifie(os.path.isfile(p_pile) and ava == [],
        f"vue « empilement » : AUCUN mot-clé AVA* (comportement d'origine) "
        f"— trouvés : {ava}")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
try:
    root.destroy()
except tk.TclError:
    pass
raise SystemExit(0 if ok else 1)
