# -*- coding: utf-8 -*-
"""Mesure P5 (lot 5) — réactivité MESURÉE de l'interface : les chiffres AVANT le code.

QUESTION (lot 5 = P5, branche `OptimisationUI`, 20/10/2026) : l'interface est-elle
LENTE, et OÙ ? Le chantier P5 corrigera APRÈS, jamais avant : ce banc ne change
RIEN au produit, il chronomètre ce qui existe et écrit ses chiffres (motif
P1/P4 : JSON conservé pour comparer avant/après).

CE QUI EST CHRONOMMÉTRÉ (les cinq suspicions du lot, plus la décomposition)
  [1] curseurs   — `_add_slider` : coût d'un PAS de glissement et coût du
                   GLISSEMENT COMPLET (le pas + l'aperçu du relâchement), puis
                   le coût d'un glissement de 200 px (P5 : plus rien pendant le
                   geste, UN aperçu au relâchement — voir plus bas) ;
  [2] aperçu     — `_refresh_preview` avec et sans histogrammes, et la part
                   exacte des histogrammes dedans (34 ms au jalon 79) ;
  [3] boucle     — `_tick` : coût de `_tick_corps` en état stable, en % du
                   budget de 30 ms ;
  [4] cases      — `invoke()` (clic réel) contre `var.set` nu (que Tk
                   n'accompagne d'AUCUN rappel — mesuré ici, pas supposé) ;
  [5] listes     — combobox de 147/200 valeurs : coût d'un repeuplement
                   (`config(values=...)`), d'un `set` et d'une sélection ;
  [6] spinners   — coût d'un cran ; le `command` d'un Spinbox ne part JAMAIS
                   sur `set()`, contrairement à un Scale (mesuré ici) ;
  [7] visibilité — `_maj_visibilite_cadres` : coût et NOMBRE de `pack`/`forget`
                   par changement de source ;
  [8] rafale     — boucle `_tick` ACTIVE : un glissement d'une seconde
                   prive-t-il le fil d'interface ? (battements obtenus contre
                   attendus, écart maximal entre deux battements, NOMBRE
                   D'APERÇUS — attendu : UN seul, au relâchement).

P5 — LE CORRECTIF EST DANS LE CHEMIN MESURÉ (v2.97.0, 20/10/2026) : depuis le
RENDU AU RELÂCHEMENT, les sections [1] et [8] passent par le VRAI geste
(`_debut_glissement` / `_fin_glissement`, les gestionnaires de
`<ButtonPress-1>` / `<ButtonRelease-1>`). Un `s.set()` seul ne fait plus que la
variable et l'étiquette : le chiffre « pas de glissement » est donc celui de la
souris, et l'aperçu n'est compté qu'une fois le doigt levé. Les chiffres d'AVANT
le correctif (un aperçu PAR PIXEL, 50 à 76 s pour 200 px) restent au JSON du
20/10 et dans `AVANCEMENT.md` : c'est la référence de comparaison.

SEUIL DU GUET (0,25 s) : le lot prévoit de baisser `Guet.SEUIL_S` à 0,25 s
« temporairement ». Ici la MÊME question est posée sans toucher au produit :
chaque opération mesurée est comptée au-delà de `--seuil` (défaut 0,25 s) et le
rapport dit combien d'opérations le Guet aurait signalées. Rien n'est donc à
annuler après le passage — un seuil « temporaire » qu'on oublie de remonter
fausserait le journal des sessions suivantes.

TAILLE MESURÉE (correction du 20/10/2026, remarque d'Alain « qui travaille en
360×560 ? ») : l'aperçu n'est PAS une vignette. L'application le plafonne à
**1600 px de côté** (`worker.py` / `app.py` : `min(1.0, 1600/max(h, w))`), soit
**1600×1200** en 4/3 et **1600×900** en 16:9, et le dessin se fait à la taille
du CANVAS (`_render` : cv2.resize + PIL/PhotoImage). Le banc mesure donc par
défaut sur un **aperçu 1600×1200** dans une **fenêtre PLEIN ÉCRAN** (24 pouces,
1920×1080) ; `--taille` et `--fenetre` changent cela, et la section [2 bis]
donne la COURBE coût/taille — un chiffre pris en 360×560 ne décrit pas l'usage
réel (il donne une borne BASSE).

USAGE
  python bancs/_mesure_p5_reactivite.py             # mesure complète (écran requis)
  python bancs/_mesure_p5_reactivite.py --n 7       # plus de répétitions (médianes)
  python bancs/_mesure_p5_reactivite.py --seuil 0.1 # autre seuil de signalement
  python bancs/_mesure_p5_reactivite.py --autotest  # mécanique seule (aucun écran)

SORTIE : tableau console + `bancs/_mesure_p5_reactivite.json` (rejouable, diff).
Les chiffres du passage réel sont consignés dans `AVANCEMENT.md`.
"""

