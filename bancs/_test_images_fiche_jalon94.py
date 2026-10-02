# -*- coding: utf-8 -*-
"""Banc du jalon 94 : images de la FICHE Store (capture + tuiles).

POURQUOI CE BANC : les images de la fiche ont des tailles IMPOSÉES par
Microsoft (capture Desktop ≥ 1366×768 ; tuiles 1:1, 16:9, 4:3). Ce banc vérifie
tout ce qui se vérifie SANS soumettre, sur une source SYNTHÉTIQUE (aucune vraie
capture n'est nécessaire) :

  [1] les exigences encodées (minimum Desktop + les trois tailles de tuile) ;
  [2] la lecture des zones de masquage « x,y,l,h » (et ses REFUS clairs) ;
  [3] la GÉOMÉTRIE de composition : « contain » garde TOUTE la fenêtre (bandes
      exactes, aucun étirement) ; « cover » remplit sans bande ;
  [4] le REFUS d'une capture plus petite que 1366×768 ;
  [5] le masquage est EFFECTIF dans le fichier écrit ;
  [6] `verifier()` distingue un dossier conforme d'un dossier faux ;
  [7] BOUT EN BOUT : `principal()` écrit les quatre fichiers puis les contrôle.

Exécution : python bancs/_test_images_fiche_jalon94.py
"""
import sys as _sys_banc, pathlib as _pl_banc
_RACINE = None
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _RACINE = str(_d_banc)
        _sys_banc.path.insert(0, _RACINE)
        break
import importlib.util
import os
import shutil
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


DOSSIER = os.path.join(_RACINE, "installer", "windows", "msix")
_spec = importlib.util.spec_from_file_location(
    "images_fiche", os.path.join(DOSSIER, "images_fiche.py"))
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

from PIL import Image                                            # noqa: E402

VERT = (0, 255, 0)


def _source(larg, haut, couleur=VERT):
    """Image unie : toute transformation déterministe y est MESURABLE."""
    return Image.new("RGB", (larg, haut), couleur)


def _pixel(chemin, x, y):
    with Image.open(chemin) as im:
        return im.convert("RGB").getpixel((x, y))


def _tailles(image):
    return image.size

# ==================================== [1] exigences encodees
print("[1] exigences de la fiche (tailles imposees par Microsoft)")
verifie(M.MINIMUM == (1366, 768), "minimum Desktop = 1366x768 (%r)" % (M.MINIMUM,))
verifie([(l, h) for _, l, h in M.TUILES] == [(2160, 2160), (1920, 1080),
                                             (1200, 900)],
        "tuiles 1:1 2160x2160, 16:9 1920x1080, 4:3 1200x900")
verifie(M.CAPTURE.endswith(".png"), "la capture est ecrite en PNG (%s)" % M.CAPTURE)
verifie(M.composer is not None and M.masquer is not None, "API attendue presente")

# ==================================== [2] lecture des zones de masquage
print("[2] zones de masquage « x,y,l,h » : lecture et REFUS clairs")
verifie(M.lire_rectangles([]) == [], "aucune zone -> liste vide")
verifie(M.lire_rectangles(["16,88,400,42"]) == [(16, 88, 400, 42)],
        "« 16,88,400,42 » -> (16, 88, 400, 42)")
verifie(M.lire_rectangles(["1;2;3;4", " 5 , 6 , 7 , 8 "])
        == [(1, 2, 3, 4), (5, 6, 7, 8)],
        "separateurs « ; » et espaces tolerés")
for mauvais, motif in (("1,2,3", "trois nombres"),
                       ("a,b,c,d", "texte"),
                       ("1,2,0,4", "largeur nulle")):
    try:
        M.lire_rectangles([mauvais])
        verifie(False, "REFUS attendu pour %r (%s)" % (mauvais, motif))
    except SystemExit:
        verifie(True, "refus de %r (%s)" % (mauvais, motif))
# ==================================== [3] geometrie de composition
print("[3] « contain » garde TOUTE la fenetre (bandes exactes, zero etirement)")
src = _source(1600, 900)
# 16:9 : le rapport est IDENTIQUE a la cible -> aucune bande
carre_16_9 = M.composer(src, 1920, 1080)
verifie(carre_16_9.size == (1920, 1080),
        "tuile 16:9 a la taille exacte (%dx%d)" % carre_16_9.size)
verifie(carre_16_9.getpixel((0, 0)) == VERT
        and carre_16_9.getpixel((1919, 1079)) == VERT,
        "16:9 : capture IDENTIQUE au rapport -> couvre toute la cible")
# 1:1 : 1600x900 -> 2160x1215, centre verticalement (dy = 472)
carre_1 = M.composer(src, 2160, 2160)
verifie(carre_1.size == (2160, 2160),
        "tuile 1:1 a la taille exacte (%dx%d)" % carre_1.size)
verifie(carre_1.getpixel((1080, 471)) != VERT
        and carre_1.getpixel((1080, 472)) == VERT
        and carre_1.getpixel((1080, 1686)) == VERT
        and carre_1.getpixel((1080, 1687)) != VERT,
        "1:1 : bandes EXACTES (haut 472 px, bas 473 px), fenetre au centre")
