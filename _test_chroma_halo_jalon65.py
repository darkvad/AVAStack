# -*- coding: utf-8 -*-
"""Banc v2.37.3 — LE HALO DE COULEUR DES ÉTOILES (réduction de bruit chromatique).

CONSTAT D'ALAIN (26/09/2026) : « Les étoiles brillantes rouges et bleues ont un
halo gênant », VISIBLE AUSSI dans le fichier passé par BlurXTerminator (« en
général, c'est un halo killer pourtant »). Mesuré sur son empilement M31 réel
(anneau r = 3..9 px, en multiples du niveau de ciel local) : la réduction de
bruit chromatique d'alors faisait passer le halo de son étoile bleue de R/B 1,30
(référence) à 0,44 — un HALO BLEU créé là où il n'y en avait aucun — pendant que
la LUMINANCE ne bougeait pas (±6 % : c'est un halo de COULEUR). Cause : un écart
de chroma (Cr/Cb) ne dépend pas de la luminosité du pixel, donc le flou
mélangeait la couleur du CŒUR de l'étoile avec celle du CIEL et la déposait sur
les AILES faibles, où un minuscule écart devient une énorme couleur.

Vérifie :
  [1] le contrat de base (no-op, entrée jamais modifiée) — les cas fins sont déjà
      couverts par `_test_chroma_nr_jalon63.py`, ils ne sont pas redoublés ;
  [2] L'ANTI-RÉGRESSION DU HALO : sur une étoile brillante à AILES LARGES
      (profil de Moffat — une gaussienne n'a pas d'ailes et ne reproduit PAS
      l'artefact) posée sur un ciel TEINTÉ (bleu, comme le sien), la couleur du
      halo ne doit pas bouger. TÉMOIN : la formule d'AVANT la v2.37.3 (chroma
      absolue) est RÉ-ÉCRITE ICI exprès — le banc doit montrer qu'elle dévie,
      elle, de plusieurs dizaines de pour cent : sans témoin, ce banc ne
      prouverait pas qu'il sait discriminer (leçon du projet : confronter toute
      implémentation à une référence indépendante) ;
  [3] le bénéfice d'origine est CONSERVÉ : le grain coloré du fond tombe toujours
      (et exactement de (1 − force) sur un ciel NEUTRE — le fond que la
      neutralisation laisse, cf. jalon 62) ;
  [4] la LUMINANCE (canal Y) reste intacte ;
  [5] LE RAYON SUIT LA RÉSOLUTION : une image réduite de moitié, lissée avec le
      rayon ramené (1,5 px), donne le MÊME halo que l'image pleine résolution
      avec le rayon de référence (3 px) — alors que le rayon NON ramené (3 px sur
      l'image réduite) dévie : c'était le halo 2,4× trop large de sa visu ;
  [6] transport : le rayon voyage dans le job du solveur VeraLux, entre dans la
      clé des réglages, et l'interface le pose d'après l'échelle de l'aperçu ;
  [7] sur un FICHIER RÉEL (optionnel) :
      `python _test_chroma_halo_jalon65.py <fichier>` mesure le halo de la plus
      brillante étoile avant/après.

Exécution : python _test_chroma_halo_jalon65.py
"""
import sys

import cv2
import numpy as np
cv2.ocl.setUseOpenCL(False)          # parade du projet : crash OpenCV 5/OpenCL au
                                     # teardown quand on enchaîne les bancs Tk

from avastack.processing import couleurs as C                      # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok = ok and bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


# --------------------------------------------------- témoin : la formule d'avant
def chroma_absolue(img, force=0.9, rayon=3.0):
    """La réduction de bruit chromatique d'AVANT la v2.37.3 (chroma ABSOLUE) —
    gardée ici comme TÉMOIN, jamais utilisée par l'appli. C'est elle qui
    fabriquait le halo : le banc doit le montrer."""
    a = np.asarray(img, dtype=np.float32)
    f = np.float32(min(1.0, max(0.0, float(force))))
    ycc = cv2.cvtColor(a, cv2.COLOR_RGB2YCrCb)
    for i in (1, 2):
        c = ycc[..., i]
        lisse = cv2.GaussianBlur(c, (0, 0), sigmaX=float(rayon))
        ycc[..., i] = c + f * (lisse - c)
    return np.maximum(cv2.cvtColor(ycc, cv2.COLOR_YCrCb2RGB),
                      np.float32(0.0)).astype(np.float32)


