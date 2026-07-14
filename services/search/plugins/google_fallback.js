// google-fallback - crawler de ultima prioridade (priority 99)
// Quando todas as outras fontes falham, faz busca no Google pelo serial do
// jogo + "PSX ROM download" e desce nos resultados ate encontrar um link
// direto para arquivo .7z/.zip/.iso/.bin/.chd.
// Se Google bloquear (429/503), aguarda 30s e tenta DuckDuckGo como alternativa.
const axios = require('axios');
const cheerio = require('cheerio');
const { buildSource } = require('./_base');

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.5',
};

const ROM_EXT_REGEX = /\.(7z|zip|iso|bin|chd)(\?|$)/i;
const VALID_CONTENT_TYPES = [
  'application/zip',
  'application/x-zip-compressed',
  'application/x-7z-compressed',
  'application/x-iso9660-image',
  'application/octet-stream',
  'application/x-bin',
  'binary/octet-stream',
  'application/x-chd',
];
const MIN_FILE_SIZE = 1024 * 1024; // 1 MB
const MAX_RESULTS = 10;
const MAX_DEPTH = 3;
const MAX_PAGES = 20;
const BLOCK_WAIT_MS = 30000;

// Serial sem hifen para variacao de busca (ex: SLPS01348)
function serialVariants(serial) {
  const clean = (serial || '').trim().toUpperCase();
  if (!clean) return [];
  const noHyphen = clean.replace(/-/g, '');
  return [clean, noHyphen];
}

function buildGoogleQueries(serial) {
  const variants = serialVariants(serial);
  if (!variants.length) return [];
  const [s1, s2] = variants;
  const orSerial = s2 ? `"${s1}" OR "${s2}"` : `"${s1}"`;
  return [
    `site:*.com ${orSerial} filetype:zip OR filetype:7z OR filetype:iso OR filetype:bin`,
    `"${s1}" download ROM PSX`,
  ];
}

function buildDuckQuery(serial) {
  const variants = serialVariants(serial);
  if (!variants.length) return '';
  const [s1] = variants;
  return `"${s1}" download ROM PSX 7z zip iso`;
}

// Extrai URLs de resultados organicos do HTML do Google
function extractGoogleResults(html) {
  const $ = cheerio.load(html);
  const urls = [];
  const seen = new Set();
  // Padrao classico: <a href="/url?q=ACTUAL_URL&...">
  $('a[href*="/url?q="]').each((_, el) => {
    const href = $(el).attr('href') || '';
    const m = href.match(/\/url\?q=([^&]+)/);
    if (!m) return;
    const url = decodeURIComponent(m[1]);
    if (seen.has(url)) return;
    if (/google\.|gstatic\.|youtube\.|wikipedia\./i.test(url)) return;
    seen.add(url);
    urls.push(url);
  });
  // Fallback: links diretos nao-google
  if (!urls.length) {
    $('a[href^="http"]').each((_, el) => {
      const href = $(el).attr('href') || '';
      if (/google\.|gstatic\.|youtube\.|wikipedia\./i.test(href)) return;
      if (seen.has(href)) return;
      seen.add(href);
      urls.push(href);
    });
  }
  return urls.slice(0, MAX_RESULTS);
}

// Extrai URLs de resultados do DuckDuckGo HTML
function extractDuckResults(html) {
  const $ = cheerio.load(html);
  const urls = [];
  const seen = new Set();
  $('.result__a[href]').each((_, el) => {
    const href = $(el).attr('href') || '';
    // DuckDuckGo usa redirect: //duckduckgo.com/l/?uddg=ACTUAL_URL
    const m = href.match(/uddg=([^&]+)/);
    let url = href;
    if (m) url = decodeURIComponent(m[1]);
    if (seen.has(url)) return;
    if (/duckduckgo\.|google\.|wikipedia\./i.test(url)) return;
    seen.add(url);
    urls.push(url);
  });
  return urls.slice(0, MAX_RESULTS);
}

// Enstra links diretos para .7z/.zip/.iso/.bin/.chd no HTML da pagina
function findDirectLinks(html, baseUrl) {
  const $ = cheerio.load(html);
  const links = [];
  const seen = new Set();
  $('a[href]').each((_, el) => {
    const href = ($(el).attr('href') || '').trim();
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
    if (!ROM_EXT_REGEX.test(href)) return;
    let full = href;
    if (href.startsWith('/')) {
      const base = baseUrl.match(/^(https?:\/\/[^/]+)/);
      full = base ? base[1] + href : href;
    } else if (!href.startsWith('http')) {
      const dir = baseUrl.replace(/\/[^/]*$/, '/');
      full = dir + href;
    }
    if (seen.has(full)) return;
    seen.add(full);
    links.push(full);
  });
  // Tambem procura URLs literais no texto/HTML
  const re = /https?:\/\/[^\s"'<>]+\.(?:7z|zip|iso|bin|chd)(?:\?[^\s"'<>]*)?/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    if (seen.has(m[0])) continue;
    seen.add(m[0]);
    links.push(m[0]);
  }
  return links;
}

