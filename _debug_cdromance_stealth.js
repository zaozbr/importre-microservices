const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth');

chromium.use(stealth());

async function debug() {
  const browser = await chromium.launch({
    headless: false,
    args: ['--disable-blink-features=AutomationControlled', '--no-sandbox']
  });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport: { width: 1920, height: 1080 },
  });
  const page = await context.newPage();

  console.log('1. Navegando para cdromance.org...');
  await page.goto('https://cdromance.org/?s=Crash%20Bandicoot', { waitUntil: 'domcontentloaded', timeout: 30000 });

  console.log('   Aguardando Cloudflare challenge...');
  for (let i = 0; i < 24; i++) {
    await page.waitForTimeout(5000);
    const title = await page.title();
    const htmlLen = (await page.content()).length;
    console.log(`   [${i*5+5}s] title="${title}" html=${htmlLen}`);
    if (!title.includes('moment') && !title.includes('Cloudflare') && !title.includes('Um momento') && htmlLen > 50000) {
      console.log('   Challenge resolvido!');
      break;
    }
  }

  const html = await page.content();
  console.log('   HTML final:', html.length);

  // Procura links psx-iso
  const psxLinks = await page.$$eval('a[href*="psx-iso"]', els => els.map(e => e.href));
  console.log('   Links psx-iso:', psxLinks.length);
  psxLinks.slice(0, 10).forEach(h => console.log('   ->', h));

  let gameUrl = null;
  if (psxLinks.length) {
    gameUrl = psxLinks[0];
  } else {
    const allLinks = await page.$$eval('a', els => els.map(e => ({href: e.href, text: e.textContent.trim().substring(0,80)})).filter(e => e.href));
    const gameLinks = allLinks.filter(h => h.href.includes('cdromance.org/') && !h.href.includes('?s=') && !h.href.includes('/category/') && !h.href.includes('/page/') && !h.href.endsWith('cdromance.org/') && !h.href.includes('cloudflare'));
    const unique = [...new Map(gameLinks.map(h => [h.href, h])).values()];
    console.log('   Links de jogo candidatos:', unique.length);
    unique.slice(0, 15).forEach(h => console.log('   ->', h.href, '|', h.text));
    if (unique.length) gameUrl = unique[0].href;
  }

  if (!gameUrl) {
    require('fs').writeFileSync('_cdromance_search.html', html);
    console.log('   HTML salvo. Saindo.');
    await browser.close();
    return;
  }

  // 2. Pagina do jogo
  console.log('\n2. Acessando pagina do jogo:', gameUrl);
  await page.goto(gameUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  for (let i = 0; i < 12; i++) {
    await page.waitForTimeout(5000);
    const title = await page.title();
    const htmlLen = (await page.content()).length;
    console.log(`   [${i*5+5}s] title="${title}" html=${htmlLen}`);
    if (!title.includes('moment') && !title.includes('Cloudflare') && !title.includes('Um momento') && htmlLen > 50000) break;
  }

  const gameHtml = await page.content();
  console.log('   HTML jogo:', gameHtml.length);

  // Procura #acf-content-wrapper
  const acfData = await page.$eval('#acf-content-wrapper', el => el.getAttribute('data-id')).catch(() => null);
  console.log('   #acf-content-wrapper data-id:', acfData);

  if (acfData) {
    console.log('\n3. POST AJAX para ajax.php com post_id:', acfData);
    const postRes = await page.evaluate(async (postId) => {
      const res = await fetch('/wp-content/plugins/cdromance/public/ajax.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `post_id=${postId}`
      });
      return { status: res.status, html: await res.text() };
    }, acfData);

    console.log('   AJAX Status:', postRes.status, 'Tamanho:', postRes.html.length);
    console.log('   Resposta (primeiros 2000 chars):', postRes.html.substring(0, 2000));

    // Extrai links de download
    const dlMatches = postRes.html.match(/https?:\/\/[^"'\s]*download[^"'\s]*/gi);
    console.log('\n   Links com "download":', dlMatches ? dlMatches.length : 0);
    if (dlMatches) [...new Set(dlMatches)].slice(0, 10).forEach(h => console.log('   ->', h));

    // Procura por links dl*.cdromance.com
    const dlCdromance = postRes.html.match(/https?:\/\/dl\d*\.cdromance\.com[^"'\s]*/gi);
    console.log('   Links dl*.cdromance.com:', dlCdromance ? dlCdromance.length : 0);
    if (dlCdromance) dlCdromance.forEach(h => console.log('   ->', h));

    // Procura todos os links <a>
    const $ = require('cheerio').load(postRes.html);
    console.log('   Links <a> na resposta:');
    $('a').each((i, el) => {
      const href = $(el).attr('href');
      const text = $(el).text().trim();
      if (href) console.log(`   -> ${href} | ${text.substring(0, 80)}`);
    });

    require('fs').writeFileSync('_cdromance_ajax_resp.html', postRes.html);
  }

  await browser.close();
}

debug().catch(e => { console.log('ERRO:', e.message); process.exit(1); });
