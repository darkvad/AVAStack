# -*- coding: utf-8 -*-
"""Test rapide : déduplication céleste avec le FICHIER RÉEL d'Alain."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from avastack.catalogues.celebres import cherche_celebres

# Coordonnées M31 (résolues par l'astrométrie, cf. journal Alain)
ra, dec, rayon = 10.6833, 41.2686, 0.5
res = cherche_celebres(ra, dec, rayon)
print(f"Trouve: {len(res)} objets (bruts, AVANT déduplication)")
for o in res:
    print(f"  {o.designation!r} | {o.type_obj} | mag={o.mag_v} | size={o.size_arcmin:.1f}' "
          f"| ra={o.ra_deg:.5f} dec={o.dec_deg:.5f}")

# Déduplication par position (même logique que _objets_celestes_resolus)
import re

def sanitize(nom):
    nom = re.sub(r"[\\/:*?\"<>]", "_", nom)
    nom = re.sub(r"[\x00-\x1f]", "", nom)
    nom = re.sub(r"\s+", " ", nom).strip(" .")
    return nom

def score_nom(s):
    s2 = sanitize(s)
    if re.fullmatch(r"M\s*\d+", s2):
        return 0
    if re.fullmatch(r"(NGC|IC)\s*\d+", s2):
        return 1
    if re.fullmatch(r"(Sh2-|Barnard\s*|LDN\s*)\d+", s2):
        return 2
    if re.search(r"\d", s2) and len(s2) >= 3 and not s2[-1].isspace():
        return 3
    return 4

import math
cosd = math.cos(math.radians(dec))
groupes = {}
for o in res:
    cle = (round(o.ra_deg * 100), round(o.dec_deg * 100))
    groupes.setdefault(cle, []).append(o)

def meilleur_du_groupe(g):
    def clef(o):
        dra = (o.ra_deg - ra + 180.0) % 360.0 - 180.0
        dist2 = (dra * cosd) ** 2 + (o.dec_deg - dec) ** 2
        return (score_nom(o.designation), dist2, o.mag_v or 99.0)
    return min(g, key=clef)

def clef_tri(o):
    dra = (o.ra_deg - ra + 180.0) % 360.0 - 180.0
    dist2 = (dra * cosd) ** 2 + (o.dec_deg - dec) ** 2
    return (dist2, o.mag_v or 99.0)

reps = [meilleur_du_groupe(g) for g in groupes.values()]
reps.sort(key=clef_tri)

print(f"\nAPRÈS déduplication : {len(reps)} objets distincts")
for o in reps:
    nom = sanitize(o.designation)
    sc = score_nom(o.designation)
    print(f"  {nom!r} | {o.type_obj} | mag={o.mag_v} | score={sc}")

assert len(reps) == 2, f"2 objets distincts attendus (M31 + M32), obtenu {len(reps)}"
assert score_nom(reps[0].designation) == 0, "le premier doit être « M 31 » (Messier)"
print("\nTEST OK : « M 31 » sélectionné, pas « 224 »")
