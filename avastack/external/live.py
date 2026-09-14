# -*- coding: utf-8 -*-
"""GraXpert « live » — exécution du CLI sur l'aperçu de l'empilement (jalon 4).

Contrairement au traitement externe manuel (bouton ⚡, sur un INSTANTANÉ
pleine résolution), le mode live enchaîne GraXpert AVANT l'étirement VeraLux,
dans le thread solveur de DisplayProcessor, à chaque nouvel empilement
(décision d'Alain : ordre photométrique correct, gradient retiré avant
l'étirement).

Principe : la copie linéaire [0..1] de l'aperçu transmise au solveur est
écrite dans un FITS temporaire, la commande GraXpert configurée par
l'utilisateur (mêmes placeholders {input}/{output}/{outbase} que le
traitement manuel) est exécutée, le fichier produit est relu (load_image
normalise les entiers en [0..1] et conserve les flottants) puis renvoyé.
L'empilement accumulé n'est JAMAIS modifié : seule la copie du solveur est
traitée. Aucun état global : tout passe par les arguments/retours.
"""

import hashlib
import os
import shutil
import subprocess
import tempfile

import numpy as np

from ..images import auto_unflip, find_output, load_image, save_image

TIMEOUT_S = 300        # au-delà, l'outil est considéré bloqué (1er lancement
                       # possible = téléchargement du modèle IA → long)

# PIÈGE subprocess + cx_Freeze (constaté le 14/09/2026) : quand GraXpert
# plante, cx_Freeze affiche une boîte de dialogue MODALE qui bloque le
# processus jusqu'au clic sur OK. Avec subprocess.run(capture_output=True),
# le processus bloqué garde les tubes ouverts et communicate() reste coincé
# MÊME après le timeout (le kill ne touche que cmd.exe, pas GraXpert).
# → sorties écrites dans des FICHIERS (pas de tubes) et kill de
# l'ARBORESCENCE (taskkill /T) au délai : la dialogue disparaît.

# PIÈGE convention d'axes FITS couleur (diagnostiqué le 14/09/2026) : le
# lecteur FITS de GraXpert 3.1.0rc2 suppose les canaux sur NAXIS3
# (astropy data = (C, H, W)), alors que save_image écrit la convention
# astropy standard (data (H, W, C) → NAXIS1=3). Mal lu, l'aperçu RGB est
# déformé : crash cv2.resize « !dsize.empty() » (boîte de dialogue modale)
# avec l'AI, ou sortie dégénérée (W, 3) avec RBF. Le mono 2D n'est pas
# concerné. → pour le RGB on écrit le FITS d'entrée canaux-en-tête et on
# retranspose la sortie (3, H, W) → (H, W, 3). Détail du diagnostic et
# résultats des essais : AVANCEMENT.md (pièges du 14/09/2026).)


def _ecrire_entree(chemin, img):
    """Écrit l'aperçu pour l'outil externe. RGB : FITS canaux-en-tête
    (convention attendue par le lecteur de GraXpert, cf. ci-dessus)."""
    if img.ndim == 3:
        from astropy.io import fits
        d = np.ascontiguousarray(np.transpose(img, (2, 0, 1)))
        fits.PrimaryHDU(d.astype(np.float32)).writeto(chemin, overwrite=True)
    else:
        save_image(chemin, img)


def _lire_sortie(chemin):
    """Lit la sortie de l'outil ; (3, H, W) → (H, W, 3) (cf. convention)."""
    out = load_image(chemin)
    if out.ndim == 3 and out.shape[0] == 3 and out.shape[2] != 3:
        out = np.ascontiguousarray(np.transpose(out, (1, 2, 0)))
    return out


def commande_valide(cmd):
    """True si la commande contient les placeholders indispensables."""
    return bool(cmd) and "{input}" in cmd and ("{output}" in cmd
                                               or "{outbase}" in cmd)


def cle_image(img):
    """Empreinte du CONTENU de l'image (clé du cache GraXpert du solveur :
    bouger un curseur VeraLux ne doit pas relancer GraXpert)."""
    return hashlib.sha1(np.ascontiguousarray(img).tobytes()).hexdigest()


def _run_bloquant_survivable(cmd, tmp, timeout):
    """Exécute la commande SANS tubes (sorties → fichiers) et tue
    l'ARBORESCENCE au délai. Renvoie (returncode, message d'erreur)."""
    sortie = open(os.path.join(tmp, "outils_sortie.txt"), "wb")
    try:
        p = subprocess.Popen(cmd, shell=True, stdout=sortie, stderr=sortie,
                             stdin=subprocess.DEVNULL)
        termine = p.wait(timeout=timeout)
        return termine, ""
    except subprocess.TimeoutExpired:
        # tue cmd.exe ET graxpert.exe (+ la dialogue modale éventuelle)
        subprocess.run(f"taskkill /F /T /PID {p.pid}", capture_output=True)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        return (p.poll() if p.poll() is not None else -1,
                f"délai dépassé ({timeout} s) — outil bloqué, arrêt forcé")
    except Exception as exc:              # binaire absent…
        return -1, str(exc)
    finally:
        sortie.close()


def appliquer(img, cmd, timeout=TIMEOUT_S):
    """Applique GraXpert (CLI) à l'image linéaire img ([0..1], mono ou RGB).

    Renvoie (image traitée, "") en cas de succès, sinon (img, message
    d'erreur) — l'appelant étire alors l'image brute et affiche l'erreur.
    L'image d'entrée n'est jamais modifiée ; les fichiers temporaires sont
    supprimés quoi qu'il arrive. RGB : FITS canaux-en-tête (cf. convention
    du lecteur de GraXpert)."""
    if not commande_valide(cmd):
        return img, ("commande absente ou incomplète "
                     "(il faut {input} et {output} ou {outbase})")
    tmp = None
    try:
        tmp = tempfile.mkdtemp(prefix="avastack_gxlive_")
        src = os.path.join(tmp, "in.fits")
        outbase = os.path.join(tmp, "out")
        _ecrire_entree(src, img)
        commande = (cmd.replace("{input}", src)
                       .replace("{output}", outbase + ".fits")
                       .replace("{outbase}", outbase))
        code, err = _run_bloquant_survivable(commande, tmp, timeout)
        if err:
            return img, err
        if code != 0:
            lignes = []
            try:
                with open(os.path.join(tmp, "outils_sortie.txt"),
                          encoding="utf-8", errors="replace") as f:
                    lignes = [l for l in f.read().splitlines() if l.strip()]
            except OSError:
                pass
            detail = lignes[-1] if lignes else "aucun message"
            return img, f"code {code} : {detail}"
        res = find_output(src, outbase)
        if res is None:
            return img, "fichier de sortie introuvable (l'outil n'a rien écrit)"
        out = _lire_sortie(res)
        out = auto_unflip(out, img)       # éventuel miroir vertical FITS
        out = np.asarray(out, dtype=np.float32)
        if out.shape != img.shape:
            return img, (f"dimensions de sortie {out.shape[:2]} ≠ "
                         f"entrée {img.shape[:2]}")
        return out, ""
    except Exception as exc:              # E/S, lecture…
        return img, str(exc)
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
