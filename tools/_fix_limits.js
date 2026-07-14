const fs = require('fs');
let cfg = fs.readFileSync('F:/importre/shared/config.js', 'utf8');
const replacements = [
  ["'archive.org': 6", "'archive.org': 10"],
  ["'archive.org-jp': 6", "'archive.org-jp': 10"],
  ["'archive_org': 6", "'archive_org': 10"],
  ["'archive_org_jp': 6", "'archive_org_jp': 10"],
  ["'archive.org-extra': 6", "'archive.org-extra': 10"],
  ["'archive_extra': 6", "'archive_extra': 10"],
  ["'archive_chd_jp': 6", "'archive_chd_jp': 10"],
  ["'archive_redump_jp': 6", "'archive_redump_jp': 10"],
  ["'archive_gamelist_202205': 6", "'archive_gamelist_202205': 10"],
  ["'archive_ps1_eu_chd_arquivista': 6", "'archive_ps1_eu_chd_arquivista': 10"],
  ["'archive_psximagefiles': 6", "'archive_psximagefiles': 10"],
  ["'archive_sony_playstation_part1': 6", "'archive_sony_playstation_part1': 10"],
  ["'archive_centuron_psx': 6", "'archive_centuron_psx': 10"],
  ["'archive_redumpsonyplaystationamerica20160617': 6", "'archive_redumpsonyplaystationamerica20160617': 10"],
  ["'archive_2024_sony_playstation_usa_hearto_1g1r_collection': 6", "'archive_2024_sony_playstation_usa_hearto_1g1r_collection': 10"],
  ["'archive_sony_play_station_japan_non_redump': 6", "'archive_sony_play_station_japan_non_redump': 10"],
  ["'romsfun': 10", "'romsfun': 15"],
];
for (const [from, to] of replacements) {
  cfg = cfg.split(from).join(to);
}
fs.writeFileSync('F:/importre/shared/config.js', cfg);
console.log('SOURCE_LIMITS aumentado');
