# =====================================================================
#  把「用大肥鱼阅读器打开」注册到 Windows 资源管理器右键菜单
#
#  用法（普通权限即可，只写 HKEY_CURRENT_USER）
#      powershell -ExecutionPolicy Bypass -File _scripts\install-shell-menu.ps1
#      powershell -ExecutionPolicy Bypass -File _scripts\install-shell-menu.ps1 -Extensions .md,.txt,.pdf
#      powershell -ExecutionPolicy Bypass -File _scripts\install-shell-menu.ps1 -WhatIf
#      powershell -ExecutionPolicy Bypass -File _scripts\install-shell-menu.ps1 -Uninstall
#
#  实现注意
#      注册表路径里有 * （表示所有文件类型）。PowerShell 的注册表 provider
#      （Test-Path / New-Item / Get-ItemProperty 这些 cmdlet）会把 * 当通配符
#      展开，碰到这个路径会卡死。所以这里一律用：
#          Microsoft.Win32.Registry   —— 写
#          reg.exe                    —— 读
#      改这个脚本时请保持同样的做法。
# =====================================================================

param(
    [string[]]$Extensions = @('*'),
    [switch]$Uninstall,
    [switch]$WhatIf,
    # 让 Windows 11 恢复成 Win10 那种完整右键菜单 —— 我们的菜单项就会直接出现，
    # 不用再点「显示更多选项」。这是全局改动，会影响资源管理器整体外观。
    [switch]$ClassicMenu,
    [switch]$RestoreMenu
)

$ErrorActionPreference = 'Stop'

# powershell -File 会把 -Extensions .md,.txt 连成单个字符串，这里统一再拆一次
$Extensions = @($Extensions | ForEach-Object { "$_" -split ',' } |
                ForEach-Object { $_.Trim() } |
                Where-Object { $_ })
if ($Extensions.Count -eq 0) { $Extensions = @('*') }

$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Launcher = Join-Path $RepoRoot '_webapp\open_in_reader.py'
$Icon     = Join-Path $RepoRoot '_webapp\static\mascot.ico'
$LogFile  = Join-Path $RepoRoot '_webapp\logs\open-with.log'

$KeyName  = 'StudyAIReader'
$MenuText = '用大肥鱼阅读器打开'

function Get-SubKey([string]$ext) {
    if ($ext -eq '*') { return "Software\Classes\*\shell\$KeyName" }
    return "Software\Classes\$($ext.TrimStart('.'))\shell\$KeyName"
}

function Find-Pythonw {
    $cands = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\pythonw.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\pythonw.exe"
    )
    foreach ($c in $cands) { if (Test-Path $c) { return $c } }
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $py = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($py) {
        $w = Join-Path (Split-Path $py.Source -Parent) 'pythonw.exe'
        if (Test-Path $w) { return $w }
        return $py.Source
    }
    return $null
}

# =====================================================================
#  Windows 11 右键菜单样式切换
#   {86ca1aa0-...} 存在 = 经典（Win10 完整菜单）
#   不存在           = Win11 精简菜单（第三方项收在「显示更多选项」）
# =====================================================================
$ClassicKey = 'Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32'

function Restart-Explorer {
    try {
        Get-Process explorer -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Milliseconds 1200
        if (-not (Get-Process explorer -ErrorAction SilentlyContinue)) { Start-Process explorer.exe }
    } catch { }
}

