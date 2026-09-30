# -*- coding: utf-8 -*-
"""_diag_parallele_gpu_jalon82.py — LES OUTILS EXTERNES PAR COUCHE, EN LOT, SUR
UNE MACHINE À GPU NVIDIA (CUDA).

POURQUOI CE BANC EXISTE. La mesure du 30/09/2026 (jalon 82) a été faite sur la
machine de dev, dont le GPU est un iGPU à mémoire PARTAGÉE, utilisé via DirectML
(GraXpert 3.1.0rc2) — sur 3 couches de 2168 × 3838 :

  - GRADIENT GraXpert (`-cmd background-extraction`) : **10,12 s -> 4,24 s en
    lot (+58,1 %)** — ses appels passent l'essentiel de leur temps à DÉMARRER,
    et le lot recouvre ces temps morts ;
  - DÉBRUITAGE GraXpert (`-cmd denoising`, modèle **3.0.2**) : **869,80 s ->
    981,69 s en lot (-12,9 %, PERTE)** — les trois appels simultanés ont brûlé
    ~880 s de CPU CHACUN pour le même travail, et ~10 Go de RAM à eux trois.

Le verdict du débruitage peut tenir au GPU (DirectML sur mémoire partagée), pas
au principe du parallélisme : ce banc rejoue donc EXACTEMENT les mêmes mesures
sur une machine à GPU DÉDIÉ et répond à trois questions, dans cet ordre :

  [1] GraXpert utilise-t-il VRAIMENT le GPU ? Son journal nomme les
      « inference providers » (`['CUDAExecutionProvider', 'CPUExecutionProvider']`
      ou autre chose) — c'est la première chose à savoir : sans CUDA, tout le
      reste mesure du calcul CPU ;
  [2] le lot fait-il gagner du temps sur un GPU DÉDIÉ (gradient ET débruitage) ?
  [3] combien de VRAM et de RAM système consomment 1 puis 3 appels simultanés ?
      (`nvidia-smi` est interrogé pendant les appels : 8 Go de la 3060 Ti
      suffisent-ils ?)

CE BANC NE MODIFIE RIEN dans l'application : il passe par le MÊME code
(`external.live.appliquer` / `appliquer_lot`) pour les mesures, et sonde le
journal d'un appel supplémentaire pour lire les providers.

Usage :
  python bancs/_diag_parallele_gpu_jalon82.py [dossier] [etape] [--px N] [--delai S]

  dossier : dossier contenant canal_R.fit / canal_G.fit / canal_B.fit (les
            couches de composition telles que l'application les ENREGISTRE —
            bouton « 💾 Enregistrer les canaux (par filtre)… » en mode
            composition). Absent ou introuvable → le banc fabrique des couches
            SYNTHÉTIQUES à la même définition (2168 × 3838) : les durées d'un
            appel GraXpert dépendent de la TAILLE de l'image, pas de son
            contenu — c'est dit dans le rapport.
  etape   : « diagnostic » (recommandé en premier : trois appels sur une
            vignette, répond à [1] et donne l'ordre de grandeur — AUCUNE mesure
            longue), « gradient » (diagnostic + mesure des 3 couches),
            « debruitage » (diagnostic + mesure), « tout » (défaut).
  --px N  : force une définition réduite (N pixels de côté) — validation du banc,
            PAS une mesure (chaque ligne le rappelle).
  --delai S : délai par appel (défaut 1200 s ; c'est aussi le garde-fou en cas de
            boîte de dialogue modale d'un GraXpert en échec).

⚠ Sur une machine SANS CUDA, le débruitage peut être BEAUCOUP plus lent qu'avec
un GPU : commencer par « diagnostic » (vignette) avant « tout ».

⚠ LE GAIN DÉPEND DE LA TAILLE (mesuré le 30/09/2026 sur la machine de dev) : à
petite définition le lot GAGNE — les démarrages fixes y pèsent lourd et se
recouvrent ; en pleine résolution il peut PERDRE, car le calcul domine (+22 % à
300 px contre **-13 % à 8,32 Mpx** pour le débruitage, même machine, mêmes
couches). **Seule la mesure en PLEINE RÉSOLUTION décide** : `--px` sert à
valider le banc, jamais à conclure.

Lancement (depuis la racine du dépôt ou du dossier d'installation) :
  python bancs/_diag_parallele_gpu_jalon82.py /chemin/vers/couches diagnostic
"""
# Racine du projet (celle qui porte AVAStack.py) dans sys.path : les bancs
# vivent sous bancs/ (ou bancs/cameras/) et non plus à côté de l'application.
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break

