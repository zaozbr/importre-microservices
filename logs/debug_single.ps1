# Debug script for single file
$dir = 'D:\roms\library\roms\psx'
$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE'
$serialRegex = "($serialPrefixes)-(\d{3,6})"

$testFile = '0-kara-no-Mahjong-Mahjong-Youchien-Tamago-gumi-SLPS-01311.chd'
$filePath = Join-Path $dir $testFile

Write-Output "File exists: $(Test-Path $filePath)"
Write-Output "Matches serial regex: $($testFile -imatch $serialRegex)"

# Extract serial
$baseName = $testFile -replace '\.chd$', ''
$m = [regex]::Match($baseName, $serialRegex)
Write-Output "Serial match: $($m.Success)"
if ($m.Success) {
    $serial = "$($m.Groups[1].Value)-$($m.Groups[2].Value)"
    Write-Output "Serial: $serial"
}

# Clean name - simulate Clean-GameName
$name = $baseName
$serialEscaped = [regex]::Escape($serial)
Write-Output "Serial escaped: $serialEscaped"
$name = [regex]::Replace($name, $serialEscaped, '')
Write-Output "After serial removal: '$name'"

# Remove other serials
$name = [regex]::Replace($name, "($serialPrefixes)-\d{3,6}(_\d+)?(\.\d+)?", '')
$name = [regex]::Replace($name, "\($serialPrefixes)_\d{3}\.\d{2}", '')
Write-Output "After other serial removal: '$name'"

# Remove parens/brackets
$name = [regex]::Replace($name, '\([^)]*\)', '')
$name = [regex]::Replace($name, '\[[^\]]*\]', '')
Write-Output "After parens/brackets: '$name'"

# Remove disc/track
$name = [regex]::Replace($name, '(?i)-\s*disc[\s-]*\d+', '')
$name = [regex]::Replace($name, '(?i)\bdisc[\s-]*\d+', '')
$name = [regex]::Replace($name, '(?i)-\s*track[\s-]*\d+', '')
$name = [regex]::Replace($name, '(?i)\btrack[\s-]*\d+', '')
Write-Output "After disc/track: '$name'"

# Remove bin/chd
$name = [regex]::Replace($name, '(?i)\bbin\b', '')
$name = [regex]::Replace($name, '(?i)\bchd\b', '')
Write-Output "After bin/chd: '$name'"

# Replace special chars
$name = $name -replace '/', '-'
$name = $name -replace ':', '-'
$name = $name -replace '\?', ''
$name = $name -replace '!', ''
$name = $name -replace '\+', 'and'
$name = $name -replace '&', 'and'
$name = $name -replace '\s+', '-'
$name = $name -replace "[^A-Za-z0-9\-'']", ''
$name = $name -replace '-{2,}', '-'
$name = $name.Trim(' -')
$name = $name -replace '-{2,}', '-'
$name = $name.Trim(' -')

Write-Output "Final clean name: '$name'"

# Title case
$words = $name -split '-'
$result = @()
$romanPatterns = @('III','II','IV','VI','VII','VIII','IX','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX')
foreach ($word in $words) {
    Write-Output "  Word: '$word' - digit:$($word -match '^\d+$') roman:$($romanPatterns -contains $word.ToUpper()) len1:$($word.Length -le 1) upper:$($word -cmatch '^[A-Z0-9]+$')"
    if ($word -match '^\d+$') { $result += $word }
    elseif ($romanPatterns -contains $word.ToUpper()) { $result += $word.ToUpper() }
    elseif ($word.Length -le 1) { $result += $word.ToUpper() }
    elseif ($word -cmatch '^[A-Z0-9]+$') { $result += $word }
    else { $result += $word.Substring(0,1).ToUpper() + $word.Substring(1).ToLower() }
}
$cleanName = ($result -join '-')
Write-Output "Title case result: '$cleanName'"

$newName = "$cleanName-$serial.chd"
Write-Output "New name: '$newName'"
Write-Output "Old name: '$testFile'"
Write-Output "Same: $($newName -eq $testFile)"
