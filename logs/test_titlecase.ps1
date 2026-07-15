# Test Title Case function
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
        else {
            $result += $word.Substring(0,1).ToUpper() + $word.Substring(1).ToLower()
        }
    }
    
    return ($result -join '-')
}

# Test cases
$tests = @(
    '0-kara-no-Mahjong-Mahjong-Youchien-Tamago-gumi',
    '007-Racing',
    '2xtreme',
    '3d-Baseball',
    '3x3-Eyes',
    'Crash-Bandicoot',
    'FINAL-FANTASY',
    'Metal-Gear-Solid',
    'IV',
    '3D',
    'the-legend-of-dragoon'
)

foreach ($test in $tests) {
    $result = To-TitleCase $test
    Write-Output "$test -> $result"
}
