# Migrar QRDet de CPU para DirectML (GPU)
$ErrorActionPreference = 'Continue'
$log = 'F:\importre\tools\qrdet_to_gpu.log'
function Log($msg) { "[$(Get-Date)] $msg" | Out-File $log -Append -Encoding utf8; Write-Host $msg }

Log "=== Iniciando migracao QRDet CPU -> DirectML ==="

# 1. Listar servicos Avast
Log "=== Servicos Avast ==="
$svc = Get-Service | Where-Object { $_.Name -match 'avast' -or $_.DisplayName -match 'Avast' }
$svc | Select-Object Name, DisplayName, Status, StartType | Format-Table -AutoSize | Out-File $log -Append -Encoding utf8
$svc | Format-Table Name, DisplayName, Status, StartType -AutoSize

# 2. Backup do valor atual
$regPath = 'HKLM:\SOFTWARE\Avast Software\Avast\properties\MediaScan\Settings'
$current = (Get-ItemProperty $regPath -ErrorAction SilentlyContinue).LastQRdetEP
Log "Valor atual de LastQRdetEP: $current"

# 3. Mudar registry para directml
try {
  Set-ItemProperty -Path $regPath -Name 'LastQRdetEP' -Value 'directml' -Type String -ErrorAction Stop
  Log "Registry atualizada: LastQRdetEP = directml"
  $verify = (Get-ItemProperty $regPath -ErrorAction SilentlyContinue).LastQRdetEP
  Log "Verificacao: LastQRdetEP = $verify"
} catch {
  Log "ERRO ao mudar registry: $_"
}

# 4. Reiniciar o servico principal Avast
# O servico principal costuma ser 'avast! Antivirus' ou 'Avast Antivirus'
$mainSvc = $svc | Where-Object { $_.DisplayName -match 'Antivirus' -or $_.Name -match 'avast' } | Select-Object -First 1
if ($mainSvc) {
  Log "Reiniciando servico: $($mainSvc.Name) ($($mainSvc.DisplayName))"
  try {
    Restart-Service -Name $mainSvc.Name -Force -ErrorAction Stop
    Log "Servico reiniciado com sucesso"
  } catch {
    Log "Restart-Service falhou: $_. Tentando net stop/start..."
    & net stop $mainSvc.Name 2>&1 | Out-File $log -Append -Encoding utf8
    Start-Sleep -Seconds 3
    & net start $mainSvc.Name 2>&1 | Out-File $log -Append -Encoding utf8
  }
} else {
  Log "Nenhum servico Avast encontrado para reiniciar"
}

# 5. Aguardar e verificar model_host
Start-Sleep -Seconds 8
Log "=== Verificando model_host apos restart ==="
$mh = Get-CimInstance Win32_Process -Filter "Name='model_host.exe'" -ErrorAction SilentlyContinue
if ($mh) {
  foreach ($p in $mh) {
    Log "PID $($p.ProcessId): $($p.CommandLine)"
  }
} else {
  Log "Nenhum model_host rodando apos restart (pode ser lazy-start)"
}

# 6. Verificar GPU usage
Log "=== GPU apos migracao ==="
& nvidia-smi 2>&1 | Out-File $log -Append -Encoding utf8

Log "=== Fim ==="
