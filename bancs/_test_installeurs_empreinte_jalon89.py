# -*- coding: utf-8 -*-
"""Banc du jalon 89 : LES INSTALLATEURS WINDOWS VÉRIFIENT L'EMPREINTE DU PYTHON
TÉLÉCHARGÉ (v2.48.2) — plus le correctif de désinstallation.

POURQUOI : un testeur a reçu « Impossible d'exécuter un fichier depuis le dossier
temporaire... Erreur 4551 : une stratégie de contrôle d'application a bloqué ce
fichier ». La mesure (banc `_diag_execution_temp.ps1`) a montré que Smart App
Control, APPLIQUÉ, laisse pourtant exécuter depuis %TEMP% un fichier SIGNÉ — une
cause possible restait donc : un téléchargement INTERROMPU, donc un fichier
TRONQUÉ sans signature valide, parti à l'exécution avec un message
incompréhensible.

CE BANC VÉRIFIE :
  [1] l'empreinte SHA-256 du Python de python.org est déclarée dans les DEUX
      installateurs Windows, au format SHA-256, et les deux valeurs sont
      IDENTIQUES (deux chaînes recopiées finissent toujours par diverger : c'est
      ce banc qui les empêche de le faire en silence) ;
  [2] les DEUX vérifient AVANT d'exécuter, et les DEUX retentent une seconde fois
      quand le fichier est incomplet ou altéré ;
  [3] l'échec est DIT en clair (mot « INCOMPLET »), jamais un message obscur ;
  [4] le correctif de désinstallation : la marque « raccourcis : AUCUN » est
      ÉCRITE à l'installation ET RELUE à la désinstallation, et les raccourcis ne
      sont retirés que s'ils ont été créés ;
  [5] si le fichier téléchargé est présent localement, l'empreinte déclarée
      correspond bien au fichier RÉEL (contrôle direct, sinon « non vérifiée »).

Provenance de la valeur épinglée : relevée le 02/10/2026 d'un téléchargement
HTTPS de https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe dont la
signature Authenticode a été vérifiée comme **Valide** (signataire : Python
Software Foundation), taille 26 538 304 octets.

Exécution : python bancs/_test_installeurs_empreinte_jalon89.py
"""
import sys as _sys_banc, pathlib as _pl_banc
for _d_banc in _pl_banc.Path(__file__).resolve().parents:
    if (_d_banc / "AVAStack.py").is_file():
        _sys_banc.path.insert(0, str(_d_banc)); break
import hashlib
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):     # console Windows (cp1252)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ok = True


def verifie(cond, msg):
    global ok
    ok &= bool(cond)
    print(("  OK    " if cond else "  ÉCHEC ") + msg)


RACINE = str(_pl_banc.Path(__file__).resolve().parents[1])
PS1 = os.path.join(RACINE, "installer", "windows", "install_avastack.ps1")
ISS = os.path.join(RACINE, "installer", "windows", "avastack.iss")

with open(PS1, encoding="utf-8", errors="replace") as f:
    ps1 = f.read()
with open(ISS, encoding="utf-8", errors="replace") as f:
    iss = f.read()

# ============================================ [1] l'empreinte, des deux côtés
print("[1] l'empreinte SHA-256 du Python téléchargé, déclarée des DEUX côtés")
m_ps1 = re.search(r"\$PY_SHA256\s*=\s*'([0-9A-Fa-f]{64})'", ps1)
m_iss = re.search(r'#define\s+PythonSha256\s+"([0-9A-Fa-f]{64})"', iss)
verifie(m_ps1 is not None, "le paquet ZIP déclare $PY_SHA256 (64 hex)")
verifie(m_iss is not None, "Inno Setup déclare #define PythonSha256 (64 hex)")
if m_ps1 and m_iss:
    a, b = m_ps1.group(1).upper(), m_iss.group(1).upper()
    verifie(a == b, "les DEUX empreintes sont IDENTIQUES (%s...)" % a[:16])
    verifie(bool(re.fullmatch(r"[0-9A-F]{64}", a)), "format SHA-256 (64 hex)")

# ============================================ [2] vérification AVANT exécution
print("[2] les deux vérifient AVANT d'exécuter, et retentent une fois")
for quoi, texte, motifs in (
        ("paquet ZIP (PowerShell)", ps1,
         ("Get-FileHash", "$fichierBon",
          "for ($essai = 1; $essai -le 2",
          "$obtenue.ToUpperInvariant() -eq $PY_SHA256")),
        ("Inno Setup (Pascal)", iss,
         ("GetSHA256OfFile", "VerifierEmpreintePython", "FichierBon",
          "for Essai := 1 to 2"))):
    for motif in motifs:
        verifie(motif in texte, "%s : %s" % (quoi, motif))

# ============================================ [3] l'échec est DIT en clair
print("[3] l'échec est dit en clair (jamais un message obscur)")
verifie("INCOMPLET" in ps1, "le paquet ZIP dit « INCOMPLET »")
verifie("INCOMPLET" in iss, "Inno Setup dit « INCOMPLET »")
verifie("Empreinte attendue" in ps1, "le paquet ZIP affiche l'empreinte attendue")
verifie("connexion Internet" in ps1 and "python.org" in ps1,
        "le paquet ZIP dit QUOI FAIRE (connexion / python.org)")
verifie("connexion Internet" in iss and "python.org" in iss,
        "Inno Setup dit QUOI FAIRE (connexion / python.org)")

# ============================================ [4] correctif de désinstallation
print("[4] correctif de désinstallation (raccourcis Bureau / Menu Démarrer)")
verifie(ps1.count("raccourcis : AUCUN") >= 2,
        "la marque est ÉCRITE à l'installation ET RELUE à la désinstallation")
verifie("$raccourcisCrees" in ps1, "les raccourcis ne partent que si CRÉÉS")
verifie("raccourcis non touches" in ps1, "le cas « non touchés » est annoncé")

# ============================================ [5] contrôle direct du fichier
print("[5] contrôle direct : l'empreinte déclarée est-elle celle du fichier RÉEL ?")
tmp = os.environ.get("TEMP", "")
candidats = [os.path.join(tmp, "python-3.12.7-amd64.exe"),
             os.path.join(tmp, "py3127_ref.exe")]
trouve = next((c for c in candidats if os.path.isfile(c)), None)
if trouve is None or not m_ps1:
    print("  (fichier de python.org absent de %TEMP% : empreinte NON vérifiée ici)")
    print("   elle a été relevée d'un téléchargement dont la signature Authenticode")
    print("   a été vérifiée comme Valide — provenance en tête de ce banc)")
else:
    with open(trouve, "rb") as f:
        reel = hashlib.sha256(f.read()).hexdigest().upper()
    verifie(reel == m_ps1.group(1).upper(),
            "l'empreinte déclarée = le fichier %s" % os.path.basename(trouve))

print("\nBANC JALON 89 (empreinte des installateurs Windows) :",
      "TOUT AU VERT ✅" if ok else "ÉCHECS ❌")
sys.exit(0 if ok else 1)
