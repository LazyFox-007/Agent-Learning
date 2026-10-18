param(
    [Parameter(Mandatory=$true)][string]$Pptx,
    [Parameter(Mandatory=$true)][string]$Pdf
)
$ErrorActionPreference = "Stop"
$existing = @(Get-Process POWERPNT -ErrorAction SilentlyContinue)
$ppt = New-Object -ComObject PowerPoint.Application
$pres = $null
try {
    $pres = $ppt.Presentations.Open($Pptx, $true, $false, $true)
    if (Test-Path $Pdf) { Remove-Item -LiteralPath $Pdf -Force }
    $pres.SaveAs($Pdf, 32)
    "slides=$($pres.Slides.Count)"
}
finally {
    if ($pres -ne $null) { try { $pres.Close() } catch {} }
    if ($existing.Count -eq 0) { try { $ppt.Quit() } catch {} }
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($ppt) | Out-Null
}
