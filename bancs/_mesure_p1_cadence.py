# -*- coding: utf-8 -*-
"""Mesure P1 (lot 2) — « profondeur → mesure → coût » sur des données RÉELLES.

POURQUOI CE BANC AVANT LE CODE : la cadence de re-mesure (3 → 6 → 12 → 24…) ne
doit pas être choisie « au feeling ». Ce banc empile de VRAIES brutes, palier
par palier, et chronomètre les trois mesures que la cadence déclenchera :

  • ASTROMÉTRIE  (`SuiviAstrometrie.resoudre_sur`, image brute de la grille) ;
  • GAINS GAIA   (`Photometrie.mesurer`, zéro-points par bande) ;
  • SPCC         (`SessionSpcc.mesurer`, spectres Gaia × profils capteur).

Il mesure AUSSI le coût d'empilement de chaque palier, pour distinguer ce qui
est imputable à la mesure de ce qui l'est à l'acquisition.

USAGE
  python bancs/_mesure_p1_cadence.py
  python bancs/_mesure_p1_cadence.py --dossier "C:\\Astro\\...\\LIGHT" \
      --paliers 3,6,12,24,48 --max 89
  python bancs/_mesure_p1_cadence.py --autotest     # mécanique seule (0,1 s)

SORTIE : tableau console + `bancs/_mesure_p1_cadence.json` (rejouable, diff).
Les chiffres du dernier passage réel sont consignés dans AVANCEMENT.md.

ATTENTION (règle du projet) : les brutes sont DITHÉRÉES — l'empilement passe
par `StarAligner` + `LiveStacker`, exactement comme le worker, sinon les
mesures porteraient sur une image jamais alignée et les chiffres seraient faux.
"""

import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc))
        break

import argparse
import json
import os
import sys
import time

import numpy as np
import cv2

cv2.ocl.setUseOpenCL(False)      # crash OpenCV 5/OpenCL au teardown sinon

from avastack.images import load_image
from avastack.processing import StarAligner, LiveStacker
from avastack.processing import astrometrie as astro
from avastack.processing import photometrie as photo
from avastack.processing import spcc as spcc_mod
from avastack.processing.cadence import CadenceMesure

if hasattr(sys.stdout, "reconfigure"):     # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAUT = r"C:\Astro\Images_Stack\180.00s\LIGHT"
SORTIE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "_mesure_p1_cadence.json")
CAPTEUR = "Sony IMX585"          # Player One Uranus-C (jeu réel de référence)
BLANC = "Average Spiral Galaxy"
MODE = "osc"


def paliers(txt):
    """« 3,6,12 » → [3, 6, 12] (entiers croissants, doublons retirés)."""
    out = []
    for morceau in str(txt or "").replace(";", ",").split(","):
        morceau = morceau.strip()
        if not morceau:
            continue
        try:
            n = int(float(morceau))
        except ValueError:
            raise SystemExit(f"palier illisible : {morceau!r}")
        if n > 0 and n not in out:
            out.append(n)
    return sorted(out)


def frames_du_dossier(dossier):
    """FITS du dossier (NON récursif : les sous-dossiers `rejected` restent
    dehors), triés par date de modification — l'ordre de lecture du worker."""
    try:
        noms = [e.path for e in os.scandir(dossier)
                if e.is_file() and e.name.lower().endswith(
                    (".fits", ".fit", ".fts"))]
    except OSError as exc:
        raise SystemExit(f"dossier illisible : {dossier} ({exc})")
    return sorted(noms, key=os.path.getmtime)


def canaux_de(img):
    """Image → {bande: 2D} comme `worker._photo_canaux` (R/G/B ou L)."""
    if img is None:
        return {}
    if getattr(img, "ndim", 2) == 3:
        a = img if img.shape[-1] == 3 else np.transpose(img, (1, 2, 0))
        return {"R": a[..., 0].copy(), "G": a[..., 1].copy(),
                "B": a[..., 2].copy()}
    return {"L": img}


def chrono(fn):
    """Exécute `fn` → (résultat|None, durée s, message d'erreur "")."""
    t0 = time.perf_counter()
    try:
        res = fn()
    except Exception as exc:          # une mesure ne tue jamais le banc
        return None, time.perf_counter() - t0, f"exception ({exc})"
    return res, time.perf_counter() - t0, ""


