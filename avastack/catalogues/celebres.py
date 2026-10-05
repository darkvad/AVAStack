# -*- coding: utf-8 -*-
"""Catalogue local d'objets célestes célèbres (Messier, NGC, IC, Sh2, Barnard, LDN).

Format : HEALpix NESTED niveau 8, compatible avec le format « Siril HEALpixel Catalog »
(128 octets d'en-tête + index uint32 cumulatif + enregistrements fixes).

Sources (publiques ; jalon 97, 05/10/2026) :
  • OpenNGC (https://github.com/mattiaverga/OpenNGC, CC-BY-SA-4.0) — NGC+IC
    fusionnés, types PROPRES, cross-ids Messier (colonne M), tailles
    (MajAx en arcmin), noms communs ;
  • VizieR miroir Harvard (CC-BY-4.0), au format VOTable — VII/20 (Sharpless
    Sh2, coordonnées B1900), VII/220A (Barnard, B1875), VII/7A (Lynds LDN,
    B1950) ; coordonnées ICRS prises dans les colonnes _RA.icrs/_DE.icrs de
    VizieR (Barnard, LDN) ou converties par astropy (Sharpless).

PIÈGES (05/10/2026) : VizieR Strasbourg répond « Making sure you're not a
bot! » (Anubis) aux requêtes urllib ; le miroir Harvard rend les VOTables
complets mais son asu-tsv tronque le flux à ~81 Ko et ne rend RIEN pour les
trois tables ci-dessus. Les identifiants VII/258 (« catalogue Messier » du
générateur d'origine) désignent en réalité un catalogue de QUASARS, et
VII/260 n'existe pas en tant que table IC — d'où le .dat d'origine avec tous
les objets mal classés en « nébuleuse diffuse ».

Le module fournit :
  - `telecharger_et_indexer(dossier)` : télécharge OpenNGC + les VOTables,
    écrit `celebres_healpix8.dat`
  - `cherche_celebres(ra, dec, rayon_deg)` → liste d'ObjetCelebre triés par proximité/éclat
"""

import csv
import math
import os
import re
import struct
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
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

# URL du CSV OpenNGC (NGC+IC fusionnés, colonne « ; » — ~4 Mo, mis à jour
# régulièrement par son mainteneur ; licence CC-BY-SA-4.0 : CRÉDITER — cf.
# INSTALLATION.md et PRIVACY.md).
OPENNGC_URL = ("https://raw.githubusercontent.com/mattiaverga/OpenNGC/"
               "master/database_files/NGC.csv")
# Miroir Harvard (Strasbourg est derrière un anti-robot Anubis, cf. docstring).
VIZIER_HARVARD_VOTABLE = "https://vizier.cfa.harvard.edu/viz-bin/votable"

# Type OpenNGC → type AVAStack (noms français = clés de TYPE_MAP).
OPENNGC_TYPES = {
    "G": "galaxie", "GPair": "galaxie", "GTrpl": "galaxie",
    "GGroup": "galaxie",
    "OCl": "amas_ouvert", "*Ass": "amas_ouvert",        # NGC 206 = *Ass
    "GCl": "amas_globulaire",
    "PN": "nebuleuse_planetaire",
    "HII": "region_HII", "EmN": "region_HII",
    "Neb": "nebuleuse_diffuse", "RfN": "nebuleuse_diffuse",
    "SNR": "nebuleuse_diffuse", "Cl+N": "nebuleuse_diffuse",  # M42 = Cl+N
}
# Types IGNORÉS : doublons de désignation (Dup), objets inexistants (NonEx),
# novae, étoiles (déjà couvertes par Gaia côté affichage), objets non
# classés (Other). JAMAIS de repli implicite — c'est le repli par défaut
# « nebuleuse_diffuse » de l'ancien générateur qui noyait tout en « (Nb) ».
OPENNGC_IGNORES = {"Dup", "NonEx", "Nova", "*", "**", "Other", ""}

# Sh2 / Barnard / LDN : OpenNGC ne les couvre pas. (fichier cache, source
# VizieR, colonne numéro, préfixe de désignation, type, colonnes RA/Dec —
# _RA.icrs déjà converti par VizieR quand il existe, sinon conversion astropy
# de l'équinoxe besselien —, colonne de taille : Diam en arcmin, ou Area en
# deg² pour LDN → diamètre équivalent 2·√(Area/π)).
SOURCES_VOTABLE = [
    ("sharpless.tsv", "VII/20/catalog", "Sh2", "Sh2-", "region_HII",
     "RA1900", "DE1900", "B1900", "Diam"),
    ("barnard.tsv", "VII/220A/barnard", "Barn", "Barnard ", "nebuleuse_obscure",
     "_RA.icrs", "_DE.icrs", None, "Diam"),
    ("ldn.tsv", "VII/7A/ldn", "LDN", "LDN ", "nebuleuse_obscure",
     "_RA.icrs", "_DE.icrs", None, "Area"),
]


