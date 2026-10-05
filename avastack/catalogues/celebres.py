# -*- coding: utf-8 -*-
"""Catalogue local d'objets célestes célèbres (Messier, NGC, IC, Sh2, Barnard, LDN).

Format : HEALpix NESTED niveau 8, compatible avec le format « Siril HEALpixel Catalog »
(128 octets d'en-tête + index uint32 cumulatif + enregistrements fixes).

Sources VizieR (publiques, CC-BY 4.0 compatible) :
  • VII/258  — Messier (110 objets)
  • VII/118  — NGC 2000.0 (~13 200 objets)
  • VII/260  — IC (~5 300 objets)
  • J/ApJS/59/1  — Sharpless H II regions (Sh2, ~313)
  • J/AJ/117/349 — Barnard dark nebulae (~350)
  • ApJS/179/1   — LDN (Lynds Dark Nebulae, ~1800)

Le module fournit :
  - `telecharger_et_indexer(dossier)` : télécharge les CSV VizieR, écrit `celebres_healpix8.dat`
  - `cherche_celebres(ra, dec, rayon_deg)` → liste d'ObjetCelebre triés par proximité/éclat
"""

import csv
import gzip
import math
import os
import re
import struct
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from . import healpix
from .telechargeur import _EN_TETES

# ──────────────────────────────────────────────────────────────────────────
# Enregistrement de l'objet célèbre (en mémoire)
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True)
class ObjetCelebre:
    designation: str
    aliases: List[str]
    type_obj: str
    mag_v: Optional[float]
    size_arcmin: float
    ra_deg: float
    dec_deg: float
    healpix8: int


# ──────────────────────────────────────────────────────────────────────────
# Constantes du format binaire
# ──────────────────────────────────────────────────────────────────────────
TAILLE_ENTETE = 128
TYPE_CELEBRES = 4
NIVEAU = 8
NPIX_NIVEAU8 = healpix.NPIX_NIVEAU8
# RA/Dec stockés : deg × (2³¹−1)/360 (format Siril)
ECHELLE_ANGLE = 360.0 / (2 ** 31 - 1)

TAILLE_ENREG = 64

TYPE_MAP = {
    "galaxy": 0, "galaxie": 0,
    "diffuse nebula": 1, "nebuleuse_diffuse": 1, "bright nebula": 1,
    "planetary nebula": 2, "nebuleuse_planetaire": 2,
    "open cluster": 3, "amas_ouvert": 3,
    "globular cluster": 4, "amas_globulaire": 4,
    "dark nebula": 5, "nebuleuse_obscure": 5,
    "HII region": 6, "region_HII": 6, "emission nebula": 6,
    "supernova remnant": 1, "nebula": 1,
    "cluster": 3, "association": 3,
}

VIZIER_BASE = "https://vizier.cds.unistra.fr/viz-bin/VizieR-3"
CATALOGUES_VIZIER = [
    ("messier.csv.gz", "VII/258/messier",
     ["RAJ2000", "DEJ2000", "Name", "Type", "Vmag", "Size"],
     {"Gx": "galaxie", "PN": "nebuleuse_planetaire", "Cl": "amas_ouvert",
      "Gb": "amas_globulaire", "Nb": "nebuleuse_diffuse", "DNe": "nebuleuse_diffuse"}),
    ("ngc2000.csv.gz", "VII/118/ngc2000",
     ["RAJ2000", "DEJ2000", "NGC", "Type", "Vmag", "Size"],
     {"Gx": "galaxie", "PN": "nebuleuse_planetaire", "Cl": "amas_ouvert",
      "Gb": "amas_globulaire", "Nb": "nebuleuse_diffuse", "DNe": "nebuleuse_diffuse",
      "Ast": "amas_ouvert", "OC": "amas_ouvert", "GC": "amas_globulaire"}),
    ("ic.csv.gz", "VII/260/ic",
     ["RAJ2000", "DEJ2000", "IC", "Type", "Vmag", "Size"],
     {"Gx": "galaxie", "PN": "nebuleuse_planetaire", "Cl": "amas_ouvert",
      "Gb": "amas_globulaire", "Nb": "nebuleuse_diffuse", "DNe": "nebuleuse_diffuse"}),
    ("sharpless.csv.gz", "J/ApJS/59/table1",
     ["RAJ2000", "DEJ2000", "Sh2", "Size"],
     {"HII": "region_HII"}),
    ("barnard.csv.gz", "J/AJ/117/349/table1",
     ["RAJ2000", "DEJ2000", "Barnard", "Size"],
     {"DNe": "nebuleuse_obscure"}),
    ("ldn.csv.gz", "ApJS/179/table1",
     ["RAJ2000", "DEJ2000", "LDN", "Size"],
     {"DNe": "nebuleuse_obscure"}),
]


