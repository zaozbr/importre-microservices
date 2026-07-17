/**
 * motrix_watchdog.js
 *
 * Observabilidade do daemon aria2c do Motrix.
 * - DESCOBRE a porta RPC dinamicamente via netstat (PIDs de aria2c.exe)
 * - Monitora downloads ativos, parados e em espera via RPC
 * - Detecta downloads com erro e devolve o serial para a fila de busca
 * - Detecta downloads travados (stalled) e remove
 * - Garante que o daemon Motrix esta rodando (reinicia se necessario)
 * - Loga metricas: velocidade total, downloads ativos, completados, falhas
 * - Reporta para o dashboard do download service
 */
const axios = require('axios');
const { execSync } = require('child_process');
const fs = require('fs');
const { PORTS } = require('../../shared/config');
const Logger = require('../../shared/logger');

const log = new Logger('motrix-watchdog');
const QUEUE_URL = `http://127.0.0.1:${PORTS.QUEUE}`;
const POLL_INTERVAL_MS = 15000; // 15s
const STALL_THRESHOLD_MS = 300000; // 5min sem progresso = stalled
const SYSTEM_JSON = 'C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\system.json';
const ARIA2_DEFAULT_PORT = 6800;

let rpcId = 1;
let discoveredPort = null;

const http = require('http');
const httpAgent = new http.Agent({ keepAlive: true, maxSockets: 4, timeout: 30000 });
const rpcAxios = axios.create({ timeout: 10000, httpAgent });

function rpcUrl(port) { return `http://127.0.0.1:${port}/jsonrpc`; }

function execSyncSafe(cmd, timeoutMs = 8000) {
  try { return execSync(cmd, { encoding: 'utf8', timeout: timeoutMs, windowsHide: true }); }
  catch (e) { return e.stdout || ''; }
}

/** PIDs de todos os aria2c.exe rodando. */
function allAria2cPids() {
  const pids = new Set();
  const output = execSyncSafe('wmic process where "name=\'aria2c.exe\'" get ProcessId /value');
  for (const line of output.split('\n')) {
    const m = line.match(/ProcessId=(\d+)/);
    if (m) pids.add(m[1]);
  }
  return [...pids];
}

/** Portas em LISTENING pertencentes aos PIDs dados. */
function portsForPids(pids) {
  if (!pids.length) return [];
  const pidSet = new Set(pids);
  const ports = new Set();
  const output = execSyncSafe('netstat -ano');
  for (const line of output.split('\n')) {
    if (!line.includes('LISTENING')) continue;
    const m = line.match(/:\d+\s+\S+\s+\S+\s+(\d+)\s*$/);
    if (m && pidSet.has(m[1])) {
      const portMatch = line.match(/:(\d+)\s/);
      if (portMatch) ports.add(parseInt(portMatch[1]));
    }
  }
  return [...ports];
}

/** Le rpc-listen-port do system.json do Motrix. */
function readConfiguredPort() {
  try {
    const cfg = JSON.parse(fs.readFileSync(SYSTEM_JSON, 'utf8'));
    if (cfg['rpc-listen-port']) return parseInt(cfg['rpc-listen-port']);
  } catch { /* sem config */ }
  return ARIA2_DEFAULT_PORT;
}

async function probePort(port) {
  try {
    const r = await rpcAxios.post(rpcUrl(port), { jsonrpc: '2.0', method: 'aria2.getVersion', id: 'probe', params: ['token:devin'] }, { timeout: 3000 });
    if (r.data.result && r.data.result.version) return port;
  } catch { /* morto */ }
  return null;
}

/**
 * Descobre a porta RPC dinamicamente:
 * 1. Porta ja conhecida
 * 2. netstat: PIDs de aria2c.exe -> portas em LISTENING -> probe
 * 3. system.json rpc-listen-port
 * 4. Fallback: 6800
 */
