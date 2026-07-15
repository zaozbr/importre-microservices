$datFile = "F:\importre\logs\psx_redump.dat"
$lines = Get-Content $datFile

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

# Search for NBA Power Dunkers
$found = $serialToName.GetEnumerator() | Where-Object { $_.Value -like "*NBA*Power*Dunk*" }
foreach ($f in $found) {
    Write-Host "  $($f.Value) -> $($f.Key)"
}
if ($found.Count -eq 0) {
    $found2 = $serialToName.GetEnumerator() | Where-Object { $_.Value -like "*Power Dunk*" }
    Write-Host "  Power Dunk search:"
    foreach ($f in $found2) {
        Write-Host "    $($f.Value) -> $($f.Key)"
    }
}

# Search for SLPS-09049
Write-Host ""
$found3 = $serialToName.GetEnumerator() | Where-Object { $_.Key -like "SLPS-0904*" }
foreach ($f in $found3) {
    Write-Host "  $($f.Key) -> $($f.Value)"
}