import json
import os
import shutil
import subprocess
import sys
import threading
import time

import numpy as np
import cv2
cv2.ocl.setUseOpenCL(False)          # crash OpenCV 5/OpenCL au teardown sinon
from astropy.io import fits

from avastack import travail
from avastack.compat import IS_WINDOWS, memoire_libre
from avastack.config import dossier_config
from avastack.external import live as gx
from avastack.images import ecrire_fits, find_output

try:                                 # sortie console : jamais de plantage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _lire_arguments():
    """(positionnels, options) — `--option valeur` ; sans dépendance externe."""
    pos, opt, i = [], {}, 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a.startswith("--"):
            opt[a[2:]] = (sys.argv[i + 1] if i + 1 < len(sys.argv) else "")
            i += 2
        else:
            pos.append(a)
            i += 1
    return pos, opt


_POS, OPT = _lire_arguments()
DOSSIER = _POS[0] if _POS else ""
ETAPE = (_POS[1] if len(_POS) > 1 else "tout").strip().lower()
PX_FORCE = int(OPT.get("px", 0) or 0)      # 0 = plein format
DELAI = float(OPT.get("delai", 1200) or 1200)
# La config d'AVAStack de CETTE machine (`%APPDATA%\AVAStack\config.json` sous
# Windows, `~/.config/AVAStack` sous Linux…) : c'est `config.py` qui sait où
# elle vit — le banc ne devine pas.
CHEMIN_CONFIG = os.path.join(dossier_config(), "config.json")
ROLES = ("R", "G", "B")
TAILLE_DEFAUT = (2168, 3838)               # ses couches réelles (h, w)
VIGNETTE = 512                             # côté de la vignette de diagnostic


class Sortie:
    """Tout ce qui est écrit est AFFICHÉ *et* gardé : le banc produit un fichier
    de rapport, à renvoyer tel quel (les mesures se lisent loin de la machine)."""

    def __init__(self):
        self.lignes = []

    def dit(self, txt=""):
        print(txt, flush=True)
        self.lignes.append(txt)

    def ecrire(self):
        chemin = os.path.join(travail.dossier_travail(),
                              "rapport_gpu_jalon82.txt")
        with open(chemin, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lignes) + "\n")
        return chemin


S = Sortie()
dit = S.dit


def _nvidia_smi(*args):
    """Sortie de `nvidia-smi` (liste de lignes), ou None s'il est introuvable.

    `shutil.which` d'abord (PATH) ; sous Windows, repli sur l'emplacement
    habituel du pilote (nvidia-smi n'y est pas toujours dans le PATH)."""
    exe = shutil.which("nvidia-smi")
    if exe is None and IS_WINDOWS:
        for c in (os.path.join(os.environ.get("ProgramW6432") or "",
                               "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe"),
                  os.path.join(os.environ.get("SystemRoot") or "",
                               "System32", "nvidia-smi.exe")):
            if os.path.isfile(c):
                exe = c
                break
    if exe is None:
        return None
    try:
        p = subprocess.run([exe] + list(args), capture_output=True, text=True,
                           timeout=20)
        return [l.strip() for l in (p.stdout or "").splitlines() if l.strip()]
    except Exception:                  # pilote absent, permission, timeout…
        return None


def info_gpu():
    """[nom, pilote, VRAM totale Mo] du premier GPU NVIDIA, ou None."""
    ligne = _nvidia_smi("--query-gpu=name,driver_version,memory.total",
                        "--format=csv,noheader")
    if not ligne:
        return None
    champs = [c.strip() for c in ligne[0].split(",")]
    return champs if len(champs) >= 3 else None


