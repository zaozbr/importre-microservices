$serials = @(
    'SCES-00563','SCES-01701','SCES-03035','SCPS-45125','SCUS-94177',
    'SCUS-94426','SCUS-94640','SCUS-94952','SLES-00081','SLES-00118',
    'SLES-00197','SLES-00217','SLES-00339','SLES-00417','SLES-005901',
    'SLES-00882','SLES-01007','SLES-01266','SLES-01267','SLES-01416',
    'SLES-01597','SLES-01939','SLES-02086','SLES-02375','SLES-02499',
    'SLES-02563','SLES-02631','SLES-02961','SLES-03149','SLES-03206'
)
$dir = 'D:\roms\library\roms\psx'
foreach ($s in $serials) {
    $p = Join-Path $dir "$s.chd"
    if (Test-Path $p) {
        $sz = (Get-Item $p).Length
        Write-Output "$s $sz"
    } else {
        Write-Output "$s MISSING"
    }
}
