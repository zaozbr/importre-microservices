$dir = "D:\roms\library\roms\psx"
$files = Get-ChildItem "$dir\*.chd"
$serialPrefixes = 'SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE|ESPM|UNL'

$other = @()
foreach ($f in $files) {
    $name = $f.BaseName
    if ($name -match "($serialPrefixes)-\d{4,5}" -and 
        $name -notmatch "-($serialPrefixes)-\d{4,5}(\(Disc\d+\))?$" -and
        $name -notmatch "-($serialPrefixes)-\d{4,5}(\(Disc\d+\))?\(\d+\)$" -and
        $name -notmatch "-($serialPrefixes)-\d{4,5}-Disc\d+$" -and
        $name -notmatch "-($serialPrefixes)-\d{4,5}-Disc\d+\(\d+\)$") {
        $other += $f
    }
}

Write-Host "=== OTHER (has serial, different format) - $($other.Count) files ==="
$other | ForEach-Object { Write-Host "  $($_.Name)" }
