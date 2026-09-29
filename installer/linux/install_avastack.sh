#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# install_avastack.sh — installateur LINUX pour AVAStack (live stacking).
#
# Déploiement LOCAL, sans droits administrateur : l'application est copiée dans
# ~/.local/share/AVAStack (modifiable avec --prefix), un venv y est créé et les
# dépendances y sont installées, puis un lanceur (~/.local/bin/avastack) et une
# entrée de menu (~/.local/share/applications/avastack.desktop) sont écrits.
#
# DIFFÉRENCE DE FOND AVEC WINDOWS : sous Linux, Tkinter n'existe PAS sur pip —
# il vient du paquet système `python3-tk`. Le script teste les prérequis AVANT
# de copier quoi que ce soit et dit exactement quelle commande lancer sur
# Debian/Ubuntu, Fedora, Arch.
#
# CAMÉRAS : cette version n'installe AUCUNE caméra — aucun SDK constructeur
# (*.so) n'est embarqué et les paquets pip `qhyccd`/`zwoasi` ne sont PAS
# installés. L'application fonctionne en mode « Dossier surveillé »,
# « Composition multi-dossiers », « OpenCV » et « Simulée (démo) ». L'option
# --cameras ajoute les paquets pip caméras et copie les bibliothèques
# constructeurs présentes dans le paquet.
#
# La version installée est lue dans avastack/__init__.py (AVASTACK_VERSION),
# source unique de vérité (cf. CLAUDE.md).

set -euo pipefail

# Le script utilise bash (BASH_SOURCE, tableaux) : lancé avec sh/dash, il
# échouerait de façon obscure — on le dit franchement.
if [ -z "${BASH_VERSION:-}" ]; then
    printf '[AVAStack] ERREUR : ce script doit être lancé avec bash.\n' >&2
    printf '[AVAStack] Exemple : bash install_avastack.sh --prefix ~/.local/share/AVAStack\n' >&2
    exit 1
fi

NOM_APP="AVAStack"
VERSION_MIN_PY="3.10"
DOSSIER_DEFAUT="$HOME/.local/share/AVAStack"

OPTION_CAMERAS=0
OPTION_RACCOURCI=1
OPTION_FORCER=0
OPTION_PURGER=0
ACTION="installer"
PREFIX=""
PY=""

# --- messages (jamais de sortie muette) -------------------------------------
info()   { printf '[AVAStack] %s\n' "$*"; }
avis()   { printf '[AVAStack] ATTENTION : %s\n' "$*" >&2; }
erreur() { printf '[AVAStack] ERREUR : %s\n' "$*" >&2; }

usage() {
    cat <<'FIN'
Installateur Linux AVAStack — usage :
  bash install_avastack.sh [options]

OPTIONS
  --prefix DIR       dossier d'installation (défaut : ~/.local/share/AVAStack)
  --cameras          installe aussi les paquets pip caméras (qhyccd, zwoasi)
                     et copie les bibliothèques constructeurs présentes
  --sans-raccourci   n'écrit ni ~/.local/bin/avastack ni l'entrée .desktop
  --forcer           passe outre un garde-fou : Tkinter absent (installation
                     inutilisable telle quelle) ou dossier supprimé sans
                     VERSION.txt (--desinstaller)
  --desinstaller     supprime l'installation (GARDE les réglages)
  --purger           avec --desinstaller : supprime AUSSI les réglages
  -h, --aide         affiche cette aide

Sans --cameras (défaut) : aucune caméra n'est installée — l'application
fonctionne en mode Dossier surveillé / Composition / OpenCV / Simulée (démo).
FIN
}

aide_prerequis() {
    cat <<'FIN'
Prérequis Linux (à installer AVANT, avec les droits administrateur) :
  Debian / Ubuntu / Linux Mint :
      sudo apt install python3 python3-venv python3-tk libgl1 libglib2.0-0 libusb-1.0-0
  Fedora :
      sudo dnf install python3 python3-tkinter mesa-libGL glib2 libusb1
  Arch / Manjaro :
      sudo pacman -S python python-pip tk libgl libusb
python3-tk est INDISPENSABLE : Tkinter n'est pas installable avec pip.
FIN
}

# --- emplacements et outils -------------------------------------------------
dossier_script() {
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd
}

