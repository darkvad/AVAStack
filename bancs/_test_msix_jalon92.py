# -*- coding: utf-8 -*-
"""Banc du jalon 92 : paquet MSIX (chantier « Microsoft Store »).

POURQUOI CE BANC : le Store distribue des MSIX, et un MSIX est IMMUABLE — il
faut donc y emballer l'application GELÉE. Ce banc vérifie tout ce qui est
vérifiable SANS soumettre au Store :

  [1] la VERSION MSIX : « 2.49.0 » → « 2.49.0.0 » (quatre nombres exigés) ;
  [2] le MODÈLE de manifeste porte tous les jetons, une application de BUREAU
      pleine confiance (Windows.FullTrustApplication + rescap:runFullTrust) ;
  [3] les VIGNETTES sont générées depuis la VRAIE icône (assets/avastack.png)
      aux tailles EXACTES attendues par le manifeste ;
  [4] MakeAppx / signtool sont trouvables (Windows SDK) ;
  [5] le manifeste ÉCRIT ne contient plus aucun jeton et porte l'identité ;
  [6] BOUT EN BOUT : MakeAppx emballe un VRAI .msix (faux paquet léger) et
      l'archive contient le manifeste, les types, le blockmap et les vignettes.

Autonome : ne construit PAS le gros paquet (250 Mo) — juste un faux paquet.
Exécution : python bancs/_test_msix_jalon92.py
"""
import sys as _sys_banc, pathlib as _pl_banc
_RACINE = None
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _RACINE = str(_d_banc)
        _sys_banc.path.insert(0, _RACINE)
        break
import importlib.util
import os
import shutil
import struct
import sys
import tempfile
import zipfile

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


DOSSIER = os.path.join(_RACINE, "installer", "windows", "msix")
GABARIT = os.path.join(DOSSIER, "AppxManifest.xml.template")
_spec = importlib.util.spec_from_file_location(
    "build_msix", os.path.join(DOSSIER, "build_msix.py"))
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

# ==================================== [1] version MSIX
print("[1] version MSIX : QUATRE nombres (exige par le schema AppX)")
verifie(M.version_msix("2.49.0") == "2.49.0.0", "2.49.0 -> 2.49.0.0")
verifie(M.version_msix("1.2") == "1.2.0.0", "1.2 -> 1.2.0.0")
verifie(M.version_msix("10.20.30.40") == "10.20.30.40", "4 nombres conserves")

# ==================================== [2] modele de manifeste
print("[2] le modele porte tous les jetons et une appli de BUREAU pleine confiance")
with open(GABARIT, encoding="utf-8") as f:
    gabarit = f.read()
JETONS = ("__NAME__", "__PUBLISHER__", "__VERSION__", "__DISPLAY_NAME__",
          "__PUBLISHER_DISPLAY__", "__DESCRIPTION__", "__EXE__")
manquants = [j for j in JETONS if j not in gabarit]
verifie(not manquants, "jetons tous presents (manquants : %r)" % (manquants,))
verifie("Windows.FullTrustApplication" in gabarit,
        "EntryPoint = Windows.FullTrustApplication (appli de bureau)")
verifie("runFullTrust" in gabarit and "restrictedcapabilities" in gabarit,
        "capacite rescap:runFullTrust declaree (namespace rescap)")
verifie("Identity" in gabarit and "ProcessorArchitecture" in gabarit,
        "Identity + architecture declarees")

# ==================================== [3] vignettes depuis la vraie icone
print("[3] vignettes : la VRAIE icone (assets/avastack.png) sert de source")
vdir = tempfile.mkdtemp(prefix="banc92_vig_")
info, source = M.faire_vignettes(vdir)
verifie(info == "photo",
        "source REELLE utilisee (info=%r, %s)" % (info, os.path.basename(source)))
from PIL import Image                                     # noqa: E402
for nom, larg, haut in M.VIGNETTES:
    p = os.path.join(vdir, nom)
    taille = None
    if os.path.isfile(p):
        with Image.open(p) as im:
            taille = im.size
    verifie(taille == (larg, haut),
            "%s : PNG %dx%d (obtenu %s)" % (nom, larg, haut, taille))
