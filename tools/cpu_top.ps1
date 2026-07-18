$snap1 = @{}
Get-Process | Where-Object { $_.CPU -gt 0 } | ForEach-Object { $snap1[$_.Id] = @{ Name=$_.Name; CPU=$_.CPU; Priority=$_.PriorityClass } }
Start-Sleep -Seconds 3
$snap2 = @{}
Get-Process | Where-Object { $_.CPU -gt 0 } | ForEach-Object { $snap2[$_.Id] = @{ Name=$_.Name; CPU=$_.CPU; Priority=$_.PriorityClass } }

$cores = (Get-CimInstance Win32_Processor).NumberOfLogicalProcessors
$results = @()
foreach ($id in $snap2.Keys) {
  if ($snap1.ContainsKey($id)) {
    $delta = $snap2[$id].CPU - $snap1[$id].CPU
    if ($delta -gt 0) {
      $pct = [math]::Round($delta / 3 * 100 / $cores, 1)
      $results += [PSCustomObject]@{
        Name = $snap2[$id].Name
        Id = $id
        CPU_pct = $pct
        Priority = $snap2[$id].Priority
      }
    }
  }
}
$results | Sort-Object CPU_pct -Descending | Select-Object -First 20 | Format-Table -AutoSize
Write-Host ""
Write-Host "Total CPU logico: $cores cores"
Write-Host "Soma do top: " ([math]::Round(($results | Measure-Object CPU_pct -Sum).Sum,1)) "%"