async function discoverPort() {
  if (discoveredPort) {
    const p = await probePort(discoveredPort);
    if (p) return p;
  }
  // netstat: encontra portas que aria2c.exe esta ouvindo
  const pids = allAria2cPids();
  if (pids.length) {
    const ports = portsForPids(pids);
    for (const port of ports) {
      if (port === discoveredPort) continue;
      const p = await probePort(port);
      if (p) {
        if (discoveredPort !== p) log.info(`Porta RPC descoberta via netstat: ${p}`);
        discoveredPort = p;
        return p;
      }
    }
  }
  // system.json
  const cfgPort = readConfiguredPort();
  if (cfgPort !== discoveredPort) {
    const p = await probePort(cfgPort);
    if (p) { discoveredPort = p; return p; }
  }
  // fallback
  if (ARIA2_DEFAULT_PORT !== cfgPort && ARIA2_DEFAULT_PORT !== discoveredPort) {
    const p = await probePort(ARIA2_DEFAULT_PORT);
    if (p) { discoveredPort = p; return p; }
  }
  return null;
}

async function rpc(method, params = []) {
  const port = discoveredPort || await discoverPort();
  if (!port) throw new Error('daemon aria2c nao encontrado');
  const r = await rpcAxios.post(rpcUrl(port), {
    jsonrpc: '2.0', method, id: String(rpcId++), params: ['token:devin', ...params]
  });
  if (r.data.error) throw new Error(`RPC: ${r.data.error.message}`);
  return r.data.result;
}

async function queueRequest(method, endpoint, body) {
  try {
    const res = await axios({ method, url: `${QUEUE_URL}${endpoint}`, data: body, timeout: 10000 });
    return res.data;
  } catch (e) {
    log.warn(`queue ${endpoint} falhou: ${e.message}`);
    return null;
  }
}

// Mapa gid -> { serial, site, lastCompleted, lastProgressTime, startedAt }
const trackedDownloads = new Map();

/**
 * Associa um gid a um serial para que possamos devolver a fila se falhar.
 * Chamado pelo download service quando inicia um download via RPC.
 */
function trackDownload(gid, serial, site) {
  trackedDownloads.set(gid, {
    serial,
    site,
    lastCompleted: 0,
    lastProgressTime: Date.now(),
    startedAt: Date.now()
  });
}

/**
 * Remove tracking de um gid.
 */
function untrackDownload(gid) {
  trackedDownloads.delete(gid);
}

/**
 * Verifica se o daemon Motrix esta rodando.
 */
async function isMotrixAlive() {
  try {
    const r = await rpc('aria2.getVersion');
    return !!r.version;
  } catch { return false; }
}

/**
 * Tenta reiniciar o Motrix se nao estiver rodando.
 */
async function ensureMotrixRunning() {
  const alive = await isMotrixAlive();
  if (alive) return true;
  log.warn('Motrix daemon nao responde. O ariang_watchdog cuida do restart - nao duplicar.');
  return false;
}

/**
 * Processa downloads ativos: detecta stalled e atualiza tracking.
 */
async function processActiveDownloads() {
  let active;
  try { active = await rpc('aria2.tellActive'); }
  catch (e) { log.warn(`tellActive falhou: ${e.message}`); return; }

  const now = Date.now();
  let totalSpeed = 0;

  for (const d of active) {
    const completed = parseInt(d.completedLength) || 0;
    const speed = parseInt(d.downloadSpeed) || 0;
    totalSpeed += speed;

    const tracked = trackedDownloads.get(d.gid);
    if (tracked) {
      // Atualizar progresso
      if (completed > tracked.lastCompleted) {
        tracked.lastCompleted = completed;
        tracked.lastProgressTime = now;
      }
      // Detectar stall
      const stallDuration = now - tracked.lastProgressTime;
      if (stallDuration > STALL_THRESHOLD_MS && speed === 0) {
        log.warn(`Download ${tracked.serial} (gid=${d.gid}) stalled ha ${stallDuration/1000}s. Removendo e devolvendo a fila.`);
        try {
          await rpc('aria2.forceRemove', [d.gid]);
        } catch { /* ja removido */ }
        // Devolver para fila
        await queueRequest('post', '/queue/requeue', { serial: tracked.serial });
        untrackDownload(d.gid);
      }
    }
  }

  return { activeCount: active.length, totalSpeed };
}

/**
 * Processa downloads parados: detecta erros e devolve para fila.
 */
