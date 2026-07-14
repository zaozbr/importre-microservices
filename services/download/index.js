const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { PSX_DIR, PORTS, WORKERS, ARIA2, SOURCE_LIMITS } = require('../../shared/config');
const WORKER_ALLOCATION = require('../../shared/config').WORKER_ALLOCATION || { [ARCHIVE_ORG]: 2, [ARCHIVE_ORG_JP]: 2, 'coolrom': 4, 'round_robin': 12 };
const Logger = require('../../shared/logger');
const { aria2Download } = require('./aria2');
const motrixWatchdog = require('./motrix_watchdog');
const aria2Rpc = require('./aria2_rpc');

const log = new Logger('download-service');

// Constantes de fontes (evita duplicacao de string)
const ARCHIVE_ORG = 'archive.org';
const ARCHIVE_ORG_JP = 'archive.org-jp';
const app = express();
app.use(express.json());
app.use('/shared', express.static(path.join(__dirname, '..', '..', 'shared')));

const QUEUE_URL = `http://127.0.0.1:${PORTS.QUEUE}`;

const status = { active: 0, completed: 0, failed: 0 };
const activeDownloads = new Map(); // serial -> { progress, speed, source, startedAt }

// Controle de slots concorrentes por fonte (evita race condition entre workers)
const sourceSlots = new Map(); // site -> { current, max, waiters }

function getSlotState(site) {
  if (!sourceSlots.has(site)) {
    const limit = SOURCE_LIMITS[site] || Infinity;
    sourceSlots.set(site, { current: 0, max: limit, waiters: [] });
  }
  return sourceSlots.get(site);
}

function acquireSourceSlot(site, timeoutMs = 300000) {
  // Timeout de 5min: workers dedicados esperam seu slot
  return new Promise((resolve, reject) => {
    const state = getSlotState(site);
    if (state.current < state.max) {
      state.current++;
      resolve();
      return;
    }
    let timer = null;
    const waiter = () => {
      if (timer) clearTimeout(timer);
      resolve();
    };
    state.waiters.push(waiter);
    if (timeoutMs !== Infinity) {
      timer = setTimeout(() => {
        const idx = state.waiters.indexOf(waiter);
        if (idx !== -1) state.waiters.splice(idx, 1);
        reject(new Error(`timeout aguardando slot de ${site}`));
      }, timeoutMs);
    }
  });
}

function releaseSourceSlot(site) {
  const state = getSlotState(site);
  state.current = Math.max(0, state.current - 1);
  if (state.waiters.length > 0) {
    const next = state.waiters.shift();
    state.current++;
    next();
  }
}

async function queueRequest(method, endpoint, body) {
  const res = await axios({ method, url: `${QUEUE_URL}${endpoint}`, data: body, timeout: 15000 });
  return res.data;
}

async function resolvePageDownload(pageUrl, siteHint) {
  const headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' };
  const res = await axios.get(pageUrl, { headers, timeout: 20000 });
  const $ = cheerio.load(res.data);

  if (siteHint === 'coolrom' || pageUrl.includes('coolrom')) {
    return resolveCoolrom($);
  }
  if (siteHint === 'vimm' || pageUrl.includes('vimm.net')) {
    return resolveVimm($, res, pageUrl);
  }
  if (siteHint === 'retrostic' || pageUrl.includes('retrostic')) {
    return resolveRetrostic($, pageUrl, headers);
  }
  if (siteHint === 'romsdl' || pageUrl.includes('romsdl')) {
    return resolveRomsdl($, res, pageUrl, headers);
  }
  if (siteHint === 'romsretro' || pageUrl.includes('romsretro')) {
    const dl = resolveRomsretro($);
    if (dl) return dl;
  }
  if (siteHint === 'romsfun' || pageUrl.includes('romsfun.com/download/')) {
    return resolveRomsfun($, res, pageUrl, headers);
  }
  return resolveGenericLink($, pageUrl);
}

function resolveCoolrom($) {
  const link = $('a[href*="dl.coolrom"]').attr('href');
  if (link) return link;
  throw new Error('coolrom: link de download nao encontrado');
}

function resolveVimm($, res, pageUrl) {
  const setCookies = res.headers['set-cookie'];
  const cookieStr = setCookies
    ? (Array.isArray(setCookies) ? setCookies : [setCookies])
        .map(c => c.split(';')[0]).join('; ')
    : '';
  const scriptText = $('script').map((i, el) => $(el).html()).get().join('\n');
  const mediaMatch = scriptText.match(/"ID":(\d+)/);
  const mediaId = mediaMatch ? mediaMatch[1] : null;
  if (!mediaId) throw new Error('vimm: mediaId nao encontrado');
  const dlUrl = `https://dl3.vimm.net/?mediaId=${mediaId}&alt=0`;
  log.info(`Vimm resolvido: ${dlUrl} (cookies: ${cookieStr ? 'sim' : 'nao'})`);
  return { url: dlUrl, headers: { 'Cookie': cookieStr, 'Referer': pageUrl } };
}

