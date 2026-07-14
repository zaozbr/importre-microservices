$results = Get-ChildItem 'D:\roms\library\roms\psx' -Filter *.chd -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'Twisted|Ultraman' } | Select-Object Name
$results | Format-Table -AutoSize
