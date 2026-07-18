const axios = require('axios');
const querystring = require('querystring');

const AJAX_URL = 'https://romspure.cc/wp-admin/admin-ajax.php';
const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9'
};

async function searchGame(query) {
  const url = 'https://romspure.cc/?s=' + encodeURIComponent(query);
  const r = await axios.get(url, { headers, timeout: 15000 });

  // Find game page links
  const links = [...r.data.matchAll(/href="(https:\/\/romspure\.cc\/roms\/[^"]+)"/gi)].map(m => m[1]);
  const unique = [...new Set(links)];

  // Also try to find post IDs from the page
  const postIds = [...r.data.matchAll(/data-post-id="(\d+)"/gi)].map(m => m[1]);

  return { links: unique, postIds: [...new Set(postIds)] };
}

async function getDownloadLink(postId, index) {
  // Get nonce
  const nr = await axios.post(AJAX_URL, querystring.stringify({ action: 'romspure_get_nonce' }), {
    headers: { ...headers, 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest' },
    timeout: 15000
  });
  const nonce = nr.data.data.nonce;

  // Get download link
  const body = querystring.stringify({
    action: 'app_get_download_link',
    post_id: String(postId),
    index: String(index),
    nonce: nonce
  });
  const dr = await axios.post(AJAX_URL, body, {
    headers: { ...headers, 'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest', 'Referer': 'https://romspure.cc/' },
    timeout: 15000
  });
  return dr.data.data;
}

async function main() {
  const targets = [
    { code: 'SLPS-00142', name: 'senryaku-shougi' },
    { code: 'SLPS-02895', name: '' },
    { code: 'SLPM-87255', name: '' },
    { code: 'SLPM-86274', name: '' },
    { code: 'SCPS-10108', name: '' },
    { code: 'SLPM-86148', name: '' },
    { code: 'SLPS-00575', name: 'zeiramzone' },
    { code: 'SLPM-86895', name: 'hunter-x-hunter' }
  ];

  for (const t of targets) {
    const query = t.code.replace('-', ' ');
    console.log(`\nSearching for ${t.code}...`);
    try {
      const result = await searchGame(query);
      console.log(`  Links: ${result.links.length}`);
      result.links.slice(0, 5).forEach(l => console.log('    ', l));

      // Try to find the game page and extract post ID
      for (const link of result.links.slice(0, 3)) {
        const pageR = await axios.get(link, { headers, timeout: 15000 });
        const postIdMatch = pageR.data.match(/data-post-id="(\d+)"/);
        const dlLinkMatch = pageR.data.match(/href="(https:\/\/romspure\.cc\/download\/[^"]+)"/);
        if (postIdMatch && dlLinkMatch) {
          const postId = postIdMatch[1];
          const dlLink = dlLinkMatch[1];
          console.log(`  Post ID: ${postId}, DL link: ${dlLink}`);

          // Get actual download URL
          try {
            const dl = await getDownloadLink(postId, 1);
            console.log(`  ACTUAL URL: ${dl.url}`);
            console.log(`  Name: ${dl.name}, Size: ${dl.size}`);
          } catch (e) {
            console.log(`  Failed to get download link: ${e.message}`);
          }
          break;
        }
      }
    } catch (e) {
      console.log(`  Error: ${e.message}`);
    }
  }
}
main().catch(e => console.log('Fatal:', e.message));
