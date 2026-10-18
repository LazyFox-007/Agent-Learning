param(
    [Parameter(Mandatory=$true)][string]$Docx,
    [Parameter(Mandatory=$true)][string]$Pdf
)
$ErrorActionPreference = "Stop"
$existing = @(Get-Process WINWORD -ErrorAction SilentlyContinue)
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $null
try {
    $doc = $word.Documents.Open($Docx, $false, $false)
    try { $doc.Fields.Update() | Out-Null } catch {}
    try {
        if ($doc.TablesOfContents.Count -gt 0) { $doc.TablesOfContents.Item(1).Update() | Out-Null }
    } catch {}
    $doc.Repaginate()
    $doc.Save()
    if (Test-Path $Pdf) { Remove-Item -LiteralPath $Pdf -Force }
    $doc.ExportAsFixedFormat($Pdf, 17)
    $pages = $doc.ComputeStatistics(2)
    "pages=$pages"
}
finally {
    if ($doc -ne $null) { try { $doc.Close(0) } catch {} }
    if ($existing.Count -eq 0) { try { $word.Quit() } catch {} }
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
