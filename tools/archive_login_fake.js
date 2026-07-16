const axios = require('axios');
const fs = require('fs');

(async () => {
  // 1. Obter dominios do email-fake.com
  const domResp = await axios.get('https://email-fake.com/', { timeout: 10000,
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
  });
  // Extrair dominios da pagina
  const domainMatches = domResp.data.match(/@[a-z0-9.-]+\.[a-z]{2,}/gi) || [];
  const domains = [...new Set(domainMatches.map(d => d.substring(1)))].filter(d =>
    !d.includes('example') && !d.includes('test') && d.includes('.')
  ).slice(0, 20);
  console.log('Dominios disponiveis:', domains.slice(0, 10));

  // Escolher um dominio que parece normal
  const goodDomains = domains.filter(d =>
    !d.includes('fake') && !d.includes('temp') && !d.includes('disposable') &&
    !d.includes('guerrilla') && !d.includes('mail') && !d.includes('trash')
  );
  const domain = goodDomains[0] || domains[0];
  console.log(`Dominio escolhido: ${domain}`);

  const user = 'imp' + Math.random().toString(36).substring(2, 10);
  const email = `${user}@${domain}`;
  console.log(`Email: ${email}`);

  // 2. Registrar no archive.org
  const archivePass = 'Arch2026' + Math.random().toString(36).substring(2, 8) + '!';

  // Obter cookies de sessao
  const sessResp = await axios.get('https://archive.org/account/signup', {
    timeout: 15000,
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0' }
  });
  const sessCookies = sessResp.headers['set-cookie'] || [];
  const cookieJar = [];
  if (sessCookies) {
    (Array.isArray(sessCookies) ? sessCookies : [sessCookies]).forEach(c => {
      const m = c.match(/^([^=]+)=([^;]+)/);
      if (m) cookieJar.push(`${m[1]}=${m[2]}`);
    });
  }

  // Fazer signup
  const screenname = 'imp' + Math.random().toString(36).substring(2, 8);
  const signupResp = await axios.post('https://archive.org/account/signup',
    `email=${encodeURIComponent(email)}&screenname=${screenname}&password=${encodeURIComponent(archivePass)}&password2=${encodeURIComponent(archivePass)}&terms=1&op=signup`,
    {
      timeout: 15000,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
        'Referer': 'https://archive.org/account/signup',
        'Cookie': cookieJar.join('; '),
      },
      maxRedirects: 0,
      validateStatus: () => true
    }
  );
  console.log(`Signup status: ${signupResp.status}`);

  // 3. Aguardar email de confirmacao
  console.log('Aguardando email de confirmacao...');
  for (let i = 0; i < 24; i++) {
    await new Promise(r => setTimeout(r, 5000));
    try {
      const checkResp = await axios.get(`https://email-fake.com/${domain}/${user}/`, {
        timeout: 10000,
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
      });
      // Procurar por email do archive.org
      if (checkResp.data.includes('archive.org') || checkResp.data.includes('confirm') || checkResp.data.includes('verify')) {
        console.log(`Email do archive.org encontrado!`);
        // Extrair link de confirmacao
        const linkMatch = checkResp.data.match(/https?:\/\/[^\s"<>]*archive\.org[^\s"<>]*/i);
        if (linkMatch) {
          console.log(`Link: ${linkMatch[0].substring(0, 100)}`);
          const confResp = await axios.get(linkMatch[0], {
            timeout: 15000, maxRedirects: 5, validateStatus: () => true,
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
          });
          console.log(`Confirmacao status: ${confResp.status}`);
        }
        break;
      }
    } catch (e) {}
    process.stdout.write(`${i+1}..`);
  }
  console.log('');

  // 4. Fazer login
  console.log('\nFazendo login...');
  const loginResp = await axios.post('https://archive.org/account/login',
    `username=${encodeURIComponent(email)}&password=${encodeURIComponent(archivePass)}&remember=true`,
    {
      timeout: 15000,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
        'Referer': 'https://archive.org/account/login',
      },
      maxRedirects: 0,
      validateStatus: () => true
    }
  );
  console.log(`Login status: ${loginResp.status}`);
  const loginCookies = loginResp.headers['set-cookie'] || [];

  let loggedInSig = null;
  let loggedInUser = null;
  for (const c of (Array.isArray(loginCookies) ? loginCookies : [loginCookies])) {
    const sigMatch = c.match(/logged-in-sig=([^;]+)/);
    const userMatch = c.match(/logged-in-user=([^;]+)/);
    if (sigMatch) loggedInSig = sigMatch[1];
    if (userMatch) loggedInUser = userMatch[1];
  }

  if (loggedInSig && loggedInUser && loggedInUser !== 'deleted') {
    const cookieContent = `# Netscape HTTP Cookie File\n.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-sig\t${loggedInSig}\n.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-user\t${loggedInUser}\n`;
    fs.writeFileSync('F:\\importre\\archive_cookies.txt', cookieContent);
    console.log('\n*** Cookie salvo! ***');
    console.log(`User: ${decodeURIComponent(loggedInUser)}`);
  } else {
    console.log('\nLogin falhou - tentar sem confirmacao');
    console.log('Cookies:', (Array.isArray(loginCookies) ? loginCookies : [loginCookies]).map(c => c.substring(0, 80)));
  }
})().catch(e => console.error('Erro:', e.message));
