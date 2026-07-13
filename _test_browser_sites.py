from playwright.sync_api import sync_playwright
import time, re

serial = 'SLUS-00426'
name = 'MDK'

sites = [
    ('romsdl', f'https://romsdl.com/roms/playstation-1', 'playstation-1'),
    ('retrostic', f'https://www.retrostic.com/roms/ps-1', 'ps-1'),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for site_key, url, system in sites:
        print(f"\n=== {site_key}: {url} ===")
        try:
            page = browser.new_page()
            page.goto(url, timeout=30000)
            time.sleep(2)
            html = page.content()
            if serial.lower().replace('-', '') in html.lower().replace('-', ''):
                print(f"  {serial} found in page")
            else:
                print(f"  {serial} NOT found")
            page.close()
        except Exception as e:
            print(f"  Erro: {e}")
    browser.close()
