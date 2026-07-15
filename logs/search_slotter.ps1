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

# Search for Slotter Mania
$found = $gameMap.Keys | Where-Object { $_ -like "*Slotter*" } | Sort-Object
foreach ($f in $found) {
    Write-Host "  $f -> $($gameMap[$f])"
}
if ($found.Count -eq 0) { Write-Host "  (no matches for Slotter)" }

Write-Host ""
# Search for Hana Hana
$found2 = $gameMap.Keys | Where-Object { $_ -like "*Hana*Hana*" } | Sort-Object
foreach ($f in $found2) {
    Write-Host "  $f -> $($gameMap[$f])"
}
if ($found2.Count -eq 0) { Write-Host "  (no matches for Hana Hana)" }

Write-Host ""
# Search for SLPS-033
$found3 = $gameMap.GetEnumerator() | Where-Object { $_.Value -like "SLPS-033*" } | Sort-Object Value
foreach ($f in $found3) {
    Write-Host "  $($f.Key) -> $($f.Value)"
}