shutil.rmtree(vdir, ignore_errors=True)

# ==================================== [4] outils du Windows SDK
print("[4] MakeAppx / signtool trouvables (Windows SDK)")
makeappx = M.trouver_outil("makeappx.exe")
signtool = M.trouver_outil("signtool.exe")
verifie(bool(makeappx), "MakeAppx : %s" % makeappx)
verifie(bool(signtool), "signtool : %s" % signtool)

# ==================================== [5] manifeste ecrit SANS jeton
print("[5] le manifeste ECRIT ne contient plus aucun jeton")
bac = tempfile.mkdtemp(prefix="banc92_")
paquet = os.path.join(bac, "faux_paquet")
os.makedirs(os.path.join(paquet, "_internal"))
open(os.path.join(paquet, M.EXE_DEFAUT), "wb").close()
with open(os.path.join(paquet, "_internal", "x.txt"), "w", encoding="utf-8") as f:
    f.write("x\n")
staging = os.path.join(bac, "staging")
remplacements = {"__NAME__": "Banc92.Test", "__PUBLISHER__": "CN=Banc92",
                 "__VERSION__": "2.49.0.0", "__DISPLAY_NAME__": "Banc",
                 "__PUBLISHER_DISPLAY__": "Banc", "__DESCRIPTION__": "desc",
                 "__EXE__": M.EXE_DEFAUT}
manifeste, _ = M.preparer_staging(paquet, staging, GABARIT, remplacements)
with open(manifeste, encoding="utf-8") as f:
    xml = f.read()
restants = [j for j in JETONS if j in xml]
verifie(not restants, "aucun jeton restant (restants : %r)" % (restants,))
verifie('Name="Banc92.Test"' in xml and 'Publisher="CN=Banc92"' in xml
        and 'Version="2.49.0.0"' in xml,
        "identite (Name / Publisher / Version) ecrite dans le manifeste")
verifie(os.path.isfile(os.path.join(staging, "Assets",
                                    "Square150x150Logo.png")),
        "vignettes ecrites dans le dossier de staging")
verifie(os.path.isfile(os.path.join(staging, "_internal", "x.txt")),
        "le staging copie bien le _internal du paquet gele")

# ==================================== [6] bout en bout : MakeAppx
print("[6] bout en bout : MakeAppx produit un VRAI .msix")
if makeappx:
    cible = os.path.join(bac, "banc92.msix")
    code, sortie = M.empaqueter(makeappx, staging, cible)
    verifie(code == 0 and os.path.isfile(cible),
            "MakeAppx pack -> code %s (%s)" % (code, os.path.basename(cible)))
    if os.path.isfile(cible):
        with zipfile.ZipFile(cible) as z:
            noms = z.namelist()
        for attendu in ("AppxManifest.xml", "[Content_Types].xml",
                        "AppxBlockMap.xml", "Assets/StoreLogo.png",
                        M.EXE_DEFAUT):
            verifie(attendu in noms, "le .msix contient %s" % attendu)
else:
    print("  (MakeAppx absent : section 6 ignoree)")

shutil.rmtree(bac, ignore_errors=True)

# ==================================== [7] icone de FENETRE (barre de titres)
print("[7] l'icone de FENETRE est posable (barre de titres + barre des taches)")
import tkinter as tk                                       # noqa: E402
from avastack import ressources                            # noqa: E402
racine_tk = tk.Tk()
racine_tk.withdraw()
try:
    posee = ressources.poser_icone_fenetre(racine_tk)
    verifie(posee, "poser_icone_fenetre -> True (icone %s)"
            % os.path.basename(ressources.FICHIER_ICO))
    verifie(os.path.isfile(ressources.chemin(ressources.FICHIER_ICO)),
            "l'icone .ico existe : %s" % ressources.DOSSIER)
    verifie(os.path.isfile(ressources.chemin(ressources.FICHIER_PNG)),
            "la source .png des vignettes existe")
finally:
    racine_tk.destroy()

print("")
print("TOUT AU VERT" if ok else "DES ÉCHECS")
sys.exit(0 if ok else 1)