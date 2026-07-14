# Script de processamento CHD batch 3
# Processa todos os arquivos PSX nao convertidos

$ErrorActionPreference = 'Continue'
$psxDir = 'D:\roms\library\roms\psx'
$tempDir = 'F:\importre\temp_extract'
$duplicadosDir = 'D:\roms\duplicados'
$failedDir = 'D:\roms\duplicados\failed'
$logFile = 'F:\importre\logs\chd_batch3.log'
$chdman = 'D:\roms\library\roms\psx\chdman.exe'
$sevenZip = 'C:\Program Files\7-Zip\7z.exe'

# Garantir diretorios
foreach ($d in @($tempDir, $duplicadosDir, $failedDir, 'F:\importre\logs')) {
    if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

function Write-Log {
    param([string]$msg)
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -LiteralPath $logFile -Value $line -ErrorAction SilentlyContinue
}

function Move-FileSafe {
    param([string]$src, [string]$destDir)
    if (-not (Test-Path -LiteralPath $src)) { return $false }
    $name = Split-Path $src -Leaf
    $dest = Join-Path $destDir $name
    # Se ja existe no destino, adiciona sufixo
    $counter = 1
    while (Test-Path -LiteralPath $dest) {
        $base = [System.IO.Path]::GetFileNameWithoutExtension($name)
        $ext = [System.IO.Path]::GetExtension($name)
        $dest = Join-Path $destDir "${base}_$counter$ext"
        $counter++
    }
    try {
        Move-Item -LiteralPath $src -Destination $dest -ErrorAction Stop
        Write-Log "Movido: $src -> $dest"
        return $true
    } catch {
        Write-Log "ERRO ao mover: $src -> $dest : $_"
        return $false
    }
}

Write-Log "=== INICIO processamento batch 3 ==="

# ============================================
# FASE 1: Processar arquivos compactados (.7z, .zip, .rar)
# ============================================
$archives = Get-ChildItem $psxDir -Include *.7z,*.zip,*.rar -Recurse -ErrorAction SilentlyContinue
$archCount = ($archives | Measure-Object).Count
Write-Log "FASE 1: $archCount arquivos compactados encontrados"

foreach ($arch in $archives) {
    Write-Log "Processando archive: $($arch.Name)"
    $extractDir = Join-Path $tempDir ($arch.BaseName + '_extract')
    if (Test-Path -LiteralPath $extractDir) { Remove-Item -LiteralPath $extractDir -Recurse -Force }
    New-Item -ItemType Directory -Path $extractDir -Force | Out-Null

    # Extrair
    & $sevenZip x -y -o"$extractDir" -LiteralPath $arch.FullName 2>&1 | Out-Null

    # Procurar arquivos .bin/.img/.iso e .cue extraidos
    $bins = Get-ChildItem $extractDir -Include *.bin,*.img,*.iso -Recurse -ErrorAction SilentlyContinue
    foreach ($bin in $bins) {
        $cuePath = Join-Path $bin.DirectoryName ($bin.BaseName + '.cue')
        $outChd = Join-Path $psxDir ($bin.BaseName + '.chd')

        if (Test-Path -LiteralPath $outChd) {
            Write-Log "CHD ja existe para $($bin.Name), pulando conversao"
            continue
        }

        $inputFile = $null
        if (Test-Path -LiteralPath $cuePath) {
            $inputFile = $cuePath
        } else {
            # Criar cue temporario
            $tempCue = Join-Path $bin.DirectoryName ($bin.BaseName + '.cue')
            $cueContent = "FILE `"$($bin.Name)`" BINARY`nTRACK 01 MODE2/2352`nINDEX 01 00:00:00"
            Set-Content -LiteralPath $tempCue -Value $cueContent -Encoding ASCII
            $inputFile = $tempCue
            Write-Log "Cue temporario criado para $($bin.Name)"
        }

        Write-Log "Convertendo: $inputFile -> $outChd"
        & $chdman createcd -i "$inputFile" -o "$outChd" -f 2>&1 | ForEach-Object { Write-Log $_ }

        if (Test-Path -LiteralPath $outChd) {
            Write-Log "Conversao OK: $outChd"
            # Mover originais para duplicados
            Move-FileSafe $bin.FullName $duplicadosDir
            if (Test-Path -LiteralPath $cuePath) { Move-FileSafe $cuePath $duplicadosDir }
        } else {
            Write-Log "FALHA na conversao: $($bin.Name)"
            Move-FileSafe $bin.FullName $failedDir
            if (Test-Path -LiteralPath $cuePath) { Move-FileSafe $cuePath $failedDir }
        }
    }

    # Verificar se ja existe .chd extraido
    $extractedChds = Get-ChildItem $extractDir -Filter '*.chd' -Recurse -ErrorAction SilentlyContinue
    foreach ($echd in $extractedChds) {
        $destChd = Join-Path $psxDir $echd.Name
        if (-not (Test-Path -LiteralPath $destChd)) {
            Move-Item -LiteralPath $echd.FullName -Destination $destChd -ErrorAction SilentlyContinue
            Write-Log "CHD movido de archive: $($echd.Name)"
        }
    }

    # Mover archive original para duplicados
    Move-FileSafe $arch.FullName $duplicadosDir

    # Limpar temp
    Remove-Item -LiteralPath $extractDir -Recurse -Force -ErrorAction SilentlyContinue
}

# ============================================
# FASE 2: Processar .bin/.img/.iso avulsos (sem .chd correspondente)
# ============================================
Write-Log "FASE 2: Processando .bin/.img/.iso avulsos sem CHD"

$bins = Get-ChildItem $psxDir -Filter '*.bin' -ErrorAction SilentlyContinue
$isos = Get-ChildItem $psxDir -Filter '*.iso' -ErrorAction SilentlyContinue
$imgs = Get-ChildItem $psxDir -Filter '*.img' -ErrorAction SilentlyContinue
$allBins = @($bins) + @($isos) + @($imgs)

foreach ($bin in $allBins) {
    if ($null -eq $bin) { continue }
    $chdPath = Join-Path $psxDir ($bin.BaseName + '.chd')
    if (Test-Path -LiteralPath $chdPath) {
        # Ja tem CHD - mover fonte para duplicados
        Write-Log "CHD ja existe para $($bin.Name) - movendo fonte para duplicados"
        Move-FileSafe $bin.FullName $duplicadosDir
        $cuePath = Join-Path $psxDir ($bin.BaseName + '.cue')
        if (Test-Path -LiteralPath $cuePath) { Move-FileSafe $cuePath $duplicadosDir }
        continue
    }

    # Precisa converter
    $cuePath = Join-Path $psxDir ($bin.BaseName + '.cue')
    $outChd = Join-Path $psxDir ($bin.BaseName + '.chd')
    $inputFile = $null

    if (Test-Path -LiteralPath $cuePath) {
        $inputFile = $cuePath
    } else {
        # Criar cue temporario
        $tempCue = Join-Path $psxDir ($bin.BaseName + '.cue')
        $cueContent = "FILE `"$($bin.Name)`" BINARY`nTRACK 01 MODE2/2352`nINDEX 01 00:00:00"
        Set-Content -LiteralPath $tempCue -Value $cueContent -Encoding ASCII
        $inputFile = $tempCue
        Write-Log "Cue temporario criado para $($bin.Name)"
    }

    Write-Log "Convertendo: $inputFile -> $outChd"
    $output = & $chdman createcd -i "$inputFile" -o "$outChd" -f 2>&1
    foreach ($line in $output) { Write-Log $line }

    if ((Test-Path -LiteralPath $outChd) -and (Get-Item -LiteralPath $outChd).Length -gt 0) {
        Write-Log "Conversao OK: $outChd ($([math]::Round((Get-Item -LiteralPath $outChd).Length/1MB, 1)) MB)"
        # Mover originais para duplicados
        Move-FileSafe $bin.FullName $duplicadosDir
        if (Test-Path -LiteralPath $cuePath) { Move-FileSafe $cuePath $duplicadosDir }
    } else {
        Write-Log "FALHA na conversao: $($bin.Name)"
        if (Test-Path -LiteralPath $outChd) { Remove-Item -LiteralPath $outChd -Force -ErrorAction SilentlyContinue }
        Move-FileSafe $bin.FullName $failedDir
        if (Test-Path -LiteralPath $cuePath) { Move-FileSafe $cuePath $failedDir }
    }
}

# ============================================
# FASE 3: Processar .cue orfaos (sem .bin e sem .chd)
# ============================================
Write-Log "FASE 3: Processando .cue orfaos"

$cues = Get-ChildItem $psxDir -Filter '*.cue' -ErrorAction SilentlyContinue
foreach ($cue in $cues) {
    $chdPath = Join-Path $psxDir ($cue.BaseName + '.chd')
    $binPath = Join-Path $psxDir ($cue.BaseName + '.bin')

    if (Test-Path -LiteralPath $chdPath) {
        # CHD ja existe - mover cue para duplicados (bin ja foi movido na fase 2)
        Write-Log "CHD existe para $($cue.Name) - movendo cue para duplicados"
        Move-FileSafe $cue.FullName $duplicadosDir
    } elseif (-not (Test-Path -LiteralPath $binPath)) {
        # Sem bin e sem chd - orfao, mover para failed
        Write-Log "Cue orfao (sem bin e sem chd): $($cue.Name) - movendo para failed"
        Move-FileSafe $cue.FullName $failedDir
    }
}

# ============================================
# FASE 4: Processar .ecm (verificar se tem chd)
# ============================================
Write-Log "FASE 4: Verificando arquivos .ecm"
$ecms = Get-ChildItem $psxDir -Filter '*.ecm' -ErrorAction SilentlyContinue
foreach ($ecm in $ecms) {
    # .ecm precisa ser decodificado primeiro (unecm) - sem ferramenta disponivel
    # Verificar se ja existe chd correspondente
    $baseName = $ecm.BaseName  # inclui .bin
    $chdPath = Join-Path $psxDir ([System.IO.Path]::GetFileNameWithoutExtension($baseName) + '.chd')
    if (Test-Path -LiteralPath $chdPath) {
        Write-Log "CHD ja existe para ECM $($ecm.Name) - movendo ECM para duplicados"
        Move-FileSafe $ecm.FullName $duplicadosDir
    } else {
        Write-Log "ECM sem CHD correspondente: $($ecm.Name) - sem ferramenta unecm, movendo para failed"
        Move-FileSafe $ecm.FullName $failedDir
    }
}

# ============================================
# FASE 5: Limpeza de .bin/.cue ja convertidos (que ainda restaram)
# ============================================
Write-Log "FASE 5: Limpeza final de arquivos fonte ja convertidos"
$remainingBins = Get-ChildItem $psxDir -Filter '*.bin' -ErrorAction SilentlyContinue
foreach ($bin in $remainingBins) {
    $chdPath = Join-Path $psxDir ($bin.BaseName + '.chd')
    if (Test-Path -LiteralPath $chdPath) {
        Write-Log "Limpando bin ja convertido: $($bin.Name)"
        Move-FileSafe $bin.FullName $duplicadosDir
    }
}
$remainingCues = Get-ChildItem $psxDir -Filter '*.cue' -ErrorAction SilentlyContinue
foreach ($cue in $remainingCues) {
    $chdPath = Join-Path $psxDir ($cue.BaseName + '.chd')
    if (Test-Path -LiteralPath $chdPath) {
        Write-Log "Limpando cue ja convertido: $($cue.Name)"
        Move-FileSafe $cue.FullName $duplicadosDir
    }
}

# ============================================
# RELATORIO FINAL
# ============================================
Write-Log "=== RELATORIO FINAL ==="
$finalChds = (Get-ChildItem $psxDir -Filter '*.chd' -ErrorAction SilentlyContinue | Measure-Object).Count
$finalBins = (Get-ChildItem $psxDir -Filter '*.bin' -ErrorAction SilentlyContinue | Measure-Object).Count
$finalCues = (Get-ChildItem $psxDir -Filter '*.cue' -ErrorAction SilentlyContinue | Measure-Object).Count
$finalEcms = (Get-ChildItem $psxDir -Filter '*.ecm' -ErrorAction SilentlyContinue | Measure-Object).Count
$failedCount = (Get-ChildItem $failedDir -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Log "CHDs na pasta psx: $finalChds"
Write-Log "BINs restantes: $finalBins"
Write-Log "CUEs restantes: $finalCues"
Write-Log "ECMs restantes: $finalEcms"
Write-Log "Arquivos em failed: $failedCount"
Write-Log "=== FIM processamento batch 3 ==="
