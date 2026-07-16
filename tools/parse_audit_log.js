const fs = require('fs');
const log = 'C:\\Users\\Usuario\\Documents\\DuckStation\\duckstation.log';
const content = fs.readFileSync(log, 'utf8');
const lines = content.split(/\r\n|\r|\n/);

// Encontrar todos os CHDs com erro
// Padroes:
// 1. "Failed to open disc image 'FILE.chd'" - CHD corrompido/invalido
// 2. "Failed to read executable 'X' from disc" apos "Scanning 'FILE.chd'" - CHD abre mas exe ilegivel

const brokenChds = new Set();

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];

  // Pattern 1: Failed to open disc image
  const m1 = line.match(/Failed to open disc image '([^']+)'/);
  if (m1) {
    brokenChds.add(m1[1]);
    continue;
  }

  // Pattern 2: Failed to read executable - procurar Scanning anterior
  if (/Failed to read executable/i.test(line)) {
    for (let j = i - 1; j >= Math.max(0, i - 5); j--) {
      const m = lines[j].match(/Scanning '([^']+)'/);
      if (m) {
        brokenChds.add(m[1]);
        break;
      }
    }
  }
}

const list = [...brokenChds].sort();
console.log(`CHDs com problema: ${list.length}`);
console.log('\nLista:');
for (const f of list) {
  const basename = f.split('\\').pop().split('/').pop();
  console.log(`  ${basename}`);
}

// Salvar lista
fs.writeFileSync('F:\\importre\\tools\\broken_chds.txt', list.join('\n') + '\n');
console.log(`\nLista salva em F:\\importre\\tools\\broken_chds.txt`);
