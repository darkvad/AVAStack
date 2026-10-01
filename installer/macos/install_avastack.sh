#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# install_avastack.sh — installateur macOS pour AVAStack (live stacking).
#
# Déploiement LOCAL, sans droits administrateur : l'application est copiée dans
# ~/Library/Application Support/AVAStack/app (modifiable avec --prefix), un venv
# y est créé, les dépendances y sont installées, puis TROIS accès sont écrits :
#   • un lanceur de commande  ~/.local/bin/avastack ;
#   • un BUNDLE macOS          ~/Applications/AVAStack.app  (double-clic) ;
#   • le lanceur interne       <prefix>/lancer_avastack.sh (utilisé par les deux).
#
# POURQUOI UN BUNDLE : sous macOS, une application se lance par le Finder ; un
# simple script .sh n'est pas cliquable. Le bundle est MINIMAL (Info.plist +
# exécutable shell) : il n'embarque NI Python NI le venv, il pointe sur celui de
# l'installation — c'est ce qui permet de mettre à jour l'application sans
# retoucher le bundle. Il n'est pas signé ni notarisé (pas de compte Apple) : si
# macOS refuse de l'ouvrir, faire un clic droit → « Ouvrir », ou lever la
# quarantaine (xattr -dr com.apple.quarantine ~/Applications/AVAStack.app).
#
# DIFFÉRENCE DE FOND AVEC WINDOWS : sous macOS, Tkinter n'existe PAS sur pip et
# le Python du SYSTÈME (/usr/bin/python3) n'en a pas d'utilisable — il faut un
# Python de python.org (Tk inclus) ou Homebrew + `brew install python-tk@3.13`.
# Le script teste donc Tkinter RÉELLEMENT et refuse d'installer sans lui (sauf
# --forcer), en disant exactement quelle commande lancer.
#
# CAMÉRAS : cette version n'installe AUCUNE caméra — aucun SDK constructeur
# (*.dylib) n'est embarqué. L'application fonctionne en mode « Dossier
# surveillé », « Composition multi-dossiers », « OpenCV » et « Simulée (démo) ».
# L'option --cameras copie les bibliothèques constructeurs présentes dans le
# paquet et TENTE les paquets pip caméras (tolérant : un échec n'interrompt pas
# l'installation, ces paquets n'existant pas pour toutes les marques).
#
# ÉTAT DE CE SCRIPT (à dater, règle du projet) : écrit le 29/09/2026 à partir de
# l'installateur LINUX (éprouvé en réel sur Ubuntu), ADAPTÉ pour macOS et
# VÉRIFIÉ par analyse syntaxique (`bash -n`) et par construction du paquet — il
# n'a PAS encore été exécuté sur une machine macOS (aucune n'est disponible).
# La version installée est lue dans avastack/__init__.py (AVASTACK_VERSION),
# source unique de vérité (cf. CLAUDE.md).

set -euo pipefail

# Le script utilise bash (BASH_SOURCE, tableaux) : lancé avec sh/dash, il
# échouerait de façon obscure — on le dit franchement.
if [ -z "${BASH_VERSION:-}" ]; then
    printf '[AVAStack] ERREUR : ce script doit être lancé avec bash.\n' >&2
    printf '[AVAStack] Exemple : bash installer/install_avastack.sh\n' >&2
    exit 1
fi

NOM_APP="AVAStack"
VERSION_MIN_PY="3.10"
# Sous macOS, la config de l'application est ~/Library/Application Support/AVAStack
# (cf. avastack/config.py) : l'application vit dans un SOUS-DOSSIER `app` pour ne
# pas mélanger code, config.json, journal et catalogues dans un même dossier.
DOSSIER_DEFAUT="$HOME/Library/Application Support/AVAStack/app"
BUNDLE_DEFAUT="$HOME/Applications/AVAStack.app"
LANCEUR_DEFAUT="$HOME/.local/bin/avastack"

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
Installateur macOS AVAStack — usage :
  bash installer/install_avastack.sh [options]

