$dir = "D:\roms\library\roms\psx"
$chdman = "D:\roms\library\chdman.exe"

# Test with a few no-serial files
$testFiles = @(
    "Aqua-GT.chd",
    "Battle-Arena-Toshinden.chd",
    "BLADE.chd",
    "Card-Shark.chd",
    "Chaos-Break.chd",
    "Final-Fantasy-V.chd",
    "Re-Volt.chd",
    "Vandal-Hearts-II.chd",
    "Ten-Pin-Alley.chd",
    "Tilt.chd"
)

foreach ($f in $testFiles) {
    $path = Join-Path $dir $f
    if (Test-Path $path) {
        Write-Host "=== $f ==="
        & $chdman info -i $path 2>&1 | Select-Object -First 20
        Write-Host ""
    }
}
