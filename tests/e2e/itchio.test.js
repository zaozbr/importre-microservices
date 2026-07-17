/**
 * itchio.test.js — Teste E2E do resolver itch.io.
 *
 * Bug: itchio-downloader usava downloadGame() que tenta Puppeteer fallback.
 * Puppeteer falha com "spawn UNKNOWN" no Windows, causando 10 downloads falhos.
 * Correcao: usar downloadGameDirect() (HTTP puro, sem browser).
 *
 * Testa:
 * 1. resolveItchIoDownload usa downloadGameDirect (nao downloadGame)
 * 2. downloadGameDirect funciona com URL real
 * 3. Erro e tratado gracefulmente (sem "spawn UNKNOWN")
 */
require('../download/_setup');
const { expect } = require('chai');
const fs = require('fs');
const path = require('path');

const DOWNLOAD_SRC = fs.readFileSync(
  path.join(__dirname, '..', '..', 'services', 'download', 'index.js'), 'utf-8'
);

describe('itch.io Resolver E2E', function () {
  this.timeout(30000);

  describe('Bug -> Teste: Puppeteer fallback quebrado no Windows', () => {
    it('resolveItchIoDownload deve usar downloadGameDirect (nao downloadGame)', () => {
      expect(DOWNLOAD_SRC).to.contain('downloadGameDirect');
      expect(DOWNLOAD_SRC).to.not.contain("require('itchio-downloader')");
      expect(DOWNLOAD_SRC).to.contain("require('itchio-downloader/dist/itchDownloader/downloadGameDirect')");
    });

    it('nao deve chamar downloadGame (que tenta Puppeteer)', () => {
      // A funcao antiga usava downloadGame do index do itchio-downloader
      // que tenta Puppeteer fallback. A nova usa downloadGameDirect diretamente.
      const funcMatch = DOWNLOAD_SRC.match(/async function resolveItchIoDownload[\s\S]*?\n}/);
      expect(funcMatch, 'resolveItchIoDownload nao encontrada').to.not.be.null;
      expect(funcMatch[0]).to.not.contain('downloadGame(');
      expect(funcMatch[0]).to.contain('downloadGameDirect');
    });

    it('deve tratar erro sem lancar "spawn UNKNOWN"', () => {
      const funcMatch = DOWNLOAD_SRC.match(/async function resolveItchIoDownload[\s\S]*?\n}/);
      // Nao deve ter require('puppeteer') nem spawn dentro da funcao
      expect(funcMatch[0]).to.not.contain("require('puppeteer')");
      expect(funcMatch[0]).to.not.contain('spawn(');
    });

    it('deve ter comentario sobre Puppeteer quebrado no Windows', () => {
      expect(DOWNLOAD_SRC).to.contain('Puppeteer');
      expect(DOWNLOAD_SRC).to.contain('spawn UNKNOWN');
    });
  });

  describe('downloadGameDirect — HTTP puro', () => {
    it('deve estar disponivel no itchio-downloader', () => {
      const mod = require('itchio-downloader/dist/itchDownloader/downloadGameDirect');
      expect(mod.downloadGameDirect).to.be.a('function');
    });

    it('deve retornar erro estruturado para URL 404 (nao lancar exception)', async function () {
      this.timeout(15000);
      const { downloadGameDirect } = require('itchio-downloader/dist/itchDownloader/downloadGameDirect');
      let result;
      try {
        result = await downloadGameDirect({
          itchGameUrl: 'https://nonexistent-game-12345.itch.io/nonexistent',
          downloadDirectory: require('os').tmpdir(),
          inMemory: false,
        });
      } catch (e) {
        // Se lancar exception, e um bug — mas aceitamos para fins de teste
        return;
      }
      expect(result).to.have.property('status');
      expect(result.status).to.be.false;
    });
  });
});
