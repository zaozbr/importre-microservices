$dir = "D:\roms\library\roms\psx"
$chdman = "F:\importre\chdman.exe"
$tempDir = "C:\temp_chd"

# Test with files that have no serial
$testFiles = @(
    "Aqua-GT.chd",
    "Battle-Arena-Toshinden.chd",
    "Card-Shark.chd",
    "Re-Volt.chd",
    "Ten-Pin-Alley.chd"
)

$serialPattern = '(SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE)[-_]?\d{4,5}'

foreach ($f in $testFiles) {
    $path = Join-Path $dir $f
    if (-not (Test-Path $path)) { continue }
    
    Write-Host "=== $f ==="
    
    # Extract to temp
    $base = [System.IO.Path]::GetFileNameWithoutExtension($f)
    $outBin = Join-Path $tempDir "${base}.bin"
    $outCue = Join-Path $tempDir "${base}.cue"
    
    # Clean up old files
    Remove-Item $outBin -ErrorAction SilentlyContinue
    Remove-Item $outCue -ErrorAction SilentlyContinue
    
    & $chdman extractcd -i $path -o $outCue -ib $outBin 2>&1 | Out-Null
    
    if (Test-Path $outBin) {
        # Read binary and search for serial patterns
        $bytes = [System.IO.File]::ReadAllBytes($outBin)
        $text = [System.Text.Encoding]::ASCII.GetString($bytes)
        
        # Search for BOOT line (SYSTEM.CNF)
        $bootMatches = [regex]::Matches($text, 'BOOT\s*=\s*cdrom:\\([^\s;]+)')
        foreach ($m in $bootMatches) {
            Write-Host "  BOOT: $($m.Groups[1].Value)"
        }
        
        # Search for serial pattern
        $serialMatches = [regex]::Matches($text, $serialPattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
        $found = @()
        foreach ($m in $serialMatches) {
            $val = $m.Value.ToUpper()
            if ($val -notmatch '^SLED' -or $val -match '\d{5}') {
                $found += $val
            }
        }
        $unique = $found | Select-Object -Unique
        if ($unique.Count -gt 0) {
            Write-Host "  Serials found: $($unique -join ', ')"
        } else {
            Write-Host "  No serials found"
        }
        
        # Also search for SYSTEM.CNF content
        $cnfIdx = $text.IndexOf('SYSTEM.CNF')
        if ($cnfIdx -ge 0) {
            $context = $text.Substring([math]::Max(0, $cnfIdx - 10), [math]::Min(500, $text.Length - $cnfIdx + 10))
            $bootLine = [regex]::Match($context, 'BOOT[^\n]*')
            if ($bootLine.Success) {
                Write-Host "  SYSTEM.CNF BOOT: $($bootLine.Value.Trim())"
            }
        }
        
        # Clean up
        Remove-Item $outBin -ErrorAction SilentlyContinue
        Remove-Item $outCue -ErrorAction SilentlyContinue
    } else {
        Write-Host "  Extraction failed"
    }
    Write-Host ""
}
