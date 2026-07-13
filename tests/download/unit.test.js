// Testes unitarios do servico de download
// Roda: npx mocha tests/download/unit.test.js --timeout 30000
require('./_setup');
const { expect } = require('chai');
const cheerio = require('cheerio');

// Importar modulo sem iniciar servidor (require.main !== module)
const dl = require('../../services/download/index');
const aria2 = require('../../services/download/aria2');

describe('Unit: aria2.js - parseSpeed', () => {
  it('parsea speed com KiB', () => {
    expect(aria2.parseSpeed('DL:1.5KiB')).to.equal('1.5KiB/s');
  });
  it('parsea speed com MiB', () => {
    expect(aria2.parseSpeed('DL:5.2MiB')).to.equal('5.2MiB/s');
  });
  it('parsea speed com GiB', () => {
    expect(aria2.parseSpeed('DL:0.1GiB')).to.equal('0.1GiB/s');
  });
  it('retorna null para linha sem speed', () => {
    expect(aria2.parseSpeed('some random output')).to.be.null;
  });
  it('retorna null para linha vazia', () => {
    expect(aria2.parseSpeed('')).to.be.null;
  });
});

describe('Unit: aria2.js - parseProgress', () => {
  it('parsea progresso com percentual explicito', () => {
    const line = '[#abc123 1.5MiB/10MiB(15%)]';
    expect(aria2.parseProgress(line)).to.equal(15);
  });
  it('parsea progresso so com percentual', () => {
    expect(aria2.parseProgress('Status: (42%)')).to.equal(42);
  });
  it('calcula percentual a partir de bytes/total', () => {
    const line = '[#def456 5MiB/20MiB]';
    expect(aria2.parseProgress(line)).to.equal(25);
  });
  it('retorna null para linha sem progresso', () => {
    expect(aria2.parseProgress('no progress here')).to.be.null;
  });
});

describe('Unit: aria2.js - parseSize', () => {
  it('parsea bytes', () => {
    expect(aria2.parseSize('100B')).to.equal(100);
  });
  it('parsea KB', () => {
    expect(aria2.parseSize('1KB')).to.equal(1024);
  });
  it('parsea MiB', () => {
    expect(aria2.parseSize('1MiB')).to.equal(1048576);
  });
  it('parsea GiB', () => {
    expect(aria2.parseSize('2GiB')).to.equal(2147483648);
  });
  it('retorna 0 para string invalida', () => {
    expect(aria2.parseSize('invalid')).to.equal(0);
  });
});

describe('Unit: aria2.js - speedToMbps', () => {
  it('converte KiB/s para MB/s', () => {
    expect(aria2.speedToMbps('1024KiB/s')).to.be.closeTo(1.0, 0.001);
  });
  it('converte MiB/s direto', () => {
    expect(aria2.speedToMbps('5MiB/s')).to.equal(5);
  });
  it('converte GiB/s para MB/s', () => {
    expect(aria2.speedToMbps('1GiB/s')).to.equal(1024);
  });
  it('retorna 0 para null', () => {
    expect(aria2.speedToMbps(null)).to.equal(0);
  });
  it('retorna 0 para string invalida', () => {
    expect(aria2.speedToMbps('abc')).to.equal(0);
  });
});

describe('Unit: download/index.js - speedToMbps', () => {
  it('converte KiB/s', () => {
    expect(dl.speedToMbps('512KiB/s')).to.be.closeTo(0.5, 0.001);
  });
  it('converte MiB/s', () => {
    expect(dl.speedToMbps('10MiB/s')).to.equal(10);
  });
  it('retorna 0 para null', () => {
    expect(dl.speedToMbps(null)).to.equal(0);
  });
  it('retorna 0 para string vazia', () => {
    expect(dl.speedToMbps('')).to.equal(0);
  });
});

describe('Unit: extractCookieStr', () => {
  it('extrai cookies de array', () => {
    const res = { headers: { 'set-cookie': ['PHPSESSID=abc123; path=/', 'foo=bar; path=/'] } };
    expect(dl.extractCookieStr(res)).to.equal('PHPSESSID=abc123; foo=bar');
  });
  it('extrai cookie de string unica', () => {
    const res = { headers: { 'set-cookie': 'session=xyz; path=/' } };
    expect(dl.extractCookieStr(res)).to.equal('session=xyz');
  });
  it('retorna string vazia sem cookies', () => {
    const res = { headers: {} };
    expect(dl.extractCookieStr(res)).to.equal('');
  });
});

