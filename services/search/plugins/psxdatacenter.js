const { loadJson, normalize, buildSource } = require('./_base');

module.exports = {
  name: 'psxdatacenter',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 25,
  enabled: true,
  search(serial, title) {
    // psxdatacenter nao tem download direto; usamos como fonte de referencia
    return [];
  }
};
