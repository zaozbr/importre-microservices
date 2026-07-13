const axios = require('axios');
const cheerio = require('cheerio');

async function testVimm() {
  console.log('=== TESTE VIMM COMPLETO ===');
  const pageUrl = 'https://vimm.net/vault/5960';
  const headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' };
  
  // 1. GET pagina - pega cookies
  const jar = {};
  const res = await axios.get(pageUrl, { 
    headers, 
    timeout: 20000,
    maxRedirects: 5
  });
  
  // Salva cookies
  const setCookies = res.headers['set-cookie'];
  if (setCookies) {
    for (const c of (Array.isArray(setCookies) ? setCookies : [setCookies])) {
      const match = c.match(/^([^=]+)=([^;]*)/);
      if (match) jar[match[1]] = match[2];
    }
  }
  console.log('Cookies:', Object.keys(jar));
  
  const $ = cheerio.load(res.data);
  
  // Extrai mediaId
  const scriptText = $('script').map((i, el) => $(el).html()).get().join('\n');
  const mediaMatch = scriptText.match(/"ID":(\d+)/);
  const mediaId = mediaMatch ? mediaMatch[1] : null;
  console.log('mediaId:', mediaId);
  
  // Extrai Serial
  const serialMatch = scriptText.match(/"Serial":"([^"]+)"/);
  console.log('Serial:', serialMatch ? serialMatch[1] : 'not found');
  
  // Procura form action
  const form = $('form#dl_form');
  console.log('Form dl_form found:', form.length > 0);
  if (form.length) {
    console.log('Form action:', form.attr('action'));
    console.log('Form method:', form.attr('method'));
    const inputs = {};
    form.find('input').each((i, el) => {
      const name = $(el).attr('name');
      const value = $(el).attr('value');
      if (name) inputs[name] = value;
    });
    console.log('Form inputs:', JSON.stringify(inputs));
  }
  
  // Procura mirror button
  const mirrorBtn = $('[data-mirror]');
  if (mirrorBtn.length) {
    console.log('Mirror button data-mirror:', mirrorBtn.attr('data-mirror'));
    console.log('Mirror onclick:', mirrorBtn.attr('onclick'));
  }
  
  // Tenta GET no dl3 com cookies
  if (mediaId) {
    console.log('\nTentando GET dl3.vimm.net com cookies...');
    const cookieStr = Object.entries(jar).map(([k,v]) => `${k}=${v}`).join('; ');
    try {
      const dlRes = await axios.get(`https://dl3.vimm.net/?mediaId=${mediaId}&alt=0`, {
        headers: { ...headers, 'Referer': pageUrl, 'Cookie': cookieStr },
        timeout: 15000,
        maxRedirects: 0,
        validateStatus: s => s < 500,
        responseType: 'stream'
      });
      console.log('GET dl3 status:', dlRes.status, 'Content-Type:', dlRes.headers['content-type']);
      console.log('Location:', dlRes.headers.location);
    } catch (e) {
      console.log('GET dl3 error:', e.message, e.response?.status, e.response?.headers?.location);
    }
  }
}

testVimm().catch(e => console.log('Error:', e.message));
