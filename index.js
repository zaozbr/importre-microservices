const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const http = require('http');
const { killBeforeStart } = require('./shared/kill_before_start');

const ROOT = __dirname;
const PYTHON = process.env.PYTHON || 'C:\\Users\\Usuario\\AppData\\Local\\Programs\\Python\\Python314\\python.exe';
const ROMS_DIR = process.env.ROMS_DIR || 'D:\\roms\\library\\roms';
const STATE_DIR = path.join(ROMS_DIR, '_importre_state');
const PSX_DIR = path.join(ROMS_DIR, 'psx');

const IMPORTRE_SCRIPT = path.join(ROOT, 'importre.py');
const CHD_SCRIPT = path.join(ROOT, '_chd_convert_v2.py');

const IMPORTRE_PORT = 8765;
const CHD_PORT = 8766;

const procs = {};
const logs = { importre: [], chd: [], system: [] };

function log(name, msg) {
  const line = `[${new Date().toISOString()}] [${name}] ${msg}`;
  console.log(line);
  logs[name].push(line);
  if (logs[name].length > 500) logs[name].shift();
}

async function startImportre() {
  if (procs.importre) return;
  // Garbage collector: matar zumbis na porta do importre antes de subir
  await killBeforeStart({
    port: IMPORTRE_PORT,
    pid: procs.importre?.pid,
    name: 'importre',
    waitPort: false, // porta pode estar em TIME_WAIT
    waitTimeoutMs: 5000,
    log: (msg) => log('importre', '[GC] ' + msg),
  });
  const args = [
    IMPORTRE_SCRIPT,
    '--workers', '20',
    '--rounds', '999',
    '--limit', '999'
  ];
  log('importre', `Iniciando ${PYTHON} ${args.join(' ')}`);
  const proc = spawn(PYTHON, args, {
    cwd: ROOT,
    env: { ...process.env, ROMS_DIR, STATE_DIR },
    windowsHide: true,
  });
  procs.importre = proc;
  proc.stdout.on('data', d => log('importre', d.toString().trim()));
  proc.stderr.on('data', d => log('importre', d.toString().trim()));
  proc.on('exit', (code) => {
    log('importre', `Processo encerrou com code ${code}. Reiniciando em 30s...`);
    procs.importre = null;
    setTimeout(startImportre, 30000);
  });
}

async function startChd() {
  if (procs.chd) return;
  // Garbage collector: matar zumbis na porta do CHD antes de subir
  await killBeforeStart({
    port: CHD_PORT,
    pid: procs.chd?.pid,
    name: 'chd',
    waitPort: false,
    waitTimeoutMs: 5000,
    log: (msg) => log('chd', '[GC] ' + msg),
  });
  const args = [CHD_SCRIPT, '--workers', '2'];
  log('chd', `Iniciando ${PYTHON} ${args.join(' ')}`);
  const proc = spawn(PYTHON, args, {
    cwd: ROOT,
    env: { ...process.env, ROMS_DIR, STATE_DIR },
    windowsHide: true,
  });
  procs.chd = proc;
  proc.stdout.on('data', d => log('chd', d.toString().trim()));
  proc.stderr.on('data', d => log('chd', d.toString().trim()));
  proc.on('exit', (code) => {
    log('chd', `Processo encerrou com code ${code}. Reiniciando em 30s...`);
    procs.chd = null;
    setTimeout(startChd, 30000);
  });
}

function stopAll() {
  for (const [name, proc] of Object.entries(procs)) {
    if (proc) {
      log(name, 'Sinal de termino enviado');
      proc.kill('SIGTERM');
    }
  }
}

function httpServer() {
  http.createServer((req, res) => {
    if (req.url === '/status') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        importre: !!procs.importre && !procs.importre.killed,
        chd: !!procs.chd && !procs.chd.killed,
        importre_port: IMPORTRE_PORT,
        chd_port: CHD_PORT,
        state_dir: STATE_DIR,
        psx_dir: PSX_DIR
      }, null, 2));
    } else if (req.url === '/logs') {
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end([...logs.importre, ...logs.chd].join('\n'));
    } else {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(`<h1>importre-lite</h1>
<ul>
<li><a href="http://127.0.0.1:${IMPORTRE_PORT}/">Dashboard importre</a></li>
<li><a href="http://127.0.0.1:${CHD_PORT}/">Dashboard CHD</a></li>
<li><a href="/status">Status JSON</a></li>
<li><a href="/logs">Logs</a></li>
</ul>`);
    }
  }).listen(8767, () => log('system', 'Orquestrador em http://127.0.0.1:8767'));
}

process.on('SIGINT', () => { stopAll(); process.exit(0); });
process.on('SIGTERM', () => { stopAll(); process.exit(0); });

const args = process.argv.slice(2);
(async () => {
  if (args.includes('--importre')) {
    await startImportre();
  } else if (args.includes('--chd')) {
    await startChd();
  } else {
    await startImportre();
    await startChd();
    httpServer();
  }
})();
