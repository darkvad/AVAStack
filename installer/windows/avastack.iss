; avastack.iss - Installateur Windows pour AVAStack (live stacking)
;
; Deploiement LOCAL : copie l'application dans un dossier choisi par
; l'utilisateur, cree un venv, installe les dependances (numpy, opencv,
; pillow, astropy + les paquets cameras qhyccd et zwoasi), et cree un
; raccourci.
;
; Les SDK binaires constructeurs poses par Alain a la racine du depot
; (ASICamera2.dll, PlayerOneCamera.dll, ToupCam.dll, SVBCameraSDK.dll) sont
; EMBARQUES dans l'installateur depuis le 19/09/2026 (decision d'Alain :
; Â« j'ai mis dans le dossier principal toutes les dll des sdk, donc inclut
; les Â») - les paquet pip associes (zwoasi ; PlayerOne/Touptek/SVBONY en
; ctypes direct, pas de paquet) sont installes via requirements.txt.
;
; Compilation : powershell -NoProfile -ExecutionPolicy Bypass -File build_avastack.ps1
; (recommande : la version est lue dans avastack/__init__.py et passee a ISCC
; via /DAppVersion=...) ; sinon ISCC.exe avastack.iss a la main, en verifiant
; le define de repli ci-dessous.

#define RepoRoot "..\.."
#define AppName "AVAStack"
; Version AVAStack : source unique de verite = AVASTACK_VERSION dans
; avastack/__init__.py (lue par build_avastack.ps1 et passee via
; /DAppVersion=...). Depuis le 27/09/2026 (consigne d'Alain) le nom de
; l'artefact PORTE LA VERSION : compiler sans version produirait un
; installateur MAL NOMME, qui mentirait sur ce qu'il contient -> on refuse
; de compiler (plus aucun define de repli a maintenir).
#ifndef AppVersion
  #error AppVersion non defini : compilez avec build_avastack.ps1, ou passez /DAppVersion=<version> a ISCC
#endif
#define MinPythonMajor 3
#define MinPythonMinor 10
#define PythonInstallerUrl "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
#define PythonInstallerFile "python-3.12.7-amd64.exe"

[Setup]
AppId={{7E1A2C4B-9D3F-4E68-A5C1-B2F0D8A6E4C2}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\AVAStack
DefaultGroupName=AVAStack
DisableProgramGroupPage=yes
OutputDir=output
; Le nom de l'artefact PORTE LA VERSION (consigne d'Alain, 27/09/2026) :
; c'est lui qui dit ce qu'on teste, et deux versions ne s'ecrasent JAMAIS
; (avastack-setup-2.38.3.exe a cote de avastack-setup-2.38.2.exe).
OutputBaseFilename=avastack-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\AVAStack.py

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Files]
; Application (package + lanceur) - pas de venv/, .git/, __pycache__
Source: "{#RepoRoot}\AVAStack.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\avastack\*.py"; DestDir: "{app}\avastack"; Flags: ignoreversion
Source: "{#RepoRoot}\avastack\cameras\*.py"; DestDir: "{app}\avastack\cameras"; Flags: ignoreversion
Source: "{#RepoRoot}\avastack\processing\*.py"; DestDir: "{app}\avastack\processing"; Flags: ignoreversion
Source: "{#RepoRoot}\avastack\catalogues\*.py"; DestDir: "{app}\avastack\catalogues"; Flags: ignoreversion
Source: "{#RepoRoot}\avastack\external\*.py"; DestDir: "{app}\avastack\external"; Flags: ignoreversion
Source: "{#RepoRoot}\avastack\ui\*.py"; DestDir: "{app}\avastack\ui"; Flags: ignoreversion
Source: "{#RepoRoot}\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
; SDK binaires des cameras (poses par Alain a la racine du depot) : charges
; par avastack/cameras/sdk_loader.py dans le dossier du programme.
Source: "{#RepoRoot}\ASICamera2.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\PlayerOneCamera.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\ToupCam.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\SVBCameraSDK.dll"; DestDir: "{app}"; Flags: ignoreversion
; Bancs de diagnostic camera autonomes : outils d'Alain pour deboguer hors
; application (detection, controles SDK, TEC, flux, capacites dynamiques).
Source: "{#RepoRoot}\_diag_camera_qhy.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\_diag_camera_playerone.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\_diag_camera_svbony.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\_diag_camera_touptek.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\_diag_solve_reel.py"; DestDir: "{app}"; Flags: ignoreversion
; Banc de regression REEL du solveur (v2.27.0) : resout les vraies images
; M31 (empilement composite + brute G) et confronte a ASTAP ; saute
; proprement si les images de test sont absentes.
Source: "{#RepoRoot}\_test_solveur_reel_m31.py"; DestDir: "{app}"; Flags: ignoreversion
; Banc de regression REEL de l'echelle des sauvegardes (v2.27.1) : verifie que
; l'empilement lineaire ecrit est borne a [0,1] (AVASCALE reversible) et que
; ASTAP RESOUT le fichier M31 du disque ; saute proprement si absent.
Source: "{#RepoRoot}\_test_save_lineaire_echelle.py"; DestDir: "{app}"; Flags: ignoreversion
; Banc de branchement du solveur au worker (v2.28.0) : astrometrie de l'empilement
; (indices -> resolution unique -> propagation mots-cles WCS).
Source: "{#RepoRoot}\_test_astro_branchement_jalon56.py"; DestDir: "{app}"; Flags: ignoreversion
; Banc de photometrie (v2.30.0, jalon 56 etape 4) : zero-point par bande
; (appariements Gaia via le WCS, gains relatifs, worker reel).
Source: "{#RepoRoot}\_test_photometrie_jalon56.py"; DestDir: "{app}"; Flags: ignoreversion
; Diagnostic ASTAP en balayage (v2.29.0) : essaie plusieurs -fov, affiche
; le verdict brut et liste les bases installees (D80 seule = balayage
; impossible) ; confronte au resultat du solveur interne indice.
Source: "{#RepoRoot}\_diag_astap_aveugle.py"; DestDir: "{app}"; Flags: ignoreversion
; Diagnostic de resolution d'une COMPOSITION (v2.31.2) : compare chaque
; couche separee et le composite (celui que l'appli analyse).
Source: "{#RepoRoot}\_diag_solve_compo.py"; DestDir: "{app}"; Flags: ignoreversion
; Diagnostic du VOTE RANSAC (v2.31.3) : instrumente le vote (echelle, angle) et
; le raffinement, et compare au WCS vrai d'ASTAP (qui correspond a qui) —
; c'est cet outil qui a identifie le bug d'appariement direct/croise.
Source: "{#RepoRoot}\_diag_vote.py"; DestDir: "{app}"; Flags: ignoreversion
; Diagnostic d'appariement (v2.31.3) : ecart de CHAQUE etoile detectee a
; l'etoile de catalogue Gaia la plus proche, via le WCS vrai d'ASTAP.
Source: "{#RepoRoot}\_diag_appariement.py"; DestDir: "{app}"; Flags: ignoreversion
; Diagnostic d'ALIGNEMENT SOUS-PIXEL (v2.32.0) : verite terrain par appariement
; mutuel d'etoiles (sans WCS), repartition SPATIALE du decalage, correlation de
; phase comme second avis, ce que CHAQUE chemin de l'aligneur retourne (reste
; mesure APRES application) et precision sur des decalages connus. C'est cet
; outil qui a identifie le defaut ORB : le sous-pixel n'etait jamais corrige.
Source: "{#RepoRoot}\_diag_align_precision.py"; DestDir: "{app}"; Flags: ignoreversion
; Diagnostic des GAINS PHOTOMETRIQUES (v2.32.0) : etat des canaux, zero-points
; Gaia et leur dispersion (fiabilite), effet REEL des gains sur la couleur du
; fond, et decalage des etoiles ENTRE canaux (franges colorees).
Source: "{#RepoRoot}\_diag_couleur_gains.py"; DestDir: "{app}"; Flags: ignoreversion

