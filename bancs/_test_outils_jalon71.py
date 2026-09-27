# -*- coding: utf-8 -*-
"""Banc du jalon 71 : la DÉTECTION des outils externes dit ce qu'elle trouve.

Constat déclencheur (Alain, 27/09/2026, installateur Linux) : « la détection
de l'emplacement de GraXpert ne s'est pas faite (celle de rec-astro BlurX
oui) ». Ce banc rejoue la détection SANS installer aucun outil :

  [1] Linux : le binaire officiel s'appelle `GraXpert-linux` (archive
      `graxpert-linux-amd64.zip` décompressée, README officiel) — trouvé dans
      le dossier décompressé, dans `~/.local/GraXpert/`, dans `~/.local/bin/`,
      ou en AppImage exécutable. C'est exactement le cas qui échouait
      (comparaison sensible à la casse, binaire hors PATH).
  [2] Ordre de recherche : ini de Siril (`graxpert_path`) > variable
      `AVASTACK_GRAXPERT` > PATH > emplacements de l'OS > filtre `GraXpert*`.
  [3] macOS : l'exécutable du bundle (`GraXpert.app/Contents/MacOS/GraXpert`) ;
      Windows : `%LOCALAPPDATA%\\Programs\\GraXpert\\GraXpert.exe`.
  [4] `siril_ini` : lecture de l'ini de Siril (dossier par OS, clé cherchée
      sans groupe, déséchappement GKeyFile), valeur d'un fichier disparu
      ignorée ; `dossier_catalogues()` suit `catalogue_gaia_astro`.
  [5] `outil_manquant()` : commande nue/chemin existant/chemin disparu/PATH.
  [6] UI réelle : la ligne d'état affiche « ⚠ … introuvable » au démarrage
      d'une session dont la commande persistée n'a plus d'outil (le cas
      Linux figé dans config.json), puis « ✔ … » après le bouton « … ».

Exécution : python bancs/_test_outils_jalon71.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import shutil
import sys
import tempfile

from avastack import siril_ini as ini_mod
from avastack import config as config_mod
from avastack import catalogues as cat_mod
from avastack.external import detection as det_mod
from avastack.external import live as live_mod

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


TMP = tempfile.mkdtemp(prefix="banc71_")
HOME = os.path.join(TMP, "home")
CONF = os.path.join(TMP, "conf")
DATA = os.path.join(TMP, "data")
for _d in (HOME, CONF, DATA):
    os.makedirs(_d)

# --- isolement de l'environnement (rien de réel n'est touché) ----------------
_ENV_SAUVE = {k: os.environ.get(k) for k in
              ("HOME", "USERPROFILE", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
               "LOCALAPPDATA", "APPDATA", "PATH", "AVASTACK_GRAXPERT",
               "AVASTACK_RC_ASTRO")}
_CONFIG_SAUVE = dict(config_mod.CONFIG)
_WHICH_SAUVE = det_mod.shutil.which
_FLAGS_SAUVE = (det_mod.IS_WINDOWS, det_mod.IS_MACOS,
                ini_mod.IS_WINDOWS, ini_mod.IS_MACOS,
                config_mod.IS_WINDOWS, config_mod.IS_MACOS,
                cat_mod.IS_WINDOWS, cat_mod.IS_MACOS)


def simule_os(windows=False, macos=False):
    """Bascule la logique d'OS des modules de détection, HOME/XDG isolés."""
    for k in ("HOME", "USERPROFILE", "AVASTACK_GRAXPERT", "AVASTACK_RC_ASTRO"):
        os.environ.pop(k, None)
    os.environ["HOME"] = HOME
    os.environ["USERPROFILE"] = HOME
    os.environ["XDG_CONFIG_HOME"] = CONF
    os.environ["XDG_DATA_HOME"] = DATA
    os.environ["LOCALAPPDATA"] = HOME
    os.environ["APPDATA"] = HOME
    det_mod.IS_WINDOWS = ini_mod.IS_WINDOWS = config_mod.IS_WINDOWS = windows
    det_mod.IS_MACOS = ini_mod.IS_MACOS = config_mod.IS_MACOS = macos
    cat_mod.IS_WINDOWS, cat_mod.IS_MACOS = windows, macos
    det_mod.shutil.which = lambda nom: None      # « hors PATH » par défaut


def restaure():
    det_mod.shutil.which = _WHICH_SAUVE
    for k, v in _ENV_SAUVE.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    config_mod.CONFIG.clear()
    config_mod.CONFIG.update(_CONFIG_SAUVE)
    (det_mod.IS_WINDOWS, det_mod.IS_MACOS,
     ini_mod.IS_WINDOWS, ini_mod.IS_MACOS,
     config_mod.IS_WINDOWS, config_mod.IS_MACOS,
     cat_mod.IS_WINDOWS, cat_mod.IS_MACOS) = _FLAGS_SAUVE


