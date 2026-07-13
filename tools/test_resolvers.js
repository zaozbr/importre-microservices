const axios = require('axios');
const cheerio = require('cheerio');

async function testVimm() {
  try {
    const r = await axios.get('https://vimm.net/vault/1', {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
      timeout: 15000
    });
    const $ = cheerio.load(r.data);
    const links = [];
    $('a[href]').each((i, el) => {
      const h = $(el).attr('href');
      const text = $(el).text().trim();
      if (h && (h.includes('download') || h.includes('media') || h.endsWith('.7z') || h.endsWith('.zip'))) {
        links.push({ href: h, text });
      }
    });
    console.log('Vimm download links:', JSON.stringify(links.slice(0, 10), null, 2));
    
    // Tambem procura forms
    const forms = [];
    $('form').each((i, el) => {
      const action = $(el).attr('action');
      const method = $(el).attr('method');
      forms.push({ action, method });
    });
    console.log('Forms:', JSON.stringify(forms.slice(0, 5), null, 2));
  } catch (e) {
    console.log('Vimm err:', e.message);
  }
}

async function testRetroiso() {
  try {
    const fs = require('fs');
    const cache = JSON.parse(fs.readFileSync('D:/roms/library/roms/_importre_state/retroiso_cache.json', 'utf-8'));
    const first = Object.entries(cache)[0];
    console.log('Retroiso sample:', first[0], first[1]);
    const r = await axios.get(first[1], {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
      timeout: 15000
    });
    const $ = cheerio.load(r.data);
    const links = [];
    $('a[href]').each((i, el) => {
      const h = $(el).attr('href');
      if (h && (h.endsWith('.7z') || h.endsWith('.zip') || h.endsWith('.rar') || h.endsWith('.iso') || h.includes('download'))) {
        links.push(h);
      }
    });
    console.log('Retroiso links:', links.slice(0, 10));
  } catch (e) {
    console.log('Retroiso err:', e.message);
  }
}

testVimm().then(() => testRetroiso());
