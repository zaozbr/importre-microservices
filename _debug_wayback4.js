const fs = require('fs');
const cheerio = require('cheerio');

const html = fs.readFileSync('_cdromance_wb_game.html', 'utf-8');
const $ = cheerio.load(html);
$('#wm-ipp, #wm-ipp-base').remove();

// Procura #acf-content-wrapper e data-id
console.log('=== #acf-content-wrapper ===');
const acf = $('#acf-content-wrapper');
console.log('Existe:', acf.length);
console.log('data-id:', acf.attr('data-id'));
console.log('HTML:', acf.html() ? acf.html().substring(0, 500) : 'vazio');

// Procura o botao "Find Links"
console.log('\n=== Botao Find Links ===');
$('button').each((i, el) => {
  const text = $(el).text().trim();
  if (/find/i.test(text)) {
    console.log('Button:', text);
    console.log('id:', $(el).attr('id'));
    console.log('class:', $(el).attr('class'));
    console.log('onclick:', $(el).attr('onclick'));
    console.log('data-*:', Object.keys($(el).attr()).filter(k => k.startsWith('data')).map(k => `${k}=${$(el).attr(k)}`));
    // Parent
    console.log('Parent:', $(el).parent().prop('tagName'), 'id=', $(el).parent().attr('id'), 'class=', $(el).parent().attr('class'));
  }
});

// Procura .acf-get-content-button
console.log('\n=== .acf-get-content-button ===');
$('.acf-get-content-button').each((i, el) => {
  console.log('Tag:', $(el).prop('tagName'));
  console.log('Text:', $(el).text().trim());
  console.log('id:', $(el).attr('id'));
  console.log('class:', $(el).attr('class'));
  console.log('href:', $(el).attr('href'));
  console.log('data-*:', Object.keys($(el).attr()).filter(k => k.startsWith('data')).map(k => `${k}=${$(el).attr(k)}`));
});

// Script 8 completo
console.log('\n=== SCRIPT AJAX COMPLETO ===');
$('script:not([src])').each((i, el) => {
  const text = $(el).text();
  if (text.includes('acf-get-content-button') || text.includes('ajax.php')) {
    console.log(text);
  }
});

// Procura #download div
console.log('\n=== #download div ===');
$('#download').each((i, el) => {
  console.log('HTML:', $(el).html() ? $(el).html().substring(0, 1000) : 'vazio');
});

// Procura div com id="download"
console.log('\n=== Conteudo ao redor de "download" ===');
const downloadIdx = html.indexOf('id="download"');
if (downloadIdx >= 0) {
  // Remove wayback prefix
  let snippet = html.substring(downloadIdx - 100, downloadIdx + 1000);
  console.log(snippet);
}
