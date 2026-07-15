$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE'
$serialRegex = "($serialPrefixes)-\d{3,6}"
$noSerial = @(Get-ChildItem 'D:\roms\library\roms\psx' -Filter '*.chd' | Where-Object { $_.Name -inotmatch $serialRegex })
Write-Output "Total without serial: $($noSerial.Count)"
$noSerial | Select-Object -First 10 | ForEach-Object { Write-Output $_.Name }
