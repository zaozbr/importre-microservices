$f = (Get-ChildItem 'D:\roms\library\roms\psx\*.chd' | Where-Object { $_.Length -gt 1MB } | Select-Object -First 1).FullName
Write-Host "File: $f"
$fs = [System.IO.File]::OpenRead($f)
$buf = New-Object byte[] 16
$fs.Read($buf, 0, 16) | Out-Null
$fs.Dispose()
$magic = [System.Text.Encoding]::ASCII.GetString($buf, 0, 8)
Write-Host "Magic: '$magic'"
$hex = ($buf[0..7] | ForEach-Object { '{0:X2}' -f $_ }) -join ' '
Write-Host "Hex: $hex"
