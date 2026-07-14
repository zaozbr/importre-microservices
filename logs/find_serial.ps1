$binFile = 'C:\temp_chd\temp_test.bin'
$sectorSize = 2352
$numSectors = 50
$bytes = [System.IO.File]::ReadAllBytes($binFile)[0..($sectorSize * $numSectors)]
$text = [System.Text.Encoding]::ASCII.GetString($bytes)

# Look for PSX serial patterns: SLUS_012.34, SLES_004.77, etc
$matches = [regex]::Matches($text, '[A-Z]{4}[_-]\d{3}[\._-]\d{2}')
foreach ($m in $matches) {
    Write-Output "Found: $($m.Value) at offset $($m.Index)"
}

# Also try broader pattern
$matches2 = [regex]::Matches($text, 'SL[A-Z]{2}[_-]\d{3}')
foreach ($m in $matches2) {
    Write-Output "Broad: $($m.Value) at offset $($m.Index)"
}

# Also check for volume label in ISO9660 (offset 0x8000 = sector 16)
$sector16 = [System.IO.File]::ReadAllBytes($binFile)[($sectorSize * 16)..($sectorSize * 17)]
$volText = [System.Text.Encoding]::ASCII.GetString($sector16)
Write-Output "--- Sector 16 (Volume Descriptor) ---"
# Volume ID is at offset 40 within the sector (but in MODE2_RAW, data starts at offset 24)
$volId = $volText.Substring(24 + 40, 32).Trim()
Write-Output "Volume ID: '$volId'"

# Search for serial in sector 16
$matches3 = [regex]::Matches($volText, '[A-Z]{4}[_-]\d{3}[\._-]\d{2}')
foreach ($m in $matches3) {
    Write-Output "Sector16: $($m.Value) at offset $($m.Index)"
}
