// Auditoria completa do diretorio psx
// Identifica: arquivos .chd ok, .bin/.cue pendentes, arquivos lixo, duplicados
const fs = require('fs');
const path = require('path');

const dir = 'D:/roms/library/roms/psx';
const files = fs.readdirSync(dir).filter(f => !f.startsWith('.') && f !== '.playwright-mcp');

const chdFiles = [];
const binFiles = [];
const cueFiles = [];
const archiveFiles = []; // .7z, .zip, .rar
const otherFiles = [];
const serials = new Set();

// Carrega queue.json para saber seriais validos
const q = JSON.parse(fs.readFileSync('D:/roms/library/roms/_importre_state/queue.json', 'utf-8'));
const validSerials = new Set(q.queue.map(i => i.serial));
const completedSerials = new Set(Object.keys(q.completed || {}));

for (const f of files) {
  const lower = f.toLowerCase();
  const fullPath = path.join(dir, f);
  const st = fs.statSync(fullPath);
  
  if (lower.endsWith('.chd')) {
    chdFiles.push({ name: f, size: st.size });
  } else if (lower.endsWith('.bin')) {
    binFiles.push({ name: f, size: st.size });
  } else if (lower.endsWith('.cue')) {
    cueFiles.push({ name: f, size: st.size });
  } else if (lower.endsWith('.7z') || lower.endsWith('.zip') || lower.endsWith('.rar')) {
    archiveFiles.push({ name: f, size: st.size });
  } else {
    otherFiles.push({ name: f, size: st.size });
  }
  
  // Extrai serial do nome
  const serialMatch = f.match(/([SC][LEUPSM]{2,3}-\d{3,5})/i);
  if (serialMatch) serials.add(serialMatch[1].toUpperCase());
}

console.log('=== AUDITORIA D:/roms/library/roms/psx ===\n');
console.log('Total arquivos:', files.length);
console.log('Arquivos .chd (convertidos):', chdFiles.length);
console.log('Arquivos .bin (pendentes conversao):', binFiles.length);
console.log('Arquivos .cue (pendentes conversao):', cueFiles.length);
console.log('Arquivos .7z/.zip/.rar (pendentes extracao):', archiveFiles.length);
console.log('Outros arquivos:', otherFiles.length);
console.log('Seriais unicos nos nomes:', serials.size);
console.log('Seriais validos na fila:', validSerials.size);
console.log('Seriais completados na fila:', completedSerials.size);

// Arquivos .chd com serial valido
const chdWithSerial = chdFiles.filter(f => {
  const m = f.name.match(/([SC][LEUPSM]{2,3}-\d{3,5})/i);
  return m && validSerials.has(m[1].toUpperCase());
});
console.log('\n.chd com serial valido:', chdWithSerial.length);

// Arquivos .chd sem serial (nome estranho)
const chdNoSerial = chdFiles.filter(f => !f.name.match(/[SC][LEUPSM]{2,3}-\d{3,5}/i));
console.log('.chd sem serial reconhecivel:', chdNoSerial.length);

// Arquivos lixo (extensao nao reconhecida)
console.log('\n=== Arquivos lixo (outros) ===');
const trashExts = new Set();
for (const f of otherFiles) {
  const ext = path.extname(f.name).toLowerCase();
  trashExts.add(ext);
}
console.log('Extensoes encontradas:', [...trashExts].join(', '));
console.log('Primeiros 10:');
for (const f of otherFiles.slice(0, 10)) {
  console.log(`  ${f.name} (${(f.size/1024).toFixed(0)}KB)`);
}

// Arquivos .bin sem .cue correspondente
const cueNames = new Set(cueFiles.map(f => f.name.replace(/\.cue$/i, '')));
const binWithoutCue = binFiles.filter(f => !cueNames.has(f.name.replace(/\.bin$/i, '')));
console.log('\n=== .bin sem .cue ===');
console.log('Total:', binWithoutCue.length);
for (const f of binWithoutCue.slice(0, 10)) {
  console.log(`  ${f.name} (${(f.size/1048576).toFixed(1)}MB)`);
}

// Arquivos .chd duplicados (mesmo serial, arquivos diferentes)
const chdBySerial = {};
for (const f of chdFiles) {
  const m = f.name.match(/([SC][LEUPSM]{2,3}-\d{3,5})/i);
  if (m) {
    const s = m[1].toUpperCase();
    if (!chdBySerial[s]) chdBySerial[s] = [];
    chdBySerial[s].push(f);
  }
}
const chdDups = Object.entries(chdBySerial).filter(([_s, files]) => files.length > 1);
console.log('\n=== .chd duplicados por serial ===');
console.log('Total seriais com duplicata:', chdDups.length);
for (const [s, files] of chdDups.slice(0, 10)) {
  console.log(`  ${s}: ${files.map(f => f.name).join(', ')}`);
}

// Seriais completados na fila mas sem .chd no diretorio
const chdSerials = new Set(Object.keys(chdBySerial));
const completedWithoutChd = [...completedSerials].filter(s => !chdSerials.has(s));
console.log('\n=== Completados na fila sem .chd ===');
console.log('Total:', completedWithoutChd.length);
for (const s of completedWithoutChd.slice(0, 10)) {
  console.log(`  ${s}`);
}

// Salva relatorio completo
const report = {
  timestamp: new Date().toISOString(),
  total: files.length,
  chd: chdFiles.length,
  bin: binFiles.length,
  cue: cueFiles.length,
  archives: archiveFiles.length,
  other: otherFiles.length,
  chdDups: chdDups.map(([s, files]) => ({ serial: s, files: files.map(f => f.name) })),
  binWithoutCue: binWithoutCue.map(f => f.name),
  otherFiles: otherFiles.map(f => ({ name: f.name, size: f.size })),
  completedWithoutChd: completedWithoutChd,
};
fs.writeFileSync('D:/roms/library/roms/_importre_state/audit_report.json', JSON.stringify(report, null, 2));
console.log('\nRelatorio salvo em audit_report.json');