def faux_binaire(*morceaux):
    """Pose un FAUX exécutable (fichier vide + droit d'exécution) et renvoie
    son chemin — aucun outil réel n'est requis pour ce banc."""
    p = os.path.join(*morceaux)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\n")                 # contenu jamais exécuté
    try:
        os.chmod(p, 0o755)
    except OSError:
        pass
    return p


def chemin_dans(commande):
    """Chemin en tête d'une commande entre guillemets, ou None."""
    c = commande.strip()
    return c[1:c.find('"', 1)] if c.startswith('"') else None


def meme(a, b):
    """Les deux chemins désignent-ils le MÊME fichier ?

    Sous Windows le système de fichiers ignore la casse (le fichier
    `GraXpert.exe` est bien trouvé sous le nom `graxpert.exe`) et le chemin
    retourné est celui DEMANDÉ — d'où `normcase`, qui ne change rien sous
    Linux (où la casse, elle, compte)."""
    return bool(a) and bool(b) and os.path.normcase(os.path.normpath(a)) == \
        os.path.normcase(os.path.normpath(b))


print("[1] LINUX : le binaire officiel s'appelle GraXpert-linux")
simule_os()
verifie("GraXpert-linux" in det_mod._noms_graxpert(),
        f"noms cherchés sous Linux : {det_mod._noms_graxpert()}")

# Cas d'Alain : archive décompressée dans le dossier personnel, hors PATH.
exe1 = faux_binaire(HOME, "GraXpert-linux-amd64", "GraXpert-linux")
verifie(meme(det_mod.chemin_graxpert(), exe1),
        f"dossier décompressé : {os.path.basename(os.path.dirname(exe1))}/"
        f"{os.path.basename(exe1)}")
verifie(meme(chemin_dans(det_mod.commande_par_defaut_graxpert()), exe1)
        and meme(chemin_dans(det_mod.commande_par_defaut_graxpert_dn()), exe1),
        "gradient ET débruitage partent du même chemin détecté")
os.remove(exe1)

# Dossier `~/.local/GraXpert/` (disposition « un dossier par outil »).
exe2 = faux_binaire(HOME, ".local", "GraXpert", "GraXpert")
verifie(meme(det_mod.chemin_graxpert(), exe2), "~/.local/GraXpert/GraXpert")
os.remove(exe2)

# Binaire posé dans le `bin` utilisateur (`~/.local/bin`, hors PATH ici).
exe3 = faux_binaire(HOME, ".local", "bin", "graxpert")
verifie(meme(det_mod.chemin_graxpert(), exe3), "~/.local/bin/graxpert")
os.remove(exe3)

# AppImage déposée dans ~/Applications (fichier exécutable accepté tel quel).
exe4 = faux_binaire(HOME, "Applications", "GraXpert-3.1.0.AppImage")
verifie(meme(det_mod.chemin_graxpert(), exe4),
        "AppImage exécutable dans ~/Applications")

print("[2] Ordre de recherche : Siril > env > PATH > OS > filtre")
# PATH : une piste moins explicite doit CÉDER devant celles d'avant.
det_mod.shutil.which = lambda nom: ("/faux/bin/GraXpert-linux"
                                    if nom == "GraXpert-linux" else None)
verifie(meme(det_mod.chemin_graxpert(), "/faux/bin/GraXpert-linux"),
        "PATH utilisé quand aucune piste plus explicite n'existe")
os.environ["AVASTACK_GRAXPERT"] = exe4
verifie(meme(det_mod.chemin_graxpert(), exe4),
        "variable AVASTACK_GRAXPERT prioritaire sur le PATH")
os.environ["AVASTACK_GRAXPERT"] = os.path.join(TMP, "absent.exe")
verifie(meme(det_mod.chemin_graxpert(), "/faux/bin/GraXpert-linux"),
        "variable d'environnement menant à un fichier ABSENT : ignorée")
os.remove(exe4)

print("[3] macOS (bundle) et Windows (Programs)")
simule_os(macos=True)
exe5 = faux_binaire(HOME, "Applications", "GraXpert.app", "Contents", "MacOS",
                    "GraXpert")
verifie(meme(det_mod.chemin_graxpert(), exe5),
        "macOS : GraXpert.app/Contents/MacOS/GraXpert")
os.remove(exe5)
simule_os(windows=True)
exe6 = faux_binaire(HOME, "Programs", "GraXpert", "GraXpert.exe")
verifie(meme(det_mod.chemin_graxpert(), exe6),
        "Windows : %LOCALAPPDATA%\\Programs\\GraXpert\\GraXpert.exe")
