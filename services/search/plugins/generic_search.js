const axios = require('axios');
const { normalize, buildSource } = require('./_base');

const cache = new Map();

async function fetchHtml(url, timeout = 15000) {
  const key = url;
  if (cache.has(key)) return cache.get(key);
  try {
    const res = await axios.get(url, {
      timeout,
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' }
    });
    cache.set(key, res.data);
    return res.data;
  } catch (e) {
    return null;
  }
}

function extractLinks(html, baseUrl, patterns, title) {
  if (!html) return [];
  const results = [];
  const normTitle = normalize(title);
  const stopWords = ['privacy', 'policy', 'register', 'login', 'terms', 'contact', 'about', 'home', 'faq', 'dmca', 'sitemap', 'hot', 'best', 'games', 'roms'];
  for (const pattern of patterns) {
    const re = new RegExp(pattern, 'gi');
    let m;
    while ((m = re.exec(html)) !== null) {
      const href = m[1].replace(/&amp;/g, '&');
      const text = (m[2] || '').trim();
      let url = href;
      if (url.startsWith('/')) url = baseUrl + url;
      else if (!url.startsWith('http')) url = baseUrl + '/' + url;
      const normText = normalize(text);
      const lowUrl = url.toLowerCase();
      if (stopWords.some(w => lowUrl.includes('/' + w) || normText === w)) continue;
      if (normTitle && normText && !normText.includes(normTitle) && !normTitle.includes(normText)) continue;
      results.push({ url, text });
    }
  }
  return results;
}

async function genericSiteSearch(site, baseUrl, searchUrl, linkPatterns, serial, title) {
  try {
    const query = encodeURIComponent(title || serial);
    const url = searchUrl.replace('{query}', query);
    const html = await fetchHtml(url);
    const links = extractLinks(html, baseUrl, linkPatterns, title || serial);
    return links.slice(0, 3).map(l => buildSource(site, l.url, l.text || title || serial));
  } catch (e) {
    return [];
  }
}

module.exports = { fetchHtml, extractLinks, genericSiteSearch };
