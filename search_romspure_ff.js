const axios = require('axios');
const fs = require('fs');

const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Accept': 'text/html,application/xhtml+xml',
  'Accept-Language': 'en-US,en;q=0.9'
};

async function fetchPage(url) {
  try {
    const r = await axios.get(url, { timeout: 15000, headers, validateStatus: () => true });
    if (r.status === 200) {
      const h = r.data;
      const links = [...h.matchAll(/href="([^"]*download[^"]*)"/gi)].map(m => m[1]);
      return { status: 200, dlLinks: links };
    }
    return { status: r.status };
  } catch (e) {
    return { error: e.message };
  }
}

async function main() {
  const games = [
    { serial: 'SLPS-00142', name: 'senryaku-shougi', url: 'https://romspure.cc/roms/sony-playstation/senryaku-shougi/' },
    { serial: 'SCPS-10108', name: 'poketan', url: 'https://romspure.cc/roms/sony-playstation/poketan/' },
    { serial: 'SLPS-02895', name: 'pacapaca-passion-special', url: 'https://romspure.cc/roms/sony-playstation/pacapaca-passion-special/' },
    { serial: 'SLPM-86274', name: 'reikoku', url: 'https://romspure.cc/roms/sony-playstation/reikoku-ikeda-kizoku-shinrei-kenkyuujo/' },
    { serial: 'SLPM-87255', name: 'soukyuu-gurentai', url: 'https://romspure.cc/roms/sony-playstation/arcade-hits-soukyuu-gurentai/' }
  ];

  for (const game of games) {
    const result = await fetchPage(game.url);
    if (result.status === 200) {
      console.log(game.serial, '-> DL:', result.dlLinks);
    } else {
      console.log(game.serial, '->', result.status || result.error);
    }
  }
}
main();
