/**
 * ariang_watchdog.js
 *
 * Watchdog para garantir 99%+ de uptime do AriaNg + daemon aria2c.
 *
 * DESCOBERTA DE PORTA 100% DINAMICA — sem listas hardcoded:
 * 1. Escaneia netstat procurando PIDs de aria2c.exe em LISTENING
 * 2. Sonda cada porta encontrada com aria2.getVersion (RPC)
 * 3. Fallback: le rpc-listen-port do system.json do Motrix
 * 4. Fallback final: porta 6800 (default historico do aria2)
 *
 * LIMPEZA COMPLETA antes de reiniciar:
 * - Mata TODOS os aria2c.exe (com e sem porta)
 * - Mata node.exe orfaos do ariang_web.js
 * - Aguarda portas libererarem (TIME_WAIT)
 * - Verifica que a porta-alvo esta livre antes de subir
 * - Sobe o daemon sempre na porta original (lida do system.json)
 *
 * - Verifica a cada 60s se o daemon e o web server respondem
 * - Coleta diagnostico de crash antes de matar (crash_reports/)
 * - Nao mata processos saudaveis
 */
const axios = require('axios');
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const http = require('http');

const SYSTEM_JSON = 'C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\system.json';
const ARIA2C_EXE = 'F:\\importre\\Motrix\\app\\resources\\engine\\aria2c.exe';
const SESSION_DIR = 'C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\session';
const LOG_FILE = 'F:\\importre\\logs\\ariang_watchdog.log';
const CRASH_REPORT_DIR = 'F:\\importre\\logs\\crash_reports';
const ARIANG_WEB_SCRIPT = 'F:\\importre\\tools\\ariang_web.js';
const CHECK_INTERVAL_MS = 60000;
const LOG_TAIL_LINES = 80;
const ARIA2_DEFAULT_PORT = 6800; // fallback final — default historico do aria2

const httpAgent = new http.Agent({ keepAlive: true, maxSockets: 2, timeout: 10000 });
const rpc = axios.create({ timeout: 15000, httpAgent });

let consecutiveFailures = 0;
let lastRestart = 0;
let totalChecks = 0;
let totalRestarts = 0;
let discoveredPort = null;   // porta RPC atualmente em uso (descoberta dinamicamente)
let originalPort = null;     // porta original do config — sempre usada ao reiniciar

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

function rpcUrl(port) { return `http://127.0.0.1:${port}/jsonrpc`; }

// ============================================================
// PORTA ORIGINAL — lida do system.json do Motrix.
// Usada SEMPRE ao reiniciar o daemon (porta-alvo fixa).
// ============================================================

function readOriginalPort() {
  if (originalPort) return originalPort;
  try {
    const cfg = JSON.parse(fs.readFileSync(SYSTEM_JSON, 'utf8'));
    if (cfg['rpc-listen-port']) {
      originalPort = parseInt(cfg['rpc-listen-port']);
      log(`Porta original do system.json: ${originalPort}`);
      return originalPort;
    }
  } catch (e) { log(`Aviso: nao foi possivel ler system.json: ${e.message}`); }
  originalPort = ARIA2_DEFAULT_PORT;
  log(`system.json indisponivel — porta original default: ${originalPort}`);
  return originalPort;
}

// ============================================================
// DESCOBERTA DINAMICA DE PORTA RPC
// Escaneia netstat procurando PIDs de aria2c.exe em LISTENING,
// depois sonda cada porta com aria2.getVersion.
// Sem listas hardcoded — descobre do sistema operacional.
// ============================================================

/** Retorna todos os PIDs de aria2c.exe rodando no sistema. */
function allAria2cPids() {
  const pids = new Set();
  const output = execSyncSafe('wmic process where "name=\'aria2c.exe\'" get ProcessId /value');
  for (const line of output.split('\n')) {
    const m = line.match(/ProcessId=(\d+)/);
    if (m) pids.add(m[1]);
  }
  return [...pids];
}

/** Retorna todas as portas em LISTENING pertencentes aos PIDs dados. */
function portsForPids(pids) {
  if (!pids.length) return [];
  const pidSet = new Set(pids);
  const ports = new Set();
  const output = execSyncSafe('netstat -ano');
  for (const line of output.split('\n')) {
    // Linha:  TCP    0.0.0.0:16810    0.0.0.0:0    LISTENING    12345
    if (!line.includes('LISTENING')) continue;
    const m = line.match(/:\d+\s+\S+\s+\S+\s+(\d+)\s*$/);
    if (m && pidSet.has(m[1])) {
      const portMatch = line.match(/:(\d+)\s/);
      if (portMatch) ports.add(parseInt(portMatch[1]));
    }
  }
  return [...ports];
}

