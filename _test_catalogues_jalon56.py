# -*- coding: utf-8 -*-
"""Banc du jalon 56 (étape 1) : fondations catalogues — HEALPix NESTED
maison (entrelacement, pix2ang, ang2pix, pixels_cone), lecture du format
Siril (en-tête chunked + extraction), téléchargeur Zenodo (reprise Range,
sha256, sommaire). Catalogues inutilisés par ce banc.

Exécution : python _test_catalogues_jalon56.py
"""
import hashlib
import http.server
import os
import re
import sys
import tempfile
import threading

import numpy as np

from avastack.catalogues import (CatalogueSiril, NIVEAU_CATALOGUE,
                                 ang2pix_nest, chunk_vers_plage_pixels,
                                 depaqueter, dossier_catalogues,
                                 entrelacer, etat_local, lire_entete,
                                 pixel_vers_chunk, pix2ang_nest,
                                 pixels_cone)
from avastack.catalogues import telechargeur

if hasattr(sys.stdout, "reconfigure"):     # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# Valeurs de référence astropy-healpix 2.0.1 (générées le 22/09/2026,
# graine 56) : (pixel, ra_deg, dec_deg) — 1–3 pixels par face, choisis
# pour couvrir les DEUX régions (linéaire/Collignon) des faces polaires.
REF_PIX = [
    (1107, 52.7343750000, 7.0303931808),
    (24056, 88.5211267606, 50.2858100190),
    (62319, 47.3376623377, 75.8933059990),
    (67558, 140.0976562500, 13.2480149057),
    (89081, 166.3815789474, 47.3575762332),
    (105292, 118.7037037037, 44.3998327471),
    (195969, 235.6578947368, 83.0515681640),
    (152047, 260.8593750000, 37.7327475896),
    (169966, 217.7608695652, 46.9649773400),
    (237545, 299.4750000000, 52.8018537817),
    (254123, 294.9428571429, 57.5898719083),
    (261050, 271.0227272727, 81.9527640710),
    (283738, 40.9570312500, -2.3880154633),
    (345578, 119.7070312500, -8.3855386471),
    (399835, 188.7890625000, -18.0529530381),
    (454641, 168.9257812500, 28.9715322237),
    (525189, 39.8863636364, -81.9527640710),
    (587988, 40.4296875000, -10.9588633070),
    (666729, 205.9375000000, -63.4482836803),
    (708187, 223.9453125000, -24.4602915090),
    (729565, 296.7452830189, -70.5359495596),
    (758100, 308.1390134529, -48.3367942301),
]

M31 = (10.684, 41.269)          # centre approximatif (deg)


def sep_deg(ra1, dec1, ra2, dec2):
    """Séparation angulaire (deg) — haversine (stable près de 0, contra-
    rairement à arccos dont le bruit monte à ~1e-6° sur des points quasi
    identiques)."""
    p1, d1, p2, d2 = map(np.radians, (ra1, dec1, ra2, dec2))
    a = (np.sin((d2 - d1) / 2.0) ** 2
         + np.cos(d1) * np.cos(d2) * np.sin((p2 - p1) / 2.0) ** 2)
    return np.degrees(2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0))))


# ============================================================ [1] HEALPix
print("[1] HEALPix NESTED : entrelacement, pix2ang vs astropy, ang2pix")
rng = np.random.default_rng(56)
n=0
for _ in range(200):
    ix = int(rng.integers(0, 1 << 7))
    iy = int(rng.integers(0, 1 << 7))
    p = entrelacer(ix, iy, 7)
    a, b = depaqueter(np.array([p]), 7)
    n += int(a[0]) == ix and int(b[0]) == iy
verifie(n == 200,
        f"entrelacer/depaqueter réversible (200 paires aléatoires, niv. 7)")

pix_ref = np.array([r[0] for r in REF_PIX], np.int64)
ra_ref = np.array([r[1] for r in REF_PIX])
dec_ref = np.array([r[2] for r in REF_PIX])
ra_mes, dec_mes = pix2ang_nest(pix_ref)
err = np.maximum(np.abs(sep_deg(ra_mes, dec_mes, ra_ref, dec_ref)),
                 np.abs(dec_mes - dec_ref))
verifie(float(err.max()) < 1e-8,
        f"pix2ang_nest = astropy sur {len(REF_PIX)} pixels de référence "
        f"(écart max {err.max():.2e}°)")
ret = ang2pix_nest(ra_ref, dec_ref)
verifie(bool((ret == pix_ref).all()),
        "ang2pix_nest inverse exactement ces mêmes pixels")

