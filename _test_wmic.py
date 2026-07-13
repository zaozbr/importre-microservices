import subprocess
result = subprocess.run(
    ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine"],
    capture_output=True, text=True, timeout=10
)
print("stdout:", result.stdout[:500])
print("found supervisor:", "_chd_supervisor" in result.stdout)