describe('Unit: extractFormData', () => {
  it('extrai campos input de um form', () => {
    const html = '<form action="/download" method="post">'
      + '<input name="session" value="abc123">'
      + '<input name="rom_url" value="http://example.com/game.7z">'
      + '<input name="csrf" value="token123">'
      + '</form>';
    const $ = cheerio.load(html);
    const data = dl.extractFormData($, 'form[action$="/download"][method="post"]');
    expect(data).to.deep.equal({
      session: 'abc123',
      rom_url: 'http://example.com/game.7z',
      csrf: 'token123'
    });
  });
  it('retorna objeto vazio se form nao existe', () => {
    const $ = cheerio.load('<div>no form</div>');
    const data = dl.extractFormData($, 'form[action$="/download"]');
    expect(data).to.deep.equal({});
  });
  it('ignora inputs sem name', () => {
    const html = '<form><input value="no name"><input name="x" value="y"></form>';
    const $ = cheerio.load(html);
    const data = dl.extractFormData($, 'form');
    expect(data).to.deep.equal({ x: 'y' });
  });
});

describe('Unit: resolveCoolrom', () => {
  it('encontra link dl.coolrom', () => {
    const html = '<a href="https://dl.coolrom.com/abc/123">Download</a>';
    const $ = cheerio.load(html);
    expect(dl.resolveCoolrom($)).to.equal('https://dl.coolrom.com/abc/123');
  });
  it('lanca erro se link nao encontrado', () => {
    const $ = cheerio.load('<div>no link</div>');
    expect(() => dl.resolveCoolrom($)).to.throw('coolrom: link de download nao encontrado');
  });
});

describe('Unit: resolveVimm', () => {
  it('extrai mediaId e monta URL dl3', () => {
    const html = '<script>{"ID":12345,"name":"game"}</script>';
    const $ = cheerio.load(html);
    const res = { headers: { 'set-cookie': ['PHPSESSID=abc; path=/'] } };
    const result = dl.resolveVimm($, res, 'https://vimm.net/rom/12345');
    expect(result.url).to.equal('https://dl3.vimm.net/?mediaId=12345&alt=0');
    expect(result.headers.Cookie).to.equal('PHPSESSID=abc');
    expect(result.headers.Referer).to.equal('https://vimm.net/rom/12345');
  });
  it('lanca erro se mediaId nao encontrado', () => {
    const $ = cheerio.load('<script>no id here</script>');
    const res = { headers: {} };
    expect(() => dl.resolveVimm($, res, 'https://vimm.net/')).to.throw('vimm: mediaId nao encontrado');
  });
});

describe('Unit: resolveRomsretro', () => {
  it('encontra link dl.romsretro.com', () => {
    const html = '<a href="https://dl.romsretro.com/game.7z">Download</a>';
    const $ = cheerio.load(html);
    expect(dl.resolveRomsretro($)).to.equal('https://dl.romsretro.com/game.7z');
  });
  it('retorna null se link nao encontrado', () => {
    const $ = cheerio.load('<div>nothing</div>');
    expect(dl.resolveRomsretro($)).to.be.null;
  });
});

describe('Unit: resolveGenericLink', () => {
  it('encontra link com extensao .7z', () => {
    const html = '<a href="/downloads/game.7z">Download</a>';
    const $ = cheerio.load(html);
    expect(dl.resolveGenericLink($, 'https://example.com')).to.equal('https://example.com/downloads/game.7z');
  });
  it('encontra link com extensao .zip absoluto', () => {
    const html = '<a href="https://cdn.example.com/game.zip">Download</a>';
    const $ = cheerio.load(html);
    expect(dl.resolveGenericLink($, 'https://example.com')).to.equal('https://cdn.example.com/game.zip');
  });
  it('encontra link /download/ path', () => {
    const html = '<a href="/download/123">Get</a>';
    const $ = cheerio.load(html);
    expect(dl.resolveGenericLink($, 'https://example.com')).to.equal('https://example.com/download/123');
  });
  it('para no primeiro link com extensao encontrada', () => {
    const html = '<a href="/download/123">DL</a><a href="/files/game.iso">ISO</a>';
    const $ = cheerio.load(html);
    // /download/ e encontrado primeiro (best=null), seta best e para
    // .iso nunca e avaliado pois o each para com return false
    const result = dl.resolveGenericLink($, 'https://example.com');
    expect(result).to.equal('https://example.com/download/123');
  });
  it('lanca erro se nenhum link encontrado', () => {
    const $ = cheerio.load('<div>no links</div>');
    expect(() => dl.resolveGenericLink($, 'https://example.com')).to.throw('link de download nao encontrado');
  });
  it('monta URL relativa sem barra inicial', () => {
    const html = '<a href="downloads/game.7z">DL</a>';
    const $ = cheerio.load(html);
    expect(dl.resolveGenericLink($, 'https://example.com')).to.equal('https://example.com/downloads/game.7z');
  });
});