class Sonde:
    """Échantillonne en tâche de fond la VRAM utilisée et la RAM système LIBRE
    pendant un appel — c'est ce qui dit si trois appels simultanés tiennent
    dans les 8 Go de la 3060 Ti (et dans la RAM de la machine)."""

    def __init__(self, periode=2.0):
        self.periode = float(periode)
        self._stop = threading.Event()
        self._fil = None
        self.vram_max, self.vram_tot, self.util_max = 0.0, None, 0.0
        self.ram_min, self.ram_avant, self.n = None, None, 0

    def _boucle(self):
        while not self._stop.wait(self.periode):
            ligne = _nvidia_smi(
                "--query-gpu=memory.used,memory.total,utilization.gpu",
                "--format=csv,noheader,nounits")
            if ligne:
                try:
                    v, t, u = (float(x) for x in ligne[0].split(",")[:3])
                    self.vram_max = max(self.vram_max, v)
                    self.vram_tot = t
                    self.util_max = max(self.util_max, u)
                except Exception:
                    pass
            libre = memoire_libre()
            if libre:
                self.ram_min = (libre if self.ram_min is None
                                else min(self.ram_min, libre))
            self.n += 1

    def __enter__(self):
        self.ram_avant = memoire_libre()
        self._fil = threading.Thread(target=self._boucle, daemon=True)
        self._fil.start()
        return self

    def __exit__(self, *_a):
        self._stop.set()
        if self._fil is not None:
            self._fil.join(timeout=5.0)
        return False

    def resume(self):
        """Une ligne lisible : VRAM de pic, charge GPU de pic, RAM libre mini."""
        bouts = []
        if self.vram_tot:
            bouts.append("VRAM pic %d Mo / %d Mo"
                         % (int(self.vram_max), int(self.vram_tot)))
            bouts.append("GPU pic %d %%" % int(self.util_max))
        else:
            bouts.append("VRAM non mesurée (nvidia-smi indisponible)")
        if self.ram_min is not None and self.ram_avant:
            bouts.append("RAM libre mini %.1f Go (baisse de %.1f Go)"
                         % (self.ram_min / 2**30,
                            (self.ram_avant - self.ram_min) / 2**30))
        return " · ".join(bouts)


def reglage(cle, defaut):
    """Valeur de `cle` dans la config d'AVAStack de CETTE machine (tolérant).

    Le banc doit mesurer les commandes RÉELLES de l'utilisateur quand la config
    existe ; ailleurs, on prend celles que l'application proposerait
    (`external.detection`) — jamais une commande inventée."""
    try:
        with open(CHEMIN_CONFIG, encoding="utf-8") as f:
            return json.load(f).get(cle, defaut)
    except Exception:
        return defaut


def commandes():
    """(commande gradient, commande débruitage) — config de la machine, sinon
    détection/liaison par défaut de l'application."""
    gx_cmd = str(reglage("cmd_graxpert", "") or "")
    dn_cmd = str(reglage("cmd_graxpert_dn", "") or "")
    if not gx_cmd or not dn_cmd:
        try:
            from avastack.external import detection as _det
            if not gx_cmd:
                gx_cmd = _det.commande_par_defaut_graxpert()
            if not dn_cmd:
                dn_cmd = _det.commande_par_defaut_graxpert_dn()
        except Exception as exc:
            dit("  ⚠ détection des commandes impossible : %s" % exc)
    return gx_cmd, dn_cmd


def couches_synthetiques(h, w, graine=7):
    """Trois couches mono réalistes À LA DÉFINITION DEMANDÉE (repli quand les
    couches réelles sont absentes) : fond légèrement incliné (le retrait de
    gradient a du travail), bruit gaussien, quelques étoiles.

    Les durées d'un appel GraXpert dépendent de la TAILLE de l'image, pas de son
    contenu : ce repli mesure donc la même chose — et c'est DIT dans le rapport."""
    rng = np.random.default_rng(graine)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    base = 0.03 + 0.012 * (xx / float(w)) + 0.008 * (yy / float(h))
    out = {}
    for i, role in enumerate(ROLES):
        img = base * (1.0 + 0.15 * i) + rng.normal(0, 0.004, (h, w))
        for _ in range(40):
            y = int(rng.integers(10, h - 10))
            x = int(rng.integers(10, w - 10))
            img[y - 2:y + 3, x - 2:x + 3] += 0.4
        out[role] = np.clip(img, 0.0, 1.0).astype(np.float32)
    return out


def charger_couches():
    """(couches, provenance) — les siennes si le dossier les porte, sinon des
    couches synthétiques à la même définition."""
    if DOSSIER and os.path.isdir(DOSSIER):
        trouve = {}
        for role in ROLES:
            for ext in (".fit", ".fits"):
                p = os.path.join(DOSSIER, "canal_%s%s" % (role, ext))
                if os.path.isfile(p):
                    d = np.asarray(fits.getdata(p), dtype=np.float32)
                    if d.ndim == 3 and d.shape[0] == 3:
                        d = np.ascontiguousarray(np.transpose(d, (1, 2, 0)))
                    trouve[role] = d
                    break
        if len(trouve) == len(ROLES):
            return trouve, "couches RÉELLES (%s)" % DOSSIER
        dit("  ⚠ couches canal_R/G/B introuvables dans %s → synthèse" % DOSSIER)
    h, w = TAILLE_DEFAUT
    return (couches_synthetiques(h, w),
            "couches SYNTHÉTIQUES %d × %d (aucun dossier de couches fourni)"
            % (w, h))


