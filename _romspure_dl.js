/**
 * Romspure.cc downloader via Playwright (real browser).
 *
 * Romspure returns 403 for axios/curl but works in a real browser.
 * Strategy:
 *   1. Launch chromium (headless=false) and navigate to each game page.
 *   2. Extract the /download/{slug}-{postId} link from the page.
 *   3. Navigate to the download page so the browser holds cookies.
 *   4. Run the romspure AJAX flow (romspure_get_nonce -> app_get_download_link)
 *      INSIDE the page context via fetch() so requests carry browser
 *      cookies/headers (bypasses Cloudflare 403).
 *   5. Submit the resulting direct URL to the local aria2c daemon
 *      (token:devin) with out={SERIAL}.{ext}.
 *   6. Fallback: if aria2c fails, trigger a Playwright download event.
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const axios = require('axios');

const DOWNLOAD_DIR = 'F:/downloads';
const ARIA2_RPC = 'http://127.0.0.1:6800/jsonrpc';
const ARIA2_TOKEN = 'token:devin';
const STATE_FILE = 'F:/importre/_romspure_dl_state.json';

const GAMES = [
  { url: 'https://romspure.cc/roms/sony-playstation/ayakashi-ninden-kunoichiban/', serial: 'SLPS-00946' },
  { url: 'https://romspure.cc/roms/sony-playstation/poketan/', serial: 'SCPS-10108' },
  { url: 'https://romspure.cc/roms/sony-playstation/mahjong-ganryuujima-2-161/', serial: 'SLPS-02979' },
  { url: 'https://romspure.cc/roms/sony-playstation/soukyugurentai-oubushutsugeki/', serial: 'SLPM-87255' },
  { url: 'https://romspure.cc/roms/sony-playstation/guuguuthropus/', serial: 'SLPM-86148' },
  { url: 'https://romspure.cc/roms/sony-playstation/pacapaca-passion-special/', serial: 'SLPS-02895' },
  { url: 'https://romspure.cc/roms/sony-playstation/reikoku-ikeda-kizoku-shinrei-kenkyuujo/', serial: 'SLPM-86274' },
  { url: 'https://romspure.cc/roms/sony-playstation/zeiramzone/', serial: 'SLPS-00575' },
  { url: 'https://romspure.cc/roms/sony-playstation/kinniku-banzuke-road-to-sasuke/', serial: 'KinnikuBanzuke' },
  { url: 'https://romspure.cc/roms/sony-playstation/gute-zeiten-schlechte-zeiten-quiz/', serial: 'SLES-02693' },
  { url: 'https://romspure.cc/roms/sony-playstation/gute-zeiten-schlechte-zeiten-vol-2/', serial: 'SLES-02441' },
  { url: 'https://romspure.cc/roms/sony-playstation/zoku-gussun-oyoyo/', serial: 'SLPS-00488' },
  { url: 'https://romspure.cc/roms/sony-playstation/katou-hifumi-kudan-shougi-club/', serial: 'SLPM-86045' },
  { url: 'https://romspure.cc/roms/sony-playstation/meltylancer-re-inforce/', serial: 'SLPS-01147' },
  { url: 'https://romspure.cc/roms/sony-playstation/mouja/', serial: 'SLPS-02252' },
  { url: 'https://romspure.cc/roms/sony-playstation/senryaku-shougi/', serial: 'SLPS-00142' },
  { url: 'https://romspure.cc/roms/sony-playstation/castlevania-symphony-of-the-night-6776/', serial: 'SLUS-00519' },
  { url: 'https://romspure.cc/roms/sony-playstation/final-fantasy-vii/', serial: 'SLUS-00286' },
];

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function loadState() {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
  } catch {
    return { done: [], failed: [], results: [] };
  }
}

function saveState(state) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

function extFromUrl(url) {
  const clean = url.split('?')[0].split('#')[0];
  const m = clean.match(/\.(zip|rar|7z|chd|iso)(?:$|\/)/i);
  return m ? m[1].toLowerCase() : 'zip';
}

async function aria2AddUri(url, outName, cookieHeader, referer) {
  const headers = [];
  if (cookieHeader) headers.push('Cookie: ' + cookieHeader);
  if (referer) headers.push('Referer: ' + referer);
  headers.push('User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');
  const options = { dir: DOWNLOAD_DIR, out: outName, header: headers };
  const params = [ARIA2_TOKEN, [url], options];
  const r = await axios.post(ARIA2_RPC, {
    jsonrpc: '2.0', method: 'aria2.addUri', id: '1', params,
  }, { timeout: 15000 });
  if (r.data.error) throw new Error('aria2 error: ' + JSON.stringify(r.data.error));
  return r.data.result;
}

/**
 * Download via Playwright browser download event.
 * The browser sends proper Referer/cookies/User-Agent so the CDN accepts it.
 * Uses waitForEvent('download') since waitForDownload is not available
 * in the patched playwright-extra version.
 */
