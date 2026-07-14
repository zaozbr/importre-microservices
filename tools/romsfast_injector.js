/**
 * romsfast_injector.js
 *
 * Busca links frescos do romsfast.com a cada 5 minutos e injeta
 * na fila do queue service com sources pre-resolvidas.
 * O token do romsfast expira rapidamente, entao buscamos e inserimos
 * imediatamente para nao perder o token.
 *
 * Fluxo:
 * 1. Pegar itens pending da queue (porta 9001)
 * 2. Para cada item, buscar no romsfun.com a pagina de download
 * 3. Resolver o token fresco de sto.romsfast.com
 * 4. Inserir como source ready na fila com prioridade alta
 * 5. O download service pega imediatamente e baixa antes do token expirar
 */
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');

const QUEUE_URL = 'http://127.0.0.1:9001';
const INTERVAL_MS = 3 * 60 * 1000; // 3 minutos (token expira em ~4min)
const MAX_ITEMS_PER_CYCLE = 30;
const TOKEN_FRESH_MS = 4 * 60 * 1000; // token valido por ~4min

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.5',
};

const ROMSFUN_BASE = 'https://romsfun.com';
const ROMSFUN_PSX_SEARCH = 'https://romsfun.com/roms/playstation/?s=';

const LOG_FILE = 'F:\\importre\\logs\\romsfast_injector.log';

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

/**
 * Busca itens pending na queue que ainda nao tem source romsfun.
 */
async function getPendingItems() {
  try {
    const r = await axios.get(`${QUEUE_URL}/queue`, { timeout: 30000 });
    const queue = r.data;
    if (!queue.queue) return [];
    // Filtra apenas pending e searching (ready ja tem sources de outras fontes)
    // Prioriza US/EU (romsfun tem esses) sobre JP
    const candidates = queue.queue.filter(item => {
      if (!['pending', 'searching'].includes(item.status)) return false;
      const hasRomsfun = item.sources && item.sources.some(s => s.site === 'romsfun');
      return !hasRomsfun;
    });
    // Priorizar US/EU (SLUS, SLES, SCES) sobre JP
    const usEu = candidates.filter(i => i.serial.startsWith('SLUS') || i.serial.startsWith('SLES') || i.serial.startsWith('SCES'));
    const jp = candidates.filter(i => !usEu.includes(i));
    return [...usEu, ...jp].slice(0, MAX_ITEMS_PER_CYCLE);
  } catch (e) {
    log(`Erro buscando queue: ${e.message}`);
    return [];
  }
}

/**
 * Busca pagina de download no romsfun.com por titulo.
 */
async function findDownloadPage(title) {
  const cleanTitle = title.split('(')[0].trim();
  const query = encodeURIComponent(cleanTitle);
  const searchUrl = ROMSFUN_PSX_SEARCH + query;
  const res = await axios.get(searchUrl, { headers: HEADERS, timeout: 15000 });
  const $ = cheerio.load(res.data);
  const links = [];
  const seen = new Set();
  $('a[href*="/roms/playstation/"]').each((_, el) => {
    const href = $(el).attr('href');
    if (!href || href.includes('?s=') || href.includes('/page/') || seen.has(href)) return;
    if (href.endsWith('.html') && href.includes('romsfun.com/roms/playstation/')) {
      seen.add(href);
      links.push(href);
    }
  });
  return links.slice(0, 3);
}

/**
 * Extrai a URL da pagina de download (romsfun.com/download/...).
 */
async function extractDownloadPageUrl(gameUrl) {
  const res = await axios.get(gameUrl, { headers: HEADERS, timeout: 15000 });
  const $ = cheerio.load(res.data);
  let dlUrl = $('a[href*="/download/"]').first().attr('href');
  if (!dlUrl) {
    const match = res.data.match(/href="(https?:\/\/romsfun\.com\/download\/[^"]+)"/);
    if (match) dlUrl = match[1];
  }
  if (!dlUrl) return null;
  if (dlUrl.startsWith('/')) dlUrl = ROMSFUN_BASE + dlUrl;
  return dlUrl;
}

/**
 * Resolve o token fresco de sto.romsfast.com a partir da pagina de download.
 */
async function resolveDirectUrl(downloadPageUrl) {
  const res = await axios.get(downloadPageUrl, { headers: HEADERS, timeout: 15000 });
  const html = res.data;
  // Link direto com token
  const dlMatch = html.match(/href="(https?:\/\/sto\.romsfast\.com\/[^"]*\.(7z|zip|rar|iso|bin|chd)[^"]*)"/i);
  if (dlMatch) return { url: dlMatch[1], referer: downloadPageUrl };
  // Qualquer link externo com extensao de ROM
  const extMatch = html.match(/href="(https?:\/\/(?!romsfun\.com)[^"]*\.(7z|zip|rar|iso|bin|chd)[^"]*)"/i);
  if (extMatch) return { url: extMatch[1], referer: downloadPageUrl };
  // Tenta mirrors /1, /2, /3
  for (let mirror = 1; mirror <= 3; mirror++) {
    try {
      const mirrorUrl = downloadPageUrl.endsWith('/') ? downloadPageUrl + mirror : downloadPageUrl + '/' + mirror;
      const mRes = await axios.get(mirrorUrl, { headers: HEADERS, timeout: 15000 });
      const mMatch = mRes.data.match(/href="(https?:\/\/sto\.romsfast\.com\/[^"]*\.(7z|zip|rar|iso|bin|chd)[^"]*)"/i);
      if (mMatch) return { url: mMatch[1], referer: mirrorUrl };
      const mExt = mRes.data.match(/href="(https?:\/\/(?!romsfun\.com)[^"]*\.(7z|zip|rar|iso|bin|chd)[^"]*)"/i);
      if (mExt) return { url: mExt[1], referer: mirrorUrl };
    } catch { /* tenta proximo mirror */ }
  }
  return null;
}

