$bytes = [System.IO.File]::ReadAllBytes('C:\Program Files\Avast Software\Avast\model_host.exe')
$txt = [System.Text.Encoding]::ASCII.GetString($bytes)
$providers = [regex]::Matches($txt, '--[a-z_]+') | ForEach-Object { $_.Value } | Sort-Object -Unique
Write-Host "=== Flags --xxx encontradas ==="
$providers
Write-Host ""
Write-Host "=== Strings com 'provider' ==="
[regex]::Matches($txt, '[a-zA-Z_]*provider[a-zA-Z_]*') | ForEach-Object { $_.Value } | Sort-Object -Unique
Write-Host ""
Write-Host "=== Strings com 'cuda/tensorrt/directml/gpu/onnxrt' ==="
[regex]::Matches($txt, '[a-zA-Z_]*(cuda|tensorrt|directml|gpu|onnxruntime|onnxrt)[a-zA-Z_]*', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase) | ForEach-Object { $_.Value } | Sort-Object -Unique
