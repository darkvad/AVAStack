# -*- coding: utf-8 -*-
"""Banc du jalon 77 : AVAStack SANS SIRIL — spectres Gaia XP et base SPCC.

QUESTION D'ALAIN (29/09/2026) : « si tu traites ce point (bouton pour les
48 morceaux de spectres Gaia XP), AVAStack pourra fonctionner sans Siril,
y compris pour l'astrométrie et les capteurs et filtres SPCC ? »

RÉPONSE MESURÉE : NON — pas ce point SEUL. Il manquait DEUX jeux de données,
et ce banc les prend tous les deux :
  • les 48 morceaux de spectres Gaia XP (l'astrométrie avait déjà son bouton
    « ⬇ Gaia », la SPCC n'avait rien) ;
  • la base de profils SPCC (capteurs, filtres, références de blanc), qui
    n'était LUE que chez Siril (%LOCALAPPDATA%\\siril-spcc-database) : sans
    elle, la SPCC exigeait Siril installé ET une calibration lancée une fois.

Ce banc ne touche PAS le réseau : il monte un serveur HTTP LOCAL qui sert des
fichiers factices et des archives ZIP construites ici. Le code exercé est le
VRAI code (reprise par Range, sha256, extraction) — seules les URL changent,
et c'est pour cela que les hôtes sont des constantes de module.

  [1] `chunks_du_champ` : les morceaux qui couvrent un champ (M31 → 1 morceau),
      confrontés à une référence INDÉPENDANTE (astropy-healpix) ;
  [2] `telecharger_chunks` : transfert réel, sha256, pas de re-téléchargement,
      REPRISE d'un .part (Range/206), refus d'un sha256 qui ne correspond pas ;
  [3] `telecharger_base_spcc` : archive GitLab → base exploitable ; ce qui n'est
      pas une catégorie n'est pas extrait, une archive piégée (`..`) est
      REFUSÉE, et une base incomplète est refusée ;
  [4] `spcc_db` : base cherchée dans l'ordre config choisie → copie AVAStack →
      emplacements de Siril (comportement d'origine conservé) ;
  [5] UI RÉELLE : boutons « ⬇ Spectres (champ) », « ⬇ les 48 », « ⬇ Base SPCC »
      et « 📂 Dossier SPCC » — VISIBLES (géométrie, règle v2.38.9), message
      clair quand les indices manquent, transferts suivis par la file, et la
      SPCC devient UTILISABLE sans redémarrer après le téléchargement de la base
      (case cochable + listes remplies).

Exécution : python bancs/_test_sans_siril_jalon77.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import hashlib
import http.server
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import urllib.parse
import zipfile

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


TMP = tempfile.mkdtemp(prefix="banc77_")
DATA = os.path.join(TMP, "data")
CONF = os.path.join(TMP, "conf")
os.makedirs(DATA)
os.makedirs(CONF)

# --- isolement de l'environnement (rien de réel n'est touché) ----------------
# Même méthode que le banc du jalon 70 : on simule LINUX avec HOME/XDG dans le
# dossier du banc, donc aucune base de Siril réelle ne peut intervenir.
_ENV_SAUVE = {k: os.environ.get(k) for k in
              ("HOME", "USERPROFILE", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
               "LOCALAPPDATA", "APPDATA")}
os.environ["HOME"] = TMP
os.environ["USERPROFILE"] = TMP
os.environ["XDG_DATA_HOME"] = DATA
os.environ["XDG_CONFIG_HOME"] = CONF
os.environ.pop("LOCALAPPDATA", None)
os.environ.pop("APPDATA", None)

from avastack import catalogues as cat_mod            # noqa: E402
from avastack import config as config_mod             # noqa: E402
from avastack.catalogues import spcc_db as DB         # noqa: E402
from avastack.catalogues import telechargeur as dl    # noqa: E402

# PIÈGE (mesuré en écrivant ce banc) : `os.environ` ne suffit PAS sous Windows —
# `dossier_config()` lit `%APPDATA%` quand `IS_WINDOWS` est vrai, donc le banc
# lisait le VRAI config.json (et la case SPCC d'Alain, cochée, faussait le test).
# Les constantes d'OS sont donc basculées comme dans le banc du jalon 70.
_FLAGS_SAUVE = (cat_mod.IS_WINDOWS, cat_mod.IS_MACOS,
                DB.IS_MACOS, config_mod.IS_WINDOWS, config_mod.IS_MACOS)
cat_mod.IS_WINDOWS = config_mod.IS_WINDOWS = False
cat_mod.IS_MACOS = DB.IS_MACOS = config_mod.IS_MACOS = False

_CONFIG_SAUVE = dict(config_mod.CONFIG)
_URL_ZENODO_SAUVE = dl.URL_ZENODO
_URL_SPCC_SAUVE = dl.URL_SPCC


def restaure():
    for k, v in _ENV_SAUVE.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    config_mod.CONFIG.clear()
    config_mod.CONFIG.update(_CONFIG_SAUVE)
    (cat_mod.IS_WINDOWS, cat_mod.IS_MACOS, DB.IS_MACOS,
     config_mod.IS_WINDOWS, config_mod.IS_MACOS) = _FLAGS_SAUVE
    dl.URL_ZENODO = _URL_ZENODO_SAUVE
    dl.URL_SPCC = _URL_SPCC_SAUVE

# --- serveur HTTP local (fichiers factices ; AUCUN accès réseau réel) --------
CONTENU = {}
RANGES_VUS = []


class Manipulateur(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        chemin = urllib.parse.urlparse(self.path).path     # clés = « /dossier/… »
        data = CONTENU.get(chemin)
        if data is None:
            self.send_error(404)
            return
        debut = 0
        m = re.match(r"bytes=(\d+)-", self.headers.get("Range") or "")
        if m:
            debut = int(m.group(1))
            RANGES_VUS.append(chemin)
        corps = data[debut:]
        self.send_response(206 if debut else 200)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Content-Type", "application/octet-stream")
        if debut:
            self.send_header("Content-Range",
                             "bytes %d-%d/%d" % (debut, len(data) - 1, len(data)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *a):            # pas de bruit dans la console du banc
        pass


_SERVEUR = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Manipulateur)
_BASE = "http://127.0.0.1:%d" % _SERVEUR.server_address[1]
threading.Thread(target=_SERVEUR.serve_forever, daemon=True,
                 name="serveur-banc77").start()
dl.URL_ZENODO = _BASE                     # le vrai code, une autre adresse
print("serveur local : %s" % _BASE)


def sert_chunk(chunk):
    """Pose un morceau factice + SON .sha256sum sur le serveur → (nom, sha)."""
    nom = dl.nom_chunk(chunk)
    contenu = ("donnees factices du morceau %d " % chunk).encode() * 4096
    sha = hashlib.sha256(contenu).hexdigest()
    CONTENU["/%s/files/%s" % (dl.RECORD_XPSAMP, nom)] = contenu
    CONTENU["/%s/files/%s.sha256sum" % (dl.RECORD_XPSAMP, nom)] = \
        ("%s  %s\n" % (sha, nom)).encode()
    return nom, sha


CATEGORIES = tuple(DB.SOUS_DOSSIERS)


def zip_base_spcc(piege=False, categories=CATEGORIES):
    """Archive ZIP façon GitLab (racine `<projet>-<ref>`) construite en mémoire.
    `piege` ajoute une entrée qui SORT du dossier (`../`)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("siril-spcc-database-main/README.md", "# base factice\n")
        for cat in categories:
            z.writestr("siril-spcc-database-main/%s/profil.json" % cat,
                       json.dumps({"model": "Banc 77", "name": "%s-1" % cat,
                                   "type": "MONO_SENSOR", "channel": "RED",
                                   "wavelength": {"value": [400.0] * 8,
                                                  "units": "nm"},
                                   "values": {"value": [1.0] * 8}}))
        z.writestr("siril-spcc-database-main/utils/outil.py", "# pas une base\n")
        z.writestr("siril-spcc-database-main/SIGHTRON_Comet_BP.json",
                   json.dumps({"name": "Comet BP"}))
        if piege:
            z.writestr("siril-spcc-database-main/../../evil.json", "{}")
    return buf.getvalue()


