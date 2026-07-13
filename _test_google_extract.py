import sys
sys.path.insert(0, r"D:\roms\library\roms\psx")
from importre import SiteNavigator

html = '''
<a href="https://coolrom.com/roms/psx/backyard-football_SLUS-01449">download</a>
<a href="https://archive.org/download/SLUS-01449/file.zip">archive</a>
<a href="https://vimm.net/vault/SLUS-01449">vimm</a>
<a href="https://google.com/search">skip</a>
'''
print(SiteNavigator._extract_known_urls(html, 'SLUS-01449'))
