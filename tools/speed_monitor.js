/**
 * speed_monitor.js — Monitor de velocidade + watchdog aria2c
 *
 * Verifica a cada 30s:
 * - Velocidade total do aria2c
 * - Status da fila
 * - Se aria2c caiu, reinicia automaticamente
 * - Se velocidade < 10MB/s por 3 ciclos seguidos, alerta
 */

const http = require('http');
const { execSync, spawn } = require('child_process');

const ARIA2_PORT = 16810;
const QUEUE_PORT = 9011;
const ARIA2C_BAT = 'F:\\importre\\tools\\start_aria2c.bat';
const CHECK_INTERVAL = 30000;
const MIN_SPEED_MB = 10;
const STALL_CYCLES = 3;

let stallCount = 0;

function rpcAria2(method) {
  return new Promise(resolve => {
    const data = JSON.stringify({ jsonrpc: '2.0', method, id: '1', params: ['token:devin'] });
    const req = http.request(
      { hostname: '127.0.0.1', port: ARIA2_PORT, path: '/jsonrpc', method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': data.length } },
      res => { let b = ''; res.on('data', d => { b += d; }); res.on('end', () => { try { resolve(JSON.parse(b)); } catch { resolve(null); } }); }
    );
    req.on('error', () => resolve(null));
    req.setTimeout(5000, () => { req.destroy(); resolve(null); });
    req.write(data); req.end();
  });
}

function getQueueStatus() {
  return new Promise(resolve => {
    const req = http.request(
      { hostname: '127.0.0.1', port: QUEUE_PORT, path: '/status', method: 'GET', timeout: 5000 },
      res => { let b = ''; res.on('data', d => { b += d; }); res.on('end', () => { try { resolve(JSON.parse(b)); } catch { resolve(null); } }); }
    );
    req.on('error', () => resolve(null));
    req.on('timeout', () => { req.destroy(); resolve(null); });
    req.end();
  });
}

function restartAria2c() {
  console.log('  Reiniciando aria2c...');
  try { execSync('taskkill /F /IM aria2c.exe', { stdio: 'pipe' }); } catch { /* aria2c not running */ }
  const sleep = (ms) => { const end = Date.now() + ms; while (Date.now() < end) { /* busy wait */ } };
  sleep(2000);
  spawn('cmd.exe', ['/c', ARIA2C_BAT], { detached: true, stdio: 'ignore', windowsHide: true });
  sleep(5000);
}

async function check() {
  const now = new Date().toLocaleTimeString('pt-BR');
  const aria2 = await rpcAria2('aria2.tellActive');
  const queue = await getQueueStatus();

  if (!aria2) {
    console.log(`${now} | aria2c CAIU — reiniciando...`);
    restartAria2c();
    const retry = await rpcAria2('aria2.tellActive');
    if (retry) {
      const active = retry.result || [];
      let spd = 0; active.forEach(a => { spd += parseInt(a.downloadSpeed || 0, 10); });
      console.log(`  Reiniciado! ${active.length} downloads, ${(spd / 1048576).toFixed(1)}MB/s`);
    } else {
      console.log('  Falhou ao reiniciar — tentando novamente proximo ciclo');
    }
    return;
  }

  const active = aria2.result || [];
  let totalSpeed = 0;
  active.forEach(a => { totalSpeed += parseInt(a.downloadSpeed || 0, 10); });
  const speedMB = (totalSpeed / 1048576).toFixed(1);

  let stalled = 0;
  active.forEach(a => { if (parseInt(a.downloadSpeed || 0) < 10240) stalled++; });

  const qStr = queue ? `${queue.completed}/${queue.total} pend:${queue.pending} fail:${queue.failed}` : 'ERRO';

  console.log(`${now} | aria2: ${active.length} ativos, ${speedMB}MB/s (stalled:${stalled}) | queue: ${qStr}`);

  if (parseFloat(speedMB) < MIN_SPEED_MB) {
    stallCount++;
    if (stallCount >= STALL_CYCLES) {
      console.log(`  *** VELOCIDADE BAIXA por ${STALL_CYCLES} ciclos — possivel problema ***`);
      stallCount = 0;
    }
  } else {
    stallCount = 0;
  }
}

console.log('=== Speed Monitor iniciado (30s interval) ===');
check();
setInterval(check, CHECK_INTERVAL);
