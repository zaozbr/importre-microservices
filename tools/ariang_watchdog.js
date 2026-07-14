/**
 * ariang_watchdog.js
 *
 * Watchdog para garantir 99%+ de uptime do AriaNg + daemon aria2c.
 * - Verifica a cada 60s se o daemon aria2c (porta 16802) responde
 * - Verifica se o servidor web AriaNg (porta 16801) responde
 * - Antes de reiniciar: coleta diagnostico completo do crash e escreve
 *   relatorio em logs/crash_reports/crash_<timestamp>.log (RPC state,
 *   erros ativos/parados, portas, processos, memoria, session, log tail)
 *   para analise da causa raiz e correcao posterior.
 * - Remove TODOS os zumbis antes de reerguer o server: aria2c.exe (com
 *   e sem porta) e node.exe orfaos do ariang_web.js, confirmando a morte.
 * - Mantem o aria2c com todas as configs otimizadas
 * - Nao mata processos se estiverem saudaveis
 */
const axios = require('axios');
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const http = require('http');

const RPC_URL = 'http://127.0.0.1:16802/jsonrpc';
const WEB_URL = 'http://127.0.0.1:16801';
const CHECK_INTERVAL_MS = 60000; // 60s - menos agressivo
const ARIA2C_EXE = 'F:\\importre\\Motrix\\app\\resources\\engine\\aria2c.exe';
const SESSION_DIR = 'C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\session';
const SYSTEM_JSON = 'C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\system.json';
const LOG_FILE = 'F:\\importre\\logs\\ariang_watchdog.log';
const CRASH_REPORT_DIR = 'F:\\importre\\logs\\crash_reports';
const ARIANG_WEB_SCRIPT = 'F:\\importre\\tools\\ariang_web.js';
const LOG_TAIL_LINES = 80;

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

function execSyncSafe(cmd, timeoutMs = 8000) {
  try { return execSync(cmd, { encoding: 'utf8', timeout: timeoutMs, windowsHide: true }); }
  catch (e) { return e.stdout || ''; }
}

// ============================================================
// DIAGNOSTICO DE CRASH — coleta estado antes de matar/reiniciar
// Escreve relatorio em logs/crash_reports/crash_<timestamp>.log
// para analise posterior da causa raiz da queda.
// ============================================================

async function collectRpcState() {
  const state = { alive: false, version: null, globalStat: null, activeErrors: [], stoppedErrors: [] };
  try {
    const r = await rpc.post(RPC_URL, { jsonrpc: '2.0', method: 'aria2.getVersion', id: 'diag', params: [] },
      { timeout: 5000, httpAgent: new http.Agent({ keepAlive: false }) });
    if (r.data.result) { state.alive = true; state.version = r.data.result.version; }
  } catch (e) { state.getVersionError = e.message; }

  if (!state.alive) return state;
  try {
    const r = await rpc.post(RPC_URL, { jsonrpc: '2.0', method: 'aria2.getGlobalStat', id: 'diag', params: [] },
      { timeout: 5000, httpAgent: new http.Agent({ keepAlive: false }) });
    state.globalStat = r.data.result;
  } catch (e) { state.globalStatError = e.message; }

  try {
    const r = await rpc.post(RPC_URL, { jsonrpc: '2.0', method: 'aria2.tellActive', id: 'diag', params: [0, 100] },
      { timeout: 5000, httpAgent: new http.Agent({ keepAlive: false }) });
    for (const d of r.data.result) {
      if (d.errorCode !== '0') state.activeErrors.push({ gid: d.gid, errorCode: d.errorCode, errorMessage: d.errorMessage });
    }
  } catch (e) { state.tellActiveError = e.message; }

  try {
    const r = await rpc.post(RPC_URL, { jsonrpc: '2.0', method: 'aria2.tellStopped', id: 'diag', params: [0, 50] },
      { timeout: 5000, httpAgent: new http.Agent({ keepAlive: false }) });
    for (const d of r.data.result) {
      if (d.status === 'error') state.stoppedErrors.push({ gid: d.gid, errorCode: d.errorCode, errorMessage: d.errorMessage });
    }
  } catch (e) { state.tellStoppedError = e.message; }

  return state;
}

function collectPortState() {
  const ports = { 16801: [], 16802: [] };
  const output = execSyncSafe('netstat -ano');
  for (const line of output.split('\n')) {
    for (const p of ['16801', '16802']) {
      if (line.includes(`:${p}`)) {
        const m = line.match(/(\S+)\s+(\S+)\s+(\S+)\s+(\d+)/);
        if (m) ports[p].push({ proto: m[1], local: m[2], state: m[3], pid: m[4] });
      }
    }
  }
  return ports;
}

function collectProcessState() {
  const aria2c = execSyncSafe('tasklist /FI "IMAGENAME eq aria2c.exe" /FO CSV /NH');
  const node = execSyncSafe('tasklist /FI "IMAGENAME eq node.exe" /FO CSV /NH');
  return { aria2c: aria2c.trim().split('\n').filter(l => l.includes('aria2c')), node: node.trim().split('\n').filter(l => l.includes('node')) };
}