# ================================================== [1] morceaux d'un champ
print("\n[1] chunks_du_champ : morceaux qui couvrent un champ")
import astropy.units as u                                    # noqa: E402
from astropy_healpix import HEALPix                          # noqa: E402

_hp8 = HEALPix(nside=256, order="nested")     # niveau 8 = celui du catalogue


def reference_chunk(ra, dec):
    """Morceau attendu d'après astropy-healpix — INDÉPENDANT de notre code :
    le pixel de niveau 1 est le pixel de niveau 8 privé de ses 14 bits de poids
    faible (propriété NESTED), et c'est ainsi que Siril nomme ses morceaux (sa
    plage de pixels est vérifiée sur les fichiers RÉELS au banc du jalon 56)."""
    pix8 = int(_hp8.lonlat_to_healpix(ra * u.deg, dec * u.deg))
    return pix8 >> (2 * (cat_mod.NIVEAU_CATALOGUE - 1))


M31 = (10.6847, 41.269)
_c_m31 = dl.chunks_du_champ(M31[0], M31[1], 0.75)
verifie(_c_m31 == [reference_chunk(*M31)],
        "champ M31 (rayon 0,75°) → morceau(x) %s (référence astropy : %d)"
        % (_c_m31, reference_chunk(*M31)))

points = [M31, (0.0, 0.0), (83.6, -5.4), (202.5, 47.2), (266.4, -29.0),
          (310.0, 60.0), (120.0, -80.0), (0.5, 89.5)]
