# -*- coding: utf-8 -*-
"""Banc du jalon 72 : l'ESPACE DISQUE se dit, et rien ne s'écrit à moitié.

Constat déclencheur (Alain, 27/09/2026, Linux) : « Erreur : 24962352 requested
and 10902832 written » pendant BlurX (outil détecté au vert). Mesures réelles
sur sa machine : `/tmp` est un **tmpfs de 4,6 Go**, rempli par l'application
elle-même (2,8 Go de dossiers `avastack_frames_*`, frames de 32 Mio) alors que
116 Go dormaient sur le disque. Le message vient de `numpy.ndarray.tofile()`,
appelé par astropy pour écrire un FITS : écriture PARTIELLE (43 %), signature
d'un volume plein.

Ce banc vérifie, SANS disque plein réel :
  [1] `travail` : détection tmpfs (point de montage le plus long), repli du
      dossier par défaut hors tmpfs, réglage honoré, messages chiffrés, plafond
      calculé sur l'espace RÉEL, nettoyage des orphelins (jamais un récent) ;
  [2] `images` : écriture ATOMIQUE (aucun `.part` résiduel), REFUS avant
      écriture quand l'espace manque, et traduction du message brut de numpy
      (« N requested and M written ») en phrase qui dit le fichier, la quantité
      et le volume ;
  [3] `framestore` : le plafond d'archivage SUIT l'espace libre (le 20 Go en dur
      ne protégeait pas un volume de 4,6 Go) ;
  [4] UI réelle : ligne « dossier de travail » (chemin + espace + alerte RAM),
      bouton 📂 (dialog intercepté, choix persisté), contrôle d'espace AVANT la
      chaîne externe (refus immédiat, aucun dossier laissé), et fichiers de
      travail CONSERVÉS en cas d'échec (au lieu d'être effacés).

Exécution : python bancs/_test_espace_jalon72.py
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

from avastack import travail
from avastack import config as config_mod
from avastack import images as img_mod
from avastack.processing.framestore import ArchiveFrames

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


TMP = tempfile.mkdtemp(prefix="banc72_")

_ENV_SAUVE = {k: os.environ.get(k) for k in ("XDG_CACHE_HOME", "TMPDIR")}
_CONFIG_SAUVE = dict(config_mod.CONFIG)
_MONTAGES_SAUVE = travail.points_de_montage
_ESPACE_SAUVE = travail.espace_libre
_TMPFS_SAUVE = travail.est_tmpfs
_OS_SAUVE = (travail.IS_WINDOWS, travail.IS_MACOS)
_DEFAUT_SAUVE = travail.dossier_defaut
_DST_SAUVE = travail.dossier_temp_systeme


def restaure():
    travail.points_de_montage = _MONTAGES_SAUVE
    travail.espace_libre = _ESPACE_SAUVE
    travail.est_tmpfs = _TMPFS_SAUVE
    travail.dossier_temp_systeme = _DST_SAUVE
    travail.IS_WINDOWS, travail.IS_MACOS = _OS_SAUVE
    for k, v in _ENV_SAUVE.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    config_mod.CONFIG.clear()
    config_mod.CONFIG.update(_CONFIG_SAUVE)


def petit_fits(chemin, cote=64):
    """Écrit un FITS de taille connue (64×64 float32 = 16 Kio) — par notre
    propre écriture atomique, ce qui la teste au passage."""
    img_mod.save_image(chemin, np.zeros((cote, cote), dtype=np.float32))
    return os.path.getsize(chemin)

print("[1] travail : tmpfs, repli, messages, plafond, orphelins")
verifie(travail.texte_octets(24_962_352) == "23,8 Mo"
        and travail.texte_octets(1 << 30) == "1,0 Go"
        and travail.texte_octets(512) == "512 o",
        "messages chiffrés : %s, %s, %s"
        % (travail.texte_octets(24_962_352), travail.texte_octets(1 << 30),
           travail.texte_octets(512)))

# Détection tmpfs : c'est le point de montage le PLUS LONG qui décide.
# (Le banc rejoue LINUX : la détection est désactivée sous Windows/macOS, où
# le dossier temporaire vit sur disque — cf. travail.est_tmpfs.)
travail.IS_WINDOWS = travail.IS_MACOS = False
travail.points_de_montage = lambda: [("/", "ext4"), ("/tmp", "tmpfs"),
                                     ("/tmp/sous", "ext4")]
verifie(travail.est_tmpfs("/tmp/avastack_x") is True,
        "« /tmp » en tmpfs : volume de RAM détecté")
verifie(travail.est_tmpfs("/home/alain/x") is False,
        "« /home » (disque) non signalé comme RAM")
verifie(travail.est_tmpfs("/tmp/sous/x") is False,
        "sous-montage disque reconnu sous un tmpfs parent")

# Repli : temporaire système en tmpfs → on va sur le disque (cache utilisateur).
CACHE = os.path.join(TMP, "cache")
os.environ["XDG_CACHE_HOME"] = CACHE
travail.points_de_montage = lambda: [("/", "ext4"), ("/tmp", "tmpfs")]
travail.dossier_temp_systeme = lambda: "/tmp"
verifie(travail.dossier_defaut() == os.path.join(CACHE, "avastack"),
        "repli hors tmpfs : %s" % travail.dossier_defaut())
travail.points_de_montage = lambda: [("/", "ext4")]
verifie(travail.dossier_defaut() == "/tmp",
        "sans tmpfs : le temporaire système reste utilisé")
travail.dossier_temp_systeme = _DST_SAUVE          # retour au vrai temporaire
travail.IS_WINDOWS, travail.IS_MACOS = _OS_SAUVE   # et au vrai OS

# Réglage explicite honoré (« dossier de travail » de l'interface).
choisi = os.path.join(TMP, "sur_le_disque")
os.makedirs(choisi, exist_ok=True)
config_mod.CONFIG["dossier_travail"] = choisi
verifie(travail.dossier_travail() == choisi,
        "réglage « dossier_travail » honoré : %s" % travail.dossier_travail())
cree = travail.creer_dossier("avastack_")
verifie(os.path.dirname(cree) == choisi
        and os.path.basename(cree).startswith("avastack_"),
        "creer_dossier() crée bien DANS le dossier de travail")
shutil.rmtree(cree, ignore_errors=True)

# Plafond calculé sur l'espace RÉEL (le bug de fond : 20 Go en dur).
travail.espace_libre = lambda _d: 100 * (1 << 20)          # 100 Mo libres
verifie(travail.plafond_effectif("/tmp", 20 * (1 << 30)) == 50 * (1 << 20),
        "plafond effectif = 50 % de l'espace libre, au lieu de 20 Go fixes")

# Messages chiffrés : refus AVANT écriture quand l'espace manque.
travail.espace_libre = lambda _d: 10 * (1 << 20)
ok_esp, msg_esp = travail.verifier_espace("/tmp", 100 * (1 << 20),
                                          "l'écriture du FITS de travail")
verifie(not ok_esp and "espace insuffisant" in msg_esp
        and "Mo" in msg_esp and "dossier de travail" in msg_esp,
        "refus chiffré : « %s… »" % msg_esp[:74])
verifie(travail.verifier_espace("/tmp", 1 << 20)[0],
        "espace suffisant : aucun refus")

# Orphelins : un dossier VIEUX part, un dossier RÉCENT reste.
travail.espace_libre = _ESPACE_SAUVE
vieil = os.path.join(choisi, "avastack_vieux")
recent = os.path.join(choisi, "avastack_recent")
for d in (vieil, recent):
    os.makedirs(d, exist_ok=True)
    petit_fits(os.path.join(d, "frame_000000.fits"))
vieux_t = time.time() - 10 * 3600
os.utime(vieil, (vieux_t, vieux_t))
n, octets = travail.nettoyer_orphelins(dossiers=[choisi])
verifie(n == 1 and octets >= 4096 and not os.path.exists(vieil)
        and os.path.exists(recent),
        "orphelins : %d dossier(s), %s récupérés — le récent est intact"
        % (n, travail.texte_octets(octets)))
shutil.rmtree(recent, ignore_errors=True)
config_mod.CONFIG.pop("dossier_travail", None)



print("[2] images : écriture ATOMIQUE, refus avant écriture, message traduit")
fits_test = os.path.join(TMP, "atomique.fits")
taille = petit_fits(fits_test)
verifie(os.path.isfile(fits_test)
        and not os.path.exists(fits_test + ".part"),
        "FITS écrit sans partiel résiduel (%d octets)" % taille)
png_test = os.path.join(TMP, "atomique.png")
img_mod.save_image(png_test, np.random.rand(16, 16).astype(np.float32))
verifie(os.path.isfile(png_test)
        and not os.path.exists(png_test + ".part"),
        "PNG écrit sans partiel résiduel")

# Refus AVANT d'écrire : un FITS de 16 Kio dans 4 Kio libres.
travail.espace_libre = lambda _d: 4096
refuse = os.path.join(TMP, "refuse.fits")
msg_refus = ""
try:
    img_mod.save_image(refuse, np.zeros((64, 64), np.float32))
except OSError as exc:
    msg_refus = str(exc)
verifie("espace insuffisant" in msg_refus and not os.path.exists(refuse)
        and not os.path.exists(refuse + ".part"),
        "refus AVANT écriture, rien n'est créé : « %s… »" % msg_refus[:58])
travail.espace_libre = _ESPACE_SAUVE

# Écriture PARTIELLE (le message EXACT d'Alain) → phrase claire, pas de partiel.
brut = OSError("24962352 requested and 10902832 written")
traduit = img_mod.traduction_erreur_ecriture(brut, refuse, 24_962_352)
verifie("écriture incomplète" in traduit and "23,8 Mo" in traduit
        and "espace" in traduit and "dossier de travail" in traduit,
        "message brut traduit : « %s… »" % traduit[:92])


def _ecrivain_brut(destination):
    """Écrit 2 Kio puis échoue, comme numpy sur un volume plein."""
    with open(destination, "wb") as f:
        f.write(b"0" * 2048)
    raise brut


msg_partiel = ""
try:
    img_mod.ecrire_fichier(refuse, _ecrivain_brut, octets=1000)
except OSError as exc:
    msg_partiel = str(exc)
verifie("écriture incomplète" in msg_partiel
        and not os.path.exists(refuse) and not os.path.exists(refuse + ".part"),
        "échec en pleine écriture : partiel SUPPRIMÉ, message traduit")

print("[3] framestore : le plafond d'archivage SUIT l'espace libre")
travail.espace_libre = lambda _d: 100 * 1024            # 100 Kio libres
arch = ArchiveFrames(max_octets=20 * (1 << 30), intervalle_s=0.0)
for _ in range(15):
    if arch.ajouter(np.zeros((64, 64), np.float32)) is None:
        break
verifie(arch.erreur != "" and "plafond" in arch.erreur,
        "archivage ARRÊTÉ par le plafond RÉEL : « %s… »" % arch.erreur[:66])
verifie(arch._taille <= 80 * 1024,
        "occupation bornée (%s pour 100 Kio libres)"
        % travail.texte_octets(arch._taille))
arch.vider()
travail.espace_libre = _ESPACE_SAUVE

print("[4] UI : ligne de travail, bouton 📂, refus avant chaîne, journal gardé")
import tkinter as tk                            # noqa: E402
import avastack.ui.app as app_mod               # noqa: E402

app_mod.CONFIG = config_mod.CONFIG              # le dict que lit la config
_SAUVER = app_mod.sauver_config
sauve = {}
app_mod.sauver_config = lambda d: sauve.update(d)
_ASK = app_mod.filedialog.askdirectory

perso = os.path.join(TMP, "travail_ui")
os.makedirs(perso, exist_ok=True)
config_mod.CONFIG["dossier_travail"] = perso
root = tk.Tk()
root.withdraw()
ui = app_mod.App(root)
verifie(perso in ui.lbl_travail.cget("text")
        and "libres" in ui.lbl_travail.cget("text"),
        "ligne de travail : « %s… »" % ui.lbl_travail.cget("text")[:72])

# v2.38.9 — GÉOMÉTRIE de cette ligne : elle doit être VISIBLE SANS DÉFILEMENT et
# ses TROIS boutons doivent être affichés. C'est la régression exacte du
# 27/09/2026, vue par Alain : « pas de chemin pour temp et pas de bouton
# journal ». Mesure d'alors : le bouton « Journal » n'était JAMAIS affiché
# (`pack` abandonne SILENCIEUSEMENT le widget qui ne tient plus — trois boutons
# sur une ligne dans un cadre de 318 px) et la ligne était à y≈2421 px sur les
# 3218 px de la colonne défilante, donc sous le pli. `winfo_ismapped` ne dit rien
# sur une fenêtre retirée : on l'affiche le temps de la mesure.
from tkinter import ttk                        # noqa: E402
ui.root.deiconify()
ui.root.update()
boutons = []


def _boutons_de_travail(widget):
    for enfant in widget.winfo_children():
        if isinstance(enfant, ttk.Button):
            boutons.append(enfant)
        _boutons_de_travail(enfant)


_boutons_de_travail(ui.lbl_travail.master)
_vus = sorted(str(b.cget("text")) for b in boutons)
verifie(_vus == ["Journal", "Ouvrir", "📂 Dossier"],
        "les trois boutons existent : %s" % _vus)
verifie(all(b.winfo_ismapped() for b in boutons),
        "aucun bouton écrasé (non affiché : %s)"
        % [b.cget("text") for b in boutons if not b.winfo_ismapped()])
_y = ui.lbl_travail.winfo_rooty() - ui.root.winfo_rooty()
verifie(0 <= _y < ui.root.winfo_height(),
        "ligne VISIBLE sans défilement (y=%d px, fenêtre haute de %d px)"
        % (_y, ui.root.winfo_height()))
ui.root.withdraw()

# Alerte « en RAM » : la ligne doit la dire (orange), comme sur son /tmp.
_TMPFS = travail.est_tmpfs
ui._travail_recycle = (0, 0)      # le nettoyage réel du démarrage ne pollue pas
travail.est_tmpfs = lambda _d: True
ui._maj_travail_vue()
verifie("RAM" in ui.lbl_travail.cget("text")
        and "#c98a00" in str(ui.lbl_travail.cget("foreground")),
        "alerte tmpfs : « …%s »" % ui.lbl_travail.cget("text")[-38:])
travail.est_tmpfs = _TMPFS

# Bouton 📂 : dossier choisi → persisté dans la config ET affiché.
autre = os.path.join(TMP, "travail_choisi")
os.makedirs(autre, exist_ok=True)
app_mod.filedialog.askdirectory = lambda *a, **k: autre
ui._choisir_dossier_travail()
verifie(config_mod.CONFIG.get("dossier_travail") == autre
        and autre in ui.lbl_travail.cget("text")
        and sauve.get("dossier_travail") == autre,
        "bouton 📂 : choix persisté (config) et affiché")
app_mod.filedialog.askdirectory = _ASK

# Contrôle d'espace AVANT la chaîne : refus immédiat, AUCUN dossier laissé.
config_mod.CONFIG["dossier_travail"] = perso
avant = set(os.listdir(perso))
ui.ext_job = (True, 'graxpert "{input}" -cli -output "{outbase}"',
              False, "", False, "", "graxpert", 0.5)
ui.stacker = None                    # pas de composition : chaîne mono
_E = travail.espace_libre
travail.espace_libre = lambda _d: 4096
ui._run_external(np.zeros((64, 64), np.float32), 3, ui._session)
verifie("espace insuffisant" in ui.ext_msg and ui.ext_state == "error"
        and ui.ext_busy is False,
        "chaîne refusée AVANT écriture : « %s… »" % ui.ext_msg[:56])
verifie(set(os.listdir(perso)) == avant,
        "aucun dossier de travail laissé par le refus")
travail.espace_libre = _E

# Échec APRÈS écriture : le dossier (et son journal) est CONSERVÉ et annoncé.
garde = travail.creer_dossier("avastack_")
with open(os.path.join(garde, "outils_sortie.txt"), "w",
          encoding="utf-8") as f:
    f.write("journal de l'outil")
ui.ext_state = "error"
ui.ext_msg = "Erreur : test d'échec"
ui.ext_busy = True
ui._fin_ext_tmp(garde, ui._session)
verifie(os.path.isdir(garde) and "conservés" in ui.ext_msg,
        "échec : fichiers CONSERVÉS et annoncés — « %s… »" % ui.ext_msg[:64])
shutil.rmtree(garde, ignore_errors=True)

# Succès : le dossier est supprimé comme avant (non-régression).
propre = travail.creer_dossier("avastack_")
ui.ext_state = "ok"
ui.ext_busy = True
ui._fin_ext_tmp(propre, ui._session)
verifie(not os.path.exists(propre) and ui.ext_busy is False,
        "succès : dossier supprimé et ext_busy libéré")

root.destroy()
app_mod.sauver_config = _SAUVER
restaure()
shutil.rmtree(TMP, ignore_errors=True)

print("\nBANC JALON 72 (espace disque et écritures) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)

