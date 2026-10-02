#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""images_fiche.py — images de la FICHE Store (capture d'écran + tuiles).

POURQUOI CE SCRIPT (chantier « Microsoft Store », jalon 94, 02/10/2026) : la
fiche se remplit dans Partner Center, et les IMAGES y ont des tailles IMPOSÉES
(une capture d'écran Desktop ≥ 1366×768 ; des tuiles 1:1, 16:9 et 4:3). À ne PAS
confondre avec les vignettes DU PAQUET (StoreLogo, Square44/71/150/310,
Wide310×150), déjà produites par `build_msix.py` depuis l'icône : ce sont DEUX
choses différentes (cf. SOUMISSION.md § 5, question tranchée par Alain).

CE QUE FAIT CE SCRIPT, à partir d'UNE capture d'écran réelle de la fenêtre :
  1) il VÉRIFIE que la capture respecte le minimum Desktop (1366×768) ;
  2) il écrit la capture TELLE QUELLE : c'est le fichier à téléverser comme
     capture d'écran (aucun retraitement, donc aucune perte) ;
  3) il compose les TROIS tuiles aux tailles de la fiche :
       1:1  2160×2160   ·   16:9  1920×1080   ·   4:3  1200×900
     en gardant TOUTE la fenêtre visible (« contain ») sur un fond flou tiré de
     la capture elle-même — donc sans déformer ni rogner l'interface (option
     `--recadrer` : remplissage « cover » à la place, sans bandes) ;
  4) il permet de MASQUER des zones (`--masquer x,y,l,h`, répétable) : un chemin
     ou une adresse réseau PERSONNELS ne doivent JAMAIS partir dans la fiche
     (règle du dépôt : rien de personnel dans un document publié). La voie PROPRE
     reste une capture en mode « Simulée (démo) », sans chemin ni cible
     personnels (cf. SOUMISSION.md § 5) — le masquage est un pis-aller.

PIL (pillow) est déjà une dépendance du projet (outil de BUILD, comme dans
`build_msix.py`).

Usage (Windows) :
    python installer/windows/msix/images_fiche.py --capture "C:\\...\\capture.png"
    python installer/windows/msix/images_fiche.py --capture capture.png \
        --masquer "16,88,400,42" --masquer "16,455,400,125"
    python installer/windows/msix/images_fiche.py --verifier installer\\windows\\output\\fiche
"""
import argparse
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
except ImportError:                      # pillow est une dépendance du projet
    Image = ImageDraw = ImageEnhance = ImageFilter = None

# --- Exigences de la fiche (Microsoft, cf. SOUMISSION.md § 5) ----------------
MINIMUM = (1366, 768)                    # capture Desktop : minimum exigé
CAPTURE = "avastack-ecran-1.png"         # nom du fichier « capture d'écran »
TUILES = (("avastack-tuile-1x1-2160.png", 2160, 2160),
          ("avastack-tuile-16x9-1920x1080.png", 1920, 1080),
          ("avastack-tuile-4x3-1200x900.png", 1200, 900))
MASQUE = (0x20, 0x20, 0x24)              # bandeau neutre du masquage
GAMME_FOND = 0.35                        # assombrissement du fond flou


def racine_depot(depart):
    """Racine du dépôt (celle qui porte `AVAStack.py`), depuis un fichier."""
    chemin = os.path.abspath(depart)
    while True:
        if os.path.isfile(os.path.join(chemin, "AVAStack.py")):
            return chemin
        parent = os.path.dirname(chemin)
        if parent == chemin:
            raise SystemExit("Racine du depot introuvable (AVAStack.py).")
        chemin = parent


def _exiger_pil():
    """PIL est nécessaire à la composition : erreur claire s'il manque."""
    if Image is None:
        raise SystemExit("PIL (pillow) est necessaire : pip install pillow")


