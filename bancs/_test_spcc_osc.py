# -*- coding: utf-8 -*-
"""Banc jalon 58 bis (v2.40.0) : SPCC d'une image COULEUR (capteur OSC).

Constats d'Alain du 28/09/2026, sur ses brutes OSC (Uranus-C Pro, mode
dossier) : « la case SPCC dit que c'est que pour du mono multibande, alors que
SPCC fonctionne en images couleurs dans Siril — il faut juste lui dire que
c'est un capteur couleur et le choisir ».

Ce que ce banc vérifie :
  [1] la base expose les capteurs/filtres COULEUR (listes dédupliquées) et
      `capteur_osc` / `filtre_osc` les reconnaissent (un capteur MONO est
      refusé comme capteur OSC) ;
  [2] `reponses_osc` : trois réponses DISTINCTES, égales à la QE seule quand
      il n'y a pas de filtre (comme le « No filter » de Siril) ;
  [3] `coherence_osc` : le pendant couleur de `coherence_bandes` (qui, lui,
      EXIGE trois filtres distincts — impossible en OSC, où un seul filtre
      couvre les trois bandes) ;
  [4] BOUT EN BOUT : sur une image couleur synthétique bâtie avec les réponses
      OSC réelles, `coefficients_spcc` retrouve les gains par canal
      instrumentaux (vérité connue) ;
  [5] l'INTERFACE : le type « Couleur (OSC) » repeuple les sélecteurs (un seul
      filtre pour les trois bandes, lignes G/B grisées) et l'état est cohérent ;
  [6] l'empilement d'une source couleur reçoit bien les gains (`LiveStacker`),
      et l'empilement BRUT (corrections=False) n'est jamais touché.

Exécution : python bancs/_test_spcc_osc.py
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import sys

import numpy as np

from avastack.catalogues import WcsTan
from avastack.processing import spcc as SP

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


H, W = 512, 512
ECH_DEG = 0.001
RA0, DEC0 = 10.68, 41.27


def wcs_du_banc():
    return WcsTan((RA0, DEC0), (W / 2.0, H / 2.0),
                  [[-ECH_DEG, 0.0], [0.0, ECH_DEG]], (H, W))


def corps_noir(wl_nm, temperature):
    h, c, k = 6.62607015e-34, 2.99792458e8, 1.380649e-23
    lam = np.asarray(wl_nm, float) * 1e-9
    return (1.0 / lam ** 5) / (np.expm1(h * c / (lam * k * temperature)))


def troupeau(graine=58, n=60):
    rng = np.random.default_rng(graine)
    xs, ys = [], []
    for iy in range(3, H - 3, 48):
        for ix in range(3, W - 3, 48):
            if rng.random() < 0.75:
                xs.append(ix + rng.uniform(-6, 6))
                ys.append(iy + rng.uniform(-6, 6))
    pos = np.column_stack([xs[:n], ys[:n]])
    return pos, rng.uniform(3000.0, 12000.0, len(pos))


def image_depuis(pos, flux, bruit=1.0, graine=7):
    rng = np.random.default_rng(graine)
    img = np.full((H, W), 100.0)
    yy, xx = np.mgrid[0:H, 0:W]
    sig = 1.1
    for (x, y), f in zip(pos, flux):
        x0, x1 = max(0, int(x) - 8), min(W, int(x) + 9)
        y0, y1 = max(0, int(y) - 8), min(H, int(y) + 9)
        if x1 <= x0 or y1 <= y0:
            continue
        d2 = (xx[y0:y1, x0:x1] - x) ** 2 + (yy[y0:y1, x0:x1] - y) ** 2
        img[y0:y1, x0:x1] += (f / (2.0 * np.pi * sig ** 2)
                              * np.exp(-d2 / (2.0 * sig ** 2)))
    if bruit > 0.0:
        img = img + rng.normal(0.0, bruit, img.shape)
    return img


# ===================== [1] base : capteurs/filtres COULEUR ===================
print("[1] base SPCC : listes COULEUR et reconnaissance du capteur")
base_ok = bool(SP.base_presente())
noms = SP.noms_base()
print(f"      base Siril installée : {base_ok}")
verifie(set(("osc_capteurs", "osc_filtres")) <= set(noms),
        "noms_base() expose les listes couleur (osc_capteurs/osc_filtres)")
if base_ok:
    caps, fils = noms["osc_capteurs"], noms["osc_filtres"]
    verifie(len(caps) > 0 and len(fils) > 0,
            f"{len(caps)} capteurs couleur, {len(fils)} filtres couleur")
    verifie(len(caps) == len(set(caps)) and len(fils) == len(set(fils)),
            "aucun doublon (la base contient UNE entrée par canal couleur)")
    verifie("Sony IMX585" in caps and "No filter" in fils,
            f"capteurs/filtres d'usage présents (IMX585 : "
            f"{'Sony IMX585' in caps}, « No filter » : {'No filter' in fils})")
    modele, canaux = SP.capteur_osc("Sony IMX585")
    verifie(modele is not None and set(canaux) == {"RED", "GREEN", "BLUE"},
            f"capteur_osc(\"Sony IMX585\") → {modele}, canaux "
            f"{sorted(canaux)}")
    verifie(SP.capteur_osc("Sony IMX585 Red")[0] is not None,
            "le nom d'un CANAL est aussi accepté (« Sony IMX585 Red »)")
    verifie(SP.capteur_osc("Generic mono")[0] is None,
            "un capteur MONO n'est PAS pris pour un capteur couleur")
    verifie(SP.capteur_osc("caméra de l'espace")[0] is None,
            "un nom inconnu est refusé (aucune courbe inventée)")
    nom_f, _f = SP.filtre_osc("No filter")
    verifie(nom_f == "No filter", f"filtre_osc(\"No filter\") → {nom_f}")
else:
    print("      (base absente : reconnaissance sautée)")

# ===================== [2] réponses R/G/B du capteur OSC ====================
print("[2] reponses_osc : trois bandes distinctes, filtre optionnel")
if base_ok:
    rep, noms_f, err = SP.reponses_osc("Sony IMX585", "")
    verifie(rep is not None and err == "",
            f"réponses calculées sans filtre ({err or 'ok'})")
    if rep is not None:
        a = np.vstack(rep)
        verifie(a.shape == (3, SP.XPSAMPLED_LEN),
                f"trois courbes sur la grille spectrale {a.shape}")
        verifie(a.std(axis=0).max() > 1e-6,
                "les trois canaux sont DISTINCTS (sinon aucune couleur)")
        # Sans filtre, la réponse est la QE seule : on la compare à la QE brute
        _m, cap = SP.capteur_osc("Sony IMX585")
        qe = SP.reponse_canal(SP._courbe_de(cap["RED"]), None)
        verifie(np.allclose(rep[0], qe, rtol=1e-12),
                "réponse sans filtre = QE du canal (comme « No filter »)")
        rep2, _n2, err2 = SP.reponses_osc("Sony IMX585", "UV/IR Block")
        verifie(rep2 is not None and not np.allclose(rep2[0], rep[0]),
                f"un vrai filtre CHANGE les réponses ({err2 or 'ok'})")
        verifie(SP.reponses_osc("Sony IMX585",
                                "filtre qui n'existe pas")[0] is None,
                "filtre inconnu → refus explicite (jamais un calcul muet)")
    verifie(SP.reponses_osc("Generic mono", "No filter")[0] is None,
            "capteur mono passé à reponses_osc → refus (chemin OSC seulement)")
else:
    print("      (base absente : réponses sautées)")

# ===================== [3] cohérence couleur ================================
print("[3] coherence_osc : le pendant couleur de coherence_bandes")
if base_ok:
    verifie(SP.coherence_osc("Sony IMX585", "No filter") == [],
            "capteur couleur + LPF valides → aucun avertissement")
    av = SP.coherence_osc("Generic mono", "No filter")
    verifie(len(av) == 1 and "OSC" in av[0],
            f"capteur mono en mode OSC → avertissement "
            f"(« {av[0] if av else ''} »)")
    # ET la preuve que le contrôle MONO aurait refusé ce cas légitime :
    av_mono = SP.coherence_bandes(["No filter", "No filter", "No filter"])
    verifie(av_mono and "répétés" in av_mono[0],
            f"coherence_bandes refuse un même filtre sur 3 bandes "
            f"(« {av_mono[0] if av_mono else ''} ») — d'où un contrôle "
            f"SPÉCIFIQUE en OSC")
else:
    print("      (base absente : cohérence sautée)")


# ===================== [4] BOUT EN BOUT sur une image COULEUR ===============
print("[4] coefficients_spcc DE BOUT EN BOUT en mode COULEUR (OSC)")
pos, temps = troupeau()
sp = np.vstack([corps_noir(SP.GRILLE_WL, t) for t in temps])
gains_vrais = np.array([0.7, 1.0, 1.3])      # vérité à retrouver (R/G, B/G)
wcs = wcs_du_banc()
canaux = None


def catalogue_factice(wcs_, forme, dossier=None, limmag=None, spectres=False):
    ra, dec = wcs_.vers_radec(pos)
    return ({"ra": np.asarray(ra, float).ravel(),
             "dec": np.asarray(dec, float).ravel(),
             "g": 10.0 + np.linspace(0.0, 3.0, len(pos)), "flux": sp},
            f"{len(pos)} étoiles synthétiques")


def fabrique(rep_):
    """Image couleur synthétique : flux = prédiction × gain par canal ×
    luminosité, luminosité INDÉPENDANTE de la couleur (sinon toutes les étoiles
    ont la même magnitude dans chaque bande, le filtre de saturation en écarte
    la quasi-totalité et le test ne mesure plus rien — piège du 24/09/2026)."""
    pred = SP.flux_par_canal(SP.photons(sp), rep_)
    rng = np.random.default_rng(58)
    lum = 10.0 ** (-0.4 * rng.uniform(0.0, 5.0, len(pos)))
    flux = pred * gains_vrais[None, :] * lum[:, None]
    amp = flux / np.max(flux) * 1.0e5
    return {"R": image_depuis(pos, amp[:, 0]),
            "G": image_depuis(pos, amp[:, 1]),
            "B": image_depuis(pos, amp[:, 2])}


if base_ok:
    rep_osc, _nf, err_osc = SP.reponses_osc("Sony IMX585", "No filter")
    canaux = fabrique(rep_osc)
    ses = SP.SessionSpcc(catalogue=catalogue_factice)
    res, msg = ses.mesurer(
        canaux, wcs, "Sony IMX585",
        {"R": "No filter", "G": "No filter", "B": "No filter"},
        "Average Spiral Galaxy", forme=(H, W), mode="osc")
    k, d = ses.coefficients, ses.diag
    print(f"        diag : {d.get('erreur') or 'ok'} ; mode {d.get('mode')} ; "
          f"n={d.get('n_regression')} ; pentes "
          f"{d.get('b_rg', float('nan')):.4f} / "
          f"{d.get('b_bg', float('nan')):.4f} ; "
          f"K {np.round(k, 4) if k is not None else None}")
    verifie(k is not None and ses.valide,
            f"mesure OSC de bout en bout réussie ({str(msg)[:60]}…)")
    verifie(abs(d.get("b_rg", 0.0) - gains_vrais[0]) < 0.03,
            f"pente R/G retrouvée = gain vrai 0,70 "
            f"(obtenu {d.get('b_rg'):.4f})")
    verifie(abs(d.get("b_bg", 0.0) - gains_vrais[2]) < 0.03,
            f"pente B/G retrouvée = gain vrai 1,30 "
            f"(obtenu {d.get('b_bg'):.4f})")
    verifie(len(d.get("filtres", ())) == 3
            and len(set(d.get("filtres", ()))) == 3,
            f"les trois bandes portent leur nom "
            f"(« {d.get('filtres', [''])[0]} »)")
    # Le MÊME capteur en mode MONO doit rester possible (la base décrit les
    # deux versions) : c'est la valeur du paramètre `mode` qui tranche.
    k_mono, d_mono = SP.coefficients_spcc(
        canaux, wcs, "Sony IMX585",
        {"R": "QHYCCD MiniCam8M Red", "G": "QHYCCD MiniCam8M Green",
         "B": "QHYCCD MiniCam8M Blue"}, "Average Spiral Galaxy",
        catalogue=catalogue_factice, mode="mono")
    verifie(d_mono.get("mode") is None
            and (k_mono is not None or d_mono.get("erreur")),
            "mode=\"mono\" forcé : chemin mono (avec filtres mono), "
            "aucune exception")
    # Détection AUTOMATIQUE (sans `mode`) : c'est le FILTRE qui tranche.
    verifie(SP.mode_bandes("Sony IMX585",
                           {"R": "No filter", "G": "No filter",
                            "B": "No filter"}) == "osc",
            "mode_bandes : même filtre OSC sur 3 canaux → « osc »")
    verifie(SP.mode_bandes("Sony IMX585",
                           {"R": "QHYCCD MiniCam8M Red",
                            "G": "QHYCCD MiniCam8M Green",
                            "B": "QHYCCD MiniCam8M Blue"}) == "mono",
            "mode_bandes : trois filtres MONO → « mono » (même nom de capteur)")
    verifie(SP.mode_bandes("Generic mono", {"R": "No filter"}) == "mono",
            "mode_bandes : capteur mono → « mono », jamais OSC")
else:
    print("      (base absente : bout en bout sauté)")


# ===================== [5] INTERFACE : choix du type de capteur =============
print("[5] interface : « Couleur (OSC) » repeuple les sélecteurs et grise G/B")
try:
    import tkinter as tk

    import avastack.ui.app as ui
    # Banc hermétique : configuration VIDE (cf. bancs 19/54/56/58), sinon la
    # config.json de la machine fausserait les valeurs par défaut.
    _cfg_sauve = dict(ui.CONFIG)
    ui.CONFIG.clear()
    root = tk.Tk()
    root.withdraw()
    app = ui.App(root)
    verifie(getattr(app, "var_spcc_type", None) is not None
            and app.var_spcc_type.get() == app.SPCC_TYPE_MONO,
            f"type « {app.SPCC_TYPE_MONO} » par défaut (comportement "
            f"historique : le mono multi-bandes)")
    verifie(set(app._spcc_cbs) == {"capteur", "fr", "fg", "fb", "blanc"},
            f"sélecteurs créés : {sorted(app._spcc_cbs)}")
    if base_ok:
        verifie(set(app._spcc_cbs["capteur"].cget("values")) ==
                set(noms["capteur"]),
                f"sélecteur capteur = liste MONO "
                f"({len(noms['capteur'])} entrées)")
        app.var_spcc_type.set(app.SPCC_TYPE_OSC)
        app._on_spcc_type()
        verifie(app._spcc_osc() is True, "type basculé : _spcc_osc() → True")
        verifie(set(app._spcc_cbs["capteur"].cget("values")) ==
                set(noms["osc_capteurs"]),
                f"sélecteur capteur = liste COULEUR "
                f"({len(noms['osc_capteurs'])} entrées) — la liste mono est "
                f"abandonnée")
        verifie(set(app._spcc_cbs["fr"].cget("values")) ==
                set(noms["osc_filtres"]),
                "sélecteur de filtre = liste COULEUR (osc_filters)")
        verifie(app._spcc_lbls["capteur"].cget("text") == "Capteur OSC :"
                and app._spcc_lbls["fr"].cget("text") == "Filtre (OSC) :"
                and app._spcc_lbls["fg"].cget("text") == "Filtre (OSC) :",
                "libellés renommés (un seul filtre pour les trois bandes)")
        verifie("disabled" in app._spcc_cbs["fg"].state()
                and "disabled" in app._spcc_cbs["fb"].state(),
                "lignes G et B grisées (le filtre est COMMUN : rien à y "
                "choisir)")
        f_r = app._spcc_vars["fr"].get()
        verifie(f_r and f_r == app._spcc_vars["fg"].get()
                == app._spcc_vars["fb"].get(),
                f"les trois canaux portent le MÊME filtre (« {f_r} »)")
        verifie("no filter" in f_r.lower() or "full spectrum" in f_r.lower(),
                f"défaut OSC = référence « sans filtre » (« {f_r} ») : jamais un "
                f"vrai LPF appliqué en silence à une brute sans filtre")
        cap, filtres, blanc = app._spcc_profils()
        verifie(cap == app._spcc_vars["capteur"].get()
                and set(filtres) == {"R", "G", "B"}
                and len(set(filtres.values())) == 1 and blanc,
                f"profils lus par le worker : capteur « {cap} », filtres "
                f"{sorted(set(filtres.values()))}, blanc « {blanc} »")
        # Changer de type invalide la mesure précédente (bandes différentes).
        app.spcc.coefficients = np.array([0.9, 1.0, 1.1])
        app.spcc.diag = {"capteur": "x", "b_rg": 1.0, "b_bg": 1.0,
                         "n_regression": 10}
        app.var_spcc_type.set(app.SPCC_TYPE_MONO)
        app._on_spcc_type()
        verifie(not app.spcc.valide and app.spcc.gains() == {},
                "retour en mono : la mesure couleur est oubliée "
                "(des coefficients d'autres bandes seraient faux)")
        # Persistance du type (une config qui ne le garderait pas relancerait
        # en mono à chaque ouverture — c'est le constat d'Alain).
        sauvegardes = []
        ui.sauver_config = lambda c: sauvegardes.append(dict(c))
        app.var_spcc_type.set(app.SPCC_TYPE_OSC)
        app._on_spcc_type()
        app._sauver_config_app()
        verifie(sauvegardes and sauvegardes[-1].get("spcc_type")
                == app.SPCC_TYPE_OSC
                and isinstance(sauvegardes[-1].get("spcc_fg"), str),
                f"config : type persisté (« "
                f"{sauvegardes[-1].get('spcc_type') if sauvegardes else '?'} »)")
    else:
        print("      (base absente : peuplement des sélecteurs non testé)")
    root.destroy()
    ui.CONFIG.update(_cfg_sauve)
except Exception as exc:            # Tk indisponible (session sans écran)
    print(f"  (UI non testée : {type(exc).__name__} : {exc})")

# ===================== [6] empilement d'une source COULEUR ==================
print("[6] LiveStacker : les gains R/G/B sont appliqués, le BRUT est préservé")
from avastack.processing.stacking import LiveStacker, _gains_canaux

st = LiveStacker((4, 3, 3))
frame = np.zeros((4, 3, 3), np.float32)
frame[..., 0] = 100.0            # R
frame[..., 1] = 200.0            # G
frame[..., 2] = 400.0            # B
for _ in range(3):
    st.add(frame)
brut = st.mean(corrections=False)
verifie(np.allclose(brut[..., 0], 100.0) and np.allclose(brut[..., 2], 400.0),
        "empilement BRUT inchangé (les sauvegardes linéaires restent brutes)")
st.gains = {"R": 2.0, "G": 1.0, "B": 0.5}
corr = st.mean()
verifie(np.allclose(corr[..., 0], 200.0, atol=1e-3)
        and np.allclose(corr[..., 1], 200.0, atol=1e-3)
        and np.allclose(corr[..., 2], 200.0, atol=1e-3),
        f"gains appliqués par CANAL : R×2, B×0,5 → les trois canaux à 200 "
        f"({float(corr[0, 0, 0])})")
st.gains = None
verifie(np.allclose(st.mean()[..., 0], 100.0),
        "sans gain posé (case SPCC décochée) : aucun effet, image intacte")
# Le canal doit être trouvé quelle que soit la disposition des axes.
verifie(np.allclose(_gains_canaux(np.ones((3, 2, 2)),
                                  {"R": 3.0, "G": 1.0, "B": 1.0})[0], 3.0),
        "disposition (C, H, W) gérée comme (H, W, C)")
verifie(np.asarray(_gains_canaux(np.ones((2, 2)),
                                 {"R": 2.0})).shape == (2, 2),
        "image MONO : traversée sans erreur (aucun gain inventé)")

# ============================== bilan =======================================
print()
print("BANC JALON 58 bis (SPCC couleur/OSC) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)
