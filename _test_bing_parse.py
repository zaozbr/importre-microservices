import requests
from urllib.parse import quote_plus
import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from _web_discovery_subagent import extract_bing_domains

q = '"psx roms" download'
url = f"https://www.bing.com/search?q={quote_plus(q)}&setmkt=en-US&setlang=en&form=QBLH"
print("url", url)
r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=25)
print("status", r.status_code, "len", len(r.text))
d = extract_bing_domains(r.text)
print("domains", d)
