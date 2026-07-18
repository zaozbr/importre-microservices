const axios = require('axios');
const querystring = require('querystring');
const fs = require('fs');

const AJAX_URL = 'https://romspure.cc/wp-admin/admin-ajax.php';
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0';

// Load missing games
const missing = JSON.parse(fs.readFileSync('F:/importre_state/missing_analysis.json', 'utf8'));
const reallyMissing = missing.really_missing;

// Load already processed
const batch = JSON.parse(fs.readFileSync('F:/importre_state/romspure_batch_results.json', 'utf8'));
const processed = new Set([...batch.results.map(r => r.serial), ...batch.errors]);

// Filter JP games not yet processed
const jpGames = Object.entries(reallyMissing).filter(([k]) =>
  (k.startsWith('SLPS') || k.startsWith('SCPS') || k.startsWith('SLPM')) && !processed.has(k)
);

console.log(`Remaining JP games to search: ${jpGames.length}`);

function simplifyName(name) {
  let n = name.replace(/\[.*?\]/gi, '').replace(/\(.*?\)/gi, '');
  n = n.replace(/Playstation The Best/i, '').replace(/PSone Books/i, '');
  n = n.replace(/Bandai The Best/i, '').replace(/Reprint/i, '');
  n = n.replace(/Value 1500/i, '').replace(/Nice Price Vol\.\d+/i, '');
  n = n.replace(/SuperLite 1500 Series/i, '').replace(/Simple 1500 Series Vol\.\d+/i, '');
  n = n.replace(/ASCII Casual Collection/i, '').replace(/Artdink Best Choice/i, '');
  n = n.replace(/SNK Best Collec/i, '').replace(/Collectors Edition/i, '');
  n = n.replace(/Limited Edition/i, '').replace(/Popular Edition/i, '');
  n = n.replace(/1300yen Release/i, '').replace(/Complete Works/i, '');
  n = n.replace(/Deluxe Pack/i, '').replace(/Deluxe Version/i, '');
  n = n.replace(/Anniversary Package/i, '');
  n = n.trim();
  const words = n.split(/\s+/).filter(w => w.length > 1);
  return words.slice(0, 4).join(' ');
}

async function searchRomspure(query) {
  const url = 'https://romspure.cc/?s=' + encodeURIComponent(query);
  const r = await axios.get(url, {
    headers: { 'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml' },
    timeout: 15000
  });
  return [...new Set([...r.data.matchAll(/href="(https:\/\/romspure\.cc\/roms\/sony-playstation\/[^"]+)"/gi)].map(m => m[1]))];
}

async function getDownloadLink(postId, index, downloadPageUrl) {
  const pageR = await axios.get(downloadPageUrl, {
    headers: { 'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml' },
    timeout: 15000, maxRedirects: 5
  });
  const cookies = pageR.headers['set-cookie'];
  const cookieStr = cookies ? cookies.map(c => c.split(';')[0]).join('; ') : '';

  const nonceR = await axios.post(AJAX_URL, querystring.stringify({ action: 'romspure_get_nonce' }), {
    headers: { 'User-Agent': UA, 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://romspure.cc', 'Referer': downloadPageUrl, 'Cookie': cookieStr },
    timeout: 15000
  });
  const nonce = nonceR.data.data.nonce;

  const body = querystring.stringify({ action: 'app_get_download_link', post_id: String(postId), index: String(index), nonce });
  const dlR = await axios.post(AJAX_URL, body, {
    headers: { 'User-Agent': UA, 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://romspure.cc', 'Referer': downloadPageUrl, 'Cookie': cookieStr },
    timeout: 15000
  });
  return dlR.data.data;
}

async function addToAria2(url, filename) {
  const params = ['token:devin', [url], { dir: 'F:/downloads', out: filename }];
  const r = await axios.post('http://127.0.0.1:6800/jsonrpc', { jsonrpc: '2.0', method: 'aria2.addUri', id: '1', params });
  return r.data.result;
}

async function processGame(serial, title) {
  const searchName = simplifyName(title);
  console.log(`\n[${serial}] Search: "${searchName}"`);

  try {
    const links = await searchRomspure(searchName);
    if (links.length === 0) {
      console.log(`  No results`);
      return null;
    }

    for (const link of links.slice(0, 2)) {
      const pageR = await axios.get(link, {
        headers: { 'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml' },
        timeout: 15000
      });
      const dlLinkMatch = pageR.data.match(/href="(https:\/\/romspure\.cc\/download\/[^"]+)"/);
      if (!dlLinkMatch) continue;

      const dlLink = dlLinkMatch[1];
      const postIdMatch = dlLink.match(/-(\d+)$/);
      if (!postIdMatch) continue;

      const postId = postIdMatch[1];
      try {
        const dl = await getDownloadLink(postId, 1, dlLink + '/1');
        console.log(`  Found: ${dl.name} (${dl.size})`);
        const filename = dl.url.split('/').pop().split('?')[0];
        const gid = await addToAria2(dl.url, filename);
        console.log(`  Added to aria2c: GID=${gid}`);
        return { serial, url: dl.url, name: dl.name, size: dl.size, gid };
      } catch (e) {
        try {
          const dl2 = await getDownloadLink(postId, 2, dlLink + '/2');
          console.log(`  Found (mirror): ${dl2.name} (${dl2.size})`);
          const filename = dl2.url.split('/').pop().split('?')[0];
          const gid = await addToAria2(dl2.url, filename);
          console.log(`  Added to aria2c: GID=${gid}`);
          return { serial, url: dl2.url, name: dl2.name, size: dl2.size, gid };
        } catch (e2) {
          console.log(`  Download failed: ${e.message}`);
        }
      }
    }
  } catch (e) {
    console.log(`  Error: ${e.message}`);
  }
  return null;
}

async function main() {
  const results = [...batch.results];
  const errors = [...batch.errors];

  for (let i = 0; i < jpGames.length; i++) {
    const [serial, title] = jpGames[i];
    console.log(`\n--- ${i + 1}/${jpGames.length} ---`);

    const result = await processGame(serial, title);
    if (result) {
      results.push(result);
    } else {
      errors.push(serial);
    }

    if ((i + 1) % 5 === 0) {
      fs.writeFileSync('F:/importre_state/romspure_batch_results.json', JSON.stringify({ results, errors, processed: results.length + errors.filter(e => !results.some(r => r.serial === e)).length, total: 307 }, null, 2));
    }

    await new Promise(r => setTimeout(r, 1500));
  }

  fs.writeFileSync('F:/importre_state/romspure_batch_results.json', JSON.stringify({ results, errors, processed: results.length + errors.length, total: 307 }, null, 2));

  console.log(`\n=== FINAL SUMMARY ===`);
  console.log(`Found: ${results.length}/${307}`);
  console.log(`Not found: ${errors.length}`);
}
main().catch(e => console.log('Fatal:', e.message));