/** Sonda uma porta com aria2.getVersion — retorna a porta se vivo. */
async function probePort(port, timeoutMs = 3000) {
  try {
    const r = await rpc.post(rpcUrl(port), { jsonrpc: '2.0', method: 'aria2.getVersion', id: 'probe', params: [] },
      { timeout: timeoutMs, httpAgent: new http.Agent({ keepAlive: false }) });
    if (r.data.result && r.data.result.version) return port;
  } catch { /* morto */ }
  return null;
}

/**
 * Descobre a porta RPC do daemon aria2c dinamicamente:
 * 1. Se ja temos discoveredPort e responde, usa ela
 * 2. Escaneia netstat: PIDs de aria2c.exe -> portas em LISTENING -> probe RPC
 * 3. Fallback: porta original do system.json
 * 4. Fallback final: default historico 6800
 */
async function discoverDaemonPort() {
  // 1. Porta ja conhecida
  if (discoveredPort) {
    const p = await probePort(discoveredPort, 3000);
    if (p) return p;
  }

  // 2. Escaneia netstat: encontra portas que aria2c.exe esta ouvindo
  const pids = allAria2cPids();
  if (pids.length) {
    const ports = portsForPids(pids);
    for (const port of ports) {
      if (port === discoveredPort) continue;
      const p = await probePort(port, 3000);
      if (p) {
        if (discoveredPort !== p) log(`Porta RPC descoberta via netstat: ${p} (aria2c PID=${pids.join(',')})`);
        discoveredPort = p;
        return p;
      }
    }
    // aria2c.exe existe mas nenhuma porta responde RPC — processo zumbi
    log(`aria2c.exe rodando (PIDs ${pids.join(',')}) mas sem porta RPC respondendo — possivel zumbi`);
  }

  // 3. Fallback: porta do system.json
  const origPort = readOriginalPort();
  if (origPort !== discoveredPort) {
    const p = await probePort(origPort, 3000);
    if (p) {
      log(`Porta RPC encontrada via system.json: ${origPort}`);
      discoveredPort = p;
      return p;
    }
  }

  // 4. Fallback final: default historico
  if (ARIA2_DEFAULT_PORT !== origPort && ARIA2_DEFAULT_PORT !== discoveredPort) {
    const p = await probePort(ARIA2_DEFAULT_PORT, 3000);
    if (p) {
      log(`Porta RPC encontrada via fallback default: ${ARIA2_DEFAULT_PORT}`);
      discoveredPort = p;
      return p;
    }
  }

  return null;
}

// ============================================================
// DIAGNOSTICO DE CRASH
// ============================================================

async function collectRpcState() {
  const state = { alive: false, version: null, globalStat: null, activeErrors: [], stoppedErrors: [], port: discoveredPort };
  if (!discoveredPort) return state;
  const url = rpcUrl(discoveredPort);
  try {
    const r = await rpc.post(url, { jsonrpc: '2.0', method: 'aria2.getVersion', id: 'diag', params: [] },
      { timeout: 5000, httpAgent: new http.Agent({ keepAlive: false }) });
    if (r.data.result) { state.alive = true; state.version = r.data.result.version; }
  } catch (e) { state.getVersionError = e.message; }
  if (!state.alive) return state;
  try {
    const r = await rpc.post(url, { jsonrpc: '2.0', method: 'aria2.getGlobalStat', id: 'diag', params: [] },
      { timeout: 5000, httpAgent: new http.Agent({ keepAlive: false }) });
    state.globalStat = r.data.result;
  } catch (e) { state.globalStatError = e.message; }
  try {
    const r = await rpc.post(url, { jsonrpc: '2.0', method: 'aria2.tellActive', id: 'diag', params: [0, 100] },
      { timeout: 5000, httpAgent: new http.Agent({ keepAlive: false }) });
    for (const d of r.data.result) {
      if (d.errorCode !== '0') state.activeErrors.push({ gid: d.gid, errorCode: d.errorCode, errorMessage: d.errorMessage });
    }
  } catch (e) { state.tellActiveError = e.message; }
  try {
    const r = await rpc.post(url, { jsonrpc: '2.0', method: 'aria2.tellStopped', id: 'diag', params: [0, 50] },
      { timeout: 5000, httpAgent: new http.Agent({ keepAlive: false }) });
    for (const d of r.data.result) {
      if (d.status === 'error') state.stoppedErrors.push({ gid: d.gid, errorCode: d.errorCode, errorMessage: d.errorMessage });
    }
  } catch (e) { state.tellStoppedError = e.message; }
  return state;
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
  const procState = collectProcessState();
  const sysState = collectSystemState();
  const logTail = collectLogTail();
  const sections = [
    `=== CRASH REPORT ===`,
    `Timestamp: ${ts.toISOString()}`,
    `Reason: ${reason}`,
    `Consecutive failures: ${consecutiveFailures}`,
    `Total checks: ${totalChecks}`,
    `Total restarts: ${totalRestarts}`,
    `Discovered port: ${discoveredPort}`,
    `Original port: ${originalPort}`,
    ``,
    `--- RPC STATE ---`,
    JSON.stringify(rpcState, null, 2),
    ``,
    `--- PROCESSES ---`,
    `aria2c.exe: ${procState.aria2c.length} instancia(s)`,
    JSON.stringify(procState.aria2c, null, 2),
    `node.exe: ${procState.node.length} instancia(s)`,
    ``,
    `--- SYSTEM ---`,
    JSON.stringify(sysState, null, 2),
    ``,
    `--- LAST ${LOG_TAIL_LINES} LOG LINES ---`,
    logTail,
    ``,
    `=== FIM ===`
  ];
  try { fs.writeFileSync(reportFile, sections.join('\n')); } catch (e) { log(`Falha escrevendo crash report: ${e.message}`); }
  log(`CRASH REPORT: ${reportFile}`);
  log(`CRASH SUMMARY: rpcAlive=${rpcState.alive} aria2cProcs=${procState.aria2c.length} port=${discoveredPort}`);
  for (const e of (rpcState.stoppedErrors || []).slice(0, 5)) {
    log(`  stoppedError gid=${e.gid} code=${e.errorCode}: ${e.errorMessage}`);
  }
  return reportFile;
}

