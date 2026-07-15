const axios = require('axios');
const fs = require('fs');

const MAIL_API = 'https://api.mail.tm';

(async () => {
  // 1. Criar email temporario
  const domains = (await axios.get(`${MAIL_API}/domains`, { timeout: 10000 })).data['hydra:member'];
  const domain = domains[0].domain;
  const user = 'imp' + Math.random().toString(36).substring(2, 10);
  const email = `${user}@${domain}`;
  const mailPass = 'Imp@2026#' + Math.random().toString(36).substring(2, 8);
  console.log(`Email: ${email}`);

  // Criar conta no mail.tm
  await axios.post(`${MAIL_API}/accounts`, { address: email, password: mailPass }, { timeout: 10000 });
  const loginResp = await axios.post(`${MAIL_API}/token`, { address: email, password: mailPass }, { timeout: 10000 });
  const token = loginResp.data.token;
  console.log('Conta mail.tm criada');

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
  console.log(`Sessao signup: ${cookieJar.length} cookies`);

  // Fazer signup
  const signupResp = await axios.post('https://archive.org/account/signup',
    `email=${encodeURIComponent(email)}&screenname=${user}&password=${encodeURIComponent(archivePass)}&password2=${encodeURIComponent(archivePass)}&terms=1&op=signup`,
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
  let msgId = null;
  for (let i = 0; i < 24; i++) {
    await new Promise(r => setTimeout(r, 5000));
    try {
      const msgs = await axios.get(`${MAIL_API}/messages`, {
        timeout: 10000,
        headers: { Authorization: `Bearer ${token}` }
      });
      const messages = msgs.data['hydra:member'];
      if (messages.length > 0) {
        msgId = messages[0].id;
        console.log(`Email recebido: "${messages[0].subject}" de ${messages[0].from.address}`);
        break;
      }
    } catch (e) {}
    process.stdout.write(`${i+1}..`);
  }
  console.log('');

  if (msgId) {
    const msg = await axios.get(`${MAIL_API}/messages/${msgId}`, {
      timeout: 10000,
      headers: { Authorization: `Bearer ${token}` }
    });
    const html = (msg.data.html || []).join('');
    const text = msg.data.text || '';
    const fullContent = html + text;

    // Procurar link de confirmacao
    const linkMatch = fullContent.match(/https?:\/\/[^\s"<>]*archive\.org[^\s"<>]*confirm[^\s"<>]*/i)
      || fullContent.match(/https?:\/\/[^\s"<>]*archive\.org[^\s"<>]*verify[^\s"<>]*/i)
      || fullContent.match(/https?:\/\/[^\s"<>]*archive\.org[^\s"<>]*activate[^\s"<>]*/i);
    if (linkMatch) {
      console.log(`Confirmando: ${linkMatch[0].substring(0, 80)}...`);
      const confResp = await axios.get(linkMatch[0], {
        timeout: 15000,
        maxRedirects: 5,
        validateStatus: () => true,
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
      });
      console.log(`Confirmacao status: ${confResp.status}`);
    } else {
      // Procurar qualquer link do archive.org
      const anyLink = fullContent.match(/https?:\/\/[^\s"<>]*archive\.org[^\s"<>]*/i);
      if (anyLink) {
        console.log(`Link encontrado: ${anyLink[0].substring(0, 100)}`);
      }
      console.log(`Conteudo do email (primeiros 500 chars): ${fullContent.substring(0, 500)}`);
    }
  } else {
    console.log('Nenhum email recebido apos 120s');
    // Tentar login mesmo sem confirmar - archive.org as vezes permite
  }

  // 4. Fazer login no archive.org
  console.log('\nFazendo login no archive.org...');
  const loginResp2 = await axios.post('https://archive.org/account/login',
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
  console.log(`Login status: ${loginResp2.status}`);
  const loginCookies = loginResp2.headers['set-cookie'] || [];

  let loggedInSig = null;
  let loggedInUser = null;
  for (const c of (Array.isArray(loginCookies) ? loginCookies : [loginCookies])) {
    const sigMatch = c.match(/logged-in-sig=([^;]+)/);
    const userMatch = c.match(/logged-in-user=([^;]+)/);
    if (sigMatch) loggedInSig = sigMatch[1];
    if (userMatch) loggedInUser = userMatch[1];
  }

  if (loggedInSig && loggedInUser) {
    const cookieContent = `# Netscape HTTP Cookie File\n.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-sig\t${loggedInSig}\n.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-user\t${loggedInUser}\n`;
    fs.writeFileSync('F:\\importre\\archive_cookies.txt', cookieContent);
    console.log('\nCookie salvo em F:\\importre\\archive_cookies.txt');
    console.log(`User: ${decodeURIComponent(loggedInUser)}`);
    console.log(`Sig: ${loggedInSig.substring(0, 40)}...`);
  } else {
    console.log('\nCookies de login nao encontrados');
    console.log('Set-Cookie recebidos:');
    for (const c of (Array.isArray(loginCookies) ? loginCookies : [loginCookies])) {
      console.log(`  ${c.substring(0, 100)}`);
    }
  }
})().catch(e => console.error('Erro:', e.message));
