# -*- coding: utf-8 -*-
"""Banc v2.93.0 — LOT 1 (P2 + P3) : base SPCC la plus riche, zéro substitution
silencieuse, astrométrie servie en FIN DE SOURCE.

DÉFAUTS MESURÉS LE 19/10/2026 (liste d'Alain) :
  · P2 — la copie d'AVAStack (`%APPDATA%\\AVAStack\\spcc-database`) avait 12
    `mono_filters` SANS `QHYCCD_MiniCam8M_LRGB.json`, la base Siril en avait
    13. `dossier_base()` prenait le PREMIER dossier valide : la copie
    incomplète MASQUAIT la base complète → filtres MiniCam introuvables.
    Aggravant : `_spcc_defaut` remplaçait une valeur absente par `liste[0]`
    (un nom ARBITRAIRE) → `config.json` portait `spcc_fr = « Antlia R »`.
  · P3 — `_servir_demandes_sans_frame` servait SPCC et photométrie mais PAS
    l'astrométrie, et `_astro_tour` n'était appelé qu'après un re-stack : une
    astro cochée en fin de brutes n'était jamais tentée, et le WCS manquant
    ENTRAÎNAIT Gaia + SPCC.

Vérifie :
  [1] `dossier_base` : 13 filtres GAGNENT sur 12, sans rien copier ; égalité →
      copie AVAStack (ordre historique) ; `chemin_spcc` explicite prime ;
      dossier choisi VIDE ignoré ; compteurs exacts ;
  [2] téléchargeur : une extraction PLUS PAUVRE est REFUSÉE (base intacte) et
      un fichier existant portant plus de profils n'est jamais écrasé ;
  [3] `_profil` : exact → normalisé → sous-chaîne ; échec = noms les plus
      proches ;
  [4] `defaut_profil` PAR CANAL (jamais `liste[0]`) et
      `_spcc_verifier_profils` : `Antlia R` REPOSÉ en `QHYCCD MiniCam8M Red`
      avec message, valeur absente CONSERVÉE + alerte ;
  [5] P3 : astro D'ABORD dans `_servir_demandes_sans_frame`, puis photo et
      SPCC reposées après une résolution, demande consommée UNE fois ; aucun
      essai quand le WCS est déjà résolu ; fin de source arme l'astro UNE fois ;
      `_on_astro` pose la demande au cochage et au changement d'indices ;
  [6] garde FILTER : un modèle de filtres incompatible donne un avertissement
      rouge, un rôle générique (« R ») ne dit rien.

Exécution : python bancs/_test_lot1_p2_p3.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import json
import os
import shutil
import sys
import tempfile
import types
import zipfile

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

import avastack.config as config_mod
import avastack.ui.app as app_mod
import avastack.core.worker as worker_mod
from avastack.catalogues import spcc_db as DB
from avastack.catalogues import telechargeur as DL
from avastack.processing import spcc as SP

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


class FauxVar:
    """Variable Tk réduite à get/set (les méthodes testées n'en demandent pas
    plus : aucune n'est exécutée dans le thread Tk)."""

    def __init__(self, valeur=""):
        self._v = valeur

    def get(self):
        return self._v

    def set(self, valeur):
        self._v = valeur


def ecrire_profils(dossier, categorie, noms, objets=None):
    """Écrit `noms` fichiers JSON dans `dossier/<categorie>` (contenu dict ou
    liste d'objets — les deux formes de la base Siril)."""
    d = os.path.join(dossier, categorie)
    os.makedirs(d, exist_ok=True)
    for i, nom in enumerate(noms):
        with open(os.path.join(d, f"{nom}.json"), "w", encoding="utf-8") as f:
            json.dump(objets if objets is not None else {"name": nom}, f)


def base_factice(racine, nb_filtres):
    """Base SPCC minimale mais VALIDE : 5 catégories, `nb_filtres` filtres."""
    for cat in DB.SOUS_DOSSIERS:
        if cat != "mono_filters":
            ecrire_profils(racine, cat, ["un"])
    ecrire_profils(racine, "mono_filters", [f"filtre{i:02d}"
                                            for i in range(nb_filtres)])
    return racine


TMP = tempfile.mkdtemp(prefix="ava_lot1_")
AV = base_factice(os.path.join(TMP, "avastack"), 12)
SIRIL = base_factice(os.path.join(TMP, "siril"), 13)

_vrai_av, _vrai_siril = DB.dossier_avastack, DB._candidats_siril
_vraie_config = dict(config_mod.CONFIG)

# ================================================ [1] base la plus riche
print("\n[1] dossier_base : la base la PLUS RICHE gagne (13 > 12), rien n'est copié")
config_mod.CONFIG.pop(DB.CLE_CONFIG, None)
DB.dossier_avastack = lambda: AV
DB._candidats_siril = lambda: [SIRIL]
verifie(DB.compter_base(SIRIL)["mono_filters"] == 13
        and DB.compter_base(AV)["mono_filters"] == 12,
        "prémisse : 13 filtres (Siril) contre 12 (copie AVAStack)")
verifie(DB.total_base(SIRIL) == 17 and DB.total_base(AV) == 16,
        f"compteurs totaux exacts (Siril {DB.total_base(SIRIL)}, "
        f"AVAStack {DB.total_base(AV)})")
verifie(DB.dossier_base() == SIRIL,
        "la base Siril (13 filtres) BAT la copie incomplète (12) — sans copie")
verifie(len(os.listdir(os.path.join(AV, "mono_filters"))) == 12,
        "…et la copie d'AVAStack est INCHANGÉE (aucun fichier déplacé)")

# À ÉGALITÉ : l'ordre historique tranche (copie AVAStack d'abord).
EGAL = base_factice(os.path.join(TMP, "egal"), 12)
DB._candidats_siril = lambda: [EGAL]
verifie(DB.dossier_base() == AV,
        "à égalité de richesse, la copie d'AVAStack reste retenue (ordre historique)")

# CHOIX EXPLICITE : il prime, même plus pauvre.
config_mod.CONFIG[DB.CLE_CONFIG] = AV
DB._candidats_siril = lambda: [SIRIL]
verifie(DB.dossier_base() == AV,
        "chemin_spcc EXPLICITE prime, même si sa base est plus pauvre")
VIDE = os.path.join(TMP, "vide")
os.makedirs(VIDE, exist_ok=True)
config_mod.CONFIG[DB.CLE_CONFIG] = VIDE
verifie(DB.dossier_base() == SIRIL,
        "dossier choisi VIDE : ignoré (il ne masque pas une base utilisable)")
config_mod.CONFIG.pop(DB.CLE_CONFIG, None)

# Aucune base nulle part : None (l'appli doit le DIRE).
AUCUNE = os.path.join(TMP, "aucune")
os.makedirs(AUCUNE, exist_ok=True)
DB.dossier_avastack = lambda: AUCUNE
DB._candidats_siril = lambda: []
verifie(DB.dossier_base() is None, "aucune base : None (jamais un dossier vide)")
DB.dossier_avastack, DB._candidats_siril = _vrai_av, _vrai_siril


# ================================================ [2] téléchargeur : garde
print("\n[2] téléchargeur : une extraction ne rend JAMAIS la base plus pauvre")


def zip_base(entrees):
    """Construit un ZIP de base SPCC : {chemin relatif: contenu JSON}."""
    chemin = os.path.join(TMP, f"base_{len(os.listdir(TMP))}.zip")
    with zipfile.ZipFile(chemin, "w") as zf:
        for rel, contenu in entrees.items():
            zf.writestr("siril-spcc-database-master/" + rel,
                        json.dumps(contenu))
    return chemin


INSTALLE = base_factice(os.path.join(TMP, "installee"), 2)   # 2 fichiers
avant = sorted(os.listdir(os.path.join(INSTALLE, "mono_filters")))
# Archive qui n'apporte QU'UN filtre là où il y en a DEUX → REFUSÉE.
pauvre = {f"{cat}/un.json": {"name": "un"} for cat in DB.SOUS_DOSSIERS}
pauvre["mono_filters/un.json"] = {"name": "un"}
err = ""
try:
    DL.extraire_zip_spcc(zip_base(pauvre), INSTALLE)
except RuntimeError as exc:
    err = str(exc)
verifie("PLUS PAUVRE" in err and "mono_filters" in err,
        f"archive avec MOINS de filtres : REFUSÉE (« {err[:58]}… »)")
verifie(sorted(os.listdir(os.path.join(INSTALLE, "mono_filters"))) == avant,
        "…et la base installée est INTACTE (aucun profil supprimé)")

# Même NOMBRE de fichiers, mais un fichier portant MOINS d'objets : conservé.
RICHE = base_factice(os.path.join(TMP, "riche"), 1)
with open(os.path.join(RICHE, "mono_filters", "jeu.json"), "w",
          encoding="utf-8") as f:
    json.dump([{"name": "R"}, {"name": "G"}, {"name": "B"},
               {"name": "L"}], f)
egaux = {f"{cat}/un.json": {"name": "un"} for cat in DB.SOUS_DOSSIERS}
egaux["mono_filters/filtre00.json"] = {"name": "filtre00"}
egaux["mono_filters/jeu.json"] = [{"name": "R"}]      # 1 objet au lieu de 4
DL.extraire_zip_spcc(zip_base(egaux), RICHE)
with open(os.path.join(RICHE, "mono_filters", "jeu.json"), encoding="utf-8") as f:
    garde = json.load(f)
verifie(isinstance(garde, list) and len(garde) == 4,
        "fichier existant à 4 profils CONSERVÉ face à une version à 1 profil")



# ================================================ [3] _profil : 3 essais
print("\n[3] `_profil` : exact → normalisé → sous-chaîne ; échec explicite")
NOMS = ["No filter", "Full spectrum (no filter)",
        "QHYCCD MiniCam8M Red", "Antlia R"]
_vrai_lister, _vrai_courbe = DB.lister, DB.courbe
DB.lister = lambda cat, base=None: (
    [{"nom": n, "modele": "M", "canal": "RED", "chemin": "x", "index": 0}
     for n in NOMS] if cat == "mono_filters" else [])
DB.courbe = lambda e: (np.array([400.0, 500.0, 600.0]),
                       np.array([1.0, 1.0, 1.0]))
verifie(SP._profil("No filter", "mono_filters", "f")[0] == "No filter",
        "EXACT d'abord : « No filter » ne devient pas « Full spectrum (no filter) »")
verifie(SP._profil("  antlia   r ", "mono_filters", "f")[0] == "Antlia R",
        "NORMALISÉ : casse et espaces neutralisés")
verifie(SP._profil("MiniCam8M Red", "mono_filters", "f")[0]
        == "QHYCCD MiniCam8M Red",
        "SOUS-CHAÎNE : « MiniCam8M Red » retrouve le nom complet")
verifie(SP._profil("Antlia X", "mono_filters", "f") == (None, None),
        "introuvable → (None, None), jamais un profil approximatif")
verifie(SP.proches_noms("mono_filters", "Antlia Rr") == ["Antlia R"],
        "échec EXPLIQUÉ : les noms les plus proches sont proposés")
DB.lister, DB.courbe = _vrai_lister, _vrai_courbe


# ================================================ [4] défauts + substitution
print("\n[4] défauts PAR CANAL et substitution de profil DITE, jamais muette")
PROFILS = {
    "Antlia L": {"modele": "Antlia LRGB-V Pro", "canal": "LUM"},
    "Antlia R": {"modele": "Antlia LRGB-V Pro", "canal": "RED"},
    "Antlia G": {"modele": "Antlia LRGB-V Pro", "canal": "GREEN"},
    "Antlia B": {"modele": "Antlia LRGB-V Pro", "canal": "BLUE"},
    "QHYCCD MiniCam8M Red": {"modele": "QHYCCD MiniCam8M LRGB", "canal": "RED"},
    "QHYCCD MiniCam8M Green": {"modele": "QHYCCD MiniCam8M LRGB",
                               "canal": "GREEN"},
    "QHYCCD MiniCam8M Blue": {"modele": "QHYCCD MiniCam8M LRGB",
                              "canal": "BLUE"},
}
_vrai_profils = SP.profils_filtres
SP.profils_filtres = lambda: PROFILS
LISTE = list(PROFILS)
verifie(LISTE[0] == "Antlia L",
        "prémisse : `liste[0]` est un filtre de LUMINANCE (l'ancien défaut)")
verifie(SP.defaut_profil("fr", LISTE) == "Antlia R",
        "défaut du champ R = un filtre de canal RED, pas `liste[0]`")
verifie(SP.defaut_profil("fg", LISTE) == "Antlia G"
        and SP.defaut_profil("fb", LISTE) == "Antlia B",
        "défauts G et B par CANAL (GREEN / BLUE)")
verifie(SP.defaut_profil("fr", ["Antlia L"]) == "",
        "aucun filtre du canal → \"\" (l'appelant CONSERVE la valeur)")


class FauxAppSPCC:
    """Hôte minimal pour `App._spcc_verifier_profils` (aucun Tk)."""

    def __init__(self):
        self._spcc_vars = {
            "fr": FauxVar("Antlia R"),
            "fg": FauxVar("QHYCCD MiniCam8M Green"),
            "fb": FauxVar("QHYCCD MiniCam8M Blue"),
            "capteur": FauxVar("Sony IMX585"),
            "blanc": FauxVar("Average Spiral Galaxy"),
        }
        self._spcc_noms = {"filtres": LISTE,
                           "capteur": ["Sony IMX585", "QHYCCD MiniCam8M"],
                           "blancs": ["Average Spiral Galaxy"]}
        self._spcc_alerte = ""
        self._spcc_osc = lambda: False
        self._maj_spcc_vue = lambda: None
        # L'avis de correction est temporisé par un `after` Tk : un hôte sans
        # `root` se contente de le poser (le banc vérifie le texte, pas le délai).
        self._armer_effacement_correction = lambda: None


CAS = FauxAppSPCC()
app_mod.App._spcc_verifier_profils(CAS)
verifie(CAS._spcc_vars["fr"].get() == "QHYCCD MiniCam8M Red",
        "CAS RÉEL : `Antlia R` REPOSÉ en `QHYCCD MiniCam8M Red` "
        "(modèle des filtres G/B)")
verifie("remplacé par" in CAS._spcc_correction
        and "MiniCam8M Red" in CAS._spcc_correction,
        f"…et le remplacement est DIT (« {CAS._spcc_correction[:60]}… »)")
verifie(not CAS._spcc_alerte,
        "…comme AVIS de correction (ambre), pas comme problème persistant (rouge)")
app_mod.App._effacer_spcc_correction(CAS)
verifie(CAS._spcc_correction == "",
        "l'avis de correction s'EFFACE : l'état de la mesure reprend la main")

CAS2 = FauxAppSPCC()
CAS2._spcc_vars["fr"].set("Profil disparu")
app_mod.App._spcc_verifier_profils(CAS2)
verifie(CAS2._spcc_vars["fr"].get() == "Profil disparu",
        "valeur ABSENTE de la base : CONSERVÉE, jamais remplacée")
verifie("absent de la base" in CAS2._spcc_alerte,
        "…et signalée (« absent de la base — conservé »)")

CAS3 = FauxAppSPCC()
CAS3._spcc_vars["fr"].set("Antlia G")      # présent, mais canal GREEN
app_mod.App._spcc_verifier_profils(CAS3)
verifie("n'est pas un filtre R" in CAS3._spcc_alerte,
        "profil présent mais du MAUVAIS CANAL : signalé, conservé")
SP.profils_filtres = _vrai_profils

# Le MÊME contrôle avec la VRAIE base installée (aucune donnée factice) : c'est
# le cas réel du 19/10 (`config.json` portait `spcc_fr = « Antlia R »`).
if (SP.profils_filtres().get("QHYCCD MiniCam8M Red")):
    REEL = FauxAppSPCC()
    REEL._spcc_noms = SP.noms_base()
    REEL._spcc_vars["fr"].set("Antlia R")
    app_mod.App._spcc_verifier_profils(REEL)
    verifie(REEL._spcc_vars["fr"].get() == "QHYCCD MiniCam8M Red",
            "VRAIE base : « Antlia R » → « QHYCCD MiniCam8M Red » "
            "(sans réparer la base à la main)")
    verifie("remplacé par" in REEL._spcc_correction,
            "…et l'avis de correction est posé (il sera temporisé à l'écran)")
else:
    print("  (base réelle sans QHYCCD MiniCam8M : contrôle réel ignoré)")



# ================================================ [5] P3 : service sans frame
print("\n[5] P3 : astro D'ABORD, puis photo/SPCC — sans nouvelle frame")


class FauxSuivi:
    def __init__(self, resolu=False):
        self.resolu = resolu


class FauxAppDemandes:
    def __init__(self, resolu=False):
        self.stacker = types.SimpleNamespace(n=10)
        self.suivi_astro = FauxSuivi(resolu)
        self._astro_demande = True
        self._photo_demande = False
        self._spcc_demande = False
        self._astro_actif = True
        self._photo_actif = True
        self._spcc_actif = True
        self.appels = []
        self.rendus = 0

    def _astro_tour(self, st):
        self.appels.append("astro")
        self.suivi_astro.resolu = True

    def _photo_tour(self, st):
        self.appels.append("photo")

    def _spcc_tour(self, st):
        self.appels.append("spcc")

    def _pousser_rendu(self):
        self.rendus += 1


CAS = FauxAppDemandes()
app_mod.App._servir_demandes_sans_frame(CAS)
verifie(CAS.appels == ["astro", "photo", "spcc"],
        f"ordre astro → photo → SPCC (reçu {CAS.appels})")
verifie(CAS.rendus == 1, "un seul rendu poussé à l'UI")
verifie(not CAS._astro_demande, "demande d'astrométrie CONSOMMÉE")
CAS.appels.clear()
app_mod.App._servir_demandes_sans_frame(CAS)
verifie(CAS.appels == [] and CAS.rendus == 1,
        "2e passage : plus rien (consommée UNE fois, pas de boucle)")

CAS2 = FauxAppDemandes(resolu=True)
CAS2._astro_tour = lambda st: CAS2.appels.append("astro")   # ne résout rien
app_mod.App._servir_demandes_sans_frame(CAS2)
verifie(CAS2.appels == ["astro"],
        "WCS déjà résolu : photo et SPCC ne sont PAS relancées")


class FauxAppFin:
    def __init__(self):
        self._source_epuisee = False
        self._astro_demande = False
        self._astro_actif = True
        self.suivi_astro = FauxSuivi(False)
        self._cadence_dossier = lambda: True


CAS = FauxAppFin()
worker_mod.AcquisitionWorker._armer_astro_fin_source(CAS)
verifie(CAS._astro_demande is True,
        "fin de source (dossier) + WCS manquant : demande ARMÉE")
CAS._astro_demande = False
worker_mod.AcquisitionWorker._armer_astro_fin_source(CAS)
verifie(CAS._astro_demande is False,
        "…UNE seule fois : la transition n'est pas rejouée à chaque tour")
CAS._source_epuisee = False          # une frame est repassée
worker_mod.AcquisitionWorker._armer_astro_fin_source(CAS)
verifie(CAS._astro_demande is True,
        "une nouvelle frame puis l'épuisement : la demande est réarmée")
CAS._astro_actif = False
CAS._source_epuisee = False
CAS._astro_demande = False
worker_mod.AcquisitionWorker._armer_astro_fin_source(CAS)
verifie(CAS._astro_demande is False, "astrométrie décochée : rien n'est armé")
CAS._astro_actif = True
CAS.suivi_astro.resolu = True
CAS._source_epuisee = False
worker_mod.AcquisitionWorker._armer_astro_fin_source(CAS)
verifie(CAS._astro_demande is False, "WCS déjà résolu : rien n'est armé")
CAS.suivi_astro.resolu = False
CAS._cadence_dossier = lambda: False
CAS._source_epuisee = False
worker_mod.AcquisitionWorker._armer_astro_fin_source(CAS)
verifie(CAS._astro_demande is False and CAS._source_epuisee is False,
        "caméra LIVE : jamais d'armement (un read() vide n'est pas une fin)")



class FauxAppOnAstro:
    def __init__(self, actif=True, indices=None, resolu=False,
                 actif_avant=False):
        self.var_astro = FauxVar(actif)
        self.var_astro_ra = FauxVar("10.68")
        self.var_astro_dec = FauxVar("41.27")
        self.var_astro_champ = FauxVar("2.64")
        self.suivi_astro = FauxSuivi(resolu)
        self.suivi_astro.indice = lambda *a: False
        self.suivi_astro.reset = lambda: None
        self._astro_actif = actif_avant
        self._astro_indices = indices
        self._astro_demande = False
        self._astro_name_proposed = False
        self._astro_msg_indices = ""
        self._astro_source = ""
        self._astro_champ_seul = None
        self.astro_info = ""
        self.astro_couleur = "#888888"
        self._rafraichir_rendu = False
        self._maj_astro_vue = lambda: None
        self._demander_mesures = lambda *a, **k: None


CAS = FauxAppOnAstro()
app_mod.App._on_astro(CAS)
verifie(CAS._astro_demande is True, "cochage de l'astrométrie : demande POSÉE")
CAS = FauxAppOnAstro(indices=(10.68, 41.27, 2.64), resolu=True,
                     actif_avant=True)
app_mod.App._on_astro(CAS)
verifie(CAS._astro_demande is False,
        "mêmes indices + WCS résolu : aucune demande inutile")
CAS._astro_indices = (1.0, 2.0, 3.0)                  # indices différents
app_mod.App._on_astro(CAS)
verifie(CAS._astro_demande is True, "changement d'INDICES : demande POSÉE")
CAS = FauxAppOnAstro(actif=False)
app_mod.App._on_astro(CAS)
verifie(CAS._astro_demande is False, "astrométrie décochée : aucune demande")


# ================================================ [6] garde FILTER
print("\n[6] garde FILTER : modèle de filtres inadapté → avertissement ROUGE")
from astropy.io import fits              # noqa: E402 (FITS à en-tête)

BRUTE = os.path.join(TMP, "brute.fit")
ENTETE = fits.Header()
ENTETE["FILTER"] = "QHYCCD_MiniCam8M_Red"
fits.PrimaryHDU(np.zeros((4, 4), np.float32), ENTETE).writeto(BRUTE)


class FauxGarde:
    def __init__(self, filtres):
        self._filtres = filtres
        self._spcc_osc = lambda: False
        self._brute_courante = lambda: BRUTE
        self._spcc_profils = lambda: ("Sony IMX585", self._filtres,
                                      "Average Spiral Galaxy")


SP.profils_filtres = lambda: PROFILS
GARDE = FauxGarde({"R": "Antlia R", "G": "Antlia G", "B": "Antlia B"})
MSG = app_mod.App._spcc_garde_filtre(GARDE)
verifie("≠ modèle" in MSG and "Antlia" in MSG,
        f"modèle incompatible : averti (« {MSG[:52]}… »)")
GARDE2 = FauxGarde({"R": "QHYCCD MiniCam8M Red",
                    "G": "QHYCCD MiniCam8M Green",
                    "B": "QHYCCD MiniCam8M Blue"})
verifie(app_mod.App._spcc_garde_filtre(GARDE2) == "",
        "même modèle que le FILTER de la brute : aucun avertissement")
ENTETE = fits.Header()
ENTETE["FILTER"] = "R"
fits.PrimaryHDU(np.zeros((4, 4), np.float32), ENTETE).writeto(BRUTE,
                                                              overwrite=True)
verifie(app_mod.App._spcc_garde_filtre(GARDE) == "",
        "FILTER réduit à un rôle (« R ») : rien à conclure, aucun bruit")
SP.profils_filtres = _vrai_profils


# ================================================ [7] UI réelle : listes SPCC
print("\n[7] UI réelle : la liste du filtre R propose les filtres MONO (MiniCam)")
try:
    import tkinter as tk            # noqa: PLC0415 (pas de Tk au chargement)
    root = tk.Tk()
    root.withdraw()
except Exception as exc:            # pas d'affichage : contrôle ignoré
    print(f"  (Tk indisponible : contrôle ignoré — {exc})")
else:
    app = app_mod.App(root)
    for _ in range(20):
        root.update()
    vals = tuple(app._spcc_cbs["fr"].cget("values"))
    if any("MiniCam" in v for v in vals):
        verifie(app._spcc_vars["fr"].get() in vals,
                f"la valeur affichée « {app._spcc_vars['fr'].get()} » FIGURE "
                f"dans la liste R ({len(vals)} entrées)")
        verifie(any("MiniCam" in v for v in vals),
                "…et les filtres MiniCam sont proposés au clic")
        verifie(bool(app._spcc_correction) and not app._spcc_alerte,
                "le profil corrigé est annoncé en AVIS (ambre), pas en alerte")
        app._effacer_spcc_correction()
        verifie(not app._spcc_correction and not app._spcc_alerte,
                "l'avis s'efface ensuite sans laisser de rouge permanent")
    else:
        print("  (base réelle sans MiniCam : contrôles UI ignorés)")
    if app._spcc_correction_after is not None:
        try:
            root.after_cancel(app._spcc_correction_after)
        except Exception:
            pass
        app._spcc_correction_after = None
    root.destroy()


# ================================================ nettoyage et verdict
config_mod.CONFIG.clear()
config_mod.CONFIG.update(_vraie_config)
shutil.rmtree(TMP, ignore_errors=True)
print("\n" + ("TOUT OK — Lot 1 (P2 + P3) vérifié."
              if ok else "ÉCHECS — voir ci-dessus."))
raise SystemExit(0 if ok else 1)

