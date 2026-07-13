"""Analisa velocidades de download ao longo do dia comparando manhã vs tarde.
Lê o importre.log (89MB) de forma eficiente, extraindo apenas linhas com MB/s.
"""
import re
import os
from collections import defaultdict
from datetime import datetime

LOG = r"D:\roms\library\roms\_importre_state\importre.log"

# Padrão: 2026-07-12 05:22:30,600 [INFO] [aria2] SLPM-86025 283.1/283.2MB 0.0MB/s conns=2
# Ou:    2026-07-12 05:25:23,764 [INFO] SUCESSO: SLPM-86015 via coolrom
SPEED_PATTERN = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*\[aria2\].*?(\d+\.\d+)/(\d+\.\d+)MB\s+(\d+\.\d+)MB/s.*?conns=(\d+)')
SUCESSO_PATTERN = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*SUCESSO:.*?via\s+(\w+)')
TOR_PATTERN = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?(tor|Tor|SOCKS|proxy)', re.IGNORECASE)

# Coletar por hora
hourly_speeds = defaultdict(list)  # hora -> [(speed_mb, conns), ...]
hourly_sucessos = defaultdict(lambda: defaultdict(int))  # hora -> {site: count}
hourly_tor = defaultdict(int)  # hora -> count
hourly_total_speed = defaultdict(float)  # hora -> soma de velocidades (aproximado)

# Ler arquivo linha por linha (eficiente para 89MB)
print("Lendo log... (pode levar alguns segundos)")
line_count = 0
speed_lines = 0
sucesso_lines = 0
tor_lines = 0

with open(LOG, "r", encoding="utf-8", errors="replace") as f:
    for line in f:
        line_count += 1
        
        # Padrão de velocidade
        m = SPEED_PATTERN.search(line)
        if m:
            timestamp, comp, total, speed, conns = m.groups()
            hour = timestamp.split(" ")[1][:2]  # "05", "16", etc
            speed_f = float(speed)
            conns_i = int(conns)
            hourly_speeds[hour].append((speed_f, conns_i))
            hourly_total_speed[hour] += speed_f
            speed_lines += 1
            continue
        
        # Padrão de sucesso
        m = SUCESSO_PATTERN.search(line)
        if m:
            timestamp, site = m.groups()
            hour = timestamp.split(" ")[1][:2]
            hourly_sucessos[hour][site] += 1
            sucesso_lines += 1
            continue
        
        # Padrão Tor
        m = TOR_PATTERN.search(line)
        if m:
            timestamp = m.group(1)
            hour = timestamp.split(" ")[1][:2]
            hourly_tor[hour] += 1
            tor_lines += 1

print(f"Total linhas: {line_count}")
print(f"Linhas de velocidade: {speed_lines}")
print(f"Linhas de sucesso: {sucesso_lines}")
print(f"Linhas de Tor/proxy: {tor_lines}")

# Resumo por hora
print("\n" + "=" * 80)
print(f"{'Hora':>4} | {'Amostras':>8} | {'Speed méd':>9} | {'Speed max':>9} | {'Speed min':>9} | {'Conns méd':>9} | {'Sucessos':>8} | {'Tor refs':>8}")
print("-" * 80)

for hour in sorted(hourly_speeds.keys()):
    speeds = hourly_speeds[hour]
    speed_vals = [s for s, c in speeds]
    conn_vals = [c for s, c in speeds]
    total_sucessos = sum(hourly_sucessos[hour].values())
    
    avg_speed = sum(speed_vals) / len(speed_vals) if speed_vals else 0
    max_speed = max(speed_vals) if speed_vals else 0
    min_speed = min(speed_vals) if speed_vals else 0
    avg_conns = sum(conn_vals) / len(conn_vals) if conn_vals else 0
    
    print(f"{hour:>4} | {len(speeds):>8} | {avg_speed:>8.2f}M | {max_speed:>8.2f}M | {min_speed:>8.2f}M | {avg_conns:>8.1f} | {total_sucessos:>8} | {hourly_tor[hour]:>8}")

# Detalhar sucessos por site por hora (apenas horas com mais sucessos)
print("\n" + "=" * 80)
print("SUCESSOS POR HORA E SITE:")
print("=" * 80)
for hour in sorted(hourly_sucessos.keys()):
    sites = hourly_sucessos[hour]
    total = sum(sites.values())
    if total > 0:
        top_sites = sorted(sites.items(), key=lambda x: -x[1])[:5]
        sites_str = ", ".join(f"{s}={c}" for s, c in top_sites)
        print(f"  {hour}h: {total} sucessos — {sites_str}")

# Comparar manhã (05-12h) vs tarde (13-17h)
print("\n" + "=" * 80)
print("COMPARAÇÃO: MANHÃ vs TARDE")
print("=" * 80)

manha_speeds = []
tarde_speeds = []
for hour, speeds in hourly_speeds.items():
    h = int(hour)
    if 5 <= h <= 12:
        manha_speeds.extend([s for s, c in speeds])
    elif 13 <= h <= 17:
        tarde_speeds.extend([s for s, c in speeds])

if manha_speeds:
    print(f"Manhã (05-12h):  {len(manha_speeds)} amostras | méd={sum(manha_speeds)/len(manha_speeds):.2f}MB/s | max={max(manha_speeds):.2f}MB/s")
else:
    print("Manhã: sem dados")

if tarde_speeds:
    print(f"Tarde (13-17h):  {len(tarde_speeds)} amostras | méd={sum(tarde_speeds)/len(tarde_speeds):.2f}MB/s | max={max(tarde_speeds):.2f}MB/s")
else:
    print("Tarde: sem dados")

# Verificar se havia downloads via Tor (archive_request com proxy)
print("\n" + "=" * 80)
print("REFERÊNCIAS A TOR/PROXY NO LOG:")
print("=" * 80)
for hour in sorted(hourly_tor.keys()):
    print(f"  {hour}h: {hourly_tor[hour]} referências")

# Velocidades máximas por hora para identificar picos
print("\n" + "=" * 80)
print("PICOS DE VELOCIDADE (top 5 por hora):")
print("=" * 80)
for hour in sorted(hourly_speeds.keys()):
    speeds = hourly_speeds[hour]
    top5 = sorted(speeds, key=lambda x: -x[0])[:5]
    top_str = ", ".join(f"{s:.1f}MB/s(c={c})" for s, c in top5)
    print(f"  {hour}h: {top_str}")
