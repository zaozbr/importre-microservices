const axios = require('axios');
const fs = require('fs');

(async () => {
  // 1. Criar email no guerrillamail
  const gResp = await axios.get('https://api.guerrillamail.com/ajax.php?f=get_email_address&lang=pt', { timeout: 10000 });
  const email = gResp.data.email_addr;
  const sidToken = gResp.data.sid_token;
  console.log(`Email guerrilla: ${email}`);
  console.log(`SID: ${sidToken}`);

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

  // 3. Aguardar email de confirmacao no guerrillamail
  console.log('Aguardando email de confirmacao...');
  let confirmLink = null;
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 5000));
    try {
      const checkResp = await axios.get(`https://api.guerrillamail.com/ajax.php?f=get_email_list&offset=0&sid_token=${sidToken}`, { timeout: 10000 });
      const list = checkResp.data.list || [];
      if (list.length > 0) {
        console.log(`Email recebido: "${list[0].mail_subject}" de ${list[0].mail_from}`);
        // Ler o email
        const readResp = await axios.get(`https://api.guerrillamail.com/ajax.php?f=fetch_email&email_id=${list[0].mail_id}&sid_token=${sidToken}`, { timeout: 10000 });
        const body = readResp.data.mail_body || '';
        // Procurar link de confirmacao
        const linkMatch = body.match(/https?:\/\/[^\s"<>]*archive\.org[^\s"<>]*/i);
        if (linkMatch) {
          confirmLink = linkMatch[0];
          console.log(`Link: ${confirmLink.substring(0, 100)}`);
          // Confirmar
          const confResp = await axios.get(confirmLink, {
            timeout: 15000,
            maxRedirects: 5,
            validateStatus: () => true,
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
          });
          console.log(`Confirmacao status: ${confResp.status}`);
          break;
        }
        console.log(`Conteudo (200 chars): ${body.substring(0, 200)}`);
        break;
      }
    } catch (e) {}
    process.stdout.write(`${i+1}..`);
  }
  console.log('');

  // 4. Fazer login no archive.org
  console.log('\nFazendo login no archive.org...');
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
    console.log('\n*** Cookie salvo em F:\\importre\\archive_cookies.txt ***');
    console.log(`User: ${decodeURIComponent(loggedInUser)}`);
    console.log(`Sig: ${loggedInSig.substring(0, 40)}...`);
  } else {
    console.log('\nLogin falhou ou conta nao confirmada');
    console.log('Cookies recebidos:');
    for (const c of (Array.isArray(loginCookies) ? loginCookies : [loginCookies])) {
      console.log(`  ${c.substring(0, 120)}`);
    }
  }
})().catch(e => console.error('Erro:', e.message));