def _url_vizier(cat: str) -> str:
    return f"{VIZIER_BASE}?-source={cat}&-out.max=unlimited&-out.form=CSV"


def _telecharger_vizier(nom_fichier: str, catalogue: str, dossier: str, progression=None) -> str:
    chemin = os.path.join(dossier, nom_fichier)
    if os.path.isfile(chemin) and os.path.getsize(chemin) > 100:
        return chemin
    os.makedirs(dossier, exist_ok=True)
    url = _url_vizier(catalogue)
    req = urllib.request.Request(url, headers=_EN_TETES)
    tmp = chemin + ".part"
    with urllib.request.urlopen(req, timeout=120) as rep, open(tmp, "wb") as f:
        total = rep.length or 0
        lu = 0
        while True:
            bloc = rep.read(1 << 16)
            if not bloc:
                break
            f.write(bloc)
            lu += len(bloc)
            if progression and total:
                progression(nom_fichier, lu / total)
    os.replace(tmp, chemin)
    return chemin
# ──────────────────────────────────────────────────────────────────────────
# Parsing CSV → liste ObjetCelebre
# ──────────────────────────────────────────────────────────────────────────
def _lire_csv_gz(chemin: str, cols: List[str], type_map: dict, prefix: str) -> List[ObjetCelebre]:
    objets = []
    with gzip.open(chemin, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                ra = float(row.get(cols[0], "nan"))
                dec = float(row.get(cols[1], "nan"))
                if not (np.isfinite(ra) and np.isfinite(dec)):
                    continue
                nom_col = cols[2]
                nom = row.get(nom_col, "").strip()
                if not nom:
                    continue
                designation = f"{prefix}{nom}"
                type_raw = row.get(cols[3], "").strip()
                type_obj = type_map.get(type_raw, "nebuleuse_diffuse")
                mag_v = None
                if len(cols) > 4 and cols[4] in row:
                    v = row[cols[4]].strip()
                    if v and v not in ("", "nan", "NaN"):
                        try:
                            mag_v = float(v)
                        except ValueError:
                            pass
                size = 1.0
                if len(cols) > 5 and cols[5] in row:
                    s = row[cols[5]].strip()
                    if s:
                        try:
                            size = float(s)
                        except ValueError:
                            pass
                aliases = [designation]
                if prefix != "M" and not designation.startswith("M"):
                    if nom.isdigit():
                        aliases.append(f"M{nom}")
                hpix = healpix.ang2pix_nest(ra, dec, NIVEAU)
                objets.append(ObjetCelebre(
                    designation=designation,
                    aliases=aliases,
                    type_obj=type_obj,
                    mag_v=mag_v,
                    size_arcmin=size,
                    ra_deg=ra,
                    dec_deg=dec,
                    healpix8=int(hpix),
                ))
            except Exception:
                # Ignorer les lignes malformées
                continue
# ──────────────────────────────────────────────────────────────────────────
# Écriture format binaire Siril-compatible
# ──────────────────────────────────────────────────────────────────────────
def _ecrire_binaire(objets: List[ObjetCelebre], chemin: str):
    objets.sort(key=lambda o: o.healpix8)

    index = np.zeros(NPIX_NIVEAU8 + 1, dtype=np.uint32)
    for obj in objets:
        index[obj.healpix8 + 1] += 1
    np.cumsum(index, out=index)

    titre = "AVAStack Famous Objects Catalogue".ljust(48, "\x00")[:48].encode("ascii")
    release = 1
    niveau = NIVEAU
    ctype = TYPE_CELEBRES
    chunked = 0
    chunk_level = 0
    chunk = 0
    p_debut = 0
    p_fin = NPIX_NIVEAU8 - 1

    entete = bytearray(TAILLE_ENTETE)
    entete[:48] = titre
    entete[48] = release
    entete[49] = niveau
    entete[50] = ctype
    entete[51] = chunked
    entete[52] = chunk_level
    struct.pack_into("<III", entete, 53, chunk, p_debut, p_fin)

    tmp = chemin + ".part"
    with open(tmp, "wb") as f:
        f.write(entete)
        f.write(index.tobytes())
        for obj in objets:
            ra_s = int(round(obj.ra_deg / 360.0 * (2**31 - 1)))
            dec_s = int(round((obj.dec_deg + 90.0) / 180.0 * (2**31 - 1)))
            mag_v = np.float16(obj.mag_v) if obj.mag_v is not None else np.float16(np.nan)
            size = np.float16(obj.size_arcmin)
            type_code = TYPE_MAP.get(obj.type_obj, 1)
            designation = obj.designation[:30].encode("ascii", errors="ignore")
            aliases_str = ";".join(obj.aliases[:3])[:30].encode("ascii", errors="ignore")
            rec = struct.pack(
                "<iiHH ee HH I HHHH 16s 16s",
                ra_s, dec_s,
                0, 0,
                float(mag_v), float(size),
                type_code, 0,
                obj.healpix8,
                len(designation),
                0, 0, 0,
                designation.ljust(16, b"\x00"),
                aliases_str.ljust(16, b"\x00"),
            )
            f.write(rec)
    os.replace(tmp, chemin)


def _tous_les_objets(dossier: str, progression=None) -> List[ObjetCelebre]:
    tous = []
    for i, (fname, cat, cols, tmap) in enumerate(CATALOGUES_VIZIER):
        if progression:
            progression(f"Téléchargement {fname}", i / len(CATALOGUES_VIZIER))
        chemin = _telecharger_vizier(fname, cat, dossier, progression)
        prefix = {"messier.csv.gz": "M", "ngc2000.csv.gz": "NGC", "ic.csv.gz": "IC",
                  "sharpless.csv.gz": "Sh2-", "barnard.csv.gz": "Barnard",
                  "ldn.csv.gz": "LDN"}[fname]
        obj = _lire_csv_gz(chemin, cols, tmap, prefix)
        tous.extend(obj)
        if progression:
            progression(f"Parsing {fname}", (i + 1) / len(CATALOGUES_VIZIER))
    return tous
# ──────────────────────────────────────────────────────────────────────────
# Lecture du fichier binaire (recherche par cône)
# ──────────────────────────────────────────────────────────────────────────
# PIÈGE (retours d'Alain, 05/10/2026, « ? » après chaque nom) : le dict
# inverse de TYPE_MAP {v: k} faisait gagner le DERNIER synonyme (« nebula »),
# que TYPE_ICON (noms français) ne connaissait pas → icône « ? » partout.
# Table inverse EXPLICITE, en noms français (les mêmes clés que TYPE_ICON).
TYPE_CODE_VERS_NOM = {
    0: "galaxie", 1: "nebuleuse_diffuse", 2: "nebuleuse_planetaire",
    3: "amas_ouvert", 4: "amas_globulaire", 5: "nebuleuse_obscure",
    6: "region_HII",
}


def _designations_lisibles(designation: str, aliases: List[str]):
    """Noms LISIBLES pour l'affichage (retours d'Alain, 05/10/2026).
    Le générateur d'origine du .dat stockait les désignations NGC 2000 SANS
    préfixe (« 224 », « 206 ») et les beaux noms en alias SEULS (« M  32 »
    pour « 221 ») :
    - espaces internes compactés (« M  31 » → « M 31 ») ;
    - désignation « nombre nu » : on garde de préférence un alias PRÉFIXÉ
      (« 221 » + alias « M  32 » → « M 32 ») ;
    - à défaut, préfixe « NGC » : le générateur d'origine ne stockait les
      nombres nus QUE pour NGC 2000 (pas de CSV IC séparé). No-op sur le
      format nouveau, qui préfixe déjà (« NGC224 »).
    → (designation, aliases) nettoyés."""
    d = " ".join(str(designation).split())
    aliases = [a for a in (_nom_propre(a) for a in aliases) if a and a != d]
    if re.fullmatch(r"\d+", d):
        meilleur = min(aliases, key=score_designation, default=None)
        if meilleur is not None and score_designation(meilleur) <= 2:
            d = meilleur
        else:
            d = "NGC " + d
    return d, aliases


class CatalogueCelebres:
    def __init__(self, chemin: str):
        self.chemin = chemin
        self._f = open(chemin, "rb")
        self.entete = self._lire_entete()
        self.index = self._lire_index()

    def _lire_entete(self):
        ent = self._f.read(TAILLE_ENTETE)
        if len(ent) != TAILLE_ENTETE:
            raise ValueError(f"En-tête tronqué : {self.chemin}")
        return {
            "titre": ent[:48].split(b"\x00")[0].decode("ascii", errors="replace").strip(),
            "release": ent[48],
            "niveau": ent[49],
            "type": ent[50],
            "chunked": bool(ent[51]),
            "chunk_level": ent[52],
            "chunk": int.from_bytes(ent[53:57], "little"),
            "pixel_debut": int.from_bytes(ent[57:61], "little"),
            "pixel_fin": int.from_bytes(ent[61:65], "little"),
        }

    def _lire_index(self):
        data = self._f.read(NPIX_NIVEAU8 * 4 + 4)
        return np.frombuffer(data, dtype="<u4")

    def chercher(self, ra: float, dec: float, rayon_deg: float) -> List[ObjetCelebre]:
        pix = healpix.pixels_cone(ra, dec, rayon_deg)
        if pix.size == 0:
            return []

        resultats = []
        cosd = np.cos(np.radians(dec))
        for hpix in pix:
            deb = self.index[hpix]
            fin = self.index[hpix + 1]
            if deb == fin:
                continue
            self._f.seek(TAILLE_ENTETE + (NPIX_NIVEAU8 + 1) * 4 + deb * TAILLE_ENREG)
            for _ in range(fin - deb):
                rec_bytes = self._f.read(TAILLE_ENREG)
                if len(rec_bytes) != TAILLE_ENREG:
                    break
                (ra_s, dec_s, dra, ddec, mag_v, size_arcmin,
                 type_code, _pad, healpix8, name_len,
                 _pad2, _pad3, _pad4,
                 designation, aliases) = struct.unpack("<iiHH ee HH I HHHH 16s 16s", rec_bytes)

                ra_obj = ra_s * 360.0 / (2**31 - 1)
                dec_obj = dec_s * 180.0 / (2**31 - 1) - 90.0

                dra_deg = (ra_obj - ra + 180.0) % 360.0 - 180.0
                if (dra_deg * cosd) ** 2 + (dec_obj - dec) ** 2 > rayon_deg * rayon_deg:
                    continue

                mag = float(mag_v) if not np.isnan(mag_v) else 99.0
                designation = (designation.split(b"\x00")[0]
                               .decode("ascii", errors="ignore").strip())
                aliases = (aliases.split(b"\x00")[0]
                           .decode("ascii", errors="ignore"))
                aliases_list = [" ".join(a.split())
                                for a in aliases.split(";") if a.strip()]
                # Le générateur d'ORIGINE du .dat (généré localement, cf.
                # AVANCEMENT 03/10/2026) stockait les désignations NGC SANS
                # préfixe (« 224 ») et les beaux noms en alias SEULS (« M  32 »
                # pour « 221 ») — retours d'Alain 05/10/2026 : étiquette
                # « 206 (?) » pour NGC 206, icône « ? » partout.
                designation, aliases_list = _designations_lisibles(
                    designation, aliases_list)
                type_obj = TYPE_CODE_VERS_NOM.get(type_code,
                                                  "nebuleuse_diffuse")

                resultats.append(ObjetCelebre(
                    designation=designation,
                    aliases=aliases_list or [designation],
                    type_obj=type_obj,
                    mag_v=mag if mag < 99 else None,
                    size_arcmin=float(size_arcmin),
                    ra_deg=ra_obj,
                    dec_deg=dec_obj,
                    healpix8=healpix8,
                ))

        def clef(o):
            dra = (o.ra_deg - ra + 180.0) % 360.0 - 180.0
            dist2 = (dra * cosd) ** 2 + (o.dec_deg - dec) ** 2
            return (dist2, o.mag_v or 99.0)

        resultats.sort(key=clef)
        return resultats

    def close(self):
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


_catalogue_global: Optional[CatalogueCelebres] = None
_catalogue_path: Optional[str] = None


def _catalogue(dossier: str) -> CatalogueCelebres:
    global _catalogue_global, _catalogue_path
    chemin = os.path.join(dossier, "celebres_healpix8.dat")
    if _catalogue_global is None or _catalogue_path != chemin:
        if _catalogue_global:
            _catalogue_global.close()
        _catalogue_global = CatalogueCelebres(chemin)
        _catalogue_path = chemin
    return _catalogue_global


# ──────────────────────────────────────────────────────────────────────────
# API publique
# ──────────────────────────────────────────────────────────────────────────
def telecharger_et_indexer(dossier: str, progression=None) -> str:
    os.makedirs(dossier, exist_ok=True)
    if progression:
        progression("Téléchargement catalogues VizieR", 0.0)
    objets = _tous_les_objets(dossier, progression)
    if progression:
        progression(f"Indexation {len(objets)} objets", 0.8)
    chemin = os.path.join(dossier, "celebres_healpix8.dat")
    _ecrire_binaire(objets, chemin)
    if progression:
        progression("Terminé", 1.0)
    global _catalogue_global, _catalogue_path
    if _catalogue_global:
        _catalogue_global.close()
    _catalogue_global = None
    _catalogue_path = None
    return chemin


def est_disponible(dossier: str = None) -> bool:
    from ..catalogues import dossier_catalogues
    d = dossier or dossier_catalogues()
    return os.path.isfile(os.path.join(d, "celebres_healpix8.dat"))


def cherche_celebres(ra: float, dec: float, rayon_deg: float, dossier: str = None) -> List[ObjetCelebre]:
    from ..catalogues import dossier_catalogues
    d = dossier or dossier_catalogues()
    cat = _catalogue(d)
    return cat.chercher(ra, dec, rayon_deg)


def _nom_propre(nom: str) -> str:
    """Nom compacté pour le classement (« M  31 » → « M31 »)."""
    return " ".join(str(nom).split()).strip(" .")


def score_designation(nom: str) -> int:
    """0 = le meilleur : « M31 » (Messier), puis « NGC… »/« IC… » avec
    préfixe, puis Sh2/Barnard/LDN, puis tout nom exploitable ; un nombre nu
    (« 224 ») ou un nom tronqué (« Great Nebula in ») est le pire.
    Sert à choisir le représentant d'un groupe de doublons (M31 ≡ NGC 224) —
    cf. banc `bancs/_test_dedup_celebre_jalon96.py` (données réelles : le
    catalogue brut renvoie M31, NGC 224 ET « 224 » aux mêmes coordonnées)."""
    s = _nom_propre(nom)
    if re.fullmatch(r"M\s*\d+", s):
        return 0
    if re.fullmatch(r"(NGC|IC)\s*\d+", s):
        return 1
    if re.fullmatch(r"(Sh2-|Barnard\s*|LDN\s*)\d+", s):
        return 2
    if re.search(r"\d", s) and len(s) >= 3 and not s[-1].isspace():
        return 3
    return 4


def deduplique_celebres(objets: List[ObjetCelebre],
                        ra_centre: float = None,
                        dec_centre: float = None) -> List[ObjetCelebre]:
    """Une SEULE entrée par position (~0,01° : même objet vu par plusieurs
    catalogues — « NGC 224 » et « M31 ») : un représentant par groupe, choisi
    par `score_designation` (Messier d'abord), puis distance au centre fourni
    puis éclat ; la liste finale est triée par distance puis éclat.
    Utilisée par l'annotation temps-réel (UNE étiquette par objet — les
    doublons empilaient leurs textes au même endroit, illisibles, constat
    Alain sur M31) et par le nom de cible (jamais « 224 » si « M31 » existe)."""
    if not objets:
        return []
    cosd = (math.cos(math.radians(dec_centre))
            if dec_centre is not None else 0.0)

    def dist2(o: ObjetCelebre) -> float:
        if ra_centre is None or dec_centre is None:
            return 0.0
        dra = (o.ra_deg - ra_centre + 180.0) % 360.0 - 180.0
        return (dra * cosd) ** 2 + (o.dec_deg - dec_centre) ** 2

    groupes = {}
    for o in objets:
        cle = (round(o.ra_deg * 100), round(o.dec_deg * 100))
        groupes.setdefault(cle, []).append(o)

    reps = [min(g, key=lambda o: (score_designation(o.designation),
                                  dist2(o), o.mag_v or 99.0))
            for g in groupes.values()]
    reps.sort(key=lambda o: (dist2(o), o.mag_v or 99.0))
    return reps