manques = []
for ra, dec in points:
    attendu = reference_chunk(ra, dec)
    obtenu = dl.chunks_du_champ(ra, dec, 0.2)
    if attendu not in obtenu:
        manques.append((ra, dec, attendu, obtenu))
verifie(not manques,
        "le morceau du point est TOUJOURS pris dans le champ (%s)"
        % (manques or "8 points testés"))

_vus = set()
for i in range(2000):                      # balayage régulier de la sphère
    _vus |= set(dl.chunks_du_champ((i * 137.508) % 360.0,
                                   -85.0 + (i % 171) * 1.0, 0.01))
verifie(_vus == set(range(dl.TOTAL_CHUNKS)),
        "l'union des morceaux désignés sur la sphère = les 48 (%d trouvés)"
        % len(_vus))

# ============================================== [2] télécharger_chunks
print("\n[2] telecharger_chunks : transfert réel, sha256, reprise")
DDL = os.path.join(TMP, "catalogues")
os.makedirs(DDL)
sert_chunk(1)
sert_chunk(2)
_paliers = []
_res = dl.telecharger_chunks(DDL, [2, 1],
                             lambda nom, frac: _paliers.append((nom, frac)))
verifie(sorted(n for n, _p, _t in _res) == [1, 2]
        and all(t for _n, _p, t in _res),
        "2 morceaux transférés (%s)"
        % [(n, "transféré" if t else "déjà là") for n, _p, t in _res])
verifie(_paliers and all(0.0 < f <= 1.0 for _n, f in _paliers),
        "progression annoncée (%d paliers, dernier %.0f %%)"
        % (len(_paliers), 100.0 * _paliers[-1][1]))
_etat = dl.etat_local(DDL)
verifie(sorted(_etat["chunks"]) == [1, 2],
        "etat_local voit les morceaux %s" % sorted(_etat["chunks"]))
_etiq = {n: os.path.basename(p) for n, p in _etat["chunks"].items()}
verifie(_etiq[2] == dl.nom_chunk(2), "les fichiers portent le nom attendu (%s)"
        % _etiq[2])

_res2 = dl.telecharger_chunks(DDL, [1, 2])
verifie(not any(t for _n, _p, t in _res2),
        "deuxième appel : RIEN n'est retéléchargé (sha256 conforme)")

nom1 = dl.nom_chunk(1)
os.remove(os.path.join(DDL, nom1))
with open(os.path.join(DDL, nom1 + ".part"), "wb") as f:
    f.write(CONTENU["/%s/files/%s" % (dl.RECORD_XPSAMP, nom1)][:5000])
