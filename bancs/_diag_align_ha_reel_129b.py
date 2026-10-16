# -*- coding: utf-8 -*-
"""DIAGNOSTIC 129b — REJEU HORS-LIGNE des VRAIES frames (L / G / Ha) dans le
vrai aligneur, AVANT tout correctif.

But (règle d'or du chantier LRGB+Ha : « pas de correctif non mesuré ») :
  nommer la raison EXACTE des refus du rôle Ha mesurés en réel le 15/10/2026
  (dossier Ha de ~40 frames, ~69 % de refus), et vérifier l'hypothèse du
  correctif : « en composition broadband+Ha, le Ha est le SEUL rôle aligné en
  INTER-FILTRES ; `triangles_seuls = False` y laisse l'ORB passer d'abord, or
  l'ORB s'apparie mal d'un filtre à l'autre (jalon 21) ».

MESURES (rien n'est modifié) :
  [1] ORB, porte par porte, sur des frames Ha contre une référence L : nombre
      de keypoints/descripteurs (réf et frame), appariements « good »
      (ratio test), inliers RANSAC, validité `_M_valide` — dit OÙ l'ORB meurt ;
  [2] `compute()` réel, en séquence, `triangles_seuls` False PUIS True,
      référence = 1re brute L : compte des ACCEPTÉS et méthode employée
      (l'aligneur n'écrit rien au journal : c'est ce relevé qui documente) ;
  [3] TÉMOIN broadband (référence L vs frames G) : le problème est-il propre au
      Ha ou général à l'inter-filtres ?
  [4] TÉMOIN intra-Ha (référence = 1re brute Ha vs frames Ha) : le Ha est-il
      alignable quand il est l'ANCRE (cas HOO/SHO) ?

Usage (les dossiers viennent de config.json ; surchargeables) :
  python bancs/_diag_align_ha_reel_129b.py [NB_FRAMES_PAR_ROLE] [RACINE]
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import os
import sys

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV/OpenCL au teardown sinon

from avastack.processing import alignment as al_mod
from avastack.processing import stars as st_mod
from avastack.processing.composition import extraire_canal
import avastack.images as images

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Dossiers RÉELS du test (relevés dans config.json, session du 15/10/2026).
RACINE_DEFAUT = (r"\\192.168.155.45\Telechargements\Astro\SV555\NINA"
                 r"\2026-09-22\Soiree_20260922\M 33\LIGHT\QHYminiCam8M"
                 r"\Full Resolution\1x1")
DOSSIERS = (("L", "60.00"), ("R", "60.00"), ("G", "60.00"),
            ("B", "60.00"), ("Ha", "180.00"))


def dossier_de(racine, role, expo):
    return os.path.join(racine, expo, "-15.00", "90", "25", role)


def lister(racine, role, expo, n):
    """Les `n` brutes RÉPARTIES sur le dossier (jamais les 3 mêmes)."""
    d = dossier_de(racine, role, expo)
    if not os.path.isdir(d):
        return []
    f = sorted(x for x in os.listdir(d)
               if x.lower().endswith((".fits", ".fit", ".fts")))
    if not f:
        return []
    idx = np.unique(np.linspace(0, len(f) - 1, min(n, len(f))).astype(int))
    return [os.path.join(d, f[i]) for i in idx]


def charger(chemin, role):
    """Canal du rôle (mono : tel quel) — même charge que le worker."""
    a = np.asarray(images.load_image(chemin), np.float32)
    return extraire_canal(a, role)


def orb_portes(al, frame):
    """Rejoue la BRANCHE ORB de `_compute_direct` et rend chaque porte.

    Rend un dict : kp/ref/desc, appariements « good », inliers RANSAC et la
    PREMIÈRE porte qui lâche (c'est elle qui explique le refus)."""
    g = al._norm8(frame)                       # bornes PROPRES à la frame
    kp, des = al.orb.detectAndCompute(g, None)
    n_kp = len(kp) if kp is not None else 0
    n_ref = len(al.ref_kp) if al.ref_kp is not None else 0
    r = {"kp": n_kp, "ref": n_ref, "good": 0, "inl": 0, "porte": ""}
    if des is None or al.ref_des is None:
        r["porte"] = "pas de descripteurs"
        return r
    if n_kp < al.min_matches or n_ref < al.min_matches:
        r["porte"] = f"kp < min_matches({al.min_matches})"
        return r
    good = [p[0] for p in al.bf.knnMatch(al.ref_des, des, k=2)
            if len(p) == 2 and p[0].distance < al.ratio * p[1].distance]
    r["good"] = len(good)
    if len(good) < al.min_matches:
        r["porte"] = f"good < min_matches({al.min_matches})"
        return r
    src = np.float32([kp[m.trainIdx].pt for m in good])
    dst = np.float32([al.ref_kp[m.queryIdx].pt for m in good])
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                         ransacReprojThreshold=2.0,
                                         maxIters=5000)
    if M is None or inl is None:
        r["porte"] = "RANSAC sans matrice"
        return r
    r["inl"] = int(inl.sum())
    if r["inl"] < al.min_inliers:
        r["porte"] = f"inliers < min_inliers({al.min_inliers})"
        return r
    if not al_mod._M_valide(M):
        ang, ech, _dx, _dy = al_mod.infos_M(M)
        r["porte"] = f"_M_valide (angle {ang:+.1f}°, éch {ech:.4f})"
        return r
    r["porte"] = "OK (l'ORB suffirait)"
    return r


