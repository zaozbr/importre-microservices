# Quick test of chdman extraction
$chdman = 'D:\roms\library\roms\psx\chdman.exe'
$tempDir = 'C:\temp_chd'
if (!(Test-Path $tempDir)) { New-Item -ItemType Directory -Path $tempDir -Force | Out-Null }

$testFile = 'D:\roms\library\roms\psx\3D-Lemmings.chd'
$tempBin = Join-Path $tempDir 'test.bin'
$tempCue = Join-Path $tempDir 'test.cue'

Remove-Item $tempBin -ErrorAction SilentlyContinue
Remove-Item $tempCue -ErrorAction SilentlyContinue

& $chdman extractcd -i $testFile -o $tempCue -ob $tempBin -f 2>&1 | Out-Null

if (Test-Path $tempBin) {
    $sectorSize = 2352
    $numSectors = 50
    $bytesToRead = $sectorSize * $numSectors
    $fs = [System.IO.File]::OpenRead($tempBin)
    $buffer = New-Object byte[] $bytesToRead
    $read = $fs.Read($buffer, 0, $bytesToRead)
    $fs.Close()
    
    $text = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $read)
    
    $matches = [regex]::Matches($text, '(SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA)[_-](\d{3})[\._-](\d{2})')
    foreach ($m in $matches) {
        Write-Output "Serial: $($m.Groups[1].Value)-$($m.Groups[2].Value)$($m.Groups[3].Value) at offset $($m.Index)"
    }
    
    $matches2 = [regex]::Matches($text, '(SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA)[_-](\d{4,5})')
    foreach ($m in $matches2) {
        Write-Output "Serial (4-5 digit): $($m.Groups[1].Value)-$($m.Groups[2].Value) at offset $($m.Index)"
    }
    
    Remove-Item $tempBin -ErrorAction SilentlyContinue
    Remove-Item $tempCue -ErrorAction SilentlyContinue
    Write-Output "Done"
} else {
    Write-Output "Extraction failed"
}
