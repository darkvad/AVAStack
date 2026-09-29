# -*- coding: utf-8 -*-
"""Compatibilite multiplateforme (Windows / Linux / macOS).

Constantes liees a l'OS, centralisees ici pour qu'aucun autre module
n'ait besoin de tester lui-meme la plateforme.
"""

import os
import sys

IS_WINDOWS = (os.name == "nt")
IS_MACOS = (sys.platform == "darwin")

# Nom de bibliotheque du SDK ZWO selon l'OS (DLL Windows, .so Linux, .dylib macOS)
ZWO_DLL_NAME = "ASICamera2.dll" if IS_WINDOWS else (
    "libASICamera2.dylib" if IS_MACOS else "libASICamera2.so")


def memoire_libre():
    """Octets de mémoire PHYSIQUE encore disponibles, ou None si indéterminable.

    Trois implémentations sans AUCUNE dépendance, choisies ici pour qu'aucun
    autre module n'ait à tester la plateforme : Windows `GlobalMemoryStatusEx`
    (ctypes), Linux `/proc/meminfo` (`MemAvailable`, repli `MemFree`) et macOS
    `os.sysconf` (`SC_AVPHYS_PAGES` × taille de page).

    Sert au garde-fou du PARALLÉLISME des outils externes (jalon 81) : chaque
    GraXpert simultané coûte ~680 Mo (les 217 Mo du modèle IA + son runtime
    Python) — mesuré 1,22 Go pour TROIS. On ne parallélise donc pas à
    l'aveugle sur une machine déjà chargée."""
    try:
        if IS_WINDOWS:
            import ctypes

            class _Etat(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            etat = _Etat()
            etat.dwLength = ctypes.sizeof(_Etat)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(
                    ctypes.byref(etat)):
                return None
            return int(etat.ullAvailPhys)
        if IS_MACOS:
            return int(os.sysconf("SC_AVPHYS_PAGES")
                       * os.sysconf("SC_PAGE_SIZE"))
        with open("/proc/meminfo", encoding="ascii", errors="replace") as f:
            infos = {}
            for ligne in f:
                cle, _, valeur = ligne.partition(":")
                infos[cle.strip()] = valeur.strip()
        for cle in ("MemAvailable", "MemFree"):
            if cle in infos:
                return int(infos[cle].split()[0]) * 1024
    except Exception:                     # sonde : jamais bloquante
        return None
    return None
