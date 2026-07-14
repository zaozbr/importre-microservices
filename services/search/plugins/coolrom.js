const { loadJson, normalize, titleScore, buildSource } = require('./_base');

// Extrai numero de volume/sequencia do titulo
// Ex: "Simple 1500 Series Vol.75" -> "75", "Suudoku 3" -> "3", "Hello Kitty Vol.04" -> "04"
function extractVolumeNum(text) {
  if (!text) return null;
  const norm = normalize(text);
  // Padroes: "vol 75", "vol. 75", "volume 75"
  const volMatch = norm.match(/vol(?:ume)?\.?\s*(\d+)/i);
  if (volMatch) return volMatch[1];
  // Padrao: numero apos nome do jogo (sequel): "Suudoku 3", "Biohazard 2"
  // Pega qualquer numero 1-99 que nao seja 1500 (series name) ou ano
  const seqMatch = norm.match(/(?:^|\s)(\d{1,2})(?:\s|$)/g);
  if (seqMatch) {
    for (const m of seqMatch) {
      const num = m.trim();
      if (num !== '1500' && !/^19\d{2}$/.test(num) && !/^20\d{2}$/.test(num) && parseInt(num) >= 2) {
        return num;
      }
    }
  }
  return null;
}

module.exports = {
  name: 'coolrom',
  matchType: 'title',
  needsMultiChunk: true,
  priority: 3,
  enabled: false, // DESATIVADO: bug de volume entrega arquivos errados (0/13 corretos)
  search(serial, title) {
    const data = loadJson('coolrom_index.json');
    const crData = data.cr_data || data;
    const target = normalize(title || serial);
    if (!target || target.length < 3) return [];

    const targetVol = extractVolumeNum(title || serial);

    const results = [];
    const scored = [];

    for (const item of Object.values(crData)) {
      if (!item.norm || !item.url) continue;

      const score = titleScore(target, item.norm);
      if (score < 0.7) continue;

      // Validacao critica de volume: se o alvo tem volume, o item deve ter o MESMO volume
      if (targetVol) {
        const itemVol = extractVolumeNum(item.name);
        if (itemVol && itemVol !== targetVol) {
          // Volume diferente - rejeita completamente
          continue;
        }
        // Se item nao tem volume mas alvo tem, penaliza muito
        if (!itemVol) {
          continue;
        }
      }

      scored.push({ item, score });
    }

    // Ordena por score (maior primeiro)
    scored.sort((a, b) => b.score - a.score);

    for (const { item, score } of scored.slice(0, 3)) {
      results.push(buildSource('coolrom', `https://coolrom.com.au${item.url}`, item.name, { score }));
    }
    return results;
  }
};
