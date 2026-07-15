#!/usr/bin/env node
/**
 * speed_monitor.js — Monitoramento contínuo para atingir 40MB/s
 * - Verifica velocidade a cada 30s
 * - Se < 40MB/s, diagnostica e tenta corrigir
 * - Purge stopped downloads
 * - Aumenta concurrent se preciso
 * - Log em logs/speed_monitor.log
 */
const axios = require('axios');
const fs = require('fs');
const path = require('path');

const RPC_URL = 'http://127.0.0.1:16810/jsonrpc';
const LOG_FILE = path.join(__dirname, '..', 'logs', 'speed_monitor.log');
const TARGET_MBPS = 40;
const CHECK_INTERVAL_MS = 30000;
const CONSECUTIVE_TARGETS_NEEDED = 3;

let consecutiveTargets = 0;
let totalChecks = 0;

function log(msg) {
  const ts = new Date().toISOString();
  const line = `[${ts}] ${msg}`;
  console.log(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

async function rpc(method, params = []) {
  const r = await axios.post(RPC_URL, { jsonrpc: '2.0', method, id: '1', params }, { timeout: 15000 });
  return r.data.result;
}

async function getStats() {
  return await rpc('aria2.getGlobalStat');
}

async function getActive() {
  return await rpc('aria2.tellActive', []);
}

async function purgeStopped() {
  try { await rpc('aria2.purgeDownloadResult'); } catch {}
}

async function setMaxConcurrent(n) {
  try { await rpc('aria2.changeGlobalOption', [{ 'max-concurrent-downloads': String(n) }]); } catch {}
}

async function diagnose(speedMbps, active, stopped) {
  const issues = [];

  if (speedMbps < 1 && active > 0) {
    issues.push('Velocidade muito baixa com downloads ativos — possivel throttling do servidor');
  }
  if (active < 10 && speedMbps < TARGET_MBPS) {
    issues.push(`Poucos downloads ativos (${active}) — download service pode nao estar alimentando`);
  }
  if (stopped > 20) {
    issues.push(`Muitos stopped (${stopped}) — fazendo purge`);
    await purgeStopped();
  }
  if (active > 50 && speedMbps < 10) {
    issues.push(`Muitos downloads (${active}) mas velocidade baixa — possivel saturacao ou RPC instavel`);
  }

  // Verificar fontes
  const downloads = await getActive();
  const byHost = {};
  for (const d of downloads) {
    let host = '?';
    try { host = d.files[0].uris[0].uri.match(/https?:\/\/([^\/]+)/)[1]; } catch {}
    if (!byHost[host]) byHost[host] = { count: 0, speed: 0 };
    byHost[host].count++;
    byHost[host].speed += parseInt(d.downloadSpeed) / 1048576;
  }

  const hostSummary = Object.entries(byHost)
    .sort((a, b) => b[1].speed - a[1].speed)
    .map(([h, v]) => `${h}:${v.count}dl/${v.speed.toFixed(1)}MB/s`)
    .join(' | ');

  return { issues, hostSummary, byHost };
}

async function check() {
  totalChecks++;
  try {
    const stats = await getStats();
    const speed = parseInt(stats.downloadSpeed) / 1048576;
    const active = parseInt(stats.numActive);
    const stopped = parseInt(stats.numStopped);

    const targetMet = speed >= TARGET_MBPS;
    if (targetMet) {
      consecutiveTargets++;
    } else {
      consecutiveTargets = 0;
    }

    const status = targetMet ? 'META ATINGIDA' : 'ABAIXO DA META';
    log(`Check #${totalChecks}: ${speed.toFixed(2)} MB/s | Active: ${active} | Stopped: ${stopped} | ${status} (${consecutiveTargets}/${CONSECUTIVE_TARGETS_NEEDED})`);

    if (!targetMet) {
      const diag = await diagnose(speed, active, stopped);
      if (diag.hostSummary) log(`  Fontes: ${diag.hostSummary}`);
      for (const issue of diag.issues) log(`  ISSUE: ${issue}`);

      // Auto-fix: se active < 20 e tem stopped, purge e tentar alimentar mais
      if (active < 20 && stopped > 5) {
        log('  Auto-fix: purgando stopped para liberar slots');
        await purgeStopped();
      }
    }

    if (consecutiveTargets >= CONSECUTIVE_TARGETS_NEEDED) {
      log(`*** SUCESSO: ${CONSECUTIVE_TARGETS_NEEDED} ciclos consecutivos acima de ${TARGET_MBPS} MB/s! ***`);
    }
  } catch (e) {
    log(`Check #${totalChecks}: ERRO — ${e.message}`);
  }
}

async function main() {
  log(`=== Speed Monitor iniciado — Target: ${TARGET_MBPS} MB/s ===`);
  log(`Intervalo: ${CHECK_INTERVAL_MS / 1000}s | Ciclos necessarios: ${CONSECUTIVE_TARGETS_NEEDED}`);

  // Verificar se daemon está vivo
  try {
    const v = await rpc('aria2.getVersion');
    log(`Daemon v${v.version} OK`);
  } catch (e) {
    log(`ERRO: Daemon nao responde — ${e.message}`);
  }

  // Loop principal
  setInterval(check, CHECK_INTERVAL_MS);
  check(); // Primeiro check imediato
}

main();
