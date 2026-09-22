# -*- coding: utf-8 -*-
"""Wrapper ASTAP (astap_cli) — RÉFÉRENCE INDÉPENDANTE et repli du solveur
interne (jalon 56, étape 2 ; décision d'Alain du 22/09/2026 : résolution
interne avec indices, ASTAP en validation croisée et repli).

Conventions VÉRIFIÉES EN RÉEL le 22/09/2026 (astap_cli CLI-2024.11.17,
« C:\\Program Files\\astap\\astap_cli.exe » + base D80 Gaia DR3) :
  • `-ra` en HEURES (dec 41,3° → 2,75 h) ; `-spd` = 90 + dec (distance au
    pôle SUD : l'écho « Start position » a tranché — passer 90 − dec fait
    chercher à dec = −41,3° au lieu de +41,3°) ; `-fov` = hauteur du champ
    en degrés (écho « Image height ») ; `-r` rayon de recherche en degrés ;
  • SUCCÈS : exit 0 + fichier <base>.wcs (en-tête FITS 80 colonnes avec la
    matrice CD et PLTSOLVD = T) + <base>.ini ; ÉCHEC : exit 1, .wcs absent,
    .ini avec PLTSOLVD=F.
"""

import os
import shutil
import subprocess

from ..compat import IS_WINDOWS
from .solveur import WcsTan

# piége console : ne pas ouvrir une fenêtre DOS à chaque solve
_CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0

# Emplacements connus de astap_cli (après les surcharges ci-dessous).
_CHEMIN_DEFAUT_WINDOWS = r"C:\Program Files\astap\astap_cli.exe"
_CHEMINS_UNIX = ("/usr/local/bin/astap_cli", "/usr/bin/astap_cli",
                 "/opt/astap/astap_cli",
                 "/Applications/ASTAP.app/Contents/MacOS/astap_cli")


def trouver_astap(chemin=None):
    """→ chemin de astap_cli.exe, ou None. Ordre : `chemin` explicite,
    variable d'environnement AVASTACK_ASTAP, installation Windows par
    défaut, PATH, puis emplacements Unix/macOS courants."""
    for candidat in (chemin, os.environ.get("AVASTACK_ASTAP"),
                     _CHEMIN_DEFAUT_WINDOWS if IS_WINDOWS else None):
        if candidat and os.path.isfile(candidat):
            return candidat
    for nom in ("astap_cli", "astap"):
        p = shutil.which(nom)
        if p:
            return p
    for p in _CHEMINS_UNIX:
        if os.path.isfile(p):
            return p
    return None


def resoudre_avec_astap(chemin_image, ra0=None, dec0=None, rayon_deg=None,
                        fov_deg=0.0, chemin_astap=None, timeout=300,
                        dossier_sortie=None):
    """Résout `chemin_image` avec astap_cli.
    `ra0`/`dec0` (deg) : indices du centre — FORTEMENT conseillés (sinon
    ASTAP balaye tout le ciel, lent et moins fiable) ; `rayon_deg` : rayon
    de recherche (défaut 3°) ; `fov_deg` : hauteur du champ en degrés (0 =
    auto) ; `dossier_sortie` : où écrire .wcs/.ini (défaut : à côté de
    l'image).
    → (WcsTan, "") en succès ; (None, message explicite) sinon — jamais
    d'exception propagée."""
    exe = trouver_astap(chemin_astap)
    if exe is None:
        return None, "astap_cli introuvable (ni chemin par défaut, ni PATH)"
    if not os.path.isfile(chemin_image):
        return None, f"image absente : {chemin_image}"

    dossier = dossier_sortie or os.path.dirname(chemin_image) or "."
    os.makedirs(dossier, exist_ok=True)
    base = os.path.join(dossier,
                        os.path.splitext(os.path.basename(chemin_image))[0])
    cmd = [exe, "-f", os.path.abspath(chemin_image), "-o",
           os.path.abspath(base), "-wcs",
           "-r", f"{float(rayon_deg) if rayon_deg else 3.0:.4f}",
           "-fov", f"{float(fov_deg):.4f}"]
    if ra0 is not None and dec0 is not None:
        cmd += ["-ra", f"{float(ra0) / 15.0:.6f}",
                "-spd", f"{90.0 + float(dec0):.6f}"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout,
                             creationflags=_CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired:
        return None, f"astap_cli : délai dépassé ({timeout} s)"
    except OSError as exc:
        return None, f"astap_cli : lancement impossible ({exc})"

    p_wcs = base + ".wcs"
    if res.returncode != 0 or not os.path.isfile(p_wcs):
        # le journal d'astap_cli finit par « No solution found! » ou une
        # erreur : garder la dernière ligne non vide comme message.
        lignes = [l.strip() for l in (res.stdout or "").splitlines()
                  if l.strip()]
        detail = lignes[-1] if lignes else f"exit {res.returncode}"
        return None, f"astap_cli : pas de solution — {detail}"

    # <base>.wcs = en-tête FITS 80 colonnes : lisible par astropy (dépendance
    # déjà requise par images.py). PIÈGE 0/1-based : WcsTan.depuis_mots_cles
    # retranche 1 à CRPIX (convention tableau interne).
    try:
        from astropy.io import fits
        entete = fits.getheader(p_wcs)
        if not bool(entete.get("PLTSOLVD", False)):
            return None, "astap_cli : .wcs sans PLTSOLVD=T"
        wcs = WcsTan.depuis_mots_cles(entete)
    except Exception as exc:
        return None, f"astap_cli : .wcs inutilisable ({exc})"
    return wcs, ""