async function processStoppedDownloads() {
  let stopped;
  try { stopped = await rpc('aria2.tellStopped', [0, 50]); }
  catch (e) { log.warn(`tellStopped falhou: ${e.message}`); return { stoppedCount: 0, errors: 0, completed: 0 }; }

  let errors = 0;
  let completed = 0;

  for (const d of stopped) {
    const tracked = trackedDownloads.get(d.gid);
    if (!tracked) continue; // nao era nosso download

    if (d.status === 'error') {
      errors++;
      log.warn(`Download ${tracked.serial} (gid=${d.gid}) ERRO: ${d.errorMessage || 'desconhecido'}. Devolvendo a fila.`);
      await queueRequest('post', '/queue/requeue', { serial: tracked.serial });
      untrackDownload(d.gid);
    } else if (d.status === 'complete') {
      completed++;
      untrackDownload(d.gid); // download service ja tratou
    } else if (d.status === 'removed') {
      log.info(`Download ${tracked.serial} (gid=${d.gid}) removido.`);
      untrackDownload(d.gid);
    }
  }

  // Limpar resultados antigos periodicamente
  if (stopped.length > 20) {
    try { await rpc('aria2.purgeDownloadResult'); } catch { /* ok */ }
  }

  return { stoppedCount: stopped.length, errors, completed };
}

/**
 * Processa downloads em espera.
 */
async function processWaitingDownloads() {
  try {
    const waiting = await rpc('aria2.tellWaiting', [0, 50]);
    return { waitingCount: waiting.length };
  } catch { return { waitingCount: 0 }; }
}

/**
 * Coleta metricas globais.
 */
async function collectMetrics() {
  try {
    const stat = await rpc('aria2.getGlobalStat');
    return {
      downloadSpeed: parseInt(stat.downloadSpeed) || 0,
      uploadSpeed: parseInt(stat.uploadSpeed) || 0,
      numActive: parseInt(stat.numActive) || 0,
      numWaiting: parseInt(stat.numWaiting) || 0,
      numStopped: parseInt(stat.numStopped) || 0,
      numStoppedTotal: parseInt(stat.numStoppedTotal) || 0
    };
  } catch { return null; }
}

/**
 * Formata velocidade em MB/s.
 */
function formatSpeed(bps) {
  const mbps = bps / 1048576;
  return mbps.toFixed(2) + ' MB/s';
}

/**
 * Loop principal do watchdog.
 */
async function watchdogLoop() {
  log.info('Motrix watchdog iniciado');
  let cycleCount = 0;
  let consecutiveFailures = 0;

  while (true) {
    try {
      // 1. Garantir que Motrix esta rodando
      const alive = await ensureMotrixRunning();
      if (!alive) {
        consecutiveFailures++;
        if (consecutiveFailures > 3) {
          log.error('Motrix indisponivel ha 3+ ciclos. Downloads podem estar parados.');
        }
        await sleep(POLL_INTERVAL_MS);
        continue;
      }
      consecutiveFailures = 0;

      // 2. Coletar metricas
      const metrics = await collectMetrics();
      if (!metrics) {
        await sleep(POLL_INTERVAL_MS);
        continue;
      }

      // 3. Processar downloads ativos (detectar stalled)
      await processActiveDownloads();

      // 4. Processar downloads parados (detectar erros, devolver a fila)
      const stoppedInfo = await processStoppedDownloads();

      // 5. Processar waiting
      await processWaitingDownloads();

      // 6. Logar metricas a cada 6 ciclos (1min)
      cycleCount++;
      if (cycleCount % 6 === 0) {
        log.info(
          `Motrix: speed=${formatSpeed(metrics.downloadSpeed)} | active=${metrics.numActive} | waiting=${metrics.numWaiting} | stopped=${metrics.numStopped} | tracked=${trackedDownloads.size} | errors=${stoppedInfo?.errors || 0}`
        );
      }

      // 7. Alerta se velocidade total < 1MB/s e ha downloads ativos
      if (metrics.numActive > 0 && metrics.downloadSpeed < 1048576 && cycleCount % 12 === 0) {
        log.warn(`Velocidade total baixa: ${formatSpeed(metrics.downloadSpeed)} com ${metrics.numActive} downloads ativos`);
      }
    } catch (e) {
      log.warn(`Watchdog cycle error: ${e.message}`);
    }
    await sleep(POLL_INTERVAL_MS);
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// Exportar para uso pelo download service
module.exports = {
  trackDownload,
  untrackDownload,
  isMotrixAlive,
  ensureMotrixRunning,
  collectMetrics,
  watchdogLoop,
  trackedDownloads
};

// Se executado diretamente, rodar watchdog standalone
if (require.main === module) {
  watchdogLoop().catch(e => {
    log.error(`Watchdog fatal: ${e.message}`);
    process.exit(1);
  });
}
