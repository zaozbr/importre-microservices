$dir = "D:\roms\library\roms\psx"
$files = Get-ChildItem "$dir\*.chd"

$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE|ESPM|UNL'

$conforming = @()
$withDisc = @()
$withSuffix = @()
$withDiscSuffix = @()
$noSerial = @()
$other = @()

foreach ($f in $files) {
    $name = $f.BaseName
    if ($name -match "-($serialPrefixes)-\d{4,5}(\(Disc\d+\))?$") {
        $conforming += $f
    } elseif ($name -match "-($serialPrefixes)-\d{4,5}(\(Disc\d+\))?\(\d+\)$") {
        $withSuffix += $f
    } elseif ($name -match "-($serialPrefixes)-\d{4,5}-Disc\d+$") {
        $withDisc += $f
    } elseif ($name -match "-($serialPrefixes)-\d{4,5}-Disc\d+\(\d+\)$") {
        $withDiscSuffix += $f
    } elseif ($name -match "($serialPrefixes)-\d{4,5}") {
        $other += $f
    } else {
        $noSerial += $f
    }
}

# Categorize no-serial
$bios = @()
$test = @()
$homebrew = @()
$multipart = @()
$multitrack = @()
$genuine = @()

foreach ($f in $noSerial) {
    $name = $f.BaseName
    if ($name -match '^SCPH|^scph') { $bios += $f }
    elseif ($name -match 'UNKNOWN$|^test-|^SBL0$|^buzzy$|^nortis$|^japan-j3$|^WCG[12]$|^yicestar|^sp-1v1') { $test += $f }
    elseif ($name -match 'HBREW|NYMC|Celeste|Magic-Castle|Magic_Castle') { $homebrew += $f }
    elseif ($name -match '_\d+$') { $multipart += $f }
    elseif ($name -match 'Track-') { $multitrack += $f }
    else { $genuine += $f }
}

$totalNamed = $conforming.Count + $withDisc.Count + $withDiscSuffix.Count + $other.Count
$pct = [math]::Round($totalNamed / $files.Count * 100, 1)

Write-Host "============================================"
Write-Host "  RELATORIO FINAL - RENOMEACAO PSX ROMS"
Write-Host "============================================"
Write-Host ""
Write-Host "Diretorio: $dir"
Write-Host "Total de arquivos .chd: $($files.Count)"
Write-Host ""
Write-Host "--- STATUS DOS ARQUIVOS ---"
Write-Host ""
Write-Host "Nomeados com serial (conformes): $totalNamed ($pct%)"
Write-Host "  - Padrao [Nome]-[Serial].chd: $($conforming.Count)"
Write-Host "  - Multi-disc [Nome]-[Serial]-DiscN.chd: $($withDisc.Count)"
Write-Host "  - Multi-disc com duplicata: $($withDiscSuffix.Count)"
Write-Host "  - Outro formato com serial: $($other.Count)"
Write-Host ""
Write-Host "Duplicatas com sufixo (N): $($withSuffix.Count)"
Write-Host ""
Write-Host "Sem serial: $($noSerial.Count)"
Write-Host "  - BIOS (SCPH): $($bios.Count)"
Write-Host "  - Testes/UNKNOWN: $($test.Count)"
Write-Host "  - Homebrew: $($homebrew.Count)"
Write-Host "  - Multi-part (_N tracks): $($multipart.Count)"
Write-Host "  - Multi-track (Track-N): $($multitrack.Count)"
Write-Host "  - Jogos sem serial: $($genuine.Count)"
Write-Host ""

if ($genuine.Count -gt 0) {
    Write-Host "--- JOGOS AINDA SEM SERIAL ---"
    $genuine | ForEach-Object { Write-Host "  $($_.Name)" }
    Write-Host ""
}

if ($other.Count -gt 0) {
    Write-Host "--- ARQUIVOS 'OTHER' (tem serial, formato diferente) ---"
    $other | ForEach-Object { Write-Host "  $($_.Name)" }
    Write-Host ""
}

Write-Host "--- RESUMO DAS ACOES REALIZADAS ---"
Write-Host ""
Write-Host "Batch 1 (url_decode.ps1): 465 arquivos URL-decoded"
Write-Host "Batch 1 (rename_batch1.ps1): 1679 arquivos renomeados (serial no nome)"
Write-Host "Batch 2 (rename_batch2_chdman.ps1): 378 arquivos renomeados (serial via chdman)"
Write-Host "Batch 3 (rename_batch3.ps1): 77 arquivos renomeados (serial via Redump DAT)"
Write-Host "Batch 4 (rename_batch4.ps1): 15 arquivos renomeados (serial-only filenames)"
Write-Host "Manual: 1 arquivo (Baldy-Land-SLPS-010 -> SLPS-01074(3))"
Write-Host ""
Write-Host "Total de arquivos renomeados: ~2550"
Write-Host ""

# Save final lists
$withSuffix | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\final_duplicates.txt" -Encoding UTF8
$noSerial | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\final_no_serial.txt" -Encoding UTF8
$other | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\final_other.txt" -Encoding UTF8
$genuine | ForEach-Object { $_.Name } | Out-File "F:\importre\logs\final_genuine_no_serial.txt" -Encoding UTF8

Write-Host "Listas finais salvas em:"
Write-Host "  F:\importre\logs\final_duplicates.txt ($($withSuffix.Count) duplicatas)"
Write-Host "  F:\importre\logs\final_no_serial.txt ($($noSerial.Count) sem serial)"
Write-Host "  F:\importre\logs\final_other.txt ($($other.Count) other)"
Write-Host "  F:\importre\logs\final_genuine_no_serial.txt ($($genuine.Count) jogos sem serial)"
