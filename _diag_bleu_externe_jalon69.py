# -*- coding: utf-8 -*-
"""Diag jalon 69 — « LE FICHIER TRAITÉ EXTERNE A-T-IL PLUS DE BRUIT BLEU QUE LE
STACK ? » (impression d'Alain, 27/09/2026, après test de la v2.38.1 ; les deux
fichiers comparés sont les « tel que vu » v2.38.1).

Méthode (celle du projet, pour rester comparable aux mesures d'AVANCEMENT) :
  • FOND : médiane par canal de la zone centrale (comme `_diag_empilement_couleur.py`) ;
  • PLANCHER DE BRUIT : σ robuste (MAD × 1,4826) des blocs 96×96 les PLUS LISSES
    — peu importe où est le ciel, ce qui compte est l'équilibre R/G et B/G ;
  • GRAIN CHROMATIQUE : σ et MAD de (R−G) et (B−G) sur un fond COMMUN aux deux
    fichiers (blocs les plus lisses des DEUX, intersectés), le fond étant le même
    pixel dans les deux images (alignement vérifié) ;
  • NORMALISATION : le grain chromatique est rapporté ① au grain de LUMINANCE
    (part du bruit qui est colorée — indépendant de l'étirement) et ② au NIVEAU
    du fond (l'étirement logD diffère entre les deux fichiers).

Usage : python _diag_bleu_externe_jalon69.py
"""
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)

from avastack.images import load_image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FICHIERS = [
    ("STACK  (vue empilement, tel que vu)",
     r"C:\Astro\test\m31_stack_etire-telquevu_traite-v2.38.1.fits"),
    ("EXTERNE (vue traitée ⚡, tel que vu)",
     r"C:\Astro\test\m31_traite_externe_etire-v2.38.1.fits"),
]
# Usage libre : python _diag_bleu_externe_jalon69.py <ref.fits> <autre.fits>
# (le redressement du miroir vertical est détecté automatiquement, donc les
#  fichiers produits AVANT la v2.38.2 se comparent sans précaution)
_args = [a for a in sys.argv[1:] if not a.startswith("-")]
if len(_args) >= 2:
    FICHIERS = [("FICHIER 1 (référence)", _args[0]),
                ("FICHIER 2 (à comparer)", _args[1])]
CLES = ("AVAVUE", "AVAAPPLI", "AVACOMPO", "AVASPCC", "AVAGAIA", "AVAWB",
        "AVAFIT", "AVALAYER", "AVAFRAME", "AVASCALE", "AVANAN", "FILTER")
BLOC = 96


def entete(path):
    from astropy.io import fits
    h = fits.open(path)[0].header
    for k in CLES:
        if k in h:
            print(f"    {k:<9} = {h[k]}")


def zones_lisses(img, n, bloc=BLOC):
    """n blocs `bloc`×`bloc` les plus lisses (MAD de la luminance), renvoyés
    comme liste de (y, x) — le MÊME découpage pour toutes les images de même
    taille (les blocs sont alignés sur la grille)."""
    a = np.asarray(img, np.float32)
    lum = a.mean(axis=2) if a.ndim == 3 else a
    h, w = lum.shape[:2]
    scores = []
    for y in range(0, h - bloc + 1, bloc):
        for x in range(0, w - bloc + 1, bloc):
            v = lum[y:y + bloc, x:x + bloc].ravel()
            m = float(np.median(v))
            scores.append((1.4826 * float(np.median(np.abs(v - m))), y, x))
    scores.sort()
    return [(y, x) for _, y, x in scores[:n]]


def mad(v):
    """Échelle ROBUSTE (MAD × 1,4826) — la bonne mesure d'un grain."""
    v = np.asarray(v, np.float64).ravel()
    return 1.4826 * float(np.median(np.abs(v - np.median(v))))


def sablier(img, blocs):
    """(R, G, B) empilés sur les blocs donnés."""
    a = np.asarray(img, np.float32)
    parts = [a[y:y + BLOC, x:x + BLOC] for (y, x) in blocs]
    z = np.concatenate([p.reshape(-1, a.shape[-1]) for p in parts], 0)
    return z[:, 0], z[:, 1], z[:, 2]


print("=" * 78)
print("[0] inspection : provenance (en-tête) et géométrie")
print("=" * 78)
imgs = []
for titre, p in FICHIERS:
    try:
        img = load_image(p)
    except Exception as e:                      # fichier absent/illisible
        print(f"  ABSENT/ILLISIBLE : {p} ({e})")
        imgs.append(None)
        continue
    imgs.append(img)
    print(f"\n  {titre}\n    {p}")
    print(f"    {img.shape} · {img.dtype} · min {float(img.min()):.4f} "
          f"· max {float(img.max()):.4f}")
    entete(p)
if any(i is None for i in imgs):
    raise SystemExit(2)

