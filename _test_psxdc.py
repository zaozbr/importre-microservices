"""Testa resolucao de nomes via psxdatacenter e outras fontes."""
import requests, re, json, sys

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def resolve_psxdatacenter(serial):
    """Tenta resolver nome via psxdatacenter.com"""
    # psxdatacenter organiza por regiao/letra/serial
    # JP: SLPS, SLPM, SCPS -> /games/j/S/SLPS-XXXXX.html
    # EU: SLES, SCES -> /games/p/S/SLES-XXXXX.html
    # US: SLUS, SCUS -> /games/u/S/SLUS-XXXXX.html
    region = 'j'
    if serial.startswith(('SLES', 'SCES')):
        region = 'p'
    elif serial.startswith(('SLUS', 'SCUS')):
        region = 'u'
    
    letter = serial[0]
    url = f'https://psxdatacenter.com/games/{region}/{letter}/{serial}.html'
    try:
        r = requests.get(url, timeout=15, headers=HEADERS)
        if r.status_code == 200:
            # Extrair titulo
            m = re.search(r'<title>(.*?)</title>', r.text, re.I|re.S)
            title = m.group(1).strip() if m else ''
            # Extrair nome do jogo (geralmente em <font> ou <h2>)
            for mm in re.finditer(r'<font[^>]*size=["\']?5["\']?[^>]*>(.*?)</font>', r.text, re.I|re.S):
                txt = re.sub(r'<[^>]+>', '', mm.group(1)).strip()
                if txt and len(txt) > 2:
                    return txt
            # Tentar h2
            for mm in re.finditer(r'<h2[^>]*>(.*?)</h2>', r.text, re.I|re.S):
                txt = re.sub(r'<[^>]+>', '', mm.group(1)).strip()
                if txt and len(txt) > 2:
                    return txt
            return title
    except Exception as e:
        print(f'  psxdatacenter erro: {e}')
    return None

def resolve_redump(serial):
    """Tenta resolver nome via redump.org"""
    # Redump tem uma lista de PSX
    url = f'http://redump.org/disc/quicksearch/{serial}'
    try:
        r = requests.get(url, timeout=15, headers=HEADERS, allow_redirects=True)
        if r.status_code == 200 and 'disc/' in r.url:
            # Extrair nome da pagina
            m = re.search(r'<title>(.*?)</title>', r.text, re.I|re.S)
            if m:
                title = m.group(1).strip()
                # Redump: "Disc Name (Region) - Redump"
                return title.split(' - ')[0].strip()
    except Exception as e:
        print(f'  redump erro: {e}')
    return None

def resolve_github(serial):
    """Busca por serial no GitHub via API de busca de codigo"""
    url = f'https://api.github.com/search/code?q={serial}+psx+in:file'
    try:
        r = requests.get(url, timeout=15, headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            data = r.json()
            items = data.get('items', [])
            for item in items[:3]:
                name = item.get('name', '')
                repo = item.get('repository', {}).get('full_name', '')
                print(f'    GitHub: {repo}/{name}')
        else:
            print(f'    GitHub status: {r.status_code}')
    except Exception as e:
        print(f'  github erro: {e}')
    return None

# Testar com os seriais pendentes
serials = [
    'SLPS-01224', 'SLPS-01190', 'SLPS-02060', 'SLPS-02016',
    'SLPS-00187', 'SLPS-08770', 'SLPS-01269',
    'SLPM-86129', 'SLPM-86922', 'SLPM-86796', 'SLPM-86880', 'SLPM-87255',
    'SLES-02758', 'SLES-01361', 'SLES-03515', 'SLES-01419',
    'SLES-01375', 'SLES-02838', 'SLES-02693', 'SLES-02631',
    'SLES-04047', 'SLES-01216',
]

print("=== RESOLUCAO DE NOMES ===")
results = {}
for s in serials:
    print(f'\n[{s}]')
    name = resolve_psxdatacenter(s)
    if name:
        print(f'  psxdatacenter: {name}')
        results[s] = name
    else:
        print(f'  psxdatacenter: NAO ENCONTRADO')
        # Tentar redump
        name2 = resolve_redump(s)
        if name2:
            print(f'  redump: {name2}')
            results[s] = name2

print(f"\n\n=== RESUMO ===")
print(f"Resolvidos: {len(results)}/{len(serials)}")
for s, n in results.items():
    print(f"  {s}: {n}")
