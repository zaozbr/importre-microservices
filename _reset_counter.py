"""Zera a contagem do importre - so reflete jogos da nova leva de redownload."""
import json, shutil
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

QF = r'D:\roms\library\roms\_importre_state\queue.json'
q = json.load(open(QF, 'r', encoding='utf-8'))

# Backup
shutil.copy2(QF, QF + '.bak_pre_reset')

old_completed = len(q.get('completed', {}))
old_failed = len(q.get('failed', {}))

q['completed'] = {}
q['failed'] = {}
q['retry_count'] = {}
queue_len = len(q.get('queue', []))
ip_len = len(q.get('in_progress', {}))
q['total'] = queue_len + ip_len

json.dump(q, open(QF, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

print('Contagem zerada:')
print(f'  Completed removidos: {old_completed}')
print(f'  Failed removidos: {old_failed}')
print(f'  Queue (pendentes): {queue_len}')
print(f'  In progress: {ip_len}')
print(f'  Completed: 0')
print(f'  Failed: 0')
print(f'  Total: {q["total"]}')