# Racine du paquet = dossier qui contient AVAStack.py. Le script vit dans
# installer/ dans le paquet et installer/linux/ dans le dépôt : on remonte
# jusqu'à 4 niveaux.
trouver_racine() {
    local d i
    d="$(dossier_script)"
    for i in 1 2 3 4; do
        if [ -f "$d/AVAStack.py" ] && [ -d "$d/avastack" ]; then
            printf '%s\n' "$d"
            return 0
        fi
        d="$(dirname -- "$d")"
    done
    return 1
}

lire_version() {
    local f="$1/avastack/__init__.py" v=""
    if [ -f "$f" ]; then
        v="$(sed -n 's/^AVASTACK_VERSION[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$f" | head -n 1)"
    fi
    if [ -z "$v" ]; then
        v="inconnue"
    fi
    printf '%s\n' "$v"
}

trouver_python() {
    local c chemin
    for c in python3 python; do
        chemin="$(command -v "$c" 2>/dev/null || true)"
        if [ -z "$chemin" ]; then
            continue
        fi
        if "$chemin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            printf '%s\n' "$chemin"
            return 0
        fi
    done
    return 1
}

# --- prérequis --------------------------------------------------------------
verifier_prerequis() {
    local tk_ok=1
    if ! "$PY" -c 'import ensurepip' >/dev/null 2>&1; then
        erreur "le module « venv » de $PY est incomplet (ensurepip absent)."
        aide_prerequis
        exit 1
    fi
    info "Python       : $("$PY" --version 2>&1)  ($PY)"
    if "$PY" -c 'import tkinter' >/dev/null 2>&1; then
        info "Tkinter      : OK"
    else
        tk_ok=0
        if [ "$OPTION_FORCER" -eq 1 ]; then
            avis "Tkinter absent — installation forcée : AVAStack ne pourra PAS"
            avis "démarrer avant l'installation de python3-tk."
        else
            erreur "Tkinter est absent de $PY : AVAStack ne peut pas démarrer sans lui."
            aide_prerequis
            erreur "Relance ensuite la même commande."
            exit 1
        fi
    fi
    if [ "$tk_ok" -eq 1 ]; then
        info "Prérequis    : OK"
    fi
}

# --- copie de l'application -------------------------------------------------
copier_application() {
    local src="$1" dst="$2" f
    info "copie de l'application vers $dst"
    mkdir -p "$dst"
    cp -f "$src/AVAStack.py" "$dst/"
    cp -f "$src/veralux_core_headless.py" "$dst/"
    cp -f "$src/requirements.txt" "$dst/"
    rm -rf "$dst/avastack"
    cp -R "$src/avastack" "$dst/avastack"
    find "$dst/avastack" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    # Bancs installés : les OUTILS DE DIAGNOSTIC MATÉRIEL caméra
    # seulement (`bancs/cameras/_diag_*.py`). Le paquet ne contient QUE
    # ceux-là : les bancs de régression caméra et tous les autres bancs
    # sont des outils de dev, jamais embarqués (décision de projet,
    # 27/09/2026 : l'installation ne contient que des outils utilisables
    # par l'utilisateur). Arbre copié tel quel.
    if [ -d "$src/bancs" ]; then
        rm -rf "$dst/bancs"
        cp -R "$src/bancs" "$dst/bancs"
        find "$dst/bancs" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    fi
    # Lisez-moi utilisateur : racine du paquet, ou installer/linux/ quand le
    # script est lancé depuis le dépôt (jamais celui de Windows).
    for f in "$src/LISEZMOI.txt" "$src/installer/linux/LISEZMOI.txt"; do
        if [ -f "$f" ]; then
            cp -f "$f" "$dst/LISEZMOI.txt"
            break
        fi
    done
    # Outil de création du venv (stdlib seulement) : copié avec l'application
    # pour que l'installation reste auto-suffisante (mise à jour, réparation).
    for f in "$src/installer/common/avastack_setup.py" "$src/installer/avastack_setup.py"; do
        if [ -f "$f" ]; then
            mkdir -p "$dst/installer/common"
            cp -f "$f" "$dst/installer/common/avastack_setup.py"
            break
        fi
    done
}

# --- dépendances ------------------------------------------------------------
filtrer_requirements() {
    local source="$1" destination="$2"
    if [ "$OPTION_CAMERAS" -eq 1 ]; then
        cp -f "$source" "$destination"
    else
        # Caméras NON installées (réglage livré) : on retire les paquets
        # caméras de la liste. L'application démarre sans eux — leurs imports
        # sont PARESSEUX (dans les méthodes des classes caméra), l'absence de
        # SDK se voit donc à l'ouverture d'une source caméra, jamais au
        # démarrage (mode dossier / simulé pleinement fonctionnel).
        awk '!/^[[:space:]]*(qhyccd|zwoasi)[[:space:]]*$/' "$source" > "$destination"
    fi
}

