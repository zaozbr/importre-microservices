const puppeteer = require('puppeteer-core');
const fs = require('fs');

const endpoints = [
  { port: 50413, path: '/devtools/browser/b14e7c52-2006-4111-8970-2c3ec47fb841' },
  { port: 53529, path: '/devtools/browser/c131f990-83d4-4ee0-857f-06c278322ab7' },
  { port: 54558, path: '/devtools/browser/0c3baa20-f44a-42e7-bc46-3d77fc4ce979' },
];

(async () => {
  for (const ep of endpoints) {
    try {
      const wsUrl = `ws://127.0.0.1:${ep.port}${ep.path}`;
      console.log(`Tentando conectar: porta ${ep.port}...`);
      const browser = await puppeteer.connect({ browserWSEndpoint: wsUrl, defaultViewport: null });
      console.log(`  Conectado!`);

      // Listar abas
      const pages = await browser.pages();
      for (const p of pages) {
        const url = p.url();
        if (url.includes('archive.org')) {
          console.log(`  Pagina archive.org: ${url}`);
        }
      }

      // Obter cookies do archive.org
      const cookies = await browser.cookies('https://archive.org');
      let sig = null, user = null;
      for (const c of cookies) {
        if (c.name === 'logged-in-sig') sig = c.value;
        if (c.name === 'logged-in-user') user = c.value;
      }

      if (sig && user && user !== 'deleted') {
        console.log(`  *** COOKIE ENCONTRADO! ***`);
        console.log(`  User: ${decodeURIComponent(user)}`);
        console.log(`  Sig: ${sig.substring(0, 50)}...`);
        const cookieContent = `# Netscape HTTP Cookie File\n.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-sig\t${sig}\n.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-user\t${user}\n`;
        fs.writeFileSync('F:\\importre\\archive_cookies.txt', cookieContent);
        console.log(`  *** COOKIE SALVO em archive_cookies.txt ***`);
        browser.disconnect();
        process.exit(0);
      } else {
        console.log(`  Sem cookie logged-in-sig (cookies: ${cookies.length})`);
        for (const c of cookies) {
          if (c.name.includes('logged') || c.name.includes('auth')) {
            console.log(`    ${c.name}=${c.value.substring(0, 50)}`);
          }
        }
      }
      browser.disconnect();
    } catch (e) {
      console.log(`  Erro: ${e.message}`);
    }
  }
  console.log('\nNenhum cookie encontrado em nenhum perfil.');
})();
