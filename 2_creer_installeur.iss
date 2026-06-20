; ============================================================
;  Installeur pour Suivi Hotel des Ventes
;  Ouvrez ce fichier avec Inno Setup (gratuit : jrsoftware.org/isdl.php)
;  puis cliquez sur "Compile". Vous obtiendrez un installeur dans Sortie\
; ============================================================

#define MonApp "Suivi Hotel des Ventes"
#define MaVersion "1.1.2"
#define MonEditeur "Alexandre"
#define MonExe "SuiviHDV.exe"

[Setup]
AppName={#MonApp}
AppVersion={#MaVersion}
AppPublisher={#MonEditeur}
DefaultDirName={autopf}\SuiviHDV
DefaultGroupName=Suivi Hotel des Ventes
DisableProgramGroupPage=yes
OutputDir=Sortie
OutputBaseFilename=SuiviHDV_Installeur_{#MaVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=app\icon.ico
UninstallDisplayIcon={app}\{#MonExe}
PrivilegesRequired=lowest

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Creer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
; Application principale (dossier onedir — moins suspect pour les antivirus)
Source: "dist\SuiviHDV\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Addon WoW (copie dans un sous-dossier pour que l'utilisateur le trouve facilement)
Source: "addon\SuiviHDV\*"; DestDir: "{app}\Addon_WoW\SuiviHDV"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Suivi Hotel des Ventes"; Filename: "{app}\{#MonExe}"
Name: "{group}\Desinstaller"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Suivi Hotel des Ventes"; Filename: "{app}\{#MonExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MonExe}"; Description: "Lancer l'application maintenant"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  AddonMsg: string;
begin
  if CurStep = ssDone then
  begin
    AddonMsg := 'L''addon WoW a ete copie dans :' + #13#10 +
                ExpandConstant('{app}') + '\Addon_WoW\SuiviHDV' + #13#10#13#10 +
                'Copiez ce dossier dans :' + #13#10 +
                'World of Warcraft\_retail_\Interface\AddOns\';
    MsgBox(AddonMsg, mbInformation, MB_OK);
  end;
end;
