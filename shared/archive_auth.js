const fs = require('fs');
const path = require('path');

let cached = null;
let cachedTime = 0;
const CACHE_TTL_MS = 5 * 60 * 1000; // Reler a cada 5min (cookie pode expirar)

function getArchiveCookies() {
  // Reler arquivo se cache expirou (permite renovar cookie sem restart)
  const now = Date.now();
  if (cached && (now - cachedTime) < CACHE_TTL_MS) return cached;
  try {
    const authFile = path.join(__dirname, 'archive_auth.json');
    if (fs.existsSync(authFile)) {
      const auth = JSON.parse(fs.readFileSync(authFile, 'utf-8'));
      cached = `logged-in-sig=${auth['logged-in-sig']}; logged-in-user=${auth['logged-in-user']}`;
      cachedTime = now;
      return cached;
    }
  } catch (e) {
    console.error('Erro lendo archive_auth.json:', e.message);
  }
  return '';
}

function getArchiveHeaders() {
  const cookie = getArchiveCookies();
  const headers = {
    'Referer': 'https://archive.org/',
    'Accept': '*/*',
  };
  if (cookie) {
    headers['Cookie'] = cookie;
  }
  return headers;
}

module.exports = { getArchiveCookies, getArchiveHeaders };
