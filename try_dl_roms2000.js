const axios = require('axios');
const fs = require('fs');

const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9',
  'Referer': 'https://www.roms2000.com/poketan-playstation-rom'
};

async function tryDownload(url, outName, referer) {
  const h = { ...headers, Referer: referer };
  console.log('Trying:', url);
  try {
    const r = await axios.get(url, { timeout: 30000, headers: h, responseType: 'stream', maxRedirects: 10 });
    const size = parseInt(r.headers['content-length'] || 0);
    const ct = r.headers['content-type'] || '';
    console.log('Status:', r.status, 'Size:', Math.round(size / 1048576) + 'MB', 'Type:', ct);

    if (ct.includes('text/html')) {
      let body = '';
      r.data.on('data', d => body += d);
      r.data.on('end', () => {
        const links = [...body.matchAll(/href="([^"]*download[^"]*)"/gi)].map(m => m[1]);
        const metaRefresh = body.match(/<meta[^>]*url=([^"']*)["']/i);
        console.log('HTML page - links:', links.slice(0, 5), 'meta:', metaRefresh ? metaRefresh[1] : 'none');
      });
      return;
    }

    const outPath = 'F:/downloads/' + outName;
    const ws = fs.createWriteStream(outPath);
    let received = 0;
    const start = Date.now();
    r.data.on('data', d => {
      received += d.length;
      const speed = Math.round(received / (Date.now() - start) / 1024);
      if (size && Math.round(received / size * 100) % 20 === 0) {
        console.log(Math.round(received / size * 100) + '%', speed + 'KB/s');
      }
    });
    r.data.pipe(ws);
    return new Promise((resolve) => {
      ws.on('finish', () => { console.log('Done! Saved to', outPath); resolve(); });
      ws.on('error', e => { console.log('Write error:', e.message); resolve(); });
    });
  } catch (e) {
    console.log('Error:', e.message, e.response && e.response.status);
    if (e.response && e.response.headers) {
      console.log('Location:', e.response.headers.location);
    }
  }
}

async function main() {
  await tryDownload(
    'https://www.roms2000.com/download/roms/playstation/poketan',
    'SCPS-10108.zip',
    'https://www.roms2000.com/poketan-playstation-rom'
  );
  console.log('---');
  await tryDownload(
    'https://www.roms2000.com/download/roms/playstation/pacapaca-passion-special',
    'SLPS-02895.zip',
    'https://www.roms2000.com/pacapaca-passion-special-playstation-rom'
  );
}
main();
