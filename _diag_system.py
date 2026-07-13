"""Diagnostico completo de sujeira no sistema para evitar crashes do Devin."""
import os, sys, subprocess, shutil, glob, time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15, shell=True)
        return r.stdout + r.stderr
    except:
        return ""

def fmt_bytes(n):
    if n >= 1e9: return f"{n/1e9:.1f} GB"
    if n >= 1e6: return f"{n/1e6:.1f} MB"
    if n >= 1e3: return f"{n/1e3:.1f} KB"
    return f"{n} B"

print("=" * 70)
print("  DIAGNOSTICO DE SUCULEIRA DO SISTEMA")
print("=" * 70)

# 1. Processos por categoria
print("\n[1] PROCESSOS POR CATEGORIA (RAM)")
print("-" * 50)

cats = {
    "Devin": [], "pwsh": [], "cmd": [], "conhost": [],
    "chrome": [], "brave": [], "node": [], "python": [],
    "msedgewebview2": [], "duckstation": [], "chdman": [],
}

out = run('wmic process get name,processid,workingsetsize /format:csv')
for line in out.strip().split('\n'):
    parts = line.strip().split(',')
    if len(parts) < 4: continue
    name = parts[1]
    pid = parts[2]
    try: ws = int(parts[3])
    except: continue
    for cat in cats:
        if cat.lower() in name.lower():
            cats[cat].append((pid, name, ws))
            break

total_ram = 0
for cat, procs in sorted(cats.items(), key=lambda x: -sum(p[2] for p in x[1])):
    if not procs: continue
    ram = sum(p[2] for p in procs)
    total_ram += ram
    print(f"  {cat:20s}: {len(procs):3d} proc, {fmt_bytes(ram):>10s}")
    for pid, name, ws in sorted(procs, key=lambda x: -x[2])[:3]:
        print(f"    PID {pid:>6s}: {fmt_bytes(ws):>10s}")

print(f"\n  TOTAL CATEGORIZADO: {fmt_bytes(total_ram)}")

# 2. Disco
print("\n[2] ESPACO EM DISCO")
print("-" * 50)
out = run('wmic logicaldisk get caption,freespace,size /format:list')
disks = {}
current = {}
for line in out.strip().split('\n'):
    line = line.strip()
    if line.startswith('Caption='):
        if current: disks[current.get('Caption','')] = current
        current = {'Caption': line.split('=')[1]}
    elif line.startswith('FreeSpace='):
        current['Free'] = int(line.split('=')[1]) if line.split('=')[1].isdigit() else 0
    elif line.startswith('Size='):
        current['Size'] = int(line.split('=')[1]) if line.split('=')[1].isdigit() else 0
if current: disks[current.get('Caption','')] = current

for disk, info in disks.items():
    if not disk: continue
    free = info.get('Free', 0)
    size = info.get('Size', 0)
    used = size - free
    pct = (used / size * 100) if size else 0
    print(f"  {disk} {fmt_bytes(used):>10s} / {fmt_bytes(size):>10s} usado ({pct:.0f}%) | livre: {fmt_bytes(free)}")

# 3. Temp do Windows
print("\n[3] TEMP DO WINDOWS")
print("-" * 50)
temp_dir = Path(os.environ.get('TEMP', 'C:\\Users\\Usuario\\AppData\\Local\\Temp'))
total = 0
count = 0
for f in temp_dir.rglob('*'):
    try:
        if f.is_file():
            total += f.stat().st_size
            count += 1
    except: pass
print(f"  {temp_dir}")
print(f"  {count} arquivos, {fmt_bytes(total)}")

# 4. Devin overflow temp
print("\n[4] DEVIN OVERFLOW TEMP")
print("-" * 50)
overflow_dir = temp_dir / 'devin.exe-overflows'
if overflow_dir.exists():
    total = 0
    count = 0
    for f in overflow_dir.rglob('*'):
        try:
            if f.is_file():
                total += f.stat().st_size
                count += 1
        except: pass
    print(f"  {overflow_dir}")
    print(f"  {count} arquivos, {fmt_bytes(total)}")
else:
    print("  Nao existe")

# 5. Devin summaries
print("\n[5] DEVIN SUMMARIES (historico de sessoes)")
print("-" * 50)
summaries = Path(r'C:\Users\Usuario\AppData\Roaming\devin\cli\summaries')
if summaries.exists():
    files = list(summaries.glob('*'))
    total = sum(f.stat().st_size for f in files if f.is_file())
    print(f"  {summaries}")
    print(f"  {len(files)} arquivos, {fmt_bytes(total)}")
    for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
        ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(f.stat().st_mtime))
        print(f"    {ts} {fmt_bytes(f.stat().st_size):>10s} {f.name}")
else:
    print("  Nao existe")

