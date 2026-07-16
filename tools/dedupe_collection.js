const fs = require('fs');
const path = require('path');

const DUP = 'D:\\roms\\duplicados';
const ROM = 'D:\\roms\\library\\roms\\psx';

// === Mapeamento de titulos JP -> US/EU ===
const JP_TO_US = {
  'biohazard': 'resident evil',
  'biohazard 2': 'resident evil 2',
  'biohazard 3': 'resident evil 3',
  'biohazard code veronica': 'resident evil code veronica',
  'biohazard code:veronica': 'resident evil code veronica',
  'biohazard - code veronica': 'resident evil code veronica',
  'biohazard gun survivor': 'resident evil survivor',
  'biohazard 2 gun survivor': 'resident evil survivor 2',
  'jikkyou j league': 'j league',
  'winning eleven': 'international superstar soccer',
  'iss pro': 'international superstar soccer pro',
  'tobal': 'tobal',
  'gundan': 'gundam',
  'kidou senshi gundam': 'gundam',
  'soukou kihei votoms': 'votoms',
  'tokimeki memorial': 'tokimeki memorial',
  'derby stallion': 'derby stallion',
  'pachinko': 'pachinko',
  'pachi-slot': 'pachi-slot',
  'pachislot': 'pachi-slot',
  'ryu ga gotoku': 'yakuza',
  'tale of': 'tales of',
  'dragon quest': 'dragon quest',
  'final fantasy': 'final fantasy',
  'chrono': 'chrono',
  'seiken densetsu': 'secret of mana',
  'jikuu tantei': 'jikuu tantei',
  'sa ga': 'saga',
  'saga frontier': 'saga frontier',
  'front mission': 'front mission',
  'koudelka': 'koudelka',
  'vagrant story': 'vagrant story',
  'valkyrie profile': 'valkyrie profile',
  'star ocean': 'star ocean',
  'xenogears': 'xenogears',
  'grandia': 'grandia',
  'lunar': 'lunar',
  'suikoden': 'suikoden',
  'wild arms': 'wild arms',
  'breath of fire': 'breath of fire',
  'parasite eve': 'parasite eve',
  'chrono trigger': 'chrono trigger',
  'chrono cross': 'chrono cross',
  'vandal hearts': 'vandal hearts',
  'disgaea': 'disgaea',
  'rhapsody': 'rhapsody',
  'mechanical': 'mechanical',
};

function extractSerial(name) {
  const m = name.match(/(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}/i);
  if (!m) return null;
  let s = m[0].toUpperCase().replace('_', '-');
  s = s.replace(/^(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)0*(\d{3,5})$/i, '$1-$2');
  return s;
}

function serialRegion(serial) {
  if (!serial) return null;
  if (/^(SLUS|SCUS|SLED)/i.test(serial)) return 'USA';
  if (/^(SLES|SCES)/i.test(serial)) return 'EUR';
  if (/^(SLPS|SIPS|SLPM|SCPS)/i.test(serial)) return 'JPN';
  return 'OTHER';
}

function regionPriority(region) {
  return { USA: 0, EUR: 1, OTHER: 2, JPN: 3 }[region] ?? 9;
}

function isDemo(name) {
  return /demo|demoversion|sample|trial|teaser|preview|beta|alpha|proto|vol\.\s*\d/i.test(name);
}

