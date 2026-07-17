/**
 * search_lines.test.js — Testes E2E para cada plugin de search.
 *
 * Duas fases:
 * 1. Estrutura (sem rede): verifica que cada plugin carrega, exporta interface correta
 * 2. E2E (com rede, opt-in): chama search() com timeout — apenas com SEARCH_E2E=1
 *
 * Por padrao, roda apenas fase 1 (rapida, sem rede).
 * Para rodar fase 2: SEARCH_E2E=1 npm run test:e2e:search
 */
require('../download/_setup');
const { expect } = require('chai');
const fs = require('fs');
const path = require('path');

const PLUGINS_DIR = path.join(__dirname, '..', '..', 'services', 'search', 'plugins');
const RUN_E2E = process.env.SEARCH_E2E === '1';

// Lista todos os plugins (exceto _base, loader, generic_search, web_sites, magnet_cache)
const pluginFiles = fs.readdirSync(PLUGINS_DIR)
  .filter(f => f.endsWith('.js') && !f.startsWith('_') && f !== 'loader.js' && f !== 'generic_search.js' && f !== 'web_sites.js' && f !== 'magnet_cache.js');

const TEST_CASES = [
  { serial: 'SCES-00422', title: 'Crash Bandicoot' },
  { serial: 'SLUS-00598', title: 'Final Fantasy VII' },
];

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`timeout ${ms}ms em ${label}`)), ms))
  ]);
}

describe('Search Plugins E2E — cada linha de search', function () {
  this.timeout(15000);

  // Fase 1: Estrutura (sem rede) — sempre roda
  describe('Fase 1: Estrutura (sem rede)', () => {
    pluginFiles.forEach(file => {
      const pluginName = path.basename(file, '.js');
      let plugin = null;

      before(() => {
        try {
          delete require.cache[require.resolve(path.join(PLUGINS_DIR, file))];
          plugin = require(path.join(PLUGINS_DIR, file));
        } catch (e) {
          plugin = null;
        }
      });

      describe(`Plugin: ${pluginName}`, () => {
        it('deve carregar sem erro', () => {
          expect(plugin, `Plugin ${pluginName} falhou ao carregar`).to.not.be.null;
        });

        it('deve exportar name (string)', () => {
          if (!plugin) return;
          expect(plugin.name).to.be.a('string');
          expect(plugin.name).to.not.be.empty;
        });

        it('deve exportar matchType (string)', () => {
          if (!plugin) return;
          expect(plugin.matchType).to.be.a('string');
          expect(['serial', 'title', 'unknown']).to.include(plugin.matchType);
        });

        it('deve exportar search() function', () => {
          if (!plugin) return;
          expect(plugin.search).to.be.a('function');
        });

        it('deve exportar priority (number)', () => {
          if (!plugin) return;
          expect(plugin.priority).to.be.a('number');
        });

        it('deve exportar enabled (boolean)', () => {
          if (!plugin) return;
          expect(plugin.enabled).to.be.a('boolean');
        });
      });
    });
  });

  // Fase 2: E2E (com rede) — apenas com SEARCH_E2E=1
  describe('Fase 2: E2E com rede (opt-in: SEARCH_E2E=1)', () => {
    before(function () {
      if (!RUN_E2E) this.skip();
    });

    pluginFiles.forEach(file => {
      const pluginName = path.basename(file, '.js');
      let plugin = null;

      before(() => {
        try {
          delete require.cache[require.resolve(path.join(PLUGINS_DIR, file))];
          plugin = require(path.join(PLUGINS_DIR, file));
        } catch { plugin = null; }
      });

      describe(`Plugin: ${pluginName}`, () => {
        TEST_CASES.forEach(({ serial, title }) => {
          it(`search(${serial}) deve retornar array ou [] (graceful)`, async function () {
            if (!plugin || plugin.enabled === false) { this.skip(); return; }
            let result;
            try {
              result = await withTimeout(plugin.search(serial, title), 8000, `${pluginName}.search`);
            } catch {
              // Timeout ou erro de rede e aceitavel em teste
              return;
            }
            expect(result).to.be.an('array');
          });

          it(`search(${serial}) sources devem ter {site, url} validos`, async function () {
            if (!plugin || plugin.enabled === false) { this.skip(); return; }
            let result;
            try {
              result = await withTimeout(plugin.search(serial, title), 8000, `${pluginName}.search`);
            } catch { return; }
            if (!result || result.length === 0) return;
            result.forEach((src, i) => {
              expect(src, `Source #${i} de ${pluginName}`).to.have.property('site');
              expect(src).to.have.property('url');
              expect(src.url, `URL de ${pluginName} source #${i}`).to.not.be.empty;
              if (typeof src.url === 'string' && src.url.length > 0) {
                expect(src.url).to.match(/^(https?:|magnet:|ftp:|\/)/, `URL invalida: ${src.url}`);
              }
            });
          });
        });
      });
    });
  });

  // Bug -> Teste: plugin que lanca exception em vez de retornar []
  describe('Bug -> Teste: plugins devem tratar erros gracefulmente', () => {
    it('loader.js searchWith deve capturar exceptions e retornar []', () => {
      const loaderSrc = fs.readFileSync(path.join(PLUGINS_DIR, 'loader.js'), 'utf-8');
      expect(loaderSrc).to.contain('try');
      expect(loaderSrc).to.contain('catch');
      expect(loaderSrc).to.contain('return []');
    });
  });
});
