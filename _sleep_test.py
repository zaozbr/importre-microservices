import time, os
LOG = r'D:\roms\library\roms\_importre_state\sleep_test.log'
f = open(LOG, 'w')
f.write(f'before sleep at {time.time()}\n')
f.close()
time.sleep(5)
f = open(LOG, 'a')
f.write(f'after sleep at {time.time()}\n')
f.close()
