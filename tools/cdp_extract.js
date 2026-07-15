const puppeteer = require('puppeteer-core');
const fs = require('fs');

const endpoints = [
  { port: 50413, path: '/devtools/browser/b14e7c52-2006-4111-8970-2c3ec47fb841' },
  { port: 53529, path: '/devtools/browser/c131f990-83d4-4ee0-857f-06c278322ab7' },
  { port: 54558, path: '/devtools/browser/0c3baa20-f44a-42e7-bc46-3d77fc4ce979' },
];

function extractAuthCookies(cookies) {
  let sig = null;
  let user = null;
  for (const c of cookies) {
    if (c.name === 'logged-in-sig') sig = c.value;
    if (c.name === 'logged-in-user') user = c.value;
  }
  return { sig, user };
}

function saveCookieJar(sig, user) {
  const cookieContent = `# Netscape HTTP Cookie File\n.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-sig\t${sig}\n.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-user\t${user}\n`;
  fs.writeFileSync('F:\\importre\\archive_cookies.txt', cookieContent);
}

function logAuthCookies(cookies) {
  for (const c of cookies) {
    if (c.name.includes('logged') || c.name.includes('auth')) {
      console.log(`    ${c.name}=${c.value.substring(0, 50)}`);
    }
  }
}

async function tryExtractFromEndpoint(ep) {
  try {
    const wsUrl = `ws://127.0.0.1:${ep.port}${ep.path}`;
    console.log(`Tentando conectar: porta ${ep.port}...`);
    const browser = await puppeteer.connect({ browserWSEndpoint: wsUrl, defaultViewport: null });
    console.log(`  Conectado!`);

    const pages = await browser.pages();
    for (const p of pages) {
      const url = p.url();
      if (url.includes('archive.org')) {
        console.log(`  Pagina archive.org: ${url}`);
      }
    }

    const cookies = await browser.cookies('https://archive.org');
    const { sig, user } = extractAuthCookies(cookies);

    if (sig && user && user !== 'deleted') {
      console.log(`  *** COOKIE ENCONTRADO! ***`);
      console.log(`  User: ${decodeURIComponent(user)}`);
      console.log(`  Sig: ${sig.substring(0, 50)}...`);
      saveCookieJar(sig, user);
      console.log(`  *** COOKIE SALVO em archive_cookies.txt ***`);
      browser.disconnect();
      return true;
    }

    console.log(`  Sem cookie logged-in-sig (cookies: ${cookies.length})`);
    logAuthCookies(cookies);
    browser.disconnect();
    return false;
  } catch (e) {
    console.log(`  Erro: ${e.message}`);
    return false;
  }
}

(async () => {
  for (const ep of endpoints) {
    const found = await tryExtractFromEndpoint(ep);
    if (found) process.exit(0);
  }
  console.log('\nNenhum cookie encontrado em nenhum perfil.');
})();