if ($ClassicMenu -or $RestoreMenu) {
    if ($RestoreMenu) {
        $k = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($ClassicKey)
        if ($k) { $k.Close() }
        [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree(
            'Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}', $false)
        Write-Host ""
        Write-Host "  已恢复 Windows 11 默认右键菜单。" -ForegroundColor Green
    } else {
        $k = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($ClassicKey)
        $k.SetValue('', '', [Microsoft.Win32.RegistryValueKind]::String)
        $k.Close()
        Write-Host ""
        Write-Host "  已切换为经典右键菜单（Win10 样式）。" -ForegroundColor Green
        Write-Host "  注意：这是全局改动，资源管理器所有右键都会变回旧样式。" -ForegroundColor Yellow
    }
    if (-not $WhatIf) { Restart-Explorer }
    Write-Host ""
    exit 0
}

if ($Uninstall) {
    Write-Host ""
    Write-Host "=== 卸载右键菜单 ===" -ForegroundColor Cyan
    $n = 0
    $targets = @()
    foreach ($ext in $Extensions) { $targets += (Get-SubKey $ext) }
    $targets += "Software\Classes\Directory\shell\$KeyName"
    foreach ($sub in $targets) {
        $root = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($sub)
        if ($root) {
            $root.Close()
            if (-not $WhatIf) {
                [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($sub, $false)
            }
            Write-Host ("  移除  HKCU\{0}" -f $sub) -ForegroundColor Yellow
            $n++
        }
    }
    Write-Host ""
    if ($n -eq 0) { Write-Host "  没有找到已注册的菜单项" }
    else { Write-Host ("  已移除 {0} 项。资源管理器按 F5 或重开窗口即可。" -f $n) -ForegroundColor Green }
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host ("=" * 64)
Write-Host "  用大肥鱼阅读器打开 · 右键菜单注册" -ForegroundColor Cyan
Write-Host ("=" * 64)

if (-not (Test-Path $Launcher)) {
    Write-Host ("!! 找不到启动脚本: {0}" -f $Launcher) -ForegroundColor Red
    exit 1
}

$pythonw = Find-Pythonw
if (-not $pythonw) {
    Write-Host "!! 没找到 Python，请先安装 Python 3.8+" -ForegroundColor Red
    exit 1
}

$hasIcon = Test-Path $Icon
$cmdValue = '"{0}" "{1}" "%1"' -f $pythonw, $Launcher

Write-Host ("  启动脚本 : {0}" -f $Launcher)
Write-Host ("  Python   : {0}" -f $pythonw)
Write-Host ("  图标     : {0}" -f $(if ($hasIcon) { $Icon } else { '(没有，用默认图标)' }))
Write-Host ("  显示文字 : {0}" -f $MenuText)
Write-Host ("  适用范围 : {0}" -f ($Extensions -join ', '))
Write-Host ""

Write-Host "=== 写入注册表（HKEY_CURRENT_USER）===" -ForegroundColor Cyan

foreach ($ext in $Extensions) {
    $sub = Get-SubKey $ext

    if ($WhatIf) {
        Write-Host ("  [预览] HKCU\{0}" -f $sub)
        Write-Host ("         (Default) = {0}" -f $MenuText)
        Write-Host ("         \command  = {0}" -f $cmdValue)
        continue
    }

    $k = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($sub)
    $k.SetValue('', $MenuText, [Microsoft.Win32.RegistryValueKind]::String)
    $k.SetValue('MultiSelectModel', 'Player', [Microsoft.Win32.RegistryValueKind]::String)
    if ($hasIcon) {
        $k.SetValue('Icon', $Icon, [Microsoft.Win32.RegistryValueKind]::String)
    }
    $k.Close()

    $kc = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey("$sub\command")
    $kc.SetValue('', $cmdValue, [Microsoft.Win32.RegistryValueKind]::String)
    $kc.Close()

    Write-Host ("  OK  HKCU\{0}" -f $sub) -ForegroundColor Green
}

# 文件夹单独一份：`*` 只管文件，文件夹走 Directory
$dirSub = "Software\Classes\Directory\shell\$KeyName"
if ($WhatIf) {
    Write-Host ("  [预览] HKCU\{0}" -f $dirSub)
} else {
    $kd = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($dirSub)
    $kd.SetValue('', $MenuText, [Microsoft.Win32.RegistryValueKind]::String)
    $kd.SetValue('MultiSelectModel', 'Player', [Microsoft.Win32.RegistryValueKind]::String)
    if ($hasIcon) { $kd.SetValue('Icon', $Icon, [Microsoft.Win32.RegistryValueKind]::String) }
    $kd.Close()
    $kdc = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey("$dirSub\command")
    $kdc.SetValue('', $cmdValue, [Microsoft.Win32.RegistryValueKind]::String)
    $kdc.Close()
    Write-Host ("  OK  HKCU\{0}" -f $dirSub) -ForegroundColor Green
}

Write-Host ""
if ($WhatIf) {
    Write-Host "  预览模式，没有写入任何东西。" -ForegroundColor Yellow
} else {
    Write-Host "  完成。随便右键一个文件看看效果。" -ForegroundColor Green
    Write-Host ""
    Write-Host "  提示：" -ForegroundColor DarkGray
    Write-Host "    - Windows 11 默认把旧式菜单收在「显示更多选项」里（Shift+F10 可直达）" -ForegroundColor DarkGray
    Write-Host "    - 点了没反应就看日志：" -ForegroundColor DarkGray
    Write-Host ("        {0}" -f $LogFile) -ForegroundColor DarkGray
    Write-Host "    - 不想要了：" -ForegroundColor DarkGray
    Write-Host ("        powershell -ExecutionPolicy Bypass -File `"{0}`" -Uninstall" -f $PSCommandPath) -ForegroundColor DarkGray
}
Write-Host ""
