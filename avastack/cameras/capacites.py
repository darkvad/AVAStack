# -*- coding: utf-8 -*-
"""Modèle commun des CAPACITÉS d'une caméra, détectées EN DYNAMIQUE.

Objectif (Alain, 19/09/2026) : pour CHAQUE marque, interroger la caméra
BRANCHÉE — n'importe laquelle, pas seulement celles qu'Alain possède —
et en déduire tout ce que l'application doit adapter : plages
d'exposition / gain / offset, présence du TEC et de sa plage de consigne,
binning, ROI, formats, USB3, ST4, roue à filtres…

Chaque classe de caméra implémente `detecter_capacites()` sur une caméra
OUVERTE (les SDK exigent l'ouverture pour la plupart de ces lectures) et
renvoie un objet `Capacites`. RIEN n'est codé en dur par modèle : tout ce
qui est dans l'objet vient des réponses du SDK. La seule table fixe est
GAIN_UNITAIRE_CONNU, qui sert à ANNOTER le verdict (jamais à régler).

État par marque (constat 19/09/2026, exports des DLL réellement livrées ;
complété pour QHY par la sonde ctypes native, jalon 30/31) :
  - Player One : POAGetConfigsCount / POAGetConfigAttributes (sonde
    POASonde de cameras/playerone.py, validée par _test_camera_playerone) ;
  - ZWO : ASIGetNumOfControls / ASIGetControlCaps (ASICamera2.dll) ;
  - SVBONY : SVBGetNumOfControls / SVBGetControlCaps (SVBCameraSDK.dll) ;
  - QHY : le binding Python (paquet qhyccd) n'expose AUCUNE fonction de
    plages → relevé NATIF par ctypes (qhyct.py : plages MinMaxStep +
    roue CFW) fait À L'OUVERTURE, traduit par QHYCamera.detecter_capacites.

⚠ Jalon 32 : le NUMÉROTAGE des contrôles DIFFÈRE par marque (enums
officielles des SDK — cf. CID_CONTROLES_PAR_MARQUE). Le câblage de l'UI
interroge des RÔLES (« gain », « offset »…) via Capacites.plage(), JAMAIS
un cid littéral : « 6 » = gain QHY, mais balance des blancs B chez
Player One et « Flip » chez SVBONY — un curseur construit dessus serait
FAUX même si la sonde a bien répondu.
"""

# Gains unitaires CONNUS (capteur → gain SDK où e-/ADU ≈ 1, spec
# constructeur ou relevé réel d'Alain). Table CROISSANTE : chaque caméra
# testée la complète. Jamais utilisée pour RÉGLER la caméra — seulement
# pour annoter le verdict (« le gain unitaire est dans la plage »).
GAIN_UNITAIRE_CONNU = {
    "IMX585": 210,      # Player One Uranus-C Pro (demande d'Alain, 19/09/2026)
}


# --- Rôles → id de contrôle PAR MARQUE (jalon 32) ----------------------------
# Chaque SDK numérote SES contrôles à sa façon : ce sont les enums
# officielles, stables PAR MARQUE (pas par modèle). Le câblage de l'UI
# interroge des RÔLES via Capacites.plage(), jamais un cid littéral —
# un cid QHY est sans sens ailleurs (« 6 » = gain QHY, mais balance des
# blancs B chez Player One, « Flip » chez SVBONY).
# QHY : contrôles natifs (jalon 30, relevés par GetQHYCCDParamMinMaxStep) ;
# ZWO : ASI_CONTROL_TYPE (ASICamera2.h) ; SVBONY : SVB_CONTROL_TYPE
# (SVBCameraSDK.h — 13 = BlackLevel, l'« offset » du SDK SVB) ; Player One :
# POAConfigID (POACamera.h).
CID_CONTROLES_PAR_MARQUE = {
    "QHY":        {"expo_us": "8", "gain": "6", "offset": "7",
                   "tec_consigne": "18"},
    "Player One": {"expo_us": 0,  "gain": 1,  "offset": 7,
                   "tec_consigne": 17},
    "SVBONY":     {"expo_us": 1,  "gain": 0,  "offset": 13,
                   "tec_consigne": 15},
    "ZWO":        {"expo_us": 1,  "gain": 0,  "offset": 5,
                   "tec_consigne": 16},
}


