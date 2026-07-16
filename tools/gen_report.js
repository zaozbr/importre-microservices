const fs = require('fs');
const path = require('path');

const ROM = 'D:\\roms\\library\\roms\\psx';

function extractSerial(name) {
  const m = name.match(/(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}/i);
  if (!m) return null;
  return m[0].toUpperCase().replace('_', '-').replace(/^(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)0*(\d{3,5})$/i, '$1-$2');
}

function serialRegion(s) {
  if (!s) return 'OTHER';
  if (/^(SLUS|SCUS|SLED)/i.test(s)) return 'USA';
  if (/^(SLES|SCES)/i.test(s)) return 'EUR';
  if (/^(SLPS|SIPS|SLPM|SCPS)/i.test(s)) return 'JPN';
  return 'OTHER';
}

function isDemo(name) {
  return /demo|demoversion|sample|trial|teaser|preview|beta|alpha|proto/i.test(name);
}

function cleanName(name) {
  let t = name.replace(/\.chd$/i, '');
  t = t.replace(/\[(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}\]/gi, '');
  t = t.replace(/\[U\]/gi, '').replace(/\[J\]/gi, '').replace(/\[E\]/gi, '');
  t = t.replace(/\[NTSC-U\]/gi, '').replace(/\[NTSC-J\]/gi, '').replace(/\[PAL\]/gi, '');
  t = t.replace(/\[IOL\.com\]/gi, '').replace(/\[ccd\+img\+sub\]/gi, '').replace(/\[\d+\]/g, '');
  t = t.replace(/\((USA|Europe|Japan|Germany|France|Spain|Italy|Korea|Asia|Australia|Canada|Brazil|Mexico|Netherlands|Sweden|Norway|Denmark|Finland|Belgium|Portugal|Switzerland|Austria|Greece|Poland|Czech|Russia|Turkey|Israel|South Africa|New Zealand|Ireland|Luxembourg|Iceland)\)/gi, '');
  t = t.replace(/\([A-Z][a-z](,[A-Z][a-z])*\)/g, '');
  t = t.replace(/\(Track\s*\d+[^)]*\)/gi, '').replace(/\(Disc\s*\d+[^)]*\)/gi, '');
  t = t.replace(/Track\s*\d+/gi, '').replace(/Disc\s*\d+/gi, '').replace(/CD\s*\d+/gi, '');
  t = t.replace(/\(v\d+\.\d+\)/gi, '').replace(/\(v\d+\)/gi, '');
  t = t.replace(/\(Alt\)/gi, '').replace(/\(Beta[^)]*\)/gi, '').replace(/\(Greatest Hits\)/gi, '');
  t = t.replace(/\(Platinum\)/gi, '').replace(/\(PlayStation the Best\)/gi, '').replace(/\(PSone Books\)/gi, '');
  t = t.replace(/-nao-conversivel/gi, '').replace(/_\d{10}$/, '').replace(/_\d+$/, '');
  t = t.replace(/[._]/g, ' ').replace(/\s+/g, ' ').trim();
  return t;
}

const chds = fs.readdirSync(ROM).filter(f => f.toLowerCase().endsWith('.chd'));
console.log(`Total CHDs: ${chds.length}`);

const games = [];
for (const f of chds) {
  const raw = f.replace(/\.chd$/i, '');
  const serial = extractSerial(raw);
  const region = serialRegion(serial);
  const demo = isDemo(raw);
  const name = cleanName(raw);
  games.push({ file: f, serial, region, demo, name });
}

const nonDemo = games.filter(g => !g.demo);
const demos = games.filter(g => g.demo);

// Agrupar por titulo normalizado (chave)
function normKey(name) {
  return name.toLowerCase().replace(/[^a-z0-9]/g, '');
}

const byTitle = new Map();
for (const g of nonDemo) {
  const k = normKey(g.name);
  if (!byTitle.has(k)) byTitle.set(k, []);
  byTitle.get(k).push(g);
}

// Para cada titulo, escolher a melhor versao por regiao
const pri = { USA: 0, EUR: 1, OTHER: 2, JPN: 3 };
const finalGames = [];
for (const [key, versions] of byTitle) {
  versions.sort((a, b) => (pri[a.region] ?? 9) - (pri[b.region] ?? 9));
  finalGames.push(versions[0]); // melhor versao
}

finalGames.sort((a, b) => {
  const pa = pri[a.region] ?? 9, pb = pri[b.region] ?? 9;
  if (pa !== pb) return pa - pb;
  return a.name.localeCompare(b.name);
});

let md = `# Colecao PSX - Jogos Atuais\n\n`;
md += `**Data:** ${new Date().toISOString().split('T')[0]}\n\n`;
md += `**Total CHDs:** ${chds.length}\n`;
md += `**Jogos unicos (sem demo):** ${finalGames.length}\n`;
md += `**Demos:** ${demos.length}\n\n`;
md += `**Criterio:** USA > EUR > Outros > JPN | Sem demos | 1 versao por jogo\n\n`;
md += `## Resumo por regiao\n\n`;
md += `| Regiao | Jogos |\n|--------|-------|\n`;
for (const r of ['USA', 'EUR', 'OTHER', 'JPN']) {
  md += `| ${r} | ${finalGames.filter(g => g.region === r).length} |\n`;
}

md += `\n## Lista completa (${finalGames.length} jogos)\n\n`;
md += `| # | Serial | Regiao | Jogo |\n`;
md += `|---|--------|--------|------|\n`;
for (let i = 0; i < finalGames.length; i++) {
  const g = finalGames[i];
  md += `| ${i + 1} | ${g.serial || 'N/A'} | ${g.region} | ${g.name} |\n`;
}

const mdPath = 'F:\\importre\\jogos-atuais.md';
fs.writeFileSync(mdPath, md);
console.log(`jogos-atuais.md gerado: ${mdPath}`);
console.log(`Jogos unicos: ${finalGames.length}`);
console.log(`  USA: ${finalGames.filter(g => g.region === 'USA').length}`);
console.log(`  EUR: ${finalGames.filter(g => g.region === 'EUR').length}`);
console.log(`  OTHER: ${finalGames.filter(g => g.region === 'OTHER').length}`);
console.log(`  JPN: ${finalGames.filter(g => g.region === 'JPN').length}`);
console.log(`Demos: ${demos.length}`);
