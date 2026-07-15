#Requires -Version 5.1
<#
    PSX CHD Renamer - Batch 2: Extract serial from CHD binary
    For files without serial in filename, extract .bin and search for serial
#>

$ErrorActionPreference = 'Continue'
$dir = 'D:\roms\library\roms\psx'
$logFile = 'F:\importre\logs\rename.log'
$errorLog = 'F:\importre\logs\rename_errors.log'
$chdman = 'D:\roms\library\roms\psx\chdman.exe'
$tempDir = 'C:\temp_chd'
$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE'

# Ensure temp dir
if (!(Test-Path $tempDir)) { New-Item -ItemType Directory -Path $tempDir -Force | Out-Null }

# Get files without serial
$files = Get-ChildItem $dir -Filter '*.chd'
$serialRegex = "($serialPrefixes)-\d{3,6}"
$noSerial = @($files | Where-Object { $_.Name -inotmatch $serialRegex })

Write-Output "Files without serial: $($noSerial.Count)"

# Function to extract serial from binary
function Get-SerialFromBin {
    param([string]$chdFile)
    
    $tempBin = Join-Path $tempDir 'extract_temp.bin'
    $tempCue = Join-Path $tempDir 'extract_temp.cue'
    
    # Clean up any existing temp files
    Remove-Item $tempBin -ErrorAction SilentlyContinue
    Remove-Item $tempCue -ErrorAction SilentlyContinue
    
    # Extract
    $output = & $chdman extractcd -i $chdFile -o $tempCue -ob $tempBin -f 2>&1
    
    if (!(Test-Path $tempBin)) {
        return $null
    }
    
    # Read first 50 sectors (2352 bytes each for MODE2_RAW)
    $sectorSize = 2352
    $numSectors = 50
    $bytesToRead = $sectorSize * $numSectors
    
    try {
        $fs = [System.IO.File]::OpenRead($tempBin)
        $buffer = New-Object byte[] $bytesToRead
        $read = $fs.Read($buffer, 0, $bytesToRead)
        $fs.Close()
    } catch {
        Remove-Item $tempBin -ErrorAction SilentlyContinue
        Remove-Item $tempCue -ErrorAction SilentlyContinue
        return $null
    }
    
    $text = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $read)
    
    # Search for PSX serial patterns: SLUS_012.34, SLES_004.77, etc.
    $matches = [regex]::Matches($text, "($serialPrefixes)[_-](\d{3})[\._-](\d{2})")
    foreach ($m in $matches) {
        $serial = "$($m.Groups[1].Value)-$($m.Groups[2].Value)$($m.Groups[3].Value)"
        # Clean up temp
        Remove-Item $tempBin -ErrorAction SilentlyContinue
        Remove-Item $tempCue -ErrorAction SilentlyContinue
        return $serial
    }
    
    # Also try 4-5 digit format: SLPS_01497
    $matches = [regex]::Matches($text, "($serialPrefixes)[_-](\d{4,5})")
    foreach ($m in $matches) {
        $serial = "$($m.Groups[1].Value)-$($m.Groups[2].Value)"
        Remove-Item $tempBin -ErrorAction SilentlyContinue
        Remove-Item $tempCue -ErrorAction SilentlyContinue
        return $serial
    }
    
    # Clean up
    Remove-Item $tempBin -ErrorAction SilentlyContinue
    Remove-Item $tempCue -ErrorAction SilentlyContinue
    return $null
}