def dedupliquer(valeurs):
    """→ liste SANS DOUBLON, ordre d'apparition conservé.

    Nécessaire car plusieurs SDK rendent des tableaux de taille FIXE dont la
    queue n'est pas un vrai terminateur mais du remplissage : le relevé réel
    de l'Uranus-C Pro (19/09/2026) a rendu 8 formats dont 4 × « RAW8 » (zéro
    de remplissage = valeur d'énumération valide, donc impossible à
    distinguer d'un vrai format). Dédupliquer garde l'information utile
    (RAW8 est bien supporté, il est listé une fois)."""
    vus, out = set(), []
    for v in valeurs:
        if v not in vus:
            vus.add(v)
            out.append(v)
    return out


class Controle:
    """Un contrôle du SDK, tel que lu EN DYNAMIQUE (pas un guess)."""

    def __init__(self, cid, nom="", type_val=0, mini=0, maxi=0, defaut=0,
                 ecrivable=False, lisible=True, auto=False, desc=""):
        self.cid = cid
        self.nom = nom
        self.type_val = type_val          # 0 = int, 1 = float, 2 = bool
        self.min = mini
        self.max = maxi
        self.defaut = defaut
        self.ecrivable = ecrivable
        self.lisible = lisible
        self.auto = auto
        self.desc = desc


