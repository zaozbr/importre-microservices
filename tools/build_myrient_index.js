#!/usr/bin/env node
/**
 * build_myrient_index.js
 * Constrói índice myrient_results.json a partir do directory listing do Myrient.
 *
 * O Myrient foi encerrado em 31/03/2026. O script tenta a URL ao vivo primeiro
 * e, se a página não contiver listings (página de shutdown), recorre ao
 * snapshot do Wayback Machine.
 *
 * Fontes:
 *  - Sony - PlayStation (Redump)
 *  - Sony - PlayStation (Asia) (Redump)
 */
const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');
const path = require('path');

const SOURCES = [
  { live: 'https://myrient.erista.me/files/Redump/Sony%20-%20PlayStation/', wayback: '20251231155849' },
  // "Sony - PlayStation (Asia)" não existe no Myrient Redump — apenas "Sony - PlayStation/"
  { live: 'https://myrient.erista.me/files/Redump/Sony%20-%20PlayStation%20(Asia)/', wayback: null },
];

const OUTPUT = 'D:/roms/library/roms/_importre_state/myrient_results.json';

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
};

const TIMEOUT = 30000;

// Serial entre parênteses ou colchetes: (SLUS-01234), [SLUS-01234], (SLUS 01234)
const SERIAL_RE = /[\(\[]([A-Z]{4})[-\s]?(\d{3,5})[\)\]]/i;

function extractSerial(name) {
  const m = name.match(SERIAL_RE);
  if (!m) return null;
  const region = m[1].toUpperCase();
  const num = m[2].padStart(5, '0');
  return `${region}-${num}`;
}

function cleanTitle(name) {
  return name.replace(/\.(zip|chd)$/i, '').trim();
}

async function fetchListing(url, label) {
  console.log(`[fetch] ${label}: ${url}`);
  try {
    const res = await axios.get(url, {
      headers: HEADERS,
      timeout: TIMEOUT,
      responseType: 'text',
      maxRedirects: 5,
    });
    const $ = cheerio.load(res.data);
    const items = [];
    $('a').each((_, el) => {
      const href = $(el).attr('href');
      if (!href) return;
      let name;
      try { name = decodeURIComponent(href); } catch (e) { name = href; }
      if (href.endsWith('/') || href === '../' || href.startsWith('?') || href.startsWith('#')) return;
      if (!/\.(zip|chd)$/i.test(name)) return;
      const fullUrl = new URL(href, url).href;
      const serial = extractSerial(name);
      if (!serial) return;
      items.push({ serial, url: fullUrl, title: cleanTitle(name) });
    });
    console.log(`[fetch] ${items.length} arquivos com serial encontrados`);
    return items;
  } catch (e) {
    console.error(`[erro] ${label}: ${e.message}`);
    return [];
  }
}

(async () => {
  const all = [];
  const seen = new Set();
  for (const src of SOURCES) {
    let items = await fetchListing(src.live, 'live');
    // Se a página live não tem listings (shutdown), usa Wayback
    if (items.length === 0 && src.wayback) {
      const wbUrl = `https://web.archive.org/web/${src.wayback}/${src.live}`;
      items = await fetchListing(wbUrl, 'wayback');
    } else if (items.length === 0 && !src.wayback) {
      console.log(`[skip] Sem snapshot Wayback disponível para: ${src.live}`);
    }
    for (const it of items) {
      const key = it.serial + '|' + it.url;
      if (seen.has(key)) continue;
      seen.add(key);
      all.push(it);
    }
  }
  all.sort((a, b) => a.serial.localeCompare(b.serial));
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, JSON.stringify(all, null, 2));
  console.log(`[done] ${all.length} entradas salvas em ${OUTPUT}`);
  if (all.length > 0) {
    console.log('Exemplos:');
    all.slice(0, 3).forEach(i => console.log(`  ${i.serial}  ${i.title}  ${i.url}`));
  }
})();
