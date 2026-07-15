$dir = 'D:\roms\library\roms\psx'

$cases = @(
    @('SCUS-94952.chd', 'PlayStation-Picks-SCUS-94952.chd'),
    @('SLES-00217.chd', 'Sampras-Extreme-Tennis-SLES-00217.chd'),
    @('SLES-03206.chd', 'Card-Shark-SLES-03206.chd')
)

foreach ($entry in $cases) {
    $oldFile = $entry[0]
    $newFile = $entry[1]
    $oldPath = Join-Path $dir $oldFile
    $newPath = Join-Path $dir $newFile

    Write-Output "--- $oldFile ---"
    if (Test-Path $oldPath) {
        $oldItem = Get-Item $oldPath
        Write-Output "  Origem existe: $oldFile ($($oldItem.Length) bytes)"
    } else {
        Write-Output "  Origem NAO existe: $oldFile"
    }

    if (Test-Path $newPath) {
        $newItem = Get-Item $newPath
        Write-Output "  Destino existe: $newFile ($($newItem.Length) bytes)"
    } else {
        Write-Output "  Destino NAO existe: $newFile"
    }
}
