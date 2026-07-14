/**
 * perf_monitor.js
 *
 * Monitoramento de performance a cada 10 minutos.
 * Mede velocidade, identifica gargalos, remove downloads mortos,
 * e tenta otimizar configs para dobrar performance.
 */
const axios = require('axios');
const fs = require('fs');
const http = require('http');

const RPC_URL = 'http://127.0.0.1:16800/jsonrpc';
const INTERVAL_MS = 10 * 60 * 1000; // 10 minutos
const httpAgent = new http.Agent({ keepAlive: true, maxSockets: 4, timeout: 30000 });
const rpc = axios.create({ timeout: 30000, httpAgent });

let rpcId = 1;
let history = [];
const HISTORY_FILE = 'F:\\importre\\logs\\perf_history.json';

async function call(method, params = []) {
  const r = await rpc.post(RPC_URL, { jsonrpc: '2.0', method, id: String(rpcId++), params });
  if (r.data.error) throw new Error(`RPC: ${r.data.error.message}`);
  return r.data.result;
}

function log(msg) {
  const ts = new Date().toISOString();
  console.log(`[${ts}] ${msg}`);
}

async function monitor() {
  try {
    const stat = await call('aria2.getGlobalStat');
    const speedMB = (parseInt(stat.downloadSpeed) / 1048576).toFixed(2);
    const uploadMB = (parseInt(stat.uploadSpeed) / 1048576).toFixed(2);
    const active = parseInt(stat.numActive);
    const stopped = parseInt(stat.numStopped);

    let topSpeeds = [];
    let deadCount = 0;
    let fastCount = 0;

    try {
      const downloads = await call('aria2.tellActive');
      const sorted = downloads.map(d => ({
        gid: d.gid,
        speed: parseInt(d.downloadSpeed),
        speedMB: parseFloat((parseInt(d.downloadSpeed) / 1048576).toFixed(2)),
        size: parseInt(d.totalLength),
        sizeMB: parseFloat((parseInt(d.totalLength) / 1048576).toFixed(0)),
        pct: d.totalLength > 0 ? ((parseInt(d.completedLength) / parseInt(d.totalLength)) * 100).toFixed(1) : '0',
        conn: parseInt(d.connections),
        bt: !!d.bittorrent,
        status: d.status
      })).sort((a, b) => b.speed - a.speed);

      topSpeeds = sorted.slice(0, 5);
      fastCount = sorted.filter(d => d.speedMB > 0.5).length;
      deadCount = sorted.filter(d => d.speed === 0 && d.conn <= 1 && d.size === 0).length;

      // Remover downloads mortos (0 bytes, 1 conexao)
      let removed = 0;
      for (const d of sorted) {
        if (d.speed === 0 && d.conn <= 1 && d.size === 0) {
          try { await call('aria2.forceRemove', [d.gid]); removed++; } catch {}
        }
      }
      if (removed > 0) log(`Removidos ${removed} downloads mortos`);

      log(`=== MONITOR ===`);
      log(`Speed: ${speedMB} MB/s | Upload: ${uploadMB} MB/s | Active: ${active} | Stopped: ${stopped}`);
      log(`Rapidos (>0.5MB/s): ${fastCount} | Mortos: ${deadCount} | Total: ${sorted.length}`);
      log(`=== TOP 5 ===`);
      topSpeeds.forEach(d => {
        const type = d.bt ? 'BT' : 'HTTP';
        log(`  ${d.speedMB}MB/s | ${d.sizeMB}MB | ${d.pct}% | ${type} | conn:${d.conn} | ${d.gid}`);
      });

      // Salvar historico
      history.push({ ts: Date.now(), speed: parseFloat(speedMB), active, fast: fastCount, dead: deadCount });
      if (history.length > 144) history.shift(); // 24h
      try { fs.writeFileSync(HISTORY_FILE, JSON.stringify(history, null, 2)); } catch {}

      // Analise de tendencia
      if (history.length >= 3) {
        const recent = history.slice(-3);
        const avg = recent.reduce((s, h) => s + h.speed, 0) / recent.length;
        const trend = recent[2].speed - recent[0].speed;
        log(`Media 3 ciclos: ${avg.toFixed(2)} MB/s | Tendencia: ${trend > 0 ? '+' : ''}${trend.toFixed(2)} MB/s`);
        if (avg < 20) {
          log(`ALERTA: Media abaixo de 20MB/s`);
        }
        if (avg > 40) {
          log(`EXCELENTE: Acima de 40MB/s!`);
        }
      }
    } catch (e) {
      log(`tellActive falhou: ${e.message}`);
    }

    log(`Aguardando 10min para proximo ciclo...`);
  } catch (e) {
    log(`ERRO: ${e.message}`);
  }
}

// Carregar historico
try { history = JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf8')); } catch {}

log('=== PERF MONITOR INICIADO ===');
log(`Intervalo: ${INTERVAL_MS / 1000}s`);
monitor();
setInterval(monitor, INTERVAL_MS);
