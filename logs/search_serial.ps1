$binFile = "C:\temp_chd\test.bin"
$bytes = [System.IO.File]::ReadAllBytes($binFile)
$text = [System.Text.Encoding]::ASCII.GetString($bytes)

# Search for serial pattern
$serialPattern = '(SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE)[-_]?\d{4,5}'
$matches = [regex]::Matches($text, $serialPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
$found = @()
foreach ($m in $matches) {
    $found += $m.Value.ToUpper()
}
$unique = $found | Select-Object -Unique
Write-Host "Serials found in Aqua-GT.bin:"
$unique | ForEach-Object { Write-Host "  $_" }

# Search for BOOT line
$bootMatches = [regex]::Matches($text, 'BOOT\s*=\s*[^\r\n;]+')
foreach ($m in $bootMatches) {
    Write-Host "  BOOT: $($m.Value.Trim())"
}

# Search for SYSTEM.CNF
$cnfIdx = $text.IndexOf('SYSTEM.CNF')
if ($cnfIdx -ge 0) {
    $start = [math]::Max(0, $cnfIdx - 50)
    $len = [math]::Min(500, $text.Length - $start)
    $context = $text.Substring($start, $len)
    Write-Host "  Context around SYSTEM.CNF:"
    $context -split "`n" | Select-Object -First 10 | ForEach-Object { Write-Host "    $_" }
}
