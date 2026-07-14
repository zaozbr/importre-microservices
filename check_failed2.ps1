$failedDir = "D:\roms\duplicados\failed"
$tempDir = "F:\importre\temp_extract"
$sevenZip = "C:\Program Files\7-Zip\7z.exe"
$logFile = "F:\importre\logs\chd_batch.log"

function Log-Message {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -ErrorAction SilentlyContinue
}

# Get all archives in failed dir with non-zero size
$archives = Get-ChildItem -LiteralPath $failedDir -File | Where-Object { ($_.Extension -eq '.7z' -or $_.Extension -eq '.zip' -or $_.Extension -eq '.rar') -and $_.Length -gt 0 }
Log-Message "Checking $($archives.Count) non-zero archives in failed dir"

foreach ($archive in $archives) {
    Log-Message "Testing: $($archive.Name) ($($archive.Length) bytes)"
    if (Test-Path $tempDir) { Get-ChildItem $tempDir -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    $errFile = Join-Path $tempDir "7z_err.txt"
    $outFile = Join-Path $tempDir "7z_out.txt"
    
    $proc = Start-Process -FilePath $sevenZip -ArgumentList "t", "`"$($archive.FullName)`"" -NoNewWindow -Wait -PassThru -RedirectStandardOutput $outFile -RedirectStandardError $errFile
    if ($proc.ExitCode -eq 0) {
        Log-Message "  VALID archive! Trying extraction..."
        $proc2 = Start-Process -FilePath $sevenZip -ArgumentList "x", "`"$($archive.FullName)`"", "-o`"$tempDir`"", "-y" -NoNewWindow -Wait -PassThru -RedirectStandardOutput $outFile -RedirectStandardError $errFile
        if ($proc2.ExitCode -eq 0) {
            $extracted = Get-ChildItem $tempDir -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '7z_err.txt' -and $_.Name -ne '7z_out.txt' }
            Log-Message "  Extracted $($extracted.Count) files"
            foreach ($f in $extracted) {
                Log-Message "    -> $($f.Name) ($($f.Length) bytes)"
            }
        } else {
            Log-Message "  Extraction failed (exit $($proc2.ExitCode))"
        }
    } else {
        $err = ""
        if (Test-Path -LiteralPath $errFile) { $raw = Get-Content -LiteralPath $errFile -Raw; if ($raw) { $err = $raw.Substring(0, [Math]::Min(150, $raw.Length)) } }
        Log-Message "  CORRUPTED: $err"
    }
}

if (Test-Path $tempDir) { Get-ChildItem $tempDir -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue }
