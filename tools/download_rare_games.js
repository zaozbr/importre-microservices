/**
 * download_rare_games.js — Baixa jogos raros encontrados no Google.
 *
 * Fontes encontradas:
 * - CDRomance: Zeiramzone (SLPS-00575), Soukyugurentai (SLPM-87255)
 * - Romspure: Ayakashi Ninden Kunoichiban (SLPS-00946), PokeTan (SCPS-10108),
 *   Guuguuthropus (SLPM-86148), Pacapaca Passion Special (SLPS-02895)
 * - Roms2000: Pacapaca Passion Special (SLPS-02895)
 * - RomsBase: Mahjong Ganryuujima (SLPS-02979)
 * - Archive.org: Bow and Arrow PSX (HBREW-027)
 * - itch.io free: Turbo-Tihu (HBREW-032)
 * - Hitmen: PSXMahjongg (HBREW-044)
 * - Blogspot: Flappy Adventure 3 (HBREW-013)
 *
 * Uso: node tools/download_rare_games.js
 */
const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

const DOWNLOAD_DIR = 'F:\\downloads';
const TIMEOUT = 60000;

const games = [
  // Homebrew com URLs diretas
  { serial: 'HBREW-027', name: 'Bow and Arrow PSX', url: 'https://archive.org/download/bow_and_arrow_iso/bow_and_arrow_iso.zip' },
  { serial: 'HBREW-044', name: 'PSXMahjongg', url: 'http://hitmen.c02.at/files/releases/psx_mahjongg.zip' },
  // Jogos comerciais — URLs de pagina (precisa scraping para achar download direto)
  { serial: 'SLPS-00575', name: 'Zeiramzone', url: 'https://cdromance.org/psx-iso/zeiramzone-japan/' },
  { serial: 'SLPS-00946', name: 'Ayakashi Ninden Kunoichiban', url: 'https://romspure.cc/roms/sony-playstation/ayakashi-ninden-kunoichiban/' },
  { serial: 'SCPS-10108', name: 'PokeTan', url: 'https://romspure.cc/roms/sony-playstation/poketan/' },
  { serial: 'SLPM-86148', name: 'Guuguuthropus', url: 'https://romspure.cc/roms/sony-playstation/guuguuthropus/' },
  { serial: 'SLPS-02895', name: 'Pacapaca Passion Special', url: 'https://romspure.cc/roms/sony-playstation/pacapaca-passion-special/' },
  { serial: 'SLPS-02979', name: 'Mahjong Ganryuujima', url: 'https://www.romsbase.com/rom/playstation/mahjong-ganryuujima-jp/21243' },
];

function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const proto = url.startsWith('https') ? https : http;
    const file = fs.createWriteStream(dest);
    const req = proto.get(url, { timeout: TIMEOUT, headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' } }, (res) => {
      if (res.statusCode === 301 || res.statusCode === 302) {
        file.close();
        fs.unlinkSync(dest);
        return downloadFile(res.headers.location, dest).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        file.close();
        fs.unlinkSync(dest);
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      res.pipe(file);
      file.on('finish', () => { file.close(); resolve(dest); });
    });
    req.on('error', (e) => { file.close(); try { fs.unlinkSync(dest); } catch {} reject(e); });
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

async function main() {
  console.log('=== DOWNLOAD RARE GAMES ===');
  for (const game of games) {
    const ext = game.url.endsWith('.zip') ? '.zip' : '.html';
    const dest = path.join(DOWNLOAD_DIR, `${game.serial}${ext}`);
    if (fs.existsSync(dest)) {
      console.log(`SKIP ${game.serial} (ja existe): ${game.name}`);
      continue;
    }
    console.log(`Baixando ${game.serial}: ${game.name}...`);
    try {
      await downloadFile(game.url, dest);
      const size = Math.round(fs.statSync(dest).size / 1024);
      console.log(`  OK: ${size} KB -> ${dest}`);
    } catch (e) {
      console.log(`  FALHOU: ${e.message}`);
      try { fs.unlinkSync(dest); } catch {}
    }
  }
  console.log('=== CONCLUIDO ===');
}

main().catch(e => console.error('Erro:', e));
