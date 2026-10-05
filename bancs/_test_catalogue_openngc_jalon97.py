# -*- coding: utf-8 -*-
"""Banc jalon 97 (v2.56.0) — GÉNÉRATEUR DU CATALOGUE CÉLÈBRES (OpenNGC).

Cause du jalon : le générateur d'origine pointait vers de MAUVAIS ids VizieR
(« VII/258 » = catalogue de QUASARS, « VII/260 » inexistant en table IC) et
repliait tout code de type inconnu en « nébuleuse diffuse » → TOUS les objets
annotés « (Nb) » (constat Alain sur M31). Nouveau générateur :

  [1] table OPENNGC_TYPES / OPENNGC_IGNORES (jamais de repli implicite) ;
  [2] `_designation_openngc` : M d'abord (« NGC0224 »+« 031 » → « M 31 »),
      suffixes lettres (« NGC0186A »), composantes NED ignorées ;
  [3] `_hms_vers_deg` / `_dms_vers_deg` (formats « : » et courts) ;
  [4] chaîne BOUT-EN-BOUT sur fichiers synthétiques : CSV OpenNGC + VOTables
      (Sh2 en B1900 via astropy, Barnard en _RA.icrs) → .dat → relecture
      CatalogueCelebres + dedup (M31 ≡ NGC 224 → UN objet « M 31 ») ;
  [5] contrôle du .dat EMBARQUÉ livré : M31/M32/M110 galaxies, NGC 206 amas
      ouvert, Sh2-155/Barnard 33/LDN 1622 présents aux bonnes positions.

Exécution : python bancs/_test_catalogue_openngc_jalon97.py
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys
import tempfile

from avastack.catalogues import celebres as cel
from avastack.catalogues.celebres import (CatalogueCelebres, ObjetCelebre,
                                          _ecrire_binaire,
                                          _designation_openngc,
                                          _dms_vers_deg, _hms_vers_deg,
                                          _lire_nebuleuses_votable,
                                          _lire_openngc, deduplique_celebres)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


print("[1] table des types OpenNGC : mappage explicite, AUCUN repli")
for brut, attendu in (("G", "galaxie"), ("GPair", "galaxie"),
                      ("OCl", "amas_ouvert"), ("*Ass", "amas_ouvert"),
                      ("GCl", "amas_globulaire"), ("PN", "nebuleuse_planetaire"),
                      ("HII", "region_HII"), ("EmN", "region_HII"),
                      ("Neb", "nebuleuse_diffuse"), ("RfN", "nebuleuse_diffuse"),
                      ("SNR", "nebuleuse_diffuse"), ("Cl+N", "nebuleuse_diffuse")):
    verifie(cel.OPENNGC_TYPES.get(brut) == attendu,
            f"{brut!r} → {attendu!r}")
verifie(all(t not in cel.OPENNGC_TYPES for t in
            ("Dup", "NonEx", "Nova", "*", "**", "Other", "")),
        "Dup/NonEx/Nova/étoiles/Other/"" ignorés (jamais repliés en nébuleuse)")

print("[2] désignations OpenNGC : Messier d'abord, suffixes lettres, NED ignorés")
d, al = _designation_openngc("NGC0224", "031")
verifie(d == "M 31" and al == ["NGC 224"],
        f"« NGC0224 »+« 031 » → {d!r} {al}")
d, al = _designation_openngc("NGC0224", "")
verifie(d == "NGC 224" and al == [], f"sans M → {d!r}")
d, al = _designation_openngc("NGC0206", "")
verifie(d == "NGC 206", f"NGC 206 : {d!r}")
d, al = _designation_openngc("NGC0186A", "")
verifie(d == "NGC 186A", f"suffixe lettre : {d!r}")
d, al = _designation_openngc("IC0434", "")
verifie(d == "IC 434", f"préfixe IC : {d!r}")
d, al = _designation_openngc("NGC0001", "001")
verifie(d == "M 1", f"M sans zéro de tête : {d!r}")

print("[3] conversions de coordonnées (formats VizieR VOTable)")
verifie(abs(_hms_vers_deg("00:42:44.33") - 10.6847) < 0.001,
        "RA « 00:42:44.33 » → 10,68° (M31)")
verifie(abs(_hms_vers_deg("03 32 57.4") - 53.2392) < 0.001,
        "RA « 03 32 57.4 » (_RA.icrs Barnard) → 53,24°")
verifie(abs(_dms_vers_deg("+41:16:07.5") - 41.2687) < 0.001,
        "Dec « +41:16:07.5 » → 41,27° (M31)")
verifie(abs(_dms_vers_deg("-02 27") + 2.45) < 0.001,
        "Dec court « -02 27 » → -2,45°")
verifie(abs(_dms_vers_deg("-16 06 34") + 16.1094) < 0.001,
        "Dec « -16 06 34 » → -16,11°")

print("[4] chaîne bout-en-bout : CSV OpenNGC + VOTables synthétiques → .dat")
tmp = tempfile.mkdtemp(prefix="avastack_banc97_")
csv_p = os.path.join(tmp, "openngc.csv")
with open(csv_p, "w", encoding="utf-8") as f:
    f.write("Name;Type;RA;Dec;MajAx;V-Mag;M;Common names\n")
    f.write("NGC0224;G;00:42:44.33;+41:16:07.5;177.83;3.44;031;Andromeda Galaxy\n")
    f.write("NGC0206;*Ass;00:40:35.30;+40:44:22.0;;;;\n")       # sans taille
    f.write("NGC0186A;G;00:38:01.60;+42:17:50.0;;;;\n")
    f.write("IC0001;**;00:08:27.05;+27:43:03.6;;;;\n")          # étoile → ignoré
    f.write("IC0002;G;00:11:00.88;-12:49:22.3;0.98;15.46;;\n")
    f.write("IC0080 NED01;G;00:21:00.00;+27:00:00.0;;;;\n")     # composante → ignorée
    f.write("IC0003;Other;00:12:06.09;-00:24:54.6;;;;\n")       # Other → ignoré
objets = _lire_openngc(csv_p)
par_nom = {o.designation: o for o in objets}
verifie(set(par_nom) == {"M 31", "NGC 206", "NGC 186A", "IC 2"},
        f"4 objets gardés, NED/étoile/Other ignorés : {sorted(par_nom)}")
m31 = par_nom["M 31"]
verifie(m31.type_obj == "galaxie" and m31.mag_v is not None
        and abs(m31.mag_v - 3.44) < 1e-6
        and abs(m31.size_arcmin - 177.83) < 1e-6
        and "Andromeda Galaxy" in m31.aliases,
        "M 31 : galaxie, V 3,44, taille 177,83′, alias « Andromeda Galaxy »")
verifie(par_nom["NGC 206"].type_obj == "amas_ouvert"
        and par_nom["NGC 206"].size_arcmin == 0.0,
        "NGC 206 : amas ouvert (*Ass), taille inconnue")
# VOTable Sharpless : équinoxe B1900 → astropy, contrôle sur Sh2-155
sh2_p = os.path.join(tmp, "sharpless.tsv")
with open(sh2_p, "w", encoding="utf-8") as f:
    f.write('<VOTABLE version="1.1"><RESOURCE><TABLE>\n')
    f.write('<FIELD name="Sh2"/><FIELD name="RA1900"/>'
            '<FIELD name="DE1900"/><FIELD name="Diam"/>\n')
    f.write('<DATA><TABLEDATA>\n')
    f.write('<TR><TD>155</TD><TD>22 52 48.0</TD><TD>+62 05 00</TD>'
            '<TD>60.0</TD></TR>\n')
    f.write('</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>\n')
sh2 = _lire_nebuleuses_votable(sh2_p, "Sh2", "Sh2-", "region_HII",
                               "RA1900", "DE1900", "B1900", "Diam")
verifie(len(sh2) == 1 and sh2[0].designation == "Sh2-155"
        and sh2[0].type_obj == "region_HII"
        and abs(sh2[0].size_arcmin - 60.0) < 1e-6,
        "Sh2-155 : région HII, 60′")
# VizieR donne pour Sh2-155 un équinox B1900 : la conversion ICRS doit tomber
# à moins de 10′ de la position J2000 connue (22:57:00 +62:35).
verifie(abs(sh2[0].ra_deg - 344.25) < 0.15 and abs(sh2[0].dec_deg - 62.59) < 0.15,
        f"Sh2-155 converti B1900→ICRS : ({sh2[0].ra_deg:.3f}, "
        f"{sh2[0].dec_deg:.3f}) ≈ (344,25, 62,59)")
# VOTable Barnard : colonnes _RA.icrs déjà converties (pas d'astropy)
bar_p = os.path.join(tmp, "barnard.tsv")
with open(bar_p, "w", encoding="utf-8") as f:
    f.write('<VOTABLE version="1.1"><RESOURCE><TABLE>\n')
    f.write('<FIELD name="Barn"/><FIELD name="_RA.icrs"/>'
            '<FIELD name="_DE.icrs"/><FIELD name="Diam"/>\n')
    f.write('<DATA><TABLEDATA>\n')
    f.write('<TR><TD>33</TD><TD>05 40 58.9</TD><TD>-02 27 36</TD>'
            '<TD>6.0</TD></TR>\n')
    f.write('</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>\n')
bar = _lire_nebuleuses_votable(bar_p, "Barn", "Barnard ", "nebuleuse_obscure",
                               "_RA.icrs", "_DE.icrs", None, "Diam")
verifie(len(bar) == 1 and bar[0].designation == "Barnard 33"
        and abs(bar[0].ra_deg - 85.245) < 0.01
        and abs(bar[0].dec_deg + 2.46) < 0.01
        and abs(bar[0].size_arcmin - 6.0) < 1e-6,
        "Barnard 33 : lu depuis _RA.icrs, position Horsehead, 6′")
# Écriture binaire + relecture + dedup
dat_p = os.path.join(tmp, "celebres_healpix8.dat")
_ecrire_binaire(objets + bar + sh2, dat_p)
cat = CatalogueCelebres(dat_p)
reperes = deduplique_celebres(cat.chercher(10.6847, 41.2690, 0.5),
                              10.6847, 41.2690)
verifie([o.designation for o in reperes] == ["M 31"],
        f"relecture + dedup : {[(o.designation, o.type_obj) for o in reperes]} "
        "(M31 ≡ NGC 224 → UN objet, type LISIBLE)")
verifie(reperes[0].type_obj == "galaxie",
        "le type relu du .dat est « galaxie » (plus jamais « (Nb) »)")

print("[5] contrôle du .dat EMBARQUÉ livré (régression garantie)")
emb = os.path.join(os.path.dirname(__file__), "..", "avastack",
                   "catalogues", "data", "celebres_healpix8.dat")
cat_e = CatalogueCelebres(os.path.abspath(emb))
champ = deduplique_celebres(cat_e.chercher(10.6847, 41.2690, 1.2),
                            10.6847, 41.2690)
types = {o.designation: o.type_obj for o in champ}
verifie(types.get("M 31") == "galaxie" and types.get("M 32") == "galaxie"
        and types.get("M 110") == "galaxie",
        f"M31/M32/M110 = galaxie : {types}")
verifie(types.get("NGC 206") == "amas_ouvert",
        "NGC 206 = amas ouvert (plus « (Nb) »)")
n_objets = sum(cat_e.index[1:]) if hasattr(cat_e, "index") else -1
sh2_155 = cat_e.chercher(344.25, 62.59, 0.3)
verifie(any(o.designation == "Sh2-155" for o in sh2_155),
        "Sh2-155 PRÉSENT (l'ancien .dat ne l'avait pas : mauvais id VizieR)")
b33 = cat_e.chercher(85.245, -2.46, 0.2)
verifie(any(o.designation == "Barnard 33" for o in b33),
        "Barnard 33 présent (Horsehead)")
ldn = cat_e.chercher(88.65, 2.01, 0.2)
verifie(any(o.designation == "LDN 1622" for o in ldn),
        "LDN 1622 présent")

print()
print("BANC TERMINÉ : " + ("TOUT AU VERT" if ok else "ÉCHEC — corriger avant de continuer"))
sys.exit(0 if ok else 1)