function normalizeTitle(name) {
  let t = name;
  // Remover ext
  t = t.replace(/\.(chd|bin|img|iso|cue)$/i, '');
  // Remover serial entre colchetes
  t = t.replace(/\[(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}\]/gi, '');
  t = t.replace(/\[SLUS-?\d+\]/gi, '').replace(/\[SLPS-?\d+\]/gi, '').replace(/\[SLES-?\d+\]/gi, '');
  t = t.replace(/\[U\]/gi, '').replace(/\[J\]/gi, '').replace(/\[E\]/gi, '');
  t = t.replace(/\[NTSC-U\]/gi, '').replace(/\[NTSC-J\]/gi, '').replace(/\[PAL\]/gi, '');
  t = t.replace(/\[IOL\.com\]/gi, '').replace(/\[ccd\+img\+sub\]/gi, '');
  t = t.replace(/\[\d+\]/g, ''); // [1783840814] timestamps
  // Remover regiao entre parenteses
  t = t.replace(/\((USA|Europe|Japan|Germany|France|Spain|Italy|Korea|Asia|Australia|Canada|Brazil|Mexico|Netherlands|Sweden|Norway|Denmark|Finland|Belgium|Portugal|Switzerland|Austria|Greece|Poland|Czech|Russia|Turkey|Israel|South Africa|New Zealand|Ireland|Luxembourg|Iceland)\)/gi, '');
  t = t.replace(/\((En|Fr|De|Es|It|Nl|Sv|No|Da|Fi|Pt|El|Pl|Cs|Ru|Tr|He|Ko|Ja|Zh)[,)]/gi, '(');
  // Remover (En,Fr,De,...) tags
  t = t.replace(/\([A-Z][a-z](,[A-Z][a-z])*\)/g, '');
  // Remover disc/track info
  t = t.replace(/\(Disc\s*\d+[^)]*\)/gi, '');
  t = t.replace(/\(Track\s*\d+[^)]*\)/gi, '');
  t = t.replace(/Disc\s*\d+/gi, '');
  t = t.replace(/CD\s*\d+/gi, '');
  t = t.replace(/\(v\d+\.\d+\)/gi, '');
  t = t.replace(/\(v\d+\)/gi, '');
  t = t.replace(/\(Alt\)/gi, '');
  t = t.replace(/\(Beta[^)]*\)/gi, '');
  t = t.replace(/\(Demo[^)]*\)/gi, '');
  t = t.replace(/\(Preview[^)]*\)/gi, '');
  t = t.replace(/\(Sample[^)]*\)/gi, '');
  t = t.replace(/\(Rental\)/gi, '');
  t = t.replace(/\(Greatest Hits\)/gi, '');
  t = t.replace(/\(Platinum\)/gi, '');
  t = t.replace(/\(PlayStation the Best\)/gi, '');
  t = t.replace(/\(PSone Books\)/gi, '');
  t = t.replace(/\(Premium Box\)/gi, '');
  t = t.replace(/\(Deluxe Pack\)/gi, '');
  t = t.replace(/\(Limited Edition\)/gi, '');
  t = t.replace(/\(Tentou You [^)]*\)/gi, '');
  t = t.replace(/\(Front Mission History\)/gi, '');
  // Remover chars extras
  t = t.replace(/[._]/g, ' ');
  t = t.replace(/\s+/g, ' ').trim();
  // Remover sufixos _1, _2 (duplicados)
  t = t.replace(/_\d+$/, '');
  // Lowercase para comparacao
  t = t.toLowerCase().trim();
  // Aplicar mapeamento JP->US
  for (const [jp, us] of Object.entries(JP_TO_US)) {
    if (t.includes(jp)) {
      t = t.replace(jp, us);
    }
  }
  // Remover chars nao alfanumericos para comparacao fuzzy
  t = t.replace(/[^a-z0-9]/g, '');
  return t;
}

function walkDir(dir) {
  const r = [];
  try {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const f = path.join(dir, e.name);
      if (e.isDirectory()) r.push(...walkDir(f));
      else r.push(f);
    }
  } catch {}
  return r;
}

// === 1. Construir base da colecao ===
const colChds = fs.readdirSync(ROM).filter(f => f.toLowerCase().endsWith('.chd'));
const collection = []; // {file, serial, region, normTitle, isDemo, rawName}

for (const f of colChds) {
  const raw = f.replace(/\.chd$/i, '');
  const serial = extractSerial(raw);
  const region = serialRegion(serial) || 'OTHER';
  const norm = normalizeTitle(raw);
  const demo = isDemo(raw);
  collection.push({ file: f, serial, region, normTitle: norm, isDemo: demo, rawName: raw });
}

// Index por titulo normalizado
const colByTitle = new Map();
for (const g of collection) {
  if (g.isDemo) continue;
  if (!colByTitle.has(g.normTitle)) colByTitle.set(g.normTitle, []);
  colByTitle.get(g.normTitle).push(g);
}

console.log(`Colecao: ${collection.length} CHDs (${collection.filter(g => g.isDemo).length} demos)`);
console.log(`Titulos unicos na colecao (sem demo): ${colByTitle.size}`);

// === 2. Analisar duplicados ===
const dupFiles = walkDir(DUP);
const dupBins = dupFiles.filter(f => /\.(bin|img|iso)$/i.test(f));

