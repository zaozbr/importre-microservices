/**
 * ariang_watchdog.js
 *
 * Watchdog para garantir 99%+ de uptime do AriaNg + daemon aria2c.
 * - Verifica a cada 30s se o daemon aria2c (porta 16800) responde
 * - Verifica se o servidor web AriaNg (porta 16801) responde
 * - Reinicia automaticamente o que cair
 * - Mantem o aria2c com todas as configs otimizadas
 * - Nao mata processos se estiverem saudaveis
 */
const axios = require('axios');
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const http = require('http');

const RPC_URL = 'http://127.0.0.1:16800/jsonrpc';
const WEB_URL = 'http://127.0.0.1:16801';
const CHECK_INTERVAL_MS = 60000; // 60s - menos agressivo
const ARIA2C_EXE = 'F:\\importre\\Motrix\\app\\resources\\engine\\aria2c.exe';
const SESSION_DIR = 'C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\session';
const SYSTEM_JSON = 'C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\system.json';
const LOG_FILE = 'F:\\importre\\logs\\ariang_watchdog.log';

const httpAgent = new http.Agent({ keepAlive: true, maxSockets: 2, timeout: 10000 });
const rpc = axios.create({ timeout: 15000, httpAgent });

let consecutiveFailures = 0;
let lastRestart = 0;
let totalChecks = 0;
let totalRestarts = 0;

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function isDaemonAlive() {
  try {
    const r = await rpc.post(RPC_URL, { jsonrpc: '2.0', method: 'aria2.getVersion', id: '1', params: [] });
    return !!r.data.result.version;
  } catch { return false; }
}

async function isWebAlive() {
  try {
    await axios.get(WEB_URL, { timeout: 5000 });
    return true;
  } catch { return false; }
}

function killAllAria2c() {
  // Matar apenas os PIDs que estao listening na porta 16800
  try {
    const output = execSync('netstat -ano', { encoding: 'utf8', timeout: 5000 });
    const pids = new Set();
    for (const line of output.split('\n')) {
      if (line.includes(':16800') && line.includes('LISTENING')) {
        const match = line.match(/\s+(\d+)$/);
        if (match) pids.add(match[1]);
      }
    }
    for (const pid of pids) {
      try { execSync(`taskkill /F /PID ${pid}`, { stdio: 'ignore' }); } catch {}
    }
    // Tambem matar processos aria2c sem porta (zumbis)
    try { execSync('taskkill /F /IM aria2c.exe', { stdio: 'ignore' }); } catch {}
  } catch {}
}

function startDaemon() {
  const sessionFile = `${SESSION_DIR}\\download.session`;
  if (!fs.existsSync(SESSION_DIR)) fs.mkdirSync(SESSION_DIR, { recursive: true });
  if (!fs.existsSync(sessionFile)) fs.writeFileSync(sessionFile, '');

  let trackers = '';
  try { trackers = JSON.parse(fs.readFileSync(SYSTEM_JSON, 'utf8'))['bt-tracker'] || ''; } catch {}

  const args = [
    '--enable-rpc=true', '--rpc-listen-port=16800', '--rpc-allow-origin-all=true', '--rpc-listen-all=true',
    '--check-certificate=false', '--dir=D:\\roms\\library\\roms\\psx',
    `--save-session=${sessionFile}`, '--save-session-interval=10',
    '--max-concurrent-downloads=40', '--max-connection-per-server=16', '--split=16', '--min-split-size=1M',
    '--continue=true', '--file-allocation=none', '--max-tries=0', '--retry-wait=3',
    '--connect-timeout=30', '--timeout=30', '--lowest-speed-limit=0',
    '--seed-time=0', '--seed-ratio=0', '--max-overall-upload-limit=1M', '--max-upload-limit=256K',
    '--enable-dht=true', '--enable-dht6=true', '--enable-peer-exchange=true', '--bt-enable-lpd=true',
    '--bt-max-peers=255', '--bt-request-peer-speed-limit=10M',
    '--listen-port=6881-6999', '--dht-listen-port=26701',
    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    '--console-log-level=warn'
  ];
  if (trackers) args.push(`--bt-tracker=${trackers}`);

  spawn(ARIA2C_EXE, args, { windowsHide: true, detached: true, stdio: 'ignore' }).unref();
}

