# -*- coding: utf-8 -*-
"""Banc de la jauge `postes` — NOMMER LE RÉSIDUEL (branche `OptimisationUI`, 21/10/2026).

POURQUOI : la réconciliation mémoire laissait **555,6 Mio** (relevé `perf-8`)
qu'aucune jauge ne nommait. `perf.postes_memoire(obj)` range les tableaux de
l'application sous l'attribut de PREMIER niveau qui les tient — c'est cette
liste qui nomme le résiduel. Comme toute jauge, elle doit être RECOUPÉE avant
qu'on décide quoi que ce soit sur ses chiffres.

CE QUE CE BANC VERROUILLE
  [1] chaque tableau est rangé sous SON attribut de premier niveau, y compris
      à travers un conteneur (`dict`/`list`) et un objet du PROJET ;
  [2] DÉDUPLICATION par `id()` : une image aliasée par deux attributs (le piège
      du « Go inexpliqué ») n'est comptée qu'UNE fois ;
  [3] seuil : les tableaux < 64 Kio sont agrégés sous « petits tableaux » (le
      JSON ne doit pas contenir des milliers de lignes) ;
  [4] `exclure` : l'empileur n'est pas compté ici (il a SA jauge) ;
  [5] les objets ÉTRANGERS au projet (Tk, PIL, astropy, `types.SimpleNamespace`)
      ne sont PAS traversés — coût maîtrisé et aucun faux poste ;
  [6] `jauger_postes` : inactif ⇒ ne touche à RIEN ; actif ⇒ `postes`,
      `postes_mo` et `postes_nb_tableaux` atterrissent dans `instantane()`
      (`jauges`), donc dans le JSON `--perf` ;
  [7] COÛT : le parcours d'un graphe réaliste reste sous la seconde (large
      borne : on mesure un ordre de grandeur, pas une machine).

Exécution : python bancs/_test_p1_postes_memoire.py
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import sys
import time
import types

import numpy as np

from avastack import perf

if hasattr(sys.stdout, "reconfigure"):      # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MIO = 1024.0 * 1024.0
ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


class _FauxPoste:
    """Objet du PROJET (module `avastack…`) : doit être traversé."""

    def __init__(self, img):
        self.interne = {"n": 1, "img": img}
        self.rien = None


_FauxPoste.__module__ = "avastack.processing.faux"


class _Racine:
    def __init__(self):
        self.gros = np.zeros((64, 64, 3), np.float32)      # 48 Kio < seuil
        self.immense = np.zeros((512, 512), np.float32)    # 1 Mio
        self.alias = None
        self.imbrique = [_FauxPoste(np.zeros((256, 256), np.float32))]
        self.etranger = types.SimpleNamespace(
            image=np.zeros((1024, 1024), np.float32))      # NE DOIT PAS entrer
        self.stacker = np.zeros((300, 300), np.float32)    # exclu


print("=" * 78)
print("[1] rangement par attribut de premier niveau (conteneurs et objets)")
print("=" * 78)
r = _Racine()
r.alias = r.immense                    # même tableau sous deux noms
tab = perf.postes_memoire(r, max_postes=8)
postes = tab["postes"]
verifie(postes.get("immense") == r.immense.nbytes,
        f"`immense` porte SES octets ({postes.get('immense', 0):,})")
verifie("alias" not in postes,
        "l'ALIAS n'apparaît pas : tableaux dédupliqués par `id()`")
verifie(postes.get("imbrique") == 256 * 256 * 4,
        "un objet du projet est traversé (son image est comptée sous "
        "`imbrique`)")
verifie("etranger" not in postes,
        "un objet ÉTRANGER (`types.SimpleNamespace` + 4 Mio) n'est PAS parcouru")
verifie("stacker" not in postes, "l'empileur est exclu (il a sa propre jauge)")
verifie(postes.get("petits tableaux") == r.gros.nbytes,
        "sous 64 Kio, agrégé : « petits tableaux » = "
        f"{postes.get('petits tableaux'):,}")
verifie(tab["total_octets"] == r.immense.nbytes + 256 * 256 * 4 + r.gros.nbytes,
        "total = somme des tableaux RÉELLEMENT atteints "
        f"({tab['total_octets']:,} o)")
verifie(tab["nb_tableaux"] == 3,
        f"3 tableaux comptés (immense+alias = 1) : {tab['nb_tableaux']}")
verifie("(autres)" not in postes,
        "top `max_postes` large ⇒ pas de ligne « (autres) » inutile")

print("=" * 78)
print("[2] « (autres) » : le plafond du rapport ne perd AUCUN octet")
print("=" * 78)
tab2 = perf.postes_memoire(r, max_postes=1)
verifie(len(tab2["postes"]) == 2 and "(autres)" in tab2["postes"],
        "plafond à 1 nom ⇒ le reste est agrégé sous « (autres) »")
verifie(sum(tab2["postes"].values()) == tab2["total_octets"],
        "la somme des lignes ÉGALE le total (rien ne disparaît du JSON)")

print("=" * 78)
print("[3] `jauger_postes` : inerte hors `--perf`, publiée DANS `instantane()`")
print("=" * 78)
perf.desactiver()
perf.jauger_postes(r)
verifie("postes" not in (perf.instantane().get("jauges") or {}),
        "instrumentation INACTIVE : la jauge ne publie rien (coût nul)")
perf.activer()
t0 = time.time()
perf.jauger_postes(r)
cout = (time.time() - t0) * 1000.0
jg = perf.instantane().get("jauges") or {}
verifie(isinstance(jg.get("postes"), dict) and jg["postes"].get("immense", 0) > 0,
        f"ACTIVE : `postes` est publiée (Mio par attribut) — {jg.get('postes')}")
attendu = round(tab["total_octets"] / MIO, 1)
verifie(jg.get("postes_mo") == attendu,
        f"`postes_mo` = {jg.get('postes_mo')} Mio (total attendu {attendu})")
verifie(jg.get("postes_nb_tableaux") == tab["nb_tableaux"],
        "`postes_nb_tableaux` publié")
verifie(cout < 1000.0, f"coût du parcours : {cout:.2f} ms (borne large < 1000)")
perf.desactiver()

print("=" * 78)
print("[4] graphe RÉALISTE : 40 tableaux, déduplication et coût")
print("=" * 78)
racine = _Racine()
for i in range(40):
    setattr(racine, f"poste_{i:02d}", np.zeros((128, 128), np.float32))
racine.alias2 = getattr(racine, "poste_00")
t0 = time.time()
gros = perf.postes_memoire(racine, max_postes=12)
cout = (time.time() - t0) * 1000.0
attendu = 40 * 128 * 128 * 4 + racine.immense.nbytes + 256 * 256 * 4 + 48 * 1024
verifie(gros["total_octets"] == attendu,
        f"total exact sur 40+ tableaux ({gros['total_octets']:,} o)")
verifie(gros["nb_tableaux"] == 43,
        "43 tableaux distincts (40 + immense + imbriqué + petits) : "
        f"{gros['nb_tableaux']}")
verifie(cout < 1000.0, f"coût sur 43 tableaux : {cout:.2f} ms")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)

