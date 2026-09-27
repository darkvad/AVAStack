# -*- coding: utf-8 -*-
"""Banc du jalon 70 : les DONNÉES de l'astrométrie sont dites et téléchargeables.

Constat déclencheur (Alain, 27/09/2026, installateur Linux) : « l'astrométrie
ne trouve pas de résultat… et ça échoue en silence ». Ce banc rejoue la
mécanique SANS réseau et SANS catalogue réel :

  [1] `dossiers_siril()` couvre le dossier LINUX de Siril
      (`~/.local/share/siril`, doc Siril 1.4.4) et suit `XDG_DATA_HOME` ; sous
      Windows, `%LOCALAPPDATA%\\Siril` reste le premier candidat.
  [2] `dossier_catalogues()` : surcharge de config > dossier qui contient DÉJÀ
      des `siril_cat*` > dossier `catalogues` d'AVAStack (repli, créé).
  [3] `SuiviAstrometrie` : « catalogue absent » est une cause de DONNÉES → UN
      seul essai (plus 20 pour rien), `raison_attente()` le dit, et les essais
      REPARTENT tout seuls dès que le catalogue apparaît.
  [4] UI réelle : la ligne « Catalogues » montre le dossier utilisé et l'absence
      du catalogue ; le bouton ⬇ passe par un THREAD + une file (téléchargeur
      FACTICE), la progression s'affiche, la fin réactive le bouton.

Exécution : python bancs/_test_catalogues_jalon70.py
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
import time

import numpy as np

from avastack import catalogues as cat_mod
from avastack import config as config_mod
from avastack.catalogues import solveur as solveur_mod
from avastack.catalogues import telechargeur as dl_mod
from avastack.processing.astrometrie import SuiviAstrometrie

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


TMP = tempfile.mkdtemp(prefix="banc70_")
DATA = os.path.join(TMP, "data")
CONF = os.path.join(TMP, "conf")
os.makedirs(DATA)
os.makedirs(CONF)

# --- isolement de l'environnement (rien de réel n'est touché) ----------------
_ENV_SAUVE = {k: os.environ.get(k) for k in
              ("HOME", "USERPROFILE", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
               "LOCALAPPDATA")}
_CONFIG_SAUVE = dict(config_mod.CONFIG)
_FLAGS_SAUVE = (cat_mod.IS_WINDOWS, cat_mod.IS_MACOS,
                config_mod.IS_WINDOWS, config_mod.IS_MACOS)


def simule_linux():
    """Bascule la logique d'OS en Linux, avec HOME/XDG dans le dossier du banc."""
    os.environ["HOME"] = TMP
    os.environ["USERPROFILE"] = TMP
    os.environ["XDG_DATA_HOME"] = DATA
    os.environ["XDG_CONFIG_HOME"] = CONF
    cat_mod.IS_WINDOWS = config_mod.IS_WINDOWS = False
    cat_mod.IS_MACOS = config_mod.IS_MACOS = False


def restaure():
    for k, v in _ENV_SAUVE.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    config_mod.CONFIG.clear()
    config_mod.CONFIG.update(_CONFIG_SAUVE)
    (cat_mod.IS_WINDOWS, cat_mod.IS_MACOS,
     config_mod.IS_WINDOWS, config_mod.IS_MACOS) = _FLAGS_SAUVE


def catalogue_factice(dossier, nom="siril_cat_healpix8_astro.dat"):
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, nom)
    with open(chemin, "wb") as f:
        f.write(b"\x00" * 64)          # contenu factice : seul le NOM compte
    return chemin


print("[1] dossiers_siril() : chemins par OS")
simule_linux()
dossiers = cat_mod.dossiers_siril()
verifie(os.path.join(DATA, "siril") in dossiers,
        f"XDG_DATA_HOME/siril présent ({dossiers[0] if dossiers else '—'})")
verifie(any(d.endswith(os.path.join(".local", "share", "siril"))
            for d in dossiers),
        "repli ~/.local/share/siril présent (dossier Linux de Siril)")
verifie(any(d.endswith(os.path.join(".local", "share", "kstars"))
            for d in dossiers),
        "dossier KStars conservé (autres catalogues)")
