$dirs = Get-ChildItem 'D:\roms\library\roms\psx' -Directory
foreach ($d in $dirs) {
    Write-Output ("--- " + $d.Name + " ---")
    $items = Get-ChildItem -LiteralPath $d.FullName -ErrorAction SilentlyContinue
    if ($items) {
        $items | Select-Object Name, Length | Format-Table -AutoSize
    } else {
        Write-Output "(vazio)"
    }
}