def appel_journalise(img, cmd, timeout):
    """Appel de l'outil avec les MÊMES conventions que l'application, mais le
    journal est CONSERVÉ : c'est le seul moyen de lire les « inference
    providers » (l'application efface son dossier de travail quand tout va bien).

    → (image de sortie ou None, message d'erreur, lignes du journal, durée)."""
    tmp = travail.creer_dossier("avastack_gpu_")
    t0 = time.perf_counter()
    try:
        src = os.path.join(tmp, "in.fits")
        base = os.path.join(tmp, "out")
        gx._ecrire_entree(src, img)
        commande = (cmd.replace("{input}", src)
                       .replace("{output}", base + ".fits")
                       .replace("{outbase}", base))
        code, err = gx._run_bloquant_survivable(commande, tmp, timeout)
        duree = time.perf_counter() - t0
        lignes = []
        try:
            with open(os.path.join(tmp, "outils_sortie.txt"),
                      encoding="utf-8", errors="replace") as f:
                lignes = [l for l in f.read().splitlines() if l.strip()]
        except OSError:
            pass
        if err:
            return None, err, lignes, duree
        if code != 0:
            return (None, "code %s : %s"
                    % (code, lignes[-1] if lignes else "aucun message"),
                    lignes, duree)
        res = find_output(src, base)
        if res is None:
            return None, "l'outil n'a rien écrit", lignes, duree
        return gx._lire_sortie(res), "", lignes, duree
    except Exception as exc:               # E/S, FITS illisible…
        return None, str(exc), [], time.perf_counter() - t0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _sans_entete(ligne):
    """Message d'une ligne de journal, sans horodatage ni préfixe du logger."""
    return (ligne.split("INFO", 1)[-1].strip() if "INFO" in ligne
            else ligne.strip())


def lire_journal(lignes):
    """Ce que le journal de GraXpert dit du GPU, du modèle et des réglages.

    ⚠ Le LIVRE des lignes DIFFÈRE selon la tâche (constat du 30/09/2026) :
    le retrait de gradient écrit « Providers : [...] » puis « Used providers :
    [...] », le débruitage écrit « Available inference providers : [...] » puis
    « Used inference providers : [...] ». On accepte les DEUX formulations — un
    banc qui n'en connaîtrait qu'une ne saurait rien dire du gradient."""
    out = {}
    for l in lignes:
        bas = l.lower()
        if "used inference providers" in bas or "used providers" in bas:
            out["providers_utilises"] = _sans_entete(l)
        elif ("available inference providers" in bas
              or "providers :" in bas):
            out["providers_disponibles"] = _sans_entete(l)
        elif "ai model path" in bas:
            out["modele"] = _sans_entete(l)
        elif "using ai version" in bas:
            out["version_ia"] = _sans_entete(l)
        elif "batch size" in bas:
            out["batch"] = _sans_entete(l)
        elif "gpu acceleration" in bas:
            out["acceleration_gpu"] = _sans_entete(l)
        elif "starting graxpert cli" in bas:
            out["tache"] = _sans_entete(l)
    return out


def etape(nom, imgs, cmd, lot):
    """Une étape GraXpert par couche : SÉRIE (aujourd'hui) ou LOT → (durée, images).

    Passe par le code de l'application (`gx.appliquer` / `gx.appliquer_lot`) et
    sonde la VRAM et la RAM système pendant l'appel."""
    dit("\n  %s — %s" % (nom, "LOT (3 appels simultanés)" if lot
                         else "SÉRIE (aujourd'hui)"))
    t0 = time.perf_counter()
    with Sonde() as sonde:
        if lot:
            res = gx.appliquer_lot([(r, imgs[r], cmd) for r in ROLES], DELAI)
        else:
            res = {r: gx.appliquer(imgs[r], cmd, DELAI) for r in ROLES}
    duree = time.perf_counter() - t0
    out, ok = {}, 0
    for r in ROLES:
        img, err = res.get(r, (None, "appel non exécuté"))
        if err or img is None:
            dit("      ⚠ couche %s : %s" % (r, (err or "aucun résultat")[:120]))
        else:
            ok += 1
        out[r] = img
    dit("      → %d couche(s) sur %d en %6.3f s  (%.2f s par appel)  [%s]"
        % (ok, len(ROLES), duree, duree / len(ROLES), time.strftime("%H:%M:%S")))
    dit("        %s" % sonde.resume())
    return duree, out