const dupAnalysis = [];
for (const bin of dupBins) {
  const raw = path.basename(bin, path.extname(bin));
  const dir = path.dirname(bin);
  const serial = extractSerial(raw) || extractSerial(path.basename(dir));
  const region = serialRegion(serial) || 'OTHER';
  const norm = normalizeTitle(raw);
  const demo = isDemo(raw) || isDemo(path.basename(dir));

  let isValid = true;
  try { if (fs.statSync(bin).size < 1024 * 1024) isValid = false; } catch { isValid = false; }

  dupAnalysis.push({ bin, raw, serial, region, normTitle: norm, isDemo: demo, isValid, dir });
}

console.log(`\nDuplicados: ${dupBins.length} bins (${dupAnalysis.filter(d => d.isDemo).length} demos, ${dupAnalysis.filter(d => !d.isValid).length} invalidos)`);

// === 3. Comparar ===
const salvageable = [];
const discardable = [];

for (const d of dupAnalysis) {
  if (!d.isValid || d.isDemo) {
    discardable.push({ ...d, reason: d.isDemo ? 'demo' : 'invalido/corrompido' });
    continue;
  }

  // Verificar se o jogo existe na colecao
  const colMatches = colByTitle.get(d.normTitle) || [];

  if (colMatches.length === 0) {
    // Jogo nao existe na colecao -> aproveitavel
    salvageable.push({ ...d, reason: 'nao existe na colecao' });
    continue;
  }

  // Jogo existe: comparar prioridade de regiao
  const bestColRegion = colMatches.reduce((best, g) =>
    regionPriority(g.region) < regionPriority(best) ? g.region : best, 'OTHER');

  if (regionPriority(d.region) < regionPriority(bestColRegion)) {
    // Duplicado tem regiao melhor -> aproveitavel
    salvageable.push({ ...d, reason: `regiao melhor (${d.region} > ${bestColRegion})` });
  } else {
    // Colecao ja tem versao melhor ou igual -> descartar
    discardable.push({ ...d, reason: `colecao ja tem ${bestColRegion} (dup=${d.region})` });
  }
}

console.log(`\n=== Resultado ===`);
console.log(`Aproveitavel: ${salvageable.length}`);
console.log(`Descartavel: ${discardable.length}`);

// === 4. Deletar descartaveis ===
let deleted = 0, deletedBytes = 0;

for (const d of discardable) {
  const baseNoExt = path.basename(d.bin, path.extname(d.bin));
  // Deletar bin + arquivos relacionados
  const related = dupFiles.filter(f => {
    const fb = path.basename(f);
    return fb.startsWith(baseNoExt) && /\.(bin|img|iso|cue|sub|ccd|mds|mdf|ape|7z)$/i.test(f);
  });
  for (const f of related) {
    try {
      const sz = fs.statSync(f).size;
      fs.unlinkSync(f);
      deleted++;
      deletedBytes += sz;
    } catch {}
  }
}

console.log(`\nDeletados: ${deleted} arquivos (${(deletedBytes / 1073741824).toFixed(2)} GB)`);

// Limpar pastas vazias
function rmEmpty(dir) {
  let n = 0;
  try {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      if (e.isDirectory()) {
        const sub = path.join(dir, e.name);
        n += rmEmpty(sub);
        try { if (fs.readdirSync(sub).length === 0) { fs.rmdirSync(sub); n++; } } catch {}
      }
    }
  } catch {}
  return n;
}
const cleaned = rmEmpty(DUP);
console.log(`Pastas vazias removidas: ${cleaned}`);

// === 5. Listar aproveitaveis ===
console.log(`\n=== Jogos aproveitaveis em duplicados (${salvageable.length}) ===`);
salvageable.sort((a, b) => a.raw.localeCompare(b.raw));
for (const s of salvageable) {
  console.log(`  [${s.region}] ${s.raw} -- ${s.reason}`);
}

// Salvar lista em arquivo
const reportPath = 'F:\\importre\\tools\\salvageable_list.txt';
const lines = salvageable.map(s => `[${s.region}] ${s.raw} -- ${s.reason}`);
fs.writeFileSync(reportPath, `Jogos aproveitaveis em D:\\roms\\duplicados\nTotal: ${salvageable.length}\n\n${lines.join('\n')}\n`);
console.log(`\nLista salva em: ${reportPath}`);