def retenus_doublants(depths):
    """Paliers qu'une cadence DOUBLANTE retiendrait (délai ignoré).

    Sert de borne HAUTE du coût réel : le délai de 20 s ne peut que RETIRER
    des mesures, jamais en ajouter. Utilise `CadenceMesure` — une seule
    politique, celle du code de production.
    """
    cad = CadenceMesure("borne")
    out = []
    # Horloge VIRTUELLE : chaque palier arrive au moins un délai après le
    # précédent (une nuit réelle prend des dizaines de secondes par palier).
    # Sans cela, le délai de 20 s bloquerait tout et la « borne » ne dirait
    # rien du coût.
    t = 0.0
    for n in depths:
        doit, _ = cad.doit_mesurer(n, maintenant=t)
        if doit:
            out.append(n)
            cad.noter_mesure(n, maintenant=t)
        t += max(cad.delai_s + 1.0, 30.0)
    return out


def mesurer(dossier, depths, limite=None):
    """Empile les brutes et chronomètre les trois mesures à chaque palier."""
    chemins = frames_du_dossier(dossier)
    if limite:
        chemins = chemins[:int(limite)]
    if not chemins:
        raise SystemExit(f"aucune brute FITS dans {dossier}")
    depths = [n for n in depths if n <= len(chemins)]
    if not depths:
        raise SystemExit(f"aucun palier atteignable ({len(chemins)} brutes)")

    ra, dec, champ, msg = astro.indices_entete_fits(chemins[0])
    print(f"[brutes] {len(chemins)} frames — {os.path.basename(chemins[0])}")
    print(f"[indices] AD {ra} Dec {dec} champ {champ} ({msg})")
    suivi = astro.SuiviAstrometrie()
    if ra is not None and dec is not None:
        suivi.indice(ra, dec, champ)
    phot = photo.Photometrie()
    sess = spcc_mod.SessionSpcc()

    aligner = StarAligner()
    st = None
    t_emp = 0.0
    lignes = []
    for i, chemin in enumerate(chemins, start=1):
        img = load_image(chemin)
        if st is None:
            st = LiveStacker(img.shape, k=3.0, method="kappa", window=8)
            aligner.set_reference(img)
            M = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
            ok, err = True, ""
        else:
            res, dt, err = chrono(lambda: aligner.compute(img))
            t_emp += dt
            M, ok = (res if isinstance(res, tuple) and len(res) == 2
                     else (None, False))
        if err:
            print(f"  frame {i} : alignement en échec — {err}")
        if not ok or M is None:
            continue
        aligned = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                                 flags=cv2.INTER_LINEAR)
        _, dt, _ = chrono(lambda: (st.add(aligned), st.note_alignement(M)))
        t_emp += dt
        if i not in depths:
            continue

        ligne = {"profondeur": i, "total": int(st.n),
                 "t_empilement_s": round(t_emp, 4)}
        # --- astrométrie : la MÊME image que l'aligneur (grille complète).
        if suivi.resolu:
            ligne["astro"] = {"t_s": 0.0, "ok": True,
                              "msg": "déjà résolu (pas de re-solve)"}
        else:
            res, dt, err = chrono(lambda: suivi.resoudre_sur(
                st.mean(recadre=False, corrections=False), n_frames=i))
            okk, msgk = res if isinstance(res, tuple) else (False, err or "")
            ligne["astro"] = {"t_s": round(dt, 4), "ok": bool(okk),
                              "msg": str(msgk), "essais": int(suivi.essais)}
        # --- photométrie / SPCC : canaux de la grille RECADRÉE + WCS propagé.
        canaux = canaux_de(st.mean(corrections=False))
        wcs = None
        if canaux:
            forme = tuple(np.asarray(next(iter(canaux.values()))).shape[:2])
            wcs, msg_w = suivi.wcs_grille(getattr(st, "cadre", None),
                                          forme=forme)
        else:
            forme, msg_w = None, "aucun canal"
        if wcs is None or not canaux:
            ligne["photo"] = {"t_s": 0.0, "ok": False,
                              "msg": f"WCS indisponible ({msg_w})"}
            ligne["spcc"] = {"t_s": 0.0, "ok": False,
                             "msg": f"WCS indisponible ({msg_w})"}
        else:
            res, dt, err = chrono(lambda: phot.mesurer(canaux, wcs,
                                                       forme=forme))
            gains, msgp = (res if isinstance(res, tuple) else (None, err or ""))
            ligne["photo"] = {"t_s": round(dt, 4), "ok": gains is not None,
                              "msg": str(msgp), "gains": dict(gains or {})}
            res, dt, err = chrono(lambda: sess.mesurer(
                canaux, wcs, CAPTEUR, {}, BLANC, forme=forme, mode=MODE))
            coef, msgs = (res if isinstance(res, tuple) else (None, err or ""))
            del coef                  # les coefficients vivent dans `sess`
            ligne["spcc"] = {"t_s": round(dt, 4), "ok": sess.valide,
                             "msg": str(msgs),
                             "capteur": sess.diag.get("capteur", "")}
        lignes.append(ligne)
        print(f"  palier {i:4d} : empilement {ligne['t_empilement_s']:6.2f} s | "
              f"astro {ligne['astro']['t_s']:6.2f} s | "
              f"Gaia {ligne['photo']['t_s']:6.2f} s | "
              f"SPCC {ligne['spcc']['t_s']:6.2f} s")
        for cle in ("astro", "photo", "spcc"):
            if not ligne[cle]["ok"]:
                print(f"           {cle:5s} : {ligne[cle]['msg'][:110]}")
    return lignes, depths