verifie("graxpert.exe" in det_mod._noms_graxpert(),
        f"Windows : nom du binaire {det_mod._noms_graxpert()}")
os.remove(exe6)

print("[4] INI DE SIRIL : graxpert_path, puis catalogue_gaia_astro")


def ecrit_ini(lignes):
    """Écrit un ini FACTICE à l'emplacement Linux simulé (GKeyFile ÉCHAPPE
    les antislashs : c'est ce que le lecteur doit défaire)."""
    p = os.path.join(CONF, "siril", "config.1.4.ini")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes) + "\n")
    return p


simule_os()
verifie(ini_mod.dossiers_config_siril()[0] == os.path.join(CONF, "siril"),
        f"dossier d'ini Linux : {ini_mod.dossiers_config_siril()[0]}")
exe7 = faux_binaire(HOME, "GraXpert-linux-amd64", "GraXpert-linux")
ini7 = ecrit_ini(["[core]",
                  "graxpert_path=" + exe7.replace(os.sep, os.sep * 2)])
verifie(ini_mod.lire_cle(ini_mod.CLE_GRAXPERT) == exe7,
        "clé lue, antislashs déséchappés (C:\\\\Users → C:\\Users)")
det_mod.shutil.which = lambda nom: "/faux/bin/GraXpert-linux"
verifie(meme(det_mod.chemin_graxpert(), exe7),
        "l'ini de Siril prime sur le PATH (choix explicite de l'utilisateur)")
os.rename(ini7, ini7 + ".bak")
verifie(ini_mod.lire_cle(ini_mod.CLE_GRAXPERT) is None,
        "ini absent : lecture muette (aucune exception)")
os.rename(ini7 + ".bak", ini7)
os.remove(exe7)
verifie(ini_mod.chemin_fichier(ini_mod.CLE_GRAXPERT) is None
        and ini_mod.lire_chemin(ini_mod.CLE_GRAXPERT) == exe7,
        "valeur pointant un fichier DISPARU : écartée (mais relue telle quelle)")
verifie(meme(det_mod.chemin_graxpert(), "/faux/bin/GraXpert-linux"),
        "… et la détection se rabat alors sur le PATH")
ecrit_ini(["[un_groupe_quelconque]",
           "graxpert_path=" + exe7.replace(os.sep, os.sep * 2)])
verifie(ini_mod.lire_cle(ini_mod.CLE_GRAXPERT) == exe7,
        "clé trouvée quel que soit le GROUPE (nom de clé unique)")
simule_os(macos=True)
verifie("org.free-astro.Siril" in ini_mod.dossiers_config_siril()[0],
        "dossier d'ini macOS : ~/Library/Application Support/org.free-astro.Siril/siril")
simule_os(windows=True)
verifie(ini_mod.dossiers_config_siril()[0] == os.path.join(HOME, "siril"),
        "dossier d'ini Windows : %LOCALAPPDATA%\\siril")

# --- le dossier des CATALOGUES suit `catalogue_gaia_astro` -------------------
simule_os()
cible = os.path.join(DATA, "siril")
os.makedirs(cible, exist_ok=True)
cat_fictif = os.path.join(cible, "siril_cat_healpix8_astro.dat")
with open(cat_fictif, "wb") as f:
    f.write(b"faux catalogue du banc")
ecrit_ini(["[core]",
           "catalogue_gaia_astro=" + cat_fictif.replace(os.sep, os.sep * 2),
           "catalogue_gaia_photo=" + os.path.join(
               cible, "siril_cat1_healpix8_xpsamp").replace(os.sep, os.sep * 2)])
config_mod.CONFIG.pop("chemin_catalogues", None)
verifie(cat_mod.dossier_catalogues() == cible,
        f"dossier des catalogues DÉSIGNÉ par Siril : {cat_mod.dossier_catalogues()}")

print("[5] outil_manquant : l'échec est DIT avant l'exécution")
import numpy as np                              # noqa: E402
simule_os()
exe8 = faux_binaire(HOME, "GraXpert-linux-amd64", "GraXpert-linux")
cmd8 = f'"{exe8}" "{{input}}" -cli -output "{{outbase}}"'
verifie(live_mod.binaire_de(cmd8) == exe8,
        "binaire isolé en tête de commande (guillemets respectés)")
verifie(live_mod.outil_manquant(cmd8) == "",
        "chemin EXISTANT : aucun message (la commande passe)")
os.remove(exe8)
m8 = live_mod.outil_manquant(cmd8)
verifie(m8.startswith("exécutable introuvable"),
        f"chemin DISPARU : « {m8[:42]}… »")
m9 = live_mod.outil_manquant("graxpert {input} -cli -output {outbase}")
verifie("PATH" in m9, f"binaire nu hors PATH : « {m9} »")
det_mod.shutil.which = lambda nom: "/faux/bin/graxpert" if nom == "graxpert" \
    else None
