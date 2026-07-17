/**
 * kill_before_start.js — Garante que processos antigos sejam mortos
 * antes de iniciar um novo servico ou abrir uma janela.
 *
 * PROPOSITO: Toda vez que um servico vai ser (re)iniciado, devemos:
 * 1. Matar o processo antigo (por PID, se conhecido)
 * 2. Matar qualquer processo na porta-alvo (zumbis)
 * 3. Aguardar a porta libererar (TIME_WAIT)
 * 4. SO ENTÃO iniciar o novo processo
 *
 * Isso evita:
 * - Portas ocupadas por processos zumbis
 * - Multiplas instancias do mesmo servico
 * - Janelas duplicadas abertas
 * - Conflitos de bind EADDRINUSE
 *
 * Uso:
 *   const { killBeforeStart } = require('./shared/kill_before_start');
 *   await killBeforeStart({ port: 9001, pid: oldPid, name: 'queue' });
 *   spawn('node', ['services/queue/index.js'], { windowsHide: true, detached: true });
 */
const { execSync } = require('child_process');

/**
 * Mata processo por PID.
 * @param {number} pid
 * @returns {boolean} true se matou (ou ja estava morto)
 */
function killPid(pid) {
  if (!pid || pid === process.pid) return false;
  try {
    process.kill(pid, 'SIGTERM');
  } catch (e) {
    // ja morto
  }
  // Aguardar 500ms e forcar kill se ainda vivo
  try {
    execSync(`taskkill /F /PID ${pid}`, { windowsHide: true, timeout: 3000, stdio: 'ignore' });
  } catch (e) {
    // ja morto ou sem permissao
  }
  return true;
}

/**
 * Encontra PIDs em LISTENING numa porta.
 * @param {number} port
 * @returns {number[]}
 */
function pidsOnPort(port) {
  const pids = new Set();
  try {
    const output = execSync('netstat -ano', { encoding: 'utf8', timeout: 5000, windowsHide: true });
    for (const line of output.split('\n')) {
      if (line.includes('LISTENING') && line.includes(`:${port} `)) {
        const m = line.match(/\s+(\d+)\s*$/);
        if (m) pids.add(parseInt(m[1]));
      }
    }
  } catch (e) {}
  return [...pids];
}

/**
 * Mata todos os processos em LISTENING numa porta.
 * @param {number} port
 * @returns {number} quantidade de processos mortos
 */
function killByPort(port) {
  const pids = pidsOnPort(port);
  for (const pid of pids) {
    if (pid === process.pid) continue;
    killPid(pid);
  }
  return pids.length;
}

/**
 * Verifica se uma porta esta livre (sem LISTENING).
 * @param {number} port
 * @returns {boolean}
 */
function isPortFree(port) {
  return pidsOnPort(port).length === 0;
}

/**
 * Aguarda uma porta libererar.
 * @param {number} port
 * @param {number} timeoutMs - timeout em ms (default 10000)
 * @returns {Promise<boolean>} true se liberou, false se timeout
 */
async function waitForPortFree(port, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (isPortFree(port)) return true;
    await new Promise(r => setTimeout(r, 500));
  }
  return isPortFree(port);
}

/**
 * Mata processos por nome de imagem (ex: 'aria2c.exe').
 * NUNCA usar para 'chdman.exe' (compartilhado com conversor CHD).
 * @param {string} imageName - nome do executavel (ex: 'aria2c.exe')
 * @returns {number} quantidade de processos mortos
 */
function killByName(imageName) {
  let count = 0;
  try {
    const output = execSync(`wmic process where "name='${imageName}'" get ProcessId /value`, {
      encoding: 'utf8', timeout: 5000, windowsHide: true,
    });
    for (const line of output.split('\n')) {
      const m = line.match(/ProcessId=(\d+)/);
      if (m) {
        const pid = parseInt(m[1]);
        if (pid && pid !== process.pid) {
          killPid(pid);
          count++;
        }
      }
    }
  } catch (e) {}
  return count;
}

/**
 * ROTINA COMPLETA: matar processo antigo + aguardar porta + pronto para iniciar.
 *
 * @param {Object} opts
 * @param {number} [opts.port] - porta do servico (mata zumbis nela)
 * @param {number} [opts.pid] - PID do processo antigo conhecido
 * @param {string} [opts.name] - nome do servico para log
 * @param {string} [opts.imageName] - nome do exe para matar todos (ex: 'aria2c.exe')
 * @param {boolean} [opts.waitPort] - se true, aguarda porta liberar (default true)
 * @param {number} [opts.waitTimeoutMs] - timeout para aguardar porta (default 10000)
 * @param {Function} [opts.log] - funcao de log (default console.log)
 * @returns {Promise<{killed: number, portFree: boolean}>}
 */
async function killBeforeStart(opts = {}) {
  const {
    port,
    pid,
    name = 'service',
    imageName,
    waitPort = true,
    waitTimeoutMs = 10000,
    log = (msg) => console.log(`[kill-before-start] ${msg}`),
  } = opts;

  let killed = 0;

  // 1. Matar processo antigo por PID
  if (pid) {
    log(`${name}: matando processo antigo PID ${pid}...`);
    if (killPid(pid)) killed++;
  }

  // 2. Matar zumbis na porta
  if (port) {
    const portPids = pidsOnPort(port).filter(p => p !== process.pid);
    if (portPids.length > 0) {
      log(`${name}: matando ${portPids.length} processo(s) zumbi na porta ${port}...`);
      for (const p of portPids) {
        killPid(p);
        killed++;
      }
    }
  }

  // 3. Matar por nome de imagem (opcional)
  if (imageName) {
    const imgKilled = killByName(imageName);
    if (imgKilled > 0) {
      log(`${name}: matou ${imgKilled} processo(s) de ${imageName}`);
      killed += imgKilled;
    }
  }

  // 4. Aguardar porta liberar
  let portFree = true;
  if (waitPort && port) {
    log(`${name}: aguardando porta ${port} liberar...`);
    portFree = await waitForPortFree(port, waitTimeoutMs);
    if (!portFree) {
      log(`${name}: AVISO porta ${port} ainda ocupada apos ${waitTimeoutMs}ms`);
    }
  }

  return { killed, portFree };
}

module.exports = {
  killPid,
  pidsOnPort,
  killByPort,
  isPortFree,
  waitForPortFree,
  killByName,
  killBeforeStart,
};