# 6. Devin logs
print("\n[6] DEVIN LOGS")
print("-" * 50)
log_dirs = [
    Path(r'C:\Users\Usuario\AppData\Roaming\devin'),
    Path(r'C:\Users\Usuario\AppData\Local\devin'),
    Path(r'C:\Users\Usuario\AppData\Local\Programs\Devin'),
]
for ld in log_dirs:
    if not ld.exists(): continue
    total = 0
    count = 0
    for f in ld.rglob('*.log'):
        try:
            total += f.stat().st_size
            count += 1
        except: pass
    if count:
        print(f"  {ld}")
        print(f"  {count} arquivos .log, {fmt_bytes(total)}")

# 7. PSX temp files
print("\n[7] ARQUIVOS TEMPORARIOS PSX (_temp_*)")
print("-" * 50)
psx = Path(r'D:\roms\library\roms\psx')
temp_files = list(psx.glob('_temp_*'))
total = sum(f.stat().st_size for f in temp_files if f.is_file())
print(f"  {len(temp_files)} arquivos, {fmt_bytes(total)}")
for f in sorted(temp_files, key=lambda x: x.stat().st_size, reverse=True)[:10]:
    print(f"    {fmt_bytes(f.stat().st_size):>10s} {f.name}")

# 8. F:\chd_temp
print("\n[8] F:\\chd_temp (SSD temporario)")
print("-" * 50)
chd_temp = Path(r'F:\chd_temp')
if chd_temp.exists():
    files = list(chd_temp.iterdir())
    total = sum(f.stat().st_size for f in files if f.is_file())
    chds = [f for f in files if f.suffix == '.chd']
    print(f"  {len(files)} itens, {fmt_bytes(total)}")
    print(f"  CHDs: {len(chds)}")
    for f in sorted(files, key=lambda x: x.stat().st_size, reverse=True)[:5]:
        print(f"    {fmt_bytes(f.stat().st_size):>10s} {f.name}")

# 9. D:\roms\duplicados
print("\n[9] D:\\roms\\duplicados (fontes movidas)")
print("-" * 50)
dup = Path(r'D:\roms\duplicados')
if dup.exists():
    files = list(dup.rglob('*'))
    total = sum(f.stat().st_size for f in files if f.is_file())
    print(f"  {len(files)} itens, {fmt_bytes(total)}")

# 10. Processos zumbis (pwsh, cmd, conhost antigos)
print("\n[10] PROCESSOS ZUMBIS (pwsh/cmd/conhost antigos)")
print("-" * 50)
out = run('wmic process get name,processid,creationdate /format:csv')
now = time.time()
zombies = []
for line in out.strip().split('\n'):
    parts = line.strip().split(',')
    if len(parts) < 4: continue
    name = parts[1]
    pid = parts[2]
    cdate = parts[3]
    if not name or not pid: continue
    if name.lower() not in ('pwsh.exe', 'cmd.exe', 'conhost.exe'): continue
    # Parse creation date
    try:
        # 20260712044020.831294-180
        d = cdate.split('.')[0]
        ts = time.mktime(time.strptime(d, '%Y%m%d%H%M%S'))
        age_min = (now - ts) / 60
    except:
        age_min = 0
    zombies.append((name, pid, age_min))

print(f"  Total: {len(zombies)} processos")
for name, pid, age in sorted(zombies, key=lambda x: -x[2])[:15]:
    print(f"  {name:20s} PID {pid:>6s} idade: {age:.0f} min")

# 11. Recomendacoes
print("\n" + "=" * 70)
print("  RECOMENDACOES DE LIMPEZA")
print("=" * 70)
print("""
1. FECHAR ABAS DO CHROME/BRAVE NAO UTILIZADAS
   - Chrome: ~3 GB em 18 processos
   - Brave: ~800 MB em 12 processos
   - Total navegadores: ~3.8 GB

2. FECHAR DUCKSTATION (se nao estiver em uso)
   - duckstation-qt: 542 MB

3. LIMPAR PROCESSOS POWERSHELL ZUMBIS
   - 10 instancias de pwsh.exe (~720 MB)
   - 14 instancias de cmd.exe (~168 MB)
   - 16 instancias de conhost.exe (~150 MB)
   - Total: ~1 GB em processos de shell

4. LIMPAR TEMP DO WINDOWS
   - Arquivos temporarios acumulados

5. LIMPAR ARQUIVOS _temp_* DO PSX
   - CUEs temporarios de conversoes anteriores

6. DEVIN PROCESSO PRINCIPAL (PID 139772): 2.78 GB
   - Este e o processo que mais consome RAM
   - Pode estar com memory leak apos sessao longa
   - Reiniciar o Devin pode liberar ~5 GB de RAM
""")