async function downloadViaPlaywright(context, url, savePath, timeoutMs) {
  const dlPage = await context.newPage();
  try {
    // Set up download listener before navigating
    const downloadPromise = dlPage.waitForEvent('download', { timeout: timeoutMs });
    // Navigate to the direct URL — Chrome will trigger a download for ZIP files.
    // page.goto throws "Download is starting" when the response is a download
    // instead of a page — this is expected, the download event still fires.
    try {
      await dlPage.goto(url, { waitUntil: 'commit', timeout: 30000 });
    } catch (e) {
      if (!/download is starting/i.test(e.message)) throw e;
    }
    const download = await downloadPromise;
    // Wait for the download to complete and save
    await download.saveAs(savePath);
    const suggested = download.suggestedFilename();
    return { saved: savePath, suggested };
  } finally {
    await dlPage.close().catch(() => {});
  }
}

/** Check if a file with the serial name already exists in DOWNLOAD_DIR. */
function fileExists(serial) {
  for (const ext of ['zip', 'rar', '7z', 'chd', 'iso']) {
    const p = path.join(DOWNLOAD_DIR, `${serial}.${ext}`);
    if (fs.existsSync(p) && fs.statSync(p).size > 1024) return p;
  }
  return null;
}

/**
 * Run the romspure AJAX flow from inside the browser page so that
 * Cloudflare cookies and headers are present.
 * Returns { url, name, size } or throws.
 */
async function getDirectLinkInPage(page, downloadPageUrl, postId, index) {
  return await page.evaluate(async ({ downloadPageUrl, postId, index }) => {
    const AJAX = 'https://romspure.cc/wp-admin/admin-ajax.php';
    const formPost = (body) => fetch(AJAX, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest',
      },
      referrer: downloadPageUrl,
      body,
    }).then(r => r.json());

    // 1. nonce
    const nonceRes = await formPost('action=romspure_get_nonce');
    const nonce = nonceRes && nonceRes.data && nonceRes.data.nonce;
    if (!nonce) throw new Error('no nonce: ' + JSON.stringify(nonceRes));

    // 2. download link
    const dlRes = await formPost(
      'action=app_get_download_link&post_id=' + encodeURIComponent(postId) +
      '&index=' + encodeURIComponent(index) + '&nonce=' + encodeURIComponent(nonce)
    );
    if (!dlRes || !dlRes.data || !dlRes.data.url) {
      throw new Error('no dl url: ' + JSON.stringify(dlRes));
    }
    return dlRes.data;
  }, { downloadPageUrl, postId, index });
}

