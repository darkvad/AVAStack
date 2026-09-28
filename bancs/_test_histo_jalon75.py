# -*- coding: utf-8 -*-
"""Banc du jalon 75 : HISTOGRAMME À DEUX BANDES ET BARRES DE NIVEAUX.

Demande d'Alain (28/09/2026) : « trois barres de réglage de l'histogramme, un
peu comme le GRAND histogramme de SharpCap… il faut réfléchir à l'étirement
existant VeraLux ou STF qui va (ou pas) se refaire à la frame suivante ».
Décisions prises avec lui, dans cet ordre :
  ① les barres agissent sur la SORTIE DU MOTEUR (modèle du MINI-histogramme
     SharpCap : « the stretch in the mini histogram affects the display
     only »), seule forme compatible avec LES DEUX moteurs — VeraLux n'a ni
     point noir ni point blanc (ancre + logD) ;
  ② elles s'appliquent EN DELTA, à chaque frame, par-dessus l'étirement
     automatique qui continue de s'ajuster ;
  ③ un bouton ⏹/▶ gèle l'auto du MOTEUR (STF : stats ; VeraLux : logD
     verrouillé, mécanisme du jalon 3) — utile DANS LES DEUX MOTEURS ;
  ④ l'histogramme porte DEUX bandes (brut linéaire + sortie du moteur), avec
     un sélecteur ; ⑤ saturation par couleur R/V/B dans la partie Saturation.

Vérifie :
  [1] l'étage de niveaux est l'IDENTITÉ AU BIT à 0 / 0,5 / 1 (aucune
      régression possible : le court-circuit évite même le calcul) ;
  [2] la propriété qui fait le sens du geste : MTF(m, m) = 0,5 (la position de
      la barre médian EST le niveau affiché en gris moyen), et les points
      noir/blanc coupent et saturent au bon endroit ;
  [3] PARITÉ ÉCRAN / FICHIER au bit (« Enregistrer tel que vu » = l'écran),
      avec barres + gamma + saturation globale + saturation par couleur, Y
      COMPRIS étirement gelé (le fichier doit utiliser les MÊMES stats gelées) ;
  [4] le mode manuel (auto décoché) est INCHANGÉ (pas de médian ajouté là) ;
  [5] gel / reprise : en gel, deux images différentes donnent les MÊMES
      paramètres ; après reprise, les paramètres suivent de nouveau l'image ;
  [6] saturation par couleur : 1,0 = identité, le gris (c = Y) ne bouge pas,
      un gain double bien l'écart par canal, et c'est un no-op en mono ;
  [7] les deux bandes : coût INDÉPENDANT de la résolution, et normalisation
      COMMUNE des trois courbes (l'ancienne normalisation par canal rendait une
      dominante de couleur invisible) ;
  [8] géométrie : positions des barres = paramètres, aller-retour de l'axe,
      prise à ±7 px, glissement simulé, ordre des barres respecté, étiquettes
      contenues dans le Canvas et sans chevauchement, et LE TRACÉ SUIT LE GESTE
      sans aucune frame (défaut réel du 28/09/2026 : « l'image change mais la
      barre ne bouge pas, comme si le bas n'était pas rafraîchi ») — sans
      recalculer l'histogramme, et assez vite pour suivre chaque pixel ;
  [9] UI réelle : état initial, sélecteur, ⏹/▶ en STF ET en VeraLux, champs
      resynchronisés, nouvelle session = barres remises à l'auto ;
  [10] la chaîne LINÉAIRE n'est pas contaminée (les barres ne touchent pas les
      corrections de l'empilement).
  [11] l'ÉCHELLE Y de la bande basse (log ↔ linéaire, décision d'Alain du
       28/09/2026) : en linéaire les hauteurs sont PROPORTIONNELLES aux comptes
       (un vrai PIC au lieu de la colline), la bande HAUTE n'est pas touchée
       (mesuré : en linéaire elle ne montrerait plus que 10 bacs sur 256),
       aucun recalcul, l'échelle est DITE dans la ligne d'état, la case est
       persistée, et le retour au log redonne le tracé d'origine AU BIT ;

Exécution : python bancs/_test_histo_jalon75.py   (nécessite un affichage)
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent désormais dans bancs/ (ou bancs/cameras/) et non plus à côté de
# l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys
import time
import tkinter as tk

import numpy as np

import avastack.ui.app as ui
from avastack.processing import veralux as veralux_moteur
from avastack.processing.display import (DisplayProcessor, mtf, niveaux,
                                         niveaux_actifs, saturation_actifs,
                                         saturation_canaux)

if hasattr(sys.stdout, "reconfigure"):   # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


def image_factice(h=400, w=600, rgb=True, mono=False, seed=0):
    """Ciel factice : fond + nébulosité + étoiles + bruit (linéaire [0..1])."""
    rng = np.random.default_rng(seed)
    n = 1 if mono else (3 if rgb else 1)
    shape = (h, w, n) if n > 1 else (h, w)
    img = rng.normal(0.02, 0.006, shape)
    yy, xx = np.mgrid[0:h, 0:w]
    prof = 0.05 * np.exp(-((yy - h / 3.0) ** 2 + (xx - w / 2.0) ** 2)
                         / (h * w / 30.0))
    for _ in range(30):
        cy, cx = rng.integers(0, h), rng.integers(0, w)
        prof = prof + 0.6 * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / 6.0)
    img = img + (prof[..., None] if n > 1 else prof)
    return np.clip(img.astype(np.float32), 0.0, 1.0)


def reglages(proche, **extra):
    """Dict de réglages du rendu pleine résolution, repris de l'état `proche`
    (jalon 5 : la sauvegarde lit le dict capturé côté UI, jamais l'état vivant)."""
    d = dict(stretch=proche.stretch, auto=proche.auto,
             sigma_k=proche.sigma_k, target=proche.target,
             black=proche.black, white=proche.white,
             gamma=proche.gamma, saturation=proche.saturation,
             bar_noir=proche.bar_noir, bar_median=proche.bar_median,
             bar_blanc=proche.bar_blanc,
             sat_canaux=tuple(proche.sat_canaux),
             stats_gelees=(proche._stats if proche.fige else None),
             vl_mode_res=proche.vl_mode_res, vl_target_bg=proche.vl_target_bg,
             vl_log_d=proche.vl_log_d, vl_profil=proche.vl_profil,
             vl_log_d_resolu=proche.vl_log_d_resolu)
    d.update(extra)
    return d


rgb = image_factice()
mono = image_factice(mono=True)

print("[1] Étage de niveaux : IDENTITÉ AU BIT, sinon court-circuit")
x = np.random.default_rng(3).random((64, 64, 3)).astype(np.float32)
y = niveaux(x, 0.0, 0.5, 1.0)
verifie(y is x or np.array_equal(y, x), "niveaux(x, 0, 0,5, 1) rend x au bit près")
verifie(not niveaux_actifs(0.0, 0.5, 1.0), "niveaux_actifs : identité détectée")
verifie(niveaux_actifs(0.0, 0.25, 1.0) and niveaux_actifs(0.01, 0.5, 1.0)
        and niveaux_actifs(0.0, 0.5, 0.99),
        "niveaux_actifs : médian, noir et blanc détectés séparément")
d_ex = DisplayProcessor()
d_ex.bar_noir, d_ex.bar_median, d_ex.bar_blanc = 0.0, 0.5, 1.0
d_ref = DisplayProcessor()
verifie(np.array_equal(d_ex.process(rgb, live=False),
                       d_ref.process(rgb, live=False)),
        "un rendu avec barres « posées » à l'identité = un rendu sans barres")

print("[2] Le sens du geste : la position de la barre EST le niveau affiché")
verifie(all(abs(float(mtf(np.float32(m), m)) - 0.5) < 1e-6
            for m in (0.1, 0.25, 0.5, 0.75, 0.9)),
        "MTF(m, m) = 0,5 (gris moyen) pour tout médian")
v = np.linspace(0.0, 1.0, 1024).astype(np.float32)
verifie(float(niveaux(v, 0.25, 0.5, 1.0)[v < 0.25].max()) == 0.0,
        "la barre NOIR coupe tout ce qui est en dessous d'elle")
verifie(float(niveaux(v, 0.0, 0.5, 0.75)[v > 0.75].min()) == 1.0,
        "la barre BLANC sature tout ce qui est au-dessus d'elle")
verifie(abs(float(niveaux(np.float32(0.5), 0.0, 0.5, 1.0)) - 0.5) < 1e-6,
        "sans barre touchée, la sortie = l'entrée")

print("[3] Parité ÉCRAN / FICHIER (« tel que vu ») au bit, barres comprises")
d3 = DisplayProcessor()
d3.bar_noir, d3.bar_median, d3.bar_blanc = 0.08, 0.42, 0.93
d3.gamma, d3.saturation = 1.35, 1.25
d3.sat_canaux = (1.4, 1.0, 0.8)
scr = d3.process(rgb, live=False)
fich = (d3.rendu_pleine_resolution(rgb, reglages(d3)) * 255).astype(np.uint8)
verifie(np.array_equal(scr, fich),
        "écran == fichier au bit près (barres + gamma + saturations)")
d4 = DisplayProcessor()
d4.process(rgb, live=False)                 # stats établies sur CETTE image
d4.fige = True
autre = image_factice(seed=7)
verifie(np.array_equal(d4._auto_params(rgb, live=False),
                       d4._auto_params(autre, live=False)),
        "étirement gelé : les paramètres ne suivent plus l'image")
scr_g = d4.process(autre, live=False)
fich_g = (d4.rendu_pleine_resolution(autre, reglages(d4)) * 255).astype(np.uint8)
verifie(np.array_equal(scr_g, fich_g),
        "gelé : le fichier utilise les MÊMES stats gelées que l'écran (au bit)")
sans = (d4.rendu_pleine_resolution(autre, reglages(d4, stats_gelees=None))
        * 255).astype(np.uint8)
verifie(not np.array_equal(fich_g, sans),
        "témoin : SANS les stats gelées le fichier serait différent (le test mord)")

print("[4] Mode manuel (auto décoché) : INCHANGÉ")
d5 = DisplayProcessor()
d5.auto = False
d5.black, d5.white = 0.015, 0.030
attendu5 = (np.clip((rgb - 0.015) / (0.030 - 0.015), 0.0, 1.0) * 255.0
            ).astype(np.uint8)
verifie(np.array_equal(d5.process(rgb, live=False), attendu5),
        "manuel : clip((img−black)/(white−black)), sans médian ajouté")

print("[5] Gel / reprise de l'étirement automatique (STF)")
d6 = DisplayProcessor()
d6.process(rgb, live=False)
avant = d6._auto_params(rgb, live=False)
d6.fige = True
verifie(d6._auto_params(autre, live=False) == avant,
        "gelé : les paramètres restent ceux de la dernière frame")
d6.reprendre_auto()
verifie(d6._stats is None and d6._auto_params(autre, live=False) != avant,
        "reprise : stats oubliées, recalculées sur l'image courante")
d7 = DisplayProcessor()
d7.fige = True                       # gel demandé AVANT toute stat connue
verifie(d7._auto_params(rgb, live=False) is not None,
        "gel sans stats : l'auto s'établit quand même (aucun blocage)")

print("[6] Saturation par couleur : SECTEUR DE TEINTE (pas de « l'un renforce "
      "l'autre »)")
verifie(not saturation_actifs((1.0, 1.0, 1.0))
        and saturation_actifs((1.3, 1.0, 1.0)),
        "saturation_actifs : neutre détecté (chemin rapide)")


def sat(px):
    """Saturation HSV d'un pixel RGB (même convention que le traitement)."""
    import cv2 as _cv
    return float(_cv.cvtColor(np.array([[px]], np.float32),
                              _cv.COLOR_RGB2HSV)[0, 0, 1])


def teinte(px):
    """Teinte HSV (0..360) d'un pixel RGB."""
    import cv2 as _cv
    return float(_cv.cvtColor(np.array([[px]], np.float32),
                              _cv.COLOR_RGB2HSV)[0, 0, 0])


rouge = np.array([[[0.70, 0.20, 0.20]]], np.float32)
vert = np.array([[[0.20, 0.60, 0.20]]], np.float32)
jaune = np.array([[[0.70, 0.70, 0.20]]], np.float32)
r = saturation_canaux(rouge, (2.0, 1.0, 1.0))[0, 0]
# NB : saturer un rouge rapproche naturellement V et B de 0 (c'est la
# définition de la saturation) — ce qui doit rester invariant, c'est la TEINTE
# et la VALEUR (le maximum), pas les canaux faibles.
verifie(sat(r) > sat(rouge[0, 0]) + 0.05
        and abs(teinte(r) - teinte(rouge[0, 0])) < 1.0
        and abs(float(max(r)) - 0.70) < 1e-5,
        "curseur ROUGE à 2,00 : le rouge devient PLUS saturé, teinte et valeur "
        "intactes")
# LE contrôle qui répond au constat d'Alain (« quand je pousse l'un, c'est
# l'autre couleur qui se renforce ») : avant correction, le curseur rouge
# faisait tomber le rouge d'un pixel vert (0,20 → 0,00), donc verdissait tout.
v = saturation_canaux(vert, (2.0, 1.0, 1.0))[0, 0]
verifie(np.allclose(v, vert[0, 0], atol=1e-5),
        "curseur ROUGE à 2,00 : un pixel VERT ne bouge pas (défaut corrigé)")
g = saturation_canaux(vert, (1.0, 2.0, 1.0))[0, 0]
verifie(sat(g) > sat(vert[0, 0]) + 0.05, "curseur VERT à 2,00 : le vert monte")
b = saturation_canaux(np.array([[[0.20, 0.20, 0.70]]], np.float32),
                      (1.0, 1.0, 2.0))[0, 0]
verifie(sat(b) > 0.5 + 0.05, "curseur BLEU à 2,00 : le bleu monte")
verifie(np.allclose(saturation_canaux(jaune, (2.0, 1.0, 1.0)),
                    saturation_canaux(jaune, (1.0, 2.0, 1.0)), atol=1e-6),
        "un jaune (entre deux secteurs) réagit PAREIL aux deux curseurs "
        "(poids 1/2 - 1/2 : transition douce)")
gris = np.array([[[0.4, 0.4, 0.4]]], np.float32)
verifie(np.allclose(saturation_canaux(gris, (2.0, 0.5, 1.5)), gris, atol=1e-6),
        "un gris (S = 0) reste un gris, quels que soient les trois curseurs")
verifie(np.array_equal(
            DisplayProcessor._finition(mono, False, 1.0, 1.0, (2.0, 1.0, 1.0)),
            DisplayProcessor._finition(mono, False, 1.0, 1.0, None)),
        "mono : la saturation par couleur est sans effet (non appelée)")
glob = DisplayProcessor._finition(rgb, True, 1.0, 1.5, None)
verifie(np.allclose(DisplayProcessor._finition(rgb, True, 1.0, 1.5,
                                               (2.0, 1.0, 1.0)),
                    DisplayProcessor._finition(glob, True, 1.0, 1.0,
                                               (2.0, 1.0, 1.0)), atol=1e-6),
        "ordre : saturation GLOBALE puis saturation par couleur")

print("[7] Les deux bandes : coût indépendant de la résolution, échelle commune")
petit = image_factice(600, 800)
gros = image_factice(1800, 2400, seed=1)
t0 = time.perf_counter()
c1, hi1 = ui.App._hist_canaux(petit)
t1 = time.perf_counter() - t0
t0 = time.perf_counter()
c2, hi2 = ui.App._hist_canaux(gros)
t2 = time.perf_counter() - t0
verifie(len(c1) == 3 and len(c1[0]) == 256 and hi1 > 0,
        "3 canaux × 256 bacs, axe calculé (brut)")
c3, hi3 = ui.App._hist_canaux(petit, plage=(0.0, 1.0))
verifie(hi3 == 1.0, "bande « sortie » : axe imposé 0..1")
verifie(t2 < 0.30 and t2 < 4.0 * max(t1, 1e-3) + 0.05,
        "coût borné et peu sensible à la résolution (%.1f ms en 0,5 Mpx, "
        "%.1f ms en 13 Mpx)" % (t1 * 1000.0, t2 * 1000.0))
cha = [np.zeros(256), np.zeros(256), np.zeros(256)]
cha[0][128] = 1000.0                 # rouge : pic franc
cha[2][128] = 10.0                   # bleu : pic 100 fois plus petit
polys = ui.App._courbes_pts(cha, 400, 0, 100)
hauts = [min(q[1::2]) for q in polys]
verifie(hauts[2] > hauts[0] + 40,
        "pic 100 fois plus petit → courbe bien plus basse (échelle COMMUNE : "
        "l'ancienne normalisation par canal les superposait)")

print("[8] Géométrie et interactions des barres (fenêtre réelle)")
ui.CONFIG = {}                      # état initial DÉTERMINÉ (moteur STF)
ui.sauver_config = lambda d: None
root = tk.Tk()
app = ui.App(root)
root.update()
app.cv_hist.config(width=840)
root.update()
# Deux bandes REMPLIES (histogrammes factices) : le tracé doit être vérifié
# dans son état complet — courbes, légendes, repères et étiquettes de barres —
# et non sur deux bandes vides.
app._hist_brut = ui.App._hist_canaux(rgb)
app._hist_sortie = (ui.App._hist_canaux(rgb, plage=(0.0, 1.0))[0],)
app.disp.auto = True
app.disp.last_lo, app.disp.last_hi, app.disp.last_m = 0.015, 0.029, 0.32
w = app._hist_taille()[0]
verifie(abs(app._hist_x(0.0, w) - app.HIST_MARGE) < 1e-6
        and abs(app._hist_x(1.0, w) - (w - app.HIST_MARGE)) < 1e-6,
        "l'axe « sortie » va de la marge gauche à la marge droite")
verifie(all(abs(app._hist_valeur(app._hist_x(v, w), w) - v) < 1e-6
            for v in (0.0, 0.25, 0.5, 0.75, 1.0)),
        "aller-retour position ↔ valeur exact")
app.disp.bar_noir, app.disp.bar_median, app.disp.bar_blanc = 0.2, 0.5, 0.8
verifie(app._hist_hit(app._hist_x(0.5, w), w) == "median",
        "la barre médian est saisie à sa position")
verifie(app._hist_hit(app._hist_x(0.5, w) + app.HIST_PRISE + 3, w) is None,
        "hors de la zone de prise : aucune barre saisie")


class Ev:
    """Évènement Tk simulé (seul `x` est utilisé par les gestes)."""
    def __init__(self, x):
        self.x = x


app._hist_press(Ev(app._hist_x(0.50, w)))
verifie(app._hist_drag == "median", "le clic sur la barre médian la saisit")
app._hist_drag_move(Ev(app._hist_x(0.62, w)))
app._hist_release()
verifie(abs(app.disp.bar_median - 0.62) < 1e-6, "le glissement déplace la barre")
app.disp.bar_noir, app.disp.bar_median, app.disp.bar_blanc = 0.2, 0.5, 0.6
app._hist_press(Ev(app._hist_x(0.95, w)))
app._hist_drag_move(Ev(app._hist_x(0.95, w)))
app._hist_release()
verifie(app.disp.bar_median <= app.disp.bar_blanc - 0.009,
        "médian poussé au-delà du blanc : il s'arrête juste avant")


def poignee_median(application):
    """Abscisse de la POIGNÉE de la barre médian telle qu'elle est TRACÉE.

    On lit le Canvas (source de vérité de ce que voit Alain), pas les
    paramètres : c'est ce qui permet d'attraper un panneau qui ne suit pas le
    geste alors que les valeurs, elles, sont bien à jour."""
    for item in application.cv_hist.find_all():
        if (application.cv_hist.type(item) == "rectangle"
                and application.cv_hist.itemcget(item, "fill") == "#ffd75e"):
            c = application.cv_hist.coords(item)
            return (c[0] + c[2]) / 2.0
    return None


def poignees_posees(application, largeur):
    """VRAI si les TROIS barres sont tracées à l'abscisse de leur valeur.

    Les poignées sont reconnues par leur GÉOMÉTRIE (8 × 7 px) et non par leur
    couleur : « noir » et « blanc » la partagent (blanche tous les deux), un
    tri par couleur confondrait les deux — erreur commise dans la 1re écriture
    de ce contrôle, et c'est le banc qui l'a montrée."""
    xs = []
    for item in application.cv_hist.find_all():
        if application.cv_hist.type(item) != "rectangle":
            continue
        c = application.cv_hist.coords(item)
        if abs((c[2] - c[0]) - 8.0) < 0.6 and abs((c[3] - c[1]) - 7.0) < 0.6:
            xs.append((c[0] + c[2]) / 2.0)
    vals = sorted((application.disp.bar_noir, application.disp.bar_median,
                   application.disp.bar_blanc))
    return (len(xs) == 3
            and all(abs(x - application._hist_x(v, largeur)) < 1.5
                    for x, v in zip(sorted(xs), vals)))


# LE TRACÉ SUIT LE DOIGT SANS AUCUNE FRAME (défaut RÉEL signalé par Alain le
# 28/09/2026 : « quand l'empilement est fini, si on touche aux barres, l'image
# change alors que la position de la barre ne change pas, ou pas complètement,
# comme si le bas n'était pas rafraîchi »). Rien ici ne produit de frame : seul
# le geste doit faire bouger le panneau — et SANS recalculer l'histogramme,
# puisque la courbe (sortie du moteur, avant l'étage de niveaux) ne dépend pas
# des barres.
app.disp.bar_noir, app.disp.bar_median, app.disp.bar_blanc = 0.10, 0.50, 0.90
app._draw_hist()
n_maj = [0]
_vraie_maj = app._maj_histogrammes


def _maj_comptee(*a, **k):
    n_maj[0] += 1
    return _vraie_maj(*a, **k)


app._maj_histogrammes = _maj_comptee
brut_avant, sortie_avant = app._hist_brut, app._hist_sortie
app._hist_press(Ev(app._hist_x(0.50, w)))
app._hist_drag_move(Ev(app._hist_x(0.68, w)))
x_trace = poignee_median(app)
app._hist_release()
attendu = app._hist_x(0.68, w)
verifie(x_trace is not None and abs(x_trace - attendu) < 1.5,
        "sans aucune frame, la POIGNÉE TRACÉE suit le doigt (%.1f px attendu, "
        "%s px tracé)" % (attendu, "—" if x_trace is None else "%.1f" % x_trace))
verifie(poignees_posees(app, w) and n_maj[0] == 0
        and app._hist_brut is brut_avant and app._hist_sortie is sortie_avant,
        "les trois barres sont tracées à leur valeur… et sans AUCUN recalcul de "
        "l'histogramme (une barre ne change pas la courbe)")
app._hist_press(Ev(app._hist_x(0.90, w)))          # relâchement hors du geste
app._hist_drag_move(Ev(app._hist_x(0.80, w)))
app._hist_release()
verifie(poignees_posees(app, w),
        "le relâchement retrace les valeurs RÉELLEMENT appliquées (blanc "
        "%.0f %%)" % (100.0 * app.disp.bar_blanc))
app.disp.bar_median = 0.70
app._draw_hist()
app._hist_dblclick(Ev(app._hist_x(0.70, w)))
verifie(abs(poignee_median(app) - app._hist_x(0.50, w)) < 1.5,
        "double-clic : la barre revient au défaut ET le tracé suit")
app._maj_histogrammes = _vraie_maj
t0 = time.perf_counter()
for _ in range(40):
    app._draw_hist()
t_trace = (time.perf_counter() - t0) / 40.0
verifie(t_trace < 0.02,
        "un tracé complet coûte %.1f ms (il peut donc suivre CHAQUE pixel de "
        "souris, l'image restant le gros du travail)" % (t_trace * 1000.0))

app.ent_bar["noir"].delete(0, "end")
app.ent_bar["noir"].insert(0, "15")
app._on_niveaux_saisie()
verifie(abs(app.disp.bar_noir - 0.15) < 1e-9, "la saisie « 15 » vaut 15 %")
app.disp.bar_median = 0.44
app._maj_niveaux_vue()
verifie(abs(float(app.var_bar_median.get()) - 44.0) < 0.05,
        "l'affichage resynchronise les champs (une seule source de vérité)")
app.var_hist_mode.set("Brut (linéaire)")
app._on_hist_mode()
root.update()
app._draw_hist()
n_brut = len(app.cv_hist.find_all())
verifie(app.hist_mode == "brut" and app._hist_zone_sortie() is None,
        "sélecteur « brut » : une seule bande, pas de barres")
app.var_hist_mode.set("Sortie du moteur")
app._on_hist_mode()
root.update()
app._draw_hist()
n_sortie = len(app.cv_hist.find_all())
app.var_hist_mode.set("Les deux")
app._on_hist_mode()
root.update()
app._draw_hist()
n_deux = len(app.cv_hist.find_all())
verifie(n_sortie > n_brut and n_deux > n_sortie,
        "les trois états dessinent bien des choses différentes (%d / %d / %d)"
        % (n_brut, n_sortie, n_deux))
verifie(app._hist_zone_sortie() is not None,
        "en mode « les deux », la bande « sortie » existe (barres actives)")
# Étiquettes : contenues dans le Canvas ET sans chevauchement, même quand les
# trois barres se serrent (leçon des jalons 72/74 : un texte rogné ou superposé
# est un défaut, et il ne se réveille qu'avec des valeurs extrêmes).
app.disp.bar_noir, app.disp.bar_median, app.disp.bar_blanc = 0.40, 0.42, 0.44
app._maj_niveaux_vue()
app._draw_hist()
boites = []
for item in app.cv_hist.find_all():
    if app.cv_hist.type(item) == "text":
        b = app.cv_hist.bbox(item)
        if b:
            boites.append(b)
lg, ht = app._hist_taille()
hors = [b for b in boites
        if b[0] < 0 or b[2] > lg + 1 or b[1] < 0 or b[3] > ht + 1]
verifie(not hors, "aucune étiquette ne sort du Canvas (%d textes)" % len(boites))


def croise(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


doubles = [(i, j) for i in range(len(boites)) for j in range(i + 1, len(boites))
           if croise(boites[i], boites[j])]
verifie(not doubles,
        "aucune étiquette n'en chevauche une autre (%d textes, 3 barres serrées)"
        % len(boites))

print("[9] UI : état initial, ⏹/▶ dans les DEUX moteurs, session neuve")
app.disp.reset()
app._tick()                          # consomme le drapeau « niveaux_new »
verifie(app.disp.bar_noir == 0.0 and app.disp.bar_median == 0.5
        and app.disp.bar_blanc == 1.0,
        "session neuve : barres remises à l'identité CÔTÉ AFFICHAGE")
verifie(abs(float(app.var_bar_median.get()) - 50.0) < 0.05
        and app.btn_figer.cget("text") == "⏹ Figer l'auto",
        "session neuve : champs et bouton resynchronisés")
verifie("décalage sur l'auto" in app.lbl_hist_etat.cget("text"),
        "l'état affiché dit que les barres sont un DÉCALAGE sur l'auto")
app.var_moteur.set("STF")
app._on_moteur()
app._on_figer()
verifie(app.disp.fige and "auto FIGÉ (STF" in app.lbl_hist_etat.cget("text")
        and "Reprendre" in app.btn_figer.cget("text"),
        "STF : ⏹ gèle l'auto ET l'état le dit")
verifie("cible du fond 25 %" in app.lbl_hist_etat.cget("text"),
        "l'état DIT la cible de fond du moteur (25 % par défaut en STF)")
app.var_target.set(0.30)                 # curseur STF « Luminosité du fond »
app._on_target_auto()
verifie("cible du fond 30 %" in app.lbl_hist_etat.cget("text"),
        "changer la cible du STF met la ligne d'état à jour (l'état ne ment pas)")
app.var_target.set(0.25)
app._on_target_auto()
app._on_figer()
verifie(not app.disp.fige and app.disp._stats is None
        and app.disp.bar_noir == 0.0,
        "STF : ▶ reprend (stats oubliées), sans toucher aux barres")
if veralux_moteur.moteur_disponible():
    app.var_moteur.set("VeraLux")
    app._on_moteur()
    app.disp.vl_log_d_resolu = 2.35          # comme après une résolution
    app.var_vl_target.set(0.16)
    app.disp.vl_target_bg = 0.16     # comme le curseur : l'état lit disp
    app._on_figer()
    verifie(app.var_vl_mode_res.get() == "logD forcé"
            and abs(float(app.var_vl_logd.get()) - 2.35) < 1e-6
            and "auto FIGÉ (VeraLux" in app.lbl_hist_etat.cget("text"),
            "VeraLux : ⏹ verrouille le logD résolu (le moteur est gelé)")
    verifie("fond visé 16 %" in app.lbl_hist_etat.cget("text"),
            "VeraLux : l'état dit SON fond visé (16 %), pas un défaut supposé")
    app._on_figer()
    verifie(app.var_vl_mode_res.get() == "fond cible (auto)",
            "VeraLux : ▶ rend la main au fond cible")
else:
    print("  (moteur VeraLux absent : contrôle du gel VeraLux sauté)")

print("[10] La chaîne LINÉAIRE n'est pas contaminée par les barres")
reg = app._reglages_rendu()
verifie(all(k in reg for k in ("bar_noir", "bar_median", "bar_blanc",
                               "sat_canaux", "stats_gelees")),
        "les réglages capturés portent barres, saturations et stats gelées")
sans_bar = dict((k, v) for k, v in reg.items() if not k.startswith("bar_"))
app.disp.bar_noir, app.disp.bar_median, app.disp.bar_blanc = 0.31, 0.44, 0.87
reg2 = app._reglages_rendu()
sans_bar2 = dict((k, v) for k, v in reg2.items() if not k.startswith("bar_"))
verifie(sans_bar == sans_bar2,
        "changer les barres ne modifie AUCUN autre réglage (empilement intact)")
verifie(reg2["bar_noir"] == 0.31,
        "…mais la barre est bien TRANSPORTÉE vers « tel que vu »")

print("[11] Échelle y de la bande basse : LOG (défaut) contre LINÉAIRE")
# Propriété qui DÉFINIT « linéaire » : le rapport des hauteurs ÉGALE le rapport
# des comptes (1000 contre 10 → ×100) — le log, lui, le compresse ; c'est
# exactement ce qui transforme la « colline » en PIC (mesuré sur les frames
# d'Alain : 170 bacs à mi-hauteur → 27).
bacs = [np.zeros(256), np.zeros(256), np.zeros(256)]
bacs[0][100], bacs[0][120] = 1000.0, 10.0
h_log = ui.App._courbes_pts(bacs, 400, 0, 100)
h_lin = ui.App._courbes_pts(bacs, 400, 0, 100, lineaire=True)


def hauteur(pts, i, base=100.0):
    """Hauteur du bac i au-dessus du bas de la bande (les points d'une
    polyligne sont [x0, y0, x1, y1, …], d'où l'indice 2·i + 1). On retire la
    marge de 1 px du tracé : sans elle, le rapport des hauteurs n'est plus
    exactement celui des comptes (mesuré ×50 au lieu de ×100)."""
    return base - pts[2 * i + 1] - 1.0


r_log = hauteur(h_log[0], 100) / max(hauteur(h_log[0], 120), 1e-9)
r_lin = hauteur(h_lin[0], 100) / max(hauteur(h_lin[0], 120), 1e-9)
verifie(abs(r_lin - 100.0) < 0.5 and 2.0 < r_log < 5.0,
        "linéaire : hauteur PROPORTIONNELLE aux comptes (×%.0f pour 1000/10), "
        "là où le log la comprime à ×%.1f" % (r_lin, r_log))
# Le tracé laisse 1 px de marge en haut (y0 - 1) : c'est là que doit se trouver
# le bac le plus peuplé, l'échelle étant COMMUNE aux trois canaux.
verifie(abs(min(h_lin[0][1::2]) + 1.0) < 1e-9,
        "…et le bac le plus peuplé touche le haut de la bande (échelle COMMUNE)")
# La case elle-même : VISIBLE (leçon du jalon 72 — `pack` abandonne
# SILENCIEUSEMENT un widget qui ne tient plus) et CÂBLÉE de bout en bout.
root.update()
verifie(app.chk_hist_lineaire.winfo_ismapped() == 1
        and app.chk_hist_lineaire.winfo_width() > 30,
        "la case est VISIBLE, pack ne l'a pas abandonnée (largeur %d px)"
        % app.chk_hist_lineaire.winfo_width())
app.chk_hist_lineaire.invoke()
verifie(app.hist_lineaire and app.var_hist_lineaire.get(),
        "la case est CÂBLÉE : le clic lève bien l'état de l'affichage")
app.chk_hist_lineaire.invoke()
verifie(not app.hist_lineaire, "…et le second clic revient au log")


def lignes_canvas(application):
    """Tous les tracés du Canvas, dans l'ordre de création (la bande HAUTE est
    dessinée en premier : ses 3 courbes sont les 3 premiers items)."""
    return [tuple(application.cv_hist.coords(i))
            for i in application.cv_hist.find_all()
            if application.cv_hist.type(i) == "line"]


app.var_hist_mode.set("Les deux")
app._on_hist_mode()
root.update()
avant = lignes_canvas(app)
barres_avant = (app.disp.bar_noir, app.disp.bar_median, app.disp.bar_blanc)
n_maj2 = [0]


def _maj_comptee2(*a, **k):
    n_maj2[0] += 1
    return _vraie_maj(*a, **k)


app._maj_histogrammes = _maj_comptee2
app.var_hist_lineaire.set(True)
app._on_hist_lineaire()
apres = lignes_canvas(app)
app._maj_histogrammes = _vraie_maj
diff = [i for i, (a, b) in enumerate(zip(avant, apres)) if a != b]
verifie(len(avant) == len(apres) and avant[:3] == apres[:3],
        "la bande HAUTE (3 premières courbes) n'est PAS touchée : en linéaire "
        "elle ne montrerait plus que 10 bacs sur 256")
verifie(len(diff) == 3 and all(i > 3 for i in diff),
        "exactement les 3 courbes de la BANDE BASSE changent (items %s)" % diff)
verifie(n_maj2[0] == 0,
        "basculer l'échelle ne recalcule AUCUN histogramme (les bacs sont en "
        "mémoire, règle du défaut ③)")
verifie(app.hist_lineaire
        and "échelle y LINÉAIRE" in app.lbl_hist_etat.cget("text"),
        "l'état DIT l'échelle de la bande basse (une échelle muette est un "
        "piège : 66 % de l'axe en log, 10,5 % en linéaire)")
verifie((app.disp.bar_noir, app.disp.bar_median, app.disp.bar_blanc)
        == barres_avant,
        "…et les barres n'ont pas bougé d'un pixel (elles vivent en x)")
capture = []
ui.sauver_config = lambda d: capture.append(d)
app._sauver_config_app()
verifie(capture and capture[-1].get("hist_lineaire") is True,
        "la case est PERSISTÉE (une config d'avant la case garde le log)")
ui.sauver_config = lambda d: None
app.var_hist_lineaire.set(False)
app._on_hist_lineaire()
verifie(not app.hist_lineaire and lignes_canvas(app) == avant,
        "retour au LOG : le tracé d'origine revient AU BIT (zéro régression)")


root.destroy()
print()
print("BANC JALON 75 (histogramme 2 bandes et barres de niveaux) :",
      "TOUT PASSE ✅" if ok else "ÉCHECS ❌")
raise SystemExit(0 if ok else 1)


