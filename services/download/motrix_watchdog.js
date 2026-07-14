/**
 * motrix_watchdog.js
 *
 * Observabilidade do daemon aria2c do Motrix (porta 16800).
 * - Monitora downloads ativos, parados e em espera via RPC
 * - Detecta downloads com erro e devolve o serial para a fila de busca
 * - Detecta downloads travados (stalled) e remove
 * - Garante que o daemon Motrix esta rodando (reinicia se necessario)
 * - Loga metricas: velocidade total, downloads ativos, completados, falhas
 * - Reporta para o dashboard do download service
 */
const axios = require('axios');
const { PORTS } = require('../../shared/config');
const Logger = require('../../shared/logger');

const log = new Logger('motrix-watchdog');
const RPC_URL = 'http://127.0.0.1:16800/jsonrpc';
const QUEUE_URL = `http://127.0.0.1:${PORTS.QUEUE}`;
const POLL_INTERVAL_MS = 15000; // 15s
const STALL_THRESHOLD_MS = 180000; // 3min sem progresso = stalled
const ARIA2C_EXE = 'F:\\importre\\Motrix\\app\\resources\\engine\\aria2c.exe';
const SESSION_DIR = 'C:\\Users\\Usuario\\AppData\\Roaming\\Motrix\\session';

let rpcId = 1;

const http = require('http');
const httpAgent = new http.Agent({ keepAlive: true, maxSockets: 4, timeout: 30000 });
const rpcAxios = axios.create({ timeout: 10000, httpAgent });

async function rpc(method, params = []) {
  const r = await rpcAxios.post(RPC_URL, {
    jsonrpc: '2.0', method, id: String(rpcId++), params
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
  log.warn('Motrix daemon nao responde. Tentando reiniciar aria2c...');
  try {
    const { spawn } = require('child_process');
    const fs = require('fs');
    const path = require('path');
    const aria2c = fs.existsSync(ARIA2C_EXE) ? ARIA2C_EXE : 'F:\\importre\\Motrix\\app\\resources\\engine\\aria2c.exe';
    if (!fs.existsSync(SESSION_DIR)) fs.mkdirSync(SESSION_DIR, { recursive: true });
    const sessionFile = path.join(SESSION_DIR, 'download.session');
    if (!fs.existsSync(sessionFile)) fs.writeFileSync(sessionFile, '');
    spawn(aria2c, [
      '--enable-rpc=true', '--rpc-listen-port=16800', '--rpc-allow-origin-all=true', '--rpc-listen-all=true',
      '--check-certificate=false', '--dir=D:\\roms\\library\\roms\\psx',
      `--save-session=${sessionFile}`, '--save-session-interval=10',
      '--max-concurrent-downloads=30', '--max-connection-per-server=16', '--split=16', '--min-split-size=1M',
      '--continue=true', '--file-allocation=none', '--max-tries=0', '--retry-wait=5',
      '--seed-time=0', '--seed-ratio=0', '--enable-dht=true', '--enable-peer-exchange=true',
      '--bt-enable-lpd=true', '--bt-max-peers=128', '--listen-port=6881-6999', '--dht-listen-port=26701',
      '--console-log-level=warn'
    ], { windowsHide: true, detached: true, stdio: 'ignore' }).unref();
    log.info('aria2c daemon reiniciado. Aguardando 8s...');
    await sleep(8000);
    const alive2 = await isMotrixAlive();
    if (alive2) {
      log.info('aria2c voltou!');
      return true;
    }
    log.error('aria2c nao voltou apos restart');
    return false;
  } catch (e) {
    log.error(`Erro reiniciando aria2c: ${e.message}`);
    return false;
  }
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
