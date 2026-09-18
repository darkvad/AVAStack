; avastack.iss - Installateur Windows pour AVAStack (live stacking)
;
; Deploiement LOCAL : copie l'application dans un dossier choisi par
; l'utilisateur, cree un venv, installe les dependances (numpy, opencv,
; pillow, astropy + le paquet camera qhyccd), et cree un raccourci.
;
; Les SDK binaires constructeurs (ASICamera2.dll, PlayerOneCamera.dll…) ne
; sont PAS embarques (code proprietaire) : l'utilisateur les telecharge
; ensuite et les depose dans le dossier d'installation - message explicite
; en fin d'installation.
;
; Compilation : powershell -NoProfile -ExecutionPolicy Bypass -File build_avastack.ps1
; (recommande : la version est lue dans avastack/__init__.py et passee a ISCC
; via /DAppVersion=...) ; sinon ISCC.exe avastack.iss a la main, en verifiant
; le define de repli ci-dessous.

#define RepoRoot "..\.."
#define AppName "AVAStack"
; Version AVAStack : source unique de verite = AVASTACK_VERSION dans
; avastack/__init__.py (lue par build_avastack.ps1). Le define de repli ne
; sert qu'a une compilation manuelle ISCC sans /DAppVersion=.
#ifndef AppVersion
  #define AppVersion "2.13.0"
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
OutputBaseFilename=avastack-setup
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
Source: "{#RepoRoot}\avastack\external\*.py"; DestDir: "{app}\avastack\external"; Flags: ignoreversion
Source: "{#RepoRoot}\avastack\ui\*.py"; DestDir: "{app}\avastack\ui"; Flags: ignoreversion
Source: "{#RepoRoot}\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
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
    'SDK des cameras', 'Bibliotheques constructeurs (optionnel, a ajouter ensuite)',
    'AVAStack est installe avec le support QHY (paquet qhyccd inclus dans les ' +
    'dependances). Pour les AUTRES marques de camera (ZWO, Player One, Touptek/' +
    'Altair, SVBONY), telechargez le SDK du constructeur et copiez la DLL dans ' +
    'le dossier d''installation APRES cette installation :' + #13#10#13#10 +
    '- ZWO : ASICamera2.dll (astronomy-imaging-camera.com)' + #13#10 +
    '- Player One : PlayerOneCamera.dll (player-one-astronomy.com)' + #13#10 +
    '- Touptek/Altair : toupcam.dll (touptek.com)' + #13#10 +
    '- SVBONY : SVBCameraSDK.dll (svbony.com)' + #13#10#13#10 +
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

  if not ExecEtVerifie('Creation du venv AVAStack (numpy/opencv/pillow/astropy/qhyccd)...',
       PythonChoisi, '"' + ScriptSetup + '" create-venv --venv-dir "' + AppDir + '\venv" ' +
       '--requirements "' + AppDir + '\requirements.txt"', AppDir) then
    Exit;

  PythonVenv := AppDir + '\venv';
  EcrireLanceur(AppDir, PythonVenv);

  // Le raccourci Bureau/Menu pointe vers le lanceur genere (cf. [Icons]
  // modifie dynamiquement : simplest = recree ici)
  WizardForm.StatusLabel.Caption := 'Installation terminee.';
end;
