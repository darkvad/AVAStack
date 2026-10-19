# -*- coding: utf-8 -*-
"""Banc v2.94.0 — P1 (lot 2) : CADENCE DE RE-MESURE, sur le chemin de DÉCISION.

DÉFAUT CORRIGÉ (liste d'Alain du 19/10/2026) : astrométrie, gains Gaia et SPCC
mesuraient UNE fois — dès 3 frames — puis restaient `valide` ; un empilement
passé de 3 à 80 frames gardait la mesure faite sur 3.

Vérifie, SANS aucune mesure réelle (espion sur `mesurer`) :
  [1] politique pure `CadenceMesure` : seuil, doublement, délai, plafond,
      passe finale (prioritaire sur le délai et le plafond) ;
  [2] chemin de DÉCISION du worker `_photo_tour` : suite de profondeurs
      1→24 → mesures à 3, 6, 12 (et 24 hors plafond), un ÉCHEC ne consomme pas
      le quota des succès, la profondeur mesurée est celle de la mesure ;
  [3] `_spcc_tour` : même cadence, la profondeur vient de `_profondeur_spcc`
      (par rôle en composition, jamais la somme) ;
  [4] PASSE FINALE : la source s'épuise → une dernière mesure à la profondeur
      atteinte, UNE seule fois (pas de boucle) ;
  [5] astrométrie : le WCS résolu n'est JAMAIS re-solu ; la profondeur de la
      mesure est consignée pour l'état.

Exécution : python bancs/_test_p1_cadence.py
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc))
        break

import sys
import types

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon

from avastack.core import worker as worker_mod
from avastack.processing.cadence import (CadenceMesure, DELAI_MIN_S,
                                         MAX_REMESURES, SEUIL_PROFONDEUR,
                                         suffixe_etat)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


class FauxPhoto:
    """Espion : compte les mesures, peut échouer."""

    def __init__(self, ok_mesure=True):
        self.erreur = ok_mesure
        self.appels = []
        self.derniere_erreur = ""

    @property
    def valide(self):
        return bool(self.appels) and self.erreur

    def mesurer(self, canaux, wcs, forme=None):
        self.appels.append(tuple(sorted(canaux)))
        if not self.erreur:
            self.derniere_erreur = "échec simulé"
            return None, self.derniere_erreur
        return {"R": 1.0, "G": 1.0, "B": 1.0}, "mesure simulée"


class FauxSpcc(FauxPhoto):
    def __init__(self, ok_mesure=True):
        super().__init__(ok_mesure)
        self.diag = {}
        self.coefficients = np.ones(3)

    @property
    def valide(self):
        return bool(self.appels) and self.erreur

    def mesurer(self, canaux, wcs, capteur, filtres, blanc, forme=None,
                mode=None):
        self.appels.append((capteur, mode))
        if not self.erreur:
            self.derniere_erreur = "échec simulé"
            return None, self.derniere_erreur
        return {"coefficients": [1.0, 1.0, 1.0]}, "SPCC simulée"


class FauxSuivi:
    def __init__(self, resolu=False):
        self.resolu = resolu
        self.resolutions = 0

    def resoudre_sur(self, img, n_frames=None):
        self.resolutions += 1
        self.resolu = True
        return True, "résolu (simulé)"


def empilement(n):
    return types.SimpleNamespace(n=int(n))


class Hote:
    """Hôte minimal : les méthodes du mixin sont appelées NON liées."""

    def __init__(self, n, photo=None, spcc=None, suivi=None, cadence=None,
                 mode_compo=False, source_rgb=True):
        self.stacker = empilement(n)
        self.photometrie = photo or FauxPhoto()
        self.spcc = spcc or FauxSpcc()
        self.suivi_astro = suivi or FauxSuivi(True)
        self._photo_actif = True
        self._spcc_actif = True
        self._spcc_dispo = True
        self._mode_compo = mode_compo
        self._source_epuisee = False
        self._photo_essais = 0
        self._photo_dernier = 0.0
        self._spcc_essais = 0
        self._spcc_dernier = 0.0
        self._photo_raison = ""
        self._spcc_raison = ""
        self._cadence_photo = cadence or CadenceMesure("photo", delai_s=0.0)
        self._cadence_spcc = cadence or CadenceMesure("spcc", delai_s=0.0)
        self._cadence_astro = CadenceMesure("astro")
        self.photo_info = ""
        self.spcc_info = ""
        self.photo_couleur = self.spcc_couleur = ""
        self._profondeur = None       # profondeur scriptée (compo)
        self._source_rgb = lambda st: source_rgb
        self._profondeur_astro = lambda st: int(st.n)
        self._profondeur_spcc = (lambda st: int(self._profondeur)
                                 if self._profondeur is not None
                                 else int(st.n))
        self._photo_canaux = lambda st: ({"R": np.zeros((2, 2)),
                                          "G": np.zeros((2, 2)),
                                          "B": np.zeros((2, 2))},
                                         object(), (2, 2))
        self._spcc_profils = lambda: ("capteur", {"R": "r", "G": "g",
                                                  "B": "b"}, "blanc")
        self._spcc_garde_filtre = lambda: ""
        self._spcc_osc = lambda: False
        # Espions d'affichage : aucune IHM ici.
        self._maj_photo_etat = lambda: None
        self._maj_spcc_etat = lambda: None
        self._maj_spcc_vue = lambda: None
        self._maj_astro_etat = lambda: None


def photo(cas):
    worker_mod.AcquisitionWorker._photo_tour(cas, cas.stacker)


def spcc(cas):
    worker_mod.AcquisitionWorker._spcc_tour(cas, cas.stacker)


class Horloge:
    """Horloge monotone pilotée par le banc (`worker.time.monotonic`)."""
    t = 0.0

    def monotonic(self):
        return self.t


# ================================================ [1] politique pure
print("\n[1] CadenceMesure : seuil, doublement, délai, plafond, passe finale")
cad = CadenceMesure("test")
verifie(cad.seuil == SEUIL_PROFONDEUR == 3,
        f"seuil = ASTRO_MIN_FRAMES ({cad.seuil})")
verifie(not cad.doit_mesurer(2, 0.0)[0], "2 frames : trop court")
verifie(cad.doit_mesurer(3, 0.0)[0], "3 frames : première mesure")
cad.noter_mesure(3, 0.0)
verifie(not cad.doit_mesurer(4, 100.0)[0], "4 frames : pas de doublement")
verifie(not cad.doit_mesurer(6, 5.0)[0], "6 frames mais délai en cours")
verifie(cad.doit_mesurer(6, DELAI_MIN_S + 1.0)[0],
        f"6 frames + {DELAI_MIN_S:.0f} s : re-mesure")
cad.noter_mesure(6, DELAI_MIN_S + 1.0)
verifie(cad.cible() == 12, "cible suivante = 12 frames (6 doublé)")
verifie(MAX_REMESURES >= 4, f"plafond de re-mesures ({MAX_REMESURES})")
c2 = CadenceMesure("plafond", delai_s=0.0, max_remesures=1)
c2.noter_mesure(3, 0.0)
c2.noter_mesure(6, 1.0)
verifie(not c2.doit_mesurer(12, 2.0)[0], "plafond atteint : plus de re-mesure")
verifie(c2.doit_mesurer(12, 2.0, fin_source=True)[0],
        "passe finale : PRIORITAIRE sur le plafond")
verifie(not c2.doit_mesurer(6, 2.0, fin_source=True)[0],
        "passe finale refusée si la profondeur n'a pas bougé")
c2b = CadenceMesure("etat", delai_s=0.0)
c2b.noter_mesure(6, 0.0)
verifie("12" in suffixe_etat(c2b, 6), "l'état annonce la cible (12 frames)")
c3 = CadenceMesure("delai", delai_s=60.0)
c3.noter_mesure(6, 0.0)
verifie("délai" in suffixe_etat(c3, 12),
        "profondeur atteinte mais délai : l'état le dit")

# ================================================ [2] chemin de décision (photo)
print("\n[2] _photo_tour : mesures à 3, 6, 12, 24 — jamais avant, jamais à 4-5")
vrai_time = worker_mod.time
horloge = Horloge()
worker_mod.time = horloge
cas = Hote(0)
for n in range(1, 25):
    cas.stacker.n = n
    horloge.t = n * 10.0
    photo(cas)
verifie(len(cas.photometrie.appels) == 4,
        f"4 mesures pour 24 frames (reçu {len(cas.photometrie.appels)})")
verifie(cas._cadence_photo.profondeur == 24,
        f"profondeur mesurée = 24 (reçu {cas._cadence_photo.profondeur})")
verifie(cas._cadence_photo.remesures == 3,
        "3 RE-mesures (la première n'en est pas une)")
verifie(cas._photo_essais == 0,
        "trois succès ne consomment PAS le quota d'échecs")

print("    échec : le quota d'échecs est consommé, pas celui des succès")
cas2 = Hote(0, photo=FauxPhoto(ok_mesure=False))
for n in (3, 4):
    cas2.stacker.n = n
    horloge.t += 25.0
    photo(cas2)
verifie(cas2._photo_essais == 2, "2 échecs comptés dans `_photo_essais`")
verifie(not cas2._cadence_photo.deja_mesure,
        "un échec n'inscrit AUCUNE mesure réussie (cadence vierge)")

# ================================================ [3] SPCC : profondeur par rôle
print("\n[3] _spcc_tour : même cadence, profondeur = `_profondeur_spcc`")
cas3 = Hote(3, spcc=FauxSpcc())
cas3._profondeur = 3
for n in (3, 6, 12, 40):
    cas3.stacker.n = n
    cas3._profondeur = 3          # la profondeur des BANDES ne bouge pas
    horloge.t += 60.0
    spcc(cas3)
verifie(len(cas3.spcc.appels) == 1,
        f"1 seule mesure : la SOMME (40) ne compte pas (reçu {len(cas3.spcc.appels)})")
cas3._profondeur = 6
horloge.t += 60.0
spcc(cas3)
verifie(len(cas3.spcc.appels) == 2,
        "les bandes passent à 6 frames → re-mesure")
verifie(cas3.spcc.appels[-1] == ("capteur", "mono"),
        "profils et mode transmis à la mesure")

# ================================================ [4] passe finale
print("\n[4] Passe finale : la source s'épuise, la mesure part UNE fois")
cas4 = Hote(6)
photo(cas4)                      # mesure à 6
verifie(len(cas4.photometrie.appels) == 1, "mesure initiale à 6 frames")
cas4.stacker.n = 7
cas4._source_epuisee = True
photo(cas4)
verifie(len(cas4.photometrie.appels) == 2,
        "passe finale à 7 frames (la source ne grandira plus)")
verifie(cas4._cadence_photo.finales == 1, "passe finale comptée")
photo(cas4)
verifie(len(cas4.photometrie.appels) == 2, "pas de boucle : rien de plus à 7")

# ================================================ [5] astrométrie
print("\n[5] Astrométrie : WCS résolu = jamais re-solu, profondeur consignée")
cas5 = Hote(9, suivi=FauxSuivi(True))
worker_mod.AcquisitionWorker._astro_tour(cas5, cas5.stacker)
verifie(cas5.suivi_astro.resolutions == 0,
        "WCS déjà résolu : AUCUN appel au solveur")
verifie(cas5._cadence_astro.deja_mesure
        and cas5._cadence_astro.profondeur == 9,
        "profondeur de la mesure consignée (9 frames)")
worker_mod.AcquisitionWorker._astro_tour(cas5, cas5.stacker)
verifie(cas5._cadence_astro.mesures == 1, "deuxième tour : aucune re-mesure")

worker_mod.time = vrai_time
print()
print("BANC P1 : " + ("VERT" if ok else "ÉCHEC"))
sys.exit(0 if ok else 1)
