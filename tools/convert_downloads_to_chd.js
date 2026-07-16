/**
 * convert_downloads_to_chd.js
 *
 * Converte todas as pastas em F:\downloads para .chd e move para D:\roms\library\roms\psx.
 * Fluxo: descomprimir .ecm (no F:) -> chdman gera .chd temp (no F:) -> mover .chd para D: -> limpar F:.
 * Processa em paralelo (max 12 conversões simultâneas com chdman).
 *
 * Uso: node tools/convert_downloads_to_chd.js
 */
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const { decodeEcmStream, eccedcInit } = require('./unecm.js');

const DOWNLOADS_DIR = 'F:\\downloads';
const ROM_DIR = 'D:\\roms\\library\\roms\\psx';
const CHD_TEMP_DIR = 'F:\\chd_temp';
const CHDMAN = 'F:\\importre\\chdman.exe';
const MAX_PARALLEL = 12;

if (!fs.existsSync(CHD_TEMP_DIR)) fs.mkdirSync(CHD_TEMP_DIR, { recursive: true });
eccedcInit();

// Descomprimir todos os .ecm de uma pasta para .bin/.img (no proprio F:)
async function decompressEcms(dir) {
  const allFiles = fs.readdirSync(dir, { withFileTypes: true });
  const ecms = [];
  function scan(d, prefix) {
    for (const entry of allFiles) {
      // so top-level por enquanto
    }
  }
  // Buscar .ecm na raiz e em subpastas
  function findEcms(d) {
    const items = fs.readdirSync(d, { withFileTypes: true });
    const result = [];
    for (const item of items) {
      const fullPath = path.join(d, item.name);
      if (item.isDirectory()) {
        result.push(...findEcms(fullPath));
      } else if (item.name.toLowerCase().endsWith('.ecm')) {
        result.push(fullPath);
      }
    }
    return result;
  }
  const ecmFiles = findEcms(dir);
  for (const ecmPath of ecmFiles) {
    const outPath = ecmPath.replace(/\.ecm$/i, '');
    if (fs.existsSync(outPath)) {
      // Ja descomprimido, deletar .ecm
      fs.unlinkSync(ecmPath);
      continue;
    }
    const ecmSize = fs.statSync(ecmPath).size;
    console.log(`[ECM] Descomprimindo ${path.basename(ecmPath)} (${(ecmSize / 1048576).toFixed(0)}MB)`);
    try {
      await decodeEcmStream(ecmPath, outPath);
      // Deletar .ecm apos descomprimir com sucesso
      fs.unlinkSync(ecmPath);
      console.log(`[ECM-OK] ${path.basename(outPath)} descomprimido`);
    } catch (e) {
      console.log(`[ECM-ERROR] ${path.basename(ecmPath)}: ${e.message}`);
      // Deletar saida parcial se existir
      try { if (fs.existsSync(outPath)) fs.unlinkSync(outPath); } catch {}
    }
  }
}

function findRomFiles(dir) {
  const files = fs.readdirSync(dir);
  // Procurar .cue+bin, .iso, ou .bin direto
  const cues = files.filter(f => f.toLowerCase().endsWith('.cue'));
  const isos = files.filter(f => f.toLowerCase().endsWith('.iso'));
  const bins = files.filter(f => f.toLowerCase().endsWith('.bin'));
  const imgs = files.filter(f => f.toLowerCase().endsWith('.img'));
  if (cues.length > 0) return cues.map(f => path.join(dir, f));
  if (isos.length > 0) return isos.map(f => path.join(dir, f));
  // .bin sem .cue: gerar .cue
  if (bins.length > 0 && cues.length === 0) {
    const generated = [];
    for (const bin of bins) {
      const cuePath = path.join(dir, bin.replace(/\.bin$/i, '.cue'));
      if (!fs.existsSync(cuePath)) {
        const binName = bin;
        const cueContent = `FILE "${binName}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`;
        fs.writeFileSync(cuePath, cueContent);
      }
      generated.push(cuePath);
    }
    return generated;
  }
  // .img sem .cue: gerar .cue
  if (imgs.length > 0 && cues.length === 0) {
    const generated = [];
    for (const img of imgs) {
      const cuePath = path.join(dir, img.replace(/\.img$/i, '.cue'));
      if (!fs.existsSync(cuePath)) {
        const cueContent = `FILE "${img}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`;
        fs.writeFileSync(cuePath, cueContent);
      }
      generated.push(cuePath);
    }
    return generated;
  }
  // Procurar em subpastas (discos)
  const subdirs = files.filter(f => {
    try { return fs.statSync(path.join(dir, f)).isDirectory(); } catch { return false; }
  });
  const result = [];
  for (const sd of subdirs) {
    const sub = path.join(dir, sd);
    const subFiles = fs.readdirSync(sub);
    const subCues = subFiles.filter(f => f.toLowerCase().endsWith('.cue'));
    const subIsos = subFiles.filter(f => f.toLowerCase().endsWith('.iso'));
    const subBins = subFiles.filter(f => f.toLowerCase().endsWith('.bin'));
    const subImgs = subFiles.filter(f => f.toLowerCase().endsWith('.img'));
    if (subCues.length > 0) result.push(...subCues.map(f => path.join(sub, f)));
    else if (subIsos.length > 0) result.push(...subIsos.map(f => path.join(sub, f)));
    else if (subBins.length > 0) {
      for (const bin of subBins) {
        const cuePath = path.join(sub, bin.replace(/\.bin$/i, '.cue'));
        if (!fs.existsSync(cuePath)) {
          fs.writeFileSync(cuePath, `FILE "${bin}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`);
        }
        result.push(cuePath);
      }
    } else if (subImgs.length > 0) {
      for (const img of subImgs) {
        const cuePath = path.join(sub, img.replace(/\.img$/i, '.cue'));
        if (!fs.existsSync(cuePath)) {
          fs.writeFileSync(cuePath, `FILE "${img}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`);
        }
        result.push(cuePath);
      }
    }
  }
  return result;
}

