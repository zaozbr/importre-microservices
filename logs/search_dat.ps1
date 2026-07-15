$datFile = "F:\importre\logs\psx_redump.dat"
$lines = Get-Content $datFile

$gameMap = @{}
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
        if (-not $gameMap.ContainsKey($currentName)) {
            $gameMap[$currentName] = $currentSerial
        }
        $currentName = $null
        $currentSerial = $null
    }
}

# Search for specific games in the DAT
$searchTerms = @(
    "Simple 1500 Series Vol. 14",
    "Simple 1500 Series Vol. 5",
    "Simple 1500 Series Vol. 74",
    "Simple 1500 Series Vol. 78",
    "Command & Conquer",
    "Conveni",
    "Power Instinct",
    "Gouketuji",
    "Linda",
    "Great Battle",
    "Tilt",
    "Nazo",
    "Clay Fighter"
)

foreach ($term in $searchTerms) {
    Write-Host "=== Search: $term ==="
    $found = $gameMap.Keys | Where-Object { $_ -like "*$term*" } | Sort-Object
    foreach ($f in $found) {
        Write-Host "  $f -> $($gameMap[$f])"
    }
    if ($found.Count -eq 0) {
        Write-Host "  (no matches)"
    }
    Write-Host ""
}
