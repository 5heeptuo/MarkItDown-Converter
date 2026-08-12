# MarkItDownConverter 安装脚本：复制到 Program Files + 创建桌面快捷方式
# 需要以管理员权限运行（UAC 提权）
$ErrorActionPreference = "Stop"

$src = "C:\Users\kunyu\Downloads\MarkItDownConverter\dist\MarkItDownConverter"
$dst = "C:\Program Files\MarkItDownConverter"
$exe = Join-Path $dst "MarkItDownConverter.exe"
$icon = Join-Path $dst "_internal\assets\icon.ico"

# 1. 复制程序文件
if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
New-Item -ItemType Directory -Path $dst -Force | Out-Null
robocopy $src $dst /E /NFL /NDL /NJH /NJS | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Output "COPY_FAILED"; exit 1 }

# 2. 创建桌面快捷方式
$desktop = [Environment]::GetFolderPath("Desktop")
$ws = New-Object -ComObject WScript.Shell
$lnkPath = Join-Path $desktop "MarkItDown 转换器.lnk"
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = $exe
$lnk.WorkingDirectory = $dst
$lnk.IconLocation = "$icon,0"
$lnk.Description = "批量文件转 Markdown 工具"
$lnk.Save()

Write-Output "INSTALL_OK"
exit 0
