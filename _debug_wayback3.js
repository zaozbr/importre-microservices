const fs = require('fs');
const cheerio = require('cheerio');

const html = fs.readFileSync('_cdromance_wb_game.html', 'utf-8');
const $ = cheerio.load(html);

// Remove wayback toolbar
$('#wm-ipp, #wm-ipp-base, .wb-autocomplete-suggestions').remove();

console.log('Tamanho HTML:', html.length);

// Procura #obfuscatedId
const ticket = $('#obfuscatedId').text().trim();
console.log('Ticket (#obfuscatedId):', ticket ? `"${ticket}"` : 'NAO ENCONTRADO');

// Procura elementos obfuscados
$('[id*="obfuscat"], [class*="obfuscat"]').each((i, el) => {
  console.log('Elemento obfuscat:', $(el).prop('tagName'), 'id=', $(el).attr('id'), 'class=', $(el).attr('class'), 'text=', $(el).text().trim().substring(0, 200));
});

// Busca por "obfuscat" no HTML
const obfMatches = html.match(/.{0,50}obfuscat.{0,100}/gi);
console.log('\nMatches obfuscat:', obfMatches ? obfMatches.slice(0, 5) : 'nenhum');

// Busca por "ticket" no HTML
const ticketMatches = html.match(/.{0,30}ticket.{0,80}/gi);
console.log('\nMatches ticket:', ticketMatches ? ticketMatches.slice(0, 10) : 'nenhum');

// Busca por "download" no HTML
const dlMatches = html.match(/.{0,30}download.{0,80}/gi);
console.log('\nMatches download:', dlMatches ? dlMatches.slice(0, 15) : 'nenhum');

// Busca por "cdrTicket"
const cdrMatches = html.match(/.{0,30}cdrTicket.{0,80}/gi);
console.log('\nMatches cdrTicket:', cdrMatches ? cdrMatches.slice(0, 5) : 'nenhum');

// Forms
console.log('\nForms:', $('form').length);
$('form').each((i, el) => {
  const action = $(el).attr('action');
  const method = $(el).attr('method');
  const inputs = $(el).find('input').map((j, inp) => `${$(inp).attr('name')}=${$(inp).attr('value')||''}`).get();
  console.log(`Form ${i}: action=${action} method=${method} inputs=[${inputs.join(', ')}]`);
});

// Scripts inline relevantes
console.log('\n=== SCRIPTS INLINE RELEVANTES ===');
$('script:not([src])').each((i, el) => {
  const text = $(el).text().trim();
  if (text.length > 50 && !text.includes('wayback') && !text.includes('archive_analytics') && !text.includes('webComponentLoader')) {
    console.log(`Script ${i} (${text.length} chars):`, text.substring(0, 500));
    console.log('---');
  }
});

// Scripts externos
console.log('\n=== SCRIPTS EXTERNOS ===');
$('script[src]').each((i, el) => {
  const src = $(el).attr('src');
  if (src && !src.includes('wayback') && !src.includes('archive.org')) {
    console.log(`  ${src}`);
  }
});

// Divs com classes relacionadas a download/game
console.log('\n=== DIVS COM CLASSES DOWNLOAD/GAME ===');
$('[class*="download"], [class*="game"], [class*="entry-content"], [class*="post-content"]').each((i, el) => {
  if (i < 15) {
    const text = $(el).text().trim().substring(0, 200);
    console.log(`  ${$(el).prop('tagName')} class="${$(el).attr('class')}" text="${text}"`);
  }
});

// Links de download
console.log('\n=== LINKS DE DOWNLOAD ===');
$('a').each((i, el) => {
  const href = $(el).attr('href') || '';
  const text = $(el).text().trim();
  if (/download/i.test(href) || /download/i.test(text)) {
    console.log(`  href=${href} | text=${text.substring(0, 80)}`);
  }
});

// Botoes
console.log('\n=== BOTOES ===');
$('button, input[type="button"], input[type="submit"]').each((i, el) => {
  const text = $(el).text().trim() || $(el).attr('value') || '';
  const onclick = $(el).attr('onclick') || '';
  console.log(`  ${$(el).prop('tagName')} text="${text}" onclick="${onclick}" id="${$(el).attr('id')||''}"`);
});
