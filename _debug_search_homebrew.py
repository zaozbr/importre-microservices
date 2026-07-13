import sys
sys.path.insert(0, r'D:\roms\library\roms\psx')
from importre import SiteNavigator
from playwright.sync_api import sync_playwright

pw = sync_playwright().start()
nav = SiteNavigator(pw)

# Chamar metodo diretamente com prints
import logging
logging.basicConfig(level=logging.DEBUG)

result, detail = nav.search_homebrew('Celeste Classic PSX', 'HBREW-001', 'Celeste Classic PSX (psn00bsdk)')
print('FINAL result:', result)
print('FINAL detail:', detail)

nav.browser.close()
pw.stop()
