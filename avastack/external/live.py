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
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .. import travail
from ..compat import memoire_libre
from ..images import auto_unflip, ecrire_fits, find_output, load_image

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
    (convention attendue par le lecteur de GraXpert, cf. ci-dessus).

    v2.38.6 : une SEULE route d'écriture FITS pour toute l'application
    (`images.ecrire_fits` : espace vérifié avant, écriture `.part` renommée,
    message clair si le volume est plein) — c'est ici que se jouait le
    « N requested and M written » incompréhensible du 27/09/2026."""
    return ecrire_fits(chemin, img)


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


def _decoupe(cmd):
    """(tête TELLE QU'ÉCRITE, reste) d'une commande — guillemets conservés."""
    c = (cmd or "").strip()
    if not c:
        return "", ""
    if c.startswith('"'):
        fin = c.find('"', 1)
        if fin == -1:
            return c, ""
        return c[:fin + 1], c[fin + 1:].strip()
    parts = c.split(None, 1)
    return parts[0], (parts[1].strip() if len(parts) > 1 else "")


def binaire_de(cmd):
    """Premier jeton de la commande (guillemets ôtés), ou None.

    `"C:\\...\\GraXpert.exe" "{input}" -cli …` → `C:\\...\\GraXpert.exe`."""
    tete = _decoupe(cmd)[0]
    if not tete:
        return None
    return (tete[1:-1].strip() if tete.startswith('"') else tete) or None


def remplacer_binaire(cmd, reference):
    """Commande `cmd` où SEUL le binaire est repris de `reference` (v2.38.5).

    POURQUOI : quand l'exécutable d'une commande persistée n'existe plus (ou
    n'a jamais été trouvé — cas Linux d'Alain, où la commande de repli «
    graxpert … » avait été figée dans config.json), on reprend le chemin
    fraîchement détecté SANS perdre les OPTIONS réglées par l'utilisateur
    (`-correction Division -smoothing 0.8`, `-strength 0.9`…). Réécrire la
    commande entière depuis le défaut effacerait ce réglage ; ne changer que
    le binaire le préserve. Si la détection n'a rien trouvé, `reference`
    porte le binaire nu — la commande reste donc exécutable telle quelle."""
    tete = _decoupe(reference)[0]
    if not tete:
        return cmd
    reste = _decoupe(cmd)[1]
    return tete + (f" {reste}" if reste else "")


def outil_manquant(cmd):
    """Message si l'exécutable de `cmd` est INTROUVABLE, sinon "" (chaîne vide).

    POURQUOI (constat d'Alain, 27/09/2026) : `commande_valide()` ne regardait
    que les PLACEHOLDERS — la commande de repli « graxpert … » (binaire nu,
    aucune détection réussie sous Linux) était donc jugée bonne, l'échec
    n'apparaissant qu'à l'exécution par un « command not found » du shell,
    noyé dans le message d'erreur de l'outil. Ici, un chemin (absolu ou
    relatif) doit EXISTER, un nom nu doit être dans le PATH."""
    nom = binaire_de(cmd)
    if not nom:
        return "commande absente"
    if os.path.isfile(nom):
        return ""
    if os.sep in nom or (os.altsep and os.altsep in nom) or ":" in nom \
            or nom.endswith((".exe", ".bat", ".cmd", ".AppImage")):
        return f"exécutable introuvable : {nom}"
    return "" if shutil.which(nom) else f"commande introuvable dans le PATH : {nom}"


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
    # v2.38.5 : dire l'outil INTROUVABLE ici plutôt que de le découvrir par un
    # « command not found » du shell, noyé dans la sortie de l'outil.
    manque = outil_manquant(cmd)
    if manque:
        return img, (f"{manque} — réglez le chemin dans « Traitement externe » "
                     "(bouton « … ») ou installez l'outil")
    tmp = None
    garder = False
    try:
        tmp = travail.creer_dossier("avastack_gxlive_")

        def _msg_err(texte):
            """Marque l'échec et dit OÙ sont les fichiers de travail conservés
            (v2.38.6 : sans cela, le dossier — et le journal de l'outil — était
            effacé quoi qu'il arrive, donc l'échec restait inexplicable)."""
            nonlocal garder
            garder = True
            return f"{texte} — fichiers de travail conservés : {tmp}"

        src = os.path.join(tmp, "in.fits")
        outbase = os.path.join(tmp, "out")
        _ecrire_entree(src, img)
        commande = (cmd.replace("{input}", src)
                       .replace("{output}", outbase + ".fits")
                       .replace("{outbase}", outbase))
        code, err = _run_bloquant_survivable(commande, tmp, timeout)
        if err:
            return img, _msg_err(err)
        if code != 0:
            lignes = []
            try:
                with open(os.path.join(tmp, "outils_sortie.txt"),
                          encoding="utf-8", errors="replace") as f:
                    lignes = [l for l in f.read().splitlines() if l.strip()]
            except OSError:
                pass
            detail = lignes[-1] if lignes else "aucun message"
            return img, _msg_err(f"code {code} : {detail}")
        res = find_output(src, outbase)
        if res is None:
            return img, _msg_err("fichier de sortie introuvable (l'outil n'a "
                                 "rien écrit)")
        out = _lire_sortie(res)
        out = auto_unflip(out, img)       # éventuel miroir vertical FITS
        out = np.asarray(out, dtype=np.float32)
        if out.shape != img.shape:
            return img, _msg_err(f"dimensions de sortie {out.shape[:2]} ≠ "
                                 f"entrée {img.shape[:2]}")
        # Jalon 23b : sortie DÉGÉNÉRÉE (pixels non finis, image vide —
        # constat réel d'Alain en SHO sans S : « plus d'image dans la
        # visu ») → repli sur l'image brute avec un message clair, au
        # lieu d'un noir inexpliqué après étirement.
        if not np.isfinite(out).all():
            return img, _msg_err("sortie contenant des pixels non finis "
                                 "(NaN/Inf) — outil ignoré, image brute "
                                 "conservée")
        if float(np.max(np.abs(out))) < 1e-9:
            return img, _msg_err("sortie vide (image noire) — outil ignoré, "
                                 "image brute conservée")
        return out, ""
    except Exception as exc:              # E/S, lecture…
        return img, (f"{exc}"
                     + (f" — fichiers de travail conservés : {tmp}"
                        if tmp else ""))
    finally:
        # v2.38.6 : le dossier n'est supprimé QUE si tout s'est bien passé.
        if tmp is not None and not garder:
            shutil.rmtree(tmp, ignore_errors=True)


# ============ Jalon 81 : PLUSIEURS APPELS EN PARALLÈLE (une passe par couche)
# POURQUOI : le coût de GraXpert est FIXE par appel — le démarrage de son
# binaire figé (Python + imports) puis le chargement des 217 Mo du modèle IA, à
# CHAQUE invocation. La chaîne par couche (jalon 24) l'appelle donc trois fois
# de SUITE, une par couche de composition : ~8,3 s de pur démarrage par passe.
# Or les couches sont INDÉPENDANTES (fichiers d'entrée et de sortie distincts,
# aucun état partagé : `appliquer` crée SON dossier temporaire) — lancer les
# appels EN MÊME TEMPS chevauche leurs démarrages.
# MESURÉ (29/09/2026, machine de dev, 3 couches d'aperçu) : 13,70 s en série →
# 5,58 s en parallèle, et les fichiers produits sont IDENTIQUES OCTET À OCTET
# (SHA-256 égaux) : même binaire, mêmes arguments, entrées indépendantes — le
# parallélisme ne peut PAS changer un pixel, il ne change que l'instant où
# chaque appel démarre.
# MÉMOIRE (mesurée) : ~680 Mo par appel, 1,22 Go pour trois (les pages du
# modèle sont partagées) — et tout est rendu dès que les processus sortent.
MAX_PARALLELE = 3                # au plus trois appels simultanés (une passe)
PAR_APPEL_OCTETS = 800 << 20     # mémoire à réserver par appel simultané
MARGE_MACHINE_OCTETS = 1 << 30   # ce qu'on ne prend JAMAIS à l'application


def parallele_max(nb):
    """Nombre d'appels simultanés AUTORISÉS pour `nb` éléments (jalon 81).

    Plafonné par `MAX_PARALLELE`, par le nombre d'éléments, et par la MÉMOIRE
    LIBRE mesurée (chaque appel simultané réserve ~800 Mo ; on laisse toujours
    1 Go à la machine). Rend au moins 1 — un résultat de 1 veut dire « en
    série », c'est-à-dire le comportement d'avant, jamais une erreur ; une
    sonde muette laisse simplement le plafond nominal."""
    n = max(1, min(int(MAX_PARALLELE), int(nb)))
    if n <= 1:
        return 1
    libre = memoire_libre()
    if libre is None:                 # sonde muette : plafond nominal
        return n
    dispo = int(max(0, libre - MARGE_MACHINE_OCTETS) // PAR_APPEL_OCTETS)
    return max(1, min(n, dispo))


def appliquer_lot(items, timeout=TIMEOUT_S):
    """Applique l'outil à PLUSIEURS images, `parallele_max` à la fois.

    `items` : liste de (cle, image, commande) — `cle` identifie l'élément (le
    RÔLE de la couche), UNIQUE dans le lot. Renvoie {cle: (image, err)} avec
    EXACTEMENT les valeurs d'appels `appliquer()` en série.

    Repli SÉRIE — jamais d'image perdue : lot d'un seul élément, mémoire libre
    insuffisante (`parallele_max` = 1), ou lancement concurrent en échec (le
    pool de fils indisponible, un élément sans résultat)."""
    items = list(items or [])
    res = {}
    if not items:
        return res
    if parallele_max(len(items)) <= 1:
        for cle, img, cmd in items:
            res[cle] = appliquer(img, cmd, timeout)
        return res
    n = parallele_max(len(items))
    try:
        with ThreadPoolExecutor(max_workers=n) as ex:
            futurs = {cle: ex.submit(appliquer, img, cmd, timeout)
                      for cle, img, cmd in items}
            for cle, futur in futurs.items():
                try:
                    res[cle] = futur.result()
                except Exception as exc:   # ne doit pas arriver (repli série)
                    res[cle] = (None, f"{exc}")
    except Exception:                      # pool indisponible
        pass
    # Un élément SANS image (pool en échec) est refait EN SÉRIE : le lot rend
    # toujours une entrée par élément, jamais un trou silencieux. Un échec
    # NORMAL de l'outil (img + message) n'est PAS refait : son message est
    # celui, exact, de l'appel.
    for cle, img, cmd in items:
        if cle not in res or res[cle][0] is None:
            res[cle] = appliquer(img, cmd, timeout)
    return res