// Corrigir .cue que referencia arquivo inexistente (path absoluto, extensao errada, etc)
function fixCueReferences(cuePath) {
  try {
    let content = fs.readFileSync(cuePath, 'utf8');
    const dir = path.dirname(cuePath);
    // Procurar referencias FILE "xxx" BINARY
    const refs = content.match(/FILE\s+"([^"]+)"\s+BINARY/gi) || [];
    let changed = false;
    for (const ref of refs) {
      const m = ref.match(/FILE\s+"([^"]+)"/i);
      if (!m) continue;
      const refFile = m[1];
      // Se for path absoluto (C:\..., D:\..., L:\..., etc), sempre substituir
      const isAbsolute = /^[A-Za-z]:[\\/]/.test(refFile) || refFile.startsWith('/');
      const baseName = path.basename(refFile);
      const refPath = path.join(dir, baseName);
      if (isAbsolute || !fs.existsSync(refPath)) {
        // Listar todos arquivos .bin/.img/.iso na pasta
        const allFiles = fs.readdirSync(dir);
        const candidates = allFiles.filter(f => /\.(bin|img|iso)$/i.test(f));
        // Tentar match por nome base (sem extensao)
        const wantedBase = baseName.replace(/\.(img|bin|iso)$/i, '').toLowerCase();
        let found = candidates.find(f => {
          const fb = f.replace(/\.(bin|img|iso)$/i, '').toLowerCase();
          return fb === wantedBase;
        });
        // Se nao encontrou por nome exato, usar o unico .bin/.img disponivel
        if (!found && candidates.length === 1) {
          found = candidates[0];
        }
        // Se ainda nao encontrou, tentar por similaridade (primeiros 10 chars)
        if (!found && wantedBase.length > 5) {
          found = candidates.find(f => {
            const fb = f.replace(/\.(bin|img|iso)$/i, '').toLowerCase();
            return fb.startsWith(wantedBase.substring(0, 10)) || wantedBase.startsWith(fb.substring(0, 10));
          });
        }
        if (found) {
          content = content.replace(refFile, found);
          changed = true;
        }
      }
    }
    if (changed) {
      fs.writeFileSync(cuePath, content);
    }
  } catch {}
}

// Converter para .chd temporario no F: e depois mover para D:
async function convertToChd(cuePath, chdFinalPath) {
  const chdName = path.basename(chdFinalPath);
  const chdTempPath = path.join(CHD_TEMP_DIR, chdName);

  return new Promise((resolve, reject) => {
    const args = ['createcd', '-i', cuePath, '-o', chdTempPath, '-c', 'none'];
    execFile(CHDMAN, args, { timeout: 600000, maxBuffer: 1024 * 1024 }, (err) => {
      if (err) {
        // Tentar com force flag
        execFile(CHDMAN, [...args, '-f'], { timeout: 600000, maxBuffer: 1024 * 1024 }, async (err2) => {
          if (err2) {
            // Limpar .chd temp se existir
            try { if (fs.existsSync(chdTempPath)) fs.unlinkSync(chdTempPath); } catch {}
            reject(err2);
          } else {
            await moveChdToDest(chdTempPath, chdFinalPath);
            resolve();
          }
        });
      } else {
        moveChdToDest(chdTempPath, chdFinalPath).then(resolve).catch(reject);
      }
    });
  });
}

// Mover .chd do temp (F:) para destino (D:) - copia + delete (cross-device)
async function moveChdToDest(chdTempPath, chdFinalPath) {
  if (!fs.existsSync(chdTempPath) || fs.statSync(chdTempPath).size === 0) {
    throw new Error('CHD temporario nao foi criado ou esta vazio');
  }
  // fs.rename nao funciona entre drives diferentes - usar copy + unlink
  fs.copyFileSync(chdTempPath, chdFinalPath);
  fs.unlinkSync(chdTempPath);
}