def phase_diagnostic(cmd_gx, cmd_dn, imgs, faire_gx, faire_dn):
    """Les « inference providers », sur une VIGNETTE : quelques secondes, et
    c'est la réponse à « le GPU sert-il VRAIMENT ? » (les providers ne dépendent
    pas de la taille de l'image ; les durées, si)."""
    dit("\n[2] DIAGNOSTIC — quel moteur d'inférence GraXpert utilise-t-il ?")
    dit("    (vignette %d px ; la ligne « providers UTILISÉS » est la réponse)"
        % VIGNETTE)
    vign = {r: np.ascontiguousarray(imgs[r][:VIGNETTE, :VIGNETTE])
            for r in ROLES}
    cuda = []
    for libelle, cmd, actif in (("GRADIENT", cmd_gx, faire_gx),
                                ("DÉBRUITAGE", cmd_dn, faire_dn)):
        if not actif or not cmd:
            continue
        out, err, lignes, duree = appel_journalise(vign["R"], cmd, DELAI)
        dit("\n    · %s — appel de %.2f s" % (libelle, duree))
        dit("      commande : %s" % cmd[:110])
        infos = lire_journal(lignes)
        for cle, etiq in (("tache", "tâche"), ("version_ia", "version IA"),
                          ("modele", "modèle"), ("batch", "batch"),
                          ("acceleration_gpu", "accél. GPU"),
                          ("providers_disponibles", "providers DISPONIBLES"),
                          ("providers_utilises", "providers UTILISÉS")):
            if cle in infos:
                dit("      %-21s : %s" % (etiq, infos[cle][:150]))
        if "providers_utilises" not in infos:
            dit("      ⚠ le journal ne nomme pas les providers — dernières "
                "lignes :")
            for l in lignes[-6:]:
                dit("      | %s" % l[:150])
        elif "CUDA" in (infos.get("providers_utilises") or ""):
            cuda.append(libelle)
        if err or out is None:
            dit("      ⚠ l'appel a échoué : %s" % (err or "aucune image")[:150])
            continue
        # L'appel instrumenté doit rendre EXACTEMENT l'image de l'application.
        ref, err_ref = gx.appliquer(vign["R"], cmd, DELAI)
        if err_ref or ref is None:
            dit("      ⚠ comparaison avec l'application impossible : %s"
                % err_ref)
        else:
            dit("      %s" % ("appel instrumenté = application, AU BIT"
                              if np.array_equal(out, ref)
                              else "⚠ ÉCART entre l'appel instrumenté et "
                                   "l'application — ne pas conclure"))
    if cuda:
        dit("\n    ✔ CUDA est utilisé pour : %s" % ", ".join(cuda))
    else:
        dit("\n    ⚠ CUDA n'apparaît dans AUCUN journal : l'inférence ne passe "
            "pas par le GPU NVIDIA")
        dit("      (Vérifier le pilote NVIDIA, `nvidia-smi`, et une éventuelle "
            "mise à jour de GraXpert : sa build doit embarquer CUDA.)")


