const fs = require('fs');
const path = require('path');

let cached = null;

function getArchiveCookies() {
  if (cached) return cached;
  try {
    const authFile = path.join(__dirname, 'archive_auth.json');
    if (fs.existsSync(authFile)) {
      const auth = JSON.parse(fs.readFileSync(authFile, 'utf-8'));
      cached = `logged-in-sig=${auth['logged-in-sig']}; logged-in-user=${auth['logged-in-user']}`;
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
