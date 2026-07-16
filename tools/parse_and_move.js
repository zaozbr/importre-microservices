const fs = require('fs');
const path = require('path');

const content = fs.readFileSync('F:\\importre\\tools\\broken_chds2.txt', 'utf8');
const lines = content.split(/\r\n|\r|\n/);
console.log('Total linhas do log:', lines.length);

// Percorrer TODAS as linhas. Para cada linha, track do ultimo "Scanning"
// e identificar erros:
// - "Failed to open disc image" -> CHD nao abre
// - "invalid file" -> CHD invalido
// - "Failed to read executable" -> exe ilegivel (CHD abre mas disco com problema)
const broken = new Set();
let lastScan = null;
let errorCount = 0;

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];

  // Atualizar ultimo scan
  const sm = line.match(/Scanning '([^']+)'/i);
  if (sm) {
    lastScan = sm[1];
    continue;
  }

  // Erro: Failed to open disc image
  if (/Failed to open disc image/i.test(line)) {
    errorCount++;
    // O nome do arquivo pode estar na propria linha ou no lastScan
    const m = line.match(/Failed to open disc image '([^']+)'/i);
    if (m) {
      broken.add(path.basename(m[1]));
    } else if (lastScan) {
      broken.add(path.basename(lastScan));
    }
    continue;
  }

  // Erro: invalid file
  if (/invalid file/i.test(line)) {
    errorCount++;
    if (lastScan) broken.add(path.basename(lastScan));
    continue;
  }

  // Erro: Failed to read executable
  if (/Failed to read executable/i.test(line)) {
    errorCount++;
    if (lastScan) broken.add(path.basename(lastScan));
    continue;
  }

  // Erro: Failed to read (generico de disco)
  if (/E\(.*Failed to read/i.test(line) && !/executable/i.test(line)) {
    errorCount++;
    if (lastScan) broken.add(path.basename(lastScan));
  }
}

const list = [...broken].sort();
console.log('Total erros encontrados no log:', errorCount);
console.log('CHDs unicos com problema:', list.length);
console.log('\nLista:');
list.forEach(f => console.log('  ' + f));

// Mover para D:\roms\psx-quebrados
const SRC = 'D:\\roms\\library\\roms\\psx';
const DST = 'D:\\roms\\psx-quebrados';
if (!fs.existsSync(DST)) fs.mkdirSync(DST, { recursive: true });

let moved = 0, notFound = 0, failed = 0;
const norm = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');

// Criar indice da colecao para match fuzzy
const colChds = fs.readdirSync(SRC).filter(f => f.toLowerCase().endsWith('.chd'));
const colIndex = new Map();
for (const f of colChds) {
  colIndex.set(norm(f), f);
}

for (const f of list) {
  const dst = path.join(DST, f);
  try {
    // Match exato
    const src = path.join(SRC, f);
    if (fs.existsSync(src)) {
      if (fs.existsSync(dst)) { fs.unlinkSync(src); }
      else { fs.renameSync(src, dst); }
      console.log('[OK] ' + f);
      moved++;
    } else {
      // Match fuzzy
      const match = colIndex.get(norm(f));
      if (match) {
        const srcM = path.join(SRC, match);
        const dstM = path.join(DST, match);
        if (fs.existsSync(dstM)) { fs.unlinkSync(srcM); }
        else { fs.renameSync(srcM, dstM); }
        console.log('[OK-MATCH] ' + match + ' (procurava ' + f + ')');
        moved++;
      } else {
        console.log('[NAO ENCONTRADO] ' + f);
        notFound++;
      }
    }
  } catch (e) {
    console.log('[ERRO] ' + f + ': ' + e.message.substring(0, 60));
    failed++;
  }
}

console.log('\n=== Resultado ===');
console.log('Movidos:', moved);
console.log('Nao encontrados:', notFound);
console.log('Erros:', failed);
console.log('CHDs restantes na colecao:', fs.readdirSync(SRC).filter(f => f.toLowerCase().endsWith('.chd')).length);
console.log('CHDs em psx-quebrados:', fs.readdirSync(DST).filter(f => f.toLowerCase().endsWith('.chd')).length);
