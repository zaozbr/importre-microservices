const fs = require('fs');
const path = require('path');

const DUP = 'D:\\roms\\duplicados';

function extractSerial(name) {
  const m = name.match(/(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}/i);
  if (!m) return null;
  let s = m[0].toUpperCase().replace('_', '-');
  s = s.replace(/^(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)0*(\d{3,5})$/i, '$1-$2');
  return s;
}

function serialRegion(serial) {
  if (!serial) return 'OTHER';
  if (/^(SLUS|SCUS|SLED)/i.test(serial)) return 'USA';
  if (/^(SLES|SCES)/i.test(serial)) return 'EUR';
  if (/^(SLPS|SIPS|SLPM|SCPS)/i.test(serial)) return 'JPN';
  return 'OTHER';
}

function isDemo(name) {
  return /demo|demoversion|sample|trial|teaser|preview|beta|alpha|proto/i.test(name);
}

// Limpar nome do jogo: remove regioes, tracks, disc, versoes, serials, etc
function cleanGameName(name) {
  let t = name;
  t = t.replace(/\.(bin|img|iso|cue|sub|ccd|mds|mdf)$/i, '');
  // Remover serial entre colchetes
  t = t.replace(/\[(SLES|SLUS|SCES|SCUS|SLPS|SIPS|SLPM|SCPS|SLED)[-_]?\d{3,5}\]/gi, '');
  t = t.replace(/\[U\]/gi, '').replace(/\[J\]/gi, '').replace(/\[E\]/gi, '');
  t = t.replace(/\[NTSC-U\]/gi, '').replace(/\[NTSC-J\]/gi, '').replace(/\[PAL\]/gi, '');
  t = t.replace(/\[IOL\.com\]/gi, '').replace(/\[ccd\+img\+sub\]/gi, '');
  t = t.replace(/\[\d+\]/g, '');
  // Remover regioes entre parenteses
  t = t.replace(/\((USA|Europe|Japan|Germany|France|Spain|Italy|Korea|Asia|Australia|Canada|Brazil|Mexico|Netherlands|Sweden|Norway|Denmark|Finland|Belgium|Portugal|Switzerland|Austria|Greece|Poland|Czech|Russia|Turkey|Israel|South Africa|New Zealand|Ireland|Luxembourg|Iceland)\)/gi, '');
  // Remover tags de idioma (En,Fr,De,...)
  t = t.replace(/\([A-Z][a-z](,[A-Z][a-z])*\)/g, '');
  // Remover Track/Disc info
  t = t.replace(/\(Track\s*\d+[^)]*\)/gi, '');
  t = t.replace(/\(Disc\s*\d+[^)]*\)/gi, '');
  t = t.replace(/Track\s*\d+/gi, '');
  t = t.replace(/Disc\s*\d+/gi, '');
  t = t.replace(/CD\s*\d+/gi, '');
  // Remover versoes
  t = t.replace(/\(v\d+\.\d+\)/gi, '');
  t = t.replace(/\(v\d+\)/gi, '');
  // Remover extras
  t = t.replace(/\(Alt\)/gi, '').replace(/\(Beta[^)]*\)/gi, '');
  t = t.replace(/\(Greatest Hits\)/gi, '').replace(/\(Platinum\)/gi, '');
  t = t.replace(/\(PlayStation the Best\)/gi, '').replace(/\(PSone Books\)/gi, '');
  t = t.replace(/\(Premium Box\)/gi, '').replace(/\(Deluxe Pack\)/gi, '');
  t = t.replace(/\(Limited Edition\)/gi, '').replace(/\(Rental\)/gi, '');
  t = t.replace(/\(Tentou You [^)]*\)/gi, '').replace(/\(Front Mission History\)/gi, '');
  t = t.replace(/-nao-conversivel/gi, '');
  // Remover timestamps _NNNNNNNNN
  t = t.replace(/_\d{10}$/, '');
  t = t.replace(/_\d+$/, '');
  // Limpar chars
  t = t.replace(/[._]/g, ' ');
  t = t.replace(/\s+/g, ' ').trim();
  // Remover chars invalidos para nome de pasta
  t = t.replace(/[<>:"/\\|?*]/g, '');
  return t.trim();
}

// Chave de agrupamento: nome do jogo sem track/disc/numero
function gameKey(name) {
  let t = cleanGameName(name);
  t = t.toLowerCase().replace(/[^a-z0-9]/g, '');
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

// === 1. Coletar todos os arquivos ===
const allFiles = walkDir(DUP);
const dataFiles = allFiles.filter(f => /\.(bin|img|iso)$/i.test(f));
const cueFiles = allFiles.filter(f => /\.cue$/i.test(f));

console.log(`Arquivos: ${dataFiles.length} bins, ${cueFiles.length} cues`);

// === 2. Agrupar bins por jogo ===
// Cada bin pertence a um jogo. Multi-track = mesmo jogo.
const games = new Map(); // key -> {serial, region, gameName, files: [{path, ext, trackNum}], cues: []}

for (const bin of dataFiles) {
  const basename = path.basename(bin);
  const ext = path.extname(bin).toLowerCase();
  const baseNoExt = basename.replace(/\.(bin|img|iso)$/i, '');
  const dir = path.dirname(bin);

  // Pular corrompidos
  try { if (fs.statSync(bin).size < 1024 * 1024) continue; } catch { continue; }
  // Pular demos
  if (isDemo(basename) || isDemo(path.basename(dir))) continue;

  const serial = extractSerial(basename) || extractSerial(path.basename(dir));
  const key = serial ? serial : gameKey(baseNoExt);

  if (!games.has(key)) {
    const gameName = cleanGameName(baseNoExt);
    games.set(key, {
      serial,
      region: serialRegion(serial),
      gameName,
      dir,
      files: [],
      cues: []
    });
  }

  // Extrair numero do track
  let trackNum = 0;
  const tm = baseNoExt.match(/Track\s*0*(\d+)/i);
  if (tm) trackNum = parseInt(tm[1]);

  games.get(key).files.push({ path: bin, ext, baseNoExt, trackNum });
}

// === 3. Associar cues aos jogos ===
for (const cue of cueFiles) {
  const basename = path.basename(cue, '.cue');
  const dir = path.dirname(cue);
  const serial = extractSerial(basename) || extractSerial(path.basename(dir));
  const key = serial ? serial : gameKey(basename);

  if (games.has(key)) {
    games.get(key).cues.push(cue);
  } else {
    // Cue sem bin correspondente - pode ser cue principal de multi-track
    // Tentar匹配 por gameKey
    const gk = gameKey(basename);
    for (const [_k, g] of games) {
      if (gameKey(g.gameName) === gk) {
        g.cues.push(cue);
        break;
      }
    }
  }
}

console.log(`Jogos identificados: ${games.size}`);

// === 4. Para cada jogo: criar pasta, mover arquivos, criar cue correto ===
const report = [];
let processed = 0, errors = 0;

for (const [key, game] of games) {
  const { serial, region, gameName, files, cues, dir } = game;

  if (files.length === 0) continue;

  // Nome da pasta: [SERIAL] se tem serial, senao [GameName]
  const folderName = serial || gameName.replace(/[^a-zA-Z0-9_\-().[\]]/g, '_').substring(0, 60);
  const newDir = path.join(DUP, folderName);

  try {
    if (!fs.existsSync(newDir)) fs.mkdirSync(newDir, { recursive: true });
    if (processed % 10 === 0) console.log(`Progresso: ${processed}/${games.size} jogos...`);

    // Nome base para arquivos: GameName-Serial (ou GameName se sem serial)
    const fileBase = serial ? `${gameName}-${serial}` : gameName;
    const safeFileBase = fileBase.replace(/[<>:"/\\|?*]/g, '').substring(0, 120);

    // Ordenar bins por track number
    files.sort((a, b) => {
      if (a.trackNum !== b.trackNum) return a.trackNum - b.trackNum;
      return a.baseNoExt.localeCompare(b.baseNoExt);
    });

    // Determinar se é multi-track
    const isMultiTrack = files.length > 1;
    const hasExplicitTracks = files.some(f => f.trackNum > 0);

    // Renomear e mover bins
    const newBinNames = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      let newBinName;
      if (isMultiTrack || hasExplicitTracks) {
        const trackStr = String(i + 1).padStart(2, '0');
        newBinName = `${safeFileBase} (Track ${trackStr})${f.ext}`;
      } else {
        newBinName = `${safeFileBase}${f.ext}`;
      }
      const newPath = path.join(newDir, newBinName);
      try {
        // Usar rename (move instantaneo no mesmo volume D:)
        if (path.dirname(f.path).toLowerCase() === newDir.toLowerCase()) {
          // Ja esta na pasta certa, so renomear
          if (path.basename(f.path) !== newBinName) {
            fs.renameSync(f.path, newPath);
          }
        } else {
          fs.renameSync(f.path, newPath);
        }
        newBinNames.push(newBinName);
      } catch (e) {
        // Fallback: copiar + deletar se rename falhar (cross-volume)
        try {
          fs.copyFileSync(f.path, newPath);
          fs.unlinkSync(f.path);
          newBinNames.push(newBinName);
        } catch (e2) {
          errors++;
          console.log(`[ERR] mover ${f.path}: ${e2.message.substring(0, 60)}`);
        }
      }
    }

    // Criar .cue correto
    // Ler o cue mais completo (que referencia mais bins)
    let bestCue = null;
    let bestCueRefCount = 0;
    for (const cue of cues) {
      try {
        const content = fs.readFileSync(cue, 'utf8');
        const refCount = (content.match(/FILE\s+"/gi) || []).length;
        if (refCount > bestCueRefCount) {
          bestCue = content;
          bestCueRefCount = refCount;
        }
      } catch {}
    }

    let cueContent;
    if (bestCue && bestCueRefCount === newBinNames.length) {
      // O cue existente referencia todos os bins - apenas atualizar nomes
      cueContent = bestCue;
      // Substituir cada FILE "xxx" BINARY pelo novo nome
      let binIdx = 0;
      cueContent = cueContent.replace(/FILE\s+"[^"]+"\s+BINARY/gi, () => {
        const name = newBinNames[binIdx++] || newBinNames[0];
        return `FILE "${name}" BINARY`;
      });
    } else {
      // Criar cue generico
      cueContent = '';
      for (let i = 0; i < newBinNames.length; i++) {
        if (i === 0) {
          cueContent += `FILE "${newBinNames[i]}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n`;
        } else {
          cueContent += `FILE "${newBinNames[i]}" BINARY\n  TRACK ${String(i + 1).padStart(2, '0')} AUDIO\n    INDEX 01 00:00:00\n`;
        }
      }
    }

    const cuePath = path.join(newDir, `${safeFileBase}.cue`);
    fs.writeFileSync(cuePath, cueContent);

    // Deletar cues antigos
    for (const cue of cues) {
      if (path.resolve(cue) !== path.resolve(cuePath)) {
        try { fs.unlinkSync(cue); } catch {}
      }
    }

    // Deletar arquivos relacionados antigos (sub, ccd, mds, mdf, ape, 7z, txt, html)
    const dir2 = dir;
    try {
      const oldFiles = fs.readdirSync(dir2);
      for (const of of oldFiles) {
        const ofPath = path.join(dir2, of);
        if (ofPath === newDir) continue;
        if (/\.(sub|ccd|mds|mdf|ape|7z|txt|html|gba|Zone\.Identifier)$/i.test(of)) {
          try { fs.unlinkSync(ofPath); } catch {}
        }
      }
    } catch {}

    processed++;
    report.push({
      serial: serial || 'N/A',
      region,
      gameName,
      tracks: newBinNames.length,
      folder: folderName,
      cueFile: `${safeFileBase}.cue`
    });

  } catch (e) {
    errors++;
    if (errors < 20) console.log(`[ERR] ${key}: ${e.message.substring(0, 80)}`);
  }
}

console.log(`\nProcessados: ${processed} jogos`);
console.log(`Erros: ${errors}`);

// === 5. Limpar pastas vazias e arquivos soltos ===
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

// Deletar arquivos soltos que nao sao .bin/.img/.iso/.cue (ja movidos)
const remaining = walkDir(DUP);
let cleaned = 0;
for (const f of remaining) {
  if (!/\.(bin|img|iso|cue)$/i.test(f)) {
    try { fs.unlinkSync(f); cleaned++; } catch {}
  }
}
rmEmpty(DUP);
console.log(`Lixo limpo: ${cleaned}`);

// === 6. Gerar jogos-atuais.md ===
report.sort((a, b) => {
  if (a.region !== b.region) {
    const pri = { USA: 0, EUR: 1, OTHER: 2, JPN: 3 };
    return (pri[a.region] ?? 9) - (pri[b.region] ?? 9);
  }
  return a.gameName.localeCompare(b.gameName);
});

let md = `# Jogos Aproveitaveis em D:\\roms\\duplicados\n\n`;
md += `**Data:** ${new Date().toISOString().split('T')[0]}\n\n`;
md += `**Total de jogos:** ${report.length}\n\n`;
md += `**Criterio:** USA > EUR > Outros > JPN | Sem demos\n\n`;
md += `| # | Serial | Regiao | Jogo | Tracks | Pasta |\n`;
md += `|---|--------|--------|------|--------|-------|\n`;
for (let i = 0; i < report.length; i++) {
  const r = report[i];
  md += `| ${i + 1} | ${r.serial} | ${r.region} | ${r.gameName} | ${r.tracks} | ${r.folder} |\n`;
}

const mdPath = 'F:\\importre\\jogos-atuais.md';
fs.writeFileSync(mdPath, md);
console.log(`\nLista gerada: ${mdPath}`);
console.log(`Total de jogos aproveitaveis: ${report.length}`);
