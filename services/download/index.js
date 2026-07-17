const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { PSX_DIR, PORTS, WORKERS, ARIA2, SOURCE_LIMITS, DOWNLOAD_DIR, DUP_DIR, STATE_DIR } = require('../../shared/config');
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
  // itch.io e tratado em tryResolveUrl (usa itchio-downloader, nao passa por aqui)
  return resolveGenericLink($, pageUrl);
}

// itch.io: usa itchio-downloader com direct HTTP (sem Puppeteer)
// Puppeteer fallback falha com "spawn UNKNOWN" no Windows — usar apenas direct HTTP
// Baixa o arquivo para DOWNLOAD_DIR e retorna localPath
async function resolveItchIoDownload(pageUrl) {
  const itchDir = path.join(DOWNLOAD_DIR, 'itch');
  if (!fs.existsSync(itchDir)) { try { fs.mkdirSync(itchDir, { recursive: true }); } catch {} }

  // PATH 1: downloadGameDirect (HTTP puro, sem browser) — preferencial
  try {
    const { downloadGameDirect } = require('itchio-downloader/dist/itchDownloader/downloadGameDirect');
    const directResult = await downloadGameDirect({
      itchGameUrl: pageUrl,
      downloadDirectory: itchDir,
      inMemory: false,
    });
    if (directResult && directResult.status && directResult.filePath) {
      return { localPath: directResult.filePath, size: directResult.bytesDownloaded };
    }
    // Direct HTTP falhou — logar motivo e NAO tentar Puppeteer (quebrado no Windows)
    const reason = directResult?.failReason || directResult?.message || 'unknown';
    const httpStatus = directResult?.httpStatus ? ` (HTTP ${directResult.httpStatus})` : '';
    throw new Error(`itch.io direct HTTP falhou: ${reason}${httpStatus}`);
  } catch (e) {
    // Se ja e nosso erro re-lancado, propagar
    if (e.message.includes('itch.io direct HTTP falhou')) throw e;
    // Erro inesperado no direct HTTP
    throw new Error(`itch.io direct HTTP erro: ${e.message}`);
  }
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

async function downloadFile(item, source, url, sourceIndex = 0, extraHeaders = null, multiSourceUrls = null) {
  const isMagnet = url.startsWith('magnet:');
  const isTorrent = url.endsWith('.torrent') && !url.startsWith('http');
  const isBt = isMagnet || isTorrent;
  const ext = isBt ? '.chd' : (path.extname(new URL(url).pathname) || '.7z');
  // Baixar para F:\downloads (nova esteira)
  if (!fs.existsSync(DOWNLOAD_DIR)) { try { fs.mkdirSync(DOWNLOAD_DIR, { recursive: true }); } catch {} }
  const tmpPath = path.join(DOWNLOAD_DIR, `${item.serial}${ext}`);
  // Multi-source: adquirir slot de cada fonte
  const sites = multiSourceUrls ? multiSourceUrls.map(m => m.site) : [source.site];
  for (const site of sites) await acquireSourceSlot(site);
  for (const site of sites) startDownloadTracking(item.serial, site);
  try {
    // itch.io: arquivo ja foi baixado pelo itchio-downloader em tryResolveUrl
    if (extraHeaders && extraHeaders.__localPath) {
      handleLocalFile(extraHeaders.__localPath, tmpPath, item.serial);
      return tmpPath;
    }
    const urlLog = multiSourceUrls ? `${multiSourceUrls.length} fontes (multi-source)` : `fonte #${sourceIndex + 1} (${source.site})`;
    log.info(`aria2 start ${item.serial} ${urlLog}: ${url.substring(0, 80)}...`);
    const opts = buildDownloadOptions(url, item, isBt);
    opts.extraHeaders = extraHeaders;
    // Multi-source: passar array de URLs para o aria2
    const downloadArg = multiSourceUrls ? multiSourceUrls.map(m => m.url) : url;
    await aria2Download(downloadArg, tmpPath, opts);
  } catch (e) {
    await handleDownloadError(e, isBt, tmpPath, url, item.serial, extraHeaders);
  } finally {
    endDownloadTracking(item.serial);
    for (const site of sites) releaseSourceSlot(site);
  }
  return tmpPath;
}

// Move arquivo local (itch.io) para tmpPath
function handleLocalFile(localPath, tmpPath, serial) {
  log.info(`itch.io file already downloaded: ${serial} <- ${localPath}`);
  if (path.resolve(localPath) !== path.resolve(tmpPath)) {
    fs.copyFileSync(localPath, tmpPath);
    try { fs.unlinkSync(localPath); } catch {}
  }
}

// Trata erro de download: BT nao tem fallback, HTTP tenta axios
async function handleDownloadError(e, isBt, tmpPath, url, serial, extraHeaders) {
  if (isBt) {
    try { fs.unlinkSync(tmpPath); } catch {}
    throw e;
  }
  log.warn(`aria2 falhou ${serial}: ${e.message}. Tentando fallback axios.`);
  try {
    await axiosFallbackDownload(url, tmpPath, extraHeaders);
  } catch (axiosErr) {
    try { fs.unlinkSync(tmpPath); } catch {}
    throw new Error(`aria2 + axios falharam: ${e.message} | ${axiosErr.message}`);
  }
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
    // Fontes CHD diretas (prioridade alta - evita conversao)
    'archive_chd_jp': 15, 'archive_ps1_eu_chd_arquivista': 15, 'archive-centuron-psx': 15,
    // Fontes diretas rapidas (prioridade media-alta)
    'vimm': 10, 'romsdl': 10, 'retrostic': 10, 'romspedia': 10, 'romsgames': 10,
    'retromania': 10, 'romspure': 10, 'romsretro': 10, 'blueroms': 10, 'consoleroms': 10,
    'archive_redump_jp': 9, 'archive-gamelist-202205': 8, 'archive-psximagefiles': 8, 'archive-sony-playstation-part1': 8, 'archive-redumpsonyplaystationamerica20160617': 8, 'archive-2024-sony-playstation-usa-hearto-1g1r-collection': 8, 'archive-sony-play-station-japan-non-redump': 8,
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
  // Bonus para URLs .chd diretas (prioriza baixar CHD pronto, evita conversao)
  function chdBonus(source) {
    const urlNoQuery = (source.url || '').split('?')[0].toLowerCase();
    if (urlNoQuery.endsWith('.chd')) return 5;
    return 0;
  }
  // Embaralha fontes com mesma prioridade para diversificar
  const shuffled = [...sources].sort(() => Math.random() - 0.5);
  return shuffled.sort((a, b) => ((speedMap[b.site] || 5) + chdBonus(b)) - ((speedMap[a.site] || 5) + chdBonus(a)));
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
  // itch.io: usa itchio-downloader (baixa arquivo diretamente, sem URL intermediaria)
  if (source.site === 'itch.io' || source.url.includes('itch.io')) {
    const { localPath, size } = await resolveItchIoDownload(source.url);
    return { url: `file:///${localPath.replace(/\\/g, '/')}`, extraHeaders: { __localPath: localPath }, localPath, size };
  }
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

// === Semáforo para limitar conversoes CHD concorrentes ===
// chdman e CPU-intensivo - max 2 simultaneos
const chdSemaphore = { current: 0, max: 6, waiters: [] };

function acquireChdSlot() {
  return new Promise((resolve) => {
    if (chdSemaphore.current < chdSemaphore.max) {
      chdSemaphore.current++;
      resolve();
    } else {
      chdSemaphore.waiters.push(resolve);
    }
  });
}

function releaseChdSlot() {
  chdSemaphore.current--;
  if (chdSemaphore.waiters.length > 0) {
    const next = chdSemaphore.waiters.shift();
    chdSemaphore.current++;
    next();
  }
}

// Spawnar conversao CHD em subprocesso separado (nao bloqueia event loop)
function spawnChdConversion(extractDir, serial) {
  const child = spawn(process.execPath, [
    path.join(__dirname, 'chd_convert_one.js'),
    extractDir,
    serial
  ], {
    windowsHide: true,
    detached: true,
    stdio: 'ignore',
  });
  child.unref();
  return child;
}

function handleDirectChd(tmpPath, item, source) {
  // Se ja for .chd, mover direto para PSX_DIR (sem conversao necessaria)
  const chdDest = path.join(PSX_DIR, path.basename(tmpPath));
  try {
    if (fs.existsSync(chdDest)) {
      // Mover CHD existente para duplicados
      if (!fs.existsSync(DUP_DIR)) fs.mkdirSync(DUP_DIR, { recursive: true });
      const dupDest = path.join(DUP_DIR, path.basename(tmpPath));
      try { fs.renameSync(chdDest, dupDest); } catch {}
    }
    fs.renameSync(tmpPath, chdDest);
    log.info(`CHD direto movido: ${item.serial} (${source.site})`);
  } catch {
    try { fs.copyFileSync(tmpPath, chdDest); fs.unlinkSync(tmpPath); } catch {}
  }
  log.info(`Download concluido: ${item.serial} (${source.site})`);
}

function prepareExtractDir(item) {
  // Criar pasta isolada para descompactacao: F:\downloads\<serial>\
  const extractDir = path.join(DOWNLOAD_DIR, item.serial);
  if (fs.existsSync(extractDir)) {
    try { fs.rmSync(extractDir, { recursive: true, force: true }); } catch {}
  }
  fs.mkdirSync(extractDir, { recursive: true });
  return extractDir;
}

async function extractOrMoveArchive(tmpPath, extractDir, item) {
  // Descompactar se for archive (.7z, .zip, .rar)
  if (tmpPath.endsWith('.7z') || tmpPath.endsWith('.zip') || tmpPath.endsWith('.rar')) {
    try {
      await validateAndExtractTo(tmpPath, extractDir);
    } catch (e) {
      log.warn(`Extracao falhou para ${item.serial}: ${e.message}`);
      try { fs.unlinkSync(tmpPath); } catch {}
      try { fs.rmSync(extractDir, { recursive: true, force: true }); } catch {}
      throw e;
    }
    // Apagar archive apos extrair
    try { fs.unlinkSync(tmpPath); } catch {}
  } else if (tmpPath.endsWith('.iso') || tmpPath.endsWith('.bin') || tmpPath.endsWith('.cue') || tmpPath.endsWith('.img')) {
    // Arquivo de midia direto - mover para pasta isolada
    try {
      fs.renameSync(tmpPath, path.join(extractDir, path.basename(tmpPath)));
    } catch {
      try { fs.copyFileSync(tmpPath, path.join(extractDir, path.basename(tmpPath))); fs.unlinkSync(tmpPath); } catch {}
    }
  }
}

function launchChdConversion(extractDir, serial) {
  // Disparar conversao CHD IMEDIATAMENTE em subprocesso separado
  // Semáforo limita a 2 conversoes simultaneas (chdman e CPU-intensivo)
  // O subprocesso faz: converter -> mover CHD -> mover origens -> apagar pasta
  acquireChdSlot().then(() => {
    spawnChdConversion(extractDir, serial);
    // Monitorar fim do subprocesso para liberar slot
    // Como usamos detached+unref, nao podemos esperar o exit event.
    // Em vez disso, verificar se a pasta foi apagada (sinal de conclusao)
    const checkInterval = setInterval(() => {
      if (!fs.existsSync(extractDir)) {
        clearInterval(checkInterval);
        releaseChdSlot();
      }
    }, 3000);
    // Timeout de 10 minutos (fallback)
    setTimeout(() => {
      clearInterval(checkInterval);
      releaseChdSlot();
    }, 600000);
  });
}

async function processDownload(item, source, url, sourceIndex, extraHeaders, multiSourceUrls = null) {
  const tmpPath = await downloadFile(item, source, url, sourceIndex, extraHeaders, multiSourceUrls);
  await new Promise(r => setTimeout(r, 500));

  if (tmpPath.toLowerCase().endsWith('.chd')) {
    handleDirectChd(tmpPath, item, source);
    return;
  }

  const extractDir = prepareExtractDir(item);
  await extractOrMoveArchive(tmpPath, extractDir, item);
  launchChdConversion(extractDir, item.serial);

  log.info(`Download concluido: ${item.serial} (${source.site}) -> conversao CHD disparada`);
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

// === Nova esteira: extrair para pasta isolada ===
async function validateAndExtractTo(archivePath, destDir) {
  let archiveOk = false;
  let archiveErr = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await testArchive(archivePath);
      archiveOk = true;
      break;
    } catch (err) {
      archiveErr = err;
      await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
    }
  }
  if (!archiveOk) {
    throw new Error('arquivo corrompido: ' + (archiveErr ? archiveErr.message : 'unknown'));
  }
  try {
    await extractWith7z(archivePath, destDir);
  } catch (extractErr) {
    throw new Error('extracao falhou: ' + extractErr.message);
  }
}

// Filtra apenas fontes HTTP direto (nao magnet/torrent) com size conhecido
function filterHttpSources(resolvedSources) {
  return resolvedSources.filter(s => {
    if (!s.url || !s.size) return false;
    const isBt = s.url.startsWith('magnet:') || (s.url.endsWith('.torrent') && !s.url.startsWith('http'));
    return !isBt;
  });
}

// Agrupa fontes por size (mesmo tamanho = provavelmente mesmo arquivo)
function groupBySize(httpSources) {
  const bySize = new Map();
  for (const s of httpSources) {
    const key = String(s.size);
    if (!bySize.has(key)) bySize.set(key, []);
    bySize.get(key).push(s);
  }
  return bySize;
}

// Agrupa fontes HTTP que apontam para o mesmo arquivo (mesmo size) para multi-source download.
// O aria2 vai baixar chunks diferentes de cada URL em paralelo, acelerando o download.
// Fontes BT/magnet nao sao agrupadas (protocolo diferente).
function groupMultiSourceSources(resolvedSources) {
  const httpSources = filterHttpSources(resolvedSources);
  const bySize = groupBySize(httpSources);
  // Para cada grupo com 2+ fontes, criar um multi-source set
  const multiGroups = [];
  const usedSerials = new Set();
  for (const [, group] of bySize) {
    if (group.length >= 2) {
      multiGroups.push(group);
      group.forEach(s => usedSerials.add(s));
    }
  }
  // Fontes restantes (sem grupo ou size desconhecido) ficam como single-source
  const singles = resolvedSources.filter(s => !usedSerials.has(s));
  return { multiGroups, singles };
}

// Resolve todas as URLs das fontes (Fase 1 do resolveAndDownload)
async function resolveAllSources(orderedSources, preferredSite, item, directExts, errors) {
  const resolved = [];
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
    let resolvedSize = source.size || source.metadata?.size;
    try {
      const r = await tryResolveUrl(source, directExts);
      if (r) { url = r.url; extraHeaders = r.extraHeaders; if (r.size) resolvedSize = r.size; }
    } catch (e) {
      log.warn(`Nao foi possivel resolver pagina ${source.site} para ${item.serial}: ${e.message}`);
      errors.push(`${source.site}: ${e.message}`);
      continue;
    }
    resolved.push({ source, url, extraHeaders, index: i, size: resolvedSize });
  }
  return resolved;
}