import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc))
        break

import argparse
import json
import os
import statistics
import sys
import time

if hasattr(sys.stdout, "reconfigure"):     # sortie pipée ≠ console (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SORTIE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "_mesure_p5_reactivite.json")
SEUIL_DEFAUT = 0.25          # s — seuil de signalement voulu par le lot 5
BUDGET_TICK_MS = 30.0        # la boucle d'interface se replanifie toutes les 30 ms
APERCU_MAX_PX = 1600         # plafond de l'aperçu : `min(1, 1600/max(h, w))`
APERCU_DEFAUT = (1600, 1200)  # 4:3 AU PLAFOND = le cas le plus coûteux
ECHELLES = "560x360,1280x720,1600x1200"   # courbe de coût selon la taille


def lire_taille(txt, defaut=APERCU_DEFAUT):
    """« 1600x1200 » → (1600, 1200) ; « auto » → le plafond de l'aperçu réel.

    POURQUOI CE PLAFOND (correction du 20/10, remarque d'Alain « qui travaille
    en 360×560 ? ») : l'application ne rend JAMAIS l'aperçu en pleine résolution
    — `worker.py` et `app.py` le réduisent par `min(1.0, 1600/max(h, w))`. Un
    capteur 4/3 (QHY MiniCam8M) donne donc **1600×1200** et un 16:9
    (IMX585) **1600×900** : c'est CETTE image que l'étirement, la saturation et
    les histogrammes parcourent à chaque geste.
    """
    t = str(txt or "auto").strip().lower().replace("×", "x").replace(" ", "")
    if t in ("", "auto", "apercu", "aperçu", "defaut", "défaut"):
        return tuple(defaut)                       # pyright: ignore
    for sep in ("x", "*", ","):
        if sep in t:
            a, _, b = t.partition(sep)
            try:
                w, h = int(float(a)), int(float(b))
            except ValueError:
                raise SystemExit(f"taille illisible : {txt!r} (attendu LxH)")
            if w < 8 or h < 8:
                raise SystemExit(f"taille trop petite : {txt!r}")
            return (w, h)
    raise SystemExit(f"taille illisible : {txt!r} (attendu LxH)")



# --------------------------------------------------------------------------- #
# Mécanique PURE (testable sans écran : --autotest)
# --------------------------------------------------------------------------- #
def chrono(f, n=5):
    """Chronomètre `n` appels de `f` → médiane / min / max en MILLISECONDES.

    La MÉDIANE est la valeur de référence : un banc qui ne retiendrait que la
    moyenne laisserait un ramasse-miettes (ou un premier appel à froid) décider
    du chiffre publié.
    """
    durees = []
    for _ in range(max(1, int(n))):
        t0 = time.perf_counter()
        f()
        durees.append((time.perf_counter() - t0) * 1000.0)
    return {"n": len(durees),
            "med_ms": round(statistics.median(durees), 3),
            "min_ms": round(min(durees), 3),
            "max_ms": round(max(durees), 3)}


def au_dela(durees_ms, seuil_s):
    """Nombre d'opérations au-delà du seuil — l'équivalent d'un Guet abaissé."""
    return sum(1 for d in durees_ms if float(d) > float(seuil_s) * 1000.0)


def glissement_ms(pas_ms, n_pas=200):
    """Coût d'un GLISSEMENT de `n_pas` pixels de souris (P5 : un pas ≈ 0 ms).

    AVANT P5, un `ttk.Scale` rappelait sa `command` à CHAQUE changement de
    valeur : glisser sur 200 px coûtait 200 rappels complets (50 à 76 s sur
    l'aperçu réel). Depuis le rendu au relâchement, `pas_ms` est le coût d'un
    pas — on y ajoute l'aperçu UNIQUE du relâchement pour obtenir le prix du
    geste complet.
    """
    return round(float(pas_ms) * int(n_pas), 1)


def autotest():
    """Mécanique du banc, SANS interface : agrégats et seuils."""
    ok = True

    def verifie(cond, msg):
        nonlocal ok
        ok &= bool(cond)
        print(("  OK    " if cond else "  ÉCHEC ") + msg)

    d = chrono(lambda: None, 3)
    verifie(d["n"] == 3 and set(d) == {"n", "med_ms", "min_ms", "max_ms"},
            "chrono : 3 mesures, quatre champs (n, médiane, min, max)")
    verifie(d["min_ms"] <= d["med_ms"] <= d["max_ms"],
            "chrono : min ≤ médiane ≤ max")
    verifie(au_dela([10, 260, 300, 40], 0.25) == 2,
            "au_dela : compte les opérations au-delà du seuil (2 attendues)")
    verifie(au_dela([10, 40], 0.25) == 0,
            "au_dela : aucune opération sous le seuil")
    verifie(glissement_ms(4.0, 200) == 800.0,
            "glissement_ms : 200 pixels × 4 ms = 800 ms")
    verifie(lire_taille("auto") == APERCU_DEFAUT,
            f"lire_taille : « auto » = le plafond de l'aperçu {APERCU_DEFAUT}")
    verifie(lire_taille("1920x1080") == (1920, 1080),
            "lire_taille : « 1920x1080 »")
    verifie(lire_taille("800 × 600") == (800, 600),
            "lire_taille : ×, espaces et casse tolérés")
    try:
        lire_taille("beaucoup")
        refus = False
    except SystemExit:
        refus = True
    verifie(refus, "lire_taille : une taille illisible est REFUSÉE")
    return ok