async function processGame(browser, game, state) {
  const { url: gameUrl, serial } = game;
  console.log(`\n=== ${serial} ===`);
  console.log(`  Page: ${gameUrl}`);

  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    acceptDownloads: true,
  });
  const page = await context.newPage();

  try {
    // 1. Navigate to the game page
    await page.goto(gameUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(1500);

    // 2. Find the /download/ link on the page
    let dlLink = await page.evaluate(() => {
      const a = document.querySelector('a[href*="/download/"]');
      return a ? a.href : null;
    });

    if (!dlLink) {
      // Some pages render the button after a moment / via JS
      await sleep(2500);
      dlLink = await page.evaluate(() => {
        const a = document.querySelector('a[href*="/download/"]');
        return a ? a.href : null;
      });
    }

    if (!dlLink) {
      // Try clicking a "Download" button which may reveal the link
      const btn = await page.$('a:has-text("Download"), button:has-text("Download"), a:has-text("Download Now")');
      if (btn) {
        await btn.click().catch(() => {});
        await sleep(2000);
        dlLink = await page.evaluate(() => {
          const a = document.querySelector('a[href*="/download/"]');
          return a ? a.href : null;
        });
      }
    }

    if (!dlLink) {
      throw new Error('no /download/ link found on game page');
    }
    console.log(`  Download page link: ${dlLink}`);

    // Extract postId from the link (trailing -NNNN)
    const postIdMatch = dlLink.match(/-(\d+)\/?$/);
    if (!postIdMatch) throw new Error('cannot parse postId from ' + dlLink);
    const postId = postIdMatch[1];
    console.log(`  Post ID: ${postId}`);

    // 3. Navigate to the download page (index 1) to establish cookies
    const downloadPageUrl = dlLink.endsWith('/') ? dlLink + '1' : dlLink + '/1';
    await page.goto(downloadPageUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(1500);

    // 4. Try clicking "Download Now" if present (some pages need it)
    const dlBtn = await page.$('a:has-text("Download"), button:has-text("Download"), a:has-text("Download Now"), .download-btn, #download');
    if (dlBtn) {
      console.log('  Found Download button on download page');
    }

    // 5. Get the direct link via in-page AJAX (index 1, then mirror 2)
    // Retry on rate-limit ("Action too quick") with exponential backoff.
    let dlData = null;
    for (const idx of [1, 2]) {
      for (let attempt = 0; attempt < 4; attempt++) {
        try {
          const dpUrl = dlLink.endsWith('/') ? dlLink + idx : dlLink + '/' + idx;
          if (attempt === 0 && idx === 2) {
            await page.goto(dpUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
            await sleep(1000);
          }
          dlData = await getDirectLinkInPage(page, dpUrl, postId, idx);
          console.log(`  Direct link (index ${idx}): ${dlData.name} | ${dlData.size}`);
          console.log(`  URL: ${dlData.url.substring(0, 100)}...`);
          break;
        } catch (e) {
          const slow = /slow down|too quick/i.test(e.message);
          console.log(`  index ${idx} attempt ${attempt + 1} failed: ${e.message}`);
          if (!slow || attempt === 3) break;
          const wait = 8000 * (attempt + 1);
          console.log(`  rate-limited, waiting ${wait / 1000}s before retry...`);
          await sleep(wait);
        }
      }
      if (dlData) break;
    }

    if (!dlData || !dlData.url) {
      throw new Error('could not obtain direct download URL');
    }

    // 6. Determine extension and filename
    const ext = extFromUrl(dlData.url);
    const outName = `${serial}.${ext}`;
    console.log(`  Output: ${outName}`);

    // 7. Collect cookies for aria2c fallback
    const cookies = await context.cookies();
    const cookieHeader = cookies
      .filter(c => c.domain.includes('romspure') || c.domain.includes('.'))
      .map(c => `${c.name}=${c.value}`)
      .join('; ');

    // 8. Download via Playwright (primary) — browser sends correct headers
    const savePath = path.join(DOWNLOAD_DIR, outName);
    let downloaded = false;
    try {
      console.log(`  Downloading via Playwright (may take a while for large files)...`);
      const result = await downloadViaPlaywright(context, dlData.url, savePath, 600000);
      const stat = fs.statSync(savePath);
      console.log(`  -> Saved: ${savePath} (${(stat.size / 1e6).toFixed(1)} MB)`);
      state.done.push(serial);
      state.results.push({ serial, url: dlData.url, name: dlData.name, size: dlData.size, out: outName, saved: savePath });
      downloaded = true;
    } catch (e) {
      console.log(`  Playwright download failed: ${e.message}`);
    }

    // 9. Fallback: aria2c with Referer header
    if (!downloaded) {
      try {
        const gid = await aria2AddUri(dlData.url, outName, cookieHeader, downloadPageUrl);
        console.log(`  -> aria2c fallback GID=${gid} (with Referer)`);
        state.done.push(serial);
        state.results.push({ serial, url: dlData.url, name: dlData.name, size: dlData.size, gid, out: outName });
      } catch (e) {
        console.log(`  aria2c also failed: ${e.message}`);
        throw new Error('all download methods failed: ' + e.message);
      }
    }
  } catch (e) {
    console.log(`  FAILED: ${e.message}`);
    state.failed.push({ serial, error: e.message });
  } finally {
    await context.close().catch(() => {});
  }
}

async function main() {
  if (!fs.existsSync(DOWNLOAD_DIR)) fs.mkdirSync(DOWNLOAD_DIR, { recursive: true });

  // If command-line serials are provided, filter GAMES to only those
  const argSerials = process.argv.slice(2);
  let gamesToProcess = GAMES;
  if (argSerials.length > 0) {
    gamesToProcess = GAMES.filter(g => argSerials.includes(g.serial));
    const found = gamesToProcess.map(g => g.serial);
    const missing = argSerials.filter(s => !found.includes(s));
    if (missing.length > 0) {
      console.log(`WARNING: serials not found in GAMES list: ${missing.join(', ')}`);
    }
    console.log(`Filtered to ${gamesToProcess.length} games: ${found.join(', ')}`);
  }

  const state = loadState();
  // Reconcile: only keep "done" entries whose file actually exists
  const validDone = state.done.filter(s => fileExists(s));
  if (validDone.length !== state.done.length) {
    console.log(`Reconciling state: ${state.done.length - validDone.length} entries have no file, will re-download`);
    state.done = validDone;
    state.results = state.results.filter(r => fileExists(r.serial));
    state.failed = state.failed.filter(f => !validDone.includes(f.serial));
  }
  const doneSet = new Set(state.done);

  const browser = await chromium.launch({
    headless: false,
    args: ['--disable-blink-features=AutomationControlled'],
  });

  console.log(`Total games: ${gamesToProcess.length} | already done: ${doneSet.size}`);

  try {
    for (let i = 0; i < gamesToProcess.length; i++) {
      const game = gamesToProcess[i];
      console.log(`\n--- ${i + 1}/${gamesToProcess.length} ---`);
      if (doneSet.has(game.serial)) {
        console.log(`  ${game.serial} already done, skipping`);
        continue;
      }
      await processGame(browser, game, state);
      saveState(state);
      await sleep(2500);
    }
  } finally {
    await browser.close().catch(() => {});
    saveState(state);
  }

  console.log('\n=== FINAL SUMMARY ===');
  console.log(`Done:   ${state.done.length}/${gamesToProcess.length}`);
  console.log(`Failed: ${state.failed.length}`);
  if (state.failed.length) {
    console.log('Failed list:');
    state.failed.forEach(f => console.log(`  ${f.serial}: ${f.error}`));
  }
  console.log('\nResults:');
  state.results.forEach(r => console.log(`  ${r.serial}: ${r.out || r.url}`));
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