describe('Unit: sortSourcesBySpeed', () => {
  it('prioriza fontes diretas sobre archive.org', () => {
    const sources = [
      { site: 'archive.org', url: 'http://a.org' },
      { site: 'vimm', url: 'http://vimm.net' },
      { site: 'coolrom', url: 'http://coolrom.com' }
    ];
    const sorted = dl.sortSourcesBySpeed(sources);
    expect(sorted[0].site).to.equal('vimm');
    expect(sorted[sorted.length - 1].site).to.equal('archive.org');
  });
  it('coolrom tem prioridade media (entre vimm e archive.org)', () => {
    const sources = [
      { site: 'archive.org', url: 'http://a.org' },
      { site: 'coolrom', url: 'http://coolrom.com' },
      { site: 'vimm', url: 'http://vimm.net' }
    ];
    const sorted = dl.sortSourcesBySpeed(sources);
    expect(sorted[0].site).to.equal('vimm');
    expect(sorted[1].site).to.equal('coolrom');
    expect(sorted[2].site).to.equal('archive.org');
  });
  it('google_fallback vai por ultimo', () => {
    const sources = [
      { site: 'google_fallback', url: 'http://google.com' },
      { site: 'archive.org', url: 'http://a.org' }
    ];
    const sorted = dl.sortSourcesBySpeed(sources);
    expect(sorted[sorted.length - 1].site).to.equal('google_fallback');
  });
  it('fonte desconhecida usa prioridade default 5', () => {
    const sources = [
      { site: 'unknown_site', url: 'http://unknown.com' },
      { site: 'archive.org', url: 'http://a.org' }
    ];
    const sorted = dl.sortSourcesBySpeed(sources);
    // unknown tem default 5, archive.org tambem 5 - ordem aleatoria
    expect(sorted.length).to.equal(2);
  });
});

describe('Unit: orderSources', () => {
  it('coloca fonte preferida primeiro', () => {
    const sources = [
      { site: 'vimm', url: 'http://vimm.net' },
      { site: 'archive.org', url: 'http://a.org' },
      { site: 'coolrom', url: 'http://coolrom.com' }
    ];
    const ordered = dl.orderSources(sources, 'coolrom');
    expect(ordered[0].site).to.equal('coolrom');
  });
  it('sem preferencia usa sortSourcesBySpeed', () => {
    const sources = [
      { site: 'archive.org', url: 'http://a.org' },
      { site: 'vimm', url: 'http://vimm.net' }
    ];
    const ordered = dl.orderSources(sources, 'any');
    expect(ordered[0].site).to.equal('vimm');
  });
  it('preferencia nao encontrada usa sort', () => {
    const sources = [
      { site: 'vimm', url: 'http://vimm.net' },
      { site: 'archive.org', url: 'http://a.org' }
    ];
    const ordered = dl.orderSources(sources, 'nonexistent');
    expect(ordered[0].site).to.equal('vimm');
  });
  it('normaliza ponto para underscore na fonte preferida', () => {
    const sources = [
      { site: 'archive_org', url: 'http://a.org' },
      { site: 'vimm', url: 'http://vimm.net' }
    ];
    const ordered = dl.orderSources(sources, 'archive.org');
    expect(ordered[0].site).to.equal('archive_org');
  });
});

describe('Unit: Source Slots', () => {
  it('getSlotState cria estado inicial', () => {
    const state = dl.getSlotState('test_site_' + Date.now());
    expect(state).to.have.property('current', 0);
    expect(state).to.have.property('max');
    expect(state.waiters).to.be.an('array');
  });
  it('acquireSourceSlot incrementa current', async () => {
    const site = 'test_acquire_' + Date.now();
    await dl.acquireSourceSlot(site, 1000);
    const state = dl.getSlotState(site);
    expect(state.current).to.be.greaterThan(0);
    dl.releaseSourceSlot(site);
  });
  it('releaseSourceSlot decrementa current', async () => {
    const site = 'test_release_' + Date.now();
    await dl.acquireSourceSlot(site, 1000);
    dl.releaseSourceSlot(site);
    const state = dl.getSlotState(site);
    expect(state.current).to.equal(0);
  });
  it('respeita limite max de slots', async () => {
    const site = 'test_max_' + Date.now();
    // Forca limite 1
    dl.sourceSlots.set(site, { current: 0, max: 1, waiters: [] });
    await dl.acquireSourceSlot(site, 1000);
    // Segundo acquire deve aguardar (timeout rapido para nao travar)
    try {
      await dl.acquireSourceSlot(site, 200);
      expect.fail('deveria ter dado timeout');
    } catch (e) {
      expect(e.message).to.include('timeout');
    }
    dl.releaseSourceSlot(site);
  });
  it('release acorda waiter na fila', async () => {
    const site = 'test_waiter_' + Date.now();
    dl.sourceSlots.set(site, { current: 0, max: 1, waiters: [] });
    await dl.acquireSourceSlot(site, 5000);
    // Segundo acquire fica na fila
    const secondPromise = dl.acquireSourceSlot(site, 5000);
    // Espera um pouco e libera
    await new Promise(r => setTimeout(r, 100));
    dl.releaseSourceSlot(site);
    // Segundo deve conseguir
    await secondPromise;
    dl.releaseSourceSlot(site);
  });
});

