# -*- coding: utf-8 -*-
"""Mesure MÉMOIRE (et threads) de l'application — outil rejouable.

POURQUOI (20/10/2026) : après P5, Alain a constaté « 80 % de 32 Go » occupés et
une interface qui ne répond que lorsque le spinner « traitement en cours » est
éteint. Le premier réflexe a été de MESURER l'application elle-même, plutôt que
de supposer : elle tient en **RSS ~148 Mo (pic 259 Mo)** après trois aperçus
1600×1200, avec 3 threads — donc le repos ne consomme pas 25 Go. Les suspects
sont les accumulateurs d'empilement à PLEINE RÉSOLUTION
(`LiveStacker.sum/sumsq/wsum` en float64, fenêtre Winsorized de 8 frames, × nombre
de canaux). CE QU'IL RESTE À MESURER : la RSS **pendant un empilement réel**,
1 canal puis 5 — ajouter ici le branchement sur une source « dossier » est le
prochain pas ; en attendant, cet outil fixe la RÉFÉRENCE du repos.

Aucune dépendance externe (pas de psutil) : lecture de `K32GetProcessMemoryInfo`
par ctypes. Windows uniquement pour l'instant ; ailleurs, l'outil s'arrête
proprement (le projet vise aussi Linux/macOS : y lire `/proc/self/status` ou
`resource.getrusage`).

USAGE : python bancs/_mesure_memoire.py   (nécessite un affichage)
"""
import sys as _s, pathlib as _p
for _d in _p.Path(__file__).resolve().parents:
    if (_d / "AVAStack.py").is_file():
        _s.path.insert(0, str(_d)); break
import ctypes, ctypes.wintypes as wt, sys, threading
import numpy as np
import avastack.ui.app as ui

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def mem_mb():
    """(RSS, pic RSS, mémoire privée/commit) du processus, en Mo."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = wt.HANDLE
    k32.K32GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC),
                                            wt.DWORD]
    k32.K32GetProcessMemoryInfo.restype = wt.BOOL
    p = PMC()
    p.cb = ctypes.sizeof(PMC)
    if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(p),
                                       p.cb):
        raise OSError(ctypes.get_last_error())
    return (p.WorkingSetSize / 2**20, p.PeakWorkingSetSize / 2**20,
            p.PagefileUsage / 2**20)


def montre(etape):
    ws, pic, pf = mem_mb()
    print(f"{etape:44s} RSS {ws:8.0f} Mo · pic {pic:8.0f} Mo · "
          f"mémoire privée {pf:8.0f} Mo · threads {threading.active_count()}")


def main():
    montre("interpréteur + numpy importés")
    ui.CONFIG = {}
    ui.sauver_config = lambda *a, **k: None
    ui.App._dire = lambda self, *a, **k: None
    import tkinter as tk
    root = tk.Tk()
    app = ui.App(root)
    # 1b (20/10/2026) : mesure de MÉMOIRE après un rendu → rendu IMMÉDIAT (le
    # fil de rendu ne sert qu'en production).
    app.rendu.immediat = True
    root.update()
    montre("après construction de l'App")
    app.var_view.set("pile")
    img = np.random.default_rng(1).random((1200, 1600, 3)).astype(np.float32)
    montre("après une image linéaire 1600x1200 (float32)")
    app.last_show = img
    for _ in range(3):
        app._refresh_preview()
        root.update()
    montre("après 3 aperçus (etirement + histogrammes)")
    for t in threading.enumerate():
        print("  thread :", t.name, "| daemon" if t.daemon else "")
    root.destroy()
    montre("après destroy")
    return 0


if __name__ == "__main__":
    sys.exit(main())
