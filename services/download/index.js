const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { PSX_DIR, PORTS, WORKERS, ARIA2, SOURCE_LIMITS } = require('../../shared/config');
const WORKER_ALLOCATION = require('../../shared/config').WORKER_ALLOCATION || { 'archive.org': 2, 'archive.org-jp': 2, 'coolrom': 5, 'round_robin': 5 };
const Logger = require('../../shared/logger');
const { aria2Download } = require('./aria2');

const log = new Logger('download-service');
const app = express();
app.use(express.json());
app.use('/shared', express.static(path.join(__dirname, '..', '..', 'shared')));

const QUEUE_URL = `http://127.0.0.1:${PORTS.QUEUE}`;

let status = { active: 0, completed: 0, failed: 0 };
let activeDownloads = new Map(); // serial -> { progress, speed, source, startedAt }

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
  
  // === CoolROM ===
  if (siteHint === 'coolrom' || pageUrl.includes('coolrom')) {
    const link = $('a[href*="dl.coolrom"]').attr('href');
    if (link) return link;
  }
  
  // === Vimm: extrai mediaId do HTML, GET dl3 com cookies ===
  if (siteHint === 'vimm' || pageUrl.includes('vimm.net')) {
    // Extrai cookies da resposta (PHPSESSID é necessario)
    const setCookies = res.headers['set-cookie'];
    const cookieStr = setCookies 
      ? (Array.isArray(setCookies) ? setCookies : [setCookies])
          .map(c => c.split(';')[0]).join('; ')
      : '';
    
    // Procura mediaId no JavaScript embutido
    const scriptText = $('script').map((i, el) => $(el).html()).get().join('\n');
    const mediaMatch = scriptText.match(/"ID":(\d+)/);
    const mediaId = mediaMatch ? mediaMatch[1] : null;
    
    if (mediaId) {
      // GET dl3.vimm.net com cookies + Referer retorna o arquivo direto
      const dlUrl = `https://dl3.vimm.net/?mediaId=${mediaId}&alt=0`;
      log.info(`Vimm resolvido: ${dlUrl} (cookies: ${cookieStr ? 'sim' : 'nao'})`);
      // Retorna URL especial com cookies embutidos via header customizado
      // O aria2/axios precisa do Cookie header - armazenamos nos metadados
      return { url: dlUrl, headers: { 'Cookie': cookieStr, 'Referer': pageUrl } };
    }
    throw new Error('vimm: mediaId nao encontrado');
  }
  
  // === RetroStic: POST com session/rom_url/console_url ===
  if (siteHint === 'retrostic' || pageUrl.includes('retrostic')) {
    // Extrai form de download com campos hidden
    const form = $('form[action*="download"]');
    if (form.length) {
      const formData = {};
      form.find('input').each((i, el) => {
        const name = $(el).attr('name');
        const value = $(el).attr('value');
        if (name) formData[name] = value || '';
      });
      
      // POST para {pageUrl}/download
      const dlUrl = pageUrl.endsWith('/') ? pageUrl + 'download' : pageUrl + '/download';
      const postRes = await axios.post(dlUrl, new URLSearchParams(formData).toString(), {
        headers: { 
          ...headers, 
          'Content-Type': 'application/x-www-form-urlencoded',
          'Referer': pageUrl
        },
        timeout: 20000,
        maxRedirects: 0,
        validateStatus: s => s < 400
      });
      
      // Extrai URL do JS redirect
      const jsMatch = postRes.data.match(/window\.location\.href\s*=\s*["']([^"']+)["']/);
      if (jsMatch) return jsMatch[1];
      
      // Ou procura link direto na resposta
      const $resp = cheerio.load(postRes.data);
      const directLink = $resp('a[href*=".7z"], a[href*=".zip"], a[href*=".rar"], a[href*=".iso"]').attr('href');
      if (directLink) return directLink;
      
      throw new Error('retrostic: URL nao extraida do POST');
    }
    throw new Error('retrostic: form de download nao encontrado');
  }
  
  // === RomsDL: POST vazio para /download ===
  if (siteHint === 'romsdl' || pageUrl.includes('romsdl')) {
    const dlUrl = pageUrl.endsWith('/') ? pageUrl + 'download' : pageUrl + '/download';
    let postRes;
    try {
      postRes = await axios.post(dlUrl, '', {
        headers: { ...headers, 'Referer': pageUrl },
        timeout: 20000,
        maxRedirects: 5,
        validateStatus: s => s < 400
      });
    } catch (e) {
      // Se 302 redirect, pega Location
      if (e.response && e.response.headers && e.response.headers.location) {
        return e.response.headers.location;
      }
      throw new Error('romsdl: POST falhou: ' + e.message);
    }
    
    // Se redirect seguido, verifica URL final
    const finalUrl = postRes.request?.res?.responseUrl || postRes.config?.url;
    if (finalUrl && /\.(7z|zip|rar|iso|bin)$/i.test(finalUrl)) {
      return finalUrl;
    }
    
    // Metodo 1: link direto <a> com extensao
    const respData = typeof postRes.data === 'string' ? postRes.data : '';
    const $resp = cheerio.load(respData);
    const directLink = $resp('a[href*=".7z"], a[href*=".zip"], a[href*=".rar"], a[href*=".iso"], a[href*=".bin"]').attr('href');
    if (directLink) return directLink;
    
    // Metodo 2: JS redirect
    const jsMatch = respData.match(/window\.location\.href\s*=\s*["']([^"']+)["']/);
    if (jsMatch) return jsMatch[1];
    
    // Metodo 3: meta refresh
    const metaMatch = respData.match(/<meta[^>]+refresh[^>]+url=([^"'>]+)/i);
    if (metaMatch) return metaMatch[1];
    
    // Metodo 4: Location header
    if (postRes.headers && postRes.headers.location) {
      return postRes.headers.location;
    }
    
    throw new Error('romsdl: URL nao extraida do POST');
  }
  
  // === RomsRetro: link direto dl.romsretro.com ===
  if (siteHint === 'romsretro' || pageUrl.includes('romsretro')) {
    const dlLink = $('a[href*="dl.romsretro.com"]').attr('href');
    if (dlLink) return dlLink;
  }
  
  // === Generico: procura link com extensao ===
  const exts = ['.7z', '.zip', '.rar', '.iso', '.bin', '.cue', '.img', '.chd'];
  let best = null;
  $('a[href]').each((_, el) => {
    const href = $(el).attr('href');
    if (!href) return;
    const lower = href.toLowerCase();
    if (exts.some(e => lower.includes(e))) {
      best = href;
      return false;
    }
    if (lower.includes('/download/') && !best) {
      best = href;
      return false;
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
    log.info(`[WATCHDOG] downloads=${active} total=${totalMbps.toFixed(2)}MB/s alvo=${ARIA2.TOTAL_SPEED_MBPS}MB/s lentos=${slowCount} bySource=${JSON.stringify(bySource)}`);
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

async function downloadFile(item, source, url, sourceIndex = 0, extraHeaders = null) {
  const ext = path.extname(new URL(url).pathname) || '.7z';
  const tmpPath = path.join(PSX_DIR, `${item.serial}${ext}`);
  await acquireSourceSlot(source.site);
  startDownloadTracking(item.serial, source.site);
  try {
    log.info(`aria2 start ${item.serial} fonte #${sourceIndex + 1} (${source.site}): ${url}`);
    await aria2Download(url, tmpPath, {
      connections: ARIA2.CONNECTIONS,
      split: ARIA2.SPLIT,
      minSpeedMbps: ARIA2.MIN_SPEED_MBPS,
      slowThresholdMs: ARIA2.SLOW_DOWNLOAD_THRESHOLD_MS,
      stalledThresholdMs: ARIA2.SLOW_DOWNLOAD_THRESHOLD_MS + 30000,
      onProgress: (p) => { updateProgress(item.serial, p); },
      extraHeaders
    });
  } catch (e) {
    log.warn(`aria2 falhou ${item.serial}: ${e.message}. Tentando fallback axios.`);
    const writer = fs.createWriteStream(tmpPath);
    try {
      const isArchive = url.includes('archive.org');
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
      // Headers extras do resolver (vimm cookies, etc)
      if (extraHeaders) Object.assign(headers, extraHeaders);
      const response = await axios({
        method: 'get',
        url,
        responseType: 'stream',
        timeout: 600000,
        maxRedirects: 5,
        headers
      });
      response.data.pipe(writer);
      await new Promise((resolve, reject) => {
        writer.on('finish', resolve);
        writer.on('error', reject);
        setTimeout(() => reject(new Error('axios stream timeout')), 600000);
      });
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

function sortSourcesBySpeed(sources) {
  // Prioriza fontes diretas e rapidas; diversifica para nao saturar uma so fonte
  const speedMap = {
    // Fontes diretas rapidas (prioridade alta)
    'vimm': 10, 'romsdl': 10, 'retrostic': 10, 'romspedia': 10, 'romsgames': 10,
    'retromania': 10, 'romspure': 10, 'romsretro': 10, 'blueroms': 10, 'consoleroms': 10,
    'hexrom': 10, 'freeroms': 10, 'classicgames': 10, 'oldiesnest': 10, 'playretrogames': 10,
    'roms2000': 10, 'romulation': 10, 'retrogames_cc': 10, 'retrogames_games': 10,
    'myrient': 10, 'homebrew': 10, 'retroiso': 10,
    // CoolROM: rapido mas satura (prioridade media)
    'coolrom': 7,
    // archive.org: lento por arquivo mas estavel (prioridade baixa-media)
    'archive.org': 5, 'archive.org-jp': 5, 'archive_extra': 5, 'archive_org': 5, 'archive_org_jp': 5,
    'archive.org-extra': 5,
    // Fallback web (ultima opcao)
    'google_fallback': 1, 'google-fallback': 1
  };
  // Embaralha fontes com mesma prioridade para diversificar
  const shuffled = [...sources].sort(() => Math.random() - 0.5);
  return shuffled.sort((a, b) => (speedMap[b.site] || 5) - (speedMap[a.site] || 5));
}

async function resolveAndDownload(item, sources, preferredSite) {
  if (!sources || !sources.length) throw new Error('sem sources');
  const directExts = ['.7z', '.zip', '.rar', '.iso', '.bin', '.cue', '.img', '.chd'];
  // Se tem fonte preferida, coloca ela primeiro ANTES do sort
  if (preferredSite && preferredSite !== 'any') {
    const pref = sources.find(s => s.site === preferredSite || s.site === preferredSite.replace('.', '_'));
    if (pref) {
      sources = [pref, ...sources.filter(s => s !== pref)];
    } else {
      sources = sortSourcesBySpeed(sources);
    }
  } else {
    sources = sortSourcesBySpeed(sources);
  }
  const errors = [];
  for (let i = 0; i < sources.length; i++) {
    const source = sources[i];
    if (!source.url) continue;
    // Verifica se ha slot disponivel antes de tentar
    const slotState = getSlotState(source.site);
    if (slotState.current >= slotState.max) {
      // Se e a fonte preferida (worker dedicado), ESPERA o slot
      if (preferredSite && (source.site === preferredSite || source.site === preferredSite.replace('.', '_'))) {
        log.info(`Worker dedicado ${preferredSite} esperando slot para ${item.serial}...`);
        // acquireSourceSlot vai esperar com timeout de 5min
      } else {
        // Se nao e a preferida, pula para proxima fonte
        log.info(`Slot cheio para ${source.site}, pulando para proxima fonte de ${item.serial}`);
        errors.push(`${source.site}: slot cheio`);
        continue;
      }
    }
    let url = source.url;
    let extraHeaders = null;
    const isDirect = directExts.some(e => source.url.toLowerCase().endsWith(e));
    if (!isDirect || ['coolrom', 'vimm', 'retrostic', 'romsdl', 'romsretro'].includes(source.site)) {
      try {
        const resolved = await resolvePageDownload(source.url, source.site);
        if (typeof resolved === 'object' && resolved.url) {
          url = resolved.url;
          extraHeaders = resolved.headers || null;
        } else {
          url = resolved;
        }
      } catch (e) {
        log.warn(`Nao foi possivel resolver pagina ${source.site} para ${item.serial}: ${e.message}`);
        errors.push(`${source.site}: ${e.message}`);
        continue;
      }
    }
    try {
      const tmpPath = await downloadFile(item, source, url, i, extraHeaders);
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

// === Workers dedicados por fonte ===
// Garante diversificacao: 2 archive.org + 2 archive.org-jp + 5 coolrom + 10 RR (cada um numa fonte diferente)
// Meta: mínimo 10 fontes diferentes ativas sempre

// 10 fontes para os 10 RR workers (cada worker fixo numa fonte)
const rrSources = [
  'archive.org-extra',  // RR 0
  'vimm',               // RR 1
  'retrostic',          // RR 2
  'romsdl',             // RR 3
  'romsretro',          // RR 4
  'cdromance',          // RR 5
  'romspedia',          // RR 6
  'romsgames',          // RR 7
  'myrient',            // RR 8
  'homebrew'            // RR 9
];

async function processOneWithPreferredSource(preferredSite) {
  // Pega item ready com fonte preferida via queue service
  const res = await queueRequest('post', '/queue/next-ready', { preferredSite });
  if (!res || !res.item) return false;
  const item = res.item;

  if (!item.sources || !item.sources.length) {
    await queueRequest('post', '/queue/fail', { serial: item.serial, reason: 'sem URL' });
    return true;
  }

  // Se tem fonte preferida, reordena sources para ela primeiro
  if (preferredSite && preferredSite !== 'any') {
    const pref = item.sources.find(s => s.site === preferredSite || s.site === preferredSite.replace('.', '_'));
    if (pref) {
      item.sources = [pref, ...item.sources.filter(s => s !== pref)];
    }
  }

  // Verifica se pelo menos uma fonte tem slot disponivel
  const hasAvailableSlot = item.sources.some(s => {
    const st = getSlotState(s.site);
    return st.current < st.max;
  });
  if (!hasAvailableSlot) {
    // Devolve para a fila - todos slots cheios
    await queueRequest('post', '/queue/requeue', { serial: item.serial });
    log.info(`Item ${item.serial} devolvido - todos slots cheios`);
    return true;
  }

  status.active++;
  let success = false;
  let lastError = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      if (attempt > 0) {
        log.info(`Retry ${attempt}/3 para ${item.serial}...`);
        await new Promise(r => setTimeout(r, 5000 * attempt));
      }
      log.info(`Download ${item.serial}: ${item.sources.length} fontes (tentativa ${attempt + 1}) [worker: ${preferredSite}]`);
      await resolveAndDownload(item, item.sources, preferredSite);
      await queueRequest('post', '/queue/complete', { serial: item.serial });
      status.completed++;
      success = true;
      break;
    } catch (e) {
      lastError = e;
      log.warn(`Tentativa ${attempt + 1}/3 falhou para ${item.serial}: ${e.message}`);
    }
  }
  if (!success) {
    log.error(`Download falhou definitivo ${item.serial}: ${lastError?.message}`);
    await queueRequest('post', '/queue/fail', { serial: item.serial, reason: lastError?.message || 'erro desconhecido' });
    status.failed++;
  }
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
  
  // Workers dedicados para archive.org (2)
  for (let i = 0; i < (alloc['archive.org'] || 2); i++) {
    workers.push(dedicatedWorkerLoop(id++, 'archive.org'));
  }
  // Workers dedicados para archive.org-jp (2)
  for (let i = 0; i < (alloc['archive.org-jp'] || 2); i++) {
    workers.push(dedicatedWorkerLoop(id++, 'archive.org-jp'));
  }
  // Workers dedicados para coolrom (5)
  for (let i = 0; i < (alloc['coolrom'] || 5); i++) {
    workers.push(dedicatedWorkerLoop(id++, 'coolrom'));
  }
  // Workers RR fixos em fontes unicas (10)
  const rrCount = alloc['round_robin'] || 10;
  for (let i = 0; i < rrCount; i++) {
    const source = rrSources[i % rrSources.length];
    workers.push(rrWorkerLoop(id++, source));
  }
  
  const fontesUnicas = 3 + Math.min(rrCount, rrSources.length); // archive.org + archive.org-jp + coolrom + RR unicos
  log.info(`Iniciando ${workers.length} workers: ${alloc['archive.org']||2} archive.org + ${alloc['archive.org-jp']||2} archive.org-jp + ${alloc['coolrom']||5} coolrom + ${rrCount} RR fixos. Meta: ${fontesUnicas} fontes unicas`);
  await Promise.all(workers);
}

app.get('/status', (req, res) => res.json(status));

// Resiliente: nao morre em uncaught/rejection
process.on('uncaughtException', (e) => {
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

app.listen(PORTS.DOWNLOAD, '127.0.0.1', () => {
  log.info(`Download service em http://127.0.0.1:${PORTS.DOWNLOAD}`);
  loop();
  performanceWatchdog();
});
