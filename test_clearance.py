import requests

# Try different URL formats for clearancebin item
identifier = 'vigilante-8-play-station-ps-1-psone-p-sx'
filename = 'Vigilante 8.cue'  # Small file to test

urls = [
    f'https://archive.org/download/{identifier}/{filename}',
    f'https://archive.org/download/{identifier}/{filename.replace(" ", "%20")}',
    f'https://ia803207.us.archive.org/download/{identifier}/{filename.replace(" ", "%20")}',
    f'https://ia803207.us.archive.org/{identifier}/{filename.replace(" ", "%20")}',
    f'https://archive.org/details/{identifier}',
]

for url in urls:
    try:
        r = requests.head(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True)
        print(f'{r.status_code} | {url[:80]}')
    except Exception as e:
        print(f'ERR | {url[:80]} | {e}')

# Also try the paq9a file from psxrip
print('\n--- psxrip ---')
filename2 = 'Vigilante 8 [NTSC-U] (SLUS00510).paq9a'
urls2 = [
    f'https://archive.org/download/psxrip/{filename2.replace(" ", "%20")}',
    f'https://archive.org/download/psxrip/{filename2.replace(" ", "+")}',
]
for url in urls2:
    try:
        r = requests.head(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'}, allow_redirects=True)
        print(f'{r.status_code} | {url[:80]}')
    except Exception as e:
        print(f'ERR | {url[:80]} | {e}')
