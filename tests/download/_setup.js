// Helper para testes: mocka config antes de carregar o servico de download
// Garante que PSX_DIR aponta para diretorio temporario isolado.
const fs = require('fs');
const path = require('path');
const os = require('os');

// Singleton: cria tmpDir apenas uma vez (compartilhado entre todos os testes)
if (!global.__IMPORTRE_TEST_TMPDIR) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'importre-test-'));
  if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });
  global.__IMPORTRE_TEST_TMPDIR = tmpDir;

  process.env.PSX_DIR = tmpDir;
  process.env.ROMS_DIR = path.dirname(tmpDir);

  // Mock config via require.cache (so funciona se config ainda nao foi carregado)
  try {
    const configPath = require.resolve('../../shared/config');
    if (!require.cache[configPath]) {
      require.cache[configPath] = {
        id: configPath,
        filename: configPath,
        loaded: true,
        exports: {
          PSX_DIR: tmpDir,
          ROMS_DIR: path.dirname(tmpDir),
          STATE_DIR: tmpDir,
          DUP_DIR: tmpDir,
          CHD_TEMP_DIR: tmpDir,
          PORTS: { QUEUE: 9001, SEARCH: 9002, DOWNLOAD: 9003, CHD: 9004, ORCHESTRATOR: 8767 },
          WORKERS: { SEARCH: 15, DOWNLOAD: 30, CHD: 2 },
          ARIA2: { CONNECTIONS: 16, SPLIT: 16, MIN_SPEED_MBPS: 1.0, TOTAL_SPEED_MBPS: 20.0, SPEED_CHECK_INTERVAL_MS: 30000, SLOW_DOWNLOAD_THRESHOLD_MS: 60000 },
          SOURCE_LIMITS: {},
          WORKER_ALLOCATION: {},
          LOG_PATH: path.join(tmpDir, 'test.log'),
          QUEUE_PATH: path.join(tmpDir, 'queue.json'),
          SITES_PATH: path.join(tmpDir, 'sites.json'),
          BLACKLIST_PATH: path.join(tmpDir, 'blacklist.json'),
          LEARNING_PATH: path.join(tmpDir, 'learning.json'),
          CONTROL_PATH: path.join(tmpDir, 'control.json'),
          DL_PROGRESS_PATH: path.join(tmpDir, 'dl_progress.json'),
          ARCHIVE_JP_INDEX: path.join(tmpDir, 'archive_jp_index.json'),
          COOLROM_INDEX: path.join(tmpDir, 'coolrom_index.json'),
          CHDMAN_PATH: path.join(tmpDir, 'chdman.exe'),
        }
      };
    }
  } catch (e) {
    // Config ja carregado - usa env vars
  }
}

const tmpDir = global.__IMPORTRE_TEST_TMPDIR;

module.exports = { tmpDir };
