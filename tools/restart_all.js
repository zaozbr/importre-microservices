/**
 * restart_all.js — Procedimento unificado de restart completo.
 *
 * Executa EM SERIE (nao paralelo):
 * 1. Derruba todos os servicos (orchestrator, queue, search, download, chd)
 * 2. Mata processos aria2c e chdman orfaos
 * 3. Limpa arquivos temporarios (session, lockfiles, CLOSE_WAIT sockets)
 * 4. Verifica que todas as portas estao livres
 * 5. Inicia aria2c (se nao estiver rodando)
 * 6. Inicia orchestrator (que sobe os servicos filhos)
 * 7. Aguarda estabilizacao e verifica healthcheck
 * 8. Relatorio final de status
 *
 * Uso: node tools/restart_all.js [--dry-run] [--skip-aria2]
 */
const { execSync, spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');
const { killBeforeStart } = require('../shared/kill_before_start');

const PORTS = {
  ORCHESTRATOR: 8767,
  QUEUE: 9001,
  SEARCH: 9002,
  DOWNLOAD: 9003,
  CHD: 9004,
  ARIA2: 6800,
};

const ARIA2C_EXE = 'F:\\importre\\Motrix\\app\\resources\\engine\\aria2c.exe';
const PROJECT_DIR = 'F:\\importre';
const SESSION_DIR = 'C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\session';

const args = process.argv.slice(2);
const DRY_RUN = args.includes('--dry-run');
const SKIP_ARIA2 = args.includes('--skip-aria2');

function log(msg) { console.log(`[restart] ${msg}`); }
function warn(msg) { console.warn(`[restart] WARN: ${msg}`); }
function err(msg) { console.error(`[restart] ERROR: ${msg}`); }

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function execSyncSafe(cmd, timeoutMs = 10000) {
  try { return execSync(cmd, { encoding: 'utf8', timeout: timeoutMs, windowsHide: true }); }
  catch (e) { return e.stdout || ''; }
}

/** Mata processos por nome */
function killProcessByName(name) {
  const output = execSyncSafe(`wmic process where "name='${name}'" get ProcessId /value`, 5000);
  const pids = [];
  for (const line of output.split('\n')) {
    const m = line.match(/ProcessId=(\d+)/);
    if (m) pids.push(m[1]);
  }
  for (const pid of pids) {
    log(`  Matando ${name} PID ${pid}`);
    if (!DRY_RUN) execSyncSafe(`taskkill /F /PID ${pid}`, 5000);
  }
  return pids.length;
}

/** Mata processo por porta */
function killProcessByPort(port) {
  const conns = execSyncSafe(`netstat -ano | findstr ":${port} "`, 5000);
  const pids = new Set();
  for (const line of conns.split('\n')) {
    if (line.includes('LISTENING') || line.includes('ESTABLISHED')) {
      const m = line.match(/\s+(\d+)\s*$/);
      if (m) pids.add(m[1]);
    }
  }
  for (const pid of pids) {
    log(`  Matando PID ${pid} (porta ${port})`);
    if (!DRY_RUN) execSyncSafe(`taskkill /F /PID ${pid}`, 5000);
  }
  return pids.size;
}

/** Verifica se porta esta livre */
function isPortFree(port) {
  const conns = execSyncSafe(`netstat -ano | findstr ":${port} "`, 3000);
  return !conns.includes('LISTENING');
}

/** HTTP GET com timeout */
function httpGet(url, timeoutMs = 5000) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, res => {
      let d = '';
      res.on('data', c => { d += c; });
      res.on('end', () => resolve({ ok: true, status: res.statusCode, data: d }));
    });
    req.on('error', () => resolve({ ok: false }));
    req.on('timeout', () => { req.destroy(); resolve({ ok: false }); });
  });
}

/** Inicia aria2c — SEMPRE mata zumbis antes */
async function startAria2() {
  if (SKIP_ARIA2) { log('Pulando aria2 (--skip-aria2)'); return; }
  // Garbage collector: matar todos os aria2c.exe zumbis e aguardar porta
  if (!DRY_RUN) {
    log('GC: limpando aria2c.exe zumbis...');
    await killBeforeStart({
      port: PORTS.ARIA2,
      imageName: 'aria2c.exe',
      name: 'aria2c',
      waitPort: true,
      waitTimeoutMs: 10000,
      log: (msg) => log('  ' + msg),
    });
  }
  if (!isPortFree(PORTS.ARIA2)) {
    log('aria2c ja esta rodando na porta 6800');
    return;
  }
  log('Iniciando aria2c...');
  if (DRY_RUN) { log('  [dry-run] nao iniciando'); return; }
  const sessionFile = path.join(SESSION_DIR, 'download.session');
  const args = [
    '--enable-rpc',
    '--rpc-listen-all=false',
    '--rpc-listen-port=6800',
    '--rpc-secret=devin',
    '--dir=F:\\downloads',
    '--max-concurrent-downloads=60',
    '--max-connection-per-server=16',
    '--split=16',
    '--min-split-size=1M',
    '--file-allocation=none',
    '--max-tries=0',
    '--retry-wait=3',
    '--connect-timeout=30',
    '--timeout=30',
    '--lowest-speed-limit=0',
    '--seed-time=0',
    '--seed-ratio=0',
    '--max-overall-upload-limit=1M',
    '--max-upload-limit=256K',
    '--bt-max-peers=255',
    '--bt-request-peer-speed-limit=10M',
    '--enable-dht=true',
    '--enable-peer-exchange=true',
    '--bt-enable-lpd=true',
    '--check-certificate=false',
    '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    '--input-file=' + sessionFile,
    '--save-session=' + sessionFile,
    '--save-session-interval=30',
  ];
  spawn(ARIA2C_EXE, args, { detached: true, stdio: 'ignore', windowsHide: true }).unref();
  log('  aria2c iniciado');
}

