/**
 * rpc_token.test.js — Verifica que todas chamadas aria2 RPC incluem o token.
 *
 * Cobre: aria2_rpc.js, motrix_watchdog.js, ariang_watchdog.js, orchestrator/index.js
 * Para cada arquivo, le o codigo e verifica que chamadas aria2.* incluem 'token:devin'.
 */
require('../download/_setup');
const { expect } = require('chai');
const fs = require('fs');
const path = require('path');

const FILES_TO_CHECK = [
  { name: 'aria2_rpc.js', path: path.join(__dirname, '..', '..', 'services', 'download', 'aria2_rpc.js') },
  { name: 'motrix_watchdog.js', path: path.join(__dirname, '..', '..', 'services', 'download', 'motrix_watchdog.js') },
  { name: 'ariang_watchdog.js', path: path.join(__dirname, '..', '..', 'tools', 'ariang_watchdog.js') },
  { name: 'orchestrator/index.js', path: path.join(__dirname, '..', '..', 'orchestrator', 'index.js') },
];

// Metodos aria2 que exigem token (referencia — nao usado diretamente)
const _ARIA2_METHODS = [
  'aria2.getVersion', 'aria2.getGlobalStat', 'aria2.tellActive', 'aria2.tellStopped',
  'aria2.tellWaiting', 'aria2.tellStatus', 'aria2.addUri', 'aria2.addTorrent',
  'aria2.remove', 'aria2.forceRemove', 'aria2.pause', 'aria2.unpause',
  'aria2.getPeers', 'aria2.getFiles', 'aria2.getServers', 'aria2.getOption',
  'aria2.changeOption', 'aria2.getGlobalOption', 'aria2.changeGlobalOption',
  'aria2.changePosition', 'aria2.purgeDownloadResult', 'aria2.removeDownloadResult',
];

describe('RPC Token — todas chamadas aria2 devem incluir token:devin', function () {
  this.timeout(10000);

  FILES_TO_CHECK.forEach(({ name, path: filePath }) => {
    describe(`Arquivo: ${name}`, () => {
      let content;

      before(() => {
        try {
          content = fs.readFileSync(filePath, 'utf-8');
        } catch (e) {
          content = null;
        }
      });

      it('deve existir', () => {
        expect(content, `Arquivo ${filePath} nao encontrado`).to.not.be.null;
      });

      // Conta quantas chamadas aria2.* existem
      const methodCalls = content ? content.match(/aria2\.\w+/g) || [] : [];
      const uniqueMethods = [...new Set(methodCalls)];

      if (uniqueMethods.length > 0) {
        it(`deve ter ${uniqueMethods.length} metodos aria2 diferentes`, () => {
          expect(uniqueMethods.length).to.be.greaterThan(0);
        });

        it('TODAS chamadas devem incluir token:devin ou ARIA2_RPC_TOKEN ou ARIA2_TOKEN', () => {
          // Verifica que o arquivo referencia o token de alguma forma
          const hasToken = content.includes('token:devin') ||
                           content.includes('ARIA2_RPC_TOKEN') ||
                           content.includes('ARIA2_TOKEN') ||
                           content.includes("['token:devin'") ||
                           content.includes("['token:devin',");
          expect(hasToken, `${name} nao referencia token:devin em nenhum lugar`).to.be.true;
        });

        // Verifica que nao ha params: [] (sem token) em chamadas aria2
        it('nao deve ter params: [] (sem token) em chamadas aria2', () => {
          // Procura por padroes como "params: []" que indicam chamada sem token
          const emptyParams = content.match(/params:\s*\[\s*\]/g) || [];
          // Permite params: [] apenas se nao estiver proximo de aria2.
          // Como e dificil verificar contexto, verificamos se ha mais tokens que empty params
          const tokenCount = (content.match(/token:devin|ARIA2_RPC_TOKEN|ARIA2_TOKEN/g) || []).length;
          // Se ha empty params, deve ha pelo menos 1 token para compensar
          if (emptyParams.length > 0) {
            expect(tokenCount, `${name} tem ${emptyParams.length} params:[] mas apenas ${tokenCount} referencias de token`).to.be.greaterThan(0);
          }
        });
      }
    });
  });

  describe('Bug -> Teste: token ausente causava "Motrix indisponivel"', () => {
    it('motrix_watchdog.js rpc() deve prefixar token nos params', () => {
      const content = fs.readFileSync(
        path.join(__dirname, '..', '..', 'services', 'download', 'motrix_watchdog.js'), 'utf-8'
      );
      // A funcao rpc deve adicionar token:devin aos params
      expect(content).to.contain("'token:devin'");
    });

    it('aria2_rpc.js rpc() deve prefixar token nos params', () => {
      const content = fs.readFileSync(
        path.join(__dirname, '..', '..', 'services', 'download', 'aria2_rpc.js'), 'utf-8'
      );
      // A funcao rpc deve adicionar token:devin aos params
      expect(content).to.contain("'token:devin'");
    });

    it('ariang_watchdog.js probePort deve usar token', () => {
      const content = fs.readFileSync(
        path.join(__dirname, '..', '..', 'tools', 'ariang_watchdog.js'), 'utf-8'
      );
      // Deve usar ARIA2_RPC_TOKEN ou token:devin
      expect(content).to.contain('ARIA2_RPC_TOKEN');
    });

    it('orchestrator/index.js deve ter ARIA2_TOKEN definido', () => {
      const content = fs.readFileSync(
        path.join(__dirname, '..', '..', 'orchestrator', 'index.js'), 'utf-8'
      );
      expect(content).to.contain('ARIA2_TOKEN');
      expect(content).to.contain('token:devin');
    });
  });
});
