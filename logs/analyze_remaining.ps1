$dir = "D:\roms\library\roms\psx"
$files = Get-ChildItem "$dir\*.chd"

# Serial pattern - known PSX prefixes
$serialPattern = '-(SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE)-\d{4,5}$'

$conforming = @()
$nonConforming = @()
$withSuffix = @()  # files with (1), (2) etc
$noSerial = @()

foreach ($f in $files) {
    $name = $f.BaseName
    if ($name -match '\(\d+\)$') {
        $withSuffix += $f
    }
    if ($name -match $serialPattern) {
        $conforming += $f
    } else {
        $nonConforming += $f
        # Check if it has any serial-like pattern at all
        if ($name -notmatch '(SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE)-\d{4,5}') {
            $noSerial += $f
        }
    }
}

Write-Host "=== ANALYSIS OF REMAINING FILES ==="
Write-Host "Total .chd files: $($files.Count)"
Write-Host "Conforming to pattern: $($conforming.Count)"
Write-Host "Non-conforming: $($nonConforming.Count)"
Write-Host "  - With (N) suffix (duplicates): $($withSuffix.Count)"
Write-Host "  - No serial at all: $($noSerial.Count)"
Write-Host ""

Write-Host "=== FILES WITH (N) SUFFIX (first 50) ==="
$withSuffix | Select-Object -First 50 | ForEach-Object { Write-Host "  $($_.Name)" }
Write-Host ""

Write-Host "=== FILES WITH NO SERIAL (first 80) ==="
$noSerial | Select-Object -First 80 | ForEach-Object { Write-Host "  $($_.Name)" }
Write-Host ""

# Save full lists
$withSuffix | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\files_with_suffix.txt" -Encoding UTF8
$noSerial | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\files_no_serial.txt" -Encoding UTF8
$nonConforming | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\files_non_conforming.txt" -Encoding UTF8

Write-Host "Full lists saved to:"
Write-Host "  F:\importre\logs\files_with_suffix.txt ($($withSuffix.Count) files)"
Write-Host "  F:\importre\logs\files_no_serial.txt ($($noSerial.Count) files)"
Write-Host "  F:\importre\logs\files_non_conforming.txt ($($nonConforming.Count) files)"