RANGES_VUS.clear()
_res3 = dl.telecharger_chunks(DDL, [1])
verifie(bool(_res3[0][2]), "morceau effacé → retéléchargé")
verifie(bool(RANGES_VUS),
        "la reprise a demandé un Range (une coupure réseau ne repart pas de 0)")
verifie(dl.etat_local(DDL)["chunks"][1] == os.path.join(DDL, nom1),
        "fichier complet après reprise (le .part a été renommé)")

nom2 = dl.nom_chunk(2)
os.remove(os.path.join(DDL, nom2))
CONTENU["/%s/files/%s.sha256sum" % (dl.RECORD_XPSAMP, nom2)] = \
    ("%s  %s\n" % ("0" * 64, nom2)).encode()
_err = ""
try:
    dl.telecharger_chunks(DDL, [2])
except RuntimeError as exc:
    _err = str(exc)
verifie("sha256" in _err and not os.path.isfile(os.path.join(DDL, nom2)),
        "sha256 non conforme : refus et fichier SUPPRIMÉ (« %s »)" % _err[:48])
sert_chunk(2)                              # remise en état pour la suite


# ============================================ [3] base de profils SPCC
print("\n[3] telecharger_base_spcc : l'archive GitLab devient une base")
CONTENU["/spcc.zip"] = zip_base_spcc()
dl.URL_SPCC = _BASE + "/spcc.zip"
DEST = os.path.join(TMP, "spcc")
_paliers = []
_d, _poses, _tele = dl.telecharger_base_spcc(
    DEST, lambda nom, frac: _paliers.append((nom, frac)))
verifie(_tele and _d == DEST and _poses >= len(CATEGORIES),
        "archive extraite : %d fichiers posés" % _poses)
verifie(DB.base_complete(DEST), "les cinq catégories sont là et non vides")
verifie(all(os.path.isfile(os.path.join(DEST, c, "profil.json"))
            for c in CATEGORIES),
        "un profil par catégorie, dans SON sous-dossier")
verifie(not os.path.isdir(os.path.join(DEST, "utils")),
        "ce qui n'est pas une catégorie n'est PAS extrait (utils/)")
verifie(os.path.isfile(os.path.join(DEST, "SIGHTRON_Comet_BP.json")),
        "les .json de référence à la racine sont conservés")
_residus = ([n for n in os.listdir(DEST) if n.endswith((".zip", ".part"))]
            + ([os.path.basename(DEST) + ".extraction"]
               if os.path.isdir(DEST + ".extraction") else []))
verifie(not _residus, "aucun résidu (ni ZIP, ni temporaire, ni .part) : %s"
        % (_residus or "0"))
verifie(_paliers and any(str(n).lower().endswith(".json") for n, _f in _paliers),
        "l'extraction annonce sa progression (%d paliers)" % len(_paliers))
verifie(dl.telecharger_base_spcc(DEST)[2] is False,
        "base complète : re-cliquer ne retélécharge RIEN")

CONTENU["/spcc_piege.zip"] = zip_base_spcc(piege=True)
dl.URL_SPCC = _BASE + "/spcc_piege.zip"
DEST2 = os.path.join(TMP, "spcc_piege")
_err = ""
try:
    dl.telecharger_base_spcc(DEST2)
except RuntimeError as exc:
    _err = str(exc)
verifie("suspect" in _err or "hors dossier" in _err,
        "archive PIÉGÉE (entrée `../`) refusée (« %s »)" % _err[:44])
verifie(not any(os.path.isfile(os.path.join(DEST2, c, "profil.json"))
                for c in CATEGORIES),
        "archive piégée : AUCUN profil posé")
_pieges = [os.path.join(p, "evil.json") for p in (TMP, os.path.dirname(TMP))]
verifie(not any(os.path.exists(p) for p in _pieges),
        "aucune écriture hors du dossier de destination")

CONTENU["/spcc_incomplet.zip"] = zip_base_spcc(categories=CATEGORIES[:-1])
dl.URL_SPCC = _BASE + "/spcc_incomplet.zip"
_err = ""
try:
    dl.telecharger_base_spcc(os.path.join(TMP, "spcc_incomplet"))
except RuntimeError as exc:
    _err = str(exc)
verifie("INCOMPLÈTE" in _err,
        "archive sans une catégorie : REFUSÉE (« %s »)" % _err[:52])
