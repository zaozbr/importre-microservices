#Requires -Version 5.1
<#
    PSX CHD Renamer - Batch 1: Files with serial in filename
    Uses whitelist of known PSX serial prefixes to avoid false matches
#>

$ErrorActionPreference = 'Continue'
$dir = 'D:\roms\library\roms\psx'
$logFile = 'F:\importre\logs\rename.log'
$errorLog = 'F:\importre\logs\rename_errors.log'
$dryRun = $false  # ACTUAL RENAME MODE

# Known PSX serial prefixes
$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE'
$serialRegex = "($serialPrefixes)-(\d{3,6})"

# Ensure log directory
$logDir = Split-Path $logFile -Parent
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
if (!(Test-Path $logFile)) { "Timestamp|OldName|NewName|Status" | Out-File -FilePath $logFile -Encoding UTF8 }
if (!(Test-Path $errorLog)) { "Timestamp|FileName|Error" | Out-File -FilePath $errorLog -Encoding UTF8 }

function Write-Log {
    param([string]$msg)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "$timestamp|$msg"
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

function Write-ErrLog {
    param([string]$file, [string]$err)
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $errorLog -Value "$timestamp|$file|$err" -Encoding UTF8
}

function Extract-Serial {
    param([string]$filename)
    
    $baseName = $filename -replace '\.bin\.chd$', '' -replace '\.chd$', ''
    
    # Try at end of name: ...-SLPS-01311 or ...-SLPS-01311_2 or ...-SLES-01266.1
    $m = [regex]::Match($baseName, "$serialRegex(?:_(\d+))?(?:\.(\d+))?$")
    if ($m.Success) {
        $serial = "$($m.Groups[1].Value)-$($m.Groups[2].Value)"
        $disc = $null
        if ($m.Groups[3].Value) { $disc = $m.Groups[3].Value }
        elseif ($m.Groups[4].Value) { $disc = $m.Groups[4].Value }
        return @{ Serial = $serial; Disc = $disc }
    }
    
    # Try anywhere in name (for bracketed/parens cases)
    $m = [regex]::Match($baseName, $serialRegex)
    if ($m.Success) {
        $serial = "$($m.Groups[1].Value)-$($m.Groups[2].Value)"
        return @{ Serial = $serial; Disc = $null }
    }
    
    # Try disc format: SLPS_014.97
    $m = [regex]::Match($baseName, "($serialPrefixes)_(\d{3})\.(\d{2})")
    if ($m.Success) {
        $serial = "$($m.Groups[1].Value)-$($m.Groups[2].Value)$($m.Groups[3].Value)"
        return @{ Serial = $serial; Disc = $null }
    }
    
    # Try format: SLPS_01497
    $m = [regex]::Match($baseName, "($serialPrefixes)_(\d{3,6})")
    if ($m.Success) {
        $serial = "$($m.Groups[1].Value)-$($m.Groups[2].Value)"
        return @{ Serial = $serial; Disc = $null }
    }
    
    return $null
}

function Extract-DiscNumber {
    param([string]$filename)
    
    # Disc1, Disc-1, Disc 1
    $m = [regex]::Match($filename, '(?i)disc[\s-]*([0-9])\b')
    if ($m.Success) { return $m.Groups[1].Value }
    
    # [Disc1of2]
    $m = [regex]::Match($filename, '(?i)disc([0-9])\s*of')
    if ($m.Success) { return $m.Groups[1].Value }
    
    return $null
}

function Clean-GameName {
    param([string]$rawName, [string]$serial)
    
    $name = $rawName
    
    # Remove extensions
    $name = $name -replace '\.bin\.chd$', ''
    $name = $name -replace '\.chd$', ''
    
    # If name starts with serial, game name might be in parens after it
    $serialEscaped = [regex]::Escape($serial)
    $m = [regex]::Match($name, "^$serialEscaped\s*\(([^)]+)\)")
    if ($m.Success) {
        $gameName = $m.Groups[1].Value
        $gameName = $gameName -replace '/', '-'
        $gameName = $gameName -replace ':', '-'
        $gameName = $gameName -replace '\s+', '-'
        $gameName = $gameName -replace "[^A-Za-z0-9\-'']", ''
        $gameName = $gameName -replace '-{2,}', '-'
        $gameName = $gameName.Trim(' -')
        if ($gameName.Length -ge 1) { return $gameName }
    }
    
    # Remove the specific serial from the name
    $name = [regex]::Replace($name, $serialEscaped, '')
    
    # Remove any other serial patterns (with known prefixes)
    $name = [regex]::Replace($name, "($serialPrefixes)-\d{3,6}(_\d+)?(\.\d+)?", '')
    $name = [regex]::Replace($name, "($serialPrefixes)_\d{3}\.\d{2}", '')
    $name = [regex]::Replace($name, "($serialPrefixes)_\d{3,6}", '')
    
    # Remove parens content
    $name = [regex]::Replace($name, '\([^)]*\)', '')
    
    # Remove bracketed content
    $name = [regex]::Replace($name, '\[[^\]]*\]', '')
    
    # Remove disc/track indicators
    $name = [regex]::Replace($name, '(?i)-\s*disc[\s-]*\d+', '')
    $name = [regex]::Replace($name, '(?i)\bdisc[\s-]*\d+', '')
    $name = [regex]::Replace($name, '(?i)-\s*track[\s-]*\d+', '')
    $name = [regex]::Replace($name, '(?i)\btrack[\s-]*\d+', '')
    
    # Remove "bin" leftover
    $name = [regex]::Replace($name, '(?i)\bbin\b', '')
    
    # Remove "chd" leftover (standalone word)
    $name = [regex]::Replace($name, '(?i)\bchd\b', '')
    
    # Replace special characters
    $name = $name -replace '/', '-'
    $name = $name -replace ':', '-'
    $name = $name -replace '\?', ''
    $name = $name -replace '!', ''
    $name = $name -replace '\+', 'and'
    $name = $name -replace '&', 'and'
    
    # Replace spaces with hyphens
    $name = $name -replace '\s+', '-'
    
    # Remove non-allowed characters
    $name = $name -replace "[^A-Za-z0-9\-'']", ''
    
    # Clean up hyphens
    $name = $name -replace '-{2,}', '-'
    $name = $name.Trim(' -')
    $name = $name -replace '-{2,}', '-'
    $name = $name.Trim(' -')
    
    return $name
}

function To-TitleCase {
    param([string]$name)
    
    $words = $name -split '-'
    $result = @()
    $romanPatterns = @('III','II','IV','VI','VII','VIII','IX','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX')
    
    foreach ($word in $words) {
        if ($word -match '^\d+$') {
            # Pure number - keep as is
            $result += $word
        }
        elseif ($romanPatterns -contains $word.ToUpper()) {
            # Roman numerals - uppercase
            $result += $word.ToUpper()
        }
        elseif ($word.Length -le 1) {
            $result += $word.ToUpper()
        }
        elseif ($word -cmatch '^[A-Z0-9]+$') {
            # All uppercase (case-sensitive) - keep as-is (acronyms like 3D, CD, DVD)
            $result += $word
        }
        elseif ($word -cmatch '^\d') {
            # Word starts with digit - capitalize first LETTER, lowercase rest
            # e.g., 2xtreme -> 2Xtreme, 3d -> 3D, 3x3 -> 3X3
            $letterMatch = [regex]::Match($word, '[a-zA-Z]')
            if ($letterMatch.Success) {
                $pos = $letterMatch.Index
                $result += $word.Substring(0, $pos) + $word.Substring($pos, 1).ToUpper() + $word.Substring($pos + 1).ToLower()
            } else {
                $result += $word
            }
        }
        else {
            # Standard Title Case: capitalize first letter, lowercase rest
            $result += $word.Substring(0,1).ToUpper() + $word.Substring(1).ToLower()
        }
    }
    
    return ($result -join '-')
}

# Main processing
$files = Get-ChildItem $dir -Filter '*.chd'
$goodPattern = "^[A-Za-z0-9].*($serialPrefixes)-\d{3,6}(-Disc\d+)?(\(\d+\))?\.chd$"
$badChars = '[\(\)\[\]]'

# Get ALL files with a valid serial (even if they look OK, they may need Title Case)
$toRename = @($files | Where-Object { 
    $_.Name -imatch $serialRegex 
})

Write-Output "Files to process (with valid serial): $($toRename.Count)"

$renamed = 0
$skipped = 0
$errors = 0
$batchNum = 0
$newNames = @{}
$existingNames = @{}
Get-ChildItem $dir -Filter '*.chd' | ForEach-Object { $existingNames[$_.Name.ToLower()] = $true }

foreach ($file in $toRename) {
    $oldName = $file.Name
    $batchNum++
    
    $serialInfo = Extract-Serial $oldName
    if (!$serialInfo) {
        Write-ErrLog $oldName "Could not extract serial"
        $errors++
        continue
    }
    
    $serial = $serialInfo.Serial
    $disc = $serialInfo.Disc
    if (!$disc) { $disc = Extract-DiscNumber $oldName }
    
    $cleanName = Clean-GameName $oldName $serial
    
    if (!$cleanName -or $cleanName.Length -lt 1 -or $cleanName -match '^\d+$') {
        Write-ErrLog $oldName "No valid game name (empty or numeric only)"
        $errors++
        continue
    }
    
    $cleanName = To-TitleCase $cleanName
    
    $newName = "$cleanName-$serial"
    if ($disc) { $newName += "-Disc$disc" }
    $newName += ".chd"
    
    if ($newName -ceq $oldName) {
        $skipped++
        continue
    }
    
    # Handle duplicates
    $newNameLower = $newName.ToLower()
    if ($newNames.ContainsKey($newNameLower) -or ($existingNames.ContainsKey($newNameLower) -and $newName -cne $oldName)) {
        $counter = 1
        $baseName = $newName -replace '\.chd$', ''
        while ($true) {
            $testName = "${baseName}($counter).chd"
            $testNameLower = $testName.ToLower()
            if (!$newNames.ContainsKey($testNameLower) -and !($existingNames.ContainsKey($testNameLower) -and $testName -cne $oldName)) {
                $newName = $testName
                $newNameLower = $testNameLower
                break
            }
            $counter++
        }
    }
    
    $newNames[$newNameLower] = $true
    
    if ($dryRun) {
        Write-Output "[DRY] $oldName -> $newName"
    } else {
        try {
            Rename-Item -LiteralPath $file.FullName -NewName $newName -ErrorAction Stop
            Write-Log "$oldName|$newName|OK"
            $renamed++
        } catch {
            Write-ErrLog $oldName $_.Exception.Message
            $errors++
        }
    }
    
    if ($batchNum % 100 -eq 0) {
        Write-Output "--- Progress: $batchNum / $($toRename.Count) (Renamed: $renamed, Skipped: $skipped, Errors: $errors) ---"
    }
}

Write-Output ""
Write-Output "=== BATCH 1 COMPLETE ==="
Write-Output "Total processed: $batchNum"
Write-Output "Renamed: $renamed"
Write-Output "Skipped (already OK): $skipped"
Write-Output "Errors: $errors"
