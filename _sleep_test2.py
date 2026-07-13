import time, urllib.request, json
LOG = r'D:\roms\library\roms\_importre_state\sleep_test2.log'
f = open(LOG, 'w')
f.write(f'before urlopen at {time.time()}\n')
f.close()
try:
    r = urllib.request.urlopen('http://127.0.0.1:8765/api/status', timeout=10)
    d = json.loads(r.read().decode())
except:
    pass
f = open(LOG, 'a')
f.write(f'before sleep at {time.time()}\n')
f.close()
time.sleep(5)
f = open(LOG, 'a')
f.write(f'after sleep at {time.time()}\n')
f.close()
