$dir = 'D:\roms\library\roms\psx'

# Lista de renomeacoes: @('serial', 'novo-nome')
$renames = @(
    @('SCPS-45125', 'Einhander-SCPS-45125.chd'),
    @('SCUS-94177', 'Interactive-CD-Sampler-Volume-3.5-SCUS-94177.chd'),
    @('SCUS-94426', 'Crash-Team-Racing-SCUS-94426.chd'),
    @('SCUS-94640', 'Syphon-Filter-3-SCUS-94640.chd'),
    @('SCUS-94952', 'PlayStation-Picks-SCUS-94952.chd'),
    @('SLES-00081', 'Defcon-5-SLES-00081.chd'),
    @('SLES-00118', 'Power-Serve-SLES-00118.chd'),
    @('SLES-00197', 'Galaxy-Fight-SLES-00197.chd'),
    @('SLES-00217', 'Sampras-Extreme-Tennis-SLES-00217.chd'),
    @('SLES-00339', 'Fade-to-Black-SLES-00339.chd'),
    @('SLES-00417', 'Allied-General-SLES-00417.chd'),
    @('SLES-00882', "NBA-Pro-'98-SLES-00882.chd"),
    @('SLES-01007', 'Command-&-Conquer-Red-Alert-SLES-01007.chd'),
    @('SLES-01267', 'World-Cup-98-SLES-01267.chd'),
    @('SLES-01416', 'Asterix-SLES-01416.chd'),
    @('SLES-01597', 'Egypt-1156-B.C.-Tomb-of-the-Pharaoh-SLES-01597.chd'),
    @('SLES-01939', 'Ruff-&-Tumble-SLES-01939.chd'),
    @('SLES-02086', 'N-Gen-Racing-SLES-02086.chd'),
    @('SLES-02375', '007-Tomorrow-Never-Dies-SLES-02375.chd'),
    @('SLES-02499', 'Midnight-In-Vegas-SLES-02499.chd'),
    @('SLES-02563', 'Anstoss-Premier-Manager-SLES-02563.chd'),
    @('SLES-02631', 'Wild-Rapids-SLES-02631.chd'),
    @('SLES-02961', 'Anastasia-SLES-02961.chd'),
    @('SLES-03149', 'International-Superstar-Soccer-2000-SLES-03149.chd'),
    @('SLES-03206', 'Card-Shark-SLES-03206.chd')
)

$success = 0
$skipped = 0
$errors = 0

foreach ($entry in $renames) {
    $serial = $entry[0]
    $newName = $entry[1]
    $oldPath = Join-Path $dir "$serial.chd"
    $newPath = Join-Path $dir $newName

    # Verificar se origem existe
    if (-not (Test-Path $oldPath)) {
        Write-Output "SKIP (MISSING): $serial.chd"
        $skipped++
        continue
    }

    # Verificar se tem 0 bytes
    $fileSize = (Get-Item $oldPath).Length
    if ($fileSize -eq 0) {
        Write-Output "SKIP (0 bytes): $serial.chd"
        $skipped++
        continue
    }

    # Verificar se destino ja existe
    if (Test-Path $newPath) {
        Write-Output "SKIP (target exists): $newName"
        $skipped++
        continue
    }

    # Renomear
    try {
        Rename-Item -Path $oldPath -NewName $newName -ErrorAction Stop
        Write-Output "OK: $serial.chd -> $newName ($fileSize bytes)"
        $success++
    } catch {
        Write-Output "ERROR: $serial.chd -> $newName : $_"
        $errors++
    }
}

Write-Output ""
Write-Output "=== RESUMO ==="
Write-Output "Renomeados: $success"
Write-Output "Pulados: $skipped"
Write-Output "Erros: $errors"
