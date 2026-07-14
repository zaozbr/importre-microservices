$dir = 'D:\roms\library\roms\psx'
$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE'
$serialRegex = "($serialPrefixes)-\d{3,6}"
$goodPattern = "^[A-Za-z][A-Za-z0-9].*$serialRegex(\(\d+\))?\.chd$"
$badChars = '[\(\)\[\]]'

$files = Get-ChildItem $dir -Filter '*.chd'
$total = $files.Count
$good = @($files | Where-Object { $_.Name -match $goodPattern -and $_.Name -notmatch $badChars })
$needRename = @($files | Where-Object { $_.Name -notmatch $goodPattern -or $_.Name -match $badChars })
$hasSerial = @($needRename | Where-Object { $_.Name -imatch $serialRegex })
$noSerial = @($needRename | Where-Object { $_.Name -inotmatch $serialRegex })

Write-Output "Total: $total"
Write-Output "Already OK: $($good.Count)"
Write-Output "Need rename: $($needRename.Count)"
Write-Output "  Has valid serial: $($hasSerial.Count)"
Write-Output "  No serial: $($noSerial.Count)"

# Export no-serial list
$noSerial | Select-Object -ExpandProperty Name | Sort-Object | Out-File -FilePath 'F:\importre\logs\no_serial.txt' -Encoding UTF8

# Export has-serial list (still needs cleanup)
$hasSerial | Select-Object -ExpandProperty Name | Sort-Object | Out-File -FilePath 'F:\importre\logs\has_serial.txt' -Encoding UTF8

Write-Output "`n--- Has serial samples (first 30) ---"
$hasSerial | Select-Object -First 30 -ExpandProperty Name
Write-Output "`n--- No serial samples (first 50) ---"
$noSerial | Select-Object -First 50 -ExpandProperty Name