def lire_rectangles(options):
    """« x,y,l,h » (liste de textes) → liste de (x, y, l, h) entiers.

    Lève une erreur claire plutôt que de deviner : une zone mal écrite doit
    s'arrêter là, pas masquer le mauvais endroit de la capture.
    """
    rectangles = []
    for texte in options or ():
        morceaux = [m.strip() for m in texte.replace(";", ",").split(",")]
        if len(morceaux) != 4:
            raise SystemExit(
                "Zone de masquage invalide : %r (attendu « x,y,l,h »)." % texte)
        try:
            x, y, larg, haut = (int(float(m)) for m in morceaux)
        except ValueError:
            raise SystemExit(
                "Zone de masquage invalide : %r (quatre NOMBRES attendus)."
                % texte)
        if larg <= 0 or haut <= 0:
            raise SystemExit(
                "Zone de masquage invalide : %r (largeur/hauteur > 0)." % texte)
        rectangles.append((x, y, larg, haut))
    return rectangles


def masquer(image, rectangles, couleur=MASQUE):
    """Peint des bandeaux opaques (x, y, largeur, hauteur) dans la SOURCE.

    Appliqué AVANT la composition : les bandeaux suivent la mise à l'échelle et
    se retrouvent donc aussi dans les tuiles.
    """
    pinceau = ImageDraw.Draw(image)
    for x, y, larg, haut in rectangles:
        pinceau.rectangle((x, y, x + larg - 1, y + haut - 1), fill=couleur)
    return image


def _cover(image, larg, haut):
    """Remplit la cible sans déformer : échelle « cover » + recadrage centré."""
    base_l, base_h = image.size
    ratio = max(larg / base_l, haut / base_h)
    neuf = (max(larg, int(base_l * ratio + 0.5)),
            max(haut, int(base_h * ratio + 0.5)))
    redim = image.resize(neuf, Image.LANCZOS)
    dx, dy = (neuf[0] - larg) // 2, (neuf[1] - haut) // 2
    return redim.crop((dx, dy, dx + larg, dy + haut))


def _fond(image, larg, haut):
    """Fond de la cible : la capture floutée + assombrie, en « cover ».

    Il évite les bandes plates : les marges reprennent les couleurs réelles de
    la capture (floutées) sans jamais attirer l'œil (assombries).
    """
    flou = image.filter(ImageFilter.GaussianBlur(
        radius=max(8.0, min(image.size) / 40.0)))
    return ImageEnhance.Brightness(_cover(flou, larg, haut)).enhance(GAMME_FOND)