/**
 * Marca item como ready com source romsfun fresca E adiciona download diretamente ao aria2.
 * Isso elimina o tempo de espera entre injecao e download, evitando que o token expire.
 */
async function markReadyWithRomsfun(serial, title, directUrl, referer) {
  try {
    // 1. Marcar como ready na queue
    const sources = [{
      site: 'romsfun',
      url: directUrl,
      title: title,
      score: 0.9,
      referer: referer,
      fresh: true,
      injectedAt: Date.now(),
      expiresAt: Date.now() + TOKEN_FRESH_MS
    }];
    await axios.post(`${QUEUE_URL}/queue/ready`, { serial, sources }, { timeout: 10000 });

    // 2. Adicionar download DIRETAMENTE ao aria2 (sem esperar o download service)
    try {
      const out = `${serial}.zip`;
      const rpcRes = await axios.post('http://127.0.0.1:16800/jsonrpc', {
        jsonrpc: '2.0', method: 'aria2.addUri', id: 'inj', params: [
          [directUrl],
          {
            dir: 'D:\\roms\\library\\roms\\psx',
            out: out,
            header: [`Referer: ${referer}`],
            'user-agent': HEADERS['User-Agent'],
            'max-connection-per-server': '16',
            'split': '16',
            'min-split-size': '1M',
            'max-tries': '0',
            'retry-wait': '3',
            'connect-timeout': '20',
            'timeout': '20',
            'check-certificate': 'false'
          }
        ]
      }, { timeout: 10000 });
      const gid = rpcRes.data.result;
      log(`READY+ARIA2: ${serial} -> gid=${gid} | ${directUrl.substring(0, 60)}...`);
    } catch (ariaErr) {
      log(`READY (sem aria2): ${serial} -> ${directUrl.substring(0, 80)}... | aria err: ${ariaErr.message}`);
    }
    return true;
  } catch (e) {
    log(`Erro marcando ready ${serial}: ${e.message}`);
    return false;
  }
}

/**
 * Ciclo principal: busca pending, resolve tokens, injeta na fila.
 */
async function cycle() {
  log('=== CICLO INICIO ===');
  const items = await getPendingItems();
  if (!items.length) {
    log('Nenhum item pending sem source romsfun. Aguardando proximo ciclo.');
    return;
  }
  log(`Items pendentes sem romsfun: ${items.length}`);

  let injected = 0;
  let failed = 0;
  let noLinks = 0;
  let noDlPage = 0;
  let noToken = 0;
  for (const item of items) {
    const { serial, title } = item;
    try {
      // 1. Buscar pagina do jogo no romsfun
      const searchTitle = (title || serial).split('(')[0].split('[')[0].trim();
      const gameLinks = await findDownloadPage(searchTitle);
      if (!gameLinks.length) { failed++; noLinks++; if (noLinks <= 3) log(`semLinks: ${serial} | titulo: "${searchTitle}"`); continue; }

      // 2. Extrair pagina de download
      let dlPageUrl = null;
      for (const gameUrl of gameLinks) {
        try {
          dlPageUrl = await extractDownloadPageUrl(gameUrl);
          if (dlPageUrl) break;
        } catch { /* tenta proximo */ }
      }
      if (!dlPageUrl) { failed++; noDlPage++; continue; }

      // 3. Resolver token fresco
      const resolved = await resolveDirectUrl(dlPageUrl);
      if (!resolved) { failed++; noToken++; continue; }

      // 4. Inserir como ready na fila
      const ok = await markReadyWithRomsfun(serial, title, resolved.url, resolved.referer);
      if (ok) injected++;
      else failed++;
    } catch (e) {
      log(`Erro processando ${serial}: ${e.message}`);
      failed++;
    }
  }
  log(`Detalhamento: semLinks=${noLinks} semDlPage=${noDlPage} semToken=${noToken} injetados=${injected}`);
  log(`=== CICLO FIM === Injetados: ${injected} | Falharam: ${failed} | Total: ${items.length}`);
}

// Iniciar
log('=== ROMSFast INJECTOR INICIADO ===');
log(`Intervalo: ${INTERVAL_MS / 1000}s | Max items/ciclo: ${MAX_ITEMS_PER_CYCLE}`);

// Rodar imediatamente
cycle().catch(e => log(`Erro no ciclo inicial: ${e.message}`));

// Repetir a cada 5 minutos
setInterval(() => {
  cycle().catch(e => log(`Erro no ciclo: ${e.message}`));
}, INTERVAL_MS);
