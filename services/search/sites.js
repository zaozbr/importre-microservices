const fs = require('fs');
const { SITES_PATH } = require('../../shared/config');
const { plugins, searchWith } = require('./plugins/loader');

let siteConfig = {};
try { if (fs.existsSync(SITES_PATH)) siteConfig = JSON.parse(fs.readFileSync(SITES_PATH, 'utf-8')); } catch (e) { }

function isEnabled(name) {
  const cfg = siteConfig[name];
  if (!cfg) return true;
  return cfg.enabled !== false;
}

function pluginPriority(name) {
  const p = plugins[name];
  const cfg = siteConfig[name];
  if (cfg && typeof cfg.priority === 'number') return cfg.priority;
  return (p && p.priority) || 0;
}

function isLocalCache(name) {
  const p = plugins[name];
  return p && (p.name === 'archive.org' || p.name === 'archive.org-jp' || p.name === 'archive-extra' || p.name === 'coolrom' || p.name === 'myrient' || p.name === 'homebrew' || p.name === 'psxdatacenter' || p.name === 'retroiso' || p.name === 'romsdl' || p.name === 'retrostic' || p.name === 'vimm' || p.name === 'hexrom' || p.name === 'romulation');
}

async function searchWithTimeout(pluginName, serial, title, ms) {
  return new Promise((resolve) => {
    const t = setTimeout(() => resolve([]), ms);
    searchWith(pluginName, serial, title).then(r => { clearTimeout(t); resolve(r); }).catch(() => { clearTimeout(t); resolve([]); });
  });
}

async function searchAll(serial, title) {
  const results = [];
  const seenUrls = new Set();
  const names = Object.keys(plugins).sort((a, b) => pluginPriority(a) - pluginPriority(b));

  // 1. Plugins de cache local em paralelo (rapidos)
  const localNames = names.filter(n => pluginPriority(n) < 50 && isLocalCache(n) && isEnabled(n));
  const localPromises = localNames.map(async name => {
    try {
      return await searchWithTimeout(name, serial, title, 5000);
    } catch (e) { return []; }
  });
  const localResults = (await Promise.all(localPromises)).flat();
  for (const s of localResults) {
    if (!s.url || seenUrls.has(s.url)) continue;
    seenUrls.add(s.url);
    results.push(s);
    if (results.length >= 10) return results;
  }

  // 2. Outros plugins diretos (nao-web) em paralelo com timeout curto
  const directNames = names.filter(n => pluginPriority(n) < 50 && isEnabled(n) && !isLocalCache(n) && !['google_fallback', 'bing_fallback', 'duckduckgo_fallback'].includes(n));
  const directPromises = directNames.map(async name => {
    try {
      return await searchWithTimeout(name, serial, title, 8000);
    } catch (e) { return []; }
  });
  const directResults = (await Promise.all(directPromises)).flat();
  for (const s of directResults) {
    if (!s.url || seenUrls.has(s.url)) continue;
    seenUrls.add(s.url);
    results.push(s);
    if (results.length >= 10) return results;
  }

  // 3. Fallback web: so executa se nada encontrado, com timeout curto e em paralelo
  if (results.length === 0) {
    const webNames = names.filter(n => pluginPriority(n) >= 50 && isEnabled(n));
    const webPromises = webNames.map(async name => {
      try {
        return await searchWithTimeout(name, serial, title, 10000);
      } catch (e) { return []; }
    });
    const webResults = (await Promise.all(webPromises)).flat();
    for (const s of webResults) {
      if (!s.url || seenUrls.has(s.url)) continue;
      seenUrls.add(s.url);
      results.push(s);
      if (results.length >= 5) return results;
    }
  }

  return results;
}

module.exports = { searchAll, plugins, listPlugins: require('./plugins/loader').listPlugins };
