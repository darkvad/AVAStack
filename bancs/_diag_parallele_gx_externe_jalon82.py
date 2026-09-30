# -*- coding: utf-8 -*-
"""_diag_parallele_gx_externe_jalon82.py — LE TRAITEMENT EXTERNE (⚡) PAR COUCHE
A-T-IL QUELQUE CHOSE À GAGNER DU LOT ?

CONTEXTE : le jalon 81 (v2.45.0) a mis les outils externes PAR COUCHE en lot
pour le SOLVEUR LIVE et pour l'EXPORT pleine résolution — mais le TRAITEMENT
EXTERNE (bouton ⚡, `App._run_external_compo` → `_compo_couches_traitees`) est
resté SÉRIE : trois appels GraXpert pour le gradient, puis trois pour le
débruitage, l'un après l'autre. Or chaque appel paie ~2,8 s FIXES (démarrage de
son binaire figé + chargement des 217 Mo du modèle IA) et les couches sont
INDÉPENDANTES.

CE QUI EST MESURÉ ICI, avec le VRAI GraXpert d'Alain et ses VRAIES couches
(`canal_R/G/B.fit`, 2168 × 3838 — la chaîne ⚡ travaille en PLEINE résolution) :
la chaîne réelle par couche, en SÉRIE (comportement actuel) puis en LOT
(`external.live.appliquer_lot`, le code que l'implémentation emploierait),
pour ses deux étapes GraXpert — gradient (`cmd_graxpert`) et débruitage
(`cmd_graxpert_dn`, mode « graxpert ») — avec, en sortie, la VÉRIFICATION que
les images sont identiques AU BIT entre série et lot.

Rien de l'application n'est modifié : on appelle les mêmes fonctions, dans le
même ordre, sur les mêmes données.

Usage :
  python bancs/_diag_parallele_gx_externe_jalon82.py [dossier] [etape]

  etape = « tout » (défaut : gradient puis débruitage), « gradient »,
          « debruitage », ou « essai » (recadrage 400 px : validation du banc,
          PAS une mesure — les chiffres d'essai sont étiquetés comme tels).

⚠ DÉLAI : la chaîne ⚡ autorise 1800 s par appel (`_ext_run_cmd`), alors que le
chemin LIVE n'en autorise que 300 (`external.live.TIMEOUT_S`). Mesurer avec le
délai du live tuait un débruitage pleine résolution (constaté) : ce banc use donc
du délai du ⚡.
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import hashlib
import json
import os
import sys
import time

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon
from astropy.io import fits

from avastack.external import live as gx
from avastack.compat import memoire_libre

try:                                 # sortie console : jamais de plantage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DOSSIER = sys.argv[1] if len(sys.argv) > 1 else r"C:\Astro\test"
ETAPE = (sys.argv[2] if len(sys.argv) > 2 else "tout").strip().lower()
ROLES = ("R", "G", "B")
CHEMIN_CONFIG = os.path.join(os.environ.get("APPDATA", ""), "AVAStack",
                             "config.json")
TIMEOUT_ETAPE = 1800        # délai du traitement externe ⚡ (`_ext_run_cmd`)
ESSAI_PX = 400              # recadrage du mode « essai » (validation seulement)


def dit(txt=""):
    """Sortie SUIVIE en direct (un banc long doit être lisible pendant qu'il
    tourne : sans `flush`, Python garde tout dans le tampon du tube)."""
    print(txt, flush=True)


def reglage(cle, defaut):
    """Valeur de `cle` dans la config RÉELLE d'Alain (tolérant : absent = défaut)."""
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


def empreinte(img):
    """SHA-256 des octets de l'image : « identique à l'octet » se PROUVE."""
    return hashlib.sha256(np.ascontiguousarray(img).tobytes()).hexdigest()


def etape(nom, imgs, cmd, lot):
    """Une étape GraXpert par couche : SÉRIE ou LOT → (durée, {rôle: image}, …).

    Les deux chemins passent EXACTEMENT par le code de l'application
    (`gx.appliquer` / `gx.appliquer_lot`) : la mesure porte donc sur ce que
    l'implémentation ferait, pas sur une approximation. Le délai est celui du
    traitement externe (1800 s), pas celui du live (300 s)."""
    dit("\n  %s — %s, une couche à la fois, %d appels"
        % (nom, "LOT (simultanés)" if lot else "SÉRIE (aujourd'hui)",
           len(ROLES)))
    dit("      commande : %s…" % cmd[:100])
    t0 = time.perf_counter()
    if lot:
        res = gx.appliquer_lot([(r, imgs[r], cmd) for r in ROLES],
                               TIMEOUT_ETAPE)
    else:
        res = {r: gx.appliquer(imgs[r], cmd, TIMEOUT_ETAPE) for r in ROLES}
    duree = time.perf_counter() - t0
    out, ok = {}, 0
    for r in ROLES:
        img, err = res.get(r, (None, "appel non exécuté"))
        if err or img is None:
            dit("      ⚠ couche %s : %s" % (r, (err or "aucun résultat")[:120]))
        else:
            ok += 1
        out[r] = img
    dit("      → %d couche(s) sur %d en %6.3f s   (%.2f s par appel)  "
        "[%s]" % (ok, len(ROLES), duree, duree / len(ROLES),
                  time.strftime("%H:%M:%S")))
    return duree, out


