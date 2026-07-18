const axios = require('axios');

const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9'
};

async function searchGame(query) {
  const url = 'https://romspure.cc/?s=' + encodeURIComponent(query);
  const r = await axios.get(url, { headers, timeout: 15000 });

  // Find game page links (exclude category links)
  const links = [...r.data.matchAll(/href="(https:\/\/romspure\.cc\/roms\/sony-playstation\/[^"]+)"/gi)].map(m => m[1]);
  const unique = [...new Set(links)];

  // Find post IDs
  const postIds = [...r.data.matchAll(/data-post-id="(\d+)"/gi)].map(m => m[1]);

  // Find titles
  const titles = [...r.data.matchAll(/<h[23][^>]*>\s*<a[^>]*>([^<]+)<\/a>/gi)].map(m => m[1].trim());

  return { links: unique, postIds: [...new Set(postIds)], titles };
}

async function main() {
  // Search by game name
  const searches = [
    'senryaku shougi',
    'zeiramzone',
    'hunter x hunter',
    'wanders',
    'puzzle bobble',
    'magical drop',
    'gunbird',
    'strider',
    'castlevania',
    'mega man',
    'breath of fire',
    'suikoden',
    'vagrant story',
    'parasite eve',
    'chrono cross',
    'xenogears',
    'final fantasy',
    'dragon quest',
    'metal slug',
    'king of fighters'
  ];

  for (const q of searches) {
    console.log(`\nSearch: "${q}"`);
    try {
      const result = await searchGame(q);
      console.log(`  Links: ${result.links.length}, Titles: ${result.titles.length}`);
      result.links.slice(0, 3).forEach(l => console.log('    ', l));
      result.titles.slice(0, 3).forEach(t => console.log('    Title:', t));
    } catch (e) {
      console.log(`  Error: ${e.message}`);
    }
  }
}
main().catch(e => console.log('Fatal:', e.message));
