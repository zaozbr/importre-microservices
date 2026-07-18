# Matar model_host atual e reiniciar com DirectML (GPU)
$ErrorActionPreference = 'Stop'
$log = 'F:\importre\tools\model_host_gpu.log'
"[$(Get-Date)] Iniciando migracao para DirectML" | Out-File $log -Encoding utf8

# 1. Matar instancias existentes
$procs = Get-CimInstance Win32_Process -Filter "Name='model_host.exe'" -ErrorAction SilentlyContinue
foreach ($p in $procs) {
  "[$(Get-Date)] Matendo PID $($p.ProcessId): $($p.CommandLine)" | Out-File $log -Append -Encoding utf8
  try {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
    "[$(Get-Date)] PID $($p.ProcessId) morto" | Out-File $log -Append -Encoding utf8
  } catch {
    "[$(Get-Date)] Erro matando PID $($p.ProcessId): $_" | Out-File $log -Append -Encoding utf8
    # Tentar taskkill
    & taskkill /F /PID $p.ProcessId 2>&1 | Out-File $log -Append -Encoding utf8
  }
}

Start-Sleep -Seconds 2

# 2. Verificar se respawnou
$check = Get-CimInstance Win32_Process -Filter "Name='model_host.exe'" -ErrorAction SilentlyContinue
"[$(Get-Date)] Apos kill, instancias ativas: $($check.Count)" | Out-File $log -Append -Encoding utf8
foreach ($c in $check) {
  "[$(Get-Date)] Sobrevivente PID $($c.ProcessId): $($c.CommandLine)" | Out-File $log -Append -Encoding utf8
}

# 3. Iniciar nova instancia com DirectML
$modelPath = 'C:\Program Files\Avast Software\mlm\26.6181.39'
$exe = 'C:\Program Files\Avast Software\Avast\model_host.exe'

# Tentar --provider=directml primeiro
$args1 = "--model-name=QRDet --model-path=`"$modelPath`" --provider=directml"
"[$(Get-Date)] Tentando iniciar com: $args1" | Out-File $log -Append -Encoding utf8

try {
  $proc = Start-Process -FilePath $exe -ArgumentList $args1 -PassThru -WindowStyle Hidden -ErrorAction Stop
  Start-Sleep -Seconds 3
  $alive = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
  if ($alive) {
    "[$(Get-Date)] SUCESSO: model_host iniciado com DirectML, PID $($proc.Id)" | Out-File $log -Append -Encoding utf8
    "DONE directml $($proc.Id)" | Out-File $log -Append -Encoding utf8
    exit 0
  } else {
    "[$(Get-Date)] Processo com --provider=directml terminou imediatamente" | Out-File $log -Append -Encoding utf8
  }
} catch {
  "[$(Get-Date)] Falha com --provider=directml: $_" | Out-File $log -Append -Encoding utf8
}

# 4. Tentar --dml como flag
$args2 = "--model-name=QRDet --model-path=`"$modelPath`" --provider=cpu --dml"
"[$(Get-Date)] Tentando iniciar com: $args2" | Out-File $log -Append -Encoding utf8
try {
  $proc = Start-Process -FilePath $exe -ArgumentList $args2 -PassThru -WindowStyle Hidden -ErrorAction Stop
  Start-Sleep -Seconds 3
  $alive = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
  if ($alive) {
    "[$(Get-Date)] SUCESSO: model_host iniciado com --dml, PID $($proc.Id)" | Out-File $log -Append -Encoding utf8
    "DONE dml $($proc.Id)" | Out-File $log -Append -Encoding utf8
    exit 0
  } else {
    "[$(Get-Date)] Processo com --dml terminou imediatamente" | Out-File $log -Append -Encoding utf8
  }
} catch {
  "[$(Get-Date)] Falha com --dml: $_" | Out-File $log -Append -Encoding utf8
}

# 5. Tentar --provider=dml
$args3 = "--model-name=QRDet --model-path=`"$modelPath`" --provider=dml"
"[$(Get-Date)] Tentando iniciar com: $args3" | Out-File $log -Append -Encoding utf8
try {
  $proc = Start-Process -FilePath $exe -ArgumentList $args3 -PassThru -WindowStyle Hidden -ErrorAction Stop
  Start-Sleep -Seconds 3
  $alive = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
  if ($alive) {
    "[$(Get-Date)] SUCESSO: model_host iniciado com --provider=dml, PID $($proc.Id)" | Out-File $log -Append -Encoding utf8
    "DONE provider-dml $($proc.Id)" | Out-File $log -Append -Encoding utf8
    exit 0
  }
} catch {
  "[$(Get-Date)] Falha com --provider=dml: $_" | Out-File $log -Append -Encoding utf8
}

"[$(Get-Date)] FALHA: nenhuma variacao funcionou" | Out-File $log -Append -Encoding utf8
"FAILED" | Out-File $log -Append -Encoding utf8
