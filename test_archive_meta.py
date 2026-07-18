import requests, json

# Check metadata of psx_vigil8a to see where the serial is stored
identifier = 'psx_vigil8a'
url = f'https://archive.org/metadata/{identifier}'
r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
data = r.json()

# Print metadata
meta = data.get('metadata', {})
print("=== Metadata fields ===")
for k, v in meta.items():
    if isinstance(v, str) and len(v) < 200:
        print(f"  {k}: {v}")

# Check collection
print(f"\n=== Collection ===")
print(f"  {meta.get('collection', 'N/A')}")

# Check if there's a description with serial
desc = meta.get('description', '')
print(f"\n=== Description (first 500 chars) ===")
print(desc[:500] if desc else "N/A")
