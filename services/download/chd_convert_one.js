/**
 * chd_convert_one.js — Converte uma pasta isolada para .chd (one-shot)
 *
 * Uso: node chd_convert_one.js <dir> <serial>
 *
 * Faz:
 * 1. Extrai arquivos compactados se houver
 * 2. Converte .cue+.bin / .bin orfao / .img para .chd
 * 3. Move .chd para D:\roms\library\roms\psx
 * 4. Move arquivos de origem para D:\roms\duplicados
 * 5. Apaga pasta de conversao
 *
 * Sai com codigo 0 se OK, 1 se erro.
 */
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { PSX_DIR, DUP_DIR, CHDMAN_PATH } = require('../../shared/config');

const SEVEN_ZIP = process.env.SEVEN_ZIP_PATH || 'C:\\Program Files\\7-Zip\\7z.exe';

function log(msg) {
  console.log(`[${new Date().toISOString()}] [chd-convert] ${msg}`);
}

function convertCueToChd(cuePath, chdPath) {
  return new Promise((resolve) => {
    const proc = spawn(CHDMAN_PATH, ['createcd', '-i', cuePath, '-o', chdPath, '-f'], {
      cwd: path.dirname(cuePath),
      windowsHide: true,
    });
    let stderr = '';
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => resolve({ success: code === 0, error: stderr }));
    proc.on('error', (e) => resolve({ success: false, error: e.message }));
  });
}

function getBinsFromCue(cuePath) {
  const content = fs.readFileSync(cuePath, 'utf-8');
  const bins = [];
  const dir = path.dirname(cuePath);
  for (const line of content.split('\n')) {
    const match = line.match(/FILE\s+"([^"]+)"/i);
    if (match) {
      const binPath = path.join(dir, match[1]);
      if (fs.existsSync(binPath)) bins.push(binPath);
    }
  }
  return bins;
}

function generateCueForBin(binPath) {
  const cuePath = binPath.replace(/\.bin$/i, '.cue');
  const binName = path.basename(binPath);
  fs.writeFileSync(cuePath, `FILE "${binName}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`);
  return cuePath;
}

function moveToDuplicados(filePath) {
  if (!fs.existsSync(filePath)) return;
  if (!fs.existsSync(DUP_DIR)) fs.mkdirSync(DUP_DIR, { recursive: true });
  const name = path.basename(filePath);
  let dest = path.join(DUP_DIR, name);
  let counter = 1;
  while (fs.existsSync(dest)) {
    const ext = path.extname(name);
    const base = path.basename(name, ext);
    dest = path.join(DUP_DIR, `${base}_${counter}${ext}`);
    counter++;
  }
  try {
    fs.renameSync(filePath, dest);
  } catch {
    try { fs.copyFileSync(filePath, dest); fs.unlinkSync(filePath); } catch {}
  }
}

function extractArchive(archPath, destDir) {
  return new Promise((resolve) => {
    const proc = spawn(SEVEN_ZIP, ['x', '-y', `-o${destDir}`, archPath], { cwd: destDir, windowsHide: true });
    let stderr = '';
    proc.stderr.on('data', (d) => { stderr += d.toString(); });
    proc.on('close', (code) => resolve({ success: code === 0, error: stderr }));
    proc.on('error', (e) => resolve({ success: false, error: e.message }));
  });
}

// Descomprimir ECM (Error Code Modeler) para binario raw
// Baseado no codigo C de Neill Corlett (unecm.c v1.0)
// Formato ECM: header "ECM\0" + records (type+num varint) + EDC final
const ecc_f_lut = new Uint8Array(256);
const ecc_b_lut = new Uint8Array(256);
const edc_lut = new Uint32Array(256);

function eccedc_init() {
  for (let i = 0; i < 256; i++) {
    const j = (i << 1) ^ (i & 0x80 ? 0x11D : 0);
    ecc_f_lut[i] = j & 0xFF;
    ecc_b_lut[i ^ j] = i & 0xFF;
    let edc = i;
    for (let k = 0; k < 8; k++) {
      edc = (edc >>> 1) ^ (edc & 1 ? 0xD8018001 : 0);
    }
    edc_lut[i] = edc >>> 0;
  }
}

eccedc_init();

function edc_partial_computeblock(edc, src, size) {
  let result = edc >>> 0;
  for (let i = 0; i < size; i++) {
    result = (result >>> 8) ^ edc_lut[(result ^ src[i]) & 0xFF];
  }
  return result >>> 0;
}

