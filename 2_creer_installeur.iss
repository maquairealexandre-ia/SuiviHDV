; ============================================================
;  Installeur pour Suivi Hotel des Ventes
;  Ouvrez ce fichier avec Inno Setup (gratuit : jrsoftware.org/isdl.php)
;  puis cliquez sur "Compile". Vous obtiendrez un installeur dans Sortie\
; ============================================================

#define MonApp "Suivi Hotel des Ventes"
#define MaVersion "1.1.3"
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

; Addon WoW — installe directement dans le dossier choisi par l'utilisateur
Source: "addon\SuiviHDV\*"; DestDir: "{code:GetWowAddonsDir}\SuiviHDV"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Suivi Hotel des Ventes"; Filename: "{app}\{#MonExe}"
Name: "{group}\Desinstaller"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Suivi Hotel des Ventes"; Filename: "{app}\{#MonExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MonExe}"; Description: "Lancer l'application maintenant"; Flags: nowait postinstall skipifsilent

[Code]
var
  WowAddonsPage: TInputDirWizardPage;

function DetectWowAddons: string;
var
  Lecteurs: TArrayOfString;
  i: Integer;
  Chemin: string;
begin
  SetArrayLength(Lecteurs, 6);
  Lecteurs[0] := 'C';
  Lecteurs[1] := 'D';
  Lecteurs[2] := 'E';
  Lecteurs[3] := 'F';
  Lecteurs[4] := 'G';
  Lecteurs[5] := 'H';

  for i := 0 to GetArrayLength(Lecteurs) - 1 do
  begin
    Chemin := Lecteurs[i] + ':\Program Files (x86)\World of Warcraft\_retail_\Interface\AddOns';
    if DirExists(Chemin) then begin Result := Chemin; Exit; end;

    Chemin := Lecteurs[i] + ':\Program Files\World of Warcraft\_retail_\Interface\AddOns';
    if DirExists(Chemin) then begin Result := Chemin; Exit; end;

    Chemin := Lecteurs[i] + ':\World of Warcraft\_retail_\Interface\AddOns';
    if DirExists(Chemin) then begin Result := Chemin; Exit; end;
  end;

  Result := 'C:\Program Files (x86)\World of Warcraft\_retail_\Interface\AddOns';
end;

procedure InitializeWizard;
begin
  WowAddonsPage := CreateInputDirPage(
    wpSelectDir,
    'Dossier AddOns de World of Warcraft',
    'Ou se trouve votre dossier Interface\AddOns ?',
    'L''addon SuiviHDV sera installe automatiquement dans ce dossier.'
      + #13#10 + 'Le chemin detecte est pre-rempli, verifiez qu''il est correct.',
    False,
    ''
  );
  WowAddonsPage.Add('');
  WowAddonsPage.Values[0] := DetectWowAddons;
end;

function GetWowAddonsDir(Param: string): string;
begin
  Result := WowAddonsPage.Values[0];
end;
