; MarKusSXCH TagStudio – Windows-Installer (Inno Setup 6)
; Aufruf: ISCC.exe /DAppVersion=3.0 packaging\windows.iss   (nach python packaging\build.py)

#ifndef AppVersion
  #define AppVersion "0.0"
#endif

[Setup]
AppId={{8F1E6C2A-3B7D-4E59-9C1A-6D2F7A1B5E30}
AppName=MarKusSXCH TagStudio
AppVersion={#AppVersion}
AppVerName=MarKusSXCH TagStudio {#AppVersion}
AppPublisher=Markus Keller
AppPublisherURL=https://github.com/MarkusKeller8200/markussxch-tagstudio
DefaultDirName={autopf}\TagStudio
DefaultGroupName=MarKusSXCH TagStudio
DisableProgramGroupPage=yes
; ohne Administratorrechte installierbar (für den eigenen Benutzer); auf Wunsch für alle
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=TagStudio-{#AppVersion}-Windows-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\TagStudio.exe
UninstallDisplayName=MarKusSXCH TagStudio
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Reste einer älteren Version entfernen (Einstellungen, Sicherungen und Plugin-Daten liegen im Benutzerordner und bleiben)
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\TagStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}\Dokumentation"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}\Dokumentation"; Flags: ignoreversion
Source: "..\PLUGINS.md"; DestDir: "{app}\Dokumentation"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}\Dokumentation"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\MarKusSXCH TagStudio"; Filename: "{app}\TagStudio.exe"
Name: "{autodesktop}\MarKusSXCH TagStudio"; Filename: "{app}\TagStudio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TagStudio.exe"; Description: "{cm:LaunchProgram,MarKusSXCH TagStudio}"; Flags: nowait postinstall skipifsilent
