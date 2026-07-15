$dir = "D:\roms\library\roms\psx"
$dryRun = $false  # Set to $false to actually rename

# ============================================================
# MANUAL SERIAL MAPPING (corrected from Redump database)
# ============================================================
$serialMap = @{
    # Genuine games (63)
    "19-ji-03-pun-Ueno-Hatsu-Yakou-Ressha.chd" = "SLPS-01865"
    "Alex-Fergusons-Player-Manager-2002.chd" = "SLES-03775"
    "All-Star-Tennis-2000.chd" = "SLES-02764"
    "Angel-Graffiti-Anata-he-no-Profile.chd" = "SLPS-00163"
    "Aqua-GT.chd" = "SLES-03390"
    "Baldy-Land.chd" = "SLPS-01074"
    "Battle-Arena-Toshinden.chd" = "SCES-00002"
    "BLADE.chd" = "SLES-03213"
    "Block-Buster.chd" = "SLES-04067"
    "BursTrick-Wake-Boarding.chd" = "SLES-03338"
    "Card-Shark.chd" = "SLES-03206"
    "Chaos-Break.chd" = "SLPM-86363"
    "Cinema-Eikaiwa-Series-Dai-1-dan-Tengoku-ni-Ikenai-Papa.chd" = "SLPM-86565"
    "Clock-Tower-The-First-Fear.chd" = "SLPS-00917"
    "Command-Conquer-Alarmstufe-Rot.chd" = "SLES-01007"
    "Conveni-Portable-The.chd" = "SLPS-00782"
    "CT-Special-Forces.chd" = "SLES-03986"
    "Culdcept-Expansion.chd" = "SLPM-86223"
    "Dance-Dance-Revolution-Extra-Mix.chd" = "SLPM-86831"
    "DX-Jinsei-Game.chd" = "SLPS-00155"
    "Final-Fantasy-Extra-Collection.chd" = "SLPM-80073"
    "Final-Fantasy-V.chd" = "SCPS-45214"
    "Firebugs.chd" = "SCES-03884"
    "Gensou-Suiko-Gaiden-Vol1-Harmonia-no-Kenshi.chd" = "SLPM-86637"
    "Goiken-Muyou-II.chd" = "SLPS-01542"
    "Golden-Goal-98.chd" = "SLES-01222"
    "Gouketuji-Ichizoku-2-Chottodake-Saikyou-Densetsu.chd" = "SLPS-00104"
    "Jet-de-Go-Lets-Go-by-Airliner.chd" = "SLPM-86323"
    "Jumping-Flash-Aloha-Danshaku-Funky-Daisakusen-no-Maki.chd" = "SCPS-10007"
    "Kids-Station-Bokura-to-Asobou-Ultraman-TV.chd" = "SLPS-02873"
    "Kururin-Pa.chd" = "SLPS-00066"
    "Linda-3-Cube-Again.chd" = "SCPS-10039"
    "Medarot-R-Parts-Collection.chd" = "SLPS-02635"
    "Megami-Ibunroku-Persona-Be-Your-True-Mind.chd" = "SLPS-91029"
    "Planet-Laika-Kasei-Mokushiroku.chd" = "SLPM-86264"
    "Pro-Logic-Mah-Jong-Hai-Shin.chd" = "SLPM-86018"
    "Re-Volt.chd" = "SLUS-00851"
    "Sentinel-Returns.chd" = "SLES-01051"
    "Simple-1500-Series-Vol-14-The-Block-Kuzushi.chd" = "SLPS-02450"
    "Simple-1500-Series-Vol005-The-Igo.chd" = "SLPS-02441"
    "Simple-1500-Series-Vol074-The-Horror-Mystery-Sangekikan-Kebin-Hakushaku-no-Fukkatu.chd" = "SLPM-86901"
    "Simple-1500-Series-Vol078-The-Zero-Yon.chd" = "SLPM-86712"
    "Ten-Pin-Alley.chd" = "SLES-00534"
    "Tenshi-Doumei.chd" = "SLPS-01228"
    "The-Great-Battle-VI.chd" = "SLPS-00719"
    "Thunder-Storm-Road-Blaster.chd" = "SLPS-00095"
    "Tilt.chd" = "SLES-00152"
    "Total-Drivin.chd" = "SLES-00307"
    "Transport-Tycoon-3D-Sl-Kara-Hajimeyou.chd" = "SLPS-00694"
    "Twin-Goddesses.chd" = "SLPS-00018"
    "Uchuu-Seibutsu-Furopon-kun-P.chd" = "SLPS-00032"
    "Vandal-Hearts-II.chd" = "SLUS-00940"
    "Victory-Boxing-Champion-Edition.chd" = "SLES-00180"
    "Warhammer-Shadow-of-the-Horned-Rat.chd" = "SLES-00028"
    "Warhawk-The-Red-Mercury-Missions.chd" = "SCES-00062"
    "World-Soccer-Jikkyou-Winning-Eleven-4.chd" = "SLPM-86291"
    "Yaku-Yuujou-Dangi.chd" = "SLPS-00152"
    "Yeh-Yeh-Tennis.chd" = "SLES-02272"
    
    # Spaces/parens games (16)
    "3D Lemmings (Japan).chd" = "SIPS-60002"
    "Aqua GT (Europe).chd" = "SLES-03390"
    "Card Shark (Europe).chd" = "SLES-03206"
    "Crash Bandicoot Racing (Japan).chd" = "SCPS-10118"
    "Elan (Japan).chd" = "SLPS-01925"
    "Final Fantasy Extra Collection (Japan).chd" = "SLPM-80073"
    "Grand Theft Auto - Mission Pack #1 - London 1969 (Europe).chd" = "SLES-01714"
    "Nazo-Oh (Japan).chd" = "SLPS-00447"
    "Re-Volt (Europe).chd" = "SLES-01973"
    "Tony Hawk's Pro Skater 3 (Europe).chd" = "SLES-03645"
    "Twin Goddesses (Japan).chd" = "SLPS-00018"
    "V2000 (Europe).chd" = "SLES-00545"
    "Vigilante 8 - 2nd Battle (Japan).chd" = "SLPS-02615"
    "Winning Post 3 (Japan).chd" = "SLPS-01263"
    "Wizardry - New Age of Llylgamyn (Japan) (En,Ja).chd" = "SLPS-02349"
    
    # Incomplete serials (2)
    "Baldy-Land-SLPS-010.chd" = "SLPS-01074"
    "Slotter-Mania-2-Chounetsu-30-Hana-Hana-And-Kingbary-And-Hai-Hai-Siesta-SLPS-033.chd" = "SLPS-03349"
    
    # ESPM non-standard serials (keep as-is, just clean name)
    "Iceman-Digital-Playstage-ESPM-70001.chd" = "ESPM-70001"
    "Robots-Video-Alchemy.chd" = "ESPM-70002"
}

