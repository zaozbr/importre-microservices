const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { PSX_DIR, PORTS, WORKERS, ARIA2, SOURCE_LIMITS } = require('../../shared/config');
const Logger = require('../../shared/logger');
const { aria2Download } = require('./aria2');

const log = new Logger('download-service');
const app = express();
app.use(express.json());
app.use('/shared', express.static(path.join(__dirname, '..', '..', 'shared')));

const QUEUE_URL = `http://127.0.0.1:${PORTS.QUEUE}`;

let status = { active: 0, completed: 0, failed: 0 };
let activeDownloads = new Map(); // serial -> { progress, speed, source, startedAt }

async function queueRequest(method, endpoint, body) {
  const res = await axios({ method, url: `${QUEUE_URL}${endpoint}`, data: body, timeout: 5000 });
  return res.data;
}

async function resolvePageDownload(pageUrl, siteHint) {
  const res = await axios.get(pageUrl, {
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
    timeout: 20000
  });
  const $ = cheerio.load(res.data);
  // CoolROM
  if (siteHint === 'coolrom' || pageUrl.includes('coolrom')) {
    const link = $('a[href*="dl.coolrom"]').attr('href');
    if (link) return link;
  }
  // Vimm: link direto para download
  if (siteHint === 'vimm' || pageUrl.includes('vimm.net')) {
    const link = $('a[href*="/vault/"][href*="download"]').attr('href') || $('a[href*="media/"]').attr('href');
    if (link) return link.startsWith('http') ? link : `https://vimm.net${link}`;
  }
  // RetroStic, RomsDL, RetroISO e outros genericos
  const exts = ['.7z', '.zip', '.rar', '.iso', '.bin', '.cue', '.img'];
  let best = null;
  $('a[href]').each((_, el) => {
    const href = $(el).attr('href');
    if (!href) return;
    const lower = href.toLowerCase();
    if (exts.some(e => lower.includes(e))) {
      best = href;
      return false; // para no primeiro
    }
  });
  if (!best) throw new Error('link de download nao encontrado');
  if (best.startsWith('http')) return best;
  const base = new URL(pageUrl).origin;
  return best.startsWith('/') ? base + best : base + '/' + best;
}

function testArchive(archivePath) {
  return new Promise((resolve, reject) => {
    const sevenZip = process.env.SEVEN_ZIP_PATH || 'C:\\Program Files\\7-Zip\\7z.exe';
    const proc = spawn(sevenZip, ['t', archivePath], { windowsHide: true });
    let stderr = '';
    proc.stderr.on('data', d => stderr += d.toString());
    proc.on('exit', (code) => {
      if (code === 0) resolve(true);
      else reject(new Error(stderr.slice(0, 200)));
    });
  });
}

function extractWith7z(archivePath, destDir) {
  return new Promise((resolve, reject) => {
    const sevenZip = process.env.SEVEN_ZIP_PATH || 'C:\\Program Files\\7-Zip\\7z.exe';
    const proc = spawn(sevenZip, ['x', '-y', '-o' + destDir, archivePath], { cwd: destDir, windowsHide: true });
    let stderr = '';
    proc.stderr.on('data', d => stderr += d.toString());
    proc.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr.slice(0, 200)));
    });
  });
}

async function updateProgress(serial, progress) {
  try {
    await axios.post(`http://127.0.0.1:${PORTS.QUEUE}/queue/update`, { serial, updates: { progress } }, { timeout: 3000 });
  } catch (e) {}
  if (activeDownloads.has(serial)) {
    const d = activeDownloads.get(serial);
    d.progress = progress;
    d.speed = progress.speed;
  }
}

function speedToMbps(speedStr) {
  if (!speedStr) return 0;
  const m = speedStr.match(/([\d.]+)([KMGT]?i?)B\/s/);
  if (!m) return 0;
  const val = parseFloat(m[1]);
  const unit = (m[2] || '').toLowerCase();
  if (unit.startsWith('k')) return val / 1024;
  if (unit.startsWith('m')) return val;
  if (unit.startsWith('g')) return val * 1024;
  return val / 1048576;
}

function startDownloadTracking(serial, source) {
  activeDownloads.set(serial, { serial, source, startedAt: Date.now(), progress: {}, speed: null });
}

function endDownloadTracking(serial) {
  activeDownloads.delete(serial);
}

