const axios = require('axios');
const cheerio = require('cheerio');

async function test() {
  const fs = require('fs');
  const cache = JSON.parse(fs.readFileSync('D:/roms/library/roms/_importre_state/vimm_cache.json', 'utf-8'));
  const entry = Object.entries(cache).find(([s]) => s === 'SLUS-00270');
  if (!entry) { console.log('SLUS-00270 not in vimm cache'); return; }
  console.log('Vimm URL:', entry[1]);
  
  const pageUrl = `https://www.vimm.net${entry[1]}`;
  console.log('Page URL:', pageUrl);
  
  const res = await axios.get(pageUrl, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
    timeout: 20000
  });
  const $ = cheerio.load(res.data);
  
  // Procura form POST
  const form = $('form[action*="dl3.vimm.net"]');
  if (form.length) {
    let action = form.attr('action');
    console.log('Form action:', action);
    if (action && action.startsWith('//')) action = 'https:' + action;
    else if (action && action.startsWith('/')) action = 'https://vimm.net' + action;
    console.log('Resolved URL:', action);
    
    // Procura inputs hidden
    const inputs = {};
    form.find('input').each((i, el) => {
      const name = $(el).attr('name');
      const value = $(el).attr('value');
      if (name) inputs[name] = value;
    });
    console.log('Form inputs:', JSON.stringify(inputs));
    
    // Tenta POST
    console.log('\nTentando POST...');
    try {
      const dlRes = await axios.post(action, inputs, {
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
        timeout: 15000,
        maxRedirects: 5,
        responseType: 'stream'
      });
      console.log('POST response status:', dlRes.status);
      console.log('Content-Type:', dlRes.headers['content-type']);
      console.log('Content-Length:', dlRes.headers['content-length']);
    } catch (e) {
      console.log('POST error:', e.message);
      if (e.response) {
        console.log('Status:', e.response.status);
        console.log('Location:', e.response.headers.location);
      }
    }
  } else {
    console.log('No dl3.vimm.net form found');
    // Procura outros links
    $('a[href]').each((i, el) => {
      const h = $(el).attr('href');
      if (h && (h.includes('download') || h.includes('media'))) console.log('Link:', h);
    });
  }
}

test().catch(e => console.log('Error:', e.message));
