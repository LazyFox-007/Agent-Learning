# 生成带水印 + 配乐的成片
#
# 用法（在 PowerShell 里）
#   .\tools\make-version.ps1 -Platform 'B站'      -Name '江西的那个人'
#   .\tools\make-version.ps1 -Platform '小红书'   -Name '墨有意'
#   .\tools\make-version.ps1 -Platform ''          -Name '墨有意'     # 只显示 @墨有意
#
# 水印会烧进像素（不是独立轨道），播放器关不掉，只能逐帧修复才能去。

param(
  [string]$Platform = 'B站',
  [Parameter(Mandatory = $true)][string]$Name,
  [string]$Suffix   = '',          # 副行文字，默认「大肥鱼阅读器」
  [string]$Video    = 'C:\StudyAI\docs\大肥鱼阅读器-介绍片.mp4',
  [string]$Music    = 'D:\AI\Mcptools\vediocut\EAC-design-world\.eac\outputs\f8b07e73-ca10-44e9-87c4-8fd273e64c96\d21633ac-a603-4add-ad84-9f624b216a20\music.wav',
  [string]$FFmpeg   = 'C:\tools\ffmpeg\ffmpeg.exe'
)

if (-not $Suffix) { $Suffix = '大肥鱼阅读器' }

# 水印主文案：@"平台 + 昵称"
$mark = if ($Platform) { "@$Platform$Name" } else { "@$Name" }
$tag  = if ($Platform) { $Platform } else { '纯净' }

$out = "C:\StudyAI\docs\大肥鱼阅读器-介绍片-$tag`版.mp4"

Write-Host "水印文案 : $mark"
Write-Host "副行     : $Suffix"
Write-Host "输出     : $out"

# ---- 滤镜 ----
# drawtext 里 : ' \ 需要转义；中文直接写没问题
$filter = @"
[0:v]drawtext=fontfile='C\:/Windows/Fonts/msyhbd.ttc':text='$mark':fontcolor=white@0.66:fontsize=34:shadowcolor=black@0.55:shadowx=2:shadowy=2:x=w-tw-64:y=h-th-46,drawtext=fontfile='C\:/Windows/Fonts/msyh.ttc':text='$Suffix':fontcolor=white@0.34:fontsize=22:shadowcolor=black@0.45:shadowx=1:shadowy=1:x=w-tw-66:y=h-th-88[v];
[1:a]highpass=f=45,volume='1.75*if(lt(t\,2)\,0.50*(t/2)\,if(lt(t\,6)\,0.50\,if(lt(t\,21)\,0.50+(t-6)/15*0.18\,if(lt(t\,29.5)\,0.68+(t-21)/8.5*0.14\,if(lt(t\,41.5)\,0.82+(t-29.5)/12*0.18\,if(lt(t\,58.5)\,1.00-(t-41.5)/17*0.12\,if(lt(t\,62)\,0.88-(t-58.5)/3.5*0.13\,if(lt(t\,65.5)\,0.75*(65.5-t)/3.5\,0))))))))':eval=frame,alimiter=limit=0.95:level=false,aresample=48000[a]
"@

$flt = Join-Path $env:TEMP ("wm-" + [guid]::NewGuid().ToString('N').Substring(0,8) + ".filter")
[System.IO.File]::WriteAllText($flt, $filter, (New-Object System.Text.UTF8Encoding($false)))

# ---- 渲染 ----
if (Test-Path $out) { Remove-Item $out -Force }
& $FFmpeg -y -i $Video -i $Music -filter_complex_script $flt `
  -map '[v]' -map '[a]' -c:v libx264 -preset medium -crf 18 `
  -pix_fmt yuv420p -c:a aac -b:a 192k -ar 48000 -movflags +faststart -shortest $out 2>&1 |
  Select-String 'error|Invalid|No such' | Select-Object -First 4 | ForEach-Object { Write-Host "  ⚠ $_" }

Remove-Item $flt -Force -ErrorAction SilentlyContinue

if (Test-Path $out) {
  $mb = (Get-Item $out).Length / 1MB
  Write-Host ("✅ 完成  {0:N1} MB" -f $mb) -ForegroundColor Green

  # 抽右下角确认水印
  $chk = Join-Path $env:TEMP ("wmchk-" + [guid]::NewGuid().ToString('N').Substring(0,6) + ".png")
  & $FFmpeg -y -ss 40 -i $out -frames:v 1 -vf "crop=860:220:1080:860" $chk 2>&1 | Out-Null
  $dst = "C:\StudyAI\_webapp\_shots\wm-$tag.png"
  Move-Item $chk $dst -Force -ErrorAction SilentlyContinue
  Write-Host "  水印预览: $dst"
}
