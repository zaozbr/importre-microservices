import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0'})
s.cookies.update({
    'logged-in-sig': '1815366851%201783830851%20ezlNQhrkcwCjOxmlnfRurVC8vSzynRSi%2BeJKI33cQ%2F%2BRgy6docXmL7yZL72iEwHVWma1JlBtC6PxhrVbCrOwvzb1R4yYMT2Gq1%2BqtwRVyoXSAFnmRiwrW92b7wsKmXz4qMr1PbDfFptM4HQ7Bdu9kOaPv98Ru13ggcdSRtbM1r5LO27wHMI5KRJ2PWNTx3vGSLuCw%2BuDaKyT8lpvUy2RObNIO4kLMi0wgGcU5xGPu4mFaOpYt5CPLiygH9%2BpS2a9NxPVAMGyV7X8GEQ3OVPyEzgHVnXyqUMixx8Y4pnjO5X1Wf77d%2BiGCPU9w8VR9YmG1AXaD%2Bh%2FCywSV3zORtwwDQ%3D%3D',
    'logged-in-user': 'zaozao2%40gmail.com',
})

# Testar varias colecoes
for coll in ['psx-chd-roms-s', 'psx_samsho3j', 'chd_psx', 'psx-ntscj-chd-zstd', 'psx_zuttoiss']:
    r = s.get(f'http://archive.org/metadata/{coll}', timeout=15)
    if r.status_code == 200:
        data = r.json()
        files = data.get('files', [])
        rom_files = [f for f in files if any(f.get('name', '').lower().endswith(ext) for ext in ('.bin', '.cue', '.iso', '.img', '.zip', '.7z', '.rar', '.chd', '.ecm', '.pbp'))]
        print(f'{coll}: {len(files)} files, {len(rom_files)} ROMs')
        for f in rom_files[:3]:
            name = f.get('name', '?')
            size = f.get('size', '?')
            print(f'  {name} ({size})')
    else:
        print(f'{coll}: HTTP {r.status_code}')
