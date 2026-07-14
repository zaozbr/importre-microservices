import subprocess, os, re, uuid

CHDMAN = r'F:\importre\chdman.exe'
TEMP = r'F:\chd_temp'
PSX = r'D:\roms\library\roms\PSX'

def test_file(filename):
    chd_path = os.path.join(PSX, filename)
    uid = uuid.uuid4().hex[:8]
    cue = os.path.join(TEMP, f'_rn_{uid}.cue')
    binf = os.path.join(TEMP, f'_rn_{uid}.bin')
    
    print(f'\n=== Testing: {filename} ===')
    r = subprocess.run([CHDMAN, 'extractcd', '-i', chd_path, '-o', cue, '-ob', binf, '-f'],
                       capture_output=True, timeout=180)
    print('RC:', r.returncode)
    
    if os.path.exists(binf):
        sz = os.path.getsize(binf)
        print('BIN size:', sz)
        
        # Read entire file
        with open(binf, 'rb') as f:
            data = f.read()
        
        # Search for all serial patterns
        pat1 = re.findall(rb'(SLUS|SLES|SLPS|SLPM|SCPS|SCES|SCUS|SLED)[-_](\d{5})', data, re.I)
        pat2 = re.findall(rb'(SLUS|SLES|SLPS|SLPM|SCPS|SCES|SCUS|SLED)(\d{5})', data, re.I)
        pat3 = re.findall(rb'(SLUS|SLES|SLPS|SLPM|SCPS|SCES|SCUS|SLED)[_\.](\d{3})[_\.](\d{2})', data, re.I)
        print('With separator:', pat1[:10])
        print('Without separator:', pat2[:10])
        print('Split format:', pat3[:10])
        
        # Search for BOOT=
        boot_match = re.findall(rb'BOOT\s*=\s*[^\r\n]{0,80}', data, re.I)
        print('BOOT strings:', [b.decode('ascii', errors='replace')[:80] for b in boot_match[:5]])
        
        # Search for cdrom:
        cdrom_match = re.findall(rb'cdrom:[^\r\n\0]{0,80}', data, re.I)
        print('cdrom strings:', [b.decode('ascii', errors='replace')[:80] for b in cdrom_match[:5]])
        
        # Search for SYSTEM.CNF
        sys_match = re.findall(rb'SYSTEM\.[Cc][Nn][Ff]', data)
        print('SYSTEM.CNF found:', len(sys_match), 'times')
        
        # Dump a region around any "SL" pattern
        for m in re.finditer(rb'(SLUS|SLES|SLPS|SLPM|SCPS|SCES|SCUS|SLED)', data, re.I):
            start = max(0, m.start()-20)
            end = min(len(data), m.end()+30)
            context = data[start:end]
            print(f'  Context at {m.start()}: {context}')
            break  # just first

    for p in [cue, binf]:
        try:
            if os.path.exists(p):
                os.chmod(p, 0o777)
                os.remove(p)
        except:
            pass

# Test with a file that already has serial (to verify extraction works)
test_file('007-Racing-SLUS-01300.chd')
# Test with a file without serial
test_file('19-ji-03-pun-Ueno-Hatsu-Yakou-Ressha.chd')
