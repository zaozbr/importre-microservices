/**
 * Watchdog externo: monitora o orchestrator e reinicia se morrer.
 * Roda como processo separado, independente do orchestrator.
 * Uso: node tools/orchestrator_watchdog.js
 */
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

const ROOT = path.resolve(__dirname, '..');
const ORCH_PORT = 8767;
const CHECK_INTERVAL = 15000; // 15s
const LOG_FILE = path.join('D:\\roms\\library\\roms\\_importre_state', 'orchestrator_watchdog.log');

let orchProcess = null;
let lastCheck = Date.now();

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] [watchdog] ${msg}`;
  console.log(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch (e) {}
}

function checkOrchestrator() {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${ORCH_PORT}/`, { timeout: 5000 }, (res) => {
      resolve(true);
      res.resume();
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
  });
}

function startOrchestrator() {
  log('Iniciando orchestrator...');
  orchProcess = spawn('node', [
    '--max-old-space-size=4096',
    'orchestrator/index.js'
  ], {
    cwd: ROOT,
    stdio: 'ignore',
    detached: false
  });

  orchProcess.on('exit', (code) => {
    log(`Orchestrator saiu com code ${code}. Será reiniciado em 5s.`);
    orchProcess = null;
    setTimeout(() => startOrchestrator(), 5000);
  });

  orchProcess.on('error', (e) => {
    log(`Erro ao iniciar orchestrator: ${e.message}`);
    orchProcess = null;
    setTimeout(() => startOrchestrator(), 5000);
  });

  log(`Orchestrator iniciado (PID ${orchProcess.pid})`);
}

async function loop() {
  const alive = await checkOrchestrator();
  if (!alive) {
    log('Orchestrator nao responde! Verificando processo...');
    if (!orchProcess || orchProcess.killed) {
      log('Processo morto. Reiniciando...');
      startOrchestrator();
    } else {
      // Processo existe mas nao responde - matar e reiniciar
      log('Processo travado. Matando e reiniciando...');
      try { orchProcess.kill('SIGKILL'); } catch (e) {}
      orchProcess = null;
      setTimeout(() => startOrchestrator(), 2000);
    }
  }
  lastCheck = Date.now();
}

// Iniciar
log('Watchdog do orchestrator iniciado');
if (!await checkOrchestrator()) {
  startOrchestrator();
}

setInterval(loop, CHECK_INTERVAL);

// Graceful shutdown
process.on('SIGINT', () => {
  log('Watchdog encerrando...');
  if (orchProcess) {
    try { orchProcess.kill('SIGTERM'); } catch (e) {}
  }
  process.exit(0);
});
process.on('uncaughtException', (e) => {
  log('Watchdog uncaught: ' + e.message);
});
