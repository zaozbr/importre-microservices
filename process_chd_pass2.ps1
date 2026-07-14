# PSX to CHD - Pass 2: Process remaining archives and loose files
$ErrorActionPreference = "Continue"
$psxDir = "D:\roms\library\roms\psx"
$tempDir = "F:\importre\temp_extract"
$duplicadosDir = "D:\roms\duplicados"
$failedDir = "D:\roms\duplicados\failed"
$logFile = "F:\importre\logs\chd_batch.log"
$chdman = "D:\roms\library\roms\psx\chdman.exe"
$sevenZip = "C:\Program Files\7-Zip\7z.exe"

function Log-Message {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -ErrorAction SilentlyContinue
}

function Clean-TempDir {
    if (Test-Path $tempDir) {
        Get-ChildItem $tempDir -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Convert-ToCHD {
    param([string]$inputFile, [string]$outputChd)
    try {
        Log-Message "Converting: $inputFile -> $outputChd"
        $errFile = Join-Path $tempDir "chdman_err.txt"
        $proc = Start-Process -FilePath $chdman -ArgumentList "createcd", "-i", "`"$inputFile`"", "-o", "`"$outputChd`"", "-f" -NoNewWindow -Wait -PassThru -RedirectStandardError $errFile
        # Use -LiteralPath to handle square brackets in filenames
        if ($proc.ExitCode -eq 0 -and (Test-Path -LiteralPath $outputChd)) {
            Log-Message "SUCCESS: Created $outputChd"
            return $true
        } else {
            $err = ""
            if (Test-Path -LiteralPath $errFile) { $err = Get-Content -LiteralPath $errFile -Raw }
            Log-Message "FAILED: Conversion failed for $inputFile. Exit: $($proc.ExitCode). Error: $err"
            if (Test-Path -LiteralPath $outputChd) { Remove-Item -LiteralPath $outputChd -Force -ErrorAction SilentlyContinue }
            return $false
        }
    } catch {
        Log-Message "FAILED: Exception converting $inputFile - $($_.Exception.Message)"
        return $false
    }
}

function Create-TempCue {
    param([string]$binFile)
    $cueFile = [System.IO.Path]::ChangeExtension($binFile, ".cue")
    $binName = [System.IO.Path]::GetFileName($binFile)
    $cueContent = "FILE `"$binName`" BINARY`r`n  TRACK 01 MODE2/2352`r`n  INDEX 01 00:00:00`r`n"
    Set-Content -LiteralPath $cueFile -Value $cueContent -Encoding ASCII -NoNewline
    Log-Message "Created temp CUE: $cueFile"
    return $cueFile
}

function Get-CHDOutputName {
    param([string]$baseName)
    $sanitized = $baseName -replace '[^\w\-\.\(\)\[\]&]', '-'
    $sanitized = $sanitized -replace '-{2,}', '-'
    $sanitized = $sanitized.Trim('-')
    return Join-Path $psxDir "$sanitized.chd"
}

function Process-ExtractedFiles {
    param([string]$extractDir)
    
    $cueFiles = Get-ChildItem $extractDir -Filter *.cue -File -Recurse -ErrorAction SilentlyContinue
    $binFiles = Get-ChildItem $extractDir -Filter *.bin -File -Recurse -ErrorAction SilentlyContinue
    $isoFiles = Get-ChildItem $extractDir -Filter *.iso -File -Recurse -ErrorAction SilentlyContinue
    $imgFiles = Get-ChildItem $extractDir -Filter *.img -File -Recurse -ErrorAction SilentlyContinue
    $chdFiles = Get-ChildItem $extractDir -Filter *.chd -File -Recurse -ErrorAction SilentlyContinue
    
    $processed = $false
    
    # If already CHD in archive, just move it
    if ($chdFiles.Count -gt 0) {
        foreach ($chd in $chdFiles) {
            $destChd = Join-Path $psxDir $chd.Name
            if (Test-Path -LiteralPath $destChd) {
                Log-Message "CHD already exists at destination, skipping: $($chd.Name)"
            } else {
                Move-Item -LiteralPath $chd.FullName -Destination $psxDir -Force
                Log-Message "Moved existing CHD from archive: $($chd.Name)"
            }
            $processed = $true
        }
        return $processed
    }
    
    # Process .cue files
    foreach ($cue in $cueFiles) {
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($cue.Name)
        $outputChd = Get-CHDOutputName $baseName
        if (Test-Path -LiteralPath $outputChd) {
            Log-Message "CHD already exists: $outputChd - skipping"
            $processed = $true
            continue
        }
        $success = Convert-ToCHD $cue.FullName $outputChd
        if ($success) { $processed = $true }
    }
    
    # Process .bin files without .cue
    foreach ($bin in $binFiles) {
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($bin.Name)
        $cuePath = [System.IO.Path]::ChangeExtension($bin.FullName, ".cue")
        $outputChd = Get-CHDOutputName $baseName
        
        if (Test-Path -LiteralPath $outputChd) {
            Log-Message "CHD already exists: $outputChd - skipping bin"
            $processed = $true
            continue
        }
        
        $hasCue = $false
        foreach ($cue in $cueFiles) {
            if ([System.IO.Path]::GetFileNameWithoutExtension($cue.Name) -eq $baseName) {
                $hasCue = $true
                break
            }
        }
        if ($hasCue) { continue }
        
        $tempCue = Create-TempCue $bin.FullName
        $success = Convert-ToCHD $tempCue $outputChd
        if (Test-Path -LiteralPath $tempCue) { Remove-Item -LiteralPath $tempCue -Force -ErrorAction SilentlyContinue }
        if ($success) { $processed = $true }
    }
    
    # Process .iso files
    foreach ($iso in $isoFiles) {
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($iso.Name)
        $outputChd = Get-CHDOutputName $baseName
        if (Test-Path -LiteralPath $outputChd) {
            Log-Message "CHD already exists: $outputChd - skipping iso"
            $processed = $true
            continue
        }
        $success = Convert-ToCHD $iso.FullName $outputChd
        if ($success) { $processed = $true }
    }
    
    # Process .img files
    foreach ($img in $imgFiles) {
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($img.Name)
        $outputChd = Get-CHDOutputName $baseName
        if (Test-Path -LiteralPath $outputChd) {
            Log-Message "CHD already exists: $outputChd - skipping img"
            $processed = $true
            continue
        }
        $cuePath = [System.IO.Path]::ChangeExtension($img.FullName, ".cue")
        if (Test-Path -LiteralPath $cuePath) {
            $success = Convert-ToCHD $cuePath $outputChd
        } else {
            $success = Convert-ToCHD $img.FullName $outputChd
        }
        if ($success) { $processed = $true }
    }
    
    return $processed
}

Log-Message "========================================"
Log-Message "Starting PSX to CHD Pass 2"
Log-Message "========================================"

# 1. Process SLES-04067.bin (loose bin without cue)
$slesBin = "D:\roms\library\roms\psx\SLES-04067.bin"
if (Test-Path -LiteralPath $slesBin) {
    $outputChd = Get-CHDOutputName "SLES-04067"
    if (-not (Test-Path -LiteralPath $outputChd)) {
        $tempCue = Create-TempCue $slesBin
        $success = Convert-ToCHD $tempCue $outputChd
        if (Test-Path -LiteralPath $tempCue) { Remove-Item -LiteralPath $tempCue -Force -ErrorAction SilentlyContinue }
        if ($success) {
            Move-Item -LiteralPath $slesBin -Destination $duplicadosDir -Force
            Log-Message "Moved SLES-04067.bin to duplicados"
        } else {
            Move-Item -LiteralPath $slesBin -Destination $failedDir -Force
            Log-Message "Moved SLES-04067.bin to failed"
        }
    } else {
        Log-Message "SLES-04067 CHD already exists, moving bin to duplicados"
        Move-Item -LiteralPath $slesBin -Destination $duplicadosDir -Force
    }
}

# 2. Process remaining archives
$archives = Get-ChildItem $psxDir -Include *.7z,*.zip,*.rar -Recurse -ErrorAction SilentlyContinue | Where-Object { -not $_.PSIsContainer }
Log-Message "Pass 2: Found $($archives.Count) archive files to process"

foreach ($archive in $archives) {
    Log-Message "--- Processing archive: $($archive.FullName) ---"
    Clean-TempDir
    
    # Extract
    try {
        Log-Message "Extracting: $($archive.FullName)"
        $proc = Start-Process -FilePath $sevenZip -ArgumentList "x", "`"$($archive.FullName)`"", "-o`"$tempDir`"", "-y" -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$tempDir\7z_out.txt" -RedirectStandardError "$tempDir\7z_err.txt"
        if ($proc.ExitCode -ne 0) {
            $errContent = ""
            if (Test-Path -LiteralPath "$tempDir\7z_err.txt") { $errContent = Get-Content -LiteralPath "$tempDir\7z_err.txt" -Raw }
            Log-Message "ERROR: Extraction failed (exit $($proc.ExitCode)): $errContent"
            # Move corrupted archive to failed
            Move-Item -LiteralPath $archive.FullName -Destination $failedDir -Force -ErrorAction SilentlyContinue
            # Also try to move parent folder if empty
            $parentDir = $archive.DirectoryName
            if ($parentDir -ne $psxDir) {
                $remaining = Get-ChildItem $parentDir -Recurse -ErrorAction SilentlyContinue
                if ($remaining.Count -eq 0) {
                    Remove-Item $parentDir -Force -ErrorAction SilentlyContinue
                    Log-Message "Removed empty folder: $parentDir"
                }
            }
            continue
        }
        Log-Message "Extraction complete"
    } catch {
        Log-Message "ERROR: Failed to extract $($archive.FullName) - $($_.Exception.Message)"
        continue
    }
    
    # Process extracted files
    $processed = Process-ExtractedFiles $tempDir
    
    if ($processed) {
        # Move original archive to duplicados
        Move-Item -LiteralPath $archive.FullName -Destination $duplicadosDir -Force -ErrorAction SilentlyContinue
        Log-Message "Moved to duplicados: $($archive.FullName)"
        # Clean up parent folder if empty
        $parentDir = $archive.DirectoryName
        if ($parentDir -ne $psxDir) {
            $remaining = Get-ChildItem $parentDir -Recurse -ErrorAction SilentlyContinue
            if ($remaining.Count -eq 0) {
                Remove-Item $parentDir -Force -ErrorAction SilentlyContinue
                Log-Message "Removed empty folder: $parentDir"
            }
        }
    } else {
        Log-Message "WARNING: No files converted from $($archive.FullName)"
        # Check what was extracted
        $extracted = Get-ChildItem $tempDir -Recurse -ErrorAction SilentlyContinue
        if ($extracted.Count -eq 0) {
            Log-Message "Archive was empty or corrupted, moving to failed"
            Move-Item -LiteralPath $archive.FullName -Destination $failedDir -Force -ErrorAction SilentlyContinue
        } else {
            Log-Message "Extracted files: $($extracted.Name -join ', ')"
            Move-Item -LiteralPath $archive.FullName -Destination $duplicadosDir -Force -ErrorAction SilentlyContinue
        }
        $parentDir = $archive.DirectoryName
        if ($parentDir -ne $psxDir) {
            $remaining = Get-ChildItem $parentDir -Recurse -ErrorAction SilentlyContinue
            if ($remaining.Count -eq 0) {
                Remove-Item $parentDir -Force -ErrorAction SilentlyContinue
                Log-Message "Removed empty folder: $parentDir"
            }
        }
    }
    
    Clean-TempDir
}

# 3. Process any remaining loose .bin files
$looseBins = Get-ChildItem $psxDir -Filter *.bin -File -ErrorAction SilentlyContinue
foreach ($bin in $looseBins) {
    $baseName = $bin.BaseName
    $outputChd = Get-CHDOutputName $baseName
    $outputBase = [System.IO.Path]::GetFileNameWithoutExtension($outputChd)
    
    if (Test-Path -LiteralPath $outputChd) {
        Log-Message "CHD exists for: $baseName - moving bin to duplicados"
        Move-Item -LiteralPath $bin.FullName -Destination $duplicadosDir -Force -ErrorAction SilentlyContinue
        continue
    }
    
    $cuePath = Join-Path $psxDir "$baseName.cue"
    if (Test-Path -LiteralPath $cuePath) {
        $success = Convert-ToCHD $cuePath $outputChd
    } else {
        $tempCue = Create-TempCue $bin.FullName
        $success = Convert-ToCHD $tempCue $outputChd
        if (Test-Path -LiteralPath $tempCue) { Remove-Item -LiteralPath $tempCue -Force -ErrorAction SilentlyContinue }
    }
    
    if ($success) {
        Move-Item -LiteralPath $bin.FullName -Destination $duplicadosDir -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $cuePath) { Move-Item -LiteralPath $cuePath -Destination $duplicadosDir -Force -ErrorAction SilentlyContinue }
    } else {
        Move-Item -LiteralPath $bin.FullName -Destination $failedDir -Force -ErrorAction SilentlyContinue
    }
}