async function processFolder(folderName) {
  const folderPath = path.join(DOWNLOADS_DIR, folderName);

  // 1. Descomprimir .ecm primeiro (no F:)
  await decompressEcms(folderPath);

  // 2. Encontrar ROMs
  const romFiles = findRomFiles(folderPath);

  if (romFiles.length === 0) {
    console.log(`[SKIP] ${folderName}: nenhum ROM encontrado`);
    return { name: folderName, status: 'skip', reason: 'no rom' };
  }

  const results = [];
  for (let i = 0; i < romFiles.length; i++) {
    const romPath = romFiles[i];
    const ext = path.extname(romPath);
    const baseName = path.basename(romPath, ext);

    // Nome do CHD: se multi-disc, adicionar _discN
    let chdName;
    if (romFiles.length > 1) {
      chdName = `${folderName}_disc${i + 1}.chd`;
    } else {
      chdName = `${folderName}.chd`;
    }
    const chdFinalPath = path.join(ROM_DIR, chdName);

    // Se CHD já existe, pular
    if (fs.existsSync(chdFinalPath) && fs.statSync(chdFinalPath).size > 0) {
      console.log(`[EXISTS] ${chdName} já existe`);
      results.push({ chd: chdName, status: 'exists' });
      continue;
    }

    try {
      console.log(`[CONVERT] ${folderName} -> ${chdName} (${i + 1}/${romFiles.length})`);
      // Corrigir referencias do .cue antes de converter
      if (romPath.toLowerCase().endsWith('.cue')) {
        fixCueReferences(romPath);
      }
      // chdman gera no F: temp, depois move para D:
      await convertToChd(romPath, chdFinalPath);

      // Verificar se CHD foi criado em D:
      if (fs.existsSync(chdFinalPath) && fs.statSync(chdFinalPath).size > 0) {
        console.log(`[OK] ${chdName} (${(fs.statSync(chdFinalPath).size / 1048576).toFixed(0)}MB)`);
        results.push({ chd: chdName, status: 'ok' });
      } else {
        console.log(`[FAIL] ${chdName} não foi criado`);
        results.push({ chd: chdName, status: 'fail' });
      }
    } catch (e) {
      console.log(`[ERROR] ${chdName}: ${e.message}`);
      results.push({ chd: chdName, status: 'error', error: e.message });
    }
  }

  // Se pelo menos 1 CHD foi criado com sucesso, DELETAR originais (liberar espaco no F:)
  const successCount = results.filter(r => r.status === 'ok' || r.status === 'exists').length;
  if (successCount > 0 && successCount === romFiles.length) {
    try {
      fs.rmSync(folderPath, { recursive: true, force: true });
      console.log(`[CLEAN] ${folderName}: originais deletados, pasta removida`);
    } catch (e) {
      console.log(`[CLEAN-ERROR] ${folderName}: ${e.message}`);
    }
  }

  return { name: folderName, results };
}

async function runQueue(queue, parallel) {
  const results = [];
  let idx = 0;
  async function worker() {
    while (idx < queue.length) {
      const i = idx++;
      const folder = queue[i];
      try {
        const r = await processFolder(folder);
        results.push(r);
      } catch (e) {
        results.push({ name: folder, error: e.message });
      }
    }
  }
  const workers = Array.from({ length: parallel }, () => worker());
  await Promise.all(workers);
  return results;
}

(async () => {
  console.log('=== Converter F:\\downloads para CHD ===');
  const allDirs = fs.readdirSync(DOWNLOADS_DIR, { withFileTypes: true })
    .filter(d => d.isDirectory() && d.name !== 'torrents')
    .map(d => d.name);

  console.log(`Pastas para processar: ${allDirs.length}`);
  console.log(`Paralelismo: ${MAX_PARALLEL}`);
  console.log(`Destino: ${ROM_DIR}`);
  console.log('');

  const results = await runQueue(allDirs, MAX_PARALLEL);

  // Resumo
  let ok = 0, exists = 0, fail = 0, skip = 0, error = 0;
  for (const r of results) {
    if (r.results) {
      for (const sub of r.results) {
        if (sub.status === 'ok') ok++;
        else if (sub.status === 'exists') exists++;
        else if (sub.status === 'fail') fail++;
        else if (sub.status === 'error') error++;
      }
    } else if (r.status === 'skip') skip++;
  }

  console.log('\n=== Resumo ===');
  console.log(`Convertidos: ${ok}`);
  console.log(`Já existiam: ${exists}`);
  console.log(`Falhas: ${fail}`);
  console.log(`Erros: ${error}`);
  console.log(`Pulados: ${skip}`);
  console.log(`Total pastas: ${results.length}`);
})();