# ============================================================
# Title Case function (same as batch1)
# ============================================================
function ToTitleCase($s) {
    # Uppercase acronyms and roman numerals
    $acronyms = @('3D','II','III','IV','V','VI','VII','VIII','IX','CT','DX','GT','TV','SL','ESPM','PSX','NSC','NGC','NBA','NFL','NHL','F1','WRC','RPG','SRPG','MMO','TBS','RTS','FPS','VS','UI','AI','PC','CD','DVD','HD','VR','AR','OS','API','URL','HTTP','XML','JSON','CSV','PDF','SQL','SSH','TCP','UDP','DNS','DHCP','IP','MAC','LAN','WAN','VPN','VPS','SSD','HDD','RAM','CPU','GPU','ROM','ISO','BIN','CUE','CHD','R','S','T','X','Z','P')
    # Words that should be lowercase in the middle of a title
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
            # Words starting with digits - keep as-is
            $result += $w
        } elseif (-not $isFirst -and -not $isLast -and $lowerWords -contains $w.ToLower()) {
            # Lowercase words in the middle of the title
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

# ============================================================
# Clean filename function
# ============================================================
function Clean-Name($name) {
    # Remove .chd extension
    $n = $name -replace '\.chd$', ''
    
    # Remove region tags (Japan), (Europe), (USA), (En,Ja), etc.
    $n = $n -replace '\s*\([^)]*\)', ''
    
    # Remove any existing serial from the name (incomplete or complete)
    $n = $n -replace '-(SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE|ESPM|UNL)-\d{1,5}$', ''
    $n = $n -replace '-(SLES|SLUS|SLPS|SLPM|SCPS|SCES|SCUS|SLED|SCED|SIPS|SLKA|PAPX|PCPX|SCAJ|SCAR|SCPM|SLPH|SLKO|SLHI|SABE|ESPM|UNL)-\d{1,5}-DUS-\d{1,5}$', ''
    
    # Replace spaces with dashes
    $n = $n -replace ' ', '-'
    
    # Replace special characters
    $n = $n -replace '/', '-'
    $n = $n -replace ':', '-'
    $n = $n -replace '#', '-'
    $n = $n -replace "'", ''
    $n = $n -replace '!', ''
    $n = $n -replace ',', ''
    $n = $n -replace '\.', ''
    $n = $n -replace '&', 'and'
    $n = $n -replace '\+', 'and'
    
    # Remove multiple dashes
    $n = $n -replace '-+', '-'
    
    # Remove leading/trailing dashes
    $n = $n -replace '^-', ''
    $n = $n -replace '-$', ''
    
    # Apply Title Case to the full name (convert dashes to spaces, title case, back to dashes)
    $spaceName = $n -replace '-', ' '
    $titled = ToTitleCase $spaceName
    $n = $titled -replace ' ', '-'
    
    return $n
}

# ============================================================
# Main renaming logic
# ============================================================
$renamed = 0
$skipped = 0
$notFound = 0
$logFile = "F:\importre\logs\rename_batch3_log.txt"
$logEntries = @()

Write-Host "=== BATCH 3: Renaming files with web-looked-up serials ==="
Write-Host "Mode: $(if ($dryRun) { 'DRY RUN' } else { 'ACTUAL RENAME' })"
Write-Host ""

foreach ($entry in $serialMap.GetEnumerator()) {
    $fileName = $entry.Key
    $serial = $entry.Value
    $filePath = Join-Path $dir $fileName
    
    if (-not (Test-Path $filePath)) {
        Write-Host "[SKIP] Not found: $fileName"
        $notFound++
        continue
    }
    
    # Clean the name
    $cleanName = Clean-Name $fileName
    
    # Build new name
    $newName = "${cleanName}-${serial}.chd"
    $newPath = Join-Path $dir $newName
    
    # Check if already has the correct name
    if ($fileName -ceq $newName) {
        Write-Host "[OK] Already correct: $fileName"
        $skipped++
        continue
    }
    
    # Check if target already exists
    if (Test-Path $newPath) {
        # Add (1) suffix
        $newName = "${cleanName}-${serial}(1).chd"
        $newPath = Join-Path $dir $newName
        if (Test-Path $newPath) {
            $newName = "${cleanName}-${serial}(2).chd"
            $newPath = Join-Path $dir $newName
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
Write-Host "=== BATCH 3 COMPLETE ==="
Write-Host "Mode: $(if ($dryRun) { 'DRY RUN' } else { 'ACTUAL' })"
Write-Host "Would rename / Renamed: $renamed"
Write-Host "Already correct: $skipped"
Write-Host "Not found: $notFound"

# Save log
$logEntries | Out-File $logFile -Encoding UTF8
Write-Host "Log saved to: $logFile"
