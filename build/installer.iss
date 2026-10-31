; Inno Setup 6 – instalater za UNA - ROAD ENGINEERING ANALYSIS
#define AppName "UNA - ROAD ENGINEERING ANALYSIS"
#ifndef AppVer
  #define AppVer "1.1.0"
#endif
[Setup]
AppId={{B7A3C1D2-5E4F-4A10-9C2B-0E1AB0AA0003}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=VAŠA FIRMA
DefaultDirName={autopf}\UNA
DefaultGroupName=UNA - Road Engineering Analysis
OutputDir=..\dist
OutputBaseFilename=UNA_Setup
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=EULA.txt
SetupIconFile=assets\una.ico
WizardImageFile=assets\wizard_big.bmp
WizardSmallImageFile=assets\wizard_small.bmp
UninstallDisplayIcon={app}\UNA.exe
PrivilegesRequired=admin
UninstallDisplayName={#AppName}
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
#if FileExists(CompilerPath + "Languages\SerbianLatin.isl")
Name: "serbian"; MessagesFile: "compiler:Languages\SerbianLatin.isl"
#endif
[Files]
Source: "..\dist\UNA.dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{group}\UNA - Road Engineering Analysis"; Filename: "{app}\UNA.exe"
Name: "{autodesktop}\UNA - Road Engineering Analysis"; Filename: "{app}\UNA.exe"
[Run]
Filename: "{app}\UNA.exe"; Description: "Pokreni UNA - ROAD ENGINEERING ANALYSIS"; Flags: postinstall nowait skipifsilent
