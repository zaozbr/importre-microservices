const axios = require('axios');
const { exec } = require('child_process');
const { PORTS } = require('../shared/config');
const fs = require('fs');

const LOG_PATH = 'D:/roms/library/roms/_importre_state/health_watchdog.log';
const CHECK_INTERVAL_MS = 5 * 60 * 1000;
const DL_TARGET_MBPS = 20;
const DL_MIN_PER_FILE_MBPS = 1;

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  try { fs.appendFileSync(LOG_PATH, line + '\n', 'utf-8'); } catch (e) {}
}

function execPromise(cmd) {
  return new Promise((resolve) => {
    exec(cmd, { windowsHide: true }, (err, stdout, stderr) => resolve({ err, stdout, stderr }));
  });
}

async function httpGet(url, timeout = 5000) {
  try { return (await axios.get(url, { timeout })).data; }
  catch (e) { return { error: e.message }; }
}

async function httpPost(url, body, timeout = 5000) {
  try { return (await axios.post(url, body, { timeout })).data; }
  catch (e) { return { error: e.message }; }
}

async function checkServices() {
  const queue = await httpGet(`http://127.0.0.1:${PORTS.QUEUE}/status`);
  const search = await httpGet(`http://127.0.0.1:${PORTS.SEARCH}/status`);
  const download = await httpGet(`http://127.0.0.1:${PORTS.DOWNLOAD}/status`);
  const chd = await httpGet(`http://127.0.0.1:${PORTS.CHD}/status`);
  return { queue, search, download, chd, allOk: !queue.error && !search.error && !download.error && !chd.error };
}

async function restartAll() {
  log('RESTART geral via API');
  try {
    await axios.get(`http://127.0.0.1:${PORTS.ORCHESTRATOR}/api/control/restart`, { timeout: 60000 });
    await new Promise(r => setTimeout(r, 10000));
  } catch (e) {
    log('API restart falhou, tentando matar/renascer processos...');
    await execPromise('taskkill /F /IM node.exe');
    await new Promise(r => setTimeout(r, 3000));
    await execPromise('node orchestrator/index.js', { cwd: 'F:/importre' });
  }
}

async function rebuildQueueIfEmpty() {
  try {
    const q = await httpGet(`http://127.0.0.1:${PORTS.QUEUE}/status`);
    if (q.total === 0) {
      log('Fila vazia detectada. Reconstruindo via rebuild-queue.js...');
      await execPromise('node tools/rebuild-queue.js', { cwd: 'F:/importre' });
      await httpPost(`http://127.0.0.1:${PORTS.QUEUE}/reprocess-failures`, {});
    }
  } catch (e) { log('Erro rebuildQueueIfEmpty: ' + e.message); }
}

async function checkPerformance() {
  try {
    const dl = await httpGet(`http://127.0.0.1:${PORTS.DOWNLOAD}/status`);
    if (dl.error) return { ok: false, reason: 'download service indisponivel' };
    const active = dl.active || 0;
    if (active === 0) return { ok: false, reason: 'nenhum download ativo' };
    return { ok: true, active };
  } catch (e) { return { ok: false, reason: e.message }; }
}

async function cycle() {
  log('=== Health check ===');
  const status = await checkServices();
  if (!status.allOk) {
    log('Servico indisponivel: ' + JSON.stringify({ queue: status.queue.error, search: status.search.error, download: status.download.error, chd: status.chd.error }));
    await restartAll();
    return;
  }

  const q = status.queue;
  const active = q.pending + q.searching + q.ready + q.downloading;
  log(`status: pendentes=${q.pending} buscando=${q.searching} prontos=${q.ready} downloads=${q.downloading} completados=${q.completed} falhas=${q.failed}`);

  if (active === 0 && q.total === 0) {
    await rebuildQueueIfEmpty();
    await restartAll();
    return;
  }

  const perf = await checkPerformance();
  if (!perf.ok) {
    log('Performance issue: ' + perf.reason);
  } else {
    log(`Downloads ativos: ${perf.active}`);
  }

  // Se fila parada (sem busca, sem download, sem prontos) mas com pendentes
  if (q.pending > 0 && q.searching === 0 && q.ready === 0 && q.downloading === 0) {
    log('Fila parada. Reiniciando search e download...');
    await restartAll();
  }

  // Reprocessar falhas periodicamente para dar novas chances
  if (q.failed > 0) {
    log(`Reprocessando ${q.failed} falhas...`);
    await httpPost(`http://127.0.0.1:${PORTS.QUEUE}/reprocess-failures`, {});
  }
}

async function main() {
  log('Health watchdog iniciado. Checagens a cada 5 minutos.');
  while (true) {
    try { await cycle(); }
    catch (e) { log('Erro no ciclo: ' + e.message); }
    await new Promise(r => setTimeout(r, CHECK_INTERVAL_MS));
  }
}

main();
