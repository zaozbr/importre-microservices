const axios = require('axios');
const cheerio = require('cheerio');
const SERIAL_RE = /[\(\[]([A-Z]{4})[-\s]?(\d{3,5})[\)\]]/i;
axios.get('https://web.archive.org/web/2025/https://myrient.erista.me/files/Redump/Sony%20-%20PlayStation/', {
  headers: { 'User-Agent': 'Mozilla/5.0' }, timeout: 30000, maxRedirects: 5
}).then(r => {
  console.log('Final URL:', r.request?.res?.responseUrl || 'unknown');
  const $ = cheerio.load(r.data);
  let total = 0, withSerial = 0;
  const examples = [];
  $('a').each((_, el) => {
    const h = $(el).attr('href');
    if (!h || !/\.(zip|chd)$/i.test(h)) return;
    total++;
    let name;
    try { name = decodeURIComponent(h); } catch (e) { name = h; }
    if (SERIAL_RE.test(name)) {
      withSerial++;
      if (examples.length < 10) examples.push(name);
    }
  });
  console.log('total:', total, 'with serial:', withSerial);
  examples.forEach(e => console.log('  ', e));
}).catch(e => console.error('ERR', e.message));
