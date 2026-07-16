const fs = require('fs');
const content = fs.readFileSync('F:\\importre\\tools\\broken_chds2.txt', 'utf8');
const lines = content.split(/\r\n|\r|\n/);

console.log('Total linhas:', lines.length);

// Percorrer todas as linhas e encontrar:
// 1. "Failed to open disc image 'FILE.chd'" - CHD corrompido
// 2. "Failed to read executable 'X' from disc" - procurar Scanning anterior
// 3. "invalid file" - CHD invalido

const brokenChds = new Set();
let lastScanned = null;

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];

  // Track ultimo Scanning
  const scanMatch = line.match(/Scanning '([^']+\.chd)'/i);
  if (scanMatch) {
    lastScanned = scanMatch[1];
    continue;
  }

  // Pattern 1: Failed to open disc image
  const m1 = line.match(/Failed to open disc image '([^']+)'/i);
  if (m1) {
    brokenChds.add(m1[1]);
    continue;
  }

  // Pattern 2: invalid file
  if (/invalid file/i.test(line) && lastScanned) {
    brokenChds.add(lastScanned);
    continue;
  }

  // Pattern 3: Failed to read executable
  if (/Failed to read executable/i.test(line) && lastScanned) {
    brokenChds.add(lastScanned);
    continue;
  }

  // Pattern 4: Failed to read (generico apos scan)
  if (/Failed to read/i.test(line) && lastScanned && !/executable/i.test(line) && /E\(|ERROR|Failed to read disc/i.test(line)) {
    brokenChds.add(lastScanned);
  }
}

// Tambem procurar por qualquer linha com ERROR ou E( que mencione .chd
for (const line of lines) {
  const m = line.match(/E\([^)]*\).*?['"]?([^'"\s]+\.chd)['"]?/i);
  if (m && m[1]) {
    // Extrair apenas o nome do arquivo
    const basename = m[1].split('\\').pop().split('/').pop();
    brokenChds.add('D:\\roms\\library\\roms\\psx\\' + basename);
  }
}

const list = [...brokenChds].sort();
console.log('CHDs com problema encontrados:', list.length);
console.log('\nLista completa:');
for (const f of list) {
  const basename = f.split('\\').pop().split('/').pop();
  console.log('  ' + basename);
}

// Salvar lista processada
fs.writeFileSync('F:\\importre\\tools\\broken_chds_final.txt', list.map(f => f.split('\\').pop().split('/').pop()).join('\n') + '\n');
console.log('\nLista salva em F:\\importre\\tools\\broken_chds_final.txt');
