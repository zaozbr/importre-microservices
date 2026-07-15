$src = 'C:\teste'
$dst = 'D:\roms\library\roms\psx'

# Listar CHDs no destino e extrair seriais
$dstFiles = Get-ChildItem -Path $dst -Filter '*.chd' -ErrorAction SilentlyContinue
$dstSerials = @{}
foreach ($f in $dstFiles) {
  # Extrair serial do nome (formato ...-SLUS-00006.chd ou SLUS-00006.chd)
  if ($f.BaseName -match '([SC]{2}[A-Z]{2}-\d{3,5}(?:_\d)?)') {
    $serial = $matches[1]
    if (-not $dstSerials.ContainsKey($serial)) {
      $dstSerials[$serial] = $f.FullName
    }
  }
}
Write-Output "Seriais no destino: $($dstSerials.Count)"

# Processar cada CHD na origem
$srcFiles = Get-ChildItem -Path $src -Filter '*.chd' -ErrorAction SilentlyContinue
$moved = 0
$skipped = 0
$movedSerials = @()

foreach ($f in $srcFiles) {
  $serial = $f.BaseName
  if ($dstSerials.ContainsKey($serial)) {
    Write-Output "SKIP: $serial (ja existe: $($dstSerials[$serial]))"
    $skipped++
  } else {
    $destPath = Join-Path $dst $f.Name
    try {
      Move-Item -LiteralPath $f.FullName -Destination $destPath -Force -ErrorAction Stop
      Write-Output "MOVE: $serial -> $destPath"
      $moved++
      $movedSerials += $serial
    } catch {
      Write-Output "FAIL: $serial - $($_.Exception.Message)"
    }
  }
}

Write-Output ""
Write-Output "Resumo: $moved movidos, $skipped pulados (ja existiam)"

# Salvar lista de seriais movidos para remover da queue
$movedSerials | Out-File -FilePath 'F:\importre\logs\moved_chds.txt' -Encoding utf8
Write-Output "Seriais movidos salvos em F:\importre\logs\moved_chds.txt"
