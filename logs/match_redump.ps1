$datFile = "F:\importre\logs\psx_redump.dat"
$content = Get-Content $datFile -Raw

# Parse the DAT file - extract game name and serial
# Format: game ( name "..." ... serial "..." ... )
$games = @()
$gameBlocks = [regex]::Matches($content, 'game\s*\([^)]*(?:\([^)]*\)[^)]*)*\)', [System.Text.RegularExpressions.RegexOptions]::Singleline)

Write-Host "Parsing $($gameBlocks.Count) game entries..."

$gameMap = @{}

foreach ($block in $gameBlocks) {
    $blockText = $block.Value
    $nameMatch = [regex]::Match($blockText, 'name\s+"([^"]+)"')
    $serialMatch = [regex]::Match($blockText, 'serial\s+"([^"]+)"')
    
    if ($nameMatch.Success -and $serialMatch.Success) {
        $name = $nameMatch.Groups[1].Value
        $serial = $serialMatch.Groups[1].Value
        if (-not $gameMap.ContainsKey($name)) {
            $gameMap[$name] = $serial
        }
    }
}

Write-Host "Parsed $($gameMap.Count) unique game-serial mappings"
Write-Host ""

# Now read the genuine no-serial files
$genuineFile = "F:\importre\logs\genuine_no_serial.txt"
$spacesFile = "F:\importre\logs\spaces_no_serial.txt"
$games = Get-Content $genuineFile
$spacesGames = Get-Content $spacesFile

# Function to normalize a game name for matching
function Normalize-Name($name) {
    # Remove .chd extension
    $n = $name -replace '\.chd$', ''
    # Replace dashes with spaces
    $n = $n -replace '-', ' '
    # Remove extra spaces
    $n = $n -replace '\s+', ' '
    return $n.Trim()
}

# Function to normalize DAT name for matching
function Normalize-DatName($name) {
    # Remove region tags like (Japan), (Europe), (USA)
    $n = $name -replace '\s*\([^)]*\)\s*', ' '
    # Remove language tags like (En,Ja)
    $n = $n -replace '\s*\([^)]*\)\s*', ' '
    # Remove disc tags
    $n = $n -replace '\s*\(Disc\s*\d+\)\s*', ' '
    # Remove extra spaces
    $n = $n -replace '\s+', ' '
    return $n.Trim()
}

Write-Host "=== MATCHING GENUINE GAMES ==="
$matched = 0
$unmatched = @()

foreach ($game in $games) {
    $normName = Normalize-Name $game
    $found = $false
    
    # Try exact match first (case insensitive)
    foreach ($key in $gameMap.Keys) {
        $normKey = Normalize-DatName $key
        if ($normKey -ieq $normName) {
            Write-Host "  MATCH: $game -> $($gameMap[$key])"
            $found = $true
            $matched++
            break
        }
    }
    
    if (-not $found) {
        # Try partial match - first few words
        $words = $normName -split ' '
        if ($words.Count -ge 2) {
            $firstWords = ($words[0..1] -join ' ')
            foreach ($key in $gameMap.Keys) {
                $normKey = Normalize-DatName $key
                if ($normKey -like "*$firstWords*" -and $normKey -like "*$($words[$words.Count-1])*") {
                    Write-Host "  PARTIAL: $game -> $($gameMap[$key]) (key: $key)"
                    $found = $true
                    $matched++
                    break
                }
            }
        }
    }
    
    if (-not $found) {
        $unmatched += $game
    }
}

Write-Host ""
Write-Host "Matched: $matched / $($games.Count)"
Write-Host "Unmatched: $($unmatched.Count)"
Write-Host ""

Write-Host "=== UNMATCHED GAMES ==="
$unmatched | ForEach-Object { Write-Host "  $_" }
Write-Host ""

Write-Host "=== MATCHING SPACES/PARENS GAMES ==="
$matchedSpaces = 0
$unmatchedSpaces = @()

foreach ($game in $spacesGames) {
    $normName = Normalize-Name $game
    $found = $false
    
    foreach ($key in $gameMap.Keys) {
        $normKey = Normalize-DatName $key
        if ($normKey -ieq $normName) {
            Write-Host "  MATCH: $game -> $($gameMap[$key])"
            $found = $true
            $matchedSpaces++
            break
        }
    }
    
    if (-not $found) {
        $words = $normName -split ' '
        if ($words.Count -ge 2) {
            $firstWords = ($words[0..1] -join ' ')
            foreach ($key in $gameMap.Keys) {
                $normKey = Normalize-DatName $key
                if ($normKey -like "*$firstWords*" -and ($normKey -like "*$($words[$words.Count-1])*")) {
                    Write-Host "  PARTIAL: $game -> $($gameMap[$key]) (key: $key)"
                    $found = $true
                    $matchedSpaces++
                    break
                }
            }
        }
    }
    
    if (-not $found) {
        $unmatchedSpaces += $game
    }
}

Write-Host ""
Write-Host "Matched: $matchedSpaces / $($spacesGames.Count)"
Write-Host "Unmatched: $($unmatchedSpaces.Count)"
Write-Host ""

Write-Host "=== UNMATCHED SPACES GAMES ==="
$unmatchedSpaces | ForEach-Object { Write-Host "  $_" }
