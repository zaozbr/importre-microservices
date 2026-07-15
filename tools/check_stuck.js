const axios = require('axios');

(async () => {
  const r = await axios.post('http://127.0.0.1:16810/jsonrpc', {
    jsonrpc: '2.0', id: '1', method: 'aria2.tellActive', params: []
  }, { timeout: 15000 });

  const active = r.data.result;
  const stuck = active.filter(d => parseInt(d.downloadSpeed) < 10240);

  console.log(`Downloads parados: ${stuck.length}/${active.length}\n`);

  stuck.slice(0, 15).forEach(d => {
    const name = d.files[0].path.split('\\').pop();
    const url = d.files[0].uris[0]?.uri || 'sem URL';
    const status = d.files[0].uris[0]?.status || 'sem status';
    const code = d.files[0].uris[0]?.errorCode || '';
    const done = (parseInt(d.completedLength) / 1048576).toFixed(1);
    const total = (parseInt(d.totalLength) / 1048576).toFixed(1);
    console.log(`${name}  ${done}/${total}MB  status=${status}  code=${code}`);
    console.log(`  URL: ${url.substring(0, 120)}`);
    console.log();
  });

  // Agrupar por status
  const statuses = {};
  stuck.forEach(d => {
    const s = d.files[0].uris[0]?.status || 'unknown';
    statuses[s] = (statuses[s] || 0) + 1;
  });
  console.log('--- Por status ---');
  Object.entries(statuses).forEach(([s, c]) => console.log(`${s}: ${c}`));
})().catch(e => console.error('Erro:', e.message));
