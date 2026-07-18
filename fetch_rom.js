const axios = require('axios');
const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9'
};

async function main() {
  const url = process.argv[2] || 'https://romspure.cc/roms/sony-playstation/senryaku-shougi/';
  try {
    const r = await axios.get(url, { timeout: 15000, headers, maxRedirects: 5 });
    const h = r.data;
    // Find download links
    const dlLinks = [];
    const dlMatches = h.matchAll(/href=["']([^"']*download[^"']*)["']/gi);
    for (const m of dlMatches) dlLinks.push(m[1]);
    console.log('Download links:', dlLinks.slice(0, 10));

    // Find form actions
    const forms = [];
    const formMatches = h.matchAll(/<form[^>]*action=["']([^"']*)["']/gi);
    for (const m of formMatches) forms.push(m[1]);
    console.log('Forms:', forms.slice(0, 5));

    // Find data-url attributes
    const dataUrls = [];
    const dataMatches = h.matchAll(/data-[a-z]*url=["']([^"']*)["']/gi);
    for (const m of dataMatches) dataUrls.push(m[1]);
    console.log('Data URLs:', dataUrls.slice(0, 5));

    // Find links with "download" class
    const btns = [];
    const btnMatches = h.matchAll(/<a[^>]*class=["'][^"']*download[^"']*["'][^>]*>/gi);
    for (const m of btnMatches) btns.push(m[0]);
    console.log('Download buttons:', btns.slice(0, 5));

    // Find any links with .zip, .rar, .7z, .iso
    const archLinks = [];
    const archMatches = h.matchAll(/href=["']([^"']*\.(zip|rar|7z|iso|bin)["])/gi);
    for (const m of archMatches) archLinks.push(m[1]);
    console.log('Archive links:', archLinks.slice(0, 10));

  } catch (e) {
    console.log('Error:', e.message, e.response && e.response.status);
  }
}
main();