def composer(image, larg, haut, recadrer=False):
    """Image cible depuis la capture.

    Défaut : TOUTE la capture reste visible (« contain ») sur le fond flou — ni
    déformation, ni rognage de l'interface.  `recadrer=True` remplit la cible en
    « cover » : aucune bande, mais l'interface est rognée sur les bords.
    """
    if recadrer:
        return _cover(image, larg, haut)
    base_l, base_h = image.size
    ratio = min(larg / base_l, haut / base_h)
    neuf = (max(1, int(base_l * ratio + 0.5)), max(1, int(base_h * ratio + 0.5)))
    cible = _fond(image, larg, haut)
    cible.paste(image.resize(neuf, Image.LANCZOS),
                ((larg - neuf[0]) // 2, (haut - neuf[1]) // 2))
    return cible
def lire_capture(chemin):
    """Ouvre la capture et VÉRIFIE le minimum Desktop (1366×768).

    → image PIL « RGB » (jamais de canal alpha : la fiche veut un PNG opaque).
    """
    _exiger_pil()
    if not os.path.isfile(chemin):
        raise SystemExit("Capture introuvable : %s" % chemin)
    image = Image.open(chemin).convert("RGB")
    if image.size[0] < MINIMUM[0] or image.size[1] < MINIMUM[1]:
        raise SystemExit(
            "Capture trop petite : %dx%d (minimum Desktop exige : %dx%d).\n"
            "-> refais la capture avec une fenetre AU MOINS aussi grande "
            "(Microsoft accepte jusqu'au 4K 3840x2160)."
            % (image.size[0], image.size[1], MINIMUM[0], MINIMUM[1]))
    return image


def faire_images(chemin, dossier, rectangles=(), recadrer=False):
    """Écrit la capture + les trois tuiles dans `dossier`.

    → liste de (nom de fichier, (largeur, hauteur)) dans l'ordre d'écriture.
    """
    os.makedirs(dossier, exist_ok=True)
    source = lire_capture(chemin)
    if rectangles:
        masquer(source, rectangles)
    ecrits = []
    source.save(os.path.join(dossier, CAPTURE), "PNG")
    ecrits.append((CAPTURE, source.size))
    for nom, larg, haut in TUILES:
        composer(source, larg, haut, recadrer).save(
            os.path.join(dossier, nom), "PNG")
        ecrits.append((nom, (larg, haut)))
    return ecrits


def verifier(dossier):
    """Contrôle un dossier DÉJÀ écrit : tailles exactes exigées par la fiche.

    → liste de (nom attendu, présent ?, taille lue ou None).
    """
    _exiger_pil()
    attendus = [(CAPTURE, None)] + [(n, (l, h)) for n, l, h in TUILES]
    resultats = []
    for nom, taille in attendus:
        chemin = os.path.join(dossier, nom)
        if not os.path.isfile(chemin):
            resultats.append((nom, taille, False, None))
            continue
        lue = Image.open(chemin).size
        resultats.append((nom, taille, True, lue))
    return resultats
def principal():
    ici = os.path.dirname(os.path.abspath(__file__))
    defaut_sortie = os.path.join(racine_depot(ici), "installer", "windows",
                                 "output", "fiche")

    p = argparse.ArgumentParser(
        description="Images de la fiche Microsoft Store (capture + tuiles).")
    p.add_argument("--capture", default=None,
                   help="capture d'ecran REELLE de la fenetre (PNG)")
    p.add_argument("--sortie", default=defaut_sortie,
                   help="dossier des images (defaut : %s)" % defaut_sortie)
    p.add_argument("--masquer", action="append", default=[], metavar="x,y,l,h",
                   help="zone a neutraliser (chemins/adresses PERSONNELS) ; "
                        "repetable")
    p.add_argument("--recadrer", action="store_true",
                   help="tuiles en « cover » (sans bandes, interface rognee) "
                        "au lieu du defaut « contain » (fenetre entiere)")
    p.add_argument("--verifier", default=None, metavar="DOSSIER",
                   help="controle un dossier deja ecrit, puis sort")
    args = p.parse_args()

    if args.verifier:
        resultats = verifier(args.verifier)
        print("Verification de %s" % args.verifier)
        conforme = True
        for nom, taille, present, lue in resultats:
            if not present:
                print("  MANQUANT  %s" % nom)
                conforme = False
                continue
            if taille is None:              # la capture : minimum Desktop
                bon = lue[0] >= MINIMUM[0] and lue[1] >= MINIMUM[1]
                print("  %s  %s  %dx%d  (minimum %dx%d)"
                      % ("OK    " if bon else "ÉCHEC ", nom, lue[0], lue[1],
                         MINIMUM[0], MINIMUM[1]))
            else:
                bon = lue == taille
                print("  %s  %s  %dx%d  (attendu %dx%d)"
                      % ("OK    " if bon else "ÉCHEC ", nom, lue[0], lue[1],
                         taille[0], taille[1]))
            conforme &= bon
        print("")
        print("CONFORME" if conforme else "NON CONFORME")
        return 0 if conforme else 1

    if not args.capture:
        p.error("--capture est requis (ou --verifier DOSSIER).")

    rectangles = lire_rectangles(args.masquer)
    image = lire_capture(args.capture)
    print("Capture lue : %s  %dx%d  (minimum Desktop %dx%d : OK)"
          % (args.capture, image.size[0], image.size[1],
             MINIMUM[0], MINIMUM[1]))
    if rectangles:
        print("Masquage    : %d zone(s) neutralisee(s) %r"
              % (len(rectangles), rectangles))
        print("  ATTENTION : la voie PROPRE est une capture en mode "
              "« Simulee (demo) »,")
        print("              sans chemin ni cible personnels (SOUMISSION.md 5).")
    print("Tuiles      : %s"
          % ("recadrage « cover »" if args.recadrer
             else "fenetre entiere « contain » sur fond flou"))

    ecrits = faire_images(args.capture, args.sortie, rectangles, args.recadrer)
    print("")
    print("Ecrit dans %s :" % args.sortie)
    for nom, taille in ecrits:
        print("  %-34s %dx%d" % (nom, taille[0], taille[1]))
    print("")
    print("Fiche Store : televerser ces fichiers dans Partner Center")
    print("              (capture >= 1366x768 ; tuiles 1:1 / 16:9 / 4:3 —")
    print("              cf. installer/windows/msix/SOUMISSION.md, section 5).")
    return 0


if __name__ == "__main__":
    sys.exit(principal())