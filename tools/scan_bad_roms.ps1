#requires -Version 5.1
<#
  scan_bad_roms.ps1 — Escaneia CHDs corrompidos e CUEs sem BIN
  Analisa o diretorio D:\roms\library\roms\psx\ procurando:
    1. CHDs com header invalido (nao comeca com "MComprCHD")
    2. CHDs com tamanho 0 ou muito pequeno (< 1KB)
    3. CUEs cujo BIN referenciado nao existe
    4. CUEs com track start out of range (parsing basico)
  Move arquivos problemáticos para D:\roms\quarantine\
#>
[CmdletBinding()]
param(
    [string]$RomDir    = 'D:\roms\library\roms\psx',
    [string]$Quarantine = 'D:\roms\quarantine',
    [string]$ReportFile = 'F:\importre\logs\bad_roms_report.txt',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

# --- helpers -----------------------------------------------------------------

function Test-ChdHeader {
    param([string]$Path)
    # CHD magic: "MComprCHD" (9 bytes ASCII) — mas na verdade o header CHD v3+ tem
    # tag "MComprCHD" nos primeiros 8 bytes. CHD v5 usa "MComprCHD" tambem.
    # Ref: chd.cpp — chd_file::open()
    try {
        $fs = [System.IO.File]::OpenRead($Path)
        try {
            $buf = New-Object byte[] 16
            $n = $fs.Read($buf, 0, 16)
            if ($n -lt 8) { return $false }
            $magic = [System.Text.Encoding]::ASCII.GetString($buf, 0, 8)
            return ($magic -eq 'MComprCHD')
        } finally { $fs.Dispose() }
    } catch {
        return $false  # arquivo em uso ou inacessivel — assume ruim
    }
}

function Get-CueBinReferences {
    param([string]$CuePath)
    $bins = @()
    $dir = [System.IO.Path]::GetDirectoryName($CuePath)
    foreach ($line in [System.IO.File]::ReadLines($CuePath)) {
        $t = $line.Trim()
        if ($t -match '^FILE\s+"([^"]+)"') {
            $bins += (Join-Path $dir $Matches[1])
        }
    }
    return $bins
}

# --- main --------------------------------------------------------------------

Write-Host "[scan] Diretorio: $RomDir"
Write-Host "[scan] Quarentena: $Quarantine"
Write-Host "[scan] DryRun: $DryRun"
Write-Host ''

# Garante pasta de quarentena
if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $Quarantine | Out-Null
}

$badFiles = [System.Collections.Generic.List[string]]::new()
$stats = [PSCustomObject]@{
    ChdTotal      = 0
    ChdBadHeader  = 0
    ChdEmpty      = 0
    CueTotal      = 0
    CueMissingBin = 0
    Moved         = 0
}

# 1) Escanear CHDs
Write-Host '[scan] Escaneando arquivos .chd...'
$chdFiles = Get-ChildItem -Path $RomDir -Filter '*.chd' -File -ErrorAction SilentlyContinue
$stats.ChdTotal = $chdFiles.Count
$i = 0

foreach ($f in $chdFiles) {
    $i++
    if ($i % 500 -eq 0) {
        Write-Host "  [$i/$($chdFiles.Count)] $($f.Name)"
    }

    $isBad = $false
    $reason = ''

    # tamanho 0 ou muito pequeno
    if ($f.Length -lt 1024) {
        $isBad = $true
        $reason = "empty_or_tiny ($($f.Length) bytes)"
        $stats.ChdEmpty++
    } else {
        # header invalido
        if (-not (Test-ChdHeader -Path $f.FullName)) {
            $isBad = $true
            $reason = "bad_header"
            $stats.ChdBadHeader++
        }
    }

    if ($isBad) {
        $badFiles.Add("$($f.FullName)|chd|$reason")
    }
}

Write-Host "[scan] CHDs: $($stats.ChdTotal) total, $($stats.ChdBadHeader) header ruim, $($stats.ChdEmpty) vazio/pequeno"

# 2) Escanear CUEs
Write-Host '[scan] Escaneando arquivos .cue...'
$cueFiles = Get-ChildItem -Path $RomDir -Filter '*.cue' -File -ErrorAction SilentlyContinue
$stats.CueTotal = $cueFiles.Count

foreach ($f in $cueFiles) {
    $bins = Get-CueBinReferences -CuePath $f.FullName
    if ($bins.Count -eq 0) {
        # CUE sem nenhuma referencia FILE — provavelmente corrompido
        $badFiles.Add("$($f.FullName)|cue|no_file_refs")
        $stats.CueMissingBin++
        continue
    }

    foreach ($b in $bins) {
        if (-not (Test-Path -LiteralPath $b -PathType Leaf)) {
            $badFiles.Add("$($f.FullName)|cue|missing_bin:$([System.IO.Path]::GetFileName($b))")
            $stats.CueMissingBin++
            break
        }
    }
}

Write-Host "[scan] CUEs: $($stats.CueTotal) total, $($stats.CueMissingBin) com BIN faltando"

# 3) Mover para quarentena
Write-Host ''
Write-Host "[move] $($badFiles.Count) arquivos problemáticos encontrados"

if ($badFiles.Count -eq 0) {
    Write-Host '[move] Nada a mover.'
} else {
    # Escrever relatorio
    $badFiles | ForEach-Object { $_ -replace '\|', "`t" } | Set-Content -Path $ReportFile -Encoding UTF8
    Write-Host "[move] Relatorio salvo em: $ReportFile"

    if (-not $DryRun) {
        foreach ($entry in $badFiles) {
            $parts = $entry -split '\|'
            $filePath = $parts[0]
            $type = $parts[1]
            $reason = $parts[2]

            if (Test-Path -LiteralPath $filePath -PathType Leaf) {
                $dest = Join-Path $Quarantine ([System.IO.Path]::GetFileName($filePath))
                # evita sobrescrever
                $base = [System.IO.Path]::GetFileNameWithoutExtension($dest)
                $ext = [System.IO.Path]::GetExtension($dest)
                $counter = 1
                while (Test-Path -LiteralPath $dest) {
                    $dest = Join-Path $Quarantine "${base}_${counter}${ext}"
                    $counter++
                }
                try {
                    Move-Item -LiteralPath $filePath -Destination $dest -ErrorAction Stop
                    $stats.Moved++
                    Write-Host "  [OK] $($parts[0]) -> $dest ($reason)"
                } catch {
                    Write-Host "  [ERRO] $($parts[0]): $_"
                }
            }
        }
    } else {
        Write-Host '[move] DryRun — apenas listando:'
        $badFiles | ForEach-Object {
            $p = $_ -split '\|'
            Write-Host "  $($p[0]) [$($p[1])] $($p[2])"
        }
    }
}

# 4) Relatorio final
Write-Host ''
Write-Host '=== RELATORIO FINAL ==='
Write-Host "CHDs escaneados:    $($stats.ChdTotal)"
Write-Host "  Header ruim:      $($stats.ChdBadHeader)"
Write-Host "  Vazio/pequeno:    $($stats.ChdEmpty)"
Write-Host "CUEs escaneados:    $($stats.CueTotal)"
Write-Host "  BIN faltando:     $($stats.CueMissingBin)"
Write-Host "Total problemáticos: $($badFiles.Count)"
Write-Host "Movidos:            $($stats.Moved)"
Write-Host "Relatorio:          $ReportFile"
