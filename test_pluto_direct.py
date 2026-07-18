import requests, time

# Try accessing pluto.romulation.net directly to see if it's an IP-level block
print("Test 1: Direct GET to pluto.romulation.net")
try:
    r = requests.get('https://pluto.romulation.net/', timeout=10,
                     headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    print(f"  Status: {r.status_code}, Content: {r.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")

# Test 2: Try a HEAD request to a pluto file URL
print("\nTest 2: HEAD request to pluto file URL")
try:
    r = requests.head('https://pluto.romulation.net/files/guest/test', timeout=10,
                      headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    print(f"  Status: {r.status_code}, Headers: {dict(r.headers)}")
except Exception as e:
    print(f"  Error: {e}")

# Test 3: Check DNS resolution
print("\nTest 3: DNS resolution")
import socket
try:
    ips = socket.getaddrinfo('pluto.romulation.net', 443)
    for ip in ips[:3]:
        print(f"  {ip[4]}")
except Exception as e:
    print(f"  Error: {e}")

# Test 4: Try with explicit Connection: close header
print("\nTest 4: With Connection: close header")
try:
    r = requests.get('https://pluto.romulation.net/', timeout=10,
                     headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                              'Connection': 'close'})
    print(f"  Status: {r.status_code}, Content: {r.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")
