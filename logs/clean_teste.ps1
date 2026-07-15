Remove-Item "C:\teste\*" -Force -Recurse -Confirm:$false -ErrorAction SilentlyContinue
$remaining = Get-ChildItem "C:\teste" -Force -Recurse -ErrorAction SilentlyContinue
if ($remaining) {
  Write-Output "Restam $($remaining.Count) itens:"
  $remaining | ForEach-Object { Write-Output "  $($_.FullName)" }
} else {
  Write-Output "C:\teste limpo completamente"
}