cat_mod.IS_WINDOWS = config_mod.IS_WINDOWS = True
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "appdata")
verifie(cat_mod.dossiers_siril()[0] ==
        os.path.join(os.path.join(TMP, "appdata"), "Siril"),
        "Windows : %LOCALAPPDATA%\\Siril en PREMIER candidat")

print("[2] dossier_catalogues() : surcharge > Siril > repli AVAStack")
simule_linux()
config_mod.CONFIG.pop("chemin_catalogues", None)
verifie(cat_mod.dossier_catalogues() == os.path.join(CONF, "AVAStack",
                                                     "catalogues"),
        "sans rien : dossier `catalogues` d'AVAStack (repli, créé)")
verifie(os.path.isdir(cat_mod.dossier_catalogues()),
        "le dossier de repli existe (cible du téléchargement)")
siril = os.path.join(DATA, "siril")
catalogue_factice(siril)
verifie(cat_mod.dossier_catalogues() == siril,
        f"catalogue présent → dossier de Siril retenu ({os.path.basename(siril)})")
verifie(cat_mod.chemin_catalogue_astro() is not None,
        "chemin_catalogue_astro() trouve le fichier (nom reconnu)")
autre = os.path.join(TMP, "mes_catalogues")
os.makedirs(autre)
config_mod.CONFIG["chemin_catalogues"] = autre
verifie(cat_mod.dossier_catalogues() == autre,
        "la surcharge `chemin_catalogues` PRIME (clé réellement honorée)")
config_mod.CONFIG["chemin_catalogues"] = os.path.join(TMP, "inexistant")
verifie(cat_mod.dossier_catalogues() == siril,
        "surcharge vers un dossier absent : ignorée (repli sur Siril)")

print("[3] SuiviAstrometrie : cause de DONNÉES = essais arrêtés, puis reprise")
# On retire le catalogue factice : c'est EXACTEMENT l'état de la machine Linux
# d'Alain le 27/09/2026 (aucun catalogue, aucun ASTAP).
config_mod.CONFIG.pop("chemin_catalogues", None)
os.remove(cat_mod.chemin_catalogue_astro())
verifie(cat_mod.chemin_catalogue_astro() is None,
        "catalogue retiré : plus aucun trouvé (dossier de repli vide)")

appels = {"n": 0}


def solveur_sans_catalogue(img, ra0, dec0, champ, dossier=None, limmag=None):
    """Comme le VRAI solveur : il nomme le dossier RÉELLEMENT cherché (défaut
    compris), ce qui est précisément ce que l'utilisateur doit lire."""
    appels["n"] += 1
    return None, {}, (f"{solveur_mod.MSG_CATALOGUE_ABSENT} dans "
                      f"{dossier or cat_mod.dossier_catalogues()}")


class FauxWcs:
    """WCS minimal : ce que `texte_resume()` lit après une résolution."""
    echelle_arcsec = 1.5
    angle_deg = 0.0


suivi = SuiviAstrometrie(solveur=solveur_sans_catalogue)
suivi.indice(10.68, 41.27, 2.6)
img = np.zeros((64, 96), dtype=np.float32)
verifie(suivi.peut_essayer(30), "premier essai autorisé (30 frames)")
okk, msg = suivi.resoudre_sur(img, n_frames=30)
verifie(not okk and suivi.donnees_absentes,
        f"échec marqué « données absentes » (« {msg[:40]}… »)")
verifie(suivi.essais == 1 and appels["n"] == 1,
        f"UN seul essai, UN seul appel du solveur ({suivi.essais}/{appels['n']})")
verifie(not suivi.peut_essayer(300) and not suivi.peut_essayer(10 ** 6),
        "plus aucun essai tant que le catalogue manque (même sur 1 M frames)")
raison = suivi.raison_attente()
verifie("DONNÉES MANQUANTES" in raison
        and os.path.basename(cat_mod.dossier_catalogues()) in raison,
        f"la raison dit la DONNÉE et le dossier cherché (« {raison[:58]}… »)")

catalogue_factice(cat_mod.dossier_catalogues())
verifie(suivi.peut_essayer(300) and not suivi.donnees_absentes,
        "catalogue arrivé : les essais REPARTENT seuls (sans redémarrage)")

