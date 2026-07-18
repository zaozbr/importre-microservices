const axios = require('axios');
const querystring = require('querystring');

const AJAX_URL = 'https://romspure.cc/wp-admin/admin-ajax.php';
const headers = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Accept': 'application/json, text/javascript, */*; q=0.01',
  'Accept-Language': 'en-US,en;q=0.9',
  'X-Requested-With': 'XMLHttpRequest',
  'Origin': 'https://romspure.cc',
  'Referer': 'https://romspure.cc/download/senryaku-shougi-124778/1'
};

async function getNonce() {
  const r = await axios.post(AJAX_URL, querystring.stringify({ action: 'romspure_get_nonce' }), {
    headers: { ...headers, 'Content-Type': 'application/x-www-form-urlencoded' },
    timeout: 15000
  });
  console.log('Nonce response:', JSON.stringify(r.data));
  if (r.data && r.data.success && r.data.data && r.data.data.nonce) {
    return r.data.data.nonce;
  }
  throw new Error('Failed to get nonce: ' + JSON.stringify(r.data));
}

async function getDownloadLink(postId, index, nonce) {
  const body = querystring.stringify({
    action: 'app_get_download_link',
    post_id: String(postId),
    index: String(index),
    nonce: nonce
  });
  const r = await axios.post(AJAX_URL, body, {
    headers: { ...headers, 'Content-Type': 'application/x-www-form-urlencoded' },
    timeout: 15000
  });
  console.log('Download link response:', JSON.stringify(r.data));
  if (r.data && r.data.success && r.data.data && r.data.data.url) {
    return r.data.data;
  }
  throw new Error('Failed to get download link: ' + JSON.stringify(r.data));
}

async function main() {
  // Test with senryaku-shougi (post_id=124778, index=1)
  const nonce = await getNonce();
  console.log('Nonce:', nonce);

  const dl = await getDownloadLink(124778, 1, nonce);
  console.log('Download URL:', dl.url);
  console.log('Name:', dl.name);
  console.log('Size:', dl.size);
}
main().catch(e => console.log('Error:', e.message));
