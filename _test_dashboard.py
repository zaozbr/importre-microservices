"""
Teste automatizado do dashboard — valida todos os endpoints e dados.
Executa como QA: verifica cada bloco do dashboard tem dados corretos.
"""
import sys, json, time, requests, os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

API = 'http://127.0.0.1:8765'
STATE_DIR = r'D:\roms\library\roms\_importre_state'

PASS = 0
FAIL = 0
ERRORS = []


def check(name, condition, detail=''):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f'  [PASS] {name}')
    else:
        FAIL += 1
        ERRORS.append(f'{name}: {detail}')
        print(f'  [FAIL] {name} — {detail}')


def test_server_online():
    """Testa se o servidor está online."""
    print('\n=== TESTE 1: Servidor Online ===')
    try:
        r = requests.get(f'{API}/api/status', timeout=5)
        check('Servidor responde', r.status_code == 200, f'Status: {r.status_code}')
        return r.json()
    except Exception as e:
        check('Servidor responde', False, str(e))
        return None


def test_status_fast():
    """Testa o endpoint /api/status/fast."""
    print('\n=== TESTE 2: Status Fast ===')
    try:
        r = requests.get(f'{API}/api/status/fast', timeout=5)
        check('Fast endpoint responde', r.status_code == 200)
        d = r.json()
        s = d.get('status', {})
        check('Tem status', 'status' in d)
        check('Tem dl_progress', 'dl_progress' in s)
        check('Tem in_progress_items', 'in_progress_items' in s)
        check('Tem completed', 'completed' in s)
        check('Tem pending', 'pending' in s)
        check('Tem failed', 'failed' in s)
        check('Tem total', 'total' in s)
        return d
    except Exception as e:
        check('Fast endpoint', False, str(e))
        return None


def test_status_full():
    """Testa o endpoint /api/status (completo)."""
    print('\n=== TESTE 3: Status Full ===')
    try:
        r = requests.get(f'{API}/api/status', timeout=5)
        check('Full endpoint responde', r.status_code == 200)
        d = r.json()
        s = d.get('status', {})
        check('Tem sites', 'sites' in d)
        check('Tem blacklist', 'blacklist' in d)
        check('Tem control', 'control' in d)
        check('Tem learning', 'learning' in d)
        check('Tem process_state', 'process_state' in d)
        check('Tem completed_items', 'completed_items' in s)
        check('Tem failed_items', 'failed_items' in s)
        check('Tem dl_progress', 'dl_progress' in s)
        # Verificar se completed_items tem mais de 30
        ci_count = len(s.get('completed_items', {}))
        check('Completed_items > 30', ci_count > 30, f'So {ci_count} itens')
        return d
    except Exception as e:
        check('Full endpoint', False, str(e))
        return None


def test_emergency_endpoint():
    """Testa o endpoint /api/emergency."""
    print('\n=== TESTE 4: Emergency Endpoint ===')
    try:
        r = requests.get(f'{API}/api/emergency', timeout=5)
        check('Emergency endpoint responde', r.status_code == 200, f'Status: {r.status_code}')
        d = r.json()
        check('Tem errors', 'errors' in d)
        check('Tem dl_log', 'dl_log' in d)
        check('Tem queue_completed_count', 'queue_completed_count' in d)
        check('Tem queue_failed_count', 'queue_failed_count' in d)
        check('Tem queue_pending_count', 'queue_pending_count' in d)
        # Verificar se errors tem estrutura correta
        errors = d.get('errors', {})
        for serial, e in errors.items():
            check(f'Erro {serial} tem campo error', 'error' in e)
            check(f'Erro {serial} tem campo mode', 'mode' in e)
            check(f'Erro {serial} tem campo time', 'time' in e)
            break
        return d
    except Exception as e:
        check('Emergency endpoint', False, str(e))
        return None


def test_dashboard_html():
    """Testa se o dashboard HTML tem todos os blocos."""
    print('\n=== TESTE 5: Dashboard HTML ===')
    try:
        r = requests.get(f'{API}/', timeout=5)
        check('Dashboard HTML responde', r.status_code == 200)
        html = r.text
        # Verificar blocos
        check('Tem bloco Downloads Ativos', 'dl-rows' in html)
        check('Tem bloco Atividade', 'feed-box' in html)
        check('Tem bloco Buscando', 'search-rows' in html)
        check('Tem bloco Iniciando', 'start-rows' in html)
        check('Tem bloco Concluidos', 'ok-rows' in html)
        check('Tem bloco Falhas', 'fail-rows' in html)
        check('Tem bloco Sites', 'sites-rows' in html)
        check('Tem bloco Erros Emergency', 'emerg-error-rows' in html)
        check('Tem bloco Erros Emergency Section', 'emerg-errors-section' in html)
        # Verificar JavaScript
        check('Tem fetch /api/emergency', "/api/emergency" in html)
        check('Tem updateEmergency function', 'updateEmergency' in html)
        check('Tem refreshFull', 'refreshFull' in html)
        check('Tem refreshFast', 'refreshFast' in html)
        return html
    except Exception as e:
        check('Dashboard HTML', False, str(e))
        return None


