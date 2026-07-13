"""Diagnostica coolrom: testa download direto vs Tor, verifica sites.json."""
import json
import time
import requests

# 1. Verificar sites.json
sites = json.load(open(r"D:\roms\library\roms\_importre_state\sites.json", "r", encoding="utf-8"))
coolrom = sites.get("coolrom", {})
print("=== COOLROM no sites.json ===")
print(f"  enabled: {coolrom.get('enabled')}")
print(f"  fail_count: {coolrom.get('fail_count')}")
print(f"  last_fail: {coolrom.get('last_fail')}")
print(f"  url: {coolrom.get('url')}")

# 2. Testar URL de download do coolrom (do log)
# Exemplo: https://dl.coolrom.com/roms/psx/Lightning%20Legend%20-%20Daigo%20no%20Daibouken%20(Japan).7z/...
TEST_URLS = [
    "https://dl.coolrom.com/roms/psx/Lightning%20Legend%20-%20Daigo%20no%20Daibouken%20(Japan).7z/1JC...",
    "https://coolrom.com/roms/psx/",
]

# URL real do log (sucesso pela manhã)
# Vou pegar uma URL que funcionou
print("\n=== TESTE DE CONECTIVIDADE COOLROM ===")

# Testar página principal
try:
    resp = requests.get("https://coolrom.com/roms/psx/", timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    print(f"  coolrom.com/roms/psx/: {resp.status_code}")
except Exception as e:
    print(f"  coolrom.com/roms/psx/: ERRO — {e}")

# Testar dl.coolrom.com diretto
try:
    resp = requests.get("https://dl.coolrom.com/", timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    print(f"  dl.coolrom.com/: {resp.status_code}")
except Exception as e:
    print(f"  dl.coolrom.com/: ERRO — {e}")

# Testar via Tor
try:
    proxies = {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}
    resp = requests.get("https://coolrom.com/roms/psx/", timeout=30, headers={"User-Agent": "Mozilla/5.0"}, proxies=proxies)
    print(f"  coolrom.com via Tor: {resp.status_code}")
except Exception as e:
    print(f"  coolrom.com via Tor: ERRO — {e}")

# 3. Verificar quantos itens na fila têm URL do coolrom no cache
coolrom_cache_path = r"D:\roms\library\roms\_importre_state\coolrom_cache.json"
if __import__("os").path.exists(coolrom_cache_path):
    cache = json.load(open(coolrom_cache_path, "r", encoding="utf-8"))
    print(f"\n=== COOLROM CACHE ===")
    print(f"  Total entradas: {len(cache)}")
    # Verificar se URLs têm timestamp expirado
    # URL pattern: dl.coolrom.com/roms/psx/{nome}.7z/{hash}/{ts}/
    import re
    ts_pattern = re.compile(r'/(\d{10})/$')
    expired = 0
    valid = 0
    now = int(time.time())
    for serial, url in list(cache.items())[:100]:
        if isinstance(url, str):
            m = ts_pattern.search(url)
            if m:
                ts = int(m.group(1))
                age_hours = (now - ts) / 3600
                if age_hours > 12:  # mais de 12h = provavelmente expirado
                    expired += 1
                else:
                    valid += 1
    print(f"  Amostra 100: {valid} válidas (<12h), {expired} expiradas (>12h)")

# 4. Verificar queue.json — quantos pending têm coolrom como fonte potencial
q = json.load(open(r"D:\roms\library\roms\_importre_state\queue.json", "r", encoding="utf-8"))
queue = q.get("queue", [])
print(f"\n=== QUEUE ===")
print(f"  pending: {len(queue)}")
print(f"  completed: {len(q.get('completed', {}))}")
print(f"  failed: {len(q.get('failed', {}))}")

# 5. Verificar Blacklist
blacklist = json.load(open(r"D:\roms\library\roms\_importre_state\blacklist.json", "r", encoding="utf-8"))
coolrom_blacklisted = [k for k, v in blacklist.items() if isinstance(v, dict) and v.get("site") == "coolrom"]
print(f"\n=== BLACKLIST ===")
print(f"  Total blacklist: {len(blacklist)}")
print(f"  CoolROM blacklist: {len(coolrom_blacklisted)}")
