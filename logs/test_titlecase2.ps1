# Test updated Title Case function
function To-TitleCase {
    param([string]$name)
    
    $words = $name -split '-'
    $result = @()
    $romanPatterns = @('III','II','IV','VI','VII','VIII','IX','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX')
    
    foreach ($word in $words) {
        if ($word -match '^\d+$') {
            $result += $word
        }
        elseif ($romanPatterns -contains $word.ToUpper()) {
            $result += $word.ToUpper()
        }
        elseif ($word.Length -le 1) {
            $result += $word.ToUpper()
        }
        elseif ($word -cmatch '^[A-Z0-9]+$') {
            $result += $word
        }
        elseif ($word -cmatch '^\d') {
            $letterMatch = [regex]::Match($word, '[a-zA-Z]')
            if ($letterMatch.Success) {
                $pos = $letterMatch.Index
                $result += $word.Substring(0, $pos) + $word.Substring($pos, 1).ToUpper() + $word.Substring($pos + 1).ToLower()
            } else {
                $result += $word
            }
        }
        else {
            $result += $word.Substring(0,1).ToUpper() + $word.Substring(1).ToLower()
        }
    }
    
    return ($result -join '-')
}

$tests = @(
    '0-kara-no-Mahjong',
    '2xtreme',
    '3d-Baseball',
    '3x3-Eyes',
    '3D',
    '007-Racing',
    'Crash-Bandicoot',
    'the-legend-of-dragoon',
    'FINAL-FANTASY-VII',
    '70s-Robot-Anime',
    'A-TRAIN',
    'I-max-Shogi-II',
    'J-League'
)

foreach ($test in $tests) {
    $result = To-TitleCase $test
    Write-Output "$test -> $result"
}
