/**
 * renew_archive_cookie.js
 *
 * Renova o cookie do archive.org automaticamente.
 *
 * Uso:
 *   node tools/renew_archive_cookie.js
 *
 * Pre-requisitos:
 *   - Python 3 + internetarchive instalado (py -m pip install internetarchive)
 *   - Conta ja criada no archive.org (ver knowledge/archive_cookie_renewal.md)
 *   - ia.exe em C:\Users\Usuario\AppData\Local\Programs\Python\Python314\Scripts\ia.exe
 *
 * O que faz:
 *   1. Faz login via `ia configure` (API interna do archive.org — nao precisa de browser)
 *   2. Le o ia.ini e extrai logged-in-sig + logged-in-user
 *   3. Salva em F:\importre\archive_cookies.txt (formato Netscape)
 *   4. Reinicia aria2c com o cookie novo
 *
 * Se o login falhar (conta expirada/suspensa), imprime instrucoes para criar nova conta.
 */

const { execSync, spawn } = require('child_process');
const fs = require('fs');

const IA_EXE = 'C:\\Users\\Usuario\\AppData\\Local\\Programs\\Python\\Python314\\Scripts\\ia.exe';
const IA_INI = 'C:\\Users\\Usuario\\.config\\internetarchive\\ia.ini';
const COOKIE_OUT = 'F:\\importre\\archive_cookies.txt';
const ARIA2C_BAT = 'F:\\importre\\tools\\start_aria2c.bat';

// Credenciais da conta atual — atualizar se criar nova conta
// (ver knowledge/archive_cookie_renewal.md para criar nova)
const ARCHIVE_EMAIL = 'kideje5455@ezimb.com';
const ARCHIVE_PASS = 'Arch2026xK9!mp';

function log(msg) { console.log(`[${new Date().toISOString()}] ${msg}`); }

function runIaConfigure() {
  log('Fazendo login via ia configure...');
  try {
    const out = execSync(`"${IA_EXE}" configure --username "${ARCHIVE_EMAIL}" --password "${ARCHIVE_PASS}"`, {
      timeout: 30000,
      encoding: 'utf8',
      stdio: 'pipe',
    });
    log('Login OK: ' + out.trim());
    return true;
  } catch (e) {
    log('ERRO no login: ' + e.message);
    if (e.stderr) log('  stderr: ' + e.stderr);
    log('\n*** CONTA EXPIRADA OU SUSPENSA ***');
    log('Para criar nova conta, ver knowledge/archive_cookie_renewal.md');
    log('Passos resumidos:');
    log('  1. Gerar email em https://temp-mail.org/');
    log('  2. Criar conta em https://archive.org/account/signup');
    log('  3. Confirmar email pelo temp-mail.org');
    log('  4. Atualizar ARCHIVE_EMAIL e ARCHIVE_PASS neste script');
    log('  5. Rodar: node tools/renew_archive_cookie.js');
    return false;
  }
}

function extractCookies() {
  log('Lendo ia.ini...');
  if (!fs.existsSync(IA_INI)) {
    log('ERRO: ia.ini nao encontrado em ' + IA_INI);
    return null;
  }

  const content = fs.readFileSync(IA_INI, 'utf8');
  const sigMatch = content.match(/logged-in-sig\s*=\s*([^;]+)/);
  const userMatch = content.match(/logged-in-user\s*=\s*([^;]+)/);

  if (!sigMatch || !userMatch) {
    log('ERRO: Cookies logged-in-sig/user nao encontrados no ia.ini');
    return null;
  }

  const sig = sigMatch[1].trim();
  const user = userMatch[1].trim();

  if (user === 'deleted' || sig.includes('deleted')) {
    log('ERRO: Cookies marcados como deleted — login falhou');
    return null;
  }

  return { sig, user };
}

function saveCookieJar(sig, user) {
  const cookieContent = [
    '# Netscape HTTP Cookie File',
    `.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-sig\t${sig}`,
    `.archive.org\tTRUE\t/\tTRUE\t1899999999\tlogged-in-user\t${user}`,
    '',
  ].join('\n');

  fs.writeFileSync(COOKIE_OUT, cookieContent);
  log(`Cookie salvo em ${COOKIE_OUT}`);
  log(`  User: ${decodeURIComponent(user)}`);
  log(`  Sig: ${sig.substring(0, 50)}...`);
}

function restartAria2c() {
  log('Reiniciando aria2c...');

  // Matar aria2c existente
  try {
    execSync('taskkill /F /IM aria2c.exe', { stdio: 'pipe' });
    log('  aria2c antigo morto');
  } catch {
    log('  aria2c nao estava rodando');
  }

  // Aguardar 2s (sleep sincrono)
  const sleep = (ms) => { const end = Date.now() + ms; while (Date.now() < end) { /* busy wait */ } };
  sleep(2000);

  // Iniciar novo
  spawn('cmd.exe', ['/c', ARIA2C_BAT], {
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  });
  log('  aria2c iniciado');

  // Aguardar inicializacao (6s — aria2c demora para subir)
  sleep(6000);

  // Verificar
  try {
    const out = execSync('tasklist /FI "IMAGENAME eq aria2c.exe" /NH', { encoding: 'utf8', timeout: 5000 });
    if (out.includes('aria2c.exe')) {
      log('  aria2c rodando!');
    } else {
      log('  AVISO: aria2c nao detectado pelo tasklist — verificar manualmente');
    }
  } catch {
    log('  AVISO: nao foi possivel verificar aria2c — verificar manualmente');
  }
}

function testCookie() {
  log('Testando cookie com curl...');
  try {
    const out = execSync(
      `curl -s -o NUL -w "%{http_code} %{size_download}" -L -b ${COOKIE_OUT} "https://archive.org/download/psx-roms-archive/battle-hunter-slus-01335-.7z" -H "User-Agent: Mozilla/5.0" --max-time 20 -r 0-1023`,
      { encoding: 'utf8', timeout: 25000, stdio: 'pipe' }
    );
    log(`  Resultado: ${out.trim()}`);
    if (out.includes('206')) {
      log('  *** COOKIE FUNCIONANDO! (206 Partial Content) ***');
      return true;
    }
    log('  Cookie pode estar invalido (esperado 206)');
    return false;
  } catch (e) {
    log('  Erro no teste: ' + e.message);
    return false;
  }
}

// Main
log('=== Renovacao de Cookie archive.org ===');
if (!fs.existsSync(IA_EXE)) {
  log('ERRO: ia.exe nao encontrado. Instalar: py -m pip install internetarchive');
  process.exit(1);
}

if (!runIaConfigure()) {
  process.exit(1);
}

const cookies = extractCookies();
if (!cookies) {
  process.exit(1);
}

saveCookieJar(cookies.sig, cookies.user);
restartAria2c();
testCookie();
log('=== Concluido ===');
