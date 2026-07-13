module.exports = {
  name: 'psxdatacenter',
  matchType: 'serial',
  needsMultiChunk: true,
  priority: 25,
  enabled: true,
  search(_serial, _title) {
    // psxdatacenter nao tem download direto; usamos como fonte de referencia
    return [];
  }
};