async function resolveRetrostic($, pageUrl, headers) {
  const form = $('form[action*="download"]');
  if (!form.length) throw new Error('retrostic: form de download nao encontrado');
  const formData = {};
  form.find('input').each((i, el) => {
    const name = $(el).attr('name');
    const value = $(el).attr('value');
    if (name) formData[name] = value || '';
  });
  const dlUrl = pageUrl.endsWith('/') ? pageUrl + 'download' : pageUrl + '/download';
  const postRes = await axios.post(dlUrl, new URLSearchParams(formData).toString(), {
    headers: { ...headers, 'Content-Type': 'application/x-www-form-urlencoded', 'Referer': pageUrl },
    timeout: 20000, maxRedirects: 0, validateStatus: s => s < 400
  });
  const jsMatch = postRes.data.match(/window\.location\.href\s*=\s*["']([^"']+)["']/);
  if (jsMatch) return jsMatch[1];
  const $resp = cheerio.load(postRes.data);
  const directLink = $resp('a[href*=".7z"], a[href*=".zip"], a[href*=".rar"], a[href*=".iso"]').attr('href');
  if (directLink) return directLink;
  throw new Error('retrostic: URL nao extraida do POST');
}

function extractCookieStr(res) {
  const setCookies = res.headers['set-cookie'];
  return setCookies
    ? (Array.isArray(setCookies) ? setCookies : [setCookies])
        .map(c => c.split(';')[0]).join('; ')
    : '';
}

// romsfun: pagina de download tem link para sto.romsfast.com com token
// A pagina mostra "Please wait 7 seconds" e depois "Download Now"
// O link direto esta no HTML: href="https://sto.romsfast.com/...?token=..."
async function resolveRomsfun($, res, pageUrl, headers) {
  // Procura link direto para sto.romsfast.com ou similar com extensao de ROM
  const html = res.data;
  const dlMatch = html.match(/href="(https?:\/\/sto\.romsfast\.com\/[^"]*\.(7z|zip|rar|iso|bin|chd)[^"]*)"/i);
  if (dlMatch) {
    return { url: dlMatch[1], headers: { 'Referer': pageUrl } };
  }
  // Procura qualquer link externo com extensao de ROM
  const extMatch = html.match(/href="(https?:\/\/(?!romsfun\.com)[^"]*\.(7z|zip|rar|iso|bin|chd)[^"]*)"/i);
  if (extMatch) {
    return { url: extMatch[1], headers: { 'Referer': pageUrl } };
  }
  // Tenta mirrors /1, /2, /3
  for (let mirror = 1; mirror <= 3; mirror++) {
    try {
      const mirrorUrl = pageUrl.endsWith('/') ? pageUrl + mirror : pageUrl + '/' + mirror;
      const mRes = await axios.get(mirrorUrl, { headers, timeout: 15000 });
      const mMatch = mRes.data.match(/href="(https?:\/\/sto\.romsfast\.com\/[^"]*\.(7z|zip|rar|iso|bin|chd)[^"]*)"/i);
      if (mMatch) return { url: mMatch[1], headers: { 'Referer': mirrorUrl } };
      const mExt = mRes.data.match(/href="(https?:\/\/(?!romsfun\.com)[^"]*\.(7z|zip|rar|iso|bin|chd)[^"]*)"/i);
      if (mExt) return { url: mExt[1], headers: { 'Referer': mirrorUrl } };
    } catch (e) { /* tenta proximo mirror */ }
  }
  throw new Error('romsfun: link de download nao encontrado');
}

function extractFormData($, formSelector) {
  const form = $(formSelector).first();
  const formData = {};
  if (form.length) {
    form.find('input').each((_, el) => {
      const name = $(el).attr('name');
      const value = $(el).attr('value');
      if (name) formData[name] = value;
    });
  }
  return formData;
}

