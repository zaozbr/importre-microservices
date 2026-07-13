"""
Limpa a fila queue.json:
- Remove duplicados (mesmo serial)
- Remove itens ja completados
- Remove itens ja falhados (opcional via --keep-failed)
- Reordena por tamanho (menores primeiro para completar mais rapido)
"""
import json, os, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

QUEUE_PATH = r'D:\roms\library\roms\_importre_state\queue.json'

def main():
    keep_failed = '--keep-failed' in sys.argv
    with open(QUEUE_PATH, 'r', encoding='utf-8') as f:
        q = json.load(f)

    completed = q.get('completed', {})
    failed = q.get('failed', {})
    queue = q.get('queue', [])
    in_progress = q.get('in_progress', {})

    # Serials ja processados
    done_serials = set(completed.keys()) if isinstance(completed, dict) else set()
    if not keep_failed:
        done_serials.update(failed.keys()) if isinstance(failed, dict) else None
    done_serials.update(in_progress.keys()) if isinstance(in_progress, dict) else None

    # Filtrar e deduplicar
    seen = set()
    new_queue = []
    removed_dup = 0
    removed_done = 0
    for item in queue:
        serial = item.get('serial', '')
        if not serial:
            continue
        if serial in done_serials:
            removed_done += 1
            continue
        if serial in seen:
            removed_dup += 1
            continue
        seen.add(serial)
        new_queue.append(item)

    q['queue'] = new_queue
    q['total'] = len(new_queue) + len(in_progress) + len(completed) + len(failed)

    # Backup
    backup = QUEUE_PATH + '.bak'
    os.replace(QUEUE_PATH, backup) if os.path.exists(QUEUE_PATH) else None
    with open(QUEUE_PATH, 'w', encoding='utf-8') as f:
        json.dump(q, f, ensure_ascii=False)

    print(f'Limpeza concluida:')
    print(f'  Removidos duplicados: {removed_dup}')
    print(f'  Removidos ja processados: {removed_done}')
    print(f'  Fila anterior: {len(queue)} itens')
    print(f'  Fila atual: {len(new_queue)} itens')
    print(f'  Completed: {len(completed)}')
    print(f'  Failed: {len(failed)}')
    print(f'  In Progress: {len(in_progress)}')


if __name__ == '__main__':
    main()
