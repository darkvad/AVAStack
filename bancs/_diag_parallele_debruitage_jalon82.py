# -*- coding: utf-8 -*-
"""_diag_parallele_debruitage_jalon82.py — LE DÉBRUITAGE PAR COUCHE EN LOT
RAPPORTE-T-IL QUELQUE CHOSE ?

QUESTION D'ALAIN (30/09/2026) : « on va mesurer le gain en parallélisant le
débruitage ». C'est la dernière piste ouverte du chantier performance (le
jalon 81 a mesuré celui des outils EXTERNES en lot : 13,70 s → 5,58 s pour
trois couches d'aperçu). Mais ici l'outil n'est plus un sous-processus qui paie
un démarrage FIXE : c'est du calcul PUR dans OpenCV
(`cv2.fastNlMeansDenoising`), qui utilise DÉJÀ tous les cœurs pour UN appel.
La question n'est donc pas rhétorique — lancer trois débruitages simultanés
peut ne rien rapporter du tout, voire coûter (14 fils OpenCV × 3 appels = 42
fils sur 14 cœurs).

CE QUI EST MESURÉ (aucune modification de l'application) : les TROIS couches
réelles d'Alain (`canal_R/G/B.fit`, 2168 × 3838), à l'APERÇU 1600 px (ce que
voit le solveur live) et en PLEINE RÉSOLUTION (ce que voit l'export « tel que
vu » et le traitement externe ⚡), pour les DEUX algorithmes locaux (nlm — son
réglage — et ondelettes), et sous TROIS réglages du nombre de fils OpenCV :

  - « par défaut » : OpenCV prend tous les cœurs (14 ici) — c'est l'état actuel ;
  - « 1 fil » : OpenCV bridé, le parallélisme ne peut venir que des couches ;
  - « 4 fils » : OpenCV bridé à 4 — trois appels simultanés = 12 fils ≤ 14 cœurs.

Pour chaque réglage : SÉRIE (comportement actuel) puis LOT (trois appels
simultanés, ce que ferait l'implémentation) — et l'on VÉRIFIE que les images
obtenues sont identiques AU BIT : un débruitage est déterministe, le
parallélisme ne peut pas changer un pixel, seulement l'instant de départ.

Usage : python bancs/_diag_parallele_debruitage_jalon82.py [dossier]
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon
from astropy.io import fits

from avastack.processing import denoise as _denoise

try:                                 # sortie console : jamais de plantage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DOSSIER = sys.argv[1] if len(sys.argv) > 1 else r"C:\Astro\test"
ROLES = ("R", "G", "B")
APERCU_PX = 1600.0                   # même échelle d'aperçu que l'application
CHEMIN_CONFIG = os.path.join(os.environ.get("APPDATA", ""), "AVAStack",
                             "config.json")


def reglage(cle, defaut):
    """Valeur de `cle` dans la config RÉELLE d'Alain (tolérant : absent = défaut).

    Le réglage mesuré doit être celui de sa session, pas un réglage inventé
    (règle du projet) — mais une config absente ne doit pas empêcher la mesure."""
    try:
        with open(CHEMIN_CONFIG, encoding="utf-8") as f:
            return json.load(f).get(cle, defaut)
    except Exception:
        return defaut


def lire_fits(p):
    """Couche mono [0..1] d'un FITS (comme `images.load_image`)."""
    d = np.asarray(fits.getdata(p), dtype=np.float32)
    if d.ndim == 3 and d.shape[0] == 3:
        d = np.ascontiguousarray(np.transpose(d, (1, 2, 0)))
    return d


def reduire(img):
    """Même réduction d'aperçu que l'application (INTER_AREA, 1600 px)."""
    h, w = img.shape[:2]
    e = min(1.0, APERCU_PX / float(max(h, w)))
    if e >= 1.0:
        return img.copy(), 1.0
    return cv2.resize(img, None, fx=e, fy=e,
                      interpolation=cv2.INTER_AREA), e


def charger_couches():
    """Les trois couches réelles, ou None (dossier absent → message clair)."""
    couches = {}
    for role in ROLES:
        p = os.path.join(DOSSIER, "canal_%s.fit" % role)
        if not os.path.isfile(p):
            print("  ⚠ couche introuvable : %s" % p)
            return None
        couches[role] = lire_fits(p)
    return couches


def serie(imgs, methode, force):
    """Comportement ACTUEL : un débruitage après l'autre."""
    t0 = time.perf_counter()
    outs, errs = [], []
    for im in imgs:
        o, e = _denoise.denoiser(im, methode, force)
        outs.append(o)
        errs.append(e)
    return time.perf_counter() - t0, outs, errs


def lot(imgs, methode, force):
    """Ce que ferait l'implémentation : les couches EN MÊME TEMPS."""
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(imgs)) as ex:
        res = list(ex.map(lambda im: _denoise.denoiser(im, methode, force),
                          imgs))
    return (time.perf_counter() - t0, [r[0] for r in res],
            [r[1] for r in res])


def identiques(a, b):
    """True si les images du lot sont identiques AU BIT à celles de la série."""
    return (len(a) == len(b)
            and all(np.array_equal(x, y) for x, y in zip(a, b)))