verifie(live_mod.outil_manquant("graxpert {input} -cli -output {outbase}") == "",
        "binaire nu PRÉSENT dans le PATH : aucun message")
verifie(live_mod.outil_manquant("") == "commande absente",
        "commande vide : cas signalé sans exception")
det_mod.shutil.which = lambda nom: None          # aucun outil : cas d'Alain
img, err = live_mod.appliquer(np.zeros((4, 4)), "graxpert {input} -cli "
                                                "-output {outbase}")
verifie("introuvable" in err and img.shape == (4, 4),
        "GraXpert live sur outil absent : erreur DITE, aucune exécution lancée")

# Re-détection d'une commande FIGÉE : le binaire change, les OPTIONS restent.
cible2 = faux_binaire(HOME, "GraXpert-linux-amd64", "GraXpert-linux")
figee = (f'"{os.path.join(HOME, "disparu2", "GraXpert-linux")}" "{{input}}" '
         '-cli -cmd background-extraction -correction Division -smoothing 0.8 '
         '-output "{outbase}"')
fusion = live_mod.remplacer_binaire(figee,
                                    det_mod.commande_par_defaut_graxpert())
verifie(meme(live_mod.binaire_de(fusion), cible2)
        and "-smoothing 0.8" in fusion and "-correction Division" in fusion
        and "disparu2" not in fusion,
        "commande figée : chemin remplacé, RÉGLAGES de l'utilisateur conservés")
os.remove(cible2)

print("[6] UI : l'état de la détection est AFFICHÉ (constat Linux rejoué)")
import tkinter as tk                            # noqa: E402
import avastack.ui.app as app_mod               # noqa: E402

app_mod.CONFIG = config_mod.CONFIG              # le dict que lit la config
_SAUVER = app_mod.sauver_config
app_mod.sauver_config = lambda *a, **k: None     # JAMAIS le vrai config.json
_ASK = app_mod.filedialog.askopenfilename
absente = os.path.join(HOME, "disparu", "GraXpert-linux")
config_mod.CONFIG["cmd_graxpert"] = f'"{absente}" "{{input}}" -cli'
config_mod.CONFIG["cmd_bxt"] = f'"{absente}" bxt "{{input}}" -o "{{output}}"'
config_mod.CONFIG["cmd_graxpert_dn"] = (f'"{absente}" "{{input}}" '
                                        '-cmd denoising -strength 0.9 '
                                        '-output "{outbase}"')

root = tk.Tk()
root.withdraw()
ui = app_mod.App(root)
verifie(absente not in ui.var_cmd_graxpert.get(),
        "commande persistée SANS outil : re-détectée à l'ouverture "
        "(plus de valeur figée)")
verifie("-strength 0.9" in ui.var_cmd_graxpert_dn.get()
        and absente not in ui.var_cmd_graxpert_dn.get(),
        "débruitage figé : chemin re-détecté, curseur -strength 0.9 CONSERVÉ")
verifie("introuvable" in ui.lbl_etat_graxpert.cget("text"),
        f"ligne GraXpert : « {ui.lbl_etat_graxpert.cget('text')} »")
verifie("introuvable" in ui.lbl_etat_bxt.cget("text"),
        f"ligne BlurXTerminator : « {ui.lbl_etat_bxt.cget('text')} »")

b2 = faux_binaire(HOME, "GraXpert-linux-amd64", "GraXpert-linux")
app_mod.filedialog.askopenfilename = lambda *a, **k: b2
ui._pick_exe(ui.var_cmd_graxpert)
verifie(ui.var_cmd_graxpert.get().startswith(f'"{b2}"')
        and "-cli" in ui.var_cmd_graxpert.get(),
        "bouton « … » : chemin en tête, options conservées")
verifie("✔" in ui.lbl_etat_graxpert.cget("text")
        and b2 in ui.lbl_etat_graxpert.cget("text"),
        f"ligne d'état après choix : « {ui.lbl_etat_graxpert.cget('text')} »")
app_mod.filedialog.askopenfilename = _ASK

sauve = {}


def faux_sauver_config(d):
    sauve.clear()
    sauve.update(d)


app_mod.sauver_config = faux_sauver_config
ui._sauver_config_app()
verifie(sauve.get("cmd_graxpert", "").startswith(f'"{b2}"'),
        "commande AVEC outil : persistée comme avant (non-régression)")
verifie("cmd_bxt" not in sauve,
        "commande SANS outil : plus JAMAIS persistée (l'ancienne version la "
        "figeait à vie)")

root.destroy()
app_mod.sauver_config = _SAUVER
restaure()
shutil.rmtree(TMP, ignore_errors=True)

print("\nBANC JALON 71 (détection des outils externes) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)