function ecc_computeblock(src, major_count, minor_count, major_mult, minor_inc, dest) {
  const size = major_count * minor_count;
  for (let major = 0; major < major_count; major++) {
    let index = (major >> 1) * major_mult + (major & 1);
    let ecc_a = 0;
    let ecc_b = 0;
    for (let minor = 0; minor < minor_count; minor++) {
      const temp = src[index];
      index += minor_inc;
      if (index >= size) index -= size;
      ecc_a ^= temp;
      ecc_b ^= temp;
      ecc_a = ecc_f_lut[ecc_a];
    }
    ecc_a = ecc_b_lut[ecc_f_lut[ecc_a] ^ ecc_b];
    dest[major] = ecc_a;
    dest[major + major_count] = ecc_a ^ ecc_b;
  }
}

function ecc_generate(sector, zeroaddress) {
  const address = [0, 0, 0, 0];
  if (zeroaddress) {
    for (let i = 0; i < 4; i++) {
      address[i] = sector[12 + i];
      sector[12 + i] = 0;
    }
  }
  // ECC P code: dest = sector + 0x81C
  ecc_computeblock(sector.subarray(0xC), 86, 24, 2, 86, sector.subarray(0x81C));
  // ECC Q code: dest = sector + 0x8C8
  ecc_computeblock(sector.subarray(0xC), 52, 43, 86, 88, sector.subarray(0x8C8));
  if (zeroaddress) {
    for (let i = 0; i < 4; i++) sector[12 + i] = address[i];
  }
}

function eccedc_generate(sector, type) {
  switch (type) {
    case 1: // Mode 1
      edc_computeblock(sector.subarray(0x00), 0x810, sector.subarray(0x810));
      for (let i = 0; i < 8; i++) sector[0x814 + i] = 0;
      ecc_generate(sector, 0);
      break;
    case 2: // Mode 2 form 1
      edc_computeblock(sector.subarray(0x10), 0x808, sector.subarray(0x818));
      ecc_generate(sector, 1);
      break;
    case 3: // Mode 2 form 2
      edc_computeblock(sector.subarray(0x10), 0x91C, sector.subarray(0x92C));
      break;
  }
}

function edc_computeblock(src, size, dest) {
  const edc = edc_partial_computeblock(0, src, size);
  dest[0] = (edc >>> 0) & 0xFF;
  dest[1] = (edc >>> 8) & 0xFF;
  dest[2] = (edc >>> 16) & 0xFF;
  dest[3] = (edc >>> 24) & 0xFF;
}

function readEcmRecord(data, i) {
  let pos = i;
  let c = data[pos]; pos++;
  let bits = 5;
  const type = c & 3;
  let num = (c >> 2) & 0x1F;
  while (c & 0x80) {
    c = data[pos]; pos++;
    num |= (c & 0x7F) << bits;
    bits += 7;
  }
  if (num === 0xFFFFFFFF) return null;
  num++;
  if (num >= 0x80000000) throw new Error('ECM corrupto: num muito grande');
  return { type, num, nextI: pos };
}

function processRawChunks(data, i, num, chunks, checkedc) {
  let pos = i;
  let remaining = num;
  let edc = checkedc;
  while (remaining > 0) {
    let b = remaining;
    if (b > 2352) b = 2352;
    const raw = data.subarray(pos, pos + b);
    edc = edc_partial_computeblock(edc, raw, b);
    chunks.push(Buffer.from(raw));
    pos += b;
    remaining -= b;
  }
  return { nextI: pos, checkedc: edc };
}

function processSectorChunk(data, i, type, sector, chunks, checkedc) {
  let pos = i;
  let edc = checkedc;
  sector.fill(0);
  sector[0] = 0x00;
  for (let k = 1; k <= 10; k++) sector[k] = 0xFF;
  sector[11] = 0x00;
  switch (type) {
    case 1: // Mode 1
      sector[0x0F] = 0x01;
      sector.set(data.subarray(pos, pos + 0x003), 0x00C); pos += 0x003;
      sector.set(data.subarray(pos, pos + 0x800), 0x010); pos += 0x800;
      eccedc_generate(sector, 1);
      edc = edc_partial_computeblock(edc, sector, 2352);
      chunks.push(Buffer.from(sector));
      break;
    case 2: // Mode 2 form 1
      sector[0x0F] = 0x02;
      sector.set(data.subarray(pos, pos + 0x804), 0x014); pos += 0x804;
      sector[0x10] = sector[0x14];
      sector[0x11] = sector[0x15];
      sector[0x12] = sector[0x16];
      sector[0x13] = sector[0x17];
      eccedc_generate(sector, 2);
      edc = edc_partial_computeblock(edc, sector.subarray(0x10), 2336);
      chunks.push(Buffer.from(sector.subarray(0x10, 0x10 + 2336)));
      break;
    case 3: // Mode 2 form 2
      sector[0x0F] = 0x02;
      sector.set(data.subarray(pos, pos + 0x918), 0x014); pos += 0x918;
      sector[0x10] = sector[0x14];
      sector[0x11] = sector[0x15];
      sector[0x12] = sector[0x16];
      sector[0x13] = sector[0x17];
      eccedc_generate(sector, 3);
      edc = edc_partial_computeblock(edc, sector.subarray(0x10), 2336);
      chunks.push(Buffer.from(sector.subarray(0x10, 0x10 + 2336)));
      break;
  }
  return { nextI: pos, checkedc: edc };
}

