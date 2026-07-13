const path = require('path');

const ROMS_DIR = process.env.ROMS_DIR || 'D:\\roms\\library\\roms';
const PSX_DIR = path.join(ROMS_DIR, 'psx');
const STATE_DIR = path.join(ROMS_DIR, '_importre_state');
const DUP_DIR = process.env.DUP_DIR || 'D:\\roms\\duplicados';
const CHD_TEMP_DIR = process.env.CHD_TEMP_DIR || 'F:\\chd_temp';

module.exports = {
  ROMS_DIR,
  PSX_DIR,
  STATE_DIR,
  DUP_DIR,
  CHD_TEMP_DIR,
  CHDMAN_PATH: path.join(PSX_DIR, 'chdman.exe'),
  QUEUE_PATH: path.join(STATE_DIR, 'queue.json'),
  SITES_PATH: path.join(STATE_DIR, 'sites.json'),
  BLACKLIST_PATH: path.join(STATE_DIR, 'blacklist.json'),
  LEARNING_PATH: path.join(STATE_DIR, 'learning.json'),
  CONTROL_PATH: path.join(STATE_DIR, 'control.json'),
  LOG_PATH: path.join(STATE_DIR, 'importre.log'),
  DL_PROGRESS_PATH: path.join(STATE_DIR, 'dl_progress.json'),
  ARCHIVE_JP_INDEX: path.join(STATE_DIR, 'archive_jp_index.json'),
  COOLROM_INDEX: path.join(STATE_DIR, 'coolrom_index.json'),
  PORTS: {
    QUEUE: 9001,
    SEARCH: 9002,
    DOWNLOAD: 9003,
    CHD: 9004,
    ORCHESTRATOR: 8767
  },
  WORKERS: {
    SEARCH: 15,
    DOWNLOAD: 20,
    CHD: 2
  },
  ARIA2: {
    CONNECTIONS: 16,
    SPLIT: 16,
    MIN_SPEED_MBPS: 1.0,
    TOTAL_SPEED_MBPS: 20.0,
    SPEED_CHECK_INTERVAL_MS: 30000,
    SLOW_DOWNLOAD_THRESHOLD_MS: 60000
  },
  SOURCE_LIMITS: {
    'archive.org': 6,
    'archive.org-jp': 4,
    'archive_org': 6,
    'archive_org_jp': 4,
    'archive.org-extra': 3,
    'archive_extra': 3,
    'coolrom': 5,
    'vimm': 3,
    'retrostic': 3,
    'romsdl': 3,
    'romsretro': 2,
    'romspedia': 2,
    'romsgames': 2,
    'homebrew': 2,
    'myrient': 2,
    'psxdatacenter': 2,
    'romulation': 2,
    'consoleroms': 2,
    'freeroms': 2,
    'cdromance': 2,
    'romsfun': 2
  },
  // Alocação obrigatória: 2 archive.org + 2 archive.org-jp + 5 coolrom + 10 RR
  // Total: 19 workers, mínimo 10 fontes diferentes ativas
  WORKER_ALLOCATION: {
    'archive.org': 2,
    'archive.org-jp': 2,
    'coolrom': 5,
    'round_robin': 11
  }
};
