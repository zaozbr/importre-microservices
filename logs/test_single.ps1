$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE'
$serialRegex = "($serialPrefixes)-(\d{3,6})"
$test = '0-kara-no-Mahjong-Mahjong-Youchien-Tamago-gumi-SLPS-01311.chd'
Write-Output "Regex: $serialRegex"
Write-Output "Match: $($test -imatch $serialRegex)"

# Count how many files with serials exist
$files = Get-ChildItem 'D:\roms\library\roms\psx' -Filter '*.chd'
$withSerial = @($files | Where-Object { $_.Name -imatch $serialRegex })
Write-Output "Files with serial: $($withSerial.Count)"

# Check if 0-kara file would be renamed
$file = $files | Where-Object { $_.Name -eq $test }
if ($file) {
    Write-Output "File exists: $($file.Name)"
    # Simulate what batch1 would do
    $baseName = $test -replace '\.chd$', ''
    $serialMatch = [regex]::Match($baseName, $serialRegex)
    Write-Output "Serial found: $($serialMatch.Groups[0].Value)"
    
    # Clean name
    $serial = "$($serialMatch.Groups[1].Value)-$($serialMatch.Groups[2].Value)"
    $nameWithoutSerial = $baseName -replace [regex]::Escape($serial), ''
    Write-Output "Name without serial: '$nameWithoutSerial'"
    
    # Title case
    $words = $nameWithoutSerial -split '-'
    $result = @()
    foreach ($word in $words) {
        if ($word -match '^\d+$') { $result += $word }
        elseif ($word.Length -le 1) { $result += $word.ToUpper() }
        elseif ($word -match '^[A-Z0-9]+$') { $result += $word }
        else { $result += $word.Substring(0,1).ToUpper() + $word.Substring(1).ToLower() }
    }
    $cleanName = ($result -join '-') -replace '-{2,}', '-' -replace '^-|-$', ''
    Write-Output "Clean name: '$cleanName'"
    $newName = "$cleanName-$serial.chd"
    Write-Output "New name: '$newName'"
    Write-Output "Same as old: $($newName -eq $test)"
}