def main():
    dit("=" * 78)
    dit("TRAITEMENT EXTERNE (⚡) PAR COUCHE : SÉRIE ou LOT ? (mesure, jalon 82)")
    dit("=" * 78)
    essai = (ETAPE == "essai")
    faire_gx = essai or ETAPE in ("tout", "gradient")
    faire_dn = essai or ETAPE in ("tout", "debruitage")

    cmd_gx = str(reglage("cmd_graxpert", "") or "")
    cmd_dn = str(reglage("cmd_graxpert_dn", "") or "")
    methode_dn = str(reglage("dn_methode", "graxpert"))

    dit("\n[0] outils et mémoire")
    for nom, cmd in (("gradient (cmd_graxpert)", cmd_gx),
                     ("débruitage (cmd_graxpert_dn)", cmd_dn)):
        manque = gx.outil_manquant(cmd) if cmd else "commande absente"
        dit("  %-30s : %s" % (nom, "✔ " + (gx.binaire_de(cmd) or "?")
                              if not manque else "⚠ " + manque))
    if not cmd_gx or gx.outil_manquant(cmd_gx):
        dit("\n  → mesure impossible SANS GraXpert (la mesure porte sur le VRAI "
            "outil : aucun chiffre inventé).")
        return
    libre = memoire_libre()
    dit("  mémoire libre                 : %s"
        % ("%.1f Go" % (libre / 2**30) if libre else "indéterminée"))
    dit("  appels simultanés autorisés   : %d (MAX_PARALLELE = %d)"
        % (gx.parallele_max(3), gx.MAX_PARALLELE))
    dit("  débruitage GraXpert prévu     : %s (mode config : %s)"
        % ("oui" if cmd_dn else "non", methode_dn))
    dit("  étape(s) mesurée(s)           : %s   · mode : %s"
        % (ETAPE, "ESSAI 400 px (validation, PAS une mesure)" if essai
           else "pleine résolution"))

    dit("\n[1] chargement des trois couches réelles")
    imgs = {}
    for r in ROLES:
        p = os.path.join(DOSSIER, "canal_%s.fit" % r)
        if not os.path.isfile(p):
            dit("  ⚠ couche introuvable : %s → mesure impossible" % p)
            return
        imgs[r] = lire_fits(p)
    if essai:                      # recadrage central : validation seulement
        for r in ROLES:
            imgs[r] = np.ascontiguousarray(imgs[r][:ESSAI_PX, :ESSAI_PX])
    h, w = imgs["R"].shape[:2]
    dit("  %d × %d par couche (%.2f Mpx)" % (w, h, w * h / 1e6))

    # ---------------------------------------------- [2] gradient par couche
    total_serie = total_lot = 0.0
    if faire_gx:
        dit("\n[2] GRADIENT par couche (cmd_graxpert) : série contre lot")
        t_s, out_s = etape("gradient", imgs, cmd_gx, lot=False)
        t_l, out_l = etape("gradient", imgs, cmd_gx, lot=True)
        ident = all(out_s[r] is not None and out_l[r] is not None
                    and empreinte(out_s[r]) == empreinte(out_l[r])
                    for r in ROLES)
        dit("      → série %.2f s · lot %.2f s · gain %+.1f %%   %s"
            % (t_s, t_l, 100.0 * (t_s - t_l) / max(t_s, 1e-9),
               "identiques À L'OCTET" if ident
               else "⚠ ÉCART (ou appel raté) : ne pas conclure"))
        total_serie += t_s
        total_lot += t_l
    else:
        out_s = out_l = imgs

    # ------------------------------------------- [3] débruitage par couche
    if faire_dn and cmd_dn and not gx.outil_manquant(cmd_dn) \
            and methode_dn == "graxpert":
        dit("\n[3] DÉBRUITAGE GraXpert par couche (cmd_graxpert_dn)")
        dit("    (l'entrée est la SORTIE DU GRADIENT de la même couche — "
            "l'ordre de la chaîne réelle)")
        t_s2, out_s2 = etape("débruitage", out_s, cmd_dn, lot=False)
        t_l2, out_l2 = etape("débruitage", out_l, cmd_dn, lot=True)
        ident2 = all(out_s2[r] is not None and out_l2[r] is not None
                     and empreinte(out_s2[r]) == empreinte(out_l2[r])
                     for r in ROLES)
        dit("      → série %.2f s · lot %.2f s · gain %+.1f %%   %s"
            % (t_s2, t_l2, 100.0 * (t_s2 - t_l2) / max(t_s2, 1e-9),
               "identiques À L'OCTET" if ident2
               else "⚠ ÉCART (ou appel raté) : ne pas conclure"))
        total_serie += t_s2
        total_lot += t_l2
    else:
        dit("\n[3] DÉBRUITAGE GraXpert : non mesuré (commande absente ou "
            "mode local)")

    # --------------------------------------------------------- [4] synthèse
    dit("\n" + "=" * 78)
    dit("BILAN — les étapes GraXpert par couche de la chaîne ⚡ mesurées ici")
    dit("  SÉRIE (aujourd'hui)     : %6.2f s" % total_serie)
    dit("  LOT (ce qui est mesuré) : %6.2f s" % total_lot)
    if total_lot <= total_serie:
        dit("  → GAIN de %.1f %% (%.2f s gagnées)"
            % (100.0 * (total_serie - total_lot) / max(total_serie, 1e-9),
               total_serie - total_lot))
    else:
        dit("  → PERTE de %.1f %% (%.2f s PERDUES) : le lot est plus LENT"
            % (100.0 * (total_lot - total_serie) / max(total_serie, 1e-9),
               total_lot - total_serie))
    dit("  (BXT reste UN appel sur le composite : rien à paralléliser de ce")
    dit("   côté. Aucun pixel ne change : mêmes commandes, entrées")
    dit("   indépendantes — seul l'instant de départ diffère.)")
    dit("=" * 78)


if __name__ == "__main__":
    main()