async function resolveRomsdl($, res, pageUrl, headers) {
  const baseUrl = pageUrl.replace('://www.romsdl.com', '://romsdl.com');
  const dlUrl = baseUrl.endsWith('/') ? baseUrl + 'download' : baseUrl + '/download';
  let formDataFinal = extractFormData($, 'form[action$="/download"][method="post"]');
  let cookieFinal = extractCookieStr(res);

  if (!formDataFinal.session) {
    const reGet = await axios.get(baseUrl, { headers, timeout: 20000, maxRedirects: 5 });
    const $re = cheerio.load(reGet.data);
    formDataFinal = extractFormData($re, 'form[action$="/download"][method="post"]');
    cookieFinal = extractCookieStr(reGet) || cookieFinal;
  }

  log.info(`romsdl: POST form data=${JSON.stringify(formDataFinal)} cookies=${cookieFinal ? 'sim' : 'nao'}`);

  let postRes;
  try {
    postRes = await axios.post(dlUrl, new URLSearchParams(formDataFinal).toString(), {
      headers: {
        ...headers, 'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': baseUrl, ...(cookieFinal ? { 'Cookie': cookieFinal } : {}),
      },
      timeout: 20000, maxRedirects: 5, validateStatus: s => s < 400
    });
  } catch (e) {
    if (e.response && e.response.headers && e.response.headers.location) {
      return e.response.headers.location;
    }
    throw new Error('romsdl: POST falhou: ' + e.message);
  }

  const finalUrl = postRes.request?.res?.responseUrl || postRes.config?.url;
  if (finalUrl && /\.(7z|zip|rar|iso|bin)$/i.test(finalUrl)) return finalUrl;

  const respData = typeof postRes.data === 'string' ? postRes.data : '';
  const $resp = cheerio.load(respData);
  const directLink = $resp('a[href*=".7z"], a[href*=".zip"], a[href*=".rar"], a[href*=".iso"], a[href*=".bin"]').attr('href');
  if (directLink) return directLink;

  const jsMatch = respData.match(/window\.location\.href\s*=\s*["']([^"']+)["']/);
  if (jsMatch) return jsMatch[1];

  const metaMatch = respData.match(/<meta[^>]+refresh[^>]+url=([^"'>]+)/i);
  if (metaMatch) return metaMatch[1];

  if (postRes.headers && postRes.headers.location) return postRes.headers.location;
  if (respData.includes('Invalid session')) throw new Error('romsdl: sessao invalida');
  if (respData.includes('An Error Occurred')) throw new Error('romsdl: pagina de erro');
  throw new Error('romsdl: URL nao extraida do POST');
}

function resolveRomsretro($) {
  return $('a[href*="dl.romsretro.com"]').attr('href') || null;
}

function resolveGenericLink($, pageUrl) {
  const exts = ['.7z', '.zip', '.rar', '.iso', '.bin', '.cue', '.img', '.chd'];
  let best = null;
  $('a[href]').each((_, el) => {
    const href = $(el).attr('href');
    if (!href) return;
    const lower = href.toLowerCase();
    if (exts.some(e => lower.includes(e))) { best = href; return false; }
    if (lower.includes('/download/') && !best) { best = href; return false; }
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
    proc.stderr.on('data', d => { stderr += d.toString(); });
    proc.on('exit', (code) => {
      if (code === 0) resolve(true);
      else reject(new Error(stderr.slice(0, 200)));
    });
    proc.on('error', (err) => reject(new Error('7z.exe nao encontrado: ' + err.message)));
  });
}

function extractWith7z(archivePath, destDir) {
  return new Promise((resolve, reject) => {
    const sevenZip = process.env.SEVEN_ZIP_PATH || 'C:\\Program Files\\7-Zip\\7z.exe';
    if (!fs.existsSync(destDir)) {
      try { fs.mkdirSync(destDir, { recursive: true }); } catch (e) {
        return reject(new Error('destino nao existe e nao pode ser criado: ' + destDir));
      }
    }
    const proc = spawn(sevenZip, ['x', '-y', '-o' + destDir, archivePath], { cwd: destDir, windowsHide: true });
    let stderr = '';
    proc.stderr.on('data', d => { stderr += d.toString(); });
    proc.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(stderr.slice(0, 200)));
    });
    proc.on('error', (err) => reject(new Error('7z.exe nao encontrado: ' + err.message)));
  });
}

