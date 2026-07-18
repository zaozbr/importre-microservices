const axios = require('axios');
const fs = require('fs');

const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9'
};

async function main() {
  const gameUrl = 'https://romspure.cc/roms/sony-playstation/senryaku-shougi/';
  const r1 = await axios.get(gameUrl, { timeout: 15000, headers });

  // Find all links on game page
  const allLinks = [...r1.data.matchAll(/href="([^"]*)"/gi)].map(m => m[1]);
  const dlLinks = allLinks.filter(l => l.includes('download') || l.includes('.zip') || l.includes('.rar'));
  console.log('Game page download-related links:', dlLinks);

  // Now fetch the download page
  const dlUrl = 'https://romspure.cc/download/senryaku-shougi-124778';
  const r2 = await axios.get(dlUrl, { timeout: 15000, headers, validateStatus: () => true });

  // Save full HTML for inspection
  fs.writeFileSync('F:/importre/dl_page.html', r2.data);
  console.log('Download page saved. Length:', r2.data.length);

  // Search for any URLs in the page
  const urls = [...r2.data.matchAll(/https?:\/\/[^\s"'<>]+/gi)].map(m => m[0]);
  const uniqueUrls = [...new Set(urls)].filter(u => !u.includes('fonts.') && !u.includes('wp-content') && !u.includes('wp-includes') && !u.includes('gmpg.org') && !u.includes('yoast'));
  console.log('\nNon-asset URLs found:');
  uniqueUrls.forEach(u => console.log('  ', u));

  // Search for download-related text
  const dlText = r2.data.match(/download[^<]*/gi);
  console.log('\nDownload text:', dlText?.slice(0, 10));

  // Search for form actions
  const forms = [...r2.data.matchAll(/<form[^>]*action="([^"]*)"[^>]*>/gi)].map(m => m[1]);
  console.log('\nForm actions:', forms);

  // Search for script blocks with download logic
  const scripts = [...r2.data.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)].map(m => m[1]).filter(s => s.includes('download') || s.includes('file') || s.includes('href'));
  console.log('\nRelevant scripts:');
  scripts.forEach((s, i) => console.log(`Script ${i}:`, s.substring(0, 300)));
}
main().catch(e => console.log('Error:', e.message));
