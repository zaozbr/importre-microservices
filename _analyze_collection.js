const axios = require('axios');
const fs = require('fs');
const path = require('path');

const PSX_DIR = 'D:\\roms\\library\\roms\\PSX';
const QUEUE_URL = 'http://127.0.0.1:9001';

async function analyze() {
  console.log('=== ANALISE GERAL DA COLECAO ===\n');

  // 1. Arquivos no disco
  const allFiles = fs.existsSync(PSX_DIR) ? fs.readdirSync(PSX_DIR) : [];
  const chdFiles = allFiles.filter(f => f.endsWith('.chd'));
  const binFiles = allFiles.filter(f => f.endsWith('.bin'));
  const cueFiles = allFiles.filter(f => f.endsWith('.cue'));
  const isoFiles = allFiles.filter(f => f.endsWith('.iso'));
  const archiveFiles = allFiles.filter(f => /\.(7z|zip|rar)$/.test(f));
  const aria2Files = allFiles.filter(f => f.endsWith('.aria2'));

  // Seriais unicos no disco
  const serialsOnDisk = new Set();
  const chdSerials = new Set();
  const needsConversion = new Set();
  const incompleteSerials = new Set();

  for (const f of allFiles) {
    const m = f.match(/^([A-Z]+-\d{3,5})/);
    if (!m) continue;
    const serial = m[1];
    serialsOnDisk.add(serial);
    if (f.endsWith('.chd')) {
      chdSerials.add(serial);
    } else if (f.endsWith('.aria2')) {
      incompleteSerials.add(serial);
    } else if (/\.(bin|cue|iso|7z|zip|rar|img)$/.test(f) && !chdSerials.has(serial)) {
      needsConversion.add(serial);
    }
  }

  // 2. Estado da fila
  let queueStats = {};
  let totalQueue = 0;
  let regions = { JP: 0, US: 0, EU: 0, OTHER: 0 };
  let completedRegions = { JP: 0, US: 0, EU: 0, OTHER: 0 };
  let pendingRegions = { JP: 0, US: 0, EU: 0, OTHER: 0 };
  let failedItems = [];

  try {
    const r = await axios.get(`${QUEUE_URL}/queue`, { timeout: 30000 });
    const q = r.data;
    totalQueue = q.queue.length;
    q.queue.forEach(i => {
      queueStats[i.status] = (queueStats[i.status] || 0) + 1;
      let reg = 'OTHER';
      if (/^SLPS|^SCPS|^SLPM/.test(i.serial)) reg = 'JP';
      else if (/^SLUS|^SCUS/.test(i.serial)) reg = 'US';
      else if (/^SLES|^SCES/.test(i.serial)) reg = 'EU';
      regions[reg]++;
      if (i.status === 'completed') completedRegions[reg]++;
      if (['pending', 'ready', 'searching', 'downloading'].includes(i.status)) pendingRegions[reg]++;
      if (i.status === 'failed') failedItems.push(i.serial);
    });
  } catch (e) {
    console.log('Erro ao conectar ao queue service:', e.message);
  }

  // 3. Tamanho total (apenas CHDs, que sao o produto final)
  let chdSize = 0;
  for (const f of chdFiles) {
    try { chdSize += fs.statSync(path.join(PSX_DIR, f)).size; } catch (e) { }
  }

  console.log('--- ARQUIVOS NO DISCO ---');
  console.log(`  Total arquivos: ${allFiles.length}`);
  console.log(`  CHD (convertidos): ${chdFiles.length} (${(chdSize / 1024 / 1024 / 1024).toFixed(1)} GB)`);
  console.log(`  BIN: ${binFiles.length}, CUE: ${cueFiles.length}, ISO: ${isoFiles.length}`);
  console.log(`  Arquivos compactados (7z/zip/rar): ${archiveFiles.length}`);
  console.log(`  Downloads incompletos (.aria2): ${aria2Files.length}`);
  console.log(`  Seriais unicos no disco: ${serialsOnDisk.size}`);

  console.log('\n--- ESTADO DA FILA ---');
  console.log(`  Total de itens na fila: ${totalQueue}`);
  Object.entries(queueStats).sort((a, b) => b[1] - a[1]).forEach(([k, v]) => {
    console.log(`    ${k}: ${v}`);
  });

  console.log('\n--- POR REGIAO ---');
  console.log(`  JP (SLPS/SCPS/SLPM): ${regions.JP} total | ${completedRegions.JP} completos | ${pendingRegions.JP} pendentes`);
  console.log(`  US (SLUS/SCUS):      ${regions.US} total | ${completedRegions.US} completos | ${pendingRegions.US} pendentes`);
  console.log(`  EU (SLES/SCES):      ${regions.EU} total | ${completedRegions.EU} completos | ${pendingRegions.EU} pendentes`);
  console.log(`  OTHER:               ${regions.OTHER} total | ${completedRegions.OTHER} completos | ${pendingRegions.OTHER} pendentes`);

  console.log('\n--- CONVERSAO CHD ---');
  console.log(`  CHDs ja convertidos: ${chdSerials.size}`);
  console.log(`  Aguardando conversao (bin/cue/iso/7z/zip no disco): ${needsConversion.size}`);
  console.log(`  Downloads incompletos (.aria2): ${incompleteSerials.size}`);

  console.log('\n=== RESUMO EXECUTIVO ===');
  const completedCount = queueStats.completed || 0;
  const pendingCount = (queueStats.pending || 0) + (queueStats.ready || 0) + (queueStats.searching || 0) + (queueStats.downloading || 0);
  const cooldownCount = queueStats.cooldown || 0;
  const failedCount = queueStats.failed || 0;
  console.log(`  Total na fila:        ${totalQueue}`);
  console.log(`  Completos:            ${completedCount} (${(completedCount / totalQueue * 100).toFixed(1)}%)`);
  console.log(`  Pendentes (baixar):   ${pendingCount} (${(pendingCount / totalQueue * 100).toFixed(1)}%)`);
  console.log(`  Em cooldown:          ${cooldownCount}`);
  console.log(`  Falhados:             ${failedCount}`);
  console.log(`  Convertidos CHD:      ${chdSerials.size}`);
  console.log(`  Faltam converter:     ${needsConversion.size}`);
  console.log(`  Incompletos:          ${incompleteSerials.size}`);
  console.log(`  Tamanho CHDs:         ${(chdSize / 1024 / 1024 / 1024).toFixed(1)} GB`);

  if (failedItems.length > 0) {
    console.log(`\n  Seriais falhados (${failedItems.length}):`);
    failedItems.slice(0, 20).forEach(s => console.log(`    ${s}`));
    if (failedItems.length > 20) console.log(`    ... e mais ${failedItems.length - 20}`);
  }

  if (needsConversion.size > 0 && needsConversion.size <= 30) {
    console.log(`\n  Seriais aguardando conversao (${needsConversion.size}):`);
    [...needsConversion].forEach(s => console.log(`    ${s}`));
  } else if (needsConversion.size > 30) {
    console.log(`\n  Seriais aguardando conversao: ${needsConversion.size} (mostrando primeiros 20)`);
    [...needsConversion].slice(0, 20).forEach(s => console.log(`    ${s}`));
    console.log(`    ... e mais ${needsConversion.size - 20}`);
  }

  if (incompleteSerials.size > 0 && incompleteSerials.size <= 20) {
    console.log(`\n  Seriais com download incompleto (${incompleteSerials.size}):`);
    [...incompleteSerials].forEach(s => console.log(`    ${s}`));
  } else if (incompleteSerials.size > 20) {
    console.log(`\n  Seriais com download incompleto: ${incompleteSerials.size} (mostrando primeiros 20)`);
    [...incompleteSerials].slice(0, 20).forEach(s => console.log(`    ${s}`));
    console.log(`    ... e mais ${incompleteSerials.size - 20}`);
  }
}

analyze().catch(e => console.log('Erro:', e.message));
