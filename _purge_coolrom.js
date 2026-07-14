const axios = require('axios');
const QUEUE_URL = 'http://127.0.0.1:9001';

async function purgeCoolrom() {
  const r = await axios.get(`${QUEUE_URL}/queue`, { timeout: 30000 });
  const q = r.data;
  let cleaned = 0;
  let requeued = 0;
  for (const item of q.queue) {
    if (!item.sources || !item.sources.length) continue;
    const hasCoolrom = item.sources.some(s => s.site === 'coolrom');
    if (!hasCoolrom) continue;
    if (item.status === 'completed') continue; // nao mexe em completos

    // Remove coolrom das fontes
    const remaining = item.sources.filter(s => s.site !== 'coolrom');

    if (remaining.length === 0) {
      // Sem outras fontes - volta para pending para re-busca
      try {
        await axios.post(`${QUEUE_URL}/queue/update`, {
          serial: item.serial,
          updates: { status: 'pending', sources: [], retry_count: 0 }
        }, { timeout: 5000 });
        requeued++;
      } catch (e) { /* ignora */ }
    } else {
      // Mantem outras fontes, so remove coolrom
      try {
        await axios.post(`${QUEUE_URL}/queue/update`, {
          serial: item.serial,
          updates: { sources: remaining }
        }, { timeout: 5000 });
        cleaned++;
      } catch (e) { /* ignora */ }
    }
  }
  console.log(`Coolrom removido de ${cleaned} itens (mantiveram outras fontes)`);
  console.log(`${requeued} itens voltaram para pending (sem outras fontes)`);
}
purgeCoolrom().catch(e => console.log('err:', e.message));