function verifyFinalEdc(data, i, checkedc) {
  if (i + 4 > data.length) return;
  const edcBytes = data.subarray(i, i + 4);
  const expected = [
    (checkedc >>> 0) & 0xFF,
    (checkedc >>> 8) & 0xFF,
    (checkedc >>> 16) & 0xFF,
    (checkedc >>> 24) & 0xFF
  ];
  if (edcBytes[0] !== expected[0] || edcBytes[1] !== expected[1] ||
      edcBytes[2] !== expected[2] || edcBytes[3] !== expected[3]) {
    log(`  Aviso: EDC mismatch (esperado ${expected.join(',')}, obtido ${Array.from(edcBytes).join(',')})`);
  }
}

function unecm(data) {
  // Verificar header "ECM\0"
  if (data[0] !== 0x45 || data[1] !== 0x43 || data[2] !== 0x4D || data[3] !== 0x00) {
    throw new Error('Header ECM nao encontrado');
  }

  const chunks = [];
  let checkedc = 0;
  let i = 4;
  const sector = new Uint8Array(2352);

  while (i < data.length) {
    const record = readEcmRecord(data, i);
    if (!record) break;
    i = record.nextI;

    if (record.type === 0) {
      // Tipo 0: dados raw, sem setores
      const result = processRawChunks(data, i, record.num, chunks, checkedc);
      i = result.nextI;
      checkedc = result.checkedc;
    } else {
      // Tipos 1, 2, 3: setores com ECC/EDC regenerados
      let num = record.num;
      while (num > 0) {
        const result = processSectorChunk(data, i, record.type, sector, chunks, checkedc);
        i = result.nextI;
        checkedc = result.checkedc;
        num--;
      }
    }
  }

  // Verificar EDC final
  verifyFinalEdc(data, i, checkedc);

  return Buffer.concat(chunks);
}

async function extractArchives(dir) {
  // 1. Extrair arquivos compactados
  const archives = fs.readdirSync(dir).filter(f => /\.(7z|zip|rar)$/i.test(f));
  for (const arch of archives) {
    const archPath = path.join(dir, arch);
    log(`  Extraindo: ${arch}`);
    const result = await extractArchive(archPath, dir);
    if (result.success) {
      try { fs.unlinkSync(archPath); } catch {}
      log(`  Extraido: ${arch}`);
    } else {
      log(`  Erro ao extrair: ${arch}`);
    }
  }
}

function decompressEcmFiles(dir) {
  // 1b. Descomprimir arquivos .ecm para .bin (ECM = Error Code Modeler)
  const ecmFiles = fs.readdirSync(dir).filter(f => /\.ecm$/i.test(f));
  for (const ecm of ecmFiles) {
    const ecmPath = path.join(dir, ecm);
    // Remover .ecm e garantir extensao .bin (ou .img se o nome original tinha .img)
    let binPath = ecmPath.replace(/\.ecm$/i, '');
    const ext = path.extname(binPath).toLowerCase();
    if (ext !== '.bin' && ext !== '.img' && ext !== '.iso') {
      binPath = binPath + '.bin';
    }
    log(`  Descomprimindo ECM: ${ecm}`);
    try {
      const ecmData = fs.readFileSync(ecmPath);
      const binData = unecm(ecmData);
      fs.writeFileSync(binPath, binData);
      fs.unlinkSync(ecmPath);
      log(`  ECM descomprimido: ${ecm} -> ${path.basename(binPath)} (${Math.round(binData.length / 1048576)}MB)`);
    } catch (e) {
      log(`  Erro ao descomprimir ECM: ${ecm} - ${e.message}`);
    }
  }
}

async function convertCueBins(dir, chdFiles) {
  // 2. Converter .cue + .bin para .chd
  const cueFiles = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.cue'));
  for (const cue of cueFiles) {
    const cuePath = path.join(dir, cue);
    const bins = getBinsFromCue(cuePath);
    if (!bins.length) continue;

    const stem = path.basename(cue, '.cue');
    const chdName = stem.replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') + '.chd';
    const chdPath = path.join(dir, chdName);

    if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
      chdFiles.push(chdPath);
      continue;
    }

    log(`  Convertendo: ${cue} -> ${chdName}`);
    const result = await convertCueToChd(cuePath, chdPath);
    if (result.success && fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
      chdFiles.push(chdPath);
      log(`  OK: ${chdName} (${Math.round(fs.statSync(chdPath).size / 1048576)}MB)`);
    } else {
      log(`  Falhou: ${cue}`);
    }
  }
}