; Banc SPCC (v2.33.0, jalon 58) : calibration spectrophotométrique ABSOLUE
; « à la Siril » sur des couches REELLES — spectres Gaia du champ, profils
; capteur/filtres de la base Siril, reference de blanc, coefficients par
; regression robuste, et comparaison objective des methodes (brut,
; equilibrage du fond, Linear Fit, gains Gaia relatifs, SPCC) par l'erreur
; des COULEURS D'ETOILES en magnitudes.
Source: "{#RepoRoot}\_diag_spcc.py"; DestDir: "{app}"; Flags: ignoreversion

; Outil : QUE CONTIENNENT les fichiers d'empilement (brut vs traité) ? Fond et
; bruit par canal, contraste de fond R/G et B/G, rapport brut/traité, clés AVA*
; de l'en-tête. C'est l'outil qui a identifié l'écrêtage [0..1] de la chaîne
; live en v2.35.1 (voir aussi _test_save_brute_jalon59.py).
Source: "{#RepoRoot}\_diag_empilement_couleur.py"; DestDir: "{app}"; Flags: ignoreversion

; Banc SPCC (v2.34.0, jalon 58) : verifie le MODELE contre une VERITE
; ANALYTIQUE — image fabriquee a partir des spectres et de reponses connues
; (attenuations instrumentales x0,7 / x1,3) : les pentes de regression doivent
; valoir exactement ces gains, la reference de blanc doit devenir NEUTRE,
; plus les refus propres, le piege des unites (angstroms), la robustesse de la
; regression, la session et tout le branchement UI (case opt-in, selecteurs
; alimentes par la base Siril, config round-trip, gains par role).
Source: "{#RepoRoot}\_test_spcc_jalon58.py"; DestDir: "{app}"; Flags: ignoreversion

