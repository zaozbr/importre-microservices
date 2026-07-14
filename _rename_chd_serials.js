'use strict';
/**
 * Renomeia todos os .chd sem serial no nome para o padrão nome-do-jogo-SERIAL.chd
 * Extrai o serial do header do CHD via chdman extractcd.
 * O serial PSX é armazenado no SYSTEM.CNF como SLPS_024.66;1
 */

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROMS_DIR = 'D:\\roms\\library\\roms\\psx';
const CHDMAN = 'F:\\importre\\chdman.exe';
const TEMP_DIR = 'F:\\chd_temp';
const LOG_FILE = 'F:\\importre\\_rename_log.txt';
const PROGRESS_FILE = 'F:\\importre\\_rename_progress.json';
const EXTRACT_TIMEOUT = 180000; // 180s

// Serial no nome do arquivo: SLUS-01272, SLPS_00700, SCUS-94400, SLES-02089, etc
const SERIAL_IN_NAME_RE = /(SLUS|SLES|SLPS|SLPM|SCPS|SCES|SCUS|SLED)[-_]?\d{3,5}/i;

// Serial no BIN: SLPS_024.66 ou SLPS-02466 ou SLPS 024.66
const SERIAL_BIN_RE = /(SLUS|SLES|SLPS|SLPM|SCPS|SCES|SCUS|SLED)[_\-\s]?(\d{3,5})[._]?(\d{0,2})/i;

let tempCounter = 0;

function logMsg(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  fs.appendFileSync(LOG_FILE, line + '\n');
}

