const fs = require('fs');
const { SITES_PATH } = require('../../shared/config');
const { plugins, searchWith } = require('./plugins/loader');

let siteConfig = {};
try { if (fs.existsSync(SITES_PATH)) siteConfig = JSON.parse(fs.readFileSync(SITES_PATH, 'utf-8')); } catch (e) { }

function isEnabled(name) {
  const cfg = siteConfig[name];
  if (!cfg) return true; // default enabled
  return cfg.enabled !== false;
}

function pluginPriority(name) {
  const p = plugins[name];
  const cfg = siteConfig[name];
  if (cfg && typeof cfg.priority === 'number') return cfg.priority;
  return (p && p.priority) || 0;
}

async function searchAll(serial, title) {
  const results = [];
  const seenUrls = new Set();

  // Ordena plugins por prioridade crescente (menor numero = tentar primeiro)
  const names = Object.keys(plugins).sort((a, b) => pluginPriority(a) - pluginPriority(b));

  for (const name of names) {
    if (!isEnabled(name)) continue;
    const p = plugins[name];
    // fontes de cache local / diretas primeiro
    if (p.priority < 50) {
      try {
        const sources = await searchWith(name, serial, title);
        for (const s of sources) {
          if (!s.url || seenUrls.has(s.url)) continue;
          seenUrls.add(s.url);
          results.push(s);
        }
        if (results.length >= 10) break;
      } catch (e) { /* ignore */ }
    }
  }

  // Fallback web: so executa se nenhuma fonte direta encontrou nada
  if (results.length === 0) {
    for (const name of names) {
      const p = plugins[name];
      if (p.priority >= 50 && isEnabled(name)) {
        try {
          const sources = await searchWith(name, serial, title);
          for (const s of sources) {
            if (!s.url || seenUrls.has(s.url)) continue;
            seenUrls.add(s.url);
            results.push(s);
          }
          if (results.length >= 5) break;
        } catch (e) { /* ignore */ }
      }
    }
  }

  return results;
}

module.exports = { searchAll, plugins, listPlugins: require('./plugins/loader').listPlugins };
