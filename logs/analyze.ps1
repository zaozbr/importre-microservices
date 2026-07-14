$dir = 'D:\roms\library\roms\psx'
$files = Get-ChildItem $dir -Filter '*.chd'
$total = $files.Count

# Pattern: starts with letter, ends with -SERIAL(4 letters-4to6 digits).chd, no parentheses/brackets
$goodPattern = '^[A-Za-z][A-Za-z0-9].*-[A-Z]{4}-\d{4,6}\.chd$'
$badChars = '[\(\)\[\]]'

$matched = @($files | Where-Object { $_.Name -match $goodPattern -and $_.Name -notmatch $badChars })
$notmatched = @($files | Where-Object { $_.Name -notmatch $goodPattern -or $_.Name -match $badChars })

Write-Output "Total: $total"
Write-Output "Already OK: $($matched.Count)"
Write-Output "Need rename: $($notmatched.Count)"

# Categorize problems
$noSerial = @($notmatched | Where-Object { $_.Name -notmatch '-[A-Z]{4}-\d{4,6}\.chd$' })
$hasParen = @($notmatched | Where-Object { $_.Name -match '[\(\)\[\]]' })
$startsWithNonLetter = @($notmatched | Where-Object { $_.Name -notmatch '^[A-Za-z]' })

Write-Output "--- Categories (overlap possible) ---"
Write-Output "No serial at end: $($noSerial.Count)"
Write-Output "Has parens/brackets: $($hasParen.Count)"
Write-Output "Starts with non-letter: $($startsWithNonLetter.Count)"

Write-Output "--- Sample no-serial (first 40) ---"
$noSerial | Select-Object -First 40 -ExpandProperty Name
