# -*- coding: utf-8 -*-
r"""Diagnostic de l'appariement RANSAC de paires (jalon 56, retour d'Alain).

Prend un WCS VRAI (ASTAP) comme référence pour savoir quelles étoiles image
correspondent à quelles étoiles catalogue, puis instrumente le vote
(échelle, angle) ET l'étape 2 (similitude exacte + appariement mutuel) : le
meilleur nombre d'inliers atteignable est comparé à ce que `_ransac_paires`
trouve réellement. Tranche entre « données décalées » et « bug du solveur ».

Usage : python bancs/_diag_vote.py <image> --ra <deg> --dec <deg> --champ <deg>
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import argparse
import math
import os
import sys
import tempfile

import numpy as np

from avastack.catalogues import solveur as S
from avastack.catalogues.astap import resoudre_avec_astap
from avastack.images import borner_lineaire, load_image, save_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def entrees_du_vote(img, ra, dec, champ):
    """Reproduit EXACTEMENT ce que `resoudre` passe à `_ransac_paires`."""
    h, w = img.shape[:2]
    pos, _m = S._detecter(img, S.MAX_ETOILES_DETECTION)
    et, _m2 = S._extraire_catalogue(ra, dec, champ, (h, w))
    xi, eta = S.projection_tan(et["ra"], et["dec"], ra, dec)
    dans = S.masque_champ(xi, eta, champ, (h, w))
    xi, eta = xi[dans], eta[dans]
    ra_c, dec_c = et["ra"][dans], et["dec"][dans]
    ordre = np.argsort(et["g"][dans])[:S.N_CAT_MAX]
    xi, eta = xi[ordre], eta[ordre]
    ra_c, dec_c = ra_c[ordre], dec_c[ordre]
    cat_xy = np.column_stack([xi, eta])
    return (pos, cat_xy, champ / float(w), (h, w), ra_c, dec_c)


def _similitude(s0, s1, d0, d1):
    """Similitude exacte qui envoie s0→d0 et s1→d1 (A, t) : prédiction = A·x+t.
    Copie fidèle de ce que fait `_ransac_paires` (étape 2)."""
    vs, vd = np.asarray(s1) - np.asarray(s0), np.asarray(d1) - np.asarray(d0)
    ls, ld = math.hypot(*vs), math.hypot(*vd)
    cth = (vs @ vd) / (ls * ld)
    sth = (vs[0] * vd[1] - vs[1] * vd[0]) / (ls * ld)
    A = (ld / ls) * np.array([[cth, -sth], [sth, cth]])
    return A, np.asarray(d0) - A @ np.asarray(s0)


def principal():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("--ra", type=float, required=True)
    ap.add_argument("--dec", type=float, required=True)
    ap.add_argument("--champ", type=float, required=True)
    a = ap.parse_args()

    img = load_image(a.image)
    h, w = img.shape[:2]
    print(f"image {w}×{h}")
    with tempfile.TemporaryDirectory(prefix="avastack_vote_") as tmp:
        bornee, _ = borner_lineaire(img)
        copie = os.path.join(tmp, "b.fits")
        save_image(copie, bornee)
        wcs, msg = resoudre_avec_astap(copie, ra0=a.ra, dec0=a.dec,
                                       rayon_deg=1.0, fov_deg=a.champ * h / w,
                                       dossier_sortie=tmp, timeout=180)
    if wcs is None:
        print("ASTAP : ÉCHEC —", msg)
        return 1
    print(f"WCS vrai : échelle {wcs.echelle_arcsec:.4f}\"/px, "
          f"angle {wcs.angle_deg:+.2f}°")

    pos, cat_xy, ech_deg, forme, ra_c, dec_c = entrees_du_vote(
        img, a.ra, a.dec, a.champ)
    n_img = min(S.RANSAC_N_IMG, len(pos))
    n_cat = min(S.RANSAC_N_CAT, len(cat_xy))
    P, C = pos[:n_img], cat_xy[:n_cat]
    print(f"pos {len(pos)} étoiles (top-{n_img} au vote) ; catalogue "
          f"clippé/trié {len(cat_xy)} (top-{n_cat} au vote) ; ech_deg "
          f"{ech_deg * 3600:.4f}\"/px")

    # Correspondances VRAIES (WCS ASTAP)
    ra_i, dec_i = wcs.vers_radec(pos)
    cosd = math.cos(math.radians(a.dec))
    d_px = np.hypot((ra_i[:, None] - ra_c[None, :]) * cosd,
                    dec_i[:, None] - dec_c[None, :]) \
        * 3600.0 / wcs.echelle_arcsec
    vraie = d_px.argmin(1)
    dmin = d_px[np.arange(len(pos)), vraie]
    print(f"contreparties fiables (< 2 px) : {int((dmin <= 2).sum())}/{len(pos)}"
          f" ; < 1 px : {int((dmin <= 1).sum())}")
    vraie[dmin > 2.0] = -1

    # --- TEST A : similitude depuis les VRAIES correspondances -------------
    res = []
    for i1 in range(n_img):
        for i2 in range(i1 + 1, n_img):
            c1, c2 = vraie[i1], vraie[i2]
            if c1 < 0 or c2 < 0 or c1 >= n_cat or c2 >= n_cat:
                continue
            for mir in (False, True):
                G = S._grille_indice(cat_xy, ech_deg, forme, mir)
                A_, t_ = _similitude(G[c1], G[c2], P[i1], P[i2])
                ia_, _ = S._appariements_mutuels(pos, G @ A_.T + t_,
                                                 S.MUTUEL_RAYON)[:2]
                res.append((len(ia_), i1, i2, c1, c2, mir))
    res.sort(reverse=True)
    print(f"[A] similitude depuis les VRAIES correspondances : {len(res)} "
          f"testées ; MEILLEUR = {res[0][0] if res else 0} inliers "
          f"{res[0][1:] if res else ''}")

    # --- TEST B : rejeu fidèle du VOTE (échelle, angle) --------------------
    G_f = S._grille_indice(C, ech_deg, forme, False)
    G_t = S._grille_indice(C, ech_deg, forme, True)
    ii_p = np.array([(x, y) for x in range(n_img) for y in range(x + 1, n_img)])
    kk_p = np.array([(x, y) for x in range(n_cat) for y in range(x + 1, n_cat)])
    vi = P[ii_p[:, 1]] - P[ii_p[:, 0]]
    li = np.hypot(vi[:, 0], vi[:, 1])
    ai = np.arctan2(vi[:, 1], vi[:, 0])
    vf = G_f[kk_p[:, 1]] - G_f[kk_p[:, 0]]
    vt = G_t[kk_p[:, 1]] - G_t[kk_p[:, 0]]
    lc = np.hypot(vf[:, 0], vf[:, 1])
    ac_f = np.arctan2(vf[:, 1], vf[:, 0])
    ac_t = np.arctan2(vt[:, 1], vt[:, 0])
    gi, gc = li >= S.RANSAC_PAIRES_MIN, lc >= S.RANSAC_PAIRES_MIN
    kk_p, lc, ac_f, ac_t = kk_p[gc], lc[gc], ac_f[gc], ac_t[gc]
    ii_p, li, ai = ii_p[gi], li[gi], ai[gi]
    e_lo, e_hi = 1.0 - S.RANSAC_ECH_REL, 1.0 + S.RANSAC_ECH_REL
    n_e = int(round((e_hi - e_lo) / S.RANSAC_PAS_ECH))
    n_a = int(round(2.0 * math.pi / S.RANSAC_PAS_ANG))
    edges_e = np.linspace(e_lo, e_hi, n_e + 1)
    edges_a = np.linspace(-math.pi, math.pi, n_a + 1)
    vote = np.zeros((n_e, n_a), np.int32)
    for ang_cat in (ac_f, ac_f + math.pi, ac_t, ac_t + math.pi):
        for a_ in range(0, len(ii_p), 64):
            b_ = min(a_ + 64, len(ii_p))
            dang = (ai[a_:b_, None] - ang_cat[None, :] + math.pi) \
                % (2.0 * math.pi) - math.pi
            ech = li[a_:b_, None] / lc[None, :]
            ok = (ech >= e_lo) & (ech <= e_hi)
            H, _, _ = np.histogram2d(ech[ok], dang[ok], bins=(edges_e, edges_a))
            vote += H.astype(np.int32)
    pic = np.unravel_index(vote.argmax(), vote.shape)
    ech_pic = 0.5 * (edges_e[pic[0]] + edges_e[pic[0] + 1])
    ang_pic = 0.5 * (edges_a[pic[1]] + edges_a[pic[1] + 1])
    cas = ((ac_f, 0, False), (ac_f + math.pi, 1, False),
           (ac_t, 0, True), (ac_t + math.pi, 1, True))
    print(f"[B] vote : pic {int(vote[pic])} paires ; échelle relative "
          f"{ech_pic:.4f} → {ech_pic * ech_deg * 3600:.4f}\"/px ; angle "
          f"{math.degrees(ang_pic):+.2f}°")

    # --- TEST B2 : vote SÉPARÉ par hypothèse (miroir × sens) ---------------
    print("[B2] vote séparé par hypothèse :")
    infos_cas = []
    for ang_cat, anc, mir in cas:
        v1 = np.zeros((n_e, n_a), np.int32)
        for a_ in range(0, len(ii_p), 64):
            b_ = min(a_ + 64, len(ii_p))
            dang = (ai[a_:b_, None] - ang_cat[None, :] + math.pi) \
                % (2.0 * math.pi) - math.pi
            ech = li[a_:b_, None] / lc[None, :]
            ok = (ech >= e_lo) & (ech <= e_hi)
            H, _, _ = np.histogram2d(ech[ok], dang[ok], bins=(edges_e, edges_a))
            v1 += H.astype(np.int32)
        p1 = np.unravel_index(v1.argmax(), v1.shape)
        e1 = 0.5 * (edges_e[p1[0]] + edges_e[p1[0] + 1])
        a1 = 0.5 * (edges_a[p1[1]] + edges_a[p1[1] + 1])
        infos_cas.append((float(v1[p1]), e1, a1, anc, mir, ang_cat))
        print(f"    anc={anc} miroir={mir} : pic {int(v1[p1]):5d} ; échelle "
              f"{e1:.4f} → {e1 * ech_deg * 3600:.4f}\"/px ; angle "
              f"{math.degrees(a1):+.2f}°")

    # --- TEST C : COPIE littérale de l'étape 2, instrumentée ---------------
    meilleur_len, meilleur_info, n_cand = 0, None, 0
    for ang_cat, anc, mir in cas:
        G = S._grille_indice(cat_xy, ech_deg, forme, mir)
        for a_ in range(0, len(ii_p), 64):
            b_ = min(a_ + 64, len(ii_p))
            dang = (ai[a_:b_, None] - ang_cat[None, :] + math.pi) \
                % (2.0 * math.pi) - math.pi
            ech = li[a_:b_, None] / lc[None, :]
            ok = ((np.abs(ech - ech_pic) < S.RANSAC_TOL_E)
                  & (np.abs(dang - ang_pic) < S.RANSAC_TOL_A))
            rws, cls = np.nonzero(ok)
            n_cand += len(rws)
            for r_, c_ in zip(rws, cls):
                i1, i2 = ii_p[a_ + r_]
                k1, k2 = kk_p[c_]
                ka_, kb_ = (k1, k2) if anc == 0 else (k2, k1)
                A_, t_ = _similitude(G[ka_], G[kb_], P[i1], P[i2])
                ia_, _ = S._appariements_mutuels(pos, G @ A_.T + t_,
                                                 S.MUTUEL_RAYON)[:2]
                if len(ia_) > meilleur_len:
                    meilleur_len = len(ia_)
                    meilleur_info = (anc, mir, i1, i2, k1, k2)
    print(f"[C] étape 2 copiée : {n_cand} candidats ; MEILLEUR = "
          f"{meilleur_len} inliers ; info {meilleur_info}")

    # --- TEST C2 : étape 2 avec le pic PROPRE à chaque hypothèse -----------
    print("[C2] étape 2 avec le pic PROPRE au cas (correction proposée) :")
    meilleur_global, info_global = 0, None
    for pic_val, e_c, a_c, anc, mir, ang_cat in infos_cas:
        G = S._grille_indice(cat_xy, ech_deg, forme, mir)
        n_best, res_c = 0, None
        for a_ in range(0, len(ii_p), 64):
            b_ = min(a_ + 64, len(ii_p))
            dang = (ai[a_:b_, None] - ang_cat[None, :] + math.pi) \
                % (2.0 * math.pi) - math.pi
            ech = li[a_:b_, None] / lc[None, :]
            ok = ((np.abs(ech - e_c) < S.RANSAC_TOL_E)
                  & (np.abs(dang - a_c) < S.RANSAC_TOL_A))
            rws, cls = np.nonzero(ok)
            for r_, c_ in zip(rws, cls):
                i1, i2 = ii_p[a_ + r_]
                k1, k2 = kk_p[c_]
                ka_, kb_ = (k1, k2) if anc == 0 else (k2, k1)
                A_, t_ = _similitude(G[ka_], G[kb_], P[i1], P[i2])
                ia_, _ = S._appariements_mutuels(pos, G @ A_.T + t_,
                                                 S.MUTUEL_RAYON)[:2]
                if len(ia_) > n_best:
                    n_best, res_c = len(ia_), (i1, i2, k1, k2)
        print(f"    anc={anc} miroir={mir} (pic {int(pic_val)}) : "
              f"MEILLEUR = {n_best} inliers {res_c}")
        if n_best > meilleur_global:
            meilleur_global, info_global = n_best, (anc, mir)
    print(f"[C2] meilleur GLOBAL = {meilleur_global} inliers (cas "
          f"{info_global})")

    # --- TEST E : la paire CONNUE bonne passe-t-elle le filtre du bin ? ----
    i1c, i2c = int(res[0][1]), int(res[0][2])
    c1c, c2c = int(res[0][3]), int(res[0][4])
    r0 = int(np.flatnonzero((ii_p[:, 0] == i1c) & (ii_p[:, 1] == i2c))[0])
    c0 = int(np.flatnonzero((kk_p[:, 0] == min(c1c, c2c))
                            & (kk_p[:, 1] == max(c1c, c2c)))[0])
    print(f"[E] paire connue bonne : image ({i1c},{i2c}) [index {r0}] ↔ "
          f"catalogue ({c1c},{c2c}) [index {c0}], miroir={res[0][5]}")
    print(f"    li = {li[r0]:.2f} px ; lc = {lc[c0]:.2f} px ; "
          f"ech[paire] = {li[r0] / lc[c0]:.6f}")
    for pic_val, e_c, a_c, anc, mir, ang_cat in infos_cas:
        d_ = (ai[r0] - ang_cat[c0] + math.pi) % (2.0 * math.pi) - math.pi
        e_ = li[r0] / lc[c0]
        print(f"    cas anc={anc} mir={mir} : ech = {e_:.6f} (pic {e_c:.6f}, "
              f"écart {abs(e_ - e_c):.6f} vs tol {S.RANSAC_TOL_E}) ; "
              f"dang = {math.degrees(d_):+.3f}° (pic {math.degrees(a_c):+.3f}°, "
              f"écart {math.degrees(abs(d_ - a_c)):.3f}° vs tol "
              f"{math.degrees(S.RANSAC_TOL_A):.3f}°)")

    ia, ib, A, t, mir, msg = S._ransac_paires(pos, cat_xy, ech_deg, forme)
    print(f"[D] _ransac_paires RÉEL : inliers={0 if ia is None else len(ia)} ; "
          f"message=« {msg} »")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
