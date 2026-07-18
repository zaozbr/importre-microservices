import subprocess, sys, time, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Test curl download
print("Testing curl download from dl3.vimm.net...")

# First visit game page with curl to get cookies
result = subprocess.run([
    'curl', '-s', '-c', r'F:\downloads\psx_faltantes\test_cookies.txt',
    '-o', 'nul',
    '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'https://vimm.net/vault/6455'
], capture_output=True, text=True, timeout=30)
print(f'Game page: {result.returncode}')

time.sleep(5)

# Now try download with curl using cookies
result2 = subprocess.run([
    'curl', '-sI', '-L',
    '-b', r'F:\downloads\psx_faltantes\test_cookies.txt',
    '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    '-H', 'Referer: https://vimm.net/vault/6455',
    'https://dl3.vimm.net/?mediaId=5252'
], capture_output=True, text=True, timeout=30)
print(f'Download headers:\n{result2.stdout[:500]}')
