const axios = require('axios');
const querystring = require('querystring');

const AJAX_URL = 'https://romspure.cc/wp-admin/admin-ajax.php';
const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9'
};

// Games we need from romspure (search query -> expected game code)
const TARGETS = [
  { search: 'senryaku shougi', code: 'SLPS-00142' },
  { search: 'zeiramzone', code: 'SLPS-00575' },
  { search: 'hunter x hunter maboroshi', code: 'SLPM-86895' },
];

async function getNonce() {
  const r = await axios.post(AJAX_URL, querystring.stringify({ action: 'romspure_get_nonce' }), {
    headers: { ...headers, 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
    timeout: 15000
  });
  return r.data.data.nonce;
}

async function getDownloadLink(postId, index, nonce) {
  const body = querystring.stringify({
    action: 'app_get_download_link',
    post_id: String(postId),
    index: String(index),
    nonce: nonce
  });
  const r = await axios.post(AJAX_URL, body, {
    headers: { ...headers, 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest', 'Referer': 'https://romspure.cc/' },
    timeout: 15000
  });
  return r.data.data;
}

async function searchAndDownload(searchQuery, code) {
  console.log(`\n=== ${code} (search: "${searchQuery}") ===`);

  // Search for the game
  const searchUrl = 'https://romspure.cc/?s=' + encodeURIComponent(searchQuery);
  const sr = await axios.get(searchUrl, { headers, timeout: 15000 });
  const links = [...new Set([...sr.data.matchAll(/href="(https:\/\/romspure\.cc\/roms\/sony-playstation\/[^"]+)"/gi)].map(m => m[1]))];

  if (links.length === 0) {
    console.log('  No results found');
    return null;
  }

  console.log(`  Found ${links.length} result(s)`);

  // Visit the first result to get download link and extract post ID
  for (const link of links.slice(0, 3)) {
    const pageR = await axios.get(link, { headers, timeout: 15000 });
    const dlLinkMatch = pageR.data.match(/href="(https:\/\/romspure\.cc\/download\/[^"]+)"/);

    if (dlLinkMatch) {
      const dlLink = dlLinkMatch[1];
      // Extract post ID from download URL: /download/{slug}-{postId}
      const postIdMatch = dlLink.match(/-(\d+)$/);
      if (!postIdMatch) {
        console.log('  Could not extract post ID from:', dlLink);
        continue;
      }
      const postId = postIdMatch[1];
      console.log(`  Post ID: ${postId}, Page: ${link}`);

      // Get actual download URL
      const nonce = await getNonce();
      try {
        const dl = await getDownloadLink(postId, 1, nonce);
        console.log(`  URL: ${dl.url}`);
        console.log(`  Name: ${dl.name}, Size: ${dl.size}`);
        return { code, url: dl.url, name: dl.name, size: dl.size };
      } catch (e) {
        console.log(`  Failed to get download link: ${e.message}`);
        // Try index 2
        try {
          const dl2 = await getDownloadLink(postId, 2, nonce);
          console.log(`  URL (mirror): ${dl2.url}`);
          console.log(`  Name: ${dl2.name}, Size: ${dl2.size}`);
          return { code, url: dl2.url, name: dl2.name, size: dl2.size };
        } catch (e2) {
          console.log(`  Mirror also failed: ${e2.message}`);
        }
      }
    }
  }
  return null;
}

async function addToAria2(url, filename) {
  const params = [
    'token:devin',
    [url],
    { dir: 'F:/downloads', out: filename }
  ];
  const r = await axios.post('http://127.0.0.1:6800/jsonrpc', {
    jsonrpc: '2.0', method: 'aria2.addUri', id: '1', params
  });
  return r.data.result;
}

async function main() {
  const results = [];
  for (const t of TARGETS) {
    try {
      const result = await searchAndDownload(t.search, t.code);
      if (result) {
        results.push(result);
        // Add to aria2c
        const filename = result.url.split('/').pop().split('?')[0];
        const gid = await addToAria2(result.url, filename);
        console.log(`  Added to aria2c: GID=${gid}, filename=${filename}`);
      }
    } catch (e) {
      console.log(`  Error: ${e.message}`);
    }
    // Small delay between requests
    await new Promise(r => setTimeout(r, 1000));
  }

  console.log('\n=== Summary ===');
  results.forEach(r => console.log(`  ${r.code}: ${r.url}`));
}
main().catch(e => console.log('Fatal:', e.message));
