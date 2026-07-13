import sys, time
sys.path.insert(0, r'D:\roms\library\roms\psx')
from importre import SiteNavigator
from playwright.sync_api import sync_playwright

pw = sync_playwright().start()
nav = SiteNavigator(pw)

t0 = time.time()
result, detail = nav.search_homebrew('Celeste Classic PSX', 'HBREW-001', 'Celeste Classic PSX (psn00bsdk)')
print(f'tempo: {time.time()-t0:.1f}s')
print('FINAL result:', result)
print('FINAL detail:', detail)

nav.browser.close()
pw.stop()
