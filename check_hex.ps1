$fs = [System.IO.File]::OpenRead('D:\roms\library\roms\psx\SLPS-00383.7z')
$buf = New-Object byte[] 16
$fs.Read($buf, 0, 16) | Out-Null
$fs.Close()
$hex = ($buf | ForEach-Object { $_.ToString('X2') }) -join ' '
Write-Host $hex