// ============================================================
// WEB SERVER — porta descoberta via netstat (node ariang_web.js)
// ============================================================

function ariangWebNodePids() {
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

function discoverWebPort() {
  // Procura node.exe rodando ariang_web.js e descobre a porta via netstat
  const pids = ariangWebNodePids();
  if (pids.length) {
    const ports = portsForPids(pids);
    if (ports.length) return ports[0];
  }
  // Fallback: porta padrao 16801 (web server classico)
  return 16801;
}

async function isWebAlive() {
  const port = discoverWebPort();
  try {
    await axios.get(`http://127.0.0.1:${port}`, { timeout: 5000 });
    return true;
  } catch { return false; }
}

// ============================================================
// MATADOR DE ZUMBIS + LIMPEZA COMPLETA DE PORTAS
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

/** Verifica se uma porta esta em LISTENING por algum processo. */
function isPortListening(port) {
  const output = execSyncSafe('netstat -ano');
  for (const line of output.split('\n')) {
    if (line.includes('LISTENING') && line.includes(`:${port}`)) return true;
  }
  return false;
}

/** Aguarda uma porta libererar (nenhum processo em LISTENING). */
async function waitForPortFree(port, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!isPortListening(port)) return true;
    await sleep(1000);
  }
  return !isPortListening(port);
}

function killAllZombies() {
  log('Limpando todos os zumbis...');

  // 1. TODOS os aria2c.exe (com e sem porta)
  const allAria = allAria2cPids();
  if (allAria.length) log(`  Matando aria2c.exe: PIDs ${allAria.join(', ')}`);
  killPids(allAria);

  // 2. node.exe rodando ariang_web.js
  const webNodePids = ariangWebNodePids();
  if (webNodePids.length) log(`  Matando node ariang_web.js: PIDs ${webNodePids.join(', ')}`);
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
    log(`  AVISO: zumbis teimosos apos ${deadlineMs}ms: aria2c=${aria.join(',')} nodeWeb=${web.join(',')}`);
    return false;
  }
  return true;
}

// ============================================================
// START DAEMON — sempre na porta original do system.json
// ============================================================

