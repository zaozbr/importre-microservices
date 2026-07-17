const { expect } = require('chai');
const { killPid, pidsOnPort, killByPort, isPortFree, killByName, killBeforeStart } = require('../../shared/kill_before_start');

describe('kill_before_start', () => {
  describe('pidsOnPort', () => {
    it('deve retornar array para porta nao usada', () => {
      const pids = pidsOnPort(59999);
      expect(pids).to.be.an('array');
      // porta 59999 provavelmente nao esta em uso
      expect(pids.length).to.equal(0);
    });
  });

  describe('isPortFree', () => {
    it('deve retornar true para porta livre', () => {
      expect(isPortFree(59999)).to.be.true;
    });
  });

  describe('killPid', () => {
    it('deve retornar false para PID invalido', () => {
      expect(killPid(0)).to.be.false;
      expect(killPid(null)).to.be.false;
      expect(killPid(undefined)).to.be.false;
    });
  });

  describe('killByName', () => {
    it('deve retornar 0 para processo inexistente', () => {
      const count = killByName('processo-inexistente-12345.exe');
      expect(count).to.equal(0);
    });
  });

  describe('killBeforeStart', () => {
    it('deve executar sem erro para porta livre', async () => {
      const result = await killBeforeStart({
        port: 59999,
        name: 'test-service',
        waitPort: true,
        waitTimeoutMs: 1000,
        log: () => {}, // silencioso
      });
      expect(result).to.have.property('killed');
      expect(result).to.have.property('portFree');
      expect(result.portFree).to.be.true;
    });

    it('deve aceitar opts vazias', async () => {
      const result = await killBeforeStart({ log: () => {} });
      expect(result).to.have.property('killed', 0);
    });

    it('deve retornar killed=0 quando nao ha processo na porta', async () => {
      const result = await killBeforeStart({
        port: 59998,
        name: 'test',
        waitPort: false,
        log: () => {},
      });
      expect(result.killed).to.equal(0);
    });
  });
});