function collectSystemState() {
  const mem = execSyncSafe('wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value');
  const sessionFile = `${SESSION_DIR}\\download.session`;
  let sessionInfo = null;
  try {
    if (fs.existsSync(sessionFile)) {
      const stat = fs.statSync(sessionFile);
      sessionInfo = { size: stat.size, mtime: stat.mtime.toISOString() };
    } else { sessionInfo = { exists: false }; }
  } catch (e) { sessionInfo = { error: e.message }; }
  return { memory: mem.trim(), session: sessionInfo };
}

function collectLogTail() {
  try {
    if (!fs.existsSync(LOG_FILE)) return '(log nao existe)';
    const data = fs.readFileSync(LOG_FILE, 'utf8');
    const lines = data.split('\n').filter(l => l.trim());
    return lines.slice(-LOG_TAIL_LINES).join('\n');
  } catch (e) { return `(erro lendo log: ${e.message})`; }
}

async function collectCrashDiagnostics(reason) {
  const ts = new Date();
  const stamp = ts.toISOString().replace(/[:.]/g, '-');
  if (!fs.existsSync(CRASH_REPORT_DIR)) {
    try { fs.mkdirSync(CRASH_REPORT_DIR, { recursive: true }); } catch {}
  }
  const reportFile = `${CRASH_REPORT_DIR}\\crash_${stamp}.log`;

  const rpcState = await collectRpcState();
  const portState = collectPortState();
  const procState = collectProcessState();
  const sysState = collectSystemState();
  const logTail = collectLogTail();

  const sections = [
    `=== CRASH REPORT ===`,
    `Timestamp: ${ts.toISOString()}`,
    `Reason: ${reason}`,
    `Consecutive failures: ${consecutiveFailures}`,
    `Total checks so far: ${totalChecks}`,
    `Total restarts so far: ${totalRestarts}`,
    ``,
    `--- RPC STATE ---`,
    JSON.stringify(rpcState, null, 2),
    ``,
    `--- PORTS (16801 web, 16802 rpc) ---`,
    JSON.stringify(portState, null, 2),
    ``,
    `--- PROCESSES ---`,
    `aria2c.exe: ${procState.aria2c.length} instancia(s)`,
    JSON.stringify(procState.aria2c, null, 2),
    `node.exe: ${procState.node.length} instancia(s)`,
    JSON.stringify(procState.node, null, 2),
    ``,
    `--- SYSTEM ---`,
    JSON.stringify(sysState, null, 2),
    ``,
    `--- LAST ${LOG_TAIL_LINES} LOG LINES ---`,
    logTail,
    ``,
    `=== FIM DO RELATORIO ===`
  ];

  const content = sections.join('\n');
  try { fs.writeFileSync(reportFile, content); }
  catch (e) { log(`Falha escrevendo crash report: ${e.message}`); }

  log(`CRASH REPORT escrito: ${reportFile}`);
  // Resumo rapido no log principal para diagnostico imediato
  log(`CRASH SUMMARY: rpcAlive=${rpcState.alive} aria2cProcs=${procState.aria2c.length} nodeProcs=${procState.node.length} activeErrors=${rpcState.activeErrors?.length || 0} stoppedErrors=${rpcState.stoppedErrors?.length || 0}`);
  if (rpcState.globalStatError) log(`  RPC globalStatError: ${rpcState.globalStatError}`);
  if (rpcState.getVersionError) log(`  RPC getVersionError: ${rpcState.getVersionError}`);
  for (const e of (rpcState.stoppedErrors || []).slice(0, 5)) {
    log(`  stoppedError gid=${e.gid} code=${e.errorCode}: ${e.errorMessage}`);
  }

  return reportFile;
}

async function isDaemonAlive() {
  try {
    const r = await rpc.post(RPC_URL, { jsonrpc: '2.0', method: 'aria2.getVersion', id: '1', params: [] }, { timeout: 15000, httpAgent: new (require('http').Agent)({ keepAlive: false }) });
    return !!r.data.result.version;
  } catch { return false; }
}

async function isWebAlive() {
  try {
    await axios.get(WEB_URL, { timeout: 5000 });
    return true;
  } catch { return false; }
}

// ============================================================
// MATADOR DE ZUMBIS — remove TODOS os processos orfaos antes
// de reerguer o server. Mata aria2c.exe (com e sem porta) e
// node.exe rodando ariang_web.js, depois confirma que morreram.
// ============================================================

function killPids(pids) {
  for (const pid of pids) {
    try { execSync(`taskkill /F /PID ${pid}`, { stdio: 'ignore', windowsHide: true }); }
    catch {} // ja morto
  }
}

function pidsOnPort(port) {
  const pids = new Set();
  const output = execSyncSafe('netstat -ano');
  for (const line of output.split('\n')) {
    if (line.includes(`:${port}`)) {
      const m = line.match(/\s+(\d+)\s*$/);
      if (m) pids.add(m[1]);
    }
  }
  return [...pids];
}

