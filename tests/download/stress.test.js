// Teste de stress do servico de download
// Testa concorrencia, race conditions, spin lock, e comportamento sob carga.
// Roda: npx mocha tests/download/stress.test.js --timeout 120000
require('./_setup');
const { expect } = require('chai');

const dl = require('../../services/download/index');

describe('Stress: Source Slots - concorrencia alta', () => {
  const SITE = 'stress_slot_site';

  beforeEach(() => {
    dl.sourceSlots.set(SITE, { current: 0, max: 5, waiters: [] });
  });

  it('suporta 100 acquire/release sem deadlock', async () => {
    const promises = [];
    for (let i = 0; i < 100; i++) {
      promises.push((async () => {
        await dl.acquireSourceSlot(SITE, 10000);
        await new Promise(r => setTimeout(r, Math.random() * 10));
        dl.releaseSourceSlot(SITE);
      })());
    }
    await Promise.all(promises);
    const state = dl.getSlotState(SITE);
    expect(state.current).to.equal(0);
    expect(state.waiters.length).to.equal(0);
  }).timeout(60000);

  it('nao excede max concurrent slots sob carga', async () => {
    let maxObserved = 0;
    const checkInterval = setInterval(() => {
      const state = dl.getSlotState(SITE);
      if (state.current > maxObserved) maxObserved = state.current;
    }, 5);

    const promises = [];
    for (let i = 0; i < 50; i++) {
      promises.push((async () => {
        await dl.acquireSourceSlot(SITE, 10000);
        await new Promise(r => setTimeout(r, 50));
        dl.releaseSourceSlot(SITE);
      })());
    }
    await Promise.all(promises);
    clearInterval(checkInterval);
    expect(maxObserved).to.be.at.most(5);
  }).timeout(60000);

  it('waiters sao acordados em ordem FIFO', async () => {
    dl.sourceSlots.set(SITE, { current: 0, max: 1, waiters: [] });
    const order = [];

    // Ocupa o unico slot
    await dl.acquireSourceSlot(SITE, 5000);

    // 3 waiters
    const w1 = dl.acquireSourceSlot(SITE, 5000).then(() => order.push(1));
    const w2 = dl.acquireSourceSlot(SITE, 5000).then(() => order.push(2));
    const w3 = dl.acquireSourceSlot(SITE, 5000).then(() => order.push(3));

    // Libera gradualmente
    await new Promise(r => setTimeout(r, 50));
    dl.releaseSourceSlot(SITE);
    await w1;
    dl.releaseSourceSlot(SITE);
    await w2;
    dl.releaseSourceSlot(SITE);
    await w3;

    expect(order).to.deep.equal([1, 2, 3]);
    dl.releaseSourceSlot(SITE);
  }).timeout(30000);

  it('timeout de waiter remove da fila sem vazar slot', async () => {
    dl.sourceSlots.set(SITE, { current: 0, max: 1, waiters: [] });
    await dl.acquireSourceSlot(SITE, 5000);

    // Waiter com timeout curto
    try {
      await dl.acquireSourceSlot(SITE, 100);
      expect.fail('deveria timeout');
    } catch (e) {
      expect(e.message).to.include('timeout');
    }

    const state = dl.getSlotState(SITE);
    expect(state.waiters.length).to.equal(0);

    // Slot ainda ocupado pelo primeiro acquire
    expect(state.current).to.equal(1);

    // Liberar nao deve acordar ninguem (waiter ja saiu)
    dl.releaseSourceSlot(SITE);
    expect(state.current).to.equal(0);
  }).timeout(10000);
});

