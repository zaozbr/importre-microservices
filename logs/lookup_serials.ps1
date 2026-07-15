$datFile = "F:\importre\logs\psx_redump.dat"
$lines = Get-Content $datFile

# Build serial -> name mapping
$serialToName = @{}
$currentName = $null
$currentSerial = $null

foreach ($line in $lines) {
    $line = $line.Trim()
    if ($line -match '^name\s+"(.+)"' -and $line -notmatch '^name "Sony') {
        $currentName = $matches[1]
    }
    if ($line -match '^serial\s+"(.+)"' -and $currentName) {
        $currentSerial = $matches[1]
    }
    if ($line -eq ')' -and $currentName -and $currentSerial) {
        if (-not $serialToName.ContainsKey($currentSerial)) {
            $serialToName[$currentSerial] = $currentName
        }
        $currentName = $null
        $currentSerial = $null
    }
}

Write-Host "Loaded $($serialToName.Count) serial-to-name mappings"
Write-Host ""

# Files to look up
$files = @(
    "SLES-00314.chd",
    "SLES-00573.chd",
    "SLES-00590.1.chd",
    "SLES-01266.1.chd",
    "SLES-01416.chd",
    "SLES-01597.1.chd",
    "SLES-01597.chd",
    "SLES-01939.1.chd",
    "SLES-02375.chd",
    "SLES-03990.chd",
    "SLES-10973.chd",
    "SLES-11881.chd",
    "SLPM-87175.1.chd",
    "SLPS-09049.1.chd",
    "SCES-01707.1.chd"
)

foreach ($f in $files) {
    # Extract serial from filename
    $serial = ($f -replace '\.chd$', '' -replace '\.\d+$', '')
    
    if ($serialToName.ContainsKey($serial)) {
        Write-Host "  $f -> $($serialToName[$serial]) [$serial]"
    } else {
        Write-Host "  $f -> NOT FOUND [$serial]"
    }
}

Write-Host ""
Write-Host "=== Special cases ==="
Write-Host "  NBA-Power-Dunkers-3-SLUS-004550.chd -> checking SLUS-00455 and SLUS-004550"
if ($serialToName.ContainsKey("SLUS-00455")) {
    Write-Host "    SLUS-00455 -> $($serialToName['SLUS-00455'])"
}
if ($serialToName.ContainsKey("SLUS-004550")) {
    Write-Host "    SLUS-004550 -> $($serialToName['SLUS-004550'])"
}
