// Testes para o plugin google-fallback: crawler de ultima prioridade
// Mocka respostas do Google e paginas de download para verificar:
// - Extracao de URLs de resultados organicos
// - Descida de niveis no crawl (links internos)
// - Validacao via HEAD (content-type e content-length)
// - Fallback para DuckDuckGo quando Google bloqueia (429/503)
// Roda: npx mocha tests/download/google_fallback.test.js --timeout 60000
require('./_setup');
const { expect } = require('chai');
const axios = require('axios');

const plugin = require('../../services/search/plugins/google_fallback');
const { plugins } = require('../../services/search/plugins/loader');

// --- Helpers de mock manual (sem sinon) ---
function stubAxios(getImpl, headImpl) {
  const origGet = axios.get;
  const origHead = axios.head;
  axios.get = getImpl;
  axios.head = headImpl || origHead;
  return function restore() {
    axios.get = origGet;
    axios.head = origHead;
  };
}

function makeGetStub(responses) {
  let call = 0;
  return function fakeGet(url, _opts) {
    const idx = call;
    call++;
    if (typeof responses === 'function') return responses(url, idx);
    if (idx < responses.length) {
      const r = responses[idx];
      if (r instanceof Error) return Promise.reject(r);
      return Promise.resolve(r);
    }
    return Promise.reject(new Error('Unexpected GET call #' + idx + ' to ' + url));
  };
}

function makeHeadStub(headers) {
  return function fakeHead() {
    return Promise.resolve({ headers });
  };
}

function axiosError(status, message) {
  const err = new Error(message || 'HTTP ' + status);
  err.response = { status };
  return err;
}