OPTIONS
  --prefix DIR       dossier d'installation (défaut :
                     ~/Library/Application Support/AVAStack/app)
  --cameras          copie les bibliothèques constructeurs (*.dylib) présentes
                     et TENTE les paquets pip caméras (facultatif)
  --sans-raccourci   n'écrit ni ~/.local/bin/avastack ni AVAStack.app
  --forcer           passe outre un garde-fou : Tkinter absent (installation
                     inutilisable telle quelle), ou dossier supprimé sans
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
Prérequis macOS — un Python AVEC Tkinter (Tkinter n'est pas installable par pip) :

  Méthode python.org (recommandée, Tk inclus) :
      1. télécharger Python 3.12 ou 3.13 sur https://www.python.org/downloads/macos/
      2. installer le paquet .pkg, puis relancer ce script

  Méthode Homebrew :
      brew install python@3.13 python-tk@3.13

  À VÉRIFIER en une commande :
      python3 -c 'import tkinter; print(tkinter.TkVersion)'

  Le Python livré par macOS (/usr/bin/python3) n'a pas de Tkinter utilisable :
  il ne peut pas faire tourner AVAStack.
FIN
}

# --- emplacements ------------------------------------------------------------
dossier_script() {
    printf '%s\n' "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
}

trouver_racine() {
    local d
    for d in "$(dossier_script)" "$(dossier_script)/.." "$(dossier_script)/../.." \
             "$(pwd)"; do
        if [ -f "$d/AVAStack.py" ] && [ -d "$d/avastack" ]; then
            printf '%s\n' "$(cd "$d" && pwd)"
            return 0
        fi
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
    # Ordre : le python3 du PATH (python.org et Homebrew y posent un lien), puis
    # leurs emplacements usuels (Apple Silicon et Intel).
    for c in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 python; do
        if [ "${c#/}" = "$c" ]; then
            chemin="$(command -v "$c" 2>/dev/null || true)"
        else
            chemin="$c"
        fi
        if [ -z "$chemin" ] || [ ! -x "$chemin" ]; then
            continue
        fi
        if "$chemin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            printf '%s\n' "$chemin"
            return 0
        fi
    done
    return 1
}

# --- vérifications d'environnement ------------------------------------------
verifier_macos() {
    local systeme
    systeme="$(uname -s 2>/dev/null || echo inconnu)"
    if [ "$systeme" != "Darwin" ]; then
        erreur "ce script est l'installateur macOS (système détecté : $systeme)."
        erreur "Windows : avastack-setup-<version>.exe"
        erreur "Linux   : avastack-setup-<version>-linux.tar.gz"
        exit 1
    fi
}

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
            avis "démarrer avant l'installation d'un Python AVEC Tkinter."
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
    # Ressources : icone de l'application (assets/ a cote du package).
    if [ -d "$src/assets" ]; then
        rm -rf "$dst/assets"
        cp -R "$src/assets" "$dst/assets"
    fi
    find "$dst/avastack" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    # Bancs installés : les OUTILS DE DIAGNOSTIC MATÉRIEL caméra seulement
    # (`bancs/cameras/_diag_*.py`) — même règle que le paquet Linux : les bancs
    # de régression sont des outils de DEV et restent au dépôt.
    if [ -d "$src/bancs" ]; then
        rm -rf "$dst/bancs"
        cp -R "$src/bancs" "$dst/bancs"
        find "$dst/bancs" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    fi
    # Lisez-moi utilisateur : racine du paquet, ou installer/macos/ quand le
    # script est lancé depuis le dépôt (jamais celui de Windows ni de Linux).
    for f in "$src/LISEZMOI.txt" "$src/installer/macos/LISEZMOI.txt"; do
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
    # Les paquets caméras ne sont PAS installés d'office (réglage livré) : leurs
    # imports sont PARESSEUX dans le code, l'application démarre sans eux. Sous
    # macOS, `qhyccd` n'a même pas de roue : il est donc TOUJOURS retiré, et
    # `--cameras` les tentera séparément, de façon tolérante.
    awk '!/^[[:space:]]*(qhyccd|zwoasi)[[:space:]]*$/' "$source" > "$destination"
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
        erreur "Vérifie que $PY est bien un Python de python.org ou Homebrew, puis relance."
        exit 1
    fi
}

