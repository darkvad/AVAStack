# -*- coding: utf-8 -*-
"""TRACE PAR RÔLE de l'empilement — instrumentation du worker (chantier CAUSE AMONT).

POURQUOI CE MODULE (chantier CAUSE AMONT, étape ⑦, 17/10/2026) : les taches
rouges/bleues du LRGB ne sont portées par AUCUNE des cinq couches prises
isolément (mesuré : contrôle positif à +852…+2026 % sur les 200 étoiles
brillantes), et le combine est innocenté trois fois (runs 140/142/143). Ce qui
reste à expliquer n'est donc pas une DONNÉE, mais un ÉTAT D'EMPILEMENT : quelle
référence d'alignement était en vigueur, quels offsets en sont sortis, quels
pixels ont été rejetés et avec quel σ. Ces quatre faits n'étaient journalisés
NULLE PART — ce module les écrit.

MESURES PRODUITES (une ligne JSON par brute, plus une par référence posée) :
  · `reference` : à quel moment la référence d'alignement a été posée, PAR QUI
    (motif : initiale / auto / manuelle / repli / restack / Ha), depuis quel
    RÔLE (`role`), à quelle PROFONDEUR de ce rôle (`n`) et avec quelle
    empreinte (identifie le CONTENU de la référence, pas son nom) ;
  · `frame` : pour chaque brute vue par le worker — rôle, étape (empilée,
    refus d'alignement, refus du filtre défocus, ancre), empreinte de la brute,
    offsets/angle/échelle/méthode d'alignement, profondeur de CHAQUE rôle,
    rejets kappa-sigma CUMULÉS, et les statistiques de POIDS (`wsum/n`) et de σ
    temporel de la pile du rôle (p50/p90/p99, sur une grille décimée).

POURQUOI L'EMPREINTE : deux runs « sur les mêmes brutes » ne se comparent que
si l'on PROUVE que la brute est la même. L'empreinte porte sur une version
décimée (≤ 512 × 512) de l'image de travail : insensible au bruit de lecture
d'un nom de fichier, elle identifie le contenu — et elle rend appariable une
brute du rôle L d'un run avec la même brute lue par le rôle R d'un autre.

GARDE-FOUS (règles du dépôt) :
  · INACTIF PAR DÉFAUT : sans `ouvrir()` ni `AVASTACK_TRACE_ROLES`, toutes les
    fonctions rendent immédiatement — aucun calcul, aucune écriture, donc un
    comportement NUMÉRIQUEMENT IDENTIQUE À L'AVANT (un seul test de chaîne par
    frame) ;
  · JAMAIS D'EXCEPTION : journaliser est un service, pas une dépendance — une
    trace ratée ne doit pas faire échouer un empilement (même convention que
    `journal.py`) ;
  · TAILLE BORNÉE (`MAX_OCTETS`) : la trace s'arrête d'écrire au-delà, elle ne
    remplit pas le disque de travail ;
  · les CARTES (poids/σ/moyenne par rôle) sont une option SÉPARÉE
    (`exporter_cartes`) : ~34 Mo par carte en 8 Mpx, on ne les écrit que sur
    demande explicite.

UTILISATION (hors application, depuis un driveur de mesure) :
    from avastack.processing import trace_roles
    trace_roles.ouvrir(r"C:\\Astro\\test\\_trace", nom="145_143")
    ... (l'appli tourne) ...
    trace_roles.exporter_cartes(r"C:\\Astro\\test\\_trace", "145_143",
                                app.stacker.stackers)
    trace_roles.fermer()
ou, sans code : `AVASTACK_TRACE_ROLES=C:\\Astro\\test\\_trace` dans
l'environnement (le fichier est alors nommé `trace_roles_<horodatage>.jsonl`).

RIEN ICI NE MODIFIE LES EMPILEMENTS : on ne lit que `sum`, `sumsq`, `wsum`,
`n`, `rejected_total`, `cadre` — jamais d'écriture en place.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from typing import Any, Mapping

import numpy as np

# Nom de la variable d'environnement (précédent : AVASTACK_SANS_DIALOGUE).
ENV_DIR = "AVASTACK_TRACE_ROLES"
# Nom de fichier par défaut quand la trace est ouverte par l'environnement.
NOM_DEFAUT = "trace_roles"
# Au-delà, la trace cesse d'écrire (elle ne remplit jamais le disque de travail).
MAX_OCTETS = 64 << 20
# Pas de la grille décimée des statistiques par frame (poids et σ) : 4 → un
# pixel sur 16, soit ~500 k pixels sur 8,4 Mpx — les percentiles y sont
# stables et le coût par frame reste de l'ordre de quelques dizaines de ms.
PAS_STATS = 4
# Pas maximal de l'empreinte : ≤ 512 pas dans la plus grande dimension.
COTE_EMPREINTE = 512

_verrou = threading.Lock()
_actif: bool = False
_chemin: str | None = None
_octets: int = 0
_seq: int = 0                 # numéro de la dernière brute vue (0 = aucune)
_ref: dict[str, Any] | None = None   # dernière référence posée (inline)


# --------------------------------------------------------------------- outils
def _horodatage() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _f(v: Any, defaut: float | None = None) -> float | None:
    """→ float fini, ou `defaut` (jamais d'exception, jamais de NaN/inf en JSON)."""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return defaut
    return x if np.isfinite(x) else defaut


def _defaut_json(obj: Any) -> Any:
    """Repli `json.dumps` : un scalaire/tableau numpy devient du JSON (jamais d'échec)."""
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


def empreinte(img: Any) -> str:
    """Empreinte de CONTENU d'une image (décimée, 8 octets, hexadécimale).

    Deux brutes identiques — même lue par deux rôles, ou par deux runs — donnent
    la même empreinte ; deux brutes différentes la même empreinte est
    improbable (2⁶⁴). Le calcul porte sur au plus 512 pixels par côté :
    quelques millisecondes, même sur 8,4 Mpx.
    """
    try:
        a = np.asarray(img)
        if a.ndim == 3 and a.shape[0] <= 4 and a.shape[0] < a.shape[1]:
            pas = max(1, int(max(a.shape[1], a.shape[2])) // COTE_EMPREINTE)
            a = a[:, ::pas, ::pas]                    # (C, H, W)
        else:
            pas = max(1, int(max(a.shape[:2])) // COTE_EMPREINTE)
            a = a[::pas, ::pas]                       # (H, W) ou (H, W, C)
        v = np.ascontiguousarray(a, dtype=np.float32)
        return hashlib.blake2b(v.tobytes(), digest_size=8).hexdigest()
    except Exception:
        return ""


def profondeurs(app: Any) -> dict[str, int]:
    """{rôle: frames empilées} de l'empilement COURANT (mono → clé "mono")."""
    try:
        st = getattr(app, "stacker", None)
        if st is None:
            return {}
        if hasattr(st, "stackers"):
            return {str(r): int(getattr(s, "n", 0) or 0)
                    for r, s in st.stackers.items()}
        return {"mono": int(getattr(st, "n", 0) or 0)}
    except Exception:
        return {}


def pile_role(app: Any, role: Any) -> Any:
    """LiveStacker de `role` (ou l'empilement mono), None s'il n'existe pas."""
    try:
        st = getattr(app, "stacker", None)
        if st is None:
            return None
        if hasattr(st, "stackers"):
            return st.stackers.get(role) if role else None
        return st
    except Exception:
        return None


def cadre(app: Any) -> list[int] | None:
    """Cadre commun (intersection) en cours, ou None."""
    try:
        c = getattr(getattr(app, "stacker", None), "cadre", None)
        return [int(v) for v in c] if c else None
    except Exception:
        return None


# ------------------------------------------------------------------- ouverture
def ouvrir(dossier: str, nom: str = "") -> bool:
    """Ouvre (ou rouvre) la trace dans `dossier` → True si elle est active.

    `nom` = nom du fichier sans extension (défaut : `trace_roles`). Un fichier
    EXISTANT est REMPLACÉ : une trace est l'enregistrement d'UN run, pas un
    journal cumulatif (les runs se distinguent par leur nom, cf. `--tag` du
    driveur de mesure hors dépôt).
    """
    global _actif, _chemin, _octets, _seq, _ref
    try:
        dossier = str(dossier).strip()
        if not dossier:
            return False
        os.makedirs(dossier, exist_ok=True)
        base = (str(nom).strip() or NOM_DEFAUT)
        chemin = os.path.join(dossier, base + ".jsonl")
        with _verrou:
            _chemin = chemin
            _octets = 0
            _seq = 0
            _ref = None
            _actif = True
            try:
                if os.path.isfile(chemin):
                    os.remove(chemin)          # run neuf = trace neuve
            except OSError:
                with open(chemin, "w", encoding="utf-8"):
                    pass                       # au moins tronquer
        _ecrire({"type": "entete", "t": _horodatage(),
                 "version": _version(), "argv": list(sys.argv),
                 "cwd": os.getcwd(), "python": sys.version.split()[0],
                 "fichier": chemin})
        return True
    except Exception:
        _actif = False
        _chemin = None
        return False


def _version() -> str:
    """Version de l'application (import paresseux : ce module reste autonome)."""
    try:
        from .. import AVASTACK_VERSION
        return str(AVASTACK_VERSION)
    except Exception:
        return "?"


def actif() -> bool:
    """La trace écrit-elle ? (activée par `ouvrir`, ou par `AVASTACK_TRACE_ROLES`)."""
    global _actif
    if _actif:
        return True
    dossier = os.environ.get(ENV_DIR, "").strip()
    if not dossier:
        return False
    return ouvrir(dossier, "trace_roles_" + time.strftime("%Y%m%d_%H%M%S"))


def fermer() -> None:
    """Clôt la trace (écrit une ligne de fin). Idempotent, jamais d'exception."""
    global _actif, _chemin, _ref
    if _actif:
        _ecrire({"type": "fin", "t": _horodatage(), "seq": _seq})
    _actif = False
    _chemin = None
    _ref = None


# -------------------------------------------------------------------- écriture
def _ecrire(rec: Mapping[str, Any]) -> None:
    """Ajoute UNE ligne JSON à la trace (jamais d'exception, jamais de blocage)."""
    global _octets
    chemin = _chemin
    if not chemin:
        return
    try:
        ligne = json.dumps(dict(rec), ensure_ascii=False, default=_defaut_json)
        with _verrou:
            if _octets > MAX_OCTETS:
                return
            with open(chemin, "a", encoding="utf-8", errors="replace") as f:
                f.write(ligne + "\n")
            _octets += len(ligne) + 1
    except Exception:
        pass


# --------------------------------------------------------- statistiques de pile
def resume_pile(st: Any, pas: int = PAS_STATS) -> dict[str, Any]:
    """Poids et σ TEMPOREL de la pile d'un rôle, sur une grille décimée.

    POIDS : `wsum / n` — 1,0 = pixel gardé par TOUTES les frames du rôle ;
    < 1 = rejeté au moins une fois (le rejet kappa-sigma met un poids 0/1, il
    n'y a pas d'autre pondération dans `LiveStacker`). `poids_sous_pct` est donc
    la part des pixels COUVERTS qui ont perdu au moins une frame : c'est la
    signature cherchée derrière une tache (un pixel rejeté dans un run et pas
    dans l'autre).

    σ : écart-type TEMPOREL par pixel de la pile (`sqrt(sumsq/wsum − moyenne²)`),
    en unités de l'image linéaire. p50/p90/p99 disent si la couche est
    homogène ou si une zone porte un excès de bruit.

    Les pixels NON COUVERTS (`wsum == 0`, bords de recalage) sont EXCLUS : les
    inclure écraserait les percentiles par des zéros. → {} si rien à mesurer.
    """
    try:
        if st is None:
            return {}
        n = int(getattr(st, "n", 0) or 0)
        if n <= 0:
            return {}
        w = getattr(st, "wsum", None)
        s = getattr(st, "sum", None)
        q = getattr(st, "sumsq", None)
        if w is None or s is None or q is None:
            return {}
        pas = max(1, int(pas))
        sl = (slice(None, None, pas),) * int(np.ndim(w))
        ww = np.asarray(w[sl], dtype=np.float64)
        ss = np.asarray(s[sl], dtype=np.float64)
        qq = np.asarray(q[sl], dtype=np.float64)
        if ww.size == 0:
            return {}
        couverts = ww > 0.0
        nc = int(np.count_nonzero(couverts))
        if nc == 0:
            return {}
        poids = ww[couverts] / float(n)
        out: dict[str, Any] = {
            "px_grille": int(ww.size),
            "px_couverts_pct": round(100.0 * nc / float(ww.size), 3),
            "poids_moyen": round(float(np.mean(poids)), 6),
            "poids_plein_pct": round(
                100.0 * float(np.count_nonzero(poids >= 1.0 - 1e-9)) / nc, 3),
            "poids_sous_pct": round(
                100.0 * float(np.count_nonzero(poids < 1.0 - 1e-9)) / nc, 3),
        }
        if n >= 2:
            wc = np.maximum(ww[couverts], 1e-9)
            moy = ss[couverts] / wc
            var = qq[couverts] / wc - moy * moy
            sig = np.sqrt(np.maximum(var, 0.0))
            out["sigma_p50"] = round(float(np.percentile(sig, 50)), 9)
            out["sigma_p90"] = round(float(np.percentile(sig, 90)), 9)
            out["sigma_p99"] = round(float(np.percentile(sig, 99)), 9)
        return out
    except Exception:
        return {}


# ------------------------------------------------------------- enregistrements
def noter_reference(app: Any, img: Any, motif: str = "",
                    role_source: Any = None, aligneur: str = "partage") -> None:
    """Journalise une RÉFÉRENCE D'ALIGNEMENT posée (et la retient pour inliner).

    `motif` : initiale / auto / manuelle / repli / restack / Ha — le « pourquoi »
    de la pose. `role_source` : le rôle dont la COUCHE a servi de référence
    (None hors composition, ou pour une brute). `aligneur` : "partage"
    (composite) ou "Ha" (voie A, repère propre).
    """
    global _ref
    if not actif():
        return
    try:
        role = None if role_source is None else str(role_source)
        n_role = int(getattr(pile_role(app, role), "n", 0) or 0)
        rec = {
            "type": "reference", "t": _horodatage(), "seq": _seq,
            "aligneur": aligneur, "motif": str(motif or ""),
            "role": role, "n": n_role,
            "mode": "compo" if bool(getattr(app, "_mode_compo", False)) else "mono",
            "composition": str(getattr(app, "_compo_nom", "") or ""),
            "empreinte": empreinte(img),
            "forme": [int(v) for v in np.shape(img)],
            "n_roles": profondeurs(app),
            "cadre": cadre(app),
            # Étape ① du plan ⑪ : la trace doit dire si le repli « phase » était
            # autorisé — sans ce drapeau, deux runs « avec » et « sans » phase se
            # ressemblent (mêmes brutes, même référence) alors que la mesure des
            # refus par rôle ne se compare QUE si l'on sait lequel tournait.
            "repli_phase": bool(getattr(getattr(app, "aligner", None),
                                        "repli_phase", True)),
        }
        _ref = rec
        app._trace_ref = rec
        _ecrire(rec)
    except Exception:
        pass


def noter_frame(app: Any, role: Any, etape: str, image: Any = None,
                aligneur: Any = None, ok: bool | None = None,
                expo: Any = None, t0: float | None = None,
                raison: str = "") -> None:
    """Journalise UNE brute vue par le worker, avec l'état de SA pile.

    `etape` : empilee / refus_alignement / refus_flou / ancre.
    `aligneur` : l'aligneur qui vient de décider (`StarAligner`), lu pour ses
    offsets — ignoré quand `ok` est faux (son `dernier` est celui d'AVANT, et
    l'écrire ferait croire qu'une frame refusée a été recalée).
    """
    global _seq
    if not actif():
        return
    try:
        _seq += 1
        role_s = None if role is None else str(role)
        st = pile_role(app, role_s)
        rec: dict[str, Any] = {
            "type": "frame", "t": _horodatage(), "seq": _seq,
            "role": role_s,
            "mode": "compo" if bool(getattr(app, "_mode_compo", False)) else "mono",
            "etape": str(etape or ""),
            "empreinte": empreinte(image) if image is not None else "",
            "expo": _f(expo),
            "n_roles": profondeurs(app),
            "cadre": cadre(app),
            "refus_role": int((getattr(app, "bad_frames_par_role", {}) or {})
                              .get(role_s, 0) or 0),
            "refus_total": int(getattr(app, "bad_frames", 0) or 0),
            "floues": int(getattr(app, "floues_rejetees", 0) or 0),
            "raison": str(raison or "")[:240],
        }
        # Référence EN VIGUEUR (celle qui vient d'être utilisée) : âge et contenu.
        ref = _ref if isinstance(_ref, dict) else None
        rec["ref_seq"] = ref.get("seq") if ref else None
        rec["ref_role"] = ref.get("role") if ref else None
        rec["ref_n"] = ref.get("n") if ref else None
        rec["ref_motif"] = str(ref.get("motif") or "") if ref else ""
        rec["ref_empreinte"] = str(ref.get("empreinte") or "") if ref else ""
        rec["ref_age"] = (int(_seq - int(ref.get("seq") or 0)) if ref else None)
        # Alignement : SEULEMENT s'il a réussi (sinon `dernier` est périmé).
        rec["align_ok"] = bool(ok) if ok is not None else None
        d = getattr(aligneur, "dernier", None) if ok else None
        if isinstance(d, Mapping):
            dx, dy = _f(d.get("dx")), _f(d.get("dy"))
            rec["align_methode"] = str(d.get("methode") or "")
            rec["dx"] = dx
            rec["dy"] = dy
            rec["distance"] = (round(float(np.hypot(dx or 0.0, dy or 0.0)), 4)
                               if (dx is not None or dy is not None) else None)
            rec["angle"] = _f(d.get("angle"))
            rec["echelle"] = _f(d.get("echelle"))
        # Pile du rôle : profondeur, rejets cumulés, poids, σ.
        rec["n_role"] = int(getattr(st, "n", 0) or 0)
        rec["rejets_cumules"] = int(getattr(st, "rejected_total", 0) or 0)
        rec.update(resume_pile(st))
        if t0 is not None:
            rec["duree_ms"] = int(round((time.perf_counter() - float(t0)) * 1000.0))
        _ecrire(rec)
    except Exception:
        pass


# --------------------------------------------------------------------- cartes
def exporter_cartes(dossier: str, prefixe: str,
                    stackers: Mapping[str, Any]) -> list[str]:
    """Écrit, PAR RÔLE, trois cartes FITS : moyenne, poids, σ (option).

    POURQUOI des cartes et pas seulement des statistiques : une tache est un
    DÉFAUT LOCAL. Des percentiles disent « la couche a plus de bruit », pas
    « ici, et pas là ». La carte de poids (`wsum/n`) montre les pixels qu'un run
    a rejetés et l'autre non ; la carte de σ montre où le bruit temporel
    double — les deux se superposent (ou non) aux taches mesurées hors appli.

    Même route d'écriture FITS que l'application (`images.ecrire_fits` :
    atomique, float32, en-têtes), et JAMAIS d'exception remontée : une carte
    ratée ne doit pas invalider la mesure des autres.

    → liste des chemins écrits.
    """
    ecrits: list[str] = []
    try:
        from ..images import ecrire_fits
    except Exception:
        return ecrits
    try:
        os.makedirs(dossier, exist_ok=True)
    except Exception:
        return ecrits
    base = str(prefixe or NOM_DEFAUT).strip() or NOM_DEFAUT
    for role, st in dict(stackers or {}).items():
        try:
            n = int(getattr(st, "n", 0) or 0)
            w = getattr(st, "wsum", None)
            s = getattr(st, "sum", None)
            q = getattr(st, "sumsq", None)
            if n <= 0 or w is None or s is None or q is None:
                continue
            ww = np.asarray(w, dtype=np.float64)
            wc = np.maximum(ww, 1e-9)
            moy = (np.asarray(s, dtype=np.float64) / wc).astype(np.float32)
            var = (np.asarray(q, dtype=np.float64) / wc
                   - moy.astype(np.float64) ** 2)
            sig = np.sqrt(np.maximum(var, 0.0)).astype(np.float32)
            poi = (ww / float(n)).astype(np.float32)
            # Bords jamais couverts : 0 (ni poids ni σ n'y ont de sens).
            poi[ww <= 0.0] = 0.0
            sig[ww <= 0.0] = 0.0
            role_txt = str(role)
            for suffixe, arr in (("moyenne", moy), ("poids", poi),
                                 ("sigma", sig)):
                chemin = os.path.join(dossier,
                                      f"{base}_{role_txt}_{suffixe}.fits")
                try:
                    ecrire_fits(chemin, arr,
                                entete={"AVATRACE": base, "AVAROLE": role_txt,
                                        "AVAFRAME": n})
                    ecrits.append(chemin)
                except Exception:
                    continue
        except Exception:
            continue
    return ecrits
