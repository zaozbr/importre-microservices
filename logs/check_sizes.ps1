$dir = "D:\roms\library\roms\psx"
Get-ChildItem "$dir\Actua-Pool*.chd" | Sort-Object Name | ForEach-Object {
    $sizeMB = [math]::Round($_.Length / 1MB, 1)
    Write-Host ("{0,-55} {1,10} MB" -f $_.Name, $sizeMB)
}