# ------------------------------------------------------------------ la scène
# Ciel TEINTÉ comme le sien (B > G > R) et étoiles de Moffat : des AILES larges,
# comme une vraie PSF. Chaque étoile est fortement exposée (toutes les couches
# saturent au cœur, la couleur n'apparaît qu'autour) — la configuration réelle.
N = 600
yy, xx = np.mgrid[0:N, 0:N].astype(np.float64)
RNG = np.random.default_rng(20260926)
CIEL = (0.00120, 0.00140, 0.00170)      # R, G, B — ciel bleuté
CIEL_NEUTRE = (0.00140, 0.00140, 0.00140)
GRAIN = 0.0004
ROUGE = (1.00, 0.72, 0.42)
BLEUE = (0.42, 0.70, 1.00)
PALE = (0.85, 0.90, 1.00)               # étoile FAIBLE : son halo ne vaut que
                                        # quelques fois le ciel, donc la teinte du
                                        # ciel y pèse lourd — la configuration la
                                        # plus sensible (celle de son étoile bleue)


def moffat(cx, cy, fwhm, amp, beta=2.5):
    alpha = fwhm / (2.0 * np.sqrt(2.0 ** (1.0 / beta) - 1.0))
    r2 = (xx - cx) ** 2 + (yy - cy) ** 2
    return amp / (1.0 + r2 / alpha ** 2) ** beta


def scene(ciel=CIEL, grain=GRAIN, etoiles=True, cote=N):
    """Scène paramétrable : `cote` permet de la fabriquer à une autre échelle
    (les rayons et positions sont exprimés en pixels de la scène N×N)."""
    k = cote / float(N)
    s = (np.array(ciel, np.float32).reshape(1, 1, 3)
         * np.ones((cote, cote, 1), np.float32))
    if etoiles:
        for (cx, cy), coul, amp in (((200, 200), ROUGE, 2.6),
                                    ((420, 380), BLEUE, 2.6),
                                    ((300, 480), PALE, 0.10)):
            s += (moffat(cx * k, cy * k, 3.0 * k, amp)[..., None]
                  * np.array(coul, np.float32).reshape(1, 1, 3)).astype(np.float32)
    s += RNG.normal(0.0, grain, s.shape).astype(np.float32)
    return np.clip(s, 0.0, 1.0).astype(np.float32)


IMAGE = scene()
# (libellé, position, étoile BRILLANTE ?) — la discrimination du banc se juge sur
# les brillantes : c'est là que le halo de couleur se voyait (constat d'Alain) ;
# l'étoile faible n'y sert que de garde-fou « aucun dégât » (son halo ne vaut que
# quelques fois le ciel, la structure de couleur y est trop douce pour que le
# flou la change beaucoup — même la formule d'avant y déviait peu).
ETOILES = (("ROUGE brillante", (200, 200), True),
           ("BLEUE brillante", (420, 380), True),
           ("PÂLE faible", (300, 480), False))
FORCE = 0.9


def couronne(img, pt, r0=3, r1=9, ref=(16, 24)):
    """Éclat PAR COULEUR de la couronne r = r0..r1 (moyenne des anneaux, fond
    local retranché) en MULTIPLES du niveau de ciel — la mesure du halo."""
    cx, cy = pt
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    sky = np.array([np.median(img[(d >= ref[0]) & (d <= ref[1]), c])
                    for c in range(3)], dtype=np.float64)
    out = []
    for c in range(3):
        v = [float(np.mean(img[(d >= r - 0.5) & (d < r + 0.5), c]))
             for r in range(r0, r1 + 1)]
        out.append((float(np.mean(v)) - sky[c]) / max(float(sky[c]), 1e-12))
    return np.array(out)