def resume(lignes, depths):
    """Tableau récapitulatif + bornes de coût (doublant / à chaque palier)."""
    retenus = retenus_doublants(depths)
    par_prof = {l["profondeur"]: l for l in lignes}

    def total(cle, sel):
        return sum(par_prof[n][cle]["t_s"] for n in sel if n in par_prof)

    print("\n=== Cout par palier (s) — mesure seule, empilement exclu ===")
    print("frames | astro | Gaia  | SPCC  | astro OK | Gaia OK | SPCC OK")
    for n in depths:
        l = par_prof.get(n)
        if l is None:
            continue
        print(f"{n:6d} | {l['astro']['t_s']:5.2f} | {l['photo']['t_s']:5.2f} | "
              f"{l['spcc']['t_s']:5.2f} | {str(l['astro']['ok']):8s} | "
              f"{str(l['photo']['ok']):7s} | {str(l['spcc']['ok']):7s}")
    print(f"\nPaliers retenus par une cadence DOUBLANTE : {retenus}")
    print(f"Cout cumule cadence doublante : astro {total('astro', retenus):.2f} s"
          f" + Gaia {total('photo', retenus):.2f} s"
          f" + SPCC {total('spcc', retenus):.2f} s")
    print(f"Cout cumule si CHAQUE palier mesurait : astro "
          f"{total('astro', depths):.2f} s + Gaia {total('photo', depths):.2f} s"
          f" + SPCC {total('spcc', depths):.2f} s")
    return {"paliers": depths, "retenus_doublants": retenus}


def autotest():
    """Mécanique du banc, SANS données : parsing et borne doublante."""
    ok = True

    def verifie(cond, msg):
        nonlocal ok
        ok &= bool(cond)
        print(("  OK    " if cond else "  ECHEC ") + msg)

    verifie(paliers("3, 6;12,6") == [3, 6, 12], "paliers : tri, doublons, ;")
    verifie(retenus_doublants([3, 6, 12, 24, 48]) == [3, 6, 12, 24, 48],
            "borne doublante : chaque palier double -> tous retenus")
    verifie(retenus_doublants([3, 4, 5, 6, 7, 12]) == [3, 6, 12],
            "borne doublante : 3, 4, 5, 7 non mesurés (pas de doublement)")
    verifie(set(canaux_de(np.zeros((4, 5), np.float32))) == {"L"},
            "canaux_de : image 2D -> L")
    r3 = canaux_de(np.zeros((4, 5, 3), np.float32))
    verifie(set(r3) == {"R", "G", "B"}, "canaux_de : image (H,W,3) -> R/G/B")
    return ok


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dossier", default=DEFAUT,
                   help=f"dossier de brutes FITS (défaut : {DEFAUT})")
    p.add_argument("--paliers", default="3,6,12,24,48",
                   help="profondeurs à chronométrer (défaut 3,6,12,24,48)")
    p.add_argument("--max", type=int, default=0,
                   help="nombre maximal de brutes lues (0 = toutes)")
    p.add_argument("--json", default=SORTIE, help="fichier de sortie JSON")
    p.add_argument("--autotest", action="store_true",
                   help="vérifie la mécanique du banc, sans données")
    a = p.parse_args(argv)
    if a.autotest:
        print("[autotest] mécanique du banc de mesure P1")
        return 0 if autotest() else 1
    depths = paliers(a.paliers)
    print(f"[banc] dossier = {a.dossier}")
    lignes, depths = mesurer(a.dossier, depths, a.max or None)
    recap = resume(lignes, depths)
    doc = {"horodatage": time.strftime("%Y-%m-%d %H:%M:%S"),
           "dossier": a.dossier, "lignes": lignes, **recap}
    try:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        print(f"\n[JSON] {a.json}")
    except OSError as exc:            # un JSON raté n'invalide pas la mesure
        print(f"\n[JSON] échec de l'écriture ({exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
