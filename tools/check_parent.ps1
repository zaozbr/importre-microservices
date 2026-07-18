$pid_target = 21008
$proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pid_target"
if ($proc) {
  $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ParentProcessId)"
  Write-Host "=== Processo alvo ==="
  Write-Host "PID: $($proc.ProcessId) | Name: $($proc.Name)"
  Write-Host "CommandLine: $($proc.CommandLine)"
  Write-Host ""
  Write-Host "=== Processo pai ==="
  if ($parent) {
    Write-Host "PID: $($parent.ProcessId) | Name: $($parent.Name)"
    Write-Host "CommandLine: $($parent.CommandLine)"
  } else {
    Write-Host "Pai nao encontrado (ja terminou)"
  }
} else {
  Write-Host "Processo $pid_target nao existe mais"
}

Write-Host ""
Write-Host "=== Todos os model_host ativos ==="
Get-CimInstance Win32_Process -Filter "Name='model_host.exe'" | Select-Object ProcessId, ParentProcessId, CommandLine | Format-List