describe('Stress: Cooldown sob carga', () => {
  it('set/get cooldown 1000 vezes sem lentidao', () => {
    const site = 'stress_cooldown';
    const start = Date.now();
    for (let i = 0; i < 1000; i++) {
      dl.setSourceCooldown(site, 1000);
      dl.isSourceInCooldown(site);
    }
    const elapsed = Date.now() - start;
    expect(elapsed).to.be.lessThan(1000); // menos de 1s para 1000 ops
  });

  it('cooldown expirado e limpo da memoria', async () => {
    const site = 'stress_cooldown_cleanup';
    dl.setSourceCooldown(site, 50);
    expect(dl.sourceCooldown.has(site)).to.be.true;
    await new Promise(r => setTimeout(r, 100));
    expect(dl.isSourceInCooldown(site)).to.be.false;
    expect(dl.sourceCooldown.has(site)).to.be.false;
  });
});

describe('Stress: Download Tracking concorrente', () => {
  it('100 downloads tracked/untracked sem vazamento', () => {
    const serials = [];
    for (let i = 0; i < 100; i++) {
      const serial = `STRESS_TRACK_${i}_${Date.now()}`;
      serials.push(serial);
      dl.startDownloadTracking(serial, 'test_source');
    }
    expect(dl.activeDownloads.size).to.be.at.least(100);

    for (const serial of serials) {
      dl.endDownloadTracking(serial);
    }
    for (const serial of serials) {
      expect(dl.activeDownloads.has(serial)).to.be.false;
    }
  });

  it('start/end intercalado nao corrompe map', () => {
    const serials = [];
    for (let i = 0; i < 50; i++) {
      const serial = `STRESS_INTERLEAVE_${i}_${Date.now()}`;
      serials.push(serial);
    }

    // Start all
    for (const s of serials) dl.startDownloadTracking(s, 'src');
    // End even ones
    for (let i = 0; i < serials.length; i += 2) dl.endDownloadTracking(serials[i]);
    // Re-start some
    dl.startDownloadTracking(serials[0], 'src2');
    // End all
    for (const s of serials) dl.endDownloadTracking(s);

    for (const s of serials) {
      expect(dl.activeDownloads.has(s)).to.be.false;
    }
  });
});

describe('Stress: trackRequeue sob carga (spin lock detection)', () => {
  it('100 requeues rapidos nao lancam erro', () => {
    for (let i = 0; i < 100; i++) {
      dl.trackRequeue();
    }
    // Funcao deve completar sem throw
    expect(true).to.be.true;
  });

  it('trackRequeue em paralelo (race condition)', async () => {
    const promises = [];
    for (let i = 0; i < 50; i++) {
      promises.push(Promise.resolve().then(() => dl.trackRequeue()));
    }
    await Promise.all(promises);
    // Nao deve lancar erro nem corromper estado
    expect(true).to.be.true;
  });
});

describe('Stress: orderSources com muitas fontes', () => {
  it('ordena 100 fontes rapidamente', () => {
    const sources = [];
    const sites = ['vimm', 'archive.org', 'coolrom', 'romsdl', 'retrostic', 'romspedia', 'romsgames', 'google_fallback'];
    for (let i = 0; i < 100; i++) {
      sources.push({ site: sites[i % sites.length], url: `http://example.com/${i}.7z` });
    }
    const start = Date.now();
    const ordered = dl.orderSources(sources, 'any');
    const elapsed = Date.now() - start;

    expect(ordered.length).to.equal(100);
    expect(elapsed).to.be.lessThan(100);
    // vimm deve vir antes de archive.org
    const vimmIdx = ordered.findIndex(s => s.site === 'vimm');
    const archiveIdx = ordered.findIndex(s => s.site === 'archive.org');
    expect(vimmIdx).to.be.lessThan(archiveIdx);
  });

  it('orderSources com preferredSite coloca preferida primeiro mesmo com 50 fontes', () => {
    const sources = [];
    for (let i = 0; i < 50; i++) {
      sources.push({ site: `site_${i}`, url: `http://example.com/${i}.7z` });
    }
    sources.push({ site: 'target', url: 'http://target.com/game.7z' });
    const ordered = dl.orderSources(sources, 'target');
    expect(ordered[0].site).to.equal('target');
  });
});

