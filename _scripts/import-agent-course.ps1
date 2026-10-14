# =====================================================================
#  导入 AI Agent 全栈课程
#
#  上游：https://github.com/callous-0923/agent-study  (MIT License)
#
#  本脚本做四件事：
#    1) 克隆上游仓库（浅克隆，用完即删）
#    2) 复制 HTML 讲义与 Python 源码，保留章节目录结构
#    3) 把硬编码的线上绝对 URL 改写为相对路径 -> 可完全离线浏览
#    4) 移除 busuanzi 访问统计（外部 CDN，本地无意义）
#
#  版权：课程内容版权归原作者 callous-0923 所有，遵循 MIT License。
#        本脚本仅做本地化转换，不修改课程实质内容。
# =====================================================================
$ErrorActionPreference = 'Continue'

# ---------- 路径（相对于脚本位置，不写死绝对路径）----------
$RepoRoot   = Split-Path $PSScriptRoot -Parent          # 仓库根目录
$Dest       = Join-Path $RepoRoot '01-AI-Agent全栈课程'
$Src        = Join-Path $RepoRoot '_agent-study-src'
$Upstream   = 'https://github.com/callous-0923/agent-study.git'
$SitePrefix = 'https://callous-0923.github.io/agent-study/'

Write-Host ""
Write-Host ("=" * 66)
Write-Host "  导入 AI Agent 全栈课程" -ForegroundColor Cyan
Write-Host ("=" * 66)
Write-Host ("  仓库根目录 : {0}" -f $RepoRoot)
Write-Host ("  课程目标   : {0}" -f $Dest)
Write-Host ""

# ---------- 1) 克隆上游 ----------
Write-Host "=== 1/4) 克隆上游仓库 ===" -ForegroundColor Cyan

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "  [错误] 没有找到 git，请先安装：https://git-scm.com/downloads" -ForegroundColor Red
    exit 1
}

if (Test-Path $Src) { Remove-Item $Src -Recurse -Force -EA SilentlyContinue }

$env:GIT_TERMINAL_PROMPT = '0'
$sw = [Diagnostics.Stopwatch]::StartNew()
$log = & git -c core.longpaths=true clone --depth 1 --quiet $Upstream $Src 2>&1
$sw.Stop()

