const axios = require('axios');
const cheerio = require('cheerio');

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.5',
};

async function debug() {
  const title = 'Crash Bandicoot';
  const q = encodeURIComponent(title.split('(')[0].trim());
  const searchUrl = `https://cdromance.org/?s=${q}`;
  console.log('1. Buscando:', searchUrl);

  const res = await axios.get(searchUrl, { headers: HEADERS, timeout: 15000 });
  console.log('   Status:', res.status, 'Tamanho:', res.data.length);

  const $ = cheerio.load(res.data);

  // Procura todos os links
  const allLinks = [];
  $('a').each((i, el) => {
    const href = $(el).attr('href');
    if (href) allLinks.push(href);
  });
  console.log('   Total links na pagina:', allLinks.length);

  // Procura links psx-iso
  const psxLinks = allLinks.filter(h => h.includes('psx-iso'));
  console.log('   Links psx-iso:', psxLinks.length);
  psxLinks.slice(0, 10).forEach(h => console.log('   ->', h));

  // Procura qualquer link que pareca pagina de jogo
  const gameLinks = allLinks.filter(h => h.includes('cdromance.org') && !h.includes('?s=') && !h.includes('/category/') && !h.includes('/page/'));
  const uniqueGameLinks = [...new Set(gameLinks)];
  console.log('   Links cdromance.org (nao categoria/page):', uniqueGameLinks.length);
  uniqueGameLinks.slice(0, 15).forEach(h => console.log('   ->', h));

  if (!uniqueGameLinks.length) {
    // Vamos ver os primeiros 20 links
    console.log('   Primeiros 20 links:');
    allLinks.slice(0, 20).forEach(h => console.log('   ->', h));
    return;
  }

  // Tenta acessar a primeira pagina de jogo
  const gameUrl = uniqueGameLinks[0];
  console.log('\n2. Acessando pagina do jogo:', gameUrl);
  const gameRes = await axios.get(gameUrl, { headers: HEADERS, timeout: 15000 });
  console.log('   Status:', gameRes.status, 'Tamanho:', gameRes.data.length);
  const $game = cheerio.load(gameRes.data);

  // Procura span#obfuscatedId
  const ticket = $game('#obfuscatedId').text().trim();
  console.log('   Ticket (#obfuscatedId):', ticket ? `"${ticket}"` : 'NAO ENCONTRADO');

  // Procura outros possiveis elementos de ticket
  const ticketAlt = $game('span[id*="obfuscated"]').text().trim();
  console.log('   Ticket alt (span[id*="obfuscated"]):', ticketAlt ? `"${ticketAlt}"` : 'NAO');

  // Procura formularios
  console.log('   Forms na pagina:', $game('form').length);
  $game('form').each((i, el) => {
    const action = $game(el).attr('action');
    const method = $game(el).attr('method');
    const inputs = $game(el).find('input').map((j, inp) => `${$game(inp).attr('name')}=${$game(inp).attr('value')||''}`).get();
    console.log(`   Form ${i}: action=${action} method=${method} inputs=${inputs.join(', ')}`);
  });

  // Procura por "ticket" ou "download" no HTML
  const html = gameRes.data;
  const ticketMatches = html.match(/ticket[^<]*/gi);
  console.log('   Mencoes a "ticket":', ticketMatches ? ticketMatches.slice(0, 5) : 'nenhuma');

  // Procura por cdrTicketInput
  const cdrTicketMatches = html.match(/cdrTicketInput[^<]*/gi);
  console.log('   Mencoes a "cdrTicketInput":', cdrTicketMatches ? cdrTicketMatches.slice(0, 5) : 'nenhuma');

  // Salva HTML para inspecao
  require('fs').writeFileSync('_cdromance_game.html', html);
  console.log('   HTML salvo em _cdromance_game.html');

  if (!ticket) {
    // Procura por data attributes ou hidden inputs
    const hiddenInputs = $game('input[type="hidden"]').map((i, el) => `${$game(el).attr('name')}=${$game(el).attr('value')||''}`).get();
    console.log('   Hidden inputs:', hiddenInputs);

    // Procura por qualquer elemento com "obfuscat" no id ou class
    $game('[id*="obfuscat"], [class*="obfuscat"]').each((i, el) => {
      console.log('   Elemento obfuscat:', $game(el).prop('tagName'), 'id=', $game(el).attr('id'), 'class=', $game(el).attr('class'), 'text=', $game(el).text().trim().substring(0, 100));
    });
  }

  if (ticket) {
    console.log('\n3. POST com ticket:', ticket);
    const postRes = await axios.post('https://cdromance.org/',
      `cdrTicketInput=${encodeURIComponent(ticket)}`,
      {
        headers: { ...HEADERS, 'Content-Type': 'application/x-www-form-urlencoded', 'Referer': gameUrl },
        timeout: 15000,
        maxRedirects: 5
      }
    );
    console.log('   POST Status:', postRes.status, 'Tamanho:', postRes.data.length);

    const $dl = cheerio.load(postRes.data);
    const dlLinks = [];
    $dl('a[href*="cdromance.com/download.php"]').each((i, el) => {
      dlLinks.push($dl(el).attr('href'));
    });
    console.log('   Links de download:', dlLinks.length);
    dlLinks.forEach(h => console.log('   ->', h));

    // Procura outros padroes de link de download
    const allDlLinks = postRes.data.match(/https?:\/\/[^"'\s]*download[^"'\s]*/gi);
    console.log('   Todos links com "download":', allDlLinks ? allDlLinks.length : 0);
    if (allDlLinks) allDlLinks.slice(0, 10).forEach(h => console.log('   ->', h));
  }
}

debug().catch(e => console.log('ERRO:', e.message));