// Valida se o conteudo extraido em PSX_DIR contem o serial esperado
function validateExtractedContent(serial) {
  if (!serial) return false;
  try {
    const files = fs.readdirSync(PSX_DIR);
    const serialLower = serial.toLowerCase();
    const matches = files.filter(f =>
      f.toLowerCase().includes(serialLower) &&
      /\.(chd|bin|cue|iso|img)$/i.test(f)
    );
    return matches.length > 0;
  } catch (e) {
    return false;
  }
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

// === Metricas de resiliencia ===
let requeueRecent = []; // timestamps dos requeues recentes

function trackRequeue() {
  const now = Date.now();
  requeueRecent.push(now);
  // Mantem apenas ultimos 60s
  requeueRecent = requeueRecent.filter(t => now - t < 60000);
}

async function performanceWatchdog() {
  while (true) {
    await new Promise(r => setTimeout(r, ARIA2.SPEED_CHECK_INTERVAL_MS));
    let totalMbps = 0;
    let slowCount = 0;
    const bySource = {};
    for (const d of activeDownloads.values()) {
      const mbps = speedToMbps(d.speed);
      totalMbps += mbps;
      if (mbps < ARIA2.MIN_SPEED_MBPS) slowCount++;
      bySource[d.source] = (bySource[d.source] || 0) + 1;
    }
    const active = activeDownloads.size;
    const fontesUnicas = Object.keys(bySource).length;
    
    log.info(`[WATCHDOG] downloads=${active} total=${totalMbps.toFixed(2)}MB/s alvo=${ARIA2.TOTAL_SPEED_MBPS}MB/s lentos=${slowCount} fontes=${fontesUnicas} bySource=${JSON.stringify(bySource)}`);
    
    // Alerta: velocidade abaixo do alvo
    if (active > 0 && totalMbps < ARIA2.TOTAL_SPEED_MBPS) {
      log.warn(`[WATCHDOG] velocidade total abaixo do alvo: ${totalMbps.toFixed(2)} < ${ARIA2.TOTAL_SPEED_MBPS} MB/s`);
      if (active < WORKERS.DOWNLOAD) {
        log.warn(`[WATCHDOG] poucos downloads ativos (${active}/${WORKERS.DOWNLOAD}). Verificar se search service esta alimentando a fila.`);
      }
    }
    
    // Alerta: poucas fontes unicas (meta: 10+)
    if (active > 0 && fontesUnicas < 5) {
      log.warn(`[WATCHDOG] CRITICO: so ${fontesUnicas} fontes ativas (meta 10+). Workers RR podem estar sem itens.`);
    }
    
    // Alerta: muitos downloads lentos
    if (slowCount > 0 && slowCount >= active / 2) {
      log.warn(`[WATCHDOG] ${slowCount}/${active} downloads abaixo de ${ARIA2.MIN_SPEED_MBPS}MB/s. Considerar aumentar conexoes ou trocar fontes.`);
    }
    
    // === DETECCAO DE SPIN LOCK ===
    // Se mais de 30 requeues em 60s = spin lock
    const requeueRate = requeueRecent.length;
    if (requeueRate > 30) {
      log.error(`[WATCHDOG] CRITICO: SPIN LOCK detectado! ${requeueRate} requeues em 60s. Pausando workers por 30s.`);
      // Forca cooldown de todos itens ready
      try {
        await queueRequest('post', '/queue/cooldown-all', { duration: 30000 });
      } catch (e) {}
      requeueRecent = []; // reseta
    } else if (requeueRate > 10) {
      log.warn(`[WATCHDOG] ALERTA: ${requeueRate} requeues em 60s. Possivel spin lock iminente.`);
    }
  }
}

function buildDownloadOptions(url, item, isBt) {
  const isArchive = url.includes(ARCHIVE_ORG);
  return {
    connections: ARIA2.CONNECTIONS,
    split: ARIA2.SPLIT,
    ...(isBt ? { minSpeedMbps: 0.1 } : isArchive ? {} : { minSpeedMbps: ARIA2.MIN_SPEED_MBPS }),
    slowThresholdMs: isBt ? 120000 : ARIA2.SLOW_DOWNLOAD_THRESHOLD_MS,
    stalledThresholdMs: isBt ? 180000 : ARIA2.SLOW_DOWNLOAD_THRESHOLD_MS + 30000,
    maxTimeMs: isBt ? 900000 : 600000,
    onProgress: (p) => { updateProgress(item.serial, p); },
    extraHeaders: null
  };
}

async function downloadFile(item, source, url, sourceIndex = 0, extraHeaders = null) {
  const isMagnet = url.startsWith('magnet:');
  const isTorrent = url.endsWith('.torrent') && !url.startsWith('http');
  const isBt = isMagnet || isTorrent;
  const ext = isBt ? '.chd' : (path.extname(new URL(url).pathname) || '.7z');
  const tmpPath = path.join(PSX_DIR, `${item.serial}${ext}`);
  await acquireSourceSlot(source.site);
  startDownloadTracking(item.serial, source.site);
  try {
    log.info(`aria2 start ${item.serial} fonte #${sourceIndex + 1} (${source.site}): ${url.substring(0, 80)}...`);
    const opts = buildDownloadOptions(url, item, isBt);
    opts.extraHeaders = extraHeaders;
    await aria2Download(url, tmpPath, opts);
  } catch (e) {
    if (isBt) {
      try { fs.unlinkSync(tmpPath); } catch (e2) {}
      throw e;
    }
    log.warn(`aria2 falhou ${item.serial}: ${e.message}. Tentando fallback axios.`);
    try {
      await axiosFallbackDownload(url, tmpPath, extraHeaders);
    } catch (axiosErr) {
      try { fs.unlinkSync(tmpPath); } catch (e2) {}
      throw new Error(`aria2 + axios falharam: ${e.message} | ${axiosErr.message}`);
    }
  } finally {
    endDownloadTracking(item.serial);
    releaseSourceSlot(source.site);
  }
  return tmpPath;
}

async function axiosFallbackDownload(url, tmpPath, extraHeaders) {
  const writer = fs.createWriteStream(tmpPath);
  const isArchive = url.includes(ARCHIVE_ORG);
  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate, br',
  };
  if (isArchive) {
    const { getArchiveHeaders } = require('../../shared/archive_auth');
    const archHdrs = getArchiveHeaders();
    headers['Referer'] = archHdrs['Referer'];
    if (archHdrs['Cookie']) headers['Cookie'] = archHdrs['Cookie'];
  }
  if (extraHeaders) Object.assign(headers, extraHeaders);
  const response = await axios({ method: 'get', url, responseType: 'stream', timeout: 30000, maxRedirects: 5, headers });
  response.data.pipe(writer);
  const STREAM_TIMEOUT_MS = 120000;
  const SLOW_SPEED_THRESHOLD = 0.3;
  const SLOW_SPEED_MS = 120000;
  let streamSlowSince = 0;
  let lastStreamSpeed = 0;
  let lastBytesRead = 0;
  let lastBytesCheck = Date.now();
  response.data.on('data', (chunk) => { lastBytesRead += chunk.length; });
  const streamMonitor = setInterval(() => {
    const now = Date.now();
    const elapsed = (now - lastBytesCheck) / 1000;
    if (elapsed > 0) {
      const bytesPerSec = (lastBytesRead / elapsed);
      lastStreamSpeed = bytesPerSec / 1048576;
      lastBytesRead = 0;
      lastBytesCheck = now;
      if (lastStreamSpeed < SLOW_SPEED_THRESHOLD) {
        if (!streamSlowSince) streamSlowSince = now;
        else if (now - streamSlowSince > SLOW_SPEED_MS) {
          writer.destroy();
          clearInterval(streamMonitor);
        }
      } else { streamSlowSince = 0; }
    }
  }, 5000);
  await new Promise((resolve, reject) => {
    const cleanup = () => clearInterval(streamMonitor);
    writer.on('finish', () => { cleanup(); resolve(); });
    writer.on('error', (err) => { cleanup(); reject(err); });
    setTimeout(() => { cleanup(); writer.destroy(); reject(new Error('axios stream timeout 120s')); }, STREAM_TIMEOUT_MS);
  });
}

