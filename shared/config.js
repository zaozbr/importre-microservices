const path = require('path');

const ROMS_DIR = process.env.ROMS_DIR || 'D:\\roms\\library\\roms';
const PSX_DIR = path.join(ROMS_DIR, 'psx');
const STATE_DIR = process.env.STATE_DIR || 'F:\\importre_state';
const DUP_DIR = process.env.DUP_DIR || 'D:\\roms\\duplicados';
const CHD_TEMP_DIR = process.env.CHD_TEMP_DIR || 'F:\\chd_temp';
const DOWNLOAD_DIR = process.env.DOWNLOAD_DIR || 'F:\\downloads';

module.exports = {
  ROMS_DIR,
  PSX_DIR,
  STATE_DIR,
  DUP_DIR,
  CHD_TEMP_DIR,
  DOWNLOAD_DIR,
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
    QUEUE: 9011,
    SEARCH: 9002,
    DOWNLOAD: 9003,
    CHD: 9004,
    ORCHESTRATOR: 8767
  },
  WORKERS: {
    SEARCH: 40,
    DOWNLOAD: 40,
    CHD: 2
  },
  ARIA2: {
    CONNECTIONS: 16,
    SPLIT: 16,
    MIN_SPEED_MBPS: 0.25,
    TOTAL_SPEED_MBPS: 40.0,
    SPEED_CHECK_INTERVAL_MS: 30000,
    SLOW_DOWNLOAD_THRESHOLD_MS: 120000
  },
  SOURCE_LIMITS: {
    'archive.org': 40,
    'archive.org-jp': 40,
    'archive_org': 40,
    'archive_org_jp': 40,
    'archive.org-extra': 40,
    'archive_extra': 40,
    'coolrom': 10,
    'vimm': 20,
    'retrostic': 20,
    'romsdl': 10,
    'romsretro': 10,
    'romspedia': 20,
    'romsgames': 10,
    'homebrew': 4,
    'myrient': 20,
    'psxdatacenter': 4,
    'romulation': 20,
    'consoleroms': 10,
    'freeroms': 10,
    'cdromance': 10,
    'romsfun': 0,
    'archive_chd_jp': 40,
    'archive_redump_jp': 40,
    'archive_gamelist_202205': 40,
    'archive_ps1_eu_chd_arquivista': 40,
    'archive_psximagefiles': 40,
    'archive_sony_playstation_part1': 40,
    'archive_centuron_psx': 40,
    'archive_redumpsonyplaystationamerica20160617': 40,
    'archive_2024_sony_playstation_usa_hearto_1g1r_collection': 40,
    'archive_sony_play_station_japan_non_redump': 40,
    // Torrent/magnet sources (limite 3 - BitTorrent nao sofre throttling)
    'archive-centuron-psx-torrent': 3,
    'archive-sony-play-station-japan-non-redump-torrent': 3,
    'archive-chd-jp-torrent': 3,
    'archive-redumpsonyplaystationamerica20160617-torrent': 3,
    'archive-sony-playstation-part1-torrent': 3,
    'archive-psximagefiles-torrent': 3,
    'archive-ps1-eu-chd-arquivista-torrent': 3,
    'archive-gamelist-202205-torrent': 3,
    // Novas fontes web
    'retromania': 4,
    'romspure': 4,
    'google_fallback': 2
  },
  // Alocação: 20 archive.org + 10 archive.org-jp + 0 coolrom + 30 RR
  // Total: 60 workers - archive.org limita ~0.25MB/s por arquivo, compensar com paralelismo
  WORKER_ALLOCATION: {
    'archive.org': 20,
    'archive.org-jp': 10,
    'coolrom': 0,
    'round_robin': 30
  }
};
