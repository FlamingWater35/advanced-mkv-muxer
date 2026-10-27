; Inno Setup script for Advanced MKV Muxer.
;
; It is normally compiled through scripts/build_windows.py, which passes the
; version and the folder produced by Nuitka --mode=standalone:
;
;   ISCC.exe installer\Advanced-MKV-Muxer.iss ^
;       /DDisplayVersion=2.4.2 ^
;       /DFileVersion=2.4.2.0 ^
;       /DPayloadDir=..\build\installer\main.dist
;
; The application is installed per user, below
; %LOCALAPPDATA%\Programs\Advanced MKV Muxer: no administrator rights and no
; UAC prompt are involved.
;
; Requires Inno Setup 6.3 or newer (tested with 6.7 and 7.0).

#define AppName "Advanced MKV Muxer"
#define AppExeName "Advanced-MKV-Muxer.exe"
#define AppPublisher "FlamingWater35"
#define AppUrl "https://github.com/FlamingWater35/advanced-mkv-muxer"
#define AppId "{{6F4C3D2A-9B71-4E58-8A0D-3C5E7B1F92A4}"

; Full version as shown to the user, e.g. "2.4.2" or "2.5.0-rc1".
#ifndef DisplayVersion
  #define DisplayVersion "0.0.0"
#endif

; Numeric version for the Windows file version resource.
#ifndef FileVersion
  #define FileVersion "0.0.0.0"
#endif

; Folder that contains the standalone build (app executable + Resources). Nuitka
; names the folder after the entry module (main.py), hence "main.dist".
#ifndef PayloadDir
  #define PayloadDir "..\build\installer\main.dist"
#endif

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#FileVersion}
AppVerName={#AppName} {#DisplayVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
AppUpdatesURL={#AppUrl}/releases

; Per-user installation: no admin rights, no UAC prompt.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#AppName}
UsePreviousAppDir=yes
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes

; The payload is 64-bit, 32-bit Windows is not supported.
ArchitecturesAllowed=x64compatible

OutputDir=..\dist
OutputBaseFilename=Advanced-MKV-Muxer-{#DisplayVersion}-windows-x64-setup
SetupIconFile=..\Resources\Icons\App.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#DisplayVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoVersion={#FileVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