creer_venv() {
    local venv="$1" requirements="$2" helper
    helper="$PREFIX/installer/common/avastack_setup.py"
    if [ -f "$helper" ]; then
        "$PY" "$helper" create-venv --venv-dir "$venv" --requirements "$requirements"
    else
        info "création du venv : $venv"
        "$PY" -m venv "$venv"
        "$venv/bin/python" -m pip install --upgrade pip --quiet
        "$venv/bin/python" -m pip install -r "$requirements" --quiet
    fi
    if [ ! -x "$venv/bin/python" ]; then
        erreur "venv incomplet : $venv/bin/python absent."
        erreur "Sur Debian/Ubuntu : sudo apt install python3-venv, puis relance."
        exit 1
    fi
}

# --- caméras (option --cameras) ---------------------------------------------
copier_sdk_cameras() {
    local src="$1" dst="$2" d f nom vus="" nb=0
    for d in "$src" "$src/sdk" "$src/installer"; do
        for f in "$d"/lib*.so "$d"/lib*.so.* "$d"/*.so "$d"/*.dylib "$d"/lib*.dylib; do
            if [ -f "$f" ]; then
                nom="$(basename -- "$f")"
                case " $vus " in
                    *" $nom "*) continue ;;
                esac
                vus="$vus $nom"
                cp -f "$f" "$dst/"
                info "bibliothèque copiée : $nom"
                nb=$((nb + 1))
            fi
        done
    done
    if [ "$nb" -eq 0 ]; then
        avis "aucune bibliothèque constructeur (*.so) trouvée dans le paquet."
        avis "Les caméras resteront indisponibles : voir LISEZMOI.txt."
    fi
}

poser_regles_udev() {
    local src="$1" f regles=()
    for f in "$src"/*.rules "$src/sdk"/*.rules; do
        if [ -f "$f" ]; then
            regles+=("$f")
        fi
    done
    if [ "${#regles[@]}" -eq 0 ]; then
        info "aucun fichier de règles udev (*.rules) fourni : les caméras"
        info "resteront invisibles pour un utilisateur non root (voir LISEZMOI)."
        return 0
    fi
    for f in "${regles[@]}"; do
        info "pose des règles udev (sudo) : $(basename -- "$f")"
        if ! sudo install -m 644 "$f" /lib/udev/rules.d/; then
            avis "échec pour $f — à lancer à la main :"
            avis "  sudo install -m 644 \"$f\" /lib/udev/rules.d/"
        fi
    done
    sudo udevadm control --reload-rules >/dev/null 2>&1 || true
    info "débranche puis rebranche la caméra pour que les règles s'appliquent."
}

# --- lanceurs ---------------------------------------------------------------
ecrire_lanceur() {
    local dossier="$1" fichier="$1/lancer_avastack.sh"
    {
        printf '#!/usr/bin/env bash\n'
        printf '# Lanceur AVAStack — généré par install_avastack.sh le %s. Ne pas éditer.\n' "$(date '+%Y-%m-%d %H:%M')"
        printf 'exec "%s/venv/bin/python" "%s/AVAStack.py" "$@"\n' "$dossier" "$dossier"
    } > "$fichier"
    chmod 755 "$fichier"
    info "lanceur écrit : $fichier"
}

ecrire_raccourcis() {
    local lanceur="$1" binaires apps exec_cmd
    binaires="$HOME/.local/bin"
    apps="$HOME/.local/share/applications"
    mkdir -p "$binaires" "$apps"
    ln -sf "$lanceur" "$binaires/avastack"
    info "commande écrite : $binaires/avastack"
    exec_cmd="$lanceur"
    case "$lanceur" in
        *" "*) exec_cmd="\"$lanceur\"" ;;
    esac
    {
        printf '[Desktop Entry]\n'
        printf 'Type=Application\n'
        printf 'Version=1.0\n'
        printf 'Name=AVAStack\n'
        printf 'GenericName=Live stacking\n'
        printf 'Comment=Empilement temps réel des brutes (live stacking)\n'
        printf 'Exec=%s\n' "$exec_cmd"
        printf 'Path=%s\n' "$PREFIX"
        printf 'Terminal=false\n'
        printf 'Categories=Science;Astronomy;\n'
        printf 'StartupNotify=false\n'
    } > "$apps/avastack.desktop"
    chmod 644 "$apps/avastack.desktop"
    info "entrée de menu écrite : $apps/avastack.desktop"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$apps" >/dev/null 2>&1 || true
    fi
    case ":$PATH:" in
        *":$binaires:"*) ;;
        *) avis "$binaires n'est pas dans ton PATH : utilise « ~/.local/bin/avastack »"
           avis "ou ajoute-le (export PATH=\"\$HOME/.local/bin:\$PATH\")." ;;
    esac
}

# --- vérification -----------------------------------------------------------
verifier_application() {
    local py="$PREFIX/venv/bin/python" err_demarrage
    info "vérification de l'installation"
    if "$py" -c 'import tkinter' >/dev/null 2>&1; then
        info "  Tkinter (interface)       OK"
    else
        avis "  Tkinter ABSENT dans le venv — installe python3-tk, puis relance."
    fi
    if "$py" -c 'import numpy, cv2, PIL' >/dev/null 2>&1; then
        info "  numpy / OpenCV / Pillow   OK"
    else
        avis "  numpy/OpenCV/Pillow inutilisables — voir l'erreur exacte :"
        avis "    \"$py\" -c \"import cv2\""
        avis "  si elle mentionne libGL : sudo apt install libgl1 libglib2.0-0"
    fi
    if "$py" -c 'import astropy' >/dev/null 2>&1; then
        info "  astropy (FITS)            OK"
    else
        avis "  astropy absent : lecture et écriture FITS limitées."
    fi
    if "$py" -c 'import qhyccd' >/dev/null 2>&1; then
        info "  caméras QHY (pip qhyccd)  OK"
    else
        info "  caméras                   non installées (mode dossier / simulé) — réglage livré"
    fi
    # v2.38.7 : DÉMARRAGE RÉEL de l'application — on IMPORTE l'interface dans le
    # venv, depuis le dossier d'installation (aucune fenêtre ouverte). C'est ce
    # test qui manquait le 27/09/2026 : l'installateur concluait « installation
    # terminée », puis l'application ne s'ouvrait pas (« rien du tout : aucune
    # fenêtre, aucun message ») et la cause exacte n'existait nulle part.
    if err_demarrage="$( cd "$PREFIX" && "$py" -c 'import avastack.ui.app' 2>&1 )"
    then
        info "  démarrage (imports)       OK"
    else
        avis "  L'APPLICATION NE PEUT PAS DÉMARRER — erreur exacte :"
        printf '%s\n' "$err_demarrage" | sed 's/^/      /' >&2 || true
        avis "  corrige la cause ci-dessus, puis relance ce script ; le"
        avis "  journal de l'application (journal.txt) gardera la trace des"
        avis "  essais suivants : ${XDG_CONFIG_HOME:-$HOME/.config}/AVAStack/"
    fi
}

# --- désinstallation --------------------------------------------------------
desinstaller() {
    local prefix="$1" config
    if [ ! -f "$prefix/VERSION.txt" ]; then
        erreur "$prefix ne ressemble pas à une installation AVAStack (VERSION.txt absent)."
        erreur "Vérifie le --prefix ; ajoute --forcer pour passer outre ce garde-fou."
        if [ "$OPTION_FORCER" -ne 1 ]; then
            exit 2
        fi
        avis "garde-fou ignoré (--forcer) : poursuite de la suppression."
    fi
    info "désinstallation de $prefix"
    rm -rf "$prefix"
    rm -f "$HOME/.local/bin/avastack"
    rm -f "$HOME/.local/share/applications/avastack.desktop"
    config="${XDG_CONFIG_HOME:-$HOME/.config}/AVAStack"
    if [ "$OPTION_PURGER" -eq 1 ]; then
        rm -rf "$config"
        info "réglages supprimés : $config"
    else
        info "réglages conservés : $config/config.json"
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
    fi
}

# --- programme --------------------------------------------------------------
main() {
    local racine version requirements_installe lanceur script_abs
    script_abs="$(dossier_script)/$(basename -- "${BASH_SOURCE[0]}")"

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --prefix)
                if [ "$#" -lt 2 ]; then
                    erreur "--prefix attend un chemin."
                    exit 2
                fi
                PREFIX="$2"
                shift 2
                ;;
            --prefix=*)     PREFIX="${1#--prefix=}"; shift ;;
            --cameras)      OPTION_CAMERAS=1; shift ;;
            --sans-raccourci) OPTION_RACCOURCI=0; shift ;;
            --forcer)       OPTION_FORCER=1; shift ;;
            --purger)       OPTION_PURGER=1; shift ;;
            --desinstaller) ACTION="desinstaller"; shift ;;
            -h|--aide)      usage; exit 0 ;;
            *)
                erreur "option inconnue : $1"
                usage >&2
                exit 2
                ;;
        esac
    done

    if [ -z "$PREFIX" ]; then
        PREFIX="$DOSSIER_DEFAUT"
    fi
    case "$PREFIX" in
        /*) ;;
        *) PREFIX="$(pwd)/$PREFIX" ;;
    esac
    case "$PREFIX" in
        /) erreur "refus d'installer à la racine du système."; exit 2 ;;
    esac
    PREFIX="${PREFIX%/}"

    if [ "$ACTION" = "desinstaller" ]; then
        desinstaller "$PREFIX"
        return 0
    fi

    racine="$(trouver_racine)" || {
        erreur "AVAStack.py introuvable autour de $(dossier_script)."
        erreur "Lance ce script depuis le dossier extrait du paquet, ou depuis le dépôt."
        exit 1
    }
    if [ "$PREFIX" = "$racine" ]; then
        erreur "le dossier d'installation est le dossier du paquet : choisis-en un autre (--prefix)."
        exit 2
    fi
    PY="$(trouver_python)" || {
        erreur "aucun python3 >= $VERSION_MIN_PY trouvé."
        aide_prerequis
        exit 1
    }
    version="$(lire_version "$racine")"

    echo
    info "AVAStack $version — installateur Linux"
    info "dossier d'installation : $PREFIX"
    if [ "$OPTION_CAMERAS" -eq 1 ]; then
        info "caméras : option --cameras demandée"
    else
        info "caméras : NON installées (mode dossier / composition / OpenCV / simulé)"
    fi
    echo

    verifier_prerequis
    copier_application "$racine" "$PREFIX"
    printf 'AVAStack %s\ninstallé le %s par installer/install_avastack.sh\n' \
        "$version" "$(date '+%Y-%m-%d %H:%M')" > "$PREFIX/VERSION.txt"
    if [ "$OPTION_CAMERAS" -eq 1 ]; then
        copier_sdk_cameras "$racine" "$PREFIX"
    fi

    requirements_installe="$PREFIX/requirements-installation.txt"
    filtrer_requirements "$PREFIX/requirements.txt" "$requirements_installe"
    creer_venv "$PREFIX/venv" "$requirements_installe"
    rm -f "$requirements_installe"

    ecrire_lanceur "$PREFIX"
    lanceur="$PREFIX/lancer_avastack.sh"
    if [ "$OPTION_RACCOURCI" -eq 1 ]; then
        ecrire_raccourcis "$lanceur"
    fi
    if [ "$OPTION_CAMERAS" -eq 1 ]; then
        poser_regles_udev "$racine"
    fi

    verifier_application

    echo
    info "installation terminée — AVAStack $version"
    echo "  Dossier        : $PREFIX"
    echo "  Interpréteur   : $PREFIX/venv/bin/python"
    if [ "$OPTION_RACCOURCI" -eq 1 ]; then
        echo "  Lancement      : avastack   (ou : bash $lanceur)"
        echo "                   ou l'entrée AVAStack du menu Applications"
    else
        echo "  Lancement      : bash $lanceur"
    fi
    echo "  Réglages       : ${XDG_CONFIG_HOME:-$HOME/.config}/AVAStack/config.json"
    echo "  Version notée  : $PREFIX/VERSION.txt"
    echo "  Sources        : Simulée (démo), Dossier surveillé, Composition, OpenCV"
    echo "  Caméras        : absentes — pour les ajouter le jour où les bibliothèques"
    echo "                   constructeurs (*.so) seront là :"
    echo "                     bash \"$script_abs\" --cameras    (voir LISEZMOI.txt)"
    echo "  Mise à jour    : fermer AVAStack, extraire le nouveau paquet, relancer"
    echo "                   ce script (le venv et les réglages sont réutilisés)."
    echo "  Désinstaller   : bash \"$script_abs\" --desinstaller [--purger]"
    echo
}

main "$@"