function sortSourcesBySpeed(sources) {
  // PRIORIZA TORRENT/MAGNET - depois fontes diretas rapidas
  const speedMap = {
    // TORRENT/MAGNET - prioridade maxima (nao sofre throttling por IP)
    'archive-centuron-psx-torrent': 20,
    'archive-sony-play-station-japan-non-redump-torrent': 20,
    'archive-chd-jp-torrent': 20,
    'archive-gamelist-202205-torrent': 20,
    'archive-ps1-eu-chd-arquivista-torrent': 20,
    'archive-psximagefiles-torrent': 20,
    'archive-redumpsonyplaystationamerica20160617-torrent': 20,
    'archive-sony-playstation-part1-torrent': 20,
    // Fontes diretas rapidas (prioridade alta)
    'vimm': 10, 'romsdl': 10, 'retrostic': 10, 'romspedia': 10, 'romsgames': 10,
    'retromania': 10, 'romspure': 10, 'romsretro': 10, 'blueroms': 10, 'consoleroms': 10, 'archive_chd_jp': 8, 'archive_redump_jp': 7, 'archive-gamelist-202205': 6, 'archive-ps1-eu-chd-arquivista': 6, 'archive-psximagefiles': 6, 'archive-sony-playstation-part1': 6, 'archive-centuron-psx': 6, 'archive-redumpsonyplaystationamerica20160617': 6, 'archive-2024-sony-playstation-usa-hearto-1g1r-collection': 6, 'archive-sony-play-station-japan-non-redump': 6,
    'hexrom': 10, 'freeroms': 10, 'classicgames': 10, 'oldiesnest': 10, 'playretrogames': 10,
    'roms2000': 10, 'romulation': 10, 'retrogames_cc': 10, 'retrogames_games': 10,
    'myrient': 10, 'homebrew': 10, 'retroiso': 10, 'romsfun': 10, 'cdromance': 10,
    'psxdatacenter': 8,
    // CoolROM: rapido mas satura (prioridade media)
    'coolrom': 7,
    // archive.org: lento por arquivo mas estavel (prioridade baixa-media)
    [ARCHIVE_ORG]: 5, [ARCHIVE_ORG_JP]: 5, 'archive_extra': 5, 'archive_org': 5, 'archive_org_jp': 5,
    'archive.org-extra': 5,
    // Fallback web (ultima opcao)
    'google_fallback': 3, 'google-fallback': 3
  };
  // Embaralha fontes com mesma prioridade para diversificar
  const shuffled = [...sources].sort(() => Math.random() - 0.5);
  return shuffled.sort((a, b) => (speedMap[b.site] || 5) - (speedMap[a.site] || 5));
}

function orderSources(sources, preferredSite) {
  if (preferredSite && preferredSite !== 'any') {
    const pref = sources.find(s => s.site === preferredSite || s.site === preferredSite.replace('.', '_'));
    if (pref) return [pref, ...sources.filter(s => s !== pref)];
  }
  return sortSourcesBySpeed(sources);
}

const RESOLVER_SITES = ['coolrom', 'vimm', 'retrostic', 'romsdl', 'romsretro', 'romsfun'];

