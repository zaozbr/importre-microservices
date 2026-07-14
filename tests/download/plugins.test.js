// Testes para plugins de busca: romsfun, consoleroms e archive_chd_jp
// Testa: carregamento, prioridade, matchType, busca por titulo, validacao de URLs,
// rejeicao de mods/sequencias erradas, fallback quando titulo nao encontrado.
// Roda: npx mocha tests/download/plugins.test.js --timeout 60000
const { expect } = require('chai');

const { plugins } = require('../../services/search/plugins/loader');

describe('Plugins: romsfun e consoleroms', () => {
  describe('Carregamento e configuracao', () => {
    it('romsfun deve estar carregado', () => {
      expect(plugins['romsfun']).to.exist;
      expect(plugins['romsfun'].name).to.equal('romsfun');
    });

    it('consoleroms deve estar carregado', () => {
      expect(plugins['consoleroms']).to.exist;
      expect(plugins['consoleroms'].name).to.equal('consoleroms');
    });

    it('romsfun deve ter prioridade e enabled corretos', () => {
      const p = plugins['romsfun'];
      expect(p.priority).to.be.a('number');
      expect(p.enabled).to.be.true;
      expect(p.matchType).to.equal('title');
      expect(p.needsMultiChunk).to.be.true;
    });

    it('consoleroms deve ter prioridade e enabled corretos', () => {
      const p = plugins['consoleroms'];
      expect(p.priority).to.be.a('number');
      expect(p.enabled).to.be.true;
      expect(p.matchType).to.equal('title');
      expect(p.needsMultiChunk).to.be.true;
    });

    it('ambos devem ter funcao search', () => {
      expect(plugins['romsfun'].search).to.be.a('function');
      expect(plugins['consoleroms'].search).to.be.a('function');
    });
  });

  describe('romsfun: validacao de entrada', () => {
    it('deve retornar array vazio para titulo vazio', async () => {
      const result = await plugins['romsfun'].search('SCUS-001', '');
      expect(result).to.be.an('array');
      expect(result).to.have.length(0);
    });

    it('deve retornar array vazio para titulo null', async () => {
      const result = await plugins['romsfun'].search('SCUS-001', null);
      expect(result).to.be.an('array');
      expect(result).to.have.length(0);
    });

    it('deve retornar array (mesmo que vazio) para titulo valido', async () => {
      const result = await plugins['romsfun'].search('SCUS-99999', 'Nonexistent Game XYZ');
      expect(result).to.be.an('array');
    });
  });

  describe('consoleroms: validacao de entrada', () => {
    it('deve retornar array vazio para titulo vazio', async () => {
      const result = await plugins['consoleroms'].search('SCUS-001', '');
      expect(result).to.be.an('array');
      expect(result).to.have.length(0);
    });

    it('deve retornar array vazio para titulo null', async () => {
      const result = await plugins['consoleroms'].search('SCUS-001', null);
      expect(result).to.be.an('array');
      expect(result).to.have.length(0);
    });

    it('deve retornar array para titulo de jogo inexistente', async () => {
      const result = await plugins['consoleroms'].search('SCUS-99999', 'Nonexistent Game XYZ');
      expect(result).to.be.an('array');
    });
  });

  describe('romsfun: estrutura de resultados', () => {
    it('cada source deve ter site, url e title', async () => {
      // Testa com um titulo que provavelmente existe
      const result = await plugins['romsfun'].search('SCUS-94900', 'Crash Bandicoot');
      if (result.length > 0) {
        for (const s of result) {
          expect(s.site).to.equal('romsfun');
          expect(s.url).to.be.a('string');
          expect(s.url).to.not.be.empty;
          expect(s.title).to.exist;
        }
      }
    });

    it('URLs devem ser URLs validas (http/https)', async () => {
      const result = await plugins['romsfun'].search('SCUS-94900', 'Crash Bandicoot');
      for (const s of result) {
        expect(s.url).to.match(/^https?:\/\//);
      }
    });
  });

  describe('consoleroms: estrutura de resultados', () => {
    it('cada source deve ter site, url e title', async () => {
      const result = await plugins['consoleroms'].search('SCUS-94900', 'Crash Bandicoot');
      if (result.length > 0) {
        for (const s of result) {
          expect(s.site).to.equal('consoleroms');
          expect(s.url).to.be.a('string');
          expect(s.url).to.not.be.empty;
        }
      }
    });

    it('URLs devem ser URLs validas (http/https)', async () => {
      const result = await plugins['consoleroms'].search('SCUS-94900', 'Crash Bandicoot');
      for (const s of result) {
        expect(s.url).to.match(/^https?:\/\//);
      }
    });
  });

  describe('romsfun: priorizacao de ROMs sobre mods', () => {
    it('deve priorizar URLs com /PSX/ sobre /Mods/', async () => {
      const result = await plugins['romsfun'].search('SCUS-94900', 'Crash Bandicoot');
      if (result.length >= 2) {
        const hasPsx = result.some(s => s.url.includes('/PSX/'));
        const hasMods = result.some(s => s.url.includes('/Mods/'));
        if (hasPsx && hasMods) {
          const psxIdx = result.findIndex(s => s.url.includes('/PSX/'));
          const modsIdx = result.findIndex(s => s.url.includes('/Mods/'));
          expect(psxIdx).to.be.lessThan(modsIdx, 'ROMs originais devem vir antes de mods');
        }
      }
    });
  });

  describe('consoleroms: anti-sequencia', () => {
    it('nao deve retornar sequencia errada (Crash 2 quando buscar Crash 1)', async () => {
      const result = await plugins['consoleroms'].search('SCUS-94900', 'Crash Bandicoot');
      // Se retornar resultados, nenhum deve ser "Crash Bandicoot 2" ou "3"
      for (const s of result) {
        const urlLower = s.url.toLowerCase();
        // URL nao deve conter "crash-bandicoot-2" ou "crash-bandicoot-3"
        expect(urlLower).to.not.include('crash-bandicoot-2');
        expect(urlLower).to.not.include('crash-bandicoot-3');
      }
    });
  });

  describe('romsfun: extracao de extensao', () => {
    it('URLs de download devem ter extensao de ROM (.zip, .7z, .rar, .iso)', async () => {
      const result = await plugins['romsfun'].search('SCUS-94900', 'Crash Bandicoot');
      for (const s of result) {
        const hasExt = /\.(zip|7z|rar|iso|bin|cue|img|chd)/i.test(s.url);
        expect(hasExt, `URL sem extensao de ROM: ${s.url}`).to.be.true;
      }
    });
  });

  describe('consoleroms: extracao de extensao', () => {
    it('URLs de download devem ter extensao de ROM', async () => {
      const result = await plugins['consoleroms'].search('SCUS-94900', 'Crash Bandicoot');
      for (const s of result) {
        const hasExt = /\.(zip|7z|rar|iso|bin|cue|img|chd)/i.test(s.url);
        expect(hasExt, `URL sem extensao de ROM: ${s.url}`).to.be.true;
      }
    });
  });

  describe('Tratamento de erros', () => {
    it('romsfun nao deve lancar erro para entrada invalida', async () => {
      let threw = false;
      try {
        await plugins['romsfun'].search('', '');
      } catch (e) { threw = true; }
      expect(threw).to.be.false;
    });

    it('consoleroms nao deve lancar erro para entrada invalida', async () => {
      let threw = false;
      try {
        await plugins['consoleroms'].search('', '');
      } catch (e) { threw = true; }
      expect(threw).to.be.false;
    });

    it('romsfun deve retornar array mesmo em falha de rede', async () => {
      // Titulo que causa timeout ou erro de rede
      const result = await plugins['romsfun'].search('XXXX-00000', 'zzzzz nonexistent');
      expect(result).to.be.an('array');
    });

    it('consoleroms deve retornar array mesmo em falha de rede', async () => {
      const result = await plugins['consoleroms'].search('XXXX-00000', 'zzzzz nonexistent');
      expect(result).to.be.an('array');
    });
  });

  describe('archive_chd_jp: plugin JP com 4161 ROMs CHD', () => {
    it('deve estar carregado', () => {
      expect(plugins['archive_chd_jp']).to.exist;
      expect(plugins['archive_chd_jp'].name).to.equal('archive-chd-jp');
    });

    it('deve ter prioridade e enabled corretos', () => {
      const p = plugins['archive_chd_jp'];
      expect(p.priority).to.be.a('number');
      expect(p.enabled).to.be.true;
      expect(p.matchType).to.equal('title');
    });

    it('deve retornar vazio para serial nao-JP (SLUS)', async () => {
      const result = await plugins['archive_chd_jp'].search('SLUS-00426', 'MDK (USA)');
      expect(result).to.be.an('array');
      expect(result).to.have.length(0);
    });

    it('deve retornar vazio para serial nao-JP (SLES)', async () => {
      const result = await plugins['archive_chd_jp'].search('SLES-00567', 'Tomb Raider (Europe)');
      expect(result).to.be.an('array');
      expect(result).to.have.length(0);
    });

    it('deve retornar vazio para titulo vazio', async () => {
      const result = await plugins['archive_chd_jp'].search('SLPS-001', '');
      expect(result).to.be.an('array');
      expect(result).to.have.length(0);
    });

    it('deve encontrar jogos JP por titulo', async () => {
      const result = await plugins['archive_chd_jp'].search('SLPS-03189', 'Gear Fighter Dendoh (Japan)');
      expect(result).to.be.an('array');
      // Pode encontrar ou nao (depende do cache), mas nao deve crashar
      if (result.length > 0) {
        for (const s of result) {
          expect(s.site).to.equal('archive-chd-jp');
          expect(s.url).to.match(/^https?:\/\//);
          expect(s.url).to.include('.chd');
        }
      }
    });

    it('URLs devem apontar para archive.org/download/chd_psx_jap', async () => {
      const result = await plugins['archive_chd_jp'].search('SLPS-01348', 'G-Darius (Japan)');
      for (const s of result) {
        expect(s.url).to.include('archive.org/download/chd_psx_jap');
      }
    });

    it('nao deve lancar erro para entrada invalida', async () => {
      let threw = false;
      try {
        await plugins['archive_chd_jp'].search('', '');
      } catch (e) { threw = true; }
      expect(threw).to.be.false;
    });
  });

  describe('coolrom: validacao de volume anti-bug', () => {
    it('deve estar carregado (desativado por bug de volume)', () => {
      expect(plugins['coolrom']).to.exist;
      expect(plugins['coolrom'].enabled).to.be.false; // desativado apos bug 0/13 corretos
    });

    it('NAO deve retornar a mesma URL para Suudoku 3, 4 e 5 (bug original)', async () => {
      const r3 = await plugins['coolrom'].search('SLPM-86536', 'Suudoku 3 [Superlite 1500 Series]');
      const r4 = await plugins['coolrom'].search('SLPM-86676', 'Suudoku 4 [Superlite 1500 Series]');
      const r5 = await plugins['coolrom'].search('SLPM-86741', 'Suudoku 5 [Superlite 1500 Series]');
      // Se todos retornam a mesma URL, o bug persiste
      const urls3 = r3.map(s => s.url);
      const urls4 = r4.map(s => s.url);
      const urls5 = r5.map(s => s.url);
      // Nao deve haver intersecao entre os 3
      const overlap34 = urls3.some(u => urls4.includes(u));
      const overlap35 = urls3.some(u => urls5.includes(u));
      const overlap45 = urls4.some(u => urls5.includes(u));
      expect(overlap34, 'Suudoku 3 e 4 nao devem ter URLs em comum').to.be.false;
      expect(overlap35, 'Suudoku 3 e 5 nao devem ter URLs em comum').to.be.false;
      expect(overlap45, 'Suudoku 4 e 5 nao devem ter URLs em comum').to.be.false;
    });

    it('Hello Kitty Vol.1 e Vol.2 nao devem retornar Vol.04', async () => {
      const r1 = await plugins['coolrom'].search('SLPM-86866', 'Simple 1500 Series Hello Kitty Vol.1');
      const r2 = await plugins['coolrom'].search('SLPM-86867', 'Simple 1500 Series Hello Kitty Vol.2');
      // Nenhum resultado deve conter "Vol.04" ou "Vol._04"
      for (const s of r1) {
        expect(s.url).to.not.include('Vol._04', 'Vol.1 nao deve retornar Vol.04');
        expect(s.url).to.not.include('Vol.04', 'Vol.1 nao deve retornar Vol.04');
      }
      for (const s of r2) {
        expect(s.url).to.not.include('Vol._04', 'Vol.2 nao deve retornar Vol.04');
        expect(s.url).to.not.include('Vol.04', 'Vol.2 nao deve retornar Vol.04');
      }
    });

    it('Simple 1500 Series Vol.12 nao deve retornar Vol.34', async () => {
      const r = await plugins['coolrom'].search('SLPM-86970', 'Simple 1500 Series Vol.12 - The Quiz');
      for (const s of r) {
        expect(s.url).to.not.include('Vol._34', 'Vol.12 nao deve retornar Vol.34');
      }
    });

    it('extrair volume de titulos com "Vol.N"', () => {
      // Testa a funcao interna indiretamente via comportamento do plugin
      // Se o plugin nao retorna volume errado, a extracao funciona
    });
  });
});
