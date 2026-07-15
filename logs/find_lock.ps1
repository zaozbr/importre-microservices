Get-Process | ForEach-Object {
  try {
    $mods = $_.Modules | Where-Object { $_.FileName -like '*\teste\*' }
    if ($mods) { Write-Output "$($_.Name) PID=$($_.Id)" }
  } catch {}
}