function allAria2cPids() {
  const pids = new Set();
  const output = execSyncSafe('wmic process where "name=\'aria2c.exe\'" get ProcessId /value');
  for (const line of output.split('\n')) {
    const m = line.match(/ProcessId=(\d+)/);
    if (m) pids.add(m[1]);
  }
  return [...pids];
}

function ariangWebNodePids() {
  // Matar apenas node.exe cuja linha de comando contenha ariang_web.js.
  // wmic /value retorna blocos separados por linha em branco; cada bloco
  // descreve um processo com suas propriedades (CommandLine, ProcessId).
  const pids = new Set();
  const output = execSyncSafe('wmic process where "name=\'node.exe\'" get ProcessId,CommandLine /value');
  const blocks = output.split(/\r?\n\r?\n/);
  for (const block of blocks) {
    const pidM = block.match(/ProcessId=(\d+)/);
    const cmdM = block.match(/CommandLine=(.*)/);
    if (pidM && cmdM && cmdM[1].includes('ariang_web.js')) pids.add(pidM[1]);
  }
  return [...pids];
}

function killAllZombies() {
  log('Limpando todos os zumbis antes do restart...');

  // 1. aria2c na porta 16802 (rpc)
  const rpcPids = pidsOnPort(16802);
  if (rpcPids.length) log(`  Zumbis aria2c na porta 16802: PIDs ${rpcPids.join(', ')}`);
  killPids(rpcPids);

  // 2. aria2c na porta 16801 (web server embutido do aria2, se houver)
  const webPortPids = pidsOnPort(16801);
  if (webPortPids.length) log(`  Zumbis na porta 16801: PIDs ${webPortPids.join(', ')}`);
  killPids(webPortPids);

  // 3. TODOS os aria2c.exe restantes (zumbis sem porta / portas estranhas)
  const allAria = allAria2cPids();
  if (allAria.length) log(`  Zumbis aria2c.exe sem porta: PIDs ${allAria.join(', ')}`);
  killPids(allAria);

  // 4. node.exe rodando ariang_web.js (orfaos do web server)
  const webNodePids = ariangWebNodePids();
  if (webNodePids.length) log(`  Zumbis node ariang_web.js: PIDs ${webNodePids.join(', ')}`);
  killPids(webNodePids);
}

async function confirmZombiesDead(deadlineMs = 8000) {
  const deadline = Date.now() + deadlineMs;
  while (Date.now() < deadline) {
    const aria = allAria2cPids();
    const web = ariangWebNodePids();
    if (aria.length === 0 && web.length === 0) return true;
    await sleep(500);
  }
  const aria = allAria2cPids();
  const web = ariangWebNodePids();
  if (aria.length || web.length) {
    log(`  AVISO: zumbis teimosos ainda vivos apos ${deadlineMs}ms: aria2c=${aria.join(',')} nodeWeb=${web.join(',')}`);
    return false;
  }
  return true;
}

function startDaemon() {
  const sessionFile = `${SESSION_DIR}\\download.session`;
  if (!fs.existsSync(SESSION_DIR)) fs.mkdirSync(SESSION_DIR, { recursive: true });
  if (!fs.existsSync(sessionFile)) fs.writeFileSync(sessionFile, '');

  let trackers = '';
  try { trackers = JSON.parse(fs.readFileSync(SYSTEM_JSON, 'utf8'))['bt-tracker'] || ''; } catch {}

  const args = [
    '--enable-rpc=true', '--rpc-listen-port=16802', '--rpc-allow-origin-all=true', '--rpc-listen-all=true',
    '--rpc-max-request-size=2M',
    '--check-certificate=false', '--dir=D:\\roms\\library\\roms\\psx',
    `--save-session=${sessionFile}`, '--save-session-interval=10',
    '--max-concurrent-downloads=60', '--max-connection-per-server=16', '--split=16', '--min-split-size=1M',
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
  if (fs.existsSync(ARIANG_WEB_SCRIPT)) {
    spawn('node', [ARIANG_WEB_SCRIPT], { windowsHide: true, detached: true, stdio: 'ignore' }).unref();
  }
}

async function applyConfigs() {
  try {
    await rpc.post(RPC_URL, { jsonrpc: '2.0', method: 'aria2.changeGlobalOption', id: '1', params: [{
      'max-concurrent-downloads': '60',
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
    // Coletar diagnostico ANTES de matar — captura a causa da queda
    const reason = `daemon morto (webAlive=${webAlive}, falhas=${consecutiveFailures})`;
    log(`Daemon morto. Coletando diagnostico de crash...`);
    await collectCrashDiagnostics(reason);

    log('Removendo todos os zumbis...');
    killAllZombies();
    const dead = await confirmZombiesDead();
    if (!dead) log('Zumbis teimosos persistem — tentando restart mesmo assim.');
    await sleep(2000);

    log('Levantando aria2c...');
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
      await collectCrashDiagnostics('daemon nao voltou apos restart');
    }
  }

  // Restart web server se morto (sem matar daemon)
  if (!webAlive) {
    log('Web server morto. Removendo zumbis node do ariang_web...');
    const webNodePids = ariangWebNodePids();
    killPids(webNodePids);
    if (webNodePids.length) await sleep(1000);
    log('Reiniciando web server...');
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
