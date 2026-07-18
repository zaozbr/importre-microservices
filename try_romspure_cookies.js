const axios = require('axios');
const https = require('https');

const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9'
};

async function main() {
  // Step 1: Fetch game page to get cookies
  const gameUrl = 'https://romspure.cc/roms/sony-playstation/senryaku-shougi/';
  console.log('Step 1: Fetching game page...');
  const r1 = await axios.get(gameUrl, { timeout: 15000, headers });
  const cookies = r1.headers['set-cookie'];
  console.log('Cookies:', cookies);

  // Extract download link from game page
  const dlLinks = [...r1.data.matchAll(/href="([^"]*\/download\/[^"]*)"/gi)].map(m => m[1]);
  console.log('Download links:', dlLinks);

  if (dlLinks.length === 0) {
    console.log('No download link found');
    return;
  }

  // Step 2: Fetch download page with cookies and referer
  const dlUrl = dlLinks[0];
  console.log('Step 2: Fetching download page:', dlUrl);
  const cookieStr = cookies ? cookies.map(c => c.split(';')[0]).join('; ') : '';
  const r2 = await axios.get(dlUrl, {
    timeout: 15000,
    headers: { ...headers, Referer: gameUrl, Cookie: cookieStr },
    maxRedirects: 0,
    validateStatus: () => true
  });
  console.log('Status:', r2.status, 'Location:', r2.headers.location);

  if (r2.status === 200) {
    const h = r2.data;
    // Find direct file links
    const fileLinks = [...h.matchAll(/href="([^"]*\.(zip|rar|7z|iso|bin)[^"]*)"/gi)].map(m => m[1]);
    console.log('File links:', fileLinks.slice(0, 5));
    // Find meta refresh
    const meta = h.match(/<meta[^>]*url=([^"']*)["']/i);
    if (meta) console.log('Meta refresh:', meta[1]);
    // Find download buttons
    const btns = [...h.matchAll(/<a[^>]*class="[^"]*download[^"]*"[^>]*href="([^"]*)"/gi)].map(m => m[1]);
    console.log('Download buttons:', btns.slice(0, 5));
    // Find data attributes
    const dataAttrs = [...h.matchAll(/data-(?:download|file|url)="([^"]*)"/gi)].map(m => m[1]);
    console.log('Data attrs:', dataAttrs.slice(0, 5));
  } else if (r2.status === 302 || r2.status === 301) {
    console.log('Redirect to:', r2.headers.location);
  }
}
main().catch(e => console.log('Error:', e.message));
