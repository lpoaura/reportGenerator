param([string]$File)
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
    $d = $w.Documents.Open($File, $false, $false)
    $n = $d.Fields.Update()
    foreach ($toc in $d.TablesOfContents) { $toc.Update() }
    $out = $File -replace '\.docx$', '_maj.pdf'
    $d.ExportAsFixedFormat($out, 17)
    "OK  champs mis à jour (retour $n), sommaires : $($d.TablesOfContents.Count), pages : $($d.ComputeStatistics(2))"
    $d.Close(0)
} catch {
    "ECHEC : $($_.Exception.Message)"
}
$w.Quit()