def grain_colore(img, zone=(slice(30, 150), slice(450, 570))):
    """σ haute fréquence des ÉCARTS de couleur (R−G, B−G) : le grain COLORÉ."""
    z = np.asarray(img, np.float32)[zone]
    hf = z - cv2.GaussianBlur(z, (0, 0), sigmaX=2.0)
    return (float((hf[..., 0] - hf[..., 1]).std()),
            float((hf[..., 2] - hf[..., 1]).std()))


# ============================================== [1] contrat de base (rappel)
print("[1] contrat : no-op et entrée jamais modifiée")
mono = np.full((24, 24), 0.02, np.float32)
verifie(np.array_equal(C.reduire_bruit_chroma(mono), mono), "mono : inchangé")
avant = IMAGE.copy()
verifie(np.array_equal(C.reduire_bruit_chroma(IMAGE, force=0.0), IMAGE),
        "force 0 : no-op strict")
C.reduire_bruit_chroma(IMAGE)
verifie(np.array_equal(IMAGE, avant), "l'image d'origine n'est JAMAIS modifiée")

# =============================== [2] LE HALO : la couleur des étoiles ne bouge pas
print("[2] ANTI-RÉGRESSION DU HALO : la couleur autour des étoiles est préservée")
fixe = C.reduire_bruit_chroma(IMAGE, force=FORCE)              # v2.37.3
temoin = chroma_absolue(IMAGE, force=FORCE)                    # avant v2.37.3
for nom, pt, brillante in ETOILES:
    r0 = couronne(IMAGE, pt)
    r1 = couronne(fixe, pt)
    rt = couronne(temoin, pt)
    print(f"    {nom} : couronne r=3..9 en multiples du ciel — référence "
          f"R {r0[0]:.2f} V {r0[1]:.2f} B {r0[2]:.2f}")
    print(f"         spécifique R {r1[0]:.2f} V {r1[1]:.2f} B {r1[2]:.2f} · "
          f"témoin (avant v2.37.3) R {rt[0]:.2f} V {rt[1]:.2f} B {rt[2]:.2f}")
    ecart = np.abs(r1 - r0) / np.maximum(r0, 1e-12)
    ecart_t = np.abs(rt - r0) / np.maximum(r0, 1e-12)
    print(f"         écart max par canal : spécifique {100 * ecart.max():.1f} % "
          f"· témoin {100 * ecart_t.max():.1f} %")
    verifie(float(ecart.max()) < 0.10,
            f"{nom} : éclat du halo par canal inchangé à "
            f"{100 * ecart.max():.1f} % près (< 10 %)")
    # La COULEUR du halo (rapport R/B de la couronne) : ce que l'œil voit.
    ref_rb = r0[0] / max(r0[2], 1e-12)
    fix_rb = r1[0] / max(r1[2], 1e-12)
    tem_rb = rt[0] / max(rt[2], 1e-12)
    ecart_rb = abs(fix_rb - ref_rb) / ref_rb
    ecart_rb_t = abs(tem_rb - ref_rb) / ref_rb
    print(f"         couleur du halo R/B : référence {ref_rb:.2f} → spécifique "
          f"{fix_rb:.2f} · témoin {tem_rb:.2f}")
    verifie(ecart_rb < 0.10,
            f"{nom} : couleur du halo R/B conservée "
            f"({100 * ecart_rb:.1f} % d'écart, < 10 %)")
    if brillante:
        # LE TÉMOIN DOIT DÉVIER : sans ça, le banc ne prouverait pas qu'il sait
        # discerner la régression qu'Alain a vue (mesuré sur son fichier : la
        # couleur du halo de son étoile bleue passait de 1,30 à 0,44 en R/B).
        verifie(ecart_rb_t > 0.10,
                f"{nom} : le TÉMOIN (formule d'avant) dévie de "
                f"{100 * ecart_rb_t:.0f} % sur R/B — le banc DISCRIMINE bien "
                f"(il aurait attrapé la régression)")


