$dir = "D:\roms\library\roms\psx"
$files = Get-ChildItem "$dir\*.chd"

$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE|ESPM|UNL'
$serialPattern = "-($serialPrefixes)-\d{4,5}(\(Disc\d+\))?$"
$serialPatternWithDup = "-($serialPrefixes)-\d{4,5}(\(Disc\d+\))?\(\d+\)$"

$conforming = @()
$withDisc = @()
$withSuffix = @()
$withDiscSuffix = @()
$noSerial = @()
$other = @()

foreach ($f in $files) {
    $name = $f.BaseName
    
    if ($name -match $serialPattern) {
        $conforming += $f
    } elseif ($name -match $serialPatternWithDup) {
        $withSuffix += $f
    } elseif ($name -match "-($serialPrefixes)-\d{4,5}-Disc\d+$") {
        $withDisc += $f
    } elseif ($name -match "-($serialPrefixes)-\d{4,5}-Disc\d+\(\d+\)$") {
        $withDiscSuffix += $f
    } elseif ($name -match "($serialPrefixes)-\d{4,5}") {
        $other += $f
    } else {
        $noSerial += $f
    }
}

Write-Host "=== FINAL ANALYSIS ==="
Write-Host "Total .chd files: $($files.Count)"
Write-Host ""
Write-Host "Conforming (serial at end): $($conforming.Count)"
Write-Host "With (N) suffix (duplicates): $($withSuffix.Count)"
Write-Host "With -DiscN suffix: $($withDisc.Count)"
Write-Host "With -DiscN(N) suffix: $($withDiscSuffix.Count)"
Write-Host "Other (has serial, different format): $($other.Count)"
Write-Host "No serial at all: $($noSerial.Count)"
Write-Host ""

# Categorize no-serial files
$bios = @()
$test = @()
$homebrew = @()
$multipart = @()
$multitrack = @()
$genuine = @()

foreach ($f in $noSerial) {
    $name = $f.BaseName
    if ($name -match '^SCPH|^scph') {
        $bios += $f
    } elseif ($name -match 'UNKNOWN$|^test-|^SBL0$|^buzzy$|^nortis$|^japan-j3$|^WCG[12]$|^yicestar|^sp-1v1') {
        $test += $f
    } elseif ($name -match 'HBREW|NYMC|Celeste|Magic-Castle|Magic_Castle') {
        $homebrew += $f
    } elseif ($name -match '_\d+$') {
        $multipart += $f
    } elseif ($name -match 'Track-') {
        $multitrack += $f
    } else {
        $genuine += $f
    }
}

Write-Host "=== NO-SERIAL BREAKDOWN ==="
Write-Host "BIOS files: $($bios.Count)"
Write-Host "Test/UNKNOWN files: $($test.Count)"
Write-Host "Homebrew files: $($homebrew.Count)"
Write-Host "Multi-part (_N) files: $($multipart.Count)"
Write-Host "Multi-track (Track-N) files: $($multitrack.Count)"
Write-Host "Genuine games still without serial: $($genuine.Count)"
Write-Host ""

if ($genuine.Count -gt 0) {
    Write-Host "=== GENUINE GAMES WITHOUT SERIAL ==="
    $genuine | ForEach-Object { Write-Host "  $($_.Name)" }
    Write-Host ""
}

if ($test.Count -gt 0) {
    Write-Host "=== TEST/UNKNOWN FILES ==="
    $test | ForEach-Object { Write-Host "  $($_.Name)" }
    Write-Host ""
}

if ($bios.Count -gt 0) {
    Write-Host "=== BIOS FILES ==="
    $bios | ForEach-Object { Write-Host "  $($_.Name)" }
    Write-Host ""
}

if ($homebrew.Count -gt 0) {
    Write-Host "=== HOMEBREW FILES ==="
    $homebrew | ForEach-Object { Write-Host "  $($_.Name)" }
    Write-Host ""
}

# Summary
$totalConforming = $conforming.Count + $withDisc.Count + $withDiscSuffix.Count
Write-Host "=== SUMMARY ==="
Write-Host "Total files: $($files.Count)"
Write-Host "Properly named (with serial): $totalConforming ($([math]::Round($totalConforming/$files.Count*100, 1))%)"
Write-Host "Duplicates with (N) suffix: $($withSuffix.Count)"
Write-Host "No serial (BIOS/test/homebrew/multipart/genuine): $($noSerial.Count)"
Write-Host "  - BIOS: $($bios.Count)"
Write-Host "  - Test/UNKNOWN: $($test.Count)"
Write-Host "  - Homebrew: $($homebrew.Count)"
Write-Host "  - Multi-part tracks: $($multipart.Count)"
Write-Host "  - Multi-track: $($multitrack.Count)"
Write-Host "  - Genuine without serial: $($genuine.Count)"

# Save lists for reference
$withSuffix | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\final_duplicates.txt" -Encoding UTF8
$noSerial | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\final_no_serial.txt" -Encoding UTF8