; Banc du CHANTIER v2.35.0 : LA SAUVEGARDE LINEAIRE EST BRUTE + LES
; CORRECTIONS DE COULEUR SONT DANS LA CHAINE DE SORTIE. Preuve, au banc, que
; le fichier enregistre est IDENTIQUE AU PIXEL PRES avec et sans SPCC / gains
; Gaia / equilibrage / Linear Fit coches (alors que l'affichage change) ;
; verifie aussi l'ordre des corrections (gains -> equilibrage -> recalage), le
; transport de l'equilibrage au solveur live et la 3e sortie « empilement
; traite (lineaire) » (bouton dedie, sans etirement, en-tete descriptif).
Source: "{#RepoRoot}\_test_save_brute_jalon59.py"; DestDir: "{app}"; Flags: ignoreversion

; Banc de l'OPTION v2.36.0 : NORMALISATION COMMUNE DES CANAUX (case decochee
; par defaut). Montre, sur une scene synthetique, pourquoi le fond s'ameliore
; enfin avec l'integration quand les trois roles partagent l'echelle du vert
; (grain/fond x1,8 de 30 a 120 frames) alors qu'avec la normalisation par role
; il reste inchange (x0,9) et COLORE -> c'est la cause du grain que voit Alain.
Source: "{#RepoRoot}\_test_norm_commune_jalon61.py"; DestDir: "{app}"; Flags: ignoreversion

; Banc des CORRECTIFS v2.36.1 (fond bleu, constats d'Alain du 25/09/2026) :
; (1) les PNG/TIFF ne permutent plus R et B (verifie par DEUX lecteurs
; independants : OpenCV brut et PIL) ; (2) neutralisation de la couleur du fond
; avant l'etirement VeraLux (gains ~2 % mesures sur la mediane de la moitie
; sombre : fond etire de R/G 0,36 B/G 1,61 -> 1,02 / 1,00) ; (3) branchement
; UI/solveur/config. Accepte un fichier REEL en argument :
;   python _test_fond_bleu_jalon62.py "mon_fichier_lineaire.fits"
; -> fond lineaire, gains proposes, fond etire avant/apres, et controle du PNG ecrit.
Source: "{#RepoRoot}\_test_fond_bleu_jalon62.py"; DestDir: "{app}"; Flags: ignoreversion

; Banc de la REDUCTION DU BRUIT CHROMATIQUE (v2.37.0, demande d'Alain : « un
; equivalent de SCNR pour le bleu », case DECOCHEE par defaut) : la primitive
; (grain colore x(1-force) exactement, luminance intacte, couleur de l'objet
; preservee), le cas REEL (gains de la SPCC : K_B/K_G = 1,318 -> grain B/G
; mesure a 1,174 sur ses empilements M31), le transport au solveur VeraLux
; (sortie identique a la chaine attendue) et le branchement UI/config (rendu
; IMMEDIAT au clic, sans nouvelle frame).
Source: "{#RepoRoot}\_test_chroma_halo_jalon65.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\_test_chroma_nr_jalon63.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\_test_chroma_structure_jalon67.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\_test_zoom_pleine_res_jalon68.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\_test_pleine_res_traitee_jalon69.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\_test_unflip_jalon69.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\_test_bxt_entete_jalon69.py"; DestDir: "{app}"; Flags: ignoreversion

; veralux_core_headless.py : code tiers GPL-3.0-or-later (Riccardo Paterniti),
; copie tel quel (sa licence exige de transmettre le source a cote du binaire).
Source: "{#RepoRoot}\veralux_core_headless.py"; DestDir: "{app}"; Flags: ignoreversion
; Lisez-moi explicatif (SDK cameras)
Source: "LISEZMOI.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\common\avastack_setup.py"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{autodesktop}\AVAStack"; Filename: "{app}\lancer_avastack.bat"; \
    Comment: "Live stacking AVAStack"