bande = carre_1.getpixel((1080, 100))
verifie(bande != VERT and bande[1] < 200,
        "1:1 : la bande est le fond ASSOMBRI (%r), pas la capture" % (bande,))
# 4:3 : 1600x900 -> 1200x675, centre verticalement (dy = 112)
carre_4_3 = M.composer(src, 1200, 900)
verifie(carre_4_3.size == (1200, 900),
        "tuile 4:3 a la taille exacte (%dx%d)" % carre_4_3.size)
verifie(carre_4_3.getpixel((600, 111)) != VERT
        and carre_4_3.getpixel((600, 112)) == VERT
        and carre_4_3.getpixel((600, 786)) == VERT
        and carre_4_3.getpixel((600, 787)) != VERT,
        "4:3 : bandes EXACTES (haut 112 px, bas 113 px), fenetre au centre")
# « cover » : aucune bande, la cible est entierement couverte
carre_cover = M.composer(src, 2160, 2160, recadrer=True)
verifie(carre_cover.size == (2160, 2160)
        and carre_cover.getpixel((0, 0)) == VERT
        and carre_cover.getpixel((2159, 2159)) == VERT,
        "« cover » : la cible est couverte jusqu'aux coins (aucune bande)")

# ==================================== [4] refus d'une capture trop petite
print("[4] une capture plus petite que 1366x768 est REFUSEE")
bac = tempfile.mkdtemp(prefix="banc94_")
petite = os.path.join(bac, "petite.png")
_source(800, 600).save(petite, "PNG")
try:
    M.faire_images(petite, os.path.join(bac, "refus"))
    verifie(False, "REFUS attendu pour une capture 800x600")
except SystemExit as err:
    message = str(err)
    verifie("1366x768" in message or "1366" in message,
            "refus explicite (message : %s)" % message.splitlines()[0])
verifie(not os.path.isfile(os.path.join(bac, "refus", M.CAPTURE)),
        "aucun fichier ecrit quand la capture est refusee")

# ==================================== [5] masquage effectif
print("[5] le masquage est EFFECTIF dans le fichier ecrit")
grande = os.path.join(bac, "grande.png")
_source(1600, 900).save(grande, "PNG")
sortie = os.path.join(bac, "masque")
ecrits = M.faire_images(grande, sortie, [(100, 100, 400, 50)])
ecran = os.path.join(sortie, M.CAPTURE)
verifie(_pixel(ecran, 300, 125) == M.MASQUE,
        "le centre de la zone masquee porte le bandeau %r" % (M.MASQUE,))
verifie(_pixel(ecran, 300, 300) == VERT,
        "hors zone : la capture est intacte")
verifie(_pixel(os.path.join(sortie, M.TUILES[0][0]), 400, 640) == M.MASQUE,
        "la tuile 1:1 porte AUSSI le bandeau (masquage AVANT composition)")
verifie(_pixel(os.path.join(sortie, M.TUILES[0][0]), 1080, 1080) == VERT,
        "la tuile 1:1 reste INTACTE hors de la zone masquee")
verifie([t[1] for t in ecrits] == [(1600, 900), (2160, 2160), (1920, 1080),
                                   (1200, 900)],
        "les quatre tailles annoncees sont celles ecrites")

# ==================================== [6] verifier() distingue conforme/faux
print("[6] verifier() distingue un dossier conforme d'un dossier faux")
resultats = M.verifier(sortie)
verifie(all(present for _, _, present, _ in resultats)
        and all(lue == attendu for _, attendu, _, lue in resultats
                if attendu is not None),
        "dossier conforme : %d fichiers aux tailles exactes" % len(resultats))
_source(10, 10).save(os.path.join(sortie, M.TUILES[1][0]), "PNG")
resultats = M.verifier(sortie)
faux = [(nom, lue) for nom, attendu, _, lue in resultats
        if attendu is not None and attendu != lue]
verifie(len(faux) == 1 and faux[0][0] == M.TUILES[1][0],
        "dossier faux : l'ecart est DESIGNEE (%r)" % (faux,))

# ==================================== [7] bout en bout : principal()
print("[7] bout en bout : principal() ecrit puis controle (code de sortie)")
final = os.path.join(bac, "final")
ancien_argv = sys.argv
try:
    sys.argv = ["images_fiche.py", "--capture", grande, "--sortie", final,
                "--masquer", "0,0,160,40"]
    code = M.principal()
    verifie(code == 0, "principal() -> code 0")
    verifie(all(os.path.isfile(os.path.join(final, nom))
                for nom in [M.CAPTURE] + [n for n, _, _ in M.TUILES]),
            "les quatre fichiers sont ecrits dans %s"
            % os.path.basename(final))
    sys.argv = ["images_fiche.py", "--verifier", final]
    code = M.principal()
    verifie(code == 0, "principal() --verifier -> code 0 (CONFORME)")
    _source(11, 11).save(os.path.join(final, M.CAPTURE), "PNG")
    sys.argv = ["images_fiche.py", "--verifier", final]
    code = M.principal()
    verifie(code == 1, "principal() --verifier -> code 1 (capture trop petite)")
finally:
    sys.argv = ancien_argv
    shutil.rmtree(bac, ignore_errors=True)

print("")
print("TOUT AU VERT" if ok else "DES ÉCHECS")
sys.exit(0 if ok else 1)