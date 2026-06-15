; Inno Setup Script for KastomPOS
; Full Windows Installer with Start Menu, Desktop Shortcut, and Uninstaller

[Setup]
AppName=KastomPOS
AppVersion=1.0.0
AppPublisher=KastomPOS
AppPublisherURL=https://github.com/your-org/kastompos
AppSupportURL=https://github.com/your-org/kastompos/issues
AppUpdatesURL=https://github.com/your-org/kastompos/releases
DefaultDirName={autopf}\KastomPOS
DefaultGroupName=KastomPOS
DisableProgramGroupPage=yes
; Uncomment when you have an icon file:
; SetupIconFile=static\favicon.ico
; WizardImageFile=static\installer_banner.bmp
; WizardSmallImageFile=static\installer_icon.bmp
UninstallDisplayIcon={app}\KastomPOS.exe
UninstallDisplayName=KastomPOS
Compression=lzma2
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=KastomPOS_Setup
PrivilegesRequired=admin
; Minimum Windows 10
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64
; Splash/wizard appearance
WizardStyle=modern
ShowLanguageDialog=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Launch KastomPOS when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Main application executable
Source: "dist\KastomPOS.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu
Name: "{group}\KastomPOS"; Filename: "{app}\KastomPOS.exe"; Comment: "KastomPOS - ERP & Point of Sale"
Name: "{group}\Uninstall KastomPOS"; Filename: "{uninstallexe}"
; Desktop shortcut (optional)
Name: "{autodesktop}\KastomPOS"; Filename: "{app}\KastomPOS.exe"; Tasks: desktopicon; Comment: "KastomPOS - ERP & Point of Sale"

[Registry]
; Optional: add to startup
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "KastomPOS"; ValueData: """{app}\KastomPOS.exe"""; Tasks: startupicon; Flags: uninsdeletevalue

[Run]
; Launch after install
Filename: "{app}\KastomPOS.exe"; Parameters: "--reinstall"; Description: "{cm:LaunchProgram,KastomPOS}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up app data on uninstall
Type: filesandordirs; Name: "{userappdata}\KastomPOS"

[Code]
// Check for Visual C++ Redistributable and warn if missing
function VCRedistInstalled: Boolean;
var
  Installed: Cardinal;
begin
  Result := RegQueryDWordValue(HKLM, 
    'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64',
    'Installed', Installed) and (Installed = 1);
end;

procedure InitializeWizard;
begin
  if not VCRedistInstalled then
    MsgBox('KastomPOS requires the Microsoft Visual C++ Redistributable (x64).' + #13#10 +
           'Please download and install it from Microsoft if the app fails to start.' + #13#10 + #13#10 +
           'https://aka.ms/vs/17/release/vc_redist.x64.exe', 
           mbInformation, MB_OK);
end;
