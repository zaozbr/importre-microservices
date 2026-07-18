const axios = require('axios');

async function main() {
  const url = 'https://romspure.cc/roms/sony-playstation/senryaku-shougi/';
  const userAgents = [
    'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
    'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0'
  ];

  for (const ua of userAgents) {
    try {
      const r = await axios.get(url, {
        timeout: 15000,
        headers: { 'User-Agent': ua, 'Accept': 'text/html' },
        validateStatus: () => true
      });
      console.log(ua.substring(0, 30), '-> Status:', r.status);
      if (r.status === 200) {
        const h = r.data;
        const links = [...h.matchAll(/href="([^"]*download[^"]*)"/gi)].map(m => m[1]);
        console.log('  DL links:', links.slice(0, 5));
        const forms = [...h.matchAll(/<form[^>]*action="([^"]*)"/gi)].map(m => m[1]);
        console.log('  Forms:', forms.slice(0, 3));
      }
    } catch (e) {
      console.log(ua.substring(0, 30), '-> Error:', e.message);
    }
  }
}
main();
