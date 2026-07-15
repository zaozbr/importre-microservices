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

# Search for specific terms
$searchTerms = @(
    "Vandal Hearts",
    "3D Lemmings",
    "Aqua GT"
)

foreach ($term in $searchTerms) {
    Write-Host "=== Search: $term ==="
    $found = $gameMap.Keys | Where-Object { $_ -like "*$term*" } | Sort-Object
    foreach ($f in $found) {
        Write-Host "  $f -> $($gameMap[$f])"
    }
    Write-Host ""
}
