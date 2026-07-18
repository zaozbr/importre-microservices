import requests, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Completely fresh session, no cookies
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
})

# Try direct download without visiting game page first
print("Test 1: Direct download without visiting game page")
r = session.get('https://dl3.vimm.net/?mediaId=5252', stream=True, timeout=60)
print(f'  Status: {r.status_code}, Content-Type: {r.headers.get("content-type","?")}')

if r.status_code == 429:
    # Try with curl
    print("\nTest 2: Trying with curl")
    import subprocess
    result = subprocess.run([
        'curl', '-sI', '-L',
        '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        '-H', 'Referer: https://vimm.net/vault/6455',
        'https://dl3.vimm.net/?mediaId=5252'
    ], capture_output=True, text=True, timeout=30)
    print(f'  curl result: {result.stdout[:500]}')
    print(f'  curl stderr: {result.stderr[:200]}')
    
    # Check if it's a temporary block
    print("\n  The server is rate limiting by IP. Need to wait longer.")
    print("  Let's check the Retry-After header if present")
    r2 = session.get('https://dl3.vimm.net/?mediaId=5252', stream=False, timeout=30)
    print(f'  Headers: {dict(r2.headers)}')
