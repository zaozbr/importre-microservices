$dir = 'D:\roms\library\roms\psx'
$files = Get-ChildItem $dir -Filter '*.chd'
$goodPattern = '^[A-Za-z][A-Za-z0-9].*-[A-Z]{4}-\d{4,6}\.chd$'
$badChars = '[\(\)\[\]]'

$notmatched = @($files | Where-Object { $_.Name -notmatch $goodPattern -or $_.Name -match $badChars })
$hasSerial = @($notmatched | Where-Object { $_.Name -match '[A-Z]{4}-\d{4,6}' })

# Show variety of patterns
Write-Output "=== Samples with serial but needing cleanup (first 80) ==="
$hasSerial | Select-Object -First 80 -ExpandProperty Name
