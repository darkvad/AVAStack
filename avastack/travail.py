# -*- coding: utf-8 -*-
"""Dossier de TRAVAIL d'AVAStack : où vivent les fichiers temporaires lourds.

POURQUOI CE MODULE (constat RÉEL d'Alain, 27/09/2026, machine Linux) :

    Erreur : 24962352 requested and 10902832 written

Ce message est celui de `numpy.ndarray.tofile()` — appelé par astropy pour
écrire les données d'un FITS (`io/fits/util.py::_array_to_file` « delegates
directly to ndarray.tofile »). Il signifie **écriture PARTIELLE** : 10 902 832
octets écrits sur 24 962 352 demandés. Mesure sur sa machine :

    tmpfs  4,6G  2,8G  1,8G  61%  /tmp     ← /tmp est de la RAM (tmpfs)
    du -sh /tmp = 2,8G  →  3 dossiers avastack_frames_* (frames de 32 Mio)
    /dev/sdb2  234G  106G  116G  48%  /    ← 116 Go libres, jamais utilisés

Trois défauts démontrés, corrigés ici ou chez les appelants :
  ① le **plafond d'archivage des frames** était de 20 Go EN DUR alors que le
     volume en faisait 4,6 → le garde-fou ne pouvait pas se déclencher ;
  ② **rien ne nettoyait les résidus** d'une session morte (2,8 Go de RAM) ;
  ③ l'échec était **illisible** : ni le fichier, ni la cause, ni le volume.

Ce module centralise donc : le dossier de travail (avec REPLI HORS tmpfs), la
création des dossiers temporaires d'AVAStack (un seul point d'entrée), l'espace
libre du volume, la traduction des erreurs d'écriture en phrases chiffrées, le
nettoyage des orphelins, et un plafond d'usage calculé sur l'espace RÉEL.
"""

import os
import shutil
import subprocess
import tempfile
import time

from .compat import IS_MACOS, IS_WINDOWS

# Tous nos dossiers temporaires commencent par ce préfixe (framestore, chaîne
# externe, GraXpert live, astrométrie, composition) : c'est ce qui permet de
# reconnaître — et de nettoyer — les résidus d'une session morte.
PREFIXE: str = "avastack_"
# Âge au-delà duquel un dossier `avastack_*` est un ORPHELIN (aucune session
# d'empilement ne dure 6 h sans écrire : une frame est archivée au plus toutes
# les secondes, et une chaîne externe toutes les minutes).
AGE_ORPHELIN_H: float = 6.0
# Marge appliquée à une écriture demandée (en-têtes, métadonnées, arrondis).
MARGE: float = 1.20
# Part MAXIMALE du volume qu'AVAStack s'autorise à occuper (travail + frames) :
# au-delà, c'est le système qui souffre (et /tmp en tmpfs étouffe la RAM).
PART_MAX_VOLUME: float = 0.5


def dossier_temp_systeme() -> str:
    """Dossier temporaire du système (`$TMPDIR`, sinon `/tmp`…)."""
    return tempfile.gettempdir()


def points_de_montage() -> list[tuple[str, str]]:
    """[(point de montage, type de système)] lus dans `/proc/mounts`.

    → [] sur Windows/macOS ou si `/proc` est absent (jamais d'exception) :
    la détection de tmpfs n'a de sens que sous Linux."""
    try:
        with open("/proc/mounts", encoding="utf-8", errors="replace") as f:
            lignes = f.read().splitlines()
    except OSError:
        return []
    out: list[tuple[str, str]] = []
    for ligne in lignes:
        champs = ligne.split()
        if len(champs) >= 3:
            out.append((champs[1].replace("\\040", " "), champs[2]))
    return out


def est_tmpfs(chemin: str) -> bool:
    """`chemin` est-il sur un volume de RAM (tmpfs) ?

    C'est LE critère qui manquait : sous Linux `/tmp` est souvent un tmpfs
    (une fraction de la RAM), donc parfait pour un fichier de 2 Mo et
    catastrophique pour des FITS de 25 à 35 Mo écrits en série. On cherche le
    point de montage le PLUS LONG qui préfixe le chemin (celui qui porte
    réellement le fichier, pas `/`)."""
    return type_systeme(chemin) == "tmpfs"


# Types de systèmes de fichiers RÉSEAU (NAS) : un `stat` sur ces montages peut
# ATTENDRE INDÉFINIMENT quand le réseau ne répond pas (autofs n'a pas de délai
# par défaut ; un pare-feu qui filtre le NAS suffit). Constat RÉEL d'Alain,
# 27/09/2026 : ses dossiers de couches R/G/B sont sur son NAS, `nftables`
# filtrait ce NAS, et l'application ne s'ouvrait plus — sans un mot.
TYPES_RESEAU: tuple[str, ...] = (
    "nfs", "nfs4", "cifs", "smb3", "smbfs", "sshfs", "fuse.sshfs",
    "fuse.rclone", "glusterfs", "ceph", "9p", "afs", "davfs",
    "fuse.gvfsd-fuse", "autofs")