async function tryResolveUrl(source, directExts) {
  // Magnet links e .torrent locais nao precisam resolver pagina
  if (source.url.startsWith('magnet:')) return null;
  if (source.url.endsWith('.torrent') && !source.url.startsWith('http')) return null;
  // Remove query string antes de checar extensao (URLs com token: file.zip?token=...)
  const urlNoQuery = source.url.split('?')[0].toLowerCase();
  const isDirect = directExts.some(e => urlNoQuery.endsWith(e));
  if (isDirect && !RESOLVER_SITES.includes(source.site)) return null;
  const resolved = await resolvePageDownload(source.url, source.site);
  if (typeof resolved === 'object' && resolved.url) {
    return { url: resolved.url, extraHeaders: resolved.headers || null };
  }
  return { url: resolved, extraHeaders: null };
}

async function processDownload(item, source, url, sourceIndex, extraHeaders) {
  const tmpPath = await downloadFile(item, source, url, sourceIndex, extraHeaders);
  await new Promise(r => setTimeout(r, 2000));
  if (tmpPath.endsWith('.7z') || tmpPath.endsWith('.zip') || tmpPath.endsWith('.rar')) {
    await validateAndExtract(tmpPath);
  }
  const contentOk = validateExtractedContent(item.serial);
  if (!contentOk) {
    log.warn(`Conteudo extraido para ${item.serial} nao contem serial - possivel download errado`);
  }
  log.info(`Download concluido: ${item.serial} (${source.site})`);
}

async function validateAndExtract(tmpPath) {
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

async function resolveAndDownload(item, sources, preferredSite) {
  if (!sources || !sources.length) throw new Error('sem sources');
  const directExts = ['.7z', '.zip', '.rar', '.iso', '.bin', '.cue', '.img', '.chd'];
  const orderedSources = orderSources(sources, preferredSite);
  const errors = [];
  for (let i = 0; i < orderedSources.length; i++) {
    const source = orderedSources[i];
    if (!source.url) continue;
    const slotState = getSlotState(source.site);
    if (slotState.current >= slotState.max) {
      if (preferredSite && (source.site === preferredSite || source.site === preferredSite.replace('.', '_'))) {
        log.info(`Worker dedicado ${preferredSite} esperando slot para ${item.serial}...`);
      } else {
        log.info(`Slot cheio para ${source.site}, pulando para proxima fonte de ${item.serial}`);
        errors.push(`${source.site}: slot cheio`);
        continue;
      }
    }
    let url = source.url;
    let extraHeaders = null;
    try {
      const resolved = await tryResolveUrl(source, directExts);
      if (resolved) { url = resolved.url; extraHeaders = resolved.extraHeaders; }
    } catch (e) {
      log.warn(`Nao foi possivel resolver pagina ${source.site} para ${item.serial}: ${e.message}`);
      errors.push(`${source.site}: ${e.message}`);
      continue;
    }
    try {
      await processDownload(item, source, url, i, extraHeaders);
      return;
    } catch (e) {
      log.warn(`Download fonte #${i + 1} (${source.site}) falhou para ${item.serial}: ${e.message}`);
      errors.push(`${source.site}: ${e.message}`);
    }
  }
  throw new Error('todas as fontes falharam: ' + errors.join(' | '));
}

// === Workers dedicados por fonte ===
// Garante diversificacao: 2 archive.org + 2 archive.org-jp + 4 coolrom + 12 RR (cada um numa fonte diferente)
// Meta: mínimo 10 fontes diferentes ativas sempre

// Cooldown global por fonte (ex: vimm 429 rate limit)
const sourceCooldown = new Map(); // site -> timestamp ate quando evitar
function isSourceInCooldown(site) {
  const until = sourceCooldown.get(site);
  if (!until) return false;
  if (Date.now() < until) return true;
  sourceCooldown.delete(site);
  return false;
}
function setSourceCooldown(site, ms) {
  sourceCooldown.set(site, Date.now() + ms);
  log.warn(`Fonte ${site} em cooldown por ${ms/1000}s (rate limit)`);
}

// 28 fontes para os 28 RR workers - inclui torrent + 6 fontes novas
const rrSources = [
  // === TORRENT/MAGNET (prioridade maxima) ===
  'archive-centuron-psx-torrent',                    // RR 0
  'archive-sony-play-station-japan-non-redump-torrent', // RR 1
  'archive-chd-jp-torrent',                          // RR 2
  'archive-redumpsonyplaystationamerica20160617-torrent', // RR 3
  'archive-sony-playstation-part1-torrent',          // RR 4
  'archive-psximagefiles-torrent',                   // RR 5
  'archive-ps1-eu-chd-arquivista-torrent',           // RR 6
  'archive-gamelist-202205-torrent',                 // RR 7
  // === HTTP direto (fontes web) ===
  'vimm',                        // RR 8
  'retrostic',                   // RR 9
  'romsdl',                      // RR 10
  'romsretro',                   // RR 11
  'cdromance',                   // RR 12
  'romspedia',                   // RR 13
  'romsgames',                   // RR 14
  'myrient',                     // RR 15
  'romsfun',                     // RR 16
  'consoleroms',                 // RR 17
  'romulation',                  // RR 18
  'freeroms',                    // RR 19
  // === HTTP archive.org (colecoes) ===
  'archive_chd_jp',              // RR 20
  'archive_redump_jp',           // RR 21
  'archive.org-extra',           // RR 22
  'homebrew',                    // RR 23
  'archive_sony_playstation_part1', // RR 24
  'archive_psximagefiles',       // RR 25
  'archive_ps1_eu_chd_arquivista', // RR 26
  'archive_gamelist_202205',     // RR 27
  // === Novas fontes (psxdatacenter, retromania, romspure) ===
  'psxdatacenter',               // RR 28
  'retromania',                  // RR 29
  'romspure'                     // RR 30
];

async function executeDownloadWithRetry(item, preferredSite, maxAttempts) {
  let success = false;
  let lastError = null;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      if (attempt > 0) {
        log.info(`Retry ${attempt}/${maxAttempts} para ${item.serial}...`);
        await new Promise(r => setTimeout(r, 3000 * attempt));
      }
      log.info(`Download ${item.serial}: ${item.sources.length} fontes (tentativa ${attempt + 1}) [worker: ${preferredSite}]`);
      await resolveAndDownload(item, item.sources, preferredSite);
      await queueRequest('post', '/queue/complete', { serial: item.serial });
      status.completed++;
      success = true;
      break;
    } catch (e) {
      lastError = e;
      if (e.message && e.message.includes('429')) {
        setSourceCooldown(preferredSite, 60000);
      }
      log.warn(`Tentativa ${attempt + 1}/${maxAttempts} falhou para ${item.serial}: ${e.message}`);
    }
  }
  return { success, lastError };
}

