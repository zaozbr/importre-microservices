$logFile = "F:\importre\logs\chd_batch2.log"

function Log {
    param([string]$msg)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Add-Content -LiteralPath $logFile -Value $line
    Write-Output $line
}

$psxDir = "D:\roms\library\roms\psx"
$duplicadosDir = "D:\roms\duplicados"
$failedDir = "D:\roms\duplicados\failed"

# 1. Beyond the Beyond (empty folder)
$folder = Join-Path $psxDir "Beyond the Beyond (USA)"
if (Test-Path -LiteralPath $folder) {
    $items = Get-ChildItem -LiteralPath $folder -Recurse -ErrorAction SilentlyContinue
    if ($items.Count -eq 0) {
        Remove-Item -LiteralPath $folder -Force
        Log "Pasta vazia removida: Beyond the Beyond (USA)"
    }
}

# 2. Twisted Metal - .ape to duplicados
$folder = Join-Path $psxDir "Twisted Metal - World Tour (E) [SCES-00567]"
if (Test-Path -LiteralPath $folder) {
    Log "Movendo .ape do Twisted Metal para duplicados (CHD ja existe: Twisted-Metal-World-Tour-SCES-00567.chd)"
    Get-ChildItem -LiteralPath $folder | ForEach-Object {
        Move-Item -LiteralPath $_.FullName -Destination $duplicadosDir -Force
        Log "Movido: $($_.Name)"
    }
    if ((Get-ChildItem -LiteralPath $folder -Recurse -ErrorAction SilentlyContinue).Count -eq 0) {
        Remove-Item -LiteralPath $folder -Force
        Log "Pasta vazia removida: Twisted Metal"
    }
}

# 3. Ultraman - .ape and .cue to duplicados
$folder = Join-Path $psxDir "Ultraman Tiga & Dyna Fighting Evolution - New Generations (Japan) [SLPS-01455]"
if (Test-Path -LiteralPath $folder) {
    Log "Movendo .ape/.cue do Ultraman para duplicados (CHD ja existe)"
    Get-ChildItem -LiteralPath $folder | ForEach-Object {
        Move-Item -LiteralPath $_.FullName -Destination $duplicadosDir -Force
        Log "Movido: $($_.Name)"
    }
    if ((Get-ChildItem -LiteralPath $folder -Recurse -ErrorAction SilentlyContinue).Count -eq 0) {
        Remove-Item -LiteralPath $folder -Force
        Log "Pasta vazia removida: Ultraman"
    }
}

# 4. Vigilante 8 - .ape to failed (Track 01 failed)
$folder = Join-Path $psxDir "Vigilante 8 - Second Offense (E) [SLES-02162]"
if (Test-Path -LiteralPath $folder) {
    Log "Movendo .ape do Vigilante 8 para failed (Track 01 falhou)"
    Get-ChildItem -LiteralPath $folder | ForEach-Object {
        Move-Item -LiteralPath $_.FullName -Destination $failedDir -Force
        Log "Movido para failed: $($_.Name)"
    }
    if ((Get-ChildItem -LiteralPath $folder -Recurse -ErrorAction SilentlyContinue).Count -eq 0) {
        Remove-Item -LiteralPath $folder -Force
        Log "Pasta vazia removida: Vigilante 8"
    }
}

# Final check
Log "=== VERIFICACAO FINAL ==="
$archives = (Get-ChildItem $psxDir -Include *.7z,*.zip,*.rar -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
$bins = (Get-ChildItem $psxDir -Include *.bin,*.img,*.iso -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
$dirs = (Get-ChildItem $psxDir -Directory -ErrorAction SilentlyContinue | Measure-Object).Count
$chds = (Get-ChildItem $psxDir -Filter *.chd -ErrorAction SilentlyContinue | Measure-Object).Count
Log "Compactados restantes: $archives"
Log "Bin/Img/Iso restantes: $bins"
Log "Subpastas restantes: $dirs"
Log "Total CHDs: $chds"
Log "=== FIM ==="