def type_systeme(chemin: str) -> str:
    """Type de système de fichiers qui porte RÉELLEMENT `chemin` (point de
    montage le PLUS LONG qui le préfixe), ou "" si inconnu (Windows/macOS, ou
    `/proc/mounts` absent). Jamais d'exception."""
    if IS_WINDOWS or IS_MACOS:
        return ""
    cible = os.path.realpath(os.path.abspath(chemin))
    meilleur, fstype = "", ""
    for point, type_fs in points_de_montage():
        p = os.path.realpath(point) if point != "/" else "/"
        prefixe = p if p == "/" else p.rstrip(os.sep) + os.sep
        if (cible == p or cible.startswith(prefixe)) and len(p) > len(meilleur):
            meilleur, fstype = p, type_fs
    return fstype


def sur_montage_reseau(chemin: str) -> bool:
    """`chemin` est-il sur un montage RÉSEAU (NAS : NFS, SMB, sshfs…) ?
    → bool, jamais d'exception. Sert à NE PAS balayer ces dossiers : un accès
    que le réseau (ou un pare-feu) bloque y attend indéfiniment."""
    return type_systeme(chemin) in TYPES_RESEAU


def dossier_defaut() -> str:
    """Dossier de travail par défaut : le temporaire du système, SAUF s'il vit
    en RAM — auquel cas un dossier de cache sur le disque (`~/.cache/avastack`,
    `XDG_CACHE_HOME` honoré). Constat du 27/09/2026 : avec `/tmp` en tmpfs de
    4,6 Go, les frames (32 Mio) et les FITS d'outils remplissaient la RAM
    pendant que 116 Go dormaient sur le disque."""
    tmp = dossier_temp_systeme()
    if not est_tmpfs(tmp):
        return tmp
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "avastack")


def dossier_travail() -> str:
    """Dossier de travail EFFECTIF, créé au besoin :

      1. le réglage `dossier_travail` de config.json (choix explicite de
         l'utilisateur, bouton « dossier de travail » de l'interface) — c'est
         le seul moyen de mettre les fichiers de 30 Mo sur un disque de
         données plutôt que dans la RAM ;
      2. sinon `dossier_defaut()` : le temporaire du système, ou un cache sur
         le disque si ce temporaire est un tmpfs.

    Un réglage inutilisable (chemin refusé, volume disparu) ne fait JAMAIS
    échouer l'application : on retombe sur le défaut."""
    reglage = ""
    try:
        from .config import CONFIG
        reglage = os.path.expanduser((CONFIG.get("dossier_travail") or "").strip())
    except Exception:                    # config illisible : jamais bloquant
        reglage = ""
    if reglage:
        try:
            os.makedirs(reglage, exist_ok=True)
            if os.path.isdir(reglage):
                return reglage
        except OSError:
            pass
    d = dossier_defaut()
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return dossier_temp_systeme()
    return d


def creer_dossier(prefixe: str | None = None) -> str:
    """Crée un dossier temporaire DANS le dossier de travail (`mkdtemp`).

    À utiliser PARTOUT à la place de `tempfile.mkdtemp()` : c'est ce qui
    garantit que les FITS d'étape, l'archive des frames et les aperçus d'outils
    vont au même endroit — celui que l'utilisateur peut déplacer."""
    return tempfile.mkdtemp(prefix=prefixe or PREFIXE, dir=dossier_travail())


def espace_libre(dossier: str) -> int:
    """Octets libres du volume qui porte `dossier` (0 si illisible)."""
    try:
        return int(shutil.disk_usage(dossier).free)
    except OSError:
        return 0


