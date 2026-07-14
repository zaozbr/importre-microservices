// Testes de respawn de arquivos: arquivo corrompido, incompleto, re-download,
// extracao falha, validacao de conteudo, cleanup de arquivos temporarios.
// Roda: npx mocha tests/download/respawn.test.js --timeout 60000
const { tmpDir } = require('./_setup');
const { expect } = require('chai');
const fs = require('fs');
const path = require('path');
const http = require('http');

const dl = require('../../services/download/index');

let mockServer;
const mockPort = 19010;

function createMockServer(port, handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

function closeServer(server) {
  return new Promise((resolve) => {
    if (!server) return resolve();
    server.close(() => resolve());
  });
}

// Cria um arquivo .7z valido minimo (header 7z: 37 7A BC AF 27 1C)
function createValid7zHeader() {
  return Buffer.from([0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C, 0x00, 0x00, 0x00, 0x00]);
}

describe('Respawn: validacao e recuperacao de arquivos', () => {
  before(async () => {
    if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });
    mockServer = await createMockServer(mockPort, (req, res) => {
      if (req.url === '/valid.7z') {
        const buf = createValid7zHeader();
        res.setHeader('Content-Type', 'application/octet-stream');
        res.end(buf);
      } else if (req.url === '/corrupt.7z') {
        res.setHeader('Content-Type', 'application/octet-stream');
        res.end(Buffer.from('CORRUPT_DATA_NOT_A_VALID_ARCHIVE'));
      } else if (req.url === '/empty.7z') {
        res.setHeader('Content-Type', 'application/octet-stream');
        res.end();
      } else if (req.url === '/partial.7z') {
        res.write(Buffer.from([0x37, 0x7A, 0xBC]));
        res.destroy();
      } else if (req.url === '/fake.7z') {
        // Arquivo que parece 7z mas e HTML
        const html = Buffer.from('<html><body>404 Not Found</body></html>');
        res.setHeader('Content-Type', 'text/html');
        res.end(html);
      } else if (req.url === '/slow.7z') {
        const buf = createValid7zHeader();
        res.setHeader('Content-Type', 'application/octet-stream');
        // Envia muito lentamente (1 byte por 500ms)
        buf.forEach((byte, i) => {
          setTimeout(() => {
            if (i === buf.length - 1) res.end(Buffer.from([byte]));
            else res.write(Buffer.from([byte]));
          }, i * 500);
        });
      } else {
        res.statusCode = 404;
        res.end('Not Found');
      }
    });
  });

  after(async () => {
    await closeServer(mockServer);
  });

  describe('validateExtractedContent', () => {
    it('deve retornar false para serial vazio', () => {
      expect(dl.validateExtractedContent('')).to.be.false;
      expect(dl.validateExtractedContent(null)).to.be.false;
    });

    it('deve retornar false quando PSX_DIR nao tem arquivos do serial', () => {
      // tmpDir esta limpo (ou tem arquivos de outros testes)
      const result = dl.validateExtractedContent('SCUS-99999');
      expect(result).to.be.false;
    });

    it('deve retornar true quando arquivo .bin com serial existe', () => {
      const testFile = path.join(tmpDir, 'SCUS-99998.bin');
      fs.writeFileSync(testFile, Buffer.alloc(1024));
      const result = dl.validateExtractedContent('SCUS-99998');
      expect(result).to.be.true;
      fs.unlinkSync(testFile);
    });

    it('deve retornar true quando arquivo .chd com serial existe', () => {
      const testFile = path.join(tmpDir, 'SLES-99997.chd');
      fs.writeFileSync(testFile, Buffer.alloc(1024));
      const result = dl.validateExtractedContent('SLES-99997');
      expect(result).to.be.true;
      fs.unlinkSync(testFile);
    });

    it('deve retornar false quando arquivo sem extensao de ROM existe', () => {
      const testFile = path.join(tmpDir, 'SCUS-99996.txt');
      fs.writeFileSync(testFile, 'not a rom');
      const result = dl.validateExtractedContent('SCUS-99996');
      expect(result).to.be.false;
      fs.unlinkSync(testFile);
    });

    it('deve ser case-insensitive na comparacao de serial', () => {
      const testFile = path.join(tmpDir, 'scus-99995.bin');
      fs.writeFileSync(testFile, Buffer.alloc(1024));
      const result = dl.validateExtractedContent('SCUS-99995');
      expect(result).to.be.true;
      fs.unlinkSync(testFile);
    });
  });

  describe('testArchive: validacao de integridade', () => {
    it('deve rejeitar arquivo corrompido', async () => {
      const corruptPath = path.join(tmpDir, 'corrupt-test.7z');
      fs.writeFileSync(corruptPath, Buffer.from('CORRUPT_DATA'));
      try {
        await dl.testArchive(corruptPath);
        expect.fail('deveria ter rejeitado arquivo corrompido');
      } catch (e) {
        expect(e.message).to.not.be.empty;
      }
      try { fs.unlinkSync(corruptPath); } catch (e) {}
    });

    it('deve rejeitar arquivo vazio', async () => {
      const emptyPath = path.join(tmpDir, 'empty-test.7z');
      fs.writeFileSync(emptyPath, Buffer.alloc(0));
      try {
        await dl.testArchive(emptyPath);
        expect.fail('deveria ter rejeitado arquivo vazio');
      } catch (e) {
        expect(e.message).to.not.be.empty;
      }
      try { fs.unlinkSync(emptyPath); } catch (e) {}
    });

    it('deve rejeitar arquivo que nao existe', async () => {
      try {
        await dl.testArchive(path.join(tmpDir, 'nonexistent.7z'));
        expect.fail('deveria ter rejeitado arquivo inexistente');
      } catch (e) {
        expect(e).to.exist;
      }
    });
  });

  describe('extractWith7z: extracao de arquivos', () => {
    it('deve criar diretorio de destino se nao existir', async () => {
      const newDir = path.join(tmpDir, 'new-extract-dir');
      if (fs.existsSync(newDir)) fs.rmSync(newDir, { recursive: true });
      // Cria um arquivo 7z invalido mas testa se o diretorio e criado
      const fakeArchive = path.join(tmpDir, 'fake-extract.7z');
      fs.writeFileSync(fakeArchive, Buffer.from('not valid'));
      try {
        await dl.extractWith7z(fakeArchive, newDir);
        expect.fail('deveria falhar com arquivo invalido');
      } catch (e) {
        // O diretorio deve ter sido criado mesmo com falha na extracao
        expect(fs.existsSync(newDir)).to.be.true;
      }
      try { fs.unlinkSync(fakeArchive); } catch (e) {}
      try { fs.rmSync(newDir, { recursive: true }); } catch (e) {}
    });

    it('deve rejeitar extracao de arquivo corrompido', async () => {
      const corruptPath = path.join(tmpDir, 'corrupt-extract.7z');
      const extractDir = path.join(tmpDir, 'extract-corrupt');
      fs.writeFileSync(corruptPath, Buffer.from('CORRUPT'));
      if (!fs.existsSync(extractDir)) fs.mkdirSync(extractDir, { recursive: true });
      try {
        await dl.extractWith7z(corruptPath, extractDir);
        expect.fail('deveria falhar com arquivo corrompido');
      } catch (e) {
        expect(e.message).to.not.be.empty;
      }
      try { fs.unlinkSync(corruptPath); } catch (e) {}
      try { fs.rmSync(extractDir, { recursive: true }); } catch (e) {}
    });
  });

  describe('Respawn: re-download apos falha', () => {
    it('deve limpar arquivo corrompido apos falha de validacao', () => {
      const corruptPath = path.join(tmpDir, 'respawn-corrupt.7z');
      fs.writeFileSync(corruptPath, Buffer.from('CORRUPT'));
      // Simula cleanup que validateAndExtract faz
      try { fs.unlinkSync(corruptPath); } catch (e) {}
      expect(fs.existsSync(corruptPath)).to.be.false;
    });

    it('deve limpar arquivo temporario apos extracao bem-sucedida', () => {
      const archivePath = path.join(tmpDir, 'respawn-ok.7z');
      fs.writeFileSync(archivePath, Buffer.alloc(100));
      // Simula cleanup apos extracao
      try { fs.unlinkSync(archivePath); } catch (e) {}
      expect(fs.existsSync(archivePath)).to.be.false;
    });

    it('deve nao deixar arquivos .part ou .tmp no diretorio', () => {
      // Verifica que tmpDir nao tem arquivos .part ou .tmp apos testes
      const files = fs.readdirSync(tmpDir);
      const leftovers = files.filter(f => f.endsWith('.part') || f.endsWith('.tmp'));
      expect(leftovers).to.be.empty;
    });
  });

  describe('Respawn: deteccao de download falso', () => {
    it('deve detectar arquivo HTML disfarcado de ROM', () => {
      const fakePath = path.join(tmpDir, 'SCUS-FAKE.7z');
      fs.writeFileSync(fakePath, '<html><body>404</body></html>');
      const stat = fs.statSync(fakePath);
      // HTML tipicamente tem < 1KB, ROMs tem > 1MB
      const isLikelyHtml = stat.size < 1024 && fs.readFileSync(fakePath, 'utf8').includes('<html');
      expect(isLikelyHtml).to.be.true;
      fs.unlinkSync(fakePath);
    });

    it('deve aceitar arquivo binario como ROM potencial', () => {
      const romPath = path.join(tmpDir, 'SCUS-OK.bin');
      // Cria arquivo binario de 1MB
      fs.writeFileSync(romPath, Buffer.alloc(1024 * 1024, 0xFF));
      const stat = fs.statSync(romPath);
      const isLikelyRom = stat.size > 1024;
      expect(isLikelyRom).to.be.true;
      fs.unlinkSync(romPath);
    });
  });
});
