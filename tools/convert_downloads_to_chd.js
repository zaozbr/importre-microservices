/**
 * convert_downloads_to_chd.js
 *
 * Converte todas as pastas em F:\downloads para .chd e move para D:\roms\library\roms\psx.
 * Processa em paralelo (max 4 conversões simultâneas com chdman).
 * Após converter, move arquivos originais para D:\roms\duplicados e deleta a pasta temporária.
 *
 * Uso: node tools/convert_downloads_to_chd.js
 */
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');

const DOWNLOADS_DIR = 'F:\\downloads';
const ROM_DIR = 'D:\\roms\\library\\roms\\psx';
const DUPLICADOS_DIR = 'D:\\roms\\duplicados';
const CHDMAN = 'F:\\importre\\chdman.exe';
const MAX_PARALLEL = 4;

if (!fs.existsSync(DUPLICADOS_DIR)) fs.mkdirSync(DUPLICADOS_DIR, { recursive: true });

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
  const subdirs = files.filter(f => fs.statSync(path.join(dir, f)).isDirectory());
  const result = [];
  for (const sd of subdirs) {
    const sub = path.join(dir, sd);
    const subFiles = fs.readdirSync(sub);
    const subCues = subFiles.filter(f => f.toLowerCase().endsWith('.cue'));
    const subIsos = subFiles.filter(f => f.toLowerCase().endsWith('.iso'));
    const subBins = subFiles.filter(f => f.toLowerCase().endsWith('.bin'));
    if (subCues.length > 0) result.push(...subCues.map(f => path.join(sub, f)));
    else if (subIsos.length > 0) result.push(...subIsos.map(f => path.join(sub, f)));
    else if (subBins.length > 0) {
      // Gerar .cue para .bin em subpasta
      for (const bin of subBins) {
        const cuePath = path.join(sub, bin.replace(/\.bin$/i, '.cue'));
        if (!fs.existsSync(cuePath)) {
          fs.writeFileSync(cuePath, `FILE "${bin}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`);
        }
        result.push(cuePath);
      }
    }
  }
  return result;
}

// Corrigir .cue que referencia arquivo inexistente (.img quando so existe .bin)
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
      const refPath = path.join(dir, refFile);
      if (!fs.existsSync(refPath)) {
        // Procurar arquivo com extensao diferente
        const baseName = refFile.replace(/\.(img|bin|iso)$/i, '');
        const altBin = path.join(dir, baseName + '.bin');
        const altImg = path.join(dir, baseName + '.img');
        const altIso = path.join(dir, baseName + '.iso');
        if (fs.existsSync(altBin)) {
          content = content.replace(refFile, path.basename(altBin));
          changed = true;
        } else if (fs.existsSync(altImg)) {
          content = content.replace(refFile, path.basename(altImg));
          changed = true;
        } else if (fs.existsSync(altIso)) {
          content = content.replace(refFile, path.basename(altIso));
          changed = true;
        }
      }
    }
    if (changed) {
      fs.writeFileSync(cuePath, content);
    }
  } catch {}
}

function convertToChd(cuePath, chdPath) {
  return new Promise((resolve, reject) => {
    const args = ['createcd', '-i', cuePath, '-o', chdPath, '-c', 'none'];
    execFile(CHDMAN, args, { timeout: 600000, maxBuffer: 1024 * 1024 }, (err) => {
      if (err) {
        // Tentar com force flag
        execFile(CHDMAN, [...args, '-f'], { timeout: 600000, maxBuffer: 1024 * 1024 }, (err2) => {
          if (err2) reject(err2);
          else resolve();
        });
      } else {
        resolve();
      }
    });
  });
}

async function processFolder(folderName) {
  const folderPath = path.join(DOWNLOADS_DIR, folderName);
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
    const chdPath = path.join(ROM_DIR, chdName);

    // Se CHD já existe, pular
    if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 0) {
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
      await convertToChd(romPath, chdPath);

      // Verificar se CHD foi criado
      if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 0) {
        console.log(`[OK] ${chdName} (${(fs.statSync(chdPath).size / 1048576).toFixed(0)}MB)`);
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

  // Se pelo menos 1 CHD foi criado com sucesso, mover originais para duplicados
  const successCount = results.filter(r => r.status === 'ok' || r.status === 'exists').length;
  if (successCount > 0 && successCount === romFiles.length) {
    try {
      const destDir = path.join(DUPLICADOS_DIR, folderName);
      if (!fs.existsSync(destDir)) fs.mkdirSync(destDir, { recursive: true });
      // Mover todos arquivos da pasta original
      const allFiles = fs.readdirSync(folderPath);
      for (const f of allFiles) {
        const src = path.join(folderPath, f);
        const dst = path.join(destDir, f);
        try { fs.renameSync(src, dst); } catch { fs.copyFileSync(src, dst); fs.unlinkSync(src); }
      }
      // Deletar pasta original vazia
      try { fs.rmdirSync(folderPath, { recursive: true }); } catch {}
      console.log(`[CLEAN] ${folderName}: originais movidos para duplicados, pasta removida`);
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
