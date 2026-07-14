$bins = Get-ChildItem 'D:\roms\library\roms\psx' -Filter '*.bin'
foreach ($b in $bins) {
    $chd = Join-Path $b.DirectoryName ($b.BaseName + '.chd')
    $cue = Join-Path $b.DirectoryName ($b.BaseName + '.cue')
    Write-Host ($b.Name + ' | CHD:' + (Test-Path -LiteralPath $chd) + ' | CUE:' + (Test-Path -LiteralPath $cue))
}
Write-Host '---CUE---'
$cues = Get-ChildItem 'D:\roms\library\roms\psx' -Filter '*.cue'
foreach ($c in $cues) {
    $chd = Join-Path $c.DirectoryName ($c.BaseName + '.chd')
    $bin = Join-Path $c.DirectoryName ($c.BaseName + '.bin')
    Write-Host ($c.Name + ' | CHD:' + (Test-Path -LiteralPath $chd) + ' | BIN:' + (Test-Path -LiteralPath $bin))
}
