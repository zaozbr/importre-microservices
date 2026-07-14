$dir = 'D:\roms\library\roms\psx'
$files = Get-ChildItem $dir -Filter '*.chd'

# Extract all potential serials with 4-letter prefix + digits
$serials = @{}
foreach ($f in $files) {
    $matches = [regex]::Matches($f.Name, '([A-Z]{4})-(\d{3,6})')
    foreach ($m in $matches) {
        $prefix = $m.Groups[1].Value
        if (!$serials.ContainsKey($prefix)) { $serials[$prefix] = 0 }
        $serials[$prefix]++
    }
}

Write-Output "=== All 4-letter prefixes found ==="
$serials.GetEnumerator() | Sort-Object Name | ForEach-Object { Write-Output "$($_.Key): $($_.Value)" }