Name: "{group}\AVAStack"; Filename: "{app}\lancer_avastack.bat"
Name: "{group}\Dossier AVAStack"; Filename: "{app}"
Name: "{group}\Desinstaller AVAStack"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\lancer_avastack.bat"; Description: "Lancer AVAStack maintenant"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Ne supprime QUE ce que l'installateur a cree - JAMAIS les dossiers crees
; ensuite par l'usage (images, config...)
Type: filesandordirs; Name: "{app}\venv"
Type: files; Name: "{app}\lancer_avastack.bat"

[Code]
var
  PageSDK: TOutputMsgWizardPage;

// ============================================================
// PYTHON : detection + installation silencieuse si absent/trop ancien
// (meme logique que astro-pipeline.iss - constats reels integres)
// ============================================================
function ObtenirVersionPython(const PythonExe: String; var Majeur, Mineur: Integer): Boolean;
var
  ResultCode: Integer;
  FichierSortie, Sortie, TexteVersion: String;
  Parties: TStringList;
  PosPoint1, PosPoint2: Integer;
begin
  Result := False;
  FichierSortie := ExpandConstant('{tmp}\pyver.txt');
  Exec(ExpandConstant('{cmd}'), '/C ""' + PythonExe + '" --version > "' + FichierSortie + '" 2>&1"',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if not FileExists(FichierSortie) then Exit;
  Sortie := '';
  Parties := TStringList.Create;
  try
    Parties.LoadFromFile(FichierSortie);
    if Parties.Count > 0 then Sortie := Parties[0];
  finally
    Parties.Free;
  end;
  if Pos('Python ', Sortie) <> 1 then Exit;
  TexteVersion := Copy(Sortie, Length('Python ') + 1, Length(Sortie));
  PosPoint1 := Pos('.', TexteVersion);
  if PosPoint1 = 0 then Exit;
  PosPoint2 := PosPoint1 + Pos('.', Copy(TexteVersion, PosPoint1 + 1, Length(TexteVersion)));
  if PosPoint2 <= PosPoint1 then Exit;
  Majeur := StrToIntDef(Copy(TexteVersion, 1, PosPoint1 - 1), 0);
  Mineur := StrToIntDef(Copy(TexteVersion, PosPoint1 + 1, PosPoint2 - PosPoint1 - 1), 0);
  Result := (Majeur > 0);
end;

function CheminPythonFraichementInstalle(): String;
var
  DossierParent, Candidat: String;
  TrouveFichier: TFindRec;
begin
  Result := '';
  DossierParent := ExpandConstant('{localappdata}\Programs\Python');
  if not DirExists(DossierParent) then Exit;
  if FindFirst(DossierParent + '\Python3*', TrouveFichier) then
  begin
    try
      repeat
        if (TrouveFichier.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
        begin
          Candidat := DossierParent + '\' + TrouveFichier.Name + '\python.exe';
          if FileExists(Candidat) then
          begin
            Result := Candidat;
            Exit;
          end;
        end;
      until not FindNext(TrouveFichier);
    finally
      FindClose(TrouveFichier);
    end;
  end;
end;

function TrouverPythonValide(): String;
var
  Majeur, Mineur: Integer;
  CheminConnu: String;
begin
  Result := '';
  CheminConnu := CheminPythonFraichementInstalle();
  if CheminConnu <> '' then
    if ObtenirVersionPython(CheminConnu, Majeur, Mineur) then
      if (Majeur > {#MinPythonMajor}) or ((Majeur = {#MinPythonMajor}) and (Mineur >= {#MinPythonMinor})) then
      begin
        Result := CheminConnu;
        Exit;
      end;
  if ObtenirVersionPython('python', Majeur, Mineur) then
    if (Majeur > {#MinPythonMajor}) or ((Majeur = {#MinPythonMajor}) and (Mineur >= {#MinPythonMinor})) then
    begin
      Result := 'python';
      Exit;
    end;
  if ObtenirVersionPython('py', Majeur, Mineur) then
    if (Majeur > {#MinPythonMajor}) or ((Majeur = {#MinPythonMajor}) and (Mineur >= {#MinPythonMinor})) then
      Result := 'py';
end;

function InstallerPythonSiAbsent(): Boolean;
var
  CheminInstalleur: String;
  ResultCode: Integer;
begin
  Result := False;
  CheminInstalleur := ExpandConstant('{tmp}\{#PythonInstallerFile}');
  WizardForm.StatusLabel.Caption := 'Telechargement de Python (aucune version 3.10+ trouvee)...';
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
       '-NoProfile -ExecutionPolicy Bypass -Command "' +
       '[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ' +
       'Invoke-WebRequest -Uri ''{#PythonInstallerUrl}'' -OutFile ''' + CheminInstalleur + ''' -UseBasicParsing"',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if not FileExists(CheminInstalleur) then
  begin
    MsgBox('Echec du telechargement de Python (verifiez la connexion Internet). ' +
           'Installez Python 3.10 ou plus recent manuellement depuis python.org, ' +
           'puis relancez cet installateur.', mbCriticalError, MB_OK);
    Exit;
  end;
  WizardForm.StatusLabel.Caption := 'Installation de Python (silencieuse)...';
  Exec(CheminInstalleur, '/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  DeleteFile(CheminInstalleur);
  Result := (TrouverPythonValide() <> '');
end;

procedure InitializeWizard();
begin
  if TrouverPythonValide() = '' then
  begin
    if not InstallerPythonSiAbsent() then
    begin
      MsgBox('Python 3.10+ est requis pour AVAStack.', mbCriticalError, MB_OK);
      WizardForm.Close;
      Exit;
    end;
  end;

  PageSDK := CreateOutputMsgPage(wpInstalling,
    'SDK des cameras', 'Bibliotheques constructeurs (incluses)',
    'Les SDK binaires des cameras sont inclus dans le dossier ' +
    'd''installation :' + #13#10#13#10 +
    '- QHY : paquet qhyccd (SDK natif embarque dans le paquet pip)' + #13#10 +
    '- ZWO : ASICamera2.dll + paquet zwoasi' + #13#10 +
    '- Player One : PlayerOneCamera.dll (integration ctypes directe)' + #13#10 +
    '- Touptek/Altair : ToupCam.dll (integration ctypes directe)' + #13#10 +
    '- SVBONY : SVBCameraSDK.dll (integration ctypes directe)' + #13#10#13#10 +
    'Un fichier LISEZMOI.txt dans le dossier d''installation rappelle tout cela.');
end;

function ExecEtVerifie(const Description, Filename, Params, WorkDir: String): Boolean;
var
  ResultCode: Integer;
begin
  WizardForm.StatusLabel.Caption := Description;
  Result := Exec(Filename, Params, WorkDir, SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
  if not Result then
    MsgBox('Etape echouee : ' + Description + #13#10 +
           'Code retour : ' + IntToStr(ResultCode), mbError, MB_OK);
end;

procedure EcrireLanceur(const AppDir, PythonVenv: String);
var
  Contenu: TStringList;
begin
  // Lanceur .bat simple et transparent : lance l'app avec pythonw (sans
  // console) si disponible, python sinon. Pointe par les raccourcis [Icons].
  Contenu := TStringList.Create;
  try
    Contenu.Add('@echo off');
    Contenu.Add('rem Lanceur AVAStack - genere par l''installateur');
    Contenu.Add('set PYTHONW=' + PythonVenv + '\Scripts\pythonw.exe');
    Contenu.Add('if exist "%PYTHONW%" (');
    Contenu.Add('    start "" "%PYTHONW%" "' + AppDir + '\AVAStack.py"');
    Contenu.Add(') else (');
    Contenu.Add('    start "" "' + PythonVenv + '\Scripts\python.exe" "' + AppDir + '\AVAStack.py"');
    Contenu.Add(')');
    Contenu.SaveToFile(AppDir + '\lancer_avastack.bat');
  finally
    Contenu.Free;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  AppDir, ScriptSetup, PythonChoisi, PythonVenv: String;
begin
  if CurStep <> ssPostInstall then
    Exit;

  AppDir := ExpandConstant('{app}');
  PythonChoisi := TrouverPythonValide();
  if PythonChoisi = '' then
  begin
    MsgBox('Python introuvable apres installation - relancez l''installateur depuis un nouveau terminal.', mbCriticalError, MB_OK);
    Exit;
  end;

  ExtractTemporaryFile('avastack_setup.py');
  ScriptSetup := ExpandConstant('{tmp}\avastack_setup.py');

  if not ExecEtVerifie('Creation du venv AVAStack (numpy/opencv/pillow/astropy/qhyccd/zwoasi)...',
       PythonChoisi, '"' + ScriptSetup + '" create-venv --venv-dir "' + AppDir + '\venv" ' +
       '--requirements "' + AppDir + '\requirements.txt"', AppDir) then
    Exit;

  PythonVenv := AppDir + '\venv';
  EcrireLanceur(AppDir, PythonVenv);

  // Le raccourci Bureau/Menu pointe vers le lanceur genere (cf. [Icons]
  // modifie dynamiquement : simplest = recree ici)
  WizardForm.StatusLabel.Caption := 'Installation terminee.';
end;