function startDaemon() {
  const port = readOriginalPort();
  const sessionFile = `${SESSION_DIR}\\download.session`;
  if (!fs.existsSync(SESSION_DIR)) fs.mkdirSync(SESSION_DIR, { recursive: true });
  if (!fs.existsSync(sessionFile)) fs.writeFileSync(sessionFile, '');

  let trackers = '';
  try { trackers = JSON.parse(fs.readFileSync(SYSTEM_JSON, 'utf8'))['bt-tracker'] || ''; } catch {}

  const args = [
    '--enable-rpc=true', `--rpc-listen-port=${port}`, '--rpc-allow-origin-all=true', '--rpc-listen-all=true',
    '--rpc-max-request-size=2M',
    '--check-certificate=false', '--dir=F:\\downloads',
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
  discoveredPort = port; // daemon novo vai subir nesta porta
  log(`Daemon iniciado na porta ${port}`);
}

function startWebServer() {
  if (fs.existsSync(ARIANG_WEB_SCRIPT)) {
    spawn('node', [ARIANG_WEB_SCRIPT], { windowsHide: true, detached: true, stdio: 'ignore' }).unref();
  }
}

async function applyConfigs() {
  if (!discoveredPort) return false;
  try {
    await rpc.post(rpcUrl(discoveredPort), { jsonrpc: '2.0', method: 'aria2.changeGlobalOption', id: '1', params: [{
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

// ============================================================
// CHECK — ciclo principal de verificacao
// ============================================================

async function check() {
  totalChecks++;

  // 1. Descobrir porta do daemon (netstat + probe RPC)
  const port = await discoverDaemonPort();
  const daemonAlive = port !== null;
  const webAlive = await isWebAlive();

  if (daemonAlive && webAlive) {
    if (consecutiveFailures > 0) log(`Check #${totalChecks}: sistema recuperado (porta=${discoveredPort})`);
    consecutiveFailures = 0;
    return true;
  }

  consecutiveFailures++;
  log(`Check #${totalChecks}: daemon=${daemonAlive} web=${webAlive} porta=${discoveredPort} falhas=${consecutiveFailures}`);

  // 2. Restart daemon se morto
  if (!daemonAlive) {
    const now = Date.now();
    if (now - lastRestart < 10000) {
      log('Restart muito recente, aguardando...');
      return false;
    }

    const targetPort = readOriginalPort();
    const reason = `daemon morto (webAlive=${webAlive}, falhas=${consecutiveFailures}, porta-alvo=${targetPort})`;
    log(`Daemon morto. Coletando diagnostico...`);
    await collectCrashDiagnostics(reason);

    // LIMPEZA COMPLETA: matar tudo, aguardar portas liberarem, subir na porta original
    log('LIMPEZA COMPLETA: matando todos os zumbis...');
    killAllZombies();
    const dead = await confirmZombiesDead();
    if (!dead) log('Zumbis teimosos persistem — forçando novamente...');
    // Segunda rodada se necessario
    if (!dead) {
      killAllZombies();
      await confirmZombiesDead(5000);
    }

    // Aguardar porta-alvo liberar (TIME_WAIT / processo zumbi segurando)
    log(`Aguardando porta ${targetPort} liberar...`);
    const portFree = await waitForPortFree(targetPort, 15000);
    if (!portFree) {
      log(`Porta ${targetPort} ainda ocupada — forçando kill de quem segura...`);
      killPids(pidsOnPort(targetPort));
      await sleep(3000);
      await waitForPortFree(targetPort, 10000);
    }

    log(`Subindo aria2c na porta original ${targetPort}...`);
    startDaemon();
    lastRestart = Date.now();
    totalRestarts++;
    log(`aria2c reiniciado. Aguardando 12s para estabilizar...`);
    await sleep(12000);

    // 3. Re-descobre porta apos restart (deve ser a porta-alvo)
    const alive2 = await discoverDaemonPort();
    if (alive2) {
      log(`Daemon voltou na porta ${discoveredPort}! Aplicando configs...`);
      await sleep(2000);
      await applyConfigs();
      log('Configs aplicadas.');
    } else {
      log('ERRO: Daemon nao voltou apos restart!');
      await collectCrashDiagnostics('daemon nao voltou apos restart');
    }
  }

  // 4. Restart web server se morto (sem matar daemon)
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

// ============================================================
// MAIN
// ============================================================

async function main() {
  log('=== ARIANG WATCHDOG INICIADO ===');
  log('Descoberta de porta: netstat + PIDs aria2c.exe (sem listas hardcoded)');

  // Descoberta inicial
  const port = await discoverDaemonPort();
  if (port) log(`Daemon encontrado na porta ${port} no startup.`);
  else log('Daemon nao encontrado no startup.');

  const ok = await check();
  if (ok) log(`Sistema saudavel no startup (porta RPC=${discoveredPort}).`);

  setInterval(async () => {
    try { await check(); }
    catch (e) { log(`Erro no check: ${e.message}`); }
  }, CHECK_INTERVAL_MS);

  setInterval(() => {
    const uptimePct = (((totalChecks - totalRestarts) / totalChecks) * 100).toFixed(1);
    log(`STATS: checks=${totalChecks} restarts=${totalRestarts} uptime=${uptimePct}% porta=${discoveredPort}`);
  }, 300000);
}

main().catch(e => log(`Erro fatal: ${e.message}`));
