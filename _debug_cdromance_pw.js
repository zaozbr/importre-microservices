const { chromium } = require('playwright');

async function debug() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();

  // 1. Busca
  const searchUrl = 'https://cdromance.org/?s=Crash%20Bandicoot';
  console.log('1. Buscando:', searchUrl);
  await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  // Espera possivel challenge do Cloudflare resolver
  await page.waitForTimeout(5000);

  const html = await page.content();
  console.log('   Tamanho HTML:', html.length);

  // Procura links psx-iso
  const psxLinks = await page.$$eval('a[href*="psx-iso"]', els => els.map(e => e.href));
  console.log('   Links psx-iso:', psxLinks.length);
  psxLinks.slice(0, 10).forEach(h => console.log('   ->', h));

  // Se nao encontrou, procura todos os links
  if (!psxLinks.length) {
    const allLinks = await page.$$eval('a', els => els.map(e => e.href).filter(Boolean));
    const gameLinks = allLinks.filter(h => h.includes('cdromance.org/') && !h.includes('?s=') && !h.includes('/category/') && !h.includes('/page/') && !h.endsWith('cdromance.org/'));
    const unique = [...new Set(gameLinks)];
    console.log('   Links de jogo candidatos:', unique.length);
    unique.slice(0, 15).forEach(h => console.log('   ->', h));

    if (!unique.length) {
      console.log('   Primeiros 20 links:');
      allLinks.slice(0, 20).forEach(h => console.log('   ->', h));
    }

    if (!unique.length) {
      // Salva HTML para inspecao
      require('fs').writeFileSync('_cdromance_search.html', html);
      console.log('   HTML salvo em _cdromance_search.html');
      await browser.close();
      return;
    }

    // Usa primeiro link
    var gameUrl = unique[0];
  } else {
    var gameUrl = psxLinks[0];
  }

  // 2. Pagina do jogo
  console.log('\n2. Acessando pagina do jogo:', gameUrl);
  await page.goto(gameUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(3000);

  const gameHtml = await page.content();
  console.log('   Tamanho HTML:', gameHtml.length);

  // Procura #obfuscatedId
  const ticket = await page.$eval('#obfuscatedId', el => el.textContent.trim()).catch(() => null);
  console.log('   Ticket (#obfuscatedId):', ticket ? `"${ticket}"` : 'NAO ENCONTRADO');

  // Procura outros elementos
  const obfElements = await page.$$eval('[id*="obfuscat"], [class*="obfuscat"]', els =>
    els.map(e => ({ tag: e.tagName, id: e.id, class: e.className, text: e.textContent.trim().substring(0, 200) }))
  ).catch(() => []);
  console.log('   Elementos obfuscat:', obfElements.length);
  obfElements.forEach(e => console.log('   ->', e.tag, 'id=', e.id, 'class=', e.class, 'text=', e.text));

  // Procura forms
  const forms = await page.$$eval('form', els =>
    els.map(e => ({
      action: e.action,
      method: e.method,
      inputs: Array.from(e.querySelectorAll('input')).map(i => `${i.name}=${i.value}`)
    }))
  ).catch(() => []);
  console.log('   Forms:', forms.length);
  forms.forEach((f, i) => console.log(`   Form ${i}: action=${f.action} method=${f.method} inputs=[${f.inputs.join(', ')}]`));

  // Procura hidden inputs
  const hiddenInputs = await page.$$eval('input[type="hidden"]', els =>
    els.map(e => `${e.name}=${e.value}`).filter(s => !s.startsWith('='))
  ).catch(() => []);
  console.log('   Hidden inputs:', hiddenInputs);

  // Procura mencoes a ticket/cdrTicket
  const ticketMentions = gameHtml.match(/cdrTicket\w*/gi);
  console.log('   Mencoes cdrTicket*:', ticketMentions ? [...new Set(ticketMentions)] : 'nenhuma');

  // Salva HTML do jogo
  require('fs').writeFileSync('_cdromance_game.html', gameHtml);
  console.log('   HTML salvo em _cdromance_game.html');

  // Se tem ticket, faz POST
  if (ticket) {
    console.log('\n3. POST com ticket:', ticket);
    const postRes = await page.evaluate(async (ticketVal, gameUrlVal) => {
      const res = await fetch('https://cdromance.org/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Referer': gameUrlVal },
        body: `cdrTicketInput=${encodeURIComponent(ticketVal)}`
      });
      return { status: res.status, html: await res.text() };
    }, ticket, gameUrl);

    console.log('   POST Status:', postRes.status, 'Tamanho:', postRes.html.length);

    // Extrai links de download
    const dlMatches = postRes.html.match(/https?:\/\/[^"'\s]*download\.php[^"'\s]*/gi);
    console.log('   Links download.php:', dlMatches ? dlMatches.length : 0);
    if (dlMatches) dlMatches.slice(0, 10).forEach(h => console.log('   ->', h));

    // Outros links de download
    const allDl = postRes.html.match(/https?:\/\/[^"'\s]*download[^"'\s]*/gi);
    console.log('   Todos links com "download":', allDl ? allDl.length : 0);
    if (allDl) [...new Set(allDl)].slice(0, 10).forEach(h => console.log('   ->', h));

    require('fs').writeFileSync('_cdromance_post.html', postRes.html);
    console.log('   HTML do POST salvo em _cdromance_post.html');
  }

  await browser.close();
}

debug().catch(e => { console.log('ERRO:', e.message); process.exit(1); });
