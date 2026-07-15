$dir = 'D:\roms\library\roms\psx'

$renamed = @(
    'Einhander-SCPS-45125.chd',
    'Interactive-CD-Sampler-Volume-3.5-SCUS-94177.chd',
    'Crash-Team-Racing-SCUS-94426.chd',
    'Syphon-Filter-3-SCUS-94640.chd',
    'Defcon-5-SLES-00081.chd',
    'Power-Serve-SLES-00118.chd',
    'Galaxy-Fight-SLES-00197.chd',
    'Fade-to-Black-SLES-00339.chd',
    'Allied-General-SLES-00417.chd',
    "NBA-Pro-'98-SLES-00882.chd",
    'Command-&-Conquer-Red-Alert-SLES-01007.chd',
    'World-Cup-98-SLES-01267.chd',
    'Asterix-SLES-01416.chd',
    'Egypt-1156-B.C.-Tomb-of-the-Pharaoh-SLES-01597.chd',
    'Ruff-&-Tumble-SLES-01939.chd',
    'N-Gen-Racing-SLES-02086.chd',
    '007-Tomorrow-Never-Dies-SLES-02375.chd',
    'Midnight-In-Vegas-SLES-02499.chd',
    'Anstoss-Premier-Manager-SLES-02563.chd',
    'Wild-Rapids-SLES-02631.chd',
    'Anastasia-SLES-02961.chd',
    'International-Superstar-Soccer-2000-SLES-03149.chd'
)

$ok = 0
$missing = 0
foreach ($name in $renamed) {
    $p = Join-Path $dir $name
    if (Test-Path $p) {
        $sz = (Get-Item $p).Length
        Write-Output "OK: $name ($sz bytes)"
        $ok++
    } else {
        Write-Output "MISSING: $name"
        $missing++
    }
}

Write-Output ""
Write-Output "Verificados: $ok OK, $missing MISSING"
