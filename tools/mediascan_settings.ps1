Write-Host "=== MediaScan\Common ==="
Get-ItemProperty 'HKLM:\SOFTWARE\Avast Software\Avast\properties\MediaScan\Common' -ErrorAction SilentlyContinue | Format-List

Write-Host ""
Write-Host "=== MediaScan\Settings ==="
Get-ItemProperty 'HKLM:\SOFTWARE\Avast Software\Avast\properties\MediaScan\Settings' -ErrorAction SilentlyContinue | Format-List

Write-Host ""
Write-Host "=== Todas subchaves de MediaScan ==="
Get-ChildItem 'HKLM:\SOFTWARE\Avast Software\Avast\properties\MediaScan' -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
  Write-Host ""
  Write-Host "--- $($_.PSChildName) ---"
  Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue | Format-List
}

Write-Host ""
Write-Host "=== Busca ampla por 'dml/gpu/directml/hardware' em toda registry Avast ==="
Get-ChildItem 'HKLM:\SOFTWARE\Avast Software' -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
  $props = Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue
  if ($props) {
    $props.PSObject.Properties | Where-Object {
      $_.Value -is [string] -and ($_.Value -match 'dml|directml|gpu|hardware accel') -and $_.Name -notmatch '^PS'
    } | ForEach-Object {
      Write-Host "$($_.PSChildName) :: $($_.Name) = $($_.Value)"
    }
  }
}