def meilleur_triangles(ref_pos, pos, n_max, pairs_max=2000):
    """Meilleure transformation par triangles SANS `_M_valide` (comme
    `_diag_align_verite.angle_verite`), sur les `n_max` plus brillantes.

    → (n_inliers, angle, échelle, nb_paires) ou None. Sert à savoir si une
    réponse EXISTE : si `n_max` large la trouve alors que la valeur nominale
    échoue, le blocage est dans la BASE D'ÉTOILES, pas dans la géométrie."""
    inv_r, som_r, _ = al_mod._invariants_triangles(ref_pos, n_max)
    inv_c, som_c, _ = al_mod._invariants_triangles(pos, n_max)
    if inv_r is None or inv_c is None:
        return None
    ecart = np.abs(inv_r[:, None, :] - inv_c[None, :, :]).max(-1)
    paires = np.argwhere(ecart <= al_mod.TRI_TOL)
    if not len(paires):
        return None
    if len(paires) > pairs_max:
        o = np.argsort(ecart[paires[:, 0], paires[:, 1]])[:pairs_max]
        paires = paires[o]
    p_ref = np.asarray(ref_pos, np.float32)
    p_cur = np.asarray(pos, np.float32)
    best = None
    for ir, ic in paires:
        M0 = cv2.getAffineTransform(p_cur[som_c[ic]].astype(np.float32),
                                    p_ref[som_r[ir]].astype(np.float32))
        if M0 is None or not np.isfinite(M0).all():
            continue
        ang, ech, _dx, _dy = al_mod.infos_M(M0)
        if not (0.5 <= ech <= 2.0):            # borne LARGE (pas _M_valide)
            continue
        pc = cv2.transform(p_cur.reshape(-1, 1, 2), M0)[:, 0, :]
        d2 = np.hypot(pc[:, None, 0] - p_ref[None, :, 0],
                      pc[:, None, 1] - p_ref[None, :, 1])
        n = int((d2.min(1) <= al_mod.TRI_RAYON).sum())
        if best is None or n > best[0]:
            best = (n, ang, ech, len(paires))
    return best


def sequence(nom, ref_img, frames, triangles_seuls):
    """Rejoue `frames` (en SÉQUENCE, comme le worker) sur une référence."""
    al = al_mod.StarAligner()
    al.triangles_seuls = triangles_seuls
    al.set_reference(ref_img)
    res = []
    for f in frames:
        M, ok = al.compute(f)
        res.append((bool(ok) and M is not None,
                    (al.dernier or {}).get("methode", "-")))
    n_ok = sum(1 for ok, _m in res if ok)
    detail = {}
    for ok, m in res:
        if ok:
            detail[m] = detail.get(m, 0) + 1
    txt = " · ".join(f"{k} ×{v}" for k, v in detail.items()) or "aucun"
    print(f"  {nom:28s} acceptés {n_ok}/{len(res)}   ({txt})")
    return n_ok, len(res)