# Function to clean game name
function Clean-GameName {
    param([string]$rawName)
    
    $name = $rawName -replace '\.bin\.chd$', '' -replace '\.chd$', ''
    
    # Remove parens content
    $name = [regex]::Replace($name, '\([^)]*\)', '')
    # Remove brackets
    $name = [regex]::Replace($name, '\[[^\]]*\]', '')
    # Remove disc/track
    $name = [regex]::Replace($name, '(?i)-\s*disc[\s-]*\d+', '')
    $name = [regex]::Replace($name, '(?i)\bdisc[\s-]*\d+', '')
    $name = [regex]::Replace($name, '(?i)-\s*track[\s-]*\d+', '')
    $name = [regex]::Replace($name, '(?i)\btrack[\s-]*\d+', '')
    # Remove bin/chd
    $name = [regex]::Replace($name, '(?i)\bbin\b', '')
    $name = [regex]::Replace($name, '(?i)\bchd\b', '')
    # Special chars
    $name = $name -replace '/', '-' -replace ':', '-' -replace '\?', '' -replace '!', ''
    $name = $name -replace '\+', 'and' -replace '&', 'and'
    # Spaces to hyphens
    $name = $name -replace '\s+', '-'
    # Remove non-allowed
    $name = $name -replace "[^A-Za-z0-9\-'']", ''
    # Clean hyphens
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
        if ($word -match '^\d+$') { $result += $word }
        elseif ($romanPatterns -contains $word.ToUpper()) { $result += $word.ToUpper() }
        elseif ($word.Length -le 1) { $result += $word.ToUpper() }
        elseif ($word -cmatch '^[A-Z0-9]+$') { $result += $word }
        elseif ($word -cmatch '^\d') {
            $letterMatch = [regex]::Match($word, '[a-zA-Z]')
            if ($letterMatch.Success) {
                $pos = $letterMatch.Index
                $result += $word.Substring(0, $pos) + $word.Substring($pos, 1).ToUpper() + $word.Substring($pos + 1).ToLower()
            } else { $result += $word }
        }
        else { $result += $word.Substring(0,1).ToUpper() + $word.Substring(1).ToLower() }
    }
    return ($result -join '-')
}

# Process files in batches
$batchSize = 50
$batchNum = 0
$renamed = 0
$noSerialFound = 0
$errors = 0
$serialsFound = @{}

foreach ($file in $noSerial) {
    $batchNum++
    $oldName = $file.Name
    
    Write-Output "[$batchNum/$($noSerial.Count)] Processing: $oldName"
    
    # Extract serial from binary
    $serial = Get-SerialFromBin $file.FullName
    
    if (!$serial) {
        Write-Output "  No serial found in binary"
        $noSerialFound++
        continue
    }
    
    Write-Output "  Found serial: $serial"
    
    # Clean game name
    $cleanName = Clean-GameName $oldName
    if (!$cleanName -or $cleanName.Length -lt 1) {
        Write-Output "  No game name could be extracted"
        $noSerialFound++
        continue
    }
    
    # Apply Title Case
    $cleanName = To-TitleCase $cleanName
    
    # Build new name
    $newName = "$cleanName-$serial.chd"
    
    # Handle duplicates
    $newPath = Join-Path $dir $newName
    if (Test-Path $newPath) {
        $counter = 1
        $base = $newName -replace '\.chd$', ''
        while (Test-Path (Join-Path $dir "${base}($counter).chd")) { $counter++ }
        $newName = "${base}($counter).chd"
    }
    
    Write-Output "  -> $newName"
    
    try {
        Rename-Item -LiteralPath $file.FullName -NewName $newName -ErrorAction Stop
        $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        Add-Content -Path $logFile -Value "$timestamp|$oldName|$newName|CHDMAN-SERIAL"
        $renamed++
    } catch {
        Write-Output "  ERROR: $_"
        $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        Add-Content -Path $errorLog -Value "$timestamp|$oldName|$_.Exception.Message"
        $errors++
    }
    
    # Progress
    if ($batchNum % 50 -eq 0) {
        Write-Output "--- Progress: $batchNum / $($noSerial.Count) (Renamed: $renamed, NoSerial: $noSerialFound, Errors: $errors) ---"
    }
}

Write-Output ""
Write-Output "=== BATCH 2 (CHDMAN) COMPLETE ==="
Write-Output "Total processed: $batchNum"
Write-Output "Renamed: $renamed"
Write-Output "No serial found: $noSerialFound"
Write-Output "Errors: $errors"

# Clean up temp dir
Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