# --- caméras (option --cameras) ---------------------------------------------
copier_sdk_cameras() {
    local src="$1" dst="$2" d f nom vus="" nb=0
    # Sous macOS les SDK constructeurs sont des *.dylib (parfois dans un
    # framework, parfois un simple fichier à côté de l'application).
    for d in "$src" "$src/sdk" "$src/installer" \
             "$src"/*.framework/Versions/A "$src/sdk"/*.framework/Versions/A; do
        for f in "$d"/*.dylib "$d"/lib*.dylib "$d"/*.dylib.* ; do
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
        avis "aucune bibliothèque constructeur (*.dylib) trouvée dans le paquet."
        avis "Les caméras resteront indisponibles : voir LISEZMOI.txt."
    fi
    # Paquets pip caméras : TOLÉRANT (pas de roue macOS pour toutes les marques).
    for paquet in "zwoasi" "qhyccd"; do
        info "tentative du paquet pip caméras : $paquet"
        if ! "$PREFIX/venv/bin/python" -m pip install "$paquet" --quiet 2>/dev/null; then
            avis "le paquet « $paquet » n'a pas pu être installé : les caméras de"
            avis "cette marque resteront indisponibles (ce n'est pas bloquant)."
        fi
    done
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

ecrire_raccourci_cli() {
    local lanceur="$1" binaires
    binaires="$(dirname -- "$LANCEUR_DEFAUT")"
    mkdir -p "$binaires"
    {
        printf '#!/usr/bin/env bash\n'
        printf '# Lanceur AVAStack (ligne de commande) — généré le %s. Ne pas éditer.\n' "$(date '+%Y-%m-%d %H:%M')"
        printf 'exec "%s" "$@"\n' "$lanceur"
    } > "$LANCEUR_DEFAUT"
    chmod 755 "$LANCEUR_DEFAUT"
    info "lanceur de commande écrit : $LANCEUR_DEFAUT"
    case ":$PATH:" in
        *":$binaires:"*) ;;
        *) avis "$binaires n'est pas dans ton PATH."
           avis "Pour lancer « avastack » dans le Terminal, ajoute à ~/.zshrc :"
           avis "    export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
    esac
}

# Bundle macOS : le SEUL moyen de rendre l'application cliquable sans signer ni
# installer quoi que ce soit dans /Applications (droits administrateur requis).
ecrire_bundle() {
    local bundle="$1" version="$2" exe plist
    exe="$bundle/Contents/MacOS/AVAStack"
    plist="$bundle/Contents/Info.plist"
    rm -rf "$bundle"
    mkdir -p "$bundle/Contents/MacOS" "$bundle/Contents/Resources"
    {
        printf '#!/bin/bash\n'
        printf '# Lanceur AVAStack (bundle) — généré le %s. Ne pas éditer.\n' "$(date '+%Y-%m-%d %H:%M')"
        printf '# Le bundle ne contient ni Python ni venv : il pointe sur cette installation.\n'
        printf 'exec "%s/venv/bin/python" "%s/AVAStack.py" "$@"\n' "$PREFIX" "$PREFIX"
    } > "$exe"
    chmod 755 "$exe"
    cat > "$plist" <<FIN
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>AVAStack</string>
    <key>CFBundleDisplayName</key><string>AVAStack</string>
    <key>CFBundleIdentifier</key><string>org.avastack.livestacking</string>
    <key>CFBundleExecutable</key><string>AVAStack</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleVersion</key><string>$version</string>
    <key>CFBundleShortVersionString</key><string>$version</string>
    <key>LSMinimumSystemVersion</key><string>11.0</string>
    <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
FIN
    info "application cliquable écrite : $bundle"
    avis "bundle NON signé (pas de compte Apple) : si macOS refuse de l'ouvrir,"
    avis "faire un clic droit → « Ouvrir », ou lever la quarantaine :"
    avis "    xattr -dr com.apple.quarantine \"$bundle\""
}

# --- vérification -----------------------------------------------------------
verifier_application() {
    local py="$PREFIX/venv/bin/python" err_demarrage
    info "vérification de l'installation"
    if "$py" -c 'import tkinter' >/dev/null 2>&1; then
        info "  Tkinter (interface)       OK"
    else
        avis "  Tkinter ABSENT dans le venv : installe python-tk (Homebrew) ou un"
        avis "  Python de python.org, puis relance ce script."
    fi
    if "$py" -c 'import numpy, cv2, PIL' >/dev/null 2>&1; then
        info "  numpy / OpenCV / Pillow   OK"
    else
        avis "  numpy/OpenCV/Pillow inutilisables — voir l'erreur exacte :"
        avis "    \"$py\" -c \"import cv2\""
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
    # DÉMARRAGE RÉEL : on IMPORTE l'interface dans le venv depuis le dossier
    # d'installation (leçon v2.38.7 : une installation qui conclut « terminée »
    # alors que l'application ne s'ouvre pas est le pire des silences).
    if err_demarrage="$( cd "$PREFIX" && "$py" -c 'import avastack.ui.app' 2>&1 )"
    then
        info "  démarrage (imports)       OK"
    else
        avis "  L'APPLICATION NE PEUT PAS DÉMARRER — erreur exacte :"
        printf '%s\n' "$err_demarrage" | sed 's/^/      /' >&2 || true
        avis "  corrige la cause ci-dessus, puis relance ce script ; le journal"
        avis "  gardera la trace : $HOME/Library/Application Support/AVAStack/journal.txt"
    fi
}


# --- désinstallation --------------------------------------------------------
desinstaller() {
    local prefix="$1" config bundle
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
    if [ -f "$LANCEUR_DEFAUT" ]; then
        rm -f "$LANCEUR_DEFAUT"
        info "lanceur de commande supprimé : $LANCEUR_DEFAUT"
    fi
    bundle="$BUNDLE_DEFAUT"
    if [ -d "$bundle" ]; then
        rm -rf "$bundle"
        info "application cliquable supprimée : $bundle"
    fi
    config="$HOME/Library/Application Support/AVAStack"
    if [ "$OPTION_PURGER" -eq 1 ]; then
        rm -rf "$config"
        info "réglages supprimés : $config"
    else
        info "réglages conservés : $config/config.json"
    fi
}

# --- programme --------------------------------------------------------------
main() {
    local racine version requirements_installe lanceur config_journal

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
            --prefix=*)       PREFIX="${1#--prefix=}"; shift ;;
            --cameras)        OPTION_CAMERAS=1; shift ;;
            --sans-raccourci) OPTION_RACCOURCI=0; shift ;;
            --forcer)         OPTION_FORCER=1; shift ;;
            --purger)         OPTION_PURGER=1; shift ;;
            --desinstaller)   ACTION="desinstaller"; shift ;;
            -h|--aide)        usage; exit 0 ;;
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

    verifier_macos

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
    info "AVAStack $version — installateur macOS"
    info "dossier d'installation : $PREFIX"
    if [ "$OPTION_CAMERAS" -eq 1 ]; then
        info "caméras : option --cameras demandée"
    else
        info "caméras : NON installées (mode dossier / composition / OpenCV / simulé)"
    fi
    info "première version macOS : signale ce qui bloque, c'est ainsi qu'elle s'améliore."
    echo

    verifier_prerequis
    copier_application "$racine" "$PREFIX"
    printf 'AVAStack %s\ninstallé le %s par installer/install_avastack.sh (macOS)\n' \
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
        ecrire_raccourci_cli "$lanceur"
        ecrire_bundle "$BUNDLE_DEFAUT" "$version"
    fi

    verifier_application

    echo
    info "installation terminée — AVAStack $version"
    echo "  Dossier        : $PREFIX"
    echo "  Interpréteur   : $PREFIX/venv/bin/python"
    if [ "$OPTION_RACCOURCI" -eq 1 ]; then
        echo "  Double-clic    : $BUNDLE_DEFAUT"
        echo "  Terminal       : $LANCEUR_DEFAUT"
    else
        echo "  Lancement      : bash \"$lanceur\""
    fi
    config_journal="$HOME/Library/Application Support/AVAStack"
    echo "  Journal        : $config_journal/journal.txt"
    echo
    echo "Première utilisation : les données Gaia (catalogue, spectres, base SPCC)"
    echo "se téléchargent depuis la fenêtre « Astrométrie » (boutons ⬇) — Siril"
    echo "n'est plus nécessaire. Détails : LISEZMOI.txt."
    return 0
}

main "$@"

