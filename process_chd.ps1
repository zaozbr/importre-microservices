$ErrorActionPreference = "Continue"
$logFile = "F:\importre\logs\chd_batch2.log"
$psxDir = "D:\roms\library\roms\psx"
$tempDir = "F:\importre\temp_extract"
$duplicadosDir = "D:\roms\duplicados"
$failedDir = "D:\roms\duplicados\failed"
$chdman = "D:\roms\library\roms\psx\chdman.exe"
$sevenZip = "C:\Program Files\7-Zip\7z.exe"

function Log {
    param([string]$msg)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Add-Content -LiteralPath $logFile -Value $line
    Write-Output $line
}

# Ensure dirs exist
foreach ($d in @($tempDir, $duplicadosDir, $failedDir, "F:\importre\logs")) {
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

function Move-Literal {
    param([string]$src, [string]$dest)
    if (Test-Path -LiteralPath $src) {
        Move-Item -LiteralPath $src -Destination $dest -Force
        Log "Movido: $src -> $dest"
    }
}

function Process-Compressed {
    param([string]$archivePath)

    $archiveName = [System.IO.Path]::GetFileName($archivePath)
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($archiveName)
    Log "=== Processando compactado: $archiveName ==="

    # Clean temp dir
    Get-ChildItem -LiteralPath $tempDir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    $extractFolder = Join-Path $tempDir $baseName
    if (-not (Test-Path -LiteralPath $extractFolder)) { New-Item -ItemType Directory -Path $extractFolder -Force | Out-Null }

    # Extract
    Log "Extraindo $archiveName para $extractFolder"
    & $sevenZip x $archivePath "-o$extractFolder" -y -aoa 2>&1 | ForEach-Object { Log $_ }
    if ($LASTEXITCODE -ne 0) {
        Log "ERRO: Falha ao extrair $archiveName (exit $LASTEXITCODE). Movendo para failed."
        Move-Literal $archivePath (Join-Path $failedDir $archiveName)
        return
    }

    # Find .cue files first
    $cueFiles = Get-ChildItem -LiteralPath $extractFolder -Filter *.cue -Recurse -ErrorAction SilentlyContinue
    # Find .bin/.img files
    $binFiles = Get-ChildItem -LiteralPath $extractFolder -Include *.bin,*.img -Recurse -ErrorAction SilentlyContinue
    # Find .iso files
    $isoFiles = Get-ChildItem -LiteralPath $extractFolder -Filter *.iso -Recurse -ErrorAction SilentlyContinue
    # Find .chd files (already converted inside archive)
    $chdFiles = Get-ChildItem -LiteralPath $extractFolder -Filter *.chd -Recurse -ErrorAction SilentlyContinue

    $converted = $false

    # Case: already .chd inside
    if ($chdFiles.Count -gt 0) {
        foreach ($chd in $chdFiles) {
            $destChd = Join-Path $psxDir $chd.Name
            Log "CHD encontrado dentro do archive: $($chd.Name). Movendo para $psxDir"
            Move-Literal $chd.FullName $destChd
            $converted = $true
        }
    }

    # Case: .cue files - convert each
    if (-not $converted -and $cueFiles.Count -gt 0) {
        foreach ($cue in $cueFiles) {
            $chdName = $cue.BaseName + ".chd"
            $outChd = Join-Path $psxDir $chdName
            Log "Convertendo (cue): $($cue.FullName) -> $outChd"
            & $chdman createcd -i $cue.FullName -o $outChd -f 2>&1 | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $outChd)) {
                Log "Conversao OK: $chdName"
                $converted = $true
            } else {
                Log "ERRO: Falha na conversao de $($cue.Name) (exit $LASTEXITCODE)"
            }
        }
    }

    # Case: .iso files - convert each
    if (-not $converted -and $isoFiles.Count -gt 0) {
        foreach ($iso in $isoFiles) {
            $chdName = $iso.BaseName + ".chd"
            $outChd = Join-Path $psxDir $chdName
            Log "Convertendo (iso): $($iso.FullName) -> $outChd"
            & $chdman createcd -i $iso.FullName -o $outChd -f 2>&1 | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $outChd)) {
                Log "Conversao OK: $chdName"
                $converted = $true
            } else {
                Log "ERRO: Falha na conversao de $($iso.Name) (exit $LASTEXITCODE)"
            }
        }
    }

    # Case: .bin/.img without .cue - create temp cue
    if (-not $converted -and $binFiles.Count -gt 0) {
        foreach ($bin in $binFiles) {
            $chdName = $bin.BaseName + ".chd"
            $outChd = Join-Path $psxDir $chdName
            $tempCue = Join-Path $bin.DirectoryName ($bin.BaseName + ".cue")

            if (-not (Test-Path -LiteralPath $tempCue)) {
                $cueContent = "FILE `"$($bin.Name)`" BINARY`r`nTRACK 01 MODE2/2352`r`nINDEX 01 00:00:00"
                Set-Content -LiteralPath $tempCue -Value $cueContent -Encoding ASCII -NoNewline
                Log "Criado .cue temporario: $tempCue"
            }

            Log "Convertendo (bin+cue): $tempCue -> $outChd"
            & $chdman createcd -i $tempCue -o $outChd -f 2>&1 | ForEach-Object { Log $_ }
            if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $outChd)) {
                Log "Conversao OK: $chdName"
                $converted = $true
            } else {
                Log "ERRO: Falha na conversao de $($bin.Name) (exit $LASTEXITCODE)"
                # Try direct bin as iso fallback
                Log "Tentando conversao direta do bin..."
                & $chdman createcd -i $bin.FullName -o $outChd -f 2>&1 | ForEach-Object { Log $_ }
                if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $outChd)) {
                    Log "Conversao OK (fallback): $chdName"
                    $converted = $true
                }
            }
        }
    }

    if (-not $converted) {
        Log "FALHA: Nao foi possivel converter $archiveName. Movendo para failed."
        Move-Literal $archivePath (Join-Path $failedDir $archiveName)
        # Clean temp
        Get-ChildItem -LiteralPath $tempDir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        return
    }

    # Move original archive to duplicados
    Log "Movendo original para duplicados: $archiveName"
    Move-Literal $archivePath (Join-Path $duplicadosDir $archiveName)

    # Also move the parent folder if it's now empty (just contains the archive that was moved)
    $parentFolder = [System.IO.Path]::GetDirectoryName($archivePath)
    if ($parentFolder -ne $psxDir -and (Test-Path -LiteralPath $parentFolder)) {
        $remaining = Get-ChildItem -LiteralPath $parentFolder -Recurse -ErrorAction SilentlyContinue
        if ($remaining.Count -eq 0) {
            Log "Removendo pasta vazia: $parentFolder"
            Remove-Item -LiteralPath $parentFolder -Force -ErrorAction SilentlyContinue
        }
    }

    # Clean temp
    Get-ChildItem -LiteralPath $tempDir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Log "=== Concluido: $archiveName ==="
}

function Process-LooseBin {
    param([string]$binPath)

    $dir = $binPath.DirectoryName
    $baseName = $binPath.BaseName
    $chdName = $baseName + ".chd"
    $outChd = Join-Path $psxDir $chdName

    # Check if chd already exists
    if (Test-Path -LiteralPath $outChd) {
        Log "CHD ja existe para $baseName. Pulando."
        return
    }

    Log "=== Processando .bin solto: $baseName ==="

    # Look for matching .cue
    $cuePath = Join-Path $dir ($baseName + ".cue")
    if (-not (Test-Path -LiteralPath $cuePath)) {
        # Create temp cue
        $cueContent = "FILE `"$($binPath.Name)`" BINARY`r`nTRACK 01 MODE2/2352`r`nINDEX 01 00:00:00"
        Set-Content -LiteralPath $cuePath -Value $cueContent -Encoding ASCII -NoNewline
        Log "Criado .cue temporario: $cuePath"
    }

    Log "Convertendo: $cuePath -> $outChd"
    & $chdman createcd -i $cuePath -o $outChd -f 2>&1 | ForEach-Object { Log $_ }

    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $outChd)) {
        Log "Conversao OK: $chdName"
        # Move bin and cue to duplicados
        Move-Literal $binPath.FullName (Join-Path $duplicadosDir $binPath.Name)
        if (Test-Path -LiteralPath $cuePath) {
            Move-Literal $cuePath (Join-Path $duplicadosDir ($baseName + ".cue"))
        }
    } else {
        Log "ERRO: Falha na conversao de $baseName (exit $LASTEXITCODE)"
        # Try direct
        & $chdman createcd -i $binPath.FullName -o $outChd -f 2>&1 | ForEach-Object { Log $_ }
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $outChd)) {
            Log "Conversao OK (fallback): $chdName"
            Move-Literal $binPath.FullName (Join-Path $duplicadosDir $binPath.Name)
        } else {
            Log "FALHA total: $baseName. Movendo para failed."
            Move-Literal $binPath.FullName (Join-Path $failedDir $binPath.Name)
        }
    }
}

