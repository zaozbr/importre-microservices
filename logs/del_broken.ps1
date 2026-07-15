$files = @(
  'C:\teste\SLES-01007.chd',
  'C:\teste\SLUS-00547.chd',
  'C:\teste\SLUS-00859.chd',
  'C:\teste\SLUS-01106.chd',
  'C:\teste\SLUS-01470.chd'
)
foreach ($f in $files) {
  if (Test-Path $f) {
    try {
      Remove-Item -LiteralPath $f -Force -ErrorAction Stop
      Write-Output "OK: $f"
    } catch {
      Write-Output "FAIL: $f - $($_.Exception.Message)"
    }
  } else {
    Write-Output "GONE: $f"
  }
}
