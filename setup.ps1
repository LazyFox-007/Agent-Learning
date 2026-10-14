# =====================================================================
#  agent学习平台 · 一键安装
#
#  用法（在仓库根目录）：
#      powershell -ExecutionPolicy Bypass -File setup.ps1
#
#  做的事：
#      1) 检查 Python / git / Node 环境
#      2) 从上游拉取 AI Agent 全栈课程并本地化
#      3) 生成课程索引与首页路线数据
#      4) 询问是否立即启动
# =====================================================================
$ErrorActionPreference = 'Continue'

$RepoRoot = $PSScriptRoot
$CourseDir = Join-Path $RepoRoot '01-AI-Agent全栈课程'
$BuildDir  = Join-Path $RepoRoot '_webapp\_build'

Write-Host ""
Write-Host ("=" * 68)
Write-Host "  agent学习平台 · 一键安装" -ForegroundColor Cyan
Write-Host ("=" * 68)
Write-Host ("  安装目录：{0}" -f $RepoRoot)
Write-Host ""

# ---------- 1) 环境检查 ----------
Write-Host "=== 1/4) 环境检查 ===" -ForegroundColor Cyan

function Find-Exe($names) {
    foreach ($n in $names) {
        $c = Get-Command $n -ErrorAction SilentlyContinue
        if ($c) { return $c.Source }
    }
    return $null
}

# Python（必需）
$pyExe = Find-Exe @('py', 'python', 'python3')
if ($pyExe) {
    $pyVer = (& $pyExe --version 2>&1) -join ''
    Write-Host ("  ✅ Python : {0}" -f $pyVer) -ForegroundColor Green
} else {
    Write-Host "  ❌ 未找到 Python" -ForegroundColor Red
    Write-Host "     请安装 Python 3.8+：https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "     安装时务必勾选 'Add Python to PATH'" -ForegroundColor Yellow
    exit 1
}

# git（必需，用于拉取课程）
$gitExe = Find-Exe @('git')
if ($gitExe) {
    Write-Host ("  ✅ git    : {0}" -f ((& git --version 2>&1) -join '')) -ForegroundColor Green
} else {
    Write-Host "  ❌ 未找到 git" -ForegroundColor Red
    Write-Host "     请安装：https://git-scm.com/downloads" -ForegroundColor Yellow
    exit 1
}

# Node（可选，仅重新生成数据时需要）
$nodeExe = Find-Exe @('node')
if ($nodeExe) {
    Write-Host ("  ✅ Node   : {0}" -f ((& node --version 2>&1) -join '')) -ForegroundColor Green
    $hasNode = $true
} else {
    Write-Host "  ⚠️  未找到 Node（可选）" -ForegroundColor Yellow
    Write-Host "     首页路线数据已随仓库提供，不装也能正常使用。" -ForegroundColor DarkGray
    Write-Host "     仅在需要重新生成索引时才用到：https://nodejs.org/" -ForegroundColor DarkGray
    $hasNode = $false
}

# ---------- 2) 拉取课程 ----------
Write-Host ""
Write-Host "=== 2/4) 拉取课程 ===" -ForegroundColor Cyan

if (Test-Path (Join-Path $CourseDir 'index.html')) {
    Write-Host "  课程已存在，跳过。" -ForegroundColor DarkGray
    Write-Host "  如需强制重新拉取，先删除目录：" -ForegroundColor DarkGray
    Write-Host ("    Remove-Item '{0}' -Recurse -Force" -f $CourseDir) -ForegroundColor DarkGray
} else {
    & (Join-Path $RepoRoot '_scripts\import-agent-course.ps1')
    if (-not (Test-Path (Join-Path $CourseDir 'index.html'))) {
        Write-Host ""
        Write-Host "  ❌ 课程拉取失败，安装未完成。" -ForegroundColor Red
        Write-Host "     常见原因是网络无法访问 GitHub。" -ForegroundColor Yellow
        exit 1
    }
}

# ---------- 3) 生成索引与数据 ----------
Write-Host ""
Write-Host "=== 3/4) 生成索引与路线数据 ===" -ForegroundColor Cyan

if (-not $hasNode) {
    Write-Host "  跳过（无 Node）。仓库自带的 static/roadmap.js 仍可使用。" -ForegroundColor DarkGray
} elseif (-not (Test-Path $BuildDir)) {
    Write-Host "  跳过（未找到 _webapp\_build）。" -ForegroundColor DarkGray
} else {
    Push-Location $BuildDir

    if (Test-Path 'gen-index.js') {
        Write-Host "  生成课程索引 README ..." -ForegroundColor DarkGray
        & node 'gen-index.js' 2>&1 | ForEach-Object { Write-Host ("    " + $_) -ForegroundColor DarkGray }
    }

    if (Test-Path 'gen-roadmap.js') {
        Write-Host "  生成首页路线数据 ..." -ForegroundColor DarkGray
        & node 'gen-roadmap.js' 2>&1 | ForEach-Object { Write-Host ("    " + $_) -ForegroundColor DarkGray }
    }

    Pop-Location
    Write-Host "  ✅ 完成" -ForegroundColor Green
}

# ---------- 4) 收尾 ----------
Write-Host ""
Write-Host "=== 4/4) 完成 ===" -ForegroundColor Cyan
Write-Host ""

$sz  = (Get-ChildItem $CourseDir -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum
$cnt = (Get-ChildItem $CourseDir -Recurse -File -EA SilentlyContinue | Measure-Object).Count
Write-Host ("  课程：{0:N1} MB / {1} 个文件（7 层 37 章）" -f ($sz / 1MB), $cnt)
Write-Host ""

Write-Host ("=" * 68)
Write-Host "  启动方式" -ForegroundColor Cyan
Write-Host ("=" * 68)
Write-Host "  双击  _webapp\start.bat"
Write-Host "  或在仓库根目录执行："
Write-Host "        cd _webapp"
Write-Host "        python server.py"
Write-Host ""
Write-Host "  浏览器会自动打开，默认地址 http://127.0.0.1:8777/"
Write-Host ""

$ans = Read-Host "  现在启动？(Y/n)"
if ($ans -eq '' -or $ans -match '^[Yy]') {
    Start-Process -FilePath (Join-Path $RepoRoot '_webapp\start.bat')
}

Write-Host ""
