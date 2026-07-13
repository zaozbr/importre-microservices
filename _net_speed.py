"""Mede banda de rede atual."""
import subprocess, time
result = subprocess.run(
    ['powershell', '-Command',
     r"Get-Counter '\Network Interface(*)\Bytes Total/sec' -SampleInterval 2 -MaxSamples 1 | Select-Object -ExpandProperty CounterSamples | Where-Object {$_.CookedValue -gt 0} | Sort-Object CookedValue -Descending | Select-Object -First 3"],
    capture_output=True, text=True, timeout=15)
print(result.stdout)
if result.stderr:
    print("ERR:", result.stderr[:200])
