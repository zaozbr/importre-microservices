const axios = require('axios');
const fs = require('fs');
const { SITES_PATH, ARCHIVE_JP_INDEX, COOLROM_INDEX } = require('../../shared/config');

let sites = {};
let archiveJp = {};
let coolrom = {};

try { if (fs.existsSync(SITES_PATH)) sites = JSON.parse(fs.readFileSync(SITES_PATH, 'utf-8')); } catch (e) { }
try { if (fs.existsSync(ARCHIVE_JP_INDEX)) archiveJp = JSON.parse(fs.readFileSync(ARCHIVE_JP_INDEX, 'utf-8')); } catch (e) { }
try { if (fs.existsSync(COOLROM_INDEX)) coolrom = JSON.parse(fs.readFileSync(COOLROM_INDEX, 'utf-8')).cr_data || {}; } catch (e) { }

async function archiveOrgSearch(serial, title, siteConfig) {
  try {
    const q = encodeURIComponent(`"${serial}"`);
    const url = `http://archive.org/advancedsearch.php?q=${q}&fl%5B%5D=identifier&fl%5B%5D=title&sort=title&rows=10&page=1&output=json&save=yes`;
    const res = await axios.get(url, { timeout: 20000 });
    const docs = res.data?.response?.docs || [];
    const sources = [];
    for (const d of docs) {
      try {
        const meta = await axios.get(`http://archive.org/metadata/${d.identifier}`, { timeout: 15000 });
        const files = meta.data?.files || [];
        const romFiles = files.filter(f => /\.(7z|zip|rar|bin|cue|img|iso)$/i.test(f.name) && f.size > 1024 * 1024);
        if (romFiles.length) {
          const best = romFiles.find(f => f.name.toLowerCase().includes(serial.toLowerCase())) || romFiles[0];
          sources.push({
            site: 'archive.org',
            url: `http://archive.org/download/${d.identifier}/${encodeURIComponent(best.name)}`,
            title: d.title,
            size: best.size
          });
        }
      } catch (e) { /* ignore */ }
    }
    return sources;
  } catch (e) {
    return [];
  }
}

function archiveJpSearch(serial) {
  const info = archiveJp[serial];
  if (!info) return [];
  return [{
    site: 'archive.org-jp',
    url: `http://archive.org/download/${info.collection}/${encodeURIComponent(info.file)}`,
    title: info.file,
    size: info.size
  }];
}

function coolromSearch(serial, title) {
  const target = (title || serial).toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
  const results = [];
  for (const data of Object.values(coolrom)) {
    if (!data.norm || !data.url) continue;
    if (data.norm.includes(target) || target.includes(data.norm)) {
      results.push({
        site: 'coolrom',
        url: `https://coolrom.com.au${data.url}`,
        title: data.name
      });
      if (results.length >= 3) break;
    }
  }
  return results;
}

async function vimmSearch(serial, title) {
  try {
    const res = await axios.get(`https://vimm.net/vault/?p=list&system=PSX&q=${encodeURIComponent(title || serial)}`, {
      timeout: 15000,
      headers: { 'User-Agent': 'Mozilla/5.0' }
    });
    const html = res.data;
    const re = /<a href="(\/vault\/\d+)">([^<]+)<\/a>/g;
    const matches = [...html.matchAll(re)].slice(0, 3);
    return matches.map(m => ({
      site: 'vimm',
      url: `https://vimm.net${m[1]}`,
      title: m[2].trim()
    }));
  } catch (e) { return []; }
}

async function searchAll(serial, title) {
  const results = [];
  const cfg = sites.archive_org_jp;
  if (cfg && cfg.enabled !== false) {
    const jp = archiveJpSearch(serial);
    if (jp.length) results.push(...jp);
  }
  if (results.length) return results; // JP index tem alta confiabilidade

  const enabled = Object.entries(sites).filter(([_, v]) => v.enabled !== false).map(([k]) => k);
  if (enabled.includes('archive_org')) {
    const a = await archiveOrgSearch(serial, title, sites.archive_org);
    if (a.length) results.push(...a);
  }
  if (enabled.includes('coolrom')) {
    const c = coolromSearch(serial, title);
    if (c.length) results.push(...c);
  }
  if (enabled.includes('vimm')) {
    const v = await vimmSearch(serial, title);
    if (v.length) results.push(...v);
  }
  return results;
}

module.exports = { searchAll };
