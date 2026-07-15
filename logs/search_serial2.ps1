$binFile = "C:\temp_chd\test.bin"
$bytes = [System.IO.File]::ReadAllBytes($binFile)

# ISO 9660 Primary Volume Descriptor is at sector 16 (offset 0x8000)
# Volume ID is at offset 40, length 32
if ($bytes.Length -gt 0x8028) {
    $volId = [System.Text.Encoding]::ASCII.GetString($bytes, 0x8028, 32).Trim()
    Write-Host "Volume ID: '$volId'"
    
    # Also check volume descriptor at offset 40
    $volId2 = [System.Text.Encoding]::ASCII.GetString($bytes, 0x8000 + 40, 32).Trim()
    Write-Host "Volume ID (offset 40): '$volId2'"
}

# Search for any SL/SI/SC pattern (broader)
$text = [System.Text.Encoding]::ASCII.GetString($bytes)

# Search for common PSX executable names (SXXX_XXX.XX pattern)
$exeMatches = [regex]::Matches($text, 'S[A-Z]{3}_?\d{3,5}\.?\d{2}', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$exes = @()
foreach ($m in $exeMatches) {
    $exes += $m.Value.ToUpper()
}
$uniqueExes = $exes | Select-Object -Unique
if ($uniqueExes.Count -gt 0) {
    Write-Host "PSX executable patterns found:"
    $uniqueExes | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }
}

# Search for BOOT
$bootIdx = $text.IndexOf('BOOT')
if ($bootIdx -ge 0) {
    $context = $text.Substring($bootIdx, [math]::Min(200, $text.Length - $bootIdx))
    Write-Host "BOOT context: $($context.Substring(0, [math]::Min(100, $context.Length)))"
}

# Search for cdrom:
$cdromIdx = $text.IndexOf('cdrom:')
if ($cdromIdx -ge 0) {
    $context = $text.Substring($cdromIdx, [math]::Min(100, $text.Length - $cdromIdx))
    Write-Host "cdrom: context: $context"
}

# Search for any 4-letter prefix followed by digits
$patternMatches = [regex]::Matches($text, '[A-Z]{4}[-_]?\d{5}', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$pats = @()
foreach ($m in $patternMatches) {
    $pats += $m.Value.ToUpper()
}
$uniquePats = $pats | Select-Object -Unique
if ($uniquePats.Count -gt 0) {
    Write-Host "4-letter+5-digit patterns:"
    $uniquePats | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" }
}
