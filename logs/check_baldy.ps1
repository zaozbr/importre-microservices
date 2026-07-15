Get-ChildItem "D:\roms\library\roms\psx\Baldy-Land*" | ForEach-Object {
    Write-Host $_.Name
}