if ($LASTEXITCODE -ne 0) {
    Write-Host "  [错误] 克隆失败：" -ForegroundColor Red
    $log | ForEach-Object { Write-Host ("    " + $_) }
    Write-Host ""
    Write-Host "  可能原因：网络不通，或 git 的 SSL 配置有问题。" -ForegroundColor Yellow
    Write-Host "  如果报 'unable to get local issuer certificate'，可临时关闭校验（仅本次）：" -ForegroundColor Yellow
    Write-Host "    git -c http.sslVerify=false clone --depth 1 $Upstream `"$Src`"" -ForegroundColor Yellow
    exit 1
}
Write-Host ("  OK  用时 {0:N1}s" -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green

# ---------- 2) 复制章节与根文件 ----------
Write-Host ""
Write-Host "=== 2/4) 复制内容 ===" -ForegroundColor Cyan

if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
New-Item -ItemType Directory -Path $Dest -Force | Out-Null

$chapters = Get-ChildItem $Src -Directory | Where-Object { $_.Name -like 'chapter_*' } | Sort-Object Name
$totalHtml = 0; $totalPy = 0
foreach ($c in $chapters) {
    $out = Join-Path $Dest $c.Name
    New-Item -ItemType Directory -Path $out -Force | Out-Null
    Get-ChildItem $c.FullName -File | ForEach-Object {
        Copy-Item $_.FullName $out -Force
        if ($_.Extension -eq '.html') { $totalHtml++ } elseif ($_.Extension -eq '.py') { $totalPy++ }
    }
}
Write-Host ("  {0} 个章节目录：{1} 个 HTML + {2} 个 Python" -f $chapters.Count, $totalHtml, $totalPy)

Copy-Item (Join-Path $Src 'index.html') $Dest -Force
foreach ($f in @('LICENSE', 'README.md', 'requirements.txt', 'pyproject.toml')) {
    $p = Join-Path $Src $f
    if (Test-Path $p) { Copy-Item $p $Dest -Force }
}
Write-Host "  根文件：index.html, LICENSE, README.md, requirements.txt, pyproject.toml"

# 上游的 README.md 改名为「课程原版」，避免覆盖我们自己的索引
$upstreamReadme = Join-Path $Dest 'README.md'
if (Test-Path $upstreamReadme) {
    Move-Item $upstreamReadme (Join-Path $Dest 'README-课程原版.md') -Force
}

# ---------- 3) 本地化：改写链接、移除外部脚本 ----------
Write-Host ""
Write-Host "=== 3/4) 本地化（链接改写 / 移除外部依赖）===" -ForegroundColor Cyan

$allHtml   = Get-ChildItem $Dest -Recurse -Filter *.html
$urlFixed  = 0
$scriptFix = 0
$badgeFix  = 0

foreach ($f in $allHtml) {
    $isRoot = ($f.DirectoryName -eq $Dest)
    $raw = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)

    # 绝对 URL -> 相对路径（根目录用 ''，章节页用 '../'）
    $repl = if ($isRoot) { '' } else { '../' }
    $n = ([regex]::Matches($raw, [regex]::Escape($SitePrefix))).Count
    if ($n -gt 0) { $raw = $raw.Replace($SitePrefix, $repl); $urlFixed += $n }

    # 移除 busuanzi 统计脚本与徽章
    $tmp = [regex]::Replace($raw, '<script[^>]*busuanzi[^>]*>\s*</script>', '')
    if ($tmp -ne $raw) { $scriptFix++; $raw = $tmp }
    $tmp = [regex]::Replace($raw, '<div class="busuanzi-badge">[\s\S]*?</div>\s*(?=</div>)', '')
    if ($tmp -ne $raw) { $badgeFix++; $raw = $tmp }

    # 移除残留的 busuanzi CSS 规则
    $raw = [regex]::Replace($raw, '(?m)^\s*\.busuanzi[\w\-\.\s,>]*\{[^}]*\}\s*$', '')

    [System.IO.File]::WriteAllText($f.FullName, $raw, (New-Object System.Text.UTF8Encoding($false)))
}
Write-Host ("  改写绝对 URL   : {0} 处" -f $urlFixed)
Write-Host ("  移除统计脚本   : {0} 个文件" -f $scriptFix)
Write-Host ("  移除访问徽章   : {0} 个文件" -f $badgeFix)

# ---------- 4) 校验 ----------
Write-Host ""
Write-Host "=== 4/4) 校验 ===" -ForegroundColor Cyan

$leftAbs = 0; $leftScript = 0
foreach ($f in $allHtml) {
    $c = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)
    $leftAbs    += ([regex]::Matches($c, [regex]::Escape($SitePrefix))).Count
    $leftScript += ([regex]::Matches($c, 'busuanzi')).Count
}

# 全量验证站内链接可解析
$good = 0; $bad = 0; $badList = @()
foreach ($f in $allHtml) {
    $c = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)
    $dir = $f.DirectoryName
    foreach ($m in [regex]::Matches($c, 'href="([^"]+)"')) {
        $href = $m.Groups[1].Value
        if ($href -match '^(https?:|#|mailto:|/)') { continue }   # 外链/锚点/根路径跳过
        if (Test-Path (Join-Path $dir ($href -replace '/', '\'))) { $good++ }
        else { $bad++; if ($badList.Count -lt 5) { $badList += ("{0} -> {1}" -f $f.Name, $href) } }
    }
}

Write-Host ("  残留绝对 URL   : {0}  {1}" -f $leftAbs,    $(if ($leftAbs -eq 0)    { 'OK' } else { '需检查' })) -ForegroundColor $(if ($leftAbs -eq 0) { 'Green' } else { 'Yellow' })
Write-Host ("  残留 busuanzi  : {0}  {1}" -f $leftScript, $(if ($leftScript -eq 0) { 'OK' } else { '需检查' })) -ForegroundColor $(if ($leftScript -eq 0) { 'Green' } else { 'Yellow' })
Write-Host ("  站内链接       : {0} 可解析 / {1} 失效" -f $good, $bad) -ForegroundColor $(if ($bad -eq 0) { 'Green' } else { 'Yellow' })
if ($badList.Count) { $badList | ForEach-Object { Write-Host ("    " + $_) -ForegroundColor DarkGray } }

# ---------- 清理克隆源 ----------
Remove-Item $Src -Recurse -Force -EA SilentlyContinue

$sz  = (Get-ChildItem $Dest -Recurse -File | Measure-Object Length -Sum).Sum
$cnt = (Get-ChildItem $Dest -Recurse -File | Measure-Object).Count
Write-Host ""
Write-Host ("=" * 66)
Write-Host ("  ✅ 完成：{0:N2} MB / {1} 个文件" -f ($sz / 1MB), $cnt) -ForegroundColor Green
Write-Host ("  入口：{0}\index.html" -f $Dest)
Write-Host ("=" * 66)
Write-Host ""