def scenario(nom, imgs, methode, force):
    """SÉRIE vs LOT pour les trois réglages de fils OpenCV (→ gain en %)."""
    n_libre = cv2.getNumThreads()
    print("\n  %s — %d couches, force %.2f" % (nom, len(imgs), force))
    print("      %-34s %9s  %9s  %s" % ("", "série", "lot", "gain (lot / série)"))
    ref_serie = None
    for libelle, fils in (("OpenCV par défaut (%d fils)" % n_libre, None),
                          ("OpenCV bridé à 1 fil", 1),
                          ("OpenCV bridé à 4 fils", 4)):
        if fils is not None:
            cv2.setNumThreads(fils)
        try:
            t_s, out_s, err_s = serie(imgs, methode, force)
            t_l, out_l, err_l = lot(imgs, methode, force)
        finally:
            cv2.setNumThreads(n_libre)
        gain = 100.0 * (t_s - t_l) / max(t_s, 1e-9)
        print("      %-34s %7.3f s  %7.3f s  %+6.1f %%  %s"
              % (libelle, t_s, t_l, gain,
                 "gain" if gain > 3.0 else ("PERTE" if gain < -3.0
                                            else "aucun gain")))
        # Le lot doit rendre EXACTEMENT les mêmes pixels que la série.
        if not (identiques(out_s, out_l) and not any(err_s) and not any(err_l)):
            print("      ⚠ ÉCART entre série et lot (erreurs : %s / %s)"
                  % (err_s, err_l))
        if ref_serie is None:
            ref_serie = out_s
        else:
            # Le résultat ne doit pas non plus dépendre du nombre de fils OpenCV.
            if not identiques(ref_serie, out_s):
                print("      ⚠ le résultat de la SÉRIE change avec le nombre "
                      "de fils OpenCV")


def echelle(nom, img, methode, force):
    """Coût d'UN SEUL débruitage selon le nombre de fils OpenCV.

    C'est l'explication du verdict : si un appel utilise DÉJÀ bien tous les
    cœurs, le partager en trois ne peut rien apporter ; s'il plafonne, il y a
    de la place pour des appels simultanés."""
    print("\n  %s — un appel SEUL, force %.2f" % (nom, force))
    n_libre = cv2.getNumThreads()
    ref = None
    try:
        for fils in (1, 2, 4, 7, n_libre):
            cv2.setNumThreads(fils)
            t0 = time.perf_counter()
            out, err = _denoise.denoiser(img, methode, force)
            dt = time.perf_counter() - t0
            if ref is None:
                ref = dt
            print("      %2d fil(s) : %6.3f s   (×%.2f face à 1 fil)"
                  % (fils, dt, ref / max(dt, 1e-9)))
            if err:
                print("      ⚠ erreur : %s" % err)
    finally:
        cv2.setNumThreads(n_libre)


def main():
    print("=" * 78)
    print("DÉBRUITAGE PAR COUCHE : SÉRIE ou LOT ? (mesure, jalon 82)")
    print("=" * 78)
    print("\n[0] environnement")
    print("  cœurs logiques de la machine      : %s" % (os.cpu_count() or "?"))
    print("  OpenCV %s, fils ouverts par appel : %d"
          % (cv2.__version__, cv2.getNumThreads()))
    methode = str(reglage("vl_denoise_methode", "nlm"))
    force = float(reglage("vl_denoise_force", 0.5))
    print("  réglage live d'Alain (config)     : %s, force %.2f"
          % (methode, force))

    print("\n[1] chargement des trois couches réelles")
    couches = charger_couches()
    if couches is None:
        print("  → mesure impossible (dossier : %s)" % DOSSIER)
        return
    imgs_plein = [couches[r] for r in ROLES]
    imgs_apercu = [reduire(c)[0] for c in imgs_plein]
    h, w = imgs_plein[0].shape[:2]
    ha, wa = imgs_apercu[0].shape[:2]
    print("  pleine résolution : %d × %d (%d couches, %.1f Mpx chacune)"
          % (w, h, len(imgs_plein), w * h / 1e6))
    print("  aperçu (1600 px)  : %d × %d — ce que voit le solveur live"
          % (wa, ha))

    # Rodage (le premier appel OpenCV paie l'initialisation de son pool de fils).
    _denoise.denoiser(imgs_apercu[0], methode, force)

    for meth in ("nlm", "ondelettes"):
        print("\n" + "=" * 78)
        print("MÉTHODE « %s » — force %.2f" % (meth, force))
        print("=" * 78)
        echelle("APERÇU 1600 px", imgs_apercu[0], meth, force)
        echelle("PLEINE RÉSOLUTION", imgs_plein[0], meth, force)
        scenario("APERÇU 1600 px", [i.copy() for i in imgs_apercu], meth, force)
        scenario("PLEINE RÉSOLUTION", [i.copy() for i in imgs_plein], meth, force)

    print("\n" + "=" * 78)
    print("LECTURE : le LOT ne sert que s'il fait gagner du TEMPS *et* rend les")
    print("mêmes pixels. Un débruitage est du CALCUL PUR : contrairement aux")
    print("appels GraXpert (jalon 81, ~2,8 s de démarrage fixes par appel), il")
    print("n'y a ici AUCUN temps mort à recouvrir — seulement des cœurs à")
    print("partager, et OpenCV les prend DÉJÀ tous pour un seul appel.")
    print("=" * 78)


if __name__ == "__main__":
    main()
