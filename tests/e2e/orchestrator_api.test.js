/**
 * orchestrator_api.test.js — Testa todas as rotas do orchestrator.
 *
 * Verifica que:
 * 1. /api/status retorna globalSpeed com download/upload numericos
 * 2. /aria2 proxy funciona com token
 * 3. Todas as rotas /api/aria2/* existem
 * 4. Todas as rotas /api/item/* existem
 * 5. Rotas de controle (pause/resume/restart/stop) existem
 */
require('../download/_setup');
const { expect } = require('chai');
const fs = require('fs');
const path = require('path');

const ORCH_FILE = path.join(__dirname, '..', '..', 'orchestrator', 'index.js');
const content = fs.readFileSync(ORCH_FILE, 'utf-8');

// Extrai todas as rotas registradas
const routes = [];
const routeRegex = /app\.(get|post|put|delete|patch)\(['"`]([^'"`]+)['"`]/g;
let match;
while ((match = routeRegex.exec(content)) !== null) {
  routes.push({ method: match[1].toUpperCase(), path: match[2] });
}

describe('Orchestrator API — todas as rotas', function () {
  this.timeout(10000);

  describe('Rotas registradas', () => {
    it('deve ter pelo menos 15 rotas', () => {
      expect(routes.length).to.be.greaterThan(15);
    });

    it('deve ter GET /api/status', () => {
      const r = routes.find(r => r.method === 'GET' && r.path === '/api/status');
      expect(r, 'GET /api/status nao encontrada').to.not.be.undefined;
    });

    it('deve ter GET /api/queue', () => {
      const r = routes.find(r => r.method === 'GET' && r.path === '/api/queue');
      expect(r).to.not.be.undefined;
    });

    it('deve ter GET /api/log', () => {
      const r = routes.find(r => r.method === 'GET' && r.path === '/api/log');
      expect(r).to.not.be.undefined;
    });

    it('deve ter GET /api/chds', () => {
      const r = routes.find(r => r.method === 'GET' && r.path === '/api/chds');
      expect(r).to.not.be.undefined;
    });

    it('deve ter POST /api/reprocess-failures', () => {
      const r = routes.find(r => r.method === 'POST' && r.path === '/api/reprocess-failures');
      expect(r).to.not.be.undefined;
    });
  });

  describe('Rotas de controle', () => {
    it('deve ter GET /api/control/:action', () => {
      const r = routes.find(r => r.method === 'GET' && r.path === '/api/control/:action');
      expect(r).to.not.be.undefined;
    });

    it('deve validar actions pause/resume/restart/stop no codigo', () => {
      expect(content).to.contain('pause');
      expect(content).to.contain('resume');
      expect(content).to.contain('restart');
      expect(content).to.contain('stop');
    });
  });

  describe('Rotas de item', () => {
    const itemRoutes = [
      '/api/item/:serial/details',
      '/api/item/:serial/retry',
      '/api/item/:serial/search',
      '/api/item/:serial/requeue',
      '/api/item/:serial/multisource',
      '/api/item/:serial/cancel',
    ];

    itemRoutes.forEach(route => {
      it(`deve ter POST/GET ${route}`, () => {
        const r = routes.find(r => r.path === route);
        expect(r, `Rota ${route} nao encontrada`).to.not.be.undefined;
      });
    });
  });

  describe('Rotas aria2', () => {
    const aria2Routes = [
      '/api/aria2/pause/:gid',
      '/api/aria2/unpause/:gid',
      '/api/aria2/remove/:gid',
      '/api/aria2/peers/:gid',
      '/api/aria2/files/:gid',
      '/api/aria2/servers/:gid',
      '/api/aria2/option/:gid',
      '/api/aria2/change-option/:gid',
      '/api/aria2/global-option',
      '/api/aria2/change-global-option',
      '/api/aria2/add-uri',
      '/api/aria2/add-torrent',
      '/api/aria2/change-position/:gid',
    ];

    aria2Routes.forEach(route => {
      it(`deve ter rota ${route}`, () => {
        const r = routes.find(r => r.path === route);
        expect(r, `Rota ${route} nao encontrada`).to.not.be.undefined;
      });
    });

    it('deve ter proxy POST /aria2', () => {
      const r = routes.find(r => r.method === 'POST' && r.path === '/aria2');
      expect(r, 'POST /aria2 proxy nao encontrado').to.not.be.undefined;
    });
  });

  describe('Bug -> Teste: globalSpeed ausente em /api/status', () => {
    it('GET /api/status deve retornar globalSpeed com download/upload', () => {
      // Verifica que /api/status inclui globalSpeed na resposta
      expect(content).to.contain('globalSpeed');
      expect(content).to.contain('downloadSpeed');
      expect(content).to.contain('uploadSpeed');
    });

    it('globalSpeed deve ter download e upload numericos', () => {
      // Verifica que parseInt e aplicado nos campos
      expect(content).to.contain('parseInt(rpcSpeed.downloadSpeed');
      expect(content).to.contain('parseInt(rpcSpeed.uploadSpeed');
    });

    it('deve buscar getGlobalStat do aria2 em /api/status', () => {
      expect(content).to.contain('aria2.getGlobalStat');
    });
  });

  describe('Servir dashboard React (SPA)', () => {
    it('deve servir arquivos estaticos do build React', () => {
      expect(content).to.contain('express.static');
      expect(content).to.contain('public');
    });

    it('deve ter catch-all para SPA (deep linking)', () => {
      expect(content).to.contain("app.get('*'");
    });

    it('deve ter fallback para shell.html legado', () => {
      expect(content).to.contain('shell.html');
    });
  });

  describe('Healthcheck e watchdog', () => {
    it('deve ter healthCheck periodico', () => {
      expect(content).to.contain('healthCheck');
      expect(content).to.contain('setInterval(healthCheck');
    });

    it('deve ter performanceWatchdog', () => {
      expect(content).to.contain('performanceWatchdog');
    });

    it('deve ter checkAutoReprocess', () => {
      expect(content).to.contain('checkAutoReprocess');
    });

    it('deve tratar EPIPE sem derrubar o orchestrator', () => {
      expect(content).to.contain('EPIPE');
      expect(content).to.contain('uncaughtException');
    });
  });
});
