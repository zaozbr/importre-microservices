import time, os, re, sys
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import requests

LOG = r'F:\importre_state\test_pw.log'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

log("=== Playwright download test ===")

dest_dir = r'F:\downloads\psx_faltantes'
os.makedirs(dest_dir, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--disable-features=IsolateOrigins,site-per-process'])
    context = browser.new_context(
        user_agent=UA,
        accept_downloads=True,
    )
    page = context.new_page()

    # Navigate to rom page
    log("Navigating to rom page...")
    page.goto('https://www.romulation.org/rom/PSX/Vigilante-8', timeout=30000)
    log(f"  Page loaded: {page.title()}")

    # Find and click the download button
    log("Looking for download button...")
    dl_link = None
    for a in page.query_selector_all('a[href*="newdownload"]'):
        dl_link = a.get_attribute('href')
        break

    if dl_link:
        if not dl_link.startswith('http'):
            dl_link = 'https://www.romulation.org' + dl_link
        log(f"  Found download link: {dl_link[:80]}...")

        # Navigate to download page
        log("Navigating to download page...")
        page.goto(dl_link, timeout=30000)
        log(f"  Download page loaded: {page.title()}")

        # Find the USA download link
        log("Looking for USA pluto link...")
        usa_link = None
        for a in page.query_selector_all('a[href*="pluto.romulation.net"]'):
            text = a.inner_text()
            if '(USA)' in text and 'Rev' not in text:
                usa_link = a
                log(f"  Found: {text}")
                break

        if not usa_link:
            # Just get the first pluto link
            for a in page.query_selector_all('a[href*="pluto.romulation.net"]'):
                usa_link = a
                log(f"  Using first link: {a.inner_text()}")
                break

        if usa_link:
            href = usa_link.get_attribute('href')
            log(f"  Pluto URL: {href[:80]}...")

            # Try to download by clicking the link
            log("Clicking download link...")
            try:
                with page.expect_download(timeout=600000) as download_info:
                    usa_link.click()
                download = download_info.value
                dest = os.path.join(dest_dir, 'SLUS-00510_pw2.7z')
                download.save_as(dest)
                size = os.path.getsize(dest)
                log(f"  SUCCESS! Downloaded: {size/1024/1024:.1f} MB")
            except Exception as e:
                log(f"  Click download failed: {e}")
                # Try navigating directly
                log("Trying direct navigation...")
                try:
                    with page.expect_download(timeout=600000) as download_info:
                        page.goto(href, timeout=600000)
                    download = download_info.value
                    dest = os.path.join(dest_dir, 'SLUS-00510_pw2.7z')
                    download.save_as(dest)
                    size = os.path.getsize(dest)
                    log(f"  SUCCESS! Downloaded: {size/1024/1024:.1f} MB")
                except Exception as e2:
                    log(f"  Direct navigation failed: {e2}")
                    # Check page content
                    log(f"  Page URL: {page.url}")
                    log(f"  Page content: {page.content()[:300]}")
        else:
            log("  No pluto link found!")
    else:
        log("  No download button found!")

    browser.close()

log("=== Done ===")