def main(argv):
    n = int(argv[0]) if argv else 8
    racine = argv[1] if len(argv) > 1 else RACINE_DEFAUT
    print("=" * 78)
    print("DIAGNOSTIC 129b — rejeu des VRAIES frames L/G/Ha dans le vrai aligneur")
    print("=" * 78)
    print(f"racine : {racine}")
    print(f"échantillon : {n} frames par rôle\n")
    chemins = {}
    for role, expo in DOSSIERS:
        chemins[role] = lister(racine, role, expo, n)
        print(f"  {role:3s} ({expo:>6s}s) : {len(chemins[role])} frame(s) "
              f"retenue(s)")
    if not chemins.get("L") or not chemins.get("Ha"):
        print("\nSTOP : dossiers L ou Ha indisponibles (partage non monté ?)")
        return 2
    print()

    ref_L = charger(chemins["L"][0], "L")
    ref_Ha = charger(chemins["Ha"][0], "Ha")
    print(f"référence L  : {os.path.basename(chemins['L'][0])}"
          f" → forme {ref_L.shape}")
    pos_L, msg_L = st_mod.detecter_positions(
        ref_L, max_etoiles=al_mod.MAX_ALIGN_ETOILES)
    print(f"  étoiles référence L  : {len(pos_L)} « {msg_L} »")
    pos_Ha, msg_Ha = st_mod.detecter_positions(
        ref_Ha, max_etoiles=al_mod.MAX_ALIGN_ETOILES)
    print(f"  étoiles référence Ha : {len(pos_Ha)} « {msg_Ha} »")
    print()

    def positions(img):
        """Positions EXACTEMENT comme l'aligneur (étoiles réparties)."""
        return st_mod.detecter_positions(
            al_mod.canal_alignement(img),
            max_etoiles=al_mod.MAX_ALIGN_ETOILES,
            distance_min=al_mod._distance_repartition(img.shape))[0]

    cibles_G, cibles_Ha, pos_cibles_G, pos_cibles_Ha = [], [], [], []
    for role, cibles, pos_liste in (("G", cibles_G, pos_cibles_G),
                                    ("Ha", cibles_Ha, pos_cibles_Ha)):
        for p in chemins[role]:
            img = charger(p, role)
            cibles.append(img)
            pos = positions(img)
            pos_liste.append(pos)
            print(f"  étoiles {role:3s} {os.path.basename(p):42s} {len(pos):4d}")
    print()

    print("[1] ORB, PORTE PAR PORTE (référence = L, cibles = Ha)")
    al = al_mod.StarAligner()
    al.set_reference(ref_L)
    print(f"  ORB référence : {len(al.ref_kp)} keypoints")
    for nom, img in zip(chemins["Ha"], cibles_Ha):
        r = orb_portes(al, img)
        print(f"  {os.path.basename(nom):42s} kp {r['kp']:4d} · good "
              f"{r['good']:4d} · inliers {r['inl']:4d} → {r['porte']}")
    print()

    print("[2] `compute()` RÉEL en séquence — référence = 1re brute L")
    sequence("Ha · triangles_seuls=False", ref_L, cibles_Ha, False)
    sequence("Ha · triangles_seuls=True", ref_L, cibles_Ha, True)
    print()

    print("[3] TÉMOIN broadband — référence = 1re brute L, cibles = G")
    sequence("G · triangles_seuls=False", ref_L, cibles_G, False)
    sequence("G · triangles_seuls=True", ref_L, cibles_G, True)
    print()

    print("[4] TÉMOIN intra-Ha — référence = 1re brute Ha, cibles = Ha")
    sequence("Ha · triangles_seuls=False", ref_Ha, cibles_Ha[1:], False)
    sequence("Ha · triangles_seuls=True", ref_Ha, cibles_Ha[1:], True)
    print()
    print("[5] GÉOMÉTRIE RÉELLE sans `_M_valide` — la BASE D'ÉTOILES est-elle "
          "le verrou ?")
    n_fige = getattr(al_mod, "TRI_N_MAX", 12)
    print(f"  TRI_N_MAX={n_fige} · TRI_TOL={al_mod.TRI_TOL} · "
          f"TRI_RAYON={al_mod.TRI_RAYON} · TRI_INLIERS_MIN="
          f"{al_mod.TRI_INLIERS_MIN}")
    pos_ref_L = positions(ref_L)

    def ligne_geo(etiq, nom, pos):
        cells = []
        for nm in (n_fige, 18, 24, 30):
            b = meilleur_triangles(pos_ref_L, pos, nm)
            cells.append(f"n={nm:2d}: " + ("aucun" if b is None
                                           else f"{b[0]:3d}inl {b[1]:+6.1f}°"))
        print(f"  {etiq:3s} {os.path.basename(nom):42s} " + " · ".join(cells))

    def ligne_geo_ha(ref_pos, etiq, nom, pos):
        """Comme `ligne_geo`, mais avec une référence EXPLICITE (ancre Ha)."""
        cells = []
        for nm in (n_fige, 18, 24, 30):
            b = meilleur_triangles(ref_pos, pos, nm)
            cells.append(f"n={nm:2d}: " + ("aucun" if b is None
                                           else f"{b[0]:3d}inl {b[1]:+6.1f}°"))
        print(f"  {etiq:3s} {os.path.basename(nom):42s} " + " · ".join(cells))

    for nom, pos in list(zip(chemins["Ha"], pos_cibles_Ha))[:4]:
        ligne_geo("Ha", nom, pos)
    for nom, pos in list(zip(chemins["G"], pos_cibles_G))[:2]:
        ligne_geo("G", nom, pos)
    print()
    print("[6] ANCRE Ha — le Ha en RÉFÉRENCE (cibles = L puis G)")
    cibles_L = [charger(p, "L") for p in chemins["L"]]
    pos_cibles_L = [positions(i) for i in cibles_L]
    pos_ref_Ha = positions(ref_Ha)
    print(f"  étoiles dans la référence Ha : {len(pos_ref_Ha)}")
    sequence("L vs ancre Ha · False", ref_Ha, cibles_L, False)
    sequence("L vs ancre Ha · True", ref_Ha, cibles_L, True)
    sequence("G vs ancre Ha · False", ref_Ha, cibles_G, False)
    sequence("G vs ancre Ha · True", ref_Ha, cibles_G, True)
    print("  géométrie (référence = brute Ha) :")
    for nom, pos in list(zip(chemins["L"], pos_cibles_L))[:2]:
        ligne_geo_ha(pos_ref_Ha, "L", nom, pos)
    for nom, pos in list(zip(chemins["G"], pos_cibles_G))[:2]:
        ligne_geo_ha(pos_ref_Ha, "G", nom, pos)
    # Ha EMPILÉ (frames Ha alignées ENTRE ELLES — intra-rôle, mesuré 4/4) :
    # un Ha profond détecte-t-il assez d'étoiles pour servir d'ancre ?
    al_h = al_mod.StarAligner()
    al_h.set_reference(cibles_Ha[0])
    poses = [cibles_Ha[0]]
    for f in cibles_Ha[1:]:
        M, ok = al_h.compute(f)
        if ok and M is not None:
            poses.append(cv2.warpAffine(f, M, (f.shape[1], f.shape[0]),
                                        flags=cv2.INTER_LINEAR))
    pile = np.mean(np.stack(poses), axis=0)
    pos_pile = positions(pile)
    print(f"  Ha EMPILÉ ({len(poses)} frames) : {len(pos_pile)} étoiles "
          f"détectées (brute Ha seule : {len(pos_ref_Ha)})")
    sequence("L vs Ha empilé · True", pile, cibles_L, True)
    sequence("G vs Ha empilé · True", pile, cibles_G, True)
    for nom, pos in list(zip(chemins["L"], pos_cibles_L))[:2]:
        ligne_geo_ha(pos_pile, "L", nom, pos)
    for nom, pos in list(zip(chemins["G"], pos_cibles_G))[:2]:
        ligne_geo_ha(pos_pile, "G", nom, pos)
    print()
    print("LECTURE : si [2] True ≫ False et que [4] est bon, le correctif 129b")
    print("est « triangles seuls dès qu'un Ha est fusionné » (l'ancre restant")
    print("broadband). Si [3] est mauvais aussi, le problème est plus général.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
