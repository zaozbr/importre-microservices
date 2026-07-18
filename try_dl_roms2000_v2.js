const axios = require('axios');
const fs = require('fs');

const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9'
};

async function fetchPage(url, referer) {
  const h = { ...headers, Referer: referer };
  try {
    const r = await axios.get(url, { timeout: 15000, headers: h, validateStatus: () => true });
    console.log('Status:', r.status, 'URL:', url);
    if (r.status === 200) {
      const html = r.data;
      // Find all links
      const allLinks = [...html.matchAll(/href="([^"]*)"/gi)].map(m => m[1]);
      const dlLinks = allLinks.filter(u => u.includes('download') || u.match(/\.(zip|rar|7z|iso|bin)/i));
      console.log('DL links:', dlLinks.slice(0, 10));
      // Find meta refresh
      const meta = html.match(/<meta[^>]*http-equiv=["']refresh["'][^>]*content=["'][^;]*;url=([^"']*)["']/i);
      if (meta) console.log('Meta refresh:', meta[1]);
      // Find direct file URLs
      const fileUrls = allLinks.filter(u => u.includes('.zip') || u.includes('.rar') || u.includes('.7z') || u.includes('.iso'));
      console.log('File URLs:', fileUrls.slice(0, 5));
      // Save HTML
      fs.writeFileSync('F:/importre_state/roms2000_dl.html', html);
      return dlLinks;
    }
  } catch (e) {
    console.log('Error:', e.message, e.response && e.response.status);
  }
  return [];
}

async function main() {
  // Try second-level download page
  const links = await fetchPage(
    'https://roms2000.com/download/roms//poketan',
    'https://www.roms2000.com/download/roms/playstation/poketan'
  );

  // If there are more links, try them
  for (const link of links.slice(0, 3)) {
    const fullUrl = link.startsWith('http') ? link : ('https://roms2000.com' + link);
    console.log('\nTrying next level:', fullUrl);
    await fetchPage(fullUrl, 'https://roms2000.com/download/roms//poketan');
  }
}
main();
