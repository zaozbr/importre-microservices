import json, subprocess
result = subprocess.run(
    ['powershell', '-Command',
     "Get-WmiObject Win32_Process -Filter \"Name='python.exe'\" | Select-Object ProcessId, CommandLine | ConvertTo-Json"],
    capture_output=True, text=True, timeout=10
)
print(result.stdout[:3000])