a, b = imgs
alignes = (a.shape == b.shape)
if alignes:
    # La corrélation de PHASE est trompeuse ici : le fichier externe a subi un
    # retrait de gradient (son fond n'a plus les mêmes basses fréquences), la
    # phase ne « voit » donc aucun décalage fiable. Test ROBUSTE : on chercher
    # un morceau central du stack dans l'externe, sous QUATRE hypothèses
    # (identité, miroir haut-bas, miroir gauche-droite, les deux).
    ech = 8

    def petit(img, mir=0):
        s = cv2.resize(np.asarray(img, np.float32),
                       (img.shape[1] // ech, img.shape[0] // ech),
                       interpolation=cv2.INTER_AREA)
        if mir in (1, 3):
            s = s[::-1]
        if mir in (2, 3):
            s = s[:, ::-1]
        return s

    def norme(x):
        m = float(np.median(x))
        return (x - m) / max(1e-6, 1.4826 * float(np.median(np.abs(x - m))))

    ref = norme(cv2.cvtColor(petit(a), cv2.COLOR_RGB2GRAY))
    cote = 160                                    # 160×8 = 1280 px pleine rés.
    y0 = (ref.shape[0] - cote) // 2
    x0 = (ref.shape[1] - cote) // 2
    mot = ref[y0:y0 + cote, x0:x0 + cote]
    print(f"\n  recherche d'un morceau central du stack "
          f"({cote * ech} px pleine résolution) dans l'autre fichier :")
    meilleur = None
    for mir, nom in ((0, "tel quel"), (1, "miroir haut-bas"),
                     (2, "miroir gauche-droite"), (3, "miroir H et V")):
        cible = norme(cv2.cvtColor(petit(b, mir), cv2.COLOR_RGB2GRAY))
        if (cible.shape[0] < cote or cible.shape[1] < cote):
            continue
        r = cv2.matchTemplate(cible.astype(np.float32),
                              mot.astype(np.float32), cv2.TM_CCOEFF_NORMED)
        _, sc, _, loc = cv2.minMaxLoc(r)
        print(f"    {nom:<20} corrélation {sc:+.3f} · décalage "
              f"({(loc[0] - x0) * ech:+d}, {(loc[1] - y0) * ech:+d}) px")
        if meilleur is None or sc > meilleur[0]:
            meilleur = (sc, nom, mir, (loc[0] - x0) * ech, (loc[1] - y0) * ech)
    print(f"  → hypothèse retenue : {meilleur[1]} (corrélation "
          f"{meilleur[0]:+.3f}, décalage {meilleur[3]:+d}, {meilleur[4]:+d} px)")
    if meilleur[0] < 0.5:
        print("  ⚠ corrélation faible : les deux images NE montrent PAS le même "
              "champ (ou l'une est recadrée) — les mesures de bruit restent "
              "valables zone par zone, pas au pixel près")
else:
    print("\n  tailles différentes : pas de comparaison pixel à pixel")

# --- REDRESSEMENT (ce que l'application DEVRAIT faire : cf. auto_unflip) ----
redresse = bool(alignes and meilleur is not None and meilleur[0] >= 0.5
                and meilleur[2] in (1, 3))
if redresse:
    b = np.ascontiguousarray(b[::-1])
    imgs[1] = b
    print("\n  → le fichier EXTERNE est en MIROIR VERTICAL : il est redressé "
          "pour la suite,\n    afin de comparer exactement le MÊME ciel "
          "(défaut d'auto_unflip corrigé en v2.38.2 : les fichiers écrits AVANT "
          "sont à l'envers).")

print()
print("=" * 78)
print("[1] fond et grain par canal (méthode _diag_empilement_couleur.py)")
print("=" * 78)
for (titre, _), img in zip(FICHIERS, imgs):
    z = np.asarray(img, np.float32)
    h, w = z.shape[:2]
    q = z[h // 4:3 * h // 4:2, w // 4:3 * w // 4:2]
    fond = [float(np.median(q[..., c])) for c in range(3)]
    bruit = [mad(q[..., c]) for c in range(3)]
    print(f"\n  {titre}")
    print("    fond       : " + " | ".join(f"{n} {v:.5f}"
                                          for n, v in zip("RGB", fond)))
    print(f"    → équilibre du fond   R/G = {fond[0] / fond[1]:.4f}   "
          f"B/G = {fond[2] / fond[1]:.4f}   (neutre = 1,0000)")
    print("    grain (MAD): " + " | ".join(f"{n} {v:.6f}"
                                          for n, v in zip("RGB", bruit)))
    print(f"    → équilibre du grain  R/G = {bruit[0] / bruit[1]:.3f}   "
          f"B/G = {bruit[2] / bruit[1]:.3f}   (1,00 = grain gris ; "
          f">1 en B = grain BLEU)")

print()
print("=" * 78)
print("[2] grain CHROMATIQUE sur un fond COMMUN aux deux fichiers")
print("=" * 78)
if alignes:
    h, w = a.shape[:2]
    total = (h // BLOC) * (w // BLOC)
    n = max(20, int(0.15 * total))
    commun = sorted(set(zones_lisses(a, n)) & set(zones_lisses(b, n)))
    print(f"    blocs {BLOC}×{BLOC} les plus lisses : {n} demandés par fichier → "
          f"{len(commun)} communs sur {total} blocs")
    masque = np.zeros((h, w), bool)
    for (y, x) in commun:
        masque[y:y + BLOC, x:x + BLOC] = True
    res = {}
    for (titre, _), img in zip(FICHIERS, imgs):
        z = np.asarray(img, np.float32)
        # passe-haut : on retire les variations LARGES (objets, gradients) et on
        # ne garde que le GRAIN, comme le fait le diag jalon 67.
        def hp(plan):
            return plan - cv2.GaussianBlur(plan, (0, 0), sigmaX=2.0)
        rg = hp(z[..., 0] - z[..., 1])[masque]
        bg = hp(z[..., 2] - z[..., 1])[masque]
        lum = hp(z.mean(axis=2))[masque]
        # TACHES de couleur à l'échelle 2-8 px (ce que fabrique un traitement
        # IA : nettoyage fin + résidus en « plaque ») — c'est l'échelle que
        # l'œil lit comme du « bruit coloré » bien plus que le grain 1 px.
        d = z[..., 2] - z[..., 1]
        bp = (cv2.GaussianBlur(d, (0, 0), sigmaX=6.0)
              - cv2.GaussianBlur(d, (0, 0), sigmaX=1.5))[masque]
        niveau = float(np.median(z[..., 1][masque]))
        dev = np.abs(bg - np.median(bg))          # excursions du bleu
        res[titre] = dict(rg_s=float(rg.std()), rg_m=mad(rg),
                          bg_s=float(bg.std()), bg_m=mad(bg),
                          bp_m=mad(bp), lum_m=mad(lum), niveau=niveau,
                          dev=np.asarray(dev, np.float32))
        print(f"\n  {titre}")
        print(f"    R−G : σ {res[titre]['rg_s']:.6f} · MAD {res[titre]['rg_m']:.6f}")
        print(f"    B−G : σ {res[titre]['bg_s']:.6f} · MAD {res[titre]['bg_m']:.6f}"
              f"   ← le « bruit bleu » (grain 1 px)")
        print(f"    B−G échelle 2-8 px (taches) : MAD {res[titre]['bp_m']:.6f}"
              f"   · σ/MAD = {res[titre]['bg_s'] / res[titre]['bg_m']:.2f} "
              f"(>2 = bruit « en plaques », pas du grain)")
        print(f"    luminance (contrôle) : MAD {res[titre]['lum_m']:.6f} · "
              f"niveau du fond (G) {niveau:.5f}")
        print(f"    part COLORÉE du grain : B−G / luminance = "
              f"{res[titre]['bg_m'] / res[titre]['lum_m']:.4f} · "
              f"R−G / luminance = {res[titre]['rg_m'] / res[titre]['lum_m']:.4f}")
        print(f"    B−G rapporté au fond  : "
              f"{res[titre]['bg_m'] / niveau:.5f}")

print()
print("=" * 78)
print("[3] VERDICT")
print("=" * 78)
if alignes:
    k = [t for t, _ in FICHIERS]
    s, e = res[k[0]], res[k[1]]
    print(f"    B−G (absolu)  : stack {s['bg_m']:.6f} → externe "
          f"{e['bg_m']:.6f}   ×{e['bg_m'] / s['bg_m']:.3f}")
    print(f"    R−G (absolu)  : stack {s['rg_m']:.6f} → externe "
          f"{e['rg_m']:.6f}   ×{e['rg_m'] / s['rg_m']:.3f}")
    print(f"    luminance     : stack {s['lum_m']:.6f} → externe "
          f"{e['lum_m']:.6f}   ×{e['lum_m'] / s['lum_m']:.3f}")
    print(f"    part colorée B−G : stack "
          f"{s['bg_m'] / s['lum_m']:.4f} → externe {e['bg_m'] / e['lum_m']:.4f} "
          f"×{(e['bg_m'] / e['lum_m']) / (s['bg_m'] / s['lum_m']):.3f}")
    ra = float(np.median(a[..., 2][masque])) / float(np.median(a[..., 1][masque]))
    rb = float(np.median(b[..., 2][masque])) / float(np.median(b[..., 1][masque]))
    print(f"    fond B/G      : stack {ra:.4f} → externe {rb:.4f}")
    print(f"    fond G (niveau): stack {s['niveau']:.5f} → externe "
          f"{e['niveau']:.5f}   ×{e['niveau'] / s['niveau']:.3f}")
    print(f"    taches 2-8 px : stack {s['bp_m']:.6f} → externe "
          f"{e['bp_m']:.6f}   ×{e['bp_m'] / s['bp_m']:.3f}")
    # Excursions fortes, mesurées avec le MÊME seuil pour les deux (le grain du
    # stack) : ce que l'œil repère comme « du bruit bleu » quand le grain
    # moyen, lui, est propre.
    seuil = 4.0 * s['bg_m']
    for nom, r_ in ((k[0], s), (k[1], e)):
        part = 100.0 * float((r_['dev'] > seuil).mean())
        print(f"    excursions |B−G| > 4×grain(stack) : {part:6.3f} % "
              f"des pixels de ciel   [{nom}]")
