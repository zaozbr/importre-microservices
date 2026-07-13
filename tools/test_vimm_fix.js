const axios = require('axios');
const cheerio = require('cheerio');

async function testVimm() {
  console.log('=== TESTE VIMM ===');
  const pageUrl = 'https://vimm.net/vault/5960';
  const headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' };
  
  const res = await axios.get(pageUrl, { headers, timeout: 20000 });
  const $ = cheerio.load(res.data);
  
  // Extrai mediaId do JavaScript
  const scriptText = $('script').map((i, el) => $(el).html()).get().join('\n');
  const mediaMatch = scriptText.match(/"ID":(\d+)/);
  const mediaId = mediaMatch ? mediaMatch[1] : null;
  console.log('mediaId:', mediaId);
  
  if (mediaId) {
    // Testa mirror archival.cat
    const mirrorUrl = `https://archival.cat/PS1/${mediaId}.7z`;
    console.log('Mirror URL:', mirrorUrl);
    try {
      const check = await axios.head(mirrorUrl, { 
        headers: { ...headers, 'Referer': 'https://vimm.net/' },
        timeout: 10000, 
        maxRedirects: 5,
        validateStatus: s => s < 500
      });
      console.log('Mirror status:', check.status, 'Content-Type:', check.headers['content-type'], 'Size:', check.headers['content-length']);
    } catch (e) {
      console.log('Mirror error:', e.message);
    }
    
    // Testa POST dl3.vimm.net
    console.log('\nTestando POST dl3.vimm.net...');
    try {
      const postRes = await axios.post('https://dl3.vimm.net/', `mediaId=${mediaId}&alt=0`, {
        headers: { ...headers, 'Referer': pageUrl, 'Content-Type': 'application/x-www-form-urlencoded' },
        timeout: 15000,
        maxRedirects: 5,
        validateStatus: s => s < 500,
        responseType: 'stream'
      });
      console.log('POST status:', postRes.status, 'Content-Type:', postRes.headers['content-type']);
    } catch (e) {
      console.log('POST error:', e.message, e.response?.status);
    }
  }
}

testVimm().catch(e => console.log('Error:', e.message));