function startWebServer() {
  // Reiniciar servidor web AriaNg
  const webScript = 'F:\\importre\\tools\\ariang_web.js';
  if (fs.existsSync(webScript)) {
    spawn('node', [webScript], { windowsHide: true, detached: true, stdio: 'ignore' }).unref();
  }
}

async function applyConfigs() {
  try {
    await rpc.post(RPC_URL, { jsonrpc: '2.0', method: 'aria2.changeGlobalOption', id: '1', params: [{
      'max-concurrent-downloads': '40',
      'max-connection-per-server': '16',
      'split': '16',
      'min-split-size': '1M',
      'file-allocation': 'none',
      'max-tries': '0',
      'retry-wait': '3',
      'connect-timeout': '30',
      'timeout': '30',
      'lowest-speed-limit': '0',
      'seed-time': '0',
      'seed-ratio': '0',
      'max-overall-upload-limit': '1M',
      'max-upload-limit': '256K',
      'bt-max-peers': '255',
      'bt-request-peer-speed-limit': '10M',
      'enable-dht': 'true',
      'enable-peer-exchange': 'true',
      'bt-enable-lpd': 'true',
      'check-certificate': 'false',
      'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }]});
    return true;
  } catch { return false; }
}

async function check() {
  totalChecks++;
  const daemonAlive = await isDaemonAlive();
  const webAlive = await isWebAlive();

  if (daemonAlive && webAlive) {
    consecutiveFailures = 0;
    return true;
  }

  consecutiveFailures++;
  log(`Check #${totalChecks}: daemon=${daemonAlive} web=${webAlive} falhas=${consecutiveFailures}`);

  // Restart daemon se morto
  if (!daemonAlive) {
    const now = Date.now();
    if (now - lastRestart < 10000) {
      log('Restart muito recente, aguardando...');
      return false;
    }
    log('Daemon morto. Reiniciando aria2c...');
    killAllAria2c();
    await sleep(3000);
    startDaemon();
    lastRestart = Date.now();
    totalRestarts++;
    log('aria2c reiniciado. Aguardando 12s...');
    await sleep(12000);
    const alive2 = await isDaemonAlive();
    if (alive2) {
      log('Daemon voltou! Aplicando configs...');
      await sleep(2000);
      await applyConfigs();
      log('Configs aplicadas.');
    } else {
      log('ERRO: Daemon nao voltou apos restart!');
    }
  }

  // Restart web server se morto
  if (!webAlive) {
    log('Web server morto. Reiniciando...');
    startWebServer();
    await sleep(2000);
    const webAlive2 = await isWebAlive();
    if (webAlive2) log('Web server voltou!');
    else log('ERRO: Web server nao voltou!');
  }

  return false;
}

async function main() {
  log('=== ARIANG WATCHDOG INICIADO ===');
  log(`Check interval: ${CHECK_INTERVAL_MS / 1000}s`);

  // Verificacao inicial
  const ok = await check();
  if (ok) log('Sistema saudavel no startup.');

  // Loop principal
  setInterval(async () => {
    try { await check(); }
    catch (e) { log(`Erro no check: ${e.message}`); }
  }, CHECK_INTERVAL_MS);

  // Stats a cada 5min
  setInterval(() => {
    const uptimePct = (((totalChecks - totalRestarts) / totalChecks) * 100).toFixed(1);
    log(`STATS: checks=${totalChecks} restarts=${totalRestarts} uptime=${uptimePct}%`);
  }, 300000);
}

main().catch(e => log(`Erro fatal: ${e.message}`));
