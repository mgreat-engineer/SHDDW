; Inno Setup script for the Windows installer (used by the GitHub build)
#define AppVersion GetEnv("HELPER_VERSION")

[Setup]
AppName=Shadow Helper
AppVersion={#AppVersion}
AppPublisher=Shadow
DefaultDirName={autopf}\Shadow Helper
DefaultGroupName=Shadow Helper
OutputDir=..\dist-installer
OutputBaseFilename=ShadowHelper-Setup-Windows
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
Source: "..\dist\ShadowHelper\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Shadow Helper"; Filename: "{app}\ShadowHelper.exe"
Name: "{userdesktop}\Shadow Helper"; Filename: "{app}\ShadowHelper.exe"
Name: "{userstartup}\Shadow Helper"; Filename: "{app}\ShadowHelper.exe"

[Run]
Filename: "{app}\ShadowHelper.exe"; Description: "Start Shadow Helper"; Flags: nowait postinstall skipifsilent