class Capacites:
    """Ce que la caméra branchée a déclaré savoir faire."""

    def __init__(self, marque, modele="", capteur="", couleur=False,
                 bits=0, max_l=0, max_h=0, pixel_um=0.0):
        self.marque = marque
        self.modele = modele
        self.capteur = capteur
        self.couleur = couleur
        self.bits = bits
        self.max_l = max_l
        self.max_h = max_h
        self.pixel_um = pixel_um
        # plages (tuples (min, max)) ou None si le SDK ne les expose pas
        self.expo_us = None
        self.gain = None
        self.offset = None
        self.tec = False
        self.tec_consigne = None
        self.temperature_lisible = False
        self.bins = []
        self.bin_materiel = False
        self.formats = []
        self.usb3 = False
        self.st4 = False
        self.roue_slots = None
        self.serie = ""
        self.controles = []
        # extras : tout ce que la sonde a lu et qui n'a pas de champ dédié
        # (dict, clé = identifiant de contrôle de la marque, valeur = dict
        # min/max/step/valeur) — le câblage dynamique de l'UI lit ICI les
        # plages QHY natives (clés "6" gain, "7" offset, "8" expo, "18"
        # consigne TEC…) sans y coder le moindre modèle.
        self.extras = {}

    def plage_controle(self, cid):
        """→ (min, max, step) du contrôle `cid` depuis extras, ou None.

        Contrôles D'ENTRÉE seulement (ceux qu'un curseur peut régler) : les
        contrôles drapeaux (valeur sentinelle 0xFFFFFFFF, pas de plage) et
        les plages incohérentes (min >= max) sont rejetés — jamais de
        curseur construit sur une plage bidon."""
        e = self.extras.get(str(cid))
        if not isinstance(e, dict) or "min" not in e:
            return None
        mn, mx, st = float(e["min"]), float(e["max"]), float(e.get("step", 1))
        if mn >= mx or mx <= 0:
            return None
        return (mn, mx, st if st > 0 else 1.0)

    def plage(self, nom):
        """→ (min, max, step) du contrôle de RÔLE `nom` pour CETTE marque,
        ou None. Jalon 32 : les cid dépendent de la MARQUE (enums des SDK) —
        la résolution passe par CID_CONTROLES_PAR_MARQUE, la plage par
        plage_controle (relevé extras : step natif quand le SDK l'expose).
        Repli : plages déjà normalisées par la marque (tuples (min, max) —
        step inconnu → 1, curseur entier). Plage incohérente → None (jamais
        de curseur construit sur une plage bidon)."""
        if nom not in ("expo_us", "gain", "offset", "tec_consigne"):
            return None
        cid = CID_CONTROLES_PAR_MARQUE.get((self.marque or "").strip(),
                                           {}).get(nom)
        if cid is not None:
            p = self.plage_controle(cid)
            if p is not None:
                return p
        v = getattr(self, nom, None)
        if isinstance(v, (tuple, list)) and len(v) == 2:
            mn, mx = float(v[0]), float(v[1])
            if mx > mn:
                return (mn, mx, 1.0)
        return None

    # --- annotations -----------------------------------------------------------

    def gain_unitaire(self):
        """Gain unitaire CONNU du capteur (table GAIN_UNITAIRE_CONNU),
        None si inconnu — annotation uniquement, jamais un réglage."""
        cap = (self.capteur or "").upper()
        for capteur, g in GAIN_UNITAIRE_CONNU.items():
            if capteur in cap:
                return g
        return None

    # --- rendus ----------------------------------------------------------------

    def vers_dict(self):
        """→ dict sérialisable (JSON) — pour archiver/analyser hors ligne."""
        return {
            "marque": self.marque, "modele": self.modele,
            "capteur": self.capteur, "couleur": self.couleur,
            "bits": self.bits, "max_l": self.max_l, "max_h": self.max_h,
            "pixel_um": self.pixel_um,
            "expo_us": list(self.expo_us) if self.expo_us else None,
            "gain": list(self.gain) if self.gain else None,
            "offset": list(self.offset) if self.offset else None,
            "tec": self.tec,
            "tec_consigne": list(self.tec_consigne)
                            if self.tec_consigne else None,
            "temperature_lisible": self.temperature_lisible,
            "bins": list(self.bins), "bin_materiel": self.bin_materiel,
            "formats": list(self.formats),
            "usb3": self.usb3, "st4": self.st4,
            "roue_slots": self.roue_slots, "serie": self.serie,
            "controles": [c.__dict__ for c in self.controles],
            "extras": dict(self.extras),
        }

    def vers_texte(self):
        """→ résumé « possibilités » (une info par ligne, français clair)."""
        v = [f"CAMÉRA : {self.modele} ({self.marque})"]
        cap = self.capteur or "?"
        v.append(f"CAPTEUR : {cap} · {self.max_l}×{self.max_h} px · "
                 f"{self.bits} bits"
                 + (f" · pixel {self.pixel_um:.2f} µm" if self.pixel_um else "")
                 + (" · COULEUR" if self.couleur else " · mono"))
        if self.expo_us:
            v.append(f"EXPOSITION : {self.expo_us[0]} µs → {self.expo_us[1]}"
                     f" µs ({self.expo_us[1] / 1e6:.1f} s)")
        if self.gain:
            unite = self.gain_unitaire()
            note = ""
            if unite is not None:
                note = (f" — gain unitaire {unite} "
                        + ("DANS la plage"
                           if self.gain[0] <= unite <= self.gain[1]
                           else "⚠ HORS plage annoncée"))
            v.append(f"GAIN : {self.gain[0]} → {self.gain[1]} "
                     f"(unités SDK {self.marque}){note}")
        if self.offset is not None:
            v.append(f"OFFSET : {self.offset[0]} → {self.offset[1]}")
        if self.tec:
            t = "fiche TEC OUI"
            if self.tec_consigne:
                t += (f" · consigne {self.tec_consigne[0]}→"
                      f"{self.tec_consigne[1]} °C")
            t += (" · température "
                  + ("lisible ✓" if self.temperature_lisible
                     else "ILLISIBLE"))
            v.append("REFROIDISSEMENT : " + t)
        else:
            v.append("REFROIDISSEMENT : pas de TEC")
        v.append(f"BINNING : {self.bins}"
                 + (" · bin MATÉRIEL" if self.bin_materiel else ""))
        v.append(f"ROI : plein champ {self.max_l}×{self.max_h} (contraintes "
                 f"du SDK selon la marque — toujours relire la taille réelle)")
        if self.roue_slots is not None:
            v.append(f"ROUE À FILTRES : {self.roue_slots} slots")
        v.append("FORMATS : " + str(self.formats)
                 + f" · USB3 : {'oui' if self.usb3 else 'non'}"
                 + f" · ST4 : {'oui' if self.st4 else 'non'}")
        if self.serie:
            v.append(f"N° SÉRIE : {self.serie}")
        v.append(f"{len(self.controles)} contrôles énumérés")
        return "\n".join(v)