function sanitizeName(base, serial) {
  let name = base;
  // Remove serial existente se houver
  name = name.replace(SERIAL_IN_NAME_RE, '');
  // Substitui espaços por hifens
  name = name.replace(/\s+/g, '-');
  // Remove caracteres inválidos
  name = name.replace(/[<>:"/\\|?*]/g, '');
  // Remove hifens duplicados
  name = name.replace(/-+/g, '-');
  // Remove hifens no início/fim
  name = name.replace(/^-+|-+$/g, '');
  // Limita a 150 caracteres (deixando espaço para o serial)
  const serialPart = '-' + serial;
  const maxBase = 150 - serialPart.length;
  if (name.length > maxBase) {
    name = name.substring(0, maxBase).replace(/-+$/g, '');
  }
  return name + serialPart + '.chd';
}

function extractSerialFromCHD(filePath) {
  // Usa nomes únicos para cada extração para evitar conflitos
  const id = `_${process.pid}_${++tempCounter}`;
  const cuePath = path.join(TEMP_DIR, `_rn${id}.cue`);
  const binPath = path.join(TEMP_DIR, `_rn${id}.bin`);

  const result = spawnSync(CHDMAN, [
    'extractcd',
    '-i', filePath,
    '-o', cuePath,
    '-ob', binPath,
    '-f'
  ], {
    timeout: EXTRACT_TIMEOUT,
    windowsHide: true,
    encoding: 'utf8'
  });

  // Mesmo se chdman retornar erro, o BIN pode ter sido criado parcialmente
  if (!fs.existsSync(binPath)) {
    try { fs.unlinkSync(cuePath); } catch {}
    try { fs.unlinkSync(binPath); } catch {}
    return null;
  }

  try {
    // Procura por todos os padrões de serial
    const patterns = ['SLPS', 'SLUS', 'SLES', 'SLPM', 'SCPS', 'SCES', 'SCUS', 'SLED'];

    function searchInData(data) {
      for (const p of patterns) {
        let searchOff = 0;
        while (searchOff < data.length) {
          const idx = data.indexOf(p, searchOff);
          if (idx < 0) break;
          // Extrai contexto ao redor do match
          const ctx = data.slice(idx, Math.min(idx + 30, data.length)).toString('latin1');
          const match = ctx.match(SERIAL_BIN_RE);
          if (match) {
            const prefix = match[1].toUpperCase();
            const num = match[2];
            const ver = match[3] || '';
            let serial;
            if (ver && ver.length > 0) {
              serial = `${prefix}-${num}${ver}`;
            } else {
              serial = `${prefix}-${num}`;
            }
            return serial;
          }
          searchOff = idx + 4;
        }
      }
      return null;
    }

    // Passo 1: lê apenas os primeiros 5MB (mais rápido, cobre a maioria dos casos)
    const stat = fs.statSync(binPath);
    const partialSize = Math.min(5242880, stat.size);
    const fd = fs.openSync(binPath, 'r');
    const partialBuf = Buffer.alloc(partialSize);
    const bytesRead = fs.readSync(fd, partialBuf, 0, partialSize, 0);
    fs.closeSync(fd);
    const partialData = partialBuf.slice(0, bytesRead);

    let result = searchInData(partialData);
    if (result) return result;

    // Passo 2: se não encontrou nos primeiros 5MB, lê o arquivo inteiro
    const fullData = fs.readFileSync(binPath);
    result = searchInData(fullData);
    if (result) return result;
  } catch (e) {
    // erro de leitura
  } finally {
    // SEMPRE limpa os arquivos temporários
    try { fs.unlinkSync(cuePath); } catch {}
    try { fs.unlinkSync(binPath); } catch {}
  }

  return null;
}

function loadProgress() {
  try {
    return JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8'));
  } catch {
    return { processed: [], renamed: 0, notFound: 0, errors: 0 };
  }
}

function saveProgress(prog) {
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify(prog));
}

function main() {
  // Inicia log
  logMsg('=== INÍCIO DO RENOMEAMENTO DE CHDs ===');

  // Lista todos os .chd
  const allFiles = fs.readdirSync(ROMS_DIR)
    .filter(f => f.toLowerCase().endsWith('.chd'))
    .sort();

  logMsg(`Total de CHDs encontrados: ${allFiles.length}`);

  // Filtra os que NÃO têm serial no nome
  const withoutSerial = allFiles.filter(f => !SERIAL_IN_NAME_RE.test(f));
  logMsg(`CHDs SEM serial no nome: ${withoutSerial.length}`);

  const prog = loadProgress();
  const processedSet = new Set(prog.processed);

  let renamed = prog.renamed || 0;
  let notFound = prog.notFound || 0;
  let errors = prog.errors || 0;
  let batchCount = 0;

  for (let i = 0; i < withoutSerial.length; i++) {
    const filename = withoutSerial[i];
    const fullPath = path.join(ROMS_DIR, filename);

    // Pula se já processado
    if (processedSet.has(filename)) {
      continue;
    }

    // Verifica se o arquivo ainda existe (pode ter sido renomeado)
    if (!fs.existsSync(fullPath)) {
      processedSet.add(filename);
      continue;
    }

    const baseName = filename.replace(/\.chd$/i, '');

    logMsg(`[${i + 1}/${withoutSerial.length}] Processando: ${filename}`);

    let serial = null;
    try {
      serial = extractSerialFromCHD(fullPath);
    } catch (e) {
      logMsg(`  ERRO na extração: ${e.message}`);
      errors++;
    }

    if (serial) {
      const newName = sanitizeName(baseName, serial);
      const newPath = path.join(ROMS_DIR, newName);

      // Verifica se o novo nome é diferente do atual
      if (newName === filename) {
        logMsg(`  Já está com nome correto: ${filename}`);
      } else if (fs.existsSync(newPath)) {
        // Conflito: arquivo de destino já existe
        logMsg(`  AVISO: destino já existe: ${newName} — mantendo original`);
        notFound++;
      } else {
        try {
          fs.renameSync(fullPath, newPath);
          logMsg(`  RENOMEADO: ${filename} -> ${newName}`);
          renamed++;
        } catch (e) {
          logMsg(`  ERRO ao renomear: ${e.message}`);
          errors++;
        }
      }
    } else {
      logMsg(`  SERIAL NÃO ENCONTRADO: ${filename}`);
      notFound++;
    }

    processedSet.add(filename);
    prog.processed = Array.from(processedSet);
    prog.renamed = renamed;
    prog.notFound = notFound;
    prog.errors = errors;
    saveProgress(prog);

    batchCount++;

    // Reporta progresso a cada 50 arquivos
    if (batchCount % 50 === 0) {
      logMsg(`--- PROGRESSO: ${batchCount} processados | Total renomeados: ${renamed} | Não encontrados: ${notFound} | Erros: ${errors} ---`);
    }
  }

  logMsg(`=== CONCLUÍDO ===`);
  logMsg(`Total renomeados: ${renamed}`);
  logMsg(`Serial não encontrado: ${notFound}`);
  logMsg(`Erros: ${errors}`);
  logMsg(`Total processados: ${processedSet.size}`);
}

main();
