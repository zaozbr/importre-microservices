const axios = require('axios');

const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9',
  'Referer': 'https://romspure.cc/download/senryaku-shougi-124778'
};

async function tryDl(url) {
  console.log(`\nTrying: ${url}`);
  try {
    const r = await axios.get(url, { timeout: 15000, headers, maxRedirects: 0, validateStatus: () => true });
    console.log('Status:', r.status, 'Location:', r.headers.location);

    if (r.status === 200) {
      // Look for meta refresh or JS redirect
      const meta = r.data.match(/<meta[^>]*http-equiv="refresh"[^>]*content="[^;]*;url=([^"']*)"/i);
      if (meta) console.log('Meta refresh to:', meta[1]);

      const jsRedirect = r.data.match(/(?:window\.location|location\.href)\s*=\s*["']([^"']*)/i);
      if (jsRedirect) console.log('JS redirect to:', jsRedirect[1]);

      // Find direct file URLs
      const fileUrls = [...r.data.matchAll(/https?:\/\/[^\s"'<>]+\.(zip|rar|7z|iso|bin)/gi)].map(m => m[0]);
      if (fileUrls.length) console.log('File URLs:', fileUrls);

      // Find download links
      const dlLinks = [...r.data.matchAll(/href="([^"]*download[^"]*)"/gi)].map(m => m[1]);
      if (dlLinks.length) console.log('Download links:', dlLinks.slice(0, 5));

      // Check for AJAX
      const ajax = r.data.match(/admin-ajax\.php[^"']*/gi);
      if (ajax) console.log('AJAX endpoints:', [...new Set(ajax)].slice(0, 3));

      console.log('Page length:', r.data.length);
      // Save for inspection
      const fname = url.split('/').pop();
      require('fs').writeFileSync(`F:/importre/dl_page_${fname}.html`, r.data);
    }
  } catch (e) {
    console.log('Error:', e.message);
  }
}

async function main() {
  await tryDl('https://romspure.cc/download/senryaku-shougi-124778/1');
  await tryDl('https://romspure.cc/download/senryaku-shougi-124778/2');
}
main();