function countActiveBySource(site) {
  let count = 0;
  for (const d of activeDownloads.values()) {
    if (d.source === site) count++;
  }
  return count;
}

function sourceSlotsAvailable(site) {
  const limit = SOURCE_LIMITS[site];
  if (!limit) return true; // ilimitado
  return countActiveBySource(site) < limit;
}

async function performanceWatchdog() {
  while (true) {
    await new Promise(r => setTimeout(r, ARIA2.SPEED_CHECK_INTERVAL_MS));
    let totalMbps = 0;
    let slowCount = 0;
    for (const d of activeDownloads.values()) {
      const mbps = speedToMbps(d.speed);
      totalMbps += mbps;
      if (mbps < ARIA2.MIN_SPEED_MBPS) slowCount++;
    }
    const active = activeDownloads.size;
    log.info(`[WATCHDOG] downloads=${active} total=${totalMbps.toFixed(2)}MB/s alvo=${ARIA2.TOTAL_SPEED_MBPS}MB/s lentos=${slowCount}`);
    if (active > 0 && totalMbps < ARIA2.TOTAL_SPEED_MBPS) {
      log.warn(`[WATCHDOG] velocidade total abaixo do alvo: ${totalMbps.toFixed(2)} < ${ARIA2.TOTAL_SPEED_MBPS} MB/s`);
      if (active < WORKERS.DOWNLOAD) {
        log.warn(`[WATCHDOG] poucos downloads ativos (${active}/${WORKERS.DOWNLOAD}). Verificar se search service esta alimentando a fila.`);
      }
    }
    if (slowCount > 0 && slowCount >= active / 2) {
      log.warn(`[WATCHDOG] ${slowCount}/${active} downloads abaixo de ${ARIA2.MIN_SPEED_MBPS}MB/s. Considerar aumentar conexoes ou trocar fontes.`);
    }
  }
}

async function downloadFile(item, url, sourceIndex = 0) {
  const ext = path.extname(new URL(url).pathname) || '.7z';
  const tmpPath = path.join(PSX_DIR, `${item.serial}${ext}`);
  try {
    log.info(`aria2 start ${item.serial} fonte #${sourceIndex + 1}: ${url}`);
    await aria2Download(url, tmpPath, {
      connections: ARIA2.CONNECTIONS,
      split: ARIA2.SPLIT,
      minSpeedMbps: ARIA2.MIN_SPEED_MBPS,
      slowThresholdMs: ARIA2.SLOW_DOWNLOAD_THRESHOLD_MS,
      stalledThresholdMs: ARIA2.SLOW_DOWNLOAD_THRESHOLD_MS + 30000,
      onProgress: (p) => { updateProgress(item.serial, p); }
    });
  } catch (e) {
    log.warn(`aria2 falhou ${item.serial}: ${e.message}. Tentando fallback axios.`);
    const writer = fs.createWriteStream(tmpPath);
    const response = await axios({
      method: 'get',
      url,
      responseType: 'stream',
      timeout: 600000,
      maxRedirects: 5,
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }
    });
    response.data.pipe(writer);
    await new Promise((resolve, reject) => {
      writer.on('finish', resolve);
      writer.on('error', reject);
    });
  }
  return tmpPath;
}

function sortSourcesBySpeed(sources) {
  const speedMap = {
    'coolrom': 20, 'vimm': 19, 'romspedia': 18, 'romsgames': 17, 'retromania': 16,
    'romspure': 15, 'romsretro': 14, 'blueroms': 13, 'consoleroms': 12, 'hexrom': 11,
    'freeroms': 10, 'classicgames': 9, 'oldiesnest': 8, 'playretrogames': 7,
    'roms2000': 6, 'romulation': 5, 'retrogames_cc': 4, 'retrogames_games': 4,
    'myrient': 4, 'homebrew': 4, 'romsdl': 4, 'retrostic': 4, 'retroiso': 4,
    'archive.org': 2, 'archive.org-jp': 2, 'archive_extra': 2, 'archive_org': 2, 'archive_org_jp': 2,
    'google_fallback': 1
  };
  return [...sources].sort((a, b) => (speedMap[b.site] || 3) - (speedMap[a.site] || 3));
}