describe('Plugin: google-fallback', () => {
  describe('Configuracao', () => {
    it('deve estar carregado no loader', () => {
      expect(plugins['google_fallback']).to.exist;
    });

    it('deve ter nome google-fallback', () => {
      expect(plugin.name).to.equal('google-fallback');
    });

    it('deve ter matchType serial', () => {
      expect(plugin.matchType).to.equal('serial');
    });

    it('deve ter prioridade 99 (ultima prioridade)', () => {
      expect(plugin.priority).to.equal(99);
    });

    it('deve estar enabled', () => {
      expect(plugin.enabled).to.be.true;
    });

    it('deve ter funcao search', () => {
      expect(plugin.search).to.be.a('function');
    });
  });

  describe('buildGoogleQueries', () => {
    it('deve gerar query com filetype e variacoes de serial', () => {
      const queries = plugin._internal.buildGoogleQueries('SLPS-01348');
      expect(queries).to.have.length(2);
      expect(queries[0]).to.include('"SLPS-01348"');
      expect(queries[0]).to.include('"SLPS01348"');
      expect(queries[0]).to.include('filetype:zip');
      expect(queries[0]).to.include('filetype:7z');
      expect(queries[0]).to.include('filetype:iso');
      expect(queries[0]).to.include('filetype:bin');
    });

    it('deve gerar query alternativa de download', () => {
      const queries = plugin._internal.buildGoogleQueries('SCUS-94150');
      expect(queries[1]).to.include('"SCUS-94150"');
      expect(queries[1]).to.include('download ROM PSX');
    });

    it('deve retornar array vazio para serial vazio', () => {
      expect(plugin._internal.buildGoogleQueries('')).to.have.length(0);
      expect(plugin._internal.buildGoogleQueries(null)).to.have.length(0);
    });
  });

  describe('extractGoogleResults', () => {
    it('deve extrair URLs de resultados /url?q=', () => {
      const html = '<div>' +
        '<a href="/url?q=https://example.com/game1.html&sa=U">Game 1</a>' +
        '<a href="/url?q=https://romsite.org/download.html&sa=U">ROM Download</a>' +
        '<a href="/url?q=https://www.google.com/foo&sa=U">Google</a>' +
        '</div>';
      const urls = plugin._internal.extractGoogleResults(html);
      expect(urls).to.include('https://example.com/game1.html');
      expect(urls).to.include('https://romsite.org/download.html');
      expect(urls.find(u => u.includes('google.com'))).to.be.undefined;
    });

    it('deve limitar a 10 resultados', () => {
      let html = '';
      for (let i = 0; i < 15; i++) {
        html += '<a href="/url?q=https://site' + i + '.com/page' + i + '.html&sa=U">Site ' + i + '</a>';
      }
      const urls = plugin._internal.extractGoogleResults(html);
      expect(urls).to.have.length(10);
    });

    it('deve retornar array para HTML sem resultados', () => {
      const urls = plugin._internal.extractGoogleResults('<html><body>nothing</body></html>');
      expect(urls).to.be.an('array');
    });
  });

  describe('extractDuckResults', () => {
    it('deve extrair URLs de resultados do DuckDuckGo', () => {
      const html = '<div>' +
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fromsite.org%2Fgame.html&rut=1">Game</a>' +
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fdl.html&rut=2">DL</a>' +
        '</div>';
      const urls = plugin._internal.extractDuckResults(html);
      expect(urls).to.include('https://romsite.org/game.html');
      expect(urls).to.include('https://example.com/dl.html');
    });
  });

  describe('findDirectLinks', () => {
    it('deve encontrar links diretos .7z/.zip/.iso/.bin/.chd', () => {
      const html = '<a href="/files/game.7z">7z</a>' +
        '<a href="https://cdn.site.org/game.zip">ZIP</a>' +
        '<a href="/roms/game.iso">ISO</a>' +
        '<a href="/data/game.bin">BIN</a>' +
        '<a href="/chd/game.chd">CHD</a>' +
        '<a href="/page/about.html">About</a>';
      const links = plugin._internal.findDirectLinks(html, 'https://site.com/page/index.html');
      expect(links).to.include('https://site.com/files/game.7z');
      expect(links).to.include('https://cdn.site.org/game.zip');
      expect(links).to.include('https://site.com/roms/game.iso');
      expect(links).to.include('https://site.com/data/game.bin');
      expect(links).to.include('https://site.com/chd/game.chd');
      expect(links.find(l => l.includes('about.html'))).to.be.undefined;
    });

    it('deve encontrar URLs literais no texto do HTML', () => {
      const html = '<p>Download at https://cdn.example.org/roms/game.7z now</p>';
      const links = plugin._internal.findDirectLinks(html, 'https://site.com/');
      expect(links).to.include('https://cdn.example.org/roms/game.7z');
    });

    it('deve resolver URLs relativas com path', () => {
      const html = '<a href="game.zip">DL</a>';
      const links = plugin._internal.findDirectLinks(html, 'https://site.com/dir/page.html');
      expect(links).to.include('https://site.com/dir/game.zip');
    });
  });

  describe('findInternalLinks', () => {
    it('deve extrair apenas links internos do mesmo dominio', () => {
      const html = '<a href="/page2.html">Page 2</a>' +
        '<a href="/downloads/index.html">Downloads</a>' +
        '<a href="https://other.com/page">External</a>' +
        '<a href="/files/game.7z">Direct ROM</a>';
      const links = plugin._internal.findInternalLinks(html, 'https://site.com/page1.html');
      expect(links).to.include('https://site.com/page2.html');
      expect(links).to.include('https://site.com/downloads/index.html');
      expect(links.find(l => l.includes('other.com'))).to.be.undefined;
      expect(links.find(l => l.includes('.7z'))).to.be.undefined;
    });
  });

  describe('validateDirectUrl', () => {
    let restore;

    afterEach(() => {
      if (restore) restore();
      restore = null;
    });

    it('deve validar URL com content-type e content-length corretos', async () => {
      restore = stubAxios(null, makeHeadStub({
        'content-type': 'application/zip',
        'content-length': '5242880',
      }));
      const valid = await plugin._internal.validateDirectUrl('https://site.com/game.zip');
      expect(valid).to.be.true;
    });

    it('deve rejeitar URL com content-length < 1MB', async () => {
      restore = stubAxios(null, makeHeadStub({
        'content-type': 'application/zip',
        'content-length': '500000',
      }));
      const valid = await plugin._internal.validateDirectUrl('https://site.com/small.zip');
      expect(valid).to.be.false;
    });

    it('deve rejeitar URL com content-type invalido', async () => {
      restore = stubAxios(null, makeHeadStub({
        'content-type': 'text/html',
        'content-length': '5242880',
      }));
      const valid = await plugin._internal.validateDirectUrl('https://site.com/page.html');
      expect(valid).to.be.false;
    });

    it('deve aceitar application/octet-stream', async () => {
      restore = stubAxios(null, makeHeadStub({
        'content-type': 'application/octet-stream',
        'content-length': '10485760',
      }));
      const valid = await plugin._internal.validateDirectUrl('https://site.com/game.7z');
      expect(valid).to.be.true;
    });

    it('deve aceitar content-length ausente se content-type bate', async () => {
      restore = stubAxios(null, makeHeadStub({
        'content-type': 'application/x-7z-compressed',
      }));
      const valid = await plugin._internal.validateDirectUrl('https://site.com/game.7z');
      expect(valid).to.be.true;
    });

    it('deve retornar false em erro de rede', async () => {
      restore = stubAxios(null, function () { return Promise.reject(new Error('ECONNREFUSED')); });
      const valid = await plugin._internal.validateDirectUrl('https://site.com/game.zip');
      expect(valid).to.be.false;
    });
  });

  describe('crawlForDirectLinks - descida de niveis', () => {
    let restore;

    afterEach(() => {
      if (restore) restore();
      restore = null;
    });

    it('deve encontrar link direto no nivel 1 (pagina atual)', async () => {
      restore = stubAxios(
        async () => ({ data: '<a href="/files/game.7z">Download</a>' }),
        makeHeadStub({ 'content-type': 'application/x-7z-compressed', 'content-length': '5242880' })
      );
      const visited = new Set();
      const results = [];
      await plugin._internal.crawlForDirectLinks('https://site.com/page.html', 1, visited, results);
      expect(results).to.have.length(1);
      expect(results[0].url).to.equal('https://site.com/files/game.7z');
      expect(results[0].depth).to.equal(1);
    });

    it('deve descer para nivel 2 se nao encontrar direto no nivel 1', async () => {
      const responses = [
        { data: '<a href="/downloads/index.html">Downloads</a>' },
        { data: '<a href="/downloads/game.zip">Download ZIP</a>' },
      ];
      restore = stubAxios(
        makeGetStub(responses),
        makeHeadStub({ 'content-type': 'application/zip', 'content-length': '10485760' })
      );
      const visited = new Set();
      const results = [];
      await plugin._internal.crawlForDirectLinks('https://site.com/page.html', 1, visited, results);
      expect(results).to.have.length(1);
      expect(results[0].url).to.equal('https://site.com/downloads/game.zip');
      expect(results[0].depth).to.equal(2);
    });

    it('deve respeitar MAX_DEPTH (3 niveis) e parar sem resultados', async () => {
      restore = stubAxios(
        async () => ({ data: '<a href="/next/page.html">Next</a>' }),
        makeHeadStub({})
      );
      const visited = new Set();
      const results = [];
      await plugin._internal.crawlForDirectLinks('https://site.com/start.html', 1, visited, results);
      expect(results).to.have.length(0);
      expect(visited.size).to.be.at.most(20);
    });

    it('deve respeitar MAX_PAGES (20 paginas visitadas)', async () => {
      restore = stubAxios(
        async () => ({ data: '<a href="/loop/page.html">Loop</a><a href="/loop2/page.html">Loop2</a>' }),
        makeHeadStub({})
      );
      const visited = new Set();
      const results = [];
      await plugin._internal.crawlForDirectLinks('https://site.com/start.html', 1, visited, results);
      expect(visited.size).to.be.at.most(20);
    });

    it('nao deve visitar a mesma URL duas vezes', async () => {
      restore = stubAxios(
        async () => ({ data: '<a href="/same/page.html">Same</a>' }),
        makeHeadStub({})
      );
      const visited = new Set();
      const results = [];
      await plugin._internal.crawlForDirectLinks('https://site.com/same/page.html', 1, visited, results);
      expect(visited.size).to.equal(1);
    });
  });

  describe('search - integracao com mocks', () => {
    let restore;

    afterEach(() => {
      if (restore) restore();
      restore = null;
    });

    it('deve retornar URLs validas encontradas via Google', async () => {
      const responses = [
        { data: '<a href="/url?q=https://romsite.org/game.html&sa=U">Game</a>' },
        { data: '<a href="/files/game.7z">Download 7z</a>' },
      ];
      restore = stubAxios(
        makeGetStub(responses),
        makeHeadStub({ 'content-type': 'application/x-7z-compressed', 'content-length': '5242880' })
      );
      const results = await plugin.search('SLPS-01348', 'Game Title');
      expect(results).to.be.an('array');
      expect(results).to.have.length(1);
      expect(results[0].url).to.equal('https://romsite.org/files/game.7z');
      expect(results[0].site).to.equal('google-fallback');
    });

    it('deve retornar array vazio para serial vazio', async () => {
      const results = await plugin.search('', 'Title');
      expect(results).to.be.an('array');
      expect(results).to.have.length(0);
    });

    it('deve retornar array vazio se nenhuma URL encontrada', async () => {
      restore = stubAxios(
        async () => ({ data: '<html><body>no results</body></html>' }),
        makeHeadStub({})
      );
      const results = await plugin.search('SLPS-99999', 'Nonexistent');
      expect(results).to.be.an('array');
      expect(results).to.have.length(0);
    });

    it('deve fazer fallback para DuckDuckGo quando Google retorna 429', async () => {
      // Substitui setTimeout para pular o wait de 30s
      const origSetTimeout = setTimeout;
      global.setTimeout = function (fn, _ms) { return origSetTimeout(fn, 0); };
      try {
        const responses = [
          axiosError(429, 'Too Many Requests'),
          { data: '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fromsite.org%2Fgame.html&rut=1">Game</a>' },
          { data: '<a href="/files/game.zip">Download</a>' },
        ];
        restore = stubAxios(
          makeGetStub(responses),
          makeHeadStub({ 'content-type': 'application/zip', 'content-length': '5242880' })
        );
        const results = await plugin.search('SLPS-01348', 'Game');
        expect(results).to.be.an('array');
        expect(results).to.have.length(1);
        expect(results[0].url).to.equal('https://romsite.org/files/game.zip');
      } finally {
        global.setTimeout = origSetTimeout;
      }
    });

    it('deve fazer fallback para DuckDuckGo quando Google retorna 503', async () => {
      const origSetTimeout = setTimeout;
      global.setTimeout = function (fn, _ms) { return origSetTimeout(fn, 0); };
      try {
        const responses = [
          axiosError(503, 'Service Unavailable'),
          { data: '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Fdl.html&rut=1">DL</a>' },
          { data: '<a href="https://example.org/roms/game.iso">ISO</a>' },
        ];
        restore = stubAxios(
          makeGetStub(responses),
          makeHeadStub({ 'content-type': 'application/octet-stream', 'content-length': '10485760' })
        );
        const results = await plugin.search('SCUS-94150', 'Game');
        expect(results).to.have.length(1);
        expect(results[0].url).to.equal('https://example.org/roms/game.iso');
      } finally {
        global.setTimeout = origSetTimeout;
      }
    });
  });
});
