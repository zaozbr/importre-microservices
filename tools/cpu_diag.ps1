Write-Host "=== Processos Avast/model_host ==="
Get-Process | Where-Object { $_.Name -like '*Avast*' -or $_.Name -like '*model_host*' } | Select-Object Name, Id, CPU, PriorityClass, @{N='WS_MB';E={[math]::Round($_.WorkingSet/1MB,1)}} | Format-Table -AutoSize

Write-Host ""
Write-Host "=== Amostragem LoadPercentage (10 amostras x 2s) ==="
$sum = 0
for ($i = 1; $i -le 10; $i++) {
  $lp = (Get-CimInstance Win32_Processor).LoadPercentage
  $sum += $lp
  Write-Host ("Sample {0} : {1}%" -f $i, $lp)
  Start-Sleep -Seconds 2
}
Write-Host ("Media: {0}%" -f [math]::Round($sum/10,1))

Write-Host ""
Write-Host "=== Uso de CPU por processo (snapshot 4s) ==="
$snap1 = @{}
Get-Process | Where-Object { $_.CPU -gt 0 } | ForEach-Object { $snap1[$_.Id] = @{ Name=$_.Name; CPU=$_.CPU; Priority=$_.PriorityClass } }
Start-Sleep -Seconds 4
$cores = (Get-CimInstance Win32_Processor).NumberOfLogicalProcessors
$results = @()
Get-Process | Where-Object { $_.CPU -gt 0 } | ForEach-Object {
  if ($snap1.ContainsKey($_.Id)) {
    $delta = $_.CPU - $snap1[$_.Id].CPU
    if ($delta -gt 0) {
      $pct = [math]::Round($delta / 4 * 100 / $cores, 1)
      $results += [PSCustomObject]@{ Name=$_.Name; Id=$_.Id; CPU_pct=$pct; Priority=$_.PriorityClass }
    }
  }
}
$results | Sort-Object CPU_pct -Descending | Select-Object -First 15 | Format-Table -AutoSize
