Write-Host "=== Registry Avast (mlm / hardware / gpu / provider) ==="
$paths = @(
  'HKLM:\SOFTWARE\Avast Software\Avast\mlm',
  'HKLM:\SOFTWARE\Avast Software\Avast',
  'HKLM:\SOFTWARE\Avast Software\mlm',
  'HKCU:\SOFTWARE\Avast Software\Avast\mlm'
)
foreach ($p in $paths) {
  if (Test-Path $p) {
    Write-Host ""
    Write-Host "--- $p ---"
    Get-ItemProperty $p -ErrorAction SilentlyContinue | Format-List
  }
}

Write-Host ""
Write-Host "=== Busca por chaves com 'gpu/dml/hardware/provider/mlm' ==="
Get-ChildItem 'HKLM:\SOFTWARE\Avast Software' -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
  $key = $_.PSPath
  $props = Get-ItemProperty $key -ErrorAction SilentlyContinue
  if ($props) {
    $props.PSObject.Properties | Where-Object {
      $_.Name -match 'gpu|dml|directml|hardware|provider|mlm|model' -and $_.Name -notmatch '^PS'
    } | ForEach-Object {
      Write-Host "$key :: $($_.Name) = $($_.Value)"
    }
  }
}

Write-Host ""
Write-Host "=== Settings.xml / user_settings da Avast ==="
Get-ChildItem 'C:\ProgramData\Avast Software\Avast' -Recurse -Include 'settings*.xml','*.settings','usercfg*' -ErrorAction SilentlyContinue | Select-Object FullName, Length | Format-Table -AutoSize
