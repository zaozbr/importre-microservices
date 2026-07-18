import time, os, re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# First, get the rom page and download page URL using requests
session = requests.Session()
session.headers.update(HEADERS)

r = session.get('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
dl_link = None
for a in soup.find_all('a', href=True):
    if 'newdownload' in a['href']:
        dl_link = a['href'] if a['href'].startswith('http') else 'https://www.romulation.org' + a['href']
        break
print(f'Download page: {dl_link[:80]}...')

# Get pluto links from download page
r2 = session.get(dl_link, timeout=30)
soup2 = BeautifulSoup(r2.text, 'html.parser')
body = soup2.find('body') or soup2
links = []
for a in body.find_all('a', href=True):
    if 'pluto.romulation.net' in a['href']:
        links.append((a['href'], a.get_text(strip=True)))

# Pick USA
selected = None
for u, f in links:
    if '(USA)' in f and 'Rev' not in f:
        selected = (u, f)
        break
if not selected:
    for u, f in links:
        if '(USA)' in f:
            selected = (u, f)
            break

if not selected:
    print("No USA link found!")
    exit(1)

pluto_url, filename = selected
print(f"Will download: {filename}")
print(f"Pluto URL: {pluto_url[:80]}...")

# Now use Playwright to download
dest_dir = r'F:\downloads\psx_faltantes'
os.makedirs(dest_dir, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent=HEADERS['User-Agent'],
        accept_downloads=True,
    )
    page = context.new_page()

    # Navigate to the rom page first to establish session
    print("Navigating to rom page...")
    page.goto('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30000)
    time.sleep(2)

    # Now navigate to the pluto download URL
    print("Navigating to pluto URL...")
    try:
        # Try to download via page.expect_download
        with page.expect_download(timeout=600000) as download_info:
            page.goto(pluto_url, timeout=600000)
        download = download_info.value
        dest = os.path.join(dest_dir, f"SLUS-00510_pw.7z")
        download.save_as(dest)
        size = os.path.getsize(dest)
        print(f"Downloaded via Playwright: {size/1024/1024:.1f} MB")
    except Exception as e:
        print(f"Download via expect_download failed: {e}")
        # Fallback: check if we got a response
        response = page.goto(pluto_url, timeout=60000)
        if response:
            print(f"Response status: {response.status}")
            print(f"Content-Type: {response.headers.get('content-type','?')}")
            body_text = page.content()[:500]
            print(f"Page content: {body_text}")

    browser.close()
