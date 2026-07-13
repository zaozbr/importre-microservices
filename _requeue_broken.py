"""Adiciona jogos quebrados (identificados pelo DuckStation) na fila de redownload.
Preferencia por formato .chd, mas aceita outros formatos se .chd nao for encontrado."""
import sys, os, re, json, time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BROKEN_LIST = Path(r'D:\roms\library\roms\psx\_redownload_queue.json')
QUEUE_FILE = Path(r'D:\roms\library\roms\_importre_state\queue.json')
CONTROL_FILE = Path(r'D:\roms\library\roms\_importre_state\control.json')

def main():
    # Carregar lista de quebrados
    with open(BROKEN_LIST, 'r', encoding='utf-8') as f:
        broken = json.load(f)
    print(f"Jogos quebrados: {len(broken)}")

    # Carregar fila atual
    with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
        state = json.load(f)
    
    queue = state.get('queue', [])
    completed = state.get('completed', {})
    failed = state.get('failed', {})
    in_progress = state.get('in_progress', {})
    
    print(f"Fila atual: {len(queue)} pendentes, {len(completed)} completados, {len(failed)} falhados, {len(in_progress)} em progresso")
    
    # Filtrar jogos quebrados que tem serial valido
    to_requeue = []
    no_serial = []
    
    for item in broken:
        serial = item.get('serial')
        if not serial or serial == '????':
            no_serial.append(item)
            continue
        to_requeue.append(item)
    
    print(f"Com serial: {len(to_requeue)}")
    print(f"Sem serial: {len(no_serial)}")
    
    # Remover dos completed e failed (para que sejam reprocessados)
    removed_from_completed = 0
    removed_from_failed = 0
    
    for item in to_requeue:
        serial = item['serial']
        if serial in completed:
            del completed[serial]
            removed_from_completed += 1
        if serial in failed:
            del failed[serial]
            removed_from_failed += 1
        if serial in in_progress:
            del in_progress[serial]
    
    print(f"Removidos de completed: {removed_from_completed}")
    print(f"Removidos de failed: {removed_from_failed}")
    
    # Adicionar a fila com preferencia CHD
    # Formato do item da fila: {"serial": "SLUS-XXXXX", "name": "Game Name", "prefer_chd": true}
    added = 0
    skipped = 0
    existing_serials = {q.get('serial') for q in queue if isinstance(q, dict)}
    
    for item in to_requeue:
        serial = item['serial']
        if serial in existing_serials:
            skipped += 1
            continue
        
        queue.append({
            'serial': serial,
            'name': item.get('name', ''),
            'prefer_chd': True,  # Preferencia por CHD
            'redownload_reason': item.get('error_type', 'broken'),
            'redownload_description': item.get('description', ''),
            'queued_at': time.time(),
        })
        added += 1
        existing_serials.add(serial)
    
    # Para jogos sem serial, tentar adicionar por nome
    for item in no_serial:
        name = item.get('name', '')
        filename = item.get('filename', '')
        if not name and not filename:
            continue
        # Usar nome como identificador
        ident = f"NOSERIAL:{name or filename}"
        if ident in existing_serials:
            skipped += 1
            continue
        queue.append({
            'serial': ident,
            'name': name or filename,
            'prefer_chd': True,
            'redownload_reason': item.get('error_type', 'broken'),
            'redownload_description': item.get('description', ''),
            'queued_at': time.time(),
        })
        added += 1
        existing_serials.add(ident)
    
    print(f"\nAdicionados a fila: {added}")
    print(f"Skipped (ja na fila): {skipped}")
    
    # Atualizar state
    state['queue'] = queue
    state['completed'] = completed
    state['failed'] = failed
    state['in_progress'] = in_progress
    state['total'] = len(queue) + len(completed) + len(failed)
    
    # Salvar
    with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    print(f"\nFila salva: {len(queue)} pendentes, {len(completed)} completados, {len(failed)} falhados")
    
    # Atualizar control.json para garantir que importre va processar
    if CONTROL_FILE.exists():
        with open(CONTROL_FILE, 'r', encoding='utf-8') as f:
            control = json.load(f)
        control['paused'] = False
        control['updated_at'] = time.time()
        with open(CONTROL_FILE, 'w', encoding='utf-8') as f:
            json.dump(control, f, ensure_ascii=False, indent=2)
        print(f"control.json atualizado (paused=False)")
    
    # Listar jogos adicionados
    print(f"\n{'='*70}")
    print(f"  JOGOS ADICIONADOS A FILA DE REDOWNLOAD")
    print(f"{'='*70}")
    for item in to_requeue:
        serial = item['serial']
        name = item.get('name', '')[:50]
        reason = item.get('error_type', '')
        print(f"  {serial:12s} | {name:50s} | {reason}")
    
    print(f"\n{'='*70}")
    print(f"  JOGOS SEM SERIAL (adicionados por nome)")
    print(f"{'='*70}")
    for item in no_serial:
        name = item.get('name', '')[:60]
        filename = item.get('filename', '')[:60]
        reason = item.get('error_type', '')
        print(f"  {name or filename:60s} | {reason}")


if __name__ == '__main__':
    main()