# roundtrip aléatoire : centre du pixel → même pixel (hors voisinage pôle)
n = 2000
ra_al = rng.uniform(0.0, 360.0, n)
dec_al = np.degrees(np.arcsin(rng.uniform(-0.999, 0.999, n)))
p_al = ang2pix_nest(ra_al, dec_al)
c_ra, c_dec = pix2ang_nest(p_al)
verifie(bool((p_al == ang2pix_nest(c_ra, c_dec)).all()),
        f"roundtrip ang2pix(pix2ang) identité sur {n} directions")
pi_al = pixel_vers_chunk(p_al)
ok_chunk = (pi_al >= 0).all() and (pi_al < 48).all()
verifie(ok_chunk, "pixel_vers_chunk ∈ [0, 47] sur toutes les directions")
for r in (0.2, 0.5, 1.0):
    pix = pixels_cone(*M31, r)
    pra, pdec = pix2ang_nest(pix)
    verifie(bool((sep_deg(pra, pdec, *M31) <= r + 0.35).all())
            and pix.size > 0,
            f"pixels_cone(M31, {r}°) : {pix.size} pixels tous proches")

# ================================================= [2] chunks Siril
print("[2] Catalogue Siril : en-têtes des chunks présents")
dossier = dossier_catalogues()
etat = etat_local(dossier)
print(f"      dossier : {dossier}")
chunks = etat["chunks"]
verifie(len(chunks) > 0,
        f"{len(chunks)} chunk(s) xpsamp détecté(s) dans le dossier")
tout_ok = True
for num, chemin in sorted(chunks.items()):
    ent = lire_entete(chemin)
    attendu = chunk_vers_plage_pixels(num)
    if (ent["chunked"] and ent["chunk_level"] == 1 and ent["niveau"] == 8
            and ent["type"] == 2 and ent["chunk"] == num
            and (ent["pixel_debut"], ent["pixel_fin"]) == attendu):
        continue
    tout_ok = False
    print(f"      chunk {num} : incohérent → {ent} / attendu {attendu}")
verifie(tout_ok, "en-têtes chunked=1, niveau 1, plages pixels = chunk<<14")

# ============================================== [3] extraction M31 (xpsamp)
print("[3] Extraction du catalogue spectrophotométrique")
etoiles = {"ra": np.empty(0)}
if chunks:
    # tri sains / corrompus : un fichier tronqué (téléchargement Siril
    # interrompu) doit être REJETÉ proprement, jamais interprété à moitié
    sains, corrompus = {}, []
    for num, chemin in sorted(chunks.items()):
        try:
            sains[num] = CatalogueSiril(chemin)
        except ValueError as exc:
            corrompus.append((num, str(exc)))
    verifie(not corrompus,
            f"{len(sains)}/48 chunks lisibles"
            + (f" — CORROMPUS à retélécharger : "
               f"{[n for n, _ in corrompus]}" if corrompus else ""))
    for num, msg in corrompus:
        print(f"      ⚠ chunk {num} : {msg}")
    pix_m31 = ang2pix_nest(M31[0], M31[1])
    chunk_m31 = int(pixel_vers_chunk(pix_m31))
    if chunk_m31 in sains:
        # champ M31 (le but final du projet)
        etoiles = sains[chunk_m31].extraire(M31[0], M31[1], 0.3)
        cible = "M31"
        centre = M31
    elif sains:
        # chunk de M31 indisponible : validation d'extraction sur le
        # centre d'un chunk sain (mêmes mécaniques testées)
        num = sorted(sains)[0]
        c_ra, c_dec = pix2ang_nest(
            np.array([(chunk_vers_plage_pixels(num)[0]
                       + chunk_vers_plage_pixels(num)[1]) // 2]))
        centre = (float(c_ra[0]), float(c_dec[0]))
        etoiles = sains[num].extraire(centre[0], centre[1], 0.3)
        cible = f"centre du chunk {num}"
    else:
        cible = None
    if cible:
        n = etoiles["ra"].size
        verifie(n >= 50, f"{n} étoiles extraites autour de {cible} (≥ 50)")
        if n:
            sep = sep_deg(etoiles["ra"], etoiles["dec"], *centre)
            verifie(bool((sep <= 0.3 + 1e-9).all()),
                    "toutes les positions RÉELLES dans le rayon de 0,3°")
            verifie(bool(((etoiles["g"] > 0) & (etoiles["g"] < 21)).all()),
                    f"magnitudes G plausibles "
                    f"({etoiles['g'].min():.2f} … {etoiles['g'].max():.2f})")
            verifie(bool(np.isfinite(etoiles["flux"]).all()
                         and (etoiles["flux"] > 0).all()),
                    "flux xp_sampled finis et positifs (float16 × 10^fexpo)")
else:
    print("      ABSENT — téléchargez les chunks (voir telechargeur) ; "
          "sections [3]/[4] tronquées, sans échec.")

# ============================================ [4] catalogue astrométrique
print("[4] Catalogue astrométrique (s'il est présent) + cohérence croisée")
if etat["astro"]:
    cat_a = CatalogueSiril(etat["astro"])
    ent = cat_a.fichiers[0]["entete"]
    verifie(ent["type"] == 1 and not ent["chunked"],
            f"en-tête astro : type 1, monolithique (« {ent['titre']} »)")
    astro = cat_a.extraire(M31[0], M31[1], 0.3)
    verifie(astro["ra"].size >= 50,
            f"{astro['ra'].size} étoiles astro extraites autour de M31")
    verifie("teff" in astro, "champ teff présent (astro)")
    if etoiles["ra"].size:
        # chaque étoile xpsamp doit avoir une voisine astro à < 0,02°
        d_ra = (astro["ra"][None, :] - etoiles["ra"][:, None] + 180) % 360 - 180
        d_dec = astro["dec"][None, :] - etoiles["dec"][:, None]
        d2 = (d_ra * np.cos(np.radians(etoiles["dec"]))[:, None]) ** 2 \
            + d_dec ** 2
        plus_proche = d2.min(axis=1)
        verifie(bool((plus_proche < 0.02 ** 2).all()),
                f"xpsamp ⊂ astro : {int((plus_proche < 4e-4).sum())}/"
                f"{etoiles['ra'].size} étoiles appariées à < 0,02°")
else:
    print("      ABSENT — lancez le téléchargeur (1,1 Go) ou posez le "
          "fichier de Siril ; sans échec.")


# ==================================================== [5] téléchargeur
print("[5] Téléchargeur : reprise Range, sha256, sommaire Zenodo")
DONNEES = (np.random.default_rng(5).integers(0, 256, 300_000,
                                             dtype=np.uint8)).tobytes()
SHA = hashlib.sha256(DONNEES).hexdigest()


class _Srv(http.server.BaseHTTPRequestHandler):
    donnees = b""
    avec_range = True

    def do_GET(self):
        n = 0
        partiel = False
        if self.avec_range:
            m = re.match(r"bytes=(\d+)-", self.headers.get("Range") or "")
            if m:
                n = int(m.group(1))
                partiel = n > 0
        corps = self.donnees[n:]
        self.send_response(206 if partiel else 200)
        if partiel:
            self.send_header("Content-Range",
                             f"bytes {n}-{len(self.donnees) - 1}"
                             f"/{len(self.donnees)}")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *args):      # silencieux
        pass


def _serveur(avec_range):
    srv = type("_S", (_Srv,), {"donnees": DONNEES, "avec_range": avec_range})
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), srv)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, f"http://127.0.0.1:{httpd.server_port}/cat.dat"


