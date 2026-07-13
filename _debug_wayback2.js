const fs = require('fs');
const cheerio = require('cheerio');

const html = fs.readFileSync('_cdromance_wayback.html', 'utf-8');
const $ = cheerio.load(html);

// Remove wayback elements
$('#wm-ipp, #wm-ipp-base, .wb-autocomplete-suggestions').remove();

// Procura conteudo principal
console.log('=== ESTRUTURA DA PAGINA ===');
console.log('Body classes:', $('body').attr('class'));

// Procura divs principais
$('div[id]').each((i, el) => {
  if (i < 30) console.log(`div id="${$(el).attr('id')}" class="${$(el).attr('class')||''}"`);
});

// Procura articles
console.log('\nArticles:', $('article').length);
$('article').each((i, el) => {
  if (i < 3) {
    const heading = $(el).find('h1, h2, h3').first().text().trim();
    const links = $(el).find('a').map((j, a) => $(a).attr('href')).get().filter(h => h && h.includes('cdromance'));
    console.log(`Article ${i}: heading="${heading}" links=${links.length}`);
    links.slice(0, 5).forEach(l => console.log(`  -> ${l}`));
  }
});

// Procura h1/h2 com "crash"
console.log('\nHeadings com crash:');
$('h1, h2, h3').each((i, el) => {
  const text = $(el).text().trim();
  if (/crash/i.test(text)) console.log(`  ${$(el).prop('tagName')}: ${text}`);
});

// Procura qualquer link com "crash" ou "bandicoot"
console.log('\nLinks com crash/bandicoot:');
$('a').each((i, el) => {
  const href = $(el).attr('href') || '';
  const text = $(el).text().trim();
  if (/crash|bandicoot/i.test(href) || /crash|bandicoot/i.test(text)) {
    console.log(`  href=${href} | text=${text.substring(0, 80)}`);
  }
});

// Procura classes com "download" ou "game"
console.log('\nElementos com class download/game:');
$('[class*="download"], [class*="game"], [class*="entry"]').each((i, el) => {
  if (i < 20) console.log(`  ${$(el).prop('tagName')} class="${$(el).attr('class')}" text="${$(el).text().trim().substring(0, 100)}"`);
});

// Procura scripts inline
console.log('\n=== SCRIPTS INLINE ===');
$('script:not([src])').each((i, el) => {
  const text = $(el).text().trim();
  if (text.length > 50 && !text.includes('wayback')) {
    console.log(`Script ${i} (${text.length} chars):`, text.substring(0, 300));
    console.log('---');
  }
});

// Procura por "obfuscat" no HTML inteiro
console.log('\n=== BUSCA POR OBFUSCAT NO HTML ===');
const obfMatches = html.match(/.{0,50}obfuscat.{0,100}/gi);
console.log('Matches:', obfMatches ? obfMatches : 'nenhum');

// Procura por "ticket" no HTML
console.log('\n=== BUSCA POR TICKET NO HTML ===');
const ticketMatches = html.match(/.{0,30}ticket.{0,80}/gi);
console.log('Matches:', ticketMatches ? ticketMatches.slice(0, 10) : 'nenhum');

// Procura por "download" no HTML
console.log('\n=== BUSCA POR DOWNLOAD NO HTML ===');
const dlMatches = html.match(/.{0,30}download.{0,80}/gi);
console.log('Matches:', dlMatches ? dlMatches.slice(0, 15) : 'nenhum');