def chroma_hf(img, zone=(slice(30, 150), slice(450, 570))):
    """σ haute fréquence des écarts de couleur — LE grain chromatique (même
    mesure que `_test_chroma_nr_jalon63.py`)."""
    z = np.asarray(img, np.float32)[zone]
    hf = z - cv2.GaussianBlur(z, (0, 0), sigmaX=2.0)
    return (float((hf[..., 0] - hf[..., 1]).std()),
            float((hf[..., 2] - hf[..., 1]).std()))


# ============ [3] le bénéfice d'origine : le grain coloré du FOND tombe toujours
print("[3] le grain coloré du fond tombe (le bénéfice d'origine est conservé)")
# Ciel NEUTRE : le fond que laisse la neutralisation de la couleur du fond
# (case 7, cochée par défaut) — c'est la configuration réelle d'usage.
NEUTRE = scene(ciel=CIEL_NEUTRE)
ch0 = chroma_hf(NEUTRE)
print(f"    grain chromatique de départ (ciel neutre) : R−G {ch0[0]:.6f} · "
      f"B−G {ch0[1]:.6f}")
for force in (0.25, 0.5, 1.0):
    ch = chroma_hf(C.reduire_bruit_chroma(NEUTRE, force=force, rayon=3.0))
    ratio = max(ch) / max(ch0)
    verifie(abs(ratio - (1.0 - force)) < 0.06,
            f"force {force} : grain coloré ×{ratio:.3f} (attendu "
            f"×{1.0 - force:.2f} — la part demandée est retirée)")
# Ciel TEINTÉ (celui de l'empilement BRUT, avant neutralisation) : la teinte du
# fond ajoute une petite fuite du bruit de luminance (mesurée : ×0,17 au lieu de
# ×0,10 pour l'ancienne formulation). L'essentiel du bénéfice doit rester.
ch_t = chroma_hf(IMAGE)
ch_n = chroma_hf(fixe)
ratio_t = max(ch_n) / max(ch_t)
print(f"    ciel TEINTÉ (fond brut) : grain coloré ×{ratio_t:.3f} "
      f"à force {FORCE} (attendu ×{1.0 - FORCE:.2f})")
verifie(ratio_t < 0.40,
        f"ciel teinté : il ne reste que {100 * ratio_t:.0f} % du grain coloré "
        f"(< 40 % — l'essentiel du bénéfice est conservé)")

# ================================ [4] la LUMINANCE (canal Y) reste intacte
print("[4] la luminance (canal Y de YCrCb) n'est pas touchée")
y0 = cv2.cvtColor(IMAGE, cv2.COLOR_RGB2YCrCb)[..., 0]
dy = np.abs(cv2.cvtColor(fixe, cv2.COLOR_RGB2YCrCb)[..., 0] - y0)
verifie(float(dy[(slice(30, 150), slice(450, 570))].max()) < 2e-6,
        f"luminance du FOND inchangée (écart max {float(dy[(slice(30, 150), slice(450, 570))].max()):.2e})")
verifie(float(dy.max()) < 2e-5,
        f"luminance inchangée PARTOUT à {float(dy.max()):.2e} près (la seule "
        f"queue vient des cœurs saturés au bord de l'échelle)")