async function handleDownloadFailure(item, lastError) {
  log.error(`Download falhou definitivo ${item.serial}: ${lastError?.message}`);
  item.retry_count = (item.retry_count || 0) + 1;
  if (item.retry_count >= 5) {
    await queueRequest('post', '/queue/fail', { serial: item.serial, reason: lastError?.message || 'erro desconhecido' });
    status.failed++;
  } else {
    await queueRequest('post', '/queue/requeue', { serial: item.serial });
    log.info(`Item ${item.serial} devolvido para retry (${item.retry_count}/5 falhas)`);
  }
}

async function processOneWithPreferredSource(preferredSite) {
  if (preferredSite && preferredSite !== 'any' && isSourceInCooldown(preferredSite)) {
    const remaining = Math.ceil((sourceCooldown.get(preferredSite) - Date.now()) / 1000);
    log.info(`Worker ${preferredSite} aguardando cooldown (${remaining}s)...`);
    await new Promise(r => setTimeout(r, Math.min(remaining * 1000, 30000)));
    return false;
  }
  let res = await queueRequest('post', '/queue/next-ready', { preferredSite });
  if ((!res || !res.item) && preferredSite && preferredSite !== 'any') {
    res = await queueRequest('post', '/queue/next-ready', { preferredSite: 'any' });
  }
  if (!res || !res.item) return false;
  const item = res.item;

  if (!item.sources || !item.sources.length) {
    await queueRequest('post', '/queue/fail', { serial: item.serial, reason: 'sem URL' });
    return true;
  }

  if (preferredSite && preferredSite !== 'any') {
    const pref = item.sources.find(s => s.site === preferredSite || s.site === preferredSite.replace('.', '_'));
    if (pref) item.sources = [pref, ...item.sources.filter(s => s !== pref)];
  }

  const hasAvailableSlot = item.sources.some(s => getSlotState(s.site).current < getSlotState(s.site).max);
  if (!hasAvailableSlot) {
    trackRequeue();
    await queueRequest('post', '/queue/requeue', { serial: item.serial });
    log.info(`Item ${item.serial} devolvido (cooldown 15s) - todos slots cheios`);
    await new Promise(r => setTimeout(r, 5000));
    return true;
  }

  status.active++;
  const { success, lastError } = await executeDownloadWithRetry(item, preferredSite, 2);
  if (!success) await handleDownloadFailure(item, lastError);
  status.active--;
  return true;
}

async function dedicatedWorkerLoop(id, preferredSite) {
  log.info(`Worker ${id} dedicado a: ${preferredSite}`);
  while (true) {
    const hadWork = await processOneWithPreferredSource(preferredSite);
    if (!hadWork) await new Promise(r => setTimeout(r, 3000));
  }
}

async function rrWorkerLoop(id, fixedSource) {
  log.info(`Worker RR ${id} fixo na fonte: ${fixedSource}`);
  while (true) {
    const hadWork = await processOneWithPreferredSource(fixedSource);
    if (!hadWork) {
      // Se nao achou item com essa fonte, espera 3s e tenta de novo
      // (nao pega de outra fonte - mantem diversificacao)
      await new Promise(r => setTimeout(r, 3000));
    }
  }
}