async function resolveAndDownload(item, sources, preferredSite) {
  if (!sources || !sources.length) throw new Error('sem sources');
  const directExts = ['.7z', '.zip', '.rar', '.iso', '.bin', '.cue', '.img', '.chd'];
  const orderedSources = orderSources(sources, preferredSite);
  const errors = [];

  // Fase 1: Resolver todas as URLs primeiro (para poder agrupar por size)
  const resolved = await resolveAllSources(orderedSources, preferredSite, item, directExts, errors);

  // Fase 2: Agrupar fontes com mesmo size para multi-source
  const { multiGroups, singles } = groupMultiSourceSources(resolved);

  // Fase 3: Tentar multi-source primeiro (mais rapido)
  for (const group of multiGroups) {
    const primary = group[0];
    const multiUrls = group.map(g => ({ url: g.url, site: g.source.site }));
    const sites = multiUrls.map(m => m.site);
    log.info(`Multi-source ${item.serial}: ${group.length} fontes (${sites.join(', ')}) size=${primary.size}`);
    try {
      await processDownload(item, primary.source, primary.url, primary.index, primary.extraHeaders, multiUrls);
      return;
    } catch (e) {
      log.warn(`Multi-source falhou para ${item.serial}: ${e.message}. Tentando fontes individuais.`);
      errors.push(`multi-source(${sites.join(',')}): ${e.message}`);
    }
  }

  // Fase 4: Tentar fontes individuais (fallback)
  for (const r of singles) {
    try {
      await processDownload(item, r.source, r.url, r.index, r.extraHeaders);
      return;
    } catch (e) {
      log.warn(`Download fonte #${r.index + 1} (${r.source.site}) falhou para ${item.serial}: ${e.message}`);
      errors.push(`${r.source.site}: ${e.message}`);
    }
  }
  throw new Error('todas as fontes falharam: ' + errors.join(' | '));
}

