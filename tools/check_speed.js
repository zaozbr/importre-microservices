const axios = require('axios');

(async () => {
  const r = await axios.post('http://127.0.0.1:16810/jsonrpc', {
    jsonrpc: '2.0', id: '1', method: 'aria2.tellActive', params: ['token:devin']
  }, { timeout: 15000 });

  const active = r.data.result;
  console.log('Total ativos:', active.length);
  const sorted = active.sort((a, b) => parseInt(b.downloadSpeed) - parseInt(a.downloadSpeed));

  console.log('\n--- Top 10 mais rapidos ---');
  sorted.slice(0, 10).forEach(d => {
    const speed = (parseInt(d.downloadSpeed) / 1048576).toFixed(1);
    const size = (parseInt(d.totalLength) / 1048576).toFixed(0);
    const done = (parseInt(d.completedLength) / 1048576).toFixed(0);
    const name = d.files[0].path.split('\\').pop();
    console.log(`${speed}MB/s  ${done}/${size}MB  ${name}`);
  });

  console.log('\n--- Bottom 10 mais lentos ---');
  sorted.slice(-10).forEach(d => {
    const speed = (parseInt(d.downloadSpeed) / 1048576).toFixed(2);
    const size = (parseInt(d.totalLength) / 1048576).toFixed(0);
    const done = (parseInt(d.completedLength) / 1048576).toFixed(0);
    const name = d.files[0].path.split('\\').pop();
    console.log(`${speed}MB/s  ${done}/${size}MB  ${name}`);
  });

  const speeds = active.map(d => parseInt(d.downloadSpeed));
  const total = speeds.reduce((a, b) => a + b, 0);
  const fast = speeds.filter(s => s > 1048576).length;
  const slow = speeds.filter(s => s < 10240).length;
  console.log('\n--- Stats ---');
  console.log(`Total: ${(total / 1048576).toFixed(1)}MB/s`);
  console.log(`Rapidos (>1MB/s): ${fast}`);
  console.log(`Parados (<10KB/s): ${slow}`);

  // Verificar de quais sites vem os downloads
  const sites = {};
  active.forEach(d => {
    const url = d.files[0].uris[0]?.uri || '';
    let site = 'outros';
    if (url.includes('archive.org')) site = 'archive.org';
    else if (url.includes('coolrom')) site = 'coolrom';
    else if (url.includes('vimm')) site = 'vimm';
    else if (url.includes('romspedia')) site = 'romspedia';
    sites[site] = (sites[site] || 0) + 1;
  });
  console.log('\n--- Por site ---');
  Object.entries(sites).sort((a, b) => b[1] - a[1]).forEach(([site, count]) => {
    console.log(`${site}: ${count} downloads`);
  });
})().catch(e => console.error('Erro:', e.message));
