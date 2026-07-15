/* global document */
const puppeteer = require('puppeteer-core');
const fs = require('fs');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    headless: false,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled']
  });
  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

  console.log('Navegando para archive.org/login...');
  await page.goto('https://archive.org/account/login', { waitUntil: 'networkidle2', timeout: 30000 });

  // Aguardar os inputs carregarem (React) - archive.org e SPA
  console.log('Aguardando pagina carregar...');
  await new Promise(r => setTimeout(r, 8000));
  await page.waitForSelector('input', { timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  // Listar inputs para debug
  const inputs = await page.evaluate(() =>
    [...document.querySelectorAll('input')].map(i => ({ id: i.id, name: i.name, type: i.type, placeholder: i.placeholder }))
  );
  console.log('Inputs encontrados:', JSON.stringify(inputs));

  // Preencher usando seletores mais flexiveis
  const emailInput = await page.$('input[type="email"], input[name="username"], input[placeholder*="mail"], input[placeholder*="Email"]');
  const pwdInput = await page.$('input[type="password"]');

  if (!emailInput || !pwdInput) {
    console.log('Campos nao encontrados. Tentando primeiro input text + password...');
    const allInputs = await page.$$('input');
    if (allInputs.length >= 2) {
      await allInputs[0].type('kideje5455@ezimb.com');
      await allInputs[1].type('Arch2026xK9!mp');
    }
  } else {
    await emailInput.type('kideje5455@ezimb.com');
    await pwdInput.type('Arch2026xK9!mp');
  }

  // Encontrar e clicar no botao de login
  const loginBtn = await page.evaluateHandle(() => {
    const btns = [...document.querySelectorAll('button')];
    return btns.find(b => b.textContent.trim().toLowerCase().includes('log in')) || btns.find(b => b.type === 'submit') || btns[btns.length - 1];
  });

  console.log('Clicando em login...');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 }).catch(() => {}),
    loginBtn.click(),
  ]);

  await new Promise(r => setTimeout(r, 3000));
  console.log('URL apos login:', page.url());

  // Extrair todos os cookies
  const cookies = await browser.cookies('https://archive.org');
  console.log('Cookies obtidos:', cookies.length);

  let sig = null, user = null;
  for (const c of cookies) {
    if (c.name === 'logged-in-sig') sig = c.value;
    if (c.name === 'logged-in-user') user = c.value;
    console.log(`  ${c.name} = ${c.value.substring(0, 60)}`);
  }

  if (sig && user && user !== 'deleted') {
    const cookieContent = `# Netscape HTTP Cookie File\n.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-sig\t${sig}\n.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-user\t${user}\n`;
    fs.writeFileSync('F:\\importre\\archive_cookies.txt', cookieContent);
    console.log('\n*** COOKIE SALVO em archive_cookies.txt ***');
    console.log('User:', decodeURIComponent(user));
  } else {
    console.log('\nLogin falhou ou conta nao verificada');
  }

  await browser.close();
})().catch(e => console.error('Erro:', e.message));