// === Workers dedicados por fonte ===
// Garante diversificacao: 2 archive.org + 2 archive.org-jp + 4 coolrom + 12 RR (cada um numa fonte diferente)
// Meta: mínimo 10 fontes diferentes ativas sempre

// Cooldown global por fonte (ex: vimm 429 rate limit)
const COOLDOWN_FILE = path.join(STATE_DIR || 'F:\\importre_state', 'cooldown.json');
const sourceCooldown = new Map(); // site -> timestamp ate quando evitar

// Carregar cooldown persistente na inicializacao
try {
  if (fs.existsSync(COOLDOWN_FILE)) {
    const data = JSON.parse(fs.readFileSync(COOLDOWN_FILE, 'utf8'));
    for (const [site, until] of Object.entries(data)) {
      if (until > Date.now()) sourceCooldown.set(site, until);
    }
    log.info(`Cooldown persistente carregado: ${sourceCooldown.size} fontes`);
  }
} catch {}

function saveCooldown() {
  try {
    const data = {};
    for (const [site, until] of sourceCooldown.entries()) {
      if (until > Date.now()) data[site] = until;
    }
    fs.writeFileSync(COOLDOWN_FILE, JSON.stringify(data));
  } catch {}
}

function isSourceInCooldown(site) {
  const until = sourceCooldown.get(site);
  if (!until) return false;
  if (Date.now() < until) return true;
  sourceCooldown.delete(site);
  return false;
}
function setSourceCooldown(site, ms) {
  sourceCooldown.set(site, Date.now() + ms);
  saveCooldown();
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
  // romsfun removido (403 errors)
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
    // Fallback para 'any' mas filtrar fontes em cooldown
    res = await queueRequest('post', '/queue/next-ready', { preferredSite: 'any' });
  }
  if (res && res.item && res.item.sources) {
    // Filtrar fontes em cooldown SEMPRE (mesmo no caminho principal)
    const before = res.item.sources.map(s => s.site);
    const filtered = res.item.sources.filter(s => !isSourceInCooldown(s.site));
    if (filtered.length > 0) {
      res.item.sources = filtered;
      if (filtered.length < before.length) {
        log.info(`Cooldown filter: ${res.item.serial} ${before.join(',')} -> ${filtered.map(s => s.site).join(',')}`);
      }
    } else if (res.item.sources.length > 0) {
      // Todas as fontes em cooldown — devolver e esperar
      log.info(`Cooldown block: ${res.item.serial} todas fontes em cooldown (${before.join(',')})`);
      await queueRequest('post', '/queue/requeue', { serial: res.item.serial });
      return false;
    }
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
  let idleCycles = 0;
  while (true) {
    const hadWork = await processOneWithPreferredSource(fixedSource);
    if (!hadWork) {
      idleCycles++;
      //apos 2 ciclos ocioso (6s), pega de qualquer fonte para nao ficar parado
      if (idleCycles >= 2) {
        const anyWork = await processOneWithPreferredSource('any');
        if (anyWork) {
          idleCycles = 0;
        } else {
          await new Promise(r => setTimeout(r, 5000));
        }
      } else {
        await new Promise(r => setTimeout(r, 3000));
      }
    } else {
      idleCycles = 0;
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
    // Configurar opcoes globais (max-concurrent=20 para estabilidade)
    try { await aria2Rpc.changeGlobalOption({ 'seed-time': '0', 'max-concurrent-downloads': '60', 'max-connection-per-server': '16', 'split': '16', 'min-split-size': '1M', 'file-allocation': 'none', 'check-certificate': 'false', 'max-overall-download-limit': '0', 'max-download-limit': '0' }); } catch {}
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
app.get('/cooldown-status', (req, res) => {
  const entries = {};
  for (const [site, until] of sourceCooldown.entries()) {
    entries[site] = { until: new Date(until).toISOString(), remaining: Math.ceil((until - Date.now()) / 1000) };
  }
  res.json({ cooldowns: entries });
});
app.post('/cooldown', (req, res) => {
  const { site, ms } = req.body;
  if (!site) return res.status(400).json({ error: 'site required' });
  setSourceCooldown(site, ms || 60000);
  log.warn(`Cooldown manual: ${site} por ${(ms||60000)/1000}s`);
  res.json({ ok: true, site, ms: ms || 60000 });
});

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