async function convertOrphanBins(dir, chdFiles) {
  // 3. Converter .bin orfaos
  const binFiles = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.bin'));
  for (const bin of binFiles) {
    const binPath = path.join(dir, bin);
    const cuePath = binPath.replace(/\.bin$/i, '.cue');
    if (fs.existsSync(cuePath)) continue;
    if (fs.statSync(binPath).size < 1048576) continue;

    const tmpCue = generateCueForBin(binPath);
    const stem = path.basename(bin, '.bin');
    const chdName = stem.replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') + '.chd';
    const chdPath = path.join(dir, chdName);

    if (fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
      chdFiles.push(chdPath);
      try { fs.unlinkSync(tmpCue); } catch {}
      continue;
    }

    log(`  Convertendo .bin orfao: ${bin}`);
    const result = await convertCueToChd(tmpCue, chdPath);
    if (result.success && fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
      chdFiles.push(chdPath);
      log(`  OK: ${chdName}`);
    }
    try { fs.unlinkSync(tmpCue); } catch {}
  }
}

async function convertImgFiles(dir, chdFiles) {
  // 4. Converter .img
  const imgFiles = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.img'));
  for (const img of imgFiles) {
    const imgPath = path.join(dir, img);
    if (fs.statSync(imgPath).size < 1048576) continue;
    const cuePath = imgPath.replace(/\.img$/i, '.cue');
    fs.writeFileSync(cuePath, `FILE "${img}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`);
    const stem = path.basename(img, '.img');
    const chdName = stem.replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '') + '.chd';
    const chdPath = path.join(dir, chdName);
    log(`  Convertendo .img: ${img}`);
    const result = await convertCueToChd(cuePath, chdPath);
    if (result.success && fs.existsSync(chdPath) && fs.statSync(chdPath).size > 1048576) {
      chdFiles.push(chdPath);
    }
    try { fs.unlinkSync(cuePath); } catch {}
  }
}

function includeExistingChds(dir, chdFiles) {
  // 5. Incluir .chd ja existentes
  const existingChds = fs.readdirSync(dir).filter(f => f.toLowerCase().endsWith('.chd'));
  for (const chd of existingChds) {
    const chdPath = path.join(dir, chd);
    if (fs.statSync(chdPath).size > 1048576 && !chdFiles.includes(chdPath)) {
      chdFiles.push(chdPath);
    }
  }
}

function moveChdsToPsx(chdFiles) {
  // 6. Mover .chd para PSX_DIR
  for (const chdFile of chdFiles) {
    const chdDest = path.join(PSX_DIR, path.basename(chdFile));
    try {
      if (fs.existsSync(chdDest)) moveToDuplicados(chdDest);
      fs.renameSync(chdFile, chdDest);
      log(`  CHD movido: ${path.basename(chdFile)}`);
    } catch {
      try { fs.copyFileSync(chdFile, chdDest); fs.unlinkSync(chdFile); } catch {}
    }
  }
}

function moveOriginsToDups(dir) {
  // 7. Mover origens para duplicados
  const originExts = ['.bin', '.cue', '.img', '.ccd', '.sub', '.mdf', '.mds', '.ecm', '.iso', '.ape'];
  for (const f of fs.readdirSync(dir)) {
    const fp = path.join(dir, f);
    if (fs.statSync(fp).isFile()) {
      const ext = path.extname(f).toLowerCase();
      if (originExts.includes(ext) || ext === '.zip' || ext === '.7z' || ext === '.rar') {
        moveToDuplicados(fp);
      }
    }
  }
}

async function main() {
  const dir = process.argv[2];
  const serial = process.argv[3] || path.basename(dir);

  if (!dir || !fs.existsSync(dir)) {
    log(`Pasta nao encontrada: ${dir}`);
    process.exit(1);
  }

  log(`Iniciando conversao: ${serial} (${dir})`);

  try {
    await extractArchives(dir);
    decompressEcmFiles(dir);

    const chdFiles = [];
    await convertCueBins(dir, chdFiles);
    await convertOrphanBins(dir, chdFiles);
    await convertImgFiles(dir, chdFiles);
    includeExistingChds(dir, chdFiles);
    moveChdsToPsx(chdFiles);
    moveOriginsToDups(dir);

    // 8. Apagar pasta de conversao
    try { fs.rmSync(dir, { recursive: true, force: true }); } catch {}
    log(`Concluido: ${serial} (${chdFiles.length} CHDs)`);
    process.exit(0);

  } catch (e) {
    log(`ERRO: ${e.message}`);
    process.exit(1);
  }
}

main();