suivi._solveur = lambda *a, **k: (FauxWcs(), {"n_etoiles_img": 40}, "")
okk, msg = suivi.resoudre_sur(img, n_frames=300)
verifie(okk and suivi.resolu and not suivi.donnees_absentes,
        f"résolution réussie ensuite : « {msg[:44]}… »")

print("[4] UI : ligne « Catalogues » et téléchargement (factice, sans réseau)")
os.remove(cat_mod.chemin_catalogue_astro())      # retour à l'état « rien »
import tkinter as tk                             # noqa: E402
import avastack.ui.app as app_mod                # noqa: E402

app_mod.CONFIG = config_mod.CONFIG               # le dict que lit la config
_SAUVER = app_mod.sauver_config
app_mod.sauver_config = lambda *a, **k: None     # JAMAIS le vrai config.json
_ASK = app_mod.filedialog.askdirectory

root = tk.Tk()
root.withdraw()
ui = app_mod.App(root)
dossier = cat_mod.dossier_catalogues()
verifie("ABSENT" in ui.lbl_cat_etat.cget("text"),
        f"ligne d'état : {ui.lbl_cat_etat.cget('text')[:52]}…")
verifie(ui.lbl_cat_dossier.cget("text").endswith(os.path.basename(dossier)),
        f"dossier affiché : « {ui.lbl_cat_dossier.cget('text')} »")

# Choix d'un dossier (dialogue intercepté) → config PERSISTÉE.
autre2 = os.path.join(TMP, "choisi")
os.makedirs(autre2)
app_mod.filedialog.askdirectory = lambda *a, **k: autre2
ui._choisir_dossier_catalogues()
verifie(config_mod.CONFIG.get("chemin_catalogues") == autre2
        and cat_mod.dossier_catalogues() == autre2,
        "dossier choisi : config `chemin_catalogues` posée et honorée")
app_mod.filedialog.askdirectory = _ASK

# Téléchargement : téléchargeur FACTICE (aucun accès réseau dans un banc).
_VRAI_DL = dl_mod.telecharger_catalogue_astro


def faux_telechargement(dossier_cible, progression=None):
    # Un vrai transfert dure des minutes : deux paliers ESPACÉS suffisent à
    # vérifier que la progression s'affiche PENDANT le transfert.
    for fraction in (0.25, 0.75):
        if progression:
            progression("siril_cat_healpix8_astro.dat.bz2", fraction)
        time.sleep(0.15)
    return catalogue_factice(dossier_cible,
                             "siril_cat_healpix8_astro.dat.bz2"), True


dl_mod.telecharger_catalogue_astro = faux_telechargement
ui._telecharger_catalogue()
verifie(ui._cat_dl_actif and "disabled" in ui.btn_cat_dl.state(),
        "téléchargement lancé : bouton neutralisé pendant le transfert")
vus = []
for _ in range(300):                      # thread → file → _tick (30 ms)
    ui._tick()
    root.update()
    vus.append(ui.lbl_cat_etat.cget("text"))
    if not ui._cat_dl_actif and "téléchargé" in ui.lbl_cat_etat.cget("text"):
        break
    time.sleep(0.01)
verifie(any("25 %" in t or "75 %" in t for t in vus),
        "la PROGRESSION est affichée pendant le transfert")
verifie(not ui._cat_dl_actif and "disabled" not in ui.btn_cat_dl.state(),
        "fin du transfert : bouton réactivé")
verifie("téléchargé" in ui.lbl_cat_etat.cget("text"),
        f"fin annoncée : « {ui.lbl_cat_etat.cget('text')} »")
verifie(cat_mod.chemin_catalogue_astro() is not None,
        "le catalogue est EXPLOITABLE après le téléchargement")
verifie(suivi.peut_essayer(300) or suivi.resolu,
        "l'astrométrie peut repartir sur ce catalogue")
ui._maj_cat_vue()      # rafraîchissement de la ligne (ce que fait un clic)
verifie("présent" in ui.lbl_cat_etat.cget("text"),
        f"la ligne repasse en état « présent » : « {ui.lbl_cat_etat.cget('text')[:46]}… »")

root.destroy()
dl_mod.telecharger_catalogue_astro = _VRAI_DL
app_mod.sauver_config = _SAUVER
restaure()
shutil.rmtree(TMP, ignore_errors=True)

print("\nBANC JALON 70 (données astrométrie) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)