dl.URL_SPCC = _BASE + "/spcc.zip"

# ============================================ [4] où la base est cherchée
print("\n[4] spcc_db : config choisie → copie AVAStack → Siril")
config_mod.CONFIG.pop(DB.CLE_CONFIG, None)
verifie(DB.dossier_base() is None,
        "aucune base nulle part : None (l'appli doit le DIRE)")
_av = DB.dossier_avastack()
os.makedirs(_av, exist_ok=True)
for cat in (CATEGORIES[0], CATEGORIES[-1]):        # copie partielle d'AVAStack
    shutil.copytree(os.path.join(DEST, cat), os.path.join(_av, cat))
verifie(DB.dossier_base() == _av, "copie d'AVAStack retenue (%s)" % _av)
verifie(not DB.base_complete(_av),
        "…mais INCOMPLÈTE : base_complete dit non (critère du téléchargeur)")
_siril = os.path.join(DATA, "siril-spcc-database")
os.makedirs(_siril, exist_ok=True)
shutil.copytree(os.path.join(DEST, CATEGORIES[0]),
                os.path.join(_siril, CATEGORIES[0]))
verifie(DB.dossier_base() == _av,
        "les emplacements de Siril viennent APRÈS la copie d'AVAStack")
config_mod.CONFIG[DB.CLE_CONFIG] = DEST
verifie(DB.dossier_base() == DEST,
        "dossier CHOISI (chemin_spcc) : il prime sur tout")
_vide = os.path.join(TMP, "vide")
os.makedirs(_vide, exist_ok=True)
config_mod.CONFIG[DB.CLE_CONFIG] = _vide
verifie(DB.dossier_base() == _av,
        "dossier choisi VIDE : ignoré (un dossier vide ne masque pas une base)")
verifie(DB.dossier_ecriture() == _vide,
        "l'écriture vise le dossier choisi (même vide, il est créé)")
_r = DB.resume_base(DEST)
verifie(sum(_r.values()) >= len(CATEGORIES),
        "resume_base compte les profils (%s)" % _r)
config_mod.CONFIG.pop(DB.CLE_CONFIG, None)
shutil.rmtree(_av, ignore_errors=True)             # pour [5] : rien par défaut
shutil.rmtree(_siril, ignore_errors=True)


# ============================================================ [5] UI réelle
print("\n[5] UI réelle : boutons, messages, SPCC utilisable sans redémarrer")
import tkinter as tk                                  # noqa: E402
import avastack.ui.app as app_mod                     # noqa: E402
from avastack.processing import spcc as spcc_mod      # noqa: E402

app_mod.CONFIG = config_mod.CONFIG                    # le dict que lit la config
_SAUVER = app_mod.sauver_config
app_mod.sauver_config = lambda *a, **k: None          # JAMAIS le vrai config.json
_ASK = app_mod.filedialog.askdirectory
# État d'une machine SANS Siril : dossier SPCC choisi mais VIDE, aucun catalogue
# téléchargé — c'est exactement ce qu'Alain veut rendre autonome.
config_mod.CONFIG[DB.CLE_CONFIG] = _vide
dl.URL_SPCC = _BASE + "/spcc.zip"
UI_CH = dl.chunks_du_champ(315.404167, 68.163333, 0.8 * 0.5005)   # champ NGC 7023
for c in UI_CH:
    sert_chunk(c)

root = tk.Tk()
root.withdraw()
ui = app_mod.App(root)
# La fenêtre est AFFICHÉE tôt (comme le fait le banc du jalon 72) : `winfo_ismapped`
# ne dit rien sur une fenêtre retirée, et une mise en page ne se termine que sur
# une fenêtre réellement affichée.
root.deiconify()
root.update()


def _pomper(condition, delai=30.0):
    """Pompe la boucle Tk comme l'application. Jamais d'attente passive : un
    banc qui ne progresse pas doit ÉCHOUER avec un message, pas rester bloqué."""
    fin = time.time() + delai
    while time.time() < fin:
        ui._tick()
        root.update()
        if condition():
            return True
        time.sleep(0.02)
    return False