// Enstra links internos da pagina (para descer niveis)
function findInternalLinks(html, baseUrl) {
  const $ = cheerio.load(html);
  const links = [];
  const seen = new Set();
  const baseOrigin = (baseUrl.match(/^(https?:\/\/[^/]+)/) || [])[1];
  $('a[href]').each((_, el) => {
    const href = ($(el).attr('href') || '').trim();
    if (!href || href.startsWith('#') || href.startsWith('javascript:')) return;
    if (ROM_EXT_REGEX.test(href)) return; // direto ja tratado
    let full = href;
    if (href.startsWith('/')) {
      full = baseOrigin ? baseOrigin + href : href;
    } else if (!href.startsWith('http')) {
      const dir = baseUrl.replace(/\/[^/]*$/, '/');
      full = dir + href;
    }
    if (!full.startsWith('http')) return;
    if (seen.has(full)) return;
    // Mesmo dominio (link interno)
    if (baseOrigin && full.startsWith(baseOrigin)) {
      seen.add(full);
      links.push(full);
    }
  });
  return links;
}

// Validacao via HEAD request: content-type e content-length
async function validateDirectUrl(url) {
  try {
    const res = await axios.head(url, { headers: HEADERS, timeout: 15000, maxRedirects: 5 });
    const ct = (res.headers['content-type'] || '').toLowerCase();
    const cl = parseInt(res.headers['content-length'] || '0', 10);
    const ctOk = VALID_CONTENT_TYPES.some(t => ct.includes(t));
    // Se content-length ausente (chunked), aceita se content-type bate
    const sizeOk = cl === 0 ? ctOk : cl >= MIN_FILE_SIZE;
    return ctOk && sizeOk;
  } catch (e) {
    return false;
  }
}

// Crawl recursivo: busca links diretos na pagina, desce niveis se necessario
async function crawlForDirectLinks(url, depth, visited, results) {
  if (visited.size >= MAX_PAGES) return;
  if (visited.has(url)) return;
  if (depth > MAX_DEPTH) return;
  visited.add(url);
  let html;
  try {
    const res = await axios.get(url, { headers: HEADERS, timeout: 15000, maxRedirects: 5 });
    html = res.data;
  } catch (e) {
    return;
  }
  // 1. Links diretos na pagina atual
  const direct = findDirectLinks(html, url);
  for (const dl of direct) {
    if (results.length >= 5) return;
    if (results.some(r => r.url === dl)) continue;
    const valid = await validateDirectUrl(dl);
    if (valid) {
      results.push(buildSource('google-fallback', dl, url, { depth, referer: url }));
    }
  }
  if (results.length >= 5) return;
  // 2. Desce 1 nivel: segue links internos
  if (depth < MAX_DEPTH) {
    const internal = findInternalLinks(html, url);
    for (const link of internal.slice(0, 5)) {
      if (results.length >= 5) return;
      await crawlForDirectLinks(link, depth + 1, visited, results);
    }
  }
}

async function searchEngine(engineUrl, extractor) {
  const res = await axios.get(engineUrl, { headers: HEADERS, timeout: 15000 });
  return extractor(res.data);
}

async function googleSearch(serial) {
  const queries = buildGoogleQueries(serial);
  for (const q of queries) {
    const url = `https://www.google.com/search?q=${encodeURIComponent(q)}&num=10`;
    try {
      return await searchEngine(url, extractGoogleResults);
    } catch (e) {
      const status = e.response && e.response.status;
      if (status === 429 || status === 503) {
        // Google bloqueou: aguarda 30s e tenta DuckDuckGo
        await new Promise(r => setTimeout(r, BLOCK_WAIT_MS));
        return duckDuckGoSearch(serial);
      }
    }
  }
  return [];
}

async function duckDuckGoSearch(serial) {
  const q = buildDuckQuery(serial);
  if (!q) return [];
  const url = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(q)}`;
  try {
    return await searchEngine(url, extractDuckResults);
  } catch (e) {
    return [];
  }
}

module.exports = {
  name: 'google-fallback',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 99,
  enabled: true,
  async search(serial, _title) {
    if (!serial) return [];
    let resultUrls;
    try {
      resultUrls = await googleSearch(serial);
    } catch (e) {
      resultUrls = [];
    }
    if (!resultUrls.length) {
      try {
        resultUrls = await duckDuckGoSearch(serial);
      } catch (e) {
        return [];
      }
    }
    if (!resultUrls.length) return [];
    const visited = new Set();
    const results = [];
    for (const resultUrl of resultUrls.slice(0, MAX_RESULTS)) {
      if (results.length >= 5) break;
      await crawlForDirectLinks(resultUrl, 1, visited, results);
    }
    return results;
  },
  // Exportado para testes
  _internal: {
    buildGoogleQueries,
    extractGoogleResults,
    extractDuckResults,
    findDirectLinks,
    findInternalLinks,
    validateDirectUrl,
    crawlForDirectLinks,
  },
};