def test_data_consistency():
    """Testa consistencia dos dados entre endpoints."""
    print('\n=== TESTE 6: Consistencia de Dados ===')
    try:
        r1 = requests.get(f'{API}/api/status/fast', timeout=5).json()
        r2 = requests.get(f'{API}/api/status', timeout=5).json()
        r3 = requests.get(f'{API}/api/emergency', timeout=5).json()
        s1 = r1['status']
        s2 = r2['status']
        # Completed count deve ser igual entre fast e full
        check('Completed consistente', s1['completed'] == s2['completed'],
              f'fast={s1["completed"]} vs full={s2["completed"]}')
        # Failed count deve ser igual
        check('Failed consistente', s1['failed'] == s2['failed'],
              f'fast={s1["failed"]} vs full={s2["failed"]}')
        # Emergency completed deve ser >= server completed
        q_completed = r3.get('queue_completed_count', 0)
        check('Emergency completed >= server', q_completed >= s2['completed'],
              f'emergency={q_completed} vs server={s2["completed"]}')
    except Exception as e:
        check('Consistencia', False, str(e))


def test_dl_progress():
    """Testa se dl_progress.json tem dados validos."""
    print('\n=== TESTE 7: DL Progress ===')
    path = os.path.join(STATE_DIR, 'dl_progress.json')
    try:
        size = os.path.getsize(path)
        check('dl_progress.json nao esta vazio', size > 0, f'Size: {size} bytes')
        with open(path, 'r') as f:
            prog = json.load(f)
        # dl_progress pode estar vazio {} entre batches — isso e normal
        if len(prog) > 0:
            check('dl_progress tem dados', True)
        else:
            print('  [SKIP] dl_progress vazio (entre batches — normal)')
        check('dl_progress e dict valido', isinstance(prog, dict))
        for serial, info in prog.items():
            check(f'{serial} tem downloaded', 'downloaded' in info)
            check(f'{serial} tem total', 'total' in info)
            check(f'{serial} tem speed', 'speed' in info)
            check(f'{serial} tem ts', 'ts' in info)
            # Verificar se ts e recente (ultimos 60s)
            age = time.time() - info.get('ts', 0)
            check(f'{serial} ts recente', age < 60, f'Age: {age:.0f}s')
            break
    except json.JSONDecodeError as e:
        check('dl_progress.json valido', False, str(e))
    except Exception as e:
        check('dl_progress', False, str(e))


def test_download_errors():
    """Testa se download_errors.json tem dados validos."""
    print('\n=== TESTE 8: Download Errors ===')
    path = os.path.join(STATE_DIR, 'download_errors.json')
    try:
        with open(path, 'r') as f:
            errors = json.load(f)
        check('download_errors.json valido', True)
        for serial, e in errors.items():
            check(f'Erro {serial} tem error', 'error' in e)
            check(f'Erro {serial} tem mode', 'mode' in e)
            check(f'Erro {serial} tem time_str', 'time_str' in e)
            break
    except Exception as e:
        check('download_errors', False, str(e))


def test_queue_json():
    """Testa se queue.json nao esta corrompido."""
    print('\n=== TESTE 9: Queue JSON ===')
    path = os.path.join(STATE_DIR, 'queue.json')
    try:
        with open(path, 'r') as f:
            q = json.load(f)
        check('queue.json valido', True)
        check('Tem completed', 'completed' in q)
        check('Tem failed', 'failed' in q)
        check('Tem queue', 'queue' in q)
        check('Tem in_progress', 'in_progress' in q)
        c = q.get('completed', {})
        check('Completed e dict', isinstance(c, dict), f'Type: {type(c)}')
        check('Completed > 100', len(c) > 100, f'So {len(c)}')
    except json.JSONDecodeError as e:
        check('queue.json valido', False, f'Corrompido: {e}')
    except Exception as e:
        check('queue.json', False, str(e))


def main():
    print('=' * 60)
    print('  TESTE AUTOMATIZADO DO DASHBOARD — PSX ROM Downloader')
    print('=' * 60)
    test_server_online()
    test_status_fast()
    test_status_full()
    test_emergency_endpoint()
    test_dashboard_html()
    test_data_consistency()
    test_dl_progress()
    test_download_errors()
    test_queue_json()
    print('\n' + '=' * 60)
    print(f'  RESULTADO: {PASS} passaram, {FAIL} falharam')
    print('=' * 60)
    if ERRORS:
        print('\nFALHAS:')
        for e in ERRORS:
            print(f'  - {e}')
    return 1 if FAIL > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