def texte_octets(n: float) -> str:
    """« 24,9 Mo », « 1,2 Go », « 512 o » — pour les messages utilisateur."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "? o"
    for unite, facteur in (("Go", 1 << 30), ("Mo", 1 << 20), ("Kio", 1 << 10)):
        if n >= facteur:
            return ("%.1f" % (n / facteur)).replace(".", ",") + " " + unite
    return "%d o" % int(n)


def verifier_espace(dossier: str, octets: float,
                    quoi: str = "cette écriture") -> tuple[bool, str]:
    """→ (True, "") si le volume peut recevoir `octets` (marge incluse),
    sinon (False, message CHIFFRÉ et actionnable).

    Appelé AVANT d'écrire : mieux vaut refuser en 1 ms avec une phrase claire
    que remplir 43 % d'un FITS et laisser un fichier tronqué qui a l'air
    valide."""
    libre = espace_libre(dossier)
    besoin = int(max(0, octets) * MARGE)
    if libre == 0 or libre >= besoin:
        return True, ""
    return False, (
        f"espace insuffisant pour {quoi} : il faut {texte_octets(besoin)}, "
        f"il reste {texte_octets(libre)} sur le volume de « {dossier} »"
        + (" (en RAM : tmpfs)" if est_tmpfs(dossier) else "")
        + " — libérez de l'espace ou choisissez un autre dossier de travail "
          "(bouton « dossier de travail »).")


def plafond_effectif(dossier, plafond_voulu, part=PART_MAX_VOLUME):
    """Plafond d'occupation RÉEL : `min(plafond_voulu, part × espace libre)`.

    C'est la correction du garde-fou inopérant : l'archivage des frames
    s'arrêtait à 20 Go EN DUR — jamais atteints dans un `/tmp` de 4,6 Go, qui
    se remplissait donc entièrement (constat du 27/09/2026)."""
    libre = espace_libre(dossier)
    if libre <= 0:
        return int(plafond_voulu)
    return int(min(plafond_voulu, libre * max(0.05, min(0.9, part))))



def taille_dossier(chemin: str) -> int:
    """Somme des tailles des fichiers sous `chemin` (0 si illisible)."""
    total = 0
    for dossier, _sous, noms in os.walk(chemin, onerror=lambda _e: None):
        for nom in noms:
            try:
                total += os.path.getsize(os.path.join(dossier, nom))
            except OSError:
                continue
    return total


def nettoyer_orphelins(age_h: float = AGE_ORPHELIN_H,
                       dossiers: list[str] | None = None,
                       prefixe: str = PREFIXE) -> tuple[int, int]:
    """Supprime les dossiers `avastack_*` PLUS VIEUX que `age_h` heures.

    Une session d'empilement écrit en continu (frames, étapes d'outils) : un
    dossier que plus personne ne touche depuis des heures est un RÉSIDU d'une
    session morte (fermeture brutale, plantage). Sans ce nettoyage, ils
    s'accumulent — 2,8 Go constatés chez Alain le 27/09/2026, dans un tmpfs,
    c'est-à-dire de la RAM perdue.

    → (nombre de dossiers supprimés, octets récupérés). Jamais d'exception ;
    un dossier RÉCENT (session en cours, y compris d'une autre instance) est
    laissé intact."""
    if dossiers is None:
        dossiers = [dossier_travail(), dossier_temp_systeme()]
    limite = time.time() - max(0.0, float(age_h)) * 3600.0
    n, octets = 0, 0
    vus: set[str] = set()
    for racine in dossiers:
        try:
            noms = os.listdir(racine)
        except OSError:
            continue
        for nom in noms:
            chemin = os.path.join(racine, nom)
            cle = os.path.realpath(chemin)
            if cle in vus or not nom.startswith(prefixe):
                continue
            vus.add(cle)
            try:
                if not os.path.isdir(chemin) or os.path.getmtime(chemin) > limite:
                    continue                         # dossier ou session en cours
            except OSError:
                continue
            octets += taille_dossier(chemin)
            shutil.rmtree(chemin, ignore_errors=True)
            if not os.path.exists(chemin):
                n += 1
    return n, octets


def ouvrir_chemin(chemin: str) -> str:
    """Ouvre `chemin` (DOSSIER **ou FICHIER**) avec l'outil par défaut de l'OS.
    → "" si la commande est partie, sinon le message d'erreur (jamais
    d'exception : l'appelant l'affiche tel quel).

    Un fichier est ouvert par son application associée, un dossier par le
    gestionnaire de fichiers : c'est ce qui permet au bouton « Journal »
    (v2.38.7) d'emprunter exactement le même chemin que « Ouvrir » (dossier de
    travail)."""
    try:
        if IS_WINDOWS:
            # os.startfile n'existe QUE sous Windows : ignore CIBLÉ pour un
            # pyright lancé sur un autre OS (typeshed sans startfile).
            os.startfile(chemin)  # noqa: S606 (Windows)  # pyright: ignore[reportAttributeAccessIssue]
        elif IS_MACOS:
            subprocess.Popen(["open", chemin])
        else:
            subprocess.Popen(["xdg-open", chemin])
        return ""
    except Exception as exc:                     # pas de gestionnaire : dire
        return str(exc)


def ouvrir_dossier(chemin: str) -> str:
    """Nom historique (v2.38.6) : ouvrir un dossier — cf. `ouvrir_chemin`."""
    return ouvrir_chemin(chemin)

