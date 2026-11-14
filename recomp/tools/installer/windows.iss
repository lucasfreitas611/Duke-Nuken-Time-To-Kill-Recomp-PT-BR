; Compile only a reviewed, media-free stage made by package_windows.py.
#ifndef StageDir
  #error StageDir must point to a validated player stage
#endif
#ifndef ReleaseVersion
  #define ReleaseVersion "0.1.0-preview"
#endif
[Setup]
AppId={{EAA38599-E926-40C9-9397-E95DAD2732E4}
AppName=Duke Nukem Time to Kill PT-BR
AppVersion={#ReleaseVersion}
AppPublisher=Projeto Duke TTK PT-BR
DefaultDirName={localappdata}\Programs\DukeTTK-PTBR
DefaultGroupName=Duke TTK PT-BR
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
Compression=lzma2
SolidCompression=yes
OutputDir={#StageDir}\..\installer
OutputBaseFilename=DukeTTK-PTBR-{#ReleaseVersion}-Setup
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\DukeTTK-PTBR.exe
CloseApplications=yes
RestartApplications=no
[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Excludes: "__pycache__,*.pyc"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Jogar Duke TTK PT-BR"; Filename: "{app}\DukeTTK-PTBR.exe"; Parameters: "--play"
Name: "{group}\Configurar Duke TTK PT-BR"; Filename: "{app}\DukeTTK-PTBR.exe"
Name: "{autodesktop}\Jogar Duke TTK PT-BR"; Filename: "{app}\DukeTTK-PTBR.exe"; Parameters: "--play"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked
[Run]
Filename: "{app}\DukeTTK-PTBR.exe"; Description: "Verificar requisitos e preparar minha cópia USA"; Flags: nowait postinstall skipifsilent
; No UninstallDelete rule for user data: saves, profiles, imported disc and
; local compilation live outside {app}, in {localappdata}\DukeTTK-PTBR.
