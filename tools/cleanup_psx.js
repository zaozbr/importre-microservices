// Limpeza: apaga lixo, remove duplicados, identifica downloads errados
const fs = require('fs');
const path = require('path');

const dir = 'D:/roms/library/roms/psx';
const q = JSON.parse(fs.readFileSync('D:/roms/library/roms/_importre_state/queue.json', 'utf-8'));
const validSerials = new Set(q.queue.map(i => i.serial));
const completedSerials = new Set(Object.keys(q.completed || {}));
const itemBySerial = {};
for (const i of q.queue) itemBySerial[i.serial] = i;

const files = fs.readdirSync(dir).filter(f => !f.startsWith('.') && f !== '.playwright-mcp');

// Extensoes validas de ROM
const validExts = new Set(['.chd', '.bin', '.cue', '.iso', '.img', '.7z', '.zip', '.rar', '.ecm', '.mdf', '.mds', '.ccd', '.sub']);
// Extensoes de lixo
const trashExts = new Set(['.lo', '.c1', '.c2', '.c3', '.c4', '.c5', '.c6', '.c7', '.c8', '.m1', '.p1', '.sp2', '.s1', '.v1', '.v2', '.v3', '.tmp', '.php', '.url', '.exe', '.log', '.md5', '.gba', '.conf', '.aria2', '.bak', '.png', '.jpeg', '.html', '.sfix', '.sm1', '.sp1', '.1024', '.dat', '.z64', '.ps1', '.lock', '.pid', '.idlst', '.xml', '.b64', '.vbs', '.bat', '.txt', '.md', '.json', '.rom', '.pbp', '.crdownload', '.aria2__temp']);

let trashDeleted = 0;
let trashSize = 0;
let chdDeleted = 0;
let chdSize = 0;
const requeueItems = [];

// 1. Apaga arquivos lixo
console.log('=== 1. Limpando arquivos lixo ===');
for (const f of files) {
  const ext = path.extname(f).toLowerCase();
  const fullPath = path.join(dir, f);
  let st;
  try { st = fs.statSync(fullPath); } catch (e) { continue; }
  
  if (trashExts.has(ext) || ext === '') {
    try {
      fs.unlinkSync(fullPath);
      trashDeleted++;
      trashSize += st.size;
    } catch (e) {}
  }
}
console.log(`Lixo apagado: ${trashDeleted} arquivos (${(trashSize/1048576).toFixed(1)}MB)`);

// 2. Remove .chd duplicados (mantem o com nome mais descritivo)
console.log('\n=== 2. Removendo .chd duplicados ===');
const chdFiles = files.filter(f => f.toLowerCase().endsWith('.chd'));
const chdBySerial = {};
for (const f of chdFiles) {
  const m = f.match(/([SC][LEUPSM]{2,3}-\d{3,5})/i);
  if (m) {
    const s = m[1].toUpperCase();
    if (!chdBySerial[s]) chdBySerial[s] = [];
    chdBySerial[s].push(f);
  }
}

for (const [serial, files] of Object.entries(chdBySerial)) {
  if (files.length <= 1) continue;
  
  // Mantem o arquivo com nome mais longo (mais descritivo)
  // Apaga os que comecam com "-" (nome vazio tipo "-SLUS-00069.chd")
  files.sort((a, b) => {
    const aBad = a.startsWith('-') || a.match(/^SLUS-\d+\.chd$/i) || a.match(/^SLPM-\d+\.chd$/i) || a.match(/^SLPS-\d+\.chd$/i) || a.match(/^SLES-\d+\.chd$/i) || a.match(/^SCPS-\d+\.chd$/i) || a.match(/^SCUS-\d+\.chd$/i);
    const bBad = b.startsWith('-') || b.match(/^SLUS-\d+\.chd$/i) || b.match(/^SLPM-\d+\.chd$/i) || b.match(/^SLPS-\d+\.chd$/i) || b.match(/^SLES-\d+\.chd$/i) || b.match(/^SCPS-\d+\.chd$/i) || b.match(/^SCUS-\d+\.chd$/i);
    if (aBad && !bBad) return -1; // a vai primeiro (sera apagado)
    if (!aBad && bBad) return 1;
    return b.length - a.length; // nome mais longo primeiro (mantem)
  });
  
  // Apaga todos exceto o ultimo (que ficou)
  const keep = files[files.length - 1];
  for (const f of files.slice(0, -1)) {
    const fullPath = path.join(dir, f);
    try {
      const st = fs.statSync(fullPath);
      fs.unlinkSync(fullPath);
      chdDeleted++;
      chdSize += st.size;
      console.log(`  Apagado: ${f} (mantido: ${keep})`);
    } catch (e) {}
  }
}
console.log(`Duplicados apagados: ${chdDeleted} arquivos (${(chdSize/1048576).toFixed(1)}MB)`);

// 3. Identifica .chd sem serial valido (possiveis downloads errados)
console.log('\n=== 3. .chd sem serial valido ===');
const chdNoSerial = chdFiles.filter(f => {
  const m = f.match(/([SC][LEUPSM]{2,3}-\d{3,5})/i);
  return !m || !validSerials.has(m[1].toUpperCase());
});
console.log(`Total: ${chdNoSerial.length} (arquivos .chd sem serial reconhecivel)`);

// 4. Seriais completados sem .chd -> recolocar na fila
console.log('\n=== 4. Completados sem .chd -> recolocar na fila ===');
const chdSerials = new Set(Object.keys(chdBySerial));
for (const s of completedSerials) {
  if (!chdSerials.has(s)) {
    const item = itemBySerial[s];
    if (item) {
      item.status = 'pending';
      delete item.search_started;
      delete q.completed[s];
      requeueItems.push(s);
    }
  }
}
console.log(`Recolocados na fila: ${requeueItems.length}`);
for (const s of requeueItems.slice(0, 20)) console.log(`  ${s}`);

// Salva queue
try {
  fs.writeFileSync('D:/roms/library/roms/_importre_state/queue.json', JSON.stringify(q, null, 2));
  console.log('\nFila atualizada');
} catch (e) {
  console.log('lock ao salvar fila:', e.message);
}

console.log(`\n=== RESUMO ===`);
console.log(`Lixo apagado: ${trashDeleted} (${(trashSize/1048576).toFixed(1)}MB)`);
console.log(`Duplicados apagados: ${chdDeleted} (${(chdSize/1048576).toFixed(1)}MB)`);
console.log(`Itens recolocados na fila: ${requeueItems.length}`);
