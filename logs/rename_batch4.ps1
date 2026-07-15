$dir = "D:\roms\library\roms\psx"
$dryRun = $false

# ============================================================
# Title Case function (same as batch3)
# ============================================================
function ToTitleCase($s) {
    $acronyms = @('3D','II','III','IV','V','VI','VII','VIII','IX','CT','DX','GT','TV','SL','ESPM','PSX','NSC','NGC','NBA','NFL','NHL','F1','WRC','RPG','SRPG','MMO','TBS','RTS','FPS','VS','UI','AI','PC','CD','DVD','HD','VR','AR','OS','API','URL','HTTP','XML','JSON','CSV','PDF','SQL','SSH','TCP','UDP','DNS','DHCP','IP','MAC','LAN','WAN','VPN','VPS','SSD','HDD','RAM','CPU','GPU','ROM','ISO','BIN','CUE','CHD','R','S','T','X','Z','P')
    $lowerWords = @('of','to','in','on','at','by','for','and','or','the','is','as','no','de','es','la','el','un','le','da','du','di','il','na','wa','en','et','it','an','up','so','vs','he','ni','wo','ga','mo','ya','yo','ne','ku','kara','yori','made','hodo','dake','bakari')

    $words = $s -split ' '
    $result = @()
    $wordIdx = 0
    foreach ($w in $words) {
        $upper = $w.ToUpper()
        $isFirst = ($wordIdx -eq 0)
        $isLast = ($wordIdx -eq $words.Count - 1)

        if ($acronyms -contains $upper) {
            $result += $upper
        } elseif ($w -match '^\d') {
            $result += $w
        } elseif (-not $isFirst -and -not $isLast -and $lowerWords -contains $w.ToLower()) {
            $result += $w.ToLower()
        } else {
            if ($w.Length -gt 0) {
                $result += $w.Substring(0,1).ToUpper() + $w.Substring(1).ToLower()
            }
        }
        $wordIdx++
    }
    return ($result -join ' ')
}

function Clean-Name($name) {
    $n = $name -replace '\.chd$', ''
    $n = $n -replace '\s*\([^)]*\)', ''
    $n = $n -replace ' ', '-'
    $n = $n -replace '/', '-'
    $n = $n -replace ':', '-'
    $n = $n -replace '#', '-'
    $n = $n -replace "'", ''
    $n = $n -replace '!', ''
    $n = $n -replace ',', ''
    $n = $n -replace '\.', ''
    $n = $n -replace '&', 'and'
    $n = $n -replace '\+', 'and'
    $n = $n -replace '-+', '-'
    $n = $n -replace '^-', ''
    $n = $n -replace '-$', ''
    
    $spaceName = $n -replace '-', ' '
    $titled = ToTitleCase $spaceName
    $n = $titled -replace ' ', '-'
    return $n
}

# ============================================================
# Serial -> Game name mapping from Redump
# ============================================================
$renameMap = @{
    "SLES-00314.chd" = @{Serial="SLES-00314"; Name="Monster Trucks"}
    "SLES-00573.chd" = @{Serial="SLES-00573"; Name="La Cite des Enfants Perdus"}
    "SLES-00590.1.chd" = @{Serial="SLES-00590"; Name="Midnight Run - Road Fighter 2"}
    "SLES-01266.1.chd" = @{Serial="SLES-01266"; Name="Coupe du Monde 98"}
    "SLES-01416.chd" = @{Serial="SLES-01416"; Name="Asterix"}
    "SLES-01597.1.chd" = @{Serial="SLES-01597"; Name="Egypte 1156 AV JC - L Enigme de la Tombe Royale"}
    "SLES-01597.chd" = @{Serial="SLES-01597"; Name="Egypte 1156 AV JC - L Enigme de la Tombe Royale"}
    "SLES-01939.1.chd" = @{Serial="SLES-01939"; Name="Ruff and Tumble"}
    "SLES-02375.chd" = @{Serial="SLES-02375"; Name="007 - Demain ne Meurt Jamais"}
    "SLES-03990.chd" = @{Serial="SLES-03990"; Name="Extreme Ghostbusters - the Ultimate Invasion"}
    "SLES-10973.chd" = @{Serial="SLES-10973"; Name="Resident Evil 2 - Disc2"}
    "SLES-11881.chd" = @{Serial="SLES-11881"; Name="Capcom Generations - Disc2 - Chronicles of Arthur"}
    "SLPM-87175.1.chd" = @{Serial="SLPM-87175"; Name="The Dog Master"}
    "SCES-01707.1.chd" = @{Serial="SCES-01707"; Name="Star Ixiom"}
    "NBA-Power-Dunkers-3-SLUS-004550.chd" = @{Serial="SLPM-86060"; Name="NBA Power Dunkers 3"}
}

$renamed = 0
$skipped = 0
$notFound = 0
$logFile = "F:\importre\logs\rename_batch4_log.txt"
$logEntries = @()

Write-Host "=== BATCH 4: Renaming serial-only files ==="
Write-Host "Mode: $(if ($dryRun) { 'DRY RUN' } else { 'ACTUAL RENAME' })"
Write-Host ""

foreach ($entry in $renameMap.GetEnumerator()) {
    $fileName = $entry.Key
    $serial = $entry.Value.Serial
    $gameName = $entry.Value.Name
    $filePath = Join-Path $dir $fileName
    
    if (-not (Test-Path $filePath)) {
        Write-Host "[SKIP] Not found: $fileName"
        $notFound++
        continue
    }
    
    # Clean the game name
    $cleanName = Clean-Name $gameName
    
    # Build new name
    $newName = "${cleanName}-${serial}.chd"
    $newPath = Join-Path $dir $newName
    
    # Check if target already exists
    if (Test-Path $newPath) {
        $newName = "${cleanName}-${serial}(1).chd"
        $newPath = Join-Path $dir $newName
        if (Test-Path $newPath) {
            $newName = "${cleanName}-${serial}(2).chd"
            $newPath = Join-Path $dir $newName
            if (Test-Path $newPath) {
                $newName = "${cleanName}-${serial}(3).chd"
                $newPath = Join-Path $dir $newName
            }
        }
    }
    
    Write-Host "[RENAME] $fileName -> $newName"
    $logEntries += "$fileName|$newName|$serial"
    
    if (-not $dryRun) {
        try {
            Rename-Item -LiteralPath $filePath -NewName $newName -ErrorAction Stop
            $renamed++
        } catch {
            Write-Host "  ERROR: $($_.Exception.Message)"
            $logEntries[-1] += "|ERROR: $($_.Exception.Message)"
        }
    } else {
        $renamed++
    }
}

Write-Host ""
Write-Host "=== BATCH 4 COMPLETE ==="
Write-Host "Mode: $(if ($dryRun) { 'DRY RUN' } else { 'ACTUAL' })"
Write-Host "Renamed: $renamed"
Write-Host "Not found: $notFound"

$logEntries | Out-File $logFile -Encoding UTF8
Write-Host "Log saved to: $logFile"
