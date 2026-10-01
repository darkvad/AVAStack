; avastack.iss - Installateur Windows pour AVAStack (live stacking)
;
; Deploiement LOCAL : copie l'application dans un dossier choisi par
; l'utilisateur, cree un venv, installe les dependances (numpy, opencv,
; pillow, astropy + les paquets cameras qhyccd et zwoasi), et cree un
; raccourci.
;
; Les SDK binaires constructeurs places a la racine du depot
; (ASICamera2.dll, PlayerOneCamera.dll, ToupCam.dll, SVBCameraSDK.dll) sont
; EMBARQUES dans l'installateur depuis le 19/09/2026 (decision de projet :
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
; /DAppVersion=...). Depuis le 27/09/2026 (consigne de projet) le nom de
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
; Empreinte SHA-256 du fichier ci-dessus, VERIFIEE avant de l'executer (v2.48.2) :
; un telechargement interrompu ne doit jamais partir a l'execution (fichier
; tronque = signature invalide = message incomprehensible chez l'utilisateur).
; Valeur relevee d'un telechargement dont la signature Authenticode a ete
; verifiee comme Valide (signataire : Python Software Foundation).
; MEME valeur que installer/windows/install_avastack.ps1 (paquet ZIP) : un banc
; verifie que les deux fichiers s'accordent, sinon ils divergeraient en silence.
#define PythonSha256 "1206721601A62C925D4E4A0DCFC371E88F2DDBE8C0C07962EBB2BE9B5BDE4570"

[Setup]
AppId={{7E1A2C4B-9D3F-4E68-A5C1-B2F0D8A6E4C2}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\AVAStack
DefaultGroupName=AVAStack
DisableProgramGroupPage=yes
OutputDir=output
; Le nom de l'artefact PORTE LA VERSION (consigne de projet, 27/09/2026) :
; c'est lui qui dit ce qu'on teste, et deux versions ne s'ecrasent JAMAIS
; (avastack-setup-2.38.3.exe a cote de avastack-setup-2.38.2.exe).
OutputBaseFilename=avastack-setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile={#RepoRoot}\assets\avastack.ico
UninstallDisplayIcon={app}\assets\avastack.ico

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
; Ressources : l'icone de l'application (avastack/ressources.py la cherche dans
; assets/, a cote du package) - barre de titres, barre des taches, raccourcis.
Source: "{#RepoRoot}\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs
Source: "{#RepoRoot}\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
; SDK binaires des cameras (places a la racine du depot) : charges
; par avastack/cameras/sdk_loader.py dans le dossier du programme.
Source: "{#RepoRoot}\ASICamera2.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\PlayerOneCamera.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\ToupCam.dll"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#RepoRoot}\SVBCameraSDK.dll"; DestDir: "{app}"; Flags: ignoreversion
; Bancs du theme CAMERA (bancs/cameras/ dans le depot) : seuls les OUTILS DE
; DIAGNOSTIC MATERIEL sont embarques (motif _diag_*.py) - decision de projet du
; 27/09/2026 : l'installation ne contient QUE des outils qu'il peut lancer
; lui-meme (ils parlent aux VRAIES DLL et a SES cameras : detection, controles
; SDK, TEC, flux, capacites dynamiques). Le MOTIF (et non une liste) laisse
; entrer tout nouveau diagnostic tout seul.
; Les bancs de REGRESSION de la couche camera (_test_*.py : SDK factices,
; aucun materiel requis) sont des outils de DEV : ils vivent dans le depot,
; sous bancs/cameras/, et ne partent JAMAIS dans un installateur.
Source: "{#RepoRoot}\bancs\cameras\_diag_*.py"; DestDir: "{app}\bancs\cameras"; Flags: ignoreversion


; veralux_core_headless.py : code tiers GPL-3.0-or-later (Riccardo Paterniti),
; copie tel quel (sa licence exige de transmettre le source a cote du binaire).
Source: "{#RepoRoot}\veralux_core_headless.py"; DestDir: "{app}"; Flags: ignoreversion
; Lisez-moi explicatif (SDK cameras)
Source: "LISEZMOI.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\common\avastack_setup.py"; DestDir: "{tmp}"; Flags: dontcopy

[Icons]
Name: "{autodesktop}\AVAStack"; Filename: "{app}\lancer_avastack.bat"; \
    IconFilename: "{app}\assets\avastack.ico"; \
    Comment: "Live stacking AVAStack"
Name: "{group}\AVAStack"; Filename: "{app}\lancer_avastack.bat"; \
    IconFilename: "{app}\assets\avastack.ico"
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

// --- Python : telechargement VERIFIE par empreinte SHA-256 (v2.48.2) ---------
// POURQUOI (constat reel du 01/10/2026) : chez un testeur, l'installation s'est
// arretee sur
//   "Impossible d'executer un fichier depuis le dossier temporaire.
//    Abandon de l'installation. Erreur 4551 : une strategie de controle
//    d'application a bloque ce fichier."
// Le seul fichier EXECUTE depuis {tmp} est celui telecharge ici. Un
// telechargement INTERROMPU (fichier tronque, donc sans signature valide) en est
// une cause possible : on VERIFIE donc l'empreinte SHA-256 AVANT de l'executer,
// et on RETENTE une fois. Sans cette verification, un fichier incomplet partait
// a l'execution et produisait un message incomprehensible.
function VerifierEmpreintePython(const Chemin: String): Boolean;
begin
  Result := False;
  if not FileExists(Chemin) then
    Exit;
  try
    // Lowercase des deux cotes : la casse de GetSHA256OfFile n'est pas garantie.
    Result := Lowercase(GetSHA256OfFile(Chemin)) = Lowercase('{#PythonSha256}');
  except
    Result := False;
  end;
end;

function TelechargerPython(const CheminInstalleur: String): Boolean;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
       '-NoProfile -ExecutionPolicy Bypass -Command "' +
       '[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; ' +
       'Invoke-WebRequest -Uri ''{#PythonInstallerUrl}'' -OutFile ''' + CheminInstalleur + ''' -UseBasicParsing"',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := FileExists(CheminInstalleur);
end;

function InstallerPythonSiAbsent(): Boolean;
var
  CheminInstalleur: String;
  ResultCode: Integer;
  Essai: Integer;
  FichierBon: Boolean;
begin
  Result := False;
  CheminInstalleur := ExpandConstant('{tmp}\{#PythonInstallerFile}');
  FichierBon := False;
  // DEUX tentatives : un telechargement interrompu ne doit JAMAIS partir a
  // l'execution (fichier tronque = empreinte fausse = message obscur ensuite).
  for Essai := 1 to 2 do
  begin
    WizardForm.StatusLabel.Caption :=
      'Telechargement de Python (aucune version 3.10+ trouvee)...';
    if TelechargerPython(CheminInstalleur) and VerifierEmpreintePython(CheminInstalleur) then
    begin
      FichierBon := True;
      Break;
    end;
    DeleteFile(CheminInstalleur);
  end;
  if not FichierBon then
  begin
    MsgBox('Le telechargement de Python a echoue, ou le fichier recu est INCOMPLET ' +
           '(empreinte SHA-256 differente de celle attendue).' + #13#10#13#10 +
           'Verifiez la connexion Internet (ou un proxy / antivirus qui filtre les ' +
           'telechargements), puis relancez cet installateur.' + #13#10#13#10 +
           'Sinon, installez Python 3.10 ou plus recent manuellement depuis ' +
           'python.org, puis relancez cet installateur.', mbCriticalError, MB_OK);
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

