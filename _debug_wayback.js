const fs = require('fs');
const cheerio = require('cheerio');

const html = fs.readFileSync('_cdromance_wayback.html', 'utf-8');
const $ = cheerio.load(html);

console.log('Tamanho HTML:', html.length);

// Procura #obfuscatedId
const ticket = $('#obfuscatedId').text().trim();
console.log('Ticket (#obfuscatedId):', ticket ? `"${ticket}"` : 'NAO ENCONTRADO');

// Procura elementos obfuscados
$('[id*="obfuscat"], [class*="obfuscat"]').each((i, el) => {
  console.log('Elemento obfuscat:', $(el).prop('tagName'), 'id=', $(el).attr('id'), 'class=', $(el).attr('class'), 'text=', $(el).text().trim().substring(0, 200));
});

// Procura forms
console.log('\nForms:', $('form').length);
$('form').each((i, el) => {
  const action = $(el).attr('action');
  const method = $(el).attr('method');
  const inputs = $(el).find('input').map((j, inp) => `${$(inp).attr('name')}=${$(inp).attr('value')||''}`).get();
  console.log(`Form ${i}: action=${action} method=${method} inputs=[${inputs.join(', ')}]`);
});

// Hidden inputs
console.log('\nHidden inputs:');
$('input[type="hidden"]').each((i, el) => {
  console.log(`  ${$(el).attr('name')}=${$(el).attr('value')}`);
});

// Mencoes a ticket/cdrTicket
const ticketMentions = html.match(/cdrTicket\w*/gi);
console.log('\nMencoes cdrTicket*:', ticketMentions ? [...new Set(ticketMentions)] : 'nenhuma');

// Botoes/links de download
console.log('\nBotoes/links de download:');
$('a, button').each((i, el) => {
  const text = $(el).text().trim();
  const href = $(el).attr('href') || '';
  if (/download/i.test(text) || /download/i.test(href)) {
    console.log(`  ${$(el).prop('tagName')} href=${href} | text=${text.substring(0, 100)}`);
  }
});

// Links cdromance.com/download
console.log('\nLinks cdromance.com/download:');
$('a[href*="cdromance.com/download"]').each((i, el) => {
  console.log('  ->', $(el).attr('href'));
});

// Links dl*.cdromance.com
console.log('\nLinks dl*.cdromance.com:');
$('a[href*="dl"]').each((i, el) => {
  const href = $(el).attr('href');
  if (href && href.includes('cdromance')) console.log('  ->', href);
});

// Procura por scripts com ticket/obfuscated
console.log('\nScripts com ticket/obfuscated:');
$('script').each((i, el) => {
  const text = $(el).text();
  if (/ticket|obfuscat|cdrTicket/i.test(text)) {
    console.log(`  Script ${i}:`, text.substring(0, 500));
  }
});

// Procura no HTML por padroes de ticket
const ticketPatterns = html.match(/ticket['":\s]+['"]?[a-zA-Z0-9]+['"]?/gi);
console.log('\nPadroes ticket no HTML:', ticketPatterns ? ticketPatterns.slice(0, 10) : 'nenhum');

// Procura por data-* attributes relacionados a download
console.log('\nElementos com data-* download:');
$('[data-download], [data-ticket], [data-id]').each((i, el) => {
  console.log(`  ${$(el).prop('tagName')} data-download=${$(el).attr('data-download')} data-ticket=${$(el).attr('data-ticket')} data-id=${$(el).attr('data-id')}`);
});
