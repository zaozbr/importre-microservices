const { loadJson, buildSource } = require('./_base');

module.exports = {
  name: 'homebrew',
  matchType: 'serial',
  needsMultiChunk: false,
  priority: 27,
  enabled: true,
  search(serial, _title) {
    if (!serial.startsWith('HBREW-')) return [];
    const idx = loadJson('homebrew_index.json');
    const info = idx[serial];
    if (!info || !info.urls) return [];
    return info.urls.map((url, i) => buildSource('homebrew', url, `${info.name} (parte ${i + 1})`));
  }
};
