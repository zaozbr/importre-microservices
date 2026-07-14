$dir = 'D:\roms\library\roms\psx'
$files = Get-ChildItem $dir -Filter '*.chd'
$goodPattern = '^[A-Za-z][A-Za-z0-9].*-[A-Z]{4}-\d{4,6}\.chd$'
$badChars = '[\(\)\[\]]'

$notmatched = @($files | Where-Object { $_.Name -notmatch $goodPattern -or $_.Name -match $badChars })

# Has serial anywhere in name?
$hasSerial = @($notmatched | Where-Object { $_.Name -match '[A-Z]{4}-\d{4,6}' })
$noSerial = @($notmatched | Where-Object { $_.Name -notmatch '[A-Z]{4}-\d{4,6}' })

Write-Output "Need rename total: $($notmatched.Count)"
Write-Output "  Has serial in name (easy): $($hasSerial.Count)"
Write-Output "  No serial at all (hard): $($noSerial.Count)"

# Export lists
$notmatched | Select-Object -ExpandProperty Name | Sort-Object | Out-File -FilePath 'F:\importre\logs\to_rename.txt' -Encoding UTF8
$noSerial | Select-Object -ExpandProperty Name | Sort-Object | Out-File -FilePath 'F:\importre\logs\no_serial.txt' -Encoding UTF8

Write-Output "--- No-serial samples (first 50) ---"
$noSerial | Select-Object -First 50 -ExpandProperty Name
