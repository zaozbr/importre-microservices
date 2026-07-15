$datFile = "F:\importre\logs\psx_redump.dat"
$lines = Get-Content $datFile

$gameMap = @{}
$currentName = $null
$currentSerial = $null

foreach ($line in $lines) {
    $line = $line.Trim()
    
    # Match name line
    if ($line -match '^name\s+"(.+)"' -and $line -notmatch '^name "Sony') {
        $currentName = $matches[1]
    }
    
    # Match serial line (not inside rom)
    if ($line -match '^serial\s+"(.+)"' -and $currentName) {
        $currentSerial = $matches[1]
    }
    
    # Match closing paren of game block
    if ($line -eq ')' -and $currentName -and $currentSerial) {
        if (-not $gameMap.ContainsKey($currentName)) {
            $gameMap[$currentName] = $currentSerial
        }
        $currentName = $null
        $currentSerial = $null
    }
}

Write-Host "Parsed $($gameMap.Count) unique game-serial mappings"
Write-Host ""

# Show a few examples
Write-Host "=== SAMPLE MAPPINGS ==="
$gameMap.GetEnumerator() | Select-Object -First 10 | ForEach-Object {
    Write-Host "  $($_.Key) -> $($_.Value)"
}
Write-Host ""

# Save the mapping for later use
$gameMap | ConvertTo-Json | Out-File "F:\importre\logs\psx_serial_map.json" -Encoding UTF8

# Now match against our no-serial files
$genuineFile = "F:\importre\logs\genuine_no_serial.txt"
$spacesFile = "F:\importre\logs\spaces_no_serial.txt"
$games = Get-Content $genuineFile
$spacesGames = Get-Content $spacesFile

function Normalize-ForMatch($name) {
    $n = $name -replace '\.chd$', ''
    $n = $n -replace '-', ' '
    $n = $n -replace '_', ' '
    # Remove region tags
    $n = $n -replace '\s*\([^)]*\)', ''
    # Remove special chars
    $n = $n -replace "[#']", ''
    $n = $n -replace '\s+', ' '
    return $n.Trim().ToLower()
}

Write-Host "=== MATCHING GENUINE GAMES ==="
$matched = @()
$unmatched = @()

foreach ($game in $games) {
    $normName = Normalize-ForMatch $game
    $found = $false
    $foundSerial = $null
    $foundKey = $null
    
    # Try exact normalized match
    foreach ($key in $gameMap.Keys) {
        $normKey = Normalize-ForMatch $key
        if ($normKey -eq $normName) {
            $found = $true
            $foundSerial = $gameMap[$key]
            $foundKey = $key
            break
        }
    }
    
    # Try "contains" match if no exact match
    if (-not $found) {
        # Get first 2 words of our game name
        $words = $normName -split ' '
        $searchTerm = if ($words.Count -ge 2) { ($words[0..1] -join ' ') } else { $normName }
        
        foreach ($key in $gameMap.Keys) {
            $normKey = Normalize-ForMatch $key
            if ($normKey.Contains($searchTerm) -or $searchTerm.Contains($normKey)) {
                # Additional check: last word should match too
                $keyWords = $normKey -split ' '
                if ($keyWords.Count -gt 0 -and $words.Count -gt 0) {
                    if ($keyWords[$keyWords.Count-1] -eq $words[$words.Count-1] -or 
                        $keyWords[0] -eq $words[0]) {
                        $found = $true
                        $foundSerial = $gameMap[$key]
                        $foundKey = $key
                        break
                    }
                }
            }
        }
    }
    
    if ($found) {
        Write-Host "  MATCH: $game -> $foundSerial ($foundKey)"
        $matched += [PSCustomObject]@{File=$game; Serial=$foundSerial; DatName=$foundKey}
    } else {
        $unmatched += $game
    }
}

Write-Host ""
Write-Host "Matched: $($matched.Count) / $($games.Count)"
Write-Host "Unmatched: $($unmatched.Count)"
Write-Host ""

if ($unmatched.Count -gt 0) {
    Write-Host "=== UNMATCHED GENUINE ==="
    $unmatched | ForEach-Object { Write-Host "  $_" }
    Write-Host ""
}

Write-Host "=== MATCHING SPACES/PARENS GAMES ==="
$matchedSpaces = @()
$unmatchedSpaces = @()

foreach ($game in $spacesGames) {
    $normName = Normalize-ForMatch $game
    $found = $false
    $foundSerial = $null
    $foundKey = $null
    
    foreach ($key in $gameMap.Keys) {
        $normKey = Normalize-ForMatch $key
        if ($normKey -eq $normName) {
            $found = $true
            $foundSerial = $gameMap[$key]
            $foundKey = $key
            break
        }
    }
    
    if (-not $found) {
        $words = $normName -split ' '
        $searchTerm = if ($words.Count -ge 2) { ($words[0..1] -join ' ') } else { $normName }
        
        foreach ($key in $gameMap.Keys) {
            $normKey = Normalize-ForMatch $key
            if ($normKey.Contains($searchTerm) -or $searchTerm.Contains($normKey)) {
                $keyWords = $normKey -split ' '
                if ($keyWords.Count -gt 0 -and $words.Count -gt 0) {
                    if ($keyWords[$keyWords.Count-1] -eq $words[$words.Count-1] -or 
                        $keyWords[0] -eq $words[0]) {
                        $found = $true
                        $foundSerial = $gameMap[$key]
                        $foundKey = $key
                        break
                    }
                }
            }
        }
    }
    
    if ($found) {
        Write-Host "  MATCH: $game -> $foundSerial ($foundKey)"
        $matchedSpaces += [PSCustomObject]@{File=$game; Serial=$foundSerial; DatName=$foundKey}
    } else {
        $unmatchedSpaces += $game
    }
}

Write-Host ""
Write-Host "Matched: $($matchedSpaces.Count) / $($spacesGames.Count)"
Write-Host "Unmatched: $($unmatchedSpaces.Count)"
Write-Host ""

if ($unmatchedSpaces.Count -gt 0) {
    Write-Host "=== UNMATCHED SPACES ==="
    $unmatchedSpaces | ForEach-Object { Write-Host "  $_" }
}

# Save matched results
$allMatched = $matched + $matchedSpaces
$allMatched | ForEach-Object {
    "$($_.File)|$($_.Serial)|$($_.DatName)"
} | Out-File "F:\importre\logs\matched_serials.txt" -Encoding UTF8

Write-Host ""
Write-Host "Matched results saved to F:\importre\logs\matched_serials.txt"
