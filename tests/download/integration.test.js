// Testes de integracao do servico de download
// Cria servidor HTTP mock para simular fontes de download e queue service.
// Roda: npx mocha tests/download/integration.test.js --timeout 60000
require('./_setup');
const { expect } = require('chai');
const http = require('http');

const dl = require('../../services/download/index');

let mockQueueServer;
let mockFileServer;
const mockQueuePort = 19001;
const mockFilePort = 19002;

// Helper: cria servidor HTTP mock
function createMockServer(port, handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

// Helper: fecha servidor com timeout
function closeServer(server) {
  return new Promise((resolve) => {
    if (!server) return resolve();
    server.close(() => resolve());
  });
}

// Dados de teste
const TEST_SERIAL = 'SLUS-00123';
const TEST_FILE_CONTENT = Buffer.from('This is a test ROM file content for integration testing');

describe('Integration: Download Service com mock HTTP', () => {
  before(async () => {
    // Mock queue service
    mockQueueServer = await createMockServer(mockQueuePort, (req, res) => {
      let body = '';
      req.on('data', c => { body += c; });
      req.on('end', () => {
        res.setHeader('Content-Type', 'application/json');
        if (req.url === '/queue/next-ready') {
          const data = JSON.parse(body || '{}');
          if (data.preferredSite === 'none') {
            res.end(JSON.stringify({}));
          } else {
            res.end(JSON.stringify({
              item: {
                serial: TEST_SERIAL,
                title: 'Test Game',
                sources: [
                  { site: 'mock_source', url: `http://127.0.0.1:${mockFilePort}/game.7z` }
                ]
              }
            }));
          }
        } else if (req.url === '/queue/complete') {
          res.end(JSON.stringify({ ok: true }));
        } else if (req.url === '/queue/fail') {
          res.end(JSON.stringify({ ok: true }));
        } else if (req.url === '/queue/requeue') {
          res.end(JSON.stringify({ ok: true }));
        } else if (req.url === '/queue/update') {
          res.end(JSON.stringify({ ok: true }));
        } else if (req.url === '/queue/cooldown-all') {
          res.end(JSON.stringify({ ok: true }));
        } else if (req.url === '/status') {
          res.end(JSON.stringify({ pending: 0, ready: 1, downloading: 0, completed: 0 }));
        } else {
          res.statusCode = 404;
          res.end(JSON.stringify({ error: 'not found' }));
        }
      });
    });

    // Mock file server (simula fonte de download)
    mockFileServer = await createMockServer(mockFilePort, (req, res) => {
      if (req.url === '/game.7z') {
        res.setHeader('Content-Type', 'application/octet-stream');
        res.setHeader('Content-Length', TEST_FILE_CONTENT.length);
        res.end(TEST_FILE_CONTENT);
      } else if (req.url === '/slow.7z') {
        // Simula download lento (envia 1 byte a cada 500ms)
        res.setHeader('Content-Type', 'application/octet-stream');
        const interval = setInterval(() => {
          res.write(Buffer.from('x'));
        }, 500);
        setTimeout(() => {
          clearInterval(interval);
          res.end();
        }, 5000);
      } else if (req.url === '/404') {
        res.statusCode = 404;
        res.end('Not Found');
      } else if (req.url === '/429') {
        res.statusCode = 429;
        res.end('Too Many Requests');
      } else if (req.url === '/redirect.7z') {
        res.statusCode = 302;
        res.setHeader('Location', `/game.7z`);
        res.end();
      } else {
        res.statusCode = 404;
        res.end('Not Found');
      }
    });
  });

  after(async () => {
    await closeServer(mockQueueServer);
    await closeServer(mockFileServer);
  });

  describe('Mock file server', () => {
    it('serve arquivo de teste', (done) => {
      http.get(`http://127.0.0.1:${mockFilePort}/game.7z`, (res) => {
        expect(res.statusCode).to.equal(200);
        const chunks = [];
        res.on('data', c => chunks.push(c));
        res.on('end', () => {
          const buf = Buffer.concat(chunks);
          expect(buf.equals(TEST_FILE_CONTENT)).to.be.true;
          done();
        });
      });
    });

    it('retorna 404 para arquivo inexistente', (done) => {
      http.get(`http://127.0.0.1:${mockFilePort}/404`, (res) => {
        expect(res.statusCode).to.equal(404);
        done();
      });
    });

    it('retorna 429 para rate limit', (done) => {
      http.get(`http://127.0.0.1:${mockFilePort}/429`, (res) => {
        expect(res.statusCode).to.equal(429);
        done();
      });
    });

    it('segue redirect 302', (done) => {
      http.get(`http://127.0.0.1:${mockFilePort}/redirect.7z`, (res) => {
        expect(res.statusCode).to.equal(302);
        expect(res.headers.location).to.equal('/game.7z');
        done();
      });
    });
  });

  describe('resolveAndDownload com fonte mock', () => {
    it('falha graciosamente quando fonte nao responde', async () => {
      const item = { serial: 'INTEGRATION_FAIL' };
      const sources = [
        { site: 'dead_source', url: 'http://127.0.0.1:99999/nope.7z' }
      ];
      try {
        await dl.resolveAndDownload(item, sources, 'any');
        expect.fail('deveria falhar');
      } catch (e) {
        expect(e.message).to.include('todas as fontes falharam');
      }
    }).timeout(120000);

    it('falha com 404 da fonte', async () => {
      const item = { serial: 'INTEGRATION_404' };
      const sources = [
        { site: 'mock_404', url: `http://127.0.0.1:${mockFilePort}/404` }
      ];
      try {
        await dl.resolveAndDownload(item, sources, 'any');
        expect.fail('deveria falhar');
      } catch (e) {
        expect(e.message).to.include('todas as fontes falharam');
      }
    }).timeout(120000);
  });

  describe('Source slots sob carga', () => {
    it('nao excede limite max de slots concorrentes', async () => {
      const site = 'integration_slot_test';
      dl.sourceSlots.set(site, { current: 0, max: 3, waiters: [] });

      // Adquire 3 slots
      await dl.acquireSourceSlot(site, 1000);
      await dl.acquireSourceSlot(site, 1000);
      await dl.acquireSourceSlot(site, 1000);

      const state = dl.getSlotState(site);
      expect(state.current).to.equal(3);

      // Quarto deve aguardar
      let fourthAcquired = false;
      const fourth = dl.acquireSourceSlot(site, 300).then(() => { fourthAcquired = true; });
      await new Promise(r => setTimeout(r, 100));
      expect(fourthAcquired).to.be.false;

      // Libera um
      dl.releaseSourceSlot(site);
      await fourth;
      expect(fourthAcquired).to.be.true;

      // Limpa
      dl.releaseSourceSlot(site);
      dl.releaseSourceSlot(site);
      dl.releaseSourceSlot(site);
    });
  });

  describe('Cooldown de fonte', () => {
    it('bloqueia downloads durante cooldown', () => {
      const site = 'integration_cooldown_test';
      dl.setSourceCooldown(site, 10000);
      expect(dl.isSourceInCooldown(site)).to.be.true;
    });

    it('permite downloads apos cooldown expirar', async () => {
      const site = 'integration_cooldown_exp';
      dl.setSourceCooldown(site, 100);
      await new Promise(r => setTimeout(r, 200));
      expect(dl.isSourceInCooldown(site)).to.be.false;
    });
  });

  describe('Status do servico', () => {
    it('status tem campos esperados', () => {
      expect(dl.status).to.have.property('active');
      expect(dl.status).to.have.property('completed');
      expect(dl.status).to.have.property('failed');
    });
  });
});
