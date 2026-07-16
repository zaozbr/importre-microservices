// Busca de ROMs homebrew PSX via DuckDuckGo (HTML scraping) + itch.io + GitHub
// Seriais HBREW-XXX sao inventados pelo sistema - buscar SEMPRE pelo titulo, nunca pelo serial
// DuckDuckGo nao bloqueia requests automaticos como Google
const axios = require('axios');
const { buildSource } = require('./_base');

const TIMEOUT = 20000;
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

function cleanTitleStr(title) {
  return title.replace(/\[.*?\]|\(.*?\)/g, '').trim().replace(/\s+/g, ' ');
}

// Extrai URLs de download (diretas ou paginas) do HTML
function extractDownloadUrls(html) {
  const urls = new Set();
  const directMatches = html.match(/https?:\/\/[^\s"'<>]+\.(7z|zip|rar|bin|cue|iso|img|chd|ecm)/gi) || [];
  directMatches.forEach(u => urls.add(u));
  const archiveMatches = html.match(/https?:\/\/archive\.org\/(?:details|download)\/[a-zA-Z0-9_.-]+/gi) || [];
  archiveMatches.forEach(u => urls.add(u));
  const githubMatches = html.match(/https?:\/\/github\.com\/[^/\s]+\/[^/\s]+\/releases\/download\/[^\s"'<>]+/gi) || [];
  githubMatches.forEach(u => urls.add(u));
  const itchMatches = html.match(/https?:\/\/[a-zA-Z0-9-]+\.itch\.io\/[a-zA-Z0-9-]+/gi) || [];
  itchMatches.forEach(u => urls.add(u));
  return [...urls];
}

// Busca generica no DuckDuckGo pelo titulo (sem serial)
async function searchDuckDuckGo(title) {
  if (!title || title.length < 3) return [];
  try {
    const cleanTitle = cleanTitleStr(title);
    const q = encodeURIComponent(`"${cleanTitle}" PSX ROM download`);
    const url = `https://html.duckduckgo.com/html/?q=${q}`;
    const res = await axios.get(url, { timeout: TIMEOUT, headers: { 'User-Agent': UA } });
    const urls = extractDownloadUrls(res.data || '');
    return urls.slice(0, 5).map(u => buildSource('ddg-web', u, `${cleanTitle} (DuckDuckGo)`, {}));
  } catch { return []; }
}

// Busca no DuckDuckGo restrita ao archive.org (encontra identifiers via Google/DDG)
async function searchDuckDuckGoArchive(title) {
  if (!title || title.length < 3) return [];
  try {
    const cleanTitle = cleanTitleStr(title);
    const q = encodeURIComponent(`site:archive.org "${cleanTitle}"`);
    const url = `https://html.duckduckgo.com/html/?q=${q}`;
    const res = await axios.get(url, { timeout: TIMEOUT, headers: { 'User-Agent': UA } });
    const html = res.data || '';
    const archiveMatches = html.match(/archive\.org\/(?:details|download)\/([a-zA-Z0-9_.-]+)/gi) || [];
    const identifiers = [...new Set(archiveMatches.map(m => m.match(/\/([a-zA-Z0-9_.-]+)$/)?.[1]).filter(Boolean))];
    if (!identifiers.length) return [];
    const { getArchiveHeaders } = require('../../../shared/archive_auth');
    const { getAxiosProxyConfig } = require('../../../shared/tor_proxy');
    const hdrs = getArchiveHeaders();
    const results = [];
    for (const id of identifiers.slice(0, 3)) {
      try {
        const metaUrl = `https://archive.org/metadata/${id}`;
        const meta = await axios.get(metaUrl, { timeout: 20000, headers: hdrs, ...getAxiosProxyConfig(metaUrl) });
        const files = meta.data?.files || [];
        const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso|chd)$/i.test(f.name) && f.size > 1024 * 1024);
        if (romFiles.length > 0) {
          const best = romFiles.find(f => f.name.toLowerCase().includes(cleanTitle.toLowerCase().substring(0, 10))) || romFiles[0];
          results.push(buildSource('archive.org', `https://archive.org/download/${id}/${encodeURIComponent(best.name)}`, meta.data?.metadata?.title || id, { size: parseInt(best.size) || 0 }));
        }
      } catch { /* skip */ }
    }
    return results;
  } catch { return []; }
}

// Busca no itch.io (homebrew PSX e comum la)
// Reativado: itchio-downloader resolve downloads via HTTP direto
async function searchItchIo(title) {
  if (!title || title.length < 3) return [];
  try {
    const cleanTitle = cleanTitleStr(title);
    const q = encodeURIComponent(`${cleanTitle} PSX`);
    const url = `https://itch.io/search?q=${q}`;
    const res = await axios.get(url, { timeout: TIMEOUT, headers: { 'User-Agent': UA } });
    const html = res.data || '';
    // Filtrar URLs estaticas (static.itch.io) e manter apenas paginas de jogos
    const itchMatches = html.match(/https?:\/\/[a-zA-Z0-9-]+\.itch\.io\/[a-zA-Z0-9-]+/gi) || [];
    const urls = [...new Set(itchMatches)].filter(u => !u.includes('static.itch.io') && !u.includes('itch.io/lib') && !u.includes('itch.io/translations')).slice(0, 3);
    return urls.map(u => buildSource('itch.io', u, `${cleanTitle} (itch.io)`, {}));
  } catch { return []; }
}

// Busca no GitHub (homebrew PSX e comum em repos)
async function searchGitHub(title) {
  if (!title || title.length < 3) return [];
  try {
    const cleanTitle = cleanTitleStr(title);
    // Buscar por titulo + PSX/PS1/playstation
    const queries = [
      encodeURIComponent(`${cleanTitle} PSX`),
      encodeURIComponent(`${cleanTitle} PS1`),
      encodeURIComponent(`${cleanTitle} playstation homebrew`)
    ];
    const seenRepos = new Set();
    const allRepos = [];
    for (const q of queries) {
      try {
        const url = `https://api.github.com/search/repositories?q=${q}&per_page=5`;
        const res = await axios.get(url, { timeout: 15000, headers: { 'User-Agent': UA, 'Accept': 'application/vnd.github.v3+json' } });
        for (const repo of (res.data?.items || [])) {
          if (!seenRepos.has(repo.full_name)) {
            seenRepos.add(repo.full_name);
            allRepos.push(repo);
          }
        }
      } catch { /* skip */ }
    }
    const results = [];
    for (const repo of allRepos.slice(0, 8)) {
      try {
        const relUrl = `https://api.github.com/repos/${repo.full_name}/releases?per_page=5`;
        const relRes = await axios.get(relUrl, { timeout: 15000, headers: { 'User-Agent': UA, 'Accept': 'application/vnd.github.v3+json' } });
        const releases = relRes.data || [];
        for (const rel of releases) {
          const assets = (rel.assets || []).filter(a => /\.(7z|zip|rar|bin|cue|iso|img|chd|ecm)$/i.test(a.name));
          for (const asset of assets) {
            results.push(buildSource('github', asset.browser_download_url, `${repo.name}/${asset.name}`, { size: asset.size }));
          }
        }
      } catch { /* skip */ }
    }
    return results;
  } catch { return []; }
}

module.exports = {
  name: 'web_search',
  matchType: 'serial',
  needsMultiChunk: false,
  priority: 55,
  enabled: true,
  async search(_serial, title) {
    // Busca SEMPRE pelo titulo - seriais homebrew sao inventados
    const [ddg, ddgArch, itch, gh] = await Promise.all([
      searchDuckDuckGo(title),
      searchDuckDuckGoArchive(title),
      searchItchIo(title),
      searchGitHub(title)
    ]);
    return [...ddg, ...ddgArch, ...itch, ...gh];
  }
};