async function loop() {
  const alloc = WORKER_ALLOCATION;
  const workers = [];
  let id = 0;

  // Iniciar watchdog do Motrix em background
  motrixWatchdog.watchdogLoop().catch(e => log.warn(`Watchdog erro: ${e.message}`));
  log.info('Motrix watchdog iniciado em background');

  // Garantir que Motrix esta rodando
  const motrixAwake = await motrixWatchdog.ensureMotrixRunning();
  if (motrixAwake) {
    log.info('Motrix RPC ativo na porta 16800 - downloads via JSON-RPC');
    // Configurar seed-time=0 globalmente
    try { await aria2Rpc.changeGlobalOption({ 'seed-time': '0', 'max-concurrent-downloads': '50' }); } catch {}
  } else {
    log.warn('Motrix indisponivel - fallback para spawn de aria2c.exe');
  }

  // Workers dedicados para archive.org (2)
  for (let i = 0; i < (alloc[ARCHIVE_ORG] || 2); i++) {
    workers.push(dedicatedWorkerLoop(id++, ARCHIVE_ORG));
  }
  // Workers dedicados para archive.org-jp (2)
  for (let i = 0; i < (alloc[ARCHIVE_ORG_JP] || 2); i++) {
    workers.push(dedicatedWorkerLoop(id++, ARCHIVE_ORG_JP));
  }
  // Workers dedicados para coolrom (0 - desativado por bug de volume)
  for (let i = 0; i < (alloc['coolrom'] || 0); i++) {
    workers.push(dedicatedWorkerLoop(id++, 'coolrom'));
  }
  // Workers RR fixos em fontes unicas (28 - inclui 8 torrent)
  const rrCount = alloc['round_robin'] || 28;
  for (let i = 0; i < rrCount; i++) {
    const source = rrSources[i % rrSources.length];
    workers.push(rrWorkerLoop(id++, source));
  }

  const fontesUnicas = 4 + Math.min(rrCount, rrSources.length); // archive.org + archive.org-jp + coolrom + RR unicos
  log.info(`Iniciando ${workers.length} workers: ${alloc[ARCHIVE_ORG]||2} ${ARCHIVE_ORG} + ${alloc[ARCHIVE_ORG_JP]||2} ${ARCHIVE_ORG_JP} + ${alloc['coolrom']||0} coolrom + ${rrCount} RR fixos. Meta: ${fontesUnicas} fontes unicas`);
  await Promise.all(workers);
}

app.get('/status', (req, res) => res.json(status));

// Resiliente: nao morre em uncaught/rejection
process.on('uncaughtException', (e) => {
  if (e && e.code === 'EPIPE') return;
  console.error('uncaughtException', e.stack || e.message);
  log.error(`uncaught: ${e.message}`);
});
process.on('unhandledRejection', (e) => {
  console.error('unhandledRejection', e && e.stack || e && e.message || e);
  log.error(`rejection: ${e && e.message || e}`);
});

app.get('/dashboard', (req, res) => res.sendFile(path.join(__dirname, 'dashboard.html')));
app.get('/queue-proxy', async (req, res) => {
  try {
    const r = await axios.get(`http://127.0.0.1:${PORTS.QUEUE}/queue`, { timeout: 15000 });
    res.json(r.data);
  } catch (e) { res.json({ error: e.message }); }
});

// === Exports para testes ===
module.exports = {
  resolvePageDownload,
  resolveCoolrom,
  resolveVimm,
  resolveRetrostic,
  resolveRomsdl,
  resolveRomsretro,
  resolveGenericLink,
  extractCookieStr,
  extractFormData,
  speedToMbps,
  sortSourcesBySpeed,
  orderSources,
  tryResolveUrl,
  validateAndExtract,
  resolveAndDownload,
  processOneWithPreferredSource,
  executeDownloadWithRetry,
  handleDownloadFailure,
  getSlotState,
  acquireSourceSlot,
  releaseSourceSlot,
  startDownloadTracking,
  endDownloadTracking,
  trackRequeue,
  isSourceInCooldown,
  setSourceCooldown,
  validateExtractedContent,
  testArchive,
  extractWith7z,
  downloadFile,
  status,
  activeDownloads,
  sourceSlots,
  sourceCooldown,
  app,
};

// === Inicializacao do servidor (so quando executado diretamente) ===
if (require.main === module) {
  const server = app.listen(PORTS.DOWNLOAD, '127.0.0.1', () => {
    log.info(`Download service em http://127.0.0.1:${PORTS.DOWNLOAD}`);
    loop();
    performanceWatchdog();
  });
  server.on('error', (e) => {
    if (e.code === 'EADDRINUSE') {
      log.error(`Porta ${PORTS.DOWNLOAD} em uso. Encerrando (outra instancia ja rodando).`);
      process.exit(1);
    }
    log.error(`Erro no servidor: ${e.message}`);
  });
}