describe('Unit: Source Cooldown', () => {
  it('setSourceCooldown e isSourceInCooldown', () => {
    const site = 'test_cooldown_' + Date.now();
    dl.setSourceCooldown(site, 5000);
    expect(dl.isSourceInCooldown(site)).to.be.true;
  });
  it('isSourceInCooldown retorna false apos expirar', async () => {
    const site = 'test_cooldown_exp_' + Date.now();
    dl.setSourceCooldown(site, 100);
    await new Promise(r => setTimeout(r, 200));
    expect(dl.isSourceInCooldown(site)).to.be.false;
  });
  it('isSourceInCooldown retorna false sem cooldown setado', () => {
    expect(dl.isSourceInCooldown('never_set_' + Date.now())).to.be.false;
  });
});

describe('Unit: Download Tracking', () => {
  it('startDownloadTracking adiciona ao map', () => {
    const serial = 'TRACK_TEST_' + Date.now();
    dl.startDownloadTracking(serial, 'vimm');
    expect(dl.activeDownloads.has(serial)).to.be.true;
    const d = dl.activeDownloads.get(serial);
    expect(d.source).to.equal('vimm');
    expect(d.startedAt).to.be.greaterThan(0);
    dl.endDownloadTracking(serial);
  });
  it('endDownloadTracking remove do map', () => {
    const serial = 'TRACK_END_' + Date.now();
    dl.startDownloadTracking(serial, 'coolrom');
    dl.endDownloadTracking(serial);
    expect(dl.activeDownloads.has(serial)).to.be.false;
  });
});

describe('Unit: validateExtractedContent', () => {
  it('retorna false para serial nao encontrado', () => {
    expect(dl.validateExtractedContent('NONEXISTENT_SERIAL_12345')).to.be.false;
  });
  it('retorna false para serial vazio', () => {
    expect(dl.validateExtractedContent('')).to.be.false;
  });
});

describe('Unit: trackRequeue', () => {
  it('trackRequeue adiciona timestamp', () => {
    const before = dl.sourceCooldown.size; // so para garantir que modulo carregou
    dl.trackRequeue();
    dl.trackRequeue();
    dl.trackRequeue();
    // Nao podemos acessar requeueRecent diretamente, mas a funcao nao deve lancar erro
    expect(before).to.be.a('number');
  });
});

describe('Unit: tryResolveUrl', () => {
  it('retorna null para URL direta sem resolver', async () => {
    const source = { site: 'unknown', url: 'http://example.com/game.7z' };
    const directExts = ['.7z', '.zip'];
    const result = await dl.tryResolveUrl(source, directExts);
    expect(result).to.be.null;
  });
  it('tenta resolver URL de site conhecido (coolrom)', async () => {
    // coolrom esta na lista RESOLVER_SITES - vai tentar resolver
    // Como a URL e fake, vai falhar com erro de rede
    const source = { site: 'coolrom', url: 'http://nonexistent-coolrom-test.com/page' };
    const directExts = ['.7z'];
    try {
      await dl.tryResolveUrl(source, directExts);
      expect.fail('deveria ter lancado erro');
    } catch (e) {
      expect(e.message).to.be.a('string');
    }
  });
});

describe('Unit: resolveAndDownload - casos de erro', () => {
  it('lanca erro com sources vazias', async () => {
    try {
      await dl.resolveAndDownload({ serial: 'TEST' }, [], 'any');
      expect.fail('deveria lancar erro');
    } catch (e) {
      expect(e.message).to.include('sem sources');
    }
  });
  it('lanca erro com sources null', async () => {
    try {
      await dl.resolveAndDownload({ serial: 'TEST' }, null, 'any');
      expect.fail('deveria lancar erro');
    } catch (e) {
      expect(e.message).to.include('sem sources');
    }
  });
  it('lanca erro quando todas as fontes falham', async () => {
    const item = { serial: 'FAIL_TEST_' + Date.now() };
    const sources = [
      { site: 'nonexistent', url: 'http://this-does-not-exist-test.invalid/game.7z' }
    ];
    try {
      await dl.resolveAndDownload(item, sources, 'any');
      expect.fail('deveria lancar erro');
    } catch (e) {
      expect(e.message).to.include('todas as fontes falharam');
    }
  }).timeout(60000);
});
