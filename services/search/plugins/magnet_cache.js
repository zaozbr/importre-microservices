/**
 * magnet_cache.js
 *
 * Carrega magnet links do _magnet_cache.json e fornece
 * lookup por nome de colecao ou plugin.
 *
 * Usado pelos plugins archive_* para retornar sources torrent.
 */
const fs = require('fs');
const path = require('path');

const CACHE_FILE = path.join(__dirname, '..', '..', '_magnet_cache.json');
let cache = null;

function loadCache() {
  if (cache !== null) return cache;
  try {
    if (fs.existsSync(CACHE_FILE)) {
      cache = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
    } else {
      cache = {};
    }
  } catch {
    cache = {};
  }
  return cache;
}

/**
 * Obtem magnet link de uma colecao por ID do archive.org.
 * @param {string} collectionId - ex: 'Centuron-PSX'
 * @returns {string|null} magnet link ou null se nao cacheado
 */
function getMagnetByCollection(collectionId) {
  const c = loadCache();
  return c[collectionId]?.magnet || null;
}

/**
 * Obtem magnet link por nome do plugin.
 * @param {string} pluginName - ex: 'archive-centuron-psx'
 * @returns {string|null} magnet link ou null
 */
function getMagnetByPlugin(pluginName) {
  const c = loadCache();
  for (const [_id, data] of Object.entries(c)) {
    if (data.plugin === pluginName) return data.magnet;
  }
  return null;
}

/**
 * Obtem dados completos da colecao por ID.
 * @param {string} collectionId
 * @returns {object|null} { magnet, infoHash, plugin, files }
 */
function getCollectionData(collectionId) {
  const c = loadCache();
  return c[collectionId] || null;
}

/**
 * Lista todas as colecoes cacheadas.
 * @returns {array} [{ id, magnet, infoHash, plugin, fileCount }]
 */
function listCollections() {
  const c = loadCache();
  return Object.entries(c).map(([_id, data]) => ({
    id: _id,
    magnet: data.magnet,
    infoHash: data.infoHash,
    plugin: data.plugin,
    fileCount: data.files?.length || 0
  }));
}

/**
 * Encontra o indice do arquivo dentro do torrent pelo nome.
 * Usado para --select-file no aria2.
 * @param {string} collectionId
 * @param {string} fileName - nome do arquivo procurado
 * @returns {number|null} indice (1-based) ou null
 */
function findFileIndex(collectionId, fileName) {
  const data = getCollectionData(collectionId);
  if (!data || !data.files) return null;
  const lower = fileName.toLowerCase();
  const found = data.files.find(f => f.path.toLowerCase().includes(lower));
  return found ? found.index : null;
}

/**
 * Recarrega o cache (util apos atualizar _magnet_cache.json).
 */
function reload() {
  cache = null;
  return loadCache();
}

module.exports = {
  loadCache,
  getMagnetByCollection,
  getMagnetByPlugin,
  getCollectionData,
  listCollections,
  findFileIndex,
  reload
};
