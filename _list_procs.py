"""Lista processos pythonw com linha de comando."""
import subprocess, sys
result = subprocess.run(
    ['powershell', '-Command',
     "Get-CimInstance Win32_Process -Filter \"name='pythonw.exe'\" | Select-Object ProcessId,CommandLine | Format-List"],
    capture_output=True, text=True, timeout=15)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:500])
