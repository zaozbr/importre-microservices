/**
 * speed_cycle.js
 *
 * Ciclo ativo de otimizacao de velocidade. Roda a cada 2min:
 * 1. Remove downloads stalled (0MB/s, 1 conn, 0 bytes)
 * 2. Verifica velocidade total
 * 3. Se abaixo de 40MB/s, tenta injetar mais downloads romsfast
 * 4. Loga resultado para tracking de 3 ciclos consecutivos
 */
const axios = require('axios');
const http = require('http');
const fs = require('fs');

const RPC_URL = 'http://127.0.0.1:16800/jsonrpc';
const QUEUE_URL = 'http://127.0.0.1:9001';
const CYCLE_MS = 2 * 60 * 1000; // 2 min
const TARGET_MBPS = 40;
const LOG_FILE = 'F:\\importre\\logs\\speed_cycle.log';

const httpAgent = new http.Agent({ keepAlive: true, maxSockets: 4, timeout: 30000 });
const rpc = axios.create({ timeout: 20000, httpAgent });
let rpcId = 1;

let consecutiveHits = 0;
let cycleNum = 0;

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

async function call(method, params = []) {
  const r = await rpc.post(RPC_URL, { jsonrpc: '2.0', method, id: String(rpcId++), params });
  if (r.data.error) throw new Error(`RPC: ${r.data.error.message}`);
  return r.data.result;
}

async function cycle() {
  cycleNum++;
  log(`=== CICLO ${cycleNum} ===`);
  try {
    const stat = await call('aria2.getGlobalStat');
    const speedMB = parseInt(stat.downloadSpeed) / 1048576;
    const active = parseInt(stat.numActive);
    log(`Speed: ${speedMB.toFixed(2)} MB/s | Active: ${active} | Stopped: ${stat.numStopped}`);

    // Listar por host
    let downloads = [];
    try {
      downloads = await call('aria2.tellActive');
    } catch (e) {
      log(`tellActive falhou: ${e.message}`);
      return;
    }

    const byHost = {};
    const hostRegex = /https?:\/\/([^/]+)/;
    downloads.forEach(d => {
      let host = '?';
      try { host = d.files[0].uris[0].uri.match(hostRegex)[1]; } catch {}
      byHost[host] = (byHost[host] || { count: 0, speed: 0 });
      byHost[host].count++;
      byHost[host].speed += parseInt(d.downloadSpeed) / 1048576;
    });
    Object.entries(byHost).sort((a, b) => b[1].speed - a[1].speed).forEach(([h, v]) =>
      log(`  ${h}: ${v.count} dl, ${v.speed.toFixed(2)} MB/s`));

    // Remover stalled (0MB/s, 1 conn, 0 bytes)
    const stalled = downloads.filter(d => parseInt(d.downloadSpeed) === 0 && parseInt(d.connections) <= 1 && parseInt(d.totalLength) === 0);
    let removed = 0;
    for (const d of stalled) {
      try { await call('aria2.forceRemove', [d.gid]); removed++; } catch {}
    }
    if (removed > 0) log(`Removidos: ${removed} stalled`);

    // Top 5
    const sorted = downloads.map(d => ({
      speed: parseInt(d.downloadSpeed) / 1048576,
      pct: d.totalLength > 0 ? ((parseInt(d.completedLength) / parseInt(d.totalLength)) * 100).toFixed(1) : '0',
      host: (() => { try { return d.files[0].uris[0].uri.match(hostRegex)[1]; } catch { return '?'; } })()
    })).sort((a, b) => b.speed - a.speed);
    log(`=== TOP 5 ===`);
    sorted.slice(0, 5).forEach(d => log(`  ${d.speed.toFixed(2)} MB/s | ${d.pct}% | ${d.host}`));

    // Tracking de 3 ciclos consecutivos
    if (speedMB >= TARGET_MBPS) {
      consecutiveHits++;
      log(`META ATINGIDA: ${speedMB.toFixed(2)} >= ${TARGET_MBPS} MB/s | Consecutivos: ${consecutiveHits}/3`);
      if (consecutiveHits >= 3) {
        log(`>>> 3 CICLOS CONSECUTIVOS COM ${TARGET_MBPS}MB/s+! META ALCANCADA! <<<`);
      }
    } else {
      consecutiveHits = 0;
      log(`Abaixo da meta: ${speedMB.toFixed(2)} < ${TARGET_MBPS} MB/s`);
      // Se abaixo, tentar alimentar mais downloads da queue
      if (active < 30) {
        log(`Apenas ${active} downloads ativos. Tentando alimentar mais...`);
        try {
          const qResp = await axios.get(`${QUEUE_URL}/status`, { timeout: 10000 });
          const ready = qResp.data.ready || 0;
          log(`Queue ready: ${ready} itens disponiveis`);
        } catch {}
      }
    }
  } catch (e) {
    log(`ERRO no ciclo: ${e.message}`);
    consecutiveHits = 0;
  }
  log(`Aguardando ${CYCLE_MS / 1000}s para proximo ciclo...`);
}

log('=== SPEED CYCLE INICIADO ===');
log(`Target: ${TARGET_MBPS} MB/s | Intervalo: ${CYCLE_MS / 1000}s`);
cycle();
setInterval(cycle, CYCLE_MS);