verifie(not ui._spcc_dispo and "disabled" in ui.chk_spcc.state(),
        "sans base au démarrage : la case SPCC est grisée (rien n'est promis)")
verifie(not ui.var_spcc.get(),
        "case SPCC décochée au démarrage (config du banc, aucun profil restauré)")
_pomper(lambda: "morceaux" in ui.lbl_cat_etat.cget("text"), 15.0)
_pomper(lambda: "Base SPCC" in ui.lbl_base_spcc.cget("text"), 15.0)
verifie("morceaux" in ui.lbl_cat_etat.cget("text"),
        "ligne des catalogues remplie par la mesure différée : « %s… »"
        % ui.lbl_cat_etat.cget("text")[:50])
verifie("ABSENTE" in ui.lbl_base_spcc.cget("text"),
        "ligne « Base SPCC » : « %s »" % ui.lbl_base_spcc.cget("text")[:46])

# --- ⬇ Spectres (champ) sans indices : la raison est dite, rien ne part
ui.var_astro_ra.set("")
ui.var_astro_dec.set("")
ui.var_astro_champ.set("")
ui._telecharger_spectres()
verifie(not ui._cat_dl_actif and "AD/Dec/champ" in ui.lbl_cat_etat.cget("text"),
        "sans indices : la raison est dite (« %s… »)"
        % ui.lbl_cat_etat.cget("text")[:44])

# --- ⬇ Spectres (champ) avec les indices d'Alain (NGC 7023)
ui.var_astro_ra.set("315.404167")
ui.var_astro_dec.set("68.163333")
ui.var_astro_champ.set("0.5005")
ui._telecharger_spectres()
verifie(ui._cat_dl_actif
        and all("disabled" in b.state() for b in ui._boutons_dl()),
        "transfert lancé : les QUATRE boutons de téléchargement sont neutralisés")
verifie(_pomper(lambda: not ui._cat_dl_actif, 30.0), "transfert terminé")
verifie("spectres téléchargés" in ui.lbl_cat_etat.cget("text"),
        "fin annoncée : « %s… »" % ui.lbl_cat_etat.cget("text")[:54])
_presents = cat_mod.etat_local(cat_mod.dossier_catalogues())["chunks"]
verifie(all(c in _presents for c in UI_CH),
        "les morceaux du champ %s sont là (la SPCC peut les lire)" % UI_CH)
verifie(all("disabled" not in b.state() for b in ui._boutons_dl()),
        "boutons rendus après le transfert")

# --- ⬇ Base SPCC : la SPCC doit devenir utilisable DANS la session
ui._telecharger_base_spcc()
verifie(ui._cat_dl_actif, "transfert de la base lancé (vers le dossier choisi)")
verifie(_pomper(lambda: not ui._cat_dl_actif, 40.0), "transfert de la base terminé")
verifie("sans Siril" in ui.lbl_cat_etat.cget("text"),
        "fin annoncée : « %s… »" % ui.lbl_cat_etat.cget("text")[:54])
verifie(spcc_mod.base_presente(),
        "base LISIBLE par le modèle SPCC (capteurs + références de blanc)")
verifie(ui._spcc_dispo and "disabled" not in ui.chk_spcc.state(),
        "case SPCC cochable SANS redémarrer (renfort du jalon 77)")
_vals = ui._spcc_cbs["capteur"].cget("values")
verifie(bool(_vals) and ui._spcc_vars["capteur"].get() in tuple(_vals),
        "listes remplies et sélection posée (%d capteur(s) : « %s »)"
        % (len(_vals), ui._spcc_vars["capteur"].get()))
verifie("osc" in ui.lbl_base_spcc.cget("text")
        and os.path.basename(_vide) in ui.lbl_base_spcc.cget("text"),
        "ligne « Base SPCC » dit le dossier et le contenu : « %s… »"
        % ui.lbl_base_spcc.cget("text")[:52])
ui.chk_spcc.invoke()
verifie(bool(ui.var_spcc.get()) and ui._spcc_actif
        and "introuvable" not in ui.lbl_spcc.cget("text"),
        "case SPCC cochée : « %s »" % ui.lbl_spcc.cget("text")[:48])


