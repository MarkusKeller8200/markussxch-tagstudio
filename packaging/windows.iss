; TagStudioSX – Windows-Installer (Inno Setup 6)
; Aufruf: ISCC.exe /DAppVersion=3.0 packaging\windows.iss   (nach python packaging\build.py)

#ifndef AppVersion
  #define AppVersion "0.0"
#endif

[Setup]
AppId={{8F1E6C2A-3B7D-4E59-9C1A-6D2F7A1B5E30}
AppName=TagStudioSX
AppVersion={#AppVersion}
AppVerName=TagStudioSX {#AppVersion}
AppPublisher=Markus Keller
AppPublisherURL=https://github.com/MarkusKeller8200/markussxch-tagstudio
; Neu-Installation in „TagStudioSX“; ein Update (gleiche AppId) bleibt im bisherigen Ordner, z. B. „TagStudio“ (#464)
DefaultDirName={autopf}\TagStudioSX
UsePreviousAppDir=yes
DefaultGroupName=TagStudioSX
DisableProgramGroupPage=yes
; ohne Administratorrechte installierbar (für den eigenen Benutzer); auf Wunsch für alle
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=TagStudioSX-{#AppVersion}-Windows-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\TagStudioSX.exe
UninstallDisplayName=TagStudioSX
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
; laufendes TagStudioSX erkennen (Mutex aus instance.py) – erst schliessen, dann installieren
AppMutex=MarKusSXCH-TagStudio

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Reste einer älteren Version entfernen (Einstellungen, Sicherungen und Plugin-Daten liegen im Benutzerordner und bleiben)
Type: filesandordirs; Name: "{app}\_internal"
; Umbenennung 5.0.0 (#464): alte Programmdatei und Verknüpfungen „MarKusSXCH TagStudio“ entfernen
Type: files; Name: "{app}\TagStudio.exe"
Type: files; Name: "{autoprograms}\MarKusSXCH TagStudio.lnk"
Type: files; Name: "{autodesktop}\MarKusSXCH TagStudio.lnk"
Type: files; Name: "{userprograms}\MarKusSXCH TagStudio.lnk"
Type: files; Name: "{userdesktop}\MarKusSXCH TagStudio.lnk"

[Files]
Source: "..\dist\TagStudioSX\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}\Dokumentation"; Flags: ignoreversion
Source: "..\CHANGELOG.md"; DestDir: "{app}\Dokumentation"; Flags: ignoreversion
Source: "..\PLUGINS.md"; DestDir: "{app}\Dokumentation"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}\Dokumentation"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\TagStudioSX"; Filename: "{app}\TagStudioSX.exe"
Name: "{autodesktop}\TagStudioSX"; Filename: "{app}\TagStudioSX.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TagStudioSX.exe"; Description: "{cm:LaunchProgram,TagStudioSX}"; Flags: nowait postinstall skipifsilent
; Update aus 4.x (#464): dessen Updater startet danach die alte TagStudio.exe, die es nicht mehr gibt – hier neu starten
Filename: "{app}\TagStudioSX.exe"; Flags: nowait runasoriginaluser; Check: RestartAfterLegacyUpdate

[Code]
var
  LegacyExe: Boolean;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  LegacyExe := FileExists(ExpandConstant('{app}\TagStudio.exe'));
  Result := '';
end;

function RestartAfterLegacyUpdate: Boolean;
begin
  Result := WizardSilent and LegacyExe;
end;
