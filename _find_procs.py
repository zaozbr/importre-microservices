import subprocess
result = subprocess.run(
    ['wmic', 'process', 'where', "name='python.exe' or name='pythonw.exe'",
     'get', 'ProcessId,CommandLine', '/format:list'],
    capture_output=True, text=True, timeout=10
)
lines = result.stdout.split('\n')
current_cmd = ''
for line in lines:
    if line.startswith('CommandLine='):
        current_cmd = line[len('CommandLine='):]
    elif line.startswith('ProcessId='):
        pid = line[len('ProcessId='):]
        if any(k in current_cmd.lower() for k in ['importre', 'supervisor', 'wrapper', '_run_']):
            print(f"PID={pid} CMD={current_cmd[:120]}")
        current_cmd = ''