# ============== [5] le rayon SUIT la résolution (fidélité aperçu ⇄ fichier)
print("[5] le rayon suit la résolution : l'aperçu montre ce que le fichier contient")
PETIT = cv2.resize(IMAGE, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
r_apercu = C.rayon_chroma_apercu(0.5)
print(f"    rayon de référence {C.RAYON_CHROMA_DEFAUT:.1f} px → image ×0,5 : "
      f"{r_apercu:.2f} px (plancher {C.RAYON_CHROMA_MIN})")
verifie(abs(r_apercu - 1.5) < 1e-9, "×0,5 : rayon ramené à 1,50 px")
verifie(C.rayon_chroma_apercu(1.0) == C.RAYON_CHROMA_DEFAUT,
        "×1,0 (pleine résolution) : rayon de référence inchangé")
verifie(C.rayon_chroma_apercu(0.02) == C.RAYON_CHROMA_MIN,
        "facteur extrême : rayon borné au plancher (jamais < "
        f"{C.RAYON_CHROMA_MIN} px)")
verifie(C.rayon_chroma_apercu(None) == C.RAYON_CHROMA_DEFAUT
        and C.rayon_chroma_apercu("x") == C.RAYON_CHROMA_DEFAUT,
        "facteur illisible : rayon de référence (aucune exception)")
suivi = np.asarray(cv2.resize(
    C.reduire_bruit_chroma(PETIT, force=FORCE, rayon=r_apercu), (N, N),
    interpolation=cv2.INTER_LINEAR), np.float32)
fige = np.asarray(cv2.resize(
    C.reduire_bruit_chroma(PETIT, force=FORCE, rayon=C.RAYON_CHROMA_DEFAUT),
    (N, N), interpolation=cv2.INTER_LINEAR), np.float32)
# PLANCHER DE MESURE : la même image réduite SANS aucune réduction de bruit
# chromatique, comparée à la pleine résolution — le double redimensionnement
# (INTER_AREA puis INTER_LINEAR) déforme déjà un peu le profil de couleur. Toute
# comparaison aperçu/fichier doit se lire PAR RAPPORT à ce plancher, sinon on
# attribue au rayon une erreur qui vient de la mesure elle-même (leçon du projet :
# un chiffre sans sa méthode de mesure est inexploitable).
plancher = np.asarray(cv2.resize(PETIT, (N, N),
                                 interpolation=cv2.INTER_LINEAR), np.float32)
FACTEUR = 4.0            # au-delà de 4× le plancher, c'est l'échelle du rayon
for nom, pt, brillante in ETOILES:
    ref = couronne(IMAGE, pt)                # pleine résolution, SANS traitement
    rb_ref = ref[0] / max(ref[2], 1e-12)
    p = couronne(plancher, pt)
    rb_plancher = p[0] / max(p[2], 1e-12)
    pl = abs(rb_plancher - rb_ref) / rb_ref
    a, b = couronne(suivi, pt), couronne(fige, pt)
    ecart_s = abs(a[0] / max(a[2], 1e-12) - rb_ref) / rb_ref
    ecart_f = abs(b[0] / max(b[2], 1e-12) - rb_ref) / rb_ref
    # Seuil = 4× le plancher, mais JAMAIS plus serré que 5 % : sur une étoile
    # faible le plancher tombe à 0,3 % (rien ne bouge, quel que soit le rayon) et
    # un critère purement relatif n'y a plus de sens.
    seuil = max(FACTEUR * pl, 0.05)
    print(f"    {nom} : couleur du halo R/B — pleine résolution {rb_ref:.2f} · "
          f"plancher de mesure {100 * pl:.1f} % · rayon suivi {100 * ecart_s:.1f} % "
          f"({ecart_s / max(pl, 1e-9):.1f}× le plancher, seuil {100 * seuil:.1f} %) · "
          f"rayon NON suivi {100 * ecart_f:.1f} %")
    verifie(ecart_s < seuil,
            f"{nom} : l'image réduite avec le rayon ramené reste sous le seuil — "
            f"l'aperçu montre bien ce que le fichier contient")
    if brillante:
        verifie(ecart_f > seuil,
                f"{nom} : le rayon NON ramené dépasse, lui, "
                f"{ecart_f / max(pl, 1e-9):.0f}× le plancher ({100 * ecart_f:.0f} %) "
                f"— c'était le halo trop large de la visu")

# ================== [6] transport : le rayon voyage jusqu'au solveur VeraLux
print("[6] transport : le rayon entre dans le job du solveur et y est appliqué")
import inspect                                                    # noqa: E402
import time                                                       # noqa: E402
import tkinter as tk                                              # noqa: E402
import avastack.ui.app as ui                                      # noqa: E402
from avastack.processing import veralux as V                      # noqa: E402

root = tk.Tk()
root.withdraw()
ui.CONFIG = {}
ui.sauver_config = lambda d: None
app = ui.App(root)
d = app.disp
verifie(hasattr(d, "vl_chroma_rayon")
        and abs(float(d.vl_chroma_rayon) - C.RAYON_CHROMA_DEFAUT) < 1e-9,
        "le solveur démarre avec le rayon de RÉFÉRENCE pleine résolution")
cle_avant = d._vl_params()
d.vl_chroma_rayon = C.rayon_chroma_apercu(0.417)
verifie(d._vl_params() != cle_avant,
        "le rayon entre dans la CLÉ des réglages (→ une re-résolution)")
verifie(inspect.getsource(ui.App).count("rayon_chroma_apercu") >= 2,
        "l'interface le ramène à l'échelle de l'aperçu dans ses DEUX chemins "
        "(boucle d'acquisition ET _pousser_rendu)")

petite = IMAGE[0:192, 0:192].astype(np.float32)     # cadrage de CIEL


def _attendre(predicat, delai=60.0):
    t0 = time.time()
    while time.time() - t0 < delai:
        if predicat():
            return True
        time.sleep(0.2)
    return False


def _resultat():
    if not _attendre(lambda: not d._vl_pending and d._vl_result is not None
                     and d._vl_result[0] == d._vl_params()):
        return None
    return np.asarray(d._vl_result[1], np.float32)


params = dict(mode=d.vl_mode_res, target_bg=d.vl_target_bg,
              log_d=d.vl_log_d, profil=d.vl_profil)
app.var_view.set("pile")
app.var_vl_neutre.set(False)
app._on_vl_neutre()
app.var_vl_chroma.set(True)
app.var_vl_chroma_force.set(0.5)
app.last_show = petite
app._on_vl_chroma()
d.vl_chroma_rayon = 1.25                            # ce que pose l'interface
d.reset()
d.notify_new_stack()
d._process_veralux(petite, live=False)
a1 = _resultat()
attendu = np.asarray(V.etirer(C.reduire_bruit_chroma(petite, force=0.5,
                                                     rayon=1.25), **params)[0],
                     np.float32)
ecart = float(np.abs(a1 - attendu).max()) if a1 is not None else 1.0
verifie(a1 is not None and ecart < 1e-6,
        f"le solveur applique le RAYON DU JOB (1,25 px) — écart max {ecart:.2e} "
        f"avec un appel direct au même rayon")
d.vl_chroma_rayon = C.RAYON_CHROMA_DEFAUT
d.reset()
d.notify_new_stack()
d._process_veralux(petite, live=False)
a2 = _resultat()
attendu2 = np.asarray(V.etirer(C.reduire_bruit_chroma(petite, force=0.5),
                               **params)[0], np.float32)
ecart2 = float(np.abs(a2 - attendu2).max()) if a2 is not None else 1.0
diff = float(np.abs(a2 - a1).max()) if (a2 is not None and a1 is not None) else 0.0
verifie(a2 is not None and ecart2 < 1e-6,
        f"…et le rayon de référence (3 px) donne bien un AUTRE rendu — écart "
        f"max {ecart2:.2e} avec un appel direct, {diff:.2e} entre les deux rayons")
root.destroy()

# ============ [7] SUR UN FICHIER RÉEL (optionnel) : son halo, avant / après
if len(sys.argv) > 1:
    import os                                                     # noqa: E402
    from avastack.images import load_image                        # noqa: E402
    from avastack.processing import veralux as V2                 # noqa: E402
    print(f"[7] mesure sur un fichier RÉEL : {os.path.basename(sys.argv[1])}")
    reel = np.asarray(load_image(sys.argv[1]), np.float32)
    if reel.ndim != 3 or reel.shape[-1] != 3:
        print("    (fichier monochrome : aucun halo de couleur à mesurer)")
    else:
        # MÉTRIQUE QUI DÉCIDE : l'écart RENDU (après étirement VeraLux, même
        # logD) dans la couronne r = 3..9 px, en POINTS de % du pic vert — c'est
        # ce que l'œil voit. Le fond est d'abord neutralisé (case 7, cochée par
        # défaut : c'est l'ordre réel de la chaîne).
        cote = int(min(700, reel.shape[0], reel.shape[1]))
        zone = np.ascontiguousarray(C.neutraliser_fond(reel[-cote:, -cote:]))
        gh, gw = zone.shape[:2]
        gy, gx = np.mgrid[0:gh, 0:gw].astype(np.float64)
        profil = [q for q in V2.profils_disponibles() if q.startswith("Sony IMX585")]
        profil = profil[0] if profil else V2.PROFIL_PAR_DEFAUT

        def _rendu(img):
            return V2.etirer(img, mode=V2.MODE_LOG_D, log_d=logd,
                             profil=profil)[0]

        _, logd, _ = V2.etirer(zone, mode=V2.MODE_TARGET_BG, target_bg=0.11,
                               profil=profil)
        rendus = {"sans": _rendu(zone),
                  "v2.37.3": _rendu(C.reduire_bruit_chroma(zone, force=FORCE)),
                  "témoin": _rendu(chroma_absolue(zone, force=FORCE))}
        lumz = 0.299 * zone[..., 0] + 0.587 * zone[..., 1] + 0.114 * zone[..., 2]
        mxl = cv2.dilate(lumz, np.ones((7, 7), np.uint8))
        ys, xs = np.nonzero((lumz >= mxl) & (lumz > np.percentile(lumz, 99.3)))
        etoiles = []
        for i in np.argsort(lumz[ys, xs])[::-1]:
            p = (int(xs[i]), int(ys[i]))
            if min(p[0], p[1], gw - 1 - p[0], gh - 1 - p[1]) < 45:
                continue
            if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= 60 * 60
                   for q in etoiles):
                etoiles.append(p)
            if len(etoiles) >= 6:
                break

        def _couronne(img, pt, r0=3, r1=9, ref=(16, 24)):
            x, y = pt
            d = np.sqrt((gx - x) ** 2 + (gy - y) ** 2)
            sky = np.array([np.median(img[(d >= ref[0]) & (d <= ref[1]), c])
                            for c in range(3)])
            return np.array([np.mean([100.0 * (np.median(img[(d >= r - 0.5)
                                                            & (d < r + 0.5), c])
                                              - sky[c])
                                      for r in range(r0, r1 + 1)])
                             for c in range(3)])

        pires = {"v2.37.3": 0.0, "témoin": 0.0}
        for pt in etoiles:
            ref = _couronne(rendus["sans"], pt)
            ec = {k: float(np.abs(_couronne(v, pt) - ref).max())
                  for k, v in rendus.items() if k != "sans"}
            print(f"    étoile {str(pt):<12} référence R {ref[0]:6.1f} V {ref[1]:6.1f} "
                  f"B {ref[2]:6.1f} · écart rendu : v2.37.3 {ec['v2.37.3']:5.2f} pt · "
                  f"témoin {ec['témoin']:5.2f} pt")
            pires["v2.37.3"] = max(pires["v2.37.3"], ec["v2.37.3"])
            pires["témoin"] = max(pires["témoin"], ec["témoin"])
        if etoiles:
            print(f"    pire écart sur {len(etoiles)} étoiles : v2.37.3 "
                  f"{pires['v2.37.3']:.2f} pt · témoin {pires['témoin']:.2f} pt")
            verifie(pires["v2.37.3"] < 5.0,
                    f"sur son fichier, la réduction de bruit chromatique ne "
                    f"déplace le RENDU de son halo que de "
                    f"{pires['v2.37.3']:.2f} point (< 5 — invisible)")
            verifie(pires["témoin"] > 3.0 * pires["v2.37.3"],
                    f"la formule d'avant déplaçait, elle, jusqu'à "
                    f"{pires['témoin']:.1f} points — le banc DISCRIMINE")
        else:
            print("    (aucune étoile isolée trouvée dans la zone mesurée)")

print()
print("RÉSULTAT :", "TOUT PASSE" if ok else "ÉCHECS PRÉSENTS")
raise SystemExit(0 if ok else 1)
