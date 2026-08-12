; MarkItDown Converter v2.1.0 安装程序
; AppId 与 v1.x 完全一致 -> 自动检测旧版本并升级替换（不会出现两个软件）
#define MyAppName "MarkItDown Converter"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "MarkItDownConverter"
#define MyAppExeName "MarkItDownConverter.exe"
#define MyAppId "{49E42750-BA14-40A5-A97A-FB91F13D7963}"

[Setup]
AppId={{#MyAppId}
AppName={#MyAppName}
AppVerName={#MyAppName} {#MyAppVersion}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppMutex=MarkItDownConverter_SingleInstance
DefaultDirName={localappdata}\Programs\MarkItDownConverter
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\release
OutputBaseFilename=MarkItDownConverter_Setup_{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes
UsePreviousTasks=yes
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductName={#MyAppName}
VersionInfoDescription={#MyAppName} 安装程序

[Messages]
WelcomeLabel1=欢迎安装 [name]
WelcomeLabel2=安装程序将在您的电脑上安装 [name/ver]。%n%n建议继续之前关闭其他应用程序。
SelectDirLabel3=安装程序将把 [name] 安装到以下文件夹。
ReadyLabel1=安装程序已准备好开始安装 [name]。
FinishedHeadingLabel=安装完成
FinishedLabel=已在您的电脑上安装 [name]。

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "快捷方式："; Flags: checkedonce

[Files]
Source: "..\dist\MarkItDownConverter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
const
  UninstallRegKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1';

function IsProcessRunning(ExeName: String): Boolean;
var
  ResultCode: Integer;
  CheckFile: String;
  Content: AnsiString;
begin
  Result := False;
  CheckFile := ExpandConstant('{tmp}\mdc_proc_check.txt');
  DeleteFile(CheckFile);
  Exec('cmd.exe',
    '/C tasklist /FI "IMAGENAME eq ' + ExeName + '" /NH > "' + CheckFile + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if FileExists(CheckFile) then
  begin
    if LoadStringFromFile(CheckFile, Content) then
      Result := Pos(ExeName, LowerCase(Content)) > 0;
    DeleteFile(CheckFile);
  end;
end;

function InitializeSetup(): Boolean;
var
  OldVersion: String;
  MsgText: String;
  ResultCode: Integer;
begin
  Result := True;

  // 1) 检测旧版本（同一 AppId 的卸载注册记录）-> 提示升级
  if RegQueryStringValue(HKEY_CURRENT_USER, UninstallRegKey, 'DisplayVersion', OldVersion) then
  begin
    MsgText := '检测到 MarkItDown Converter 的旧版本。' + #13#10 + #13#10 +
               '当前版本：' + OldVersion + #13#10 +
               '新版本：{#MyAppVersion}' + #13#10 + #13#10 +
               '安装程序将升级现有版本。';
    MsgBox(MsgText, mbInformation, MB_OK);
  end;

  // 2) 检测旧程序是否正在运行（v1 可执行文件名与 v2 相同）
  if IsProcessRunning('{#MyAppExeName}') then
  begin
    MsgText := 'MarkItDown Converter 正在运行。' + #13#10 +
               '安装新版前需要关闭程序。' + #13#10 + #13#10 +
               '是否允许安装程序自动结束它？';
    if MsgBox(MsgText, mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec('taskkill.exe', '/IM {#MyAppExeName} /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end
    else
    begin
      Result := False;
      Exit;
    end;
  end;
end;
