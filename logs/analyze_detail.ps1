$dir = "D:\roms\library\roms\psx"
$files = Get-ChildItem "$dir\*.chd"

$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE'

# Categories
$withSuffix = @()        # (1), (2) etc
$withDisc = @()          # -Disc1, -Disc2 after serial
$withDiscAndSuffix = @() # -Disc1(1) etc
$noSerial = @()          # no serial at all
$incompleteSerial = @()  # serial but too short (e.g. SLPS-010)
$other = @()             # has serial but other issue

foreach ($f in $files) {
    $name = $f.BaseName
    
    # Check for (N) suffix
    $hasSuffix = $name -match '\(\d+\)$'
    
    # Check for disc suffix
    $hasDisc = $name -match '-Disc\d+$' -or $name -match '-Disc\d+\(\d+\)$'
    
    # Check for serial
    $hasSerial = $name -match "($serialPrefixes)-\d{4,5}"
    $hasIncompleteSerial = $name -match "($serialPrefixes)-\d{1,3}$" -or $name -match "($serialPrefixes)-\d{1,3}\(\d+\)$"
    
    if (-not $hasSerial -and -not $hasIncompleteSerial) {
        $noSerial += $f
    } elseif ($hasIncompleteSerial -and -not $hasSerial) {
        $incompleteSerial += $f
    } elseif ($hasSuffix -and $hasDisc) {
        $withDiscAndSuffix += $f
    } elseif ($hasSuffix) {
        $withSuffix += $f
    } elseif ($hasDisc) {
        $withDisc += $f
    } else {
        $other += $f
    }
}

Write-Host "=== DETAILED ANALYSIS OF NON-CONFORMING FILES ==="
Write-Host "Total .chd files: $($files.Count)"
Write-Host ""
Write-Host "Category counts:"
Write-Host "  With (N) suffix only (duplicates): $($withSuffix.Count)"
Write-Host "  With -DiscN suffix only: $($withDisc.Count)"
Write-Host "  With -DiscN(N) suffix: $($withDiscAndSuffix.Count)"
Write-Host "  No serial at all: $($noSerial.Count)"
Write-Host "  Incomplete serial: $($incompleteSerial.Count)"
Write-Host "  Other (has serial, different issue): $($other.Count)"
Write-Host ""

Write-Host "=== INCOMPLETE SERIAL ==="
$incompleteSerial | ForEach-Object { Write-Host "  $($_.Name)" }
Write-Host ""

Write-Host "=== OTHER (has serial, different issue) - first 30 ==="
$other | Select-Object -First 30 | ForEach-Object { Write-Host "  $($_.Name)" }
Write-Host ""

Write-Host "=== WITH -DiscN SUFFIX (first 30) ==="
$withDisc | Select-Object -First 30 | ForEach-Object { Write-Host "  $($_.Name)" }
Write-Host ""

Write-Host "=== WITH -DiscN(N) SUFFIX (first 20) ==="
$withDiscAndSuffix | Select-Object -First 20 | ForEach-Object { Write-Host "  $($_.Name)" }
Write-Host ""

# Save lists
$withDisc | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\files_with_disc.txt" -Encoding UTF8
$withDiscAndSuffix | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\files_with_disc_suffix.txt" -Encoding UTF8
$other | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\files_other.txt" -Encoding UTF8

Write-Host "Saved to:"
Write-Host "  files_with_disc.txt ($($withDisc.Count) files)"
Write-Host "  files_with_disc_suffix.txt ($($withDiscAndSuffix.Count) files)"
Write-Host "  files_other.txt ($($other.Count) files)"
