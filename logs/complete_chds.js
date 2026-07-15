const fs = require('fs');
const http = require('http');

const serials = fs.readFileSync('F:\\importre\\logs\\moved_chds.txt', 'utf8')
  .split('\n').map(s => s.trim()).filter(Boolean);

const QUEUE_PORT = 9001;

function complete(serial) {
  return new Promise(resolve => {
    const data = JSON.stringify({ serial });
    const req = http.request(
      { hostname: '127.0.0.1', port: QUEUE_PORT, path: '/queue/complete', method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) } },
      res => { let b = ''; res.on('data', d => { b += d; }); res.on('end', () => { try { resolve(JSON.parse(b)); } catch { resolve(null); } }); }
    );
    req.on('error', () => resolve(null));
    req.setTimeout(5000, () => { req.destroy(); resolve(null); });
    req.write(data); req.end();
  });
}

(async () => {
  let ok = 0, fail = 0;
  for (const serial of serials) {
    const r = await complete(serial);
    if (r && r.ok) { ok++; console.log(`OK: ${serial}`); }
    else { fail++; console.log(`FAIL: ${serial}`); }
  }
  console.log(`\nResumo: ${ok} completados, ${fail} falhas`);
})();
