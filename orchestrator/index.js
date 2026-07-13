const express = require('express');
const axios = require('axios');
const fs = require('fs');
const { spawn } = require('child_process');
const path = require('path');
const { PORTS, LOG_PATH, PSX_DIR } = require('../shared/config');
const Logger = require('../shared/logger');

const log = new Logger('orchestrator');
const app = express();
app.use(express.json());

const ROOT = path.dirname(__dirname);
const services = {};

function startService(name, script) {
  const proc = spawn('node', [script], { cwd: ROOT });
  services[name] = proc;
  proc.stdout.on('data', d => { try { log.info(`[${name}] ${d.toString().trim()}`); } catch (e) {} });
  proc.stdout.on('error', () => {});
  proc.stderr.on('data', d => { try { log.error(`[${name}] ${d.toString().trim()}`); } catch (e) {} });
  proc.stderr.on('error', () => {});
  proc.on('exit', (code) => {
    log.warn(`[${name}] saiu com code ${code}. Reiniciando em 30s...`);
    delete services[name];
    setTimeout(() => startService(name, script), 30000);
  });
}

async function serviceGet(port, endpoint) {
  try {
    const res = await axios.get(`http://127.0.0.1:${port}${endpoint}`, { timeout: 3000 });
    return res.data;
  } catch (e) {
    return { error: e.message };
  }
}

async function servicePost(port, endpoint, body) {
  try {
    const res = await axios.post(`http://127.0.0.1:${port}${endpoint}`, body, { timeout: 3000 });
    return res.data;
  } catch (e) {
    return { error: e.message };
  }
}

app.get('/api/status', async (req, res) => {
  res.json({
    queue: await serviceGet(PORTS.QUEUE, '/status'),
    search: await serviceGet(PORTS.SEARCH, '/status'),
    download: await serviceGet(PORTS.DOWNLOAD, '/status'),
    chd: await serviceGet(PORTS.CHD, '/status')
  });
});

app.get('/api/queue', async (req, res) => {
  res.json(await serviceGet(PORTS.QUEUE, '/queue'));
});

app.get('/api/log', async (req, res) => {
  try {
    const lines = fs.readFileSync(LOG_PATH, 'utf-8').split('\n').filter(Boolean).slice(-100).reverse();
    res.json({ lines });
  } catch (e) {
    res.json({ error: e.message });
  }
});

app.get('/api/chds', async (req, res) => {
  try {
    const chds = fs.readdirSync(PSX_DIR).filter(f => f.endsWith('.chd')).length;
    res.json({ chds });
  } catch (e) {
    res.json({ error: e.message });
  }
});

