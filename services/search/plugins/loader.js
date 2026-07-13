const fs = require('fs');
const path = require('path');

const plugins = {};
const pluginsDir = __dirname;

for (const file of fs.readdirSync(pluginsDir)) {
  if (!file.endsWith('.js') || file === 'loader.js') continue;
  const name = path.basename(file, '.js');
  try {
    const p = require(path.join(pluginsDir, file));
    if (typeof p.search === 'function' && p.name) {
      plugins[name] = p;
    }
  } catch (e) {
    console.error('Erro carregando plugin', name, e.message);
  }
}

function listPlugins() {
  return Object.entries(plugins).map(([name, p]) => ({
    name,
    matchType: p.matchType || 'unknown',
    needsMultiChunk: !!p.needsMultiChunk,
    priority: p.priority || 0,
    enabled: p.enabled !== false
  }));
}

async function searchWith(pluginName, serial, title) {
  const plugin = plugins[pluginName];
  if (!plugin || plugin.enabled === false) return [];
  try {
    return await plugin.search(serial, title);
  } catch (e) {
    console.error('Plugin error', pluginName, e.message);
    return [];
  }
}

module.exports = { plugins, listPlugins, searchWith };
