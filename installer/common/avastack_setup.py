# -*- coding: utf-8 -*-
"""Outils d'installation AVAStack (stdlib uniquement, aucune dépendance).

Utilisé par l'installateur Inno Setup (Windows) :
    python avastack_setup.py create-venv --venv-dir <chemin> --requirements <fichier>

Crée un venv et installe les dépendances. Les paquets optionnels liés aux
caméras (qhyccd) sont installés si la ligne correspondante de
requirements.txt est décommentée — comportement standard de pip.
"""

import argparse
import os
import subprocess
import sys
import venv


def creer_venv(chemin_venv, fichier_requirements):
    """Crée un venv (avec pip) et installe requirements.txt dedans."""
    print(f"[avastack-setup] creation du venv : {chemin_venv}", flush=True)
    builder = venv.EnvBuilder(with_pip=True, clear=False)
    builder.create(chemin_venv)
    python_exe = (os.path.join(chemin_venv, "Scripts", "python.exe") if os.name == "nt"
                  else os.path.join(chemin_venv, "bin", "python"))
    if not os.path.isfile(python_exe):
        raise RuntimeError(f"python.exe introuvable dans le venv : {chemin_venv}")

    print(f"[avastack-setup] mise a jour de pip...", flush=True)
    subprocess.check_call([python_exe, "-m", "pip", "install", "--upgrade", "pip",
                           "--quiet"])

    print(f"[avastack-setup] installation des dependances : {fichier_requirements}",
          flush=True)
    subprocess.check_call([python_exe, "-m", "pip", "install", "-r",
                           fichier_requirements, "--quiet"])
    print("[avastack-setup] venv pret.", flush=True)
    return python_exe


def main():
    parser = argparse.ArgumentParser(description="Outils d'installation AVAStack")
    sous = parser.add_subparsers(dest="commande", required=True)

    p_venv = sous.add_parser("create-venv", help="cree un venv + dependances")
    p_venv.add_argument("--venv-dir", required=True)
    p_venv.add_argument("--requirements", required=True)

    args = parser.parse_args()
    if args.commande == "create-venv":
        creer_venv(args.venv_dir, args.requirements)


if __name__ == "__main__":
    main()