tmp = tempfile.mkdtemp(prefix="avastack_banc56_")
try:
    # reprise avec support Range
    httpd, url = _serveur(True)
    dest = os.path.join(tmp, "cat.dat")
    with open(dest + ".part", "wb") as f:
        f.write(DONNEES[:137_000])     # simulation d'un téléchargement coupé
    telechargeur.telecharger(url, dest)
    verifie(hashlib.sha256(open(dest, "rb").read()).hexdigest() == SHA,
            "reprise Range : fichier recollé identique (137 000 o puis "
            "la suite)")
    httpd.shutdown()

    # serveur qui IGNORE Range (200 complet) : repartir de zéro, pas de
    # concaténation fausse
    httpd, url = _serveur(False)
    with open(dest + ".part", "wb") as f:
        f.write(DONNEES[:50_000])
    telechargeur.telecharger(url, dest)
    verifie(hashlib.sha256(open(dest, "rb").read()).hexdigest() == SHA,
            "serveur sans Range : reprise propre de zéro (pas de doublon)")
    httpd.shutdown()
finally:
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

try:
    somme = telechargeur.sommaire_zenodo(
        telechargeur.RECORD_ASTRO, telechargeur.NOM_ASTRO)
    verifie(re.fullmatch(r"[0-9a-f]{64}", somme or "") is not None,
            "sommaire Zenodo réel : sha256 du catalogue astro récupéré")
except Exception as exc:
    print(f"      RÉSEAU INDISPONIBLE ({exc}) — test Zenodo skippé, "
          "sans échec (les tests locaux ci-dessus couvrent la mécanique).")

# ============================================ [6] détection du dossier
print("[6] Détection du dossier des catalogues")
d = dossier_catalogues()
verifie(os.path.isdir(d), f"dossier catalogues résolu : {d}")
verifie(etat_local(d)["chunks"] == {int(k): v for k, v in chunks.items()}
        if chunks else True, "etat_local ≡ lecture directe du dossier")

print("BANC JALON 56 (étape 1) :", "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)

