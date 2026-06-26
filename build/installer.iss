; ===========================================================================
; Instalador de FaceHunt-2 (Inno Setup 6+).
;
; Toma la salida one-dir de PyInstaller (dist\FaceHunt2\) y la empaqueta en un
; único instalador: dist\FaceHunt2-Setup.exe
;
; Requisitos: Inno Setup 6+  ->  https://jrsoftware.org/isdl.php
; Compilar (desde la raíz del proyecto):
;     iscc build\installer.iss
; o abrir este archivo en el IDE de Inno Setup y presionar Compilar (F9).
;
; Instala sin permisos de administrador (por usuario). Crea acceso directo en el
; menú de inicio, opción de icono en el escritorio y un desinstalador.
; ===========================================================================

#define AppName "FaceHunt-2"
#define AppVersion "2.0.0"
#define AppPublisher "Iván Gómez Dell'Osa"
#define AppExe "FaceHunt2.exe"
#define AppURL "https://github.com/IvanGomezDellOsa/FaceHunt-2"

[Setup]
AppId={{8F2A4C7E-3B1D-4E6A-9C5F-7D2E1A8B4F90}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=FaceHunt2-Setup
SetupIconFile=..\web\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\FaceHunt2\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