app.get('/', (req, res) => {
  res.send(`<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>importre-microservices Dashboard</title>
<style>
  :root { --bg:#0f1115; --card:#1a1d23; --text:#e0e0e0; --muted:#888; --ok:#4caf50; --warn:#ff9800; --err:#f44336; --accent:#2196f3; }
  body { margin:0; font-family:Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--text); }
  header { padding:20px; background:#16191f; border-bottom:1px solid #2a2e36; }
  h1 { margin:0; font-size:22px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:15px; padding:20px; }
  .card { background:var(--card); border-radius:10px; padding:15px; border-left:4px solid var(--accent); }
  .card.ok { border-color:var(--ok); }
  .card.warn { border-color:var(--warn); }
  .card.err { border-color:var(--err); }
  .value { font-size:28px; font-weight:700; margin:5px 0; }
  .label { color:var(--muted); font-size:12px; text-transform:uppercase; }
  .section { padding:0 20px 20px; }
  .section h2 { font-size:16px; color:var(--muted); margin-bottom:10px; }
  table { width:100%; border-collapse:collapse; background:var(--card); border-radius:8px; overflow:hidden; }
  th,td { padding:10px; text-align:left; font-size:13px; border-bottom:1px solid #2a2e36; }
  th { color:var(--muted); font-weight:600; }
  tr:hover { background:#22262e; }
  .status { display:inline-block; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:600; text-transform:uppercase; }
  .status.pending { background:#333; color:#aaa; }
  .status.searching { background:#1e3a5f; color:#64b5f6; }
  .status.ready { background:#2e4a2e; color:#81c784; }
  .status.downloading { background:#5d4037; color:#ffcc80; }
  .status.completed { background:#1b5e20; color:#4caf50; }
  .status.failed { background:#4a1c1c; color:#f44336; }
  .log { background:var(--card); border-radius:8px; padding:15px; font-family:Consolas,monospace; font-size:12px; max-height:400px; overflow:auto; white-space:pre-wrap; }
  .refresh { color:var(--muted); font-size:12px; margin-left:20px; }
</style>
</head>
<body>
<header>
  <h1>importre-microservices <span class="refresh">atualiza a cada 5s</span></h1>
</header>
<div class="grid" id="cards"></div>
<div class="section">
  <h2>Downloads Ativos</h2>
  <div id="downloads"></div>
</div>
<div class="section">
  <h2>Fila (últimos 30 itens)</h2>
  <div id="queue"></div>
</div>
<div class="section">
  <h2>Log</h2>
  <div class="log" id="log"></div>
</div>
<script>
function fmt(n){ return n===undefined||n===null?'-':n; }
async function load(){
  try{
    const [status, queue, log, chds] = await Promise.all([
      fetch('/api/status').then(r=>r.json()),
      fetch('/api/queue').then(r=>r.json()),
      fetch('/api/log').then(r=>r.json()),
      fetch('/api/chds').then(r=>r.json())
    ]);
    const q = status.queue || {};
    document.getElementById('cards').innerHTML = \`
      <div class="card"><div class="label">Pendentes</div><div class="value">\${fmt(q.pending)}</div></div>
      <div class="card searching"><div class="label">Buscando</div><div class="value">\${fmt(q.searching)}</div></div>
      <div class="card ready"><div class="label">Prontos</div><div class="value">\${fmt(q.ready)}</div></div>
      <div class="card downloading"><div class="label">Download</div><div class="value">\${fmt(q.downloading)}</div></div>
      <div class="card ok"><div class="label">Completados</div><div class="value">\${fmt(q.completed)}</div></div>
      <div class="card err"><div class="label">Falhas</div><div class="value">\${fmt(q.failed)}</div></div>
      <div class="card"><div class="label">CHDs</div><div class="value">\${fmt(chds.chds)}</div></div>
      <div class="card warn"><div class="label">Downloads Ativos</div><div class="value">\${fmt((status.download||{}).active)}</div></div>
    \`;
    const items = [];
    if(queue.queue) queue.queue.slice(0,30).forEach(i=>items.push(i));
    document.getElementById('queue').innerHTML = items.length ? \`<table>
      <tr><th>Serial</th><th>Título</th><th>Status</th><th>Retry</th><th>Fontes</th><th>Último erro</th></tr>
      \${items.map(i=>\`<tr>
        <td>\${i.serial}</td>
        <td>\${i.title||'-'}</td>
        <td><span class="status \${i.status}">\${i.status}</span></td>
        <td>\${i.retry_count||0}</td>
        <td>\${(i.sources||[]).map(s=>s.site).join(', ')||'-'}</td>
        <td>\${i.last_error||'-'}</td>
      </tr>\`).join('')}
    </table>\` : '<p>Nenhum item</p>';
    document.getElementById('downloads').innerHTML = (status.download||{}).active > 0
      ? \`<table><tr><th>Service</th><th>Ativos</th><th>Completados</th><th>Falhas</th></tr>
         <tr><td>download-service</td><td>\${status.download.active}</td><td>\${status.download.completed}</td><td>\${status.download.failed}</td></tr>
         </table>\`
      : '<p>Nenhum download ativo</p>';
    document.getElementById('log').textContent = (log.lines||[]).join('\\n');
  }catch(e){ console.error(e); }
}
load();
setInterval(load,5000);
</script>
</body>
</html>`);
});

process.on('uncaughtException', (e) => log.error(`uncaught: ${e.message}`));
process.on('unhandledRejection', (e) => log.error(`rejection: ${e.message}`));

app.listen(PORTS.ORCHESTRATOR, '127.0.0.1', () => {
  log.info(`Orchestrator em http://127.0.0.1:${PORTS.ORCHESTRATOR}`);
  startService('queue', 'services/queue/index.js');
  startService('search', 'services/search/index.js');
  startService('download', 'services/download/index.js');
  startService('chd', 'services/chd/index.js');
});