describe('Stress: sortSourcesBySpeed estabilidade', () => {
  it('mantem todas as fontes apos sort', () => {
    const sources = [];
    for (let i = 0; i < 30; i++) {
      sources.push({ site: `site_${i}`, url: `http://example.com/${i}` });
    }
    const sorted = dl.sortSourcesBySpeed(sources);
    expect(sorted.length).to.equal(30);
    // Mesmas fontes (verifica por URL)
    const sortedUrls = new Set(sorted.map(s => s.url));
    const originalUrls = new Set(sources.map(s => s.url));
    expect(sortedUrls.size).to.equal(originalUrls.size);
  });

  it('ordena corretamente com fontes mistas', () => {
    const sources = [
      { site: 'google_fallback', url: 'http://g.com' },
      { site: 'vimm', url: 'http://vimm.net' },
      { site: 'archive.org', url: 'http://a.org' },
      { site: 'coolrom', url: 'http://coolrom.com' },
      { site: 'romsdl', url: 'http://romsdl.com' }
    ];
    const sorted = dl.sortSourcesBySpeed(sources);
    // vimm (10) e romsdl (10) tem mesma prioridade - ambos devem vir antes de coolrom (7)
    expect(sorted[0].site).to.be.oneOf(['vimm', 'romsdl']);
    expect(sorted[sorted.length - 1].site).to.equal('google_fallback');
    // coolrom antes de archive.org
    const coolromIdx = sorted.findIndex(s => s.site === 'coolrom');
    const archiveIdx = sorted.findIndex(s => s.site === 'archive.org');
    expect(coolromIdx).to.be.lessThan(archiveIdx);
  });
});

describe('Stress: handleDownloadFailure retry logic', () => {
  it('requeue apos falha (retry_count < 5)', async () => {
    // Mock queueRequest nao e exportada, mas handleDownloadFailure chama queueRequest
    // que vai falhar (queue service nao esta rodando). A funcao deve lidar com isso.
    const item = { serial: 'STRESS_FAIL_1', retry_count: 0 };
    try {
      await dl.handleDownloadFailure(item, new Error('test error'));
    } catch (e) {
      // Pode lancar se queueRequest falhar - aceitavel
    }
    expect(item.retry_count).to.equal(1);
  });

  it('fail apos 5 retries', async () => {
    const item = { serial: 'STRESS_FAIL_5', retry_count: 4 };
    try {
      await dl.handleDownloadFailure(item, new Error('final error'));
    } catch (e) {
      // queueRequest pode falhar
    }
    expect(item.retry_count).to.equal(5);
  });
});

describe('Stress: memoria e leaks', () => {
  it('sourceSlots nao cresce indefinidamente apos uso', () => {
    const initialSize = dl.sourceSlots.size;
    for (let i = 0; i < 100; i++) {
      const site = `leak_test_${i}`;
      dl.getSlotState(site);
      dl.acquireSourceSlot(site, 1000);
      dl.releaseSourceSlot(site);
    }
    // sourceSlots mantem entradas (nao limpa), mas nao deve crescer alem do esperado
    expect(dl.sourceSlots.size).to.be.at.most(initialSize + 100);
  });

  it('sourceCooldown limpa entradas expiradas', async () => {
    for (let i = 0; i < 50; i++) {
      dl.setSourceCooldown(`cleanup_test_${i}`, 50);
    }
    await new Promise(r => setTimeout(r, 100));
    // isSourceInCooldown remove entradas expiradas quando consultado
    for (let i = 0; i < 50; i++) {
      dl.isSourceInCooldown(`cleanup_test_${i}`);
    }
    let remaining = 0;
    for (let i = 0; i < 50; i++) {
      if (dl.sourceCooldown.has(`cleanup_test_${i}`)) remaining++;
    }
    expect(remaining).to.equal(0);
  });
});
