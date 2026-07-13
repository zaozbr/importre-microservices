import shutil
u = shutil.disk_usage('D:')
print(f"D: free={u.free/1024**3:.1f}GB total={u.total/1024**3:.1f}GB used={u.used/1024**3:.1f}GB")
u2 = shutil.disk_usage('C:')
print(f"C: free={u2.free/1024**3:.1f}GB total={u2.total/1024**3:.1f}GB")