# Main loop
$iteration = 0
while ($true) {
    $iteration++
    Log "--- Iteracao $iteration ---"

    # Find compressed files
    $archives = Get-ChildItem $psxDir -Include *.7z,*.zip,*.rar -Recurse -ErrorAction SilentlyContinue
    # Find loose bin/img/iso without matching chd
    $looseBins = Get-ChildItem $psxDir -Include *.bin,*.img,*.iso -Recurse -ErrorAction SilentlyContinue | Where-Object {
        $chdPath = Join-Path $psxDir ($_.BaseName + ".chd")
        -not (Test-Path -LiteralPath $chdPath)
    }

    $totalToProcess = $archives.Count + $looseBins.Count
    Log "Arquivos pendentes: $($archives.Count) compactados, $($looseBins.Count) bin/iso soltos"

    if ($totalToProcess -eq 0) {
        Log "=== NENHUM arquivo pendente. Processamento concluido! ==="
        break
    }

    # Process compressed files first
    foreach ($archive in $archives) {
        try {
            Process-Compressed -archivePath $archive.FullName
        } catch {
            Log "EXCECAO ao processar $($archive.FullName): $_"
        }
    }

    # Process loose bins
    foreach ($bin in $looseBins) {
        try {
            Process-LooseBin -binPath $bin
        } catch {
            Log "EXCECAO ao processar $($bin.FullName): $_"
        }
    }

    if ($iteration -gt 20) {
        Log "AVISO: Limite de iteracoes atingido. Parando."
        break
    }
}

Log "=== SCRIPT CONCLUIDO ==="