def _telecharger_fichier(url: str, chemin: str, progression=None) -> str:
    """Télécharge `url` vers `chemin` (écriture en .part puis renommé : un
    catalogue ne se retrouve JAMAIS à moitié écrit). Cache : fichier déjà
    présent et > 100 octets = réutilisé tel quel (rejouer la génération ne
    re-télécharge rien)."""
    if os.path.isfile(chemin) and os.path.getsize(chemin) > 100:
        return chemin
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    req = urllib.request.Request(url, headers=_EN_TETES)
    tmp = chemin + ".part"
    with urllib.request.urlopen(req, timeout=300) as rep, open(tmp, "wb") as f:
        total = rep.length or 0
        lu = 0
        while True:
            bloc = rep.read(1 << 16)
            if not bloc:
                break
            f.write(bloc)
            lu += len(bloc)
            if progression and total:
                progression(os.path.basename(chemin), lu / total)
    os.replace(tmp, chemin)
    return chemin


def _telecharger_openngc(dossier: str, progression=None) -> str:
    return _telecharger_fichier(OPENNGC_URL, os.path.join(dossier, "openngc.csv"),
                                progression)


def _telecharger_votable(source: str, chemin: str, progression=None) -> str:
    url = (f"{VIZIER_HARVARD_VOTABLE}?-source={urllib.parse.quote(source)}"
           f"&-out.max=unlimited")
    return _telecharger_fichier(url, chemin, progression)
# ──────────────────────────────────────────────────────────────────────────
# Parsing OpenNGC (CSV « ; ») et VOTable Harvard → liste ObjetCelebre
# ──────────────────────────────────────────────────────────────────────────
def _hms_vers_deg(txt: str) -> float:
    """« 03 32 57.4 » (heures) → degrés. Tolérant aux formats courts
    (« 16 26.0 » = heures/minutes sans secondes) et aux séparateurs « : »."""
    parts = [float(p) for p in str(txt).replace(":", " ").split()]
    while len(parts) < 3:
        parts.append(0.0)
    h, m, s = parts[:3]
    return (h + m / 60.0 + s / 3600.0) * 15.0


def _dms_vers_deg(txt: str) -> float:
    """« +31 09 33 » → degrés signés (tolère les formats courts)."""
    s = str(txt).strip()
    signe = -1.0 if s.startswith("-") else 1.0
    parts = [float(p) for p in s.lstrip("+-").replace(":", " ").split()]
    while len(parts) < 3:
        parts.append(0.0)
    d, m, sec = parts[:3]
    return signe * (d + m / 60.0 + sec / 3600.0)


def _convertir_fk4(ra_deg: float, dec_deg: float, equinox: str):
    """FK4 d'équinoxe besselien (ex. « B1900 ») → ICRS. astropy est déjà une
    dépendance du projet (lecture FITS) ; import paresseux (générateur seul)."""
    import astropy.units as u
    from astropy.coordinates import SkyCoord
    from astropy.time import Time
    c = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="fk4",
                 equinox=Time(equinox))
    icrs = c.icrs
    return float(icrs.ra.deg), float(icrs.dec.deg)


def _etiquette_xml(el) -> str:
    """Nom local d'un élément XML (sans l'espace de noms VOTable)."""
    return el.tag.split("}")[-1]


def _lire_votable(chemin: str) -> List[dict]:
    """VOTable Harvard → liste de dicts {nom de colonne: texte}. Une ligne
    dont le nombre de <TD> diffère de l'en-tête est ignorée (robustesse)."""
    racine = ET.parse(chemin).getroot()
    noms = [el.get("name") or "" for el in racine.iter()
            if _etiquette_xml(el) == "FIELD"]
    lignes = []
    for tr in (el for el in racine.iter() if _etiquette_xml(el) == "TR"):
        vals = ["".join(td.itertext()).strip()
                for td in tr if _etiquette_xml(td) == "TD"]
        if len(vals) == len(noms):
            lignes.append(dict(zip(noms, vals)))
    return lignes

def _designation_openngc(nom: str, m: str):
    """« NGC0224 » + M=« 031 » → (« M 31 », [« NGC 224 »]) ; sans M →
    (« NGC 224 », []). Suffixes lettres gardés (« NGC0186A » → « NGC 186A »).
    Le nom Messier, quand il existe, devient la désignation
    (score_designation : Messier d'abord)."""
    correspond = re.fullmatch(r"(IC|NGC)\s*0*(\d+)([A-Z]?)", nom.strip())
    prefixe = correspond.group(1)
    suffixe = correspond.group(3)
    numero = f"{correspond.group(2)}{suffixe}"
    if m and m.strip().isdigit():
        return f"M {int(m.strip())}", [f"{prefixe} {numero}"]
    return f"{prefixe} {numero}", []


