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

  // 1. Cache local puro (muito rapido, 1.5s)
  const pureCacheNames = names.filter(n => pluginPriority(n) < 50 && isLocalCache(n) && isEnabled(n) && ['archive_org', 'archive_org_jp', 'archive_extra', 'myrient', 'homebrew', 'coolrom', 'romsdl', 'retrostic', 'vimm', 'psxdatacenter'].includes(n));
  const cachePromises = pureCacheNames.map(async name => {
    try { return await searchWithTimeout(name, serial, title, 1500); } catch (e) { return []; }
  });
  const cacheResults = (await Promise.all(cachePromises)).flat();
  for (const s of cacheResults) {
    if (!s.url || seenUrls.has(s.url)) continue;
    seenUrls.add(s.url);
    results.push(s);
    if (results.length >= 10) return results;
  }

  // 2. Buscas online em paralelo (timeout generoso)
  const onlineNames = names.filter(n => pluginPriority(n) < 50 && isEnabled(n) && !['google_fallback', 'bing_fallback', 'duckduckgo_fallback'].includes(n));
  const onlinePromises = onlineNames.map(async name => {
    try { return await searchWithTimeout(name, serial, title, 25000); } catch (e) { return []; }
  });
  const onlineResults = (await Promise.all(onlinePromises)).flat();
  for (const s of onlineResults) {
    if (!s.url || seenUrls.has(s.url)) continue;
    seenUrls.add(s.url);
    results.push(s);
    if (results.length >= 15) return results;
  }

  // 3. Fallback web: so executa se pouco encontrado
  if (results.length < 3) {
    const webNames = names.filter(n => pluginPriority(n) >= 50 && isEnabled(n));
    const webPromises = webNames.map(async name => {
      try { return await searchWithTimeout(name, serial, title, 15000); } catch (e) { return []; }
    });
    const webResults = (await Promise.all(webPromises)).flat();
    for (const s of webResults) {
      if (!s.url || seenUrls.has(s.url)) continue;
      seenUrls.add(s.url);
      results.push(s);
      if (results.length >= 10) return results;
    }
  }

  return results;
}

module.exports = { searchAll, plugins, listPlugins: require('./plugins/loader').listPlugins };