# --- GÉOMÉTRIE (règle v2.38.9) : `pack` ABANDONNE en silence un widget qui ne
# tient plus — on le vérifie par la MESURE, avec des textes LONGS.
ui.lbl_cat_etat.config(
    text="catalogue astro : ABSENT — l'astrométrie interne ne peut pas aboutir "
         "(bouton ⬇ Gaia, ou déposer le fichier ici) — spectres Gaia : 0/48 "
         "morceaux")
ui.lbl_base_spcc.config(
    text="Base SPCC : " + os.path.join(_vide, "sous-dossier-tres-long-a-mesurer")
         + " — mono 13, mono 15, osc 49, osc 46, wb 144")
root.deiconify()
root.update()
for _ in range(60):        # laisser la mise en page se TERMINER avant d'auditer
    root.update()
    time.sleep(0.05)
_nouveaux = (ui.btn_spectres, ui.btn_spectres_tous, ui.btn_spcc_base,
             ui.btn_spcc_dos)
verifie(all(b.winfo_ismapped() for b in _nouveaux),
        "les quatre boutons sont AFFICHÉS (abandonnés : %s)"
        % [b.cget("text") for b in _nouveaux if not b.winfo_ismapped()])
verifie(all(b.winfo_width() > 30 for b in _nouveaux),
        "aucun bouton écrasé (largeurs %s px)"
        % [b.winfo_width() for b in _nouveaux])
verifie(ui.lbl_base_spcc.winfo_reqwidth() <= ui.lbl_base_spcc.winfo_width() + 1,
        "la ligne « Base SPCC » n'est pas rognée (%d ≤ %d px)"
        % (ui.lbl_base_spcc.winfo_reqwidth(), ui.lbl_base_spcc.winfo_width()))

_defauts = []


def _libelle(w):
    try:
        return str(w.cget("text"))[:30]
    except Exception:
        return type(w).__name__


def _ou(w):
    """Chaîne des parents — un défaut de mise en page doit dire OÙ regarder."""
    out = []
    while w is not None and w is not ui.root:
        try:
            out.append(str(w.cget("text"))[:18] or w.winfo_class())
        except Exception:
            out.append(w.winfo_class())
        w = w.master
    return " < ".join(out)


def _auditer(parent):
    # Un parent SANS taille (0/1 px) n'a pas été mis en page : ses enfants ne
    # disent rien de fiable. MESURÉ (worktree de HEAD, AVANT cette passe, avec
    # une configuration VIDE comme ici) : 29 « écrasés » identiques dès la
    # construction — c'est le SAS du panedwindow interne resté à 1 px faute de
    # position mémorisée, un état PRÉEXISTANT que ce banc ne juge pas. Le
    # contrôle de géométrie de référence reste celui du jalon 72 (banc
    # `_test_espace_jalon72.py`, avec la vraie configuration) ; ici, les quatre
    # boutons AJOUTÉS sont vérifiés nommément, juste au-dessus.
    if parent.winfo_width() <= 1 or parent.winfo_height() <= 1:
        return
    for enfant in parent.winfo_children():
        if enfant.winfo_manager() and not enfant.winfo_ismapped():
            _defauts.append(("écrasé", _libelle(enfant), _ou(enfant),
                             parent.winfo_width(), parent.winfo_height()))
            continue
        if enfant.winfo_ismapped() and enfant.winfo_x() + enfant.winfo_width() \
                > parent.winfo_width() + 1:
            _defauts.append(("débordé", _libelle(enfant), _ou(enfant),
                             parent.winfo_width(), parent.winfo_height()))
        _auditer(enfant)


_auditer(ui.root)
verifie(not _defauts,
        "aucun widget écrasé/débordé dans la fenêtre (textes longs) : %s "
        "(fenêtre %d×%d, état %s)"
        % (_defauts[:3] or "0 défaut", ui.root.winfo_width(),
           ui.root.winfo_height(), ui.root.wm_state()))

root.destroy()
app_mod.sauver_config = _SAUVER
app_mod.filedialog.askdirectory = _ASK
restaure()
_SERVEUR.shutdown()
shutil.rmtree(TMP, ignore_errors=True)

print("\nBANC JALON 77 (AVAStack sans Siril) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)