/** Inicia orchestrator — SEMPRE mata zumbis na porta antes */
async function startOrchestrator() {
  log('Iniciando orchestrator...');
  if (DRY_RUN) { log('  [dry-run] nao iniciando'); return; }
  // Garbage collector: matar zumbis na porta do orchestrator
  await killBeforeStart({
    port: PORTS.ORCHESTRATOR,
    name: 'orchestrator',
    waitPort: true,
    waitTimeoutMs: 10000,
    log: (msg) => log('  ' + msg),
  });
  spawn('node', ['orchestrator/index.js'], {
    cwd: PROJECT_DIR,
    detached: true,
    stdio: 'ignore',
    windowsHide: true,
  }).unref();
  log('  orchestrator iniciado');
}

async function phase1KillAll() {
  log('FASE 1: Derrubando servicos...');
  for (const [name, port] of Object.entries(PORTS)) {
    const killed = killProcessByPort(port);
    if (killed === 0) log(`  ${name} (${port}): ja livre`);
  }
  log('FASE 1b: Matando aria2c orfaos...');
  killProcessByName('aria2c.exe');
  // NUNCA matar chdman.exe (usado pelo conversor CHD paralelo) — PROIBIDO por AGENTS.md
  await sleep(2000);
}

function phase2CleanTemp() {
  log('FASE 2: Limpando temporarios...');
  const tmpFiles = [
    path.join(PROJECT_DIR, 'logs', 'orchestrator.pid'),
    path.join(PROJECT_DIR, 'logs', 'queue.pid'),
    path.join(PROJECT_DIR, 'logs', 'search.pid'),
    path.join(PROJECT_DIR, 'logs', 'download.pid'),
    path.join(PROJECT_DIR, 'logs', 'chd.pid'),
  ];
  for (const f of tmpFiles) {
    if (fs.existsSync(f)) {
      log(`  Removendo ${f}`);
      if (!DRY_RUN) { try { fs.unlinkSync(f); } catch {} }
    }
  }
}

async function phase3CheckPorts() {
  log('FASE 3: Verificando portas...');
  let allFree = true;
  for (const [name, port] of Object.entries(PORTS)) {
    const free = isPortFree(port);
    log(`  ${name} (${port}): ${free ? 'LIVRE' : 'OCUPADA'}`);
    if (!free) allFree = false;
  }
  if (!allFree) {
    warn('Algumas portas ainda ocupadas — aguardando 5s...');
    await sleep(5000);
    for (const [name, port] of Object.entries(PORTS)) {
      if (!isPortFree(port)) {
        warn(`  ${name} (${port}) ainda ocupada — forçando kill...`);
        killProcessByPort(port);
      }
    }
    await sleep(2000);
  }
}

async function phase4StartAria2() {
  log('FASE 4: Iniciando aria2c...');
  await startAria2();
  await sleep(3000);
}

async function phase5StartOrchestrator() {
  log('FASE 5: Iniciando orchestrator...');
  await startOrchestrator();
}

async function phase6WaitStabilize() {
  log('FASE 6: Aguardando estabilizacao (20s)...');
  await sleep(20000);
}

async function phase7Healthcheck() {
  log('FASE 7: Healthcheck...');
  const status = await httpGet(`http://127.0.0.1:${PORTS.ORCHESTRATOR}/api/status`, 5000);
  if (status.ok) {
    try {
      const j = JSON.parse(status.data);
      log(`  Orchestrator: ${j.control || 'unknown'}`);
      log(`  Queue: ${JSON.stringify(j.queue)}`);
      log(`  Download: ${JSON.stringify(j.download)}`);
      log(`  globalSpeed: ${JSON.stringify(j.globalSpeed)}`);
      log('  STATUS: OK');
    } catch {
      warn('  Resposta invalida do orchestrator');
    }
  } else {
    err('  Orchestrator nao respondeu!');
    err('  Verifique logs em F:\\importre\\logs\\');
  }

  // Verificar aria2
  const aria2Data = JSON.stringify({ jsonrpc: '2.0', method: 'aria2.getVersion', id: 'restart', params: ['token:devin'] });
  const aria2Req = await new Promise(resolve => {
    const req = http.request({
      hostname: '127.0.0.1', port: 6800, path: '/jsonrpc', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': aria2Data.length },
      timeout: 5000,
    }, res => {
      let d = '';
      res.on('data', c => { d += c; });
      res.on('end', () => resolve({ ok: true, data: d }));
    });
    req.on('error', () => resolve({ ok: false }));
    req.on('timeout', () => { req.destroy(); resolve({ ok: false }); });
    req.write(aria2Data);
    req.end();
  });

  if (aria2Req.ok) {
    try {
      const j = JSON.parse(aria2Req.data);
      log(`  aria2: v${j.result?.version || '?'} — OK`);
    } catch {
      warn('  aria2: resposta invalida');
    }
  } else {
    warn('  aria2: nao respondeu (pode estar iniciando)');
  }
}

async function main() {
  console.log('=== RESTART ALL ===');
  console.log(`Modo: ${DRY_RUN ? 'DRY-RUN' : 'PRODUCAO'}`);
  console.log('');

  await phase1KillAll();
  phase2CleanTemp();
  await phase3CheckPorts();
  await phase4StartAria2();
  await phase5StartOrchestrator();
  await phase6WaitStabilize();
  await phase7Healthcheck();

  console.log('');
  log('=== RESTART COMPLETO ===');
}

main().catch(e => { err(e.message); process.exit(1); });