# 4. Process any remaining loose .cue files (move to duplicados if CHD exists)
$looseCues = Get-ChildItem $psxDir -Filter *.cue -File -ErrorAction SilentlyContinue
foreach ($cue in $looseCues) {
    $baseName = $cue.BaseName
    $outputChd = Get-CHDOutputName $baseName
    if (Test-Path -LiteralPath $outputChd) {
        Log-Message "CHD exists for: $baseName - moving cue to duplicados"
        Move-Item -LiteralPath $cue.FullName -Destination $duplicadosDir -Force -ErrorAction SilentlyContinue
    }
}

Clean-TempDir
Log-Message "========================================"
Log-Message "Pass 2 complete"
Log-Message "========================================"

# Final summary
$remainingArchives = (Get-ChildItem $psxDir -Include *.7z,*.zip,*.rar -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
$remainingBins = (Get-ChildItem $psxDir -Filter *.bin -File -ErrorAction SilentlyContinue | Measure-Object).Count
$remainingCues = (Get-ChildItem $psxDir -Filter *.cue -File -ErrorAction SilentlyContinue | Measure-Object).Count
$remainingIsos = (Get-ChildItem $psxDir -Filter *.iso -File -ErrorAction SilentlyContinue | Measure-Object).Count
$totalChds = (Get-ChildItem $psxDir -Filter *.chd -File -ErrorAction SilentlyContinue | Measure-Object).Count
Log-Message "REMAINING: Archives=$remainingArchives, BINs=$remainingBins, CUEs=$remainingCues, ISOs=$remainingIsos"
Log-Message "TOTAL CHD files: $totalChds"