async function resolveAndDownload(item, sources) {
  if (!sources || !sources.length) throw new Error('sem sources');
  const directExts = ['.7z', '.zip', '.rar', '.iso', '.bin', '.cue', '.img'];
  sources = sortSourcesBySpeed(sources);
  const errors = [];
  for (let i = 0; i < sources.length; i++) {
    const source = sources[i];
    if (!source.url) continue;
    if (!sourceSlotsAvailable(source.site)) {
      errors.push(`${source.site}: limite de downloads simultaneos atingido`);
      continue;
    }
    let url = source.url;
    const isDirect = directExts.some(e => source.url.toLowerCase().endsWith(e));
    if (!isDirect || ['coolrom', 'vimm', 'retrostic', 'romsdl', 'retroiso'].includes(source.site)) {
      try {
        url = await resolvePageDownload(source.url, source.site);
      } catch (e) {
        log.warn(`Nao foi possivel resolver pagina ${source.site} para ${item.serial}: ${e.message}`);
        errors.push(`${source.site}: ${e.message}`);
        continue;
      }
    }
    try {
      startDownloadTracking(item.serial, source.site);
      const tmpPath = await downloadFile(item, url, i);
      // aguarda handles serem liberados
      await new Promise(r => setTimeout(r, 2000));
      if (tmpPath.endsWith('.7z') || tmpPath.endsWith('.zip') || tmpPath.endsWith('.rar')) {
        let archiveOk = false;
        let archiveErr = null;
        for (let attempt = 0; attempt < 3; attempt++) {
          try {
            await testArchive(tmpPath);
            archiveOk = true;
            break;
          } catch (err) {
            archiveErr = err;
            await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
          }
        }
        if (!archiveOk) {
          try { fs.unlinkSync(tmpPath); } catch (e) {}
          throw new Error('arquivo corrompido: ' + archiveErr.message);
        }
        try {
          await extractWith7z(tmpPath, PSX_DIR);
          fs.unlinkSync(tmpPath);
        } catch (extractErr) {
          try { fs.unlinkSync(tmpPath); } catch (e) {}
          throw new Error('extracao falhou: ' + extractErr.message);
        }
      }
      return; // sucesso
    } catch (e) {
      log.warn(`Download fonte #${i + 1} (${source.site}) falhou para ${item.serial}: ${e.message}`);
      errors.push(`${source.site}: ${e.message}`);
    }
  }
  throw new Error('todas as fontes falharam: ' + errors.join(' | '));
}

async function processOne() {
  const { item } = await queueRequest('post', '/queue/next-ready');
  if (!item) return false;

  if (!item.sources || !item.sources.length) {
    await queueRequest('post', '/queue/fail', { serial: item.serial, reason: 'sem URL' });
    return true;
  }

  status.active++;
  try {
    log.info(`Download ${item.serial}: ${item.sources.length} fontes disponiveis`);
    await resolveAndDownload(item, item.sources);
    await queueRequest('post', '/queue/complete', { serial: item.serial });
    status.completed++;
  } catch (e) {
    log.error(`Download falhou ${item.serial}: ${e.message}`);
    await queueRequest('post', '/queue/fail', { serial: item.serial, reason: e.message });
    status.failed++;
  }
  status.active--;
  endDownloadTracking(item.serial);
  return true;
}

async function workerLoop(id) {
  while (true) {
    const hadWork = await processOne();
    if (!hadWork) await new Promise(r => setTimeout(r, 2000));
  }
}

async function loop() {
  const workers = Math.max(1, WORKERS.DOWNLOAD || 1);
  log.info(`Iniciando ${workers} workers de download`);
  await Promise.all(Array.from({ length: workers }, (_, i) => workerLoop(i)));
}

app.get('/status', (req, res) => res.json(status));

process.on('uncaughtException', (e) => log.error(`uncaught: ${e.message}`));
process.on('unhandledRejection', (e) => log.error(`rejection: ${e.message}`));

app.get('/dashboard', (req, res) => res.sendFile(path.join(__dirname, 'dashboard.html')));
app.get('/queue-proxy', async (req, res) => {
  try {
    const r = await axios.get(`http://127.0.0.1:${PORTS.QUEUE}/queue`, { timeout: 3000 });
    res.json(r.data);
  } catch (e) { res.json({ error: e.message }); }
});

app.listen(PORTS.DOWNLOAD, '127.0.0.1', () => {
  log.info(`Download service em http://127.0.0.1:${PORTS.DOWNLOAD}`);
  loop();
  performanceWatchdog();
});