def _enveloppe(fonction, durees):
    """Enveloppe `fonction` en notant sa durée (ms) dans `durees`."""
    def enveloppe(*a, **k):
        t0 = time.perf_counter()
        try:
            return fonction(*a, **k)
        finally:
            durees.append((time.perf_counter() - t0) * 1000.0)
    return enveloppe


def image_factice(h=360, w=560, seed=7):
    """Aperçu linéaire RVB factice [0..1] : fond + nébulosité + étoiles.

    Même image que le banc du jalon 79 — elle a du DÉTAIL (sinon un étirement
    ou une saturation ne changeraient rien et les mesures porteraient sur du
    vide).
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    img = rng.normal(0.02, 0.006, (h, w, 3))
    yy, xx = np.mgrid[0:h, 0:w]
    prof = 0.05 * np.exp(-((yy - h / 3.0) ** 2 + (xx - w / 2.0) ** 2)
                         / (h * w / 30.0))
    for _ in range(30):
        cy, cx = rng.integers(0, h), rng.integers(0, w)
        prof = prof + 0.6 * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / 6.0)
    img = img + prof[..., None]
    return np.clip(img, 0.0, 1.0).astype(np.float32)


# --------------------------------------------------------------------------- #
# Interface réelle
# --------------------------------------------------------------------------- #
def mesurer(n=5, seuil=SEUIL_DEFAUT, taille="auto", fenetre="zoomed",
            echelles=ECHELLES):
    """Chronomètre l'interface RÉELLE et rend le document du JSON."""
    import tkinter as tk
    from tkinter import ttk

    import avastack.ui.app as ui
    from avastack.cameras import SOURCES

    # Le guet de gel est DÉBRAYÉ : ce banc gèle volontairement la boucle
    # d'interface pendant ses mesures, ce qui ferait écrire de FAUX gels au
    # journal (et le seuil n'a pas à être remonté après coup).
    os.environ["AVASTACK_SANS_GUET"] = "1"

    doc = {"horodatage": time.strftime("%Y-%m-%d %H:%M:%S"),
           "seuil_s": float(seuil), "rep": int(n),
           "budget_tick_ms": BUDGET_TICK_MS}
    blocages = []            # (ms, nom) : le pire blocage observé, par opération

    def mesure(nom, f, rep=None, suivi=True):
        d = chrono(f, rep or n)
        if suivi:
            blocages.append((d["max_ms"], nom))
        return d

    def agrandir(fenetre_txt: str) -> str:
        """Met la fenêtre à l'usage RÉEL (24 pouces, 1920×1080) : plein écran.

        POURQUOI (remarque d'Alain, 20/10) : le dessin coûte selon la taille du
        CANVAS (`_render` : cv2.resize + PIL/PhotoImage) — mesurer dans la
        fenêtre de construction (canvas 840×560) sous-estime ce poste. « zoomed »
        reproduit un usage plein écran ; une géométrie explicite (« 1280x800 »)
        est aussi acceptée.
        """
        txt = str(fenetre_txt or "").strip().lower()
        if txt in ("", "normal", "normale", "defaut", "défaut"):
            return "normale"
        if txt in ("zoomed", "plein", "plein-ecran", "plein-écran", "max"):
            try:
                root.state("zoomed")                 # Windows / macOS
                return "plein écran"
            except tk.TclError:                      # Linux (X11)
                try:
                    root.attributes("-zoomed", True)
                    return "plein écran (attribut X11)"
                except tk.TclError:
                    return "normale (zoom indisponible)"
        w, h = lire_taille(txt)
        root.geometry(f"{w}x{h}+0+0")
        return f"{w}×{h}"

    # ------------------------------------------------------- [0] mise en place
    print("=" * 78)
    print("[0] INTERFACE RÉELLE (hermétique) — APERÇU POSÉ À LA TAILLE RÉELLE")
    print("=" * 78)
    ui.CONFIG = {}                       # état initial DÉTERMINÉ (moteur STF)
    ui.sauver_config = lambda d: None
    root = tk.Tk()
    t0 = time.perf_counter()
    app = ui.App(root)
    # 1b (20/10/2026) : cette MESURE chronomètre l'aperçu lui-même (P5) → rendu
    # IMMÉDIAT, sinon elle mesurerait une simple mise en file.
    app.rendu.immediat = True
    mode_fenetre = agrandir(fenetre)
    root.update()
    doc["construction_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)


    # La boucle d'interface est FIGÉE pour les sections 1 à 7 : sinon un tick
    # tomberait au milieu d'une mesure et le chiffre publié mélangerait deux
    # travaux. Elle est RALLUMÉE pour la rafale (section 8), qui en a besoin.
    try:
        if getattr(app, "_tick_id", None) is not None:
            root.after_cancel(app._tick_id)
    except Exception:                    # noqa: BLE001 — fenêtre déjà détruite
        pass
    app._tick_id = None
    app._planifier_tick = lambda delai=30: None      # pyright: ignore

    app.var_view.set("pile")
    lw, lh = lire_taille(taille)
    app.last_show = image_factice(lh, lw)
    app._refresh_preview()
    root.update()
    cw, ch = app.cv_img.winfo_width(), app.cv_img.winfo_height()
    doc["fenetre"] = mode_fenetre
    doc["apercu_taille"] = f"{lw}x{lh}"
    doc["apercu_mpx"] = round(lw * lh / 1e6, 2)
    doc["canvas"] = f"{cw}x{ch}"
    print(f"    construction : {doc['construction_ms']:.0f} ms · fenêtre "
          f"{mode_fenetre} · canvas {cw}×{ch}")
    print(f"    APERÇU MESURÉ : {lw}×{lh} ({lw * lh / 1e6:.2f} Mpx) — plafond "
          f"réel de l'application ({APERCU_MAX_PX} px de côté)")

    # --- instrumentation : on ENVELOPPE le code testé, on ne le remplace pas
    DECOMP = {"hist_ms": [], "show_ms": []}
    COMPTES = {"preview": 0}
    ui.App._maj_histogrammes = _enveloppe(
        ui.App._maj_histogrammes, DECOMP["hist_ms"])      # pyright: ignore
    ui.App._show_image = _enveloppe(
        ui.App._show_image, DECOMP["show_ms"])            # pyright: ignore
    _preview0 = ui.App._refresh_preview

    def preview(self, *a, **k):
        COMPTES["preview"] += 1
        return _preview0(self, *a, **k)

    ui.App._refresh_preview = preview                     # pyright: ignore

    # ------------------------------------------------------------ helpers widgets
    def parcours(w):
        yield w
        for e in w.winfo_children():
            yield from parcours(e)

    def curseur(texte):
        """Le `ttk.Scale` RÉEL portant l'étiquette `texte` (même technique que
        le banc du jalon 79 : par le libellé, jamais par une position en dur)."""
        for w in parcours(app.root):
            if not isinstance(w, ttk.Scale):
                continue
            ligne = w.master
            row = ligne.master if ligne is not None else None
            if row is None:
                continue
            for cadre in row.winfo_children():
                for c in cadre.winfo_children():
                    try:
                        if str(c.cget("text")) == texte:
                            return w
                    except Exception:        # noqa: BLE001 — widget sans « text »
                        continue
        return None

    def widget_texte(texte, classe):
        for w in parcours(app.root):
            if not isinstance(w, classe):
                continue
            try:
                if str(w.cget("text")) == texte:
                    return w
            except Exception:                # noqa: BLE001
                continue
        return None

    # ---------------------------------------------------------------- [1] curseurs
    print()
    print("=" * 78)
    print("[1] CURSEURS — coût d'un geste (un rappel par pixel de souris)")
    print("=" * 78)
    doc["curseurs"] = []
    for texte, cible in (
            ("Gamma (les 2 moteurs)", 1.45),
            ("Saturation (globale)", 1.35),
            ("Saturation rouge", 1.30),
            ("Luminosité du fond du ciel", 0.21),
            ("Coupure du bruit (k·σ sous le fond)", 3.3),
            ("Black point", 0.02)):
        s = curseur(texte)
        if s is None:
            print(f"  (absent) {texte}")
            continue
        origine = float(s.get())
        etat = {"i": 0}

        def pas_glissement(lo=origine, hi=cible, etat=etat, s=s):
            """UN pas de souris PENDANT un glissement (P5 : ne calcule RIEN)."""
            etat["i"] ^= 1
            s._debut_glissement()
            s.set(hi if etat["i"] else lo)
            s._fin_glissement()

        def glissement_complet(lo=origine, hi=cible, etat=etat, s=s):
            """Le MÊME pas + l'aperçu du RELÂCHEMENT (ce que vit l'utilisateur)."""
            etat["i"] ^= 1
            s._debut_glissement()
            s.set(hi if etat["i"] else lo)
            s._fin_glissement()
            root.update()                 # traite l'`after_idle` du relâchement

        brut = mesure(texte + " (pas de glissement)", pas_glissement)
        etat["i"] = 0
        total = mesure(texte + " (glissement + relâchement)", glissement_complet)
        s.set(origine)                        # état RENDU (hors mesure)
        app._forcer_rendu_curseur(s)
        root.update()
        ligne = {"curseur": texte,
                 "pas_glissement_ms": brut["med_ms"],
                 "apercu_relachement_ms": total["med_ms"],
                 "glissement_200px_ms": round(
                     glissement_ms(brut["med_ms"]) + total["med_ms"], 1)}
        doc["curseurs"].append(ligne)
        print(f"  {texte:40s} pas {brut['med_ms']:6.3f} ms · "
              f"glissement + relâchement {total['med_ms']:6.1f} ms · "
              f"glissement 200 px ≈ {ligne['glissement_200px_ms']:6.0f} ms")

    # ------------------------------------------------------------------- [2] aperçu
    print()
    print("=" * 78)
    print("[2] APERÇU — décomposition (histogrammes contre rendu)")
    print("=" * 78)
    DECOMP["hist_ms"].clear()
    DECOMP["show_ms"].clear()
    avec_hist = mesure("_refresh_preview(hist=True)",
                       lambda: app._refresh_preview(hist=True), rep=max(3, n // 2))
    hist_ms = (round(statistics.median(DECOMP["hist_ms"]), 1)
               if DECOMP["hist_ms"] else None)
    show_avec = (round(statistics.median(DECOMP["show_ms"]), 1)
                 if DECOMP["show_ms"] else None)
    DECOMP["hist_ms"].clear()
    DECOMP["show_ms"].clear()
    sans_hist = mesure("_refresh_preview(hist=False)",
                       lambda: app._refresh_preview(hist=False), rep=max(3, n // 2))
    show_sans = (round(statistics.median(DECOMP["show_ms"]), 1)
                 if DECOMP["show_ms"] else None)
    doc["apercu"] = {"avec_hist_ms": avec_hist["med_ms"],
                     "sans_hist_ms": sans_hist["med_ms"],
                     "histogrammes_ms": hist_ms,
                     "dessin_ms": show_avec}
    print(f"  image + histogrammes : {avec_hist['med_ms']:6.1f} ms  "
          f"(histogrammes {hist_ms} ms, dessin {show_avec} ms)")
    print(f"  image seule          : {sans_hist['med_ms']:6.1f} ms  "
          f"(dessin {show_sans} ms)")

    # ---------------------------------------------------------- [2 bis] échelle
    print()
    print("=" * 78)
    print("[2 bis] ÉCHELLE — même aperçu, plusieurs tailles (le coût suit les PIXELS)")
    print("=" * 78)
    doc["echelle"] = []
    for txt in [t for t in str(echelles or "").replace(";", ",").split(",")
                if t.strip()]:
        tw, th = lire_taille(txt)
        app.last_show = image_factice(th, tw)
        root.update()
        d = mesure(f"aperçu {tw}×{th}",
                   lambda: app._refresh_preview(hist=True),
                   rep=max(3, n // 2), suivi=False)
        doc["echelle"].append({"taille": f"{tw}x{th}",
                               "mpx": round(tw * th / 1e6, 2),
                               "med_ms": d["med_ms"]})
        print(f"  {tw}×{th} ({tw * th / 1e6:5.2f} Mpx) : aperçu complet "
              f"{d['med_ms']:7.1f} ms")
    app.last_show = image_factice(lh, lw)      # retour à la taille de référence
    root.update()

    # -------------------------------------------------------------------- [3] boucle
    print()
    print("=" * 78)
    print(f"[3] BOUCLE D'INTERFACE — coût de _tick_corps "
          f"(budget {BUDGET_TICK_MS:.0f} ms)")
    print("=" * 78)
    tick = mesure("_tick_corps", app._tick_corps, rep=max(10, n * 4))
    pct = round(100.0 * tick["med_ms"] / BUDGET_TICK_MS, 1)
    doc["tick"] = {"med_ms": tick["med_ms"], "max_ms": tick["max_ms"],
                   "budget_pct": pct}
    print(f"  _tick_corps : {tick['med_ms']:7.3f} ms (max {tick['max_ms']:6.3f}) "
          f"→ {pct:.1f} % du budget de {BUDGET_TICK_MS:.0f} ms")


    # --------------------------------------------------------------------- [4] cases
    print()
    print("=" * 78)
    print("[4] CASES À COCHER — clic réel (invoke) contre var.set nu")
    print("=" * 78)
    doc["cases"] = []
    for texte, attr in (
            ("Neutraliser la couleur du fond (après étirement)", "var_vl_neutre"),
            ("Auto-stretch STF (fond calé sur la cible)", "var_auto"),
            ("PNG annoté à côté du FITS", "var_annoter_sauvegarde")):
        chk = widget_texte(texte, ttk.Checkbutton)
        var = getattr(app, attr, None)
        if chk is None or var is None:
            print(f"  (absent) {texte}")
            continue
        avant = bool(var.get())
        rep_nu = max(5, n)
        COMPTES["preview"] = 0
        nu = mesure(texte + " (var.set nu)",
                    lambda v=var: v.set(not bool(v.get())), rep=rep_nu)
        vus_nu = round(COMPTES["preview"] / rep_nu, 2)   # par appel
        var.set(avant)                        # état rendu (hors mesure)
        root.update()
        rep_clic = max(3, n // 2)
        COMPTES["preview"] = 0
        clic = mesure(texte, chk.invoke, rep=rep_clic)
        vus_clic = round(COMPTES["preview"] / rep_clic, 2)   # par clic
        chk.invoke()                          # retour à l'état initial
        root.update()
        doc["cases"].append({"case": texte, "set_nu_ms": nu["med_ms"],
                             "invoke_ms": clic["med_ms"],
                             "previews_set_nu": vus_nu,
                             "previews_invoke": vus_clic})
        print(f"  {texte[:44]:44s} var.set {nu['med_ms']:5.2f} ms "
              f"({vus_nu} aperçu) · invoke {clic['med_ms']:6.1f} ms "
              f"({vus_clic} aperçu)")

    # -------------------------------------------------------------------- [5] listes
    print()
    print("=" * 78)
    print("[5] LISTES DÉROULANTES — repeuplement et sélection")
    print("=" * 78)
    doc["listes"] = []
    cbs = getattr(app, "_spcc_cbs", {}) or {}
    spcc_actif = bool(getattr(app, "var_spcc", None) is not None
                      and app.var_spcc.get())
    for cle, cb in cbs.items():
        valeurs = list(cb.cget("values") or [])
        if not valeurs:
            print(f"  SPCC « {cle} » : liste VIDE (base absente)")
            doc["listes"].append({"liste": f"spcc:{cle}", "n_valeurs": 0})
            continue
        repeuplement = mesure(
            f"spcc:{cle} (config)",
            lambda cb=cb, v=valeurs: cb.config(values=v), rep=max(3, n // 2))
        actuel = str(cb.get())
        autre = valeurs[0] if valeurs[0] != actuel else valeurs[-1]
        selection = mesure(
            f"spcc:{cle} (sélection)",
            lambda cb=cb, v=autre: (cb.set(v), app._on_spcc_profil()),
            rep=max(3, n // 2))
        if actuel:
            cb.set(actuel)                    # état rendu, hors mesure
            app._on_spcc_profil()
        doc["listes"].append({"liste": f"spcc:{cle}", "n_valeurs": len(valeurs),
                              "repeuplement_ms": repeuplement["med_ms"],
                              "selection_ms": selection["med_ms"],
                              "spcc_active": spcc_actif})
        print(f"  SPCC « {cle:7s} » {len(valeurs):4d} valeurs · "
              f"repeuplement {repeuplement['med_ms']:6.1f} ms · "
              f"sélection {selection['med_ms']:6.1f} ms"
              + ("" if spcc_actif else "  (SPCC inactive : sélection sans effet)"))

    for attribut, etiquette, methode in (
            ("cb_ref_refresh", "Fréquence de référence", "_on_ref_refresh"),
            ("cb_fenetre", "Fenêtre de rejet", "_on_rejet")):
        cb = getattr(app, attribut, None)
        if cb is None:
            continue
        valeurs = list(cb.cget("values") or [])
        if not valeurs:
            continue
        actuel = str(cb.get())
        autre = valeurs[0] if valeurs[0] != actuel else valeurs[-1]
        d = mesure(f"{attribut} (sélection)",
                   lambda cb=cb, v=autre, m=methode:
                   (cb.set(v), getattr(app, m)()), rep=max(3, n // 2))
        if actuel:
            cb.set(actuel)
            getattr(app, methode)()
        doc["listes"].append({"liste": etiquette, "n_valeurs": len(valeurs),
                              "selection_ms": d["med_ms"]})
        print(f"  {etiquette:24s} {len(valeurs):4d} valeurs · "
              f"sélection {d['med_ms']:6.1f} ms")


    # ------------------------------------------------------------------ [6] spinners
    print()
    print("=" * 78)
    print("[6] SPINNERS — un cran (le `set()` seul ne rappelle RIEN)")
    print("=" * 78)
    doc["spinners"] = []
    for attribut, methode in (("sp_fusion_ha_poids", "_on_fusion_ha"),
                              ("sp_fusion_ha_alpha", "_on_fusion_ha"),
                              ("sp_fusion_ha_q", "_on_fusion_ha"),
                              ("sp_lissage_halos", "_on_lissage_halos")):
        sp = getattr(app, attribut, None)
        rappel = getattr(app, methode, None)
        if sp is None or rappel is None:
            print(f"  (absent) {attribut}")
            continue
        origine = float(sp.get())
        cible = origine + 1.0
        nu = mesure(attribut + " (set nu)",
                    lambda sp=sp, v=cible: sp.set(v), rep=max(5, n))
        COMPTES["preview"] = 0
        complet = mesure(attribut + " (set + commande)",
                         lambda sp=sp, v=cible, f=rappel: (sp.set(v), f()),
                         rep=max(3, n // 2))
        vus = COMPTES["preview"]
        par_cran = round(vus / max(3, n // 2), 2)
        sp.set(origine)
        rappel()
        doc["spinners"].append({"spinner": attribut, "set_nu_ms": nu["med_ms"],
                                "avec_commande_ms": complet["med_ms"],
                                "previews": par_cran})
        print(f"  {attribut:20s} set {nu['med_ms']:5.2f} ms · "
              f"set + commande {complet['med_ms']:6.1f} ms ({par_cran} aperçu)")

    # --------------------------------------------------------------- [7] visibilité
    print()
    print("=" * 78)
    print("[7] VISIBILITÉ DES CADRES — pack/forget à chaque changement de source")
    print("=" * 78)
    doc["visibilite"] = []
    PF = {"pack": 0, "forget": 0}
    _pack0, _forget0 = tk.Pack.pack, tk.Pack.pack_forget

    def pack_compte(self, *a, **k):
        PF["pack"] += 1
        return _pack0(self, *a, **k)

    def forget_compte(self, *a, **k):
        PF["forget"] += 1
        return _forget0(self, *a, **k)

    tk.Pack.pack = pack_compte            # pyright: ignore
    tk.Pack.pack_forget = forget_compte   # pyright: ignore
    source_origine = app.var_source.get()
    try:
        for src in SOURCES:
            PF["pack"] = PF["forget"] = 0
            app.var_source.set(src)
            d = mesure(f"visibilité [{src[:26]}]", app._maj_visibilite_cadres,
                       rep=max(3, n // 2))
            doc["visibilite"].append({"source": src, "med_ms": d["med_ms"],
                                      "max_ms": d["max_ms"],
                                      "pack": PF["pack"],
                                      "forget": PF["forget"]})
            print(f"  {src[:36]:36s} {d['med_ms']:6.1f} ms · "
                  f"{PF['pack']:3d} pack · {PF['forget']:3d} forget")
        app.var_source.set(source_origine)
        app._maj_visibilite_cadres()
        root.update()
    finally:
        tk.Pack.pack = _pack0             # pyright: ignore
        tk.Pack.pack_forget = _forget0    # pyright: ignore


    # ------------------------------------------------------------------- [8] rafale
    print()
    print("=" * 78)
    print("[8] RAFALE — glissement d'une seconde AVEC la boucle d'interface ACTIVE")
    print("=" * 78)
    ticks = {"n": 0, "t": []}
    corps0 = ui.App._tick_corps

    def corps(self, *a, **k):
        ticks["n"] += 1
        ticks["t"].append(time.perf_counter())
        return corps0(self, *a, **k)

    ui.App._tick_corps = corps            # pyright: ignore
    doc["rafale"] = {}
    try:
        del app._planifier_tick           # rend la VRAIE boucle (attribut masqué)
        app._tick_id = None
        app._planifier_tick(30)
        root.update()
        s = curseur("Gamma (les 2 moteurs)")
        if s is None:
            print("  (curseur gamma introuvable : rafale non concluante)")
        else:
            n_pas = 60
            COMPTES["preview"] = 0
            t0 = time.perf_counter()
            s._debut_glissement()        # P5 : le glissement NE CALCULE RIEN
            for i in range(n_pas):
                s.set(1.0 + 0.02 * (i % 20))
                root.update()
                time.sleep(0.016)         # ~60 Hz de souris
            s._fin_glissement()          # UN aperçu, au relâchement
            root.update()
            dt = time.perf_counter() - t0
            apercus = COMPTES["preview"]
            attendus = dt / (BUDGET_TICK_MS / 1000.0)
            ecarts = [(ticks["t"][i + 1] - ticks["t"][i]) * 1000.0
                      for i in range(len(ticks["t"]) - 1)]
            ecart_max = round(max(ecarts), 1) if ecarts else None
            doc["rafale"] = {"duree_s": round(dt, 2), "pas": n_pas,
                             "pas_ms": round(dt / n_pas * 1000.0, 1),
                             "apercus": apercus,
                             "ticks_obtenus": ticks["n"],
                             "ticks_attendus": int(attendus),
                             "ecart_max_ms": ecart_max}
            print(f"  {n_pas} pas de souris en {dt:.2f} s "
                  f"({dt / n_pas * 1000.0:.0f} ms par pas) · "
                  f"{apercus} aperçu(s) au total · "
                  f"{ticks['n']} battements obtenus pour {int(attendus)} "
                  f"attendus · écart max {ecart_max} ms")
    finally:
        ui.App._tick_corps = corps0       # pyright: ignore
        try:
            if getattr(app, "_tick_id", None) is not None:
                root.after_cancel(app._tick_id)
        except Exception:                 # noqa: BLE001
            pass
        app._tick_id = None
        app._planifier_tick = lambda delai=30: None    # pyright: ignore

    # ------------------------------------------------------------------ [9] synthèse
    print()
    print("=" * 78)
    print(f"[9] SYNTHÈSE — au-delà de {seuil:.2f} s (le Guet abaissé)")
    print("=" * 78)
    blocages.sort(key=lambda c: c[0], reverse=True)
    depassements = [nom for ms, nom in blocages if ms > seuil * 1000.0]
    doc["blocages"] = [{"operation": nom, "max_ms": ms}
                       for ms, nom in blocages[:10]]
    doc["au_dela_seuil"] = len(depassements)
    doc["operations_au_dela"] = depassements
    print(f"  pire blocage observé : {blocages[0][1] if blocages else '—'} "
          f"({blocages[0][0] if blocages else 0} ms)")
    print(f"  opérations au-delà de {seuil:.2f} s : {len(depassements)}"
          + (f" → {', '.join(depassements[:6])}" if depassements else ""))
    if not depassements:
        print("  → aucun gel UNIQUE au-delà du seuil : la gêne éventuelle vient "
              "de l'EMPILEMENT des gestes, pas d'un blocage isolé")
    charge = max((l["pas_glissement_ms"] for l in doc["curseurs"]), default=0.0)
    # 60 pas/s × coût d'un pas (ms) ÷ 10 = % d'un cœur nécessaire.
    doc["charge_souris_60hz_pct"] = round(charge * 60.0 / 10.0, 2)
    print(f"  à 60 Hz de souris, le curseur le plus lourd demanderait "
          f"{doc['charge_souris_60hz_pct']:.2f} % d'un cœur pour suivre "
          f"({charge:.3f} ms par pas — P5 : plus AUCUN calcul pendant le geste)")
    pire = max((l["glissement_200px_ms"] for l in doc["curseurs"]), default=0.0)
    doc["glissement_200px_pire_ms"] = pire
    print(f"  un glissement de 200 px coûte au pire {pire:.0f} ms "
          f"(200 pas + UN aperçu au relâchement)")

    root.destroy()
    return doc


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=5,
                   help="répétitions par mesure (médiane ; défaut 5)")
    p.add_argument("--seuil", type=float, default=SEUIL_DEFAUT,
                   help=f"seuil de signalement en secondes (défaut "
                        f"{SEUIL_DEFAUT} = le Guet abaissé du lot 5)")
    p.add_argument("--taille", default="auto",
                   help="taille de l'APERÇU à mesurer (défaut « auto » = "
                        "1600x1200, le plafond réel de l'application ; "
                        "ex. 1600x900, 1920x1080)")
    p.add_argument("--fenetre", default="zoomed",
                   help="taille de la FENÊTRE (défaut « zoomed » = plein écran, "
                        "24 pouces en 1920×1080 ; « normal » ou « 1280x800 »)")
    p.add_argument("--tailles", default=ECHELLES,
                   help=f"tailles de la courbe [2 bis] (défaut {ECHELLES} ; "
                        "« aucune » pour la sauter)")
    p.add_argument("--json", default=SORTIE, help="fichier de sortie JSON")
    p.add_argument("--sans-json", action="store_true",
                   help="ne rien écrire sur disque")
    p.add_argument("--autotest", action="store_true",
                   help="vérifie la mécanique du banc, sans écran")
    a = p.parse_args(argv)
    if a.autotest:
        print("[autotest] mécanique du banc de mesure P5")
        return 0 if autotest() else 1
    echelles = "" if str(a.tailles).strip().lower() in ("aucune", "non", "off") \
        else a.tailles
    try:
        doc = mesurer(a.n, a.seuil, a.taille, a.fenetre, echelles)
    except Exception as exc:                  # noqa: BLE001
        print(f"\n[banc] mesure IMPOSSIBLE : {exc}")
        print("[banc] (un affichage est nécessaire : Tk doit ouvrir une fenêtre)")
        return 2
    if not a.sans_json:
        try:
            with open(a.json, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
            print(f"\n[JSON] {a.json}")
        except OSError as exc:      # un JSON raté n'invalide pas la mesure
            print(f"\n[JSON] échec de l'écriture ({exc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())


