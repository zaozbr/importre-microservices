import json, subprocess
patterns = ['importre.py', 'importre_supervisor.py', 'importre_server.py', '_monitor_importre.py', '_chd_convert_v2.py', '_chd_supervisor.py']
for pattern in patterns:
    result = subprocess.run(
        ['powershell', '-Command',
         f"Get-WmiObject Win32_Process -Filter \"Name='python.exe'\" | Where-Object {{ $_.CommandLine -like '*{pattern}*' }} | Select-Object ProcessId, CommandLine | ConvertTo-Json"],
        capture_output=True, text=True, timeout=10
    )
    print(f'--- {pattern} ---')
    if result.stdout.strip():
        print(result.stdout)
    else:
        print('nenhum')