def main():
    dit("=" * 78)
    dit("PARALLÉLISME DES OUTILS EXTERNES SUR GPU NVIDIA (mesure, jalon 82)")
    dit("=" * 78)
    faire_diag = ETAPE in ("tout", "gradient", "debruitage", "diagnostic")
    diag_gx = ETAPE in ("tout", "gradient", "diagnostic")
    diag_dn = ETAPE in ("tout", "debruitage", "diagnostic")
    faire_gx = ETAPE in ("tout", "gradient")      # mesure série/lot, 3 couches
    faire_dn = ETAPE in ("tout", "debruitage")

    dit("\n[0] environnement")
    dit("  python          : %s" % sys.version.split()[0])
    dit("  plateforme      : %s" % sys.platform)
    dit("  cœurs logiques  : %s" % (os.cpu_count() or "?"))
    dit("  OpenCV          : %s (%d fils)"
        % (cv2.__version__, cv2.getNumThreads()))
    gpu = info_gpu()
    dit("  GPU NVIDIA      : %s" % ("%s · pilote %s · %s Mo de VRAM" % tuple(gpu)
                                    if gpu else "AUCUN vu par nvidia-smi"))
    libre = memoire_libre()
    dit("  mémoire libre   : %s" % ("%.1f Go" % (libre / 2**30) if libre
                                    else "indéterminée"))
    cmd_gx, cmd_dn = commandes()
    for nom, cmd in (("gradient", cmd_gx), ("débruitage", cmd_dn)):
        manque = (gx.outil_manquant(cmd) if cmd else "commande absente")
        dit("  commande %-9s : %s" % (nom, (cmd or "—")[:110]))
        if manque:
            dit("    ⚠ %s" % manque)
    if not cmd_gx or gx.outil_manquant(cmd_gx):
        dit("\n  → mesure impossible SANS GraXpert (aucun chiffre inventé).")
        return
    dit("  étape mesurée   : %s%s" % (ETAPE, "" if not PX_FORCE else
                                     "  (--px %d : VALIDATION, pas une mesure)"
                                     % PX_FORCE))

    dit("\n[1] images")
    imgs, provenance = charger_couches()
    if PX_FORCE:
        imgs = {r: np.ascontiguousarray(imgs[r][:PX_FORCE, :PX_FORCE])
                for r in ROLES}
        provenance += " — RECADRÉES à %d px (validation)" % PX_FORCE
    h, w = imgs["R"].shape[:2]
    dit("  %d × %d par couche (%.2f Mpx)" % (w, h, w * h / 1e6))
    dit("  provenance : %s" % provenance)

    phase_diagnostic(cmd_gx, cmd_dn, imgs, diag_gx and faire_diag,
                     diag_dn and faire_diag)
    if not (faire_gx or faire_dn):
        dit("\n  → mode « diagnostic » : AUCUNE mesure longue n'a été lancée.")
        dit("    Pour les mesures série/lot en pleine résolution, relancer avec "
            "« gradient », « debruitage » ou « tout ».")
        return

    totaux, numero = {}, 3
    for nom, cmd, actif in (("GRADIENT (cmd_graxpert)", cmd_gx, faire_gx),
                            ("DÉBRUITAGE GraXpert (cmd_graxpert_dn)", cmd_dn,
                             faire_dn)):
        if not actif:
            continue
        if not cmd:
            dit("\n[%d] %s : non mesuré (commande absente)" % (numero, nom))
            numero += 1
            continue
        dit("\n[%d] %s — 3 couches, une par une" % (numero, nom))
        t_s, out_s = etape("couche par couche", imgs, cmd, lot=False)
        t_l, out_l = etape("couche par couche", imgs, cmd, lot=True)
        ident = all(out_s[r] is not None and out_l[r] is not None
                    and np.array_equal(out_s[r], out_l[r]) for r in ROLES)
        dit("      → série %.2f s · lot %.2f s · %s   [%s]"
            % (t_s, t_l,
               ("GAIN de %.1f %% (%.2f s gagnées)"
                % (100.0 * (t_s - t_l) / t_s, t_s - t_l) if t_l <= t_s else
                "PERTE de %.1f %% (%.2f s perdues)"
                % (100.0 * (t_l - t_s) / t_s, t_l - t_s)),
               "images identiques AU BIT" if ident
               else "⚠ ÉCART (ou appel raté) : ne pas conclure"))
        totaux[nom] = (t_s, t_l, ident)
        numero += 1

    dit("\n" + "=" * 78)
    dit("BILAN — à renvoyer tel quel (le rapport complet est le fichier cité "
        "à la fin)")
    for nom, (t_s, t_l, ident) in totaux.items():
        dit("  %-38s série %7.2f s · lot %7.2f s · %+.0f %%  %s"
            % (nom, t_s, t_l, 100.0 * (t_l - t_s) / max(t_s, 1e-9),
               "au bit" if ident else "ÉCART !"))
    if totaux:
        s = sum(v[0] for v in totaux.values())
        l = sum(v[1] for v in totaux.values())
        dit("  %-38s série %7.2f s · lot %7.2f s · %+.0f %%"
            % ("TOTAL des étapes mesurées", s, l, 100.0 * (l - s) / s))
    dit("=" * 78)


if __name__ == "__main__":
    try:
        main()
    finally:
        # Le rapport est écrit MÊME si le banc est interrompu (c'est le résultat
        # qui compte : il se lit sur une autre machine).
        try:
            dit("\n[rapport] fichier à renvoyer : %s" % S.ecrire())
        except Exception as exc:           # disque, permission…
            print("rapport non écrit : %s" % exc)