def _lire_openngc(chemin: str) -> List[ObjetCelebre]:
    objets = []
    with open(chemin, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f, delimiter=";"):
            try:
                type_raw = (row.get("Type") or "").strip()
                if type_raw in OPENNGC_IGNORES:
                    continue
                type_obj = OPENNGC_TYPES.get(type_raw)
                if type_obj is None:
                    # Type inconnu : on saute (PAS de repli en
                    # « nébuleuse diffuse » — piège de l'ancien .dat).
                    continue
                nom_brut = (row.get("Name") or "").strip()
                if " NED" in nom_brut:
                    # Composante interne d'une galaxie (nœud NEDxx) : pas un
                    # objet annotable en soi.
                    continue
                if not re.fullmatch(r"(IC|NGC)\s*0*\d+[A-Z]?", nom_brut):
                    continue
                ra = _hms_vers_deg(row.get("RA") or "")
                dec = _dms_vers_deg(row.get("Dec") or "")
                designation, aliases = _designation_openngc(
                    row.get("Name") or "", row.get("M") or "")
                for nom in (row.get("Common names") or "").split(","):
                    nom = nom.strip()
                    if nom and nom not in aliases and nom != designation:
                        aliases.append(nom)
                try:
                    taille = max(0.0, float(row.get("MajAx") or 0.0))
                except ValueError:
                    taille = 0.0
                mag_v = None
                v = (row.get("V-Mag") or "").strip()
                if v:
                    try:
                        mag_v = float(v)
                    except ValueError:
                        pass
                objets.append(ObjetCelebre(
                    designation=designation,
                    aliases=aliases,
                    type_obj=type_obj,
                    mag_v=mag_v,
                    size_arcmin=taille,
                    ra_deg=ra,
                    dec_deg=dec,
                    healpix8=int(healpix.ang2pix_nest(ra, dec, NIVEAU)),
                ))
            except Exception:
                # Ignorer les lignes malformées
                continue
    return objets


def _lire_nebuleuses_votable(chemin: str, colonne_num: str, prefixe: str,
                             type_obj: str, ra_col: str, dec_col: str,
                             equinox: Optional[str],
                             colonne_taille: str) -> List[ObjetCelebre]:
    """Sh2 / Barnard / LDN depuis un VOTable Harvard. Coordonnées : les
    colonnes _RA.icrs/_DE.icrs de VizieR sont déjà en ICRS (Barnard B1875,
    LDN B1950) ; sinon (Sharpless, B1900) conversion astropy FK4→ICRS.
    Taille : Diam (arcmin) ou, à défaut (LDN : Area en deg²), diamètre
    équivalent 2·√(Area/π) converti en arcmin."""
    objets = []
    for row in _lire_votable(chemin):
        try:
            numero = int((row.get(colonne_num) or "").strip())
        except ValueError:
            continue
        ra_txt = (row.get(ra_col) or "").strip()
        dec_txt = (row.get(dec_col) or "").strip()
        if not (ra_txt and dec_txt):
            continue
        if ra_col == "_RA.icrs":
            ra, dec = _hms_vers_deg(ra_txt), _dms_vers_deg(dec_txt)
        else:
            ra, dec = _convertir_fk4(_hms_vers_deg(ra_txt),
                                     _dms_vers_deg(dec_txt), equinox)
        try:
            if colonne_taille == "Area":
                area = float((row.get(colonne_taille) or "").strip())
                taille = 2.0 * math.sqrt(max(0.0, area) / math.pi) * 60.0
            else:
                taille = max(0.0,
                             float((row.get(colonne_taille) or "").strip()))
        except ValueError:
            taille = 0.0
        designation = f"{prefixe}{numero}"
        hpix = healpix.ang2pix_nest(ra, dec, NIVEAU)
        objets.append(ObjetCelebre(
            designation=designation,
            aliases=[designation],
            type_obj=type_obj,
            mag_v=None,
            size_arcmin=taille,
            ra_deg=ra,
            dec_deg=dec,
            healpix8=int(hpix),
        ))
    return objets

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
    etapes = [("openngc.csv", "OpenNGC (NGC+IC+M)", None)]
    etapes += [(f, s, r) for (f, s, *r) in SOURCES_VOTABLE]
    n = len(etapes)
    tous = []
    for i, (fname, label, rest) in enumerate(etapes):
        if progression:
            progression(f"Téléchargement {label}", i / n)
        chemin = os.path.join(dossier, fname)
        if rest is None:
            _telecharger_openngc(dossier, progression)
            sous = _lire_openngc(chemin)
        else:
            (col, prefixe, type_obj, ra_col, dec_col, equinox, col_taille) = rest
            _telecharger_votable(next(s for f, s, *r in SOURCES_VOTABLE
                                      if f == fname), chemin, progression)
            sous = _lire_nebuleuses_votable(chemin, col, prefixe, type_obj,
                                            ra_col, dec_col, equinox,
                                            col_taille)
        tous.extend(sous)
        if progression:
            progression(f"Parsing {label}", (i + 1) / n)
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