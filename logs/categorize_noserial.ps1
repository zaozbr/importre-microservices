$dir = "D:\roms\library\roms\psx"
$noSerialFile = "F:\importre\logs\files_no_serial.txt"
$names = Get-Content $noSerialFile

$categories = @{
    bios = @()
    test = @()
    homebrew = @()
    multipart = @()      # _1, _2 etc
    multitrack = @()     # (Track-N)
    spacesInName = @()   # still has spaces/parens
    incompleteSerial = @()
    genuine = @()        # real games needing lookup
}

foreach ($name in $names) {
    $base = [System.IO.Path]::GetFileNameWithoutExtension($name)
    
    if ($base -match '^SCPH|^scph') {
        $categories.bios += $name
    } elseif ($base -match 'UNKNOWN$|^test-|^SBL0$|^buzzy$|^nortis$|^japan-j3$|^WCG[12]$|^yicestar') {
        $categories.test += $name
    } elseif ($base -match 'HBREW|NYMC|Celeste-Classic|Magic-Castle') {
        $categories.homebrew += $name
    } elseif ($base -match '_\d+$') {
        $categories.multipart += $name
    } elseif ($base -match '\(Track-') {
        $categories.multitrack += $name
    } elseif ($base -match ' ' -or $base -match '\(') {
        $categories.spacesInName += $name
    } elseif ($base -match 'SLPS-\d{1,3}$') {
        $categories.incompleteSerial += $name
    } else {
        $categories.genuine += $name
    }
}

Write-Host "=== NO-SERIAL FILE CATEGORIES ==="
Write-Host "BIOS files: $($categories.bios.Count)"
$categories.bios | ForEach-Object { Write-Host "  $_" }
Write-Host ""

Write-Host "Test/UNKNOWN files: $($categories.test.Count)"
$categories.test | ForEach-Object { Write-Host "  $_" }
Write-Host ""

Write-Host "Homebrew files: $($categories.homebrew.Count)"
$categories.homebrew | ForEach-Object { Write-Host "  $_" }
Write-Host ""

Write-Host "Multi-part (_N) files: $($categories.multipart.Count)"
$categories.multipart | ForEach-Object { Write-Host "  $_" }
Write-Host ""

Write-Host "Multi-track (Track-N) files: $($categories.multitrack.Count)"
$categories.multitrack | ForEach-Object { Write-Host "  $_" }
Write-Host ""

Write-Host "Files with spaces/parens in name: $($categories.spacesInName.Count)"
$categories.spacesInName | ForEach-Object { Write-Host "  $_" }
Write-Host ""

Write-Host "Incomplete serial: $($categories.incompleteSerial.Count)"
$categories.incompleteSerial | ForEach-Object { Write-Host "  $_" }
Write-Host ""

Write-Host "Genuine games needing lookup: $($categories.genuine.Count)"
$categories.genuine | ForEach-Object { Write-Host "  $_" }
Write-Host ""

# Save genuine list for web search
$categories.genuine | Out-File "F:\importre\logs\genuine_no_serial.txt" -Encoding UTF8
$categories.spacesInName | Out-File "F:\importre\logs\spaces_no_serial.txt" -Encoding UTF8
