#Requires -Version 5.1
<#
    Pre-processing: Decode URL-encoded filenames
    Files like "Action20bass2028japan29-SLPS-00094.chd" 
    where 20=space, 28=(, 29=)
    Only applies to game name part, NOT the serial
#>

$ErrorActionPreference = 'Continue'
$dir = 'D:\roms\library\roms\psx'
$logFile = 'F:\importre\logs\rename.log'

$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE'

# Find files with URL-encoded patterns (20 between letters, 28/29 in name)
$files = Get-ChildItem $dir -Filter '*.chd'

# Detect URL-encoded files: they have patterns like "word20word" or "28japan29"
$encodedFiles = @($files | Where-Object {
    $_.Name -match '[a-zA-Z]20[a-zA-Z]' -or 
    $_.Name -match '[a-zA-Z]20\d' -or
    $_.Name -match '\d20[a-zA-Z]' -or
    $_.Name -match '28[a-zA-Z]' -or
    $_.Name -match '[a-zA-Z]29[-.]'
})

Write-Output "URL-encoded files found: $($encodedFiles.Count)"

$renamed = 0
foreach ($file in $encodedFiles) {
    $oldName = $file.Name
    
    # Split into game name and serial+extension
    $serialMatch = [regex]::Match($oldName, "($serialPrefixes)-\d{3,6}")
    if (!$serialMatch.Success) {
        # No serial found, skip - will be handled by chdman batch
        continue
    }
    
    $serialPart = $oldName.Substring($serialMatch.Index)
    $gamePart = $oldName.Substring(0, $serialMatch.Index)
    
    # Decode URL encoding in game part only
    # 20 = space, 28 = (, 29 = )
    $decoded = $gamePart
    $decoded = [regex]::Replace($decoded, '20', ' ')
    $decoded = [regex]::Replace($decoded, '28', '(')
    $decoded = [regex]::Replace($decoded, '29', ')')
    
    # Clean up: replace spaces with hyphens, remove parens content
    $decoded = $decoded -replace '\s+', '-'
    $decoded = [regex]::Replace($decoded, '\([^)]*\)', '')
    $decoded = $decoded -replace "[^A-Za-z0-9\-'']", ''
    $decoded = $decoded -replace '-{2,}', '-'
    $decoded = $decoded.Trim(' -')
    
    if (!$decoded -or $decoded.Length -lt 1) { continue }
    
    # Build new name
    $newName = "$decoded-$serialPart"
    
    if ($newName -eq $oldName) { continue }
    
    # Check for duplicates
    $newPath = Join-Path $dir $newName
    if (Test-Path $newPath) {
        $counter = 1
        $base = $newName -replace '\.chd$', ''
        while (Test-Path (Join-Path $dir "${base}($counter).chd")) { $counter++ }
        $newName = "${base}($counter).chd"
    }
    
    Write-Output "[URL] $oldName -> $newName"
    try {
        Rename-Item -LiteralPath $file.FullName -NewName $newName -ErrorAction Stop
        $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        Add-Content -Path $logFile -Value "$timestamp|$oldName|$newName|URL-DECODE"
        $renamed++
    } catch {
        Write-Output "ERROR: $_"
    }
}

Write-Output "URL-decoded: $renamed files"
